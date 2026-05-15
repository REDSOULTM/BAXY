---
name: windows-commands
triggers: ["comando", "como ejecuto", "cómo ejecuto", "como corro", "cómo corro", "terminal", "shell", "powershell", "cmd", "bash", "wsl", "linea de comando", "línea de comando"]
priority: medium
---

# Windows commands cheatsheet

Equivalencias rápidas para responder al usuario cuando pregunta cómo hacer
algo en línea de comando. **Default en Windows 11**: PowerShell, no cmd.

## Equivalencias bash ↔ PowerShell ↔ cmd

| bash | PowerShell | cmd |
|---|---|---|
| `ls` | `Get-ChildItem` (alias `ls`, `dir`) | `dir` |
| `cat file` | `Get-Content file` (alias `cat`, `gc`) | `type file` |
| `pwd` | `Get-Location` (alias `pwd`, `gl`) | `cd` |
| `cd /path` | `Set-Location /path` (alias `cd`) | `cd /d` |
| `rm file` | `Remove-Item file` (alias `rm`, `del`) | `del file` |
| `rm -rf dir` | `Remove-Item -Recurse -Force dir` | `rmdir /s /q dir` |
| `cp src dst` | `Copy-Item src dst` (alias `cp`) | `copy src dst` |
| `mv src dst` | `Move-Item src dst` (alias `mv`) | `move src dst` |
| `mkdir -p path` | `New-Item -ItemType Directory -Force path` | `md path` |
| `which cmd` | `Get-Command cmd` o `(gcm cmd).Source` | `where cmd` |
| `grep pattern file` | `Select-String pattern file` (alias `sls`) | `findstr pattern file` |
| `wc -l file` | `(Get-Content file \| Measure-Object -Line).Lines` | `find /c /v "" file` |
| `head -n 5 file` | `Get-Content file -TotalCount 5` | n/a |
| `tail -n 5 file` | `Get-Content file -Tail 5` | n/a |
| `env` | `Get-ChildItem Env:` | `set` |
| `export VAR=x` | `$env:VAR = "x"` | `set VAR=x` |
| `chmod +x` | n/a (ACL diferente) | n/a |
| `ps` | `Get-Process` (alias `ps`) | `tasklist` |
| `kill PID` | `Stop-Process -Id PID` | `taskkill /PID PID` |
| `curl url` | `Invoke-WebRequest url` (alias `curl`, `iwr`) | n/a |
| `2>/dev/null` | `2>$null` | `2>nul` |

## Gotchas comunes

- En PowerShell, `cd path` con espacios necesita **comillas**: `cd "C:\Program Files"`.
- `find` en cmd ≠ `find` Unix. Para grep usar `findstr` (cmd) o `Select-String` (PS).
- `2>&1` en PS sobre ejecutables nativos envuelve stderr como ErrorRecord;
  preferir capturar stdout normalmente sin redirección.
- WSL: si el usuario quiere Linux real, `wsl <comando>` (ej. `wsl ls /tmp`).
  Solo si WSL está instalado (`wsl --status`).

## Ejecutar comandos vía la tool `terminal`

```
terminal(action="run", command="powershell", args=["-NoProfile", "-Command", "Get-Process | Select -First 5"])
```

o más directo con shell=False:

```
terminal(action="run", command="tasklist", args=["/FO", "CSV", "/NH"])
```

El cap de output del terminal es 6000 chars stdout / 3000 chars stderr; si
necesitás más, persistir a archivo y leerlo con `filesystem.read`.
