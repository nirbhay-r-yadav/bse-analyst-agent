from src.business_analysis.business_classifier import classify_business
from src.business_analysis.models import BusinessAnalysisResult


def test_business_classifier_identifies_technology_service_signals():
    result = classify_business(
        "We provide software services, cloud services and digital transformation solutions."
    )
    assert result["business_type"] == "technology_services"


def test_result_serializes_without_financial_analysis_fields():
    result = BusinessAnalysisResult(symbol="INFY")
    payload = result.to_dict()
    assert payload["symbol"] == "INFY"
    assert "business_economics" not in payload


def test_result_contains_business_risk_sections():
    result = BusinessAnalysisResult(symbol="INFY")
    payload = result.to_dict()
    assert "business_model" in payload
    assert "management_promises" in payload
    assert "management_execution" in payload
    assert "risks" in payload
    assert "evidence" in payload
