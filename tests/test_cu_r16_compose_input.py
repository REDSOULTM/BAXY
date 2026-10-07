"""Ronda 16 (2026-10-07, auditoría de voz v2): el final de una misión de computer use se redacta sólo con el pedido de
este turno y los hechos de esta misión, con una instrucción de voz propia (primera persona, pretérito, tuteo, una frase
corta) y sin muestreo en ningún intento. Las demás operaciones no cambian."""

import json

from baxy_mind import llm

PREVIOUS_ANSWER = "MARCA-RESPUESTA-PREVIA Ya estoy en Red e Internet, donde busco la opción de Wi-Fi."
PRIOR_REQUEST = "MARCA-PEDIDO-PREVIO abrí Configuración"

MISSION = {
    "kind": "operation",
    "operation": "mission.computer.use",
    "polarity": "success",
    "verified": True,
    "succeeded": True,
    "observed": {
        "goal": "ir a temas",
        "reached": True,
        "stepsDone": ["trajo la aplicación al frente", "clic en «Personalización»", "clic en «Temas»"],
        "windowTitle": "Configuración",
        "joined": False,
        "application": "Configuración",
        "satisfiedBy": "header:temas",
        "screen": {"title": "Configuración", "values": [{"name": "Temas", "state": "selected"}]},
    },
}

# cu-r17: a mission without a question is told from its facts before any draft (floor-first); one whose goal carries
# the person's question still reaches the model, so the prompt and the sampler are read on it.
ASKED_MISSION = dict(MISSION)
ASKED_MISSION["observed"] = dict(
    MISSION["observed"],
    goal="ir a temas; y responder: ¿el modo es claro u oscuro?",
    screen={"title": "Configuración", "values": [{"name": "Temas", "state": "selected"}, {"name": "Modo", "value": "Oscuro"}]},
)

APP_OPEN = {
    "kind": "operation",
    "operation": "app.open",
    "polarity": "success",
    "verified": True,
    "succeeded": True,
    "observed": {"appId": "windows.calculator", "displayName": "Calculadora", "alreadyRunning": False},
}


def _sent(user_text: str, situation: dict, reply: str, intent: str = "status") -> list[dict]:
    runtime = object.__new__(llm.LlmRuntime)
    sent: list[dict] = []

    def fake_post(payload: dict, **_: object) -> dict:
        sent.append(payload)
        return {"choices": [{"message": {"content": reply}}]}

    runtime._post = fake_post
    facts = {
        "situation": json.dumps(situation),
        "context": PREVIOUS_ANSWER,
        "priorRequests": [PRIOR_REQUEST, "y ahora andá a Temas"],
    }
    runtime.compose_user_message(user_text, intent, facts)
    return sent


def _text(payload: dict) -> str:
    return "\n".join(str(message["content"]) for message in payload["messages"])


def test_a_computer_use_final_sees_no_earlier_turn_in_any_attempt() -> None:
    # A draft the vetoes refuse (a change claimed on a go-to goal) runs the retry and the third attempt.
    sent = _sent("y ahora andá a Temas", ASKED_MISSION, "Ya activé el modo oscuro en Temas.")
    assert len(sent) == 3
    for payload in sent:
        prompt = _text(payload)
        assert "MARCA-RESPUESTA-PREVIA" not in prompt and "MARCA-PEDIDO-PREVIO" not in prompt
        assert "previous_dialogue_for_references_only" not in prompt
        assert llm.COMPUTER_USE_VOICE_PROMPT_ES in prompt and llm.COMPUTER_USE_VOICE_LENGTH_ES in prompt


def test_a_computer_use_final_told_as_conversation_still_sees_no_earlier_turn() -> None:
    for payload in _sent("¿y ahora dónde estás?", ASKED_MISSION, "Llegué a Temas.", intent="conversation"):
        prompt = _text(payload)
        assert "MARCA-RESPUESTA-PREVIA" not in prompt and "MARCA-PEDIDO-PREVIO" not in prompt
        assert llm.COMPUTER_USE_VOICE_PROMPT_ES in prompt


def test_every_attempt_of_a_computer_use_final_is_greedy() -> None:
    sent = _sent("y ahora andá a Temas", ASKED_MISSION, "Ya activé el modo oscuro en Temas.")
    assert [payload.get("temperature") for payload in sent] == [0.0, 0.0, 0.0]
    assert not any(key in payload for payload in sent for key in ("top_p", "top_k", "seed"))


def test_an_english_request_gets_the_english_voice() -> None:
    prompt = _text(_sent("go to Themes in Settings", ASKED_MISSION, "I went to Themes in Settings.")[0])
    assert llm.COMPUTER_USE_VOICE_PROMPT_EN in prompt and llm.COMPUTER_USE_VOICE_LENGTH_EN in prompt
    assert llm.COMPUTER_USE_VOICE_PROMPT_ES not in prompt


def test_a_mission_that_did_not_reach_its_goal_keeps_its_own_length() -> None:
    failed = dict(MISSION, polarity="failure", succeeded=False)
    failed["observed"] = dict(MISSION["observed"], reached=False, satisfiedBy=None)
    instruction = llm._computer_use_voice_instruction(failed, "es")
    assert instruction == llm.COMPUTER_USE_VOICE_PROMPT_ES


def test_other_operations_keep_their_prompt_and_sampler() -> None:
    # A conversation still carries the previous answer it refers to; an operation gets no computer-use voice.
    for payload in _sent("abrí la calculadora", APP_OPEN, "Listo, abrí la Calculadora."):
        assert llm.COMPUTER_USE_VOICE_PROMPT_ES not in _text(payload)
    retried = _sent("abrí la calculadora", APP_OPEN, "Has abierto la Calculadora, como te dije antes.")
    assert len(retried) >= 2 and retried[1].get("temperature") == 0.7 and retried[1].get("seed") == 1
    assert all(llm.COMPUTER_USE_VOICE_PROMPT_ES not in _text(payload) for payload in retried)
    chat = _sent("¿y eso qué significa?", {"kind": "conversation", "polarity": "success"}, "Significa eso.",
                 intent="conversation")
    assert "MARCA-RESPUESTA-PREVIA" in _text(chat[0])
