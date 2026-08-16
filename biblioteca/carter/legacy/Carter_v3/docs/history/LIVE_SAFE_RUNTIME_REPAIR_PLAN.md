# LIVE_SAFE_RUNTIME_REPAIR_PLAN

Fecha: 2026-05-05  
Autor: Cursor (nuevo plan, no copia del cierre previo).  
Constraint hard: no hardcodes por app/frase/marca, no regex semantico, ContextoCarter first.

## Documentos encontrados/faltantes

- Encontrados: `TEXT_CORE_MASTER_CONTEXT.md`, `TEXT_CORE_CLOSURE_AUDIT.md`, `TEXT_CORE_100_MASTER_PLAN.md`, `TEXT_CORE_CLOSURE_REPORT.md`, `LIVE_SAFE_TEXT_CORE_SMOKE_PLAN.md`, `LIVE_RUNTIME_NO_HARDCODE_AUDIT.md`, `LIVE_RUNTIME_NO_HARDCODE_PLAN.md`, `LIVE_SAFE_RUNTIME_CLOSURE_REPORT.md`, `REJECTED_HARDCODE_RUNTIME_ATTEMPT_REPORT.md`, `REJECTED_HARDCODE_RUNTIME_ATTEMPT.patch`, `VISION_WITHOUT_VLM_AUDIT.md`, `VISION_WITHOUT_VLM_PLAN.md`, `VISION_WITHOUT_VLM_REPORT.md`, `THIRD_PASS_GUI_PERCEPTION_AUDIT.md`, `THIRD_PASS_GUI_PERCEPTION_PLAN.md`, `THIRD_PASS_GUI_PERCEPTION_REPORT.md`, `THIRD_PASS_MISSION_STATUS_TRACE_REPORT.md`, `SECOND_PASS_TEXT_CORE_HARDENING_REPORT.md`, `MARK_TO_CARTER_TEXT_CORE_REPORT.md`, `AUDIT_MARK_TO_CARTER_TEXT_CORE.md`, `PLAN_MARK_INSPIRED_TEXT_CORE.md`, `CHANGELOG.md`, `RESIDUAL.md`.
- Faltantes: no detectados de la lista obligatoria.

## A) Mantener de `6aae2b0a`

1. U0 hardcode_guard endurecido.
2. U1 `prior_turns` en launcher.
3. U2 prompt basado en `TOOL_CATALOG`.
4. U3 evidencia `preexisting` en `app_open`.
5. U4 `next_step_hint` generico.
6. U5 `missing_dependency -> needs_environment`.
7. U6 `notify_toast` literal.

## B) Revertir de `6aae2b0a`

- Ningun revert total propuesto ahora.
- Solo se ajustara comportamiento si rompe runtime live real o policy.

## C) Completar de `6aae2b0a`

1. Robustecer follow-ups (`Abriste X?`, `Lo cerraste?`, `Si/No/Hazlo`).
2. Completar pending intent universal para filesystem read confirmable.
3. Cubrir persona/arquitectura/capabilities sin deriva LLM generico.
4. Extender tests anti fake-success live cases.
5. Ejecutar smoke live real contra Ollama y documentar evidencia exacta.

## D) Nuevos fixes necesarios

1. Estado pending intent general en `session_state`/`agent`.
2. Mejor coherencia de memoria nombre/color con `MemoryStore`.
3. Filtros de follow-up de media (`pausala`) basados en contexto real, no frases.
4. Manejo compuesto seguro (abrir app + accion no soportada).
5. Bloqueo safety de mensajes a terceros por policy/capability/permission.

## Cambios permitidos y justificacion no-hardcode

### 1) Capability registry derivado de catalogo
- **No hardcode**: fuente unica declarativa de tools reales.
- **Archivo**: `src/carter_v3/turn_support.py`.
- **Test**: `tests/test_runtime_persona_and_capabilities.py`.
- **Smoke**: A4/A6/A7/A16.
- **Rollback**: revert de prompt builder.

### 2) System prompt desde catalogo + ContextoCarter
- **No hardcode**: no enumera apps/frases, usa capacidades presentes.
- **Archivo**: `src/carter_v3/turn_support.py`.
- **Test**: `tests/test_runtime_persona_and_capabilities.py`.
- **Smoke**: A1-A8.
- **Rollback**: fallback prompt previo.

### 3) Response composer guard por capacidades/evidencia
- **No hardcode**: opera con `ToolResult`/`VerifiedOutcome`.
- **Archivo**: `src/carter_v3/response_composer.py`.
- **Test**: `tests/test_runtime_no_fake_success_live_cases.py`.
- **Smoke**: D/E/F/G.
- **Rollback**: composer anterior.

### 4) Follow-up state por `last_turn_trace` / `prior_turns` / `session_state`
- **No hardcode**: usa estado conversacional estructural.
- **Archivo**: `src/carter_v3/agent.py`, `src/carter_v3/session_state.py`.
- **Test**: `tests/test_pending_intent_followups.py`.
- **Smoke**: B/C/E/F.
- **Rollback**: desactivar follow-up paths nuevos.

### 5) Pending intent universal
- **No hardcode**: se basa en tipo de accion pendiente, no frase literal.
- **Archivo**: `src/carter_v3/session_state.py`, `src/carter_v3/agent.py`.
- **Test**: `tests/test_pending_intent_followups.py`.
- **Smoke**: C16-C17.
- **Rollback**: apagar pending intents nuevos.

### 6) App preexisting process handling por evidence
- **No hardcode**: campo verificador `preexisting`.
- **Archivo**: `src/carter_v3/response_composer.py`, verifier si aplica.
- **Test**: `tests/test_live_regressions_from_user_log.py`.
- **Smoke**: E29-E31.
- **Rollback**: reply fallback sin preexisting.

### 7) Missing dependency normalization (`data["missing_dependency"]`)
- **No hardcode**: independiente de tool especifica.
- **Archivo**: `src/carter_v3/agent.py`, dispatchers que apliquen.
- **Test**: `tests/test_runtime_no_fake_success_live_cases.py`.
- **Smoke**: F35-F38.
- **Rollback**: quitar mapping policy block.

### 8) Path extraction estructural Windows
- **No hardcode**: forma de ruta, no intencion semantica.
- **Archivo**: `src/carter_v3/request_patterns.py` (si aplica), `agent.py`.
- **Test**: `tests/test_live_regressions_from_user_log.py`.
- **Smoke**: C16-C17-C73.
- **Rollback**: parser previo.

### 9) Memory consistency via MemoryStore
- **No hardcode**: estado persistente estructural.
- **Archivo**: `src/carter_v3/agent.py`, `memory/store.py`, `session_state.py`.
- **Test**: `tests/test_live_regressions_from_user_log.py`.
- **Smoke**: B9-B12-B20.
- **Rollback**: ruta de memoria previa.

### 10) Safety de mensajes por risk/policy/capability
- **No hardcode**: sin nombres de apps.
- **Archivo**: `src/carter_v3/security/policy.py`, `agent.py`.
- **Test**: `tests/test_runtime_no_fake_success_live_cases.py`.
- **Smoke**: I51-I53.
- **Rollback**: policy anterior.

### 11) Alarm/reminder handling por capabilities ausentes
- **No hardcode**: ausencia/presencia de tool, no regex "alarma".
- **Archivo**: `turn_support.py`, `response_composer.py`, `agent.py`.
- **Test**: `tests/test_runtime_no_fake_success_live_cases.py`.
- **Smoke**: G42-G44.
- **Rollback**: revert minimal en composer/prompt.

## Prohibiciones explicitas del plan

- no regex semantico por intencion;
- no listas de apps en routing core;
- no `if "steam"/"discord"/"whatsapp"/"spotify"...`;
- no quick patch por frase del log;
- no hardcode de respuestas literales por caso.

## Ejecucion por ciclos (max 8)

1. Escribir tests obligatorios (fallando primero) por bloque.
2. Implementar minima logica para pasar bloque.
3. Ejecutar subset + suite relevante.
4. Ejecutar `hardcode_guard`.
5. Repetir hasta cubrir bloques.
6. Ejecutar smoke live subset obligatorio.
7. Correr validacion final completa.
8. Generar reporte/veredicto honesto.

## Criterio de cierre operativo

- Sin smoke live critico no se declara `READY`.
- Si bloqueo por entorno: declarar `BLOCKED_BY_ENVIRONMENT` con evidencia.
