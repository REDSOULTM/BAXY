"""M147 (2026-10-03, DEV-F v4m–v4q F-w05-t5 «ya cambiando de tema, pone algo de javiera mena en spotify»): the decider
wrote «Javier Mené» every round and another artist played. A name a service looks up, respelled by the model a letter or
two off from what the person wrote, is looked up as the person wrote it (the service's own search forgives a typo of the
person's, D-owner 2026-09-19); a note or a reminder keeps the model's words."""

from __future__ import annotations

import importlib

from baxy_mind.semantic.decider import as_the_person_spelled

main = importlib.import_module("baxy_mind.__main__")

PLAY_QUERY = {"type": "object", "properties": {"provider": {"type": "string", "enum": ["spotify"]},
                                               "query": {"type": "string"}},
              "required": ["provider", "query"], "additionalProperties": False}
REMINDER = {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"],
            "additionalProperties": False}


def test_the_reader() -> None:
    said = ["ya cambiando de tema, pone algo de javiera mena en spotify"]
    assert as_the_person_spelled("Javier Mené", said) == "javiera mena"
    assert as_the_person_spelled("Mon Laferte", ["pon algo de mon laferte"]) is None  # said as it is
    assert as_the_person_spelled("Bohemian Rhapsody", ["pon bohemian rhapsody"]) is None
    assert as_the_person_spelled("Gustavo Cerati", ["pon algo de soda stereo"]) is None  # no run matches
    # The person's typo goes to the service, whose search forgives it (owner 2026-09-19).
    assert as_the_person_spelled("Ed Sheeran", ["play some ed sheeren"]) == "ed sheeren"


def test_f_w05_t5_the_query_is_the_persons() -> None:
    # M157: the respelling runs on the arguments the step returns (``_as_the_person_spelled``), not inside the decider's
    # values; the App's own path, with the decider's restatement as the text, is in test_c03_m157_regresiones_v4v.
    text = "ya cambiando de tema, pone algo de javiera mena en spotify"
    history = [{"role": "user", "content": text}]
    got = main._as_the_person_spelled(
        "media.play.query", {"provider": "spotify", "query": "Javier Mené"}, text, history,
    )
    assert got["query"] == "javiera mena"


def test_a_reminder_keeps_the_models_words() -> None:
    text = "recuérdame pagar la lus mañana"
    main._remember_decided_arguments(text, ("reminder.create",), (("title", "pagar la luz"),))
    got = main._with_decided_arguments("reminder.create", text, {}, REMINDER, text + "\npagar la luz")
    assert got == {"title": "pagar la luz"}
