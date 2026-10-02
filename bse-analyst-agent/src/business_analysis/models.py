from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Evidence:
    category: str
    statement: str
    source_file: str
    fiscal_year: str | None = None
    page: int | None = None
    confidence: str = "medium"


@dataclass(frozen=True)
class ManagementPromise:
    statement: str
    source_file: str
    fiscal_year: str | None
    page: int | None = None
    promise_type: str = "strategy"
    expected_outcome: str | None = None
    status: str = "unassessed"


@dataclass
class BusinessAnalysisResult:
    symbol: str
    executive_summary: str = ""
    business_model: dict[str, Any] = field(default_factory=dict)
    industry_and_market: dict[str, Any] = field(default_factory=dict)
    competitive_position: dict[str, Any] = field(default_factory=dict)
    strategy: dict[str, Any] = field(default_factory=dict)
    growth_drivers: list[str] = field(default_factory=list)
    business_risks: list[dict[str, Any]] = field(default_factory=list)
    management: dict[str, Any] = field(default_factory=dict)
    management_promises: list[ManagementPromise] = field(default_factory=list)
    management_execution: dict[str, Any] = field(default_factory=dict)
    ten_year_evolution: list[str] = field(default_factory=list)
    emerging_risks: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
