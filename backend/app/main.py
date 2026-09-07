"""
Day 1 scope: app instance, CORS (for the future React dashboard), and
the projects, dashboard, and alerts routers.

JWT-auth update: added the auth router (register/login/me). Those
three endpoints stay open (no Depends(get_current_user)) -- everything
else is unaffected here; per-route protection is added directly on the
projects/dashboard/alerts routers themselves in Phase 3.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import alerts, auth, dashboard, projects

app = FastAPI(
    title="MPLADS AI Shield",
    description="Explainable AI Early-Warning System for MPLADS fund utilization.",
    version="0.1.0",
)

# Permissive CORS for local development so the React dashboard (running on
# a different port) can call this API. Fine for Day 1 / dev; should be
# tightened to specific origins before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # or just remove this line — False is the default
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(dashboard.router)
app.include_router(alerts.router)


@app.get("/", tags=["health"])
def root():
    """Basic health check / landing route."""
    return {"status": "ok", "service": "MPLADS AI Shield API"}