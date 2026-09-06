# MPLADS Insight — Upgraded SIH Frontend

## ML pipeline status

Phase 3 converts `mplads-backend/data/processed/canonical_projects.csv` into
the generated, Git-ignored `data/processed/ml_features.csv`. Run it from the
backend directory with `python -m ml.features` after Phase 2 has produced the
canonical CSV.

The feature table retains `work_id`, typed source amount/payment/lifecycle
measurements, raw categorical context, and deterministic codes only for the
bounded-cardinality fields `houses`, `state`, `elected_nominated`,
`work_category`, `work_status`, and `stages_present`. MP, constituency, and
implementing agency remain raw rather than one-hot encoded; work description
is intentionally excluded for the later duplicate-text phase.

Financial features: `sanction_vs_recommended_ratio`,
`sanction_minus_recommended_amount`, `disbursed_to_sanction_ratio`,
`expenditure_to_sanction_ratio`, `in_progress_amount_to_sanction_ratio`, and
`recorded_payment_amount_to_sanction_ratio`. Payment features:
`payment_success_ratio`, `payment_in_progress_ratio`, `transactions_per_vendor`,
`average_successful_payment_amount`, and `average_in_progress_payment_amount`.
Timeline features are the recommendation/sanction/completion/expenditure day
intervals and `expenditure_span_days`; lifecycle coverage is
`n_lifecycle_stages_present / 4`.

All ratios are missing when either required value is missing or the denominator
is zero. Durations are missing when either date is missing; valid negative
durations are retained. Date-availability indicators preserve missingness.
Phase 2 lifecycle and data-quality flags are carried forward unchanged as
audit metadata, not risk decisions. No risk labels, scores, thresholds, or
data from `project_risk_scores.csv` are used or generated in Phase 3.

React + Vite + JavaScript + Tailwind CSS + React Router + Recharts + React Leaflet.

## Run
```bash
npm install
npm run dev
```
Open http://localhost:5173/

## Routes
/, /login, /dashboard, /projects, /projects/:id, /alerts, /analytics, /map, /reports

## Important
All data is synthetic/demo data. The UI is designed as an intelligence/monitoring layer over official project information, not as an official government portal or a copy of one.

## Next backend step
Replace `src/data.js` with API calls to Spring Boot endpoints, keeping the same UI contracts.
