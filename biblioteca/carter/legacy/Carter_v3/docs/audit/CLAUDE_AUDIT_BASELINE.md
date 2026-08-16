# CLAUDE_AUDIT_BASELINE.md
# Carter v3 — Auditoría Pre-Voz/Pre-Cámara — Fase 0: Baseline
# Generado por: Claude Code (claude-sonnet-4-6) — 2026-05-06

---

## 1. Estado del repositorio

| Campo | Valor |
|---|---|
| Rama actual | `repo-cleanup-test-rebuild` |
| HEAD | `87969048` — "Validate Carter v3 official 18x30 matrix" |
| Tags relevantes | `carter-v3-18x30-true-ready`, `carter-v3-full-true-ready-local-reminders`, `carter-v3-text-core-full-654-ready`, `carter-v3-text-core-minimum-36-ready` |
| Working tree | **SUCIO** — 7 archivos modificados, no staged |

## 2. Archivos modificados (no commiteados)

```
modified:   Carter_v3/src/carter_v3/agent.py
modified:   Carter_v3/src/carter_v3/guards.py
modified:   Carter_v3/src/carter_v3/response_composer.py
modified:   Carter_v3/src/carter_v3/session_state.py
modified:   Carter_v3/src/carter_v3/tools/local_reminders.py
modified:   Carter_v3/tests/test_local_reminders.py
modified:   Carter_v3/tests/test_runtime_no_fake_success_live_cases.py
```

**IMPORTANTE**: El tag `carter-v3-18x30-true-ready` está sobre commit `87969048`, pero el árbol de trabajo tiene 202 líneas de diferencia que no están commiteadas. El tag apunta a código diferente al que existe actualmente en disco.

### Diferencia del diff (staging sin commit):
- `agent.py`: +104 / -1 líneas — cambios grandes en lógica del loop
- `guards.py`: +10 líneas — adición de guardas
- `response_composer.py`: +13 líneas — lógica de composición
- `session_state.py`: +25 líneas — estado de sesión
- `tools/local_reminders.py`: +2 / -1 líneas — reminders
- `tests/test_local_reminders.py`: +42 líneas — nuevos tests
- `tests/test_runtime_no_fake_success_live_cases.py`: +9 líneas — nuevos casos

## 3. Tags existentes y su significado

| Tag | Commit | Descripción |
|---|---|---|
| `carter-v3-18x30-true-ready` | `87969048` | Validación oficial 18x30 (540 casos) — en HEAD |
| `carter-v3-full-true-ready-local-reminders` | `d4c0eba2` | Local reminders implementados |
| `carter-v3-text-core-full-654-ready` | `d8469442` | Suite legacy 654 tests OK |
| `carter-v3-text-core-minimum-36-ready` | `45e7d798` | Mínimo 36/36 OK |
| `checkpoint-before-gemini-full-stabilization` | — | Checkpoint pre-estabilización |
| `checkpoint-before-jarvis-consolidation` | — | Checkpoint pre-consolidación |

## 4. Resultado de pytest (estado actual en disco)

```
490 passed in 196.26s
0 failed / 0 errors / 0 skipped
```

**ADVERTENCIA CRÍTICA**: Los 490 tests pasan, pero el árbol de trabajo no está commiteado. El tag `carter-v3-18x30-true-ready` no incluye los cambios actuales de `agent.py` (+104 líneas). Los tests que pasan corresponden al código en disco, NO al código tagueado.

## 5. Resultados de guardas específicas

| Test | Resultado |
|---|---|
| `hardcode_guard.py` | `CLEAN` — 58 archivos escaneados, 0 findings |
| `test_no_semantic_hardcodes.py` | 17 passed |
| `test_llm_first_responses.py` | 12 passed |

## 6. Evidencia previa existente

### Reportes .md en Carter_v3/:
- Múltiples reportes de rondas 01-12 con resultados de matriz
- Bloqueadores ciclos 3-7 documentados
- Smoke results ciclos 5-7

### Runs JSON en audit/runs/:
- `full_18x30_true_ready_final_v2.json` — 2.2 MB — 6 mayo 5:19 PM
- `full_closure_cycle2_full_matrix_final.json` — 2.6 MB — 6 mayo 3:09 AM
- 80+ archivos .memory.db de tests
- 87 screenshots PNG de runs de prueba

## 7. Evidencia que FALTA

1. **Resultado del run oficial 18x30 live ACTUAL** — el JSON existe pero no fue validado en esta sesión
2. **Confirmación de que los 490 tests cubren casos de regresión real** vs. casos sintéticos
3. **Spotcheck manual real** con el modelo corriendo — nada de esto está en los reportes como evidencia reciente
4. **Validación de latencia** — no hay medición reciente de p95 en condiciones reales
5. **Cobertura de categorías en working tree** vs. en código commiteado
6. **Confirmación de que los cambios en agent.py (+104 líneas) no rompieron nada nuevo** — los tests pasan pero no hay commit

## 8. Alerta de integridad del tag

El tag `carter-v3-18x30-true-ready` fue aplicado sobre commit `87969048`, pero el working tree tiene 202 líneas de diferencia adicional no commiteada. Esto significa que:
- El tag NO describe el estado actual del código en disco
- Los tests que pasan corresponden a código más nuevo que el tagueado
- Si se hace rollback al tag, el código sería diferente al auditado aquí
