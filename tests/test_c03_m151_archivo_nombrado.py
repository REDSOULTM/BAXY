"""M151 (2026-10-04, App runs v4s-devF/G/H): the file BAXY just named is the one read or opened (D58).

The conversation had already named a file by its file name, almost always in BAXY's last reply. The person then asked
what it says («read it», «qué dice», «give us the gist of it», «resumemelo en corto», «y de qué trata? resumímelo así
nomás»), or picked one of the files BAXY listed after they had asked for a summary («the signed one», «la de pisos»), or
picked one to open by its place in the list («abre el segundo»). The decider in context chose ``file.open``,
``filesystem.file.open.latest``, ``filesystem.known.search``, a plan ``file.open`` + ``document.pdf.read``, or read
another file (the first instead of the ``_v2``, in the other folder):

- F-w18-t2, F-w22-t3, G-w44-t5 → ``file.open``; F-w24-t3 → ``filesystem.known.search``; H-w23-t3 →
  ``filesystem.file.open.latest``; H-w32-t2 → the plan; G-w40-t3 → ``document.pdf.read`` of «cotizacion_mudanza» in
  Descargas; G-w40-t2 «abre el segundo» → ``filesystem.file.open.latest``.

Now a decision that opens, finds or reads a file is, when the message means the one file BAXY named
(``semantic.files.named_file_meant``), the reader its extension takes (a PDF the PDF reader, a text file the text
reader) or ``file.open`` for «abre el segundo», on that file, in the folder the conversation said (M127,
``semantic.arguments.conversation_file_folder``). Everything else is left as the decider decided.

Rows are quoted with their real text; every other phrasing is our own.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.arguments import conversation_file_folder, conversation_pdf, conversation_text_file
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.files import NamedFileMeant, files_named_in_reply, named_file_meant, named_file_operation

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
TEXT_SCHEMA = {
    "type": "object",
    "properties": {
        "fileName": {"type": "string", "x-maxUtf8Bytes": 512, "x-nonWhitespace": True},
        "folder": {"type": "string", "enum": ["all_known", "desktop", "documents", "downloads"]},
        "maximumCharacters": {"type": "integer", "minimum": 200, "maximum": 200000},
        "subdirectory": {"type": "string", "x-maxUtf8Bytes": 512, "x-nonWhitespace": True},
    },
    "required": ["fileName", "folder"],
    "additionalProperties": False,
}
OPEN_SCHEMA = {
    "type": "object",
    "properties": {
        "folder": {"type": "string", "enum": ["desktop", "documents", "downloads", "pictures"]},
        "name": {"type": "string", "x-maxUtf8Bytes": 200, "x-nonWhitespace": True},
    },
    "required": ["folder", "name"],
    "additionalProperties": False,
}
SCHEMAS = {"document.pdf.read": PDF_SCHEMA, "document.text.read": TEXT_SCHEMA, "file.open": OPEN_SCHEMA}
OPERATIONS = tuple(
    json.loads(
        (pathlib.Path(sidecar.__file__).parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
)


def _tool(operation: str) -> dict[str, Any]:
    schema = SCHEMAS.get(operation) or {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "read_only", "parameters": schema}}


class _Decider:
    """The model of a whole turn: the decider answers what it is given; every other call is neutral."""

    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision

    def decide_in_context(self, *_a, **_k):
        return self.decision

    def prepare_decision(self, *_a, **_k):
        return None

    def formulate_explicit_clarification_question(self, *_a, **_k):
        return "¿Cuál?"

    def clarify_after_turn_failure(self, *_a, **_k):
        return "¿Qué quieres que haga?"

    def clarify_unresolved_input(self, *_a, **_k):
        return "¿Qué quieres decir?"

    def public_lookup_requested(self, _text):
        return False

    def operation_is_the_requested_effect(self, *_a, **_k):
        return True

    def _verify_semantic_effect_shape(self, _text):
        return "complete", "one"

    def chat(self, *_a, **_k):
        return "Respuesta.", []

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


def _history(said: list[str]) -> list[dict[str, str]]:
    """``said``: the conversation, user first and alternating, ending in the person's message."""

    return [{"role": "user" if index % 2 == 0 else "assistant", "content": line} for index, line in enumerate(said)]


def _turn(said: list[str], decision: ContextDecision) -> dict:
    tools = {name: _tool(name) for name in OPERATIONS}
    return sidecar._prepare_turn_result(
        {"id": "m151", "text": said[-1], "history": _history(said)},
        llm=_Decider(decision), planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (),
        tool_by_name=tools, dialogue_state=DialogueState(),
    )


def _arguments(said: list[str], operation: str, objective: str) -> tuple[dict | None, str]:
    return sidecar._direct_arguments_result(
        {"operation": operation, "text": objective, "history": _history(said)},
        llm=_Abstaining(), tool=_tool(operation), dialogue_state=DialogueState(),
    )


def _decided(request: str, *operations: str, **arguments: str) -> ContextDecision:
    return ContextDecision(request, "action", operations, "", tuple(arguments.items()))


# ------------------------------------------------------------------ the rows, with the decider's v4s decision

COUNCIL = [
    "Right, can you pull up my Downloads folder? I'm after the council tax letter I saved last week, it's in there "
    "somewhere",
    "Downloads is open; I can see «council_tax_2026-27.pdf», saved on 24 September.",
]
LEASE = [
    "could you open my Downloads folder please", "Opened Downloads.",
    "great, can you summarize the lease PDF in there?",
    "There are two: lease_2026_signed.pdf and lease_2026_draft.pdf. Which one?",
]
QUOTES = [
    "mostrame descargas en el explorador q ahi deje unos papeles del apto", "Listo, abrí Descargas.",
    "ahi hay una cotizacion que me mandaron, resumimela",
    "Hay dos: «cotizacion_pintura_apto.pdf» y «cotizacion_pisos_laminados.pdf». ¿Cuál te resumo?",
]
MOVING = [
    "busca un archivo que se llama cotizacion_mudanza",
    "Encontré dos: «cotizacion_mudanza.pdf» en Descargas y «cotizacion_mudanza_v2.pdf» en Documentos.",
]
MOVING_OPENED = [*MOVING, "abre el segundo", "Listo, abrí «cotizacion_mudanza_v2.pdf»."]
BILL = [
    "oye baxy cómo se hace la tortilla de patatas pa cuatro personas",
    "Para 4: 6 huevos, 4 patatas medianas, 1 cebolla, aceite y sal. Pocha patata y cebolla a fuego suave 20 min, mezcla "
    "con el huevo batido y cuaja 4 min por cada lado.",
    "y eso pa dos", "Para 2: 3 huevos, 2 patatas, media cebolla, mismo proceso.",
    "vale guárdame eso en una nota y ponle de título tortilla", "Guardada la nota «tortilla» con la receta para 2.",
    "ahora ábreme lo último que me he bajado", "Abierto factura_luz_septiembre.pdf, el último de Descargas.",
]
INVOICE = [
    "open downloads", "Downloads is open.", "whats the newest file in there",
    "The newest one is invoice_sept_2026.pdf, from this morning.",
]
PROGRAM = ["che, abrime lo último que bajé", "Abrí «programa_jornadas_ingenieria_uba.pdf», lo último en Descargas."]

ROWS = [
    pytest.param(
        [*COUNCIL, "Yeah, that's the one, give us the gist of it"],
        _decided("Read the council tax letter from my Downloads folder.", "file.open", folder="downloads",
                 name="council tax letter"),
        "document.pdf.read", {"fileName": "council_tax_2026-27.pdf", "folder": "downloads"},
        id="F-w18-t2",
    ),
    pytest.param(
        [*LEASE, "the signed one"],
        _decided("Read the signed lease PDF from my Downloads folder.", "file.open", folder="downloads",
                 name="lease signed"),
        # No line wrote the file with a folder: every known folder (PDF1689).
        "document.pdf.read", {"fileName": "lease_2026_signed.pdf", "folder": "all_known"},
        id="F-w22-t3",
    ),
    pytest.param(
        [*QUOTES, "la de pisos"],
        _decided("Busca en Descargas un archivo con «pisos».", "filesystem.known.search", folder="downloads",
                 query="pisos"),
        "document.pdf.read", {"fileName": "cotizacion_pisos_laminados.pdf", "folder": "all_known"},
        id="F-w24-t3",
    ),
    pytest.param(
        [*MOVING, "abre el segundo"],
        _decided("Abre el segundo archivo de la carpeta de descargas.", "filesystem.file.open.latest",
                 folder="downloads"),
        "file.open", {"folder": "documents", "name": "cotizacion_mudanza_v2.pdf"},
        id="G-w40-t2",
    ),
    pytest.param(
        [*MOVING_OPENED, "resumemelo en corto"],
        _decided("Resumí en corto el archivo cotizacion_mudanza de la carpeta de descargas.", "document.pdf.read",
                 fileName="cotizacion_mudanza", folder="downloads"),
        "document.pdf.read", {"fileName": "cotizacion_mudanza_v2.pdf", "folder": "documents"},
        id="G-w40-t3",
    ),
    pytest.param(
        [*BILL, "qué dice"],
        _decided("¿Qué dice el archivo más reciente?", "file.open", folder="downloads", name="archivo más reciente"),
        "document.pdf.read", {"fileName": "factura_luz_septiembre.pdf", "folder": "downloads"},
        id="G-w44-t5",
    ),
    pytest.param(
        [*INVOICE, "read it"],
        _decided("Open the newest file in Downloads.", "filesystem.file.open.latest", folder="downloads"),
        "document.pdf.read", {"fileName": "invoice_sept_2026.pdf", "folder": "all_known"},
        id="H-w23-t3",
    ),
    pytest.param(
        [*PROGRAM, "y de qué trata? resumímelo así nomás"],
        _decided("Resumime el PDF más reciente de Descargas.", "file.open", "document.pdf.read", folder="downloads"),
        "document.pdf.read", {"fileName": "programa_jornadas_ingenieria_uba.pdf", "folder": "downloads"},
        id="H-w32-t2",
    ),
]


@pytest.mark.parametrize(("said", "decision", "operation", "arguments"), ROWS)
def test_the_rows_read_or_open_the_file_baxy_named(
    said: list[str], decision: ContextDecision, operation: str, arguments: dict[str, str],
) -> None:
    result = _turn(said, decision)
    assert (result["kind"], result["effectOperations"]) == ("action", [operation]), result
    assert _arguments(said, operation, result["objective"]) == (arguments, "")


# ------------------------------------------------------------------ the reader: our own words, both languages


@pytest.mark.parametrize(
    ("message", "reply", "before", "meant"),
    [
        # One file named: what it says is asked.
        ("léemelo porfa", "Abrí «acta_reunion.pdf» en Documentos.", "", ("read", "acta_reunion.pdf")),
        ("¿y de qué va?", "Ahí está informe_final.pdf, en el escritorio.", "", ("read", "informe_final.pdf")),
        ("sum it up for me", "Opened «quarterly_report.pdf».", "", ("read", "quarterly_report.pdf")),
        ("what does it say?", "I found notes_meeting.txt on your Desktop.", "", ("read", "notes_meeting.txt")),
        ("dime qué pone", "Tienes «receta_abuela.md» en Descargas.", "", ("read", "receta_abuela.md")),
        # Several listed: one picked by a word of its name only, after a summary was asked.
        ("el de agosto", "Hay dos: «extracto_julio.pdf» y «extracto_agosto.pdf».", "resúmeme el extracto del banco",
         ("read", "extracto_agosto.pdf")),
        ("the 2025 one", "I see tax_return_2024.pdf and tax_return_2025.pdf. Which one?",
         "can you summarize my tax return", ("read", "tax_return_2025.pdf")),
        # Several listed: one picked by its place, and what is done is said.
        ("léeme el primero", "Encontré «menu_semana.pdf» y «menu_fiesta.pdf».", "", ("read", "menu_semana.pdf")),
        ("open the second one", "There are two: «cv_english.pdf» in Documents and «cv_spanish.pdf» in Downloads.", "",
         ("open", "cv_spanish.pdf")),
        ("ábreme la de pisos", "Hay dos: «cotizacion_pintura_apto.pdf» y «cotizacion_pisos_laminados.pdf».", "",
         ("open", "cotizacion_pisos_laminados.pdf")),
    ],
)
def test_other_words_mean_the_file_baxy_named(message: str, reply: str, before: str, meant: tuple[str, str]) -> None:
    found = named_file_meant(message, reply, before)
    assert found is not None and (found.act, found.name) == meant


@pytest.mark.parametrize(
    ("message", "reply", "before"),
    [
        ("ábrelo", "Abrí «acta_reunion.pdf» en Documentos.", ""),  # one file: opening stays opening
        ("open it", "I can see «council_tax_2026-27.pdf» in Downloads.", ""),
        ("resúmelo", "Hay dos: «extracto_julio.pdf» y «extracto_agosto.pdf».", ""),  # two files, none picked
        ("read it", "There are two: lease_2026_signed.pdf and lease_2026_draft.pdf.", ""),
        ("the lease one", "There are two: lease_2026_signed.pdf and lease_2026_draft.pdf.", "summarize the lease"),
        ("léemelo", "Listo, abrí Descargas.", ""),  # no file named
        ("qué dice", "", ""),  # nothing before
        ("léeme el último de descargas", "Abrí «acta_reunion.pdf».", ""),  # the newest one, in a folder
        ("read the other one", "Opened «quarterly_report.pdf».", ""),
        ("read report_2024.pdf", "Opened «quarterly_report.pdf».", ""),  # names its own file
        ("ábrelo y léemelo", "Abrí «acta_reunion.pdf».", ""),  # open and read at once stays the decider's
        ("the signed one", "There are two: lease_2026_signed.pdf and lease_2026_draft.pdf.", "find my lease"),
        ("la tercera", "Hay dos: «extracto_julio.pdf» y «extracto_agosto.pdf».", "resúmeme el extracto"),
        ("léemelos los dos", "Hay dos: «extracto_julio.pdf» y «extracto_agosto.pdf».", ""),
    ],
)
def test_no_file_is_meant_when_the_message_does_not_point_at_one(message: str, reply: str, before: str) -> None:
    assert named_file_meant(message, reply, before) is None


@pytest.mark.parametrize(
    ("said", "name", "folder"),
    [
        # DEV-I (not yet run) I-w22-t4: the file opened after a pick, in the folder the listing gave it.
        (["no era ese, era el pdf de la matricula",
          "Hay dos: matricula_2026.pdf en Descargas y matricula_firmada.pdf en Documentos. ¿Cuál abro?",
          "la firmada", "Listo, abrí matricula_firmada.pdf.", "resumemelo rapidito"],
         "matricula_firmada.pdf", "documents"),
        # DEV-I I-w33-t3.
        (["oye búscame el archivo informe_ventas_septiembre, no me acuerdo dónde lo dejé",
          "Encontré dos: informe_ventas_septiembre.xlsx en Documentos e informe_ventas_septiembre.pdf en Descargas.",
          "ya, abre el pdf", "Abrí informe_ventas_septiembre.pdf de Descargas.",
          "mejor resúmemelo, que me da lata leerlo entero"],
         "informe_ventas_septiembre.pdf", "downloads"),
    ],
)
def test_real_variants_read_the_file_just_opened_where_it_is(said: list[str], name: str, folder: str) -> None:
    meant = named_file_meant(said[-1], said[-2], said[-3])
    assert meant is not None and (meant.act, meant.name) == ("read", name)
    assert conversation_file_folder(name, said[:-1]) == folder


def test_the_extension_decides_the_reader() -> None:
    assert named_file_operation(NamedFileMeant("read", "a.pdf", "")) == "document.pdf.read"
    assert named_file_operation(NamedFileMeant("read", "notas.TXT", "")) == "document.text.read"
    assert named_file_operation(NamedFileMeant("read", "presupuesto.xlsx", "")) is None  # no reader of it here
    assert named_file_operation(NamedFileMeant("open", "presupuesto.xlsx", "")) == "file.open"


def test_a_reply_names_files_quoted_or_bare_but_not_web_addresses() -> None:
    assert files_named_in_reply("Abierto factura_luz_septiembre.pdf, el último de Descargas.") == (
        "factura_luz_septiembre.pdf",
    )
    assert files_named_in_reply("Hay dos: «a b.pdf» y «c.txt»; mira bbc.com y la versión 3.5.") == ("a b.pdf", "c.txt")


@pytest.mark.parametrize(
    ("name", "conversation", "folder"),
    [
        ("cotizacion_mudanza_v2.pdf", MOVING_OPENED, "documents"),
        ("cotizacion_mudanza.pdf", MOVING_OPENED, "downloads"),
        ("cv_spanish.pdf", ["There are two: «cv_english.pdf» in Documents and «cv_spanish.pdf» in Downloads."],
         "downloads"),
        ("invoice_sept_2026.pdf", INVOICE, "all_known"),
        ("otro.pdf", INVOICE, None),
    ],
)
def test_the_folder_is_the_one_said_with_that_file(name: str, conversation: list[str], folder: str | None) -> None:
    assert conversation_file_folder(name, conversation) == folder


def test_a_text_file_named_earlier_is_read_where_it_was_said() -> None:
    conversation = ["busca mis apuntes", "Encontré «apuntes_fisica.md» en Documentos."]
    assert conversation_text_file("léemelo («apuntes_fisica.md»)", conversation) == {
        "fileName": "apuntes_fisica.md", "folder": "documents",
    }
    assert conversation_pdf("léemelo («apuntes_fisica.md»)", conversation) is None


# ------------------------------------------------------------------ whole turns that change and that do not


def test_a_text_file_baxy_named_is_read_with_the_text_reader() -> None:
    said = ["busca mis apuntes de física", "Encontré «apuntes_fisica.md» en Documentos.", "léemelo porfa"]
    result = _turn(said, _decided("Abre los apuntes de física.", "file.open", folder="documents", name="apuntes"))
    assert result["effectOperations"] == ["document.text.read"]
    assert _arguments(said, "document.text.read", result["objective"]) == (
        {"fileName": "apuntes_fisica.md", "folder": "documents"}, "",
    )


def test_an_opening_picked_in_english_opens_that_file_where_it_is() -> None:
    said = ["find my resume", "There are two: «cv_english.pdf» in Documents and «cv_spanish.pdf» in Downloads.",
            "open the second one"]
    result = _turn(said, _decided("Open the latest file.", "filesystem.file.open.latest", folder="downloads"))
    assert result["effectOperations"] == ["file.open"]
    assert _arguments(said, "file.open", result["objective"]) == ({"folder": "downloads", "name": "cv_spanish.pdf"}, "")


@pytest.mark.parametrize(
    ("said", "decision"),
    [
        # «Ábrelo» stays opening.
        ([*COUNCIL, "open it"], _decided("Open council_tax_2026-27.pdf.", "file.open", folder="downloads",
                                         name="council_tax_2026-27.pdf")),
        # The same words with nothing before them.
        (["Yeah, that's the one, give us the gist of it"], _decided("Read the latest file.", "file.open")),
        (["qué dice"], _decided("¿Qué dice el archivo más reciente?", "filesystem.file.open.latest")),
        # Two files and none picked.
        ([*LEASE, "summarize it"], _decided("Summarize the lease.", "file.open", folder="downloads", name="lease")),
        # A pick after a search, with nothing asked of the file.
        ([*MOVING, "el segundo"], _decided("Busca cotizacion_mudanza_v2.", "filesystem.known.search",
                                            query="cotizacion_mudanza_v2")),
        # The decider read that very file: its decision stays.
        ([*MOVING_OPENED, "resumemelo en corto"],
         _decided("Resume cotizacion_mudanza_v2.pdf.", "document.pdf.read", fileName="cotizacion_mudanza_v2.pdf",
                  folder="documents")),
        # Another kind of decision is not touched.
        ([*INVOICE, "read it"], _decided("Read the latest email.", "email.latest.read")),
        # A file the reader does not read (an Excel sheet) is left to the decider.
        (["busca el presupuesto", "Encontré «presupuesto_2026.xlsx» en Documentos.", "qué dice"],
         _decided("Abre presupuesto_2026.xlsx.", "file.open", folder="documents", name="presupuesto_2026.xlsx")),
    ],
)
def test_turns_that_do_not_point_at_the_named_file_keep_the_decision(said: list[str], decision: ContextDecision) -> None:
    result = _turn(said, decision)
    assert result["effectOperations"] == list(decision.operations), result
    assert result["objective"] == decision.request
