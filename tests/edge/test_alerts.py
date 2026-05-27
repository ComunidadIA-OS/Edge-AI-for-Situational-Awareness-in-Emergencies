"""Tests for edge/alerts.py — CriticalAlert with mocked backends."""
import time
from unittest.mock import MagicMock, patch
import pytest
from edge.alerts import CriticalAlert


@pytest.fixture()
def term_alert(monkeypatch):
    """CriticalAlert forced onto the 'term' backend."""
    with patch("edge.alerts.CriticalAlert._detect_backend", return_value=("term", None, None)):
        alert = CriticalAlert.__new__(CriticalAlert)
        alert._backend = ("term", None, None)
        yield alert


def test_term_beep_does_not_raise(term_alert):
    term_alert.beep(1, duration_s=0.0)
    term_alert.beep(4, duration_s=0.0)


def test_beep_calls_correct_count(term_alert, capsys):
    import sys
    written = []
    original_write = sys.stdout.write

    with patch.object(sys.stdout, "write", side_effect=lambda s: written.append(s)):
        term_alert.beep(3, duration_s=0.0)

    bell_count = sum(1 for s in written if "\a" in s)
    assert bell_count == 3


def test_gpio_backend_calls_setup_and_cleanup():
    mock_gpio = MagicMock()
    mock_gpio.BOARD = "BOARD"
    mock_gpio.OUT = "OUT"
    mock_gpio.LOW = 0
    mock_gpio.HIGH = 1

    alert = CriticalAlert.__new__(CriticalAlert)
    alert._backend = ("gpio", mock_gpio, 7)

    alert._tick(duration_s=0.0)

    mock_gpio.output.assert_any_call(7, mock_gpio.HIGH)
    mock_gpio.output.assert_any_call(7, mock_gpio.LOW)


def test_cleanup_calls_gpio_cleanup():
    mock_gpio = MagicMock()
    alert = CriticalAlert.__new__(CriticalAlert)
    alert._backend = ("gpio", mock_gpio, 7)
    alert.cleanup()
    mock_gpio.cleanup.assert_called_once()


def test_cleanup_on_term_does_not_raise(term_alert):
    term_alert.cleanup()


def test_aplay_backend_calls_subprocess(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/aplay" if cmd == "aplay" else None)
    monkeypatch.setattr("os.path.exists", lambda p: True)

    with patch("subprocess.run") as mock_run:
        alert = CriticalAlert.__new__(CriticalAlert)
        alert._backend = ("aplay", None, None)
        alert._tick(duration_s=0.1)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "aplay"
