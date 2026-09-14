"""Presentation layer for the unified investment-analysis pipeline.

This module is deliberately read-only with respect to analysis. It reads the
persisted JSON stage artifacts and formats them for humans. It does not
recalculate financial metrics or investment decisions.

Sources of truth:
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
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


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
    """Load only persisted JSON artifacts for one stock."""
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
    financial = data["financial"]
    decision = data["decision"]
    return {
        "governance": data["governance"],
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
    """Generate the human-readable investment report from stage JSONs."""
    directory = Path(output_dir)
    data = load_report_data(directory)
    if not any(data[key] for key in ("governance", "financial", "decision")):
        raise FileNotFoundError(f"No unified pipeline artifacts found in: {directory}")

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

    if output_file is None:
        output_file = str(directory / "investment_decision.txt")

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

    lines.extend(["", SECTION_LINE, "FINANCIAL ANALYSIS", SECTION_LINE])
    lines.append(f"Financial Score: {_fmt(financial.get('financial_score'))}")
    if components:
        lines.extend(f"{name}: {_fmt(value)}" for name, value in components.items())
    else:
        lines.append("No financial components recorded.")

    lines.extend(["", SECTION_LINE, "FINANCIAL RATIOS", SECTION_LINE])
    if ratios:
        for name, value in ratios.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{name}: {json.dumps(value, ensure_ascii=False, default=str)}")
            else:
                lines.append(f"{name}: {_fmt(value)}")
    else:
        lines.append("No financial ratios recorded.")

    lines.extend(["", SECTION_LINE, "FINANCIAL HISTORY", SECTION_LINE])
    if history:
        for year in history:
            if not isinstance(year, dict):
                continue
            lines.extend([
                f"Fiscal Year: {_fmt(year.get('fiscal_year'), year.get('year', 'N/A'))}",
                f"Revenue: {_fmt(year.get('revenue'))}",
                f"EBIT: {_fmt(year.get('ebit'))}",
                f"PAT: {_fmt(year.get('pat'))}",
                "",
            ])
    else:
        lines.append("No structured financial history recorded.")

    lines.extend(["", SECTION_LINE, "VALUATION", SECTION_LINE])
    for name, value in valuation.items():
        if isinstance(value, (dict, list)):
            lines.append(f"{name}: {json.dumps(value, ensure_ascii=False, default=str)}")
        else:
            lines.append(f"{name}: {_fmt(value)}")

    lines.extend([
        "", SECTION_LINE, "FINAL INVESTMENT DECISION", SECTION_LINE,
        f"VERDICT: {_fmt(decision.get('verdict'))}",
        f"DECISION SCORE: {_fmt(decision.get('decision_score'))}",
        "REASON",
        _fmt(decision.get("reason"), "No decision reason available."),
        "", SECTION_LINE, "AI INVESTMENT THESIS", SECTION_LINE,
        f"Conviction Score: {_fmt(ai.get('conviction_score'))}",
        "Executive Summary:",
        _fmt(ai.get("thesis"), "No qualitative thesis available."),
    ])

    annual_audits = governance.get("annual_report_audits") or []
    lines.extend(["", SECTION_LINE, "ANNUAL REPORT FORENSIC FINDINGS", SECTION_LINE])
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
    return {
        "BUY": "buy",
        "WATCHLIST": "watchlist",
        "AVOID": "avoid",
    }.get(str(verdict or "").upper(), "neutral")


def _list_html(values: Any, empty: str) -> str:
    return "".join(f"<li>{_escape(item)}</li>" for item in _list_text(values, empty))


def _kv_rows(values: dict[str, Any]) -> str:
    return "".join(
        f'<div class="kv"><span>{_escape(name)}</span><strong>{_escape(_fmt(value))}</strong></div>'
        for name, value in values.items()
    )


def _ratio_groups(ratios: dict[str, Any]) -> list[tuple[str, list[tuple[str, Any]]]]:
    """Group persisted ratio keys for presentation; no values are recalculated."""
    groups = {
        "Returns & capital efficiency": ["ROCE (%)", "Average ROCE (%)", "Minimum ROCE (%)", "Maximum ROCE (%)", "ROE (%)", "Average ROE (%)", "Minimum ROE (%)", "Maximum ROE (%)"],
        "Growth": ["Revenue YoY Growth (%)", "PAT YoY Growth (%)", "Revenue CAGR (%)", "PAT CAGR (%)", "Revenue CAGR 3Y (%)", "Revenue CAGR 5Y (%)", "Revenue CAGR 10Y (%)"],
        "Profitability": ["Latest PAT Margin (%)", "Average PAT Margin (%)", "Minimum PAT Margin (%)", "Maximum PAT Margin (%)", "PAT Margin Range (pp)", "PAT Margin YoY Change (pp)", "PAT Margin Trend"],
        "Balance sheet & cash": ["Debt to Equity", "Net Debt (Cr)", "Interest Coverage Ratio", "CFO / PAT Quality Ratio", "Average CFO / PAT (Available History)", "Positive CFO Years", "CFO Positive Ratio (%)"],
        "Trend & coverage": ["years_analyzed", "history_years_available", "latest_fiscal_year", "ROCE YoY Change (pp)", "ROCE Trend", "ROE YoY Change (pp)", "ROE Trend"],
    }
    result: list[tuple[str, list[tuple[str, Any]]]] = []
    used: set[str] = set()
    for title, keys in groups.items():
        rows = [(key, ratios[key]) for key in keys if key in ratios]
        if rows:
            result.append((title, rows))
            used.update(key for key, _ in rows)
    remaining = [(key, value) for key, value in ratios.items() if key not in used and not isinstance(value, (dict, list))]
    if remaining:
        result.append(("Other persisted ratios", remaining))
    return result


def _history_cell(value: Any) -> str:
    return _escape(_fmt(value, "—"))


def _history_rows(history: list[Any], ratios: dict[str, Any]) -> str:
    roce_history = ratios.get("ROCE History (%)") or {}
    roe_history = ratios.get("ROE History (%)") or {}
    margin_history = ratios.get("PAT Margin History (%)") or {}
    rows: list[str] = []
    for year in history:
        if not isinstance(year, dict):
            continue
        fy = str(year.get("fiscal_year") or year.get("year") or "N/A")
        rows.append(
            "<tr>"
            f"<td class=\"year\">{_escape(fy)}</td>"
            f"<td>{_history_cell(year.get('revenue'))}</td>"
            f"<td>{_history_cell(year.get('ebit'))}</td>"
            f"<td>{_history_cell(year.get('pat'))}</td>"
            f"<td>{_history_cell(roce_history.get(fy))}</td>"
            f"<td>{_history_cell(roe_history.get(fy))}</td>"
            f"<td>{_history_cell(margin_history.get(fy))}</td>"
            "</tr>"
        )
    return "".join(rows) or '<tr><td colspan="7" class="empty">No structured financial history available.</td></tr>'


def _full_history_cards(history: list[Any]) -> str:
    """Expose every persisted annual field without pretending missing data exists."""
    cards: list[str] = []
    for year in history:
        if not isinstance(year, dict):
            continue
        fy = str(year.get("fiscal_year") or year.get("year") or "N/A")
        fields = [
            ("Revenue (Cr)", year.get("revenue")),
            ("EBIT (Cr)", year.get("ebit")),
            ("PAT (Cr)", year.get("pat")),
            ("Debt (Cr)", year.get("total_debt")),
            ("Equity (Cr)", year.get("total_equity")),
            ("Cash & equivalents (Cr)", year.get("cash_equivalents")),
            ("CFO (Cr)", year.get("cfo")),
            ("Interest expense (Cr)", year.get("interest_expense")),
            ("Capex (Cr)", year.get("capex")),
        ]
        cards.append(
            f'<details class="history-detail"><summary>{_escape(fy)}<span>Annual financial inputs</span></summary>'
            f'<div class="history-grid">{_kv_rows(dict(fields))}</div></details>'
        )
    return "".join(cards) or '<div class="empty">No structured annual financial inputs available.</div>'


def _governance_html(governance: dict[str, Any]) -> str:
    audits = governance.get("annual_report_audits") or []
    audit_blocks: list[str] = []
    for audit in audits:
        audit_blocks.append(
            f'''<details class="gov-year">
            <summary><span class="fy">{_escape(audit.get('fiscal_year', 'Unknown'))}</span>
            <span>Audit: {_escape(audit.get('audit_opinion_type', 'N/A'))}</span>
            <span>RPT risk: {_escape(audit.get('related_party_risk', 'N/A'))}</span></summary>
            <div class="gov-year-body"><div class="gov-grid">
            <div class="evidence"><h4>What happened</h4><p>{_escape(audit.get('what_happened', 'Not available'))}</p></div>
            <div class="evidence"><h4>Why it matters</h4><p>{_escape(audit.get('why_it_matters', 'Not available'))}</p></div>
            <div class="evidence"><h4>Auditor observations</h4><ul>{_list_html(audit.get('auditor_observations'), 'None')}</ul></div>
            <div class="evidence"><h4>Key audit matters</h4><ul>{_list_html(audit.get('key_audit_matters'), 'None')}</ul></div>
            <div class="evidence"><h4>Related-party transactions</h4><ul>{_list_html(audit.get('related_party_transactions'), 'None')}</ul></div>
            <div class="evidence"><h4>Loans / guarantees / investments</h4><ul>{_list_html(audit.get('loans_guarantees_investments'), 'None')}</ul></div>
            <div class="evidence"><h4>Contingent liabilities</h4><ul>{_list_html(audit.get('contingent_liabilities'), 'None')}</ul></div>
            <div class="evidence"><h4>Remuneration</h4><ul>{_list_html(audit.get('remuneration_details'), 'None')}</ul></div>
            <div class="evidence"><h4>Regulatory compliance</h4><ul>{_list_html(audit.get('regulatory_compliance_events'), 'None')}</ul></div>
            <div class="evidence red"><h4>Forensic red flags</h4><ul>{_list_html(audit.get('forensic_red_flags'), 'None')}</ul></div>
            <div class="evidence full"><h4>Governance conclusion</h4><p>{_escape(audit.get('governance_conclusion', 'Not available'))}</p></div>
            </div></div></details>'''
        )
    return f'''<section id="governance"><div class="section-head"><div><div class="eyebrow">03 · Governance</div><h2>Corporate Governance</h2><p>Governance evidence is rendered directly from <code>corporate_governance.json</code>.</p></div></div>
    <div class="stat-grid five">
      <div class="stat"><span>Grade</span><strong>{_escape(_fmt(governance.get('governance_grade')))}</strong></div>
      <div class="stat"><span>Risk score</span><strong>{_escape(_fmt(governance.get('risk_score')))}</strong></div>
      <div class="stat"><span>Annual report score</span><strong>{_escape(_fmt(governance.get('annual_report_score')))}</strong></div>
      <div class="stat"><span>Reports scanned</span><strong>{_escape(_fmt(governance.get('reports_scanned'), '0'))} / 10</strong></div>
      <div class="stat"><span>Hard fail</span><strong>{_escape(_fmt(governance.get('hard_fail'), 'False'))}</strong></div>
    </div>
    <div class="two-col">
      <div class="panel danger"><h3>Risk flags</h3><ul>{_list_html(governance.get('risk_flags'), 'No governance risk flags recorded.')}</ul></div>
      <div class="panel success"><h3>Positive signals</h3><ul>{_list_html(governance.get('positive_signals'), 'No positive governance signals recorded.')}</ul></div>
    </div>
    <div class="panel caution"><h3>Data availability</h3><ul>{_list_html(governance.get('data_gaps'), 'No data gaps recorded.')}</ul></div>
    <h3 class="subhead">Annual report forensics</h3><div class="gov-years">{''.join(audit_blocks) or '<div class="empty">No annual report forensic audit data available.</div>'}</div></section>'''


def generate_investment_report(report_source: str, output_file: str | None = None) -> str:
    """Generate the existing HTML dashboard from persisted stage JSONs."""
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
        f'<div class="score-card"><span>{_escape(name)}</span><strong class="{_score_class(value)}">{_escape(_fmt(value))}</strong></div>'
        for name, value in score_items
    )

    latest = history[-1] if history and isinstance(history[-1], dict) else {}
    financial_hero = "".join([
        f'<div class="stat"><span>Financial score</span><strong>{_escape(_fmt(financial.get("financial_score")))}</strong></div>',
        f'<div class="stat"><span>Latest FY</span><strong>{_escape(_fmt(ratios.get("latest_fiscal_year"), latest.get("fiscal_year", "N/A")))}</strong></div>',
        f'<div class="stat"><span>Revenue (Cr)</span><strong>{_escape(_fmt(latest.get("revenue")))}</strong></div>',
        f'<div class="stat"><span>PAT (Cr)</span><strong>{_escape(_fmt(latest.get("pat")))}</strong></div>',
        f'<div class="stat"><span>ROCE</span><strong>{_escape(_fmt(ratios.get("ROCE (%)")))}</strong></div>',
        f'<div class="stat"><span>ROE</span><strong>{_escape(_fmt(ratios.get("ROE (%)")))}</strong></div>',
    ])

    component_cards = "".join(
        f'<div class="component"><span>{_escape(name.replace("_", " ").title())}</span><strong>{_escape(_fmt(value))}</strong></div>'
        for name, value in components.items()
    ) or '<div class="empty">No financial component scores recorded.</div>'

    ratio_sections: list[str] = []
    for title, rows in _ratio_groups(ratios):
        ratio_sections.append(
            f'<div class="ratio-panel"><h3>{_escape(title)}</h3>'
            + _kv_rows(dict(rows))
            + '</div>'
        )
    ratio_html = "".join(ratio_sections) or '<div class="empty">No financial ratios recorded.</div>'

    history_html = _history_rows(history, ratios)
    full_history_html = _full_history_cards(history)

    valuation_html = _kv_rows({
        "Available": valuation.get("available"),
        "Fair value": valuation.get("fair_value"),
        "Buy below": valuation.get("buy_below"),
        "Decision score": decision_components.get("valuation"),
        "Decision state": decision.get("valuation_state"),
    })

    verdict_css = _verdict_class(verdict)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    financial_source = output_dir / "financial_analysis.json"

    html_document = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_escape(symbol)} Investment Report</title>
<style>
*{{box-sizing:border-box}}
:root{{--bg:#f5f7fb;--card:#fff;--ink:#172033;--muted:#687386;--line:#e5e9f0;--navy:#152238;--green:#16834a;--amber:#b7791f;--red:#c43d3d;--blue:#2f63c7}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,Segoe UI,Arial,sans-serif;line-height:1.55}}
.container{{max-width:1280px;margin:auto;padding:34px 24px 70px}}
.header{{display:flex;justify-content:space-between;gap:28px;align-items:flex-start;background:var(--navy);color:#fff;border-radius:22px;padding:30px 32px;box-shadow:0 10px 30px rgba(21,34,56,.12)}}
.eyebrow{{font-size:11px;letter-spacing:1.8px;text-transform:uppercase;color:#718096;font-weight:800}}
.header .eyebrow{{color:#a9b8cc}}h1{{font-size:42px;line-height:1.05;margin:7px 0}}h2{{font-size:25px;margin:0}}h3{{margin:0 0 10px;font-size:16px}}p{{margin:8px 0}}.subtitle{{color:#a9b8cc;font-size:14px}}
.verdict{{min-width:170px;padding:15px 25px;border-radius:15px;text-align:center;font-size:25px;font-weight:900;border:1px solid rgba(255,255,255,.15)}}
.verdict.buy{{background:#155c3c}}.verdict.watchlist{{background:#745416}}.verdict.avoid{{background:#7a2929}}.verdict.neutral{{background:#334155}}
.score-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:18px 0 32px}}
.score-card,.stat,.panel,.ratio-panel,.component,.history-detail{{background:var(--card);border:1px solid var(--line);border-radius:15px}}
.score-card{{padding:18px 20px}}.score-card span,.stat span{{display:block;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.8px;font-weight:800}}.score-card strong{{display:block;font-size:28px;margin-top:4px}}
.positive{{color:var(--green)}}.warning{{color:var(--amber)}}.negative{{color:var(--red)}}.neutral{{color:#526174}}
.section-head{{display:flex;justify-content:space-between;align-items:end;margin:38px 0 15px}}.section-head h2{{margin-top:3px}}.section-head p{{color:var(--muted);font-size:13px}}
.stat-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin:0 0 18px}}.stat{{padding:16px 17px}}.stat strong{{display:block;font-size:23px;margin-top:4px}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}}.panel{{padding:19px}}.panel.danger{{border-left:4px solid var(--red)}}.panel.success{{border-left:4px solid var(--green)}}.panel.caution{{border-left:4px solid var(--amber)}}ul{{padding-left:21px;margin:8px 0}}li{{margin:5px 0}}
.component-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}}.component{{padding:15px 17px;display:flex;justify-content:space-between;gap:12px}}.component span{{color:var(--muted);font-size:13px}}.component strong{{font-size:17px}}
.ratio-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}}.ratio-panel{{padding:17px 18px}}.ratio-panel h3{{padding-bottom:9px;border-bottom:1px solid var(--line)}}
.kv-grid{{display:grid;grid-template-columns:1fr 1fr;gap:0 24px}}.kv{{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px solid var(--line)}}.kv span{{color:var(--muted);font-size:13px}}.kv strong{{text-align:right;font-size:13px}}
table{{width:100%;border-collapse:separate;border-spacing:0;background:var(--card);border:1px solid var(--line);border-radius:15px;overflow:hidden}}th,td{{padding:12px 14px;border-bottom:1px solid var(--line);text-align:right;font-size:13px}}th{{background:#f0f3f8;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.7px}}th:first-child,td:first-child{{text-align:left}}tr:last-child td{{border-bottom:0}}td.year{{font-weight:800;color:var(--navy)}}
.history-detail{{margin-top:9px;overflow:hidden}}.history-detail summary{{cursor:pointer;padding:13px 16px;font-weight:800;display:flex;justify-content:space-between}}.history-detail summary span{{font-size:12px;color:var(--muted);font-weight:500}}.history-grid{{padding:0 16px 14px}}
.muted,.empty{{color:var(--muted)}}.source-note{{font-size:12px;color:var(--muted);margin:10px 0 0}}code{{background:#eef2f7;padding:2px 5px;border-radius:4px}}
.gov-years{{display:grid;gap:10px}}.gov-year{{background:var(--card);border:1px solid var(--line);border-radius:15px;overflow:hidden}}.gov-year summary{{cursor:pointer;list-style:none;padding:15px 18px;display:grid;grid-template-columns:120px 1fr 1fr;gap:14px;align-items:center;font-size:13px}}.gov-year summary::-webkit-details-marker{{display:none}}.gov-year .fy{{font-weight:900;font-size:17px}}.gov-year-body{{padding:0 18px 18px;border-top:1px solid var(--line)}}.gov-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}}.evidence{{background:#f8fafc;border:1px solid var(--line);border-radius:11px;padding:13px}}.evidence h4{{margin:0 0 6px;font-size:13px}}.evidence p{{font-size:13px}}.evidence.red{{border-left:3px solid var(--red)}}.evidence.full{{grid-column:1/-1}}.subhead{{margin:28px 0 10px}}
footer{{margin-top:42px;padding-top:18px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}}
@media(max-width:900px){{.stat-grid{{grid-template-columns:repeat(3,1fr)}}.component-grid{{grid-template-columns:repeat(2,1fr)}}.ratio-grid,.two-col,.gov-grid{{grid-template-columns:1fr}}.score-grid{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:600px){{.container{{padding:18px 12px 45px}}.header{{display:block;padding:24px}}h1{{font-size:35px}}.verdict{{margin-top:18px}}.score-grid,.stat-grid,.component-grid{{grid-template-columns:1fr}}.kv-grid{{grid-template-columns:1fr}}table{{display:block;overflow-x:auto;white-space:nowrap}}.gov-year summary{{grid-template-columns:1fr}}}}
</style>
</head>
<body><main class="container">
<header class="header"><div><div class="eyebrow">NSE Equity Research Agent</div><h1>{_escape(symbol)}</h1><div class="subtitle">Unified investment analysis · Generated {generated}</div></div><div class="verdict {verdict_css}">{_escape(verdict)}</div></header>
<section><div class="score-grid">{score_cards}</div></section>
<section><div class="section-head"><div><div class="eyebrow">01 · Decision</div><h2>Investment decision</h2></div></div><div class="panel"><div class="kv-grid">{_kv_rows({'Decision score': decision.get('decision_score'), 'Fundamental score': decision_components.get('fundamental_quality', financial.get('financial_score')), 'Governance score': decision_components.get('governance'), 'Valuation score': decision_components.get('valuation'), 'Valuation state': decision.get('valuation_state'), 'Governance hard fail': governance.get('hard_fail')})}</div><p><b>Reason:</b> {_escape(_fmt(decision.get('reason'), 'No decision reason available.'))}</p></div></section>
<section id="financial"><div class="section-head"><div><div class="eyebrow">02 · Financials</div><h2>Financial analysis</h2><p>Structured financial facts and calculated ratios are displayed exactly as persisted in <code>financial_analysis.json</code>.</p></div></div>
<div class="stat-grid">{financial_hero}</div>
<div class="section-head"><div><h3>Financial component scores</h3><p>These are persisted component scores; the report does not recalculate them.</p></div></div><div class="component-grid">{component_cards}</div>
<div class="section-head"><div><h3>10-year financial trend</h3><p>INR crore unless the metric is explicitly a percentage.</p></div></div>
<table><thead><tr><th>Fiscal year</th><th>Revenue (Cr)</th><th>EBIT (Cr)</th><th>PAT (Cr)</th><th>ROCE (%)</th><th>ROE (%)</th><th>PAT margin (%)</th></tr></thead><tbody>{history_html}</tbody></table>
<p class="source-note">No missing year or metric is invented. A dash means that the corresponding persisted value is unavailable.</p>
<div class="section-head"><div><h3>Financial ratios</h3><p>Grouped for readability; values remain unchanged from the JSON artifact.</p></div></div><div class="ratio-grid">{ratio_html}</div>
<div class="section-head"><div><h3>Annual financial inputs</h3><p>Expand a year to inspect the complete structured input record used by the financial stage.</p></div></div><div>{full_history_html}</div>
<div class="section-head"><div><h3>Valuation</h3></div></div><div class="panel"><div class="kv-grid">{valuation_html}</div><p><b>Reason:</b> {_escape(_fmt(valuation.get('reason'), 'No valuation reason available.'))}</p></div>
<p class="source-note">Financial source artifact: <code>{_escape(financial_source)}</code></p></section>
{_governance_html(governance)}
<section><div class="section-head"><div><div class="eyebrow">04 · Thesis</div><h2>Investment thesis</h2></div></div><div class="panel"><div class="kv-grid">{_kv_rows({'Conviction score': ai.get('conviction_score')})}</div><div style="margin-top:15px"><b>Executive summary</b><div style="white-space:pre-wrap;margin-top:8px">{_escape(_fmt(ai.get('thesis'), 'No qualitative thesis available.'))}</div></div></div></section>
<footer>Presentation layer only. This HTML reads persisted JSON artifacts and does not create alternate financial or governance calculations. Generated {generated}.</footer>
</main></body></html>'''

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_document, encoding="utf-8")
    return str(output_path)
