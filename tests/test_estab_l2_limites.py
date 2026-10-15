"""Estabilización L2: los límites que se descubren al actuar o se leen sobre el ACTO de la misión, y «¿En cuál ventana?».

Con todas las frases de la revisión de L (cu-v3/estab/revision_L.md):
- H1: la pregunta nunca le quita el turno a una ruta tipada (memoria, portapapeles, contactos, nota, canción).
- H2: el texto dictado, citado o buscado nunca es un límite, y la ruta tipada que lo escribe se conserva.
- H3: sólo el formato de un texto en una cinta es el límite de formato; el mapa, los íconos, la barra de tareas, el
  tamaño de la letra del sistema, un diálogo nombrado o una canción no lo son.
- H5: el límite dice también lo que sí hizo antes (un Bluetooth desactivado, un mensaje enviado).
- H8d: la respuesta a «¿En cuál ventana?» sigue el pedido en la ventana nombrada.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from baxy_mind import computer_use
from baxy_mind import cu_model_calls
from baxy_mind import cu_finals
from baxy_mind.semantic import limits, missions
from baxy_mind.semantic.drag import asks_to_drag
from baxy_mind import engine_handoff

_CASES = Path(__file__).resolve().parent.parent / "scripts" / "cu_live" / "cases"
APPS = ("Bloc de notas", "Word", "Excel", "Discord", "Spotify", "Paint", "Explorador de archivos", "Configuración",
        "Microsoft Edge", "Netflix", "YouTube", "Google Chrome")


# ------------------------------------------------------------------------------------------ the act read (H2, H3)

@pytest.mark.parametrize(
    ("said", "kind"),
    [
        ("haceme clic derecho en notas.txt y abrime las propiedades", "context_menu"),
        ("abrir el menu contextual de notas.txt", "context_menu"),
        ("en baxy-prueba-v3 ordená los archivos por tamaño, con el clic derecho en un espacio vacío, Ordenar por",
         "context_menu"),
        ("right-click the file and choose Properties", "context_menu"),
        ("ponelo en negrita", "format"),
        ("poné el título en negrita", "format"),
        ("dale negrita", "format"),
        ("centralo", "format"),
        ("centrá el título", "format"),
        ("subrayá el texto", "format"),
        ("make the title bold", "format"),
        ("Insert a table with 4 columns and 3 rows in this Word document", "format"),
        ("insertá una tabla de 3 por 3", "format"),
    ],
)
def test_a_limit_said_as_an_act_is_read(said: str, kind: str) -> None:
    assert limits.act_limit(said) == kind


H2_TEXT = [
    "en el Bloc de notas escribí: hoy dibujé un gato",
    "en Word escribí «el texto subrayado es importante»",
    "en Word escribí Informe en negrita",
    "en Excel escribí Total en A1 y ponelo",
    "en Discord escribile a Ana que lo ponga en negrita",
    "en el Bloc de notas escribí el título centrado",
    "en Spotify buscá Drag Me Down y ponela",
    "en YouTube buscá how to draw a horse",
    "en Chrome buscá como dibujar un gato",
    "en Chrome buscá clic derecho no funciona",
    "abrí el bloc de notas y escribí: hoy dibujé un gato",
    "escribí «ponelo en negrita» en el bloc de notas",
    "abrí word y escribí Informe en negrita",
]
H3_NOT_THE_RIBBON = [
    "centrá el mapa en Santiago",
    "alineá los íconos del escritorio",
    "centrá la barra de tareas",
    "en configuración aumentá el tamaño de la letra",
    "aumenta el tamaño de la fuente en Chrome",
    "buscá el texto resaltado",
    "highlight the search result",
    "abrí la carpeta Cursiva",
    "en Spotify poné Bold as Love",
    "abrí draw.io en Chrome",
    "busca Drag Race en Netflix",
    "en word andá a Dibujar",
    "el botón derecho del mouse no funciona",
    "Ponme el texto seleccionado en Arial, tamaño 20 y en cursiva, desde el cuadro de diálogo de Fuente",  # t-form-4
    "hacé clic en Archivo",
    "andá a la pestaña Insertar",
    "bajá en la lista hasta el Bloc de notas",
]


@pytest.mark.parametrize("said", H2_TEXT + H3_NOT_THE_RIBBON)
def test_text_that_is_written_searched_quoted_or_no_ribbon_act_is_no_limit(said: str) -> None:
    assert limits.act_limit(said) is None
    assert not asks_to_drag(said)
    mission = missions.mission_request(said, APPS)
    if mission is not None:
        marked = limits.with_declared_limits(mission.arguments())
        assert not any(step.get("limit") for step in marked.get("steps") or ()), said


@pytest.mark.parametrize(
    ("said", "operations"),
    [
        ("abrí el bloc de notas y escribí: hoy dibujé un gato", ("app.open", "input.text.type")),
        ("escribí «ponelo en negrita» en el bloc de notas", ("input.text.type",)),
        ("abrí word y escribí Informe en negrita", ("app.open", "input.text.type")),
    ],
)
def test_h2_the_typed_route_that_writes_it_is_kept(said: str, operations: tuple[str, ...]) -> None:
    tools = {name: {} for name in ("mission.computer.use", "app.open", "input.text.type")}
    turn = {"type": "turn.result", "id": "h2", "kind": "action", "operation": operations[0],
            "intentOperations": list(operations), "effectOperations": list(operations), "question": "", "reply": "",
            "objective": said}
    result = engine_handoff._engine_for_an_unserved_order(
        turn, {"id": "h2", "text": said, "history": [{"role": "user", "content": said}]}, tools, APPS)
    assert result["effectOperations"] == list(operations)


def test_a_chain_is_marked_at_its_first_limit_and_nothing_after_it_is_kept() -> None:
    # t-long-2: the document and the title are the safe part; the bold is the limit; the rest is never reached.
    mission = missions.mission_request(
        "en Word creá un documento en blanco, escribí «Informe semanal» como título, ponelo en negrita, centralo y "
        "guardalo como baxy-informe en Documentos\\baxy-prueba-v3", APPS)
    assert mission is not None
    marked = limits.with_declared_limits(mission.arguments())
    limits_said = [step.get("limit") for step in marked["steps"]]
    assert limits_said[-1] == "format" and limits_said.count("format") == 1
    assert all(step.get("limit") is None for step in marked["steps"][:-1])


def test_t_menu_1_is_marked_after_the_folder() -> None:
    # The sub-goals the reader wrote for t-menu-1 in r30 (evidencia_r30/v2-t-menu-1): the folder, the right click, the
    # entry of its menu; the entry after the limit is never kept.
    read = {"goal": "ir a baxy-prueba-v3; luego abrir el menu contextual de notas.txt; luego hacer clic en propiedades",
            "steps": [
                {"goal": "ir a baxy-prueba-v3", "application": "Explorador de archivos", "successCheck": None},
                {"goal": "abrir el menu contextual de notas.txt", "application": "Explorador de archivos",
                 "successCheck": None},
                {"goal": "hacer clic en propiedades", "application": "Explorador de archivos", "successCheck": None},
            ]}
    marked = limits.with_declared_limits(read)
    assert [step.get("limit") for step in marked["steps"]] == [None, "context_menu"]


def test_no_request_of_bank_b_is_a_limit_nor_a_which_window_question() -> None:
    bank = (_CASES / "BANCO_72.txt").read_text(encoding="utf-8").split()
    said = [
        line for case in bank for line in (_CASES / f"{case}.turns").read_text(encoding="utf-8").splitlines()
        if line.strip() and line.strip() not in {"no", "sí", "si"}
    ]
    assert [line for line in said if limits.act_limit(line) or limits.asks_which_window(line, APPS)] == []


# ------------------------------------------------------------------------------------------ the list that does not end

def _scroll(step: int, *, ok: bool = True, changed: bool = True, label: str | None = None) -> dict:
    scroll = {"step": step, "operation": "input.scroll", "ok": ok, "changed": changed, "surfaceChanged": changed}
    if label:
        scroll["label"] = label
    return scroll


class _Scroller:
    """A model that only ever scrolls down."""

    def _post_schema_object(self, payload: dict, label: str) -> object:
        if payload["messages"][0]["content"] == cu_model_calls.TRANSLATE_PROMPT:
            return {"es": [], "en": []}
        return {"act": "scroll", "direction": "down"}


def _decide(history: list[dict]) -> dict:
    view = {"window": {"title": "Configuración", "process": "SystemSettings"}, "controls": [
        {"i": 0, "kind": "List", "name": "Aplicaciones instaladas"}, {"i": 1, "kind": "ListItem", "name": "Audacity"}]}
    return computer_use.decide_step(
        _Scroller(), objective="abrí Configuración, Aplicaciones instaladas, y bajá en la lista hasta el Bloc de notas",
        goal="mostrar bloc de notas", application="Configuración", success_check="control:=bloc de notas",
        view=view, history=history, budget_left=10, application_names=["Configuración"], subgoal=1, subgoal_count=2,
    )


@pytest.mark.parametrize(
    ("objective", "goal"),
    [
        # Review of L2, C1: a counted scroll or a page is done as said, never cut as a list that does not end.
        ("en Chrome bajá 5 veces", "baja 5 veces"),
        ("scroll down five times in Chrome", "scroll down five times"),
        ("en Chrome bajá hasta el final de la página", "bajar hasta el final de la pagina"),
        ("en Edge leé el artículo hasta abajo", "leer el articulo"),
    ],
)
def test_c1_a_counted_scroll_or_a_page_is_never_the_long_list(objective: str, goal: str) -> None:
    view = {"window": {"title": "Noticias - Google Chrome", "process": "chrome"}, "controls": [
        {"i": 0, "kind": "Document", "name": "Noticias"}, {"i": 1, "kind": "Hyperlink", "name": "Portada"}]}
    decided = computer_use.decide_step(
        _Scroller(), objective=objective, goal=goal, application="Google Chrome", success_check=None, view=view,
        history=[_scroll(1), _scroll(2), _scroll(3)], budget_left=10, application_names=["Google Chrome"])
    assert decided.get("code") != "limit:long_list", decided


def test_c1_a_list_the_wheel_turns_is_the_long_list_unless_counted() -> None:
    view = {"window": {"title": "Configuración", "process": "SystemSettings"}, "controls": [
        {"i": 0, "kind": "List", "name": "Aplicaciones instaladas"}, {"i": 1, "kind": "Document", "name": "Ayuda"}]}
    looks = computer_use._looks_in_a_list
    assert looks("buscá el bloc de notas", "elegir bloc de notas", view, {"index": 0})
    # Estabilización L4: a «mostrar X» sub-goal says the limit in its own step (cu_navigation._reveal_step, the test
    # below); this check is only the wheel a step turns over a list of the view.
    assert looks("bajá en la lista hasta el bloc de notas", "mostrar bloc de notas", view, {"index": 0})
    assert not looks("bajá en la lista hasta el bloc de notas", "mostrar bloc de notas", view, {})
    # Contracases: a document turned, no list, a counted scroll.
    assert not looks("bajá en la ayuda", "leer la ayuda", view, {"index": 1})
    assert not looks("bajá", "bajar", view, {})
    assert not looks("bajá 4 veces en la lista", "elegir bloc de notas", view, {"index": 0})


def test_the_engine_stops_on_the_long_list_and_a_short_one_is_still_scrolled() -> None:
    stopped = _decide([_scroll(1, ok=False, label="bloc de notas"), _scroll(2), _scroll(3), _scroll(4)])
    assert stopped["operation"] == "none" and stopped["code"] == "limit:long_list"
    going = _decide([_scroll(1, ok=False, label="bloc de notas"), _scroll(2)])
    assert going["operation"] == "input.scroll"
    assert not limits.long_list_reached([_scroll(1), _scroll(2), _scroll(3, changed=False)])


# ------------------------------------------------------------------------------------------ the floor (H5)

def _chain(stop: str, *subgoals: dict, steps: list[dict] | None = None) -> dict:
    return {"goal": "; luego ".join(item["goal"] for item in subgoals), "reached": False, "stoppedBy": stop,
            "steps": steps or [], "subgoals": list(subgoals)}


def test_h5_the_limit_says_the_radio_it_switched_off_before() -> None:
    observed = _chain(
        "computer_use_limit_context_menu",
        {"goal": "ir a bluetooth y dispositivos", "application": "Configuración", "reached": True,
         "arrivedAs": "Bluetooth y dispositivos", "acted": True},
        {"goal": "desactivar bluetooth", "application": "Configuración", "reached": True, "acted": True},
        {"goal": "abrir el menu contextual de mouse", "application": "Configuración", "reached": False},
        steps=[{"step": 1, "operation": "input.visible.click", "ok": True, "name": "Bluetooth", "kind": "Button",
                "subgoal": 1}],
    )
    final = cu_finals.floor_first(observed, english=False, succeeded=False)
    # Review of L2, C4: the sub-goal told by its kind, the name as the window writes it, never quoted as said inside.
    assert final.startswith("Llegué a «Bluetooth y dispositivos» y desactivé «Bluetooth», pero no puedo hacer lo que sigue")
    assert final.endswith("los menús del clic derecho no entran en lo que veo.")


def test_h5_the_limit_says_the_message_it_sent_before() -> None:
    observed = _chain(
        "computer_use_limit_format",
        {"goal": "escribir hola", "application": "Discord", "reached": True, "acted": True},
        {"goal": "enviar", "application": "Discord", "reached": True, "acted": True},
        {"goal": "ponelo en negrita", "application": "Discord", "reached": False},
        steps=[{"step": 1, "operation": "input.text.type", "ok": True, "text": "hola", "subgoal": 0},
               {"step": 2, "operation": "input.key.press", "ok": True, "key": "enter", "subgoal": 1}],
    )
    final = cu_finals.floor_first(observed, english=False, succeeded=False)
    assert final.startswith("Escribí «hola» y lo envié, pero no puedo hacer lo que sigue: ")
    english = cu_finals.floor_first(observed, english=True, succeeded=False)
    assert english.startswith("I typed «hola» and I sent it, but I can't do the rest: ")


def test_a_limit_with_nothing_done_before_it_is_said_short() -> None:
    observed = _chain("computer_use_limit_format",
                      {"goal": "Insert a table", "application": "Word", "reached": False})
    assert cu_finals.floor_first(observed, english=False, succeeded=False) == (
        "No puedo hacer eso: los botones de formato de la cinta (negrita, tablas y similares) no entran en lo que veo.")


def test_n5_keeps_its_sentence_and_a_chain_out_of_steps_is_the_floors() -> None:
    n5 = _chain("computer_use_limit_device",
                {"goal": "ir a red e internet", "application": "Configuración", "reached": True,
                 "arrivedAs": "Red e Internet", "acted": True},
                {"goal": "ir a wi-fi", "application": "Configuración", "reached": False})
    n5["absentDevice"] = "wifi"
    assert cu_finals.floor_first(n5, english=False, succeeded=False) == (
        "Llegué a «Red e Internet», pero no puedo ir a «Wi-Fi»: este equipo no tiene adaptador Wi-Fi.")
    long_task = _chain("computer_use_budget_exhausted",
                       {"goal": "ir a c:\\windows\\system32", "application": "Explorador de archivos", "reached": False})
    assert cu_finals.limit_final(long_task, english=False).startswith("No pude terminarlo: ")


# ------------------------------------------------------------------------------------------ «¿En cuál ventana?» (H1, H8d)

def _turn(*operations: str, kind: str = "action") -> dict:
    return {"type": "turn.result", "id": "w", "kind": kind, "operation": operations[0] if operations else None,
            "intentOperations": list(operations), "effectOperations": list(operations), "question": "", "reply": "",
            "objective": ""}


def _ask(said: str, turn: dict, history: list[dict] | None = None) -> dict:
    turns = [*(history or []), {"role": "user", "content": said}]
    return engine_handoff._asks_which_window(turn, {"id": "w", "text": said, "history": turns}, APPS)


@pytest.mark.parametrize(
    "said",
    ["guarda esto", "guardá esto", "save this", "please save this",
     "guardá esto como baxy-nota1.txt en Documentos, en la carpeta baxy-prueba-v3"],
)
def test_save_this_with_no_window_and_no_typed_route_is_asked_about(said: str) -> None:
    for turn in (_turn("mission.computer.use"), _turn("input.key.press"), _turn(kind="clarify")):
        asked = _ask(said, turn)
        assert asked["kind"] == "clarify" and asked["question"] in {"¿En cuál ventana?", "Which window?"}, said


@pytest.mark.parametrize(
    ("said", "operations"),
    [
        ("guardá esto en tu memoria: mi color favorito es el azul", ("memory.save",)),
        ("save this number to my contacts: 555 1234", ("contacts.add",)),
        ("guarda esto en el portapapeles", ("clipboard.set",)),
        ("save this song to my liked songs", ("media.library.save",)),
        ("guarda esto: mañana tengo dentista a las 5", ("note.create",)),
        ("save this: my wifi password is 1234", ("memory.save",)),
        ("guarda esto en mi agenda: reunión el lunes", ("notification.schedule",)),
        ("guarda esto en favoritos", ("browser.control",)),
        ("save this page as PDF", ("browser.control",)),
        ("guarda esto en un archivo de texto", ("filesystem.write.text",)),
        ("guarda esto", ("memory.save",)),
    ],
)
def test_h1_a_typed_route_keeps_its_turn(said: str, operations: tuple[str, ...]) -> None:
    turn = _turn(*operations)
    assert _ask(said, turn) is turn


@pytest.mark.parametrize(
    "said",
    ["guardá esto en tu memoria: mi color favorito es el azul", "save this number to my contacts: 555 1234",
     "guarda esto en el portapapeles", "save this song to my liked songs", "guarda esto: mañana tengo dentista a las 5",
     "save this: my wifi password is 1234", "guarda esto en mi agenda: reunión el lunes", "guarda esto en favoritos",
     "save this page as PDF", "guarda esto en un archivo de texto", "guardá esto en esta ventana",
     "en el Bloc de notas guardá esto", "guardalo", "guardá la receta"],
)
def test_h1_the_reading_asks_only_for_a_save_of_what_is_shown(said: str) -> None:
    assert not limits.asks_which_window(said, APPS)


def test_after_a_reply_of_baxys_or_with_the_application_in_the_conversation_nothing_is_asked() -> None:
    turn = _turn("mission.computer.use")
    replied = [{"role": "user", "content": "escribime un poema"}, {"role": "assistant", "content": "El mar…"}]
    assert _ask("guardá esto", turn, replied) is turn
    noted = [{"role": "user", "content": "abrí el bloc de notas y escribí hola"}, {"role": "assistant", "content": "Listo."}]
    assert _ask("guardá esto", turn, noted) is turn


def test_h8d_the_answer_that_names_the_window_follows_the_request() -> None:
    asked = [{"role": "user", "content": "guardá esto"}, {"role": "assistant", "content": "¿En cuál ventana?"}]
    turn = _turn(kind="clarify")
    handed = _ask("en el Bloc de notas", turn, asked)
    assert handed["effectOperations"] == ["mission.computer.use"]
    assert handed["objective"] == "en Bloc de notas, guardá esto"
    assert missions.mission_destination(handed["objective"], APPS) == "Bloc de notas"
    pointed = _ask("en esta ventana", turn, asked)
    assert pointed["objective"] == "en esta ventana, guardá esto"
    # Anything else goes its own way (a «no», a new request), never M67's write of the question.
    assert _ask("no", turn, asked) is turn
    assert _ask("poné música de Queen en Spotify", turn, asked) is turn


@pytest.mark.parametrize(
    ("answer", "objective"),
    [
        # Review of L2, C5: the application's name or alias alone, the window in front said bare.
        ("Notepad", "en Bloc de notas, guardá esto"),
        ("Bloc de notas", "en Bloc de notas, guardá esto"),
        ("esta ventana", "en esta ventana, guardá esto"),
        ("en esta", "en esta ventana, guardá esto"),
        ("esta", "en esta ventana, guardá esto"),
    ],
)
def test_c5_the_bare_answer_names_the_window(answer: str, objective: str) -> None:
    asked = [{"role": "user", "content": "guardá esto"}, {"role": "assistant", "content": "¿En cuál ventana?"}]
    handed = _ask(answer, _turn(kind="clarify"), asked)
    assert handed.get("objective") == objective, (answer, handed)


def test_c5_the_framed_request_keeps_the_conversations_language() -> None:
    asked = [{"role": "user", "content": "save this"}, {"role": "assistant", "content": "Which window?"}]
    turn = _turn(kind="clarify")
    assert _ask("Notepad", turn, asked)["objective"] == "in Bloc de notas, save this"
    assert _ask("this one", turn, asked)["objective"] == "in this window, save this"
    assert missions.mission_destination("in Bloc de notas, save this", APPS) == "Bloc de notas"
    # A new request is still no answer, in either language.
    assert _ask("play Queen on Spotify", turn, asked) is turn
    assert _ask("no", turn, asked) is turn


def test_the_case_of_save_this_is_written() -> None:
    import json

    said = (_CASES / "t-guarda-1.turns").read_text(encoding="utf-8").strip()
    assert limits.asks_which_window(said, APPS)
    states = json.loads((_CASES.parent / "estado" / "casos.json").read_text(encoding="utf-8"))["casos"]
    assert "t-guarda-1" in states


# ------------------------------------------------------------------------------------------ C2: one reading of the act

@pytest.mark.parametrize(
    "said",
    [
        "en Word poné el título en negrita",
        "en Paint poné el texto en negrita",
        "en Word activá la negrita",
        "en Word hacé el título negrita",
        "en word poné el titulo en negrita y centralo",  # uso real t2-c10
        "en el word que tengo abierto ponle negrita al texto que tengo seleccionado",  # uso real t4-c13
    ],
)
def test_c2_the_readers_own_rewrite_of_a_format_is_the_limit(said: str) -> None:
    assert limits.act_limit(said) == "format"
    mission = missions.mission_request(said, APPS)
    if mission is not None:
        marked = limits.with_declared_limits(mission.arguments())
        steps = marked.get("steps") or []
        assert steps and steps[-1].get("limit") == "format", (said, steps)
        # What comes before the limit never does the format itself: the final cannot contradict it.
        assert all("negrita" not in str(step.get("goal")) for step in steps[:-1]), steps


@pytest.mark.parametrize(
    "said",
    [
        # C6 (decided by the coordinator): the person gives the shortcut; the engine presses the key, no limit.
        "en Word seleccioná todo y poné negrita con Ctrl+B",
        "en Word poné el título en negrita con control+b",
        "in Word select all and make it bold with Ctrl+B",
        "en Word poné la cursiva apretando control i",
    ],
)
def test_c6_a_format_said_with_its_shortcut_is_no_limit(said: str) -> None:
    assert limits.act_limit(said) is None
    mission = missions.mission_request(said, APPS)
    if mission is not None:
        marked = limits.with_declared_limits(mission.arguments())
        assert all(not step.get("limit") for step in marked.get("steps") or []), (said, marked)


def test_c6_a_control_that_is_no_shortcut_keeps_the_limit() -> None:
    # «el panel de control y …»: «control» followed by a joint is no key.
    assert limits.act_limit("abrí el panel de control y poné el título en negrita") == "format"
    assert limits.act_limit("en Word poné el título en negrita") == "format"


def test_c2_the_final_never_says_it_did_the_format_it_refuses() -> None:
    observed = _chain(
        "computer_use_limit_format",
        {"goal": "seleccionar titulo", "application": "Word", "reached": True, "acted": True},
        {"goal": "activar negrita", "application": "Word", "reached": False},
        steps=[{"step": 1, "operation": "input.visible.click", "ok": True, "label": "Título", "name": "Título",
                "subgoal": 0}],
    )
    final = cu_finals.floor_first(observed, english=False, succeeded=False)
    assert "negrita" not in final.split("pero")[0], final


def test_c3_a_sub_goal_reached_with_no_act_is_never_told_as_done() -> None:
    # The radio was already on: «activar bluetooth» held on the first look, nothing was pressed.
    observed = _chain(
        "computer_use_limit_context_menu",
        {"goal": "activar bluetooth", "application": "Configuración", "reached": True, "acted": False},
        {"goal": "abrir el menu contextual de mouse", "application": "Configuración", "reached": False},
    )
    final = cu_finals.floor_first(observed, english=False, succeeded=False)
    assert final == "No puedo hacer eso: los menús del clic derecho no entran en lo que veo."
    # Contracase: the same sub-goal with its act is told.
    observed["subgoals"][0]["acted"] = True
    assert "bluetooth" in cu_finals.floor_first(observed, english=False, succeeded=False)


@pytest.mark.parametrize(("goal", "spanish", "english"), [
    # Review of L2, C4: the sub-goals the floor knows how to say, in the conversation's language.
    ("creá un documento en blanco", "Creé el archivo nuevo", "I created the new file"),
    ("crear documento en blanco", "Creé el archivo nuevo", "I created the new file"),
    (r"poner nombre de archivo en D:\Perfil\Documentos\informe.docx", "Puse «informe.docx» en «nombre de archivo»",
     "I put «informe.docx» in «nombre de archivo»"),
    ("seleccionar titulo", "Elegí «Título»", "I picked «Título»"),
    ("hacer clic en Guardar", "Hice clic en «Guardar»", "I clicked «Guardar»"),
    ("buscar lofi", "Busqué «lofi»", "I searched for «lofi»"),
    ("activar modo oscuro", "Activé «modo oscuro»", "I turned on «modo oscuro»"),
])
def test_c4_a_sub_goal_done_is_told_by_its_kind(goal: str, spanish: str, english: str) -> None:
    observed = _chain(
        "computer_use_limit_format",
        {"goal": goal, "application": "Word", "reached": True, "acted": True},
        {"goal": "activar negrita", "application": "Word", "reached": False},
        steps=[{"step": 1, "operation": "input.visible.click", "ok": True, "name": "Título", "subgoal": 0}],
    )
    final = cu_finals.floor_first(observed, english=False, succeeded=False)
    assert final.startswith(spanish + ", pero no puedo hacer lo que sigue: "), final
    told = cu_finals.floor_first(observed, english=True, succeeded=False)
    assert told.startswith(english + ", but I can't do the rest: "), told


def test_c4_a_sub_goal_of_no_known_kind_is_quoted_once_and_never_in_another_language() -> None:
    observed = _chain(
        "computer_use_limit_format",
        {"goal": "ordenar la tabla por fecha", "application": "Excel", "reached": True, "acted": True},
        {"goal": "agrupar por mes", "application": "Excel", "reached": True, "acted": True},
        {"goal": "insertar una tabla dinamica", "application": "Excel", "reached": False},
    )
    final = cu_finals.floor_first(observed, english=False, succeeded=False)
    assert final.startswith("Hice «ordenar la tabla por fecha» y «agrupar por mes», pero no puedo hacer lo que sigue"), final
    assert final.count("ice") == 1, final
    told = cu_finals.floor_first(observed, english=True, succeeded=False)
    assert told.startswith("I did the steps before it, but I can't do the rest: "), told
    assert "ordenar" not in told, told
