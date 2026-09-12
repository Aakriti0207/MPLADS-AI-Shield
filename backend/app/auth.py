"""
Authentication utilities for the MPLADS AI backend.

Covers:
    - Password hashing/verification (bcrypt, used directly rather than
      via passlib -- passlib 1.7.x's bcrypt backend probes
      `bcrypt.__about__`, which was removed in bcrypt>=4.1, so calling
      passlib against a current bcrypt install raises/warns. Using the
      `bcrypt` package directly avoids that entirely and has no fewer
      security guarantees).
    - JWT creation/verification (PyJWT), configured entirely from
      environment variables -- never hardcoded.
    - `get_current_user`, a reusable FastAPI dependency that validates
      the bearer token and loads the corresponding active user.
    - `require_role`, a reusable dependency factory for future
      role-based authorization, kept deliberately separate from
      authentication.

JWT configuration is read from the environment (via app.database's
already-loaded .env, since app.database is imported first in practice,
but this module also calls load_dotenv() itself so it works standalone
too). JWT_SECRET_KEY has no default and is required -- the app refuses
to start without it, exactly like DATABASE_URL in app/database.py.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is not set. Create a .env file (see .env.example) "
        "with a strong, random JWT_SECRET_KEY."
    )

_bearer_scheme = HTTPBearer(auto_error=False)


# --- Password hashing ------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt. Returns a str suitable for
    storage in User.password_hash."""
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        # Malformed hash -- treat as a failed verification rather than
        # raising, so callers can't distinguish "bad hash" from "bad
        # password" (avoids leaking information about stored data).
        return False


# --- JWT creation / verification --------------------------------------

def create_access_token(user: User) -> str:
    """Create a signed JWT for the given user.

    Payload contains the minimum needed to identify the authenticated
    user without a DB round-trip on every request: subject (user id),
    email, role, and standard exp/iat claims.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt exceptions on failure
    (expired, invalid signature, malformed, etc.) -- callers should
    catch jwt.PyJWTError."""
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])


# --- FastAPI dependencies ---------------------------------------------

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency: read the Bearer token, validate the JWT, and
    return the corresponding active User. Raises HTTP 401 for any
    failure (missing token, invalid token, expired token, unknown or
    inactive user) without distinguishing which, to avoid leaking
    information to a caller probing for valid emails/tokens.
    """
    if credentials is None or not credentials.credentials:
        raise _CREDENTIALS_EXCEPTION

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise _CREDENTIALS_EXCEPTION

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        raise _CREDENTIALS_EXCEPTION

    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        raise _CREDENTIALS_EXCEPTION

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXCEPTION

    return user


def require_role(*allowed_roles: str):
    """
    Dependency factory for role-based authorization, kept separate from
    authentication (`get_current_user`).

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role("Administrator"))])

    Raises HTTP 403 (not 401 -- the user IS authenticated, just not
    authorized) if the current user's role isn't in `allowed_roles`.

    The role check always reads `current_user.role` as freshly loaded
    from the database by `get_current_user` (never a role claim taken
    directly from the JWT payload), so a role change takes effect on
    the user's very next request rather than only once their existing
    token expires.
    """

    def _check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return current_user

    return _check_role


# --- Phase 2: registration role policy ---------------------------------
#
# `User.role` (app/models.py) is intentionally a free-text string, not a
# fixed enum -- the application already lets people register with
# whatever descriptive title fits (e.g. "District Authority", "State
# Nodal Officer"; see tests/test_auth.py's test_register_new_user and
# app/models.py's docstring). Phase 2 does not change that. The one gap
# this closes: a caller must never be able to hand themselves
# administrative privilege just by naming it in the /auth/register
# request body. "Administrator" is the one role name this codebase
# already treats as privileged (see require_role's own docstring
# example above, and app/models.py's docstring) -- every other
# self-chosen title is left exactly as the caller submitted it.

# The privileged role label itself (also usable as an argument to
# require_role(...) wherever a genuinely admin-only capability exists).
ADMIN_ROLE = "Administrator"

# Role newly self-registered users receive when they did not request a
# privileged role. Matches the role already used as the standard
# authenticated-user fixture throughout the existing test suite (see
# tests/conftest.py's registered_user fixture), so it reflects this
# application's actual "ordinary user" role rather than a value invented
# for this change.
DEFAULT_REGISTRATION_ROLE = "District Authority"

# Matched case-insensitively so "administrator", "ADMIN", " Admin ",
# etc. are all treated the same way.
_PRIVILEGED_ROLE_NAMES = {"administrator", "admin"}


def resolve_registration_role(requested_role: str) -> str:
    """
    Decide the role a newly self-registered user actually receives.

    If `requested_role` names a privileged role (case-insensitively),
    it is silently replaced with DEFAULT_REGISTRATION_ROLE -- the
    caller still gets a 201 and a usable account, just never with
    administrative privilege. Any other value (including titles this
    application has never seen before) is returned unchanged, since
    ordinary role titles are not restricted, only the privileged one.

    There is deliberately no way to create an Administrator account
    through this public endpoint. Provisioning one requires a
    separately protected path (e.g. direct database access by an
    operator); Phase 2 does not add such a path since none currently
    exists and inventing one is out of scope here.
    """
    if requested_role.strip().lower() in _PRIVILEGED_ROLE_NAMES:
        return DEFAULT_REGISTRATION_ROLE
    return requested_role