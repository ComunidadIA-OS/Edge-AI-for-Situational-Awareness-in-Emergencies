import os
from pathlib import Path

import pytest
import yaml

from vision.utils.config import get_aws_credentials, load_yaml_config, merge_configs, validate_schema


CONFIGS_DIR = Path(__file__).parents[3] / "configs"
FIRE_YAML = CONFIGS_DIR / "auto_label_fire.yaml"


def _fire_config_schema() -> dict:
    return {
        "auto_label": {
            "required": True,
            "type": dict,
            "children": {
                "absolute_threshold": {"required": True, "type": float},
                "gradient_threshold": {"required": True, "type": float},
                "min_area": {"required": True, "type": int},
                "max_aspect_ratio": {"required": True, "type": float},
                "dbscan_eps": {"required": True, "type": int},
                "dbscan_min_samples": {"required": True, "type": int},
                "max_bbox_ratio": {"required": True, "type": float},
                "min_fill_ratio": {"required": True, "type": float},
                "class_id": {"required": True, "type": int},
            },
        },
        "dataset": {"required": True, "type": dict},
        "output": {"required": True, "type": dict},
    }


class TestLoadYamlConfig:
    def test_loads_real_config_with_expected_keys(self):
        config = load_yaml_config(str(FIRE_YAML))
        assert "auto_label" in config
        assert "dataset" in config
        assert "output" in config

    def test_raises_filenotfound_for_missing_file(self):
        with pytest.raises(FileNotFoundError, match="nonexistent.yaml"):
            load_yaml_config("nonexistent.yaml")

    def test_empty_yaml_returns_empty_dict(self, tmp_path: Path):
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")
        config = load_yaml_config(str(empty_file))
        assert config == {}

    def test_returns_errors_for_non_mapping_yaml(self, tmp_path: Path):
        list_file = tmp_path / "list.yaml"
        list_file.write_text("- item1\n- item2\n")
        config = load_yaml_config(str(list_file))
        assert "_errors" in config
        assert "mapping" in config["_errors"][0]

    def test_valid_schema_returns_clean_config(self):
        config = load_yaml_config(str(FIRE_YAML), _fire_config_schema())
        assert "_errors" not in config

    def test_invalid_schema_returns_errors_with_config(self, tmp_path: Path):
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("auto_label:\n  absolute_threshold: 'not_a_float'\n")
        schema = {
            "auto_label": {
                "required": True,
                "type": dict,
                "children": {"absolute_threshold": {"required": True, "type": float}},
            }
        }
        config = load_yaml_config(str(bad_yaml), schema)
        assert "_errors" in config
        assert len(config["_errors"]) > 0
        assert "auto_label" in config

    def test_missing_required_key_returns_errors_with_config(self, tmp_path: Path):
        partial = tmp_path / "partial.yaml"
        partial.write_text("dataset:\n  name: test\n")
        config = load_yaml_config(str(partial), _fire_config_schema())
        assert "_errors" in config
        assert any("auto_label" in e for e in config["_errors"])


class TestValidateSchema:
    def test_valid_config_returns_empty_list(self):
        config = yaml.safe_load(FIRE_YAML.read_text(encoding="utf-8"))
        errors = validate_schema(config, _fire_config_schema())
        assert errors == []

    def test_missing_required_key_returns_error(self):
        errors = validate_schema({}, {"key": {"required": True, "type": str}})
        assert len(errors) == 1
        assert "key" in errors[0]

    def test_missing_optional_key_is_ignored(self):
        errors = validate_schema({}, {"key": {"required": False, "type": str}})
        assert errors == []

    def test_type_mismatch_returns_error(self):
        errors = validate_schema({"key": 42}, {"key": {"required": True, "type": str}})
        assert len(errors) == 1
        assert "str" in errors[0].lower() or "Type mismatch" in errors[0]

    def test_nested_validation(self):
        config = {"parent": {"child": 3.14}}
        schema = {
            "parent": {
                "required": True,
                "type": dict,
                "children": {"child": {"required": True, "type": int}},
            }
        }
        errors = validate_schema(config, schema)
        assert len(errors) == 1
        assert "parent.child" in errors[0]

    def test_list_item_type_checking(self):
        config = {"items": [1, 2, "three"]}
        schema = {"items": {"required": True, "type": list, "item_type": int}}
        errors = validate_schema(config, schema)
        assert len(errors) == 1
        assert "[2]" in errors[0]

    def test_float_accepts_int(self):
        config = {"val": 10}
        schema = {"val": {"required": True, "type": float}}
        errors = validate_schema(config, schema)
        assert errors == []

    def test_int_rejects_float(self):
        config = {"val": 10.5}
        schema = {"val": {"required": True, "type": int}}
        errors = validate_schema(config, schema)
        assert len(errors) == 1


class TestGetAwsCredentials:
    def test_returns_tuple_from_env(self, monkeypatch):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "akid")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "sak")
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
        key, secret, region = get_aws_credentials()
        assert key == "akid"
        assert secret == "sak"
        assert region is None

    def test_returns_region_when_set(self, monkeypatch):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "akid")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "sak")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
        _, _, region = get_aws_credentials()
        assert region == "us-east-1"

    def test_raises_when_access_key_missing(self, monkeypatch):
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        with pytest.raises(RuntimeError, match="AWS credentials not found"):
            get_aws_credentials()

    def test_raises_when_secret_key_missing(self, monkeypatch):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "akid")
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        with pytest.raises(RuntimeError, match="AWS credentials not found"):
            get_aws_credentials()


class TestMergeConfigs:
    def test_merge_no_args_returns_empty_dict(self):
        result = merge_configs()
        assert result == {}

    def test_single_config_returns_copy(self):
        config = {"a": 1, "b": 2}
        result = merge_configs(config)
        assert result == config
        assert result is not config

    def test_merges_flat_dicts(self):
        result = merge_configs({"a": 1}, {"b": 2}, {"c": 3})
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_later_overrides_earlier(self):
        result = merge_configs({"a": 1}, {"a": 99})
        assert result == {"a": 99}

    def test_deep_merges_nested_dicts(self):
        a = {"nested": {"x": 1, "y": 2}}
        b = {"nested": {"y": 99, "z": 3}}
        result = merge_configs(a, b)
        assert result == {"nested": {"x": 1, "y": 99, "z": 3}}

    def test_deep_merge_replaces_non_dict_with_dict(self):
        a = {"nested": "string_value"}
        b = {"nested": {"new": "dict"}}
        result = merge_configs(a, b)
        assert result == {"nested": {"new": "dict"}}
