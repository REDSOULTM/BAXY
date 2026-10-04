"""M156 (2026-10-04, App run v4u-devI): what the person said in a first message reaches the operation whole.

Three single messages where the decision was right and a datum said was lost:

* I-s050 «baxy necesito que me despiertes a las 6 30 que tengo turno en la clinica» → an alarm «para las 18:00». The clock
  reader took «a las 6» and left «30»: minutes said straight after the hour («6 30», «6.30», «seis treinta») were no
  minutes, so the decider's «a las 6:30» was a time nobody said and the person's «a las 6» rang at the next 6 (D61).
* I-s085 «pone en disney plus intensamnete 2 q la quieren ver los chicos» → «¿Qué servicio de streaming y qué título
  exacto deseas buscar?». The readers chose the operation; its title reader only read «pon X en Disney+», never the
  service said first. The title goes as said: the service's search forgives the ear's typo (owner 2026-09-19).
* I-s038 «abreme el afinity foto ese pa editar una imajen» restated «Abre Affinity Photo.» → «¿Cuál es el nombre exacto
  de la aplicación…?». «Photo» was judged a name nobody said (the person wrote «foto»), so the person's words stood and
  named no application. A name written as it sounds is the name said; the application is then opened, or its absence
  said (D61.2), never asked.

Every phrasing beyond the rows is our own; clocks are fixed where the result depends on them.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.semantic import temporal
from baxy_mind.semantic.arguments import _canonical_due_utc
from baxy_mind.semantic.decider import ContextDecision, as_the_person_spelled, faithful_request
from baxy_mind.semantic.grammar import _fold
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.planner import PlannerCatalog
from test_c03_m148_avisos_eso_y_cuentas import OPERATIONS, _Decider, _history, _tool

LOCAL = timezone(timedelta(hours=-3))
# The run of I-s050: Sunday 4 October 2026, 06:25 in Chile.
RUN = datetime(2026, 10, 4, 6, 25, tzinfo=LOCAL)

S050 = "baxy necesito que me despiertes a las 6 30 que tengo turno en la clinica"
S085 = "pone en disney plus intensamnete 2 q la quieren ver los chicos"
S038 = "abreme el afinity foto ese pa editar una imajen"


def _clock(text: str) -> list[tuple[int, int]]:
    return [(clock.hour, clock.minute) for clock in temporal.spoken_clocks(_fold(text))]


def _local(utc: str | None) -> datetime | None:
    return None if utc is None else datetime.fromisoformat(utc.replace("Z", "+00:00")).astimezone(LOCAL)


def _turn(text: str, decision: ContextDecision, application_names: tuple[str, ...] = ()) -> dict:
    tools = {name: _tool(name) for name in OPERATIONS}
    return sidecar._prepare_turn_result(
        {"id": "m156", "text": text, "history": _history([text])},
        llm=_Decider(decision), planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (),
        tool_by_name=tools, dialogue_state=DialogueState(), application_names=application_names,
    )


# ------------------------------------------------------------------ I-s050: the minutes said after the hour


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (S050, [(6, 30)]),
        ("despiértame a las 6.30 porfa", [(6, 30)]),
        ("ponme la alarma a las seis treinta", [(6, 30)]),
        ("a las siete cuarenta y cinco tengo que salir", [(7, 45)]),
        ("wake me up at 6 30 tomorrow", [(6, 30)]),
        ("set an alarm at 6.30am", [(6, 30)]),
        ("a las 6 30 de la tarde", [(18, 30)]),
        # Forms that already read stay as they were.
        ("a las 6:30", [(6, 30)]),
        ("a las seis y media", [(6, 30)]),
        ("a las 6 y 30", [(6, 30)]),
        ("wake me at half six", [(6, 30)]),
        ("wake me at six thirty", [(6, 30)]),
    ],
)
def test_the_minutes_said_straight_after_the_hour(text: str, expected: list[tuple[int, int]]) -> None:
    assert _clock(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # D61: an hour alone is still the hour alone.
        ("pon una alarma a las 6", [(6, 0)]),
        # A length is no minutes of a clock, nor the day of a date.
        ("a las 6 30 minutos", [(6, 0)]),
        ("ponme un temporizador de 6 30 minutos", []),
        ("a las 6 15 de octubre", [(6, 0)]),
        ("at 7 15 minutes past", [(7, 0)]),
        # Without «a las / at», two numbers are no clock; a price is no clock.
        ("cuesta 6.30", []),
        ("tengo 6 30 fotos", []),
        ("a las 6 300", [(6, 0)]),
    ],
)
def test_what_is_no_minutes_does_not_change(text: str, expected: list[tuple[int, int]]) -> None:
    assert _clock(text) == expected


def test_i_s050_the_alarm_rings_at_half_past_six() -> None:
    # D61: the next 6:30 — at 06:25 that same morning; once it has passed, the evening one.
    assert _local(_canonical_due_utc("a las 6 30", S050, now_utc=RUN)) == datetime(2026, 10, 4, 6, 30, tzinfo=LOCAL)
    later = RUN.replace(hour=7)
    assert _local(_canonical_due_utc("a las 6 30", S050, now_utc=later)) == datetime(2026, 10, 4, 18, 30, tzinfo=LOCAL)
    # The decider's «a las 6:30» is what the person said: its restatement stays the objective.
    fidelity = faithful_request("Pon una alarma a las 6:30 para mi turno en la clínica.", S050, ())
    assert fidelity.kind == "kept" and fidelity.introduced == ()


def test_i_s050_the_turn_keeps_the_decided_alarm() -> None:
    result = _turn(S050, ContextDecision("Pon una alarma a las 6:30 para mi turno en la clínica.", "action",
                                         ("notification.schedule",), ""))
    assert result["kind"] == "action" and result["operation"] == "notification.schedule"
    assert result["objective"] == "Pon una alarma a las 6:30 para mi turno en la clínica."


@pytest.mark.parametrize(
    ("folded", "expected"),
    [
        ("set an alarm for 6 30", "at 6 30"),
        ("pon una alarma para 6.30 manana", "a las 6.30"),
        # Unchanged (M129's D61 cases).
        ("set an alarm for 8", "at 8"),
        ("set an alarm for 8 minutes", None),
        ("pon una alarma para 7 30 minutos", None),
    ],
)
def test_the_hour_after_for_keeps_its_minutes(folded: str, expected: str | None) -> None:
    assert temporal.alarm_for_hour(folded) == expected


# ------------------------------------------------------------------ I-s085: the service said before the title


@pytest.mark.parametrize(
    ("text", "service", "title"),
    [
        (S085, "disney_plus", "intensamnete 2"),
        ("pon en netflix stranger thins porque me la recomendaron", "netflix", "stranger thins"),
        ("put on netflix wensday because my daughter loves it", "netflix", "wensday"),
        ("play on disney+ bluey", "disney_plus", "bluey"),
        # A title holding «que» is whole when nothing says why after it.
        ("pon en netflix lo que el viento se llevó", "netflix", "lo que el viento se llevó"),
        # The title before the service reads as it did.
        ("pon intensamente 2 en disney plus", "disney_plus", "intensamente 2"),
        ("start Stranger Things on Netflix", "netflix", "Stranger Things"),
    ],
)
def test_the_title_after_the_service(text: str, service: str, title: str) -> None:
    assert sidecar._explicit_arguments_from_evidence("streaming.play.named", text) == {"service": service,
                                                                                         "title": title}


@pytest.mark.parametrize(
    "text",
    [
        "pon netflix",
        "pon en netflix",
        "pon en netflix algo",
        "pon en netflix una peli de terror",
        "put on netflix something",
    ],
)
def test_no_title_said_is_still_asked(text: str) -> None:
    assert sidecar._explicit_arguments_from_evidence("streaming.play.named", text) is None


# ------------------------------------------------------------------ I-s038: a name written as it sounds


def test_i_s038_the_restatement_names_what_was_said() -> None:
    fidelity = faithful_request("Abre Affinity Photo.", S038, ())
    assert fidelity.kind == "kept" and fidelity.introduced == ()
    result = _turn(S038, ContextDecision("Abre Affinity Photo.", "action", ("app.open",), ""),
                   application_names=("Spotify", "Steam", "Discord"))
    assert result["kind"] == "action" and result["operation"] == "app.open"
    assert result["objective"] == "Abre Affinity Photo."


@pytest.mark.parametrize(
    ("request_", "text"),
    [
        ("Abre Photoshop.", "abre el fotoshop"),
        ("Open Audacity.", "open audasity please"),
        ("¿Qué hora es en Tokio?", "qué hora es en Tokyo"),  # M110, which this replaces
        ("Abre Excel.", "abreme el exel"),  # M127
    ],
)
def test_a_name_spelled_as_it_sounds_is_said(request_: str, text: str) -> None:
    assert faithful_request(request_, text, ()).introduced == ()


@pytest.mark.parametrize(
    ("request_", "text"),
    [
        # A name nobody said in any spelling is still introduced.
        ("Abre Paint.", "abre el programa ese de los dibujos"),
        ("Open GIMP.", "open the photo editor"),
        ("¿Qué hora es en Madrid?", "qué hora es allá"),
    ],
)
def test_a_name_nobody_said_is_still_introduced(request_: str, text: str) -> None:
    assert faithful_request(request_, text, ()).kind != "kept"


def test_the_service_lookup_still_takes_only_near_spellings() -> None:
    # M147 is unchanged: a name to look up keeps the model's spelling unless each word is a near miss of the person's.
    assert as_the_person_spelled("Affinity Photo", [S038]) is None
    assert as_the_person_spelled("Javier Mené", ["pone algo de javiera mena en spotify"]) == "javiera mena"
