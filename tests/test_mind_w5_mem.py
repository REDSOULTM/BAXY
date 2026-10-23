"""BAXY Renew al máximo (w5, memoria y sesión larga): the session's history (src/baxy_mind/mind.py, Mind._trim) changes
what it already sent only in a cut, rarely and deeply, because the model (hybrid) re-reads everything after the first
changed message; and what a cut or a left-out body takes away never leaves behind a fact that reads otherwise."""
import json
from pathlib import Path

from baxy_mind import mind as mind_module
from baxy_mind.mind import COMPACTED, GIST_CHARS, GIST_WORDS, HISTORY_TURNS, TRIM_TURNS_TO
from test_mind_final import _mind, _say

_ids = iter(range(1, 10**6))


def _call(name: str, arguments: dict, more: int = 0) -> dict:
    calls = [{"id": f"k{next(_ids)}", "function": {"name": name, "arguments": json.dumps(arguments)}}
             for _ in range(1 + more)]
    return {"choices": [{"message": {"content": "", "tool_calls": calls}}]}


class Session:
    """Turns of one call each; for every request, whether the messages it sends start with all that the one before it
    sent and wrote (append-only) or something already sent changed (a rewrite, re-read from there on)."""

    def __init__(self, tmp_path: Path) -> None:
        self.mind, self.server = _mind(tmp_path, [])
        self.sent: list[str] = []
        self.rewrites: list[int] = []
        self.turn = 0

    def _check(self) -> None:
        now = [json.dumps(m, ensure_ascii=False, sort_keys=True) for m in self.server.bodies[-1]["messages"][1:]]
        if now[:len(self.sent)] != self.sent:
            self.rewrites.append(self.turn)
        self.sent = [json.dumps(m, ensure_ascii=False, sort_keys=True) for m in self.mind.conversation]

    def say(self, text: str, *results: str, reply: str = "Listo.") -> None:
        self.turn += 1
        self.server.replies += [_call("app_open", {"appId": f"App{self.turn}"}) for _ in results] + [_say(reply)]
        self.mind.decide(self.turn, text)
        self._check()
        for result in results:
            self.mind.continue_turn(self.turn, result)
            self._check()


def _done(size: int = 200) -> str:
    return json.dumps({"status": "completed", "verification": "readback", "observed": {"text": "x" * size}})


def test_messages_already_sent_never_change_while_the_history_fits(tmp_path: Path) -> None:
    session = Session(tmp_path)
    for turn in range(HISTORY_TURNS):
        session.say(f"pedido {turn}", _done(), _done())
    assert session.mind.trimmed_turns == 0 and session.rewrites == []


def test_a_cut_by_characters_also_leaves_room_in_the_count(tmp_path: Path) -> None:
    # int3 (sesión larga, turns 12 and 14): the bodies left out down to TRIM_TO of the characters kept every turn, the
    # count bound came back two turns later and the whole history was re-read twice (2,844 and 1,932 tokens).
    session = Session(tmp_path)
    for turn in range(5):
        session.say(f"pedido {turn}", _done())
    session.say("busca en la web qué es un pulpo", _done(20000))
    for turn in range(6):
        session.say(f"pedido {turn + 6}", _done())
    assert session.rewrites == [7]
    assert len(session.mind._turn_starts()) <= HISTORY_TURNS


def test_cuts_are_rare_and_each_leaves_room_for_the_next_turns(tmp_path: Path) -> None:
    session = Session(tmp_path)
    for turn in range(40):
        session.say(f"pedido {turn}", _done())
    kept = int(HISTORY_TURNS * TRIM_TURNS_TO)
    gaps = [b - a for a, b in zip(session.rewrites, session.rewrites[1:])]
    assert session.rewrites and all(gap == HISTORY_TURNS + 1 - kept for gap in gaps)
    # Every cut is one rewrite: what it left is not touched again until the next one.
    assert len(session.rewrites) == len(set(session.rewrites))


def test_a_cut_leaves_out_the_bodies_of_every_closed_turn_it_keeps(tmp_path: Path) -> None:
    session = Session(tmp_path)
    for turn in range(HISTORY_TURNS + 1):
        session.say(f"pedido {turn}", _done())
    results = [m["content"] for m in session.mind.conversation if m["role"] == "tool"]
    assert len(results) == int(HISTORY_TURNS * TRIM_TURNS_TO)
    assert [r.startswith(COMPACTED) for r in results] == [True] * (len(results) - 1) + [False]


def test_a_failed_step_keeps_its_code_when_its_body_is_left_out_and_when_its_turn_is_cut(tmp_path: Path) -> None:
    session = Session(tmp_path)
    for turn in range(HISTORY_TURNS - 2):
        session.say(f"pedido {turn}", _done())
    session.say("borra informe.txt y abre paint",
                json.dumps({"status": "failed", "error": "access_denied", "observed": {"text": "y" * 300}}),
                _done(), reply="No pude borrarlo; abrí Paint.")
    session.say("otro pedido", _done())
    session.say("y otro", _done())  # the cut: the failed turn is kept, without its bodies
    assert session.rewrites == [HISTORY_TURNS + 1]
    first = next(m["content"] for m in session.mind.conversation if m["role"] == "tool")
    assert first.startswith(COMPACTED) and "y" * 300 not in first
    assert first.endswith("[En este turno: app_open → falló (access_denied)]")
    # The turn cut: what the person asked and how each call ended, in the note of the cut.
    for turn in range(HISTORY_TURNS):
        session.say(f"más {turn}", _done())
    note = session.mind.conversation[0]["content"]
    assert ("«borra informe.txt y abre paint» → app_open → falló (access_denied); app_open → completado y verificado"
            in note)
    assert note.endswith("Lo demás que pasó en ellos no lo sabes]")


def test_a_cut_call_that_never_ended_is_never_told_as_done(tmp_path: Path) -> None:
    session = Session(tmp_path)
    session.server.replies += [_call("app_close", {"appId": "Paint"}, more=1)]
    session.turn += 1
    session.mind.decide(session.turn, "cierra paint y la calculadora")  # the turn ends before its calls' results
    for turn in range(HISTORY_TURNS):
        session.say(f"pedido {turn}", _done())
    note = session.mind.conversation[0]["content"]
    assert ("«cierra paint y la calculadora» → app_close → sin resultado: pudo o no ocurrir; app_close → no se ejecutó"
            in note)
    assert "«pedido 0» → app_open → completado y verificado" in note


def test_the_note_keeps_the_newest_cut_turns_within_its_bound(tmp_path: Path) -> None:
    session = Session(tmp_path)
    for turn in range(40):
        session.say(f"pedido {turn}:\n" + "palabra " * 30, _done())
    note = session.mind.conversation[0]["content"]
    lines = note.split("\n- ")[1:]
    assert sum(len(line) for line in lines) <= GIST_CHARS + len(note.split("\n- ")[-1]) and len(lines) >= 3
    assert lines[-1].startswith(f"«pedido {session.mind.trimmed_turns - 1}: palabra")  # the newest cut, in order
    said = lines[0][1:lines[0].index("»")]
    assert len(said) == GIST_WORDS + 1 and said.endswith("…") and "\n" not in said
    assert f"de {len(lines)} de ellos" in note and f"los {session.mind.trimmed_turns} turnos" in note


def test_a_reading_whose_body_is_left_out_no_longer_says_it_is_above(tmp_path: Path) -> None:
    session = Session(tmp_path)
    for turn in range(HISTORY_TURNS - 2):
        session.say(f"pedido {turn}", _done())
    session.say("¿a qué volumen está?", json.dumps({"status": "completed", "verification": "output_only",
                                                     "observed": {"volume": 30, "devices": "d" * 200}}))
    session.say("pulsa aceptar", json.dumps({"status": "completed", "verification": "readback",
                                              "observed": {"after": {"windowId": "w1", "text": "z" * 200}}}))
    told = [m["content"] for m in session.mind.conversation if m["role"] == "tool"][-2:]
    assert "su resultado está arriba" in told[0] and "su after es la ventana de después" in told[1]
    session.say("otro pedido", _done())  # the cut: both kept, without their bodies
    results = [m["content"] for m in session.mind.conversation if m["role"] == "tool"]
    assert results[0].endswith("[En este turno: app_open → completado: su resultado se omitió]")
    assert results[1].endswith("[En este turno: app_open → completado y verificado; su after se omitió]")
    for turn in range(HISTORY_TURNS):
        session.say(f"más {turn}", _done())
    note = session.mind.conversation[0]["content"]
    assert "«¿a qué volumen está?» → app_open → completado: su resultado se omitió" in note
    assert "está arriba" not in note and "es la ventana de después" not in note


def test_a_kept_session_cut_again_keeps_the_lines_of_its_earlier_cut(tmp_path: Path) -> None:
    session = Session(tmp_path)
    for turn in range(HISTORY_TURNS + 1):
        session.say(f"pedido {turn}", _done())
    kept = session.mind.export_session()
    session.mind.load_session(kept)
    for turn in range(HISTORY_TURNS):
        session.say(f"luego {turn}", _done())
    note = session.mind.conversation[0]["content"]
    assert "«pedido 0»" in note and "«luego 0»" in note
    assert note.count("\n- ") == session.mind.trimmed_turns


def test_without_words_of_the_person_the_note_says_only_how_many_turns_went(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mind_module, "HISTORY_TURNS", 1)
    mind, _ = _mind(tmp_path, [_say("Hola.")])
    mind.conversation = [{"role": "user", "content": "[Reloj: antes]"}, {"role": "assistant", "content": "Hola."}]
    mind.decide(1, "hola")
    assert mind.conversation[0]["content"].startswith("[Conversación recortada: los 1 turnos más antiguos de esta "
                                                      "sesión ya no se muestran; lo que pasó")


def test_a_read_kept_without_its_body_says_what_it_saw_was_left_out() -> None:
    # A read's line (w5-fals: «lectura: … lo que vio está arriba») said the body was above after the cut took it.
    from baxy_mind.mind import COMPACTED_FACTS, OUTPUT_READ
    line = OUTPUT_READ
    for kept, gone in COMPACTED_FACTS.items():
        line = line.replace(kept, gone)
    assert "está arriba" not in line and line.endswith("lo que vio se omitió")
