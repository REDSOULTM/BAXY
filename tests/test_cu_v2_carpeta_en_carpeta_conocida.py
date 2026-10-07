"""Live 2026-10-07: «en el Explorador de archivos andá a Documentos y creá una carpeta llamada baxy-prueba».

The decider planned filesystem.folder.open + filesystem.create.directory. No reader read either clause, so both steps
went to the model's argument extraction, which left the folder out; its question («¿en qué carpeta…?») was vetoed by
the App (machine_slot_ask), every recomposition failed and the person read «⚠ (internal_code;retry_exhausted)».

Going to a known folder and creating a named folder there is two catalog effects: the folder opened, and the new
folder made inside it (unless the creation names another). Both steps ground from what was said, nothing is asked.
The line a failed composition leaves is the operation floor's data sentence, never the diagnostic code.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import operation_floor
from baxy_mind.effect_intent import resolve_explicit_effects
from baxy_mind.semantic import decider
from baxy_mind.semantic.arguments import _explicit_arguments_from_evidence
from baxy_mind.semantic.patterns import folder_then_directory_request

ROOT = Path(__file__).resolve().parents[1]
OPERATIONS = tuple(
    json.loads((ROOT / "src/baxy_mind/data/decider_catalog.es.v1.json").read_text(encoding="utf-8"))["operations"]
) + ("mission.computer.use",)
APPS = ("Explorador de archivos", "File Explorer", "Steam", "Bloc de notas")
PLAN = ("filesystem.folder.open", "filesystem.create.directory")


@pytest.mark.parametrize(
    ("text", "opened", "created", "name"),
    [
        # the live turn
        ("en el Explorador de archivos andá a Documentos y creá una carpeta llamada baxy-prueba",
         "documents", "documents", "baxy-prueba"),
        ("Baxy, andá a documentos y creá una carpeta llamada Baxy-Prueba", "documents", "documents", "Baxy-Prueba"),
        ("abrí el escritorio y creá una carpeta llamada Facturas", "desktop", "desktop", "Facturas"),
        ("ve a la carpeta de descargas, creá una carpeta nueva llamada fotos2024", "downloads", "downloads", "fotos2024"),
        # the creation that names its own folder keeps it
        ("abrí el escritorio y creá una carpeta llamada x en descargas", "desktop", "downloads", "x"),
        ("in File Explorer go to Documents and create a folder named baxy-test", "documents", "documents", "baxy-test"),
        ("open my Downloads folder and then make a new folder called Reports", "downloads", "downloads", "Reports"),
    ],
)
def test_going_to_a_known_folder_and_creating_one_plans_both_steps_without_asking(
    text: str, opened: str, created: str, name: str,
) -> None:
    read = resolve_explicit_effects(text, OPERATIONS, application_names=APPS)
    assert read is not None and read.operations == PLAN

    # The plan request of the turn the decider decided: each step grounds from its clause, on the person's surface.
    found = sidecar._plan_effects_read(text, PLAN, OPERATIONS, [])
    evidence = sidecar._evidence_of_expected_operations(PLAN, found.operations, found.evidence)
    assert evidence is not None
    surfaces = sidecar._restore_evidence_surfaces(text, evidence)
    steps = sidecar._expand_effect_plan(PLAN, surfaces)
    assert [operation for operation, _ in steps] == list(PLAN)
    assert _explicit_arguments_from_evidence(steps[0][0], steps[0][1]) == {"folder": opened}
    assert _explicit_arguments_from_evidence(steps[1][0], steps[1][1]) == {"relativePath": name, "folder": created}


def test_a_creation_decided_alone_takes_the_folder_gone_to() -> None:
    # The decider may decide only the creation: its evidence is the whole message.
    text = "andá a Documentos y creá una carpeta llamada baxy-prueba"
    assert _explicit_arguments_from_evidence("filesystem.create.directory", text) == {
        "relativePath": "baxy-prueba", "folder": "documents",
    }


@pytest.mark.parametrize(
    "text",
    [
        "andá a Documentos",  # no creation: not this reading
        "andá a Imágenes y creá una carpeta llamada x",  # not a creation root
        "andá a Documentos y creá una carpeta",  # no name: asked, not invented
        "andá a Documentos y borrá la carpeta x",
    ],
)
def test_only_a_named_creation_after_a_known_root_is_read(text: str) -> None:
    assert folder_then_directory_request(text) is None


def test_the_plain_creation_and_open_readings_are_unchanged() -> None:
    assert resolve_explicit_effects(
        "crea una carpeta llamada x en documentos", OPERATIONS, application_names=APPS,
    ).operations == ("filesystem.create.directory",)
    assert _explicit_arguments_from_evidence("filesystem.create.directory", "crea una carpeta llamada x") == {
        "relativePath": "x",
    }
    assert _explicit_arguments_from_evidence("filesystem.folder.open", "abrí la carpeta de Descargas") == {
        "folder": "downloads",
    }
    assert _explicit_arguments_from_evidence("filesystem.folder.open", "abrí Descargas y Documentos") is None


def test_the_failed_composition_line_is_not_a_reply_of_baxy_for_the_decider() -> None:
    lines = operation_floor.floor_data()["compositionFailures"]
    assert set(lines) == {"clarification", "result", "default"}
    for line in lines.values():
        assert line["es"] and line["en"]
        assert "⚠" not in line["es"] + line["en"]
    said = lines["clarification"]["es"]
    history = [
        {"role": "user", "content": "andá a Documentos y creá una carpeta"},
        {"role": "assistant", "content": said},
    ]

    sent = decider.messages("system", "llamala baxy-prueba", history)

    assert [turn["content"] for turn in sent[1:]] == ["andá a Documentos y creá una carpeta", "llamala baxy-prueba"]
