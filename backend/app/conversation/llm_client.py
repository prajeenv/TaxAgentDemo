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


# --- DeepSeek (JSON mode) ---------------------------------------------------


def _complete_deepseek(system: str, messages: list[Message]) -> TurnOutput:
    if not DEEPSEEK_API_KEY:
        raise LLMError("DEEPSEEK_API_KEY not set")
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise LLMError(f"openai SDK not installed: {exc}")

    # The OpenAI SDK retries transient failures (connection resets, timeouts, 429,
    # 5xx) with backoff on its own — max_retries handles the WinError-10054-style
    # dropped-socket case we saw in the wild. A 60s timeout bounds a hung turn.
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        max_retries=3,
        timeout=60.0,
    )
    convo = [{"role": "system", "content": system}, *messages]

    def call(extra_note: Optional[str] = None) -> str:
        msgs = convo if extra_note is None else [*convo, {"role": "user", "content": extra_note}]
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=msgs,
            response_format={"type": "json_object"},
            temperature=0.3,
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


def _complete_anthropic(system: str, messages: list[Message]) -> TurnOutput:
    if not ANTHROPIC_API_KEY:
        raise LLMError("ANTHROPIC_API_KEY not set")
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise LLMError(f"anthropic SDK not installed: {exc}")

    # The anthropic SDK retries transient failures on its own (default 2); bump it.
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=3, timeout=60.0)
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
