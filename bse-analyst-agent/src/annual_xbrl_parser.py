from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
import re
import xml.etree.ElementTree as ET


TAG_ALIASES = {
    "revenue": (
        "revenuefromoperations",
        "revenue",
        "turnover",
    ),
    "pat_owner": (
        "profitlossattributabletoownersofparent",
        "profitlossattributabletoownersofparentcompany",
    ),
    "pat_total": (
        "profitlossforperiod",
        "profitloss",
    ),
    "ebit": (
        "operatingprofit",
        "profitfromoperations",
        "profitbeforefinancecostsandtax",
        "profitbeforeinterestandtax",
        "earningsbeforeinterestandtax",
    ),
    "pbt": (
        "profitbeforetax",
        "profitbeforetaxandexceptionalitems",
    ),
    "capex": (\n        "purchaseofpropertyplantandequipmentclassifiedasinvestingactivities",\n        "purchaseofpropertyplantandequipment",\n        "paymentsforpropertyplantandequipment",\n    ),\n    "cfo": (
        "cashflowsfromusedinoperatingactivities",
        "cashflowsfromusedinoperations",
        "cashflowsfromoperatingactivities",
    ),
    "debt": (
        "borrowings",
        "debt",
        "currentborrowings",
        "noncurrentborrowings",
    ),
    "cash": (
        "cashandcashequivalents",
        "cashandbankbalances",
        "cashandcashdeposits",
    ),
    "equity_owner": (
        "equityattributabletoownersofparent",
        "equityattributabletoownersoftheparent",
    ),
    "equity_total": ("equity",),
}


@dataclass(frozen=True)
class XBRLFact:
    tag: str
    context_ref: str | None
    value: float | str | None
    unit: str | None
    start: str | None
    end: str | None
    instant: str | None
    dimensions: tuple[str, ...] = ()


def _local(name: str) -> str:
    return name.rsplit("}", 1)[-1].lower()


def _number(value: str | None) -> float | str | None:
    if value is None:
        return None
    raw = value.strip().replace(",", "")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return raw


def _year_from_end(end: str) -> str:
    return f"FY{end[:4]}"


class AnnualXBRLParser:
    """Parse annual-report XBRL into auditable, normalized facts.

    Values are normalized to INR crore only when the XBRL unit is a monetary
    INR unit. The parser never treats PBT as EBIT and never selects a
    dimensioned fact over an undimensioned annual fact.
    """

    def parse(self, path: str | Path) -> list[XBRLFact]:
        root = ET.parse(path).getroot()
        contexts: dict[str, dict[str, Any]] = {}

        for element in root.iter():
            if _local(element.tag) != "context":
                continue
            context_id = element.attrib.get("id")
            if not context_id:
                continue

            item: dict[str, Any] = {
                "start": None,
                "end": None,
                "instant": None,
                "dimensions": [],
            }
            for child in element.iter():
                name = _local(child.tag)
                if name == "startdate":
                    item["start"] = child.text
                elif name == "enddate":
                    item["end"] = child.text
                elif name == "instant":
                    item["instant"] = child.text
                elif name in {"explicitmember", "typedmember"} and child.text:
                    item["dimensions"].append(child.text.strip())
            contexts[context_id] = item

        facts: list[XBRLFact] = []
        for element in root.iter():
            context_ref = element.attrib.get("contextRef")
            if not context_ref:
                continue
            context = contexts.get(context_ref, {})
            facts.append(
                XBRLFact(
                    tag=_local(element.tag),
                    context_ref=context_ref,
                    value=_number(element.text),
                    unit=element.attrib.get("unitRef"),
                    start=context.get("start"),
                    end=context.get("end"),
                    instant=context.get("instant"),
                    dimensions=tuple(context.get("dimensions", [])),
                )
            )
        return facts

    @staticmethod
    def is_annual(fact: XBRLFact) -> bool:
        if fact.dimensions or not fact.start or not fact.end:
            return False
        if not fact.end.endswith("-03-31"):
            return False
        try:
            days = (date.fromisoformat(fact.end) - date.fromisoformat(fact.start)).days
        except ValueError:
            return False
        return 300 <= days <= 370

    @classmethod
    def annual_facts(cls, facts: list[XBRLFact]) -> list[XBRLFact]:
        return [fact for fact in facts if cls.is_annual(fact)]

    @staticmethod
    def detect_basis(facts: list[XBRLFact]) -> str:
        values: set[str] = set()
        for fact in facts:
            if fact.tag != "natureofreportstandaloneconsolidated":
                continue
            value = str(fact.value or "").strip().lower()
            if "consolidated" in value:
                values.add("consolidated")
            elif "standalone" in value:
                values.add("standalone")
        if len(values) == 1:
            return next(iter(values))
        return "unknown"

    @staticmethod
    def _to_crore(value: float | str | None, unit: str | None) -> float | None:
        if not isinstance(value, (int, float)):
            return None
        unit_name = (unit or "").lower()
        if "inr" not in unit_name and "rupee" not in unit_name and unit_name:
            return float(value)
        return float(value) / 10_000_000.0

    @classmethod
    def _match(
        cls,
        facts: list[XBRLFact],
        aliases: tuple[str, ...],
        end: str,
    ) -> float | None:
        candidates = [
            fact for fact in facts
            if fact.end == end
            and isinstance(fact.value, (int, float))
            and any(alias in fact.tag for alias in aliases)
        ]
        if not candidates:
            return None

        def score(fact: XBRLFact) -> tuple[int, int]:
            exactness = max(
                (len(alias) for alias in aliases if fact.tag == alias),
                default=0,
            )
            return exactness, len(fact.tag)

        candidates.sort(key=score, reverse=True)
        selected = candidates[0]
        return cls._to_crore(selected.value, selected.unit)

    @classmethod
    def normalize(
        cls,
        facts: list[XBRLFact],
        source_file: str,
    ) -> list[dict[str, Any]]:
        annual = cls.annual_facts(facts)
        basis = cls.detect_basis(facts)
        ends = sorted({fact.end for fact in annual if fact.end})

        rows: list[dict[str, Any]] = []
        for end in ends:
            pat_owner = cls._match(annual, TAG_ALIASES["pat_owner"], end)
            pat_total = cls._match(annual, TAG_ALIASES["pat_total"], end)
            equity_owner = cls._match(annual, TAG_ALIASES["equity_owner"], end)
            equity_total = cls._match(annual, TAG_ALIASES["equity_total"], end)

            rows.append(
                {
                    "fiscal_year": _year_from_end(end),
                    "basis": basis,
                    "source_type": "annual_xbrl",
                    "source_file": source_file,
                    "revenue": cls._match(annual, TAG_ALIASES["revenue"], end),
                    "pat": pat_owner if pat_owner is not None else pat_total,
                    "pat_owner": pat_owner,
                    "ebit": cls._match(annual, TAG_ALIASES["ebit"], end),
                    "pbt": cls._match(annual, TAG_ALIASES["pbt"], end),
                    "cfo": cls._match(annual, TAG_ALIASES["cfo"], end),\n                    "capex": (abs(cls._match(annual, TAG_ALIASES["capex"], end)) if cls._match(annual, TAG_ALIASES["capex"], end) is not None else None),
                    "debt": cls._match(annual, TAG_ALIASES["debt"], end),
                    "cash": cls._match(annual, TAG_ALIASES["cash"], end),
                    "equity": equity_total if equity_total is not None else equity_owner,
                    "equity_owner": equity_owner,
                    "confidence": "unvalidated",
                }
            )
        return rows
