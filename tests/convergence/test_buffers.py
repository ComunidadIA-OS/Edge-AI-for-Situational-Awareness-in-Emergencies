"""Tests for the risk-buffer ring generator."""
from __future__ import annotations

import math

import pytest

from convergence.buffers import compute_risk_buffers
from convergence.models import GeoPoint


_CENTROID = GeoPoint(lat=41.6488, lon=-0.8891)


def _small_square_around(centroid: GeoPoint, half_side_m: float = 50.0) -> list[list[float]]:
    R = 6378137.0
    cos_lat = math.cos(math.radians(centroid.lat))
    deg_per_m_lat = math.degrees(1.0 / R)
    deg_per_m_lon = math.degrees(1.0 / (R * cos_lat))
    d_lat = half_side_m * deg_per_m_lat
    d_lon = half_side_m * deg_per_m_lon
    return [
        [centroid.lon - d_lon, centroid.lat - d_lat],
        [centroid.lon + d_lon, centroid.lat - d_lat],
        [centroid.lon + d_lon, centroid.lat + d_lat],
        [centroid.lon - d_lon, centroid.lat + d_lat],
        [centroid.lon - d_lon, centroid.lat - d_lat],
    ]


def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6378137.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def test_returns_one_buffer_per_requested_distance():
    coords = _small_square_around(_CENTROID)
    buffers = compute_risk_buffers(_CENTROID, coords, buffer_distances_km=(1.0, 3.0, 5.0))
    assert len(buffers) == 3
    assert [b.distance_km for b in buffers] == [1.0, 3.0, 5.0]


def test_each_buffer_is_a_closed_geojson_polygon():
    coords = _small_square_around(_CENTROID)
    buffers = compute_risk_buffers(_CENTROID, coords)
    for b in buffers:
        assert b.geometry["type"] == "Polygon"
        ring = b.geometry["coordinates"][0]
        assert len(ring) > 3
        assert ring[0] == ring[-1]


def test_buffer_radius_matches_requested_distance_plus_perimeter_extent():
    half_side = 50.0
    coords = _small_square_around(_CENTROID, half_side_m=half_side)
    buffers = compute_risk_buffers(_CENTROID, coords, buffer_distances_km=(1.0,))
    ring = buffers[0].geometry["coordinates"][0]

    distances_m = [
        _haversine_m(_CENTROID.lat, _CENTROID.lon, lat, lon) for lon, lat in ring
    ]
    avg_r = sum(distances_m) / len(distances_m)
    expected_min = 1000.0 + half_side * 0.9
    expected_max = 1000.0 + half_side * math.sqrt(2) * 1.05
    assert expected_min < avg_r < expected_max


def test_buffers_are_concentric_and_strictly_growing():
    coords = _small_square_around(_CENTROID)
    buffers = compute_risk_buffers(_CENTROID, coords, buffer_distances_km=(1.0, 3.0, 5.0))
    radii = []
    for b in buffers:
        ring = b.geometry["coordinates"][0]
        d = _haversine_m(_CENTROID.lat, _CENTROID.lon, ring[0][1], ring[0][0])
        radii.append(d)
    assert radii[0] < radii[1] < radii[2]


def test_empty_perimeter_still_produces_circles_at_requested_distances():
    buffers = compute_risk_buffers(_CENTROID, [], buffer_distances_km=(2.0,))
    assert len(buffers) == 1
    ring = buffers[0].geometry["coordinates"][0]
    r = _haversine_m(_CENTROID.lat, _CENTROID.lon, ring[0][1], ring[0][0])
    assert 1900 < r < 2100


def test_high_latitude_does_not_blow_up_near_pole():
    polar = GeoPoint(lat=85.0, lon=10.0)
    coords = _small_square_around(polar, half_side_m=100.0)
    buffers = compute_risk_buffers(polar, coords, buffer_distances_km=(1.0,))
    ring = buffers[0].geometry["coordinates"][0]
    assert all(-90.0 <= lat <= 90.0 for _, lat in ring)
