"""Ronda 23 (comprobación en vivo r21, v2-s01 «en la calculadora calculá 37*12»): el «done» del modelo citó «Se muestra 12»
con el átomo exacto «result:37*12» en falso y el sub-objetivo cerró. El App ahora lo rechaza y marca el paso tras el que
llegó («checkUnmet»); la mente se lo dice al modelo en la historia, con la causa, antes de que decida otra vez.

Contracaso: un paso sin esa marca (o con la marca en falso) se lee como siempre.
"""

from __future__ import annotations

from baxy_mind import cu_step_prompt


def test_the_refused_done_tells_the_model_why() -> None:
    step = {"step": 3, "operation": "input.key.press", "key": "enter", "ok": True, "checkUnmet": True}
    line = cu_step_prompt._history_line(step)
    assert line.startswith("3. input.key.press key=enter ok")
    assert cu_step_prompt.CHECK_UNMET_NOTE in line
    assert "Se cumple cuando" in cu_step_prompt.CHECK_UNMET_NOTE


def test_a_step_without_the_mark_reads_as_before() -> None:
    step = {"step": 3, "operation": "input.key.press", "key": "enter", "ok": True}
    assert cu_step_prompt.CHECK_UNMET_NOTE not in cu_step_prompt._history_line(step)
    assert cu_step_prompt.CHECK_UNMET_NOTE not in cu_step_prompt._history_line({**step, "checkUnmet": False})
    assert cu_step_prompt._history_line(step) == "3. input.key.press key=enter ok"
