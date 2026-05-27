"""
Pre-flight checks that run before the vision inference loop starts.

Each critical check emits a distinct beep code and prints a clear human-readable
message, then exits with a non-zero code. Non-critical issues print a warning and
continue — the operator can connect a screen to investigate.

Exit codes / beep codes:
  1 — no camera at /dev/video*
  3 — TensorRT engine file missing or unreadable
"""
from __future__ import annotations

import os
import sys
import logging
from pathlib import Path

from edge.alerts import CriticalAlert

logger = logging.getLogger(__name__)

MODEL_ENGINE_PATH: str = os.environ.get("MODEL_ENGINE_PATH", "/models/best.engine")


def _list_video_devices() -> list[str]:
    """Return /dev/video* paths present on the system."""
    video_dir = Path("/dev")
    if not video_dir.exists():
        return []
    return sorted(str(p) for p in video_dir.glob("video*"))


def run(alert: CriticalAlert | None = None) -> None:
    """
    Execute all pre-flight checks.

    Raises SystemExit(N) where N is the beep code if a critical check fails.
    Prints to stderr so the operator sees the message even in a minimal terminal.
    """
    if alert is None:
        alert = CriticalAlert()

    _check_cameras(alert)
    _check_engine(alert)
    _warn_audio_backend(alert)

    logger.info("Pre-flight checks passed.")
    print("[Heimdall] Pre-flight OK — all systems ready.", flush=True)


def _check_cameras(alert: CriticalAlert) -> None:
    devices = _list_video_devices()
    if not devices:
        msg = (
            "\n"
            "╔══════════════════════════════════════════════════════╗\n"
            "║  ERROR: no camera connected                          ║\n"
            "║  Connect a thermal camera to a /dev/video* port and  ║\n"
            "║  restart the system.                                 ║\n"
            "╚══════════════════════════════════════════════════════╝\n"
        )
        print(msg, file=sys.stderr, flush=True)
        logger.critical("No /dev/video* devices found — aborting.")
        alert.beep(1)
        sys.exit(1)
    logger.info("Cameras detected: %s", devices)
    print(f"[Heimdall] Cameras detected: {', '.join(devices)}", flush=True)


def _check_engine(alert: CriticalAlert) -> None:
    engine = Path(MODEL_ENGINE_PATH)
    if not engine.exists() or not engine.is_file():
        msg = (
            "\n"
            "╔══════════════════════════════════════════════════════╗\n"
            f"║  ERROR: TensorRT engine not found                    ║\n"
            f"║  Expected: {str(engine):<42}║\n"
            "║  Run 'python scripts/fetch_model.py' to download     ║\n"
            "║  best.pt, then export: python -m vision.inference.   ║\n"
            "║  export_tensorrt --model best.pt --fp16              ║\n"
            "╚══════════════════════════════════════════════════════╝\n"
        )
        print(msg, file=sys.stderr, flush=True)
        logger.critical("TensorRT engine missing: %s", engine)
        alert.beep(3)
        sys.exit(3)
    logger.info("TensorRT engine found: %s (%.1f MB)", engine, engine.stat().st_size / 1e6)
    print(f"[Heimdall] Engine: {engine} ({engine.stat().st_size/1e6:.1f} MB)", flush=True)


def _warn_audio_backend(alert: CriticalAlert) -> None:
    backend = alert._backend[0]
    if backend == "term":
        print(
            "[Heimdall] WARNING: no hardware audio backend (GPIO/ALSA). "
            "Beep alerts will be silent. Connect a buzzer to GPIO pin "
            f"{os.environ.get('BUZZER_GPIO_PIN', '7')} or an ALSA-compatible speaker.",
            file=sys.stderr,
            flush=True,
        )
