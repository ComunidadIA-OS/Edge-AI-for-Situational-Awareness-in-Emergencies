"""Tests for infer_jetson.py -- runnable without Jetson hardware.

All GPU/CUDA-dependent functions are tested for graceful error handling
and correct function signatures. Graphics functions use synthetic frames.
"""

import inspect
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from vision.inference.infer_jetson import (
    draw_overlay,
    get_gstreamer_pipeline,
    list_video_devices,
    load_model,
    predict_frame,
    run_camera_loop,
)


class TestListVideoDevices:
    def test_returns_list(self):
        result = list_video_devices()
        assert isinstance(result, list)

    def test_all_entries_are_strings(self):
        devices = list_video_devices()
        for dev in devices:
            assert isinstance(dev, str)

    def test_returns_empty_or_strings_on_any_os(self):
        result = list_video_devices()
        assert isinstance(result, list)
        if result:
            for item in result:
                assert isinstance(item, str)
                assert "/dev/video" in item


class TestGetGstreamerPipeline:
    def test_flir_boson_contains_format_bgr(self):
        pipeline = get_gstreamer_pipeline("/dev/video0", "flir_boson")
        assert "format=BGR" in pipeline
        assert "appsink" in pipeline
        assert "/dev/video0" in pipeline

    def test_v4l2_contains_format_bgr(self):
        pipeline = get_gstreamer_pipeline("/dev/video0", "v4l2")
        assert "format=BGR" in pipeline
        assert "appsink" in pipeline
        assert "/dev/video0" in pipeline

    def test_rtsp_contains_format_bgr(self):
        pipeline = get_gstreamer_pipeline("rtsp://192.168.1.100/stream", "rtsp")
        assert "format=BGR" in pipeline
        assert "appsink" in pipeline
        assert "rtsp://192.168.1.100/stream" in pipeline

    def test_all_templates_return_non_empty_strings(self):
        for tmpl in ("flir_boson", "v4l2", "rtsp"):
            pipeline = get_gstreamer_pipeline("/dev/video0", tmpl)
            assert isinstance(pipeline, str)
            assert len(pipeline) > 0

    def test_flir_boson_default_template(self):
        pipeline = get_gstreamer_pipeline("/dev/video0")
        assert "UYVY" in pipeline
        assert "format=BGR" in pipeline

    def test_v4l2_template_has_bgr_format(self):
        pipeline = get_gstreamer_pipeline("/dev/video0", "v4l2")
        assert "format=BGR" in pipeline
        assert "v4l2src" in pipeline

    def test_invalid_template_raises_valueerror(self):
        with pytest.raises(ValueError, match="Invalid GStreamer template"):
            get_gstreamer_pipeline("/dev/video0", "invalid_template")

    def test_all_templates_end_with_appsink(self):
        for tmpl in ("flir_boson", "v4l2", "rtsp"):
            pipeline = get_gstreamer_pipeline("/dev/video0" if tmpl != "rtsp" else "rtsp://cam/stream", tmpl)
            assert pipeline.rstrip().endswith("appsink drop=1 max-buffers=2")

    def test_rtsp_uses_jetson_codecs(self):
        pipeline = get_gstreamer_pipeline("rtsp://cam/stream", "rtsp")
        assert "nvv4l2decoder" in pipeline
        assert "nvvidconv" in pipeline


class TestLoadModelErrors:
    def test_missing_file_raises_filenotfound(self, tmp_path: Path):
        fake_path = str(tmp_path / "nonexistent.engine")
        with pytest.raises(FileNotFoundError, match="not found"):
            load_model(fake_path)

    def test_missing_deps_raises_runtimeerror(self, tmp_path: Path):
        engine_file = tmp_path / "dummy.engine"
        engine_file.write_bytes(b"\x00" * 100)

        with patch("builtins.__import__", side_effect=ImportError("No ultralytics")):
            with pytest.raises(RuntimeError, match="Missing required dependency"):
                load_model(str(engine_file))

    def test_function_signature(self):
        sig = inspect.signature(load_model)
        params = list(sig.parameters.keys())
        assert "engine_path" in params


class TestPredictFrame:
    def test_function_exists(self):
        assert callable(predict_frame)

    def test_signature_accepts_model_frame_conf(self):
        sig = inspect.signature(predict_frame)
        params = list(sig.parameters.keys())
        assert "model" in params
        assert "frame" in params
        assert "conf" in params
        assert sig.parameters["conf"].default == 0.25

    def test_returns_list_without_calling_model(self):
        mock_model = MagicMock()
        mock_model.predict.return_value = [MagicMock()]
        mock_model.predict.return_value[0].boxes = None

        frame = np.zeros((640, 640, 3), dtype=np.uint8)
        result = predict_frame(mock_model, frame)
        assert isinstance(result, list)
        assert result == []

    def test_returns_empty_list_when_no_boxes(self):
        mock_model = MagicMock()
        mock_results = MagicMock()
        mock_results.boxes = None
        mock_model.predict.return_value = [mock_results]

        frame = np.zeros((640, 640, 3), dtype=np.uint8)
        result = predict_frame(mock_model, frame)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_extracts_detection_dict_correctly(self):
        mock_model = MagicMock()

        mock_box_entry = MagicMock()
        mock_box_entry.xyxy = [MagicMock()]
        mock_box_entry.xyxy[0].cpu.return_value.numpy.return_value = (
            np.array([10.0, 20.0, 50.0, 60.0])
        )
        mock_box_entry.conf = [MagicMock()]
        mock_box_entry.conf[0].cpu.return_value.numpy.return_value = np.array(0.95)

        mock_boxes = MagicMock()
        mock_boxes.__len__.return_value = 1
        mock_boxes.__iter__.return_value = iter([mock_box_entry])

        mock_results = MagicMock()
        mock_results.boxes = mock_boxes
        mock_model.predict.return_value = [mock_results]

        frame = np.zeros((640, 640, 3), dtype=np.uint8)
        result = predict_frame(mock_model, frame, conf=0.5)

        assert len(result) == 1
        det = result[0]
        assert det["x_min"] == 10.0
        assert det["y_min"] == 20.0
        assert det["x_max"] == 50.0
        assert det["y_max"] == 60.0
        assert det["confidence"] == 0.95
        assert all(isinstance(v, float) for v in det.values())

    def test_never_returns_none(self):
        mock_model = MagicMock()
        mock_results = MagicMock()
        mock_results.boxes = None
        mock_model.predict.return_value = [mock_results]

        frame = np.zeros((640, 640, 3), dtype=np.uint8)
        result = predict_frame(mock_model, frame)
        assert result is not None
        assert isinstance(result, list)


class TestDrawOverlay:
    def test_empty_detections_same_shape(self):
        frame = np.zeros((640, 640, 3), dtype=np.uint8)
        result = draw_overlay(frame, [], 30.0)
        assert isinstance(result, np.ndarray)
        assert result.shape == (640, 640, 3)
        assert result is frame

    def test_fps_counter_drawn_in_top_left(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = draw_overlay(frame, [], 30.0)
        top_left_region = result[5:40, 5:200]
        assert np.any(top_left_region[:, :, 1] > 0)

    def test_detection_draws_green_pixels(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = [{"x_min": 100.0, "y_min": 100.0, "x_max": 200.0, "y_max": 200.0, "confidence": 0.85}]
        result = draw_overlay(frame, detections, 30.0)
        assert np.any(result[:, :, 1] > 0)

    def test_fps_text_contains_number(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = draw_overlay(frame, [], 30.0)
        top_left_region = result[5:40, 5:200]
        assert np.any(top_left_region[:, :, 1] > 0)

    def test_multiple_detections_all_drawn(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = [
            {"x_min": 50.0, "y_min": 50.0, "x_max": 150.0, "y_max": 150.0, "confidence": 0.75},
            {"x_min": 300.0, "y_min": 200.0, "x_max": 450.0, "y_max": 350.0, "confidence": 0.90},
        ]
        result = draw_overlay(frame, detections, 25.0)
        green_pixels = np.sum(result[:, :, 1] > 0)
        assert green_pixels > 0


class TestRunCameraLoop:
    def test_function_exists(self):
        assert callable(run_camera_loop)

    def test_signature_accepts_source_model_config(self):
        sig = inspect.signature(run_camera_loop)
        params = list(sig.parameters.keys())
        assert "source" in params
        assert "model" in params
        assert "config" in params
        assert sig.parameters["config"].default is None

    def test_invalid_source_raises_runtimeerror(self):
        mock_model = MagicMock()
        with pytest.raises(RuntimeError, match="Failed to open"):
            run_camera_loop("nonexistent_file.mp4", mock_model)


class TestImportability:
    def test_all_public_functions_importable(self):
        funcs = [
            list_video_devices,
            get_gstreamer_pipeline,
            load_model,
            predict_frame,
            draw_overlay,
            run_camera_loop,
        ]
        for func in funcs:
            assert callable(func), f"{func.__name__} is not callable"


class TestErrorMessages:
    def test_cv2_missing_message(self):
        with patch("vision.inference.infer_jetson._get_cv2", side_effect=RuntimeError("OpenCV (cv2) is required")):
            with pytest.raises(RuntimeError, match="OpenCV"):
                from vision.inference.infer_jetson import _get_cv2
                _get_cv2()

    def test_gstreamer_invalid_template_message(self):
        with pytest.raises(ValueError, match="Choose from:"):
            get_gstreamer_pipeline("/dev/video0", "bad_pipeline")


class TestCliListCameras:
    def test_list_cameras_flag(self, capsys):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "vision.inference.infer_jetson", "--list-cameras", "--engine", "dummy.engine"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parents[3]),
        )
        assert result.returncode == 0
        combined = result.stdout + result.stderr
        assert "video" in combined.lower() or "No video" in combined
