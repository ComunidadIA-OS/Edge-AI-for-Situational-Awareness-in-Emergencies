"""
Heimdall edge supervisor — entrypoint for the vision-inference container.

Responsibilities:
  1. Run pre-flight checks (beeps + clear messages on failure).
  2. Launch vision/inference/infer_jetson.py as a subprocess.
  3. Health-check the convergence-api on a background thread; beep × 2 if it
     stops responding for more than 3 consecutive checks.
  4. Restart the inference subprocess on crash (exponential back-off, max 5 tries).
  5. Emit 4 beeps on unclassified fatal errors.
  6. Clean up GPIO on SIGTERM/SIGINT.

Environment variables (all optional, sane defaults):
  MODEL_ENGINE_PATH     — path to TensorRT engine  (default /models/best.engine)
  CAMERA_SOURCE         — camera device/index       (default /dev/video0)
  CAMERA_TEMPLATE       — GStreamer template         (default flir_boson)
  DRONE_LAT / DRONE_LON — telemetry origin           (default 41.6837 / -0.8881)
  DRONE_ALT_M           — altitude in metres         (default 120)
  DRONE_HEADING         — heading in degrees         (default 0)
  CONVERGENCE_API_URL   — API base URL               (default http://convergence-api:8000)
  HEALTHCHECK_INTERVAL  — seconds between API checks (default 5)
  MAX_RESTARTS          — max subprocess restarts    (default 5)
"""
from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import threading
import time

import requests

from edge.alerts import CriticalAlert
from edge import preflight

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("heimdall.supervisor")

API_URL: str = os.environ.get("CONVERGENCE_API_URL", "http://convergence-api:8000")
HEALTHCHECK_INTERVAL: float = float(os.environ.get("HEALTHCHECK_INTERVAL", "5"))
MAX_RESTARTS: int = int(os.environ.get("MAX_RESTARTS", "5"))
MODEL_ENGINE_PATH: str = os.environ.get("MODEL_ENGINE_PATH", "/models/best.engine")
CAMERA_SOURCE: str = os.environ.get("CAMERA_SOURCE", "/dev/video0")
CAMERA_TEMPLATE: str = os.environ.get("CAMERA_TEMPLATE", "flir_boson")
DRONE_LAT: str = os.environ.get("DRONE_LAT", "41.6837")
DRONE_LON: str = os.environ.get("DRONE_LON", "-0.8881")
DRONE_ALT: str = os.environ.get("DRONE_ALT_M", "120")
DRONE_HEADING: str = os.environ.get("DRONE_HEADING", "0")

_alert: CriticalAlert | None = None
_proc: subprocess.Popen | None = None  # type: ignore[type-arg]
_shutdown = threading.Event()


def _build_inference_cmd() -> list[str]:
    return [
        sys.executable, "-m", "vision.inference.infer_jetson",
        "--engine", MODEL_ENGINE_PATH,
        "--source", CAMERA_SOURCE,
        "--template", CAMERA_TEMPLATE,
        "--api-url", API_URL,
        "--drone-lat", DRONE_LAT,
        "--drone-lon", DRONE_LON,
        "--drone-alt", DRONE_ALT,
        "--drone-heading", DRONE_HEADING,
    ]


def _health_monitor() -> None:
    consecutive_failures = 0
    while not _shutdown.is_set():
        time.sleep(HEALTHCHECK_INTERVAL)
        if _shutdown.is_set():
            break
        try:
            r = requests.get(f"{API_URL}/health", timeout=4)
            if r.status_code == 200:
                consecutive_failures = 0
                continue
            raise RuntimeError(f"HTTP {r.status_code}")
        except Exception as exc:
            consecutive_failures += 1
            logger.warning("API health check failed (%d/3): %s", consecutive_failures, exc)
            if consecutive_failures >= 3:
                msg = (
                    f"\n[Heimdall] ERROR: convergence API not responding at {API_URL}\n"
                    "           Check that the convergence-api container is running.\n"
                )
                print(msg, file=sys.stderr, flush=True)
                if _alert:
                    _alert.beep(2)
                consecutive_failures = 0  # reset to avoid repeated beeping


def _run_inference() -> None:
    global _proc
    cmd = _build_inference_cmd()
    backoff = [5, 15, 30, 60, 300]
    restarts = 0

    while not _shutdown.is_set():
        logger.info("Starting inference subprocess (attempt %d/%d)", restarts + 1, MAX_RESTARTS + 1)
        print(f"[Heimdall] Starting: {' '.join(cmd)}", flush=True)

        try:
            _proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
            _proc.wait()
        except FileNotFoundError:
            logger.critical("Python module vision.inference.infer_jetson not found.")
            if _alert:
                _alert.beep(4)
            sys.exit(4)
        except Exception as exc:
            logger.critical("Failed to launch inference subprocess: %s", exc)
            if _alert:
                _alert.beep(4)
            sys.exit(4)

        if _shutdown.is_set():
            break

        rc = _proc.returncode
        if rc == 0:
            logger.info("Inference subprocess exited cleanly (rc=0).")
            break

        restarts += 1
        logger.error("Inference subprocess exited with rc=%d (restart %d/%d)", rc, restarts, MAX_RESTARTS)

        if restarts > MAX_RESTARTS:
            msg = (
                "\n[Heimdall] FATAL: inference subprocess crashed too many times.\n"
                f"           Last exit code: {rc}\n"
                "           Connect a screen and check logs.\n"
            )
            print(msg, file=sys.stderr, flush=True)
            if _alert:
                _alert.beep(4)
            sys.exit(4)

        wait = backoff[min(restarts - 1, len(backoff) - 1)]
        logger.info("Waiting %d s before restart...", wait)
        _shutdown.wait(timeout=wait)


def _on_signal(sig: int, _frame: object) -> None:
    logger.info("Received signal %d — shutting down.", sig)
    _shutdown.set()
    if _proc and _proc.poll() is None:
        _proc.terminate()
        try:
            _proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _proc.kill()
    if _alert:
        _alert.cleanup()
    sys.exit(0)


def main() -> None:
    global _alert

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    _alert = CriticalAlert()

    try:
        preflight.run(alert=_alert)
    except SystemExit:
        _alert.cleanup()
        raise
    except Exception as exc:
        logger.critical("Pre-flight raised unexpected exception: %s", exc)
        _alert.beep(4)
        _alert.cleanup()
        sys.exit(4)

    monitor = threading.Thread(target=_health_monitor, daemon=True, name="health-monitor")
    monitor.start()

    try:
        _run_inference()
    except SystemExit:
        raise
    except Exception as exc:
        logger.critical("Supervisor fatal error: %s", exc)
        _alert.beep(4)
        _alert.cleanup()
        sys.exit(4)

    _alert.cleanup()


if __name__ == "__main__":
    main()
