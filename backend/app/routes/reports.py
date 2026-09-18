"""
Phase 8 -- Reports & Export.

Two data sources, same split the rest of the app uses (see
app/aggregations.py and app/routes/dashboard.py):

    canonical_projects.csv  -- the authoritative 43,863-project universe
    project_risk_scores.csv -- the authoritative CURRENT Risk Fusion output

    Project (DB table)      -- legacy/Phase-2 metadata (state, district,
                                sanctioned amount, ...), used because
                                ReportProjectRow/the CSV export mirror the
                                Project model's columns. Its own
                                risk_score/risk_level/risk_reason_1..3/
                                duplicate_risk_score/anomaly_risk_score
                                columns are legacy Phase-2 fields that the
                                current pipeline intentionally leaves NULL
                                (see app/routes/projects.py) -- every risk
                                figure in this file is therefore looked up
                                from project_risk_scores.csv and overlaid
                                onto the Project-sourced row, never read
                                from those DB columns.

Report types (REPORT_TYPES below) are deliberately limited to what can
actually be built from real, existing data:
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
role-gated. It sources project details and the full Risk Fusion +
Explainable AI breakdown the same way GET /projects/{id} and
GET /projects/{id}/risk do (by calling those route functions directly),
so the PDF always matches what the Project Details page shows on
screen -- one code path, one set of numbers.
"""

import csv
import io
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from xml.sax.saxutils import escape as _xml_escape

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
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

from app.aggregations import (
    compute_risk_level_counts_from_risk_fusion,
    load_risk_fusion,
)
from app.auth import get_current_user
from app.database import get_db
from app.models import Project, User
from app.routes.projects import get_project, get_project_risk
from app.schemas import ReportOut, ReportProjectRow, ReportsMeta, ReportTypeInfo, RiskFusionOut

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


def _load_risk_df() -> Optional[pd.DataFrame]:
    """Load the current Risk Fusion output, or None if it isn't available.

    A report must still be generatable (with honest data-quality notes)
    when the Risk Fusion CSV is missing or malformed -- it should degrade,
    never 500.
    """
    try:
        return load_risk_fusion()
    except (FileNotFoundError, ValueError):
        return None


def _apply_filters(
    query,
    state: Optional[str],
    district: Optional[str],
    constituency: Optional[str],
    category: Optional[str],
    date_from: Optional[date],
    date_to: Optional[date],
):
    """Location/category/date filters only. Risk-level filtering is handled
    separately by _scope_query, because it depends on project_risk_scores.csv
    (the Project DB row's own risk_level column is a legacy Phase-2 field the
    current pipeline never populates -- filtering on it directly would always
    return zero rows)."""
    if state:
        query = query.filter(Project.state == state)
    if district:
        query = query.filter(Project.district == district)
    if constituency:
        query = query.filter(Project.constituency == constituency)
    if category:
        query = query.filter(Project.work_type == category)
    if date_from:
        query = query.filter(Project.sanction_date >= date_from)
    if date_to:
        query = query.filter(Project.sanction_date <= date_to)
    return query


def _scope_query(
    db: Session,
    risk_df: Optional[pd.DataFrame],
    state: Optional[str],
    district: Optional[str],
    constituency: Optional[str],
    category: Optional[str],
    risk_level: Optional[str],
    date_from: Optional[date],
    date_to: Optional[date],
):
    """The full filtered Project query, including risk_level -- resolved
    against the CURRENT Risk Fusion output rather than the unpopulated
    legacy Project.risk_level DB column.

    NOTE: for a low-selectivity risk level (e.g. LOW, which is most of the
    43,863-project universe) this issues a large SQL IN(...) clause. That is
    an accepted, documented trade-off here -- report generation is an
    occasional, not high-QPS, operation -- rather than a bigger change to
    query the canonical/risk CSVs as the base project universe as
    app/routes/dashboard.py already does for the Dashboard.
    """
    query = _apply_filters(db.query(Project), state, district, constituency, category, date_from, date_to)

    if not risk_level:
        return query

    normalized = risk_level.upper().strip()

    if risk_df is None:
        # No Risk Fusion data at all -- an explicit risk_level filter can
        # never legitimately match anything, so return definitively empty
        # rather than silently ignoring the filter and returning everything.
        return query.filter(Project.project_id.is_(None))

    matching_ids = (
        risk_df.loc[
            risk_df["risk_level"].astype(str).str.upper().str.strip() == normalized,
            "work_id",
        ]
        .astype(str)
        .str.strip()
        .tolist()
    )
    return query.filter(Project.project_id.in_(matching_ids))


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


def _numeric_to_decimal(value: Any) -> Optional[Decimal]:
    """pandas/numpy scalar -> Decimal, without letting a numpy dtype leak
    into a Pydantic Decimal field. None/NaN both map to None -- never 0."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        return Decimal(str(float(value)))
    except (TypeError, ValueError):
        return None


def _risk_overlay_for_row(risk_row: Optional[pd.Series]) -> dict:
    """The three risk fields a ReportProjectRow / CSV row carries, taken
    from one row of project_risk_scores.csv. None/empty when there is no
    Risk Fusion row for this project -- never fabricated."""

    if risk_row is None:
        return {"risk_level": None, "risk_score": None, "risk_reasons": []}

    level = risk_row.get("risk_level")

    reasons = [risk_row.get("top_reason_1"), risk_row.get("top_reason_2"), risk_row.get("top_reason_3")]
    reasons = [r for r in reasons if isinstance(r, str) and r.strip()]

    return {
        "risk_level": str(level).upper().strip() if isinstance(level, str) and level.strip() else None,
        "risk_score": _numeric_to_decimal(risk_row.get("risk_score")),
        "risk_reasons": reasons,
    }


def _row_from_project(project: Project, risk_row: Optional[pd.Series] = None) -> ReportProjectRow:
    overlay = _risk_overlay_for_row(risk_row)
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
        **overlay,
    )


def _build_report(
    db: Session,
    risk_df: Optional[pd.DataFrame],
    report_type: str,
    state, district, constituency, category, risk_level, date_from, date_to,
) -> ReportOut:
    if report_type not in REPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported report type '{report_type}'.")

    base_query = _scope_query(db, risk_df, state, district, constituency, category, risk_level, date_from, date_to)

    total_projects, total_sanctioned, total_expenditure, avg_financial_progress = base_query.with_entities(
        func.count(Project.project_id),
        func.coalesce(func.sum(Project.sanctioned_amount), 0),
        func.coalesce(func.sum(Project.expenditure), 0),
        func.avg(Project.financial_progress),
    ).one()

    # --- Risk indicators, from project_risk_scores.csv, scoped to exactly
    # the project IDs the filters above matched -----------------------------
    scoped_risk: Optional[pd.DataFrame]

    if risk_df is None:
        scoped_risk = None
    else:
        scoped_ids = {pid for (pid,) in base_query.with_entities(Project.project_id).all()}
        scoped_risk = (
            risk_df[risk_df["work_id"].astype(str).str.strip().isin(scoped_ids)]
            if scoped_ids
            else risk_df.iloc[0:0]
        )

    if scoped_risk is not None and not scoped_risk.empty:
        risk_level_counts = compute_risk_level_counts_from_risk_fusion(scoped_risk)

        levels_upper = scoped_risk["risk_level"].astype(str).str.upper().str.strip()
        projects_requiring_review = int(levels_upper.isin(RISK_REVIEW_LEVELS).sum())

        duplicate_indicators = int(
            scoped_risk.get("has_duplicate_signal", pd.Series(False, index=scoped_risk.index)).fillna(False).sum()
        )
        anomaly_indicators = int(
            (
                scoped_risk.get("has_financial_anomaly", pd.Series(False, index=scoped_risk.index)).fillna(False)
                | scoped_risk.get("has_timeline_anomaly", pd.Series(False, index=scoped_risk.index)).fillna(False)
                | scoped_risk.get(
                    "has_isolation_forest_signal", pd.Series(False, index=scoped_risk.index)
                ).fillna(False)
            ).sum()
        )
    else:
        risk_level_counts = {}
        projects_requiring_review = 0
        duplicate_indicators = 0
        anomaly_indicators = 0

    # --- Priority Review Items: real HIGH/CRITICAL Risk Fusion projects in
    # scope, ordered by real risk_score -- not the unpopulated legacy
    # Project.risk_score column. ---------------------------------------------
    priority_rows: list[ReportProjectRow] = []

    if scoped_risk is not None and not scoped_risk.empty:
        priority_risk = scoped_risk[
            scoped_risk["risk_level"].astype(str).str.upper().str.strip().isin(RISK_REVIEW_LEVELS)
        ].copy()

        priority_risk["risk_score_numeric"] = pd.to_numeric(priority_risk["risk_score"], errors="coerce").fillna(0)
        priority_risk = priority_risk.sort_values(
            by=["risk_score_numeric", "work_id"], ascending=[False, True]
        ).head(PRIORITY_LIST_LIMIT)

        priority_ids = priority_risk["work_id"].astype(str).str.strip().tolist()

        projects_by_id = {
            p.project_id: p
            for p in db.query(Project).filter(Project.project_id.in_(priority_ids)).all()
        }
        risk_rows_by_id = {str(row["work_id"]).strip(): row for _, row in priority_risk.iterrows()}

        for work_id in priority_ids:
            project = projects_by_id.get(work_id)
            if project is None:
                # This work ID is a real HIGH/CRITICAL Risk Fusion project,
                # but has no matching Project DB row, so it cannot be
                # represented as a ReportProjectRow (which mirrors the
                # Project model's columns). Skipped, not fabricated -- see
                # the data-quality note below.
                continue
            priority_rows.append(_row_from_project(project, risk_rows_by_id.get(work_id)))

    data_quality_notes = []
    if total_projects == 0:
        data_quality_notes.append("No projects matched the selected scope and filters.")
    if risk_df is None:
        data_quality_notes.append(
            "AI Shield Risk Fusion output is not available; risk indicators could not be computed for this report."
        )
    elif not risk_level_counts:
        data_quality_notes.append("AI Shield risk scoring is not available for the selected scope.")
    if scoped_risk is not None and len(scoped_risk) < total_projects:
        data_quality_notes.append(
            f"{total_projects - len(scoped_risk)} project(s) in scope have no matching Risk Fusion "
            "record and are excluded from the risk indicators above."
        )
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
        priority_projects=priority_rows,
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


def _row_to_csv_cells(project: Project, risk_row: Optional[pd.Series] = None) -> list:
    overlay = _risk_overlay_for_row(risk_row)
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
        overlay["risk_level"] or "",
        _decimal_cell(overlay["risk_score"]),
        " | ".join(overlay["risk_reasons"]),
    ]


def _safe_filename_part(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in value)


def _csv_response(
    db: Session,
    risk_df: Optional[pd.DataFrame],
    report: ReportOut,
    state, district, constituency, category, risk_level, date_from, date_to,
) -> StreamingResponse:
    # The MAX_EXPORT_ROWS slice is still taken by Work ID at the SQL level
    # (as before -- this file never fabricates a full-dataset sort by risk
    # for cost reasons); what changes is that the risk fields for each row
    # in that slice, and its ordering WITHIN the slice, now reflect the
    # actual Risk Fusion output instead of the always-empty legacy column.
    rows = (
        _scope_query(db, risk_df, state, district, constituency, category, risk_level, date_from, date_to)
        .order_by(Project.project_id)
        .limit(MAX_EXPORT_ROWS)
        .all()
    )

    risk_map: dict[str, pd.Series] = {}
    if risk_df is not None and rows:
        ids = {p.project_id for p in rows}
        subset = risk_df[risk_df["work_id"].astype(str).str.strip().isin(ids)]
        risk_map = {str(row["work_id"]).strip(): row for _, row in subset.iterrows()}

    def _sort_key(project: Project):
        risk_row = risk_map.get(project.project_id)
        score = pd.to_numeric(risk_row["risk_score"], errors="coerce") if risk_row is not None else None
        has_score = score is not None and not pd.isna(score)
        # Highest score first; rows with no Risk Fusion match sort last.
        return (0 if has_score else 1, -float(score) if has_score else 0.0, project.project_id)

    rows = sorted(rows, key=_sort_key)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADER)
    for project in rows:
        writer.writerow(_row_to_csv_cells(project, risk_map.get(project.project_id)))
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
GOOD = colors.HexColor("#1B8A5A")
WARN = colors.HexColor("#B7791F")
BAD = colors.HexColor("#C0392B")

_styles = getSampleStyleSheet()
_STYLE_TITLE = ParagraphStyle("MpladsTitle", parent=_styles["Heading1"], fontSize=15, textColor=NAVY, spaceAfter=2)
_STYLE_SUBTITLE = ParagraphStyle("MpladsSubtitle", parent=_styles["Normal"], fontSize=10, textColor=MUTED, spaceAfter=10)
_STYLE_META = ParagraphStyle("MpladsMeta", parent=_styles["Normal"], fontSize=8.5, textColor=MUTED, spaceAfter=2)
_STYLE_SECTION = ParagraphStyle("MpladsSection", parent=_styles["Heading2"], fontSize=11.5, textColor=SECONDARY_NAVY, spaceBefore=12, spaceAfter=5)
_STYLE_SUBSECTION = ParagraphStyle("MpladsSubsection", parent=_styles["Normal"], fontSize=9.5, textColor=NAVY, spaceBefore=6, spaceAfter=2, fontName="Helvetica-Bold")
_STYLE_BODY = ParagraphStyle("MpladsBody", parent=_styles["Normal"], fontSize=9, leading=13, textColor=colors.HexColor("#16232E"))
_STYLE_NOTE = ParagraphStyle("MpladsNote", parent=_styles["Normal"], fontSize=8, leading=11, textColor=MUTED)
_STYLE_REASON = ParagraphStyle("MpladsReason", parent=_styles["Normal"], fontSize=8.5, leading=12, textColor=colors.HexColor("#16232E"), leftIndent=8, spaceAfter=1.5)

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

# Same component display order as the frontend's COMPONENT_ORDER
# (src/lib/riskModel.js) -- highest configured weight first.
_COMPONENT_ORDER = [
    "compliance", "financial_anomaly", "timeline_anomaly", "duplicate",
    "payment", "isolation_forest", "data_quality",
]

_STATUS_LABELS = {"HIGH": "HIGH", "MEDIUM": "MEDIUM", "LOW": "LOW", "NONE": "NOT TRIGGERED"}


def _esc(value: Any) -> str:
    """Escape free text before it goes into a reportlab Paragraph, which
    parses a small XML-like markup -- an unescaped '&' (e.g. a state name
    like "Jammu & Kashmir", or an agency name) would otherwise break PDF
    generation. Table cells (plain strings, not Paragraphs) don't need this."""
    if value is None:
        return ""
    return _xml_escape(str(value))


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


def _ordered_components(components: dict) -> list:
    """Components in the same display order the frontend uses, known ones
    first, then anything the frontend doesn't yet know about by name."""
    known = [(name, components[name]) for name in _COMPONENT_ORDER if name in components]
    extra = [(name, detail) for name, detail in components.items() if name not in _COMPONENT_ORDER]
    return known + extra


def _pdf_header_flowables(title: str, generated_at: datetime, scope: str) -> list:
    return [
        Paragraph("MPLADS AI Shield", _STYLE_TITLE),
        Paragraph(_esc(title), _STYLE_SUBTITLE),
        Paragraph(f"Generated: {generated_at.strftime('%d %B %Y, %H:%M UTC')}", _STYLE_META),
        Paragraph(f"Scope: {_esc(scope)}", _STYLE_META),
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
        "carry an AI Shield High or Critical risk indicator, from the current Risk Fusion output, and are "
        "recommended for review.",
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
    story.append(Paragraph(
        "Risk levels and indicators below come from the current Risk Fusion output "
        "(project_risk_scores.csv), scoped to the projects matching this report's filters.",
        _STYLE_NOTE,
    ))
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

        # Top reasons for the highest-priority items -- the same per-project
        # WHY, so the portfolio report doesn't stop at "HIGH" with no context.
        reasoned = [p for p in report.priority_projects if p.risk_reasons][:10]
        if reasoned:
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph("Why flagged (top priority items):", _STYLE_BODY))
            for p in reasoned:
                story.append(Paragraph(f"<b>{_esc(p.project_id)}</b>", _STYLE_REASON))
                for reason in p.risk_reasons[:3]:
                    story.append(Paragraph(f"- {_esc(reason)}", _STYLE_NOTE))
    else:
        story.append(Paragraph("No High or Critical risk projects found for the selected scope.", _STYLE_BODY))

    # Data Quality / Limitations
    story.append(Paragraph("Data Quality / Limitations", _STYLE_SECTION))
    if report.data_quality_notes:
        for note in report.data_quality_notes:
            story.append(Paragraph(f"- {_esc(note)}", _STYLE_NOTE))
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


def _project_pdf_bytes(project, risk: Optional[RiskFusionOut]) -> bytes:
    """Single-project PDF.

    `project` is a ProjectOut (from GET /projects/{id} -- the canonical
    43,863-project universe, risk-overlaid) and `risk` is a RiskFusionOut
    (from GET /projects/{id}/risk) or None if this work ID has no Risk
    Fusion row. Both are built by calling those route functions directly,
    so this PDF can never drift from what the Project Details page shows.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=18 * mm, bottomMargin=16 * mm, leftMargin=16 * mm, rightMargin=16 * mm,
    )

    generated_at = datetime.now(timezone.utc)
    story = _pdf_header_flowables(f"Project Report - {project.project_id}", generated_at, project.state or "Not available")

    # --- Project Details ---------------------------------------------------
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

    # --- Risk Fusion -- Overall Risk ----------------------------------------
    story.append(Paragraph("Risk Fusion \u2014 Overall Risk", _STYLE_SECTION))

    if risk is None:
        story.append(Paragraph(
            "AI Shield Risk Fusion scoring is not available for this project. It may be outside the "
            "currently scored project universe, or the risk dataset may need to be regenerated.",
            _STYLE_BODY,
        ))
    else:
        triggered = [
            (name, detail) for name, detail in _ordered_components(risk.components)
            if (detail.status or "NONE").upper() != "NONE"
        ]
        triggered.sort(key=lambda item: item[1].contribution, reverse=True)

        overall_table = Table([
            ["Field", "Value"],
            ["Risk Score", f"{risk.risk_score:.1f} / 100"],
            ["Risk Level", risk.risk_level],
            ["Evidence Status", risk.evidence_status],
            ["Active Risk Signals", _fmt_count(len(triggered))],
        ], colWidths=[55 * mm, 115 * mm])
        overall_table.setStyle(_TABLE_STYLE)
        story.append(overall_table)
        story.append(Paragraph(
            "This is a review-priority signal. It does not establish fraud or wrongdoing.",
            _STYLE_NOTE,
        ))

        # --- Risk Breakdown & Contribution ---------------------------------
        story.append(Paragraph("Risk Breakdown & Contribution", _STYLE_SECTION))
        if not risk.components:
            story.append(Paragraph(
                "Category contribution data is not available from the current risk response.",
                _STYLE_BODY,
            ))
        else:
            breakdown_body = [["Component", "Raw Score", "Weight", "Contribution", "Status"]]
            total_contribution = 0.0
            for _name, detail in _ordered_components(risk.components):
                total_contribution += detail.contribution
                breakdown_body.append([
                    detail.label,
                    f"{detail.score:.1f}",
                    f"{detail.weight:.0f}%",
                    f"{detail.contribution:.2f}",
                    _STATUS_LABELS.get((detail.status or "NONE").upper(), detail.status or "NOT TRIGGERED"),
                ])
            breakdown_table = Table(breakdown_body, colWidths=[52 * mm, 24 * mm, 20 * mm, 30 * mm, 44 * mm])
            breakdown_table.setStyle(_TABLE_STYLE)
            story.append(breakdown_table)
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(
                f"Sum of contributions: {total_contribution:.2f}  |  Reported score: {risk.risk_score:.2f}",
                _STYLE_NOTE,
            ))

        # --- Why This Project Was Flagged -----------------------------------
        story.append(Paragraph("Why This Project Was Flagged", _STYLE_SECTION))
        if not risk.components:
            story.append(Paragraph(
                "Category contribution data is not available from the current risk response.",
                _STYLE_BODY,
            ))
        elif not triggered:
            story.append(Paragraph(
                "No risk signal triggered for this project across the components that could be evaluated.",
                _STYLE_BODY,
            ))
        else:
            for _name, detail in triggered:
                status_label = _STATUS_LABELS.get((detail.status or "NONE").upper(), detail.status)
                story.append(Paragraph(
                    f"<b>{_esc(detail.label)}</b> \u2014 {status_label} "
                    f"(contribution: {detail.contribution:.2f} pts, {detail.weight:.0f}% weight)",
                    _STYLE_SUBSECTION,
                ))
                if detail.reasons:
                    for reason in detail.reasons:
                        story.append(Paragraph(f"- {_esc(reason)}", _STYLE_REASON))
                else:
                    story.append(Paragraph(
                        "- This component contributed points, but no reason text was recorded for it.",
                        _STYLE_REASON,
                    ))
                if not detail.evidence_available:
                    story.append(Paragraph(
                        "  Structured evidence was not stored in the current processed risk dataset "
                        "for this signal.",
                        _STYLE_NOTE,
                    ))

        # --- Data Quality -----------------------------------------------------
        story.append(Paragraph("Data Quality", _STYLE_SECTION))
        if not risk.data_quality_detail_available:
            story.append(Paragraph(
                "Per-domain data-quality detail was not recorded in the current processed risk dataset.",
                _STYLE_NOTE,
            ))
        elif risk.data_quality_notes:
            story.append(Paragraph(
                "The following evidence domain(s) could not be evaluated for this project:",
                _STYLE_BODY,
            ))
            for note in risk.data_quality_notes:
                story.append(Paragraph(f"- {_esc(note)}", _STYLE_NOTE))
            story.append(Paragraph(
                "The absence of a detected anomaly does not, by itself, mean this project is risk-free.",
                _STYLE_NOTE,
            ))
        else:
            story.append(Paragraph(
                "All evidence domains had sufficient data to be evaluated for this project.",
                _STYLE_BODY,
            ))

        # --- Recommended Review -------------------------------------------
        review_actions: list[str] = []
        seen = set()
        for _name, detail in triggered:
            for action in detail.review_actions:
                if action not in seen:
                    seen.add(action)
                    review_actions.append(action)

        if review_actions:
            story.append(Paragraph("Recommended Review", _STYLE_SECTION))
            for index, action in enumerate(review_actions, start=1):
                story.append(Paragraph(f"{index}. {_esc(action)}", _STYLE_REASON))
            story.append(Paragraph(
                "These are review suggestions, not automated conclusions.",
                _STYLE_NOTE,
            ))

    # --- Disclaimer ----------------------------------------------------------
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

    # Loaded once per request and threaded through, rather than re-read by
    # both _build_report and _csv_response.
    risk_df = _load_risk_df()

    report = _build_report(db, risk_df, report_type, state, district, constituency, category, risk_level, date_from, date_to)

    if format == "csv":
        return _csv_response(db, risk_df, report, state, district, constituency, category, risk_level, date_from, date_to)
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
    exactly like GET /projects/{id} itself is not role-gated.

    Sources project details from the canonical project universe and the
    full Risk Fusion + Explainable AI breakdown from the current Risk
    Fusion output, by calling GET /projects/{id} and GET /projects/{id}/risk
    directly -- the same data the Project Details page renders, so the
    report can never disagree with what the officer sees on screen.
    """

    if format not in ("json", "pdf"):
        raise HTTPException(status_code=400, detail=f"Unsupported export format '{format}'.")

    # Raises 404 if the work ID isn't in the canonical universe, 503 if the
    # canonical/risk datasets themselves are unavailable -- both correct to
    # propagate as-is.
    project = get_project(project_id, db)

    # A project can legitimately have no Risk Fusion row; that's reported
    # honestly in the PDF rather than treated as an error for the whole
    # report. Any other failure (e.g. the risk dataset itself missing) is
    # a real error and is allowed to propagate.
    risk: Optional[RiskFusionOut] = None
    try:
        risk = get_project_risk(project_id, db)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_404_NOT_FOUND:
            raise

    if format == "json":
        return {
            "project": project.model_dump(),
            "risk": risk.model_dump() if risk is not None else None,
        }

    filename = f"mplads-ai-shield-project-{_safe_filename_part(project.project_id)}.pdf"
    return Response(
        content=_project_pdf_bytes(project, risk),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )