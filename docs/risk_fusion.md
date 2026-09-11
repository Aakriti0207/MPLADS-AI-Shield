# Risk Fusion

Risk Fusion combines already-produced evidence into a bounded review-priority
score. It does not rerun Compliance, Phase 5 anomalies, Duplicate AI, Payment
AI, or Isolation Forest detection, and it does not establish fraud.

## Inputs and caps

The final score has seven independent components. The caps are centralized in
`backend/ml/risk_config.py` and sum to exactly 100:

| Component | Maximum contribution |
| --- | ---: |
| Compliance | 28 |
| Financial anomaly | 20 |
| Timeline anomaly | 12 |
| Duplicate / similar work | 12 |
| Data quality | 8 |
| Payment AI | 10 |
| Isolation Forest | 10 |

The original Phase 4-6 ordering is retained at 80% of its former cap. Payment
AI and Isolation Forest each receive 10 points because both are independent,
already implemented detectors without a calibration contract that supports
ranking one above the other.

Payment AI is consumed through `payment_risk_score`, `payment_status`,
`payment_reasons`, and `payment_evidence`. Isolation Forest is consumed through
`isolation_forest_risk_score`, `isolation_forest_status`,
`isolation_forest_reasons`, and `isolation_forest_evidence`.

## Score semantics

An evaluable upstream score is mapped linearly to its configured cap. A
`NOT_EVALUABLE` row contributes no points and is not treated as clean evidence.
Missing components are not renormalized, so partial evidence cannot silently
inflate a score. The final score is always in `[0, 100]`.

`LOW`, `MEDIUM`, `HIGH`, and `CRITICAL` retain the configured score thresholds.
A project with no evaluable evidence is instead marked `UNASSESSED` with
`evidence_status=INSUFFICIENT`; it must not be read as confidently low risk.
Evidence status counts evaluable domains across Compliance, Financial anomaly,
Timeline anomaly, Duplicate, Payment AI, and Isolation Forest:

- 0 domains: `INSUFFICIENT`
- 1-2 domains: `LIMITED`
- 3-6 domains: `SUFFICIENT`

## Explanations and determinism

Reasons are emitted only for evidence that contributed to the score. Upstream
Payment AI and Isolation Forest reasons are retained, with their upstream JSON
evidence available in the input contract for traceability. If an exact
duplicate match is selected, a separate similar-match explanation is not
presented as scored evidence. Duplicate ties use stable Work ID ordering, so
permuting input rows does not change the selected evidence, reasons, or score.

## Validation and scope

Risk Fusion validates required columns, unique Work IDs, foreign IDs, bounded
finite scores, supported statuses, duplicate pair structure, and duplicate
summary uniqueness without mutating caller DataFrames. Payment and Isolation
Forest inputs are optional for backward compatibility with the existing
Phase 4-6 caller; when supplied, they must follow their producer output
contracts.

API, database, dashboard, frontend, persisted Payment/Isolation output wiring,
and application-level scheduling are intentionally deferred to the later
integration phase.