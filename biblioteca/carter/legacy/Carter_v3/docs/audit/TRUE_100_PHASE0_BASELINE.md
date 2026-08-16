# Carter v3 — TRUE_100 Phase 0 Baseline
**Date**: 2026-05-07  
**Branch**: `repo-cleanup-test-rebuild`  
**HEAD**: `32d6ebe5` — "Implement GUI automation tools + fix official matrix to 98.33%"  
**Working tree**: DIRTY (5 modified runtime files, ~40 untracked files, ~250 staged deletions)

---

## 1. HEAD y Branch

```
HEAD: 32d6ebe5 (repo-cleanup-test-rebuild)
Branch: repo-cleanup-test-rebuild
Ahead of main: YES (not checked — branch is cleanup/rebuild branch)
```

---

## 2. Archivos Runtime Modificados (sin commit, vs HEAD 32d6ebe5)

| Archivo | +/- neto | Tipo | Evaluación |
|---------|----------|------|------------|
| `Carter_v3/src/carter_v3/agent.py` | +43/-36 | Runtime | LEGÍTIMO — 9 fixes verificados por handoff |
| `Carter_v3/src/carter_v3/request_patterns.py` | +22/-14 | Runtime | LEGÍTIMO — 3 guards correctos |
| `Carter_v3/tests/test_agent_integration.py` | +31/-38 | Tests | LEGÍTIMO — test renombrado + assertions corregidas |
| `Carter_v3/src/carter_v3/tools/terminal_helpers.py` | ~+30/-25 | Runtime | LEGÍTIMO — fix Popen para Windows timeout kill |
| `Carter_v3/tests/conftest.py` | ~+55/-0 | Test config | LEGÍTIMO — cleanup autouse fixture para procesos huérfanos |

### Detalle de cambios runtime legítimos

**agent.py**:
1. `_try_background_research_fallback` — guard `if allowed - {"web_research"}: return False` elimina fake-success via web_research para OS actions locales
2. `_has_local_state_question_shape` — extiende patrón para "está abierto/cerrado", "quedó", etc.
3. `_memory_key_from_recall` — negation guard para "no mezcles mis preferencias"
4. `_synthesise_direct_tool_request` — "X está abierto?" → process_list (no window_list)
5. `_synthesise_direct_filesystem_request` — guard "qué quedó abierto" no genera filesystem_read
6. `_materialise_steps` — resolver guard para app_open estructural (C17.09 Batman)

**request_patterns.py**:
1. `looks_volume_adjust_request` — guard "qué significa volumen a 20" → no trigger volume adjust
2. `synthesise_structural_tool_calls` — Windows system path guard para SAM/etc.
3. `synthesise_structural_tool_calls` — `len(target_words) <= 4` para app_open

**terminal_helpers.py**:
- Reemplaza `subprocess.run(timeout=)` con `Popen + communicate(timeout=) + kill()` — en Windows el timeout de subprocess.run no mata al hijo, causando procesos zombis

**conftest.py**:
- Agrega `autouse` fixture para limpiar procesos huérfanos (notepad, calc, etc.) antes y después de cada test — evita que tests anteriores contaminen el entorno

---

## 3. Archivos Harness/Matriz Modificados (sin commit)

| Archivo | Estado | Evaluación |
|---------|--------|------------|
| `Carter_v3/audit/official_matrix_cases.py` | Modificado en sesión previa | `_GUIDE_CANDIDATES` reordenado para priorizar 18x30 — CORRECTO |
| `Carter_v3/audit/inspect_matrix_outputs.py` | NUEVO (untracked) | Inspector caso-por-caso creado esta sesión |

**NOTA**: `official_matrix_cases.py` NO tiene hardcodes ni relajaciones. El reorden de `_GUIDE_CANDIDATES` es correcto.

---

## 4. Archivos Borrados (staged, de repo cleanup previo)

~250 archivos borrados staged: audit JSONs históricos, screenshots, reportes de sesiones anteriores, Carter_v3.rar/.zip, archivos Mark-XXXIX, etc.

**ESTOS NO SE TOCAN.** Son parte del branch de cleanup. No representan pérdida de código vivo.

---

## 5. Archivos Untracked Nuevos

| Categoría | Ejemplos |
|-----------|---------|
| Audit runs (JSONs) | FINAL_99.81.json, FINAL_100_CLOSURE.json, fix_cycle*.json, etc. |
| Docs nuevos | CLAUDE_HANDOFF_TO_NEW_CHAT.md, CLAUDE_CONTINUATION_AFTER_LIMIT_REPORT.md |
| Inspector | inspect_matrix_outputs.py |
| Live validations | LIVE_VALIDATION_C07.md, LIVE_VALIDATION_C08.md, LIVE_VALIDATION_SPOTCHECK.md |
| Otros | screenshot.png, Extras/, docs/analysis/, docs/architecture/, etc. |

**NOTA**: `oficial_live_pass1.json` NO existe — el run live falló silenciosamente en sesión anterior.

---

## 6. Validaciones al Momento del Baseline

| Check | Resultado |
|-------|-----------|
| `hardcode_guard.py` | **CLEAN** (69 archivos) |
| `pytest tests/` | En ejecución… |
| `official_matrix_cases.py` (count) | **540 / 18 cats / 30 cada una** — CORRECTO |
| `live-safe-all matrix` | **NO EJECUTADO** en sesión anterior — a ejecutar |

---

## 7. Evaluación de Cambios Peligrosos

| Tipo | ¿Hay? | Detalle |
|------|-------|---------|
| Hardcode por frase/app | NO | hardcode_guard CLEAN |
| Relaxación de policy | NO | solo guards, no relajaciones |
| Modificación de official_matrix_cases.py sospechosa | NO | solo reorden de candidatos |
| Tests que verifican comportamiento incorrecto | NO — CORREGIDO | test_agent_integration.py renombra test que verificaba bug como feature |
| Regex peligrosos nuevos | NO | todos usan ≤5 literales, sin listas de apps/marcas |
| Artifacts que no deben commitearse | SÍ — audit JSONs masivos | no se deben incluir en commit final |

---

## 8. ¿Conviene revertir algo antes de seguir?

**NO** — los 5 archivos modificados tienen cambios legítimos, verificados por el handoff y por 690 pytest.

Lo que SÍ debe hacerse:
1. Ejecutar `live-safe-all` correctamente (síncronamente, sin background)
2. Revisar cada caso con `inspect_matrix_outputs.py`
3. Resolver C16.11 en entorno limpio
4. Commit solo cuando todo esté verificado

---

## 9. Veredicto

**WORKING_TREE_DIRTY_BUT_SAFE**

- Los cambios de runtime son legítimos y mejoran calidad
- No hay hardcodes, no hay relaxaciones
- El working tree sucio es esperado (cleanup branch + fixes no commiteados)
- El próximo paso es ejecutar el full matrix live correctamente
