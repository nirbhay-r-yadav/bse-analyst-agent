"""Corporate-governance reporting sourced only from corporate_governance.json.

This module is presentation-only. It does not calculate governance scores or
reinterpret evidence. The stock folder is the report boundary:

    outputs/<SYMBOL>/corporate_governance.json

Every governance value displayed by this report is read from that artifact.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


SECTION = "=" * 88


def _fmt(value: Any, default: str = "N/A") -> str:
    if value is None or value == "":
        return default
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _section(lines: list[str], title: str) -> None:
    lines.extend(["", SECTION, title.upper(), SECTION])


def _bullet_section(lines: list[str], title: str, values: Any) -> None:
    lines.append(title)
    items = _items(values)
    if items:
        lines.extend(f"- {item}" for item in items)
    else:
        lines.append("- None recorded")


def load_governance_json(stock_output_dir: str | Path) -> tuple[Path, dict[str, Any]]:
    """Load exactly outputs/<SYMBOL>/corporate_governance.json."""
    directory = Path(stock_output_dir)
    path = directory / "corporate_governance.json"
    if not path.exists():
        raise FileNotFoundError(f"Corporate governance artifact not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in corporate governance artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Corporate governance artifact must contain a JSON object: {path}")
    return path, payload


def generate_governance_text_report(
    stock_output_dir: str | Path,
    output_file: str | Path | None = None,
) -> str:
    """Generate a governance report using only corporate_governance.json."""
    source_path, governance = load_governance_json(stock_output_dir)
    directory = source_path.parent
    symbol = str(governance.get("symbol") or directory.name)

    if output_file is None:
        output_file = directory / "corporate_governance_report.txt"
    output_path = Path(output_file)

    lines: list[str] = [
        "CORPORATE GOVERNANCE REPORT",
        SECTION,
        f"Stock: {symbol}",
        f"Source: {source_path}",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
    ]

    _section(lines, "Governance Summary")
    summary = [
        ("Governance grade", governance.get("governance_grade")),
        ("Risk score", governance.get("risk_score")),
        ("Annual report score", governance.get("annual_report_score")),
        ("Reports scanned", governance.get("reports_scanned"),),
        ("Hard fail", governance.get("hard_fail")),
    ]
    lines.extend(f"{name}: {_fmt(value)}" for name, value in summary)

    _section(lines, "Risk Assessment")
    _bullet_section(lines, "Risk flags:", governance.get("risk_flags"))
    _bullet_section(lines, "Positive signals:", governance.get("positive_signals"))
    _bullet_section(lines, "Data gaps:", governance.get("data_gaps"))

    audits = governance.get("annual_report_audits")
    _section(lines, "Annual Report Forensic Evidence")
    if not isinstance(audits, list) or not audits:
        lines.append("No annual report forensic evidence recorded.")
    else:
        lines.append(f"Reports represented in artifact: {len(audits)}")
        for index, audit in enumerate(audits, 1):
            if not isinstance(audit, dict):
                continue
            lines.extend([
                "",
                f"[{index}] Fiscal Year: {_fmt(audit.get('fiscal_year'))}",
                f"Audit Opinion: {_fmt(audit.get('audit_opinion_type'))}",
                f"Contingent Liability Risk: {_fmt(audit.get('contingent_liability_risk'))}",
                f"Related Party Risk: {_fmt(audit.get('related_party_risk'))}",
            ])
            for field, title in (
                ("auditor_observations", "Auditor Observations"),
                ("key_audit_matters", "Key Audit Matters"),
                ("related_party_transactions", "Related-Party Transactions"),
                ("loans_guarantees_investments", "Loans / Guarantees / Investments"),
                ("contingent_liabilities", "Contingent Liabilities"),
                ("remuneration_details", "Remuneration Details"),
                ("regulatory_compliance_events", "Regulatory Compliance Events"),
                ("what_happened", "What Happened"),
                ("forensic_red_flags", "Forensic Red Flags"),
                ("why_it_matters", "Why It Matters"),
                ("governance_conclusion", "Governance Conclusion"),
            ):
                value = audit.get(field)
                if isinstance(value, list):
                    lines.append(f"{title}:")
                    items = _items(value)
                    lines.extend(f"  - {item}" for item in items) if items else lines.append("  - None recorded")
                else:
                    lines.append(f"{title}: {_fmt(value, 'None recorded')}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return str(output_path)
