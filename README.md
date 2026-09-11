# 🛡️ MPLADS AI Shield

### AI-powered anomaly, compliance & risk intelligence for MPLADS project monitoring.

> Turning fragmented records into **explainable evidence, risk scores, and investigation priorities.**

---

## 🚨 The Problem

MPLADS data is spread across recommendation, sanction, completion, payment and expenditure records, making manual monitoring difficult.

**AI Shield helps identify:**

- 🔎 Unusual project behaviour
- ⚠️ Compliance inconsistencies
- 💳 Unusual payment patterns
- 🔁 Similar or duplicate projects
- 📊 Projects requiring attention
- 🧠 **Why** a project was flagged

---

## 🧠 How It Works

    Raw Data
        ↓
    Preprocessing
        ↓
    Canonical Projects
        ↓
    Feature Engineering
        ↓
    ┌─────────────┬─────────────┬─────────────┐
    │ Compliance  │  Anomalies  │  Duplicates │
    └─────────────┴─────────────┴─────────────┘
            ↓
       Payment AI
            ↓
      Isolation Forest
            ↓
        Risk Fusion
            ↓
    Risk Score + WHY Risky

---

## 🔬 AI / ML

- **Compliance:** Rule-based lifecycle & financial checks
- **Anomaly Detection:** Median/MAD, modified z-score & IQR
- **Payment AI:** Transaction and payment behaviour analysis
- **Duplicate AI:** Similarity and evidence-based matching
- **Isolation Forest:** Unsupervised anomaly detection
- **Risk Fusion:** Combines multiple evidence sources into a `0–100` score

### Risk Weights

| Evidence | Weight |
|---|---:|
| Compliance | 35 |
| Financial Anomaly | 25 |
| Timeline Anomaly | 15 |
| Duplicate | 15 |
| Data Quality | 10 |

---

## 📊 Current Results

**43,863 projects analyzed**

    LOW        42,196
    MEDIUM      1,662
    HIGH            5
    CRITICAL        0

---

## 🏗️ Tech Stack

**Frontend:** React, Vite, Tailwind CSS  
**Backend:** FastAPI, Python, SQLAlchemy  
**Database:** PostgreSQL  
**ML/Data:** Pandas, NumPy, Scikit-learn

---

## 📁 Project Structure

    MPLADS-AI-Shield/
    ├── backend/
    │   ├── app/
    │   ├── ml/
    │   │   ├── preprocessing.py
    │   │   ├── sources.py
    │   │   ├── canonical.py
    │   │   ├── features.py
    │   │   ├── compliance/
    │   │   ├── anomalies/
    │   │   ├── duplicates/
    │   │   ├── risk.py
    │   │   └── risk_config.py
    │   ├── data/
    │   └── tests/
    ├── frontend/
    │   └── src/
    └── docs/

---

## 🚦 Project Status

    ✅ Phase 1 — Preprocessing
    ✅ Phase 2 — Canonicalization
    ✅ Phase 3 — Feature Engineering
    ✅ Phase 4 — Compliance
    ✅ Phase 5 — Anomaly Detection
    ✅ Phase 6 — Duplicate AI
    ✅ Phase 7 — Payment AI
    ✅ Phase 8 — Isolation Forest
    ✅ Phase 9 — Risk Fusion + WHY Risky

    🔄 Phase 10 — Evaluation + Synthetic Anomaly Tests
    🔜 Phase 11 — FastAPI ML Integration
    🔜 Phase 12 — Upload & Analyze
    🔜 Phase 13 — Role-Based Dashboard + Alerts
    🔜 Phase 14 — SIH Polish & Demo

---

## ⚠️ Responsible AI

AI Shield identifies **unusual patterns and projects requiring review**.

It does **not** claim or prove fraud.

> **An anomaly is a signal for investigation, not proof of fraud.**

---

## 🚀 Vision

**Upload → Analyze → Detect → Explain → Prioritize → Investigate**

### From fragmented records to actionable intelligence.
