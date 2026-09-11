# Payment AI

Payment AI is a standalone, unsupervised detector for project-level payment
behavior. It uses signals already exposed by Phase 3 features: utilization
against sanction, expenditure/in-progress composition, transaction and vendor
counts, payment completion ratios, and expenditure span.

It fits robust historical baselines using medians, MAD, and an IQR fallback.
There is no reliable fraud label in the current data, so no supervised target
or fabricated label is used. `fit_payment_model(history)` and
`score_payment_data(model, new_rows)` keep fitting separate from inference and
allow unseen uploaded rows to be scored without retraining on those rows.

The input contract requires `work_id` plus the raw payment fields used by the
Phase 3 feature layer: sanction amount, expenditure and in-progress amounts,
transaction count, vendor count, successful-payment count, and in-progress
payment count. Optional derived ratio columns are not trusted; ratios are
recomputed from validated raw values. Negative values, impossible count
relationships, zero denominators, and utilization above 1 make affected
signals unavailable rather than suspicious.

The public `PaymentConfig` controls the modified-z anomaly threshold, the
higher-severity threshold, the score ceiling, and the minimum historical
sample size. Defaults are 3.5 and 5.0 for the robust-z thresholds, matching
the existing Phase 5 convention; these are policy defaults, not values tied to
specific Work IDs or test rows.

Rows without actual payment activity, without valid payment evidence, or with
only a sanction amount are `NOT_EVALUABLE` with score zero.
Negative values and zero sanctioned amounts do not become suspicious by
themselves; affected signals are treated as missing. Scores are deterministic,
bounded to 0-100, and accompanied by JSON evidence and human-readable reasons.

Baselines require at least `PaymentConfig.min_training_values` valid historical
observations per signal and at least two stable signal families overall.
Zero-variation signals are recorded as unstable and are not fitted. Signals
are grouped into utilization/expenditure, completion/progress, transaction
activity, and vendor-concentration families. At most one anomalous signal per
family contributes to the score, and each family has a configurable cap; this
prevents complementary ratios from being counted as independent evidence.

`amount_disbursed` is accepted only as an activity/evaluability indicator. It
is not an independent anomaly signal because the project-level data does not
provide enough validated payment progression detail to interpret it separately.

The default modified-z threshold is 3.5, matching the project's existing
robust anomaly convention. A 5.0 robust-z value receives the higher signal
weight. These values are configurable constants, not dataset-specific Work ID
rules. The detector scores project-level aggregate snapshots at the end of the
available reporting snapshot. It does not provide as-of or earlier-payment
behavior detection because that requires transaction-level history and an
explicit cutoff date. It cannot establish fraud or analyze transaction ordering
that is not present.