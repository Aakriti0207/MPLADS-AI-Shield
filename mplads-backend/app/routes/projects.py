"""
Routes for the `projects` resource.

Keeps route logic thin: sessions come from the `get_db` dependency,
queries go straight against the SQLAlchemy model, and serialization
is handled entirely by the Pydantic response_model. No business logic
lives here beyond a 404 check.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project
from app.schemas import ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=List[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    """
    Return all projects.

    No pagination for Day 1: the MVP dataset is small enough that a
    full list is simple and sufficient. We can add skip/limit query
    params later if/when the dataset grows enough to warrant it.
    """
    return db.query(Project).all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)):
    """Return a single project by its project_id, or 404 if not found."""
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )
    return project
