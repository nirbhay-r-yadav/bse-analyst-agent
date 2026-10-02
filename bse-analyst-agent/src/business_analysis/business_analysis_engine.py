from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .business_classifier import classify_business
from .evidence_extractor import AnnualReportEvidenceExtractor
from .models import BusinessAnalysisResult


class BusinessAnalysisEngine:
    """Evidence-first qualitative business analysis.

    Financial statements, valuation and investment scoring are deliberately
    excluded. The output focuses on business model, strategy, management
    promises, operating risks and source-backed evidence.
    """

    def __init__(self, reports_root: str | Path = "data/annual_reports"):
        self.reports_root = Path(reports_root)
        self.extractor = AnnualReportEvidenceExtractor()

    def analyze(self, symbol: str) -> BusinessAnalysisResult:
        symbol = symbol.upper().strip()
        reports = self._reports(symbol)
        result = BusinessAnalysisResult(symbol=symbol)
        all_text: list[str] = []

        for fiscal_year, path in reports[:10]:
            evidence, promises = self.extractor.extract(
                path, fiscal_year=fiscal_year
            )
            result.evidence.extend(evidence)
            result.management_promises.extend(promises)
            try:
                import pymupdf

                doc = pymupdf.open(path)
                try:
                    all_text.append(
                        "\n".join(page.get_text("text") for page in doc)
                    )
                finally:
                    doc.close()
            except Exception:
                continue

        combined = "\n".join(all_text)
        result.business_model = classify_business(combined)
        result.management_execution = self._management_execution(
            result.management_promises
        )
        result.risks = self._risk_signals(combined)
        return result

    def save(
        self,
        result: BusinessAnalysisResult,
        output_root: str | Path = "outputs/business_analysis",
    ) -> Path:
        destination = Path(output_root) / result.symbol / "business_analysis.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(result.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        return destination

    def _reports(self, symbol: str) -> list[tuple[str, Path]]:
        directory = self.reports_root / symbol
        if not directory.exists():
            return []

        files: list[tuple[str, Path]] = []
        for path in sorted(directory.glob("*.pdf")):
            years = [
                int(x)
                for x in __import__("re").findall(r"20\d{2}", path.name)
            ]
            fiscal = f"FY{max(years)}" if years else None
            if fiscal:
                files.append((fiscal, path))
        return files

    @staticmethod
    def _management_execution(
        promises: list[Any],
    ) -> dict[str, Any]:
        by_type: dict[str, int] = {}
        for promise in promises:
            by_type[promise.promise_type] = (
                by_type.get(promise.promise_type, 0) + 1
            )
        return {
            "promises_extracted": len(promises),
            "promise_types": by_type,
            "outcome_matching": "not_yet_automated",
            "note": (
                "Promise-to-outcome matching will be added after deterministic "
                "promise normalization and cross-year entity matching are tested."
            ),
        }

    @staticmethod
    def _risk_signals(text: str) -> dict[str, Any]:
        lower = text.lower()
        terms = {
            "customer_concentration": (
                "customer concentration",
                "single customer",
                "top customer",
            ),
            "regulatory": (
                "regulatory risk",
                "regulatory changes",
                "regulation",
            ),
            "competition": (
                "intense competition",
                "competitive pressure",
                "competition",
            ),
            "commodity": (
                "commodity prices",
                "raw material prices",
                "commodity risk",
            ),
            "fx": (
                "foreign exchange risk",
                "currency risk",
                "forex",
            ),
            "cyclicality": (
                "cyclical",
                "industry cycle",
                "downcycle",
            ),
        }
        return {
            "signals": {
                name: any(term in lower for term in words)
                for name, words in terms.items()
            }
        }
