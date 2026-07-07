"""App configuration: env loading, firm selection, cached ruleset.

The ruleset is loaded once and cached — it's read-only data that all requests share.
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

from app.determination.loader import load_ruleset
from app.determination.models import Ruleset

load_dotenv()

FIRM = os.getenv("FIRM", "steuerkanzlei_mueller")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")


@lru_cache(maxsize=4)
def get_ruleset(firm: str = FIRM) -> Ruleset:
    return load_ruleset(firm)
