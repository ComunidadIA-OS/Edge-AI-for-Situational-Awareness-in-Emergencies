from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from convergence.buffers import compute_risk_buffers
from convergence.client import fetch_forecast, parse_current_weather, parse_hourly_forecast
from convergence.forecast import (
    calculate_fire_weather_index,
    calculate_fuel_moisture,
    classify_fire_intensity,
    classify_risk_level,
    predict_fire_trend,
    predict_spread_rate_mh,
    run_prediction,
)
from convergence.history import ReportHistory
from convergence.models import (
    CriticalInfrastructure,
    DroneTelemetry,
    FireDetectionPayload,
    FirePerimeter,
    GeoPoint,
    Hotspot,
    MeteoReport,
    MeteoReportMetadata,
    RiskBuffer,
    SituationalAwareness,
    WeatherCurrent,
)
from convergence.fuels import get_fuel_model_or_default

logger = logging.getLogger(__name__)

_MODEL_VERSION = "2.0.0"


def generate_situational_awareness(
    current_weather: WeatherCurrent,
    prediction: Any,
    fire_perimeter: FirePerimeter,
    infrastructure: list[CriticalInfrastructure] | None = None,
) -> SituationalAwareness:
    """Generate a human-readable situational awareness summary.

    Args:
        current_weather: Current weather conditions.
        prediction: Fire behavior prediction result.
        fire_perimeter: Current fire perimeter data.
        infrastructure: Optional list of critical infrastructure at risk.

    Returns:
        SituationalAwareness object with summary, warnings, and actions.
    """
    trend_text = {
        "growing": "en expansion activa",
        "stable": "estable, sin cambios significativos",
        "shrinking": "en disminucion",
        "extinguishing": "extinguiendose naturalmente",
    }.get(prediction.trend, "indeterminado")

    intensity_text = {
        "extreme": "extrema",
        "high": "alta",
        "moderate": "moderada",
        "low": "baja",
    }

    fwi = prediction.fire_weather_index
    wind_dir = current_weather.wind_direction_deg
    wind_dir_cardinal = _degrees_to_cardinal(wind_dir)

    summary = (
        f"Incendio de {fire_perimeter.area_ha:.1f} ha {trend_text}. "
        f"Indice meteorologico de fuego: {fwi:.0f}/100. "
        f"Viento: {current_weather.wind_speed_kmh:.0f} km/h del {wind_dir_cardinal}. "
        f"Humedad: {current_weather.relative_humidity_pct:.0f}%. "
        f"Velocidad de propagacion estimada: {prediction.spread_rate_mh:.0f} m/h."
    )

    fire_behavior = (
        f"El fuego se propaga hacia el {wind_dir_cardinal} a {prediction.spread_rate_mh:.0f} m/h. "
        f"Area proyectada en 24h: {prediction.predicted_area_24h_ha:.0f} ha. "
        f"Confianza del modelo: {prediction.confidence * 100:.0f}%."
    )

    weather_summary = (
        f"Temperatura: {current_weather.temperature_c:.1f}Â°C. "
        f"Humedad relativa: {current_weather.relative_humidity_pct:.0f}%. "
        f"Precipitacion: {current_weather.precipitation_mm:.1f} mm. "
        f"Rafagas: {current_weather.wind_gusts_kmh:.0f} km/h."
    )

    warnings: list[str] = []

    if fwi >= 70:
        warnings.append("CRITICO: Indice meteorologico de fuego extremo (>70). Condiciones explosivas posibles.")
    elif fwi >= 50:
        warnings.append("ALERTA: Indice meteorologico de fuego alto (>50). Alta probabilidad de propagacion rapida.")

    if current_weather.wind_gusts_kmh > 50:
        warnings.append(f"VIENTO PELIGROSO: Rafagas de {current_weather.wind_gusts_kmh:.0f} km/h. Comportamiento erratico del fuego posible.")
    elif current_weather.wind_speed_kmh > 40:
        warnings.append(f"VIENTO FUERTE: {current_weather.wind_speed_kmh:.0f} km/h sostenidos. Propagacion acelerada.")

    if current_weather.relative_humidity_pct < 20:
        warnings.append("HUMEDAD CRITICA: Menos de 20% de humedad relativa. Combustible extremadamente seco.")

    if prediction.trend == "growing" and prediction.spread_rate_mh > 100:
        warnings.append("EXPANSION RAPIDA: El perimetro del incendio crece a mas de 100 m/h. Evacuar zonas en la direccion del viento.")

    for h in prediction.hourly:
        if h.risk_level == "extreme":
            warnings.append(f"HORA +{h.hour_offset}: Riesgo extremo. Velocidad de propagacion: {h.spread_rate_mh:.0f} m/h.")

    actions: list[str] = []

    if prediction.trend == "growing":
        actions.append(f"DESPLEGAR recursos en el flanco {_opposite_cardinal(wind_dir_cardinal)} para contener el avance.")
        actions.append("ESTABLECER linea de control a favor del viento a al menos 500m del perimetro actual.")
    elif prediction.trend == "shrinking":
        actions.append("REFORZAR linea de contencion actual. El fuego esta cediendo.")
        actions.append("PREPARAR equipos para liquidacion de puntos calientes.")
    elif prediction.trend == "stable":
        actions.append("MANTENER posicion defensiva. Monitorear cambios de viento.")
        actions.append("PREPARAR plan de evacuacion preventiva en radio de 2 km.")
    elif prediction.trend == "extinguishing":
        actions.append("INICIAR fase de liquidacion. El fuego se extingue naturalmente.")
        actions.append("PATRULLAR perimetro para detectar reigniciones.")

    if current_weather.relative_humidity_pct < 25:
        actions.append("HUMEDECER combustible alrededor del perimetro para reducir riesgo de saltos.")

    if current_weather.wind_gusts_kmh > 40:
        actions.append("RETIRAR personal de zonas de proyeccion de pavesas. Riesgo de focos secundarios.")

    infra = infrastructure or []

    return SituationalAwareness(
        summary=summary,
        fire_behavior=fire_behavior,
        weather_summary=weather_summary,
        warnings=warnings,
        recommended_actions=actions,
        infrastructure_at_risk=infra,
    )


def run_meteo_analysis(
    lat: float,
    lon: float,
    fire_perimeter: FirePerimeter,
    forecast_hours: int = 24,
    slope_deg: float = 0,
    fuel_type_id: int = 1,
    infrastructure: list[CriticalInfrastructure] | None = None,
    drone_telemetry: DroneTelemetry | None = None,
    history: ReportHistory | None = None,
    risk_buffer_distances_km: tuple[float, ...] = (1.0, 3.0, 5.0),
) -> MeteoReport:
    """Execute the complete meteorological fire analysis pipeline.

    Fetches weather data from Open-Meteo, runs the Balbi 2015 fire behavior
    prediction, computes evolution derivatives (growth rate, acceleration)
    when ``history`` is provided, and builds concentric risk-zone rings
    around the fire. Returns a MeteoReport ready for JSON serialization.

    Args:
        lat: Fire location latitude.
        lon: Fire location longitude.
        fire_perimeter: Current fire perimeter data from AI detection.
        forecast_hours: Number of hours to forecast (1-240).
        slope_deg: Average terrain slope at fire location.
        fuel_type_id: Scott/Burgan fuel model ID (1-13).
        infrastructure: Optional list of critical infrastructure to assess risk.
        drone_telemetry: Optional drone telemetry for the report.
        history: Optional ReportHistory; if given, the current area is recorded
            and dA/dt and d2A/dt2 are exposed on the prediction.
        risk_buffer_distances_km: Concentric ring distances (km) beyond the
            fire perimeter. Defaults to (1, 3, 5).

    Returns:
        Complete MeteoReport with weather, prediction, situational awareness,
        and risk buffers.
    """
    logger.info("Starting meteo analysis: lat=%.4f lon=%.4f hours=%d fuel=%d", lat, lon, forecast_hours, fuel_type_id)

    raw_data = fetch_forecast(lat, lon, forecast_hours)

    current_weather_dict = parse_current_weather(raw_data)
    current_weather = WeatherCurrent(**current_weather_dict)

    hourly_dicts = parse_hourly_forecast(raw_data, limit=forecast_hours)

    prediction = run_prediction(
        current_weather,
        fire_perimeter,
        hourly_dicts,
        slope_deg,
        fuel_type_id,
    )

    if history is not None:
        history.record(fire_perimeter.area_ha)
        growth, accel = history.derivatives()
        prediction.growth_rate_m2_s = round(growth, 3) if growth is not None else None
        prediction.acceleration_m2_s2 = round(accel, 4) if accel is not None else None

    if fire_perimeter.flame_height_m == 0 and prediction.hourly:
        fire_perimeter.flame_height_m = prediction.hourly[0].flame_height_m

    awareness = generate_situational_awareness(
        current_weather,
        prediction,
        fire_perimeter,
        infrastructure,
    )

    perimeter_coords: list[list[float]] = []
    if fire_perimeter.polygon and fire_perimeter.polygon.coordinates:
        perimeter_coords = fire_perimeter.polygon.coordinates[0]
    risk_buffers: list[RiskBuffer] = []
    if perimeter_coords:
        risk_buffers = compute_risk_buffers(
            fire_perimeter.centroid,
            perimeter_coords,
            risk_buffer_distances_km,
        )

    metadata = MeteoReportMetadata(
        generated_at=datetime.now(timezone.utc).isoformat(),
        model_version=_MODEL_VERSION,
        location=GeoPoint(lat=lat, lon=lon),
        forecast_hours=forecast_hours,
        data_sources=["open-meteo.com"],
    )

    report = MeteoReport(
        metadata=metadata,
        current_weather=current_weather,
        fire_perimeter=fire_perimeter,
        prediction=prediction,
        situational_awareness=awareness,
        risk_buffers=risk_buffers,
        drone_telemetry=drone_telemetry,
    )

    logger.info("Meteo analysis complete. FWI=%.1f trend=%s confidence=%.2f fuel=%s",
                prediction.fire_weather_index, prediction.trend, prediction.confidence, prediction.fuel_model_name)

    return report


def run_from_detection_payload(
    payload: FireDetectionPayload,
    forecast_hours: int = 24,
    infrastructure: list[CriticalInfrastructure] | None = None,
    history: ReportHistory | None = None,
) -> MeteoReport:
    """Execute meteo analysis from a drone FireDetectionPayload.

    Converts the drone's detection payload into the internal representation
    and runs the full prediction pipeline.

    Args:
        payload: FireDetectionPayload from the drone.
        forecast_hours: Number of hours to forecast.
        infrastructure: Optional critical infrastructure list.

    Returns:
        Complete MeteoReport.
    """
    perimeter = FirePerimeter(
        polygon=payload.perimeter,
        area_ha=payload.area_ha,
        centroid=payload.centroid,
        detected_at=payload.detected_at or datetime.now(timezone.utc).isoformat(),
        confidence=payload.confidence,
        front_depth_m=payload.front_depth_m,
        hotspots=payload.hotspots,
    )

    return run_meteo_analysis(
        lat=payload.centroid.lat,
        lon=payload.centroid.lon,
        fire_perimeter=perimeter,
        forecast_hours=forecast_hours,
        slope_deg=payload.slope_deg,
        fuel_type_id=payload.fuel_type_id,
        infrastructure=infrastructure,
        drone_telemetry=payload.drone_telemetry,
        history=history,
    )


def _degrees_to_cardinal(degrees: float) -> str:
    """Convert wind direction in degrees to cardinal direction."""
    directions = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
    ]
    index = round(degrees / 22.5) % 16
    return directions[index]


def _opposite_cardinal(cardinal: str) -> str:
    """Get the opposite cardinal direction."""
    opposites = {
        "N": "S", "NNE": "SSW", "NE": "SW", "ENE": "WSW",
        "E": "W", "ESE": "WNW", "SE": "NW", "SSE": "NNW",
        "S": "N", "SSW": "NNE", "SW": "NE", "WSW": "ENE",
        "W": "E", "WNW": "ESE", "NW": "SE", "NNW": "SSE",
    }
    return opposites.get(cardinal, cardinal)
