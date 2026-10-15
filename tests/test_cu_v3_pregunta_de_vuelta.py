"""Pasada v3 r9, t-drag-3 (vivo 2026-10-08): «agarrá la nota adhesiva que dice «baxy prueba» y llevala arrastrando a la
esquina de arriba a la derecha de la pantalla» → el decisor eligió input.pointer.drag y el paso de argumentos preguntó
«¿Cuál es el número de la nota adhesiva y cuál es su etiqueta?», una pregunta que la persona no puede contestar.
Estabilización L: input.pointer.drag se retiró del catálogo y arrastrar es un límite que dice el contrato de «sin
operación» (``semantic.drag.asks_to_drag``), así que nadie pregunta por un índice: un arrastre es ese límite y el motor
no lo intenta; una nota llevada a un lugar de la pantalla es mover su ventana (window.move), que conserva su ruta.
Estabilización L4 (en vivo limites1: el motor abrió Notas rápidas y paró con una causa genérica): la frase de t-drag-3
dice el gesto como manera («llevala arrastrando»), así que es el límite de arrastre; la misma nota llevada sin el gesto
conserva window.move.
Contracasos: un arrastre negado, una pregunta sobre la capacidad, un turno con otra operación tipada al lado.
"""

from __future__ import annotations

from baxy_mind import engine_handoff

APPS = ("Notas rápidas", "Microsoft Edge")
TOOLS = {operation: {} for operation in ("mission.computer.use", "input.visible.click", "window.move", "note.create")}
SAID = ("agarrá la nota adhesiva que dice «baxy prueba» y llevala arrastrando a la esquina de arriba a la derecha de "
        "la pantalla")


def _action(*operations: str) -> dict[str, object]:
    return {
        "type": "turn.result", "id": "t-drag-3", "kind": "action", "operation": operations[0],
        "intentOperations": list(operations), "effectOperations": list(operations), "question": "", "reply": "",
        "objective": "Arrastra la nota adhesiva «baxy prueba» a la esquina superior derecha de la pantalla.",
    }


def _gate(turn: dict[str, object], said: str) -> dict[str, object]:
    message = {"id": "t-drag-3", "text": said, "history": [{"role": "user", "content": said}]}
    return engine_handoff._engine_for_an_unserved_order(turn, message, TOOLS, APPS)


def test_t_drag_3_a_note_carried_to_the_screen_keeps_its_window_move() -> None:
    from baxy_mind.semantic import missions
    from baxy_mind.semantic.drag import asks_to_drag
    from baxy_mind.semantic.patterns import known_unsupported_effect_request

    # L4: the gesture said as the manner is the drag limit, never the engine's.
    assert asks_to_drag(SAID)
    assert known_unsupported_effect_request(SAID, tuple(TOOLS))
    assert not missions.engine_can_try(SAID, APPS)
    carried = SAID.replace("llevala arrastrando a", "llevala a")
    assert not asks_to_drag(carried)
    assert _gate(_action("window.move"), carried)["effectOperations"] == ["window.move"]


def test_a_drag_is_the_known_limit_never_a_question_for_an_index_nor_the_engines() -> None:
    from baxy_mind.semantic import missions
    from baxy_mind.semantic.patterns import known_unsupported_effect_request

    for said in ("arrastrá lista.txt adentro de la carpeta archivo, en baxy-prueba-v3", "arrastrala más abajo"):
        assert known_unsupported_effect_request(said, tuple(TOOLS)), said
        assert not missions.engine_can_try(said, APPS), said


def test_a_drag_beside_another_typed_operation_keeps_its_route() -> None:
    turn = _action("note.create", "input.visible.click")
    assert _gate(turn, "creá una nota que diga hola y arrastrala a la esquina")["effectOperations"] == [
        "note.create", "input.visible.click"]


def test_a_search_inside_an_application_said_with_a_slip_is_the_engines_never_the_web() -> None:
    # v3-26 (r9): «abrí el visr de eventos y en Sistema buscame un evento con ID 6005» went to web.search and the final
    # said «No encontré un evento con ID 6005» about a search that never looked in the application. On this head the
    # typed readers read it as the mission in that application (rondas 10–11); this twin keeps it so.
    from baxy_mind.semantic.patterns import resolve_explicit_effects

    said = "abrí el visr de eventos y en Sistema buscame un evento con ID 6005"
    read = resolve_explicit_effects(said, ("web.search", "mission.computer.use", "app.open"), ("Visor de eventos",))
    assert read is not None and read.operations == ("mission.computer.use",)


def test_a_refused_or_asked_about_drag_is_not_handed_over() -> None:
    for said in ("no arrastres nada", "¿podés arrastrar archivos?"):
        assert _gate(_action("input.visible.click"), said)["effectOperations"] == ["input.visible.click"]
