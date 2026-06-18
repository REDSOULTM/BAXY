"""FastAPI server that hosts the Field UI and exposes the agent over HTTP+WS.

This is the bridge between the React/Vite frontend in `ui_field/dist/` and the
Python agent. The server:

- serves the prebuilt static UI at `/`
- answers `GET /model` with the real ModelInfo of the currently loaded GGUF
  (no hardcoded strings — the UI mirrors whatever the user has on disk)
- answers `GET /metrics` with cpu/mem/gpu/net/dsk/tmp snapshots
- persists user settings to `~/.gemma4/gui.json` via `GET`/`PUT /settings`
- accepts user prompts via `POST /turn`, handed to the AgentRunner thread
  which runs Gemma4Agent.run_text and publishes progress events to BUS
- streams agent events over `WS /events`, fed by the in-process BUS that
  agent.py publishes to
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import platform
import queue
import subprocess
import threading
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

import psutil
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import AgentConfig, PACKAGE_ROOT
from .events_bus import BUS
from .llama_server import get_external_server_context, port_in_use
from .model_info import ModelInfo, build_model_info, mock_model_info

logger = logging.getLogger(__name__)

UI_DIST = PACKAGE_ROOT / "ui_field" / "dist"
SETTINGS_DIR = Path.home() / ".gemma4"
SETTINGS_PATH = SETTINGS_DIR / "gui.json"


# ---------- pydantic schemas ----------

class TurnRequest(BaseModel):
    text: str
    attachments: list[str] = []


class ActivityRequest(BaseModel):
    """UI-originated SYSTEM/USER entries — used for things like "new session"
    and "help" buttons that need to append to the activity log without going
    through the agent. real agent events come via the bus directly."""

    src: str
    msg: str


class ProfileChange(BaseModel):
    """Body of PUT /profile. MUST live at MODULE level: this file uses
    `from __future__ import annotations`, so an endpoint's parameter
    annotation is a STRING forward-ref. FastAPI can only resolve it against
    module globals — a class defined INSIDE create_app() can't be found, so
    FastAPI silently demoted `body: _ProfileChange` to a query param and
    every profile switch 422'd ("Field required"). Keeping the model here
    makes the forward-ref resolvable. (The other local _Model classes in
    create_app have the same latent bug; migrate them if they ever 422.)"""

    name: str


class AccessibilityChange(BaseModel):
    """Body of PUT /accessibility. A nivel MÓDULO por la misma razón que
    ProfileChange (forward-ref de annotations). `mode` = normal|no_vidente|
    movilidad."""

    mode: str


# ---------- hardware specs ----------

# cached at module import — these don't change at runtime, so detecting once
# avoids polling /hardware doing the work over and over.
_HARDWARE_CACHE: dict[str, Any] | None = None


def _detect_hardware() -> dict[str, Any]:
    """Best-effort detection of host hardware specs for the substrate panel.

    Each field is either the real value (e.g. "ryzen 7 7700x · 16c") or the
    literal string "unknown" so the UI can render unknown specs dim without
    fabricating values. Memory total / GPU model are detected when libraries
    are available; otherwise marked unknown.
    """
    cpu_spec = "unknown"
    cpu_cores = psutil.cpu_count(logical=True) or 0
    proc = ""
    try:
        proc = platform.processor() or ""
    except Exception:
        proc = ""

    # platform.processor() on Windows looks like
    # "AMD64 Family 25 Model 33 Stepping 0, AuthenticAMD" — try wmic for a
    # nicer marketing name. wmic is slow (~1-5s on cold start) so we give it
    # generous headroom; if it times out we fall back gracefully.
    if not proc or "Family" in proc:
        try:
            out = subprocess.check_output(
                ["wmic", "cpu", "get", "name"],
                stderr=subprocess.DEVNULL,
                timeout=5,
                text=True,
            )
            lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
            if len(lines) >= 2:
                proc = lines[1]
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            # wmic missing / slow — fall through to whatever platform.processor gave us
            pass

    proc = proc.lower().replace("(r)", "").replace("(tm)", "").strip()
    proc = " ".join(proc.split())
    if proc and "family" not in proc and cpu_cores:
        # shorten common vendor prefixes so it fits the substrate spec line
        short = proc
        for k in ("amd ", "intel "):
            if short.startswith(k):
                short = short[len(k):]
        cpu_spec = f"{short} · {cpu_cores}c"
    elif cpu_cores:
        cpu_spec = f"cpu · {cpu_cores}c"

    mem_total_gb = 0.0
    mem_spec = "unknown"
    try:
        vm = psutil.virtual_memory()
        mem_total_gb = vm.total / (1024 ** 3)
        # we can't easily detect ddr3/ddr4/ddr5 cross-platform; report just gb
        mem_spec = f"{mem_total_gb:.0f} gb"
    except Exception:
        pass

    gpu_spec = "unknown"
    gpu_vram_gb = 0.0
    try:
        h = _nvml_handle()
        if _NVML["ok"] and h is not None:
            name = _NVML["mod"].nvmlDeviceGetName(h)
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="replace")
            mem = _NVML["mod"].nvmlDeviceGetMemoryInfo(h)
            gpu_vram_gb = mem.total / (1024 ** 3)
            # collapse "NVIDIA GeForce RTX 4090" → "rtx 4090"
            short = name.lower()
            for k in ("nvidia ", "geforce "):
                short = short.replace(k, "")
            short = " ".join(short.split())
            gpu_spec = f"{short} · {gpu_vram_gb:.0f} gb"
    except Exception:
        pass

    # FALLBACK nvidia-smi: NVML/pynvml a veces NO está instalado
    # (ModuleNotFoundError), dejando gpu="unknown" y el context budget sin
    # auto-rellenar en la Field UI. nvidia-smi viene con el driver y ya se usa
    # en profile_watcher/metrics. Solo se invoca si NVML no resolvió la GPU.
    if gpu_spec == "unknown":
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            line = (out.stdout or "").strip().splitlines()[0] if out.stdout.strip() else ""
            if line:
                parts = [p.strip() for p in line.split(",")]
                name = parts[0]
                mem_mib = float(parts[1]) if len(parts) > 1 and parts[1] else 0.0
                gpu_vram_gb = mem_mib / 1024.0
                short = name.lower()
                for k in ("nvidia ", "geforce "):
                    short = short.replace(k, "")
                short = " ".join(short.split())
                gpu_spec = f"{short} · {gpu_vram_gb:.0f} gb"
        except Exception:
            pass

    return {
        "cpu": cpu_spec,
        "cpu_cores": cpu_cores,
        "mem": mem_spec,
        "mem_total_gb": round(mem_total_gb, 1),
        "gpu": gpu_spec,
        "gpu_vram_gb": round(gpu_vram_gb, 1),
    }


def _hardware_info() -> dict[str, Any]:
    global _HARDWARE_CACHE
    if _HARDWARE_CACHE is None:
        _HARDWARE_CACHE = _detect_hardware()
    return _HARDWARE_CACHE


# ---------- model info ----------

def _current_model_info(config: AgentConfig) -> ModelInfo | None:
    """Return the live ModelInfo, or None if the server is not yet healthy.

    The context_size is fetched from the llama-server via /props when possible
    so the value matches what the server actually loaded (which can differ
    from the config if an external server is in use).
    """
    if not config.model_path.exists():
        # no GGUF on disk — fall back to mock so the UI shows a clear MOCK badge
        return mock_model_info()

    ctx = None
    if port_in_use():
        ctx = get_external_server_context()
    if ctx is None:
        ctx = config.context_size  # best effort

    mmproj = str(config.mmproj_path) if config.mmproj_path.exists() else None

    return build_model_info(
        gguf_path=str(config.model_path),
        server_url=config.server_url,
        mmproj_path=mmproj,
        ctx_size=ctx,
    )


# ---------- metrics ----------

# psutil's first cpu_percent() call returns 0.0 and the meaningful reading
# only arrives on the second call. we keep a module-level prime so the first
# real GET /metrics already has data.
psutil.cpu_percent(interval=None)


# pynvml is initialised lazily on first use and the handle is cached. without
# this, every /metrics call would pay nvmlInit + nvmlShutdown, which is
# expensive and race-prone when polled at 1.5s intervals.
_NVML: dict[str, Any] = {"tried": False, "ok": False, "handle": None, "mod": None, "temp_key": None}


def _nvml_handle() -> Any:
    if _NVML["tried"]:
        return _NVML["handle"]
    _NVML["tried"] = True
    try:
        import pynvml  # type: ignore
        pynvml.nvmlInit()
        _NVML["mod"] = pynvml
        _NVML["handle"] = pynvml.nvmlDeviceGetHandleByIndex(0)
        _NVML["temp_key"] = pynvml.NVML_TEMPERATURE_GPU
        _NVML["ok"] = True
    except Exception:
        _NVML["ok"] = False
    return _NVML["handle"]


def _gpu_percent() -> tuple[float, bool]:
    """NVIDIA GPU utilization. (value, is_placeholder)."""
    h = _nvml_handle()
    if not _NVML["ok"] or h is None:
        return 0.0, True
    try:
        util = _NVML["mod"].nvmlDeviceGetUtilizationRates(h)
        return float(util.gpu), False
    except Exception:
        return 0.0, True


def _gpu_temp() -> tuple[float, bool]:
    h = _nvml_handle()
    if not _NVML["ok"] or h is None:
        return 0.0, True
    try:
        t = _NVML["mod"].nvmlDeviceGetTemperature(h, _NVML["temp_key"])
        return float(t), False
    except Exception:
        return 0.0, True


# track the previous network bytes so we can convert cumulative counters into
# a "% of recent activity" value normalized to 0..100 (cap at ~100MB/s = 100%).
_last_net = {"bytes": 0, "ts": 0.0}


def _net_percent() -> float:
    try:
        snap = psutil.net_io_counters()
        now = time.monotonic()
        total = snap.bytes_sent + snap.bytes_recv
        prev_bytes = _last_net["bytes"]
        prev_ts = _last_net["ts"]
        _last_net["bytes"] = total
        _last_net["ts"] = now
        if prev_ts == 0:
            return 0.0
        dt = max(0.001, now - prev_ts)
        bps = (total - prev_bytes) / dt
        # 100MB/s saturates the bar; users with faster nics will just stay near 100
        return min(100.0, (bps / (100 * 1024 * 1024)) * 100)
    except Exception:
        return 0.0


# the launcher process start time — used to compute uptime for the substrate
# footer. monotonic guarantees no jumps on system clock changes.
_PROCESS_STARTED = time.monotonic()


def _format_uptime(seconds: float) -> str:
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _metrics_snapshot() -> dict[str, Any]:
    gpu_val, gpu_ph = _gpu_percent()
    tmp_val, tmp_ph = _gpu_temp()
    cpu_val = float(psutil.cpu_percent(interval=None))
    mem_val = float(psutil.virtual_memory().percent)
    try:
        dsk_val = float(psutil.disk_usage(str(PACKAGE_ROOT.anchor or "C:\\")).percent)
    except Exception:
        dsk_val = 0.0

    placeholder: dict[str, bool] = {}
    if gpu_ph:
        placeholder["gpu"] = True
    if tmp_ph:
        placeholder["tmp"] = True

    # mem is reported as gb (used) for the big metric row, plus % for the bar
    try:
        vm = psutil.virtual_memory()
        mem_used_gb = (vm.total - vm.available) / (1024 ** 3)
    except Exception:
        mem_used_gb = 0.0

    return {
        "cpu": cpu_val,
        "mem": mem_val,
        "mem_used_gb": round(mem_used_gb, 1),
        "gpu": gpu_val,
        "net": _net_percent(),
        "dsk": dsk_val,
        "tmp": tmp_val,
        "uptime": _format_uptime(time.monotonic() - _PROCESS_STARTED),
        "placeholder": placeholder,
    }


# ---------- settings persistence ----------

def _load_settings() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        parsed = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("could not read %s: %s", SETTINGS_PATH, exc)
        return {}
    if not isinstance(parsed, dict):
        # someone hand-edited the file into a list/scalar. don't return non-dict
        # to the UI — it would crash the spread in the settings panel reducer.
        logger.warning("%s is not a JSON object; ignoring", SETTINGS_PATH)
        return {}
    return parsed


def _save_settings(data: dict[str, Any]) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    # ensure_ascii=False keeps user-visible strings (es_AR voice names, Spanish
    # close-phrases like "está") readable when the file is opened in an editor.
    SETTINGS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# The Settings panel's "toggles" tab maps each switch to a specific env var
# that the agent honours when it's constructed. Mirroring them into the live
# process environment lets a subsequent /agent/restart pick them up without
# requiring the user to relaunch the whole process.
_TOGGLE_ENV_MAP: dict[str, str] = {
    "factExtraction":     "GEMMA4_AGENT_FACT_EXTRACTION",
    "crossEncoderRerank": "GEMMA4_KNOWLEDGE_RERANK",
    "parallelToolExec":   "GEMMA4_AGENT_PARALLEL_TOOLS",
    "autoLoadCtx":        "GEMMA4_AGENT_PROJECT_CONTEXT",
    "persistentSessions": "GEMMA4_AGENT_SESSIONS",
    "toolTimeline":       "GEMMA4_AGENT_TIMELINE",
    "summarization":      "GEMMA4_AGENT_SUMMARIZATION",
    "tracing":            "GEMMA4_AGENT_TRACING",
    # Visión SIEMPRE cargada (2026-06-09): el mmproj queda RESIDENTE en vez de
    # cargarse lazy al llegar una imagen (router-mode). Default ON — medido que NO
    # penaliza el texto en builds recientes de llama.cpp (#21133); ahorra los ~2-5s
    # de carga on-demand del proyector en la 1ra imagen. Apagar -> vuelve el router-
    # mode lazy. Requiere reiniciar el llama-server (cambia el comando de arranque).
    "visionAlways":       "GEMMA4_VISION_ALWAYS",
    # SOLO Parakeet: apaga el fallback a Whisper. Si Parakeet no carga, la voz
    # falla limpio en vez de caer a Whisper silenciosamente.
    "sttParakeetOnly":    "GEMMA4_STT_NO_FALLBACK",
}

# OPTIM tab — palancas low-level del roadmap Gemma 4. Mismo concepto que
# _TOGGLE_ENV_MAP pero estas son una mezcla: dos toggles boolean + tres
# strings (combo / path / api key). Separar el mapping evita que un futuro
# rename de keys arrastre al otro grupo.
_OPTIM_TOGGLE_ENV_MAP: dict[str, str] = {
    "disablePrewarm": "GEMMA4_DISABLE_PREWARM",
    "telemetry":      "GEMMA4_TELEMETRY",
}
_OPTIM_STRING_ENV_MAP: dict[str, str] = {
    "kvType":         "GEMMA4_LLAMA_KV_TYPE",
    "specDraftModel": "GEMMA4_SPEC_DRAFT_MODEL",
    "llamaApiKey":    "GEMMA4_LLAMA_API_KEY",
    # Idioma del usuario (2026-06-07): "" = Automático (auto-detecta por turno,
    # comportamiento actual); "es"/"en"/"pt"/"fr"/"de"/"it" = FIJA ese idioma en
    # todo el stack (transcripción + respuesta del LLM). String vacío -> borra la
    # var -> Automático. Ver lang_profiles.resolve_lang + agent._reply_lang.
    "voiceLang":      "GEMMA4_VOICE_LANG",
    # Política de confirmación: "" = default (confirm_risky, confirma lo riesgoso);
    # "never" = auto-aprueba lo reversible, confirma solo lo destructivo; "all" =
    # PERMISIVO TOTAL, nada confirma (incl. irreversible); "always" = confirma todo
    # (auditoría). Ver safety_pkg/confirmation_policy.
    "confirmationPolicy": "GEMMA4_CONFIRMATION_POLICY",
}


def _apply_toggle_env_vars(settings: dict[str, Any]) -> None:
    """Write each toggle into os.environ as the env var that the agent reads.
    We always write — even when the toggle is False — so this function fully
    represents the user's intent rather than depending on the previous env
    state."""
    for ui_key, env_name in _TOGGLE_ENV_MAP.items():
        if ui_key in settings:
            os.environ[env_name] = "true" if bool(settings[ui_key]) else "false"
    # Optim tab toggles (mismo formato boolean -> "true"/"false")
    for ui_key, env_name in _OPTIM_TOGGLE_ENV_MAP.items():
        if ui_key in settings:
            os.environ[env_name] = "true" if bool(settings[ui_key]) else "false"
    # Optim tab strings: si el valor es vacio, BORRAR la env var (semantica
    # "off" = no setear). Caso contrario, asignar el string tal cual.
    for ui_key, env_name in _OPTIM_STRING_ENV_MAP.items():
        if ui_key not in settings:
            continue
        val = settings[ui_key]
        text = "" if val is None else str(val).strip()
        if not text:
            os.environ.pop(env_name, None)
        else:
            os.environ[env_name] = text


def _ts_now() -> str:
    """`HH:MM:SS` timestamp used by activity-log entries we publish ourselves."""
    n = datetime.datetime.now()
    return f"{n.hour:02d}:{n.minute:02d}:{n.second:02d}"


def _drain_one(q: Any, timeout_s: float) -> dict[str, Any] | None:
    """Blocking single-event drain for the WS writer task. Returns None on
    timeout so the writer can emit a heartbeat without spinning."""
    try:
        return q.get(timeout=timeout_s)
    except queue.Empty:
        return None


# ---------- app factory ----------

def create_app(config: AgentConfig | None = None) -> FastAPI:
    cfg = config or AgentConfig.from_env()
    app = FastAPI(title="gemma4 field", version="0.1.0")

    # apply the persisted toggle settings to env vars BEFORE the agent
    # builds, so the first run respects whatever the user toggled last.
    # without this, the toggles only take effect after the user re-saves
    # settings and restarts — a frustrating round trip.
    try:
        _apply_toggle_env_vars(_load_settings())
    except Exception as exc:
        logger.warning("could not apply persisted toggle env vars: %s", exc)

    # install the log recorder FIRST so it catches BOOT events emitted
    # during agent and voice startup. writes to ~/.gemma4/logs/<sid>/
    # (full.log = every BUS event, chat.log = only user-visible activity).
    from .log_recorder import RECORDER
    RECORDER.install()

    # boot the agent eagerly so the user doesn't pay 1-3s on the first
    # /turn. RUNNER.start() spins a daemon thread that builds Gemma4Agent
    # in the background; the WS subscribers see BOOT/SYSTEM activity
    # entries as it loads. by the time the user types, the agent is
    # usually idle and ready.
    from ..agent_core.agent_runner import RUNNER
    RUNNER.start()

    # The voice pipeline (wake + STT) is not booted here; see the research
    # at docs/architecture/voice_pipeline_redesign_research_prompt.md.
    # TTS (Piper) is still available at gemma4_agent.voice.tts when needed.

    # health endpoints + APIs come before the static mount, otherwise the
    # SPA fallback eats them.

    @app.get("/model")
    def get_model() -> Any:
        info = _current_model_info(cfg)
        if info is None:
            return JSONResponse({"status": "loading"}, status_code=503)
        return asdict(info)

    @app.get("/metrics")
    def get_metrics() -> Any:
        return _metrics_snapshot()

    @app.get("/hardware")
    def get_hardware() -> Any:
        # specs are immutable for the process lifetime — cached on first call.
        return _hardware_info()

    @app.get("/agent/modes")
    def agent_modes() -> Any:
        """List the agent modes the LLM can run in. `auto` is the default and
        infers the mode from the user's message; the others force the choice.
        The descriptions come from modes.py system_hint shortened to one line."""
        return {
            "items": [
                {"name": "auto",          "description": "infer from message (default)"},
                {"name": "fast_action",   "description": "short reasoning, smallest tool sequence"},
                {"name": "deep_action",   "description": "multi-step PC missions, think + act + verify"},
                {"name": "vision_action", "description": "screenshots & images before GUI actions"},
                {"name": "audio_mode",    "description": "treat attached audio as user evidence"},
                {"name": "research",      "description": "web sources, multi-call evidence gathering"},
            ],
        }

    @app.get("/agent/personas")
    def agent_personas() -> Any:
        """Personas live in personas.py PERSONAS dict. We surface name +
        description + preferred_tools so the UI can show what each does."""
        try:
            from ..support.personas import PERSONAS
            items = []
            for key in sorted(PERSONAS.keys()):
                p = PERSONAS[key]
                items.append({
                    "name": p.name,
                    "description": p.description,
                    "tone": p.tone,
                    "preferred_tools": list(p.preferred_tools),
                })
            return {"items": items}
        except Exception as exc:
            return {"items": [], "error": str(exc)}

    @app.get("/voice/inventory")
    def voice_inventory() -> Any:
        """Lists the active local voice stack for the transcript tab."""
        # STT (Parakeet) — default engine in voice.pipeline. This does not load
        # the model; it only checks whether the bundle files are present.
        try:
            from ..voice.parakeet_stt import DEFAULT_MODEL_DIR
            parakeet_downloaded = all(
                (DEFAULT_MODEL_DIR / f).exists()
                for f in ("encoder.int8.onnx", "decoder.int8.onnx",
                          "joiner.int8.onnx", "tokens.txt")
            )
        except Exception:
            parakeet_downloaded = False

        # Wake (LiveKit) — preferred backend in voice.wake, with OWW fallback.
        try:
            from ..voice.wake import LIVEKIT_MODEL_PATH
            wake_name = f"LiveKit {LIVEKIT_MODEL_PATH.stem}"
            wake_downloaded = LIVEKIT_MODEL_PATH.exists()
        except Exception:
            wake_name = "LiveKit hey_gemma"
            wake_downloaded = False

        # TTS (Piper) — we control the catalog explicitly in voice/tts.py
        try:
            from ..voice.tts import PIPER_VOICE_URLS, voice_files_exist
        except Exception:
            PIPER_VOICE_URLS = {}  # noqa: N806
            voice_files_exist = lambda _v: False  # noqa: E731
        tts_voices = []
        for name in sorted(PIPER_VOICE_URLS.keys()):
            tts_voices.append({
                "name": name,
                "downloaded": bool(voice_files_exist(name)),
            })

        return {
            "stt_default": "parakeet-tdt-0.6b-v3-int8",
            "stt": [{
                "name": "parakeet-tdt-0.6b-v3-int8",
                "size_label": "sherpa-onnx CPU int8",
                "downloaded": parakeet_downloaded,
            }],
            "tts": tts_voices,
            "wake": {"name": wake_name, "downloaded": wake_downloaded},
            "languages": ["auto", "es", "en", "fr", "pt", "it", "de"],
            "pipeline_status": "active",
        }

    @app.post("/agent/restart")
    def agent_restart() -> Any:
        """Trigger a full re-boot of the agent + llama-server.

        Used by the inline retry button on the chat input when the cold-start
        failed. The runner publishes its usual `agent` + `boot_stage` lifecycle
        events as it rebuilds, so the UI updates without any extra wiring.
        Returns immediately — the actual rebuild runs in a background thread.
        """
        from ..agent_core.agent_runner import RUNNER
        RUNNER.restart()
        BUS.publish({
            "type": "activity",
            "entry": {
                "id": uuid.uuid4().hex[:8],
                "src": "SYSTEM",
                "msg": "agent restart triggered from UI",
                "ts": _ts_now(),
            },
        })
        return {"status": "accepted"}

    @app.post("/agent/recycle_server")
    def agent_recycle_server() -> Any:
        """Recycle solo llama-server, sin tocar agent.

        Util para mitigar mmproj leak (#21690) sin perder estado del agente.
        Diferencia con /agent/restart: este solo mata+relanza el subprocess
        del LLM. La sesion, memory, knowledge, etc., quedan intactas.

        Devuelve 202 accepted; el recycle corre sync (es rapido, 4-10s).
        Publica boot_stage 'vision_relaunch' al BUS para que la UI muestre
        progreso.
        """
        from .llama_server import LlamaServerManager
        from .profiles import get_active_profile

        profile = get_active_profile()
        if not profile.server_running:
            return {"status": "skipped", "reason": "profile has server_running=False"}

        manager = LlamaServerManager()
        # recycle_for_vision_leak requiere que el manager conozca el perfil
        # actual. Como crear LlamaServerManager nuevo no lo "adopta", forzamos
        # restart sobre el perfil activo si hay server escuchando.
        try:
            result = manager.restart(profile)
        except Exception as exc:
            BUS.publish({
                "type": "activity",
                "entry": {
                    "id": uuid.uuid4().hex[:8],
                    "src": "SYSTEM",
                    "msg": f"recycle_server failed: {exc}",
                    "ts": _ts_now(),
                },
            })
            return {"status": "error", "error": str(exc)}, 500

        # Reset del counter de imagenes para empezar siguiente ciclo limpio.
        try:
            from ..tools_pkg.multimodal import reset_image_counter
            reset_image_counter()
        except Exception:
            pass

        BUS.publish({
            "type": "activity",
            "entry": {
                "id": uuid.uuid4().hex[:8],
                "src": "SYSTEM",
                "msg": f"llama-server recycled (mmproj leak mitigation #21690) · {result}",
                "ts": _ts_now(),
            },
        })
        return {"status": "accepted", "result": result}

    @app.get("/agent/status")
    def agent_status() -> Any:
        """Lets the UI gate the chat input until the agent + llama-server
        are ACTUALLY ready. `ready` requires three conditions in order:
          (a) `built`  — Gemma4Agent constructed successfully
          (b) `warmed` — a 1-token completion came back at least once
          (c) `healthy` — llama-server still answers /health right now

        (c) matters because if llama-server crashes after warmup the agent
        can't actually serve a turn — `warmed` alone would mislead the UI
        into showing the input enabled."""
        from ..agent_core.agent_runner import RUNNER
        agent = getattr(RUNNER, "_agent", None)
        built = agent is not None
        warmed = RUNNER.is_warmed_up()
        # router_ready: el router semántico terminó (o está deshabilitado/
        # degradado-tolerado). Sin esta 4ª condición, este PULL (poll de 4s /
        # cliente tardío) recomputaría ready SIN saber del router y abriría la
        # casilla de chat con el router a medias.
        router_ready = RUNNER.is_router_ready()
        healthy = False
        if built:
            try:
                healthy = bool(agent.client.health(timeout_s=0.4))
            except Exception:
                healthy = False
        return {
            "built": built,
            "healthy": healthy,
            "ready": built and warmed and healthy and router_ready,
        }

    @app.get("/settings")
    def get_settings() -> Any:
        return _load_settings()

    @app.put("/settings")
    def put_settings(body: dict[str, Any]) -> Any:
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="settings must be a JSON object")
        _save_settings(body)
        # Mirror the toggle group into env vars so the next agent restart
        # picks them up. The UI shows a "restart agent now" button after
        # apply; this just ensures that when the user clicks it, the
        # rebuild actually reflects the new toggles.
        _apply_toggle_env_vars(body)
        return {"status": "ok"}

    @app.post("/turn")
    def post_turn(req: TurnRequest) -> Any:
        # reject whitespace-only input. the UI already guards on draft.trim()
        # but server-side validation keeps callers (and curl smoke tests) from
        # publishing an empty YOU entry to every connected client.
        text = req.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="text must not be empty")
        # hand the turn off to the long-lived AgentRunner thread. it processes
        # turns serially against the single llama-server slot and publishes
        # state/activity/tokens events to BUS as the agent makes progress —
        # the WS subscribers pick them up automatically.
        from ..agent_core.agent_runner import RUNNER
        RUNNER.submit(
            text,
            images=req.attachments or None,
        )
        return {"status": "accepted"}

    # ---------- voice ----------
    # Voice pipeline v2. VOICE singleton lives in
    # voice_runner.py and owns the VoicePipeline + StreamingTTS.

    @app.get("/voice/status")
    def voice_status() -> Any:
        from .voice_runner import VOICE
        return VOICE.status()

    @app.post("/voice/start")
    def voice_start() -> Any:
        """Enable voice loop. Loads VAD + wake + STT + Piper on first
        call (~1-3s blocking). Idempotent."""
        from .voice_runner import VOICE
        # Wire UI feedback BEFORE enabling so the very first wake is caught.
        # The web UI (ui_field) drives its mic animation off {type:"state"}
        # BUS events and beeps off {type:"voice_wake"}. Without these the
        # conv state jumps idle->thinking with no "listening" phase and no
        # audible cue. Map the pipeline's state names to the frontend's
        # ConvState vocabulary (idle/listening/thinking/speaking).
        _VOICE_STATE_MAP = {
            "LISTENING": "listening",
            "TRANSCRIBING": "listening",  # still capturing the user's command
            "IDLE_LISTENING": "idle",
        }

        def _on_voice_state(state: str) -> None:
            # NO_SPEECH: the capture was dropped (silence / Whisper hallucination)
            # — a user who DID try to speak must get feedback, not a silent drop
            # back to idle ("the mic ignored me"). Emit a distinct event the HUD
            # can flash, then fall through to idle via the IDLE_LISTENING that
            # the pipeline emits right after.
            if state == "NO_SPEECH":
                BUS.publish({"type": "voice_no_speech"})
                return
            mapped = _VOICE_STATE_MAP.get(state)
            if mapped is not None:
                BUS.publish({"type": "state", "value": mapped})

        def _on_voice_wake() -> None:
            # Tell the frontend to chirp; also emit listening immediately.
            BUS.publish({"type": "voice_wake"})
            BUS.publish({"type": "state", "value": "listening"})
            # Backend-side beep as a fallback (works even if the browser
            # tab is muted / lacks an audio gesture). Windows-only; silent
            # no-op elsewhere.
            try:
                import winsound
                winsound.Beep(880, 90)
            except Exception:
                pass

        VOICE.set_on_state(_on_voice_state)
        VOICE.set_on_wake_event(_on_voice_wake)
        ok = VOICE.enable()
        # Wire on_command to the agent runner so transcribed commands
        # become turns.
        if ok:
            from ..agent_core.agent_runner import RUNNER

            def _submit_voice(text: str) -> None:
                # GATE DE BOOT (2026-06-18): no actuar sobre wakes mientras el
                # agente/router todavía cargan. Durante el arranque la CPU/GPU
                # están saturadas (embeddings, prewarm) y la captura de audio
                # puede glitchear -> el wake dispara por un transitorio y, peor,
                # el turno se ENCOLA y se ejecuta segundos después, STALE y fuera
                # de contexto. Medido: un falso "Thank you" disparó a mitad del
                # boot (router aún cargando) y se procesó 22s tarde. El mismo
                # gate que habilita la casilla de chat (ready = built ∧ warmed ∧
                # healthy ∧ router) aplica a la voz: si no está listo, se
                # DESCARTA (no se encola).
                if not (RUNNER.agent_ready() and RUNNER.is_router_ready()):
                    logger.info(
                        "voice command dropped: agente no listo (boot) text=%r",
                        text[:80])
                    return
                RUNNER.submit(text)

            VOICE.set_on_command(_submit_voice)
        return {"ok": ok, **VOICE.status()}

    @app.post("/voice/stop")
    def voice_stop() -> Any:
        from .voice_runner import VOICE
        VOICE.disable()
        return {"ok": True, **VOICE.status()}

    @app.post("/voice/trigger")
    def voice_trigger() -> Any:
        """Push-to-talk: synthesise a wake event. Not implemented in
        v2 pipeline yet (no clean state-machine injection point); the
        endpoint returns ok=False so the UI shows a clear toast."""
        from .voice_runner import VOICE
        VOICE.trigger_manual()
        return {"ok": False, **VOICE.status(),
                "message": "trigger_manual not implemented in voice v2"}

    # ---------- sessions ----------

    @app.get("/sessions")
    def list_sessions() -> Any:
        try:
            from ..memory_pkg.sessions import SessionStore
            store = SessionStore()
            rows = store.list_sessions(limit=50)
        except Exception as exc:
            logger.warning("sessions list failed: %s", exc)
            return {"sessions": [], "error": str(exc)}
        # adapt to the UI's SessionRow shape (id / label / ts / current).
        # current = null for now — once we wire current-session tracking,
        # it'll flip true on the active one.
        adapted = [
            {
                "id": str(r.get("id") or ""),
                "label": str(r.get("title") or "(sin titulo)"),
                "ts": str(r.get("updated_at") or ""),
                "turn_count": int(r.get("turn_count") or 0),
                "current": False,
            }
            for r in rows
        ]
        return {"sessions": adapted}

    # ---------- surfaces (memory / triggers / tools / sessions counts) ----------

    @app.get("/surfaces")
    def surfaces() -> Any:
        """Real counts pulled from the agent + memory store + sessions dir.
        Used by ActivityPanel's surfaces 2x2 grid. Sessions count comes from
        the on-disk sessions directory so it's available even before the
        agent is built."""
        sessions_n = 0
        memory_n = 0
        triggers_n = 0
        tools_n = 0
        try:
            from ..memory_pkg.sessions import SessionStore
            sessions_n = len(SessionStore().list_sessions(limit=1000))
        except Exception:
            pass
        # the agent owns memory/triggers/tools counts. if it isn't built yet,
        # we return whatever we can — the UI shows "—" for missing entries.
        try:
            from ..agent_core.agent_runner import RUNNER
            agent = getattr(RUNNER, "_agent", None)
            if agent is not None:
                # memory: count of pinned facts. recall().items is a dict
                # keyed by fact name, so len() over the dict is what we want.
                try:
                    rec = agent.memory.recall()
                    items = rec.get("items") if isinstance(rec, dict) else None
                    if isinstance(items, dict):
                        memory_n = len(items)
                    elif isinstance(items, list):
                        memory_n = len(items)
                except Exception:
                    pass
                try:
                    tools_n = len(agent.tools.schemas)
                except Exception:
                    pass
                # phrase triggers come from a module-level helper
                try:
                    from ..domain_tools import active_phrase_triggers
                    triggers_n = len(active_phrase_triggers(agent.state))
                except Exception:
                    pass
        except Exception:
            pass
        return {
            "sessions": sessions_n,
            "memory": memory_n,
            "triggers": triggers_n,
            "tools": tools_n,
        }

    # ---------- profiles ----------

    # ============ MEMORY (read + write) ============
    # mirrors legacy MemoryDialog. recall() returns {ok, items: {key: {value, updated_at}}}
    # so we adapt to a list[{key, value, updated_at}] that's easier to render.

    def _agent_or_none() -> Any:
        from ..agent_core.agent_runner import RUNNER
        return getattr(RUNNER, "_agent", None)

    @app.get("/memory")
    def list_memory() -> Any:
        agent = _agent_or_none()
        if agent is None:
            return {"items": [], "error": "agent not ready"}
        try:
            rec = agent.memory.recall()
            items = rec.get("items") if isinstance(rec, dict) else {}
            adapted: list[dict[str, str]] = []
            if isinstance(items, dict):
                for key, entry in items.items():
                    if isinstance(entry, dict):
                        adapted.append({
                            "key": str(key),
                            "value": str(entry.get("value", "")),
                            "updated_at": str(entry.get("updated_at", "")),
                        })
                    else:
                        adapted.append({"key": str(key), "value": str(entry), "updated_at": ""})
            adapted.sort(key=lambda r: r["key"].casefold())
            return {"items": adapted, "count": len(adapted)}
        except Exception as exc:
            return {"items": [], "error": str(exc)}

    class _MemorySave(BaseModel):
        key: str
        value: str

    @app.post("/memory")
    def memory_save(body: _MemorySave) -> Any:
        agent = _agent_or_none()
        if agent is None:
            raise HTTPException(status_code=503, detail="agent not ready")
        key = body.key.strip()
        if not key:
            raise HTTPException(status_code=400, detail="key required")
        res = agent.memory.save(key, body.value.strip())
        BUS.publish({
            "type": "activity",
            "entry": {
                "id": uuid.uuid4().hex[:8],
                "src": "MEMORY",
                "msg": f"saved · {key}",
                "ts": _ts_now(),
            },
        })
        return res

    @app.delete("/memory/{key:path}")
    def memory_delete(key: str) -> Any:
        agent = _agent_or_none()
        if agent is None:
            raise HTTPException(status_code=503, detail="agent not ready")
        res = agent.memory.delete(key)
        BUS.publish({
            "type": "activity",
            "entry": {
                "id": uuid.uuid4().hex[:8],
                "src": "MEMORY",
                "msg": f"deleted · {key}" if key != "*" else f"cleared · {res.get('deleted', 0)} entries",
                "ts": _ts_now(),
            },
        })
        return res

    # ============ TRIGGERS (CRUD via the 'routine' tool) ============
    # legacy TriggersDialog used tool_exec("routine", {...}). we expose the
    # same surface here as REST. each trigger is a routine with trigger.type
    # in {on_phrase, on_keyword} and steps[] of {tool, args}.

    @app.get("/triggers")
    def list_triggers() -> Any:
        agent = _agent_or_none()
        if agent is None:
            return {"items": [], "error": "agent not ready"}
        try:
            res = agent.tools.execute("routine", {
                "action": "list", "include_closed": False, "limit": 200,
            })
            if not isinstance(res, dict) or not res.get("ok"):
                return {"items": [], "error": str(res.get("error") if isinstance(res, dict) else res)}
            raw = res.get("items") or res.get("routines") or []
            adapted: list[dict[str, Any]] = []
            for r in raw:
                if not isinstance(r, dict):
                    continue
                meta_raw = r.get("metadata")
                meta: dict[str, Any] = meta_raw if isinstance(meta_raw, dict) else r
                tt = str(meta.get("trigger_type") or "").lower()
                if tt not in ("on_phrase", "on_keyword"):
                    continue
                trig_raw = meta.get("trigger")
                trig: dict[str, Any] = trig_raw if isinstance(trig_raw, dict) else {}
                phrase = str(trig.get("phrase") or trig.get("keyword") or "")
                adapted.append({
                    "id": str(r.get("id") or r.get("resource_id") or ""),
                    "label": str(r.get("label") or meta.get("label") or "(no label)"),
                    "phrase": phrase,
                    "type": tt,
                    "enabled": bool(meta.get("enabled", True)),
                    "steps": meta.get("steps") or [],
                })
            return {"items": adapted, "count": len(adapted)}
        except Exception as exc:
            return {"items": [], "error": str(exc)}

    class _TriggerCreate(BaseModel):
        label: str
        phrase: str
        type: str = "on_phrase"
        steps: list[dict[str, Any]] = []
        enabled: bool = True

    @app.post("/triggers")
    def trigger_create(body: _TriggerCreate) -> Any:
        agent = _agent_or_none()
        if agent is None:
            raise HTTPException(status_code=503, detail="agent not ready")
        label = body.label.strip()
        phrase = body.phrase.strip()
        if not label or not phrase:
            raise HTTPException(status_code=400, detail="label and phrase required")
        res = agent.tools.execute("routine", {
            "action": "create",
            "label": label,
            "trigger": {"type": body.type, "phrase": phrase},
            "steps": body.steps,
            "enabled": body.enabled,
        })
        if isinstance(res, dict) and res.get("ok"):
            BUS.publish({
                "type": "activity",
                "entry": {
                    "id": uuid.uuid4().hex[:8],
                    "src": "TRIGGER",
                    "msg": f"created · {label} · '{phrase}'",
                    "ts": _ts_now(),
                },
            })
        return res

    @app.put("/triggers/{tid}")
    def trigger_update(tid: str, body: _TriggerCreate) -> Any:
        """Edit an existing trigger. The 'routine' tool has no update action
        so we delete-and-recreate, mirroring legacy TriggersDialog._on_save.
        The new trigger gets a fresh id from the agent — the UI refreshes
        its list after this returns."""
        agent = _agent_or_none()
        if agent is None:
            raise HTTPException(status_code=503, detail="agent not ready")
        label = body.label.strip()
        phrase = body.phrase.strip()
        if not label or not phrase:
            raise HTTPException(status_code=400, detail="label and phrase required")
        # delete old (best-effort; ignore if it didn't exist)
        try:
            agent.tools.execute("routine", {"action": "delete", "id": tid})
        except Exception as exc:
            logger.debug("trigger_update: delete of %s failed: %s", tid, exc)
        res = agent.tools.execute("routine", {
            "action": "create",
            "label": label,
            "trigger": {"type": body.type, "phrase": phrase},
            "steps": body.steps,
            "enabled": body.enabled,
        })
        if isinstance(res, dict) and res.get("ok"):
            BUS.publish({
                "type": "activity",
                "entry": {
                    "id": uuid.uuid4().hex[:8],
                    "src": "TRIGGER",
                    "msg": f"updated · {label} · '{phrase}'",
                    "ts": _ts_now(),
                },
            })
        return res

    @app.delete("/triggers/{tid}")
    def trigger_delete(tid: str) -> Any:
        agent = _agent_or_none()
        if agent is None:
            raise HTTPException(status_code=503, detail="agent not ready")
        res = agent.tools.execute("routine", {"action": "delete", "id": tid})
        BUS.publish({
            "type": "activity",
            "entry": {
                "id": uuid.uuid4().hex[:8],
                "src": "TRIGGER",
                "msg": f"deleted · {tid}",
                "ts": _ts_now(),
            },
        })
        return res

    @app.post("/triggers/{tid}/run")
    def trigger_run(tid: str) -> Any:
        agent = _agent_or_none()
        if agent is None:
            raise HTTPException(status_code=503, detail="agent not ready")
        res = agent.tools.execute("routine", {"action": "run_now", "id": tid})
        BUS.publish({
            "type": "activity",
            "entry": {
                "id": uuid.uuid4().hex[:8],
                "src": "TRIGGER",
                "msg": f"run_now · {tid} → {res.get('status', 'done') if isinstance(res, dict) else 'done'}",
                "ts": _ts_now(),
            },
        })
        return res

    # ============ TOOLS (read schemas + execute arbitrary tool) ============

    @app.get("/tools")
    def list_tools() -> Any:
        agent = _agent_or_none()
        if agent is None:
            return {"items": [], "error": "agent not ready"}
        try:
            schemas = agent.tools.schemas
            adapted: list[dict[str, Any]] = []
            for s in schemas:
                if not isinstance(s, dict):
                    continue
                fn = s.get("function") if "function" in s else s
                if not isinstance(fn, dict):
                    continue
                adapted.append({
                    "name": str(fn.get("name") or ""),
                    "description": str(fn.get("description") or ""),
                    "schema": s,
                })
            adapted.sort(key=lambda d: d["name"])
            return {"items": adapted, "count": len(adapted)}
        except Exception as exc:
            return {"items": [], "error": str(exc)}

    class _ToolExec(BaseModel):
        name: str
        args: dict[str, Any] = {}

    @app.post("/tools/execute")
    def tool_execute(body: _ToolExec) -> Any:
        """Run any registered tool by name with an args dict. This is the same
        surface the legacy ToolExplorer used. Powerful — only exposed because
        the UI is local-only."""
        agent = _agent_or_none()
        if agent is None:
            raise HTTPException(status_code=503, detail="agent not ready")
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="name required")
        try:
            res = agent.tools.execute(name, body.args or {})
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        BUS.publish({
            "type": "activity",
            "entry": {
                "id": uuid.uuid4().hex[:8],
                "src": "TOOL",
                "msg": f"{name} · manual run",
                "ts": _ts_now(),
            },
        })
        return res

    # ============ SESSIONS (delete + rename, on top of load/new) ============

    class _SessionRename(BaseModel):
        id: str
        title: str

    @app.delete("/sessions/{sid}")
    def session_delete(sid: str) -> Any:
        try:
            from ..memory_pkg.sessions import SessionStore
            store = SessionStore()
            res = store.delete(sid)
            BUS.publish({
                "type": "activity",
                "entry": {
                    "id": uuid.uuid4().hex[:8],
                    "src": "SYSTEM",
                    "msg": f"session deleted · #{sid[:8]}",
                    "ts": _ts_now(),
                },
            })
            return res
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/sessions/rename")
    def session_rename(body: _SessionRename) -> Any:
        try:
            from ..memory_pkg.sessions import SessionStore
            store = SessionStore()
            loaded = store.load(body.id)
            if loaded is None:
                raise HTTPException(status_code=404, detail=f"session {body.id} not found")
            new_title = body.title.strip() or "(sin título)"
            loaded.title = new_title  # type: ignore[attr-defined]
            store.save(loaded)
            BUS.publish({
                "type": "activity",
                "entry": {
                    "id": uuid.uuid4().hex[:8],
                    "src": "SYSTEM",
                    "msg": f"session renamed · #{body.id[:8]} → {new_title}",
                    "ts": _ts_now(),
                },
            })
            return {"ok": True, "id": body.id, "title": new_title}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    # ---------- session mutations ----------

    class _SessionLoad(BaseModel):
        id: str

    @app.post("/sessions/load")
    def session_load(body: _SessionLoad) -> Any:
        """Load a saved session: clear current agent history + emit a SYSTEM
        entry with the title and last turns. Matches legacy _load_session."""
        try:
            from ..agent_core.agent_runner import RUNNER
            from ..memory_pkg.sessions import SessionStore
            store = SessionStore()
            loaded = store.load(body.id)
            if loaded is None:
                raise HTTPException(status_code=404, detail=f"session {body.id} not found")
            agent = getattr(RUNNER, "_agent", None)
            if agent is not None:
                agent.clear()
            n_turns = len(loaded.turns) if hasattr(loaded, "turns") else 0
            title = getattr(loaded, "title", "") or "(sin título)"
            BUS.publish({
                "type": "activity",
                "entry": {
                    "id": uuid.uuid4().hex[:8],
                    "src": "SYSTEM",
                    "msg": f"session loaded · #{body.id[:8]} · {n_turns} turns · {title}",
                    "ts": _ts_now(),
                },
            })
            BUS.publish({"type": "session", "id": body.id, "label": title})
            return {"ok": True, "id": body.id, "turns": n_turns, "title": title}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/sessions/new")
    def session_new() -> Any:
        """Start a fresh session: clear agent history + emit SYSTEM entry."""
        try:
            from ..agent_core.agent_runner import RUNNER
            from ..memory_pkg.sessions import Session
            agent = getattr(RUNNER, "_agent", None)
            if agent is not None:
                agent.clear()
            new_id = Session.new().id  # type: ignore[attr-defined]
            BUS.publish({
                "type": "activity",
                "entry": {
                    "id": uuid.uuid4().hex[:8],
                    "src": "SYSTEM",
                    "msg": f"new session · #{new_id[:8]} · context cleared",
                    "ts": _ts_now(),
                },
            })
            BUS.publish({"type": "session", "id": new_id, "label": "(sin título)"})
            return {"ok": True, "id": new_id}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/profile")
    def get_profile() -> Any:
        try:
            from .profiles import get_active_profile
            p = get_active_profile()
            # La UI ahora usa los nombres canónicos por VRAM (vram3..vram16,
            # standby) directamente, así que devolvemos el nombre tal cual.
            return {
                "active": p.name,
                "active_full": p.name,
                "display_name": p.display_name,
                "context_size": p.context_size,
                "server_running": p.server_running,
            }
        except Exception as exc:
            return {"active": "vram4", "error": str(exc)}

    @app.get("/accessibility")
    def get_accessibility() -> Any:
        """Modo de accesibilidad activo + catálogo, para el chip de la UI."""
        try:
            from .. import accessibility as _a11y
            active = _a11y.get_active_mode()
            return {
                "active": active.name,
                "display_name": active.display_name,
                "modes": [
                    {"name": m.name, "display_name": m.display_name,
                     "description": m.description}
                    for m in (_a11y.get(n) for n in _a11y.list_names())
                ],
            }
        except Exception as exc:
            return {"active": "normal", "modes": [], "error": str(exc)}

    @app.put("/accessibility")
    def put_accessibility(body: AccessibilityChange) -> Any:
        """Cambia el modo de accesibilidad (persiste). No reinicia el server: es
        una capa de comportamiento (system_hint + guardas), no de modelo."""
        try:
            from .. import accessibility as _a11y
            m = _a11y.set_active_mode(body.mode)
            BUS.publish({"type": "activity", "entry": {
                "id": uuid.uuid4().hex[:8], "src": "SYSTEM",
                "msg": f"accessibility · {m.display_name}", "ts": _ts_now()}})
            return {"ok": True, "active": m.name, "display_name": m.display_name}
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # NOTE: ProfileChange is defined at MODULE level (see its docstring) —
    # a function-local Pydantic model can't be resolved from the stringized
    # forward-ref annotation and silently breaks body binding (422).

    # El sistema usa un solo perfil (vram4) + standby. Todos los chips/nombres
    # viejos de cualquier UI cacheada (perf/bal8/bal/light y también
    # vram3/6/8/12/16) caen a vram4. set_active_profile + _resolve_alias
    # ya resuelven los nombres legacy igualmente; este map sólo cubre los chips
    # cortos de la UI vieja que NO son nombres de perfil. stdby -> standby.
    _PROFILE_UI_ALIASES: dict[str, str] = {
        "perf":  "vram4",
        "bal8":  "vram4",
        "bal":   "vram4",
        "light": "vram4",
        "stdby": "standby",
    }

    @app.put("/profile")
    def put_profile(body: ProfileChange) -> Any:
        """Switch the active VRAM profile.

        Persists to ~/.gemma4, applies env vars, AND — when the change needs
        a different llama-server (model / context / vision / on-off) — restarts
        the shared llama-server with the new profile so the model actually
        swaps and VRAM changes. The restart runs in a background thread (it
        takes ~4-10 s) and streams boot stages to the BUS; the HTTP response
        returns immediately with restarting=True so the chip flips instantly.

        Acepta nombres canónicos (vram8) y aliases UI viejos (bal8).
        """
        try:
            from .profiles import (apply_profile_to_env, get_active_profile,
                                    set_active_profile, requires_server_restart)
            raw = body.name.strip().lower()
            name = _PROFILE_UI_ALIASES.get(raw, raw)
            prev = get_active_profile()
            set_active_profile(name)
            p = get_active_profile()
            apply_profile_to_env(p)

            def _activity(msg: str) -> None:
                BUS.publish({"type": "activity", "entry": {
                    "id": uuid.uuid4().hex[:8], "src": "SYSTEM",
                    "msg": msg, "ts": _ts_now()}})

            _activity(f"profile · switched to {p.display_name}")

            needs_restart = requires_server_restart(prev, p)
            if needs_restart:
                def _do_restart() -> None:
                    try:
                        from .llama_server import get_shared_manager
                        BUS.publish({"kind": "boot_stage", "stage": "profile_swap",
                                     "phase": "starting", "profile": p.name})
                        _activity(f"profile · loading {p.display_name} model…")
                        mgr = get_shared_manager()
                        result = mgr.force_restart_for_profile(p)
                        ok = result in ("started", "already_running", "stopped")
                        _activity(
                            f"profile · {p.display_name} "
                            + ("ready" if ok else f"restart={result}")
                        )
                        BUS.publish({"kind": "boot_stage", "stage": "profile_swap",
                                     "phase": "completed", "profile": p.name,
                                     "result": result})
                    except Exception as exc:  # never let the thread die silent
                        _activity(f"profile · restart FAILED: {exc}")
                threading.Thread(target=_do_restart, name="profile-swap",
                                 daemon=True).start()

            return {"ok": True, "active": p.name,
                    "display_name": p.display_name, "restarting": needs_restart}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/log/clear")
    def clear_log() -> Any:
        """Wipe the activity log on every connected client. Mirrors the
        legacy Ctrl+L behaviour. We publish a marker event so the UI's
        reducer can drop its entries array."""
        BUS.publish({"type": "log_clear"})
        # also append a SYSTEM entry so the user has a breadcrumb
        BUS.publish({
            "type": "activity",
            "entry": {
                "id": uuid.uuid4().hex[:8],
                "src": "SYSTEM",
                "msg": "log cleared",
                "ts": _ts_now(),
            },
        })
        return {"ok": True}

    @app.post("/hardware/redetect")
    def redetect_hardware() -> Any:
        """Drop the hardware cache so the next /hardware call re-runs the
        detection. Useful after plugging/unplugging a GPU or upgrading drivers."""
        global _HARDWARE_CACHE
        _HARDWARE_CACHE = None
        info = _hardware_info()
        BUS.publish({
            "type": "activity",
            "entry": {
                "id": uuid.uuid4().hex[:8],
                "src": "SYSTEM",
                "msg": f"hardware re-detected · cpu={info['cpu']} · gpu={info['gpu']}",
                "ts": _ts_now(),
            },
        })
        return info

    @app.post("/upload")
    async def upload_attachment(file: UploadFile = File(...)) -> Any:
        """Save an uploaded file to ~/.gemma4/uploads/ and return its
        absolute path. The chat input passes that path back to /turn as an
        'attachment' so the agent's vision/audio pipeline can read it.

        Browsers can't expose a local absolute path for security, so the
        upload-then-reference dance is the only way the agent gets at real
        bytes. Files older than 24h get cleaned up best-effort on each
        upload so this dir doesn't grow unbounded."""
        uploads = SETTINGS_DIR / "uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        # cleanup: drop files older than 24h. cheap to do on every upload
        # since the dir is small in practice.
        try:
            cutoff = datetime.datetime.now().timestamp() - 86400
            for p in uploads.iterdir():
                try:
                    if p.is_file() and p.stat().st_mtime < cutoff:
                        p.unlink()
                except OSError:
                    pass
        except OSError:
            pass

        # sanitize the filename — never trust the client. uuid prefix avoids
        # collisions when the user uploads two files with the same name.
        original = (file.filename or "upload").replace("\\", "/").rsplit("/", 1)[-1]
        safe = "".join(c for c in original if c.isalnum() or c in "._-") or "upload"
        target = uploads / f"{uuid.uuid4().hex[:8]}_{safe}"
        try:
            data = await file.read()
            target.write_bytes(data)
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"write failed: {exc}")
        return {
            "ok": True,
            "path": str(target.resolve()),
            "name": original,
            "size": len(data),
        }

    @app.get("/agent/system_prompt")
    def get_system_prompt() -> Any:
        """Return the live SYSTEM_PROMPT string used by the agent so the
        Settings 'prompt' tab shows the real prompt, not a hardcoded preview.
        Includes only the base prompt — persona / project / recall hints are
        appended per-turn and aren't part of the static text."""
        try:
            from ..agent_core.agent import SYSTEM_PROMPT
            return {"prompt": SYSTEM_PROMPT}
        except Exception as exc:
            return {"prompt": "", "error": str(exc)}

    @app.post("/activity")
    def post_activity(req: ActivityRequest) -> Any:
        """Append a UI-originated entry (SYSTEM message from + new / help)
        to the activity log so every connected client sees it."""
        src = req.src.strip()
        msg = req.msg.strip()
        if not src or not msg:
            raise HTTPException(status_code=400, detail="src and msg are required")

        BUS.publish({
            "type": "activity",
            "entry": {
                "id": uuid.uuid4().hex[:8],
                "src": src,
                "msg": msg,
                "ts": _ts_now(),
            },
        })
        return {"status": "ok"}

    @app.websocket("/events")
    async def ws_events(ws: WebSocket) -> None:
        await ws.accept()
        sub = BUS.subscribe()
        loop = asyncio.get_running_loop()

        try:
            # send an initial model snapshot so newly-connected clients have
            # an authoritative header without waiting for the next 5s poll.
            info = _current_model_info(cfg)
            if info is not None:
                await ws.send_text(json.dumps({"type": "model", "info": asdict(info)}))

            # send an initial ctx snapshot so the substrate ctx·budget bar
            # has the real context size from config from the first paint.
            await ws.send_text(json.dumps({
                "type": "ctx",
                "used": 0,
                "budget": cfg.context_size,
            }))
            # send the current agent boot status so a client connecting
            # AFTER boot finished still knows the agent is ready (otherwise
            # it would wait forever for an event that already passed). We
            # gate `ready` on the warmup latch rather than /health for the
            # same reason agent_status does — /health responds before
            # load_tensors is finished.
            from ..agent_core.agent_runner import RUNNER
            RUNNER.start()
            agent = getattr(RUNNER, "_agent", None)
            built = agent is not None
            warmed = RUNNER.is_warmed_up()
            # 4ª condición del gate: el router semántico listo (o deshabilitado/
            # degradado-tolerado). Igual que el PULL de /agent/status — un cliente
            # que abre el WS tarde debe ver ready solo si el router también está.
            router_ready = RUNNER.is_router_ready()
            healthy = False
            if built:
                try:
                    healthy = bool(agent.client.health(timeout_s=0.4))
                except Exception:
                    healthy = False
            await ws.send_text(json.dumps({
                "type": "agent",
                "built": built,
                "healthy": healthy,
                "ready": built and warmed and healthy and router_ready,
            }))

            async def reader() -> None:
                # detect client disconnect — receive_text raises WebSocketDisconnect
                while True:
                    await ws.receive_text()

            async def writer() -> None:
                while True:
                    # block in a thread to avoid spinning when the bus is quiet.
                    # 1s timeout gives us a chance to also emit a heartbeat.
                    event = await loop.run_in_executor(None, _drain_one, sub, 1.0)
                    if event is None:
                        # heartbeat keeps proxies from dropping idle sockets
                        await ws.send_text(json.dumps({"type": "heartbeat"}))
                        continue
                    await ws.send_text(json.dumps(event))

            done, pending = await asyncio.wait(
                {asyncio.create_task(reader()), asyncio.create_task(writer())},
                return_when=asyncio.FIRST_EXCEPTION,
            )
            for task in pending:
                task.cancel()
            for task in done:
                exc = task.exception()
                if exc is not None and not isinstance(exc, WebSocketDisconnect):
                    logger.warning("ws /events task error: %s", exc)
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.warning("ws /events outer error: %s", exc)
        finally:
            BUS.unsubscribe(sub)

    # Cache-Control middleware: the index.html sits behind a fixed URL but
    # references hash-named JS/CSS bundles, so we MUST keep the browser from
    # caching the html — otherwise WebView2 hangs on a stale bundle pointer
    # across rebuilds. The hashed assets themselves stay cacheable since
    # their name changes on every build.
    @app.middleware("http")
    async def _no_cache_index(request: Any, call_next: Any) -> Any:
        response = await call_next(request)
        try:
            ctype = response.headers.get("content-type", "")
            if "text/html" in ctype:
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
        except Exception:
            pass
        return response

    # static UI mount — must be last so the API routes above win
    if UI_DIST.is_dir() and (UI_DIST / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(UI_DIST), html=True), name="ui")
    else:
        @app.get("/")
        def fallback_root() -> Any:
            return JSONResponse(
                {
                    "status": "no_ui",
                    "hint": (
                        f"UI bundle not found at {UI_DIST}. "
                        "Run `pnpm --dir gemma4_agent/ui_field build` and retry."
                    ),
                },
                status_code=503,
            )

    return app


def main() -> int:
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    cfg = AgentConfig.from_env()
    app = create_app(cfg)
    host = os.environ.get("GEMMA4_UI_HOST", "127.0.0.1")
    port = int(os.environ.get("GEMMA4_UI_PORT", "8765"))
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
