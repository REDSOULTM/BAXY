"""Sidecar entry: speaks baxy.mind.v1 with the App over JSONL (see protocol.py)."""
from __future__ import annotations

import datetime as _dt
import os
import queue
import sys
import urllib.error
import threading
import time
import urllib.request
from concurrent import futures
from pathlib import Path

from . import behavior, protocol
from .early import Anticipation, early_silence, wake_warm
from .llm_server import LlmServer, declared_backend, declared_build, progress_facts
from .mind import Mind
from .speech_text import Utterance
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

# Uso-124: a person's requests that may read a long prompt, each lasting while the model server advances
# (LlmServer._advance). Not a heartbeat's: the person's next words wait for it to end (MainWindowViewModel, _turnGate).
REQUESTS_THAT_READ = ("turn.decide", "turn.continue", "turn.confirm")

# Feria 2026-10-27: how long a turn's notice waits for its audio before it is answered; past it the notice is not said
# (the call may be over by then).
NOTICE_VOICE_S = 1.5


def trace_dir(environ: dict[str, str] | None = None) -> Path:
    """Where the trace and catalog.configure.json go: BAXY_RENEW_TRACE_DIR when given, else %LOCALAPPDATA%\\BAXY\\renew.
    Audit w8-medir (2026-10-23): the benches that drive the product (e2e, falsedades, resources) wrote every bench turn
    into the owner's own turns.jsonl, mixed with his real turns and, past the cap, rotating them out; they set it to
    their run's folder."""
    source = os.environ if environ is None else environ
    given = source.get("BAXY_RENEW_TRACE_DIR", "").strip()
    return Path(given) if given else Path(source.get("LOCALAPPDATA", ".")) / "BAXY" / "renew"


def trace_words(environ: dict[str, str] | None = None) -> bool:
    """Whether the trace keeps what was said (the person's words, BAXY's answers, each call's arguments). PRV1 (PRIV-02,
    2026-11-09): not in the product, whose trace is for times and names (Mind.TRACE_FACTS). A bench's run keeps it (its
    own folder, BAXY_RENEW_TRACE_DIR, read by its tools), and so does a PC whose owner asks for it, BAXY_TRACE_WORDS=1
    (the App's conversation log reads the same variable). UNI1 (REV8 P3): «1» or another usual way of saying yes (y, yes,
    t, true, on, as the standard library's strtobool read it), as the App reads it (ConversationLog.KeepsWords)."""
    source = os.environ if environ is None else environ
    return (source.get("BAXY_TRACE_WORDS", "").strip().lower() in TRACE_WORDS_YES
            or bool(source.get("BAXY_RENEW_TRACE_DIR", "").strip()))


TRACE_WORDS_YES = frozenset({"1", "y", "yes", "t", "true", "on"})


def bounded_trace(trace: Path, limit: int = TRACE_LIMIT_BYTES) -> Path:
    trace.parent.mkdir(parents=True, exist_ok=True)
    try:
        if trace.stat().st_size > limit:
            os.replace(trace, trace.with_name(trace.name + ".1"))
    except FileNotFoundError:
        pass  # the first start: nothing to cap
    except OSError as error:
        # Another process holds one of the files open (Windows): the trace goes on where it is and is capped at the next
        # start; the PermissionError ended the start, with llama-server already running.
        sys.stderr.write(f"baxy_mind_renew_trace: not rotated: {error!r}\n")
    return trace


def ready_facts(server: LlmServer, prefix_tokens: int) -> dict:
    """What catalog.ready says beside its count. With what the server keeps known, the App's ceiling for a turn's request
    follows the mind's own, and the App knows whether the processor computes the model. Settings → Model → Context
    (LocalContext in the App) takes the backend, for each preset's video memory, and the prompt prefix's tokens as read,
    for the room each one leaves. VRAM4: and the cells the server started with, which on a card short of video memory are
    fewer than the automatic ones (LlmServer.start), with what it found free when not even those fit whole (cardShort)."""
    return {"ceiling_s": server.ceiling_s,
            **{key: value for key, value in progress_facts(server).items() if key == "onProcessor"},
            "backend": server.backend, "prefixTokens": prefix_tokens, "context": server.context,
            **({"cardShort": server.card_short} if server.card_short else {})}


def main() -> int:
    # Every address the mind asks is its server on this PC. A proxy set on this PC would take the conversation away, or if it
    # refuses, leave BAXY with no model: urllib only passes it by for a name without dots, and 127.0.0.1 has them.
    urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
    gguf = os.environ.get("BAXY_MIND_LLM_GGUF", "")
    server_path = os.environ.get("BAXY_MIND_LLAMA_SERVER", "")
    if not gguf or not server_path:
        sys.stderr.write("baxy_mind_renew_failure: BAXY_MIND_LLM_GGUF and BAXY_MIND_LLAMA_SERVER are required\n")
        return 2
    try:
        # w11-llama (2026-10-25): only a declared llama-server starts, Qwen's and System One's (the same binary).
        # A remote server (BAXY_MIND_LLAMA_REMOTE, measurement only) is not this machine's binary: nothing to hash, and
        # its settings are the declared CUDA ones (the measurement pods are NVIDIA).
        remote = os.environ.get("BAXY_MIND_LLAMA_REMOTE", "").strip()
        build = f"remoto:{remote}" if remote else declared_build(server_path)
        # Encargo 8 (2026-11-02): the folder's GPU backend, by its DLL's SHA-256: the server's settings depend on it
        # (llm_server.flash_attention, default_context, slots).
        backend = "cuda" if remote else declared_backend(server_path, build)
        # uso-101: the App picked this folder for this machine's GPU (MindRuntimeDiscovery). llama-server.exe is the same
        # file in a package's two folders: the backend's DLL is what tells them apart.
        chosen = os.environ.get("BAXY_MIND_LLAMA_BACKEND", "").strip()
        if chosen and not remote and backend != chosen:
            raise RuntimeError(f"the folder of {server_path} is {backend}, not the {chosen} this machine's GPU needs")
        # The context is BAXY_RENEW_CTX's, or the one that fits the backend's budget with its cache
        # (llm_server.default_context; uso-51: 77,824 on CUDA inside 4 GB of VRAM).
        asked = os.environ.get("BAXY_RENEW_CTX", "").strip()
        layers = os.environ.get("BAXY_MIND_NGL", "99")
        server = LlmServer(gguf, server_path, layers, context=int(asked) if asked else None, backend=backend)
    except RuntimeError as error:  # an undeclared server or backend, or a pinned port in use (llm_server._pinned_port)
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
    mind.trace_words = trace_words()
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
    # NB-R1 2026-10-27: a read ahead (a turn's warm.history, the wake's) gives way to whatever waits here.
    server.yields = lambda: not pending.empty()
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
    # uso-82 (AMD e2e 2026-11-04): voice.speak is offered only by a voice that can speak, loaded or loading with its
    # files there (Speech fails at once without them). Offered always, a PC with no voice (BAXY_RENEW_TTS_DIR empty or
    # unset) had the App wait for every answer to sound, and each turn ended 10 s late (ProductConductorHost).
    speaks = ["voice.speak"] if not voice.speech.failure else []
    protocol.write_message({
        "type": "hello", "protocol": protocol.PROTOCOL,
        "models": {"llm": server.name, "server": build},
        "requests": ["catalog.configure", "turn.decide", "turn.continue", "turn.confirm", "turn.beat", "turn.beat.end",
                     "turn.notice", "session.new", "session.export", "session.title", "session.load", "trace.forget",
                     "voice.start", "voice.stop", "voice.release", "voice.status", *speaks, "voice.cancel"],
        # Ajustes → Comportamiento: the fixed identity, the factory texts the person's own replace (behavior.py), and how
        # long each may be.
        "behavior": {"identity": behavior.IDENTITY, "factory": behavior.factory(), "maxChars": behavior.MAX_CHARS},
        # VRAM4B: the card holds a smaller ready-made profile than the factory's, which the person never chose: said
        # before the catalog comes, so the App configures this run with that profile's tools (LlmServer.card_fit).
        **({"card": server.card_fit} if getattr(server, "card_fit", None) else {}),
        # VRAM4D (REV18 R18-2): the card's whole memory and whether it is short: only then does the App keep that profile.
        **({"cardMemory": server.card_memory} if getattr(server, "card_memory", None) else {}),
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
                if kind in ("turn.decide", "turn.notice") and message.get("lang") is not None:
                    # Steam in English: the turn says the language its answer will be said in, here as it arrives,
                    # before the answer is foreseen or the notice made. Only the voice reads it, never the model.
                    voice.speech.speak_in(message.get("lang"))
                if kind == "voice.speak":
                    # FT/proveedores goal (review of E001's fix): an answer asked while the voice loads waits and
                    # sounds once it is loaded, but the turn's notice says the turn is under way: heard after the
                    # answer is on screen it would say something false, so it is only taken with its audio ready
                    # (Speech.speak). The App marks it: the phrase the model wrote for the turn (turn.notice).
                    # Steam in English: «lang» is the language it is said in, «en» with the interface in English; an
                    # App that sends none (or another tag) is answered in Spanish, as always (speech_text.language).
                    accepted = voice.speech.speak(Utterance(str(message.get("text") or ""), message.get("lang")),
                                                  notice=bool(message.get("notice")))
                    # uso-82: a voice whose load failed after the hello says it no longer speaks, and the App stops
                    # asking and waiting for it (MindSidecarClient.VoiceSpeakAsync).
                    protocol.write_message({"type": "voice.speak.result", "id": message.get("id"),
                                            "accepted": accepted, "speaks": not voice.speech.failure})
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
            if mind.gave_way is not None and pending.empty() and anticipation.patience() is None:
                # A read ahead gave way to a request (the App's session.export after every turn, review of NB-R1-X4):
                # with that answered and nothing waiting or held, it is read now, on a budget of its own.
                server.deadline = time.monotonic() + LlmServer.REQUEST_SECONDS
                try:
                    mind.prefill(mind.gave_way)
                except Exception as error:  # noqa: BLE001 - the next request reads it itself
                    sys.stderr.write(f"baxy_mind_renew_failure:prefill:{error!r}\n")
                    sys.stderr.flush()
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
                server.advanced = None
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
            # warm-up and a kept session's load (LlmServer.REQUEST_SECONDS). Revisión PCR1 (A3): from when it arrived,
            # as the App's window and ceiling count from when it sent it: one that waited here behind the voice's items
            # has that much less, and the mind still gives up before the App.
            server.deadline = (None if kind in ("catalog.configure", "session.load")
                               else time.monotonic() - (time.perf_counter() - arrived) + LlmServer.REQUEST_SECONDS)
            # Uso-124: while the model server advances this request lasts, and the App's own window for it starts again
            # (each «progress» line, as for a start; MindSidecarClient).
            server.advanced = ((lambda rid=request_id: protocol.write_message({"type": "progress", "id": rid}))
                               if kind in REQUESTS_THAT_READ and not message.get("beat") else None)
            # Al máximo, palanca 2: a decision made early is this request's reply when it is the one it would make;
            # any other request (a voice request aside) finds the mind as it was before it.
            unsure = voice.unsure(str(message.get("text") or "")) if kind == "turn.decide" else []
            mind.arrived, mind.app_ms = (arrived, message.get("waitedMs")) if kind == "turn.decide" else (None, None)
            held = (anticipation.settle(kind, message, arrived, unsure) if kind not in ("voice.start", "voice.stop")
                    else None)
            try:
                if kind == "catalog.configure":
                    count = mind.configure(message)
                    voice.hear_names(mind.heard)  # the ear's hotwords: the names the model is shown or BAXY knows
                    # Ready means ready: the model is loaded and the catalog prefix is cached before the App is told so
                    # (a first turn sent earlier waited behind the warm-up and timed out, 2026-10-15). Each advance of
                    # the server through the prefix is told to the App (uso 84): it waits while they come, never on a
                    # fixed budget a slow GPU would run out (LlmServer.read_prefix).
                    try:
                        server.wait_ready(600)
                        mind.warm(lambda done, total, rid=request_id: protocol.write_message(
                            {"type": "progress", "id": rid, "done": done, "total": total, **progress_facts(server)}))
                    except Exception as error:  # noqa: BLE001 - told to the App as a startup failure
                        reply = protocol.error_reply(request_id, "request_failed", "catalog_runtime_failure")
                        reply["startup"] = server.startup_failure(error)
                        protocol.write_message(reply)
                        continue
                    protocol.write_message({"type": "catalog.ready", "id": request_id, "count": count,
                                            **ready_facts(server, mind.prefix_tokens)})
                elif kind == "turn.decide":
                    voice.speech.prepare()  # the output opens while the model decides
                    front = message.get("front") if isinstance(message.get("front"), dict) else None
                    named = message.get("named") if isinstance(message.get("named"), list) else None
                    ringing = message.get("ringing") if isinstance(message.get("ringing"), list) else None
                    # RUT1: the person's routines (RoutinesHandler's store); none sent is none kept.
                    mind.routines = message["routines"] if isinstance(message.get("routines"), list) else []
                    # MEM8C (REV20 M-1): what the memory keeps now, as the App knows it this turn; none sent, not known.
                    records = message.get("memoryRecords")
                    mind.memory_records = records if isinstance(records, int) and not isinstance(records, bool) \
                        and records >= 0 else None
                    if message.get("lang") in ("es", "en"):
                        mind.lang = message["lang"]  # ALR4: ring_answer's sentence, when the words are both languages'
                    protocol.write_message(held or anticipation.decide(request_id, str(message.get("text") or ""),
                                                                       message.get("pendingConfirmation"), unsure,
                                                                       front, named, ringing))
                elif kind == "turn.continue":
                    # After a tool the answer may come long after the output closed (HOLD_S 20 s; file.find 11-14 s,
                    # web.fetch up to 160 s): it opens again (0.38 s on the PC) while the model writes it.
                    if not message.get("beat"):
                        voice.speech.prepare()
                    # TPV7: the tool the person's «sí» just turned on (NativeTurnLoop.AnswerOffHeld), whole, for this
                    # turn's next request (Mind.tool_on).
                    if isinstance(message.get("toolOn"), dict):
                        mind.tool_on(message["toolOn"])
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
                elif kind == "turn.notice":
                    # The App's turn has been silent SilenceNotice.After while its call runs: the model writes the
                    # notice for that call, and it is answered once the voice holds its audio, so the voice.speak
                    # that follows never waits for a synthesis an answer may need (Speech.set_notice). With no voice
                    # loaded nothing would be said: the model is not asked. It gives way to any request already
                    # waiting (NB-L 2026-10-27: the call's result must never wait behind its notice), before it is
                    # written and while its audio is made.
                    phrase = mind.notice_of() if voice.speech.ready and pending.empty() else ""
                    audio = voice.speech.set_notice(phrase) if phrase else None
                    until = time.monotonic() + NOTICE_VOICE_S
                    while audio is not None and not audio.done() and pending.empty() and time.monotonic() < until:
                        futures.wait([audio], 0.02)
                    if audio is None or not audio.done() or audio.cancelled() or audio.exception():
                        phrase = ""
                    protocol.write_message({"type": "turn.notice.result", "id": request_id, "notice": phrase,
                                            "slow": mind.notices_are_slow})
                elif kind == "session.new":
                    mind.new_session()
                    protocol.write_message({"type": "session.ready", "id": request_id})
                elif kind == "session.export":
                    protocol.write_message({"type": "session.exported", "id": request_id,
                                            "conversation": mind.export_session()})
                elif kind == "session.title":
                    # The name of the conversation that closed (Mind.title_of), asked once the next one started. It
                    # gives way to any request already waiting, and to one that comes while the model writes it
                    # (server.yields, as a read ahead; revisión total, M5): the person never waits for a name.
                    conversation = message.get("conversation")
                    title = (mind.title_of(conversation) if isinstance(conversation, list) and pending.empty()
                             else "")
                    protocol.write_message({"type": "session.titled", "id": request_id, "title": title})
                elif kind == "session.load":
                    conversation = message.get("conversation")
                    mind.load_session(conversation if isinstance(conversation, list) else [])
                    protocol.write_message({"type": "session.ready", "id": request_id})
                elif kind == "trace.forget":
                    # The person had BAXY forget everything or deleted every conversation (the App deletes its own
                    # conversation log then): the trace and the slot states that hold their words go too, and the model
                    # server's last run's log (F4, 2026-11-03: kept at start, its errors may quote the model's words).
                    cleared = mind.forget_trace() & server.forget_set_aside() & server.forget_log()
                    mind._log("trace.forget", time.perf_counter(), None, cleared=cleared)
                    protocol.write_message({"type": "trace.forgotten", "id": request_id, "cleared": cleared})
                elif kind == "voice.start":
                    mode = str(message.get("mode") or "direct")
                    if voice.start(mode, message.get("echoCancel") is not False):
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
                # R7-NB-1: a request past its budget (LlmServer.REQUEST_SECONDS) says so, as the only one the App asks
                # for again; any other failure would fail the same way.
                # VIVO1 F4: the server of another model refused it for good (external_model.refused, 422): said apart, so the
                # App tells why (its translator's log) and does not ask again.
                code = ("request_timed_out" if isinstance(error, TimeoutError)
                        else "model_refused" if isinstance(error, urllib.error.HTTPError) and error.code == 422 else "request_failed")
                protocol.write_message(protocol.error_reply(request_id, code, f"{surface}_runtime_failure"))
                # P1.13: the App drops this stderr, and a decide past its budget left no row saying why.
                # PRV1: an error's text may quote what it was reading; without the trace's words, its type alone.
                mind._log("request.failed", arrived, None, kind=kind,
                          failure=repr(error) if mind.trace_words else type(error).__name__)
            if kind in PREFILLED_AFTER:
                # Al máximo W5: the reply is already out; with no turn left open, the conversation is read as the next
                # request will show it (Mind.prefill), on a budget of its own, while BAXY speaks. A request that comes
                # meanwhile ends it (LlmServer.yields), and it is read again once that one is answered (Mind.gave_way).
                server.deadline = time.monotonic() + LlmServer.REQUEST_SECONDS
                try:
                    mind.prefill()
                except Exception as error:  # noqa: BLE001 - the next request reads it itself
                    sys.stderr.write(f"baxy_mind_renew_failure:prefill:{error!r}\n")
                    sys.stderr.flush()
    finally:
        # Every step runs: the voice says it stopped on stdout, which fails once the App is gone, and that OSError
        # skipped closing both model servers (they outlived a mind run without the App's job object).
        for name, step in (("voice", voice.stop), ("speech", voice.speech.close), ("server", server.close),
                           ("system_one", system_one.close if system_one is not None else None)):
            if step is None:
                continue
            try:
                step()
            except Exception as error:  # noqa: BLE001 - the next step still runs
                try:
                    sys.stderr.write(f"baxy_mind_renew_failure:close:{name}:{error!r}\n")
                except Exception:  # noqa: BLE001 - stderr's pipe goes with the App too
                    pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
