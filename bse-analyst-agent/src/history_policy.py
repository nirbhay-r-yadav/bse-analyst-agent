"""Shared history-length policy for financial metrics."""

from __future__ import annotations

from typing import Iterable, Optional, Sequence, TypeVar

T = TypeVar("T")

MAX_ANALYTICAL_YEARS = 10
MIN_YEARS_CAGR = 2
MIN_YEARS_TREND = 3
MIN_YEARS_CONSISTENCY = 3


def valid_history(values: Iterable[Optional[T]]) -> list[T]:
    """Return non-missing observations while preserving their order."""
    return [value for value in values if value is not None]


def enough_history(values: Sequence[Optional[T]], minimum: int) -> bool:
    """Return whether at least ``minimum`` valid observations exist."""
    return len(valid_history(values)) >= minimum


def bounded_history(values: Sequence[T], max_years: int = MAX_ANALYTICAL_YEARS) -> list[T]:
    """Use up to the available maximum; never require the maximum to exist."""
    if max_years <= 0:
        return []
    return list(values[-max_years:])


def cagr_start_end(values: Sequence[Optional[float]]) -> Optional[tuple[float, float, int]]:
    """Return first/last valid values and the elapsed observation count."""
    valid = valid_history(values)
    if len(valid) < MIN_YEARS_CAGR:
        return None
    return float(valid[0]), float(valid[-1]), len(valid) - 1
