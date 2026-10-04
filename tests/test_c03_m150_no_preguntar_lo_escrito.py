"""M150 (2026-10-03, D58, goal v3 «cero repreguntas de un dato dado»): before asking a value, what the decider wrote.

Measured (DEV-E sealed, aggregates only, v4s): of the turns decided right whose value BAXY asked, 3 were decided by a
reader — the decider was never read and the isolated one had the values — and 5 by the decider in context, whose
``argument_fields`` the arguments step dropped before asking.

1. The readers' path. A turn a reader decided asks the decider before it asks the person (the decision prepared beside
   the readers when it was already written, ``LlmRuntime._finished_decision``; else asked then), and only then: what
   the decider wrote for that operation completes the extraction's values with the guarantees of the decider's own
   path (grounded in what was said, never an identifier nor a moment of the decider's). Real texts of turns the readers
   decide: DEV-F F-s016 «could you put Andor on Disney plus for me», F-s013 «Crea una nota que se llame ideas boda
   Marta con esto: …» (the extraction abstaining, as the App's sometimes does).
2. The decider's path, App runs v4r (D, F, G, H): every decided-right turn with ``argument_fields`` that asked.
   - DEV-H H-w32-t2 «y de qué trata? resumímelo así nomás» (plan file.open + document.pdf.read, the decider's
     {"folder": "Descargas", "name": …}) → the summary's ``fileName`` asked: a field under another name, fixed (the one
     field whose last word is the decider's, «name» → «fileName», as «app» begins «appId»). DEV-F F-w19-t2 «…el PDF de
     la hipoteca… ¿Me lo resumes?» has the same shape.
   - Left asking, on purpose: G-w12-t2 (note.update's identity: no note's id is ever shown to the conversation, and the
     decider's «expectedRevision» 2 was a number nobody said), H-w30-t2 (task.update's identity after a plan, the
     decider's due an ISO moment), G-w22-t4 «Tuesday evening» (no hour said; the decider's own ISO moment is never
     taken), F-w55-t2 (values keyed by the operation that are moments: 1725228000 → 1725228300).
"""

from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm as llm_module
from baxy_mind.llm import LlmRuntime
from baxy_mind.semantic import dialogue as dialogue_slot
from baxy_mind.semantic.decider import ContextDecision

STREAMING = {"type": "object", "properties": {"service": {"type": "string", "enum": ["disney_plus", "netflix"]},
                                              "title": {"type": "string", "x-maxUtf8Bytes": 512}},
             "required": ["service", "title"], "additionalProperties": False}
NOTE_CREATE = {"type": "object", "properties": {"content": {"type": "string", "x-maxUtf8Bytes": 65536},
                                                "title": {"type": "string", "x-maxUtf8Bytes": 512}},
               "required": ["content", "title"], "additionalProperties": False}
FOLDERS = ["all_known", "desktop", "documents", "downloads"]
PDF_READ = {"type": "object", "properties": {"fileName": {"type": "string", "x-maxUtf8Bytes": 512},
                                             "folder": {"type": "string", "enum": FOLDERS},
                                             "maximumCharacters": {"type": "integer", "minimum": 200}},
            "required": ["fileName", "folder"], "additionalProperties": False}
FILE_OPEN = {"type": "object", "properties": {"folder": {"type": "string",
                                                         "enum": ["desktop", "documents", "downloads", "pictures"]},
                                              "name": {"type": "string", "x-maxUtf8Bytes": 200}},
             "required": ["folder", "name"], "additionalProperties": False}


def _tool(operation: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": f"Leaf {operation}.", "parameters": schema}}


TOOLS = {"streaming.play.named": _tool("streaming.play.named", STREAMING),
         "note.create": _tool("note.create", NOTE_CREATE), "document.pdf.read": _tool("document.pdf.read", PDF_READ),
         "file.open": _tool("file.open", FILE_OPEN)}
CATALOG = SimpleNamespace(decider_tools=tuple(
    SimpleNamespace(name=name, description=f"Leaf {name}.", schema=tool["function"]["parameters"])
    for name, tool in TOOLS.items()
))


@pytest.fixture(autouse=True)
def _fresh_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sidecar, "_DECIDED_ARGUMENTS", {})
    monkeypatch.setattr(sidecar, "_DECIDER_READ_REQUESTS", {})


class _Model:
    """The extraction abstains (as the App's sometimes does); the decider answers ``decided``."""

    def __init__(self, decided: ContextDecision | None = None, *, extracted: dict[str, Any] | None = None,
                 fails: bool = False) -> None:
        self.decided, self.extracted, self.fails = decided, extracted, fails
        self.calls: list[Any] = []

    def extract_direct_arguments(self, *_args: object, **_kwargs: object) -> object:
        self.calls.append("extract")
        return llm_module.DirectArgumentExtraction(
            arguments=self.extracted, evidence=(), fallback_question="" if self.extracted else "¿Cuál?",
        )

    def decide_in_context(self, text: str, history: object, tools: Any, *, signatures: Any = None) -> ContextDecision:
        self.calls.append(("decide", text, len(history) if isinstance(history, list) else None,
                           {name for name, _ in tools}, dict(signatures or {}).get("note.create")))
        if self.fails or self.decided is None:
            raise TimeoutError("se agotó el presupuesto del decisor")
        return self.decided

    def formulate_missing_argument_question(self, *_args: object, **_kwargs: object) -> str:
        self.calls.append("formulate")
        return "¿Qué falta?"


def _action(operation: str, arguments: dict[str, Any], request: str = "") -> ContextDecision:
    return ContextDecision(request=request, decision="action", operations=(operation,), question="",
                           arguments=tuple(arguments.items()))


def _arguments(said: str, operation: str, model: _Model, *, objective: str | None = None,
               catalog: Any = CATALOG) -> tuple[dict | None, str]:
    return sidecar._direct_arguments_result(
        {"operation": operation, "text": objective or said, "history": [{"role": "user", "content": said}]},
        llm=model, tool=TOOLS[operation], dialogue_state=dialogue_slot.DialogueState(), planner_catalog=catalog,
    )


# ------------------------------------------------------------------ 1. the readers' path


def test_f_s016_a_reader_decided_turn_reads_the_decider_before_asking() -> None:
    said = "could you put Andor on Disney plus for me"
    model = _Model(_action("streaming.play.named", {"service": "Disney+", "title": "Andor"}, "Play Andor on Disney+."))
    arguments, question = _arguments(said, "streaming.play.named", model)
    assert question == "" and arguments == {"service": "disney_plus", "title": "Andor"}
    # Asked once, with the person's own message and the decider's catalog, only after the extraction abstained.
    assert [call if isinstance(call, str) else call[0] for call in model.calls] == ["extract", "decide"]
    assert model.calls[1][1] == said and "streaming.play.named" in model.calls[1][3]


def test_f_s013_the_note_the_decider_wrote_is_made_not_asked() -> None:
    said = ("Crea una nota que se llame ideas boda Marta con esto: photocall con marco dorado, barra libre hasta las "
            "4 y autobús desde Alcalá para los invitados")
    model = _Model(_action("note.create", {
        "content": "Photocall con marco dorado, barra libre hasta las 4 y autobús desde Alcalá para los invitados.",
        "title": "Ideas boda Marta"}))
    arguments, question = _arguments(said, "note.create", model)
    assert question == ""
    assert arguments is not None and arguments["title"] == "Ideas boda Marta" and "photocall" in arguments["content"].lower()


@pytest.mark.parametrize(
    ("said", "operation", "decided", "expected"),
    [
        # Other words, other language.
        ("ponme The Mandalorian en Disney+ porfa", "streaming.play.named",
         {"service": "Disney+", "title": "The Mandalorian"}, {"service": "disney_plus", "title": "The Mandalorian"}),
        ("throw Wednesday on netflix for me", "streaming.play.named",
         {"service": "Netflix", "title": "Wednesday"}, {"service": "netflix", "title": "Wednesday"}),
        ("save a note called grocery ideas: eggs, oat milk and sourdough", "note.create",
         {"title": "grocery ideas", "content": "eggs, oat milk and sourdough"},
         {"title": "grocery ideas", "content": "eggs, oat milk and sourdough"}),
    ],
)
def test_variants_of_a_reader_decided_turn(said: str, operation: str, decided: dict[str, Any],
                                           expected: dict[str, Any]) -> None:
    arguments, question = _arguments(said, operation, _Model(_action(operation, decided)))
    assert question == "" and arguments == expected


def test_what_nobody_said_or_another_reading_is_still_asked() -> None:
    # A title the decider brought that nobody said grounds nothing: the person is asked.
    model = _Model(_action("note.create", {"title": "Compras", "content": "leche y pan"}))
    assert _arguments("créame una nota nueva porfa", "note.create", model) == (None, "¿Cuál?")
    assert [call if isinstance(call, str) else call[0] for call in model.calls] == ["extract", "decide"]
    # The decider read another operation: the turn stays the readers', and the question stands.
    model = _Model(_action("web.search", {"query": "Andor"}))
    assert _arguments("could you put Andor on Disney plus", "streaming.play.named", model) == (None, "¿Cuál?")
    # No decision (budget, transport): asked as before, and the decider is not asked again for the same request.
    model = _Model(fails=True)
    assert _arguments("guárdalo en una nota", "note.create", model) == (None, "¿Cuál?")
    assert _arguments("guárdalo en una nota", "note.create", model) == (None, "¿Cuál?")
    assert sum(1 for call in model.calls if call[0] == "decide") == 1


def test_a_turn_that_resolves_never_waits_for_the_decider() -> None:
    model = _Model(_action("streaming.play.named", {"service": "Disney+", "title": "Andor"}),
                   extracted={"service": "disney_plus", "title": "Andor"})
    assert _arguments("could you put Andor on Disney plus for me", "streaming.play.named", model) == (
        {"service": "disney_plus", "title": "Andor"}, "")
    assert model.calls == ["extract"]


def test_a_request_the_decider_already_read_is_not_asked_again() -> None:
    # The decider's own path remembered this request (with no values for it): asking it again would say the same.
    objective = "Guarda eso en una nota."
    sidecar._remember_decided_arguments(objective, ("note.create",), ())
    model = _Model(_action("note.create", {"title": "Boda", "content": "photocall"}))
    assert _arguments("guárdame eso en una nota", "note.create", model, objective=objective) == (None, "¿Cuál?")
    assert model.calls == ["extract"]
    # Without the decider's catalog (an older caller) nothing more is asked of the model.
    model = _Model(_action("note.create", {"title": "Boda", "content": "photocall"}))
    assert _arguments("anótalo en una nota porfa", "note.create", model, catalog=None) == (None, "¿Cuál?")
    assert model.calls == ["extract"]


def test_a_plan_step_takes_what_the_decider_wrote_before_it_is_asked() -> None:
    # The plan request (``kind == "plan"``) asks the decider the same way before raising its question.
    said = "pon Andor en Disney plus y anota en una nota que se llame series que ya la empecé"
    history = [{"role": "user", "content": said}]
    model = _Model(ContextDecision(request="", decision="action", operations=("streaming.play.named", "note.create"),
                                   question="", arguments=(("title", "series"), ("content", "ya la empecé"))))
    operations = ("streaming.play.named", "note.create")
    assert sidecar._decided_before_asking(model, said, history, CATALOG, operations) is True
    got = sidecar._plan_step_decided_arguments("note.create", operations, said, TOOLS["note.create"], history,
                                               after_extraction=True)
    assert got == {"title": "series", "content": "ya la empecé"}
    assert sidecar._decided_before_asking(model, said, history, CATALOG, operations) is False  # read once


# ------------------------------------------------------------------ 2. the decider's path: a field under another name


def _plan(said: str, objective: str, effects: tuple[str, ...], decided: dict[str, Any],
          history: list[dict[str, str]]) -> dict[str, Any]:
    sidecar._remember_decided_arguments(objective, effects, tuple(decided.items()))
    conversation = history + [{"role": "user", "content": said}]
    return {op: sidecar._plan_step_decided_arguments(op, effects, objective, TOOLS[op], conversation)
            for op in effects}


def test_h_w32_t2_the_decider_s_name_is_the_summary_s_file_name() -> None:
    history = [{"role": "user", "content": "che, abrime lo último que bajé"},
               {"role": "assistant", "content": "Abrí «programa_jornadas_ingenieria_uba.pdf», lo último en Descargas."}]
    got = _plan("y de qué trata? resumímelo así nomás", "Resumime el PDF más reciente de Descargas.",
                ("file.open", "document.pdf.read"),
                {"folder": "Descargas", "name": "programa_jornadas_ingenieria_uba.pdf", "maximumCharacters": 2000},
                history)
    assert got == {"file.open": {"folder": "downloads", "name": "programa_jornadas_ingenieria_uba.pdf"},
                   "document.pdf.read": {"folder": "downloads", "fileName": "programa_jornadas_ingenieria_uba.pdf"}}


@pytest.mark.parametrize(
    ("said", "objective", "reply", "name", "folder", "expected_folder"),
    [
        ("Ahí tiene que estar el PDF de la hipoteca que me mandó el banco ayer. ¿Me lo resumes?",
         "Lee el PDF de la hipoteca de Descargas y resúmelo.", "Abierta la carpeta Descargas.",
         "hipoteca.pdf", "Descargas", "downloads"),
        ("what's that one about? give me the short version", "Summarize the latest PDF in Documents.",
         "Opened «lease_2026_signed.pdf», the newest in Documents.", "lease_2026_signed.pdf", "Documents",
         "documents"),
    ],
)
def test_variants_of_a_name_under_another_field(said: str, objective: str, reply: str, name: str, folder: str,
                                                expected_folder: str) -> None:
    history = [{"role": "user", "content": "abre la carpeta"}, {"role": "assistant", "content": reply}]
    got = _plan(said, objective, ("file.open", "document.pdf.read"), {"folder": folder, "name": name}, history)
    assert got["document.pdf.read"] == {"folder": expected_folder, "fileName": name}


def test_the_field_names_that_do_not_change() -> None:
    properties = {"fileName": {}, "folder": {}, "displayName": {}, "appId": {}}
    # Two fields end the same way: the decider's value cannot say which one is meant.
    assert sidecar._schema_field_of("name", "x.op", properties, []) is None
    # A prefix keeps reading first («app» → «appId»), a field of that name is itself, a short name maps nothing.
    assert sidecar._schema_field_of("app", "x.op", properties, []) == "appId"
    assert sidecar._schema_field_of("folder", "x.op", properties, []) == "folder"
    assert sidecar._schema_field_of("id", "x.op", {"noteId": {}}, []) is None
    # Only the last word of a camel-cased name («Name»), never a word inside another («rename»).
    assert sidecar._schema_field_of("name", "x.op", {"rename": {}}, []) is None
    # A name nobody said still grounds nothing.
    got = _plan("resúmemelo", "Resume el PDF.", ("document.pdf.read",), {"folder": "Descargas", "name": "contrato.pdf"},
                [{"role": "assistant", "content": "Abrí la carpeta Descargas."}])
    assert got == {"document.pdf.read": None}


# ------------------------------------------------------------------ 3. the decision prepared beside the readers


def _reply(request: str) -> dict[str, Any]:
    content = json.dumps({"request": request, "decision": "action", "operations": ["app.open"], "question": "",
                          "arguments": {"appId": "Spotify"}})
    return {"choices": [{"message": {"content": content}}], "timings": {"prompt_n": 23, "predicted_n": 40}}


class _Runtime(LlmRuntime):
    """The runtime without a server: ``_post`` records each request the decider would send."""

    def __init__(self, *, gate: threading.Event | None = None) -> None:
        self._gguf = None
        self._parallel_turn_verification = True
        self.posts: list[dict[str, Any]] = []
        self.gate = gate

    def _post(self, payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        self.posts.append(payload)
        if self.gate is not None:
            self.gate.wait(5)
        return _reply(payload["messages"][-1]["content"])


DECIDER_TOOLS = (("app.open", "Abre una aplicación."), ("web.search", "Busca en la web."))
SIGNATURES = {"app.open": ("appId",), "web.search": ("query",)}


def _settled(runtime: _Runtime) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        prepared = runtime._prepared_decision
        if prepared is not None and prepared[2].done():
            return
        time.sleep(0.005)


def test_a_decision_written_while_the_readers_decided_is_read_by_the_next_request() -> None:
    runtime = _Runtime()
    history = [{"role": "user", "content": "abre spotify"}]
    runtime.begin_request(10.0)
    runtime.prepare_decision("abre spotify", history, DECIDER_TOOLS, signatures=SIGNATURES)
    _settled(runtime)
    runtime.end_request()  # the readers decided the turn
    # The arguments request asks the same payload: no second decode.
    runtime.begin_request(10.0)
    decided = runtime.decide_in_context("abre spotify", history, DECIDER_TOOLS, signatures=SIGNATURES)
    runtime.end_request()
    assert decided.arguments == (("appId", "Spotify"),) and len(runtime.posts) == 1
    # Read once: the same payload asked again is decoded again.
    runtime.begin_request(10.0)
    runtime.decide_in_context("abre spotify", history, DECIDER_TOOLS, signatures=SIGNATURES)
    runtime.end_request()
    assert len(runtime.posts) == 2


def test_a_kept_decision_is_never_another_turn_s() -> None:
    runtime = _Runtime()
    runtime.begin_request(10.0)
    runtime.prepare_decision("abre spotify", [], DECIDER_TOOLS, signatures=SIGNATURES)
    _settled(runtime)
    runtime.end_request()
    runtime.begin_request(10.0)
    runtime.decide_in_context("busca el clima", [], DECIDER_TOOLS, signatures=SIGNATURES)
    runtime.end_request()
    assert [payload["messages"][-1]["content"] for payload in runtime.posts] == ["abre spotify", "busca el clima"]
    # The next turn's preparation drops whatever was kept.
    runtime.begin_request(10.0)
    runtime.prepare_decision("abre spotify", [], DECIDER_TOOLS, signatures=SIGNATURES)
    _settled(runtime)
    runtime.end_request()
    assert runtime._finished_decision is not None
    runtime.begin_request(10.0)
    runtime.prepare_decision("abre discord", [], DECIDER_TOOLS, signatures=SIGNATURES)
    assert runtime._finished_decision is None
    _settled(runtime)
    runtime.end_request()


def test_a_decision_still_being_written_is_cancelled_as_before() -> None:
    gate = threading.Event()
    runtime = _Runtime(gate=gate)
    runtime.begin_request(10.0)
    runtime.prepare_decision("abre spotify", [], DECIDER_TOOLS, signatures=SIGNATURES)
    deadline = time.monotonic() + 5
    while not runtime.posts and time.monotonic() < deadline:
        time.sleep(0.005)
    runtime.end_request()
    assert runtime._prepared_decision is None and getattr(runtime, "_finished_decision", None) is None
    gate.set()
