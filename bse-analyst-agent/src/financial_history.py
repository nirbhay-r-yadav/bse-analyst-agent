from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable
import json


@dataclass
class FinancialHistoryRow:
    fiscal_year: str
    basis: str
    source_type: str
    source_file: str
    revenue: float | None = None
    pat: float | None = None
    pat_owner: float | None = None
    ebit: float | None = None
    pbt: float | None = None
    cfo: float | None = None
    capex: float | None = None
    debt: float | None = None
    cash: float | None = None
    equity: float | None = None
    equity_owner: float | None = None
    confidence: str = "unvalidated"


class FinancialHistoryStore:
    """Canonical 10-year history container.

    Source precedence:
      1. validated annual XBRL
      2. validated current-period NSE financial-results XBRL
      3. annual-report PDF extraction only after explicit validation

    The store never fabricates a missing year. A missing field remains None and
    is surfaced to the caller for validation.
    """

    REQUIRED_FIELDS = (
        "revenue", "pat", "ebit", "cfo", "capex", "debt", "cash", "equity"
    )

    def __init__(self, root: str | Path = "data/financial_history"):
        self.root = Path(root)

    @staticmethod
    def _rank(row: FinancialHistoryRow) -> tuple[int, int, int]:
        source_rank = {
            "annual_xbrl": 3,
            "nse_financial_xbrl": 2,
            "annual_report_pdf": 1,
        }.get(row.source_type, 0)
        completeness = sum(getattr(row, f) is not None for f in FinancialHistoryStore.REQUIRED_FIELDS)
        validation = {"validated": 2, "unvalidated": 1}.get(row.confidence, 0)
        return source_rank, validation, completeness

    def merge(self, rows: Iterable[FinancialHistoryRow]) -> list[FinancialHistoryRow]:
        selected: dict[tuple[str, str], FinancialHistoryRow] = {}
        for row in rows:
            key = (row.fiscal_year, row.basis)
            existing = selected.get(key)
            if existing is None or self._rank(row) > self._rank(existing):
                selected[key] = row

        return sorted(
            selected.values(),
            key=lambda r: (r.fiscal_year, r.basis),
        )

    def save(self, symbol: str, rows: Iterable[FinancialHistoryRow]) -> Path:
        merged = self.merge(rows)
        destination = self.root / symbol.upper() / "history.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "symbol": symbol.upper(),
            "target_history_years": 10,
            "rows": [asdict(row) for row in merged],
            "missing_years": self.missing_years(merged),
        }
        destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return destination

    @staticmethod
    def missing_years(rows: Iterable[FinancialHistoryRow]) -> list[str]:
        years = sorted(
            {
                int(row.fiscal_year.replace("FY", ""))
                for row in rows
                if row.fiscal_year.startswith("FY") and row.fiscal_year[2:].isdigit()
            }
        )
        if not years:
            return []

        end = max(years)
        expected = {f"FY{year}" for year in range(end - 9, end + 1)}
        actual = {row.fiscal_year for row in rows}
        return sorted(expected - actual)

    @staticmethod
    def validate_row(row: FinancialHistoryRow) -> list[str]:
        errors: list[str] = []
        if not row.fiscal_year.startswith("FY"):
            errors.append("invalid_fiscal_year")
        if row.basis not in {"consolidated", "standalone", "unknown"}:
            errors.append("invalid_basis")
        if row.source_type not in {
            "annual_xbrl",
            "nse_financial_xbrl",
            "annual_report_pdf",
        }:
            errors.append("invalid_source_type")
        if row.revenue is not None and row.revenue < 0:
            errors.append("negative_revenue")
        if row.capex is not None and row.capex < 0:
            errors.append("negative_capex")
        if row.debt is not None and row.debt < 0:
            errors.append("negative_debt")
        if row.pat_owner is not None and row.pat is not None and row.pat_owner > row.pat * 1.001 and row.pat >= 0:
            errors.append("owner_pat_exceeds_total_pat")
        return errors


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Inspect a normalized financial history")
    parser.add_argument("symbol")
    args = parser.parse_args()

    path = Path("data/financial_history") / args.symbol.upper() / "history.json"
    if not path.exists():
        raise SystemExit(f"History not found: {path}")
    print(path.read_text(encoding="utf-8"))
