# Historial de sprints (router mastery)

> Qué se hizo y por qué, con resultados MEDIDOS. Programa "router al estado
> máximo" pedido por el usuario el 2026-05-29. Cada sprint tiene su commit.

---

## Línea de tiempo

| Sprint | Commit | Qué | Resultado medido |
|--------|--------|-----|------------------|
| **S0** | `2ef7f8e` | Extender `router_eval.py` para MEDIR PRECISIÓN (ruido) + fix ceguera cp1252 | El ruido se volvió visible (antes invisible) |
| **S1a** | `c996ba2` | `_RELATED_BUDGET` 3→1 | Ruido **1.86→1.63**, recall idéntico (0.9964) |
| **S1b** | `692d0b7` | Infra de cluster-collapse, **gated OFF** | Medido que pierde recall (0.9964→0.9820) → OFF |
| **S2** | `3679499` | Builder de corpus desde LOGS REALES | **1071 pares reales; recall real = 85.7%, NO 99.6%** |
| **S3a** | `c99a897` | Multi-label dominio-equivalencia (`--equiv`) | Recall real **85.7%→89.1%** honesto |
| **S3b** | `19e1192` | Anchors "hablame de X" al centroide info | Recupera el patrón; 0 regresión; 4B real elige `web` |
| **S3c** | `2834573` | Exemplar abstain-margin | **"abre el navegador" daba VACÍO → arreglado** |
| **S3d** | `f786144` | Collapse jerárquico browser_real | Ruido **−0.11/turno**, recall intacto |
| **S3e/f** | — | Medir collapse de computer_use/source_manager/media | **RECHAZADOS** (pierden recall) → techo de poda |
| **S5** | `4ce36d5` | Invariantes de robustez (5 tests) | Protege contra desconfiguración al agregar tools/MCPs |
| **S6** | `2ed5f62` | Descripciones multilingües audio/media | **IT/PT/FR recuperados a 100%**; DE = límite encoder base |
| **S5-AP** | `b812841` | Anti-primacy ordering del subset (post-cap) | Estaba mergeado pero **INERTE** (`schemas_for_names` descartaba el orden con un `set`); fix: orden por posición en `names` + cache keyed por tuple. E2E: browser antes que media llega al LLM; 27/27 verde |
| **(regen)** | 2026-06-02 | Regeneración encoder FT + cabezas + eliminación `smart_home` | holdout ES 0.9964 vigente; `tool_head` 62→**61** tools; fix desalineación de índices |

---

## Detalle de cada sprint

### S0 — Medir la precisión (el norte invisible)
El router NO tenía problema de recall (0.9964 saturado). El gap real era
PRECISIÓN: 3.17 tools/turno con 1.86 de RUIDO. Se extendió el harness para
medirlo. Ejemplo crudo: "cierra steam" → steam+app+window+verify.

### S1a — related-budget 3→1
El "related-tools" metía deps especulativas (steam→app+window+verify) = ruido
puro, 0 recall protegido en 1733 filas. Recall idéntico, ruido 1.86→1.63,
turnos ruidosos 105→72.

### S1b — cluster-collapse gated OFF
Colapsar clusters de dominio bajaba ruido (1.63→1.29) PERO perdía recall
(holdout 0.9964→0.9820: 5 casos esperaban window/browser_real/uia específico).
Ninguna regla estática distinguía ruido de necesario SIN casos reales. Queda OFF
hasta tener el corpus de logs reales. **Lección: medir antes de activar.**

### S2 — El corpus de logs reales (el hallazgo más grande)
`traces.jsonl` (7059 turnos) → 1071 pares (mensaje real → tool ejecutada).
**El router real es 85.7%, NO 99.6%.** El corpus curado sintético estaba
saturado/sesgado; los logs reales son la verdad de campo.

### S3a — Dominio-equivalencia (`--equiv`)
La tool ejecutada esa vez no es la única correcta — varias del mismo dominio
funcional son igual de válidas. "reanuda el video" puede ser media O audio. Con
multi-label, el recall honesto sube a 89.1% (los 30 "miss" que daban tool del
mismo dominio NO eran miss).

### S3b — Anchors "hablame de X"
**Causa raíz medida:** "hablame de bruno mars" caía en chitchat (chit 0.380 >
info 0.368) — el nombre propio corto embebe cerca de la charla. Se agregaron
anchors del patrón "verbo-pedir-info + ENTIDAD" al centroide info (8 ES + 4
PT/FR/DE/IT, semánticos NO keywords). Recupera 8/10 positivos, 14/14 negativos
intactos. EN VIVO el 4B real elige `web`. 0 regresión curado.

### S3c — Exemplar abstain-margin (el bug más sutil)
**Causa raíz medida:** "abre el navegador" daba subset VACÍO. Su vecino-top en
el exemplar store era una PREGUNTA reflexiva ("me abrí el navegador?" label [])
que ganaba el voto-abstención por **0.005** a 4 vecinos-comando. El exemplar
abstenía y CORTOCIRCUITABA todo el planner. Fix: la abstención debe GANAR por
margen (`GEMMA4_EXEMPLAR_ABSTAIN_MARGIN=0.05`), no por empate. 0 regresión; los
NO-TOOL legítimos siguen abstain.

### S3d — Collapse jerárquico browser_real (precisión, el pedido central)
`browser_real` (control CDP) era RUIDO en 78 filas de logs reales vs solo 2 que
lo necesitan (formularios/clicks). Discriminador SEMÁNTICO medido (no keywords):
quitar browser_real si `score(browser) > score(browser_real)` (nav simple);
conservar si browser_real≥browser ("llená el formulario"). **Recall-neutral en
AMBOS corpus** (0 perdido). Ruido curado 1.62→1.51 holdout, real 1.47→1.36.
Turnos muy ruidosos 212→168.

### S3e/f — El techo de la poda determinista
Se midieron MÁS collapses y se **RECHAZARON con la medición**:
- **computer_use**: pierde recall (goal-mission "andá a Instant Gaming y comprá"
  lo necesita). 15 casos estrictos vs 53 ruido, pero los 15 son frágiles.
- **source_manager**: pierde 1 recall ("de qué trata Dune"). Beneficio mínimo.
- **{media,browser}**: pierde **11 recall** ("pon X en youtube" SÍ usa browser —
  YouTube/Netflix son web). **media y browser SOLAPAN dominio, NO es ruido.**

**Conclusión:** browser_real fue el único cluster seguro. El ruido restante
(browser en media-play) no es podable sin perder recall. Requiere encoder FT.

### S5 — Robustez (el 2º pedido del usuario)
"Router que no se desconfigure al meter más tools/MCPs." `test_router_coverage_
invariant.py` (5 tests). Hallazgo: 68 tools en schema, tool_head conoce 62; las
6 dif son META/INTERNAL (intencional). Las 59 tools de dominio tienen cobertura
≥2 capas. Tests: tool huérfana invisible falla ruidoso; ≥2 capas; no zombies;
descripciones↔schema; enrolar 12 MCPs irrelevantes no quita nativa, no se cuela,
de-enrolar restaura subset EXACTO.

> **[ACTUALIZADO 2026-06-02]** Tras eliminar `smart_home`, el `tool_head` pasó a
> conocer **61 tools** (no 62) y las de dominio bajaron en consecuencia. El test
> calcula los conteos dinámicamente (no hardcodea 62/68), así que sigue vigente
> sin tocarlo; los números de arriba son los del momento del sprint.

### S6 — Multilingüe (ley "uso universal")
Fuga medida: recall audio/media por idioma — DE 0/5 (el peor). Fix: enriquecer
la DESCRIPCIÓN SEMÁNTICA de audio (volumen) y media (reproducir) en DE/IT/PT/FR.
**Recupera IT/PT/FR a 100%.** 0 regresión. Límite del alemán: ver
[06_PENDIENTE_Y_NO_FORZADO](06_PENDIENTE_Y_NO_FORZADO.md).

---

### S5-AP — Anti-primacy ordering (commit `b812841`, 2026-06-02/03)
Del PLAN_MAESTRO (SPRINT 5, eje D): poner la tool específica/de-mayor-confianza
PRIMERA en el subset para subir P(el 4B la elija) — efecto de primacía ("Lost in
the Middle", arXiv:2307.03172). **Causa raíz contraintuitiva:** el reorden ya
estaba codeado pero quedaba **INERTE** porque `schemas_for_names` (`tools.py`)
filtraba por `set`, descartando el orden que el router producía. Fix:
`schemas_for_names` preserva el orden de `names` + cache keyed por tuple (dos
subsets con las mismas tools en distinto orden son claves distintas).
`_antiprimacy_order` (`planner.py:188`) corre DESPUÉS del cap (`planner.py:906-913`):
no cambia el CONJUNTO, solo el orden; `pending_intent` fija al frente, infra
(session/verify/state/dependency/safety) al final. Gate `GEMMA4_ANTIPRIMACY=1`
(default ON). Validado E2E (browser antes que media llega al LLM), 27/27 verde.
**Honesto:** el margen +5-15pp es de papers genéricos, NO medido en Gemma (el
router ya está saturado en ES 0.9964); el reorden es seguro porque no cambia el
conjunto. El few-shot turn-specific del mismo sprint se **DESCARTÓ** (research:
baseline ya 6/6; prefill mal hecho rompe el tool-call).

### (regen) — Regeneración de artefactos + baja de `smart_home` (2026-06-02)
Se regeneró el encoder FT + las 3 cabezas (cierra el exemplar-staleness que
abstenía comandos crispos) y se eliminó la tool `smart_home` de raíz
(schema+handler+dataset+router-data). El holdout ES **0.9964 sigue vigente**.
**Gotcha medido:** quitar `smart_home` dejó `tool_head.tools`(61) desalineado de
los pesos(62) → 13 tools leían el umbral del vecino → "qué es pytest" ofrecía
`whatsapp`. Fix: quitar la tool del MISMO índice en los 4 arrays paralelos. Ver
[BACKLOG_MAESTRO](../_backlog/BACKLOG_MAESTRO.md).

---

## Patrones reutilizables aprendidos

1. **Collapse jerárquico SOLO cuando la avanzada es rara-pero-frágil Y el score
   discrimina.** browser_real cumplía; media/computer_use no.
2. **El discriminador por score** (`score(simple) > score(avanzada)`) es
   language-agnostic y no rompe la ley de no-keywords.
3. **Medir en AMBOS corpus** antes de cambiar un default. Un caso ganado suele
   ser otro perdido.
4. **NO auto-curar labels** con un clasificador (corrompe; ya pasó). Los misses
   de logs reales se atacan en el ROUTER, no maquillando el corpus.
5. **El encoder base es el techo** para queries cortas de voz en idiomas con
   cobertura débil (DE). No lo arreglás con anchors ni reentrenando cabezas.
