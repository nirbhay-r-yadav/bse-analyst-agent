"""Shared history-length policy for financial metrics.

Financial metrics must use the maximum valid history available from the data
provider rather than assuming a fixed ten-year dataset exists.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence, TypeVar

T = TypeVar("T")


MAX_ANALYTICAL_YEARS = 10
MIN_YEARS_CAGR = 2
MIN_YEARS_TREND = 3
MIN_YEARS_CONSISTENCY = 3


def valid_history(values: Iterable[Optional[T]]) -> list[T]:
    """Return only non-missing observations, preserving chronological order."""
    return [value for value in values if value is not None]


def enough_history(values: Sequence[Optional[T]], minimum: int) -> bool:
    """Return whether at least ``minimum`` valid observations are available."""
    return len(valid_history(values)) >= minimum


def bounded_history(values: Sequence[T], max_years: int = MAX_ANALYTICAL_YEARS) -> list[T]:
    """Use up to the available maximum; never require the maximum to exist."""
    if max_years <= 0:
        return []
    return list(values[-max_years:])


def cagr_start_end(values: Sequence[Optional[float]]) -> Optional[tuple[float, float, int]]:
    """Return first/last valid values and elapsed observation count for CAGR.

    Missing observations are skipped. At least two valid observations are
    required. The caller should still validate that the endpoints are suitable
    for its specific financial metric (for example, positive values).
    """
    valid = valid_history(values)
    if len(valid) < MIN_YEARS_CAGR:
        return None
    return float(valid[0]), float(valid[-1]), len(valid) - 1
