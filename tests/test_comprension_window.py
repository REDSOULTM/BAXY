"""The official-window harness for comprensión sets on a minimal fake capture (events.jsonl as the conductor writes
it, with the shell trace, the mind's turn audit and the composition audit of the same run)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import comprension_eval as ce  # noqa: E402
import comprension_window as cw  # noqa: E402

SET = [
    {"id": "X-s001", "kind": "single", "conv": None, "turn": 1, "source": "t", "text": "book a ferry to Europa",
     "history": [], "pending": None, "dep": False, "gold": ["limit"], "args": {}},
    {"id": "X-c01-t1", "kind": "conv", "conv": "c01", "turn": 1, "source": "t", "text": "anota algo",
     "history": [], "pending": None, "dep": False, "gold": ["ask"], "args": {}},
    {"id": "X-c01-t2", "kind": "conv", "conv": "c01", "turn": 2, "source": "t", "text": "comprar leche",
     "history": [{"role": "user", "content": "anota algo"}, {"role": "assistant", "content": "¿Qué anoto?"}],
     "pending": "anota algo", "dep": True, "gold": ["op:task.create"], "args": {"op:task.create": [["leche"]]}},
    {"id": "X-c01-t3", "kind": "conv", "conv": "c01", "turn": 3, "source": "t", "text": "gracias",
     "history": [], "pending": None, "dep": False, "gold": ["talk"], "args": {}},
    {"id": "X-s002", "kind": "single", "conv": None, "turn": 1, "source": "t", "text": "¿qué hora es?",
     "history": [], "pending": None, "dep": False, "gold": ["talk"], "args": {}},
    {"id": "X-s003", "kind": "single", "conv": None, "turn": 1, "source": "t", "text": "hola",
     "history": [], "pending": None, "dep": False, "gold": ["talk"], "args": {}},
]
# The conversation arrives out of order in the file: the harness runs it by ``turn``.
SET_FILE_ORDER = [SET[0], SET[2], SET[1], SET[3], SET[4], SET[5]]


def write_jsonl(path: Path, rows: list[dict], encoding: str = "utf-8") -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding=encoding)


def turn_block(n: int, you: str, baxy: str | None, route: str, terminal: str = "published_final") -> list[dict]:
    rows = [
        {"type": "admission", "command": "turn", "status": 200, "body": "{\"ok\":true,\"status\":\"accepted\"}"},
        {"type": "event", "event": {"type": "admission", "turnId": f"t{n}", "accepted": True, "status": 200,
                                    "error": None}},
        {"type": "event", "event": {"type": "activity", "entry": {"id": f"native-{2 * n - 1}", "src": "YOU",
                                                                  "msg": you, "ts": "23:59:58"}}},
        {"type": "event", "event": {"type": "state", "value": "thinking"}},
    ]
    if baxy is not None:
        rows.append({"type": "event", "event": {"type": "activity", "entry": {
            "id": f"native-{2 * n}", "src": "BAXY", "msg": baxy, "ts": "00:00:01", "route": route}}})
    if terminal == "composition_failed":
        rows.append({"type": "event", "event": {"type": "composition_failed", "cause": "internal_code",
                                                "controlsUsable": True, "route": route, "injected": False}})
        rows.append({"type": "event", "event": {"type": "state", "value": "error"}})
    rows.append({"type": "event", "event": {"type": "state", "value": "idle"}})
    rows.append({"type": "terminal", "kind": terminal,
                 "final": baxy if terminal == "published_final" else terminal,
                 "diagnostic": None if terminal == "published_final" else "internal_code",
                 "timedOut": False, "admissionStatus": 200})
    rows.append({"type": "posterior", "messageCount": 2 * n, "userMessageCount": n, "isBusy": False,
                 "isInputEnabled": True, "hasPendingPlan": False, "pendingCompositionCount": 0,
                 "compositionFailure": None, "hasCompositionError": terminal != "published_final",
                 "statusDescription": "BAXY disponible", "mindReplyRejection": None})
    return rows


def cancel_block(n: int) -> list[dict]:
    """The conductor's «cancel» before a new conversation: it writes a «turn» admission of its own."""
    return turn_block(900 + n, "", None, "result", terminal="rejected")


def session_new() -> dict:
    return {"type": "admission", "command": "session.new", "status": 200, "body": "{\"ok\":true,\"id\":\"s\"}"}


def fake_run(capture: Path) -> None:
    """Five turns published or failed; the sixth (X-s003) never reached the capture: the conductor stopped."""
    events = [
        {"type": "meta", "commit": "0" * 40, "profile": "p", "capture": str(capture)},
        {"type": "runtime", "ready": True, "startupError": False, "status": "BAXY disponible"},
        session_new(),
        *turn_block(1, "book a ferry to Europa", "I can't book travel from this PC.", "conversation"),
        *cancel_block(1),
        session_new(),
        *turn_block(2, "anota algo", "¿Qué quieres que anote?", "clarification"),
        *turn_block(3, "comprar leche", "¿Confirmar o cancelar?", "confirmation"),
        *turn_block(4, "gracias", "De nada.", "conversation"),
        *cancel_block(2),
        session_new(),
        *turn_block(5, "¿qué hora es?", None, "result", terminal="composition_failed"),
        {"type": "posterior", "messageCount": 9, "userMessageCount": 5},
    ]
    write_jsonl(capture / "events.jsonl", events, encoding="utf-8-sig")
    trace, seq = [], 0

    def mark(scope: str, turn: str, stage: str, ms: float, detail: str | None = None) -> None:
        nonlocal seq
        seq += 1
        trace.append({"seq": seq, "ms": ms, "scope": scope, "id": turn, "stage": stage, "detail": detail})

    mark("turn", "t0", "mind.request.start", 10.0, "catalog.configure.id.1.budget_ms.120000")
    request = 1
    for n in range(1, 6):
        start = n * 10_000.0
        mark("bridge", f"t{n}", "submit.received", start)
        request += 1
        mark("turn", f"t{n}", "mind.request.start", start + 5, f"turn.decide.id.{request}.budget_ms.22000")
        request += 1
        mark("turn", f"t{n}", "mind.request.start", start + 900, f"message.compose.id.{request}.budget_ms.5000")
        mark("bridge", f"t{n}", "response.final", start + 1500 + n)
    write_jsonl(capture / "shell-trace.jsonl", trace)
    audit = [
        {"schema": "baxy.mind-turn-audit.v1", "request_id": "2", "phase": "raw_attempt", "stages": []},
        {"schema": "baxy.mind-turn-audit.v1", "request_id": "2", "phase": "final", "decision_path": "context_decider",
         "raw_decision": {"mode": "limit", "request": "book a ferry", "effect_operations": []}, "stages": [],
         "final": {"kind": "conversation", "intent_operations": [], "effect_operations": []}},
        {"schema": "baxy.mind-turn-audit.v1", "request_id": "4", "phase": "final",
         "decision_path": "deictic_referent_clarification", "raw_decision": None, "stages": [],
         "final": {"kind": "clarify", "intent_operations": [], "effect_operations": [], "question": "q"}},
        {"schema": "baxy.mind-turn-audit.v1", "request_id": "6", "phase": "final", "decision_path": "explicit_effects",
         "raw_decision": {"mode": "action"},
         "stages": [{"name": "validated_raw", "mode": "action", "operation": "task.create",
                     "conversation_kind": None, "effect_operations": ["task.create"]}],
         "final": {"kind": "action", "intent_operations": ["task.create"], "effect_operations": ["task.create"]}},
        {"schema": "baxy.mind-turn-audit.v1", "request_id": "8", "phase": "final",
         "decision_path": "explicit_conversation", "raw_decision": {"mode": "conversation"},
         "stages": [{"name": "validated_raw", "mode": "conversation", "operation": None,
                     "conversation_kind": "knowledge", "effect_operations": []}],
         "final": {"kind": "conversation", "intent_operations": [], "effect_operations": []}},
        {"schema": "baxy.mind-turn-audit.v1", "request_id": "10", "phase": "final", "decision_path": "context_decider",
         "raw_decision": {"mode": "talk"}, "stages": [],
         "final": {"kind": "conversation", "intent_operations": [], "effect_operations": []}},
    ]
    write_jsonl(capture / "turn-audit.jsonl", audit)
    situation = {"kind": "confirmation", "polarity": "pending",
                 "pendingAction": {"operation": "task.create", "purpose": "Anota comprar leche",
                                   "arguments": {"title": "comprar leche"}}}
    compose = [
        {"schema": "baxy.message-compose-diagnostic.v2", "trace": "t3", "intent": "confirmation",
         "payload": {"kind": "confirmation"}, "situation": json.dumps(situation, ensure_ascii=False)},
        {"schema": "baxy.message-compose-diagnostic.v2", "trace": "t4", "intent": "conversation",
         "payload": {"kind": "conversation"}, "situation": "{}"},
    ]
    write_jsonl(capture / "compose-audit.jsonl", compose)


def test_turns_file_and_map(tmp_path: Path) -> None:
    set_path = tmp_path / "X.jsonl"
    write_jsonl(set_path, SET_FILE_ORDER)
    cw.main(["turns", "--set", str(set_path), "--out", str(tmp_path / "x.turns.jsonl"),
             "--map", str(tmp_path / "x.map.json")])
    commands = [json.loads(line) for line in (tmp_path / "x.turns.jsonl").read_text("utf-8").splitlines()]
    assert commands == [
        {"cmd": "session.new"}, {"cmd": "turn", "text": "book a ferry to Europa"},
        {"cmd": "cancel"}, {"cmd": "session.new"}, {"cmd": "turn", "text": "anota algo"},
        {"cmd": "turn", "text": "comprar leche"}, {"cmd": "turn", "text": "gracias"},
        {"cmd": "cancel"}, {"cmd": "session.new"}, {"cmd": "turn", "text": "¿qué hora es?"},
        {"cmd": "cancel"}, {"cmd": "session.new"}, {"cmd": "turn", "text": "hola"},
    ]
    mapping = json.loads((tmp_path / "x.map.json").read_text("utf-8"))
    assert [(e["ordinal"], e["id"], e["session"]) for e in mapping["turns"]] == [
        (1, "X-s001", 1), (2, "X-c01-t1", 2), (3, "X-c01-t2", 2), (4, "X-c01-t3", 2), (5, "X-s002", 3),
        (6, "X-s003", 4),
    ]
    cw.main(["turns", "--set", str(set_path), "--out", str(tmp_path / "y.turns.jsonl"),
             "--map", str(tmp_path / "y.map.json"), "--ids", "X-c01-t3,X-s002", "--limit", "1"])
    picked = json.loads((tmp_path / "y.map.json").read_text("utf-8"))["turns"]
    assert [e["id"] for e in picked] == ["X-c01-t1", "X-c01-t2", "X-c01-t3"]


def test_records_review_and_score(tmp_path: Path, capsys) -> None:
    set_path = tmp_path / "X.jsonl"
    write_jsonl(set_path, SET_FILE_ORDER)
    map_path = tmp_path / "x.map.json"
    cw.main(["turns", "--set", str(set_path), "--out", str(tmp_path / "x.turns.jsonl"), "--map", str(map_path)])
    capture = tmp_path / "capture"
    capture.mkdir()
    fake_run(capture)
    run_path = tmp_path / "run.jsonl"
    cw.main(["records", "--capture", str(capture), "--map", str(map_path), "--out", str(run_path)])
    run = {record["id"]: record for record in ce.read_jsonl(run_path)}
    assert set(run) == {row["id"] for row in SET}

    single = run["X-s001"]
    assert (single["kind"], single["conversation_kind"], single["decision_from"]) == (
        "conversation", "unsupported", "audit")
    assert single["reply"] == "I can't book travel from this PC." and single["question"] == ""
    assert single["latency_s"] == 1.5 and single["latency_from"] == "trace"
    assert (run["X-c01-t1"]["kind"], run["X-c01-t1"]["question"]) == ("clarify", "¿Qué quieres que anote?")
    action = run["X-c01-t2"]
    assert (action["kind"], action["operation"], action["effects"]) == ("action", "task.create", ["task.create"])
    assert action["routes"] == ["confirmation"] and action["arguments_from"] == "compose"
    assert run["X-c01-t3"]["conversation_kind"] == "knowledge"
    failed = run["X-s002"]
    assert failed["error"] == "composition_failed: internal_code" and failed["reply"] == ""
    assert failed["error_state"] is True and failed["conversation_kind"] == "knowledge"
    assert run["X-s003"]["error"] == "no_turn_in_capture"

    rows = {row["id"]: row for row in SET}
    assert {i: ce.verdict(rows[i], run[i]) for i in run} == {
        "X-s001": (True, True),
        "X-c01-t1": (True, True),
        "X-c01-t2": (True, True),
        "X-c01-t3": (True, True),
        "X-s002": (False, False),
        "X-s003": (False, False),
    }
    capsys.readouterr()
    ce.score(set_path, run_path, None, None, False, None)
    assert "X.jsonl: 6/6 turnos puntuados" in capsys.readouterr().out

    review_path = tmp_path / "review.jsonl"
    cw.main(["review", "--run", str(run_path), "--set", str(set_path), "--map", str(map_path),
             "--out", str(review_path)])
    packet = {line["id"]: line for line in ce.read_jsonl(review_path)}
    third = packet["X-c01-t3"]
    assert third["lived"] == [
        {"role": "user", "content": "anota algo"},
        {"role": "assistant", "content": "¿Qué quieres que anote?"},
        {"role": "user", "content": "comprar leche"},
        {"role": "assistant", "content": "¿Confirmar o cancelar?"},
    ]
    assert third["published"] == "De nada." and third["gold"] == ["talk"]
    assert (third["invented"], third["warning"], third["ok"], third["note"]) == (None, None, None, "")
    assert packet["X-s001"]["lived"] == [] and packet["X-s002"]["published"] is None
    assert packet["X-s002"]["warning_hint"] is True and packet["X-s002"]["error"].startswith("composition_failed")


def test_capture_alone_reads_the_route(tmp_path: Path) -> None:
    set_path = tmp_path / "X.jsonl"
    write_jsonl(set_path, SET_FILE_ORDER)
    map_path = tmp_path / "x.map.json"
    cw.main(["turns", "--set", str(set_path), "--out", str(tmp_path / "x.turns.jsonl"), "--map", str(map_path)])
    capture = tmp_path / "capture"
    capture.mkdir()
    fake_run(capture)
    for name in ("shell-trace.jsonl", "turn-audit.jsonl", "compose-audit.jsonl"):
        (capture / name).unlink()
    run_path = tmp_path / "run.jsonl"
    cw.main(["records", "--capture", str(capture), "--map", str(map_path), "--out", str(run_path)])
    run = {record["id"]: record for record in ce.read_jsonl(run_path)}
    assert [run[i]["kind"] for i in ("X-s001", "X-c01-t1", "X-c01-t2", "X-c01-t3")] == [
        "conversation", "clarify", "action", "conversation"]
    assert all(run[i]["decision_from"] == "capture" for i in ("X-s001", "X-c01-t2"))
    # Across midnight on the activity clock: 23:59:58 -> 00:00:01.
    assert run["X-s001"]["latency_s"] == 3.0 and run["X-s001"]["latency_from"] == "clock"
    # Without the audit a limit is not told apart from talk, and no operation is known.
    assert ce.verdict(SET[0], run["X-s001"]) == (False, False)
    assert ce.verdict(SET[2], run["X-c01-t2"]) == (False, False)
