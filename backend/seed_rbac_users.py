"""
Provision RBAC accounts with real assigned jurisdictions.

Why this script exists
----------------------
`POST /auth/register` deliberately grants NO jurisdiction (see
app/routes/auth.py) -- letting a registrant choose their own state or
constituency would make the entire scoping model self-service. So the
only way an account gets a jurisdiction is an operator assigning one,
and this script is that path.

It also creates the demo personas used to walk through the four roles.
Every jurisdiction it assigns is READ FROM THE REAL DATASET at run time,
not hardcoded: the script picks a state with a good spread of districts,
then a real district and a real parliamentary constituency inside it.
Nothing here fabricates data, and it does not insert a single project
row -- the dashboards are populated by the 43,863 real projects that are
already there.

Usage
-----
    python seed_rbac_users.py                # create/update the demo accounts
    python seed_rbac_users.py --list         # show what exists, change nothing
    python seed_rbac_users.py --assign \\
        --email officer@example.gov.in \\
        --role "District Authority" \\
        --state Maharashtra --district SATARA

Existing accounts are UPDATED in place (role + jurisdiction), never
duplicated, and their passwords are left untouched unless --password is
given. The script never deletes anything.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import SessionLocal
from app.models import User
from app.rbac import normalize_role, resolve_user_scope
from app.schema_migration import sync_schema

DEFAULT_PASSWORD = "MpladsDemo@2026"


# ---------------------------------------------------------------------
# Pick real jurisdictions out of the canonical dataset
# ---------------------------------------------------------------------

def discover_jurisdictions() -> dict:
    """Find a real state / district / constituency triple to demo with.

    Chooses the state with the most districts that also contains at least
    one genuine parliamentary constituency (i.e. not a "Sitting Rajya
    Sabha" sentinel), so the State Nodal dashboard's district comparison
    has something real to compare and the MP persona maps to an actual
    constituency rather than a placeholder.
    """
    from app.aggregations import load_canonical_projects

    df = load_canonical_projects()

    located = df[df["state"].notna() & df["district"].notna()].copy()
    located["state"] = located["state"].astype(str).str.strip()
    located["district"] = located["district"].astype(str).str.strip()
    located["constituency"] = located["constituency"].fillna("").astype(str).str.strip()

    real_pc = located[
        (located["constituency"] != "")
        & (~located["constituency"].str.contains("Rajya Sabha", case=False, na=False))
    ]
    if real_pc.empty:
        raise SystemExit("No project in the canonical dataset has a parliamentary constituency.")

    # State with the widest district spread among states that have a real PC.
    candidate_states = real_pc["state"].unique()
    spread = (
        located[located["state"].isin(candidate_states)]
        .groupby("state")["district"]
        .nunique()
        .sort_values(ascending=False)
    )
    state = str(spread.index[0])

    state_rows = real_pc[real_pc["state"] == state]

    # Busiest district in that state, and the busiest real constituency.
    district = str(state_rows["district"].value_counts().index[0])
    constituency = str(state_rows["constituency"].value_counts().index[0])

    return {
        "state": state,
        "district": district,
        "constituency": constituency,
        "state_projects": int(len(located[located["state"] == state])),
        "district_projects": int(len(located[(located["state"] == state) & (located["district"] == district)])),
        "constituency_projects": int(len(state_rows[state_rows["constituency"] == constituency])),
        "districts_in_state": int(located[located["state"] == state]["district"].nunique()),
    }


# ---------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------

def upsert_user(
    db: Session,
    *,
    email: str,
    role: str,
    full_name: str | None = None,
    password: str | None = None,
    scope_state: str | None = None,
    scope_district: str | None = None,
    scope_constituency: str | None = None,
    scope_mp_name: str | None = None,
) -> tuple[User, bool]:
    """Create or update one account. Returns (user, created)."""
    user = db.query(User).filter(User.email == email).first()
    created = user is None

    if user is None:
        user = User(email=email, password_hash=hash_password(password or DEFAULT_PASSWORD))
        db.add(user)
    elif password:
        user.password_hash = hash_password(password)

    user.role = role
    user.full_name = full_name
    user.is_active = True
    user.scope_state = scope_state
    user.scope_district = scope_district
    user.scope_constituency = scope_constituency
    user.scope_mp_name = scope_mp_name

    db.commit()
    db.refresh(user)
    return user, created


def describe(user: User) -> str:
    scope = resolve_user_scope(user)
    return (
        f"  {user.email:<42} {user.role:<24} "
        f"{scope.role:<20} {scope.scope_label}"
    )


# ---------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------

def cmd_seed(password: str | None) -> None:
    sync_schema()  # make sure the jurisdiction columns exist

    j = discover_jurisdictions()

    print("Jurisdictions selected from the real canonical dataset:")
    print(f"  State        : {j['state']} ({j['state_projects']} projects, {j['districts_in_state']} districts)")
    print(f"  District     : {j['district']} ({j['district_projects']} projects)")
    print(f"  Constituency : {j['constituency']} ({j['constituency_projects']} projects)")
    print()

    accounts = [
        dict(
            email="ministry@mplads.gov.in",
            role="Ministry",
            full_name="Ministry Monitoring Cell",
        ),
        dict(
            email="state.nodal@mplads.gov.in",
            role="State Nodal Officer",
            full_name=f"{j['state']} State Nodal Officer",
            scope_state=j["state"],
        ),
        dict(
            email="district.authority@mplads.gov.in",
            role="District Authority",
            full_name=f"{j['district']} District Authority",
            scope_state=j["state"],
            scope_district=j["district"],
        ),
        dict(
            email="mp@mplads.gov.in",
            role="Member of Parliament",
            full_name=f"Member of Parliament, {j['constituency']}",
            scope_state=j["state"],
            scope_constituency=j["constituency"],
        ),
    ]

    db = SessionLocal()
    try:
        for spec in accounts:
            user, created = upsert_user(db, password=password, **spec)
            print(("  created " if created else "  updated ") + describe(user).strip())
    finally:
        db.close()

    print()
    print(f"Password for all demo accounts: {password or DEFAULT_PASSWORD}")
    print("Change these before any non-local deployment.")


def cmd_list() -> None:
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.id).all()
        if not users:
            print("No accounts exist yet.")
            return
        print(f"  {'EMAIL':<42} {'ROLE TITLE':<24} {'RESOLVED':<20} SCOPE")
        for user in users:
            print(describe(user))
    finally:
        db.close()


def cmd_assign(args) -> None:
    sync_schema()

    if normalize_role(args.role) == "UNSCOPED":
        print(
            f"Warning: role title {args.role!r} does not resolve to a known role, "
            "so this account will be authorized for nothing.",
            file=sys.stderr,
        )

    db = SessionLocal()
    try:
        user, created = upsert_user(
            db,
            email=args.email,
            role=args.role,
            full_name=args.full_name,
            password=args.password,
            scope_state=args.state,
            scope_district=args.district,
            scope_constituency=args.constituency,
            scope_mp_name=args.mp_name,
        )
        print(("created" if created else "updated") + ":")
        print(describe(user))
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List accounts and their resolved scope.")
    parser.add_argument("--assign", action="store_true", help="Create/update one account.")
    parser.add_argument("--email")
    parser.add_argument("--role")
    parser.add_argument("--full-name", dest="full_name")
    parser.add_argument("--password")
    parser.add_argument("--state")
    parser.add_argument("--district")
    parser.add_argument("--constituency")
    parser.add_argument("--mp-name", dest="mp_name")
    args = parser.parse_args()

    if args.list:
        cmd_list()
    elif args.assign:
        if not args.email or not args.role:
            parser.error("--assign requires --email and --role")
        cmd_assign(args)
    else:
        cmd_seed(args.password)


if __name__ == "__main__":
    main()