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
