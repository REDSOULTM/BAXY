"""M127 (2026-10-02, App runs v4i-devF/v4i-devD and mind run devc-v4i): BAXY helps the decider with arguments (D58).

The decision was right and the arguments wrong where BAXY's own steps dropped or deformed what the model had right, or
left out what the conversation had said:

1. The fidelity check of the decider's restatement (``semantic.decider.faithful_request``) took for invented:
   - a day counted from a day said («recuérdemelo el día antes …» after «la cita … es el 3 de octubre» restated «…el 2
     de octubre…»): the person's words became the objective and the reminder was titled «listo recuerdemelo el dia
     antes» (C-w10-t5);
   - a name written with a letter left out («el exel abierto» restated «Abre Excel.»: the app was asked again,
     C-w16-t1; owner rule 2026-09-19, lo mal dicho lo arregla BAXY);
   - a one-letter name as written («near U Street»: the chat spelling reads «u» as «you», and the search went out as
     «Is there handicap parking Street?», C-p07-t2).
2. The follow-up «la otra, la de estudio / la del disco» after a song: the restatement lost the song and Spotify
   looked for «canción de estudio» or «la canción del disco de los que sobran» (F-w36-t2, F-w60-t2).
3. A PDF named by its file name earlier in the conversation («Encontré dos en Descargas: «x.pdf» y …»): the decider
   put it in another folder, the fidelity check took that folder out, and the folder was asked again (C-w10-t4).

Every phrasing below is our own. The clock is fixed in every test.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.semantic import decider, dialogue
from baxy_mind.semantic.arguments import conversation_pdf, corrected_song_title

NOW = datetime(2026, 10, 1, 12, 30)


# ------------------------------------------------------------------ 1. fidelity: derived and corrected, not invented


@pytest.mark.parametrize(
    ("restated", "text", "conversation"),
    [
        (
            "Recuérdame el 6 de noviembre a las 19:00 el examen de piano del 7 de noviembre.",
            "ya, avísame el día antes a las 7 de la tarde",
            ["El examen de piano es el 7 de noviembre a las 9:00."],
        ),
        (
            "Remind me on December 2 at 8:00 about the dentist on December 4.",
            "ok remind me two days before at 8",
            ["Your dentist appointment is on December 4 at 16:30."],
        ),
        (
            "Pon una alarma el 14 de noviembre a las 6:00 para el vuelo del 15 de noviembre.",
            "ponme una alarma la víspera a las 6",
            ["Tu vuelo sale el 15 de noviembre a las 11:40."],
        ),
    ],
)
def test_a_day_counted_from_a_day_said_is_said(restated: str, text: str, conversation: list[str]) -> None:
    fidelity = decider.faithful_request(restated, text, conversation, now=NOW)
    assert fidelity.kind == "kept", fidelity


def test_a_day_nobody_counted_is_still_introduced() -> None:
    fidelity = decider.faithful_request(
        "Pon una alarma el 2 de octubre a las 7:00.", "pon una alarma a las 7", ["El partido es el 3 de octubre."],
        now=NOW,
    )
    assert fidelity.kind != "kept" and "2 de octubre" in fidelity.introduced


@pytest.mark.parametrize(
    ("restated", "text"),
    [
        ("Abre Excel.", "oye abreme el exel porfa"),
        ("Open Photoshop.", "open photshop for me"),
        ("Tell me my train options to Los Angeles next Friday.", "train options to los angles next friday"),
    ],
)
def test_a_name_said_with_one_letter_left_out_is_that_name(restated: str, text: str) -> None:
    assert decider.faithful_request(restated, text, [], now=NOW).kind == "kept"


@pytest.mark.parametrize(
    ("restated", "text"),
    [
        ("Abre Exceller.", "oye abreme el exel porfa"),  # two letters more
        ("Abre Lexel.", "oye abreme el exel porfa"),  # not the first letter
        ("Abre Excel.", "oye abreme el exl porfa"),  # three letters said are no name
        ("Escríbele a Marta por WhatsApp que ya llegué.", "escribele a mara por wsp que ya llegue"),  # someone else
        ("Send the photo to Marta on Discord.", "send the photo to mara on discord"),
    ],
)
def test_a_name_further_from_what_was_said_is_still_introduced(restated: str, text: str) -> None:
    assert decider.faithful_request(restated, text, [], now=NOW).kind != "kept"


def test_a_one_letter_name_as_written_is_said() -> None:
    fidelity = decider.faithful_request(
        "Find coffee shops near U Street.", "any coffee shops near U Street?", [], now=NOW,
    )
    assert fidelity == decider.Fidelity("Find coffee shops near U Street.")


# ------------------------------------------------------------------ 2. «la otra, la de estudio»


@pytest.mark.parametrize(
    ("message", "before", "reply", "song"),
    [
        ("no, esa no, la otra, la de estudio", "ponme vivir sin aire de maná", "", "vivir sin aire de maná"),
        ("nah not that one, the studio version", "play hotel california please", "", "hotel california"),
        ("no esa no, la del disco", "pon cielito lindo", "", "cielito lindo"),
        (
            "no po, la otra, la de estudio",
            "ponme labios rotos de zoé",
            "Sonando «Labios rotos» de Zoé, en vivo desde el Unplugged.",
            "Labios rotos",
        ),
    ],
)
def test_the_album_version_asked_after_a_song_is_that_song(message: str, before: str, reply: str, song: str) -> None:
    assert corrected_song_title(message, before, reply) == song


@pytest.mark.parametrize(
    ("message", "before"),
    [
        ("no, la otra, la en vivo", "ponme vivir sin aire de maná"),  # another version stays with the extraction
        ("pon la versión de estudio de «Oye mi amor»", "ponme vivir sin aire de maná"),  # names its own song
        ("no, la de estudio", "qué hora es"),  # nothing was played before
        ("no esa no, la otra", "ponme vivir sin aire de maná"),  # no version asked
    ],
)
def test_no_song_is_carried_when_the_message_does_not_ask_its_album_version(message: str, before: str) -> None:
    assert corrected_song_title(message, before) is None


EXACT_SCHEMA = {
    "type": "object",
    "properties": {
        "provider": {"type": "string", "enum": ["spotify"]},
        "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
    },
    "required": ["provider", "title"],
    "additionalProperties": False,
}


def _tool(operation: str, schema: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "external_communication",
            "parameters": schema,
        },
    }


class _Abstaining:
    """The model's own extraction abstains: only BAXY's steps ground the arguments."""

    def extract_direct_arguments(self, *_args: object, **_kwargs: object) -> llm.DirectArgumentExtraction:
        return llm.DirectArgumentExtraction(arguments=None, evidence=(), fallback_question="¿Qué canción?")

    def formulate_missing_argument_question(self, *_args: object, **_kwargs: object) -> str:
        return "¿Qué canción?"


def _exact(request: str, history: list[dict[str, str]]) -> tuple[dict | None, str]:
    return sidecar._direct_arguments_result(
        {"operation": "media.play.exact", "text": request, "history": history},
        llm=_Abstaining(),
        tool=_tool("media.play.exact", EXACT_SCHEMA),
        dialogue_state=dialogue.DialogueState(),
    )


def test_the_arguments_step_plays_the_song_asked_before_in_its_album_version() -> None:
    history = [
        {"role": "user", "content": "ponme vivir sin aire de maná"},
        {"role": "assistant", "content": "No se pudo confirmar que empezara el video en YouTube."},
        {"role": "user", "content": "no, esa no, la otra, la de estudio"},
    ]
    arguments, question = _exact("Pon la canción de estudio de la banda.", history)
    assert (arguments, question) == ({"provider": "spotify", "title": "vivir sin aire de maná"}, "")


PDF_SCHEMA = {
    "type": "object",
    "properties": {
        "fileName": {"type": "string", "x-maxUtf8Bytes": 512, "x-nonWhitespace": True},
        "folder": {"type": "string", "enum": ["all_known", "desktop", "documents", "downloads"]},
        "maximumCharacters": {"type": "integer", "minimum": 200, "maximum": 200000},
    },
    "required": ["fileName", "folder"],
    "additionalProperties": False,
}
FOUND_TWO = [
    "oye búscame el pdf del arriendo que me llegó ayer",
    "Hay dos en Descargas: «contrato_arriendo_2026.pdf» y «anexo_arriendo.pdf». ¿Cuál abro?",
    "el del contrato",
    "Abrí «contrato_arriendo_2026.pdf».",
]


def test_a_pdf_named_earlier_is_read_in_the_folder_the_conversation_said() -> None:
    assert conversation_pdf("Lee el PDF «contrato_arriendo_2026.pdf» y dime cuándo vence.", FOUND_TWO) == {
        "fileName": "contrato_arriendo_2026.pdf", "folder": "downloads",
    }


def test_a_pdf_named_earlier_with_no_one_folder_is_looked_for_in_every_known_folder() -> None:
    conversation = [
        "¿dónde quedó el informe_q3.pdf?",
        "No encontré informe_q3.pdf en el escritorio, en documentos ni en descargas.",
    ]
    assert conversation_pdf("Resume informe_q3.pdf en dos líneas.", conversation) == {
        "fileName": "informe_q3.pdf", "folder": "all_known",
    }


@pytest.mark.parametrize(
    "request_text",
    [
        "Lee el PDF «presupuesto.pdf» de Documentos.",  # a file nobody wrote in the conversation
        "Compara «contrato_arriendo_2026.pdf» con «anexo_arriendo.pdf».",  # two files
        "Lee el PDF del contrato.",  # no file name
    ],
)
def test_no_pdf_is_taken_when_the_conversation_did_not_write_its_one_name(request_text: str) -> None:
    assert conversation_pdf(request_text, FOUND_TWO) is None


def test_the_arguments_step_reads_the_pdf_where_the_conversation_found_it() -> None:
    history = [{"role": role, "content": content} for role, content in zip(("user", "assistant") * 2, FOUND_TWO)]
    history.append({"role": "user", "content": "ya, y qué dice de la fecha en ese papel"})
    arguments, question = sidecar._direct_arguments_result(
        {"operation": "document.pdf.read", "text": "Lee el PDF «contrato_arriendo_2026.pdf» y dime la fecha.",
         "history": history},
        llm=_Abstaining(),
        tool=_tool("document.pdf.read", PDF_SCHEMA),
        dialogue_state=dialogue.DialogueState(),
    )
    assert (arguments, question) == ({"fileName": "contrato_arriendo_2026.pdf", "folder": "downloads"}, "")


def test_a_title_that_is_part_of_the_song_asked_stays() -> None:
    history = [
        {"role": "user", "content": "ponme vivir sin aire de maná"},
        {"role": "assistant", "content": "Sonando en vivo."},
        {"role": "user", "content": "no, esa no, la otra, la de estudio"},
    ]
    arguments, question = _exact("Pon la versión de estudio de «Vivir sin aire» de Maná.", history)
    assert (arguments, question) == ({"provider": "spotify", "title": "Vivir sin aire"}, "")
