"""Video detection runner for xheimdall-yolo26m-20260525-101951.

Loads an Ultralytics-compatible YOLO weights file (.pt / .onnx / .engine),
runs it over a video source frame by frame, and writes an annotated MP4.
Optionally displays a live window.

Usage:
    python models/detect_video.py \
        --weights models/xheimdall-yolo26m-20260525-101951.pt \
        --source  models/#3)_IR_Video_4.MP4\
        --output output.mp4

    # Live camera + display:
    python models/detect_video.py \
        --weights models/xheimdall-yolo26m-20260525-101951.engine \
        --source 0 --show
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import cv2
import numpy as np

DEFAULT_WEIGHTS = "models/xheimdall-yolo26m-20260525-101951.pt"
DEFAULT_CLASSES = {0: "fire", 1: "smoke"}

logger = logging.getLogger("detect_video")


def open_source(source: str) -> cv2.VideoCapture:
    if source.isdigit():
        cap = cv2.VideoCapture(int(source))
    else:
        cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video source: {source}")
    return cap


def color_for(class_id: int) -> tuple[int, int, int]:
    palette = [(0, 0, 255), (0, 215, 255), (0, 255, 0), (255, 128, 0)]
    return palette[class_id % len(palette)]


def draw_detections(
    frame: np.ndarray,
    boxes_xyxy: np.ndarray,
    confs: np.ndarray,
    class_ids: np.ndarray,
    names: dict[int, str],
    fps: float,
) -> np.ndarray:
    for (x1, y1, x2, y2), conf, cid in zip(boxes_xyxy, confs, class_ids):
        c = color_for(int(cid))
        p1, p2 = (int(x1), int(y1)), (int(x2), int(y2))
        cv2.rectangle(frame, p1, p2, c, 2)
        label = f"{names.get(int(cid), str(int(cid)))} {conf:.2f}"
        (tw, th), bl = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        ly = p1[1] - 6 if p1[1] - 6 > th else p1[1] + th + 6
        cv2.rectangle(frame, (p1[0], ly - th - bl), (p1[0] + tw, ly + bl), c, -1)
        cv2.putText(frame, label, (p1[0], ly), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
    return frame


def run(args: argparse.Namespace) -> int:
    weights = Path(args.weights)
    if not weights.exists():
        logger.error("Weights not found: %s", weights)
        return 2

    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error("ultralytics is required. Install: pip install ultralytics")
        return 3

    logger.info("Loading weights: %s", weights)
    model = YOLO(str(weights))

    # Class names from the model if present, otherwise the project default.
    names: dict[int, str] = getattr(model, "names", None) or DEFAULT_CLASSES

    # Warm-up
    dummy = np.zeros((args.imgsz, args.imgsz, 3), dtype=np.uint8)
    model.predict(dummy, imgsz=args.imgsz, conf=args.conf, iou=args.iou,
                  device=args.device, verbose=False)
    logger.info("Warm-up done. Classes: %s", names)

    cap = open_source(args.source)
    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    logger.info("Source: %s  %dx%d @ %.1f fps", args.source, src_w, src_h, src_fps)

    writer = None
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(args.output, fourcc, src_fps, (src_w, src_h))
        if not writer.isOpened():
            logger.error("Could not open video writer for %s", args.output)
            return 4
        logger.info("Writing annotated video to %s", args.output)

    frame_idx = 0
    t_start = time.perf_counter()
    fps_avg = 0.0
    fps_window: list[float] = []

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            t0 = time.perf_counter()
            results = model.predict(
                frame, imgsz=args.imgsz, conf=args.conf, iou=args.iou,
                device=args.device, verbose=False,
            )
            r = results[0]

            if r.boxes is not None and len(r.boxes) > 0:
                boxes = r.boxes.xyxy.cpu().numpy()
                confs = r.boxes.conf.cpu().numpy()
                cids = r.boxes.cls.cpu().numpy().astype(int)
            else:
                boxes = np.empty((0, 4))
                confs = np.empty((0,))
                cids = np.empty((0,), dtype=int)

            dt = time.perf_counter() - t0
            inst_fps = 1.0 / dt if dt > 0 else 0.0
            fps_window.append(inst_fps)
            if len(fps_window) > 30:
                fps_window.pop(0)
            fps_avg = sum(fps_window) / len(fps_window)

            frame = draw_detections(frame, boxes, confs, cids, names, fps_avg)

            if writer is not None:
                writer.write(frame)

            if args.show:
                cv2.imshow("xheimdall detect", frame)
                if (cv2.waitKey(1) & 0xFF) == ord("q"):
                    logger.info("Stopped by user (q).")
                    break

            frame_idx += 1
            if frame_idx % 30 == 0:
                logger.info("frame=%d  dets=%d  fps=%.1f",
                            frame_idx, len(boxes), fps_avg)
    finally:
        cap.release()
        if writer is not None:
            writer.release()
        if args.show:
            cv2.destroyAllWindows()

    total = time.perf_counter() - t_start
    logger.info("Done. %d frames in %.1fs (avg %.1f fps).",
                frame_idx, total, frame_idx / total if total > 0 else 0.0)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Heimdall video detection runner")
    p.add_argument("--weights", default=DEFAULT_WEIGHTS,
                   help=f"Path to YOLO weights (.pt/.onnx/.engine). Default: {DEFAULT_WEIGHTS}")
    p.add_argument("--source", default="models/3-WhiteHot.mov",
                   help="Video file path or camera index (e.g. 0).")
    p.add_argument("--output", default="output.mp4",
                   help="Annotated output video path. Use '' to disable.")
    p.add_argument("--imgsz", type=int, default=640, help="Inference image size.")
    p.add_argument("--conf", type=float, default=0.25, help="Confidence threshold.")
    p.add_argument("--iou", type=float, default=0.45, help="NMS IoU threshold.")
    p.add_argument("--device", default=None,
                   help="Torch device, e.g. '0', 'cuda:0', 'cpu'. Auto if omitted.")
    p.add_argument("--show", action="store_true", help="Display a live window.")
    return p.parse_args(argv)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    args = parse_args()
    if args.output == "":
        args.output = None
    sys.exit(run(args))
