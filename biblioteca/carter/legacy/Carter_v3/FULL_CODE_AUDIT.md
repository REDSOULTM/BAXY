# FULL_CODE_AUDIT

Fecha: 2026-05-06

## 1. Qué está bien

- `contracts.py` mantiene estados públicos pequeños y estructurales: `trivial`, `complete`, `partial`, `failed`, `needs_user`, `unverified`.
- `compute_mission_status()` no usa texto del LLM para decidir completion; depende de tools, verifier, policy y errores.
- `tools/catalog.py` es fuente única de capabilities públicas y se renderiza en `turn_support.py`.
- `PolicyEngine` bloquea clases destructivas críticas antes de tool dispatch y no autoaprueba high/critical por defecto.
- `VerificationManager` tiene readback por tool y evita confirmar herramientas sin spec.
- `AgentEngine` registra memoria real cuando existe `MemoryStore` y separa policy, dispatch, verifier, composer y verbalizer.
- `turn_support.build_messages()` alinea persona local, no fake success, catálogo y restricciones de missing capability.
- `guards.py` cubre fake success, placeholders, active-app contamination, script mismatch, memory echo e historial.
- `request_patterns.py` concentra señales estructurales auditadas y evita filesystem mutation por regex semántico.
- Runners `minimum_testing_runner.py` y `full_matrix_runner.py` tienen modos live-safe/live-safe-all para no ejecutar side effects destructivos.
- `hardcode_guard.py` está activo y baseline actual pasa: 57 files clean.

## 2. Qué está frágil

- Hay cambios no commiteados preexistentes que rompen pytest: LLM-first y test heredado de app_close absent.
- `select_tools()` devuelve solo 16 specs; cualquier capability nueva agregada al final puede no ser visible al LLM en prompts de acción.
- Catálogo público tiene cap `<=32`; añadir herramientas separadas sin consolidar rompería tests e invariant.
- `system_get_time` duplica `clock_now` en catálogo; es candidato a liberar slot sin perder capability esencial.
- Alarmas/recordatorios no existen; el sistema depende de missing-capability wording para una necesidad legítima.
- La materialización estructural puede sintetizar herramientas para clock/app/web/volume/path/terminal, pero no para schedule; hacerlo por regex de intent sería riesgoso.
- `notify_toast` es solo notificación inmediata; tests ya protegen contra usarlo como falsa alarma.
- `app_close already_absent` requiere una decisión canónica: ContextoCarter favorece `pending/unverified`, pero un test heredado espera `confirmed`.

## 3. Capacidades faltantes

- ALARMS_REMINDERS real local:
  - create future reminder/alarm;
  - list active reminders created by Carter;
  - cancel by id or selected local reminder;
  - get by id;
  - cleanup expired;
  - persist across engine restart;
  - honest limitation if no OS notification backend exists.
- Calendar/time future effects más amplios.
- Messaging draft/send con permiso explícito.
- Browser tab advanced actions verificados.
- OCR/VLM/voz/cámara fuera de scope actual.

## 4. Riesgo de fake success

- Cualquier tool con `ok=True` pero sin payload puede volverse `UNVERIFIABLE` por `_normalize_tool_result_evidence()`.
- `notify_toast` puede contener texto como “alarma creada”; composer lo narra literalmente y no como side effect.
- `app_close already_absent` no debe confirmar cierre porque no cerró nada; diff inicial va en dirección correcta.
- Nueva alarm/reminder capability debe confirmar escritura/listado en DB antes de `complete`; si no se guarda, `FAILED`/`UNVERIFIED`.

## 5. Riesgo de hardcode

- No se debe añadir `looks_alarm_request`, `looks_reminder_request` ni regex de intención semántica.
- No se debe enrutar por frases “pon alarma”, “recordatorio”, “wake me”.
- Permitido: parser temporal genérico dentro del tool para normalizar `due_at`/`when_text`, porque no decide intención ni ruta.
- Tool names/capability catalog pueden nombrar la capacidad real; el hardcode prohibido es usar tokens del prompt como ramas de routing.

## 6. Routing débil

- Las rutas con structural fallback cubren clock, memory name, URL, app open, search, screenshot, observation, volume, filesystem path y terminal safe.
- Para alarms, el LLM debe seleccionar la tool desde el catálogo. Para maximizar éxito sin semantic hardcodes, la tool debe estar entre las primeras 16 specs o en `preferred` por señal temporal estructural amplia si se decide hacerlo.
- Cualquier fallback de schedule debe basarse en tool call del LLM o en un clasificador LLM estructurado, no en listas de palabras.

## 7. Tests que no cubren la realidad

- Tests actuales de alarmas solo validan “no puedo/capability missing”; eso ya no es suficiente si aceptamos que recordatorios locales son legítimos.
- No hay tests de persistencia para alarms/reminders.
- No hay runner category 30 separado; full matrix cumple esa función pero no contiene ALARMS_REMINDERS.
- Test heredado `test_app_close_confirmed_when_already_absent` contradice la regla nueva “absent no es cierre verificado”. Debe actualizarse como mejora de test, no relajación.

## 8. Qué debe implementarse para cumplir el set completo

Primer ciclo debe reparar baseline:

1. Restaurar LLM-first en rutas tool_result unverified, permitiendo que el verbalizer sea llamado y luego guard/fallback bloquee overclaim.
2. Alinear test de app_close absent con criterio actual: `PENDING` y no `COMPLETE`.

Segundo ciclo debe añadir capability local universal:

1. Añadir una herramienta compuesta `local_reminder` o equivalente para create/list/cancel/get/cleanup en un solo slot público.
2. Liberar un slot de catálogo preferiblemente retirando `system_get_time` de catálogo público y manteniendo `clock_now` como capability de hora.
3. Implementar persistencia SQLite/local JSON fuera de cloud, con IDs únicos, zona local, estado active/cancelled/expired y timestamps.
4. Verifier debe confirmar contra la misma store local: create/get/list/cancel.
5. Composer debe responder honestamente: si no hay OS toast/scheduler, decir “recordatorio local guardado/listable por Carter; no prometo notificación del sistema”.
6. Tests unitarios/integración deben validar create future, reject past, list, cancel, persistence restart, no fake success, no external alarm hallucination.

Tercer ciclo debe revalidar:

- pytest completo;
- hardcode_guard;
- no_semantic_hardcodes;
- LLM-first;
- minimum live-safe-all;
- full matrix live-safe-all si Ollama está disponible.
