"""Structured financial-data provider for deep-stock analysis.

Primary accounting source: NSE annual audited consolidated XBRL filings.
Annual-report PDFs remain qualitative evidence for governance, forensic and
management analysis. Screener is retained only as a legacy fallback helper.
"""

from __future__ import annotations

from datetime import datetime
import re
import xml.etree.ElementTree as ET
from typing import Any

import requests
from bs4 import BeautifulSoup

from .financial_tools import AnnualFinancials, CompanyFinancialHistory


class FinancialDataError(RuntimeError):
    """Raised when structured financial data is unavailable or unreliable."""


class StructuredFinancialProvider:
    NSE_RESULTS_URL = "https://www.nseindia.com/api/corporates-financial-results"
    NSE_RESULTS_PAGE = "https://www.nseindia.com/companies-listing/corporate-filings-financial-results"
    SCREENER_SEARCH_URL = "https://www.screener.in/api/company/search/"
    SCREENER_URLS = (
        "https://www.screener.in/company/{symbol}/consolidated/",
        "https://www.screener.in/company/{symbol}/",
    )
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    @staticmethod
    def _symbol(symbol: str) -> str:
        return symbol.upper().strip().removesuffix(".NS").removesuffix(".BO")

    def _warm_nse(self) -> None:
        try:
            self.session.get(self.NSE_RESULTS_PAGE, timeout=self.timeout)
        except requests.RequestException:
            pass

    def _nse_annual_rows(self, symbol: str) -> list[dict[str, Any]]:
        self._warm_nse()
        try:
            response = self.session.get(
                self.NSE_RESULTS_URL,
                params={"index": "equities", "period": "Annual", "symbol": symbol},
                headers={"Referer": self.NSE_RESULTS_PAGE},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise FinancialDataError(f"NSE annual financial-results request failed for {symbol}: {exc}") from exc
        rows = payload.get("data", []) if isinstance(payload, dict) else payload
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    @classmethod
    def _xbrl_url(cls, row: dict[str, Any]) -> str | None:
        preferred = ("xbrl", "xbrlFileName", "xbrlFile", "xbrl_file_name", "xbrlFileLink", "xbrl_file_link")
        for key in preferred:
            value = row.get(key)
            if isinstance(value, str) and value.startswith("http") and value.lower().endswith((".xml", ".xbrl")):
                return value
        for value in row.values():
            if isinstance(value, str) and "xbrl" in value.lower() and value.startswith("http"):
                return value
        return None

    @staticmethod
    def _is_audited_consolidated(row: dict[str, Any]) -> bool:
        text = " ".join(str(v).lower() for v in row.values() if isinstance(v, (str, int, float)))
        return "audited" in text and "consolidated" in text and "standalone" not in text and "non-consolidated" not in text

    def _nse_xbrl_rows(self, symbol: str) -> list[tuple[str, bytes]]:
        rows = self._nse_annual_rows(symbol)
        candidates: list[str] = []
        for row in rows:
            url = self._xbrl_url(row)
            if url and self._is_audited_consolidated(row):
                candidates.append(url)
        if not candidates:
            candidates = [url for row in rows if (url := self._xbrl_url(row))]

        records: list[tuple[str, bytes]] = []
        seen: set[str] = set()
        for url in candidates[:12]:
            if url in seen:
                continue
            seen.add(url)
            try:
                response = self.session.get(url, headers={"Referer": self.NSE_RESULTS_PAGE}, timeout=self.timeout)
                response.raise_for_status()
                if response.content:
                    records.append((url, response.content))
            except requests.RequestException:
                continue
        return records

    @staticmethod
    def _reliable_records(records: list[AnnualFinancials]) -> list[AnnualFinancials]:
        filtered = [r for r in records if re.fullmatch(r"FY20\d{2}", r.fiscal_year)]
        unique = {r.fiscal_year: r for r in filtered}
        return sorted(unique.values(), key=lambda r: int(r.fiscal_year[2:]))[-10:]

    @staticmethod
    def _nse_xbrl_value(facts: dict[str, list[tuple[dict[str, Any], float]]], names: tuple[str, ...], context_type: str, fiscal_year: str) -> float | None:
        for name in names:
            for context, value in facts.get(name, []):
                if context.get("type") == context_type and context.get("fiscal_year") == fiscal_year and not context.get("has_dimensions"):
                    return value
        return None

    @staticmethod
    def _xbrl_date(value: Any) -> datetime | None:
        """Parse XBRL dates defensively across NSE date representations."""
        if not value:
            return None
        text = str(value).strip()
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
        if not match:
            return None
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None

    def _parse_nse_xbrl(self, xml_content: bytes, symbol: str) -> AnnualFinancials:
        root = ET.fromstring(xml_content)
        contexts: dict[str, dict[str, Any]] = {}

        for context in root.iter():
            if context.tag.split("}")[-1].lower() != "context":
                continue
            context_id = context.attrib.get("id")
            if not context_id:
                continue

            start_date = None
            end_date = None
            has_dimensions = False
            for child in context.iter():
                local = child.tag.split("}")[-1].lower()
                if local == "startdate":
                    start_date = child.text
                elif local == "enddate":
                    end_date = child.text
                elif local == "explicitmember"::
                    has_dimensions = True

            end = self._xbrl_date(end_date)
            start = self._xbrl_date(start_date)
            if end is None:
                continue

            fiscal_year = None
            context_type = "instant"
            if start is not None:
                context_type = "duration"
                days = (end - start).days
                # Indian FY is normally 1 Apr -> 31 Mar. Allow small source-format
                # variations while rejecting quarterly/half-year contexts.
                if end.month == 3 and end.day == 31 and (start.month == 4 and start.day == 1 or 300 <= days <= 370):
                    fiscal_year = f"FY{end.year}"
            elif end.month == 3 and end.day == 31:
                fiscal_year = f"FY{end.year}"

            if fiscal_year:
                contexts[context_id] = {
                    "type": context_type,
                    "fiscal_year": fiscal_year,
                    "has_dimensions": has_dimensions,
                }

        facts: dict[str, list[tuple[dict[str, Any], float]]] = {}
        for element in root.iter():
            context_ref = element.attrib.get("contextRef")
            if not context_ref or context_ref not in contexts:
                continue
            text = (element.text or "").strip()
            if not text:
                continue
            try:
                value = float(text.replace(",", ""))
            except ValueError:
                continue
            facts.setdefault(element.tag.split("}")[-1], []).append((contexts[context_ref], value))

        fiscal_years = {c["fiscal_year"] for c in contexts.values()}
        if not fiscal_years:
            raise FinancialDataError(f"No annual fiscal-year context found in NSE XBRL for {symbol}")
        fiscal_year = max(fiscal_years)

        revenue = self._nse_xbrl_value(facts, ("RevenueFromOperations",), "duration", fiscal_year)
        pat = self._nse_xbrl_value(facts, ("ProfitOrLossAttributableToOwnersOfParent", "ProfitLossForPeriod"), "duration", fiscal_year)
        ebit = self._nse_xbrl_value(facts, ("SegmentProfitLossBeforeTaxAndFinanceCosts", "ProfitLossBeforeTaxAndFinanceCosts"), "duration", fiscal_year)
        interest = self._nse_xbrl_value(facts, ("FinanceCosts",), "duration", fiscal_year)
        equity = self._nse_xbrl_value(facts, ("Equity",), "instant", fiscal_year)
        debt_current = self._nse_xbrl_value(facts, ("BorrowingsCurrent",), "instant", fiscal_year)
        debt_noncurrent = self._nse_xbrl_value(facts, ("BorrowingsNoncurrent",), "instant", fiscal_year)
        cash = self._nse_xbrl_value(facts, ("CashAndCashEquivalents",), "instant", fiscal_year)
        cfo = self._nse_xbrl_value(facts, ("CashFlowsFromUsedInOperatingActivities",), "duration", fiscal_year)
        capex = self._nse_xbrl_value(facts, ("PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",), "duration", fiscal_year)

        if revenue is None or pat is None:
            raise FinancialDataError(f"Incomplete NSE XBRL financial data for {symbol} {fiscal_year}")
        total_debt = debt_current + debt_noncurrent if debt_current is not None and debt_noncurrent is not None else None

        return AnnualFinancials(
            fiscal_year=fiscal_year,
            revenue=revenue / 10000000,
            ebit=ebit / 10000000 if ebit is not None else None,
            pat=pat / 10000000,
            total_debt=total_debt / 10000000 if total_debt is not None else None,
            total_equity=equity / 10000000 if equity is not None else None,
            cash_equivalents=cash / 10000000 if cash is not None else None,
            cfo=cfo / 10000000 if cfo is not None else None,
            interest_expense=interest / 10000000 if interest is not None else None,
            capex=capex / 10000000 if capex is not None else None,
        )

    def _nse_history(self, symbol: str) -> CompanyFinancialHistory:
        records: list[AnnualFinancials] = []
        errors: list[str] = []
        for _, xml_content in self._nse_xbrl_rows(symbol):
            try:
                records.append(self._parse_nse_xbrl(xml_content, symbol))
            except (ET.ParseError, FinancialDataError) as exc:
                errors.append(str(exc))
        records = self._reliable_records(records)
        if not records:
            detail = f"; parser errors: {' | '.join(errors[:3])}" if errors else ""
            raise FinancialDataError(f"No reliable NSE XBRL annual financial history for {symbol}{detail}")
        if any(row.revenue <= 0 or row.pat == 0 for row in records):
            raise FinancialDataError(f"NSE XBRL financial data quality check failed for {symbol}")
        return CompanyFinancialHistory(years=records)

    def get_history(self, symbol: str) -> CompanyFinancialHistory:
        return self._nse_history(self._symbol(symbol))
