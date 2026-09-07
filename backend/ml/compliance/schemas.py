"""Small structured representations used by the Phase 4 rule engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RuleMetadata:
    rule_id: str
    name: str
    category: str
    severity: str
    description: str
    official_source: str | None = None


@dataclass(frozen=True)
class ComplianceFinding:
    work_id: str
    rule_id: str
    category: str
    status: str
    severity: str
    message: str
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)