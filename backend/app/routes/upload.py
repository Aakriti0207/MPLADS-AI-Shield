"""
Route for POST /upload-analyze.

Phase 5 audit conclusion (see app/upload_analysis.py's module docstring
for the full detail): no upload endpoint, and no real-time risk-scoring
capability, existed anywhere in this repository before this file --
verified by grepping the whole backend for "upload"/"UploadFile"/
"multipart" (zero matches) and by inspecting backend/ml/ (the compliance
rule engine is the one piece that's genuinely safe and reusable at
single-project, request-time granularity; anomaly and duplicate
detection are not, and are not attempted here -- see Deferred in the
Phase 5 report).

This endpoint:
  1. Accepts a single CSV file (multipart/form-data).
  2. Validates it at the file level (extension, size, row count, header
     shape) and then at the row level (required work_id, numeric/date
     parsing) -- a bad row never aborts the rest of the upload.
  3. Runs the real, unmodified ml/compliance rule engine on each valid
     row.
  4. Looks up (read-only) whether each work_id already exists in the
     real `projects` table.
  5. Returns a structured result. Nothing is written to the database --
     see persistence_note in the response and Step 7 of the Phase 5
     report for why a preview-only flow was chosen.

Protected the same way as the other project/business-data endpoints
(projects.py, dashboard.py, alerts.py, analytics.py): router-level
Depends(get_current_user).
"""

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.schemas import (
    BasicMetricsOut,
    ComplianceSummaryOut,
    UploadAnalyzeResponse,
    UploadRowResult,
    UploadRowValidationError,
)
from app.upload_analysis import (
    UploadFormatError,
    compute_basic_metrics,
    existing_project_ids,
    parse_row,
    read_and_validate_csv,
    run_compliance_for_row,
)

router = APIRouter(
    prefix="/upload-analyze",
    tags=["upload-analyze"],
    dependencies=[Depends(get_current_user)],
)

PERSISTENCE_NOTE = (
    "Uploaded projects are analyzed only and are NOT written to the database. "
    "This keeps the existing 56,323 real project records safe from accidental "
    "modification. If you want a project saved, add it through a separate, "
    "explicit save step (not implemented in this phase)."
)

RISK_SCORING_NOTE = (
    "risk_score and risk_level are intentionally not calculated for uploaded "
    "projects. The real Project.risk_score/risk_level are produced by an "
    "offline pipeline (combining compliance, anomaly, and duplicate-detection "
    "signals with a weighting step) that lives outside this repository -- "
    "recreating that combination here would mean inventing a score, which "
    "this API will not do. What this endpoint DOES provide is a genuine, "
    "unmodified run of the existing compliance rule engine "
    "(ml/compliance/rules.py) against the fields you supplied -- see the "
    "'compliance' field on each result."
)


@router.post("", response_model=UploadAnalyzeResponse)
async def upload_analyze(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    raw_bytes = await file.read()

    try:
        df = read_and_validate_csv(raw_bytes, file.filename or "")
    except UploadFormatError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    parsed_rows = [parse_row(i, row) for i, (_, row) in enumerate(df.iterrows(), start=1)]

    candidate_ids = [r.work_id for r in parsed_rows if r.work_id]
    existing_ids = existing_project_ids(db, candidate_ids)

    results: list[UploadRowResult] = []
    valid_count = 0

    for parsed in parsed_rows:
        if parsed.errors:
            results.append(
                UploadRowResult(
                    row_number=parsed.row_number,
                    work_id=parsed.work_id,
                    is_valid=False,
                    validation_errors=[
                        UploadRowValidationError(field=field, message=message)
                        for field, message in parsed.errors
                    ],
                    matches_existing_project_id=None,
                    basic_metrics=None,
                    compliance=None,
                )
            )
            continue

        valid_count += 1
        basic_metrics = BasicMetricsOut(**compute_basic_metrics(parsed.values))

        compliance_raw = run_compliance_for_row(parsed.work_id, parsed.values)
        compliance = ComplianceSummaryOut(
            compliance_status=compliance_raw["compliance_status"],
            high_severity_count=int(compliance_raw["high_severity_count"]),
            warning_count=int(compliance_raw["warning_count"]),
            data_quality_issue_count=int(compliance_raw["data_quality_issue_count"]),
            rules_evaluated=int(compliance_raw["rules_evaluated"]),
            rules_flagged=int(compliance_raw["rules_flagged"]),
            findings=compliance_raw["findings"],
        )

        results.append(
            UploadRowResult(
                row_number=parsed.row_number,
                work_id=parsed.work_id,
                is_valid=True,
                validation_errors=[],
                matches_existing_project_id=parsed.work_id in existing_ids,
                basic_metrics=basic_metrics,
                compliance=compliance,
            )
        )

    return UploadAnalyzeResponse(
        filename=file.filename or "upload.csv",
        total_rows=len(parsed_rows),
        valid_rows=valid_count,
        rows_with_errors=len(parsed_rows) - valid_count,
        persisted_to_database=False,
        persistence_note=PERSISTENCE_NOTE,
        risk_scoring_note=RISK_SCORING_NOTE,
        results=results,
    )