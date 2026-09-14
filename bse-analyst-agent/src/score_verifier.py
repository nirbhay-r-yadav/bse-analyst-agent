"""CLI and audit helpers for verifying persisted investment scores."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from .scoring_engine import ScoringEngine


def build_verification_report(output_dir: str) -> dict[str, Any]:
    engine = ScoringEngine(output_dir)
    result = engine.calculate()
    verification = engine.verify_persisted_decision(result)
    report = {
        "symbol": result.symbol,
        "verification": verification,
        "scale_audit": {
            "governance": {
                "raw_score": result.governance.score,
                "raw_maximum": result.governance.maximum,
                "normalized_100": result.governance.normalized_100,
                "note": "Current governance grade mapping is 10 points maximum, not 100.",
            },
            "fundamentals": {
                "raw_score": result.fundamentals.score,
                "raw_maximum": result.fundamentals.maximum,
                "normalized_100": result.fundamentals.normalized_100,
                "note": "Current financial score excludes the 20-point governance bucket, so its effective maximum is 80.",
            },
            "decision": {
                "score": result.decision,
                "maximum": 100,
                "formula": result.decision_formula,
                "components": result.decision_components,
            },
        },
    }
    with open(os.path.join(output_dir, "score_verification.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    return report


def print_report(report: dict[str, Any]) -> None:
    scale = report["scale_audit"]
    verification = report["verification"]
    print("\nSCORE VERIFICATION")
    print("=" * 72)
    print(f"Symbol: {report.get('symbol') or 'UNKNOWN'}")
    print()
    print("CURRENT SCORE SCALES")
    print("-" * 72)
    for name in ("fundamentals", "governance", "decision"):
        item = scale[name]
        if name == "decision":
            print(f"Decision      : {item['score']:.2f}/100")
            print(f"  Formula     : {item['formula']}")
            print(f"  Components  : {item['components']}")
        else:
            print(
                f"{name.title():<14}: {item['raw_score']:.2f}/{item['raw_maximum']:.0f} "
                f"=> normalized {item['normalized_100']:.2f}/100"
            )
            print(f"  NOTE        : {item['note']}")
    print()
    print("PERSISTED VS RECALCULATED")
    print("-" * 72)
    for key, passed in verification.get("checks", {}).items():
        print(f"{'PASS' if passed else 'FAIL':<6} {key}")
    print()
    print(f"OVERALL VERIFICATION: {verification.get('status')}")


def main() -> int:
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "./outputs/ZOTA"
    try:
        report = build_verification_report(output_dir)
    except Exception as exc:
        print(f"VERIFICATION ERROR: {type(exc).__name__}: {exc}")
        return 1
    print_report(report)
    return 0 if report["verification"].get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
