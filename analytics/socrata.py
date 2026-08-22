"""Resilient, privacy-minimized Socrata extraction helpers."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

from .contracts import ServiceRequest

DATASET_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
SAFE_FIELDS = [
    "unique_key",
    "created_date",
    "closed_date",
    "agency",
    "agency_name",
    "complaint_type",
    "descriptor",
    "status",
    "borough",
    "community_board",
    "open_data_channel_type",
]


class SocrataClient:
    def __init__(self, app_token: str | None = None, timeout: float = 60.0) -> None:
        token = app_token or os.getenv("SOCRATA_APP_TOKEN")
        headers = {"X-App-Token": token} if token else {}
        self.client = httpx.Client(timeout=timeout, headers=headers, follow_redirects=True)

    def query(self, params: dict[str, str], attempts: int = 5) -> list[dict[str, Any]]:
        for attempt in range(attempts):
            try:
                response = self.client.get(DATASET_URL, params=params)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, list):
                    raise ValueError("Socrata response was not a list")
                return payload
            except (httpx.HTTPError, ValueError):
                if attempt == attempts - 1:
                    raise
                time.sleep(min(2**attempt, 16))
        return []

    def iter_requests(
        self, start: str, end: str, *, page_size: int = 50_000, offset: int = 0
    ) -> Iterator[list[ServiceRequest]]:
        where = f"created_date between '{start}T00:00:00' and '{end}T23:59:59'"
        while True:
            rows = self.query(
                {
                    "$select": ",".join(SAFE_FIELDS),
                    "$where": where,
                    "$order": "unique_key",
                    "$limit": str(page_size),
                    "$offset": str(offset),
                }
            )
            if not rows:
                return
            yield [ServiceRequest.model_validate(row) for row in rows]
            offset += len(rows)
            if len(rows) < page_size:
                return


def extract_to_ndjson(output_dir: Path, start: str, end: str) -> int:
    """Write resumable raw partitions outside Git; each page is validated before commit."""

    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "checkpoint.json"
    offset = 0
    if checkpoint_path.exists():
        offset = int(json.loads(checkpoint_path.read_text(encoding="utf-8"))["offset"])
    client = SocrataClient()
    for page in client.iter_requests(start, end, offset=offset):
        part_path = output_dir / f"part-{offset:09d}.ndjson"
        with part_path.open("w", encoding="utf-8") as handle:
            for row in page:
                handle.write(row.model_dump_json() + "\n")
        offset += len(page)
        checkpoint_path.write_text(json.dumps({"offset": offset}), encoding="utf-8")
    return offset
