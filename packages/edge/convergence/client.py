from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

_OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"

_FORECAST_PARAMS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "cloud_cover",
    "soil_temperature_0cm",
    "soil_moisture_0_to_1cm",
]


def fetch_forecast(
    lat: float,
    lon: float,
    forecast_hours: int = 24,
    timezone_str: str = "auto",
) -> dict:
    """Fetch weather forecast from Open-Meteo for a geographic point.

    Args:
        lat: Latitude (-90 to 90).
        lon: Longitude (-180 to 180).
        forecast_hours: Number of hours to forecast (max 240).
        timezone_str: Timezone string or "auto" for automatic detection.

    Returns:
        Raw API response as a dictionary.

    Raises:
        ValueError: If coordinates are out of range or forecast_hours > 240.
        RuntimeError: If the API request fails.
    """
    if not (-90 <= lat <= 90):
        raise ValueError(f"Latitude out of range: {lat}")
    if not (-180 <= lon <= 180):
        raise ValueError(f"Longitude out of range: {lon}")
    if forecast_hours > 240:
        raise ValueError(f"forecast_hours must be <= 240, got {forecast_hours}")

    params: dict[str, str | int | float] = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join(_FORECAST_PARAMS[:7]),
        "hourly": ",".join(_FORECAST_PARAMS),
        "timezone": timezone_str,
        "forecast_hours": forecast_hours,
    }

    url = f"{_OPEN_METEO_FORECAST}?{urlencode(params)}"
    logger.info("Fetching Open-Meteo forecast: lat=%.4f lon=%.4f hours=%d", lat, lon, forecast_hours)

    request = Request(url, headers={"User-Agent": "Heimdall-Meteo/1.0"})
    with urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    logger.info("Open-Meteo response received: %d hourly entries", len(data.get("hourly", {}).get("time", [])))
    return data


def parse_current_weather(raw: dict) -> dict:
    """Extract current weather from raw Open-Meteo response."""
    current = raw.get("current", {})
    return {
        "timestamp": current.get("time", datetime.now(timezone.utc).isoformat()),
        "temperature_c": float(current.get("temperature_2m", 0)),
        "relative_humidity_pct": float(current.get("relative_humidity_2m", 0)),
        "wind_speed_kmh": float(current.get("wind_speed_10m", 0)),
        "wind_direction_deg": float(current.get("wind_direction_10m", 0)),
        "wind_gusts_kmh": float(current.get("wind_gusts_10m", 0)),
        "precipitation_mm": float(current.get("precipitation", 0)),
        "cloud_cover_pct": float(current.get("cloud_cover", 0)),
        "soil_temperature_c": float(current.get("soil_temperature_0cm", 0)),
        "soil_moisture_pct": float(current.get("soil_moisture_0_to_1cm", 0)),
    }


def parse_hourly_forecast(raw: dict, limit: int | None = None) -> list[dict]:
    """Extract hourly forecast entries from raw Open-Meteo response."""
    hourly = raw.get("hourly", {})
    times = hourly.get("time", [])
    count = min(len(times), limit) if limit else len(times)

    entries: list[dict] = []
    for i in range(count):
        entries.append({
            "timestamp": times[i],
            "temperature_c": float(_safe_get(hourly, "temperature_2m", i)),
            "relative_humidity_pct": float(_safe_get(hourly, "relative_humidity_2m", i)),
            "wind_speed_kmh": float(_safe_get(hourly, "wind_speed_10m", i)),
            "wind_direction_deg": float(_safe_get(hourly, "wind_direction_10m", i)),
            "wind_gusts_kmh": float(_safe_get(hourly, "wind_gusts_10m", i)),
            "precipitation_mm": float(_safe_get(hourly, "precipitation", i)),
            "cloud_cover_pct": float(_safe_get(hourly, "cloud_cover", i)),
        })
    return entries


def _safe_get(data: dict, key: str, index: int, default: float = 0.0) -> float:
    values = data.get(key, [])
    if index < len(values) and values[index] is not None:
        return float(values[index])
    return default
