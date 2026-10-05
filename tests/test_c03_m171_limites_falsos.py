"""M171 (2026-10-05, App runs v5a/v5b): «Eso no lo hago» to an order the catalog does.

The contextual decider (and the isolated one) decided «limit» on orders the catalog serves; the code corrects it when a
reader proves the order (the pattern of M123/M131/M138; an exception to D58 because the decider is wrong):

* H-s074 «baxy ponle bluey en disney plus a la sofi» (decider «Pon Bluey en Disney+ para Sofía.», limit). The streaming
  reader knew «pon/ponme/pone» and not «ponle»: the clitic of who it is put for hid the order. Who it is for after the
  service («a la sofi», «para los niños», «pa mi hija», «for my kid», «so the kids can watch») was already left out of
  the title; said before the service with the clitic («ponle bluey a la sofi en disney plus») it is now too.
* I-w03-t2 «ugh ok, then al menos ponme el night light en el notebook pa no quemarme los ojos» after a limit about the
  living-room lights (decider «Activa la luz nocturna en el notebook.», limit). The readers prove system.settings.set
  (night_light) in the message, but its openers keep it from reading as a complete request, so the limit's re-read
  (M78, ``_served_surface_reread``) never tried it. It is now re-read as said when the decider's own restatement reads
  as that same order.

Limits that stay: G-w03-t3 «no, la temporada 2, el primer episodio» (streaming.play.named takes a service and a title,
and the provider plays the series where Netflix resumes it: no season or episode is chosen, so the limit is true);
D-p19-t1 «…After the Wedding with Spanish subtitles on.» (no service is named, so no reader proves an order; choosing
subtitles is no operation); an Uber, the lights of the house, food ordered; and a message whose restatement reads as
another operation.

Every phrasing beyond the rows is our own; nothing here depends on the clock.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import reading
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState
from test_c03_m148_avisos_eso_y_cuentas import OPERATIONS, _Decider, _history, _tool

S074 = "baxy ponle bluey en disney plus a la sofi"
W03_I = [
    "turn off las luces del living",
    "Eso no lo hago: apagar las luces del living.",
    "ugh ok, then al menos ponme el night light en el notebook pa no quemarme los ojos",
]
W03_G = [
    "oye, pide un uber pa las 8 to the airport",
    "Eso no lo hago: pedir un Uber para ir al aeropuerto.",
    "ok ok, entonces pon Stranger Things en Netflix",
    "No se pudo poner Stranger Things en Netflix porque la plataforma pide iniciar sesión en este PC.",
    "no, la temporada 2, el primer episodio",
]


def _limit(restated: str) -> ContextDecision:
    return ContextDecision(restated, "limit", (), "")


def _turn(said: list[str], decision: ContextDecision) -> dict:
    """``said``: the conversation, user first and alternating, ending in the person's message."""

    tools = {name: _tool(name) for name in OPERATIONS}
    return sidecar._prepare_turn_result(
        {"id": "m171", "text": said[-1], "history": _history(said)},
        llm=_Decider(decision), planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (),
        tool_by_name=tools, dialogue_state=DialogueState(),
    )


def _effects(text: str) -> tuple[str, ...] | None:
    effects = reading.read(text, available_operations=OPERATIONS).effects
    return None if effects is None else tuple(effects.operations)


STREAMING = {"type": "object", "properties": {
    "service": {"type": "string", "enum": ["disney_plus", "netflix"]},
    "title": {"type": "string", "x-maxUtf8Bytes": 512, "x-nonWhitespace": True}},
    "required": ["service", "title"], "additionalProperties": False}


def _is_limit(result: dict) -> bool:
    return result["kind"] == "conversation" and result.get("conversationKind") == "unsupported"


# ------------------------------------------------------------------ H-s074: «ponle» is «pon»


@pytest.mark.parametrize(
    ("text", "service", "title"),
    [
        (S074, "disney_plus", "bluey"),
        ("ponle bluey a la sofi en disney plus", "disney_plus", "bluey"),
        ("ponles Bluey en Disney Plus a los niños", "disney_plus", "Bluey"),
        ("ponles Bluey a los niños en Netflix", "netflix", "Bluey"),
        ("poneles Bluey en Netflix a los chicos", "netflix", "Bluey"),
        # Who it is for after the service was already no part of the title, and stays so.
        ("pon bluey en disney plus pa mi hija", "disney_plus", "bluey"),
        ("pon Bluey en Disney Plus para los niños", "disney_plus", "Bluey"),
        ("put Bluey on Disney Plus for my kid", "disney_plus", "Bluey"),
        ("put on Bluey on Disney Plus so the kids can watch", "disney_plus", "Bluey"),
    ],
)
def test_a_title_put_on_for_someone_is_that_title(text: str, service: str, title: str) -> None:
    assert _effects(text) == ("streaming.play.named",)
    assert sidecar._ground_explicit_arguments("streaming.play.named", text, STREAMING) == {"service": service,
                                                                                             "title": title}


def test_h_s074_the_decider_limit_is_the_order() -> None:
    result = _turn([S074], _limit("Pon Bluey en Disney+ para Sofía."))
    assert result["kind"] == "action" and result["operation"] == "streaming.play.named"


@pytest.mark.parametrize(
    ("text", "title"),
    [
        # With no clitic, «a la…» inside a title is the title's own; «al» is never who it is for.
        ("pon Bienvenidos a la casa en Netflix", "Bienvenidos a la casa"),
        ("ponle Regreso al futuro en Netflix", "Regreso al futuro"),
        ("ponle Bluey en Netflix", "Bluey"),
    ],
)
def test_a_title_that_says_a_place_keeps_it(text: str, title: str) -> None:
    assert sidecar._explicit_arguments_from_evidence("streaming.play.named", text)["title"] == title


@pytest.mark.parametrize("text", ["ponle hola", "ponle más volumen", "ponle un recordatorio a las 5"])
def test_ponle_without_a_service_is_no_streaming(text: str) -> None:
    assert _effects(text) != ("streaming.play.named",)


# ------------------------------------------------------------------ I-w03-t2: the restatement reads as the same order


@pytest.mark.parametrize(
    ("said", "restated"),
    [
        (W03_I, "Activa la luz nocturna en el notebook."),
        (["turn off the lights in the living room", "I don't control the lights of your home, only this PC.",
          "ugh fine, then at least turn on the night light on the laptop so my eyes don't burn"],
         "Turn on the night light on the laptop."),
        (["apaga la luz de la cocina", "Eso no lo hago: apagar la luz de la cocina.",
          "bueno ya, entonces al menos actívame la luz nocturna pa no cansar la vista"],
         "Activa la luz nocturna."),
    ],
)
def test_an_order_the_restatement_also_reads_is_done(said: list[str], restated: str) -> None:
    assert _effects(said[-1]) == ("system.settings.set",) == _effects(restated)
    result = _turn(said, _limit(restated))
    assert result["kind"] == "action" and result["operation"] == "system.settings.set"
    assert result["objective"] == said[-1]


def test_the_night_light_is_switched_on() -> None:
    assert sidecar._explicit_arguments_from_evidence("system.settings.set", W03_I[-1]) == {
        "setting": "night_light", "value": 1}


# ------------------------------------------------------------------ limits that stay


@pytest.mark.parametrize(
    ("said", "restated"),
    [
        # G-w03-t3: no season or episode is chosen by streaming.play.named; the message leans on the conversation.
        (W03_G, "Pon la temporada 2 del primer episodio de Stranger Things en Netflix."),
        # D-p19-t1: no service named, and subtitles are chosen by no operation.
        (["I'd like to watch a movie called After the Wedding with Spanish subtitles on."],
         "Play the movie After the Wedding with Spanish subtitles."),
        # The restatement reads as another order than the message: the decider meant something else.
        (W03_I, "Pon música relajante."),
        # The lights of the house, an Uber, food: no reader proves them.
        (["turn off the lights in the living room", "I don't control the lights of your home.",
          "ok then at least dim the lights in the kitchen"], "Dim the kitchen lights."),
        (["oye, pide un uber pa las 8 to the airport"], "Pide un Uber al aeropuerto a las 8."),
        (["baxy pídeme una pizza grande de pepperoni"], "Pide una pizza grande de pepperoni."),
    ],
)
def test_a_true_limit_stays_a_limit(said: list[str], restated: str) -> None:
    assert _is_limit(_turn(said, _limit(restated)))
