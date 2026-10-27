# Configuración de Claude Code para BAXY

Origen: [everything-claude-code](https://github.com/affaan-m/everything-claude-code) v2.2.3 (repo `affaan-m/ECC`),
commit `25278e7d7b6c`, MIT, © 2026 Affaan Mustafa (`LICENSE-ECC.txt`). Revisado entero el 2026-10-26 y
aplicado **adaptado**: `AGENTS.md` y `documentacion/00_IDENTIDAD.md` mandan sobre cualquier regla genérica
de ECC. Nada de esto toca el producto: sólo cambia cómo trabaja Claude Code en este repositorio.

## Qué hay

| Tipo | Nombre | De ECC | Para qué |
|---|---|---|---|
| hook | `hooks/baxy_guard.py` + `settings.json` | block-no-verify, config-protection | ver «Hooks» |
| agente | `revisor-codigo` | code-reviewer | revisión con filtro de confianza + los seis invariantes |
| agente | `revisor-python` | python-reviewer | mente; stdout es el protocolo |
| agente | `revisor-csharp` | csharp-reviewer | .NET Release, NUnit, providers |
| agente | `revisor-fieldui` | react-reviewer | React+TS en WebView2, accesibilidad |
| agente | `revisor-privacidad` | security-reviewer | exfiltración, efectos sin autorizar, rutas, procesos |
| agente | `cazador-fallos-silenciosos` | silent-failure-hunter | estados terminales honestos |
| agente | `explorador` | code-explorer | la exploración de sólo lectura que `AGENTS.md` permite |
| agente | `analizador-pruebas` | pr-test-analyzer | pytest/NUnit, un skip no es un pass |
| agente | `analizador-tipos` | type-design-analyzer | `Baxy.Contracts` y el catálogo |
| skill | `verificar` | verification-loop | la escalera de validación con los comandos de esta máquina |
| skill | `arreglar-fallo` | orch-fix-defect | prueba que falla → arreglo mínimo → verificar |
| skill | `arreglar-build` | build-fix + build-error-resolver | build verde sin callar avisos |
| skill | `traspaso` | save-session / resume-session | handoff con `docs/AI_HANDOFF_TEMPLATE.md` |
| skill | `python-testing`, `csharp-testing`, `react-patterns`, `frontend-a11y` | las mismas | referencia, con una «Nota BAXY» al principio |
| comando | `/revisar-cambio` | review-pr | revisores en paralelo, sólo si el dueño lo pide |
| comando | `/limpiar-muerto` | refactor-clean | ley 5, sin descargar herramientas |
| regla | `rules/python.md`, `csharp.md`, `fieldui.md` | rules/python, csharp, react, typescript | se cargan sólo al tocar esos ficheros |

Los agentes son de sólo lectura (salvo lo que su tarea diga), corren en `sonnet` y sus descripciones ya no
dicen «MUST BE USED / PROACTIVELY»: `AGENTS.md` dice que por defecto no se delega, así que se usan cuando el
dueño lo pide o vía `/revisar-cambio`. Su cuerpo es el de ECC sin las secciones que no aplican (Next.js,
ASP.NET, EF, Django, SQL, `npm audit`…) y con un bloque «Contexto BAXY» delante que manda sobre él.

## Hooks

Uno solo, en Python con librería estándar (funciona con el Python 3.10 del sistema; `py` no hace falta):

- **PreToolUse `Bash|PowerShell`** — deniega `--no-verify`/`--no-gpg-sign`, `git stash` (salvo
  `list`/`show`), `git reset --hard`, `git clean -f`, `git push --force`, `git checkout .`/`git restore .`
  (worktrees compartidos entre sesiones) y msconfig, `bcdedit`, `sc config|delete|stop`, `Set-Service`,
  `Stop-Service`, `reg add|delete|import HKLM` (incidente msconfig).
- **PostToolUse `Edit|Write|MultiEdit`** — no bloquea (la edición ya está hecha): avisa a Claude si
  `AGENTS.md` pasa de 10.000 caracteres o si se edita configuración de calidad (`ruff.toml`, `pytest.ini`,
  `Directory.*.props`, `global.json`, `eslint.config.js`, `tsconfig*.json`…).

Riesgos y límites: es una red, no una frontera — busca texto en el comando, así que hay falsos positivos
(un `--no-verify` dentro de un mensaje) y se esquiva con un script que haga lo mismo por dentro. No hay red,
no escribe ficheros, no lee prompts ni transcripciones. Si Python no está en el `PATH`, el hook falla y
Claude Code sigue (falla abierto). Escape: el dueño ejecuta el comando él mismo (prefijo `!`), o lanza
Claude Code con `BAXY_GUARD=off`.

## Qué se descartó y por qué

- **Los 28 hooks de ECC en Node.** Registran cada llamada de herramienta (hasta 5.000 caracteres de entrada y
  salida) y los comandos de shell en `~/.claude` y `~/.local/share` sin rotación, mandan extractos de la
  conversación a `claude -p` para resumir, pueden descargar `prettier`/`tsc` con `npx`, sondean servidores
  MCP y fallan cerrado, y GateGuard deniega la primera edición de cada fichero. Además exigen instalar
  ~45.000 líneas de JS en `~/.claude/` (nivel usuario). Lo útil para BAXY (bloquear `--no-verify`, proteger
  la configuración) cabe en `baxy_guard.py`.
- **MCP** (`chrome-devtools-mcp` por `npx` y la lista de `mcp-configs/`): descarga paquetes en cada arranque
  y varios piden claves de servicios externos; el puerto 9333 lo usan las pruebas de BAXY.
- **Reglas comunes** (`rules/common`): TDD obligatorio, 80 % de cobertura, conventional commits en inglés,
  delegar en agentes «inmediatamente», PRD antes de codificar. Chocan con `AGENTS.md`; lo aprovechable
  (filtro de confianza, checklist de calidad) va dentro de los agentes.
- **Agentes** `planner`, `architect`, `code-architect` (la arquitectura se queda en el hilo principal),
  `tdd-guide` (TDD obligatorio), `e2e-runner` (navegador web), `doc-updater` (codemaps: ya está
  `docs/AI_CONTEXT_MAP.md`), `refactor-cleaner` y `build-error-resolver` (sus flujos van como skill y
  comando en el hilo principal), `performance-optimizer`, `code-simplifier` (existe `/simplify`), y los de
  otros lenguajes y dominios (Go, Rust, Java, Kotlin, Flutter, Django, salud, marketing, redes…).
- **Skills**: de 311, el resto son de otros stacks o dominios, dependen de servicios externos, o duplican lo
  que BAXY ya tiene (memoria «continuous learning» con hooks, ADRs, onboarding, git workflow en inglés).
  `windows-desktop-e2e` (pywinauto) se descartó porque la propia skill excluye apps WebView2, que es BAXY.
- **Comandos** de sesiones/instincts en `~/.claude`, `multi-*`/`astra-review` (otros proveedores),
  `security-scan` (AgentShield por `npx`), `/plan` y `/code-review` (chocan con los de Claude Code), PM2,
  Jira, epics.
- **Instalador** (`install.ps1`/`install.sh`): instala a nivel usuario y hace `npm install`; no se ejecutó.

## Cómo probarlo

```powershell
# El hook, sin Claude: debe imprimir un JSON con "deny"
'{"tool_input":{"command":"git stash"}}' | python .claude\hooks\baxy_guard.py pre-shell
# Con Claude: pedirle que ejecute «echo probe --no-verify» → lo deniega la Guarda BAXY
claude -p "Run: echo probe --no-verify" --model haiku --allowedTools "Bash(echo:*)"
```

En una sesión: `/agents` lista los nueve agentes; `/revisar-cambio HEAD~1..HEAD` lanza la revisión.

## Cómo revertirlo

Todo vive en `.claude/` más las líneas de `.gitignore` y la sección de `CLAUDE.md` de este mismo commit:
`git revert <commit>` lo quita entero. Para apagar sólo el hook sin tocar el repo: `BAXY_GUARD=off`.
Nada se instaló a nivel usuario (`~/.claude`).
