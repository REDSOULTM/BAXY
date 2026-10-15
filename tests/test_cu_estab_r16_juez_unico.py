"""Estabilización R16 (libro de vetos y guardas §5): el juez del «done» es uno, el de la mente.

El App juzgaba otra vez el «done» que la mente ya había juzgado (``ComputerUseSuccessCheck.EvidenceRefusal`` y sus
ayudantes, gemelo C# de ``cu_validate._checked_act``). En todas las trazas de cu-v3 rehusó una sola vez (v3-11, pasada
r27 y banco r30, «seen_at_start» sobre el «done» por regla de la página creada: un rechazo incorrecto). Se fue.

Cada escenario que los tests C# fijaban sobre el gemelo del App se fija aquí sobre el juez que queda, con la misma vista
y los mismos pasos, tal como el App se los da a la mente: la vista compacta con lo de ``ForTheJudge`` (``firstLook``,
``typedInSession``, ``chosenBeforeClick``, ``changedByClick``) y el historial de ``HistoryForMind`` (sus veredictos
«query», «echo», «changed»). Un paso que el test C# daba sólo con «surfaceChanged» lleva aquí también «changed»: el
recibo vivo del proveedor trae los dos. Rechazado = la mente no da por hecho el «done» con esa cita (lo rehúsa, lo
convierte en el clic que falta, o lo dice como lo que ya estaba).
"""

from __future__ import annotations

import copy

import pytest

from baxy_mind import cu_evidence
from baxy_mind import cu_first_look
from baxy_mind import cu_goals
from baxy_mind import cu_validate
from baxy_mind.semantic.missions import fold


def _view(title: str, process: str, controls: list[dict], text: dict | None = None, **extra: object) -> dict:
    view = {"window": {"title": title, "process": process},
            "controls": [{**control, "i": control.get("i", k)} for k, control in enumerate(controls)]}
    if text is not None:
        view["text"] = text
    view.update(extra)
    return view


def _first(view: dict) -> str:
    """The sub-goal's first look as the App keeps it (LookText; the mind's twin is look_parts)."""

    return "\n".join(cu_first_look.look_parts(view)) + "\n"


def _judge(cited: str, goal: str, view: dict, history: list[dict], first: str | None = None,
           typed: tuple[str, ...] = ()) -> dict:
    seen = copy.deepcopy(view)
    if first is not None:
        seen["firstLook"] = first
    if typed:
        seen["typedInSession"] = list(typed)
    return cu_validate.validate_decision(
        {"act": "done", "evidence": cited, "why": "r16"}, view=seen, last_failed=None, application_names=(),
        history=copy.deepcopy(history), goal=goal, objective=goal,
    )


def _held(decision: dict, cited: str) -> bool:
    """The done stands on that citation, as an act done (never «already»)."""

    if decision.get("operation") != "done":
        return False
    arguments = decision.get("arguments") or {}
    marks = " «»\"'"
    return fold(str(arguments.get("evidence") or "")).strip(marks) == fold(cited).strip(marks) and not arguments.get("already")


def _click(label: str, *, step: int = 1, **receipt: object) -> dict:
    return {"step": step, "operation": "input.visible.click", "label": label, "ok": True, "changed": True, **receipt}


def _typed(text: str, into: str | None = None, *, step: int = 1, query: bool = False, **receipt: object) -> dict:
    typed = {"step": step, "operation": "input.text.type", "text": text, "ok": True, **receipt}
    if into is not None:
        typed["into"] = into
    if query:
        typed["query"] = True
    return typed


def _key(key: str, *, step: int = 1, **receipt: object) -> dict:
    return {"step": step, "operation": "input.key.press", "key": key, "ok": True, **receipt}


# ------------------------------------------------- ComputerUseMissionTests.TheJudgeOfTheModelsDoneRefusesWhatNoActOfItsOwnBrought

NOTES = _view("Notas", "Notes", [{"kind": "Document", "name": "Nota", "value": "Hoy hace moradosu"}],
              {"C": ["Hoy hace moradosu"]})


def test_the_judge_refuses_what_no_act_of_its_own_brought() -> None:
    typed = [_typed("morado")]
    assert not _held(_judge("Nota", "poner la nota de color morado", NOTES, []), "Nota")
    assert not _held(_judge("Hoy hace moradosu", "poner la nota de color morado", NOTES, typed, "notas\n"), "Hoy hace moradosu")
    assert not _held(_judge("Hoy hace moradosu", "poner la nota de color morado", NOTES, typed,
                            "notas\nhoy hace moradosu\n"), "Hoy hace moradosu")
    assert cu_goals.done_needs_an_act("recortar la imagen en proporcion cuadrada")
    assert not cu_goals.done_needs_an_act("ir a la biblioteca")


def test_contracases_a_reading_still_proves_and_the_minds_judge_was_already_stricter() -> None:
    assert _held(_judge("Nota", "leer la nota", NOTES, []), "Nota")
    results = _view("Tienda", "steam", [{"kind": "Edit", "name": "Buscar en la tienda", "value": "cuphead"},
                                        {"kind": "ListItem", "name": "Cuphead"}])
    searched = [_typed("cuphead", "Buscar en la tienda", query=True), _key("enter", step=2)]
    # The App's twin let the result named as the query prove the search; the mind's judge, upstream, never did (it
    # asks for a line of the result besides the name typed): the done never reached the App, nothing changes with R16.
    assert not _held(_judge("Cuphead", "buscar cuphead", results, searched, "tienda\n"), "Cuphead")
    folder = _view("Documentos", "explorer", [{"kind": "ListItem", "name": "informe"}])
    created = [_typed("informe", "Nombre"), _key("enter", step=2)]
    # The App's twin let the item named exactly as the text typed prove the creation; the mind's judge, upstream, never
    # did (an item that holds it in a longer name does: test_computer_use.py «informe final.txt»): nothing changes.
    assert not _held(_judge("informe", "crear carpeta informe", folder, created, "documentos\n"), "informe")


# ------------------------------------------------- ComputerUseMissionTests.AnOpeningThatMadeTheNewDocumentIsTheActOfCreatingIt


def test_an_opening_that_only_brought_the_application_up_acts_on_nothing() -> None:
    view = _view("Libro1 - Excel", "EXCEL", [])
    reused = [{"step": 1, "operation": "app.open", "ok": True}]
    assert not _held(_judge("Libro1", "crear un blank workbook", view, reused), "Libro1")


# ------------------------------------------------- ComputerUseMissionTests.AListShowingTheEntryChosenInItProvesTheDone


def test_a_list_showing_the_entry_chosen_in_it_proves_the_done() -> None:
    goal = "cambia la fuente a wingdings"
    first = "mapa de caracteres\nfuente:\tarial\n"
    chosen_view = _view("Mapa de caracteres", "charmap",
                        [{"kind": "ComboBox", "name": "Fuente:", "state": "collapsed", "value": "Wingdings"}])
    kept = _view("Mapa de caracteres", "charmap", [{"kind": "ComboBox", "name": "Fuente:", "state": "collapsed", "value": "Arial"},
                                                    {"kind": "Text", "name": "Wingdings"}])
    chosen = _typed("Wingdings", "Fuente", field="Fuente", entry=True, changed=True)
    written = _typed("Wingdings", "Fuente", field="Fuente", changed=True)
    assert _held(_judge("Wingdings", goal, chosen_view, [chosen], first), "Wingdings")
    assert not _held(_judge("Wingdings", goal, chosen_view, [written], first), "Wingdings")
    assert not cu_evidence._entry_shown("Wingdings", kept, [chosen])
    assert cu_evidence._entry_shown("Wingdings", chosen_view, [chosen])


# ------------------------------------------------- ComputerUseMissionTests.AnOptionTheClickChoseProvesTheDoneAndOneChosenBeforeIsAlreadyThere

_TRANSITIONS_BEFORE = _view("Presentación1 - PowerPoint", "POWERPNT", [
    {"kind": "TabItem", "name": "Inicio", "state": "selected"}, {"kind": "TabItem", "name": "Transiciones"},
    {"kind": "ListItem", "name": "Ninguna", "state": "selected"}, {"kind": "ListItem", "name": "Desvanecer"}])
_TRANSITIONS_AFTER = _view("Presentación1 - PowerPoint", "POWERPNT", [
    {"kind": "TabItem", "name": "Inicio"}, {"kind": "TabItem", "name": "Transiciones", "state": "selected focused"},
    {"kind": "ListItem", "name": "Ninguna"}, {"kind": "ListItem", "name": "Desvanecer", "state": "selected"}])


def test_an_option_the_click_chose_proves_the_done_and_one_chosen_before_is_already_there() -> None:
    goal = "En PowerPoint, aplica la transición Desvanecer a la diapositiva activa"
    first = _first(_TRANSITIONS_BEFORE)
    clicked = [_click("Desvanecer", selected=True)]
    by_the_click = {**_TRANSITIONS_AFTER, "chosenBeforeClick": {"1": ["inicio", "ninguna"]}}
    already = {**_TRANSITIONS_AFTER, "chosenBeforeClick": {"1": ["transiciones", "desvanecer"]}}
    assert _held(_judge("Desvanecer", goal, by_the_click, clicked, first), "Desvanecer")
    assert not _held(_judge("Desvanecer", goal, already, clicked, first), "Desvanecer")
    player = _view("Reproductor multimedia", "Microsoft.Media.Player", [
        {"kind": "ListItem", "name": "Configuración", "state": "selected"}, {"kind": "RadioButton", "name": "Claro"},
        {"kind": "RadioButton", "name": "Oscuro", "state": "selected"}, {"kind": "Text", "name": "Oscuro"}],
        chosenBeforeClick={"1": [], "2": ["configuracion"]})
    opened = [_click("Configuración", step=1, selected=True), _click("Tema de la aplicación", step=2)]
    assert cu_evidence.chosen_by_act("Configuración", player, opened)


# ------------------------------------------------- ComputerUseMissionTests.TheMindsClosingsOfWhatIsAlreadyDonePassTheShellsJudge


def test_what_the_first_look_showed_proves_no_new_slide() -> None:
    before = _view("Presentación1 - PowerPoint", "POWERPNT",
                   [{"kind": "TabItem", "name": "Insertar"}, {"kind": "Button", "name": "Nueva diapositiva"}],
                   {"BL": ["Diapositiva 1 de 1"]})
    after = _view("Presentación1 - PowerPoint", "POWERPNT",
                  [{"kind": "TabItem", "name": "Insertar", "state": "selected"}, {"kind": "Button", "name": "Nueva diapositiva"}],
                  {"BL": ["diapositiva 2 de 2"]})
    added = [_click("Insertar", step=1), _click("Nueva diapositiva", step=2)]
    assert _held(_judge("diapositiva 2 de 2", "add a new slide", after, added, _first(before)), "diapositiva 2 de 2")
    assert not _held(_judge("Diapositiva 1 de 1", "add a new slide", before, added, _first(before)), "Diapositiva 1 de 1")


# ------------------------------------------------- ComputerUseMissionTests.AWarningThatSomethingFailedProvesNoDone


def test_a_warning_that_something_failed_proves_no_done() -> None:
    warning = _view("Sin título - OneNote", "ONENOTE", [
        {"kind": "Edit", "name": "Cuadro de texto Nombre de sección", "value": "n"},
        {"kind": "Text", "name": "Ya existe una sección con ese nombre. Utilice otro nombre."}])
    steps = [_click("Crear una nueva sección", step=1), _typed("n", step=2, changed=True)]
    cited = "Ya existe una sección con ese nombre. Utilice otro nombre."
    assert not _held(_judge(cited, "en onenote crea una pagina nueva", warning, steps, "sin titulo - onenote\n"), cited)
    assert _held(_judge(cited, "leer el aviso de onenote", warning, steps, "sin titulo - onenote\n"), cited)


# ------------------------------------------------- ComputerUseMissionTests.SeenAtStartIsJudgedPartByPart


def _switches(bluetooth: str) -> dict:
    return _view("Configuración", "SystemSettings", [
        {"kind": "Button", "name": "Bluetooth"}, {"kind": "Text", "name": bluetooth},
        {"kind": "Button", "name": "Wi-Fi"}, {"kind": "Text", "name": "Activado"}])


def test_seen_at_start_is_judged_part_by_part() -> None:
    first = _first(_switches("Desactivado"))
    on = _switches("Activado")
    toggled = [_click("Bluetooth", toggled=True)]
    assert cu_first_look.shows_anew("activado", on, first)
    assert _held(_judge("Activado", "activar el bluetooth", on, toggled, first), "Activado")
    assert not cu_first_look.shows_anew("activado", _switches("Desactivado"), first)

    def prompt(*lines: str) -> dict:
        return _view("Windows PowerShell", "WindowsTerminal", [], {"C": list(lines)})

    shown = _first(prompt("PS C:\\Users\\usuario>"))
    assert not cu_first_look.shows_anew("ps c:\\users\\usuario>", prompt("PS C:\\Users\\usuario> pruebas"), shown)
    assert cu_first_look.shows_anew("ps c:\\users\\usuario>", prompt("PS C:\\Users\\usuario>", "PS C:\\Users\\usuario>"), shown)


# ------------------------------------------------- ComputerUseMissionTests.SearchingTheNameIsNoActForAGoalOfDoingSomethingElse


def test_searching_the_name_is_no_act_for_a_goal_of_doing_something_else() -> None:
    results = _view("Tienda", "store", [{"kind": "Edit", "name": "Buscar en la tienda", "value": "cuphead"},
                                        {"kind": "ListItem", "name": "Cuphead"}])
    searched = [_typed("cuphead", "Buscar en la tienda", query=True), _key("enter", step=2)]
    installed = [*searched, _click("Instalar", step=3)]
    named = [_typed("informe", "Nombre"), _key("enter", step=2)]
    assert not _held(_judge("Cuphead", "instalar cuphead", results, searched, "tienda\n"), "Cuphead")
    assert not cu_evidence.acted_with_effect(searched, "instalar cuphead")
    assert cu_evidence.acted_with_effect(searched, "buscar cuphead"), "a search is its own act"
    assert cu_evidence.acted_with_effect(installed, "instalar cuphead")
    assert cu_evidence.acted_with_effect(named, "crear la carpeta informe"), "a name box is no search"
    assert not cu_evidence.acted_with_effect(
        [{"step": 1, "operation": "input.scroll", "direction": "down", "ok": True, "changed": False}], "bajar hasta el final")
    assert cu_evidence.acted_with_effect(
        [{"step": 1, "operation": "input.scroll", "direction": "down", "ok": True, "changed": True}], "bajar hasta el final")
    assert not cu_evidence.acted_with_effect([_key("tab")], "marcar la casilla")


# ------------------------------------------------- ComputerUseMissionTests.ACitationThatSaysNothingOfTheGoalIsNoProof


def test_a_notice_of_the_windows_own_state_is_no_proof_and_the_control_the_goal_names_is() -> None:
    word = _view("Documento1  -  Autorecuperado - Word", "WINWORD",
                 [{"kind": "TabItem", "name": "Inicio", "state": "selected"}, {"kind": "Button", "name": "Negrita", "state": "off"}],
                 {"TL": ["Pegar", "Fuente", "ARCHIVO NO GUARDADO RECUPERADO"]})
    first = _first(word)
    read_only = copy.deepcopy(word)
    read_only["text"]["TL"].append("@ DOCUMENTO DE SOLO LECTURA")
    bold = copy.deepcopy(word)
    bold["controls"][1]["state"] = "on"
    goal = "en el word que tengo abierto ponle negrita al texto que tengo seleccionado"
    assert not _held(_judge("@ DOCUMENTO DE SOLO LECTURA", goal, read_only, [_key("ctrl_n")], first),
                     "@ DOCUMENTO DE SOLO LECTURA")
    assert _held(_judge("Negrita", goal, bold, [_click("Negrita")], first), "Negrita")


# ------------------------------------------------- ComputerUseMissionTests.AControlListedOnlyForTheGoalsWords…


def _folder(selected: bool, entry: str | None, reserved: bool) -> dict:
    controls = [{"kind": "Button", "name": name, "zone": "T"} for name in ("Atrás", "Adelante", "Arriba", "Nuevo", "Ordenar", "Ver")]
    controls += [{"kind": "ListItem", "name": f"archivo {k}.txt", "zone": "L", "state": "selected" if selected and k == 3 else ""}
                 for k in range(40)]
    if entry is not None:
        controls.append({"kind": "ListItem", "name": entry, "zone": "L", **({"reserved": True} if reserved else {})})
    return _view("C:\\Users\\p\\Documentos", "explorer", controls,
                 {"L": ["Presupuesto 2023.xlsx", "archivo 0.txt"]}, controlCount=300)


def test_a_control_listed_only_for_the_goals_words_is_no_evidence_of_the_act() -> None:
    goal = "comprime el archivo presupuesto 2023"
    first = _first(_folder(selected=False, entry=None, reserved=False))
    steps = [_click("archivo 3.txt", selected=True)]
    reserved = _folder(selected=True, entry="Presupuesto 2023.xlsx", reserved=True)
    listed = _folder(selected=True, entry="Presupuesto 2023.xlsx", reserved=False)
    assert not _held(_judge("Presupuesto 2023.xlsx", goal, reserved, steps, first), "Presupuesto 2023.xlsx")
    assert _held(_judge("Presupuesto 2023.xlsx", goal, listed, steps, first), "Presupuesto 2023.xlsx")


def _documents(entry: dict | None) -> dict:
    controls = [{"kind": "Edit", "name": "Nombre", "value": "Informe"}]
    controls += [{"kind": "ListItem", "name": f"archivo {k}.txt", "zone": "L"} for k in range(40)]
    if entry is not None:
        controls.append(entry)
    return _view("Documentos", "explorer", controls, controlCount=300)


def test_a_control_listed_only_for_the_goals_words_shows_nothing_elsewhere() -> None:
    goal = "crea una carpeta nueva llamada informe"
    typed = [_typed("Informe", "Nombre", changed=True)]
    assert not _held(_judge("Informe", goal, _documents(None), typed, "documentos\n"), "Informe")
    reserved = {"kind": "ListItem", "name": "Informe 2023.xlsx", "zone": "L", "reserved": True}
    assert not _held(_judge("Informe", goal, _documents(reserved), typed, "documentos\n"), "Informe")
    # The App's twin let an entry listed by the base cut that holds the name lift its veto; the mind's judge, upstream,
    # never did (the name typed is still only what BAXY typed): the done never reached the App, nothing changes with R16.
    listed = {"kind": "ListItem", "name": "Informe 2023.xlsx", "zone": "L"}
    assert not _held(_judge("Informe", goal, _documents(listed), typed, "documentos\n"), "Informe")


# ------------------------------------------------- ComputerUseMissionTests.TheControlTheClickChangedRelatesTheCitation / NewTextAfterAKey…


def _controls(process: str, controls: list[dict], **extra: object) -> dict:
    return _view(process, process, controls, **extra)


@pytest.mark.parametrize("goal", ["dale play al video", "reproduce el video"])
def test_the_control_the_click_changed_relates_play(goal: str) -> None:
    before = _controls("msedge", [{"kind": "Button", "name": "Reproducir (k)", "state": "off"}])
    after = _controls("msedge", [{"kind": "Button", "name": "Pausa (k)", "state": "on"}], changedByClick=[1])
    assert _held(_judge("Pausa (k)", goal, after, [_click("Reproducir (k)")], _first(before)), "Pausa (k)")


@pytest.mark.parametrize("goal", ["activa el wifi", "enciende el wi-fi", "turn on wi-fi"])
def test_a_switch_the_click_turned_on_relates_wifi(goal: str) -> None:
    before = _controls("SystemSettings", [{"kind": "Button", "name": "Wi-Fi", "state": "off"},
                                          {"kind": "Text", "name": "Desactivado"}])
    on = _controls("SystemSettings", [{"kind": "Button", "name": "Wi-Fi", "state": "on"}, {"kind": "Text", "name": "Activado"}])
    assert _held(_judge("Activado", goal, on, [_click("Wi-Fi")], _first(before)), "Activado")


def test_the_option_now_a_value_and_a_number_in_words_relate_their_goals() -> None:
    mode_before = _controls("SystemSettings", [{"kind": "ComboBox", "name": "Elige tu modo", "value": "Claro"}])
    mode_after = _controls("SystemSettings", [{"kind": "ComboBox", "name": "Elige tu modo", "value": "Oscuro"}])
    assert _held(_judge("Oscuro", "pon el tema negro", mode_after, [_click("Oscuro")], _first(mode_before)), "Oscuro")
    calculator = [{"kind": "Text", "name": "La pantalla muestra 0"}, {"kind": "Button", "name": "Siete"},
                  {"kind": "Button", "name": "Multiplicar por"}, {"kind": "Button", "name": "Ocho"},
                  {"kind": "Button", "name": "Es igual a"}]
    before = _controls("CalculatorApp", calculator)
    after = _controls("CalculatorApp", [{**calculator[0], "name": "La pantalla muestra 56"}, *calculator[1:]])
    steps = [_click(name, step=k + 1) for k, name in enumerate(("Siete", "Multiplicar por", "Ocho", "Es igual a"))]
    assert _held(_judge("La pantalla muestra 56", "multiplica siete por ocho", after, steps, _first(before)),
                 "La pantalla muestra 56")


def test_new_text_after_a_key_or_in_another_control_proves_its_goal() -> None:
    song_before = _controls("Spotify", [{"kind": "Button", "name": "Siguiente"}, {"kind": "Text", "name": "Bohemian Rhapsody"}])
    song_after = _controls("Spotify", [{"kind": "Button", "name": "Siguiente"}, {"kind": "Text", "name": "Under Pressure"}])
    assert _held(_judge("Under Pressure", "skip this song", song_after, [_click("Siguiente")], _first(song_before)),
                 "Under Pressure")
    pause_before = _controls("msedge", [{"kind": "Button", "name": "Pausa (k)"}])
    pause_after = _controls("msedge", [{"kind": "Button", "name": "Reproducir (k)"}])
    assert _held(_judge("Reproducir (k)", "pausa el video", pause_after, [_key("k")], _first(pause_before)), "Reproducir (k)")
    assert cu_evidence._unrelated_evidence("DOCUMENTO DE SOLO LECTURA", {**pause_after, "firstLook": _first(pause_before),
                                                                        "text": {"C": ["DOCUMENTO DE SOLO LECTURA"]}},
                                           [_key("k")], "pausa el video")


# ------------------------------------------------- ComputerUseR24ArrivalTests (twin: test_cu_r24_llegada_por_el_acto.py)


def test_r24_a_box_on_from_the_start_with_no_click_on_it_is_still_seen_before() -> None:
    obs = _view("OBS 31.0.0 - Perfil: Sin título", "obs64", [
        {"kind": "CheckBox", "name": "Silenciar 'Audio del escritorio'", "state": "on focused"},
        {"kind": "CheckBox", "name": "Silenciar 'Mic/Aux'", "state": "on"},
        {"kind": "Text", "name": "Audio del escritorio"}], chosenBeforeClick={"3": ["silenciar 'mic/aux'"]})
    first = "obs 31.0.0 - perfil: sin titulo\nsilenciar 'audio del escritorio'\nsilenciar 'mic/aux'\naudio del escritorio\n"
    steps = [_click("Silenciar 'Audio del escritorio'", step=3)]
    assert _held(_judge("Silenciar 'Audio del escritorio'", "silenciar el audio del escritorio", obs, steps, first),
                 "Silenciar 'Audio del escritorio'")
    assert not _held(_judge("Silenciar 'Mic/Aux'", "silenciar el mic/aux", obs, steps, first), "Silenciar 'Mic/Aux'")


def test_r24_a_switch_the_click_turned_off_is_no_proof_of_turning_it_on() -> None:
    off = _view("Configuración rápida", "shell", [{"kind": "Button", "name": "Wi-Fi", "state": "off"},
                                                   {"kind": "Button", "name": "Bluetooth", "state": "off"}], changedByClick=[3])
    first = "configuracion rapida\nwi-fi\nbluetooth\n"
    steps = [_click("Wi-Fi", step=3)]
    assert not _held(_judge("Wi-Fi", "activar el wifi", off, steps, first), "Wi-Fi")


def _onenote(in_search: bool) -> dict:
    if in_search:
        controls = [{"i": 40, "kind": "Edit", "name": "Buscar", "state": "focused", "value": "Lista del super"},
                    {"i": 47, "kind": "Document", "name": "Título de página"}, {"i": 48, "kind": "Document", "name": "Cuerpo de página"}]
    else:
        controls = [{"i": 40, "kind": "Button", "name": "Buscar"},
                    {"i": 47, "kind": "Document", "name": "Título de página", "state": "focused", "value": "Lista del super"},
                    {"i": 48, "kind": "Document", "name": "Cuerpo de página"}]
    return _view("Sin título - APP", "APP", controls)


def test_r24_the_title_typed_into_the_title_field_is_done_and_into_a_search_box_is_not() -> None:
    goal = "ponele de título Lista del super"
    first = "sin titulo - app\ntitulo de pagina\n"
    title = [_typed("Lista del super", "Título de página", step=3, changed=True)]
    search = [_typed("Lista del super", "Buscar", step=3, changed=True, query=True)]
    assert _held(_judge("Lista del super", goal, _onenote(False), title, first), "Lista del super")
    assert not _held(_judge("Lista del super", goal, _onenote(True), search, first), "Lista del super")


def test_r24_the_search_box_clicked_then_typed_into_is_no_arrival() -> None:
    view = _view("Notas - APP", "APP", [{"kind": "Edit", "name": "Buscar", "value": "receta", "state": "focused"},
                                        {"kind": "Button", "name": "Inicio"}], changedByClick=[2])
    steps = [_click("Buscar", step=2), _typed("receta", "Buscar", step=3, changed=True)]
    assert not _held(_judge("Buscar", "buscar receta", view, steps, "notas - app\nbuscar\ninicio\n"), "Buscar")


def _playlist(appeared: list[str]) -> dict:
    return _view("Mi playlist - APP", "APP", [
        {"i": 10, "kind": "Text", "name": "Mi playlist"},
        {"i": 20, "kind": "Edit", "name": "Nombre", "state": "focused", "value": "Gym"},
        {"i": 21, "kind": "Edit", "name": "Descripción"}, {"i": 22, "kind": "Button", "name": "Guardar"},
        {"i": 23, "kind": "Button", "name": "Cerrar"}], newTextAfterClick=appeared)


@pytest.mark.parametrize("goal", ["ponele de nombre «Gym» a la playlist", "escribí «Gym» en el nombre"])
def test_r24_the_name_typed_into_a_form_still_to_save_is_not_set(goal: str) -> None:
    first = "mi playlist - app\nmi playlist\neditar detalles\n"
    steps = [_click("Editar detalles", step=2), _typed("Gym", "Nombre", step=3, changed=True)]
    view = _playlist(["Editar detalles", "Nombre", "Descripción", "Guardar", "Cerrar"])
    assert not _held(_judge("Gym", goal, view, steps, first), "Gym")


def test_r24_the_same_form_after_the_verified_click_on_save_is_set() -> None:
    first = "mi playlist - app\nmi playlist\neditar detalles\n"
    steps = [_click("Editar detalles", step=2), _typed("Gym", "Nombre", step=3, changed=True), _click("Guardar", step=4)]
    assert _held(_judge("Gym", "ponele de nombre «Gym» a la playlist", _playlist(["Cambios guardados"]), steps, first), "Gym")


@pytest.mark.parametrize("appeared", [["Título de la pestaña"], None])
def test_r24_the_rename_box_brought_by_the_click_is_no_name_set(appeared: list[str] | None) -> None:
    extra = {"newTextAfterClick": appeared} if appeared is not None else {}
    view = _view("Windows PowerShell - APP", "APP", [
        {"i": 10, "kind": "TabItem", "name": "Windows PowerShell"},
        {"i": 12, "kind": "Edit", "name": "Título de la pestaña", "state": "focused", "value": "pruebas"}], **extra)
    first = "windows powershell - app\nwindows powershell\ncambiar nombre de pestana\n"
    steps = [_click("Cambiar nombre de pestaña", step=2), _typed("pruebas", "Título de la pestaña", step=3, changed=True)]
    assert not _held(_judge("pruebas", "ponele de título «pruebas» a la pestaña", view, steps, first), "pruebas")


def test_r24_the_rename_box_beside_a_column_of_the_same_name_is_brought() -> None:
    view = _view("Documentos - APP", "APP", [
        {"i": 5, "kind": "HeaderItem", "name": "Nombre"}, {"i": 6, "kind": "ListItem", "name": "Nueva carpeta"},
        {"i": 7, "kind": "Edit", "name": "Nombre", "state": "focused", "value": "pruebas"}])
    steps = [_key("f2", step=2, changed=True), _typed("pruebas", "Nombre", step=3, changed=True)]
    assert not _held(_judge("pruebas", "ponele de nombre «pruebas» a la carpeta Nueva carpeta", view, steps,
                            "documentos - app\nnombre\nnueva carpeta\n"), "pruebas")


# ------------------------------------------------- CuV3CitaPartidaTests (twin: test_cu_v3_cita_partida.py)


def _photo(degrees: str) -> dict:
    return _view("paisaje.jpg", "Photos", [{"kind": "Button", "name": "Girar en el sentido de las agujas del reloj"}],
                 {"TL": ["paisaJe.Jpg", "Restablecer", degrees], "TR": ["Cancelar"]})


def test_a_split_citation_proves_an_act_only_when_one_of_its_pieces_is_new() -> None:
    goal = "girar la imagen a la derecha"
    first = _first(_photo("0°"))
    steps = [_click("Girar en el sentido de las agujas del reloj")]
    assert _held(_judge("Restablecer | 90°", goal, _photo("90°"), steps, first), "Restablecer | 90°")
    assert not _held(_judge("paisaJe.Jpg | Restablecer", goal, _photo("90°"), steps, first), "paisaJe.Jpg | Restablecer")
    assert not _held(_judge("Restablecer | 90°", goal, _photo("90°"), [], first), "Restablecer | 90°")


# ------------------------------------------------- CuV3HonestidadR15bTests.TDrag4_ChoosingTheToolIsDoneByItsClick


def test_t_drag_4_choosing_the_tool_is_done_by_its_click() -> None:
    paint = _view("Sin título - Paint", "mspaint", [{"i": 21, "kind": "Button", "name": "Pinceles", "state": "on"},
                                                     {"i": 40, "kind": "Pane", "name": "Lienzo"}])
    brush = [_click("Pinceles", toggled=True)]
    assert _held(_judge("Pinceles", "seleccionar pinceles", paint, brush), "Pinceles")


# ------------------------------------------------- CuV3R24UnActoSinEfectoTests (twin: test_cu_v3_r24_un_acto_sin_efecto.py)


def _snipping(captured: bool = False) -> dict:
    controls = [{"i": 0, "kind": "Button", "name": "Nueva captura de pantalla"},
                {"i": 1, "kind": "ListItem", "name": "Pantalla completa", "state": "selected"},
                {"i": 2, "kind": "ListItem", "name": "Rectángulo"}]
    if captured:
        controls.append({"i": 3, "kind": "Image", "name": "Captura de pantalla 1"})
    return _view("Recortes - Captura de pantalla 1" if captured else "Recortes", "SnippingTool", controls)


_SNIP_FIRST = "recortes\nnueva captura de pantalla\npantalla completa\nrectangulo"
_FULL_SCREEN = _click("Pantalla completa", step=5, selected=True, kind="ListItem")


@pytest.mark.parametrize("goal", ["sacá una captura de pantalla completa", "haz una captura de pantalla completa",
                                  "hazme una captura de pantalla completa"])
def test_v3_33_an_option_chosen_is_no_product_made(goal: str) -> None:
    assert not _held(_judge("Pantalla completa", goal, _snipping(), [_FULL_SCREEN], _SNIP_FIRST), "Pantalla completa")
    unanswered = [_FULL_SCREEN, _click("Nueva captura de pantalla", step=6, changed=False, kind="Button")]
    assert not _held(_judge("Pantalla completa", goal, _snipping(), unanswered, _SNIP_FIRST), "Pantalla completa")


def test_v3_33_the_capture_made_after_its_command_closes() -> None:
    pressed = [_FULL_SCREEN, _click("Nueva captura de pantalla", step=6, kind="Button")]
    assert _held(_judge("Captura de pantalla 1", "sacá una captura de pantalla completa", _snipping(captured=True), pressed,
                        _SNIP_FIRST), "Captura de pantalla 1")
    assert cu_evidence.product_noun("sacá una captura de pantalla completa") == "captura"
    assert cu_evidence.product_noun("en recortes poner el modo pantalla completa") is None


def test_v3_33_a_new_photo_in_black_and_white_is_still_a_product() -> None:
    photos = _view("Fotos - IMG_0001.jpg", "Photos", [
        {"i": 0, "kind": "Button", "name": "Guardar como copia"}, {"i": 1, "kind": "ListItem", "name": "Original"},
        {"i": 2, "kind": "ListItem", "name": "Blanco y negro", "state": "selected"}, {"i": 3, "kind": "Button", "name": "Tomar foto"}])
    chose = [_click("Blanco y negro", step=4, selected=True, kind="ListItem")]
    assert not _held(_judge("Blanco y negro", "hace una foto en blanco y negro", photos, chose,
                            "fotos - img_0001.jpg\nguardar como copia\noriginal\nblanco y negro"), "Blanco y negro")
