from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.annual_report_downloader import AnnualReportDownloader


def build_inventory(
    symbol: str,
    root: str = "data/annual_reports",
    min_year: int = 2017,
    max_year: int | None = None,
) -> Path:
    downloader = AnnualReportDownloader(root)
    inventory = downloader.inventory(symbol, min_year=min_year, max_year=max_year)
    destination = Path(root) / symbol.upper() / "inventory.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(inventory, indent=2), encoding="utf-8")

    print(f"Annual-report inventory: {symbol.upper()}")
    for item in inventory:
        records = item["records"]
        if not records:
            print(f'{item["fiscal_year"]}: MISSING')
            continue
        for record in records:
            print(
                f'{item["fiscal_year"]}: {record["file_type"].upper()} '
                f'{record["file_name"]} | {record.get("size") or "size n/a"}'
            )
    print(f"Saved: {destination}")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inventory NSE annual reports by fiscal year")
    parser.add_argument("symbol")
    parser.add_argument("--root", default="data/annual_reports")
    parser.add_argument("--min-year", type=int, default=2017)
    parser.add_argument("--max-year", type=int, default=None)
    args = parser.parse_args()
    build_inventory(args.symbol, args.root, args.min_year, args.max_year)
