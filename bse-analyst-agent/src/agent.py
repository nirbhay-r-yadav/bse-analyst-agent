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

from src.prompts import (
    FORENSIC_AUDITOR_SYSTEM,
    INVESTMENT_COMMITTEE_SYSTEM,
    BUSINESS_REPORT_EXTRACTION_SYSTEM,
    BUSINESS_REPORT_SYNTHESIS_SYSTEM,
)

warnings.filterwarnings("ignore", message=r".*fixed sampling defaults.*temperature will be ignored.*")
warnings.filterwarnings("ignore", message=r".*automatic function calling \(AFC\).*")


class ForensicAuditOutput(BaseModel):
    """Structured, year-specific governance evidence extracted from one annual report."""

    audit_opinion_type: str = Field(description="Unmodified/Clean, Qualified, Adverse, or Disclaimer")
    auditor_observations: List[str] = Field(default_factory=list, description="Material auditor, CARO, internal-control, EOM, or KAM observations actually stated in the report")
    key_audit_matters: List[str] = Field(default_factory=list, description="Material KAMs and accounting judgement areas actually disclosed")
    related_party_transactions: List[str] = Field(default_factory=list, description="Actual related-party transactions, counterparties, amounts, percentages, balances, and nature disclosed in the notes")
    loans_guarantees_investments: List[str] = Field(default_factory=list, description="Actual loans, guarantees, investments, advances, or other funding to subsidiaries/promoter/group entities, including amounts and outstanding balances where disclosed")
    contingent_liabilities: List[str] = Field(default_factory=list, description="Actual contingent liabilities, disputed claims, guarantees, tax/legal exposures, amounts, and nature disclosed")
    remuneration_details: List[str] = Field(default_factory=list, description="Actual promoter/director/KMP/relative remuneration, commission, or benefits disclosed, including amounts where available")
    regulatory_compliance_events: List[str] = Field(default_factory=list, description="Actual regulatory, statutory, compliance, delay, penalty, SEBI/exchange, tax, PF/GST, whistleblower, or other governance events disclosed")
    what_happened: List[str] = Field(default_factory=list, description="Concise factual year-level events that actually happened according to the supplied annual report; preserve amounts, percentages, counterparties, and dates when available")
    contingent_liability_risk: str = Field(description="Low, Medium, or High with concise evidence-based reasoning")
    related_party_risk: str = Field(description="Low, Medium, or High with concise evidence-based reasoning")
    forensic_red_flags: List[str] = Field(default_factory=list, description="Specific evidence-backed accounting, audit, or governance red flags; do not invent")
    why_it_matters: List[str] = Field(default_factory=list, description="Investor interpretation of the actual disclosed facts, clearly separated from facts")
    governance_conclusion: str = Field(default="Unavailable", description="One concise year-level governance conclusion based only on the supplied evidence")


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


    class BusinessEvidenceOutput(BaseModel):
        """Meaningful business evidence extracted from one annual-report package."""
        business_model: List[str] = Field(default_factory=list)
        industry_and_market: List[str] = Field(default_factory=list)
        products_and_customers: List[str] = Field(default_factory=list)
        competitive_position: List[str] = Field(default_factory=list)
        strategy: List[str] = Field(default_factory=list)
        growth_drivers: List[str] = Field(default_factory=list)
        economics: List[str] = Field(default_factory=list)
        capital_allocation: List[str] = Field(default_factory=list)
        business_risks: List[str] = Field(default_factory=list)
        management: List[str] = Field(default_factory=list)
        promises: List[Dict[str, Any]] = Field(default_factory=list)
        evidence: List[Dict[str, Any]] = Field(default_factory=list)

    class BusinessResearchOutput(BaseModel):
        """Cross-year business and risk synthesis."""
        executive_summary: str = ""
        business_model: Dict[str, Any] = Field(default_factory=dict)
        industry_and_market: Dict[str, Any] = Field(default_factory=dict)
        products_and_customers: Dict[str, Any] = Field(default_factory=dict)
        competitive_position: Dict[str, Any] = Field(default_factory=dict)
        strategy: Dict[str, Any] = Field(default_factory=dict)
        growth_drivers: List[str] = Field(default_factory=list)
        economics: Dict[str, Any] = Field(default_factory=dict)
        capital_allocation: Dict[str, Any] = Field(default_factory=dict)
        business_risks: List[Dict[str, Any]] = Field(default_factory=list)
        management: Dict[str, Any] = Field(default_factory=dict)
        ten_year_evolution: List[str] = Field(default_factory=list)
        emerging_risks: List[str] = Field(default_factory=list)
        limitations: List[str] = Field(default_factory=list)
        evidence: List[Dict[str, Any]] = Field(default_factory=list)

    def extract_business_evidence(self, report_text: str, fiscal_year: str) -> "AnalysisOrchestrator.BusinessEvidenceOutput":
        prompt = ChatPromptTemplate.from_messages([
            ("system", BUSINESS_REPORT_EXTRACTION_SYSTEM),
            ("human",
             "Extract meaningful business evidence from this annual report package. "
             "Every evidence item must include fiscal_year and page when available. "
             "For promises, include statement, promise_type, expected_outcome, fiscal_year and page.\n\n"
             "=== FISCAL YEAR ===\n{fiscal_year}\n\n"
             "=== ANNUAL REPORT EXCERPTS ===\n{report_text}"),
        ])
        chain = prompt | self.llm.with_structured_output(self.BusinessEvidenceOutput)
        return chain.invoke({"fiscal_year": fiscal_year, "report_text": report_text})

    def synthesize_business_research(self, evidence_json: str) -> "AnalysisOrchestrator.BusinessResearchOutput":
        prompt = ChatPromptTemplate.from_messages([
            ("system", BUSINESS_REPORT_SYNTHESIS_SYSTEM),
            ("human",
             "Synthesize the following evidence from multiple annual reports into one "
             "coherent Business & Risk Research report. Preserve source years/pages for material claims.\n\n"
             "=== EXTRACTED EVIDENCE ===\n{evidence_json}"),
        ])
        chain = prompt | self.llm.with_structured_output(self.BusinessResearchOutput)
        return chain.invoke({"evidence_json": evidence_json})

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
