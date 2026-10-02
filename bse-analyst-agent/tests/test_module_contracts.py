from src.contracts import PUBLIC_MODULE_APIS


def test_public_module_api_contract_is_complete():
    expected = {
        "discovery",
        "risk",
        "financial_engine",
        "financial_ratios",
        "quality_score",
        "valuation",
        "recommendation",
        "annual_report",
        "annual_report_history",
        "annual_report_inventory",
        "financial_history",
        "financial_history_adapter",
        "business_analysis",
        "document_parser",
        "stock_research",
        "deep_scan",
        "reporting",
    }
    assert set(PUBLIC_MODULE_APIS) == expected


def test_public_module_apis_do_not_depend_on_menu_or_main():
    assert all("src.menu" not in path for path in PUBLIC_MODULE_APIS.values())
    assert all(path != "main" and not path.startswith("main.") for path in PUBLIC_MODULE_APIS.values())


def test_engine_contracts_point_to_replaceable_classes():
    assert PUBLIC_MODULE_APIS["financial_engine"].startswith("src.financial_engine.")
    assert PUBLIC_MODULE_APIS["stock_research"].startswith("src.stock_research_engine.")
    assert PUBLIC_MODULE_APIS["deep_scan"].startswith("src.deep_scanner.")
    assert PUBLIC_MODULE_APIS["risk"].startswith("src.corporate_risk.")
