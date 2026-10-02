from __future__ import annotations

import re


def classify_business(text: str) -> dict[str, object]:
    lower=text.lower()
    scores={
        "technology_services":sum(bool(re.search(p,lower)) for p in (r"software services?",r"it services?",r"digital transformation",r"cloud services?")),
        "manufacturing":sum(bool(re.search(p,lower)) for p in (r"manufactur",r"plant",r"production capacity",r"factory")),
        "financial_services":sum(bool(re.search(p,lower)) for p in (r"loan book",r"net interest income",r"banking",r"non-banking finance")),
        "consumer":sum(bool(re.search(p,lower)) for p in (r"consumer",r"retail",r"brand",r"distribution")),
        "energy_infrastructure":sum(bool(re.search(p,lower)) for p in (r"power plant",r"renewable",r"transmission",r"generation capacity")),
    }
    business_type=max(scores,key=scores.get) if any(scores.values()) else "other"
    return {"business_type":business_type,"keyword_scores":scores}
