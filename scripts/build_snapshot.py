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
import pandas as pd

from analytics.backtest import run_injection_backtest
from analytics.signals import detect_volume_signals, rank_signals

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public" / "data"
API = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
BOUNDARIES = "https://data.cityofnewyork.us/resource/5crt-au7u.geojson"
WINDOW_START = "2024-08-01"
WINDOW_END = "2026-07-31"
EXTRACTED_AT = "2026-08-21"
ANALYSIS_START = date(2026, 5, 1)
ANALYSIS_END = date(2026, 7, 31)


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


def complete_daily(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["day"]).dt.date
    frame["district"] = frame["community_board"].map(lambda value: parse_district(value)[0])
    frame["problem"] = frame["complaint_type"]
    frame["requests"] = frame["requests"].astype(int)
    dates = pd.DataFrame({"date": pd.date_range(ANALYSIS_START, ANALYSIS_END, freq="D").date})
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


def build_snapshot() -> dict[str, Any]:
    where_full = f"created_date between '{WINDOW_START}T00:00:00' and '{WINDOW_END}T23:59:59'"
    where_analysis = f"created_date between '{ANALYSIS_START}T00:00:00' and '{ANALYSIS_END}T23:59:59'"

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
            "$where": where_analysis,
            "$group": "complaint_type",
            "$order": "requests desc",
            "$limit": "12",
        }
    )
    top_problems = [row["complaint_type"] for row in top_problem_rows]
    problem_clause = ",".join(sql_quote(problem) for problem in top_problems)
    daily_rows = query(
        {
            "$select": "date_trunc_ymd(created_date) as day,community_board,complaint_type,count(*) as requests",
            "$where": f"{where_analysis} and complaint_type in({problem_clause})",
            "$group": "day,community_board,complaint_type",
            "$order": "day",
            "$limit": "50000",
        }
    )
    daily = complete_daily(daily_rows)
    daily = daily.loc[daily["district"].map(is_official_district)].reset_index(drop=True)

    raw_signals = detect_volume_signals(daily, as_of=ANALYSIS_END)
    recent_cutoff = ANALYSIS_END - timedelta(days=20)
    recent = [row for row in raw_signals if pd.to_datetime(row["date"]).date() >= recent_cutoff]
    ranked = rank_signals(recent or raw_signals[-40:])[:24]

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
            "severity": item["severity"],
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
            "trigger": "Observed volume exceeded the validated robust-z, ratio, and absolute-delta thresholds.",
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
                    "note": "Difference divided by scaled median absolute deviation.",
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
        }
        signal_rows.append(signal)
        group = daily.loc[(daily["district"] == district) & (daily["problem"] == problem)].sort_values("date")
        group = group.assign(baseline=matching_weekday_baseline(group))
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
            "$where": where_analysis,
            "$group": "agency",
            "$order": "requests desc",
            "$limit": "50",
        }
    )
    channels = query(
        {
            "$select": "open_data_channel_type,count(*) as requests",
            "$where": where_analysis,
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
    backtest = run_injection_backtest(daily)
    readiness = "validated" if backtest.f1 >= 0.75 and backtest.false_alerts_per_week <= 10 else "exploratory"

    snapshot: dict[str, Any] = {
        "meta": {
            "product": "NYC311 Pulse",
            "artifact_version": "2026.07-v1",
            "method_version": "1.0.0",
            "source_dataset": "NYC Open Data erm2-nwe9",
            "source_url": "https://data.cityofnewyork.us/resource/erm2-nwe9",
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
            "extracted_at": EXTRACTED_AT,
            "request_count": request_count,
            "readiness": readiness,
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
            "high_signals": sum(row["severity"] == "high" for row in signal_rows),
            "unresolved_as_of": unresolved_count,
            "aged_open_30_days": aged_open_count,
        },
        "signals": signal_rows,
        "trends": {"citywide_volume": citywide_points, "by_signal": trends_by_signal},
        "map": map_rows,
        "quality": {
            "sample_period": "2026-07",
            "rows_checked": month_total,
            "closed_date_coverage": round(100 * int(quality_counts["with_closed"]) / month_total, 1),
            "district_field_coverage": round(100 * int(quality_counts["with_district"]) / month_total, 1),
            "quarantined_rows": 0,
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
    snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    boundary_path.write_text(json.dumps(boundaries), encoding="utf-8")
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
        },
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Built {snapshot['meta']['artifact_version']} with {len(snapshot['signals'])} signals")
