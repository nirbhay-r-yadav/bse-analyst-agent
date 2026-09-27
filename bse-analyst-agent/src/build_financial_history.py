from __future__ import annotations

import argparse
from pathlib import Path

from src.annual_report_downloader import AnnualReportDownloader, extract_archive
from src.annual_xbrl_parser import AnnualXBRLParser
from src.annual_report_pdf_normalizer import AnnualReportPDFNormalizer
from src.financial_history import FinancialHistoryRow, FinancialHistoryStore


def build(symbol: str, root: str = "data/annual_reports") -> Path:
    downloader = AnnualReportDownloader(root)
    records = downloader.discover(symbol)
    parser = AnnualXBRLParser()
    pdf_parser = AnnualReportPDFNormalizer()
    rows: list[FinancialHistoryRow] = []

    for record in records:
        artifact = downloader.download(record)
        files = extract_archive(artifact)
        for file_path in files:
            suffix = file_path.suffix.lower()
            try:
                if suffix in {".xml", ".xbrl"}:
                    facts = parser.parse(file_path)
                    normalized = parser.normalize(facts, str(file_path))
                elif suffix == ".pdf":
                    normalized = pdf_parser.normalize(file_path)
                else:
                    continue
            except Exception as exc:
                print(f"[WARN] Could not parse {file_path}: {exc}")
                continue

            for item in normalized:
                rows.append(FinancialHistoryRow(**item))

    store = FinancialHistoryStore()
    destination = store.save(symbol, rows)
    print(f"Saved normalized history: {destination}")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build historical financial-source data from NSE annual reports"
    )
    parser.add_argument("symbol")
    parser.add_argument("--root", default="data/annual_reports")
    args = parser.parse_args()
    build(args.symbol, args.root)
