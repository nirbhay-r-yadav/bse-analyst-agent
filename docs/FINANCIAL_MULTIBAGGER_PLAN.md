# Financial Analysis & Multibagger Discovery Plan

**Status: LOCKED — design baseline**

## 1. Objective

Build an evidence-based stock-analysis engine, not a numerical scoring system.

The primary goal is to collect reliable financial data, understand business economics and trajectory, classify the business, and identify potential multibaggers.

**Do not use an artificial 100-point score as the primary output.**

---

## 2. Core Pipeline

```text
NSE / XBRL data
      ↓
Local raw JSON cache
      ↓
Data validation
      ↓
Normalized financial facts
      ↓
Critical financial metrics
      ↓
Trend / inflection analysis
      ↓
Business quality analysis
      ↓
Multibagger analysis
      ↓
Investor report
```

Repeated analysis should use locally cached data whenever it is still valid, rather than repeatedly downloading the same information.

Python owns deterministic calculations and validation. LLMs may explain qualitative evidence, but must not invent financial facts or perform core deterministic calculations.

---

## 3. Critical Investor Questions

### 3.1 Is the business growing?

Metrics:
- Revenue growth
- Revenue CAGR where meaningful
- 3Y / 5Y / 10Y growth where available
- Growth acceleration
- Volume / operating growth where available

The report must distinguish sustained growth from a one-year spike.

### 3.2 Does growth create profit?

Metrics:
- EBIT
- EBIT margin
- PAT
- PAT margin
- PAT growth / recovery
- ROCE
- ROE

The system must identify whether revenue growth is translating into better economics.

### 3.3 Are profits real and cash-backed?

Metrics:
- CFO
- CFO / PAT
- FCF
- FCF margin
- CFO consistency
- Cash conversion trend

Accounting profit without supporting cash generation is a warning signal.

### 3.4 Is the balance sheet safe?

Metrics:
- Debt / Equity
- Net Debt
- Interest Coverage
- Working-capital trends
- Receivables
- Inventory
- Current liabilities

The system should distinguish low leverage from merely acceptable leverage and identify deterioration.

### 3.5 Does the business create shareholder value?

Metrics:
- ROCE
- ROE
- Incremental returns / incremental ROCE where data permits
- Retained earnings
- FCF
- Dilution / share-count changes
- Capital allocation

The question is not just whether the company grows, but whether growth creates value.

### 3.6 Can the business become much larger?

This requires financial plus qualitative evidence:
- Growth runway
- Reinvestment opportunity
- Capacity expansion
- Market opportunity
- Market-share potential
- New products / geographies / distribution
- Competitive position

---

## 4. Metric Philosophy

Every important metric should capture, where meaningful:

- Current level
- Historical values
- Trend
- Consistency
- Inflection / change in trajectory

Do not rely blindly on CAGR when the underlying series crosses zero or contains loss years.

For example, a mathematically valid PAT CAGR can be economically meaningless when PAT moved through losses. Such a metric should be marked unavailable / not meaningful rather than presented as a misleading growth rate.

Missing data remains missing. Never silently convert unavailable facts into zero.

Every important conclusion must be traceable to underlying facts and their source.

---

## 5. Business Classifications

The final system should classify businesses qualitatively rather than produce a false-precision score.

### EXCELLENT BUSINESS

Proven high-quality economics, strong returns, durable cash generation, sound balance sheet and attractive long-term characteristics.

### POTENTIAL MULTIBAGGER

Evidence suggests substantial future compounding potential. The company does not have to be excellent today if economics, runway and trajectory indicate significant room for improvement and expansion.

### GOOD BUSINESS

Healthy and attractive business, but not clearly exceptional enough to classify as excellent or potential multibagger.

### IMPROVING / TURNAROUND

Economics are materially improving, but evidence is not yet sufficient to call the business excellent or a multibagger.

### AVERAGE BUSINESS

No compelling exceptional characteristics.

### WEAK BUSINESS

Poor or deteriorating economics, profitability, cash generation or balance sheet.

### VALUE TRAP / HIGH RISK

Headline valuation or growth may look attractive, but underlying economics are weak, deteriorating or structurally risky.

---

## 6. Multibagger Detection Framework

A potential multibagger should be identified from multiple independent signals, not one ratio.

### Growth
- Sustained growth
- Growth acceleration
- Expanding addressable opportunity
- Volume / operating growth where available

### Profitability improvement
- EBIT margin expansion
- PAT margin expansion
- ROCE improvement
- ROE improvement

### Operating leverage

Look for cases where earnings are growing faster than revenue, for example:

```text
Revenue +20%
EBIT    +35%
PAT     +50%
```

This can indicate improving economics and operating leverage.

### Cash-flow confirmation

Strong evidence includes:

```text
PAT ↑
CFO ↑
FCF ↑
```

Profit growth without cash-flow confirmation requires caution.

### Reinvestment economics

Investigate whether the company can reinvest capital at attractive returns.

Where data permits, analyse incremental ROCE / incremental returns rather than only historical ROCE.

### Balance-sheet capacity

The company should have sufficient financial capacity to fund growth without destructive leverage or repeated equity dilution.

### Growth runway

Combine financial evidence with business-analysis evidence for:
- Capacity
- Distribution
- Products
- Geography
- Market size
- Market share
- Competitive position
- Management growth plans

### Valuation

Valuation is considered after understanding business economics and future potential.

The question is:

> Is the current market price already discounting most of the future growth?

A great business at an extreme valuation is not automatically a multibagger from today's price.

---

## 7. Current Quality vs Future Potential

The engine must explicitly distinguish current quality from future potential.

Examples:

| Current business | Trajectory | Interpretation |
|---|---|---|
| Excellent | Stable | Excellent compounder |
| Good | Rapidly improving | Potential multibagger candidate |
| Excellent | Deteriorating | Watch / possible future problem |
| Weak | Improving rapidly | Turnaround candidate |
| Cheap | Deteriorating | Possible value trap |

A company with the best current ratios is not automatically the best multibagger candidate.

---

## 8. Evidence Strength

Multibagger conclusions must carry evidence strength:

### EARLY

Some promising signals exist, but important confirmations are missing.

### DEVELOPING

Multiple independent signals are confirming the thesis, but durability is not yet fully established.

### STRONG

Growth, margins, returns, cash generation, reinvestment economics, runway, balance sheet and valuation provide broad independent confirmation.

Never make a binary multibagger claim merely because one or two metrics look attractive.

---

## 9. Data Architecture

Primary financial source:

**NSE / XBRL whenever the required financial fact is available.**

Target history:

**Up to 10 fiscal years, using whatever valid data is available under the source policy.**

Local structure should separate raw source data, normalized facts and derived analysis:

```text
data/
  financial/
    SYMBOL/
      raw/
      normalized/
      analysis/
```

Example:

```text
ZOTA/
  raw/
    FY2026.json
    FY2025.json
    ...
  normalized/
    financial_history.json
  analysis/
    financial_analysis.json
```

Derived analysis must not overwrite the source facts.

---

## 10. Development Order

1. Identify the exact required financial facts.
2. Map every fact to its best source.
3. Download and cache source data locally.
4. Build validation and normalization.
5. Build the critical financial metrics.
6. Build trend, consistency and inflection analysis.
7. Build business-quality classification.
8. Build multibagger detection.
9. Generate the investor-oriented financial report.
10. Only then connect the financial conclusion to the wider investment decision workflow.

---

## 11. Report Philosophy

The report must answer investor questions and explain conclusions, not dump ratios.

Each section should contain:

- Relevant facts
- Historical context
- Assessment
- Positives
- Concerns
- Evidence / source trace
- What would confirm the thesis
- What would invalidate the thesis

The report should finish with:

```text
Current Business Quality
Trajectory
Multibagger Potential
Evidence Strength
Key Positives
Key Concerns
What to Monitor
```

The report should explicitly explain **why** the company is or is not a potential multibagger.

---

## 12. Explicitly Abandoned

The following are not part of the target architecture:

- Artificial 100-point financial scoring as the primary output
- Arbitrary weights creating false precision
- LLM-generated financial facts
- LLM-owned deterministic calculations
- Calling a company a multibagger solely because of high growth
- Calling a company a multibagger solely because of low PE
- Calling a company a multibagger solely because of one attractive ratio

The engine should **discover, explain and challenge the investment thesis**, rather than manufacture a numerical ranking.

---

## Locked Design Principle

> **Reliable data first. Understand the economics second. Detect the trajectory third. Classify the business fourth. Test multibagger potential fifth. Report the evidence clearly.**

This document is the design baseline for the next financial-analysis refactor. Changes to this direction should be deliberate and explicit rather than accidental changes made while fixing individual metrics.
