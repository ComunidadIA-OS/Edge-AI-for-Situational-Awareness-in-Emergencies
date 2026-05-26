"""SageMaker Training Job Launcher — XHeimdall.

Run locally to launch training jobs on AWS SageMaker.
Requires: pip install sagemaker boto3
"""

import os
import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_SAGEMAKER_AVAILABLE = False
try:
    import sagemaker
    from sagemaker.estimator import Estimator
    from sagemaker.inputs import TrainingInput
    _SAGEMAKER_AVAILABLE = True
except ImportError:
    pass


def load_training_config(config_path: str = "configs/training.yaml") -> dict:
    """Load training configuration from YAML file.

    Returns dict with model, augmentation, sagemaker, and dataset sections.
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Training config not found: {config_path}")

    with open(config_file) as f:
        return yaml.safe_load(f)


def build_hyperparameters(config: dict) -> dict[str, str]:
    """Convert training config dict to SageMaker environment variables dict.

    All values must be strings (SageMaker requirement).
    """
    model = config.get("model", {})

    hp: dict[str, str] = {}

    hp["YOLO_MODEL"] = str(model.get("name", "yolo26m.pt"))

    for key, default in [
        ("YOLO_EPOCHS", "200"),
        ("YOLO_BATCH", "8"),
        ("YOLO_IMGSZ", "640"),
        ("YOLO_PATIENCE", "30"),
        ("YOLO_LR0", "0.01"),
        ("YOLO_DEVICE", "0,1,2,3"),
        ("YOLO_NUM_WORKERS", "8"),
        ("YOLO_PRETRAINED", "true"),
        ("YOLO_SAVE_PERIOD", "10"),
    ]:
        yaml_key = key.lower().removeprefix("yolo_")
        val = model.get(yaml_key, default)
        hp[key] = str(val)

    return hp


def launch_training_job(
    image_uri: str,
    role_arn: str,
    s3_data_path: str,
    s3_output_path: str,
    instance_type: str = "ml.g5.12xlarge",
    instance_count: int = 1,
    use_spot: bool = True,
    hyperparameters: dict[str, str] | None = None,
    max_wait_seconds: int = 43200,
    checkpoint_s3_uri: str | None = None,
    volume_size: int = 100,
) -> str:
    """Launch a SageMaker Training Job.

    Args:
        image_uri: ECR image URI for the training container
        role_arn: IAM role ARN with SageMaker + S3 permissions
        s3_data_path: S3 URI for dataset (e.g., s3://bucket/yolo_dataset/)
        s3_output_path: S3 URI for model output
        instance_type: SageMaker instance type
        instance_count: Number of instances (always 1 for single-node)
        use_spot: Use spot instances for cost savings
        hyperparameters: Environment variables dict (keys → env vars in container)
        max_wait_seconds: Max wait time for spot fulfillment + training
        checkpoint_s3_uri: S3 URI for checkpoint storage (spot recovery)
        volume_size: EBS volume size in GB

    Returns:
        SageMaker training job name (str)

    Raises:
        RuntimeError: If sagemaker SDK is not installed
    """
    if not _SAGEMAKER_AVAILABLE:
        raise RuntimeError(
            "sagemaker SDK is not installed. Install with: pip install sagemaker boto3"
        )

    session = sagemaker.Session()

    if checkpoint_s3_uri is None and use_spot:
        checkpoint_s3_uri = s3_output_path.rstrip("/") + "/checkpoints/"

    environment = hyperparameters or {}
    if checkpoint_s3_uri:
        environment["OUTPUT_CHECKPOINT_S3"] = checkpoint_s3_uri

    estimator = Estimator(
        image_uri=image_uri,
        role=role_arn,
        instance_count=instance_count,
        instance_type=instance_type,
        output_path=s3_output_path,
        sagemaker_session=session,
        use_spot_instances=use_spot,
        max_wait=max_wait_seconds if use_spot else None,
        max_run=max_wait_seconds,
        checkpoint_s3_uri=checkpoint_s3_uri if use_spot else None,
        volume_size=volume_size,
        environment=environment,
    )

    train_input = TrainingInput(
        s3_data=s3_data_path,
        content_type="application/x-recordio",
        input_mode="File",
    )

    logger.info(f"Launching training job on {instance_type}" + (" (SPOT)" if use_spot else " (ON-DEMAND)"))
    logger.info(f"  Image: {image_uri}")
    logger.info(f"  Data: {s3_data_path}")
    logger.info(f"  Output: {s3_output_path}")
    logger.info(f"  Checkpoint: {checkpoint_s3_uri or 'disabled'}")
    logger.info(f"  Hyperparameters: {len(environment)} vars")

    estimator.fit({"training": train_input}, wait=False)

    job_name = estimator.latest_training_job.name
    logger.info(f"Training job launched (async): {job_name}")
    logger.info(f"Monitor: https://console.aws.amazon.com/sagemaker/home?region={session.boto_region_name}#/jobs/{job_name}")
    logger.info(f"Stream logs: aws logs tail /aws/sagemaker/TrainingJobs/{job_name} --follow")

    return job_name


def launch_from_config(
    config_path: str = "configs/training.yaml",
    image_uri: str | None = None,
    role_arn: str | None = None,
    s3_data_path: str | None = None,
    s3_output_path: str | None = None,
) -> str:
    """Convenience function: load config from YAML, then launch training job.

    Required env vars (can override config):
        SAGEMAKER_ROLE_ARN: IAM role ARN
        SAGEMAKER_IMAGE_URI: ECR image URI
        S3_DATA_PATH: S3 dataset path
        S3_OUTPUT_PATH: S3 model output path
    """
    config = load_training_config(config_path)
    sm_config = config.get("sagemaker", {})
    dataset_config = config.get("dataset", {})

    hp = build_hyperparameters(config)

    return launch_training_job(
        image_uri=image_uri or os.environ["SAGEMAKER_IMAGE_URI"],
        role_arn=role_arn or os.environ["SAGEMAKER_ROLE_ARN"],
        s3_data_path=s3_data_path or os.environ.get("S3_DATA_PATH", "s3://xheimdall-datasets/yolo_dataset/"),
        s3_output_path=s3_output_path or os.environ.get("S3_OUTPUT_PATH", "s3://xheimdall-models/training/"),
        instance_type=sm_config.get("instance_type", "ml.g5.12xlarge"),
        use_spot=sm_config.get("use_spot", True),
        max_wait_seconds=int(sm_config.get("max_wait", 43200)),
        hyperparameters=hp,
        volume_size=int(sm_config.get("volume_size", 100)),
    )
