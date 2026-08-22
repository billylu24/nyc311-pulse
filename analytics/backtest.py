"""Versioned validation/locked-test protocol for volume anomaly detection."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .evaluation import evaluate_configuration, make_semisynthetic_panel, metrics_dict, protocol_hash
from .signals import VolumeThresholds


@dataclass(frozen=True)
class BacktestResult:
    precision: float
    recall: float
    f1: float
    false_alerts_per_week: float
    median_detection_delay_days: float
    injections: int
    scenario_recall: dict[str, float] = field(default_factory=dict)
    confidence_intervals: dict[str, list[float]] = field(default_factory=dict)
    selected_model: str = "robust_seasonal"
    candidates: list[dict[str, Any]] = field(default_factory=list)
    protocol_sha256: str = ""


def candidate_configurations() -> list[VolumeThresholds]:
    """Pre-registered candidate set; locked-test output never changes this grid."""

    return [
        VolumeThresholds(history_points=8, robust_z=4.0, minimum_ratio=1.5, detector="robust_seasonal"),
        VolumeThresholds(history_points=13, robust_z=4.0, minimum_ratio=1.5, detector="robust_seasonal"),
        VolumeThresholds(history_points=26, robust_z=4.0, minimum_ratio=1.5, detector="robust_seasonal"),
        VolumeThresholds(history_points=13, prediction_z=3.5, minimum_ratio=1.4, detector="nb_conformal"),
        VolumeThresholds(history_points=26, prediction_z=3.0, minimum_ratio=1.4, detector="nb_conformal"),
        VolumeThresholds(
            history_points=26,
            prediction_z=3.0,
            minimum_ratio=1.4,
            minimum_absolute_delta=12,
            detector="nb_conformal",
        ),
        VolumeThresholds(history_points=26, prediction_z=3.5, minimum_ratio=1.4, detector="nb_conformal"),
        VolumeThresholds(
            history_points=26,
            prediction_z=3.5,
            minimum_ratio=1.4,
            minimum_absolute_delta=15,
            spike_ratio=1.95,
            spike_minimum_baseline=40,
            detector="nb_conformal",
        ),
        VolumeThresholds(
            history_points=13,
            prediction_z=3.5,
            minimum_ratio=1.4,
            detector="hybrid_nb_ewma",
            shift_window=3,
        ),
    ]


def configuration_name(config: VolumeThresholds) -> str:
    threshold = config.robust_z if config.detector == "robust_seasonal" else config.prediction_z
    spike = (
        f"-sr{config.spike_ratio:g}-b{config.spike_minimum_baseline:g}"
        if config.spike_ratio is not None
        else ""
    )
    return f"{config.detector}-h{config.history_points}-z{threshold:g}-d{config.minimum_absolute_delta:g}{spike}"


def _meets_operational_constraints(row: dict[str, Any]) -> bool:
    metrics = row["metrics"]
    return (
        metrics["f1"] >= 0.80
        and metrics["false_alerts_per_week"] <= 5
        and metrics["median_detection_delay_days"] <= 2
        and min(metrics["scenario_recall"].values(), default=0) >= 0.70
    )


def _selection_key(row: dict[str, Any]) -> tuple[float, float, float, int]:
    metrics = row["metrics"]
    weakest = min(metrics["scenario_recall"].values(), default=0)
    complexity = 0 if row["detector"] == "robust_seasonal" else (1 if row["detector"] == "nb_conformal" else 2)
    return (metrics["f1"], -metrics["false_alerts_per_week"], weakest, -complexity)


def run_injection_backtest(daily: pd.DataFrame, seed: int = 311, events: int | None = None) -> BacktestResult:
    """Tune on a seeded validation panel and evaluate once on an independent locked panel."""

    eligible = sum(
        len(group) >= 70 and float(np.median(group["requests"].to_numpy(dtype=float))) >= 10
        for _, group in daily.groupby(["district", "problem"])
    )
    if eligible == 0:
        return BacktestResult(0, 0, 0, 0, 0, 0)
    event_count = events or min(1200, max(60, eligible * 4))
    validation_panel, validation_events = make_semisynthetic_panel(daily, seed=seed, events=event_count)
    validation_control, _ = make_semisynthetic_panel(daily, seed=seed, events=event_count, inject=False)
    validation_rows: list[dict[str, Any]] = []
    configs = candidate_configurations()
    for config in configs:
        metrics, intervals = evaluate_configuration(
            validation_panel, validation_events, config, control_panel=validation_control
        )
        validation_rows.append(
            {
                "name": configuration_name(config),
                "detector": config.detector,
                "history_points": config.history_points,
                "metrics": metrics_dict(metrics),
                "confidence_intervals": intervals,
            }
        )
    feasible = [row for row in validation_rows if _meets_operational_constraints(row)] or validation_rows
    selected_row = max(feasible, key=_selection_key)
    selected_index = next(
        index for index, row in enumerate(validation_rows) if row["name"] == selected_row["name"]
    )
    selected_config = configs[selected_index]

    locked_panel, locked_events = make_semisynthetic_panel(daily, seed=seed + 24000, events=event_count)
    locked_control, _ = make_semisynthetic_panel(daily, seed=seed + 24000, events=event_count, inject=False)
    locked_metrics, intervals = evaluate_configuration(
        locked_panel, locked_events, selected_config, control_panel=locked_control
    )
    protocol = {
        "version": "2.0.0",
        "generator_version": "2.3.0-actionable-strengths",
        "train": ["2024-08-01", "2025-12-31"],
        "validation": ["2026-01-01", "2026-04-30"],
        "locked_test": ["2026-05-01", "2026-07-31"],
        "validation_seed": seed,
        "locked_seed": seed + 24000,
        "events_per_split": event_count,
        "candidate_grid": [asdict(config) for config in configs],
        "selected": configuration_name(selected_config),
    }
    return BacktestResult(
        precision=locked_metrics.precision,
        recall=locked_metrics.recall,
        f1=locked_metrics.f1,
        false_alerts_per_week=locked_metrics.false_alerts_per_week,
        median_detection_delay_days=locked_metrics.median_detection_delay_days,
        injections=event_count,
        scenario_recall=locked_metrics.scenario_recall,
        confidence_intervals=intervals,
        selected_model=configuration_name(selected_config),
        candidates=validation_rows,
        protocol_sha256=protocol_hash(protocol),
    )
