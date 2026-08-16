# FULL_18X30_MATRIX_AUDIT

Fecha: 2026-05-06

## Veredicto de auditoría inicial

`MATRIX_NOT_OFFICIAL_YET`

El runner existente sí contiene 18 categorías y 654 casos, pero la matriz importada desde `legacy/Carter_v2/audit/runners/full_live_llm_cases.py` no está alineada 1:1 con la guía oficial actual `Carter_v3_GUIA_OFICIAL_TESTING (1).md`.

La guía oficial declara exactamente:

- 18 categorías.
- 30 casos por categoría.
- 540 casos oficiales.
- La guía es la fuente oficial única.

El runner actual declara:

- 18 categorías.
- 654 casos.
- 30+ casos por categoría.
- Importa una matriz legacy v2 con taxonomía antigua.

## Fuentes leídas

- `../ContextoCarter.md`.
- `../Cater_v3_tests/Carter_v3_GUIA_OFICIAL_TESTING (1).md`.
- `../Cater_v3_tests/Carter_v3_MINIMUM_TESTING_OFICIAL.md`.
- `audit/full_matrix_runner.py`.
- `audit/minimum_testing_runner.py`.
- `../legacy/Carter_v2/audit/runners/full_live_llm_cases.py`.
- `CARTER_V3_FULL_TRUE_READY_REPORT.md` como evidencia histórica, no como cierre 18x30.
- `TEST_TRUE_READY_REPORT.md` como evidencia histórica, no como cierre 18x30.

## Confirmación de la guía oficial

Parseo de la guía oficial:

- Categorías encontradas: 18.
- Filas oficiales encontradas: 540.
- Cada categoría C01-C18 tiene exactamente 30 casos.

## Tabla oficial vs runner actual

| Categoría | Nombre oficial | Casos actuales | Requiere 30 | Estado | Live-safe | Gaps |
|---|---|---:|---:|---|---|---|
| C01 | Conversación simple y bajo contenido | 40 | 30 | `COMPLETE_30_PLUS` | completo | Nombre abreviado, cobertura compatible. |
| C02 | Identidad, personalidad y límites de Carter | 32 | 30 | `COMPLETE_30_PLUS` | completo | Nombre abreviado, cobertura parcial de límites. |
| C03 | Conocimiento y preguntas sin herramientas innecesarias | 31 | 30 | `COMPLETE_30_PLUS` | completo | Nombre abreviado, cobertura compatible. |
| C04 | Memoria, preferencias y olvido | 31 | 30 | `COMPLETE_30_PLUS` | completo | Runner separa preferencias en C05 legacy; C04 oficial mezcla memoria/preferencias/olvido. |
| C05 | Intención: conversación vs acción | 35 | 30 | `NEEDS_REAL_CASES` | completo | C05 legacy es preferencias de estilo, no intención conversación vs acción. |
| C06 | Router de herramientas y contratos | 37 | 30 | `COMPLETE_30_PLUS` | completo | C06 legacy es herramientas simples; cubre parte pero no todos los contratos oficiales. |
| C07 | Apps, ventanas y procesos Windows | 33 | 30 | `COMPLETE_30_PLUS` | parcial en live-safe clásico; no-skip en live-safe-all | Cobertura compatible pero con taxonomía legacy. |
| C08 | Web, URLs y navegador | 36 | 30 | `COMPLETE_30_PLUS` | no-skip en live-safe-all | Cobertura compatible. |
| C09 | Steam, juegos, biblioteca local y tienda | 38 | 30 | `NEEDS_REAL_CASES` | no-skip en live-safe-all | C09 legacy es filesystem, no Steam. Casos Steam están dispersos y no llegan como categoría oficial dedicada. |
| C10 | Filesystem, carpetas y documentos locales | 37 | 30 | `NEEDS_REAL_CASES` | parcial/no-skip en live-safe-all | C10 legacy es terminal; filesystem está en C09 legacy. Numeración oficial rota. |
| C11 | Terminal, comandos y política | 49 | 30 | `NEEDS_REAL_CASES` | política-only/no-skip en live-safe-all | C11 legacy es safety/policy, no terminal. |
| C12 | Seguridad, permisos, confirmaciones y fake success | 40 | 30 | `NEEDS_REAL_CASES` | no-skip en live-safe-all | C12 legacy es misiones compuestas, no safety oficial. |
| C13 | GUI, visión, observación y reintentos | 47 | 30 | `COMPLETE_30_PLUS` | no-skip en live-safe-all | Cobertura compatible. |
| C14 | Misiones compuestas y autonomía por pasos | 46 | 30 | `NEEDS_REAL_CASES` | no-skip en live-safe-all | C14 legacy es typos/ambigüedad, no misiones compuestas. |
| C15 | Latencia, timeouts, recursos y progreso | 30 | 30 | `COMPLETE_30_PLUS` | completo | Cobertura compatible, pero guía oficial incluye recursos/progreso más amplio. |
| C16 | Multilingüe, typos e informalidad | 31 | 30 | `COMPLETE_30_PLUS` | completo | Cobertura compatible, aunque typos estaban parcialmente en C14 legacy. |
| C17 | Follow-ups, contexto limpio y contaminación | 31 | 30 | `COMPLETE_30_PLUS` | completo | Cobertura compatible. |
| C18 | Regresiones reales, residual y aceptación final | 30 | 30 | `COMPLETE_30_PLUS` | no-skip en live-safe-all | Cobertura compatible, pero no replica exactamente las 30 filas oficiales. |

## Hallazgos técnicos

1. La condición numérica `18 categorías x >=30` se cumple en el runner legacy.
2. La condición oficial semántica no se cumple porque la numeración y nombres C05-C14 no corresponden a la guía v3.
3. La categoría oficial C09 Steam no existe como categoría dedicada en el runner actual.
4. La categoría oficial C14 misiones compuestas está en C12 legacy.
5. La categoría oficial C12 safety está en C11 legacy.
6. La categoría oficial C11 terminal está en C10 legacy.
7. El runner `live-safe-all` ya elimina skips por política, pero eso no prueba por sí solo que los casos sean los oficiales.

## Decisión

No se puede declarar `CARTER_V3_18X30_TRUE_READY` con la matriz legacy tal como está.

## Plan de cierre

1. Crear una fuente de casos oficial que use `Carter_v3_GUIA_OFICIAL_TESTING (1).md` como fuente canónica.
2. Hacer que `audit/full_matrix_runner.py` ejecute por defecto la matriz oficial v3 C01-C18.
3. Mantener validadores reales del runner: no fake success, tool policy, memory policy, active-app policy, safety policy, observation integrity, mission integrity y latency budget.
4. Ejecutar la matriz oficial con `--mode live-safe-all --label full_18x30_true_ready`.
5. Si falla, crear `FULL_18X30_FAILURE_AUDIT.md`, reparar universalmente y reejecutar.
6. Solo declarar true-ready si el runner oficial ejecuta 540/540 con 0 skipped, 0 failed, 0 critical failures y pasan los gates finales.
