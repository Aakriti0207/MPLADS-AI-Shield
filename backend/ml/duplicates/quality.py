"""Description quality policy for Phase 6."""

from __future__ import annotations

import math

from ml.duplicates.normalization import normalize_description

MISSING = "MISSING"
GARBLED = "GARBLED"
TOO_SHORT = "TOO_SHORT"
USABLE = "USABLE"


def classify_description(value: object) -> tuple[str, str]:
    """Return the deterministic quality class and normalized description."""
    missing_number = False
    if value is not None:
        try:
            missing_number = math.isnan(value)  # type: ignore[arg-type]
        except TypeError:
            pass
    raw = "" if value is None or missing_number else str(value)
    trimmed = raw.strip()
    normalized = normalize_description(raw)
    if not trimmed or not normalized:
        return MISSING, normalized
    
    non_space = sum(not character.isspace() for character in trimmed)
    question_marks = trimmed.count("?")

    # Garbled content takes precedence when both quality rules apply: it is
    # more informative than TOO_SHORT and must not become usable text.
    if question_marks >= 2 or (
        non_space and question_marks / non_space >= 0.20
    ):
        return GARBLED, normalized
    
    if len(trimmed) < 10:
        return TOO_SHORT, normalized
    
    return USABLE, normalized
