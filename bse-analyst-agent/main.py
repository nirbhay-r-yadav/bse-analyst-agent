import argparse
import csv
import os
import sys
import warnings
from datetime import datetime
from dotenv import load_dotenv
from src.decision_engine import calculate_investment_decision
from src.corporate_risk import assess_corporate_risk, extract_announcements_from_rows
from src.nse_corporate_filings import NSECorporateFilings
from src.report_generator import generate_investment_report

warnings.filterwarnings("ignore", message=r".*automatic function calling \(AFC\).*")
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
load_dotenv()

from src.nse_downloader import NSEDownloader
from src.doc_parser import FinancialDocParser
from src.financial_tools import calculate_fundamental_ratios, calculate_quality_score, calculate_pe_valuation, determine_final_recommendation
from src.agent import AnalysisOrchestrator
from src.nse_universe import NSEUniverse
from src.smallcap_scanner import SmallMicrocapConfig, classify_market_cap
from src.deep_scanner import run_deep_scan
from src.corporate_risk import assess_corporate_risk, extract_announcements_from_rows
from src.nse_corporate_filings import NSECorporateFilings


def run_corporate_risk_only(symbol: str, report_years: int = 10, live_filings: bool = True):
    """Corporate-risk-only test path.

    This deliberately does NOT run financial ratios, valuation, quality score,
    investment memo, or final investment recommendation. It downloads up to
    ten annual reports and uses only their audit/notes evidence for governance
    risk, alongside current NSE corporate/PIT/shareholding signals.
    """
    symbol = symbol.upper().strip()
    print(f"{'=' * 72} CORPORATE RISK ONLY | {symbol}{'=' * 72}")
    print(f"[*] Annual-report history requested: {report_years} years")

    filing_data = {"announcements": [], "pit_risk_rows": [], "shareholding": {}}
    if live_filings:
        print("[*] Collecting current NSE corporate/PIT/shareholding signals...")
        filing_data = NSECorporateFilings().cached_risk_inputs(symbol, days=180, refresh=True)

    shareholding = filing_data.get("shareholding", {})
    promoter_holding = filing_data.get("promoter_holding_pct")
    promoter_pledge = filing_data.get("promoter_pledge_pct")
    promoter_change = filing_data.get("promoter_change_pct")

    audits = []
    downloader = NSEDownloader()
    reports = downloader.download_reports(symbol, years=report_years)
    print(f"[+] Annual reports downloaded/available: {len(reports)}")

    ai = AnalysisOrchestrator()
    for item in reports:
        fy = item.get("fiscal_year", "Unknown")
        try:
            parser = FinancialDocParser(item["path"])
            sections = parser.extract_critical_sections()
            print(f"[*] Forensic governance audit: {fy}")
            forensic = ai.audit_forensics(sections.get("auditor_report", ""), sections.get("notes", ""))
            audits.append({
                "fiscal_year": fy,
                "audit_opinion_type": forensic.audit_opinion_type,
                "contingent_liability_risk": forensic.contingent_liability_risk,
                "related_party_risk": forensic.related_party_risk,
                "forensic_red_flags": forensic.forensic_red_flags,
            })
        except Exception as exc:
            print(f"[!] Could not audit {fy}: {type(exc).__name__}: {exc}")

    if not reports:
        report_gap = "No annual reports available from NSE"
    elif len(audits) < min(report_years, len(reports)):
        report_gap = f"Only {len(audits)}/{len(reports)} available reports were successfully audited"
    else:
        report_gap = None

    announcements = extract_announcements_from_rows(
        [*filing_data.get("announcements", []), *filing_data.get("pit_risk_rows", [])]
    )
    corporate = assess_corporate_risk(
        promoter_holding_pct=promoter_holding,
        promoter_pledge_pct=promoter_pledge,
        promoter_change_pct=promoter_change,
        announcements=announcements,
        annual_report_audits=audits,
    )
    if report_gap:
        corporate.data_gaps.append(report_gap)

    # Save structured corporate governance result.
    import json

    output_dir = os.path.join("outputs", symbol)
    os.makedirs(output_dir, exist_ok=True)

    governance_result = {
        "symbol": symbol,
        "analysis_type": "corporate_governance",
        "generated_at": datetime.now().isoformat(),
        "governance_grade": corporate.governance_grade,
        "risk_score": corporate.risk_score,
        "annual_report_score": corporate.annual_report_score,
        "hard_fail": corporate.hard_fail,
        "risk_flags": list(corporate.risk_flags or []),
        "positive_signals": list(corporate.positive_signals or []),
        "data_gaps": list(corporate.data_gaps or []),
        "promoter_holding_pct": promoter_holding,
        "promoter_pledge_pct": promoter_pledge,
        "promoter_change_pct": promoter_change,
        "annual_report_audits": audits,
    }

    governance_file = os.path.join(
        output_dir,
        "corporate_governance.json",
    )

    with open(governance_file, "w", encoding="utf-8") as f:
        json.dump(
            governance_result,
            f,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    print(f"[+] Corporate governance result saved: {governance_file}")

    print("" + "=" * 72)
    print("CORPORATE GOVERNANCE RISK")
    print("=" * 72)

    print("OVERALL VERDICT")
    print(f"  Governance Grade   : {corporate.governance_grade}")
    print(f"  Numerical Risk     : {corporate.risk_score}/100")
    print(f"  Annual Report Risk : {corporate.annual_report_score}/100")
    print(
        f"  Critical Override  : "
        f"{'YES' if corporate.hard_fail else 'NO'}"
    )

    print("WHY?")

    if corporate.hard_fail:
        critical_flags = []

        for flag in corporate.risk_flags:
            text_lower = str(flag).lower()

            if any(
                term in text_lower
                for term in (
                    "fraud",
                    "forensic",
                    "adverse audit",
                    "disclaimer",
                    "insolvency",
                    "diversion",
                    "misstatement",
                    "money laundering",
                )
            ):
                critical_flags.append(flag)

        if critical_flags:
            for flag in critical_flags:
                print(f"  [CRITICAL] {flag}")
        else:
            print("  [CRITICAL] Critical governance trigger detected.")
    else:
        print("  No critical governance override detected.")

    print("KEY CONCERNS")

    concerns_found = False

    # Show the actual forensic findings from annual reports.
    for audit in audits:
        fiscal_year = str(audit.get("fiscal_year", "Unknown"))

        red_flags = audit.get("forensic_red_flags") or []

        if isinstance(red_flags, str):
            red_flags = [red_flags]

        if not red_flags:
            continue

        concerns_found = True

        print(f"  [!] {fiscal_year}")

        for red_flag in red_flags:
            print(f"      • {str(red_flag).strip()}")

    # Show other governance concerns.
    for flag in corporate.risk_flags:
        text_lower = str(flag).lower()

        # Annual-report forensic counts are already represented above.
        if "forensic red flag" in text_lower:
            continue

        print(f"  [!] {flag}")
        concerns_found = True

    if not concerns_found:
        print("  None identified.")

    print("POSITIVE SIGNALS")

    if corporate.positive_signals:
        for signal in corporate.positive_signals:
            print(f"  [+] {signal}")
    else:
        print("  None identified.")

    print("DATA LIMITATIONS")

    if corporate.data_gaps:
        for gap in corporate.data_gaps:
            print(f"  [?] {gap}")
    else:
        print("  None identified.")

    print("10-YEAR HISTORY")
    print(
        "  FY       Audit      Related Party    "
        "Contingent Risk    Flags"
    )
    print("  " + "-" * 65)

    for audit in audits:
        fiscal_year = str(audit.get("fiscal_year", "Unknown"))

        short_year = fiscal_year
        if fiscal_year.startswith("FY"):
            short_year = fiscal_year[2:]

        audit_opinion = str(
            audit.get("audit_opinion_type") or "Unknown"
        ).strip()

        audit_lower = audit_opinion.lower()

        if (
            "unmodified" in audit_lower
            or "unqualified" in audit_lower
            or audit_lower == "clean"
        ):
            audit_display = "Clean"
        elif "qualified" in audit_lower:
            audit_display = "Qualified"
        elif "adverse" in audit_lower:
            audit_display = "Adverse"
        elif "disclaimer" in audit_lower:
            audit_display = "Disclaimer"
        else:
            audit_display = audit_opinion[:12]

        def _risk_label(value):
            value_text = str(value or "Unknown").strip().lower()

            for level in (
                "very high",
                "critical",
                "high",
                "moderate",
                "medium",
                "low",
            ):
                if value_text.startswith(level):
                    return level.title()

            return "Unknown"

        related_display = _risk_label(
            audit.get("related_party_risk")
        )

        contingent_display = _risk_label(
            audit.get("contingent_liability_risk")
        )

        red_flags = audit.get("forensic_red_flags") or []

        if isinstance(red_flags, str):
            red_flags = [red_flags]

        red_flag_count = len(red_flags)

        critical_year = any(
            any(
                term in str(red_flag).lower()
                for term in (
                    "fraud",
                    "forensic",
                    "diversion",
                    "misstatement",
                    "money laundering",
                    "insolvency",
                )
            )
            for red_flag in red_flags
        )

        flag_display = str(red_flag_count)

        if critical_year:
            flag_display += " [CRITICAL]"

        print(
            f"  {short_year:<8}"
            f"{audit_display:<11}"
            f"{related_display:<17}"
            f"{contingent_display:<19}"
            f"{flag_display}"
        )

    print("INVESTOR INTERPRETATION")

    if corporate.hard_fail:
        print("  Critical forensic/governance trigger detected.")
        print(
            "  Manual review of the underlying annual-report "
            "evidence is required."
        )
        print(
            "  Numerical risk score alone does not determine the "
            "Governance Grade."
        )
        print(
            "  The Governance Grade is currently driven by the "
            "Critical Override."
        )
    elif corporate.risk_score >= 50:
        print(
            "  Governance risk is elevated based on the numerical "
            "risk score."
        )
    elif corporate.risk_score >= 30:
        print(
            "  Some governance concerns are present and should be "
            "monitored."
        )
    else:
        print(
            "  No major governance risk detected from the available "
            "signals."
        )

    print("=" * 72)


def run_financial_analysis_only(
    symbol: str,
    price: float | None = None,
    shares_cr: float | None = None,
    target_pe: float = 25.0,
    mos: float = 20.0,
):
    """Run financial analysis only and persist the structured result."""

    symbol = symbol.upper().strip()

    print()
    print("=" * 72)
    print(f"FINANCIAL ANALYSIS | {symbol}")
    print("=" * 72)

    print("[*] Downloading annual report...")
    pdf_path = NSEDownloader().download_report(symbol)

    if not pdf_path:
        print(f"[!] Could not download annual report for {symbol}.")
        return

    parser = FinancialDocParser(pdf_path)
    sections = parser.extract_critical_sections()

    orchestrator = AnalysisOrchestrator()

    print("[*] Extracting financial history...")
    history = orchestrator.extract_metrics_payload(
        sections["financial_statements"]
    )

    print("[*] Calculating fundamental ratios...")
    ratios = calculate_fundamental_ratios(history)

    # Governance is intentionally kept separate from this analysis.
    # The final investment decision will combine the two later.
    quality = calculate_quality_score(
        ratios,
        governance_clean=True,
    )

    valuation = {
        "available": False,
        "reason": (
            "Current price and shares outstanding were not supplied. "
            "Valuation will be calculated during Investment Decision "
            "when available."
        ),
    }

    if price is not None and shares_cr is not None:
        print("[*] Calculating P/E valuation...")
        valuation = calculate_pe_valuation(
            price,
            shares_cr,
            history.years[-1].pat,
            ratios["PAT CAGR (%)"],
            target_pe,
            mos,
        )

    # Financial score deliberately excludes the governance component.
    financial_components = {
        key: value
        for key, value in quality.get("components", {}).items()
        if key != "governance"
    }

    financial_score = sum(
        int(value or 0)
        for value in financial_components.values()
    )

    financial_result = {
        "symbol": symbol,
        "analysis_type": "financial_analysis",
        "generated_at": datetime.now().isoformat(),

        "financial_score": financial_score,
        "financial_components": financial_components,

        "ratios": dict(ratios),

        "valuation": valuation,

        "history": {
            "fiscal_years": [
                str(year.fiscal_year)
                for year in history.years
            ],
            "revenue": [
                year.revenue
                for year in history.years
            ],
            "ebit": [
                year.ebit
                for year in history.years
            ],
            "pat": [
                year.pat
                for year in history.years
            ],
        },
    }

    output_dir = os.path.join("outputs", symbol)
    os.makedirs(output_dir, exist_ok=True)

    financial_file = os.path.join(
        output_dir,
        "financial_analysis.json",
    )

    import json

    with open(financial_file, "w", encoding="utf-8") as f:
        json.dump(
            financial_result,
            f,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    print()
    print("=" * 72)
    print("FINANCIAL ANALYSIS RESULT")
    print("=" * 72)
    print(f"  Financial Score : {financial_score}/80")
    print(f"  History Years   : {len(history.years)}")

    if valuation.get("available"):
        print(
            f"  Fair Value      : ₹{valuation['fair_value']}"
        )
        print(
            f"  Buy Below       : ₹{valuation['buy_below']}"
        )
    else:
        print("  Valuation       : Not calculated")

    print(f"[+] Financial analysis saved: {financial_file}")
    print("=" * 72)


def run_investment_decision_only(symbol: str):
    """Combine saved governance and financial results using the existing decision engine."""

    import json

    symbol = symbol.upper().strip()

    output_dir = os.path.join("outputs", symbol)

    governance_file = os.path.join(
        output_dir,
        "corporate_governance.json",
    )

    financial_file = os.path.join(
        output_dir,
        "financial_analysis.json",
    )

    print()
    print("=" * 72)
    print(f"INVESTMENT DECISION | {symbol}")
    print("=" * 72)

    if not os.path.exists(governance_file):
        print(
            "[!] Corporate governance result not found."
        )
        print(
            f"    Expected: {governance_file}"
        )
        print(
            "    Run Corporate Governance Analysis first."
        )
        return

    if not os.path.exists(financial_file):
        print(
            "[!] Financial analysis result not found."
        )
        print(
            f"    Expected: {financial_file}"
        )
        print(
            "    Run Financial Analysis first."
        )
        return

    with open(
        governance_file,
        "r",
        encoding="utf-8",
    ) as f:
        governance = json.load(f)

    with open(
        financial_file,
        "r",
        encoding="utf-8",
    ) as f:
        financial = json.load(f)

    governance_grade = str(
        governance.get("governance_grade", "D")
    ).upper()

    forensic_clean = not bool(
        governance.get("hard_fail", True)
    )

    financial_components = financial.get(
        "financial_components",
        {},
    )

    # Reconstruct the quality structure expected by the
    # existing decision engine. Governance remains separate.
    quality = {
        "components": {
            **financial_components,
        },
        "score_100": financial.get(
            "financial_score",
            0,
        ),
    }

    ratios = financial.get(
        "ratios",
        {},
    )

    valuation = financial.get(
        "valuation",
        {
            "available": False,
        },
    )

    decision = calculate_investment_decision(
        quality=quality,
        ratios=ratios,
        valuation=valuation,
        governance_grade=governance_grade,
        forensic_clean=forensic_clean,
    )

    investment_result = {
        "symbol": symbol,
        "analysis_type": "investment_decision",
        "generated_at": datetime.now().isoformat(),

        "verdict": decision["verdict"],
        "reason": decision["reason"],
        "decision_score": decision["decision_score"],
        "decision_components": decision["decision_components"],
        "valuation_state": decision["valuation_state"],

        "governance": {
            "grade": governance_grade,
            "risk_score": governance.get("risk_score"),
            "annual_report_score": governance.get(
                "annual_report_score"
            ),
            "hard_fail": governance.get("hard_fail"),
        },

        "financial": {
            "financial_score": financial.get(
                "financial_score"
            ),
            "components": financial_components,
            "ratios": ratios,
        },
    }

    os.makedirs(
        output_dir,
        exist_ok=True,
    )

    decision_file = os.path.join(
        output_dir,
        "investment_decision.json",
    )

    with open(
        decision_file,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            investment_result,
            f,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    # Save detailed human-readable investment decision report.
    report_file = os.path.join(
        output_dir,
        "investment_decision.txt",
    )

    lines = []

    lines.append("=" * 72)
    lines.append(f"             INVESTMENT DECISION REPORT")
    lines.append("=" * 72)
    lines.append("")
    lines.append(f"Stock              : {symbol}")
    lines.append(
        f"Generated          : {investment_result['generated_at']}"
    )
    lines.append("")

    # ------------------------------------------------------------
    # FINAL DECISION
    # ------------------------------------------------------------
    lines.append("-" * 72)
    lines.append("FINAL INVESTMENT DECISION")
    lines.append("-" * 72)
    lines.append("")
    lines.append(
        f"VERDICT            : {decision['verdict']}"
    )
    lines.append(
        f"DECISION SCORE     : {decision['decision_score']}"
    )
    lines.append(
        f"FUNDAMENTAL SCORE  : "
        f"{decision['decision_components']['fundamental_quality']}"
    )
    lines.append(
        f"GOVERNANCE SCORE   : "
        f"{decision['decision_components']['governance']}"
    )
    lines.append(
        f"VALUATION SCORE    : "
        f"{decision['decision_components']['valuation']}"
    )
    lines.append(
        f"VALUATION STATE    : {decision['valuation_state']}"
    )
    lines.append("")

    lines.append("REASON")
    lines.append(f"  {decision['reason']}")
    lines.append("")

    # ------------------------------------------------------------
    # DECISION LOGIC
    # ------------------------------------------------------------
    lines.append("-" * 72)
    lines.append("DECISION LOGIC")
    lines.append("-" * 72)
    lines.append("")

    lines.append("1. GOVERNANCE SCORING")
    lines.append("   Grade A = 10 points")
    lines.append("   Grade B = 8 points")
    lines.append("   Grade C = 4 points")
    lines.append("   Grade D = 0 points")
    lines.append("")

    lines.append("2. VALUATION SCORING")
    lines.append("   Margin of Safety = 10 points")
    lines.append("   Below Fair Value  = 6 points")
    lines.append("   Above Fair Value  = 0 points")
    lines.append("   Unavailable       = 0 points")
    lines.append("")

    lines.append("3. AVOID CONDITIONS")
    lines.append("   - Forensic/governance clearance fails")
    lines.append("   - Persistently weak operating cash flow")
    lines.append("   - Fundamental score < 40")
    lines.append("")

    lines.append("4. BUY CONDITION")
    lines.append("   - Valuation has a Margin of Safety")
    lines.append("   - Fundamental score >= 60")
    lines.append("   - Governance score >= 8")
    lines.append("")

    lines.append("5. WATCHLIST CONDITION")
    lines.append("   - Decision score >= 60")
    lines.append("   - BUY conditions are not fully satisfied")
    lines.append("")

    # ------------------------------------------------------------
    # GOVERNANCE
    # ------------------------------------------------------------
    lines.append("-" * 72)
    lines.append("CORPORATE GOVERNANCE")
    lines.append("-" * 72)
    lines.append("")

    lines.append(
        f"Governance Grade   : {governance_grade}"
    )
    lines.append(
        f"Governance Score   : "
        f"{decision['decision_components']['governance']}"
    )
    lines.append(
        f"Risk Score         : "
        f"{governance.get('risk_score')}"
    )
    lines.append(
        f"Annual Report Score: "
        f"{governance.get('annual_report_score')}"
    )
    lines.append(
        f"Hard Fail          : "
        f"{governance.get('hard_fail')}"
    )
    lines.append(
        f"Promoter Holding   : "
        f"{governance.get('promoter_holding_pct')}%"
    )
    lines.append(
        f"Promoter Pledge    : "
        f"{governance.get('promoter_pledge_pct')}"
    )
    lines.append(
        f"Promoter Change    : "
        f"{governance.get('promoter_change_pct')}%"
    )
    lines.append("")

    lines.append("Risk Flags:")
    risk_flags = governance.get("risk_flags", [])

    if risk_flags:
        for flag in risk_flags:
            lines.append(f"  - {flag}")
    else:
        lines.append("  - None")
    lines.append("")

    lines.append("Positive Signals:")
    positive_signals = governance.get(
        "positive_signals",
        [],
    )

    if positive_signals:
        for signal in positive_signals:
            lines.append(f"  + {signal}")
    else:
        lines.append("  - None")
    lines.append("")

    lines.append("Data Gaps:")
    data_gaps = governance.get(
        "data_gaps",
        [],
    )

    if data_gaps:
        for gap in data_gaps:
            lines.append(f"  - {gap}")
    else:
        lines.append("  - None")
    lines.append("")

    # ------------------------------------------------------------
    # FINANCIAL ANALYSIS
    # ------------------------------------------------------------
    lines.append("-" * 72)
    lines.append("FINANCIAL ANALYSIS")
    lines.append("-" * 72)
    lines.append("")

    lines.append(
        f"Financial Score    : "
        f"{financial.get('financial_score')}/80"
    )
    lines.append("")

    lines.append("Financial Components:")

    for name, score in financial_components.items():
        lines.append(
            f"  {name.replace('_', ' ').title():22}: {score}"
        )

    lines.append("")

    # ------------------------------------------------------------
    # RATIOS
    # ------------------------------------------------------------
    lines.append("-" * 72)
    lines.append("FINANCIAL RATIOS")
    lines.append("-" * 72)
    lines.append("")

    ratios = financial.get("ratios", {})

    for name, value in ratios.items():
        if name == "hurdles_passed":
            continue

        lines.append(
            f"{name:32}: {value}"
        )

    lines.append("")

    # ------------------------------------------------------------
    # FINANCIAL HISTORY
    # ------------------------------------------------------------
    history = financial.get(
        "history",
        {},
    )

    lines.append("-" * 72)
    lines.append("FINANCIAL HISTORY USED")
    lines.append("-" * 72)
    lines.append("")

    fiscal_years = history.get(
        "fiscal_years",
        [],
    )
    revenues = history.get(
        "revenue",
        [],
    )
    ebits = history.get(
        "ebit",
        [],
    )
    pats = history.get(
        "pat",
        [],
    )

    lines.append(
        f"{'Fiscal Year':15}"
        f"{'Revenue':15}"
        f"{'EBIT':15}"
        f"{'PAT':15}"
    )
    lines.append("-" * 60)

    for i, fiscal_year in enumerate(fiscal_years):
        revenue = revenues[i] if i < len(revenues) else "N/A"
        ebit = ebits[i] if i < len(ebits) else "N/A"
        pat = pats[i] if i < len(pats) else "N/A"

        lines.append(
            f"{str(fiscal_year):15}"
            f"{str(revenue):15}"
            f"{str(ebit):15}"
            f"{str(pat):15}"
        )

    lines.append("")

    # ------------------------------------------------------------
    # VALUATION
    # ------------------------------------------------------------
    lines.append("-" * 72)
    lines.append("VALUATION")
    lines.append("-" * 72)
    lines.append("")

    valuation = financial.get(
        "valuation",
        {},
    )

    lines.append(
        f"Available          : "
        f"{valuation.get('available')}"
    )

    if valuation.get("available"):
        lines.append(
            f"Current Price      : "
            f"{valuation.get('current_price')}"
        )
        lines.append(
            f"Fair Value         : "
            f"{valuation.get('fair_value')}"
        )
        lines.append(
            f"Buy Below          : "
            f"{valuation.get('buy_below')}"
        )
    else:
        lines.append(
            f"Reason             : "
            f"{valuation.get('reason', 'Unavailable')}"
        )

    lines.append("")

    # ------------------------------------------------------------
    # DECISION COMPONENT SUMMARY
    # ------------------------------------------------------------
    lines.append("-" * 72)
    lines.append("DECISION COMPONENT SUMMARY")
    lines.append("-" * 72)
    lines.append("")

    for name, score in decision[
        "decision_components"
    ].items():
        lines.append(
            f"{name.replace('_', ' ').title():25}: {score}"
        )

    lines.append("")

    # ------------------------------------------------------------
    # SOURCE FILES
    # ------------------------------------------------------------
    lines.append("-" * 72)
    lines.append("SOURCE FILES")
    lines.append("-" * 72)
    lines.append("")
    lines.append(
        "Corporate Governance : "
        "corporate_governance.json"
    )
    lines.append(
        "Financial Analysis   : "
        "financial_analysis.json"
    )
    lines.append(
        "Decision Engine      : "
        "src/decision_engine.py"
    )
    lines.append("")

    lines.append("=" * 72)
    lines.append("                    END OF REPORT")
    lines.append("=" * 72)

    with open(
        report_file,
        "w",
        encoding="utf-8",
    ) as f:
        f.write("\n".join(lines))

    print(
        f"[+] Detailed investment report saved: "
        f"{report_file}"
    )
    print()
    print("=" * 72)
    print("INVESTMENT DECISION")
    print("=" * 72)

    print(
        f"  Verdict           : {decision['verdict']}"
    )
    print(
        f"  Decision Score    : {decision['decision_score']}"
    )
    print(
        f"  Fundamental Score : "
        f"{decision['decision_components']['fundamental_quality']}"
    )
    print(
        f"  Governance Score  : "
        f"{decision['decision_components']['governance']}"
    )
    print(
        f"  Valuation Score   : "
        f"{decision['decision_components']['valuation']}"
    )
    print(
        f"  Valuation State   : {decision['valuation_state']}"
    )

    print()
    print("REASON")
    print(f"  {decision['reason']}")

    print()
    print(
        f"[+] Investment decision saved: {decision_file}"
    )
    print("=" * 72)


def save_summary_to_notepad(symbol, forensics, ratios, quality, valuation, recommendation, memo, output_dir="./outputs"):
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filepath = os.path.join(output_dir, f"{symbol.upper()}_Investment_Summary_{timestamp}.txt")
    divider, sub = "=" * 70, "-" * 70
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"{divider}FIVE-YEAR EQUITY RESEARCH INVESTMENT MEMO")
        f.write(f"Company: {symbol.upper()} | Date: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}{divider}")
        f.write(f"[FINAL VERDICT]: {recommendation['verdict']}")
        f.write(f"[DETERMINISTIC QUALITY SCORE]: {quality['score_100']} / 100")
        f.write(f"[AI THESIS CONVICTION]: {memo.conviction_score} / 10")
        f.write(f"[GOVERNANCE]: {'PASSED' if memo.governance_clearance else 'FAILED / REVIEW'}")
        f.write(f"[DECISION LOGIC]: {recommendation['reason']}")
        f.write(f"{sub}EXECUTIVE THESIS{sub}{memo.executive_summary.strip()}")
        f.write(f"{sub}FIVE-YEAR FUNDAMENTALS{sub}")
        for metric, value in ratios.items():
            if metric != "hurdles_passed": f.write(f"  • {metric:<30}: {value}")
        f.write("Hurdles:")
        for check, passed in ratios.get("hurdles_passed", {}).items(): f.write(f"  • {check.replace('_', ' ').title():<30}: {'PASS [✓]' if passed else 'FAIL [X]'}")
        f.write(f"{sub}QUALITY SCORE{sub}")
        for component, points in quality["components"].items(): f.write(f"  • {component.replace('_', ' ').title():<30}: {points:>2} / 20")
        f.write(f"  TOTAL: {quality['score_100']} / 100")
        f.write(f"{sub}VALUATION{sub}")
        if valuation.get("available"):
            for key, value in valuation.items():
                if key != "available": f.write(f"  • {key.replace('_', ' ').title():<30}: {value}")
        else: f.write(f"  • {valuation.get('reason', 'Not calculated.')}")
        f.write(f"{sub}FORENSIC & GOVERNANCE{sub}")
        f.write(f"  • Audit Opinion             : {forensics.audit_opinion_type}")
        f.write(f"  • Contingent Liability Risk : {forensics.contingent_liability_risk}")
        f.write(f"  • Related Party Risk        : {forensics.related_party_risk}")
        f.write("  Key Audit Matters:")
        for item in forensics.key_audit_matters or ["None specified."]: f.write(f"    - {item}")
        f.write("  Forensic Red Flags:")
        for item in forensics.forensic_red_flags or ["None detected."]: f.write(f"    ! {item}")
        f.write(f"{sub}FINANCIAL STRENGTHS{sub}")
        for item in memo.financial_strengths: f.write(f"  [+] {item}")
        f.write(f"{sub}CRITICAL RISKS{sub}")
        for item in memo.critical_risks: f.write(f"  [-] {item}")
        f.write(f"{divider}End of Report")
    return filepath


def run_universe_scan(refresh=False, top=50, limit=None, output_dir="./outputs"):
    """Stage 1: exchange-level discovery only; not an investment recommendation."""
    cfg = SmallMicrocapConfig(); universe = NSEUniverse()
    print("[*] Discovering NSE equity universe...")
    rows = universe.discover(limit=limit, refresh=refresh); candidates = []
    for row in rows:
        market_cap, price, traded_value = row.get("market_cap_cr"), row.get("price"), row.get("avg_daily_value_cr")
        if market_cap is None or price is None or traded_value is None: continue
        category = classify_market_cap(float(market_cap), cfg)
        if category not in ("MICROCAP", "SMALLCAP"): continue
        if float(price) < cfg.min_price or float(traded_value) < cfg.min_daily_traded_value_cr: continue
        candidates.append({**row, "market_cap_category": category})
    candidates.sort(key=lambda x: (0 if x["market_cap_category"] == "MICROCAP" else 1, -float(x["market_cap_cr"]), -float(x["avg_daily_value_cr"])))
    selected = candidates[:top]; os.makedirs(output_dir, exist_ok=True); path = os.path.join(output_dir, "small_microcap_universe.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fields = ["symbol", "company_name", "market_cap_category", "market_cap_cr", "price", "avg_daily_value_cr", "source"]
        writer = csv.DictWriter(fh, fieldnames=fields); writer.writeheader(); writer.writerows({k: row.get(k) for k in fields} for row in selected)
    print(f"[+] NSE rows collected: {len(rows)}"); print(f"[+] Candidates passing market/liquidity filters: {len(candidates)}"); print(f"[+] Saved top {len(selected)} candidates to: {path}")
    print("TOP CANDIDATES — Stage 1 only (NOT investment recommendations)"); print("-" * 95)
    for i, row in enumerate(selected, 1): print(f"{i:>2}. {row['symbol']:<15} {row['market_cap_category']:<9} MCap ₹{float(row['market_cap_cr']):>9.0f} Cr  Price ₹{float(row['price']):>8.2f}  Traded ₹{float(row['avg_daily_value_cr']):>7.2f} Cr")
    return selected


def main(symbol, price=None, shares_cr=None, target_pe=25.0, mos=20.0):
    symbol = symbol.upper().strip(); print(f"========================================== Starting V2 NSE Analysis Agent | {symbol}==========================================")
    pdf_path = NSEDownloader().download_report(symbol)
    if not pdf_path: print(f"[!] Could not download annual report for {symbol}. Exiting."); sys.exit(1)
    parser = FinancialDocParser(pdf_path); sections = parser.extract_critical_sections(); orchestrator = AnalysisOrchestrator()
    print("[*] Running forensic governance audit..."); forensics = orchestrator.audit_forensics(sections["auditor_report"], sections["notes"])
    print("[*] Extracting five-year financial history..."); history = orchestrator.extract_metrics_payload(sections["financial_statements"]); ratios = calculate_fundamental_ratios(history)
    governance_clean = (forensics.audit_opinion_type.lower().startswith("unmodified") and forensics.contingent_liability_risk.lower().startswith("low") and forensics.related_party_risk.lower().startswith("low") and not forensics.forensic_red_flags)
    quality = calculate_quality_score(ratios, governance_clean=governance_clean); valuation = {"available": False, "reason": "Supply --price and --shares-cr to calculate transparent P/E fair value."}
    if price is not None and shares_cr is not None: valuation = calculate_pe_valuation(price, shares_cr, history.years[-1].pat, ratios["PAT CAGR (%)"], target_pe, mos)
    print("[*] Generating investment thesis..."); memo = orchestrator.run_investment_committee(forensics, ratios, quality, valuation); recommendation = determine_final_recommendation(quality, ratios, governance_clean, valuation); memo.verdict = recommendation["verdict"]
    print("" + "=" * 60); print(f"FINAL VERDICT: {recommendation['verdict']}"); print(f"QUALITY SCORE: {quality['score_100']}/100"); print(f"AI THESIS CONVICTION: {memo.conviction_score}/10")
    if valuation.get("available"): print(f"FAIR VALUE: ₹{valuation['fair_value']} | BUY BELOW: ₹{valuation['buy_below']}")
    print("=" * 60); saved_file = save_summary_to_notepad(symbol, forensics, ratios, quality, valuation, recommendation, memo); print(f"[+] Summary saved: {saved_file}")
    try: os.system(f'notepad "{saved_file}"')
    except Exception: pass


if __name__ == "__main__":
    cli = argparse.ArgumentParser(
        description="Indian equity research agent and small/micro-cap scanner"
    )

    cli.add_argument(
        "symbol",
        nargs="?",
        default=None,
        help="NSE symbol for deep analysis"
    )
    cli.add_argument("--scan", action="store_true", help="Stage 1: discover NSE small/micro-cap candidates")
    cli.add_argument("--deep-scan", action="store_true", help="Stage 2: deeply analyze the Stage-1 CSV")
    cli.add_argument("--corporate-risk", action="store_true", help="Corporate-risk-only test using up to ten annual reports")
    cli.add_argument("--corporate-years", type=int, default=10, help="Annual reports used by --corporate-risk (default: 10)")
    cli.add_argument("--refresh", action="store_true", help="Refresh the NSE universe cache")
    cli.add_argument("--top", type=int, default=50, help="Stage-1 candidates or Stage-2 shortlist size")
    cli.add_argument("--deep-limit", type=int, default=20, help="Maximum Stage-1 candidates sent to deep analysis")
    cli.add_argument("--no-live-filings", action="store_true", help="Disable live NSE corporate/PIT filing checks")
    cli.add_argument("--limit", type=int, help="Limit universe symbols for testing")
    cli.add_argument("--input-csv", default="./outputs/small_microcap_universe.csv", help="Stage-1 CSV for Stage 2")
    cli.add_argument("--price", type=float, help="Current share price for single-stock valuation")
    cli.add_argument("--shares-cr", type=float, help="Shares outstanding in crore for single-stock valuation")
    cli.add_argument("--target-pe", type=float, default=25.0, help="Target P/E multiple")
    cli.add_argument("--mos", type=float, default=20.0, help="Margin of safety percentage")

    args = cli.parse_args()

    # Interactive menu when no command-line arguments are supplied.
    # Interactive menu when no command-line arguments are supplied.
    if len(sys.argv) == 1:
        while True:
            print("" + "=" * 60)
            print("        NSE EQUITY RESEARCH AGENT")
            print("=" * 60)
            print()
            print("1. Deep Scan")
            print("2. Small / micro-cap universe scan")
            print("3. Exit")
            print()

            choice = input("Select an option [1-3]: ").strip()

            if choice == "1":
                symbol = input("Enter NSE symbol for Deep Scan: ").strip()

                if not symbol:
                    print("[!] Symbol is required.")
                    continue

                while True:
                    print()
                    print("" + "-" * 60)
                    print(f"        DEEP SCAN: {symbol.upper()}")
                    print("-" * 60)
                    print()
                    print("1. Corporate Governance Analysis")
                    print("2. Financial Analysis")
                    print("3. Investment Decision")
                    print("4. Generate Investment Report")
                    print("5. Back")
                    print()

                    deep_choice = input("Select an option [1-5]: ").strip()

                    if deep_choice == "1":
                        years_input = input(
                            "Number of annual reports [10]: "
                        ).strip()

                        try:
                            years = int(years_input) if years_input else 10
                        except ValueError:
                            print("[!] Invalid number of years.")
                            continue

                        years = max(1, min(years, 10))

                        run_corporate_risk_only(
                            symbol,
                            report_years=years,
                            live_filings=True,
                        )

                    elif deep_choice == "2":
                        run_financial_analysis_only(symbol)

                    elif deep_choice == "3":
                        run_investment_decision_only(symbol)

                    elif deep_choice == "4":
                        report_file = os.path.join(
                            "outputs",
                            symbol.upper(),
                            "investment_decision.txt",
                        )

                        if not os.path.exists(report_file):
                            print()
                            print("[!] Investment decision report not found.")
                            print("    Run Investment Decision first.")
                            continue

                        try:
                            generated_report = generate_investment_report(
                                report_file
                            )

                            print()
                            print("=" * 72)
                            print("INVESTMENT REPORT")
                            print("=" * 72)
                            print()
                            print(
                                f"[+] Visual report generated: {generated_report}"
                            )
                            print()

                            open_report = input(
                                "Open report in browser? [Y/n]: "
                            ).strip().lower()

                            if open_report in ("", "y", "yes"):
                                import webbrowser

                                webbrowser.open(
                                    os.path.abspath(generated_report)
                                )

                        except Exception as exc:
                            print()
                            print(
                                f"[!] Could not generate investment report: "
                                f"{type(exc).__name__}: {exc}"
                            )

                    elif deep_choice == "5":
                        break

                    else:
                        print("[!] Invalid option.")

            elif choice == "2":
                run_universe_scan(
                    refresh=False,
                    top=50,
                    limit=None,
                )

            elif choice == "3":
                print("Exiting.")
                sys.exit(0)

            else:
                print("[!] Invalid option.")

    # Command-line modes.
    if args.corporate_risk:
        if not args.symbol:
            cli.error("--corporate-risk requires a symbol")

        run_corporate_risk_only(
            args.symbol,
            report_years=max(1, min(args.corporate_years, 10)),
            live_filings=not args.no_live_filings,
        )

    elif args.deep_scan:
        run_deep_scan(
            input_csv=args.input_csv,
            top=args.top,
            deep_limit=args.deep_limit,
            live_filings=not args.no_live_filings,
        )

    elif args.scan:
        run_universe_scan(
            refresh=args.refresh,
            top=args.top,
            limit=args.limit,
        )

    elif args.symbol:
        main(
            args.symbol,
            args.price,
            args.shares_cr,
            args.target_pe,
            args.mos,
        )

    else:
        cli.print_help()
