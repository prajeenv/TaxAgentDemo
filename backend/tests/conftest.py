"""Test bootstrap: load .env before any app module imports read the environment.

The LLM battery (test_guardrail_llm.py) decides whether to run based on
DEEPSEEK_API_KEY / ANTHROPIC_API_KEY read at import time in app.conversation.llm_client.
Loading .env here (at collection, before those imports) means the battery runs when a
key is configured and skips cleanly otherwise — without requiring the key to be
exported into the shell.
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()  # loads backend/.env if present; no-op otherwise
