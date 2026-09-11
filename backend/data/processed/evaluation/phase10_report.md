# Phase 10 Synthetic Evaluation

This evaluates controlled anomalies through the existing Phase 3-7 pipeline. It is not real-world accuracy.

| Scenario | Expected detector | Actual detector | Expected flag | Actual flag | Risk score | Pass |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| CLEAN_CONTROL | NONE | NONE | False | False | 0.00 | True |
| FINANCIAL_ANOMALY | FINANCIAL_ANOMALY | FINANCIAL_ANOMALY+COMPLIANCE | True | True | 14.00 | True |
| TIMELINE_ANOMALY | TIMELINE_ANOMALY | TIMELINE_ANOMALY+COMPLIANCE | True | True | 10.00 | True |
| COMPLIANCE_VIOLATION | COMPLIANCE | FINANCIAL_ANOMALY+COMPLIANCE | True | True | 14.00 | True |
| DUPLICATE_SIMILARITY | DUPLICATE | DUPLICATE | True | True | 12.00 | True |
| MULTI_EVIDENCE | RISK_FUSION | FINANCIAL_ANOMALY+TIMELINE_ANOMALY+COMPLIANCE | True | True | 24.00 | True |
| MISSING_DATA | MISSING_DATA | NONE | False | False | 0.00 | True |
| ZERO_VALUE | ZERO_VALUE | FINANCIAL_ANOMALY | False | True | 20.00 | True |
| INVALID_DATE_ORDER | COMPLIANCE | COMPLIANCE | True | True | 10.00 | True |
| RISK_EXPLANATION | RISK_FUSION | FINANCIAL_ANOMALY+COMPLIANCE | True | True | 14.00 | True |
| PAYMENT_ANOMALY | PAYMENT_AI | PAYMENT_AI | True | True | 3.60 | True |
| ISOLATION_FOREST | ISOLATION_FOREST | FINANCIAL_ANOMALY+COMPLIANCE+ISOLATION_FOREST | True | True | 34.00 | True |


Final status: **PASS**
