"""M106 (2026-10-01): DEV-D v4a D-w08-t3 «ponme recordatorio una ora antes d ese partido».

The verified reminder reached the composer without its observed record: the reminder record repeated «version» and the
Kernel dropped any observation it could not parse or that crossed its budget (C# M106ObservacionAcotadaTests). Now the
record arrives (bounded when it is large: identity and asked fields whole, free text cut, ``truncated`` set, the
message's ``observedLimit`` naming the bound), and the mind tells the reminder's verified due at the person's clock, as
it tells an alarm's: a draft with that time is published, a draft with another time is not, and the floor says it.

Every phrasing below is our own.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from baxy_mind import llm
from test_c03_m101b_sin_vacios import _Scripted

_ASKED = "ponme recordatorio una hora antes de ese partido"


def _due(days: int = 3) -> datetime:
    return (datetime.now(timezone.utc) + timedelta(days=days)).replace(minute=0, second=0, microsecond=0)


def _reminder(due: datetime, **extra: object) -> dict:
    observed = {"reminderId": "0b5c", "title": "Partido de la Selección", "details": "", "dueUtc": due.isoformat(),
                "dismissed": False, "deleted": False, "version": 1, **extra}
    return {"kind": "operation", "operation": "reminder.create", "polarity": "success", "verified": True,
            "succeeded": True, "observed": observed}


def _final(situation: dict, drafts: list[str]) -> str:
    facts = {"situation": json.dumps(situation, ensure_ascii=False), "mustNotAskFollowUp": True}
    return _Scripted(drafts).compose_user_message(_ASKED, "status", facts)


def _spanish_date(local: datetime) -> str:
    return f"{local.day} de {llm._WEATHER_MONTHS[local.month - 1][0]}"


def test_a_draft_that_says_the_verified_time_is_published() -> None:
    local = _due().astimezone()
    draft = f"Listo, te puse el recordatorio del partido para el {_spanish_date(local)} a las {local:%H:%M}."
    assert _final(_reminder(_due()), [draft]) == draft


def test_a_draft_with_another_time_gives_way_to_the_verified_one() -> None:
    local = _due().astimezone()
    other = (local + timedelta(hours=3)).strftime("%H:%M")
    floor = f"Creé el recordatorio «Partido de la Selección» para el {_spanish_date(local)} a las {local:%H:%M}."
    assert llm._deterministic_final(_reminder(_due()), {}, _ASKED, "es") == floor
    assert _final(_reminder(_due()), [f"Te avisaré a las {other}."] * 3) == floor


def test_tomorrow_is_said_as_the_word_the_person_hears() -> None:
    due = _due(days=1)
    local = due.astimezone()
    expected = "mañana" if local.date() == datetime.now().astimezone().date() + timedelta(days=1) else _spanish_date(local)
    final = llm._deterministic_final(_reminder(due), {}, _ASKED, "es")
    assert expected in final and f"{local:%H:%M}" in final


def test_a_projected_record_keeps_the_title_and_time_and_the_bound_stays_out_of_the_payload() -> None:
    situation = _reminder(_due(), details="detalle " * 250 + "…", truncated=True)
    situation["observedLimit"] = "projected"
    payload = llm._compose_situation_payload(situation, "es", _ASKED)
    local = _due().astimezone()
    assert payload["seen"]["title"] == "Partido de la Selección"
    assert payload["seen"]["scheduledLocalTime"] == f"{local:%H:%M}"
    assert "details" not in payload["seen"]
    assert "observedLimit" not in payload


def test_a_projected_page_read_is_more_not_shown() -> None:
    observed = {"title": "Informe anual", "url": "https://example.org/informe", "text": "Una frase leída. " * 100,
                "truncated": True}
    assert llm._project_page_read(observed, "es")["moreNotShown"] is True
