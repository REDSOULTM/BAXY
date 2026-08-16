# COMPETITIVE_AUDIT_BASELINE.md
# Carter v3 — Auditoría Competitiva: Baseline de Estado
# Generado por: Claude Code (claude-sonnet-4-6) — 2026-05-06

---

## 1. Branch actual

`repo-cleanup-test-rebuild`

## 2. HEAD

`91ff4215` — "Close Carter v3 pre-voice/pre-camera blockers + repo reorganization"

## 3. Tags relevantes

| Tag | Commit | Descripción |
|---|---|---|
| `carter-v3-18x30-true-ready` | 87969048 | Valida la matriz oficial 18x30 |
| `carter-v3-full-true-ready-local-reminders` | d4c0eba2 | Implementa local reminders verificados |
| `carter-v3-text-core-full-654-ready` | d8469442 | Texto core true ready sin hardcodes |
| `carter-v3-text-core-minimum-36-ready` | 45e7d798 | Mínimo 36 estable |
| `checkpoint-before-gemini-full-stabilization` | (old) | Checkpoint pre-Gemini |
| `checkpoint-before-jarvis-consolidation` | (old) | Checkpoint pre-consolidación |

## 4. Estado del working tree

**⚠️ WORKING TREE SUCIO**

El branch `repo-cleanup-test-rebuild` tiene cientos de archivos marcados como `deleted` en el working tree. Esto corresponde a una reorganización del repo en curso donde archivos que estaban en `Carter_v3/` se movieron o eliminaron desde el working directory pero aún están tracked en git.

- El tag `carter-v3-18x30-true-ready` (commit 87969048) describe el estado histórico de la matriz.
- HEAD (91ff4215) es el commit más reciente, pero el working tree tiene deletes no stageados.
- **El working tree NO está limpio. Hay riesgo de confusión entre estado committado y estado en disco.**

## 5. Archivos modificados / eliminados (resumen)

El `git status` muestra >100 archivos marcados como `deleted` (no stageados), principalmente:
- Todos los docs de auditoría en `Carter_v3/` (`.md` de ciclos, planes, reportes)
- Imágenes de audit en `Carter_v3/audit/runs/`
- Docs de Roadmap en `Carter_v3/Roadmap/`
- Archivos ZIP (`Carter_v3.rar`, `Carter_v3.zip`)

El **código fuente** en `Carter_v3/src/` y los **tests** en `Carter_v3/tests/` parecen intactos en disco.

## 6. Estado de tests conocidos

| Test suite | Estado conocido | Fuente |
|---|---|---|
| `python -m pytest` (490 tests) | PASAN con ScriptedAdapter | CLAUDE_CARTER_V3_AUDIT_VERDICT.md |
| `hardcode_guard.py` (58 archivos) | CLEAN | CLAUDE_CARTER_V3_AUDIT_VERDICT.md |
| `full_matrix_runner.py` modo `scripted` | 540/540 | CARTER_V3_18X30_TRUE_READY_REPORT.md |
| `full_matrix_runner.py` modo `live-safe-all` | 540/540 | CARTER_V3_18X30_TRUE_READY_REPORT.md |
| Validación live con LLM real | **NO EJECUTADA** | CLAUDE_CARTER_V3_AUDIT_VERDICT.md |
| Latencia real medida | **NO MEDIDA** | CLAUDE_CARTER_V3_AUDIT_VERDICT.md |

## 7. Reportes previos existentes (en Carter_v3/docs/audit/)

| Reporte | Valor |
|---|---|
| `CLAUDE_CARTER_V3_AUDIT_VERDICT.md` | Veredicto oficial Claude — `TESTS_PASS_BUT_RUNTIME_WEAK` |
| `CLAUDE_RUNTIME_CODE_AUDIT.md` | 29 hallazgos del código runtime |
| `CLAUDE_18X30_MATRIX_AUDIT.md` | Auditoría de la matriz 18x30 |
| `CLAUDE_CATEGORY_CAPABILITY_AUDIT.md` | Estado por categoría C01-C18 |
| `CLAUDE_AUDIT_BASELINE.md` | Baseline de auditoría anterior |
| `PROMPT_FOR_CHATGPT_CODEX_TO_FINISH_CARTER_V3.md` | Prompt para Codex pre-competitivo |

## 8. Veredicto previo (antes de esta auditoría competitiva)

**`TESTS_PASS_BUT_RUNTIME_WEAK`** — Carter v3 tiene arquitectura sólida y tests que pasan, pero **nunca se validó live** que pueda abrir apps reales, verificarlas, y manejar follow-ups con un modelo LLM real corriendo.

Bloqueadores activos documentados al inicio de esta sesión:
- B1: Working tree no commiteado
- B2: Confirmaciones "Sí"/"OK"/"YES" rotas (pending_intent)
- B3: fake_success_guard cubre solo inicio de reply
- B4: notify_toast usa synchronous_ok sin verificación visual
- B5: Sin progress reporting en misiones compuestas
- B6: System prompt puede ejecutar cuando usuario solo pregunta

## 9. Advertencia sobre tags

**El tag `carter-v3-18x30-true-ready` NO representa el working tree actual en disco.**

La auditoría competitiva se basa en el código fuente legible en disco, que puede tener cambios respecto al commit taggeado. Cualquier afirmación sobre el estado del código se basa en lo leído directamente de los archivos en disco en esta sesión (2026-05-06).

---

*Este documento es solo baseline. No modifica código, no hace commits, no declara READY.*
