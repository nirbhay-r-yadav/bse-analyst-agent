from pathlib import Path

from src.business_analysis.business_classifier import classify_business
from src.business_analysis.metrics import analyze_financial_economics
from src.business_analysis.models import BusinessAnalysisResult


def test_business_classifier_identifies_technology_service_signals():
    result=classify_business("We provide software services, cloud services and digital transformation solutions.")
    assert result["business_type"]=="technology_services"


def test_business_economics_is_deterministic():
    rows=[
        {"fiscal_year":"FY2025","revenue":1000,"ebit":220,"pat":160,"cfo":170,"debt":100,"cash":50,"equity":700,"capex":60},
        {"fiscal_year":"FY2026","revenue":1200,"ebit":276,"pat":198,"cfo":205,"debt":80,"cash":70,"equity":780,"capex":72},
    ]
    result=analyze_financial_economics(rows)
    assert round(result["revenue_yoy_pct"],2)==20.00
    assert round(result["ebit_margin_pct"],2)==23.00
    assert round(result["pat_margin_pct"],2)==16.50
    assert round(result["cfo_pat_ratio"],2)==1.04
    assert round(result["capex_to_revenue_pct"],2)==6.00


def test_result_serializes():
    result=BusinessAnalysisResult(symbol="INFY")
    assert result.to_dict()["symbol"]=="INFY"
