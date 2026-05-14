"""Interactive CLI for the standalone Gemma 4 agent."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from gemma4_agent.agent import Gemma4Agent
    from gemma4_agent.config import AgentConfig
    from gemma4_agent.sessions import Session, SessionStore, auto_title, is_enabled as sessions_enabled
    from gemma4_agent.timeline import TimelineWriter, is_enabled as timeline_enabled
else:
    from .agent import Gemma4Agent
    from .config import AgentConfig
    from .sessions import Session, SessionStore, auto_title, is_enabled as sessions_enabled
    from .timeline import TimelineWriter, is_enabled as timeline_enabled


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


class ProgressDisplay:
    FRAMES = "|/-\\"

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled and sys.stdout.isatty()
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._start = 0.0
        self._frame = 0
        self._progress = 0.03
        self._message = "Pensando"
        self._mode = ""
        self._tools = 0
        self._steps = 0
        self._turn = 0
        self._max_turns = 0

    def start(self) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._running = True
            self._start = time.time()
            self._progress = 0.03
            self._message = "Preparando turno"
            self._tools = 0
            self._steps = 0
            self._turn = 0
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def update(self, event: str, payload: dict[str, Any]) -> None:
        if not self.enabled:
            return
        with self._lock:
            if event == "start":
                self._mode = str(payload.get("mode") or "")
                self._steps = int(payload.get("steps") or 0)
                self._max_turns = int(payload.get("max_turns") or 0)
                suffix = f" | {self._steps} pasos" if self._steps else ""
                self._message = f"Planificando{suffix}"
                self._progress = max(self._progress, 0.06)
            elif event == "tool_subset":
                count = int(payload.get("schema_count") or 0)
                self._message = f"Seleccionando {count} tool(s) relevantes"
                self._progress = max(self._progress, 0.09)
            elif event == "llm_start":
                self._turn = int(payload.get("turn") or 0)
                self._tools = int(payload.get("tools") or self._tools)
                self._message = "Gemma pensando"
                self._progress = max(self._progress, min(0.72, 0.12 + max(self._turn - 1, 0) * 0.10))
            elif event == "llm_response":
                tool_calls = int(payload.get("tool_calls") or 0)
                self._message = f"Gemma eligio {tool_calls} tool(s)" if tool_calls else "Preparando respuesta"
                self._progress = max(self._progress, 0.55 if tool_calls else 0.88)
            elif event == "tool_start":
                self._tools = max(self._tools, int(payload.get("index") or self._tools + 1) - 1)
                name = str(payload.get("name") or "tool")
                detail = _tool_detail(payload.get("args"))
                self._message = f"Tool {name}{detail}"
                self._progress = min(0.90, max(self._progress + 0.05, 0.60))
            elif event == "tool_end":
                self._tools = max(self._tools, int(payload.get("index") or self._tools))
                name = str(payload.get("name") or "tool")
                status = str(payload.get("status") or ("ok" if payload.get("ok") else "error"))
                self._message = f"Tool {name} -> {status}"
                self._progress = min(0.94, max(self._progress + 0.04, 0.66))
            elif event == "image_injected":
                self._message = "Imagen devuelta a Gemma para verificacion"
                self._progress = min(0.95, max(self._progress, 0.76))
            elif event == "context_retry":
                self._message = "Compactando contexto y reintentando"
                self._progress = max(self._progress, 0.20)
            elif event == "context_retry_ok":
                self._message = "Contexto compactado"
                self._progress = max(self._progress, 0.30)
            elif event in {"final", "max_turns"}:
                self._message = "Listo"
                self._tools = int(payload.get("tools") or self._tools)
                self._progress = 1.0
            elif event == "error":
                self._message = "Error del LLM"
                self._progress = 1.0

    def finish(self) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._running = False
            self._progress = 1.0
        if self._thread:
            self._thread.join(timeout=0.5)
        self._clear_line()

    def _loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
                line = self._render_line()
                self._frame += 1
            width = max(40, shutil.get_terminal_size((100, 20)).columns)
            sys.stdout.write("\r" + line[: width - 1].ljust(width - 1))
            sys.stdout.flush()
            time.sleep(0.12)

    def _render_line(self) -> str:
        elapsed = int(time.time() - self._start) if self._start else 0
        width = 18
        filled = min(width, max(0, int(self._progress * width)))
        bar = "#" * filled + "-" * (width - filled)
        pct = int(self._progress * 100)
        frame = self.FRAMES[self._frame % len(self.FRAMES)]
        meta = []
        if self._mode:
            meta.append(self._mode)
        if self._steps:
            meta.append(f"{self._steps} pasos")
        if self._tools:
            meta.append(f"{self._tools} tools")
        if self._turn and self._max_turns:
            meta.append(f"turno {self._turn}/{self._max_turns}")
        suffix = " | " + " | ".join(meta) if meta else ""
        return f"{PALETTE['system']}{frame} [{bar}] {pct:3d}% {self._message} ({elapsed}s){suffix}{PALETTE['reset']}"

    def _clear_line(self) -> None:
        width = max(40, shutil.get_terminal_size((100, 20)).columns)
        sys.stdout.write("\r" + " " * (width - 1) + "\r")
        sys.stdout.flush()


def _tool_detail(raw_args: Any) -> str:
    if not isinstance(raw_args, dict):
        return ""
    for key in ("action", "query", "name", "path", "url", "command"):
        value = raw_args.get(key)
        if value:
            text = str(value)
            if len(text) > 36:
                text = "..." + text[-33:]
            return f"({text})"
    return ""


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
    parser.add_argument("--no-progress", action="store_true", help="Desactivar barra de progreso del chat")
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
    progress_enabled = not args.no_progress

    session_store: SessionStore | None = None
    current_session: Session | None = None
    if sessions_enabled():
        try:
            session_store = SessionStore()
            current_session = Session.new()
        except OSError as exc:
            print(f"{PALETTE['system']}Sessions desactivado: {exc}{PALETTE['reset']}")
            session_store = None

    print(f"{PALETTE['ok']}Gemma4 agent listo en {config.server_url}{PALETTE['reset']}")
    print(f"{PALETTE['system']}Comandos: /quit /clear /image <path> /audio <path> /memory /tools /state /cleanup /progress /persona [name] /sessions /load <id> /new /title <txt>{PALETTE['reset']}")
    print(f"{PALETTE['system']}Tools reales: {len(agent.tools.schemas)} | Mode: {config.agent_mode} | Safety: {config.enable_safety} | Trace: {config.trace_path}{PALETTE['reset']}")
    print(f"{PALETTE['system']}Memory: {config.memory_path}{PALETTE['reset']}")
    print(f"{PALETTE['system']}State: {config.state_path}{PALETTE['reset']}")
    if session_store and current_session:
        print(f"{PALETTE['system']}Session: {current_session.id} (nuevo) | dir: {session_store.root}{PALETTE['reset']}\n")
    else:
        print()

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
        if low == "/state":
            print(agent.tools.execute("state", {"action": "resources", "include_closed": False}))
            print()
            continue
        if low == "/cleanup":
            print(agent.tools.execute("state", {"action": "cleanup"}))
            print()
            continue
        if low == "/progress":
            progress_enabled = not progress_enabled
            state = "activada" if progress_enabled else "desactivada"
            print(f"{PALETTE['system']}Barra de progreso {state}.{PALETTE['reset']}\n")
            continue
        if low == "/persona" or low.startswith("/persona "):
            from .personas import list_names
            arg = user[len("/persona"):].strip()
            if not arg:
                current = agent.get_persona()
                print(f"{PALETTE['system']}Persona actual: {current['persona']} ({current['description']}){PALETTE['reset']}")
                print(f"{PALETTE['system']}Disponibles: {', '.join(list_names())}{PALETTE['reset']}\n")
            else:
                result = agent.set_persona(arg)
                if result.get("ok"):
                    print(f"{PALETTE['system']}Persona cambiada a '{result['persona']}': {result['description']}{PALETTE['reset']}\n")
                else:
                    print(f"{PALETTE['system']}Error: {result.get('error')}. Disponibles: {', '.join(result.get('available', []))}{PALETTE['reset']}\n")
            continue
        if low == "/sessions":
            if not session_store:
                print(f"{PALETTE['system']}Sessions desactivado.{PALETTE['reset']}\n")
                continue
            entries = session_store.list_sessions(limit=20)
            if not entries:
                print(f"{PALETTE['system']}No hay sessions guardadas en {session_store.root}{PALETTE['reset']}\n")
            else:
                print(f"{PALETTE['system']}Sessions (mas recientes primero):{PALETTE['reset']}")
                for entry in entries:
                    mark = " (actual)" if current_session and entry["id"] == current_session.id else ""
                    print(f"{PALETTE['system']}  {entry['id']}  [{entry['updated_at']}]  ({entry['turn_count']}t)  {entry['title']}{mark}{PALETTE['reset']}")
                print()
            continue
        if low.startswith("/load "):
            if not session_store:
                print(f"{PALETTE['system']}Sessions desactivado.{PALETTE['reset']}\n")
                continue
            sid = user[6:].strip()
            loaded = session_store.load(sid)
            if not loaded:
                print(f"{PALETTE['error']}No se encontro session: {sid}{PALETTE['reset']}\n")
                continue
            current_session = loaded
            print(f"{PALETTE['system']}Session cargada: {loaded.id} - {loaded.title} ({len(loaded.turns)} turnos){PALETTE['reset']}")
            print(f"{PALETTE['system']}Resumen de turnos:{PALETTE['reset']}")
            for turn in loaded.turns[-6:]:
                preview = turn.content[:100].replace("\n", " ")
                print(f"{PALETTE['system']}  [{turn.role}] {preview}{PALETTE['reset']}")
            print(f"{PALETTE['system']}(El agente arranca con history vacio; los turnos son referencia para vos.){PALETTE['reset']}\n")
            continue
        if low == "/new":
            if not session_store:
                print(f"{PALETTE['system']}Sessions desactivado.{PALETTE['reset']}\n")
                continue
            current_session = Session.new()
            agent.clear()
            print(f"{PALETTE['system']}Nueva session: {current_session.id}. Contexto del agente limpiado.{PALETTE['reset']}\n")
            continue
        if low.startswith("/title "):
            if not session_store or not current_session:
                print(f"{PALETTE['system']}Sessions desactivado.{PALETTE['reset']}\n")
                continue
            new_title = user[7:].strip()
            if not new_title:
                print(f"{PALETTE['error']}Uso: /title <texto>{PALETTE['reset']}\n")
                continue
            current_session.title = new_title
            session_store.save(current_session)
            print(f"{PALETTE['system']}Titulo: {new_title}{PALETTE['reset']}\n")
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

        progress = ProgressDisplay(enabled=progress_enabled)
        progress.start()
        progress_cb: Any = progress.update
        timeline_writer: TimelineWriter | None = None
        if timeline_enabled() and current_session is not None:
            turn_idx = len(current_session.turns) // 2 + 1
            timeline_writer = TimelineWriter(
                session_id=current_session.id,
                turn_index=turn_idx,
                inner=progress.update,
            )
            progress_cb = timeline_writer
        try:
            reply = agent.run_text(user, images=pending_images, audios=pending_audios, progress=progress_cb)
        finally:
            progress.finish()
            if timeline_writer is not None:
                timeline_writer.close()
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

        if session_store and current_session:
            from .sessions import SessionTurn
            current_session.turns.append(SessionTurn(role="user", content=user))
            current_session.turns.append(SessionTurn(
                role="assistant",
                content=reply.content or "",
                tool_count=len(reply.tool_events),
            ))
            if current_session.title == "(sin titulo)" and len(current_session.turns) <= 2:
                try:
                    title = auto_title(
                        user,
                        chat_fn=lambda msgs: agent.client.chat(
                            msgs, tools=None, enable_thinking=False,
                            parallel_tool_calls=False, max_tokens=30, timeout_s=10.0,
                        ),
                    )
                    current_session.title = title
                except Exception:
                    pass
            session_store.save(current_session)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
