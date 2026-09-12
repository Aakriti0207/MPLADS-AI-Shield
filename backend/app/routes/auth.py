"""
Authentication routes: register, login, and the current-user profile.

Kept deliberately thin, matching the style of the existing routes
(projects.py, dashboard.py, alerts.py): sessions come from `get_db`,
business logic lives in app/auth.py, and response shape is handled by
the Pydantic response_model.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    resolve_registration_role,
    verify_password,
)
from app.database import get_db
from app.models import User
from app.rate_limit import rate_limit
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# Phase 6: basic brute-force/abuse deterrent on the two credential-facing
# endpoints. See app/rate_limit.py's module docstring for exactly what
# this does and doesn't protect against (in short: per-process, per-IP,
# in-memory -- a real deployment behind multiple workers/instances still
# needs a proper gateway-level or shared-store rate limiter).
LOGIN_RATE_LIMIT = rate_limit(max_requests=5, window_seconds=60)
REGISTER_RATE_LIMIT = rate_limit(max_requests=5, window_seconds=60)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(REGISTER_RATE_LIMIT)],
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user.

    Rejects duplicate emails, hashes the password (never stores
    plaintext), and returns the safe user profile -- never the
    password hash.

    Phase 2: the role actually stored is resolved through
    resolve_registration_role(), never assigned directly from
    payload.role -- this prevents a caller from granting themselves
    administrative privilege simply by naming it in the request body.
    See app/auth.py's resolve_registration_role() docstring.
    """
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=resolve_registration_role(payload.role),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(LOGIN_RATE_LIMIT)])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with email + password and return a JWT.

    Uses one generic 401 message for both "no such user" and "wrong
    password" so the error doesn't reveal which emails are registered.
    """
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
    )

    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise invalid_credentials

    if not user.is_active:
        raise invalid_credentials

    access_token = create_access_token(user)
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's safe profile."""
    return current_user