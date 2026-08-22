"""Score a completed blind-review packet and optionally promote the artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POSITIVE = {"clear_anomaly", "plausible_anomaly"}
ALLOWED = POSITIVE | {"unsupported", "uncertain"}


def score(packet: dict[str, Any], labels: list[dict[str, Any]]) -> dict[str, Any]:
    expected = {case["case_id"] for case in packet["cases"]}
    received = {row["case_id"] for row in labels}
    if received != expected or len(labels) != 60:
        raise ValueError("Labels must contain each of the 60 review case IDs exactly once")
    if any(row.get("label") not in ALLOWED for row in labels):
        raise ValueError(f"Labels must be one of: {', '.join(sorted(ALLOWED))}")
    by_id = {row["case_id"]: row for row in labels}
    top_token = hashlib.sha256(f"{packet['seed']}|top20".encode()).hexdigest()[:12]
    top_cases = [case for case in packet["cases"] if case["group_token"] == top_token]
    positives = sum(by_id[case["case_id"]]["label"] in POSITIVE for case in top_cases)
    evidence_count = sum(bool(row.get("external_evidence")) for row in labels)
    precision = positives / 20
    return {
        "status": "passed" if precision >= 0.65 else "failed",
        "sample_size": 60,
        "top20_positive": positives,
        "precision_at_20": round(precision, 3),
        "externally_correlated_rate": round(evidence_count / 60, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("labels", type=Path, help="JSON list with case_id, label, and optional external_evidence")
    parser.add_argument("--update-artifact", action="store_true")
    args = parser.parse_args()
    snapshot_path = ROOT / "public" / "data" / "snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    payload = json.loads(args.labels.read_text(encoding="utf-8"))
    labels = payload["cases"] if isinstance(payload, dict) and "cases" in payload else payload
    result = score(snapshot["evaluation"]["review_packet"], labels)
    print(json.dumps(result, indent=2))
    if not args.update_artifact:
        return
    snapshot["evaluation"]["human_review"] = result
    validated = result["status"] == "passed" and snapshot["evaluation"]["locked_test"]["passed"]
    status = "validated" if validated else "revalidation_required"
    snapshot["evaluation"]["status"] = status
    snapshot["meta"]["model_status"] = status
    snapshot["meta"]["readiness"] = status
    snapshot["backtest"]["status"] = status
    for signal in snapshot["signals"]:
        signal["severity"] = "high" if validated and signal["calibrated_score"] >= 5 else (
            "watch" if validated else "research_flag"
        )
    snapshot["summary"]["high_signals"] = sum(row["severity"] == "high" for row in snapshot["signals"])
    snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
