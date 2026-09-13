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
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip().lower()

    @classmethod
    def _row_value(cls, row: dict[str, Any], *names: str) -> Any:
        wanted = {name.lower() for name in names}
        for key, value in row.items():
            if key.lower() in wanted:
                return value
        return None

    @classmethod
    def _contains_value(cls, row: dict[str, Any], *values: str) -> bool:
        wanted = {value.lower() for value in values}
        return any(cls._text(v) in wanted for v in row.values() if isinstance(v, (str, int, float)))

    @classmethod
    def _xbrl_url(cls, row: dict[str, Any]) -> str | None:
        """Find the XBRL URL even if NSE changes the response field name."""
        preferred = (
            "xbrl",
            "xbrlFileName",
            "xbrlFile",
            "xbrl_file_name",
            "xbrlFileLink",
            "xbrl_file_link",
        )
        for key in preferred:
            value = row.get(key)
            if isinstance(value, str) and value.startswith("http") and value.lower().endswith((".xml", ".xbrl")):
                return value
        for value in row.values():
            if isinstance(value, str) and "xbrl" in value.lower() and value.startswith("http"):
                return value
        return None

    @classmethod
    def _is_audited_consolidated(cls, row: dict[str, Any]) -> bool:
        values = [cls._text(v) for v in row.values() if isinstance(v, (str, int, float))]
        text = " ".join(values)
        audited = "audited" in text
        consolidated = "consolidated" in text
        standalone = "standalone" in text or "non-consolidated" in text
        return audited and consolidated and not standalone

    def _nse_xbrl_rows(self, symbol: str) -> list[tuple[str, bytes]]:
        rows = self._nse_annual_rows(symbol)
        candidates: list[tuple[str, str]] = []
        for row in rows:
            url = self._xbrl_url(row)
            if not url:
                continue
            if self._is_audited_consolidated(row):
                candidates.append((url, self._row_value(row, "period", "fromDate", "toDate") or ""))

        if not candidates:
            # Some NSE payload versions omit the audited/consolidated labels.
            for row in rows:
                url = self._xbrl_url(row)
                if url:
                    candidates.append((url, self._row_value(row, "period", "fromDate", "toDate") or ""))

        unique: list[tuple[str, str]] = []
        seen: set[str] = set()
        for item in candidates:
            if item[0] not in seen:
                seen.add(item[0])
                unique.append(item)

        records: list[tuple[str, bytes]] = []
        for url, label in unique[:12]:
            try:
                response = self.session.get(url, headers={"Referer": self.NSE_RESULTS_PAGE}, timeout=self.timeout)
                response.raise_for_status()
                if response.content:
                    records.append((label, response.content))
            except requests.RequestException:
                continue
        return records

    @staticmethod
    def _reliable_records(records: list[AnnualFinancials]) -> list[AnnualFinancials]:
        filtered = [r for r in records if re.fullmatch(r"FY20\d{2}", r.fiscal_year)]
        unique = {r.fiscal_year: r for r in filtered}
        return sorted(unique.values(), key=lambda r: int(r.fiscal_year[2:]))[-10:]

    @staticmethod
    def _nse_xbrl_value(
        facts: dict[str, list[tuple[dict[str, Any], float]]],
        names: tuple[str, ...],
        context_type: str,
        fiscal_year: str,
    ) -> float | None:
        for name in names:
            candidates = []
            for context, value in facts.get(name, []):
                if context.get("type") != context_type:
                    continue
                if context.get("fiscal_year") != fiscal_year:
                    continue
                if context.get("has_dimensions"):
                    continue
                candidates.append(value)
            if candidates:
                return candidates[0]
        return None

    def _parse_nse_xbrl(self, xml_content: bytes, symbol: str) -> AnnualFinancials:
        root = ET.fromstring(xml_content)
        contexts: dict[str, dict[str, Any]] = {}

        for context in root.iter():
            if context.tag.split("}")[-1] != "context":
                continue
            context_id = context.attrib.get("id")
            if not context_id:
                continue
            start_date = None
            end_date = None
            has_dimensions = False
            for child in context.iter():
                local = child.tag.split("}")[-1]
                if local == "startDate":
                    start_date = child.text
                elif local == "endDate":
                    end_date = child.text
                elif local == "explicitMember":
                    has_dimensions = True
            if not end_date:
                continue

            fiscal_year = None
            context_type = "instant"
            try:
                end = datetime.fromisoformat(end_date)
                if start_date:
                    context_type = "duration"
                    start = datetime.fromisoformat(start_date)
                    if start.month == 4 and start.day == 1 and end.month == 3 and end.day == 31:
                        fiscal_year = f"FY{end.year}"
                elif end.month == 3 and end.day == 31:
                    fiscal_year = f"FY{end.year}"
            except ValueError:
                continue

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
            local_name = element.tag.split("}")[-1]
            facts.setdefault(local_name, []).append((contexts[context_ref], value))

        fiscal_years = {c["fiscal_year"] for c in contexts.values() if c.get("fiscal_year")}
        if not fiscal_years:
            raise FinancialDataError(f"No annual fiscal-year context found in NSE XBRL for {symbol}")
        fiscal_year = max(fiscal_years)

        revenue = self._nse_xbrl_value(facts, ("RevenueFromOperations",), "duration", fiscal_year)
        pat = self._nse_xbrl_value(
            facts,
            ("ProfitOrLossAttributableToOwnersOfParent", "ProfitLossForPeriod"),
            "duration",
            fiscal_year,
        )
        ebit = self._nse_xbrl_value(
            facts,
            ("SegmentProfitLossBeforeTaxAndFinanceCosts", "ProfitLossBeforeTaxAndFinanceCosts"),
            "duration",
            fiscal_year,
        )
        interest = self._nse_xbrl_value(facts, ("FinanceCosts",), "duration", fiscal_year)
        equity = self._nse_xbrl_value(facts, ("Equity",), "instant", fiscal_year)
        debt_current = self._nse_xbrl_value(facts, ("BorrowingsCurrent",), "instant", fiscal_year)
        debt_noncurrent = self._nse_xbrl_value(facts, ("BorrowingsNoncurrent",), "instant", fiscal_year)
        cash = self._nse_xbrl_value(facts, ("CashAndCashEquivalents",), "instant", fiscal_year)
        cfo = self._nse_xbrl_value(facts, ("CashFlowsFromUsedInOperatingActivities",), "duration", fiscal_year)
        capex = self._nse_xbrl_value(
            facts,
            ("PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",),
            "duration",
            fiscal_year,
        )

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
        downloaded = self._nse_xbrl_rows(symbol)
        records: list[AnnualFinancials] = []
        errors: list[str] = []
        for _, xml_content in downloaded:
            try:
                records.append(self._parse_nse_xbrl(xml_content, symbol))
            except (ET.ParseError, FinancialDataError) as exc:
                errors.append(str(exc))

        records = self._reliable_records(records)
        if not records:
            detail = f"; parser errors: {' | '.join(errors[:3])}" if errors else ""
            raise FinancialDataError(f"No reliable NSE XBRL annual financial history for {symbol}{detail}")

        if sum(1 for r in records if r.revenue <= 0 or r.pat == 0) > 0:
            raise FinancialDataError(f"NSE XBRL financial data quality check failed for {symbol}")
        return CompanyFinancialHistory(years=records)

    # Legacy Screener helpers retained for compatibility with older callers.
    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None:
            return None
        text = str(value).strip().replace("₹", "").replace(",", "")
        if text in {"", "-", "—", "NA", "N/A"}:
            return None
        negative = text.startswith("(") and text.endswith(")")
        text = text.strip("()")
        text = re.sub(r"[^0-9.+-]", "", text)
        try:
            number = float(text)
        except ValueError:
            return None
        return -number if negative else number

    def get_history(self, symbol: str) -> CompanyFinancialHistory:
        clean_symbol = self._symbol(symbol)
        return self._nse_history(clean_symbol)
