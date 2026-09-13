import unittest

from src.financial_tools import AnnualFinancials, CompanyFinancialHistory, calculate_fundamental_ratios


def make_roe_year(year: int) -> AnnualFinancials:
    step = year - 2010
    return AnnualFinancials(
        fiscal_year=f"FY{year}",
        revenue=(100 + step * 10),
        ebit=(20 + step * 3),
        pat=(10 + step * 2),
        total_debt=40,
        total_equity=100 + step * 12,
        cash_equivalents=10,
    )


class ROETests(unittest.TestCase):
    def test_roe_uses_average_beginning_and_ending_equity(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2025", revenue=1420, ebit=260, pat=180, total_equity=850),
            AnnualFinancials(fiscal_year="FY2026", revenue=1600, ebit=300, pat=210, total_equity=950),
        ])
        ratios = calculate_fundamental_ratios(history)

        expected = 210 / ((850 + 950) / 2) * 100
        self.assertEqual(ratios["ROE (%)"], round(expected, 2))

    def test_roe_has_ten_year_history_using_valid_prior_equity(self):
        history = CompanyFinancialHistory(years=[make_roe_year(year) for year in range(2017, 2027)])
        ratios = calculate_fundamental_ratios(history)

        self.assertEqual(len(ratios["ROE History (%)"]), 9)
        self.assertNotIn("FY2017", ratios["ROE History (%)"])
        self.assertEqual(list(ratios["ROE History (%)"].keys())[0], "FY2018")
        self.assertEqual(list(ratios["ROE History (%)"].keys())[-1], "FY2026")

        expected_values = []
        years = [make_roe_year(year) for year in range(2017, 2027)]
        for index in range(1, len(years)):
            expected_values.append(
                years[index].pat / ((years[index - 1].total_equity + years[index].total_equity) / 2) * 100
            )

        self.assertEqual(
            list(ratios["ROE History (%)"].values()),
            [round(value, 2) for value in expected_values],
        )
        self.assertEqual(ratios["Minimum ROE (%)"], round(min(expected_values), 2))
        self.assertEqual(ratios["Maximum ROE (%)"], round(max(expected_values), 2))
        self.assertEqual(ratios["ROE Range (pp)"], round(max(expected_values) - min(expected_values), 2))

    def test_roe_average_uses_full_precision_values(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2024", revenue=1000, ebit=150, pat=101, total_equity=503),
            AnnualFinancials(fiscal_year="FY2025", revenue=1100, ebit=170, pat=113, total_equity=607),
            AnnualFinancials(fiscal_year="FY2026", revenue=1200, ebit=190, pat=127, total_equity=719),
        ])
        ratios = calculate_fundamental_ratios(history)

        roe_values = [
            113 / ((503 + 607) / 2) * 100,
            127 / ((607 + 719) / 2) * 100,
        ]
        self.assertEqual(ratios["Average ROE (%)"], round(sum(roe_values) / len(roe_values), 2))

    def test_roe_yoy_change_and_trend(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2024", revenue=1000, ebit=150, pat=90, total_equity=500),
            AnnualFinancials(fiscal_year="FY2025", revenue=1100, ebit=180, pat=105, total_equity=550),
            AnnualFinancials(fiscal_year="FY2026", revenue=1200, ebit=210, pat=126, total_equity=600),
        ])
        ratios = calculate_fundamental_ratios(history)

        prior_roe = 105 / ((500 + 550) / 2) * 100
        latest_roe = 126 / ((550 + 600) / 2) * 100
        self.assertEqual(ratios["ROE YoY Change (pp)"], round(latest_roe - prior_roe, 2))
        self.assertEqual(ratios["ROE Trend"], "UP")

    def test_roe_is_unavailable_without_prior_equity(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2026", revenue=1000, ebit=150, pat=100, total_equity=500),
        ])
        ratios = calculate_fundamental_ratios(history)

        self.assertIsNone(ratios["ROE (%)"])
        self.assertIsNone(ratios["Average ROE (%)"])
        self.assertEqual(ratios["ROE History (%)"], {})
        self.assertIsNone(ratios["ROE YoY Change (pp)"])
        self.assertEqual(ratios["ROE Trend"], "FLAT")

    def test_roe_year_is_excluded_when_current_or_prior_equity_is_missing(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2024", revenue=1000, ebit=150, pat=90, total_equity=500),
            AnnualFinancials(fiscal_year="FY2025", revenue=1100, ebit=180, pat=105, total_equity=None),
            AnnualFinancials(fiscal_year="FY2026", revenue=1200, ebit=210, pat=126, total_equity=600),
        ])
        ratios = calculate_fundamental_ratios(history)

        self.assertEqual(ratios["ROE History (%)"], {})
        self.assertIsNone(ratios["ROE (%)"])
        self.assertIsNone(ratios["Average ROE (%)"])

    def test_roe_can_be_negative_when_pat_is_negative(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2025", revenue=1000, ebit=50, pat=100, total_equity=500),
            AnnualFinancials(fiscal_year="FY2026", revenue=1100, ebit=60, pat=-20, total_equity=550),
        ])
        ratios = calculate_fundamental_ratios(history)

        expected = -20 / ((500 + 550) / 2) * 100
        self.assertEqual(ratios["ROE (%)"], round(expected, 2))


if __name__ == "__main__":
    unittest.main()
