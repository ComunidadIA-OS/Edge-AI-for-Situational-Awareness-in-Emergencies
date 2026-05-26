import numpy as np
import pytest
import cv2

from vision.training.auto_label import (
    apply_absolute_threshold,
    apply_gradient_filter,
    apply_area_shape_filter,
    cluster_fire_regions,
    bboxes_to_yolo,
    _subdivide_cluster,
    _create_bbox_dict,
    process_single_tiff,
)


# ---------------------------------------------------------------------------
# apply_absolute_threshold
# ---------------------------------------------------------------------------

class TestApplyAbsoluteThreshold:
    def test_fire_array_has_active_pixels(self, celsius_fire_array):
        mask = apply_absolute_threshold(celsius_fire_array, 150.0)
        assert mask.dtype == np.uint8
        assert mask.shape == celsius_fire_array.shape
        assert np.sum(mask > 0) > 100

    def test_nofire_array_is_all_zeros(self, celsius_nofire_array):
        mask = apply_absolute_threshold(celsius_nofire_array, 150.0)
        assert np.all(mask == 0)

    def test_nan_pixels_treated_as_false(self, celsius_with_nan):
        mask = apply_absolute_threshold(celsius_with_nan, 150.0)
        nan_rows = slice(0, 20)
        assert np.all(mask[nan_rows, :] == 0)

    def test_active_pixels_in_non_nan_region(self, celsius_with_nan):
        mask = apply_absolute_threshold(celsius_with_nan, 150.0)
        active_region = mask[30:80, 200:280]
        assert np.sum(active_region > 0) > 50

    def test_none_input_raises_valueerror(self):
        with pytest.raises(ValueError, match="must not be None"):
            apply_absolute_threshold(None, 150.0)

    def test_threshold_zero_raises_valueerror(self):
        arr = np.array([[100.0]], dtype=np.float32)
        with pytest.raises(ValueError, match="must be > 0 and <= 1000"):
            apply_absolute_threshold(arr, 0.0)

    def test_threshold_negative_raises_valueerror(self):
        arr = np.array([[100.0]], dtype=np.float32)
        with pytest.raises(ValueError, match="must be > 0 and <= 1000"):
            apply_absolute_threshold(arr, -1.0)

    def test_threshold_above_1000_raises_valueerror(self):
        arr = np.array([[100.0]], dtype=np.float32)
        with pytest.raises(ValueError, match="must be > 0 and <= 1000"):
            apply_absolute_threshold(arr, 1000.1)

    def test_threshold_at_boundary_1000_is_valid(self):
        arr = np.array([[1000.0]], dtype=np.float32)
        mask = apply_absolute_threshold(arr, 1000.0)
        assert mask[0, 0] == 255

    def test_all_nan_array_returns_all_zeros(self):
        arr = np.full((50, 50), np.nan, dtype=np.float32)
        mask = apply_absolute_threshold(arr, 150.0)
        assert np.all(mask == 0)

    def test_multiple_threshold_levels(self, celsius_fire_array):
        mask_low = apply_absolute_threshold(celsius_fire_array, 10.0)
        mask_high = apply_absolute_threshold(celsius_fire_array, 300.0)
        assert np.sum(mask_low > 0) > np.sum(mask_high > 0)


# ---------------------------------------------------------------------------
# apply_gradient_filter
# ---------------------------------------------------------------------------

class TestApplyGradientFilter:
    def test_sharp_edge_preserved(self, celsius_fire_array):
        mask = apply_absolute_threshold(celsius_fire_array, 100.0)
        result = apply_gradient_filter(celsius_fire_array, mask, gradient_threshold=40.0)
        assert result.dtype == np.uint8
        assert result.shape == celsius_fire_array.shape
        assert np.sum(result > 0) > 0

    def test_uniform_region_cleared(self):
        uniform = np.full((100, 100), 200.0, dtype=np.float32)
        mask = np.ones((100, 100), dtype=np.uint8) * 255
        result = apply_gradient_filter(uniform, mask, gradient_threshold=10.0)
        assert np.all(result == 0)

    def test_shape_mismatch_raises_valueerror(self, celsius_fire_array):
        mask = np.ones((100, 100), dtype=np.uint8) * 255
        with pytest.raises(ValueError, match="Shape mismatch"):
            apply_gradient_filter(celsius_fire_array, mask)

    def test_none_thermal_img_raises_valueerror(self):
        mask = np.ones((50, 50), dtype=np.uint8) * 255
        with pytest.raises(ValueError, match="thermal_img must not be None"):
            apply_gradient_filter(None, mask)

    def test_none_mask_raises_valueerror(self):
        img = np.ones((50, 50), dtype=np.float32)
        with pytest.raises(ValueError, match="mask must not be None"):
            apply_gradient_filter(img, None)

    def test_binary_closing_fills_holes(self):
        img = np.full((20, 20), 25.0, dtype=np.float32)
        img[5:15, 5] = 250.0
        img[5:15, 14] = 250.0
        img[5:6, 6:13] = 250.0
        img[14:15, 6:13] = 250.0
        mask = np.zeros((20, 20), dtype=np.uint8)
        mask[5:15, 5:15] = 255
        result = apply_gradient_filter(img, mask, gradient_threshold=30.0)
        assert result.dtype == np.uint8

    def test_nan_in_thermal_img_handled(self, celsius_with_nan):
        mask = np.zeros(celsius_with_nan.shape, dtype=np.uint8)
        mask[30:80, 200:280] = 255
        result = apply_gradient_filter(celsius_with_nan, mask, gradient_threshold=30.0)
        assert result.shape == celsius_with_nan.shape


# ---------------------------------------------------------------------------
# apply_area_shape_filter
# ---------------------------------------------------------------------------

class TestApplyAreaShapeFilter:
    def test_large_contour_kept(self):
        img = np.zeros((200, 200), dtype=np.uint8)
        cv2.circle(img, (100, 100), 30, 255, -1)
        result = apply_area_shape_filter(img, min_area=50)
        assert np.sum(result > 0) > 0

    def test_small_contour_removed(self):
        img = np.zeros((200, 200), dtype=np.uint8)
        cv2.circle(img, (100, 100), 3, 255, -1)
        result = apply_area_shape_filter(img, min_area=50)
        assert np.all(result == 0)

    def test_thin_line_removed(self):
        img = np.zeros((200, 200), dtype=np.uint8)
        cv2.rectangle(img, (10, 95), (190, 105), 255, -1)
        result = apply_area_shape_filter(img, min_area=50, max_aspect_ratio=8.0)
        assert np.all(result == 0)

    def test_compact_region_kept(self):
        img = np.zeros((200, 200), dtype=np.uint8)
        cv2.circle(img, (100, 100), 15, 255, -1)
        result = apply_area_shape_filter(img, min_area=50, max_aspect_ratio=8.0)
        assert np.sum(result > 0) > 0

    def test_empty_mask_returns_all_zeros(self):
        img = np.zeros((100, 100), dtype=np.uint8)
        result = apply_area_shape_filter(img)
        assert np.all(result == 0)

    def test_none_mask_raises_valueerror(self):
        with pytest.raises(ValueError, match="mask must not be None"):
            apply_area_shape_filter(None)

    def test_mixed_contours_filtered_correctly(self):
        img = np.zeros((200, 200), dtype=np.uint8)
        cv2.circle(img, (50, 50), 20, 255, -1)
        cv2.circle(img, (150, 150), 3, 255, -1)
        cv2.rectangle(img, (5, 5), (15, 195), 255, -1)
        result = apply_area_shape_filter(img, min_area=50, max_aspect_ratio=8.0)
        assert np.sum(result > 0) > 0
        contours, _ = cv2.findContours(result, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        assert len(contours) == 1


# ---------------------------------------------------------------------------
# _create_bbox_dict
# ---------------------------------------------------------------------------

class TestCreateBboxDict:
    def test_creates_correct_keys(self):
        points = np.array([[10, 20], [50, 80]], dtype=np.int64)
        bbox = _create_bbox_dict(points, img_w=200, img_h=200)
        assert "x_min" in bbox
        assert "y_min" in bbox
        assert "x_max" in bbox
        assert "y_max" in bbox
        assert "fill_ratio" in bbox
        assert "area_px" in bbox
        assert "n_pixels" in bbox

    def test_padding_applied(self):
        points = np.array([[50, 50], [100, 100]], dtype=np.int64)
        bbox = _create_bbox_dict(points, img_w=300, img_h=300)
        assert bbox["x_min"] < 50
        assert bbox["y_min"] < 50
        assert bbox["x_max"] > 100
        assert bbox["y_max"] > 100

    def test_padding_clamped_to_bounds(self):
        points = np.array([[0, 0], [5, 5]], dtype=np.int64)
        bbox = _create_bbox_dict(points, img_w=100, img_h=100)
        assert bbox["x_min"] >= 0
        assert bbox["y_min"] >= 0


# ---------------------------------------------------------------------------
# _subdivide_cluster
# ---------------------------------------------------------------------------

class TestSubdivideCluster:
    def test_large_cluster_triggers_kmeans_subdivision(self):
        points = np.column_stack([
            np.random.randint(0, 90, 100),
            np.random.randint(0, 90, 100),
        ])
        results = _subdivide_cluster(points, img_w=100, img_h=100, max_ratio=0.1)
        assert len(results) > 0

    def test_small_cluster_not_subdivided(self):
        points = np.column_stack([
            np.random.randint(10, 30, 20),
            np.random.randint(10, 30, 20),
        ])
        results = _subdivide_cluster(points, img_w=200, img_h=200, max_ratio=0.4)
        assert len(results) == 1

    def test_shallow_depth_returns_single_bbox(self):
        points = np.column_stack([
            np.random.randint(0, 100, 50),
            np.random.randint(0, 100, 50),
        ])
        results = _subdivide_cluster(points, img_w=200, img_h=200, max_ratio=0.4, depth=0)
        assert len(results) == 1

    def test_few_points_not_subdivided(self):
        points = np.column_stack([
            np.random.randint(0, 80, 5),
            np.random.randint(0, 80, 5),
        ])
        results = _subdivide_cluster(points, img_w=200, img_h=200, max_ratio=0.4)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# cluster_fire_regions
# ---------------------------------------------------------------------------

class TestClusterFireRegions:
    def test_large_cluster_subdivided_by_kmeans(self):
        mask = np.zeros((100, 100), dtype=np.uint8)
        cv2.rectangle(mask, (10, 10), (90, 90), 255, -1)
        bboxes = cluster_fire_regions(mask, eps=10, min_samples=5, max_bbox_ratio=0.1)
        assert len(bboxes) >= 1

    def test_two_disconnected_clusters(self):
        mask = np.zeros((200, 200), dtype=np.uint8)
        cv2.circle(mask, (40, 40), 15, 255, -1)
        cv2.circle(mask, (160, 160), 15, 255, -1)
        bboxes = cluster_fire_regions(mask, eps=20, min_samples=5)
        assert len(bboxes) == 2

    def test_single_cluster(self):
        mask = np.zeros((200, 200), dtype=np.uint8)
        cv2.circle(mask, (100, 100), 20, 255, -1)
        bboxes = cluster_fire_regions(mask, eps=30, min_samples=5)
        assert len(bboxes) == 1

    def test_empty_mask_returns_empty_list(self):
        mask = np.zeros((100, 100), dtype=np.uint8)
        bboxes = cluster_fire_regions(mask)
        assert bboxes == []

    def test_noise_points_excluded(self):
        mask = np.zeros((200, 200), dtype=np.uint8)
        cv2.circle(mask, (50, 50), 10, 255, -1)
        for x, y in [(180, 10), (185, 15), (10, 190), (15, 195)]:
            mask[y, x] = 255
        bboxes = cluster_fire_regions(mask, eps=20, min_samples=5)
        assert len(bboxes) == 1

    def test_fewer_than_min_samples_returns_empty(self):
        mask = np.zeros((200, 200), dtype=np.uint8)
        mask[50, 50] = 255
        mask[51, 50] = 255
        mask[50, 51] = 255
        bboxes = cluster_fire_regions(mask, eps=30, min_samples=5)
        assert bboxes == []

    def test_output_dict_keys(self):
        mask = np.zeros((200, 200), dtype=np.uint8)
        cv2.circle(mask, (100, 100), 20, 255, -1)
        bboxes = cluster_fire_regions(mask, eps=30, min_samples=5)
        assert len(bboxes) > 0
        bbox = bboxes[0]
        for key in ("x_min", "y_min", "x_max", "y_max", "fill_ratio", "area_px", "n_pixels"):
            assert key in bbox

    def test_fill_ratio_between_zero_and_one(self):
        mask = np.zeros((200, 200), dtype=np.uint8)
        cv2.circle(mask, (100, 100), 20, 255, -1)
        bboxes = cluster_fire_regions(mask, eps=30, min_samples=5)
        for bbox in bboxes:
            assert 0.0 <= bbox["fill_ratio"] <= 1.0

    def test_none_mask_raises_valueerror(self):
        with pytest.raises(ValueError, match="mask must not be None"):
            cluster_fire_regions(None)

    def test_img_dims_derived_from_mask(self):
        mask = np.zeros((150, 250), dtype=np.uint8)
        cv2.circle(mask, (125, 75), 20, 255, -1)
        bboxes = cluster_fire_regions(mask, eps=30, min_samples=5)
        for bbox in bboxes:
            assert 0 <= bbox["x_min"] < 250
            assert 0 <= bbox["y_min"] < 150

    def test_explicit_img_dims_override(self):
        mask = np.zeros((150, 250), dtype=np.uint8)
        cv2.circle(mask, (125, 75), 20, 255, -1)
        bboxes = cluster_fire_regions(mask, eps=30, min_samples=5, img_w=500, img_h=300)
        for bbox in bboxes:
            assert bbox["x_max"] < 500
            assert bbox["y_max"] < 300


# ---------------------------------------------------------------------------
# bboxes_to_yolo
# ---------------------------------------------------------------------------

class TestBboxesToYolo:
    def test_valid_bboxes_produce_correct_format(self, sample_bboxes):
        output = bboxes_to_yolo(sample_bboxes, img_w=640, img_h=480)
        lines = output.strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            parts = line.split()
            assert len(parts) == 5
            assert parts[0] == "0"
            for val in parts[1:]:
                assert 0.0 <= float(val) <= 1.0

    def test_six_decimal_places(self, single_bbox):
        output = bboxes_to_yolo(single_bbox, img_w=640, img_h=480)
        for part in output.split()[1:]:
            decimal_part = part.split(".")[1]
            assert len(decimal_part) == 6

    def test_low_fill_ratio_excluded(self, sample_bboxes):
        output = bboxes_to_yolo(sample_bboxes, img_w=640, img_h=480, min_fill_ratio=0.9)
        assert output == ""

    def test_empty_list_returns_empty_string(self):
        output = bboxes_to_yolo([], img_w=640, img_h=480)
        assert output == ""

    def test_coordinates_clamped_to_range(self):
        bbox_out_of_bounds = {
            "x_min": -50, "y_min": -50,
            "x_max": 700, "y_max": 550,
            "fill_ratio": 0.5, "area_px": 10000, "n_pixels": 5000,
        }
        output = bboxes_to_yolo([bbox_out_of_bounds], img_w=640, img_h=480)
        parts = output.split()
        xc = float(parts[1])
        yc = float(parts[2])
        w = float(parts[3])
        h = float(parts[4])
        assert 0.0 <= xc <= 1.0
        assert 0.0 <= yc <= 1.0
        assert 0.0 <= w <= 1.0
        assert 0.0 <= h <= 1.0

    def test_single_bbox_correct_values(self, single_bbox):
        bbox = single_bbox[0]
        output = bboxes_to_yolo(single_bbox, img_w=640, img_h=480)
        parts = output.split()
        xc = float(parts[1])
        yc = float(parts[2])
        w = float(parts[3])
        h = float(parts[4])
        expected_xc = ((bbox["x_min"] + bbox["x_max"]) / 2) / 640
        expected_yc = ((bbox["y_min"] + bbox["y_max"]) / 2) / 480
        expected_w = (bbox["x_max"] - bbox["x_min"]) / 640
        expected_h = (bbox["y_max"] - bbox["y_min"]) / 480
        assert xc == pytest.approx(expected_xc, abs=1e-5)
        assert yc == pytest.approx(expected_yc, abs=1e-5)
        assert w == pytest.approx(expected_w, abs=1e-5)
        assert h == pytest.approx(expected_h, abs=1e-5)

    def test_custom_class_id(self):
        bbox = {"x_min": 0, "y_min": 0, "x_max": 100, "y_max": 100,
                "fill_ratio": 0.5, "area_px": 10000, "n_pixels": 5000}
        output = bboxes_to_yolo([bbox], img_w=200, img_h=200, class_id=5)
        assert output.startswith("5 ")

    def test_no_empty_line_trailing(self):
        output = bboxes_to_yolo([], img_w=640, img_h=480)
        assert output == ""
        assert output.rstrip() == output


# ---------------------------------------------------------------------------
# End-to-End Cascade
# ---------------------------------------------------------------------------

class TestEndToEndCascade:
    def test_full_pipeline_detects_fire(self, synthetic_celsius_array):
        mask1 = apply_absolute_threshold(synthetic_celsius_array, 150.0)
        mask2 = apply_gradient_filter(synthetic_celsius_array, mask1, 40.0)
        mask3 = apply_area_shape_filter(mask2, min_area=50)
        bboxes = cluster_fire_regions(mask3, eps=30)
        labels = bboxes_to_yolo(bboxes, 640, 512)
        assert len(labels) > 0

    def test_full_pipeline_nofire_returns_empty(self, celsius_nofire_array):
        mask1 = apply_absolute_threshold(celsius_nofire_array, 150.0)
        mask2 = apply_gradient_filter(celsius_nofire_array, mask1, 40.0)
        mask3 = apply_area_shape_filter(mask2, min_area=50)
        bboxes = cluster_fire_regions(mask3, eps=30)
        labels = bboxes_to_yolo(bboxes, 640, 512)
        assert labels == ""

    def test_full_pipeline_shape_consistency(self, synthetic_celsius_array):
        h, w = synthetic_celsius_array.shape
        mask1 = apply_absolute_threshold(synthetic_celsius_array, 150.0)
        assert mask1.shape == (h, w)
        mask2 = apply_gradient_filter(synthetic_celsius_array, mask1, 40.0)
        assert mask2.shape == (h, w)
        mask3 = apply_area_shape_filter(mask2, min_area=50)
        assert mask3.shape == (h, w)


# ---------------------------------------------------------------------------
# process_single_tiff â€” orchestrator integration
# ---------------------------------------------------------------------------

class TestProcessSingleTiff:
    def test_fire_tiff_produces_bboxes(self, test_data_dir, sample_config_dict):
        tiff_path = str(test_data_dir / "flame_fire" / "00001.TIFF")
        result = process_single_tiff(tiff_path, sample_config_dict)
        assert result is not None
        yolo_str, debug_img = result
        assert yolo_str != ""
        for line in yolo_str.strip().split("\n"):
            assert line.startswith("0 ")
        assert debug_img is None

    def test_nofire_tiff_produces_empty_string(self, test_data_dir, sample_config_dict):
        tiff_path = str(test_data_dir / "flame_nofire" / "00001.TIFF")
        result = process_single_tiff(tiff_path, sample_config_dict)
        assert result is not None
        yolo_str, debug_img = result
        assert yolo_str == ""
        assert debug_img is None

    def test_all_fire_tiffs_have_bboxes(self, test_data_dir, sample_config_dict):
        for i in range(1, 6):
            tiff_path = str(test_data_dir / "flame_fire" / f"{i:05d}.TIFF")
            result = process_single_tiff(tiff_path, sample_config_dict)
            assert result is not None
            yolo_str, _ = result
            assert yolo_str != "", f"Fire TIFF {i:05d} should have bboxes"

    def test_all_nofire_tiffs_are_empty(self, test_data_dir, sample_config_dict):
        for i in range(1, 3):
            tiff_path = str(test_data_dir / "flame_nofire" / f"{i:05d}.TIFF")
            result = process_single_tiff(tiff_path, sample_config_dict)
            assert result is not None
            yolo_str, _ = result
            assert yolo_str == "", f"No-fire TIFF {i:05d} should be empty"

    def test_debug_overlay_with_jpg(self, test_data_dir, sample_config_dict):
        tiff_path = str(test_data_dir / "flame_fire" / "00001.TIFF")
        jpg_path = str(test_data_dir / "flame_fire_jpg" / "00001.JPG")
        result = process_single_tiff(tiff_path, sample_config_dict, jpg_path=jpg_path)
        assert result is not None
        yolo_str, debug_img = result
        assert debug_img is not None
        assert debug_img.shape[2] == 3
        assert debug_img.shape[0] == 542  # 512 + 30px footer
        assert debug_img.shape[1] == 640
        assert yolo_str != ""

    def test_missing_tiff_returns_none(self, sample_config_dict):
        result = process_single_tiff("nonexistent_file.TIFF", sample_config_dict)
        assert result is None

    def test_config_missing_required_key(self, sample_config_dict):
        incomplete = sample_config_dict.copy()
        del incomplete["absolute_threshold"]
        with pytest.raises(ValueError, match="absolute_threshold"):
            process_single_tiff("dummy.TIFF", incomplete)

    def test_config_multiple_missing_keys(self, sample_config_dict):
        incomplete = {"absolute_threshold": 150.0}
        with pytest.raises(ValueError) as exc_info:
            process_single_tiff("dummy.TIFF", incomplete)
        msg = str(exc_info.value)
        for key in [
            "gradient_threshold", "min_area", "max_aspect_ratio",
            "dbscan_eps", "dbscan_min_samples", "max_bbox_ratio",
            "kmeans_subdivide_threshold", "min_fill_ratio", "class_id",
        ]:
            assert key in msg, f"Missing key '{key}' should be mentioned in error"

    def test_pipeline_ordering_matches_design(self, test_data_dir, sample_config_dict):
        tiff_path = str(test_data_dir / "flame_fire" / "00001.TIFF")
        result = process_single_tiff(tiff_path, sample_config_dict)
        assert result is not None
        yolo_str, _ = result
        assert yolo_str != ""
        for line in yolo_str.strip().split("\n"):
            parts = line.split()
            assert len(parts) == 5
            for val in parts[1:]:
                assert 0.0 <= float(val) <= 1.0
