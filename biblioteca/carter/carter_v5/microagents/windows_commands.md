---
name: windows_commands
triggers: ["comando", "shell", "terminal", "powershell", "cmd", "ejecutar"]
priority: medium
---

# Windows command equivalents (terminal_run cheat sheet)

Carter v5 corre comandos via `terminal_run(command, args)`. Estos son los más comunes en Windows:

## Filesystem (preferí `filesystem` tool, no terminal)

| Bash / Unix | Windows native | Carter tool |
|---|---|---|
| `ls`, `ls -la` | `dir`, `dir /a` | `filesystem.list` (preferido) |
| `cat`, `head`, `tail` | `type`, `more` | `filesystem.read` (preferido) |
| `cp` | `copy`, `xcopy` | `filesystem.copy` |
| `mv` | `move` | `filesystem.move` |
| `rm` | `del`, `erase` | `filesystem.delete` (destructive) |
| `mkdir -p` | `mkdir` | `filesystem.create_dir` |
| `find` | `dir /s` | `filesystem.search` |

## Process / system

| Action | Windows command |
|---|---|
| Lista procesos | `tasklist` |
| Mata proceso (destructive) | `taskkill /PID <pid>` o `taskkill /IM <name>` |
| Hora | `time /t`, `Get-Date` |
| Disco | `wmic logicaldisk get size,freespace,caption` |
| Network | `ipconfig`, `netstat` |
| Users | `whoami`, `net user` |

## Development

| Tool | Comando |
|---|---|
| Python | `python --version`, `python script.py`, `pip list` |
| Git | `git status`, `git log -5`, `git diff` |
| NPM | `npm list`, `npm install`, `npm run build` |
| pytest | `pytest -v`, `pytest --collect-only` |

## Notas

- `dir`, `ls`, `type`, `cat` son **shell builtins** — usá `filesystem.list/read` que es más limpio.
- `pip install`, `npm install`, `apt install` son **DESTRUCTIVE** — requiere confirmación.
- `taskkill /F` es destructive. `Stop-Process -Force` también.
