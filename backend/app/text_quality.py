"""
Detects a specific, confirmed data-quality problem in the canonical
project dataset: Hindi/Devanagari source text that has been corrupted
into literal '?' characters somewhere upstream of this application.

This is not a rendering or encoding bug on our side. Inspecting the raw
bytes of canonical_projects.csv confirms the corruption is already baked
into the file -- e.g. work_description for WS/MP1/2023-2024/1215 is
literally ``P.C.C ??? ?? ???????`` at the byte level, not Devanagari text
that merely displays wrong. The original characters are gone; nothing
downstream can recover them.

Given that, the only honest behaviour is to detect this pattern and
withhold the field (falling back to something else, or to None) rather
than showing garbled text as though it were a real project name or
description. The frontend already did this for `work_description` via
`cleanWorkDescription()` in lib/normalizers.js -- this is the backend
counterpart, so the same rule applies wherever this data reaches a
client, not just the one screen that happened to surface it first:
GET /projects (ProjectOut.project_name), GET /projects/query, and the
role dashboards (ScopedProjectRow.work_description) all read through
this one function so the heuristic cannot drift between them.
"""

from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s")

# Matches the frontend's cleanWorkDescription() thresholds exactly:
# at least 3 '?' characters, and more than 15% of the (whitespace-
# stripped) text is '?'. Both conditions are needed so a short string
# with an incidental question mark ("Repair work?") isn't misflagged.
_MIN_QUESTION_MARKS = 3
_CORRUPTION_RATIO = 0.15


def is_corrupted_text(text: str | None) -> bool:
    """True when `text` matches the known '?'-corruption pattern."""
    if not text:
        return False

    compact = _WHITESPACE.sub("", text)
    if not compact:
        return False

    question_marks = compact.count("?")
    if question_marks < _MIN_QUESTION_MARKS:
        return False

    return (question_marks / len(compact)) > _CORRUPTION_RATIO


def clean_source_text(text: str | None) -> str | None:
    """Return `text` unchanged, or None if it is corrupted or empty.

    Callers should apply this to any free-text field sourced from
    canonical_projects.csv's work_description column (directly, or via
    a derived field such as project_name) before it reaches a response.
    """
    if text is None:
        return None

    stripped = text.strip()
    if not stripped:
        return None

    if is_corrupted_text(stripped):
        return None

    return stripped