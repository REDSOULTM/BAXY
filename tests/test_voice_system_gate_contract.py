from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VOICE_GATE = ROOT / "scripts" / "run_voice_system_gate.py"


def test_product_voice_gate_requires_the_calibrated_acoustic_wake_backend() -> None:
    source = VOICE_GATE.read_text(encoding="utf-8")

    assert 'probe.get("wakeWord") is True' in source
    assert 'probe.get("wakeBackend") == "acoustic"' in source
    assert 'hardware.get("wake_backend") == "acoustic"' in source


def test_product_voice_gate_does_not_report_the_legacy_backend_as_current() -> None:
    source = VOICE_GATE.read_text(encoding="utf-8")

    assert "LiveKit WakeWord ONNX acoustic detector" not in source
    assert "Hyperspotter cascade" in source
