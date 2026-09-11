"""Phase 7 configuration: evidence weights, caps, and thresholds.

Every tunable number the Risk Fusion Engine (``ml/risk.py``) uses lives here,
centralized, so scoring behaviour can be audited or adjusted without touching
fusion logic. Nothing here is a fraud probability -- these are attention /
review-priority weights over independent evidence categories produced by
Phases 4-6.

==============================================================================
WHY THESE DEFAULTS (evidence-category caps, sum to 100)
==============================================================================
The five caps below were chosen, after inspecting the actual Phase 4-6
outputs on the full dataset (43,863 canonical projects), in this priority
order:

1. COMPLIANCE (cap 35) is weighted highest because it is the only evidence
   category grounded in explicit, documented MPLADS rules (see
   ``RULE_METADATA`` in ``ml/compliance/rules.py``) rather than a statistical
   comparison. A rule breach (e.g. expenditure exceeding the sanctioned
   amount) is the most defensible, most explainable signal available.

2. FINANCIAL_ANOMALY (cap 25) is next because peer-relative statistical
   outliers in amounts are a strong independent corroborating signal, but
   they are not an explicit rule breach -- a project can be a financial
   outlier for legitimate reasons (e.g. an unusually large but fully
   justified public work).

3. TIMELINE_ANOMALY (cap 15) is weighted below financial anomalies because,
   on the real data, timeline deviations are far more common and far less
   discriminating: 2,984 of ~263k evaluated timeline-metric rows (~1.1%) are
   flagged ANOMALY vs. 4,334 of ~438k financial rows, but administrative
   delay is a weaker indicator of irregularity than an unusual amount.

4. DUPLICATE (cap 15) is capped at the same level as timeline anomalies
   deliberately. Inspecting the actual Phase 6 output showed that the
   overwhelming majority of EXACT_MATCH pairs (116,479 of 121,273 pairs) are
   generic, highly-repeated boilerplate descriptions (median
   ``description_frequency`` of 151, i.e. the same short phrase such as
   "Construction of road" appears against unrelated projects all over the
   dataset) -- not evidence of one work being duplicated. A rarity-weighting
   step (below) already discounts this, but the category cap is kept modest
   as a second safeguard against a single noisy detector dominating the
   score (see Section 27 "dominance check" in the Phase 7 brief).

5. DATA_QUALITY (cap 10) is deliberately the smallest cap. Source/field
   conflicts (rule DQ01) describe data-collection inconsistency, not
   suspicious project behaviour, and must never be allowed to compete with
   real anomaly/compliance evidence for the top of the score.

These are defaults, not laws of nature -- they are declared as named
constants below specifically so they can be revisited if
``risk_quality_report.json``'s dominance/distribution sections show an
unintended concentration.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. Evidence-category caps (points out of 100). Must sum to <= 100.
# ---------------------------------------------------------------------------
COMPLIANCE_CAP = 35.0
FINANCIAL_ANOMALY_CAP = 25.0
TIMELINE_ANOMALY_CAP = 15.0
DUPLICATE_CAP = 15.0
DATA_QUALITY_CAP = 10.0

TOTAL_CAP = COMPLIANCE_CAP + FINANCIAL_ANOMALY_CAP + TIMELINE_ANOMALY_CAP + DUPLICATE_CAP + DATA_QUALITY_CAP
assert TOTAL_CAP <= 100.0, "Evidence-category caps must not exceed the 0-100 score range"

# ---------------------------------------------------------------------------
# 2. Compliance (Phase 4) point values.
#
# Only findings with status == FLAG and category != "DATA_QUALITY" count
# toward compliance_contribution; DATA_QUALITY findings (DQ01) are scored
# separately under data_quality_contribution so the two categories never
# double count the same underlying evidence (see rules.py: DQ01 already
# excluded from Phase 4's own compliance_status calculation).
# ---------------------------------------------------------------------------
COMPLIANCE_SEVERITY_POINTS = {
    "HIGH": 10.0,
    "WARNING": 4.0,
}
DATA_QUALITY_RULE_POINTS = 10.0  # DQ01 is binary: flagged or not.

# Compliance rule IDs that inspect the *same underlying condition* as a
# Phase 5 anomaly metric. Used only for overlap handling (Section 8), never
# to change the compliance_contribution itself.
#   C08 "Expenditure exceeds sanction" / C09 "Disbursement exceeds sanction"
#   overlap with the FINANCIAL anomaly metrics that measure the same
#   expenditure/disbursement-vs-sanction relationship on a peer-relative
#   basis (e.g. expenditure_to_sanction_ratio, disbursed_to_sanction_ratio,
#   total_expenditure, amount_disbursed).
FINANCIAL_OVERLAP_RULE_IDS = frozenset({"C08", "C09"})
#   C01 "Recommendation to sanction timeline" / C02 "Sanction to completion
#   timeline" overlap with the TIMELINE anomaly metrics that measure the
#   same durations on a peer-relative basis.
TIMELINE_OVERLAP_RULE_IDS = frozenset({"C01", "C02"})

# ---------------------------------------------------------------------------
# 3. Anomaly (Phase 5) severity buckets and point values.
#
# Phase 5 does not emit a HIGH/MEDIUM/LOW severity field -- only a status
# (NORMAL/ANOMALY/NOT_EVALUABLE), a modified_z_score, and a decision_method.
# Risk Fusion derives a review-priority bucket from the magnitude of the
# modified z-score (the same statistic Phase 5 already thresholds ANOMALY
# at 3.5 for). This is an interpretive bucket for weighting purposes only --
# it is not a new anomaly detector and does not change Phase 5's own
# ANOMALY/NORMAL decision.
# ---------------------------------------------------------------------------
ANOMALY_Z_HIGH = 7.0     # |z| >= 7.0
ANOMALY_Z_MEDIUM = 5.0   # 5.0 <= |z| < 7.0
# 3.5 <= |z| < 5.0 is LOW (3.5 is Phase 5's own ANOMALY threshold).
ANOMALY_POINTS = {"HIGH": 8.0, "MEDIUM": 5.0, "LOW": 3.0}
# ~11% of real ANOMALY rows (609 of 7,318) use the IQR fallback (no z-score
# is defined when the peer group's MAD is zero). These are still genuine
# 1.5xIQR outliers, so they are scored as a flat MEDIUM rather than dropped.
IQR_FALLBACK_POINTS = ANOMALY_POINTS["MEDIUM"]
IQR_FALLBACK_BUCKET = "MEDIUM"

# Overlap discount applied to an anomaly category's raw contribution when the
# overlapping compliance rule(s) for that same family already fired (see
# Section 8 "avoid double counting" and FINANCIAL_OVERLAP_RULE_IDS /
# TIMELINE_OVERLAP_RULE_IDS above). The compliance rule is treated as the
# PRIMARY signal (an explicit, deterministic threshold breach); the anomaly
# detector's contribution is treated as SECONDARY/corroborating evidence for
# the same underlying condition and is halved rather than dropped, because
# the *degree* of statistical extremity is still additional information a
# reviewer benefits from (e.g. "not just over budget, but a 40-sigma
# outlier").
ANOMALY_OVERLAP_DISCOUNT = 0.5

# ---------------------------------------------------------------------------
# 4. Duplicate / similar-work (Phase 6) weighting.
#
# Inspecting the real Phase 6 output showed that raw EXACT_MATCH/
# SIMILAR_MATCH counts are dominated by generic, highly-repeated boilerplate
# descriptions (see module docstring above). description_frequency (how many
# other USABLE descriptions in the whole dataset normalize to the same text)
# is therefore used as a rarity weight: a match on a nearly-unique
# description is much stronger evidence than a match on a phrase repeated
# hundreds of times.
# ---------------------------------------------------------------------------
DUPLICATE_SIMILARITY_THRESHOLD = 0.85  # Must match ml/duplicates/engine.py.
DUPLICATE_RARITY_BANDS = (
    # (max_frequency_inclusive, weight)
    (3, 1.0),
    (10, 0.7),
    (30, 0.4),
    (float("inf"), 0.15),
)

# ---------------------------------------------------------------------------
# 5. Risk levels. Defaults from the Phase 7 brief; re-validated against the
# actual score distribution in risk_quality_report.json after scoring the
# full dataset (see the Phase 7 final report for the observed distribution
# and the rationale for keeping these defaults rather than moving them).
# ---------------------------------------------------------------------------
RISK_LEVEL_THRESHOLDS = (
    (25.0, "LOW"),        # score < 25
    (50.0, "MEDIUM"),     # 25 <= score < 50
    (75.0, "HIGH"),       # 50 <= score < 75
    (float("inf"), "CRITICAL"),  # score >= 75
)

# ---------------------------------------------------------------------------
# 6. Evidence status. A project's four evidence domains are: compliance,
# financial anomaly, timeline anomaly, duplicate/similarity. A domain is
# "evaluable" for a project when Phases 4-6 could actually evaluate at least
# one signal in that domain for it (not when the project happens to look
# clean). Evidence status is about *data availability*, never about the
# risk_score itself -- a LOW score with INSUFFICIENT evidence must never
# read the same as a LOW score with SUFFICIENT evidence (Section 11).
# ---------------------------------------------------------------------------
EVIDENCE_STATUS_THRESHOLDS = (
    (0, "INSUFFICIENT"),  # 0 of 4 domains evaluable
    (2, "LIMITED"),       # 1-2 of 4 domains evaluable
    (4, "SUFFICIENT"),    # 3-4 of 4 domains evaluable
)


def risk_level_for(score: float) -> str:
    for upper_bound, level in RISK_LEVEL_THRESHOLDS:
        if score < upper_bound:
            return level
    return RISK_LEVEL_THRESHOLDS[-1][1]


def evidence_status_for(evaluable_domain_count: int) -> str:
    for upper_bound, status in EVIDENCE_STATUS_THRESHOLDS:
        if evaluable_domain_count <= upper_bound:
            return status
    return EVIDENCE_STATUS_THRESHOLDS[-1][1]


def anomaly_severity_bucket(modified_z_score: float | None, decision_method: str) -> str:
    """Map a Phase 5 anomaly row to a HIGH/MEDIUM/LOW review-priority bucket."""
    if decision_method == "iqr_fallback" or modified_z_score is None:
        return IQR_FALLBACK_BUCKET
    magnitude = abs(modified_z_score)
    if magnitude >= ANOMALY_Z_HIGH:
        return "HIGH"
    if magnitude >= ANOMALY_Z_MEDIUM:
        return "MEDIUM"
    return "LOW"


def anomaly_points(modified_z_score: float | None, decision_method: str) -> float:
    if decision_method == "iqr_fallback" or modified_z_score is None:
        return IQR_FALLBACK_POINTS
    return ANOMALY_POINTS[anomaly_severity_bucket(modified_z_score, decision_method)]


def duplicate_rarity_weight(description_frequency: float | None) -> float:
    """Lower weight for matches on common/boilerplate descriptions."""
    if description_frequency is None:
        return DUPLICATE_RARITY_BANDS[0][1]
    for max_frequency, weight in DUPLICATE_RARITY_BANDS:
        if description_frequency <= max_frequency:
            return weight
    return DUPLICATE_RARITY_BANDS[-1][1]