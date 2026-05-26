"""Tests for export_tensorrt.py â€” runs without GPU/CUDA."""

import inspect

import pytest

from vision.inference.export_tensorrt import export_to_tensorrt, get_version_info, upload_engine_to_s3


class TestGetVersionInfo:
    """Version info collection works without GPU."""

    def test_returns_dict(self):
        info = get_version_info()
        assert isinstance(info, dict)

    def test_has_expected_keys(self):
        info = get_version_info()
        for key in ["tensorrt", "torch", "ultralytics", "cuda_available"]:
            assert key in info, f"Missing key: {key}"

    def test_all_values_are_strings(self):
        info = get_version_info()
        for key, val in info.items():
            assert isinstance(val, str), f"{key} should be str, got {type(val).__name__}"

    def test_missing_libs_show_not_installed(self):
        info = get_version_info()
        assert info["tensorrt"] == "not_installed"
        assert info["ultralytics"] == "not_installed"

    def test_every_call_fresh(self):
        a = get_version_info()
        b = get_version_info()
        assert a == b
        assert a is not b


class TestExportToTensorrtNoGPU:
    """export_to_tensorrt raises clear errors without GPU/CUDA."""

    def test_missing_model_raises_filenotfound(self, tmp_path):
        fake_path = str(tmp_path / "nonexistent.pt")
        with pytest.raises(FileNotFoundError, match="Model not found"):
            export_to_tensorrt(fake_path, str(tmp_path / "out.engine"))

    def test_missing_deps_raises_runtimeerror(self, tmp_path):
        dummy_pt = tmp_path / "dummy.pt"
        dummy_pt.write_bytes(b"PK\x03\x04")

        with pytest.raises(RuntimeError, match="Missing required dependency"):
            export_to_tensorrt(str(dummy_pt), str(tmp_path / "out.engine"))

    def test_default_args_are_callable(self):
        sig = inspect.signature(export_to_tensorrt)
        params = sig.parameters
        assert params["imgsz"].default == 640
        assert params["half"].default is True
        assert params["workspace"].default == 4
        assert params["dynamic"].default is False
        assert params["simplify"].default is True
        assert params["opset"].default == 17
        assert params["batch"].default == 1

    def test_missing_file_before_cuda_check(self, tmp_path):
        """FileNotFoundError should raise before CUDA check."""
        fake_path = str(tmp_path / "nonexistent.pt")
        with pytest.raises(FileNotFoundError):
            export_to_tensorrt(fake_path, str(tmp_path / "out.engine"))


class TestUploadEngineToS3:
    """S3 upload logic (mocked via missing file)."""

    def test_missing_file_returns_false(self, tmp_path):
        result = upload_engine_to_s3(str(tmp_path / "missing.engine"))
        assert result is False

    def test_function_signature(self):
        sig = inspect.signature(upload_engine_to_s3)
        params = list(sig.parameters.keys())
        assert "engine_path" in params
        assert "s3_uri" in params
        assert "region" in params

    def test_default_s3_uri(self):
        sig = inspect.signature(upload_engine_to_s3)
        default = sig.parameters["s3_uri"].default
        assert "xheimdall-models" in default
        assert "best_fp16.engine" in default

    def test_default_region(self):
        sig = inspect.signature(upload_engine_to_s3)
        assert sig.parameters["region"].default == "us-east-1"

    def test_returns_bool(self, tmp_path):
        result = upload_engine_to_s3(str(tmp_path / "missing.engine"))
        assert isinstance(result, bool)
