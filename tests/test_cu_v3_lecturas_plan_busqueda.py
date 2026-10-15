"""Ronda 20 P8: the planner's readings of a switch and of a new container, and the data a search's proof reads.

Cases of the r18 pass: v3-33 («sacá una captura de pantalla completa» read as a switch turned off), v3-37 («abrí una
pestaña nueva de símbolo del sistema» read as going to «nueva de simbolo del sistema»), v3-29 («No hay caracteres
disponibles» taken for no «nothing found»). Every rule is general (no phrase, no application in the readers) and has
its counter-case.
"""

from __future__ import annotations

import re

import pytest

from baxy_mind import operation_floor
from baxy_mind.semantic import lexicon, missions


# ---------------------------------------------------------------- (a) a switch is said definite


@pytest.mark.parametrize(
    "clause",
    [
        "sacá una captura de pantalla completa",  # v3-33
        "saca una captura de pantalla completa",
        "sacá una copia",
        "quitá una fila",
        "poné una alarma a las 7",
        "pone un temporizador de 5 minutos",
        "sacá 2 fotos",
        "desactivá un filtro",
        "apagá otra luz",
    ],
)
def test_an_indefinite_or_counted_object_is_never_a_switch(clause: str) -> None:
    read = missions.read_clause(clause)
    goal, check = read if read is not None else ("", None)
    assert not goal.startswith(("activar", "desactivar")), read
    assert ":on" not in (check or "") and ":off" not in (check or ""), read


@pytest.mark.parametrize(
    ("clause", "goal", "atom"),
    [
        ("sacá el modo oscuro", "desactivar modo oscuro", "control:modo oscuro:off"),
        ("sacale lo de mantener la relación de aspecto", "desactivar mantener la relacion de aspecto",
         "control:mantener la relacion de aspecto:off"),
        ("sacale el tilde a negrita", "desactivar negrita", "control:negrita:off"),
        ("quitá la negrita", "desactivar negrita", "control:negrita:off"),
        ("apagá el wifi", "desactivar wifi", "control:wifi:off"),
        ("apagá wifi", "desactivar wifi", "control:wifi:off"),
        ("activá el modo oscuro", "activar modo oscuro", "control:modo oscuro:on"),
        ("poné el modo avión", "activar modo avion", "control:modo avion:on"),
        ("turn off the dark mode", "desactivar dark mode", "control:dark mode:off"),
    ],
)
def test_a_definite_switch_keeps_its_reading(clause: str, goal: str, atom: str) -> None:
    read = missions.read_clause(clause)
    assert read is not None and read[0] == goal, read
    assert atom in (read[1] or "").split("|"), read


@pytest.mark.parametrize(
    ("clause", "goal", "atom"),
    [
        # Review 2 of r20 P8, blocker 2: the article said is never given back to the name; a number inside the
        # name is no count.
        ("activá el 5G", "activar 5g", "control:5g:on"),
        ("apagá el 5G", "desactivar 5g", "control:5g:off"),
        ("desactivá el 2FA", "desactivar 2fa", "control:2fa:off"),
        ("desactivá 2FA", "desactivar 2fa", "control:2fa:off"),
        ("turn off the 5G", "desactivar 5g", "control:5g:off"),
    ],
)
def test_the_article_never_enters_the_switch_name(clause: str, goal: str, atom: str) -> None:
    read = missions.read_clause(clause)
    assert read is not None and read[0] == goal, read
    atoms = (read[1] or "").split("|")
    assert atom in atoms, read
    assert not any(re.match(r"^control:(?:el|la|los|las|the) ", each) for each in atoms), read


@pytest.mark.parametrize("clause", ["apagá la otra pantalla", "activá la otra pantalla", "desactivá el otro filtro"])
def test_an_article_before_an_indefinite_is_no_switch(clause: str) -> None:
    read = missions.read_clause(clause)
    goal, check = read if read is not None else ("", None)
    assert not goal.startswith(("activar", "desactivar")), read
    assert ":on" not in (check or "") and ":off" not in (check or ""), read


@pytest.mark.parametrize(
    "clause",
    [
        # Review 3 of r20 P8, blocker 3: a verb that gives or takes a thing before a definite object is no switch;
        # the base left these to the free reading.
        "ponele el nombre informe",
        "ponele el volumen al máximo",
        "put on the music",
        "take off the music",
        "take away the toolbar",
        "sacame la captura",
        "quitame el filtro",
    ],
)
def test_a_verb_that_gives_or_takes_a_thing_is_no_switch(clause: str) -> None:
    read = missions.read_clause(clause)
    goal, check = read if read is not None else ("", None)
    assert not goal.startswith(("activar", "desactivar")), read
    assert ":on" not in (check or "") and ":off" not in (check or ""), read


def test_the_ambiguous_verbs_are_data() -> None:
    assert {"saca", "quita"} <= lexicon.TOGGLE_AMBIGUOUS_OFF_VERBS
    assert {"pon", "pone"} <= lexicon.TOGGLE_AMBIGUOUS_ON_VERBS
    assert {"un", "una", "otra", "a", "an"} <= lexicon.INDEFINITE_LEADS


# ---------------------------------------------------------------- (b) a new container of a named kind


@pytest.mark.parametrize(
    ("clause", "goal", "kind"),
    [
        ("abrí una pestaña nueva de símbolo del sistema", "abrir una pestaña nueva de simbolo del sistema",
         "simbolo del sistema"),  # v3-37
        ("abrí una nueva pestaña de símbolo del sistema", "abrir una pestaña nueva de simbolo del sistema",
         "simbolo del sistema"),
        ("abrí otra pestaña de powershell", "abrir una pestaña nueva de powershell", "powershell"),
        ("nueva pestaña de powershell", "abrir una pestaña nueva de powershell", "powershell"),
        ("crea una pestaña nueva con powershell", "abrir una pestaña nueva de powershell", "powershell"),
        ("open a new command prompt tab", "abrir una pestaña nueva de command prompt", "command prompt"),
        ("open a new tab of command prompt", "abrir una pestaña nueva de command prompt", "command prompt"),
        ("abrí una ventana nueva de incógnito", "abrir una ventana nueva de incognito", "incognito"),
    ],
)
def test_a_new_container_of_a_kind_is_checked_by_its_birth(clause: str, goal: str, kind: str) -> None:
    read = missions.read_clause(clause)
    assert read is not None and read[0] == goal, read
    atoms = (read[1] or "").split("|")
    assert f"born:{kind}" in atoms, read
    assert all(atom.startswith("born:") for atom in atoms), read
    assert not any("nueva" in atom or "otra" in atom or atom.endswith(":new") for atom in atoms), read


@pytest.mark.parametrize(
    ("clause", "goal", "check"),
    [
        ("abrí una pestaña nueva", "apretar ctrl t", "stepDone:input.key.press:ctrl_t"),
        ("open a new tab", "apretar ctrl t", "stepDone:input.key.press:ctrl_t"),
        ("andá a la pestaña de Descargas", "ir a la pestaña descargas", "control:descargas:selected|title:descargas"),
    ],
)
def test_a_new_tab_without_kind_and_a_tab_gone_to_keep_their_readings(clause: str, goal: str, check: str) -> None:
    assert missions.read_clause(clause) == (goal, check)


@pytest.mark.parametrize(
    "clause",
    [
        "abrí otra pestaña", "abrí la pestaña de Descargas", "abrí una nueva carpeta", "abrí otra carpeta",
        # Review 1 of r20 P8 (finding 3): the novelty after an article, or after the container's noun.
        "open a new window", "open a new tab in edge", "abrí una ventana nueva", "abrí la pestaña nueva",
    ],
)
def test_novelty_never_enters_a_place(clause: str) -> None:
    read = missions.read_clause(clause)
    goal = read[0] if read is not None else ""
    place = re.match(r"^ir a (?P<target>.*)$", goal)
    words = set(place.group("target").split()) if place is not None else set()
    assert not words & lexicon.NOVELTY_WORDS, read


@pytest.mark.parametrize(
    ("clause", "goal"),
    [
        # Counter-cases: a place whose name holds such a word without a container, or a container without one.
        ("abrí el documento nuevo", "ir a documento nuevo"),
        ("abrí la ventana de opciones", "ir a ventana de opciones"),
    ],
)
def test_a_place_without_a_new_container_stays_a_place(clause: str, goal: str) -> None:
    read = missions.read_clause(clause)
    assert read is not None and read[0] == goal, read


@pytest.mark.parametrize(
    "clause",
    [
        # Review 2 of r20 P8, blocker 1: said definite, the other or the new container is one already open; opening
        # a third one would be done right on something nobody asked for.
        "abrí la otra pestaña de YouTube",
        "abrí el otro tab de youtube",
        "la otra pestaña de spotify",
        "abrí la pestaña nueva de youtube",
        "abrí la otra ventana de chrome",
        "open the new tab of youtube",
        "open the other window of chrome",
    ],
)
def test_a_definite_other_container_is_never_a_new_one(clause: str) -> None:
    read = missions.read_clause(clause)
    goal, check = read if read is not None else ("", None)
    assert not goal.startswith("abrir una "), read
    assert "born:" not in (check or ""), read


def test_a_definite_other_container_inside_an_application_is_never_a_new_one() -> None:
    request = missions.mission_request("en Chrome abrí la otra pestaña de YouTube", ["Google Chrome"])
    assert request is not None
    assert not request.goal.startswith("abrir una "), request
    assert "born:" not in (request.success_check or ""), request
    # Counter-case: the indefinite asks a new one, in the same frame.
    request = missions.mission_request("en Chrome abrí otra pestaña de YouTube", ["Google Chrome"])
    assert request is not None and request.goal == "abrir una pestaña nueva de youtube", request
    assert "born:youtube" in (request.success_check or "").split("|"), request


@pytest.mark.parametrize(
    ("clause", "target"),
    [
        # Review 3 of r20 P8, blocker 2: a name that begins with a word of novelty, no container and no indefinite
        # article before it, is a place still, with the place's check (never a click's stepDone).
        ("andá a new york", "new york"),
        ("andá a nueva york", "nueva york"),
        ("andá a nuevo león", "nuevo leon"),
        ("go to new releases", "new releases"),
        ("go to the new arrivals page", "new arrivals"),
        ("go to another page", "another"),
        ("andá a la carpeta nueva carpeta", "nueva carpeta"),
        ("abrí la carpeta nueva carpeta", "nueva carpeta"),
        ("abrí new releases", "new releases"),
        ("abrí el menú nuevo", "nuevo"),
        ("andá a la pestaña de new york", "new york"),
        ("andá a la ventana nueva", "ventana nueva"),
    ],
)
def test_a_name_that_begins_with_novelty_stays_a_place(clause: str, target: str) -> None:
    read = missions.read_clause(clause)
    assert read is not None and read[0] == f"ir a {target}", read
    assert f"control:{target}:current" in (read[1] or "").split("|"), read
    assert "stepDone:" not in (read[1] or ""), read


def test_the_container_words_are_data() -> None:
    assert {"pestana", "tab", "ventana", "window"} <= lexicon.CONTAINER_NOUNS
    assert {"nueva", "otra", "new"} <= lexicon.NOVELTY_WORDS
    assert set(lexicon.CONTAINER_GOAL_NOUNS) == set(lexicon.CONTAINER_NOUNS)
    assert {"una", "a", "an"} <= lexicon.INDEFINITE_ARTICLES
    assert lexicon.INDEFINITE_NOVELTY_WORDS <= lexicon.NOVELTY_WORDS | {"otras", "otros"}
    assert not {"nueva", "new"} & lexicon.INDEFINITE_NOVELTY_WORDS


# ---------------------------------------------------------------- (c) a search that found nothing (data)


def _evidence() -> dict:
    return operation_floor.floor_data()["computerUse"]["evidence"]


@pytest.mark.parametrize(
    "line",
    ["no hay caracteres disponibles", "ningun elemento disponible", "no items available", "0 files found",
     "no hay resultados para cookies"],
)
def test_saying_none_is_available_is_nothing_found(line: str) -> None:
    assert re.search(_evidence()["noResults"], line)


@pytest.mark.parametrize(
    "line",
    ["hay 3 actualizaciones disponibles", "caracteres disponibles", "google chrome - programas y caracteristicas",
     "u+038f: letra griega mayuscula omega con tonos"],
)
def test_a_line_with_things_available_is_no_nothing_found(line: str) -> None:
    assert not re.search(_evidence()["noResults"], line)


def test_the_query_function_words_are_data() -> None:
    words = _evidence()["queryFunctionWords"]
    assert {"de", "the", "of"} <= set(words)
    assert "omega" not in words and "mayuscula" not in words


# ---------------------------------------------------------------- (e) a written loading indicator (data)


def test_the_written_loading_name_is_narrow() -> None:
    loading = re.compile(operation_floor.floor_data()["computerUse"]["loading"])
    assert loading.search("cargando notas rapidas...")
    assert not loading.search("ocupado")
    assert not loading.search("mostrar como: ocupado")
    assert not loading.search("busy")
