# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Saúl Briceño, Carlos Langa, and ComunidadIA-OS contributors
#
# Part of Heimdall's vision-inference path — a derivative work of Ultralytics
# YOLO — licensed under AGPL-3.0. See LICENSE-AGPL-3.0.txt and NOTICE.

"""Jetson AGX Inference — Heimdall Fire Detection.

Runs TensorRT YOLO inference with GStreamer camera pipelines on NVIDIA Jetson.
Written for Jetson AGX with TensorRT, CUDA, OpenCV, and GStreamer.
Gracefully handles missing hardware on non-Jetson platforms.

Usage:
    python src/infer_jetson.py --engine best_fp16.engine --source /dev/video0
    python src/infer_jetson.py --engine best_fp16.engine --list-cameras
"""

from __future__ import annotations

import argparse
import logging
import platform
import sys
import time
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def list_video_devices() -> list[str]:
    """Scan /dev/video* on Linux. Returns empty list on non-Linux.

    Returns:
        List of discovered video device paths.
    """
    if platform.system() != "Linux":
        return []

    video_dir = Path("/dev")
    if not video_dir.exists():
        return []

    devices = sorted(
        str(p) for p in video_dir.glob("video*")
    )
    return devices


def get_gstreamer_pipeline(source: str, template: str = "flir_boson") -> str:
    """Build a GStreamer pipeline string for the given source and template.

    All pipelines output BGR format for OpenCV compatibility.

    Args:
        source: Device path, integer camera index, or RTSP URL.
        template: One of "flir_boson", "v4l2", "rtsp".

    Returns:
        GStreamer pipeline string ending with appsink format=BGR.

    Raises:
        ValueError: If template is not one of the valid options.
    """
    templates = {
        "flir_boson": (
            f"v4l2src device={source} ! "
            "video/x-raw,format=UYVY,width=640,height=512,framerate=30/1 ! "
            "videoconvert ! "
            "video/x-raw,format=BGR ! "
            "appsink drop=1 max-buffers=2"
        ),
        "v4l2": (
            f"v4l2src device={source} ! "
            "video/x-raw,format=BGR,width=640,height=480,framerate=30/1 ! "
            "appsink drop=1 max-buffers=2"
        ),
        "rtsp": (
            f"rtspsrc location={source} latency=0 ! "
            "rtph264depay ! h264parse ! nvv4l2decoder ! nvvidconv ! "
            "video/x-raw,format=BGRx ! videoconvert ! "
            "video/x-raw,format=BGR ! "
            "appsink drop=1 max-buffers=2"
        ),
    }

    if template not in templates:
        raise ValueError(
            f"Invalid GStreamer template: '{template}'. "
            f"Choose from: {', '.join(sorted(templates.keys()))}"
        )

    return templates[template]


def load_model(engine_path: str) -> object:
    """Load a TensorRT YOLO engine and run warm-up inference.

    Args:
        engine_path: Path to the .engine file exported by export_tensorrt.py.

    Returns:
        Loaded YOLO model object ready for inference.

    Raises:
        FileNotFoundError: If engine_path does not exist.
        RuntimeError: If required dependencies are missing or engine fails to load.
    """
    engine_file = Path(engine_path)
    if not engine_file.exists():
        raise FileNotFoundError(f"TensorRT engine not found: {engine_path}")

    try:
        import tensorrt as trt
        import torch
        from ultralytics import YOLO
    except ImportError as e:
        raise RuntimeError(
            f"Missing required dependency: {e}. "
            "Install with: pip install torch ultralytics tensorrt"
        )

    logger.info("TensorRT version: %s", getattr(trt, "__version__", "unknown"))
    logger.info("Torch version: %s", torch.__version__)
    logger.info("Ultralytics version: %s", __import__("ultralytics").__version__)

    logger.info("Loading TensorRT engine: %s", engine_path)
    model = YOLO(engine_path)
    engine_size_mb = engine_file.stat().st_size / (1024 * 1024)
    logger.info("Engine loaded: %.1f MB", engine_size_mb)

    logger.info("Running warm-up inference on synthetic frame...")
    dummy_frame = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
    results = model.predict(dummy_frame, verbose=False)
    logger.info("Warm-up complete: %d result(s)", len(results))

    return model


def predict_frame(
    model: object, frame: np.ndarray, conf: float = 0.25
) -> list[dict[str, float]]:
    """Run YOLO inference on a single BGR frame.

    Args:
        model: Loaded YOLO model from load_model().
        frame: BGR image as uint8 ndarray (H, W, 3).
        conf: Confidence threshold for detections.

    Returns:
        List of detection dicts, each with keys:
            x_min, y_min, x_max, y_max, confidence (all floats).
        Returns empty list when no detections found.
    """
    results = model.predict(frame, conf=conf, verbose=False)
    detections: list[dict[str, float]] = []

    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return detections

    for box in boxes:
        xyxy = box.xyxy[0].cpu().numpy()
        conf_val = float(box.conf[0].cpu().numpy())
        detections.append({
            "x_min": float(xyxy[0]),
            "y_min": float(xyxy[1]),
            "x_max": float(xyxy[2]),
            "y_max": float(xyxy[3]),
            "confidence": conf_val,
        })

    return detections


def draw_overlay(
    frame: np.ndarray, detections: list[dict[str, float]], fps: float
) -> np.ndarray:
    """Draw bounding boxes, confidence labels, and FPS counter on a frame.

    Args:
        frame: BGR image as uint8 ndarray (H, W, 3). Modified in place.
        detections: List of detection dicts from predict_frame().
        fps: Current FPS value to display.

    Returns:
        Annotated frame (same array reference, modified in place).
    """
    cv2 = _get_cv2()
    GREEN = (0, 255, 0)

    for det in detections:
        x_min = int(det["x_min"])
        y_min = int(det["y_min"])
        x_max = int(det["x_max"])
        y_max = int(det["y_max"])
        conf = det["confidence"]

        cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), GREEN, 2)

        label = f"FIRE {conf:.2f}"
        (label_w, label_h), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2
        )
        label_y = y_min - 10 if y_min - 10 > label_h else y_min + label_h + 10
        cv2.rectangle(
            frame,
            (x_min, label_y - label_h - baseline),
            (x_min + label_w, label_y + baseline),
            GREEN,
            -1,
        )
        cv2.putText(
            frame,
            label,
            (x_min, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            2,
        )
    fps_text = f"FPS: {fps:.1f}"
    cv2.putText(
        frame,
        fps_text,
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2,
    )

    return frame


def run_camera_loop(
    source: str, model: object, config: dict | None = None
) -> None:
    """Main real-time inference loop with video capture and display.

    Opens video source (file, camera, or GStreamer pipeline), runs inference
    on each frame, displays annotated output, and optionally records to disk.

    Args:
        source: Video file path (ends with .mp4/.avi), camera index (integer),
                device path (/dev/video*), or GStreamer pipeline string.
        model: Loaded YOLO model from load_model().
        config: Optional configuration dict with keys:
            - gstreamer_template: "flir_boson" | "v4l2" | "rtsp" (default "flir_boson")
            - conf: Confidence threshold (default 0.25)
            - record: Enable video recording (default False)
            - record_path: Output video path (default "output.avi")
            - window_name: Display window title (default "Heimdall - Fire Detection")
            - api_url: Convergence API URL for FireDetectionPayload POSTing (default None)
            - drone_lat: Drone latitude for geo projection (default 0.0)
            - drone_lon: Drone longitude for geo projection (default 0.0)
            - drone_alt: Drone AGL altitude in metres (default 120.0)
            - drone_heading: Drone heading in degrees 0=N (default 0.0)
            - drone_speed_kmh: Drone speed in km/h (default 0.0)
            - fuel_type_id: Scott/Burgan fuel model 1-13 (default 4)
            - slope_deg: Terrain slope at fire location (default 0.0)
            - api_interval_s: Minimum seconds between API POSTs (default 2.0)

    Raises:
        RuntimeError: If the video source cannot be opened.
    """
    if config is None:
        config = {}

    gst_template = config.get("gstreamer_template", "flir_boson")
    conf = config.get("conf", 0.25)
    record_flag = config.get("record", False)
    record_path = config.get("record_path", "output.avi")
    window_name = config.get("window_name", "Heimdall - Fire Detection")

    api_url = config.get("api_url")
    poster = None
    if api_url:
        from vision.inference.post_to_api import DetectionPoster
        poster = DetectionPoster(
            api_url=api_url,
            drone_lat=config.get("drone_lat", 0.0),
            drone_lon=config.get("drone_lon", 0.0),
            drone_alt_m=config.get("drone_alt", 120.0),
            drone_heading_deg=config.get("drone_heading", 0.0),
            drone_speed_kmh=config.get("drone_speed_kmh", 0.0),
            fuel_type_id=config.get("fuel_type_id", 4),
            slope_deg=config.get("slope_deg", 0.0),
            min_interval_s=config.get("api_interval_s", 2.0),
        )
        logger.info("API poster enabled: %s", api_url)

    cv2 = _get_cv2()

    cap = _open_source(source, gst_template, cv2)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video source: {source}")

    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    logger.info("Camera opened: %dx%d", frame_w, frame_h)

    writer = None
    recording = record_flag
    if recording:
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        writer = cv2.VideoWriter(record_path, fourcc, 30.0, (frame_w, frame_h))
        logger.info("Recording started: %s", record_path)

    fps_history: list[float] = []
    fps_avg = 0.0

    logger.info("Inference loop started. Press 'q' to quit, 'r' to toggle recording.")
    while True:
        loop_start = time.perf_counter()

        ret, frame = cap.read()
        if not ret:
            logger.warning("End of stream or read error for source: %s", source)
            break

        detections = predict_frame(model, frame, conf)

        if poster is not None and detections:
            frame_h, frame_w = frame.shape[:2]
            poster.post(detections, frame_w, frame_h)

        frame = draw_overlay(frame, detections, fps_avg)

        cv2.imshow(window_name, frame)

        if recording and writer is not None:
            writer.write(frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            logger.info("Quit key pressed")
            break
        elif key == ord("r"):
            recording = not recording
            if recording:
                fourcc = cv2.VideoWriter_fourcc(*"XVID")
                writer = cv2.VideoWriter(
                    record_path, fourcc, 30.0, (frame_w, frame_h)
                )
                logger.info("Recording resumed: %s", record_path)
            else:
                if writer is not None:
                    writer.release()
                    writer = None
                logger.info("Recording paused")

        loop_time = time.perf_counter() - loop_start
        fps_history.append(1.0 / loop_time if loop_time > 0 else 0.0)
        if len(fps_history) > 100:
            fps_history.pop(0)
        fps_avg = sum(fps_history) / len(fps_history)

    cap.release()
    cv2.destroyAllWindows()
    if writer is not None:
        writer.release()
    if poster is not None:
        poster.shutdown()
    logger.info("Inference loop ended")


def _get_cv2():
    """Lazy import cv2 with clear error message."""
    try:
        import cv2
        return cv2
    except ImportError:
        raise RuntimeError(
            "OpenCV (cv2) is required for Jetson inference. "
            "Install with: pip install opencv-python"
        )


def _open_source(source: str, gst_template: str, cv2) -> object:
    """Open a video source: file, camera, or GStreamer pipeline.

    Args:
        source: File path, camera index string, device path, or GStreamer string.
        gst_template: GStreamer template name for camera/device sources.
        cv2: OpenCV module reference.

    Returns:
        cv2.VideoCapture object.
    """
    source_lower = source.lower()

    if source.endswith((".mp4", ".avi", ".MP4", ".AVI")):
        return cv2.VideoCapture(source)

    if source.startswith("/dev/video") or source.isdigit():
        pipeline = get_gstreamer_pipeline(source, gst_template)
        logger.info("Opening GStreamer pipeline: %s...", pipeline[:80])
        return cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

    logger.info("Opening source as GStreamer pipeline: %s", source)
    return cv2.VideoCapture(source, cv2.CAP_GSTREAMER)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Heimdall Jetson Fire Detection Inference"
    )
    parser.add_argument(
        "--engine", required=True, help="Path to TensorRT .engine file"
    )
    parser.add_argument(
        "--source", default="0", help="Video source: camera index, /dev/video*, RTSP URL, or video file"
    )
    parser.add_argument(
        "--conf", type=float, default=0.25, help="Confidence threshold (default: 0.25)"
    )
    parser.add_argument(
        "--template",
        choices=["flir_boson", "v4l2", "rtsp"],
        default="flir_boson",
        help="GStreamer pipeline template for camera/device sources (default: flir_boson)",
    )
    parser.add_argument(
        "--list-cameras",
        action="store_true",
        help="List available video devices and exit",
    )
    parser.add_argument(
        "--record", action="store_true", help="Record output to video file"
    )
    parser.add_argument(
        "--api-url", default=None,
        help="Convergence API base URL (e.g. http://localhost:8000). Enables live POST /detect."
    )
    parser.add_argument("--drone-lat", type=float, default=0.0, help="Drone latitude (decimal degrees)")
    parser.add_argument("--drone-lon", type=float, default=0.0, help="Drone longitude (decimal degrees)")
    parser.add_argument("--drone-alt", type=float, default=120.0, help="Drone AGL altitude in metres")
    parser.add_argument("--drone-heading", type=float, default=0.0, help="Drone heading degrees (0=N)")
    parser.add_argument("--fuel-type", type=int, default=4, choices=range(1, 14),
                        metavar="1-13", help="Scott/Burgan fuel model ID (default 4 = chaparral)")
    parser.add_argument("--slope", type=float, default=0.0, help="Terrain slope in degrees")
    parser.add_argument("--api-interval", type=float, default=2.0,
                        help="Minimum seconds between API POSTs (default 2.0)")

    args = parser.parse_args()

    if args.list_cameras:
        devices = list_video_devices()
        if devices:
            print("Available video devices:")
            for dev in devices:
                print(f"  {dev}")
        else:
            print("No video devices found (non-Linux OS or no /dev/video* entries).")
        sys.exit(0)

    print(f"Loading model from: {args.engine}")
    model = load_model(args.engine)

    run_camera_loop(
        source=args.source,
        model=model,
        config={
            "gstreamer_template": args.template,
            "conf": args.conf,
            "record": args.record,
            "api_url": args.api_url,
            "drone_lat": args.drone_lat,
            "drone_lon": args.drone_lon,
            "drone_alt": args.drone_alt,
            "drone_heading": args.drone_heading,
            "fuel_type_id": args.fuel_type,
            "slope_deg": args.slope,
            "api_interval_s": args.api_interval,
        },
    )
