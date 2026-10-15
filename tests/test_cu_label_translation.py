"""Traducción general de etiquetas (goal v3, punto 6; CONTRATO_VISTA_ACCION.md §4.4.1).

Un lugar dicho en un idioma sobre una ventana en el otro, cuyo par no está en la tabla de
``semantic/missions.py``: el modelo local traduce SÓLO la etiqueta y la traducción se usa sólo
si la vista la muestra. Las vistas son nombres reales de Windows en español (pedido en inglés) y
en inglés (pedido en español); el modelo es falso y devuelve la traducción.
"""

from __future__ import annotations

import pytest

from baxy_mind.semantic.missions import fold as missions_fold
from baxy_mind import computer_use
from baxy_mind import cu_view
from baxy_mind import cu_goals
from baxy_mind import cu_rules
from baxy_mind import cu_model_calls
from baxy_mind.semantic.missions import label_alternatives, label_translatable, read_clause

APPS = ("Configuración", "Explorador de archivos", "Paint", "Word", "Excel", "Visor de eventos",
        "Administrador de tareas", "Reloj", "Calculadora")


def _control(i: int, kind: str, name: str, zone: str = "C", state: str = "") -> dict:
    return {"i": i, "kind": kind, "name": name, "state": state, "zone": zone}


def _view(title: str, controls: list[tuple[str, str, str]], text: dict | None = None) -> dict:
    return {
        "window": {"title": title, "process": "app", "requested": True},
        "controls": [_control(i, kind, name, zone) for i, (kind, name, zone) in enumerate(controls)],
        "text": text or {},
    }


_SETTINGS_SIDE = [
    ("ListItem", "Inicio", "L"), ("ListItem", "Sistema", "L"), ("ListItem", "Bluetooth y dispositivos", "L"),
    ("ListItem", "Red e Internet", "L"), ("ListItem", "Personalización", "L"), ("ListItem", "Aplicaciones", "L"),
    ("ListItem", "Cuentas", "L"), ("ListItem", "Hora e idioma", "L"), ("ListItem", "Juegos", "L"),
    ("ListItem", "Accesibilidad", "L"), ("ListItem", "Privacidad y seguridad", "L"), ("ListItem", "Windows Update", "L"),
    ("Edit", "Buscar una configuración", "TL"),
]


def _settings(*page: tuple[str, str, str]) -> dict:
    return _view("Configuración", [*_SETTINGS_SIDE, *page])


# (pedido, vista, respuesta del modelo falso, control que se pulsa). Las vistas en español llevan
# los nombres que muestra Windows 11 en español; las inglesas, los de Windows en inglés.
CASES: list[tuple[str, dict, dict, str]] = [
    # Configuración en español, pedido en inglés.
    ("go to date and time", _settings(("Button", "Fecha y hora", "C"), ("Button", "Idioma y región", "C"),
                                      ("Button", "Escritura", "C"), ("Button", "Voz", "C")),
     {"es": ["Fecha y hora"], "en": ["Date & time"]}, "Fecha y hora"),
    ("go to default apps", _settings(("Button", "Aplicaciones instaladas", "C"), ("Button", "Aplicaciones avanzadas", "C"),
                                     ("Button", "Aplicaciones predeterminadas", "C"), ("Button", "Aplicaciones de inicio", "C")),
     {"es": ["Aplicaciones predeterminadas"], "en": ["Default apps"]}, "Aplicaciones predeterminadas"),
    ("go to accent color", _settings(("Button", "Fondo", "C"), ("Button", "Colores", "C"), ("Button", "Color de énfasis", "C"),
                                     ("Button", "Temas", "C")),
     {"es": ["Color de énfasis", "Color de acento"], "en": ["Accent color"]}, "Color de énfasis"),
    ("go to night light", _settings(("Button", "Brillo", "C"), ("Button", "Luz nocturna", "C"), ("Button", "HDR", "C"),
                                    ("Button", "Escala", "C")),
     {"es": ["Luz nocturna"], "en": ["Night light"]}, "Luz nocturna"),
    ("go to multitasking", _settings(("Button", "Pantalla", "C"), ("Button", "Sonido", "C"), ("Button", "Multitarea", "C"),
                                     ("Button", "Activación", "C")),
     {"es": ["Multitarea"], "en": ["Multitasking"]}, "Multitarea"),
    ("go to troubleshoot", _settings(("Button", "Solucionar problemas", "C"), ("Button", "Recuperación", "C"),
                                     ("Button", "Proyección en este equipo", "C")),
     {"es": ["Solucionar problemas"], "en": ["Troubleshoot"]}, "Solucionar problemas"),
    ("go to recovery", _settings(("Button", "Solucionar problemas", "C"), ("Button", "Recuperación", "C"),
                                 ("Button", "Portapapeles", "C")),
     {"es": ["Recuperación"], "en": ["Recovery"]}, "Recuperación"),
    ("go to sign-in options", _settings(("Button", "Tu información", "C"), ("Button", "Correo electrónico y cuentas", "C"),
                                        ("Button", "Opciones de inicio de sesión", "C"), ("Button", "Familia", "C")),
     {"es": ["Opciones de inicio de sesión"], "en": ["Sign-in options"]}, "Opciones de inicio de sesión"),
    ("go to mobile hotspot", _settings(("Button", "Wi-Fi", "C"), ("Button", "Ethernet", "C"), ("Button", "VPN", "C"),
                                       ("Button", "Zona con cobertura inalámbrica móvil", "C"), ("Button", "Proxy", "C")),
     {"es": ["Punto de acceso móvil", "Zona con cobertura inalámbrica móvil"], "en": ["Mobile hotspot"]},
     "Zona con cobertura inalámbrica móvil"),
    ("go to game mode", _settings(("Button", "Game Bar", "C"), ("Button", "Capturas", "C"), ("Button", "Modo de juego", "C")),
     {"es": ["Modo de juego"], "en": ["Game mode"]}, "Modo de juego"),
    # Explorador en español.
    ("click properties", _view("Este equipo - Explorador de archivos", [
        ("Button", "Nuevo", "T"), ("Button", "Cortar", "T"), ("Button", "Copiar", "T"), ("Button", "Propiedades", "T"),
        ("TreeItem", "Este equipo", "L"), ("Group", "Dispositivos y unidades", "C")]),
     {"es": ["Propiedades"], "en": ["Properties"]}, "Propiedades"),
    ("go to devices and drives", _view("Este equipo - Explorador de archivos", [
        ("TreeItem", "Inicio", "L"), ("TreeItem", "Galería", "L"), ("TreeItem", "Este equipo", "L"),
        ("Group", "Dispositivos y unidades", "C"), ("ListItem", "Disco local (C:)", "C")]),
     {"es": ["Dispositivos y unidades"], "en": ["Devices and drives"]}, "Dispositivos y unidades"),
    # Paint en español.
    ("click shapes", _view("Sin título - Paint", [
        ("Button", "Selección", "T"), ("Button", "Recortar", "T"), ("Button", "Girar", "T"), ("Button", "Formas", "T"),
        ("Button", "Pinceles", "T"), ("Button", "Capas", "TR")]),
     {"es": ["Formas"], "en": ["Shapes"]}, "Formas"),
    ("click layers", _view("Sin título - Paint", [
        ("Button", "Selección", "T"), ("Button", "Formas", "T"), ("Button", "Capas", "TR")]),
     {"es": ["Capas"], "en": ["Layers"]}, "Capas"),
    ("click crop", _view("Sin título - Paint", [
        ("Button", "Selección", "T"), ("Button", "Recortar", "T"), ("Button", "Cambiar tamaño", "T"), ("Button", "Girar", "T")]),
     {"es": ["Recortar"], "en": ["Crop"]}, "Recortar"),
    ("click rotate", _view("Sin título - Paint", [
        ("Button", "Recortar", "T"), ("Button", "Cambiar tamaño", "T"), ("Button", "Girar", "T"), ("Button", "Voltear", "T")]),
     {"es": ["Girar", "Rotar"], "en": ["Rotate"]}, "Girar"),
    # Word y Excel en español.
    ("go to the draw tab", _view("Documento1 - Word", [
        ("TabItem", "Archivo", "T"), ("TabItem", "Inicio", "T"), ("TabItem", "Insertar", "T"), ("TabItem", "Dibujar", "T"),
        ("TabItem", "Disposición", "T"), ("TabItem", "Referencias", "T"), ("TabItem", "Correspondencia", "T")]),
     {"es": ["Dibujar"], "en": ["Draw"]}, "Dibujar"),
    ("go to the layout tab", _view("Documento1 - Word", [
        ("TabItem", "Inicio", "T"), ("TabItem", "Insertar", "T"), ("TabItem", "Disposición", "T"),
        ("TabItem", "Referencias", "T")]),
     {"es": ["Disposición", "Diseño"], "en": ["Layout"]}, "Disposición"),
    ("go to the mailings tab", _view("Documento1 - Word", [
        ("TabItem", "Inicio", "T"), ("TabItem", "Referencias", "T"), ("TabItem", "Correspondencia", "T")]),
     {"es": ["Correspondencia"], "en": ["Mailings"]}, "Correspondencia"),
    ("go to the data tab", _view("Libro1 - Excel", [
        ("TabItem", "Inicio", "T"), ("TabItem", "Insertar", "T"), ("TabItem", "Fórmulas", "T"), ("TabItem", "Datos", "T"),
        ("TabItem", "Revisar", "T")]),
     {"es": ["Datos"], "en": ["Data"]}, "Datos"),
    ("go to the page layout tab", _view("Libro1 - Excel", [
        ("TabItem", "Inicio", "T"), ("TabItem", "Disposición de página", "T"), ("TabItem", "Fórmulas", "T")]),
     {"es": ["Diseño de página", "Disposición de página"], "en": ["Page Layout"]}, "Disposición de página"),
    # Ventanas en inglés, pedido en español.
    ("andá a registros de windows", _view("Event Viewer", [
        ("TreeItem", "Event Viewer (Local)", "L"), ("TreeItem", "Custom Views", "L"), ("TreeItem", "Windows Logs", "L"),
        ("TreeItem", "Applications and Services Logs", "L")]),
     {"es": ["Registros de Windows"], "en": ["Windows Logs"]}, "Windows Logs"),
    ("andá a vistas personalizadas", _view("Event Viewer", [
        ("TreeItem", "Event Viewer (Local)", "L"), ("TreeItem", "Custom Views", "L"), ("TreeItem", "Windows Logs", "L")]),
     {"es": ["Vistas personalizadas"], "en": ["Custom Views"]}, "Custom Views"),
    ("andá a historial de aplicaciones", _view("Task Manager", [
        ("ListItem", "Processes", "L"), ("ListItem", "Performance", "L"), ("ListItem", "App history", "L"),
        ("ListItem", "Startup apps", "L"), ("ListItem", "Users", "L")]),
     {"es": ["Historial de aplicaciones"], "en": ["App history"]}, "App history"),
    ("hacé clic en agregar una alarma", _view("Clock", [
        ("ListItem", "Focus sessions", "L"), ("ListItem", "Timer", "L"), ("ListItem", "Alarm", "L"),
        ("Button", "Add an alarm", "BR")]),
     {"es": ["Agregar una alarma"], "en": ["Add an alarm", "Add alarm"]}, "Add an alarm"),
    ("hacé clic en vuelta", _view("Clock", [
        ("ListItem", "Stopwatch", "L"), ("Button", "Start", "C"), ("Button", "Lap", "C"), ("Button", "Reset", "C")]),
     {"es": ["Vuelta"], "en": ["Lap"]}, "Lap"),
    ("andá a cálculo de fecha", _view("Calculator", [
        ("ListItem", "Standard", "L"), ("ListItem", "Scientific", "L"), ("ListItem", "Date calculation", "L"),
        ("ListItem", "Currency", "L"), ("ListItem", "Volume", "L")]),
     {"es": ["Cálculo de fecha"], "en": ["Date calculation"]}, "Date calculation"),
    ("andá a moneda", _view("Calculator", [
        ("ListItem", "Standard", "L"), ("ListItem", "Date calculation", "L"), ("ListItem", "Currency", "L")]),
     {"es": ["Moneda"], "en": ["Currency"]}, "Currency"),
]


class _Translator:
    """A local model that only translates: a step request means the test failed (the step must be the reading's)."""

    def __init__(self, reply: dict) -> None:
        self.reply = reply
        self.payloads: list[dict] = []

    def _post_schema_object(self, payload: dict, label: str) -> dict:
        del label
        self.payloads.append(payload)
        if payload.get("grammar") != cu_model_calls.TRANSLATE_GRAMMAR:
            raise AssertionError("the step was asked of the model")
        return self.reply


def _said_label(goal: str) -> str:
    parsed = cu_goals._goal_target(goal)
    assert parsed is not None, goal
    return parsed[2]


def _decide(goal: str, view: dict, model: object, history: list[dict] | None = None, cached: object = None) -> dict:
    return computer_use.decide_step(
        model, objective=goal, goal=goal, application=None, success_check=None, view=view, history=history or [],
        budget_left=8, application_names=APPS, label_translations=cached,
    )


def test_there_are_at_least_twenty_labels_and_none_is_in_the_table() -> None:
    labels = {_said_label(read_clause(said)[0]) for said, *_ in CASES}
    assert len(labels) >= 20
    for said, _view_, reply, clicked in CASES:
        label = _said_label(read_clause(said)[0])
        # Ni el nombre dicho ni el de la pantalla están en la tabla, y ningún nombre dicho encuentra el control.
        assert label_alternatives(label) == (), label
        assert label_alternatives(clicked) == (), clicked
        assert label_translatable(label), label
        assert cu_view.find_control(_view_, label) is None, label


@pytest.mark.parametrize(("said", "view", "reply", "clicked"), CASES, ids=[case[0] for case in CASES])
def test_a_label_out_of_the_table_is_clicked_by_its_translation_on_screen(said: str, view: dict, reply: dict, clicked: str) -> None:
    goal = read_clause(said)[0]
    model = _Translator(reply)
    # Sin traducción la lectura no llega a ese control: es la traducción la que lo encuentra.
    plain = cu_rules.deterministic_step(goal=goal, view=view, history=[])
    assert not (plain and plain["operation"] == "input.visible.click" and plain["arguments"].get("label") == clicked)

    decision = _decide(goal, view, model)

    label = _said_label(goal)
    assert decision["operation"] == "input.visible.click", decision
    assert decision["arguments"]["label"] == clicked
    assert decision["alias"]["from"] == label
    assert cu_view.view_contains(view, decision["alias"]["to"])
    assert decision["translation"]["label"] == label and decision["translation"]["source"] == "model"
    # Una sola llamada corta, con la etiqueta sola: nunca el pedido ni la pantalla.
    assert len(model.payloads) == 1
    sent = model.payloads[0]
    assert sent["messages"] == [
        {"role": "system", "content": cu_model_calls.TRANSLATE_PROMPT}, {"role": "user", "content": label},
    ]
    assert sent["temperature"] == 0.0 and sent["max_tokens"] <= 48


def test_a_translation_not_on_screen_is_never_clicked_and_is_reported_for_the_cache() -> None:
    goal = read_clause("go to date and time")[0]
    view = _settings(("Button", "Idioma y región", "C"), ("Button", "Escritura", "C"))
    model = _Translator({"es": ["Fecha y hora"], "en": ["Date & time"]})

    decision = _decide(goal, view, model)

    assert decision.get("alias") is None
    assert not (decision["operation"] == "input.visible.click"
                and missions_fold(decision["arguments"].get("label")) == "fecha y hora")
    # El shell cuenta el rechazo: la traducción vino y no está en la vista.
    assert decision["translation"]["names"] == ["Fecha y hora", "Date & time"]
    assert not any(cu_view.view_contains(view, name) for name in decision["translation"]["names"])


def test_going_to_a_place_never_clicks_a_switch_its_translation_names() -> None:
    goal = read_clause("go to transparency effects")[0]
    view = _settings(("ToggleButton", "Efectos de transparencia", "C"), ("Button", "Color de énfasis", "C"))
    model = _Translator({"es": ["Efectos de transparencia"], "en": ["Transparency effects"]})

    decision = _decide(goal, view, model)

    assert decision.get("alias") is None
    assert not (decision["operation"] == "input.visible.click"
                and missions_fold(decision["arguments"].get("label")) == "efectos de transparencia")


def test_a_slider_is_no_place_either() -> None:
    goal = read_clause("go to brightness")[0]
    view = _settings(("Slider", "Brillo", "C"), ("Button", "Luz nocturna", "C"))
    model = _Translator({"es": ["Brillo"], "en": ["Brightness"]})

    decision = _decide(goal, view, model)

    assert decision.get("alias") is None
    assert decision["arguments"].get("label") != "Brillo"


@pytest.mark.parametrize("said", ["click file", "click new", "click open", "click view", "click delete", "click install"])
def test_act_names_are_never_translated(said: str) -> None:
    goal = read_clause(said)[0]
    view = _view("Sin título - Paint", [("Button", "Archivo", "T"), ("Button", "Nuevo", "T"), ("Button", "Abrir", "T"),
                                         ("Button", "Ver", "T"), ("Button", "Eliminar", "T"), ("Button", "Instalar", "T")])

    class _Never:
        def _post_schema_object(self, payload: dict, label: str) -> dict:
            if payload.get("grammar") == cu_model_calls.TRANSLATE_GRAMMAR:
                raise AssertionError("an act's name was sent to be translated")
            return {"act": "none"}

    decision = _decide(goal, view, _Never())

    assert decision.get("alias") is None and decision.get("translation") is None


def test_a_label_the_table_knows_is_never_sent_to_the_model() -> None:
    # «downloads» está en la tabla: la tabla va primero y el modelo no traduce.
    assert not label_translatable("downloads")
    assert cu_model_calls.translate_label(_Translator({"es": ["Descargas"], "en": []}), "downloads") == ((), "")


def test_a_cached_translation_costs_no_model_call() -> None:
    goal = read_clause("go to date and time")[0]
    view = _settings(("Button", "Fecha y hora", "C"), ("Button", "Idioma y región", "C"))

    class _Never:
        def _post_schema_object(self, payload: dict, label: str) -> dict:
            raise AssertionError("the model was asked")

    decision = _decide(goal, view, _Never(), cached={"date and time": {"names": ["Fecha y hora"], "seenOnScreen": 3}})

    assert decision["arguments"]["label"] == "Fecha y hora"
    assert decision["alias"] == {"from": "date and time", "to": "Fecha y hora"}
    assert decision["translation"]["source"] == "cache"


def test_a_window_without_a_tree_uses_a_translation_written_on_screen() -> None:
    goal = read_clause("go to the news")[0]
    assert label_alternatives(_said_label(goal)) == ()
    view = {"window": {"title": "Steam", "process": "steamwebhelper", "requested": True},
            "controls": [_control(0, "Pane", "Steam", "C")],
            "text": {"T": ["TIENDA", "BIBLIOTECA", "COMUNIDAD", "NOTICIAS"],
                     "C": ["Las noticias de tus juegos aparecen aquí cuando hay novedades"]}}
    model = _Translator({"es": ["Noticias"], "en": ["News"]})

    decision = _decide(goal, view, model)

    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"] == {"label": "Noticias"}
    assert decision["alias"] == {"from": _said_label(goal), "to": "Noticias"}


def test_a_written_sentence_that_mentions_the_translation_is_no_place() -> None:
    goal = read_clause("go to the news")[0]
    view = {"window": {"title": "Steam", "process": "steamwebhelper", "requested": True},
            "controls": [_control(0, "Pane", "Steam", "C")],
            "text": {"C": ["Las noticias de tus juegos aparecen aquí cuando hay novedades para mostrar"]}}
    model = _Translator({"es": ["Noticias"], "en": ["News"]})

    decision = _decide(goal, view, model)

    assert decision.get("alias") is None


def test_an_unreadable_translation_is_no_name() -> None:
    class _Broken:
        def _post_schema_object(self, payload: dict, label: str) -> dict:
            raise ValueError("cut short")

    assert cu_model_calls.translate_label(_Broken(), "date and time") == ((), "")
    assert cu_model_calls.translate_label(_Translator({"es": "Fecha"}), "date and time") == ((), "model")


# ---------------------------------------------------------------- revisión adversarial (contracasos)

class _NeverTranslates:
    """A local model that must not be asked to translate."""

    def _post_schema_object(self, payload: dict, label: str) -> dict:
        if payload.get("grammar") == cu_model_calls.TRANSLATE_GRAMMAR:
            raise AssertionError("the label was sent to be translated")
        return {"act": "none", "why": "nada"}


class _TranslatesThenWaits(_Translator):
    """Translates, and answers a step request with no step (the model's own click is judged elsewhere)."""

    def _post_schema_object(self, payload: dict, label: str) -> dict:
        if payload.get("grammar") == cu_model_calls.TRANSLATE_GRAMMAR:
            return super()._post_schema_object(payload, label)
        return {"act": "none", "why": "nada"}


def _clicked(decision: dict, name: str) -> bool:
    return decision["operation"] == "input.visible.click" and missions_fold(
        decision["arguments"].get("label")) == missions_fold(name)


_PLAYER = [("ListItem", "Inicio", "L"), ("ListItem", "Buscar", "L"), ("ListItem", "Tu biblioteca", "L"),
           ("Text", "Canciones populares", "C"), ("Button", "Reproducir", "C")]


def test_an_account_act_label_is_never_translated() -> None:
    # «following» es un acto de cuenta: ni se traduce ni se pulsa «Siguiendo», que dejaría de seguir al artista.
    goal = read_clause("go to following")[0]
    view = _view("Reproductor", [*_PLAYER, ("Button", "Siguiendo", "C")])

    decision = _decide(goal, view, _NeverTranslates())

    assert not label_translatable("following")
    assert not _clicked(decision, "Siguiendo")
    assert decision.get("alias") is None


@pytest.mark.parametrize("act", ["Siguiendo", "Guardar en Tu biblioteca", "Eliminar", "Abrir en una nueva ventana"])
def test_a_translation_onto_an_act_the_goal_does_not_ask_for_is_never_clicked(act: str) -> None:
    # El nombre lo pone el modelo, no la persona: la guarda de actos de los clics del modelo vale también aquí.
    goal = read_clause("go to the artists")[0]
    view = _view("Reproductor", [*_PLAYER, ("Button", act, "C")])

    decision = _decide(goal, view, _Translator({"es": [act], "en": ["Artists"]}))

    assert not _clicked(decision, act)
    assert decision.get("alias") is None


def test_a_translation_the_table_knows_as_another_place_is_never_used() -> None:
    # «Diseño» es en la tabla «design»: nunca es «layout», aunque el modelo lo diga primero.
    goal = read_clause("go to the layout tab")[0]
    both = _view("Documento1 - Word", [("TabItem", "Inicio", "T"), ("TabItem", "Diseño", "T"),
                                       ("TabItem", "Disposición", "T"), ("TabItem", "Referencias", "T")])
    only_design = _view("Documento1 - Word", [("TabItem", "Inicio", "T"), ("TabItem", "Diseño", "T")])
    reply = {"es": ["Diseño", "Disposición"], "en": ["Layout"]}

    chosen = _decide(goal, both, _Translator(reply))
    alone = _decide(goal, only_design, _TranslatesThenWaits(reply))

    assert label_alternatives("diseño") == ("design",)
    assert _clicked(chosen, "Disposición") and chosen["alias"] == {"from": "layout", "to": "Disposición"}
    assert not _clicked(alone, "Diseño") and alone.get("alias") is None


def test_a_short_translation_never_lands_on_a_longer_name_that_holds_it() -> None:
    # «Datos» no es «Uso de datos»: la traducción tiene que ser el nombre entero del control.
    goal = read_clause("go to data")[0]
    view = _settings(("Button", "Wi-Fi", "C"), ("Button", "Uso de datos", "C"), ("Button", "Proxy", "C"))

    decision = _decide(goal, view, _Translator({"es": ["Datos"], "en": ["Data"]}))

    assert not _clicked(decision, "Uso de datos")
    assert decision.get("alias") is None


def test_a_written_line_must_be_the_translation_whole() -> None:
    goal = read_clause("go to the news")[0]
    view = {"window": {"title": "Steam", "process": "steamwebhelper", "requested": True},
            "controls": [_control(0, "Pane", "Steam", "C")],
            "text": {"T": ["TIENDA", "BIBLIOTECA", "NOTICIAS DE AMIGOS"]}}

    decision = _decide(goal, view, _Translator({"es": ["Noticias"], "en": ["News"]}))

    assert decision.get("alias") is None


_CHATS = [("Edit", "Buscar o empezar un chat nuevo", "TL"), ("ListItem", "Work", "L"), ("ListItem", "Family", "L"),
          ("ListItem", "Mom", "L")]


@pytest.mark.parametrize("said", ["andá al chat familia", "hacé clic en familia"])
def test_a_chat_is_never_reached_by_translating_its_name(said: str) -> None:
    # Una conversación se llama como la llamó la persona: «Family» no es la «familia» que dijo.
    goal = read_clause(said)[0]
    with_box = _view("Chats", [*_CHATS, ("Edit", "Escribe un mensaje", "B")])
    content = _view("Chats", [("ListItem", "Work", "C"), ("ListItem", "Family", "C"), ("ListItem", "Mom", "C")])
    reply = {"es": ["Familia"], "en": ["Family"]}

    for view in (_view("Chats", _CHATS), with_box, content):
        decision = _decide(goal, view, _Translator(reply))
        assert not _clicked(decision, "Family"), view
        assert decision.get("alias") is None


def test_a_request_that_writes_or_sends_is_never_translated() -> None:
    objective = "andá al chat familia y escribile hola y mandalo"
    goal = read_clause("andá al chat familia")[0]
    view = _view("Chats", [("ListItem", "Work", "L"), ("ListItem", "Family", "L")])

    decision = computer_use.decide_step(
        _NeverTranslates(), objective=objective, goal=goal, application=None, success_check=None, view=view,
        history=[], budget_left=8, application_names=APPS, subgoal=0, subgoal_count=3,
        label_translations={"familia": {"names": ["Family"]}},
    )

    assert not _clicked(decision, "Family")
    assert decision.get("alias") is None and decision.get("translation") is None
