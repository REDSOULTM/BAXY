# TEST_TRUE_READY_REPORT

Veredicto final: **TEST_TRUE_READY**

## 1. Test ejecutado

Matriz completa importada por `audit/full_matrix_runner.py` desde `legacy/Carter_v2/audit/runners/full_live_llm_cases.py`.

Categorías: 18.

Casos: 654.

## 2. Comandos exactos

Baseline fallido:

```powershell
python audit/full_matrix_runner.py --mode live-safe --model qwen2.5:7b-instruct --label gpt55_true_ready_round0b
```

Revalidaciones enfocadas:

```powershell
python audit/full_matrix_runner.py --mode live-safe --model qwen2.5:7b-instruct --category 4 --label gpt55_true_ready_round1_cat4
python audit/full_matrix_runner.py --mode live-safe --model qwen2.5:7b-instruct --category 11 --label gpt55_true_ready_round1_cat11
python audit/full_matrix_runner.py --mode live-safe --model qwen2.5:7b-instruct --category 14 --label gpt55_true_ready_round1_cat14
python audit/full_matrix_runner.py --mode live-safe --model qwen2.5:7b-instruct --label gpt55_true_ready_round1_full
```

Validación final sin skipped:

```powershell
python audit/full_matrix_runner.py --mode live-safe-all --model qwen2.5:7b-instruct --label gpt55_true_ready_round2_all
```

Anti-hardcode y suite:

```powershell
python audit/hardcode_guard.py
python -m pytest tests/test_no_semantic_hardcodes.py -v
python -m pytest -q
```

## 3. Totales finales

Final `live-safe-all`:

- total_cases=654
- executed=654
- skipped=0
- passed=654
- failed=0
- dangerous_cases=68
- dangerous_passed_by_block=68
- critical_failures=0
- global_pass_rate=100.0%
- p95_ms=3057.5
- validator_failures={}
- verdict=V3_BASELINE_LANDED_LIVE_VERIFIED

Final `live-safe` clásico post-fix:

- executed=526
- skipped=128 por restricciones históricas de modo
- passed=526
- failed=0
- global_pass_rate=100.0%

## 4. Casos peligrosos y bloqueo

- Ningún caso peligroso ejecutó herramientas reales.
- Ningún caso peligroso terminó como `complete`.
- Distribución final dangerous: `failed=49`, `needs_user=5`, `trivial=14`.
- Los `trivial` fueron respuestas sin herramienta y sin afirmación de ejecución; se trataron como rechazo/guía segura/no capacidad verificable.

## 5. Memoria/privacidad

- `actualiza mi nombre a Pedro` ya no se resuelve como app.
- La asignación explícita de nombre se enruta a memoria local (`memory_save`) por patrón auditado de `user.name`.
- Secretos siguen bloqueados por `contains_secret()`; no se relajó policy de memoria.

## 6. Fixes aplicados

1. Policy safety más completa para lenguaje natural destructivo y acciones críticas.
2. Memory name update local, sin rutas ni apps.
3. Gate universal de ambigüedad de resolver.
4. Fallback de app limitado a forma app open/close y sin saltarse policy blocks.
5. Modo `live-safe-all` para ejecutar todos los casos sin side effects reales y sin skipped.

## 7. Validación anti-hardcode

- `python audit/hardcode_guard.py` → `hardcode_guard: clean (57 files scanned)`.
- `python -m pytest tests/test_no_semantic_hardcodes.py -v` → `17 passed`.

## 8. Suite completa

- `python -m pytest -q` → suite completa PASS.
- Único warning observado: `pywinauto` STA COM threading mode en `test_uia_probe.py`; no bloqueante.

## 9. Diff audit

- Ver `FINAL_TEST_DIFF_AUDIT.md`.
- Veredicto: `DIFF_CLEAN_ACCEPTABLE`.

## 10. Riesgos restantes

- `live-safe-all` bloquea side effects para no tocar apps/browser/filesystem/terminal del usuario. Para validar efectos reales de acciones intrusivas debe usarse un entorno controlado o confirmación explícita.
- Algunas respuestas `trivial` peligrosas son rechazos/guías sin tool; no ejecutan nada, pero pueden mejorarse en tono para mencionar riesgo más explícitamente.

## 11. Veredicto final

**TEST_TRUE_READY**

Condiciones cumplidas:

- test pasa 100%;
- executed=total_cases;
- skipped=0;
- failed=0;
- critical_failures=0;
- peligrosos bloqueados/no ejecutados;
- no fake success observado;
- no hardcodes detectados;
- hardcode_guard pasa;
- no-semantic-hardcodes pasa;
- suite completa pasa;
- diff audit aceptable;
- ContextoCarter.md respetado.
