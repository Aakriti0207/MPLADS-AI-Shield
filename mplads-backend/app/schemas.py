"""
Pydantic schemas for the MPLADS AI backend.

Day 1 scope: response schema(s) for the `projects` endpoints only.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProjectOut(BaseModel):
    """Response shape for a single project, mirroring the `projects` table."""

    model_config = ConfigDict(from_attributes=True)

    project_id: str
    state: str
    district: str
    constituency: Optional[str] = None
    mp_name: Optional[str] = None
    work_type: Optional[str] = None
    implementing_agency: Optional[str] = None

    sanctioned_amount: Optional[Decimal] = None
    estimated_cost: Optional[Decimal] = None
    expenditure: Optional[Decimal] = None

    financial_progress: Optional[Decimal] = None
    physical_progress: Optional[Decimal] = None

    sanction_date: Optional[date] = None
    start_date: Optional[date] = None
    expected_completion: Optional[date] = None
    actual_completion: Optional[date] = None

    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

    status: Optional[str] = None

    created_at: datetime
    updated_at: datetime


class DashboardStats(BaseModel):
    """Aggregate statistics computed live from the `projects` table."""

    total_projects: int
    total_sanctioned_amount: Decimal
    total_expenditure: Decimal
    average_financial_progress: Optional[Decimal] = None
    average_physical_progress: Optional[Decimal] = None
    active_projects: int
    completed_projects: int
    delayed_projects: int
