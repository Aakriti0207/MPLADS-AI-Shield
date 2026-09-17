"""Resolve project Parliamentary Constituencies without inventing data.

Usage from backend/:
    python resolve_constituencies.py --input data/processed/canonical_projects.csv

Outputs:
    data/processed/constituency_resolution.csv
    data/processed/canonical_projects_enriched.csv

Resolution policy:
1. Preserve a real source constituency as SOURCE / HIGH.
2. Treat "Sitting Rajya Sabha" as an MP-house marker, not a place.
3. For Rajya Sabha/project rows, learn (state, district) -> Lok Sabha PC candidates
   only from canonical rows that already contain a real constituency.
4. Resolve automatically when the district has exactly one observed PC.
5. If a district has several PCs, resolve only when exactly one candidate PC is
   explicitly mentioned in the work description.
6. Otherwise leave the project UNRESOLVED. Never substitute the state name and
   never guess a PC.

The output is auditable: every row records source, confidence and candidates.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


RAJYA_SABHA_MARKERS = {
    "sitting rajya sabha",
    "rajya sabha",
    "nominated rajya sabha",
}


def clean(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "null", "nat"}:
        return None
    return text


def norm(value) -> str:
    text = clean(value) or ""
    text = text.upper()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_rs_marker(value) -> bool:
    text = (clean(value) or "").casefold()
    return text in RAJYA_SABHA_MARKERS or "rajya sabha" in text


def infer_mp_type(row: pd.Series) -> str:
    constituency = clean(row.get("constituency"))
    houses = (clean(row.get("houses")) or "").upper()

    if is_rs_marker(constituency):
        return "Rajya Sabha"

    # A real constituency is the strongest indication that this project row
    # carries Lok Sabha constituency metadata.
    if constituency:
        return "Lok Sabha"

    if houses == "RS":
        return "Rajya Sabha"
    if houses == "LS":
        return "Lok Sabha"

    # Some canonical rows were merged from LS and RS lifecycle sources.
    # Do not pretend the house is known when the constituency does not tell us.
    return "Unknown"


def build_district_pc_map(df: pd.DataFrame) -> dict[tuple[str, str], list[str]]:
    """Learn candidate PCs only from rows with real source constituencies."""
    candidates: dict[tuple[str, str], set[str]] = {}

    for _, row in df.iterrows():
        state = clean(row.get("state"))
        district = clean(row.get("district"))
        pc = clean(row.get("constituency"))

        if not state or not district or not pc or is_rs_marker(pc):
            continue

        key = (norm(state), norm(district))
        candidates.setdefault(key, set()).add(pc)

    return {
        key: sorted(values, key=str.casefold)
        for key, values in candidates.items()
    }


def pc_mentioned_in_description(pc: str, description) -> bool:
    pc_norm = norm(pc)
    description_norm = norm(description)
    if not pc_norm or not description_norm:
        return False

    # Avoid matching very short accidental tokens.
    return len(pc_norm) >= 4 and pc_norm in description_norm


def resolve_row(
    row: pd.Series,
    district_pc_map: dict[tuple[str, str], list[str]],
) -> dict[str, str | None]:
    original = clean(row.get("constituency"))
    mp_type = infer_mp_type(row)

    # Preserve genuine source constituency.
    if original and not is_rs_marker(original):
        return {
            "mp_type": mp_type,
            "resolved_constituency": original,
            "constituency_resolution_source": "SOURCE",
            "constituency_resolution_confidence": "HIGH",
            "constituency_candidates": original,
        }

    state = clean(row.get("state"))
    district = clean(row.get("district"))

    if not state or not district:
        return {
            "mp_type": mp_type,
            "resolved_constituency": None,
            "constituency_resolution_source": "UNRESOLVED_MISSING_LOCATION",
            "constituency_resolution_confidence": "UNRESOLVED",
            "constituency_candidates": None,
        }

    candidates = district_pc_map.get((norm(state), norm(district)), [])

    if len(candidates) == 1:
        return {
            "mp_type": mp_type,
            "resolved_constituency": candidates[0],
            "constituency_resolution_source": "DISTRICT_UNIQUE_PC",
            "constituency_resolution_confidence": "MEDIUM",
            "constituency_candidates": candidates[0],
        }

    if len(candidates) > 1:
        hits = [
            pc
            for pc in candidates
            if pc_mentioned_in_description(pc, row.get("work_description"))
        ]

        if len(hits) == 1:
            return {
                "mp_type": mp_type,
                "resolved_constituency": hits[0],
                "constituency_resolution_source": "WORK_DESCRIPTION_PC_MATCH",
                "constituency_resolution_confidence": "MEDIUM",
                "constituency_candidates": " | ".join(candidates),
            }

        return {
            "mp_type": mp_type,
            "resolved_constituency": None,
            "constituency_resolution_source": "UNRESOLVED_AMBIGUOUS_DISTRICT",
            "constituency_resolution_confidence": "UNRESOLVED",
            "constituency_candidates": " | ".join(candidates),
        }

    return {
        "mp_type": mp_type,
        "resolved_constituency": None,
        "constituency_resolution_source": "UNRESOLVED_NO_DISTRICT_PC_MAP",
        "constituency_resolution_confidence": "UNRESOLVED",
        "constituency_candidates": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="data/processed/canonical_projects.csv",
        help="Canonical project CSV",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed",
        help="Output directory",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(
        input_path,
        dtype=str,
        engine="python",
    )

    required = {
        "work_id",
        "state",
        "district",
        "constituency",
        "work_description",
        "houses",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise SystemExit(f"Missing required columns: {missing}")

    district_pc_map = build_district_pc_map(df)

    resolution = pd.DataFrame(
        [
            resolve_row(row, district_pc_map)
            for _, row in df.iterrows()
        ]
    )

    audit = pd.concat(
        [
            df[
                [
                    "work_id",
                    "houses",
                    "state",
                    "district",
                    "constituency",
                    "mp",
                    "elected_nominated",
                ]
            ].reset_index(drop=True),
            resolution,
        ],
        axis=1,
    )

    enriched = df.copy()
    enriched["source_constituency"] = enriched["constituency"]
    enriched["mp_type"] = resolution["mp_type"]
    enriched["resolved_constituency"] = resolution["resolved_constituency"]
    enriched["constituency_resolution_source"] = resolution[
        "constituency_resolution_source"
    ]
    enriched["constituency_resolution_confidence"] = resolution[
        "constituency_resolution_confidence"
    ]
    enriched["constituency_candidates"] = resolution[
        "constituency_candidates"
    ]

    # IMPORTANT:
    # Do not overwrite the original constituency column. Backend integration
    # should deliberately choose resolved_constituency when it is available.
    audit_path = output_dir / "constituency_resolution.csv"
    enriched_path = output_dir / "canonical_projects_enriched.csv"

    audit.to_csv(audit_path, index=False, encoding="utf-8")
    enriched.to_csv(enriched_path, index=False, encoding="utf-8")

    counts = resolution["constituency_resolution_source"].value_counts()
    print(f"Input rows: {len(df):,}")
    print()
    print("Resolution summary:")
    for key, value in counts.items():
        print(f"  {key}: {value:,}")

    unresolved = resolution["resolved_constituency"].isna().sum()
    resolved = len(resolution) - unresolved

    print()
    print(f"Resolved constituency: {resolved:,}")
    print(f"Unresolved constituency: {unresolved:,}")
    print(f"Audit: {audit_path}")
    print(f"Enriched canonical: {enriched_path}")
    print()
    print("Original canonical_projects.csv was NOT modified.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
