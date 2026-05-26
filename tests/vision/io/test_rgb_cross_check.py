"""Tests for RGB + Thermal cross-check module."""

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from vision.io.rgb_cross_check import (
    fire_hsv_ratio,
    cross_check_label,
    cross_check_dataset,
    DEFAULT_MIN_FIRE_RATIO,
)


def _make_rgb_image(w: int, h: int, color_bgr: tuple[int, int, int]) -> np.ndarray:
    """Create a solid-color BGR image."""
    return np.full((h, w, 3), color_bgr, dtype=np.uint8)


def _make_fire_region(w: int, h: int) -> np.ndarray:
    """Create an image with fire-like orange/red pixels."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = (0, 100, 255)  # Orange in BGR (0, 100, 255) = H ~ 10-15
    return img


def _make_no_fire_region(w: int, h: int) -> np.ndarray:
    """Create an image with no fire colors (green vegetation)."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = (100, 180, 50)  # Green in BGR
    return img


class TestFireHsvRatio:
    def test_empty_array(self):
        result = fire_hsv_ratio(np.array([], dtype=np.uint8))
        assert result == 0.0

    def test_all_fire_orange(self):
        img = _make_fire_region(100, 50)
        ratio = fire_hsv_ratio(img)
        assert ratio > 0.5, f"Expected >0.5 fire ratio in orange image, got {ratio:.4f}"

    def test_all_green(self):
        img = _make_no_fire_region(100, 50)
        ratio = fire_hsv_ratio(img)
        assert ratio < DEFAULT_MIN_FIRE_RATIO, f"Expected near-zero fire ratio in green image, got {ratio:.4f}"

    def test_all_black(self):
        img = _make_rgb_image(100, 50, (0, 0, 0))
        ratio = fire_hsv_ratio(img)
        assert ratio == 0.0

    def test_mixed_fire_and_nonfire(self):
        img = _make_no_fire_region(100, 50)
        img[10:40, 20:50] = (0, 100, 255)  # Fire patch
        ratio = fire_hsv_ratio(img)
        assert 0.1 < ratio < 0.5, f"Expected mixed ratio, got {ratio:.4f}"

    def test_bright_red(self):
        img = np.full((50, 50, 3), (0, 0, 255), dtype=np.uint8)  # Pure red BGR
        ratio = fire_hsv_ratio(img)
        assert ratio > 0.7, f"Bright red should have high fire ratio, got {ratio:.4f}"

    def test_dark_red(self):
        img = np.full((50, 50, 3), (0, 0, 40), dtype=np.uint8)  # Dark red (V=40 < 50 threshold)
        ratio = fire_hsv_ratio(img)
        assert ratio < DEFAULT_MIN_FIRE_RATIO, f"Dark red should have low fire ratio, got {ratio:.4f}"

    def test_gray_warm(self):
        img = np.full((50, 50, 3), (80, 80, 80), dtype=np.uint8)  # Gray (warm ground)
        ratio = fire_hsv_ratio(img)
        assert ratio < DEFAULT_MIN_FIRE_RATIO, f"Gray should have zero fire ratio, got {ratio:.4f}"


class TestCrossCheckLabel:
    def test_empty_label(self, tmp_path):
        rgb_path = tmp_path / "test.jpg"
        cv2.imwrite(str(rgb_path), _make_fire_region(640, 512))
        filtered, stats = cross_check_label(str(rgb_path), "", 640, 512)
        assert filtered == ""
        assert stats["empty_label"] is True
        assert stats["total_bboxes"] == 0

    def test_single_bbox_fire_confirmed(self, tmp_path):
        rgb_path = tmp_path / "fire_rgb.jpg"
        cv2.imwrite(str(rgb_path), _make_fire_region(640, 512))
        # Bbox in center covering 50% of image
        label = "0 0.50 0.50 0.50 0.50"
        filtered, stats = cross_check_label(str(rgb_path), label, 640, 512)
        assert stats["total_bboxes"] == 1
        assert stats["kept_bboxes"] == 1
        assert stats["removed_bboxes"] == 0
        assert label in filtered

    def test_single_bbox_fire_rejected(self, tmp_path):
        rgb_path = tmp_path / "no_fire_rgb.jpg"
        cv2.imwrite(str(rgb_path), _make_no_fire_region(640, 512))
        label = "0 0.50 0.50 0.50 0.50"
        filtered, stats = cross_check_label(str(rgb_path), label, 640, 512)
        assert stats["total_bboxes"] == 1
        assert stats["removed_bboxes"] == 1
        assert stats["kept_bboxes"] == 0
        assert filtered == ""

    def test_mixed_keep_and_reject(self, tmp_path):
        rgb_path = tmp_path / "mixed.jpg"
        img = _make_no_fire_region(640, 512)
        img[50:150, 50:150] = (0, 100, 255)  # Fire patch
        cv2.imwrite(str(rgb_path), img)

        labels = [
            "0 0.15625 0.19531 0.15625 0.19531",  # Fire patch (50-150, 50-150)
            "0 0.70 0.70 0.10 0.10",                # No-fire region
        ]
        filtered, stats = cross_check_label(str(rgb_path), "\n".join(labels), 640, 512)
        assert stats["total_bboxes"] == 2
        assert stats["kept_bboxes"] >= 1

    def test_rgb_read_error(self, tmp_path):
        rgb_path = tmp_path / "nonexistent.jpg"
        label = "0 0.50 0.50 0.50 0.50"
        filtered, stats = cross_check_label(str(rgb_path), label, 640, 512)
        assert stats["rgb_read_error"] is True
        assert filtered == label  # Pass-through on error

    def test_malformed_line_passed_through(self, tmp_path):
        rgb_path = tmp_path / "fire.jpg"
        cv2.imwrite(str(rgb_path), _make_fire_region(640, 512))
        label = "bad line"
        filtered, stats = cross_check_label(str(rgb_path), label, 640, 512)
        assert stats["kept_bboxes"] == 1  # Malformed lines are kept

    def test_small_crop_passed(self, tmp_path):
        rgb_path = tmp_path / "fire.jpg"
        cv2.imwrite(str(rgb_path), _make_fire_region(640, 512))
        label = "0 0.50 0.50 0.001 0.001"  # Tiny bbox
        filtered, stats = cross_check_label(str(rgb_path), label, 640, 512)
        assert stats["kept_bboxes"] == 1  # Small crops pass through


class TestCrossCheckDataset:
    def test_full_dataset_crosscheck(self, tmp_path):
        prepared = tmp_path / "prepared"
        labels_dir = prepared / "labels" / "all"
        labels_dir.mkdir(parents=True)

        rgb_dir = tmp_path / "rgb"
        rgb_dir.mkdir()

        # Create fire label with bboxes
        fire_label = labels_dir / "flame_fire_00001.txt"
        fire_label.write_text("0 0.50 0.50 0.30 0.30\n0 0.20 0.20 0.10 0.10")

        # Create nofire label (empty â€” should be skipped)
        nofire_label = labels_dir / "flame_nofire_00081.txt"
        nofire_label.write_text("")

        # Create paired RGB with fire colors
        rgb_img = _make_fire_region(640, 512)
        cv2.imwrite(str(rgb_dir / "00001.jpg"), rgb_img)

        report = cross_check_dataset(str(prepared), str(rgb_dir), img_w=640, img_h=512)

        assert report["total_labels_checked"] == 1
        assert report["total_bboxes_before"] == 2
        assert report["total_bboxes_after"] == 2  # RGB has fire â†’ both kept
        assert report["rgb_missing"] == 0
        assert Path(prepared, "cross_check_report.json").exists()

        # Verify backup exists
        assert Path(prepared, "labels", "all_pre_crosscheck", "flame_fire_00001.txt").exists()

    def test_skip_nofire_labels(self, tmp_path):
        prepared = tmp_path / "prepared"
        labels_dir = prepared / "labels" / "all"
        labels_dir.mkdir(parents=True)

        rgb_dir = tmp_path / "rgb"
        rgb_dir.mkdir()

        # Only nofire labels â€” should check zero
        nofire_label = labels_dir / "flame_nofire_00001.txt"
        nofire_label.write_text("")

        report = cross_check_dataset(str(prepared), str(rgb_dir))
        assert report["total_labels_checked"] == 0

    def test_rgb_missing(self, tmp_path):
        prepared = tmp_path / "prepared"
        labels_dir = prepared / "labels" / "all"
        labels_dir.mkdir(parents=True)

        rgb_dir = tmp_path / "rgb_empty"
        rgb_dir.mkdir()

        fire_label = labels_dir / "flame_fire_00099.txt"
        fire_label.write_text("0 0.50 0.50 0.30 0.30")

        report = cross_check_dataset(str(prepared), str(rgb_dir))
        assert report["rgb_missing"] == 1
        assert report["total_labels_checked"] == 1
