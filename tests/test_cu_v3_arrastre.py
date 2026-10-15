"""Computer use v3, punto 2 (arrastrar y soltar), reescrito en la estabilización L.

v3 leía «arrastrá X a Y» / «mové X dentro de Y» / «drag X onto Y» como un sub-objetivo «arrastrar X a Y» que el acto
``drag`` del bucle hacía con el puntero real. El dueño declaró arrastrar un límite desde el primer día (2026-10-10): el
lector y el acto se retiraron, y el pedido es el límite que dice el contrato de «sin operación»
(``patterns.known_unsupported_effect_request``, lectura ``semantic.drag.asks_to_drag``); ni el lector de misiones ni
el motor lo intentan. Los contracasos de entonces siguen, con lo que deben hacer ahora:
- una ventana, la ventana de una aplicación o una nota llevadas a un lugar de la pantalla son mover una ventana
  (window.move/window.snap, sin puntero): no son el límite, salvo que la persona diga el gesto como manera
  («llevala arrastrando a la esquina…», estabilización L4: en vivo t-drag-3 abrió Notas rápidas y paró con una causa
  genérica; la nota se nombra por lo que dice y su ventana se titula «Notas rápidas», window.move no la elige);
- el puntero mismo («arrastrá el puntero hasta Aceptar», «drag the cursor onto OK») es mover el puntero: no es el límite;
- un pronombre llevado a otro lugar («arrastralo a la papelera», «drag it onto Trash», «arrastrala más abajo») es un
  arrastre de lo dicho antes: es el límite (BAXY no lo arrastra ni borra nada);
- «mové X dentro de Y» no es arrastrar (lo mueve una operación de archivos si la hay).
"""

from __future__ import annotations

import pytest

from baxy_mind.semantic.drag import asks_to_drag
from baxy_mind.semantic.missions import free_form_arguments, mission_request, read_clause
from baxy_mind.semantic.patterns import known_unsupported_effect_request

APPLICATIONS = ("Spotify", "Discord", "Explorador de archivos", "PowerPoint", "Paint")
OPERATIONS = ("mission.computer.use", "window.move", "window.snap", "filesystem.move", "app.open")


@pytest.mark.parametrize(
    "said",
    [
        # t-drag-1: the folder's place after the comma is no part of the drop.
        "arrastrá lista.txt adentro de la carpeta archivo, en baxy-prueba-v3",
        "arrastrá lista.txt a la carpeta archivo",
        "drag the slide Tres onto the slide Uno",
        "En el panel de miniaturas arrastra la diapositiva «Tres» para que quede la primera",
        "en el explorador de archivos arrastrá lista.txt a la carpeta archivo",
        "dragueá el archivo informe.txt a la carpeta Docs",
        "arrastrá el archivo volumen.txt a la carpeta Docs",
        "arrastra este archivo a esa ventana",
        # A pronoun carried elsewhere drags what was said before: the limit, nothing deleted.
        "arrastralo a la papelera",
        "drag it onto Trash",
        "arrastrala más abajo",
        # Estabilización L4 (en vivo t-drag-3, t-drag-4): the gesture said as the manner of carrying or drawing.
        "agarrá la nota adhesiva que dice «baxy prueba» y llevala arrastrando a la esquina de arriba a la derecha de la "
        "pantalla",
        "en Paint draw una línea recta arrastrando el mouse de la izquierda a la derecha del lienzo, más o menos por la "
        "mitad",
        "move the file to the folder by dragging it",
        "drag and drop the photo onto the desktop folder",
    ],
)
def test_a_drag_is_the_known_limit_and_never_a_mission(said: str) -> None:
    assert asks_to_drag(said)
    assert known_unsupported_effect_request(said, OPERATIONS)
    assert mission_request(said, APPLICATIONS) is None
    assert free_form_arguments(said, APPLICATIONS) is None
    reading = read_clause(said)
    assert reading is None or not reading[0].startswith("arrastrar ")


@pytest.mark.parametrize(
    "said",
    [
        # A window moved, the window of an application, or a note carried to a place of the screen: window.move/snap.
        "arrastrá la ventana a la izquierda",
        "drag the window to the right",
        "arrastrá la nota a la esquina de arriba",
        "arrastrá la nota a la otra pantalla",
        "drag the note to the second screen",
        "arrastrá Paint a la derecha",
        "arrastrá Spotify a la otra pantalla",
        "drag Discord to the left",
        # Estabilización L4: a window carried with the gesture said is still a window moved.
        "llevá la ventana arrastrando a la izquierda",
        # The pointer itself: moving it, never dragging a control.
        "arrastrá el puntero hasta Aceptar",
        "drag the cursor onto OK",
        "mueve el mouse sobre el botón Inicio",
        "mové el cursor sobre Aceptar",
        "move the mouse onto the Start button",
        # A level set by its own operation.
        "arrastrá el volumen al 50",
        "drag the brightness to 70%",
        # Moving into something is no drag.
        "mové la foto dentro de la carpeta Viajes",
        "move report.docx into Archive",
        "mové la foto a la izquierda",
    ],
)
def test_contracase_a_window_the_pointer_a_level_or_a_move_is_no_drag(said: str) -> None:
    assert not asks_to_drag(said)
    assert not known_unsupported_effect_request(said, OPERATIONS)


@pytest.mark.parametrize(
    "said",
    [
        "en discord arrastrá Spotify a general",
        "en powerpoint mové Spotify dentro de Viajes",
        "en el explorador de archivos drag Discord onto Archive",
    ],
)
def test_an_installed_application_dragged_is_never_a_drag_goal(said: str) -> None:
    mission = mission_request(said, APPLICATIONS)
    assert mission is None or not any(
        goal.startswith("arrastrar ") for goal in (mission.goal, *(step.goal for step in mission.steps))
    )


@pytest.mark.parametrize(
    "said",
    [
        # Review of L (H2, H3): a word of dragging inside what is written, searched, opened or named is no act.
        "en Spotify buscá Drag Me Down y ponela",
        "busca Drag Race en Netflix",
        "en Chrome buscá clic derecho no funciona",
        "abrí draw.io en Chrome",
        "en el Bloc de notas escribí: arrastrá los archivos a la papelera",
        "escribí «drag and drop» en el bloc de notas",
    ],
)
def test_a_drag_word_that_is_no_act_is_no_limit(said: str) -> None:
    assert not asks_to_drag(said)
