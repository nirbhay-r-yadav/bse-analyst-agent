"""Independent deep-scan use case with injectable collaborators."""

from __future__ import annotations

import csv
import os
from typing import Any, Dict, List

from .agent import AnalysisOrchestrator
from .corporate_risk import CorporateRiskEngine, extract_announcements_from_rows
from .doc_parser import FinancialDocParser
from .financial_engine import FinancialAnalysisEngine
from .nse_corporate_filings import NSECorporateFilings
from .nse_downloader import NSEDownloader
from .run_history import record_run, summarize_results


def _is_complete_analysis(result: Dict[str, Any]) -> bool:
    """Return True only when a candidate contains the final research payload."""
    return (
        result.get("status") == "ANALYZED"
        and bool(result.get("verdict"))
        and result.get("quality_score") is not None
        and result.get("ai_conviction") is not None
        and bool(str(result.get("thesis") or "").strip())
    )


class DeepScannerEngine:
    """Run candidate-level research without depending on menu or CLI code."""

    def __init__(
        self,
        downloader=None,
        parser_factory=FinancialDocParser,
        orchestrator=None,
        filings_client=None,
        risk_engine=None,
        financial_engine=None,
    ):
        self.downloader = downloader or NSEDownloader()
        self.parser_factory = parser_factory
        self.orchestrator = orchestrator
        self.filings_client = filings_client
        self.risk_engine = risk_engine or CorporateRiskEngine()
        self.financial_engine = financial_engine or FinancialAnalysisEngine()

    def analyze_candidate(
        self,
        row: Dict[str, Any],
        live_filings: bool = True,
    ) -> Dict[str, Any]:
        symbol = str(row.get("symbol", "")).strip().upper()
        if not symbol:
            return {**row, "status": "ERROR", "error": "Missing symbol"}

        try:
            filing_data = {
                "announcements": [],
                "pit_risk_rows": [],
                "shareholding": {},
            }
            if live_filings:
                client = self.filings_client or NSECorporateFilings()
                filing_data = client.cached_risk_inputs(symbol)

            promoter_holding = (
                filing_data.get("promoter_holding_pct")
                or row.get("promoter_holding_pct")
            )
            promoter_pledge = (
                filing_data.get("promoter_pledge_pct")
                if filing_data.get("promoter_pledge_pct") is not None
                else row.get("promoter_pledge_pct")
            )
            promoter_change = (
                filing_data.get("promoter_change_pct")
                if filing_data.get("promoter_change_pct") is not None
                else row.get("promoter_change_pct")
            )

            corporate = self.risk_engine.assess(
                promoter_holding_pct=promoter_holding,
                promoter_pledge_pct=promoter_pledge,
                promoter_change_pct=promoter_change,
                auditor_status=row.get("auditor_status"),
                related_party_risk=row.get("related_party_risk"),
                announcements=extract_announcements_from_rows(
                    [
                        *filing_data.get("announcements", []),
                        *filing_data.get("pit_risk_rows", []),
                    ]
                ),
            )

            if corporate.hard_fail:
                return {
                    **row,
                    "status": "CORPORATE_RISK_REJECT",
                    "stage": "CORPORATE_RISK",
                    "verdict": "AVOID",
                    "corporate_risk_score": corporate.risk_score,
                    "governance_grade": corporate.governance_grade,
                    "corporate_risk_flags": ";".join(corporate.risk_flags),
                    "corporate_data_gaps": ";".join(corporate.data_gaps),
                    "promoter_holding_pct": promoter_holding,
                    "promoter_pledge_pct": promoter_pledge,
                    "promoter_change_pct": promoter_change,
                    "shareholding_as_on": filing_data.get("shareholding", {}).get(
                        "as_on_date"
                    ),
                    "shareholding_xbrl_url": filing_data.get("shareholding", {}).get(
                        "xbrl_url"
                    ),
                    "filing_source": filing_data.get("source", "NSE"),
                    "error": "Rejected before deep analysis due to a hard corporate-risk signal",
                }

            # Ensure the stock-specific cache is populated before analysis.
            # The downloader creates data/downloads/<SYMBOL>/ and reuses valid
            # cached reports before downloading anything new.
            report_records = self.downloader.download_reports(symbol, years=10)
            if not report_records:
                return {
                    **row,
                    "status": "NO_REPORT",
                    "error": "Annual reports unavailable",
                }

            # Deep Scan currently uses the latest annual report for qualitative
            # forensic parsing, while the downloader keeps the full requested
            # report history available in the stock-specific cache.
            pdf_path = report_records[0]["path"]
            sections = self.parser_factory(pdf_path).extract_critical_sections()

            ai = self.orchestrator or AnalysisOrchestrator()
            forensics = ai.audit_forensics(
                sections["auditor_report"],
                sections["notes"],
            )
            history = ai.extract_metrics_payload(
                sections["financial_statements"]
            )

            governance_clean = (
                forensics.audit_opinion_type.lower().startswith("unmodified")
                and forensics.contingent_liability_risk.lower().startswith("low")
                and forensics.related_party_risk.lower().startswith("low")
                and not forensics.forensic_red_flags
                and corporate.governance_grade in {"A", "B"}
            )

            price = (
                float(row["price"])
                if row.get("price") not in (None, "")
                else None
            )
            market_cap = (
                float(row["market_cap_cr"])
                if row.get("market_cap_cr") not in (None, "")
                else None
            )
            shares_cr = (
                market_cap / price
                if price and price > 0 and market_cap and market_cap > 0
                else None
            )

            analysis = self.financial_engine.analyze(
                history,
                governance_clean=governance_clean,
                current_price=price,
                shares_outstanding_cr=shares_cr,
                target_pe=20.0,
                margin_of_safety_pct=30.0,
            )
            memo = ai.run_investment_committee(
                forensics,
                analysis.ratios,
                analysis.quality,
                analysis.valuation,
            )

            return {
                **row,
                "status": "ANALYZED",
                "verdict": analysis.recommendation["verdict"],
                "decision_reason": analysis.recommendation["reason"],
                "quality_score": analysis.quality["score_100"],
                "ai_conviction": memo.conviction_score,
                "governance_clean": governance_clean,
                "corporate_risk_score": corporate.risk_score,
                "governance_grade": corporate.governance_grade,
                "corporate_risk_flags": ";".join(corporate.risk_flags),
                "corporate_data_gaps": ";".join(corporate.data_gaps),
                "promoter_holding_pct": promoter_holding,
                "promoter_pledge_pct": promoter_pledge,
                "promoter_change_pct": promoter_change,
                "shareholding_as_on": filing_data.get("shareholding", {}).get(
                    "as_on_date"
                ),
                "shareholding_xbrl_url": filing_data.get("shareholding", {}).get(
                    "xbrl_url"
                ),
                "filing_source": filing_data.get("source", "NSE"),
                "annual_reports_scanned": len(report_records),
                "annual_report_paths": ";".join(
                    str(record["path"]) for record in report_records
                ),
                "pat_cagr_pct": analysis.ratios.get("PAT CAGR (%)"),
                "revenue_cagr_pct": analysis.ratios.get("Revenue CAGR (%)"),
                "roce_pct": analysis.ratios.get("ROCE (%)"),
                "roe_pct": analysis.ratios.get("ROE (%)"),
                "cfo_pat": analysis.ratios.get("CFO / PAT Quality Ratio"),
                "debt_equity": analysis.ratios.get("Debt to Equity"),
                "fair_value": analysis.valuation.get("fair_value"),
                "buy_below": analysis.valuation.get("buy_below"),
                "risk_flags": ";".join(forensics.forensic_red_flags or []),
                "thesis": memo.executive_summary.strip(),
            }
        except Exception as exc:
            return {
                **row,
                "status": "ERROR",
                "error": f"{type(exc).__name__}: {exc}",
            }

    def run(
        self,
        input_csv="./outputs/small_microcap_universe.csv",
        top=10,
        deep_limit=20,
        output_dir="./outputs",
        live_filings=True,
    ) -> List[Dict[str, Any]]:
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

        analyzed = [
            r for r in results if r.get("status") == "ANALYZED"
        ]
        analyzed.sort(
            key=lambda r: (
                r.get("verdict") == "BUY",
                float(r.get("quality_score") or 0),
                float(r.get("ai_conviction") or 0),
            ),
            reverse=True,
        )
        selected = analyzed[:top]

        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "small_microcap_deep_analysis.csv")
        fields = sorted({key for row in results for key in row.keys()})
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=fields,
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(results)

        record_run(
            "DEEP_SCAN",
            summarize_results(results),
            output_dir=output_dir,
            notes=(
                f"live_filings={'ON' if live_filings else 'OFF'}; "
                f"top={top}; deep_limit={deep_limit}"
            ),
        )

        print(f"[+] Stage-2 candidates processed: {len(rows)}")
        print(f"[+] Stage-2 fully analyzed: {len(analyzed)}")
        summary = summarize_results(results)
        print(f"ANALYZED={summary['analyzed']}")
        print(f"ERROR={summary['errors']}")
        for result in results:
            if result.get("status") == "ERROR":
                print(f"[ERROR] {result.get('error', '')}")
        print(f"[+] Live NSE filing checks: {'ON' if live_filings else 'OFF'}")
        print(f"[+] Saved full deep-analysis results: {path}")
        print("\nTOP SMALL/MICRO-CAP RESEARCH SHORTLIST")
        print("-" * 110)
        for i, row in enumerate(selected, 1):
            print(
                f"{i:>2}. {row['symbol']:<15} "
                f"{row.get('market_cap_category',''):<9} "
                f"{row.get('verdict',''):<10} "
                f"Score {row.get('quality_score')}  "
                f"Gov {row.get('governance_grade')}  "
                f"Fair ₹{row.get('fair_value')}"
            )
        return selected


def analyze_candidate(
    row,
    orchestrator=None,
    filings_client=None,
    live_filings=True,
):
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
