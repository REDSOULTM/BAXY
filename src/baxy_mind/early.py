"""BAXY Renew al máximo, palancas 2 y 5 (artifacts/renew/maximo/INVESTIGACION_PALANCAS_2.md): latency only; what BAXY
decides and says does not change.

2. **Decisión anticipada.** A spoken request ends after END_SILENCE_S (0.9 s) of silence, and only then did the model
   start deciding (p50 ~1.1 s from the person's words to the first step, practice e2e). The voice tells the mind what
   was said EARLY_SILENCE_S into that silence (Voice.on_early), and the mind decides right then, on its request loop,
   with every effect held: the reply is not sent, the trace rows are held, the voice's look-ahead is only recorded, and
   the mind's state is set aside first. When the App's turn.decide comes, the decision is used only if it is the one
   that request would have made: the same words (the transcript of the whole silence, decoded again as always), no call
   waiting for the person's «sí» (the App's, unknown to the mind), the clock's same minute, and no other request between
   them. Otherwise, or when the person goes on speaking (Voice says so), or after HOLD_S unused, everything is put back
   as it was: the mind's state (every attribute but the shared ones, deep-copied), no trace row, no look-ahead, and the
   slot holds again the text a read ahead had left in it (LlmServer.resident), so the next request reads what it would
   have read. One fact stays: the slot did read the person's words, so the warm-up no longer saves it (``_turned``).
   Expected saving per spoken order with a hit: min(decision, END_SILENCE_S − EARLY_SILENCE_S) ≈ 0.7 s.
5. **Precalentar al oír «Baxy»** (palanca 5). When the wake word fires (or the microphone button opens a request), the
   conversation and the next turn's clock are read into the slot (Mind.prefill(clock=True)), while the person speaks:
   the GPU is awake and the decision reads only the person's words. Same prompt; only when it is read changes.

BAXY_RENEW_EARLY: «0» turns palanca 2 off (the voice then decodes nothing early); empty or «1», on with
EARLY_SILENCE_S; a number of seconds under END_SILENCE_S, on with that wait. BAXY_RENEW_WAKE_WARM=0 turns palanca 5 off.
"""
from __future__ import annotations

import copy
import json
import os
import sys
import threading
import time
from typing import Any

from .mind import Mind
from .voice import END_SILENCE_S

# Silence before the early transcript: 2 blocks of 100 ms, so a soft word ending under the voice threshold is in it.
EARLY_SILENCE_S = 0.2
# An early decision nobody asked for is put back after this (the App dropped the words, or nothing was transcribed).
HOLD_S = 5.0
# Mind attributes an early decision never sets aside: what it shares with the process (the model server, the decision
# model, the trace's file and lock, the voice's look-ahead, which it swaps itself), what the catalog set (no decision
# writes it; the tests prove it equal), and two facts of the slot: it read the person's words (``_turned``, so the
# warm-up never saves it) and the rows being held.
SHARED = frozenset({"server", "system_one", "trace", "_log_lock", "foresee", "_turned", "_holding", "tools", "english",
                    "arguments", "names", "wire_to_op", "risk", "effects", "constants"})


def early_silence() -> float | None:
    """BAXY_RENEW_EARLY as the seconds of silence before the early transcript, or None when palanca 2 is off."""
    setting = os.environ.get("BAXY_RENEW_EARLY", "").strip().lower()
    if setting in {"0", "off"}:
        return None
    try:
        value = float(setting) if setting not in {"", "1", "on"} else EARLY_SILENCE_S
    except ValueError:
        return EARLY_SILENCE_S
    return value if 0 < value < END_SILENCE_S else EARLY_SILENCE_S


def wake_warm() -> bool:
    """Whether palanca 5 is on (BAXY_RENEW_WAKE_WARM, on unless «0»)."""
    return os.environ.get("BAXY_RENEW_WAKE_WARM", "").strip().lower() not in {"0", "off"}


class _Cancelled(BaseException):
    """The person went on speaking: the early decision stops before its next call to a model. A BaseException, so no
    ``except Exception`` of the mind takes it for a failed call and goes on another way."""


class _Guard:
    """The model server (or the decision model) as an early decision sees it: each call first checks it was not
    cancelled; attributes read through."""

    def __init__(self, target: Any, cancelled: threading.Event) -> None:
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_cancelled", cancelled)

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._target, name)
        if not callable(value):
            return value

        def guarded(*args: Any, **kwargs: Any) -> Any:
            if self._cancelled.is_set():
                raise _Cancelled()
            return value(*args, **kwargs)

        return guarded


def set_aside(mind: Mind) -> dict[str, Any]:
    """The mind's own state, deep-copied in one piece (the open turn's conversation is the session's same list)."""
    return copy.deepcopy({key: value for key, value in vars(mind).items() if key not in SHARED})


def put_back(mind: Mind, kept: dict[str, Any]) -> None:
    for key in [key for key in vars(mind) if key not in SHARED and key not in kept]:
        delattr(mind, key)
    for key, value in kept.items():
        setattr(mind, key, value)


def _same(pending: Any, guessed: Any) -> bool:
    return json.dumps(pending or None, sort_keys=True) == json.dumps(guessed, sort_keys=True)


class Anticipation:
    """Palancas 2 and 5 on the mind's request loop (__main__): every call is made on that one thread, so an early
    decision never runs beside a request; only ``cancel`` comes from the voice's thread."""

    def __init__(self, mind: Mind, warm: bool = True, hold_s: float = HOLD_S) -> None:
        self.mind = mind
        self.warm = warm
        self.hold_s = hold_s
        self._lock = threading.Lock()
        self._running: tuple[int, threading.Event] | None = None
        self._dropped: set[int] = set()   # early transcripts the voice took back
        self._held: dict[str, Any] | None = None
        self._missed: str | None = None   # why the last early decision was not used, for the next decision's row
        self._discarded = 0

    # ---- from the voice's thread -------------------------------------------------------------------------------
    def cancel(self, seq: int) -> None:
        """The voice took early transcript ``seq`` back: its decision stops before its next call to a model."""
        with self._lock:
            self._dropped.add(seq)
            if self._running is not None and self._running[0] == seq:
                self._running[1].set()

    # ---- on the request loop -----------------------------------------------------------------------------------
    def idle(self) -> bool:
        """No call waits for its result and no heartbeat is open (the model's question may wait: the words answer it)."""
        turn = self.mind._turn or {}
        return bool(self.mind.tools) and self.mind._beat is None and not turn.get("awaiting") and not turn.get("queue")

    def speculate(self, seq: int, text: str) -> bool:
        """Decide on early transcript ``seq`` with every effect held; whether a decision is held for the App's request."""
        self.drop("superseded")
        mind = self.mind
        with self._lock:
            self._dropped = {dropped for dropped in self._dropped if dropped >= seq}
            if seq in self._dropped:
                return False
            cancelled = threading.Event()
            self._running = (seq, cancelled)
        if not self.idle():
            with self._lock:
                self._running = None
            return False
        kept = set_aside(mind)
        resident = getattr(mind.server, "resident", None)
        clock = mind._clock_time()
        rows: list[dict[str, Any]] = []
        foreseen: list[tuple[str | None, bool]] = []
        server, system_one, foresee = mind.server, mind.system_one, mind.foresee
        mind.server = _Guard(server, cancelled)  # type: ignore[assignment]
        if system_one is not None:
            mind.system_one = _Guard(system_one, cancelled)  # type: ignore[assignment]
        if foresee is not None:
            mind.foresee = lambda written, done: foreseen.append((written, done)) or False
        mind._holding = (threading.get_ident(), rows)
        mind._clock_time = lambda: clock  # type: ignore[method-assign]  # the decision's minute is the one compared
        started = time.perf_counter()
        result: dict[str, Any] | None = None
        try:
            result = mind.decide(None, text, None)
        except (_Cancelled, Exception) as error:  # noqa: BLE001 - put back; the App's request decides as always
            if not isinstance(error, _Cancelled):
                sys.stderr.write(f"baxy_mind_renew_failure:early:{error!r}\n")
                sys.stderr.flush()
        finally:
            ended = time.perf_counter()
            del mind._clock_time
            mind.server, mind.system_one, mind.foresee = server, system_one, foresee
            mind._holding = None
            with self._lock:
                self._running = None
        held = {"seq": seq, "text": text, "clock": clock, "result": result, "rows": rows, "foreseen": foreseen,
                "kept": kept, "resident": resident, "started": started, "ended": ended}
        if result is None or cancelled.is_set():
            self._back(held, "cancelled" if cancelled.is_set() else "failed")
            return False
        self._held = held
        return True

    def drop(self, reason: str, seq: int | None = None) -> None:
        """The held decision (only ``seq``'s, when given) is put back, slot included."""
        held = self._held
        if held is not None and (seq is None or held["seq"] == seq):
            self._held = None
            self._back(held, reason)

    def patience(self) -> float | None:
        """How long the loop may wait for a request before the held decision is put back (None: nothing held)."""
        if self._held is None:
            return None
        return max(0.0, self._held["ended"] + self.hold_s - time.perf_counter())

    def expire(self) -> None:
        if self._held is not None and self.patience() == 0.0:
            self.drop("expired")

    def settle(self, kind: str, message: dict[str, Any], arrived: float) -> dict[str, Any] | None:
        """Before any request: the held decision when this is the turn.decide it was made for (its reply, with this
        request's id), else None, with the held decision put back first. The slot is left to that request to read."""
        held, self._held = self._held, None
        if held is None:
            return None
        if kind != "turn.decide":
            self._back(held, "request")
            return None
        reason = ("text" if str(message.get("text") or "") != held["text"]
                  else "pending" if not _same(message.get("pendingConfirmation"), None)
                  else "clock" if self.mind._clock_time() != held["clock"] else None)
        if reason is not None:
            self._back(held, reason, reread=False)
            return None
        decided = held["ended"] - held["started"]
        ahead = arrived - held["started"]
        rows = held["rows"]
        if rows:
            rows[-1]["early"] = {"hit": True, "ahead_ms": round(ahead * 1000), "saved_ms": round(
                max(0.0, min(decided, ahead)) * 1000), "waited_ms": round(max(0.0, held["ended"] - arrived) * 1000),
                **({"discarded": self._discarded} if self._discarded else {})}
        self._discarded, self._missed = 0, None
        for row in rows:
            self.mind._write_row(row)
        if self.mind.foresee is not None:
            for written, done in held["foreseen"]:
                try:
                    if self.mind.foresee(written, done):
                        break
                except Exception:  # noqa: BLE001 - a failing look-ahead never fails the answer
                    break
        return {**held["result"], "id": message.get("id")}

    def decide(self, request_id: Any, text: str, pending: dict[str, Any] | None) -> dict[str, Any]:
        """The App's turn.decide when no early decision was used: as always; after one that was put back, its row says
        why (``early``), so the A/B reads the misses beside the hits."""
        missed, discarded = self._missed, self._discarded
        self._missed, self._discarded = None, 0
        if missed is None:
            return self.mind.decide(request_id, text, pending)
        rows: list[dict[str, Any]] = []
        self.mind._holding = (threading.get_ident(), rows)
        try:
            return self.mind.decide(request_id, text, pending)
        finally:
            self.mind._holding = None
            if rows:
                rows[-1]["early"] = {"hit": False, "reason": missed, "discarded": discarded}
            for row in rows:
                self.mind._write_row(row)

    def wake(self) -> bool:
        """Palanca 5: «Baxy» was heard (or the button opened a request): what the first decision reads is read now."""
        self.drop("wake")
        if not self.warm or not self.idle():
            return False
        try:
            return self.mind.prefill(clock=True)
        except Exception as error:  # noqa: BLE001 - the decision reads it itself
            sys.stderr.write(f"baxy_mind_renew_failure:wake:{error!r}\n")
            sys.stderr.flush()
            return False

    def _back(self, held: dict[str, Any], reason: str, reread: bool = True) -> None:
        """Put back what an early decision changed. ``reread``: the slot reads again the text a read ahead had left in
        it, so it holds what it held before (when a request is waiting, that request reads it itself)."""
        put_back(self.mind, held["kept"])
        self._missed, self._discarded = reason, self._discarded + 1
        if reread and held["resident"] is not None:
            try:
                self.mind.server.prefill(held["resident"])
            except Exception:  # noqa: BLE001 - the next request reads it itself
                pass
