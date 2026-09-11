# 🛡️ MPLADS AI Shield

### AI-powered anomaly, compliance & risk intelligence for MPLADS project monitoring.

> Turning fragmented project records into **explainable evidence, risk scores, and investigation priorities.**

---

## 🚨 The Problem

MPLADS projects generate large volumes of data across **recommendation, sanction, completion and expenditure** stages.

These records can be fragmented, inconsistent, incomplete, and difficult to compare manually.

**MPLADS AI Shield brings them together to answer:**

- 🔎 Which projects behave unusually compared with similar projects?
- ⚠️ Which projects have compliance or lifecycle inconsistencies?
- 🔁 Which projects show suspicious similarity patterns?
- 📊 Which projects deserve attention first?
- 🧠 **Why** was a project flagged?

---

## 🧠 How AI Shield Works

```text
                    Raw MPLADS Data
                           │
                           ▼
                  Data Preprocessing
                           │
                           ▼
                 Canonical Project Model
                           │
                           ▼
                  Feature Engineering
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
        Compliance      Anomaly       Duplicate
          Engine        Detection      Analysis
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                      Risk Fusion
                           │
                           ▼
                  Explainable Risk Score
                           │
                           ▼
                   Investigation Queue
```

## 🔬 AI / ML

### Compliance
Deterministic lifecycle & financial rules.

### Anomaly Detection
Peer-relative statistical anomaly detection using
Median/MAD, modified z-score and IQR.

### Duplicate Detection
Similarity + evidence-based duplicate analysis.

### Risk Fusion
Weighted evidence from:
Compliance 35 | Financial 25 | Timeline 15 |
Duplicate 15 | Data Quality 10

## 📊 Current Results

43,863 projects analyzed

LOW       42,196
MEDIUM     1,662
HIGH           5
CRITICAL       0

## 🏗️ Tech Stack

Frontend: React + Vite + Tailwind
Backend: FastAPI + Python
Database: PostgreSQL
ML/Data: Pandas, NumPy, Scikit-learn

## 📁 Project Structure
```text
backend/
├── app/
├── ml/
│   ├── preprocessing.py
│   ├── canonical.py
│   ├── features.py
│   ├── compliance/
│   ├── anomalies/
│   ├── duplicates/
│   ├── risk.py
│   └── risk_config.py
└── data/
frontend/
└── src/
```
## 🚦 Project Status
```
✅ Phase 1 — Preprocessing
✅ Phase 2 — Canonicalization
✅ Phase 3 — Feature Engineering
✅ Phase 4 — Compliance
✅ Phase 5 — Anomaly Detection
✅ Phase 6 — Duplicate Detection
✅ Phase 7 — Risk Fusion
🔄 Phase 8 — Evaluation
🔜 API + Dashboard Integration
```
## ⚠️ Important

AI Shield identifies unusual patterns and projects
requiring review. It does not claim or prove fraud.

## 🚀 Vision

Upload MPLADS data → Analyze → Explain → Prioritize
→ Investigate
