from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

FireIntensity = Literal["low", "moderate", "high", "extreme"]
FireTrend = Literal["growing", "stable", "shrinking", "extinguishing"]
RiskLevel = Literal["low", "moderate", "high", "extreme"]
FuelTypeId = Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]


@dataclass
class GeoPoint:
    lat: float
    lon: float

    def to_geojson(self) -> list[float]:
        return [self.lon, self.lat]


@dataclass
class GeoPolygon:
    coordinates: list[list[list[float]]]

    def to_geojson(self) -> dict:
        return {"type": "Polygon", "coordinates": self.coordinates}


@dataclass
class Hotspot:
    lat: float
    lon: float
    temperature_c: float
    confidence: float

    def to_dict(self) -> dict:
        return {"lat": self.lat, "lon": self.lon, "temperature_c": self.temperature_c, "confidence": self.confidence}


@dataclass
class DroneTelemetry:
    lat: float
    lon: float
    altitud_m: float
    heading_deg: float
    speed_kmh: float
    timestamp: str


@dataclass
class WeatherCurrent:
    timestamp: str
    temperature_c: float
    relative_humidity_pct: float
    wind_speed_kmh: float
    wind_direction_deg: float
    wind_gusts_kmh: float
    precipitation_mm: float
    cloud_cover_pct: float
    soil_temperature_c: float
    soil_moisture_pct: float


@dataclass
class WeatherHourly:
    timestamp: str
    temperature_c: float
    relative_humidity_pct: float
    wind_speed_kmh: float
    wind_direction_deg: float
    wind_gusts_kmh: float
    precipitation_mm: float
    cloud_cover_pct: float


@dataclass
class FirePerimeter:
    polygon: GeoPolygon
    area_ha: float
    centroid: GeoPoint
    detected_at: str
    confidence: float
    front_depth_m: float = 0.0
    flame_height_m: float = 0.0
    hotspots: list[Hotspot] = field(default_factory=list)


@dataclass
class HourlyPrediction:
    hour_offset: int
    timestamp: str
    temperature_c: float
    wind_speed_kmh: float
    wind_direction_deg: float
    normal_wind_kmh: float
    precipitation_mm: float
    fire_intensity: FireIntensity
    spread_rate_mh: float
    spread_direction_deg: float
    predicted_area_ha: float
    predicted_perimeter: dict
    risk_level: RiskLevel
    extinguishing_probability: float
    flame_height_m: float = 0.0


@dataclass
class FireBehaviorPrediction:
    trend: FireTrend
    confidence: float
    spread_direction_deg: float
    spread_rate_mh: float
    current_area_ha: float
    predicted_area_24h_ha: float
    fire_weather_index: float
    fuel_moisture_pct: float
    fuel_type_id: int = 1
    fuel_model_name: str = ""
    growth_rate_m2_s: float | None = None
    acceleration_m2_s2: float | None = None
    hourly: list[HourlyPrediction] = field(default_factory=list)


@dataclass
class RiskBuffer:
    distance_km: float
    geometry: dict


@dataclass
class CriticalInfrastructure:
    name: str
    category: str
    location: GeoPoint
    distance_km: float
    eta_hours: float
    risk_level: RiskLevel


@dataclass
class SituationalAwareness:
    summary: str
    fire_behavior: str
    weather_summary: str
    warnings: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    infrastructure_at_risk: list[CriticalInfrastructure] = field(default_factory=list)


@dataclass
class MeteoReportMetadata:
    generated_at: str
    model_version: str
    location: GeoPoint
    forecast_hours: int
    data_sources: list[str] = field(default_factory=lambda: ["open-meteo.com"])


@dataclass
class FireDetectionPayload:
    drone_telemetry: DroneTelemetry
    perimeter: GeoPolygon
    area_ha: float
    centroid: GeoPoint
    confidence: float
    fuel_type_id: int = 1
    slope_deg: float = 0.0
    front_depth_m: float = 0.0
    hotspots: list[Hotspot] = field(default_factory=list)
    detected_at: str = ""


@dataclass
class MeteoReport:
    metadata: MeteoReportMetadata
    current_weather: WeatherCurrent
    fire_perimeter: FirePerimeter
    prediction: FireBehaviorPrediction
    situational_awareness: SituationalAwareness
    risk_buffers: list[RiskBuffer] = field(default_factory=list)
    drone_telemetry: DroneTelemetry | None = None

    def to_json(self) -> str:
        return json.dumps(self._to_serializable(), indent=2, ensure_ascii=False)

    def to_dict(self) -> dict:
        return self._to_serializable()

    def _to_serializable(self) -> dict:
        return MeteoReport._walk(self)  # type: ignore[return-value]

    @staticmethod
    def _walk(obj: object) -> object:
        # Walk the dataclass tree directly so `to_geojson()` is honored.
        # asdict() would flatten GeoPolygon → {"coordinates": [...]} and lose
        # the {"type": "Polygon"} discriminator that ground-control's Zod
        # schema requires; same for GeoPoint → [lon, lat].
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "to_geojson"):
            return obj.to_geojson()  # type: ignore[attr-defined]
        if hasattr(obj, "__dataclass_fields__"):
            return {
                f: MeteoReport._walk(getattr(obj, f))
                for f in obj.__dataclass_fields__  # type: ignore[attr-defined]
            }
        if isinstance(obj, (list, tuple)):
            return [MeteoReport._walk(v) for v in obj]
        if isinstance(obj, dict):
            return {k: MeteoReport._walk(v) for k, v in obj.items()}
        return obj
