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
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

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
    ]

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
