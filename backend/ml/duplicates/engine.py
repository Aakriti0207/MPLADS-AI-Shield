"""Phase 6 duplicate/similar-work engine and output generation."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from ml.config import BACKEND_ROOT
from ml.duplicates.candidates import DEFAULT_CANDIDATE_LIMIT, exact_pairs, similarity_candidates
from ml.duplicates.evidence import amount_difference, build_evidence, financial_year_relationship, same_context
from ml.duplicates.quality import GARBLED, MISSING, TOO_SHORT, USABLE, classify_description

CANONICAL_INPUT_PATH = BACKEND_ROOT / "data" / "processed" / "canonical_projects.csv"
OUTPUT_DIR = BACKEND_ROOT / "data" / "processed"
MATCH_OUTPUT_PATH = OUTPUT_DIR / "duplicate_matches.csv"
SUMMARY_OUTPUT_PATH = OUTPUT_DIR / "duplicate_summary.csv"
SIMILARITY_THRESHOLD = 0.85
WORK_ID_PATTERN = re.compile(r"^WS/MP\d+/\d{4}-\d{4}/\d+$")
REQUIRED_COLUMNS = frozenset({
    "work_id", "work_description", "state", "constituency", "mp",
    "implementing_agency", "recommended_amount", "sanction_amount",
})
DUPLICATE_MATCH_COLUMNS = [
    "work_id_a", "work_id_b", "match_type", "similarity_score",
    "description_quality_a", "description_quality_b", "description_frequency_a",
    "description_frequency_b", "same_state", "same_constituency", "same_mp",
    "same_implementing_agency", "financial_year_a", "financial_year_b",
    "financial_year_relationship",
    "recommended_amount_difference", "sanction_amount_difference", "evidence_json",
]
DUPLICATE_SUMMARY_COLUMNS = [
    "work_id", "exact_match_count", "similar_match_count",
    "highest_similarity_score", "phase6_status",
]


def _validate_source(source: pd.DataFrame) -> None:
    missing = sorted(REQUIRED_COLUMNS - set(source.columns))
    if missing:
        raise ValueError("canonical_projects is missing required Phase 6 columns: " + ", ".join(missing))
    if source["work_id"].isna().any() or not source["work_id"].is_unique:
        raise ValueError("canonical_projects must have a non-null, unique work_id column")
    malformed = ~source["work_id"].astype(str).str.fullmatch(WORK_ID_PATTERN.pattern).fillna(False)
    if malformed.any():
        raise ValueError("canonical_projects contains malformed canonical Work IDs")


def _prepare(source: pd.DataFrame) -> pd.DataFrame:
    prepared = source.copy(deep=True).reset_index(drop=True)
    years = prepared["work_id"].astype(str).str.extract(r"/(\d{4}-\d{4})/", expand=False)
    prepared["financial_year"] = years
    quality_values = prepared["work_description"].map(classify_description)
    prepared["description_quality"] = quality_values.map(lambda item: item[0])
    prepared["normalized_description"] = quality_values.map(lambda item: item[1])
    usable = prepared["description_quality"].eq(USABLE)
    frequencies = prepared.loc[usable, "normalized_description"].value_counts()
    prepared["description_frequency"] = prepared["normalized_description"].map(frequencies).fillna(0).astype("int64")
    return prepared


def _pair_row(pair: tuple[str, str], match_type: str, score: float, lookup: dict[str, pd.Series], frequencies: dict[str, int]) -> dict:
    work_id_a, work_id_b = pair
    row_a, row_b = lookup[work_id_a], lookup[work_id_b]
    return {
        "work_id_a": work_id_a, "work_id_b": work_id_b, "match_type": match_type,
        "similarity_score": float(score), "description_quality_a": row_a["description_quality"],
        "description_quality_b": row_b["description_quality"], "description_frequency_a": frequencies[work_id_a],
        "description_frequency_b": frequencies[work_id_b], "same_state": same_context(row_a, row_b, "state"),
        "same_constituency": same_context(row_a, row_b, "constituency"), "same_mp": same_context(row_a, row_b, "mp"),
        "same_implementing_agency": same_context(row_a, row_b, "implementing_agency"),
        "financial_year_a": row_a["financial_year"], "financial_year_b": row_b["financial_year"],
        "financial_year_relationship": financial_year_relationship(row_a, row_b),
        "recommended_amount_difference": amount_difference(row_a, row_b, "recommended_amount"),
        "sanction_amount_difference": amount_difference(row_a, row_b, "sanction_amount"),
        "evidence_json": build_evidence(row_a, row_b, score, match_type, frequencies[work_id_a], frequencies[work_id_b]),
    }


def _build_summary(prepared: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    summary = pd.DataFrame({"work_id": prepared["work_id"].astype(str)})
    exact_counts = matches.loc[matches["match_type"].eq("EXACT_MATCH")].groupby("work_id_a").size() if not matches.empty else pd.Series(dtype="int64")
    exact_reverse = matches.loc[matches["match_type"].eq("EXACT_MATCH")].groupby("work_id_b").size() if not matches.empty else pd.Series(dtype="int64")
    similar_counts = matches.loc[matches["match_type"].eq("SIMILAR_MATCH")].groupby("work_id_a").size() if not matches.empty else pd.Series(dtype="int64")
    similar_reverse = matches.loc[matches["match_type"].eq("SIMILAR_MATCH")].groupby("work_id_b").size() if not matches.empty else pd.Series(dtype="int64")
    summary["exact_match_count"] = summary["work_id"].map(exact_counts).fillna(0).astype("int64") + summary["work_id"].map(exact_reverse).fillna(0).astype("int64")
    summary["similar_match_count"] = summary["work_id"].map(similar_counts).fillna(0).astype("int64") + summary["work_id"].map(similar_reverse).fillna(0).astype("int64")
    scores: dict[str, float] = {}
    if not matches.empty:
        for _, row in matches.iterrows():
            scores[row.work_id_a] = max(scores.get(row.work_id_a, 0.0), float(row.similarity_score))
            scores[row.work_id_b] = max(scores.get(row.work_id_b, 0.0), float(row.similarity_score))
    summary["highest_similarity_score"] = summary["work_id"].map(scores).astype("float64")
    quality = prepared.set_index("work_id")["description_quality"]
    summary["phase6_status"] = "NO_MATCH_FOUND"
    summary.loc[quality.isin([MISSING, GARBLED, TOO_SHORT]).reindex(summary.work_id, fill_value=False).to_numpy(), "phase6_status"] = "NOT_EVALUABLE"
    summary.loc[summary["similar_match_count"].gt(0), "phase6_status"] = "SIMILAR_WORK_CANDIDATE"
    summary.loc[summary["exact_match_count"].gt(0), "phase6_status"] = "EXACT_MATCH_CANDIDATE"
    return summary[DUPLICATE_SUMMARY_COLUMNS]


def build_phase6_outputs(canonical_projects: pd.DataFrame, candidate_limit: int = DEFAULT_CANDIDATE_LIMIT) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build deterministic pair evidence and one-row-per-work summaries."""
    _validate_source(canonical_projects)
    prepared = _prepare(canonical_projects)
    usable = prepared[prepared["description_quality"].eq(USABLE)].copy()
    lookup = {str(row.work_id): row for _, row in prepared.iterrows()}
    frequencies = prepared.set_index("work_id")["description_frequency"].astype(int).to_dict()
    exact = set(exact_pairs(usable))
    retrieved = similarity_candidates(usable, candidate_limit=candidate_limit)
    rows = [_pair_row(pair, "EXACT_MATCH", 1.0, lookup, frequencies) for pair in sorted(exact)]
    for pair, score in sorted(retrieved.items()):
        if pair in exact or score < SIMILARITY_THRESHOLD:
            continue
        rows.append(_pair_row(pair, "SIMILAR_MATCH", score, lookup, frequencies))
    matches = pd.DataFrame(rows, columns=DUPLICATE_MATCH_COLUMNS)
    if not matches.empty:
        matches = matches.sort_values(["work_id_a", "work_id_b", "match_type"], kind="mergesort").reset_index(drop=True)
    return matches, _build_summary(prepared, matches)


def run_phase6_from_file(path: Path | str = CANONICAL_INPUT_PATH, candidate_limit: int = DEFAULT_CANDIDATE_LIMIT) -> tuple[pd.DataFrame, pd.DataFrame]:
    return build_phase6_outputs(pd.read_csv(path), candidate_limit=candidate_limit)


def write_phase6_outputs(matches: pd.DataFrame, summary: pd.DataFrame, output_dir: Path | str = OUTPUT_DIR) -> tuple[Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    matches_path, summary_path = output_dir / "duplicate_matches.csv", output_dir / "duplicate_summary.csv"
    matches[DUPLICATE_MATCH_COLUMNS].to_csv(matches_path, index=False)
    summary[DUPLICATE_SUMMARY_COLUMNS].to_csv(summary_path, index=False)
    return matches_path, summary_path
