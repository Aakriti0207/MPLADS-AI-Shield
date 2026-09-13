"""
Day 1 scope: app instance, CORS (for the future React dashboard), and
the projects, dashboard, and alerts routers.

JWT-auth update: added the auth router (register/login/me). Those
three endpoints stay open (no Depends(get_current_user)) -- everything
else is unaffected here; per-route protection is added directly on the
projects/dashboard/alerts routers themselves in Phase 3.

Phase 4: registered the analytics router (GET /analytics), protected
the same way as projects/dashboard/alerts.

Phase 5: registered the upload router (POST /upload-analyze), protected
the same way as projects/dashboard/alerts/analytics.

Phase 6 (security/production hardening):
    - CORS origins are now read from the CORS_ORIGINS env var instead of
      a hardcoded wildcard. See _resolve_cors_origins() below for the
      exact resolution rules (including a hard failure in production if
      it's left unset).
    - ENVIRONMENT (default "development") gates two things: whether
      interactive API docs (/docs, /redoc, /openapi.json) are exposed,
      and whether CORS_ORIGINS is required rather than defaulted.
    - A small set of defensive HTTP response headers is added to every
      response (see _SecurityHeadersMiddleware).
    - A catch-all exception handler ensures an unexpected/unhandled
      error returns a generic 500 with no internal detail, instead of
      whatever FastAPI's default would render -- see
      unhandled_exception_handler() below. Existing HTTPException-based
      responses (401/404/400/422/etc.) are untouched by this: Starlette
      matches the most specific registered handler for a given
      exception type, and HTTPException has its own handler, so this
      only ever catches exceptions nothing else already handles.

None of this is a substitute for HTTPS termination, a reverse proxy, or
real deployment infrastructure -- see the Phase 6 report's "Remaining
Security Limitations" for what's still deployment-dependent.
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.routes import alerts, analytics, auth, dashboard, projects, public, upload

load_dotenv()

logger = logging.getLogger("mplads.main")

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()


def _is_production() -> bool:
    """Reads ENVIRONMENT fresh on every call (rather than a frozen
    module-level snapshot) so this -- and anything built on it, like
    _resolve_cors_origins() below -- behaves correctly if the process
    environment changes between calls (this also makes it possible to
    unit-test with monkeypatch, without needing to reimport the app)."""
    return os.getenv("ENVIRONMENT", "development").strip().lower() == "production"


IS_PRODUCTION = _is_production()

DEFAULT_DEV_CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def _resolve_cors_origins() -> list[str]:
    """
    Resolve the CORS allow-list from the CORS_ORIGINS env var
    (comma-separated, e.g. "https://app.example.com,https://admin.example.com").

    - In production (ENVIRONMENT=production): CORS_ORIGINS is REQUIRED,
      exactly like DATABASE_URL/JWT_SECRET_KEY already are -- the app
      refuses to start rather than silently falling back to a wildcard
      or a localhost default that would be meaningless in production.
    - Outside production: if CORS_ORIGINS is unset, default to the
      local Vite dev server origins (http://localhost:5173 and
      http://127.0.0.1:5173) -- this project's actual local dev setup
      (see frontend/vite.config.js / frontend/.env), not a placeholder
      guess.
    - "*" is accepted verbatim (allow-all) if explicitly set -- this is
      still allowed since Phase 6 doesn't mandate blocking it, but it's
      logged as a warning since it defeats the purpose of an allow-list.
    """
    raw = os.getenv("CORS_ORIGINS")

    if raw is None or raw.strip() == "":
        if _is_production():
            raise RuntimeError(
                "CORS_ORIGINS is not set. In production (ENVIRONMENT=production), "
                "you must explicitly set CORS_ORIGINS to a comma-separated list of "
                "allowed frontend origin(s), e.g. "
                "CORS_ORIGINS=https://your-frontend.example.com"
            )
        return DEFAULT_DEV_CORS_ORIGINS

    if raw.strip() == "*":
        logger.warning(
            "CORS_ORIGINS=\"*\" allows requests from ANY origin. This is not "
            "recommended, even outside production."
        )
        return ["*"]

    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if not origins:
        raise RuntimeError("CORS_ORIGINS is set but contains no valid origin(s).")
    return origins


CORS_ORIGINS = _resolve_cors_origins()


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    A small, deliberately conservative set of defensive response headers
    -- not a general-purpose "security headers" package. Each one was
    picked because it's safe for a JSON API that also serves FastAPI's
    own Swagger UI (/docs) and doesn't require HTTPS to be meaningful:

    - X-Content-Type-Options: nosniff
        Stops browsers from MIME-sniffing responses into an unintended
        type. No effect on Swagger UI (it declares its own content
        types) or on the JSON responses this API returns.
    - X-Frame-Options: DENY
        Basic clickjacking protection. This API isn't meant to be
        embedded in an iframe anywhere.
    - Referrer-Policy: no-referrer
        Avoids leaking full request URLs (which can contain project IDs
        or other query data) via the Referer header on any outbound
        link/request a client might make from a page showing this data.
    - Cache-Control: no-store (added only when the route hasn't already
      set its own Cache-Control) on non-docs responses, since most
      responses here are authenticated project/business data that
      shouldn't be cached by intermediate proxies or the browser disk
      cache.

    Deliberately NOT included: Content-Security-Policy and
    Strict-Transport-Security. A CSP here would risk breaking Swagger
    UI's CDN-loaded assets without real testing against every asset it
    loads, and HSTS is only meaningful once this API is actually served
    over HTTPS by a reverse proxy -- adding it here would be a header
    with no effect at best and a misleading claim of protection at
    worst. Both are listed under Deferred in the Phase 6 report.
    """

    DOCS_PATHS = {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path not in self.DOCS_PATHS and "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        return response


app = FastAPI(
    title="MPLADS AI Shield",
    description="Explainable AI Early-Warning System for MPLADS fund utilization.",
    version="0.1.0",
    # Phase 6: interactive docs are a normal, low-risk convenience in
    # development, but expose the full API surface/schema to anyone who
    # can reach the API -- disabled by default in production. Set
    # ENVIRONMENT=production to disable them; leave ENVIRONMENT unset or
    # "development" (the default) to keep them on.
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

app.add_middleware(_SecurityHeadersMiddleware)

# CORS: origins come from CORS_ORIGINS (see _resolve_cors_origins() above)
# instead of a hardcoded wildcard. allow_credentials stays False -- this
# API is used with an Authorization: Bearer header (see app/auth.py and
# frontend/src/lib/api.js), never cookies, so there is no reason to also
# allow credentialed cross-origin requests. Methods/headers are scoped to
# what this API actually uses: GET/POST, and the Authorization/
# Content-Type headers the frontend sends (Content-Type must be listed
# explicitly for the JSON request bodies on /auth/register, /auth/login
# to pass CORS preflight -- it isn't a CORS-safelisted header for
# application/json).
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(dashboard.router)
app.include_router(public.router)
app.include_router(alerts.router)
app.include_router(analytics.router)
app.include_router(upload.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catch-all for anything not already handled by FastAPI's own
    HTTPException/RequestValidationError handlers (those remain fully in
    effect -- Starlette dispatches to the most specific registered
    handler for a given exception type, so a raised HTTPException still
    goes to FastAPI's built-in handler, never here).

    The real exception and traceback are logged server-side only; the
    client always gets a generic message, never a stack trace,
    exception message, file path, or any other internal detail.
    """
    logger.exception("Unhandled exception while processing %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


@app.get("/", tags=["health"])
def root():
    """Basic health check / landing route. Intentionally public."""
    return {"status": "ok", "service": "MPLADS AI Shield API"}