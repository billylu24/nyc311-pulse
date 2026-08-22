from datetime import date, timedelta

import pandas as pd

from analytics.signals import detect_volume_signals, stable_signal_id


def series(values):
    start = date(2026, 1, 1)
    return pd.DataFrame(
        {
            "date": [start + timedelta(days=index) for index in range(len(values))],
            "district": ["Brooklyn 05"] * len(values),
            "problem": ["Street Condition"] * len(values),
            "requests": values,
        }
    )


def test_stable_id_does_not_depend_on_rank():
    first = stable_signal_id("volume_surge", "Brooklyn 05", "Street Condition", "2026-07-31")
    second = stable_signal_id("volume_surge", "Brooklyn 05", "Street Condition", "2026-07-31")
    assert first == second
    assert first.startswith("SIG-")


def test_matching_weekday_spike_is_detected():
    values = [20] * 63 + [20] * 6 + [80]
    found = detect_volume_signals(series(values))
    assert found[-1]["effect"] == 4.0
    assert found[-1]["district"] == "Brooklyn 05"


def test_sparse_series_does_not_alert():
    values = [1] * 69 + [20]
    assert detect_volume_signals(series(values)) == []


def test_zero_mad_uses_stable_scale():
    values = [20] * 69 + [50]
    found = detect_volume_signals(series(values))
    assert found[-1]["anomaly_score"] == 30.0
