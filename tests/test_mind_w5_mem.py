"""BAXY Renew al máximo (w5, memoria y sesión larga): the session's history (src/baxy_mind/mind.py, Mind._trim) changes
what it already sent only in a cut, rarely and deeply, because the model (hybrid) re-reads everything after the first
changed message."""
import json
from pathlib import Path

from baxy_mind.mind import COMPACTED, HISTORY_TURNS, TRIM_TURNS_TO
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
