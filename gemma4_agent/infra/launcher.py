"""Local launcher for the Gemma 4 Windows agent.

This is intentionally small and dependency-free. It borrows the useful shape of
Jarvis' launcher (one command for setup/status/start), but keeps this project
fully local and focused on the text agent.
"""

from __future__ import annotations

import argparse
import atexit
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from .. import __version__
from .config import AgentConfig, PACKAGE_ROOT, PROJECT_ROOT
from .llama_server import LlamaServerManager, port_in_use
from .llm_client import LLMClient
from .profiles import apply_profile_to_env, get_active_profile
from ..tools_pkg.tools import COMPOUND_TOOL_SCHEMAS


def _shutdown_voice_recorder() -> None:
    """Voice recorder removed in the clean-slate rewrite.
    Stub kept so atexit registration doesn't error; replaced when
    the new voice pipeline lands."""
    pass


atexit.register(_shutdown_voice_recorder)


PALETTE = {
    "title": "\033[36;1m",
    "ok": "\033[32m",
    "warn": "\033[33m",
    "error": "\033[31;1m",
    "dim": "\033[90m",
    "reset": "\033[0m",
}

BANNER = r"""
   ____                         _  _       _                    _
  / ___| ___ _ __ ___  _ __ ___| || |     / \   __ _  ___ _ __ | |_
 | |  _ / _ \ '_ ` _ \| '_ ` _ \ || |_   / _ \ / _` |/ _ \ '_ \| __|
 | |_| |  __/ | | | | | | | | | |__   _| / ___ \ (_| |  __/ | | | |_
  \____|\___|_| |_| |_|_| |_| |_|  |_|  /_/   \_\__, |\___|_| |_|\__|
                                                |___/
"""


def _pick_bindable_port(host: str, preferred: int) -> int:
    """Return a port we can actually bind on `host`. The default UI port (8765)
    sometimes falls inside a Windows EXCLUDED port range (Hyper-V / WSL2 / Docker
    reserve dynamic ranges, e.g. 8728-8827 covers 8765) -> uvicorn fails with
    'WinError 13: socket access not permitted' and the UI never comes up.
    Try the preferred port first; if it's not bindable, walk a few candidates
    and finally let the OS pick a free one. This makes `launcher ui` robust to
    the system reserving the default port."""
    import socket

    def _can_bind(p: int) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, p))
            s.close()
            return True
        except OSError:
            return False

    if _can_bind(preferred):
        return preferred
    # try a handful of nearby/clear ports outside common reserved ranges
    for cand in (8765, 8770, 8123, 7860, 9123, 5111, 8099, 8311):
        if cand != preferred and _can_bind(cand):
            print(color("warn", f"puerto {preferred} bloqueado por el sistema "
                                 f"(rango reservado); usando {cand}"))
            return cand
    # last resort: let the OS assign a free ephemeral port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((host, 0))
    free = s.getsockname()[1]
    s.close()
    print(color("warn", f"puerto {preferred} bloqueado; usando libre {free}"))
    return free


def enable_ansi() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


def color(name: str, text: str) -> str:
    return f"{PALETTE[name]}{text}{PALETTE['reset']}"


def print_banner() -> None:
    print(color("title", BANNER.rstrip()))
    print(color("dim", f"  Gemma4 Agent v{__version__} | local Windows launcher"))
    print()


def config_with_args(args: argparse.Namespace) -> AgentConfig:
    config = AgentConfig.from_env()
    updates = dict(config.__dict__)
    if getattr(args, "server", None):
        updates["server_url"] = args.server
    if getattr(args, "mode", None):
        updates["agent_mode"] = args.mode
    return AgentConfig(**updates)


def file_line(label: str, path: Path) -> str:
    exists = path.exists()
    status = color("ok", "OK") if exists else color("error", "MISSING")
    return f"{label:<18} {status:<20} {path}"


def health_status(config: AgentConfig, timeout_s: float = 2.0) -> bool:
    return LLMClient(config).health(timeout_s=timeout_s)


def _encoder_health() -> tuple[bool, str]:
    """¿Carga el encoder de embeddings del router? Falla -> routing degradado.

    La causa típica es numpy fuera de pin (2.x rompe pandas -> arrastra
    sentence-transformers vía sklearn). Devuelve (ok, detalle) para el status.
    """
    try:
        import numpy as _np
    except Exception as exc:  # pragma: no cover - numpy siempre debería estar
        return False, f"numpy no importa: {exc}"
    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401
    except Exception as exc:
        return False, f"numpy {_np.__version__}; sentence-transformers roto ({type(exc).__name__})"
    return True, f"numpy {_np.__version__}, sentence-transformers OK"


def _stt_engine_status() -> tuple[str, str]:
    """¿Está listo el STT (Parakeet, único motor) para runtime? Verifica sus
    precondiciones (sherpa-onnx + modelo) SIN arrancar el pipeline de voz (no
    toca micrófono). Whisper se eliminó (reescritura 2026-06-17): si Parakeet no
    está, la voz falla limpio — lo hacemos VISIBLE acá (patrón del health del
    encoder) para que la falta de precondiciones no sorprenda en vivo."""
    from pathlib import Path as _Path
    try:
        import importlib.util as _ilu
        has_sherpa = _ilu.find_spec("sherpa_onnx") is not None
    except Exception:
        has_sherpa = False
    bundle = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
    prod = _Path.home() / ".gemma4" / "models" / bundle / "encoder.int8.onnx"
    repo = (_Path(__file__).resolve().parent.parent.parent
            / "data" / "stt_eval" / "sherpa" / bundle / "encoder.int8.onnx")
    has_model = prod.exists() or repo.exists()
    if has_sherpa and has_model:
        return "parakeet", "Parakeet-TDT-v3 (sherpa-onnx, modelo presente)"
    missing = []
    if not has_sherpa:
        missing.append("sherpa-onnx no instalado")
    if not has_model:
        missing.append("modelo Parakeet ausente")
    return "parakeet-no-listo", "; ".join(missing) + " -> la voz fallará limpio"


def print_status(args: argparse.Namespace) -> int:
    config = config_with_args(args)
    print_banner()

    health = health_status(config)
    health_text = color("ok", "online") if health else color("warn", "offline")
    print(f"{'server':<18} {health_text:<20} {config.server_url}")
    print(f"{'mode':<18} {config.agent_mode}")
    print(f"{'safety':<18} {config.enable_safety}")
    print(f"{'tools':<18} {len(COMPOUND_TOOL_SCHEMAS)} compound schemas")
    print(f"{'context':<18} {config.context_size}")
    print()
    print(file_line("llama-server", config.llama_server_exe))
    print(file_line("model", config.model_path))
    print(file_line("mmproj", config.mmproj_path))
    print()
    print(f"{'memory':<18} {config.memory_path}")
    print(f"{'state':<18} {config.state_path}")
    print(f"{'trace':<18} {config.trace_path}")
    print(f"{'captures':<18} {config.captures_dir}")
    print()
    # HEALTH del stack numérico/encoder (2026-06-07): un numpy fuera de pin
    # (2.x) rompe pandas y arrastra a sentence-transformers -> el ENCODER DEL
    # ROUTER no carga y el routing se degrada SILENCIOSO. Lo hacemos VISIBLE acá.
    _enc_ok, _enc_detail = _encoder_health()
    _enc_text = color("ok", "ok") if _enc_ok else color("error", "BROKEN")
    print(f"{'router encoder':<18} {_enc_text:<20} {_enc_detail}")
    if not _enc_ok:
        print(color("error",
            "  -> El encoder del router NO carga: el routing está DEGRADADO "
            "(ofrecerá web/knowledge para casi todo)."))
        print(color("dim",
            "     Fix: pip install \"numpy==1.26.4\"  (o reinstalá con "
            "-c constraints.txt). Ver requirements.txt."))
    # MOTOR STT (2026-06-17, Parakeet-only tras la reescritura): NO hay fallback a
    # Whisper -> si Parakeet no está, la voz falla limpio; lo hacemos VISIBLE acá.
    _stt_engine, _stt_detail = _stt_engine_status()
    _stt_ok = _stt_engine == "parakeet"
    _stt_text = color("ok", "parakeet") if _stt_ok else color("warn", _stt_engine)
    print(f"{'stt engine':<18} {_stt_text:<20} {_stt_detail}")
    if not _stt_ok:
        print(color("warn",
            "  -> NO estás usando Parakeet. Para restaurarlo: instalá sherpa-onnx "
            "y/o descargá el modelo Parakeet a ~/.gemma4/models/."))
    # MIC default muteado en Windows -> Baxy no oye nada (causa real 2026-06-07).
    try:
        from ..voice.noise_calibration import microphone_muted as _mic_muted
        _muted = _mic_muted()
    except Exception:
        _muted = None
    if _muted is True:
        print(f"{'mic (default)':<18} {color('error', 'MUTEADO'):<20} "
              "el micrófono default está silenciado en Windows -> Baxy no oirá nada")
        print(color("dim", "     Fix: Sonido > Entrada > Volumen (desmutear)."))
    elif _muted is False:
        print(f"{'mic (default)':<18} {color('ok', 'ok'):<20} no muteado")
    print()
    if not health:
        print(color("dim", "Tip: python -m gemma4_agent.infra.launcher chat  # levanta llama-server si hace falta"))
    return 0


def start_server(args: argparse.Namespace, *, wait: bool = True) -> int:
    """Arranca llama-server usando el LlamaServerManager + perfil activo."""
    config = config_with_args(args)

    # Aplicar perfil activo al entorno antes de construir el comando
    profile = get_active_profile()
    apply_profile_to_env(profile)

    # Standby: nada que arrancar
    if not profile.server_running:
        print(color("warn", f"Active profile is {profile.display_name} (server off). Skipping."))
        return 0

    # Server externo: respetar
    if port_in_use():
        print(color("warn",
            "Detected an external llama-server on :8080. NOT killing or "
            "reconfiguring it. Profile flags will not be applied to it."
        ))
        return 0

    missing = [p for p in (config.llama_server_exe, config.model_path) if not p.exists()]
    if missing:
        print(color("error", "No puedo iniciar llama-server; faltan archivos:"))
        for path in missing:
            print(f"  {path}")
        return 2

    # Use the PROCESS-WIDE shared manager so the /profile endpoint (same
    # process, uvicorn thread) can later restart THIS exact server when the
    # user switches VRAM profiles.
    from .llama_server import get_shared_manager
    manager = get_shared_manager(config=config)
    timeout_s = max(1, int(getattr(args, "timeout", 90)))
    print(color("dim",
        f"Iniciando llama-server (profile={profile.name}, ctx={profile.context_size}); "
        f"logs en {(PACKAGE_ROOT / 'logs' / 'llama-server.out.log')}"
    ))
    result = manager.start(profile, wait_health=wait, timeout_s=timeout_s)
    if result == "started":
        print(color("ok", f"llama-server listo en {config.server_url}"))
        return 0
    if result == "already_running":
        print(color("ok", f"llama-server ya estaba online en {config.server_url}"))
        return 0
    if result == "external":
        # connect_ex race; tratamos como warning
        print(color("warn", "Server externo detectado tras intentar arrancar; respetado."))
        return 0
    if result == "missing_files":
        print(color("error", "Faltan archivos para arrancar llama-server."))
        return 2
    if result == "skipped_standby":
        return 0
    # timeout u otros
    print(color("error", "llama-server no quedo listo. Revisa los logs en gemma4_agent/logs/."))
    return 3


def run_chat(args: argparse.Namespace) -> int:
    cmd = [sys.executable, "-m", "gemma4_agent.chat"]
    if not getattr(args, "no_start_server", False):
        cmd.append("--start-server")
    if getattr(args, "server", None):
        cmd.extend(["--server", args.server])
    if getattr(args, "mode", None):
        cmd.extend(["--mode", args.mode])
    return subprocess.run(cmd, cwd=str(PROJECT_ROOT)).returncode


def run_smoke(args: argparse.Namespace) -> int:
    cmd = [sys.executable, "-m", "gemma4_agent.eval_smoke"]
    if getattr(args, "web", False):
        cmd.append("--web")
    return subprocess.run(cmd, cwd=str(PROJECT_ROOT)).returncode


def run_ui(args: argparse.Namespace) -> int:
    """Open the Field UI.

    Modes:
      default        — pywebview window (native)
      --browser      — open the system default browser
      --no-window    — server only, no GUI (useful for headless dev)
    """
    # Web UI path: import locally para no pagar el costo de import de
    # fastapi/uvicorn en cada invocación del launcher.
    # (La GUI vieja PyQt6 + el flag --legacy-ui se eliminaron 2026-06-03;
    # la UI default es la web ui_field/.)
    try:
        import uvicorn
    except ImportError:
        print(color("error", "fastapi/uvicorn no estan instalados."))
        print(color("dim", "  pip install fastapi uvicorn"))
        return 2

    from .server import create_app, UI_DIST

    if not (UI_DIST / "index.html").exists():
        print(color("warn", f"UI bundle no encontrado en {UI_DIST}."))
        print(color("dim", "  cd gemma4_agent/ui_field && pnpm install && pnpm run build"))
        return 2

    config = config_with_args(args)
    app = create_app(config)
    host = getattr(args, "host", "127.0.0.1")
    port = _pick_bindable_port(host, int(getattr(args, "port", 8765)))
    url = f"http://{host}:{port}/"

    no_window = bool(getattr(args, "no_window", False))
    use_browser = bool(getattr(args, "browser", False))

    # ---- headless: just block on uvicorn in this thread ----
    if no_window and not use_browser:
        print(color("dim", f"field UI (headless) · {url} · ctrl-c para salir"))
        uvicorn.run(app, host=host, port=port, log_level="warning")
        return 0

    # ---- shared server thread for both browser and window modes ----
    # uvicorn.Server lets us run it cleanly inside a daemon thread and shut
    # it down when the GUI exits. plain `uvicorn.run` doesn't return until
    # killed, which is fine in headless but blocks the GUI event loop.
    import threading
    server_config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(server_config)

    server_thread = threading.Thread(target=server.run, name="field-uvicorn", daemon=True)
    server_thread.start()

    # wait for the port to bind before we open the GUI — otherwise the window
    # may show an "ERR_CONNECTION_REFUSED" flash on first paint.
    import socket
    import time
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)
    else:
        print(color("error", "el server local no levanto a tiempo."))
        return 3

    if use_browser:
        import webbrowser
        webbrowser.open(url)
        print(color("ok", f"abriendo {url} en el browser"))
        print(color("dim", "ctrl-c para detener el server"))
        try:
            server_thread.join()
        except KeyboardInterrupt:
            server.should_exit = True
        return 0

    # ---- pywebview window mode (default) ----
    try:
        import webview  # type: ignore
    except ImportError:
        print(color("warn", "pywebview no esta instalado; cayendo a modo browser."))
        print(color("dim", "  pip install pywebview"))
        import webbrowser
        webbrowser.open(url)
        try:
            server_thread.join()
        except KeyboardInterrupt:
            server.should_exit = True
        return 0

    # WebView2 renderiza con la GPU por defecto. En este deployment la GPU es
    # para el LLM (y a veces un juego en simultaneo). Cuando esta saturada (~97%)
    # el proceso de GPU del WebView2 CRASHEA y se lleva toda la ventana/proceso
    # con el (no hay traceback de Python: es un crash nativo, vuelve al prompt).
    # Forzamos compositing por CPU para que la UI NUNCA compita por la GPU; el
    # grafo neuronal + el borde viajero corren bien en CPU. Debe setearse ANTES
    # de crear la ventana (WebView2 lee la env var al inicializar). Sumamos
    # --disable-gpu-watchdog: bajo GPU saturada el watchdog de Chromium MATA el
    # proceso de GPU al detectar un "hang" (el gatillo exacto del crash de arriba).
    _wv2_args = os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "")
    if "--disable-gpu" not in _wv2_args:
        os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
            f"{_wv2_args} --disable-gpu --disable-gpu-compositing --disable-gpu-watchdog".strip()
        )

    print(color("ok", f"abriendo ventana · {url}"))

    # The window is frameless (the "field" redesign has no OS title bar — the
    # red .app-frame is the visible chrome). The UI draws its OWN thin title bar
    # (TitleBar.tsx) with min/maximize/close + a `.pywebview-drag-region` handle
    # so the window can be moved. These controls call back into Python through
    # the js_api below. easy_drag stays OFF so a stray click on the chat input
    # never drags the window — only the explicit drag region moves it.
    class _WindowControls:
        """Exposed to JS as window.pywebview.api.* — drives the native window
        from the custom title bar.

        CRITICAL: the pywebview Window reference is stored as `_window`
        (underscore-prefixed). pywebview introspects the js_api object with
        `dir()` and RECURSES into every public, non-callable attribute to expose
        it (webview/util.py get_functions). A public `self.window = <Window>`
        makes it recurse into `window.native` → the .NET WinForms form →
        `.AccessibilityObject.Owner.ActiveControl.Controls.Owner.ModifierKeys…`
        — a circular COM graph → `maximum recursion depth exceeded` storm that
        crashes the bridge. Underscore-prefixed names are skipped by get_functions,
        so `_window` is invisible to the introspection. Only the win_* methods
        are exposed. Bound right after create_window; methods run post-load."""

        def __init__(self) -> None:
            self._window = None  # set below; underscore = NOT introspected
            self._maximized = False
            # True solo si el usuario cerró con NUESTRA X (win_close). Si
            # webview.start() vuelve con esto en False, la ventana murió sola
            # (crash nativo de WebView2/GPU) -> caemos al browser, no matamos la app.
            self._user_closed = False

        def win_minimize(self):
            if self._window is not None:
                self._window.minimize()

        def win_toggle_maximize(self) -> bool:
            if self._window is None:
                return self._maximized
            if self._maximized:
                self._window.restore()
                self._maximized = False
            else:
                self._window.maximize()
                self._maximized = True
            return self._maximized

        def win_is_maximized(self) -> bool:
            return self._maximized

        def win_close(self):
            self._user_closed = True  # cierre deliberado, no un crash
            if self._window is not None:
                self._window.destroy()

        # keep _maximized accurate even when the OS maximizes/restores the window
        # WITHOUT our button (double-click the drag region, Win+Up, aero-snap):
        # pywebview fires these events, and the UI re-reads win_is_maximized on
        # focus, so the CSS expand/compact follows every path.
        def _on_maximized(self):
            self._maximized = True

        def _on_restored(self):
            self._maximized = False

    controls = _WindowControls()
    window = webview.create_window(
        "gemma 4 · field",
        url,
        js_api=controls,
        width=1080,
        height=640,
        min_size=(1000, 600),
        background_color="#0A0E14",
        frameless=True,
        easy_drag=False,
    )
    controls._window = window
    # track OS-driven maximize/restore so win_is_maximized stays truthful for
    # the UI's expand/compact CSS (not just our own button).
    try:
        window.events.maximized += controls._on_maximized
        window.events.restored += controls._on_restored
    except Exception:  # noqa: BLE001 — events are best-effort, button path still works
        pass
    try:
        # webview.start() blocks on the main thread until the window closes.
        # http_server=False because uvicorn already serves the dist/ bundle.
        webview.start(http_server=False)
    except Exception:  # noqa: BLE001 — un crash nativo de WebView2 puede burbujear
        pass

    # RECUPERACIÓN: si start() volvió SIN que el usuario apretara la X, la ventana
    # nativa se murió sola (crash de GPU de WebView2 bajo carga — documentado arriba;
    # Python sobrevive y start() retorna, por eso esto corre). En vez de dejar caer
    # TODA la app (matar uvicorn + salir), reabrimos en el browser del sistema:
    # es un proceso aparte, inmune al crash de GPU de WebView2, así el usuario sigue
    # trabajando sin re-lanzar nada. uvicorn (y el agente) siguen vivos.
    if not controls._user_closed:
        print(color("warn", "la ventana nativa se cerró sola (WebView2/GPU); reabriendo en el browser…"))
        import webbrowser
        webbrowser.open(url)
        print(color("dim", f"  {url} · ctrl-c para detener"))
        try:
            server_thread.join()
        except KeyboardInterrupt:
            pass

    # cierre limpio (X del usuario, o ctrl-c tras el fallback al browser): bajamos
    # uvicorn. daemon=True lo mataría igual al salir, pero el shutdown ordenado le
    # da a las conexiones WS la chance de cerrar.
    server.should_exit = True
    server_thread.join(timeout=3.0)
    return 0


def open_path(args: argparse.Namespace) -> int:
    target = getattr(args, "target", "project")
    config = config_with_args(args)
    targets = {
        "project": PROJECT_ROOT,
        "package": PACKAGE_ROOT,
        "data": config.state_path.parent,
        "captures": config.captures_dir,
        "logs": PACKAGE_ROOT / "logs",
    }
    path = targets.get(target, PROJECT_ROOT)
    path.mkdir(parents=True, exist_ok=True) if target in {"data", "captures", "logs"} else None
    os.startfile(path) if os.name == "nt" else subprocess.run(["xdg-open", str(path)], check=False)
    print(color("ok", f"Abierto: {path}"))
    return 0


def create_desktop_shortcut(args: argparse.Namespace) -> int:
    desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    path = Path(getattr(args, "path", "") or desktop / "Gemma4 Agent.cmd")
    path.parent.mkdir(parents=True, exist_ok=True)
    chat_cmd = f'"{sys.executable}" -m gemma4_agent.chat --start-server'
    if getattr(args, "mode", None):
        chat_cmd += f" --mode {args.mode}"
    content = "\n".join(
        [
            "@echo off",
            f'cd /d "{PROJECT_ROOT}"',
            chat_cmd,
            "pause",
            "",
        ]
    )
    path.write_text(content, encoding="utf-8")
    print(color("ok", f"Acceso directo creado: {path}"))
    return 0


def interactive_menu(args: argparse.Namespace) -> int:
    while True:
        print_banner()
        print("1. Abrir chat (auto llama-server)")
        print("2. Ver estado")
        print("3. Ejecutar smoke test local")
        print("4. Iniciar solo llama-server")
        print("5. Abrir carpeta data/logs")
        print("6. Crear acceso directo en el escritorio")
        print("7. Salir")
        print()
        choice = input("gemma4 launcher> ").strip().lower()
        print()
        if choice in {"1", "chat", "c"}:
            return run_chat(args)
        if choice in {"2", "status", "estado", "s"}:
            print_status(args)
            pause()
        elif choice in {"3", "smoke", "test", "t"}:
            run_smoke(args)
            pause()
        elif choice in {"4", "server", "servidor"}:
            start_server(args)
            pause()
        elif choice in {"5", "open", "abrir"}:
            data_args = argparse.Namespace(**{**vars(args), "target": "data"})
            logs_args = argparse.Namespace(**{**vars(args), "target": "logs"})
            open_path(data_args)
            open_path(logs_args)
            pause()
        elif choice in {"6", "shortcut", "acceso"}:
            create_desktop_shortcut(args)
            pause()
        elif choice in {"7", "q", "quit", "salir"}:
            return 0
        else:
            print(color("warn", "Opcion no reconocida."))
            pause()


def pause() -> None:
    try:
        input("\nEnter para continuar...")
    except (EOFError, KeyboardInterrupt):
        print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m gemma4_agent.infra.launcher",
        description="Launcher local para Gemma4 Agent.",
    )
    parser.add_argument("--server", default=None, help="Base URL del llama-server")
    parser.add_argument("--mode", default=None, help="Modo del agente: auto, fast_action, deep_action, vision_action, audio_mode, research")

    sub = parser.add_subparsers(dest="command")

    chat = sub.add_parser("chat", help="Abrir el chat; por defecto levanta llama-server si hace falta")
    chat.add_argument("--server", default=None)
    chat.add_argument("--mode", default=None)
    chat.add_argument("--no-start-server", action="store_true")

    status = sub.add_parser("status", help="Mostrar diagnostico local")
    status.add_argument("--server", default=None)
    status.add_argument("--mode", default=None)

    server = sub.add_parser("server", help="Iniciar solo llama-server")
    server.add_argument("--server", default=None)
    server.add_argument("--mode", default=None)
    server.add_argument("--timeout", type=int, default=90)
    server.add_argument("--no-wait", action="store_true")

    smoke = sub.add_parser("smoke", help="Ejecutar smoke tests locales sin LLM")
    smoke.add_argument("--web", action="store_true")

    ui = sub.add_parser("ui", help="Abrir la Field UI (ventana nativa por defecto)")
    ui.add_argument("--browser", action="store_true",
                    help="Abrir en el browser del sistema en lugar de una ventana nativa")
    ui.add_argument("--no-window", action="store_true",
                    help="Solo levantar el server, sin ventana ni browser (headless)")
    ui.add_argument("--host", default="127.0.0.1")
    ui.add_argument("--port", type=int, default=8765)

    open_cmd = sub.add_parser("open", help="Abrir carpetas utiles")
    open_cmd.add_argument("target", choices=["project", "package", "data", "captures", "logs"], nargs="?", default="project")

    shortcut = sub.add_parser("shortcut", help="Crear .cmd de escritorio")
    shortcut.add_argument("--path", default=None)
    shortcut.add_argument("--mode", default=None)

    mcp = sub.add_parser(
        "mcp",
        help="Exponer compound tools como MCP server (stdio o HTTP). Ver docs/MCP.md.",
    )
    mcp.add_argument(
        "--port", type=int, default=None,
        help="Si se setea, corre en HTTP en este puerto. Default: stdio.",
    )
    mcp.add_argument(
        "--host", type=str, default="127.0.0.1",
        help="HTTP bind host. Default 127.0.0.1 (solo localhost).",
    )
    mcp.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    enable_ansi()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "chat":
        return run_chat(args)
    if args.command == "status":
        return print_status(args)
    if args.command == "server":
        return start_server(args, wait=not args.no_wait)
    if args.command == "smoke":
        return run_smoke(args)
    if args.command == "ui":
        return run_ui(args)
    if args.command == "open":
        return open_path(args)
    if args.command == "shortcut":
        return create_desktop_shortcut(args)
    if args.command == "mcp":
        # TIER 2 #7: MCP server exposure. Delegamos al modulo directo
        # para evitar duplicar logica de stdio/HTTP/logging.
        from ..tools_pkg.mcp_server import main as mcp_main
        mcp_argv: list[str] = []
        if args.port is not None:
            mcp_argv.extend(["--port", str(args.port)])
        if args.host:
            mcp_argv.extend(["--host", args.host])
        if args.log_level:
            mcp_argv.extend(["--log-level", args.log_level])
        return mcp_main(mcp_argv)
    return interactive_menu(args)


if __name__ == "__main__":
    raise SystemExit(main())
