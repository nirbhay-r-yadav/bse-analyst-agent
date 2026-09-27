"""Stable contracts for the research application's replaceable modules.

Protocols describe what the application expects from each major capability.
They deliberately contain no implementation imports, so a module can be
rewritten, optimized, or replaced without forcing changes throughout the app.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence


class UniverseDiscovery(Protocol):
    def run(self, refresh: bool = False, top: int = 50, limit: int | None = None, output_dir: str = "./outputs") -> Sequence[Mapping[str, Any]]:
        ...


class AnnualReportDownloader(Protocol):
    def download_report(self, symbol: str, custom_filename: str | None = None, force_redownload: bool = False) -> str | None:
        ...


class FinancialHistorySource(Protocol):
    def discover(self, symbol: str) -> Sequence[Mapping[str, Any]]:
        ...

    def build_history(self, symbol: str) -> Sequence[Mapping[str, Any]]:
        ...


class DocumentExtractor(Protocol):
    def extract_critical_sections(self) -> Mapping[str, str]:
        ...


class CorporateRiskAssessor(Protocol):
    def assess(self, **inputs: Any) -> Any:
        ...


class FinancialAnalysis(Protocol):
    def calculate_ratios(self, history: Any) -> Mapping[str, Any]:
        ...

    def calculate_quality(self, ratios: Mapping[str, Any], governance_clean: bool = True) -> Mapping[str, Any]:
        ...

    def calculate_valuation(self, *args: Any, **kwargs: Any) -> Mapping[str, Any]:
        ...

    def determine_recommendation(self, *args: Any, **kwargs: Any) -> Mapping[str, Any]:
        ...


class StockResearch(Protocol):
    def analyze(self, symbol: str, price: float | None = None, shares_cr: float | None = None, target_pe: float = 25.0, mos: float = 20.0) -> Mapping[str, Any] | None:
        ...


class DeepScanner(Protocol):
    def analyze_candidate(self, row: Mapping[str, Any], live_filings: bool = True) -> Mapping[str, Any]:
        ...

    def run(self, input_csv: str = "./outputs/small_microcap_universe.csv", top: int = 10, deep_limit: int = 20, output_dir: str = "./outputs", live_filings: bool = True) -> Sequence[Mapping[str, Any]]:
        ...


class ReportWriter(Protocol):
    def write(self, *args: Any, **kwargs: Any) -> str:
        ...


PUBLIC_MODULE_APIS = {
    "discovery": "src.universe_scan.UniverseScanEngine.run",
    "risk": "src.corporate_risk.CorporateRiskEngine.assess",
    "financial_engine": "src.financial_engine.FinancialAnalysisEngine",
    "financial_ratios": "src.financial_tools.calculate_fundamental_ratios",
    "quality_score": "src.financial_tools.calculate_quality_score",
    "valuation": "src.financial_tools.calculate_pe_valuation",
    "recommendation": "src.financial_tools.determine_final_recommendation",
    "annual_report": "src.nse_downloader.NSEDownloader.download_report",
    "annual_report_history": "src.build_financial_history.build",
    "financial_history": "src.financial_history.FinancialHistoryStore",
    "financial_history_adapter": "src.financial_history_adapter.to_company_history",
    "document_parser": "src.doc_parser.FinancialDocParser.extract_critical_sections",
    "stock_research": "src.stock_research_engine.StockResearchEngine.analyze",
    "deep_scan": "src.deep_scanner.DeepScannerEngine.run",
    "reporting": "src.reporting.InvestmentReportWriter.write",
}
