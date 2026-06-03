---
name: windows-commands
priority: medium
triggers: ["powershell", "cmd", "bash", "wsl"]
examples: ["cómo ejecuto un comando en la terminal de windows", "qué comando de powershell o cmd uso para esto", "cómo corro esto desde la línea de comandos", "how do I run a command in the terminal", "que comando uso en la consola para esto"]
---

# Windows commands cheatsheet

Equivalencias para responder cómo hacer algo en línea de comando. **Default Windows 11: PowerShell, no cmd.**

## bash ↔ PowerShell ↔ cmd
| bash | PowerShell (aliases) | cmd |
|---|---|---|
| `ls` | `Get-ChildItem` (`ls`,`dir`) | `dir` |
| `cat file` | `Get-Content file` (`cat`,`gc`) | `type file` |
| `pwd` | `Get-Location` (`pwd`,`gl`) | `cd` |
| `cd /path` | `Set-Location /path` (`cd`) | `cd /d` |
| `rm file` | `Remove-Item file` (`rm`,`del`) | `del file` |
| `rm -rf dir` | `Remove-Item -Recurse -Force dir` | `rmdir /s /q dir` |
| `cp src dst` | `Copy-Item src dst` (`cp`) | `copy src dst` |
| `mv src dst` | `Move-Item src dst` (`mv`) | `move src dst` |
| `mkdir -p path` | `New-Item -ItemType Directory -Force path` | `md path` |
| `which cmd` | `Get-Command cmd` / `(gcm cmd).Source` | `where cmd` |
| `grep pat file` | `Select-String pat file` (`sls`) | `findstr pat file` |
| `wc -l file` | `(Get-Content file \| Measure-Object -Line).Lines` | `find /c /v "" file` |
| `head -n 5 file` | `Get-Content file -TotalCount 5` | n/a |
| `tail -n 5 file` | `Get-Content file -Tail 5` | n/a |
| `env` | `Get-ChildItem Env:` | `set` |
| `export VAR=x` | `$env:VAR = "x"` | `set VAR=x` |
| `chmod +x` | n/a (ACL distinto) | n/a |
| `ps` | `Get-Process` (`ps`) | `tasklist` |
| `kill PID` | `Stop-Process -Id PID` | `taskkill /PID PID` |
| `curl url` | `Invoke-WebRequest url` (`curl`,`iwr`) | n/a |
| `2>/dev/null` | `2>$null` | `2>nul` |

## Gotchas
- PS `cd` con espacios necesita comillas: `cd "C:\Program Files"`.
- `find` en cmd ≠ `find` Unix; para grep usar `findstr` (cmd) o `Select-String` (PS).
- `2>&1` en PS sobre ejecutables nativos envuelve stderr como ErrorRecord; preferir capturar stdout sin redirección.
- WSL (si está instalado, `wsl --status`): para Linux real, `wsl <comando>` (ej. `wsl ls /tmp`).

## Vía la tool `terminal`
```
terminal(action="run", command="powershell", args=["-NoProfile", "-Command", "Get-Process | Select -First 5"])
terminal(action="run", command="tasklist", args=["/FO", "CSV", "/NH"])   # directo, shell=False
```
Cap de output: 6000 chars stdout / 3000 stderr. Si necesitás más, persistir a archivo y leer con `filesystem.read`.
