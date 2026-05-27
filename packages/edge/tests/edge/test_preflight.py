"""Tests for edge/preflight.py — pre-flight checks with mocked filesystem."""
import sys
from unittest.mock import MagicMock, patch
import pytest
from edge.alerts import CriticalAlert


def _make_term_alert():
    alert = CriticalAlert.__new__(CriticalAlert)
    alert._backend = ("term", None, None)
    return alert


# ── camera checks ─────────────────────────────────────────────────────────────

def test_no_cameras_exits_with_code_1(monkeypatch, capsys):
    monkeypatch.setattr("edge.preflight._list_video_devices", lambda: [])
    alert = _make_term_alert()
    beeps = []
    alert.beep = lambda n, **kw: beeps.append(n)

    with pytest.raises(SystemExit) as exc:
        import edge.preflight as pf
        # patch engine check so it doesn't interfere
        with patch("edge.preflight._check_engine"):
            with patch("edge.preflight._warn_audio_backend"):
                pf._check_cameras(alert)
    assert exc.value.code == 1
    assert beeps == [1]


def test_cameras_present_does_not_exit(monkeypatch, capsys):
    monkeypatch.setattr("edge.preflight._list_video_devices", lambda: ["/dev/video0"])
    alert = _make_term_alert()
    import edge.preflight as pf
    pf._check_cameras(alert)  # should not raise


# ── engine checks ─────────────────────────────────────────────────────────────

def test_missing_engine_exits_with_code_3(tmp_path, monkeypatch):
    monkeypatch.setattr("edge.preflight.MODEL_ENGINE_PATH", str(tmp_path / "missing.engine"))
    alert = _make_term_alert()
    beeps = []
    alert.beep = lambda n, **kw: beeps.append(n)

    with pytest.raises(SystemExit) as exc:
        import edge.preflight as pf
        pf._check_engine(alert)

    assert exc.value.code == 3
    assert beeps == [3]


def test_engine_present_does_not_exit(tmp_path, monkeypatch):
    engine = tmp_path / "best.engine"
    engine.write_bytes(b"\x00" * 100)
    monkeypatch.setattr("edge.preflight.MODEL_ENGINE_PATH", str(engine))
    alert = _make_term_alert()
    import edge.preflight as pf
    pf._check_engine(alert)  # should not raise


# ── full run ──────────────────────────────────────────────────────────────────

def test_preflight_passes_when_all_ok(tmp_path, monkeypatch):
    engine = tmp_path / "best.engine"
    engine.write_bytes(b"\x00" * 100)
    monkeypatch.setattr("edge.preflight._list_video_devices", lambda: ["/dev/video0"])
    monkeypatch.setattr("edge.preflight.MODEL_ENGINE_PATH", str(engine))
    alert = _make_term_alert()
    import edge.preflight as pf
    pf.run(alert=alert)  # should not raise or exit
