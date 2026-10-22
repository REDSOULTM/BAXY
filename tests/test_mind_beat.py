"""BAXY Renew al máximo, tanda 5 (artifacts/renew/maximo/MAXIMO.md, area 10): what the heartbeat's model reads. Each
test holds one lever, so it can be measured and withdrawn on its own."""
from baxy_mind.mind import beat_message


def test_a_reminder_without_a_time_has_no_empty_brackets() -> None:
    # R10.3: past the ten listed the App adds «y 3 más sin listar» with no time, and it read «y 3 más sin listar ()».
    message = beat_message({"now": "22:00", "reminders": [{"text": "Regar las plantas", "due": None},
                                                          {"text": "y 3 más sin listar", "due": ""}]})
    line = next(line for line in message.splitlines() if line.startswith("Recordatorios:"))
    assert line == "Recordatorios: Regar las plantas; y 3 más sin listar"
