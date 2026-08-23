"""Goal 06: personalidad en el prompt, narrate usa compose, caminos feos sin constante."""

from pathlib import Path
import inspect

from baxy_mind import llm as llm_mod
from baxy_mind.llm import (
    CPU_USER_MESSAGE_PROMPT,
    NARRATOR_PROMPT,
    SYSTEM_PROMPT,
    USER_MESSAGE_PROMPT,
    visible_reply_invents_a_spanish_infinitive,
    visible_reply_is_a_fixed_stall,
)


ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "src/baxy_mind/__main__.py").read_text(encoding="utf-8")


def test_personality_lives_in_the_editable_prompt() -> None:
    prompt = USER_MESSAGE_PROMPT + "\n" + SYSTEM_PROMPT + "\n" + CPU_USER_MESSAGE_PROMPT
    assert "compañero" in prompt
    assert "un él" in prompt
    assert "Tuteas" in prompt
    assert "Listo," in USER_MESSAGE_PROMPT
    assert "No pude:" in USER_MESSAGE_PROMPT
    assert "estado observable" in USER_MESSAGE_PROMPT
    assert "eso no lo hago" in USER_MESSAGE_PROMPT
    assert "UNA frase" in USER_MESSAGE_PROMPT or "Una frase" in CPU_USER_MESSAGE_PROMPT
    assert "idioma del pedido" in prompt
    assert "fine-tun" not in prompt.casefold()
    assert NARRATOR_PROMPT == USER_MESSAGE_PROMPT


def test_narrate_is_compose_not_a_parallel_prompt() -> None:
    source = inspect.getsource(llm_mod.LlmRuntime.narrate)
    assert "compose_user_message" in source
    assert "NARRATOR_PROMPT" not in source


def test_recovery_compose_does_not_pass_a_spanish_constant() -> None:
    assert "No pude completar el análisis de tu petición." not in MAIN
    assert "request_analysis_failed" in MAIN


def test_invented_infinitives_and_stalls_are_still_rejected() -> None:
    assert visible_reply_invents_a_spanish_infinitive("No puedo cuecer las lentejas.")
    assert visible_reply_invents_a_spanish_infinitive("Cambia tetera por Descalzica.")
    assert visible_reply_is_a_fixed_stall("un momento…")
    assert not visible_reply_is_a_fixed_stall("Listo, Spotify está abierto y sonando")


def test_compose_rejects_invented_words_on_the_shipped_entry(monkeypatch) -> None:
    captured: list[str] = []

    class FakeClient(llm_mod.LlmRuntime):
        def __init__(self) -> None:  # noqa: D107
            pass

        def _post(self, payload):  # noqa: ANN001
            _ = payload
            return {"choices": [{"message": {"content": "No puedo cuecer las lentejas."}}]}

    client = FakeClient()
    text = client.compose_user_message(
        "cierra la olla",
        "error",
        {"situation": '{"kind":"failure","cause":"timeout","polarity":"failure"}'},
    )
    captured.append(text)
    assert text == ""
