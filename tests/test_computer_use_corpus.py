"""Computer use v2 (owner 2026-10-07): órdenes de voz que operan una aplicación por su interfaz, como lo haría una
persona, en español (rioplatense y neutro) y en inglés, de una cláusula o encadenadas de 2 a 5. Cada una tiene que
leerse como una misión del motor con una comprobación por sub-objetivo; lo que el catálogo tipado ya cubre entero
sigue su operación (D21) y lo que el motor nunca intenta solo (borrar, pagar, preguntas, prohibiciones) no es misión.

Medido 2026-10-07 sobre las 134 primeras órdenes: antes del lector v2, 58 misiones comprobadas (66 con un
sub-objetivo sin comprobación, 5 sin leer, 5 mal partidas); después, 134.
"""

from __future__ import annotations

import re
from pathlib import Path

from baxy_mind import computer_use
from baxy_mind.effect_intent import resolve_explicit_effects
from baxy_mind.semantic import missions

ROOT = Path(__file__).resolve().parents[1]

APPS = (
    "Steam", "Discord", "Google Chrome", "Calculadora", "Configuración", "Bloc de notas", "Paint", "Spotify",
    "WhatsApp", "Explorador de archivos", "Word", "Excel", "Opera GX Browser", "Microsoft Edge", "VLC media player",
    "Reloj", "Outlook", "Telegram", "Visual Studio Code", "OBS Studio", "Panel de control", "Microsoft Teams", "Zoom",
)


def _catalog_operations() -> frozenset[str]:
    source = (ROOT / "src/Baxy.Kernel/Operations/ProductCatalog.cs").read_text(encoding="utf-8")
    return frozenset(re.findall(r'Descriptor\(\s*"([a-z0-9.]+)"', source))


OPERATIONS = _catalog_operations()

# Órdenes que son misiones del motor: (frase, número de sub-objetivos esperado).
MISSIONS: tuple[tuple[str, int], ...] = (
    # --- rioplatense
    ("abrí Spotify, buscá Bad Bunny y poné la primera", 2),
    ("en Discord andá a general y escribí hola", 2),
    ("en Paint elegí el lápiz y después el color rojo", 2),
    ("abrí la calculadora y calculá 12 por 7", 1),
    ("en Configuración andá a Bluetooth y después a Pantalla", 2),
    ("abrí Steam y andá a la biblioteca", 1),
    ("en Steam buscá Hades", 1),
    ("en Spotify buscá Duki", 1),
    ("abrí el bloc de notas y escribí lista del súper", 1),
    ("en Paint elegí el balde de pintura", 1),
    ("en Paint seleccioná el color azul", 1),
    ("en Word escribí Querido Juan", 1),
    ("en el Explorador andá a Descargas", 1),
    ("en el Explorador de archivos creá una carpeta nueva llamada fotos viejas", 1),
    ("en el Explorador renombrá la carpeta Nueva carpeta a proyectos", 1),
    ("abrí el Explorador de archivos, andá al Escritorio y creá una carpeta que se llame tareas", 2),
    ("en Configuración andá a Sistema, después a Pantalla y después a Escala", 3),
    ("en Spotify andá a Tu biblioteca", 1),
    ("en Discord andá al servidor de amigos y después al canal música", 2),
    ("en Steam andá a la tienda y buscá Hollow Knight", 2),
    ("en VLC apretá espacio", 1),
    ("en la calculadora calculá 345 más 12", 1),
    ("abrí la calculadora y multiplicá 8 por 9", 1),
    ("en Teams andá a Chat", 1),
    ("en Outlook andá a Enviados", 1),
    ("en el Reloj andá a Cronómetro y apretá iniciar", 2),
    ("en el Reloj andá a Temporizador", 1),
    ("en Excel escribí 100 y apretá enter", 2),
    ("en Steam andá a la biblioteca y después a descargas", 2),
    ("en Discord buscá a Ron92", 1),
    ("en Spotify buscá lo-fi y poné el primer resultado", 2),
    ("abrí Paint y elegí el rectángulo", 1),
    ("en el Panel de control abrí Programas", 1),
    ("en Configuración buscá Bluetooth", 1),
    ("en el Explorador buscá informe.pdf", 1),
    ("en el Explorador abrí la carpeta Imágenes", 1),
    ("abrí el Explorador y entrá a Música", 1),
    ("en el bloc de notas apretá control z", 1),
    ("en Discord andá a general, escribí hola y mandalo", 3),
    ("en Discord andá a general. Después escribí buenas", 2),
    ("en Paint hacé clic en Texto", 1),
    ("en Steam tocá Comunidad", 1),
    ("en Paint elegí la goma", 1),
    ("en OBS apretá Iniciar grabación", 1),
    ("en Zoom tocá unirse", 1),
    ("en Spotify buscá Bad Bunny, después andá a Canciones", 2),
    ("en Visual Studio Code creá un archivo llamado notas.txt", 1),
    ("en Configuración entrá a Bluetooth y activalo", 2),
    ("en Steam andá a la biblioteca, buscá Portal y abrilo", 3),
    ("abrí Spotify, buscá a Duki y ponelo", 2),
    ("en el Explorador andá a Documentos, creá una carpeta llamada test y abrila", 3),
    ("en Steam buscá Hades y abrilo", 2),
    ("abrí Paint y después elegí el lápiz", 1),
    ("en Configuración andá a Red e Internet", 1),
    ("en la calculadora dividí 100 entre 4", 1),
    ("en Discord entrá al canal de voz General", 1),
    ("en Paint elegí el pincel, después el color verde y después la goma", 3),
    ("en Telegram buscá a Juan", 1),
    ("en Word hacé clic en Insertar y después en Tabla", 2),
    ("en Spotify andá a Buscar y escribí Coldplay", 2),
    ("en el Explorador andá a Imágenes y después creá una carpeta llamada vacaciones", 2),
    ("en Discord andá a general y después a memes", 2),
    ("abrí Steam, andá a la tienda, buscá Celeste y abrilo", 3),
    # --- neutro
    ("Abre Spotify, busca Shakira y reproduce la primera canción", 2),
    ("En Discord ve al canal general y escribe hola a todos", 2),
    ("En Paint selecciona el lápiz y luego el color negro", 2),
    ("Abre la calculadora y calcula 25 por 4", 1),
    ("En Configuración ve a Bluetooth y luego a Pantalla", 2),
    ("Abre Steam, ve a la tienda y busca Celeste", 2),
    ("En Word escribe Hola mundo", 1),
    ("En el Explorador crea una nueva carpeta llamada viajes", 1),
    ("En Configuración busca sonido", 1),
    ("En Paint elige el color amarillo", 1),
    ("En el bloc de notas escribe recordatorio y luego presiona enter", 2),
    ("En Steam ve a la biblioteca y luego busca Portal 2", 2),
    ("Abre el Explorador de archivos y ve a Imágenes", 1),
    ("En Spotify ve a Inicio y luego a Buscar", 2),
    ("Abre Configuración y ve a Personalización, luego a Colores", 2),
    ("En el Explorador cambia el nombre de la carpeta borrador a final", 1),
    ("En Telegram abre el chat con Juan", 1),
    ("En Outlook ve a la bandeja de entrada y luego a Borradores", 2),
    ("Abre Paint, selecciona el pincel y después el color azul", 2),
    ("En Excel escribe ventas y presiona tab", 2),
    ("En la calculadora multiplica 15 por 3", 1),
    ("En Steam haz clic en Biblioteca", 1),
    ("En el Explorador de archivos busca presupuesto", 1),
    ("En Spotify busca Queen y reproduce la primera", 2),
    # --- inglés
    ("open Spotify, search for Bad Bunny and play the first one", 2),
    ("in Discord go to general and type hello", 2),
    ("in Paint pick the pencil and then the red color", 2),
    ("open the calculator and calculate 12 times 7", 1),
    ("in Settings go to Bluetooth and then to Display", 2),
    ("open Steam and go to the library", 1),
    ("in Steam search for Hades", 1),
    ("in Notepad type shopping list", 1),
    ("in Word type Dear John", 1),
    ("in Paint select the eraser", 1),
    ("in File Explorer go to Downloads", 1),
    ("in Explorer rename the folder New folder to projects", 1),
    ("open File Explorer, go to Desktop and create a new folder called tasks", 2),
    ("in Spotify search for Queen and play the first result", 2),
    ("in Discord go to the music channel then type hi everyone", 2),
    ("in Steam go to the store and then search for Hollow Knight", 2),
    ("in the calculator compute 345 plus 12", 1),
    ("in Settings search for sound", 1),
    ("in Chrome switch to the Gmail tab", 1),
    ("in Teams go to Calendar", 1),
    ("in Outlook go to Sent Items", 1),
    ("in Paint click Text", 1),
    ("in Notepad type hello world then press enter", 2),
    ("in Discord search for Ron92", 1),
    ("open Paint, choose the rectangle, then pick blue", 2),
    ("in Telegram open the chat with John", 1),
    ("in Excel type 100 and press enter", 2),
    ("in Steam go to library, then downloads", 2),
    ("in Spotify go to Your Library", 1),
    ("in File Explorer open the Pictures folder", 1),
    ("in Settings go to System, then Display, then Scale", 3),
    ("in VLC press space", 1),
    ("in Spotify search for lofi beats then play it", 2),
    ("in Explorer make a new folder named photos", 1),
    ("in Zoom click Join", 1),
    ("open Discord, go to general, type hello and send it", 3),
    ("in Steam click Community", 1),
    ("in Paint choose the fill tool", 1),
    ("in Explorer create a folder called reports and open it", 2),
    ("in Steam search for Portal and open it", 2),
    ("in Word click Insert and then Table", 2),
    ("open the calculator and multiply 6 by 7", 1),
    ("in Spotify go to Search and type Coldplay", 2),
    # --- bench en vivo del coordinador (2026-10-07)
    ("en la calculadora calculá 12*12, copiá el resultado y pegalo en el Bloc de notas", 3),
    ("en Opera abrí una pestaña nueva, andá a es.wikipedia.org, buscá Ñuñoa y abrí la sección Historia", 4),
    ("abrí Configuración, andá a Personalización, entrá a Colores y decime si el modo es claro u oscuro", 2),
    # --- segunda tanda, escrita antes de tocar el lector para ella: 22/28 a la primera
    ("en Spotify buscame a Tini y reproducí la primera canción", 2),
    ("abrí Discord y buscá el canal anuncios", 1),
    ("en el explorador de archivos, entrá a Descargas y después creá una carpeta que se llame juegos", 2),
    ("en Paint, agarrá el lápiz y después el color violeta", 2),
    ("en la calculadora hacé 9 por 9", 1),
    ("open Notepad and type buy milk then press enter", 2),
    ("in Spotify look up Daft Punk and play the first song", 2),
    ("in File Explorer create a new folder named Invoices 2026", 1),
    ("en Steam andá a la biblioteca y buscá Stardew Valley y abrilo", 3),
    ("en Configuración andá a Bluetooth y dispositivos y activá el Bluetooth", 2),
    ("en Word escribí Estimado cliente y después apretá enter", 2),
    ("en Chrome abrí una nueva pestaña y andá a youtube.com", 2),
    ("en Opera andá a github.com y buscá baxy", 2),
    ("abrí el bloc de notas, escribí hola mundo, seleccioná todo y copialo", 3),
    ("in Paint choose the brush, then the green color, then the eraser", 3),
    ("en el Explorador renombrá el archivo notas.txt como apuntes.txt", 1),
    ("en Discord andá al servidor Amigos, después al canal general y escribí qué onda", 3),
    ("in Settings go to Personalization and then Colors and tell me if dark mode is on", 2),
    ("en Telegram buscá a Mamá y abrí el chat", 2),
    ("en Excel hacé clic en Insertar y después en Gráfico", 2),
    ("en Spotify andá a tu biblioteca y poné la primera playlist", 2),
    ("en Configuración buscá modo oscuro y abrilo", 2),
    ("in the calculator divide 144 by 12", 1),
    ("en VLC tocá Reproducir", 1),
    ("en Outlook andá a Bandeja de entrada y buscá factura", 2),
    ("abrí Paint, elegí el rectángulo y después el azul", 2),
    ("in Steam open the library and search for Terraria", 2),
    ("en el explorador andá a Documentos, creá la carpeta Proyectos y entrá", 3),
)

# Lo que el catálogo tipado ya hace entero sigue su operación (D21).
TYPED: tuple[tuple[str, tuple[str, ...]], ...] = (
    # The typed folder route covers going to a known folder and creating one in it (D21; v2 plan fix).
    ("en el Explorador de archivos andá a Documentos y creá una carpeta llamada baxy-prueba", ("filesystem.folder.open", "filesystem.create.directory")),
    ("En el explorador de archivos ve a Documentos y crea una carpeta llamada informes", ("filesystem.folder.open", "filesystem.create.directory")),
    ("in File Explorer go to Documents and create a folder named baxy-test", ("filesystem.folder.open", "filesystem.create.directory")),
    ("go to Documents in File Explorer and create a folder called drafts", ("filesystem.folder.open", "filesystem.create.directory")),
    ("abrí Configuración y activá el modo avión", ("system.settings.set",)),
    ("busca gatos en google", ("browser.navigate",)),
)

# Lo que el motor nunca intenta solo: no es misión.
NEVER: tuple[str, ...] = (
    "en el Explorador borrá la carpeta fotos",
    "en Steam comprá Hades",
    "in Explorer delete the folder photos",
    "¿en Spotify podés buscar a Duki?",
    "no abras Steam",
    "en Discord no escribas nada",
    "en Steam desinstalá Hades",
    "en Steam buscá Hades y compralo",
)


def _route(text: str) -> tuple[str, ...] | None:
    intent = resolve_explicit_effects(text, OPERATIONS, application_names=APPS)
    return intent.operations if intent is not None else None


def _verdict(text: str, count: int) -> str:
    mission = missions.mission_request(text, APPS)
    if mission is None:
        return "no_read"
    checks = [step.success_check for step in mission.steps] or [mission.success_check]
    if any(check is None for check in checks):
        return "no_check"
    if len(checks) != count:
        return "steps"
    route = _route(text)
    if route != ("mission.computer.use",):
        return f"route:{','.join(route or ('none',))}"
    return "ok"


def measure() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for text, count in MISSIONS:
        found.setdefault(_verdict(text, count), []).append(text)
    return found


def test_the_corpus_is_large_and_bilingual() -> None:
    assert len(MISSIONS) >= 120
    assert len({text for text, _ in MISSIONS}) == len(MISSIONS)
    assert sum(1 for text, _ in MISSIONS if re.match(r"(?i)(?:in|open|go)\b", text)) >= 40


def test_voice_orders_that_operate_an_app_are_checked_missions() -> None:
    found = measure()
    failing = {verdict: texts for verdict, texts in found.items() if verdict != "ok"}
    assert len(found.get("ok", ())) >= len(MISSIONS) - 0, failing


def test_the_catalog_keeps_what_it_covers_entirely() -> None:
    for text, route in TYPED:
        assert _route(text) == route, text


def test_what_the_engine_never_tries_is_not_a_mission() -> None:
    for text in NEVER:
        assert _route(text) != ("mission.computer.use",), text
        assert not missions.engine_can_try(text, APPS), text
    # An order no reader knows is no part of the place before it: the chain is left to the decider.
    assert _route("abre Steam, ve a la biblioteca y dibujá a Batman") != ("mission.computer.use",)
    assert _route("en Discord buscá a Cotele y llamalo") != ("mission.computer.use",)


def _steps(text: str) -> list[tuple[str | None, str, str | None]]:
    mission = missions.mission_request(text, APPS)
    assert mission is not None, text
    return [(step.application, step.goal, step.success_check) for step in mission.steps]


def test_copy_and_paste_switch_to_the_application_the_clause_names() -> None:
    steps = _steps("en la calculadora calculá 12*12, copiá el resultado y pegalo en el Bloc de notas")
    assert [(application, goal) for application, goal, _ in steps] == [
        ("Calculadora", "calcular 12*12"), ("Calculadora", "apretar ctrl c"), ("Bloc de notas", "apretar ctrl v"),
    ]
    assert steps[1][2].split("|")[0] == "stepDone:input.key.press:ctrl_c"
    assert steps[2][2].split("|")[0] == "stepDone:input.key.press:ctrl_v"


def test_a_new_tab_an_address_a_search_and_a_section_of_the_page() -> None:
    steps = _steps(
        "en Opera abrí una pestaña nueva, andá a es.wikipedia.org, buscá Ñuñoa y abrí la sección Historia"
    )
    assert [goal for _, goal, _ in steps] == [
        "apretar ctrl t", "ir a la direccion es.wikipedia.org", "buscar Ñuñoa", "ir a historia",
    ]
    assert steps[0][2] == "stepDone:input.key.press:ctrl_t"
    assert steps[1][2] == "title:wikipedia"
    # The page titled with the name counts once this sub-goal submitted the search (a title that said it already does
    # not).
    assert steps[2][2].split("|")[:2] == [
        "title:nunoa&stepDone:input.key.press:enter", "title:nunoa&stepDone:input.visible.click:nunoa",
    ]
    assert "stepDone:input.visible.click:historia" in steps[3][2].split("|")


def test_a_closing_question_is_split_off_and_answered_by_the_final() -> None:
    said = "abrí Configuración, andá a Personalización, entrá a Colores y decime si el modo es claro u oscuro"
    mission = missions.mission_request(said, APPS)
    assert [step.goal for step in mission.steps] == ["ir a personalizacion", "ir a colores"]
    assert mission.goal.endswith(missions.QUESTION_MARK + "decime si el modo es claro u oscuro")
    # A single clause with a question stays a single mission (its own budget, not a chain link's thirty seconds):
    # the question rides on the goal, and the loop's steps read the goal without it.
    single = missions.mission_request("en Configuración andá a Colores y decime si el modo es claro u oscuro", APPS)
    assert single.steps == () and "steps" not in single.arguments()
    assert single.goal == "ir a colores" + missions.QUESTION_MARK + "decime si el modo es claro u oscuro"
    assert single.success_check.startswith("control:colores:selected|")
    seen = computer_use.project_seen({"goal": mission.goal, "reached": True, "steps": []}, "es")
    assert seen["goal"] == "ir a personalizacion; luego ir a colores"
    assert seen["question"] == "decime si el modo es claro u oscuro"
    assert computer_use.compose_instruction(seen, "es").startswith("seen.question")
    # «escribí decime si venís» types the words: no joiner, no question.
    assert missions.mission_request("en el bloc de notas escribí decime si venís", APPS).goal == "escribir decime si venís"


def test_created_and_renamed_items_keep_their_names_as_said() -> None:
    created = missions.mission_request("en el Explorador creá una carpeta llamada Fotos Viejas", APPS)
    assert (created.goal, created.success_check) == (
        "crear carpeta Fotos Viejas", "control:=fotos viejas&stepDone:input.text.type:fotos viejas",
    )
    renamed = missions.mission_request("en el Explorador renombrá la carpeta Borrador a Final", APPS)
    assert (renamed.goal, renamed.success_check) == ("renombrar Borrador a Final", "control:=final&stepDone:input.text.type:final")


_VIEW_SEARCH = {
    "window": {"title": "Steam", "focused": None},
    "controls": [{"i": 0, "kind": "Edit", "name": "Buscar en la tienda"}, {"i": 1, "kind": "Button", "name": "Tienda"}],
    "text": {},
}


def test_searching_types_in_the_windows_search_then_submits() -> None:
    first = computer_use.deterministic_step(goal="buscar Hades", view=_VIEW_SEARCH, history=[])
    assert first["operation"] == "input.visible.click" and first["arguments"]["label"] == "Buscar en la tienda"
    focused = {**_VIEW_SEARCH, "window": {"title": "Steam", "focused": {"kind": "Edit", "name": "Buscar en la tienda"}}}
    clicked = [{"step": 1, "operation": "input.visible.click", "label": "Buscar en la tienda", "ok": True}]
    assert computer_use.deterministic_step(goal="buscar Hades", view=focused, history=clicked)["arguments"] == {"text": "Hades"}
    typed = [*clicked, {"step": 2, "operation": "input.text.type", "text": "Hades", "ok": True}]
    assert computer_use.deterministic_step(goal="buscar Hades", view=focused, history=typed)["arguments"] == {"key": "enter"}


def test_an_address_is_the_bar_the_address_delete_and_enter() -> None:
    # Delete drops the page of the history the bar completes the address with (measured on Opera: Enter went to
    # «…/wiki/Curicó»); ctrl_l put the keyboard on the bar, so it erases characters there and is not asked.
    view = {"window": {"title": "Opera", "focused": {"kind": "Edit", "name": "Campo de dirección", "value": ""}}, "controls": [], "text": {}}
    history: list[dict] = []
    for wanted in (
        {"key": "ctrl_l"}, {"text": "es.wikipedia.org"}, {"key": "delete", "target": "text_field"}, {"key": "enter"},
    ):
        step = computer_use.deterministic_step(goal="ir a la direccion es.wikipedia.org", view=view, history=history)
        assert step["arguments"] == wanted
        history.append({"step": len(history) + 1, "operation": step["operation"], "ok": True, **wanted})
    assert computer_use.deterministic_step(goal="ir a la direccion es.wikipedia.org", view=view, history=history) is None


def test_choosing_clicks_the_tool_until_it_shows_selected() -> None:
    view = {"window": {"title": "Paint"}, "controls": [
        {"i": 0, "kind": "RadioButton", "name": "Lápiz", "state": ""}, {"i": 1, "kind": "ListItem", "name": "Rojo", "state": ""},
    ], "text": {}}
    assert computer_use.deterministic_step(goal="seleccionar lapiz", view=view, history=[])["arguments"] == {"label": "Lápiz", "index": 0}
    # The English name of the colour finds the Spanish control.
    assert computer_use.deterministic_step(goal="seleccionar red", view=view, history=[])["arguments"]["label"] == "Rojo"
    chosen = {**view, "controls": [{"i": 0, "kind": "RadioButton", "name": "Lápiz", "state": "on"}]}
    assert computer_use.deterministic_step(goal="seleccionar lapiz", view=chosen, history=[]) is None


def test_every_mission_of_the_corpus_grounds_against_the_catalog_schema() -> None:
    from baxy_mind.__main__ import _ground_explicit_arguments
    from test_computer_use import CHAIN_SCHEMA

    ungrounded = [
        text for text, _ in MISSIONS
        if _ground_explicit_arguments("mission.computer.use", text, CHAIN_SCHEMA, APPS) is None
    ]
    assert ungrounded == []


# --- revisión 2026-10-07: comprobaciones que pasaban en la primera mirada, y lecturas que perdían lo dicho


def _check(text: str) -> str:
    mission = missions.mission_request(text, APPS)
    assert mission is not None and mission.success_check, text
    return mission.success_check


def test_a_created_or_renamed_item_is_its_whole_name_typed_in_this_sub_goal() -> None:
    # The old #general, or «informe2» holding «informe», was there at the first look: neither is the item made.
    assert _check("en Discord creá un canal llamado general") == "control:=general&stepDone:input.text.type:general"
    assert _check("en el Explorador renombrá informe2 a informe") == "control:=informe&stepDone:input.text.type:informe"


def test_a_search_is_never_the_title_alone() -> None:
    # A window already titled «Duki» before the search is no search done.
    for term in _check("en Spotify buscá Duki").split("|"):
        assert "stepDone:" in term, term


def test_playing_needs_an_act_that_started_it_not_any_click() -> None:
    alone = _check("en Spotify poné la primera").split("|")
    assert all(not term.endswith("stepDone:input.visible.click") and not term.endswith("stepDone:input.key.press")
               for term in alone), alone
    assert "control:pausa&stepDone:input.visible.click:reproducir" in alone
    assert "control:pausa&stepDone:input.key.press:enter" in alone
    # After a search, the result clicked carries the name searched.
    played = _steps("en Spotify buscá Duki y poné la primera")[1][2].split("|")
    assert "control:pausa&stepDone:input.visible.click:duki" in played


def test_touching_a_word_that_is_also_a_place_clicks_the_place() -> None:
    assert missions.read_clause("tocá Inicio")[0] == "hacer clic en inicio"
    assert "stepDone:input.visible.click:inicio" in missions.read_clause("tocá Inicio")[1].split("|")
    assert missions.read_clause("tap Home")[0] == "hacer clic en home"
    # The key when the key is said, or with a verb that only presses.
    assert missions.read_clause("tocá la tecla Inicio") == ("apretar inicio", "stepDone:input.key.press:home")
    assert missions.read_clause("apretá inicio") == ("apretar inicio", "stepDone:input.key.press:home")
    assert missions.read_clause("dale enter") == ("apretar enter", "stepDone:input.key.press:enter")


def test_the_loop_reads_a_single_missions_goal_without_its_question() -> None:
    view = {"window": {"title": "Bloc de notas", "focused": {"kind": "Document", "name": "Editor de texto", "value": ""}},
            "controls": [{"i": 0, "kind": "Document", "name": "Editor de texto"}], "text": {}}
    goal = "escribir Hola" + missions.QUESTION_MARK + "decime qué dice"
    step = computer_use.decide_step(None, objective=goal, goal=goal, application=None, success_check=None, view=view,
                                    history=[], budget_left=5, application_names=())
    assert step["arguments"] == {"text": "Hola"}


def test_a_check_names_what_was_said_as_the_shell_folds_it() -> None:
    # The reader folds «Straße» to «strasse»; the shell (FormD, ToLowerInvariant) to «straße».
    assert missions.check_fold("Straße Ñandú") == "straße nandu"
    assert _check("en el Explorador creá una carpeta llamada Straße") == "control:=straße&stepDone:input.text.type:straße"


def test_the_text_keeps_its_capitals_across_double_spaces_and_line_breaks() -> None:
    assert missions.mission_request("en el bloc de notas escribí  Hola  Mundo", APPS).goal == "escribir Hola Mundo"
    assert missions.mission_request("en el bloc de notas escribí Hola\nMundo", APPS).goal == "escribir Hola Mundo"
