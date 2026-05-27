# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Saúl Briceño, Carlos Langa, and ComunidadIA-OS contributors
#
# Part of Heimdall's vision-inference path — a derivative work of Ultralytics
# YOLO — licensed under AGPL-3.0. See LICENSE-AGPL-3.0.txt and NOTICE.

"""RGB + Thermal cross-check: validates auto-labeled thermal bboxes against paired RGB.

For each thermal-labeled bbox, FIRST checks the TIFF temperature -- if max > 200°C it's
definitively fire (thermal sees through smoke) and the bbox is kept regardless of RGB.
Only if temperature is borderline (< 200°C) does it check RGB for fire-colored pixels.

This prevents false negatives from smoke-obscured fires where RGB shows gray smoke
but LWIR thermal clearly shows > 200°C fire.

Uses low thresholds by design -- the RGB check is a SAFETY FILTER that only removes
clear false positives (hot rocks, warm bare ground). It does NOT require perfect
RGB fire visibility.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Fire color ranges in HSV (OpenCV: H[0-179], S[0-255], V[0-255])
# Red, orange, yellow -- conservative to avoid rejecting real fire
_FIRE_HSV_RANGES: list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]] = [
    # Red (low hue, includes wrap-around)
    ((0, 12), (50, 255), (50, 255)),
    # Orange
    ((8, 22), (60, 255), (60, 255)),
    # Yellow
    ((18, 35), (50, 255), (80, 255)),
    # Red wrap-around (170-179)
    ((170, 179), (50, 255), (50, 255)),
]

DEFAULT_MIN_FIRE_RATIO = 0.03
DEFAULT_MIN_CROP_AREA = 25
TIFF_TEMP_BYPASS = 200.0  # °C -- if max TIFF temp > this, keep bbox regardless of RGB


def fire_hsv_ratio(rgb_crop: np.ndarray) -> float:
    """Calculate the ratio of fire-colored pixels in an RGB image crop.

    Args:
        rgb_crop: BGR image crop (uint8, (H, W, 3))

    Returns:
        Float in [0.0, 1.0] -- fraction of pixels matching fire HSV ranges.
    """
    if rgb_crop.size == 0:
        return 0.0

    hsv = cv2.cvtColor(rgb_crop, cv2.COLOR_BGR2HSV)
    total = hsv.shape[0] * hsv.shape[1]
    if total == 0:
        return 0.0

    mask = np.zeros((hsv.shape[0], hsv.shape[1]), dtype=np.uint8)
    for (h_lo, h_hi), (s_lo, s_hi), (v_lo, v_hi) in _FIRE_HSV_RANGES:
        lower = np.array([h_lo, s_lo, v_lo], dtype=np.uint8)
        upper = np.array([h_hi, s_hi, v_hi], dtype=np.uint8)
        mask |= cv2.inRange(hsv, lower, upper)

    return float(np.count_nonzero(mask)) / total


def _tiff_max_temp_in_bbox(
    tiff_path: str | None, x1: int, y1: int, x2: int, y2: int,
) -> float:
    """Return max Celsius temperature in a bbox region of a TIFF.

    Returns 0.0 if TIFF cannot be read, region is empty, or tiff_path is None.
    """
    if tiff_path is None:
        return 0.0
    try:
        from vision.io.thermal_io import read_celsius_tiff
        celsius = read_celsius_tiff(tiff_path)
        if celsius is None:
            return 0.0
        crop = celsius[y1:y2, x1:x2]
        valid = crop[~np.isnan(crop)]
        if valid.size == 0:
            return 0.0
        return float(np.max(valid))
    except Exception:
        return 0.0


def cross_check_label(
    rgb_path: str,
    yolo_label: str,
    img_w: int,
    img_h: int,
    min_fire_ratio: float = DEFAULT_MIN_FIRE_RATIO,
    min_crop_area: int = DEFAULT_MIN_CROP_AREA,
    tiff_path: str | None = None,
    tiff_temp_bypass: float = TIFF_TEMP_BYPASS,
) -> tuple[str, dict]:
    """Cross-check a YOLO label file against paired RGB + TIFF temperature.

    For each bbox, FIRST checks the TIFF max temperature -- if > tiff_temp_bypass
    (200°C), the bbox is kept regardless of RGB (thermal sees through smoke).
    Otherwise, crops the RGB region and checks for fire-colored pixels.

    Args:
        rgb_path: Path to the paired RGB image
        yolo_label: YOLO format label string (one bbox per line)
        img_w: Image width in pixels
        img_h: Image height in pixels
        min_fire_ratio: Minimum fraction of fire-colored pixels to keep bbox
        min_crop_area: Minimum crop area in pixels (skip crops smaller than this)
        tiff_path: Path to the original Celsius TIFF (for temperature bypass)
        tiff_temp_bypass: °C threshold -- if max TIFF temp > this, auto-keep bbox

    Returns:
        (filtered_yolo_string, stats_dict) where stats_dict has:
            total_bboxes, kept_bboxes, removed_bboxes, temp_bypassed, bbox_details[]
    """
    rgb = cv2.imread(rgb_path)
    if rgb is None:
        logger.warning("Cannot read RGB image: %s", rgb_path)
        return yolo_label, {
            "total_bboxes": 0, "kept_bboxes": 0, "removed_bboxes": 0,
            "temp_bypassed": 0, "rgb_read_error": True, "bbox_details": [],
        }

    rgb_h, rgb_w = rgb.shape[:2]

    lines = [l.strip() for l in yolo_label.strip().split("\n") if l.strip()]
    if not lines:
        return yolo_label, {
            "total_bboxes": 0, "kept_bboxes": 0, "removed_bboxes": 0,
            "temp_bypassed": 0, "empty_label": True, "bbox_details": [],
        }

    kept_lines: list[str] = []
    details: list[dict] = []
    total_bboxes = len(lines)
    kept = 0
    removed = 0
    temp_bypassed = 0

    for line in lines:
        parts = line.split()
        if len(parts) != 5:
            logger.warning("Malformed YOLO line: %s", line)
            kept_lines.append(line)
            kept += 1
            continue

        cls_id, xc_str, yc_str, w_str, h_str = parts
        xc = float(xc_str)
        yc = float(yc_str)
        bw = float(w_str)
        bh = float(h_str)

        # Convert normalized -> pixel coordinates
        px = int((xc - bw / 2) * img_w)
        py = int((yc - bh / 2) * img_h)
        pw = int(bw * img_w)
        ph = int(bh * img_h)

        # Clamp to image bounds
        x1 = max(0, px)
        y1 = max(0, py)
        x2 = min(rgb_w, px + pw)
        y2 = min(rgb_h, py + ph)

        crop_w = x2 - x1
        crop_h = y2 - y1
        crop_area = crop_w * crop_h

        if crop_area < min_crop_area:
            details.append({
                "bbox": line, "fire_ratio": 0.0, "crop_area": crop_area,
                "kept": True, "reason": "crop_too_small_passed",
            })
            kept_lines.append(line)
            kept += 1
            continue

        # -- Temperature bypass: if TIFF max temp > 200°C, keep regardless of RGB --
        max_temp = _tiff_max_temp_in_bbox(tiff_path, x1, y1, x2, y2)
        if max_temp > tiff_temp_bypass:
            kept_lines.append(line)
            kept += 1
            temp_bypassed += 1
            details.append({
                "bbox": line, "fire_ratio": 0.0,
                "crop_area": crop_area, "kept": True,
                "reason": f"temp_bypass max_tiff={max_temp:.0f}C > {tiff_temp_bypass}C",
                "tiff_max_temp": round(max_temp, 1),
            })
            continue

        rgb_crop = rgb[y1:y2, x1:x2]
        ratio = fire_hsv_ratio(rgb_crop)

        if ratio >= min_fire_ratio:
            kept_lines.append(line)
            kept += 1
            details.append({
                "bbox": line, "fire_ratio": round(ratio, 4),
                "crop_area": crop_area, "kept": True,
                "tiff_max_temp": round(max_temp, 1),
            })
        else:
            removed += 1
            details.append({
                "bbox": line, "fire_ratio": round(ratio, 4),
                "crop_area": crop_area, "kept": False,
                "reason": f"fire_ratio={ratio:.4f} < {min_fire_ratio} (max_tiff={max_temp:.0f}C)",
                "tiff_max_temp": round(max_temp, 1),
            })

    return "\n".join(kept_lines), {
        "total_bboxes": total_bboxes,
        "kept_bboxes": kept,
        "removed_bboxes": removed,
        "temp_bypassed": temp_bypassed,
        "bbox_details": details,
    }


def cross_check_dataset(
    prepared_dir: str,
    flame_rgb_dir: str,
    flame_tiff_dir: str | None = None,
    img_w: int = 640,
    img_h: int = 512,
    min_fire_ratio: float = DEFAULT_MIN_FIRE_RATIO,
    tiff_temp_bypass: float = TIFF_TEMP_BYPASS,
) -> dict:
    """Cross-check all auto-labeled images in a prepared dataset against paired RGB + TIFF.

    Walks labels/all/, finds paired RGB and TIFF for FLAME fire images.
    Uses temperature bypass: if TIFF max temp > 200°C, keeps bbox regardless of RGB.
    No-fire images are left unchanged (they have empty labels).

    Args:
        prepared_dir: Path to prepared dataset root (contains labels/all/ and images/all/)
        flame_rgb_dir: Path to FLAME RGB directory (e.g., .../Fire/RGB/Corrected FOV/)
        flame_tiff_dir: Path to FLAME Celsius TIFF directory (for temperature bypass)
        img_w: Image width for YOLO coordinate denormalization
        img_h: Image height for YOLO coordinate denormalization
        min_fire_ratio: Minimum fire-colored pixel ratio to keep bbox
        tiff_temp_bypass: °C threshold -- if max TIFF temp > this, auto-keep bbox

    Returns:
        Report dict with keys:
            total_labels_checked, total_bboxes_before, total_bboxes_after,
            bboxes_removed, temp_bypassed, labels_modified, rgb_missing,
            tiff_missing, rgb_read_errors, per_label[]
    """
    labels_dir = Path(prepared_dir) / "labels" / "all"
    labels_backup_dir = Path(prepared_dir) / "labels" / "all_pre_crosscheck"
    rgb_dir = Path(flame_rgb_dir)
    tiff_dir = Path(flame_tiff_dir) if flame_tiff_dir else None

    if not labels_dir.exists():
        raise FileNotFoundError(f"Labels directory not found: {labels_dir}")
    if not rgb_dir.exists():
        raise FileNotFoundError(f"RGB directory not found: {rgb_dir}")

    label_files = sorted(labels_dir.glob("*.txt"))
    logger.info("Cross-checking %d label files against RGB at %s", len(label_files), rgb_dir)
    if tiff_dir:
        logger.info("Temperature bypass enabled: TIFF dir %s, threshold %.0f°C",
                     tiff_dir, tiff_temp_bypass)

    # Backup original labels
    labels_backup_dir.mkdir(exist_ok=True)
    for lf in label_files:
        backup = labels_backup_dir / lf.name
        if not backup.exists():
            backup.write_bytes(lf.read_bytes())

    total_checked = 0
    total_before = 0
    total_after = 0
    bboxes_removed = 0
    temp_bypassed_total = 0
    labels_modified = 0
    rgb_missing = 0
    tiff_missing = 0
    rgb_read_errors = 0
    per_label: list[dict] = []

    for label_file in label_files:
        name = label_file.stem  # e.g., "flame_fire_00001"

        # Only cross-check fire labels (nofire have empty files)
        if "nofire" in name or "no_fire" in name:
            continue
        if "_fire_" not in name:
            continue

        total_checked += 1

        # Extract original stem: "flame_fire_00001" -> "00001"
        parts = name.split("_")
        stem = parts[-1]

        # Find paired RGB
        rgb_candidates = list(rgb_dir.glob(f"{stem}.*"))
        if not rgb_candidates:
            logger.warning("No RGB pair found for %s (stem=%s)", name, stem)
            rgb_missing += 1
            per_label.append({"label": name, "status": "rgb_missing"})
            continue

        rgb_path = str(rgb_candidates[0])
        yolo_label = label_file.read_text().strip()

        # Find paired TIFF for temperature bypass
        tiff_path: str | None = None
        if tiff_dir:
            tiff_candidates = list(tiff_dir.glob(f"{stem}.*"))
            if tiff_candidates:
                tiff_path = str(tiff_candidates[0])
            else:
                tiff_missing += 1

        total_before += len(yolo_label.split("\n")) if yolo_label else 0

        filtered, stats = cross_check_label(
            rgb_path, yolo_label, img_w, img_h,
            min_fire_ratio=min_fire_ratio,
            tiff_path=tiff_path,
            tiff_temp_bypass=tiff_temp_bypass,
        )

        if stats.get("rgb_read_error"):
            rgb_read_errors += 1
            per_label.append({"label": name, "status": "rgb_read_error"})
            continue

        total_after += stats["kept_bboxes"]
        removed = stats["removed_bboxes"]
        bboxes_removed += removed
        bypassed = stats.get("temp_bypassed", 0)
        temp_bypassed_total += bypassed

        if removed > 0:
            labels_modified += 1
            label_file.write_text(filtered + "\n" if filtered else "")
            logger.info(
                "%s: %d/%d bboxes kept (%d removed, %d temp-bypassed)",
                name, stats["kept_bboxes"], stats["total_bboxes"], removed, bypassed,
            )
        else:
            logger.debug("%s: all %d bboxes confirmed", name, stats["total_bboxes"])

        per_label.append({
            "label": name,
            "status": "checked",
            "bboxes_before": stats["total_bboxes"],
            "bboxes_after": stats["kept_bboxes"],
            "bboxes_removed": removed,
            "temp_bypassed": bypassed,
            "details": stats.get("bbox_details", []),
        })

    report = {
        "total_labels_checked": total_checked,
        "total_bboxes_before": total_before,
        "total_bboxes_after": total_after,
        "bboxes_removed": bboxes_removed,
        "temp_bypassed": temp_bypassed_total,
        "labels_modified": labels_modified,
        "rgb_missing": rgb_missing,
        "tiff_missing": tiff_missing,
        "rgb_read_errors": rgb_read_errors,
        "bboxes_removed_pct": round(
            100 * bboxes_removed / max(total_before, 1), 1
        ),
        "labels_modified_pct": round(
            100 * labels_modified / max(total_checked, 1), 1
        ),
        "per_label": per_label,
    }

    report_path = Path(prepared_dir) / "cross_check_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info("=" * 60)
    logger.info("RGB+Thermal Cross-Check Complete")
    logger.info("  Labels checked: %d", total_checked)
    logger.info("  Bboxes before: %d", total_before)
    logger.info("  Bboxes after:  %d", total_after)
    logger.info("  Bboxes removed: %d (%.1f%%)", bboxes_removed, report["bboxes_removed_pct"])
    logger.info("  Temp bypassed: %d", temp_bypassed_total)
    logger.info("  Labels modified: %d (%.1f%%)", labels_modified, report["labels_modified_pct"])
    logger.info("  RGB missing: %d, TIFF missing: %d", rgb_missing, tiff_missing)
    logger.info("  Report: %s", report_path)
    logger.info("=" * 60)

    return report


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    import sys

    prepared = sys.argv[1] if len(sys.argv) > 1 else "data/prepared"
    rgb = sys.argv[2] if len(sys.argv) > 2 else (
        r"datasets/CVSubset/FLAME 3 CV Dataset (Sycan Marsh)/Fire/RGB/Corrected FOV"
    )
    tiff = sys.argv[3] if len(sys.argv) > 3 else (
        r"datasets/CVSubset/FLAME 3 CV Dataset (Sycan Marsh)/Fire/Thermal/Celsius TIFF"
    )

    report = cross_check_dataset(prepared, rgb, tiff)
    print(json.dumps(report, indent=2))
