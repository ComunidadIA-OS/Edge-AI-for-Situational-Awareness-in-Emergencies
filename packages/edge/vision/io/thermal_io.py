# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026 Saúl Briceño, Carlos Langa, and ComunidadIA-OS contributors
#
# Part of Heimdall's vision-inference path — a derivative work of Ultralytics
# YOLO — licensed under AGPL-3.0. See LICENSE-AGPL-3.0.txt and NOTICE.

import logging
import subprocess
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def read_celsius_tiff(path: str) -> np.ndarray | None:
    """Read a radiometric Celsius TIFF (float32) and return a (H,W) float32 ndarray.

    Supports uncompressed and LZW-compressed TIFFs via tifffile + imagecodecs.
    Returns None (with WARNING log) on any failure path — never raises.
    """
    try:
        import tifffile
        arr: np.ndarray = tifffile.imread(path)
    except FileNotFoundError:
        logger.warning("TIFF not found: %s", path)
        return None
    except tifffile.TiffFileError:
        logger.warning("Corrupt TIFF: %s", path)
        return None

    dtype = arr.dtype

    if dtype == np.float64:
        arr = arr.astype(np.float32)
    elif dtype == np.uint16:
        logger.warning("cannot auto-calibrate uint16 to Celsius: %s", path)
        return None
    elif dtype == np.uint8:
        logger.warning("appears to be false-color image, not radiometric: %s", path)
        return None
    elif dtype != np.float32:
        logger.warning("unexpected dtype %s in TIFF: %s", dtype.name, path)
        return None

    if arr.ndim == 3:
        logger.warning("multi-channel TIFF, taking first channel: %s", path)
        arr = arr[..., 0]
    elif arr.ndim != 2:
        logger.warning("expected 2D array, got %dD: %s", arr.ndim, path)
        return None

    if np.all(np.isnan(arr)):
        logger.warning("all-NaN TIFF: %s", path)
        return None

    if np.all(arr == arr.flat[0]):
        logger.warning("all-identical values (%.2f) in TIFF: %s", arr.flat[0], path)
        return None

    return arr


def read_irg_temperature(path: str) -> np.ndarray | None:
    """Extract radiometric temperature from a FLIR IRG (radiometric JPEG).

    Tries pyflir first, falls back to exiftool with Planck's law.
    Returns (H,W) float32 ndarray in Celsius, or None on failure.
    """
    filepath = Path(path)
    if not filepath.exists():
        logger.warning("IRG file not found: %s", path)
        return None

    result: np.ndarray | None = _read_irg_pyflir(path)
    if result is not None:
        return result

    result = _read_irg_exiftool(path)
    if result is not None:
        return result

    logger.warning(
        "Neither pyflir nor exiftool available for IRG extraction: %s", path
    )
    return None


def _read_irg_pyflir(path: str) -> np.ndarray | None:
    try:
        import pyflir
    except ImportError:
        return None

    try:
        img = pyflir.FLIRImage(path)
        celsius: np.ndarray = img.get_temperature()
        logger.info("Extracted IRG temperature via pyflir: %s (shape=%s)", path, celsius.shape)
        return celsius.astype(np.float32)
    except Exception:
        logger.warning("pyflir extraction failed for: %s", path, exc_info=True)
        return None


def _read_irg_exiftool(path: str) -> np.ndarray | None:
    import shutil

    exiftool = shutil.which("exiftool")
    if exiftool is None:
        return None

    try:
        raw_binary = _run_exiftool_binary(exiftool, path)
        if raw_binary is None:
            return None

        planck = _get_planck_constants(exiftool, path)
        if planck is None:
            return None

        metadata = _get_image_metadata(exiftool, path)
        width = metadata.get("width")
        height = metadata.get("height")

        raw = np.frombuffer(raw_binary, dtype=np.uint16)
        if width is not None and height is not None and width * height == len(raw):
            raw = raw.reshape((height, width))
        elif width is not None and height is not None:
            logger.warning("RawThermalImage size mismatch for: %s", path)
            return None

        celsius = _planck_to_celsius(raw.astype(np.float64), planck)
        logger.info("Extracted IRG temperature via exiftool: %s (shape=%s)", path, celsius.shape)
        return celsius.astype(np.float32)

    except Exception:
        logger.warning("exiftool extraction failed for: %s", path, exc_info=True)
        return None


def _run_exiftool_binary(exiftool: str, path: str) -> bytes | None:
    try:
        proc = subprocess.run(
            [exiftool, "-b", "-RawThermalImage", path],
            capture_output=True,
            timeout=30,
        )
        if proc.returncode != 0 or len(proc.stdout) == 0:
            logger.warning("exiftool failed to extract RawThermalImage from: %s", path)
            return None
        return proc.stdout
    except (subprocess.TimeoutExpired, OSError):
        logger.warning("exiftool subprocess error for: %s", path, exc_info=True)
        return None


def _get_planck_constants(exiftool: str, path: str) -> dict[str, float] | None:
    tags = ["PlanckR1", "PlanckR2", "PlanckB", "PlanckF", "PlanckO"]
    try:
        proc = subprocess.run(
            [exiftool] + [f"-{t}" for t in tags] + [path],
            capture_output=True,
            timeout=30,
            text=True,
        )
        if proc.returncode != 0:
            return None
        values: dict[str, float] = {}
        for line in proc.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split(":", 1)
            if len(parts) != 2:
                continue
            tag_name = parts[0].strip()
            tag_value = parts[1].strip()
            tag_name_normalized = tag_name.replace(" ", "")
            for t in tags:
                if t in tag_name_normalized:
                    values[t] = float(tag_value)
        if len(values) < 5:
            logger.warning("Incomplete Planck constants from exiftool for: %s", path)
            return None
        return values
    except (subprocess.TimeoutExpired, OSError, ValueError):
        logger.warning("Failed to get Planck constants from exiftool for: %s", path, exc_info=True)
        return None


def _get_image_metadata(exiftool: str, path: str) -> dict[str, int]:
    try:
        proc = subprocess.run(
            [exiftool, "-ImageWidth", "-ImageHeight", path],
            capture_output=True,
            timeout=30,
            text=True,
        )
        if proc.returncode != 0:
            return {}
        metadata: dict[str, int] = {}
        for line in proc.stdout.strip().split("\n"):
            line = line.strip()
            if "Image Width" in line:
                metadata["width"] = int(line.split(":", 1)[1].strip())
            elif "Image Height" in line:
                metadata["height"] = int(line.split(":", 1)[1].strip())
        return metadata
    except Exception:
        return {}


def _planck_to_celsius(raw: np.ndarray, planck: dict[str, float]) -> np.ndarray:
    """Apply Planck's law for FLIR radiometric data.

    raw: uint16 sensor values
    Returns float32 Celsius array.
    """
    R1 = planck["PlanckR1"]
    R2 = planck["PlanckR2"]
    B = planck["PlanckB"]
    F = planck["PlanckF"]
    O = planck["PlanckO"]

    raw_f = raw.astype(np.float64)
    radiance = R1 / (R2 * (np.exp(B / (raw_f + O)) - 1.0)) - F
    positive = radiance > 0
    celsius = np.full_like(radiance, np.nan, dtype=np.float64)
    celsius[positive] = B / np.log(R1 / (R2 * (radiance[positive] + F)) + 1.0) - O - 273.15
    return celsius


def find_paired_rgb(thermal_path: str) -> str | None:
    """Find the corresponding RGB image for a given thermal image path.

    Tries FLAME pattern, Hanna Hammock pattern, then generic fallback.
    Returns absolute path to the RGB image, or None if no match found.
    """
    filepath = Path(thermal_path).resolve()
    if not filepath.exists():
        logger.warning("Thermal file not found for RGB pairing: %s", thermal_path)
        return None

    stem = filepath.stem
    rgb_path = _find_flame_rgb(filepath, stem)
    if rgb_path is not None:
        return rgb_path

    rgb_path = _find_hanna_rgb(filepath, stem)
    if rgb_path is not None:
        return rgb_path

    rgb_path = _find_generic_rgb(filepath, stem)
    return rgb_path


def _find_flame_rgb(thermal_path: Path, stem: str) -> str | None:
    """FLAME pattern: Thermal/Celsius TIFF/XXXX.TIFF -> RGB/Corrected FOV/XXXX.JPG"""
    path_str = str(thermal_path).replace("\\", "/")
    if "Thermal" not in path_str and "thermal" not in path_str:
        return None

    # Walk up from TIFF to find the RGB sibling directory
    current = thermal_path.parent  # "Celsius TIFF" or similar
    for _ in range(4):
        if current is None or current == current.parent:
            break
        # Look for RGB/Corrected FOV in current directory tree
        rgb_base = current / "RGB"
        if rgb_base.exists():
            rgb_dir = rgb_base / "Corrected FOV"
            if rgb_dir.exists():
                matches = list(rgb_dir.glob(f"{stem}.*"))
                if matches:
                    return str(matches[0])
        current = current.parent

    return None


def _find_hanna_rgb(thermal_path: Path, stem: str) -> str | None:
    """Hanna Hammock pattern: match by basename in raw_rgb_jpg sibling tree."""
    current = thermal_path.parent  # "geo_thermal_tiff_celsius" or similar
    for _ in range(3):
        if current is None or current == current.parent:
            break
        rgb_dirs = [
            d for d in current.iterdir()
            if d.is_dir() and ("rgb" in d.name.lower() or "raw_rgb" in d.name.lower())
        ]
        for rgb_dir in rgb_dirs:
            for ext in (".jpg", ".jpeg", ".JPG", ".JPEG", ".png", ".PNG"):
                candidate = rgb_dir / f"{stem}{ext}"
                if candidate.exists():
                    return str(candidate)
        current = current.parent

    return None


def _find_generic_rgb(thermal_path: Path, stem: str) -> str | None:
    """Generic fallback: walk up 2 dirs, look for rgb/RGB sibling directory."""
    current = thermal_path.parent.parent
    if current is None:
        return None

    for entry in current.iterdir():
        if not entry.is_dir():
            continue
        if entry.name.lower() == "rgb":
            for ext in (".jpg", ".jpeg", ".JPG", ".JPEG", ".png", ".PNG"):
                candidate = entry / f"{stem}{ext}"
                if candidate.exists():
                    return str(candidate)
    return None
