"""Pure, deterministic Phase 4 rule evaluations.

Rules consume only validated Phase 3 feature columns. They do not load files,
perform classification, or assign a numeric score.
"""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from ml.compliance.schemas import ComplianceFinding, RuleMetadata


PASS = "PASS"
FLAG = "FLAG"
NOT_EVALUABLE = "NOT_EVALUABLE"
WARNING = "WARNING"
HIGH = "HIGH"


RULE_METADATA = {
    "C01": RuleMetadata(
        "C01", "Recommendation to sanction timeline", "TIMELINE", WARNING,
        "Sanction should generally be issued within 45 days of recommendation.",
        "MPLADS Guidelines 2023, Para 3.2.4",
    ),
    "C02": RuleMetadata(
        "C02", "Sanction to completion timeline", "TIMELINE", WARNING,
        "The standard completion period should generally not exceed one year.",
        "MPLADS Guidelines 2023, Para 3.2.12",
    ),
    "C03": RuleMetadata("C03", "Completion without sanction", "LIFECYCLE", HIGH, "A completion record exists without a sanction record."),
    "C04": RuleMetadata("C04", "Expenditure without sanction", "LIFECYCLE", HIGH, "Positive expenditure exists without a sanction record."),
    "C05": RuleMetadata("C05", "Completion before sanction", "LIFECYCLE", HIGH, "Completion occurred before sanction."),
    "C06": RuleMetadata("C06", "Expenditure before recommendation", "LIFECYCLE", HIGH, "Expenditure occurred before recommendation."),
    "C07": RuleMetadata("C07", "Recommendation after sanction", "LIFECYCLE", HIGH, "Recommendation occurred after sanction."),
    "C08": RuleMetadata("C08", "Expenditure exceeds sanction", "FINANCIAL", HIGH, "Total expenditure exceeds the sanctioned amount."),
    "C09": RuleMetadata("C09", "Disbursement exceeds sanction", "FINANCIAL", HIGH, "Disbursed amount exceeds the sanctioned amount."),
    "C10": RuleMetadata(
        "C10", "Sanction below minimum amount", "FINANCIAL", WARNING,
        "The normal minimum sanctioned amount for an individual work is ₹2.5 lakh; exceptions may exist.",
        "MPLADS Guidelines 2023 (minimum sanctioned amount provision)",
    ),
    "C11": RuleMetadata(
        "C11", "Sanction exceeds recommendation", "FINANCIAL", WARNING,
        "Sanction exceeds recommendation; required MP consent cannot be verified from available data.",
        "MPLADS Guidelines 2023 (MP consent provision)",
    ),
    "DQ01": RuleMetadata(
        "DQ01", "Source/data conflict", "DATA_QUALITY", WARNING,
        "Source fields conflict and require data-quality review; this is not a compliance violation.",
        None,
    ),
}

RULE_IDS = tuple(RULE_METADATA)


def _present(row: pd.Series, column: str) -> bool:
    return column in row.index and pd.notna(row[column])


def _available(row: pd.Series, column: str) -> bool:
    return _present(row, column) and bool(row[column])


def _number(row: pd.Series, column: str) -> float | None:
    if not _present(row, column):
        return None
    value = pd.to_numeric(row[column], errors="coerce")
    return None if pd.isna(value) else float(value)


def _value(row: pd.Series, column: str) -> Any:
    value = row[column] if column in row.index else None
    if pd.isna(value) if not isinstance(value, (list, dict)) else False:
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _finding(row: pd.Series, rule_id: str, status: str, message: str, evidence: dict[str, Any]) -> ComplianceFinding:
    metadata = RULE_METADATA[rule_id]
    return ComplianceFinding(
        work_id=str(row["work_id"]), rule_id=rule_id, category=metadata.category,
        status=status, severity=metadata.severity, message=message, evidence=evidence,
    )


def evaluate_c01(row: pd.Series) -> ComplianceFinding:
    days = _number(row, "recommendation_to_sanction_days")
    evidence = {"observed_days": days, "threshold_days": 45}
    if not (_available(row, "is_recommended_date_available") and _available(row, "is_sanction_date_available")) or days is None or days < 0:
        return _finding(row, "C01", NOT_EVALUABLE, "Recommendation-to-sanction timeline cannot be evaluated from the available valid dates.", evidence)
    if days > 45:
        return _finding(row, "C01", FLAG, f"Sanction was issued {int(days)} days after recommendation; this timeline deviation requires review and is not definitive legal wrongdoing.", evidence)
    return _finding(row, "C01", PASS, "Sanction was issued within 45 days of recommendation.", evidence)


def evaluate_c02(row: pd.Series) -> ComplianceFinding:
    days = _number(row, "sanction_to_completion_days")
    evidence = {"observed_days": days, "threshold_days": 365}
    if not (_available(row, "is_sanction_date_available") and _available(row, "is_completion_date_available")) or days is None or days < 0:
        return _finding(row, "C02", NOT_EVALUABLE, "Sanction-to-completion timeline cannot be evaluated from the available valid dates.", evidence)
    if days > 365:
        return _finding(row, "C02", FLAG, f"The standard one-year completion period was exceeded by a duration of {int(days)} days; exceptions or justification may exist and require review.", evidence)
    return _finding(row, "C02", PASS, "Completion occurred within the standard one-year period.", evidence)


def evaluate_c03(row: pd.Series) -> ComplianceFinding:
    completion = _available(row, "is_completion_date_available")
    sanction = _available(row, "is_sanction_date_available")
    evidence = {"completion_date_available": completion, "sanction_date_available": sanction}
    if not _present(row, "is_completion_date_available") or not _present(row, "is_sanction_date_available"):
        return _finding(row, "C03", NOT_EVALUABLE, "Completion-without-sanction cannot be evaluated because lifecycle availability data is missing.", evidence)
    if completion and not sanction:
        return _finding(row, "C03", FLAG, "A completion record exists without a sanction record.", evidence)
    return _finding(row, "C03", PASS, "No completion-without-sanction condition was found.", evidence)


def evaluate_c04(row: pd.Series) -> ComplianceFinding:
    expenditure = _number(row, "total_expenditure")
    sanction = _available(row, "is_sanction_date_available")
    evidence = {"total_expenditure": expenditure, "sanction_date_available": sanction}
    if expenditure is None or not _present(row, "is_sanction_date_available"):
        return _finding(row, "C04", NOT_EVALUABLE, "Expenditure-without-sanction cannot be evaluated because required data is missing.", evidence)
    if expenditure > 0 and not sanction:
        return _finding(row, "C04", FLAG, "Positive expenditure exists without a sanction record.", evidence)
    return _finding(row, "C04", PASS, "No expenditure-without-sanction condition was found.", evidence)


def _chronology_rule(row: pd.Series, rule_id: str, flag_column: str, date_columns: tuple[str, str], description: str) -> ComplianceFinding:
    evidence = {column: _value(row, column) for column in date_columns}
    if not all(_present(row, column) for column in date_columns):
        return _finding(row, rule_id, NOT_EVALUABLE, f"{description} cannot be evaluated because a required date is missing.", evidence)
    flagged = _value(row, flag_column)
    evidence["phase3_flag"] = bool(flagged) if flagged is not None else None
    if flagged is None:
        return _finding(row, rule_id, NOT_EVALUABLE, f"{description} cannot be evaluated because the Phase 3 chronology flag is missing.", evidence)
    if bool(flagged):
        return _finding(row, rule_id, FLAG, description + ".", evidence)
    return _finding(row, rule_id, PASS, "No chronological inconsistency was found.", evidence)


def evaluate_c05(row: pd.Series) -> ComplianceFinding:
    return _chronology_rule(row, "C05", "flag_completion_before_sanction", ("is_completion_date_available", "is_sanction_date_available"), "Completion occurred before sanction")


def evaluate_c06(row: pd.Series) -> ComplianceFinding:
    return _chronology_rule(row, "C06", "flag_expenditure_before_recommendation", ("is_first_expenditure_date_available", "is_recommended_date_available"), "Expenditure occurred before recommendation")


def evaluate_c07(row: pd.Series) -> ComplianceFinding:
    return _chronology_rule(row, "C07", "flag_recommendation_after_sanction", ("is_recommended_date_available", "is_sanction_date_available"), "Recommendation occurred after sanction")


def _amount_comparison(row: pd.Series, rule_id: str, left_column: str, right_column: str, label: str) -> ComplianceFinding:
    left = _number(row, left_column)
    right = _number(row, right_column)
    evidence = {left_column: left, right_column: right}
    if left is None or right is None:
        return _finding(row, rule_id, NOT_EVALUABLE, f"{label} cannot be evaluated because a required amount is missing.", evidence)
    if left > right:
        return _finding(row, rule_id, FLAG, f"{label}: {left_column} exceeds {right_column}.", evidence)
    return _finding(row, rule_id, PASS, f"{left_column} does not exceed {right_column}.", evidence)


def evaluate_c08(row: pd.Series) -> ComplianceFinding:
    return _amount_comparison(row, "C08", "total_expenditure", "sanction_amount", "Total expenditure exceeds sanction")


def evaluate_c09(row: pd.Series) -> ComplianceFinding:
    return _amount_comparison(row, "C09", "amount_disbursed", "sanction_amount", "Disbursement exceeds sanction")


def evaluate_c10(row: pd.Series) -> ComplianceFinding:
    amount = _number(row, "sanction_amount")
    evidence = {"sanction_amount": amount, "threshold_amount": 250000}
    if amount is None:
        return _finding(row, "C10", NOT_EVALUABLE, "Minimum sanction amount cannot be evaluated because sanction amount is missing.", evidence)
    if amount < 250000:
        return _finding(row, "C10", FLAG, "Sanction is below the normal minimum of ₹2.5 lakh; permitted exceptions may exist and require review.", evidence)
    return _finding(row, "C10", PASS, "Sanction meets the normal minimum amount threshold.", evidence)


def evaluate_c11(row: pd.Series) -> ComplianceFinding:
    recommended = _number(row, "recommended_amount")
    sanctioned = _number(row, "sanction_amount")
    evidence = {"recommended_amount": recommended, "sanction_amount": sanctioned}
    if recommended is None or sanctioned is None:
        return _finding(row, "C11", NOT_EVALUABLE, "Sanction-versus-recommendation cannot be evaluated because a required amount is missing.", evidence)
    if sanctioned > recommended:
        return _finding(row, "C11", FLAG, "Sanction amount exceeds the recommended amount; required consent cannot be verified from available data.", evidence)
    return _finding(row, "C11", PASS, "Sanction amount does not exceed the recommended amount.", evidence)


def evaluate_dq01(row: pd.Series) -> ComplianceFinding:
    conflict = _value(row, "any_field_conflict")
    evidence = {"any_field_conflict": conflict}
    if conflict is None:
        return _finding(row, "DQ01", NOT_EVALUABLE, "Source/data conflict cannot be evaluated because the conflict indicator is missing.", evidence)
    if bool(conflict):
        return _finding(row, "DQ01", FLAG, "Source fields conflict and require data-quality review; this is not a compliance violation.", evidence)
    return _finding(row, "DQ01", PASS, "No source/data conflict was found.", evidence)


RULE_EVALUATORS: dict[str, Callable[[pd.Series], ComplianceFinding]] = {
    "C01": evaluate_c01, "C02": evaluate_c02, "C03": evaluate_c03,
    "C04": evaluate_c04, "C05": evaluate_c05, "C06": evaluate_c06,
    "C07": evaluate_c07, "C08": evaluate_c08, "C09": evaluate_c09,
    "C10": evaluate_c10, "C11": evaluate_c11, "DQ01": evaluate_dq01,
}