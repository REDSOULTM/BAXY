"""v3 r3a lectura L2: the application a request names is found by its words, not only by its exact name or a row of
the alias table (data/app_aliases.v1.json), and a request may open with the application and a colon or a comma.

The cases are the blind pass's orders (v3_primera_pasada_veredictos.json: v3-04, v3-19, v3-26, v3-29, v3-35, v3-39,
v3-48, v3-50, v3-62, v3-67) against a Start catalog fixed in tests/data; each rule has its counter-case.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind import known_folders
from baxy_mind.semantic import catalog, missions, patterns

ROOT = Path(__file__).resolve().parents[1]
START = json.loads((ROOT / "tests" / "data" / "cu_v3_start_catalog.v1.json").read_text(encoding="utf-8"))["names"]
INDEX = catalog.build_application_catalog_index(START)
OPERATIONS = ("app.open", "app.close", "mission.computer.use", "web.search", "browser.navigate", "file.open",
              "note.create", "input.key.press", "input.text.type", "input.visible.click", "window.focus")


@pytest.fixture(autouse=True)
def _documents(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(known_folders, "known_folder", lambda folder: {"documents": r"D:\Perfil\Documentos"}.get(folder))


def _name(said: str, names: object = INDEX, *, loose: bool = False) -> str | None:
    index = catalog.build_application_catalog_index(names)
    key = missions._catalog_key(said, index, loose=loose)
    return missions._display_name(key, index) if key is not None else None


# ------------------------------------------------------------ the aliases are data


def test_the_alias_table_is_data_and_every_row_names_catalog_names() -> None:
    data = json.loads((ROOT / "src" / "baxy_mind" / "data" / "app_aliases.v1.json").read_text(encoding="utf-8"))
    assert data["version"] == 1
    for group in ("aliases", "mission_aliases"):
        assert data[group], group
        for row in data[group]:
            assert row["spoken"] and row["catalog"], row
            # Folded: no capitals, no accents (the readers fold what is said before looking it up).
            for word in (*row["spoken"], *row["catalog"]):
                assert word == missions.fold(word), word
    assert catalog._CATALOG_NAME_ALIASES == catalog.app_alias_rows("aliases")
    assert missions._EXTRA_ALIASES == catalog.app_alias_rows("mission_aliases")
    # The rows the code had before they moved are still read: «calc» is the Calculator, «chrome» Google Chrome.
    assert _name("calc") == "Calculadora"
    assert _name("chrome") == "Google Chrome"
    assert _name("task scheduler") == "Programador de tareas"


# ------------------------------------------------------------ a name by its words


@pytest.mark.parametrize(("said", "name"), [
    ("7zip", "7-Zip File Manager"),            # v3-48, v3-50: a digit and a letter part words
    ("7-zip", "7-Zip File Manager"),           # the help beside it is no application said
    ("sticky note", "Notas rápidas"),          # v3-29: an alias said in the singular
    ("nota rapida", "Notas rápidas"),          # v3-35
    ("windows terminal", "Terminal"),          # v3-39
    ("windows security", "Seguridad de Windows"),  # v3-62
    ("task scheduler", "Programador de tareas"),   # v3-67
])
def test_a_name_said_by_its_words_is_the_one_application(said: str, name: str) -> None:
    assert _name(said) == name
    assert _name(said, loose=True) == name


@pytest.mark.parametrize(("said", "name"), [
    ("powerpint", "PowerPoint"),               # v3-04: one near spelling
    ("adminsitrador de tareas", "Administrador de tareas"),  # v3-19
    ("el visr de eventos", "Visor de eventos"),             # v3-26
])
def test_a_misheard_name_is_the_application_only_where_the_whole_slot_is_the_name(said: str, name: str) -> None:
    # Review of L2: a near spelling is read only for the slot an open verb or a head frame delimits whole
    # («abre powerpint y …»), never for «en X» or a scan of a clause's first words.
    assert _name(said, loose=True) == name
    assert _name(said) is None


@pytest.mark.parametrize("said", ["stream", "print", "route", "cursos"])
def test_an_ordinary_word_a_letter_off_a_name_is_no_application(said: str) -> None:
    # Review of L2 (base: None): «stream»/Steam, «print»/Paint, «route»/Router, «cursos»/Cursor. Not even whole.
    assert _name(said) is None
    assert _name(said, loose=True) is None


@pytest.mark.parametrize("text", [
    "on stream type hello and press enter", "en stream escribí hola", "en print escribí hola",
    "en cursos abrí el primero", "en route 66 buscá el mapa", "en el print screen guardá la captura",
])
def test_a_place_frame_with_an_ordinary_word_is_no_mission_in_an_application(text: str) -> None:
    assert missions.mission_request(text, INDEX) is None, text
    found = missions.free_form_arguments(text, INDEX)
    assert found is None or found.get("application") not in {"Steam", "Paint", "Router", "Cursor"}, found


def test_a_loose_word_or_two_near_names_name_nothing() -> None:
    # «zip» alone is no part that tells 7-Zip apart; «team» is as near to Steam as to Teams (APPS1495: ask which).
    assert _name("zip") is None
    assert _name("team", ("Steam", "Microsoft Teams")) is None
    assert patterns.near_catalog_application_candidates("abre team", ("Steam", "Microsoft Teams")) == (
        "Microsoft Teams", "Steam")
    # Words that are no application's name stay unread; a place inside an application is no application.
    for said in ("sistema", "general", "la casa de juan", "registro de aplicacion"):
        assert _name(said) is None, said
    # Two applications that both carry the words said: neither is chosen.
    assert _name("python 3", ("Python 3.12 (64-bit)", "Python 3.13 (64-bit)")) is None


# ------------------------------------------------------------ the head frame


@pytest.mark.parametrize(("text", "application", "goal"), [
    ("windows terminal: open settings and tell me which profile is the default", "Terminal", "ir a settings"),
    ("windows security, go to firewall & network protection and tell me which network is active",
     "Seguridad de Windows", "ir a firewall & network protection"),
    ("task scheduler: open library > microsoft > windows > defrag and tell me the next run time",
     # Ronda 21 (v3-67): opening a route introduces it; one click per piece, never one label with «>».
     "Programador de tareas", "hacer clic en library; luego hacer clic en microsoft; luego hacer clic en windows; "
     "luego hacer clic en defrag"),
])
def test_an_application_named_before_a_colon_or_a_comma_frames_the_request(text: str, application: str, goal: str) -> None:
    mission = missions.mission_request(text, INDEX)
    assert mission is not None and mission.application == application, text
    assert mission.goal.startswith(goal), mission.goal
    assert patterns.resolve_explicit_effects(text, OPERATIONS, INDEX).operations == ("mission.computer.use",)


def test_a_head_that_names_no_application_precisely_is_no_frame() -> None:
    # «Notas» is no application here: one loose word at the head frames nothing (a note to take, or the decider's).
    assert missions._head_frame("notas: comprar pan", INDEX) == "notas: comprar pan"
    # The assistant's own name is an address, never the application (BAXY is in this Start catalog).
    assert missions._head_frame("baxy, abre paint", INDEX) == "baxy, abre paint"
    mission = missions.mission_request("baxy, abre paint y dibujá un gato", INDEX)
    assert mission is None or mission.application != "BAXY"
    # A head that is no name at all stays as said.
    assert missions._head_frame("ok, abre paint", INDEX) == "ok, abre paint"


# ------------------------------------------------------------ the blind pass's orders


@pytest.mark.parametrize(("text", "application", "first"), [
    ("abre powerpint, haz una presentación en blanco, ponle 'Proyecto final' de título y guárdala como proyecto-final "
     "en Documentos\\baxy-prueba-v3", "PowerPoint", None),
    ("abre 7zip y anda a la carpeta Documentos\\baxy-prueba-v3", "7-Zip File Manager", None),
    ("en 7zip abrí el prueba.zip que está en baxy-prueba-v3", "7-Zip File Manager", None),
    ("abrí el visr de eventos y en Sistema buscame un evento con ID 6005", "Visor de eventos", "ir a sistema"),
])
def test_the_blind_orders_are_one_mission_in_the_application_named(text: str, application: str, first: str | None) -> None:
    mission = missions.mission_request(text, INDEX)
    assert mission is not None and mission.application == application, text
    if first is not None:
        assert mission.steps and mission.steps[0].goal.lower() == first, mission.steps
    assert patterns.resolve_explicit_effects(text, OPERATIONS, INDEX).operations == ("mission.computer.use",)


def test_a_place_said_inside_the_application_is_gone_to_before_the_order() -> None:
    mission = missions.mission_request("abrí el visr de eventos y en Sistema buscame un evento con ID 6005", INDEX)
    assert [(step.goal, step.free) for step in mission.steps] == [
        ("ir a sistema", False), ("buscar un evento con ID 6005", False)]
    # Counter-cases: an application after «en» is its own frame, never a place («en Paint dibujá …» switches to it);
    # with no application named first nothing is a place inside one.
    assert missions._place_then_order("en paint buscame un gato", INDEX) is None
    assert missions.mission_request("en Sistema buscame un evento con ID 6005", INDEX) is None


@pytest.mark.parametrize("text", [
    "abrí Word y en negrita escribí hola",
    "abrí el bloc de notas y en inglés escribí hola",
    "abrí Chrome y en incógnito buscá gatos",
    "abrí el bloc de notas y en silencio escribí hola",
    "abrí el bloc de notas y en serio escribí hola",
    "open notepad and in uppercase type hello",
])
def test_a_way_of_doing_after_en_is_no_place_to_go_to(text: str) -> None:
    # Review of L2 (base: None): «en negrita», «en inglés», «en incógnito» say how, never where; no «ir a …» step.
    mission = missions.mission_request(text, INDEX)
    assert mission is None or not any(step.goal.lower().startswith("ir a ") for step in mission.steps), mission


def test_a_place_after_en_is_said_as_a_name() -> None:
    # A place is said with an article, a capital or as a name the label tables know; a lowercase word with none of
    # those is no place («en sistema» is the known label, «en la tienda» has its article).
    said = "abrí Steam y en la tienda buscá Hades"
    assert [step.goal.lower() for step in missions.mission_request(said, INDEX).steps][:1] == ["ir a tienda"]
    said = "abrí el visr de eventos y en sistema buscame un evento con ID 6005"
    assert [step.goal.lower() for step in missions.mission_request(said, INDEX).steps][:1] == ["ir a sistema"]
    assert missions._place_then_order("en Novedades buscame hades", INDEX, "en Novedades buscame hades") is not None
    assert missions._place_then_order("en novedades buscame hades", INDEX, "en novedades buscame hades") is None


def test_a_new_note_said_without_its_application_stays_a_note() -> None:
    # Counter-case of «nota rápida»: «crea una nota» names no application and is the notes store's.
    assert patterns.resolve_explicit_effects("crea una nota que diga comprar pan", OPERATIONS, INDEX).operations == (
        "note.create",)
