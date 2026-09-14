"""Unified candidate analysis pipeline.

Stage 1 (the universe scanner) supplies normalized market candidates here.
This module owns candidate-level orchestration for the new architecture:
market candidate -> governance -> financials -> valuation -> decision.

Deterministic calculations stay in the financial and corporate-risk engines;
LLM calls are limited to qualitative annual-report forensics and explanation.
"""

from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, List

from .agent import AnalysisOrchestrator, ForensicAuditOutput
from .corporate_risk import CorporateRiskEngine, extract_announcements_from_rows
from .decision_engine import calculate_investment_decision
from .doc_parser import FinancialDocParser
from .financial_data_provider import FinancialDataError, StructuredFinancialProvider
from .financial_engine import FinancialAnalysisEngine
from .nse_corporate_filings import NSECorporateFilings
from .nse_downloader import NSEDownloader
from .run_history import record_run, summarize_results


class DeepScannerEngine:
    """Run the unified candidate-level research pipeline."""

    def __init__(
        self,
        downloader=None,
        parser_factory=FinancialDocParser,
        orchestrator=None,
        filings_client=None,
        risk_engine=None,
        financial_engine=None,
        financial_provider=None,
    ):
        self.downloader = downloader or NSEDownloader()
        self.parser_factory = parser_factory
        self.orchestrator = orchestrator
        self.filings_client = filings_client
        self.risk_engine = risk_engine or CorporateRiskEngine()
        self.financial_engine = financial_engine or FinancialAnalysisEngine()
        self.financial_provider = financial_provider or StructuredFinancialProvider()

    @staticmethod
    def _write_json(path: str, payload: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)

    @staticmethod
    def _annual_report_gap(reports: List[Dict[str, Any]], audits: List[Dict[str, Any]]) -> str | None:
        if not reports:
            return "No annual reports available"
        if len(audits) < len(reports):
            return f"Only {len(audits)}/{len(reports)} available reports were successfully audited"
        if len(reports) < 10:
            return f"Only {len(reports)}/10 requested annual reports are available"
        return None

    def _load_governance_evidence(
        self,
        symbol: str,
        row: Dict[str, Any],
        live_filings: bool,
    ) -> tuple[Dict[str, Any], Any, List[Dict[str, Any]], List[Dict[str, Any]]]:
        filing_data: Dict[str, Any] = {
            "announcements": [],
            "pit_risk_rows": [],
            "shareholding": {},
        }
        if live_filings:
            client = self.filings_client or NSECorporateFilings()
            filing_data = client.cached_risk_inputs(symbol)

        promoter_holding = filing_data.get("promoter_holding_pct")
        if promoter_holding is None:
            promoter_holding = row.get("promoter_holding_pct")
        promoter_pledge = filing_data.get("promoter_pledge_pct")
        if promoter_pledge is None:
            promoter_pledge = row.get("promoter_pledge_pct")
        promoter_change = filing_data.get("promoter_change_pct")
        if promoter_change is None:
            promoter_change = row.get("promoter_change_pct")

        reports = self.downloader.download_reports(symbol, years=10)
        audits: List[Dict[str, Any]] = []
        ai = self.orchestrator or AnalysisOrchestrator()

        # All available annual reports contribute governance evidence. Their
        # financial tables are intentionally NOT used for financial metrics.
        for item in reports[:10]:
            fiscal_year = item.get("fiscal_year", "Unknown")
            try:
                sections = self.parser_factory(item["path"]).extract_critical_sections()
                forensic = ai.audit_forensics(
                    sections.get("auditor_report", ""),
                    sections.get("notes", ""),
                )
                audit = forensic.model_dump()
                audit["fiscal_year"] = fiscal_year
                audits.append(audit)
            except Exception as exc:
                audits.append(
                    {
                        "fiscal_year": fiscal_year,
                        "audit_opinion_type": "Unavailable",
                        "auditor_observations": [],
                        "key_audit_matters": [],
                        "related_party_transactions": [],
                        "loans_guarantees_investments": [],
                        "contingent_liabilities": [],
                        "remuneration_details": [],
                        "regulatory_compliance_events": [],
                        "what_happened": [],
                        "contingent_liability_risk": "Unavailable",
                        "related_party_risk": "Unavailable",
                        "forensic_red_flags": [f"Annual-report audit failed: {type(exc).__name__}: {exc}"],
                        "why_it_matters": [],
                        "governance_conclusion": "Unavailable",
                    }
                )

        announcements = extract_announcements_from_rows(
            [*filing_data.get("announcements", []), *filing_data.get("pit_risk_rows", [])]
        )
        corporate = self.risk_engine.assess(
            promoter_holding_pct=promoter_holding,
            promoter_pledge_pct=promoter_pledge,
            promoter_change_pct=promoter_change,
            auditor_status=row.get("auditor_status"),
            related_party_risk=row.get("related_party_risk"),
            announcements=announcements,
            annual_report_audits=audits,
        )
        gap = self._annual_report_gap(reports, audits)
        if gap and gap not in corporate.data_gaps:
            corporate.data_gaps.append(gap)

        return filing_data, corporate, reports, audits

    @staticmethod
    def _forensic_for_committee(audits: List[Dict[str, Any]]) -> ForensicAuditOutput:
        """Convert the latest audited annual-report evidence to the memo schema."""
        if not audits:
            return ForensicAuditOutput(
                audit_opinion_type="Unavailable",
                key_audit_matters=[],
                contingent_liability_risk="Unavailable",
                related_party_risk="Unavailable",
                forensic_red_flags=["No annual-report forensic evidence available"],
            )
        latest = audits[0]
        return ForensicAuditOutput(
            audit_opinion_type=str(latest.get("audit_opinion_type") or "Unavailable"),
            auditor_observations=list(latest.get("auditor_observations") or []),
            key_audit_matters=list(latest.get("key_audit_matters") or []),
            related_party_transactions=list(latest.get("related_party_transactions") or []),
            loans_guarantees_investments=list(latest.get("loans_guarantees_investments") or []),
            contingent_liabilities=list(latest.get("contingent_liabilities") or []),
            remuneration_details=list(latest.get("remuneration_details") or []),
            regulatory_compliance_events=list(latest.get("regulatory_compliance_events") or []),
            what_happened=list(latest.get("what_happened") or []),
            contingent_liability_risk=str(latest.get("contingent_liability_risk") or "Unavailable"),
            related_party_risk=str(latest.get("related_party_risk") or "Unavailable"),
            forensic_red_flags=list(latest.get("forensic_red_flags") or []),
            why_it_matters=list(latest.get("why_it_matters") or []),
            governance_conclusion=str(latest.get("governance_conclusion") or "Unavailable"),
        )

    def analyze_candidate(self, row: Dict[str, Any], live_filings: bool = True, persist: bool = True) -> Dict[str, Any]:
        """Analyze one scanner candidate through the unified architecture."""
        symbol = str(row.get("symbol", "")).strip().upper()
        if not symbol:
            return {**row, "status": "ERROR", "error": "Missing symbol"}
        try:
            filing_data, corporate, reports, audits = self._load_governance_evidence(symbol, row, live_filings)
            if corporate.hard_fail:
                result = {**row, "status": "CORPORATE_RISK_REJECT", "stage": "GOVERNANCE", "verdict": "AVOID", "corporate_risk_score": corporate.risk_score, "governance_grade": corporate.governance_grade, "corporate_risk_flags": ";".join(corporate.risk_flags), "corporate_data_gaps": ";".join(corporate.data_gaps), "annual_reports_scanned": len(audits), "filing_source": filing_data.get("source", "NSE"), "error": "Rejected before financial analysis due to a hard governance signal"}
                if persist:
                    self._persist_stage_outputs(symbol, corporate, audits, None, None, None, result)
                return result
            try:
                history = self.financial_provider.get_history(symbol)
            except FinancialDataError as exc:
                result = {**row, "status": "FINANCIAL_DATA_ERROR", "stage": "FINANCIAL_ANALYSIS", "governance_grade": corporate.governance_grade, "corporate_risk_score": corporate.risk_score, "corporate_risk_flags": ";".join(corporate.risk_flags), "error": str(exc)}
                if persist:
                    self._persist_stage_outputs(symbol, corporate, audits, None, None, None, result)
                return result
            governance_clean = not corporate.hard_fail and corporate.governance_grade in {"A", "B"}
            price = self._float_or_none(row.get("price"))
            market_cap = self._float_or_none(row.get("market_cap_cr"))
            shares_cr = market_cap / price if price and price > 0 and market_cap and market_cap > 0 else None
            ratios = self.financial_engine.calculate_ratios(history)
            quality_full = self.financial_engine.calculate_quality(ratios, governance_clean=True)
            financial_components = {key: value for key, value in quality_full.get("components", {}).items() if key != "governance"}
            financial_score = sum(int(value or 0) for value in financial_components.values())
            valuation = (self.financial_engine.calculate_valuation(price, shares_cr, history.years[-1].pat, ratios.get("PAT CAGR (%)"), target_pe=20.0, margin_of_safety_pct=30.0) if price is not None and shares_cr is not None else {"available": False, "reason": "Current price and shares outstanding are unavailable."})
            quality = {"components": financial_components, "score_100": financial_score}
            decision = calculate_investment_decision(quality=quality, ratios=ratios, valuation=valuation, governance_grade=corporate.governance_grade, forensic_clean=not corporate.hard_fail)
            ai = self.orchestrator or AnalysisOrchestrator()
            memo = ai.run_investment_committee(self._forensic_for_committee(audits), ratios, quality, valuation)
            result = {**row, "status": "ANALYZED", "stage": "DECISION", "verdict": decision["verdict"], "decision_reason": decision["reason"], "decision_score": decision["decision_score"], "quality_score": financial_score, "ai_conviction": getattr(memo, "conviction_score", None), "governance_clean": governance_clean, "corporate_risk_score": corporate.risk_score, "governance_grade": corporate.governance_grade, "corporate_risk_flags": ";".join(corporate.risk_flags), "corporate_data_gaps": ";".join(corporate.data_gaps), "promoter_holding_pct": filing_data.get("promoter_holding_pct") if filing_data.get("promoter_holding_pct") is not None else row.get("promoter_holding_pct"), "promoter_pledge_pct": filing_data.get("promoter_pledge_pct") if filing_data.get("promoter_pledge_pct") is not None else row.get("promoter_pledge_pct"), "promoter_change_pct": filing_data.get("promoter_change_pct") if filing_data.get("promoter_change_pct") is not None else row.get("promoter_change_pct"), "shareholding_as_on": filing_data.get("shareholding", {}).get("as_on_date"), "shareholding_xbrl_url": filing_data.get("shareholding", {}).get("xbrl_url"), "filing_source": filing_data.get("source", "NSE"), "annual_reports_scanned": len(audits), "annual_report_paths": ";".join(str(record["path"]) for record in reports), "pat_cagr_pct": ratios.get("PAT CAGR (%)"), "revenue_cagr_pct": ratios.get("Revenue CAGR (%)"), "roce_pct": ratios.get("ROCE (%)"), "roe_pct": ratios.get("ROE (%)"), "cfo_pat": ratios.get("CFO / PAT Quality Ratio"), "debt_equity": ratios.get("Debt to Equity"), "fair_value": valuation.get("fair_value"), "buy_below": valuation.get("buy_below"), "risk_flags": ";".join(getattr(memo, "critical_risks", []) or []), "thesis": str(getattr(memo, "executive_summary", "") or "").strip()}
            if persist:
                self._persist_stage_outputs(symbol, corporate, audits, history, ratios, quality, result, valuation=valuation, decision=decision, memo=memo)
            return result
        except Exception as exc:
            return {**row, "status": "ERROR", "stage": "PIPELINE", "error": f"{type(exc).__name__}: {exc}"}

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _persist_stage_outputs(self, symbol: str, corporate: Any, audits: List[Dict[str, Any]], history: Any, ratios: Any, quality: Any, result: Dict[str, Any], valuation: Dict[str, Any] | None = None, decision: Dict[str, Any] | None = None, memo: Any | None = None) -> None:
        output_dir = os.path.join("outputs", symbol)
        self._write_json(os.path.join(output_dir, "corporate_governance.json"), {"symbol": symbol, "analysis_type": "corporate_governance", "governance_grade": corporate.governance_grade, "risk_score": corporate.risk_score, "annual_report_score": corporate.annual_report_score, "reports_scanned": len(audits), "hard_fail": corporate.hard_fail, "risk_flags": list(corporate.risk_flags), "positive_signals": list(corporate.positive_signals), "data_gaps": list(corporate.data_gaps), "annual_report_audits": audits})
        if history is not None and ratios is not None and quality is not None:
            self._write_json(os.path.join(output_dir, "financial_analysis.json"), {"symbol": symbol, "analysis_type": "financial_analysis", "financial_score": quality["score_100"], "financial_components": quality["components"], "ratios": dict(ratios), "valuation": valuation or {"available": False}, "history": [year.model_dump() for year in history.years]})
        if decision is not None:
            self._write_json(os.path.join(output_dir, "investment_decision.json"), {"symbol": symbol, "analysis_type": "investment_decision", **decision, "governance": {"grade": corporate.governance_grade, "risk_score": corporate.risk_score, "annual_report_score": corporate.annual_report_score, "hard_fail": corporate.hard_fail}, "financial": {"financial_score": quality["score_100"], "components": quality["components"], "ratios": dict(ratios)}, "ai": {"conviction_score": getattr(memo, "conviction_score", None), "thesis": str(getattr(memo, "executive_summary", "") or "").strip()}})

    def run(self, input_csv="./outputs/small_microcap_universe.csv", top=10, deep_limit=20, output_dir="./outputs", live_filings=True) -> List[Dict[str, Any]]:
        if not os.path.exists(input_csv):
            raise FileNotFoundError(f"Stage-1 CSV not found: {input_csv}. Run --scan first.")
        with open(input_csv, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))[:deep_limit]
        results = [self.analyze_candidate(row, live_filings=live_filings) for row in rows]
        analyzed = [r for r in results if r.get("status") == "ANALYZED"]
        analyzed.sort(key=lambda r: (r.get("verdict") == "BUY", float(r.get("quality_score") or 0), float(r.get("ai_conviction") or 0)), reverse=True)
        selected = analyzed[:top]
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "small_microcap_deep_analysis.csv")
        fields = sorted({key for row in results for key in row.keys()})
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)
        record_run("DEEP_SCAN", summarize_results(results), output_dir=output_dir, notes=f"live_filings={'ON' if live_filings else 'OFF'}; top={top}; deep_limit={deep_limit}")
        print(f"[+] Stage-2 candidates processed: {len(rows)}")
        print(f"[+] Stage-2 fully analyzed: {len(analyzed)}")
        summary = summarize_results(results)
        print(f"ANALYZED={summary['analyzed']}")
        print(f"ERROR={summary['errors']}")
        for item in results:
            if item.get("status") != "ANALYZED":
                print(f"[{item.get('status')}] {item.get('symbol', '')} {item.get('error', '')}")
        print(f"[+] Live NSE filing checks: {'ON' if live_filings else 'OFF'}")
        print(f"[+] Saved full deep-analysis results: {path}")
        print("\nTOP SMALL/MICRO-CAP RESEARCH SHORTLIST")
        print("-" * 110)
        for i, item in enumerate(selected, 1):
            print(f"{i:>2}. {item['symbol']:<15} {item.get('market_cap_category',''):<9} {item.get('verdict',''):<10} Score {item.get('quality_score')} Gov {item.get('governance_grade')} Fair ₹{item.get('fair_value')}")
        return selected

    def analyze_symbol(self, symbol: str, live_filings: bool = True) -> Dict[str, Any]:
        """Single-stock entry point using exactly the same pipeline as scanner candidates."""
        symbol = symbol.strip().upper()
        from .nse_universe import NSEUniverse
        return self.analyze_candidate(NSEUniverse().quote(symbol), live_filings=live_filings)


def analyze_candidate(row, orchestrator=None, filings_client=None, live_filings=True):
    return DeepScannerEngine(orchestrator=orchestrator, filings_client=filings_client).analyze_candidate(row, live_filings=live_filings)


def run_deep_scan(input_csv="./outputs/small_microcap_universe.csv", top=10, deep_limit=20, output_dir="./outputs", live_filings=True):
    return DeepScannerEngine().run(input_csv=input_csv, top=top, deep_limit=deep_limit, output_dir=output_dir, live_filings=live_filings)
