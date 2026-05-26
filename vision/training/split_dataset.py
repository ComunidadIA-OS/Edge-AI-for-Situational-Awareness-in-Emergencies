import os
import re
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def split_temporal_aware(
    data_dir: str,
    output_dir: str,
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15),
) -> dict:
    if abs(sum(ratios) - 1.0) > 1e-6:
        raise ValueError(f"Ratios must sum to 1.0, got {ratios} summing to {sum(ratios)}")

    images_dir = Path(data_dir) / "images" / "all"
    labels_dir = Path(data_dir) / "labels" / "all"

    image_names: set[str] = set()
    for pattern in ("*.jpg", "*.JPG", "*.jpeg", "*.JPEG", "*.png", "*.PNG"):
        for f in images_dir.glob(pattern):
            image_names.add(f.name)
    images = sorted(image_names)

    valid_images = []
    for img in images:
        stem = Path(img).stem
        label_file = labels_dir / f"{stem}.txt"
        if label_file.exists():
            valid_images.append(img)
        else:
            logger.warning("Orphan image (no label): %s", img)

    if len(valid_images) < 3:
        raise ValueError(f"Cannot split fewer than 3 images (got {len(valid_images)})")

    groups: dict[str, list[str]] = {}
    for img in valid_images:
        prefix = _extract_group_prefix(img)
        groups.setdefault(prefix, []).append(img)

    for prefix in groups:
        groups[prefix] = sorted(groups[prefix])

    train_files: list[str] = []
    val_files: list[str] = []
    test_files: list[str] = []

    for prefix, files in groups.items():
        n = len(files)
        n_train = max(1, int(n * ratios[0]))
        n_val = max(1, int(n * ratios[1])) if n >= 3 else 0

        train_files.extend(files[:n_train])
        val_files.extend(files[n_train:n_train + n_val])
        test_files.extend(files[n_train + n_val:])

    out_images = Path(output_dir) / "images"
    out_labels = Path(output_dir) / "labels"

    splits = [
        ("train", train_files),
        ("val", val_files),
        ("test", test_files),
    ]

    for split_name, files in splits:
        (out_images / split_name).mkdir(parents=True, exist_ok=True)
        (out_labels / split_name).mkdir(parents=True, exist_ok=True)

    for split_name, files in splits:
        for fname in files:
            src_img = images_dir / fname
            dst_img = out_images / split_name / fname
            label_name = Path(fname).stem + ".txt"
            src_label = labels_dir / label_name
            dst_label = out_labels / split_name / label_name

            _link_or_copy(src_img, dst_img)
            _link_or_copy(src_label, dst_label)

    stats = _compute_split_stats(data_dir, output_dir, valid_images)
    return stats


def validate_split(output_dir: str) -> dict:
    issues: list[str] = []
    images_dir = Path(output_dir) / "images"
    labels_dir = Path(output_dir) / "labels"

    split_names = ["train", "val", "test"]

    all_images: dict[str, set[str]] = {}
    for split_name in split_names:
        split_img_dir = images_dir / split_name
        split_lbl_dir = labels_dir / split_name
        if not split_img_dir.exists():
            issues.append(f"Missing images/{split_name}/ directory")
            continue
        if not split_lbl_dir.exists():
            issues.append(f"Missing labels/{split_name}/ directory")
            continue

        image_files = {f.name for f in split_img_dir.glob("*.jpg")} | {
            f.name for f in split_img_dir.glob("*.JPG")
        }
        label_files = {f.name for f in split_lbl_dir.glob("*.txt")}

        all_images[split_name] = image_files

        for img_name in image_files:
            stem = Path(img_name).stem
            expected_label = f"{stem}.txt"
            if expected_label not in label_files:
                issues.append(f"Missing label for {split_name}/{img_name}")

        for lbl_name in label_files:
            stem = Path(lbl_name).stem
            found = (f"{stem}.jpg" in image_files) or (f"{stem}.JPG" in image_files)
            if not found:
                issues.append(f"Missing image for {split_name}/{lbl_name}")

    leakage_detected = False
    for split_a in split_names:
        for split_b in split_names:
            if split_a >= split_b:
                continue
            overlap = all_images.get(split_a, set()) & all_images.get(split_b, set())
            if overlap:
                leakage_detected = True
                for img in overlap:
                    issues.append(f"Leakage: {img} found in both {split_a} and {split_b}")

    for split_name in split_names:
        imgs = all_images.get(split_name, set())
        if len(imgs) == 0:
            issues.append(f"Empty split: {split_name}")

    class_distribution = _compute_class_distribution(output_dir, split_names, all_images)

    return {
        "valid": len(issues) == 0,
        "leakage_detected": leakage_detected,
        "class_distribution": class_distribution,
        "issues": issues,
    }


def _extract_group_prefix(filename: str) -> str:
    stem = Path(filename).stem
    match = re.match(r"^(.+?)_\d+$", stem)
    if match:
        return match.group(1) + "_"
    return stem[:8]


def _has_fire(img_name: str, labels_dir: str) -> bool:
    label_path = Path(labels_dir) / "all" / (Path(img_name).stem + ".txt")
    if not label_path.exists():
        return False
    content = label_path.read_text().strip()
    return content != ""


def _link_or_copy(src: Path, dst: Path) -> None:
    try:
        os.symlink(src.resolve(), dst)
    except OSError:
        shutil.copy2(str(src), str(dst))


def _compute_split_stats(
    data_dir: str,
    output_dir: str,
    valid_images: list[str],
) -> dict:
    labels_dir = data_dir
    out_images_dir = Path(output_dir) / "images"
    split_names = ["train", "val", "test"]
    total = len(valid_images)

    result: dict[str, int] = {s: 0 for s in split_names}
    fire_keys = {f"{s}_fire" for s in split_names}
    nofire_keys = {f"{s}_nofire" for s in split_names}
    for k in fire_keys | nofire_keys:
        result[k] = 0

    for split_name in split_names:
        split_dir = out_images_dir / split_name
        if not split_dir.exists():
            continue
        seen: set[str] = set()
        for pattern in ("*.jpg", "*.JPG", "*.jpeg", "*.JPEG", "*.png", "*.PNG"):
            for img in split_dir.glob(pattern):
                if img.name in seen:
                    continue
                seen.add(img.name)
                is_fire = _has_fire(img.name, labels_dir)
                result[split_name] += 1
                if is_fire:
                    result[f"{split_name}_fire"] += 1
                else:
                    result[f"{split_name}_nofire"] += 1

    if result["train"] + result["val"] + result["test"] != total:
        logger.warning(
            "Split stats mismatch: found %d in splits vs %d input images",
            result["train"] + result["val"] + result["test"],
            total,
        )

    return result


def _compute_class_distribution(
    output_dir: str,
    split_names: list[str],
    all_images: dict[str, set[str]],
) -> dict:
    labels_dir = Path(output_dir) / "labels"
    distribution: dict[str, dict[str, int]] = {}

    for split_name in split_names:
        split_labels = labels_dir / split_name
        fire_count = 0
        nofire_count = 0
        for lbl in split_labels.glob("*.txt"):
            content = lbl.read_text().strip()
            if content:
                fire_count += 1
            else:
                nofire_count += 1
        distribution[split_name] = {
            "fire": fire_count,
            "nofire": nofire_count,
        }

    return distribution
