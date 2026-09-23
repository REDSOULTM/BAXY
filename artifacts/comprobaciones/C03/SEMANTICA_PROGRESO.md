# Fase 3.5 — progreso (fuente de verdad ante un corte)

Sesión Opus 5.5, rama `codex/kiro-goal-c03`, punto de partida tag `opus55-inicio` = b5c9fe72 (lo creó esta sesión;
ver DECISIONES_OPUS_2026-09-22.md). **Meta vigente: `META_SEMANTICA_TOTAL_2026-09-22.md`** (sustituye la lista de 13
entregables; lo hecho se hereda). Al retomar: leer esto, `git status --short`, `git log --oneline opus55-inicio..HEAD`.
Un comando largo a medias se vuelve a correr entero.

## Entregables de la meta

| # | Entregable | Estado |
|---|---|---|
| 1 | Clase 1 (hueco de diálogo) cerrada y commiteada con la cifra de c1c | hecho (dueño 39/60, held-out 22/30, 742 sin cambios, pytest 13 591 verdes tras re-anclar sellos) |
| 2 | Baseline por capas (A, B, C por dominio y tipo de fallo) sobre b5c9fe72 y sobre el HEAD con la clase 1 | pendiente |
| 3 | `src/baxy_mind/semantic/` (puerta `read()`, dominios, normalización única, identidad/límites); lectores viejos retirados; commit por dominio | pendiente |
| 4 | `documentacion/SEMANTICA.md` (diez minutos; de qué BAXY anterior se heredó cada pieza) | pendiente |
| 5 | Cierre: capa A ≥ 95 %, held-out nuevo del dueño ≥ 95 %, Full verde, cien 100/100, sellos, `SEMANTICA_<fecha>.md` | pendiente |

Heredado y hecho: harness `scripts/semantic_replay.py` (+ guardia de VS Code), held-out del 22 congelado,
`SEMANTICA_BASELINE_2026-09-22.md`. Las clases 2–5 pasan al dominio `dialogue` de `semantic/`; sus parches
preparados siguen en el scratchpad (`patch_guard.py`, `patch_veto.py`).

## Tabla por capas (última cifra medida y comando)

| Capa | Filas tras filtros (es/en + dirigido a BAXY) | Bien | Comando |
|---|---|---|---|
| A — real del dueño | pendiente | pendiente | — |
| B — herencia curada | pendiente | pendiente | — |
| C — corpus sintéticos | pendiente | pendiente | — |
| Held-out nuevo del dueño | se pide al final | — | — |

## Guiones contextuales (heredados)

| Guion | Baseline b5c9fe72 | Clase 1 (c1c) |
|---|---|---|
| dueño 2026-09-21 (60) | 33/60 | 39/60 (contexto 5/12, guarda 2/8, paráfrasis 1/5, familia 1/1, efecto inventado 0/1, fuera de alcance 5/8) |
| held-out 2026-09-22 (30) | 15/30 | 22/30 (contexto 5/9, guarda 5/6, paráfrasis 0/1, familia 2/4, efecto inventado 1/1, fuera 2/2) |
| 35 bancos | 398/525 | sin medir |
| 742 sólo-decisión | 0 errores; determinista (dos corridas idénticas) | 0 decisiones distintas (`S/lit-c1.jsonl`) |

Comandos (`S` = scratchpad de la sesión; python = `%LOCALAPPDATA%\BAXYRuntime\python\mind-runtime-v1\Scripts\python.exe`):
`semantic_replay.py conv --out S/c1c --label sem-c1c --idle 30 --reviews artifacts/comprobaciones/C03/contexto/semantic_reviews.json <guiones>`,
luego `rescore` con las mismas revisiones; `semantic_replay.py literals --out S/lit-c1.jsonl` y `diff S/lit-base.jsonl S/lit-c1.jsonl`.

## Incidente 2026-09-22 (no repetir)

El held-out cerró VS Code dos veces (y con él esta sesión): «cerralo» se leyó como «la ventana activa» y «sí, dale»
lo confirmó. Arreglos: el pronombre con antecedente toma el objeto del pedido anterior (`dialogue_slot.substituted_reference`);
el harness pone una ventana guardia propia en primer plano y aborta si el proceso raíz de VS Code desaparece.
Las capas A/B/C se corren sólo-decisión, nunca con efectos.

## Cambios sin commitear

Clase 1 entera (shell + mente + harness con guardia + pruebas), baseline con bancos y 742, decisiones §3–4, la meta.

## Próximo paso

diff de los 742 → commit y push de la clase 1 → filtros de idioma y destinatario sobre
`tests/data/historical_messages.jsonl` → baseline por capas.
