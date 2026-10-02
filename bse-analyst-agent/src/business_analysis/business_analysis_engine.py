from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .business_classifier import classify_business
from .evidence_extractor import AnnualReportEvidenceExtractor
from .metrics import analyze_financial_economics
from .models import BusinessAnalysisResult


class BusinessAnalysisEngine:
    """Build an evidence-first business analysis from annual reports and history.

    This first version deliberately avoids an opaque business-quality score.
    It produces measurable economics, extracted evidence, and management
    promises so later interpretation can be audited.
    """

    def __init__(self, reports_root: str|Path="data/annual_reports", history_root: str|Path="data/financial_history"):
        self.reports_root=Path(reports_root)
        self.history_root=Path(history_root)
        self.extractor=AnnualReportEvidenceExtractor()

    def analyze(self,symbol:str)->BusinessAnalysisResult:
        symbol=symbol.upper().strip()
        reports=self._reports(symbol)
        rows=self._history(symbol)
        result=BusinessAnalysisResult(symbol=symbol)
        all_text=[]
        for fiscal_year,path in reports:
            evidence,promises=self.extractor.extract(path,fiscal_year=fiscal_year)
            result.evidence.extend(evidence)
            result.management_promises.extend(promises)
            try:
                import pymupdf
                doc=pymupdf.open(path)
                all_text.append("\\n".join(page.get_text("text") for page in doc))
            except Exception:
                continue
        combined="\\n".join(all_text)
        result.business_model=classify_business(combined)
        economics=analyze_financial_economics(rows)
        result.business_economics=economics
        result.profit_engine={k:economics[k] for k in ("ebit_margin_pct","pat_margin_pct","cfo_pat_ratio","roce_pct","revenue_cagr_approx","positive_cfo_years","cfo_years")}
        result.capital_absorption={
            "capital_intensity_proxy":"capex_to_revenue_pct",
            "capex_to_revenue_pct":economics.get("capex_to_revenue_pct"),
            "latest_capex_cr":economics.get("latest_capex_cr"),
            "net_debt_cr":economics.get("net_debt_cr"),
            "note":"Capex is a proxy for capital absorption; full incremental invested-capital analysis requires validated capex and working-capital history.",
        }
        result.management_execution=self._management_execution(result.management_promises,economics)
        result.risks=self._risk_signals(combined,economics)
        return result

    def save(self,result:BusinessAnalysisResult,output_root:str|Path="outputs/business_analysis")->Path:
        destination=Path(output_root)/result.symbol/"business_analysis.json"
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(json.dumps(result.to_dict(),indent=2,default=str),encoding="utf-8")
        return destination

    def _reports(self,symbol:str)->list[tuple[str,Path]]:
        directory=self.reports_root/symbol
        if not directory.exists(): return []
        files=[]
        for path in sorted(directory.glob("*.pdf")):
            years=[int(x) for x in __import__("re").findall(r"20\\d{2}",path.name)]
            fiscal=f"FY{max(years)}" if years else None
            if fiscal: files.append((fiscal,path))
        return files

    def _history(self,symbol:str)->list[dict[str,Any]]:
        path=self.history_root/symbol/"history.json"
        if not path.exists(): return []
        payload=json.loads(path.read_text(encoding="utf-8"))
        return payload.get("rows",[])

    @staticmethod
    def _management_execution(promises:list[Any],economics:dict[str,Any])->dict[str,Any]:
        by_type={}
        for promise in promises: by_type[promise.promise_type]=by_type.get(promise.promise_type,0)+1
        return {
            "promises_extracted":len(promises),
            "promise_types":by_type,
            "outcome_matching":"not_yet_automated",
            "financial_outcomes_available":bool(economics.get("years_available")),
            "note":"Promise-to-outcome matching will be added after deterministic promise normalization and cross-year entity matching are tested.",
        }

    @staticmethod
    def _risk_signals(text:str,economics:dict[str,Any])->dict[str,Any]:
        lower=text.lower()
        terms={
            "customer_concentration":("customer concentration","single customer","top customer"),
            "regulatory":("regulatory risk","regulatory changes","regulation"),
            "competition":("intense competition","competitive pressure","competition"),
            "commodity":("commodity prices","raw material prices","commodity risk"),
            "fx":("foreign exchange risk","currency risk","forex"),
            "cyclicality":("cyclical","industry cycle","downcycle"),
        }
        return {"signals":{name:any(term in lower for term in words) for name,words in terms.items()},"net_debt_cr":economics.get("net_debt_cr")}
