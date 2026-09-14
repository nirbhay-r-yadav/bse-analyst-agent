"""
src/agent.py
Qualitative Gemini orchestration for the unified research pipeline.

Gemini interprets governance evidence and writes the investment thesis.
Python owns financial extraction, numeric calculations, validation, valuation,
and the final deterministic verdict.
"""

import os
import json
import warnings
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from src.prompts import FORENSIC_AUDITOR_SYSTEM, INVESTMENT_COMMITTEE_SYSTEM

warnings.filterwarnings("ignore", message=r".*fixed sampling defaults.*temperature will be ignored.*")
warnings.filterwarnings("ignore", message=r".*automatic function calling \(AFC\).*")


class ForensicAuditOutput(BaseModel):
    """Structured, year-specific governance evidence extracted from one annual report."""

    audit_opinion_type: str = Field(description="Unmodified/Clean, Qualified, Adverse, or Disclaimer")
    auditor_observations: List[str] = Field(description="Material auditor, CARO, internal-control, EOM, or KAM observations actually stated in the report")
    key_audit_matters: List[str] = Field(description="Material KAMs and accounting judgement areas actually disclosed")
    related_party_transactions: List[str] = Field(description="Actual related-party transactions, counterparties, amounts, percentages, balances, and nature disclosed in the notes; empty only when none/materially none are identified")
    loans_guarantees_investments: List[str] = Field(description="Actual loans, guarantees, investments, advances, or other funding to subsidiaries/promoter/group entities, including amounts and outstanding balances where disclosed")
    contingent_liabilities: List[str] = Field(description="Actual contingent liabilities, disputed claims, guarantees, tax/legal exposures, amounts, and nature disclosed")
    remuneration_details: List[str] = Field(description="Actual promoter/director/KMP/relative remuneration, commission, or benefits disclosed, including amounts where available")
    regulatory_compliance_events: List[str] = Field(description="Actual regulatory, statutory, compliance, delay, penalty, SEBI/exchange, tax, PF/GST, whistleblower, or other governance events disclosed")
    what_happened: List[str] = Field(description="Concise factual year-level events that actually happened according to the supplied annual report; preserve amounts, percentages, counterparties, and dates when available")
    contingent_liability_risk: str = Field(description="Low, Medium, or High with concise evidence-based reasoning")
    related_party_risk: str = Field(description="Low, Medium, or High with concise evidence-based reasoning")
    forensic_red_flags: List[str] = Field(description="Specific evidence-backed accounting, audit, or governance red flags; do not invent")
    why_it_matters: List[str] = Field(description="Investor interpretation of the actual disclosed facts, clearly separated from facts")
    governance_conclusion: str = Field(description="One concise year-level governance conclusion based only on the supplied evidence")


class InvestmentMemo(BaseModel):
    verdict: str = Field(description="BUY, WATCHLIST, or AVOID. Advisory only; deterministic Python decides the verdict.")
    conviction_score: int = Field(description="1-10 confidence in the written thesis, not a replacement for the deterministic score")
    executive_summary: str = Field(description="Clear investment thesis and business-quality interpretation")
    financial_strengths: List[str] = Field(description="Key financial and competitive strengths")
    critical_risks: List[str] = Field(description="Structural risks and thesis-breakers")
    governance_clearance: bool = Field(description="True only when governance evidence is clean enough to pass")


class AnalysisOrchestrator:
    """LLM-only qualitative layer; no financial-number extraction."""

    def __init__(self, model_name: str | None = None, temperature: float = 0.0):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY or GOOGLE_API_KEY environment variable not detected. Set it in .env."
            )
        selected_model = model_name or os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        self.llm = ChatGoogleGenerativeAI(
            model=selected_model,
            temperature=temperature,
            google_api_key=api_key,
        )

    def audit_forensics(self, auditor_text: str, notes_text: str) -> ForensicAuditOutput:
        prompt = ChatPromptTemplate.from_messages([
            ("system", FORENSIC_AUDITOR_SYSTEM),
            (
                "human",
                "Perform the forensic governance audit. Return factual, year-specific evidence. "
                "Do not summarize a fact merely as a risk label when the underlying amount, party, "
                "percentage, event, or disclosure is present in the supplied text.\n\n"
                "=== AUDITOR REPORT / CARO ===\n{auditor_text}\n\n"
                "=== NOTES ===\n{notes_text}",
            ),
        ])
        chain = prompt | self.llm.with_structured_output(ForensicAuditOutput)
        return chain.invoke({
            "auditor_text": auditor_text or "No auditor text extracted.",
            "notes_text": notes_text or "No notes text extracted.",
        })

    def run_investment_committee(
        self,
        forensic: ForensicAuditOutput,
        calculated_ratios: Dict[str, Any],
        quality_score: Dict[str, Any],
        valuation: Dict[str, Any] | None = None,
    ) -> InvestmentMemo:
        prompt = ChatPromptTemplate.from_messages([
            ("system", INVESTMENT_COMMITTEE_SYSTEM),
            (
                "human",
                "Interpret the evidence. Do not override Python's numeric score, "
                "valuation, or final verdict.\n\n"
                "=== FORENSIC ===\n{forensics}\n\n"
                "=== FUNDAMENTALS ===\n{ratios}\n\n"
                "=== QUALITY SCORE ===\n{quality}\n\n"
                "=== VALUATION ===\n{valuation}",
            ),
        ])
        chain = prompt | self.llm.with_structured_output(InvestmentMemo)
        return chain.invoke({
            "forensics": forensic.model_dump_json(indent=2),
            "ratios": json.dumps(calculated_ratios, indent=2),
            "quality": json.dumps(quality_score, indent=2),
            "valuation": json.dumps(valuation or {"available": False}, indent=2),
        })
