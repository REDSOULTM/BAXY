"""Ronda 19 (revisión, MUSIC1675, CLOSE1371): a request conditioned on an application being open now.

«si tengo word abierto, ponelo a la izquierda» plans window.resolve + window.snap; the window read is the check, so
no window means the condition is false. The mind marks the plan (``presentStateCondition``) and the shell never opens
the absent application to satisfy it (src/Baxy.App/PlannerExecutionSupport.cs, OpenBeforeResolvingAgain). Without the
condition («pone word a la izquierda») nothing is marked and an installed application with no window is opened.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind.planner import PlanProposal
from baxy_mind.semantic.apps import present_state_condition
from baxy_mind import plan_shape


CONDITIONED = (
    # español: inicial y final
    "si tengo word abierto, ponelo a la izquierda",
    "Si tengo el Word abierto ponelo a la izquierda",
    "pone word a la izquierda si esta abierto",
    "si el edge está abierto movelo a la derecha",
    "si hay spotify corriendo achicalo",
    "Hola BAXY, si tengo el chrome abierto ponelo a la derecha",
    # English: initial and final
    "If Chrome is open, snap it to the right",
    "snap chrome to the right if it's open",
    "move word to the left if it is running please",
    # spanglish
    "si tengo chrome open, snap it to the left",
    "pone el edge a la derecha if it's open",
    "if word is abierto ponelo a la izquierda",
    # Revisión 2: an order not to open it is the same check (es / en / spanglish).
    "pone word a la izquierda pero no lo abras si está cerrado",
    "snap word left but don't open it if it's closed",
    "pon word a la izquierda sin abrirlo",
    "put word on the left, don't open it",
    "snap word left, do not open it",
    "move chrome right without opening it",
    "no abras word, solo ponelo a la izquierda",
    "pon word a la izquierda, don't open it",
    # Revisión 2: other leads, the condition in the middle, and «'s open».
    "only if chrome is open, put it on the right",
    "pon word a la izquierda en caso de que esté abierto",
    "en caso de tener abierto el word ponelo a la izquierda",
    "pon el word a la izquierda, siempre que esté abierto",
    "mové el word a la derecha siempre y cuando esté abierto",
    "snap word left as long as it's open",
    "if word's open, snap it left",
    "if word’s open, snap it left",
    "pon word a la izquierda si está abierto, y chrome a la derecha",
    "pon word a la izquierda si está abierto y si no no hagas nada",
    "snap word left only if it's open",
    # Revisión 3 (B1): the state said the other way round, the person abstaining when it fails (es / en / spanglish).
    "pon word a la izquierda, pero si no está abierto no hagas nada",
    "pon word a la izquierda, si está cerrado no hagas nada",
    "pon chrome a la derecha, si no está abierto olvidalo",
    "pon chrome a la derecha; si no lo tengo abierto, dejalo",
    "pon word a la izquierda y si no está, nada",
    "si word está cerrado dejalo, si no ponelo a la izquierda",
    "snap word left, if it's not open never mind",
    "snap word left; if it's not running, skip it",
    "snap word left, but if it isn't open leave it",
    "snap chrome right but leave it closed if it's closed",
    "if word is closed don't do anything, otherwise snap it left",
    "snap word left unless it is closed",
    "pon word a la izquierda a menos que esté cerrado",
    "pon word a la izquierda salvo que esté cerrado",
    "pon word a la izquierda, if it's not open forget it",
    # Revisión 3 (B2): presence without a word of state.
    "si hay una ventana de word, ponela a la izquierda",
    "if there's a word window, snap it left",
    "si existe la ventana de chrome, ponela a la derecha",
    "snap word left if it's there",
    "snap word left if you find it",
    "acomodá el word a la izquierda si lo encontrás",
    "pon el word a la izquierda solo si lo tengo",
    "si ya tengo el chrome, mandalo a la derecha",
    "si todavía tengo el chrome, movelo a la derecha",
    "if word is up, snap it left",
    "if chrome is still up move it right",
    "si el word está en pantalla, movelo a la derecha",
    "if word is on screen, ponelo a la izquierda",
    # Revisión 3: an opening of another thing is not the consequence of the condition failing.
    "si está abierto el word ponelo a la izquierda y abrí chrome",
    "if word is open snap it left and open chrome",
)

NOT_CONDITIONED = (
    "pone word a la izquierda",
    "pon el Word y el Edge uno al lado del otro",
    "snap chrome to the right",
    "abri word y ponelo a la izquierda",
    "si podes, pone word a la izquierda",
    "dejalo abierto",
    # A negated state is not the condition that it is open.
    "si word no esta abierto, abrilo y ponelo a la izquierda",
    "snap chrome to the right if it isn't open",
    "pone el word a la izquierda si no esta abierto el chrome",
    # Revisión 2: a closed state, an order to open, or «open» as the order are not that condition.
    "si esta cerrado abrilo y ponelo a la izquierda",
    "if word is closed, open it and snap it left",
    "if you don't have word open, open it and put it left",
    "si no tengo word abierto abrilo y ponelo a la izquierda",
    "if you can open it, snap word left",
    "open word and snap it left",
    "abrí el word y ponelo a la izquierda si podés",
    "pon word a la izquierda y abrí chrome",
    "put word on the left, open it first if needed",
    "abrilo si hace falta y ponelo a la izquierda",
    # Revisión 3: the condition's consequence is the opening, so the absent application may be opened (contracasos).
    "pon word a la izquierda, si no está abierto, abrilo",
    "pon word a la izquierda; si no está abierto, ábrelo",
    "snap word left, if it's not open, open it",
    "if there's no word window, open one and snap it left",
    "si no hay una ventana de word, abrila y ponela a la izquierda",
    "si no lo encontrás, abrilo y ponelo a la izquierda",
    "if you can't find it, launch it and snap word left",
    "si word está cerrado, prendelo y ponelo a la izquierda",
    "si está cerrado hay que abrirlo, y ponelo a la izquierda",
    "snap word left, and if it's closed start it first",
    "si tengo word abierto ponelo a la izquierda, si no abrilo",
    "if chrome isn't running, open it, then snap it right",
)

# Revisión 2 (B1): requests the planner may answer with a question or a conversation; their text reads the condition,
# but only a plan carries the mark, so the shell keeps the question instead of failing the turn.
CONDITIONED_QUESTIONS = (
    "si tengo el chrome abierto, movelo",
    "if spotify is running, play something",
    "si tengo discord abierto mandale un mensaje",
)


@pytest.mark.parametrize("text", CONDITIONED)
def test_a_present_state_condition_is_read(text: str) -> None:
    assert present_state_condition(text)


@pytest.mark.parametrize("text", NOT_CONDITIONED)
def test_a_request_without_that_condition_is_not_marked(text: str) -> None:
    assert not present_state_condition(text)


@pytest.mark.parametrize("text", CONDITIONED)
def test_the_plan_result_carries_the_mark(text: str) -> None:
    assert plan_shape._plan_condition_marks("plan", [{"role": "user", "content": text}], text) == {
        "presentStateCondition": True
    }
    # The person's own message decides it even when the objective was rewritten without the condition.
    assert plan_shape._plan_condition_marks("plan", [{"role": "user", "content": text}], "pone word a la izquierda") == {
        "presentStateCondition": True
    }


@pytest.mark.parametrize("text", NOT_CONDITIONED)
def test_an_unconditioned_plan_result_carries_nothing(text: str) -> None:
    assert plan_shape._plan_condition_marks("plan", [{"role": "user", "content": text}], text) == {}
    assert plan_shape._plan_condition_marks("plan", [], text) == {}


@pytest.mark.parametrize("text", CONDITIONED_QUESTIONS)
@pytest.mark.parametrize("kind", ("clarify", "conversation"))
def test_only_a_plan_result_carries_the_mark(text: str, kind: str) -> None:
    """B1: the reading fires on the text, yet a clarify or conversation plan.result goes out unmarked; the shell's
    MindSidecarClient.ParsePlanResult would otherwise turn the question into plan_incomplete (and ignores a stray mark
    outside a plan, tests/Baxy.Integration.Tests/R19AppCerradaSeAbreTests.cs)."""

    assert present_state_condition(text)
    history = [{"role": "user", "content": text}]
    question = PlanProposal(kind=kind, question="¿A dónde?" if kind == "clarify" else "", steps=())
    message = json.loads(json.dumps(plan_shape._plan_result_message("7", question, history, text)))
    assert "presentStateCondition" not in message
    assert message["kind"] == kind and message["type"] == "plan.result" and message["steps"] == []
    planned = PlanProposal(kind="plan", question="", steps=())
    assert plan_shape._plan_result_message("7", planned, history, text)["presentStateCondition"] is True
