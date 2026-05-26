import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml


def _type_name(t: type) -> str:
    mapping: dict[type, str] = {
        dict: "dict",
        float: "float",
        int: "int",
        str: "str",
        list: "list",
        bool: "bool",
    }
    return mapping.get(t, t.__name__)


def _check_type(value: object, expected: type) -> bool:
    if expected is float:
        return isinstance(value, float | int) and not isinstance(value, bool)
    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, expected)


def validate_schema(config: dict[str, Any], schema: dict[str, Any], prefix: str = "") -> list[str]:
    errors: list[str] = []
    for key, rules in schema.items():
        path = f"{prefix}.{key}" if prefix else key
        required = rules.get("required", False)
        expected_type = rules.get("type")

        if key not in config:
            if required:
                errors.append(f"Missing required key: '{path}'")
            continue

        value = config[key]

        if expected_type is not None:
            if not _check_type(value, expected_type):
                errors.append(
                    f"Type mismatch for '{path}': expected {_type_name(expected_type)}, "
                    f"got {_type_name(type(value))}"
                )

        children = rules.get("children")
        if children is not None and isinstance(value, Mapping):
            errors.extend(validate_schema(dict(value), children, path))

        item_type = rules.get("item_type")
        if item_type is not None and isinstance(value, Sequence) and not isinstance(value, str):
            for idx, item in enumerate(value):
                if not _check_type(item, item_type):
                    errors.append(
                        f"Type mismatch for '{path}[{idx}]': expected {_type_name(item_type)}, "
                        f"got {_type_name(type(item))}"
                    )

    return errors


def load_yaml_config(path: str | Path, schema: dict[str, Any] | None = None) -> dict[str, Any]:
    filepath = Path(path)

    if not filepath.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")

    raw = filepath.read_text(encoding="utf-8")
    parsed: dict[str, Any] | list[Any] | None = yaml.safe_load(raw)

    if parsed is None:
        return {}

    if not isinstance(parsed, Mapping):
        return {"_errors": [f"YAML parse error: expected a mapping, got {_type_name(type(parsed))}"]}

    config: dict[str, Any] = dict(parsed)

    if schema is not None:
        schema_errors = validate_schema(config, schema)
        if schema_errors:
            return {"_errors": schema_errors, **config}

    return config


def get_aws_credentials() -> tuple[str, str, str | None]:
    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    region = os.environ.get("AWS_DEFAULT_REGION") or None

    if not access_key or not secret_key:
        raise RuntimeError(
            "AWS credentials not found. "
            "Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables."
        )

    return access_key, secret_key, region


def merge_configs(*configs: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}

    for config in configs:
        _deep_merge(merged, config)

    return merged


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> None:
    for key, value in overlay.items():
        if key in base and isinstance(base[key], Mapping) and isinstance(value, Mapping):
            _deep_merge(base[key], value)
        else:
            base[key] = value
