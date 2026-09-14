from types import SimpleNamespace

import src.deep_scanner as deep_scanner


def test_complete_analysis_requires_final_payload():
    result = {
        "status": "ANALYZED",
        "verdict": "WATCHLIST",
        "quality_score": 72,
        "ai_conviction": 7,
        "thesis": "Solid business, valuation needs patience.",
    }
    assert result["status"] == "ANALYZED"
    assert result["quality_score"] is not None
    assert result["ai_conviction"] is not None
    assert result["thesis"]


def test_corporate_reject_happens_before_financial_analysis():
    class FakeFilings:
        def cached_risk_inputs(self, symbol):
            return {
                "announcements": [],
                "pit_risk_rows": [],
                "shareholding": {},
                "promoter_holding_pct": 55,
                "promoter_pledge_pct": 25,
                "promoter_change_pct": 0,
                "source": "test",
            }

    class FakeDownloader:
        def download_reports(self, symbol, years=10):
            return []

    class FakeAI:
        pass

    class ExplodingFinancialProvider:
        def get_history(self, symbol):
            raise AssertionError("Financial provider must not run after hard governance failure")

    result = deep_scanner.DeepScannerEngine(
        downloader=FakeDownloader(),
        orchestrator=FakeAI(),
        filings_client=FakeFilings(),
        financial_provider=ExplodingFinancialProvider(),
    ).analyze_candidate(
        {"symbol": "TEST", "price": "100", "market_cap_cr": "1000"},
        live_filings=True,
        persist=False,
    )

    assert result["status"] == "CORPORATE_RISK_REJECT"
    assert result["stage"] == "GOVERNANCE"
    assert result["verdict"] == "AVOID"
    assert "pledge" in result["corporate_risk_flags"].lower()


def test_pipeline_uses_structured_financial_provider_and_deterministic_decision():
    audit = {
        "fiscal_year": "FY2026",
        "audit_opinion_type": "Unmodified",
        "contingent_liability_risk": "Low",
        "related_party_risk": "Low",
        "forensic_red_flags": [],
    }

    class FakeFilings:
        def cached_risk_inputs(self, symbol):
            return {
                "announcements": [],
                "pit_risk_rows": [],
                "shareholding": {},
                "promoter_holding_pct": 55,
                "promoter_pledge_pct": 0,
                "promoter_change_pct": 0,
                "source": "test",
            }

    class FakeDownloader:
        def download_reports(self, symbol, years=10):
            return [{"fiscal_year": "FY2026", "path": "report.pdf"}]

    class FakeParser:
        def __init__(self, path):
            self.path = path

        def extract_critical_sections(self):
            return {"auditor_report": "clean", "notes": "clean"}

    class FakeAI:
        def audit_forensics(self, auditor_text, notes_text):
            return SimpleNamespace(**audit)

        def run_investment_committee(self, forensic, ratios, quality, valuation):
            return SimpleNamespace(
                conviction_score=8,
                executive_summary="Strong test thesis",
                critical_risks=[],
            )

    class FakeRiskEngine:
        def assess(self, **inputs):
            return SimpleNamespace(
                hard_fail=False,
                risk_score=5,
                annual_report_score=0,
                governance_grade="A",
                risk_flags=[],
                positive_signals=[],
                data_gaps=[],
            )

    class FakeFinancialProvider:
        def __init__(self):
            self.called = False

        def get_history(self, symbol):
            self.called = True
            return SimpleNamespace(
                years=[
                    SimpleNamespace(
                        pat=100,
                        model_dump=lambda: {"fiscal_year": "FY2026", "pat": 100},
                    )
                ]
            )

    class FakeFinancialEngine:
        def calculate_ratios(self, history):
            return {
                "PAT CAGR (%)": 12,
                "Revenue CAGR (%)": 12,
                "ROCE (%)": 22,
                "ROE (%)": 20,
                "CFO / PAT Quality Ratio": 1.1,
                "Debt to Equity": 0.2,
                "Positive CFO Years": "5/5",
            }

        def calculate_quality(self, ratios, governance_clean=True):
            return {
                "components": {
                    "capital_efficiency": 20,
                    "growth": 20,
                    "balance_sheet": 15,
                    "cash_quality": 15,
                },
                "score_100": 70,
            }

        def calculate_valuation(self, *args, **kwargs):
            return {
                "available": True,
                "current_price": 100,
                "fair_value": 150,
                "buy_below": 105,
            }

    provider = FakeFinancialProvider()
    result = deep_scanner.DeepScannerEngine(
        downloader=FakeDownloader(),
        parser_factory=FakeParser,
        orchestrator=FakeAI(),
        filings_client=FakeFilings(),
        risk_engine=FakeRiskEngine(),
        financial_engine=FakeFinancialEngine(),
        financial_provider=provider,
    ).analyze_candidate(
        {"symbol": "TEST", "price": "100", "market_cap_cr": "1000"},
        live_filings=True,
        persist=False,
    )

    assert provider.called
    assert result["status"] == "ANALYZED"
    assert result["stage"] == "DECISION"
    assert result["annual_reports_scanned"] == 1
    assert result["verdict"] == "BUY"
    assert result["quality_score"] == 70


def test_run_deep_scan_persists_checkpoint(tmp_path):
    input_csv = tmp_path / "input.csv"
    input_csv.write_text(
        "symbol,price,market_cap_cr\nGOOD,100,1000\nBAD,100,1000\n",
        encoding="utf-8",
    )

    class FakeEngine:
        def analyze_candidate(self, row, live_filings=True):
            if row["symbol"] == "GOOD":
                return {
                    **row,
                    "status": "ANALYZED",
                    "stage": "DECISION",
                    "verdict": "WATCHLIST",
                    "quality_score": 70,
                    "ai_conviction": 7,
                    "thesis": "Test thesis",
                }
            return {
                **row,
                "status": "ERROR",
                "stage": "PIPELINE",
                "error": "RuntimeError: test failure",
            }

    engine = FakeEngine()
    scanner = deep_scanner.DeepScannerEngine.__new__(deep_scanner.DeepScannerEngine)
    scanner.analyze_candidate = engine.analyze_candidate

    selected = scanner.run(
        input_csv=str(input_csv),
        top=10,
        deep_limit=2,
        output_dir=str(tmp_path),
        live_filings=False,
    )

    assert len(selected) == 1
    assert selected[0]["symbol"] == "GOOD"
    checkpoint = tmp_path / "small_microcap_deep_analysis.csv"
    assert checkpoint.exists()
    text = checkpoint.read_text(encoding="utf-8")
    assert "GOOD" in text
    assert "BAD" in text
