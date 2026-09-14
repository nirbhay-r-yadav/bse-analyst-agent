"""Centralized, deterministic scoring engine.

This module is the single home for score construction. It deliberately reads
persisted analysis artifacts rather than fetching market data or parsing source
documents. Analysis modules produce facts; this module turns those facts into
scores. The initial implementation preserves the project's current scoring
semantics so we can verify them before changing the model.

Future artifacts such as ``business_analysis.json`` can be added without
moving scoring logic back into DeepScannerEngine.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping


LEGACY_GOVERNANCE_POINTS = {"A": 10, "B": 8, "C": 4, "D": 0}


@dataclass(frozen=True)
class ScoreBreakdown:
    name: str
    score: float
    maximum: float
    normalized_100: float
    components: dict[str, Any]


@dataclass(frozen=True)
class ScoringResult:
    symbol: str
    governance: ScoreBreakdown
    fundamentals: ScoreBreakdown
    business: ScoreBreakdown | None
    valuation: ScoreBreakdown
    decision: float
    decision_components: dict[str, float]
    decision_formula: str

    def to_dict(self) -> dict[str, Any]:
        def breakdown(value: ScoreBreakdown | None) -> Any:
            if value is None:
                return None
            return {
                "score": value.score,
                "maximum": value.maximum,
                "normalized_100": value.normalized_100,
                "components": value.components,
            }

        return {
            "symbol": self.symbol,
            "governance": breakdown(self.governance),
            "fundamentals": breakdown(self.fundamentals),
            "business": breakdown(self.business),
            "valuation": breakdown(self.valuation),
            "decision": self.decision,
            "decision_components": self.decision_components,
            "decision_formula": self.decision_formula,
        }


class ScoringEngine:
    """Read persisted analysis JSON and calculate auditable score breakdowns."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    def _read(self, filename: str) -> dict[str, Any] | None:
        path = os.path.join(self.output_dir, filename)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        if not isinstance(payload, dict):
            raise ValueError(f"{filename} must contain a JSON object")
        return payload

    @staticmethod
    def _normalise(score: float, maximum: float) -> float:
        if maximum <= 0:
            return 0.0
        return round(max(0.0, min(100.0, score / maximum * 100.0)), 2)

    def _governance(self, payload: Mapping[str, Any]) -> ScoreBreakdown:
        grade = str(payload.get("governance_grade") or "D").upper()
        score = float(LEGACY_GOVERNANCE_POINTS.get(grade, 0))
        return ScoreBreakdown(
            name="governance",
            score=score,
            maximum=10.0,
            normalized_100=self._normalise(score, 10.0),
            components={"grade": score, "grade_label": grade},
        )

    def _fundamentals(self, payload: Mapping[str, Any]) -> ScoreBreakdown:
        components_raw = payload.get("financial_components") or {}
        components = {
            str(key): float(value or 0)
            for key, value in components_raw.items()
            if key != "governance"
        }
        score = float(sum(components.values()))
        # Current financial quality has five 20-point buckets, but governance
        # is removed before the score is persisted. Therefore the current raw
        # fundamentals score has an 80-point maximum, not a 100-point maximum.
        maximum = 80.0
        return ScoreBreakdown(
            name="fundamentals",
            score=score,
            maximum=maximum,
            normalized_100=self._normalise(score, maximum),
            components=components,
        )

    def _business(self, payload: Mapping[str, Any] | None) -> ScoreBreakdown | None:
        if not payload:
            return None
        components_raw = payload.get("business_components") or payload.get("components") or {}
        if not components_raw:
            score = payload.get("business_score")
            if score is None:
                return None
            return ScoreBreakdown("business", float(score), 100.0, self._normalise(float(score), 100.0), {})
        components = {str(k): float(v or 0) for k, v in components_raw.items()}
        maximum = float(payload.get("score_maximum") or sum(max(0.0, value) for value in components.values()) or 100.0)
        score = float(payload.get("business_score") if payload.get("business_score") is not None else sum(components.values()))
        return ScoreBreakdown("business", score, maximum, self._normalise(score, maximum), components)

    def _valuation(self, financial: Mapping[str, Any]) -> ScoreBreakdown:
        valuation = financial.get("valuation") or {}
        score = 0.0
        state = "UNAVAILABLE"
        if valuation.get("available"):
            price = float(valuation.get("current_price") or 0)
            fair_value = float(valuation.get("fair_value") or 0)
            buy_below = float(valuation.get("buy_below") or 0)
            if buy_below > 0 and price <= buy_below:
                score = 10.0
                state = "MARGIN_OF_SAFETY"
            elif fair_value > 0 and price <= fair_value:
                score = 6.0
                state = "BELOW_FAIR_VALUE"
            else:
                state = "ABOVE_FAIR_VALUE"
        return ScoreBreakdown(
            name="valuation",
            score=score,
            maximum=10.0,
            normalized_100=self._normalise(score, 10.0),
            components={"state": state, "score": score},
        )

    def calculate(self) -> ScoringResult:
        governance_json = self._read("corporate_governance.json")
        financial_json = self._read("financial_analysis.json")
        business_json = self._read("business_analysis.json")
        if governance_json is None:
            raise FileNotFoundError("corporate_governance.json is required")
        if financial_json is None:
            raise FileNotFoundError("financial_analysis.json is required")

        governance = self._governance(governance_json)
        fundamentals = self._fundamentals(financial_json)
        business = self._business(business_json)
        valuation = self._valuation(financial_json)

        # This is intentionally the current legacy decision formula. We are
        # documenting it first; a future migration can replace it with an
        # explicit 100-point weighted model after verification passes.
        decision_components = {
            "fundamental_quality": fundamentals.score,
            "valuation": valuation.score,
            "governance": governance.score,
        }
        decision = round(sum(decision_components.values()), 2)
        symbol = str(governance_json.get("symbol") or financial_json.get("symbol") or "")
        return ScoringResult(
            symbol=symbol,
            governance=governance,
            fundamentals=fundamentals,
            business=business,
            valuation=valuation,
            decision=decision,
            decision_components=decision_components,
            decision_formula="fundamentals_raw + valuation_raw + governance_raw",
        )

    def verify_persisted_decision(self, result: ScoringResult) -> dict[str, Any]:
        payload = self._read("investment_decision.json")
        if payload is None:
            return {"status": "MISSING", "checks": {"investment_decision.json": False}}

        persisted_decision = payload.get("decision_score")
        persisted_fundamentals = payload.get("financial", {}).get("financial_score")
        persisted_governance = payload.get("governance", {}).get("grade")

        checks = {
            "decision_matches_recalculation": persisted_decision is not None and float(persisted_decision) == result.decision,
            "fundamentals_matches_recalculation": persisted_fundamentals is not None and float(persisted_fundamentals) == result.fundamentals.score,
            "governance_grade_matches": persisted_governance is not None and str(persisted_governance).upper() == result.governance.components["grade_label"],
            "decision_is_0_to_100": 0 <= result.decision <= 100,
            "governance_uses_100_point_scale": result.governance.maximum == 100,
            "fundamentals_uses_100_point_scale": result.fundamentals.maximum == 100,
        }
        return {
            "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "persisted": {
                "decision": persisted_decision,
                "fundamentals": persisted_fundamentals,
                "governance_grade": persisted_governance,
            },
            "recalculated": result.to_dict(),
        }


def score_outputs(output_dir: str) -> dict[str, Any]:
    """Convenience API used by tests, CLI tooling and future Deep Scan stages."""
    engine = ScoringEngine(output_dir)
    result = engine.calculate()
    verification = engine.verify_persisted_decision(result)
    return {"scores": result.to_dict(), "verification": verification}
