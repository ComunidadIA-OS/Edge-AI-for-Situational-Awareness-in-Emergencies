"""Replay pre-recorded FireDetectionPayload entries to the Convergence API.

Reads a JSONL file (one JSON payload per line) and posts each entry to
POST /detect at a configurable interval. With --loop the sequence repeats
indefinitely — useful for live demos when real hardware is unavailable.

Usage:
    python scripts/replay_detections.py --file tests/data/demo_replay.jsonl
    python scripts/replay_detections.py --file tests/data/demo_replay.jsonl --interval 3 --loop
    python scripts/replay_detections.py --file tests/data/demo_replay.jsonl --api-url http://192.168.1.50:8000
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("replay")


def _stamp_now(payload: dict) -> dict:
    """Overwrite timestamps with the current UTC time so the report looks live."""
    now = datetime.now(timezone.utc).isoformat()
    payload = dict(payload)
    payload["detected_at"] = now
    if "drone_telemetry" in payload and payload["drone_telemetry"]:
        payload["drone_telemetry"] = dict(payload["drone_telemetry"])
        payload["drone_telemetry"]["timestamp"] = now
    return payload


def post_payload(url: str, payload: dict, timeout: float = 10.0) -> bool:
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        if r.ok:
            data = r.json()
            area = data.get("fire_perimeter", {}).get("area_ha", "?")
            fwi = data.get("prediction", {}).get("fire_weather_index", "?")
            trend = data.get("prediction", {}).get("trend", "?")
            logger.info("  OK | area=%.2f ha | FWI=%.0f | trend=%s", area, fwi, trend)
            return True
        else:
            logger.warning("  HTTP %d: %s", r.status_code, r.text[:120])
            return False
    except requests.exceptions.ConnectionError:
        logger.error("  Connection refused — is the API running at %s?", url)
        return False
    except Exception as exc:
        logger.error("  Unexpected error: %s", exc)
        return False


def run_replay(
    jsonl_path: Path,
    api_url: str,
    interval_s: float,
    loop: bool,
    dry_run: bool,
) -> None:
    lines = [ln.strip() for ln in jsonl_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        logger.error("No payloads found in %s", jsonl_path)
        sys.exit(1)

    payloads = []
    for i, line in enumerate(lines, 1):
        try:
            payloads.append(json.loads(line))
        except json.JSONDecodeError as e:
            logger.error("JSON parse error on line %d: %s", i, e)
            sys.exit(1)

    detect_url = api_url.rstrip("/") + "/detect"
    logger.info("Replay: %d payloads | interval=%.1fs | loop=%s | url=%s",
                len(payloads), interval_s, loop, detect_url)
    if dry_run:
        logger.info("DRY RUN — payloads will not be sent")

    iteration = 0
    while True:
        iteration += 1
        if loop and iteration > 1:
            logger.info("--- loop %d ---", iteration)
        for idx, payload in enumerate(payloads, 1):
            live_payload = _stamp_now(payload)
            logger.info("[%d/%d] area=%.2f ha | confidence=%.2f",
                        idx, len(payloads),
                        live_payload.get("area_ha", 0),
                        live_payload.get("confidence", 0))
            if not dry_run:
                post_payload(detect_url, live_payload)
            if idx < len(payloads):
                time.sleep(interval_s)

        if not loop:
            break
        time.sleep(interval_s)

    logger.info("Replay complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay FireDetectionPayload JSONL to Convergence API")
    parser.add_argument("--file", required=True, help="Path to JSONL replay file")
    parser.add_argument("--api-url", default="http://localhost:8000",
                        help="Convergence API base URL (default: http://localhost:8000)")
    parser.add_argument("--interval", type=float, default=5.0,
                        help="Seconds between payloads (default: 5)")
    parser.add_argument("--loop", action="store_true",
                        help="Repeat the sequence indefinitely (demo mode)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and log payloads without sending them")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        logger.error("File not found: %s", path)
        sys.exit(1)

    run_replay(path, args.api_url, args.interval, args.loop, args.dry_run)


if __name__ == "__main__":
    main()
