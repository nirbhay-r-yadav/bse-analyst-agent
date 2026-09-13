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
        self.assertEqual(ratios["PAT Margin YoY Change (pp)"], 1.0)
        self.assertEqual(ratios["PAT Margin Trend"], "UP")

    def test_pat_margin_contraction_is_detected(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2024", revenue=1000, ebit=180, pat=120),
            AnnualFinancials(fiscal_year="FY2025", revenue=1100, ebit=180, pat=110),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertEqual(ratios["PAT Margin YoY Change (pp)"], -1.91)
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
