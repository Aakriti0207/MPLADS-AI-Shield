"""Synthetic validation for Phase 6 duplicate and similar-work evidence."""

from __future__ import annotations

import json
import tempfile

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

from ml.duplicates.candidates import SIMILARITY_BATCH_SIZE, similarity_candidates
from ml.duplicates.engine import (
    DUPLICATE_MATCH_COLUMNS,
    DUPLICATE_SUMMARY_COLUMNS,
    SIMILARITY_THRESHOLD,
    build_phase6_outputs,
    write_phase6_outputs,
)
from ml.duplicates.normalization import normalize_description
from ml.duplicates.quality import GARBLED, MISSING, TOO_SHORT, USABLE, classify_description


def make_row(index: int, description: object, **changes: object) -> dict:
    row = {
        "work_id": f"WS/MP{index}/2024-2025/{index}",
        "work_description": description,
        "state": "State A",
        "constituency": "Constituency A",
        "mp": "Member A",
        "implementing_agency": "Agency A",
        "recommended_amount": 100.0,
        "sanction_amount": 100.0,
    }
    row.update(changes)
    return row


def check(label: str, condition: bool) -> bool:
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}")
    return condition


def previous_similarity_candidates(frame: pd.DataFrame, candidate_limit: int) -> dict[tuple[str, str], float]:
    """Small-fixture reference for the former brute-force implementation."""
    vectorizer = TfidfVectorizer(dtype=np.float64, token_pattern=r"(?u)\b\w+\b")
    matrix = vectorizer.fit_transform(frame["normalized_description"].astype(str).tolist())
    neighbor_count = min(candidate_limit + 1, matrix.shape[0])
    search = NearestNeighbors(n_neighbors=neighbor_count, metric="cosine", algorithm="brute")
    distances, indices = search.fit(matrix).kneighbors(matrix, return_distance=True)
    work_ids = frame["work_id"].astype(str).tolist()
    candidates: dict[tuple[str, str], float] = {}
    for row_index, (row_distances, row_indices) in enumerate(zip(distances, indices)):
        for distance, neighbor_index in zip(row_distances, row_indices):
            if neighbor_index == row_index:
                continue
            pair = tuple(sorted((work_ids[row_index], work_ids[int(neighbor_index)])))
            score = float(1.0 - distance)
            candidates[pair] = max(score, candidates.get(pair, -np.inf))
    return candidates


def main() -> int:
    quality_cases = [
        (None, MISSING), ("   ", MISSING), ("", MISSING), ("short", TOO_SHORT),
        ("a??", GARBLED),
        ("P.C.C ??? ?? ???????", GARBLED),
        ("This is a usable project description", USABLE),
    ]
    rows = [
        make_row(1, "Construction of a community hall at Ward 1."),
        make_row(2, " construction-of a COMMUNITY hall at Ward 1! ", recommended_amount=999.0),
        make_row(3, "Construction of a community hall at Ward 2."),
        make_row(4, "P.C.C ??? ?? ???????"),
        make_row(5, None),
        make_row(6, "short"),
        make_row(7, "Installation of a solar street light at Ward 3."),
        make_row(8, "Installation of solar street lighting at Ward 3."),
        make_row(9, "High Mast LED Light", state="State B"),
        make_row(10, "High Mast LED Light", state="State C"),
        make_row(11, "Road project with same amount", recommended_amount=100.0, sanction_amount=100.0),
        make_row(12, "Construction of a community hall at Ward 1.", state=None, constituency=None),
    ]
    frame = pd.DataFrame(rows)
    matches, summary = build_phase6_outputs(frame, candidate_limit=10)
    pair_set = set(zip(matches.work_id_a, matches.work_id_b))
    exact = matches[matches.match_type.eq("EXACT_MATCH")]
    similar = matches[matches.match_type.eq("SIMILAR_MATCH")]
    checks = [
        *[(check(f"quality {expected}", classify_description(value)[0] == expected)) for value, expected in quality_cases],
        check("NFKC/case/punctuation normalization", normalize_description(" Café, ROAD!  ") == "café road"),
        check("exact punctuation/case variant is matched", len(exact) >= 1),
        check("exact pair has canonical ordering", all(matches.work_id_a < matches.work_id_b)),
        check("no self-pairs", all(matches.work_id_a != matches.work_id_b)),
        check("no duplicate pairs", len(pair_set) == len(matches)),
        check("similarity threshold is explicit", SIMILARITY_THRESHOLD == 0.85),
        check("similar candidates are above threshold", similar.empty or (similar.similarity_score >= SIMILARITY_THRESHOLD).all()),
        check("generic repeated descriptions are retained", ((exact.description_frequency_a > 1) | (exact.description_frequency_b > 1)).any()),
        check("missing and garbled descriptions are not evaluated", set(summary.loc[summary.work_id.isin([rows[3]["work_id"], rows[4]["work_id"], rows[5]["work_id"]]), "phase6_status"]) == {"NOT_EVALUABLE"}),
        check("same amount alone does not create a match", not ((matches.work_id_a == rows[10]["work_id"]) | (matches.work_id_b == rows[10]["work_id"])).any()),
        check("different state does not suppress exact candidate", ((exact.work_id_a == rows[8]["work_id"]) | (exact.work_id_b == rows[8]["work_id"])).any()),
        check("missing context is null rather than false", matches.loc[matches.work_id_a.eq(rows[0]["work_id"]) & matches.work_id_b.eq(rows[11]["work_id"]), "same_state"].isna().all()),
        check("deterministic repeated output", matches.equals(build_phase6_outputs(frame, candidate_limit=10)[0]) and summary.equals(build_phase6_outputs(frame, candidate_limit=10)[1])),
        check("match schema is exact", list(matches.columns) == DUPLICATE_MATCH_COLUMNS),
        check("summary schema is exact", list(summary.columns) == DUPLICATE_SUMMARY_COLUMNS),
        check("evidence is valid JSON", all(json.loads(value)["interpretation"] == "evidence_for_human_review_only" for value in matches.evidence_json)),
        check("exact status is evidence-only", summary.loc[summary.work_id.eq(rows[0]["work_id"]), "phase6_status"].iloc[0] == "EXACT_MATCH_CANDIDATE"),
        check("evidence exposes match and context relationships", all(
            {"description_match_type", "description_similarity", "description_frequency_a", "description_frequency_b",
             "same_state", "same_constituency", "same_mp", "same_implementing_agency",
             "financial_year_relationship", "recommended_amount_difference", "sanction_amount_difference"}
            <= set(json.loads(value)) for value in matches.evidence_json
        )),
        check("financial-year relationship is explicit", set(matches.financial_year_relationship) <= {"SAME", "DIFFERENT", "UNKNOWN"}),
    ]
    candidate_frame = pd.DataFrame({
        "work_id": [f"WS/MP{i}/2024-2025/{i}" for i in range(6)],
        "normalized_description": [
            "project road alpha", "project road alpha beta",
            "project bridge gamma delta", "project school epsilon zeta eta",
            "project library theta iota kappa lambda", "project solar mu",
        ],
    })
    expected_candidates = previous_similarity_candidates(candidate_frame, candidate_limit=2)
    batched_candidates = similarity_candidates(candidate_frame, candidate_limit=2, batch_size=2)
    equivalent_scores = (
        expected_candidates.keys() == batched_candidates.keys()
        and all(np.isclose(expected_candidates[pair], batched_candidates[pair]) for pair in expected_candidates)
    )
    checks.extend([
        check("batched retrieval matches previous small-fixture behavior", equivalent_scores),
        check("configurable batch size is explicit", SIMILARITY_BATCH_SIZE == 256),
        check("candidate limit is respected by each query", len(batched_candidates) <= len(candidate_frame) * 2),
        check("retrieval excludes self-pairs", all(pair[0] != pair[1] for pair in batched_candidates)),
        check("retrieval is deterministic across batch sizes", batched_candidates == similarity_candidates(candidate_frame, candidate_limit=2, batch_size=3)),
    ])
    performance_rows = [make_row(1000 + i, f"Construction of project type {i} in location {i}.") for i in range(500)]
    performance_matches, _ = build_phase6_outputs(pd.DataFrame(performance_rows), candidate_limit=10)
    checks.append(check("bounded candidate retrieval on synthetic data", len(performance_matches) <= 500 * 10))
    with tempfile.TemporaryDirectory() as directory:
        match_path, summary_path = write_phase6_outputs(matches, summary, directory)
        checks.extend([check("match CSV written", match_path.exists()), check("summary CSV written", summary_path.exists())])
    passed = all(checks)
    print(f"PHASE 6: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
