import hashlib

from scripts.score_review import score


def test_blind_review_gate_requires_thirteen_top20_positives():
    seed = 311
    top_token = hashlib.sha256(f"{seed}|top20".encode()).hexdigest()[:12]
    control_token = hashlib.sha256(f"{seed}|matched_control".encode()).hexdigest()[:12]
    cases = [
        {"case_id": f"CASE-{index:02d}", "group_token": top_token if index < 20 else control_token}
        for index in range(60)
    ]
    labels = [
        {
            "case_id": case["case_id"],
            "label": "clear_anomaly" if index < 13 else "unsupported",
            "external_evidence": ["official-source"] if index == 0 else [],
        }
        for index, case in enumerate(cases)
    ]
    result = score({"seed": seed, "cases": cases}, labels)
    assert result["status"] == "passed"
    assert result["precision_at_20"] == 0.65
