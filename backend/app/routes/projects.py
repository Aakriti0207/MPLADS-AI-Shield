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
    ProjectOut,
    ProjectPage,
    RiskFusionOut,
)

from app.aggregations import (
    load_canonical_projects,
    load_risk_fusion,
)


# =====================================================================
# Router
# =====================================================================

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
) -> pd.DataFrame:
    """
    Apply project filters directly to the canonical dataset.
    """

    result = df.copy()

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
):
    """
    Return a page from the CURRENT 43,863-project canonical universe.

    Risk score and risk level are overlaid from current Risk Fusion.
    """

    canonical_df, risk_df = (
        _load_project_datasets()
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
    search: str | None = Query(
        None,
        max_length=120,
        description=(
            "Search project ID, state, district, "
            "constituency, work category, MP, or description."
        ),
    ),
    db: Session = Depends(get_db),
):
    """
    Return a filtered page from the canonical 43,863-project universe.
    """

    canonical_df, risk_df = (
        _load_project_datasets()
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
):
    """
    Return the CURRENT Phase 7 Risk Fusion result.

    The canonical dataset, not the incomplete Project DB, determines
    whether the project exists.
    """

    canonical_df, risk_df = (
        _load_project_datasets()
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

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Current Risk Fusion result for "
                f"project '{project_id}' is not available."
            ),
        )

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
):
    """
    Return one project from the canonical 43,863-project universe.

    Current Risk Fusion risk_score/risk_level are overlaid on the
    response.

    No database row is required for the project to exist in the
    canonical project universe.
    """

    canonical_df, risk_df = (
        _load_project_datasets()
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

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Project '{project_id}' not found"
            ),
        )

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