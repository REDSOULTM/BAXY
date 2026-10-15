"""Ronda 22 (motor-listas-abiertas-y-app-ya-arrancada), pasada r18.

Gemelos con las vistas reales de t2-c04 (cu-v3/tandas_r20/t2/model_calls.jsonl: Configuración > Pantalla, la lista
«Escala» abierta con «100%» y «125% (recomendado)» selected) y t4-c18 («en paint elegí el balde de pintura y el color
rojo»), con sus contracasos: un número que sólo está en un texto no se elige; «150» no es «1500» ni «12» es «125»; un
nombre con «y» sin artículo ni clase propios no se parte; «haz clic en Colores» sigue siendo un clic.
"""

from __future__ import annotations

from baxy_mind import computer_use as cu
from baxy_mind import cu_options
from baxy_mind import cu_diagnosis
from baxy_mind.semantic.missions import mission_request


def _control(i: int, kind: str, name: str, state: str = "", zone: str = "R", value: str = "") -> dict:
    control: dict = {"i": i, "kind": kind, "name": name, "state": state, "zone": zone}
    if value:
        control["value"] = value
    return control


_SETTINGS_HEAD = [
    _control(1, "Button", "Minimizar Configuración", zone="TR"),
    _control(3, "Button", "Cerrar Configuración", zone="TR"),
    _control(4, "Edit", "Cuadro de búsqueda, Buscar una opción", zone="T", value="pantalla"),
    _control(8, "ListItem", "Sistema", "selected", zone="TL"),
    _control(20, "Button", "Pantalla", zone="T"),
    _control(22, "Slider", "Brillo", zone="TR", value="30"),
]
_SETTINGS_TAIL = [
    _control(33, "Button", "Escala"),
    _control(34, "ComboBox", "Resolución de pantalla", "collapsed", zone="BR"),
    _control(35, "ListItem", "1920 × 1080 (recomendada)", "selected", zone="BR"),
    _control(36, "ComboBox", "Orientación de la pantalla", "collapsed", zone="BR"),
    _control(37, "ListItem", "Horizontal", "selected", zone="BR"),
    _control(48, "Text", "Pantalla", zone="T"),
]


def _view(scale: list[dict], *texts: dict) -> dict:
    return {
        "window": {"title": "Configuración", "process": "SystemSettings"},
        "controls": [*_SETTINGS_HEAD, *scale, *_SETTINGS_TAIL, *texts],
        "text": {"R": ["100%", "125% (recomendado)"]},
    }


# t2-c04 request 2: the list open after the click on «Escala».
_OPEN = [
    _control(27, "ComboBox", "Escala", "expanded"),
    _control(28, "ListItem", "100%"),
    _control(29, "ListItem", "125% (recomendado)", "selected focused"),
    _control(30, "ListItem", "150%"),
    _control(31, "ListItem", "175%"),
]
# The first look: the box closed, its value the entry shown selected right after it.
_CLOSED = [_control(27, "ComboBox", "Escala", "collapsed"), _control(28, "ListItem", "125% (recomendado)", "selected")]
_OPENED = [{"step": 1, "operation": "input.visible.click", "label": "Escala", "ok": True}]


def test_t2_c04_t2_open_list_with_the_number_selected_is_already_so() -> None:
    step = cu_options._numbered_list_step("activar escala de la pantalla en 125", _view(_OPEN), _OPENED)
    assert step == {
        "operation": "done", "arguments": {"evidence": "125% (recomendado)", "already": True}, "reason": cu_options.REASON_LIST_VALUE,
    }


def test_t2_c04_t2_closed_box_showing_the_number_is_already_so() -> None:
    step = cu_options._numbered_list_step("pon la escala en 125", _view(_CLOSED), [])
    assert step is not None and step["operation"] == "done" and step["arguments"]["already"] is True


def test_t2_c04_t4_open_list_entry_with_the_number_is_clicked() -> None:
    step = cu_options._numbered_list_step("cambiar la escala a 100", _view(_OPEN), _OPENED)
    assert step == {
        "operation": "input.visible.click", "arguments": {"label": "100%", "index": 28}, "reason": cu_options.REASON_LIST_ENTRY,
    }


def test_t2_c04_t4_after_the_click_it_is_done_by_the_act_never_already() -> None:
    chosen = [
        _control(27, "ComboBox", "Escala", "collapsed"), _control(28, "ListItem", "100%", "selected"),
    ]
    history = [*_OPENED, {"step": 2, "operation": "input.visible.click", "label": "100%", "index": 28, "ok": True}]
    step = cu_options._numbered_list_step("cambiar la escala a 100", _view(chosen), history)
    assert step is not None and step["operation"] == "done"
    assert step["arguments"] == {"evidence": "100%"}


def test_a_failed_click_on_the_entry_is_not_repeated() -> None:
    history = [*_OPENED, {"step": 2, "operation": "input.visible.click", "label": "100%", "index": 28, "ok": False}]
    assert cu_options._numbered_list_step("cambiar la escala a 100", _view(_OPEN), history) is None


def test_decide_step_takes_the_entry_without_the_model() -> None:
    def no_model(*_args, **_kwargs):
        raise AssertionError("the model is not asked")

    step = cu.decide_step(
        no_model, objective="regresa la escala a 100", goal="cambiar la escala a 100", application="Configuración",
        success_check="control:escala en 100:on", view=_view(_OPEN), history=_OPENED, budget_left=10,
        application_names=("Configuración",),
    )
    assert step["operation"] == "input.visible.click"
    assert step["arguments"]["label"] == "100%"


# Contracasos.

def test_a_number_only_in_a_text_is_never_chosen() -> None:
    closed = [_control(27, "ComboBox", "Escala", "collapsed")]
    view = _view(closed, _control(50, "Text", "Escala recomendada: 125%"))
    assert cu_options._numbered_list_step("pon la escala en 125", view, []) is None


def test_a_number_is_a_whole_number_of_the_entry() -> None:
    entries = [
        _control(27, "ComboBox", "Escala", "expanded"),
        _control(28, "ListItem", "1500%"),
        _control(29, "ListItem", "125% (recomendado)", "selected"),
    ]
    assert cu_options._numbered_list_step("pon la escala en 150", _view(entries), _OPENED) is None
    assert cu_options._numbered_list_step("pon la escala en 12", _view(entries), _OPENED) is None


def test_a_list_the_goal_does_not_name_is_not_read() -> None:
    assert cu_options._numbered_list_step("pon el volumen en 100", _view(_OPEN), _OPENED) is None


def test_two_entries_with_the_number_are_the_models() -> None:
    entries = [
        _control(27, "ComboBox", "Escala", "expanded"),
        _control(28, "ListItem", "100%"),
        _control(29, "ListItem", "100% (personalizado)"),
    ]
    assert cu_options._numbered_list_step("pon la escala en 100", _view(entries), _OPENED) is None


def test_a_typed_text_leaves_it_to_the_model() -> None:
    history = [*_OPENED, {"step": 2, "operation": "input.text.type", "text": "125", "ok": True}]
    assert cu_options._numbered_list_step("pon la escala en 125", _view(_CLOSED), history) is None


def test_writing_a_number_is_never_a_choice() -> None:
    assert cu_options._numbered_list_step("escribir 125 en escala", _view(_OPEN), _OPENED) is None


# t4-c18: two objects chosen with one verb, the second with its own article and kind.

def _goals(text: str, apps: tuple[str, ...]) -> list[str]:
    mission = mission_request(text, apps)
    assert mission is not None
    return mission.goal.split("; luego ")


def test_t4_c18_bucket_and_red_are_two_choices() -> None:
    assert _goals("en paint elegí el balde de pintura y el color rojo", ("Paint",)) == [
        "seleccionar balde de pintura", "seleccionar rojo",
    ]


def test_english_object_with_its_own_kind_is_split_too() -> None:
    assert _goals("in paint choose the bucket and the colour red", ("Paint",)) == ["seleccionar bucket", "seleccionar red"]


def test_a_name_that_carries_y_is_one_choice() -> None:
    assert _goals("en Configuración selecciona Sonido y vídeo", ("Configuración",)) == ["seleccionar sonido y video"]
    assert _goals("en Configuración selecciona Brillo y color", ("Configuración",)) == ["seleccionar brillo y color"]


def test_a_click_on_a_control_named_colours_stays_a_click() -> None:
    assert _goals("en paint haz clic en Colores", ("Paint",)) == ["hacer clic en colores"]


# Revisión 1, hallazgo 1: sólo un objetivo que fija un valor o elige una entrada se da por hecho con la entrada vista
# elegida. Configuración > Energía: la caja de suspender cerrada con «15 minutos» selected.

_POWER = {
    "window": {"title": "Configuración", "process": "SystemSettings"},
    "controls": [
        *_SETTINGS_HEAD,
        _control(40, "ComboBox", "Cuando esté enchufado, suspender el equipo después de", "collapsed"),
        _control(41, "ListItem", "15 minutos", "selected"),
    ],
    "text": {"R": ["15 minutos"]},
}


def test_choosing_the_entry_seen_selected_is_already_so() -> None:
    for goal in (
        "poner suspender el equipo despues de 15 minutos", "cambiar suspender el equipo despues a 15 minutos",
        "activar suspender el equipo despues de 15 minutos", "seleccionar suspender el equipo despues de 15 minutos",
    ):
        step = cu_options._numbered_list_step(goal, _POWER, [])
        assert step is not None and step["operation"] == "done", goal
        assert step["arguments"] == {"evidence": "15 minutos", "already": True}, goal


def test_undoing_going_or_clicking_is_never_already_so() -> None:
    for goal in (
        "desactivar suspender el equipo despues de 15 minutos", "quitar suspender el equipo despues de 15 minutos",
        "ir a suspender el equipo despues de 15 minutos", "hacer clic en suspender el equipo despues de 15 minutos",
        "apagar suspender el equipo despues de 15 minutos", "turn off suspender el equipo despues de 15 minutos",
    ):
        assert cu_options._numbered_list_step(goal, _POWER, []) is None, goal


def test_decide_step_never_says_already_for_a_goal_that_undoes() -> None:
    class _Asked(Exception):
        pass

    class _Model:
        """The model is asked: the rule left the goal to it, which is all this counter-case needs."""

        def _post_schema_object(self, *_args, **_kwargs):
            raise _Asked

    no_list = _Model()

    for goal, check in (
        ("desactivar suspender el equipo despues de 15 minutos", "control:suspender el equipo despues de 15 minutos:off"),
        ("ir a suspender el equipo despues de 15 minutos", ""),
        ("hacer clic en suspender el equipo despues de 15 minutos", ""),
    ):
        try:
            step = cu.decide_step(
                no_list, objective=goal, goal=goal, application="Configuración", success_check=check, view=_POWER,
                history=[], budget_left=10, application_names=("Configuración",),
            )
        except _Asked:
            continue
        assert not (step.get("operation") == "done" and step.get("reason") == cu_options.REASON_LIST_VALUE), goal


# Revisión 2, hallazgo 1: una clase seguida de su complemento («el color de relleno») no es un segundo objeto; partirlo
# dejaba como objetivo el complemento, y un clic en la herramienta de relleno o en «Línea» pasaba por el color pedido.

def test_a_kind_with_its_complement_is_never_a_second_object() -> None:
    for text, apps in (
        ("en paint elegí el lápiz y el color de relleno", ("Paint",)),
        ("en paint elegí la forma rectángulo y el color de la línea", ("Paint",)),
        ("en configuración elegí el tema oscuro y el color de énfasis", ("Configuración",)),
        ("in paint choose the pencil and the colour of the line", ("Paint",)),
        ("in paint choose the pencil and the colour for the outline", ("Paint",)),
    ):
        mission = mission_request(text, apps)
        assert mission is not None, text
        goals = mission.goal.split("; luego ")
        assert len(goals) == 1, (text, goals)
        for wrong in ("=relleno", "=fill", "=balde", "=linea", "=line", "=enfasis", "=outline"):
            assert f"click:{wrong}" not in (mission.success_check or ""), (text, wrong)


def test_a_kind_with_a_name_after_it_still_splits() -> None:
    assert _goals("en paint elegí el lápiz y la herramienta borrador", ("Paint",)) == [
        "seleccionar lapiz", "seleccionar borrador",
    ]


# Revisión 2, hallazgo 2 (ronda 20b): con una pregunta abierta en la ventana de la misión ninguna regla actúa; la lista
# numerada tampoco hace clic en la entrada ni da «ya estaba» por encima de ella.

_QUESTION = [
    _control(60, "Window", "¿Quiere mantener esta configuración de pantalla?", zone="C"),
    _control(61, "Button", "Mantener los cambios", zone="C"),
    _control(62, "Button", "Revertir", zone="C"),
]


def test_a_pending_question_keeps_the_numbered_list_out() -> None:
    class _Asked(Exception):
        pass

    class _Model:
        def _post_schema_object(self, *_args, **_kwargs):
            raise _Asked

    for goal, objective in (
        ("cambiar la escala a 100", "regresa la escala a 100"),
        ("activar escala de la pantalla en 125", "ponle la escala en 125"),
    ):
        view = {**_view(_OPEN), "controls": [*_view(_OPEN)["controls"], *_QUESTION]}
        # Without the question the rule decides on its own (the counter-case is the question, nothing else).
        assert cu_options._numbered_list_step(goal, view, _OPENED) is not None, goal
        asked = {**view, "questionPending": True}
        try:
            step = cu.decide_step(
                _Model(), objective=objective, goal=goal, application="Configuración", success_check="control:escala:on",
                view=asked, history=_OPENED, budget_left=10, application_names=("Configuración",),
            )
        except _Asked:
            continue
        assert step.get("reason") not in {cu_options.REASON_LIST_ENTRY, cu_options.REASON_LIST_VALUE}, (goal, step)


# Revisión 3, hallazgo 1: a la meta le sobra algo además de la lista, el número y su unidad («y la orientación en
# vertical»): la escala vista en 125 no cumple la meta entera, ni la entrada «100%» abierta es el único paso.

def _one_goal(text: str) -> str:
    goals = _goals(text, ("Configuración",))
    assert len(goals) == 1, (text, goals)
    return goals[0]


_MORE_THAN_THE_LIST = (
    "en configuración pon la escala en 125 y la orientación en vertical",
    "en configuración cambia la escala a 125 y la orientación a vertical",
    "en configuración cambia la escala a 125 y la resolución en la recomendada",
    "en configuración pon la escala en 125 y después la orientación en vertical",
)


def test_a_goal_that_asks_more_than_the_number_is_never_already_so() -> None:
    for text in _MORE_THAN_THE_LIST:
        assert cu_options._numbered_list_step(_one_goal(text), _view(_CLOSED), []) is None, text
        assert cu_options._numbered_list_step(_one_goal(text), _view(_OPEN), _OPENED) is None, text


def test_a_goal_that_asks_more_than_the_number_never_clicks_the_entry() -> None:
    goal = _one_goal("en configuración cambia la escala a 100 y la orientacion a vertical")
    assert cu_options._numbered_list_step(goal, _view(_OPEN), _OPENED) is None


def test_decide_step_asks_the_model_when_the_goal_asks_more() -> None:
    class _Asked(Exception):
        pass

    class _Model:
        def _post_schema_object(self, *_args, **_kwargs):
            raise _Asked

    for text in (*_MORE_THAN_THE_LIST, "en configuración cambia la escala a 100 y la orientacion a vertical"):
        goal = _one_goal(text)
        for view, history in ((_view(_CLOSED), []), (_view(_OPEN), _OPENED)):
            try:
                step = cu.decide_step(
                    _Model(), objective=text, goal=goal, application="Configuración", success_check="",
                    view=view, history=history, budget_left=10, application_names=("Configuración",),
                )
            except _Asked:
                continue
            assert step.get("reason") not in {cu_options.REASON_LIST_ENTRY, cu_options.REASON_LIST_VALUE}, (text, step)


def test_the_list_with_its_complement_is_still_only_the_number() -> None:
    step = cu_options._numbered_list_step("activar escala de la pantalla en 125", _view(_CLOSED), [])
    assert step is not None and step["arguments"] == {"evidence": "125% (recomendado)", "already": True}


# Revisión 3, hallazgo 2: el número con su unidad. «2 horas» nunca es la entrada «2 minutos».

def _power(entry: str) -> dict:
    return {
        **_POWER,
        "controls": [
            *_SETTINGS_HEAD,
            _control(40, "ComboBox", "Cuando esté enchufado, suspender el equipo después de", "collapsed"),
            _control(41, "ListItem", entry, "selected"),
        ],
        "text": {"R": [entry]},
    }


def test_a_number_with_another_unit_is_never_the_entry() -> None:
    for goal, entry in (
        ("poner suspender el equipo despues de 2 horas", "2 minutos"),
        ("cambiar suspender el equipo despues a 2 horas", "2 minutos"),
        ("poner suspender el equipo despues de 15 horas", "15 minutos"),
    ):
        assert cu_options._numbered_list_step(goal, _power(entry), []) is None, goal
    opened = {
        **_POWER,
        "controls": [
            *_SETTINGS_HEAD,
            _control(40, "ComboBox", "Cuando esté enchufado, suspender el equipo después de", "expanded"),
            _control(41, "ListItem", "1 minuto"),
            _control(42, "ListItem", "2 minutos", "selected"),
            _control(43, "ListItem", "1 hora"),
        ],
    }
    assert cu_options._numbered_list_step("poner suspender el equipo despues de 2 horas", opened, []) is None


def test_the_same_unit_is_still_the_entry() -> None:
    step = cu_options._numbered_list_step("poner suspender el equipo despues de 2 horas", _power("2 horas"), [])
    assert step == {
        "operation": "done", "arguments": {"evidence": "2 horas", "already": True}, "reason": cu_options.REASON_LIST_VALUE,
    }


# Integración ronda 22: la regla de la lista numerada es una regla más; tras un paso de regla que la guarda de la App
# rehusó (ronda 21, v3-36: ``refused``), el paso siguiente es del modelo, no de la lista.

def test_a_step_the_guard_refused_hands_the_list_to_the_model() -> None:
    class _Asked(Exception):
        pass

    class _Model:
        def _post_schema_object(self, *_args, **_kwargs):
            raise _Asked

    refused = {"step": 2, "operation": "input.key.press", "key": "ctrl_k", "ok": False, "error": "document_not_named",
               "source": "rule", "refused": True}
    history = [*_OPENED, refused]
    assert cu_diagnosis.refused_by_the_guard(history)
    # Without the guard's refusal the rule would decide on its own (the counter-case is the refusal, nothing else).
    assert cu_options._numbered_list_step("cambiar la escala a 100", _view(_OPEN), history) is not None
    try:
        step = cu.decide_step(
            _Model(), objective="regresa la escala a 100", goal="cambiar la escala a 100", application="Configuración",
            success_check="control:escala en 100:on", view=_view(_OPEN), history=history, budget_left=10,
            application_names=("Configuración",),
        )
    except _Asked:
        return
    assert step.get("reason") not in {cu_options.REASON_LIST_ENTRY, cu_options.REASON_LIST_VALUE}, step
