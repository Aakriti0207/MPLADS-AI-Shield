"""Focused tests for Payment AI and Isolation Forest Risk Fusion inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from ml.isolation_forest.engine import fit_isolation_forest_model, score_isolation_forest_data
from ml.payment.engine import fit_payment_model, score_payment_data
from ml.risk import build_output, load_inputs, validate_inputs
from ml.risk_config import ISOLATION_FOREST_CAP, PAYMENT_CAP, RISK_COMPONENT_CAPS
from test_phase7_risk import _anomaly_row, _compliance_finding, _match_row, make_inputs, row_for


def producer_outputs(work_ids: list[str], payment_score: float = 80.0, isolation_score: float = 70.0) -> dict[str, pd.DataFrame]:
    return {
        "payment": pd.DataFrame({
            "work_id": work_ids,
            "payment_status": ["EVALUABLE"] * len(work_ids),
            "payment_risk_score": [payment_score] * len(work_ids),
            "payment_anomaly_status": ["ANOMALY"] * len(work_ids),
            "payment_signal_count": [1] * len(work_ids),
            "payment_high_signal_count": [1] * len(work_ids),
            "payment_reasons": [json.dumps(["Upstream payment reason."]) for _ in work_ids],
            "payment_evidence": [json.dumps({"signals": ["payment"]}) for _ in work_ids],
        }),
        "isolation_forest": pd.DataFrame({
            "work_id": work_ids,
            "isolation_forest_risk_score": [isolation_score] * len(work_ids),
            "isolation_forest_status": ["ANOMALY"] * len(work_ids),
            "isolation_forest_raw_score": [-0.1] * len(work_ids),
            "isolation_forest_percentile": [2.0] * len(work_ids),
            "isolation_forest_reasons": [json.dumps(["Upstream Isolation Forest reason."]) for _ in work_ids],
            "isolation_forest_evidence": [json.dumps({"selected_features": ["sanction_amount"]}) for _ in work_ids],
        }),
    }


def main() -> int:
    checks: list[tuple[bool, str]] = []
    base = make_inputs(["W1", "W2"])
    optional = producer_outputs(["W1", "W2"])
    original = {key: value.copy(deep=True) for key, value in optional.items()}
    fused = {**base, **optional}
    validate_inputs(fused)
    output = build_output(fused)
    row = row_for(output, "W1")
    checks += [
        (row["payment_contribution"] == round(0.8 * PAYMENT_CAP, 2), "Payment score contributes through its configured cap"),
        (row["isolation_forest_contribution"] == round(0.7 * ISOLATION_FOREST_CAP, 2), "Isolation Forest score contributes through its configured cap"),
        ("Upstream payment reason." in row["risk_reasons"], "Payment reasons are preserved"),
        ("Upstream Isolation Forest reason." in row["risk_reasons"], "Isolation Forest reasons are preserved"),
        (output["risk_score"].between(0, 100).all(), "Fused scores remain bounded"),
        (all(value <= cap for value, cap in zip(row[[f"{name}_contribution" for name in RISK_COMPONENT_CAPS]], RISK_COMPONENT_CAPS.values())), "Every component respects its cap"),
        (all(optional[key].equals(original[key]) for key in optional), "Producer input frames remain unchanged"),
    ]

    all_components = make_inputs(
        ["W1", "W2", "W3"],
        compliance_findings=[
            _compliance_finding("W1", "C08", "FINANCIAL", "FLAG", "HIGH", "Compliance evidence"),
            _compliance_finding("W1", "DQ01", "DATA_QUALITY", "FLAG", "WARNING", "Data quality evidence"),
        ],
        financial_rows=[_anomaly_row("W1", "total_expenditure", "FINANCIAL", "ANOMALY", 500000.0, 6.0)],
        timeline_rows=[_anomaly_row("W1", "sanction_to_completion_days", "TIMELINE", "ANOMALY", 900.0, 6.0)],
        phase5_evaluated={"W1": (1, 1)},
        duplicate_matches=[_match_row("W1", "W2", "SIMILAR_MATCH", 0.92, 2, 2)],
        duplicate_statuses={"W1": (0, 1, 0.92, "SIMILAR_WORK_CANDIDATE"), "W2": (0, 1, 0.92, "SIMILAR_WORK_CANDIDATE")},
    )
    all_components.update({key: value.iloc[[0]].copy() for key, value in optional.items()})
    all_row = row_for(build_output(all_components), "W1")
    checks.append((all(all_row[f"{name}_contribution"] > 0 for name in RISK_COMPONENT_CAPS), "All available components are represented in one fused result"))

    unavailable_base = make_inputs(
        ["W1", "W2"],
        compliance_not_evaluable={"W1", "W2"},
        duplicate_statuses={"W1": (0, 0, None, "NOT_EVALUABLE"), "W2": (0, 0, None, "NOT_EVALUABLE")},
    )
    unavailable = {**unavailable_base, **{key: value.iloc[0:0].copy() for key, value in optional.items()}}
    unavailable_row = row_for(build_output(unavailable), "W1")
    checks += [
        (unavailable_row["payment_contribution"] == 0 and unavailable_row["isolation_forest_contribution"] == 0, "Unavailable AI inputs contribute zero"),
        (unavailable_row["evidence_status"] == "INSUFFICIENT" and unavailable_row["risk_level"] == "UNASSESSED", "All unavailable evidence is explicitly non-evaluable"),
    ]

    tied = make_inputs(
        ["W1", "W2", "W3"],
        duplicate_matches=[
            _match_row("W1", "W3", "SIMILAR_MATCH", 0.95, 2, 2),
            _match_row("W1", "W2", "SIMILAR_MATCH", 0.95, 2, 2),
        ],
        duplicate_statuses={"W1": (0, 2, 0.95, "SIMILAR_WORK_CANDIDATE"), "W2": (0, 1, 0.95, "SIMILAR_WORK_CANDIDATE"), "W3": (0, 1, 0.95, "SIMILAR_WORK_CANDIDATE")},
    )
    tied_row = row_for(build_output(tied), "W1")
    tied_reordered = {key: value.iloc[::-1].reset_index(drop=True) for key, value in tied.items()}
    checks.append(("W2" in tied_row["risk_reasons"] and build_output(tied).equals(build_output(tied_reordered)), "Tied duplicate candidates use stable Work ID ordering"))
    partial = {**base, "payment": optional["payment"].iloc[[0]].copy(), "isolation_forest": optional["isolation_forest"].iloc[0:0].copy()}
    checks.append((row_for(build_output(partial), "W2")["payment_contribution"] == 0, "A missing project row is not treated as zero-risk evidence"))

    exact_and_similar = make_inputs(
        ["W1", "W2", "W3"],
        duplicate_matches=[
            _match_row("W1", "W2", "EXACT_MATCH", 1.0, 2, 2),
            _match_row("W1", "W3", "SIMILAR_MATCH", 0.99, 1, 1),
        ],
        duplicate_statuses={"W1": (1, 1, 1.0, "EXACT_MATCH_CANDIDATE"), "W2": (1, 0, 1.0, "EXACT_MATCH_CANDIDATE"), "W3": (0, 1, 0.99, "SIMILAR_WORK_CANDIDATE")},
    )
    exact_row = row_for(build_output(exact_and_similar), "W1")
    checks += [
        ("W2" in exact_row["risk_reasons"] and "W3" not in exact_row["risk_reasons"], "Exact duplicate evidence suppresses unrelated similar explanation"),
        (build_output(exact_and_similar).equals(build_output({key: value.sample(frac=1, random_state=4).reset_index(drop=True) for key, value in exact_and_similar.items()})), "Reordering inputs preserves output"),
    ]

    invalid = {**fused, "payment": optional["payment"].copy()}
    invalid["payment"].loc[0, "payment_risk_score"] = float("inf")
    try:
        validate_inputs(invalid)
        rejected = False
    except ValueError:
        rejected = True
    checks.append((rejected, "Invalid upstream numeric scores fail clearly"))

    missing = {**fused, "payment": optional["payment"].drop(columns=["payment_evidence"])}
    try:
        validate_inputs(missing)
        rejected = False
    except ValueError:
        rejected = True
    checks.append((rejected, "Missing producer columns fail clearly"))

    for passed, label in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    passed = all(value for value, _ in checks)
    print(f"RISK FUSION COMPLETION: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


def run_real_data_harness() -> bool:
    root = Path(__file__).parent
    features_path = root / "data" / "processed" / "ml_features.csv"
    before = hashlib.sha256(features_path.read_bytes()).hexdigest()
    features = pd.read_csv(features_path)
    split = max(20, int(len(features) * 0.8))
    history, scored_rows = features.iloc[:split].copy(deep=True), features.iloc[split:].copy(deep=True)
    payment = score_payment_data(fit_payment_model(history), scored_rows)
    isolation = score_isolation_forest_data(fit_isolation_forest_model(history), scored_rows)
    inputs = load_inputs(root / "data" / "processed")
    inputs["payment"] = payment
    inputs["isolation_forest"] = isolation
    validate_inputs(inputs)
    output = build_output(inputs)
    after = hashlib.sha256(features_path.read_bytes()).hexdigest()
    scored_ids = set(scored_rows["work_id"].astype(str))
    output_ids = set(output["work_id"].astype(str))
    represented = output.loc[output["work_id"].isin(scored_ids), ["payment_contribution", "isolation_forest_contribution"]].gt(0).any().all()
    passed = before == after and scored_ids.issubset(output_ids) and output["risk_score"].between(0, 100).all() and represented
    print(f"REAL-DATA RISK FUSION: {'PASS' if passed else 'FAIL'} ({len(output):,} projects, {len(scored_rows):,} AI-scored rows)")
    return passed


if __name__ == "__main__":
    raise SystemExit(0 if main() == 0 and run_real_data_harness() else 1)