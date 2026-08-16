# OPUS_CONTINUATION_BASELINE.md
# Estado de partida — Sesión de auditoría Claude Code (claude-sonnet-4-6)
# Fecha: 2026-05-06
# Propósito: Foto exacta del estado del repositorio antes de cualquier cambio en esta sesión

---

## 1. Estado git

**Rama activa:** `repo-cleanup-test-rebuild`
**HEAD:** `91ff4215` — "Close Carter v3 pre-voice/pre-camera blockers + repo reorganization"

**Historial reciente:**
```
91ff4215 Close Carter v3 pre-voice/pre-camera blockers + repo reorganization
87969048 Validate Carter v3 official 18x30 matrix
d4c0eba2 Implement verified local reminders for Carter v3
d8469442 Validate Carter v3 test to true ready without hardcodes
45e7d798 Stabilize Carter v3 text core with live minimum 36 ready
b4f80788 Implement LLM-first responses and manual live validation
8f3adefc Resolve Carter v3 strict live runtime blockers cycle 7
3a7aa176 Checkpoint before GPT55 cycle 7 strict blockers
```

**Working tree:** Sucio. ~364 entradas en `git status --short`.
- La mayoría son archivos borrados (`D`) de la raíz de `Carter_v3/` — reorganización en curso.
- Incluye archivos `.rar`, `.zip`, `%USERPROFILE%/...`, docs de ciclos previos.
- **No hay nada staged para commit.**

---

## 2. Conteo de tests

| Suite | Resultado |
|---|---|
| Total tests recolectados | **507** |
| Exit code | **0** |
| Fallidos | **0** |
| Hardcode guard | **CLEAN (58 archivos)** |

Suites específicas (de sesión anterior):
- `test_no_semantic_hardcodes.py`: 17 passed
- `test_llm_first_responses.py`: 12 passed
- `test_guards.py`: 18 passed
- `test_pending_intent_followups.py`: 8 passed

---

## 3. Documentos de competencia ya existentes

Ubicación: `Carter_v3/docs/competition/`

| Archivo | Origen | Contenido |
|---|---|---|
| `CLAUDE_COMPETITIVE_AUDIT_VERDICT.md` | Claude Code | Veredicto CARTER_ARCHITECTURE_GOOD_RUNTIME_WEAK con adendum del código real de 8 competidores |
| `WHAT_NOT_TO_COPY_FROM_COMPETITORS.md` | Claude Code | Tabla de 20 anti-patrones con riesgo y alternativa Carter |
| `COMPETITOR_GOOSE_DEEP_AUDIT.md` | GitHub Copilot | Audit Rust real de Goose — cita archivo:línea |
| `COMPETITOR_AGENTS_DEEP_AUDIT.md` | GitHub Copilot | Audit de AutoGPT, AutoGen, LangGraph, OS-Copilot, Open Interpreter, OpenHands, Agent-S, Claude CU |
| `COMPETITOR_MARK_DEEP_AUDIT.md` | Copilot/Codex | Audit de Mark XXXIX |
| `COMPETITOR_OPENCLAW_DEEP_AUDIT.md` | Copilot/Codex | Audit de OpenClaw |
| `COMPETITOR_LANDSCAPE_AUDIT.md` | Claude/Copilot | Resumen de todos los competidores |
| `COMPETITIVE_AUDIT_BASELINE.md` | Claude Code | Baseline de auditoría |
| `COMPETITOR_CODE_INVENTORY.md` | Claude Code | Inventario de código de competidores |
| `CARTER_VS_COMPETIDORES_TESIS.md` | Copilot | Tesis completa |
| `CARTER_VS_COMPETITION_MATRIX.md` | Copilot | Matriz de comparación |

---

## 4. Docs de auditoría ya existentes

Ubicación: `Carter_v3/docs/audit/`

| Archivo | Descripción |
|---|---|
| `CLAUDE_18X30_MATRIX_AUDIT.md` | Audit de la matriz 18x30 de capacidades |
| `CLAUDE_AUDIT_BASELINE.md` | Baseline de auditoría del código |
| `CLAUDE_CARTER_V3_AUDIT_VERDICT.md` | Veredicto de auditoría de código |
| `CLAUDE_CATEGORY_CAPABILITY_AUDIT.md` | Audit por categoría de capacidad |
| `CLAUDE_CONTEXT_CARTER_REQUIREMENTS.md` | Extracto de ContextoCarter.md |
| `CLAUDE_MANUAL_SPOTCHECK_SET.md` | Set de spotchecks manuales |
| `CLAUDE_RUNTIME_CODE_AUDIT.md` | Audit de código en runtime |
| `CODEX_REVIEW_minimum_live_safe_tool_policy_round.md` | Review de Codex |
| `PROMPT_FOR_CHATGPT_CODEX_TO_FINISH_CARTER_V3.md` | Prompt para Codex |

---

## 5. Bloqueadores activos (de BLOCKERS.md)

| # | Bloqueador | Prioridad |
|---|---|---|
| B1 | Working tree no commiteado — estado actual no coincide con HEAD | INMEDIATO |
| B2 | "Sí"/"OK"/"YES" no activan `pending_intent` | ALTA |
| B3 | `fake_success_guard` solo cubre inicio de reply | ALTA |
| B4 | `notify_toast` usa `synchronous_ok` → CONFIRMED sin verificación real | MEDIA |
| B5 | Sin progress reporting en misiones compuestas | MEDIA |
| B6 | System prompt puede ejecutar cuando usuario solo pregunta | MEDIA |

---

## 6. Veredicto oficial establecido

`CARTER_ARCHITECTURE_GOOD_RUNTIME_WEAK`

Carter v3 tiene la mejor arquitectura combinada de los 12 competidores analizados para el nicho de asistente personal local en Windows. Pero el runtime nunca fue validado live con LLM real y hay bloqueadores activos de experiencia real.

---

## 7. Restricciones de esta sesión

- NO abrir apps ni ventanas (usuario jugando)
- NO implementar sin confirmación del usuario
- NO committear sin autorización explícita
- NO reorganizar el repo
- NO agregar hardcodes de ningún tipo
- Esta sesión es solo: auditar, documentar, identificar problemas de Codex

---

## 8. Herramientas del ambiente

- Python: disponible
- pytest: 507 tests, exit 0
- hardcode_guard: CLEAN
- Ollama: NO usado esta sesión (usuario gaming)
- Git user: REDUniversitario

---

*Generado automáticamente por Claude Code (claude-sonnet-4-6) al inicio de sesión de auditoría — 2026-05-06*
