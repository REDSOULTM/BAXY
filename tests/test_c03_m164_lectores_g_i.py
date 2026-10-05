"""M164 (2026-10-04, mind v4y-w with the written history and BAXY's greeting): the code that still lost what the
isolated decider got right in DEV-G and DEV-I (D58).

- G-s001 «pon en youtube el resumen del partido de nacional y de una subele el volumen a 80» → only the video: «de una»
  between «y» and «súbele» hid the second order from the clause reader (``_request_clauses``), which split «y luego
  súbele» but not «y de una súbele». A word of when or how («de una», «ya», «de paso», «right away») between the
  conjunction and an action verb now ends the clause, as «luego» does.
- G-s110 «oye, dime qué es esto que está sonando, que me ha encantado y no la reconozco» → the decider read
  ``audio.status`` («El volumen está en 60…»): what is sounding is the media session
  (``semantic.media.asks_what_sounds``); the level, the mute or the device keep ``audio.status``.
- G-w40-t2 «abre el segundo» after «Encontré dos: «cotizacion_mudanza.pdf» en Descargas y «cotizacion_mudanza_v2.pdf»
  en Documentos.» → «No abro el segundo.»: the catalog reader (``catalog_unavailable``) read «el segundo» as a game the
  library lacks, before the decider and M151. A pick among the files BAXY just listed is no game; M151 opens it.
- I-w27-t3 «could you open it for me?» after «Found it — budget.xlsx is in your Downloads folder.» → the decider asked.
  A pointer opened right after BAXY named one file, and only one, is that file (``semantic.files.only_file_named``).

Rows are quoted with their real text and history; every other phrasing is our own.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import effect_intent
from baxy_mind import llm
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.files import only_file_named
from baxy_mind.semantic.grammar import _request_clauses
from baxy_mind.semantic.media import asks_what_sounds

OPEN_SCHEMA = {
    "type": "object",
    "properties": {
        "folder": {"type": "string", "enum": ["desktop", "documents", "downloads", "pictures"]},
        "name": {"type": "string", "x-maxUtf8Bytes": 200, "x-nonWhitespace": True},
    },
    "required": ["folder", "name"],
    "additionalProperties": False,
}
OPERATIONS = tuple(
    json.loads(
        (pathlib.Path(sidecar.__file__).parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
)
APPLICATIONS = ("Steam", "Spotify", "Google Chrome", "Discord", "Calculadora", "Bloc de notas")
# A library with a game in it, as on the PC the rows ran on: the catalog reader closes a game it lacks.
GAMES = effect_intent.build_game_catalog_index([("steam", "2767030", "Marvel Rivals")])
GREETING = {"role": "assistant", "content": "Hola, soy BAXY. ¿En qué puedo ayudarte hoy?"}


def _tool(operation: str) -> dict[str, Any]:
    schema = (
        OPEN_SCHEMA if operation == "file.open"
        else {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    )
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "read_only", "parameters": schema}}


class _Decider:
    """The model of a whole turn: the decider answers what it is given; every other call is neutral."""

    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision, serves: bool = True) -> None:
        self.decision = decision
        self.serves = serves
        self.asked = 0

    def decide_in_context(self, *_a, **_k):
        self.asked += 1
        return self.decision

    def prepare_decision(self, *_a, **_k):
        return None

    def formulate_explicit_clarification_question(self, *_a, **_k):
        return "¿Cuál?"

    def clarify_after_turn_failure(self, *_a, **_k):
        return "¿Qué quieres que haga?"

    def clarify_unresolved_input(self, *_a, **_k):
        return "¿Qué quieres decir?"

    def clarify_missing_referent(self, *_a, **_k):
        return "¿Qué abro?"

    def public_lookup_requested(self, _text):
        return False

    def operation_is_the_requested_effect(self, *_a, **_k):
        return self.serves

    def _verify_semantic_effect_shape(self, _text):
        return "complete", "one"

    def chat(self, *_a, **_k):
        return "Respuesta.", []

    def compose_user_message(self, *_a, **_k):
        return "No abro el segundo."

    def prepare_chat(self, *_a, **_k):
        return None

    def detect_response_language(self, _text):
        return "es"

    def consume_deferred_response_language(self, _text):
        return True, None

    def retire_deferred_response_language(self, _text):
        return None

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


class _Abstaining:
    """The model's own extraction abstains: only BAXY's steps ground the arguments."""

    def extract_direct_arguments(self, *_args: object, **_kwargs: object) -> llm.DirectArgumentExtraction:
        return llm.DirectArgumentExtraction(arguments=None, evidence=(), fallback_question="¿Qué archivo?")

    def formulate_missing_argument_question(self, *_args: object, **_kwargs: object) -> str:
        return "¿Qué archivo?"


def _history(before: list[dict[str, str]], text: str) -> list[dict[str, str]]:
    return [*before, {"role": "user", "content": text}]


def _turn(
    before: list[dict[str, str]], text: str, decision: ContextDecision, *, serves: bool = True,
) -> tuple[dict, _Decider]:
    """``serves``: what the model answers when asked whether an operation is the effect requested. In the App it said no
    for «abre el segundo» (G-w40-t2), so the catalog reader's limit was not withdrawn."""

    tools = {name: _tool(name) for name in OPERATIONS}
    model = _Decider(decision, serves)
    result = sidecar._prepare_turn_result(
        {"id": "m164", "text": text, "history": _history(before, text)},
        llm=model, planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (),
        tool_by_name=tools, application_names=APPLICATIONS, game_catalog=GAMES, dialogue_state=DialogueState(),
    )
    return result, model


def _open_arguments(before: list[dict[str, str]], text: str, objective: str) -> tuple[dict | None, str]:
    return sidecar._direct_arguments_result(
        {"operation": "file.open", "text": objective, "history": _history(before, text)},
        llm=_Abstaining(), tool=_tool("file.open"), dialogue_state=DialogueState(),
    )


def _said(*lines: str) -> list[dict[str, str]]:
    """The conversation before the message, user first and alternating."""

    return [{"role": "user" if index % 2 == 0 else "assistant", "content": line} for index, line in enumerate(lines)]


def _decided(request: str, decision: str = "action", *operations: str, **arguments: str) -> ContextDecision:
    return ContextDecision(request, decision, operations, "", tuple(arguments.items()))


TALK = _decided("", "talk")


# ------------------------------------------------------------------ G-s001: «y de una súbele…» is its own order


@pytest.mark.parametrize(
    ("text", "operations", "evidence"),
    [
        # The row (DEV-G v4y G-s001).
        ("pon en youtube el resumen del partido de nacional y de una subele el volumen a 80",
         ("media.play.youtube", "audio.volume"), ("pon en youtube el resumen del partido de nacional", "volumen a 80")),
        # Our own words: another adverb, another first order, the other language.
        ("abre spotify y de paso súbele el volumen a 80", ("app.open", "audio.volume"), ("spotify", "volumen a 80")),
        ("pon en youtube el gol de la final y ya bájale el volumen a 30",
         ("media.play.youtube", "audio.volume"), ("pon en youtube el gol de la final", "volumen a 30")),
        ("play the match highlights on youtube and right away set the volume to 80",
         ("media.play.youtube", "audio.volume"), ("play the match highlights on youtube", "set the volume to 80")),
    ],
)
def test_an_order_after_and_and_a_word_of_when_is_its_own_clause(
    text: str, operations: tuple[str, ...], evidence: tuple[str, ...],
) -> None:
    intent = effect_intent.resolve_explicit_effects(text, OPERATIONS, APPLICATIONS, GAMES)
    assert intent is not None and (intent.operations, intent.evidence) == (operations, evidence)


def test_the_row_plans_the_video_and_the_volume() -> None:
    text = "pon en youtube el resumen del partido de nacional y de una subele el volumen a 80"
    result, model = _turn([GREETING], text, TALK)
    assert (result["kind"], result["effectOperations"]) == ("plan", ["media.play.youtube", "audio.volume"]), result
    assert model.asked == 0


@pytest.mark.parametrize(
    ("text", "operations"),
    [
        # «pon X en youtube» alone stays one video.
        ("pon en youtube el resumen del partido de nacional", ("media.play.youtube",)),
        ("pon el resumen del partido en youtube", ("media.play.youtube",)),
        # Without the adverb the split was already there.
        ("pon en youtube el resumen del partido de nacional y subele el volumen a 80",
         ("media.play.youtube", "audio.volume")),
    ],
)
def test_what_already_read_well_reads_the_same(text: str, operations: tuple[str, ...]) -> None:
    intent = effect_intent.resolve_explicit_effects(text, OPERATIONS, APPLICATIONS, GAMES)
    assert intent is not None and intent.operations == operations


@pytest.mark.parametrize(
    "text",
    [
        "pon música y ya está",  # «ya está» is no order
        "abre spotify y ya",
        "dile que ya voy y de una vez que traiga pan",  # no action verb after the adverb
        "and now what?",
    ],
)
def test_the_adverb_alone_or_before_no_order_splits_nothing(text: str) -> None:
    assert len(_request_clauses(effect_intent._fold(text))) == 1


# ------------------------------------------------------------------ G-s110: what is sounding is the song


@pytest.mark.parametrize(
    ("before", "text", "decision"),
    [
        # The row (DEV-G v4y G-s110), with the decider's v4y-w decision.
        ([GREETING], "oye, dime qué es esto que está sonando, que me ha encantado y no la reconozco",
         _decided("¿Qué está sonando en el PC?", "action", "audio.status")),
        # Our own words, both languages.
        ([], "¿qué es lo que estoy escuchando?", _decided("¿Qué se escucha en el PC?", "action", "audio.status")),
        ([], "hey what am I listening to right now", _decided("What is playing on the PC?", "action", "audio.status")),
    ],
)
def test_what_is_sounding_reads_the_media_session(before, text: str, decision: ContextDecision) -> None:
    result, _ = _turn(before, text, decision)
    assert (result["kind"], result["effectOperations"]) == ("action", ["media.status"]), result


@pytest.mark.parametrize(
    ("text", "decision"),
    [
        ("¿a cuánto está el volumen?", _decided("¿A cuánto está el volumen?", "action", "audio.status")),
        ("is the sound muted right now?", _decided("Is the sound muted?", "action", "audio.status")),
        ("por dónde está sonando el audio, ¿los audífonos o el parlante?",
         _decided("¿Por qué salida suena el audio?", "action", "audio.status")),
    ],
)
def test_the_level_the_mute_and_the_device_stay_the_output_status(text: str, decision: ContextDecision) -> None:
    result, _ = _turn([], text, decision)
    assert (result["kind"], result["effectOperations"]) == ("action", ["audio.status"]), result


@pytest.mark.parametrize(
    ("text", "asks"),
    [
        ("oye, dime qué es esto que está sonando, que me ha encantado y no la reconozco", True),
        ("¿qué suena?", True),
        ("what's that playing? love it", True),
        ("what is this that's playing", True),
        ("¿a cuánto está el volumen?", False),
        ("qué tan fuerte está sonando", False),
        ("por qué no suena nada", False),
        ("why is nothing playing", False),
        ("what device is playing the sound", False),
    ],
)
def test_the_reader_of_what_sounds(text: str, asks: bool) -> None:
    assert asks_what_sounds(text) is asks


# ------------------------------------------------------------------ G-w40-t2: a pick among the files listed

MOVING = _said(
    "busca un archivo que se llama cotizacion_mudanza",
    "Encontré dos: «cotizacion_mudanza.pdf» en Descargas y «cotizacion_mudanza_v2.pdf» en Documentos.",
)
INVOICES = _said(
    "find the file called invoice",
    "I found two: «invoice.pdf» in Downloads and «invoice_old.pdf» in Documents.",
)
RECIPES = _said(
    "búscame la receta del queque",
    "Hay dos: «queque_naranja.docx» en el Escritorio y «queque_chocolate.docx» en Documentos.",
)


@pytest.mark.parametrize(
    ("before", "text", "decision", "arguments"),
    [
        # The row (DEV-G v4y G-w40-t2), with the App's v4y decision.
        ([GREETING, *MOVING], "abre el segundo",
         _decided("Abre el segundo archivo de la carpeta de descargas.", "action", "filesystem.file.open.latest",
                  folder="downloads"),
         {"folder": "documents", "name": "cotizacion_mudanza_v2.pdf"}),
        # Our own words, both languages.
        (INVOICES, "open the first one", _decided("Open the newest file in Downloads.", "action",
                                                   "filesystem.file.open.latest", folder="downloads"),
         {"folder": "downloads", "name": "invoice.pdf"}),
        (RECIPES, "abre el primero porfa", _decided("Abre la receta del queque.", "action", "file.open",
                                                     folder="desktop", name="queque"),
         {"folder": "desktop", "name": "queque_naranja.docx"}),
    ],
)
def test_a_pick_among_the_files_listed_opens_that_file(before, text: str, decision, arguments) -> None:
    result, model = _turn(before, text, decision, serves=False)
    assert (result["kind"], result["effectOperations"]) == ("action", ["file.open"]), result
    assert model.asked == 1
    assert _open_arguments(before, text, result["objective"]) == (arguments, "")


@pytest.mark.parametrize(
    "before",
    [
        [],  # nothing listed before
        [GREETING],
        _said("qué juegos tengo", "Tienes Hades y Celeste."),  # a list with no file in it
    ],
)
def test_the_same_pick_with_no_file_listed_is_read_as_before(before) -> None:
    # Read as before M164: the catalog reader's limit, «No abro el segundo.», before the decider.
    result, model = _turn(before, "abre el segundo", TALK, serves=False)
    assert (result["kind"], result.get("conversationKind"), result["effectOperations"]) == (
        "conversation", "unsupported", [],
    ), result
    assert model.asked == 0


# ------------------------------------------------------------------ I-w27-t3: «open it» after one file named

LIGHTS = [
    GREETING,
    *_said(
        "would you mind turning off the living room lights, please?",
        "That one's not on me — I'm stuck to this PC, I can't touch your lights.",
        "fair enough — could you check if budget.xlsx is in my downloads, please?",
        "Found it — budget.xlsx is in your Downloads folder.",
    ),
]
LEASE = _said("¿está el contrato_arriendo.pdf en documentos?", "Sí, «contrato_arriendo.pdf» está en Documentos.")
NOTES = _said("is my week 3 notes file on the desktop?", "Yes — «notes_week3.docx» is on your Desktop.")
ASKED = _decided("", "clarify")


@pytest.mark.parametrize(
    ("before", "text", "arguments"),
    [
        # The row (DEV-I v4y I-w27-t3): the decider asked.
        (LIGHTS, "could you open it for me?", {"folder": "downloads", "name": "budget.xlsx"}),
        # Our own words, both languages.
        (LEASE, "dale, ábrelo", {"folder": "documents", "name": "contrato_arriendo.pdf"}),
        (NOTES, "can you open that one?", {"folder": "desktop", "name": "notes_week3.docx"}),
    ],
)
def test_opening_a_pointer_after_one_file_named_opens_it(before, text: str, arguments: dict[str, str]) -> None:
    result, _ = _turn(before, text, ASKED)
    assert (result["kind"], result["effectOperations"]) == ("action", ["file.open"]), result
    assert _open_arguments(before, text, result["objective"]) == (arguments, "")


@pytest.mark.parametrize(
    ("before", "text", "decision"),
    [
        # M19: a pointer with nothing named before stays asked.
        ([], "ábrelo", ASKED),
        ([], "ábrelo", _decided("Abre el navegador.", "action", "app.open")),
        (_said("qué hora es", "Son las 10:40."), "ábreme eso porfa", ASKED),
        # Two files named and none picked.
        (_said("find my resume", "There are two: «cv_english.pdf» in Documents and «cv_spanish.pdf» in Downloads."),
         "open it", ASKED),
        # The one file named, but the message opens another thing.
        (LEASE, "ábrelo en el navegador", ASKED),
    ],
)
def test_a_pointer_with_no_single_file_before_stays_asked(before, text: str, decision: ContextDecision) -> None:
    result, _ = _turn(before, text, decision)
    assert result["kind"] == "clarify", result


def test_the_one_file_named_is_found_only_when_it_is_the_only_one() -> None:
    assert only_file_named("could you open it for me?", "Found it — budget.xlsx is in your Downloads folder.") == (
        "budget.xlsx"
    )
    assert only_file_named("open it", "There are two: «a.pdf» and «b.pdf».") is None
    assert only_file_named("ábrelo", "Listo, abrí Descargas.") is None
    assert only_file_named("open the newest one", "Opened «a.pdf».") is None
    assert only_file_named("open report.pdf", "Opened «a.pdf».") is None
