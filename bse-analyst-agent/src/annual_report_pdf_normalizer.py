from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pymupdf


FIELD_PATTERNS = {
    "revenue": (r"revenue from operations", r"revenue"),
    "pat_owner": (r"profit attributable to owners", r"profit attributable to equity holders"),
    "pat": (r"profit for the (year|period)", r"profit for the year"),
    "ebit": (r"profit before finance costs and tax", r"operating profit"),
    "pbt": (r"profit before tax",),
    "cfo": (r"net cash generated from operating activities", r"cash flows from operating activities"),
    "debt": (r"total borrowings", r"borrowings"),
    "cash": (r"cash and cash equivalents", r"cash and bank balances"),
    "equity_owner": (r"equity attributable to owners",),
    "equity": (r"total equity", r"total equity and liabilities"),
}

BASIS_RE = re.compile(r"consolidated", re.I)
STANDALONE_RE = re.compile(r"standalone", re.I)


def _number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("(", "-").replace(")", "")
    if not text or text in {"-", "—", "–"}:
        return None
    text = re.sub(r"[^0-9.\-]", "", text)
    try:
        return float(text) if text else None
    except ValueError:
        return None


def _to_crore(value: float | None, page_text: str) -> float | None:
    if value is None:
        return None
    lower = page_text.lower()
    if re.search(r"\bin\s*(?:₹|rs\.?|inr)?\s*lakhs?\b", lower):
        return value / 100.0
    if "in millions" in lower:
        return value / 10.0
    if "in thousands" in lower:
        return value / 10000.0
    if "in usd" in lower and "crore" not in lower:
        return value
    return value


class AnnualReportPDFNormalizer:
    """Extract only high-confidence statement rows from annual-report PDFs.

    This is intentionally conservative: a page/table is ignored unless a
    recognizable statement label has numeric columns. No values are inferred
    from prose or chart summaries.
    """

    def normalize(self, path: str | Path) -> list[dict[str, Any]]:
        path = Path(path)
        doc = pymupdf.open(path)
        rows: dict[tuple[str, str], dict[str, Any]] = {}

        for page in doc:
            text = page.get_text("text")
            if not text:
                continue
            if not any(re.search(p, text, re.I) for pats in FIELD_PATTERNS.values() for p in pats):
                continue

            basis = "consolidated" if BASIS_RE.search(text[:5000]) else (
                "standalone" if STANDALONE_RE.search(text[:5000]) else "unknown"
            )
            years = sorted({int(y) for y in re.findall(r"\b20(?:1[7-9]|2[0-9])\b", text)}, reverse=True)
            if not years:
                continue

            try:
                tables = page.find_tables().tables
            except Exception:
                tables = []

            for table in tables:
                data = table.extract()
                for cells in data:
                    if not cells:
                        continue
                    label = " ".join(str(x or "") for x in cells[:2]).strip()
                    if not label:
                        continue
                    field = None
                    for name, patterns in FIELD_PATTERNS.items():
                        if any(re.search(p, label, re.I) for p in patterns):
                            field = name
                            break
                    if field is None:
                        continue

                    values = [_to_crore(_number(x), text) for x in cells[1:]]
                    numeric = [v for v in values if v is not None]
                    if not numeric:
                        continue

                    for idx, value in enumerate(numeric[:len(years)]):
                        fy = f"FY{years[idx]}"
                        key = (fy, basis)
                        row = rows.setdefault(key, {
                            "fiscal_year": fy,
                            "basis": basis,
                            "source_type": "annual_report_pdf",
                            "source_file": str(path),
                            "revenue": None,
                            "pat": None,
                            "pat_owner": None,
                            "ebit": None,
                            "pbt": None,
                            "cfo": None,
                            "debt": None,
                            "cash": None,
                            "equity": None,
                            "equity_owner": None,
                            "confidence": "extracted_unvalidated",
                        })
                        if row.get(field) is None:
                            row[field] = value

        return list(rows.values())
