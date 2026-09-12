# BSE Analyst Agent

**AI-powered Indian stock analysis and investment research platform**

BSE Analyst Agent is a Python-based research platform for analyzing Indian equities through market data, multi-year financial fundamentals, corporate governance risk, valuation signals, and structured investment decisions.

> **Goal:** Turn raw market and company data into structured, explainable investment research.

## 🚀 Key Features

### 📊 Market & Universe Analysis
- Large-scale Indian stock universe discovery
- Bulk quote retrieval and market-data processing
- Market-cap based filtering and candidate selection
- Optimized workflows for large-universe scans

### 💰 Financial Analysis
- Multi-year financial statement analysis
- Revenue, EBIT and PAT analysis
- Growth and profitability metrics
- Financial quality scoring
- Fiscal-year validation and data-quality checks
- Protection against incomplete or unreliable financial data producing false conclusions

### 🏢 Corporate Governance & Risk
- Corporate announcement and filing analysis
- Multi-year corporate-risk assessment
- Governance-risk calibration
- Detection of potentially material corporate events
- Separation of meaningful risk signals from generic filing noise

### 📈 Investment Decision Engine

The investment workflow evaluates multiple independent dimensions:

```text
Fundamentals ──┐
Valuation ──────┼──> Investment Decision ──> BUY / HOLD / AVOID
Governance ─────┘
```

The system is designed to stop analysis when critical underlying data fails validation instead of generating a misleading investment conclusion.

### 📑 Automated Investment Reports

Generate structured research reports covering:
- Company overview
- Financial performance
- Fundamental quality
- Governance and corporate risk
- Valuation signals
- Investment decision
- Supporting metrics and findings

## 🧠 Analysis Philosophy

BSE Analyst Agent follows a **data-first, validation-first** approach.

```text
Market / Company Data
        ↓
Data Validation
        ↓
Financial Extraction
        ↓
Financial Analysis
        ↓
Governance Analysis
        ↓
Valuation
        ↓
Investment Decision
        ↓
Research Report
```

Missing, inconsistent, or suspicious financial data should be identified before it can distort the final analysis.

## 🏗️ Architecture

```text
bse-analyst-agent/
├── main.py
├── requirements.txt
├── src/
│   ├── nse_universe.py
│   ├── financial_analysis.py
│   ├── financial_tools.py
│   ├── financial_data_provider.py
│   ├── financial_doc_parser.py
│   ├── analysis_orchestrator.py
│   ├── corporate_risk.py
│   ├── nse_corporate_filings.py
│   ├── decision_engine.py
│   ├── report_generator.py
│   └── ...
└── tests/
```

The architecture is evolving as the financial-analysis and data pipelines are strengthened.

## 🔬 Research Pipeline

```text
Stock Universe
      ↓
Market Data
      ↓
Candidate Selection
      ↓
Financial Data / Annual Reports
      ↓
Financial Document Parsing
      ↓
Multi-Year Financial Analysis
      ↓
Corporate Governance Analysis
      ↓
Valuation Analysis
      ↓
Investment Decision Engine
      ↓
Investment Research Report
```

## ⚙️ Technology Stack

- **Python**
- **Pydantic** for structured data validation
- **Pandas** for data processing
- **Yahoo Finance / market-data sources**
- **NSE data sources**
- **Annual reports and corporate filings**
- **pytest** for automated testing
- **Git / GitHub** for version control

## 🧪 Testing

Run the complete test suite:

```bash
pytest
```

Run a specific test module:

```bash
pytest tests/test_nse_universe.py
```

## ▶️ Running the Project

Clone the repository:

```bash
git clone https://github.com/nirbhay-r-yadav/bse-analyst-agent.git
cd bse-analyst-agent
```

Create and activate a virtual environment on Windows:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Start the application:

```powershell
python main.py
```

## 🔎 Universe Scanning

The project supports large-scale stock-universe discovery and bulk quote processing.

Example:

```python
from src.nse_universe import NSEUniverse

universe = NSEUniverse(request_delay=0.25)
stocks = universe.discover(refresh=True)

print(f"Completed: {len(stocks)} stocks")
```

Performance optimization of large-universe scans is an active development area.

## 🛡️ Data Quality & Reliability

Financial analysis can become misleading when historical data is incomplete, incorrectly mapped to fiscal years, or unavailable from a source.

The project therefore emphasizes:

- Fiscal-year validation
- Missing-data detection
- Structured financial schemas
- Sanity checks
- Source validation
- Explicit failure handling
- Prevention of false investment conclusions

## 🗺️ Roadmap

### Current Development

- [x] Multi-year financial analysis
- [x] Corporate governance analysis
- [x] Investment decision engine
- [x] Automated investment reports
- [x] Large-universe stock discovery
- [x] Bulk quote processing
- [x] Financial data validation
- [ ] Improve universe-scan performance
- [ ] Strengthen fiscal-year extraction
- [ ] Improve structured financial-data providers
- [ ] Expand valuation analysis
- [ ] Improve automated research quality

### Future

- [ ] Portfolio-level analysis
- [ ] Historical backtesting
- [ ] Advanced valuation models
- [ ] Advanced stock ranking
- [ ] Performance tracking
- [ ] Interactive research dashboard
- [ ] Automated research alerts
- [ ] Additional Indian market data sources

## ⚠️ Disclaimer

BSE Analyst Agent is a **research and decision-support project**. It does not guarantee investment returns and is not a substitute for independent financial research or professional financial advice.

Investment decisions should be independently verified using official company filings, exchange disclosures, financial statements, and other reliable sources.

## 👨‍💻 Project

Developed by **Nirbhay Yadav**.

GitHub: https://github.com/nirbhay-r-yadav

Repository: https://github.com/nirbhay-r-yadav/bse-analyst-agent

## 📄 License

License information will be added as the project is prepared for broader distribution.
