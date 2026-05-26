"""Direct boto3 launcher for SageMaker training — bypasses the sagemaker SDK.

Why: the sagemaker SDK pulls in pyiceberg which fails to build on Windows.
boto3 alone is enough to submit a training job; we just don't get the
high-level Estimator helpers.

Usage (env vars assumed to be set):
    python scripts/launch_sagemaker_boto3.py
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone

import boto3
import yaml

CONFIG_PATH = "configs/training.yaml"

IMAGE_URI = os.environ.get("SAGEMAKER_IMAGE_URI", "")
ROLE_ARN = os.environ.get("SAGEMAKER_ROLE_ARN", "")
S3_DATA = os.environ.get(
    "S3_DATA_PATH", "s3://xheimdall-datasets/yolo_dataset/"
)
S3_OUTPUT = os.environ.get(
    "S3_OUTPUT_PATH", "s3://xheimdall-models/training/"
)
REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def build_env(cfg: dict) -> dict[str, str]:
    m = cfg.get("model", {})
    return {
        "SM_MODEL_DIR": "/opt/ml/model",
        "SM_CHANNEL_TRAINING": "/opt/ml/input/data/training",
        "SM_OUTPUT_DATA_DIR": "/opt/ml/output/data",
        "YOLO_MODEL": str(m.get("name", "yolo26m.pt")),
        "YOLO_EPOCHS": str(m.get("epochs", 200)),
        "YOLO_BATCH": str(m.get("batch", 8)),
        "YOLO_IMGSZ": str(m.get("imgsz", 640)),
        "YOLO_PATIENCE": str(m.get("patience", 30)),
        "YOLO_LR0": str(m.get("lr0", 0.01)),
        "YOLO_DEVICE": str(m.get("device", "0")),
        "YOLO_NUM_WORKERS": str(m.get("num_workers", 8)),
        "YOLO_PRETRAINED": str(m.get("pretrained", True)).lower(),
        "YOLO_SAVE_PERIOD": str(m.get("save_period", 10)),
        "YOLO_OPTIMIZER": str(m.get("optimizer", "auto")),
        "YOLO_BOX": str(m.get("box", 7.5)),
        "YOLO_CLS": str(m.get("cls", 0.5)),
        "YOLO_DFL": str(m.get("dfl", 1.5)),
        "YOLO_MOMENTUM": str(m.get("momentum", 0.937)),
        "YOLO_WEIGHT_DECAY": str(m.get("weight_decay", 0.0005)),
    }


def _validate_env() -> None:
    missing = []
    if not IMAGE_URI:
        missing.append("SAGEMAKER_IMAGE_URI")
    if not ROLE_ARN:
        missing.append("SAGEMAKER_ROLE_ARN")
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "See scripts/README.md for setup instructions."
        )


def main() -> int:
    _validate_env()
    cfg = load_config()
    sm_cfg = cfg.get("sagemaker", {})

    instance_type = sm_cfg.get("instance_type", "ml.g5.xlarge")
    use_spot = bool(sm_cfg.get("use_spot", False))
    max_run = int(sm_cfg.get("max_run", 28800))
    max_wait = int(sm_cfg.get("max_wait", 36000)) if use_spot else None
    volume_size = int(sm_cfg.get("volume_size", 100))

    env_vars = build_env(cfg)

    # Pass W&B API key if available (never logged/committed)
    wandb_key = os.environ.get("WANDB_API_KEY")
    if wandb_key:
        env_vars["WANDB_API_KEY"] = wandb_key

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    job_name = f"xheimdall-yolo26m-{ts}"

    request = {
        "TrainingJobName": job_name,
        "AlgorithmSpecification": {
            "TrainingImage": IMAGE_URI,
            "TrainingInputMode": "File",
        },
        "RoleArn": ROLE_ARN,
        "InputDataConfig": [
            {
                "ChannelName": "training",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": S3_DATA,
                        "S3DataDistributionType": "FullyReplicated",
                    },
                },
                "InputMode": "File",
            }
        ],
        "OutputDataConfig": {"S3OutputPath": S3_OUTPUT},
        "ResourceConfig": {
            "InstanceType": instance_type,
            "InstanceCount": 1,
            "VolumeSizeInGB": volume_size,
        },
        "StoppingCondition": {"MaxRuntimeInSeconds": max_run},
        "Environment": env_vars,
        "EnableManagedSpotTraining": use_spot,
    }

    if use_spot:
        request["StoppingCondition"]["MaxWaitTimeInSeconds"] = max_wait
        request["CheckpointConfig"] = {
            "S3Uri": S3_OUTPUT.rstrip("/") + "/checkpoints/",
            "LocalPath": "/opt/ml/checkpoints/",
        }
        env_vars["OUTPUT_CHECKPOINT_S3"] = request["CheckpointConfig"]["S3Uri"]

    print(f"Launching training job: {job_name}")
    print(f"  Instance: {instance_type} ({'SPOT' if use_spot else 'ON-DEMAND'})")
    print(f"  Image: {IMAGE_URI}")
    print(f"  Data: {S3_DATA}")
    print(f"  Output: {S3_OUTPUT}")
    print(f"  Max runtime: {max_run}s")
    for k, v in env_vars.items():
        print(f"  ENV {k}={v}")

    sm = boto3.client("sagemaker", region_name=REGION)
    resp = sm.create_training_job(**request)

    print()
    print(f"Job ARN: {resp['TrainingJobArn']}")
    print(f"Console: https://{REGION}.console.aws.amazon.com/sagemaker/home?region={REGION}#/jobs/{job_name}")
    print(f"Logs:    aws logs tail /aws/sagemaker/TrainingJobs --log-stream-name-prefix {job_name} --follow --region {REGION}")

    print()
    print(f"To check status:")
    print(f"  aws sagemaker describe-training-job --training-job-name {job_name} --query TrainingJobStatus")
    return 0


if __name__ == "__main__":
    sys.exit(main())
