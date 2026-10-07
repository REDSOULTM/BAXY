"""Live a3 (2026-10-07): «open Settings, go to Accessibility and then to Text size» on a Spanish Settings."""

from baxy_mind.semantic import missions


def test_text_size_carries_its_spanish_name() -> None:
    request = missions.mission_request("open Settings, go to Accessibility and then to Text size", ["Configuración"])
    assert request is not None
    checks = [step.success_check or "" for step in request.steps]
    assert any("tamano de texto" in check for check in checks)
    assert "text size" in missions.label_alternatives("tamaño de texto")
