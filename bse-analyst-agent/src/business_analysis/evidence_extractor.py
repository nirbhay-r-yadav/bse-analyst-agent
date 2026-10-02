from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import pymupdf

from .models import Evidence, ManagementPromise


SECTION_KEYWORDS={
    "business_model":("business overview","our business","business model","products","services","segments"),
    "strategy":("strategy","strategic priorities","our priorities","outlook","growth strategy"),
    "capital":("capital expenditure","capex","capacity expansion","capacity addition","investment"),
    "risk":("risk management","principal risks","risk factors","competition","regulatory risk","customer concentration"),
    "management":("chairman","managing director","management discussion","md&a","director's report"),
}
PROMISE_RE=re.compile(r"\\b(?:we|the company|management)\\b.{0,180}\\b(?:will|plan to|plans to|target|aim to|expect to|intend to|committed to)\\b.{0,220}[.!?]",re.I|re.S)


class AnnualReportEvidenceExtractor:
    """Extract auditable qualitative evidence without interpreting it."""

    def extract(self,path: str|Path,fiscal_year: str|None=None,max_pages: int=250) -> tuple[list[Evidence],list[ManagementPromise]]:
        path=Path(path)
        doc=pymupdf.open(path)
        evidence=[]; promises=[]
        for page_number,page in enumerate(doc,1):
            if page_number>max_pages: break
            text=page.get_text("text") or ""
            if not text.strip(): continue
            lower=text.lower()
            for category,keywords in SECTION_KEYWORDS.items():
                hits=[k for k in keywords if k in lower]
                if hits:
                    evidence.append(Evidence(category=category,statement=f"Matched keywords: {', '.join(hits[:4])}",source_file=str(path),fiscal_year=fiscal_year,page=page_number,confidence="medium"))
            for match in PROMISE_RE.finditer(text):
                statement=" ".join(match.group(0).split())
                if len(statement)>=45:
                    promises.append(ManagementPromise(statement=statement,source_file=str(path),fiscal_year=fiscal_year,page=page_number,promise_type=_promise_type(statement)))
        return _dedupe_evidence(evidence),_dedupe_promises(promises)


def _promise_type(text:str)->str:
    lower=text.lower()
    for name,words in (("capacity",("capacity","commission","plant")),("capex",("capex","investment","capital expenditure")),("growth",("growth","revenue","sales")),("strategy",("strategy","strategic","focus"))):
        if any(word in lower for word in words): return name
    return "strategy"


def _dedupe_evidence(items:Iterable[Evidence])->list[Evidence]:
    seen=set(); out=[]
    for item in items:
        key=(item.category,item.source_file,item.page)
        if key not in seen: seen.add(key); out.append(item)
    return out


def _dedupe_promises(items:Iterable[ManagementPromise])->list[ManagementPromise]:
    seen=set(); out=[]
    for item in items:
        key=(item.fiscal_year,item.page,item.statement[:120])
        if key not in seen: seen.add(key); out.append(item)
    return out
