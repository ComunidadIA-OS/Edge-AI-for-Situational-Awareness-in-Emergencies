"""Warm-restart launcher for XHeimdall Job 2 (precision pass).

Loads best.pt from a prior SageMaker training job, lowers LR 10x,
shortens schedule, disables mosaic/mixup, enables cosine LR.
Estimated mAP50-95 lift: 0.246 -> 0.28-0.33.

Assumes the training image at SAGEMAKER_IMAGE_URI has been rebuilt with the
patched train_sagemaker.py (supports SM_CHANNEL_PRETRAINED + augmentation
env vars). Recommended tag: :warm-restart-v1.

Channels:
  - training:    s3://xheimdall-datasets/yolo_dataset/
  - pretrained:  s3://xheimdall-models/warm-start/<JOB>/pretrained/best.pt

Usage:
  python scripts/launch_warm_restart.py --base-job <NAME> [--wait] [--dry-run]

Required env: SAGEMAKER_IMAGE_URI, SAGEMAKER_ROLE_ARN, AWS_*
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3

REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
IMAGE_URI = os.environ.get("SAGEMAKER_IMAGE_URI", "")
ROLE_ARN = os.environ.get("SAGEMAKER_ROLE_ARN", "")
S3_DATA = os.environ.get("S3_DATA_PATH", "s3://xheimdall-datasets/yolo_dataset/")
S3_OUTPUT_BUCKET = "xheimdall-models"
S3_WARMSTART_PREFIX = "warm-start"

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


JOB2_HYPERPARAMS = {
    # Schedule (the dominant change vs Job 1)
    "YOLO_LR0": "0.001",
    "YOLO_LRF": "0.01",
    "YOLO_COS_LR": "true",
    "YOLO_WARMUP_EPOCHS": "3.0",
    "YOLO_EPOCHS": "50",
    "YOLO_PATIENCE": "20",
    "YOLO_SAVE_PERIOD": "5",

    # Capacity (same as Job 1)
    "YOLO_IMGSZ": "1280",
    "YOLO_BATCH": "8",
    "YOLO_NUM_WORKERS": "8",
    "YOLO_DEVICE": "0",

    # Optimizer (same as Job 1)
    "YOLO_OPTIMIZER": "SGD",
    "YOLO_MOMENTUM": "0.937",
    "YOLO_WEIGHT_DECAY": "0.0005",

    # Loss gains (same as Job 1: heavy box+dfl penalties to lock in tight bboxes)
    "YOLO_BOX": "10.0",
    "YOLO_CLS": "0.5",
    "YOLO_DFL": "3.0",

    # Augmentation - disable noisy ones for fine descent on small thermal fire targets
    "YOLO_MOSAIC": "0.0",
    "YOLO_MIXUP": "0.0",
    "YOLO_COPY_PASTE": "0.0",
    "YOLO_CLOSE_MOSAIC": "0",
    "YOLO_HSV_H": "0.0",  # no-op on thermal grayscale
    "YOLO_HSV_S": "0.0",  # no-op on thermal grayscale
    "YOLO_HSV_V": "0.2",
    "YOLO_FLIPLR": "0.5",
    "YOLO_FLIPUD": "0.0",
    "YOLO_SCALE": "0.3",
    "YOLO_TRANSLATE": "0.1",
    "YOLO_ERASING": "0.0",

    # Pretrained model path inside container (mounted via "pretrained" channel)
    "YOLO_MODEL": "/opt/ml/input/data/pretrained/best.pt",
    "YOLO_PRETRAINED": "true",
}


def _validate_env() -> None:
    missing = [k for k in ("SAGEMAKER_IMAGE_URI", "SAGEMAKER_ROLE_ARN") if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"Missing env vars: {missing}")


def wait_for_job(sm, base_job: str, poll_seconds: int = 60) -> str:
    """Block until base job reaches a terminal state. Return final status."""
    print(f"[wait] Polling {base_job} every {poll_seconds}s...")
    while True:
        d = sm.describe_training_job(TrainingJobName=base_job)
        status = d["TrainingJobStatus"]
        secondary = d.get("SecondaryStatus", "")
        if status in ("Completed", "Failed", "Stopped"):
            print(f"[wait] Terminal: {status} / {secondary}")
            return status
        elapsed = (datetime.now(timezone.utc) - d["TrainingStartTime"]).total_seconds() / 60
        print(f"[wait] {datetime.now().strftime('%H:%M:%S')}  status={status}/{secondary}  elapsed={elapsed:.1f}min")
        time.sleep(poll_seconds)


def extract_best_pt_from_job(s3, base_job: str, dest_bucket: str, dest_key: str) -> None:
    """Download the base job's model.tar.gz, extract best.pt, upload to dest."""
    src_key = f"training/{base_job}/output/model.tar.gz"
    print(f"[best.pt] Downloading s3://{dest_bucket}/{src_key} ...")
    buf = io.BytesIO()
    s3.download_fileobj(dest_bucket, src_key, buf)
    buf.seek(0)
    print(f"[best.pt] Downloaded {buf.getbuffer().nbytes/1e6:.1f} MB. Extracting...")

    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        candidates = [m for m in tar.getmembers() if m.name.endswith("best.pt")]
        if not candidates:
            names = [m.name for m in tar.getmembers()][:30]
            raise RuntimeError(f"No best.pt in archive. Members (first 30): {names}")
        # Prefer 'best.pt' at root, fall back to 'train/weights/best.pt'
        candidates.sort(key=lambda m: ("/" in m.name, len(m.name)))
        chosen = candidates[0]
        print(f"[best.pt] Picked: {chosen.name} ({chosen.size/1e6:.1f} MB)")
        f = tar.extractfile(chosen)
        if f is None:
            raise RuntimeError(f"Cannot extract {chosen.name}")
        data = f.read()

    print(f"[best.pt] Uploading to s3://{dest_bucket}/{dest_key} ...")
    s3.put_object(Bucket=dest_bucket, Key=dest_key, Body=data)
    print(f"[best.pt] Done. {len(data)/1e6:.1f} MB stored.")


def build_request(job_name: str, pretrained_s3_prefix: str) -> dict:
    env_vars = {
        "SM_MODEL_DIR": "/opt/ml/model",
        "SM_CHANNEL_TRAINING": "/opt/ml/input/data/training",
        "SM_CHANNEL_PRETRAINED": "/opt/ml/input/data/pretrained",
        "SM_OUTPUT_DATA_DIR": "/opt/ml/output/data",
        "TRAINING_JOB_NAME": job_name,
        **JOB2_HYPERPARAMS,
    }

    # Pass W&B API key if available (never logged/committed)
    wandb_key = os.environ.get("WANDB_API_KEY")
    if wandb_key:
        env_vars["WANDB_API_KEY"] = wandb_key

    return {
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
                    }
                },
                "InputMode": "File",
            },
            {
                "ChannelName": "pretrained",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": pretrained_s3_prefix,
                        "S3DataDistributionType": "FullyReplicated",
                    }
                },
                "InputMode": "File",
            },
        ],
        "OutputDataConfig": {"S3OutputPath": f"s3://{S3_OUTPUT_BUCKET}/training/"},
        "ResourceConfig": {
            "InstanceType": "ml.g5.xlarge",
            "InstanceCount": 1,
            "VolumeSizeInGB": 100,
        },
        "StoppingCondition": {"MaxRuntimeInSeconds": 14400},  # 4h safety cap
        "Environment": env_vars,
        "EnableManagedSpotTraining": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-job", required=True, help="Source job name (warm-start origin)")
    parser.add_argument("--wait", action="store_true", help="Poll base job until terminal before launching Job 2")
    parser.add_argument("--dry-run", action="store_true", help="Print request JSON and exit (no AWS calls beyond describe)")
    args = parser.parse_args()

    _validate_env()
    sm = boto3.client("sagemaker", region_name=REGION)
    s3 = boto3.client("s3", region_name=REGION)

    # 1. Optionally wait for the base job (skipped in dry-run so request can be inspected anytime)
    if args.dry_run:
        d = sm.describe_training_job(TrainingJobName=args.base_job)
        print(f"[dry-run] Base job status: {d['TrainingJobStatus']}/{d.get('SecondaryStatus','')}")
    elif args.wait:
        final = wait_for_job(sm, args.base_job)
        if final != "Completed":
            print(f"[abort] Base job ended in non-Completed state: {final}. Aborting.")
            return 2
    else:
        d = sm.describe_training_job(TrainingJobName=args.base_job)
        status = d["TrainingJobStatus"]
        if status != "Completed":
            print(f"[abort] Base job {args.base_job} status is {status}, need Completed. "
                  f"Re-run with --wait or wait manually.")
            return 2

    # 2. Build target paths and Job 2 name
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    job2_name = f"xheimdall-yolo26m-precision-{ts}"
    warm_prefix = f"{S3_WARMSTART_PREFIX}/{job2_name}"
    pretrained_s3_prefix = f"s3://{S3_OUTPUT_BUCKET}/{warm_prefix}/pretrained/"

    if args.dry_run:
        print(f"[dry-run] Would extract+upload best.pt from {args.base_job} -> {pretrained_s3_prefix}best.pt")
        request = build_request(job2_name, pretrained_s3_prefix)
        print("[dry-run] CreateTrainingJob request:")
        print(json.dumps(request, indent=2, default=str))
        return 0

    # 3. Extract best.pt and upload it to the pretrained channel
    extract_best_pt_from_job(
        s3,
        base_job=args.base_job,
        dest_bucket=S3_OUTPUT_BUCKET,
        dest_key=f"{warm_prefix}/pretrained/best.pt",
    )

    # 4. Launch
    request = build_request(job2_name, pretrained_s3_prefix)
    print(f"\n[launch] CreateTrainingJob: {job2_name}")
    print(f"[launch] Image: {IMAGE_URI}")
    print(f"[launch] Hyperparams: lr0={JOB2_HYPERPARAMS['YOLO_LR0']} cos_lr={JOB2_HYPERPARAMS['YOLO_COS_LR']} "
          f"mosaic={JOB2_HYPERPARAMS['YOLO_MOSAIC']} epochs={JOB2_HYPERPARAMS['YOLO_EPOCHS']}")
    resp = sm.create_training_job(**request)
    print(f"\n[launched] {resp['TrainingJobArn']}")
    print(f"[launched] Console: https://{REGION}.console.aws.amazon.com/sagemaker/home?region={REGION}#/jobs/{job2_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
