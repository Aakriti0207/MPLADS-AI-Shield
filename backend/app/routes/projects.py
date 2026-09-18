"""
Routes for the projects resource.

Current architecture:

    canonical_projects.csv
            +
    project_risk_scores.csv
            ↓
        Project API

The canonical CSV is the authoritative project universe for the
current ML/Risk Fusion system.

The Project database is still used when a matching DB record exists,
but the API no longer limits the project universe to the incomplete
database table.

Current canonical universe:
    43,863 projects

Current Risk Fusion universe:
    43,863 projects

The API deliberately keeps ProjectOut's legacy Phase-2 fields for
frontend compatibility. Current AI risk is available through:

    GET /projects/{project_id}/risk

and comes from the current Risk Fusion output.

RBAC
----
Every read in this module is scoped SERVER-SIDE before anything is
returned. The authorized project universe is derived from the
authenticated user (app/rbac.py's `get_scope`), never from a
state/district/constituency value the client sent -- a client filter
can only narrow what the user is already entitled to, and a filter
naming someone else's jurisdiction is refused outright.

Single-project reads (GET /projects/{id} and GET /projects/{id}/risk)
apply the same check, so a caller cannot reach an out-of-scope project
by typing its ID into the URL or by skipping the list endpoint and
calling the risk endpoint directly. An out-of-scope ID returns the
same 404 as a non-existent one, so 403-vs-404 can't be used to probe
which work IDs are real.
"""

from datetime import date
from decimal import Decimal
from typing import Any, List

import pandas as pd

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models import Project
from app.schemas import (
    ProjectFilterOptions,
    ProjectOut,
    ProjectPage,
    RiskFusionOut,
    ScopeInfo,
)

from app.rbac import (
    UserScope,
    get_scope,
    narrow_within_scope,
    project_not_found,
    scope_canonical,
    scope_frames,
)

from app.aggregations import (
    load_canonical_projects,
    load_risk_fusion,
)

from ml.risk_config import (
    COMPONENT_LABELS,
    RISK_COMPONENT_CAPS,
    component_description,
    component_review_actions,
)


# =====================================================================
# Router
# =====================================================================

# ---------------------------------------------------------------------
# Legacy-CSV fallback for component_breakdown
# ---------------------------------------------------------------------
#
# ``component_breakdown`` / ``data_quality_notes`` are columns added to
# project_risk_scores.csv by the current ml/risk.py. A processed CSV
# generated BEFORE those columns existed is still perfectly valid input --
# it just does not carry the per-component regrouping.
#
# Rather than degrade to "category contribution data is not available"
# (which is what erased the WHY FLAGGED panel), this rebuilds the same
# structure from columns the legacy CSV DOES carry:
#
#   *_contribution        -> the component's real points
#   risk_reasons          -> the ordered reason texts
#   source_signal_summary -> the per-signal source / severity_tier / points
#
# ml/risk.py writes risk_reasons and source_signal_summary from the SAME
# sorted rows, index for index, so signal i belongs to reason i. Nothing is
# recomputed and nothing is invented: the numbers are the backend's own.
#
# The one thing a legacy CSV genuinely cannot provide is the structured
# per-signal `evidence` dict. That is reported honestly via
# ``evidence_available: False`` rather than filled with placeholder values;
# re-running ``python -m ml.risk`` restores full evidence.

SOURCE_ORDER_TO_CONTRIBUTION_COLUMN = {
    "compliance": "compliance_contribution",
    "financial_anomaly": "financial_anomaly_contribution",
    "timeline_anomaly": "timeline_anomaly_contribution",
    "duplicate": "duplicate_contribution",
    "data_quality": "data_quality_contribution",
    "payment": "payment_contribution",
    "isolation_forest": "isolation_forest_contribution",
}

SEVERITY_TIER_TO_STATUS = {3: "HIGH", 2: "MEDIUM", 1: "LOW"}


def _loads(value: Any) -> Any:
    """Parse a JSON cell, tolerating NaN / empty / already-parsed values."""

    if value is None or isinstance(value, (list, dict)):
        return value

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    text = str(value).strip()

    if not text:
        return None

    try:
        import json as _json

        return _json.loads(text)

    except Exception:
        return None


def build_component_breakdown_from_legacy(
    row: Any,
) -> dict[str, Any]:
    """Rebuild the per-component breakdown from legacy risk CSV columns."""

    reasons = _loads(
        row.get("risk_reasons")
    )

    if not isinstance(reasons, list):
        reasons = []

    summary = _loads(
        row.get("source_signal_summary")
    )

    signals = (
        summary.get("signals")
        if isinstance(summary, dict)
        else None
    )

    if not isinstance(signals, list):
        signals = []

    grouped: dict[str, list[dict[str, Any]]] = {}

    for index, signal in enumerate(signals):

        if not isinstance(signal, dict):
            continue

        source = str(
            signal.get("source")
            or ""
        )

        if source not in SOURCE_ORDER_TO_CONTRIBUTION_COLUMN:
            continue

        grouped.setdefault(source, []).append(
            {
                "text": (
                    reasons[index]
                    if index < len(reasons)
                    else None
                ),
                "severity_tier": signal.get("severity_tier"),
                "points": signal.get("points"),
            }
        )

    components: dict[str, Any] = {}

    for name, cap in RISK_COMPONENT_CAPS.items():

        contribution = pd.to_numeric(
            row.get(
                SOURCE_ORDER_TO_CONTRIBUTION_COLUMN[name]
            ),
            errors="coerce",
        )

        contribution = (
            0.0
            if pd.isna(contribution)
            else float(contribution)
        )

        entries = grouped.get(name, [])

        reason_texts = [
            entry["text"]
            for entry in entries
            if entry["text"]
        ]

        tiers = [
            int(entry["severity_tier"])
            for entry in entries
            if entry.get("severity_tier") is not None
        ]

        status = (
            SEVERITY_TIER_TO_STATUS.get(max(tiers), "LOW")
            if tiers
            else "NONE"
        )

        components[name] = {
            "label": COMPONENT_LABELS[name],
            # Same definition ml/risk.py uses: the component's own 0-100
            # fill, so score * weight / 100 == contribution exactly.
            "score": (
                round(contribution / cap * 100, 1)
                if cap > 0
                else 0.0
            ),
            "weight": cap,
            "contribution": round(contribution, 2),
            "status": status,
            "reasons": reason_texts,
            # Legacy CSVs carry no structured evidence -- say so, never
            # substitute placeholder numbers.
            "evidence": [],
            "evidence_available": False,
        }

    return components


def enrich_component_details(
    components: dict[str, Any],
) -> dict[str, Any]:
    """Attach presentational XAI metadata to each parsed component.

    ``component_breakdown`` in the risk CSV carries only the numbers and the
    real evidence (score / weight / contribution / status / reasons /
    evidence). The human-facing prose -- what the detector measures, and what
    a reviewer should inspect for that CATEGORY of signal -- is owned by
    ml/risk_config.py and attached here at serialization time.

    This deliberately adds NOTHING numeric and never touches an existing key,
    so the frontend still reconciles against exactly the backend's own
    score / weight / contribution values.
    """

    enriched: dict[str, Any] = {}

    for name, detail in components.items():

        if not isinstance(detail, dict):
            continue

        merged = dict(detail)

        merged.setdefault(
            "description",
            component_description(name),
        )

        merged.setdefault(
            "review_actions",
            component_review_actions(name),
        )

        merged.setdefault(
            "evidence_available",
            True,
        )

        enriched[name] = merged

    return enriched


router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    dependencies=[Depends(get_current_user)],
)


# =====================================================================
# Pagination
# =====================================================================

DEFAULT_LIMIT = 50
MAX_LIMIT = 300


# =====================================================================
# Data loading helpers
# =====================================================================

def _load_project_datasets():
    """
    Load the canonical project universe and current Risk Fusion output.

    Both must describe exactly the same work_id universe.
    """

    try:

        canonical_df = (
            load_canonical_projects()
        )

        risk_df = (
            load_risk_fusion()
        )

    except (
        FileNotFoundError,
        ValueError,
    ) as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )

    canonical_ids = set(
        canonical_df["work_id"]
    )

    risk_ids = set(
        risk_df["work_id"]
    )

    if canonical_ids != risk_ids:

        missing_risk = canonical_ids - risk_ids
        extra_risk = risk_ids - canonical_ids

        raise HTTPException(
            status_code=503,
            detail=(
                "Canonical and Risk Fusion project universes "
                "do not match. "
                f"Canonical={len(canonical_ids)}, "
                f"RiskFusion={len(risk_ids)}, "
                f"missing_risk={len(missing_risk)}, "
                f"extra_risk={len(extra_risk)}."
            ),
        )

    return canonical_df, risk_df


# =====================================================================
# Data conversion helpers
# =====================================================================

def _clean_string(
    value: Any,
) -> str | None:
    """
    Convert a value into a nullable string.
    """

    if value is None:
        return None

    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value or value.lower() == "nan":
        return None

    return value


def _decimal(
    value: Any,
) -> Decimal | None:
    """
    Convert a numeric value to Decimal safely.
    """

    if value is None:
        return None

    if pd.isna(value):
        return None

    try:
        return Decimal(
            str(value)
        )
    except Exception:
        return None


def _date(
    value: Any,
) -> date | None:
    """
    Convert a canonical date value into a Python date.
    """

    if value is None:
        return None

    if pd.isna(value):
        return None

    try:

        parsed = pd.to_datetime(
            value,
            errors="coerce",
        )

        if pd.isna(parsed):
            return None

        return parsed.date()

    except Exception:

        return None


# =====================================================================
# Canonical → ProjectOut
# =====================================================================

def _canonical_row_to_project(
    row: pd.Series,
) -> ProjectOut:
    """
    Convert one canonical CSV row into the existing ProjectOut API
    contract.

    Fields that are not available in canonical_projects.csv remain
    None rather than being fabricated.

    Legacy Phase-2 risk fields are populated only when they are actually
    present in the Risk Fusion output or canonical source. Current
    Risk Fusion should be consumed through /risk.
    """

    project_id = _clean_string(
        row.get("work_id")
    )

    if not project_id:
        raise ValueError(
            "Canonical project row has no work_id."
        )

    sanctioned_amount = _decimal(
        row.get("sanction_amount")
    )

    expenditure = _decimal(
        row.get("total_expenditure")
    )

    # ---------------------------------------------------------------
    # Calculate financial progress from canonical financial data.
    #
    # This is the same definition used by Dashboard/Analytics.
    # ---------------------------------------------------------------

    financial_progress = None

    if (
        sanctioned_amount is not None
        and sanctioned_amount > 0
        and expenditure is not None
    ):

        financial_progress = (
            expenditure
            / sanctioned_amount
            * Decimal("100")
        )

    # ---------------------------------------------------------------
    # Build response.
    # ---------------------------------------------------------------

    return ProjectOut(
        project_id=project_id,

        state=_clean_string(
            row.get("state")
        ),

        district=_clean_string(
            row.get("district")
        ),

        constituency=_clean_string(
            row.get("constituency")
        ),

        mp_name=_clean_string(
            row.get("mp")
        ),

        work_type=_clean_string(
            row.get("work_category")
        ),

        implementing_agency=_clean_string(
            row.get("implementing_agency")
        ),

        sanctioned_amount=sanctioned_amount,

        # canonical_projects.csv does not contain estimated_cost.
        estimated_cost=None,

        expenditure=expenditure,

        financial_progress=financial_progress,

        # Not available in canonical source.
        physical_progress=None,

        sanction_date=_date(
            row.get("sanction_date")
        ),

        # canonical source has no explicit start_date.
        start_date=None,

        # canonical source has completion_date, but no expected
        # completion date.
        expected_completion=None,

        actual_completion=_date(
            row.get("completion_date")
        ),

        # Geographic coordinates are not present in canonical data.
        latitude=None,
        longitude=None,

        status=_clean_string(
            row.get("status")
        ),

        # -----------------------------------------------------------
        # Legacy Phase-2 risk fields.
        #
        # These are intentionally not fabricated from current Risk
        # Fusion. The current risk contract is /risk.
        # -----------------------------------------------------------

        risk_score=None,
        risk_level=None,

        financial_risk_score=None,
        payment_risk_score=None,
        execution_risk_score=None,
        peer_anomaly_score=None,
        isolation_forest_score=None,
        anomaly_risk_score=None,
        duplicate_risk_score=None,

        raw_max_similarity=None,
        most_similar_work_id=None,

        risk_reason_1=None,
        risk_reason_2=None,
        risk_reason_3=None,

        risk_metadata=None,

        # These do not exist in canonical_projects.csv.
        created_at=None,
        updated_at=None,
    )


# =====================================================================
# Risk Fusion map
# =====================================================================

def _risk_map(
    risk_df: pd.DataFrame,
) -> dict[str, dict[str, Any]]:
    """
    Create a work_id → Risk Fusion row mapping.
    """

    result = {}

    for _, row in risk_df.iterrows():

        work_id = _clean_string(
            row.get("work_id")
        )

        if not work_id:
            continue

        result[work_id] = (
            row.to_dict()
        )

    return result


# =====================================================================
# Apply current Risk Fusion to ProjectOut
# =====================================================================

def _apply_risk_to_project(
    project: ProjectOut,
    risk_row: dict[str, Any] | None,
) -> ProjectOut:
    """
    Overlay the current Risk Fusion score/level on ProjectOut.

    This is response-only. Nothing is written back to the DB.
    """

    if not risk_row:
        return project

    risk_score = _decimal(
        risk_row.get("risk_score")
    )

    risk_level = _clean_string(
        risk_row.get("risk_level")
    )

    return project.model_copy(
        update={
            "risk_score": risk_score,
            "risk_level": (
                risk_level.upper()
                if risk_level
                else None
            ),
        }
    )


# =====================================================================
# Filtering
# =====================================================================

def _apply_canonical_filters(
    df: pd.DataFrame,
    state: str | None,
    category: str | None,
    status_value: str | None,
    search: str | None,
    district: str | None = None,
    constituency: str | None = None,
) -> pd.DataFrame:
    """
    Apply project filters directly to the canonical dataset.

    IMPORTANT: this runs on a frame that has ALREADY been reduced to the
    caller's authorized scope. These filters therefore only ever narrow
    further -- they cannot be used to reach a record the scope excluded.
    """

    result = df.copy()

    # ---------------------------------------------------------------
    # District / constituency
    # ---------------------------------------------------------------

    for column, value in (("district", district), ("constituency", constituency)):

        if not value:
            continue

        if column not in result.columns:
            continue

        result = result[
            result[column]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.casefold()
            == value.strip().casefold()
        ]

    # ---------------------------------------------------------------
    # State
    # ---------------------------------------------------------------

    if state:

        result = result[
            result["state"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.casefold()
            == state.strip().casefold()
        ]

    # ---------------------------------------------------------------
    # Work category
    # ---------------------------------------------------------------

    if category:

        result = result[
            result["work_category"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.casefold()
            == category.strip().casefold()
        ]

    # ---------------------------------------------------------------
    # Status
    # ---------------------------------------------------------------

    if status_value:

        result = result[
            result["status"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.casefold()
            == status_value.strip().casefold()
        ]

    # ---------------------------------------------------------------
    # Search
    # ---------------------------------------------------------------

    if search:

        pattern = (
            search
            .strip()
            .casefold()
        )

        searchable_columns = [
            "work_id",
            "state",
            "district",
            "constituency",
            "work_category",
            "mp",
            "implementing_agency",
            "work_description",
        ]

        mask = pd.Series(
            False,
            index=result.index,
        )

        for column in searchable_columns:

            if column not in result.columns:
                continue

            mask = (
                mask
                | result[column]
                .fillna("")
                .astype(str)
                .str.casefold()
                .str.contains(
                    pattern,
                    regex=False,
                )
            )

        result = result[mask]

    return result


# =====================================================================
# GET /projects
# =====================================================================

@router.get(
    "",
    response_model=List[ProjectOut],
)
def list_projects(
    skip: int = Query(
        0,
        ge=0,
        description="Number of projects to skip.",
    ),
    limit: int = Query(
        DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=(
            f"Maximum projects returned "
            f"in one page (1-{MAX_LIMIT})."
        ),
    ),
    db: Session = Depends(get_db),
    scope: UserScope = Depends(get_scope),
):
    """
    Return a page from the canonical project universe, reduced to the
    records the authenticated caller is authorized for.

    Ministry/Admin sees the full 43,863-project universe exactly as
    before. A State Nodal / District Authority / MP account sees only
    its own jurisdiction, and an account with no jurisdiction assigned
    sees an empty page -- the scope is applied to the QUERY, not to the
    rendering.

    Risk score and risk level are overlaid from current Risk Fusion --
    the same values every role receives for the same project.
    """

    canonical_df, risk_df = (
        _load_project_datasets()
    )

    canonical_df, risk_df = scope_frames(
        canonical_df,
        risk_df,
        scope,
    )

    risk_lookup = _risk_map(
        risk_df
    )

    # Stable deterministic ordering.
    canonical_df = (
        canonical_df
        .sort_values(
            "work_id"
        )
    )

    page_df = (
        canonical_df
        .iloc[
            skip: skip + limit
        ]
    )

    results = []

    for _, row in page_df.iterrows():

        project = (
            _canonical_row_to_project(
                row
            )
        )

        project = (
            _apply_risk_to_project(
                project,
                risk_lookup.get(
                    project.project_id
                ),
            )
        )

        results.append(project)

    return results


# =====================================================================
# GET /projects/query
# =====================================================================

@router.get(
    "/query",
    response_model=ProjectPage,
)
def query_projects(
    skip: int = Query(
        0,
        ge=0,
        description="Number of projects to skip.",
    ),
    limit: int = Query(
        DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=(
            f"Maximum projects returned "
            f"in one page (1-{MAX_LIMIT})."
        ),
    ),
    state: str | None = Query(
        None,
        description="Filter by state.",
    ),
    category: str | None = Query(
        None,
        description="Filter by work category.",
    ),
    status_value: str | None = Query(
        None,
        alias="status",
        description="Filter by project status.",
    ),
    district: str | None = Query(
        None,
        description="Filter by district (must be inside your authorized scope).",
    ),
    constituency: str | None = Query(
        None,
        description="Filter by constituency (must be inside your authorized scope).",
    ),
    search: str | None = Query(
        None,
        max_length=120,
        description=(
            "Search project ID, state, district, "
            "constituency, work category, MP, or description."
        ),
    ),
    db: Session = Depends(get_db),
    scope: UserScope = Depends(get_scope),
):
    """
    Return a filtered page of the caller's AUTHORIZED project universe.

    Order of operations matters and is deliberate:

        1. reduce the canonical frame to the caller's scope
        2. reconcile the client's location filters against that scope
           (narrow only; a filter naming another jurisdiction is a 403)
        3. apply the remaining filters
        4. paginate

    `total` is therefore the total WITHIN scope. It is never the
    national count with rows withheld at render time.
    """

    canonical_df, risk_df = (
        _load_project_datasets()
    )

    canonical_df, risk_df = scope_frames(
        canonical_df,
        risk_df,
        scope,
    )

    # Raises 403 if the caller asked for a jurisdiction that is not
    # theirs; otherwise returns the filters that are safe to apply.
    state, district, constituency = narrow_within_scope(
        scope,
        requested_state=state,
        requested_district=district,
        requested_constituency=constituency,
    )

    risk_lookup = _risk_map(
        risk_df
    )

    filtered_df = (
        _apply_canonical_filters(
            canonical_df,
            state,
            category,
            status_value,
            search,
            district=district,
            constituency=constituency,
        )
    )

    filtered_df = (
        filtered_df
        .sort_values(
            "work_id"
        )
    )

    total = int(
        len(filtered_df)
    )

    page_df = (
        filtered_df
        .iloc[
            skip: skip + limit
        ]
    )

    items = []

    for _, row in page_df.iterrows():

        project = (
            _canonical_row_to_project(
                row
            )
        )

        project = (
            _apply_risk_to_project(
                project,
                risk_lookup.get(
                    project.project_id
                ),
            )
        )

        items.append(project)

    return ProjectPage(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        scope=ScopeInfo(**scope.as_metadata()),
        role_key=scope.role,
        empty_state_message=(
            scope.empty_state_message
            if total == 0
            else None
        ),
    )


# =====================================================================
# GET /projects/filter-options
# =====================================================================
#
# Declared BEFORE the "/{project_id:path}" routes below so it is matched
# as a literal path rather than swallowed as a project ID.

@router.get(
    "/filter-options",
    response_model=ProjectFilterOptions,
)
def get_project_filter_options(
    db: Session = Depends(get_db),
    scope: UserScope = Depends(get_scope),
):
    """
    Filter option lists for the Project Explorer, restricted to the
    caller's authorized jurisdiction.

    This is the server-side half of role-aware filters. The values
    returned are exactly the distinct values present in the caller's own
    authorized records -- so a District Authority is never offered an
    "All States" dropdown, because their option list contains one state
    and one district. `locked_filters` tells the UI which controls are
    fixed by jurisdiction and should be rendered as a static label
    rather than a selector.

    This endpoint is convenience only, never enforcement: /projects/query
    re-checks every filter it receives regardless of what was offered
    here.
    """

    canonical_df, _risk_df = _load_project_datasets()

    scoped_df = scope_canonical(canonical_df, scope)

    def _distinct(column: str) -> list[str]:
        if column not in scoped_df.columns:
            return []
        values = (
            scoped_df[column]
            .dropna()
            .astype(str)
            .str.strip()
        )
        values = values[(values != "") & (values.str.lower() != "nan")]
        return sorted(set(values))

    locked = []
    if scope.scope_type in ("state", "district", "constituency"):
        locked.append("state")
    if scope.scope_type == "district":
        locked.append("district")
    if scope.scope_type == "constituency":
        locked.append("constituency")

    return ProjectFilterOptions(
        states=_distinct("state"),
        districts=_distinct("district"),
        constituencies=_distinct("constituency"),
        categories=_distinct("work_category"),
        statuses=_distinct("status"),
        scope=ScopeInfo(**scope.as_metadata()),
        role_key=scope.role,
        locked_filters=locked,
    )


# =====================================================================
# GET /projects/{project_id}/risk
# =====================================================================

@router.get(
    "/{project_id:path}/risk",
    response_model=RiskFusionOut,
)
def get_project_risk(
    project_id: str,
    db: Session = Depends(get_db),
    scope: UserScope = Depends(get_scope),
):
    """
    Return the CURRENT Risk Fusion result for one project.

    The canonical dataset, not the incomplete Project DB, determines
    whether the project exists.

    RBAC: the risk endpoint enforces project-level authorization in its
    own right. It is NOT a side door around GET /projects/{id} -- a
    caller who cannot see the project cannot see its risk, even by
    calling this route directly. The score itself is untouched: Risk
    Fusion stays the single source of truth and returns identical
    values for every role that IS authorized to see the project.
    """

    canonical_df, risk_df = (
        _load_project_datasets()
    )

    # Scope first: this reduces the risk frame to the authorized work
    # IDs, so an out-of-scope ID simply is not present below and falls
    # through to the same 404 a non-existent ID gets.
    canonical_df, risk_df = scope_frames(
        canonical_df,
        risk_df,
        scope,
    )

    normalized_id = (
        project_id.strip()
    )

    matching = risk_df[
        risk_df["work_id"]
        .astype(str)
        .str.strip()
        == normalized_id
    ]

    if matching.empty:

        # Deliberately identical whether the project is out of scope or
        # genuinely has no Risk Fusion row: distinguishing the two would
        # let an unauthorized caller confirm that a work ID exists.
        raise project_not_found()

    row = matching.iloc[0]

    def _float(
        value: Any,
    ) -> float:
        numeric = pd.to_numeric(
            value,
            errors="coerce",
        )

        if pd.isna(numeric):
            return 0.0

        return float(numeric)

    def _int(
        value: Any,
    ) -> int:
        numeric = pd.to_numeric(
            value,
            errors="coerce",
        )

        if pd.isna(numeric):
            return 0

        return int(numeric)

    def _bool(
        value: Any,
    ) -> bool:
        if isinstance(value, bool):
            return value

        if pd.isna(value):
            return False

        return str(value).strip().lower() in {
            "true",
            "1",
            "yes",
        }

    def _string_list(
        value: Any,
    ) -> list[str]:
        if value is None or pd.isna(value):
            return []

        if isinstance(value, list):
            return [
                str(item)
                for item in value
            ]

        text = str(value).strip()

        if not text:
            return []

        # Current CSV may store this as a serialized list.
        if (
            text.startswith("[")
            and text.endswith("]")
        ):
            try:
                import json as _json

                parsed = _json.loads(text)

                if isinstance(parsed, list):
                    return [str(item) for item in parsed]

            except Exception:
                pass

            try:
                import ast

                parsed = ast.literal_eval(
                    text
                )

                if isinstance(
                    parsed,
                    list,
                ):
                    return [
                        str(item)
                        for item in parsed
                    ]

            except Exception:
                pass

        return [text]

    def _dict_value(
        value: Any,
    ) -> dict[str, Any]:

        if value is None:
            return {}

        if isinstance(value, dict):
            return value

        if pd.isna(value):
            return {}

        text = str(value).strip()

        if not text:
            return {}

        # Prefer real JSON parsing (component_breakdown/source_signal_summary
        # are written with json.dumps and may contain true/false/null, which
        # ast.literal_eval cannot parse); fall back to ast.literal_eval for
        # legacy CSV values written in Python-repr form.
        try:
            import json as _json

            parsed = _json.loads(text)

            if isinstance(parsed, dict):
                return parsed

        except Exception:
            pass

        try:

            import ast

            parsed = ast.literal_eval(
                text
            )

            if isinstance(
                parsed,
                dict,
            ):
                return parsed

        except Exception:
            pass

        return {
            "raw": text
        }

    def _components_value(
        value: Any,
    ) -> dict[str, Any]:
        """Parse component_breakdown into {component_name: RiskComponentDetail}.

        Numbers and evidence come straight from the risk pipeline output;
        only the presentational description / review_actions strings are
        layered on, from ml/risk_config.py.
        """

        parsed = _dict_value(value)
        components: dict[str, Any] = {}
        for name, detail in parsed.items():
            if isinstance(detail, dict):
                components[name] = detail
        return enrich_component_details(components)

    return RiskFusionOut(
        work_id=normalized_id,

        risk_score=_float(
            row["risk_score"]
        ),

        risk_level=str(
            row["risk_level"]
        ).upper().strip(),

        evidence_status=str(
            row["evidence_status"]
        ).upper().strip(),

        compliance_contribution=_float(
            row["compliance_contribution"]
        ),

        financial_anomaly_contribution=_float(
            row["financial_anomaly_contribution"]
        ),

        timeline_anomaly_contribution=_float(
            row["timeline_anomaly_contribution"]
        ),

        duplicate_contribution=_float(
            row["duplicate_contribution"]
        ),

        data_quality_contribution=_float(
            row["data_quality_contribution"]
        ),

        payment_contribution=_float(
            row["payment_contribution"]
        ),

        isolation_forest_contribution=_float(
            row["isolation_forest_contribution"]
        ),

        total_evidence_signals=_int(
            row["total_evidence_signals"]
        ),

        high_severity_signal_count=_int(
            row["high_severity_signal_count"]
        ),

        medium_severity_signal_count=_int(
            row["medium_severity_signal_count"]
        ),

        low_severity_signal_count=_int(
            row["low_severity_signal_count"]
        ),

        has_compliance_signal=_bool(
            row["has_compliance_signal"]
        ),

        has_financial_anomaly=_bool(
            row["has_financial_anomaly"]
        ),

        has_timeline_anomaly=_bool(
            row["has_timeline_anomaly"]
        ),

        has_duplicate_signal=_bool(
            row["has_duplicate_signal"]
        ),

        has_data_quality_signal=_bool(
            row["has_data_quality_signal"]
        ),

        has_payment_signal=_bool(
            row["has_payment_signal"]
        ),

        has_isolation_forest_signal=_bool(
            row["has_isolation_forest_signal"]
        ),

        top_reason_1=(
            _clean_string(
                row.get("top_reason_1")
            )
        ),

        top_reason_2=(
            _clean_string(
                row.get("top_reason_2")
            )
        ),

        top_reason_3=(
            _clean_string(
                row.get("top_reason_3")
            )
        ),

        risk_reasons=_string_list(
            row.get("risk_reasons")
        ),

        source_signal_summary=_dict_value(
            row.get(
                "source_signal_summary"
            )
        ),

        components=_components_value(
            row.get("component_breakdown")
        )
        or enrich_component_details(
            build_component_breakdown_from_legacy(row)
        ),

        # False when the processed CSV predates the per-domain
        # data-quality column, so the UI can say "not recorded"
        # instead of the much more dangerous "all data available".
        data_quality_detail_available=(
            "data_quality_notes" in row.index
        ),

        data_quality_notes=_string_list(
            row.get("data_quality_notes")
        ),
    )


# =====================================================================
# GET /projects/{project_id}
# =====================================================================

@router.get(
    "/{project_id:path}",
    response_model=ProjectOut,
)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    scope: UserScope = Depends(get_scope),
):
    """
    Return one project from the caller's AUTHORIZED canonical universe.

    Current Risk Fusion risk_score/risk_level are overlaid on the
    response -- the same values for every authorized role.

    No database row is required for the project to exist in the
    canonical project universe.

    RBAC: a project outside the caller's jurisdiction returns exactly
    the same 404 body as an ID that does not exist at all. Nothing --
    not existence, not financials, not risk -- leaks through this route.
    """

    canonical_df, risk_df = (
        _load_project_datasets()
    )

    canonical_df, risk_df = scope_frames(
        canonical_df,
        risk_df,
        scope,
    )

    normalized_id = (
        project_id.strip()
    )

    matching = canonical_df[
        canonical_df["work_id"]
        .astype(str)
        .str.strip()
        == normalized_id
    ]

    if matching.empty:

        raise project_not_found()

    row = matching.iloc[0]

    project = (
        _canonical_row_to_project(
            row
        )
    )

    risk_lookup = _risk_map(
        risk_df
    )

    project = (
        _apply_risk_to_project(
            project,
            risk_lookup.get(
                normalized_id
            ),
        )
    )

    return project