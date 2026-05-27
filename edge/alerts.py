"""
Audible alert system for Jetson edge deployment.

Operators cannot see a screen while the Jetson is mounted on the drone.
Critical failures emit a specific number of beeps so the operator can
diagnose the problem by ear and then connect a screen if needed.

Beep codes:
  1 beep  — no camera connected
  2 beeps — convergence API (FastAPI) not responding
  3 beeps — TensorRT engine file missing or unreadable
  4 beeps — unclassified fatal error (catch-all)

Backend cascade (first available wins):
  1. Jetson.GPIO  — active buzzer wired to a GPIO pin (most reliable on drone)
  2. aplay        — synthesised 880 Hz sine tone via ALSA (HDMI / USB audio)
  3. terminal \a  — ASCII bell (last resort; silent on most headless systems)
"""
from __future__ import annotations

import io
import math
import os
import shutil
import struct
import sys
import time
import wave
import logging

logger = logging.getLogger(__name__)

BUZZER_GPIO_PIN: int = int(os.environ.get("BUZZER_GPIO_PIN", "7"))
BEEP_DURATION_S: float = float(os.environ.get("CRITICAL_BEEP_DURATION_S", "0.6"))
BEEP_GAP_S: float = 0.35
BEEP_FREQ_HZ: float = 880.0  # A5 — easy to hear over engine noise


def _generate_beep_wav(duration_s: float, freq_hz: float = BEEP_FREQ_HZ) -> bytes:
    """Return a mono 16-bit PCM WAV byte string of a sine tone."""
    sample_rate = 16_000
    n_samples = max(1, int(sample_rate * duration_s))
    amplitude = 20_000  # int16 max is 32767
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            sample = int(amplitude * math.sin(2 * math.pi * freq_hz * i / sample_rate))
            frames += struct.pack("<h", sample)
        w.writeframes(bytes(frames))
    return buf.getvalue()


class CriticalAlert:
    """Emits audible beeps using the best available audio backend."""

    def __init__(self, gpio_pin: int = BUZZER_GPIO_PIN) -> None:
        self._backend = self._detect_backend(gpio_pin)
        logger.info("Audio backend: %s", self._backend[0])

    def _detect_backend(self, pin: int) -> tuple:
        try:
            import Jetson.GPIO as GPIO  # type: ignore[import]
            GPIO.setmode(GPIO.BOARD)
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
            logger.info("Jetson.GPIO available on pin %d", pin)
            return ("gpio", GPIO, pin)
        except Exception as e:
            logger.debug("Jetson.GPIO unavailable (%s), trying aplay", e)

        if shutil.which("aplay"):
            logger.info("aplay available, using ALSA audio")
            return ("aplay", None, None)

        logger.warning("No hardware audio backend found; using terminal bell (may be silent)")
        return ("term", None, None)

    def beep(self, times: int, duration_s: float = BEEP_DURATION_S) -> None:
        """Emit `times` beeps with the configured backend."""
        for i in range(times):
            self._tick(duration_s)
            if i < times - 1:
                time.sleep(BEEP_GAP_S)

    def _tick(self, duration_s: float) -> None:
        backend = self._backend[0]
        try:
            if backend == "gpio":
                _, GPIO, pin = self._backend
                GPIO.output(pin, GPIO.HIGH)
                time.sleep(duration_s)
                GPIO.output(pin, GPIO.LOW)
            elif backend == "aplay":
                import subprocess
                wav_bytes = _generate_beep_wav(duration_s)
                subprocess.run(
                    ["aplay", "-q", "-t", "wav", "-"],
                    input=wav_bytes,
                    timeout=duration_s + 2.0,
                    check=False,
                )
            else:
                sys.stdout.write("\a")
                sys.stdout.flush()
                time.sleep(duration_s)
        except Exception as exc:
            logger.error("Beep failed (%s): %s", backend, exc)

    def cleanup(self) -> None:
        if self._backend[0] == "gpio":
            try:
                _, GPIO, _ = self._backend
                GPIO.cleanup()
            except Exception:
                pass
