"""Export FastAPI's contract for the generated TypeScript client."""

from __future__ import annotations

import json
from pathlib import Path

from api.index import app

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public" / "openapi.json"

if __name__ == "__main__":
    OUTPUT.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
