from datetime import date

import pytest

from scripts import build_snapshot


def aggregate_row(day: str, board: str, requests: int = 1):
    return {
        "day": f"{day}T00:00:00",
        "community_board": board,
        "complaint_type": "Noise",
        "requests": str(requests),
    }


def test_query_all_reads_past_first_limit(monkeypatch):
    pages = {
        0: [aggregate_row("2026-01-01", "01 MANHATTAN"), aggregate_row("2026-01-02", "01 MANHATTAN")],
        2: [aggregate_row("2026-01-03", "01 MANHATTAN")],
    }
    monkeypatch.setattr(build_snapshot, "query", lambda params: pages[int(params["$offset"])])
    rows, count = build_snapshot.query_all({"$order": "day"}, page_size=2)
    assert len(rows) == 3
    assert count == 2


def test_query_all_rejects_duplicate_pages(monkeypatch):
    row = aggregate_row("2026-01-01", "01 MANHATTAN")
    pages = {0: [row, aggregate_row("2026-01-02", "01 MANHATTAN")], 2: [row]}
    monkeypatch.setattr(build_snapshot, "query", lambda params: pages[int(params["$offset"])])
    with pytest.raises(RuntimeError, match="duplicate"):
        build_snapshot.query_all({"$order": "day"}, page_size=2)


def test_complete_daily_rejects_truncated_final_date():
    rows = [aggregate_row("2026-01-01", "01 MANHATTAN")]
    with pytest.raises(RuntimeError, match="incomplete"):
        build_snapshot.complete_daily(rows, start=date(2026, 1, 1), end=date(2026, 1, 2))


def test_aggregate_total_must_reconcile():
    rows = [aggregate_row("2026-01-01", "01 MANHATTAN", requests=4)]
    assert build_snapshot.validate_aggregate_reconciliation(rows, 4) == 4
    with pytest.raises(RuntimeError, match="reconciliation"):
        build_snapshot.validate_aggregate_reconciliation(rows, 5)
