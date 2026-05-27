"""Concentric risk-zone polygons around the fire centroid.

The buffers extend a fixed distance beyond the furthest point on the
current fire perimeter, yielding circular evacuation/alert rings the
frontend can paint directly on the map. This is the form fire incident
commanders use for evacuation planning, so the JSON contract stays close
to operational practice.

Uses a local equirectangular projection around the centroid (accurate to
~1% for radii under 10 km at mid latitudes). No external geometry
dependencies.
"""
from __future__ import annotations

import math

from convergence.models import GeoPoint, RiskBuffer


_R_EARTH_M = 6378137.0
_DEFAULT_BUFFERS_KM = (1.0, 3.0, 5.0)
_DEFAULT_POINTS = 64


def compute_risk_buffers(
    centroid: GeoPoint,
    fire_perimeter_coords: list[list[float]],
    buffer_distances_km: tuple[float, ...] = _DEFAULT_BUFFERS_KM,
    points_per_circle: int = _DEFAULT_POINTS,
) -> list[RiskBuffer]:
    """Build concentric risk-zone rings around the fire centroid.

    Args:
        centroid: Fire centroid (lat/lon).
        fire_perimeter_coords: Outer ring of the fire polygon as a list of
            ``[lon, lat]`` pairs (GeoJSON Polygon coordinates[0]).
        buffer_distances_km: Distances beyond the furthest perimeter point
            for each ring. Defaults to (1, 3, 5) km.
        points_per_circle: Vertex count per ring; higher = smoother circle.

    Returns:
        A ``RiskBuffer`` for each requested distance, each carrying a GeoJSON
        ``Polygon`` geometry ready for direct rendering.
    """
    cos_lat = math.cos(math.radians(centroid.lat))
    if cos_lat < 1e-6:
        cos_lat = 1e-6

    max_dist_m = 0.0
    for point in fire_perimeter_coords:
        if len(point) < 2:
            continue
        lon, lat = point[0], point[1]
        x = _R_EARTH_M * math.radians(lon - centroid.lon) * cos_lat
        y = _R_EARTH_M * math.radians(lat - centroid.lat)
        d = math.sqrt(x * x + y * y)
        if d > max_dist_m:
            max_dist_m = d

    buffers: list[RiskBuffer] = []
    for dist_km in buffer_distances_km:
        radius_m = max_dist_m + dist_km * 1000.0
        ring = _circle_ring(centroid, radius_m, points_per_circle, cos_lat)
        buffers.append(RiskBuffer(
            distance_km=float(dist_km),
            geometry={"type": "Polygon", "coordinates": [ring]},
        ))
    return buffers


def _circle_ring(
    centroid: GeoPoint,
    radius_m: float,
    points: int,
    cos_lat: float,
) -> list[list[float]]:
    coords: list[list[float]] = []
    for i in range(points):
        theta = 2.0 * math.pi * i / points
        x = radius_m * math.cos(theta)
        y = radius_m * math.sin(theta)
        lat = centroid.lat + math.degrees(y / _R_EARTH_M)
        lon = centroid.lon + math.degrees(x / (_R_EARTH_M * cos_lat))
        coords.append([round(lon, 6), round(lat, 6)])
    coords.append(coords[0])
    return coords
