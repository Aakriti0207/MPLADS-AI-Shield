"""Deterministic, language-preserving description normalization."""

from __future__ import annotations

import re
import unicodedata


def normalize_description(value: object) -> str:
    """Normalize punctuation and spacing without translating or rewriting text."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = "".join(" " if unicodedata.category(character).startswith("P") else character for character in text)
    return re.sub(r"\s+", " ", text).strip()
