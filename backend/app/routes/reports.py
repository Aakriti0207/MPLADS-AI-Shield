"""
Phase 8 -- Reports & Export.

Every number in a generated report is computed live from the `projects`
table (same source of truth as app/aggregations.py, app/routes/dashboard.py
and app/routes/projects.py) -- nothing here is hardcoded or invented.

Report types (REPORT_TYPES below) are deliberately limited to what can
actually be built from real, existing Project columns:
    - project_monitoring: portfolio financial/progress summary
    - risk_anomaly: AI Shield risk distribution + anomaly indicators
"State Monitoring Report" / "Constituency Report" (mentioned in the
Phase 8 brief) are not separate types here -- they're the same
project_monitoring report scoped with the `state` / `constituency`
filter, since that's the real, already-authoritative way to narrow the
same query rather than a second endpoint duplicating it.

Authorization mirrors GET /dashboard/role-overview exactly: the User
model still has no state/district/constituency/MP scope column, so a
non-Ministry/Admin account cannot be given an authoritative scoped
report. GET /reports/meta reports scope_available=False for such
accounts (frontend renders "Scoped reporting is not available for this
account." per the brief) and GET /reports/generate independently
enforces the same rule server-side -- the frontend meta check is
UX only, never the authorization boundary.

Export formats:
    - format=json (default): the ReportOut payload, used to render the
      on-screen "Report Information" preview.
    - format=csv: every project row matching the current scope/filters
      (up to MAX_EXPORT_ROWS), built with Python's csv module -- no
      React-rendered text, no serialized objects.
    - format=pdf: a compact, institutional-style document (reportlab),
      matching the artifact's navy/blue palette, with the same
      sections agreed in the brief (Executive Summary, Monitoring
      Overview, Risk & AI Shield Indicators, Priority Review Items,
      Data Quality / Limitations, Disclaimer).

GET /reports/project/{project_id} is a separate, single-project PDF
(for a Project Detail "Export Report" action) -- available to any
authenticated user, exactly like GET /projects/{id} itself is not
role-gated.
"""

import csv
import io
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Project, User
from app.schemas import ReportOut, ReportProjectRow, ReportsMeta, ReportTypeInfo

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(get_current_user)],
)

# --- What this endpoint can actually generate --------------------------

REPORT_TYPES: dict[str, ReportTypeInfo] = {
    "project_monitoring": ReportTypeInfo(
        id="project_monitoring",
        label="Project Monitoring Report",
        description="Portfolio financial totals, progress, and priority projects for the selected scope.",
    ),
    "risk_anomaly": ReportTypeInfo(
        id="risk_anomaly",
        label="Risk & Anomaly Report",
        description="AI Shield risk-level distribution, duplicate/anomaly indicators, and priority review projects.",
    ),
}

FILTERS_SUPPORTED = ["state", "district", "constituency", "category", "risk_level", "date_from", "date_to"]
EXPORT_FORMATS = ["json", "csv", "pdf"]

MAX_EXPORT_ROWS = 5000
PRIORITY_LIST_LIMIT = 25
RISK_REVIEW_LEVELS = ("HIGH", "CRITICAL")


def _is_ministry(role: Optional[str]) -> bool:
    """Same substring rule as GET /dashboard/role-overview (see
    app/routes/dashboard.py) -- kept identical so a role that dashboard
    treats as national-scope is treated the same way here."""
    role = (role or "").lower()
    return "admin" in role or "ministry" in role


def _require_ministry(current_user: User) -> None:
    if not _is_ministry(current_user.role):
        raise HTTPException(
            status_code=403,
            detail="Scoped reporting is not available for this account.",
        )


@router.get("/meta", response_model=ReportsMeta)
def get_reports_meta(current_user: User = Depends(get_current_user)):
    """What report generation is available for the authenticated caller."""

    role = current_user.role or ""

    if not _is_ministry(role):
        return ReportsMeta(
            role=role,
            scope_available=False,
            unavailable_reason=(
                "Scoped reporting is not available for this account. "
                "Report generation currently requires national (Ministry/Admin) scope."
            ),
        )

    return ReportsMeta(
        role=role,
        scope_available=True,
        scope_label="National",
        report_types=list(REPORT_TYPES.values()),
        filters_supported=FILTERS_SUPPORTED,
        export_formats=EXPORT_FORMATS,
    )


def _apply_filters(
    query,
    state: Optional[str],
    district: Optional[str],
    constituency: Optional[str],
    category: Optional[str],
    risk_level: Optional[str],
    date_from: Optional[date],
    date_to: Optional[date],
):
    if state:
        query = query.filter(Project.state == state)
    if district:
        query = query.filter(Project.district == district)
    if constituency:
        query = query.filter(Project.constituency == constituency)
    if category:
        query = query.filter(Project.work_type == category)
    if risk_level:
        query = query.filter(Project.risk_level == risk_level.upper())
    if date_from:
        query = query.filter(Project.sanction_date >= date_from)
    if date_to:
        query = query.filter(Project.sanction_date <= date_to)
    return query


def _scope_label(state, district, constituency, category, risk_level, date_from, date_to) -> str:
    parts = []
    if state:
        parts.append(f"State: {state}")
    if district:
        parts.append(f"District: {district}")
    if constituency:
        parts.append(f"Constituency: {constituency}")
    if category:
        parts.append(f"Category: {category}")
    if risk_level:
        parts.append(f"Risk level: {risk_level.upper()}")
    if date_from or date_to:
        parts.append(f"Sanctioned {date_from or 'earliest'} to {date_to or 'latest'}")
    return "National" if not parts else "; ".join(parts)


def _row_from_project(project: Project) -> ReportProjectRow:
    return ReportProjectRow(
        project_id=project.project_id,
        work_type=project.work_type,
        state=project.state,
        district=project.district,
        constituency=project.constituency,
        implementing_agency=project.implementing_agency,
        status=project.status,
        sanctioned_amount=project.sanctioned_amount,
        expenditure=project.expenditure,
        financial_progress=project.financial_progress,
        risk_level=project.risk_level,
        risk_score=project.risk_score,
        risk_reasons=[r for r in (project.risk_reason_1, project.risk_reason_2, project.risk_reason_3) if r],
    )


def _build_report(
    db: Session,
    report_type: str,
    state, district, constituency, category, risk_level, date_from, date_to,
) -> ReportOut:
    if report_type not in REPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported report type '{report_type}'.")

    base_query = _apply_filters(db.query(Project), state, district, constituency, category, risk_level, date_from, date_to)

    total_projects, total_sanctioned, total_expenditure, avg_financial_progress = base_query.with_entities(
        func.count(Project.project_id),
        func.coalesce(func.sum(Project.sanctioned_amount), 0),
        func.coalesce(func.sum(Project.expenditure), 0),
        func.avg(Project.financial_progress),
    ).one()

    risk_rows = base_query.with_entities(Project.risk_level, func.count(Project.project_id)).group_by(Project.risk_level).all()
    risk_level_counts = {level: count for level, count in risk_rows if level is not None}
    projects_requiring_review = sum(count for level, count in risk_level_counts.items() if level in RISK_REVIEW_LEVELS)

    duplicate_indicators = (
        base_query.filter(Project.duplicate_risk_score.isnot(None), Project.duplicate_risk_score > 0)
        .with_entities(func.count(Project.project_id))
        .scalar()
        or 0
    )
    anomaly_indicators = (
        base_query.filter(Project.anomaly_risk_score.isnot(None), Project.anomaly_risk_score > 0)
        .with_entities(func.count(Project.project_id))
        .scalar()
        or 0
    )

    priority_rows = (
        base_query.filter(Project.risk_level.in_(list(RISK_REVIEW_LEVELS)))
        .order_by(Project.risk_score.desc().nullslast(), Project.project_id)
        .limit(PRIORITY_LIST_LIMIT)
        .all()
    )

    data_quality_notes = []
    if total_projects == 0:
        data_quality_notes.append("No projects matched the selected scope and filters.")
    if not risk_level_counts:
        data_quality_notes.append("AI Shield risk scoring is not available for the selected scope.")
    if avg_financial_progress is None:
        data_quality_notes.append("Financial progress data is not available for the selected scope.")

    return ReportOut(
        report_type=report_type,
        title=REPORT_TYPES[report_type].label,
        generated_at=datetime.now(timezone.utc),
        scope=_scope_label(state, district, constituency, category, risk_level, date_from, date_to),
        filters_applied={
            "state": state,
            "district": district,
            "constituency": constituency,
            "category": category,
            "risk_level": risk_level.upper() if risk_level else None,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
        },
        total_projects=total_projects,
        total_sanctioned_amount=total_sanctioned,
        total_expenditure=total_expenditure,
        average_financial_progress=avg_financial_progress,
        risk_level_counts=risk_level_counts,
        projects_requiring_review=projects_requiring_review,
        duplicate_indicators=duplicate_indicators,
        anomaly_indicators=anomaly_indicators,
        priority_projects=[_row_from_project(p) for p in priority_rows],
        data_quality_notes=data_quality_notes,
        disclaimer=(
            "AI Shield identifies indicators that may require review. It does not "
            "establish fraud, wrongdoing, or non-compliance."
        ),
    )


# --- CSV export ----------------------------------------------------------

CSV_HEADER = [
    "Work ID", "State", "District", "Constituency", "Category",
    "Implementing Agency", "Status", "Sanctioned Amount", "Expenditure",
    "Financial Progress (%)", "Risk Level", "Risk Score", "Risk Reasons",
]


def _decimal_cell(value: Optional[Decimal]) -> str:
    return "" if value is None else str(value)


def _row_to_csv_cells(project: Project) -> list:
    return [
        project.project_id,
        project.state or "",
        project.district or "",
        project.constituency or "",
        project.work_type or "",
        project.implementing_agency or "",
        project.status or "",
        _decimal_cell(project.sanctioned_amount),
        _decimal_cell(project.expenditure),
        _decimal_cell(project.financial_progress),
        project.risk_level or "",
        _decimal_cell(project.risk_score),
        " | ".join(r for r in (project.risk_reason_1, project.risk_reason_2, project.risk_reason_3) if r),
    ]


def _safe_filename_part(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in value)


def _csv_response(db: Session, report: ReportOut, state, district, constituency, category, risk_level, date_from, date_to) -> StreamingResponse:
    rows = (
        _apply_filters(db.query(Project), state, district, constituency, category, risk_level, date_from, date_to)
        .order_by(Project.risk_score.desc().nullslast(), Project.project_id)
        .limit(MAX_EXPORT_ROWS)
        .all()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADER)
    for project in rows:
        writer.writerow(_row_to_csv_cells(project))
    buffer.seek(0)

    filename = f"mplads-ai-shield-{report.report_type}-{report.generated_at.strftime('%Y%m%d-%H%M%S')}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- PDF export ------------------------------------------------------------

NAVY = colors.HexColor("#0B2E4F")
SECONDARY_NAVY = colors.HexColor("#123A5C")
ACCENT_BLUE = colors.HexColor("#1D63A8")
BORDER = colors.HexColor("#DCE2E8")
MUTED = colors.HexColor("#55636E")

_styles = getSampleStyleSheet()
_STYLE_TITLE = ParagraphStyle("MpladsTitle", parent=_styles["Heading1"], fontSize=15, textColor=NAVY, spaceAfter=2)
_STYLE_SUBTITLE = ParagraphStyle("MpladsSubtitle", parent=_styles["Normal"], fontSize=10, textColor=MUTED, spaceAfter=10)
_STYLE_META = ParagraphStyle("MpladsMeta", parent=_styles["Normal"], fontSize=8.5, textColor=MUTED, spaceAfter=2)
_STYLE_SECTION = ParagraphStyle("MpladsSection", parent=_styles["Heading2"], fontSize=11.5, textColor=SECONDARY_NAVY, spaceBefore=12, spaceAfter=5)
_STYLE_BODY = ParagraphStyle("MpladsBody", parent=_styles["Normal"], fontSize=9, leading=13, textColor=colors.HexColor("#16232E"))
_STYLE_NOTE = ParagraphStyle("MpladsNote", parent=_styles["Normal"], fontSize=8, leading=11, textColor=MUTED)

_TABLE_STYLE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), NAVY),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTSIZE", (0, 0), (-1, -1), 8),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F5F7")]),
    ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
])

_APP_DISCLAIMER = "This is a SIH prototype backed by live project data. It is not an official Government of India report."


def _fmt_money(value) -> str:
    if value is None:
        return "Not available"
    return f"Rs. {float(value):,.2f}"


def _fmt_pct(value) -> str:
    if value is None:
        return "Not available"
    return f"{float(value):.1f}%"


def _fmt_count(value) -> str:
    return "Not available" if value is None else f"{value:,}"


def _pdf_header_flowables(title: str, generated_at: datetime, scope: str) -> list:
    return [
        Paragraph("MPLADS AI Shield", _STYLE_TITLE),
        Paragraph(title, _STYLE_SUBTITLE),
        Paragraph(f"Generated: {generated_at.strftime('%d %B %Y, %H:%M UTC')}", _STYLE_META),
        Paragraph(f"Scope: {scope}", _STYLE_META),
        Spacer(1, 6 * mm),
    ]


def _report_pdf_bytes(report: ReportOut) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=18 * mm, bottomMargin=16 * mm, leftMargin=16 * mm, rightMargin=16 * mm,
    )

    story = _pdf_header_flowables(report.title, report.generated_at, report.scope)

    # Executive Summary
    story.append(Paragraph("Executive Summary", _STYLE_SECTION))
    story.append(Paragraph(
        f"This report covers {_fmt_count(report.total_projects)} project(s) in the selected scope, "
        f"with total sanctioned amount {_fmt_money(report.total_sanctioned_amount)} and total expenditure "
        f"{_fmt_money(report.total_expenditure)}. {_fmt_count(report.projects_requiring_review)} project(s) "
        "carry an AI Shield High or Critical risk indicator and are recommended for review.",
        _STYLE_BODY,
    ))

    # Monitoring Overview
    story.append(Paragraph("Monitoring Overview", _STYLE_SECTION))
    overview_table = Table([
        ["Metric", "Value"],
        ["Total projects", _fmt_count(report.total_projects)],
        ["Sanctioned amount", _fmt_money(report.total_sanctioned_amount)],
        ["Expenditure", _fmt_money(report.total_expenditure)],
        ["Average financial progress", _fmt_pct(report.average_financial_progress)],
    ], colWidths=[80 * mm, 90 * mm])
    overview_table.setStyle(_TABLE_STYLE)
    story.append(overview_table)

    # Risk & AI Shield Indicators
    story.append(Paragraph("AI Shield Risk Indicators", _STYLE_SECTION))
    if report.risk_level_counts:
        risk_body = [["Risk Level", "Projects"]] + [
            [level.title(), _fmt_count(count)] for level, count in sorted(report.risk_level_counts.items())
        ]
    else:
        risk_body = [["Risk Level", "Projects"], ["Not available", "Not available"]]
    risk_table = Table(risk_body, colWidths=[80 * mm, 90 * mm])
    risk_table.setStyle(_TABLE_STYLE)
    story.append(risk_table)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f"Projects Requiring Review: {_fmt_count(report.projects_requiring_review)}  |  "
        f"Duplicate Indicators: {_fmt_count(report.duplicate_indicators)}  |  "
        f"Anomaly Indicators: {_fmt_count(report.anomaly_indicators)}",
        _STYLE_BODY,
    ))

    # Priority Review Items
    story.append(Paragraph("Priority Review Items", _STYLE_SECTION))
    if report.priority_projects:
        priority_body = [["Work ID", "State", "Category", "Risk Level", "Risk Score"]]
        for p in report.priority_projects:
            priority_body.append([
                p.project_id,
                p.state or "Not available",
                p.work_type or "Not available",
                p.risk_level or "Not available",
                _fmt_count(p.risk_score) if p.risk_score is not None else "Not available",
            ])
        priority_table = Table(priority_body, colWidths=[55 * mm, 30 * mm, 40 * mm, 25 * mm, 20 * mm])
        priority_table.setStyle(_TABLE_STYLE)
        story.append(priority_table)
    else:
        story.append(Paragraph("No High or Critical risk projects found for the selected scope.", _STYLE_BODY))

    # Data Quality / Limitations
    story.append(Paragraph("Data Quality / Limitations", _STYLE_SECTION))
    if report.data_quality_notes:
        for note in report.data_quality_notes:
            story.append(Paragraph(f"- {note}", _STYLE_NOTE))
    else:
        story.append(Paragraph("No data limitations identified for this scope.", _STYLE_NOTE))

    # Disclaimer
    story.append(Paragraph("Disclaimer", _STYLE_SECTION))
    story.append(Paragraph(report.disclaimer, _STYLE_NOTE))
    story.append(Paragraph(_APP_DISCLAIMER, _STYLE_NOTE))

    doc.build(story)
    return buffer.getvalue()


def _pdf_response(report: ReportOut) -> Response:
    filename = f"mplads-ai-shield-{report.report_type}-{report.generated_at.strftime('%Y%m%d-%H%M%S')}.pdf"
    return Response(
        content=_report_pdf_bytes(report),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _project_pdf_bytes(project: Project) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=18 * mm, bottomMargin=16 * mm, leftMargin=16 * mm, rightMargin=16 * mm,
    )

    generated_at = datetime.now(timezone.utc)
    story = _pdf_header_flowables(f"Project Report - {project.project_id}", generated_at, project.state or "Not available")

    story.append(Paragraph("Project Details", _STYLE_SECTION))
    details_table = Table([
        ["Field", "Value"],
        ["Work ID", project.project_id],
        ["State", project.state or "Not available"],
        ["District", project.district or "Not available"],
        ["Constituency", project.constituency or "Not available"],
        ["Category", project.work_type or "Not available"],
        ["Implementing Agency", project.implementing_agency or "Not available"],
        ["Status", project.status or "Not available"],
        ["Sanctioned Amount", _fmt_money(project.sanctioned_amount)],
        ["Expenditure", _fmt_money(project.expenditure)],
        ["Financial Progress", _fmt_pct(project.financial_progress)],
    ], colWidths=[55 * mm, 115 * mm])
    details_table.setStyle(_TABLE_STYLE)
    story.append(details_table)

    story.append(Paragraph("AI Shield Risk Indicators", _STYLE_SECTION))
    if project.risk_level:
        risk_table = Table([
            ["Field", "Value"],
            ["Risk Level", project.risk_level],
            ["Risk Score", _fmt_count(project.risk_score) if project.risk_score is not None else "Not available"],
        ], colWidths=[55 * mm, 115 * mm])
        risk_table.setStyle(_TABLE_STYLE)
        story.append(risk_table)
        reasons = [r for r in (project.risk_reason_1, project.risk_reason_2, project.risk_reason_3) if r]
        if reasons:
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph("Review Priority Notes:", _STYLE_BODY))
            for reason in reasons:
                story.append(Paragraph(f"- {reason}", _STYLE_NOTE))
    else:
        story.append(Paragraph("AI Shield risk scoring is not available for this project.", _STYLE_BODY))

    story.append(Paragraph("Disclaimer", _STYLE_SECTION))
    story.append(Paragraph(
        "AI Shield identifies indicators that may require review. It does not "
        "establish fraud, wrongdoing, or non-compliance.",
        _STYLE_NOTE,
    ))
    story.append(Paragraph(_APP_DISCLAIMER, _STYLE_NOTE))

    doc.build(story)
    return buffer.getvalue()


# --- Routes ----------------------------------------------------------------

@router.get("/generate")
def generate_report(
    report_type: str = Query(..., description="One of: " + ", ".join(REPORT_TYPES)),
    format: str = Query("json", description="One of: " + ", ".join(EXPORT_FORMATS)),
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    constituency: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a report for the authenticated caller's authorized scope.

    format=json returns the ReportOut payload used to render the
    on-screen preview; format=csv/pdf return an actual downloadable
    file built from the same filtered query.
    """
    _require_ministry(current_user)

    if format not in EXPORT_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported export format '{format}'.")

    report = _build_report(db, report_type, state, district, constituency, category, risk_level, date_from, date_to)

    if format == "csv":
        return _csv_response(db, report, state, district, constituency, category, risk_level, date_from, date_to)
    if format == "pdf":
        return _pdf_response(report)
    return report


@router.get("/project/{project_id:path}")
def generate_project_report(
    project_id: str,
    format: str = Query("pdf", description="One of: json, pdf"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Single-project report -- available to any authenticated user,
    exactly like GET /projects/{id} itself is not role-gated."""

    if format not in ("json", "pdf"):
        raise HTTPException(status_code=400, detail=f"Unsupported export format '{format}'.")

    project = db.query(Project).filter(Project.project_id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    if format == "json":
        return _row_from_project(project)

    filename = f"mplads-ai-shield-project-{_safe_filename_part(project.project_id)}.pdf"
    return Response(
        content=_project_pdf_bytes(project),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )