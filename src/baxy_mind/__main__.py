"""Sidecar entry: speaks baxy.mind.v1 with the App over JSONL (see protocol.py)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from . import protocol
from .llm_server import LlmServer
from .mind import Mind
from .voice import Voice

UNSUPPORTED = {"plan", "plan.ground", "computer.use.step", "narrate", "message.send", "voice.speak", "arguments",
               "message.compose"}


def main() -> int:
    gguf = os.environ.get("BAXY_MIND_LLM_GGUF", "")
    server_path = os.environ.get("BAXY_MIND_LLAMA_SERVER", "")
    if not gguf or not server_path:
        sys.stderr.write("baxy_mind_renew_failure: BAXY_MIND_LLM_GGUF and BAXY_MIND_LLAMA_SERVER are required\n")
        return 2
    extra = os.environ.get("BAXY_RENEW_SERVER_ARGS", "").split()
    server = LlmServer(gguf, server_path, os.environ.get("BAXY_MIND_NGL", "99"),
                       context=int(os.environ.get("BAXY_RENEW_CTX", "40960")), extra_args=extra)
    server.start()
    trace = Path(os.environ.get("LOCALAPPDATA", ".")) / "BAXY" / "renew" / "turns.jsonl"
    trace.parent.mkdir(parents=True, exist_ok=True)
    mind = Mind(server, trace)
    voice = Voice(protocol.write_message)  # loads beside the model; turns never wait for it
    protocol.write_message({
        "type": "hello", "protocol": protocol.PROTOCOL, "mindVersion": "renew-0.1",
        "models": {"llm": server.name},
        "requests": ["catalog.configure", "turn.decide", "turn.continue", "turn.confirm", "session.new",
                     "voice.start", "voice.stop", "voice.status", "voice.cancel", "shutdown"],
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
                    except Exception as error:  # noqa: BLE001 - told to the App as a startup failure
                        reply = protocol.error_reply(request_id, "request_failed", "catalog_runtime_failure")
                        reply["startup"] = server.startup_failure(error)
                        protocol.write_message(reply)
                        continue
                    protocol.write_message({"type": "catalog.ready", "id": request_id, "count": count})
                elif kind == "turn.decide":
                    protocol.write_message(mind.decide(request_id, str(message.get("text") or "")))
                elif kind == "turn.continue":
                    protocol.write_message(mind.continue_turn(request_id, str(message.get("observation") or ""),
                                                              bool(message.get("final"))))
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
                elif kind == "voice.cancel":
                    # Nothing is spoken yet (no text to speech in Renew), so there is nothing to cancel.
                    protocol.write_message({"type": "voice.cancelled", "id": request_id})
                elif kind == "shutdown":
                    protocol.write_message({"type": "shutdown.ack", "id": request_id})
                    break
                elif kind in UNSUPPORTED:
                    protocol.write_message(protocol.error_reply(request_id, "unsupported_request",
                                                                f"{kind}_unavailable_in_renew"))
                else:
                    protocol.write_message(protocol.error_reply(request_id, "unknown_request", kind))
            except Exception as error:  # noqa: BLE001 - one failed request never ends the sidecar
                surface = {"turn.decide": "turn", "turn.continue": "turn", "turn.confirm": "turn"}.get(kind, "request")
                sys.stderr.write(f"baxy_mind_renew_failure:{kind}:{error!r}\n")
                sys.stderr.flush()
                protocol.write_message(protocol.error_reply(request_id, "request_failed",
                                                            f"{surface}_runtime_failure"))
    finally:
        voice.stop()
        server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
