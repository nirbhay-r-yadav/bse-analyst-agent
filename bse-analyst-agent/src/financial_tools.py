from typing import Dict, Any, List
import re
from pydantic import BaseModel, Field, model_validator

from .history_policy import MIN_YEARS_CAGR, MIN_YEARS_CONSISTENCY, MIN_YEARS_TREND, valid_history


class AnnualFinancials(BaseModel):
    fiscal_year: str = Field(description="Fiscal year label, e.g. FY2026")
    revenue: float = Field(description="Revenue from operations, INR Cr")
    ebit: float | None = Field(default=None, description="Operating profit / EBIT, INR Cr")
    pat: float = Field(description="Profit after tax attributable to shareholders, INR Cr")
    total_debt: float | None = Field(default=None, description="Total debt including lease liabilities, INR Cr")
    total_equity: float | None = Field(default=None, description="Shareholders' equity / net worth, INR Cr")
    cash_equivalents: float | None = Field(default=None, description="Cash, cash equivalents and current investments, INR Cr")
    cfo: float | None = Field(default=None, description="Cash flow from operating activities, INR Cr")
    interest_expense: float | None = Field(default=None, description="Finance costs / interest expense, INR Cr")
    capex: float | None = Field(default=None, description="Capital expenditure / purchase of PPE and intangibles, INR Cr; positive amount")

    @model_validator(mode="after")
    def validate_data(self):
        if not re.fullmatch(r"FY\d{4}", self.fiscal_year):
            raise ValueError("fiscal_year must use the format FY20XX")
        if self.revenue <= 0:
            raise ValueError("revenue must be greater than zero")
        return self


class CompanyFinancialHistory(BaseModel):
    years: List[AnnualFinancials] = Field(min_length=1, max_length=10, description="Up to 10 available fiscal years in chronological order, oldest first; fewer years are valid")

    @model_validator(mode="after")
    def validate_history(self):
        fiscal_years = [year.fiscal_year for year in self.years]
        if len(fiscal_years) != len(set(fiscal_years)):
            raise ValueError("fiscal years must be unique")
        numeric_years = [int(year[2:]) for year in fiscal_years]
        if numeric_years != sorted(numeric_years):
            raise ValueError("fiscal years must be in chronological order, oldest first")
        return self


CompanyFinancialInputs = AnnualFinancials


def _growth(new: float, old: float) -> float | None:
    return ((new - old) / old * 100.0) if old else None


def _cagr(new: float, old: float, periods: int) -> float | None:
    if periods <= 0 or old <= 0 or new <= 0:
        return None
    return ((new / old) ** (1 / periods) - 1) * 100.0


def calculate_fundamental_ratios(data: CompanyFinancialHistory) -> Dict[str, Any]:
    years = data.years
    latest = years[-1]
    prior = years[-2] if len(years) >= 2 else None

    def calculate_roce(year: AnnualFinancials) -> float | None:
        if year.total_equity is None or year.total_debt is None or year.cash_equivalents is None or year.ebit is None:
            return None
        capital_employed = year.total_equity + year.total_debt - year.cash_equivalents
        if capital_employed <= 0:
            return None
        return year.ebit / capital_employed * 100

    roce = calculate_roce(latest)
    prior_roce = calculate_roce(prior) if prior else None
    roce_yoy_change = roce - prior_roce if roce is not None and prior_roce is not None else None
    roce_trend = "FLAT"
    if roce_yoy_change is not None:
        roce_trend = "UP" if roce_yoy_change > 0 else "DOWN" if roce_yoy_change < 0 else "FLAT"
    roce_values = [(year.fiscal_year, calculate_roce(year)) for year in years]
    valid_roce_values = [value for _, value in roce_values if value is not None]
    roce_history = {fiscal_year: round(value, 2) for fiscal_year, value in roce_values if value is not None}
    average_roce = sum(valid_roce_values) / len(valid_roce_values) if valid_roce_values else None

    def calculate_roe(index: int) -> float | None:
        if index <= 0:
            return None
        current = years[index]
        previous = years[index - 1]
        if current.total_equity is None or previous.total_equity is None:
            return None
        average_equity = (previous.total_equity + current.total_equity) / 2
        if average_equity <= 0:
            return None
        return current.pat / average_equity * 100

    roe = calculate_roe(len(years) - 1)
    prior_roe = calculate_roe(len(years) - 2) if len(years) >= 3 else None
    roe_yoy_change = roe - prior_roe if roe is not None and prior_roe is not None else None
    roe_trend = "FLAT"
    if roe_yoy_change is not None:
        roe_trend = "UP" if roe_yoy_change > 0 else "DOWN" if roe_yoy_change < 0 else "FLAT"
    roe_values = [(year.fiscal_year, calculate_roe(index)) for index, year in enumerate(years)]
    valid_roe_values = [value for _, value in roe_values if value is not None]
    roe_history = {fiscal_year: round(value, 2) for fiscal_year, value in roe_values if value is not None}
    average_roe = sum(valid_roe_values) / len(valid_roe_values) if valid_roe_values else None

    net_debt = latest.total_debt - latest.cash_equivalents if latest.total_debt is not None and latest.cash_equivalents is not None else None
    de_ratio = latest.total_debt / latest.total_equity if latest.total_debt is not None and latest.total_equity not in (None, 0) else None
    interest_coverage = latest.ebit / latest.interest_expense if latest.ebit is not None and latest.interest_expense is not None and latest.interest_expense > 0 else None
    cfo_to_pat = latest.cfo / latest.pat if latest.cfo is not None and latest.pat > 0 else None
    rev_growth_yoy = _growth(latest.revenue, prior.revenue) if prior else None
    pat_growth_yoy = _growth(latest.pat, prior.pat) if prior else None

    valid_revenue = valid_history([year.revenue for year in years])
    valid_pat = valid_history([year.pat for year in years])
    revenue_cagr = _cagr(valid_revenue[-1], valid_revenue[0], len(valid_revenue) - 1) if len(valid_revenue) >= MIN_YEARS_CAGR else None
    pat_cagr = _cagr(valid_pat[-1], valid_pat[0], len(valid_pat) - 1) if len(valid_pat) >= MIN_YEARS_CAGR else None

    def period_cagr(field: str, period: int) -> float | None:
        if period <= 1:
            return None
        values = valid_history([getattr(year, field) for year in years])
        if len(values) < period:
            return None
        old = values[-period]
        new = values[-1]
        return _cagr(new, old, period - 1)

    revenue_cagr_3y = period_cagr("revenue", 3)
    revenue_cagr_5y = period_cagr("revenue", 5)
    revenue_cagr_10y = period_cagr("revenue", 10)

    margin_values = [(year.fiscal_year, year.pat / year.revenue * 100) for year in years if year.revenue > 0]
    margins = [value for _, value in margin_values]
    pat_margin_history = {fiscal_year: round(value, 2) for fiscal_year, value in margin_values}
    latest_margin = margins[-1] if margins else None
    avg_margin = sum(margins) / len(margins) if margins else None
    margin_range = max(margins) - min(margins) if margins else None
    pat_margin_yoy_change = latest_margin - margins[-2] if len(margins) >= 2 else None
    pat_margin_trend = "FLAT"
    if pat_margin_yoy_change is not None:
        pat_margin_trend = "UP" if pat_margin_yoy_change > 0 else "DOWN" if pat_margin_yoy_change < 0 else "FLAT"

    cfo_values = [y.cfo for y in years if y.cfo is not None]
    positive_cfo_years = sum(1 for value in cfo_values if value > 0)
    cfo_positive_ratio = positive_cfo_years / len(cfo_values) if cfo_values else None
    conversion = [y.cfo / y.pat for y in years if y.cfo is not None and y.pat > 0]
    avg_cash_conversion = sum(conversion) / len(conversion) if conversion else None

    revenue_trend = "FLAT"
    if len(years) >= 2:
        revenue_trend = "UP" if latest.revenue > prior.revenue else "DOWN" if latest.revenue < prior.revenue else "FLAT"
    pat_trend = "FLAT"
    if len(years) >= 2:
        pat_trend = "UP" if latest.pat > prior.pat else "DOWN" if latest.pat < prior.pat else "FLAT"

    hurdles = {
        "roce_above_15": roce is not None and roce >= 15.0,
        "clean_debt": (de_ratio is not None and de_ratio <= 1.0) or (net_debt is not None and net_debt <= 0),
        "cash_conversion_sound": cfo_to_pat is not None and cfo_to_pat >= 0.70,
        "healthy_coverage": interest_coverage is not None and interest_coverage >= 3.5,
        "cfo_history_sufficient": len(cfo_values) >= MIN_YEARS_CONSISTENCY,
        "cfo_positive_consistency": cfo_positive_ratio is not None and cfo_positive_ratio >= 0.70,
    }

    return {
        "years_analyzed": len(years),
        "history_years_available": len(years),
        "latest_fiscal_year": latest.fiscal_year,
        "ROCE (%)": round(roce, 2) if roce is not None else None,
        "Average ROCE (%)": round(average_roce, 2) if average_roce is not None else None,
        "ROCE History (%)": roce_history,
        "Minimum ROCE (%)": round(min(valid_roce_values), 2) if valid_roce_values else None,
        "Maximum ROCE (%)": round(max(valid_roce_values), 2) if valid_roce_values else None,
        "ROCE Range (pp)": round(max(valid_roce_values) - min(valid_roce_values), 2) if valid_roce_values else None,
        "ROCE YoY Change (pp)": round(roce_yoy_change, 2) if roce_yoy_change is not None else None,
        "ROCE Trend": roce_trend,
        "ROE (%)": round(roe, 2) if roe is not None else None,
        "Average ROE (%)": round(average_roe, 2) if average_roe is not None else None,
        "ROE History (%)": roe_history,
        "Minimum ROE (%)": round(min(valid_roe_values), 2) if valid_roe_values else None,
        "Maximum ROE (%)": round(max(valid_roe_values), 2) if valid_roe_values else None,
        "ROE Range (pp)": round(max(valid_roe_values) - min(valid_roe_values), 2) if valid_roe_values else None,
        "ROE YoY Change (pp)": round(roe_yoy_change, 2) if roe_yoy_change is not None else None,
        "ROE Trend": roe_trend,
        "Revenue YoY Growth (%)": round(rev_growth_yoy, 2) if rev_growth_yoy is not None else None,
        "PAT YoY Growth (%)": round(pat_growth_yoy, 2) if pat_growth_yoy is not None else None,
        "Revenue CAGR (%)": round(revenue_cagr, 2) if revenue_cagr is not None else None,
        "PAT CAGR (%)": round(pat_cagr, 2) if pat_cagr is not None else None,
        "Revenue CAGR 3Y (%)": round(revenue_cagr_3y, 2) if revenue_cagr_3y is not None else None,
        "Revenue CAGR 5Y (%)": round(revenue_cagr_5y, 2) if revenue_cagr_5y is not None else None,
        "Revenue CAGR 10Y (%)": round(revenue_cagr_10y, 2) if revenue_cagr_10y is not None else None,
        "Latest PAT Margin (%)": round(latest_margin, 2) if latest_margin is not None else None,
        "Average PAT Margin (%)": round(avg_margin, 2) if avg_margin is not None else None,
        "PAT Margin History (%)": pat_margin_history,
        "Minimum PAT Margin (%)": round(min(margins), 2) if margins else None,
        "Maximum PAT Margin (%)": round(max(margins), 2) if margins else None,
        "PAT Margin Range (pp)": round(margin_range, 2) if margin_range is not None else None,
        "PAT Margin YoY Change (pp)": round(pat_margin_yoy_change, 2) if pat_margin_yoy_change is not None else None,
        "PAT Margin Trend": pat_margin_trend,
        "Debt to Equity": round(de_ratio, 2) if de_ratio is not None else None,
        "Net Debt (Cr)": round(net_debt, 2) if net_debt is not None else None,
        "Interest Coverage Ratio": round(interest_coverage, 2) if interest_coverage is not None else None,
        "CFO / PAT Quality Ratio": round(cfo_to_pat, 2) if cfo_to_pat is not None else None,
        "Average CFO / PAT (Available History)": round(avg_cash_conversion, 2) if avg_cash_conversion is not None else None,
        "Positive CFO Years": f"{positive_cfo_years}/{len(cfo_values)}",
        "CFO Positive Ratio (%)": round(cfo_positive_ratio * 100, 2) if cfo_positive_ratio is not None else None,
        "trends": {"revenue": revenue_trend, "pat": pat_trend},
        "hurdles_passed": hurdles,
    }


def calculate_quality_score(ratios: Dict[str, Any], governance_clean: bool = True) -> Dict[str, Any]:
    """Deterministic 100-point score. LLM explains the result; Python owns the score."""
    roce = ratios["ROCE (%)"]
    revenue_cagr = ratios["Revenue CAGR (%)"]
    pat_cagr = ratios["PAT CAGR (%)"]
    net_debt = ratios["Net Debt (Cr)"]
    de_ratio = ratios["Debt to Equity"]
    cfo_quality = ratios["CFO / PAT Quality Ratio"]
    avg_conversion = ratios["Average CFO / PAT (Available History)"]
    components = {
        "capital_efficiency": 20 if roce is not None and roce >= 20 else 15 if roce is not None and roce >= 15 else 8 if roce is not None and roce >= 10 else 0,
        "growth": 20 if revenue_cagr is not None and pat_cagr is not None and revenue_cagr >= 15 and pat_cagr >= 15 else 15 if revenue_cagr is not None and pat_cagr is not None and revenue_cagr >= 10 and pat_cagr >= 10 else 8 if revenue_cagr is not None and revenue_cagr >= 5 else 0,
        "balance_sheet": 20 if net_debt is not None and net_debt <= 0 else 15 if de_ratio is not None and de_ratio <= 0.5 else 10 if de_ratio is not None and de_ratio <= 1 else 0,
        "cash_quality": 20 if cfo_quality is not None and avg_conversion is not None and cfo_quality >= 1 and avg_conversion >= 0.8 else 15 if cfo_quality is not None and avg_conversion is not None and cfo_quality >= 0.7 and avg_conversion >= 0.7 else 8 if avg_conversion is not None and avg_conversion >= 0.5 else 0,
        "governance": 20 if governance_clean else 0,
    }
    score = sum(components.values())
    rating = "INVESTIBLE" if score >= 80 else "WATCHLIST" if score >= 60 else "AVOID"
    return {"score_100": score, "rating": rating, "components": components}


def calculate_pe_valuation(current_price: float, shares_outstanding_cr: float, latest_pat_cr: float, pat_cagr_pct: float | None, target_pe: float = 25.0, margin_of_safety_pct: float = 20.0) -> Dict[str, Any]:
    if current_price <= 0 or shares_outstanding_cr <= 0 or latest_pat_cr <= 0:
        return {"available": False, "reason": "Valid price, shares outstanding and PAT are required."}
    if pat_cagr_pct is None:
        return {"available": False, "reason": "PAT CAGR is unavailable; valuation is withheld rather than treating missing growth as zero."}
    eps = latest_pat_cr / shares_outstanding_cr
    fair_value = eps * target_pe
    buy_below = fair_value * (1 - margin_of_safety_pct / 100.0)
    market_cap_cr = current_price * shares_outstanding_cr
    implied_pe = current_price / eps if eps else 0.0
    return {
        "available": True,
        "current_price": round(current_price, 2),
        "market_cap_cr": round(market_cap_cr, 2),
        "eps": round(eps, 2),
        "current_pe": round(implied_pe, 2),
        "target_pe": round(target_pe, 2),
        "fair_value": round(fair_value, 2),
        "margin_of_safety_pct": round(margin_of_safety_pct, 2),
        "buy_below": round(buy_below, 2),
        "upside_to_fair_value_pct": round((fair_value / current_price - 1) * 100, 2),
        "pat_cagr_used_pct": round(pat_cagr_pct, 2),
    }


def determine_final_recommendation(quality: Dict[str, Any], ratios: Dict[str, Any], forensic_clean: bool, valuation: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Deterministic final decision; avoids allowing an LLM to override hard risk rules."""
    cfo_history_sufficient = ratios.get("hurdles_passed", {}).get("cfo_history_sufficient", False)
    cfo_positive_consistency = ratios.get("hurdles_passed", {}).get("cfo_positive_consistency", False)
    if not forensic_clean or (cfo_history_sufficient and not cfo_positive_consistency):
        return {"verdict": "AVOID", "reason": "Governance/forensic clearance failed or available operating cash flow history is persistently weak."}

    score = quality["score_100"]
    if score < 60:
        return {"verdict": "AVOID", "reason": "Quality score is below the minimum 60/100 threshold."}

    if valuation and valuation.get("available"):
        price = valuation["current_price"]
        buy_below = valuation["buy_below"]
        fair_value = valuation["fair_value"]
        if score >= 80 and price <= buy_below:
            return {"verdict": "BUY", "reason": "High quality and price is at or below the margin-of-safety level."}
        if price <= fair_value:
            return {"verdict": "WATCH/BUY", "reason": "Quality clears the minimum threshold and price is at or below fair value."}
        return {"verdict": "WATCH", "reason": "Quality is acceptable but price is above fair value."}

    return {"verdict": "WATCH", "reason": "Quality clears the minimum threshold; valuation is unavailable."}
