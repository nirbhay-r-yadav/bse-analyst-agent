"""Single-stock business and risk research entry point."""

from .deep_scanner import DeepScannerEngine


def analyze_stock(symbol: str):
    """Run business analysis and business/corporate-risk research only."""
    symbol = symbol.upper().strip()
    print(
        f"\n==========================================\n"
        f" BUSINESS + RISK RESEARCH | {symbol}\n"
        f"==========================================\n"
    )
    result = DeepScannerEngine().analyze_symbol(symbol)

    if result.get("status") != "ANALYZED":
        print(f"[!] Research failed: {result.get('error', 'unknown error')}")
        return result

    print(f"[+] Corporate risk score: {result.get('corporate_risk_score')}/100")
    print(f"[+] Governance grade: {result.get('governance_grade')}")
    print(f"[+] Annual reports scanned: {result.get('annual_reports_scanned')}")
    print(f"[+] Evidence items: {result.get('evidence_count')}")
    print(f"[+] Management promises: {result.get('management_promises')}")
    print("[+] No financial analysis, valuation or buy/sell decision was run.")
    return result
