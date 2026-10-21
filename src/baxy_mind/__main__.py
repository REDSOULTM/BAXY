"""Sidecar entry: speaks baxy.mind.v1 with the App over JSONL (see protocol.py)."""
from __future__ import annotations

import datetime as _dt
import os
import queue
import sys
import threading
import time
from pathlib import Path

from . import protocol
from .llm_server import LlmServer
from .mind import NOTICE, Mind
from .voice import Voice


def main() -> int:
    gguf = os.environ.get("BAXY_MIND_LLM_GGUF", "")
    server_path = os.environ.get("BAXY_MIND_LLAMA_SERVER", "")
    if not gguf or not server_path:
        sys.stderr.write("baxy_mind_renew_failure: BAXY_MIND_LLM_GGUF and BAXY_MIND_LLAMA_SERVER are required\n")
        return 2
    server = LlmServer(gguf, server_path, os.environ.get("BAXY_MIND_NGL", "99"),
                       context=int(os.environ.get("BAXY_RENEW_CTX", "49152")))
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
        "type": "hello", "protocol": protocol.PROTOCOL,
        "models": {"llm": server.name},
        "requests": ["catalog.configure", "turn.decide", "turn.continue", "turn.confirm", "turn.beat", "turn.beat.end",
                     "session.new", "session.export", "session.load",
                     "voice.start", "voice.stop", "voice.release", "voice.status", "voice.speak", "voice.cancel"],
    })
    # The reader answers voice.speak, voice.cancel and voice.status as they arrive, so they never wait for an inference
    # (the App's notice at 2 s of silence and a barge-in's cancel reached the voice only after the model finished, round
    # 2 of nb-aviso); every other request keeps its order on this loop. None ends it (the App closed stdin); an int is
    # the exit code (a protocol violation, or the pipe failing).
    pending: queue.Queue[dict | int | None] = queue.Queue()

    def read() -> None:
        try:
            while True:
                try:
                    message = protocol.read_message()
                except protocol.ProtocolViolation as violation:
                    protocol.write_message(protocol.error_reply(None, violation.code, violation.detail))
                    pending.put(65)
                    return
                if message is None:
                    pending.put(None)
                    return
                if not message:
                    continue
                kind = str(message.get("type"))
                if kind == "voice.speak":
                    # FT/proveedores goal (review of E001's fix): an answer asked while the voice loads waits and
                    # sounds once it is loaded, but the turn's «Un momento.» says the turn is under way: heard after
                    # the answer is on screen it would say something false, so it is only taken from a loaded voice.
                    text = str(message.get("text") or "")
                    accepted = (voice.speech.ready or text != NOTICE) and voice.speech.speak(text,
                                                                                            notice=text == NOTICE)
                    protocol.write_message({"type": "voice.speak.result", "id": message.get("id"),
                                            "accepted": accepted})
                elif kind == "voice.cancel":
                    voice.speech.cancel()
                    protocol.write_message({"type": "voice.cancelled", "id": message.get("id")})
                elif kind == "voice.status":
                    protocol.write_message({"type": "voice.status.result", "id": message.get("id"),
                                            "status": voice.status()})
                elif kind == "voice.release":
                    voice.release()
                    protocol.write_message({"type": "voice.released", "id": message.get("id")})
                else:
                    pending.put(message)
        except Exception as error:  # noqa: BLE001 - the pipe failed: the loop ends instead of waiting forever
            sys.stderr.write(f"baxy_mind_renew_failure:reader:{error!r}\n")
            sys.stderr.flush()
            pending.put(74)

    threading.Thread(target=read, name="mind-reader", daemon=True).start()
    try:
        while True:
            message = pending.get()
            if isinstance(message, int):
                return message
            if message is None:
                break
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
                    protocol.write_message({"type": "catalog.ready", "id": request_id, "count": count,
                                            "notice": NOTICE})
                elif kind == "turn.decide":
                    voice.speech.prepare()  # the output opens while the model decides
                    protocol.write_message(mind.decide(request_id, str(message.get("text") or ""),
                                                       message.get("pendingConfirmation")))
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
                elif kind == "session.export":
                    protocol.write_message({"type": "session.exported", "id": request_id,
                                            "conversation": mind.export_session()})
                elif kind == "session.load":
                    conversation = message.get("conversation")
                    mind.load_session(conversation if isinstance(conversation, list) else [])
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
