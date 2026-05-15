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
        "--port",
        "8080",
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
        # --keep -1: defensa mientras issue #21468 (cache-reuse roto en
        # Gemma 4 por arquitectura shared-KV) este abierto. Preserva todo
        # el system prompt entre turnos, evita que context shifts tiren la
        # prefix cache. PR #22288 candidato a merge; una vez merged, este
        # flag deja de ser critico pero no daña tenerlo.
        # Item I1 #3 + Bloque D1 del informe de optimizacion externa.
        "--keep",
        "-1",
    ]

    # VRAM-tight perfiles (balanced, light): --no-mmap para evitar
    # double-buffer entre RAM mapeada y VRAM (critico con budget apretado).
    if profile.name in {"balanced", "light"}:
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
                if profile.name in {"balanced", "light"}:
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
