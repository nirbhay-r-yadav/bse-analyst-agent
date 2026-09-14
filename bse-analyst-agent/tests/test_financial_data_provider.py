import unittest
from unittest.mock import Mock

from src.financial_data_provider import StructuredFinancialProvider
from src.financial_tools import calculate_fundamental_ratios
from src.financial_tools import AnnualFinancials


def make_record(year: int) -> AnnualFinancials:
    return AnnualFinancials(
        fiscal_year=f"FY{year}",
        revenue=100 + year,
        ebit=20,
        pat=10,
        total_debt=5,
        total_equity=100,
        cash_equivalents=2,
        cfo=12,
        interest_expense=1,
    )


class FinancialDataProviderTests(unittest.TestCase):
    def test_more_than_ten_years_trimmed_to_latest_ten(self):
        records = [make_record(year) for year in range(2014, 2027)]
        trimmed = StructuredFinancialProvider._reliable_records(records)
        self.assertEqual(len(trimmed), 10)
        self.assertEqual(trimmed[0].fiscal_year, "FY2017")
        self.assertEqual(trimmed[-1].fiscal_year, "FY2026")

    def test_nse_xbrl_parser_preserves_missing_cash_as_none(self):
        xml = b"""
        <xbrli:xbrl
            xmlns:xbrli="http://www.xbrl.org/2003/instance"
            xmlns:in="http://example.com/in">
          <xbrli:context id="duration2026">
            <xbrli:period>
              <xbrli:startDate>2025-04-01</xbrli:startDate>
              <xbrli:endDate>2026-03-31</xbrli:endDate>
            </xbrli:period>
          </xbrli:context>

          <xbrli:context id="instant2026">
            <xbrli:period>
              <xbrli:instant>2026-03-31</xbrli:instant>
            </xbrli:period>
          </xbrli:context>

          <in:RevenueFromOperations contextRef="duration2026">1400000000</in:RevenueFromOperations>
          <in:ProfitLossAttributableToOwnersOfParent contextRef="duration2026">140000000</in:ProfitLossAttributableToOwnersOfParent>
          <in:FinanceCosts contextRef="duration2026">20000000</in:FinanceCosts>
          <in:ProfitLossBeforeTaxAndFinanceCosts contextRef="duration2026">280000000</in:ProfitLossBeforeTaxAndFinanceCosts>
          <in:CashFlowsFromUsedInOperatingActivities contextRef="duration2026">150000000</in:CashFlowsFromUsedInOperatingActivities>

          <in:Equity contextRef="instant2026">1400000000</in:Equity>
          <in:BorrowingsCurrent contextRef="instant2026">260000000</in:BorrowingsCurrent>
          <in:BorrowingsNoncurrent contextRef="instant2026">0</in:BorrowingsNoncurrent>
        </xbrli:xbrl>
        """

        provider = StructuredFinancialProvider()

        record = provider._parse_nse_xbrl(
            xml,
            "TEST",
            fiscal_year_override="FY2026",
        )

        self.assertEqual(record.fiscal_year, "FY2026")
        self.assertEqual(record.revenue, 140.0)
        self.assertEqual(record.pat, 14.0)
        self.assertEqual(record.ebit, 28.0)
        self.assertIsNone(record.cash_equivalents)
        self.assertEqual(record.total_debt, 26.0)



if __name__ == "__main__":
    unittest.main()
