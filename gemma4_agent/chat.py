"""Interactive CLI for the standalone Gemma 4 agent."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from gemma4_agent.agent import Gemma4Agent
    from gemma4_agent.config import AgentConfig
else:
    from .agent import Gemma4Agent
    from .config import AgentConfig


PALETTE = {
    "user": "\033[33;1m",
    "assistant": "\033[36m",
    "tool": "\033[35m",
    "result": "\033[34m",
    "error": "\033[31;1m",
    "system": "\033[90m",
    "ok": "\033[32m",
    "reset": "\033[0m",
}


def enable_ansi() -> None:
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def _print_server_help(config: AgentConfig) -> None:
    print(f"{PALETTE['error']}llama-server no responde en {config.server_url}{PALETTE['reset']}")
    model_path = config.model_path.resolve()
    mmproj_path = config.mmproj_path.resolve()
    llama_path = config.llama_server_exe.resolve()
    print(f"{PALETTE['system']}Ejemplo para levantar Gemma 4 E4B-Q6_K:{PALETTE['reset']}")
    print(f'  & "{llama_path}" `')
    print(f'      -m "{model_path}" `')
    print(f'      --mmproj "{mmproj_path}" `')
    print(f'      --jinja --port 8080 -ngl 99 -c {config.context_size} `')
    print('      --parallel 1 --ctx-checkpoints 1 --flash-attn on')
    print(f"\n{PALETTE['system']}O ejecutá el agente con --start-server para levantarlo automáticamente.{PALETTE['reset']}")


def _start_llama_server(config: AgentConfig, agent: Gemma4Agent) -> bool:
    llama = config.llama_server_exe.resolve()
    model = config.model_path.resolve()
    mmproj = config.mmproj_path.resolve()
    missing = [str(p) for p in (llama, model, mmproj) if not p.exists()]
    if missing:
        print(f"{PALETTE['error']}No puedo iniciar llama-server; faltan archivos:{PALETTE['reset']}")
        for path in missing:
            print(f"  {path}")
        return False

    cmd = [
        str(llama),
        "-m", str(model),
        "--mmproj", str(mmproj),
        "--jinja",
        "--port", "8080",
        "-ngl", "99",
        "-c", str(config.context_size),
        "--parallel", "1",
        "--ctx-checkpoints", "1",
        "--flash-attn", "on",
    ]
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(exist_ok=True)
    stdout_path = log_dir / "llama-server.out.log"
    stderr_path = log_dir / "llama-server.err.log"
    stdout = stdout_path.open("a", encoding="utf-8", errors="replace")
    stderr = stderr_path.open("a", encoding="utf-8", errors="replace")
    subprocess.Popen(
        cmd,
        cwd=str(Path(__file__).resolve().parents[1]),
        stdout=stdout,
        stderr=stderr,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    print(f"{PALETTE['system']}Iniciando llama-server; logs en {stdout_path}{PALETTE['reset']}")
    for _ in range(90):
        if agent.client.health(timeout_s=1.0):
            return True
        time.sleep(1)
    print(f"{PALETTE['error']}llama-server no quedó listo tras 90s. Revisá {stderr_path}{PALETTE['reset']}")
    return False


def _path(raw: str) -> Path | None:
    path = Path(raw.strip().strip('"').strip("'")).expanduser()
    if not path.exists():
        print(f"{PALETTE['error']}No existe: {path}{PALETTE['reset']}")
        return None
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default=None, help="Base URL del llama-server")
    parser.add_argument("--image", action="append", default=[], help="Adjuntar imagen al primer turno")
    parser.add_argument("--audio", action="append", default=[], help="Adjuntar audio al primer turno")
    parser.add_argument("--mode", default=None, help="Modo: auto, fast_action, deep_action, vision_action, audio_mode, research")
    parser.add_argument("--no-health", action="store_true", help="No verificar /health antes de iniciar")
    parser.add_argument("--start-server", action="store_true", help="Levantar llama-server si no responde")
    args = parser.parse_args()

    enable_ansi()
    config = AgentConfig.from_env()
    if args.server:
        config = AgentConfig(**{**config.__dict__, "server_url": args.server})
    if args.mode:
        config = AgentConfig(**{**config.__dict__, "agent_mode": args.mode})

    agent = Gemma4Agent(config)
    if not args.no_health and not agent.client.health():
        if args.start_server and _start_llama_server(config, agent):
            pass
        else:
            _print_server_help(config)
            return 2

    pending_images = [p for raw in args.image if (p := _path(raw))]
    pending_audios = [p for raw in args.audio if (p := _path(raw))]

    print(f"{PALETTE['ok']}Gemma4 agent listo en {config.server_url}{PALETTE['reset']}")
    print(f"{PALETTE['system']}Comandos: /quit /clear /image <path> /audio <path> /memory /tools{PALETTE['reset']}")
    print(f"{PALETTE['system']}Tools reales: {len(agent.tools.schemas)} | Mode: {config.agent_mode} | Trace: {config.trace_path}{PALETTE['reset']}")
    print(f"{PALETTE['system']}Memory: {config.memory_path}{PALETTE['reset']}\n")

    while True:
        try:
            user = input(f"{PALETTE['user']}vos>{PALETTE['reset']} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        low = user.lower()
        if low in {"/quit", "/exit", "/q"}:
            break
        if low == "/clear":
            agent.clear()
            print(f"{PALETTE['system']}Contexto limpiado.{PALETTE['reset']}\n")
            continue
        if low == "/memory":
            print(agent.memory.prompt_summary())
            print()
            continue
        if low == "/tools":
            for schema in agent.tools.schemas:
                print(schema["function"]["name"])
            print()
            continue
        if low.startswith("/image "):
            p = _path(user[7:])
            if p:
                pending_images.append(p)
                print(f"{PALETTE['system']}Imagen adjunta al proximo turno: {p}{PALETTE['reset']}\n")
            continue
        if low.startswith("/audio "):
            p = _path(user[7:])
            if p:
                pending_audios.append(p)
                print(f"{PALETTE['system']}Audio adjunto al proximo turno: {p}{PALETTE['reset']}\n")
            continue

        reply = agent.run_text(user, images=pending_images, audios=pending_audios)
        pending_images = []
        pending_audios = []

        for event in reply.tool_events:
            print(f"{PALETTE['tool']}-> {event.name}({event.args}){PALETTE['reset']}")
            color = PALETTE["result"] if event.result.get("ok") else PALETTE["error"]
            print(f"{color}<- {event.result}{PALETTE['reset']}")

        if reply.error:
            print(f"{PALETTE['error']}LLM error: {reply.error}{PALETTE['reset']}\n")
        else:
            print(f"{PALETTE['assistant']}gemma4>{PALETTE['reset']} {reply.content}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
