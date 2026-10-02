import json

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
