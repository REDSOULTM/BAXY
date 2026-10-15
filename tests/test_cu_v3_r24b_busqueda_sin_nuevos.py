"""Revisión 1 de r24b (banco r23, v1): tras SetValue «Spotify» en la caja de la Store y un Enter que no llegó, lo que
nombraba la consulta (el banner de la portada) ya estaba antes de buscar. El App marca el paso («searchNothingNew») y
la mente se lo dice al modelo en la historia: la búsqueda no mostró resultados nuevos.

Contracaso: un paso sin esa marca (o con la marca en falso) se lee como siempre.
"""

from __future__ import annotations

from baxy_mind import cu_step_prompt


def test_the_search_that_brought_nothing_new_is_told_to_the_model() -> None:
    step = {"step": 4, "operation": "input.key.press", "key": "enter", "ok": True, "searchNothingNew": True}
    line = cu_step_prompt._history_line(step)
    assert line.startswith("4. input.key.press key=enter ok")
    assert cu_step_prompt.SEARCH_NOTHING_NEW_NOTE in line
    assert "resultados nuevos" in cu_step_prompt.SEARCH_NOTHING_NEW_NOTE
    # Revisión 3: dice lo visto, no una causa que la vista no prueba.
    assert "no corrió" not in cu_step_prompt.SEARCH_NOTHING_NEW_NOTE
    assert "no llegó" not in cu_step_prompt.SEARCH_NOTHING_NEW_NOTE


def test_a_step_without_the_mark_reads_as_before() -> None:
    step = {"step": 4, "operation": "input.key.press", "key": "enter", "ok": True}
    assert cu_step_prompt.SEARCH_NOTHING_NEW_NOTE not in cu_step_prompt._history_line(step)
    assert cu_step_prompt.SEARCH_NOTHING_NEW_NOTE not in cu_step_prompt._history_line({**step, "searchNothingNew": False})
    assert cu_step_prompt._history_line(step) == "4. input.key.press key=enter ok"
