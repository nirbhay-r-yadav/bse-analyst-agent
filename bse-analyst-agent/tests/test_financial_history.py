from src.financial_history import FinancialHistoryRow, FinancialHistoryStore


def test_missing_years_detects_gap():
    rows = [
        FinancialHistoryRow("FY2024", "consolidated", "annual_xbrl", "a"),
        FinancialHistoryRow("FY2026", "consolidated", "annual_xbrl", "b"),
    ]
    assert FinancialHistoryStore.missing_years(rows) == [
        "FY2017",
        "FY2018",
        "FY2019",
        "FY2020",
        "FY2021",
        "FY2022",
        "FY2023",
        "FY2025",
    ]


def test_validation_does_not_accept_unknown_source():
    row = FinancialHistoryRow("FY2026", "consolidated", "guess", "a")
    assert "invalid_source_type" in FinancialHistoryStore.validate_row(row)
