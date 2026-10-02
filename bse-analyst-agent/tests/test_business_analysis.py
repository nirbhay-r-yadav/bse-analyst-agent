from pathlib import Path

from src.business_analysis.business_analysis_engine import BusinessAnalysisEngine
from src.business_analysis.models import BusinessAnalysisResult


def test_result_serializes_meaningful_business_sections_without_financial_analysis():
    result = BusinessAnalysisResult(symbol="INFY")
    payload = result.to_dict()

    assert payload["symbol"] == "INFY"
    assert "products_and_customers" in payload
    assert "economics" in payload
    assert "capital_allocation" in payload
    assert "business_risks" in payload
    assert "management_execution" in payload
    assert "financial_ratios" not in payload
    assert "valuation" not in payload


def test_report_discovery_deduplicates_fiscal_years(tmp_path: Path):
    root = tmp_path / "annual_reports" / "INFY"
    root.mkdir(parents=True)
    (root / "AR_2025_2026.pdf").write_bytes(b"pdf")
    (root / "INFY_FY2025_26_annual_report.pdf").write_bytes(b"pdf")
    (root / "INFY_FY2024_25_annual_report.pdf").write_bytes(b"pdf")

    engine = object.__new__(BusinessAnalysisEngine)
    engine.reports_root = tmp_path / "annual_reports"

    reports = engine._reports("INFY")

    assert [year for year, _ in reports] == ["FY2026", "FY2025"]
    assert len(reports) == 2


def test_keyword_matches_are_not_business_evidence():
    engine = object.__new__(BusinessAnalysisEngine)
    evidence = engine._build_evidence(
        [{"fiscal_year": "FY2026", "source_file": "annual.pdf", "output": {}}],
        [
            {
                "category": "strategy",
                "statement": "Management is expanding AI-led services across enterprise clients.",
                "fiscal_year": "FY2026",
                "page": 151,
                "confidence": "high",
            }
        ],
    )

    assert len(evidence) == 1
    assert "Matched keywords" not in evidence[0].statement
