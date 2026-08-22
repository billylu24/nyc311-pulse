"""Build the fixed, privacy-minimized portfolio snapshot from official NYC Open Data.

The default build uses server-side Socrata aggregates so a reviewer can reproduce the
deployed artifact without downloading millions of request-level records. The full raw
extract path remains available through analytics.socrata for warehouse rebuilds.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pandas as pd

from analytics.backtest import candidate_configurations, configuration_name, run_injection_backtest
from analytics.evaluation import merge_alert_episodes
from analytics.signals import detect_hybrid_signals, detect_nb_signals, detect_volume_signals, rank_signals

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public" / "data"
API = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
BOUNDARIES = "https://data.cityofnewyork.us/resource/5crt-au7u.geojson"
WINDOW_START = "2024-08-01"
WINDOW_END = "2026-07-31"
EXTRACTED_AT = "2026-08-21"
TRAIN_END = date(2025, 12, 31)
VALIDATION_START = date(2026, 1, 1)
VALIDATION_END = date(2026, 4, 30)
ANALYSIS_START = date.fromisoformat(WINDOW_START)
ANALYSIS_END = date.fromisoformat(WINDOW_END)
PAGE_SIZE = 50_000


def query(params: dict[str, str], timeout: float = 180.0) -> list[dict[str, Any]]:
    cache_dir = ROOT / ".cache" / "socrata"
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()
    cache_path = cache_dir / f"{key}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    for attempt in range(4):
        try:
            response = httpx.get(API, params=params, timeout=timeout, follow_redirects=True)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise RuntimeError("Unexpected Socrata response")
            cache_path.write_text(json.dumps(payload), encoding="utf-8")
            return payload
        except (httpx.HTTPError, RuntimeError):
            if attempt == 3:
                raise
            time.sleep(2**attempt)
    return []


def query_all(params: dict[str, str], *, page_size: int = PAGE_SIZE) -> tuple[list[dict[str, Any]], int]:
    """Read every Socrata page and reject repeated aggregate rows.

    Grouped Socrata queries are still subject to ``$limit``.  The previous builder
    silently stopped at 50,000 rows, so an explicit stable order and pagination are
    part of the public artifact contract now.
    """

    if "$order" not in params:
        raise ValueError("Paginated queries require a stable $order")
    rows: list[dict[str, Any]] = []
    offset = 0
    pages = 0
    while True:
        page_params = {**params, "$limit": str(page_size), "$offset": str(offset)}
        page = query(page_params)
        pages += 1
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += len(page)
    keys = [json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows]
    if len(keys) != len(set(keys)):
        raise RuntimeError("Paginated Socrata aggregate contains duplicate rows")
    return rows, pages


def validate_aggregate_reconciliation(rows: list[dict[str, Any]], expected_count: int) -> int:
    observed = sum(int(row["requests"]) for row in rows)
    if observed != expected_count:
        raise RuntimeError(f"Daily aggregate reconciliation failed: grouped={observed}, source={expected_count}")
    return observed


def sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def parse_district(value: str) -> tuple[str, str]:
    normalized = value.strip().upper()
    if normalized == "UNSPECIFIED" or "UNSPECIFIED" in normalized:
        return "Unspecified", "Unspecified"
    pieces = normalized.split(maxsplit=1)
    if len(pieces) != 2 or not pieces[0].isdigit():
        return value.title(), "Unspecified"
    number, borough = pieces
    borough_name = borough.title()
    return f"{borough_name} {int(number):02d}", borough_name


def is_official_district(value: str) -> bool:
    limits = {"Manhattan": 12, "Bronx": 12, "Brooklyn": 18, "Queens": 14, "Staten Island": 3}
    if value == "Unspecified" or " " not in value:
        return False
    borough, number = value.rsplit(" ", 1)
    return borough in limits and number.isdigit() and 1 <= int(number) <= limits[borough]


def official_board_values() -> list[str]:
    limits = {"MANHATTAN": 12, "BRONX": 12, "BROOKLYN": 18, "QUEENS": 14, "STATEN ISLAND": 3}
    return [f"{number:02d} {borough}" for borough, limit in limits.items() for number in range(1, limit + 1)]


def complete_daily(
    rows: list[dict[str, Any]], *, start: date = ANALYSIS_START, end: date = ANALYSIS_END
) -> pd.DataFrame:
    if not rows:
        raise RuntimeError("Daily aggregate query returned no rows")
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["day"]).dt.date
    if frame["date"].min() != start or frame["date"].max() != end:
        raise RuntimeError(
            f"Daily aggregate is incomplete: expected {start}..{end}, "
            f"received {frame['date'].min()}..{frame['date'].max()}"
        )
    duplicate = frame.duplicated(["date", "community_board", "complaint_type"])
    if duplicate.any():
        raise RuntimeError(f"Daily aggregate contains {int(duplicate.sum())} duplicate keys")
    frame["district"] = frame["community_board"].map(lambda value: parse_district(value)[0])
    frame["problem"] = frame["complaint_type"]
    frame["requests"] = frame["requests"].astype(int)
    dates = pd.DataFrame({"date": pd.date_range(start, end, freq="D").date})
    completed: list[pd.DataFrame] = []
    for (district, problem), group in frame.groupby(["district", "problem"]):
        merged = dates.merge(group[["date", "requests"]], on="date", how="left")
        merged["requests"] = merged["requests"].fillna(0).astype(int)
        merged["district"] = district
        merged["problem"] = problem
        completed.append(merged)
    return pd.concat(completed, ignore_index=True)


def matching_weekday_baseline(group: pd.DataFrame) -> list[float | None]:
    dates = group["date"].tolist()
    values = group["requests"].tolist()
    result: list[float | None] = []
    for index, current_date in enumerate(dates):
        history = [values[p] for p in range(index) if dates[p].weekday() == current_date.weekday()][-8:]
        result.append(float(pd.Series(history).median()) if len(history) == 8 else None)
    return result


def build_blind_review_packet(
    daily: pd.DataFrame, ranked_candidates: list[dict[str, object]], *, seed: int = 311
) -> dict[str, Any]:
    """Create 20 top, 20 near-threshold, and 20 matched control cases in blinded order."""

    rng = np.random.default_rng(seed)
    cases: list[dict[str, Any]] = []
    alert_keys = {
        (str(row["district"]), str(row["problem"]), str(row["date"])) for row in ranked_candidates
    }

    def add_case(row: dict[str, object], group: str) -> None:
        district, problem = str(row["district"]), str(row["problem"])
        index_date = pd.to_datetime(str(row["date"])).date()
        series = daily.loc[(daily["district"] == district) & (daily["problem"] == problem)].sort_values("date")
        series = series.loc[(series["date"] >= index_date - timedelta(days=41)) & (series["date"] <= index_date)]
        identity = f"{seed}|{group}|{district}|{problem}|{index_date}"
        cases.append(
            {
                "case_id": f"REV-{hashlib.sha256(identity.encode()).hexdigest()[:10].upper()}",
                "group_token": hashlib.sha256(f"{seed}|{group}".encode()).hexdigest()[:12],
                "district": district,
                "problem": problem,
                "index_date": str(index_date),
                "points": [
                    {"date": str(point.date), "observed": int(point.requests)}
                    for point in series.itertuples(index=False)
                ],
                "label": None,
                "external_evidence": [],
            }
        )

    for row in ranked_candidates[:20]:
        add_case(row, "top20")
    for row in ranked_candidates[20:40]:
        add_case(row, "near_threshold")

    control_pool: list[dict[str, object]] = []
    control_date = ANALYSIS_END
    for (district, problem), group in daily.groupby(["district", "problem"], sort=True):
        ordered = group.sort_values("date")
        row = ordered.loc[ordered["date"] == control_date]
        if row.empty or (str(district), str(problem), str(control_date)) in alert_keys:
            continue
        control_pool.append(
            {
                "district": str(district),
                "problem": str(problem),
                "date": str(control_date),
                "observed": int(row.iloc[0]["requests"]),
            }
        )
    if len(control_pool) < 20:
        raise RuntimeError("Not enough matched controls for blind review")
    for index in rng.choice(len(control_pool), size=20, replace=False):
        add_case(control_pool[int(index)], "matched_control")
    if len(cases) != 60:
        raise RuntimeError(f"Blind review packet requires 60 cases, received {len(cases)}")
    order = rng.permutation(len(cases))
    shuffled = [cases[int(index)] for index in order]
    key = {case["case_id"]: case["group_token"] for case in shuffled}
    return {
        "protocol_version": "2.0.0",
        "seed": seed,
        "labels": ["clear_anomaly", "plausible_anomaly", "unsupported", "uncertain"],
        "cases": shuffled,
        "key_sha256": hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest(),
    }


def build_snapshot() -> dict[str, Any]:
    where_full = f"created_date between '{WINDOW_START}T00:00:00' and '{WINDOW_END}T23:59:59'"
    where_train = f"created_date between '{WINDOW_START}T00:00:00' and '{TRAIN_END}T23:59:59'"

    request_count = int(query({"$select": "count(*) as count", "$where": where_full})[0]["count"])
    as_of_timestamp = f"{WINDOW_END}T23:59:59"
    unresolved_where = f"{where_full} and (closed_date is null or closed_date > '{as_of_timestamp}')"
    aged_cutoff = (date.fromisoformat(WINDOW_END) - timedelta(days=30)).isoformat()
    aged_open_where = (
        f"created_date between '{WINDOW_START}T00:00:00' and '{aged_cutoff}T23:59:59' "
        f"and (closed_date is null or closed_date > '{as_of_timestamp}')"
    )
    unresolved_count = int(query({"$select": "count(*) as count", "$where": unresolved_where})[0]["count"])
    aged_open_count = int(query({"$select": "count(*) as count", "$where": aged_open_where})[0]["count"])
    top_problem_rows = query(
        {
            "$select": "complaint_type,count(*) as requests",
            "$where": where_train,
            "$group": "complaint_type",
            "$order": "requests desc",
            "$limit": "12",
        }
    )
    top_problems = [row["complaint_type"] for row in top_problem_rows]
    problem_clause = ",".join(sql_quote(problem) for problem in top_problems)
    board_clause = ",".join(sql_quote(board) for board in official_board_values())
    daily_where = f"{where_full} and complaint_type in({problem_clause}) and community_board in({board_clause})"
    daily_rows, daily_pages = query_all(
        {
            "$select": "date_trunc_ymd(created_date) as day,community_board,complaint_type,count(*) as requests",
            "$where": daily_where,
            "$group": "day,community_board,complaint_type",
            "$order": "day,community_board,complaint_type",
        }
    )
    expected_daily_count = int(query({"$select": "count(*) as count", "$where": daily_where})[0]["count"])
    observed_daily_count = validate_aggregate_reconciliation(daily_rows, expected_daily_count)
    daily = complete_daily(daily_rows)
    if not daily["district"].map(is_official_district).all():
        raise RuntimeError("Daily aggregate contains a non-official Community District")

    backtest = run_injection_backtest(daily, events=1200)
    selected_config = next(
        config for config in candidate_configurations() if configuration_name(config) == backtest.selected_model
    )
    detector = {
        "robust_seasonal": detect_volume_signals,
        "nb_conformal": detect_nb_signals,
        "hybrid_nb_ewma": detect_hybrid_signals,
    }[selected_config.detector]
    raw_signals = merge_alert_episodes(
        detector(daily, as_of=ANALYSIS_END, thresholds=selected_config),
        cooldown_days=selected_config.cooldown_days,
    )
    recent_cutoff = ANALYSIS_END - timedelta(days=20)
    recent = [row for row in raw_signals if pd.to_datetime(row["date"]).date() >= recent_cutoff]
    candidate_pool = recent if len(recent) >= 40 else raw_signals[-80:]
    ranked_candidates = rank_signals(candidate_pool)
    ranked = ranked_candidates[:24]
    review_packet = build_blind_review_packet(daily, ranked_candidates)

    signal_rows: list[dict[str, Any]] = []
    trends_by_signal: dict[str, list[dict[str, Any]]] = {}
    for item in ranked:
        district = str(item["district"])
        problem = str(item["problem"])
        borough = parse_district(district.replace(" ", " ", 1))[1]
        if borough == "Unspecified":
            borough = district.rsplit(" ", 1)[0] if " " in district else "Unspecified"
        effect = float(item["effect"])
        display_effect = f"{effect:.1f}×"
        title = f"{problem} volume moved above its weekday baseline"
        signal = {
            "id": item["id"],
            "type": "volume_surge",
            "severity": "research_flag",
            "as_of": item["date"],
            "district": district,
            "borough": borough,
            "problem": problem,
            "agency": None,
            "observed": item["observed"],
            "expected": item["expected"],
            "effect": effect,
            "display_effect": display_effect,
            "uncertainty": "Eight matching weekdays; robust median and MAD baseline.",
            "persistence": int(item.get("persistence", 1)),
            "trigger": "Observed volume exceeded the selected research detector; human validation remains pending.",
            "evidence": [
                {
                    "label": "Observed requests",
                    "value": str(int(float(item["observed"]))),
                    "note": "Requests created on the signal date.",
                },
                {
                    "label": "Expected baseline",
                    "value": f"{float(item['expected']):.1f}",
                    "note": "Median of eight prior matching weekdays.",
                },
                {
                    "label": "Robust score",
                    "value": f"{float(item['anomaly_score']):.1f}",
                    "note": f"Calibrated evidence from {selected_config.detector}.",
                },
                {
                    "label": "Upper bound",
                    "value": f"{float(item.get('upper_bound', item['expected'])):.1f}",
                    "note": "Research prediction boundary selected on validation data.",
                },
            ],
            "data_quality_flags": [] if district != "Unspecified" else ["Community district unspecified"],
            "limitation": "Request counts describe reported service demand, not population need or agency quality.",
            "recommended_action": (
                "Check intake channels, duplicate patterns, and operational context "
                "before changing staffing or policy."
            ),
            "title": title,
            "priority_score": round(float(item["priority_score"]), 3),
            "model_version": "2.0.0",
            "episode_start": item.get("episode_start", item["date"]),
            "episode_end": item.get("episode_end", item["date"]),
            "upper_bound": round(float(item.get("upper_bound", item["expected"])), 2),
            "excess_count": round(
                float(item.get("excess_count", float(item["observed"]) - float(item["expected"]))), 2
            ),
            "calibrated_score": round(float(item.get("calibrated_score", item["anomaly_score"])), 2),
            "detector": str(item.get("detector", selected_config.detector)),
        }
        signal_rows.append(signal)
        group = daily.loc[(daily["district"] == district) & (daily["problem"] == problem)].sort_values("date")
        group = group.assign(baseline=matching_weekday_baseline(group))
        group = group.tail(180)
        trends_by_signal[str(item["id"])] = [
            {
                "date": str(row.date),
                "observed": int(row.requests),
                "baseline": None if pd.isna(row.baseline) else round(float(row.baseline), 1),
            }
            for row in group.itertuples(index=False)
        ]

    citywide = daily.groupby("date", as_index=False)["requests"].sum()
    citywide_points = [
        {"date": str(row.date), "observed": int(row.requests)} for row in citywide.itertuples(index=False)
    ]
    evaluation_daily = daily.loc[daily["date"] >= date(2026, 5, 1)]
    by_district: dict[str, list[dict[str, Any]]] = {}
    for district, group in evaluation_daily.groupby("district", sort=True):
        totals = group.groupby("date", as_index=False)["requests"].sum()
        by_district[str(district)] = [
            {"date": str(row.date), "observed": int(row.requests)} for row in totals.itertuples(index=False)
        ]
    by_problem: dict[str, list[dict[str, Any]]] = {}
    for problem, group in evaluation_daily.groupby("problem", sort=True):
        totals = group.groupby("date", as_index=False)["requests"].sum()
        by_problem[str(problem)] = [
            {"date": str(row.date), "observed": int(row.requests)} for row in totals.itertuples(index=False)
        ]
    board_counts = (
        daily.loc[daily["date"] >= ANALYSIS_END - timedelta(days=27)]
        .groupby("district", as_index=False)["requests"]
        .sum()
    )
    severity_by_district = {row["district"]: row["severity"] for row in reversed(signal_rows)}
    map_rows = []
    for row in board_counts.itertuples(index=False):
        district = str(row.district)
        borough = district.rsplit(" ", 1)[0] if district != "Unspecified" else "Unspecified"
        map_rows.append(
            {
                "district": district,
                "borough": borough,
                "requests": int(row.requests),
                "severity": severity_by_district.get(district, "normal"),
            }
        )

    agencies = query(
        {
            "$select": "agency,count(*) as requests",
            "$where": where_full,
            "$group": "agency",
            "$order": "requests desc",
            "$limit": "50",
        }
    )
    channels = query(
        {
            "$select": "open_data_channel_type,count(*) as requests",
            "$where": where_full,
            "$group": "open_data_channel_type",
            "$order": "requests desc",
        }
    )
    districts = sorted({row["district"] for row in map_rows if is_official_district(row["district"])})

    quality_month_where = "created_date between '2026-07-01T00:00:00' and '2026-07-31T23:59:59'"
    quality_counts = query(
        {
            "$select": "count(*) as total,count(closed_date) as with_closed,count(community_board) as with_district",
            "$where": quality_month_where,
        }
    )[0]
    month_total = int(quality_counts["total"])
    scenario_gate = all(value >= 0.70 for value in backtest.scenario_recall.values())
    synthetic_pass = (
        backtest.f1 >= 0.80
        and backtest.false_alerts_per_week <= 5
        and backtest.median_detection_delay_days <= 2
        and scenario_gate
    )
    readiness = "revalidation_required"

    snapshot: dict[str, Any] = {
        "meta": {
            "product": "NYC311 Pulse",
            "artifact_version": "2026.07-v1",
            "method_version": "2.0.0",
            "source_dataset": "NYC Open Data erm2-nwe9",
            "source_url": "https://data.cityofnewyork.us/resource/erm2-nwe9",
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
            "extracted_at": EXTRACTED_AT,
            "request_count": request_count,
            "readiness": readiness,
            "data_status": "complete",
            "model_status": readiness,
            "evaluation_protocol_version": "2.0.0",
            "fixed_snapshot": True,
        },
        "dimensions": {
            "boroughs": ["Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island"],
            "districts": districts,
            "agencies": [row["agency"] for row in agencies],
            "problems": top_problems,
            "channels": [row["open_data_channel_type"] for row in channels],
        },
        "summary": {
            "requests": request_count,
            "districts": len(districts),
            "signals": len(signal_rows),
            "high_signals": 0,
            "unresolved_as_of": unresolved_count,
            "aged_open_30_days": aged_open_count,
        },
        "signals": signal_rows,
        "trends": {
            "citywide_volume": citywide_points,
            "by_signal": trends_by_signal,
            "by_district": by_district,
            "by_problem": by_problem,
        },
        "map": map_rows,
        "quality": {
            "sample_period": "2026-07",
            "rows_checked": month_total,
            "closed_date_coverage": round(100 * int(quality_counts["with_closed"]) / month_total, 1),
            "district_field_coverage": round(100 * int(quality_counts["with_district"]) / month_total, 1),
            "quarantined_rows": 0,
            "aggregate_rows": len(daily_rows),
            "aggregate_pages": daily_pages,
            "aggregate_request_total": observed_daily_count,
            "aggregate_reconciled": True,
            "aggregate_min_date": str(min(row["day"][:10] for row in daily_rows)),
            "aggregate_max_date": str(max(row["day"][:10] for row in daily_rows)),
            "warnings": [
                "Closed-date coverage varies because open requests are right-censored.",
                "Community Board may contain Unspecified or non-residential joint-interest areas.",
                "Due Date is excluded because coverage is insufficient for a citywide SLA metric.",
            ],
        },
        "backtest": {
            "precision": backtest.precision,
            "recall": backtest.recall,
            "f1": backtest.f1,
            "false_alerts_per_week": backtest.false_alerts_per_week,
            "median_detection_delay_days": backtest.median_detection_delay_days,
            "injections": backtest.injections,
            "status": readiness,
        },
        "evaluation": {
            "protocol_version": "2.0.0",
            "protocol_sha256": backtest.protocol_sha256,
            "splits": {
                "train": [WINDOW_START, str(TRAIN_END)],
                "validation": [str(VALIDATION_START), str(VALIDATION_END)],
                "locked_test": ["2026-05-01", WINDOW_END],
            },
            "selected_model": backtest.selected_model,
            "candidate_validation": backtest.candidates,
            "locked_test": {
                "precision": backtest.precision,
                "recall": backtest.recall,
                "f1": backtest.f1,
                "false_alerts_per_week": backtest.false_alerts_per_week,
                "median_detection_delay_days": backtest.median_detection_delay_days,
                "scenario_recall": backtest.scenario_recall,
                "confidence_intervals": backtest.confidence_intervals,
                "events": backtest.injections,
                "passed": synthetic_pass,
            },
            "release_gates": {
                "f1_min": 0.80,
                "false_alerts_per_week_max": 5,
                "median_detection_delay_days_max": 2,
                "scenario_recall_min": 0.70,
                "real_precision_at_20_min": 0.65,
            },
            "human_review": {
                "status": "pending",
                "sample_size": 60,
                "precision_at_20": None,
                "externally_correlated_rate": None,
            },
            "review_packet": review_packet,
            "status": readiness,
        },
    }
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    snapshot["meta"]["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    return snapshot


def build_boundaries() -> dict[str, Any]:
    response = httpx.get(BOUNDARIES, params={"$limit": "100"}, timeout=120, follow_redirects=True)
    response.raise_for_status()
    geojson = response.json()
    allowed = {
        *range(101, 113),
        *range(201, 213),
        *range(301, 319),
        *range(401, 415),
        *range(501, 504),
    }
    features = []
    for feature in geojson.get("features", []):
        code = int(float(feature.get("properties", {}).get("boro_cd", 0)))
        if code in allowed:
            feature["properties"] = {"boro_cd": code}
            features.append(feature)
    if len(features) != 59:
        raise RuntimeError(f"Expected 59 community districts, received {len(features)}")
    return {"type": "FeatureCollection", "features": features}


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    boundaries = build_boundaries()
    snapshot_path = OUTPUT / "snapshot.json"
    boundary_path = OUTPUT / "community-districts.geojson"
    review_path = OUTPUT / "review-packet.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    boundary_path.write_text(json.dumps(boundaries), encoding="utf-8")
    review_path.write_text(json.dumps(snapshot["evaluation"]["review_packet"], indent=2), encoding="utf-8")
    manifest = {
        "artifact_version": snapshot["meta"]["artifact_version"],
        "created_from_snapshot": EXTRACTED_AT,
        "request_count": snapshot["meta"]["request_count"],
        "files": {
            snapshot_path.name: {
                "bytes": snapshot_path.stat().st_size,
                "sha256": hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
            },
            boundary_path.name: {
                "bytes": boundary_path.stat().st_size,
                "sha256": hashlib.sha256(boundary_path.read_bytes()).hexdigest(),
                "features": len(boundaries["features"]),
            },
            review_path.name: {
                "bytes": review_path.stat().st_size,
                "sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
                "cases": len(snapshot["evaluation"]["review_packet"]["cases"]),
            },
        },
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Built {snapshot['meta']['artifact_version']} with {len(snapshot['signals'])} signals")
