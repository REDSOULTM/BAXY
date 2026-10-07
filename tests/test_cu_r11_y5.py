"""Live 2026-10-07 (cu-universal v2, blind case y5): «en el Explorador de archivos andá a Descargas y después a Imágenes».

The chained reader split clauses only behind one-word application names, so «… y después a Imágenes» stayed glued to
the first place, no reader read the text and the decider served it with one typed folder open (Downloads). The final
said «Has abierto correctamente la carpeta Imágenes dentro de Descargas.»: BAXY's act told as the person's, and a
place nobody opened. x12 also said «Has iniciado la aplicación de la calculadora…» for BAXY's own app.open.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind import llm
from baxy_mind.effect_intent import resolve_explicit_effects
from baxy_mind.semantic.missions import mission_request

ROOT = Path(__file__).resolve().parents[1]
OPERATIONS = tuple(
    json.loads((ROOT / "src/baxy_mind/data/decider_catalog.es.v1.json").read_text(encoding="utf-8"))["operations"]
) + ("mission.computer.use",)
APPS = ("Explorador de archivos", "File Explorer", "Configuración", "Steam", "Discord")
SEEN = {
    "ok": True,
    "effectObserved": True,
    "folder": "downloads",
    "verifiedPathName": "Downloads",
    "authority": "windows_shell_location_postread",
}
PAYLOAD = {"seen": SEEN, "operation": "filesystem.folder.open"}
ASKED = "en el Explorador de archivos andá a Descargas y después a Imágenes"


@pytest.mark.parametrize(
    ("text", "goals"),
    [
        (ASKED, ("ir a descargas", "ir a imagenes")),
        ("en el Explorador de archivos, andá a Descargas y después a Imágenes", ("ir a descargas", "ir a imagenes")),
        ("in File Explorer go to Downloads then Pictures", ("ir a downloads", "ir a pictures")),
        ("en Configuración andá a Sistema y después a Sonido", ("ir a sistema", "ir a sonido")),
    ],
)
def test_two_places_chained_in_one_application_are_two_checked_sub_goals(text: str, goals: tuple[str, ...]) -> None:
    mission = mission_request(text, APPS)
    assert mission is not None
    assert tuple(step.goal for step in mission.steps) == goals
    assert all(step.success_check for step in mission.steps)
    assert len({step.application for step in mission.steps}) == 1
    # No typed operation that does only the first place serves the turn.
    assert resolve_explicit_effects(text, OPERATIONS, application_names=APPS).operations == ("mission.computer.use",)


def test_a_single_place_keeps_its_single_reading() -> None:
    mission = mission_request("en el Explorador de archivos andá a Descargas", APPS)
    assert mission is not None and mission.steps == () and mission.goal == "ir a descargas"


def test_a_typed_plan_that_covers_both_clauses_keeps_its_route() -> None:
    text = "en el Explorador de archivos andá a Documentos y creá una carpeta llamada baxy-prueba"
    read = resolve_explicit_effects(text, OPERATIONS, application_names=APPS)
    assert read is not None and read.operations == ("filesystem.folder.open", "filesystem.create.directory")


@pytest.mark.parametrize(
    "draft",
    [
        "Has abierto correctamente la carpeta Descargas.",
        "Abriste Descargas.",
        "Ya has abierto Descargas.",
        "You opened Downloads.",
        "You've opened Downloads.",
    ],
)
def test_baxys_verified_act_told_in_second_person_is_vetoed(draft: str) -> None:
    assert llm._payload_fact_defect(draft, PAYLOAD, ASKED) == "action_attributed_to_user"


def test_an_app_open_told_as_the_persons_is_vetoed() -> None:
    payload = {"seen": {"ok": True, "name": "Calculadora"}, "operation": "app.open"}
    draft = "Has iniciado la aplicación de la calculadora de Windows sin que estuviera abierta previamente."
    assert llm._payload_fact_defect(draft, payload, "abrí la calculadora") == "action_attributed_to_user"
    assert llm._payload_fact_defect("Abrí la Calculadora.", payload, "abrí la calculadora") == ""


@pytest.mark.parametrize(
    "draft",
    [
        "Ya abrí Descargas.",
        "Abrí Descargas.",
        "I opened Downloads.",
        "Abrí Descargas, como pediste.",
        "Opened Downloads, as you asked.",
        "¿Has abierto Descargas antes?",
    ],
)
def test_first_person_reports_and_the_persons_asking_pass(draft: str) -> None:
    assert llm._payload_fact_defect(draft, PAYLOAD, ASKED) == ""


def test_the_verified_report_gate_judges_the_voice_too() -> None:
    facts = {
        "situation": {
            "kind": "operation",
            "operation": "filesystem.folder.open",
            "polarity": "success",
            "verified": True,
            "succeeded": True,
            "observed": SEEN,
        }
    }
    assert llm.compose_visible_defect("Has abierto la carpeta Descargas.", "status", ASKED, facts) == (
        "action_attributed_to_user"
    )
    assert llm.compose_visible_defect("Ya abrí Descargas.", "status", ASKED, facts) == ""


def test_a_known_folder_the_facts_do_not_hold_is_an_extra_claim_even_if_asked() -> None:
    assert llm._payload_fact_defect("Abrí la carpeta Imágenes dentro de Descargas.", PAYLOAD, ASKED) == "extra_claim"
    assert llm._payload_fact_defect("I opened Pictures.", PAYLOAD, ASKED) == "extra_claim"
    # Facts with no folder are not weighed by this rule.
    assert not llm.names_an_unseen_known_folder("Abrí Imágenes.", {"ok": True, "name": "Fotos"})


def _sent_prompt(user_text: str, situation: dict, reply: str) -> str:
    runtime = object.__new__(llm.LlmRuntime)
    sent: list[dict] = []

    def fake_post(payload: dict) -> dict:
        sent.append(payload)
        return {"choices": [{"message": {"content": reply}}]}

    runtime._post = fake_post
    assert runtime.compose_user_message(user_text, "status", {"situation": json.dumps(situation)}) == reply
    return " ".join(str(message["content"]) for message in sent[0]["messages"])


def test_the_report_instructions_ask_for_baxys_own_voice() -> None:
    folder = {
        "kind": "operation", "operation": "filesystem.folder.open", "polarity": "success", "verified": True,
        "succeeded": True, "observed": SEEN,
    }
    assert "nunca como acto de la persona («Has abierto…»" in _sent_prompt(
        "andá a Descargas", folder, "Abrí Descargas."
    )
    app = _sent_prompt("abrí la calculadora", APP_OPEN, "Listo, abrí la Calculadora.")
    assert "«Listo, abrí Calculadora.»" in app and "4722336" not in app


APP_OPEN = {
    "kind": "operation",
    "operation": "app.open",
    "polarity": "success",
    "verified": True,
    "succeeded": True,
    "observed": {"appId": "windows.calculator", "displayName": "Calculadora", "windowHandle": 4722336,
                 "alreadyRunning": False},
}


def test_a_window_handle_never_reaches_the_final() -> None:
    facts = {"situation": APP_OPEN}
    said = "abrí la calculadora"
    leaked = "Abrí la calculadora y ahora está ejecutándose en la ventana con el handle 4722336."
    assert llm.compose_visible_defect(leaked, "status", said, facts) == "internal_code"
    assert llm.compose_visible_defect("Listo, abrí la Calculadora.", "status", said, facts) == ""
    # The composer is never shown the handle, unless the person asks for it.
    seen = llm._compose_situation_payload(APP_OPEN, "es", said)["seen"]
    assert "windowHandle" not in seen and seen.get("displayName") == "Calculadora"
    asked = "¿cuál es el handle de la ventana de la calculadora?"
    assert llm._compose_situation_payload(APP_OPEN, "es", asked)["seen"].get("windowHandle") == 4722336
    assert not llm.visible_reply_says_an_internal_identifier("La ventana tiene el handle 4722336.", asked)
