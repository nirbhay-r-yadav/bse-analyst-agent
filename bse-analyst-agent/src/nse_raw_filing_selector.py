from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


# Primary company-level financial statement concepts. These are deliberately
# conservative: segment/detail concepts must never qualify a filing by
# themselves.
ANNUAL_PRIMARY_TAGS = {
    "revenuefromoperations",
    "revenue",
    "turnover",
    "profitlossforperiod",
    "profitloss",
    "profitorlossattributabletoownersofparent",
    "profitlossattributabletoownersofparent",
    "profitlossattributabletoownersofparentcompany",
    "profitbeforetax",
    "profitbeforetaxandexceptionalitems",
    "profitbeforefinancecostsandtax",
    "operatingprofit",
    "profitfromoperations",
    "cashflowsfromusedinoperatingactivities",
    "cashflowsfromoperatingactivities",
    "cashflowsfromusedinoperations",
}

INSTANT_PRIMARY_TAGS = {
    "cashandcashequivalents",
    "cashandbankbalances",
    "cashandcashdeposits",
    "equity",
    "equityattributabletoownersofparent",
    "equityattributabletoownersoftheparent",
    "borrowings",
    "debt",
    "borrowingscurrent",
    "currentborrowings",
    "borrowingsnoncurrent",
    "noncurrentborrowings",
}


def _period(fact: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    context = fact.get("context") or {}
    return context.get("start_date"), context.get("end_date"), context.get("instant")


def _is_annual_undimensioned(fact: dict[str, Any], end: str) -> bool:
    start, fact_end, instant = _period(fact)
    if instant or fact_end != end or not start:
        return False
    if (fact.get("context") or {}).get("has_dimensions"):
        return False
    try:
        days = (date.fromisoformat(fact_end) - date.fromisoformat(start)).days
    except ValueError:
        return False
    return 300 <= days <= 370


def _is_instant_undimensioned(fact: dict[str, Any], end: str) -> bool:
    start, fact_end, instant = _period(fact)
    return bool(
        instant == end
        and not start
        and not fact_end
        and not (fact.get("context") or {}).get("has_dimensions")
    )


def _tag(fact: dict[str, Any]) -> str:
    return str(fact.get("tag") or "").lower()


def filing_score(payload: dict[str, Any]) -> tuple[int, int, int, int]:
    """Return a conservative quality score for primary financial filing data.

    The score only considers undimensioned company-level facts. Segment,
    expense-detail and other dimensional facts contribute zero.
    """
    fiscal_year = str(payload.get("fiscal_year") or "")
    if not fiscal_year.startswith("FY20"):
        return (0, 0, 0, 0)

    end = f"{fiscal_year[2:]}-03-31"
    facts = payload.get("facts") or []
    if not isinstance(facts, list):
        return (0, 0, 0, 0)

    annual_tags = {
        _tag(fact)
        for fact in facts
        if _is_annual_undimensioned(fact, end)
    }
    instant_tags = {
        _tag(fact)
        for fact in facts
        if _is_instant_undimensioned(fact, end)
    }

    annual_primary = len(annual_tags & ANNUAL_PRIMARY_TAGS)
    instant_primary = len(instant_tags & INSTANT_PRIMARY_TAGS)

    explicit_basis = any(
        _tag(fact) == "natureofreportstandaloneconsolidated"
        for fact in facts
    )

    # Revenue + profit are the minimum P&L identity we require. A balance
    # concept is required too, so segment-only filings cannot qualify.
    core_pnl = bool(
        annual_tags & {"revenuefromoperations", "revenue", "turnover"}
    ) and bool(
        annual_tags
        & {
            "profitlossforperiod",
            "profitloss",
            "profitorlossattributabletoownersofparent",
            "profitlossattributabletoownersofparent",
            "profitlossattributabletoownersofparentcompany",
            "profitbeforetax",
            "profitbeforefinancecostsandtax",
            "operatingprofit",
            "profitfromoperations",
        }
    )
    primary = core_pnl and instant_primary > 0

    # Score only primary evidence. The final component rewards filings that
    # explicitly declare the reporting basis.
    return (
        1 if primary else 0,
        annual_primary,
        instant_primary,
        1 if explicit_basis else 0,
    )


def rank_primary_filings(
    paths: list[str | Path],
    fiscal_year: str,
) -> list[Path]:
    """Return candidate primary financial filings for one fiscal year.

    Invalid/segment-only XBRL files are excluded before ranking. This is
    intentionally separate from normalization so bad source selection cannot
    be hidden by alias mappings.
    """
    candidates: list[tuple[tuple[int, int, int, int], Path]] = []

    for raw_path in paths:
        path = Path(raw_path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if str(payload.get("fiscal_year") or "") != fiscal_year:
            continue

        score = filing_score(payload)
        if score[0] == 1:
            candidates.append((score, path))

    candidates.sort(key=lambda item: (item[0], item[1].name), reverse=True)
    return [path for _, path in candidates]


def select_primary_filing(
    paths: list[str | Path],
    fiscal_year: str,
) -> Path:
    """Select the highest-quality primary financial filing or fail loudly."""
    ranked = rank_primary_filings(paths, fiscal_year)
    if not ranked:
        raise ValueError(
            f"{fiscal_year}: no suitable primary financial-statement XBRL filing found; "
            "segment/detail-only filings are rejected"
        )
    return ranked[0]
