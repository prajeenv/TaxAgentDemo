"""Structural enforcement of the core principle: the determination package must
never depend on the LLM or conversation layer.

This is the whole legal/testability rationale, enforced by a test rather than by
discipline. If someone imports `anthropic`, `openai`, or `app.conversation` inside
`app/determination/`, this fails.
"""

from __future__ import annotations

import ast
from pathlib import Path

_DETERMINATION_DIR = Path(__file__).resolve().parents[1] / "app" / "determination"

# Anything in this set appearing in a determination-package import is a violation.
_FORBIDDEN_ROOTS = {"anthropic", "openai"}
_FORBIDDEN_PREFIXES = ("app.conversation",)


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
    return modules


def test_determination_imports_no_llm_or_conversation_code():
    violations: list[str] = []
    for py_file in _DETERMINATION_DIR.rglob("*.py"):
        modules = _imported_modules(py_file.read_text(encoding="utf-8"))
        for mod in modules:
            root = mod.split(".")[0]
            if root in _FORBIDDEN_ROOTS or mod.startswith(_FORBIDDEN_PREFIXES):
                violations.append(f"{py_file.name} imports forbidden module '{mod}'")
    assert not violations, "separation seam breached: " + "; ".join(violations)
