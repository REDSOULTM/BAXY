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

from . import __version__
from .config import AgentConfig, PACKAGE_ROOT, PROJECT_ROOT
from .llama_server import LlamaServerManager, port_in_use
from .llm_client import LLMClient
from .profiles import apply_profile_to_env, get_active_profile
from .tools import COMPOUND_TOOL_SCHEMAS


def _emit_router_v2_summary() -> None:
    """Hotfix H 2026-05-17. Best-effort: log the v2 session
    summary on shutdown so operators can track router_v2 health
    over real sessions without instrumenting every turn. No-op if
    the singleton was never instantiated (e.g. launcher status
    that doesn't touch routing).
    """
    try:
        from .router_v2 import RouterV2
        router = RouterV2._instance
        if router is None:
            return
        summary = router.session_summary()
        # Only emit when there's something to report — keeps the
        # status command quiet for users that don't run a chat.
        if summary.get("calls_total", 0) > 0:
            print(f"router_v2_session_summary {summary}")
    except Exception:
        pass


atexit.register(_emit_router_v2_summary)


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
    if not health:
        print(color("dim", "Tip: python -m gemma4_agent.launcher chat  # levanta llama-server si hace falta"))
    return 0


def _ensure_router_v2_model() -> None:
    """Idempotent: download e5-small ONNX + tokenizer + smalltalk
    centroid on first launch. ~113 MB int8 model.

    Hotfix E 2026-05-17. The previous path-to-production required
    the user to run scripts/bootstrap_e5_small.py manually. That
    step is now automated — if MODEL_PATH doesn't exist, the
    launcher invokes the same bootstrap script before starting.
    Already-installed models are detected by checking MODEL_PATH;
    re-runs print 'already complete' and return in <1s.

    Errors during bootstrap log a warning but do NOT block the
    launcher — v1 is still a valid fallback path.
    """
    try:
        from .router_v2 import MODEL_PATH
        if MODEL_PATH.exists():
            return
        print(
            "First-run router_v2 bootstrap: downloading e5-small "
            "(~113 MB, multilingual int8 ONNX) to ~/.gemma4/models/e5-small/. "
            "This happens once."
        )
        from scripts.bootstrap_e5_small import main as bootstrap_main
        bootstrap_main()
    except Exception as exc:
        print(f"router_v2 bootstrap failed ({exc}); falling back to v1 routing.")


def start_server(args: argparse.Namespace, *, wait: bool = True) -> int:
    """Arranca llama-server usando el LlamaServerManager + perfil activo."""
    _ensure_router_v2_model()
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

    manager = LlamaServerManager(config=config)
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
      default        — pywebview window (native, like the legacy PyQt6 GUI)
      --browser      — open the system default browser
      --no-window    — server only, no GUI (useful for headless dev)
      --legacy-ui    — fall back to the PyQt6 GUI that lived here before
    """
    if getattr(args, "legacy_ui", False):
        cmd = [sys.executable, "-m", "gemma4_agent.ui"]
        return subprocess.run(cmd, cwd=str(PROJECT_ROOT)).returncode

    # Web UI path: import locally so users who only need the legacy GUI
    # don't pay the fastapi/uvicorn import cost on every launcher invocation.
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
        print(color("dim", "  o usa --legacy-ui para abrir la GUI PyQt6 anterior."))
        return 2

    config = config_with_args(args)
    app = create_app(config)
    host = getattr(args, "host", "127.0.0.1")
    port = int(getattr(args, "port", 8765))
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

    print(color("ok", f"abriendo ventana · {url}"))
    webview.create_window(
        "gemma 4 · field",
        url,
        width=1320,
        height=860,
        min_size=(1024, 700),
        background_color="#0A0E14",
    )
    try:
        # webview.start() blocks on the main thread until the window closes.
        # http_server=False because uvicorn already serves the dist/ bundle.
        webview.start(http_server=False)
    finally:
        # tell uvicorn to wind down. daemon=True would kill it on exit too,
        # but a clean shutdown gives the WS connections a chance to close.
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
        prog="python -m gemma4_agent.launcher",
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
    ui.add_argument("--legacy-ui", action="store_true", help="Abrir la GUI PyQt6 anterior")
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
        from .mcp_server import main as mcp_main
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
