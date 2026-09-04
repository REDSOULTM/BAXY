"""Goal 06: personalidad en el prompt, narrate usa compose, caminos feos sin constante."""

from pathlib import Path
import inspect
import json

from baxy_mind import llm as llm_mod
from baxy_mind.llm import (
    CPU_USER_MESSAGE_PROMPT,
    NARRATOR_PROMPT,
    SYSTEM_PROMPT,
    USER_MESSAGE_PROMPT,
    _compose_shape_instruction,
    _compose_situation_payload,
    _local_clock_from_observed,
    compose_visible_defect,
    visible_reply_invents_a_spanish_infinitive,
    visible_reply_is_a_fixed_stall,
)


ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "src/baxy_mind/__main__.py").read_text(encoding="utf-8")


def test_early_signal_production_path_uses_compose_not_snippet_template() -> None:
    assert "formulate_progress" not in MAIN
    assert '"cause": "acting"' in MAIN


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


def test_shape_instruction_is_not_the_published_sentence() -> None:
    open_es = _compose_shape_instruction(
        {"polarity": "success", "observed": {"app": "Word"}},
        "es",
        "abre Word",
    )
    assert "Listo, Word está abierto" not in open_es
    assert "observed.app" in open_es
    open_en = _compose_shape_instruction(
        {"polarity": "success", "observed": {"app": "Word"}},
        "en",
        "open Word",
    )
    assert "Word is open" not in open_en
    note = _compose_shape_instruction(
        {"polarity": "success", "observed": {"title": "Ideas"}},
        "es",
        "crea una nota Ideas",
    )
    assert "la nota Ideas está creada" not in note
    welcome = _compose_shape_instruction(
        {"kind": "welcome", "polarity": "success"},
        "en",
        "hi",
    )
    assert welcome == ""
    close = _compose_shape_instruction(
        {"kind": "operation", "polarity": "success"},
        "en",
        "close the window",
    )
    assert "The window is closed." not in close
    assert "Name the window" not in close


def test_compose_payload_does_not_contain_published_sentences() -> None:
    captured: list[dict] = []

    class FakeClient(llm_mod.LlmRuntime):
        def __init__(self) -> None:  # noqa: D107
            pass

        def _post(self, payload):  # noqa: ANN001
            captured.append(payload)
            return {"choices": [{"message": {"content": "Listo, Word está abierto."}}]}

    client = FakeClient()
    client.compose_user_message(
        "abre Word",
        "status",
        {
            "situation": (
                '{"kind":"operation","operation":"app.open","polarity":"success",'
                '"verified":true,"observed":{"app":"Word"}}'
            )
        },
    )
    blob = json.dumps(captured, ensure_ascii=False)
    assert "Listo, Word está abierto" not in blob
    captured.clear()
    client.compose_user_message(
        "ábrela",
        "clarification",
        {"situation": '{"kind":"clarification","cause":"ambiguous_request","polarity":"pending"}'},
    )
    blob = json.dumps(captured, ensure_ascii=False)
    assert "¿Qué quieres abrir?" not in blob
    assert "What do you want to open?" not in blob
    captured.clear()
    client.compose_user_message(
        "abre Steam",
        "error",
        {
            "situation": (
                '{"kind":"failure","cause":"app_not_found","polarity":"failure",'
                '"target":"Steam"}'
            )
        },
    )
    blob = json.dumps(captured, ensure_ascii=False)
    assert "no la encontré" not in blob.casefold()
    assert "Listo, Word está abierto" not in blob
    assert compose_visible_defect(
        "The app is open.",
        "status",
        "open Discord",
        {
            "situation": (
                '{"kind":"operation","polarity":"success",'
                '"observed":{"app":"Discord"}}'
            )
        },
    ) == "missing_name"
    assert compose_visible_defect(
        "Hola, ¿cómo te va?",
        "welcome",
        "",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == "welcome_question"
    assert compose_visible_defect(
        "Listo, Steam está abierto.",
        "status",
        "cierra Steam",
        {
            "situation": (
                '{"kind":"operation","polarity":"success","observed":{"app":"Steam"}}'
            )
        },
    ) == "reversed_result"
    assert compose_visible_defect(
        "Sigo trabajando en el estado observable.",
        "status",
        "abre Steam y ve a la biblioteca",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    ) == "internal_code"
    assert compose_visible_defect(
        "I couldn't: I opened Word.",
        "error",
        "open Word and wipe the disk",
        {
            "situation": (
                '{"kind":"failure","cause":"mission_failed","polarity":"failure"}'
            )
        },
    ) == "reversed_polarity"
    assert compose_visible_defect(
        "I couldn't.",
        "status",
        "open Steam and go to the library",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    ) == "acting_asserted"
    assert compose_visible_defect(
        "Hola.",
        "status",
        "abre Steam y ve a la biblioteca",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    ) == "acting_asserted"
    assert compose_visible_defect(
        "Sigo adelante.",
        "status",
        "abre Steam y ve a la biblioteca",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "Digo que sí.",
        "status",
        "abre Steam y ve a la biblioteca",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    ) == "acting_asserted"
    assert compose_visible_defect(
        "Still working.",
        "status",
        "open Steam and go to the library",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "I'm here.",
        "status",
        "open Steam and go to the library",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    ) == "acting_asserted"
    assert compose_visible_defect(
        "Progreso, sin el resultado.",
        "status",
        "abre Steam y ve a la biblioteca",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    ) == "copied_instruction"
    assert compose_visible_defect(
        "I couldn't: the mute feature is active.",
        "status",
        "mute the speakers",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":true}}'
            )
        },
    ) == "asserted_failure"
    assert compose_visible_defect(
        "La persona está muda.",
        "status",
        "silencia los altavoces",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":true}}'
            )
        },
    ) == "missing_name"
    captured.clear()
    client.compose_user_message(
        "abre Steam y ve a la biblioteca",
        "status",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    )
    for payload in captured:
        system = payload["messages"][0]["content"]
        user = payload["messages"][1]["content"]
        assert system == CPU_USER_MESSAGE_PROMPT
        assert "estado observable" not in system
        assert "abre Steam" not in user
    captured.clear()
    client.compose_user_message(
        "open Word and wipe the disk",
        "error",
        {
            "situation": (
                '{"kind":"failure","cause":"mission_failed","polarity":"failure",'
                '"steps":["I opened Word."]}'
            )
        },
    )
    blob = json.dumps(captured, ensure_ascii=False)
    assert "I opened Word" not in blob


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
    assert visible_reply_invents_a_spanish_infinitive(
        "Listo, Abrbió Word y creó la nota."
    )
    assert visible_reply_invents_a_spanish_infinitive(
        "The window washas been closed."
    )
    assert visible_reply_invents_a_spanish_infinitive(
        "Los altavoces están silo."
    )
    assert visible_reply_invents_a_spanish_infinitive(
        "No puedo decirar el día actual sin ver la pantalla."
    )
    assert visible_reply_invents_a_spanish_infinitive("No puedo fabricar una hora talcr.")
    assert visible_reply_invents_a_spanish_infinitive(
        "Want me to readver the current date and time?"
    )
    assert visible_reply_invents_a_spanish_infinitive(
        "Quieres que vme la Papelera de reciclaje?"
    )
    assert visible_reply_invents_a_spanish_infinitive(
        "¿Quieres que te comprobo si una aplicación está instalada?"
    )
    assert visible_reply_invents_a_spanish_infinitive(
        "No puedo llamarar a un taxi en Marte."
    )
    assert visible_reply_invents_a_spanish_infinitive("Buenos nochesos.")
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
    ) == "missing_confirmation_choice"
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
        "Muted: false.",
        "status",
        "unmute the audio",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":false}}'
            )
        },
    ) == "internal_code"
    assert compose_visible_defect(
        "Muted.",
        "status",
        "mute the speakers",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":true}}'
            )
        },
    ) == "copied_instruction"
    assert compose_visible_defect(
        "Unmuted.",
        "status",
        "unmute the audio",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":false}}'
            )
        },
    ) == "copied_instruction"
    assert compose_visible_defect(
        "The speakers are muted.",
        "status",
        "mute the speakers",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":true}}'
            )
        },
    ) == ""
    assert compose_visible_defect(
        "The audio is unmuted.",
        "status",
        "unmute the audio",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":false}}'
            )
        },
    ) == ""
    assert compose_visible_defect(
        "Listo, los altavoces están silenciados.",
        "status",
        "silencia los altavoces",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":true}}'
            )
        },
    ) == ""
    assert compose_visible_defect(
        "Listo, el volumen está mutado.",
        "status",
        "silencia los altavoces",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":true}}'
            )
        },
    ) == "extra_claim"
    assert compose_visible_defect(
        "I couldn't: the wait ran out.",
        "error",
        "close Chrome",
        {"situation": '{"kind":"failure","cause":"timeout","polarity":"failure","target":"Chrome"}'},
    ) == ""
    assert compose_visible_defect(
        "I couldn't: wait ended.",
        "error",
        "close Chrome",
        {"situation": '{"kind":"failure","cause":"timeout","polarity":"failure","target":"Chrome"}'},
    ) == "copied_instruction"
    assert compose_visible_defect(
        "I couldn't: the wait ended ended ended.",
        "error",
        "close Chrome",
        {"situation": '{"kind":"failure","cause":"timeout","polarity":"failure","target":"Chrome"}'},
    ) == "invented"
    assert compose_visible_defect(
        "I couldn't: mission unfinished.",
        "error",
        "open Word and wipe the disk",
        {"situation": '{"kind":"failure","cause":"mission_failed","polarity":"failure"}'},
    ) == "copied_instruction"
    assert compose_visible_defect(
        "I couldn't: I don't do that.",
        "error",
        "open Word and wipe the disk",
        {"situation": '{"kind":"failure","cause":"mission_failed","polarity":"failure"}'},
    ) == ""
    assert compose_visible_defect(
        "No pude: no respondo.",
        "error",
        "abre Steam y borra el disco",
        {"situation": '{"kind":"failure","cause":"mission_failed","polarity":"failure"}'},
    ) == "extra_claim"
    assert compose_visible_defect(
        "No pude: eso no lo hago.",
        "error",
        "abre Steam y borra el disco",
        {"situation": '{"kind":"failure","cause":"mission_failed","polarity":"failure"}'},
    ) == ""
    assert compose_visible_defect(
        "La volumen está en 10.",
        "status",
        "pon el volumen a 10",
        {
            "situation": (
                '{"kind":"operation","polarity":"success","observed":{"level":10}}'
            )
        },
    ) == "wrong_gender"
    assert compose_visible_defect(
        "No pude: el tiempo tiempo se agotó el tiempo.",
        "error",
        "abre Calculadora",
        {
            "situation": (
                '{"kind":"failure","cause":"timeout","polarity":"failure",'
                '"target":"Calculadora"}'
            )
        },
    ) == "invented"
    assert compose_visible_defect(
        "La hora localTime es 22:10.",
        "status",
        "qué hora es ahora",
        {
            "situation": (
                '{"kind":"operation","operation":"system.time",'
                '"polarity":"success","observed":{"localTime":"22:10"}}'
            )
        },
    ) == "internal_code"
    time_contract = (
        '{"kind":"operation","operation":"system.time","polarity":"success",'
        '"observed":{"version":1,"utc":"2026-09-03T02:10:00.0000000+00:00",'
        '"localUtcOffsetMinutes":-240}}'
    )
    assert compose_visible_defect(
        "Listo, son las 22:10.",
        "status",
        "qué hora es ahora",
        {"situation": time_contract},
    ) == ""
    assert compose_visible_defect(
        "Listo, son las 2:10.",
        "status",
        "qué hora es ahora",
        {"situation": time_contract},
    ) == "missing_name"
    assert compose_visible_defect(
        "No pude: no pude encontrarlo.",
        "status",
        "qué hora es ahora",
        {"situation": time_contract},
    ) == "asserted_failure"
    assert compose_visible_defect(
        "Listo, el volumen está en 100 y son las 14:30.",
        "status",
        "Dime la hora y el estado del audio.",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.volume",'
                '"polarity":"success","observed":{"level":100}}'
            )
        },
    ) == "extra_claim"
    assert compose_visible_defect(
        "Sigo, el estado es que Steam está abierto.",
        "status",
        "abre Steam y ve a la biblioteca",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    ) == "internal_code"
    assert compose_visible_defect(
        'Gamma, el título es "Gamma".',
        "status",
        "crea la nota Gamma",
        {
            "situation": (
                '{"kind":"operation","operation":"note.create",'
                '"polarity":"success","observed":{"title":"Gamma"}}'
            )
        },
    ) == "copied_instruction"
    assert compose_visible_defect(
        "La nota Gamma está abierta.",
        "status",
        "crea la nota Gamma",
        {
            "situation": (
                '{"kind":"operation","operation":"note.create",'
                '"polarity":"success","observed":{"title":"Gamma"}}'
            )
        },
    ) == "extra_claim"
    assert compose_visible_defect(
        "La ventanaien la ventana.",
        "status",
        "cierra la ventana",
        {"situation": '{"kind":"operation","operation":"app.close","polarity":"success"}'},
    ) == "invented"
    assert compose_visible_defect(
        "La ventana activa.",
        "status",
        "cierra la ventana activa",
        {"situation": '{"kind":"operation","operation":"app.close","polarity":"success"}'},
    ) == "missing_state"
    assert compose_visible_defect(
        "La ventana está cerrada.",
        "status",
        "cierra la ventana",
        {"situation": '{"kind":"operation","operation":"app.close","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "No pude: la terminal ya terminado de esperar.",
        "error",
        "abre la terminal",
        {"situation": '{"kind":"failure","cause":"timeout","polarity":"failure","target":"Terminal"}'},
    ) == "invented"
    assert compose_visible_defect(
        "Estado observable: El audio ya fue reactivado.",
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
        "Los altavoces están silo.",
        "status",
        "silencia los altavoces",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":true}}'
            )
        },
    ) == "invented"
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
        "el volumen está en 80.",
        "status",
        "sube el volumen a 80",
        {
            "situation": (
                '{"kind":"operation","polarity":"success","observed":{"level":80}}'
            )
        },
    ) == "lowercase"
    assert compose_visible_defect(
        "Calculadora está abierto.",
        "status",
        "abre Calculadora",
        {
            "situation": (
                '{"kind":"operation","polarity":"success","observed":{"app":"Calculadora"}}'
            )
        },
    ) == "wrong_gender"
    assert compose_visible_defect(
        "Clarify what you mean.",
        "clarification",
        "close it",
        {"situation": '{"kind":"clarification","polarity":"pending"}'},
    ) == "clarification_not_a_question"
    mission_facts = {
        "situation": (
            '{"kind":"status","cause":"mission_completed","polarity":"success",'
            '"steps":["Abrí Word.","Creé la nota «Borrador»."]}'
        )
    }
    assert compose_visible_defect(
        "Listo, la nota «Borrador» fue creada con éxito.",
        "status",
        "abre Word y crea una nota",
        mission_facts,
    ) == "missing_name"
    assert compose_visible_defect(
        "Listo, Abrí Word y creé la nota «Borrador».",
        "status",
        "abre Word y crea una nota",
        mission_facts,
    ) == ""
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


def test_system_time_contract_is_utc_and_offset_not_localtime() -> None:
    observed = {
        "version": 1,
        "utc": "2026-09-03T06:57:52.1829160+00:00",
        "localUtcOffsetMinutes": -240,
    }
    assert _local_clock_from_observed(observed) == "02:57"
    assert _local_clock_from_observed({"localTime": "22:10"}) is None
    payload = _compose_situation_payload(
        {
            "kind": "operation",
            "polarity": "success",
            "observed": observed,
        },
        "es",
        "¿Qué hora es?",
    )
    assert payload["seen"]["time"] == "02:57"
    assert "utc" not in payload["seen"]
    assert "localUtcOffsetMinutes" not in payload["seen"]
    assert "localTime" not in payload["seen"]
    assert "si seen.time" in USER_MESSAGE_PROMPT

    captured: list[dict] = []

    class FakeClient(llm_mod.LlmRuntime):
        def __init__(self) -> None:  # noqa: D107
            pass

        def _post(self, payload):  # noqa: ANN001
            captured.append(payload)
            return {"choices": [{"message": {"content": "Listo, son las 2:57."}}]}

    client = FakeClient()
    text = client.compose_user_message(
        "¿Qué hora es?",
        "status",
        {
            "situation": json.dumps(
                {
                    "kind": "operation",
                    "operation": "system.time",
                    "polarity": "success",
                    "observed": observed,
                },
                ensure_ascii=False,
            )
        },
    )
    assert text == "Listo, son las 2:57."
    blob = json.dumps(captured, ensure_ascii=False)
    assert "02:57" in blob
    assert "localTime" not in blob
    assert "localUtcOffsetMinutes" not in blob
