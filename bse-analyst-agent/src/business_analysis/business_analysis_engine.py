from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pymupdf

from .models import BusinessAnalysisResult, Evidence, ManagementPromise
from ..agent import AnalysisOrchestrator


class BusinessAnalysisEngine:
    """LLM-driven qualitative business analysis.

    Python handles document discovery, page selection, provenance and output
    validation. Gemini performs the actual business interpretation. Financial
    statements, valuation and buy/sell scoring are deliberately excluded.
    """

    SECTION_KEYWORDS = (
        "business overview",
        "our business",
        "business model",
        "products",
        "services",
        "customers",
        "markets",
        "industry",
        "strategy",
        "strategic priorities",
        "growth strategy",
        "outlook",
        "competition",
        "competitive",
        "moat",
        "risk management",
        "principal risks",
        "risk factors",
        "research and development",
        "r&d",
        "acquisition",
        "capacity",
        "expansion",
        "geography",
        "management discussion",
        "director's report",
    )

    def __init__(
        self,
        reports_root: str | Path = "data/annual_reports",
        orchestrator: AnalysisOrchestrator | None = None,
    ):
        self.reports_root = Path(reports_root)
        self.orchestrator = orchestrator or AnalysisOrchestrator()

    def analyze(self, symbol: str) -> BusinessAnalysisResult:
        symbol = symbol.upper().strip()
        reports = self._reports(symbol)
        result = BusinessAnalysisResult(symbol=symbol)

        if not reports:
            result.limitations.append("No annual reports were found.")
            return result

        extracted: list[dict[str, Any]] = []

        for fiscal_year, path in reports[:10]:
            report_text = self._prepare_report(path)
            if not report_text:
                result.limitations.append(
                    f"{fiscal_year}: no readable business-research text was extracted."
                )
                continue

            try:
                output = self.orchestrator.extract_business_evidence(
                    report_text, fiscal_year
                )
                extracted.append(
                    {
                        "fiscal_year": fiscal_year,
                        "source_file": str(path),
                        "output": output.model_dump(),
                    }
                )
            except Exception as exc:
                result.limitations.append(
                    f"{fiscal_year}: LLM extraction failed: "
                    f"{type(exc).__name__}: {exc}"
                )

        if not extracted:
            return result

        try:
            synthesis = self.orchestrator.synthesize_business_research(
                json.dumps(extracted, ensure_ascii=False, indent=2)
            )
            payload = synthesis.model_dump()
        except Exception as exc:
            result.limitations.append(
                f"Cross-year LLM synthesis failed: {type(exc).__name__}: {exc}"
            )
            payload = {}

        result.executive_summary = str(payload.get("executive_summary", ""))
        result.business_model = payload.get("business_model", {})
        result.industry_and_market = payload.get("industry_and_market", {})
        result.products_and_customers = payload.get("products_and_customers", {})
        result.competitive_position = payload.get("competitive_position", {})
        result.strategy = payload.get("strategy", {})
        result.growth_drivers = list(payload.get("growth_drivers", []))
        result.economics = payload.get("economics", {})
        result.capital_allocation = payload.get("capital_allocation", {})
        result.business_risks = list(payload.get("business_risks", []))
        result.management = payload.get("management", {})
        result.ten_year_evolution = list(payload.get("ten_year_evolution", []))
        result.emerging_risks = list(payload.get("emerging_risks", []))
        result.limitations.extend(payload.get("limitations", []))

        result.evidence = self._build_evidence(extracted, payload.get("evidence", []))
        result.management_promises = self._build_promises(
            extracted, payload.get("management_promises", [])
        )
        result.management_execution = payload.get("management_execution", {})
        if not result.management_execution:
            result.management_execution = {
                "promises_extracted": len(result.management_promises),
                "note": "Execution status was synthesized from the supplied annual-report evidence.",
            }

        if len(reports) < 10:
            result.limitations.append(
                f"Only {len(reports)}/10 unique fiscal years were available."
            )

        return result

    def save(
        self,
        result: BusinessAnalysisResult,
        output_root: str | Path = "outputs/business_analysis",
    ) -> Path:
        destination = Path(output_root) / result.symbol / "business_analysis.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return destination

    def _reports(self, symbol: str) -> list[tuple[str, Path]]:
        """Discover annual reports from the configured root and downloader cache."""
        roots = [self.reports_root]
        download_root = Path("data/downloads")
        if download_root != self.reports_root:
            roots.append(download_root)

        by_year: dict[int, Path] = {}
        for root in roots:
            directory = root / symbol
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.pdf")):
                years = [int(x) for x in re.findall(r"20\d{2}", path.name)]
                if not years:
                    continue
                fiscal_year = max(years)
                # Prefer the configured research root when both contain a year.
                if fiscal_year not in by_year or root == self.reports_root:
                    by_year[fiscal_year] = path

        return [
            (f"FY{year}", by_year[year])
            for year in sorted(by_year, reverse=True)
        ]

    def _prepare_report(self, path: Path, max_pages: int = 20) -> str:
        """Select business-relevant pages; keywords only filter input, never create evidence."""
        doc = pymupdf.open(path)
        try:
            pages: dict[int, str] = {}
            for page_number, page in enumerate(doc, 1):
                text = page.get_text("text") or ""
                if not text.strip():
                    continue
                lower = text.lower()
                if any(keyword in lower for keyword in self.SECTION_KEYWORDS):
                    pages[page_number] = " ".join(text.split())[:5000]

            selected: set[int] = set()
            for page_number in pages:
                selected.update(
                    number
                    for number in range(page_number - 1, page_number + 2)
                    if number in pages
                )

            ordered = sorted(selected)[:max_pages]
            chunks = [
                f"--- PAGE {page_number} ---\n{pages[page_number]}"
                for page_number in ordered
            ]
            return "\n\n".join(chunks)
        finally:
            doc.close()

    @staticmethod
    def _build_evidence(
        extracted: list[dict[str, Any]],
        synthesized: list[dict[str, Any]],
    ) -> list[Evidence]:
        source_by_year = {
            item["fiscal_year"]: item["source_file"] for item in extracted
        }
        evidence: list[Evidence] = []
        seen: set[tuple[str, str, str, int | None]] = set()

        for item in synthesized:
            year = item.get("fiscal_year")
            source = item.get("source_file") or source_by_year.get(year, "")
            statement = str(item.get("statement", "")).strip()
            category = str(item.get("category", "business")).strip()
            page = item.get("page")
            confidence = str(item.get("confidence", "medium")).lower()
            if not statement:
                continue
            key = (category, statement, str(year), page)
            if key in seen:
                continue
            seen.add(key)
            evidence.append(
                Evidence(
                    category=category,
                    statement=statement,
                    source_file=source,
                    fiscal_year=str(year) if year else None,
                    page=page,
                    confidence=confidence,
                )
            )
        return evidence

    @staticmethod
    def _build_promises(
        extracted: list[dict[str, Any]],
        synthesized: list[dict[str, Any]],
    ) -> list[ManagementPromise]:
        source_by_year = {
            item["fiscal_year"]: item["source_file"] for item in extracted
        }
        promises: list[ManagementPromise] = []
        seen: set[tuple[str, str, int | None]] = set()

        for item in synthesized:
            statement = str(item.get("statement", "")).strip()
            year = item.get("fiscal_year")
            if not statement:
                continue
            key = (statement, str(year), item.get("page"))
            if key in seen:
                continue
            seen.add(key)
            promises.append(
                ManagementPromise(
                    statement=statement,
                    source_file=item.get("source_file")
                    or source_by_year.get(year, ""),
                    fiscal_year=str(year) if year else None,
                    page=item.get("page"),
                    promise_type=str(item.get("promise_type", "strategy")),
                    expected_outcome=item.get("expected_outcome"),
                    status=str(item.get("status", "unassessed")),
                )
            )
        return promises

    @staticmethod
    def _management_execution(promises: list[Any]) -> dict[str, Any]:
        return {
            "promises_extracted": len(promises),
            "outcome_matching": "llm_cross_year_synthesis",
        }
