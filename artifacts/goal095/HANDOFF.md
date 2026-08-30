# Handoff — 09.5.0 — 2026-08-30

## Objetivo
Demostrar que todas las fuentes del linaje están presentes, copiadas del todo e
identificadas sin modificarlas. Cierre: universo estable **o** `FALLO_DE_AMBIENTE`.

## Estado
Hecho: preflight de `Programacion`, aliases, Git de BAXY/Carter, SHA-256 de
FunctionGemma y Probando Gemma 4, snapshots A/B, before/after Git idéntico,
informe `documentacion/herencia/09_5_FUENTES.md`.
En curso: nada. La sesión cierra `FALLO_DE_AMBIENTE`.
Sin empezar: 09.5.1 manifiesto y colas.

## Decisiones tomadas
- `D:\BAXY` y `D:\BAXYRuntime` no cuentan como generaciones independientes.
  `D:\BAXY\source` es otro HEAD del mismo remoto que `Programacion\BAXY`
  (`c57c7aff` ≠ `203c34a9`). `D:\BAXY\FunctionGemma` (3 ficheros) no es
  duplicado de `Programacion\FunctionGemma`.
- `ETC (No relacionado con baxy)` queda fuera: nombre + primer nivel de curso.
- Schema Agent descrito en `documentacion/25_INTEGRACION_GENERACIONAL_*.md` vive
  en historial Git de BAXY; eso no localiza la carpeta que 09.5.0 exige.
- Completitud de `Probando Gemma 4` se mide contra el mapa 01 (`models` ~17 GiB,
  `data` ~39 GiB), no contra «la carpeta existe».

## Archivos tocados
- `documentacion/herencia/09_5_FUENTES.md` — inventario y veredicto
- `artifacts/goal095/environment/09.5.0.md` — receta de ambiente
- `artifacts/goal095/environment/sources_index.json` — índice máquina
- `artifacts/goal095/sources/*.sha256.jsonl` — identidad de árboles sin Git
- `artifacts/goal095/scripts/hash_tree.py` — receta del manifiesto

## Archivos relevantes aún sin tocar
- `documentacion/sprints/09.5.1_MANIFIESTO_Y_COLAS.md` — siguiente **después**
  de un 09.5.0 verde
- `documentacion/herencia/00_MAPA.md` — no se reescribe en el fallo

## Hipótesis
Confirmadas: no hay copia viva (0 procesos; A=B). Git históricos no mutados
(HEAD + `status` SHA-256 iguales).
Descartadas: «FunctionGemma a medias» → 34,4 GiB, sentinelas del mapa 01,
estable. «`Probando schemas` podría ser FunctionGemma/schemas» → no hay carpeta
con ese nombre; Agent/Function Schema tampoco.

## Comandos ejecutados y resultado
- Recuento A/B → BAXY 116641/25488709507, Carter 136316/14935292111,
  FunctionGemma 1090/34366705385, Probando Gemma 4 36249/3690624981; A=B.
- `hash_tree.py` FunctionGemma → manifiesto `ff150df2…619eaa` (59,96 s, 0 errores).
- `hash_tree.py` Probando Gemma 4 → manifiesto `72f9e5fc…13c7e71` (520,71 s, 0 errores).
- Git before/after BAXY `203c34a9` / Carter `9cf62d23` / status SHA iguales.
- Compuerta Full: no ejecutada — no hay cambio de producto; el goal para en
  ambiente.

## Problemas pendientes
- Copiar `Probando schemas` y Agent/Function Schema a `Programacion\`.
- Completar `Probando Gemma 4\models` y `\data` hasta el tamaño del mapa 01.
- Owner: ambiente. Luego la misma sesión 09.5.0.

## Siguiente acción recomendada
Preparar el PC con `artifacts/goal095/environment/09.5.0.md` (prueba
`READY=1`) y relanzar `documentacion/sprints/09.5.0_FUENTES_Y_AMBIENTE.md`.
