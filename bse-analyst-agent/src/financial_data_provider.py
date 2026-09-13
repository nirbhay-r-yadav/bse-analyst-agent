"""Structured financial-data provider for deep-stock analysis."""
from __future__ import annotations

from datetime import datetime
import re
import xml.etree.ElementTree as ET
from typing import Any

import requests

from .financial_tools import AnnualFinancials, CompanyFinancialHistory


class FinancialDataError(RuntimeError):
    """Raised when structured financial data is unavailable or unreliable."""


class StructuredFinancialProvider:
    NSE_RESULTS_URL = "https://www.nseindia.com/api/corporates-financial-results"
    NSE_RESULTS_PAGE = "https://www.nseindia.com/companies-listing/corporate-filings-financial-results"
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
            response = self.session.get(self.NSE_RESULTS_URL, params={"index": "equities", "period": "Annual", "symbol": symbol}, headers={"Referer": self.NSE_RESULTS_PAGE}, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise FinancialDataError(f"NSE annual financial-results request failed for {symbol}: {exc}") from exc
        rows = payload.get("data", []) if isinstance(payload, dict) else payload
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    @staticmethod
    def _xbrl_url(row: dict[str, Any]) -> str | None:
        for key in ("xbrl", "xbrlFileName", "xbrlFile", "xbrl_file_name", "xbrlFileLink", "xbrl_file_link"):
            value = row.get(key)
            if isinstance(value, str) and value.startswith("http") and value.lower().endswith((".xml", ".xbrl")):
                return value
        for value in row.values():
            if isinstance(value, str) and "xbrl" in value.lower() and value.startswith("http"):
                return value
        return None

    @staticmethod
    def _nse_row_fiscal_year(row: dict[str, Any]) -> str | None:
        for key in ("financialYear", "toDate"):
            value = row.get(key)
            if isinstance(value, str):
                match = re.search(r"31-Mar-(\d{4})", value, re.IGNORECASE)
                if match:
                    return f"FY{match.group(1)}"
        return None

    @staticmethod
    def _nse_row_priority(row: dict[str, Any]) -> int:
        score = 0
        if str(row.get("period", "")).strip().lower() == "annual":
            score += 100
        if str(row.get("relatingTo", "")).strip().lower() == "annual":
            score += 80
        if str(row.get("cumulative", "")).strip().lower() == "cumulative":
            score += 40
        if str(row.get("audited", "")).strip().lower() == "audited":
            score += 30
        if str(row.get("consolidated", "")).strip().lower() == "consolidated":
            score += 30
        return score

    def _nse_xbrl_records(self, symbol: str) -> list[tuple[str, bytes, str | None]]:
        rows = self._nse_annual_rows(symbol)
        best_by_year: dict[str, tuple[int, str, str | None]] = {}
        fallback: list[tuple[int, str, str | None]] = []
        for row in rows:
            url = self._xbrl_url(row)
            if not url:
                continue
            fiscal_year = self._nse_row_fiscal_year(row)
            candidate = (self._nse_row_priority(row), url, fiscal_year)
            if fiscal_year:
                current = best_by_year.get(fiscal_year)
                if current is None or candidate[0] > current[0]:
                    best_by_year[fiscal_year] = candidate
            else:
                fallback.append(candidate)

        candidates = sorted(best_by_year.values(), key=lambda item: item[2] or "", reverse=True)
        if len(candidates) < 10:
            candidates.extend(sorted(fallback, key=lambda item: item[0], reverse=True)[: 10 - len(candidates)])

        records = []
        seen: set[str] = set()
        for _, url, fiscal_year in candidates[:12]:
            if url in seen:
                continue
            seen.add(url)
            try:
                response = self.session.get(url, headers={"Referer": self.NSE_RESULTS_PAGE}, timeout=self.timeout)
                response.raise_for_status()
                if response.content:
                    records.append((url, response.content, fiscal_year))
            except requests.RequestException:
                continue
        return records

    def _nse_xbrl_rows(self, symbol: str) -> list[tuple[str, bytes]]:
        return [(url, xml_content) for url, xml_content, _ in self._nse_xbrl_records(symbol)]

    @staticmethod
    def _reliable_records(records: list[AnnualFinancials]) -> list[AnnualFinancials]:
        filtered = [r for r in records if re.fullmatch(r"FY20\d{2}", r.fiscal_year)]
        unique = {r.fiscal_year: r for r in filtered}
        return sorted(unique.values(), key=lambda r: int(r.fiscal_year[2:]))[-10:]

    @staticmethod
    def _nse_xbrl_value(facts: dict[str, list[tuple[dict[str, Any], float]]], names: tuple[str, ...], context_type: str, fiscal_year: str) -> float | None:
        normalized_names = tuple(name.lower() for name in names)
        matches: list[tuple[dict[str, Any], float]] = []
        for name in normalized_names:
            for context, value in facts.get(name, []):
                if context.get("type") == context_type and context.get("fiscal_year") == fiscal_year and not context.get("has_dimensions"):
                    matches.append((context, value))
        if matches:
            annual = [item for item in matches if item[0].get("annual_context")]
            if annual:
                return annual[0][1]
            return matches[0][1]
        for name in normalized_names:
            for context, value in facts.get(name, []):
                if context.get("type") == context_type and context.get("fiscal_year") == fiscal_year:
                    return value
        return None

    @staticmethod
    def _xbrl_date(value: Any) -> datetime | None:
        if not value:
            return None
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(value).strip())
        if not match:
            return None
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None

    @staticmethod
    def _local_name(tag: Any) -> str:
        text = str(tag)
        return text.rsplit("}", 1)[-1].rsplit(":", 1)[-1].lower()

    def _parse_nse_xbrl(self, xml_content: bytes, symbol: str, fiscal_year_override: str | None = None) -> AnnualFinancials:
        root = ET.fromstring(xml_content)
        contexts: dict[str, dict[str, Any]] = {}
        for element in root.iter():
            if self._local_name(element.tag) != "context":
                continue
            context_id = element.attrib.get("id")
            if not context_id:
                continue
            start_date = end_date = instant_date = None
            has_dimensions = False
            for child in element.iter():
                local = self._local_name(child.tag)
                if local == "startdate":
                    start_date = child.text
                elif local == "enddate":
                    end_date = child.text
                elif local == "instant":
                    instant_date = child.text
                elif local in {"explicitmember", "typedmember"}:
                    has_dimensions = True

            start = self._xbrl_date(start_date)
            end = self._xbrl_date(end_date)
            instant = self._xbrl_date(instant_date)
            context_lower = context_id.lower()
            legacy_annual_context = context_lower.startswith("four") and context_lower.endswith("d")

            fiscal_year = fiscal_year_override if fiscal_year_override and legacy_annual_context else None
            context_type = "duration" if legacy_annual_context else "instant"
            annual_context = legacy_annual_context

            if start is not None:
                context_type = "duration"
                days = (end - start).days if end is not None else 0
                if end is not None and end.month == 3 and end.day == 31 and 300 <= days <= 370:
                    fiscal_year = f"FY{end.year}"
            elif end is not None and end.month == 3 and end.day == 31:
                fiscal_year = f"FY{end.year}"
            elif instant is not None:
                fiscal_year = fiscal_year_override if fiscal_year_override else (f"FY{instant.year}" if instant.month == 3 and instant.day == 31 else None)

            if legacy_annual_context and fiscal_year_override:
                fiscal_year = fiscal_year_override
                context_type = "duration"
                annual_context = True
            elif legacy_annual_context and fiscal_year is not None:
                context_type = "duration"
                annual_context = True

            if fiscal_year:
                contexts[context_id] = {"type": context_type, "fiscal_year": fiscal_year, "has_dimensions": has_dimensions, "annual_context": annual_context}

        if not any(c.get("fiscal_year") for c in contexts.values()):
            raw = xml_content.decode("utf-8", errors="ignore")
            context_pattern = re.compile(r"<(?P<tag>(?:[A-Za-z0-9_.-]+:)?context)\b[^>]*\bid=[\"'](?P<id>[^\"']+)[\"'][^>]*>(?P<body>.*?)</(?:[A-Za-z0-9_.-]+:)?context\s*>", re.IGNORECASE | re.DOTALL)
            date_pattern = re.compile(r"<(?:[A-Za-z0-9_.-]+:)?(?P<name>startDate|endDate|instant)\b[^>]*>\s*(?P<value>[^<]+)\s*</(?:[A-Za-z0-9_.-]+:)?(?P=name)>", re.IGNORECASE)
            for match in context_pattern.finditer(raw):
                context_id = match.group("id")
                body = match.group("body")
                dates = {m.group("name").lower(): m.group("value") for m in date_pattern.finditer(body)}
                end = self._xbrl_date(dates.get("enddate"))
                start = self._xbrl_date(dates.get("startdate"))
                instant = self._xbrl_date(dates.get("instant"))
                context_lower = context_id.lower()
                legacy_annual_context = context_lower.startswith("four") and context_lower.endswith("d")
                fiscal_year = fiscal_year_override if fiscal_year_override and legacy_annual_context else None
                context_type = "duration" if legacy_annual_context else "instant"
                annual_context = legacy_annual_context
                if start is not None:
                    context_type = "duration"
                    days = (end - start).days if end is not None else 0
                    if end is not None and end.month == 3 and end.day == 31 and 300 <= days <= 370:
                        fiscal_year = f"FY{end.year}"
                elif end is not None and end.month == 3 and end.day == 31:
                    fiscal_year = f"FY{end.year}"
                elif instant is not None:
                    fiscal_year = fiscal_year_override if fiscal_year_override else (f"FY{instant.year}" if instant.month == 3 and instant.day == 31 else None)
                if legacy_annual_context and fiscal_year_override:
                    fiscal_year = fiscal_year_override
                    context_type = "duration"
                    annual_context = True
                elif legacy_annual_context and fiscal_year is not None:
                    context_type = "duration"
                    annual_context = True
                if fiscal_year:
                    contexts[context_id] = {"type": context_type, "fiscal_year": fiscal_year, "has_dimensions": bool(re.search(r"explicitMember|typedMember", body, re.IGNORECASE)), "annual_context": annual_context}

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
            facts.setdefault(self._local_name(element.tag), []).append((contexts[context_ref], value))

        fiscal_years = {c["fiscal_year"] for c in contexts.values()}
        if not fiscal_years:
            raise FinancialDataError(f"No annual fiscal-year context found in NSE XBRL for {symbol}")
        fiscal_year = fiscal_year_override or max(fiscal_years)
        revenue = self._nse_xbrl_value(facts, ("RevenueFromOperations",), "duration", fiscal_year)
        pat = self._nse_xbrl_value(facts, ("ProfitOrLossAttributableToOwnersOfParent", "ProfitLossAttributableToOwnersOfParent", "ProfitLossForPeriod"), "duration", fiscal_year)
        ebit = self._nse_xbrl_value(facts, ("SegmentProfitLossBeforeTaxAndFinanceCosts", "ProfitLossBeforeTaxAndFinanceCosts"), "duration", fiscal_year)
        interest = self._nse_xbrl_value(facts, ("FinanceCosts",), "duration", fiscal_year)
        equity = self._nse_xbrl_value(facts, ("Equity",), "instant", fiscal_year)
        debt_current = self._nse_xbrl_value(facts, ("BorrowingsCurrent",), "instant", fiscal_year)
        debt_noncurrent = self._nse_xbrl_value(facts, ("BorrowingsNoncurrent",), "instant", fiscal_year)
        cash = self._nse_xbrl_value(facts, ("CashAndCashEquivalents",), "instant", fiscal_year)
        cfo = self._nse_xbrl_value(facts, ("CashFlowsFromUsedInOperatingActivities", "CashFlowsFromUsedInOperations"), "duration", fiscal_year)
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
        for _, xml_content, fiscal_year in self._nse_xbrl_records(symbol):
            try:
                records.append(self._parse_nse_xbrl(xml_content, symbol, fiscal_year_override=fiscal_year))
            except (ET.ParseError, FinancialDataError, ValueError):
                continue
        reliable = self._reliable_records(records)
        if not reliable:
            raise FinancialDataError(f"Financial data quality check failed for {symbol}")
        return CompanyFinancialHistory(symbol=symbol, years=reliable)

    def get_history(self, symbol: str) -> CompanyFinancialHistory:
        symbol = self._symbol(symbol)
        try:
            return self._nse_history(symbol)
        except FinancialDataError:
            raise
