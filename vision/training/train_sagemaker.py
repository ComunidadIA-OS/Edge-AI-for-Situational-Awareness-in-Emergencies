"""XHeimdall SageMaker Training Entrypoint — YOLO26m thermal fire detection.

This script is the ENTRYPOINT of the SageMaker Docker container.
Invoked as: python /opt/ml/code/train.py
Environment: SageMaker Training Job with SM_MODEL_DIR, SM_CHANNEL_TRAINING set.
"""

import os
import json
import shutil
import signal
import subprocess
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone

import yaml
from ultralytics import YOLO

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def get_env_vars() -> dict:
    """Read all SageMaker and YOLO environment variables with defaults.

    Defaults match Ultralytics defaults or prior hardcoded values to keep
    existing jobs backward-compatible. Job 2 (warm-restart) overrides the
    augmentation knobs (mosaic, mixup, scale, hsv_*) and the schedule knobs
    (lrf, cos_lr, warmup_epochs).
    """
    return {
        "SM_MODEL_DIR": os.environ["SM_MODEL_DIR"],
        "SM_CHANNEL_TRAINING": os.environ["SM_CHANNEL_TRAINING"],
        "SM_CHANNEL_VALIDATION": os.getenv("SM_CHANNEL_VALIDATION"),
        "SM_CHANNEL_PRETRAINED": os.getenv("SM_CHANNEL_PRETRAINED"),
        "YOLO_MODEL": os.getenv("YOLO_MODEL", "yolo26m.pt"),
        "YOLO_EPOCHS": os.getenv("YOLO_EPOCHS", "200"),
        "YOLO_BATCH": os.getenv("YOLO_BATCH", "8"),
        "YOLO_IMGSZ": os.getenv("YOLO_IMGSZ", "640"),
        "YOLO_PATIENCE": os.getenv("YOLO_PATIENCE", "30"),
        "YOLO_LR0": os.getenv("YOLO_LR0", "0.01"),
        "YOLO_LRF": os.getenv("YOLO_LRF", "0.01"),
        "YOLO_COS_LR": os.getenv("YOLO_COS_LR", "false"),
        "YOLO_WARMUP_EPOCHS": os.getenv("YOLO_WARMUP_EPOCHS", "3.0"),
        "YOLO_DEVICE": os.getenv("YOLO_DEVICE", "0,1,2,3"),
        "YOLO_NUM_WORKERS": os.getenv("YOLO_NUM_WORKERS", "8"),
        "YOLO_PRETRAINED": os.getenv("YOLO_PRETRAINED", "true"),
        "YOLO_SAVE_PERIOD": os.getenv("YOLO_SAVE_PERIOD", "10"),
        "YOLO_OPTIMIZER": os.getenv("YOLO_OPTIMIZER", "auto"),
        "YOLO_BOX": os.getenv("YOLO_BOX", "7.5"),
        "YOLO_CLS": os.getenv("YOLO_CLS", "0.5"),
        "YOLO_DFL": os.getenv("YOLO_DFL", "1.5"),
        "YOLO_MOMENTUM": os.getenv("YOLO_MOMENTUM", "0.937"),
        "YOLO_WEIGHT_DECAY": os.getenv("YOLO_WEIGHT_DECAY", "0.0005"),
        "YOLO_HSV_H": os.getenv("YOLO_HSV_H", "0.0"),
        "YOLO_HSV_S": os.getenv("YOLO_HSV_S", "0.0"),
        "YOLO_HSV_V": os.getenv("YOLO_HSV_V", "0.3"),
        "YOLO_FLIPUD": os.getenv("YOLO_FLIPUD", "0.0"),
        "YOLO_FLIPLR": os.getenv("YOLO_FLIPLR", "0.5"),
        "YOLO_MOSAIC": os.getenv("YOLO_MOSAIC", "1.0"),
        "YOLO_MIXUP": os.getenv("YOLO_MIXUP", "0.1"),
        "YOLO_COPY_PASTE": os.getenv("YOLO_COPY_PASTE", "0.0"),
        "YOLO_CLOSE_MOSAIC": os.getenv("YOLO_CLOSE_MOSAIC", "10"),
        "YOLO_SCALE": os.getenv("YOLO_SCALE", "0.5"),
        "YOLO_TRANSLATE": os.getenv("YOLO_TRANSLATE", "0.1"),
        "YOLO_ERASING": os.getenv("YOLO_ERASING", "0.4"),
        "OUTPUT_CHECKPOINT_S3": os.getenv("OUTPUT_CHECKPOINT_S3"),
    }


def validate_env(env: dict) -> None:
    """Validate critical env vars. Raises SystemExit on missing required vars."""
    required = ["SM_MODEL_DIR", "SM_CHANNEL_TRAINING"]
    missing = [k for k in required if k not in os.environ]
    if missing:
        logger.error(f"Missing required environment variables: {missing}")
        sys.exit(1)

    data_yaml_path = Path(env["SM_CHANNEL_TRAINING"]) / "data.yaml"
    if not data_yaml_path.exists():
        logger.error(f"data.yaml not found at {data_yaml_path}")
        sys.exit(1)

    logger.info(f"data.yaml found at {data_yaml_path}")
    logger.info(f"Model output dir: {env['SM_MODEL_DIR']}")


def setup_signal_handlers(checkpoint_s3: str | None, checkpoint_dir: Path) -> None:
    """Register SIGTERM handler for SageMaker spot interruption.

    When SageMaker sends SIGTERM (2-minute warning before spot termination):
    1. Sync latest checkpoints to S3
    2. Exit with code 0 (SageMaker will resume from checkpoint on next attempt)
    """
    def sigterm_handler(signum, frame):
        logger.warning("=" * 60)
        logger.warning("SIGTERM received — spot instance interruption")
        logger.warning("=" * 60)

        if checkpoint_s3 and checkpoint_dir.exists():
            logger.info(f"Syncing checkpoints to {checkpoint_s3}")
            result = subprocess.run(
                ["aws", "s3", "sync", str(checkpoint_dir), checkpoint_s3, "--no-progress"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                logger.info("Checkpoint sync complete. Exiting gracefully.")
            else:
                logger.error(f"Checkpoint sync failed: {result.stderr}")
        else:
            logger.info("No checkpoint S3 URI configured. Exiting.")

        sys.exit(0)

    signal.signal(signal.SIGTERM, sigterm_handler)
    logger.info("SIGTERM handler registered for spot interruption resilience.")


def load_data_config(data_yaml_path: Path) -> dict:
    """Load and validate data.yaml."""
    with open(data_yaml_path) as f:
        config = yaml.safe_load(f)

    nc = config.get("nc", 0)
    names = config.get("names", {})
    logger.info(f"Data config: nc={nc}, names={names}, path={config.get('path')}")

    return config


def extract_metrics(results, epochs_completed: int) -> dict:
    """Extract key metrics from Ultralytics training results object.

    Returns a dict with mAP50, mAP50-95, precision, recall, best_epoch.
    The Ultralytics Results object has:
    - results.results_dict: dict with metric keys
    - results.best: best epoch (int or None)
    - results.epoch: last completed epoch (int)
    """
    rd = getattr(results, "results_dict", {}) or {}

    return {
        "mAP50": round(float(rd.get("metrics/mAP50(B)", 0.0)), 4),
        "mAP50_95": round(float(rd.get("metrics/mAP50-95(B)", 0.0)), 4),
        "precision": round(float(rd.get("metrics/precision(B)", 0.0)), 4),
        "recall": round(float(rd.get("metrics/recall(B)", 0.0)), 4),
        "epochs_completed": epochs_completed,
        "best_epoch": int(results.best) if getattr(results, "best", None) is not None else epochs_completed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def sync_checkpoints(checkpoint_dir: Path, s3_uri: str) -> bool:
    """Sync training checkpoints to S3. Returns True on success."""
    if not checkpoint_dir.exists():
        logger.warning(f"Checkpoint dir does not exist: {checkpoint_dir}")
        return False

    logger.info(f"Syncing {checkpoint_dir} → {s3_uri}")
    result = subprocess.run(
        ["aws", "s3", "sync", str(checkpoint_dir), s3_uri, "--no-progress"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.error(f"S3 sync failed: {result.stderr}")
        return False
    logger.info("S3 sync complete.")
    return True


def main():
    logger.info("=" * 60)
    logger.info("XHeimdall YOLO26m Training — SageMaker Entrypoint")
    logger.info("=" * 60)

    env = get_env_vars()
    for key, value in sorted(env.items()):
        logger.info(f"  {key}={value}")

    validate_env(env)

    data_yaml_path = Path(env["SM_CHANNEL_TRAINING"]) / "data.yaml"
    data_config = load_data_config(data_yaml_path)

    # Rewrite data.yaml path to SageMaker channel mount point.
    # Ultralytics resolves relative paths against CWD (/opt/ml/code),
    # NOT against where data.yaml lives. This fixes the discrepancy.
    data_config["path"] = env["SM_CHANNEL_TRAINING"]
    with open(data_yaml_path, "w") as f:
        yaml.dump(data_config, f, default_flow_style=False)
    logger.info(f"data.yaml path rewritten to: {data_config['path']}")

    epochs = int(env["YOLO_EPOCHS"])
    batch = int(env["YOLO_BATCH"])
    imgsz = int(env["YOLO_IMGSZ"])
    patience = int(env["YOLO_PATIENCE"])
    lr0 = float(env["YOLO_LR0"])
    lrf = float(env["YOLO_LRF"])
    cos_lr = env["YOLO_COS_LR"].lower() == "true"
    warmup_epochs = float(env["YOLO_WARMUP_EPOCHS"])
    device = env["YOLO_DEVICE"]
    pretrained = env["YOLO_PRETRAINED"].lower() == "true"
    model_name = env["YOLO_MODEL"]
    save_period = int(env["YOLO_SAVE_PERIOD"])
    num_workers = int(env["YOLO_NUM_WORKERS"])
    optimizer = env["YOLO_OPTIMIZER"]
    box_gain = float(env["YOLO_BOX"])
    cls_gain = float(env["YOLO_CLS"])
    dfl_gain = float(env["YOLO_DFL"])
    momentum = float(env["YOLO_MOMENTUM"])
    weight_decay = float(env["YOLO_WEIGHT_DECAY"])
    hsv_h = float(env["YOLO_HSV_H"])
    hsv_s = float(env["YOLO_HSV_S"])
    hsv_v = float(env["YOLO_HSV_V"])
    flipud = float(env["YOLO_FLIPUD"])
    fliplr = float(env["YOLO_FLIPLR"])
    mosaic = float(env["YOLO_MOSAIC"])
    mixup = float(env["YOLO_MIXUP"])
    copy_paste = float(env["YOLO_COPY_PASTE"])
    close_mosaic = int(env["YOLO_CLOSE_MOSAIC"])
    scale = float(env["YOLO_SCALE"])
    translate = float(env["YOLO_TRANSLATE"])
    erasing = float(env["YOLO_ERASING"])

    sm_model_dir = Path(env["SM_MODEL_DIR"])
    weights_dir = sm_model_dir / "train" / "weights"
    checkpoint_s3 = env.get("OUTPUT_CHECKPOINT_S3")

    if checkpoint_s3:
        setup_signal_handlers(checkpoint_s3, weights_dir)

    sm_channel_pretrained = env.get("SM_CHANNEL_PRETRAINED")
    if sm_channel_pretrained:
        pretrained_pt = Path(sm_channel_pretrained) / "best.pt"
        if pretrained_pt.exists():
            logger.info(f"Warm-restart: loading pretrained weights from {pretrained_pt}")
            model_name = str(pretrained_pt)
        else:
            logger.error(f"SM_CHANNEL_PRETRAINED set but best.pt missing at {pretrained_pt}")
            sys.exit(1)

    logger.info(f"Loading model: {model_name}")
    model = YOLO(model_name)

    logger.info("=" * 60)
    logger.info("STARTING TRAINING")
    logger.info(f"  Epochs: {epochs}, Batch: {batch}, ImgSz: {imgsz}")
    logger.info(f"  Device: {device}, Patience: {patience}")
    logger.info(f"  LR schedule: lr0={lr0}, lrf={lrf}, cos_lr={cos_lr}, warmup={warmup_epochs}")
    logger.info(f"  Optimizer: {optimizer}, Momentum: {momentum}, WD: {weight_decay}")
    logger.info(f"  Loss gains: box={box_gain}, cls={cls_gain}, dfl={dfl_gain}")
    logger.info(f"  Aug HSV: h={hsv_h}, s={hsv_s}, v={hsv_v}")
    logger.info(f"  Aug geo: mosaic={mosaic}, mixup={mixup}, copy_paste={copy_paste}, close_mosaic={close_mosaic}")
    logger.info(f"  Aug geo: scale={scale}, translate={translate}, fliplr={fliplr}, flipud={flipud}, erasing={erasing}")
    logger.info(f"  Save period: {save_period} epochs")
    logger.info(f"  Checkpoint S3: {checkpoint_s3 or 'disabled'}")
    logger.info("=" * 60)

    # W&B observability — init before training, auto-log metrics
    try:
        import wandb
        wandb_api_key = os.environ.get("WANDB_API_KEY")
        training_job_name = os.environ.get("TRAINING_JOB_NAME", "xheimdall-yolo26m")
        if wandb_api_key:
            wandb.login(key=wandb_api_key)
            wandb.init(
                project="xheimdall-yolo26m",
                name=training_job_name,
                config={
                    "model": model_name,
                    "epochs": epochs,
                    "batch": batch,
                    "imgsz": imgsz,
                    "lr0": lr0,
                    "lrf": lrf,
                    "cos_lr": cos_lr,
                    "optimizer": optimizer,
                    "box_gain": box_gain,
                    "cls_gain": cls_gain,
                    "dfl_gain": dfl_gain,
                },
                resume="allow",
            )
            logger.info(f"W&B initialized: project=xheimdall-yolo26m, run={wandb.run.name}")
        else:
            logger.info("WANDB_API_KEY not set — skipping W&B init")
    except Exception as e:
        logger.warning(f"W&B init failed (non-fatal): {e}")

    results = model.train(
        data=str(data_yaml_path),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        patience=patience,
        lr0=lr0,
        lrf=lrf,
        cos_lr=cos_lr,
        warmup_epochs=warmup_epochs,
        save_period=save_period,
        pretrained=pretrained,
        workers=num_workers,
        optimizer=optimizer,
        momentum=momentum,
        weight_decay=weight_decay,
        box=box_gain,
        cls=cls_gain,
        dfl=dfl_gain,
        hsv_h=hsv_h,
        hsv_s=hsv_s,
        hsv_v=hsv_v,
        flipud=flipud,
        fliplr=fliplr,
        mosaic=mosaic,
        mixup=mixup,
        copy_paste=copy_paste,
        close_mosaic=close_mosaic,
        scale=scale,
        translate=translate,
        erasing=erasing,
        project=str(sm_model_dir),
        name="train",
        exist_ok=True,
    )

    best_pt_src = sm_model_dir / "train" / "weights" / "best.pt"
    best_pt_dst = sm_model_dir / "best.pt"
    if best_pt_src.exists():
        shutil.copy2(str(best_pt_src), str(best_pt_dst))
        logger.info(f"Copied best.pt → {best_pt_dst}")
    else:
        logger.error(f"best.pt not found at {best_pt_src}")

    best_epoch = int(results.best) if getattr(results, "best", None) is not None else epochs
    metrics = extract_metrics(results, best_epoch)
    metrics_path = sm_model_dir / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"Metrics saved to {metrics_path}")
    logger.info(f"  mAP50={metrics['mAP50']}, mAP50-95={metrics['mAP50_95']}")
    logger.info(f"  Best epoch: {metrics['best_epoch']}")

    if checkpoint_s3:
        sync_checkpoints(weights_dir, checkpoint_s3)

    logger.info("=" * 60)
    logger.info("TRAINING COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
