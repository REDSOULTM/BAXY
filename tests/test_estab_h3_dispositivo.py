"""Encargo H3: el estado de un dispositivo nombrado sólo se dice si la lectura de ese turno lo trae en su propia fila.

Tanda n5 (notebook, fable/estab-fase3 5862303c4) t3-c09 t1, «en Configuración andá a Bluetooth y fijate si los
auriculares están conectados»: la pantalla sólo traía una TV LG y el propio PC, más una línea suelta «Conectado»; el
redactor dijo «vi que los auriculares están conectados» y nada lo vetó. En n1 y n6 dijo «no vi los auriculares
conectados, solo un mouse y un control de Xbox» sobre dos filas «Emparejado». Ahora el suelo responde la pregunta por
el estado de un tipo de dispositivo con las filas de dispositivo de la ventana (dato
``operation_floor.v1.json`` «computerUse.answer.devices»; estados de ``screen_state_lines.v1.json``), antes de
cualquier borrador. Payloads reales en ``tests/data/estab_h3_dispositivo.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind import cu_finals
from baxy_mind.computer_use_finals import _computer_use_floor_first
from baxy_mind.cu_projection import project_seen
from baxy_mind.semantic import mission_answer

_DATA = json.loads(
    (Path(__file__).resolve().parent / "data" / "estab_h3_dispositivo.json").read_text(encoding="utf-8")
)
_ASKED = "fijate si los auriculares están conectados"


def _situation(observed: dict) -> dict:
    return {"kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
            "succeeded": True, "observed": observed}


def _seen(question: str, *rows: str) -> dict:
    return {"goal": "ir a bluetooth", "reached": True, "question": question, "screen": {"numbers": list(rows)}}


def test_n5_the_loose_connected_line_is_nobodys_and_the_tv_is_said() -> None:
    assert "auriculares están conectados" in _DATA["n5_draft"]
    assert _computer_use_floor_first(_situation(_DATA["n5_observed"]), "es") == (
        "No vi los auriculares en la pantalla; lo que veo es «[LG] webOS TV NU855BPSA».")


def test_n6_the_paired_rows_are_said_paired_never_connected() -> None:
    assert _computer_use_floor_first(_situation(_DATA["n6_observed"]), "es") == (
        "No vi los auriculares en la pantalla; lo que veo es «BT5.2 Mouse» (Emparejado) y "
        "«Xbox Wireless Controller» (Emparejado).")


def test_n1_each_row_keeps_its_own_state_even_truncated() -> None:
    assert cu_finals.question_answer(_DATA["n1_seen"], english=False) == (
        "No vi los auriculares en la pantalla; lo que veo es «BT5.2 Mouse» (Emparejado), «Xbox Wireless Controller» "
        "(Emparejado), «[LG] webOS TV NU855BPSA» (No conectado) y «[TV] UN40JU6500» (No conectado).")


def test_n1_the_mouse_asked_is_said_with_the_state_its_row_writes() -> None:
    seen = {**_DATA["n1_seen"], "question": "fijate si el mouse está conectado"}
    assert cu_finals.question_answer(seen, english=False) == "Veo «BT5.2 Mouse» (Emparejado)."


@pytest.mark.parametrize(
    ("question", "row", "english", "expected"),
    [
        # Contracases: headphones really connected are said, by their category or their own name.
        (_ASKED, "WH-1000XM4, categoría Audio, 80% de batería, estado Conectado,", False,
         "Veo «WH-1000XM4» (Conectado)."),
        (_ASKED, "Auriculares JBL: Conectado", False, "Veo «Auriculares JBL» (Conectado)."),
        ("check if my headphones are connected", "Sony WH-1000XM4, category Audio, status Connected", True,
         "I see «Sony WH-1000XM4» (Connected)."),
        ("fijate si los headphones están connected", "Galaxy Buds2, categoría Audio, estado Conectado", False,
         "Veo «Galaxy Buds2» (Conectado)."),
        ("decime si los audífonos están emparejados", "Galaxy Buds2, categoría Audio, estado Emparejado", False,
         "Veo «Galaxy Buds2» (Emparejado)."),
    ],
)
def test_a_device_of_the_kind_asked_is_said_with_its_row_state(
    question: str, row: str, english: bool, expected: str,
) -> None:
    assert cu_finals.question_answer(_seen(question, row), english=english) == expected


def test_no_device_row_at_all_says_the_kind_was_not_seen() -> None:
    seen = {**_seen(_ASKED), "screen": {"lines": ["Conectado", "Bluetooth y dispositivos >", "REDNOTE"]}}
    assert cu_finals.question_answer(seen, english=False) == "No vi los auriculares en la pantalla."
    assert cu_finals.question_answer({**seen, "question": "are the headphones connected"}, english=True) == (
        "I didn't see the headphones on the screen.")


@pytest.mark.parametrize(
    "question",
    [
        "decime si el modo es claro u oscuro",  # no device kind
        "fijate si el bluetooth está activado",  # Bluetooth is a place, not a device kind
        "fijate si el audio está activado",  # a category only names rows, never the device asked
        "fijate cuántos auriculares hay",  # no state asked
    ],
)
def test_a_question_about_no_device_state_is_not_read_as_one(question: str) -> None:
    assert mission_answer.device_asked(question) is None


def test_the_kind_is_said_with_the_persons_own_words() -> None:
    assert mission_answer.device_asked(_ASKED) == ("headphones", "los auriculares")
    assert mission_answer.device_asked("fijate si mis audífonos están prendidos") == ("headphones", "audífonos")
    assert mission_answer.device_asked("is the mouse connected") == ("mouse", "the mouse")


def test_the_states_are_the_ones_the_view_groups() -> None:
    # One list: the view's ScreenStateLines (C#) and the mind read the same data.
    data = json.loads((Path(cu_finals.__file__).resolve().parent / "data" / "screen_state_lines.v1.json").read_text(
        encoding="utf-8"))
    assert set(mission_answer.screen_states()) == set(data["states"])


def test_the_draft_never_reaches_the_writer_for_a_device_question() -> None:
    # The floor answers before any draft (llm_compose: _computer_use_floor_first), so the n5 draft cannot be published.
    observed = _DATA["n5_observed"]
    assert project_seen(observed, "es")["question"].strip() == _ASKED
    assert cu_finals.floor_first(observed, english=False, succeeded=True) != ""
    # Contracase: a mission that did not succeed leaves its question to the model (it says it could not see it).
    assert cu_finals.floor_first(observed, english=False, succeeded=False) == ""
