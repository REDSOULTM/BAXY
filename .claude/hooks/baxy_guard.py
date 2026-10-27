"""Guarda de Claude Code para BAXY: lee el evento del hook por stdin y decide.

Adaptado de los hooks de everything-claude-code (block-no-verify, config-protection) y del
incidente de msconfig. Sólo librería estándar; si este script falla, Claude Code sigue (falla
abierto). Modos:
  pre-shell  PreToolUse de Bash/PowerShell: deniega lo que no se hace aquí nunca.
  post-edit  PostToolUse de Edit/Write: avisa a Claude, sin bloquear, de lo que debe revisar.
BAXY_GUARD=off al lanzar Claude Code la apaga entera.
"""

import json
import os
import re
import sys
from pathlib import Path

AGENTS_LIMIT = 10_000

# Patrón -> motivo. Se buscan en el comando entero, sin distinguir mayúsculas.
DENIED_COMMANDS = [
    (r"--no-verify\b|--no-gpg-sign\b|commit\.gpgsign\s*=\s*false",
     "no se saltan los hooks ni la firma de git; arregla lo que el hook señala"),
    (r"\bgit\s+stash\b(?!\s+(list|show)\b)",
     "git stash en un worktree compartido esconde el trabajo de otras sesiones"),
    (r"\bgit\s+reset\s+(\S+\s+)*--hard\b",
     "git reset --hard borra cambios sin confirmar, también los de otras sesiones"),
    (r"\bgit\s+clean\s+(\S+\s+)*-[a-z]*f",
     "git clean -f borra ficheros sin versionar que pueden ser de otra sesión"),
    (r"\bgit\s+push\b[^;&|]*\s(--force\b|-f\b)",
     "push forzado: reescribe historia publicada"),
    (r"\bgit\s+checkout\s+(--\s+)?\.(\s|$)|"
     r"\bgit\s+restore\s+(?![^;&|]*--staged)(\S+\s+)*\.(\s|$)",
     "descartar el árbol entero borra cambios de otras sesiones"),
    (r"\bmsconfig\b|\bbcdedit\b|\bsc(\.exe)?\s+(config|delete|stop)\b|"
     r"\bset-service\b|\bstop-service\b|\breg(\.exe)?\s+(add|delete|import)\s+hklm",
     "configuración de servicios o del arranque de Windows (incidente msconfig: 256 servicios)"),
]

QUALITY_CONFIGS = {
    "ruff.toml", "pytest.ini", "directory.build.props", "directory.packages.props",
    "global.json", "eslint.config.js", ".editorconfig", "requirements-quality.txt",
}


def deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": f"Guarda BAXY: {reason}. Si de verdad hace falta, "
                                    "que lo ejecute el dueño (prefijo ! en Claude Code).",
    }}))


def pre_shell(event: dict) -> int:
    command = str(event.get("tool_input", {}).get("command", ""))
    for pattern, reason in DENIED_COMMANDS:
        if re.search(pattern, command, re.IGNORECASE):
            deny(reason)
            return 0
    return 0


def post_edit(event: dict) -> int:
    file_path = str(event.get("tool_input", {}).get("file_path", ""))
    if not file_path:
        return 0
    path = Path(file_path)
    name = path.name.lower()
    notes = []
    if name == "agents.md":
        try:
            size = len(path.read_text(encoding="utf-8"))
        except OSError:
            size = 0
        if size > AGENTS_LIMIT:
            notes.append(f"AGENTS.md tiene {size} caracteres y el tope duro es {AGENTS_LIMIT} "
                         "(Grok lo trunca por el final). Recórtalo antes de seguir.")
    if name in QUALITY_CONFIGS or (name.startswith("tsconfig") and name.endswith(".json")):
        notes.append(f"Has editado {path.name}, configuración de calidad. No se relaja una regla "
                     "para pasar la compuerta (AGENTS.md: ni skip, ni umbral relajado); si el "
                     "cambio es legítimo, di por qué en el commit.")
    if not notes:
        return 0
    print("Guarda BAXY: " + " ".join(notes), file=sys.stderr)
    return 2  # PostToolUse con código 2: el aviso llega a Claude; la edición ya está hecha.


def main() -> int:
    if os.environ.get("BAXY_GUARD", "").lower() == "off" or len(sys.argv) != 2:
        return 0
    # Claude Code lee la salida como UTF-8; la consola de Windows no lo es por defecto.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return 0
    handlers = {"pre-shell": pre_shell, "post-edit": post_edit}
    handler = handlers.get(sys.argv[1])
    return handler(event) if handler else 0


if __name__ == "__main__":
    sys.exit(main())
