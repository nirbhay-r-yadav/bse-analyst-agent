from src.financial_tools import AnnualFinancials, CompanyFinancialHistory, calculate_fundamental_ratios


def test_metrics_use_available_history_when_only_six_years_exist():
    years = [
        AnnualFinancials(fiscal_year=f"FY{year}", revenue=100.0 + year - 2019, pat=10.0 + year - 2019)
        for year in range(2019, 2025)
    ]
    history = CompanyFinancialHistory(years=years)
    ratios = calculate_fundamental_ratios(history)

    assert ratios["years_analyzed"] == 6
    assert ratios["Revenue CAGR (%)"] is not None
    assert ratios["PAT CAGR (%)"] is not None
    assert ratios["Revenue CAGR 10Y (%)"] is None
    assert ratios["hurdles_passed"]["cfo_history_sufficient"] is False


def test_cfo_metrics_use_only_available_cfo_observations():
    years = []
    for year in range(2019, 2025):
        years.append(
            AnnualFinancials(
                fiscal_year=f"FY{year}",
                revenue=100.0 + year - 2019,
                pat=10.0 + year - 2019,
                cfo=(20.0 + year - 2022) if year >= 2022 else None,
            )
        )

    ratios = calculate_fundamental_ratios(CompanyFinancialHistory(years=years))

    assert ratios["Positive CFO Years"] == "3/3"
    assert ratios["CFO Positive Ratio (%)"] == 100.0
    assert ratios["hurdles_passed"]["cfo_history_sufficient"] is True
    assert ratios["hurdles_passed"]["cfo_positive_consistency"] is True
    assert ratios["Average CFO / PAT (Available History)"] is not None
