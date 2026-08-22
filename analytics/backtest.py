"""Deterministic injection backtest for the published volume detector."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .signals import VolumeThresholds, detect_volume_signals


@dataclass(frozen=True)
class BacktestResult:
    precision: float
    recall: float
    f1: float
    false_alerts_per_week: float
    median_detection_delay_days: float
    injections: int


def run_injection_backtest(daily: pd.DataFrame, seed: int = 311) -> BacktestResult:
    frame = daily.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    eligible = []
    for key, group in frame.groupby(["district", "problem"]):
        group = group.sort_values("date")
        if len(group) >= 70 and group["requests"].median() >= 10:
            eligible.append((key, group))
    if not eligible:
        return BacktestResult(0, 0, 0, 0, 0, 0)

    rng = np.random.default_rng(seed)
    injected = frame.copy()
    labels: set[tuple[str, str, date]] = set()
    chosen = rng.choice(len(eligible), size=min(12, len(eligible)), replace=False)
    for position, chosen_index in enumerate(chosen):
        (district, problem), group = eligible[int(chosen_index)]
        valid_rows = group.iloc[56:-7] if len(group) > 70 else group.iloc[56:]
        if valid_rows.empty:
            continue
        start = valid_rows.iloc[position % len(valid_rows)]["date"]
        scenario = position % 3
        duration = 1 if scenario == 0 else 7
        for offset in range(duration):
            target = start + timedelta(days=offset)
            multiplier = 2.0 if scenario == 0 else 1.5
            if scenario == 2:
                multiplier = 1.1 + (0.6 * offset / max(duration - 1, 1))
            mask = (injected["district"] == district) & (injected["problem"] == problem) & (injected["date"] == target)
            injected.loc[mask, "requests"] = np.ceil(injected.loc[mask, "requests"] * multiplier)
            labels.add((str(district), str(problem), target))

    detections = detect_volume_signals(injected, thresholds=VolumeThresholds())
    predicted = {
        (str(row["district"]), str(row["problem"]), date.fromisoformat(str(row["date"]))) for row in detections
    }
    true_positive = len(predicted & labels)
    false_positive = len(predicted - labels)
    false_negative = len(labels - predicted)
    precision = true_positive / max(true_positive + false_positive, 1)
    recall = true_positive / max(true_positive + false_negative, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    weeks = max((frame["date"].max() - frame["date"].min()).days / 7, 1)
    return BacktestResult(
        precision=round(precision, 3),
        recall=round(recall, 3),
        f1=round(f1, 3),
        false_alerts_per_week=round(false_positive / weeks, 2),
        median_detection_delay_days=0.0,
        injections=len(labels),
    )
