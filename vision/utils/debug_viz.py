from pathlib import Path

import numpy as np
import cv2


def create_debug_overlay(
    jpg_path: str,
    celsius: np.ndarray,
    mask: np.ndarray,
    bboxes: list[dict],
    output_path: str | None = None,
    footer_text: str | None = None,
) -> np.ndarray:
    """Build a rich HITL debug overlay from thermal data and bounding boxes.

    Returns a (H+30, W, 3) uint8 BGR composite image with heatmap overlay,
    bounding boxes, temperature legend, and footer bar.
    """
    jpg_file = Path(jpg_path)
    if not jpg_file.exists():
        raise ValueError(f"JPG not found: {jpg_path}")

    if celsius is None:
        raise ValueError("celsius array must not be None")

    if mask is None:
        raise ValueError("mask must not be None")

    if celsius.shape != mask.shape:
        raise ValueError(
            f"Shape mismatch: celsius {celsius.shape} vs mask {mask.shape}"
        )

    h, w = celsius.shape

    bg = cv2.imread(str(jpg_file))
    if bg.shape[0] != h or bg.shape[1] != w:
        bg = cv2.resize(bg, (w, h))

    celsius_norm = np.clip(celsius, 0, 200).astype(np.float32) / 200.0 * 255
    celsius_norm = celsius_norm.astype(np.uint8)
    heatmap = cv2.applyColorMap(celsius_norm, cv2.COLORMAP_INFERNO)

    overlay = bg.copy()
    active = mask > 0
    if active.any():
        overlay[active] = cv2.addWeighted(bg[active], 0.6, heatmap[active], 0.4, 0)

    for bbox in bboxes:
        x_min = int(bbox["x_min"])
        y_min = int(bbox["y_min"])
        x_max = int(bbox["x_max"])
        y_max = int(bbox["y_max"])
        fill_ratio = bbox["fill_ratio"]

        cv2.rectangle(overlay, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
        label = f"\U0001f525 {fill_ratio:.2f}"

        (tw, th), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
        )
        label_y = max(y_min - 3, 12)
        box_top = max(y_min - th - 5, 0)

        cv2.rectangle(
            overlay,
            (x_min, box_top),
            (x_min + tw, y_min),
            (0, 0, 0),
            -1,
        )
        cv2.putText(
            overlay,
            label,
            (x_min, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
        )

    bar_height = int(h * 0.6)
    y_start = int(h * 0.1)
    bar_x_start = w - 40
    bar_x_end = w - 10

    gradient = np.linspace(255, 0, bar_height, dtype=np.uint8).reshape(-1, 1)
    bar_colored = cv2.applyColorMap(gradient, cv2.COLORMAP_INFERNO)
    overlay[y_start:y_start + bar_height, bar_x_start:bar_x_end] = bar_colored

    cv2.rectangle(
        overlay,
        (bar_x_start, y_start),
        (bar_x_end, y_start + bar_height),
        (255, 255, 255),
        1,
    )

    cv2.putText(
        overlay,
        "200C",
        (bar_x_start - 5, y_start + 12),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        (255, 255, 255),
        1,
    )
    cv2.putText(
        overlay,
        "0C",
        (bar_x_start - 5, y_start + bar_height - 5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        (255, 255, 255),
        1,
    )

    canvas = np.full((h + 30, w, 3), 30, dtype=np.uint8)
    canvas[:h, :] = overlay
    canvas[h:, :] = (20, 20, 20)

    footer_info = footer_text or str(jpg_file.name)
    max_temp = np.nanmax(celsius)
    fire_px = int((mask > 0).sum())
    line = (
        f"  {footer_info}  |  Bboxes: {len(bboxes)}  |  "
        f"Fire px: {fire_px}  |  Max: {max_temp:.1f}C"
    )
    cv2.putText(
        canvas,
        line,
        (10, h + 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
    )

    if output_path is not None:
        success = cv2.imwrite(output_path, canvas)
        if not success:
            raise OSError(f"Failed to write debug overlay to: {output_path}")

    return canvas
