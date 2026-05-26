from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone

import numpy as np

from convergence.models import (
    FireBehaviorPrediction,
    FireIntensity,
    FirePerimeter,
    FireTrend,
    GeoPoint,
    GeoPolygon,
    Hotspot,
    HourlyPrediction,
    RiskLevel,
    WeatherCurrent,
)
from convergence.fuels import FuelModel, get_fuel_model_or_default

logger = logging.getLogger(__name__)

_WIND_DRIVEN_WEIGHT = 0.70
_TERRAIN_WEIGHT = 0.20
_FUEL_WEIGHT = 0.10

_BASE_SPREAD_RATE_MH = 30.0
_WIND_SPEED_FACTOR = 0.06
_HUMIDITY_REDUCTION = 0.008
_TEMPERATURE_BOOST = 0.003

_EXTINGUISHING_PRECIP_THRESHOLD = 2.5
_CRITICAL_WIND_SPEED = 50.0
_CRITICAL_HUMIDITY = 20.0
_CRITICAL_TEMPERATURE = 35.0

_SPREAD_EXPANSION_FACTOR = 1.25

_SIGMA = 5.670367e-8
_T_FLAME = 1200.0

_MOISTURE_COEFFICIENT = 4.0
_BETA_OPT = 0.0025
_BASELINE_CALIBRATION = 0.10
_WIND_TILT_COEFF = 0.08
_TILT_AMPLIFIER = 6.0
_FLAME_DEPTH_FACTOR = 1.5
_MAX_TILT_DEG = 80.0


def calculate_fire_weather_index(
    temperature_c: float,
    humidity_pct: float,
    wind_speed_kmh: float,
    precipitation_mm: float,
) -> float:
    """Calculate a simplified Fire Weather Index (0-100 scale).

    Weighted model combining temperature, humidity, wind, and precipitation.
    Calibrated to produce values matching operational fire danger ratings.

    Args:
        temperature_c: Air temperature in Celsius.
        humidity_pct: Relative humidity percentage (0-100).
        wind_speed_kmh: Wind speed at 10m in km/h.
        precipitation_mm: Precipitation in last hour in mm.

    Returns:
        Fire Weather Index value between 0 and 100.
    """
    temp_score = max(0.0, min(40.0, (temperature_c / 40.0) * 35.0))

    humidity_score = max(0.0, ((100.0 - humidity_pct) / 100.0) * 30.0)

    wind_score = max(0.0, min(35.0, (wind_speed_kmh / 60.0) * 35.0))

    precip_penalty = min(25.0, precipitation_mm * 8.0)

    fwi = temp_score + humidity_score + wind_score - precip_penalty
    fwi = max(0.0, min(100.0, fwi * 1.05))

    return round(fwi, 1)


def calculate_fuel_moisture(
    temperature_c: float,
    humidity_pct: float,
    precipitation_mm: float,
    hours_since_rain: float = 0,
) -> float:
    """Estimate fine fuel moisture content as a percentage.

    Args:
        temperature_c: Air temperature in Celsius.
        humidity_pct: Relative humidity percentage.
        precipitation_mm: Precipitation amount in mm.
        hours_since_rain: Hours since last significant rainfall.

    Returns:
        Estimated fuel moisture percentage (0-100).
    """
    equilibrium_moisture = 0.942 * (humidity_pct ** 0.679) + 0.000499 * math.exp(0.1 * humidity_pct) + 0.18 * (21.1 - temperature_c) * (1 - math.exp(-0.115 * humidity_pct))

    if precipitation_mm > 0.5:
        saturation = min(1.0, precipitation_mm / 10.0)
        return max(1.0, equilibrium_moisture + (35.0 - equilibrium_moisture) * saturation)

    drying = 1.0 - math.exp(-0.3 * max(hours_since_rain, 0))
    return max(1.0, equilibrium_moisture - drying * 5.0)


def predict_spread_rate_mh(
    wind_speed_kmh: float,
    humidity_pct: float,
    temperature_c: float,
    fuel_moisture_pct: float,
    slope_deg: float = 0,
) -> float:
    """Predict fire spread rate in meters per hour.

    Simplified Rothermel-based model combining wind, humidity,
    temperature, fuel moisture, and terrain slope.

    Args:
        wind_speed_kmh: Wind speed in km/h at 10m.
        humidity_pct: Relative humidity percentage.
        temperature_c: Air temperature in Celsius.
        fuel_moisture_pct: Fuel moisture percentage.
        slope_deg: Terrain slope in degrees.

    Returns:
        Estimated spread rate in meters per hour.
    """
    wind_component = _BASE_SPREAD_RATE_MH * (1 + wind_speed_kmh * _WIND_SPEED_FACTOR)
    humidity_factor = 1 - max(0, (100 - humidity_pct) * _HUMIDITY_REDUCTION)
    temperature_factor = 1 + max(0, temperature_c - 20) * _TEMPERATURE_BOOST
    fuel_factor = max(0.1, 1 - fuel_moisture_pct / 100.0)

    slope_factor = 1.0
    if slope_deg > 0:
        slope_factor = 1 + 0.05 * math.tan(math.radians(min(slope_deg, 45)))

    spread_rate = wind_component * humidity_factor * temperature_factor * fuel_factor * slope_factor
    return round(max(0.5, min(spread_rate, 8000.0)), 1)


def calculate_normal_wind(
    wind_speed_kmh: float,
    wind_direction_deg: float,
    segment_normal_deg: float,
) -> float:
    """Project wind speed onto the segment normal vector.

    The Balbi model requires wind perpendicular to the fire front.
    normalWind = wind_speed * cos(angle between wind vector and segment normal)

    Args:
        wind_speed_kmh: Wind speed at 10m in km/h.
        wind_direction_deg: Wind direction in degrees (meteorological convention).
        segment_normal_deg: Direction of the segment normal (perpendicular to front,
                            pointing outward in the direction of spread).

    Returns:
        Normal wind component in km/h (always >= 0 for head fire).
    """
    delta = abs(wind_direction_deg - segment_normal_deg) % 360
    if delta > 180:
        delta = 360 - delta
    cos_factor = math.cos(math.radians(delta))
    normal_wind = wind_speed_kmh * max(0.0, cos_factor)
    return round(normal_wind, 1)


def predict_spread_rate_balbi(
    normal_wind_kmh: float,
    humidity_pct: float,
    temperature_c: float,
    fuel_model: FuelModel,
    slope_deg: float = 0,
) -> float:
    """Predict fire spread rate using the Balbi 2015 physical model.

    Implements the published quadratic form coupling wind and slope through
    a combined flame-tilt angle gamma:

        R0   = (R_00 * chi_0 / (1 + a*Md)) * (Sd/(Sd+Sl))    (base, still air)
        Rt   = R0 * (1 + k_tilt * tan(gamma))
        R    = 0.5 * (Rt + sqrt(Rt^2 + 4*r0*R0/cos(gamma)))
        R_total = R0 + R

    Where gamma = arctan(k_wind * U) + slope_rad couples wind and slope
    geometrically instead of adding them linearly. This reproduces the
    non-linear acceleration observed when wind and slope are aligned.

    Reference: Balbi et al. (2015) "A physical model for wildland fires",
    Fire Safety Journal 71: 51-63.

    Args:
        normal_wind_kmh: Wind component normal to fire front in km/h.
        humidity_pct: Relative humidity percentage (0-100).
        temperature_c: Ambient air temperature in Celsius.
        fuel_model: FuelModel with physical properties.
        slope_deg: Terrain slope in degrees.

    Returns:
        Spread rate in meters per hour.
    """
    U = max(normal_wind_kmh, 0.0) / 3.6
    T_amb = temperature_c + 273.15
    slope_rad = math.radians(min(max(slope_deg, 0.0), 60.0))

    Md = max(estimate_fuel_moisture_from_weather(temperature_c, humidity_pct), 1.0) / 100.0

    sigma_d = max(fuel_model.sigmad, 0.05)
    sigma_l = max(fuel_model.sigmal, 0.0)
    S_d = max(fuel_model.sd, 1.0)
    S_l = max(fuel_model.sl, 0.0)
    e_depth = max(fuel_model.e, 0.01)
    rho_p = max(fuel_model.rhod, 100.0)
    Cp = fuel_model.cp

    rho_b = sigma_d / e_depth
    beta = rho_b / rho_p

    optical_depth = S_d * e_depth * beta
    chi_0 = (1.0 - math.exp(-min(optical_depth, 10.0))) * min((beta / _BETA_OPT) ** 0.5, 2.0)

    delta_T = max(fuel_model.ti - T_amb, 50.0)
    R_00_raw = (_SIGMA * (_T_FLAME ** 4)) / (rho_b * Cp * delta_T)

    moisture_term = 1.0 / (1.0 + _MOISTURE_COEFFICIENT * Md)
    dead_weight = S_d / max(S_d + S_l, 1.0)

    R_0 = R_00_raw * chi_0 * moisture_term * dead_weight * _BASELINE_CALIBRATION
    R_0 = max(R_0, 1e-7)

    alpha_wind = math.atan(_WIND_TILT_COEFF * U)
    gamma = min(alpha_wind + slope_rad, math.radians(_MAX_TILT_DEG))
    cos_gamma = max(math.cos(gamma), 0.05)
    tan_gamma = math.tan(gamma)

    R_t = R_0 * (1.0 + _TILT_AMPLIFIER * tan_gamma)
    r_0 = R_0 * _FLAME_DEPTH_FACTOR

    discriminant = R_t * R_t + 4.0 * r_0 * R_0 / cos_gamma
    R_aug = 0.5 * (R_t + math.sqrt(discriminant))

    R_total_ms = R_0 + R_aug

    R_mh = R_total_ms * 3600.0
    return round(max(0.1, min(R_mh, 8000.0)), 1)


def calculate_flame_height_balbi(
    spread_rate_mh: float,
    fuel_model: FuelModel,
) -> float:
    """Estimate flame height using Byram's fireline intensity formula.

    I = H * w * R
    h_flame = 0.0775 * I^(2/3)

    Where:
        I = fireline intensity (kW/m)
        H = heat of combustion (kJ/kg)
        w = fuel consumed per unit area (kg/mÂ²)
        R = rate of spread (m/s)

    Args:
        spread_rate_mh: Spread rate in meters per hour.
        fuel_model: FuelModel with DeltaH and fuel loads.

    Returns:
        Flame height in meters.
    """
    H_kj_kg = fuel_model.delta_h / 1000.0
    w_kg_m2 = fuel_model.sigmad + fuel_model.sigmal
    R_ms = spread_rate_mh / 3600.0
    I_kW_m = H_kj_kg * w_kg_m2 * R_ms
    h_flame = 0.0775 * (max(I_kW_m, 0.01) ** (2.0 / 3.0))
    return round(h_flame, 2)


def estimate_fuel_moisture_from_weather(
    temperature_c: float,
    humidity_pct: float,
    precipitation_mm: float = 0,
) -> float:
    """Estimate fine fuel moisture content from weather variables.

    Used when the drone lacks an IR sensor for direct Md measurement.
    Based on equilibrium moisture content (EMC) model.

    Args:
        temperature_c: Air temperature in Celsius.
        humidity_pct: Relative humidity percentage.
        precipitation_mm: Precipitation in mm.

    Returns:
        Estimated fuel moisture percentage (0-100).
    """
    emc = (
        0.942 * (humidity_pct ** 0.679)
        + 0.000499 * math.exp(0.1 * humidity_pct)
        + 0.18 * (21.1 - temperature_c) * (1.0 - math.exp(-0.115 * humidity_pct))
    )
    if precipitation_mm > 0.5:
        saturation = min(1.0, precipitation_mm / 10.0)
        return max(1.0, emc + (35.0 - emc) * saturation)
    return max(1.0, emc - 5.0)


def classify_fire_intensity(
    spread_rate_mh: float,
    fwi: float,
    temperature_c: float,
) -> FireIntensity:
    """Classify fire intensity level.

    Args:
        spread_rate_mh: Spread rate in meters per hour.
        fwi: Fire Weather Index (0-100).
        temperature_c: Air temperature in Celsius.

    Returns:
        Fire intensity classification.
    """
    if fwi >= 70 or spread_rate_mh > 300 or temperature_c > 40:
        return "extreme"
    if fwi >= 50 or spread_rate_mh > 120 or temperature_c > 35:
        return "high"
    if fwi >= 30 or spread_rate_mh > 30:
        return "moderate"
    return "low"


def classify_risk_level(
    fwi: float,
    spread_rate_mh: float,
    extinguishing_prob: float,
) -> RiskLevel:
    """Determine risk level for decision support.

    Args:
        fwi: Fire Weather Index.
        spread_rate_mh: Spread rate in m/h.
        extinguishing_prob: Probability of natural extinguishing.

    Returns:
        Risk classification level.
    """
    if extinguishing_prob > 0.7:
        return "low"
    if fwi >= 70 or spread_rate_mh > 250:
        return "extreme"
    if fwi >= 50 or spread_rate_mh > 100:
        return "high"
    if fwi >= 30:
        return "moderate"
    return "low"


def predict_fire_trend(
    current_spread_rate: float,
    future_spread_rates: list[float],
    precipitation_mm: float,
    humidity_pct: float,
) -> FireTrend:
    """Determine overall fire behavior trend over the forecast period.

    Args:
        current_spread_rate: Current estimated spread rate in m/h.
        future_spread_rates: Projected spread rates for each forecast hour.
        precipitation_mm: Current precipitation in mm.
        humidity_pct: Current relative humidity.

    Returns:
        Fire trend classification.
    """
    if precipitation_mm >= _EXTINGUISHING_PRECIP_THRESHOLD and humidity_pct > 80:
        return "extinguishing"

    if not future_spread_rates:
        return "stable"

    avg_future = sum(future_spread_rates) / len(future_spread_rates)
    ratio = avg_future / max(current_spread_rate, 0.001)

    if ratio > 1.3:
        return "growing"
    if ratio > 0.7:
        return "stable"
    if ratio > 0.3:
        return "shrinking"
    return "extinguishing"


def predict_perimeter_expansion(
    current_perimeter: GeoPolygon,
    centroid: GeoPoint,
    spread_direction_deg: float,
    spread_rate_mh: float,
    hours: int,
) -> dict:
    """Generate a predicted fire perimeter after N hours of spread.

    Uses a simplified directional buffer: expands the current polygon
    in the spread direction proportionally to spread rate and time.

    Args:
        current_perimeter: Current fire perimeter as GeoJSON polygon.
        centroid: Fire centroid coordinates.
        spread_direction_deg: Direction of spread in degrees from north.
        spread_rate_mh: Spread rate in meters per hour.
        hours: Number of hours to project.

    Returns:
        Predicted perimeter as a GeoJSON geometry dict.
    """
    distance_m = spread_rate_mh * hours
    distance_deg = distance_m / 111_320.0

    direction_rad = math.radians(spread_direction_deg)
    dx = distance_deg * math.sin(direction_rad) * _SPREAD_EXPANSION_FACTOR
    dy = distance_deg * math.cos(direction_rad) * _SPREAD_EXPANSION_FACTOR

    lateral_spread = distance_deg * 0.3

    new_centroid_lat = centroid.lat + dy
    new_centroid_lon = centroid.lon + dx

    angle_a = spread_direction_deg - 30
    angle_b = spread_direction_deg + 30

    a1_rad = math.radians(angle_a)
    a2_rad = math.radians(angle_b)

    vertices: list[list[float]] = []
    steps = 8
    for i in range(steps + 1):
        frac = i / steps
        angle = a1_rad + (a2_rad - a1_rad) * frac
        r = distance_deg * (1 + 0.3 * math.sin(math.pi * frac))
        v_lat = centroid.lat + r * math.cos(angle) + dy * 0.5
        v_lon = centroid.lon + r * math.sin(angle) + dx * 0.5
        vertices.append([v_lon, v_lat])

    vertices.append(vertices[0])

    return {"type": "Polygon", "coordinates": [vertices]}


def run_prediction(
    current_weather: WeatherCurrent,
    fire_perimeter: FirePerimeter,
    hourly_weather: list[dict],
    slope_deg: float = 0,
    fuel_type_id: int = 1,
) -> FireBehaviorPrediction:
    """Execute full fire behavior prediction pipeline using Balbi 2015.

    Args:
        current_weather: Current weather conditions at the fire location.
        fire_perimeter: Detected fire perimeter with area and centroid.
        hourly_weather: List of hourly weather forecast dictionaries.
        slope_deg: Average terrain slope in degrees at the fire location.
        fuel_type_id: Scott/Burgan fuel model ID (1-13).

    Returns:
        Complete fire behavior prediction with hourly breakdown.
    """
    fuel_model = get_fuel_model_or_default(fuel_type_id)

    fwi = calculate_fire_weather_index(
        current_weather.temperature_c,
        current_weather.relative_humidity_pct,
        current_weather.wind_speed_kmh,
        current_weather.precipitation_mm,
    )

    fuel_moisture = estimate_fuel_moisture_from_weather(
        current_weather.temperature_c,
        current_weather.relative_humidity_pct,
        current_weather.precipitation_mm,
    )

    spread_direction = current_weather.wind_direction_deg

    normal_wind_current = calculate_normal_wind(
        current_weather.wind_speed_kmh,
        current_weather.wind_direction_deg,
        spread_direction,
    )

    current_spread_rate = predict_spread_rate_balbi(
        normal_wind_current,
        current_weather.relative_humidity_pct,
        current_weather.temperature_c,
        fuel_model,
        slope_deg,
    )

    current_flame_height = calculate_flame_height_balbi(current_spread_rate, fuel_model)

    hourly_predictions: list[HourlyPrediction] = []
    future_spread_rates: list[float] = []

    for i, hw in enumerate(hourly_weather):
        hour_offset = i + 1

        hw_fwi = calculate_fire_weather_index(
            hw["temperature_c"],
            hw["relative_humidity_pct"],
            hw["wind_speed_kmh"],
            hw["precipitation_mm"],
        )

        hw_direction = hw["wind_direction_deg"]
        if hw_direction == 0 and hw["wind_speed_kmh"] < 1:
            hw_direction = current_weather.wind_direction_deg

        hw_normal_wind = calculate_normal_wind(
            hw["wind_speed_kmh"],
            hw_direction,
            hw_direction,
        )

        hw_spread_rate = predict_spread_rate_balbi(
            hw_normal_wind,
            hw["relative_humidity_pct"],
            hw["temperature_c"],
            fuel_model,
            slope_deg,
        )

        hw_flame_height = calculate_flame_height_balbi(hw_spread_rate, fuel_model)

        future_spread_rates.append(hw_spread_rate)

        extinguishing_prob = _calculate_extinguishing_probability(
            hw["precipitation_mm"],
            hw["relative_humidity_pct"],
        )

        intensity = classify_fire_intensity(hw_spread_rate, hw_fwi, hw["temperature_c"])
        risk = classify_risk_level(hw_fwi, hw_spread_rate, extinguishing_prob)

        cumulative_area = fire_perimeter.area_ha * (1 + hw_spread_rate * hour_offset / max(current_spread_rate, 0.001) * 0.02)

        predicted_polygon = predict_perimeter_expansion(
            fire_perimeter.polygon,
            fire_perimeter.centroid,
            hw_direction,
            hw_spread_rate,
            hour_offset,
        )

        hourly_predictions.append(HourlyPrediction(
            hour_offset=hour_offset,
            timestamp=hw["timestamp"],
            temperature_c=hw["temperature_c"],
            wind_speed_kmh=hw["wind_speed_kmh"],
            wind_direction_deg=hw_direction,
            normal_wind_kmh=hw_normal_wind,
            precipitation_mm=hw["precipitation_mm"],
            fire_intensity=intensity,
            spread_rate_mh=hw_spread_rate,
            spread_direction_deg=hw_direction,
            predicted_area_ha=round(cumulative_area, 2),
            predicted_perimeter=predicted_polygon,
            risk_level=risk,
            extinguishing_probability=round(extinguishing_prob, 3),
            flame_height_m=hw_flame_height,
        ))

    trend = predict_fire_trend(
        current_spread_rate,
        future_spread_rates,
        current_weather.precipitation_mm,
        current_weather.relative_humidity_pct,
    )

    avg_future_rate = sum(future_spread_rates) / max(len(future_spread_rates), 1)
    predicted_24h_area = fire_perimeter.area_ha * (1 + avg_future_rate * 24 / max(current_spread_rate, 0.001) * 0.02)

    trend_confidence = _calculate_trend_confidence(future_spread_rates)

    return FireBehaviorPrediction(
        trend=trend,
        confidence=round(trend_confidence, 3),
        spread_direction_deg=round(spread_direction, 1),
        spread_rate_mh=current_spread_rate,
        current_area_ha=fire_perimeter.area_ha,
        predicted_area_24h_ha=round(predicted_24h_area, 2),
        fire_weather_index=fwi,
        fuel_moisture_pct=round(fuel_moisture, 1),
        fuel_type_id=fuel_type_id,
        fuel_model_name=fuel_model.name,
        hourly=hourly_predictions,
    )


def _calculate_extinguishing_probability(
    precipitation_mm: float,
    humidity_pct: float,
) -> float:
    if precipitation_mm >= _EXTINGUISHING_PRECIP_THRESHOLD and humidity_pct > 80:
        return min(1.0, 0.5 + precipitation_mm * 0.15 + (humidity_pct - 80) * 0.02)
    if precipitation_mm >= 1.0:
        return min(0.9, precipitation_mm * 0.3 + humidity_pct * 0.004)
    if humidity_pct > 70:
        return min(0.5, (humidity_pct - 70) * 0.02)
    return max(0.0, (30 - humidity_pct) * 0.005)


def _calculate_trend_confidence(spread_rates: list[float]) -> float:
    if len(spread_rates) < 2:
        return 0.5
    increases = sum(1 for i in range(1, len(spread_rates)) if spread_rates[i] > spread_rates[i - 1])
    total_changes = len(spread_rates) - 1
    directional_ratio = max(increases, total_changes - increases) / total_changes
    arr = np.array(spread_rates, dtype=np.float64)
    cv = float(np.std(arr) / (np.mean(arr) + 0.001))
    signal = 1.0 - min(cv * 0.4, 0.6)
    return round(max(0.25, min(0.95, directional_ratio * 0.6 + signal * 0.4)), 3)
