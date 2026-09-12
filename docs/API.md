# MPLADS AI Shield — Backend API

This document describes the FastAPI backend **as it actually exists in this
repository** (`backend/app/`). Every field, endpoint, and example below was
verified directly against the current code and, where shown, against a real
request/response from a running instance of the app — nothing here is
aspirational or copied from an earlier plan.

If you're integrating a frontend against this API, read
[Frontend Integration](#frontend-integration) first.

---

## Overview

- **Framework**: FastAPI + SQLAlchemy, PostgreSQL in production / SQLite for
  tests.
- **Auth**: JWT bearer tokens (`Authorization: Bearer <token>`), issued by
  `POST /auth/login`.
- **Data**: `GET /projects`, `GET /projects/{id}`, `GET /dashboard/stats`,
  `GET /alerts`, and `GET /analytics` all read from one real table
  (`projects`), populated from the actual Phase 2 MPLADS dataset
  (56,323 rows) via `import_phase2.py` — not mock/demo data (a separate
  `seed_data.py` script exists for inserting *synthetic* rows for local
  dev, and every such row is clearly and permanently marked
  `is_synthetic=True` in the database; it does not appear in API
  responses since `is_synthetic` isn't part of `ProjectOut`).
- **Risk data**: `risk_score`, `risk_level`, and the related fields are
  **pre-computed and imported**, not calculated by this API at request
  time — see [Risk Data](#risk-data) for exactly what that means.

---

## Local Setup

```bash
# 1. Clone and enter the backend
git clone https://github.com/Aakriti0207/MPLADS-AI-Shield.git
cd MPLADS-AI-Shield/backend

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# then edit .env with real values -- see Environment Variables below

# 5. Create the database tables (requires a running PostgreSQL instance
#    matching DATABASE_URL in .env)
python create_tables.py

# 6. Populate data (either or both):
python seed_data.py        # synthetic demo rows, safe for local dev
python import_phase2.py    # the real 56,323-row Phase 2 dataset,
                            # if you have data/phase2/project_risk_scores.csv

# 7. Run the API
uvicorn app.main:app --reload

# 8. Open interactive docs (development only -- see CORS & Environment
#    section for why these are disabled in production)
# http://127.0.0.1:8000/docs
```

---

## Environment Variables

Exact names, as read directly from `app/database.py`, `app/auth.py`, and
`app/main.py`. See `backend/.env.example` for the full file with
placeholders.

| Variable | Required? | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | **Required** — app refuses to start without it | none | PostgreSQL connection string, e.g. `postgresql://user:pass@localhost:5432/mplads_ai_shield` |
| `JWT_SECRET_KEY` | **Required** — app refuses to start without it | none | Signing secret for JWTs. Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `JWT_ALGORITHM` | Optional | `HS256` | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Optional | `60` | Access token lifetime |
| `CORS_ORIGINS` | **Required if `ENVIRONMENT=production`**; optional otherwise | Local Vite dev origins (`http://localhost:5173`, `http://127.0.0.1:5173`) when unset outside production | Comma-separated list of allowed frontend origins |
| `ENVIRONMENT` | Optional | `development` | `production` disables `/docs`/`/redoc`/`/openapi.json` and makes `CORS_ORIGINS` mandatory |

Never commit a real `.env` file — it's already listed in `backend/.gitignore`.

---

## Authentication

### Flow

1. `POST /auth/register` — create an account.
2. `POST /auth/login` — exchange email + password for a JWT access token.
3. Send that token on every protected request:
   `Authorization: Bearer <access_token>`
4. `GET /auth/me` — fetch the authenticated user's own profile (useful to
   verify a stored token is still valid, e.g. on app startup).

### Public vs. protected routes

| Public (no token needed) | Protected (`Authorization: Bearer <token>` required) |
|---|---|
| `GET /` | `GET /auth/me` |
| `POST /auth/register` | `GET /projects`, `GET /projects/{id}` |
| `POST /auth/login` | `GET /dashboard/stats` |
| | `GET /alerts` |
| | `GET /analytics` |
| | `POST /upload-analyze` |

### What happens with a bad token

Every failure mode below returns the **same** generic response, by design —
this stops a caller from probing which emails are registered or which
tokens are almost-valid:

```json
HTTP 401
{ "detail": "Could not validate credentials" }
```

This covers: missing `Authorization` header, malformed header, invalid
signature, expired token, a token whose `sub` doesn't match any user, and a
token for a user whose account has since been deactivated (`is_active =
false`).

Login itself (`POST /auth/login`) also uses one generic message for both
"no such email" and "wrong password":

```json
HTTP 401
{ "detail": "Incorrect email or password." }
```

### Rate limiting on auth endpoints

`POST /auth/login` and `POST /auth/register` are limited to **5 requests
per 60 seconds per client IP**. Exceeding it returns:

```json
HTTP 429
{ "detail": "Too many requests. Please try again later." }
```
with a `Retry-After` header (seconds). This is a basic, single-process,
in-memory deterrent — see [Known Limitations](#known-limitations).

---

## API Endpoints

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| GET | `/` | Public | Health check |
| POST | `/auth/register` | Public | Create a user account |
| POST | `/auth/login` | Public | Exchange credentials for a JWT |
| GET | `/auth/me` | Bearer | Get the authenticated user's profile |
| GET | `/projects` | Bearer | List projects (paginated) |
| GET | `/projects/{project_id}` | Bearer | Get one project by ID |
| GET | `/dashboard/stats` | Bearer | Portfolio-wide aggregate statistics |
| GET | `/alerts` | Bearer | Risk-derived alerts (paginated) |
| GET | `/analytics` | Bearer | Extended analytics (superset of `/dashboard/stats`) |
| POST | `/upload-analyze` | Bearer | Upload a CSV of candidate projects for compliance analysis (not persisted) |

---

## Projects

### `GET /projects`

Query parameters:

| Param | Type | Default | Constraints |
|---|---|---|---|
| `skip` | int | `0` | `>= 0` |
| `limit` | int | `50` | `1`–`100` |

Values outside these bounds return `422` (see [Error Handling](#error-handling)).
Results are ordered by `project_id` ascending, deterministically, so
consecutive pages never overlap or skip rows.

Response: `200`, an array of the `ProjectOut` objects described below.

### `GET /projects/{project_id}`

`project_id` is a real MPLADS work ID and **contains literal `/`
characters** (e.g. `WS/MP07/2025-2026/00123`) — URL-encode it:
`/projects/WS%2FMP07%2F2025-2026%2F00123`.

- Found → `200`, one `ProjectOut` object.
- Not found → `404`:
```json
  { "detail": "Project 'DOES-NOT-EXIST' not found" }
```

### `ProjectOut` fields

Every field below is exactly what's on the `Project` SQLAlchemy model —
nothing is fabricated or renamed for the API layer. **Fields marked
nullable are genuinely `null` for a large share of real rows** — never
treat a `null` here as "0" or "empty string".

| Field | Type | Nullable? | Notes |
|---|---|---|---|
| `project_id` | string | No | Real MPLADS work ID; contains `/` |
| `state` | string | **Yes** | Null for ~41% of real rows |
| `district` | string | **Yes** | Null for essentially all real rows |
| `constituency` | string | Yes | |
| `mp_name` | string | Yes | |
| `work_type` | string | Yes | |
| `implementing_agency` | string | Yes | |
| `sanctioned_amount` | decimal (as JSON string, e.g. `"2500000.00"`) | Yes | |
| `estimated_cost` | decimal | **Yes — null for essentially all real rows** | No source value in the real Phase 2 dataset |
| `expenditure` | decimal | Yes | |
| `financial_progress` | decimal (0–100) | Yes | |
| `physical_progress` | decimal (0–100) | **Yes — null for essentially all real rows** | No source value in the real dataset |
| `sanction_date` | date (`YYYY-MM-DD`) | Yes | |
| `start_date` | date | Yes | |
| `expected_completion` | date | **Yes — null for essentially all real rows** | |
| `actual_completion` | date | Yes | |
| `latitude` / `longitude` | decimal | **Yes — null for real rows** | No coordinates in the source data; never fabricate a map marker for these |
| `status` | string | **Yes — null for essentially all real rows** | |
| `risk_score` | decimal (0–100) | Yes | See [Risk Data](#risk-data) |
| `risk_level` | string: `LOW` \| `MEDIUM` \| `HIGH` (no `CRITICAL` observed in current real data, but the field allows any string) | Yes | Uppercase in the DB/API — normalize case-insensitively in the frontend if needed |
| `financial_risk_score`, `payment_risk_score`, `execution_risk_score`, `peer_anomaly_score`, `isolation_forest_score`, `anomaly_risk_score`, `duplicate_risk_score` | decimal (0–100) | Yes | Component sub-scores behind `risk_score` |
| `raw_max_similarity` | decimal (0–1) | Yes | Highest similarity to another project, if any |
| `most_similar_work_id` | string | Yes | The `project_id` `raw_max_similarity` refers to |
| `risk_reason_1`, `risk_reason_2`, `risk_reason_3` | string | **Yes — populated for only a handful of the 56,323 real rows** | Free-text explanation strings, not codes |
| `risk_metadata` | object | Yes | Free-form JSON (e.g. `work_category`, `n_distinct_vendors`) — treat as opaque/optional, don't assume specific keys are always present |
| `created_at`, `updated_at` | datetime | No | DB row timestamps, not project dates |

*(There is no `id`, `work_id`, or `name` field — `project_id` is both the
primary key and the only identifier/label; there is no project title/name
in the real data.)*

---

## Dashboard

### `GET /dashboard/stats`

No query parameters. Every value is computed live from the `projects`
table with SQL aggregates (`COUNT`/`SUM`/`AVG`/`GROUP BY`) — nothing is
cached or hardcoded.

| Field | Type | Notes |
|---|---|---|
| `total_projects` | int | |
| `total_sanctioned_amount` | decimal | |
| `total_expenditure` | decimal | |
| `average_financial_progress` | decimal, nullable | |
| `average_physical_progress` | decimal, nullable | Null on the real dataset (see `ProjectOut.physical_progress` above) |
| `active_projects` | int | `total_projects - completed_projects` |
| `completed_projects` | int | `status` (case-insensitively) `= "Completed"` |
| `delayed_projects` | int | Not completed, has an `expected_completion` date, and that date has passed |
| `risk_level_counts` | object, e.g. `{"HIGH": 12, "MEDIUM": 40, "LOW": 300}` | Unscored (`risk_level IS NULL`) projects are excluded entirely, not bucketed |
| `by_state` | array of `{state, total_sanctioned_amount, total_expenditure}` | `state` is `"Not specified"` for null/blank |
| `by_work_type` | array of `{work_type, count}` | `work_type` is `"Not specified"` for null/blank |

---

## Alerts

### `GET /alerts`

Query parameters: `skip` (default `0`, `>= 0`), `limit` (default `50`,
`1`–`100`) — same pagination semantics as `/projects`.

Alerts are **derived live from the same `Project` risk columns** described
above — there is no separate alerts table, and these are not mock/sample
data. A project can generate more than one alert. Rules:

| `alert_type` | Trigger | `severity` |
|---|---|---|
| `high_risk_project` | `risk_level` is `HIGH` or `CRITICAL` | same as `risk_level`, lowercased |
| `possible_duplicate` | `raw_max_similarity >= 0.85` and `most_similar_work_id` is set | `high` if `>= 0.95`, else `medium` |
| `financial_risk`, `payment_risk`, `execution_risk`, `peer_anomaly`, `anomaly_detection`, `anomaly_risk` | corresponding component score `>= 80` | `critical` |

`AlertOut` fields: `alert_id`, `project_id`, `alert_type`, `severity`,
`message` (human-readable, built from the real stored reason text where
available), `created_at`.

Sort order: severity priority, then the project's `risk_score` descending,
then `project_id` — deterministic across pages.

---

## Risk Data

**Important, read before building any risk UI:** `risk_score`,
`risk_level`, and every related field on `ProjectOut` are **pre-computed
offline and imported** into the database (`import_phase2.py`, from
`data/phase2/project_risk_scores.csv`) — this API does **not** run any ML
model or calculate these values at request time. They are advisory,
review-priority signals for human review, not a fraud determination (see
`app/models.py`'s docstring).

- `risk_reason_1/2/3` are free-text strings explaining specific findings
  (e.g. "Expenditure is recorded... but no matching sanction record
  exists...") — they are populated for only a small fraction of real
  rows; most real projects have `null` for all three, which is expected,
  not a bug.
- `risk_metadata` is an opaque JSON object; don't assume any specific key
  is always present.
- `GET /analytics`'s `risk_score_summary` (average/min/max, and
  `scored_project_count` — the count of projects that actually have a
  score) is the only place the API *aggregates* risk scores; it still
  never calculates a new one.

---

## Analytics

### `GET /analytics`

No query parameters. **Superset of `/dashboard/stats`** — every field
`/dashboard/stats` returns is also present here (computed by the exact
same backend functions, so the two can never disagree), plus:

| Field | Type | Notes |
|---|---|---|
| `risk_score_summary` | `{average, minimum, maximum, scored_project_count}` | All null/0 only if zero projects have a `risk_score` |
| `estimated_cost_summary` | `{total, average, minimum, maximum, project_count_with_data}` | On the real dataset, `project_count_with_data` will be `0` (or near it) since real rows have no `estimated_cost` source value — this is reported honestly, not defaulted to 0 |
| `financial_progress_summary` / `physical_progress_summary` | same shape as above | for `financial_progress` / `physical_progress` respectively |
| `status_distribution` | array of `{status, count}` | `"Not specified"` bucket for null/blank |

---

## Upload / Analyze

### `POST /upload-analyze`

`multipart/form-data`, field name `file`, CSV only.

**What this does NOT do**: it does not calculate a `risk_score` or
`risk_level` for the uploaded rows, and it does not persist anything to
the database. The real risk-scoring pipeline exists only as an offline
process outside this repository — recreating it here would mean
fabricating a score, which this endpoint deliberately does not do. What it
**does** do is run the real, existing MPLADS compliance rule engine
(`ml/compliance/rules.py`) against each row.

**Limits**: 2 MB max file size, 500 rows max, `.csv` extension only,
rate-limited to 10 requests/60s per client IP.

**CSV columns** — only `work_id` is required; every other column is
optional (a missing date/amount simply means the compliance rules that
need it return `NOT_EVALUABLE` rather than failing):

`work_id`, `sanctioned_amount`, `recommended_amount`, `amount_disbursed`,
`expenditure`, `estimated_cost`, `recommended_date`, `sanction_date`,
`completion_date`, `first_expenditure_date`, `state`, `work_type`,
`implementing_agency`, `status`

Response fields (top level): `filename`, `total_rows`, `valid_rows`,
`rows_with_errors`, `persisted_to_database` (always `false`),
`persistence_note`, `risk_scoring_note`, `results` (array, one entry per
CSV row).

Each `results[]` entry: `row_number`, `work_id`, `is_valid`,
`validation_errors` (array of `{field, message}` for that row, if any),
`matches_existing_project_id` (a real DB lookup — true if that `work_id`
already exists in `projects`), `basic_metrics`
(`{financial_progress_percent, expenditure_exceeds_sanctioned_amount}` —
plain arithmetic from what you supplied, not a model output),
`compliance` (`{compliance_status, high_severity_count, warning_count,
data_quality_issue_count, rules_evaluated, rules_flagged, findings[]}` —
`findings[]` items are `{rule_id, category, status, severity, message,
evidence}`), and `risk_score`/`risk_level` (always `null`).

File-level problems (empty file, wrong extension, missing `work_id`
column, duplicate `work_id` values, too many rows) return `400` with a
plain-text `detail` message. Row-level problems never fail the whole
request — that row's `is_valid` is `false` with `validation_errors`
explaining why, and the rest of the file is still processed.

---

## Error Handling

Standard FastAPI/Pydantic v2 shapes — nothing custom.

**401** (missing/invalid/expired token, or wrong login credentials):
```json
{ "detail": "Could not validate credentials" }
```

**404** (unknown `project_id`):
```json
{ "detail": "Project 'DOES-NOT-EXIST' not found" }
```

**422** (invalid query param, e.g. `GET /projects?limit=0`):
```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": ["query", "limit"],
      "msg": "Input should be greater than or equal to 1",
      "input": "0",
      "ctx": { "ge": 1 }
    }
  ]
}
```

**429** (rate limit — `/auth/login`, `/auth/register`, `/upload-analyze`
only):
```json
{ "detail": "Too many requests. Please try again later." }
```

**500** (unexpected server error — should be rare): a fixed generic body,
never a stack trace, file path, or internal detail:
```json
{ "detail": "Internal server error." }
```

---

## CORS

Configured in `app/main.py` via the `CORS_ORIGINS` environment variable
(see [Environment Variables](#environment-variables)).

- **Local development**: if `CORS_ORIGINS` is unset and `ENVIRONMENT` is
  not `production`, the API allows `http://localhost:5173` and
  `http://127.0.0.1:5173` (the Vite dev server's default origins) — no
  extra configuration needed for local frontend development.
- **Production**: `ENVIRONMENT=production` makes `CORS_ORIGINS` mandatory
  — the app refuses to start without it. Set it to your real deployed
  frontend origin(s), comma-separated.
- Allowed methods: `GET`, `POST` only (everything this API exposes).
- Allowed headers: `Authorization`, `Content-Type`.
- `allow_credentials` is `False` — this API is used with a bearer token,
  never cookies.

**Production CORS is not configured out of the box** — you must set
`CORS_ORIGINS` yourself for your actual deployed frontend URL.

---

## Frontend Integration

The frontend in this repo (`frontend/src/`) already integrates against
this exact API — the examples below match its real code
(`frontend/src/lib/api.js`, `frontend/src/context/AuthContext.jsx`).

### 1. Configure the backend URL

`frontend/.env`:
VITE_API_URL=http://127.0.0.1:8000

`lib/api.js` reads this via `import.meta.env.VITE_API_URL`, falling back
to `http://127.0.0.1:8000` if unset.

### 2. Login and store the token

```javascript
const res = await fetch(`${API_BASE}/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password }),
})
const { access_token } = await res.json()
// frontend/src/context/AuthContext.jsx stores this via lib/authToken.js
```

### 3. Call protected endpoints with `apiFetch`

The frontend's `lib/api.js` already wraps `fetch` to attach the token
automatically:

```javascript
import { apiFetch } from '../lib/api'

const res = await apiFetch('/projects?skip=0&limit=50')
if (!res.ok) {
  if (res.status === 401) {
    // apiFetch already calls the registered "unauthorized handler"
    // (AuthContext's logout()) on any 401 -- no extra handling usually needed
  }
  // handle other error shapes per "Error Handling" above
}
const projects = await res.json()
```

Equivalent raw `fetch`, if not using the wrapper:
```javascript
fetch(`${API_BASE}/projects`, {
  headers: { Authorization: `Bearer ${token}` },
})
```

### 4. Handling specific error codes

- **401** → token missing/expired/invalid — clear stored auth state and
  redirect to login (already handled by `apiFetch`'s unauthorized-handler
  hook).
- **404** → the requested `project_id` doesn't exist — show a "not found"
  state, don't retry.
- **422** → invalid request parameters (e.g. bad pagination values) — this
  is a frontend bug if it happens with normal user input; check the
  `detail[].loc` to see which parameter.
- **429** → rate-limited — show the message from `detail` and, if present,
  respect the `Retry-After` header before retrying.

### 5. Risk level casing

The API always returns `risk_level` uppercase (`"HIGH"`, `"MEDIUM"`,
`"LOW"`). If your UI component expects Title Case (e.g. a badge
component), normalize it client-side — the existing frontend already does
this consistently (see `titleCase()` in `Projects.jsx`,
`ProjectDetails.jsx`, `MapPage.jsx`).

---

## Testing

```bash
cd backend
pytest -q
```

Verified in this repository state: **98 tests pass** (auth, protected
routes, project pagination/detail, dashboard aggregates, risk fields,
alerts, analytics, upload/analyze, and security/CORS/rate-limiting). A
passing run means: authentication and authorization work correctly,
project pagination and 404 handling are correct, dashboard/analytics
aggregates match hand-computed expected values, risk fields serialize
correctly including null handling, alerts stay consistent with the
underlying risk data, upload validation and the compliance engine behave
correctly, and CORS/rate-limiting/security headers work as configured.

---

## Swagger / OpenAPI

Available at `/docs` (Swagger UI) and `/redoc`, **in development only**
(`ENVIRONMENT` unset or not `production`) — disabled entirely when
`ENVIRONMENT=production`, since they expose the full API surface/schema.

Verified: every route's docstring is used as its OpenAPI description;
protected routes correctly show a security requirement (padlock icon) in
Swagger UI, public routes (`/`, `/auth/register`, `/auth/login`) do not.
The raw schema is also available as JSON at `/openapi.json` (dev only).

---

## Known Limitations

Real, current limitations — not bugs, and not all in scope for this repo
to fix on its own:

- **Sparse risk reasons**: `risk_reason_1/2/3` are populated for only a
  small fraction of the real 56,323-row dataset. This reflects the
  underlying data, not a backend defect.
- **`estimated_cost`, `physical_progress`, `expected_completion`,
  `latitude`/`longitude`, `district`, `status`**: null for most/all real
  rows — there's no source value for them in the real Phase 2 dataset.
  Never fabricate these client-side.
- **Rate limiting is per-process, in-memory**: effective for a single
  backend instance, but resets on restart and doesn't coordinate across
  multiple workers/instances. A real multi-instance deployment needs a
  shared store (Redis) or a gateway-level limiter.
- **No HTTPS of its own**: this API expects a reverse proxy to terminate
  TLS in front of it in any real deployment.
- **Upload/analyze does not calculate risk**: intentional — see
  [Upload / Analyze](#upload--analyze).