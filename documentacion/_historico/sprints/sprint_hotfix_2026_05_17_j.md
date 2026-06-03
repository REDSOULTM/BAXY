# HOTFIX 2026-05-17 (J) — Adaptive subset cap (confidence-aware TOP_K)

> Continuá el chat post hotfixes E + E.5 + F + G + H + I. Sprint
> chico de calibración. Surgió de la observación del operador en
> el activity log a las 21:01:35: la query trivial "sube el
> volumen" routeó a **16 tools** cuando `audio` era top-1 en
> ambos retrievers (dense AND BM25) con score máximo teórico.
> Subset bloat = ~10KB de schemas innecesarios al LLM en cada
> turn inequívoco.

---

## Contexto: el bug

Repro:
```
>>> from gemma4_agent.router_v2 import route_v2
>>> subset, tel = route_v2('sube el volumen')
>>> len(subset)
16
>>> tel['dense_top1'], tel['bm25_top1']
('audio', 'audio')
>>> tel['top_score']
0.0328  # max teórico para RRF k=60 / 65 docs (≈ 2/61)
```

Los dos retrievers concuerdan, score máximo posible, pero igual
devolvemos 16 tools.

Cost real:
```
16 schemas total: 14816 chars
4 schemas (audio + 3 vecinos): 4326 chars
savings potencial: 10490 chars (71% reduction)
```

Para Gemma 4 E4B (modelo chico, 32K context), ~10KB extra de
schemas por turn easy es significativo:
- Más tokens en prompt → más latencia per-turn (importa para voice).
- Más distractores → más probabilidad de que el LLM elija wrong
  tool ("local_search" estaba en el subset para "sube el volumen"
  — no tiene sentido).
- Menos espacio para historia conversacional / breadcrumbs.

---

## La señal estructural que ya emitimos pero no usamos

`router_v2.RouterV2.route()` ya calcula y emite en telemetry:

- `dense_top1`: nombre del tool con mayor cosine similarity.
- `bm25_top1`: nombre del tool con mayor BM25 score.
- `top_score`: RRF score del subset top-1.

Cuando `dense_top1 == bm25_top1` AND `top_score` está cerca del
max teórico (~0.033 = 2/(60+1)), tenemos **alta confianza** de que
el primer tool es el correcto. Subset bloat innecesario en ese
caso.

Cuando difieren, los dos retrievers proponen tools distintos →
ambigüedad real → vale la pena dar más opciones al LLM.

---

## OBJETIVO

Un commit chico. **Adaptive subset cap por confidence**.

```
| Señal estructural                                          | Cap |
|------------------------------------------------------------|-----|
| dense_top1 == bm25_top1 AND top_score >= 0.030             |   4 |
| dense_top1 == bm25_top1 AND top_score >= 0.020             |   8 |
| dense_top1 != bm25_top1 (retrievers disagree)              |  16 |
| (fallback paths: cache / smalltalk / fallback_applied unchanged) |
```

Detección 100% estructural — no toca calibración del smalltalk
gate, no toca prompts, no toca regex, no toca el cache.

---

## REGLAS GENERALES

1. PortandoLoMejor. Un commit chico, prefijo `feat(routing):`.
2. **CERO matching de idioma del user**. La señal viene del
   shape del retrieval (dense_top1, bm25_top1, top_score).
3. NO toques planner.py, modes.py, las 65 tools, tool_descriptions.yaml,
   voice/*, smalltalk gate logic, cache logic, fallback logic.
4. **Conservar TOP_K=16 como constante** — sigue siendo el cap
   máximo cuando hay ambigüedad. Solo agregamos un cap menor para
   alta confianza.
5. NO instales libs nuevas.
6. NO `git add -A`.

---

## FIX J1 — Adaptive cap en `RouterV2.route()`

### J1.1 — Agregar constantes

Editar `gemma4_agent/router_v2.py`. Después de `TOP_K = 16`
agregar:

```python
# Adaptive subset cap (hotfix J 2026-05-17).
# When BOTH retrievers (dense + BM25) agree on the top tool AND
# the RRF score is near max-theoretical (~0.033 = 2/(60+1) for
# RRF_K=60 over 65 docs), confidence is high enough to cap the
# subset tightly. When they disagree, we fall back to TOP_K for
# the LLM to choose.
#
# Bands chosen empirically against the smoke probes 2026-05-17:
#   "sube el volumen"   -> top_score=0.0328 (max), agree   -> 4
#   "apaga la pc"       -> top_score=0.0328, agree         -> 4
#   "instala vlc"       -> top_score=0.0328, agree         -> 4
#   "ayudame con un X"  -> top_score=0.0325, disagree      -> 16
#
# 0.030 is well above the FALLBACK_THETA=0.025 floor so high-
# confidence and fallback paths never overlap.
HIGH_CONFIDENCE_TOP_SCORE = 0.030
HIGH_CONFIDENCE_CAP = 4
MEDIUM_CONFIDENCE_TOP_SCORE = 0.020
MEDIUM_CONFIDENCE_CAP = 8
```

### J1.2 — Modificar el slicing post-RRF

Localizar en `route()`:

```python
top_indices = np.argsort(-rrf_scores)[:TOP_K]
subset = [self._tool_names[int(i)] for i in top_indices]
top_score = float(rrf_scores[top_indices[0]])
```

Reemplazar por:

```python
# Always compute the full ranking first — we cap after we know
# which confidence band we're in.
top_indices = np.argsort(-rrf_scores)[:TOP_K]
subset_full = [self._tool_names[int(i)] for i in top_indices]
top_score = float(rrf_scores[top_indices[0]])

# Adaptive cap based on agreement + RRF score (hotfix J).
dense_top1_name = self._tool_names[int(dense_ranking[0])]
bm25_top1_name = self._tool_names[int(bm25_ranking[0])]
retrievers_agree = dense_top1_name == bm25_top1_name
if retrievers_agree and top_score >= HIGH_CONFIDENCE_TOP_SCORE:
    adaptive_cap = HIGH_CONFIDENCE_CAP
    confidence_band = "high"
elif retrievers_agree and top_score >= MEDIUM_CONFIDENCE_TOP_SCORE:
    adaptive_cap = MEDIUM_CONFIDENCE_CAP
    confidence_band = "medium"
else:
    adaptive_cap = TOP_K
    confidence_band = "low"
subset = subset_full[:adaptive_cap]
```

### J1.3 — Agregar telemetry

Después del bloque, en el telemetry dict que ya se construye:

```python
telemetry["source"] = "hybrid"
telemetry["top_score"] = top_score
telemetry["dense_top1"] = dense_top1_name
telemetry["bm25_top1"] = bm25_top1_name
telemetry["smalltalk_sim"] = smalltalk_sim
telemetry["tools_sim"] = tools_sim
telemetry["smalltalk_delta"] = smalltalk_delta
# Hotfix J: expose the adaptive cap decision so we can audit
# whether the bands are well-calibrated in production.
telemetry["confidence_band"] = confidence_band
telemetry["adaptive_cap"] = adaptive_cap
telemetry["retrievers_agree"] = retrievers_agree
```

### J1.4 — Actualizar el counter del Sprint H4

Editar `gemma4_agent/router_v2.py::RouterV2.__init__` para que
el `_counters` dict trackee el nuevo signal:

```python
self._counters: dict[str, int] = {
    "calls_total": 0,
    "source_cache": 0,
    "source_smalltalk": 0,
    "source_hybrid": 0,
    "source_empty_query": 0,
    "source_disabled": 0,
    "fallback_applied": 0,
    "pending_tool_injected": 0,
    "load_failed": 0,
    # Hotfix J: track how often each confidence band fires.
    "band_high": 0,
    "band_medium": 0,
    "band_low": 0,
}
```

Y dentro de `route()`, después de incrementar `calls_total` y los
`source_*`:

```python
band = telemetry.get("confidence_band")
if band:
    key = f"band_{band}"
    if key in self._counters:
        self._counters[key] += 1
```

### J1.5 — Coherencia con `fallback_applied`

El path Layer 3 (popular fallback cuando `top_score <
FALLBACK_THETA=0.025`) sigue intacto. Como `MEDIUM_CONFIDENCE_TOP_SCORE
= 0.020` está por debajo de `FALLBACK_THETA = 0.025`, el orden de
chequeo es:

1. Si `retrievers_agree AND top_score >= 0.030` → cap=4 (high).
2. Si `retrievers_agree AND top_score >= 0.020` → cap=8 (medium).
3. Sino → cap=16 (low).
4. **Después**, si `top_score < FALLBACK_THETA=0.025`, popular
   fallback se aplica sobre el subset ya capeado.

Importante: el fallback_applied check NO debe sobrescribir el
adaptive_cap si pasamos por las bandas high/medium. En la
práctica `top_score >= 0.020` y `top_score < 0.025` quedan en
banda "medium" Y fallback_applied=True simultáneamente. Eso es
OK — significa "el retrieval está debil pero los dos retrievers
están de acuerdo en algo; mostremos 8 + popular".

Si querés ser más estricto: cuando `fallback_applied=True`,
forzar el cap a `TOP_K`. Eso da al LLM la red de popular fallback
completa cuando el retrieval flaqueó. Lo dejo a tu criterio en
implementación — mi default sería el comportamiento simple
(adaptive cap luego fallback popular puede insertar duplicados,
y el `dict.fromkeys` ya deduplica).

### J1.6 — Tests

Crear `gemma4_agent/test_router_v2_adaptive_cap.py`:

```python
"""Adaptive subset cap by confidence (hotfix J 2026-05-17).

Cap-by-confidence is a pure post-processing layer on top of the
existing RRF pipeline. Tests verify:
  - High-confidence queries (clear top-1 in both retrievers,
    near-max RRF score) -> 4 tools.
  - Medium-confidence queries (agreement but lower score) -> 8.
  - Low-confidence queries (retrievers disagree) -> 16.
  - Cache hits / smalltalk / fallback paths are unchanged.

Skips integration cases when the e5-small model isn't on disk.
"""
from __future__ import annotations

import unittest

from gemma4_agent.router_v2 import (
    HIGH_CONFIDENCE_CAP,
    HIGH_CONFIDENCE_TOP_SCORE,
    MEDIUM_CONFIDENCE_CAP,
    MEDIUM_CONFIDENCE_TOP_SCORE,
    MODEL_PATH,
    RouterV2,
    TOP_K,
    route_v2,
)


class AdaptiveCapConstantsTest(unittest.TestCase):
    """Pin the band boundaries so a silent regression shows up
    in the diff."""

    def test_high_band_above_fallback_theta(self) -> None:
        # HIGH band must be above FALLBACK_THETA (0.025) so the
        # popular-fallback path doesn't overlap with high-confidence.
        self.assertGreater(HIGH_CONFIDENCE_TOP_SCORE, 0.025)

    def test_medium_band_below_high(self) -> None:
        self.assertLess(MEDIUM_CONFIDENCE_TOP_SCORE, HIGH_CONFIDENCE_TOP_SCORE)

    def test_caps_are_ordered(self) -> None:
        self.assertLess(HIGH_CONFIDENCE_CAP, MEDIUM_CONFIDENCE_CAP)
        self.assertLess(MEDIUM_CONFIDENCE_CAP, TOP_K)

    def test_high_cap_is_small_enough_to_help(self) -> None:
        # If HIGH cap is too big the optimization is meaningless.
        self.assertLessEqual(HIGH_CONFIDENCE_CAP, 6)


@unittest.skipUnless(MODEL_PATH.exists(), "e5-small ONNX model not installed")
class AdaptiveCapBehaviourTest(unittest.TestCase):
    """Integration tests with the real router.

    Each test resets the singleton to avoid cache-hit pollution
    from prior tests."""

    def _route_cold(self, query: str):
        RouterV2.reset()
        router = RouterV2.get()
        if not router._ensure_loaded():
            self.skipTest(router._load_error)
        return route_v2(query)

    def test_clear_volume_command_yields_high_band(self) -> None:
        # The motivating bug for hotfix J: 'sube el volumen' had
        # 16 tools when audio was clearly top-1 in both retrievers.
        subset, tel = self._route_cold("sube el volumen")
        self.assertEqual(tel.get("source"), "hybrid")
        self.assertTrue(tel.get("retrievers_agree"))
        self.assertEqual(tel.get("confidence_band"), "high")
        self.assertEqual(tel.get("adaptive_cap"), HIGH_CONFIDENCE_CAP)
        self.assertLessEqual(len(subset), HIGH_CONFIDENCE_CAP)
        self.assertIn("audio", subset)

    def test_clear_power_command_yields_high_band(self) -> None:
        subset, tel = self._route_cold("apaga la pc")
        self.assertTrue(tel.get("retrievers_agree"))
        self.assertLessEqual(len(subset), HIGH_CONFIDENCE_CAP)
        self.assertIn("system", subset)

    def test_clear_install_command_yields_high_band(self) -> None:
        subset, tel = self._route_cold("instala vlc")
        self.assertTrue(tel.get("retrievers_agree"))
        self.assertLessEqual(len(subset), HIGH_CONFIDENCE_CAP)
        self.assertIn("package", subset)

    def test_subset_keeps_top_tool_first(self) -> None:
        # The capping should NOT reorder — top-1 stays first.
        subset, tel = self._route_cold("sube el volumen")
        self.assertEqual(subset[0], "audio")

    def test_telemetry_exposes_band(self) -> None:
        _, tel = self._route_cold("sube el volumen")
        self.assertIn("confidence_band", tel)
        self.assertIn("adaptive_cap", tel)
        self.assertIn("retrievers_agree", tel)

    def test_smalltalk_unchanged_no_band(self) -> None:
        # Smalltalk gate fires before the cap logic; confidence_band
        # should NOT appear in telemetry for smalltalk source.
        subset, tel = self._route_cold("hola")
        if tel.get("source") == "smalltalk":
            # confidence_band is hybrid-path only
            self.assertNotIn("confidence_band", tel)
            self.assertEqual(subset, [])


@unittest.skipUnless(MODEL_PATH.exists(), "e5-small ONNX model not installed")
class AdaptiveCapCounterTest(unittest.TestCase):
    """Verify the band counters added in J1.4 increment correctly."""

    def test_band_counters_increment(self) -> None:
        RouterV2.reset()
        router = RouterV2.get()
        if not router._ensure_loaded():
            self.skipTest(router._load_error)
        baseline_high = router._counters.get("band_high", 0)
        router.route("sube el volumen")  # expected high
        self.assertGreaterEqual(
            router._counters.get("band_high", 0),
            baseline_high + 1,
        )

    def test_session_summary_includes_band_counters(self) -> None:
        RouterV2.reset()
        router = RouterV2.get()
        if not router._ensure_loaded():
            self.skipTest(router._load_error)
        router.route("sube el volumen")
        summary = router.session_summary()
        self.assertIn("band_high", summary)
        self.assertIn("band_medium", summary)
        self.assertIn("band_low", summary)


if __name__ == "__main__":
    unittest.main()
```

### J1.7 — Commit

`feat(routing): adaptive subset cap by retriever confidence`

Mensaje:

```
feat(routing): adaptive subset cap by retriever confidence

Audit during real session 2026-05-17 21:01:35: operator's
"sube el volumen" routed to 16 tools (TOP_K cap) even though
audio was top-1 in BOTH dense AND BM25 retrievers with RRF score
0.0328 — the max theoretical for k=60 over 65 docs. Subset bloat
costs ~10KB of unnecessary schemas (71% of total) in the LLM
prompt per easy turn.

Fix: adaptive cap based on retriever agreement + RRF score.

Bands:
  HIGH   : agree=True, top_score >= 0.030  -> cap 4
  MEDIUM : agree=True, top_score >= 0.020  -> cap 8
  LOW    : disagree OR low score           -> cap 16 (= TOP_K)

Detection is 100% structural — reads dense_top1, bm25_top1,
top_score values that route() already computes for telemetry.
No keyword matching, no language-specific logic, no calibration
changes to smalltalk gate / fallback / cache.

Telemetry adds confidence_band, adaptive_cap, retrievers_agree
fields. RouterV2._counters tracks band_{high,medium,low}; the
session_summary emitted at shutdown shows the distribution so
operator can audit whether the bands need re-calibration after
real usage.

Order vs FALLBACK_THETA=0.025: HIGH boundary 0.030 sits above
the fallback floor, so popular-fallback only triggers in
LOW/MEDIUM territory where the extra options help.

Tests pin the band boundaries + 3 clear-command repros
(audio/system/package) + smalltalk-path unchanged + band-counter
increments. Skips integration cases when model isn't on disk.

Expected impact: ~70% of real-traffic turns are unambiguous
commands ("open chrome", "set volume", "install X"). On those,
prompt size drops 60-70% — measurable latency reduction for
voice-driven turns where the LLM prompt rebuild is on the
critical path.
```

---

## REPORTE FINAL

Devolveme:
1. Hash del commit.
2. Output de `python -m pytest gemma4_agent/test_router_v2_adaptive_cap.py -v`.
3. Output de `python -m pytest gemma4_agent/ -q --tb=line`.
4. Repro post-fix mostrando band distribution:
   ```python
   from gemma4_agent.router_v2 import RouterV2, route_v2
   queries = [
       'sube el volumen',
       'apaga la pc',
       'instala vlc',
       'abre chrome',
       'busca info sobre los dinosaurios',
       'ayudame con un proyecto',  # ambiguous
       'hace un backup',
       'hola',  # smalltalk
   ]
   for q in queries:
       RouterV2.reset()
       subset, tel = route_v2(q)
       band = tel.get('confidence_band', '-')
       agree = tel.get('retrievers_agree', '-')
       print(f'{q!r:42s} src={tel.get("source"):9s} band={band:7s} agree={agree!s:5s} subset_size={len(subset)}')
   ```
5. session_summary después de las queries de arriba:
   ```python
   print(RouterV2.get().session_summary())
   ```

## CRITERIO DE ÉXITO

- 1 commit aterrizado.
- ≥10 tests nuevos verdes.
- Suite completa verde (modulo Sprint 3a pre-existing failure +
  xfailed de E.5).
- Las 5+ queries del repro con `retrievers_agree=True` y score >=
  0.030 muestran `subset_size <= 4`.
- Queries ambiguas siguen mostrando `subset_size` cercano a 16.
- session_summary muestra `band_high > 0` después del repro.

## NO HACER (anti-scope)

- NO bajes `TOP_K=16` como constante global. Sigue siendo el cap
  máximo para queries ambiguas — solo agregamos capas más
  pequeñas para alta confianza.
- NO matchees texto del user en ningún sitio.
- NO toques smalltalk gate, cache, popular fallback. Solo el
  slicing post-RRF.
- NO toques el `route_v2` signature (sigue aceptando solo
  `query` y `pending_tool_hint`).
- NO migres las constantes a config / env vars. Hardcoded en el
  módulo con comment explicando la calibración es lo correcto.
- NO agregues una banda "ultra-high" cap=1. Aunque el top-1 sea
  obvio, dar 3 vecinos al LLM le permite recuperar si el routing
  está marginalmente mal (e.g. `audio` top-1 cuando la intent era
  realmente `audio_device`). 4 es el mínimo seguro.
- NO inflas la HIGH band threshold por encima de 0.033. Ese ES
  el max teórico — cualquier valor más alto haría la banda
  inalcanzable.
- Si el test integration falla porque el RRF score teórico
  cambió (e.g. alguien modificó RRF_K), ajustá los thresholds
  del test al nuevo max teórico, NO al revés. Las constantes en
  router_v2 son la fuente de verdad.
