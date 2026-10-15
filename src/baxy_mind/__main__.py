"""Sidecar entry: speaks baxy.mind.v1 with the App over JSONL (see protocol.py)."""
from __future__ import annotations

import datetime as _dt
import os
import sys
import time
from pathlib import Path

from . import protocol
from .llm_server import LlmServer
from .mind import Mind
from .voice import Voice


def main() -> int:
    gguf = os.environ.get("BAXY_MIND_LLM_GGUF", "")
    server_path = os.environ.get("BAXY_MIND_LLAMA_SERVER", "")
    if not gguf or not server_path:
        sys.stderr.write("baxy_mind_renew_failure: BAXY_MIND_LLM_GGUF and BAXY_MIND_LLAMA_SERVER are required\n")
        return 2
    extra = os.environ.get("BAXY_RENEW_SERVER_ARGS", "").split()
    server = LlmServer(gguf, server_path, os.environ.get("BAXY_MIND_NGL", "99"),
                       context=int(os.environ.get("BAXY_RENEW_CTX", "49152")), extra_args=extra)
    server.start()
    trace = Path(os.environ.get("LOCALAPPDATA", ".")) / "BAXY" / "renew" / "turns.jsonl"
    trace.parent.mkdir(parents=True, exist_ok=True)
    mind = Mind(server, trace)
    def spoken(queued: float, sounded: float) -> None:
        # From the App's voice.speak to the first sound, and when it sounded (the turn's own rows say when its text
        # reached the mind), so text-to-first-sound is read from this trace.
        mind._log("voice.speak", queued, None, sound_ms=round((sounded - queued) * 1000),
                  sound_at=(_dt.datetime.now() + _dt.timedelta(seconds=sounded - time.monotonic()))
                  .isoformat(timespec="milliseconds"))

    voice = Voice(protocol.write_message, spoken)  # loads beside the model; turns never wait for it
    protocol.write_message({
        "type": "hello", "protocol": protocol.PROTOCOL, "mindVersion": "renew-0.1",
        "models": {"llm": server.name},
        "requests": ["catalog.configure", "turn.decide", "turn.continue", "turn.confirm", "turn.beat", "turn.beat.end",
                     "session.new",
                     "voice.start", "voice.stop", "voice.status", "voice.speak", "voice.cancel", "shutdown"],
    })
    try:
        while True:
            try:
                message = protocol.read_message()
            except protocol.ProtocolViolation as violation:
                protocol.write_message(protocol.error_reply(None, violation.code, violation.detail))
                return 65
            if message is None:
                break
            if not message:
                continue
            request_id, kind = message.get("id"), str(message.get("type"))
            try:
                if kind == "catalog.configure":
                    count = mind.configure(message)
                    # Ready means ready: the model is loaded and the catalog prefix is cached before the App is told so
                    # (a first turn sent earlier waited behind the warm-up and timed out, 2026-10-15).
                    try:
                        server.wait_ready(600)
                        mind.warm()
                    except Exception:  # noqa: BLE001 - told to the App as a startup failure
                        reply = protocol.error_reply(request_id, "request_failed", "catalog_runtime_failure")
                        reply["startup"] = server.startup_failure()
                        protocol.write_message(reply)
                        continue
                    protocol.write_message({"type": "catalog.ready", "id": request_id, "count": count})
                elif kind == "turn.decide":
                    voice.speech.prepare()  # the output opens while the model decides
                    protocol.write_message(mind.decide(request_id, str(message.get("text") or "")))
                elif kind == "turn.continue":
                    protocol.write_message(mind.continue_turn(request_id, str(message.get("observation") or ""),
                                                              bool(message.get("final")), bool(message.get("beat"))))
                elif kind == "turn.beat":
                    protocol.write_message(mind.beat(request_id, dict(message.get("context") or {})))
                elif kind == "turn.beat.end":
                    mind.end_beat()
                    protocol.write_message({"type": "turn.beat.ended", "id": request_id})
                elif kind == "turn.confirm":
                    protocol.write_message(mind.confirm(request_id, bool(message.get("approve")),
                                                        str(message.get("label") or "")))
                elif kind == "session.new":
                    mind.new_session()
                    protocol.write_message({"type": "session.ready", "id": request_id})
                elif kind == "voice.start":
                    mode = str(message.get("mode") or "direct")
                    if voice.start(mode):
                        protocol.write_message({"type": "voice.started", "id": request_id, "mode": mode})
                    else:
                        protocol.write_message(protocol.error_reply(request_id, "voice_unavailable",
                                                                    voice.failure or "voice_unavailable"))
                elif kind == "voice.stop":
                    voice.stop()
                    protocol.write_message({"type": "voice.stopped", "id": request_id})
                elif kind == "voice.status":
                    protocol.write_message({"type": "voice.status.result", "id": request_id, "status": voice.status()})
                elif kind == "voice.speak":
                    protocol.write_message({"type": "voice.speak.result", "id": request_id,
                                            "accepted": voice.speech.speak(str(message.get("text") or ""))})
                elif kind == "voice.cancel":
                    voice.speech.cancel()
                    protocol.write_message({"type": "voice.cancelled", "id": request_id})
                elif kind == "shutdown":
                    protocol.write_message({"type": "shutdown.ack", "id": request_id})
                    break
                else:
                    protocol.write_message(protocol.error_reply(request_id, "unknown_request", kind))
            except Exception as error:  # noqa: BLE001 - one failed request never ends the sidecar
                surface = {"turn.decide": "turn", "turn.continue": "turn", "turn.confirm": "turn",
                           "turn.beat": "turn"}.get(kind, "request")
                sys.stderr.write(f"baxy_mind_renew_failure:{kind}:{error!r}\n")
                sys.stderr.flush()
                protocol.write_message(protocol.error_reply(request_id, "request_failed",
                                                            f"{surface}_runtime_failure"))
    finally:
        voice.stop()
        voice.speech.close()
        server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
