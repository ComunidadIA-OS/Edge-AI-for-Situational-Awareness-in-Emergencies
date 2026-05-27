"""Tests for vision/inference/post_to_api.py."""
from __future__ import annotations

import math
import time
from unittest.mock import MagicMock, patch

import pytest

from vision.inference.post_to_api import (
    DEFAULT_HFOV_DEG,
    DetectionPoster,
    bbox_to_geo_polygon,
    build_payload,
    pixel_to_geo,
)

_LAT = 41.6488
_LON = -0.8891
_ALT = 120.0
_HEADING = 0.0  # nose pointing North
_IMG_W = 640
_IMG_H = 512


class TestPixelToGeo:
    def test_image_centre_maps_to_drone_position(self):
        lat, lon = pixel_to_geo(
            _IMG_W / 2, _IMG_H / 2,
            _IMG_W, _IMG_H,
            _LAT, _LON, _ALT, _HEADING,
        )
        assert abs(lat - _LAT) < 1e-6
        assert abs(lon - _LON) < 1e-6

    def test_heading_zero_right_pixel_is_east(self):
        # Right of centre → positive longitude (East), same latitude
        lat, lon = pixel_to_geo(
            _IMG_W / 2 + 100, _IMG_H / 2,
            _IMG_W, _IMG_H,
            _LAT, _LON, _ALT, drone_heading_deg=0.0,
        )
        assert lon > _LON
        assert abs(lat - _LAT) < 1e-4

    def test_heading_zero_down_pixel_is_south(self):
        # Down in image (positive y) → negative latitude (South)
        lat, lon = pixel_to_geo(
            _IMG_W / 2, _IMG_H / 2 + 100,
            _IMG_W, _IMG_H,
            _LAT, _LON, _ALT, drone_heading_deg=0.0,
        )
        assert lat < _LAT
        assert abs(lon - _LON) < 1e-4

    def test_heading_90_right_pixel_is_south(self):
        # Drone faces East → image right = South
        lat, lon = pixel_to_geo(
            _IMG_W / 2 + 100, _IMG_H / 2,
            _IMG_W, _IMG_H,
            _LAT, _LON, _ALT, drone_heading_deg=90.0,
        )
        assert lat < _LAT
        assert abs(lon - _LON) < 1e-4

    def test_gsd_scale_proportional_to_altitude(self):
        lat1, lon1 = pixel_to_geo(
            _IMG_W / 2 + 100, _IMG_H / 2,
            _IMG_W, _IMG_H, _LAT, _LON, _ALT, _HEADING,
        )
        lat2, lon2 = pixel_to_geo(
            _IMG_W / 2 + 100, _IMG_H / 2,
            _IMG_W, _IMG_H, _LAT, _LON, _ALT * 2, _HEADING,
        )
        delta1 = abs(lon1 - _LON)
        delta2 = abs(lon2 - _LON)
        assert abs(delta2 / delta1 - 2.0) < 0.01


class TestBboxToGeoPolygon:
    def test_returns_closed_ring(self):
        ring, _, _ = bbox_to_geo_polygon(
            100, 100, 300, 300,
            _IMG_W, _IMG_H, _LAT, _LON, _ALT, _HEADING,
        )
        assert ring[0] == ring[-1], "Ring must be closed"
        assert len(ring) == 5

    def test_area_increases_with_bbox_size(self):
        _, _, area_small = bbox_to_geo_polygon(
            280, 220, 360, 292, _IMG_W, _IMG_H, _LAT, _LON, _ALT, _HEADING,
        )
        _, _, area_large = bbox_to_geo_polygon(
            100, 100, 540, 412, _IMG_W, _IMG_H, _LAT, _LON, _ALT, _HEADING,
        )
        assert area_large > area_small

    def test_full_frame_bbox_matches_footprint(self):
        _, _, area_ha = bbox_to_geo_polygon(
            0, 0, _IMG_W, _IMG_H,
            _IMG_W, _IMG_H, _LAT, _LON, _ALT, _HEADING,
            hfov_deg=DEFAULT_HFOV_DEG,
        )
        hfov_rad = math.radians(DEFAULT_HFOV_DEG)
        vfov_rad = hfov_rad * (_IMG_H / _IMG_W)
        w_m = 2 * _ALT * math.tan(hfov_rad / 2)
        h_m = 2 * _ALT * math.tan(vfov_rad / 2)
        expected_ha = (w_m * h_m) / 10_000.0
        assert abs(area_ha - expected_ha) / expected_ha < 0.01

    def test_ring_is_geojson_lon_lat_order(self):
        ring, (c_lat, c_lon), _ = bbox_to_geo_polygon(
            200, 150, 440, 362,
            _IMG_W, _IMG_H, _LAT, _LON, _ALT, _HEADING,
        )
        # GeoJSON convention: [lon, lat] — lon is ≈ -0.88, lat ≈ 41.6
        for coord in ring:
            lon_candidate, lat_candidate = coord
            assert -180 <= lon_candidate <= 180
            assert -90 <= lat_candidate <= 90
            # sanity: our test case is in Spain
            assert 40.0 < lat_candidate < 43.0
            assert -2.0 < lon_candidate < 1.0


class TestBuildPayload:
    _det = [{"x_min": 200.0, "y_min": 150.0, "x_max": 440.0, "y_max": 362.0, "confidence": 0.82}]

    def test_schema_top_level_keys(self):
        payload = build_payload(
            self._det, _IMG_W, _IMG_H,
            _LAT, _LON, _ALT, _HEADING,
        )
        for key in ("drone_telemetry", "perimeter", "area_ha", "centroid",
                    "confidence", "fuel_type_id", "slope_deg", "hotspots", "detected_at"):
            assert key in payload, f"Missing key: {key}"

    def test_perimeter_is_valid_polygon(self):
        payload = build_payload(self._det, _IMG_W, _IMG_H, _LAT, _LON, _ALT, _HEADING)
        coords = payload["perimeter"]["coordinates"]
        assert len(coords) == 1
        ring = coords[0]
        assert ring[0] == ring[-1]
        assert len(ring) == 5

    def test_area_ha_positive(self):
        payload = build_payload(self._det, _IMG_W, _IMG_H, _LAT, _LON, _ALT, _HEADING)
        assert payload["area_ha"] > 0

    def test_confidence_is_max_of_detections(self):
        dets = [
            {"x_min": 0, "y_min": 0, "x_max": 100, "y_max": 100, "confidence": 0.5},
            {"x_min": 200, "y_min": 200, "x_max": 300, "y_max": 300, "confidence": 0.9},
        ]
        payload = build_payload(dets, _IMG_W, _IMG_H, _LAT, _LON, _ALT, _HEADING)
        assert payload["confidence"] == 0.9

    def test_union_bbox_when_multiple_detections(self):
        dets = [
            {"x_min": 50.0, "y_min": 50.0, "x_max": 150.0, "y_max": 150.0, "confidence": 0.7},
            {"x_min": 400.0, "y_min": 300.0, "x_max": 550.0, "y_max": 450.0, "confidence": 0.8},
        ]
        payload = build_payload(dets, _IMG_W, _IMG_H, _LAT, _LON, _ALT, _HEADING)
        # union should produce bigger area than either single bbox
        single_payload = build_payload(dets[:1], _IMG_W, _IMG_H, _LAT, _LON, _ALT, _HEADING)
        assert payload["area_ha"] > single_payload["area_ha"]

    def test_raises_on_empty_detections(self):
        with pytest.raises(ValueError):
            build_payload([], _IMG_W, _IMG_H, _LAT, _LON, _ALT, _HEADING)


class TestDetectionPoster:
    def _make_poster(self, min_interval_s: float = 0.0) -> DetectionPoster:
        return DetectionPoster(
            api_url="http://localhost:8000",
            drone_lat=_LAT, drone_lon=_LON,
            drone_alt_m=_ALT, drone_heading_deg=_HEADING,
            min_interval_s=min_interval_s,
        )

    _det = [{"x_min": 200.0, "y_min": 150.0, "x_max": 440.0, "y_max": 362.0, "confidence": 0.82}]

    def test_no_post_on_empty_detections(self):
        poster = self._make_poster()
        with patch("vision.inference.post_to_api.requests") as mock_req:
            poster.post([], _IMG_W, _IMG_H)
            poster._executor.shutdown(wait=True)
            mock_req.post.assert_not_called()

    def test_posts_on_valid_detections(self):
        poster = self._make_poster(min_interval_s=0.0)
        mock_response = MagicMock()
        mock_response.ok = True
        with patch("vision.inference.post_to_api.requests") as mock_req:
            mock_req.post.return_value = mock_response
            poster.post(self._det, _IMG_W, _IMG_H)
            poster._executor.shutdown(wait=True)
            mock_req.post.assert_called_once()
            call_kwargs = mock_req.post.call_args
            assert "detect" in call_kwargs[0][0]

    def test_rate_limit_suppresses_second_call(self):
        poster = self._make_poster(min_interval_s=60.0)
        mock_response = MagicMock()
        mock_response.ok = True
        with patch("vision.inference.post_to_api.requests") as mock_req:
            mock_req.post.return_value = mock_response
            poster.post(self._det, _IMG_W, _IMG_H)
            poster.post(self._det, _IMG_W, _IMG_H)
            poster._executor.shutdown(wait=True)
            assert mock_req.post.call_count == 1

    def test_network_failure_does_not_raise(self):
        poster = self._make_poster(min_interval_s=0.0)
        with patch("vision.inference.post_to_api.requests") as mock_req:
            mock_req.post.side_effect = ConnectionError("refused")
            poster.post(self._det, _IMG_W, _IMG_H)
            poster._executor.shutdown(wait=True)
        # test passes if no exception propagated
