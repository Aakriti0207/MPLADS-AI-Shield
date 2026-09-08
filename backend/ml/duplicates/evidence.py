"""Context and JSON evidence enrichment for Phase 6 pairs."""

from __future__ import annotations

import json
import math
from typing import Any

import pandas as pd


def _value(row: pd.Series, column: str) -> Any:
    value = row.get(column)
    if pd.isna(value) or str(value).strip() == "":
        return None
    return str(value)


def same_context(row_a: pd.Series, row_b: pd.Series, column: str) -> bool | None:
    value_a, value_b = _value(row_a, column), _value(row_b, column)
    if value_a is None or value_b is None:
        return None
    return value_a == value_b


def amount_difference(row_a: pd.Series, row_b: pd.Series, column: str) -> float | None:
    value_a = pd.to_numeric(pd.Series([row_a.get(column)]), errors="coerce").iloc[0]
    value_b = pd.to_numeric(pd.Series([row_b.get(column)]), errors="coerce").iloc[0]
    if pd.isna(value_a) or pd.isna(value_b) or not math.isfinite(float(value_a)) or not math.isfinite(float(value_b)):
        return None
    return float(abs(value_a - value_b))


def financial_year_relationship(row_a: pd.Series, row_b: pd.Series) -> str:
    year_a, year_b = _value(row_a, "financial_year"), _value(row_b, "financial_year")
    if year_a is None or year_b is None:
        return "UNKNOWN"
    return "SAME" if year_a == year_b else "DIFFERENT"


def build_evidence(
    row_a: pd.Series,
    row_b: pd.Series,
    similarity_score: float,
    match_type: str,
    frequency_a: int,
    frequency_b: int,
) -> str:
    evidence = {
        "reason": "identical_normalized_description" if match_type == "EXACT_MATCH" else "high_description_similarity",
        "description_match_type": match_type,
        "description_similarity": float(similarity_score),
        "description_frequency_a": int(frequency_a),
        "description_frequency_b": int(frequency_b),
        "same_state": same_context(row_a, row_b, "state"),
        "same_constituency": same_context(row_a, row_b, "constituency"),
        "same_mp": same_context(row_a, row_b, "mp"),
        "same_implementing_agency": same_context(row_a, row_b, "implementing_agency"),
        "financial_year_a": row_a.get("financial_year"),
        "financial_year_b": row_b.get("financial_year"),
        "financial_year_relationship": financial_year_relationship(row_a, row_b),
        "recommended_amount_difference": amount_difference(row_a, row_b, "recommended_amount"),
        "sanction_amount_difference": amount_difference(row_a, row_b, "sanction_amount"),
        "interpretation": "evidence_for_human_review_only",
    }
    return json.dumps(evidence, sort_keys=True, allow_nan=False)
