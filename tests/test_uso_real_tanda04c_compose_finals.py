"""Uso real tanda 4c (2026-09-24, official window): composition defects and wrong finals. One owner per rule.

1. A calendar question carries only the part it asks («¿qué mes sale ahora mismo en el calendario de mi casa?»
   ended in no_response: «Este mes es septiembre.» was rejected three times for lacking the day). Owner:
   semantic/network.calendar_parts_asked, llm._calendar_facts / _misses_calendar_facts; mirror in
   UserMessagePolicy.PreservesObservedDate.
2. A raise or a lowering is said only as the observed levels show it («Incrementa el brightness al level 8» with
   the brightness at 100 → «El brightness se incrementó al nivel 8.»). Owner: llm._unobserved_direction.
3. A Spanish reply writes the PC's nouns in Spanish, the person's English word included (same turn). Owner:
   llm._english_pc_nouns, the word-level check of the Spanish compose contract.
4. The article agrees with the PC noun the model translated («Please decrease el brillo del screen un poco» →
   «¿Cuánto deseas reducir el brillo del pantalla?»). Owner: llm.visible_reply_breaks_article_agreement, in the
   compose defects and in the explicit clarification retry.
5. The applications shown are the open ones, read aloud («show me las aplicaciones» pressed the Windows key and the
   final narrated the title of the window that had had the focus). Owner: grammar.window_inventory_arguments;
   the key press narrates only the key (llm._compose_situation_payload).
6. A piece of fiction asked for is written, in a persona too («Actúa como Julio Berne y haz un relato basado en
   el año 2090» died twice as a knowledge answer that only asked back). Owner:
   semantic/patterns.conversation_only_content_request (content_draft).

Every list mixes Spanish, English and Spanglish and holds phrasings never seen in a run.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.effect_intent import operation_domain_is_grounded
from baxy_mind.llm import LlmRuntime
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.network import calendar_parts_asked
from baxy_mind.semantic.patterns import conversation_only_content_request, resolve_explicit_clarification_intent
from baxy_mind.semantic.reading import read

OPERATIONS = (
    "audio.volume", "audio.volume.adjust", "input.key.press", "app.installed", "app.open", "window.resolve",
    "window.focus", "system.time", "system.settings.set", "system.settings.adjust", "web.search",
)

WINDOW_RESOLVE_SCHEMA = {
    "type": "object",
    "properties": {
        "applicationName": {"type": "string"},
        "byTitle": {"type": "boolean"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        "offset": {"type": "integer", "minimum": 0},
        "process": {"type": "string"},
    },
    "required": [],
    "additionalProperties": False,
}
KEY_SCHEMA = {
    "type": "object",
    "properties": {"key": {"type": "string", "enum": ["enter", "escape", "tab", "win"]}},
    "required": ["key"],
    "additionalProperties": False,
}


def _effects(text: str) -> tuple[str, ...] | None:
    reading = read(text, available_operations=OPERATIONS)
    return reading.effects.operations if reading.effects is not None else None


def _tool(operation: str) -> dict:
    schema = {"window.resolve": WINDOW_RESOLVE_SCHEMA, "input.key.press": KEY_SCHEMA}.get(
        operation, {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    )
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"), "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.", "risk": "low_reversible", "parameters": schema,
        },
    }


class _NoEvidence:
    @staticmethod
    def candidate_families(*_args: object) -> tuple[str, ...]:
        return ()

    @staticmethod
    def retrieve(*_args: object, **_kwargs: object) -> list[object]:
        return []


class _Writer:
    """Readers own the routing; the model only writes the conversation reply it is handed."""

    def __init__(self, reply: str = "") -> None:
        self.reply = reply
        self.chats: list[dict[str, object]] = []

    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("a deterministic reading owns this turn")

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None

    def chat(self, text: str, **kwargs: object) -> tuple[str, list[object]]:
        self.chats.append({"text": text, **kwargs})
        return self.reply, []


def _turn(text: str, model: _Writer | None = None) -> dict:
    tools = [_tool(name) for name in OPERATIONS]
    return sidecar._prepare_turn_result(
        {"id": "tanda-04c", "text": text, "history": []},
        llm=model or _Writer(),
        planner_catalog=PlannerCatalog(tools),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={tool["function"]["canonical_name"]: tool for tool in tools},
    )


# ---------------------------------------------------------------- 1. the calendar part asked

# 05:54 UTC at UTC-3 is 02:54 on Thursday 24 September 2026.
_CLOCK = {
    "kind": "operation", "operation": "system.time", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"utc": "2026-09-24T05:54:00+00:00", "localUtcOffsetMinutes": -180},
}


@pytest.mark.parametrize(
    ("text", "parts"),
    [
        ("¿qué mes sale ahora mismo en el calendario de mi casa?", ("month",)),  # tanda 4c t34
        ("what month is it", ("month",)),
        ("¿en qué mes estamos, bro?", ("month",)),
        ("dime what month es ahora", ("month",)),
        ("¿estamos a enero o febrero?", ("month",)),
        ("¿en qué año estamos?", ("year",)),
        ("what year is it right now", ("year",)),
        ("¿qué mes y año es?", ("month", "year")),
        ("which month and year are we in", ("month", "year")),
        ("¿qué día es hoy?", ("date",)),
        ("a cuántos estamos", ("date",)),
        ("what's the date today", ("date",)),
        ("¿qué día de la semana es?", ("weekday",)),  # tanda 6b: the weekday alone
        ("is today friday", ("weekday",)),
        ("¿hoy es 24 de septiembre?", ("date",)),
        ("¿qué hora es?", ()),
    ],
)
def test_the_calendar_part_asked_is_read(text, parts):
    assert calendar_parts_asked(text) == parts


@pytest.mark.parametrize(
    ("text", "language", "facts"),
    [
        ("¿qué mes sale ahora mismo en el calendario de mi casa?", "es", {"month": "septiembre"}),
        ("what month is it", "en", {"month": "September"}),
        ("¿en qué año estamos?", "es", {"year": "2026"}),
        ("which month and year are we in", "en", {"month": "September", "year": "2026"}),
        ("¿qué día es hoy?", "es", {"date": "2026-09-24"}),
        ("¿qué día de la semana es?", "es", {"weekday": "jueves"}),
    ],
)
def test_the_payload_carries_only_the_part_asked(text, language, facts):
    payload = llm._compose_situation_payload(_CLOCK, language, text)
    assert {key: payload[key] for key in ("date", "weekday", "month", "year") if key in payload} == facts
    assert "clock" not in payload


@pytest.mark.parametrize(
    ("text", "reply", "published"),
    [
        # The three drafts tanda 4c t34 rejected.
        ("¿qué mes sale ahora mismo en el calendario de mi casa?", "Este mes es septiembre.", True),
        ("¿qué mes sale ahora mismo en el calendario de mi casa?", "Ahora mismo es septiembre.", True),
        (
            "¿qué mes sale ahora mismo en el calendario de mi casa?",
            "Ahora mismo es septiembre en el calendario de mi casa.",
            True,
        ),
        ("¿estamos a enero o febrero?", "Ni uno ni otro: estamos en septiembre.", True),
        ("¿estamos a enero o febrero?", "Estamos en enero.", False),
        ("¿en qué mes estamos, bro?", "Estamos en octubre.", False),
        ("¿en qué mes estamos, bro?", "Hoy es 23 de septiembre.", False),
        ("¿en qué mes estamos, bro?", "Son las 02:54.", False),
        ("what month is it", "It's September.", True),
        ("what month is it", "It's August.", False),
        ("¿en qué año estamos?", "Estamos en 2026.", True),
        ("¿en qué año estamos?", "Estamos en 2025.", False),
        ("¿qué mes y año es?", "Es septiembre de 2026.", True),
        ("¿qué mes y año es?", "Es septiembre.", False),
        ("¿qué día es hoy?", "Hoy es 24 de septiembre.", True),
        ("¿qué día es hoy?", "Estamos en septiembre.", False),
    ],
)
def test_the_part_asked_is_the_part_checked(text, reply, published):
    facts = {"situation": json.dumps(_CLOCK)}
    payload = llm._compose_situation_payload(_CLOCK, "es", text)
    assert (llm.compose_visible_defect(reply, "status", text, facts) == "") is published
    assert (llm._payload_fact_defect(reply, payload, text) == "") is published


def test_a_named_month_outside_the_carried_one_is_another_month():
    # «enero o febrero» named back is two other months; the answer says the carried one only.
    assert llm._misses_calendar_facts("No es enero ni febrero, es septiembre.", {"month": "septiembre"})
    assert not llm._misses_calendar_facts("It may still feel like summer, but it's September.", {"month": "September"})


# ---------------------------------------------------------------- 2. the direction observed

_SET_TO_8 = {"effect": "applied", "seen": {"setting": "brightness", "value": 8}, "operation": "system.settings.set"}
_LOWERED_100_TO_80 = {
    "seen": {"setting": "brightness", "direction": "down", "amount": 20, "baselineValues": [100], "values": [80]},
    "operation": "system.settings.adjust",
}
_VOLUME_0_TO_50 = {
    "effect": "applied",
    "seen": {"baseline": {"volumePercent": 0, "muted": False}, "final": {"volumePercent": 50, "muted": False},
             "applied": True, "muted": False, "level": 50},
    "operation": "audio.volume",
}
_VOLUME_UP_AT_TOP = {
    "seen": {"direction": "up", "amount": 10, "baselineLevel": 100, "level": 100, "muted": False},
    "operation": "audio.volume.adjust",
}


@pytest.mark.parametrize(
    ("payload", "reply", "defect"),
    [
        (_SET_TO_8, "El brillo se incrementó al nivel 8.", "unobserved_direction"),  # tanda 4c t37
        (_SET_TO_8, "Subí el brillo a 8.", "unobserved_direction"),
        (_SET_TO_8, "I raised the brightness to 8.", "unobserved_direction"),
        (_SET_TO_8, "Bajé el brillo a 8.", "unobserved_direction"),
        (_SET_TO_8, "El brillo quedó en el nivel 8.", ""),
        (_SET_TO_8, "Brightness is now at 8.", ""),
        (_LOWERED_100_TO_80, "Bajé el brillo al 80.", ""),
        (_LOWERED_100_TO_80, "Reducí el brillo de 100 a 80.", ""),
        (_LOWERED_100_TO_80, "I lowered the brightness to 80.", ""),
        (_LOWERED_100_TO_80, "Aumenté el brillo al 80.", "unobserved_direction"),
        (_VOLUME_0_TO_50, "Subí el volumen al 50 %.", ""),
        (_VOLUME_0_TO_50, "I turned the volume down to 50%.", "unobserved_direction"),
        (_VOLUME_UP_AT_TOP, "Subí el volumen al 100 %.", "unobserved_direction"),
        (_VOLUME_UP_AT_TOP, "El volumen sigue en 100 %, ya estaba al máximo.", ""),
    ],
)
def test_a_direction_is_said_only_as_observed(payload, reply, defect):
    assert llm._payload_fact_defect(reply, payload, "") == defect


def test_an_offer_to_lower_more_is_not_a_claimed_direction():
    assert llm._payload_fact_defect("El brillo quedó en 8. ¿Quieres que lo baje más?", _SET_TO_8, "") == ""


# ---------------------------------------------------------------- 3. the PC's nouns in Spanish

_BRIGHTNESS_SET = {
    "kind": "operation", "operation": "system.settings.set", "polarity": "success", "verified": True,
    "succeeded": True, "observed": {"setting": "brightness", "value": 8},
}


@pytest.mark.parametrize(
    ("request_text", "reply", "defect"),
    [
        ("Incrementa el brightness al level 8", "El brightness quedó en el nivel 8.", "english_word"),  # t37
        ("Incrementa el brightness al level 8", "El brillo quedó en el level 8.", "english_word"),
        ("ponme el screen más oscuro, nivel 8", "La screen quedó en el nivel 8.", "english_word"),
        ("Incrementa el brightness al level 8", "El brillo quedó en el nivel 8.", ""),
        ("Incrementa el brightness al level 8", "El brillo, que llamaste «brightness», quedó en 8.", ""),
        # A spanglish request may keep the person's terms; an English one is English.
        ("Pon el brightness en 8 please", "El brightness quedó en 8.", ""),
        ("Set the brightness to 8", "Brightness is now at 8.", ""),
    ],
)
def test_a_spanish_reply_names_the_pc_in_spanish(request_text, reply, defect):
    facts = {"situation": json.dumps(_BRIGHTNESS_SET)}
    assert llm.compose_visible_defect(reply, "status", request_text, facts) == defect


@pytest.mark.parametrize(
    ("reply", "words"),
    [
        ("Subí el volume y el sound quedó en el level 40.", ["volume", "sound", "level"]),
        ("Según weather.com, hoy hay sol.", []),
        ("Está sonando Daft Punk - Instant Crush (Official Music Video).", []),
        ("Puse «Screen Saver» como protector.", []),
    ],
)
def test_only_the_lowercase_prose_nouns_count_as_english(reply, words):
    assert llm._english_pc_nouns(reply) == words


# ---------------------------------------------------------------- 4. the article agrees


@pytest.mark.parametrize(
    ("text", "agreeing"),
    [
        ("¿Cuánto deseas reducir el brillo del pantalla?", "de la pantalla"),  # tanda 4c t12
        ("Reducí el brillo del pantalla un 20 por ciento.", "de la pantalla"),  # tanda-02 t45
        ("¿A qué nivel pongo el música?", "la música"),
        ("Subí la volumen al 40 %.", "el volumen"),
        ("Abrí un ventana nueva del navegador.", "una ventana"),
        ("¿Cierro esa programa?", "ese programa"),
        ("Dejé el alarma a las siete.", "la alarma"),
        ("Moví el archivo al carpeta Descargas.", "a la carpeta"),
        ("¿Cuánto quieres bajar el brillo de la pantalla?", ""),
        ("La música está en pausa y el volumen en 30.", ""),
        ("Abrí el Red Dead Redemption.", ""),
        ("¿La programo para mañana?", ""),
        ("I turned the screen brightness down.", ""),
    ],
)
def test_the_article_agrees_with_the_pc_noun(text, agreeing):
    assert llm.visible_reply_breaks_article_agreement(text) == agreeing


def test_a_composed_reply_with_a_disagreeing_article_is_retried():
    adjusted = {
        "kind": "operation", "operation": "system.settings.adjust", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {"setting": "brightness", "direction": "down", "amount": 20, "baselineValues": [100],
                     "values": [80]},
    }
    facts = {"situation": json.dumps(adjusted)}
    request_text = "baja el brillo de la pantalla un 20"
    assert llm.compose_visible_defect(
        "Reducí el brillo del pantalla un 20 por ciento.", "status", request_text, facts
    ) == "wrong_gender"


def test_the_clarification_is_asked_again_with_the_agreeing_article():
    runtime = object.__new__(LlmRuntime)
    drafts = iter(
        [
            "¿Cuánto deseas reducir el brillo del pantalla?",
            "¿Cuánto deseas reducir el brillo de la pantalla?",
        ]
    )
    sent: list[list[dict]] = []

    def response(payload: dict, _label: str) -> dict:
        sent.append([dict(message) for message in payload["messages"]])
        return {"requested_fields": ["amount"], "question": next(drafts)}

    runtime._post_schema_object = response  # type: ignore[method-assign]
    question = runtime.formulate_explicit_clarification_question(
        "Please decrease el brillo del screen un poco", ("system.settings.adjust",), ("amount",)
    )
    assert question == "¿Cuánto deseas reducir el brillo de la pantalla?"
    assert "«de la pantalla»" in json.dumps(sent[1], ensure_ascii=False)


def test_a_clarification_that_never_agrees_is_not_published():
    runtime = object.__new__(LlmRuntime)
    runtime._post_schema_object = (  # type: ignore[method-assign]
        lambda _payload, _label: {"requested_fields": ["amount"], "question": "¿Cuánto bajo el música?"}
    )
    with pytest.raises(ValueError):
        runtime.formulate_explicit_clarification_question(
            "turn down la music un poco", ("audio.volume.adjust",), ("amount",)
        )


# ---------------------------------------------------------------- 5. the applications shown


@pytest.mark.parametrize(
    "text",
    [
        "show me las aplicaciones",  # tanda 4c t40
        "muéstrame mis apps",
        "show me all my programs",
        "qué aplicaciones tengo abiertas",
        "which apps are open right now",
        "enséñame los programas abiertos",
        "lista las aplicaciones",
        "dime qué apps tengo abiertas por favor",
        "Enseñarme las apps.",
    ],
)
def test_the_applications_shown_are_the_open_windows_read_aloud(text):
    assert _effects(text) == ("window.resolve",)
    assert operation_domain_is_grounded(text, "window.resolve", ())
    assert sidecar._ground_explicit_arguments("window.resolve", text, WINDOW_RESOLVE_SCHEMA) == {
        "process": "*", "byTitle": False,
    }
    assert not sidecar._closed_unsupported_request(text)


@pytest.mark.parametrize(
    "text", ["show me las aplicaciones", "show me the apps", "show me my open apps", "qué programas tengo abiertos"]
)
def test_the_tanda_turn_reads_the_open_windows_without_the_model(text):
    result = _turn(text)
    assert result["kind"] == "action"
    assert result["effectOperations"] == ["window.resolve"]


@pytest.mark.parametrize(
    "text", ["show me music apps", "list the apps for editing photos", "muéstrame las aplicaciones de música"]
)
def test_a_category_of_applications_is_still_asked_which(text):
    clarification = resolve_explicit_clarification_intent(text, OPERATIONS, ())
    assert clarification is not None and clarification.operations == ("app.installed",)


@pytest.mark.parametrize("text", ["abre el menú inicio", "open the start menu", "pull up the start menu please"])
def test_the_start_menu_named_is_still_the_windows_key(text):
    assert _effects(text) == ("input.key.press",)
    assert sidecar._ground_explicit_arguments("input.key.press", text, KEY_SCHEMA) == {"key": "win"}


@pytest.mark.parametrize(
    "text",
    ["muéstrame las aplicaciones instaladas", "list the apps installed", "show the apps downloaded today"],
)
def test_the_installed_applications_listed_stay_a_limit(text):
    assert _effects(text) != ("input.key.press",)
    assert sidecar._closed_unsupported_request(text)


def test_a_key_press_narrates_only_the_key():
    pressed = {
        "kind": "operation", "operation": "input.key.press", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {
            "ok": True, "effectObserved": True, "action": "key", "key": "win", "acceptedEvents": 2,
            "expectedEvents": 2, "inputSize": 40, "lastWin32Error": 0, "foregroundProcessIdBefore": 100,
            "foregroundProcessIdAfter": 200, "foregroundTitleBefore": "Informe trimestral - Word",
            "authority": "win32_sendinput_return_count",
        },
    }
    payload = llm._compose_situation_payload(pressed, "es", "abre el menú inicio")
    assert payload["seen"] == {"keyPressed": "win"}
    assert "Informe" not in json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------- 6. fiction asked for is written


@pytest.mark.parametrize(
    "text",
    [
        "Actúa como Julio Berne y haz un relato basado en el año 2090",  # tanda 4c t23
        "actua como Shakespeare y escríbeme un poema sobre el mar",
        "pretend you're a pirate and tell me a story about treasure",
        "como si fueras Borges, escribe un cuento corto",
        "imagina que eres un robot y cuéntame una historia de amor",
        "hazme un relato de terror",
        "write me a short story set in the year 3000",
        "tell me a bedtime story please",
        "act as Jules Verne and write a tale about the moon",
        "make up a fable about a fox",
        "please narrate a legend about dragons",
    ],
)
def test_fiction_asked_for_is_a_draft_written_in_the_conversation(text):
    assert conversation_only_content_request(text)
    assert llm._conversation_presentation_shape(text, conversation_kind="knowledge", has_history=True) == (
        "content_draft"
    )


@pytest.mark.parametrize(
    "text",
    [
        "cuéntame la historia de Roma",
        "tell me the story of the Titanic",
        "busca la historia de la segunda guerra mundial",
        "abre el historial de chrome",
        "actúa como si nada",
        "hazme un favor y abre spotify",
    ],
)
def test_a_history_or_an_order_is_not_fiction(text):
    assert not conversation_only_content_request(text)


def test_the_tanda_turn_is_written_by_the_model_without_a_routing_call():
    story = (
        "En 2090, el Nautilus IV bajó a la fosa de las Marianas con doce científicos a bordo. "
        "Allí, entre luces que nadie había visto, encontraron una ciudad dormida."
    )
    model = _Writer(story)
    result = _turn("Actúa como Julio Berne y haz un relato basado en el año 2090", model)
    assert result["kind"] == "conversation"
    assert result["reply"] == story
    assert len(model.chats) == 1
