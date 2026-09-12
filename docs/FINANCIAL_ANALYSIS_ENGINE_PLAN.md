# Financial Analysis Engine — Roadmap

**Status:** Agreed working plan  
**Branch:** `v8-investment-decision-engine`  
**Ultimate goal:** Make the system usable for finding and researching potential multibagger investments.

## 1. Product Goal

The project should evolve into a practical, evidence-based stock research system that helps identify promising multibagger candidates.

The system should not make decisions from a single metric or from LLM opinion. Financial calculations must be deterministic, validated, and traceable to data sources.

## 2. Staged Analysis Pipeline

```text
MARKET
  ↓
Universe Scanner
  ↓
Financial Pre-Screen
  ↓
Financial Engine
  ↓
Governance / Forensic Engine + Management Execution Engine
  ↓
Deep Research
  ↓
Valuation
  ↓
Decision Engine
  ↓
Multibagger Candidates
```

### Target scale

- **2,000–3,000 stocks:** cheap universe/market screening
- **~100–300:** financial pre-screen
- **~30–50:** full validated Financial Engine
- **~10–20:** governance/forensics + management execution
- **~5–10:** deep research + valuation + final decision

The full financial engine should **not** run across thousands of stocks.

## 3. Ownership Principle

**One calculation, one authoritative owner.**

- Revenue CAGR, PAT CAGR, ROCE, ROE, margins, debt, cash flow → **Financial Engine**
- Management promises, actions, and execution → **Management Execution Engine**
- Accounting/governance red flags → **Governance / Forensic Engine**
- Business model, industry, moat, growth runway, competition → **Deep Research**
- Fair value and scenario analysis → **Valuation Engine**
- BUY / WATCHLIST / AVOID → **Decision Engine**

Cheap pre-screening may use the same metric definitions as the full Financial Engine, but with lower-cost data and shallower validation. It must not create a second conflicting definition of the metric.

## 4. Financial Engine Scope

The Financial Engine answers:

1. Is the company growing?
2. Is growth profitable?
3. Does the company earn good returns on capital/equity?
4. Does accounting profit turn into cash?
5. Is the balance sheet safe?
6. Can the company reinvest successfully?

### Core annual inputs

Preferred record structure:

```text
FY
Revenue
EBIT / Operating Profit
PAT
Total Debt
Equity
Cash
CFO
Interest Expense
Capex
```

Preferred history: **5 valid fiscal years**.  
Minimum for the full engine: **3 valid fiscal years**.

Missing data must remain missing/unavailable. It must never silently become zero.

Fiscal years must be real, unique, validated, and chronological.

## 5. Metrics to Review

Before changing code, review each metric one at a time and decide **Keep / Change / Remove / Add**.

Order:

1. Revenue growth / CAGR
2. PAT growth / CAGR
3. PAT margin and margin trend
4. ROCE
5. ROE
6. Debt / Equity
7. Net debt
8. Interest coverage
9. CFO / PAT
10. Cash-flow consistency
11. Capex / reinvestment
12. Overall financial-quality score
13. Multibagger-specific additions/exclusions

For every metric, document:

- What it measures
- Why it matters
- Exact input fields
- Preferred source
- Validation rules
- Whether it is a pre-screen or full-engine metric
- Industry exceptions
- Meaning when data is unavailable

## 6. Current Financial Metrics

The existing engine calculates or exposes:

- Revenue CAGR
- PAT CAGR
- Revenue YoY
- PAT YoY
- PAT margin
- Margin trend / stability
- ROCE
- ROE
- Debt / Equity
- Net debt
- Interest coverage
- CFO / PAT
- Positive CFO years
- Average CFO / PAT
- Financial quality score
- P/E valuation separately

These are **not automatically accepted as final**. Each will be reviewed against the multibagger goal and validated data requirements before being changed.

## 7. Financial Quality vs Valuation

Keep these concepts separate:

- **Financial quality:** Is this a good business financially?
- **Valuation:** How much are we paying for it?

A high-quality company can be too expensive. A cheap company can be low quality.

Valuation should therefore remain a separate layer from core financial quality.

## 8. Data Source Strategy

Do not prematurely declare one source as the permanent primary source.

First define the financial data contract and validation rules. Then objectively test sources against that contract.

### Source roles

- **Regulatory/company filings:** preferred authoritative evidence where feasible.
- **Structured financial providers such as Screener:** useful for structured P&L, balance sheet, cash flow, and annual financial history; must pass validation.
- **Yahoo/NSE market data:** primarily useful for price, market cap, historical prices, volume, and market information. Yahoo should not automatically be treated as the preferred accounting-statement source.
- **Annual reports:** primary evidence for management commentary, commitments, actions, governance/accounting context, unusual items, explanations, and verification. They are not simply another raw-number feed.

Source choice should depend on the **fact being established**, not a blanket source preference.

## 9. Annual Report / Management Execution Layer

Annual reports should eventually support a separate Management Execution Engine.

Concept:

```text
Management says X
      ↓
Extract measurable commitment
      ↓
Find later evidence
      ↓
Compare actual action
      ↓
Compare business/financial outcome
      ↓
Execution assessment
```

Examples of trackable commitments:

- Capacity expansion
- Capex plans
- Debt reduction
- Margin targets
- New products
- New markets
- Acquisitions
- Plants / facilities
- Investment plans

The system should compare claims with later evidence rather than asking an LLM to simply label management as good or bad.

## 10. Validation Rules / Known Problems

The current financial pipeline has produced examples of invalid financial histories and bogus ratios. These must be eliminated before the engine is considered reliable.

Known failure patterns include:

- Fiscal years returned out of order
- Missing fiscal years
- Zero-valued financial years entering ratio calculations
- Invalid starting revenue/PAT producing misleading CAGR values
- Missing data being represented as zero
- Ambiguous handling of zero interest expense
- Misleading fixed labels such as “Average CFO / PAT (5Y)” when fewer years are available
- Weak Pydantic validation of chronological/unique fiscal years

Required principle:

> **Invalid financial data must fail validation or be marked unavailable; it must never produce a confident financial conclusion.**

## 11. Industry Exceptions

Industrial-company metrics must not be blindly applied to every sector.

Banks, insurers, and other financial businesses may require different measures for profitability, leverage, capital adequacy, and cash flow.

Industry classification should eventually determine which financial metric contract is appropriate.

## 12. Current Phase

### Phase 1 — Improve Financial Analysis Engine

We are **not** doing a broad rewrite now.

The immediate task is to walk through the Financial Engine calculations one by one, starting with:

### Step 1 — Revenue Growth / CAGR

For Revenue Growth / CAGR we will decide:

- exact definition
- why it matters for multibagger discovery
- annual vs CAGR usage
- required data
- source preference
- fiscal-year validation
- minimum valid history
- handling of missing/zero values
- pre-screen vs full-engine use
- industry exceptions

Only after agreeing on the metric definition should code be changed.

## 13. Engineering Principles

- Preserve existing working architecture where possible.
- Improve incrementally; avoid unnecessary rewrites.
- Keep deterministic Python calculations separate from LLM research.
- Keep data acquisition separate from calculations.
- Validate before calculating.
- Never turn missing data into zero silently.
- Never allow invalid data to generate confident investment conclusions.
- Prefer evidence-backed explanations over LLM-only judgments.
- Keep financial quality, governance, management execution, research, valuation, and final decision as distinct responsibilities.

## 14. Definition of Done for the Financial Engine

The Financial Engine is ready for production use when:

- Financial history is validated and correctly ordered.
- Required metrics have explicit definitions.
- Missing/invalid data is handled safely.
- Source provenance is retained.
- Metrics are consistent between pre-screen and full analysis.
- Industry-specific rules are respected.
- Financial quality is deterministic and testable.
- Known bogus-ratio cases are covered by tests.
- The engine can support downstream governance, management execution, research, valuation, and decision stages without duplicating financial calculations.
