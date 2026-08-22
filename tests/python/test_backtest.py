from datetime import date, timedelta

import pandas as pd

from analytics.backtest import run_injection_backtest


def test_injection_backtest_is_deterministic_and_reports_all_metrics():
    start = date(2026, 1, 1)
    rows = []
    for series in range(4):
        for offset in range(92):
            rows.append(
                {
                    "date": start + timedelta(days=offset),
                    "district": f"Queens {series + 1:02d}",
                    "problem": "Noise",
                    "requests": 20 + (offset % 3),
                }
            )
    frame = pd.DataFrame(rows)
    first = run_injection_backtest(frame)
    second = run_injection_backtest(frame)
    assert first == second
    assert first.injections > 0
    assert 0 <= first.precision <= 1
    assert 0 <= first.recall <= 1
    assert 0 <= first.f1 <= 1
