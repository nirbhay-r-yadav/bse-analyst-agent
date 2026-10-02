from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

import pymupdf


STATEMENT_PATTERNS = {
    "profit_loss": re.compile(
        r"(consolidated statement of profit and loss|statement of profit and loss|income statement)",
        re.I,
    ),
    "balance_sheet": re.compile(
        r"(consolidated balance sheet|statement of financial position|balance sheet)",
        re.I,
    ),
    "cash_flow": re.compile(
        r"(consolidated statement of cash flows?|statement of cash flows?|cash flow statement)",
        re.I,
    ),
}


class AnnualReportParser:
    """Parse an annual-report artifact into auditable source sections.

    PDF parsing is deliberately extraction-first. It does not guess financial
    values from arbitrary prose. XBRL/structured reports are handled separately
    by the financial-history normalizer.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def extract_pdf_sections(self, max_pages_per_section: int = 30) -> dict[str, str]:
        document = pymupdf.open(self.path)
        pages = [(i + 1, page.get_text("text")) for i, page in enumerate(document)]
        result: dict[str, str] = {}

        for name, pattern in STATEMENT_PATTERNS.items():
            matched = []
            for page_number, text in pages:
                if pattern.search(text[:1200]):
                    matched.append((page_number, text))
                    if len(matched) >= max_pages_per_section:
                        break
            result[name] = "".join(
                f"\n--- [PAGE {page_number}] ---\n{text}" for page_number, text in matched
            )

        return result

    def extract_xbrl_documents(self) -> list[dict[str, Any]]:
        """Return JSON-like XBRL documents found inside an annual-report ZIP."""
        if self.path.suffix.lower() != ".zip":
            return []

        documents: list[dict[str, Any]] = []
        with zipfile.ZipFile(self.path) as archive:
            for name in archive.namelist():
                if not name.lower().endswith(".json"):
                    continue
                try:
                    documents.append(json.loads(archive.read(name).decode("utf-8")))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
        return documents

    def parse(self) -> dict[str, Any]:
        suffix = self.path.suffix.lower()
        if suffix == ".pdf":
            return {
                "source_type": "annual_report_pdf",
                "path": str(self.path),
                "sections": self.extract_pdf_sections(),
            }
        if suffix == ".zip":
            return {
                "source_type": "annual_report_archive",
                "path": str(self.path),
                "xbrl_documents": self.extract_xbrl_documents(),
            }
        return {
            "source_type": "unsupported",
            "path": str(self.path),
        }
