from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from .financial_history import FinancialHistoryRow, FinancialHistoryStore


REVENUE_TAGS = ("revenuefromoperations", "revenue", "turnover")
PAT_OWNER_TAGS = (
    "profitorlossattributabletoownersofparent",
    "profitlossattributabletoownersofparent",
    "profitlossattributabletoownersofparentcompany",
)
PAT_TOTAL_TAGS = ("profitlossforperiod", "profitloss")
EBIT_TAGS = (
    "operatingprofit",
    "profitfromoperations",
    "profitbeforefinancecostsandtax",
    "profitbeforeinterestandtax",
    "earningsbeforeinterestandtax",
)
PBT_TAGS = ("profitbeforetax", "profitbeforetaxandexceptionalitems")
CFO_TAGS = (
    "cashflowsfromusedinoperatingactivities",
    "cashflowsfromoperatingactivities",
    "cashflowsfromusedinoperations",
)
CAPEX_TAGS = (
    "purchaseofpropertyplantandequipmentclassifiedasinvestingactivities",
    "purchaseofpropertyplantandequipment",
    "paymentsforpropertyplantandequipment",
)
CASH_TAGS = ("cashandcashequivalents", "cashandbankbalances", "cashandcashdeposits")
EQUITY_OWNER_TAGS = (
    "equityattributabletoownersofparent",
    "equityattributabletoownersoftheparent",
)
EQUITY_TOTAL_TAGS = ("equity",)
DEBT_TOTAL_TAGS = ("borrowings", "debt")
DEBT_CURRENT_TAGS = ("borrowingscurrent", "currentborrowings")
DEBT_NONCURRENT_TAGS = ("borrowingsnoncurrent", "noncurrentborrowings")


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _crore(fact: dict[str, Any]) -> float | None:
    value = _num(fact.get("value"))
    if value is None:
        return None
    unit = str(fact.get("unit") or "").lower()
    if "inr" in unit or "rupee" in unit:
        return value / 10_000_000.0
    return value


def _period(fact: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    ctx = fact.get("context") or {}
    return ctx.get("start_date"), ctx.get("end_date"), ctx.get("instant")


def _annual(fact: dict[str, Any]) -> bool:
    start, end, instant = _period(fact)
    if instant or not start or not end or not end.endswith("-03-31"):
        return False
    try:
        days = (date.fromisoformat(end) - date.fromisoformat(start)).days
    except ValueError:
        return False
    return 300 <= days <= 370 and not (fact.get("context") or {}).get("has_dimensions")


def _instant(fact: dict[str, Any], end: str) -> bool:
    start, fact_end, instant = _period(fact)
    return bool(instant == end and not start and not fact_end and not (fact.get("context") or {}).get("has_dimensions"))


def _matches(tag: str, aliases: tuple[str, ...]) -> bool:
    tag = tag.lower()
    return any(tag == alias for alias in aliases)


def _pick(facts: list[dict[str, Any]], aliases: tuple[str, ...], end: str) -> float | None:
    candidates = [
        f for f in facts
        if _matches(str(f.get("tag", "")), aliases)
        and _period(f)[1] == end
        and _annual(f)
        and _crore(f) is not None
    ]
    if not candidates:
        return None
    for alias in aliases:
        for fact in candidates:
            if str(fact.get("tag", "")).lower() == alias:
                return _crore(fact)
    return None


def _pick_instant(facts: list[dict[str, Any]], aliases: tuple[str, ...], end: str) -> float | None:
    for alias in aliases:
        candidates = [
            f for f in facts
            if str(f.get("tag", "")).lower() == alias
            and _instant(f, end)
            and _crore(f) is not None
        ]
        if candidates:
            return _crore(candidates[0])
    return None


def _basis(facts: list[dict[str, Any]], source_file: str | Path | None = None) -> str:
    """Determine reporting basis from explicit or deterministic filing evidence.

    NSE Integrated Filing JSON can omit the explicit nature-of-report tag.
    We therefore accept only evidence that identifies consolidated reporting:
    NCI facts, or owner-of-parent facts that are specific to consolidated
    presentation. We never infer basis from the filename alone.
    """
    values = set()
    tags = {str(fact.get("tag", "")).lower() for fact in facts}

    for fact in facts:
        if str(fact.get("tag", "")).lower() != "natureofreportstandaloneconsolidated":
            continue
        value = str(fact.get("value") or "").strip().lower()
        if "consolidated" in value:
            values.add("consolidated")
        elif "standalone" in value:
            values.add("standalone")

    if len(values) == 1:
        return next(iter(values))
    if len(values) > 1:
        raise ValueError(f"{source_file or 'raw NSE facts'}: conflicting reporting basis facts: {sorted(values)}")

    nci_tags = {
        "profitorlossattributabletononcontrollinginterests",
        "noncontrollinginterests",
    }
    if tags & nci_tags:
        return "consolidated"

    # Older NSE files may omit both the explicit basis tag and NCI facts.
    # These owner-of-parent concepts are specific to consolidated reporting
    # and provide deterministic evidence without relying on the filename.
    consolidated_only_tags = {
        "profitorlossattributabletoownersofparent",
        "profitlossattributabletoownersofparent",
        "profitlossattributabletoownersofparentcompany",
        "equityattributabletoownersofparent",
        "equityattributabletoownersoftheparent",
    }
    if tags & consolidated_only_tags:
        return "consolidated"

    hint_tags = sorted(
        tag for tag in tags
        if any(token in tag for token in ("natureofreport", "consolidated", "standalone", "noncontrolling", "ownersofparent"))
    )
    raise ValueError(
        f"{source_file or 'raw NSE facts'}: unable to determine reporting basis; "
        f"no explicit basis or consolidated-only evidence found. "
        f"basis-related tags={hint_tags}"
    )


def _debt(facts: list[dict[str, Any]], end: str) -> float | None:
    total = _pick_instant(facts, DEBT_TOTAL_TAGS, end)
    if total is not None:
        return total
    current = _pick_instant(facts, DEBT_CURRENT_TAGS, end)
    noncurrent = _pick_instant(facts, DEBT_NONCURRENT_TAGS, end)
    if current is None and noncurrent is None:
        return None
    return (current or 0.0) + (noncurrent or 0.0)


def normalize_raw_file(path: str | Path) -> list[FinancialHistoryRow]:
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    facts = payload.get("facts", [])
    if not isinstance(facts, list):
        raise ValueError(f"Invalid facts payload: {path}")

    fiscal_year = str(payload.get("fiscal_year") or "")
    if not re.fullmatch(r"FY20\d{2}", fiscal_year):
        match = re.search(r"FY(20\d{2})", path.name)
        fiscal_year = f"FY{match.group(1)}" if match else ""
    if not fiscal_year:
        raise ValueError(f"Unable to determine fiscal year: {path}")

    basis = _basis(facts, path)
    year = fiscal_year[2:]
    end = f"{year}-03-31"

    revenue = _pick(facts, REVENUE_TAGS, end)
    pat_owner = _pick(facts, PAT_OWNER_TAGS, end)
    pat_total = _pick(facts, PAT_TOTAL_TAGS, end)
    capex = _pick(facts, CAPEX_TAGS, end)
    equity_total = _pick_instant(facts, EQUITY_TOTAL_TAGS, end)
    row = FinancialHistoryRow(
        fiscal_year=fiscal_year,
        basis=basis,
        source_type="nse_financial_xbrl",
        source_file=str(path),
        revenue=revenue,
        pat=pat_owner if pat_owner is not None else pat_total,
        pat_owner=pat_owner,
        ebit=_pick(facts, EBIT_TAGS, end),
        pbt=_pick(facts, PBT_TAGS, end),
        cfo=_pick(facts, CFO_TAGS, end),
        capex=abs(capex) if capex is not None else None,
        debt=_debt(facts, end),
        cash=_pick_instant(facts, CASH_TAGS, end),
        equity=equity_total if equity_total is not None else _pick_instant(facts, EQUITY_OWNER_TAGS, end),
        equity_owner=_pick_instant(facts, EQUITY_OWNER_TAGS, end),
        confidence="unvalidated",
    )
    errors = FinancialHistoryStore.validate_row(row)
    missing = [field for field in FinancialHistoryStore.REQUIRED_FIELDS if getattr(row, field) is None]
    if errors:
        raise ValueError(f"{path}: invalid normalized row: {errors}")
    if missing:
        raise ValueError(f"{path}: missing required fields: {missing}")
    row.confidence = "validated"
    return [row]


def build_from_raw(
    symbol: str,
    raw_root: str | Path = "data/financial_raw",
    history_root: str | Path = "data/financial_history",
) -> Path:
    symbol = symbol.upper().strip()
    directory = Path(raw_root) / symbol
    files = sorted(directory.glob("FY*.json"))
    if not files:
        raise FileNotFoundError(f"No FY*.json raw financial files found: {directory}")

    rows: list[FinancialHistoryRow] = []
    for path in files:
        rows.extend(normalize_raw_file(path))

    return FinancialHistoryStore(history_root).save(symbol, rows)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build normalized financial history from existing NSE raw JSON")
    parser.add_argument("symbol")
    args = parser.parse_args()

    destination = build_from_raw(args.symbol)
    print(destination)
