"""Groot's persona: a system prompt defining tone, address style, and character.

Kept as a plain text file (persona.txt, project root) rather than a Python constant so
it's easy to hand-edit without touching code.
"""

from __future__ import annotations

from groot.config import PROJECT_ROOT

PERSONA_FILE = PROJECT_ROOT / "persona.txt"


def load_persona() -> str:
    return PERSONA_FILE.read_text().strip()
