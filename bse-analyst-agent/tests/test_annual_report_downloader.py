from pathlib import Path

from src.annual_report_downloader import AnnualReportRecord


def test_annual_report_record_year_and_type():
    record = AnnualReportRecord(
        symbol="INFY",
        from_year="2025",
        to_year="2026",
        file_name="AR_29313_INFY_2025_2026_U_8985411.pdf",
        url="https://nsearchives.nseindia.com/annual_reports/example.pdf",
    )
    assert record.report_year == 2026
    assert record.file_type == "pdf"


def test_annual_report_record_zip_type():
    record = AnnualReportRecord(
        symbol="INFY",
        from_year="2021",
        to_year="2022",
        file_name="annual_report_2021_2022.zip",
        url="https://nsearchives.nseindia.com/annual_reports/example.zip",
    )
    assert record.report_year == 2022
    assert record.file_type == "zip"
