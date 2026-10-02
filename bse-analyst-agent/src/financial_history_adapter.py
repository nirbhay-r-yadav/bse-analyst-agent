from __future__ import annotations

from typing import Iterable

from .financial_history import FinancialHistoryRow
from .financial_tools import AnnualFinancials, CompanyFinancialHistory


def to_company_history(
    rows: Iterable[FinancialHistoryRow],
    basis: str = "consolidated",
) -> CompanyFinancialHistory:
    """Convert validated normalized rows into the existing analysis contract.

    Rows with a different reporting basis or missing revenue/PAT are excluded.
    No interpolation or estimation is performed here.
    """
    selected = [
        row for row in rows
        if row.basis == basis
        and row.revenue is not None
        and row.pat is not None
    ]
    selected.sort(key=lambda row: int(row.fiscal_year[2:]))

    annuals = [
        AnnualFinancials(
            fiscal_year=row.fiscal_year,
            revenue=row.revenue,
            ebit=row.ebit,
            pat=row.pat_owner if row.pat_owner is not None else row.pat,
            total_debt=row.debt,
            total_equity=(
                row.equity_owner
                if row.equity_owner is not None
                else row.equity
            ),
            cash_equivalents=row.cash,
            cfo=row.cfo,\n            capex=row.capex,
        )
        for row in selected[-10:]
    ]

    if not annuals:
        raise ValueError(
            f"No usable {basis} history rows with both revenue and PAT"
        )

    return CompanyFinancialHistory(years=annuals)
