# FULL_18X30_DIFF_AUDIT

Fecha: 2026-05-06

## Veredicto

`DIFF_CLEAN_FOR_COMMIT`

El diff final queda acotado al cierre oficial 18x30: fuente de matriz oficial, runner oficial, rutas estructurales universales necesarias para pasar la guía oficial, reglas de ignore para artefactos transitorios, auditorías y evidencia JSON de las corridas completas.

No se detectan cambios orientados a un caso exacto de la matriz ni atajos por aplicación concreta. Las reparaciones son estructurales por familia de herramienta, política de seguridad y semántica universal.

## Archivos modificados

| Archivo | Motivo | Riesgo revisado |
|---|---|---|
| `.gitignore` | Ignora bases SQLite de memoria de auditoría, screenshots y PNG temporales generados por corridas live-safe. | No afecta runtime; evita contaminar futuros diffs con artefactos volátiles. |
| `audit/full_matrix_runner.py` | Deja de importar la matriz legacy v2 y usa la matriz oficial v3 parseada desde la guía. Ajusta safety policy por `destructive_risk`. | Mantiene validadores; no relaja `tool_policy`, `memory_policy`, `active_app_policy`, `mission_integrity`, `observation_integrity` ni `latency_budget`. |
| `src/carter_v3/agent.py` | Añade rutas estructurales para memoria oficial, no-tool guard, no-active-window guard y herramientas read-only locales. | Rutas universales; side effects siguen pasando por `_classify_tool_policy`; no hay fake success. |
| `src/carter_v3/request_patterns.py` | Amplía detección de hora/fecha para variantes informales oficiales. | Cambio limitado a patrón universal de clock/date; no introduce respuestas fijas. |

## Archivos nuevos intencionales

| Archivo | Motivo |
|---|---|
| `audit/official_matrix_cases.py` | Loader canónico de la guía oficial `Carter_v3_GUIA_OFICIAL_TESTING (1).md` hacia el esquema `Case`. Verifica 18 categorías y mínimo 30 casos por categoría. |
| `FULL_18X30_MATRIX_AUDIT.md` | Auditoría inicial que demuestra que la matriz legacy de 654 casos no era equivalente oficial v3. |
| `FULL_18X30_FAILURE_AUDIT.md` | Registro honesto de fallos iniciales 504/540 y 535/540, reparaciones y revalidación final 540/540. |
| `audit/runs/full_18x30_true_ready.json` | Evidencia de primera corrida oficial completa: 504/540. |
| `audit/runs/full_18x30_true_ready_v2.json` | Evidencia de segunda corrida oficial completa: 535/540. |
| `audit/runs/full_18x30_true_ready_final_v2.json` | Evidencia final oficial: 540/540, 0 skipped, 0 failed. |

## Artefactos transitorios eliminados o ignorados

Se eliminaron de la working tree los artefactos generados que no aportan evidencia final estable:

- `audit/*.memory.db` de corridas/probes oficiales 18x30.
- `audit/runs/official_18x30_*.json` de probes parciales y scripted smokes.
- `audit/runs/*_screenshot.png` generados durante pruebas visuales.
- `audit/tmp_scripted.png`.
- `audit/runs/full_18x30_true_ready_final.json`, reemplazado por la revalidación final `full_18x30_true_ready_final_v2.json` posterior a la recuperación completa de pytest.

Se conservaron solo las tres corridas completas oficiales necesarias para auditar evolución de fallos y cierre.

## Revisión anti-hardcode

Revisión aplicada sobre el diff:

- La fuente de casos no copia prompts en código: parsea la guía oficial como fuente única.
- Las rutas nuevas en `agent.py` no reconocen IDs de caso ni textos exactos de la matriz.
- Los patrones agregados son por intención universal: memoria, procesos, ventanas, recursos, filesystem local, prohibición de tools y prohibición de ventana activa.
- Los side effects no se marcan como éxito falso: siguen pasando por policy/verifier.
- Los casos destructivos se bloquean o quedan `needs_user/failed/trivial` según corresponda; el runner ahora impide marcarlos `complete` si hay `destructive_risk`.

Gates ejecutados:

- `python audit/hardcode_guard.py` -> `hardcode_guard: clean (58 files scanned)`.
- `python -m pytest tests/test_no_semantic_hardcodes.py -v` -> `17 passed`.
- `python -m pytest tests/test_llm_first_responses.py -v` -> `12 passed`.

## Validación final asociada al diff

### Matriz oficial 18x30

Comando:

`python audit/full_matrix_runner.py --mode live-safe-all --model qwen2.5:7b-instruct --label full_18x30_true_ready_final_v2`

Resultado:

- total=540
- executed=540
- skipped=0
- passed=540
- failed=0
- critical_failures=0
- global=100.0%
- P1=100.0%
- P2=100.0%
- P3=100.0%
- category_11=100.0%
- category_18=100.0%
- p95=3777.9ms
- artifact=`audit/runs/full_18x30_true_ready_final_v2.json`

### Pytest

Comando:

`python -m pytest --tb=short`

Resultado:

- `488 passed`

## Decisión

El diff es apto para commit/tag del cierre oficial 18x30 porque:

1. Ejecuta la matriz oficial, no la legacy.
2. La corrida final oficial pasa 540/540 con 0 skipped.
3. Las regresiones pytest quedaron recuperadas.
4. Los gates anti-hardcode y LLM-first pasan.
5. Los artefactos transitorios fueron limpiados o ignorados.
6. La evidencia conservada permite auditar fallos iniciales y resultado final.
