import logging
from pathlib import Path

import numpy as np
import cv2
from sklearn.cluster import DBSCAN, KMeans

from vision.io.thermal_io import read_celsius_tiff

logger = logging.getLogger(__name__)


def apply_absolute_threshold(celsius: np.ndarray, threshold: float) -> np.ndarray:
    if celsius is None:
        raise ValueError("celsius array must not be None")
    if threshold <= 0 or threshold > 1000:
        raise ValueError(f"threshold must be > 0 and <= 1000, got {threshold}")

    valid = ~np.isnan(celsius)
    mask = np.zeros(celsius.shape, dtype=np.uint8)
    mask[valid] = (celsius[valid] >= threshold).astype(np.uint8) * 255
    return mask


def apply_gradient_filter(
    thermal_img: np.ndarray,
    mask: np.ndarray,
    gradient_threshold: float = 40.0,
) -> np.ndarray:
    if thermal_img is None:
        raise ValueError("thermal_img must not be None")
    if mask is None:
        raise ValueError("mask must not be None")
    if thermal_img.shape != mask.shape:
        raise ValueError(
            f"Shape mismatch: thermal_img {thermal_img.shape} vs mask {mask.shape}"
        )

    gx = cv2.Sobel(thermal_img, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(thermal_img, cv2.CV_64F, 0, 1, ksize=3)
    magnitude = np.sqrt(gx**2 + gy**2)
    magnitude[np.isnan(magnitude)] = 0.0

    sharp_mask = (magnitude > gradient_threshold).astype(np.uint8) * 255
    result = cv2.bitwise_and(mask, sharp_mask)
    kernel = np.ones((3, 3), np.uint8)
    return cv2.morphologyEx(result, cv2.MORPH_CLOSE, kernel)


def apply_area_shape_filter(
    mask: np.ndarray,
    min_area: int = 50,
    max_aspect_ratio: float = 8.0,
) -> np.ndarray:
    if mask is None:
        raise ValueError("mask must not be None")

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    clean = np.zeros(mask.shape, dtype=np.uint8)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue

        x, y, w, h = cv2.boundingRect(cnt)
        aspect = max(w, h) / (min(w, h) + 1e-6)
        if aspect > max_aspect_ratio:
            continue

        cv2.drawContours(clean, [cnt], -1, 255, -1)

    return clean


def _create_bbox_dict(points: np.ndarray, img_w: int, img_h: int) -> dict:
    y_min, x_min = points.min(axis=0)
    y_max, x_max = points.max(axis=0)

    pad_x = int((x_max - x_min) * 0.05)
    pad_y = int((y_max - y_min) * 0.05)

    x_min = max(0, x_min - pad_x)
    y_min = max(0, y_min - pad_y)
    x_max = min(img_w - 1, x_max + pad_x)
    y_max = min(img_h - 1, y_max + pad_y)

    bbox_area = int((x_max - x_min) * (y_max - y_min))
    fill_ratio = len(points) / max(bbox_area, 1)

    return {
        "x_min": int(x_min),
        "y_min": int(y_min),
        "x_max": int(x_max),
        "y_max": int(y_max),
        "fill_ratio": float(fill_ratio),
        "area_px": bbox_area,
        "n_pixels": len(points),
    }


def _subdivide_cluster(
    points: np.ndarray,
    img_w: int,
    img_h: int,
    max_ratio: float,
    depth: int = 3,
) -> list[dict]:
    if depth == 0 or len(points) < 10:
        return [_create_bbox_dict(points, img_w, img_h)]

    bbox = _create_bbox_dict(points, img_w, img_h)
    if bbox["area_px"] / (img_w * img_h) <= max_ratio:
        return [bbox]

    km = KMeans(n_clusters=2, n_init=5, random_state=42)
    labels = km.fit_predict(points)

    results: list[dict] = []
    for k in range(2):
        sub = points[labels == k]
        if len(sub) > 5:
            results.extend(
                _subdivide_cluster(sub, img_w, img_h, max_ratio, depth - 1)
            )

    return results


def cluster_fire_regions(
    mask: np.ndarray,
    eps: int = 30,
    min_samples: int = 5,
    max_bbox_ratio: float = 0.4,
    img_w: int | None = None,
    img_h: int | None = None,
) -> list[dict]:
    if mask is None:
        raise ValueError("mask must not be None")

    points_y, points_x = np.where(mask > 0)
    points = np.column_stack([points_y, points_x])

    h, w = mask.shape
    if img_w is None:
        img_w = w
    if img_h is None:
        img_h = h

    if len(points) < min_samples:
        return []

    db = DBSCAN(eps=eps, min_samples=min_samples)
    labels = db.fit_predict(points)

    bboxes: list[dict] = []
    unique_labels = np.unique(labels)

    for label in unique_labels:
        if label == -1:
            continue
        cluster_pts = points[labels == label]

        sub_bboxes = _subdivide_cluster(
            cluster_pts, img_w, img_h, max_bbox_ratio
        )
        bboxes.extend(sub_bboxes)

    return bboxes


def bboxes_to_yolo(
    bboxes: list[dict],
    img_w: int,
    img_h: int,
    class_id: int = 0,
    min_fill_ratio: float = 0.15,
) -> str:
    lines: list[str] = []

    for bbox in bboxes:
        if bbox["fill_ratio"] < min_fill_ratio:
            continue

        x_center = ((bbox["x_min"] + bbox["x_max"]) / 2) / img_w
        y_center = ((bbox["y_min"] + bbox["y_max"]) / 2) / img_h
        width = (bbox["x_max"] - bbox["x_min"]) / img_w
        height = (bbox["y_max"] - bbox["y_min"]) / img_h

        x_center = max(0.0, min(1.0, x_center))
        y_center = max(0.0, min(1.0, y_center))
        width = max(0.0, min(1.0, width))
        height = max(0.0, min(1.0, height))

        lines.append(
            f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"
        )

    return "\n".join(lines)


REQUIRED_CONFIG_KEYS = [
    "absolute_threshold",
    "gradient_threshold",
    "min_area",
    "max_aspect_ratio",
    "dbscan_eps",
    "dbscan_min_samples",
    "max_bbox_ratio",
    "kmeans_subdivide_threshold",
    "min_fill_ratio",
    "class_id",
]


def process_single_tiff(
    tiff_path: str,
    config: dict,
    jpg_path: str | None = None,
    rgb_path: str | None = None,
) -> tuple[str, np.ndarray | None] | None:
    missing = [k for k in REQUIRED_CONFIG_KEYS if k not in config]
    if missing:
        raise ValueError(f"Missing required config key(s): {', '.join(missing)}")

    tiff_file = Path(tiff_path)
    if not tiff_file.exists():
        logger.warning("TIFF not found: %s", tiff_path)
        return None

    celsius = read_celsius_tiff(tiff_path)
    if celsius is None:
        return None

    step = "apply_absolute_threshold"
    try:
        mask = apply_absolute_threshold(celsius, config["absolute_threshold"])

        step = "apply_gradient_filter"
        mask = apply_gradient_filter(celsius, mask, config["gradient_threshold"])

        step = "apply_area_shape_filter"
        mask = apply_area_shape_filter(mask, config["min_area"], config["max_aspect_ratio"])

        step = "cluster_fire_regions"
        bboxes = cluster_fire_regions(
            mask,
            config["dbscan_eps"],
            config["dbscan_min_samples"],
            config["max_bbox_ratio"],
        )

        step = "bboxes_to_yolo"
        img_h, img_w = celsius.shape
        yolo_str = bboxes_to_yolo(
            bboxes, img_w, img_h, config["class_id"], config["min_fill_ratio"]
        )
    except Exception:
        logger.error("Pipeline step '%s' failed for: %s", step, tiff_path, exc_info=True)
        return None

    debug_img = _build_debug_overlay(
        celsius, mask, bboxes, img_w, img_h, jpg_path, rgb_path
    )

    logger.info(
        "Processed %s: %d bboxes, %d fire pixels, max %.1fC",
        tiff_file.name,
        len(bboxes),
        np.sum(mask > 0),
        np.nanmax(celsius),
    )

    return (yolo_str, debug_img)


def _build_debug_overlay(
    celsius: np.ndarray,
    mask: np.ndarray,
    bboxes: list[dict],
    img_w: int,
    img_h: int,
    jpg_path: str | None,
    rgb_path: str | None,
) -> np.ndarray | None:
    img = _load_overlay_image(jpg_path, rgb_path)
    if img is None:
        return None

    if img.shape[0] != img_h or img.shape[1] != img_w:
        img = cv2.resize(img, (img_w, img_h))

    for bbox in bboxes:
        pt1 = (bbox["x_min"], bbox["y_min"])
        pt2 = (bbox["x_max"], bbox["y_max"])
        cv2.rectangle(img, pt1, pt2, (0, 255, 0), 2)

    overlay = img.copy()
    red_mask = mask > 0
    overlay[red_mask, 2] = 255
    img = cv2.addWeighted(img, 0.7, overlay, 0.3, 0)

    footer = np.zeros((30, img_w, 3), dtype=np.uint8)
    img = np.vstack([img, footer])
    cv2.putText(
        img,
        f"{len(bboxes)} bboxes | max temp: {np.nanmax(celsius):.1f}C",
        (10, img.shape[0] - 6),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        1,
    )

    return img


def _load_overlay_image(
    jpg_path: str | None,
    rgb_path: str | None,
) -> np.ndarray | None:
    if jpg_path:
        jpg_file = Path(jpg_path)
        if jpg_file.exists():
            return cv2.imread(str(jpg_file))
        logger.warning("JPG not found: %s", jpg_path)

    if rgb_path:
        rgb_file = Path(rgb_path)
        if rgb_file.exists():
            return cv2.imread(str(rgb_file))
        logger.warning("RGB not found: %s", rgb_path)

    return None
