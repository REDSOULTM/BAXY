"""Uso real tanda 5 (2026-09-24, official window): apps, media and settings said in Spanglish.

- «Abre el gallery» asked which folder: Windows names its own apps in the language it is installed in («Fotos»,
  «Photos») and people name them in theirs, or by what they show (the Photos app opens on its Gallery). A
  built-in app is found by any of its Spanish or English names that the Start catalog carries
  (catalog._CATALOG_NAME_ALIASES), also after «ábreme», «ponme» and «quiero que abras».
- «Inicia mi homescreen» was a limit: starting, launching or putting on the home screen is going to it, like
  «Ve al homescreen» (the desktop, window.minimize.all); it is never a game title.
- «silenciar la configuraciones» (MASSIVE audio_volume_mute) asked about Do Not Disturb: settings make no sound of
  their own, so silencing them is silencing the PC; the silence verb said alone has nothing else to fall on.
- «busca podcast y reprodúce lo» was asked «¿un podcast específico…?»: searching for a thing and playing it is the
  order to play it; a show named only by its kind leaves the pick to the search, so nothing is asked. The search
  verb is never part of what plays (it became the query «busca despacito y»).
- «¿puedes poner catalunya informació, por favor?» played an old upload: a station named with no station noun is
  still a broadcaster when a tuning verb, «en directo/live» or a broadcaster's word («cadena», «onda», a news
  service «informació») says so; the polite infinitive («poner») is the order too.
- «pausar el audiolibro» answered «no se observó el cambio»: the YouTube video had ended. Pausing what is not
  playing changes nothing; the failure is that absence, told plainly (youtube_playing_video_not_found).
"""

from __future__ import annotations

import pytest

from baxy_mind import llm
from baxy_mind.__main__ import _explicit_arguments_from_evidence, _prepare_turn_result
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.media import radio_station_query
from baxy_mind.semantic.patterns import resolve_application_catalog_app_id
from baxy_mind.semantic.reading import read
from test_c03_pointless_questions import _NoEvidence, _tool
from test_c03_unknown_looked_up import _KnowledgeLlm

OPERATIONS = (
    "app.open", "app.installed", "filesystem.folder.open", "window.minimize.all", "input.key.press",
    "game.entitlement.named", "game.launch", "audio.mute", "audio.volume", "audio.volume.adjust",
    "audio.microphone.mute", "audio.app.volume.adjust", "system.settings.set", "media.play.youtube",
    "media.play.query", "media.control", "web.search", "web.news.headlines",
)

SPANISH_WINDOWS = (
    "Fotos", "Cámara", "Reloj", "Herramienta Recortes", "Grabadora de sonido", "Reproductor multimedia",
    "Notas rápidas", "Microsoft Store", "Panel de control", "Calculadora", "Bloc de notas", "Spotify", "Steam",
)
ENGLISH_WINDOWS = (
    "Photos", "Camera", "Clock", "Snipping Tool", "Sound Recorder", "Media Player", "Sticky Notes",
    "Calendar", "Maps", "Calculator", "Notepad", "Spotify",
)


def _opened(text: str, catalog: tuple[str, ...]) -> str | None:
    reading = read(text, available_operations=OPERATIONS, application_names=catalog)
    assert reading.effects is not None and reading.effects.operations == ("app.open",), (text, reading.effects)
    return resolve_application_catalog_app_id(text, catalog)


def _effects(text: str) -> tuple[str, ...]:
    reading = read(text, available_operations=OPERATIONS)
    return () if reading.effects is None else reading.effects.operations


def _arguments(text: str, operation: str) -> dict[str, object] | None:
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is not None and reading.effects.operations == (operation,), (text, reading.effects)
    return _explicit_arguments_from_evidence(operation, reading.effects.evidence[0], (), ())


# --- 1. a built-in app by any of its names ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "app"),
    [
        ("Abre el gallery", "Fotos"),  # the replay row
        ("open the gallery", "Fotos"),
        ("abre la galería de fotos", "Fotos"),
        ("ábreme la galería", "Fotos"),
        ("ponme la galería", "Fotos"),
        ("quiero que abras la galería", "Fotos"),
        ("i want you to open the photos app", "Fotos"),
        ("launch the gallery", "Fotos"),
        ("open the camera", "Cámara"),
        ("open clock", "Reloj"),
        ("launch the snipping tool", "Herramienta Recortes"),
        ("abre la herramienta de recortes", "Herramienta Recortes"),
        ("open sound recorder", "Grabadora de sonido"),
        ("open media player please", "Reproductor multimedia"),
        ("open sticky notes", "Notas rápidas"),
        ("abre la tienda de microsoft", "Microsoft Store"),
        ("open control panel", "Panel de control"),
        ("abre el snipping tool", "Herramienta Recortes"),
        ("open la galería", "Fotos"),
        ("abre el sound recorder", "Grabadora de sonido"),
        ("ábreme la calculadora por favor", "Calculadora"),
    ],
)
def test_an_app_named_in_english_opens_on_a_spanish_windows(text: str, app: str) -> None:
    assert _opened(text, SPANISH_WINDOWS) == app


@pytest.mark.parametrize(
    ("text", "app"),
    [
        ("abre fotos", "Photos"),
        ("abre la galería", "Photos"),
        ("abre la cámara", "Camera"),
        ("abre el reloj", "Clock"),
        ("abre el calendario", "Calendar"),
        ("abre mapas", "Maps"),
        ("abre la grabadora", "Sound Recorder"),
        ("abre las notas rápidas", "Sticky Notes"),
        ("abre el reproductor multimedia", "Media Player"),
    ],
)
def test_an_app_named_in_spanish_opens_on_an_english_windows(text: str, app: str) -> None:
    assert _opened(text, ENGLISH_WINDOWS) == app


@pytest.mark.parametrize(
    ("text", "catalog"),
    [
        # The name stands for an app that is not installed: nothing is opened in its place.
        ("abre la galería", ("Spotify", "Steam")),
        ("open the camera", ("Spotify", "Steam")),
        # Another thing named with the same word is that other thing.
        ("abre la galería de steam", SPANISH_WINDOWS),
        ("pon el reloj a las 7", SPANISH_WINDOWS),
    ],
)
def test_what_names_no_installed_app_opens_none(text: str, catalog: tuple[str, ...]) -> None:
    reading = read(text, available_operations=OPERATIONS, application_names=catalog)
    assert reading.effects is None or "app.open" not in reading.effects.operations, reading.effects
    assert resolve_application_catalog_app_id(text, catalog) not in {"Fotos", "Cámara", "Reloj"}


# --- 2. the home screen started ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Inicia mi homescreen",  # the replay row
        "inicia la pantalla de inicio",
        "launch my home screen",
        "start the home screen",
        "ponme el homescreen por favor",
        "bring up the home screen",
        "arranca el start screen",
        "lanza la pantalla de inicio",
        "start mi home screen",
        # The rows an earlier tanda fixed keep their reading.
        "Ve al homescreen",
        "Abre el start screen",
    ],
)
def test_starting_the_home_screen_is_going_to_the_desktop(text: str) -> None:
    assert _effects(text) == ("window.minimize.all",)


@pytest.mark.parametrize(
    "text", ["abre el escritorio", "inicia el escritorio", "inicia windows", "lanza mortal kombat", "inicia el menú inicio"],
)
def test_what_is_not_the_home_screen_minimizes_nothing(text: str) -> None:
    assert "window.minimize.all" not in _effects(text)


# --- 3. the settings silenced -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "state"),
    [
        ("silenciar la configuraciones", True),  # the replay row
        ("silencia la configuración", True),
        ("mute the settings", True),
        ("mute settings please", True),
        ("silencia los ajustes de sonido", True),
        ("mutea la config del sistema", True),
        ("silencia los settings", True),
        ("mutea los settings del sistema", True),
        ("silencia", True),
        ("mute", True),
        ("mute now", True),
        ("silenciar el volumen", True),
        ("mutea el pc", True),
        ("apaga el volumen", True),
        ("enciende el volumen", False),
    ],
)
def test_silencing_the_settings_is_silencing_the_pc(text: str, state: bool) -> None:
    assert _arguments(text, "audio.mute") == {"state": state}


@pytest.mark.parametrize(
    "text",
    [
        "silencia las notificaciones",
        "silencia la configuración de notificaciones",
        "silencia spotify",
        "silencia el micrófono",
        "no silencies la configuración",
    ],
)
def test_silencing_something_else_is_not_the_pc_mute(text: str) -> None:
    assert "audio.mute" not in _effects(text)


# --- 4. a podcast searched and played ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("busca podcast y reprodúce lo", "podcast"),  # the replay row
        ("busca un podcast y ponlo", "podcast"),
        ("find a podcast and play it", "podcast"),
        ("search for a podcast and play one", "podcast"),
        ("búscame un audiolibro y ponlo por favor", "audiolibro"),
        ("busca un podcast cualquiera y ponlo", "podcast"),
        ("busca podcasts de historia y pon uno", "podcasts de historia"),
        ("busca un podcast y play it", "podcast"),
        # The search verb is never part of what plays.
        ("busca despacito y ponlo", "despacito"),
        ("find despacito and play it", "despacito"),
    ],
)
def test_what_is_searched_to_be_played_plays(text: str, query: str) -> None:
    assert _arguments(text, "media.play.youtube") == {"query": query}


@pytest.mark.parametrize("text", ["pon un podcast", "busca música y ponla"])
def test_the_bare_order_still_asks_what_to_play(text: str) -> None:
    # The order alone names nothing (uso real 2026-09-23); bare music is asked (MUSIC1571).
    reading = read(text, available_operations=OPERATIONS)
    assert reading.clarification is not None and reading.clarification.missing_fields == ("query",)


@pytest.mark.parametrize("text", ["busca podcast", "encuentra audiobook", "busca el clima y dímelo"])
def test_a_search_alone_plays_nothing(text: str) -> None:
    assert not {"media.play.youtube", "media.play.query"} & set(_effects(text))


# --- 5. a station named by itself -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("¿puedes poner catalunya informació, por favor?", "catalunya informacio en vivo"),  # the replay row
        ("pon cadena ser", "cadena ser en vivo"),
        ("me pones la cadena dial", "cadena dial en vivo"),
        ("sintoniza onda cero", "onda cero en vivo"),
        ("sintoniza éxitos clásicos", "exitos clasicos en vivo"),
        ("tune in to classic hits", "classic hits en vivo"),
        ("pon catalunya informació en directo", "catalunya informacio en vivo"),
        ("pon catalunya informació live", "catalunya informacio en vivo"),
        ("¿puedes poner la radio cooperativa?", "radio cooperativa en vivo"),
    ],
)
def test_a_broadcaster_named_by_itself_plays_live(text: str, query: str) -> None:
    assert radio_station_query(text) == query
    assert _arguments(text, "media.play.youtube") == {"query": query}


@pytest.mark.parametrize(
    "text",
    [
        "pon más información",
        "pon la información del clima",
        "pon toda la información",
        "pon mi información",
        "pon cadena de favores",
        "¿qué suena en cadena ser?",
        "pon despacito",
        "pon música en vivo",
        "pon la tele en directo",
        # An artist live is a live recording, not a broadcaster.
        "Pon Tesla en vivo",
        "pon rosalía en directo",
    ],
)
def test_what_names_no_broadcaster_is_no_station(text: str) -> None:
    assert radio_station_query(text) is None


# --- the five replay rows through the whole turn ---------------------------------------------------------------


def _typed_tool(operation: str, properties: dict[str, object], required: tuple[str, ...]) -> dict[str, object]:
    tool = _tool(operation)
    tool["function"]["parameters"]["properties"] = properties
    tool["function"]["parameters"]["required"] = list(required)
    return tool


def _turn(text: str) -> dict[str, object]:
    tools = {
        "app.open": _typed_tool("app.open", {"appId": {"type": "string", "minLength": 1}}, ("appId",)),
        "window.minimize.all": _tool("window.minimize.all"),
        "audio.mute": _typed_tool("audio.mute", {"state": {"type": "boolean"}}, ("state",)),
        "media.play.youtube": _tool("media.play.youtube", required=("query",)),
        "media.play.query": _tool("media.play.query", required=("query",)),
        "filesystem.folder.open": _tool("filesystem.folder.open", required=("folder",)),
        "system.settings.set": _tool("system.settings.set", required=("setting",)),
        "web.search": _tool("web.search", required=("query",)),
    }
    return _prepare_turn_result(
        {"id": "turn-tanda05", "text": text},
        llm=_KnowledgeLlm("x"),
        planner_catalog=PlannerCatalog(list(tools.values())),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name=tools,
        application_names=SPANISH_WINDOWS,
    )


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("Abre el gallery", "app.open"),
        ("Inicia mi homescreen", "window.minimize.all"),
        ("silenciar la configuraciones", "audio.mute"),
        ("busca podcast y reprodúce lo", "media.play.youtube"),
        ("¿puedes poner catalunya informació, por favor?", "media.play.youtube"),
    ],
)
def test_the_replay_rows_act_instead_of_asking_or_refusing(text: str, operation: str) -> None:
    result = _turn(text)

    assert result["kind"] == "action", result
    assert result["operation"] == operation


# --- 6. pausing what is not playing -----------------------------------------------------------------------------


def _not_playing_facts() -> dict:
    return {
        "situation": {
            "kind": "failure",
            "polarity": "failure",
            "cause": "mission_failed",
            "stepCount": 0,
            "steps": [],
            "reason": {"kind": "operation", "operation": "media.control", "polarity": "failure",
                       "verified": False, "succeeded": False, "error": "youtube_playing_video_not_found"},
        }
    }


def test_the_absence_has_a_fact_to_tell() -> None:
    fact = llm._cause_in_prose("youtube_playing_video_not_found", "es")
    assert fact.startswith("nothing is playing") and "_" not in fact


@pytest.mark.parametrize(
    "draft",
    [
        "No hay nada sonando: el video de YouTube ya había terminado.",
        "No se está reproduciendo nada; el video de YouTube estaba en pausa.",
    ],
)
def test_nothing_playing_is_told_plainly(draft: str) -> None:
    assert llm.compose_visible_defect(draft, "error", "pausar el audiolibro", _not_playing_facts()) == ""


@pytest.mark.parametrize("draft", ["Listo, pausé el audiolibro.", "El audiolibro quedó en pausa."])
def test_a_pause_that_did_not_happen_is_never_claimed(draft: str) -> None:
    assert llm.compose_visible_defect(draft, "error", "pausar el audiolibro", _not_playing_facts()) != ""
