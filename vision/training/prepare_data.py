import os
import json
import shutil
import logging
from pathlib import Path

import cv2
import yaml

from vision.training.auto_label import process_single_tiff

logger = logging.getLogger(__name__)


def generate_data_yaml(
    dataset_path: str,
    nc: int,
    names: list[str],
    output_path: str,
) -> None:
    if nc != len(names):
        raise ValueError(f"nc ({nc}) must equal len(names) ({len(names)})")

    data = {
        "path": dataset_path,
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "nc": nc,
        "names": {i: name for i, name in enumerate(names)},
        "download": None,
    }

    with open(output_path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)


def process_dataset(dataset_config: dict) -> dict:
    output_dir = Path(dataset_config["output_dir"])
    images_dir = output_dir / "images" / "all"
    labels_dir = output_dir / "labels" / "all"
    debug_dir = output_dir / "debug"

    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    debug_dir.mkdir(parents=True, exist_ok=True)

    debug_enabled = dataset_config.get("debug_enabled", False)
    debug_every_n = dataset_config.get("debug_every_n", 10)

    fire_images = 0
    nofire_images = 0
    total_bboxes = 0
    errors: list[str] = []
    skipped: list[str] = []

    for source in dataset_config.get("sources", []):
        source_name = source.get("name", "unknown")
        logger.info("Processing source: %s", source_name)

        source_type = source.get("type", "")
        label_config = source.get("auto_label_config", {})

        if source_type == "flame":
            fire_images, nofire_images, total_bboxes, src_errors, src_skipped = (
                _process_flame_source(
                    source, images_dir, labels_dir, debug_dir,
                    debug_enabled, debug_every_n, label_config,
                    fire_images, nofire_images, total_bboxes,
                )
            )
            errors.extend(src_errors)
            skipped.extend(src_skipped)

        elif source_type == "hanna":
            fire_images, nofire_images, total_bboxes, src_errors, src_skipped = (
                _process_hanna_source(
                    source, images_dir, labels_dir, debug_dir,
                    debug_enabled, debug_every_n, label_config,
                    fire_images, nofire_images, total_bboxes,
                )
            )
            errors.extend(src_errors)
            skipped.extend(src_skipped)

        else:
            errors.append(f"Unknown source type '{source_type}' for '{source_name}'")

    total_images = fire_images + nofire_images

    output_dir_str = str(output_dir)
    generate_data_yaml(
        dataset_path=output_dir_str,
        nc=1,
        names=["fire"],
        output_path=os.path.join(output_dir_str, "data.yaml"),
    )

    avg_bboxes = total_bboxes / max(fire_images, 1)

    report = {
        "total_images": total_images,
        "fire_images": fire_images,
        "nofire_images": nofire_images,
        "total_bboxes": total_bboxes,
        "avg_bboxes_per_image": round(avg_bboxes, 2),
        "errors": errors,
        "skipped": skipped,
    }

    report_path = os.path.join(output_dir_str, "processing_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    if fire_images == 0:
        errors.append("WARNING: Zero fire images found across all sources")

    return report


def _process_flame_source(
    source: dict,
    images_dir: Path,
    labels_dir: Path,
    debug_dir: Path,
    debug_enabled: bool,
    debug_every_n: int,
    label_config: dict,
    fire_images: int,
    nofire_images: int,
    total_bboxes: int,
) -> tuple[int, int, int, list[str], list[str]]:
    fire_dir = Path(source.get("fire_dir", ""))
    nofire_dir = Path(source.get("nofire_dir", ""))
    fire_jpg_dir = Path(source.get("fire_jpg_dir", ""))
    nofire_jpg_dir = Path(source.get("nofire_jpg_dir", ""))
    errors: list[str] = []
    skipped: list[str] = []

    if not fire_dir.exists() and not nofire_dir.exists():
        errors.append(
            f"Neither fire_dir nor nofire_dir exist for FLAME source '{source.get('name')}'"
        )
        return fire_images, nofire_images, total_bboxes, errors, skipped

    if not fire_dir.exists():
        errors.append(f"fire_dir not found: {fire_dir}")
    else:
        fire_images, total_bboxes, src_skipped = _process_fire_tiffs(
            fire_dir, fire_jpg_dir, images_dir, labels_dir, debug_dir,
            debug_enabled, debug_every_n, label_config,
            "flame_fire", fire_images, total_bboxes,
        )
        skipped.extend(src_skipped)

    if not nofire_dir.exists():
        errors.append(f"nofire_dir not found: {nofire_dir}")
    else:
        nofire_images, src_skipped = _process_nofire_tiffs(
            nofire_dir, nofire_jpg_dir, images_dir, labels_dir,
            "flame_nofire", nofire_images,
        )
        skipped.extend(src_skipped)

    return fire_images, nofire_images, total_bboxes, errors, skipped


def _process_hanna_source(
    source: dict,
    images_dir: Path,
    labels_dir: Path,
    debug_dir: Path,
    debug_enabled: bool,
    debug_every_n: int,
    label_config: dict,
    fire_images: int,
    nofire_images: int,
    total_bboxes: int,
) -> tuple[int, int, int, list[str], list[str]]:
    thermal_dir = Path(source.get("thermal_dir", ""))
    jpg_dir = Path(source.get("jpg_dir", ""))
    stem_suffix_strip = source.get("stem_suffix_strip", "")
    errors: list[str] = []
    skipped: list[str] = []

    if not thermal_dir.exists():
        errors.append(
            f"thermal_dir not found for Hanna source '{source.get('name')}': {thermal_dir}"
        )
        return fire_images, nofire_images, total_bboxes, errors, skipped

    name_prefix = source.get("name", "hanna").replace(" ", "_").lower()
    tiff_files = sorted(
        list(thermal_dir.rglob("*.tif"))
        + list(thermal_dir.rglob("*.tiff"))
        + list(thermal_dir.rglob("*.TIF"))
        + list(thermal_dir.rglob("*.TIFF"))
    )

    if not tiff_files:
        errors.append(f"WARNING: Zero TIFFs found in Hanna source '{source.get('name')}'")
        return fire_images, nofire_images, total_bboxes, errors, skipped

    logger.info("Hanna source '%s': found %d TIFFs", source.get("name"), len(tiff_files))

    for i, tiff in enumerate(tiff_files):
        if (i + 1) % 50 == 0:
            logger.info("Progress: %d/%d", i + 1, len(tiff_files))

        result = process_single_tiff(str(tiff), label_config)
        if result is None:
            skipped.append(f"Failed to process {tiff.name}")
            continue

        yolo_str, _ = result
        tiff_stem = tiff.stem
        pair_stem = (
            tiff_stem[: -len(stem_suffix_strip)]
            if stem_suffix_strip and tiff_stem.endswith(stem_suffix_strip)
            else tiff_stem
        )
        out_name = f"{name_prefix}_{pair_stem}"

        paired = _find_paired_jpg(tiff, jpg_dir, pair_stem)
        if not paired:
            skipped.append(f"No JPG for Hanna {tiff.name} (looked for {pair_stem})")
            continue

        (labels_dir / f"{out_name}.txt").write_text(yolo_str)
        shutil.copy2(paired, images_dir / f"{out_name}.jpg")

        if yolo_str.strip():
            fire_images += 1
            total_bboxes += len(yolo_str.strip().split("\n"))
            if debug_enabled and fire_images % debug_every_n == 0:
                debug_result = process_single_tiff(
                    str(tiff), label_config, jpg_path=str(paired)
                )
                if debug_result is not None:
                    _, debug_img = debug_result
                    if debug_img is not None:
                        cv2.imwrite(str(debug_dir / f"{out_name}_debug.jpg"), debug_img)
        else:
            nofire_images += 1

    return fire_images, nofire_images, total_bboxes, errors, skipped


def _process_fire_tiffs(
    fire_dir: Path,
    jpg_dir: Path,
    images_dir: Path,
    labels_dir: Path,
    debug_dir: Path,
    debug_enabled: bool,
    debug_every_n: int,
    label_config: dict,
    prefix: str,
    fire_count: int,
    total_bbox_count: int,
) -> tuple[int, int, list[str]]:
    skipped: list[str] = []
    tiff_files = sorted(
        list(fire_dir.glob("*.TIFF")) + list(fire_dir.glob("*.tiff"))
    )
    tiff_files = _exclude_nadirplots(tiff_files)

    for i, tiff in enumerate(tiff_files):
        if (i + 1) % 50 == 0:
            logger.info("Progress: %d/%d", i + 1, len(tiff_files))

        result = process_single_tiff(str(tiff), label_config)
        if result is None:
            skipped.append(f"Failed to process fire TIFF {tiff.name}")
            continue

        yolo_str, _ = result
        stem = tiff.stem
        out_name = f"{prefix}_{stem}"
        (labels_dir / f"{out_name}.txt").write_text(yolo_str)

        paired = _find_paired_jpg(tiff, jpg_dir, stem)
        if not paired:
            skipped.append(f"No JPG for fire {tiff.name}")
            continue

        shutil.copy2(paired, images_dir / f"{out_name}.jpg")

        fire_count += 1
        if yolo_str.strip():
            total_bbox_count += len(yolo_str.strip().split("\n"))

        if debug_enabled and fire_count % debug_every_n == 0:
            debug_result = process_single_tiff(
                str(tiff), label_config, jpg_path=str(paired)
            )
            if debug_result is not None:
                _, debug_img = debug_result
                if debug_img is not None:
                    cv2.imwrite(str(debug_dir / f"{out_name}_debug.jpg"), debug_img)

    return fire_count, total_bbox_count, skipped


def _process_nofire_tiffs(
    nofire_dir: Path,
    jpg_dir: Path,
    images_dir: Path,
    labels_dir: Path,
    prefix: str,
    nofire_count: int,
) -> tuple[int, list[str]]:
    skipped: list[str] = []
    tiff_files = sorted(
        list(nofire_dir.glob("*.TIFF")) + list(nofire_dir.glob("*.tiff"))
    )
    tiff_files = _exclude_nadirplots(tiff_files)

    for tiff in tiff_files:
        stem = tiff.stem
        out_name = f"{prefix}_{stem}"

        paired = _find_paired_jpg(tiff, jpg_dir, stem)
        if not paired:
            skipped.append(f"No JPG for nofire {tiff.name}")
            continue

        (labels_dir / f"{out_name}.txt").write_text("")
        shutil.copy2(paired, images_dir / f"{out_name}.jpg")
        nofire_count += 1

    return nofire_count, skipped


def _find_paired_jpg(tiff_path: Path, jpg_dir: Path, stem: str) -> Path | None:
    if not jpg_dir.exists():
        return None

    for ext in (".JPG", ".jpg", ".jpeg", ".JPEG"):
        candidate = jpg_dir / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return None


def _exclude_nadirplots(files: list[Path]) -> list[Path]:
    return [f for f in files if "NADIRPLOTS" not in str(f).upper()]
