# Followup Log — Carter Agent
- Sesión: 2026-05-15 (autónoma nocturna, continuación)
- Disparador: hallazgos del smoke test 50/50 (`audit/smoke_summary.md`)
- Reglas: igual que la sesión anterior. NO se hace git.

---

## Fix #1 — Schema sync (CC-106 / T2-004 / T2-005 / T2-008)

**Hallazgo**: durante la sesión de fixes anterior, varios parámetros nuevos se añadieron a las
implementaciones de las tools pero NO al `COMPOUND_TOOL_SCHEMAS`. Con `additionalProperties=false`
el dispatcher rechazaba los args como "unexpected argument", y el LLM no veía los parámetros
en su catálogo. El smoke test lo detectó (2 fails en `gui`, hallazgo #1 del summary).

### Cambios

- `gemma4_agent/tools.py:3450` — schema `gui`:
  - Añadido `"monitor": {"type": "string"}` (CC-106).
  - Añadido `"raw_sendkeys": {"type": "boolean"}` (T3-010 — escape de SendKeys metachars).
  - Description actualizada: explicita `screen_x/screen_y` vs `center_x/center_y`, `monitor='primary|all|<index>'`, comportamiento de escape de SendKeys.
- `gemma4_agent/tools.py:3455` — schema `filesystem`:
  - Añadido `"max_bytes": {"type": "integer"}` (T2-004 diff, T2-005 archive).
  - Añadido `"max_files": {"type": "integer"}` (T2-005 archive).
  - Description actualizada: menciona gate duro de `delete`, semántica de `overwrite=false` y caps de `diff`/`archive`.
- `gemma4_agent/tools.py:3504` — schema `terminal`:
  - Añadido `"max_stdout_chars": {"type": "integer"}` (T2-008).
  - Añadido `"max_stderr_chars": {"type": "integer"}` (T2-008).
  - Description actualizada: explicita `shell=False` por defecto, gate duro, validación de cwd, log a `captures_dir`.

### Resultado

- Modo A: **137/141 pass** (de 135/141), los 2 fails de `gui` pasan.
- LLM ahora puede emitir `gui(action=screenshot, monitor='primary')` cuando el usuario pide "monitor principal".

---

## Fix #2 — Pre-validation hook (UX classifier vs gate duro)

**Hallazgo**: el `safety.classify_tool_call` corría ANTES de validaciones de input específicas
(formato de hora, zip-slip). Resultado UX subóptimo: el usuario veía `needs_confirmation` para
un alarm con `time='garbage'` o un restore de zip envenenado, en vez de un error claro.

### Diseño

- Nuevo registry `_PRE_VALIDATORS: dict[str, Callable[[dict], dict|None]]` en `tools.py`.
- En `ToolRegistry.execute()`, después de la schema validation y antes del `classify_tool_call`,
  se busca un pre-validator para el tool name. Si devuelve un `_err(...)`, se short-circuit.
- Los pre-validators son pure functions que solo inspeccionan args; no tocan estado.

### Pre-validators implementados

- `_prevalidate_notification(args)`:
  - Para `alarm_create`/`reminder_create`/`timer_start`/`toast_schedule`:
  - Si `seconds`/`minutes` están: pass-through.
  - Si `time`/`due` matchea `HH:MM` o `datetime.fromisoformat`: pass-through.
  - Caso contrario: retorna `needs_user` con mensaje claro de formato esperado.
- `_prevalidate_backup_sync(args)`:
  - Para `restore` con `path` y `dst` válidos:
  - Abre el zip y verifica containment de cada entry (mismo check que `_backup_restore`).
  - Si encuentra zip-slip: retorna `failed` ANTES del classifier. El usuario no necesita confirmar un zip envenenado; necesita saber que el zip está mal.

### Resultado

- Modo A: **143/143 pass** (smoke tests actualizados; 2 nuevos casos para confirmed=True).
- Verificación end-to-end:
  - `notification.alarm_create(time='garbage')` → `needs_user` SIN confirmation.
  - `backup_sync.restore` con `../../escape.txt` → `failed` SIN confirmation.
  - `notification.alarm_create(time='07:30')` → `needs_confirmation` (sigue gated por classifier, correcto).
- Tests del repo: **71/71 pass** (incluso `test_g6_active_phrase_triggers_returns_enabled` que ya había sido arreglado en sesión anterior con `safety_enabled=False`).

---

## Verificación final

- `python -m py_compile gemma4_agent/_ps.py gemma4_agent/state.py gemma4_agent/tools.py gemma4_agent/domain_tools.py gemma4_agent/ops_tools.py` → OK.
- `python audit/smoke_mode_a.py` → 143/143 PASS, 6/6 anti-bypass PASS, 0 fail.
- `python -m pytest gemma4_agent/test_*.py` → 71 passed.

### Anti-bypass confirmado (no degradado)

Los gates duros siguen siendo inviolables:
- `_internal_safe`, `routine_context`, `confirmed_at_create` desde args → filtrados.
- Solo `confirmed=true` (legítimo, lo añade el flujo de safety/form_filler/usuario) pasa.

---

## Pendientes (no urgentes)

Quedan los pendientes documentados en `audit/fix_notes.md` y `audit/smoke_summary.md`:

1. **T2-backup_sync-no-checkpoint-022** (PARTIAL): dst-tree snapshot pre-overwrite. ~80 líneas.
2. **T3-smart_home-rollback-incomplete-032** (SKIPPED): snapshot entity completo (brightness/color).
3. **T3-uia-no-thread-affinity-013** (SKIPPED): long-lived PowerShell host.
4. **Modelo grande en llama-server**: actualmente Gemma-4-E4B-Q6 (chico). Para mejor adherencia
   a tool_calls en multi-turn, levantar Gemma 4 26B A4B IQ4_XS.
5. **Prompt #31 / #19 Modo B**: el modelo eligió `browser`/`app` en lugar de `web`/`package`.
   No es bug — es decisión razonable del modelo. Considerar mejorar las descriptions para
   sesgar mejor la selección si causa problemas.

Sesión cerrada sin tocar git.
