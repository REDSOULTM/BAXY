"""Uso real v3 tanda 4 (t4-r6), secciones 2, 3 y la corrección de la 4 del diagnóstico.

- c02-1 «dame 3 libros de cortazar para arrancar» → «El Aleph» (Borges) and two titles that do not exist: the works or
  members of a named person or group are looked up (knowledge reference kind ``works``), never a kind of work, the
  person's own things or a folder named so.
- c01-3 «y ponme cumbia mientras» → Spotify looked for «cumbia mientras»: a nexus of simultaneity ends what to play also
  at the end of the message.
- c01-4 «no po, en spotify te dije, no en youtube» → YouTube; c04-2 «joder que te he dicho brillo no volumen» → talk
  about the sound output: a contrastive correction is about the last request, Y in it becomes X, and a request that
  already named X is done again; a decider's choice that names what the person refused is replaced.
- c04-2's wording retry is audited with the history it carries (the raw audit wrote «history_users: 0»).
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import llm
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import arguments, decider, dialogue, knowledge
from baxy_mind import context_decision


# ------------------------------------------------------------------ 2. works of a named person or group


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("Dame 3 libros de Julio Cortázar para empezar.", "libros de Julio Cortázar"),
        ("¿Qué películas de Christopher Nolan me recomiendas?", "películas de Christopher Nolan"),
        ("dime los integrantes de Soda Stereo", "integrantes de Soda Stereo"),
        ("pasame canciones de los Prisioneros", "canciones de los Prisioneros"),
        ("give me 3 books by Gabriel García Márquez", "books by Gabriel García Márquez"),
        ("what are some songs by The Beatles?", "songs by The Beatles"),
    ],
)
def test_the_works_of_a_named_person_or_group_are_looked_up(text: str, query: str) -> None:
    lookup = knowledge.reference_lookup(text)
    assert lookup is not None and lookup.kind == "works" and lookup.query == query


@pytest.mark.parametrize(
    "text",
    [
        "dame 3 libros de autoayuda",  # a kind of work
        "Dame 3 libros de Autoayuda",  # a kind, even capitalized
        "películas de terror para ver hoy",
        "Películas de Terror",
        "canciones de cuna",
        "libros de texto",
        "mis libros de Cálculo",  # the person's own things
        "abre la carpeta libros de Juan",  # a folder named so
        "dame 3 libros de cortazar para arrancar",  # no name written as one (the restatement is read too)
        "libros de Cortázar baratos en Amazon",  # more said of the works: the decider's
        "cuáles son los últimos discos de Soda Stereo",  # the newest (M56), not the works
        "dame los mejores libros de Julio Cortázar",  # an opinion
    ],
)
def test_no_named_person_or_group_no_works_lookup(text: str) -> None:
    lookup = knowledge.reference_lookup(text)
    assert lookup is None or lookup.kind != "works"


def test_the_talk_gate_reads_the_restatement_that_writes_the_name() -> None:
    # The person wrote «cortazar»; the decider's restatement writes it as a name, and the gate tries it first.
    said, restated = "dame 3 libros de cortazar para arrancar", "Dame 3 libros de Julio Cortázar para empezar."
    found = [knowledge.reference_lookup(candidate) for candidate in dict.fromkeys((restated, said))]
    assert found[0] is not None and found[0].kind == "works" and found[1] is None


# ------------------------------------------------------------------ 3a. simultaneity at the end of the message


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("y ponme cumbia mientras", "cumbia"),
        ("y ponme cumbia mientras.", "cumbia"),
        ("pon cumbia de mientras", "cumbia"),
        ("pon cumbia mientras tanto", "cumbia"),
        ("ponme cumbia mientras cocino", "cumbia"),
        ("play jazz meanwhile", "jazz"),
        ("pon jazz while", "jazz"),
    ],
)
def test_a_nexus_of_simultaneity_ends_what_to_play(text: str, query: str) -> None:
    assert arguments.music_named_in_message("media.play.query", text) == {"query": query}


def test_a_title_that_begins_with_the_nexus_keeps_it() -> None:
    assert arguments.music_named_in_message("media.play.query", "pon Mientras tanto de Los Bunkers") == {
        "query": "Mientras tanto de Los Bunkers"
    }


def test_the_decided_query_loses_the_clause_the_person_left_out() -> None:
    decided = {"provider": "spotify", "query": "cumbia mientras cocino"}
    assert arguments.as_the_person_named("media.play.query", decided, "ponme cumbia mientras cocino", [])["query"] == (
        "cumbia"
    )


def test_a_decided_query_whose_cut_loses_a_named_word_is_not_cut() -> None:
    decided = {"query": "Los Bunkers, El Detenido"}
    said = "pon el detenido de los bunkers"
    assert arguments.as_the_person_named("media.play.query", decided, said, [])["query"] != "Los Bunkers"


# ------------------------------------------------------------------ 3b/4. the contrastive correction


@pytest.mark.parametrize(
    ("text", "wanted", "refused"),
    [
        ("no po, en spotify te dije, no en youtube", "spotify", "youtube"),
        ("joder que te he dicho brillo no volumen", "brillo", "volumen"),
        ("no en spotify, en youtube", "youtube", "spotify"),
        ("no, el brillo, no el volumen", "brillo", "volumen"),
        ("I said spotify, not youtube", "spotify", "youtube"),
        ("not youtube, spotify", "spotify", "youtube"),
        ("no youtube sino spotify", "spotify", "youtube"),
    ],
)
def test_a_contrastive_correction_is_read(text: str, wanted: str, refused: str) -> None:
    contrast = dialogue.contrastive_correction(text)
    assert contrast is not None and (contrast.wanted, contrast.refused) == (wanted, refused)


@pytest.mark.parametrize(
    "text",
    [
        "no, en YouTube",  # a destination, no contrast
        "no quiero spotify",  # a prohibition without a replacement
        "spotify no anda",  # a sentence, no correction
        "no, a las 7, no a las 6",  # an hour: the hour reader's
        "no, mejor a las 6:15",
        "no, eso no",
        "ya no",
    ],
)
def test_counter_cases_of_the_contrast(text: str) -> None:
    assert dialogue.contrastive_correction(text) is None


@pytest.mark.parametrize(
    ("last", "text", "corrected"),
    [
        ("pon una cumbia en youtube", "no po, en spotify te dije, no en youtube", "pon una cumbia en spotify"),
        ("y ponme cumbia mientras", "no po, en spotify te dije, no en youtube", "ponme cumbia mientras en spotify"),
        ("pon el volumen al 40", "joder que te he dicho brillo no volumen", "pon el brillo al 40"),
        ("pon el brillo al 40", "joder que te he dicho brillo no volumen", "pon el brillo al 40"),
        # The value readers stay as they were.
        ("ponme una alarma a las 6 y media pa mañana", "no, mejor a las 6:15", "ponme una alarma a las 6:15 pa mañana"),
    ],
)
def test_the_contrast_corrects_the_last_request(last: str, text: str, corrected: str) -> None:
    assert dialogue.corrected_request(last, text) == corrected


def test_a_destination_alone_is_not_a_contrast_of_the_last_request() -> None:
    assert dialogue.corrected_request("ponme cumbia en spotify", "no, en YouTube") is None


OPERATIONS = (
    "audio.volume", "audio.volume.adjust", "audio.status", "media.play.query", "media.play.youtube", "media.status",
    "system.settings.set", "display.status", "web.search",
)


class _Decider:
    def __init__(self, request: str, decision: str, operations: tuple[str, ...] = ()) -> None:  # noqa: D107
        self.decided = decider.ContextDecision(request=request, decision=decision, operations=operations, question="")

    def decide_in_context(self, *_args: object, **_kwargs: object) -> decider.ContextDecision:
        return self.decided

    @staticmethod
    def clarify_after_turn_failure(*_args: object, **_kwargs: object) -> str:
        return "¿Qué quieres que haga?"


def _tool(operation: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "read_only",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }


def _decided(turns: list[tuple[str, str]], text: str, model: _Decider) -> dict[str, object]:
    history = [{"role": role, "content": content} for role, content in turns] + [{"role": "user", "content": text}]
    return context_decision._context_decided_result(
        {"id": "t4", "text": text, "history": history},
        llm=model,
        planner_catalog=PlannerCatalog([_tool(name) for name in OPERATIONS]),
    )


def test_a_decider_choice_of_the_refused_service_is_replaced() -> None:
    result = _decided(
        [("user", "y ponme cumbia mientras"), ("assistant", "No pude confirmar que sonara la cumbia en Spotify.")],
        "no po, en spotify te dije, no en youtube",
        _Decider("Pon una cumbia en YouTube.", "action", ("media.play.youtube",)),
    )
    assert result["intentOperations"] == ["media.play.query"]
    assert "spotify" in str(result["objective"]).lower() and "youtube" not in str(result["objective"]).lower()


def test_talk_after_a_contrast_with_the_last_request_does_it_again() -> None:
    result = _decided(
        [("user", "pon el brillo al 40"), ("assistant", "Brillo en 40 %.")],
        "joder que te he dicho brillo no volumen",
        _Decider("¿Por qué cambiaste el volumen?", "talk"),
    )
    assert result["intentOperations"] == ["system.settings.set"]
    assert str(result["objective"]) == "pon el brillo al 40"


def test_a_decider_choice_that_follows_the_contrast_stays() -> None:
    result = _decided(
        [("user", "y ponme cumbia mientras"), ("assistant", "No pude confirmar que sonara la cumbia.")],
        "no po, en spotify te dije, no en youtube",
        _Decider("Pon cumbia en Spotify.", "action", ("media.play.query",)),
    )
    assert result["intentOperations"] == ["media.play.query"]
    assert result["objective"] == "Pon cumbia en Spotify."


def test_a_destination_alone_leaves_the_decider() -> None:
    result = _decided(
        [("user", "ponme cumbia"), ("assistant", "Suena cumbia en Spotify.")],
        "no, en YouTube",
        _Decider("Pon cumbia en YouTube.", "action", ("media.play.youtube",)),
    )
    assert result["intentOperations"] == ["media.play.youtube"]


# ------------------------------------------------------------------ 4. the wording retry keeps the history


class _Recorder(llm.LlmRuntime):
    def __init__(self, replies: list[str]) -> None:  # noqa: D107
        self._gguf = "granite-4.2-3b-Q4_K_M.gguf"
        self.replies = iter(replies)
        self.payloads: list[dict] = []

    def _post(self, payload: dict) -> dict:
        self.payloads.append(payload)
        return {"choices": [{"message": {"content": next(self.replies)}, "finish_reason": "stop"}]}


def test_the_wording_retry_carries_the_history_and_its_audit_says_so(tmp_path, monkeypatch) -> None:
    audit = tmp_path / "raw.jsonl"
    monkeypatch.setenv("BAXY_MIND_RAW_REPLY_AUDIT_PATH", str(audit))
    history = [
        {"role": "user", "content": "Me llamo Ágata y guardé 17 notas."},
        {"role": "assistant", "content": "Anotado, Ágata."},
    ]
    text = "¿Cuántas notas te dije que guardé?"
    # The first draft repeats the person's message (an echo): the bounded retry writes it again.
    runtime = _Recorder([text, json.dumps({"answer": "Me dijiste que guardaste 17 notas."})])
    runtime.chat(text, history=history, conversation_kind="knowledge", response_language="es")
    assert len(runtime.payloads) == 2
    retry = runtime.payloads[1]["messages"]
    assert any("17 notas" in str(message.get("content")) for message in retry[:-1])
    rows = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
    assert [row["attempt"] for row in rows] == [1, 2]
    assert rows[1]["history_users"] == rows[0]["history_users"] == 1


@pytest.mark.parametrize(
    "text", ["no cierres chrome", "no pongas reggaeton", "no borres el archivo", "no apagues el wifi", "no, no cierres chrome"]
)
def test_a_prohibition_of_the_last_request_is_no_contrast(text: str) -> None:
    # Review of t4-r6: «no Y X» without a pause read «X instead of Y» with the verb as Y, and the request the person
    # forbade was repeated as its correction.
    assert dialogue.contrastive_correction(text) is None


class _TalkingDecider(_Decider):
    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, dict]:
        return "Vale, no lo pongo.", {}

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"


def test_talk_after_a_prohibition_does_not_repeat_the_forbidden_request() -> None:
    result = _decided(
        [("user", "pon reggaeton en spotify"), ("assistant", "¿Pongo reggaeton en Spotify?")],
        "no pongas reggaeton",
        _TalkingDecider("Vale, no lo pongo.", "talk"),
    )
    assert "media.play.query" not in (result.get("intentOperations") or [])
    assert result.get("reply") == "Vale, no lo pongo."


@pytest.mark.parametrize(
    "text",
    [
        "me encantan las canciones de Queen",
        "¿Qué opinas de las películas de Nolan?",
        "Escribe un poema como los poemas de Neruda",
        "ya vi todas las películas de Christopher Nolan",
        "Pon canciones de Bad Bunny",
        "Quiero escuchar canciones de Queen",
    ],
)
def test_a_statement_or_another_task_about_the_works_is_no_works_lookup(text: str) -> None:
    # Review of t4-r6: the talk gate turned an opinion or a creative request about someone's works into a web search.
    lookup = knowledge.reference_lookup(text)
    assert lookup is None or lookup.kind != "works"


@pytest.mark.parametrize(
    "text",
    [
        "¿Cuáles son los integrantes de Soda Stereo?",
        "oye, ¿me puedes recomendar algunas películas de Christopher Nolan?",
        "any songs by The Beatles?",
        "Libros de Julio Cortázar",
    ],
)
def test_a_question_for_the_works_in_other_forms_is_looked_up(text: str) -> None:
    lookup = knowledge.reference_lookup(text)
    assert lookup is not None and lookup.kind == "works"


def test_a_decided_artist_after_a_comma_said_earlier_is_kept() -> None:
    # Review of t4-r6: the clause cut also split on the comma, and dropped the artist the person had said before.
    decided = {"query": "Bohemian Rhapsody, Queen"}
    earlier = ["me encanta queen"]
    result = arguments.as_the_person_named("media.play.query", decided, "pon bohemian rhapsody", earlier, earlier)
    assert result["query"] == "Bohemian Rhapsody, Queen"
