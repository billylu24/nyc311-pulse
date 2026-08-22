from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


class ArtifactUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=1)
def load_snapshot() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "public" / "data" / "snapshot.json"
    if not path.exists():
        raise ArtifactUnavailable(f"Snapshot artifact not found: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))
