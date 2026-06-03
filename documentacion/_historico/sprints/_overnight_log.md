# Overnight Sprint 0 + 1 — Log

- **Started:** 2026-05-16 (PortandoLoMejor branch)
- **Finished:** 2026-05-16, same session
- **Operator:** Claude Code (Opus 4.7)
- **Base commit:** aa99458 `fix(streaming): Tab navigation universal...`
- **Final commit:** db1dfe6 `sprint1: unify routine_runner and watcher_runner...`
- **Net delta:** 23 files changed, 201 insertions(+), 4084 deletions(-) → **-3883 LOC**

## Pre-flight setup

- Working tree arrancó dirty (17 `M`, decenas de `??`). Para garantizar
  commits chicos y revertibles por tarea: `git stash push -u -m
  "pre-overnight-sprint-2026-05-16"`. Stash queda sin aplicar; el user
  decide al despertar.
- **Consecuencia:** los archivos `gemma4_agent/docs/architecture/`
  (incluído `08_findings.md` y `sprint_prompts/sprint_0_and_1_tonight.md`)
  están dentro del stash, no en HEAD. Este log se creó en
  `docs/architecture/sprint_prompts/_overnight_log.md` (raíz del repo) —
  ruta paralela. Al unstashear, va a quedar la versión de raíz Y la del
  paquete co-existiendo; el user decide cuál mantener.

## Sprint 0 — Infra crítica

### 0.1 requirements.txt — commit 123d2c2

Scaneé top-level imports con AST sobre `gemma4_agent/**.py`. 40 paquetes
externos detectados, agrupados por tema (voice / LLM / UI desktop /
UI field / data / docs / DB / IoT / win32). Versiones pineadas a
`pip freeze` del venv activo donde aplica; `>=` para 5 paquetes no
instalados acá (psycopg, pymysql, paho-mqtt, pdfplumber, pynvml).

### 0.2 pyproject.toml — commit d914beb

PEP 621 mínimo + 4 console_scripts:
- `gemma4-chat → gemma4_agent.chat:main` ✓
- `gemma4-ui → gemma4_agent.ui.app:main` ✓
- `gemma4-server → gemma4_agent.server:main` (desvio: el prompt pedia
  `server:main_entry` pero esa función no existe; sí existe `main()`)
- `gemma4-launcher → gemma4_agent.launcher:main` ✓

### 0.3 Verificación

- `python -c "import gemma4_agent"` ✓
- `requirements.txt` + `pyproject.toml` en raíz ✓

## Sprint 1 — Quick wins

### 1.1 Borrar design_handoff_carter_field/ — commit 571047b ✅

Grep limpio (0 referencias en el paquete). `git rm -r`. **−3980 LOC.**

### 1.2 Strings "carter" en ui_field — commit 3035b54 ✅

4 reemplazos user-visible (`carter` → `gemma4`) en:
- `index.html:6` `<title>field · carter</title>`
- `SettingsPanel.tsx:889` ‘local ai agent · carter build · …’
- `SettingsPanel.tsx:894` `<span className="v">carter · 2026.05</span>`
- `TopBar.tsx:72` `<span className="v">carter</span>` (build chip)

Dejado intacto: `prototype.css:1189` comment `ADDENDUM (carter port)` —
no es label/title/copy visible. No rebuilds (dist/ intacto, per prompt).

### 1.3 23 entries legacy en ToolRegistry._impls — commit 84bf4a7 ✅

Borradas exactamente las 23 entries listadas (system_time, list_processes,
list_windows, app_search, app_open, app_close, filesystem_{list,read,
write,search,delete}, web_open_url, terminal_run, clipboard_{read,write},
gui_{screenshot,click,type,keypress}, memory_{save,recall,list,delete}).

Pre-flight grep confirmó **cero** call sites externos por nombre
(`execute("…")` y `_impls["…"]`). Los métodos helpers que el dict
referenciaba (self.app_open, self.filesystem_list, …) SE QUEDAN — 21
llamadas internas desde compounds `t_*` siguen usándolos.

### 1.4 Colapsar flag_grounding_by_turn — SKIPPED

`grep -rn "flag_grounding"` devuelve **vacío** en HEAD y en el stash.
El método al que apunta el prompt (experience.py:202-248) no existe en
el código actual. Probablemente forma parte de trabajo aún no commiteado
fuera de esta rama. **Nada que hacer.**

### 1.5 Inline _ToolCallRecord — SKIPPED

Dos razones independientes para no tocar:

1. **Caller externo confirmado**: `gemma4_agent/test_mission_goal.py`
   importa `_ToolCallRecord` en la línea 15 y lo construye en tres tests
   (líneas 257, 264, 271). El prompt indica: "Si SÍ se construye
   externamente: dejarlo, anotar".
2. **mission_outcome.py está en la lista QUE NO HAGAS** del propio
   prompt overnight (tests frágiles).

### 1.6 Mover _SSRFGuardRedirectHandler — SKIPPED

Premise del prompt incorrecto: dice que la clase se usa en
`web_read` y `download_tool` dentro de `ops_tools.py`, pero el grep
devuelve **0** referencias en `ops_tools.py`. La clase y su único caller
(`_http_get_text` en `tools.py:1383`) viven en el mismo módulo. Moverla
sería una regresión (introduce import cross-module gratuito).

### 1.7 ModelInfo TypedDict → frozen dataclass — commit d0a78ea ✅

Conversión limpia. Único consumidor Python es `server.py`, dos call sites:
- `GET /model`: ahora `return asdict(info)` (en vez de `return info`).
- websocket initial snapshot: `json.dumps({…info: asdict(info)})`.

`import asdict` agregado a server.py. JSON shape verificado byte-idéntico
al previo via `json.dumps(asdict(mock_model_info()))`. La TS `interface
ModelInfo` en `ui_field/src/types.ts` no requiere cambio.

### 1.8 Unificar routine_runner + watcher_runner → task_runner — commit db1dfe6 ✅

Nuevo módulo `task_runner.py` (88 LOC) con:
- argparse `--type {routine, watcher} --id --label`
- helper privado `_build_registry()` (factoriza el setup compartido)
- `_run_routine(args)` y `_run_watcher(args)` para el dispatch

Los dos legacy `routine_runner.py` / `watcher_runner.py` se reescribieron
como wrappers de 15 líneas que prepend `--type routine|watcher` a
`sys.argv[1:]` y llaman `task_runner.main(...)`. Esto preserva los
Scheduled Tasks de Windows ya registrados (invocan los módulos por nombre
exacto via `python -m gemma4_agent.routine_runner` /
`python -m gemma4_agent.watcher_runner`).

Routing verificado:
- `python -m gemma4_agent.routine_runner` → "error: --id or --label
  required for --type routine"
- `python -m gemma4_agent.watcher_runner` → "error: --id required for
  --type watcher"

### 1.9 Borrar scratch files de auditoría — SKIPPED

No existen archivos `_inventory_*`, `_depgraph_*` ni `_tool_inventory*`
en `gemma4_agent/` root. El único archivo `_*.py` ahí es `_ps.py`, que
es código de producción (helpers PowerShell, no scratch). Nada para
borrar.

## Final state

- `python -c "import gemma4_agent"` ✓
- `python -m gemma4_agent.launcher status` corre limpio: muestra server
  online, modelo cargado, llama-server OK, 64 compound schemas (consistente
  con la limpieza de 1.3).
- Branch `PortandoLoMejor` con 6 commits nuevos sobre `aa99458`, ningún
  push. Stash `pre-overnight-sprint-2026-05-16` intacto para que el user
  decida al despertar.

## Findings nuevos / observaciones

1. **Stash co-existence problem**: el dir `gemma4_agent/docs/architecture/`
   (donde vive `08_findings.md` y `_findings_seed.md`) está en el stash,
   no en HEAD. Cuando el user re-aplique el stash, va a tener este log
   en `docs/architecture/sprint_prompts/_overnight_log.md` (root) **Y** los
   findings en `gemma4_agent/docs/architecture/`. Probablemente quiera
   moverlos todos a `docs/architecture/` (root) o todos a
   `gemma4_agent/docs/architecture/` para no duplicar la jerarquía.

2. **Stale prompt assumptions (3 tareas saltadas)**: 1.4, 1.5 (parcial),
   1.6 y 1.9 apuntaban a código/archivos que no existen en HEAD. Sugiere
   que el prompt fue redactado a partir de findings de una versión
   distinta del repo, o que pre-supone que las tareas dirty (17 M en el
   stash) ya estuvieran commiteadas. Si las tareas 1.4 y 1.6 son
   importantes, hay que correrlas después de unstashear.

3. **CRLF warnings**: git muestra "LF will be replaced by CRLF" en cada
   archivo escrito por este sprint. Es comportamiento normal en Windows
   con `core.autocrlf=true`, no es un problema.

4. **Test coverage gap detectada (no actuada)**: `test_mission_goal.py`
   importa el nombre privado `_ToolCallRecord` de `mission_outcome.py`.
   Esto convierte un detalle de implementación en API pública. Cuando
   alguien quiera refactorizar `mission_outcome.py` en Sprint 3+, va a
   tener que tocar también ese test. Worth keeping in mind.

## Blockers para Sprint 2/3/4

- Sprint 2 (telemetría): nada cambió que lo afecte.
- Sprint 3 (boundaries con tests): la situación de `_ToolCallRecord`
  arriba sugiere que conviene auditar imports de nombres `_privados` en
  los tests del paquete antes de empezar el refactor.
- Sprint 4 (god classes): la limpieza de `tools.py:_impls` deja el dict
  ahora con sólo entries `t_*` compound, lo cual prepara mejor el terreno
  para extraer ToolRegistry. Buen anticipo accidental.

## Recap de commits

```
123d2c2 sprint0: add requirements.txt from real imports
d914beb sprint0: add pyproject.toml with entry points
571047b sprint1: remove Carter design handoff folder
3035b54 sprint1: replace user-visible 'carter' strings in ui_field
84bf4a7 sprint1: remove 23 legacy plain tools from ToolRegistry._impls
d0a78ea sprint1: convert ModelInfo from TypedDict to frozen dataclass
db1dfe6 sprint1: unify routine_runner and watcher_runner under task_runner
```

(More to come: this log itself will land in one final commit.)
