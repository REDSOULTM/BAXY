# PROMPT — Sprint 0 + Sprint 1 (correr esta noche, secuencial)

> Copiá el bloque de abajo y pegalo a un Claude Code que arranque en
> `c:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\`. Está
> diseñado para correr 6-10h sin intervención y dejar el repo verde a
> la mañana.

---

## Prompt completo (copy/paste)

```
Sos un agente de refactor autónomo. Vas a ejecutar Sprint 0 + Sprint 1 del
plan de la auditoría que ya está en docs/architecture/08_findings.md
sección §7. Trabajás en la rama actual (la que esté checkouteada al
arrancar). Hacé commits chicos por cada tarea para que cualquier
problema sea fácil de revertir.

# REGLAS GENERALES
1. NO toques nada que no esté en la lista explícita de abajo. Si en el
   camino ves otra deuda interesante, anotala en
   docs/architecture/sprint_prompts/_overnight_log.md y SEGUÍ.
2. Antes de tocar cualquier archivo, leelo entero. Antes de borrar nada,
   verificá con grep que nada lo importe.
3. Después de CADA tarea: git add + git commit con mensaje
   "sprint{0|1}: <tarea>" + 2-3 líneas explicando el qué y el por qué.
4. Si una tarea falla (test rojo, import roto, etc.): revertí la tarea
   completa con git reset --hard HEAD~1, anotá el blocker en
   _overnight_log.md y pasá a la siguiente. No dejes el repo en estado
   roto.
5. Si el repo no tiene tests para el área, no inventes tests. Solo
   verificá que `python -c "import gemma4_agent"` sigue funcionando
   después de cada commit.
6. NUNCA hagas git push. NUNCA cambies de rama. NUNCA borres branches.
7. Si tenés dudas sobre si algo se usa, asumí "se usa" y NO lo borres.
   Anotá la duda en _overnight_log.md.

# CONTEXTO
- Auditoría completa en docs/architecture/00_inventory.md → 08_findings.md
- El plan de sprint está en 08_findings.md §7.
- Findings detallados en 08_findings.md §1-4 (CRITICAL/HIGH/MED/LOW).
- _findings_seed.md tiene el seed crudo si querés contexto extra.

# WORKFLOW

## SPRINT 0 — Infra crítica (estimado 30-60min)

### 0.1 Crear requirements.txt desde imports reales
- Escaneá todos los imports externos (no stdlib) en gemma4_agent/*.py y
  gemma4_agent/voice/*.py + gemma4_agent/ui/*.py + gemma4_agent/scripts/*.py.
- Usá pip freeze del entorno actual (si está disponible) para versionar.
- Si pip freeze no tira nada útil, usá versiones >= sin pin estricto.
- Resultado: requirements.txt en la raíz del repo (no dentro de
  gemma4_agent/).
- Agregá comentarios sobre el grupo: "# voice stack", "# LLM stack",
  "# UI desktop", "# UI field (FastAPI)", "# data/storage", etc.
- Commit: "sprint0: add requirements.txt from real imports".

### 0.2 Crear pyproject.toml mínimo
- [project] name="gemma4_agent" version="0.1.0" requires-python=">=3.11"
- [project.scripts] gemma4-chat = "gemma4_agent.chat:main",
  gemma4-ui = "gemma4_agent.ui.app:main",
  gemma4-server = "gemma4_agent.server:main_entry"  (si existe, sino
  omitir esa línea),
  gemma4-launcher = "gemma4_agent.launcher:main".
- Verificá que cada entry point realmente exista con una función main().
- Si alguno no existe, NO lo inventes; documentá en _overnight_log.md y
  sacá esa línea.
- Commit: "sprint0: add pyproject.toml with entry points".

### 0.3 Verificación final del Sprint 0
- `python -c "import gemma4_agent"` debe seguir funcionando.
- Listar requirements.txt + pyproject.toml en _overnight_log.md.

## SPRINT 1 — Quick wins puros (estimado 2-4h)

Hacelos EN ESTE ORDEN. Cada uno con su propio commit.

### 1.1 Eliminar gemma4_agent/design_handoff_carter_field/
- Verificá primero con grep -r "design_handoff_carter_field" que nadie
  del paquete lo referencie.
- Si grep limpio: `git rm -r gemma4_agent/design_handoff_carter_field`.
- Si grep encuentra algo: NO lo borres, anotalo en _overnight_log.md y
  saltá esta tarea.
- Commit: "sprint1: remove Carter design handoff folder".

### 1.2 Limpiar strings "carter" en ui_field/src
- Archivos: ui_field/src/components/SettingsPanel.tsx, TopBar.tsx,
  ui_field/src/styles/prototype.css, ui_field/index.html.
- Reemplazá literal "carter" → "gemma4" en TEXTO VISIBLE solamente
  (labels, títulos, copys). NO toques nombres de variables, clases CSS,
  IDs de elementos ni paths.
- NO rebuilds (no `pnpm run build`). Solo edita fuentes.
- Commit: "sprint1: replace user-visible 'carter' strings in ui_field".

### 1.3 Eliminar 23 entries legacy del dict _impls en tools.py
- Editá gemma4_agent/tools.py, líneas 1561-1584 (el literal
  _impls = {...} en ToolRegistry.__init__).
- Eliminá ESTAS 23 entries (que son las que NO están en
  COMPOUND_TOOL_SCHEMAS — verificadas en Fase 7):
  "system_time", "list_processes", "list_windows", "app_search",
  "app_open", "app_close", "filesystem_list", "filesystem_read",
  "filesystem_write", "filesystem_search", "filesystem_delete",
  "web_open_url", "terminal_run", "clipboard_read", "clipboard_write",
  "gui_screenshot", "gui_click", "gui_type", "gui_keypress",
  "memory_save", "memory_recall", "memory_list", "memory_delete".
- IMPORTANTÍSIMO: los métodos `self.system_time`, `self.filesystem_list`,
  etc., SE QUEDAN (son helpers internos llamados por los compound
  t_*). Solo borrás las entries del dict.
- Verificá con grep: `grep -n "self\.app_open\|self\.filesystem_list"
  gemma4_agent/tools.py` debe seguir devolviendo matches (uso interno).
- Verificá con grep externo: `grep -rn 'execute("app_open"' gemma4_agent/`
  debe devolver vacío. Si devuelve algo, NO borres esa entry y anotá
  en _overnight_log.md.
- Commit: "sprint1: remove 23 legacy plain tools from ToolRegistry._impls
  (kept as internal helper methods)".

### 1.4 Colapsar ExperienceMemory.flag_grounding +
###     flag_grounding_by_turn en uno
- Archivo: gemma4_agent/experience.py:202-248.
- Crear método único:
  `flag_grounding(self, *, experience_id: int | None = None,
                  turn_id: str | None = None,
                  reason: str | None = None) -> dict[str, Any]`
- Exactamente uno de los dos (experience_id o turn_id) debe estar
  presente; si ambos None o ambos set, devolvé error.
- Internamente usa el query correcto según cuál vino.
- Mantené las 2 firmas viejas como wrappers deprecated que delegan al
  nuevo, con un comment `# deprecated, use flag_grounding(...)` para no
  romper callers (hay 1 en grounding_gate.py).
- O mejor: actualizá el caller en grounding_gate.py para usar la nueva
  firma y eliminá los 2 métodos viejos. Verificá con
  `grep -rn "flag_grounding\|flag_grounding_by_turn" gemma4_agent/`
  primero.
- Commit: "sprint1: collapse ExperienceMemory.flag_grounding_by_turn
  into flag_grounding".

### 1.5 Inline _ToolCallRecord (1-USER en mission_outcome.py)
- Archivo: gemma4_agent/mission_outcome.py:43-49.
- _ToolCallRecord es @dataclass(frozen=True) con 4 fields, usado solo
  dentro de compute_mission_outcome.
- Si el caller (gemma4_agent/agent.py) construye explícitamente
  _ToolCallRecord para pasarlo: PRIMERO inspeccionar el call site.
- Si NO se construye externamente y solo se usa interno: inline a
  list[tuple[str, dict, bool, VerifierOutcome|None]] o a un dict.
- Si SÍ se construye externamente: dejarlo, anotar en _overnight_log.md
  con la línea exacta donde se construye.
- Commit: "sprint1: inline _ToolCallRecord (if applicable)".

### 1.6 Mover _SSRFGuardRedirectHandler de tools.py a ops_tools.py
- Archivo origen: gemma4_agent/tools.py:1365 (la clase entera, ~30 LOC).
- Archivo destino: gemma4_agent/ops_tools.py (al inicio, después de los
  imports).
- Verificá los callers con grep: solo deberían ser web_read y
  download_tool en ops_tools.py (la clase se usa ahí porque es para
  SSRF guard en HTTP). Si hay caller en tools.py, agregá import desde
  ops_tools.
- Commit: "sprint1: move _SSRFGuardRedirectHandler to ops_tools where
  it's used".

### 1.7 ModelInfo: TypedDict → @dataclass(frozen=True)
- Archivo: gemma4_agent/model_info.py:21.
- Cambiar a:
  @dataclass(frozen=True)
  class ModelInfo:
      family: str
      params: str
      runtime: str
      quant: str
      size_bytes: int
      name_full: str
      context_size: int
      mmproj: bool
- Verificá que ningún caller use sintaxis dict (`info["family"]`).
  Buscar con: `grep -rn 'ModelInfo' gemma4_agent/` y leer cada uso.
- Si encontrás `info["family"]` o similar: convertí a `info.family`.
- Commit: "sprint1: convert ModelInfo from TypedDict to dataclass for
  consistency".

### 1.8 Routine + watcher runners → task_runner unificado
- Archivos: gemma4_agent/routine_runner.py + gemma4_agent/watcher_runner.py.
- Crear gemma4_agent/task_runner.py con:
  - argparse: --type {routine,watcher}, --id, --label (label solo para
    routine).
  - Internamente despacha al tool correcto.
- NO borres los archivos viejos todavía: convertirlos en wrappers de 5
  líneas que importan y llaman a task_runner.main() con el --type
  hardcoded. Esto preserva compatibilidad con los Scheduled Tasks de
  Windows que ya están registrados.
- Actualizá entry points en pyproject.toml si los tenías.
- Commit: "sprint1: unify routine_runner and watcher_runner under
  task_runner".

### 1.9 Borrar archivos scratch que dejé en el repo
- Verificá si quedaron archivos `_*.py`, `_*.json`, `_*.err`,
  `_*.md` (no en docs/) en gemma4_agent/ raíz: scanners de inventario
  que escribí durante la auditoría.
- Para cada uno: si el nombre empieza con `_inventory_`, `_depgraph_`,
  o `_tool_inventory`, son scratch y se borran.
- Commit: "sprint1: remove auditing scratch files".

### 1.10 Final del Sprint 1
- `python -c "import gemma4_agent"` debe seguir funcionando.
- `python -m gemma4_agent.launcher status` debe ejecutar sin trace
  fatal (puede fallar por server caído, eso está bien — solo verificá
  que parsea argumentos y no crashea al importar).
- Total LOC ahorradas: contá con `git diff --shortstat main` (o la rama
  base) y anotá en _overnight_log.md.

## REPORTING

Al terminar todo (o cuando te bloquees), creá/actualizá
docs/architecture/sprint_prompts/_overnight_log.md con:
- Timestamp de inicio y fin.
- Lista de tareas hechas (con SHA del commit).
- Lista de tareas saltadas (con razón).
- Total LOC removidas (git diff --shortstat).
- Hallazgos nuevos no planeados.
- Cualquier blocker para Sprint 2/3/4 que detectes en el camino.
- Estado final del repo: `git log --oneline -20` + `git status`.

NO hagas git push. NO toques main. Dejame revisar a la mañana.

# QUE NO HAGAS

- NO crear PRs (no tenés acceso a GitHub).
- NO instalar dependencias nuevas (ya está el repo como está).
- NO ejecutar el agente real, ni el llama-server, ni los runners.
- NO tocar archivos en data/, ~/.gemma4/, captures/, logs/, models/.
- NO refactorizar god classes (eso es Sprint 4).
- NO tocar voice/, mission_goal.py, mission_outcome.py, verifiers.py,
  verify_core.py (probados, frágiles).

Arrancá.
```

---

## Notas para vos al despertar

1. **Revisá `_overnight_log.md` PRIMERO** — ahí está el resumen de qué hizo, qué saltó, qué encontró nuevo.
2. **Revisá `git log --oneline`** — los commits de Sprint 0 + 1 deberían ser ~12 commits chicos (no uno gigante).
3. **Si algo está raro:** `git log` te muestra los SHAs; podés revertir tarea por tarea con `git revert <sha>`.
4. **Si quedó todo bien:** dejá ese branch como está y arrancá Sprint 2 con un prompt nuevo.

## Por qué quedó solo Sprint 0 + Sprint 1 esta noche

- **Sprint 2** necesita **datos reales de telemetría** que vienen de uso (días, no horas). No es overnight.
- **Sprint 3** necesita **tests** para refactorizar boundaries sin romper. Hay que escribirlos primero, y eso es trabajo de día con vos validando contratos.
- **Sprint 4** (god classes) es directamente refactor de semanas con tests primero.

Los tres siguientes los lanzás mañana con prompts dedicados cuando estemos los dos despiertos.
