"""CLI for the unified NSE equity research pipeline.

The CLI is intentionally thin. Analysis belongs to the stage engines in
``src``; this file only collects user input and invokes those stages.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import Any, Dict, List

from dotenv import load_dotenv

from src.deep_scanner import DeepScannerEngine
from src.governance_report import generate_governance_text_report
from src.nse_universe import NSEUniverse
from src.report_generator import generate_investment_report, generate_investment_text_report
from src.smallcap_scanner import SmallMicrocapConfig, classify_market_cap

load_dotenv()


OUTPUT_DIR = "./outputs"
UNIVERSE_FILE = os.path.join(OUTPUT_DIR, "small_microcap_universe.csv")


def run_universe_scan(
    refresh: bool = False,
    top: int = 50,
    limit: int | None = None,
    output_dir: str = OUTPUT_DIR,
) -> List[Dict[str, Any]]:
    """Stage 1: discover and filter candidates for the unified pipeline."""
    cfg = SmallMicrocapConfig()
    universe = NSEUniverse()
    print("[*] Discovering NSE equity universe...")
    rows = universe.discover(limit=limit, refresh=refresh)
    candidates: List[Dict[str, Any]] = []

    for row in rows:
        market_cap = row.get("market_cap_cr")
        price = row.get("price")
        traded_value = row.get("avg_daily_value_cr")
        if market_cap is None or price is None or traded_value is None:
            continue
        category = classify_market_cap(float(market_cap), cfg)
        if category not in ("MICROCAP", "SMALLCAP"):
            continue
        if float(price) < cfg.min_price or float(traded_value) < cfg.min_daily_traded_value_cr:
            continue
        candidates.append({**row, "market_cap_category": category})

    candidates.sort(
        key=lambda row: (
            0 if row["market_cap_category"] == "MICROCAP" else 1,
            -float(row["market_cap_cr"]),
            -float(row["avg_daily_value_cr"]),
        )
    )
    selected = candidates[:top]
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "small_microcap_universe.csv")

    fields = [
        "symbol",
        "company_name",
        "market_cap_category",
        "market_cap_cr",
        "price",
        "avg_daily_value_cr",
        "source",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in fields} for row in selected)

    print(f"[+] NSE rows collected: {len(rows)}")
    print(f"[+] Candidates passing market/liquidity filters: {len(candidates)}")
    print(f"[+] Saved {len(selected)} candidates to: {path}")
    print("[+] Feed for new architecture: run --deep-scan")
    print("\nSTAGE 1 CANDIDATES — NOT INVESTMENT RECOMMENDATIONS")
    print("-" * 95)
    for index, row in enumerate(selected, 1):
        print(
            f"{index:>2}. {row['symbol']:<15} {row['market_cap_category']:<9} "
            f"MCap ₹{float(row['market_cap_cr']):>9.0f} Cr  "
            f"Price ₹{float(row['price']):>8.2f}  "
            f"Traded ₹{float(row['avg_daily_value_cr']):>7.2f} Cr"
        )
    return selected


def _show_result(result: Dict[str, Any]) -> None:
    print("\n" + "=" * 72)
    print(f"PIPELINE RESULT | {result.get('symbol', '')}")
    print("=" * 72)
    for key in (
        "status",
        "stage",
        "verdict",
        "decision_score",
        "quality_score",
        "governance_grade",
        "corporate_risk_score",
        "annual_reports_scanned",
        "fair_value",
        "buy_below",
    ):
        if key in result:
            print(f"{key.replace('_', ' ').title():22}: {result[key]}")
    if result.get("error"):
        print(f"Error                  : {result['error']}")
    print("=" * 72)


def run_single_stock(symbol: str, live_filings: bool = True) -> Dict[str, Any]:
    """Analyze a single stock through the exact same pipeline as scanner output."""
    result = DeepScannerEngine().analyze_symbol(symbol, live_filings=live_filings)
    _show_result(result)

    if result.get("status") == "ANALYZED":
        output_dir = os.path.join(OUTPUT_DIR, symbol)
        try:
            governance_report = generate_governance_text_report(output_dir)
            print(f"[+] Corporate governance report: {governance_report}")
        except Exception as exc:
            print(f"[!] Corporate governance report generation failed: {type(exc).__name__}: {exc}")
        try:
            text_report = generate_investment_text_report(output_dir)
            print(f"[+] Text investment report: {text_report}")
        except Exception as exc:
            print(f"[!] Text report generation failed: {type(exc).__name__}: {exc}")

    return result


def interactive() -> None:
    while True:
        print("\n" + "=" * 60)
        print("        NSE EQUITY RESEARCH AGENT")
        print("=" * 60)
        print("1. Deep Scan")
        print("2. Small / micro-cap universe scan")
        print("3. Exit")

        choice = input("\nSelect an option [1-3]: ").strip()

        if choice == "1":
            symbol = input("Enter NSE symbol for Deep Scan: ").strip().upper()
            if not symbol:
                print("[!] Symbol is required.")
                continue
            result = run_single_stock(symbol)
            if result.get("status") == "ANALYZED":
                output_dir = os.path.join(OUTPUT_DIR, symbol)
                open_report = input("Generate visual investment report? [Y/n]: ").strip().lower()
                if open_report in ("", "y", "yes"):
                    try:
                        generated = generate_investment_report(output_dir)
                        print(f"[+] Visual report generated: {generated}")
                    except Exception as exc:
                        print(f"[!] Visual report generation failed: {type(exc).__name__}: {exc}")

        elif choice == "2":
            run_universe_scan(refresh=False, top=50)
            answer = input("Run new architecture on the first 20 candidates? [Y/n]: ").strip().lower()
            if answer in ("", "y", "yes"):
                DeepScannerEngine().run(
                    input_csv=UNIVERSE_FILE,
                    top=10,
                    deep_limit=20,
                    live_filings=True,
                )

        elif choice == "3":
            print("Exiting.")
            return
        else:
            print("[!] Invalid option.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Indian equity research agent and small/micro-cap scanner"
    )
    parser.add_argument("symbol", nargs="?", default=None, help="NSE symbol for unified deep analysis")
    parser.add_argument("--scan", action="store_true", help="Stage 1: discover NSE small/micro-cap candidates")
    parser.add_argument("--deep-scan", action="store_true", help="Stage 2: run the unified pipeline on Stage-1 candidates")
    parser.add_argument("--refresh", action="store_true", help="Refresh the NSE universe cache")
    parser.add_argument("--top", type=int, default=50, help="Number of Stage-1 candidates or final shortlist size")
    parser.add_argument("--deep-limit", type=int, default=20, help="Maximum Stage-1 candidates sent to the new pipeline")
    parser.add_argument("--no-live-filings", action="store_true", help="Disable live NSE corporate/PIT filing checks")
    parser.add_argument("--limit", type=int, help="Limit universe symbols for testing")
    parser.add_argument("--input-csv", default=UNIVERSE_FILE, help="Stage-1 CSV consumed by --deep-scan")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if len(sys.argv) == 1:
        interactive()
        return

    live_filings = not args.no_live_filings

    if args.scan:
        run_universe_scan(refresh=args.refresh, top=args.top, limit=args.limit)
        return

    if args.deep_scan:
        DeepScannerEngine().run(
            input_csv=args.input_csv,
            top=args.top,
            deep_limit=args.deep_limit,
            live_filings=live_filings,
        )
        return

    if args.symbol:
        run_single_stock(args.symbol, live_filings=live_filings)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
