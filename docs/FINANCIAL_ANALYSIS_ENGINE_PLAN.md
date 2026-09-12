# BSE Analyst Agent — Architecture & Long-Term Goal

**Status:** Agreed and frozen working architecture  
**Branch:** `v8-investment-decision-engine`  
**Goal:** Build a usable, evidence-based system that helps identify and research potential multibagger investments.

## 1. Product Goal

The system should help find companies that may have the combination of:

- strong financial quality;
- durable growth;
- trustworthy governance and management execution;
- a strong business with meaningful growth runway; and
- reasonable valuation.

The system is a research and decision-support tool, not a stock-tip generator.

## 2. Architecture — Do Not Expand Without a Strong Reason

```text
                         MARKET
                           ↓
                  Universe Scanner
                           ↓
                  Financial Analysis
                           ↓
                Governance + Management
                           ↓
                    Business Research
                           ↓
                      Valuation
                           ↓
                     Decision
                           ↓
              Multibagger Candidates
```

This architecture is the agreed long-term direction.

**We will not keep adding new top-level modules.**

Future work should focus on improving, validating, and optimizing the existing modules.

## 3. Module Responsibilities

| Module | Main Question |
|---|---|
| **Universe Scanner** | What companies should we look at? |
| **Financial Analysis** | Are the financial numbers strong and reliable? |
| **Governance + Management** | Can we trust management and its execution? |
| **Business Research** | Is this a strong business with room to become much bigger? |
| **Valuation** | Is the current price reasonable relative to the opportunity? |
| **Decision** | Is the company worth further investment consideration? |
| **Multibagger Candidates** | Which companies deserve the highest research/investment attention? |

## 4. Business Research Is the Overarching Qualitative Layer

Business Research is intentionally broad rather than split into multiple engines.

It can cover:

- business model;
- products and services;
- customers;
- industry and market;
- competition;
- competitive advantages / moat;
- growth opportunities and runway;
- annual-report research;
- management commentary relevant to the business; and
- other qualitative evidence needed to understand the company.

Business Model Analysis is therefore a capability inside **Business Research**, not a separate top-level module.

## 5. Optimization Rule

The architecture is frozen for the foreseeable development of the project.

**Only optimize the existing modules. Do not divert into architecture expansion.**

Optimization includes:

- improving accuracy;
- improving data quality;
- improving source reliability;
- improving calculations;
- improving validation;
- improving speed and efficiency;
- improving evidence quality;
- improving tests;
- improving explainability; and
- improving the final decision quality.

A new top-level module should only be considered if the existing architecture cannot reasonably support a required capability.

## 6. Design Principles

### One calculation, one owner

Each important calculation should have one authoritative definition and owner. Other modules reuse the result rather than creating conflicting versions.

### Deterministic financial analysis

Financial calculations and financial scoring must be validated, testable, and traceable to source data.

### Evidence over opinion

LLMs may help extract, compare, summarize, and explain evidence. They should not replace validated calculations or invent unsupported conclusions.

### Progressive depth

The system should become deeper and more expensive as companies survive each stage.

```text
Large universe
      ↓
Cheap screening
      ↓
Financial analysis
      ↓
Governance + management
      ↓
Business research
      ↓
Valuation
      ↓
Final shortlist
```

## 7. Long-Term Objective

Build a practical system that can answer:

> **Which companies have the financial quality, durable growth, trustworthy management, strong business characteristics, and reasonable valuation that make them worth researching as potential multibaggers?**

The immediate development priority is to make each existing module accurate, reliable, efficient, and useful — without changing the agreed architecture.
