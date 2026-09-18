"""
Centralized Role-Based Access Control for the MPLADS AI Shield backend.

This is the ONE place role identity, permissions and data scope live.
Every protected route derives its authorized record set from here
rather than re-implementing its own role check -- so there is exactly
one definition of "what may this account see?" in the codebase.

-------------------------------------------------------------------
Design rules this module follows
-------------------------------------------------------------------

1.  The backend is the ultimate authority. A route NEVER trusts a
    state/district/constituency value sent by the client to widen
    access. Client-supplied filters can only ever NARROW the scope
    already derived from the authenticated user (see
    `narrow_within_scope`).

2.  Scope comes from the authenticated User row, not the JWT payload.
    `get_current_user` (app/auth.py) re-reads the DB row on every
    request, so revoking or re-assigning an officer's jurisdiction
    takes effect on their very next call, not when their token
    expires.

3.  Nothing is fabricated. Scope is matched against the real columns
    that already exist in canonical_projects.csv -- `state`,
    `district`, `constituency` and `mp` -- and against the identical
    columns on the `projects` table. No geography is hardcoded, no
    hierarchy table is invented, and no synthetic mapping is created.

4.  An account whose jurisdiction has not been assigned yet resolves
    to the EMPTY scope: it authenticates fine and every endpoint keeps
    working, but it is authorized for zero records. Denying data is
    the safe default; denying the endpoint would be a behaviour change
    for existing accounts.

5.  Risk is never recomputed per role. Scope decides WHICH rows a
    caller may see; the Risk Fusion values inside those rows are the
    same bytes every role gets.

-------------------------------------------------------------------
Role labels
-------------------------------------------------------------------

`User.role` is free text by design (see app/models.py) and existing
accounts already carry titles like "Administrator", "District
Authority", "State Nodal Officer". `normalize_role()` maps those real
strings onto the four canonical roles without requiring any existing
row to be rewritten. The Ministry/Admin substring rule is the exact
same one GET /dashboard/role-overview and require_ministry_or_admin
already used, so no currently-privileged account loses privilege.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

import pandas as pd
from fastapi import Depends, HTTPException, status

from app.auth import get_current_user
from app.models import User

# =====================================================================
# Roles
# =====================================================================

ROLE_MINISTRY = "MINISTRY"
ROLE_STATE_NODAL = "STATE_NODAL"
ROLE_DISTRICT_AUTHORITY = "DISTRICT_AUTHORITY"
ROLE_MP = "MP"
ROLE_UNSCOPED = "UNSCOPED"

ROLE_LABELS = {
    ROLE_MINISTRY: "Ministry / Admin",
    ROLE_STATE_NODAL: "State Nodal Authority",
    ROLE_DISTRICT_AUTHORITY: "District Authority",
    ROLE_MP: "Member of Parliament",
    ROLE_UNSCOPED: "Unassigned",
}

# Order matters: the first pattern that matches wins. "admin"/"ministry"
# is checked first so an account literally titled "Ministry of Rural
# Development (State Cell)" stays national rather than being demoted to
# state scope by the later "state" pattern.
_ROLE_PATTERNS = (
    (re.compile(r"admin|ministry|national", re.I), ROLE_MINISTRY),
    (re.compile(r"state\s*nodal|state", re.I), ROLE_STATE_NODAL),
    (re.compile(r"district", re.I), ROLE_DISTRICT_AUTHORITY),
    (re.compile(r"member\s+of\s+parliament|parliamentarian|\bmp\b|\bm\.p\.\b", re.I), ROLE_MP),
)


def normalize_role(raw_role: Optional[str]) -> str:
    """Map a free-text `User.role` onto one of the canonical roles.

    An unrecognised title returns ROLE_UNSCOPED -- deliberately NOT
    ROLE_MINISTRY. Defaulting an unknown title to the broadest scope
    would mean any self-registered account could reach national data
    simply by inventing a title the pattern list has never seen.
    """
    text = (raw_role or "").strip()
    if not text:
        return ROLE_UNSCOPED
    for pattern, role in _ROLE_PATTERNS:
        if pattern.search(text):
            return role
    return ROLE_UNSCOPED


# =====================================================================
# Permissions
# =====================================================================
#
# Only permissions that correspond to something this application can
# actually do are listed. Nothing here promises a capability the
# existing backend does not implement.

VIEW_DASHBOARD = "VIEW_DASHBOARD"
VIEW_PROJECTS = "VIEW_PROJECTS"
VIEW_PROJECT_DETAILS = "VIEW_PROJECT_DETAILS"
VIEW_RISK = "VIEW_RISK"
VIEW_ALERTS = "VIEW_ALERTS"
VIEW_ANALYTICS = "VIEW_ANALYTICS"
VIEW_REPORTS = "VIEW_REPORTS"
VIEW_MAP = "VIEW_MAP"
VIEW_FINANCIALS = "VIEW_FINANCIALS"
VIEW_PAYMENTS = "VIEW_PAYMENTS"
VIEW_COMPLIANCE = "VIEW_COMPLIANCE"
VIEW_DUPLICATES = "VIEW_DUPLICATES"
VIEW_AI_INSIGHTS = "VIEW_AI_INSIGHTS"
VIEW_DISTRICT_COMPARISON = "VIEW_DISTRICT_COMPARISON"
VIEW_REVIEW_QUEUE = "VIEW_REVIEW_QUEUE"
EXPORT_REPORTS = "EXPORT_REPORTS"
UPLOAD_DATA = "UPLOAD_DATA"
MANAGE_USERS = "MANAGE_USERS"

# Read permissions every jurisdictional role shares. What differs
# between them is the SCOPE those reads resolve to, not the verb.
_COMMON_VIEW = {
    VIEW_DASHBOARD,
    VIEW_PROJECTS,
    VIEW_PROJECT_DETAILS,
    VIEW_RISK,
    VIEW_ALERTS,
    VIEW_ANALYTICS,
    VIEW_MAP,
    VIEW_FINANCIALS,
    VIEW_AI_INSIGHTS,
    VIEW_REPORTS,
    EXPORT_REPORTS,
}

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    ROLE_MINISTRY: frozenset(
        _COMMON_VIEW
        | {
            VIEW_PAYMENTS,
            VIEW_COMPLIANCE,
            VIEW_DUPLICATES,
            VIEW_DISTRICT_COMPARISON,
            VIEW_REVIEW_QUEUE,
            UPLOAD_DATA,
            MANAGE_USERS,
        }
    ),
    ROLE_STATE_NODAL: frozenset(
        _COMMON_VIEW
        | {
            VIEW_PAYMENTS,
            VIEW_COMPLIANCE,
            VIEW_DUPLICATES,
            VIEW_DISTRICT_COMPARISON,
            VIEW_REVIEW_QUEUE,
        }
    ),
    ROLE_DISTRICT_AUTHORITY: frozenset(
        _COMMON_VIEW
        | {
            VIEW_PAYMENTS,
            VIEW_COMPLIANCE,
            VIEW_DUPLICATES,
            VIEW_REVIEW_QUEUE,
        }
    ),
    # An MP is an oversight persona, not an administrative one: full
    # visibility of the works recommended under their constituency,
    # but none of the operational review/administrative surfaces and
    # no data-ingestion or user-management capability.
    ROLE_MP: frozenset(_COMMON_VIEW),
    ROLE_UNSCOPED: frozenset(),
}


def permissions_for(role: str) -> frozenset[str]:
    return ROLE_PERMISSIONS.get(role, frozenset())


# =====================================================================
# Scope
# =====================================================================

SCOPE_NATIONAL = "national"
SCOPE_STATE = "state"
SCOPE_DISTRICT = "district"
SCOPE_CONSTITUENCY = "constituency"
SCOPE_NONE = "none"


@dataclass(frozen=True)
class UserScope:
    """The authorized data scope of one authenticated account.

    `role` is the canonical role; `scope_type` is what the scope is
    keyed on; `state`/`district`/`constituency`/`mp_name` are the real
    values matched against the canonical dataset columns of the same
    name.
    """

    role: str
    scope_type: str
    state: Optional[str] = None
    district: Optional[str] = None
    constituency: Optional[str] = None
    mp_name: Optional[str] = None
    raw_role: str = ""
    permissions: frozenset[str] = field(default_factory=frozenset)

    # -- identity -----------------------------------------------------

    @property
    def is_national(self) -> bool:
        return self.scope_type == SCOPE_NATIONAL

    @property
    def is_empty(self) -> bool:
        """True when the account has no authorized records at all."""
        return self.scope_type == SCOPE_NONE

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)

    # -- presentation -------------------------------------------------

    @property
    def scope_name(self) -> Optional[str]:
        """The human name of the jurisdiction, e.g. "Maharashtra"."""
        if self.scope_type == SCOPE_NATIONAL:
            return "India"
        if self.scope_type == SCOPE_STATE:
            return self.state
        if self.scope_type == SCOPE_DISTRICT:
            return self.district
        if self.scope_type == SCOPE_CONSTITUENCY:
            return self.constituency or self.mp_name
        return None

    @property
    def scope_label(self) -> str:
        """Short label used as the dashboard heading context."""
        if self.scope_type == SCOPE_NATIONAL:
            return "National"
        if self.scope_type == SCOPE_DISTRICT and self.state:
            return f"{self.district}, {self.state}"
        if self.scope_type == SCOPE_CONSTITUENCY and self.state:
            return f"{self.scope_name}, {self.state}"
        return self.scope_name or "No jurisdiction assigned"

    @property
    def scope_indicator(self) -> str:
        """The "Showing data for X" line every dashboard must display."""
        if self.scope_type == SCOPE_NATIONAL:
            return "Showing nationwide data"
        if self.scope_type == SCOPE_STATE:
            return f"Showing data for {self.state}"
        if self.scope_type == SCOPE_DISTRICT:
            return f"Showing data for {self.district}"
        if self.scope_type == SCOPE_CONSTITUENCY:
            return f"Showing projects for {self.scope_name}"
        return "No jurisdiction has been assigned to this account"

    @property
    def empty_state_message(self) -> str:
        if self.scope_type == SCOPE_CONSTITUENCY:
            return "No projects are currently available for your constituency."
        if self.scope_type == SCOPE_DISTRICT:
            return "No projects are currently available for your assigned district."
        if self.scope_type == SCOPE_STATE:
            return "No projects are currently available for your assigned state."
        if self.scope_type == SCOPE_NATIONAL:
            return "No projects are currently available."
        return (
            "This account has no assigned jurisdiction, so no project "
            "records are authorized for it yet. Contact the Ministry "
            "administrator to have a state, district or constituency assigned."
        )

    @property
    def unavailable_reason(self) -> Optional[str]:
        return None if not self.is_empty else self.empty_state_message

    # -- permissions --------------------------------------------------

    def can(self, permission: str) -> bool:
        return permission in self.permissions

    # -- serialization ------------------------------------------------

    def as_metadata(self) -> dict:
        """The `scope` block echoed on scope-aware API responses.

        Only jurisdiction identity is exposed -- never the internal
        permission evaluation, user id, or any other authorization
        internal.
        """
        return {
            "type": self.scope_type,
            "name": self.scope_name,
            "label": self.scope_label,
            "indicator": self.scope_indicator,
            "state": self.state,
            "district": self.district,
            "constituency": self.constituency,
            "mp_name": self.mp_name,
        }


NATIONAL_SCOPE = UserScope(
    role=ROLE_MINISTRY,
    scope_type=SCOPE_NATIONAL,
    raw_role="Ministry",
    permissions=permissions_for(ROLE_MINISTRY),
)


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def resolve_user_scope(user: User) -> UserScope:
    """Derive the authorized scope of an authenticated user.

    Reads only the User row: the canonical role plus whichever
    jurisdiction columns an operator assigned to that account
    (`scope_state`, `scope_district`, `scope_constituency`,
    `scope_mp_name`). A jurisdictional role with no assignment
    resolves to the empty scope rather than silently widening.
    """
    raw_role = (user.role or "").strip()
    role = normalize_role(raw_role)

    scope_state = _clean(getattr(user, "scope_state", None))
    scope_district = _clean(getattr(user, "scope_district", None))
    scope_constituency = _clean(getattr(user, "scope_constituency", None))
    scope_mp_name = _clean(getattr(user, "scope_mp_name", None))

    if role == ROLE_MINISTRY:
        return UserScope(
            role=role,
            scope_type=SCOPE_NATIONAL,
            raw_role=raw_role,
            permissions=permissions_for(role),
        )

    if role == ROLE_STATE_NODAL and scope_state:
        return UserScope(
            role=role,
            scope_type=SCOPE_STATE,
            state=scope_state,
            raw_role=raw_role,
            permissions=permissions_for(role),
        )

    if role == ROLE_DISTRICT_AUTHORITY and scope_district:
        return UserScope(
            role=role,
            scope_type=SCOPE_DISTRICT,
            state=scope_state,
            district=scope_district,
            raw_role=raw_role,
            permissions=permissions_for(role),
        )

    if role == ROLE_MP and (scope_constituency or scope_mp_name):
        return UserScope(
            role=role,
            scope_type=SCOPE_CONSTITUENCY,
            state=scope_state,
            constituency=scope_constituency,
            mp_name=scope_mp_name,
            raw_role=raw_role,
            permissions=permissions_for(role),
        )

    # Recognised role, no jurisdiction assigned -- or an unrecognised
    # role title. Either way: authenticated, but authorized for nothing.
    return UserScope(
        role=role,
        scope_type=SCOPE_NONE,
        raw_role=raw_role,
        permissions=permissions_for(role),
    )


# =====================================================================
# DataFrame scoping (canonical_projects.csv / project_risk_scores.csv)
# =====================================================================

# Canonical column names this module matches against. These are the
# real columns present in data/processed/canonical_projects.csv.
COL_STATE = "state"
COL_DISTRICT = "district"
COL_CONSTITUENCY = "constituency"
COL_MP = "mp"


def _norm_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series("", index=df.index, dtype="object")
    return df[column].fillna("").astype(str).str.strip().str.casefold()


def _eq(df: pd.DataFrame, column: str, value: str) -> pd.Series:
    return _norm_series(df, column) == value.strip().casefold()


def scope_canonical(df: pd.DataFrame, scope: UserScope) -> pd.DataFrame:
    """Reduce the canonical project frame to the caller's scope.

    This is the single chokepoint every project-universe read goes
    through. A national scope returns the frame unchanged (Ministry
    behaviour is preserved exactly); an empty scope returns zero rows.
    """
    if scope.is_national:
        return df

    if scope.is_empty:
        return df.iloc[0:0]

    mask = pd.Series(True, index=df.index)

    if scope.scope_type == SCOPE_STATE:
        mask &= _eq(df, COL_STATE, scope.state)

    elif scope.scope_type == SCOPE_DISTRICT:
        mask &= _eq(df, COL_DISTRICT, scope.district)
        # District names repeat across states (there is an AURANGABAD in
        # more than one), so the assigned state -- when present -- is
        # applied as an additional constraint rather than assumed away.
        if scope.state:
            mask &= _eq(df, COL_STATE, scope.state)

    elif scope.scope_type == SCOPE_CONSTITUENCY:
        # An MP account may be keyed on the constituency, on the MP name
        # (the honest fallback for Rajya Sabha members, whose canonical
        # `constituency` value is the sentinel "Sitting Rajya Sabha"
        # rather than a parliamentary constituency), or on both.
        constituency_mask = None
        if scope.constituency:
            constituency_mask = _eq(df, COL_CONSTITUENCY, scope.constituency)
        if scope.mp_name:
            mp_mask = _eq(df, COL_MP, scope.mp_name)
            constituency_mask = mp_mask if constituency_mask is None else (constituency_mask | mp_mask)
        if constituency_mask is not None:
            mask &= constituency_mask
        if scope.state:
            mask &= _eq(df, COL_STATE, scope.state)

    else:  # pragma: no cover - every scope_type is handled above
        return df.iloc[0:0]

    return df[mask]


def scope_frames(
    canonical_df: pd.DataFrame,
    risk_df: pd.DataFrame,
    scope: UserScope,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Scope the canonical frame, then restrict Risk Fusion to exactly
    the same work_id universe.

    Keeping both frames on the identical work_id set is what lets the
    existing `_validate_universe` / universe-equality checks in
    dashboard.py and analytics.py keep passing untouched after scoping.
    """
    if scope.is_national:
        return canonical_df, risk_df

    scoped_canonical = scope_canonical(canonical_df, scope)
    authorized_ids = set(scoped_canonical["work_id"].astype(str).str.strip())
    scoped_risk = risk_df[risk_df["work_id"].astype(str).str.strip().isin(authorized_ids)]
    return scoped_canonical, scoped_risk


def authorized_work_ids(canonical_df: pd.DataFrame, scope: UserScope) -> set[str]:
    """The exact set of canonical work IDs this account may read."""
    if scope.is_empty:
        return set()
    scoped = scope_canonical(canonical_df, scope)
    return set(scoped["work_id"].astype(str).str.strip())


def is_row_in_scope(row, scope: UserScope) -> bool:
    """Scope check for a single canonical row / ORM Project instance.

    Accepts anything exposing `state` / `district` / `constituency` /
    `mp` (canonical row) or `mp_name` (ORM Project), so the same rule
    covers both storage shapes without duplicating it.
    """
    if scope.is_national:
        return True
    if scope.is_empty:
        return False

    def _get(*names):
        for name in names:
            try:
                value = row[name] if hasattr(row, "keys") and name in row else getattr(row, name, None)
            except Exception:  # pragma: no cover - defensive on odd row types
                value = None
            if value is not None and str(value).strip().lower() not in ("", "nan"):
                return str(value).strip().casefold()
        return None

    row_state = _get("state")
    row_district = _get("district")
    row_constituency = _get("constituency")
    row_mp = _get("mp", "mp_name")

    if scope.scope_type == SCOPE_STATE:
        return row_state == scope.state.strip().casefold()

    if scope.scope_type == SCOPE_DISTRICT:
        if row_district != scope.district.strip().casefold():
            return False
        if scope.state and row_state != scope.state.strip().casefold():
            return False
        return True

    if scope.scope_type == SCOPE_CONSTITUENCY:
        matched = False
        if scope.constituency and row_constituency == scope.constituency.strip().casefold():
            matched = True
        if scope.mp_name and row_mp == scope.mp_name.strip().casefold():
            matched = True
        if not matched:
            return False
        if scope.state and row_state != scope.state.strip().casefold():
            return False
        return True

    return False  # pragma: no cover


# =====================================================================
# SQLAlchemy query scoping (the `projects` table)
# =====================================================================

def scope_project_query(query, scope: UserScope):
    """Apply the caller's scope to a SQLAlchemy query over `Project`.

    Used by the reports router, which aggregates the ORM table rather
    than the canonical frame. Same rule, same source of truth -- just
    expressed as SQL instead of a DataFrame mask.
    """
    from app.models import Project  # local import: avoids a cycle at import time

    if scope.is_national:
        return query

    if scope.is_empty:
        # Definitively empty rather than "unfiltered": an unassigned
        # account must never fall through to the whole table.
        return query.filter(Project.project_id.is_(None))

    if scope.scope_type == SCOPE_STATE:
        return query.filter(Project.state == scope.state)

    if scope.scope_type == SCOPE_DISTRICT:
        query = query.filter(Project.district == scope.district)
        if scope.state:
            query = query.filter(Project.state == scope.state)
        return query

    if scope.scope_type == SCOPE_CONSTITUENCY:
        from sqlalchemy import or_

        clauses = []
        if scope.constituency:
            clauses.append(Project.constituency == scope.constituency)
        if scope.mp_name:
            clauses.append(Project.mp_name == scope.mp_name)
        if clauses:
            query = query.filter(or_(*clauses))
        if scope.state:
            query = query.filter(Project.state == scope.state)
        return query

    return query.filter(Project.project_id.is_(None))  # pragma: no cover


# =====================================================================
# Client-supplied filters: narrow only, never widen
# =====================================================================

def narrow_within_scope(
    scope: UserScope,
    requested_state: Optional[str] = None,
    requested_district: Optional[str] = None,
    requested_constituency: Optional[str] = None,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Reconcile client-supplied location filters against the scope.

    A filter is honoured only when it stays inside the authorized
    jurisdiction. A filter naming a DIFFERENT jurisdiction is rejected
    with 403 rather than silently ignored -- silently ignoring it would
    return the caller's own data under a label claiming it was someone
    else's, which is worse than an explicit refusal.

    Returns the (state, district, constituency) filters the route should
    actually apply on top of the already-scoped frame.
    """
    def _conflicts(requested: Optional[str], authorized: Optional[str]) -> bool:
        if not requested or not authorized:
            return False
        return requested.strip().casefold() != authorized.strip().casefold()

    if scope.is_empty:
        return (None, None, None)

    if scope.is_national:
        return (requested_state, requested_district, requested_constituency)

    if scope.scope_type == SCOPE_STATE:
        if _conflicts(requested_state, scope.state):
            raise _forbidden("outside your assigned state")
        # District/constituency filters are fine here: they can only
        # narrow, because the frame is already restricted to the state.
        return (scope.state, requested_district, requested_constituency)

    if scope.scope_type == SCOPE_DISTRICT:
        if _conflicts(requested_state, scope.state) or _conflicts(requested_district, scope.district):
            raise _forbidden("outside your assigned district")
        return (scope.state, scope.district, requested_constituency)

    if scope.scope_type == SCOPE_CONSTITUENCY:
        if _conflicts(requested_state, scope.state) or _conflicts(
            requested_constituency, scope.constituency
        ):
            raise _forbidden("outside your assigned constituency")
        return (scope.state, requested_district, scope.constituency)

    return (None, None, None)  # pragma: no cover


# =====================================================================
# Errors
# =====================================================================

PROJECT_NOT_FOUND_DETAIL = "Project not found."


def _forbidden(what: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"You don't have permission to access this resource ({what}).",
    )


def forbidden(detail: str = "You don't have permission to access this resource.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def project_not_found() -> HTTPException:
    """The response returned for an out-of-scope project ID.

    Deliberately identical -- status AND body -- to the response for a
    project ID that does not exist at all. Returning 403 here would
    confirm the record exists, which is itself a leak: an MP could
    enumerate which work IDs are real by watching 403-vs-404. The
    existing convention for a genuinely missing project is already 404
    (see GET /projects/{id}), so this matches it exactly.
    """
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=PROJECT_NOT_FOUND_DETAIL,
    )


# =====================================================================
# FastAPI dependencies
# =====================================================================

def get_scope(current_user: User = Depends(get_current_user)) -> UserScope:
    """The authorized scope of the authenticated caller.

    Every scope-aware route depends on THIS rather than reading
    `current_user.role` itself.
    """
    return resolve_user_scope(current_user)


def require_permission(*required: str):
    """Dependency factory: require one or more permissions.

    Raises 403 (never 401 -- the caller is authenticated) when the
    caller's role does not hold every listed permission.
    """

    def _check(scope: UserScope = Depends(get_scope)) -> UserScope:
        missing = [p for p in required if not scope.can(p)]
        if missing:
            raise forbidden()
        return scope

    return _check


def require_any_permission(*accepted: str):
    """As `require_permission`, but any one of the listed permissions
    is sufficient."""

    def _check(scope: UserScope = Depends(get_scope)) -> UserScope:
        if not any(scope.can(p) for p in accepted):
            raise forbidden()
        return scope

    return _check


# =====================================================================
# Role dashboard configuration
# =====================================================================
#
# One centralized description of which dashboard and which navigation
# each role gets. The frontend mirrors these keys (src/lib/roles.js)
# but the backend copy is what the API reports, so the two can never
# drift into disagreeing about which role sees what.

ROLE_CONFIG: dict[str, dict] = {
    ROLE_MINISTRY: {
        "scope": SCOPE_NATIONAL,
        "dashboard": "ministry",
        "nav": ["Dashboard", "Projects", "AI Shield", "Upload & Analyze", "Alerts", "Analytics", "Map View", "Reports"],
    },
    ROLE_STATE_NODAL: {
        "scope": SCOPE_STATE,
        "dashboard": "state",
        "nav": ["Overview", "State Projects", "District Monitoring", "AI Shield", "Alerts", "Analytics", "Map View", "Reports"],
    },
    ROLE_DISTRICT_AUTHORITY: {
        "scope": SCOPE_DISTRICT,
        "dashboard": "district",
        "nav": ["Overview", "District Projects", "AI Shield", "Priority Alerts", "Risk Monitoring", "Map View", "Reports", "Review Queue"],
    },
    ROLE_MP: {
        "scope": SCOPE_CONSTITUENCY,
        "dashboard": "mp",
        "nav": ["Overview", "My Projects", "AI Shield", "Alerts", "Analytics", "Map View", "Reports"],
    },
    ROLE_UNSCOPED: {
        "scope": SCOPE_NONE,
        "dashboard": "unscoped",
        "nav": ["Overview"],
    },
}


def role_config(role: str) -> dict:
    return ROLE_CONFIG.get(role, ROLE_CONFIG[ROLE_UNSCOPED])


def scope_payload(scope: UserScope) -> dict:
    """Everything the frontend needs to render a role correctly, in one
    place: identity, jurisdiction, permissions and dashboard key."""
    config = role_config(scope.role)
    return {
        "role_key": scope.role,
        "role_label": scope.role_label,
        "raw_role": scope.raw_role,
        "dashboard": config["dashboard"],
        "nav": config["nav"],
        "permissions": sorted(scope.permissions),
        "scope": scope.as_metadata(),
        "scope_available": not scope.is_empty,
        "empty_state_message": scope.empty_state_message,
    }


def sorted_permissions(scope: UserScope) -> list[str]:
    return sorted(scope.permissions)


def ensure_iterable(value: Optional[Iterable[str]]) -> list[str]:  # pragma: no cover - tiny helper
    return list(value or [])