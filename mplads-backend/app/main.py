"""
FastAPI application entry point for the MPLADS AI backend.

Day 1 scope: app instance, CORS (for the future React dashboard), and
the `projects` router only. Dashboard and alerts routes come later.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import projects

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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)


@app.get("/", tags=["health"])
def root():
    """Basic health check / landing route."""
    return {"status": "ok", "service": "MPLADS AI Shield API"}
