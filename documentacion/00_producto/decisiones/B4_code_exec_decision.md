# B4 (code-exec sandbox) — Decisión de seguridad (2026-05-29)

## Veredicto
**NO se implementa un "sandbox" de ejecución de código arbitrario** — porque NO se puede
garantizar en Windows sin VM/contenedor, y el propio backlog lo condiciona a esa garantía.
El VALOR que B4 perseguía (cómputo/datos rápido) YA está cubierto de forma segura.

## La spec y su gate (BACKLOG_competidores.md:73-80)
> B4 · Tool de EJECUCIÓN DE CÓDIGO sandboxeada (pandas/numpy). De: Open Interpreter,
> OS-Copilot, Mark-XXXIX. Qué: tool `python`/`analyze` para cómputo/datos sin screenshots.
> Cómo: sandbox real (RestrictedPython o subproceso aislado), timeout 20s, SIN red ni
> filesystem por defecto, whitelist de libs. **Gate: suite de inputs maliciosos
> (exfiltración, DoS `while True`, `__import__`, `open(/etc/passwd)`) → 0 escapes.
> Si no podemos garantizar el sandbox, NO hacer.**

El gate es explícito y duro: **0 escapes, o NO hacer.**

## Por qué 0-escapes NO es alcanzable aquí (investigado, no asumido)
Plataforma: Windows, Python 3.10, OSS/gratis, asistente local (4 GB VRAM).
- **Sin `resource`** (Unix-only): no hay `setrlimit` para CPU/memoria.
- **Sin Job Objects en el repo** (grep `JobObject`/`win32job` → 0): cap de memoria/CPU a nivel SO
  requeriría ctypes a la WinAPI, complejo y frágil; igual no aísla red/fs.
- **Sin RestrictedPython** ni lib de sandbox instalada.
- **Filesystem NO aislable** sin chroot/container: `open("C:/Users/...")` directo funciona.
- **Red NO aislable** en-proceso: `import socket`/`urllib` siguen disponibles.
- **AST-whitelist se bypassea** (el propio backlog lo dice): `getattr(__builtins__, ...)`,
  `hex(__import__)`, etc. Una heurística AST NO es un sandbox.
- **Memory bomb**: `[0]*10**10` consume RAM ANTES de que el timeout/taskkill mate el proceso.

Un sandbox con garantía real necesita **aislamiento a nivel SO** (Docker/WSL2 con red+fs
restringidos, límites de cgroups). Eso es pesado y fuera de scope para este producto.

## Por qué NO un "MVP igual" (subproceso + AST-check)
Sería un sandbox con escapes conocidos vendido como sandbox → **falsa seguridad**: el usuario
correría código creyéndolo aislado y un `open`/`socket`/obfuscación escaparía. CLAUDE.md
(seguridad + honestidad) y el gate del backlog lo prohíben. *Un sandbox malo es peor que ninguno.*

## El VALOR de B4 YA está cubierto (de forma SEGURA)
B4 buscaba "cómputo/datos sin screenshots" (ej. "tabulá ese CSV" → ~0.8s vs ~3s de visión). Eso
ya lo dan, SIN ejecución de código arbitrario:
- **`data_analysis`** (domain_tools/data_analysis.py): csv_profile/describe/query/head/to_xlsx +
  plots. Usa pandas con `df.query()` (engine numexpr, rechaza `@`/backticks) — operaciones de
  datos seguras, **sin eval/exec**.
- **`file_process`** (B6, 2026-05-29): entrada única que detecta CSV/XLSX → delega a data_analysis.
- **`terminal`** (con hard-gate `confirmed=True`): para el caso "correr un comando/script" arbitrario
  el usuario YA tiene una vía explícita y confirmada (misma clase de riesgo que un code-exec).

## Si se revisita en el futuro
La vía correcta es aislamiento a nivel SO: ejecutar el código en **WSL2/Docker** con red y fs
bloqueados + límites de recursos (cgroups), no un AST-jail dentro de Windows. Recién con eso se
puede pasar la suite de "0 escapes" y cumplir el gate del backlog.

## Estado
B4 = **decidido NO implementar como sandbox** (gate de seguridad no satisfacible). Valor cubierto
por data_analysis + file_process. Es la decisión que el propio backlog manda ("si no podemos
garantizar el sandbox, NO hacer").
