# FULL_18X30_FAILURE_AUDIT

Fecha: 2026-05-06

## Veredicto

`FAILURES_FIXED_AND_REVALIDATED`

Durante el cierre oficial 18x30 hubo fallos reales iniciales. No se declaró ready hasta corregirlos y reejecutar la matriz completa.

## Corridas relevantes

### Primera corrida oficial completa

Artifact: `audit/runs/full_18x30_true_ready.json`

- total=540
- executed=540
- skipped=0
- passed=504
- failed=36
- global=93.33%
- validator_failures=`tool_policy: 36`

Clases principales:

- C04 memoria no persistía/recuperaba preferencias oficiales de forma verificable.
- C06 router no usaba tools read-only en varios casos oficiales.
- C10 filesystem no enrutaba búsquedas/lecturas oficiales sin ruta explícita.
- C12 active-window policy podía consultar ventana activa al pedir uso global.
- C15/C16 recursos/volumen/typos no tenían ruta estructural suficiente.
- C17/C18 regresiones de contexto/filesystem/volumen.

### Segunda corrida completa

Artifact: `audit/runs/full_18x30_true_ready_v2.json`

- total=540
- executed=540
- skipped=0
- passed=535
- failed=5
- global=99.07%
- validator_failures=`tool_policy: 5`

Fallos restantes entonces:

| ID | Categoría | Diagnóstico | Acción |
|---|---|---|---|
| C07.19 | Apps/ventanas | pregunta de ventanas abiertas no ejecutaba `window_list` | ruta directa read-only para conteo/listado de ventanas |
| C07.29 | Apps/ventanas | caso `session/window` era ambiguo y no debía exigir tool | metadata oficial marcada opcional |
| C09.29 | Steam | verificación de app abierta no usaba ventana/proceso | ruta directa genérica `está abierto` -> `window_list` |
| C14.04 | Misiones | `files/apps` no estaba mapeado en metadata | mapeo oficial para `files/` y efectos side-effect opcionales |
| C14.18 | Misiones | `files` sin sufijo no estaba mapeado | mapeo oficial para `files` genérico |

## Reparaciones aplicadas

- Añadida fuente de matriz oficial: `audit/official_matrix_cases.py`.
- `audit/full_matrix_runner.py` ahora importa la matriz oficial v3 desde la guía canónica.
- Seguridad de `live-safe-all` conservada: side effects siguen bloqueados por policy.
- Memoria explícita oficial:
  - `recuerda que ...` guarda en memoria real local.
  - consultas oficiales recuperan memoria real.
  - borrados amplios piden confirmación/bloquean.
  - secretos como contraseña/RUT no se guardan.
- Rutas read-only directas y verificadas para:
  - procesos;
  - ventanas;
  - recursos RAM/CPU/GPU;
  - filesystem read/list/search acotado;
  - logs/proyecto (`RESIDUAL.md`, `CHANGELOG.md`).
- Restricciones explícitas respetadas:
  - `sin usar herramientas` no dispara tools;
  - `no uses ventana activa` no observa la ventana activa;
  - `usa ventana activa como contexto siempre` se rechaza sin consultar ventana.
- Metadata oficial corregida para distinguir:
  - read-only real vs side-effect bloqueable;
  - optional/confirmable/contextual tools;
  - `files.open/apps`, `files`, `session/window`, `window/apps`.

## Corrida final revalidada

Artifact: `audit/runs/full_18x30_true_ready_final_v2.json`

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

## Decisión

Los fallos de la matriz oficial 18x30 quedaron cerrados con correcciones universales y revalidación completa.
