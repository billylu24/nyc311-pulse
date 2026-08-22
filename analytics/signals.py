"""Explainable robust signal detection and stable identifiers."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import cast

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class VolumeThresholds:
    robust_z: float = 3.5
    minimum_ratio: float = 1.5
    minimum_baseline: float = 5.0
    minimum_absolute_delta: float = 10.0
    history_points: int = 8


def stable_signal_id(signal_type: str, district: str, problem: str, window_start: str) -> str:
    identity = "|".join([signal_type, district, problem, window_start]).lower().encode("utf-8")
    digest = hashlib.sha256(identity).hexdigest()[:10].upper()
    return f"SIG-{digest}"


def _robust_baseline(history: Iterable[float]) -> tuple[float, float]:
    values = np.asarray(list(history), dtype=float)
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    return median, max(1.4826 * mad, 1.0)


def detect_volume_signals(
    daily: pd.DataFrame,
    *,
    as_of: date | None = None,
    thresholds: VolumeThresholds | None = None,
) -> list[dict[str, object]]:
    """Detect high-volume district/problem days against eight matching weekdays."""

    thresholds = thresholds or VolumeThresholds()
    required = {"date", "district", "problem", "requests"}
    missing = required - set(daily.columns)
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
    frame = daily.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    if as_of is not None:
        frame = frame.loc[frame["date"] <= as_of]

    candidates: list[dict[str, object]] = []
    for key, group in frame.groupby(["district", "problem"], sort=True):
        district_key, problem_key = cast(tuple[object, object], key)
        district, problem = str(district_key), str(problem_key)
        group = group.sort_values("date")
        dates = group["date"].tolist()
        values = group["requests"].astype(float).tolist()
        for index, (current_date, observed) in enumerate(zip(dates, values, strict=True)):
            weekday_history = [
                values[prior] for prior in range(index) if dates[prior].weekday() == current_date.weekday()
            ][-thresholds.history_points :]
            if len(weekday_history) < thresholds.history_points:
                continue
            expected, scale = _robust_baseline(weekday_history)
            delta = observed - expected
            ratio = observed / max(expected, 1.0)
            robust_z = delta / scale
            if (
                expected < thresholds.minimum_baseline
                or delta < thresholds.minimum_absolute_delta
                or ratio < thresholds.minimum_ratio
                or robust_z < thresholds.robust_z
            ):
                continue
            candidates.append(
                {
                    "id": stable_signal_id("volume_surge", str(district), str(problem), str(current_date)),
                    "type": "volume_surge",
                    "date": str(current_date),
                    "district": str(district),
                    "problem": str(problem),
                    "observed": round(observed, 2),
                    "expected": round(expected, 2),
                    "effect": round(ratio, 2),
                    "anomaly_score": round(robust_z, 2),
                    "affected_count": int(observed),
                }
            )
    return candidates


def rank_signals(signals: list[dict[str, object]]) -> list[dict[str, object]]:
    """Apply the published 50/30/20 priority weighting without changing identifiers."""

    if not signals:
        return []
    frame = pd.DataFrame(signals)
    persistence = frame["persistence"] if "persistence" in frame.columns else pd.Series([1] * len(frame))
    frame["persistence"] = persistence.fillna(1)
    for source, target in [
        ("anomaly_score", "strength_pct"),
        ("affected_count", "impact_pct"),
        ("persistence", "persistence_pct"),
    ]:
        frame[target] = frame[source].rank(pct=True, method="average")
    frame["priority_score"] = 0.5 * frame["strength_pct"] + 0.3 * frame["impact_pct"] + 0.2 * frame["persistence_pct"]
    frame["severity"] = np.where(frame["priority_score"] >= 0.9, "high", "watch")
    return frame.sort_values(["priority_score", "date"], ascending=False).to_dict("records")
