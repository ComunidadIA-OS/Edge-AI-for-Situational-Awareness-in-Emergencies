import json
import os
from pathlib import Path

import cv2
import numpy as np
import pytest
import tifffile
import yaml

from vision.training.prepare_data import (
    generate_data_yaml,
    process_dataset,
    _find_paired_jpg,
    _exclude_nadirplots,
)


class TestGenerateDataYaml:
    def test_valid_yaml_output(self, tmp_path):
        output = tmp_path / "data.yaml"
        generate_data_yaml(str(tmp_path), 1, ["fire"], str(output))
        assert output.exists()

        with open(output) as f:
            parsed = yaml.safe_load(f)

        assert parsed["path"] == str(tmp_path)
        assert parsed["train"] == "images/train"
        assert parsed["val"] == "images/val"
        assert parsed["test"] == "images/test"
        assert parsed["nc"] == 1
        assert parsed["names"] == {0: "fire"}
        assert parsed["download"] is None

    def test_nc_mismatch_raises_valueerror(self, tmp_path):
        output = tmp_path / "data.yaml"
        with pytest.raises(ValueError, match="nc \\(2\\) must equal len\\(names\\) \\(1\\)"):
            generate_data_yaml(str(tmp_path), 2, ["fire"], str(output))

    def test_multiple_classes(self, tmp_path):
        output = tmp_path / "data.yaml"
        generate_data_yaml(str(tmp_path), 3, ["fire", "smoke", "none"], str(output))
        assert output.exists()

        with open(output) as f:
            parsed = yaml.safe_load(f)

        assert parsed["nc"] == 3
        assert parsed["names"] == {0: "fire", 1: "smoke", 2: "none"}

    def test_output_path_relative(self, tmp_path):
        output = tmp_path / "data.yaml"
        generate_data_yaml(".", 1, ["fire"], str(output))
        assert output.exists()

        with open(output) as f:
            parsed = yaml.safe_load(f)
        assert parsed["path"] == "."

    def test_names_dict_format(self, tmp_path):
        output = tmp_path / "data.yaml"
        generate_data_yaml(str(tmp_path), 1, ["fire"], str(output))

        with open(output) as f:
            parsed = yaml.safe_load(f)

        names = parsed["names"]
        assert isinstance(names, dict)
        for k, v in names.items():
            assert isinstance(k, int)
            assert isinstance(v, str)


def _make_fire_tiff(path: Path) -> None:
    rng = np.random.default_rng(42)
    img = np.full((512, 640), 25.0, dtype=np.float32)
    img += rng.normal(0, 1.5, img.shape).astype(np.float32)
    hot_region = np.zeros((512, 640), dtype=bool)
    hot_region[100:250, 200:420] = True
    hot_y, hot_x = np.where(hot_region)
    for y, x in zip(hot_y, hot_x):
        dist = np.sqrt(((x - 310) / 150) ** 2 + ((y - 175) / 100) ** 2)
        temp = 400.0 - 200.0 * dist
        img[y, x] = max(temp, 80.0) + rng.normal(0, 3.0)
    tifffile.imwrite(str(path), img.astype(np.float32))


def _make_nofire_tiff(path: Path) -> None:
    rng = np.random.default_rng(99)
    img = np.full((512, 640), 25.0, dtype=np.float32)
    img += rng.normal(0, 2.0, img.shape).astype(np.float32)
    tifffile.imwrite(str(path), np.clip(img, 0, 50).astype(np.float32))


def _make_fake_jpg(path: Path) -> None:
    fake = np.zeros((512, 640, 3), dtype=np.uint8)
    cv2.imwrite(str(path), fake)


class TestProcessDataset:
    def test_process_dataset_missing_source_dir(self, tmp_path, sample_config_dict):
        config = {
            "output_dir": str(tmp_path / "out"),
            "sources": [
                {
                    "name": "Test",
                    "type": "flame",
                    "fire_dir": str(tmp_path / "nonexistent"),
                    "nofire_dir": str(tmp_path / "nonexistent2"),
                    "fire_jpg_dir": str(tmp_path / "nonexistent_jpg"),
                    "nofire_jpg_dir": str(tmp_path / "nonexistent_jpg2"),
                    "auto_label_config": sample_config_dict,
                }
            ],
        }
        report = process_dataset(config)
        assert report["total_images"] == 0
        assert len(report["errors"]) > 0

    def test_process_dataset_creates_output_structure(self, tmp_path, sample_config_dict):
        fire_dir = tmp_path / "fire_tiff"
        fire_dir.mkdir()
        jpg_dir = tmp_path / "fire_jpg"
        jpg_dir.mkdir()
        nofire_dir = tmp_path / "nofire_tiff"
        nofire_dir.mkdir()
        nofire_jpg_dir = tmp_path / "nofire_jpg"
        nofire_jpg_dir.mkdir()

        _make_fire_tiff(fire_dir / "00001.TIFF")
        _make_nofire_tiff(nofire_dir / "00001.TIFF")
        _make_fake_jpg(jpg_dir / "00001.JPG")
        _make_fake_jpg(nofire_jpg_dir / "00001.JPG")

        out_dir = tmp_path / "output"
        config = {
            "output_dir": str(out_dir),
            "sources": [
                {
                    "name": "Test",
                    "type": "flame",
                    "fire_dir": str(fire_dir),
                    "nofire_dir": str(nofire_dir),
                    "fire_jpg_dir": str(jpg_dir),
                    "nofire_jpg_dir": str(nofire_jpg_dir),
                    "auto_label_config": sample_config_dict,
                }
            ],
        }
        process_dataset(config)

        assert (out_dir / "images" / "all").exists()
        assert (out_dir / "labels" / "all").exists()
        assert (out_dir / "debug").exists()
        assert (out_dir / "data.yaml").exists()
        assert (out_dir / "processing_report.json").exists()

    def test_empty_source_logs_warning(self, tmp_path, sample_config_dict):
        fire_dir = tmp_path / "fire_tiff"
        fire_dir.mkdir()
        nofire_dir = tmp_path / "nofire_tiff"
        nofire_dir.mkdir()
        jpg_dir = tmp_path / "fire_jpg"
        jpg_dir.mkdir()
        nofire_jpg_dir = tmp_path / "nofire_jpg"
        nofire_jpg_dir.mkdir()

        out_dir = tmp_path / "output"
        config = {
            "output_dir": str(out_dir),
            "sources": [
                {
                    "name": "Empty",
                    "type": "flame",
                    "fire_dir": str(fire_dir),
                    "nofire_dir": str(nofire_dir),
                    "fire_jpg_dir": str(jpg_dir),
                    "nofire_jpg_dir": str(nofire_jpg_dir),
                    "auto_label_config": sample_config_dict,
                }
            ],
        }
        report = process_dataset(config)
        assert report["total_images"] == 0

    def test_process_dataset_minimal_run(self, tmp_path, sample_config_dict):
        fire_dir = tmp_path / "fire_tiff"
        fire_dir.mkdir()
        jpg_dir = tmp_path / "fire_jpg"
        jpg_dir.mkdir()
        nofire_dir = tmp_path / "nofire_tiff"
        nofire_dir.mkdir()
        nofire_jpg_dir = tmp_path / "nofire_jpg"
        nofire_jpg_dir.mkdir()

        _make_fire_tiff(fire_dir / "00001.TIFF")
        _make_fire_tiff(fire_dir / "00002.TIFF")
        _make_nofire_tiff(nofire_dir / "00001.TIFF")
        _make_fake_jpg(jpg_dir / "00001.JPG")
        _make_fake_jpg(jpg_dir / "00002.JPG")
        _make_fake_jpg(nofire_jpg_dir / "00001.JPG")

        out_dir = tmp_path / "output"
        config = {
            "output_dir": str(out_dir),
            "sources": [
                {
                    "name": "Test",
                    "type": "flame",
                    "fire_dir": str(fire_dir),
                    "nofire_dir": str(nofire_dir),
                    "fire_jpg_dir": str(jpg_dir),
                    "nofire_jpg_dir": str(nofire_jpg_dir),
                    "auto_label_config": sample_config_dict,
                }
            ],
        }
        report = process_dataset(config)

        assert report["total_images"] >= 2
        assert report["fire_images"] >= 1
        assert report["nofire_images"] >= 1
        assert report["total_bboxes"] > 0

        labels_all = out_dir / "labels" / "all"
        assert len(list(labels_all.glob("*.txt"))) >= 2

        images_all = out_dir / "images" / "all"
        assert len(list(images_all.glob("*.jpg"))) >= 2

        assert (out_dir / "processing_report.json").exists()
        assert (out_dir / "data.yaml").exists()

    def test_nadirplots_excluded(self, tmp_path, sample_config_dict):
        fire_dir = tmp_path / "fire_tiff"
        fire_dir.mkdir()
        nadir_dir = fire_dir / "NADIRPlots"
        nadir_dir.mkdir()
        jpg_dir = tmp_path / "fire_jpg"
        jpg_dir.mkdir()
        nofire_dir = tmp_path / "nofire_tiff"
        nofire_dir.mkdir()
        nofire_jpg_dir = tmp_path / "nofire_jpg"
        nofire_jpg_dir.mkdir()

        _make_fire_tiff(fire_dir / "00001.TIFF")
        _make_fire_tiff(nadir_dir / "excluded.TIFF")
        _make_nofire_tiff(nofire_dir / "00001.TIFF")
        _make_fake_jpg(jpg_dir / "00001.JPG")
        _make_fake_jpg(nofire_jpg_dir / "00001.JPG")

        out_dir = tmp_path / "output"
        config = {
            "output_dir": str(out_dir),
            "sources": [
                {
                    "name": "Test",
                    "type": "flame",
                    "fire_dir": str(fire_dir),
                    "nofire_dir": str(nofire_dir),
                    "fire_jpg_dir": str(jpg_dir),
                    "nofire_jpg_dir": str(nofire_jpg_dir),
                    "auto_label_config": sample_config_dict,
                }
            ],
        }
        report = process_dataset(config)

        labels_all = out_dir / "labels" / "all"
        label_files = list(labels_all.glob("*.txt"))
        for lf in label_files:
            assert "excluded" not in lf.name
            assert "NADIRPlots" not in str(lf)

        images_all = out_dir / "images" / "all"
        image_files = list(images_all.glob("*.jpg"))
        for imf in image_files:
            assert "excluded" not in imf.name


class TestFindPairedJpg:
    def test_finds_jpg(self, tmp_path):
        jpg_dir = tmp_path / "jpgs"
        jpg_dir.mkdir()
        (jpg_dir / "00001.JPG").touch()
        tiff = tmp_path / "00001.TIFF"
        tiff.touch()
        result = _find_paired_jpg(tiff, jpg_dir, "00001")
        assert result is not None
        assert result.name == "00001.JPG"

    def test_finds_lowercase(self, tmp_path):
        jpg_dir = tmp_path / "jpgs"
        jpg_dir.mkdir()
        (jpg_dir / "00001.jpg").touch()
        tiff = tmp_path / "00001.TIFF"
        tiff.touch()
        result = _find_paired_jpg(tiff, jpg_dir, "00001")
        assert result is not None
        assert result.suffix.lower() == ".jpg"

    def test_missing_dir_returns_none(self):
        result = _find_paired_jpg(Path("x.TIFF"), Path("/nonexistent"), "x")
        assert result is None

    def test_no_match_returns_none(self, tmp_path):
        jpg_dir = tmp_path / "jpgs"
        jpg_dir.mkdir()
        (jpg_dir / "other.JPG").touch()
        tiff = tmp_path / "00001.TIFF"
        tiff.touch()
        result = _find_paired_jpg(tiff, jpg_dir, "00001")
        assert result is None


class TestExcludeNadirplots:
    def test_excludes_nadir_dir(self):
        files = [
            Path("data/NADIRPlots/a.TIFF"),
            Path("data/regular/b.TIFF"),
            Path("data/NadirPlots/c.TIFF"),
        ]
        result = _exclude_nadirplots(files)
        assert len(result) == 1
        assert result[0] == Path("data/regular/b.TIFF")

    def test_no_nadir_returns_all(self):
        files = [Path("a.TIFF"), Path("b.TIFF")]
        result = _exclude_nadirplots(files)
        assert len(result) == 2
