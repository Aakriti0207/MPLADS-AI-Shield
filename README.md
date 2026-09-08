# MPLADS Insight — Upgraded SIH Frontend

## ML pipeline status

### Phase 3 — Feature Engineering ✅
Converts `data/processed/canonical_projects.csv` into the generated,
Git-ignored `data/processed/ml_features.csv`.

The feature table contains 43,863 projects and 68 ML-ready features,
including financial, timeline, lifecycle, payment, and data-quality features.

### Phase 4 — Compliance Engine ✅
Applies deterministic MPLADS compliance rules to the Phase 3 feature table.

Outputs:
- `data/processed/compliance_findings.csv`
- `data/processed/compliance_summary.csv`

Findings use `PASS`, `FLAG`, and `NOT_EVALUABLE` statuses with explainable
rule evidence. Compliance rules are kept separate from statistical anomaly
detection and risk scoring.

### Phase 5 — Financial + Timeline Anomaly Detection ✅
Detects peer-relative statistical anomalies using robust statistics over
Phase 3 features.

The detector uses:
- state + work category → state → work category → global peer hierarchy
- leave-one-out peer baselines
- median and MAD-based modified z-scores
- IQR fallback when MAD is zero
- `log1p` transformation for strongly skewed financial amounts
- explicit `NORMAL`, `ANOMALY`, and `NOT_EVALUABLE` statuses

Outputs:
- `data/processed/financial_anomalies.csv`
- `data/processed/timeline_anomalies.csv`
- `data/processed/phase5_anomaly_summary.csv`

Phase 5 does not produce fraud labels or final risk scores. Statistical
anomalies are evidence for later risk fusion.

### Frontend
React + Vite + JavaScript + Tailwind CSS + React Router + Recharts + React Leaflet.

The current frontend uses synthetic/demo data and is intended to become the
monitoring and intelligence layer over the backend project data and ML
outputs.

## Next backend step

Connect `src/data.js` to FastAPI endpoints while keeping the existing UI
contracts. The backend will expose project data, compliance findings,
anomaly evidence, and later risk-fusion results to the frontend.