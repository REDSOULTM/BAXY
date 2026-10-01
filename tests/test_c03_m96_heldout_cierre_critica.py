"""M96: the two held-out turns that kept the owner's held-out at 28/30, oscillating (conv-v3j…conv-v3v).

- t11 «cerralo» right after «abrí el bloc de notas»: in five of seven runs the contextual decider answered
  «clarify» («¿Quieres que cierre el Bloc de notas?»), so t12 «sí, dale» only reached the App's confirmation and
  app.close never ran; in conv-v3v it restated «Cerrá el Bloc de notas.» and the pair passed. The pronoun's referent
  is the application the person just asked to open; it is read, not left to the model. Never the window in front
  (2026-09-22: «cerralo» read as the active window closed VS Code). With two opened, which one is asked.
- t14 «averiguá qué dijo la crítica» after «anoche vi Oppenheimer y me gustó bastante»: conv-v3v's decider restated
  «¿Qué dijo la crítica de Oppenheimer?»; the opinion reader read «Oppenheimer opiniones», the literal check dropped
  it for «opiniones», and the App published «¿Qué crítica específica querés que averigüé?» (no search, no film).

The phrasings below are this file's own; the decider is scripted so what is under test is the deterministic step.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.apps import bare_close_pronoun, close_request_for_opened
from baxy_mind.semantic.arguments import closes_the_active_window
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.grammar import _fold

OPERATIONS = ("app.open", "app.close", "window.resolve", "window.active", "web.search", "audio.volume.adjust")
APPLICATIONS = ("Bloc de notas", "Notepad", "Calculadora", "Calculator", "Spotify", "Discord", "Visual Studio Code")


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


class _Decider:
    """The decider as conv-v3q answered t11: a question about the application just opened."""

    def __init__(self, decision: ContextDecision | None = None) -> None:
        self.decision = decision or ContextDecision("cerralo", "clarify", (), "¿Quieres que cierre el Bloc de notas?")
        self.decided = 0
        self.clarified = 0

    def decide_in_context(self, *_args: object, **_kwargs: object) -> ContextDecision:
        self.decided += 1
        return self.decision

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        self.clarified += 1
        return "¿Cuál querés que cierre, Spotify o Discord?"

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        return "Algo.", []

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"


def _turn(text: str, history: list[tuple[str, str]], decider: _Decider) -> dict[str, object]:
    tools = [_tool(name) for name in OPERATIONS]
    turns = [{"role": role, "content": content} for role, content in history]
    return sidecar._context_decided_result(
        {"id": "m96", "text": text, "history": [*turns, {"role": "user", "content": text}]},
        llm=decider,
        planner_catalog=PlannerCatalog(tools),
        application_names=APPLICATIONS,
    )


def _opened(request: str, reply: str = "Listo, está abierto.") -> list[tuple[str, str]]:
    return [("user", "¿qué hora es?"), ("assistant", "Son las 17:05."), ("user", request), ("assistant", reply)]


@pytest.mark.parametrize(
    ("said", "asked", "objective"),
    [
        # conv-v3q t10–t11, as the App sent them.
        ("cerralo", "abrí el bloc de notas", "Cierra el bloc de notas"),
        ("ciérralo", "abre la calculadora", "Cierra la calculadora"),
        ("ciérrala", "abrime la calculadora porfa", "Cierra la calculadora"),
        ("ciérrelo", "abrí spotify", "Cierra spotify"),
        ("ya, cerralo", "abrí el bloc de notas", "Cierra el bloc de notas"),
        ("bueno ahora ciérralo porfa", "abrí discord", "Cierra discord"),
        ("¿lo cierras?", "abre la calculadora", "Cierra la calculadora"),
        ("close it", "open notepad", "Close notepad"),
        ("ok close that", "open the calculator please", "Close the calculator"),
        ("can you close it please?", "open spotify", "Close spotify"),
    ],
)
def test_the_pronoun_closes_the_application_just_opened_by_its_name(said: str, asked: str, objective: str) -> None:
    decider = _Decider()

    result = _turn(said, _opened(asked), decider)

    assert decider.decided == 0  # read, never left to the model
    assert result["kind"] == "action"
    assert result["operation"] == "app.close"
    assert result["objective"] == objective
    # The close goes through window.resolve by name; never the window in front.
    assert not closes_the_active_window(str(result["objective"]))
    first, _ = sidecar._expand_effect_plan(("app.close",), (str(result["objective"]),))
    assert first[0] == "window.resolve"


def test_the_composed_answer_to_the_open_does_not_change_the_referent() -> None:
    # conv-v3q t10 answered «Abrí el Bloc de notas mientras ya estaba en ejecución.» and the decider asked again.
    history = _opened("abrí el bloc de notas", "Abrí el Bloc de notas mientras ya estaba en ejecución.")

    result = _turn("cerralo", history, _Decider())

    assert (result["kind"], result["operation"]) == ("action", "app.close")


def test_thanks_between_the_open_and_the_pronoun_keeps_the_referent() -> None:
    history = [*_opened("open notepad"), ("user", "thanks"), ("assistant", "You're welcome.")]

    result = _turn("now close it", history, _Decider())

    assert (result["kind"], result["operation"], result["objective"]) == ("action", "app.close", "Close notepad")


@pytest.mark.parametrize(("said", "asked"), [("cerralo", "abrí spotify y discord"), ("close it", "open spotify and discord")])
def test_two_applications_opened_asks_which(said: str, asked: str) -> None:
    decider = _Decider(ContextDecision("Cierra Spotify.", "action", ("app.close",), ""))

    result = _turn(said, _opened(asked), decider)

    assert decider.decided == 0
    assert result["kind"] == "clarify"
    assert result["operation"] is None
    assert decider.clarified == 1  # the question is the model's, never a fixed reply


@pytest.mark.parametrize(
    ("said", "asked"),
    [
        ("cerralo", "subí el volumen"),  # nothing was opened: the decider reads it as before
        ("cerrá esta ventana", "abrí el bloc de notas"),  # the window in front, named: not a pronoun
        ("cierra Discord", "abrí el bloc de notas"),  # a named application is no pronoun either
    ],
)
def test_other_close_turns_stay_with_the_decider(said: str, asked: str) -> None:
    decider = _Decider(ContextDecision(said, "talk", (), ""))

    _turn(said, _opened(asked), decider)

    assert decider.decided == 1


@pytest.mark.parametrize(
    ("said", "english"),
    [
        ("cerralo", False), ("ciérralo", False), ("ciérrala", False), ("ciérrelo", False), ("ya, cerralo", False),
        ("cerrá eso", False), ("y cerralo ya", False), ("¿podés cerrarlo?", False),
        ("close it", True), ("ok close that", True), ("please close this one", True), ("shut it down", True),
    ],
)
def test_bare_close_pronouns(said: str, english: bool) -> None:
    assert bare_close_pronoun(_fold(said)) == (True, english)


@pytest.mark.parametrize(
    "said",
    ["cerrá la ventana activa", "close the active window", "cierra esta ventana", "cierra Discord", "close notepad",
     "no lo cierres", "ciérralos", "close them", "cerralo y abrí spotify"],
)
def test_not_bare_close_pronouns(said: str) -> None:
    assert bare_close_pronoun(_fold(said)) == (False, False)


def test_the_close_keeps_the_application_words_and_drops_the_open_verb() -> None:
    assert close_request_for_opened("abre la calculadora", english=False) == "Cierra la calculadora"
    assert close_request_for_opened("bloc de notas", english=False) == "Cierra bloc de notas"
    assert close_request_for_opened("open the calculator please", english=True) == "Close the calculator"
    assert close_request_for_opened("abrime spotify", english=False) == "Cierra spotify"


# ------------------------------------------------------------------ t14: the critique of a film named before

WEB_SEARCH = {
    "type": "object",
    "properties": {
        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
        "nearby": {"type": ["boolean", "null"]},
        "query": {"type": "string", "x-maxUtf8Bytes": 2000, "x-nonWhitespace": True},
    },
    "required": ["query"],
    "additionalProperties": False,
}
FILM_HISTORY = [
    {"role": "user", "content": "anoche vi Oppenheimer y me gustó bastante"},
    {"role": "assistant", "content": "Es una película impactante. ¿Te gustó más el final o la trama?"},
    {"role": "user", "content": "averiguá qué dijo la crítica"},
]


@pytest.mark.parametrize(
    ("objective", "query"),
    [
        # conv-v3v t14's restatement.
        ("¿Qué dijo la crítica de Oppenheimer?", "Oppenheimer opiniones"),
        ("¿qué opinan los críticos de Dune 2?", "Dune 2 opiniones"),
        ("reseñas de la serie Severance", "serie Severance opiniones"),
        ("What do critics say about Oppenheimer?", "Oppenheimer reviews"),
    ],
)
def test_an_opinion_of_a_named_work_is_looked_up_with_the_works_name(objective: str, query: str) -> None:
    arguments = sidecar._ground_explicit_arguments("web.search", objective, WEB_SEARCH, history=FILM_HISTORY)

    assert arguments == {"query": query}


def test_a_search_said_as_an_order_keeps_the_persons_question() -> None:
    # conv-v3j…v3s: «Buscá qué dijo la crítica sobre Oppenheimer.» was already read in the person's words.
    arguments = sidecar._ground_explicit_arguments(
        "web.search", "Buscá qué dijo la crítica sobre Oppenheimer.", WEB_SEARCH, history=FILM_HISTORY,
    )

    assert arguments == {"query": "qué dijo la crítica sobre Oppenheimer"}
