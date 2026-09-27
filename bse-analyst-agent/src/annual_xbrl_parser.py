from __future__ import annotations

from dataclasses import dataclass
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
    "pat": (
        "profitlossattributabletoownersofparent",
        "profitlossattributabletoownersofparentcompany",
        "profitlossforperiod",
        "profitloss",
    ),
    "ebit": (
        "profitbeforetax",
        "profitbeforetaxandexceptionalitems",
        "operatingprofit",
    ),
    "cfo": (
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
    "equity": (
        "equityattributabletoownersofparent",
        "equityattributabletoownersoftheparent",
        "equity",
    ),
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


class AnnualXBRLParser:
    """Read annual-report XBRL without hard-coding one taxonomy namespace."""

    def parse(self, path: str | Path) -> list[XBRLFact]:
        root = ET.parse(path).getroot()
        contexts: dict[str, dict[str, Any]] = {}

        for element in root.iter():
            if _local(element.tag) != "context":
                continue
            context_id = element.attrib.get("id")
            if not context_id:
                continue
            item: dict[str, Any] = {"start": None, "end": None, "instant": None, "dimensions": []}
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
            if "contextRef" not in element.attrib:
                continue
            context_ref = element.attrib.get("contextRef")
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
    def annual_facts(facts: list[XBRLFact]) -> list[XBRLFact]:
        result = []
        for fact in facts:
            if fact.dimensions or not fact.start or not fact.end:
                continue
            if not fact.end.endswith("-03-31"):
                continue
            try:
                from datetime import date
                days = (date.fromisoformat(fact.end) - date.fromisoformat(fact.start)).days
            except ValueError:
                continue
            if 300 <= days <= 370:
                result.append(fact)
        return result

    @staticmethod
    def _match(facts: list[XBRLFact], aliases: tuple[str, ...], end: str) -> float | None:
        candidates = [
            f for f in facts
            if f.end == end and isinstance(f.value, (int, float))
            and any(alias in f.tag for alias in aliases)
        ]
        if not candidates:
            return None
        # Prefer the most exact alias and the largest populated context only
        # after filtering to undimensioned annual facts.
        candidates.sort(
            key=lambda f: max((len(alias) for alias in aliases if alias in f.tag), default=0),
            reverse=True,
        )
        return float(candidates[0].value)

    def normalize(self, facts: list[XBRLFact], source_file: str) -> list[dict[str, Any]]:
        annual = self.annual_facts(facts)
        ends = sorted({f.end for f in annual if f.end})
        rows: list[dict[str, Any]] = []
        for end in ends:
            fiscal_year = f"FY{end[:4]}"
            row = {
                "fiscal_year": fiscal_year,
                "basis": "unknown",
                "source_type": "annual_xbrl",
                "source_file": source_file,
                "revenue": self._match(annual, TAG_ALIASES["revenue"], end),
                "pat": self._match(annual, TAG_ALIASES["pat"], end),
                "ebit": self._match(annual, TAG_ALIASES["ebit"], end),
                "cfo": self._match(annual, TAG_ALIASES["cfo"], end),
                "debt": self._match(annual, TAG_ALIASES["debt"], end),
                "cash": self._match(annual, TAG_ALIASES["cash"], end),
                "equity": self._match(annual, TAG_ALIASES["equity"], end),
                "confidence": "unvalidated",
            }
            rows.append(row)
        return rows
