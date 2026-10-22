"""BAXY Renew al máximo, tanda 5 (artifacts/renew/maximo/MAXIMO.md, area 10): what the heartbeat's model reads. Each
test holds one lever, so it can be measured and withdrawn on its own."""
import json
from pathlib import Path

from baxy_mind.mind import beat_message


def test_a_reminder_without_a_time_has_no_empty_brackets() -> None:
    # R10.3: past the ten listed the App adds «y 3 más sin listar» with no time, and it read «y 3 más sin listar ()».
    message = beat_message({"now": "22:00", "reminders": [{"text": "Regar las plantas", "due": None},
                                                          {"text": "y 3 más sin listar", "due": ""}]})
    line = next(line for line in message.splitlines() if line.startswith("Recordatorios:"))
    assert line == "Recordatorios: Regar las plantas; y 3 más sin listar"


def test_the_second_move_of_a_heartbeat_reads_the_motives_it_found(tmp_path: Path) -> None:
    # 10.3: only the analysis reached the move that acts; the motive behind it (what she asked, what falls due) did not.
    from test_mind_final import _mind, _say
    decision = {"pedido": "avisarle cuando termine la descarga", "preferencia": "ninguna", "vence": "nada",
                "bloqueo": "nada", "analisis": "Terminó una descarga.", "intervenir": True}
    mind, server = _mind(tmp_path, [_say(json.dumps(decision, ensure_ascii=False)), _say("Ya terminó tu descarga.")])
    mind.beat(1, {"now": "22:00", "events": ["file appeared in Descargas: informe.pdf"]})
    analysis = server.bodies[1]["messages"][-2]
    assert analysis["role"] == "assistant"
    assert analysis["content"] == ("pedido: avisarle cuando termine la descarga; preferencia: ninguna; vence: nada; "
                                   "bloqueo: nada. Terminó una descarga.")


def test_the_heartbeat_reads_its_times_as_a_clock_and_how_far_they_are() -> None:
    # 10.4 (Test of Time): the moment and each reminder were ISO stamps the model had to subtract; now the day and the
    # time, and how long until or since, as facts. The App's «yyyy-MM-dd HH:mm» (local) and ISO with an offset both read.
    message = beat_message({"now": "2026-10-22T09:40:00-03:00", "weekday": "jueves", "reminders": [
        {"text": "Clase", "due": "2026-10-22 10:00"}, {"text": "Entrega", "due": "2026-10-23T08:00:00-03:00"},
        {"text": "Pagar", "due": "2026-10-22T09:30:00-03:00"}, {"text": "Viaje", "due": "2026-10-27 07:00"}]})
    lines = message.splitlines()
    assert lines[0] == "Momento: jueves 22/10/2026 09:40 · la persona está: desconocido"
    assert next(line for line in lines if line.startswith("Recordatorios:")) == (
        "Recordatorios: Clase (hoy 10:00, en 20 min); Entrega (mañana 08:00, en 22 h 20 min); "
        "Pagar (hoy 09:30, hace 10 min); Viaje (martes 27/10 07:00, en 5 días)")


def test_times_the_heartbeat_cannot_read_are_shown_as_they_came() -> None:
    message = beat_message({"now": "22:00", "reminders": [{"text": "Clase", "due": "mañana temprano"}]})
    assert message.splitlines()[0] == "Momento:  22:00 · la persona está: desconocido"
    assert "Recordatorios: Clase (mañana temprano)" in message
