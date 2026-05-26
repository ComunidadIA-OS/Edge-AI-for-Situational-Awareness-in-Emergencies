from pathlib import Path

import numpy as np
import pytest
import cv2

from vision.utils.debug_viz import create_debug_overlay


def _make_fake_jpg(tmp_path, name="test.jpg", shape=(512, 640), color=0):
    jpg_path = str(tmp_path / name)
    bg = np.full((*shape, 3), color, dtype=np.uint8)
    cv2.imwrite(jpg_path, bg)
    return jpg_path


class TestCreateDebugOverlay:
    def test_output_dimensions(
        self, synthetic_celsius_array, synthetic_fire_mask, sample_bboxes, tmp_path
    ):
        jpg_path = _make_fake_jpg(tmp_path)
        result = create_debug_overlay(
            jpg_path, synthetic_celsius_array, synthetic_fire_mask, sample_bboxes
        )
        assert result.shape == (512 + 30, 640, 3)
        assert result.dtype == np.uint8

    def test_output_is_bgr(
        self, synthetic_celsius_array, synthetic_fire_mask, single_bbox, tmp_path
    ):
        jpg_path = _make_fake_jpg(tmp_path)
        result = create_debug_overlay(
            jpg_path, synthetic_celsius_array, synthetic_fire_mask, single_bbox
        )
        bbox = single_bbox[0]
        y_sample = bbox["y_min"] + 1
        x_sample = bbox["x_min"] + 1
        assert result[y_sample, x_sample, 1] > result[y_sample, x_sample, 0]

    def test_empty_bboxes_generates_no_rectangles(
        self, synthetic_celsius_array, synthetic_fire_mask, tmp_path
    ):
        jpg_path = _make_fake_jpg(tmp_path)
        result = create_debug_overlay(
            jpg_path, synthetic_celsius_array, synthetic_fire_mask, []
        )
        assert result is not None
        assert result.shape == (512 + 30, 640, 3)

    def test_saves_to_disk(
        self, synthetic_celsius_array, synthetic_fire_mask, sample_bboxes, tmp_path
    ):
        jpg_path = _make_fake_jpg(tmp_path)
        output_path = str(tmp_path / "debug.jpg")
        create_debug_overlay(
            jpg_path,
            synthetic_celsius_array,
            synthetic_fire_mask,
            sample_bboxes,
            output_path=output_path,
        )
        assert Path(output_path).exists()
        loaded = cv2.imread(output_path)
        assert loaded.shape == (512 + 30, 640, 3)

    def test_missing_jpg_raises_valueerror(
        self, synthetic_celsius_array, synthetic_fire_mask, sample_bboxes
    ):
        with pytest.raises(ValueError, match="JPG not found"):
            create_debug_overlay(
                "nonexistent.jpg",
                synthetic_celsius_array,
                synthetic_fire_mask,
                sample_bboxes,
            )

    def test_none_celsius_raises_valueerror(self, tmp_path):
        jpg_path = _make_fake_jpg(tmp_path)
        with pytest.raises(ValueError, match="celsius array must not be None"):
            create_debug_overlay(
                jpg_path, None, np.zeros((512, 640), dtype=np.uint8), []
            )

    def test_none_mask_raises_valueerror(self, synthetic_celsius_array, tmp_path):
        jpg_path = _make_fake_jpg(tmp_path)
        with pytest.raises(ValueError, match="mask must not be None"):
            create_debug_overlay(jpg_path, synthetic_celsius_array, None, [])

    def test_shape_mismatch_raises_valueerror(
        self, synthetic_celsius_array, synthetic_fire_mask, tmp_path
    ):
        jpg_path = _make_fake_jpg(tmp_path)
        bad_mask = np.zeros((200, 300), dtype=np.uint8)
        with pytest.raises(ValueError, match="Shape mismatch"):
            create_debug_overlay(jpg_path, synthetic_celsius_array, bad_mask, [])

    def test_heatmap_overlay_applied(
        self, synthetic_celsius_array, synthetic_fire_mask, sample_bboxes, tmp_path
    ):
        jpg_path = _make_fake_jpg(tmp_path, color=255)
        result = create_debug_overlay(
            jpg_path, synthetic_celsius_array, synthetic_fire_mask, sample_bboxes
        )
        h = synthetic_celsius_array.shape[0]
        active_mask = synthetic_fire_mask > 0
        active_pixels = result[:h][active_mask]
        assert not np.all(active_pixels[:, 0] == 255)

    def test_legend_bar_present(
        self, synthetic_celsius_array, synthetic_fire_mask, sample_bboxes, tmp_path
    ):
        jpg_path = _make_fake_jpg(tmp_path)
        result = create_debug_overlay(
            jpg_path, synthetic_celsius_array, synthetic_fire_mask, sample_bboxes
        )
        h = synthetic_celsius_array.shape[0]
        legend_region = result[:h, -30:, :]
        assert legend_region.std() > 0

    def test_footer_contains_expected_info(
        self, synthetic_celsius_array, synthetic_fire_mask, sample_bboxes, tmp_path
    ):
        jpg_path = _make_fake_jpg(tmp_path)
        result = create_debug_overlay(
            jpg_path, synthetic_celsius_array, synthetic_fire_mask, sample_bboxes
        )
        h = synthetic_celsius_array.shape[0]
        footer_region = result[h:, :, :]
        assert footer_region.mean() < 50

    def test_no_fire_image_produces_valid_output(
        self, celsius_nofire_array, tmp_path
    ):
        jpg_path = _make_fake_jpg(tmp_path)
        nofire_mask = np.zeros((512, 640), dtype=np.uint8)
        result = create_debug_overlay(
            jpg_path, celsius_nofire_array, nofire_mask, []
        )
        assert result.shape == (542, 640, 3)

    def test_resize_jpg_to_match_celsius(
        self, synthetic_celsius_array, synthetic_fire_mask, sample_bboxes, tmp_path
    ):
        jpg_path = _make_fake_jpg(tmp_path, shape=(300, 400))
        result = create_debug_overlay(
            jpg_path, synthetic_celsius_array, synthetic_fire_mask, sample_bboxes
        )
        assert result.shape == (512 + 30, 640, 3)

    def test_footer_text_param(
        self, synthetic_celsius_array, synthetic_fire_mask, single_bbox, tmp_path
    ):
        jpg_path = _make_fake_jpg(tmp_path)
        result = create_debug_overlay(
            jpg_path,
            synthetic_celsius_array,
            synthetic_fire_mask,
            single_bbox,
            footer_text="FLAME_001.TIFF",
        )
        assert result is not None
        assert result.shape == (512 + 30, 640, 3)
