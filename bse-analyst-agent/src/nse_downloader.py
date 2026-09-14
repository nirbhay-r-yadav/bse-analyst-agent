"""
src/nse_downloader.py
Automated downloader for Indian Annual Reports via NSE India API.
Includes stock-specific local file caching, PDF validation, and multi-year report support.
"""

import os
import re
import shutil
import tempfile
import zipfile
import requests
from pathlib import Path
from typing import Optional

try:
    import pymupdf
except ImportError:
    pymupdf = None


class NSEDownloader:
    BASE_HOME = "https://www.nseindia.com"
    API_URL = "https://www.nseindia.com/api/annual-reports"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, download_dir: str = "./data/downloads"):
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._session_initialized = False

    def _init_session(self) -> bool:
        """Best-effort NSE homepage session initialization for API retry only."""
        try:
            resp = self.session.get(
                self.BASE_HOME,
                headers={"Referer": "https://www.google.com/"},
                timeout=15,
            )
            if resp.status_code >= 400:
                print(
                    f"[!] NSE homepage session unavailable: "
                    f"HTTP {resp.status_code}"
                )
                return False
            self._session_initialized = True
            return True
        except Exception as e:
            print(f"[!] NSE homepage session initialization failed: {e}")
            return False

    @staticmethod
    def _extract_fin_year(record: dict, file_url: str = "") -> str | None:
        """Extract a financial-year label from an NSE annual-report record."""
        for key in (
            "finYear",
            "financialYear",
            "financial_year",
            "year",
            "FY",
        ):
            value = record.get(key)
            if value:
                value = str(value).strip()
                if value:
                    return value

        match = re.search(
            r"_(20\d{2})_(20\d{2})(?:_|\.|$)",
            file_url,
            flags=re.IGNORECASE,
        )
        if match:
            return f"FY{match.group(1)}-{match.group(2)[-2:]}"

        return None

    def get_annual_report_records(self, symbol: str) -> list[dict]:
        """Return available NSE annual-report records, newest first.

        The annual-report API is the primary source. NSE's homepage is not a
        prerequisite because it may return HTTP 403 while the public API still
        returns valid annual-report data.
        """
        params = {
            "index": "equities",
            "symbol": symbol.upper().strip(),
        }

        api_headers = {
            "Referer": (
                "https://www.nseindia.com/"
                "companies-listing/corporate-filings-annual-reports"
            ),
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
        }

        try:
            res = self.session.get(
                self.API_URL,
                params=params,
                headers=api_headers,
                timeout=30,
            )
            content_type = (res.headers.get("Content-Type") or "").lower()
            print(
                f"[*] NSE annual-report API: HTTP {res.status_code} | "
                f"{content_type or 'content-type unavailable'}"
            )

            if res.status_code in (401, 403):
                print("[*] NSE annual-report API requires session retry; initializing homepage session...")
                if self._init_session():
                    res = self.session.get(
                        self.API_URL,
                        params=params,
                        headers=api_headers,
                        timeout=30,
                    )
                    content_type = (res.headers.get("Content-Type") or "").lower()
                    print(
                        f"[*] NSE annual-report API retry: HTTP {res.status_code} | "
                        f"{content_type or 'content-type unavailable'}"
                    )

            res.raise_for_status()

            data = res.json()
            items = data.get("data", []) if isinstance(data, dict) else []

            records = [
                item
                for item in items
                if isinstance(item, dict) and item.get("fileName")
            ]

            for record in records:
                file_url = str(record.get("fileName") or "")
                if not record.get("finYear"):
                    match = re.search(
                        r"_(20\d{2})_(20\d{2})(?:_|\.)",
                        file_url,
                        re.IGNORECASE,
                    )
                    if match:
                        record["finYear"] = (
                            f"FY{match.group(1)}-{match.group(2)[-2:]}"
                        )
                    else:
                        record["finYear"] = None

            print(f"[*] NSE annual-report API records received: {len(records)}")
            return records

        except Exception as e:
            print(f"[x] Error querying NSE annual reports: {e}")
            return []

    def get_latest_annual_report_url(
        self,
        symbol: str,
    ) -> Optional[str]:
        """Fetch the latest annual-report download URL."""
        records = self.get_annual_report_records(symbol)

        if not records:
            print(
                f"[!] No annual reports found on NSE for symbol '{symbol}'."
            )
            return None

        latest = records[0]
        print(
            f"[+] Found filing for {symbol} "
            f"({latest.get('companyName', '')}) - "
            f"FY: {latest.get('finYear', 'N/A')}"
        )
        return latest.get("fileName")

    @staticmethod
    def _safe_year(record: dict, index: int) -> str:
        value = str(
            record.get("finYear")
            or record.get("financialYear")
            or record.get("year")
            or ""
        ).strip()
        return (
            value.replace("/", "-").replace(" ", "_")
            or f"report_{index + 1}"
        )

    @staticmethod
    def _is_valid_pdf(path: str) -> bool:
        """Return True only when the file is a readable PDF with at least one page."""
        if not os.path.exists(path):
            return False

        try:
            if os.path.getsize(path) <= 10 * 1024:
                return False
        except OSError:
            return False

        try:
            with open(path, "rb") as fh:
                if fh.read(5) != b"%PDF-":
                    return False
        except OSError:
            return False

        if pymupdf is None:
            print("[!] PyMuPDF is unavailable; cannot fully validate PDF.")
            return False

        try:
            with pymupdf.open(path) as doc:
                if not doc.is_pdf or len(doc) <= 0:
                    return False
                _ = doc[0].get_text("text")
            return True
        except Exception:
            return False

    def _extract_pdf_from_zip(self, zip_path: str, target_path: str) -> bool:
        """Extract the most likely annual-report PDF from an NSE ZIP archive."""
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                members = [
                    name
                    for name in zf.namelist()
                    if not name.endswith("/") and name.lower().endswith(".pdf")
                ]
                if not members:
                    raise IOError("NSE ZIP archive contains no PDF files")

                def score(name: str) -> int:
                    lower = name.lower()
                    value = 0
                    if "annual" in lower:
                        value += 50
                    if "report" in lower:
                        value += 30
                    if "ar" in lower:
                        value += 10
                    if "financial" in lower:
                        value += 5
                    try:
                        value += min(
                            zf.getinfo(name).file_size // (1024 * 1024),
                            20,
                        )
                    except Exception:
                        pass
                    return value

                selected = max(members, key=score)
                print(f"[*] ZIP contains {len(members)} PDF(s)")
                print(f"[*] Selected PDF from ZIP: {selected}")

                extract_dir = tempfile.mkdtemp(prefix="nse_ar_")
                try:
                    extracted = Path(zf.extract(selected, extract_dir))
                    target = Path(target_path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(extracted, target)
                finally:
                    shutil.rmtree(extract_dir, ignore_errors=True)

            if not self._is_valid_pdf(str(target_path)):
                raise IOError("Extracted annual-report PDF failed validation")
            return True

        except Exception as exc:
            print(f"[!] ZIP annual-report extraction failed: {exc}")
            return False

    def _download_and_validate(
        self,
        pdf_url: str,
        target_path: str,
        timeout: int = 60,
    ) -> bool:
        """Download an NSE annual report and validate PDF/ZIP content."""
        temp_path = f"{target_path}.tmp"
        try:
            response = self.session.get(
                pdf_url,
                stream=True,
                timeout=timeout,
            )
            response.raise_for_status()
            content_type = (response.headers.get("Content-Type") or "").lower()
            print(f"[*] Download response: {response.status_code} | {content_type}")

            with open(temp_path, "wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)

            if os.path.getsize(temp_path) <= 10 * 1024:
                raise IOError("Downloaded annual-report file is unexpectedly small")

            with open(temp_path, "rb") as handle:
                signature = handle.read(8)

            if signature.startswith(b"%PDF-"):
                if not self._is_valid_pdf(temp_path):
                    raise IOError("Downloaded annual-report PDF failed validation")
                os.replace(temp_path, target_path)
                return True

            if signature.startswith(b"PK"):
                print("[*] NSE annual report is a ZIP archive")
                zip_target = f"{target_path}.zip"
                os.replace(temp_path, zip_target)
                try:
                    if not self._extract_pdf_from_zip(zip_target, target_path):
                        raise IOError(
                            "Downloaded annual-report ZIP could not produce a valid PDF"
                        )
                finally:
                    try:
                        os.remove(zip_target)
                    except OSError:
                        pass
                return True

            raise IOError(
                "Downloaded annual-report is neither PDF nor ZIP "
                f"(Content-Type: {content_type}, signature={signature!r})"
            )

        except Exception as exc:
            print(f"[!] PDF/ZIP download/validation failed: {exc}")
            try:
                os.remove(temp_path)
            except OSError:
                pass
            return False

    def download_reports(
        self,
        symbol: str,
        years: int = 10,
        force_redownload: bool = False,
    ) -> list[dict]:
        """Download/cache up to `years` reports inside the stock-specific folder."""
        symbol = symbol.upper().strip()
        stock_dir = self._stock_dir(symbol)
        records = self.get_annual_report_records(symbol)

        if not records:
            return []

        selected = records[:max(1, years)]
        results: list[dict] = []

        for index, record in enumerate(selected):
            fy = self._safe_year(record, index)
            target_filename = f"{symbol}_{fy}_annual_report.pdf"
            target_path = os.path.join(stock_dir, target_filename)

            if os.path.exists(target_path) and not force_redownload:
                if self._is_valid_pdf(target_path):
                    print(f"[✓] Valid cached annual report: {target_path}")
                    results.append({
                        "fiscal_year": str(record.get("finYear") or record.get("financialYear") or fy),
                        "path": target_path,
                        "url": record.get("fileName"),
                        "cached": True,
                    })
                    continue
                print(f"[!] Cached annual report is invalid/unreadable; will redownload: {target_path}")
                try:
                    os.remove(target_path)
                except OSError:
                    pass

            legacy_path = os.path.join(self.download_dir, target_filename)
            if (
                os.path.exists(legacy_path)
                and not force_redownload
                and self._is_valid_pdf(legacy_path)
            ):
                shutil.copy2(legacy_path, target_path)
                print(f"[✓] Reused legacy cached annual report: {target_path}")
                results.append({
                    "fiscal_year": str(record.get("finYear") or record.get("financialYear") or fy),
                    "path": target_path,
                    "url": record.get("fileName"),
                    "cached": True,
                })
                continue

            pdf_url = record.get("fileName")
            if not pdf_url:
                print(f"[!] No PDF URL for {symbol} {record.get('finYear', fy)}")
                continue

            print(f"[*] Downloading {symbol} {record.get('finYear', fy)} annual report...")
            success = self._download_and_validate(pdf_url, target_path, timeout=120)
            if not success:
                print(f"[!] Failed to download/validate {symbol} {record.get('finYear', fy)}")
                continue

            print(f"[✓] Valid annual report downloaded: {target_path}")
            results.append({
                "fiscal_year": str(record.get("finYear") or record.get("financialYear") or fy),
                "path": target_path,
                "url": record.get("fileName"),
                "cached": False,
            })

        return results

    def download_report(
        self,
        symbol: str,
        custom_filename: Optional[str] = None,
        force_redownload: bool = False,
    ) -> Optional[str]:
        """Download/cache the latest annual report in the stock-specific folder."""
        symbol = symbol.upper().strip()
        stock_dir = self._stock_dir(symbol)
        target_filename = custom_filename or f"{symbol}_latest_annual_report.pdf"
        target_path = os.path.join(stock_dir, target_filename)

        if os.path.exists(target_path) and not force_redownload:
            if self._is_valid_pdf(target_path):
                print(f"[✓] Valid cached annual report: {target_path}")
                return target_path
            print(f"[!] Cached annual report is invalid/unreadable; will redownload: {target_path}")
            try:
                os.remove(target_path)
            except OSError:
                pass

        legacy_path = os.path.join(self.download_dir, target_filename)
        if (
            os.path.exists(legacy_path)
            and not force_redownload
            and self._is_valid_pdf(legacy_path)
        ):
            shutil.copy2(legacy_path, target_path)
            print(f"[✓] Reused legacy cached annual report: {target_path}")
            return target_path

        pdf_url = self.get_latest_annual_report_url(symbol)
        if not pdf_url:
            return None

        print(f"[*] Downloading PDF from: {pdf_url}")
        success = self._download_and_validate(pdf_url, target_path, timeout=90)
        if not success:
            print("[!] Downloaded annual-report file failed PDF validation.")
            return None

        print(f"[+] Successfully downloaded: {target_path}")
        return target_path
