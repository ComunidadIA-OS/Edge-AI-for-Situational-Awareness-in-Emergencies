from pathlib import Path

import pytest
import yaml

from vision.training.launch_training import build_hyperparameters, launch_training_job, load_training_config


CONFIGS_DIR = Path(__file__).parents[3] / "configs"


class TestLoadTrainingConfig:
    def test_loads_real_config_with_all_sections(self):
        config = load_training_config(str(CONFIGS_DIR / "training.yaml"))
        assert "model" in config
        assert "augmentation" in config
        assert "sagemaker" in config
        assert "dataset" in config

    def test_model_section_has_expected_keys(self):
        config = load_training_config(str(CONFIGS_DIR / "training.yaml"))
        model = config["model"]
        assert model["name"] == "yolo26m.pt"
        assert model["epochs"] == 200
        assert model["batch"] == 8

    def test_raises_filenotfound_for_missing_file(self):
        with pytest.raises(FileNotFoundError, match="missing_config.yaml"):
            load_training_config("missing_config.yaml")

    def test_default_config_path_works_when_present(self):
        config = load_training_config()
        assert isinstance(config, dict)
        assert len(config) >= 4


class TestBuildHyperparameters:
    def test_all_values_are_strings(self):
        config = load_training_config(str(CONFIGS_DIR / "training.yaml"))
        hp = build_hyperparameters(config)
        for key, value in hp.items():
            assert isinstance(value, str), f"{key} should be str, got {type(value).__name__}"

    def test_has_all_required_keys(self):
        config = load_training_config(str(CONFIGS_DIR / "training.yaml"))
        hp = build_hyperparameters(config)
        required = [
            "YOLO_MODEL", "YOLO_EPOCHS", "YOLO_BATCH", "YOLO_IMGSZ",
            "YOLO_PATIENCE", "YOLO_LR0", "YOLO_DEVICE",
            "YOLO_NUM_WORKERS", "YOLO_PRETRAINED", "YOLO_SAVE_PERIOD",
        ]
        for key in required:
            assert key in hp, f"Missing key: {key}"

    def test_model_name_maps_from_yaml(self):
        config = load_training_config(str(CONFIGS_DIR / "training.yaml"))
        hp = build_hyperparameters(config)
        assert hp["YOLO_MODEL"] == "yolo26m.pt"

    def test_epochs_batch_from_yaml(self):
        config = load_training_config(str(CONFIGS_DIR / "training.yaml"))
        hp = build_hyperparameters(config)
        assert hp["YOLO_EPOCHS"] == "200"
        assert hp["YOLO_BATCH"] == "8"

    def test_empty_config_uses_defaults(self):
        config = {"model": {}}
        hp = build_hyperparameters(config)
        assert hp["YOLO_MODEL"] == "yolo26m.pt"
        assert hp["YOLO_EPOCHS"] == "200"
        assert hp["YOLO_PRETRAINED"] == "true"

    def test_missing_model_section_uses_defaults(self):
        config = {}
        hp = build_hyperparameters(config)
        assert hp["YOLO_MODEL"] == "yolo26m.pt"

    def test_custom_values_override_defaults(self):
        config = {"model": {"epochs": 999, "batch": 64, "name": "custom_model.pt"}}
        hp = build_hyperparameters(config)
        assert hp["YOLO_EPOCHS"] == "999"
        assert hp["YOLO_BATCH"] == "64"
        assert hp["YOLO_MODEL"] == "custom_model.pt"


class TestLaunchTrainingJobWithoutSDK:
    def test_raises_runtime_error_with_clear_message(self):
        with pytest.raises(RuntimeError, match="sagemaker SDK is not installed"):
            launch_training_job(
                image_uri="img",
                role_arn="arn",
                s3_data_path="s3://data",
                s3_output_path="s3://out",
            )

    def test_raises_runtime_error_with_spot(self):
        with pytest.raises(RuntimeError):
            launch_training_job(
                image_uri="img",
                role_arn="arn",
                s3_data_path="s3://data",
                s3_output_path="s3://out",
                use_spot=True,
                checkpoint_s3_uri="s3://checkpoints",
            )
