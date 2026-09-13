import unittest

from src.financial_tools import (
    AnnualFinancials,
    CompanyFinancialHistory,
    calculate_fundamental_ratios,
    calculate_quality_score,
    calculate_pe_valuation,
    determine_final_recommendation,
)


def make_year(year: int, multiplier: float = 1.0) -> AnnualFinancials:
    step = year - 2010
    return AnnualFinancials(
        fiscal_year=f"FY{year}",
        revenue=(100 + step * 10) * multiplier,
        ebit=(20 + step * 3) * multiplier,
        pat=(10 + step * 2) * multiplier,
        total_debt=max(5, 40 - step),
        total_equity=100 + step * 12,
        cash_equivalents=10 + step,
        cfo=(12 + step * 2) * multiplier,
        interest_expense=2,
        capex=5,
    )


class FinancialToolsTests(unittest.TestCase):
    def setUp(self):
        self.history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2022", revenue=1000, ebit=180, pat=120, total_debt=100, total_equity=600, cash_equivalents=150, cfo=125, interest_expense=10, capex=40),
            AnnualFinancials(fiscal_year="FY2023", revenue=1120, ebit=205, pat=135, total_debt=90, total_equity=680, cash_equivalents=170, cfo=145, interest_expense=9, capex=45),
            AnnualFinancials(fiscal_year="FY2024", revenue=1260, ebit=230, pat=155, total_debt=80, total_equity=760, cash_equivalents=200, cfo=165, interest_expense=8, capex=50),
            AnnualFinancials(fiscal_year="FY2025", revenue=1420, ebit=260, pat=180, total_debt=70, total_equity=850, cash_equivalents=240, cfo=195, interest_expense=7, capex=55),
            AnnualFinancials(fiscal_year="FY2026", revenue=1600, ebit=300, pat=210, total_debt=60, total_equity=950, cash_equivalents=300, cfo=225, interest_expense=6, capex=60),
        ])

    def test_five_year_ratios(self):
        ratios = calculate_fundamental_ratios(self.history)
        self.assertEqual(ratios["years_analyzed"], 5)
        self.assertEqual(ratios["history_years_available"], 5)
        self.assertGreater(ratios["ROCE (%)"], 15)
        self.assertGreater(ratios["Revenue CAGR (%)"], 10)
        self.assertGreater(ratios["PAT CAGR (%)"], 10)
        self.assertIsNone(ratios["Revenue CAGR 10Y (%)"])
        self.assertEqual(ratios["Positive CFO Years"], "5/5")

    def test_roce_exact_calculation(self):
        ratios = calculate_fundamental_ratios(self.history)
        # FY2026 capital employed = equity + debt - cash = 950 + 60 - 300 = 710.
        # ROCE = EBIT / capital employed = 300 / 710 * 100 = 42.25%.
        self.assertEqual(ratios["ROCE (%)"], 42.25)

    def test_roce_trend_and_average(self):
        ratios = calculate_fundamental_ratios(self.history)
        roce_values = [
            180 / (600 + 100 - 150) * 100,
            205 / (680 + 90 - 170) * 100,
            230 / (760 + 80 - 200) * 100,
            260 / (850 + 70 - 240) * 100,
            300 / (950 + 60 - 300) * 100,
        ]
        expected_average = sum(roce_values) / len(roce_values)
        expected_yoy = roce_values[-1] - roce_values[-2]
        self.assertEqual(ratios["Average ROCE (%)"], round(expected_average, 2))
        self.assertEqual(ratios["ROCE YoY Change (pp)"], round(expected_yoy, 2))
        self.assertEqual(ratios["ROCE Trend"], "UP")

    def test_roce_trend_down(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2025", revenue=1000, ebit=200, pat=120, total_debt=100, total_equity=500, cash_equivalents=50),
            AnnualFinancials(fiscal_year="FY2026", revenue=1100, ebit=150, pat=100, total_debt=100, total_equity=550, cash_equivalents=50),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertLess(ratios["ROCE YoY Change (pp)"], 0)
        self.assertEqual(ratios["ROCE Trend"], "DOWN")

    def test_roce_trend_flat(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2025", revenue=1000, ebit=100, pat=70, total_debt=100, total_equity=400, cash_equivalents=50),
            AnnualFinancials(fiscal_year="FY2026", revenue=1100, ebit=100, pat=75, total_debt=100, total_equity=400, cash_equivalents=50),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertEqual(ratios["ROCE YoY Change (pp)"], 0.0)
        self.assertEqual(ratios["ROCE Trend"], "FLAT")

    def test_one_year_history_has_no_roce_yoy_change(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2026", revenue=1000, ebit=150, pat=100, total_debt=100, total_equity=500, cash_equivalents=50),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertIsNotNone(ratios["ROCE (%)"])
        self.assertIsNotNone(ratios["Average ROCE (%)"])
        self.assertIsNone(ratios["ROCE YoY Change (pp)"])
        self.assertEqual(ratios["ROCE Trend"], "FLAT")

    def test_roce_missing_ebit_is_unavailable(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2025", revenue=1000, ebit=150, pat=100, total_debt=100, total_equity=500, cash_equivalents=50),
            AnnualFinancials(fiscal_year="FY2026", revenue=1100, ebit=None, pat=110, total_debt=90, total_equity=550, cash_equivalents=60),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertIsNone(ratios["ROCE (%)"])

    def test_roce_missing_equity_is_unavailable(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2025", revenue=1000, ebit=150, pat=100, total_debt=100, total_equity=500, cash_equivalents=50),
            AnnualFinancials(fiscal_year="FY2026", revenue=1100, ebit=160, pat=110, total_debt=90, total_equity=None, cash_equivalents=60),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertIsNone(ratios["ROCE (%)"])

    def test_roce_missing_debt_is_unavailable(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2025", revenue=1000, ebit=150, pat=100, total_debt=100, total_equity=500, cash_equivalents=50),
            AnnualFinancials(fiscal_year="FY2026", revenue=1100, ebit=160, pat=110, total_debt=None, total_equity=550, cash_equivalents=60),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertIsNone(ratios["ROCE (%)"])

    def test_roce_missing_cash_is_unavailable(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2025", revenue=1000, ebit=150, pat=100, total_debt=100, total_equity=500, cash_equivalents=50),
            AnnualFinancials(fiscal_year="FY2026", revenue=1100, ebit=160, pat=110, total_debt=90, total_equity=550, cash_equivalents=None),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertIsNone(ratios["ROCE (%)"])

    def test_roce_zero_capital_employed_is_unavailable(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2026", revenue=1000, ebit=150, pat=100, total_debt=100, total_equity=50, cash_equivalents=150),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertIsNone(ratios["ROCE (%)"])

    def test_roce_negative_capital_employed_is_unavailable(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2026", revenue=1000, ebit=150, pat=100, total_debt=50, total_equity=50, cash_equivalents=150),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertIsNone(ratios["ROCE (%)"])

    def test_roce_can_be_negative_when_ebit_is_negative(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2026", revenue=1000, ebit=-50, pat=-20, total_debt=100, total_equity=500, cash_equivalents=50),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertEqual(ratios["ROCE (%)"], -9.09)

    def test_roce_uses_latest_year(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2024", revenue=1000, ebit=100, pat=70, total_debt=100, total_equity=400, cash_equivalents=50),
            AnnualFinancials(fiscal_year="FY2025", revenue=1100, ebit=200, pat=120, total_debt=100, total_equity=500, cash_equivalents=50),
            AnnualFinancials(fiscal_year="FY2026", revenue=1200, ebit=180, pat=110, total_debt=100, total_equity=600, cash_equivalents=50),
        ])
        ratios = calculate_fundamental_ratios(history)
        # Latest-year ROCE = 180 / (600 + 100 - 50) * 100 = 27.69%.
        self.assertEqual(ratios["ROCE (%)"], 27.69)

    def test_pat_cagr_matches_compounded_growth(self):
        ratios = calculate_fundamental_ratios(self.history)
        # PAT grows from 120 to 210 across four year-to-year intervals.
        expected = ((210 / 120) ** (1 / 4) - 1) * 100
        self.assertAlmostEqual(ratios["PAT CAGR (%)"], round(expected, 2), places=2)

    def test_pat_cagr_can_be_negative_for_profitable_decline(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2022", revenue=1000, ebit=150, pat=100),
            AnnualFinancials(fiscal_year="FY2023", revenue=1050, ebit=140, pat=90),
            AnnualFinancials(fiscal_year="FY2024", revenue=1100, ebit=130, pat=80),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertLess(ratios["PAT CAGR (%)"], 0)

    def test_pat_margin_is_calculated_from_pat_over_revenue(self):
        ratios = calculate_fundamental_ratios(self.history)
        self.assertEqual(ratios["Latest PAT Margin (%)"], round(210 / 1600 * 100, 2))
        expected_average = sum([
            120 / 1000 * 100,
            135 / 1120 * 100,
            155 / 1260 * 100,
            180 / 1420 * 100,
            210 / 1600 * 100,
        ]) / 5
        self.assertEqual(ratios["Average PAT Margin (%)"], round(expected_average, 2))

    def test_pat_margin_expansion_is_detected(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2024", revenue=1000, ebit=150, pat=80),
            AnnualFinancials(fiscal_year="FY2025", revenue=1100, ebit=180, pat=100),
            AnnualFinancials(fiscal_year="FY2026", revenue=1200, ebit=220, pat=132),
        ])
        ratios = calculate_fundamental_ratios(history)
        # FY2025 margin = 9.09%; FY2026 margin = 11.00%; expansion = 1.91pp.
        self.assertEqual(ratios["PAT Margin YoY Change (pp)"], 1.91)
        self.assertEqual(ratios["PAT Margin Trend"], "UP")

    def test_pat_margin_contraction_is_detected(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2024", revenue=1000, ebit=180, pat=120),
            AnnualFinancials(fiscal_year="FY2025", revenue=1100, ebit=180, pat=110),
        ])
        ratios = calculate_fundamental_ratios(history)
        # FY2024 margin = 12.00%; FY2025 margin = 10.00%; contraction = -2.00pp.
        self.assertEqual(ratios["PAT Margin YoY Change (pp)"], -2.0)
        self.assertEqual(ratios["PAT Margin Trend"], "DOWN")

    def test_negative_pat_produces_negative_margin(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2025", revenue=1000, ebit=50, pat=-20),
            AnnualFinancials(fiscal_year="FY2026", revenue=1100, ebit=60, pat=-11),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertEqual(ratios["Latest PAT Margin (%)"], -1.0)
        self.assertEqual(ratios["PAT Margin YoY Change (pp)"], 1.0)
        self.assertEqual(ratios["PAT Margin Trend"], "UP")

    def test_one_year_history_has_no_pat_margin_yoy_change(self):
        history = CompanyFinancialHistory(years=[make_year(2026)])
        ratios = calculate_fundamental_ratios(history)
        self.assertIsNotNone(ratios["Latest PAT Margin (%)"])
        self.assertIsNotNone(ratios["Average PAT Margin (%)"])
        self.assertIsNone(ratios["PAT Margin YoY Change (pp)"])
        self.assertEqual(ratios["PAT Margin Trend"], "FLAT")

    def test_ten_year_pat_margin_and_roce_history(self):
        history = CompanyFinancialHistory(years=[make_year(year) for year in range(2017, 2027)])
        ratios = calculate_fundamental_ratios(history)

        self.assertEqual(ratios["years_analyzed"], 10)
        self.assertEqual(ratios["history_years_available"], 10)
        self.assertEqual(len(ratios["PAT Margin History (%)"]), 10)
        self.assertEqual(len(ratios["ROCE History (%)"]), 10)
        self.assertEqual(list(ratios["PAT Margin History (%)"].keys())[0], "FY2017")
        self.assertEqual(list(ratios["PAT Margin History (%)"].keys())[-1], "FY2026")
        self.assertEqual(list(ratios["ROCE History (%)"].keys())[0], "FY2017")
        self.assertEqual(list(ratios["ROCE History (%)"].keys())[-1], "FY2026")

        expected_margins = [
            make_year(year).pat / make_year(year).revenue * 100
            for year in range(2017, 2027)
        ]
        expected_roce = [
            make_year(year).ebit / (
                make_year(year).total_equity
                + make_year(year).total_debt
                - make_year(year).cash_equivalents
            ) * 100
            for year in range(2017, 2027)
        ]

        self.assertEqual(
            list(ratios["PAT Margin History (%)"].values()),
            [round(value, 2) for value in expected_margins],
        )
        self.assertEqual(
            list(ratios["ROCE History (%)"].values()),
            [round(value, 2) for value in expected_roce],
        )
        self.assertEqual(ratios["Minimum PAT Margin (%)"], round(min(expected_margins), 2))
        self.assertEqual(ratios["Maximum PAT Margin (%)"], round(max(expected_margins), 2))
        self.assertEqual(ratios["PAT Margin Range (pp)"], round(max(expected_margins) - min(expected_margins), 2))
        self.assertEqual(ratios["Minimum ROCE (%)"], round(min(expected_roce), 2))
        self.assertEqual(ratios["Maximum ROCE (%)"], round(max(expected_roce), 2))
        self.assertEqual(ratios["ROCE Range (pp)"], round(max(expected_roce) - min(expected_roce), 2))

    def test_ten_year_pat_margin_and_roce_use_all_valid_years(self):
        years = [make_year(year) for year in range(2017, 2027)]
        years[3] = AnnualFinancials(
            fiscal_year="FY2020",
            revenue=years[3].revenue,
            ebit=None,
            pat=years[3].pat,
            total_debt=years[3].total_debt,
            total_equity=years[3].total_equity,
            cash_equivalents=years[3].cash_equivalents,
        )
        history = CompanyFinancialHistory(years=years)
        ratios = calculate_fundamental_ratios(history)

        self.assertEqual(len(ratios["PAT Margin History (%)"]), 10)
        self.assertEqual(len(ratios["ROCE History (%)"]), 9)
        self.assertNotIn("FY2020", ratios["ROCE History (%)"])
        self.assertIn("FY2020", ratios["PAT Margin History (%)"])

    def test_score_is_deterministic(self):
        ratios = calculate_fundamental_ratios(self.history)
        score = calculate_quality_score(ratios, governance_clean=True)
        self.assertEqual(score["score_100"], 95)
        self.assertEqual(score["rating"], "INVESTIBLE")

    def test_pe_valuation(self):
        value = calculate_pe_valuation(2000, 100, 210, 10, target_pe=20, margin_of_safety_pct=20)
        self.assertTrue(value["available"])
        self.assertEqual(value["eps"], 2.1)
        self.assertEqual(value["fair_value"], 42.0)
        self.assertEqual(value["buy_below"], 33.6)

    def test_governance_failure_means_avoid(self):
        ratios = calculate_fundamental_ratios(self.history)
        quality = calculate_quality_score(ratios, governance_clean=False)
        decision = determine_final_recommendation(quality, ratios, forensic_clean=False)
        self.assertEqual(decision["verdict"], "AVOID")

    def test_ten_year_history_is_accepted(self):
        history = CompanyFinancialHistory(years=[make_year(year) for year in range(2017, 2027)])
        ratios = calculate_fundamental_ratios(history)
        self.assertEqual(ratios["history_years_available"], 10)
        self.assertIsNotNone(ratios["Revenue CAGR 10Y (%)"])
        self.assertEqual(ratios["trends"]["revenue"], "UP")

    def test_seven_year_history_is_accepted(self):
        history = CompanyFinancialHistory(years=[make_year(year) for year in range(2020, 2027)])
        ratios = calculate_fundamental_ratios(history)
        self.assertEqual(ratios["history_years_available"], 7)
        self.assertIsNotNone(ratios["Revenue CAGR 5Y (%)"])
        self.assertIsNone(ratios["Revenue CAGR 10Y (%)"])

    def test_one_year_history_is_accepted_without_fake_cagr_zero(self):
        history = CompanyFinancialHistory(years=[make_year(2026)])
        ratios = calculate_fundamental_ratios(history)
        self.assertEqual(ratios["history_years_available"], 1)
        self.assertIsNone(ratios["Revenue YoY Growth (%)"])
        self.assertIsNone(ratios["Revenue CAGR (%)"])
        self.assertIsNone(ratios["PAT CAGR (%)"])
        self.assertIsNone(ratios["Revenue CAGR 3Y (%)"])
        self.assertNotEqual(ratios["Revenue CAGR (%)"], 0.0)

    def test_unavailable_cagr_is_not_used_as_zero_in_valuation(self):
        value = calculate_pe_valuation(2000, 100, 210, None, target_pe=20, margin_of_safety_pct=20)
        self.assertFalse(value["available"])
        self.assertIn("PAT CAGR is unavailable", value["reason"])


if __name__ == "__main__":
    unittest.main()
