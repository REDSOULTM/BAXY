# Handoff — 09.5.0 run2 — 2026-08-30

## Objetivo
Congelar las cuatro fuentes mínimas con material intelectual identificable, sin
exigir blobs pesados ni carpeta Schema ni `.git`. Cierre verde o `FALLO_DE_AMBIENTE`.

## Estado
Hecho: preflight run2; A=B=recuentos `5db4d64`; manifiestos SHA-256 reutilizados;
Schema Agent anclado a refs Git de BAXY; `09_5_FUENTES.md` verde.
En curso: nada.
Sin empezar: 09.5.1.

## Decisiones tomadas
- No se altera `artifacts/goal095/environment/09.5.0.md` (fallo histórico).
- No se rehashea FunctionGemma ni Probando Gemma 4: mismos ficheros/bytes/`newest`.
- `Probando schemas` no es fuente. Schema Agent = `origin/Tools-Reduce`,
  `origin/vram4_lean`, `v0.9.2` dentro de `Programacion\BAXY`.
- FunctionGemma sin `test_*.py` se registra; no bloquea (hay evals en `ops\`).
- `D:\BAXY` sigue relacionado, no independiente.

## Archivos tocados
- `documentacion/herencia/09_5_FUENTES.md` — cierre PASS de esta corrida
- `artifacts/goal095/run2/*` — snapshots, índice, reuso de manifiestos, sentinelas
- `artifacts/goal095/HANDOFF.md` — este handoff

## Archivos relevantes aún sin tocar
- `documentacion/sprints/09.5.1_MANIFIESTO_Y_COLAS.md`
- `artifacts/goal095/environment/09.5.0.md` — se conserva
- `artifacts/goal095/sources/*.sha256.jsonl` — se reutilizan

## Hipótesis
Confirmadas: snapshot idéntico a `5db4d64`; Git históricos no mutados; refs Schema
existen en BAXY.
Descartadas: «hay que hashear otra vez» → conteos iguales. «Falta pytest en
FunctionGemma ⇒ incompleto» → hay `ops\eval_*.json` y schemas.

## Comandos ejecutados y resultado
- Recuento run2 A/B = run1: BAXY 116641/25488709507, Carter 136316/14935292111,
  FunctionGemma 1090/34366705385, PG4 36249/3690624981.
- `git rev-parse origin/Tools-Reduce` → `e6f9c1e5`; `vram4_lean` → `c5f65e9a`;
  tag `v0.9.2` commit `398f120c`.
- Git status SHA vs run1: BAXY `b0508200…`, Carter `3adb0157…`, iguales.
- Full: no. No hay cambio de producto.

## Problemas pendientes
Ninguno de ambiente. 09.5.1 debe abrir `sparse_exclusions` con `models`/`data`
omitidos de PG4.

## Siguiente acción recomendada
Lanzar `documentacion/sprints/09.5.1_MANIFIESTO_Y_COLAS.md` en sesión nueva.
