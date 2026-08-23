"""Goal 06: personalidad en el prompt, narrate usa compose, caminos feos sin constante."""

from pathlib import Path
import inspect

from baxy_mind import llm as llm_mod
from baxy_mind.llm import (
    CPU_USER_MESSAGE_PROMPT,
    NARRATOR_PROMPT,
    SYSTEM_PROMPT,
    USER_MESSAGE_PROMPT,
    _named_state_hint,
    compose_visible_defect,
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


def test_named_state_hint_is_one_sentence_with_name_and_state() -> None:
    open_es = _named_state_hint(
        {"polarity": "success", "observed": {"app": "Word"}},
        "es",
        "abre Word",
    )
    assert open_es == "Word está abierto."
    assert "Una frase" not in open_es
    assert "Di " not in open_es
    open_en = _named_state_hint(
        {"polarity": "success", "observed": {"app": "Word"}},
        "en",
        "open Word",
    )
    assert open_en == "Word is open."
    assert "the app" not in open_en.casefold()
    assert "Say " not in open_en
    playing = _named_state_hint(
        {"polarity": "success", "observed": {"app": "Spotify", "playing": True}},
        "en",
        "open Spotify",
    )
    assert "Spotify is open and playing" in playing
    note = _named_state_hint(
        {"polarity": "success", "observed": {"title": "Ideas"}},
        "es",
        "crea una nota Ideas",
    )
    assert note == "la nota Ideas está creada."
    volume = _named_state_hint(
        {"polarity": "success", "observed": {"level": 80}},
        "es",
        "sube el volumen a 80",
    )
    assert volume == "el volumen está en 80."
    welcome = _named_state_hint(
        {"kind": "welcome", "polarity": "success"},
        "en",
        "hi",
    )
    assert welcome == ""
    assert _named_state_hint(
        {"polarity": "failure", "observed": {"app": "Word"}},
        "es",
        "abre Word",
    ) == ""


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


def test_compose_visible_defect_rejects_polarity_codes_and_copied_names() -> None:
    fail = {"situation": '{"kind":"failure","cause":"timeout","polarity":"failure","target":"Chrome"}'}
    assert compose_visible_defect(
        "Listo, Chrome no respondió.", "error", "cierra Chrome", fail
    ) == "reversed_polarity"
    assert compose_visible_defect(
        "No pude: provider_down", "error", "abre Spotify", fail
    ) == "internal_code"
    assert compose_visible_defect(
        "No pude: Spotify no responde.",
        "error",
        "cierra Chrome",
        fail,
    ) == "unmentioned_name"
    assert compose_visible_defect(
        "No pude: se agotó el tiempo.",
        "error",
        "cierra Chrome",
        fail,
    ) == ""
    assert compose_visible_defect(
        "Listo, hola.",
        "welcome",
        "hola",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == "welcome_opener"
    assert compose_visible_defect(
        "Listo, confirmar.",
        "confirmation",
        "borra la nota",
        {"situation": '{"kind":"confirmation","polarity":"pending","choices":["confirmar","cancelar"]}'},
    ) == "confirmation_asserted"
    assert compose_visible_defect(
        "¿Lo borro?",
        "confirmation",
        "borra la nota",
        {"situation": '{"kind":"confirmation","polarity":"pending","choices":["confirmar","cancelar"]}'},
    ) == "missing_confirmation_choice"
    assert compose_visible_defect(
        "No pude: Spotify no responde.",
        "error",
        "open Spotify",
        {
            "situation": (
                '{"kind":"failure","cause":"provider_down",'
                '"polarity":"failure","target":"Spotify"}'
            )
        },
    ) == "wrong_language"
    assert compose_visible_defect(
        "I couldn't: the provider is down.",
        "error",
        "open Spotify",
        {
            "situation": (
                '{"kind":"failure","cause":"provider_down",'
                '"polarity":"failure","target":"Spotify"}'
            )
        },
    ) == "internal_code"
    assert compose_visible_defect(
        "No pude: eso no lo hago.",
        "error",
        "order a pizza",
        {"situation": '{"kind":"failure","cause":"out_of_catalog","polarity":"failure"}'},
    ) == "wrong_language"
    assert compose_visible_defect(
        "I couldn't: I don't do that.",
        "error",
        "order a pizza",
        {"situation": '{"kind":"failure","cause":"out_of_catalog","polarity":"failure"}'},
    ) == ""
    assert compose_visible_defect(
        "¿Confirmas o cancelas borrar la nota?",
        "confirmation",
        "borra la nota",
        {"situation": '{"kind":"confirmation","polarity":"pending","choices":["confirmar","cancelar"]}'},
    ) == ""
    assert compose_visible_defect(
        "Do you confirm?",
        "confirmation",
        "delete the note Ideas",
        {"situation": '{"kind":"confirmation","polarity":"pending","choices":["confirm","cancel"]}'},
    ) == ""
    assert compose_visible_defect(
        "No la encontré.",
        "error",
        "abre Firefox",
        {"situation": '{"kind":"failure","cause":"app_not_found","polarity":"failure","target":"Firefox"}'},
    ) == ""
    assert compose_visible_defect(
        "Listo, Discord se silenció.",
        "status",
        "open Discord y silencia",
        {
            "situation": (
                '{"kind":"operation","operation":"app.open",'
                '"polarity":"success","observed":{"app":"Discord"}}'
            )
        },
    ) == "extra_claim"
    assert compose_visible_defect(
        "Listo, el estado observable es que el audio no está mutado.",
        "status",
        "reactiva el audio",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":false}}'
            )
        },
    ) == "internal_code"
    assert compose_visible_defect(
        "Listo, el audio ya no está silenciado.",
        "status",
        "reactiva el audio",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":false}}'
            )
        },
    ) == ""
    assert compose_visible_defect(
        "Spotifylight is playing.",
        "status",
        "open Spotify",
        {
            "situation": (
                '{"kind":"operation","operation":"app.open","polarity":"success",'
                '"observed":{"app":"Spotify","playing":true}}'
            )
        },
    ) == "invented"
    assert compose_visible_defect(
        "Listo, Word está abierto.",
        "status",
        "abre Word",
        {
            "situation": (
                '{"kind":"operation","operation":"app.open","polarity":"success",'
                '"observed":{"app":"Word"}}'
            )
        },
    ) == ""
    assert compose_visible_defect(
        "Say Word is open.",
        "status",
        "open Word",
        {
            "situation": (
                '{"kind":"operation","operation":"app.open","polarity":"success",'
                '"observed":{"app":"Word"}}'
            )
        },
    ) == "copied_instruction"
    assert compose_visible_defect(
        "No pude: se agotó el tiempo.",
        "error",
        "close Chrome",
        fail,
    ) == "wrong_language"


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
