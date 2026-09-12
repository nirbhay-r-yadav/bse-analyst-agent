# Financial Analysis Engine — Roadmap

**Status:** Agreed working plan  
**Branch:** `v8-investment-decision-engine`  
**Ultimate goal:** Make the system usable for finding and researching potential multibagger investments.

## 1. Product Goal

Build a practical, evidence-based stock research system that helps identify promising multibagger candidates.

The system should:

- combine multiple independent evidence layers rather than rely on a single metric;
- use deterministic, validated financial calculations;
- keep LLM analysis focused on research, evidence extraction, and explanation rather than inventing financial conclusions;
- produce traceable, evidence-backed candidates for further investment research.

## 2. Architecture

```text
                              MARKET
                                │
                                ▼
                       ┌──────────────────┐
                       │ Universe Scanner │
                       └────────┬─────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ Financial        │
                       │ Pre-Screen       │
                       └────────┬─────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ Financial        │
                       │ Analysis Engine  │
                       └────────┬─────────┘
                                │
                 ┌──────────────┴──────────────┐
                 ▼                             ▼
       ┌────────────────────┐       ┌────────────────────────┐
       │ Governance /       │       │ Management Execution   │
       │ Forensic Engine    │       │ Engine                 │
       └──────────┬─────────┘       └───────────┬────────────┘
                  └──────────────┬──────────────┘
                                 ▼
                       ┌──────────────────┐
                       │ Deep Research    │
                       │ Business / Moat  │
                       └────────┬─────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ Valuation Engine │
                       └────────┬─────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ Decision Engine  │
                       └────────┬─────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   Multibagger    │
                       │   Candidates     │
                       └──────────────────┘
```

## 3. Responsibility of Each Layer

| Layer | Responsibility |
|---|---|
| **Universe Scanner** | Identify the investable market universe efficiently. |
| **Financial Pre-Screen** | Cheaply reduce the universe using consistent financial definitions. |
| **Financial Analysis Engine** | Deterministically validate and analyze financial performance, profitability, returns, cash flow, balance sheet, and reinvestment capacity. |
| **Governance / Forensic Engine** | Detect accounting, governance, and forensic red flags. |
| **Management Execution Engine** | Compare management statements and commitments with later actions and outcomes. |
| **Deep Research** | Analyze business model, industry, moat, competition, growth runway, and other qualitative evidence. |
| **Valuation Engine** | Estimate value using transparent valuation methods and scenarios. |
| **Decision Engine** | Combine the evidence layers into a final deterministic investment classification. |

## 4. Core Design Principles

### One calculation, one authoritative owner

A metric should have one authoritative definition and calculation owner. Other stages may reuse its result, but should not create conflicting versions.

### Deterministic financial analysis

Financial calculations and financial scoring must be deterministic, validated, testable, and traceable to source data.

### Evidence over opinion

LLMs may help extract, compare, summarize, and explain evidence. They should not replace validated financial calculations or make unsupported investment judgments.

### Separate responsibilities

Financial quality, governance, management execution, business research, valuation, and final decision-making remain distinct layers.

### Staged processing

The system should become progressively more expensive and deeper as a stock survives each stage:

```text
Thousands of stocks
        ↓
Cheap screening
        ↓
Hundreds
        ↓
Financial analysis
        ↓
Tens
        ↓
Governance + management execution
        ↓
Small shortlist
        ↓
Deep research + valuation
        ↓
Multibagger candidates
```

The full Financial Analysis Engine should not be unnecessarily run across the entire market universe.

## 5. Long-Term Objective

The finished system should help answer:

> **Which companies have the combination of financial quality, durable growth, management execution, governance quality, business strength, and reasonable valuation that makes them worth researching as potential multibaggers?**

The system should provide the evidence and analysis needed to answer that question — not simply output a stock tip.
