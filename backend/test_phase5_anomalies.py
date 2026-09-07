"""Synthetic validation for Phase 5 financial and timeline anomalies."""

from __future__ import annotations

import json
import tempfile

import numpy as np
import pandas as pd

from ml.anomalies.engine import (
    ANOMALY_COLUMNS,
    SUMMARY_COLUMNS,
    build_phase5_outputs,
    build_phase5_summary,
    write_phase5_outputs,
)
from ml.anomalies.statistics import (
    PeerBaseline,
    build_peer_index,
    choose_peer_indices,
    choose_peer_level,
    evaluate_value,
)


FINANCIAL = [
    "recommended_amount", "sanction_amount", "amount_disbursed", "total_expenditure",
    "total_amount_in_progress", "sanction_vs_recommended_ratio", "sanction_minus_recommended_amount",
    "disbursed_to_sanction_ratio", "expenditure_to_sanction_ratio", "in_progress_amount_to_sanction_ratio",
]
TIMELINE = [
    "recommendation_to_sanction_days", "sanction_to_completion_days",
    "recommendation_to_completion_days", "recommendation_to_first_expenditure_days",
    "sanction_to_first_expenditure_days", "expenditure_span_days",
]


def make_features() -> pd.DataFrame:
    rows = []
    for index in range(25):
        row = {
            "work_id": f"WS/MP1/2024-2025/{index + 1}", "state": "State A", "work_category": "Road",
            "recommended_amount": 100000.0 + index * 1000, "sanction_amount": 100000.0 + index * 1000,
            "amount_disbursed": 80000.0 + index * 800, "total_expenditure": 70000.0 + index * 700,
            "total_amount_in_progress": 5000.0 + index * 50, "sanction_vs_recommended_ratio": 1.0,
            "sanction_minus_recommended_amount": 0.0, "disbursed_to_sanction_ratio": 0.8,
            "expenditure_to_sanction_ratio": 0.7, "in_progress_amount_to_sanction_ratio": 0.05,
            "recommendation_to_sanction_days": 20.0 + index % 3, "sanction_to_completion_days": 100.0 + index % 3,
            "recommendation_to_completion_days": 120.0 + index % 3,
            "recommendation_to_first_expenditure_days": 30.0 + index % 3,
            "sanction_to_first_expenditure_days": 10.0 + index % 3, "expenditure_span_days": 60.0 + index % 3,
        }
        rows.append(row)
    rows[-1]["total_expenditure"] = 10_000_000.0
    rows[-1]["sanction_to_completion_days"] = 2000.0
    rows[-1]["recommendation_to_sanction_days"] = -5.0
    rows[-1]["sanction_amount"] = np.nan
    rows[-1]["disbursed_to_sanction_ratio"] = np.nan
    rows[-1]["state"] = np.nan
    rows[-1]["work_category"] = np.nan
    return pd.DataFrame(rows)


def main() -> int:
    features = make_features()
    original = features.copy(deep=True)
    anomalies, summary = build_phase5_outputs(features)
    repeated_anomalies, repeated_summary = build_phase5_outputs(features)
    last_id = features.iloc[-1].work_id
    last_timeline = anomalies[(anomalies.work_id == last_id) & (anomalies.metric_name == "recommendation_to_sanction_days")].iloc[0]
    last_missing = anomalies[(anomalies.work_id == last_id) & (anomalies.metric_name == "sanction_amount")].iloc[0]
    last_high = anomalies[(anomalies.work_id == last_id) & (anomalies.metric_name == "total_expenditure")].iloc[0]

    zero_mad_normal = evaluate_value(10.0, PeerBaseline("global", "GLOBAL", 20, 10.0, 0.0, 10.0, 10.0, "none"))
    zero_mad_iqr = evaluate_value(20.0, PeerBaseline("global", "GLOBAL", 20, 10.0, 0.0, 1.0, 2.0, "none"))
    zero_mad_unevaluable = evaluate_value(20.0, PeerBaseline("global", "GLOBAL", 20, 10.0, 0.0, 10.0, 10.0, "none"))
    threshold_value = 10.0 + (3.5 * 2.0 / 0.6745)
    exact_threshold = evaluate_value(threshold_value, PeerBaseline("global", "GLOBAL", 20, 10.0, 2.0, 8.0, 12.0, "none"))
    low_anomaly = evaluate_value(0.0, PeerBaseline("global", "GLOBAL", 20, 10.0, 1.0, 8.0, 12.0, "none"))

    loo_frame = pd.DataFrame({
        "state": ["State A"] * 21, "work_category": ["Road"] * 21,
        "metric": list(range(1, 21)) + [100000.0],
    })
    loo_mask = loo_frame["metric"].notna().to_numpy()
    loo_level, loo_key, loo_peers = choose_peer_level(20, loo_frame, loo_mask)
    loo_values = loo_frame.loc[loo_peers, "metric"].to_numpy(dtype=float)
    loo_median = float(np.median(loo_values))
    loo_baseline = PeerBaseline(
        loo_level, loo_key, int(loo_peers.sum()),
        loo_median,
        float(np.median(np.abs(loo_values - loo_median))),
        float(np.percentile(loo_values, 25)),
        float(np.percentile(loo_values, 75)), "none",
    )

    def hierarchy_frame(state_values, category_values):
        return pd.DataFrame({"state": state_values, "work_category": category_values})

    state_category_fallback = hierarchy_frame(["A"] * 10 + ["A"] * 15 + ["B"] * 20, ["Road"] * 10 + ["Bridge"] * 15 + ["Road"] * 20)
    state_fallback = hierarchy_frame(["A"] * 10 + ["A"] * 15 + ["B"] * 20, ["Road"] * 10 + ["Bridge"] * 15 + ["Road"] * 20)
    category_fallback = hierarchy_frame(["A"] * 10 + ["B"] * 15 + ["C"] * 20, ["Road"] * 10 + ["Road"] * 15 + ["Bridge"] * 20)
    global_fallback = hierarchy_frame(["A"] * 10 + ["B"] * 11, ["Road"] * 10 + ["Bridge"] * 11)
    missing_grouping = hierarchy_frame([np.nan] * 21, [np.nan] * 21)
    valid_state_category = np.ones(len(state_category_fallback), dtype=bool)
    valid_category = np.ones(len(category_fallback), dtype=bool)
    valid_global = np.ones(len(global_fallback), dtype=bool)
    valid_missing = np.ones(len(missing_grouping), dtype=bool)
    hierarchy_checks = [
        (choose_peer_level(0, state_category_fallback, valid_state_category)[:2] == ("state", "A"), "state+category falls back to state"),
        (choose_peer_level(0, state_fallback, valid_state_category)[:2] == ("state", "A"), "state fallback is selected when available"),
        (choose_peer_level(0, category_fallback, valid_category)[:2] == ("work_category", "Road"), "state falls back to work_category"),
        (choose_peer_level(0, global_fallback, valid_global)[:2] == ("global", "GLOBAL"), "all grouped levels fall back to global"),
        (choose_peer_level(0, missing_grouping, valid_missing)[:2] == ("global", "GLOBAL"), "missing grouping fields fall back to global"),
    ]

    performance_frame = pd.DataFrame({
        "state": np.repeat(["A", "B", "C", "D"], 1250),
        "work_category": np.tile(np.repeat(["Road", "Bridge"], 625), 4),
    })
    performance_index = build_peer_index(performance_frame, np.ones(len(performance_frame), dtype=bool))
    del performance_frame
    cached_selections = [choose_peer_indices(index, performance_index) for index in range(5000)]

    summary_rows = pd.DataFrame({
        "work_id": np.repeat([f"work-{index}" for index in range(5000)], 16),
        "domain": np.tile(["FINANCIAL"] * 10 + ["TIMELINE"] * 6, 5000),
        "status": np.tile(["NORMAL"] * 9 + ["ANOMALY"] + ["NOT_EVALUABLE"] * 6, 5000),
    })
    summary_input = summary_rows.copy(deep=True)
    performance_summary = build_phase5_summary(summary_rows)
    expected_performance_summary = {
        "financial_metrics_evaluated": 10,
        "financial_anomaly_count": 1,
        "timeline_metrics_evaluated": 0,
        "timeline_anomaly_count": 0,
        "total_anomaly_count": 1,
        "financial_not_evaluable_count": 0,
        "timeline_not_evaluable_count": 6,
        "phase5_status": "ANOMALY_FOUND",
    }
    first_performance_summary = performance_summary.iloc[0]

    checks = [
        (last_timeline.status == "NOT_EVALUABLE" and last_timeline.decision_method == "not_evaluable", "negative timeline is not evaluable"),
        (last_missing.status == "NOT_EVALUABLE", "missing financial value is not evaluable"),
        (last_high.status == "ANOMALY" and last_high.direction == "HIGH", "extreme expenditure is anomalous"),
        (last_high.peer_group_level == "global" and last_high.peer_group_size == 24, "missing grouping fields use global peers"),
        (loo_level == "state_work_category" and loo_baseline.size == 20 and loo_baseline.median == 10.5 and 100000.0 not in loo_frame.loc[loo_peers, "metric"].tolist(), "leave-one-out baseline excludes evaluated value"),
        (all(passed for passed, _ in hierarchy_checks), "peer hierarchy fallback order is deterministic"),
        (len(cached_selections) == 5000 and all(len(peers) >= 20 for _, _, peers in cached_selections), "cached peer selection avoids per-row dataframe scans"),
        (len(performance_summary) == 5000 and list(performance_summary.columns) == SUMMARY_COLUMNS, "vectorized summary handles 5,000 work IDs"),
        (all(first_performance_summary[column] == value for column, value in expected_performance_summary.items()), "vectorized summary preserves aggregate semantics"),
        (summary_rows.equals(summary_input), "summary generation does not mutate anomaly rows"),
        (zero_mad_normal["status"] == "NORMAL" and zero_mad_normal["decision_method"] == "modified_z_score", "MAD zero equal median is normal"),
        (zero_mad_iqr["status"] == "ANOMALY" and zero_mad_iqr["decision_method"] == "iqr_fallback", "MAD zero uses explicit IQR fallback"),
        (zero_mad_unevaluable["status"] == "NOT_EVALUABLE" and zero_mad_unevaluable["decision_method"] == "not_evaluable", "MAD zero without IQR is not evaluable"),
        (abs(exact_threshold["modified_z_score"] - 3.5) < 1e-12 and exact_threshold["status"] == "ANOMALY", "exact modified-z threshold is anomalous"),
        (low_anomaly["status"] == "ANOMALY" and low_anomaly["direction"] == "LOW", "LOW anomaly is detected"),
        (last_missing.status == "NOT_EVALUABLE" and last_missing.metric_name == "sanction_amount", "missing amount is not evaluable"),
        (anomalies[(anomalies.work_id == last_id) & (anomalies.metric_name == "disbursed_to_sanction_ratio")].iloc[0].status == "NOT_EVALUABLE", "NaN ratio is not evaluable"),
        ("recorded_payment_amount_to_sanction_ratio" not in set(anomalies.metric_name), "payment-specific metric excluded"),
        (list(anomalies.columns) == ANOMALY_COLUMNS, "anomaly schema is exact"),
        (list(summary.columns) == SUMMARY_COLUMNS, "summary schema is exact"),
        (features.equals(original), "input is not mutated"),
        (summary.work_id.is_unique and summary.work_id.tolist() == features.work_id.tolist(), "work IDs remain aligned"),
        (anomalies.equals(repeated_anomalies) and summary.equals(repeated_summary), "repeated execution is identical"),
        (all(json.loads(value) is not None for value in anomalies.evidence_json), "evidence is valid JSON"),
        (all(value in {"modified_z_score", "iqr_fallback", "not_evaluable"} for value in anomalies.decision_method), "decision methods are explicit"),
        (not np.isinf(pd.to_numeric(anomalies.select_dtypes(exclude="object").stack(), errors="coerce").dropna()).any(), "outputs contain no infinities"),
        (json.loads(last_high.evidence_json).get("transformation") in {"none", "log1p"}, "financial transformation is recorded"),
    ]
    with tempfile.TemporaryDirectory() as directory:
        paths = write_phase5_outputs(anomalies, summary, directory)
        checks.append((all(path.exists() for path in paths), "all output files are written"))
    for passed, label in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    passed = all(passed for passed, _ in checks)
    print(f"PHASE 5: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())