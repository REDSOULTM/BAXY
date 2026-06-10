# B2 — Corpus multilingüe de eval: construcción y hallazgos (2026-06-10)

## Qué se hizo

El corpus de eval del router (`router_eval_corpus.curated.jsonl`) estaba sesgado
al español. Distribución medida ANTES:

| idioma | ejemplos | % |
|--------|---------:|--:|
| es | 1471 | 79% |
| pt | 207 | 11% |
| fr | 150 | 8% |
| en | 27 | 1% |
| it | 4 | 0% |
| de | 2 | 0% |

Cobertura de las 15 tools top-ES en los idiomas huérfanos: **EN 6/15, IT 3/15,
DE 0/15**. Validar cualquier mejora multilingüe contra esto era ciego en EN/IT/DE.

**Construcción:** +141 ejemplos NATURALES (no traducción literal) en EN/IT/DE,
47 por idioma, cubriendo las tools clave (app, window, audio, system, media, web,
browser, device_settings, reminder, vision, clipboard) + charla (`[]`). Etiqueta
= tool de diseño. `source=b2_multilingual_eval_2026-06-10`.

## Hallazgos: B2 expuso huecos reales del router en EN/IT/DE

La validación del corpus contra el router (concordancia etiqueta↔routing) dio:
EN 89%, IT 85%, DE 78%. Los mismatches NO son ruido — son **huecos reales** que
el corpus sesgado al ES nunca habría detectado. Pendientes a atacar:

| caso | esperado | router da | hueco |
|------|----------|-----------|-------|
| `find Photoshop` (EN) | app | web+knowledge | "find X" (buscar app instalada) confundido con pregunta |
| `trova Photoshop` (IT) | app | web | "trova X" idem |
| `esci da Spotify` (IT) | app | media+browser | "esci da" (salir de) no rutea a app.close |
| `what is the CPU usage` (EN) | system | [] | métrica de sistema en EN no rutea |
| `cosa c'è negli appunti` (IT) | clipboard | [] | clipboard query IT no rutea |
| `incollalo` (IT) | clipboard | [] | "pégalo" IT no rutea |
| `what a nice day` / `che bella giornata` | [] | local_calendar | over-firing leve: "day/giornata"→calendar |

## Lección

El corpus de eval ES la herramienta de medición. Un corpus sesgado a un idioma
**oculta** los huecos de los demás: estos 6-7 huecos existían hace tiempo pero
eran invisibles porque no había ejemplos EN/IT/DE que los ejercitaran. B2 los
hace medibles. Atacarlos es trabajo futuro (cada uno es exemplars + posible
reentreno, como los 4 huecos de la misión).

## El holdout "bajó" 0.9800→0.9751 — NO es regresión, es medir la verdad

Tras agregar B2, el holdout recall pasó de **0.9800 a 0.9751** (−0.0049). Esto NO
es que el router empeore: es que ahora el holdout **incluye los huecos reales de
EN/IT/DE** que antes no se medían (el corpus era 79% ES). El router siempre falló
"find Photoshop"→app; antes era invisible, ahora se cuenta. **El 0.9800 era
artificialmente alto por el sesgo; el 0.9751 es el recall multilingüe REAL** —
más honesto. Cualquier mejora futura a los huecos hallados subirá este número de
verdad. No revertir el corpus para "recuperar" el 0.9800: sería esconder la cabeza.

## Estado

- Corpus B2 commiteado (etiquetas curadas; "who is X"→web corregido).
- Distribución DESPUÉS: es 73%, pt 10%, fr 7%, en/it/de ~2.3% c/u (de 0-1%).
  Sigue sesgado pero EN/IT/DE pasaron de casi-cero a cobertura de las tools clave.
- PENDIENTE: (a) seguir balanceando (fr/pt a paridad de categorías; más volumen
  EN/IT/DE), (b) atacar los 6-7 huecos hallados, (c) B1 (reentreno encoder con el
  corpus balanceado) y B4 (calibración abstain por idioma) que dependían de B2.
