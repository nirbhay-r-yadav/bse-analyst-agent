"""Candidate research pipeline focused on business analysis and business/corporate risk.

Financial analysis, valuation and investment-decision scoring are intentionally
outside this pipeline. The engine produces evidence that can be reviewed by a
human without turning it into a buy/sell recommendation.
"""

from __future__ import annotations

import csv
import json
import os
from typing import Any

from .agent import AnalysisOrchestrator
from .business_analysis.business_analysis_engine import BusinessAnalysisEngine
from .corporate_risk import CorporateRiskEngine, extract_announcements_from_rows
from .doc_parser import FinancialDocParser
from .nse_corporate_filings import NSECorporateFilings
from .nse_downloader import NSEDownloader
from .run_history import record_run, summarize_results


class DeepScannerEngine:
    """Run business analysis + business/corporate-risk research."""

    def __init__(
        self,
        downloader=None,
        parser_factory=FinancialDocParser,
        orchestrator=None,
        filings_client=None,
        risk_engine=None,
        business_engine=None,
    ):
        self.downloader = downloader or NSEDownloader()
        self.parser_factory = parser_factory
        self.orchestrator = orchestrator
        self.filings_client = filings_client
        self.risk_engine = risk_engine or CorporateRiskEngine()
        self.business_engine = business_engine or BusinessAnalysisEngine()

    @staticmethod
    def _write_json(path: str, payload: dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)

    @staticmethod
    def _annual_report_gap(reports: list[dict[str, Any]], audits: list[dict[str, Any]]) -> str | None:
        if not reports:
            return "No annual reports available"
        if len(audits) < len(reports):
            return f"Only {len(audits)}/{len(reports)} available reports were successfully audited"
        if len(reports) < 10:
            return f"Only {len(reports)}/10 requested annual reports are available"
        return None

    def _load_risk_evidence(
        self,
        symbol: str,
        row: dict[str, Any],
        live_filings: bool,
    ) -> tuple[dict[str, Any], Any, list[dict[str, Any]], list[dict[str, Any]]]:
        filing_data: dict[str, Any] = {
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
        audits: list[dict[str, Any]] = []
        ai = self.orchestrator or AnalysisOrchestrator()

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
                        "forensic_red_flags": [
                            f"Annual-report audit failed: {type(exc).__name__}: {exc}"
                        ],
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

    def analyze_candidate(
        self,
        row: dict[str, Any],
        live_filings: bool = True,
        persist: bool = True,
    ) -> dict[str, Any]:
        symbol = str(row.get("symbol", "")).strip().upper()
        if not symbol:
            return {**row, "status": "ERROR", "error": "Missing symbol"}

        try:
            filing_data, corporate, reports, audits = self._load_risk_evidence(
                symbol, row, live_filings
            )

            business = self.business_engine.analyze(symbol)

            result = {
                **row,
                "status": "ANALYZED",
                "stage": "BUSINESS_ANALYSIS",
                "corporate_risk_score": corporate.risk_score,
                "governance_grade": corporate.governance_grade,
                "corporate_hard_fail": corporate.hard_fail,
                "corporate_risk_flags": ";".join(corporate.risk_flags),
                "corporate_positive_signals": ";".join(corporate.positive_signals),
                "corporate_data_gaps": ";".join(corporate.data_gaps),
                "business_model": json.dumps(
                    business.business_model, ensure_ascii=False, default=str
                ),
                "business_risk_signals": json.dumps(
                    business.risks, ensure_ascii=False, default=str
                ),
                "management_promises": len(business.management_promises),
                "management_execution": json.dumps(
                    business.management_execution, ensure_ascii=False, default=str
                ),
                "evidence_count": len(business.evidence),
                "annual_reports_scanned": len(audits),
                "annual_report_paths": ";".join(
                    str(record["path"]) for record in reports
                ),
                "filing_source": filing_data.get("source", "NSE"),
                "promoter_holding_pct": (
                    filing_data.get("promoter_holding_pct")
                    if filing_data.get("promoter_holding_pct") is not None
                    else row.get("promoter_holding_pct")
                ),
                "promoter_pledge_pct": (
                    filing_data.get("promoter_pledge_pct")
                    if filing_data.get("promoter_pledge_pct") is not None
                    else row.get("promoter_pledge_pct")
                ),
                "promoter_change_pct": (
                    filing_data.get("promoter_change_pct")
                    if filing_data.get("promoter_change_pct") is not None
                    else row.get("promoter_change_pct")
                ),
            }

            if persist:
                self._persist_stage_outputs(
                    symbol, corporate, audits, business, result
                )
            return result
        except Exception as exc:
            return {
                **row,
                "status": "ERROR",
                "stage": "BUSINESS_ANALYSIS",
                "error": f"{type(exc).__name__}: {exc}",
            }

    def _persist_stage_outputs(
        self,
        symbol: str,
        corporate: Any,
        audits: list[dict[str, Any]],
        business: Any,
        result: dict[str, Any],
    ) -> None:
        output_dir = os.path.join("outputs", symbol)
        self._write_json(
            os.path.join(output_dir, "corporate_governance.json"),
            {
                "symbol": symbol,
                "analysis_type": "business_corporate_risk",
                "risk_score": corporate.risk_score,
                "annual_report_score": corporate.annual_report_score,
                "reports_scanned": len(audits),
                "hard_fail": corporate.hard_fail,
                "risk_flags": list(corporate.risk_flags),
                "positive_signals": list(corporate.positive_signals),
                "data_gaps": list(corporate.data_gaps),
                "annual_report_audits": audits,
            },
        )
        self._write_json(
            os.path.join(output_dir, "business_analysis.json"),
            {
                "symbol": symbol,
                "analysis_type": "business_analysis",
                **business.to_dict(),
            },
        )

    def run(
        self,
        input_csv="./outputs/small_microcap_universe.csv",
        top=10,
        deep_limit=20,
        output_dir="./outputs",
        live_filings=True,
    ) -> list[dict[str, Any]]:
        if not os.path.exists(input_csv):
            raise FileNotFoundError(
                f"Stage-1 CSV not found: {input_csv}. Run --scan first."
            )

        with open(input_csv, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))[:deep_limit]

        results = [
            self.analyze_candidate(row, live_filings=live_filings)
            for row in rows
        ]
        analyzed = [r for r in results if r.get("status") == "ANALYZED"]
        selected = analyzed[:top]

        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "small_microcap_business_analysis.csv")
        fields = sorted({key for row in results for key in row.keys()})
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=fields, extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(results)

        record_run(
            "BUSINESS_ANALYSIS",
            summarize_results(results),
            output_dir=output_dir,
            notes=(
                f"live_filings={'ON' if live_filings else 'OFF'}; "
                f"top={top}; deep_limit={deep_limit}"
            ),
        )

        print(f"[+] Candidates processed: {len(rows)}")
        print(f"[+] Business analyses completed: {len(analyzed)}")
        print(f"[+] Live NSE filing checks: {'ON' if live_filings else 'OFF'}")
        print(f"[+] Saved business-analysis results: {path}")

        print("\nBUSINESS / RISK RESEARCH RESULTS")
        print("-" * 110)
        for i, item in enumerate(selected, 1):
            print(
                f"{i:>2}. {item.get('symbol',''):<15} "
                f"Risk {item.get('corporate_risk_score')} "
                f"Gov {item.get('governance_grade')} "
                f"Reports {item.get('annual_reports_scanned')}"
            )
        return selected

    def analyze_symbol(
        self, symbol: str, live_filings: bool = True
    ) -> dict[str, Any]:
        symbol = symbol.strip().upper()
        from .nse_universe import NSEUniverse

        return self.analyze_candidate(
            NSEUniverse().quote(symbol), live_filings=live_filings
        )


def analyze_candidate(row, orchestrator=None, filings_client=None, live_filings=True):
    return DeepScannerEngine(
        orchestrator=orchestrator,
        filings_client=filings_client,
    ).analyze_candidate(row, live_filings=live_filings)


def run_deep_scan(
    input_csv="./outputs/small_microcap_universe.csv",
    top=10,
    deep_limit=20,
    output_dir="./outputs",
    live_filings=True,
):
    return DeepScannerEngine().run(
        input_csv=input_csv,
        top=top,
        deep_limit=deep_limit,
        output_dir=output_dir,
        live_filings=live_filings,
    )
