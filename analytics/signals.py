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
    cooldown_days: int = 7
    detector: str = "robust_seasonal"
    prediction_z: float = 3.5
    shift_window: int = 3
    spike_ratio: float | None = None
    spike_minimum_baseline: float = 0.0


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
                    "calibrated_score": round(robust_z, 2),
                    "upper_bound": round(expected + thresholds.robust_z * scale, 2),
                    "excess_count": round(delta, 2),
                    "detector": thresholds.detector,
                    "affected_count": int(observed),
                }
            )
    return candidates


def detect_nb_signals(
    daily: pd.DataFrame,
    *,
    as_of: date | None = None,
    thresholds: VolumeThresholds | None = None,
) -> list[dict[str, object]]:
    """Negative-Binomial-inspired rolling prediction interval detector.

    The conditional mean comes from prior matching weekdays. Dispersion is estimated
    from the preceding 26 weeks and the alert score is expressed in predictive
    standard deviations. This keeps the public evidence interpretable and provides a
    stable fallback for series that are too short for a full regression fit.
    """

    thresholds = thresholds or VolumeThresholds(detector="nb_conformal")
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
            prior_indices = [prior for prior in range(index) if dates[prior].weekday() == current_date.weekday()][-26:]
            if len(prior_indices) < thresholds.history_points:
                continue
            weekday_values = np.asarray([values[prior] for prior in prior_indices], dtype=float)
            expected = float(np.mean(weekday_values))
            # Estimate conditional dispersion within the matching weekday. Using the
            # variance of all recent days confounds day-of-week seasonality with
            # Negative Binomial noise and makes spike intervals far too wide.
            variance = float(np.var(weekday_values, ddof=1)) if len(weekday_values) > 1 else expected
            alpha = float(np.clip((variance - max(expected, 1.0)) / max(expected**2, 1.0), 0.0, 1.0))
            scale = max(float(np.sqrt(expected + alpha * expected**2)), 1.0)
            score = (observed - expected) / scale
            upper = expected + thresholds.prediction_z * scale
            delta = observed - expected
            ratio = observed / max(expected, 1.0)
            ratio_spike = (
                thresholds.spike_ratio is not None
                and expected >= thresholds.spike_minimum_baseline
                and ratio >= thresholds.spike_ratio
            )
            if (
                expected < thresholds.minimum_baseline
                or (observed <= upper and not ratio_spike)
                or delta < thresholds.minimum_absolute_delta
                or ratio < thresholds.minimum_ratio
            ):
                continue
            candidates.append(
                {
                    "id": stable_signal_id("volume_surge", district, problem, str(current_date)),
                    "type": "volume_surge",
                    "date": str(current_date),
                    "district": district,
                    "problem": problem,
                    "observed": round(observed, 2),
                    "expected": round(expected, 2),
                    "effect": round(ratio, 2),
                    "anomaly_score": round(score, 2),
                    "calibrated_score": round(score, 2),
                    "upper_bound": round(upper, 2),
                    "excess_count": round(delta, 2),
                    "detector": thresholds.detector,
                    "affected_count": int(observed),
                }
            )
    return candidates


def detect_hybrid_signals(
    daily: pd.DataFrame,
    *,
    as_of: date | None = None,
    thresholds: VolumeThresholds | None = None,
) -> list[dict[str, object]]:
    """Combine NB spike evidence with a short persistent-shift rule."""

    thresholds = thresholds or VolumeThresholds(detector="hybrid_nb_ewma")
    spikes = detect_nb_signals(daily, as_of=as_of, thresholds=thresholds)
    found = {(row["district"], row["problem"], row["date"]): row for row in spikes}
    frame = daily.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    if as_of is not None:
        frame = frame.loc[frame["date"] <= as_of]
    window = thresholds.shift_window
    for key, group in frame.groupby(["district", "problem"], sort=True):
        district_key, problem_key = cast(tuple[object, object], key)
        district, problem = str(district_key), str(problem_key)
        ordered = group.sort_values("date")
        dates = ordered["date"].tolist()
        values = ordered["requests"].astype(float).to_numpy()
        expected = np.full(len(values), np.nan)
        for index, current_date in enumerate(dates):
            history = [
                values[prior] for prior in range(index) if dates[prior].weekday() == current_date.weekday()
            ][-26:]
            if len(history) >= thresholds.history_points:
                expected[index] = float(np.median(history))
        for index in range(window - 1, len(values)):
            baseline = expected[index - window + 1 : index + 1]
            observed = values[index - window + 1 : index + 1]
            if np.isnan(baseline).any() or float(np.mean(baseline)) < thresholds.minimum_baseline:
                continue
            delta = float(np.sum(observed - baseline))
            ratio = float(np.sum(observed) / max(np.sum(baseline), 1.0))
            exceed_days = int(np.sum(observed >= baseline * 1.25))
            if exceed_days < max(2, window - 1) or ratio < max(1.25, thresholds.minimum_ratio - 0.2):
                continue
            if delta < thresholds.minimum_absolute_delta * window:
                continue
            current_date = dates[index]
            score = delta / max(float(np.sqrt(np.sum(baseline))), 1.0)
            row = {
                "id": stable_signal_id("volume_surge", district, problem, str(current_date)),
                "type": "volume_surge",
                "date": str(current_date),
                "district": district,
                "problem": problem,
                "observed": round(float(values[index]), 2),
                "expected": round(float(expected[index]), 2),
                "effect": round(ratio, 2),
                "anomaly_score": round(score, 2),
                "calibrated_score": round(score, 2),
                "upper_bound": round(float(expected[index] * max(1.25, thresholds.minimum_ratio - 0.2)), 2),
                "excess_count": round(delta, 2),
                "detector": thresholds.detector,
                "affected_count": int(np.sum(observed)),
            }
            found[(district, problem, str(current_date))] = row
    return sorted(found.values(), key=lambda row: (str(row["district"]), str(row["problem"]), str(row["date"])))


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
