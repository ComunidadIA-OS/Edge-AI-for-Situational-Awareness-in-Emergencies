import logging
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import tifffile

from vision.io.thermal_io import find_paired_rgb, read_celsius_tiff, read_irg_temperature


class TestReadCelsiusTiff:
    def test_valid_float32_tiff(self, tmp_path: Path):
        arr = np.array([[20.0, 30.0], [150.0, 200.0]], dtype=np.float32)
        tiff_path = tmp_path / "test_float32.tiff"
        tifffile.imwrite(str(tiff_path), arr)

        result = read_celsius_tiff(str(tiff_path))
        assert result is not None
        assert result.dtype == np.float32
        assert result.shape == (2, 2)
        assert abs(result[0, 0] - 20.0) < 0.01
        assert abs(result[1, 1] - 200.0) < 0.01

    def test_lzw_compressed_tiff(self, tmp_path: Path):
        arr = np.array([[25.5, 30.2], [180.1, 350.7]], dtype=np.float32)
        tiff_path = tmp_path / "test_lzw.tiff"
        tifffile.imwrite(str(tiff_path), arr, compression="lzw")

        result = read_celsius_tiff(str(tiff_path))
        assert result is not None
        assert result.dtype == np.float32
        assert result.shape == (2, 2)
        assert abs(result[0, 0] - 25.5) < 0.01
        assert abs(result[1, 1] - 350.7) < 0.01

    def test_float64_tiff_casts_to_float32(self, tmp_path: Path):
        arr = np.array([[10.0, 20.0], [30.0, 40.0]], dtype=np.float64)
        tiff_path = tmp_path / "test_float64.tiff"
        tifffile.imwrite(str(tiff_path), arr)

        result = read_celsius_tiff(str(tiff_path))
        assert result is not None
        assert result.dtype == np.float32
        assert result.shape == (2, 2)

    def test_uint16_returns_none_with_warning(self, tmp_path: Path, caplog):
        arr = np.array([[100, 200], [300, 400]], dtype=np.uint16)
        tiff_path = tmp_path / "test_uint16.tiff"
        tifffile.imwrite(str(tiff_path), arr)

        with caplog.at_level(logging.WARNING):
            result = read_celsius_tiff(str(tiff_path))

        assert result is None
        assert "cannot auto-calibrate uint16" in caplog.text

    def test_uint8_returns_none_with_warning(self, tmp_path: Path, caplog):
        arr = np.array([[10, 20], [30, 255]], dtype=np.uint8)
        tiff_path = tmp_path / "test_uint8.tiff"
        tifffile.imwrite(str(tiff_path), arr)

        with caplog.at_level(logging.WARNING):
            result = read_celsius_tiff(str(tiff_path))

        assert result is None
        assert "false-color" in caplog.text

    def test_unexpected_dtype_returns_none(self, tmp_path: Path, caplog):
        arr = np.array([[1, 2], [3, 4]], dtype=np.int32)
        tiff_path = tmp_path / "test_int32.tiff"
        tifffile.imwrite(str(tiff_path), arr)

        with caplog.at_level(logging.WARNING):
            result = read_celsius_tiff(str(tiff_path))

        assert result is None
        assert "unexpected dtype" in caplog.text

    def test_missing_file_returns_none(self, caplog):
        with caplog.at_level(logging.WARNING):
            result = read_celsius_tiff("nonexistent_file.TIFF")

        assert result is None
        assert "TIFF not found" in caplog.text

    def test_corrupt_file_returns_none(self, tmp_path: Path, caplog):
        corrupt_path = tmp_path / "corrupt.tiff"
        corrupt_path.write_bytes(b"This is not a valid TIFF file!")

        with caplog.at_level(logging.WARNING):
            result = read_celsius_tiff(str(corrupt_path))

        assert result is None
        assert "Corrupt TIFF" in caplog.text

    def test_all_nan_array_returns_none(self, tmp_path: Path, caplog):
        arr = np.full((3, 3), np.nan, dtype=np.float32)
        tiff_path = tmp_path / "test_nan.tiff"
        tifffile.imwrite(str(tiff_path), arr)

        with caplog.at_level(logging.WARNING):
            result = read_celsius_tiff(str(tiff_path))

        assert result is None
        assert "all-NaN" in caplog.text

    def test_all_identical_array_returns_none(self, tmp_path: Path, caplog):
        arr = np.zeros((3, 3), dtype=np.float32)
        tiff_path = tmp_path / "test_zeros.tiff"
        tifffile.imwrite(str(tiff_path), arr)

        with caplog.at_level(logging.WARNING):
            result = read_celsius_tiff(str(tiff_path))

        assert result is None
        assert "all-identical" in caplog.text

    def test_3d_tiff_takes_first_channel(self, tmp_path: Path, caplog):
        rng = np.random.default_rng(42)
        ch0 = rng.normal(50.0, 10.0, (4, 4)).astype(np.float32)
        ch1 = np.full((4, 4), 100.0, dtype=np.float32)
        ch2 = np.full((4, 4), 150.0, dtype=np.float32)
        arr = np.stack([ch0, ch1, ch2], axis=-1)
        tiff_path = tmp_path / "test_3d.tiff"
        tifffile.imwrite(str(tiff_path), arr)

        with caplog.at_level(logging.WARNING):
            result = read_celsius_tiff(str(tiff_path))

        assert result is not None
        assert result.dtype == np.float32
        assert result.shape == (4, 4)
        assert np.allclose(result, ch0)
        assert "multi-channel" in caplog.text

    def test_4d_tiff_returns_none(self, tmp_path: Path, caplog):
        arr = np.ones((2, 3, 3, 4), dtype=np.float32)
        tiff_path = tmp_path / "test_4d.tiff"
        tifffile.imwrite(str(tiff_path), arr)

        with caplog.at_level(logging.WARNING):
            result = read_celsius_tiff(str(tiff_path))

        assert result is None
        assert "expected 2D" in caplog.text

    def test_synthetic_celsius_array_shape(self, tmp_path: Path, synthetic_celsius_array):
        tiff_path = tmp_path / "synth.tiff"
        tifffile.imwrite(str(tiff_path), synthetic_celsius_array)

        result = read_celsius_tiff(str(tiff_path))
        assert result is not None
        assert result.shape == synthetic_celsius_array.shape
        assert result.dtype == np.float32


class TestReadIrgTemperature:
    def test_irg_missing_file_returns_none(self, caplog):
        with caplog.at_level(logging.WARNING):
            result = read_irg_temperature("nonexistent.irg")

        assert result is None
        assert "not found" in caplog.text

    def test_irg_no_tools_available_returns_none(self, tmp_path: Path, caplog):
        irg_path = tmp_path / "test.irg"
        irg_path.write_bytes(b"fake irg content")

        with patch("vision.io.thermal_io._read_irg_pyflir", return_value=None), \
             patch("vision.io.thermal_io._read_irg_exiftool", return_value=None), \
             caplog.at_level(logging.WARNING):
            result = read_irg_temperature(str(irg_path))

        assert result is None
        assert "Neither pyflir nor exiftool" in caplog.text

    def test_irg_pyflir_success(self, tmp_path: Path, caplog):
        irg_path = tmp_path / "test.irg"
        irg_path.write_bytes(b"fake irg content")
        expected = np.array([[30.0, 150.0], [200.0, 400.0]], dtype=np.float32)

        with patch("vision.io.thermal_io._read_irg_pyflir", return_value=expected), \
             patch("vision.io.thermal_io._read_irg_exiftool") as mock_exif, \
             caplog.at_level(logging.INFO):
            result = read_irg_temperature(str(irg_path))

        assert result is not None
        assert np.allclose(result, expected)
        mock_exif.assert_not_called()

    def test_irg_exiftool_fallback_success(self, tmp_path: Path, caplog):
        irg_path = tmp_path / "test.irg"
        irg_path.write_bytes(b"fake irg content")
        expected = np.array([[20.0, 100.0], [150.0, 300.0]], dtype=np.float32)

        with patch("vision.io.thermal_io._read_irg_pyflir", return_value=None), \
             patch("vision.io.thermal_io._read_irg_exiftool", return_value=expected), \
             caplog.at_level(logging.INFO):
            result = read_irg_temperature(str(irg_path))

        assert result is not None
        assert np.allclose(result, expected)


class TestFindPairedRgb:
    def test_flame_pattern_finds_rgb(self, tmp_path: Path):
        thermal_dir = tmp_path / "Fire" / "Thermal" / "Celsius TIFF"
        thermal_dir.mkdir(parents=True)
        rgb_dir = tmp_path / "Fire" / "RGB" / "Corrected FOV"
        rgb_dir.mkdir(parents=True)

        thermal_file = thermal_dir / "FIRE_0001.TIFF"
        thermal_file.write_bytes(b"dummy")
        rgb_file = rgb_dir / "FIRE_0001.JPG"
        rgb_file.write_bytes(b"dummy rgb")

        result = find_paired_rgb(str(thermal_file))
        assert result is not None
        assert Path(result).name == "FIRE_0001.JPG"

    def test_flame_pattern_with_jpg_lowercase(self, tmp_path: Path):
        thermal_dir = tmp_path / "Fire" / "Thermal" / "Celsius TIFF"
        thermal_dir.mkdir(parents=True)
        rgb_dir = tmp_path / "Fire" / "RGB" / "Corrected FOV"
        rgb_dir.mkdir(parents=True)

        thermal_file = thermal_dir / "00001.TIFF"
        thermal_file.write_bytes(b"dummy")
        rgb_file = rgb_dir / "00001.jpg"
        rgb_file.write_bytes(b"dummy rgb")

        result = find_paired_rgb(str(thermal_file))
        assert result is not None
        assert Path(result).name == "00001.jpg"

    def test_hanna_hammock_pattern_finds_rgb(self, tmp_path: Path):
        plot_dir = tmp_path / "plot1"
        thermal_dir = plot_dir / "geo_thermal_tiff_celsius"
        thermal_dir.mkdir(parents=True)
        rgb_dir = plot_dir / "raw_rgb_jpg"
        rgb_dir.mkdir(parents=True)

        thermal_file = thermal_dir / "IRX_0529_ref_geo.TIFF"
        thermal_file.write_bytes(b"dummy")
        rgb_file = rgb_dir / "IRX_0529_ref_geo.JPG"
        rgb_file.write_bytes(b"dummy rgb")

        result = find_paired_rgb(str(thermal_file))
        assert result is not None
        assert Path(result).stem == "IRX_0529_ref_geo"

    def test_hanna_hammock_pattern_jpg_lowercase(self, tmp_path: Path):
        plot_dir = tmp_path / "plot2"
        thermal_dir = plot_dir / "geo_thermal_tiff_celsius"
        thermal_dir.mkdir(parents=True)
        rgb_dir = plot_dir / "raw_rgb_jpg"
        rgb_dir.mkdir(parents=True)

        thermal_file = thermal_dir / "IRX_0530_ref_geo.TIFF"
        thermal_file.write_bytes(b"dummy")
        rgb_file = rgb_dir / "IRX_0530_ref_geo.jpg"
        rgb_file.write_bytes(b"dummy rgb")

        result = find_paired_rgb(str(thermal_file))
        assert result is not None
        assert Path(result).name == "IRX_0530_ref_geo.jpg"

    def test_generic_fallback_finds_rgb(self, tmp_path: Path):
        base = tmp_path / "dataset"
        thermal_sub = base / "some_thermal_subdir"
        thermal_sub.mkdir(parents=True)
        rgb_dir = base / "rgb"
        rgb_dir.mkdir()

        thermal_file = thermal_sub / "image_001.TIFF"
        thermal_file.write_bytes(b"dummy")
        rgb_file = rgb_dir / "image_001.JPG"
        rgb_file.write_bytes(b"dummy rgb")

        result = find_paired_rgb(str(thermal_file))
        assert result is not None
        assert Path(result).stem == "image_001"

    def test_no_paired_rgb_returns_none(self, tmp_path: Path, caplog):
        thermal_file = tmp_path / "orphan.TIFF"
        thermal_file.write_bytes(b"dummy")

        result = find_paired_rgb(str(thermal_file))
        assert result is None

    def test_missing_thermal_file_returns_none(self, caplog):
        with caplog.at_level(logging.WARNING):
            result = find_paired_rgb("nonexistent_thermal.TIFF")

        assert result is None
        assert "not found" in caplog.text

    def test_flame_pattern_no_rgb_dir_returns_none(self, tmp_path: Path):
        thermal_dir = tmp_path / "Fire" / "Thermal" / "Celsius TIFF"
        thermal_dir.mkdir(parents=True)
        thermal_file = thermal_dir / "FIRE_0002.TIFF"
        thermal_file.write_bytes(b"dummy")

        result = find_paired_rgb(str(thermal_file))
        assert result is None


class TestPlanckConversion:
    def test_planck_to_celsius_basic(self):
        from vision.io.thermal_io import _planck_to_celsius

        planck = {
            "PlanckR1": 15000.0,
            "PlanckR2": 0.0125,
            "PlanckB": 1400.0,
            "PlanckF": 1.0,
            "PlanckO": -7340.0,
        }
        raw = np.array([[14000, 15000], [16000, 17000]], dtype=np.uint16)
        celsius = _planck_to_celsius(raw, planck)
        assert celsius.dtype == np.float64
        assert celsius.shape == (2, 2)
        assert not np.all(np.isnan(celsius))

    def test_planck_handles_zero_raw(self):
        from vision.io.thermal_io import _planck_to_celsius

        planck = {
            "PlanckR1": 15000.0,
            "PlanckR2": 0.0125,
            "PlanckB": 1400.0,
            "PlanckF": 1.0,
            "PlanckO": -7340.0,
        }
        raw = np.zeros((2, 2), dtype=np.uint16)
        celsius = _planck_to_celsius(raw, planck)
        assert np.all(np.isnan(celsius))


class TestReadIrgPyflir:
    def test_pyflir_not_installed_returns_none(self):
        from vision.io.thermal_io import _read_irg_pyflir

        with patch.dict("sys.modules", {"pyflir": None}):
            result = _read_irg_pyflir("dummy.irg")
            assert result is None

    def test_pyflir_import_error_fallback(self):
        from vision.io.thermal_io import _read_irg_pyflir

        with patch("builtins.__import__", side_effect=ImportError):
            result = _read_irg_pyflir("dummy.irg")
            assert result is None

    def test_pyflir_extraction_failure(self, caplog):
        from vision.io.thermal_io import _read_irg_pyflir

        mock_flir = MagicMock()
        mock_flir.get_temperature.side_effect = RuntimeError("bad data")
        mock_pyflir = MagicMock()
        mock_pyflir.FLIRImage.return_value = mock_flir

        with patch.dict("sys.modules", {"pyflir": mock_pyflir}), \
             caplog.at_level(logging.WARNING):
            result = _read_irg_pyflir("dummy.irg")

        assert result is None
        assert "pyflir extraction failed" in caplog.text


class TestReadIrgExiftool:
    def test_exiftool_not_on_path_returns_none(self):
        from vision.io.thermal_io import _read_irg_exiftool

        with patch("shutil.which", return_value=None):
            result = _read_irg_exiftool("dummy.irg")
            assert result is None

    def test_exiftool_binary_extraction_error(self, caplog):
        from vision.io.thermal_io import _read_irg_exiftool

        with patch("shutil.which", return_value="/fake/exiftool"), \
             patch("vision.io.thermal_io._run_exiftool_binary", return_value=None), \
             caplog.at_level(logging.WARNING):
            result = _read_irg_exiftool("dummy.irg")

        assert result is None

    def test_exiftool_missing_planck_constants(self, caplog):
        from vision.io.thermal_io import _read_irg_exiftool

        with patch("shutil.which", return_value="/fake/exiftool"), \
             patch("vision.io.thermal_io._run_exiftool_binary", return_value=b"\x00\x01" * 4), \
             patch("vision.io.thermal_io._get_planck_constants", return_value=None), \
             caplog.at_level(logging.WARNING):
            result = _read_irg_exiftool("dummy.irg")

        assert result is None

    def test_exiftool_success_flat(self, caplog):
        from vision.io.thermal_io import _read_irg_exiftool

        raw_data = np.array([14000, 15000, 16000, 17000], dtype=np.uint16).tobytes()
        planck = {
            "PlanckR1": 15000.0,
            "PlanckR2": 0.0125,
            "PlanckB": 1400.0,
            "PlanckF": 1.0,
            "PlanckO": -7340.0,
        }
        metadata = {"width": 2, "height": 2}

        with patch("shutil.which", return_value="/fake/exiftool"), \
             patch("vision.io.thermal_io._run_exiftool_binary", return_value=raw_data), \
             patch("vision.io.thermal_io._get_planck_constants", return_value=planck), \
             patch("vision.io.thermal_io._get_image_metadata", return_value=metadata), \
             caplog.at_level(logging.INFO):
            result = _read_irg_exiftool("dummy.irg")

        assert result is not None
        assert result.dtype == np.float32
        assert result.shape == (2, 2)

    def test_exiftool_success_without_metadata_dimensions(self):
        from vision.io.thermal_io import _read_irg_exiftool

        raw_data = np.array([14000, 15000, 16000, 17000], dtype=np.uint16).tobytes()
        planck = {
            "PlanckR1": 15000.0,
            "PlanckR2": 0.0125,
            "PlanckB": 1400.0,
            "PlanckF": 1.0,
            "PlanckO": -7340.0,
        }

        with patch("shutil.which", return_value="/fake/exiftool"), \
             patch("vision.io.thermal_io._run_exiftool_binary", return_value=raw_data), \
             patch("vision.io.thermal_io._get_planck_constants", return_value=planck), \
             patch("vision.io.thermal_io._get_image_metadata", return_value={}):
            result = _read_irg_exiftool("dummy.irg")

        assert result is not None
        assert result.dtype == np.float32

    def test_exiftool_size_mismatch(self, caplog):
        from vision.io.thermal_io import _read_irg_exiftool

        raw_data = np.array([14000, 15000, 16000, 17000, 18000], dtype=np.uint16).tobytes()
        planck = {
            "PlanckR1": 15000.0,
            "PlanckR2": 0.0125,
            "PlanckB": 1400.0,
            "PlanckF": 1.0,
            "PlanckO": -7340.0,
        }
        metadata = {"width": 3, "height": 3}

        with patch("shutil.which", return_value="/fake/exiftool"), \
             patch("vision.io.thermal_io._run_exiftool_binary", return_value=raw_data), \
             patch("vision.io.thermal_io._get_planck_constants", return_value=planck), \
             patch("vision.io.thermal_io._get_image_metadata", return_value=metadata), \
             caplog.at_level(logging.WARNING):
            result = _read_irg_exiftool("dummy.irg")

        assert result is None


class TestRunExiftoolBinary:
    def test_success(self):
        from vision.io.thermal_io import _run_exiftool_binary

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b"\x00\x01\x02\x03"

        with patch("subprocess.run", return_value=mock_proc):
            result = _run_exiftool_binary("/fake/exiftool", "dummy.irg")
            assert result == b"\x00\x01\x02\x03"

    def test_nonzero_return_code(self):
        from vision.io.thermal_io import _run_exiftool_binary

        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = b""

        with patch("subprocess.run", return_value=mock_proc):
            result = _run_exiftool_binary("/fake/exiftool", "dummy.irg")
            assert result is None

    def test_empty_stdout(self):
        from vision.io.thermal_io import _run_exiftool_binary

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b""

        with patch("subprocess.run", return_value=mock_proc):
            result = _run_exiftool_binary("/fake/exiftool", "dummy.irg")
            assert result is None

    def test_timeout_expired(self, caplog):
        from vision.io.thermal_io import _run_exiftool_binary

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)), \
             caplog.at_level(logging.WARNING):
            result = _run_exiftool_binary("/fake/exiftool", "dummy.irg")
            assert result is None

    def test_os_error(self, caplog):
        from vision.io.thermal_io import _run_exiftool_binary

        with patch("subprocess.run", side_effect=OSError("not found")), \
             caplog.at_level(logging.WARNING):
            result = _run_exiftool_binary("/fake/exiftool", "dummy.irg")
            assert result is None


class TestGetPlanckConstants:
    def test_success(self):
        from vision.io.thermal_io import _get_planck_constants

        output = (
            "Planck R1 : 15000.0\n"
            "Planck R2 : 0.0125\n"
            "Planck B : 1400.0\n"
            "Planck F : 1.0\n"
            "Planck O : -7340.0\n"
        )
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = output

        with patch("subprocess.run", return_value=mock_proc):
            result = _get_planck_constants("/fake/exiftool", "dummy.irg")
            assert result is not None
            assert result["PlanckR1"] == 15000.0
            assert result["PlanckR2"] == 0.0125
            assert result["PlanckB"] == 1400.0
            assert result["PlanckF"] == 1.0
            assert result["PlanckO"] == -7340.0

    def test_nonzero_return_code(self):
        from vision.io.thermal_io import _get_planck_constants

        mock_proc = MagicMock()
        mock_proc.returncode = 1

        with patch("subprocess.run", return_value=mock_proc):
            result = _get_planck_constants("/fake/exiftool", "dummy.irg")
            assert result is None

    def test_incomplete_constants(self, caplog):
        from vision.io.thermal_io import _get_planck_constants

        output = "Planck R1 : 15000.0\n"
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = output

        with patch("subprocess.run", return_value=mock_proc), \
             caplog.at_level(logging.WARNING):
            result = _get_planck_constants("/fake/exiftool", "dummy.irg")
            assert result is None

    def test_timeout_expired(self, caplog):
        from vision.io.thermal_io import _get_planck_constants

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)), \
             caplog.at_level(logging.WARNING):
            result = _get_planck_constants("/fake/exiftool", "dummy.irg")
            assert result is None

    def test_value_error_parsing(self, caplog):
        from vision.io.thermal_io import _get_planck_constants

        output = "Planck R1 : not_a_number\nPlanck R2 : 0.0125\nPlanck B : 1400.0\nPlanck F : 1.0\nPlanck O : -7340.0\n"
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = output

        with patch("subprocess.run", return_value=mock_proc), \
             caplog.at_level(logging.WARNING):
            result = _get_planck_constants("/fake/exiftool", "dummy.irg")
            assert result is None


class TestGetImageMetadata:
    def test_success(self):
        from vision.io.thermal_io import _get_image_metadata

        output = "Image Width : 640\nImage Height : 512\n"
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = output

        with patch("subprocess.run", return_value=mock_proc):
            result = _get_image_metadata("/fake/exiftool", "dummy.irg")
            assert result == {"width": 640, "height": 512}

    def test_failure_returns_empty_dict(self):
        from vision.io.thermal_io import _get_image_metadata

        with patch("subprocess.run", side_effect=OSError):
            result = _get_image_metadata("/fake/exiftool", "dummy.irg")
            assert result == {}

    def test_nonzero_return_code(self):
        from vision.io.thermal_io import _get_image_metadata

        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""

        with patch("subprocess.run", return_value=mock_proc):
            result = _get_image_metadata("/fake/exiftool", "dummy.irg")
            assert result == {}


class TestFindPairedRgbEdgeCases:
    def test_hanna_no_rgb_parent_dir_returns_none(self, tmp_path: Path):
        plot_dir = tmp_path / "plot1"
        thermal_dir = plot_dir / "geo_thermal_tiff_celsius"
        thermal_dir.mkdir(parents=True)
        thermal_file = thermal_dir / "test.TIFF"
        thermal_file.write_bytes(b"dummy")

        result = find_paired_rgb(str(thermal_file))
        assert result is None

    def test_generic_no_rgb_sibling_returns_none(self, tmp_path: Path):
        base = tmp_path / "dataset"
        thermal_sub = base / "some_thermal_subdir"
        thermal_sub.mkdir(parents=True)
        thermal_file = thermal_sub / "img.TIFF"
        thermal_file.write_bytes(b"dummy")

        result = find_paired_rgb(str(thermal_file))
        assert result is None

    def test_flame_rgb_dir_exists_but_no_matching_file(self, tmp_path: Path):
        thermal_dir = tmp_path / "Fire" / "Thermal" / "Celsius TIFF"
        thermal_dir.mkdir(parents=True)
        rgb_dir = tmp_path / "Fire" / "RGB" / "Corrected FOV"
        rgb_dir.mkdir(parents=True)

        thermal_file = thermal_dir / "FIRE_0099.TIFF"
        thermal_file.write_bytes(b"dummy")
        rgb_file = rgb_dir / "OTHER_0001.JPG"
        rgb_file.write_bytes(b"dummy rgb")

        result = find_paired_rgb(str(thermal_file))
        assert result is None

    def test_hanna_case_insensitive_rgb_dir(self, tmp_path: Path):
        plot_dir = tmp_path / "plot1"
        thermal_dir = plot_dir / "geo_thermal_tiff_celsius"
        thermal_dir.mkdir(parents=True)
        rgb_dir = plot_dir / "Raw_RGB_JPG"
        rgb_dir.mkdir(parents=True)

        thermal_file = thermal_dir / "IMG_001.TIFF"
        thermal_file.write_bytes(b"dummy")
        rgb_file = rgb_dir / "IMG_001.JPG"
        rgb_file.write_bytes(b"dummy rgb")

        result = find_paired_rgb(str(thermal_file))
        assert result is not None
        assert Path(result).stem == "IMG_001"

    def test_generic_fallback_rgb_uppercase_dir(self, tmp_path: Path):
        base = tmp_path / "dataset"
        thermal_sub = base / "thermal_data"
        thermal_sub.mkdir(parents=True)
        rgb_dir = base / "RGB"
        rgb_dir.mkdir()

        thermal_file = thermal_sub / "img.TIFF"
        thermal_file.write_bytes(b"dummy")
        rgb_file = rgb_dir / "img.jpg"
        rgb_file.write_bytes(b"dummy rgb")

        result = find_paired_rgb(str(thermal_file))
        assert result is not None
        assert Path(result).stem == "img"
