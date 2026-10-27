# Configuración de Claude Code para BAXY

Ley 1 aplicada al propio entorno de trabajo: primero lo que ya existe (oficial de Anthropic o público y
mantenido), y sólo se construye lo que nada cubre. Todo sale de dos fuentes: los mensajes del dueño en las
sesiones del PC y del notebook (septiembre y octubre de 2026: lo que más se repitió, corrigió o se perdió
tras compactar) y una búsqueda en GitHub y la documentación oficial. `AGENTS.md` y
`documentacion/00_IDENTIDAD.md` siguen mandando. Nada de esto toca el producto.

## Heredado

| Pieza | De dónde | Para qué en BAXY |
|---|---|---|
| plugin `pr-review-toolkit` (`/pr-review-toolkit:review-pr` y 6 agentes: code-reviewer, silent-failure-hunter, pr-test-analyzer, type-design-analyzer, comment-analyzer, code-simplifier) | `anthropics/claude-plugins-official` | revisión de cambios; los agentes leen `CLAUDE.md` → `AGENTS.md` |
| plugin `claude-md-management` (`/revise-claude-md`, `claude-md-improver`) | ídem | que lo aprendido en cada sesión quede escrito |
| plugin `project-artifact` | ídem | la página de progreso que se actualiza (el «¿cómo vas?» de cada día) |
| skill `verification-before-completion` | `obra/superpowers` (MIT, `skills/LICENSE-superpowers.txt`) | nunca «listo» sin evidencia fresca |
| skill `systematic-debugging` | ídem | causa raíz antes de arreglar; nada de parches |

Los tres plugins no traen hooks ni servidores MCP; están activados en `settings.json` con alcance de proyecto.

## Construido (porque nada público lo cubría)

| Pieza | Por qué |
|---|---|
| hook `hooks/contexto.py` (SessionStart) | Al arrancar: fecha con día, máquina, worktree, rama y commit (hubo errores de fecha y de rama). Tras compactar o retomar: **todos** los mensajes del dueño de la sesión, leídos del transcript, los recientes en contexto (tope de 10.000 caracteres del hook) y la lista entera en `.claude/sesiones/<sesión>.md`, local y fuera de git. Es el patrón que la guía oficial de hooks recomienda (`SessionStart` con `compact`); no había script público que lo hiciera en local. |
| hook `hooks/baxy_guard.py` (PreToolUse/PostToolUse) | Deniega lo que ya rompió algo: `--no-verify`, `git stash`, `reset --hard`, `clean -f`, push forzado o a GitHub, descartar el árbol, servicios o arranque de Windows (msconfig), matar procesos por nombre (cerró VS Code), reiniciar o apagar. Avisa si `AGENTS.md` pasa de 10.000 caracteres o si se toca configuración de calidad. |
| regla `rules/trabajo.md` (siempre cargada, sobrevive a la compactación) | La forma de trabajar que el dueño más repitió: autonomía, confirmar sólo lo peligroso, no esperar, evidencia, soluciones generales, ramas, procesos por PID, informes en español con cifras. |
| reglas `rules/python.md`, `csharp.md`, `fieldui.md` | Lo de cada lenguaje en BAXY (stdout es el protocolo de la mente, warnings como errores, accesibilidad). |
| skills `verificar`, `arreglar-fallo`, `arreglar-build` | La escalera de validación con los comandos reales de esta máquina; se apoyan en las dos de superpowers. |
| skill `traspaso` | Handoff en el repo y el prompt o `/goal` para la sesión siguiente o la otra máquina (pedido más de ocho veces; límite de 4.000 caracteres de `/goal`). |
| skill `prueba-en-vivo` | Seguridad de las pruebas de escritorio (incidentes: msconfig, juegos abiertos, llama-server huérfanos). |
| skill `coordinar-pc-nb` | Buzón, reparto, hub y el chequeo de privacidad antes de un push. |
| skill `lanzar-baxy` | «Lanza BAXY» con `scripts\run_renew.cmd` y comprobando que arrancó. |
| agente `revisor-privacidad`, comando `/limpiar-muerto` | Lo que el toolkit oficial no mira: que no salga nada de la persona; ley 5. |

## Instalado con el sí del dueño (2026-10-26)

**context-mode** (`mksglu/context-mode`, ELv2): saca las salidas largas del contexto y guarda la sesión en SQLite
local para restaurarla tras compactar. El dueño lo aprobó sabiendo lo que hace: añade un hook de reparación al
`~/.claude/settings.json` global, guarda mensajes y salidas en claro bajo `~/.claude/context-mode/` (7 días),
consulta npm cada hora y reescribe algunos comandos (`curl`, `fetch` en línea, `gradle`) y los prompts de los
subagentes. Sólo enviaría eventos fuera si existiera `%APPDATA%\context-mode\platform.json`: no debe crearse.
Convive con `contexto.py`: context-mode recupera lo relevante por búsqueda; `contexto.py` garantiza los mensajes
del dueño literales. Diagnóstico: `/context-mode:ctx-doctor`.

**LSP oficiales** `csharp-lsp`, `pyright-lsp`, `typescript-lsp`: Claude navega el código por símbolos
(definiciones, referencias, diagnósticos) en vez de leer ficheros enteros. Necesitan en cada máquina
`dotnet tool install --global csharp-ls --add-source https://api.nuget.org/v3/index.json` y
`npm install -g pyright typescript-language-server typescript`.

Quitar cualquiera: `claude plugin uninstall <plugin> --scope project`; context-mode deja además
`~/.claude/context-mode/`, `~/.claude/hooks/context-mode-cache-heal.mjs` y su entrada en `~/.claude/settings.json`.

## Dónde está instalado (2026-10-26)

| Máquina | Sitio | Cómo |
|---|---|---|
| notebook | `D:\BAXYeval\wt\BAXY-Renew-arr-junto` (rama `nb-arr-junto`) | fusión de `nb-ecc`, versionado |
| notebook | `D:\BAXYeval\wt\BAXY-Renew-ecc` (rama `nb-ecc`, también en `hub`) | origen de la configuración |
| notebook | `D:\Perfil\Escritorio\ETC\Programacion\Baxy Renew\.claude` (carpeta de arranque de las sesiones, sin git) | copia de `.claude/` |
| PC | `C:\Users\usuario\Desktop\ETC\Programacion\BAXY-Renew\.claude` (rama `baxy-renew` del dueño) | copia de `.claude/`; git la ignora, el checkout no cambia |

En cada máquina: `csharp-ls` 0.28.0 (`dotnet tool`), `pyright`, `typescript-language-server` y `typescript`
(`npm -g`), y los plugins con alcance de proyecto. context-mode además quedó activado a nivel de usuario.
Una copia sin git se actualiza a mano, copiando `.claude/` desde `nb-ecc` (o desde `hub`).

Lección: con dos hooks `SessionStart` que devuelven `hookSpecificOutput.additionalContext` (el de context-mode y
el nuestro), sólo uno llegaba al modelo; `contexto.py` escribe texto plano y así llegan los dos.

## Revisado y descartado

- **claude-mem**: memoria alojada en su nube por defecto. **Continuous-Claude v3**: PostgreSQL y sin cambios
  desde enero. **claude-context** (Zilliz): por defecto manda el código a Zilliz y OpenAI.
- **everything-claude-code**: 28 hooks en Node que registran todo y escriben a nivel de usuario; reglas que
  chocan con `AGENTS.md`. **superpowers** entero: TDD obligatorio y subagentes por defecto.
- **security-guidance** (oficial): revisión con LLM en cada parada; lenta y cara. **hookify**: reglas locales
  sin versionar.

## Para consultar a demanda

- **ccusage**: informe local del consumo de cuota leyendo los transcripts (`npx ccusage@latest`).

## Cómo probarlo

```powershell
'{"tool_input":{"command":"git stash"}}' | python .claude\hooks\baxy_guard.py pre-shell   # JSON con "deny"
'{"source":"startup"}' | python .claude\hooks\contexto.py                                  # fecha, máquina, rama
```

`BAXY_GUARD=off` o `BAXY_CONTEXTO=off` al lanzar Claude Code apagan cada hook. Para quitarlo todo, se
revierten los commits de esta configuración y se desinstalan los tres plugins (`claude plugin uninstall
<plugin>@claude-plugins-official --scope project`).
