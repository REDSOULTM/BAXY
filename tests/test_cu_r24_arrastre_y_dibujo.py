"""Ronda 24 (pasada r23: t-drag-4, t-long-3, t-drag-3, t-drag-1), reescrito en la estabilización L.

La ronda 24 hizo posible dibujar con el puntero real (el acto ``drag`` del modelo, el trazo de BAXY sobre el lienzo y
la puerta del done que pedía un arrastre hecho). El dueño declaró arrastrar y dibujar un límite desde el primer día
(2026-10-10): toda esa maquinaria se retiró (``input.pointer.drag`` ya no está en el catálogo) y el pedido de dibujar
un trazo es el límite del contrato de «sin operación» (``semantic.drag.asks_to_drag``). Los contracasos de entonces
siguen: un sustantivo, el nombre de un control, una palabra que sólo empieza igual o un dibujo que no es un trazo de una
figura no son el límite.
"""

from __future__ import annotations

import pytest

from baxy_mind import computer_use as cu
from baxy_mind import cu_validate
from baxy_mind import cu_step_prompt
from baxy_mind.semantic.drag import asks_to_drag
from baxy_mind.semantic.missions import mission_request
from baxy_mind.semantic.patterns import known_unsupported_effect_request

T_DRAG_4 = "en Paint draw una línea recta arrastrando el mouse de la izquierda a la derecha del lienzo"
T_LONG_3 = ("Open Paint, resize the canvas to 500 by 500 pixels, draw a red filled rectangle in the middle, save it as "
            "baxy-cuadro.png in Documents\\baxy-prueba-v3 and then close Paint")


@pytest.mark.parametrize(
    "said",
    [
        T_DRAG_4, T_LONG_3, "draw a red filled rectangle in the middle", "dibujá un círculo arriba a la derecha",
        "trazá una raya", "pintá un círculo rojo", "dibujá una línea y un círculo", "en Paint dibujá un círculo",
        "abrí Paint y dibujá una línea", "dibujá con el Pincel", "draw a line chart of the sales",
        "dibujá un círculo y llevalo arrastrando a la esquina de la pantalla",
    ],
)
def test_a_stroke_asked_as_an_act_is_the_known_limit_and_never_a_mission(said: str) -> None:
    assert asks_to_drag(said)
    assert known_unsupported_effect_request(said, ("mission.computer.use", "app.open"))
    assert mission_request(said, ("Paint",)) is None


NOT_ASKED = [
    "save this drawing as baxy-dibujo.png",  # t-file-3: a noun and a file name
    "ir a la pestaña dibujar",  # v3-09's sub-goal: the name of a tab
    "en onenote ve a la pestaña Dibujar y escoge el marcador amarillo",
    "en word andá a Dibujar",
    "go to the Draw tab",
    "buscar Dragon Ball",  # «dragon» only starts like «drag»
    "abrí el drawer de la izquierda",
    "trazá la ruta a Curicó",  # a route, not a stroke
    "draw a card",
    "dibujá un gato",  # no figure a stroke makes, no canvas: no stroke to refuse
    "sketch a house in the middle",
    "en el Bloc de notas escribí: hoy dibujé un gato",  # review of L, H2: dictated text
    "en Chrome buscá como dibujar un gato",
    "en YouTube buscá how to draw a horse",
    "abrí la carpeta Fotos",
    "elegir la herramienta lapiz",
]


@pytest.mark.parametrize("said", NOT_ASKED)
def test_contracase_nouns_names_look_alikes_and_written_text_are_no_drawing(said: str) -> None:
    assert not asks_to_drag(said)


def test_the_model_has_no_drag_act_nor_a_grammar_for_it() -> None:
    assert "drag" not in cu.ACTS
    assert "drag ::=" not in cu_step_prompt.STEP_GRAMMAR and "| drag |" not in cu_step_prompt.STEP_GRAMMAR
    assert '"act":"drag"' not in cu_step_prompt.STEP_PROMPT


def test_a_drag_the_model_still_names_is_no_step() -> None:
    view = {
        "window": {"title": "Sin título - Paint", "process": "mspaint", "hwnd": 5},
        "controls": [{"i": 1, "kind": "Pane", "name": "(pane)", "body": True}],
    }
    decision = cu_validate._checked_act({"act": "drag", "i": 1, "at": [0.9, 0.5]}, view=view, last_failed=None,
                               application_names=(), history=[], goal="dibujar una linea")
    assert decision["operation"] != "input.pointer.drag"
