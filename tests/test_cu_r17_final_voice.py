"""Ronda 17 (2026-10-07): the 4B composer still wrote «Abrí Configuración.» when the app was already running and
when the person had asked «decime el volumen»; a machine-actor retry of a mission final sampled at 0.7."""

import json

from baxy_mind import llm

ASKED = {
    "kind": "operation",
    "operation": "mission.computer.use",
    "polarity": "success",
    "verified": True,
    "succeeded": True,
    "observed": {
        "goal": "ir a sonido; y responder: decime el volumen",
        "reached": True,
        "application": "Configuración",
        "window": {"title": "Configuración"},
        "steps": [
            {"operation": "app.open", "ok": True, "alreadyRunning": True, "name": "Configuración"},
            {"operation": "input.visible.click", "ok": True, "label": "Sistema"},
            {"operation": "input.visible.click", "ok": True, "label": "Sonido"},
        ],
        "screen": {"title": "Configuración", "numbers": ["Volumen 40"], "lines": ["Volumen 40", "Salida"]},
    },
}


def _facts(situation: dict) -> dict:
    return {"situation": json.dumps(situation)}


def _defect(text: str, situation: dict = ASKED) -> str:
    return llm.compose_visible_defect(text, "status", "andá a sonido y decime el volumen", _facts(situation))


def test_the_voice_instruction_names_no_opening_verb() -> None:
    assert "abrí" not in llm.COMPUTER_USE_VOICE_PROMPT_ES.casefold().split("«")[1]
    assert "I opened" not in llm.COMPUTER_USE_VOICE_PROMPT_EN


def test_an_app_already_running_is_not_told_as_opened() -> None:
    assert llm._computer_use_final_defect("Abrí Configuración y llegué a Sonido.", ASKED) == "extra_claim"
    assert llm._computer_use_final_defect("I opened Configuración.", ASKED) == "extra_claim"


def test_an_app_opened_cold_may_be_told_as_opened() -> None:
    cold = json.loads(json.dumps(ASKED))
    cold["observed"]["steps"][0]["alreadyRunning"] = False
    assert llm._computer_use_final_defect("Abrí Configuración: el volumen está en 40.", cold) == ""


def test_a_question_of_the_mission_is_answered() -> None:
    assert llm._computer_use_final_defect("Llegué a Sonido en Configuración.", ASKED) == "unanswered_question"
    assert _defect("Llegué a Sonido en Configuración.") == "unanswered_question"
    assert llm._computer_use_final_defect("El volumen está en 40.", ASKED) == ""
    assert llm._computer_use_final_defect("No pude ver el volumen en Sonido.", ASKED) == ""


def test_the_question_is_in_the_voice_instruction() -> None:
    instruction = llm._computer_use_voice_instruction(ASKED, "es")
    assert "decime el volumen" in instruction and "no lo pude ver" in instruction
    english = llm._computer_use_voice_instruction(ASKED, "en")
    assert "decime el volumen" in english and "could not see it" in english


def test_a_mission_without_a_question_owes_no_answer() -> None:
    plain = json.loads(json.dumps(ASKED))
    plain["observed"]["goal"] = "ir a sonido"
    assert llm._computer_use_final_defect("Llegué a Sonido.", plain) == ""


def test_a_machine_actor_retry_of_a_mission_final_stays_greedy() -> None:
    payload = {"messages": [{"role": "user", "content": "x"}], "temperature": 0.0}
    gguf = "qwen3-4b-instruct-2507-Q4_K_M.gguf"
    assert llm._machine_actor_repair_payload(payload, "draft", gguf, greedy=True)["temperature"] == 0.0
    assert llm._machine_actor_repair_payload(payload, "draft", gguf)["temperature"] == 0.7
