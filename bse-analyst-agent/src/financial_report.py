"""Human-readable financial analysis report sourced only from financial_analysis.json."""

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


def _load_financial_json(stock_output_dir: str | Path) -> tuple[Path, dict[str, Any]]:
    directory = Path(stock_output_dir)
    path = directory / "financial_analysis.json"
    if not path.exists():
        raise FileNotFoundError(f"Financial analysis artifact not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in financial analysis artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Financial analysis artifact must contain a JSON object: {path}")
    return path, payload


def generate_financial_text_report(
    stock_output_dir: str | Path,
    output_file: str | Path | None = None,
) -> str:
    """Generate financial_analysis.txt using only financial_analysis.json."""
    source_path, financial = _load_financial_json(stock_output_dir)
    directory = source_path.parent
    symbol = str(financial.get("symbol") or directory.name)
    output_path = Path(output_file) if output_file else directory / "financial_analysis.txt"

    components = financial.get("financial_components") or {}
    ratios = financial.get("ratios") or {}
    history = financial.get("history") or []
    valuation = financial.get("valuation") or {}

    lines = [
        "FINANCIAL ANALYSIS REPORT",
        SECTION,
        f"Stock: {symbol}",
        f"Source: {source_path}",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        SECTION,
        "FINANCIAL SCORE",
        SECTION,
        f"Financial Score: {_fmt(financial.get('financial_score'))}",
        "",
        SECTION,
        "FINANCIAL COMPONENTS",
        SECTION,
    ]
    if components:
        lines.extend(f"{name}: {_fmt(value)}" for name, value in components.items())
    else:
        lines.append("No financial components recorded.")

    lines.extend(["", SECTION, "FINANCIAL RATIOS", SECTION])
    if ratios:
        lines.extend(f"{name}: {_fmt(value)}" for name, value in ratios.items())
    else:
        lines.append("No financial ratios recorded.")

    lines.extend(["", SECTION, "FINANCIAL HISTORY", SECTION])
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

    lines.extend([SECTION, "VALUATION", SECTION])
    for name, value in valuation.items():
        if isinstance(value, (dict, list)):
            lines.append(f"{name}: {json.dumps(value, ensure_ascii=False, default=str)}")
        else:
            lines.append(f"{name}: {_fmt(value)}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return str(output_path)
