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

## Hallazgo colateral: leakage parcial training↔eval (744 textos)

Al construir B2 se midió: **744 textos están en AMBOS** `tool2vec_queries.jsonl`
(training del encoder) y `router_eval_corpus.curated.jsonl` (holdout). El holdout
se asigna por hash del texto, así que ~20% de esos 744 caen en holdout siendo
"vistos en training" → el holdout NO es 100% honesto (recall ligeramente
optimista). Es PRE-EXISTENTE (el corpus curado alimenta ambos pipelines), no
introducido por B2. Mejora futura: filtrar del training los textos que caen en
holdout (split-aware), o derivar el training de una fuente disjunta del eval.
No bloquea B2; se anota para que el número de holdout se lea con ese caveat.

## Ataque a los huecos (reentreno del encoder)

+62 ejemplos a `tool2vec_queries.jsonl` (find-app, salir-de-app, system-metric,
clipboard) en 6 idiomas → reentreno del encoder (seed 42). Resultado:

- **holdout 0.9751 → 0.9813** (subió: el encoder mejoró, no solo cerró huecos).
- huecos B2: **~6/16 → 10/16**. En vivo 3/3 verificados (find Photoshop→app,
  esci da Spotify→app.close, incollalo→clipboard).
- huecos previos de la misión: **25/25** intactos. Control sin romper.

**Residual diagnosticado (2 causas distintas, no de corpus):**
1. `what is the CPU usage`/`battery level` → [] AUNQUE el exemplar lo tiene como
   `system` a 1.000. Lo veta una capa POSTERIOR (abstención por "what is" / gate
   de pregunta), no el encoder. Es un problema de GATE, no de datos.
2. `find the calculator`/`finde Discord` → el exemplar de "find X" quedó a ~0.57
   (bajo umbral) — "find the X" embebe lejos de "abre X". Necesita más ejemplos
   o ajuste de umbral. Hueco de COBERTURA aún parcial.

## Vol2 — completar cobertura de tools en EN/IT/DE

Medido tras el primer lote: fr/pt YA bien (14-15/15 tools), el gap real era
EN/IT/DE (8-9/15). +59 ejemplos de eval para las tools faltantes (filesystem,
terminal, window, memory, gui) + corrección de etiquetas demasiado estrictas
(click/type aceptan gui|uia|computer_use por diseño). Validación expuso más
huecos (filesystem/terminal DE→[], window IT→computer_use); +20 al training →
reentreno consolidado.

Resultado: huecos vol2 **6/6 arreglados** en routing determinista ("erstelle
einen Ordner"→filesystem, "führe diesen Befehl"→terminal, "vai alla finestra
precedente"→window). Holdout 0.9813→0.9788 = medir más verdad (más casos EN/IT/DE
difíciles que ahora se cuentan). En vivo: el routing mejora pero el 4B no siempre
ELIGE la tool en DE (idioma de poca masa en su FT) — responde HONESTO ("keine
Aktion"), no miente. Residual del MODELO (techo 2B), no del router.

Distribución DESPUÉS de vol2: es 76%, pt 10%, fr 8%, en 2%, it/de ~1%. EN/IT/DE
pasaron de 8-9/15 a cobertura completa de las tools clave.

## Residual del gate de abstención (INTENTADO, no resuelto — impedimento)

"what is the CPU usage" / "what is the battery level" (EN) → `[]` aunque
`_suggest_tools` SÍ ofrece `system`. Diagnóstico profundo (2026-06-10):

- `_suggest_tools('what is the CPU usage')` = `['system']` ✓ (la guarda
  concepto-vs-métrica funciona).
- Pero `select_tool_names` FINAL = `[]`: el `system` se borra entre medio.
- Causa: `wants_knowledge('what is the CPU usage')` = True → el router lo trata
  como pregunta del mundo y el `system` no sobrevive al pipeline
  head→abstain→semantic-fallback→web-nav-filter.

INTENTADO (5 ediciones, REVERTIDAS): helper `_is_local_system_metric` +
protegerlo en `_kw_protect` + forzarlo a `names` antes de `expanded`. NINGUNA
funcionó: el `system` se borra en una capa que NO se logró localizar sin
instrumentar el flujo COMPLETO. `names` se reasigna en ~6 puntos entre el abstain
y el return (L1104/1116/1119/1249/1345/1356), y el bloque final web-nav/
info-lookup (L1402-1448) puede quitarlo de nuevo. Parchear capa-por-capa SIN
mapear el flujo entero viola el mandamiento #4 (causa raíz antes de parchear) y
arriesga el router → REVERTIDO al estado bueno (acc4a74), 25/25 huecos intactos.

**IMPEDIMENTO declarado:** este residual es un bug de ARQUITECTURA multi-capa del
router (no de corpus ni de un gate único). Requiere una sesión dedicada que
instrumente `select_tool_names` end-to-end (loguear `names` tras cada reasignación
para una query métrica-local) y decida UN punto canónico donde proteger los
datos-locales del veto de conocimiento — probablemente unificando `_is_local_
datetime` + `_is_local_system_metric` + `_is_local_state_question` en una sola
guarda "LOCAL-FACT" aplicada al final del pipeline. Workaround actual: el caso ES
("cuánto uso de CPU") SÍ rutea bien; solo el frame EN "what is the X" cae. En vivo
el guard de honestidad evita que el 4B mienta (responde sin inventar).

## Conclusión: B2 base sólida establecida (ítem grande, multi-sesión)

B2 cumplió su objetivo CENTRAL: el corpus de eval pasó de **medir solo español**
(holdout 0.9800 sesgado) a **medir y mejorar EN/IT/DE** (holdout multilingüe
honesto ~0.978, con los huecos reales contándose). Destapó ~13 huecos del router
ocultos por el sesgo; cerró la mayoría de raíz vía reentreno.

PATRÓN observado: cada lote de corpus expone más huecos → más datos → reentreno.
Rendimientos decrecientes. B2 es un ítem **grande de varias sesiones**, no se
cierra de una. Lo que queda es trabajo incremental: más volumen, atacar el
residual del gate de abstención (head↔suggest↔abstain), y B1/B4 (reentreno con
corpus balanceado + calibración por idioma) que ahora SÍ tienen base.

## Estado

- Corpus B2 commiteado (etiquetas curadas; "who is X"→web corregido).
- Distribución DESPUÉS: es 73%, pt 10%, fr 7%, en/it/de ~2.3% c/u (de 0-1%).
  Sigue sesgado pero EN/IT/DE pasaron de casi-cero a cobertura de las tools clave.
- PENDIENTE: (a) seguir balanceando (fr/pt a paridad de categorías; más volumen
  EN/IT/DE), (b) atacar los 6-7 huecos hallados, (c) B1 (reentreno encoder con el
  corpus balanceado) y B4 (calibración abstain por idioma) que dependían de B2.
