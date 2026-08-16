# CARTER_V3_18X30_TRUE_READY_REPORT

Fecha: 2026-05-06

## Veredicto final

`CARTER_V3_18X30_TRUE_READY`

Carter v3 queda validado contra la matriz oficial completa: 18 categorías x 30 casos oficiales = 540 casos, con ejecución `live-safe-all`, 0 skipped, 0 failed, sin fake success y con gates anti-hardcode/LLM-first verdes.

## Alcance validado

Fuentes oficiales revisadas:

- `../ContextoCarter.md`.
- `../Cater_v3_tests/Carter_v3_GUIA_OFICIAL_TESTING (1).md`.
- `../Cater_v3_tests/Carter_v3_MINIMUM_TESTING_OFICIAL.md`.

La matriz oficial usada por `audit/full_matrix_runner.py` ya no proviene de la matriz legacy v2. Ahora se carga desde `audit/official_matrix_cases.py`, que parsea la guía oficial como fuente canónica y valida:

- 18 categorías.
- mínimo 30 casos por categoría.
- 540 filas oficiales totales en la guía actual.

## Evidencia principal

Artifact final:

`audit/runs/full_18x30_true_ready_final_v2.json`

Comando ejecutado:

`python audit/full_matrix_runner.py --mode live-safe-all --model qwen2.5:7b-instruct --label full_18x30_true_ready_final_v2`

Resultado:

| Métrica | Resultado |
|---|---:|
| total | 540 |
| executed | 540 |
| skipped | 0 |
| passed | 540 |
| failed | 0 |
| critical_failures | 0 |
| global | 100.0% |
| P1 | 100.0% |
| P2 | 100.0% |
| P3 | 100.0% |
| category_11 | 100.0% |
| category_18 | 100.0% |
| p50 | 1325.5ms |
| p95 | 3777.9ms |
| valid_mission_status_rate | 100.0% |
| validator_failures | `{}` |

## Gates finales

| Gate | Resultado |
|---|---|
| Full pytest | `488 passed` |
| Hardcode guard | `hardcode_guard: clean (58 files scanned)` |
| Semantic hardcodes | `17 passed` |
| LLM-first responses | `12 passed` |

## Auditorías generadas

- `FULL_18X30_MATRIX_AUDIT.md`: demuestra que la matriz previa de 654 casos no era cierre oficial v3 porque usaba taxonomía legacy.
- `FULL_18X30_FAILURE_AUDIT.md`: documenta fallos reales iniciales, reparaciones y revalidación final.
- `FULL_18X30_DIFF_AUDIT.md`: documenta cambios de código, artefactos conservados/eliminados y revisión anti-hardcode del diff.

## Capacidades cubiertas por la matriz oficial

Las 18 categorías oficiales quedaron al 100%:

1. Conversación simple y bajo contenido.
2. Identidad, personalidad y límites de Carter.
3. Conocimiento y preguntas sin herramientas innecesarias.
4. Memoria, preferencias y olvido.
5. Intención: conversación vs acción.
6. Router de herramientas y contratos.
7. Apps, ventanas y procesos Windows.
8. Web, URLs y navegador.
9. Steam, juegos, biblioteca local y tienda.
10. Filesystem, carpetas y documentos locales.
11. Terminal, comandos y política.
12. Seguridad, permisos, confirmaciones y fake success.
13. GUI, visión, observación y reintentos.
14. Misiones compuestas y autonomía por pasos.
15. Latencia, timeouts, recursos y progreso.
16. Multilingüe, typos e informalidad.
17. Follow-ups, contexto limpio y contaminación.
18. Regresiones reales, residual y aceptación final.

## Cambios funcionales cerrados

- Matriz oficial v3 cargada desde guía canónica, no desde legacy v2.
- Validación de safety basada en `destructive_risk` y familias de herramientas peligrosas.
- Memoria local real para guardar, actualizar, recuperar y olvidar preferencias oficiales.
- Bloqueo estructural de secretos y borrados amplios de memoria sin confirmación.
- Respeto explícito de `sin usar herramientas` sin fabricar hora/fecha exacta.
- Respeto explícito de `no uses ventana activa` y rechazo de uso permanente de ventana activa.
- Rutas read-only para procesos, ventanas, recursos y filesystem local cuando la intención es inequívoca.
- Detección extendida de hora/fecha informal y con typos.
- Limpieza/ignore de artefactos transitorios de auditoría.

## Garantías de no fake success

- `live-safe-all` ejecutó todos los casos sin skips, pero las acciones de side effect siguieron bloqueadas por política cuando correspondía.
- Los casos destructivos no pueden pasar como `complete` si activan `destructive_risk`.
- Las rutas directas nuevas ejecutan herramientas reales o devuelven bloqueo/verificación; no generan éxito sintético.
- El runner conserva validadores de tool policy, memory policy, active-app policy, mission integrity, observation integrity, latency y no fake success.

## Limitación honesta de live-safe

`live-safe-all` no significa ejecutar acciones destructivas o invasivas. Significa ejecutar los 540 casos sin skip y validar que Carter use herramientas reales cuando son seguras/read-only, y que bloquee, pida confirmación o marque no completado cuando la acción tendría side effects o riesgo. Esta limitación es intencional y consistente con `ContextoCarter.md`.

## Git esperado

Commit target:

`Validate Carter v3 official 18x30 matrix`

Tag target:

`carter-v3-18x30-true-ready`

## Decisión

Carter v3 cumple el estándar pedido por el usuario para esta fase: matriz oficial 18x30 completa, live-safe real donde aplica, sin hardcodes, sin fake success, sin hacks por app y con evidencia reproducible conservada.
