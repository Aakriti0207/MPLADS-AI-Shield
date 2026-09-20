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
import json
from decimal import Decimal
import hashlib
import logging
import threading
import time
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import Any, List
import pandas as pd
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
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
from app.project_sectors import classify_project_sector
from app.text_quality import clean_source_text
from app.aggregations import (
    load_canonical_projects,
    load_risk_fusion,
)
logger = logging.getLogger(__name__)

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
def _build_project_datasets():
    """
    Load and prepare the canonical project universe and current Risk Fusion
    output. Called exactly once per process by _load_project_datasets().

    Besides the constituency-resolution merge, this also precomputes every
    derived column the request handlers need (normalized sector, casefolded
    filter columns, one combined search string) so that no request ever runs
    a row-wise Python loop or a str.casefold() over 43,863 rows again.
    """
    try:
        canonical_df = load_canonical_projects()
        risk_df = load_risk_fusion()
        resolution_path = (
            Path(__file__).resolve().parents[2]
            / "data"
            / "processed"
            / "constituency_resolution.csv"
        )
        if resolution_path.exists():
            resolution_df = pd.read_csv(
                resolution_path,
                low_memory=False,
            )
            required_columns = {
                "work_id",
                "mp",
                "mp_type",
                "resolved_constituency",
            }
            if required_columns.issubset(resolution_df.columns):
                resolution_meta = resolution_df[
                    [
                        "work_id",
                        "mp",
                        "mp_type",
                        "resolved_constituency",
                    ]
                ].copy()
                resolution_meta["work_id"] = (
                    resolution_meta["work_id"]
                    .astype(str)
                    .str.strip()
                )
                resolution_meta = resolution_meta.drop_duplicates(
                    subset=["work_id"],
                    keep="first",
                )
                canonical_df = canonical_df.copy()
                canonical_df["work_id"] = (
                    canonical_df["work_id"]
                    .astype(str)
                    .str.strip()
                )
                canonical_df = canonical_df.merge(
                    resolution_meta,
                    on="work_id",
                    how="left",
                    suffixes=("", "_resolved"),
                    validate="one_to_one",
                )
                resolved_constituency = (
                    canonical_df["resolved_constituency"]
                    .replace({"": pd.NA, "nan": pd.NA})
                    if "resolved_constituency" in canonical_df.columns
                    else pd.Series(pd.NA, index=canonical_df.index)
                )
                canonical_constituency = (
                    canonical_df["constituency"]
                    if "constituency" in canonical_df.columns
                    else pd.Series(pd.NA, index=canonical_df.index)
                )
                canonical_df["constituency"] = (
                    resolved_constituency.combine_first(
                        canonical_constituency
                    )
                )
                resolved_mp = (
                    canonical_df["mp_resolved"]
                    if "mp_resolved" in canonical_df.columns
                    else pd.Series(pd.NA, index=canonical_df.index)
                )
                canonical_mp = (
                    canonical_df["mp"]
                    if "mp" in canonical_df.columns
                    else pd.Series(pd.NA, index=canonical_df.index)
                )
                canonical_df["mp"] = (
                    resolved_mp.combine_first(canonical_mp)
                )
                resolved_mp_type = (
                    canonical_df["mp_type_resolved"]
                    if "mp_type_resolved" in canonical_df.columns
                    else (
                        canonical_df["mp_type"]
                        if "mp_type" in canonical_df.columns
                        else pd.Series(pd.NA, index=canonical_df.index)
                    )
                )
                if (
                    "mp_type" in canonical_df.columns
                    and "mp_type_resolved" in canonical_df.columns
                ):
                    canonical_mp_type = canonical_df["mp_type"]
                    canonical_df["mp_type"] = (
                        resolved_mp_type.combine_first(
                            canonical_mp_type
                        )
                    )
                else:
                    canonical_df["mp_type"] = resolved_mp_type
                for column in (
                    "resolved_constituency",
                    "mp_resolved",
                    "mp_type_resolved",
                ):
                    if column in canonical_df.columns:
                        canonical_df.drop(
                            columns=column,
                            inplace=True,
                        )
    except (
        FileNotFoundError,
        ValueError,
        pd.errors.ParserError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )
    canonical_ids = set(canonical_df["work_id"])
    risk_ids = set(risk_df["work_id"])
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
    # Establish the API's deterministic row order once. Filtering preserves
    # this order, so list/query endpoints no longer sort the full
    # 43,863-row frame on every request.
    #
    # Sorted by State -> District -> Work ID (rather than Work ID alone) so
    # that the unfiltered Project Explorer, and the state names within it,
    # read alphabetically instead of in the CSV's original load order
    # (which happens to cluster many same-state rows together but not in
    # A-Z order). Missing state/district values sort last, not first.
    sort_keys = [
        col
        for col in ("state", "district", "work_id")
        if col in canonical_df.columns
    ]
    canonical_df = (
        canonical_df
        .sort_values(
            sort_keys,
            key=lambda col: col.astype(str).str.casefold(),
            na_position="last",
            kind="mergesort",
        )
        .reset_index(drop=True)
    )
    canonical_df = _add_derived_columns(canonical_df)
    return canonical_df, risk_df


# ---------------------------------------------------------------------
# Process-wide dataset cache (thread-safe, single build)
# ---------------------------------------------------------------------
#
# functools.lru_cache does NOT stop two simultaneous first requests from
# both running the (slow) loader. The Projects page fires /query and
# /filter-options at the same moment, so on a cold process the whole load
# used to run twice in parallel. This lock makes the second caller wait for
# the first result instead.
_DATASET_LOCK = threading.Lock()
_DATASETS: tuple[pd.DataFrame, pd.DataFrame] | None = None
_LABEL_BY_WORK_ID: dict[str, Any] = {}
_DATA_VERSION = "0"


def _load_project_datasets():
    global _DATASETS, _LABEL_BY_WORK_ID, _DATA_VERSION
    datasets = _DATASETS
    if datasets is not None:
        return datasets
    with _DATASET_LOCK:
        if _DATASETS is None:
            started = time.perf_counter()
            canonical_df, risk_df = _build_project_datasets()
            _LABEL_BY_WORK_ID = dict(
                zip(canonical_df["work_id"], canonical_df.index)
            )
            _DATA_VERSION = str(time.time_ns())
            _DATASETS = (canonical_df, risk_df)
            logger.info(
                "Project datasets ready: %d projects in %.1fs",
                len(canonical_df),
                time.perf_counter() - started,
            )
        return _DATASETS


def _reset_all_caches() -> None:
    """Drop every process-local cache (use after regenerating the CSVs)."""
    global _DATASETS, _LABEL_BY_WORK_ID, _RISK_LIGHT, _RISK_INDEXED
    with _DATASET_LOCK:
        _DATASETS = None
        _LABEL_BY_WORK_ID = {}
    _RISK_LIGHT = None
    _RISK_INDEXED = None
    _clear_project_scope_cache()
    _risk_lookup.cache_clear()
    load_canonical_projects.cache_clear()
    load_risk_fusion.cache_clear()


# Backwards compatibility: anything that used to call
# _load_project_datasets.cache_clear() keeps working.
_load_project_datasets.cache_clear = _reset_all_caches


def warm_up_projects() -> None:
    """
    Build every cache once, at server start, so the first real user does
    not pay for it. Call from the FastAPI lifespan / startup hook.
    """
    started = time.perf_counter()
    _load_project_datasets()
    _risk_light_lookup()
    logger.info(
        "Projects warm-up finished in %.1fs",
        time.perf_counter() - started,
    )
# =====================================================================
# =====================================================================
# Cached RBAC scope
# =====================================================================
_SCOPED_INDEX_CACHE: dict[str, pd.Index] = {}
_SCOPED_INDEX_CACHE_MAX = 32

# Authorized *frames* per scope. For a scope that covers every row (national
# roles) this holds a reference to the master frame, i.e. no copy at all.
_SCOPED_FRAME_CACHE: "OrderedDict[str, pd.DataFrame]" = OrderedDict()
_SCOPED_FRAME_CACHE_MAX = 16

# Ready-made responses. Data is static per process, so a given
# (scope, filters, page) always produces the same answer.
_CACHE_LOCK = threading.RLock()
_PAGE_CACHE: "OrderedDict[str, Any]" = OrderedDict()
_PAGE_CACHE_MAX = 512
_OPTIONS_CACHE: "OrderedDict[str, Any]" = OrderedDict()
_OPTIONS_CACHE_MAX = 64

# Browser-side caching. `Vary: Authorization` makes the browser keep one
# copy per access token, so one user's cached page is never replayed to
# another user.
_CACHE_CONTROL = "private, max-age=60, stale-while-revalidate=300"


def _cache_get(cache: "OrderedDict[str, Any]", key: str) -> Any:
    with _CACHE_LOCK:
        value = cache.get(key)
        if value is not None:
            cache.move_to_end(key)
        return value


def _cache_put(
    cache: "OrderedDict[str, Any]",
    key: str,
    value: Any,
    max_size: int,
) -> Any:
    with _CACHE_LOCK:
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > max_size:
            cache.popitem(last=False)
    return value


def _scope_cache_key(scope: UserScope) -> str:
    """Build a stable cache key from the complete authorization scope."""
    payload: dict[str, Any] = {}
    try:
        payload["attributes"] = vars(scope)
    except TypeError:
        payload["attributes"] = repr(scope)
    try:
        payload["metadata"] = scope.as_metadata()
    except Exception:
        payload["metadata"] = None
    return json.dumps(
        payload,
        sort_keys=True,
        default=str,
    )


def _scoped_canonical(
    canonical_df: pd.DataFrame,
    scope: UserScope,
) -> pd.DataFrame:
    """
    Return only rows authorized for this scope.

    scope_canonical() remains the authorization enforcement point. It runs
    once per distinct scope; afterwards the authorized frame itself is
    reused (no per-request .loc copy of up to 43,863 rows).
    """
    key = _scope_cache_key(scope)
    datasets = _DATASETS
    is_master = datasets is not None and canonical_df is datasets[0]

    if is_master:
        cached_frame = _cache_get(_SCOPED_FRAME_CACHE, key)
        if cached_frame is not None:
            return cached_frame

    cached_index = _SCOPED_INDEX_CACHE.get(key)
    if cached_index is None:
        scoped = scope_canonical(
            canonical_df,
            scope,
        )
        cached_index = scoped.index.copy()
        with _CACHE_LOCK:
            if len(_SCOPED_INDEX_CACHE) >= _SCOPED_INDEX_CACHE_MAX:
                oldest_key = next(iter(_SCOPED_INDEX_CACHE))
                _SCOPED_INDEX_CACHE.pop(oldest_key, None)
            _SCOPED_INDEX_CACHE[key] = cached_index

    if is_master and len(cached_index) == len(canonical_df):
        frame = canonical_df
    else:
        frame = canonical_df.loc[cached_index]

    if is_master:
        _cache_put(
            _SCOPED_FRAME_CACHE,
            key,
            frame,
            _SCOPED_FRAME_CACHE_MAX,
        )
    return frame


def _authorized_label(
    canonical_df: pd.DataFrame,
    scope: UserScope,
    work_id: str,
) -> Any:
    """
    Row label of `work_id` if (and only if) it is inside the caller's
    authorized universe; otherwise None. Out-of-scope and non-existent IDs
    are indistinguishable to the caller.
    """
    label = _LABEL_BY_WORK_ID.get(work_id)
    if label is None:
        return None
    scoped = _scoped_canonical(canonical_df, scope)
    return label if label in scoped.index else None


def _clear_project_scope_cache() -> None:
    """Clear cached RBAC indexes and responses after a data refresh."""
    with _CACHE_LOCK:
        _SCOPED_INDEX_CACHE.clear()
        _SCOPED_FRAME_CACHE.clear()
        _PAGE_CACHE.clear()
        _OPTIONS_CACHE.clear()


def _page_key(scope: UserScope, *parts: Any) -> str:
    return "\x1f".join(
        [
            _scope_cache_key(scope),
            *("" if part is None else str(part) for part in parts),
        ]
    )


def _etag_for(key: str) -> str:
    digest = hashlib.sha1(
        f"{_DATA_VERSION}|{key}".encode("utf-8")
    ).hexdigest()[:24]
    return f'W/"{digest}"'


def _cache_headers(etag: str) -> dict[str, str]:
    return {
        "ETag": etag,
        "Cache-Control": _CACHE_CONTROL,
        "Vary": "Authorization",
    }


def _not_modified(request: Request, etag: str) -> Response | None:
    """304 when the browser already holds this exact response."""
    header = request.headers.get("if-none-match")
    if header and etag in [part.strip() for part in header.split(",")]:
        return Response(status_code=304, headers=_cache_headers(etag))
    return None


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
def _row_sector(row: Any) -> Any:
    """Normalized sector: precomputed column when present, else classify."""
    sector = row.get("_project_sector")
    if isinstance(sector, str):
        return sector
    return classify_project_sector(
        work_description=row.get("work_description"),
        work_category=row.get("work_category"),
    )


def _canonical_row_to_project(
    row: pd.Series,
    risk: tuple[Decimal | None, str | None] | None = None,
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
    project_name = _clean_string(row.get("project_name"))
    if not project_name:
        project_name = _clean_string(row.get("work_description"))
    # Never use work_category as a project name. If the source description
    # is unavailable/corrupted, expose the absence rather than showing
    # values such as "Normal/Others" as though they were project names.
    if project_name:
        normalized_name = project_name.casefold()
        if normalized_name in {
            "normal/others",
            "normal / others",
            "others",
        }:
            project_name = None
    # A large share of work_description values for Hindi-language works
    # were corrupted into literal "?" characters upstream of this
    # dataset (confirmed at the raw CSV byte level -- not a rendering
    # issue here, and not recoverable). Showing "P.C.C ??? ?? ???????"
    # as a project name is worse than showing nothing, so the same
    # corruption check the frontend already applied to work_description
    # is applied here too, before the value ever leaves the API.
    if project_name and clean_source_text(project_name) is None:
        project_name = None
    if not project_id:
        raise ValueError(
            "Canonical project row has no work_id."
        )
    sanctioned_amount = _decimal(
        row.get("sanction_amount")
    )
    # ---------------------------------------------------------------
    # Expenditure: prefer total_expenditure, but a large share of
    # canonical rows (mostly COMPLETED/ONGOING works) never got a
    # total_expenditure figure recorded upstream even though the money
    # actually disbursed against the sanction (amount_disbursed) IS
    # present. Falling back to amount_disbursed turns "Not available"
    # into a real figure for those rows without inventing anything --
    # it is the same source data, just a different column recording it.
    # ---------------------------------------------------------------
    expenditure = _decimal(
        row.get("total_expenditure")
    )
    if expenditure is None:
        expenditure = _decimal(
            row.get("amount_disbursed")
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
    # Clean resolved project-location constituency.
    #
    # "Sitting Rajya Sabha" / "Sitting Lok Sabha" describe the MP seat
    # metadata, not the project's geographic constituency. Likewise, an
    # unresolved/ambiguous resolution must not be presented as a real
    # constituency.
    #
    # This cleaning is display-only (ProjectOut), not applied to the
    # dataframe -- app/rbac.py's scope_canonical() still matches MPs
    # against the raw "Sitting Rajya Sabha" value via the `mp` column,
    # so an RS member's scoping is unaffected by this row hiding the
    # sentinel from the API response.
    # ---------------------------------------------------------------
    constituency = _clean_string(
        row.get("constituency")
    )
    if constituency:
        normalized_constituency = constituency.casefold()
        if (
            normalized_constituency in {
                "sitting rajya sabha",
                "sitting lok sabha",
            }
            or normalized_constituency.startswith("unresolved_")
            or normalized_constituency.startswith("unresolved ")
        ):
            constituency = None
    # ---------------------------------------------------------------
    # Build response.
    # ---------------------------------------------------------------
    return ProjectOut(
        project_id=project_id,
        project_name=project_name,
        state=_clean_string(
            row.get("state")
        ),
        district=_clean_string(
            row.get("district")
        ),
        constituency=constituency,
        mp_name=_clean_string(
            row.get("mp")
        ),
        mp_type=_clean_string(
            row.get("mp_type")
        ),
        # Project Category is the normalized sector used by the
        # Project Explorer. The raw work_category remains unchanged
        # in canonical_projects.csv for traceability.
        work_type=_row_sector(row),
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
        # The source data's own compliance flag: a payment exists with no
        # matching sanction record. Read directly, never inferred/guessed --
        # if the column isn't present in an older CSV, this is simply None
        # rather than fabricated.
        expenditure_without_sanction=(
            bool(row.get("flag_expenditure_without_sanction"))
            if "flag_expenditure_without_sanction" in row.index
            and pd.notna(row.get("flag_expenditure_without_sanction"))
            else None
        ),
        # -----------------------------------------------------------
        # Legacy Phase-2 risk fields.
        #
        # These are intentionally not fabricated from current Risk
        # Fusion. The current risk contract is /risk.
        # -----------------------------------------------------------
        # Current Risk Fusion score/level, when a (score, level) pair
        # is supplied by the caller (see _risk_light_lookup()).
        risk_score=risk[0] if risk else None,
        risk_level=risk[1] if risk else None,
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
@lru_cache(maxsize=1)
def _risk_lookup() -> dict[str, dict[str, Any]]:
    """Build the current Risk Fusion lookup once per backend process."""
    risk_df = load_risk_fusion()
    return (
        risk_df
        .set_index("work_id", drop=False)
        .to_dict(orient="index")
    )
_RISK_LOCK = threading.Lock()
_RISK_LIGHT: dict[str, tuple[Decimal | None, str | None]] | None = None
_RISK_INDEXED: pd.DataFrame | None = None


def _risk_light_lookup() -> dict[str, tuple[Decimal | None, str | None]]:
    """
    work_id -> (risk_score, risk_level), built once.

    The list/query/detail endpoints only need these two values. The old
    _risk_lookup() turned all 43,863 x ~50 columns (including the large
    JSON text columns) into Python dicts just to read two of them.
    """
    global _RISK_LIGHT
    lookup = _RISK_LIGHT
    if lookup is not None:
        return lookup
    with _RISK_LOCK:
        if _RISK_LIGHT is None:
            risk_df = load_risk_fusion()
            scores = [_decimal(value) for value in risk_df["risk_score"]]
            levels = []
            for value in risk_df["risk_level"]:
                text = _clean_string(value)
                levels.append(text.upper() if text else None)
            _RISK_LIGHT = dict(
                zip(risk_df["work_id"], zip(scores, levels))
            )
        return _RISK_LIGHT


def _risk_full_row(work_id: str) -> pd.Series | None:
    """One complete Risk Fusion row (all columns) for the /risk endpoint."""
    global _RISK_INDEXED
    indexed = _RISK_INDEXED
    if indexed is None:
        with _RISK_LOCK:
            if _RISK_INDEXED is None:
                _RISK_INDEXED = load_risk_fusion().set_index(
                    "work_id", drop=False
                )
            indexed = _RISK_INDEXED
    try:
        return indexed.loc[work_id]
    except KeyError:
        return None


def _rows_to_projects(page_df: pd.DataFrame) -> list[ProjectOut]:
    light = _risk_light_lookup()
    items = []
    for _, row in page_df.iterrows():
        work_id = _clean_string(row.get("work_id"))
        items.append(
            _canonical_row_to_project(row, light.get(work_id))
        )
    return items


def _risk_map(
    risk_df: pd.DataFrame,
) -> dict[str, dict[str, Any]]:
    """
    Backward-compatible Risk Fusion mapper.
    Prefer _risk_lookup() in request handlers. This fallback is kept for
    internal callers that already have a scoped Risk Fusion DataFrame.
    """
    return (
        risk_df
        .set_index("work_id", drop=False)
        .to_dict(orient="index")
    )
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
_SEARCH_COLUMNS = (
    "work_id",
    "state",
    "district",
    "constituency",
    "work_category",
    "_project_sector",
    "mp",
    "implementing_agency",
    "work_description",
)
_FILTER_NORM_COLUMNS = (
    "state",
    "district",
    "constituency",
    "status",
    "_project_sector",
    "mp_type",
)


def _norm_series(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.casefold()


def _classify_sectors(df: pd.DataFrame) -> list[Any]:
    """Row-wise sector classification without building a Series per row."""
    empty = [None] * len(df)
    descriptions = (
        df["work_description"] if "work_description" in df.columns else empty
    )
    categories = (
        df["work_category"] if "work_category" in df.columns else empty
    )
    return [
        classify_project_sector(
            work_description=description,
            work_category=category,
        )
        for description, category in zip(descriptions, categories)
    ]


def _with_project_sector(df: pd.DataFrame) -> pd.DataFrame:
    """Add the normalized project sector used by Project Explorer filters.

    app/aggregations.py's load_canonical_projects() already computes this
    exact classification once per process, as a `project_sector` column
    (see the comment there). Reuse it under the `_project_sector` name
    this module's filters/search already key off, instead of re-running
    the 43,863-row classifier a second time on every cold start.
    """
    if "_project_sector" in df.columns:
        return df
    result = df.copy()
    if "project_sector" in result.columns:
        result["_project_sector"] = result["project_sector"]
    else:
        result["_project_sector"] = _classify_sectors(result)
    return result


def _add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Precompute, once, everything the filters need:

      _project_sector   normalized sector (was a per-request apply(axis=1))
      _n_<column>       stripped + casefolded copy of each filter column
      _search_blob      all searchable columns joined into one lowercase
                        string, so search is ONE str.contains() call
    """
    df = _with_project_sector(df.copy())
    for column in _FILTER_NORM_COLUMNS:
        if column in df.columns:
            df[f"_n_{column}"] = _norm_series(df[column])
    blob = pd.Series("", index=df.index, dtype="object")
    for column in _SEARCH_COLUMNS:
        if column in df.columns:
            blob = blob + "\n" + _norm_series(df[column])
    df["_search_blob"] = blob
    return df


def _canonical_with_project_sector() -> pd.DataFrame:
    """The master frame (it already carries _project_sector)."""
    return _load_project_datasets()[0]


_canonical_with_project_sector.cache_clear = lambda: None


def _apply_canonical_filters(
    df: pd.DataFrame,
    state: str | None,
    category: str | None,
    status_value: str | None,
    search: str | None,
    district: str | None = None,
    constituency: str | None = None,
    mp_type: str | None = None,
) -> pd.DataFrame:
    """
    Apply project filters to an already-authorized canonical frame.

    Runs on the precomputed `_n_*` / `_search_blob` columns, so a request
    is a handful of vectorized comparisons instead of repeated
    fillna/astype/strip/casefold passes over 43,863 rows.
    """
    result = df
    if "_search_blob" not in result.columns:
        # A frame that did not come from the master dataset.
        result = _add_derived_columns(result)
    for column, value in (
        ("district", district),
        ("constituency", constituency),
        ("state", state),
        ("_project_sector", category),
        ("status", status_value),
        ("mp_type", mp_type),
    ):
        norm_column = f"_n_{column}"
        if not value or norm_column not in result.columns:
            continue
        result = result[result[norm_column] == value.strip().casefold()]
    if search:
        pattern = search.strip().casefold()
        if pattern:
            result = result[
                result["_search_blob"].str.contains(
                    pattern,
                    regex=False,
                )
            ]
    return result


# =====================================================================
# GET /projects
# =====================================================================
@router.get(
    "",
    response_model=List[ProjectOut],
)
def list_projects(
    request: Request,
    response: Response,
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
    Return a page from the authorized canonical project universe.

    The canonical frame is pre-sorted once at load time. Only the requested
    page is converted to ProjectOut; the finished page is then cached.
    """
    canonical_df, _risk_df = _load_project_datasets()
    scoped_df = _scoped_canonical(canonical_df, scope)
    key = _page_key(scope, "list", skip, limit)
    etag = _etag_for(key)
    not_modified = _not_modified(request, etag)
    if not_modified is not None:
        return not_modified
    results = _cache_get(_PAGE_CACHE, key)
    if results is None:
        results = _cache_put(
            _PAGE_CACHE,
            key,
            _rows_to_projects(scoped_df.iloc[skip: skip + limit]),
            _PAGE_CACHE_MAX,
        )
    response.headers.update(_cache_headers(etag))
    return results
# =====================================================================
# GET /projects/query
# =====================================================================
@router.get(
    "/query",
    response_model=ProjectPage,
)
def query_projects(
    request: Request,
    response: Response,
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
        description="Filter by normalized project category.",
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
    mp_type: str | None = Query(
        None,
        description="Filter by MP type (e.g. Lok Sabha / Rajya Sabha).",
    ),
    search: str | None = Query(
        None,
        max_length=120,
        description=(
            "Search project ID, state, district, "
            "constituency, project category, MP, or description."
        ),
    ),
    db: Session = Depends(get_db),
    scope: UserScope = Depends(get_scope),
):
    """
    Return a filtered page of the caller's authorized canonical universe.

    RBAC order is unchanged: scope first, then narrow_within_scope() (which
    refuses out-of-jurisdiction filters), and only then is the response
    cache consulted -- the cache key contains the full scope, so a cached
    page can never be served to a caller with a different scope.
    """
    canonical_df, _risk_df = _load_project_datasets()
    scoped_df = _scoped_canonical(canonical_df, scope)
    state, district, constituency = narrow_within_scope(
        scope,
        requested_state=state,
        requested_district=district,
        requested_constituency=constituency,
    )
    # The frontend historically sent this filter as camelCase ("mpType")
    # while /projects/query had no parameter for it at all. mp_type above
    # covers a caller using the snake_case name; this covers one still
    # using the old camelCase name, so neither integration breaks.
    if not mp_type:
        mp_type = request.query_params.get("mpType") or None
    mp_type = mp_type.strip() if mp_type else None
    key = _page_key(
        scope,
        "query",
        skip,
        limit,
        state,
        category,
        status_value,
        district,
        constituency,
        mp_type,
        search,
    )
    etag = _etag_for(key)
    not_modified = _not_modified(request, etag)
    if not_modified is not None:
        return not_modified
    page = _cache_get(_PAGE_CACHE, key)
    if page is None:
        filtered_df = _apply_canonical_filters(
            scoped_df,
            state,
            category,
            status_value,
            search,
            district=district,
            constituency=constituency,
            mp_type=mp_type,
        )
        total = int(len(filtered_df))
        items = _rows_to_projects(filtered_df.iloc[skip: skip + limit])
        page = _cache_put(
            _PAGE_CACHE,
            key,
            ProjectPage(
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
            ),
            _PAGE_CACHE_MAX,
        )
    response.headers.update(_cache_headers(etag))
    return page
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
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    scope: UserScope = Depends(get_scope),
):
    """
    Filter option lists for the Project Explorer, restricted to the
    caller's authorized jurisdiction.

    The values returned are exactly the distinct values present in the
    caller's own authorized records. `locked_filters` tells the UI which
    controls are fixed by jurisdiction. This endpoint is convenience only,
    never enforcement: /projects/query re-checks every filter it receives.

    `categories` are the normalized project-sector values (the same
    classify_project_sector() output ProjectOut.work_type and the `category`
    filter use). The result is computed once per scope and cached; it used
    to run a 43,863-row Python loop on every call.
    """
    canonical_df, _risk_df = _load_project_datasets()
    scoped_df = _scoped_canonical(canonical_df, scope)
    key = _page_key(scope, "options")
    etag = _etag_for(key)
    not_modified = _not_modified(request, etag)
    if not_modified is not None:
        return not_modified
    options = _cache_get(_OPTIONS_CACHE, key)
    if options is None:
        sectored_df = _with_project_sector(scoped_df)

        def _distinct(df: pd.DataFrame, column: str) -> list[str]:
            if column not in df.columns:
                return []
            values = (
                pd.Series(df[column].dropna().unique())
                .astype(str)
                .str.strip()
            )
            values = values[
                (values != "") & (values.str.lower() != "nan")
            ]
            return sorted(set(values))

        locked = []
        if scope.scope_type in ("state", "district", "constituency"):
            locked.append("state")
        if scope.scope_type == "district":
            locked.append("district")
        if scope.scope_type == "constituency":
            locked.append("constituency")
        options = _cache_put(
            _OPTIONS_CACHE,
            key,
            ProjectFilterOptions(
                states=_distinct(scoped_df, "state"),
                districts=_distinct(scoped_df, "district"),
                constituencies=_distinct(scoped_df, "constituency"),
                categories=_distinct(sectored_df, "_project_sector"),
                statuses=_distinct(scoped_df, "status"),
                mp_types=_distinct(scoped_df, "mp_type"),
                scope=ScopeInfo(**scope.as_metadata()),
                role_key=scope.role,
                locked_filters=locked,
            ),
            _OPTIONS_CACHE_MAX,
        )
    response.headers.update(_cache_headers(etag))
    return options
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
    canonical_df, _risk_df = _load_project_datasets()
    normalized_id = project_id.strip()
    # Authorization first. An out-of-scope ID follows exactly the same
    # 404 path as a nonexistent project.
    if _authorized_label(canonical_df, scope, normalized_id) is None:
        raise project_not_found()
    row = _risk_full_row(normalized_id)
    if row is None:
        raise project_not_found()
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
            "data_quality_notes" in row
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
    canonical_df, _risk_df = _load_project_datasets()
    normalized_id = project_id.strip()
    label = _authorized_label(canonical_df, scope, normalized_id)
    if label is None:
        raise project_not_found()
    return _canonical_row_to_project(
        canonical_df.loc[label],
        _risk_light_lookup().get(normalized_id),
    )