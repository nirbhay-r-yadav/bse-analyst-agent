from unittest import TestCase

from src.financial_tools import (
    AnnualFinancials,
    CompanyFinancialHistory,
    calculate_fundamental_ratios,
    calculate_pe_valuation,
    calculate_quality_score,
)


class FinancialToolsTests(TestCase):
    def test_five_year_ratios(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2022", revenue=500, ebit=80, pat=60, total_debt=100, total_equity=300, cash_equivalents=20, cfo=70),
            AnnualFinancials(fiscal_year="FY2023", revenue=600, ebit=100, pat=80, total_debt=90, total_equity=330, cash_equivalents=20, cfo=85),
            AnnualFinancials(fiscal_year="FY2024", revenue=700, ebit=120, pat=100, total_debt=80, total_equity=360, cash_equivalents=25, cfo=105),
            AnnualFinancials(fiscal_year="FY2025", revenue=800, ebit=145, pat=125, total_debt=70, total_equity=390, cash_equivalents=25, cfo=130),
            AnnualFinancials(fiscal_year="FY2026", revenue=900, ebit=170, pat=150, total_debt=60, total_equity=420, cash_equivalents=30, cfo=155),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertEqual(ratios["Years Analyzed"], 5)
        self.assertEqual(ratios["History Years Available"], 5)
        self.assertGreater(ratios["ROCE (%)"], 15)
        self.assertGreater(ratios["Revenue CAGR (%)"], 10)
        self.assertGreater(ratios["PAT CAGR (%)"], 10)
        self.assertIsNone(ratios["Revenue CAGR 10Y (%)"])
        self.assertEqual(ratios["Positive CFO Years"], "5/5")

    def test_pat_cagr_matches_compounded_growth(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2022", revenue=500, ebit=80, pat=120),
            AnnualFinancials(fiscal_year="FY2023", revenue=600, ebit=90, pat=130),
            AnnualFinancials(fiscal_year="FY2024", revenue=700, ebit=100, pat=150),
            AnnualFinancials(fiscal_year="FY2025", revenue=800, ebit=110, pat=180),
            AnnualFinancials(fiscal_year="FY2026", revenue=900, ebit=120, pat=210),
        ])
        ratios = calculate_fundamental_ratios(history)
        expected = ((210 / 120) ** (1 / 4) - 1) * 100
        self.assertAlmostEqual(ratios["PAT CAGR (%)"], round(expected, 2), places=2)

    def test_pat_cagr_can_be_negative_for_profitable_decline(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2022", revenue=1000, ebit=180, pat=200),
            AnnualFinancials(fiscal_year="FY2023", revenue=1050, ebit=170, pat=190),
            AnnualFinancials(fiscal_year="FY2024", revenue=1100, ebit=160, pat=180),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertLess(ratios["PAT CAGR (%)"], 0)

    def test_pat_margin_is_calculated_from_pat_over_revenue(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2025", revenue=1000, ebit=150, pat=100),
            AnnualFinancials(fiscal_year="FY2026", revenue=1200, ebit=180, pat=120),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertEqual(ratios["PAT Margin (%)"], 10.0)
        self.assertEqual(ratios["Latest PAT Margin (%)"], 10.0)

    def test_pat_margin_expansion_is_detected(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2025", revenue=1000, ebit=150, pat=100),
            AnnualFinancials(fiscal_year="FY2026", revenue=1100, ebit=180, pat=131),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertEqual(ratios["PAT Margin Trend"], "UP")
        self.assertEqual(ratios["PAT Margin YoY Change (pp)"], 1.91)

    def test_pat_margin_contraction_is_detected(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2025", revenue=1000, ebit=150, pat=100),
            AnnualFinancials(fiscal_year="FY2026", revenue=1000, ebit=120, pat=80),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertEqual(ratios["PAT Margin Trend"], "DOWN")
        self.assertEqual(ratios["PAT Margin YoY Change (pp)"], -2.0)

    def test_negative_pat_produces_negative_margin(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2025", revenue=1000, ebit=-50, pat=-20),
            AnnualFinancials(fiscal_year="FY2026", revenue=1000, ebit=20, pat=-10),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertEqual(ratios["Latest PAT Margin (%)"], -1.0)
        self.assertEqual(ratios["PAT Margin Trend"], "UP")

    def test_one_year_history_has_no_pat_margin_yoy_change(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2026", revenue=1000, ebit=150, pat=100),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertEqual(ratios["Latest PAT Margin (%)"], 10.0)
        self.assertIsNone(ratios["PAT Margin YoY Change (pp)"])
        self.assertEqual(ratios["PAT Margin Trend"], "FLAT")

    def test_roce_exact_calculation(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2026", revenue=1000, ebit=150, pat=100, total_debt=200, total_equity=500, cash_equivalents=50),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertEqual(ratios["ROCE (%)"], 23.08)

    def test_roce_missing_ebit_is_unavailable(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2026", revenue=1000, ebit=None, pat=100, total_debt=200, total_equity=500, cash_equivalents=50),
        ])
        self.assertIsNone(calculate_fundamental_ratios(history)["ROCE (%)"])

    def test_roce_missing_equity_is_unavailable(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2026", revenue=1000, ebit=150, pat=100, total_debt=200, total_equity=None, cash_equivalents=50),
        ])
        self.assertIsNone(calculate_fundamental_ratios(history)["ROCE (%)"])

    def test_roce_missing_debt_is_unavailable(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2026", revenue=1000, ebit=150, pat=100, total_debt=None, total_equity=500, cash_equivalents=50),
        ])
        self.assertIsNone(calculate_fundamental_ratios(history)["ROCE (%)"])

    def test_roce_missing_cash_is_unavailable(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2026", revenue=1000, ebit=150, pat=100, total_debt=200, total_equity=500, cash_equivalents=None),
        ])
        self.assertIsNone(calculate_fundamental_ratios(history)["ROCE (%)"])

    def test_roce_zero_capital_employed_is_unavailable(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2026", revenue=1000, ebit=150, pat=100, total_debt=0, total_equity=50, cash_equivalents=50),
        ])
        self.assertIsNone(calculate_fundamental_ratios(history)["ROCE (%)"])

    def test_roce_negative_capital_employed_is_unavailable(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2026", revenue=1000, ebit=150, pat=100, total_debt=0, total_equity=40, cash_equivalents=50),
        ])
        self.assertIsNone(calculate_fundamental_ratios(history)["ROCE (%)"])

    def test_roce_can_be_negative_when_ebit_is_negative(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2026", revenue=1000, ebit=-50, pat=-30, total_debt=200, total_equity=500, cash_equivalents=50),
        ])
        self.assertEqual(calculate_fundamental_ratios(history)["ROCE (%)"], -7.69)

    def test_roce_uses_latest_year(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2025", revenue=1000, ebit=100, pat=70, total_debt=100, total_equity=400, cash_equivalents=50),
            AnnualFinancials(fiscal_year="FY2026", revenue=1100, ebit=200, pat=150, total_debt=100, total_equity=440, cash_equivalents=50),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertEqual(ratios["ROCE (%)"], 40.82)

    def test_roce_trend_and_average(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2024", revenue=1000, ebit=100, pat=70, total_debt=100, total_equity=400, cash_equivalents=50),
            AnnualFinancials(fiscal_year="FY2025", revenue=1050, ebit=120, pat=80, total_debt=100, total_equity=400, cash_equivalents=50),
            AnnualFinancials(fiscal_year="FY2026", revenue=1100, ebit=150, pat=100, total_debt=100, total_equity=400, cash_equivalents=50),
        ])
        ratios = calculate_fundamental_ratios(history)
        roce_values = [
            100 / (400 + 100 - 50) * 100,
            120 / (400 + 100 - 50) * 100,
            150 / (400 + 100 - 50) * 100,
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

    def test_score_is_deterministic(self):
        result = calculate_quality_score({
            "Positive CFO Years": "5/5",
            "ROCE (%)": 20.0,
            "ROCE Trend": "UP",
            "PAT Margin Trend": "UP",
        })
        self.assertEqual(result["Score"], 95)
        self.assertEqual(result["Verdict"], "INVESTIBLE")

    def test_pe_valuation(self):
        result = calculate_pe_valuation(2.1, 20, 16)
        self.assertEqual(result["EPS"], 2.1)
        self.assertEqual(result["Fair Value"], 42.0)
        self.assertEqual(result["Buy Below"], 33.6)

    def test_governance_failure_means_avoid(self):
        result = calculate_quality_score({
            "Positive CFO Years": "5/5",
            "Governance Clean": False,
        })
        self.assertEqual(result["Verdict"], "AVOID")

    def test_seven_year_history_is_accepted(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year=f"FY{2020 + i}", revenue=500 + i * 50, ebit=80 + i * 10, pat=60 + i * 8)
            for i in range(7)
        ])
        self.assertEqual(calculate_fundamental_ratios(history)["History Years Available"], 7)

    def test_ten_year_history_is_accepted(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year=f"FY{2017 + i}", revenue=500 + i * 50, ebit=80 + i * 10, pat=60 + i * 8)
            for i in range(10)
        ])
        self.assertEqual(calculate_fundamental_ratios(history)["History Years Available"], 10)

    def test_one_year_history_is_accepted_without_fake_cagr_zero(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2026", revenue=1000, ebit=150, pat=100),
        ])
        ratios = calculate_fundamental_ratios(history)
        self.assertIsNone(ratios["Revenue CAGR (%)"])
        self.assertIsNone(ratios["PAT CAGR (%)"])

    def test_unavailable_cagr_is_not_used_as_zero_in_valuation(self):
        history = CompanyFinancialHistory(years=[
            AnnualFinancials(fiscal_year="FY2026", revenue=1000, ebit=150, pat=100),
        ])
        ratios = calculate_fundamental_ratios(history)
        valuation = calculate_pe_valuation(ratios["PAT CAGR (%)"], 20, 16)
        self.assertFalse(valuation["available"])


if __name__ == "__main__":
    import unittest
    unittest.main()
