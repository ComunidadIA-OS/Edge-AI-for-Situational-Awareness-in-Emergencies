"""FastAPI surface for the convergence (meteo + propagation) pipeline.

One process == one drone. The module owns a single in-memory ``ReportHistory``
and a single "latest payload / latest report" cache so the inference loop and
the HTTP handlers share state without a database.

Endpoints
---------
POST /detect           Ingest a FireDetectionPayload from the drone, run the
                       meteo analysis once, update history, cache the result.
GET  /latest           Return the most recent MeteoReport (JSON).
GET  /history          Return the dA/dt and d2A/dt2 series and timestamps.
POST /history/reset    Clear the ring buffer (e.g. drone re-armed).
GET  /health           Liveness probe.

Background loop
---------------
If REFRESH_SECONDS > 0 and a payload has been ingested, a task re-runs
``run_from_detection_payload`` with the last known payload every N seconds.
This keeps weather data fresh and grows the derivative history even when the
drone is not pushing new detections.

Run
---
    uvicorn convergence.api:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from convergence.history import ReportHistory
from convergence.models import (
    CriticalInfrastructure,
    DroneTelemetry,
    FireDetectionPayload,
    GeoPoint,
    GeoPolygon,
    Hotspot,
    MeteoReport,
)
from convergence.orchestrator import run_from_detection_payload

logger = logging.getLogger("convergence.api")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid int for %s=%r, using default %d", name, raw, default)
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid float for %s=%r, using default %f", name, raw, default)
        return default


HISTORY_SIZE = _env_int("HISTORY_SIZE", 30)
REFRESH_SECONDS = _env_float("REFRESH_SECONDS", 60.0)
FORECAST_HOURS = _env_int("FORECAST_HOURS", 24)
DRONE_ID = os.environ.get("DRONE_ID", "drone-0")


class _State:
    """Process-wide cache. One per Python process == one drone."""

    def __init__(self) -> None:
        self.history = ReportHistory(max_size=HISTORY_SIZE)
        self.last_payload: FireDetectionPayload | None = None
        self.last_report: MeteoReport | None = None
        self.last_updated: datetime | None = None
        self.detections_seen: int = 0
        self.refresh_ticks: int = 0
        self.lock = asyncio.Lock()


STATE = _State()


class GeoPointIn(BaseModel):
    lat: float
    lon: float


class GeoPolygonIn(BaseModel):
    coordinates: list[list[list[float]]]


class HotspotIn(BaseModel):
    lat: float
    lon: float
    temperature_c: float
    confidence: float


class DroneTelemetryIn(BaseModel):
    lat: float
    lon: float
    altitud_m: float
    heading_deg: float
    speed_kmh: float
    timestamp: str


class CriticalInfraIn(BaseModel):
    name: str
    type: str
    lat: float
    lon: float
    distance_m: float = 0.0
    threat_level: str = "moderate"


class DetectionRequest(BaseModel):
    drone_telemetry: DroneTelemetryIn
    perimeter: GeoPolygonIn
    area_ha: float = Field(gt=0)
    centroid: GeoPointIn
    confidence: float = Field(ge=0, le=1)
    fuel_type_id: int = Field(default=1, ge=1, le=13)
    slope_deg: float = 0.0
    front_depth_m: float = 0.0
    hotspots: list[HotspotIn] = Field(default_factory=list)
    detected_at: str = ""
    forecast_hours: int | None = None
    infrastructure: list[CriticalInfraIn] = Field(default_factory=list)


def _to_payload(req: DetectionRequest) -> FireDetectionPayload:
    return FireDetectionPayload(
        drone_telemetry=DroneTelemetry(**req.drone_telemetry.model_dump()),
        perimeter=GeoPolygon(coordinates=req.perimeter.coordinates),
        area_ha=req.area_ha,
        centroid=GeoPoint(**req.centroid.model_dump()),
        confidence=req.confidence,
        fuel_type_id=req.fuel_type_id,
        slope_deg=req.slope_deg,
        front_depth_m=req.front_depth_m,
        hotspots=[Hotspot(**h.model_dump()) for h in req.hotspots],
        detected_at=req.detected_at,
    )


def _to_infra(items: list[CriticalInfraIn]) -> list[CriticalInfrastructure] | None:
    if not items:
        return None
    return [CriticalInfrastructure(**i.model_dump()) for i in items]


async def _run_analysis(
    payload: FireDetectionPayload,
    forecast_hours: int,
    infrastructure: list[CriticalInfrastructure] | None,
) -> MeteoReport:
    """Run the synchronous orchestrator off the event loop."""
    return await asyncio.to_thread(
        run_from_detection_payload,
        payload,
        forecast_hours,
        infrastructure,
        STATE.history,
    )


async def _refresh_loop() -> None:
    """Periodically re-run the analysis with the last known payload.

    Keeps weather fresh and grows the derivative history between drone pushes.
    Exits cleanly when the task is cancelled at shutdown.
    """
    if REFRESH_SECONDS <= 0:
        logger.info("Refresh loop disabled (REFRESH_SECONDS=%.2f)", REFRESH_SECONDS)
        return

    logger.info("Refresh loop started (every %.1fs)", REFRESH_SECONDS)
    while True:
        try:
            await asyncio.sleep(REFRESH_SECONDS)
            if STATE.last_payload is None:
                continue
            async with STATE.lock:
                payload = STATE.last_payload
                if payload is None:
                    continue
                try:
                    report = await _run_analysis(payload, FORECAST_HOURS, None)
                    STATE.last_report = report
                    STATE.last_updated = datetime.now(timezone.utc)
                    STATE.refresh_ticks += 1
                    logger.info(
                        "Refresh tick %d: FWI=%.1f trend=%s",
                        STATE.refresh_ticks,
                        report.prediction.fire_weather_index,
                        report.prediction.trend,
                    )
                except Exception:
                    logger.exception("Refresh tick failed; will retry next interval")
        except asyncio.CancelledError:
            logger.info("Refresh loop cancelled")
            raise
        except Exception:
            logger.exception("Unexpected error in refresh loop; continuing")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_refresh_loop(), name="convergence-refresh-loop")
    logger.info(
        "API up | drone=%s history_size=%d refresh=%.1fs forecast=%dh",
        DRONE_ID, HISTORY_SIZE, REFRESH_SECONDS, FORECAST_HOURS,
    )
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        logger.info("API shutdown")


app = FastAPI(
    title="XHeimdall Convergence API",
    version="0.1.0",
    description="Fire detection ingestion + meteo propagation forecast.",
    lifespan=lifespan,
)

_cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "drone_id": DRONE_ID,
        "detections_seen": STATE.detections_seen,
        "refresh_ticks": STATE.refresh_ticks,
        "history_len": len(STATE.history),
        "last_updated": STATE.last_updated.isoformat() if STATE.last_updated else None,
        "has_report": STATE.last_report is not None,
    }


@app.post("/detect")
async def detect(req: DetectionRequest) -> dict[str, Any]:
    payload = _to_payload(req)
    infra = _to_infra(req.infrastructure)
    hours = req.forecast_hours or FORECAST_HOURS

    async with STATE.lock:
        try:
            report = await _run_analysis(payload, hours, infra)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.exception("Detection analysis failed")
            raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

        STATE.last_payload = payload
        STATE.last_report = report
        STATE.last_updated = datetime.now(timezone.utc)
        STATE.detections_seen += 1

    return report.to_dict()


@app.get("/latest")
async def latest() -> dict[str, Any]:
    if STATE.last_report is None:
        raise HTTPException(status_code=404, detail="No report yet; POST /detect first")
    return STATE.last_report.to_dict()


@app.get("/history")
async def history() -> dict[str, Any]:
    entries = STATE.history.entries
    growth, accel = STATE.history.derivatives()
    return {
        "drone_id": DRONE_ID,
        "size": len(entries),
        "capacity": HISTORY_SIZE,
        "growth_rate_m2_s": growth,
        "acceleration_m2_s2": accel,
        "entries": [asdict(e) for e in entries],
    }


@app.post("/history/reset")
async def history_reset() -> dict[str, Any]:
    async with STATE.lock:
        STATE.history.clear()
    return {"status": "cleared", "size": 0}
