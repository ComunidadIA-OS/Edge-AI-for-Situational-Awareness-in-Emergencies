"""
Download Heimdall model weights (best.pt) from the GitHub Release.

Usage:
    python scripts/fetch_model.py
    python scripts/fetch_model.py --output models/best.pt
    python scripts/fetch_model.py --force        # re-download even if file exists

The script verifies the SHA-256 checksum after download to catch partial or
corrupted downloads. Update SHA256_EXPECTED below after creating a new release.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

RELEASE_TAG = "Heimdall-Vision-TensorRT-F16"
ASSET_NAME = "Heimdall-TensorRT-FP16.pt"   # actual filename uploaded to the release
RELEASE_URL = (
    "https://github.com/ComunidadIA-OS/"
    "Edge-AI-for-Situational-Awareness-in-Emergencies/"
    f"releases/download/{RELEASE_TAG}/{ASSET_NAME}"
)

# SHA-256 of the official best.pt release asset (Heimdall-Vision-TensorRT-F16).
# Recompute with: sha256sum models/best.pt
SHA256_EXPECTED = "47ab5e4bd651e3a11afb6be787bb4a6b128e414401f4fa932d481a9a27c87921"

DEFAULT_OUTPUT = Path("models/best.pt")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _progress_hook(count: int, block_size: int, total_size: int) -> None:
    if total_size <= 0:
        return
    pct = min(100, count * block_size * 100 // total_size)
    mb = count * block_size / 1e6
    total_mb = total_size / 1e6
    print(f"\r  Downloading: {mb:.1f} / {total_mb:.1f} MB  ({pct}%)", end="", flush=True)


def download(output: Path = DEFAULT_OUTPUT, force: bool = False) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists() and not force:
        current = _sha256(output)
        if SHA256_EXPECTED != "PLACEHOLDER_REPLACE_AFTER_CREATING_RELEASE" and current == SHA256_EXPECTED:
            print(f"[fetch_model] {output} already present and checksum OK — skipping download.")
            return
        if SHA256_EXPECTED == "PLACEHOLDER_REPLACE_AFTER_CREATING_RELEASE":
            print(f"[fetch_model] {output} already present (checksum not yet configured). Use --force to re-download.")
            return

    print(f"[fetch_model] Downloading from:\n  {RELEASE_URL}")
    try:
        urllib.request.urlretrieve(RELEASE_URL, output, reporthook=_progress_hook)
    except Exception as exc:
        print(f"\n[fetch_model] ERROR: download failed — {exc}", file=sys.stderr)
        print(
            "  If the release URL is not yet published, download manually and place at:\n"
            f"  {output.resolve()}",
            file=sys.stderr,
        )
        sys.exit(1)

    print()  # newline after progress bar

    if SHA256_EXPECTED != "PLACEHOLDER_REPLACE_AFTER_CREATING_RELEASE":
        actual = _sha256(output)
        if actual != SHA256_EXPECTED:
            print(
                f"[fetch_model] CHECKSUM MISMATCH!\n"
                f"  Expected: {SHA256_EXPECTED}\n"
                f"  Got:      {actual}\n"
                "  The file may be corrupted. Delete it and re-run.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"[fetch_model] Checksum OK: {actual[:16]}…")

    size_mb = output.stat().st_size / 1e6
    print(f"[fetch_model] Saved to {output.resolve()} ({size_mb:.1f} MB)")
    print("[fetch_model] Next step: python -m vision.inference.export_tensorrt --model models/best.pt --fp16")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Heimdall model weights")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true", help="Re-download even if file exists")
    args = parser.parse_args()
    download(args.output, args.force)


if __name__ == "__main__":
    main()
