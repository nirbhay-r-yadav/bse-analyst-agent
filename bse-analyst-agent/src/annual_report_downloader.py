from __future__ import annotations

import json
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests


NSE_BASE = "https://www.nseindia.com"
ANNUAL_REPORTS_API = f"{NSE_BASE}/api/annual-reports"
ARCHIVE_BASE = "https://nsearchives.nseindia.com/"


@dataclass(frozen=True)
class AnnualReportRecord:
    symbol: str
    from_year: str | None
    to_year: str | None
    file_name: str
    url: str
    size: str | None = None
    source: str = "NSE Annual Reports"

    @property
    def report_year(self) -> int | None:
        years = [int(y) for y in re.findall(r"20\\d{2}", f"{self.from_year} {self.to_year}")]
        return max(years) if years else None

    @property
    def file_type(self) -> str:
        return Path(self.file_name).suffix.lower().lstrip(".") or "unknown"


class AnnualReportDownloader:
    """Discover and download the official NSE annual-report archive.

    The discovery endpoint is intentionally isolated from parsing so the
    financial analysis layer never depends on NSE's filing-page HTML.
    """

    def __init__(self, root: str | Path = "data/annual_reports", timeout: int = 30):
        self.root = Path(root)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/153.0 Safari/537.36"
                ),
                "Accept": "application/json,text/plain,*/*",
                "Referer": f"{NSE_BASE}/",
            }
        )

    def _prime(self) -> None:
        self.session.get(NSE_BASE, timeout=self.timeout)

    @staticmethod
    def _records(symbol: str, payload: Any) -> list[AnnualReportRecord]:
        rows = payload.get("data", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []

        result: list[AnnualReportRecord] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            file_name = (
                row.get("fileName")
                or row.get("filename")
                or row.get("file_name")
                or ""
            )
            if not file_name:
                continue
            if str(file_name).startswith("http"):
                url = str(file_name)
            else:
                url = urljoin(ARCHIVE_BASE, str(file_name).lstrip("/"))
            result.append(
                AnnualReportRecord(
                    symbol=symbol.upper(),
                    from_year=row.get("fromYr") or row.get("fromYear"),
                    to_year=row.get("toYr") or row.get("toYear"),
                    file_name=Path(str(file_name)).name,
                    url=url,
                    size=row.get("attFileSize") or row.get("fileSize"),
                )
            )
        return result

    def discover(self, symbol: str) -> list[AnnualReportRecord]:
        self._prime()
        response = self.session.get(
            ANNUAL_REPORTS_API,
            params={"index": "equities", "symbol": symbol.upper()},
            timeout=self.timeout,
        )
        response.raise_for_status()

        # NSE may return JSON or, during an anti-bot/interstitial response,
        # HTML. Never silently treat HTML as an empty filing history.
        content_type = response.headers.get("content-type", "").lower()
        if "json" not in content_type:
            try:
                payload = response.json()
            except ValueError as exc:
                raise RuntimeError(
                    "NSE annual-report endpoint returned non-JSON content"
                ) from exc
        else:
            payload = response.json()

        records = self._records(symbol, payload)
        if not records:
            raise RuntimeError(f"No annual-report records returned for {symbol.upper()}")
        return records

    def download(self, record: AnnualReportRecord, force: bool = False) -> Path:
        destination_dir = self.root / record.symbol
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / record.file_name

        if destination.exists() and not force:
            return destination

        response = self.session.get(record.url, timeout=self.timeout, stream=True)
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
        return destination

    def download_history(
        self,
        symbol: str,
        min_year: int | None = None,
        max_year: int | None = None,
    ) -> list[Path]:
        records = self.discover(symbol)
        paths: list[Path] = []
        for record in records:
            years = [int(y) for y in re.findall(r"20\d{2}", f"{record.from_year} {record.to_year}")]
            if years:
                report_year = max(years)
                if min_year is not None and report_year < min_year:
                    continue
                if max_year is not None and report_year > max_year:
                    continue
            paths.append(self.download(record))
        self._write_manifest(symbol, records)
        return paths

    def inventory(self, symbol: str, min_year: int = 2017, max_year: int | None = None) -> list[dict[str, Any]]:
        """Return a deterministic year/file inventory without downloading files."""
        records = self.discover(symbol)
        latest = max((r.report_year for r in records if r.report_year), default=None)
        end_year = max_year or latest or min_year
        start_year = min_year
        inventory: list[dict[str, Any]] = []
        for year in range(start_year, end_year + 1):
            matches = [r for r in records if r.report_year == year]
            inventory.append({
                "fiscal_year": f"FY{year}",
                "records": [asdict(r) | {"file_type": r.file_type} for r in matches],
                "available": bool(matches),
            })
        return inventory

    def _write_manifest(self, symbol: str, records: list[AnnualReportRecord]) -> None:
        destination = self.root / symbol.upper() / "manifest.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps([asdict(r) for r in records], indent=2),
            encoding="utf-8",
        )


def extract_archive(path: str | Path, destination: str | Path | None = None) -> list[Path]:
    """Extract an NSE annual-report ZIP and return contained files."""
    source = Path(path)
    if source.suffix.lower() != ".zip":
        return [source]

    target = Path(destination) if destination else source.with_suffix("")
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as archive:
        archive.extractall(target)
        return [target / name for name in archive.namelist() if not name.endswith("/")]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download NSE annual reports")
    parser.add_argument("symbol")
    parser.add_argument("--root", default="data/annual_reports")
    parser.add_argument("--min-year", type=int, default=None)
    parser.add_argument("--max-year", type=int, default=None)
    args = parser.parse_args()

    downloader = AnnualReportDownloader(args.root)
    paths = downloader.download_history(
        args.symbol, min_year=args.min_year, max_year=args.max_year
    )
    print(f"Downloaded {len(paths)} annual-report files for {args.symbol.upper()}")
