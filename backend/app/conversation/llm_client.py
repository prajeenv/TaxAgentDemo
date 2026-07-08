"""Provider seam for the conversation runner.

`complete_turn(system, history, user_message) -> TurnOutput` behind a provider
switch (LLM_PROVIDER env). Two implementations return the SAME validated TurnOutput
so runner.py is provider-agnostic:

- DeepSeek V4 Flash (primary): OpenAI-SDK-compatible, JSON mode
  (response_format={"type":"json_object"}). Higher-hallucination, so we
  schema-validate and retry once with the validation error before falling back.
- Claude Sonnet 5 (fallback): forced-tool `emit_turn`, thinking disabled for chat
  latency.

If a provider is unconfigured or errors, the runner still gets a safe TurnOutput
(the caller handles a None return as "use a safe canned turn").
"""

from __future__ import annotations

import json
import os
from typing import Optional

from pydantic import ValidationError

from app.conversation.turn_schema import TurnOutput

# --- Config -----------------------------------------------------------------

PROVIDER = os.getenv("LLM_PROVIDER", "deepseek").lower()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

Message = dict[str, str]  # {"role": "user"|"assistant", "content": str}

# Thinking mode (DEEPSEEK_THINKING env; default ENABLED):
#  - ENABLED (default): the agent REASONS about the conversation — it asks the tax
#    year, follows up on vague answers ("you said your workplace changed — tell me
#    more"), and infers what to ask next. This is the product thesis: an intelligent
#    agent, not a form. Cost: ~8-9s/turn (the reasoning chain), softened by the UI's
#    staged typing status. The determination stays deterministic regardless (the
#    engine, not the model, decides documents), so richer conversation never risks
#    the reserved-advice boundary.
#  - DISABLED: ~3s/turn but the agent is thinner — it follows the script more
#    mechanically and probes less. Fine for a pure form-filling style; not for the
#    "infers hundreds of cases" production vision.
#  max_tokens=2000 gives headroom so JSON never truncates (finish_reason=length ->
#  a costly retry). Low temperature keeps JSON structure reliable.
_THINKING_ENABLED = os.getenv("DEEPSEEK_THINKING", "enabled").lower() != "disabled"
_THINKING_KW = (
    {} if _THINKING_ENABLED
    else {"extra_body": {"thinking": {"type": "disabled"}}}
)
_MAX_TOKENS = 2000
_TEMPERATURE = 0.2

# Module-scoped clients (created once, reused). Reusing the client keeps the TCP+TLS
# connection pool warm across turns instead of re-handshaking to the API every turn
# (~0.3-0.8s/turn saved). Lazily built so importing this module never requires a key.
_deepseek_client = None
_anthropic_client = None


class LLMError(Exception):
    """Raised when a provider fails or returns unparseable output after retry."""


# --- Public API -------------------------------------------------------------


def complete_turn(
    system: str, history: list[Message], user_message: str
) -> TurnOutput:
    """Run one turn through the configured provider; return a validated TurnOutput.

    Raises LLMError if the provider is unconfigured or fails after retry — the
    runner catches this and substitutes a safe canned turn (never leaks raw text).
    """
    messages = [*history, {"role": "user", "content": user_message}]
    if PROVIDER == "anthropic":
        return _complete_anthropic(system, messages)
    return _complete_deepseek(system, messages)


def prewarm() -> None:
    """Fire a tiny throwaway call to open the TLS connection + prime the model path,
    so the first REAL turn isn't cold (~10s -> ~6-7s). Called fire-and-forget on
    session creation. Never raises — a warmup failure must never affect a session.
    It sends no user content and no system prompt, so it has zero guardrail surface.
    """
    try:
        if PROVIDER == "anthropic":
            client = _get_anthropic_client()
            client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=1,
                thinking={"type": "disabled"},
                messages=[{"role": "user", "content": "ping"}],
            )
        else:
            client = _get_deepseek_client()
            client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
    except Exception:
        pass  # warmup is best-effort; a failure is silently ignored


# --- DeepSeek (JSON mode) ---------------------------------------------------


def _get_deepseek_client():
    """Lazily build and cache the DeepSeek client (reused across turns for keep-alive).

    The OpenAI SDK retries transient failures (connection resets, timeouts, 429, 5xx)
    with backoff on its own — max_retries handles the WinError-10054-style dropped
    socket we saw in the wild. A 60s timeout bounds a hung turn.
    """
    global _deepseek_client
    if _deepseek_client is None:
        if not DEEPSEEK_API_KEY:
            raise LLMError("DEEPSEEK_API_KEY not set")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise LLMError(f"openai SDK not installed: {exc}")
        _deepseek_client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            max_retries=3,
            timeout=60.0,
        )
    return _deepseek_client


def _complete_deepseek(system: str, messages: list[Message]) -> TurnOutput:
    client = _get_deepseek_client()
    convo = [{"role": "system", "content": system}, *messages]

    def call(extra_note: Optional[str] = None) -> str:
        msgs = convo if extra_note is None else [*convo, {"role": "user", "content": extra_note}]
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=msgs,
            response_format={"type": "json_object"},
            temperature=_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
            **_THINKING_KW,
        )
        return resp.choices[0].message.content or ""

    # First attempt, then one schema-validated retry with the error appended.
    # Any provider/transport error (post-SDK-retries) becomes an LLMError so the
    # runner's safe-fallback path catches it instead of a raw 500 reaching the client.
    try:
        raw = call()
    except LLMError:
        raise
    except Exception as exc:
        raise LLMError(f"DeepSeek request failed: {type(exc).__name__}: {exc}")
    parsed = _try_parse(raw)
    if parsed is not None:
        return parsed
    retry_note = (
        "Your previous response was not a single valid JSON object matching the "
        "required schema. Respond again with ONLY the JSON object, no prose, no "
        "markdown fences, all required keys present."
    )
    try:
        raw2 = call(retry_note)
    except Exception as exc:
        raise LLMError(f"DeepSeek request failed on retry: {type(exc).__name__}: {exc}")
    parsed2 = _try_parse(raw2)
    if parsed2 is not None:
        return parsed2
    raise LLMError("DeepSeek returned invalid JSON after retry")


# --- Anthropic (forced tool) ------------------------------------------------

_EMIT_TURN_TOOL = {
    "name": "emit_turn",
    "description": "Emit the structured intake turn (reply + extracted facts + control signals).",
    "input_schema": {
        "type": "object",
        "properties": {
            "reply_text": {"type": "string"},
            "profile_update": {
                "type": "object",
                "properties": {"field_updates": {"type": "object"}},
            },
            "addressing_rule_id": {"type": ["string", "null"]},
            "checkpoint": {"type": "boolean"},
            "escalation": {
                "type": "object",
                "properties": {
                    "triggered": {"type": "boolean"},
                    "category": {"type": ["string", "null"]},
                    "client_utterance": {"type": ["string", "null"]},
                    "reason": {"type": ["string", "null"]},
                },
            },
            "conversation_complete": {"type": "boolean"},
        },
        "required": ["reply_text"],
    },
}


def _get_anthropic_client():
    """Lazily build and cache the Anthropic client (reused across turns)."""
    global _anthropic_client
    if _anthropic_client is None:
        if not ANTHROPIC_API_KEY:
            raise LLMError("ANTHROPIC_API_KEY not set")
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise LLMError(f"anthropic SDK not installed: {exc}")
        _anthropic_client = anthropic.Anthropic(
            api_key=ANTHROPIC_API_KEY, max_retries=3, timeout=60.0
        )
    return _anthropic_client


def _complete_anthropic(system: str, messages: list[Message]) -> TurnOutput:
    client = _get_anthropic_client()
    try:
        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1500,
            thinking={"type": "disabled"},  # chat latency; extraction needs no deep reasoning
            system=system,
            messages=messages,
            tools=[_EMIT_TURN_TOOL],
            tool_choice={"type": "tool", "name": "emit_turn"},
        )
    except Exception as exc:
        raise LLMError(f"Anthropic request failed: {type(exc).__name__}: {exc}")
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "emit_turn":
            try:
                return TurnOutput(**block.input)
            except ValidationError as exc:
                raise LLMError(f"Anthropic tool output failed validation: {exc}")
    raise LLMError("Anthropic returned no emit_turn tool call")


# --- Helpers ----------------------------------------------------------------


def _try_parse(raw: str) -> Optional[TurnOutput]:
    """Parse + validate a raw model string into a TurnOutput, tolerating fences."""
    text = raw.strip()
    if text.startswith("```"):
        # strip a ```json ... ``` fence if the model added one despite instructions
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    try:
        return TurnOutput(**data)
    except ValidationError:
        return None
