"""TensorRT FP16 Export — XHeimdall YOLO26m → Jetson AGX.

Converts a trained YOLO .pt model to TensorRT FP16 engine.
Requires CUDA-capable GPU with TensorRT installed.

Usage:
    python src/export_tensorrt.py --model best.pt --output best_fp16.engine
"""

import sys
import json
import time
import shutil
import logging
import subprocess
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def get_version_info() -> dict[str, str]:
    """Collect version info for debugging R13 (version mismatch risk).

    Returns dict with tensorrt, torch, ultralytics versions.
    Safe to call without GPU — returns "not_installed" for missing libs.
    """
    versions: dict[str, str] = {}

    try:
        import tensorrt
        versions["tensorrt"] = getattr(tensorrt, "__version__", "unknown")
    except ImportError:
        versions["tensorrt"] = "not_installed"

    try:
        import torch
        versions["torch"] = torch.__version__
        versions["cuda_available"] = str(torch.cuda.is_available())
        if torch.cuda.is_available():
            versions["cuda_version"] = torch.version.cuda or "unknown"
            versions["gpu_name"] = torch.cuda.get_device_name(0)
    except ImportError:
        versions["torch"] = "not_installed"
        versions["cuda_available"] = "False"

    try:
        import ultralytics
        versions["ultralytics"] = ultralytics.__version__
    except ImportError:
        versions["ultralytics"] = "not_installed"

    return versions


def export_to_tensorrt(
    model_path: str,
    output_path: str,
    imgsz: int = 640,
    half: bool = True,
    workspace: int = 4,
    dynamic: bool = False,
    simplify: bool = True,
    opset: int = 17,
    batch: int = 1,
) -> dict:
    """Export a YOLO .pt model to TensorRT FP16 engine.

    Args:
        model_path: Path to trained .pt model (e.g., best.pt)
        output_path: Output path for .engine file
        imgsz: Input image size (must be 640 for YOLO26m)
        half: Use FP16 precision
        workspace: TensorRT workspace size in GB
        dynamic: Dynamic batch size (disable for Jetson)
        simplify: ONNX model simplification
        opset: ONNX opset version (17 for TensorRT 8.6+)
        batch: Inference batch size (1 for real-time Jetson)

    Returns:
        dict with export metadata: paths, sizes, timing, versions

    Raises:
        FileNotFoundError: If model_path doesn't exist
        RuntimeError: If CUDA/TensorRT not available
    """
    model_file = Path(model_path)
    if not model_file.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    try:
        import torch
        from ultralytics import YOLO
    except ImportError as e:
        raise RuntimeError(
            f"Missing required dependency: {e}. "
            "Install with: pip install torch ultralytics"
        )

    if not torch.cuda.is_available():
        raise RuntimeError(
            "TensorRT export requires CUDA-capable GPU. "
            "No CUDA device detected."
        )

    versions = get_version_info()
    if versions["tensorrt"] == "not_installed":
        raise RuntimeError(
            "TensorRT is not installed. Install with: "
            "pip install tensorrt (or use Ultralytics Docker image)"
        )

    logger.info("=" * 60)
    logger.info("XHeimdall TensorRT FP16 Export")
    logger.info("=" * 60)
    logger.info(f"  Model:       {model_path}")
    logger.info(f"  Output:      {output_path}")
    logger.info(f"  Image size:  {imgsz}")
    logger.info(f"  Precision:   {'FP16' if half else 'FP32'}")
    logger.info(f"  Workspace:   {workspace} GB")
    logger.info(f"  Batch size:  {batch}")
    logger.info(f"  ONNX opset:  {opset}")
    logger.info("  Versions:")
    for k, v in sorted(versions.items()):
        logger.info(f"    {k}: {v}")

    logger.info("Loading model...")
    model = YOLO(model_path)
    model_size_mb = model_file.stat().st_size / (1024 * 1024)
    logger.info(f"Model loaded: {model_size_mb:.1f} MB")

    logger.info("Exporting to TensorRT (this may take 1-3 minutes)...")
    t_start = time.perf_counter()

    export_path = model.export(
        format="engine",
        imgsz=imgsz,
        half=half,
        workspace=workspace,
        dynamic=dynamic,
        simplify=simplify,
        opset=opset,
        batch=batch,
    )

    t_export = time.perf_counter() - t_start
    logger.info(f"Export completed in {t_export:.1f}s")

    export_file = Path(export_path)
    output_file = Path(output_path)

    if export_file != output_file:
        shutil.move(str(export_file), str(output_file))
        logger.info(f"Moved engine: {export_file} → {output_file}")
    else:
        logger.info(f"Engine at: {output_file}")

    engine_size_mb = output_file.stat().st_size / (1024 * 1024)
    logger.info(f"Engine size: {engine_size_mb:.1f} MB")

    logger.info("Validating engine...")
    try:
        engine_model = YOLO(str(output_file))
    except Exception as e:
        logger.error(f"Engine loading failed: {e}")
        raise RuntimeError(f"TensorRT engine validation failed: {e}")

    dummy_frame = np.random.randint(0, 255, (imgsz, imgsz, 3), dtype=np.uint8)
    t_inf_start = time.perf_counter()
    results = engine_model.predict(dummy_frame, verbose=False)
    t_inference = (time.perf_counter() - t_inf_start) * 1000

    logger.info(f"Engine validation: {len(results)} result(s)")
    logger.info(f"Inference time: {t_inference:.2f} ms")
    if t_inference > 5:
        logger.warning(
            f"Inference > 5ms target ({t_inference:.2f}ms). "
            "Jetson FPS may be below 25."
        )

    metadata = {
        "model_path": str(model_file.absolute()),
        "engine_path": str(output_file.absolute()),
        "engine_size_mb": round(engine_size_mb, 2),
        "export_time_s": round(t_export, 1),
        "inference_time_ms": round(t_inference, 2),
        "imgsz": imgsz,
        "precision": "FP16" if half else "FP32",
        "batch": batch,
        "versions": versions,
    }

    metadata_path = output_file.with_suffix(".json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Metadata saved: {metadata_path}")

    logger.info("=" * 60)
    logger.info("TENSORRT EXPORT COMPLETE")
    logger.info(f"  Engine:  {output_file} ({engine_size_mb:.1f} MB)")
    logger.info(f"  Export:  {t_export:.1f}s")
    logger.info(f"  Infer:   {t_inference:.2f}ms")
    logger.info("=" * 60)

    return metadata


def upload_engine_to_s3(
    engine_path: str,
    s3_uri: str = "s3://xheimdall-models/engines/best_fp16.engine",
    region: str = "us-east-1",
) -> bool:
    """Upload TensorRT engine to S3.

    Args:
        engine_path: Local path to .engine file
        s3_uri: S3 destination URI
        region: AWS region

    Returns:
        True if upload successful, False otherwise
    """
    engine_file = Path(engine_path)
    if not engine_file.exists():
        logger.error(f"Engine not found: {engine_path}")
        return False

    logger.info(f"Uploading {engine_file} → {s3_uri}")
    result = subprocess.run(
        ["aws", "s3", "cp", str(engine_file), s3_uri, "--region", region],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        logger.info(f"Upload complete: {s3_uri}")

        metadata_path = engine_file.with_suffix(".json")
        if metadata_path.exists():
            metadata_s3 = s3_uri.replace(".engine", ".json")
            subprocess.run(
                ["aws", "s3", "cp", str(metadata_path), metadata_s3, "--region", region],
                capture_output=True, text=True,
            )
        return True
    else:
        logger.error(f"Upload failed: {result.stderr}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Export YOLO26m to TensorRT FP16 engine"
    )
    parser.add_argument(
        "--model", required=True, help="Path to trained .pt model"
    )
    parser.add_argument(
        "--output", default="best_fp16.engine", help="Output engine path"
    )
    parser.add_argument(
        "--imgsz", type=int, default=640, help="Input image size"
    )
    parser.add_argument(
        "--fp32", action="store_true", help="Use FP32 (default: FP16)"
    )
    parser.add_argument(
        "--workspace", type=int, default=4, help="TRT workspace GB"
    )
    parser.add_argument(
        "--upload", action="store_true", help="Upload engine to S3 after export"
    )
    parser.add_argument(
        "--s3-uri",
        default="s3://xheimdall-models/engines/best_fp16.engine",
        help="S3 URI for upload",
    )

    args = parser.parse_args()

    try:
        metadata = export_to_tensorrt(
            model_path=args.model,
            output_path=args.output,
            imgsz=args.imgsz,
            half=not args.fp32,
            workspace=args.workspace,
        )

        if args.upload:
            upload_engine_to_s3(args.output, args.s3_uri)

    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except RuntimeError as e:
        logger.error(str(e))
        sys.exit(1)
