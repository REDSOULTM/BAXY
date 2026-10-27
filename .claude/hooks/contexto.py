"""Hook SessionStart de BAXY: que ninguna sesión pierda lo que el dueño pidió.

- Siempre: fecha con día de la semana, máquina (PC o notebook), worktree, rama y commit.
- Tras compactar o al retomar: todos los mensajes del dueño de esta sesión, leídos del transcript.
  Completos van a .claude/sesiones/<sesión>.md (local, fuera de git: son privados); al contexto entran los
  más recientes enteros y el resto se señala por su ruta, dentro del tope de 10.000 caracteres del hook.
Sólo librería estándar; si algo falla, la sesión sigue sin el contexto extra (falla abierto).
"""

import datetime
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

BUDGET = 9_000          # Claude Code corta a 10.000 caracteres lo que inyecta un hook
MESSAGE_CAP = 1_500     # un mensaje largo (un goal pegado) entra recortado; entero, en el fichero
DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MACHINES = {"REDPC": "el PC (REDPC)", "REDNOTE": "el notebook (REDNOTE)"}
INJECTED = re.compile(r"^\s*<(system-reminder|command-|local-command|task-notification|side-sessions-event|"
                      r"ci-monitor-event|user-prompt-submit-hook|bash-)")
PEER = re.compile(r"^\s*<cross-session-message[^>]*>(.*?)</cross-session-message>\s*$", re.S)


def git(project: Path, *args: str) -> str:
    try:
        done = subprocess.run(["git", "-C", str(project), *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=5)
        return done.stdout.strip() if done.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def orientation(project: Path) -> str:
    now = datetime.datetime.now()
    host = os.environ.get("COMPUTERNAME") or socket.gethostname()
    where = (f"Ahora: {DAYS[now.weekday()]} {now:%Y-%m-%d %H:%M} (hora local). "
             f"Máquina: {MACHINES.get(host.upper(), host)}. ")
    if git(project, "rev-parse", "--is-inside-work-tree") != "true":
        return where + (f"Carpeta: {project}, que no es un repositorio git: antes de tocar código, entra en el "
                        "worktree del goal y comprueba su rama.")
    branch = git(project, "branch", "--show-current") or "(sin rama: HEAD suelto)"
    head = git(project, "log", "-1", "--format=%h %s")
    dirty = len([line for line in git(project, "status", "--porcelain").splitlines() if line.strip()])
    return where + f"Worktree: {project}. Rama: {branch}; HEAD {head or '?'}; {dirty} fichero(s) sin confirmar."


def texts(content):
    if isinstance(content, str):
        yield content
        return
    for part in content or []:
        if isinstance(part, dict) and part.get("type") == "text":
            yield part.get("text", "")


def owner_messages(transcript: Path) -> list[tuple[str, str]]:
    found = []
    with transcript.open(encoding="utf-8", errors="replace") as lines:
        for line in lines:
            if '"type":"user"' not in line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if (entry.get("type") != "user" or entry.get("isSidechain") or entry.get("isMeta")
                    or entry.get("isCompactSummary")):
                continue
            for text in texts((entry.get("message") or {}).get("content")):
                text = text.strip()
                if not text or text.startswith("[Request interrupted"):
                    continue
                peer = PEER.match(text)
                if peer:
                    text = "[de otra sesión de Claude] " + peer.group(1).strip()
                elif INJECTED.match(text):
                    continue
                found.append((str(entry.get("timestamp", ""))[:16].replace("T", " "), text))
    return found


def save(project: Path, session: str, messages: list[tuple[str, str]]) -> Path:
    folder = project / ".claude" / "sesiones"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{session}.md"
    body = [f"# Mensajes del dueño — sesión {session}", "",
            "Privado: no se versiona ni se copia literal a ficheros versionados.", ""]
    for number, (stamp, text) in enumerate(messages, 1):
        body += [f"## {number}. {stamp} UTC", "", text, ""]
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def digest(messages: list[tuple[str, str]], path: Path, budget: int) -> str:
    head = (f"Mensajes del dueño en esta sesión ({len(messages)}; lista completa en {path}). Lo que pidió sigue "
            "vigente salvo que él mismo lo cambiara después; si dudas de un detalle, lee el fichero entero.")
    chosen, used = [], len(head)
    for number in range(len(messages), 0, -1):
        stamp, text = messages[number - 1]
        if len(text) > MESSAGE_CAP:
            text = text[:MESSAGE_CAP] + f" […recortado: {len(text)} caracteres, entero en el fichero]"
        item = f"\n{number}. [{stamp} UTC] {text}"
        if used + len(item) > budget:
            break
        chosen.append(item)
        used += len(item)
    skipped = len(messages) - len(chosen)
    tail = f"\n(Los {skipped} mensajes más antiguos sólo están en el fichero.)" if skipped else ""
    return head + "".join(reversed(chosen)) + tail


def main() -> int:
    if os.environ.get("BAXY_CONTEXTO", "").lower() == "off":
        return 0
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return 0
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".")
    parts = [orientation(project)]
    transcript = Path(str(event.get("transcript_path") or ""))
    if event.get("source") in ("compact", "resume") and transcript.is_file():
        try:
            messages = owner_messages(transcript)
            if messages:
                path = save(project, str(event.get("session_id") or transcript.stem), messages)
                parts.append(digest(messages, path, BUDGET - len(parts[0])))
        except OSError:
            pass
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                             "additionalContext": "\n\n".join(parts)}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
