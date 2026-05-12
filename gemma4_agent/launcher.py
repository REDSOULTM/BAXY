"""Local launcher for the Gemma 4 Windows agent.

This is intentionally small and dependency-free. It borrows the useful shape of
Jarvis' launcher (one command for setup/status/start), but keeps this project
fully local and focused on the text agent.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

from . import __version__
from .config import AgentConfig, PACKAGE_ROOT, PROJECT_ROOT
from .llm_client import LLMClient
from .tools import COMPOUND_TOOL_SCHEMAS


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


def llama_command(config: AgentConfig) -> list[str]:
    return [
        str(config.llama_server_exe.resolve()),
        "-m",
        str(config.model_path.resolve()),
        "--mmproj",
        str(config.mmproj_path.resolve()),
        "--jinja",
        "--port",
        "8080",
        "-ngl",
        "99",
        "-c",
        str(config.context_size),
        "--parallel",
        "1",
        "--ctx-checkpoints",
        "1",
        "--flash-attn",
        "on",
    ]


def start_server(args: argparse.Namespace, *, wait: bool = True) -> int:
    config = config_with_args(args)
    if health_status(config, timeout_s=1.0):
        print(color("ok", f"llama-server ya esta online en {config.server_url}"))
        return 0

    missing = [p for p in (config.llama_server_exe, config.model_path, config.mmproj_path) if not p.exists()]
    if missing:
        print(color("error", "No puedo iniciar llama-server; faltan archivos:"))
        for path in missing:
            print(f"  {path}")
        return 2

    log_dir = PACKAGE_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / "llama-server.out.log"
    stderr_path = log_dir / "llama-server.err.log"
    stdout = stdout_path.open("a", encoding="utf-8", errors="replace")
    stderr = stderr_path.open("a", encoding="utf-8", errors="replace")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    subprocess.Popen(
        llama_command(config),
        cwd=str(PROJECT_ROOT),
        stdout=stdout,
        stderr=stderr,
        creationflags=creationflags,
    )
    print(color("dim", f"Iniciando llama-server; logs en {stdout_path}"))
    if not wait:
        return 0

    for _ in range(max(1, int(getattr(args, "timeout", 90)))):
        if health_status(config, timeout_s=1.0):
            print(color("ok", f"llama-server listo en {config.server_url}"))
            return 0
        time.sleep(1)

    print(color("error", f"llama-server no quedo listo. Revisa {stderr_path}"))
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

    open_cmd = sub.add_parser("open", help="Abrir carpetas utiles")
    open_cmd.add_argument("target", choices=["project", "package", "data", "captures", "logs"], nargs="?", default="project")

    shortcut = sub.add_parser("shortcut", help="Crear .cmd de escritorio")
    shortcut.add_argument("--path", default=None)
    shortcut.add_argument("--mode", default=None)

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
    if args.command == "open":
        return open_path(args)
    if args.command == "shortcut":
        return create_desktop_shortcut(args)
    return interactive_menu(args)


if __name__ == "__main__":
    raise SystemExit(main())
