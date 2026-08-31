# Handoff — 09.5.11A revalidar 01–03C — 2026-08-31

## Objetivo
Demostrar que la herencia reconciliada conserva o mejora los cierres 01–03C.

## Estado
Hecho: matriz 01–03C, holdouts de procedencia/catálogo/comprensión/reproducibilidad,
mapa FieldUi actualizado sin borrar el hallazgo, next=09.5.11B.
En curso: nada. Sin empezar: 09.5.11B.

## Decisiones tomadas
- Cola transplant vacía no exime holdouts; sí exime reejecutar compuesto/VRAM/17 ms.
- Sello de catálogo 03C se conserva como identidad histórica; el vivo documenta
  `input.visible.click` (cascada). Conteos 169/158/31.
- El arnés de comprensión espera el deadline de promoción E5 del producto (185 s);
  no se relajó `score` ni `_final_operations`.
- Cero aplazos al Goal 10.

## Archivos tocados
- `artifacts/goal095/synthesis/09.5.11A_revalidar_01_03C.v1.json` — matriz machine-readable
- `artifacts/goal095/ledger/revalidate-09.5.11A.json` — ledger 09.5.11A
- `documentacion/herencia/09_5_11A_REVALIDAR.md` — cierre documental
- `artifacts/goal095/revalidate/goal03_catalog_coverage_goal09511a.json` — cobertura hello
- `artifacts/goal095/revalidate/goal03_goal09511a_r*.json` — tres corridas
- `documentacion/herencia/00_MAPA.md` — actualización FieldUi
- `tests/test_goal095_09511a_revalidate.py` — prueba dueña

## Archivos relevantes aun sin tocar
- `documentacion/sprints/09.5.11B_REVALIDAR_04_06.md` — se nombra, no se ejecuta
- `src/` — no cambia por 09.5.10; holdouts no exigieron owner de producto

## Hipotesis
Confirmadas: 169/158/31 se sostiene; mediana served y acted caben en los listones 03C
(113/124, acted [1, 1, 1]).
Descartadas: «cola vacía = no medir». «Sustituir holdout con telemetría 03C».

## Comandos ejecutados y resultado
- comprensión r1/r2/r3 served [113, 113, 113] acted [1, 1, 1] p50 [3.807, 3.778, 3.832]
- catálogo 169/158/31 sello 2231d681fb396c12…
- `.\scripts\test_source_quality.ps1` → source_quality_gate_passed: mode=Fast; EXIT=0
- validate_report errors=[]

## Problemas pendientes
Ninguno de 09.5.11A. No ejecutar 09.5.11B en esta meta.

## Siguiente accion recomendada
`documentacion/sprints/09.5.11B_REVALIDAR_04_06.md` (sesión nueva, un pegado).
