# Fase 3.5 — progreso (fuente de verdad ante un corte)

Sesión Opus 5.5, rama `codex/kiro-goal-c03`, punto de partida tag `opus55-inicio` = b5c9fe72 (lo creó esta sesión;
ver DECISIONES_OPUS_2026-09-22.md). **Meta vigente: `META_SEMANTICA_TOTAL_2026-09-22.md`** (sustituye la lista de 13
entregables; lo hecho se hereda). Al retomar: leer esto, `git status --short`, `git log --oneline opus55-inicio..HEAD`.
Un comando largo a medias se vuelve a correr entero.

## Entregables de la meta

| # | Entregable | Estado |
|---|---|---|
| 1 | Clase 1 (hueco de diálogo) cerrada y commiteada con la cifra de c1c | hecho (dueño 39/60, held-out 22/30, 742 sin cambios, pytest 13 591 verdes tras re-anclar sellos) |
| 2 | Baseline por capas (A, B, C por dominio y tipo de fallo) sobre b5c9fe72 y sobre el HEAD con la clase 1 | hecho: `SEMANTICA_CAPAS_2026-09-23.md` (por commitear) |
| 3 | `src/baxy_mind/semantic/` (puerta `read()`, dominios, normalización única, identidad/límites); lectores viejos retirados; commit por dominio | en curso: S2 commiteado; S3 sin commitear = 13 dominios acíclicos trasladados (intent, catalog, temporal, audio, windows, display, media, web, files, games, network, system, notes, messaging, ui, apps; effect_intent 19 140 → 13 133 líneas; traslado puro: 0 diferencias en 4 946 lecturas del patrón, 3 275 pruebas) + misiones compuestas (oferta parcial) + rechazo en el hueco |
| 4 | `documentacion/SEMANTICA.md` (diez minutos; de qué BAXY anterior se heredó cada pieza) | borrador escrito (por commitear) |
| 5 | Cierre: capa A ≥ 95 %, held-out nuevo del dueño ≥ 95 %, Full verde, cien 100/100, sellos, `SEMANTICA_<fecha>.md` | pendiente |

Heredado y hecho: harness `scripts/semantic_replay.py` (+ guardia de VS Code), held-out del 22 congelado,
`SEMANTICA_BASELINE_2026-09-22.md`. Las clases 2–5 pasan al dominio `dialogue` de `semantic/`; sus parches
preparados siguen en el scratchpad (`patch_guard.py`, `patch_veto.py`).

## Tabla por capas (última cifra medida y comando)

| Capa | Filas tras filtros (es/en + dirigido a BAXY) | Bien | Comando |
|---|---|---|---|
| A — real del dueño | 772 (encuesta 676 + registro real 95 + 1) | b5c9fe72 96,1 % (real 74,7 %) → clase 1 97,1 % (real 83,5 %) → S2 98,0 % (real 89,0 %) | `semantic_corpus.py score <742+capas> --survey-reference S/lit-base.jsonl` |
| B — herencia curada | 106 | 27,4 % → 27,4 % → S2 28,3 % | ídem |
| C — corpus sintéticos | 4 066 (muestra 1 000) | 54,4 % → 54,4 % → S2 54,7 % | ídem (`sample --size 1000`) |
| Held-out nuevo del dueño | se pide al final | — | — |

## Guiones contextuales (heredados)

| Guion | Baseline b5c9fe72 | Clase 1 (c1c) |
|---|---|---|
| dueño 2026-09-21 (60) | 33/60 | 39/60 → S2 45/60 (contexto 9/12, guarda 4/8, paráfrasis 0/5, familia 1/1, efecto inventado 1/1, fuera de alcance 5/8) |
| held-out 2026-09-22 (30) | 15/30 | 22/30 → S2 26/30 (contexto 6/9, guarda 6/6, paráfrasis 0/1, familia 4/4, efecto inventado 1/1, fuera 2/2) |
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

## Incidente 2026-09-23 04:44 (no fue BAXY)

Windows Update reinició el PC (`MoUsoCoreWorker.exe` y `TrustedInstaller.exe`, evento 1074, «actualización
(planeada)») con la réplica de capas S5 en 1 055/1 221. El dueño avisó: nada de reinicios, apagados ni cierres de
sesión. Las réplicas sólo-decisión no ejecutan efectos. Antes de un comando largo se mira si hay un reinicio pendiente.
S5 se completó corriendo sólo las filas que faltaban (`S/corpus_rest_s5.jsonl` → `S/layers-s5b.jsonl`, más
`S/layers-s5a.jsonl`). S5 742: 2 decisiones distintas de S2 (H0506 memoria; H0175 «en Discord apretá enter» → clic,
arreglado después de la instantánea: una tecla nunca es un control visible).

## Cambios sin commitear (S3)

- Traslado de dominios (arriba). Pureza: `S/pattern_dump.py` sobre snap-s2 y el árbol → 0 diferencias.
- Misiones compuestas: `_catalog_unavailable_turn_decision` leía «abre Spotify y baja el volumen» entero como nombre de
  juego → «no puedo». Ahora no aplica a una compuesta (contrato o cláusulas coordinadas con la primera probada). Un final
  «unsupported» con cláusulas probadas y otras no → aclaración que cita ambas partes y pregunta; `objective` = parte
  probada (un «sí» la retoma). Pruebas `tests/test_semantic_compound_offer.py`.
- Hueco: `_REFUSAL` («no, dejalo», «mejor no») nunca completa el pedido pendiente.
- `semantic_corpus.py`: familias memory.* fuera de la puntuación (ruta del shell).

## Próximo paso

Medir S5 (= S4 + veto «análisis de la solicitud», vocativos Gemma/Carter/Alexa, silenciar el PC, «sacá una captura», destino delante; capa B §12) desde `S/snap-s5` (`lit-s5`, `layers-s5`). S4 era: S3 + lectores de opinión/hecho fechado, orden tras charla, comilla sin cerrar) desde `S/snap-s4`: `literals --src S/snap-s4 --out S/lit-s4.jsonl` (S3: 1 decisión distinta vs S2, H0506 memoria), capas `--out S/layers-s4.jsonl`,
(`--corpus corpus_run.jsonl --skip-survey --out S/layers-s3.jsonl`), conv dueño+held-out con guardia; commit «semantic S3».
Luego: dominio de memoria, paráfrasis/fechas (web.search), aclaraciones sin sentido (dueño 28), B/C por tipo de fallo.
