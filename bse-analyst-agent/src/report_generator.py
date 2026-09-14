"""Presentation layer for the unified investment-analysis pipeline.

This module never calculates financial metrics or investment decisions. It reads
stage JSON artifacts produced by :class:`DeepScannerEngine` and turns them into
human-readable text and HTML reports.

Source of truth:
    corporate_governance.json
    financial_analysis.json
    investment_decision.json
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any


SECTION_LINE = "=" * 72


def _escape(value: Any) -> str:
    return html.escape(str(value))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _fmt(value: Any, default: str = "N/A") -> str:
    if value is None or value == "":
        return default
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _list_text(values: Any, empty: str = "None") -> list[str]:
    if not isinstance(values, list):
        return [empty]
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    return cleaned or [empty]


def _report_paths(output_dir: Path) -> tuple[Path, Path, Path]:
    return (
        output_dir / "corporate_governance.json",
        output_dir / "financial_analysis.json",
        output_dir / "investment_decision.json",
    )


def load_report_data(output_dir: str | Path) -> dict[str, Any]:
    """Load the structured stage artifacts for one stock."""
    directory = Path(output_dir)
    governance_file, financial_file, decision_file = _report_paths(directory)
    governance = _load_json(governance_file)
    financial = _load_json(financial_file)
    decision = _load_json(decision_file)
    symbol = (
        decision.get("symbol")
        or financial.get("symbol")
        or governance.get("symbol")
        or directory.name
    )
    return {
        "symbol": symbol,
        "governance": governance,
        "financial": financial,
        "decision": decision,
    }


def _report_values(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize the report sections without calculating new investment metrics."""
    governance = data["governance"]
    financial = data["financial"]
    decision = data["decision"]
    return {
        "governance": governance,
        "financial": financial,
        "decision": decision,
        "valuation": financial.get("valuation") or {},
        "ratios": financial.get("ratios") or {},
        "components": financial.get("financial_components") or {},
        "history": financial.get("history") or [],
        "ai": decision.get("ai") or {},
        "decision_components": decision.get("decision_components") or {},
        "verdict": decision.get("verdict") or "N/A",
    }


def generate_investment_text_report(
    output_dir: str | Path,
    output_file: str | None = None,
) -> str:
    """Generate the canonical human-readable text report from stage JSONs."""
    directory = Path(output_dir)
    data = load_report_data(directory)
    symbol = str(data["symbol"])
    governance = data["governance"]
    financial = data["financial"]
    decision = data["decision"]
    values = _report_values(data)

    if not governance and not financial and not decision:
        raise FileNotFoundError(f"No unified pipeline artifacts found in: {directory}")
    if output_file is None:
        output_file = str(directory / "investment_decision.txt")

    valuation = values["valuation"]
    ratios = values["ratios"]
    components = values["components"]
    history = values["history"]
    ai = values["ai"]
    decision_components = values["decision_components"]

    lines: list[str] = [
        "NSE EQUITY INVESTMENT REPORT",
        SECTION_LINE,
        f"Stock: {symbol}",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"VERDICT: {_fmt(decision.get('verdict'))}",
        f"DECISION SCORE: {_fmt(decision.get('decision_score'))}",
        f"FUNDAMENTAL SCORE: {_fmt(decision_components.get('fundamental_quality', financial.get('financial_score')))}",
        f"GOVERNANCE SCORE: {_fmt(decision_components.get('governance'))}",
        f"GOVERNANCE RISK SCORE: {_fmt(governance.get('risk_score'))}",
        f"GOVERNANCE GRADE: {_fmt(governance.get('governance_grade'))}",
        f"VALUATION SCORE: {_fmt(decision_components.get('valuation'))}",
        f"VALUATION STATE: {_fmt(decision.get('valuation_state'))}",
        "",
        SECTION_LINE,
        "CORPORATE GOVERNANCE",
        SECTION_LINE,
        f"Governance Grade: {_fmt(governance.get('governance_grade'))}",
        f"Risk Score: {_fmt(governance.get('risk_score'))}",
        f"Annual Report Score: {_fmt(governance.get('annual_report_score'))}",
        f"Reports Scanned: {_fmt(governance.get('reports_scanned'), '0')}",
        f"Hard Fail: {_fmt(governance.get('hard_fail'), 'False')}",
        "Risk Flags:",
    ]
    lines.extend(f"- {item}" for item in _list_text(governance.get("risk_flags")))
    lines.append("Positive Signals:")
    lines.extend(f"+ {item}" for item in _list_text(governance.get("positive_signals")))
    lines.append("Data Gaps:")
    lines.extend(f"- {item}" for item in _list_text(governance.get("data_gaps")))

    lines.extend(["", SECTION_LINE, "FINANCIAL ANALYSIS", SECTION_LINE,
                  f"Financial Score: {_fmt(financial.get('financial_score'))}"])
    for name, value in components.items():
        lines.append(f"{name}: {_fmt(value)}")

    lines.extend(["", SECTION_LINE, "FINANCIAL RATIOS", SECTION_LINE])
    for name, value in ratios.items():
        lines.append(f"{name}: {_fmt(value)}")

    lines.extend(["", SECTION_LINE, "FINANCIAL HISTORY USED", SECTION_LINE,
                  "Fiscal Year  Revenue  EBIT  PAT", "----------  -------  ----  ---"])
    for year in history:
        lines.append(
            f"{_fmt(year.get('fiscal_year'), year.get('year', 'N/A'))}  "
            f"{_fmt(year.get('revenue'))}  {_fmt(year.get('ebit'))}  {_fmt(year.get('pat'))}"
        )
    if not history:
        lines.append("No structured financial history available.")

    lines.extend(["", SECTION_LINE, "VALUATION", SECTION_LINE,
                  f"Available: {_fmt(valuation.get('available'), 'False')}",
                  f"Fair Value: {_fmt(valuation.get('fair_value'))}",
                  f"Buy Below: {_fmt(valuation.get('buy_below'))}",
                  f"Reason: {_fmt(valuation.get('reason'))}",
                  f"Decision Score: {_fmt(decision_components.get('valuation'))}",
                  f"Decision State: {_fmt(decision.get('valuation_state'))}"])

    lines.extend(["", SECTION_LINE, "FINAL INVESTMENT DECISION", SECTION_LINE,
                  f"VERDICT: {_fmt(decision.get('verdict'))}",
                  f"DECISION SCORE: {_fmt(decision.get('decision_score'))}",
                  "REASON", _fmt(decision.get("reason"), "No decision reason available."),
                  "", SECTION_LINE, "AI INVESTMENT THESIS", SECTION_LINE,
                  f"Conviction Score: {_fmt(ai.get('conviction_score'))}",
                  "Executive Summary:", _fmt(ai.get("thesis"), "No qualitative thesis available."), ""])

    annual_audits = governance.get("annual_report_audits") or []
    lines.extend([SECTION_LINE, "ANNUAL REPORT FORENSIC FINDINGS", SECTION_LINE])
    if annual_audits:
        for audit in annual_audits:
            lines.extend([
                f"Fiscal Year: {_fmt(audit.get('fiscal_year'))}",
                f"Audit Opinion: {_fmt(audit.get('audit_opinion_type'))}",
                f"Contingent Liability Risk: {_fmt(audit.get('contingent_liability_risk'))}",
                f"Related Party Risk: {_fmt(audit.get('related_party_risk'))}",
                "Forensic Red Flags:",
            ])
            lines.extend(f"- {item}" for item in _list_text(audit.get("forensic_red_flags")))
            lines.append("")
    else:
        lines.append("No annual report forensic audit data available.")

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    Path(output_file).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return str(output_file)


def _score_class(value: Any) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "neutral"
    if score >= 60:
        return "positive"
    if score >= 40:
        return "warning"
    return "negative"


def _verdict_class(verdict: Any) -> str:
    value = str(verdict or "").upper()
    return {"BUY": "buy", "WATCHLIST": "watchlist", "AVOID": "avoid"}.get(value, "neutral")


def _risk_class(value: Any) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "neutral"
    if score <= 3:
        return "positive"
    if score <= 6:
        return "warning"
    return "negative"


def _list_html(values: Any, empty: str) -> str:
    return "".join(f'<li>{_escape(item)}</li>' for item in _list_text(values, empty))


def _kv_rows(values: dict[str, Any]) -> str:
    return "".join(
        f'<div class="kv"><span>{_escape(name)}</span><strong>{_escape(_fmt(value))}</strong></div>'
        for name, value in values.items()
    )


def generate_investment_report(
    report_source: str,
    output_file: str | None = None,
) -> str:
    """Generate the HTML dashboard directly from unified stage JSON artifacts.

    Passing ``investment_decision.txt`` remains supported for compatibility;
    the text report is never parsed for financial values.
    """
    source = Path(report_source)
    output_dir = source if source.is_dir() else source.parent
    data = load_report_data(output_dir)
    if not any(data[key] for key in ("governance", "financial", "decision")):
        raise FileNotFoundError(f"No unified pipeline artifacts found in: {output_dir}")

    symbol = str(data["symbol"])
    governance = data["governance"]
    financial = data["financial"]
    decision = data["decision"]
    values = _report_values(data)
    valuation = values["valuation"]
    ratios = values["ratios"]
    components = values["components"]
    history = values["history"]
    ai = values["ai"]
    decision_components = values["decision_components"]
    verdict = values["verdict"]

    if output_file is None:
        output_file = str(output_dir / "investment_report.html")

    score_items = [
        ("Decision", decision.get("decision_score")),
        ("Fundamentals", decision_components.get("fundamental_quality", financial.get("financial_score"))),
        ("Governance", decision_components.get("governance")),
        ("Valuation", decision_components.get("valuation")),
    ]
    score_cards = "".join(
        f'<div class="score-card"><div class="score-label">{_escape(name)}</div>'
        f'<div class="score-value {_score_class(value)}">{_escape(_fmt(value))}</div></div>'
        for name, value in score_items
    )

    overview_cards = "".join([
        f'<div class="metric"><span>Fair value</span><strong>{_escape(_fmt(valuation.get("fair_value")))}</strong></div>',
        f'<div class="metric"><span>Buy below</span><strong>{_escape(_fmt(valuation.get("buy_below")))}</strong></div>',
        f'<div class="metric"><span>Reports scanned</span><strong>{_escape(_fmt(governance.get("reports_scanned"), "0"))}</strong></div>',
        f'<div class="metric"><span>Conviction</span><strong>{_escape(_fmt(ai.get("conviction_score")))}</strong></div>',
    ])

    history_rows = "".join(
        "<tr>"
        f"<td>{_escape(year.get('fiscal_year', 'N/A'))}</td>"
        f"<td>{_escape(_fmt(year.get('revenue')))}</td>"
        f"<td>{_escape(_fmt(year.get('ebit')))}</td>"
        f"<td>{_escape(_fmt(year.get('pat')))}</td>"
        "</tr>"
        for year in history
    ) or '<tr><td colspan="4">No structured financial history available.</td></tr>'

    ratio_rows = "".join(
        f"<tr><td>{_escape(name)}</td><td>{_escape(_fmt(value))}</td></tr>"
        for name, value in ratios.items()
    ) or '<tr><td colspan="2">No ratios available.</td></tr>'

    component_cards = "".join(
        f'<div class="component"><span>{_escape(name)}</span><strong>{_escape(_fmt(value))}</strong></div>'
        for name, value in components.items()
    ) or '<div class="empty">No financial components available.</div>'

    audits_html = ""
    for audit in governance.get("annual_report_audits") or []:
        audits_html += f"""
        <details class="audit-card">
          <summary><strong>{_escape(audit.get('fiscal_year', 'Unknown'))}</strong><span>{_escape(audit.get('audit_opinion_type', 'N/A'))}</span></summary>
          <div class="audit-body">
            <p><b>Contingent liability risk:</b> {_escape(audit.get('contingent_liability_risk', 'N/A'))}</p>
            <p><b>Related-party risk:</b> {_escape(audit.get('related_party_risk', 'N/A'))}</p>
            <b>Forensic red flags</b>
            <ul>{_list_html(audit.get('forensic_red_flags'), 'None')}</ul>
          </div>
        </details>
        """
    audits_html = audits_html or '<div class="empty">No annual report forensic audit data available.</div>'

    verdict_css = _verdict_class(verdict)
    html_document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_escape(symbol)} Investment Report</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;background:#0b1020;color:#e5e7eb;font-family:Inter,Segoe UI,Arial,sans-serif;line-height:1.55}} .container{{max-width:1240px;margin:auto;padding:34px 22px 64px}} .header{{display:flex;justify-content:space-between;gap:24px;align-items:flex-start}} .brand{{color:#94a3b8;text-transform:uppercase;letter-spacing:3px;font-size:12px}} h1{{font-size:44px;line-height:1.1;margin:8px 0}} h2{{margin:38px 0 14px;border-bottom:1px solid #334155;padding-bottom:9px;font-size:23px}} .subtitle{{color:#94a3b8}} .verdict{{min-width:170px;padding:18px 28px;border-radius:16px;text-align:center;border:1px solid #334155;font-size:27px;font-weight:800}} .verdict.buy{{background:#12351f}} .verdict.watchlist{{background:#3b3010}} .verdict.avoid{{background:#3b1717}} .verdict.neutral{{background:#1e293b}} .score-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:26px 0 16px}} .score-card,.metric,.component,.audit-card,.panel{{background:#111827;border:1px solid #263244;border-radius:14px;padding:17px}} .score-label,.metric span,.kv span{{color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:.7px}} .score-value{{font-size:28px;font-weight:800;margin-top:5px}} .positive{{color:#86efac}} .warning{{color:#fde68a}} .negative{{color:#fca5a5}} .neutral{{color:#cbd5e1}} .overview{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}} .metric strong{{display:block;font-size:20px;margin-top:5px}} .two{{display:grid;grid-template-columns:1fr 1fr;gap:18px}} .component-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}} .component{{display:flex;justify-content:space-between;gap:16px}} .kv-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px 22px}} .kv{{display:flex;justify-content:space-between;border-bottom:1px solid #263244;padding:8px 0;gap:12px}} .panel h3{{margin-top:0}} table{{width:100%;border-collapse:collapse;background:#111827;border-radius:14px;overflow:hidden}} th,td{{padding:11px 13px;border-bottom:1px solid #263244;text-align:left}} th{{color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:.6px}} .thesis{{white-space:pre-wrap;background:#111827;border:1px solid #263244;border-radius:14px;padding:20px;font-size:16px}} .audit-card{{margin-bottom:10px}} .audit-card summary{{cursor:pointer;display:flex;justify-content:space-between;gap:16px}} .audit-card summary span{{color:#94a3b8}} .audit-body{{padding-top:10px}} ul{{padding-left:22px}} .empty{{color:#94a3b8;padding:8px 0}} .hard-fail{{font-weight:800}} .muted{{color:#94a3b8}} @media print{{body{{background:#fff;color:#111827}} .score-card,.metric,.component,.audit-card,.panel,.thesis,table{{background:#fff;border-color:#d1d5db}} .positive,.warning,.negative,.neutral{{color:#111827}}}} @media(max-width:800px){{.header,.two{{display:block}} .verdict{{margin-top:20px}} .score-grid,.overview,.component-grid{{grid-template-columns:1fr 1fr}} .kv-grid{{grid-template-columns:1fr}}}} @media(max-width:520px){{.score-grid,.overview,.component-grid{{grid-template-columns:1fr}} h1{{font-size:36px}}}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div><div class="brand">NSE Equity Research Agent</div><h1>{_escape(symbol)}</h1><div class="subtitle">Unified pipeline report · Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div></div>
    <div class="verdict {verdict_css}">{_escape(verdict)}</div>
  </div>

  <div class="score-grid">{score_cards}</div>
  <div class="overview">{overview_cards}</div>

  <h2>Final Investment Decision</h2>
  <div class="panel">
    <div class="kv-grid">{_kv_rows({
        "Decision score": decision.get("decision_score"),
        "Fundamental score": decision_components.get("fundamental_quality", financial.get("financial_score")),
        "Governance score": decision_components.get("governance"),
        "Valuation score": decision_components.get("valuation"),
        "Valuation state": decision.get("valuation_state"),
        "Hard fail": governance.get("hard_fail"),
    })}</div>
    <p><b>Reason:</b> {_escape(_fmt(decision.get('reason'), 'No decision reason available.'))}</p>
  </div>

  <h2>Corporate Governance</h2>
  <div class="two">
    <div class="panel">
      <div class="kv-grid">{_kv_rows({
          "Grade": governance.get("governance_grade"),
          "Risk score": governance.get("risk_score"),
          "Decision score": decision_components.get("governance"),
          "Annual-report score": governance.get("annual_report_score"),
          "Reports scanned": governance.get("reports_scanned"),
          "Hard fail": governance.get("hard_fail"),
      })}</div>
    </div>
    <div class="panel"><b>Risk flags</b><ul>{_list_html(governance.get('risk_flags'), 'No governance risk flags recorded.')}</ul></div>
  </div>
  <div class="two" style="margin-top:18px">
    <div class="panel"><b>Positive signals</b><ul>{_list_html(governance.get('positive_signals'), 'No positive governance signals recorded.')}</ul></div>
    <div class="panel"><b>Data gaps</b><ul>{_list_html(governance.get('data_gaps'), 'No data gaps recorded.')}</ul></div>
  </div>

  <h2>Financial Analysis</h2>
  <div class="component-grid">{component_cards}</div>

  <h2>Financial Ratios</h2>
  <table><thead><tr><th>Ratio</th><th>Value</th></tr></thead><tbody>{ratio_rows}</tbody></table>

  <h2>Financial History Used</h2>
  <table><thead><tr><th>Fiscal Year</th><th>Revenue</th><th>EBIT</th><th>PAT</th></tr></thead><tbody>{history_rows}</tbody></table>
  <p class="muted">Only structured history present in the financial stage artifact is displayed; missing years or values are not substituted.</p>

  <h2>Valuation</h2>
  <div class="panel">
    <div class="kv-grid">{_kv_rows({
        "Available": valuation.get("available"),
        "Fair value": valuation.get("fair_value"),
        "Buy below": valuation.get("buy_below"),
        "Decision score": decision_components.get("valuation"),
        "Decision state": decision.get("valuation_state"),
    })}</div>
    <p><b>Reason:</b> {_escape(_fmt(valuation.get('reason')))}</p>
  </div>

  <h2>AI Investment Thesis</h2>
  <div class="thesis"><b>Conviction score:</b> {_escape(_fmt(ai.get('conviction_score')))}<br><br>{_escape(_fmt(ai.get('thesis'), 'No qualitative thesis available.'))}</div>

  <h2>Annual Report Forensic Findings</h2>
  {audits_html}
</div>
</body>
</html>
"""

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    Path(output_file).write_text(html_document, encoding="utf-8")
    return str(output_file)
