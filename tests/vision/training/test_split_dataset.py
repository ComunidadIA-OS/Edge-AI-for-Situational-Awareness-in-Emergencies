import os
import shutil
from pathlib import Path

import pytest

from vision.training.split_dataset import (
    split_temporal_aware,
    validate_split,
    _extract_group_prefix,
)


def _build_mini_dataset(base_dir: Path, prefixes: list[str], counts: list[int]) -> Path:
    images_dir = base_dir / "data" / "images" / "all"
    labels_dir = base_dir / "data" / "labels" / "all"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)

    for prefix, count in zip(prefixes, counts):
        for i in range(count):
            img_name = f"{prefix}_{i:04d}.jpg"
            (images_dir / img_name).touch()
            label_file = labels_dir / f"{prefix}_{i:04d}.txt"
            if "nofire" in prefix:
                label_file.write_text("")
            else:
                label_file.write_text(f"0 0.45{i%10} 0.56{i%8} 0.23 0.31\n")

    return base_dir / "data"


class TestExtractGroupPrefix:
    def test_flame_fire(self):
        assert _extract_group_prefix("flame_fire_00001.jpg") == "flame_fire_"

    def test_flame_nofire(self):
        assert _extract_group_prefix("flame_nofire_00005.jpg") == "flame_nofire_"

    def test_hanna(self):
        assert _extract_group_prefix("hanna_plot1_0003.jpg") == "hanna_plot1_"

    def test_no_digits_fallback(self):
        prefix = _extract_group_prefix("abc.jpg")
        assert len(prefix) > 0


class TestSplitTemporalAware:
    def test_validate_ratios_sum_to_one(self, tmp_path):
        data_dir = _build_mini_dataset(tmp_path, ["flame_fire"], [10])
        out_dir = tmp_path / "split_out"
        with pytest.raises(ValueError, match="Ratios must sum to 1.0"):
            split_temporal_aware(str(data_dir), str(out_dir), ratios=(0.7, 0.15, 0.1))

    def test_fewer_than_three_images(self, tmp_path):
        data_dir = _build_mini_dataset(tmp_path, ["flame_fire"], [2])
        out_dir = tmp_path / "split_out"
        with pytest.raises(ValueError, match="Cannot split fewer than 3 images"):
            split_temporal_aware(str(data_dir), str(out_dir))

    def test_temporal_split_preserves_order(self, tmp_path):
        data_dir = _build_mini_dataset(tmp_path, ["frame"], [10])
        out_dir = tmp_path / "split_out"
        stats = split_temporal_aware(str(data_dir), str(out_dir))

        train_dir = out_dir / "images" / "train"
        val_dir = out_dir / "images" / "val"
        test_dir = out_dir / "images" / "test"

        train_imgs = sorted(f.name for f in train_dir.glob("*.jpg"))
        val_imgs = sorted(f.name for f in val_dir.glob("*.jpg"))
        test_imgs = sorted(f.name for f in test_dir.glob("*.jpg"))

        assert len(train_imgs) == 7
        assert "frame_0000.jpg" in train_imgs
        assert "frame_0006.jpg" in train_imgs

        assert "frame_0007.jpg" in val_imgs
        assert "frame_0008.jpg" in test_imgs
        assert "frame_0009.jpg" in test_imgs

    def test_multi_group_no_leakage(self, tmp_path):
        data_dir = _build_mini_dataset(tmp_path, ["flame_fire", "hanna_plot1"], [10, 5])
        out_dir = tmp_path / "split_out"
        split_temporal_aware(str(data_dir), str(out_dir))

        train_imgs = set(f.name for f in (out_dir / "images" / "train").glob("*.jpg"))
        val_imgs = set(f.name for f in (out_dir / "images" / "val").glob("*.jpg"))
        test_imgs = set(f.name for f in (out_dir / "images" / "test").glob("*.jpg"))

        assert len(train_imgs & val_imgs) == 0
        assert len(train_imgs & test_imgs) == 0
        assert len(val_imgs & test_imgs) == 0

    def test_symlink_fallback_copy(self, tmp_path, monkeypatch):
        data_dir = _build_mini_dataset(tmp_path, ["flame_fire"], [5])
        out_dir = tmp_path / "split_out"

        original_symlink = os.symlink
        monkeypatch.setattr(os, "symlink", lambda src, dst: (_ for _ in ()).throw(OSError("forced")))

        stats = split_temporal_aware(str(data_dir), str(out_dir))

        train_dir = out_dir / "images" / "train"
        imgs = list(train_dir.glob("*.jpg"))
        assert len(imgs) > 0
        assert not imgs[0].is_symlink()

        os.symlink = original_symlink

    def test_output_structure(self, tmp_path):
        data_dir = _build_mini_dataset(tmp_path, ["flame_fire", "flame_nofire"], [5, 3])
        out_dir = tmp_path / "split_out"
        split_temporal_aware(str(data_dir), str(out_dir))

        assert (out_dir / "images" / "train").exists()
        assert (out_dir / "images" / "val").exists()
        assert (out_dir / "images" / "test").exists()
        assert (out_dir / "labels" / "train").exists()
        assert (out_dir / "labels" / "val").exists()
        assert (out_dir / "labels" / "test").exists()

        assert len(list((out_dir / "images" / "train").glob("*.jpg"))) > 0
        assert len(list((out_dir / "labels" / "train").glob("*.txt"))) > 0

    def test_split_stats_dict(self, tmp_path):
        data_dir = _build_mini_dataset(tmp_path, ["flame_fire", "flame_nofire"], [10, 5])
        out_dir = tmp_path / "split_out"
        stats = split_temporal_aware(str(data_dir), str(out_dir))

        required_keys = [
            "train", "val", "test",
            "train_fire", "val_fire", "test_fire",
            "train_nofire", "val_nofire", "test_nofire",
        ]
        for key in required_keys:
            assert key in stats, f"Missing key '{key}' in stats"

        total = stats["train"] + stats["val"] + stats["test"]
        assert total == 15

    def test_single_image_group_to_train(self, tmp_path):
        data_dir = _build_mini_dataset(tmp_path, ["group_a", "group_b", "group_c"], [1, 1, 20])
        out_dir = tmp_path / "split_out"
        stats = split_temporal_aware(str(data_dir), str(out_dir))

        train_dir = out_dir / "images" / "train"
        train_imgs = set(f.name for f in train_dir.glob("*.jpg"))
        assert "group_a_0000.jpg" in train_imgs
        assert "group_b_0000.jpg" in train_imgs


class TestValidateSplit:
    def test_validate_split_no_leakage(self, tmp_path):
        data_dir = _build_mini_dataset(tmp_path, ["flame_fire", "flame_nofire"], [10, 5])
        out_dir = tmp_path / "split_out"
        split_temporal_aware(str(data_dir), str(out_dir))

        result = validate_split(str(out_dir))
        assert result["valid"] is True
        assert result["leakage_detected"] is False

    def test_validate_split_detects_leakage(self, tmp_path):
        data_dir = _build_mini_dataset(tmp_path, ["flame_fire"], [10])
        out_dir = tmp_path / "split_out"
        split_temporal_aware(str(data_dir), str(out_dir))

        train_file = next((out_dir / "images" / "train").glob("*.jpg"))
        val_dir = out_dir / "images" / "val"
        shutil.copy2(str(train_file), str(val_dir / train_file.name))

        result = validate_split(str(out_dir))
        assert result["leakage_detected"] is True
        assert result["valid"] is False

    def test_validate_split_detects_orphans(self, tmp_path):
        data_dir = _build_mini_dataset(tmp_path, ["flame_fire"], [5])
        out_dir = tmp_path / "split_out"
        split_temporal_aware(str(data_dir), str(out_dir))

        orphan_jpg = out_dir / "images" / "train" / "orphan.jpg"
        orphan_jpg.touch()

        result = validate_split(str(out_dir))
        assert result["valid"] is False
        issues_text = " ".join(result["issues"])
        assert "orphan" in issues_text.lower()

    def test_validate_split_empty_split(self, tmp_path):
        data_dir = _build_mini_dataset(tmp_path, ["flame_fire"], [3])
        out_dir = tmp_path / "split_out"
        stats = split_temporal_aware(str(data_dir), str(out_dir))

        assert stats["test"] > 0 or stats["val"] > 0

    def test_class_distribution_keys(self, tmp_path):
        data_dir = _build_mini_dataset(tmp_path, ["flame_fire", "flame_nofire"], [10, 5])
        out_dir = tmp_path / "split_out"
        split_temporal_aware(str(data_dir), str(out_dir))

        result = validate_split(str(out_dir))
        dist = result["class_distribution"]
        for split_name in ["train", "val", "test"]:
            assert split_name in dist
            assert "fire" in dist[split_name]
            assert "nofire" in dist[split_name]
