"""M157 (2026-10-04, App runs v4u/v4v): three rows that went wrong in the App, each reproduced on the path the App takes
(the arguments request carries the decider's restatement as its text and the lived conversation as its history).

1. DEV-F F-w05-t5 «ya cambiando de tema, pone algo de javiera mena en spotify»: the decider restated «Pon algo de Javier
   Mené en Spotify.» and Spotify was asked «Javier Mené» in v4u and v4v (seen.query), although M147 had been written
   for this row. M147 ran on the decider's values against the grounding source, whose first line is that restatement
   (the name was «said as it is» there), and the readers had already read the name from it, so the decider's values
   were never consulted. The respelling now runs once on the arguments the step returns, against what the person and
   BAXY said (``__main__._as_the_person_spelled``).
2. DEV-I I-w41-t3 «tradúceme eso al inglés» after «¿y en onzas?»: the decider talked with the request «Traduce al inglés
   «¿Cuántas onzas son 3 tazas de harina de trigo?».»; M88's kitchen-quantity reader (inside M53's ``reference_lookup``)
   read the quoted question as a measure to look up → web.search «No la encontré ahora.». Words said, asked in another
   language, are no lookup (``semantic.conversation.translates_what_was_said``).
3. DEV-I I-w37-t3 «oye, de paso, crea una nota de la junta de hoy» → «He creado la nota titulada "Junta de hoy" con el
   contenido "Junta de hoy".»: the decider gave ``content`` (argument_fields content, title) with the title's words, and
   the arguments step took it. A note named only by what it is about has that as its title; what it says is asked (M81,
   as v4u did), and the next turn «que se decidió subir los precios un 5 por ciento» fills it
   (``semantic.notes.note_content_unsaid``).

Rows are quoted with their real text and the history the App lived; every other phrasing is our own.
"""

from __future__ import annotations

from typing import Any

from baxy_mind.semantic.conversation import translates_what_was_said
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.knowledge import reference_lookup
from baxy_mind.semantic.notes import note_content_unsaid
from test_c03_m154_cifra_se_consulta import _turn
from baxy_mind import decided_arguments
from baxy_mind import direct_arguments
from baxy_mind import argument_payload

PLAY_QUERY = {"type": "object", "properties": {
    "provider": {"type": "string", "enum": ["spotify"], "x-maxUtf8Bytes": 1024},
    "query": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
}, "required": ["provider", "query"], "additionalProperties": False}
NOTE = {"type": "object", "properties": {
    "content": {"type": "string", "x-maxUtf8Bytes": 65536},
    "title": {"type": "string", "x-maxUtf8Bytes": 512, "x-nonWhitespace": True},
}, "required": ["content", "title"], "additionalProperties": False}


def _tool(operation: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "low_reversible", "parameters": schema}}


def _history(said: list[str]) -> list[dict[str, str]]:
    return [{"role": "user" if index % 2 == 0 else "assistant", "content": line} for index, line in enumerate(said)]


class _Extraction:
    """The model's own extraction: returns ``arguments`` (None abstains); a missing value is asked by field."""

    def __init__(self, arguments: dict[str, Any] | None = None) -> None:
        self.arguments = arguments
        self.asked: list[tuple[str, ...]] = []

    def extract_direct_arguments(self, *_args: object, **_kwargs: object) -> argument_payload.DirectArgumentExtraction:
        return argument_payload.DirectArgumentExtraction(arguments=self.arguments, evidence=(), fallback_question="¿Qué?")

    def formulate_missing_argument_question(self, _objective, _purpose, _tool, fields, **_kwargs) -> str:
        self.asked.append(tuple(fields))
        return "¿Qué quieres que diga la nota?"


def _arguments(operation: str, schema: dict[str, Any], said: list[str], request: str,
               decided: tuple[tuple[str, Any], ...], model: _Extraction | None = None) -> tuple[Any, str]:
    """The App's arguments request: the decider's restatement as text, the lived conversation as history."""

    decided_arguments._remember_decided_arguments(request, (operation,), decided)
    return direct_arguments._direct_arguments_result(
        {"operation": operation, "text": request, "history": _history(said), "responseLanguage": "es"},
        llm=model or _Extraction(), tool=_tool(operation, schema), dialogue_state=DialogueState(),
    )


# ------------------------------------------------------------------ 1. F-w05-t5, the name the person wrote

F_W05 = [
    "baxy leeme el ultimo correo porfa",
    "No puedo leer el correo porque Outlook no está configurado en este equipo.",
    "dejale escrito un wsp a la paula que voy pero llego tipo 7 y media, no lo mandes eso si",
    "Se escribió el mensaje en WhatsApp a Paula diciendo que llegas a las siete y media, pero no se confirmó si se "
    "envió o no.",
    "y ponme un recordatorio una hora antes de la junta",
    "¿A qué hora es la junta?",
    "oye y el jueves como va a estar el tiempo aca en ñuñoa",
    "En Ñuñoa, el jueves estará nublado con una temperatura máxima de 20.3 °C y mínima de 9.4 °C, con una "
    "probabilidad de lluvia del 16 %.",
    "ya cambiando de tema, pone algo de javiera mena en spotify",
]


def test_f_w05_t5_spotify_is_asked_the_name_the_person_wrote() -> None:
    arguments, question = _arguments(
        "media.play.query", PLAY_QUERY, F_W05, "Pon algo de Javier Mené en Spotify.",
        (("provider", "Spotify"), ("query", "Javier Mené")),
    )
    assert (arguments, question) == ({"provider": "spotify", "query": "javiera mena"}, "")


def test_other_names_respelled_by_the_model_go_as_written() -> None:
    arguments, _ = _arguments(
        "media.play.query", PLAY_QUERY, ["oye ponme algo de bad buny en spotify"],
        "Pon algo de Bad Bunny en Spotify.", (("provider", "Spotify"), ("query", "Bad Bunny")),
    )
    assert arguments["query"] == "bad buny"
    arguments, _ = _arguments(
        "media.play.query", PLAY_QUERY, ["play some ed sheeren on spotify pls"],
        "Play some Ed Sheeran on Spotify.", (("provider", "Spotify"), ("query", "Ed Sheeran")),
    )
    # The readers' query keeps their «some» as before (old: «some Ed Sheeran»); the name goes as written.
    assert arguments["query"] == "some ed sheeren"


def test_what_must_not_change() -> None:
    # Said as it is: the model's value stays.
    arguments, _ = _arguments(
        "media.play.query", PLAY_QUERY, ["pon algo de mon laferte en spotify"],
        "Pon algo de Mon Laferte en Spotify.", (("provider", "Spotify"), ("query", "Mon Laferte")),
    )
    assert arguments["query"] == "Mon Laferte"
    arguments, _ = _arguments(
        "media.play.query", PLAY_QUERY, ["pon algo de soda stereo en spotify"],
        "Pon algo de Gustavo Cerati en Spotify.", (("provider", "Spotify"), ("query", "Gustavo Cerati")),
    )
    # M166: another artist altogether is no respelling, but an artist nobody said is not looked up: the artist the
    # person named is (``semantic.arguments.as_the_person_named``; was «Gustavo Cerati»).
    assert arguments["query"] == "soda stereo"
    # An application keeps the catalog's name the readers chose for the person's spelling (M127); a web search, a
    # note and a reminder keep the model's words.
    said = _history(["abreme el exel"])
    assert decided_arguments._as_the_person_spelled("app.open", {"appId": "Excel"}, "abreme el exel", said) == {"appId": "Excel"}
    said = _history(["busca quien es javiera mena"])
    assert decided_arguments._as_the_person_spelled(
        "web.search", {"query": "Javier Mené"}, "busca quien es javiera mena", said,
    ) == {"query": "Javier Mené"}
    said = _history(["recuérdame pagar la lus mañana"])
    assert decided_arguments._as_the_person_spelled(
        "reminder.create", {"title": "pagar la luz"}, "recuérdame pagar la lus mañana", said,
    ) == {"title": "pagar la luz"}


# ------------------------------------------------------------------ 2. I-w41-t3, a translation is no lookup

I_W41 = [
    "cuántos gramos son 3 tazas de harina de trigo, que la receta de mi mamá está en tazas",
    "No puedo saber ahora cuántos gramos son 3 tazas de harina de trigo.",
    "¿y en onzas?",
    "No puedo ver ahora cuántas onzas son 3 tazas de harina de trigo, pero puedo abrirlo en tu navegador web.",
    "tradúceme eso al inglés",
]


def test_i_w41_t3_the_translation_of_what_was_said_is_talk() -> None:
    result = _turn(I_W41, ContextDecision(
        "Traduce al inglés «¿Cuántas onzas son 3 tazas de harina de trigo?».", "talk", (), "",
    ))
    assert result["kind"] == "conversation"
    assert result["operation"] is None


def test_translations_in_other_words() -> None:
    for request in (
        "Traduce al inglés «¿Cuántas onzas son 3 tazas de harina de trigo?».",
        "Translate «¿cuántas cucharadas de azúcar lleva el queque?» into English.",
        "can you translate that to spanish? the bit about how many cups of flour",
        "oye tradúcemelo al portugués, lo de cuántos gramos de sal",
    ):
        assert translates_what_was_said(request), request
        assert reference_lookup(request) is None, request


def test_lookups_that_must_not_change() -> None:
    # The same kitchen question asked, not translated, is still looked up (M88); a recipe asked to be translated,
    # nothing said nor pointed at, is still the recipe looked up (M53).
    assert reference_lookup("¿Cuántas onzas son 3 tazas de harina de trigo?").kind == "quantity"
    assert reference_lookup("how many grams are 2 cups of flour").kind == "quantity"
    assert not translates_what_was_said("traduce la receta de las empanadas de pino al inglés")
    assert not translates_what_was_said("cuántas onzas son 3 tazas, y lo traduces después")


# ------------------------------------------------------------------ 3. I-w37-t3, what the note says is asked

I_W37 = [
    "oye, busca el archivo que se llama presupuesto_2026 en mis documentos",
    "No he encontrado un archivo llamado presupuesto_2026 en la carpeta Documentos.",
    "órale, ábremelo por favor",
    "No se pudo abrir el archivo presupuesto_2026 porque no existe en la carpeta Documentos.",
    "oye, de paso, crea una nota de la junta de hoy",
]


def test_i_w37_t3_a_note_named_by_its_topic_asks_what_it_says() -> None:
    decided = (("content", "Junta de hoy."), ("title", "Junta de hoy"))
    # The decider's values alone, and the extraction writing the title into the content too: both ask.
    for extracted in (None, {"title": "Junta de hoy", "content": "Junta de hoy."}):
        model = _Extraction(extracted)
        arguments, question = _arguments(
            "note.create", NOTE, I_W37, "Crea una nota de la junta de hoy.", decided, model,
        )
        assert arguments is None and question == "¿Qué quieres que diga la nota?"
        assert model.asked == [("content",)]


def test_i_w37_t4_the_answer_is_that_notes_content() -> None:
    # v4u asked as the fix now does; the next turn, with the question in the conversation, created the note.
    said = [*I_W37, "¿Qué contenido deseas incluir en la nota llamada «Junta de hoy»?",
            "que se decidió subir los precios un 5 por ciento"]
    request = "Crea una nota llamada «Junta de hoy» con el contenido «Se decidió subir los precios un 5 por ciento»."
    arguments, question = _arguments(
        "note.create", NOTE, said, request,
        (("content", "Se decidió subir los precios un 5 por ciento"), ("title", "Junta de hoy")),
    )
    assert question == ""
    assert arguments == {"title": "Junta de hoy", "content": "Se decidió subir los precios un 5 por ciento"}


def test_notes_named_only_by_their_topic_in_other_words() -> None:
    assert note_content_unsaid("hazme una nota sobre el cumpleaños de la Trini, porfa", "Cumpleaños de la Trini")
    assert note_content_unsaid("make a new note about today's meeting please", "Today's meeting.")
    assert note_content_unsaid("crea una nota llamada lista del súper", "Lista del súper")


def test_notes_that_must_not_change() -> None:
    # The content dictated, pointed at, or more than the topic; an empty content invents nothing.
    assert not note_content_unsaid("crea una nota que diga junta de hoy", "Junta de hoy")
    assert not note_content_unsaid("crea una nota de la junta de hoy: subir precios", "Junta de hoy")
    assert not note_content_unsaid("crea una nota de la junta de hoy y ponle que subimos precios", "Junta de hoy")
    assert not note_content_unsaid("anota la junta de hoy", "Junta de hoy")
    assert not note_content_unsaid("crea una nota de comprar pan", "Comprar pan")
    assert not note_content_unsaid("make a note about buying milk", "Buying milk")
    assert not note_content_unsaid("save that in a note called home network", "home network")
    assert not note_content_unsaid("Guárdamela en una nota que se llame tortilla", "tortilla")
    assert not note_content_unsaid("crea una nota de la junta de hoy", "Se decidió subir los precios un 5 %")
    assert not note_content_unsaid("crea una nota de la junta de hoy", "")
    # A note dictated and named in one message stays as created (M111).
    arguments, question = _arguments(
        "note.create", NOTE, ["crea una nota que se llame junta y pon ahí: subir los precios un 5 %"],
        "Crea una nota llamada «junta» con el contenido «subir los precios un 5 %».",
        (("content", "subir los precios un 5 %"), ("title", "junta")),
    )
    assert question == "" and arguments["content"] == "subir los precios un 5 %"
