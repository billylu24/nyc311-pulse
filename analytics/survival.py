"""Small Kaplan–Meier implementation used for closure probability reporting."""

from __future__ import annotations

from collections.abc import Sequence


def km_closure_probability(durations_days: Sequence[float], events: Sequence[bool], horizon_days: float = 7.0) -> float:
    """Return P(close <= horizon), retaining unresolved requests as right-censored."""

    if len(durations_days) != len(events):
        raise ValueError("durations and events must have equal length")
    if not durations_days:
        raise ValueError("at least one observation is required")
    if any(duration < 0 for duration in durations_days):
        raise ValueError("durations cannot be negative")

    survival = 1.0
    ordered_times = sorted({float(value) for value in durations_days if value <= horizon_days})
    for current_time in ordered_times:
        at_risk = sum(duration >= current_time for duration in durations_days)
        closed = sum(
            duration == current_time and bool(event) for duration, event in zip(durations_days, events, strict=True)
        )
        if at_risk and closed:
            survival *= 1.0 - closed / at_risk
    return round(1.0 - survival, 6)
