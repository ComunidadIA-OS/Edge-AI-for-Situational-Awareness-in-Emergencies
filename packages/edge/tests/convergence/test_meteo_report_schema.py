"""Regression tests for MeteoReport.to_dict() output shape.

The ground-control Zod schema (branch v0.1-GroundControl, src/schemas/
meteo-report.schema.ts) requires very specific GeoJSON / coordinate shapes.
A prior implementation used `dataclasses.asdict()` which flattened
GeoPolygon → {"coordinates": [...]} (no "type" discriminator) and
GeoPoint → {"lat": ..., "lon": ...} (a dict, not a [lon, lat] list).
Both shapes were silently rejected by the dashboard. These tests pin the
expected serialised shape so the regression cannot return.
"""
from convergence.models import (
    FireBehaviorPrediction,
    FirePerimeter,
    GeoPoint,
    GeoPolygon,
    MeteoReport,
    MeteoReportMetadata,
    SituationalAwareness,
    WeatherCurrent,
)


def _build_minimal_report() -> MeteoReport:
    return MeteoReport(
        metadata=MeteoReportMetadata(
            generated_at="2026-05-26T22:30:00Z",
            model_version="1.0",
            location=GeoPoint(lat=41.6837, lon=-0.8881),
            forecast_hours=24,
            data_sources=["test"],
        ),
        current_weather=WeatherCurrent(
            timestamp="2026-05-26T22:30:00Z",
            temperature_c=20.0, relative_humidity_pct=50.0,
            wind_speed_kmh=10.0, wind_direction_deg=0.0, wind_gusts_kmh=15.0,
            precipitation_mm=0.0, cloud_cover_pct=0.0,
            soil_temperature_c=20.0, soil_moisture_pct=20.0,
        ),
        fire_perimeter=FirePerimeter(
            polygon=GeoPolygon(coordinates=[[[1, 2], [3, 4], [5, 6], [1, 2]]]),
            area_ha=1.0,
            centroid=GeoPoint(lat=41.68, lon=-0.88),
            detected_at="2026-05-26T22:30:00Z",
            confidence=0.9,
        ),
        prediction=FireBehaviorPrediction(
            trend="growing", confidence=0.9,
            spread_direction_deg=245.0, spread_rate_mh=60.0,
            current_area_ha=1.0, predicted_area_24h_ha=100.0,
            fire_weather_index=50.0, fuel_moisture_pct=15.0,
        ),
        situational_awareness=SituationalAwareness(
            summary="s", fire_behavior="b", weather_summary="w",
        ),
    )


def test_fire_perimeter_polygon_includes_type_discriminator():
    """Without this, ground control's Zod schema rejects the payload."""
    d = _build_minimal_report().to_dict()
    assert d["fire_perimeter"]["polygon"]["type"] == "Polygon"
    assert d["fire_perimeter"]["polygon"]["coordinates"] == [[[1, 2], [3, 4], [5, 6], [1, 2]]]


def test_fire_perimeter_centroid_is_lon_lat_list():
    """Schema expects [lon, lat], not {lat, lon} dict."""
    d = _build_minimal_report().to_dict()
    centroid = d["fire_perimeter"]["centroid"]
    assert isinstance(centroid, list), f"Expected list, got {type(centroid).__name__}"
    assert len(centroid) == 2
    assert centroid == [-0.88, 41.68]  # [lon, lat]


def test_metadata_location_is_lon_lat_list():
    """Same constraint applies to top-level metadata.location."""
    d = _build_minimal_report().to_dict()
    loc = d["metadata"]["location"]
    assert isinstance(loc, list)
    assert loc == [-0.8881, 41.6837]


def test_to_dict_does_not_import_asdict():
    """asdict() flattens nested dataclasses and breaks to_geojson(). If a
    future refactor reintroduces it, this test catches the regression."""
    import ast
    import convergence.models as m
    tree = ast.parse(open(m.__file__).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "dataclasses":
            imported = [alias.name for alias in node.names]
            assert "asdict" not in imported, (
                f"convergence.models must not import asdict — found in {imported}. "
                "Use _walk() instead so to_geojson() is honored."
            )
