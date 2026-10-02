"""Minimal interactive menu for business and corporate-risk research."""

import csv
import os
from typing import Optional


def _pause() -> None:
    input("\nPress Enter to return...")


def _symbol() -> Optional[str]:
    symbol = input("NSE symbol: ").strip().upper()
    if not symbol:
        print("[!] Symbol is required.")
        return None
    return symbol


def _market_cap() -> Optional[str]:
    print("\nMarket-cap universe")
    print("  1. Microcap")
    print("  2. Smallcap")
    print("  3. Midcap")
    print("  4. Largecap")
    print("  0. Back")
    choice = input("Choose universe: ").strip()
    return {
        "1": "MICROCAP",
        "2": "SMALLCAP",
        "3": "MIDCAP",
        "4": "LARGECAP",
    }.get(choice)


def _show_cached_watchlist(segment: str) -> bool:
    path = "./outputs/opportunity_scan.csv"
    if not os.path.exists(path):
        print(f"\n[!] No saved {segment} watchlist found.")
        print("    Run the initial scan first.")
        return False

    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    selected = [
        row
        for row in rows
        if str(row.get("market_cap_category", "")).upper() == segment
    ]
    if not selected:
        print(f"\n[!] No saved {segment} watchlist found.")
        return False

    print(f"\n[+] Loaded saved {segment} watchlist.")
    for index, row in enumerate(selected[:50], 1):
        print(
            f"{index:>2}. {row.get('symbol', ''):<15} "
            f"MCap ₹{float(row.get('market_cap_cr') or 0):>9.0f} Cr"
        )

    while True:
        choice = input(
            "\nEnter stock number for Business + Risk Research (0 = Back): "
        ).strip()
        if choice == "0":
            return True
        try:
            index = int(choice)
        except ValueError:
            print("[!] Enter a valid stock number.")
            continue

        if not 1 <= index <= min(50, len(selected)):
            print(
                f"[!] Choose a number from 1 to {min(50, len(selected))}, "
                "or 0 to go back."
            )
            continue

        symbol = str(selected[index - 1].get("symbol", "")).strip().upper()
        from src.stock_analysis import analyze_stock

        print(f"\n[*] Launching Business + Risk Research for {symbol}")
        analyze_stock(symbol)
        _pause()
        return True


def _universe_actions(segment: str) -> None:
    while True:
        print(f"\n{segment} universe")
        print("  1. Run / Refresh Quality Scan")
        print("  2. View Saved Top 50 Watchlist")
        print("  0. Back")
        choice = input("Choose: ").strip()

        if choice == "0":
            return

        if choice == "2":
            _show_cached_watchlist(segment)
            continue

        if choice == "1":
            refresh = (
                input("Refresh universe + quality scan? (y/N): ")
                .strip()
                .lower()
                == "y"
            )
            print(f"\n[*] Running full {segment} universe + quality scan...")
            from src.opportunity_scanner import run_opportunity_scan

            run_opportunity_scan(
                segment=segment, top=50, refresh=refresh
            )
            _pause()
            continue

        print("[!] Invalid option. Choose 1, 2 or 0.")


def _opportunity_scan() -> None:
    segment = _market_cap()
    if segment:
        _universe_actions(segment)


def _deep_stock() -> None:
    from src.stock_analysis import analyze_stock

    symbol = _symbol()
    if not symbol:
        _pause()
        return

    print("\n[*] Running BUSINESS + RISK RESEARCH")
    analyze_stock(symbol)
    _pause()


def show_menu() -> None:
    while True:
        print("\n" + "=" * 68)
        print("        NSE BUSINESS & RISK RESEARCH AGENT")
        print("=" * 68)
        print("\n  1. Opportunity Scanner — Build/Load Top 50")
        print("  2. Business + Risk Research — Enter Any Symbol")
        print("  0. Exit")
        print("=" * 68)

        choice = input("Choose: ").strip()
        try:
            if choice == "1":
                _opportunity_scan()
            elif choice == "2":
                _deep_stock()
            elif choice == "0":
                print("\nGoodbye.")
                return
            else:
                print("[!] Invalid option. Choose 1, 2 or 0.")
        except KeyboardInterrupt:
            print("\n[!] Operation cancelled. Returning to the main menu.")
        except Exception as exc:
            print(f"\n[!] Operation failed: {exc}")
            _pause()


if __name__ == "__main__":
    show_menu()
