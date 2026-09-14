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


def _fmt_pct(value: Any) -> str:
    if value is None or value == "":
        return "N/A"
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
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

    if not governance and not financial and not decision:
        raise FileNotFoundError(
            f"No unified pipeline artifacts found in: {directory}"
        )

    if output_file is None:
        output_file = str(directory / "investment_decision.txt")

    valuation = financial.get("valuation") or {}
    ratios = financial.get("ratios") or {}
    components = financial.get("financial_components") or {}
    history = financial.get("history") or []
    ai = decision.get("ai") or {}

    lines: list[str] = [
        "NSE EQUITY INVESTMENT REPORT",
        SECTION_LINE,
        f"Stock: {symbol}",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"VERDICT: {_fmt(decision.get('verdict'))}",
        f"DECISION SCORE: {_fmt(decision.get('decision_score'))}",
        f"FUNDAMENTAL SCORE: {_fmt(financial.get('financial_score'))}",
        f"GOVERNANCE SCORE: {_fmt(governance.get('risk_score'))}",
        f"GOVERNANCE GRADE: {_fmt(governance.get('governance_grade'))}",
        f"VALUATION SCORE: {_fmt(decision.get('valuation_score'))}",
        f"VALUATION STATE: {_fmt(valuation.get('state') or valuation.get('reason'))}",
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

    lines.extend([
        "",
        SECTION_LINE,
        "FINANCIAL ANALYSIS",
        SECTION_LINE,
        f"Financial Score: {_fmt(financial.get('financial_score'))}",
    ])
    for name, value in components.items():
        lines.append(f"{name}: {_fmt(value)}")

    lines.extend([
        "",
        SECTION_LINE,
        "FINANCIAL RATIOS",
        SECTION_LINE,
    ])
    for name, value in ratios.items():
        lines.append(f"{name}: {_fmt(value)}")

    lines.extend([
        "",
        SECTION_LINE,
        "FINANCIAL HISTORY USED",
        SECTION_LINE,
        "Fiscal Year  Revenue  EBIT  PAT",
        "----------  -------  ----  ---",
    ])
    for year in history:
        lines.append(
            f"{_fmt(year.get('fiscal_year'), year.get('year', 'N/A'))}  "
            f"{_fmt(year.get('revenue'))}  "
            f"{_fmt(year.get('ebit'))}  "
            f"{_fmt(year.get('pat'))}"
        )
    if not history:
        lines.append("No structured financial history available.")

    lines.extend([
        "",
        SECTION_LINE,
        "VALUATION",
        SECTION_LINE,
        f"Available: {_fmt(valuation.get('available'), 'False')}",
        f"Fair Value: {_fmt(valuation.get('fair_value'))}",
        f"Buy Below: {_fmt(valuation.get('buy_below'))}",
        f"Reason: {_fmt(valuation.get('reason'))}",
        "",
        SECTION_LINE,
        "FINAL INVESTMENT DECISION",
        SECTION_LINE,
        f"VERDICT: {_fmt(decision.get('verdict'))}",
        f"DECISION SCORE: {_fmt(decision.get('decision_score'))}",
        f"REASON",
        _fmt(decision.get("reason"), "No decision reason available."),
        "",
        SECTION_LINE,
        "AI INVESTMENT THESIS",
        SECTION_LINE,
        f"Conviction Score: {_fmt(ai.get('conviction_score'))}",
        "Executive Summary:",
        _fmt(ai.get("thesis"), "No qualitative thesis available."),
        "",
    ])

    annual_audits = governance.get("annual_report_audits") or []
    lines.extend([
        SECTION_LINE,
        "ANNUAL REPORT FORENSIC FINDINGS",
        SECTION_LINE,
    ])
    if annual_audits:
        for audit in annual_audits:
            lines.extend([
                f"Fiscal Year: {_fmt(audit.get('fiscal_year'))}",
                f"Audit Opinion: {_fmt(audit.get('audit_opinion_type'))}",
                f"Contingent Liability Risk: {_fmt(audit.get('contingent_liability_risk'))}",
                f"Related Party Risk: {_fmt(audit.get('related_party_risk'))}",
                "Forensic Red Flags:",
            ])
            lines.extend(
                f"- {item}"
                for item in _list_text(audit.get("forensic_red_flags"))
            )
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
    if value == "BUY":
        return "buy"
    if value == "WATCHLIST":
        return "watchlist"
    if value == "AVOID":
        return "avoid"
    return "neutral"


def _list_html(values: Any, empty: str) -> str:
    items = _list_text(values, empty)
    return "".join(f'<li>{_escape(item)}</li>' for item in items)


def generate_investment_report(
    report_source: str,
    output_file: str | None = None,
) -> str:
    """Generate HTML directly from the unified pipeline JSON artifacts.

    ``report_source`` should normally be ``outputs/<SYMBOL>``. For backward
    compatibility, passing ``investment_decision.txt`` resolves its parent
    directory; the text file itself is never parsed for financial values.
    """
    source = Path(report_source)
    output_dir = source if source.is_dir() else source.parent
    data = load_report_data(output_dir)

    if not any(data[key] for key in ("governance", "financial", "decision")):
        raise FileNotFoundError(
            f"No unified pipeline artifacts found in: {output_dir}"
        )

    symbol = str(data["symbol"])
    governance = data["governance"]
    financial = data["financial"]
    decision = data["decision"]
    valuation = financial.get("valuation") or {}
    ratios = financial.get("ratios") or {}
    components = financial.get("financial_components") or {}
    history = financial.get("history") or []
    ai = decision.get("ai") or {}
    verdict = decision.get("verdict") or "N/A"

    if output_file is None:
        output_file = str(output_dir / "investment_report.html")

    score_items = [
        ("Decision", decision.get("decision_score")),
        ("Fundamentals", financial.get("financial_score")),
        ("Governance", governance.get("risk_score")),
        ("Valuation", decision.get("valuation_score")),
    ]
    score_cards = "".join(
        f'<div class="score-card"><div class="score-label">{_escape(name)}</div>'
        f'<div class="score-value {_score_class(value)}">{_escape(_fmt(value))}</div></div>'
        for name, value in score_items
    )

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
        <div class="audit-card">
          <h3>{_escape(audit.get('fiscal_year', 'Unknown'))}</h3>
          <p><b>Audit opinion:</b> {_escape(audit.get('audit_opinion_type', 'N/A'))}</p>
          <p><b>Contingent liability risk:</b> {_escape(audit.get('contingent_liability_risk', 'N/A'))}</p>
          <p><b>Related-party risk:</b> {_escape(audit.get('related_party_risk', 'N/A'))}</p>
          <b>Forensic red flags</b>
          <ul>{_list_html(audit.get('forensic_red_flags'), 'None')}</ul>
        </div>
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
*{{box-sizing:border-box}} body{{margin:0;background:#0b1020;color:#e5e7eb;font-family:Inter,Segoe UI,Arial,sans-serif;line-height:1.5}} .container{{max-width:1200px;margin:auto;padding:36px 22px 60px}} .header{{display:flex;justify-content:space-between;gap:24px;align-items:flex-start}} .brand{{color:#94a3b8;text-transform:uppercase;letter-spacing:3px;font-size:13px}} h1{{font-size:42px;margin:8px 0}} h2{{margin-top:34px;border-bottom:1px solid #334155;padding-bottom:8px}} .subtitle{{color:#94a3b8}} .verdict{{padding:22px 30px;border-radius:16px;text-align:center;border:1px solid #334155;font-size:28px;font-weight:800}} .verdict.buy{{background:#12351f}} .verdict.watchlist{{background:#3b3010}} .verdict.avoid{{background:#3b1717}} .verdict.neutral{{background:#1e293b}} .score-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:28px 0}} .score-card,.component,.audit-card,.panel{{background:#111827;border:1px solid #263244;border-radius:14px;padding:18px}} .score-label{{color:#94a3b8;font-size:13px}} .score-value{{font-size:27px;font-weight:800;margin-top:5px}} .positive{{color:#86efac}} .warning{{color:#fde68a}} .negative{{color:#fca5a5}} .neutral{{color:#cbd5e1}} .component-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}} .component{{display:flex;justify-content:space-between;gap:16px}} table{{width:100%;border-collapse:collapse;background:#111827;border-radius:14px;overflow:hidden}} th,td{{padding:11px 13px;border-bottom:1px solid #263244;text-align:left}} th{{color:#94a3b8}} .two{{display:grid;grid-template-columns:1fr 1fr;gap:18px}} ul{{padding-left:22px}} .empty{{color:#94a3b8;padding:8px 0}} .thesis{{white-space:pre-wrap;background:#111827;border:1px solid #263244;border-radius:14px;padding:20px}} @media(max-width:800px){{.header,.two{{display:block}} .verdict{{margin-top:20px}} .score-grid{{grid-template-columns:1fr 1fr}} .component-grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div><div class="brand">NSE Equity Research Agent</div><h1>{_escape(symbol)}</h1><div class="subtitle">Generated from unified pipeline stage artifacts</div></div>
    <div class="verdict {verdict_css}">{_escape(verdict)}</div>
  </div>

  <div class="score-grid">{score_cards}</div>

  <h2>Final Investment Decision</h2>
  <div class="panel">
    <p><b>Decision score:</b> {_escape(_fmt(decision.get('decision_score')))}</p>
    <p><b>Reason:</b> {_escape(_fmt(decision.get('reason'), 'No decision reason available.'))}</p>
    <p><b>Valuation state:</b> {_escape(_fmt(valuation.get('state') or valuation.get('reason')))}</p>
  </div>

  <h2>Corporate Governance</h2>
  <div class="two">
    <div class="panel">
      <p><b>Grade:</b> {_escape(_fmt(governance.get('governance_grade')))}</p>
      <p><b>Risk score:</b> {_escape(_fmt(governance.get('risk_score')))}</p>
      <p><b>Annual-report score:</b> {_escape(_fmt(governance.get('annual_report_score')))}</p>
      <p><b>Reports scanned:</b> {_escape(_fmt(governance.get('reports_scanned'), '0'))}</p>
      <p><b>Hard fail:</b> {_escape(_fmt(governance.get('hard_fail'), 'False'))}</p>
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

  <h2>Valuation</h2>
  <div class="panel">
    <p><b>Available:</b> {_escape(_fmt(valuation.get('available'), 'False'))}</p>
    <p><b>Fair value:</b> {_escape(_fmt(valuation.get('fair_value')))}</p>
    <p><b>Buy below:</b> {_escape(_fmt(valuation.get('buy_below')))}</p>
    <p><b>Reason:</b> {_escape(_fmt(valuation.get('reason')))}</p>
  </div>

  <h2>AI Investment Thesis</h2>
  <div class="thesis"><b>Conviction score:</b> {_escape(_fmt(ai.get('conviction_score')))}\n\n{_escape(_fmt(ai.get('thesis'), 'No qualitative thesis available.'))}</div>

  <h2>Annual Report Forensic Findings</h2>
  {audits_html}
</div>
</body>
</html>
"""

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    Path(output_file).write_text(html_document, encoding="utf-8")
    return str(output_file)
