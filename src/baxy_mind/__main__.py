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
from .early import Anticipation, early_silence, wake_warm
from .llm_server import LlmServer, declared_build
from .mind import Mind
from .system_one import SystemOne
from .voice import Voice


# BAXY Renew al máximo 11.6: the trace keeps every turn's rows (the person's words among them) on this PC, so it has a
# cap: past it when the mind starts, it becomes turns.jsonl.1 (the one before is dropped) and a new one begins. It stays
# in %LOCALAPPDATA%\BAXY\renew (a bench's run folder with BAXY_RENEW_TRACE_DIR: trace_dir): catalog.configure.json is
# written beside it (mind.py) and the benches read it there.
TRACE_LIMIT_BYTES = 50 * 1024 * 1024

# Al máximo W5: the requests after which the conversation may be read ahead for the next one (Mind.prefill decides
# whether a turn is left open): a turn's last answer, a heartbeat's end and a kept session's load.
PREFILLED_AFTER = ("turn.decide", "turn.continue", "turn.beat.end", "session.load")


def trace_dir(environ: dict[str, str] | None = None) -> Path:
    """Where the trace and catalog.configure.json go: BAXY_RENEW_TRACE_DIR when given, else %LOCALAPPDATA%\\BAXY\\renew.
    Audit w8-medir (2026-10-23): the benches that drive the product (e2e, falsedades, resources) wrote every bench turn
    into the owner's own turns.jsonl, mixed with his real turns and, past the cap, rotating them out; they set it to
    their run's folder."""
    source = os.environ if environ is None else environ
    given = source.get("BAXY_RENEW_TRACE_DIR", "").strip()
    return Path(given) if given else Path(source.get("LOCALAPPDATA", ".")) / "BAXY" / "renew"


def bounded_trace(trace: Path, limit: int = TRACE_LIMIT_BYTES) -> Path:
    trace.parent.mkdir(parents=True, exist_ok=True)
    try:
        if trace.stat().st_size > limit:
            os.replace(trace, trace.with_name(trace.name + ".1"))
    except FileNotFoundError:
        pass  # the first start: nothing to cap
    return trace


def main() -> int:
    gguf = os.environ.get("BAXY_MIND_LLM_GGUF", "")
    server_path = os.environ.get("BAXY_MIND_LLAMA_SERVER", "")
    if not gguf or not server_path:
        sys.stderr.write("baxy_mind_renew_failure: BAXY_MIND_LLM_GGUF and BAXY_MIND_LLAMA_SERVER are required\n")
        return 2
    try:
        # w11-llama (2026-10-25): only a declared llama-server starts, Qwen's and System One's (the same binary).
        build = declared_build(server_path)
        # Renew al máximo 1.5 (2026-10-22): 53,248 and not 49,152. With the ~43k-token prefix the history had ~2.5k
        # tokens (about three turns); 4,096 more cost ~68 MiB of KV (8 full-attention layers × 4 KV heads × 256, q8_0),
        # room left once Laya stopped using the GPU (3.1: 3,902 MiB with System One on).
        server = LlmServer(gguf, server_path, os.environ.get("BAXY_MIND_NGL", "99"),
                           context=int(os.environ.get("BAXY_RENEW_CTX", "53248")))
    except RuntimeError as error:  # an undeclared server, or a pinned port in use (llm_server._pinned_port)
        sys.stderr.write(f"baxy_mind_renew_failure: {error}\n")
        return 2
    server.start()
    # System One, layer 2: the decision model on the CPU, beside Qwen, when its GGUF is given (off otherwise).
    system_one = None
    if os.environ.get("BAXY_S1_GGUF", "").strip():
        system_one = SystemOne(os.environ["BAXY_S1_GGUF"].strip(), server_path,
                               int(os.environ.get("BAXY_S1_THREADS", "4") or 4))
        system_one.start()
    trace = bounded_trace(trace_dir() / "turns.jsonl")
    mind = Mind(server, trace, system_one)
    def spoken(queued: float, sounded: float, notice: bool) -> None:
        # From the App's voice.speak to the first sound, and when it sounded (the turn's own rows say when its text
        # reached the mind), so text-to-first-sound is read from this trace; a notice's row says so.
        mind._log("voice.speak", queued, None, sound_ms=round((sounded - queued) * 1000), notice=notice,
                  sound_at=(_dt.datetime.now() + _dt.timedelta(seconds=sounded - time.perf_counter()))
                  .isoformat(timespec="milliseconds"))

    # The reader answers voice.speak, voice.cancel and voice.status as they arrive, so they never wait for an inference
    # (the App's notice at 2 s of silence and a barge-in's cancel reached the voice only after the model finished, round
    # 2 of nb-aviso); every other request keeps its order on this loop, as ("request", when it arrived, the message).
    # None ends it (the App closed stdin); an int is the exit code (a protocol violation, or the pipe failing). The voice
    # puts its own items here too (al máximo, palancas 2 y 5, early.py): ("early", n, text), ("cancel", n), ("wake",).
    pending: queue.Queue[tuple | int | None] = queue.Queue()
    anticipation = Anticipation(mind, warm=wake_warm())
    early_s = early_silence()

    def early(seq: int, text: str | None) -> None:
        if text is None:
            anticipation.cancel(seq)  # stops a decision being made now; the loop puts back one already made
            pending.put(("cancel", seq))
        else:
            pending.put(("early", seq, text))

    voice = Voice(protocol.write_message, spoken, on_early=early if early_s else None, early_s=early_s or 0.0,
                  on_wake=(lambda: pending.put(("wake",))) if anticipation.warm else None)  # loads beside the model
    mind.foresee = voice.speech.foresee  # the last answer's first sentence is synthesized while it is written
    protocol.write_message({
        "type": "hello", "protocol": protocol.PROTOCOL,
        "models": {"llm": server.name, "server": build},
        "requests": ["catalog.configure", "turn.decide", "turn.continue", "turn.confirm", "turn.beat", "turn.beat.end",
                     "session.new", "session.export", "session.load", "trace.forget",
                     "voice.start", "voice.stop", "voice.release", "voice.status", "voice.speak", "voice.cancel"],
    })
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
                    # sounds once it is loaded, but the turn's notice says the turn is under way: heard after the
                    # answer is on screen it would say something false, so it is only taken with its audio ready
                    # (Speech.speak). The notice is the model's phrase sent with catalog.ready (al máximo 9.2a).
                    text = str(message.get("text") or "")
                    notice = mind.notice
                    accepted = voice.speech.speak(text, notice=bool(notice) and text == notice)
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
                    pending.put(("request", time.perf_counter(), message))
        except Exception as error:  # noqa: BLE001 - the pipe failed: the loop ends instead of waiting forever
            sys.stderr.write(f"baxy_mind_renew_failure:reader:{error!r}\n")
            sys.stderr.flush()
            pending.put(74)

    threading.Thread(target=read, name="mind-reader", daemon=True).start()
    try:
        while True:
            try:
                item = pending.get(timeout=anticipation.patience())
            except queue.Empty:
                anticipation.expire()  # an early decision nobody asked for is put back
                continue
            if isinstance(item, int):
                return item
            if item is None:
                break
            if item[0] != "request":
                # The voice's own items, between requests, on their own budget.
                server.deadline = time.monotonic() + LlmServer.REQUEST_SECONDS
                try:
                    if item[0] == "early":
                        anticipation.speculate(item[1], item[2])
                    elif item[0] == "cancel":
                        anticipation.drop("cancelled", item[1])
                    elif item[0] == "wake":
                        anticipation.wake()
                except Exception as error:  # noqa: BLE001 - the requests decide as always
                    sys.stderr.write(f"baxy_mind_renew_failure:{item[0]}:{error!r}\n")
                    sys.stderr.flush()
                continue
            _, arrived, message = item
            request_id, kind = message.get("id"), str(message.get("type"))
            # Review 2026-10-22: a request's calls to the model share one budget under the App's 30 s, except the
            # warm-up and a kept session's load (LlmServer.REQUEST_SECONDS).
            server.deadline = (None if kind in ("catalog.configure", "session.load")
                               else time.monotonic() + LlmServer.REQUEST_SECONDS)
            # Al máximo, palanca 2: a decision made early is this request's reply when it is the one it would make;
            # any other request (a voice request aside) finds the mind as it was before it.
            held = anticipation.settle(kind, message, arrived) if kind not in ("voice.start", "voice.stop") else None
            try:
                if kind == "catalog.configure":
                    count = mind.configure(message)
                    voice.hear_names(mind.names)  # the ear's hotwords: what the model is shown is what it may hear
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
                    # The notice the model wrote at warm-up (empty: none is said); the voice synthesizes it now.
                    voice.speech.set_notice(mind.notice)
                    protocol.write_message({"type": "catalog.ready", "id": request_id, "count": count,
                                            "notice": mind.notice})
                elif kind == "turn.decide":
                    voice.speech.prepare()  # the output opens while the model decides
                    protocol.write_message(held or anticipation.decide(request_id, str(message.get("text") or ""),
                                                                       message.get("pendingConfirmation")))
                elif kind == "turn.continue":
                    # After a tool the answer may come long after the output closed (HOLD_S 20 s; file.find 11-14 s,
                    # web.fetch up to 160 s): it opens again (0.38 s on the PC) while the model writes it.
                    if not message.get("beat"):
                        voice.speech.prepare()
                    protocol.write_message(mind.continue_turn(request_id, str(message.get("observation") or ""),
                                                              bool(message.get("final")), bool(message.get("beat"))))
                elif kind == "turn.beat":
                    protocol.write_message(mind.beat(request_id, dict(message.get("context") or {})))
                elif kind == "turn.beat.end":
                    mind.end_beat()
                    protocol.write_message({"type": "turn.beat.ended", "id": request_id})
                elif kind == "turn.confirm":
                    voice.speech.prepare()  # the person's «sí» or «no» is answered aloud too
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
                elif kind == "trace.forget":
                    # The person had BAXY forget everything or deleted every conversation (the App deletes its own
                    # conversation log then): the trace and the slot states that hold their words go too.
                    cleared = mind.forget_trace() & server.forget_set_aside()
                    mind._log("trace.forget", time.perf_counter(), None, cleared=cleared)
                    protocol.write_message({"type": "trace.forgotten", "id": request_id, "cleared": cleared})
                elif kind == "voice.start":
                    mode = str(message.get("mode") or "direct")
                    if voice.start(mode):
                        protocol.write_message({"type": "voice.started", "id": request_id, "mode": mode})
                        if mode == "direct":
                            anticipation.wake()  # palanca 5: the button opened a request, as «Baxy» does
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
            if kind in PREFILLED_AFTER:
                # Al máximo W5: the reply is already out; with no turn left open, the conversation is read as the next
                # request will show it (Mind.prefill), on a budget of its own, while BAXY speaks. A request that comes
                # meanwhile waits for it, and then does not read it itself.
                server.deadline = time.monotonic() + LlmServer.REQUEST_SECONDS
                try:
                    mind.prefill()
                except Exception as error:  # noqa: BLE001 - the next request reads it itself
                    sys.stderr.write(f"baxy_mind_renew_failure:prefill:{error!r}\n")
                    sys.stderr.flush()
    finally:
        voice.stop()
        voice.speech.close()
        server.close()
        if system_one is not None:
            system_one.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
