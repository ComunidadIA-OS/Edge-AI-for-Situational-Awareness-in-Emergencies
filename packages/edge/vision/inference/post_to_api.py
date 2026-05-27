# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Saúl Briceño, Carlos Langa, and ComunidadIA-OS contributors
#
# Part of Heimdall's vision-inference path — a derivative work of Ultralytics
# YOLO — licensed under AGPL-3.0. See LICENSE-AGPL-3.0.txt and NOTICE.

"""Convert YOLO detections + drone telemetry to a FireDetectionPayload and POST it.

Flat-earth approximation (error < 1% for altitudes under 500 m at mid-latitudes).
Camera assumed nadir-pointing. Heading rotates the image footprint in world space.

Typical call from the inference loop:

    poster = DetectionPoster(api_url="http://localhost:8000", drone_lat=41.64,
                              drone_lon=-0.88, drone_alt=120.0, drone_heading=45.0)
    poster.post(detections, frame_w=640, frame_h=512)
"""
from __future__ import annotations

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Sequence

import requests

logger = logging.getLogger(__name__)

# FLIR Boson 640 with standard 50-mm lens ≈ 32° HFOV; adjust per lens.
DEFAULT_HFOV_DEG = 32.0
_EARTH_R = 6_378_137.0
_POST_TIMEOUT_S = 5.0


def pixel_to_geo(
    px: float,
    py: float,
    img_w: int,
    img_h: int,
    drone_lat: float,
    drone_lon: float,
    drone_alt_m: float,
    drone_heading_deg: float,
    hfov_deg: float = DEFAULT_HFOV_DEG,
) -> tuple[float, float]:
    """Map a single pixel coordinate to (lat, lon).

    Args:
        px, py: Pixel position (origin top-left, y positive downward).
        img_w, img_h: Frame dimensions in pixels.
        drone_lat, drone_lon: Drone ground-track position (decimal degrees).
        drone_alt_m: AGL altitude in metres.
        drone_heading_deg: Drone nose heading 0=N, 90=E (degrees clockwise).
        hfov_deg: Camera horizontal field of view in degrees.

    Returns:
        (lat, lon) of the ground point below the pixel.
    """
    gsd = (2.0 * drone_alt_m * math.tan(math.radians(hfov_deg / 2.0))) / img_w

    dx_px = px - img_w / 2.0
    dy_px = py - img_h / 2.0

    h = math.radians(drone_heading_deg)
    east_m = gsd * (dx_px * math.cos(h) + dy_px * math.sin(h))
    north_m = gsd * (-dx_px * math.sin(h) - dy_px * math.cos(h))

    lat_rad = math.radians(drone_lat)
    d_lat = math.degrees(north_m / _EARTH_R)
    d_lon = math.degrees(east_m / (_EARTH_R * math.cos(lat_rad)))

    return drone_lat + d_lat, drone_lon + d_lon


def bbox_to_geo_polygon(
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
    img_w: int,
    img_h: int,
    drone_lat: float,
    drone_lon: float,
    drone_alt_m: float,
    drone_heading_deg: float,
    hfov_deg: float = DEFAULT_HFOV_DEG,
) -> tuple[list[list[float]], tuple[float, float], float]:
    """Convert a pixel bounding box to a GeoJSON polygon ring, centroid, and area.

    Returns:
        (ring, (centroid_lat, centroid_lon), area_ha)
        ring: closed list of [lon, lat] pairs (GeoJSON order).
    """
    corners_px = [
        (x_min, y_min),
        (x_max, y_min),
        (x_max, y_max),
        (x_min, y_max),
    ]
    corners_geo: list[tuple[float, float]] = [
        pixel_to_geo(px, py, img_w, img_h, drone_lat, drone_lon,
                     drone_alt_m, drone_heading_deg, hfov_deg)
        for px, py in corners_px
    ]

    ring = [[lon, lat] for lat, lon in corners_geo] + [[corners_geo[0][1], corners_geo[0][0]]]

    c_lat = sum(p[0] for p in corners_geo) / 4.0
    c_lon = sum(p[1] for p in corners_geo) / 4.0

    gsd = (2.0 * drone_alt_m * math.tan(math.radians(hfov_deg / 2.0))) / img_w
    w_m = (x_max - x_min) * gsd
    h_m = (y_max - y_min) * gsd
    area_ha = (w_m * h_m) / 10_000.0

    return ring, (c_lat, c_lon), max(area_ha, 0.001)


def build_payload(
    detections: Sequence[dict],
    img_w: int,
    img_h: int,
    drone_lat: float,
    drone_lon: float,
    drone_alt_m: float,
    drone_heading_deg: float,
    drone_speed_kmh: float = 0.0,
    hfov_deg: float = DEFAULT_HFOV_DEG,
    fuel_type_id: int = 4,
    slope_deg: float = 0.0,
) -> dict:
    """Build a FireDetectionPayload dict from one or more YOLO detections.

    When multiple detections exist, merges their bboxes into the union bounding
    box so the API sees a single fire footprint per frame.

    Args:
        detections: List of dicts from predict_frame() with keys
                    x_min, y_min, x_max, y_max, confidence.

    Returns:
        Dict matching the DetectionRequest schema of convergence/api.py.
    """
    if not detections:
        raise ValueError("detections must not be empty")

    x_min = min(d["x_min"] for d in detections)
    y_min = min(d["y_min"] for d in detections)
    x_max = max(d["x_max"] for d in detections)
    y_max = max(d["y_max"] for d in detections)
    confidence = max(d["confidence"] for d in detections)

    ring, (c_lat, c_lon), area_ha = bbox_to_geo_polygon(
        x_min, y_min, x_max, y_max,
        img_w, img_h,
        drone_lat, drone_lon, drone_alt_m, drone_heading_deg,
        hfov_deg,
    )

    hotspots = [
        {
            "lat": pixel_to_geo(
                (d["x_min"] + d["x_max"]) / 2,
                (d["y_min"] + d["y_max"]) / 2,
                img_w, img_h,
                drone_lat, drone_lon, drone_alt_m, drone_heading_deg, hfov_deg,
            )[0],
            "lon": pixel_to_geo(
                (d["x_min"] + d["x_max"]) / 2,
                (d["y_min"] + d["y_max"]) / 2,
                img_w, img_h,
                drone_lat, drone_lon, drone_alt_m, drone_heading_deg, hfov_deg,
            )[1],
            "temperature_c": 380.0,
            "confidence": d["confidence"],
        }
        for d in detections
    ]

    return {
        "drone_telemetry": {
            "lat": drone_lat,
            "lon": drone_lon,
            "altitud_m": drone_alt_m,
            "heading_deg": drone_heading_deg,
            "speed_kmh": drone_speed_kmh,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "perimeter": {"coordinates": [ring]},
        "area_ha": area_ha,
        "centroid": {"lat": c_lat, "lon": c_lon},
        "confidence": confidence,
        "fuel_type_id": fuel_type_id,
        "slope_deg": slope_deg,
        "front_depth_m": 0.0,
        "hotspots": hotspots,
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }


class DetectionPoster:
    """Async (non-blocking) poster — keeps the inference loop at full FPS.

    Rate-limited to at most one POST per ``min_interval_s``. Excess detections
    are dropped; the inference loop must not stall on network I/O.
    """

    def __init__(
        self,
        api_url: str,
        drone_lat: float,
        drone_lon: float,
        drone_alt_m: float,
        drone_heading_deg: float,
        drone_speed_kmh: float = 0.0,
        hfov_deg: float = DEFAULT_HFOV_DEG,
        fuel_type_id: int = 4,
        slope_deg: float = 0.0,
        min_interval_s: float = 2.0,
    ) -> None:
        self._url = api_url.rstrip("/") + "/detect"
        self._drone_lat = drone_lat
        self._drone_lon = drone_lon
        self._drone_alt_m = drone_alt_m
        self._drone_heading_deg = drone_heading_deg
        self._drone_speed_kmh = drone_speed_kmh
        self._hfov_deg = hfov_deg
        self._fuel_type_id = fuel_type_id
        self._slope_deg = slope_deg
        self._min_interval_s = min_interval_s
        self._last_post_ts: float = 0.0
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="det-poster")

    def post(
        self,
        detections: Sequence[dict],
        img_w: int,
        img_h: int,
    ) -> None:
        """Fire-and-forget POST if rate limit allows. Never raises."""
        if not detections:
            return
        now = time.monotonic()
        if now - self._last_post_ts < self._min_interval_s:
            return
        self._last_post_ts = now

        try:
            payload = build_payload(
                detections, img_w, img_h,
                self._drone_lat, self._drone_lon, self._drone_alt_m,
                self._drone_heading_deg, self._drone_speed_kmh,
                self._hfov_deg, self._fuel_type_id, self._slope_deg,
            )
        except Exception:
            logger.exception("Failed to build detection payload; skipping POST")
            return

        self._executor.submit(self._send, payload)

    def _send(self, payload: dict) -> None:
        try:
            r = requests.post(self._url, json=payload, timeout=_POST_TIMEOUT_S)
            if r.ok:
                logger.debug("POST /detect ok: area_ha=%.3f", payload["area_ha"])
            else:
                logger.warning("POST /detect %d: %s", r.status_code, r.text[:120])
        except Exception:
            logger.warning("POST /detect failed (API down?)", exc_info=False)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)
