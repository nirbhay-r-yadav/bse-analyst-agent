from __future__ import annotations

from typing import Any, Iterable


def _valid(rows: Iterable[dict[str, Any]], field: str) -> list[tuple[str, float]]:
    values=[]
    for row in rows:
        value=row.get(field)
        if isinstance(value,(int,float)) and value is not None:
            values.append((str(row.get("fiscal_year")),float(value)))
    return values


def _pct(num: float | None, den: float | None) -> float | None:
    if num is None or den in (None,0):
        return None
    return num/den*100.0


def analyze_financial_economics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows=sorted(rows,key=lambda r:int(str(r.get("fiscal_year","FY0"))[2:]))
    latest=rows[-1] if rows else {}
    previous=rows[-2] if len(rows)>1 else {}
    revenue=_valid(rows,"revenue")
    pat=_valid(rows,"pat")
    ebit=_valid(rows,"ebit")
    cfo=_valid(rows,"cfo")
    debt=_valid(rows,"debt")
    cash=_valid(rows,"cash")
    equity=_valid(rows,"equity")

    revenue_growth=_pct(latest.get("revenue")-previous.get("revenue"),previous.get("revenue")) if previous.get("revenue") else None
    pat_margin=_pct(latest.get("pat"),latest.get("revenue"))
    ebit_margin=_pct(latest.get("ebit"),latest.get("revenue"))
    cfo_pat=(latest.get("cfo")/latest.get("pat")) if latest.get("cfo") is not None and latest.get("pat") not in (None,0) else None
    net_debt=(latest.get("debt")-latest.get("cash")) if latest.get("debt") is not None and latest.get("cash") is not None else None
    capital_employed=(latest.get("equity")+latest.get("debt")-latest.get("cash")) if all(latest.get(k) is not None for k in ("equity","debt","cash")) else None
    roce=_pct(latest.get("ebit"),capital_employed)

    capex=[]
    for row in rows:
        value=row.get("capex")
        if isinstance(value,(int,float)):
            capex.append((str(row.get("fiscal_year")),abs(float(value))))
    latest_capex=capex[-1][1] if capex else None
    capex_revenue=_pct(latest_capex,latest.get("revenue"))
    wc_proxy=None
    if latest.get("revenue") and latest.get("cfo") is not None and latest.get("pat") is not None:
        # CFO-vs-PAT is only a cash-conversion proxy; it is not presented as working capital itself.
        wc_proxy=latest.get("cfo")-latest.get("pat")

    return {
        "years_available":len(rows),
        "latest_fiscal_year":latest.get("fiscal_year"),
        "revenue_cagr_approx":_cagr(revenue),
        "revenue_yoy_pct":revenue_growth,
        "ebit_margin_pct":ebit_margin,
        "pat_margin_pct":pat_margin,
        "cfo_pat_ratio":cfo_pat,
        "net_debt_cr":net_debt,
        "roce_pct":roce,
        "latest_capex_cr":latest_capex,
        "capex_to_revenue_pct":capex_revenue,
        "cash_conversion_proxy_cr":wc_proxy,
        "positive_cfo_years":sum(1 for _,v in cfo if v>0),
        "cfo_years":len(cfo),
        "revenue_history":dict(revenue),
        "pat_history":dict(pat),
        "ebit_history":dict(ebit),
        "debt_history":dict(debt),
        "cash_history":dict(cash),
        "equity_history":dict(equity),
    }


def _cagr(values: list[tuple[str,float]]) -> float | None:
    if len(values)<2 or values[0][1]<=0 or values[-1][1]<=0:
        return None
    periods=int(values[-1][0][2:])-int(values[0][0][2:])
    if periods<=0:
        return None
    return ((values[-1][1]/values[0][1])**(1/periods)-1)*100.0
