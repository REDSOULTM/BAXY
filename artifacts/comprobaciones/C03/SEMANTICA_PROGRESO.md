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

## Después de bdbd0e66 (S3 commiteado)

Guiones con el producto sobre bdbd0e66 (`S/s3c`): held-out 26→27/30; dueño 45→41/60 (+3 revisar). Regresiones
de contexto analizadas: 50 «baxy, cierra baxy» (la oferta tomaba el vocativo como cláusula), 29/40 (la causa
`request_analysis_failed` sin hecho → el modelo la leía y el veto nuevo la rechazaba tres veces), 59 «investigala»
tras una pregunta por una obra (sin antecedente). Arreglos sin commitear: vocativo fuera de las cláusulas y toda
cláusula debe ser orden; hecho para `request_analysis_failed` en `_CAUSE_FACT`; `dialogue.asked_about` como
antecedente de un pronombre tras una pregunta pública; lecturas (hora «exacta»/«porfa», «quiero saber quién es»,
app activa). `S/s4c` con revisiones: dueño 47/60, held-out 27/30 (74/90). 742 sobre `S/snap-s6`: 1 decisión
distinta de S2 (H0506, memoria del shell). Después de S6, sin medir aún: hecho de `request_analysis_failed` sin «no
entendí»; acto de charla (`dialogue.talk_act` + `__main__._talk_act_turn_decision`: afirmación en primera persona,
queja sobre BAXY, reacción → conversación social con historial; nunca con una orden, un pedido leído, deseo o
reproche que repite un pedido, verbo de búsqueda o, en una afirmación, una palabra del PC). Pendiente conocido: turno
23 (el compositor del informe de búsqueda rechaza y corta el borrador: `search_report_unsourced_claim`,
`cut_by_length`), turno 22 (título de la ventana de PotPlayer), 16 (canción de amor: pregunta Spotify).

S5c (con acto de charla y deseo de música): dueño 52/60, held-out 27/30 (79/90; guarda 13/14, efecto inventado
2/2). Capas S6: A 98,6 % (real 93,4 %), B 55 %, C 55,1 %. Después: volumen «al mínimo» y voseo «subí … N puntos»,
verbo de búsqueda delante de una pregunta datada o de opinión, dativo con objeto dicho no es referencia («devolvele el
sonido»). Midiendo S7 desde `S/snap-s7`: `lit-s7`, `layers-s7` (`S/corpus_run_s6.jsonl`), luego conv `S/s6c`.

S7 medido (`S/snap-s7`): 742 con 1 decisión distinta de S2 (H0506); capas A 98,3 % (real 83/91: log:115/117
«me gusta crear cosas como tú» con el historial real viejo, que contiene la respuesta mala de BAXY; en el producto
—s6c— el mismo turno sale bien), B 55 %, C 55,5 %; guiones s6c con revisiones: dueño 54/60, held-out 27/30 (81/90).
Commit «semantic S4». Sin medir en capas (probado con 3 404 pruebas): argumento de «devolvele el sonido», léxico de
restaurar con clíticos generados, palabras función en la contención, «escuchar X» como música, control de video,
«qué dice … en la pantalla», oscurecer/aclarar la pantalla.

S5 (commit siguiente a b15cae45): el orquestador del patrón (180 nombres, 12 222 líneas) pasa de effect_intent a
`semantic/patterns.py` (traslado puro: 0 diferencias en 4 946 lecturas contra el árbol de b15cae45); effect_intent
queda en 687 líneas de re-exportación. pytest completo (`PYTHONPATH=src … -m pytest tests`): primera corrida 8 rojos —
«averiguá si tengo Krita / la distribución de entrada…» iban a la web porque S4 añadió «averigua» al lector de
investigación de temas; revertido (se usa para comprobaciones locales) → 13 711 verdes, 0 rojos.

S6: puerta `semantic.reading.read() -> Reading` (efectos del patrón y de las formas de enunciado, aclaración, charla)
consumida por `__main__._decide_turn_result`; 19 nombres de __main__ a `semantic/reading.py`. `_PLAY_HEAD` único con
voseo: «poné/poneme/reproducí … en youtube» no se leía (5 filas del corpus cambian, las 5 a media.play.youtube, igual
que «pon…»). pytest completo 13 718 verdes. Siguiente: medir S8 (guiones + 742 + capas), luego Full (.NET + pytest) y
cien 100/100, y pedir al dueño el held-out nuevo.

S8 (HEAD 10dbcf34): guiones con el producto dueño 53/60 tras revisar el 35, held-out **29/30**; 742 con 1 decisión
distinta de S2 (H0506); capas en curso (`S/layers-s8.jsonl`). Después, sin commitear: re-armado de destino por patrón
(held-out 18). Antes de la cien: comprobar con una decisión real que «close that» / «cierra aquello» siguen
preguntando el referente (el patrón ya daba app.close en opus55-inicio; lo convierte en pregunta el turno).

cien-99 sobre c47377c6: 100 publicadas, 0 agotes, 97 limpias (074 veto por «caché», 097 prohibición re-armada,
049 asentimiento a «haz eso»); arreglado en S8. Full (`scripts/test_source_quality.ps1 -Mode Full`) **verde**: ruff
(tras quitar importaciones duplicadas de los traslados; `_KNOWN_FOLDER_*` definido una vez, en display, que era el valor
que regía en el módulo original), .NET 4 903 pruebas, pytest 13 728. Siguiente: cien-100 sobre el commit S8.

## Próximo paso

Medir S5 (= S4 + veto «análisis de la solicitud», vocativos Gemma/Carter/Alexa, silenciar el PC, «sacá una captura», destino delante; capa B §12) desde `S/snap-s5` (`lit-s5`, `layers-s5`). S4 era: S3 + lectores de opinión/hecho fechado, orden tras charla, comilla sin cerrar) desde `S/snap-s4`: `literals --src S/snap-s4 --out S/lit-s4.jsonl` (S3: 1 decisión distinta vs S2, H0506 memoria), capas `--out S/layers-s4.jsonl`,
(`--corpus corpus_run.jsonl --skip-survey --out S/layers-s3.jsonl`), conv dueño+held-out con guardia; commit «semantic S3».
Luego: dominio de memoria, paráfrasis/fechas (web.search), aclaraciones sin sentido (dueño 28), B/C por tipo de fallo.
