from datetime import date

from analytics.evaluation import Event, merge_alert_episodes, score_episodes


def alert(day: str):
    return {
        "date": day,
        "district": "Queens 01",
        "problem": "Noise",
        "observed": 40,
        "expected": 20,
        "effect": 2,
        "anomaly_score": 5,
    }


def test_daily_alerts_merge_into_one_episode():
    episodes = merge_alert_episodes([alert("2026-07-01"), alert("2026-07-03"), alert("2026-07-12")])
    assert len(episodes) == 2
    assert episodes[0]["persistence"] == 2
    assert episodes[0]["episode_end"] == "2026-07-03"


def test_event_matching_counts_once_and_computes_delay():
    episodes = merge_alert_episodes([alert("2026-07-03"), alert("2026-07-04")])
    events = [
        Event("EV-1", "Queens 01", "Noise", date(2026, 7, 1), date(2026, 7, 7), "level_shift", "nb")
    ]
    metrics = score_episodes(
        episodes,
        events,
        panel_start=date(2026, 6, 1),
        panel_end=date(2026, 7, 31),
    )
    assert metrics.true_positive == 1
    assert metrics.false_positive == 0
    assert metrics.median_detection_delay_days == 2
