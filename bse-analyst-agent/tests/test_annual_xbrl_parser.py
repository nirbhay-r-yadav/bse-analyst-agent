from src.annual_xbrl_parser import AnnualXBRLParser, XBRLFact


def test_detect_basis_only_when_unambiguous():
    facts = [
        XBRLFact(
            "natureofreportstandaloneconsolidated", "c1", "Consolidated", None,
            "2025-04-01", "2026-03-31", None
        )
    ]
    assert AnnualXBRLParser.detect_basis(facts) == "consolidated"


def test_detect_basis_rejects_mixed_document():
    facts = [
        XBRLFact("natureofreportstandaloneconsolidated", "c1", "Standalone", None, None, None, None),
        XBRLFact("natureofreportstandaloneconsolidated", "c2", "Consolidated", None, None, None, None),
    ]
    assert AnnualXBRLParser.detect_basis(facts) == "unknown"


def test_inr_is_normalized_to_crore():
    assert AnnualXBRLParser._to_crore(1_000_000_000, "INR") == 100.0


def test_pbt_is_not_used_as_ebit():
    facts = [
        XBRLFact(
            "profitbeforetax", "c1", 1_000_000_000, "INR",
            "2025-04-01", "2026-03-31", None
        ),
    ]
    rows = AnnualXBRLParser.normalize(facts, "annual.xml")
    assert rows[0]["pbt"] == 100.0
    assert rows[0]["ebit"] is None
