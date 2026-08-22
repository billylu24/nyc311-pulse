from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models import Signal
from .store import ArtifactUnavailable, load_snapshot

app = FastAPI(title="NYC311 Pulse API", version="1.0.0", docs_url="/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://nyc311-pulse.vercel.app"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(ArtifactUnavailable)
async def artifact_error(_: Request, exc: ArtifactUnavailable) -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": {"code": "artifact_unavailable", "message": str(exc)}})


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": "request_error", "message": detail}})


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "Invalid query parameters", "details": exc.errors()}},
    )


@app.get("/healthz")
def health() -> dict[str, Any]:
    snapshot = load_snapshot()
    return {"status": "ok", "version": "1.0.0", "artifact": snapshot["meta"]["artifact_version"]}


@app.get("/v1/meta")
def meta() -> dict[str, Any]:
    return load_snapshot()["meta"]


@app.get("/v1/dimensions")
def dimensions() -> dict[str, Any]:
    return load_snapshot()["dimensions"]


@app.get("/v1/signals", response_model=list[Signal])
def signals(
    borough: str | None = None,
    district: str | None = None,
    problem: str | None = None,
    agency: str | None = None,
    signal_type: str | None = Query(default=None, alias="type"),
    severity: Literal["high", "watch"] | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    rows = load_snapshot()["signals"]
    filters = {
        "borough": borough,
        "district": district,
        "problem": problem,
        "agency": agency,
        "type": signal_type,
        "severity": severity,
    }
    for key, value in filters.items():
        if value:
            rows = [row for row in rows if str(row.get(key, "")).lower() == value.lower()]
    return rows[offset : offset + limit]


@app.get("/v1/signals/{signal_id}", response_model=Signal)
def signal_detail(signal_id: str) -> dict[str, Any]:
    for row in load_snapshot()["signals"]:
        if row["id"] == signal_id:
            return row
    raise HTTPException(status_code=404, detail=f"Unknown signal: {signal_id}")


@app.get("/v1/trends")
def trends(
    metric: Literal["volume"] = "volume",
    signal_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    snapshot = load_snapshot()
    try:
        start = date.fromisoformat(start_date) if start_date else None
        end = date.fromisoformat(end_date) if end_date else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Dates must use YYYY-MM-DD") from exc
    window_start = date.fromisoformat(snapshot["meta"]["window_start"])
    window_end = date.fromisoformat(snapshot["meta"]["window_end"])
    if start and (start < window_start or start > window_end):
        raise HTTPException(status_code=422, detail="start_date falls outside the snapshot")
    if end and (end < window_start or end > window_end):
        raise HTTPException(status_code=422, detail="end_date falls outside the snapshot")
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="start_date must not be after end_date")
    rows = snapshot["trends"]["by_signal"].get(signal_id, []) if signal_id else snapshot["trends"]["citywide_volume"]
    if signal_id and not rows:
        raise HTTPException(status_code=404, detail=f"No trend for signal: {signal_id}")
    if start_date:
        rows = [row for row in rows if row["date"] >= start_date]
    if end_date:
        rows = [row for row in rows if row["date"] <= end_date]
    return {"metric": metric, "points": rows}


@app.get("/v1/map")
def map_values(metric: Literal["requests", "severity"] = "severity") -> dict[str, Any]:
    return {"metric": metric, "districts": load_snapshot()["map"]}


@app.get("/v1/quality")
def quality() -> dict[str, Any]:
    return load_snapshot()["quality"]
