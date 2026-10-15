"""v3 punto 2, lectura en la mente (diag_tipos §2.A, A1–A7): the task types read as checked sub-goals.

The t-* cases (scripts/cu_live/cases/t-*.turns) are the example specification; every rule here is general (no phrase,
no application in the readers) and has its counter-case.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from baxy_mind import known_folders
from baxy_mind import cu_forms
from baxy_mind import cu_rules
from baxy_mind import cu_validate
from baxy_mind import cu_model_calls
from baxy_mind.semantic import missions

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "scripts" / "cu_live" / "cases"
APPS = (
    "Paint", "Bloc de notas", "Notepad", "Word", "Explorador de archivos", "Explorer", "Configuración", "Settings",
    "Mapa de caracteres", "Calculadora", "Calculator", "Steam",
)
DOCUMENTS = r"D:\Perfil\Documentos"


@pytest.fixture(autouse=True)
def _documents(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(known_folders, "known_folder", lambda folder: {"documents": DOCUMENTS}.get(folder))


def _case(name: str) -> str:
    return (CASES / f"{name}.turns").read_text(encoding="utf-8").strip()


def _reads(text: str) -> list[tuple[str, str | None, bool]]:
    reads = missions._compound_reads(missions.fold(text))
    assert reads is not None, text
    return reads


def _steps(text: str) -> list[tuple[str | None, str, str | None, bool]]:
    mission = missions.mission_request(text, APPS)
    assert mission is not None and mission.steps, text
    return [(step.application, step.goal, step.success_check, step.free) for step in mission.steps]


# ------------------------------------------------------------ A1 higiene de cláusula


def test_a_quoted_literal_ends_at_its_closing_quote_and_the_orders_after_it_are_clauses() -> None:
    steps = _steps(_case("t-long-2"))
    goals = [goal for _, goal, _, _ in steps]
    assert "escribir Informe semanal" in goals
    assert ("ponelo en negrita", True) in [(goal, free) for _, goal, _, free in steps]
    assert ("centralo", True) in [(goal, free) for _, goal, _, free in steps]
    assert all(application == "Word" for application, *_ in steps)


def test_a_comma_inside_quotes_is_part_of_the_text() -> None:
    mission = missions.mission_request('en el bloc de notas escribí "casa, roja"', APPS)
    assert mission is not None and mission.goal == "escribir casa, roja"
    mission = missions.mission_request("en el bloc de notas escribí «casa, ponelo en rojo»", APPS)
    assert mission is not None and mission.goal == "escribir casa, ponelo en rojo"


def test_the_target_ends_before_a_remark_a_means_or_a_restatement() -> None:
    steps = _steps(_case("t-scroll-4"))
    assert steps[-1][1] == "seleccionar calc.exe"
    assert steps[-1][2].startswith("control:=calc.exe:selected")
    # Estabilización L4 (en vivo t-scroll-2 tecleó en el buscador): looked for «bajando en la lista» is shown, still
    # without the restatement «, la Ω».
    searched = _steps(_case("t-scroll-2"))
    assert searched[0][1] == "mostrar omega mayuscula"
    assert searched[1][1] == "seleccionar omega mayuscula"
    # Counter-case: a name with no remark keeps all its words.
    assert missions.read_clause("seleccioná el rectángulo redondeado")[0] == "seleccionar rectangulo redondeado"


def test_raising_to_a_power_is_a_sign() -> None:
    assert missions.read_clause("calculá 2 elevado a 10")[0] == "calcular 2 ^ 10"
    assert missions.read_clause("calculate 2 to the power of 8")[0] == "calcular 2 ^ 8"
    assert [goal for _, goal, _, _ in _steps(_case("t-long-1"))][1] == "calcular 2 ^ 10"
    # Counter-case: «elevado» with no second number is no operation.
    assert missions.read_clause("calculá lo elevado") is None or "^" not in missions.read_clause("calculá lo elevado")[0]


def test_a_remark_is_no_clause_and_a_prohibition_keeps_free_sub_goals_out() -> None:
    steps = _steps(_case("t-scroll-1"))
    assert [(application, goal) for application, goal, _, _ in steps] == [
        ("Configuración", "ir a aplicaciones instaladas"), ("Configuración", "mostrar bloc de notas")]
    # Counter-case: beside a prohibition, an order no reader checks is never handed to the model.
    assert missions.mission_request("en Paint andá a Archivo, dibujá un gato, pero no guardes nada", APPS) is None


# ------------------------------------------------------------ A2 rutas de menú y repeticiones


def test_a_menu_route_is_one_click_per_piece_repeated_as_said() -> None:
    steps = _steps(_case("t-menu-3"))
    assert [goal for _, goal, _, _ in steps] == ["hacer clic en view", "hacer clic en zoom", "hacer clic en zoom in"] * 2
    assert all(application == "Notepad" for application, *_ in steps)
    assert steps[0][2] == "control:view:expanded|stepDone:input.visible.click:view&control:zoom"
    assert steps[2][2] == "stepDone:input.visible.click:zoom in"


def test_the_order_said_before_a_route_is_done_once_the_route_is_open() -> None:
    steps = _steps("en Paint gira la imagen 90 grados a la derecha desde el menú Imagen > Girar")
    assert [(goal, free) for _, goal, _, free in steps] == [
        ("hacer clic en imagen", False), ("hacer clic en girar", False), ("gira la imagen 90 grados a la derecha", True)]


def test_a_single_menu_name_is_no_route() -> None:
    mission = missions.mission_request("en el bloc de notas andá a Archivo", APPS)
    assert mission is not None and not mission.steps and mission.goal == "ir a archivo"
    assert missions._route("anda a archivo") is None


# ------------------------------------------------------------ A3 clic derecho


def test_a_right_click_opens_the_menu_of_the_thing_and_its_entry_is_clicked() -> None:
    steps = _steps("en el Explorador de archivos haceme clic derecho en notas.txt y abrime las propiedades")
    assert [goal for _, goal, _, _ in steps] == ["abrir el menu contextual de notas.txt", "hacer clic en propiedades"]
    assert steps[0][2] == missions.context_menu_check("notas.txt")
    assert steps[0][2].startswith(missions.CONTEXT_MENU_CHECK + "|")
    # Counter-case: «abrime las propiedades» alone, with no menu open, is going there.
    assert missions.read_clause("abrime las propiedades")[0] == "ir a propiedades"


def test_a_right_click_as_the_means_goes_before_the_order_and_names_an_empty_space() -> None:
    steps = _steps("en el Explorador de archivos ordená los archivos por tamaño, con el clic derecho en un espacio vacío, Ordenar por")
    assert [(goal, free) for _, goal, _, free in steps] == [
        ("abrir el menu contextual de espacio vacio", False), ("hacer clic en ordenar por", False),
        ("ordená los archivos por tamaño", True)]


# ------------------------------------------------------------ A4 revelar


def test_scrolling_down_to_a_thing_shows_it_and_its_page_opens_after() -> None:
    steps = _steps(_case("t-scroll-3"))
    assert [goal for _, goal, _, _ in steps] == [
        "ir a personalization", "ir a fonts", "mostrar times new roman", "ir a times new roman"]
    assert steps[2][2] == "control:=times new roman"
    # Counter-case: lowering a level down to a number is no list scrolled.
    assert missions.read_clause("bajá el volumen hasta 20") is None or not missions.read_clause(
        "bajá el volumen hasta 20")[0].startswith("mostrar ")


# ------------------------------------------------------------ A5 formularios


def test_a_form_is_one_field_per_pair_and_its_default_button() -> None:
    steps = _steps(_case("t-form-1"))
    assert [(goal, free) for _, goal, _, free in steps] == [
        ("cambiale el tamano a la imagen, donde se ponen ancho y alto", False), ("activar pixeles", False),
        ("desactivar mantener la relacion de aspecto", False),
        ("poner ancho en 800", False), ("poner alto en 600", False), ("hacer clic en aceptar", False)]
    assert steps[3][2] == "value:ancho=800|value:width=800|value:horizontal=800"
    assert "control:mantener relacion de aspecto:off" in steps[2][2]
    # t-form-4 names no application: the reader reads it, the mission is the decider's (no window in front is
    # driven by keys and text the person did not aim at a window; review of v3 punto 2).
    assert missions.mission_request(_case("t-form-4"), APPS) is None
    form4 = _reads(_case("t-form-4"))
    assert [goal for goal, _, _ in form4] == [
        "abrir el dialogo de fuente, donde se ponen fuente, tamano y cursiva", "poner fuente en arial",
        "poner tamano en 20", "activar cursiva",
        "hacer clic en aceptar"]


def test_replacing_fills_both_fields_and_replaces_all_when_said() -> None:
    steps = _steps(_case("t-form-2"))
    assert [goal for _, goal, _, _ in steps] == [
        "abrir el dialogo de reemplazar", "poner buscar en casa", "poner reemplazar en hogar", "hacer clic en reemplazar todo"]
    one = _steps("en el bloc de notas reemplazá «casa» por «hogar»")
    assert one[-1][1] == "hacer clic en reemplazar"


def test_one_value_alone_is_no_form() -> None:
    assert missions._form_reads("pone el tamano en 20") is None
    assert missions._form_reads("subi el volumen a 20") is None


def test_unticking_is_read_in_its_spoken_forms() -> None:
    assert missions.read_clause("desmarcá Ajustar línea")[0] == "desactivar ajustar linea"
    assert missions.read_clause("uncheck Word wrap")[0] == "desactivar word wrap"
    assert missions.read_clause("sacale lo de mantener la relación de aspecto")[0].startswith("desactivar mantener")
    # Counter-case: «quitá» stays an undoing act, never read.
    assert missions.mission_request("en el Explorador de archivos quitá la papelera", APPS) is None


# ------------------------------------------------------------ A6 guardar y abrir


def test_saving_as_writes_the_absolute_path_and_checks_the_file() -> None:
    # t-file-1 and t-file-3 name no application: read by the reader, never a mission on the window in front.
    assert missions.mission_request(_case("t-file-1"), APPS) is None
    assert missions.mission_request(_case("t-file-3"), APPS) is None
    path = DOCUMENTS + r"\baxy-prueba-v3\baxy-nota1.txt"
    steps = _reads(_case("t-file-1"))
    assert [goal for goal, _, _ in steps] == [
        "abrir el dialogo de guardar como", f"poner nombre de archivo en {path}", "hacer clic en guardar"]
    assert steps[2][1] == f"file:{path}&title:baxy-nota1"
    english = _reads(_case("t-file-3"))
    assert english[1][0] == "poner nombre de archivo en " + DOCUMENTS + r"\baxy-prueba-v3\baxy-dibujo.png"
    named = _steps("en el bloc de notas " + _case("t-file-1"))
    assert named[2][2] == f"file:{path}&title:baxy-nota1"


def test_opening_through_the_route_said_replaces_the_opener() -> None:
    steps = _steps(_case("t-file-2"))
    assert [(application, goal) for application, goal, _, _ in steps] == [
        ("Bloc de notas", "hacer clic en archivo"), ("Bloc de notas", "hacer clic en abrir"),
        ("Bloc de notas", "poner nombre de archivo en " + DOCUMENTS + r"\baxy-prueba-v3\lista.txt"),
        ("Bloc de notas", "hacer clic en abrir")]
    assert steps[-1][2] == "title:lista"
    # «…, usa el Abrir de Paint» asks for the window's own Open dialog (review of cu-v3-abrir-archivo, finding 5).
    paint = _steps(_case("t-file-4"))
    assert [goal for _, goal, _, _ in paint][0] == "abrir el dialogo de abrir" and paint[0][0] == "Paint"
    assert [goal for _, goal, _, _ in paint][1:] == [
        "poner nombre de archivo en " + DOCUMENTS + r"\baxy-prueba-v3\foto.png", "hacer clic en abrir"]
    assert paint[-1][2] == "title:foto"


def test_a_place_that_is_no_known_folder_is_not_guessed() -> None:
    assert missions._file_reads("guarda esto como x.txt en la carpeta de juan") is None
    assert missions._file_reads("guarda esto como ..\\x.txt en documentos") is None


# ------------------------------------------------------------ A7 tareas largas


def test_free_sub_goals_ride_only_beside_as_many_checked_ones() -> None:
    """v3 ronda 5 (lectura M6, diseño 5) narrows what this test pinned: free sub-goals beyond the checked ones are
    kept when every sub-goal has its application resolved (v3-49 went to the engine as one sentence); they still need
    as many checked ones when none is resolved, and never ride beside a prohibition."""

    steps = _steps("abre Steam, ve a la biblioteca y dibujá a Batman")
    assert [(goal, free) for _, goal, _, free in steps] == [("ir a biblioteca", False), ("dibujá a Batman", True)]
    many = _steps("abre Steam, ve a la biblioteca, dibujá a Batman y pintalo de rojo")
    assert [(application, free) for application, _, _, free in many] == [
        ("Steam", False), ("Steam", True), ("Steam", True),
    ]
    assert missions.mission_request(
        "abre Steam, ve a la biblioteca, dibujá a Batman y pintalo de rojo, pero no lo guardes", APPS,
    ) is None
    assert missions.mission_request("ve a la biblioteca, dibujá a Batman y pintalo de rojo", APPS) is None


def test_a_model_split_is_used_only_with_the_persons_own_words() -> None:
    said = "en Paint dibujá un gato guardalo como gato.png en Documentos"
    assert missions.model_clauses_fit(said, ["en Paint dibujá un gato", "guardalo como gato.png en Documentos"])
    # Counter-case: an invented word («y borralo») is never read.
    assert missions.model_clauses_fit(said, ["en Paint dibujá un gato", "y borralo"]) is None
    assert missions.model_clauses_fit(said, []) is None
    mission = missions.mission_from_model_clauses(
        said, ["en Paint dibujá un gato", "guardalo como gato.png en Documentos"], APPS)
    assert mission is not None and mission.steps[-1].success_check == f"file:{DOCUMENTS}\\gato.png&title:gato"


class _Model:
    def __init__(self, reply: object) -> None:
        self.reply = reply
        self.payloads: list[dict] = []

    def _post_schema_object(self, payload: dict, what: str) -> object:
        self.payloads.append(payload)
        return self.reply


def test_the_split_call_sends_the_request_alone_and_validates_the_reply() -> None:
    said = "en Paint dibujá un gato guardalo como gato.png"
    model = _Model({"clauses": ["en Paint dibujá un gato", "guardalo como gato.png"]})
    assert cu_model_calls.split_request_clauses(model, said) == ("en Paint dibujá un gato", "guardalo como gato.png")
    assert model.payloads[0]["messages"][1]["content"] == said
    assert cu_model_calls.split_request_clauses(_Model({"clauses": ["borrá todo"]}), said) == ()
    assert cu_model_calls.split_request_clauses(None, said) == ()


# ------------------------------------------------------------ pasos deterministas


def test_a_field_is_set_by_its_label_replacing_what_it_held() -> None:
    # Integration of round 2 (tipos-lectura + tipos-uia): one way to set a form's field, the act the model's «type»
    # with «field» sends (input.text.type field + replace: SetValue or EM_REPLACESEL to that field), never a click,
    # Ctrl+A and typed keys that need the window in front and the person's keyboard.
    field = {"i": 3, "name": "Horizontal:", "kind": "Edit", "value": "1366"}
    view = {"controls": [field]}
    step = cu_rules.deterministic_step(goal="poner ancho en 800", view=view, history=[])
    assert step == {"operation": "input.text.type", "arguments": {"text": "800", "field": "Horizontal", "replace": True},
                    "reason": "el objetivo lo dice"}
    model = cu_validate.validate_decision({"act": "type", "text": "800", "field": "Horizontal"}, view=view, last_failed=None, application_names=[], history=[], goal="poner ancho en 800")
    assert model["arguments"] == step["arguments"]
    # Counter-cases: a field already holding the value, a value already sent, a password or a read-only field are
    # left alone, and no field of that name is the model's.
    assert cu_rules.deterministic_step(goal="poner ancho en 800", view={"controls": [{**field, "value": "800"}]}, history=[]) is None
    sent = [{"operation": "input.text.type", "ok": True, "field": "Horizontal", "text": "800"}]
    assert cu_rules.deterministic_step(goal="poner ancho en 800", view=view, history=sent) is None
    for state in ("password", "readonly"):
        assert cu_rules.deterministic_step(goal="poner ancho en 800", view={"controls": [{**field, "state": state}]}, history=[]) is None
    assert cu_rules.deterministic_step(goal="poner alto en 600", view=view, history=[]) is None


def test_revealing_scrolls_the_list_until_the_thing_shows() -> None:
    hidden = {"controls": [{"i": 0, "name": "Aplicaciones", "kind": "List"}, {"i": 1, "name": "Calculadora", "kind": "ListItem"}]}
    # Integration of round 2: first by its name through UI Automation, the model's «reveal» act (no wheel).
    step = cu_rules.deterministic_step(goal="mostrar Bloc de notas", view=hidden, history=[])
    assert step["operation"] == "input.scroll" and step["arguments"] == {"direction": "down", "amount": 10, "label": "Bloc de notas"}
    revealed = cu_validate.validate_decision({"act": "reveal", "text": "Bloc de notas"}, view=hidden, last_failed=None, application_names=[], history=[], goal="mostrar Bloc de notas")
    assert revealed["arguments"] == step["arguments"]
    # A list whose patterns could not bring it: the wheel, while each turn moves the list.
    by_name = [{"operation": "input.scroll", "ok": False, "label": "Bloc de notas"}]
    wheel = cu_rules.deterministic_step(goal="mostrar Bloc de notas", view=hidden, history=by_name)
    assert wheel["operation"] == "input.scroll" and "label" not in wheel["arguments"]
    shown = {"controls": [*hidden["controls"], {"i": 2, "name": "Bloc de notas", "kind": "ListItem"}]}
    assert cu_rules.deterministic_step(goal="mostrar Bloc de notas", view=shown, history=[]) is None
    # Estabilización L4: a wheel that no longer moves the list is the long list limit, said by the step itself (before,
    # the model was handed it and typed into the window's search, live t-scroll-2).
    stuck = [*by_name, {"operation": "input.scroll", "ok": True, "changed": False}]
    stopped = cu_rules.deterministic_step(goal="mostrar Bloc de notas", view=hidden, history=stuck)
    assert stopped["operation"] == "none" and stopped["code"] == "limit:long_list"


def test_a_context_menu_chooses_the_item_then_presses_its_key() -> None:
    view = {"controls": [{"i": 4, "name": "notas.txt", "kind": "ListItem"}]}
    first = cu_rules.deterministic_step(goal="abrir el menu contextual de notas.txt", view=view, history=[])
    assert first["operation"] == "input.visible.click" and first["arguments"]["index"] == 4
    chosen = [{"operation": "input.visible.click", "ok": True, "label": "notas.txt"}]
    second = cu_rules.deterministic_step(goal="abrir el menu contextual de notas.txt", view=view, history=chosen)
    assert second["operation"] == "input.key.press" and second["arguments"]["key"] == "context_menu"
    # Counter-case: an empty space has no item to choose; the model finds it.
    assert cu_rules.deterministic_step(goal="abrir el menu contextual de espacio vacio", view=view, history=[]) is None


# ------------------------------------------------------------ revisión adversarial (contracasos)

REVIEW_APPS = (*APPS, "Discord", "Chrome", "Spotify")


def _review(text: str) -> missions.MissionRequest | None:
    return missions.mission_request(text, REVIEW_APPS)


def test_dictated_text_is_never_a_route_or_a_form() -> None:
    # What is typed, searched or noted is text: a «>», a list after «menú» or a pair of number and field in it are
    # part of it, never clicks or fields.
    for said, goal in (
        ("en el bloc de notas escribí 5 > 3", "escribir 5 > 3"),
        ("en Discord escribí el menú de hoy, pizza, empanadas", "escribir el menú de hoy, pizza, empanadas"),
        ("en Chrome buscá mesa de 80 de ancho y 120 de alto", "buscar mesa de 80 de ancho y 120 de alto"),
        ("en el bloc de notas escribí la mesa mide 80 de ancho y 120 de alto",
         "escribir la mesa mide 80 de ancho y 120 de alto"),
    ):
        mission = _review(said)
        assert mission is not None and not mission.steps and mission.goal == goal, said
    assert missions._compound_reads("recordame que la pieza mide 3 de ancho y 4 de alto") is None
    assert _review("recordame que la pieza mide 3 de ancho y 4 de alto") is None
    # Counter-case: a route said where routes are said is still one click per piece.
    assert missions._route("desde archivo > abrir") is not None
    assert missions._route("anda a archivo > abrir") is not None


def test_a_greater_sign_names_a_route_only_where_a_route_is_said() -> None:
    assert missions._route("el precio sube de 5 > 3") is None
    assert missions._route("escribi 5 > 3") is None
    assert _review("el precio sube de 5 > 3") is None
    # Counter-case: opening the clause, after a comma or after «using», it is a route.
    assert missions._route("view > zoom > zoom in") is not None
    assert missions._route("zoom in, view > zoom") is not None
    assert missions._route("using view > zoom") is not None


def test_a_search_keeps_its_whole_query() -> None:
    for said, goal in (
        ("en Chrome buscá vuelos desde Santiago a Madrid", "buscar vuelos desde Santiago a Madrid"),
        ("en Chrome buscá how to cook rice using a pan", "buscar how to cook rice using a pan"),
        ("en Chrome buscá tutorial de python, pero en español", "buscar tutorial de python, pero en español"),
        ("en Spotify buscá Pinta y Colorea", "buscar Pinta y Colorea"),
        ("en Chrome buscá New York and New Jersey", "buscar New York and New Jersey"),
    ):
        mission = _review(said)
        assert mission is not None and not mission.steps and mission.goal == goal, said
        # The check names the whole query: a shorter search never passes for the one asked.
        assert mission.success_check.endswith(f"&text:{missions.fold(goal[len('buscar '):])}"), said
    # Counter-case: the way to scroll said at the end and a one-word restatement are no part of the query.
    assert missions.search_target("la omega mayuscula, la ω, bajando en la lista") == "la omega mayuscula"
    # Counter-case: a comma or a sequencer still parts the next order from what is searched.
    mission = _review("en Spotify buscá Pinta, y después dibujá un gato")
    assert mission is not None
    steps = [(step.application, step.goal, step.success_check, step.free) for step in mission.steps]
    assert [(goal, free) for _, goal, _, free in steps] == [("buscar Pinta", False), ("dibujá un gato", True)]


def test_only_before_an_order_is_that_order_never_a_remark() -> None:
    for said, last in (
        ("abrí Steam, andá a la biblioteca y solo mostrame los juegos instalados", "mostrame los juegos instalados"),
        ("open Steam, go to the library and just sort by name", "sort by name"),
    ):
        mission = _review(said)
        assert mission is not None and len(mission.steps) == 2, said
        assert (mission.steps[-1].goal, mission.steps[-1].free) == (last, True), said
    # Counter-case: «solo» with a participle or alone is a remark, never a sub-goal.
    assert missions._is_remark("solo seleccionado") and missions._is_remark("solo eso")
    assert not missions._is_remark("solo mostrame los juegos instalados")
    steps = _steps(_case("t-scroll-4"))
    assert [goal for _, goal, _, _ in steps][-1] == "seleccionar calc.exe"


def test_an_application_named_inside_dictated_text_is_never_where_the_mission_happens() -> None:
    assert _review("escribí que me encanta Discord y apretá enter") is None
    assert _review("escribí hola Steam, seleccioná todo y copialo") is None
    assert missions._framed_application("escribi que me encanta discord", missions.effect_intent.build_application_catalog_index(
        REVIEW_APPS)) is None
    # Counter-case: an application framed as where the clause happens is that application.
    catalog = missions.effect_intent.build_application_catalog_index(REVIEW_APPS)
    assert missions._framed_application("desde archivo > abrir del bloc de notas porfa", catalog) == "Bloc de notas"
    assert missions._framed_application("zoom in twice in notepad using the view menu", catalog) == "Notepad"


def test_no_chain_of_keys_and_text_is_read_for_the_window_in_front() -> None:
    assert _review("guardá esto como informe.txt en Documentos") is None
    # Counter-case: the same order with its application named is read.
    named = _review("en el bloc de notas guardá esto como informe.txt en Documentos")
    assert named is not None and all(step.application == "Bloc de notas" for step in named.steps)


def test_saving_is_read_only_to_a_new_file_at_a_known_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(known_folders, "known_folder", lambda folder: {"documents": str(tmp_path)}.get(folder))
    assert missions._file_reads("guarda esto como nuevo.txt en documentos") is not None
    (tmp_path / "viejo.txt").write_text("x", encoding="utf-8")
    (tmp_path / "informe.docx").write_text("x", encoding="utf-8")
    # Counter-cases: over a file that exists (also one the application names by its own extension) or with no folder
    # said, «¿Desea reemplazarlo?» could come; nothing is read.
    assert missions._file_reads("guarda esto como viejo.txt en documentos") is None
    assert missions._file_reads("guarda esto como informe en documentos") is None
    assert missions._file_reads("guarda esto como nuevo.txt") is None
    # Opening never replaces: a name alone is read, for file.open to look for it in the known folders.
    assert missions._file_reads("abri viejo.txt")[0][0] == f"abrir el archivo {tmp_path / 'viejo.txt'}"


def test_a_dialog_is_opened_by_a_checked_sub_goal_never_by_a_fixed_shortcut() -> None:
    reads = _reads("reemplazá «casa» por «hogar»")
    assert reads[0] == ("abrir el dialogo de reemplazar", "control:reemplazar con|control:replace with", False)
    # Counter-case: a key the shell's input.key.press does not accept is never read from what the person says.
    for said in ("ctrl shift s", "ctrl o", "ctrl h", "f12"):
        if said.replace(" ", "_") not in missions.KEYS:
            assert missions._key_from_words(said) is None, said
    assert missions._key_from_words("ctrl a") == "ctrl_a"


def test_the_keys_the_mind_reads_are_the_shells_own() -> None:
    import re

    catalog = (ROOT / "src" / "Baxy.Kernel" / "Operations" / "ProductCatalog.cs").read_text(encoding="utf-8")
    # The «key» property's own enum (since tipos-uia the descriptor declares «consequence» before it).
    start = catalog.index('String("key", values:', catalog.index('"input.key.press"'))
    enum = catalog[start:catalog.index("]),", start)]
    accepted = set(re.findall(r'"([a-z0-9_]+)"', enum))
    assert set(missions.KEYS) <= accepted
    assert {key for key in missions._KEY_WORDS.values() if key in missions.KEYS} <= accepted


def test_a_size_form_sets_its_unit_first_and_reads_width_by_height_once() -> None:
    steps = _steps(_case("t-form-1"))
    goals = [goal for _, goal, _, _ in steps]
    assert goals.index("activar pixeles") < goals.index("poner ancho en 800")
    assert steps[goals.index("activar pixeles")][2].startswith("control:pixeles:on|")
    by = _steps("en Paint cambiá el tamaño a 500 por 500 píxeles")
    assert [goal for _, goal, _, _ in by] == [
        "cambia el tamano, donde se ponen ancho y alto", "activar pixeles", "poner ancho en 500",
        "poner alto en 500", "hacer clic en aceptar"]
    # Counter-cases: a unit with no width or height is no option to set; styles alone are no dialog to accept.
    assert not any(goal.startswith("activar pix") for goal, _, _ in _reads("pone la fuente en arial, tamano 20"))
    assert missions._form_reads("pone la letra en negrita y subrayado") is None
    assert _reads(_case("t-form-4"))[-1][0] == "hacer clic en aceptar"


def test_two_fields_of_one_name_set_the_first_never_a_guess() -> None:
    size = {"i": 3, "name": "Horizontal", "kind": "Edit", "value": "100"}
    skew = {"i": 7, "name": "Horizontal", "kind": "Edit", "value": "0"}
    # Integration of round 2: the step names the field by its label; the shell's LabelledField takes the first of the
    # homonyms in the view's reading order (ComputerUseTiposTests), the one a person fills first.
    step = cu_rules.deterministic_step(goal="poner ancho en 800", view={"controls": [size, skew]}, history=[])
    assert step["operation"] == "input.text.type" and step["arguments"]["field"] == "Horizontal"
    assert cu_forms._field_named({"controls": [size, skew]}, ("Horizontal",)) is size
    # Counter-case: one field of that name is that field.
    alone = cu_rules.deterministic_step(goal="poner ancho en 800", view={"controls": [skew]}, history=[])
    assert alone["arguments"]["field"] == "Horizontal"
    assert cu_forms._field_named({"controls": [skew]}, ("Horizontal",)) is skew


def test_the_mind_chains_as_many_sub_goals_as_the_shell_accepts() -> None:
    # Integration of round 2: MAX_STEPS was 8 because the catalog's «steps» took 8; both are 10 now and held equal.
    import re

    catalog = (ROOT / "src" / "Baxy.Kernel" / "Operations" / "ProductCatalog.cs").read_text(encoding="utf-8")
    start = catalog.index('"steps",', catalog.index('"mission.computer.use"'))
    limit = re.search(r"maximumItems: (\d+)", catalog[start:start + 400])
    assert limit is not None and int(limit.group(1)) == missions.MAX_STEPS == 10
    ten = ", ".join(f"escribí linea{n}" for n in range(1, 11))
    mission = missions.mission_request(f"en el bloc de notas {ten}", APPS)
    assert mission is not None and len(mission.steps) == 10
    # Counter-case: one more than the shell accepts is never sent as eleven sub-goals.
    eleven = ", ".join(f"escribí linea{n}" for n in range(1, 12))
    longer = missions.mission_request(f"en el bloc de notas {eleven}", APPS)
    assert longer is None or len(longer.steps or ()) <= 10


# ------------------------------------------------------------ v3 r3a lectura L3 y L5: la orden entera, no una cláusula

ROUTE_OPERATIONS = ("app.open", "mission.computer.use", "web.search", "browser.navigate", "file.open", "note.create",
                    "calculator.expression.evaluate", "input.key.press", "input.text.type", "input.visible.click",
                    "window.focus")
LECTURA_APPS = (*APPS, "Reproductor multimedia", "Fotos", "Visor de eventos", "Microsoft Edge")


def _route(text: str) -> tuple[str, ...] | None:
    from baxy_mind.semantic import patterns

    intent = patterns.resolve_explicit_effects(text, ROUTE_OPERATIONS, LECTURA_APPS)
    return None if intent is None else intent.operations


@pytest.mark.parametrize("case", ["v3-14", "v3-15", "t-long-2", "t-long-3"])
def test_a_chain_with_free_sub_goals_the_reader_admits_is_one_mission(case: str) -> None:
    text = {
        "v3-14": "open media player, go to the video library and sort by date added",
        "v3-15": "abre la foto paisaje.jpg que esta en Documentos\\baxy-prueba-v3 en fotos, editala y girala a la derecha"
                 " pero no la guardes",
    }.get(case) or _case(case)
    if case == "t-long-3":
        # Estabilización L: t-long-3 as said draws a rectangle, the drag limit; its chain is read without that clause.
        text = text.replace(", draw a red filled rectangle in the middle", "")
    mission = missions.mission_request(text, LECTURA_APPS)
    assert mission is not None and any(step.free for step in mission.steps), case
    # The router no longer drops what the reader admitted (free sub-goals ride beside as many checked ones).
    assert _route(text) == ("mission.computer.use",), case


def test_a_free_sub_goal_alone_or_beside_a_prohibition_is_still_no_mission() -> None:
    # Counter-cases (missions.mission_request): one free sub-goal with no checked one, and free sub-goals beside a
    # prohibition said apart, stay the decider's.
    assert missions.mission_request("en Paint dibujá un gato", APPS) is None
    assert missions.mission_request("en Paint andá a Archivo, dibujá un gato, pero no guardes nada", APPS) is None
    assert _route("en Paint andá a Archivo, dibujá un gato, pero no guardes nada") != ("mission.computer.use",)
    # A calculation inside the application is still the mission's (already so before).
    assert _route("en la calculadora multiplicá 15 por 3") == ("mission.computer.use",)


def test_a_known_folder_followed_by_a_path_is_no_typed_file_open() -> None:
    from baxy_mind.semantic import files

    # «… paisaje.jpg que está en Documentos\baxy-prueba-v3» named a folder inside Documentos; read as Documentos alone
    # the file was not found there (v3-15) or another one opened.
    assert files.open_named_file_request("abre la foto paisaje.jpg que esta en Documentos\\baxy-prueba-v3") is None
    assert files.open_named_file_request("abre informe.pdf de documentos/trabajo") is None
    # Counter-case: the known folder itself still opens the file by the typed operation.
    assert files.open_named_file_request("abre informe.pdf de documentos") == ("documents", "informe.pdf")
    assert _route("abre informe.pdf de documentos") == ("file.open",)


def test_a_search_with_no_application_is_still_the_web_search() -> None:
    assert _route("busca clima en Santiago") == ("web.search",)


def test_the_name_of_the_application_framed_is_no_evidence_for_a_typed_reading() -> None:
    # v3-24: «eventos» in «Visor de eventos» read the request as a public lookup of events; the order said inside the
    # application reads nothing alone, so the typed reading is dropped and the decider has the turn.
    said = "en el visor de eventos filtra el registro de aplicación para que solo salgan los errores"
    assert missions.framed_clause(said, LECTURA_APPS) == "filtra el registro de aplicacion para que solo salgan los errores"
    assert _route(said) is None
    # Counter-cases: an order inside the application that a typed operation reads keeps that reading («buscá …» in a
    # browser is the search); without a framed application nothing changes.
    assert missions.framed_clause("busca vuelos baratos a Madrid", LECTURA_APPS) is None
    assert _route("en Microsoft Edge buscá vuelos baratos a Madrid") is not None
    assert missions.framed_clause("en la casa filtra el registro", LECTURA_APPS) is None


def test_the_place_the_search_happens_is_no_part_of_the_query() -> None:
    # v3-58 «busca cookies ahí en la configuración» typed «cookies ahi».
    assert missions.search_target("cookies ahi") == "cookies"
    assert missions.search_target("cookies ahí") == "cookies"
    assert missions.search_target("privacy settings there") == "privacy settings"
    # Counter-cases: a quoted query keeps every word, and the adverb alone is the query.
    assert missions.search_target("«cookies ahi»") == "«cookies ahi»"
    assert missions.search_target("ahi") == "ahi"
    assert missions.search_target("ahi te quiero ver") == "ahi te quiero ver"
    # Review of L5: after a preposition the adverb is the query's own place, typed and checked whole.
    assert missions.search_target("restaurantes cerca de aca") == "restaurantes cerca de aca"
    assert missions.search_target("restaurantes cerca de acá") == "restaurantes cerca de acá"
    assert missions.search_target("hotels near here") == "hotels near here"
    assert missions.search_target("que hay por aqui") == "que hay por aqui"
    assert missions.search_target("ofertas desde ahí") == "ofertas desde ahí"
