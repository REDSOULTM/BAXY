from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind.effect_intent import (
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)
from baxy_mind.planner import required_predecessors


REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "artifacts/holdout/generalization_surface_holdout_v1.jsonl"
PROMOTED = (
    REPO / "artifacts/development/generalization_surface_r1_failures.v1.jsonl"
)


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


CORPUS_ROWS = _jsonl(CORPUS)
PROMOTED_ROWS = _jsonl(PROMOTED)
AVAILABLE = {
    operation
    for row in CORPUS_ROWS
    for group in row["compatible_terminal_operation_sets"]
    for operation in group
}
APPLICATIONS = ("Bloc de notas", "Notepad", "Steam")


def _terminal_operations(operations: tuple[str, ...]) -> tuple[str, ...]:
    ordered = tuple(dict.fromkeys(operations))
    technical = {
        predecessor
        for operation in ordered
        for predecessor in required_predecessors(operation)
        if predecessor in ordered
    }
    return tuple(operation for operation in ordered if operation not in technical)


@pytest.mark.parametrize(
    "row",
    PROMOTED_ROWS,
    ids=lambda row: str(row["case_id"]),
)
def test_opened_r1_failures_are_deterministic_development_regressions(
    row: dict[str, object],
) -> None:
    result = resolve_explicit_effects(
        str(row["text"]),
        AVAILABLE,
        APPLICATIONS,
    )
    if (
        row["family"] == "message"
        and not any(
            channel in str(row["text"]).casefold()
            for channel in ("whatsapp", "discord", "wsp")
        )
    ):
        clarification = resolve_explicit_clarification_intent(
            str(row["text"]),
            AVAILABLE,
        )
        assert result is None
        assert clarification is not None
        assert clarification.operations == ("message.send",)
        assert "channel" in clarification.missing_fields
        return
    accepted = {
        tuple(group) for group in row["compatible_terminal_operation_sets"]
    }
    if ("vision.describe",) in accepted:
        # SCREEN1417 (ec963d3ef): describing the screen reads its text by OCR
        # and says images are out of reach; the corpus predates that reading.
        accepted.add(("ocr.read",))

    assert result is not None
    assert _terminal_operations(result.operations) in accepted


@pytest.mark.parametrize(
    ("text", "forbidden"),
    [
        ("¿Cómo está la red neuronal?", {"network.status"}),
        ("Consulta el estado de la memoria RAM del sistema", {"memory.status"}),
        ("Captura al ladrón y lee su texto", {"capture.screenshot", "ocr.read"}),
        (
            "Prepara la instalación mañana de VideoLAN.VLC",
            {"package.install.prepare"},
        ),
        (
            "Busca Dark en Netflix para mañana y ponla",
            {"streaming.play.named"},
        ),
        (
            "Crea una nota llamada Captura pantalla y extrae texto",
            {"capture.screenshot", "ocr.read"},
        ),
        ("Dime qué se está reproduciendo en mi cabeza", {"media.status"}),
        ("Lista los respaldos del trabajo", {"backup.list"}),
        ("Muéstrame los dispositivos USB de mi teléfono", {"peripheral.list"}),
        ("Read the latest inbox message from my phone", {"email.latest.read"}),
    ],
)
def test_nearby_domains_and_deferred_effects_never_gain_strict_authority(
    text: str,
    forbidden: set[str],
) -> None:
    result = resolve_explicit_effects(text, AVAILABLE, APPLICATIONS)
    operations = set(result.operations) if result is not None else set()

    assert operations.isdisjoint(forbidden)


def test_explicit_unknown_app_query_is_a_safe_verified_inventory_read() -> None:
    result = resolve_explicit_effects(
        "Find out if Python is installed",
        AVAILABLE,
        APPLICATIONS,
    )

    assert result is not None
    assert result.operations == ("app.installed",)
