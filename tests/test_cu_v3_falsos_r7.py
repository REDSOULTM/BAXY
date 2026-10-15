"""Falsos éxitos de la pasada v3 ronda 7 (2026-10-08): lo que el reparto dio por hecho fuera de la app pedida.

v3-34 «abre notas rápidas y crea una nota que diga llamar al dentista el martes» se leyó como app.open + note.create:
la nota quedó en el almacén de BAXY y el final dijo que se creó en Notas rápidas. Un acto cuyo objeto es aquello por lo
que la app se llama se hace dentro de ella. Cada regla con su contracaso: la misma nota con otra app sigue siendo de
BAXY, y un objeto que no es palabra del nombre no cambia el reparto."""

from __future__ import annotations

from baxy_mind import effect_intent
from baxy_mind.semantic import missions

NAMES = ("Notas rápidas", "Bloc de notas", "Spotify", "Paint", "Calendario")
OPERATIONS = (
    "app.open", "note.create", "mission.computer.use", "reminder.create", "media.play.query", "calendar.event.create",
    "task.create",
)


def _operations(text: str) -> tuple[str, ...]:
    intent = effect_intent.resolve_explicit_effects(text, OPERATIONS, NAMES)
    return intent.operations if intent is not None else ()


def test_v3_34_a_note_in_the_notes_app_is_made_inside_it() -> None:
    assert _operations("abre notas rápidas y crea una nota que diga llamar al dentista el martes") == (
        "mission.computer.use",
    )
    assert _operations("open sticky notes and create a note saying hi") == ("mission.computer.use",)
    assert _operations("abre el bloc de notas y crea una nota que diga hola") == ("mission.computer.use",)


def test_v3_34_contracase_a_note_beside_another_app_is_still_baxys() -> None:
    assert _operations("abre spotify y crea una nota que diga llamar al dentista") == ("app.open", "note.create")
    # A word of the name inside what is dictated is no object of the act.
    assert _operations("open spotify and create a note saying notes") == ("app.open", "note.create")
    assert _operations("abre paint y crea una nota: notas de paint") == ("app.open", "note.create")


def test_v3_11_the_place_said_before_the_colon_is_not_typed() -> None:
    # v3-11 r7: «escribe ahi: comprar pan, leche y huevos» typed «ahi: comprar pan, leche y huevos».
    assert missions.read_clause("escribe ahi: comprar pan, leche y huevos") == (
        "escribir comprar pan, leche y huevos", missions.WRITTEN_CHECK,
    )
    assert missions.read_clause("write there: hello")[0] == "escribir hello"
    # Contracase: without the colon the word is the text's own («escribe aqui esta frase»).
    assert missions.read_clause("escribe aqui esta frase")[0] == "escribir aqui esta frase"
    assert missions.read_clause("escribe: hola")[0] == "escribir hola"


def test_the_object_is_read_before_its_complement() -> None:
    assert missions.act_object_names_application("crea una nota que diga hola", "Notas rápidas")
    assert missions.act_object_names_application("create a new note", "sticky notes")
    assert not missions.act_object_names_application("pon musica de spotify", "Spotify")
    assert not missions.act_object_names_application("crea una nota", "Spotify")
    assert not missions.act_object_names_application("escribe: notas rapidas", "Notas rápidas")
