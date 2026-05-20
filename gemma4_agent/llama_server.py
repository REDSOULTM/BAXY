"""Fase V — LlamaServerManager.

Gestiona el ciclo de vida de llama-server segun el perfil activo. Antes de
Fase V, launcher.py disparaba un subprocess.Popen y olvidaba el handle; ahora
lo guardamos para poder hacer stop() y restart() limpios.

Reglas:
- Si detectamos un server externo escuchando en el puerto (socket.connect_ex),
  NO lo matamos. Solo loggeamos warning. El caller debe respetarlo y mostrar
  el aviso en la UI.
- STANDBY profile no arranca el server.
- start() es idempotente: si ya hay un proceso vivo gestionado por nosotros,
  devuelve True sin re-arrancar.
- restart() = stop() + start(). Es lo que llamamos al cambiar de perfil
  cuando server_running pasa de False a True o cuando cambian flags que
  requieren restart del server (context_size, model_path, mmproj on/off).

El comando se construye desde el AgentConfig (paths del usuario) + Profile
(context_size, vision_enabled, model_path override).
"""
from __future__ import annotations

import json
import logging
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

from .config import AgentConfig, PACKAGE_ROOT, PROJECT_ROOT
from .profiles import Profile


logger = logging.getLogger(__name__)


def get_external_server_context(host: str = "127.0.0.1", port: int = 8080, timeout: float = 2.0) -> int | None:
    """Pregunta a un llama-server cualquier (interno o externo) por su context size.

    GET /props devuelve algo asi:
        {
          "default_generation_settings": {
            "n_ctx": 16384,
            "n_ctx_per_seq": 16384,
            ...
          },
          ...
        }

    Algunas versiones tienen `n_ctx`, otras `n_ctx_per_seq`. Usamos el primero
    que sea int > 0. Si nada parsea, devolvemos None (server puede estar
    bootstrapping, version distinta, etc.).
    """
    url = f"http://{host}:{port}/props"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return None
    settings = data.get("default_generation_settings")
    if not isinstance(settings, dict):
        return None
    for key in ("n_ctx", "n_ctx_per_seq"):
        val = settings.get(key)
        if isinstance(val, int) and val > 0:
            return val
    return None


def port_in_use(host: str = "127.0.0.1", port: int = 8080, timeout: float = 0.3) -> bool:
    """True si hay algo escuchando en host:port.

    Usado para detectar server externo iniciado por el usuario antes de
    pisarlo. socket.connect_ex devuelve 0 si conecta.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        return sock.connect_ex((host, port)) == 0
    except OSError:
        return False
    finally:
        try:
            sock.close()
        except OSError:
            pass


def _server_port(config: "AgentConfig | None" = None) -> int:
    """Best-effort: port llama-server listens on (default 8080)."""
    try:
        url = (config or AgentConfig.from_env()).server_url  # e.g. http://127.0.0.1:8080
        return int(url.rsplit(":", 1)[1].split("/")[0])
    except Exception:
        return 8080


def _kill_server_on_port(config: "AgentConfig | None" = None) -> bool:
    """Kill whatever process listens on the llama-server port (Windows).

    Used by a USER-DRIVEN profile switch to take over the port even when the
    running server was started outside this manager (external) — the user
    explicitly asked to load a different model. Best-effort: returns True if a
    PID was found and a kill was issued. Cross-platform via psutil if present,
    else falls back to netstat+taskkill on Windows.
    """
    port = _server_port(config)
    if not port_in_use(port=port):
        return False
    pids: set[int] = set()
    try:
        import psutil  # type: ignore
        for c in psutil.net_connections(kind="inet"):
            if c.laddr and c.laddr.port == port and c.status == psutil.CONN_LISTEN and c.pid:
                pids.add(int(c.pid))
    except Exception:
        # Fallback: parse `netstat -ano` for the listening PID on this port.
        try:
            out = subprocess.run(
                ["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, timeout=5,
            ).stdout
            for line in out.splitlines():
                if f":{port} " in line and "LISTENING" in line.upper():
                    parts = line.split()
                    if parts and parts[-1].isdigit():
                        pids.add(int(parts[-1]))
        except Exception:
            return False
    killed = False
    for pid in pids:
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                           capture_output=True, timeout=5)
            killed = True
            logger.info("killed server on port %d (pid %d) for profile switch", port, pid)
        except Exception as exc:
            logger.warning("failed to kill pid %d on port %d: %s", pid, port, exc)
    return killed


# Process-wide shared manager. The launcher (start_server) and the FastAPI
# server (/profile) run in the SAME process (uvicorn on a daemon thread), so a
# module singleton lets the profile endpoint restart the very server the
# launcher started — without that, the endpoint built a fresh manager with no
# handle to the running process and the switch silently did nothing.
_SHARED_MANAGER: "LlamaServerManager | None" = None


def get_shared_manager(config: "AgentConfig | None" = None) -> "LlamaServerManager":
    global _SHARED_MANAGER
    if _SHARED_MANAGER is None:
        _SHARED_MANAGER = LlamaServerManager(config=config)
    return _SHARED_MANAGER


# Build minimo requerido para soporte correcto de tool-calling en Gemma 4.
# Esta constante refleja el roadmap del informe de auditoria (item I1 #1):
# llama.cpp b9090+ contiene los PRs #21418 (parser dedicado Gemma 4),
# #21326 y #21343 (tokenizer + token spam fixes). Builds anteriores producen
# tool_calls con tokens corruptos o argumentos serializados como string.
#
# CUDA 13.2 esta bloqueado por advertencia de Unsloth (2026-04-11): produce
# poor outputs en cualquier GGUF de Gemma 4. Recomendar CUDA 13.1 o 12.x.
LLAMA_CPP_BUILD_MIN = "b9090"
CUDA_RUNTIME_BLOCKED = "13.2"


_BUILD_CHECK_DONE: bool = False


def check_llama_build(exe_path: Path) -> dict[str, Any]:
    """Lee version + build de llama-server y emite warnings si corresponde.

    Llamada idempotente: se ejecuta una sola vez por proceso (controlada
    por _BUILD_CHECK_DONE). Si llama-server no esta disponible, retorna
    un dict con `available=False` sin levantar excepciones (el caller
    decide como manejar el missing exe).

    Returns dict con keys: available, build, cuda, raw, warnings.
    """
    global _BUILD_CHECK_DONE
    info: dict[str, Any] = {
        "available": False,
        "build": None,
        "cuda": None,
        "raw": None,
        "warnings": [],
    }
    if _BUILD_CHECK_DONE:
        return info
    _BUILD_CHECK_DONE = True

    if not exe_path.is_file():
        info["warnings"].append(f"llama-server exe not found: {exe_path}")
        return info

    try:
        proc = subprocess.run(
            [str(exe_path), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        info["warnings"].append(f"llama-server --version failed: {exc}")
        return info

    raw = (proc.stdout or "") + (proc.stderr or "")
    info["available"] = True
    info["raw"] = raw[:500]

    # Detectar build: formato tipico "version: <N> (<sha>)" o "build = <N>"
    # llama-server suele imprimir "version: 6593 (abc1234)" en stderr.
    build_match = re.search(r"\b(?:version|build)\s*[:=]?\s*(\d{3,5})\b", raw, re.IGNORECASE)
    if build_match:
        info["build"] = f"b{build_match.group(1)}"
        try:
            current_n = int(build_match.group(1))
            min_n = int(LLAMA_CPP_BUILD_MIN.lstrip("bB"))
            if current_n < min_n:
                msg = (
                    f"llama-server build {info['build']} is older than {LLAMA_CPP_BUILD_MIN}. "
                    "Gemma 4 tool calling requires PRs #21418, #21326, #21343 (merged in b9090+). "
                    "Older builds produce corrupted tool_calls."
                )
                info["warnings"].append(msg)
                logger.warning(msg)
        except ValueError:
            pass

    # Detectar CUDA runtime: formato "cuda runtime: 13.1" o "CUDA: 13.2"
    cuda_match = re.search(r"cuda(?:\s+runtime)?\s*[:=]?\s*(\d+\.\d+)", raw, re.IGNORECASE)
    if cuda_match:
        info["cuda"] = cuda_match.group(1)
        if info["cuda"] == CUDA_RUNTIME_BLOCKED:
            msg = (
                f"CUDA runtime {info['cuda']} detected. Unsloth (2026-04-11) "
                "explicitly warns: 'Do NOT use CUDA 13.2 runtime for any GGUF "
                "as it will cause poor outputs.' Downgrade to CUDA 13.1 or 12.x."
            )
            info["warnings"].append(msg)
            logger.warning("=" * 70)
            logger.warning(msg)
            logger.warning("=" * 70)

    if info["build"] is None and info["cuda"] is None:
        info["warnings"].append(
            "Could not parse build/CUDA from llama-server --version output. "
            "Tool calling may be unreliable on Gemma 4. Update to b9090+."
        )

    return info


def llama_command(config: AgentConfig, profile: Profile) -> list[str]:
    """Construye el comando de llama-server respetando el perfil.

    - Si profile.vision_enabled=False O GEMMA4_MMPROJ_PATH="" -> no se pasa --mmproj.
    - Si profile.model_path apunta a un archivo existente -> override del modelo.
    - context_size siempre viene del perfil.
    """
    # Modelo: priorizar override del perfil si el archivo existe
    model_path: Path = config.model_path
    if profile.model_path:
        candidate = Path(profile.model_path).expanduser()
        if candidate.is_file():
            model_path = candidate
        else:
            logger.warning(
                "profile %s declares model_path=%s but file does not exist; "
                "falling back to config.model_path=%s",
                profile.name,
                profile.model_path,
                config.model_path,
            )

    cmd: list[str] = [
        str(config.llama_server_exe.resolve()),
        "-m",
        str(model_path.resolve()),
        "--jinja",
        # Sprint 12 — hardening: forzar bind a loopback. El brief del
        # proyecto es "100% local"; jamas debe escuchar en 0.0.0.0.
        "--host",
        "127.0.0.1",
        "--port",
        "8080",
        # Sprint 12 — deshabilitar el webui interno de llama-server.
        # El cliente tiene UI propia (PyQt6 + React UI Field); el webui
        # interno es superficie de ataque innecesaria.
        "--no-webui",
        "-ngl",
        "99",
        "-c",
        str(int(profile.context_size)),
        "--parallel",
        "1",
        "--ctx-checkpoints",
        "1",
        "--flash-attn",
        "on",
        # --keep -1: preserva todo el system prompt entre turnos. Origen:
        # defensa contra issue #21468 (cache-reuse roto en Gemma 4 por
        # shared-KV). El PR #22288 ("server: fix swa-full logic") fue
        # MERGED 2026-04-24 y aparece desde la release b9084. Nuestro
        # LLAMA_CPP_BUILD_MIN=b9090 ya lo incluye, asi que --cache-reuse
        # esta operativo en Gemma 4. --keep -1 queda como complemento que
        # ayuda a la prefix cache aun cuando cache-reuse esta activo.
        # Item I1 #3 + Bloque D1 + Polish P1 del optimization_roadmap.md.
        "--keep",
        "-1",
        # --cache-reuse 256: ahora que PR #22288 cerro #21468 en upstream,
        # el server puede reutilizar prefijos coincidentes del KV cache
        # entre turnos. Esto recupera el ~93% de TTFT que el bug costaba
        # en el primer turno con system prompt grande (medido por el
        # reporter de #21468 con ~46K tokens). Valor 256: tamano minimo
        # de match en tokens (default del flag); subir reduce overhead
        # del scan pero baja chance de hit.
        # Polish P1 del optimization_roadmap.md.
        "--cache-reuse",
        "256",
    ]

    # Sprint 12 — API key opt-in via env var. Si GEMMA4_LLAMA_API_KEY esta
    # seteado, el server exige Authorization: Bearer <key> en cada request.
    # No lo forzamos por default para no romper el flujo "el agente Python
    # habla con llama-server en localhost"; pero si el usuario expone el
    # puerto a otra red local (errores de config), esto provee defense in
    # depth. El cliente llm_client.py debe leer el mismo env var y mandar
    # el header — ver test que verifica round-trip.
    api_key_env = (os.environ.get("GEMMA4_LLAMA_API_KEY") or "").strip()
    if api_key_env:
        cmd.extend(["--api-key", api_key_env])

    # VRAM-tight perfiles (<=6 GB: vram3/vram4/vram6): --no-mmap para evitar
    # double-buffer entre RAM mapeada y VRAM (critico con budget apretado).
    _VRAM_TIGHT = {"vram3", "vram4", "vram6"}
    if profile.name in _VRAM_TIGHT:
        cmd.append("--no-mmap")

    # KV cache quantization (opt-in via GEMMA4_LLAMA_KV_TYPE). Default: F16.
    # El informe de optimizacion externa (Bloque B1, item I1 #5, TL;DR-6)
    # advierte contra KV quant en Gemma 4 sin medir:
    #   localbench (2026-04): KL 0.377 con q8_0 KV en 26B-A4B
    #                         (vs Qwen <0.04), KL 0.108 en 31B Q8_0.
    # Si el usuario aun asi lo activa por env var, lo respetamos pero con
    # WARNING grande. Solo aceptamos valores conocidos por llama.cpp.
    _ALLOWED_KV_TYPES = {"f16", "f32", "bf16", "q8_0", "q5_1", "q5_0", "q4_1", "q4_0"}
    kv_type_env = (os.environ.get("GEMMA4_LLAMA_KV_TYPE") or "").strip().lower()
    if kv_type_env:
        if kv_type_env not in _ALLOWED_KV_TYPES:
            logger.warning(
                "GEMMA4_LLAMA_KV_TYPE=%r is not a recognized llama.cpp KV "
                "type; ignoring. Allowed: %s.",
                kv_type_env, sorted(_ALLOWED_KV_TYPES),
            )
        else:
            if kv_type_env not in {"f16", "f32", "bf16"}:
                logger.warning("=" * 70)
                logger.warning(
                    "KV cache quantization enabled by env var: %s. "
                    "localbench (2026-04) measured KL 0.377 for Gemma 4 "
                    "26B-A4B with q8_0 KV (vs Qwen <0.04). Quality may "
                    "degrade on long-context / tool-call tasks. Recommended: "
                    "leave unset (F16 default) until benchmarked on Carter 540.",
                    kv_type_env,
                )
                logger.warning("=" * 70)
            cmd.extend([
                "--cache-type-k", kv_type_env,
                "--cache-type-v", kv_type_env,
            ])

    # Speculative decoding opt-in via env var (item 2.2 del roadmap).
    #
    # Bloque D3 del informe externo: speculative decoding E2B-draft -> E4B/
    # 26B-A4B-target funciona con --spec-draft-model en llama.cpp upstream.
    # Acceptance rate estimado 40-60% en Carter (sin medir). VRAM: solo viable
    # en perfil `performance` con VRAM >=12 GB; E2B-Q4 ~1.85 GB + E4B-Q4 ~5.6 GB
    # = 7.45 GB no entra en 6 GB.
    #
    # ADVERTENCIA: bench externo hackmd.io/ODXuOQNzSiyUITz7g9mtBw mide que en
    # RTX 3090 con Qwen3.6-35B-A3B speculative resulta MAS LENTO que baseline
    # (139.9 -> 65.0 tok/s). Lo activamos solo si el usuario lo opta-in y
    # avisamos del riesgo. Si acceptance < 50% en la maquina, dejar off.
    spec_draft_env = (os.environ.get("GEMMA4_SPEC_DRAFT_MODEL") or "").strip()
    if spec_draft_env:
        if profile.name != "vram16":
            logger.warning(
                "GEMMA4_SPEC_DRAFT_MODEL set but profile=%s; speculative "
                "decoding requires the 'vram16' profile (VRAM budget). "
                "Ignoring.",
                profile.name,
            )
        else:
            draft_path = Path(spec_draft_env).expanduser()
            if not draft_path.is_file():
                logger.warning(
                    "GEMMA4_SPEC_DRAFT_MODEL=%s does not exist; ignoring "
                    "speculative decoding.",
                    spec_draft_env,
                )
            else:
                logger.warning("=" * 70)
                logger.warning(
                    "Speculative decoding ENABLED: draft=%s. Bench externo "
                    "hackmd #ODXuOQNzSiyUITz7g9mtBw measured speedup as "
                    "NEGATIVE on consumer Ampere (RTX 30xx) with some quants. "
                    "Run llama-bench --model-draft to confirm tok/s gain "
                    "before relying on this in production.",
                    draft_path.name,
                )
                logger.warning("=" * 70)
                cmd.extend(["--model-draft", str(draft_path.resolve())])
                # Flags adicionales con defaults conservadores. Si el usuario
                # los sobreescribe via env var, respetamos.
                n_max = (os.environ.get("GEMMA4_SPEC_DRAFT_N_MAX") or "16").strip()
                n_min = (os.environ.get("GEMMA4_SPEC_DRAFT_N_MIN") or "0").strip()
                draft_ngl = (os.environ.get("GEMMA4_SPEC_DRAFT_NGL") or "99").strip()
                try:
                    int(n_max); int(n_min); int(draft_ngl)
                    cmd.extend([
                        "--draft-max", n_max,
                        "--draft-min", n_min,
                        "--gpu-layers-draft", draft_ngl,
                    ])
                except ValueError:
                    logger.warning("invalid spec-draft numeric env var; ignoring extra flags")

    # Vision: solo agregar --mmproj si el perfil lo permite y hay path real
    if profile.vision_enabled:
        mmproj_env = os.environ.get("GEMMA4_MMPROJ_PATH")
        if mmproj_env == "":
            # Explicitly disabled (rare with vision_enabled=True; respect it)
            logger.info("GEMMA4_MMPROJ_PATH is empty; skipping --mmproj")
        else:
            mmproj_path = Path(mmproj_env).expanduser() if mmproj_env else config.mmproj_path
            if mmproj_path.is_file():
                cmd.extend(["--mmproj", str(mmproj_path.resolve())])
                # --no-mmproj-offload cuando VRAM efectiva es tight (perfiles
                # con --no-mmap suelen ser los de 6 GB o menos). Mitiga la
                # interaccion con issue #19980 (--fit no contabiliza VRAM del
                # mmproj). Item I1 #8 / Bloque E1 del informe.
                if profile.name in _VRAM_TIGHT:
                    cmd.append("--no-mmproj-offload")
            else:
                logger.warning(
                    "mmproj path %s does not exist; loading server without vision",
                    mmproj_path,
                )

    return cmd


class LlamaServerManager:
    """Maneja un unico proceso llama-server vivo.

    Si el usuario tiene su propio server corriendo en :8080, este manager
    lo respeta: start() detecta y devuelve "external", stop() no toca, y
    current_profile() devuelve None.
    """

    def __init__(self, config: AgentConfig | None = None, log_dir: Path | None = None) -> None:
        self._config = config or AgentConfig.from_env()
        self._proc: Optional[subprocess.Popen[bytes]] = None
        self._current_profile: Optional[Profile] = None
        self._external_detected: bool = False
        self._external_context_mismatch_msg: Optional[str] = None
        self._log_dir = log_dir or (PACKAGE_ROOT / "logs")

    def is_running(self) -> bool:
        """True si tenemos un proceso vivo gestionado por este manager.

        NO incluye servers externos. Para eso usar `has_any_server()`.
        """
        if self._proc is None:
            return False
        return self._proc.poll() is None

    def detect_crash_signature(self, max_tail_lines: int = 80) -> dict[str, str | None]:
        """Inspecciona el err log buscando una causa de crash conocida.

        Devuelve dict con keys:
          - "kind": 'cuda_illegal_memory' | 'oom' | 'segfault' | 'context_overflow' | None
          - "summary": una linea descriptiva del crash o None
          - "log_excerpt": ultimas N lineas relevantes del log (para mostrar al user)

        Util para diagnostico cuando _wait_for_health falla o el cliente recibe
        ConnectionReset persistente. NO modifica estado del manager — solo lee.
        """
        empty = {"kind": None, "summary": None, "log_excerpt": None}
        log_path = self._config.captures_dir.parent / "logs" / "llama-server.err.log"
        if not log_path.exists():
            return empty
        try:
            # Read last ~20KB (suficiente para los ultimos ~200 lines).
            with log_path.open("rb") as fh:
                fh.seek(0, 2)
                size = fh.tell()
                fh.seek(max(0, size - 20480), 0)
                tail_bytes = fh.read()
            text = tail_bytes.decode("utf-8", errors="replace")
        except OSError:
            return empty
        lines = text.split("\n")
        tail = lines[-max_tail_lines:]
        joined = "\n".join(tail).lower()
        kind: str | None = None
        summary: str | None = None
        if "cuda error" in joined and "illegal memory" in joined:
            kind = "cuda_illegal_memory"
            summary = (
                "llama-server crashed with CUDA illegal memory access. "
                "This is a GPU/driver-level issue (often after long sessions or "
                "specific prompt patterns). Restart usually recovers."
            )
        elif "out of memory" in joined or "cudamalloc" in joined.replace(" ", ""):
            kind = "oom"
            summary = "llama-server out of memory; reduce context_size or use a smaller quant."
        elif "segmentation fault" in joined or "access violation" in joined:
            kind = "segfault"
            summary = "llama-server segfaulted; likely build/binary bug, try a newer llama.cpp release."
        elif "exceed_context_size_error" in joined or "exceeds the available context size" in joined:
            kind = "context_overflow"
            summary = "Request exceeded context_size; agent should compact history or use larger context profile."
        if kind is None:
            return empty
        # Excerpt: keep last ~20 non-empty lines for the UI.
        non_empty = [l for l in tail if l.strip()][-20:]
        return {
            "kind": kind,
            "summary": summary,
            "log_excerpt": "\n".join(non_empty),
        }

    def has_any_server(self) -> bool:
        """True si hay un server escuchando en :8080, sea nuestro o externo."""
        return self.is_running() or port_in_use()

    def is_external_server(self) -> bool:
        """True si el ultimo start() encontro un server externo y no lo toco."""
        return self._external_detected

    def external_context_mismatch_msg(self) -> str | None:
        """Mensaje de warning si el server externo declara un context menor al
        que pide el perfil. None si no aplica (no hay externo, o context OK)."""
        return self._external_context_mismatch_msg

    def current_profile(self) -> Profile | None:
        """Perfil con el que arrancamos el server actual.

        Devuelve None si:
        - No hay server gestionado por nosotros.
        - Hay server externo (no conocemos su perfil).
        """
        if self._external_detected or not self.is_running():
            return None
        return self._current_profile

    def start(self, profile: Profile, wait_health: bool = True, timeout_s: int = 90) -> str:
        """Arranca llama-server con flags del perfil.

        Returns:
            "started": proceso nuevo gestionado por nosotros, healthy.
            "already_running": ya teniamos un proceso vivo, no se reinicia.
            "external": detectado server externo en :8080, no se toca.
            "skipped_standby": profile.server_running False, no se arranca.
            "timeout": arranco pero no respondio /health a tiempo.
            "missing_files": faltan llama-server.exe o modelo.
        """
        if not profile.server_running:
            logger.info("profile %s has server_running=False; not starting", profile.name)
            return "skipped_standby"

        if self.is_running() and self._current_profile is not None and \
                self._current_profile.name == profile.name:
            return "already_running"

        # External-server detection: ANTES de matar nada
        if not self.is_running() and port_in_use():
            logger.warning(
                "External llama-server detected on :8080. NOT killing or "
                "reconfiguring it. Profile flags will NOT be applied to it. "
                "Stop the external server manually if you want Gemma4 to manage it."
            )
            self._external_detected = True
            self._current_profile = None
            # Check context mismatch (silent if the external server returns
            # >= than we ask, since the server simply ignores unused capacity).
            self._external_context_mismatch_msg = None
            external_ctx = get_external_server_context()
            if external_ctx is not None and external_ctx < int(profile.context_size):
                msg = (
                    f"external server has -c={external_ctx} but profile "
                    f"{profile.name} asks for {int(profile.context_size)}; "
                    "long prompts will be truncated by the server"
                )
                logger.warning(msg)
                self._external_context_mismatch_msg = msg
            return "external"

        # Verificar archivos
        cmd_args = llama_command(self._config, profile)
        exe = Path(cmd_args[0])
        model = Path(cmd_args[2])
        if not exe.exists() or not model.exists():
            logger.error(
                "Cannot start llama-server: missing exe=%s or model=%s",
                exe, model,
            )
            return "missing_files"

        # Chequeo de build una vez por proceso. Solo se ejecuta cuando vamos a
        # arrancar nuestro server (no en path "external" ni "missing_files",
        # para no interferir con tests que mockean subprocess y para no
        # ejecutar el binario si no esta presente).
        check_llama_build(exe)

        # Item 1.9 / Bloque A3: avisar si el modelo es MXFP4 (experimental).
        try:
            from .model_info import is_experimental_quant
            flagged, pattern = is_experimental_quant(str(model))
            if flagged:
                logger.warning(
                    "Loading EXPERIMENTAL quantization (%s) for %s. Unsloth "
                    "retired MXFP4 from base quants (Q2_K_XL, Q3_K_XL, "
                    "Q4_K_XL) due to degradation on critical tensors "
                    "(attn_gate, attn_q, ssm_alpha/beta). Quality may be "
                    "lower than UD-Q4_K_XL of same size.",
                    pattern, model.name,
                )
        except Exception as exc:
            logger.debug("experimental quant check failed: %s", exc)

        # Tear down si habia uno con perfil distinto
        if self.is_running():
            self.stop()

        # Arrancar
        self._log_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = self._log_dir / "llama-server.out.log"
        stderr_path = self._log_dir / "llama-server.err.log"
        stdout_f = stdout_path.open("a", encoding="utf-8", errors="replace")
        stderr_f = stderr_path.open("a", encoding="utf-8", errors="replace")
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

        try:
            self._proc = subprocess.Popen(
                cmd_args,
                cwd=str(PROJECT_ROOT),
                stdout=stdout_f,
                stderr=stderr_f,
                creationflags=creationflags,
            )
        except OSError as exc:
            logger.error("Failed to spawn llama-server: %s", exc)
            self._proc = None
            return "missing_files"

        self._current_profile = profile
        self._external_detected = False
        self._external_context_mismatch_msg = None
        logger.info("llama-server started for profile %s (pid=%s)", profile.name, self._proc.pid)

        if not wait_health:
            return "started"

        # Esperar /health=200 con tiempo limite
        if self._wait_for_health(timeout_s=timeout_s):
            return "started"
        logger.error("llama-server did not become healthy within %ds", timeout_s)
        return "timeout"

    def stop(self, timeout_s: float = 5.0) -> bool:
        """Mata el proceso gestionado por nosotros (si existe).

        NO toca servers externos. Devuelve True si efectivamente se mato algo.
        """
        if self._external_detected:
            logger.info("stop(): external server detected, not touching it")
            return False
        if self._proc is None:
            return False
        if self._proc.poll() is not None:
            self._proc = None
            self._current_profile = None
            return False
        try:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=2.0)
        except OSError as exc:
            logger.warning("stop() error: %s", exc)
        finally:
            self._proc = None
            self._current_profile = None
        return True

    def recycle_for_vision_leak(self) -> bool:
        """Recicla el server para mitigar el leak de mmproj (issue #21690).

        Solo aplica si:
          - Tenemos un proceso vivo gestionado por nosotros.
          - El perfil activo tiene vision_enabled=True.

        Devuelve True si efectivamente se reciclo. Publica al BUS de eventos
        un payload {kind:"boot_stage", stage:"vision_relaunch"} antes y
        despues del swap. Item 1.7 / Bloque E1 del roadmap.

        Lectura: counter de imagenes se mantiene en multimodal.py; este
        metodo es solo el "como" del relanch, decidido y disparado por el
        orchestrator (NO por agent.py).
        """
        if self._external_detected:
            logger.info("recycle_for_vision_leak(): external server, skipping")
            return False
        profile = self._current_profile
        if profile is None or not self.is_running():
            logger.info("recycle_for_vision_leak(): no managed server running")
            return False
        if not getattr(profile, "vision_enabled", False):
            logger.debug("recycle_for_vision_leak(): vision disabled in profile %s", profile.name)
            return False
        # Publicar al bus (best-effort; si events_bus no esta importable
        # estamos en un entorno donde el orchestrator no lo necesita).
        try:
            from .events_bus import BUS
            BUS.publish({
                "kind": "boot_stage",
                "stage": "vision_relaunch",
                "phase": "starting",
                "profile": profile.name,
            })
        except Exception:
            pass
        logger.info("recycling llama-server (mmproj leak mitigation #21690)")
        result = self.restart(profile)
        try:
            from .events_bus import BUS
            BUS.publish({
                "kind": "boot_stage",
                "stage": "vision_relaunch",
                "phase": "completed",
                "profile": profile.name,
                "result": result,
            })
        except Exception:
            pass
        # Reset del counter de imagenes para empezar el siguiente ciclo limpio.
        try:
            from .multimodal import reset_image_counter
            reset_image_counter()
        except Exception:
            pass
        return result == "started"

    def force_restart_for_profile(self, profile: Profile,
                                  wait_health: bool = True,
                                  timeout_s: int = 90) -> str:
        """Restart for a USER-DRIVEN profile switch — authoritative.

        Unlike start()/restart(), this WILL take over the port even if the
        server there is "external": when the user picks a new VRAM profile they
        are explicitly asking to load that profile's model, so a server running
        a different model on our port must be replaced. We:
          1. stop our managed process if we have one, else kill whatever
             listens on the config port (by PID),
          2. clear the external flag,
          3. start() fresh with the new profile.

        For standby (server_running=False) we just stop and report 'stopped'.
        Returns the start() result string, or 'stopped' for standby.
        """
        # Always tear down the current server first.
        if self.is_running():
            self.stop()
        else:
            _kill_server_on_port(self._config)
        self._proc = None
        self._current_profile = None
        self._external_detected = False
        self._external_context_mismatch_msg = None

        if not profile.server_running:
            # standby: leave it down.
            return "stopped"
        # Give the OS a moment to release the port + VRAM before re-binding.
        for _ in range(20):
            if not port_in_use():
                break
            time.sleep(0.25)
        return self.start(profile, wait_health=wait_health, timeout_s=timeout_s)

    def restart(self, profile: Profile, **start_kwargs: object) -> str:
        """stop() + start(profile)."""
        self.stop()
        # start_kwargs solo pasa wait_health/timeout_s; tipamos laxo para no
        # multiplicar overloads, pero esos son los unicos validos.
        wait_health = bool(start_kwargs.get("wait_health", True))
        timeout_s = int(start_kwargs.get("timeout_s", 90))  # type: ignore[arg-type]
        return self.start(profile, wait_health=wait_health, timeout_s=timeout_s)

    def _wait_for_health(self, timeout_s: int = 90) -> bool:
        """Polea /health hasta que responda 200 o se agote el tiempo."""
        from .llm_client import LLMClient
        client = LLMClient(self._config)
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            # Si el proceso murio antes de tiempo, cortar
            if self._proc is not None and self._proc.poll() is not None:
                logger.error("llama-server process exited before becoming healthy")
                return False
            if client.health(timeout_s=1.0):
                return True
            time.sleep(1.0)
        return False
