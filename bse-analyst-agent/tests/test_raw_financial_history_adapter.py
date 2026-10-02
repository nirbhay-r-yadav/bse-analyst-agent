import json

from src.nse_raw_filing_selector import rank_primary_filings, select_primary_filing
from src.raw_financial_history_adapter import normalize_raw_file


def _fact(tag, value, *, start=None, end=None, instant=None, dimensions=False):
    return {
        "tag": tag,
        "value": value,
        "unit": "INR",
        "context": {
            "start_date": start,
            "end_date": end,
            "instant": instant,
            "dimensions": [],
            "has_dimensions": dimensions,
        },
    }


def test_normalize_existing_nse_shape(tmp_path):
    facts = [
        _fact("natureofreportstandaloneconsolidated", "Consolidated", instant="2026-03-31"),
        _fact("revenuefromoperations", "1786500000000", start="2025-04-01", end="2026-03-31"),
        _fact("profitorlossattributabletoownersofparent", "294400000000", start="2025-04-01", end="2026-03-31"),
        _fact("profitlossforperiod", "294740000000", start="2025-04-01", end="2026-03-31"),
        _fact("profitbeforefinancecostsandtax", "412840000000", start="2025-04-01", end="2026-03-31"),
        _fact("profitbeforetax", "399950000000", start="2025-04-01", end="2026-03-31"),
        _fact("cashflowsfromusedinoperatingactivities", "339860000000", start="2025-04-01", end="2026-03-31"),
        _fact("purchaseofpropertyplantandequipmentclassifiedasinvestingactivities", "27270000000", start="2025-04-01", end="2026-03-31"),
        _fact("cashandcashequivalents", "222010000000", instant="2026-03-31"),
        _fact("equity", "932970000000", instant="2026-03-31"),
        _fact("equityattributabletoownersofparent", "928520000000", instant="2026-03-31"),
        _fact("borrowingscurrent", "0", instant="2026-03-31"),
        _fact("borrowingsnoncurrent", "0", instant="2026-03-31"),
    ]
    path = tmp_path / "FY2026.json"
    path.write_text(json.dumps({"fiscal_year": "FY2026", "facts": facts}), encoding="utf-8")

    rows = normalize_raw_file(path)
    row = rows[0]

    assert row.basis == "consolidated"
    assert row.revenue == 178650.0
    assert row.pat == 29440.0
    assert row.ebit == 41284.0
    assert row.cfo == 33986.0
    assert row.capex == 2727.0
    assert row.debt == 0.0
    assert row.cash == 22201.0
    assert row.equity == 93297.0
    assert row.confidence == "validated"


def test_normalize_legacy_nse_shape_without_basis(tmp_path):
    facts = [
        _fact("revenuefromoperations", "1000000000", start="2018-04-01", end="2019-03-31"),
        _fact("profitlossforperiod", "100000000", start="2018-04-01", end="2019-03-31"),
        _fact("profitbeforefinancecostsandtax", "150000000", start="2018-04-01", end="2019-03-31"),
        _fact("profitbeforetax", "140000000", start="2018-04-01", end="2019-03-31"),
        _fact("cashflowsfromusedinoperatingactivities", "120000000", start="2018-04-01", end="2019-03-31"),
        _fact("purchaseofpropertyplantandequipment", "20000000", start="2018-04-01", end="2019-03-31"),
        _fact("cashandcashequivalents", "300000000", instant="2019-03-31"),
        _fact("equity", "500000000", instant="2019-03-31"),
        _fact("borrowingscurrent", "0", instant="2019-03-31"),
        _fact("borrowingsnoncurrent", "0", instant="2019-03-31"),
    ]
    path = tmp_path / "FY2019.json"
    path.write_text(json.dumps({"fiscal_year": "FY2019", "facts": facts}), encoding="utf-8")

    rows = normalize_raw_file(path)
    row = rows[0]

    assert row.basis == "unknown"
    assert row.confidence == "unvalidated"
    assert row.revenue == 100.0
    assert row.pat == 10.0


def test_segment_only_nse_filing_is_rejected(tmp_path):
    facts = [
        _fact(
            "otherexpenses",
            "1150000000",
            start="2019-01-01",
            end="2019-03-31",
            dimensions=True,
        ),
        _fact(
            "segmentrevenue",
            "5520000000",
            start="2019-01-01",
            end="2019-03-31",
            dimensions=True,
        ),
        _fact(
            "segmentliabilities",
            "0",
            instant="2019-03-31",
            dimensions=True,
        ),
    ]
    path = tmp_path / "FY2019.json"
    path.write_text(
        json.dumps({"fiscal_year": "FY2019", "facts": facts}),
        encoding="utf-8",
    )

    assert rank_primary_filings([path], "FY2019") == []
    try:
        select_primary_filing([path], "FY2019")
    except ValueError as exc:
        assert "no suitable primary financial-statement XBRL filing found" in str(exc)
    else:
        raise AssertionError("segment-only filing must not be selected")


def test_primary_filing_is_preferred_over_segment_only(tmp_path):
    segment = tmp_path / "FY2019_segment.json"
    primary = tmp_path / "FY2019_primary.json"

    segment_facts = [
        _fact(
            "segmentrevenue",
            "100000000",
            start="2018-04-01",
            end="2019-03-31",
            dimensions=True,
        ),
        _fact(
            "segmentliabilities",
            "0",
            instant="2019-03-31",
            dimensions=True,
        ),
    ]
    primary_facts = [
        _fact("revenuefromoperations", "1000000000", start="2018-04-01", end="2019-03-31"),
        _fact("profitlossforperiod", "100000000", start="2018-04-01", end="2019-03-31"),
        _fact("cashandcashequivalents", "300000000", instant="2019-03-31"),
    ]

    segment.write_text(
        json.dumps({"fiscal_year": "FY2019", "facts": segment_facts}),
        encoding="utf-8",
    )
    primary.write_text(
        json.dumps({"fiscal_year": "FY2019", "facts": primary_facts}),
        encoding="utf-8",
    )

    assert select_primary_filing([segment, primary], "FY2019") == primary
