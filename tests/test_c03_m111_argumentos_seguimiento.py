"""M111 (2026-10-01): arguments lost on DEV-F v4d (code 194e12f6), most of them in follow-ups.

Every phrasing below is this file's own, of the same shape as the DEV-F row it stands for.

1. A message left written (F-s005, F-s014, F-s033, F-w05-t2, F-w29-t2): «déjale escrito a X en WhatsApp que …»,
   «draft a discord message to X saying …», «… un wsp a la X que …» were read by no reader; the decider's values or
   the extraction lost the text (asked «¿Qué mensaje…?»). The order not to send it is the person's, never the text;
   with it, any message order is a draft, read before every reader that sends one, and the compound veto does not take
   that order for a negated second effect.
2. New words for the draft just asked (F-w01-t4 «mejor cámbialo, ponle que …» → «No puedo cambiar el mensaje…»): the
   same draft again, to the same person in the same client; leaving a message written is never a limit.
3. «mándaselo a Ana»: the recipient is this message's, the words those of the last draft or of the reply the person
   asked BAXY to write.
4. A note named and filled at once (F-s021 «crea una nota que se llame X y pone ahi: …» → a YouTube search beside the
   note); a note named by a word of the title it got earlier (F-w03-t6 «la nota del snippet»).
5. The rest: a misspelled service (F-s038 «netflx»), a word mistyped by two swapped letters (F-s003 «wrod»), a file
   «que está en documentos» (F-s025, refused as «No abro archivos» though ``file.open`` serves it), the name a file is
   said to have (F-s020), the song of an exact play without its artist (F-s023), the night light switched (F-w56-t3).
6. The measure (``scripts/comprension_window.py``): what the dependency step of a window or a task effect was asked to
   find is that effect's argument (F-w30-t2, F-w08-t3), without the prose of its failure.
"""

from __future__ import annotations


import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import effect_intent
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import decider, dialogue
from baxy_mind.semantic.intent import EffectIntent
from baxy_mind.semantic.notes import conversation_note_title
from baxy_mind.semantic.patterns import _PAST_STATEMENT, known_unsupported_effect_request, unresolved_compound_contract

MESSAGING = ("message.draft", "message.send", "message.recipient.resolve", "message.send.test")
DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "channel": {"type": "string", "enum": ["discord", "whatsapp"]},
        "recipient": {"type": "string", "x-maxUtf8Bytes": 512, "x-nonWhitespace": True},
        "text": {"type": "string", "x-maxUtf8Bytes": 16384, "x-nonWhitespace": True},
    },
    "required": ["channel", "recipient", "text"],
    "additionalProperties": False,
}


def _tool(operation: str, schema: dict | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "low_reversible",
            "parameters": schema or {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }


class _Model:
    """The decider answers what it is given; the extraction must never be needed."""

    def __init__(self, decision: str = "action", operations: tuple[str, ...] = (), request: str = "") -> None:
        self.decision, self.operations, self.request = decision, operations, request

    def decide_in_context(self, text: str, *_args: object, **_kwargs: object) -> decider.ContextDecision:
        return decider.ContextDecision(
            request=self.request or text, decision=self.decision, operations=self.operations, question="",
        )

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        return "Te cuento.", []

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    def extract_direct_arguments(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("the readers had the arguments")


# ------------------------------------------------------------------ 1. a message left written


@pytest.mark.parametrize(
    ("text", "draft"),
    [
        ("déjale escrito a Rocío por WhatsApp que llego a las nueve, pero no se lo mandes",
         ("whatsapp", "Rocío", "llego a las nueve")),
        ("draft a whatsapp message to Ben saying the keys are under the mat, don't send it",
         ("whatsapp", "Ben", "the keys are under the mat")),
        ("dejale escrito un wsp al Nacho que mañana no hay clases, no lo mandes eso sí",
         ("whatsapp", "Nacho", "mañana no hay clases")),
        ("y déjale escrito en Discord a Sam: «subo el parche mañana»", ("discord", "Sam", "subo el parche mañana")),
        ("escríbele a Lucía por WhatsApp que ya salí, sin enviarlo todavía", ("whatsapp", "Lucía", "ya salí")),
        ("Deja escrito a la Coni en WhatsApp que paso a las 8:30, sin enviarlo.", ("whatsapp", "Coni", "paso a las 8:30")),
    ],
)
def test_a_message_left_written_is_read_whole(text: str, draft: tuple[str, str, str]) -> None:
    assert effect_intent.message_left_written_request(text) == draft
    assert sidecar._ground_explicit_arguments("message.draft", text, DRAFT_SCHEMA) == dict(
        zip(("channel", "recipient", "text"), draft),
    )


@pytest.mark.parametrize(
    "text",
    [
        "déjale escrito a Rocío que llego a las nueve",  # no client: the client is asked
        "mándale a Rocío por WhatsApp que llego a las nueve",  # no order not to send: not this reader's
        "déjale escrito a Rocío por correo que llego a las nueve, no lo mandes",  # mail is not a chat draft
    ],
)
def test_without_client_or_without_leaving_it_written_it_is_no_draft_here(text: str) -> None:
    assert effect_intent.message_left_written_request(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "escríbele a Lucía por WhatsApp que ya salí, pero no se lo mandes",
        "déjale escrito a Rocío por WhatsApp que llego a las nueve, no lo envíes",
        "draft a discord message to Ben saying we start at nine, dont send it yet",
    ],
)
def test_a_message_not_to_be_sent_is_a_draft_never_a_send(text: str) -> None:
    read = effect_intent.resolve_explicit_effects(text, MESSAGING)
    assert read is not None and read.operations == ("message.draft",)
    assert unresolved_compound_contract(text, MESSAGING, resolved_intent=EffectIntent(("message.draft",), (text,))) is None


# ------------------------------------------------------------------ 2. new words for the draft just asked

DRAFT_ASKED = "déjale escrito a Rocío por WhatsApp que llego a las nueve, pero no se lo mandes"


@pytest.mark.parametrize(
    ("text", "earlier", "rewritten"),
    [
        ("mejor cámbialo, ponle que llego a las diez porque hay taco", [DRAFT_ASKED],
         "déjale escrito a Rocío en WhatsApp que llego a las diez porque hay taco"),
        ("no, ponle mejor que no voy a poder ir", ["qué hora es", DRAFT_ASKED],
         "déjale escrito a Rocío en WhatsApp que no voy a poder ir"),
        ("actually change it, make it say that we moved it to Friday",
         ["draft a discord message to Ben saying we play tonight, don't send it"],
         "draft a Discord message to Ben saying we moved it to Friday"),
    ],
)
def test_new_words_for_the_last_draft_are_that_draft_again(text: str, earlier: list[str], rewritten: str) -> None:
    assert effect_intent.edited_draft_request(text, earlier) == rewritten
    assert effect_intent.message_left_written_request(rewritten) is not None


@pytest.mark.parametrize(
    ("text", "earlier"),
    [
        ("mejor ponle que llego a las diez", ["pon una alarma a las nueve"]),  # no draft before
        ("uy, poné una hora mejor", [DRAFT_ASKED]),  # part of the old words: not said whole
        ("cámbialo", [DRAFT_ASKED]),  # no new words
    ],
)
def test_no_draft_or_no_whole_new_words_is_not_read(text: str, earlier: list[str]) -> None:
    assert effect_intent.edited_draft_request(text, earlier) is None


def test_the_decider_limit_on_changing_a_draft_becomes_that_draft() -> None:
    text = "mejor cámbialo, ponle que llego a las diez"
    history = [
        {"role": "user", "content": DRAFT_ASKED},
        {"role": "assistant", "content": "No pude dejar escrito el mensaje."},
        {"role": "user", "content": text},
    ]
    result = sidecar._context_decided_result(
        {"id": "m111", "text": text, "history": history},
        llm=_Model("limit", request="Cambia el mensaje de WhatsApp a Rocío: «Llego a las diez»."),
        planner_catalog=PlannerCatalog([_tool("message.draft", DRAFT_SCHEMA)]),
    )
    assert result["kind"] == "action" and result["operation"] == "message.draft"
    assert result["objective"] == "déjale escrito a Rocío en WhatsApp que llego a las diez"


# ------------------------------------------------------------------ 3. «mándaselo a Ana»


def test_the_reply_asked_for_goes_to_the_person_named_now() -> None:
    assert effect_intent.forwarded_draft(
        "mándaselo a Ana por WhatsApp",
        ["escríbeme un mensaje para felicitar a mi jefa por su ascenso"],
        "¡Felicitaciones por el ascenso, te lo mereces!",
        True,
    ) == ("whatsapp", "Ana", "¡Felicitaciones por el ascenso, te lo mereces!")


def test_the_last_draft_goes_to_another_person_in_its_client() -> None:
    assert effect_intent.forwarded_draft(
        "y déjaselo escrito también a Pedro", [DRAFT_ASKED], "Le dejé escrito a Rocío en WhatsApp.", False,
    ) == ("whatsapp", "Pedro", "llego a las nueve")


@pytest.mark.parametrize(
    ("text", "earlier", "reply", "asked"),
    [
        ("mándaselo a Ana", ["escríbeme un mensaje para Ana"], "Claro: «Hola Ana».", True),  # no client known
        ("mándaselo a Ana por WhatsApp", ["qué hora es"], "Son las 10:20.", False),  # nothing written before
        ("mándale a Ana por WhatsApp que ya llegué", [DRAFT_ASKED], "Listo.", False),  # words of its own
    ],
)
def test_nothing_written_or_words_of_its_own_are_not_forwarded(
    text: str, earlier: list[str], reply: str, asked: bool,
) -> None:
    assert effect_intent.forwarded_draft(text, earlier, reply, asked) is None


def test_the_arguments_step_forwards_the_reply_asked_for() -> None:
    history = [
        {"role": "user", "content": "redáctame un mensaje cortito para disculparme por llegar tarde"},
        {"role": "assistant", "content": "Perdón por llegar tarde, se me complicó el tránsito."},
        {"role": "user", "content": "mándaselo a Tomás por WhatsApp"},
    ]
    arguments, question = sidecar._direct_arguments_result(
        {"operation": "message.draft", "text": "Deja escrito a Tomás por WhatsApp el mensaje.", "history": history},
        llm=_Model(),
        tool=_tool("message.draft", DRAFT_SCHEMA),
        dialogue_state=dialogue.DialogueState(),
    )
    assert question == ""
    assert arguments == {
        "channel": "whatsapp", "recipient": "Tomás", "text": "Perdón por llegar tarde, se me complicó el tránsito.",
    }


# ------------------------------------------------------------------ 4. notes

NOTE_SCHEMA = {
    "type": "object",
    "properties": {"content": {"type": "string"}, "title": {"type": "string", "x-nonWhitespace": True}},
    "required": ["content", "title"],
    "additionalProperties": False,
}


@pytest.mark.parametrize(
    ("text", "note"),
    [
        ("crea una nota que se llame viaje y pon ahí: pasaporte, cargador y toalla",
         ("viaje", "pasaporte, cargador y toalla")),
        ("hazme una nota llamada «asado» y anótale que faltan carbón y hielo", ("asado", "faltan carbón y hielo")),
        ("create a note called gifts and write in it: socks for dad, a book for Ana", ("gifts", "socks for dad, a book for Ana")),
    ],
)
def test_a_note_named_and_filled_is_one_note(text: str, note: tuple[str, str]) -> None:
    read = effect_intent.resolve_explicit_effects(text, ("note.create", "media.play.youtube", "media.play.query"))
    assert read is not None and read.operations == ("note.create",)
    assert sidecar._ground_explicit_arguments("note.create", text, NOTE_SCHEMA) == {"title": note[0], "content": note[1]}


CONVERSATION = [
    "guarda ese resumen en una nota, ponle de título presupuesto viaje sur",
    "Listo, guardé la nota «presupuesto viaje sur».",
    "y qué tiempo hace en Puerto Montt?",
    "Llueve, 9 grados.",
]


@pytest.mark.parametrize(
    "request_text", ["léeme la nota del presupuesto", "ah y la nota sobre el viaje, léemela", "read me the budget note"],
)
def test_a_note_named_by_a_word_of_its_title_is_that_note(request_text: str) -> None:
    expected = None if "budget" in request_text else "presupuesto viaje sur"
    assert conversation_note_title(request_text, CONVERSATION) == expected


def test_a_word_two_titles_hold_names_no_note() -> None:
    two = [*CONVERSATION, "otra nota llamada presupuesto casa", "Guardé la nota «presupuesto casa»."]
    assert conversation_note_title("léeme la nota del presupuesto", two) is None


# ------------------------------------------------------------------ 5. the rest


def test_a_misspelled_service_is_still_the_service() -> None:
    text = "ponme el juego del calamar en netflx porfa"
    read = effect_intent.resolve_explicit_effects(text, ("streaming.play.named", "media.play.youtube"))
    assert read is not None and read.operations == ("streaming.play.named",)


def test_two_swapped_letters_are_the_word_said() -> None:
    assert decider.faithful_request("Abre Spotify.", "abre el spotfiy porfa", []).kind == "kept"
    # A name a letter away, not two swapped, is not the one said.
    assert decider.faithful_request("Abre Notion.", "abre el nation porfa", []).kind != "kept"


FILE_OPEN_SCHEMA = {
    "type": "object",
    "properties": {
        "folder": {"type": "string", "enum": ["desktop", "documents", "downloads", "pictures"]},
        "name": {"type": "string", "x-maxUtf8Bytes": 200, "x-nonWhitespace": True},
    },
    "required": ["folder", "name"],
    "additionalProperties": False,
}


def test_a_file_where_it_is_said_as_a_clause_is_opened() -> None:
    text = "ábreme el archivo notas_clase.docx que está en descargas"
    assert not known_unsupported_effect_request(text, {"file.open"})
    read = effect_intent.resolve_explicit_effects(text, ("file.open",))
    assert read is not None and read.operations == ("file.open",)
    assert sidecar._ground_explicit_arguments("file.open", text, FILE_OPEN_SCHEMA) == {
        "folder": "downloads", "name": "notas_clase.docx",
    }


SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "folder": {"type": "string", "enum": ["all_known", "desktop", "documents", "downloads"]},
        "query": {"type": "string", "x-nonWhitespace": True},
    },
    "required": ["folder", "query"],
    "additionalProperties": False,
}


@pytest.mark.parametrize(
    ("text", "arguments"),
    [
        ("busca en el escritorio la factura de la luz, creo que se llamaba boleta enel algo",
         {"folder": "desktop", "query": "boleta enel"}),
        ("find the spreadsheet called rent split in my downloads", {"folder": "downloads", "query": "rent split"}),
    ],
)
def test_the_name_a_file_is_said_to_have_is_searched(text: str, arguments: dict) -> None:
    assert sidecar._ground_explicit_arguments("filesystem.known.search", text, SEARCH_SCHEMA) == arguments


EXACT_SCHEMA = {
    "type": "object",
    "properties": {"provider": {"type": "string", "enum": ["spotify"]}, "title": {"type": "string"}},
    "required": ["provider", "title"],
    "additionalProperties": False,
}


@pytest.mark.parametrize(
    ("text", "title"),
    [
        ("Play Bohemian Rhapsody by Queen.", "Bohemian Rhapsody"),
        ("Pon «Rayando el sol» de Maná.", "Rayando el sol"),
        ("Pon la versión acústica de «Rayando el sol».", None),  # a version is no title
    ],
)
def test_the_song_of_an_exact_play_is_its_title(text: str, title: str | None) -> None:
    expected = None if title is None else {"provider": "spotify", "title": title}
    assert sidecar._ground_explicit_arguments("media.play.exact", text, EXACT_SCHEMA) == expected


@pytest.mark.parametrize(
    ("text", "switched"),
    [
        ("prende la luz nocturna porfa", ("night_light", 1)),
        ("turn off the night light", ("night_light", 0)),
        ("desactiva el no molestar", ("do_not_disturb", 0)),
        ("ponme el modo avión", ("airplane_mode", 1)),
        ("¿está activada la luz nocturna?", None),
    ],
)
def test_a_setting_switched_on_or_off(text: str, switched: tuple[str, int] | None) -> None:
    assert effect_intent.setting_switch_request(text) == switched


def test_what_was_not_done_yet_is_said_not_ordered() -> None:
    operations = ("email.latest.read", "file.open", "app.open")
    text = "léeme el último correo que me llegó, creo que es del banco, y todavía no lo he abierto"
    read = EffectIntent(("email.latest.read",), (text,))
    assert unresolved_compound_contract(text, operations, resolved_intent=read) is None
    assert _PAST_STATEMENT.match("and i haven't opened it yet")
    # An order not to do it is no statement.
    assert not _PAST_STATEMENT.match("y no lo abras")


def test_the_restatement_opens_each_application_it_names() -> None:
    text = "¿Me abrirías Paint y el Bloc de notas?"
    result = sidecar._context_decided_result(
        {"id": "m111", "text": text, "history": [{"role": "user", "content": text}]},
        llm=_Model("action", ("app.open",), "Abre Paint y el Bloc de notas."),
        planner_catalog=PlannerCatalog([_tool("app.open")]),
        application_names=("Paint", "Bloc de notas"),
    )
    assert result["kind"] == "plan"
    assert result["effectOperations"] == ["app.open", "app.open"]


# ------------------------------------------------------------------ 6. the measure


