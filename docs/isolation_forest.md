# Isolation Forest

Phase 8 is an independent, unsupervised detector for unusual multivariate
combinations in project-level MPLADS features. It complements Compliance AI,
Phase 5 Financial/Timeline Anomaly AI, Duplicate Detection, and Payment AI;
those components answer different questions and their outputs are not inputs
to this model.

## Feature contract

The supported registry is the audited 17-feature set:

- Financial/scale: `sanction_amount`, `recommended_amount`,
  `amount_disbursed`, `disbursed_to_sanction_ratio`,
  `sanction_vs_recommended_ratio`
- Timeline: `recommendation_to_sanction_days`, `sanction_to_completion_days`,
  `recommendation_to_completion_days`, `expenditure_span_days`
- Lifecycle: `n_lifecycle_stages_present`, `has_recommended_record`,
  `has_sanctioned_record`, `has_completed_record`, `has_expenditure_record`
- Payment/expenditure behavior: `n_expenditure_transactions`,
  `n_distinct_vendors`, `payment_success_ratio`

`work_id`, categorical identifiers, compliance flags, duplicate/payment/
financial/risk-fusion outputs, and redundant representations are excluded.
The API dynamically selects viable registry columns present in the supplied
DataFrame. The current `ml_features.csv` is a validation fixture only; the
engine never loads it.

## Training and inference

Use `fit_isolation_forest_model(history)` with a historical DataFrame and
`score_isolation_forest_data(model, new_rows)` for unseen rows. `work_id` is
required and must be unique in each input. At least the configured minimum
number of rows and viable numeric features must be available. Missing or
malformed numeric values become missing, not zero. Features with too few valid
observations or zero variance are excluded and recorded in diagnostics.

The fitted preprocessing stores median imputation and explicit missingness
indicators for columns that had missing values in training. It is fitted once
on history and reused unchanged at inference. A row with no sufficient
observed supported features is `NOT_EVALUABLE`.

## Scores and interpretation

scikit-learn's `decision_function` is retained as
`isolation_forest_raw_score`; lower values indicate stronger isolation. The
deterministic public score is:

`100 * (training_max_raw_score - raw_score) /
(training_max_raw_score - training_min_raw_score)`, clipped to 0-100.

The default `IsolationForestConfig.anomaly_score_threshold` is 75.0:
`ANOMALY` is at or above that threshold, and lower evaluable scores are
`NORMAL`. A constant training raw-score range maps to 50.0. Thresholds,
random state, minimum sample requirements, and estimator settings are public
configuration, not hidden Work ID rules.

Every result includes the raw score, training-relative percentile, selected and
missing features, observed feature count, and a human-readable explanation.
An `ANOMALY` means only that the project feature combination is unusual relative
to the fitted snapshot. It is not a fraud label, compliance finding, duplicate
finding, or payment-rule violation.

## Limitations and Risk Fusion

The model describes the distribution represented by its training snapshot. It
does not provide historical as-of detection, transaction ordering, causality,
or proof of misconduct. Sparse rows may be `NOT_EVALUABLE`, and median
imputation can reduce the information available for highly incomplete rows.

Risk Fusion now consumes this module's public score, status, reasons, and
evidence as one independent review-priority signal. Isolation Forest itself
remains unaware of Risk Fusion and never consumes other AI scores. API,
database, and dashboard wiring is deferred to the later application
integration phase.