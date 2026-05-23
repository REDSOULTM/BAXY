# Sprint 8b — Log (Tool2Vec-style descriptions, sin tocar router default)

- **Started:** 2026-05-17
- **Finished:** 2026-05-17 (same session)
- **Operator:** Claude Code (Opus 4.7)
- **Base commit:** `d3edf1b` (sprint8a closure)
- **Final code commit:** `5beac23` `sprint8b.4: tests for YAML enrichment (5 new tests)`
- **Net delta vs base:** 3 files, **+1630 / -5 LOC**
- **Files touched:** `gemma4_agent/tool_descriptions.yaml` (NEW, 1474 LOC),
  `gemma4_agent/router_v2.py` (+64 / -5), `gemma4_agent/test_router_v2.py`
  (+92 / -0)
- **`COMPOUND_TOOL_SCHEMAS`:** 65 → 65 (unchanged)
- **`test_router_v2`:** 22 → 27 tests (+5 new)
- **Suite total:** 790 → **795 passed**, 1 pre-existing failure (unchanged)

## Headline

`gemma4_agent/tool_descriptions.yaml` reemplaza el viejo
`semantic_router.TOOL_DESCRIPTIONS` como fuente de docs para
`router_v2`. Cada uno de los 65 compound tools tiene ahora un entry
**Tool2Vec-style** con:

- `purpose` (EN, ≤200 chars técnico para el encoder denso),
- `example_queries.es` (4-6 utterances rioplatenses con voseo, "armame",
  "decime", imperativos coloquiales),
- `example_queries.en` (4-6 utterances variadas — no traducciones 1:1
  del ES, para maximizar diversidad léxica que BM25 valora).

El bug motivador de Sprint 8 ("power point" no llegaba a `office`) está
**fixed y testeado**. Ahora `office` aparece en top-K con BM25 top-1
sobre la query "power point". Las queries coloquiales tipo "pone
Daredevil en netflix" rutean a `media`.

El router default sigue siendo v1 (planner + semantic_router viejo). v2
permanece **opt-in** vía `GEMMA4_ROUTER_V2=1` (full) o
`GEMMA4_ROUTER_V2_SHADOW=1` (blind comparison). Migración a v2 default
queda para Sprint 8c.

## 8b.1 — Bootstrap YAML — commit `ab67741` ✅

`gemma4_agent/tool_descriptions.yaml` arrancó con header de
documentación + el primer entry (`office`). El header pone el contrato
de formato por escrito para que el sprint sea reproducible:

```yaml
# Tool2Vec-style enrichment per Claude Research May 2026 §2.
# `purpose` is a 2-4 line technical summary in English for the dense
# embedding model. `example_queries` are 4-6 natural-language
# utterances per anchor language (ES, EN) that BM25 ingests as
# lexical signal and that the multilingual encoder uses to anchor
# the tool in semantic space. PT/FR/IT/DE coverage piggy-backs on
# multilingual-e5-small's cross-lingual alignment — no explicit
# queries needed for those.
```

**Decisión clave:** sólo ES + EN como anchor languages. El encoder es
`multilingual-e5-small` (100 idiomas, alineamiento cross-lingual). Para
PT/FR/IT/DE no se ganaría mucho con queries explícitas y se inflaría el
YAML 3-4×.

## 8b.2 — Los 64 entries restantes — commits `303c382` → `99c4a55` ✅

Diez batches por dominio. Después de cada batch corrí
`python -c "import yaml; ..."` para verificar que el archivo siguiera
parseable. Stats por batch:

| Batch | Domain | Entries | Commit |
|-------|--------|---------|--------|
| 8b.2.1 | documents | 5 | `303c382` |
| 8b.2.2 | browser/web/vision | 6 | `de869a0` |
| 8b.2.3 | audio/media/games | 7 | `25acb87` |
| 8b.2.4 | messaging | 5 | `82e1f8a` |
| 8b.2.5 | system/GUI | 9 | `ec00e4c` |
| 8b.2.6 | filesystem/storage | 6 | `7317355` |
| 8b.2.7 | IoT/devices | 5 | `053b799` |
| 8b.2.8 | dev tools | 6 | `3c65909` |
| 8b.2.9 | automation | 8 | `807f603` |
| 8b.2.10 | cognition | 7 | `99c4a55` |

Total: **65 entries → 1:1 con `COMPOUND_TOOL_SCHEMAS`**, verificado en
8b.4 con set-diff.

**Pothole encontrado en 8b.2.8 (dev tools):** `"C:\herramientas"` y
`"C:\tools"` dentro de strings double-quoted YAML disparan
`ScannerError: found unknown escape character 'h'` porque YAML
double-quoted interpreta `\h` como escape sequence inválida. Fix:
single-quote esos dos strings (`'C:\herramientas'`), no escapar el
backslash. Lección aplicable a cualquier ruta Windows en YAML.

## 8b.3 — Wire router_v2 a YAML — commit `758aa5a` ✅

`gemma4_agent/router_v2.py` ahora ignora
`semantic_router.TOOL_DESCRIPTIONS`. Agregué tres helpers:

```python
@staticmethod
def _load_tool_descriptions() -> dict[str, dict]:
    """Lee tool_descriptions.yaml. Devuelve {} si falla — el router
    NUNCA crashea por un YAML corrupto; degrada a docs = bare names."""

@staticmethod
def _doc_for_dense(entry, name) -> str:
    """Compose el passage para el encoder denso: purpose + es + en
    juntos en un solo string. Una sola pasada por tool a build-time."""

@staticmethod
def _doc_for_bm25(entry, name) -> str:
    """Compose el doc para BM25: name + purpose + es + en. El name
    primero porque BM25 le da peso a inicio de doc; queries como
    'abrime el Steam' tienen que matchear el name `steam` directo."""
```

`_build_index` ahora invoca esos helpers. **Importante:** el dense
embedding recibe una versión rica (purpose técnico EN + es + en) y el
BM25 una versión orientada a coverage léxico (incluye el tool name al
inicio + queries en los dos idiomas).

**Smoke probe end-to-end con el YAML enriched:**

| Query | Source | Top-1 | Subset relevant |
|---|---|---|---|
| "hola, como estas?" | smalltalk | — | [] ✓ |
| "Puedes hacerme un power point sobre IA?" | hybrid | source_manager | `office` en #8 ✓ |
| "abrime el Steam" | hybrid | app | `steam` en #2, `game_launcher` en #3 ✓ |
| "pone Daredevil en netflix" | hybrid | media | `media`, `browser` en top ✓ |
| "mandale un whatsapp a mama" | hybrid | whatsapp | top-1 correcto ✓ |
| "apaga la pc" | hybrid | system | top-1 correcto ✓ |
| "que un subagente investigue X" | hybrid | subagent | top-1 correcto ✓ |

Compare contra el smoke de 8a (con descriptions cortas) donde `office`
ni siquiera aparecía en top-K para "power point". Mejora cualitativa
gigante.

**Lo que NO mejoró todavía:** el top-1 para "power point" sigue siendo
`source_manager` (no `office`). Razón: BM25 top-1 SÍ es `office`
("hazme un power point sobre los planetas"), pero el dense top-1 es
`source_manager` (su purpose menciona "research sources"). RRF fusiona
los dos y como `source_manager` está bien rankeado en dense y BM25,
gana en la fusión. Sprint 8c puede afinar pesos RRF si esto importa —
por ahora `office` en top-K es suficiente para que el LLM tenga acceso
al schema.

## 8b.4 — Tests — commit `5beac23` ✅

Cinco tests nuevos en `gemma4_agent/test_router_v2.py`:

- **`ToolDescriptionsYamlTest` (3 unconditional, no model needed):**
  - `test_yaml_has_65_entries` — pin del count.
  - `test_yaml_entries_have_required_fields` — cada entry tiene
    `name`, `purpose`, `example_queries.es/en` con ≥4 queries
    por idioma (subTest por entry para reportes claros).
  - `test_yaml_names_match_compound_tools` — set-diff bidireccional
    contra `COMPOUND_TOOL_SCHEMAS`. Atrapa al instante el caso
    "agregué una tool nueva y se olvidaron de su entry YAML".

- **`EnrichedRoutingTest` (2 integration, skip-if-no-model):**
  - `test_power_point_routes_to_office` — el bug motivador.
  - `test_coloquial_play_routes_to_media_or_browser` — el caso
    rioplatense voseo + imperativo coloquial.

Resultado: **27/27 verde** en este host con el modelo presente. En
hosts sin modelo (CI limpio sin bootstrap), corren las 11 tests
unconditional (3 env + 4 constants + 1 disabled + 3 YAML structural).

## Final verifications

```
$ python -c "import yaml; d=yaml.safe_load(open('gemma4_agent/tool_descriptions.yaml',encoding='utf-8')); print(len(d))"
65

$ python -c "from gemma4_agent.router_v2 import RouterV2; r=RouterV2.get(); print(r._ensure_loaded())"
True

$ python -m pytest gemma4_agent/test_router_v2.py -q
27 passed in 10.24s

$ python -m pytest gemma4_agent/ -q --tb=no
795 passed, 1 failed in 81.72s
```

La 1 falla restante (`test_planner_continuation.test_without_hint_short_reply_subset_empty`)
es pre-existente desde Sprint 3a; no introducida por 8b.

## Decisiones de diseño que quedan documentadas

1. **Sólo ES + EN como anchor languages.** PT/FR/IT/DE
   piggy-back en e5-small multilingual cross-lingual alignment. Si
   8c descubre que un usuario brasileño tiene recall pobre, agregar
   `pt` en la misma key sin romper formato.

2. **BM25 doc incluye el tool name al inicio.** Las queries como
   "abrime el Steam" deben matchear vía nombre, no sólo descripcion.
   Sin esto, brand-name queries fallaban en 8a.

3. **Dense doc NO incluye el name.** El encoder semántico ya
   captura el concepto del tool desde el purpose; agregar el name
   contamina el embedding con un token que no debería pesar.

4. **purpose en EN, queries en ES+EN.** El encoder es multilingual,
   así que el idioma del purpose es indiferente para la similitud
   semántica. EN es más conciso y deja el budget de 200 chars para
   contenido técnico.

5. **`_load_tool_descriptions()` jamás crashea.** Si el YAML se
   corrompe, devuelve `{}` y los docs colapsan a los nombres pelados
   (degradación graceful). El router degrada, no se rompe.

## Lo que sigue (Sprint 8c)

- Correr el agente real una semana con `GEMMA4_ROUTER_V2_SHADOW=1`,
  exportar la distribución de eventos `router_v2`.
- Calibrar finales: `CACHE_THETA`, `SMALLTALK_DELTA_THETA`,
  `FALLBACK_THETA`, y opcionalmente pesos RRF por modalidad si
  vemos que dense o BM25 sistemáticamente ganan sobre el otro.
- Decidir si activar v2 como default (deprecate v1) o mantener
  ambos paths.
- Loop de self-improvement: si una query rutea mal y el LLM
  termina llamando un tool fuera del subset, anotar la query como
  candidato para agregar a `example_queries` de ese tool.

## Commits

```
ab67741 sprint8b.1: bootstrap tool_descriptions.yaml with format spec + office entry
303c382 sprint8b.2.1: enrich documents tools (5 entries)
de869a0 sprint8b.2.2: enrich browser/web/vision tools (6 entries)
25acb87 sprint8b.2.3: enrich audio/media/games tools (7 entries)
82e1f8a sprint8b.2.4: enrich messaging tools (5 entries)
ec00e4c sprint8b.2.5: enrich system/GUI tools (9 entries)
7317355 sprint8b.2.6: enrich filesystem/storage tools (6 entries)
053b799 sprint8b.2.7: enrich IoT/devices tools (5 entries)
3c65909 sprint8b.2.8: enrich dev tools (6 entries)
807f603 sprint8b.2.9: enrich automation tools (8 entries)
99c4a55 sprint8b.2.10: enrich cognition tools (7 entries) - 65/65 complete
758aa5a sprint8b.3: wire router_v2 to tool_descriptions.yaml
5beac23 sprint8b.4: tests for YAML enrichment (5 new tests)
<this commit>
```
