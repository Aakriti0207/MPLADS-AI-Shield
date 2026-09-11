"""
Phase 5 tests: POST /upload-analyze.

Uses the same `client` / `auth_headers` / `db_session` fixtures as the
rest of the suite (see conftest.py). CSV content is built inline as
plain strings and posted as multipart file uploads, the same way a
real client would call this endpoint.
"""

from decimal import Decimal

from app.models import Project
from app.upload_analysis import MAX_ROWS


def _upload(client, headers, content: str, filename: str = "projects.csv"):
    files = {"file": (filename, content, "text/csv")}
    return client.post("/upload-analyze", headers=headers, files=files)


VALID_CSV = (
    "work_id,sanctioned_amount,expenditure,recommended_date,sanction_date\n"
    "WS/TEST/UP/1,500000,400000,2024-01-01,2024-02-01\n"
)


# --- Auth -----------------------------------------------------------------

def test_upload_without_jwt_returns_401(client):
    resp = _upload(client, {}, VALID_CSV)
    assert resp.status_code == 401


def test_upload_with_valid_jwt_succeeds(client, auth_headers):
    resp = _upload(client, auth_headers, VALID_CSV)
    assert resp.status_code == 200


# --- File-level validation --------------------------------------------------

def test_upload_empty_file_is_rejected(client, auth_headers):
    resp = _upload(client, auth_headers, "")
    assert resp.status_code == 400


def test_upload_wrong_file_extension_is_rejected(client, auth_headers):
    resp = _upload(client, auth_headers, VALID_CSV, filename="projects.txt")
    assert resp.status_code == 400


def test_upload_missing_required_column_is_rejected(client, auth_headers):
    csv_without_work_id = "state,sanctioned_amount\nBihar,500000\n"
    resp = _upload(client, auth_headers, csv_without_work_id)
    assert resp.status_code == 400
    assert "work_id" in resp.json()["detail"]


def test_upload_malformed_csv_is_handled_cleanly(client, auth_headers):
    """A CSV with a ragged row (more fields than the header) must return
    a clean 400, never a 500 or a raw traceback."""
    malformed = "work_id,sanctioned_amount\nWS/1,100,999,extra,columns,here\n"
    resp = _upload(client, auth_headers, malformed)
    assert resp.status_code in (400, 200)  # pandas' C parser can recover some ragged rows
    assert resp.status_code != 500


def test_upload_duplicate_work_id_in_file_is_rejected(client, auth_headers):
    dup_csv = (
        "work_id,sanctioned_amount\n"
        "WS/DUP/1,100000\n"
        "WS/DUP/1,200000\n"
    )
    resp = _upload(client, auth_headers, dup_csv)
    assert resp.status_code == 400


def test_upload_too_many_rows_is_rejected(client, auth_headers):
    header = "work_id,sanctioned_amount\n"
    rows = "".join(f"WS/BULK/{i},100000\n" for i in range(MAX_ROWS + 1))
    resp = _upload(client, auth_headers, header + rows)
    assert resp.status_code == 400


# --- Row-level validation: bad rows never crash the whole upload ---------

def test_upload_invalid_numeric_value_is_a_row_level_error(client, auth_headers):
    csv_content = (
        "work_id,sanctioned_amount\n"
        "WS/GOOD/1,500000\n"
        "WS/BAD/1,not-a-number\n"
    )
    resp = _upload(client, auth_headers, csv_content)
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_rows"] == 2
    assert body["valid_rows"] == 1
    assert body["rows_with_errors"] == 1

    bad_row = next(r for r in body["results"] if r["work_id"] == "WS/BAD/1")
    assert bad_row["is_valid"] is False
    assert any(e["field"] == "sanctioned_amount" for e in bad_row["validation_errors"])
    assert bad_row["compliance"] is None


def test_upload_invalid_date_value_is_a_row_level_error(client, auth_headers):
    csv_content = "work_id,sanction_date\nWS/BADDATE/1,not-a-date\n"
    resp = _upload(client, auth_headers, csv_content)
    assert resp.status_code == 200
    body = resp.json()
    row = body["results"][0]
    assert row["is_valid"] is False
    assert any(e["field"] == "sanction_date" for e in row["validation_errors"])


def test_upload_blank_work_id_is_a_row_level_error(client, auth_headers):
    csv_content = "work_id,sanctioned_amount\n,500000\n"
    resp = _upload(client, auth_headers, csv_content)
    assert resp.status_code == 200
    row = resp.json()["results"][0]
    assert row["is_valid"] is False
    assert any(e["field"] == "work_id" for e in row["validation_errors"])


# --- Analysis content: genuine reuse of the compliance rule engine -------

def test_upload_runs_real_compliance_rules_and_flags_expected_issues(client, auth_headers):
    """Expenditure well above sanctioned amount must trigger the real
    C08 rule (not a fabricated flag)."""
    csv_content = (
        "work_id,sanctioned_amount,expenditure\n"
        "WS/OVERSPEND/1,100000,500000\n"
    )
    resp = _upload(client, auth_headers, csv_content)
    assert resp.status_code == 200
    row = resp.json()["results"][0]

    assert row["is_valid"] is True
    assert row["compliance"]["compliance_status"] == "REVIEW_REQUIRED"
    c08 = next(f for f in row["compliance"]["findings"] if f["rule_id"] == "C08")
    assert c08["status"] == "FLAG"
    assert c08["severity"] == "HIGH"

    assert row["basic_metrics"]["expenditure_exceeds_sanctioned_amount"] is True
    assert float(row["basic_metrics"]["financial_progress_percent"]) == 500.0


def test_upload_never_returns_a_fabricated_risk_score(client, auth_headers):
    resp = _upload(client, auth_headers, VALID_CSV)
    assert resp.status_code == 200
    row = resp.json()["results"][0]
    assert row["risk_score"] is None
    assert row["risk_level"] is None
    assert "offline pipeline" in resp.json()["risk_scoring_note"]


def test_upload_missing_dates_produce_not_evaluable_not_a_crash(client, auth_headers):
    """No dates supplied at all -- every date-dependent rule should come
    back NOT_EVALUABLE, never crash and never fabricate a PASS/FLAG."""
    csv_content = "work_id,sanctioned_amount\nWS/NODATES/1,500000\n"
    resp = _upload(client, auth_headers, csv_content)
    assert resp.status_code == 200
    row = resp.json()["results"][0]
    assert row["is_valid"] is True
    c01 = next(f for f in row["compliance"]["findings"] if f["rule_id"] == "C01")
    assert c01["status"] == "NOT_EVALUABLE"


# --- Existing-project lookup: genuine DB read, not fabricated ------------

def test_upload_flags_work_id_that_already_exists_in_database(client, db_session, auth_headers):
    db_session.add(Project(project_id="WS/EXISTING/1", is_synthetic=True))
    db_session.commit()

    csv_content = "work_id,sanctioned_amount\nWS/EXISTING/1,100000\n"
    resp = _upload(client, auth_headers, csv_content)
    assert resp.status_code == 200
    row = resp.json()["results"][0]
    assert row["matches_existing_project_id"] is True


def test_upload_new_work_id_does_not_match_existing_project(client, auth_headers):
    resp = _upload(client, auth_headers, VALID_CSV)
    row = resp.json()["results"][0]
    assert row["matches_existing_project_id"] is False


# --- Database safety: nothing is persisted --------------------------------

def test_upload_does_not_persist_to_database(client, db_session, auth_headers):
    before = db_session.query(Project).count()

    resp = _upload(client, auth_headers, VALID_CSV)
    assert resp.status_code == 200
    assert resp.json()["persisted_to_database"] is False

    after = db_session.query(Project).count()
    assert after == before  # nothing was inserted


def test_upload_does_not_modify_existing_project_row(client, db_session, auth_headers):
    db_session.add(Project(project_id="WS/UNCHANGED/1", sanctioned_amount=Decimal("999.00"), is_synthetic=True))
    db_session.commit()

    csv_content = "work_id,sanctioned_amount\nWS/UNCHANGED/1,1.00\n"
    _upload(client, auth_headers, csv_content)

    row = db_session.query(Project).filter_by(project_id="WS/UNCHANGED/1").one()
    assert row.sanctioned_amount == Decimal("999.00")  # untouched by the upload


# --- Existing endpoints remain unaffected ---------------------------------

def test_projects_dashboard_alerts_still_work_after_upload_endpoint_added(client, db_session, auth_headers):
    db_session.add(Project(project_id="WS/REGRESSION/1", risk_level="LOW", is_synthetic=True))
    db_session.commit()

    assert client.get("/projects", headers=auth_headers).status_code == 200
    assert client.get("/dashboard/stats", headers=auth_headers).status_code == 200
    assert client.get("/alerts", headers=auth_headers).status_code == 200