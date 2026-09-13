# BSE Analyst Agent — Frozen Architecture

## Purpose

BSE Analyst Agent is an investment research and decision-support engine designed to help identify high-quality companies with potential for long-term compounding and multibagger returns.

The architecture below is frozen. Development should improve the existing stages rather than continuously adding new top-level modules.

## Investment Analysis Pipeline

```text
MARKET
  ↓
UNIVERSE SCANNER
  ↓
FINANCIAL ANALYSIS
  ↓
GOVERNANCE + MANAGEMENT
  ↓
BUSINESS RESEARCH
  ↓
VALUATION
  ↓
DECISION
  ↓
MULTIBAGGER CANDIDATES
```

## Stage Responsibilities

### 1. Market
Provides market and security-level information required by the rest of the pipeline.

### 2. Universe Scanner
Discovers and filters the investable stock universe and identifies companies that should receive deeper analysis.

### 3. Financial Analysis
Answers: **What do the financial statements show?**

Financial Analysis should use the maximum reliable historical financial data available, up to a 10-year analytical window.

Metrics may include:

- Revenue and revenue growth
- PAT and PAT growth
- PAT margins
- ROCE
- ROE
- Debt / Equity
- Net debt
- Interest coverage
- CFO / PAT
- Cash-flow consistency
- Capex / reinvestment
- Financial-quality assessment

Rules:

- Use up to 10 years when reliable data is available.
- Retrieve an additional prior year when a metric requires prior-year data, such as average-equity ROE.
- Each metric uses the maximum valid history supported by its required inputs.
- Missing data is represented as unavailable (`None`), never silently as zero.
- Invalid or insufficient data must not produce a fabricated conclusion.
- Preserve annual observations so trends, consistency, and long-term behaviour can be evaluated.
- Do not silently change metric definitions.
- Deterministic financial calculations must remain separate from LLM-generated interpretation.

### 4. Governance + Management
Answers: **Can the company and its management be trusted?**

This stage contains corporate governance and management-quality/risk analysis, including:

- Promoter ownership and behaviour
- Promoter pledging where available
- Auditor qualifications, resignations, adverse opinions, and disclaimers
- Related-party transactions and risks
- Material corporate announcements and filings
- Management commitments and execution
- Capital-allocation behaviour
- Management credibility based on claims versus subsequent evidence

Annual reports and exchange filings are evidence sources for this stage; annual-report analysis is not a separate top-level module.

### 5. Business Research
Answers: **What is the business, and can it grow for a long time?**

Business Research covers:

- Business model
- Products and services
- Customers
- Industry and market
- Competition
- Competitive advantage / moat
- Growth opportunities and runway
- Pricing and profit drivers
- Capacity and utilisation where relevant
- Capital requirements
- Other qualitative evidence relevant to long-term business quality

Business Model Analysis is part of Business Research, not a separate top-level module.

### 6. Valuation
Answers: **What is a reasonable price for the business?**

Valuation must use validated financial inputs and must withhold a valuation conclusion when required inputs are unavailable rather than treating missing values as zero.

### 7. Decision
Combines the independent evidence from Financial Analysis, Governance + Management, Business Research, and Valuation into an explainable investment conclusion.

The decision layer must preserve hard-risk failures and data-quality failures rather than allowing a strong score in one dimension to hide a material failure in another.

## Data Sources

Financial and research information may come from multiple sources, but the engine should prefer authoritative sources where practical:

1. Company annual reports and audited financial statements
2. NSE and BSE exchange filings and disclosures
3. Structured secondary financial-data sources such as Screener for convenient extraction and cross-checking
4. Market-data providers such as Yahoo Finance for market data and supplementary information

No secondary source should automatically override a conflicting primary filing. Material conflicts must be detected and resolved or surfaced as data-quality issues.

## Architectural Rules

1. **No new top-level module without explicit architectural justification.**
2. Improve the existing stages before creating new stages.
3. One calculation should have one authoritative owner.
4. Financial calculations must be deterministic and test-covered.
5. LLM reasoning must not replace numerical calculations or data validation.
6. Do not silently change established metric definitions.
7. Do not modify unrelated modules while implementing a focused financial or governance change.
8. Financial calculation changes require tests for normal cases and relevant edge cases.
9. Prefer primary financial sources for authoritative conclusions.
10. Data-quality failures must stop or qualify conclusions rather than being hidden.

## Historical Analysis Principle

The engine should behave intelligently when historical data is available:

```text
Maximum reliable history available
            ↓
       Up to 10 years
            ↓
  Validate each required field
            ↓
Calculate each metric using its
maximum valid historical window
            ↓
Report years available / years used
```

The goal is not merely to produce ratios. The goal is to reconstruct the company's financial character over time and use that evidence in the investment decision.

## Scope Discipline

The current development priority is to strengthen **Financial Analysis** incrementally. Governance + Management and Business Research should continue to evolve within their existing stages.

Development sequence:

```text
Define metric
  ↓
Define required data
  ↓
Define historical-window behaviour
  ↓
Define edge cases
  ↓
Write tests
  ↓
Implement
  ↓
Run tests
  ↓
Commit
  ↓
Proceed to next metric
```

This architecture is intentionally stable so engineering effort can be spent improving accuracy, historical depth, validation, and investment usefulness rather than repeatedly redesigning the system.
