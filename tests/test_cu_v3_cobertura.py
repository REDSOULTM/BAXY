"""v3 ronda 3 (lectura L1, falsos éxitos M5, lugar/clic M4): an order said inside an installed application is never
served by a typed operation that acts elsewhere or does only a piece of it.

First blind pass of v3 (cu-v3/v3_primera_pasada_veredictos.json, turn audits of v2-<case>): the contextual decider
chose typed operations near the order and the arguments step asked what they need and the order did not say, or they
did something else:

- v3-01 «abre powerpoint con una presentacion en blanco y en la primera diapo ponle de titulo Informe de ventas» →
  document.presentation.create → «¿Cuántas diapositivas deseas incluir…?»;
- v3-04 «abre powerpint, haz una presentación en blanco, …» → app.open + document.presentation.create → «no se pudo
  determinar cómo»;
- v3-08 «abrí onenote, creá una página nueva y ponele de título Lista del super» → app.open + note.create → «¿Qué
  título y contenido…?» (and the engine could not even be tried: «página» read as paying);
- v3-15 / v3-18 «abre la foto paisaje.jpg … en fotos, editala y girala…», «open paisaje.jpg in photos and tell me the
  image dimensions» → one file.open;
- v3-16 / v3-38 «en fotos abrí el editor … y ponele un filtro…», «en la terminal andá a configuración y cambiá el
  tema…» → one input.visible.click on an invented label.

Each one is the engine's, with the person's words. The counter-cases keep their typed route.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import decider, missions
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind import context_decision

ROOT = Path(__file__).resolve().parents[1]
CATALOG = tuple(
    json.loads((ROOT / "src/baxy_mind/data/decider_catalog.es.v1.json").read_text(encoding="utf-8"))["operations"]
)
OPERATIONS = tuple(dict.fromkeys((*CATALOG, "mission.computer.use")))
SURFACE = json.loads((ROOT / "src/baxy_mind/data/operation_surface.v1.json").read_text(encoding="utf-8"))
APPS = (
    "BAXY", "Bloc de notas", "Discord", "Fotos", "Google Chrome", "Microsoft Edge", "Notas rápidas", "OBS Studio",
    "OneNote", "PowerPoint", "Spotify", "Steam", "Terminal",
)


def _tool(operation: str) -> dict[str, Any]:
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "read_only", "parameters": schema}}


class _Decider:
    """The decider answers what it is given; every other model call is neutral."""

    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision

    def decide_in_context(self, *_a, **_k):
        return self.decision

    def prepare_decision(self, *_a, **_k):
        return None

    def operation_is_the_requested_effect(self, *_a, **_k):
        return True

    def detect_response_language(self, _text):
        return "es"

    @staticmethod
    def chat(*_a, **_k):
        return "Hola.", []

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


def _decided(text: str, decision: ContextDecision) -> dict[str, Any]:
    catalog = PlannerCatalog([_tool(name) for name in OPERATIONS])
    return context_decision._context_decided_result(
        {"id": "cobertura", "text": text, "history": [{"role": "user", "content": text}]},
        llm=_Decider(decision), planner_catalog=catalog, application_names=APPS,
    )


V3_01 = "abre powerpoint con una presentacion en blanco y en la primera diapo ponle de titulo Informe de ventas"
V3_04 = (
    "abre powerpint, haz una presentación en blanco, ponle 'Proyecto final' de título y guárdala como proyecto-final "
    "en Documentos\\baxy-prueba-v3"
)
V3_04_RESTATED = (
    "Abre PowerPoint, crea una presentación en blanco con título «Proyecto final» y guárdala en "
    "Documentos\\baxy-prueba-v3."
)
V3_08 = "abrí onenote, creá una página nueva y ponele de título Lista del super"
V3_15 = (
    "abre la foto paisaje.jpg que esta en Documentos\\baxy-prueba-v3 en fotos, editala y girala a la derecha pero no "
    "la guardes"
)
V3_16 = "en fotos abrí el editor de la imagen que tengo abierta y ponele un filtro blanco y negro, sin guardar"
V3_18 = "open paisaje.jpg in photos and tell me the image dimensions"
V3_38 = "en la terminal anda a configuracion y cambia el tema de la app a oscuro"


@pytest.mark.parametrize(
    ("text", "restated", "chosen", "application"),
    [
        (V3_01, "Crea una presentación en PowerPoint con título «Informe de ventas» y pon una diapositiva en blanco.",
         ("document.presentation.create",), "PowerPoint"),
        (V3_08, "Abrí OneNote, creá una página nueva y ponle de título «Lista del súper».",
         ("app.open", "note.create"), "OneNote"),
        (V3_15, "Abre la foto paisaje.jpg de Documentos\\baxy-prueba-v3, edita y gira a la derecha sin guardar.",
         ("file.open",), "Fotos"),
        (V3_16, "En Fotos, haz clic en el editor de la imagen abierta y ponle un filtro blanco y negro sin guardar.",
         ("input.visible.click",), "Fotos"),
        (V3_18, "Open paisaje.jpg in Photos and tell me its dimensions.", ("file.open",), "Fotos"),
        (V3_38, "En la terminal, haz clic en Configuración y cambia el tema de la app a oscuro.",
         ("input.visible.click",), "Terminal"),
        # falsos éxitos M5: the PC's sound for a source of the application named
        ("en OBS Studio silenciá el micrófono de la escena", "Silencia el micrófono.", ("audio.mute",), "OBS Studio"),
        # v3-34: a note of BAXY's own for one in the application named
        ("en notas rápidas anotá llamar al dentista", "Crea una nota: llamar al dentista.", ("note.create",),
         "Notas rápidas"),
    ],
)
def test_an_order_inside_an_application_served_elsewhere_or_in_part_is_the_engines(
    text: str, restated: str, chosen: tuple[str, ...], application: str,
) -> None:
    result = _decided(text, ContextDecision(restated, "action", chosen, ""))
    assert result["kind"] == "action"
    assert result["effectOperations"] == ["mission.computer.use"]
    # The engine's goal is the person's words, and its application the one they named.
    assert result["objective"] == text
    assert missions.place_application(text, APPS) == application


def test_a_misspelled_application_is_read_from_the_restatement() -> None:
    """v3-04: «powerpint» is no installed name; the decider's restatement names PowerPoint. The goal stays the person's
    words with the place written as the application (review of the branch: the restatement paraphrases and sometimes
    translates, so a title or a typed text could differ from what was said)."""

    result = _decided(V3_04, ContextDecision(V3_04_RESTATED, "action", ("app.open", "document.presentation.create"), ""))
    assert result["effectOperations"] == ["mission.computer.use"]
    assert result["objective"] == V3_04.replace("powerpint", "PowerPoint")
    assert missions.place_application(result["objective"], APPS) == "PowerPoint"


@pytest.mark.parametrize(
    ("text", "restated", "chosen"),
    [
        # Review of the branch: «en» before a time or a thing is no place, whatever application the restatement adds
        # from the conversation (D21); the timed follow-up stays typed and is not run now by the engine.
        ("en 10 minutos recordame estirar", "En Discord, recuérdame estirar en 10 minutos.", ("notification.schedule",)),
        ("en un rato subile el volumen", "En Spotify, súbele el volumen en un rato.", ("audio.volume",)),
        ("en 5 minutos silenciá todo", "En OBS Studio, silencia todo en 5 minutos.", ("audio.mute",)),
        ("en la primera diapo ponele de título Hola", "En PowerPoint, pon de título «Hola» en la primera diapositiva.",
         ("document.presentation.create",)),
        # a word said after the frame that is far from the application the restatement names
        ("abre potato y anotá llamar al dentista", "Abre OneNote y anota llamar al dentista.", ("note.create",)),
    ],
)
def test_a_place_the_person_did_not_say_is_never_taken_from_the_restatement(
    text: str, restated: str, chosen: tuple[str, ...],
) -> None:
    assert missions.place_misspelled(text, restated, APPS) is None
    result = _decided(text, ContextDecision(restated, "action", chosen, ""))
    assert result["effectOperations"] == list(chosen)


@pytest.mark.parametrize(
    ("text", "restated", "chosen"),
    [
        # no application named: the typed operation is the request
        ("crea una presentación con título Informe en Documentos",
         "Crea una presentación con título «Informe» en Documentos.", ("document.presentation.create",)),
        ("anotá: comprar pan", "Crea una nota: comprar pan.", ("note.create",)),
        ("silencia el audio", "Silencia el audio.", ("audio.mute",)),
        ("hacé clic en Aceptar", "Haz clic en Aceptar.", ("input.visible.click",)),
        # the operation serves the application named, whole
        ("en Spotify baja el volumen", "Baja el volumen de Spotify.", ("audio.app.volume.adjust",)),
        ("abre edge y anda a youtube.com", "Abre youtube.com en Edge.", ("browser.navigate.named",)),
        ("abre Steam y descargá Cuphead", "Descarga Cuphead en Steam.", ("game.install.named",)),
        # pieces clause for clause
        ("abrí el bloc de notas", "Abre el Bloc de notas.", ("app.open",)),
        ("abre el bloc de notas y escribe hola", "Abre el Bloc de notas y escribe hola.",
         ("app.open", "input.text.type")),
        # an application only mentioned is not the place of the order
        ("recordame mañana a las 9 abrir Spotify", "Recuérdame mañana a las 9 abrir Spotify.",
         ("notification.schedule",)),
        # the search engine named is the place of a search
        ("busca en google un top 3 de peliculas de suspenso", "Busca en Google un top 3 de películas de suspenso.",
         ("web.search",)),
        # what the engine never tries alone
        ("en Spotify borrá la playlist Gym", "Borra la playlist Gym en Spotify.", ("input.visible.click",)),
        # Review of the branch: a clause after opening an application that asks something of its own is not done in
        # it (the mission reader excludes «abre Steam y decime la hora» too); the answer or the act is not lost.
        ("abrime steam porfa y de paso fijate que hora es", "Abre Steam y dime qué hora es.",
         ("app.open", "system.time")),
        ("abrí chrome y fijate el clima de mañana en santiago", "Abre Chrome y dime el clima de mañana en Santiago.",
         ("app.open", "weather.current")),
        ("abre discord y recordame en 10 minutos llamar a pedro", "Abre Discord y recuérdame en 10 minutos llamar a Pedro.",
         ("app.open", "reminder.create")),
        ("abre discord y recordame en 10 minutos llamar a pedro", "Abre Discord y recuérdame en 10 minutos llamar a Pedro.",
         ("app.open", "notification.schedule")),
        ("abre spotify y apagá el wifi", "Abre Spotify y apaga el wifi.", ("app.open", "wifi.radio.set")),
        ("abre spotify y prendé el bluetooth", "Abre Spotify y enciende el Bluetooth.", ("app.open", "bluetooth.radio.set")),
        ("abre spotify y subí el volumen al 50", "Abre Spotify y sube el volumen al 50.", ("app.open", "audio.volume")),
        ("abre obs y sacá una captura de pantalla", "Abre OBS y toma una captura de pantalla.",
         ("app.open", "capture.screenshot")),
        # H0081: the search only finds the page the navigation opens in the browser named
        ("abrí chrome y entrá a wikipedia", "Abre Chrome y entra a Wikipedia.", ("web.search", "browser.navigate.named")),
        # what the typed readers read apart stays apart, even when an application could make it
        ("abrí spotify y anotá llamar al dentista", "Abre Spotify y crea una nota: llamar al dentista.",
         ("app.open", "note.create")),
        # one application's work and a request of its own: left whole to the decider
        ("abrí onenote, creá una página nueva y decime qué hora es", "Abre OneNote, crea una página y dime la hora.",
         ("app.open", "note.create", "system.time")),
    ],
)
def test_the_typed_route_stays_when_it_serves_the_order(
    text: str, restated: str, chosen: tuple[str, ...],
) -> None:
    result = _decided(text, ContextDecision(restated, "action", chosen, ""))
    assert result["effectOperations"] == list(chosen)


def test_a_question_the_decider_asks_is_left_alone() -> None:
    result = _decided(V3_01, ContextDecision(V3_01, "clarify", ("document.presentation.create",), "¿Cuántas?"))
    assert result["kind"] == "clarify"


def test_every_operation_the_decider_reads_has_a_surface() -> None:
    surfaces = SURFACE["operations"]
    kinds = {"app", "piece", *SURFACE["elsewhere"]}
    missing = [operation for operation in OPERATIONS if operation not in surfaces]
    assert missing == []
    assert set(surfaces.values()) <= kinds
    assert set(SURFACE["elsewhere"]) == {"files", "own_store", "system", "web"}
    # The engine itself and its own primitives never send a turn elsewhere.
    assert surfaces["mission.computer.use"] == "app"
    assert all(surfaces[operation] == "piece" for operation in ("app.open", "input.visible.click", "input.text.type"))


def test_served_elsewhere_judges_each_operation_away_from_the_application() -> None:
    """Review of the branch: only what an application makes serves a later clause of an order that opens it; another
    operation away from it does so only when the order is one clause said inside it; one read apart never does."""

    assert decider.order_served_elsewhere(("app.open", "system.time"), 1) is None
    assert decider.order_served_elsewhere(("audio.mute",), 1) is None
    assert decider.order_served_elsewhere(("audio.mute",), 1, doing_in_place=True) == "elsewhere"
    assert decider.order_served_elsewhere(("app.open", "note.create"), 2, read_apart=("app.open", "note.create")) is None
    assert decider.order_served_elsewhere(("app.open", "note.create", "system.time"), 3) is None
    assert set(SURFACE["made_in_applications"]) <= {op for op, kind in SURFACE["operations"].items()
                                                  if kind in SURFACE["elsewhere"]}


@pytest.mark.parametrize(
    ("text", "in_place"),
    [
        ("en OBS Studio silenciá el micrófono de la escena", True),
        ("en notas rápidas anotá llamar al dentista", True),
        ("abrime steam porfa y de paso fijate que hora es", False),
        ("en fotos girá la imagen y decime la hora", False),
        ("en 10 minutos silenciá todo", False),
    ],
)
def test_doing_said_in_place(text: str, in_place: bool) -> None:
    assert missions.doing_said_in_place(text, APPS) is in_place


@pytest.mark.parametrize(
    ("operations", "clauses", "reason"),
    [
        (("note.create",), 1, "elsewhere"),
        (("app.open", "note.create"), 3, "elsewhere"),
        (("input.visible.click",), 2, "partial"),
        (("file.open",), 3, "partial"),
        (("input.visible.click",), 1, None),
        (("app.open", "input.text.type"), 2, None),
        (("media.play.query",), 2, None),
        (("app.open", "media.play.exact"), 3, None),
        (("unknown.operation",), 5, None),
        ((), 2, None),
    ],
)
def test_served_elsewhere_reads_the_surface_data(operations: tuple[str, ...], clauses: int, reason: str | None) -> None:
    assert decider.order_served_elsewhere(operations, clauses) == reason


def test_a_name_inside_a_path_is_not_the_application() -> None:
    """v3-15 and v3-17: «Documentos\\baxy-prueba-v3» named the BAXY application for the engine."""

    assert missions.free_form_arguments(V3_15, APPS)["application"] == "Fotos"
    assert missions.free_form_arguments(
        "abre la imagen prueba.png de la carpeta baxy-prueba-v3 en fotos", APPS,
    )["application"] == "Fotos"
    assert missions.free_form_arguments("abre edge y anda a youtube.com", APPS + ("YouTube",))[
        "application"
    ] == "Microsoft Edge"
    # The name said as the place, followed by a full stop, still is.
    assert missions.free_form_arguments("abrí BAXY.", APPS)["application"] == "BAXY"


@pytest.mark.parametrize(
    ("text", "can"),
    [
        (V3_08, True),
        ("en Edge abrí la página de configuración", True),
        ("en 7-Zip comprimí la carpeta Fotos", True),
        ("en Configuración comprobá si hay actualizaciones", True),
        ("en Word cambiá el formato a negrita", True),
        ("en Word formateá el texto en negrita", True),
        ("en Word ayudame a comprender el texto", True),
        # the same in English (review of the branch: «page» and «format» were still read as paying and formatting)
        ("open onenote, create a new page and title it Groceries", True),
        ("in edge open the settings page", True),
        ("in word change the format to bold", True),
        # still kept out: paying, buying (also «compren»), formatting a drive or «it», in both languages
        ("en Steam pagá el juego", False),
        ("en Steam comprá Cuphead", False),
        ("en steam compren el juego", False),
        ("en chrome compren entradas para el recital", False),
        ("in steam pay for the game", False),
        ("en el Explorador formateá el pendrive", False),
        ("en el Explorador formateá la pc", False),
        ("en el Explorador formatealo", False),
        ("in explorer format the usb drive", False),
        ("in explorer format d:", False),
    ],
)
def test_the_engine_tries_pages_and_formats_but_never_pays_or_formats_a_drive(text: str, can: bool) -> None:
    assert missions.engine_can_try(text, APPS + ("Microsoft Edge", "7-Zip File Manager", "Configuración", "Word",
                                                 "Explorador de archivos", "Explorer")) is can


@pytest.mark.parametrize(
    ("text", "clauses"),
    [(V3_08, 3), (V3_38, 2), (V3_15, 3), ("abrí el bloc de notas", 1)],
)
def test_doing_clauses(text: str, clauses: int) -> None:
    assert missions.doing_clauses(text, APPS) == clauses


@pytest.fixture
def _person_folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from baxy_mind import known_folders

    documents = tmp_path / "Documentos"
    pictures = tmp_path / "Imagenes"
    (documents / "baxy-prueba-v3").mkdir(parents=True)
    pictures.mkdir()
    (documents / "baxy-prueba-v3" / "paisaje.jpg").write_bytes(b"x")
    (documents / "baxy-prueba-v3" / "prueba.png").write_bytes(b"x")
    monkeypatch.setattr(
        known_folders, "known_folder",
        lambda folder: {"documents": str(documents), "pictures": str(pictures)}.get(folder),
    )
    return documents / "baxy-prueba-v3"


def test_a_file_opened_in_an_application_without_a_known_folder_is_the_one_located(_person_folders: Path) -> None:
    """Lugar M6: v3-18 searched Imágenes only; v3-17 typed the whole phrase in the gallery's search box.
    cu-v3-abrir-archivo (r9): the one located is opened with the application by the shell (file.open), never through a
    dialog the gallery does not have."""

    located = str(_person_folders / "paisaje.jpg")
    mission = missions.mission_request(V3_18, APPS)
    assert mission is not None and mission.application == "Fotos"
    assert mission.goal.startswith(f"abrir el archivo {located}")
    assert mission.success_check == "title:paisaje&stepDone:file.open"
    seventeen = missions.mission_request("abre la imagen prueba.png de la carpeta baxy-prueba-v3 en fotos", APPS)
    assert seventeen is not None and seventeen.application == "Fotos"
    assert seventeen.goal == f"abrir el archivo {_person_folders / 'prueba.png'}"


def test_a_file_that_is_nowhere_or_twice_is_not_guessed(_person_folders: Path) -> None:
    (_person_folders.parent / "copia").mkdir()
    (_person_folders.parent / "copia" / "paisaje.jpg").write_bytes(b"x")
    # Two files with the name: the name alone, which the engine looks for and says it is two before any file.open
    # (the provider would take the folder it is given first; test_cu_v3_abrir_archivo).
    assert missions._file_reads("abri paisaje.jpg") == [
        ("abrir el archivo paisaje.jpg", "title:paisaje&stepDone:file.open", False)]
    # A folder of the person's that has no such file is not guessed.
    assert missions._file_reads("abri nada.png de la carpeta baxy-prueba-v3") is None
    # A place that names no folder is not guessed either.
    assert missions._file_reads("abri prueba.png de la carpeta") is None


# ---------------------------------------------------------------- v3-27 r9: the on-screen keyboard for an order inside
# another application. The live turn audit (cu-universal-evidencia/v2-v3-27/turn_audit.jsonl) has the context decider's
# own choice: «Abre el mapa de caracteres y copia el símbolo del euro.» → input.keyboard.open; no mission ran and the
# final told «Abrió… copió…».
V3_27 = "abre el mapa de caracteres y copia el simbolo del euro"
APPS_V3_27 = APPS + ("Mapa de caracteres", "Teclado en pantalla", "Character Map")


def _decided_with(text: str, decision: ContextDecision, applications: tuple[str, ...]) -> dict[str, Any]:
    catalog = PlannerCatalog([_tool(name) for name in OPERATIONS])
    return context_decision._context_decided_result(
        {"id": "cobertura", "text": text, "history": [{"role": "user", "content": text}]},
        llm=_Decider(decision), planner_catalog=catalog, application_names=applications,
    )


@pytest.mark.parametrize(
    ("text", "restated"),
    [
        (V3_27, "Abre el mapa de caracteres y copia el símbolo del euro."),
        ("open character map and copy the euro sign", "Open Character Map and copy the euro sign."),
    ],
)
def test_v3_27_an_order_inside_an_application_is_not_the_on_screen_keyboard(text: str, restated: str) -> None:
    result = _decided_with(text, ContextDecision(restated, "action", ("input.keyboard.open",), ""), APPS_V3_27)
    assert result["effectOperations"] == ["mission.computer.use"]
    assert result["objective"] == text


@pytest.mark.parametrize(
    ("text", "restated", "chosen"),
    [
        # what is asked is the on-screen keyboard itself, alone or beside another application
        ("abrí el teclado en pantalla", "Abre el teclado en pantalla.", ("input.keyboard.open",)),
        ("open the on-screen keyboard", "Open the on-screen keyboard.", ("input.keyboard.open",)),
        ("abre el bloc de notas y abrí el teclado en pantalla", "Abre el Bloc de notas y el teclado en pantalla.",
         ("app.open", "input.keyboard.open")),
    ],
)
def test_v3_27_contracase_the_on_screen_keyboard_itself_keeps_its_route(
    text: str, restated: str, chosen: tuple[str, ...],
) -> None:
    result = _decided_with(text, ContextDecision(restated, "action", chosen, ""), APPS_V3_27)
    assert result["effectOperations"] == list(chosen)


def test_served_elsewhere_an_operation_never_asked_is_no_request_of_its_own() -> None:
    assert decider.order_served_elsewhere(("input.keyboard.open",), 2) is None
    assert decider.order_served_elsewhere(("input.keyboard.open",), 2, unasked=("input.keyboard.open",)) == "elsewhere"
    # what a typed reader read apart in the order was asked, whatever the gate says
    assert decider.order_served_elsewhere(
        ("input.keyboard.open",), 2, read_apart=("input.keyboard.open",), unasked=("input.keyboard.open",),
    ) is None
