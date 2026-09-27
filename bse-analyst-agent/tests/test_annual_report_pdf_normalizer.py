from src.annual_report_pdf_normalizer import _number, _to_crore


def test_pdf_number_parsing():
    assert _number("1,234.50") == 1234.5
    assert _number("(123.50)") == -123.5
    assert _number("-") is None


def test_pdf_unit_conversion():
    assert _to_crore(1000, "Amounts in ₹ crore") == 1000
    assert _to_crore(1000, "Amounts in ₹ lakhs") == 10
    assert _to_crore(1000, "Amounts in millions") == 100
