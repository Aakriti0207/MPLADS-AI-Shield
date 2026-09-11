"""Controlled canonical fixtures used by the Phase 10 evaluation."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    description: str
    expected_detector: str
    expected_reason: str


def _work_id(index: int) -> str:
    return f"WS/MP1/2024-2025/{index + 1}"


def canonical_fixture() -> pd.DataFrame:
    """Return 25 ordinary peer projects with complete lifecycle records."""
    rows = []
    for index in range(25):
        rows.append({
            "work_id": _work_id(index), "houses": "LS", "state": "State A",
            "mp": "MP One", "constituency": "Constituency A",
            "implementing_agency": "Agency A", "elected_nominated": "Elected",
            "work_category": "Road", "work_status": "Completed",
            "stages_present": "RECOMMENDED|SANCTIONED|COMPLETED|EXPENDITURE",
            "work_description": f"Road improvement project {index}",
            "recommended_amount": 1000000.0 + index * 1000, "sanction_amount": 1000000.0 + index * 1000,
            "amount_disbursed": 800000.0 + index * 800, "total_expenditure": 700000.0 + index * 700,
            "total_amount_in_progress": 50000.0, "n_expenditure_transactions": 8,
            "n_distinct_vendors": 3, "n_payment_success": 7,
            "n_payment_in_progress": 1, "recommended_date": "2024-01-01",
            "sanction_date": "2024-01-21", "completion_date": str(pd.Timestamp("2024-05-01") + pd.Timedelta(days=index)),
            "first_expenditure_date": "2024-02-01", "last_expenditure_date": "2024-04-01",
            "has_recommended_record": True, "has_sanctioned_record": True,
            "has_completed_record": True, "has_expenditure_record": True,
            "n_lifecycle_stages_present": 4, "any_field_conflict": False,
            "state_conflict": False, "mp_conflict": False, "constituency_conflict": False,
            "implementing_agency_conflict": False, "work_category_conflict": False,
            "work_description_conflict": False, "elected_nominated_conflict": False,
            "recommended_date_conflict": False,
            "flag_completion_without_sanction": False, "flag_expenditure_without_sanction": False,
            "flag_sanction_without_recommendation": False, "flag_completion_before_sanction": False,
            "flag_expenditure_before_recommendation": False, "flag_recommendation_after_sanction": False,
        })
    return pd.DataFrame(rows)


def scenario_inputs(scenario_id: str) -> tuple[pd.DataFrame, str, Scenario]:
    """Build one isolated scenario by changing only controlled fixture rows."""
    frame = canonical_fixture()
    target = _work_id(24)
    if scenario_id == "CLEAN_CONTROL":
        metadata = Scenario(scenario_id, "Untouched valid project", "NONE", "No injected anomaly")
    elif scenario_id == "FINANCIAL_ANOMALY":
        frame.loc[24, "total_expenditure"] = 50000000.0
        metadata = Scenario(scenario_id, "Extreme but valid expenditure", "FINANCIAL_ANOMALY", "Total expenditure is unusually high relative to peers")
    elif scenario_id == "TIMELINE_ANOMALY":
        frame.loc[24, "completion_date"] = "2029-06-15 00:00:00"
        metadata = Scenario(scenario_id, "Extreme lifecycle duration", "TIMELINE_ANOMALY", "Sanction-to-completion duration is unusually high")
    elif scenario_id == "COMPLIANCE_VIOLATION":
        frame.loc[24, "total_expenditure"] = 1200000.0
        metadata = Scenario(scenario_id, "Expenditure exceeds sanction", "COMPLIANCE", "C08 expenditure exceeds sanction")
    elif scenario_id == "DUPLICATE_SIMILARITY":
        frame.loc[23, "work_description"] = "Construction of community road near market"
        frame.loc[24, "work_description"] = "Construction of community road near market"
        metadata = Scenario(scenario_id, "Identical project descriptions", "DUPLICATE", "Exact description match identifies the paired Work IDs")
    elif scenario_id == "MULTI_EVIDENCE":
        frame.loc[24, "total_expenditure"] = 50000000.0
        frame.loc[24, "completion_date"] = "2029-06-15 00:00:00"
        metadata = Scenario(scenario_id, "Independent financial, timeline, and compliance signals", "RISK_FUSION", "Risk reasons include financial, timeline, and compliance evidence")
    elif scenario_id == "MISSING_DATA":
        frame.loc[24, ["amount_disbursed", "total_expenditure", "last_expenditure_date"]] = pd.NA
        frame.loc[24, ["has_expenditure_record", "n_expenditure_transactions", "n_payment_success", "n_payment_in_progress"]] = [False, pd.NA, pd.NA, pd.NA]
        metadata = Scenario(scenario_id, "Optional payment and expenditure fields removed", "MISSING_DATA", "Missing measurements remain not evaluable")
    elif scenario_id == "ZERO_VALUE":
        frame.loc[24, ["amount_disbursed", "total_expenditure", "total_amount_in_progress", "n_expenditure_transactions", "n_payment_success", "n_payment_in_progress"]] = [0.0, 0.0, 0.0, 0, 0, 0]
        metadata = Scenario(scenario_id, "Legitimate zero payment values", "ZERO_VALUE", "Zero is retained as a value and is distinct from missing")
    elif scenario_id == "INVALID_DATE_ORDER":
        frame.loc[24, "completion_date"] = "2023-12-01"
        frame.loc[24, "flag_completion_before_sanction"] = True
        metadata = Scenario(scenario_id, "Completion date precedes sanction date", "COMPLIANCE", "C05 chronology rule flags completion before sanction")
    elif scenario_id == "RISK_EXPLANATION":
        frame.loc[24, "total_expenditure"] = 50000000.0
        metadata = Scenario(scenario_id, "Known evidence requiring explanation", "RISK_FUSION", "WHY-risky output names the expenditure anomaly")
    else:
        raise ValueError(f"Unknown Phase 10 scenario: {scenario_id}")
    return frame, target, metadata


SCENARIO_IDS = (
    "CLEAN_CONTROL", "FINANCIAL_ANOMALY", "TIMELINE_ANOMALY", "COMPLIANCE_VIOLATION",
    "DUPLICATE_SIMILARITY", "MULTI_EVIDENCE", "MISSING_DATA", "ZERO_VALUE",
    "INVALID_DATE_ORDER", "RISK_EXPLANATION",
)