"""Leakage-resistant, episode-level evaluation for volume anomaly detectors."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import date, timedelta
from typing import Any, cast

import numpy as np
import pandas as pd

from .signals import VolumeThresholds, detect_hybrid_signals, detect_nb_signals, detect_volume_signals


@dataclass(frozen=True)
class Event:
    event_id: str
    district: str
    problem: str
    start: date
    end: date
    scenario: str
    generator: str


@dataclass(frozen=True)
class EpisodeMetrics:
    precision: float
    recall: float
    f1: float
    false_alerts_per_week: float
    median_detection_delay_days: float
    true_positive: int
    false_positive: int
    false_negative: int
    scenario_recall: dict[str, float]


def merge_alert_episodes(alerts: list[dict[str, object]], cooldown_days: int = 7) -> list[dict[str, object]]:
    """Merge nearby daily alerts for the same series into one operational episode."""

    episodes: list[dict[str, object]] = []
    ordered = sorted(alerts, key=lambda row: (str(row["district"]), str(row["problem"]), str(row["date"])))
    for alert in ordered:
        alert_date = date.fromisoformat(str(alert["date"]))
        if episodes:
            previous = episodes[-1]
            same_series = previous["district"] == alert["district"] and previous["problem"] == alert["problem"]
            previous_end = date.fromisoformat(str(previous["episode_end"]))
            if same_series and (alert_date - previous_end).days <= cooldown_days:
                previous["episode_end"] = str(alert_date)
                previous["persistence"] = int(str(previous["persistence"])) + 1
                if float(str(alert.get("anomaly_score", 0))) > float(str(previous.get("anomaly_score", 0))):
                    for field in ("observed", "expected", "effect", "anomaly_score", "upper_bound", "calibrated_score"):
                        if field in alert:
                            previous[field] = alert[field]
                continue
        episodes.append(
            {
                **alert,
                "episode_start": str(alert_date),
                "episode_end": str(alert_date),
                "persistence": 1,
            }
        )
    return episodes


def score_episodes(
    episodes: list[dict[str, object]],
    events: list[Event],
    *,
    panel_start: date,
    panel_end: date,
) -> EpisodeMetrics:
    """Match one alert episode to at most one labeled event with a two-day grace window."""

    used: set[int] = set()
    delays: list[int] = []
    matched_by_scenario: dict[str, int] = {}
    total_by_scenario: dict[str, int] = {}
    for event in events:
        total_by_scenario[event.scenario] = total_by_scenario.get(event.scenario, 0) + 1
        for index, episode in enumerate(episodes):
            if index in used or episode["district"] != event.district or episode["problem"] != event.problem:
                continue
            detected = date.fromisoformat(str(episode["episode_start"]))
            if event.start <= detected <= event.end + timedelta(days=2):
                used.add(index)
                delays.append(max(0, (detected - event.start).days))
                matched_by_scenario[event.scenario] = matched_by_scenario.get(event.scenario, 0) + 1
                break
    tp = len(used)
    fp = len(episodes) - tp
    fn = len(events) - tp
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    series_count = max(len({(event.district, event.problem) for event in events}), 1)
    weeks = max((panel_end - panel_start).days / 7, 1)
    # Normalize to a 708-series city panel instead of making the rate depend on benchmark sample size.
    fp_week = fp / max(series_count * weeks, 1) * 708
    return EpisodeMetrics(
        precision=round(precision, 3),
        recall=round(recall, 3),
        f1=round(f1, 3),
        false_alerts_per_week=round(fp_week, 2),
        median_detection_delay_days=round(float(np.median(delays)) if delays else 0.0, 2),
        true_positive=tp,
        false_positive=fp,
        false_negative=fn,
        scenario_recall={
            scenario: round(matched_by_scenario.get(scenario, 0) / total, 3)
            for scenario, total in sorted(total_by_scenario.items())
        },
    )


def clustered_bootstrap_ci(
    series_results: list[tuple[str, int, int, int]], *, seed: int = 311, draws: int = 500
) -> dict[str, list[float]]:
    """Bootstrap precision/recall/F1 by series, the independent evaluation unit."""

    if not series_results:
        return {metric: [0.0, 0.0] for metric in ("precision", "recall", "f1")}
    rng = np.random.default_rng(seed)
    values = {metric: [] for metric in ("precision", "recall", "f1")}
    for _ in range(draws):
        chosen = rng.integers(0, len(series_results), len(series_results))
        tp = sum(series_results[index][1] for index in chosen)
        fp = sum(series_results[index][2] for index in chosen)
        fn = sum(series_results[index][3] for index in chosen)
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-12)
        values["precision"].append(precision)
        values["recall"].append(recall)
        values["f1"].append(f1)
    return {
        metric: [round(float(np.quantile(samples, 0.025)), 3), round(float(np.quantile(samples, 0.975)), 3)]
        for metric, samples in values.items()
    }


def _series_template(group: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, float]:
    ordered = group.sort_values("date")
    values = ordered["requests"].astype(float).to_numpy()
    weekdays = pd.to_datetime(ordered["date"]).dt.weekday.to_numpy()
    global_median = max(float(np.median(values)), 10.0)
    weekday_means = np.array([
        max(float(np.median(values[weekdays == weekday])), 1.0)
        if np.any(weekdays == weekday)
        else global_median
        for weekday in range(7)
    ])
    variance = float(np.var(values))
    alpha = float(np.clip((variance - global_median) / max(global_median**2, 1), 0.02, 0.5))
    return values, weekday_means, alpha


def make_semisynthetic_panel(
    daily: pd.DataFrame,
    *,
    seed: int,
    events: int = 1200,
    start: date = date(2026, 1, 1),
    days: int = 220,
    inject: bool = True,
) -> tuple[pd.DataFrame, list[Event]]:
    """Create stratified NB/bootstrap panels with full event ground truth."""

    required = {"date", "district", "problem", "requests"}
    if required - set(daily.columns):
        raise ValueError("Daily panel is missing required columns")
    candidates = [
        (key, group)
        for key, group in daily.groupby(["district", "problem"], sort=True)
        if len(group) >= 70 and float(np.median(group["requests"].to_numpy(dtype=float))) >= 10
    ]
    if not candidates:
        raise ValueError("No eligible series for semisynthetic evaluation")
    rng = np.random.default_rng(seed)
    dates = np.array([timestamp.date() for timestamp in pd.date_range(start, periods=days, freq="D")])
    rows: list[pd.DataFrame] = []
    labels: list[Event] = []
    scenarios = ("spike", "level_shift", "gradual_ramp")
    scenario_strengths = {
        # A one-day event must be large enough to be distinguishable from an
        # overdispersed count draw; weaker changes remain research-only.
        "spike": (2.75, 3.5, 5.0),
        "level_shift": (1.75, 2.0, 2.5),
        "gradual_ramp": (1.75, 2.25, 3.0),
    }
    for index in range(events):
        raw_key, source = candidates[index % len(candidates)]
        source_district, source_problem = cast(tuple[object, object], raw_key)
        values, weekday_means, alpha = _series_template(source)
        generator = "negative_binomial" if index % 2 == 0 else "weekly_block_bootstrap"
        means = np.array([weekday_means[current.weekday()] for current in dates])
        if generator == "negative_binomial":
            shape = 1.0 / alpha
            probability = shape / (shape + means)
            generated = rng.negative_binomial(shape, probability).astype(float)
        else:
            clipped = np.clip(values, np.quantile(values, 0.05), np.quantile(values, 0.95))
            source_dates = pd.to_datetime(source["date"])
            expected_source = np.array([weekday_means[current.weekday()] for current in source_dates.dt.date])
            residuals = clipped - expected_source
            block_starts = rng.integers(0, max(len(residuals) - 7, 1), int(np.ceil(days / 7)))
            sampled = np.concatenate([residuals[position : position + 7] for position in block_starts])[:days]
            generated = np.maximum(0, np.rint(means + sampled))
        scenario = scenarios[index % len(scenarios)]
        duration = 1 if scenario == "spike" else (3, 7, 14)[(index // 3) % 3]
        possible_offsets = list(range(190, max(191, days - duration - 2)))
        truth_scale = np.sqrt(means + alpha * means**2)
        quiet_offsets = [
            position
            for position in possible_offsets
            if np.all(
                generated[position - 7 : position]
                < 1.5 * means[position - 7 : position]
            )
            and np.all(
                generated[position - 7 : position]
                < means[position - 7 : position] + 3.0 * truth_scale[position - 7 : position]
            )
        ]
        available_offsets = quiet_offsets or possible_offsets
        event_offset = available_offsets[index % len(available_offsets)]
        strengths = scenario_strengths[scenario]
        multiplier = strengths[(index // 9) % len(strengths)]
        if inject:
            for offset in range(duration):
                position = event_offset + offset
                applied = multiplier
                if scenario == "gradual_ramp":
                    applied = 1.25 + (multiplier - 1.25) * offset / max(duration - 1, 1)
                # A labeled injection must produce the declared realized effect. Multiplying
                # an unusually low random draw can otherwise label an ordinary count as a
                # spike, creating an impossible false negative in the benchmark itself.
                generated[position] = np.ceil(max(generated[position] * applied, means[position] * applied))
        district = f"SYN-{index:04d}-{source_district}"
        problem = str(source_problem)
        rows.append(pd.DataFrame({"date": dates, "district": district, "problem": problem, "requests": generated}))
        event_start = dates[event_offset]
        labels.append(
            Event(
                event_id=f"EV-{seed}-{index:04d}",
                district=district,
                problem=problem,
                start=event_start,
                end=event_start + timedelta(days=duration - 1),
                scenario=scenario,
                generator=generator,
            )
        )
    return pd.concat(rows, ignore_index=True), labels


def evaluate_configuration(
    panel: pd.DataFrame,
    events: list[Event],
    thresholds: VolumeThresholds,
    *,
    control_panel: pd.DataFrame | None = None,
) -> tuple[EpisodeMetrics, dict[str, list[float]]]:
    detector = {
        "robust_seasonal": detect_volume_signals,
        "nb_conformal": detect_nb_signals,
        "hybrid_nb_ewma": detect_hybrid_signals,
    }.get(thresholds.detector)
    if detector is None:
        raise ValueError(f"Unknown detector: {thresholds.detector}")
    alerts = detector(panel, thresholds=thresholds)
    episodes = merge_alert_episodes(alerts, cooldown_days=thresholds.cooldown_days)
    panel_dates = pd.to_datetime(panel["date"]).dt.date
    start = min(panel_dates)
    end = max(panel_dates)
    metrics = score_episodes(episodes, events, panel_start=start, panel_end=end)
    if control_panel is not None:
        control_alerts = detector(control_panel, thresholds=thresholds)
        control_episodes = merge_alert_episodes(control_alerts, cooldown_days=thresholds.cooldown_days)
        control_dates = pd.to_datetime(control_panel["date"]).dt.date
        control_weeks = max((max(control_dates) - min(control_dates)).days / 7, 1)
        control_series = max(control_panel.groupby(["district", "problem"]).ngroups, 1)
        control_fp_week = len(control_episodes) / (control_series * control_weeks) * 708
        metrics = replace(metrics, false_alerts_per_week=round(control_fp_week, 2))
    by_series: list[tuple[str, int, int, int]] = []
    for event in events:
        event_episodes = [row for row in episodes if row["district"] == event.district]
        local = score_episodes(event_episodes, [event], panel_start=start, panel_end=end)
        by_series.append((event.district, local.true_positive, local.false_positive, local.false_negative))
    return metrics, clustered_bootstrap_ci(by_series)


def protocol_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def metrics_dict(metrics: EpisodeMetrics) -> dict[str, Any]:
    return asdict(metrics)
