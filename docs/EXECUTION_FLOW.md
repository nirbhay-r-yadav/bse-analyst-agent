# Execution & Data-Source Flow Map

## Why this file exists

This document makes the runtime path of the CLI explicit so that every menu item can be traced from **user input -> source code -> data source -> transformation -> scoring -> output**.

It is an engineering/debugging map, not a second architecture. The frozen stage architecture remains authoritative.

## Current entry point

`bse-analyst-agent/main.py`

When no CLI arguments are supplied, `interactive()` presents three menu items:

```text
1. Deep Scan
2. Small / micro-cap universe scan
3. Exit
```

---

## Menu 1 — Deep Scan

### User input

```text
Enter NSE symbol for Deep Scan
```

### Call chain

```text
main.py
  interactive()
    -> run_single_stock(symbol)
      -> DeepScannerEngine().analyze_symbol(symbol)
         -> governance evidence
         -> annual-report download + forensic audit
         -> corporate-risk assessment
         -> structured financial history
         -> deterministic financial ratios / quality
         -> valuation
         -> decision engine
         -> investment committee LLM explanation
         -> persisted stage outputs
      -> generate_investment_text_report()
      -> optional generate_investment_report()
```

### Primary source-code owners

| Step | Code owner | Responsibility |
|---|---|---|
| CLI input | `main.py` | Collect symbol and flags |
| Orchestration | `src/deep_scanner.py` | Controls candidate analysis order |
| Governance filings | `src/nse_corporate_filings.py` | NSE corporate/PIT risk inputs |
| Annual reports | `src/nse_downloader.py` | Retrieve annual reports |
| Document extraction | `src/doc_parser.py` | Extract auditor report / notes |
| Qualitative forensic audit | `src/agent.py` | LLM-based annual-report forensic interpretation |
| Corporate risk | `src/corporate_risk.py` | Deterministic governance/risk scoring |
| Financial data | `src/financial_data_provider.py` | Structured historical financial inputs |
| Financial calculations | `src/financial_engine.py` | Ratios, quality, valuation inputs |
| Investment decision | `src/decision_engine.py` | Deterministic decision synthesis |
| Reports | `src/report_generator.py` | Human-readable output |

### Data-source policy

The current architecture distinguishes evidence by purpose:

- **Governance / corporate risk:** NSE corporate/PIT filings plus annual reports.
- **Financial analysis:** structured financial provider; annual-report tables are deliberately not used as the financial-metric source in the current deep-scanner governance path.
- **Market inputs:** universe/market data supplied in the candidate row.
- **Qualitative interpretation:** annual-report text sent to the forensic LLM stage.

The authoritative source for each metric must be recorded before changing the provider.

---

## Menu 2 — Small / micro-cap universe scan

### User input

There is no symbol input. The menu uses the configured NSE universe and the `SmallMicrocapConfig` filters.

### Call chain

```text
main.py
  interactive()
    -> run_universe_scan(refresh=False, top=50)
      -> NSEUniverse.discover()
      -> classify_market_cap()
      -> liquidity / price filters
      -> sort candidates
      -> save outputs/small_microcap_universe.csv
      -> print Stage-1 candidates

Optional continuation:

run -> DeepScannerEngine().run(
       input_csv=outputs/small_microcap_universe.csv,
       top=10,
       deep_limit=20,
       live_filings=True,
     )
```

### Source-code owners

| Step | Code owner | Responsibility |
|---|---|---|
| Universe discovery | `src/nse_universe.py` | Discover/refresh NSE equity universe |
| Market-cap classification | `src/smallcap_scanner.py` | MICROCAP / SMALLCAP classification and thresholds |
| Candidate ranking/filtering | `main.py` | Price, traded-value and category filters |
| Deep continuation | `src/deep_scanner.py` | Runs selected candidates through the full pipeline |

### Output contract

`outputs/small_microcap_universe.csv` currently records:

- `symbol`
- `company_name`
- `market_cap_category`
- `market_cap_cr`
- `price`
- `avg_daily_value_cr`
- `source`

Important: this is a **candidate list**, not an investment recommendation.

---

## Menu 3 — Exit

```text
interactive() -> return
```

No data source, analysis engine, or output file is touched.

---

# Runtime evidence we should expose next

For every meaningful stage, the engine should eventually be able to emit a trace record with this shape:

```text
TRACE
  run_id
  symbol
  menu_action
  stage
  function
  input_summary
  source_name
  source_locator
  retrieved_at
  records_received
  records_valid
  records_used
  years_available
  years_used
  transformations
  validation_status
  output_fields
  warnings
  duration_ms
```

This is the key missing observability layer. It lets us answer questions such as:

- Which exact function supplied PAT?
- Which source supplied each fiscal year?
- How many years were available versus used?
- Why was a year rejected?
- Which calculation produced ROCE?
- Which file/report was used for a governance red flag?
- Did the LLM interpret evidence or generate a number?
- Which stage stopped the analysis?

## Refactor rule

Do **not** add another investment-analysis stage to solve observability. Instrument the existing stages.

The next implementation step is to add a lightweight execution-trace facility and wire it first into the two active paths:

1. `run_single_stock()` / `DeepScannerEngine.analyze_candidate()`
2. `run_universe_scan()` / `DeepScannerEngine.run()`

Then extend the trace to Financial Analysis metric-by-metric, starting with **PAT and ROCE**, because those are the current validation priority.
