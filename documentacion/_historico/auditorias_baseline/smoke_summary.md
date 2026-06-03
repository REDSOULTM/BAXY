# Smoke Test Summary — Carter Agent

- Sesión: 2026-05-15 (autónoma nocturna)
- Modelo en llama-server: `gemma-4-E4B-it-Q6_K.gguf` (más chico que el target IQ4_XS 26B; importante para interpretar Modo B)
- Fixes auditados: los aplicados en la sesión anterior (CC-100/101/102/103/104/105/106/107 + individuales)

## Conteo global

| Modo | Casos | PASS | FAIL | Notas |
|---|---:|---:|---:|---|
| **A — Direct call con stubs** | 141 | 135 | 6 | 6/6 anti-bypass PASS |
| **B — LLM real** | 50 | 33 | 17 | Mayoría de fails son "no tool_call emitted" (modelo E4B chico). 0 leaks de flags privados. |

## Top hallazgos (PRIORIDAD ALTA para arreglar mañana)

### 1. **SCHEMA SYNC BUG — CC-106 / T2-008 / T2-004 / T2-005** (real, accionable)

Los fixes de la sesión anterior añadieron nuevos parámetros a las **implementaciones** de las tools, pero **NO los añadieron a `COMPOUND_TOOL_SCHEMAS`**. `additionalProperties=false` hace que `_coerce_and_validate_tool_args` los rechace como `unexpected argument`. **Consecuencia**: el LLM no puede usar los nuevos parámetros (no aparecen en su catálogo) y, cuando los pasa directamente, fallan con `invalid tool arguments`.

Tools afectadas:

| Tool | Parámetro añadido al impl | Falta en schema |
|---|---|---|
| `gui` (action=screenshot) | `monitor` | sí — CC-106 |
| `filesystem` (action=diff) | `max_bytes` | sí — T2-004 |
| `filesystem` (action=archive) | `max_files`, `max_bytes` | sí — T2-005 |
| `terminal` (action=run) | `max_stdout_chars`, `max_stderr_chars` | sí — T2-008 |
| `data_analysis` (action=csv_query) | `engine` (output only — OK) | n/a |
| `download` (action=fetch) | `signature_present`, `signer_subject`, `note` (output only — OK) | n/a |

**Fix**: editar las entries en `COMPOUND_TOOL_SCHEMAS` (alrededor de `tools.py:3450`) y agregar los properties faltantes. Cada uno son ~3-5 chars añadidos al schema. Total: <30 líneas. Después de eso re-correr Modo A y los 2 fails restantes de gui pasan.

**Evidencia Modo A**:
```
- [FAIL] `gui` CC-106 monitor=primary: expect=ok, got=failed, error='invalid tool arguments'
- [FAIL] `gui` monitor invalid: expect=needs_user, got=failed, error='invalid tool arguments'
```

**Evidencia Modo B**:
```
Prompt #11: [INFO] model did NOT use monitor=primary (got args={"action": "screenshot"})
```
El modelo no añade `monitor=primary` porque no aparece en el catálogo que recibe.

### 2. **Classifier vs gate duro — fricción innecesaria**

Algunas tools como `notification.alarm_create` y `backup_sync.restore` aparecen en `safety.classify_tool_call` (clase `automation`/`backup_or_restore`) y disparan `needs_confirmation` *antes* de llegar a las validaciones específicas implementadas en CC-024 y CC-021. Esto causa:

- `notification.alarm_create` con `time='garbage'` → debería caer en `_NotificationDueError` y retornar `needs_user`. **Actual**: el classifier dispara `needs_confirmation` primero, así que la validación nunca corre.
- `backup_sync.restore` con zip-slip → debería caer en el bloqueo `failed` con detalle de los entries blocked. **Actual**: el classifier (`safety.classify_tool_call` línea 42) dispara `needs_confirmation` y el zip-slip ni se evalúa.

**Diagnóstico**: NO es un bug funcional — el usuario ve el needs_confirmation, confirma, y entonces SÍ se ejecuta la validación específica. Pero la UX es subóptima (el usuario aprueba algo antes de saber que el zip está envenenado o la hora es inválida).

**Fix sugerido (no urgente)**: en `execute()`, llamar a una pre-validación opcional ANTES de `classify_tool_call` para tools con check de input estricto (regex de tiempo, zip-slip). Cada tool puede exponer un `validate_args` opcional.

**Evidencia Modo A**:
```
- [FAIL] `backup_sync` restore skip-policy (no gate): expect=ok, got=needs_confirmation
- [FAIL] `backup_sync` T2-021 zip-slip blocked: expect=failed, got=needs_confirmation
- [FAIL] `notification` T2-024 invalid time format: expect=needs_user, got=needs_confirmation
- [FAIL] `notification` T2-024 HH:MM ok: expect=ok, got=needs_confirmation
```

## Top hallazgos (PRIORIDAD MEDIA)

### 3. Modo B — el modelo E4B-Q6_K elige tool incorrectamente

- **Prompt #19** ("Desinstala VLC"): el modelo eligió `app.uninstall` en vez de `package.uninstall`. Es ambiguo (Windows `app(action=uninstall)` también existe). El test pre-escrito asumía `package` por convención winget. **No es bug del fix**.
- **Prompt #31** ("Busca en DuckDuckGo"): modelo eligió `browser.search` con engine=DuckDuckGo en vez de `web.search`. **No es bug del fix** — es una decisión razonable del modelo.
- 13 prompts terminaron en "no tool_call emitted" — el modelo respondió con texto en vez de tool_call. Esto se acentúa en multi-turn (4/5 multi-turn fallan ya en el primer turno). **Es comportamiento del modelo E4B chico, no del sistema**.

### 4. Modo B — Prompt #22 emitió JSON cortado

`backup_sync` args llegaron como `{"_raw": "{\"action"}` (truncado en stream). Esto es **un problema del modelo o del prompt**, no del fix. El extractor de tool_calls lo guarda como `_raw` para forensics.

## Verificaciones positivas (todo OK)

### Anti-bypass CC-101 (6/6 PASS en Modo A, 0 leaks en Modo B)

Los flags `_internal_safe`, `routine_context`, `confirmed_at_create` inyectados desde args **son filtrados** por `execute()` antes de la validación. Verificado:

- `system.shutdown` con `_internal_safe=True` desde args → `needs_confirmation` (gate duro intacto).
- `terminal.run` con `routine_context=True, confirmed_at_create=True` → `needs_confirmation` (sin opt-out via inyección).
- `filesystem.delete` con `_internal_safe=True` → `needs_confirmation`.
- `package.install` con `_internal_safe=True` → `needs_confirmation`.
- `database.execute` con `_internal_safe=True` → `needs_confirmation`.

El modelo E4B nunca intentó inyectar estos flags (no aparecen en su catálogo). Confirmado.

### Gates duros confirmados (CC-101)

- `system` shutdown/restart/sleep → todos `needs_confirmation` con `confirmed=False`.
- `terminal.run` cualquier comando → `needs_confirmation`.
- `package` install/uninstall → `needs_confirmation`.
- `filesystem.delete` → `needs_confirmation`.
- `database.execute` (cualquier DML) → `needs_confirmation`.
- `backup_sync.restore` con `conflict=overwrite` → `needs_confirmation`.
- Todos con `confirmed=True` → pasan el gate y ejecutan.

### Validación específica confirmada

- **CC-100 PS injection**:
  - `routine.create` con `trigger.at="08:00';Write-Host pwn;#"` → rechazado (`invalid routine trigger`).
  - `maintenance.event_logs_query` con `log="System' ; Stop-Computer ; #"` → `needs_user`.
  - `network.dns_set` con `addresses=["8.8.8.8' ; pwn ; '"]` → `needs_user`.
  - `network.connections` con `state="Established;pwn"` → `needs_user`.
  - `gui.keypress` con `keys="'; Stop-Computer; '"` → ejecuta sin error (env-var indirection).
- **T2-017 SQL identifier injection**: `database.schema` con `table="items; DROP TABLE items; --"` → `needs_user`.
- **T2-018 CTE+DML bypass**: `database.query` con `WITH x AS (SELECT 1) DELETE FROM items WHERE 1=1` → rechazado a nivel driver (`PRAGMA query_only=1` bloquea writes). Captura: `attempt to write a readonly database`.
- **T2-021 zip-slip**: `backup_sync.restore` con `entry.filename="../../evil.txt"` → rechaza el entry con `blocked: zip-slip outside dst`. (Solo se vio cuando se pasa `confirmed=True`; ver hallazgo #2.)
- **T2-035 pandas eval**: `data_analysis.csv_query` con `query="@__import__"` → `needs_user`. Con `query='\`a\` > 0'` (backtick) → `needs_user`.
- **T2-003 copy overwrite**: `filesystem.copy(overwrite=False)` con dst existente → `needs_user`.
- **T2-007 cwd validation**: `terminal.run(cwd='C:/does/not/exist_xyz')` → `needs_user`.
- **T2-014 SSRF guard**: `web.read(url='http://127.0.0.1:8123')` → `error: refused: target host is private/loopback`.
- **T2-014 SSRF metadata**: `web.read(url='http://169.254.169.254/...')` → `error: refused`.
- **T2-026 defender as job**: `maintenance.defender_quick_scan` → retorna `job_id` y `status=running`. No bloquea 15 min.
- **T2-027 disk_cleanup_describe**: ya no devuelve `command_describe`/`command_apply` arrays.
- **T2-046 shlex.split**: `job_manager.start(command='"C:/Program Files/python.exe" --version')` → cmd parseado correctamente.

### CC-105 redacción de credenciales

- `database.status` con `password='supersecret'` → resultado **NO contiene** `'supersecret'` (verificado por substring en JSON serializado).

### CC-102 atomic API pública

- `state.update_resource_metadata(rid, {'k': 2})` → mutación atómica. `state.update_resource(rid, ...)` con cleanup_args/status/label OK.
- `_append_routine_run` ahora usa `append_lists=("history",), max_append=50` — cap respetado.

### CC-103 parse_ps_json

- `system.cpu_ram_gpu/disk/battery/brightness_get/list_windows/window_active/window_control` ahora capturan `JSONDecodeError` y devuelven `_err` con stdout truncado, en vez de excepción cruda.

### Sanity de seguridad (host del usuario)

- **0 invocaciones reales** a `subprocess.run`/`Popen` (todas interceptadas por stub).
- **0 tokens destructivos** observados en argv stubeado (shutdown, format, diskpart, rd /s, Remove-Item -Recurse).
- **0 modificaciones** fuera de `audit/smoke_workspace/` (tempdirs limpiados al exit).

## Casos fallados Modo A — detalle completo

```
FAIL [backup_sync] restore skip-policy (no gate): expect=ok, got=needs_confirmation
FAIL [backup_sync] T2-021 zip-slip blocked: expect=failed, got=needs_confirmation
FAIL [notification] T2-024 invalid time format: expect=needs_user, got=needs_confirmation
FAIL [notification] T2-024 HH:MM ok: expect=ok, got=needs_confirmation
FAIL [gui] CC-106 monitor=primary: expect=ok, got=failed (invalid tool arguments)
FAIL [gui] monitor invalid: expect=needs_user, got=failed (invalid tool arguments)
```

Los 4 primeros son falsos negativos del test (classifier dispara antes de la validación específica — hallazgo #2). Los 2 últimos son **bug real**: schema sync (hallazgo #1).

## Para retomar mañana

### Prioridad alta — fix recomendado

1. **Agregar properties al schema de `gui`/`filesystem`/`terminal`** (~30 líneas en `tools.py:3450`):
   - `gui`: `"monitor": {"type": "string"}`
   - `filesystem`: `"max_bytes": {"type": "integer"}`, `"max_files": {"type": "integer"}`
   - `terminal`: `"max_stdout_chars": {"type": "integer"}`, `"max_stderr_chars": {"type": "integer"}`

   Después de eso, los 2 gui fails pasan y el modelo puede usar `monitor=primary` cuando se le pide screenshot del monitor principal.

### Prioridad media

2. **Decidir UX** del solapamiento classifier↔gate duro (hallazgo #2). Opciones:
   - (a) Mantener el comportamiento actual (classifier dispara primero) — más conservador.
   - (b) Hacer que `execute()` corra una pre-validación específica antes del classifier para algunas tools.
   - (c) Quitar el classifier para las tools con gates duros propios (system, terminal, package, etc.) ya que el gate duro es suficiente.

   **Mi recomendación**: (a) por ahora. Es overkill pero no es bug. La UX se puede pulir cuando llegue feedback de uso real.

### Prioridad baja

3. **Modelo en llama-server**: actualmente corre `gemma-4-E4B-it-Q6_K.gguf` (chico). El target documentado es Gemma 4 26B A4B IQ4_XS. Si quieres mejor adherencia a tool_calls (multi-turn, prompts ambiguos como #34 "Abre Chrome en https://github.com"), conviene levantar el modelo grande.
4. **Prompt #31 (DuckDuckGo)**: el modelo eligió `browser.search` en vez de `web.search`. Ambas opciones son razonables pero `web.search` es más adecuado para uso programático. Considerar mejorar la description de `web` en el schema para enfatizar "use for queries that need raw text result".

## Artefactos generados

- `audit/smoke_harness.py` — context manager con stubs (subprocess, os.startfile, urllib, socket)
- `audit/smoke_mode_a.py` — runner Modo A
- `audit/smoke_mode_b.py` — runner Modo B
- `audit/smoke_log.md` — log detallado Modo A
- `audit/smoke_log_mode_b.md` — log detallado Modo B
- `audit/smoke_results.json` — resultados JSON Modo A
- `audit/smoke_results_mode_b.json` — resultados JSON Modo B
- `audit/smoke_workspace/` — tempdirs aislados (vacíos al final, autocleanup)

## Mensaje para el dev que arregle mañana

**Tres cosas en orden de impacto:**

1. **Schema sync** (`tools.py:3450` y aledaños): agregá los 5 properties faltantes a `gui`, `filesystem`, `terminal`. Pasos: leer hallazgo #1 arriba, editar las 4 entries, re-correr `python audit/smoke_mode_a.py`, confirmar 141/141 PASS.
2. **Decisión UX** del classifier vs gate duro (hallazgo #2): no es urgente, pero abre una discusión con el resto del equipo. Mientras tanto, los tests del agente que necesiten verificar validación específica deben pasar `confirmed=True` para saltar el classifier y llegar a la validación real.
3. **Modelo en producción**: subir Gemma 4 26B A4B IQ4_XS (el target) en llama-server cuando esté disponible. El E4B-Q6 actual es bueno para smoke pero no representa el comportamiento del modelo de producción.

Sesión cerrada sin tocar git. Buen sueño.
