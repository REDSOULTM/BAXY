"""Uso real final verification (2026-09-25): the 742 decision-only replay against the 3.5 close (S8) changed 18
decisions; these are the regressions whose cause is a reader, each fixed where it lives.

1. «crea una carpeta llamada proyectos» asked for the date of an event (H0256, H0288, H0629; since 26f37154): the
   agenda reader took the participle «llamada» («named») after the thing it names for a phone call. Owner:
   semantic/notes.agenda_event_request (object_is_event) and its title reader.

Every list holds fresh phrasings (dialects, English, Spanglish), not the literals.
"""

from __future__ import annotations

import pytest

from baxy_mind.semantic.notes import agenda_event_request


@pytest.mark.parametrize(
    "text",
    [
        "créame una carpeta llamada fotos viejas",
        "crea un archivo llamado notas en el escritorio",
        "hazme una carpeta llamada tareas porfa",
        "pon una carpeta llamada música en documentos",
        "crea una lista llamada súper",
    ],
)
def test_a_thing_named_with_llamada_is_not_a_call_on_the_agenda(text: str) -> None:
    assert agenda_event_request(text) is None


@pytest.mark.parametrize(
    ("text", "title"),
    [
        ("agenda otra llamada con Ana mañana a las 5 de la tarde", "otra llamada con Ana"),
        ("pon una llamada con el dentista el lunes a las 3 de la tarde", "llamada con el dentista"),
        ("crea un evento llamado Revisión el lunes a las 10 de la mañana", "Revisión"),
        ("agenda una reunión llamada Kickoff mañana a las 9 de la mañana", "Kickoff"),
    ],
)
def test_calls_and_named_events_stay_on_the_agenda(text: str, title: str) -> None:
    event = agenda_event_request(text)
    assert event is not None
    assert event.title == title
