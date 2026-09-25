"""Uso real final verification (2026-09-25): the 742 decision-only replay against the 3.5 close (S8) changed 18
decisions; these are the regressions whose cause is a reader, each fixed where it lives.

1. «crea una carpeta llamada proyectos» asked for the date of an event (H0256, H0288, H0629; since 26f37154): the
   agenda reader took the participle «llamada» («named») after the thing it names for a phone call. Owner:
   semantic/notes.agenda_event_request (object_is_event) and its title reader.
2. «Como me llamo», «que me gusta tomar.» went to the web (H0604, H0173): who the person is and what they like
   are their own data. Owner: semantic/web._FIRST_PERSON_OWN (read by names_own_data / not_a_public_lookup).
3. «para la canción» (layer A, real log) was rewritten by the model and looked up: its form is a place («para la X»),
   but it reads a request by itself. A follow-up that reads an effect on its own is that request and the model is
   not asked. Owner: __main__._rearm_in_context.
4. «De donde sacaste esa info?» (layer A, real log; since fa327140 «buscar lo público») was looked up: where BAXY got
   what he just said is asked of BAXY. Owner: semantic/web._NOT_A_PUBLIC_LOOKUP.

Every list holds fresh phrasings (dialects, English, Spanglish), not the literals.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.semantic import web
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


@pytest.mark.parametrize(
    "text",
    ["¿cómo me llamo?", "cual me llamo yo", "qué me gusta comer", "¿qué me gustaba de chico?", "what do i like",
     "¿dónde vivo?", "where do i live again", "¿cuántos años tengo?"],
)
def test_questions_about_the_person_never_go_to_the_web(text: str) -> None:
    assert web.not_a_public_lookup(text)


@pytest.mark.parametrize(
    "text",
    ["¿cómo se llama el presidente de Chile?", "qué le gusta comer a un gato", "where does Taylor Swift live",
     "cuántos años tiene el papa"],
)
def test_questions_about_others_are_still_public(text: str) -> None:
    assert not web.not_a_public_lookup(text)


class _NoModel:
    """Records every rewrite asked (a raise would be swallowed: a failed rewrite leaves the message as it arrived)."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def rewrite_in_context(self, text, context, **kwargs):
        self.asked.append(text)
        return "busca la canción"


_OPERATIONS = ("media.control", "media.play.query", "media.status", "web.search", "audio.volume.adjust", "app.open")
_SONG = ("quiero un tema de rock", "¿Quieres que ponga un tema de rock en Spotify?", "no, en youtube",
         "¿Alguno en particular?", "pon un tema de rock en youtube",
         "Está reproduciéndose «Soda Stereo - De música ligera - YouTube».")


@pytest.mark.parametrize("text", ["para la canción", "para la música porfa", "pará la canción ya", "para la reproducción"])
def test_a_follow_up_that_reads_a_request_by_itself_is_that_request(text: str) -> None:
    turns = (*_SONG, text)
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": turn} for i, turn in enumerate(turns)]
    message = {"id": "742-regression", "text": text, "history": history}
    model = _NoModel()
    assert sidecar._rearm_in_context(message, llm=model, available_operations=_OPERATIONS) is None
    assert model.asked == []


@pytest.mark.parametrize(
    "text",
    ["¿de dónde sacaste eso?", "de donde sacas esos datos", "where did you get that from?", "did you make that up",
     "¿te lo inventaste?", "eso lo imaginaste o qué"],
)
def test_where_baxy_got_what_he_said_is_asked_of_baxy(text: str) -> None:
    assert web.not_a_public_lookup(text)


@pytest.mark.parametrize("text", ["¿dónde queda la Torre Eiffel?", "where did the Titanic sink", "¿de dónde es Shakira?"])
def test_where_things_are_is_still_public(text: str) -> None:
    assert not web.not_a_public_lookup(text)
