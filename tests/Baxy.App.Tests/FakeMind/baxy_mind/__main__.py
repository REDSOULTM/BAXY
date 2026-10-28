"""A stand-in for the mind in the App's tests: the baxy.mind.v1 JSONL protocol and nothing else (no model, no voice).

As the real mind (src/baxy_mind/__main__.py), the reader answers voice.speak, voice.cancel, voice.status and
voice.release as they arrive and every other request waits its turn on one loop. What it does is read from script.json
in its folder at each request: "hold" {type: file} waits until that file exists, "delay" {type: seconds}, "fail" [type]
answers an error, "reply" {type: object} answers that object, "emit" {type: [message]} writes those messages after the
reply, "stderr" {type: [line]} writes those lines to stderr before the reply; "delay" {"hello": seconds} holds the hello
at start. Every request's type is appended to seen.log and the request itself to requests.jsonl, and each process
writes its pid under pids/.
"""

import json
import os
import queue
import sys
import threading
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUESTS = ["catalog.configure", "turn.decide", "turn.continue", "turn.confirm", "turn.beat", "turn.beat.end",
            "session.new", "session.export", "session.load", "trace.forget",
            "voice.start", "voice.stop", "voice.release", "voice.status", "voice.speak", "voice.cancel"]
READER = {"voice.speak", "voice.cancel", "voice.status", "voice.release"}
_write_lock = threading.Lock()


def write(message: dict) -> None:
    with _write_lock:
        sys.stdout.buffer.write(json.dumps(message).encode("utf-8") + b"\n")
        sys.stdout.buffer.flush()


def script() -> dict:
    try:
        with open(os.path.join(HERE, "script.json"), encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return {}


def seen(message: dict) -> None:
    with _write_lock:
        with open(os.path.join(HERE, "seen.log"), "a", encoding="utf-8") as file:
            file.write(str(message.get("type")) + "\n")
        with open(os.path.join(HERE, "requests.jsonl"), "a", encoding="utf-8") as file:
            file.write(json.dumps(message, ensure_ascii=False) + "\n")


def answer(message: dict) -> None:
    kind, request_id, plan = str(message.get("type")), message.get("id"), script()
    hold = plan.get("hold", {}).get(kind)
    if hold:
        deadline = time.monotonic() + 60
        while not os.path.exists(os.path.join(HERE, hold)) and time.monotonic() < deadline:
            time.sleep(0.02)
    time.sleep(float(plan.get("delay", {}).get(kind, 0)))
    for line in plan.get("stderr", {}).get(kind, []):
        sys.stderr.write(line + "\n")
    sys.stderr.flush()
    if kind in plan.get("fail", []):
        reply = {"type": "error", "code": "request_failed", "detail": kind}
    elif kind in plan.get("reply", {}):
        reply = dict(plan["reply"][kind])
    elif kind == "catalog.configure":
        reply = {"type": "catalog.ready", "count": len(message.get("capabilities") or [])}
    elif kind in ("turn.decide", "turn.continue", "turn.confirm", "turn.beat"):
        reply = {"type": "turn.result", "kind": "conversation", "reply": "hola"}
    elif kind == "turn.beat.end":
        reply = {"type": "turn.beat.ended"}
    elif kind in ("session.new", "session.load"):
        reply = {"type": "session.ready"}
    elif kind == "session.export":
        reply = {"type": "session.exported", "conversation": []}
    elif kind == "trace.forget":
        reply = {"type": "trace.forgotten", "cleared": True}
    elif kind == "voice.start":
        reply = {"type": "voice.started", "mode": message.get("mode")}
    elif kind == "voice.stop":
        reply = {"type": "voice.stopped"}
    elif kind == "voice.status":
        reply = {"type": "voice.status.result",
                 "status": {"available": False, "input": False, "stt": False, "pending": False}}
    elif kind == "voice.release":
        reply = {"type": "voice.released"}
    elif kind == "voice.speak":
        reply = {"type": "voice.speak.result", "accepted": True}
    elif kind == "voice.cancel":
        reply = {"type": "voice.cancelled"}
    else:
        reply = {"type": "error", "code": "unknown_request", "detail": kind}
    reply["id"] = request_id
    write(reply)
    for extra in plan.get("emit", {}).get(kind, []):
        write(extra)


def main() -> None:
    os.makedirs(os.path.join(HERE, "pids"), exist_ok=True)
    open(os.path.join(HERE, "pids", str(os.getpid())), "w", encoding="utf-8").close()
    time.sleep(float(script().get("delay", {}).get("hello", 0)))
    write({"type": "hello", "protocol": "baxy.mind.v1", "models": {"llm": "fake"}, "requests": REQUESTS})
    pending: queue.Queue = queue.Queue()

    def read() -> None:
        for line in sys.stdin:
            if not line.strip():
                continue
            message = json.loads(line)
            seen(message)
            if message.get("type") in READER:
                answer(message)
            else:
                pending.put(message)
        pending.put(None)

    threading.Thread(target=read, daemon=True).start()
    while (message := pending.get()) is not None:
        answer(message)


main()
