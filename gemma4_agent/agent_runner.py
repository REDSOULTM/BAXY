"""Bridge between the FastAPI server and the synchronous Gemma4Agent.

Mirrors the PyQt6 `AgentWorker` semantics (one background thread, a queue of
turns, a progress callback that translates agent events into UI signals) but
publishes to the in-process EventBus so the WebSocket clients receive them
verbatim.

The agent is sync and a single turn can take 30-90 seconds; the worker thread
processes turns serially so we never have two LLM calls competing for the
single llama-server slot. POST /turn just enqueues and returns.
"""

from __future__ import annotations

import datetime
import logging
import queue
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .boot_progress import (
    LlamaLogTail,
    STAGE_HEALTH,
    STAGE_LISTENING,
    STAGE_SPAWN,
    emit_stage,
)
from .events_bus import BUS

logger = logging.getLogger(__name__)


@dataclass
class _TurnRequest:
    text: str
    images: list[str]
    audios: list[str]


def _ts() -> str:
    n = datetime.datetime.now()
    return f"{n.hour:02d}:{n.minute:02d}:{n.second:02d}"


def _publish_activity(src: str, msg: str) -> None:
    BUS.publish({
        "type": "activity",
        "entry": {
            "id": uuid.uuid4().hex[:8],
            "src": src,
            "msg": msg,
            "ts": _ts(),
        },
    })


def _fmt_args(args: Any) -> str:
    """One-line preview of a tool's args dict, capped at 120 chars."""
    import json
    try:
        s = json.dumps(args, ensure_ascii=False)
    except (TypeError, ValueError):
        s = str(args)
    if len(s) > 120:
        s = s[:117] + "..."
    return s


class AgentRunner:
    """Long-lived owner of a single Gemma4Agent + its worker thread.

    Designed to be a process-wide singleton (see module-level `RUNNER`).
    Initialisation is lazy — the first time `submit()` is called the worker
    builds the agent in its own thread. That keeps server.py startup fast
    and avoids loading the agent stack if the UI never asks for a turn.
    """

    def __init__(self) -> None:
        self._inbox: queue.Queue[_TurnRequest] = queue.Queue()
        self._running = True
        self._stop_event = threading.Event()
        self._agent: Any = None
        self._thread: threading.Thread | None = None
        self._build_lock = threading.Lock()
        # Flips True only after the agent successfully completed a 1-token
        # warmup against llama-server. /health alone is not enough — see the
        # long comment in _build_agent. The agent_status endpoint and the
        # WS handshake read this so the UI gate is correct everywhere.
        self._warmed_up: bool = False
        # Sprint 4: referencia persistente al LlamaServerManager para que
        # el callback de vision_relaunch (item 1.7) pueda reciclar el
        # server sin tener que recrear el manager (que perderia la
        # referencia al subprocess vivo).
        self._server_manager: Any = None

    def is_warmed_up(self) -> bool:
        return self._warmed_up and self._agent is not None

    def start(self) -> None:
        with self._build_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._run, name="gemma4-agent-runner", daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        # sentinel so the queue.get unblocks
        self._inbox.put(_TurnRequest(text="__stop__", images=[], audios=[]))

    def submit(self, text: str, *, images: list[str] | None = None,
               audios: list[str] | None = None) -> None:
        """Enqueue a turn. Lazy-starts the worker on first call."""
        self.start()
        self._inbox.put(_TurnRequest(
            text=text,
            images=images or [],
            audios=audios or [],
        ))

    def agent_ready(self) -> bool:
        return self._agent is not None

    def restart(self) -> None:
        """Re-run the boot sequence. Used by POST /agent/restart when the
        previous build failed and the user clicked the inline retry button.

        Behaviour: drops the existing agent reference (so /agent/status flips
        back to built=false), then schedules `_build_agent` to run on a fresh
        background thread. The main worker loop keeps draining the inbox the
        whole time; turns submitted while we rebuild get the standard
        'agent not initialised' bounce just like a cold start would."""
        # publish an "agent reset" event up front so the UI flips back to
        # the loading state immediately, before the rebuild actually starts.
        BUS.publish({"type": "agent", "built": False, "healthy": False, "ready": False})
        _publish_activity("BOOT", "agent restart requested · re-running boot sequence")
        self._agent = None
        self._warmed_up = False
        threading.Thread(
            target=self._build_agent,
            name="gemma4-agent-restart",
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # worker
    # ------------------------------------------------------------------

    def _autostart_llama_server(self) -> None:
        """Replicates the legacy ServerBootWorker logic: if the active profile
        wants a server and no one is listening on :8080, launch llama-server.exe
        with the profile's flags. Idempotent; respects an external server.

        Emits boot_stage events on the BUS as it goes so the UI can show what
        the loader is actually doing (spawn → metadata → layers → offload →
        listening → health) instead of an opaque placeholder."""
        try:
            from .config import PACKAGE_ROOT
            from .llama_server import LlamaServerManager, port_in_use
            from .profiles import apply_profile_to_env, get_active_profile
        except Exception as exc:
            _publish_activity("SYSTEM", f"autostart imports failed: {exc}")
            emit_stage(BUS.publish, STAGE_SPAWN,
                       f"autostart imports failed: {exc}",
                       error=str(exc))
            return

        profile = get_active_profile()
        if not profile.server_running:
            _publish_activity("SYSTEM", f"profile {profile.display_name} keeps server off · skipping autostart")
            # Standby profile: emit a terminal "stage" so the UI knows the
            # boot phase is over even though we never started the LLM. The
            # chat input stays disabled (agent.ready is false anyway).
            emit_stage(BUS.publish, "llama_skipped",
                       f"profile {profile.display_name} · llama-server not started")
            return

        if port_in_use():
            _publish_activity("SYSTEM", "llama-server already up on :8080 · using it")
            emit_stage(BUS.publish, STAGE_LISTENING,
                       "external llama-server detected · using it")
            return

        # apply env vars before spawning so the server sees ctx/mmproj from profile
        apply_profile_to_env(profile)
        _publish_activity("BOOT", f"launching llama-server · profile={profile.display_name}, ctx={profile.context_size}")
        emit_stage(BUS.publish, STAGE_SPAWN,
                   f"spawning llama-server · profile {profile.display_name}, ctx {profile.context_size}")

        # start tailing the err.log (llama.cpp writes its boot output to stderr).
        # the tail thread auto-terminates once it sees "server is listening".
        tail = LlamaLogTail(
            log_path=PACKAGE_ROOT / "logs" / "llama-server.err.log",
            publish=BUS.publish,
        )
        tail.start()

        try:
            manager = LlamaServerManager()
            result = manager.start(profile, wait_health=True, timeout_s=120)
            self._server_manager = manager
        except Exception as exc:
            _publish_activity("SYSTEM", f"llama-server boot crashed · {exc}")
            emit_stage(BUS.publish, STAGE_SPAWN,
                       f"llama-server crashed: {exc}", error=str(exc))
            tail.stop()
            return

        if result in {"started", "already_running", "external"}:
            _publish_activity("SYSTEM", f"llama-server up · {result}")
            emit_stage(BUS.publish, STAGE_HEALTH,
                       f"llama-server healthy · {result}", progress=100.0)
            # Sprint 4: registrar callback de vision_relaunch (item 1.7).
            # Cuando multimodal._bump_image_counter cruce IMAGE_RELAUNCH_THRESHOLD,
            # reciclamos el server para mitigar mmproj leak (#21690).
            # Solo registramos si tenemos manager vivo Y el perfil tiene
            # vision_enabled. Para perfiles sin vision el counter sube pero
            # el callback es no-op (lo verifica recycle_for_vision_leak).
            try:
                from .multimodal import set_vision_relaunch_callback
                _runner_ref = self  # closure capture explicito

                def _on_vision_threshold(image_count: int) -> None:
                    mgr = _runner_ref._server_manager
                    if mgr is None:
                        return
                    try:
                        mgr.recycle_for_vision_leak()
                    except Exception as exc:  # noqa: BLE001
                        _publish_activity(
                            "SYSTEM",
                            f"vision_relaunch failed after {image_count} images: {exc}",
                        )

                set_vision_relaunch_callback(_on_vision_threshold)
            except Exception as exc:  # noqa: BLE001
                _publish_activity("SYSTEM", f"vision_relaunch wiring failed: {exc}")
        elif result == "missing_files":
            _publish_activity("SYSTEM", "llama-server boot failed · missing exe or model")
            emit_stage(BUS.publish, STAGE_SPAWN,
                       "missing llama-server.exe or model file",
                       error="missing_files")
        elif result == "timeout":
            _publish_activity("SYSTEM", "llama-server boot timed out · check logs")
            emit_stage(BUS.publish, STAGE_HEALTH,
                       "llama-server did not respond to /health in time",
                       error="timeout")
        else:
            _publish_activity("SYSTEM", f"llama-server boot · {result}")
            emit_stage(BUS.publish, STAGE_HEALTH,
                       f"llama-server boot · {result}", error=result)

        tail.stop()

    def _build_agent(self) -> None:
        """Construct the Gemma4Agent. First, try to autostart llama-server if
        it's not already running (matches legacy GUI behavior). Then build
        the agent and run a health check. All steps emit BOOT/SYSTEM activity
        entries plus `agent` lifecycle + `boot_stage` events so the chat
        input can gate AND show what is currently loading."""
        from .agent import Gemma4Agent
        from .config import AgentConfig

        # restart of the boot sequence: clear the previous warmup latch so
        # the gate stays closed until we re-do the 1-token completion test.
        self._warmed_up = False
        BUS.publish({"type": "agent", "built": False, "healthy": False, "ready": False})

        # autostart llama-server if needed BEFORE constructing the agent —
        # otherwise the agent's first health check will fail and the UI
        # would have to retry.
        self._autostart_llama_server()

        _publish_activity("BOOT", "building agent · loading tools and memory…")
        emit_stage(BUS.publish, "agent_build", "building agent · loading tools and memory")
        try:
            cfg = AgentConfig.from_env()
            self._agent = Gemma4Agent(cfg)
            n_tools = len(self._agent.tools.schemas)
            _publish_activity("SYSTEM", f"agent ready · {n_tools} tools loaded")
            BUS.publish({"type": "agent", "built": True, "healthy": False, "ready": False})
        except Exception as exc:
            logger.exception("agent init failed")
            _publish_activity("SYSTEM", f"agent init failed: {exc}")
            emit_stage(BUS.publish, "agent_build",
                       f"agent build failed: {exc}", error=str(exc))
            BUS.publish({"type": "state", "value": "standby"})
            BUS.publish({"type": "agent", "built": False, "healthy": False, "ready": False})
            return

        # Pre-load the semantic router's BertModel + tool embeddings BEFORE
        # we let the UI unlock the input. Otherwise the first turn pays the
        # one-shot ~3-5s sentence-transformers download/load cost while the
        # user thinks the agent is thinking — the regression captured in
        # screenshots: "loading weights 199/199" + BertModel LOAD REPORT
        # appearing AFTER the user sent their first message.
        # We import lazily so the import cost itself only runs when the
        # boot path actually exercises it.
        try:
            from . import semantic_router
        except Exception as exc:
            logger.warning("semantic_router import failed (rerank disabled): %s", exc)
            semantic_router = None  # type: ignore[assignment]
        if semantic_router is not None and semantic_router.is_enabled():
            _publish_activity("BOOT", "loading semantic router · BertModel + tool embeddings")
            emit_stage(BUS.publish, "rerank_load",
                       "loading semantic router · BertModel + tool embeddings")
            try:
                tool_names = [
                    s.get("function", {}).get("name") or s.get("name") or ""
                    for s in self._agent.tools.schemas
                ]
                tool_names = [t for t in tool_names if t]
                # _ensure_loaded triggers the SentenceTransformer load AND
                # pre-computes the tool description embeddings, which is the
                # other half of the first-turn cost.
                semantic_router._ensure_loaded(known_tool_names=tool_names)
            except Exception as exc:
                # rerank is not load-bearing — log and keep going. The agent
                # falls back to keyword routing when the model isn't loaded.
                logger.warning("semantic router warmup failed: %s", exc)

        # health check against llama-server. /health responds 200 as soon as
        # the binary is bound to the port — that's BEFORE load_tensors has
        # finished moving weights to VRAM. If we trusted /health alone, the
        # UI would unlock the input and the user's first POST /turn would
        # queue inside llama-server while it kept loading (the regression
        # the user saw: first turn took 30-90s even though the input was
        # already enabled).
        #
        # To gate `ready` honestly we follow up with a 1-token chat warmup:
        # llama-server can't reply to a completion until load_tensors is
        # done, so when this call returns we know the model is in VRAM and
        # the FIRST real turn will be fast.
        try:
            healthy = bool(self._agent.client.health())
        except Exception:
            healthy = False
        if not healthy:
            _publish_activity("SYSTEM", f"llama-server NOT responding · {cfg.server_url}")
            emit_stage(BUS.publish, "ready",
                       "agent built but llama-server is unreachable",
                       error="llama-server unreachable")
            BUS.publish({"type": "state", "value": "standby"})
            BUS.publish({"type": "agent", "built": True, "healthy": False, "ready": False})
            return

        # Warmup: tiny completion that forces llama-server to finish load_tensors
        # before responding. We give it a generous 180s timeout because the
        # first call on a freshly-spawned server has to load all the weights
        # into VRAM, which on a Q6_K E4B takes ~30-90s. Subsequent restarts
        # are much faster because the GGUF stays in OS file cache.
        _publish_activity("BOOT", "warming up llama-server · first completion")
        emit_stage(BUS.publish, "llama_warmup",
                   "warming up llama-server · first completion may take 30-90s")
        warmup_ok = False
        warmup_err: str | None = None
        try:
            resp = self._agent.client.chat(
                messages=[{"role": "user", "content": "."}],
                max_tokens=1,
                timeout_s=180.0,
            )
            # any HTTP 200 with the expected shape counts as ready — we don't
            # care about the actual content of the reply.
            warmup_ok = isinstance(resp, dict) and "choices" in resp
            if not warmup_ok:
                warmup_err = "unexpected response shape"
        except Exception as exc:
            warmup_err = str(exc)

        if warmup_ok:
            # Polish P4 / Sprint 7: pre-warm del KV cache con el system
            # prompt completo del agente (system prompt + tool_schemas_hint
            # + memoria). El warmup de arriba ya forzo load_tensors a
            # terminar, pero NO calento el KV con el prefix real que el
            # usuario va a usar en su primer turno. Con PR #22288 merged
            # (Polish P1) + --cache-reuse 256 activo, este prewarm le da
            # al server la oportunidad de cachear el prefix entero antes
            # de que entre el primer turno real. Beneficio esperado:
            # primer turno real ~unidades de segundos vs ~30s+ sin prewarm.
            #
            # Best-effort: si falla, NO cambia el estado del agente. El
            # primer turno simplemente paga el TTFT completo.
            try:
                from .prewarm import prewarm_kv
                # Construir el system_prompt real que el agente usaria. Le
                # pasamos mode=None/plan=None para que sea el prompt base
                # mas el tool_schemas_hint (que sera lo mas pesado del
                # prefix). Tools=None: el catalogo ya esta en el system
                # prompt como bloque markdown EXACT.
                sys_msg = self._agent._system_message(mode=None, plan=None)
                sys_content = sys_msg.get("content", "")
                prewarm_result = prewarm_kv(
                    self._agent.client,
                    sys_content,
                    tools=None,
                    timeout_s=90.0,
                    publish=BUS.publish,
                )
                if prewarm_result.get("ok"):
                    elapsed = prewarm_result.get("elapsed_s", 0)
                    _publish_activity(
                        "SYSTEM",
                        f"KV prewarm done in {elapsed:.1f}s ({len(sys_content)} chars)",
                    )
                elif prewarm_result.get("skipped"):
                    _publish_activity(
                        "SYSTEM",
                        f"KV prewarm skipped: {prewarm_result.get('reason')}",
                    )
                else:
                    _publish_activity(
                        "SYSTEM",
                        f"KV prewarm failed (non-fatal): {prewarm_result.get('error', 'unknown')}",
                    )
            except Exception as exc:  # noqa: BLE001
                # Cualquier fallo del prewarm es NO bloqueante.
                _publish_activity("SYSTEM", f"KV prewarm crashed (non-fatal): {exc}")

            self._warmed_up = True
            _publish_activity("SYSTEM", f"llama-server online · {cfg.server_url}")
            emit_stage(BUS.publish, "ready",
                       f"ready · {n_tools} tools · model in VRAM",
                       progress=100.0)
            BUS.publish({"type": "state", "value": "idle"})
            BUS.publish({"type": "agent", "built": True, "healthy": True, "ready": True})
        else:
            _publish_activity("SYSTEM", f"warmup failed · {warmup_err}")
            emit_stage(BUS.publish, "llama_warmup",
                       f"warmup failed · {warmup_err}",
                       error=warmup_err or "warmup failed")
            BUS.publish({"type": "state", "value": "standby"})
            BUS.publish({"type": "agent", "built": True, "healthy": True, "ready": False})

    def _progress_forwarder(self, event: str, payload: dict[str, Any]) -> None:
        """Translate agent.run_text progress events into BUS events.

        Only forwards events that mean something visually to the user.
        We deliberately swallow:
          - "start" — adds no signal (state already went to 'thinking' on submit)
          - "tool_subset" with empty/zero tools — pure noise for the user
          - any event whose payload is empty when the visible label would be ""
        """
        if event == "tool_subset":
            count = int(payload.get("schema_count") or 0)
            tools = payload.get("tools") or []
            if count == 0 or not tools:
                return  # nothing actionable to show
            tlist = ", ".join(str(t) for t in tools[:6])
            if len(tools) > 6:
                tlist += f" ... (+{len(tools) - 6})"
            _publish_activity("CONTEXT", tlist)
        elif event == "tool_start":
            name = payload.get("name") or "?"
            args = payload.get("args") or {}
            _publish_activity("TOOL", f"{name}({_fmt_args(args)})")
        elif event == "tool_end":
            name = payload.get("name") or "?"
            ok = bool(payload.get("ok"))
            status = str(payload.get("status") or "")
            # only emit if there's something to say; skip silent OKs that the
            # tool_start already implied. surface failures explicitly.
            if not ok:
                _publish_activity("SYSTEM", f"{name} failed · {status}")
            elif status and status.lower() not in {"ok", "success", ""}:
                _publish_activity("TOOL", f"{name} → {status}")
        elif event == "image_injected":
            path = payload.get("path") or ""
            if path:
                _publish_activity("CONTEXT", f"image · {path}")
        elif event == "final":
            BUS.publish({"type": "state", "value": "speaking"})
        elif event == "max_turns":
            _publish_activity("SYSTEM", "max turns reached")
            BUS.publish({"type": "state", "value": "standby"})
        # event == "start" is intentionally dropped — state already transitioned.

    def _run(self) -> None:
        self._build_agent()
        while self._running:
            req = self._inbox.get()
            if not self._running or req.text == "__stop__":
                break
            if self._agent is None:
                _publish_activity("SYSTEM", "agent not initialised · ignoring turn")
                continue

            try:
                _publish_activity("YOU", req.text)
                BUS.publish({"type": "state", "value": "thinking"})

                reply = self._agent.run_text(
                    req.text,
                    images=[Path(p) for p in req.images] if req.images else None,
                    audios=[Path(p) for p in req.audios] if req.audios else None,
                    progress=self._progress_forwarder,
                )

                content = getattr(reply, "content", "") or ""
                err = getattr(reply, "error", None)

                if err:
                    _publish_activity("SYSTEM", f"turn error · {err}")
                    BUS.publish({"type": "state", "value": "standby"})
                else:
                    if content:
                        # publish the assistant's reply as a GEMMA entry so the
                        # activity log shows it like any other source.
                        preview = content if len(content) <= 600 else content[:597] + "..."
                        _publish_activity("GEMMA", preview)
                        # crude tokens estimate (4 chars ≈ 1 token) for the counter
                        BUS.publish({"type": "tokens", "delta": max(1, len(content) // 4)})
                        # if voice is active, speak the reply via piper. matches
                        # legacy main_window._on_reply_ready behaviour:
                        # begin_tts -> feed_tts_chunk -> end_tts.
                        try:
                            from .voice_runner import VOICE
                            VOICE.feed_tts(content)
                        except Exception as exc:
                            logger.warning("voice feed failed: %s", exc)
                    BUS.publish({"type": "state", "value": "idle"})

            except Exception as exc:
                logger.exception("agent turn crashed")
                _publish_activity("SYSTEM", f"turn failed: {exc}")
                BUS.publish({"type": "state", "value": "standby"})


# module-level singleton, started lazily on first submit()
RUNNER = AgentRunner()
