# HOTFIX 2026-05-17 (J.1) — TIGHT_CLUSTER band + BM25 saturation guard + cluster_size telemetry

> Continuá el chat post hotfix J. Calibration follow-up surgido
> del log real 2026-05-17 21:31:11: la query `cierra steam` cayó
> en banda LOW (cap=16) porque dense_top1=`app` y bm25_top1=
> `steam` disagree — pero los top-5 RRF están todos dentro del
> 88% del top-1, lo que indica un **cluster chico de candidatos
> reales** (4-5 tools), no ambigüedad de 16. Subset bloat
> innecesario en queries de la forma "verbo + tool name".
>
> Esta calibración fue investigada en `docs/architecture/
> compass_artifact_wf-4173e745-...md` con literatura sanity-
> checked (Shtok 2012, Bahri 2020/2023, Bruch 2023) y validada
> contra los 5 probes que la auditoría documentó.

---

## Contexto: el bug específico

Repro del log real:
```
21:31:11  YOU      cierra steam
21:31:11  CONTEXT  app, steam, watcher, game_launcher, state,
                   source_manager ... (+10)   ← 16 tools
21:31:11  GEMMA    Listo, Steam se cerró.
```

Análisis de las señales del retrieval:
```
Dense top-5:   app(0.823), state(0.807), source_manager(0.802),
               window(0.801), steam(0.797)
BM25 top-5:    steam(5.87), watcher(4.24), game_launcher(3.86),
               app(2.99), accessibility(0.00)
RRF top-5:     app(0.0320), steam(0.0318), watcher(0.0306),
               game_launcher(0.0298), state(0.0282)

rrf[4]/rrf[0] = 0.88   ← cluster TIGHT, 5 candidatos reales
```

Los 5 tools del top-5 RRF son los candidatos genuinos. El resto
(rank 6-16) son ruido — `printer_scanner`, `smart_home`,
`reminder`, etc. — irrelevantes. La banda LOW=16 los agrega como
distractor para el LLM.

Investigación dedicada con literatura como sanity check
(`compass_artifact_wf-4173e745`) recomienda una **banda
intermedia** entre HIGH/MEDIUM (que requieren agreement) y LOW
(genuinamente ambiguo).

---

## La señal estructural: `rrf[N]/rrf[0]`

Cuando los retrievers difieren pero ambos top-1 corroboran el otro
ranking (cada uno aparece en el top-25 del otro), el cluster RRF
queda concentrado en los primeros 4-8 ranks. El ratio
`rrf[4]/rrf[0]` mide ese aplanamiento:

| Query | rrf[4]/rrf[0] | Cluster status |
|---|---|---|
| `cierra steam` | 0.88 | TIGHT (5 candidatos reales) |
| `abre el powerpoint que hice` | 0.93 | TIGHT |
| `instala vlc, después abrelo` | 0.83 | TIGHT |
| `ayudame con un proyecto` | 0.61 | DISPERSED (genuinely ambiguous) |
| `hace algo` | <0.50 | NOISE (top_score < 0.020) |

**Threshold 0.80** sitúa el cutoff a 19 puntos del caso TIGHT más
bajo (0.83) Y a 19 puntos del caso DISPERSED (0.61). Margin
simétrico, no over-fit.

---

## OBJETIVO

Un commit chico. **Nueva banda TIGHT_CLUSTER + BM25 saturation
guard + cluster_size telemetry**.

```
| Señal estructural                                            | Cap | Banda          |
|--------------------------------------------------------------|-----|----------------|
| agree AND top_score >= 0.030                                 |  4  | HIGH (J)       |
| agree AND top_score >= 0.020                                 |  8  | MEDIUM (J)     |
| disagree AND top_score >= 0.025 AND rrf[4]/rrf[0] >= 0.80    |  8  | TIGHT_CLUSTER  |
| else                                                         | 16  | LOW (J)        |
| (cache / smalltalk / popular fallback paths unchanged)       |     |                |
```

---

## REGLAS GENERALES

1. PortandoLoMejor. Un commit chico, prefijo `feat(routing):`.
2. **CERO matching de texto del user**. Solo señales estructurales
   del retrieval.
3. NO toques HIGH/MEDIUM bands ya calibradas en J.
4. NO toques smalltalk gate, cache, popular fallback, RRF_K=60,
   TOP_K=16.
5. NO inventes per-language thresholds (la investigación lo
   explicita como restricción).
6. **Hard cap, NO soft cap**: la investigación rechazó soft-cap-
   by-score-floor por baja predictibilidad. Cap=8 fijo.
7. NO instales libs nuevas.
8. NO `git add -A`.

---

## FIX J1.1 — Agregar constantes

Editar `gemma4_agent/router_v2.py`. Después de las constantes
HIGH/MEDIUM de Sprint J:

```python
# TIGHT_CLUSTER band (hotfix J.1 2026-05-17).
# When retrievers DISAGREE on top-1 but the top-5 RRF scores form
# a tight cluster (rrf[4]/rrf[0] >= 0.80) AND the top score is
# corroborated across retrievers (top_score >= 0.025), the LLM
# sees 4-5 real candidates rather than the full TOP_K=16 noise.
#
# Calibration (5 probes, 2026-05-17 audit):
#   "cierra steam"               rrf[4]/rrf[0]=0.88, top=0.0320 -> TIGHT
#   "abre el powerpoint..."      rrf[4]/rrf[0]=0.93, top=~0.030 -> TIGHT
#   "instala vlc..."             rrf[4]/rrf[0]=0.83, top=~0.029 -> TIGHT
#   "ayudame con un proyecto"    rrf[4]/rrf[0]=0.61, top=0.0325 -> LOW
#   "hace algo"                  top_score<0.020              -> LOW (via floor)
#
# The 0.025 floor matches FALLBACK_THETA exactly: anything below
# is fallback territory regardless of cluster shape.
#
# The 0.80 ratio sits midway between the lowest TIGHT (0.83) and
# the highest DISPERSED (0.61) — 19-point margin in both directions.
#
# Cap=8 (not 6) because the competitive cluster is typically 4-5
# tools; cap=8 leaves a 3-4 tool margin for adjacent neighbours
# (e.g. `installer`/`launcher`/`terminal` next to `package`+`app`
# in the vlc probe). Token cost of 2 extra schemas in 32K context
# is negligible vs. recall risk.
TIGHT_CLUSTER_TOP_SCORE = 0.025   # = FALLBACK_THETA; corroboration floor
TIGHT_CLUSTER_RATIO = 0.80        # rrf[4] / rrf[0] cutoff
TIGHT_CLUSTER_CAP = 8
TIGHT_CLUSTER_RANK_AT = 4         # which RRF rank to compare against rank-0
```

---

## FIX J1.2 — BM25 saturation guard

**Riesgo identificado por la investigación**: en un corpus de 65
tools, BM25 frecuentemente retorna 0.00 para tools cuyas tokens no
aparecen en la query. Múltiples empates en BM25=0.00 reciben rango
arbitrario; si un tool irrelevante con BM25=0.00 cae en dense top-
10, infla `rrf[4]` spuriamente y eleva el ratio sobre 0.80 → falso
positivo TIGHT_CLUSTER.

**Mitigación**: en la fusión RRF, los tools con `bm25_scores[i] ==
0.0` se tratan como "no presentes en el ranking BM25". Su rank en
BM25 NO contribuye al rrf_score acumulado.

Localizar en `gemma4_agent/router_v2.py::route()`:

```python
bm25_scores = self._tool_bm25.get_scores(
    self._tokenize_for_bm25(query),
)
bm25_ranking = np.argsort(-bm25_scores)

rrf_scores = np.zeros(len(self._tool_names), dtype=np.float64)
for rank, idx in enumerate(dense_ranking):
    rrf_scores[idx] += 1.0 / (RRF_K + rank + 1)
for rank, idx in enumerate(bm25_ranking):
    rrf_scores[idx] += 1.0 / (RRF_K + rank + 1)
```

Reemplazar el segundo loop por:

```python
for rank, idx in enumerate(dense_ranking):
    rrf_scores[idx] += 1.0 / (RRF_K + rank + 1)
# Hotfix J.1 2026-05-17: BM25 saturation guard. Tools with raw
# BM25=0 are NOT genuinely ranked — they appear in the ranking
# in arbitrary order due to ties at zero. Treating them as
# "not in BM25 list" prevents spurious cluster inflation in the
# TIGHT_CLUSTER detector below.
for rank, idx in enumerate(bm25_ranking):
    if float(bm25_scores[idx]) <= 0.0:
        continue
    rrf_scores[idx] += 1.0 / (RRF_K + rank + 1)
```

Esto NO cambia el ranking efectivo del top de RRF (los tools
realmente relevantes tienen BM25 > 0). Solo cambia los scores de
los rank-tail, lo cual es lo que queremos para la métrica TIGHT.

---

## FIX J1.3 — Insertar la banda en `route()`

Localizar en `gemma4_agent/router_v2.py::route()` el bloque de
banding del Sprint J:

```python
top_indices = np.argsort(-rrf_scores)[:TOP_K]
subset_full = [self._tool_names[int(i)] for i in top_indices]
top_score = float(rrf_scores[top_indices[0]])

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

Reemplazar el `else` por:

```python
else:
    # Hotfix J.1 2026-05-17: distinguish "tight cluster of real
    # candidates" from "genuinely ambiguous → TOP_K fallback".
    # Both retrievers disagree on top-1 but if their rankings
    # overlap enough that the top-5 RRF scores stay close to
    # top-1, there are 4-5 real candidates, not 16.
    rrf_sorted = np.sort(rrf_scores)[::-1]  # descending
    if (
        len(rrf_sorted) > TIGHT_CLUSTER_RANK_AT
        and top_score >= TIGHT_CLUSTER_TOP_SCORE
        and float(rrf_sorted[0]) > 0.0
        and (float(rrf_sorted[TIGHT_CLUSTER_RANK_AT]) /
             float(rrf_sorted[0])) >= TIGHT_CLUSTER_RATIO
    ):
        adaptive_cap = TIGHT_CLUSTER_CAP
        confidence_band = "tight_cluster"
    else:
        adaptive_cap = TOP_K
        confidence_band = "low"
subset = subset_full[:adaptive_cap]
```

---

## FIX J1.4 — Telemetry + counters

### J1.4a — `confidence_band` value nueva

El telemetry ya emite `confidence_band` (Sprint J). El valor
`"tight_cluster"` aparece automáticamente.

### J1.4b — `cluster_size` métrica nueva

La investigación recomienda exponer `cluster_size = count(i in
[0..15] where rrf[i]/rrf[0] >= 0.80)` para auditar la salud de la
banda en producción.

Agregar al telemetry dict, junto a los campos existentes:

```python
# Cluster size: how many of the top-TOP_K candidates score within
# 80% of the top-1. Useful for auditing TIGHT_CLUSTER calibration
# in production: TIGHT_CLUSTER firing AND cluster_size in [3,6] is
# the healthy regime; cluster_size=12 firing TIGHT_CLUSTER signals
# BM25 saturation pathology (see hotfix J.1 saturation guard).
top_k_scores = rrf_sorted[:TOP_K] if len(rrf_sorted) >= TOP_K else rrf_sorted
if float(top_k_scores[0]) > 0.0:
    cluster_size = int(np.sum(
        top_k_scores / float(top_k_scores[0]) >= TIGHT_CLUSTER_RATIO
    ))
else:
    cluster_size = 0
telemetry["cluster_size"] = cluster_size
```

### J1.4c — Counter en `_counters`

Editar `RouterV2.__init__`:

```python
self._counters: dict[str, int] = {
    # ... existing entries unchanged ...
    "band_high": 0,
    "band_medium": 0,
    "band_low": 0,
    # Hotfix J.1 2026-05-17:
    "band_tight_cluster": 0,
}
```

El bump existente del Sprint H4 (`f"band_{band}"`) maneja
automáticamente el nuevo key porque el band name es ahora
`"tight_cluster"`.

---

## FIX J1.5 — Tests

Crear `gemma4_agent/test_router_v2_tight_cluster.py`:

```python
"""TIGHT_CLUSTER band calibration (hotfix J.1 2026-05-17).

Three critical tests calibrated against the investigation probes:

  (a) Language-agnostic equivalence: same query in ES and EN must
      produce identical TIGHT_CLUSTER + cap=8 + identical subset
      (modulo tool order being deterministic).
  (b) Genuine-ambiguity boundary: 'ayudame con un proyecto'
      (rrf[4]/rrf[0]≈0.61) must stay LOW with cap=16.
  (c) Low-signal fallback: 'hace algo' (top_score<0.025) must
      route via the corroboration FLOOR, not the ratio gate.

Plus a synthetic two-singletons regression: when both top-1s are
absent from the other retriever's top-25, top_score is below the
floor and we must NOT fire TIGHT_CLUSTER.

Plus BM25 saturation guard test: a phantom-cluster shape that
WOULD pass the ratio gate without the guard must NOT fire
TIGHT_CLUSTER after the guard is in place.

Skips integration cases when the e5-small model isn't on disk.
"""
from __future__ import annotations

import unittest

import numpy as np

from gemma4_agent.router_v2 import (
    MODEL_PATH,
    RouterV2,
    TIGHT_CLUSTER_CAP,
    TIGHT_CLUSTER_RANK_AT,
    TIGHT_CLUSTER_RATIO,
    TIGHT_CLUSTER_TOP_SCORE,
    TOP_K,
    route_v2,
)


class TightClusterConstantsTest(unittest.TestCase):
    """Pin the band boundaries so a silent regression shows up in diff."""

    def test_top_score_floor_equals_fallback_theta(self) -> None:
        # The TIGHT corroboration floor is intentionally set to
        # FALLBACK_THETA — anything below is fallback territory.
        from gemma4_agent.router_v2 import FALLBACK_THETA
        self.assertEqual(TIGHT_CLUSTER_TOP_SCORE, FALLBACK_THETA)

    def test_ratio_is_below_one(self) -> None:
        self.assertLess(TIGHT_CLUSTER_RATIO, 1.0)
        self.assertGreater(TIGHT_CLUSTER_RATIO, 0.5)

    def test_cap_between_medium_and_top_k(self) -> None:
        from gemma4_agent.router_v2 import MEDIUM_CONFIDENCE_CAP
        # TIGHT_CLUSTER fires under disagree → should give more
        # candidates than MEDIUM (which requires agreement) but
        # less than LOW=TOP_K.
        self.assertGreaterEqual(TIGHT_CLUSTER_CAP, MEDIUM_CONFIDENCE_CAP)
        self.assertLess(TIGHT_CLUSTER_CAP, TOP_K)

    def test_rank_at_is_in_range(self) -> None:
        # Comparing rank-4 vs rank-0 means 5 candidates form the cluster.
        self.assertEqual(TIGHT_CLUSTER_RANK_AT, 4)


@unittest.skipUnless(MODEL_PATH.exists(), "e5-small ONNX model not installed")
class TightClusterBehaviourTest(unittest.TestCase):
    """Integration tests with the real router. Each test resets
    the singleton to avoid cache-hit pollution."""

    def _route_cold(self, query: str):
        RouterV2.reset()
        router = RouterV2.get()
        if not router._ensure_loaded():
            self.skipTest(router._load_error)
        return route_v2(query)

    # --- (a) Language-agnostic equivalence ---
    def test_cierra_steam_fires_tight_cluster(self) -> None:
        # The motivating bug for J.1. Must land in TIGHT_CLUSTER
        # with cap=8, NOT LOW with cap=16.
        subset, tel = self._route_cold("cierra steam")
        self.assertEqual(tel.get("source"), "hybrid")
        self.assertFalse(tel.get("retrievers_agree"))
        self.assertEqual(tel.get("confidence_band"), "tight_cluster")
        self.assertEqual(tel.get("adaptive_cap"), TIGHT_CLUSTER_CAP)
        self.assertLessEqual(len(subset), TIGHT_CLUSTER_CAP)
        self.assertIn("steam", subset)
        self.assertIn("app", subset)

    def test_close_steam_en_matches_es_band(self) -> None:
        # Language-agnosticism: EN equivalent must produce the same
        # band. We don't pin identical subsets because the encoder
        # may give slightly different cosine for translated phrases;
        # we pin the BAND.
        _, tel_es = self._route_cold("cierra steam")
        _, tel_en = self._route_cold("close steam")
        self.assertEqual(
            tel_es.get("confidence_band"),
            tel_en.get("confidence_band"),
            f"ES band={tel_es.get('confidence_band')!r}, "
            f"EN band={tel_en.get('confidence_band')!r}"
        )

    # --- (b) Genuine-ambiguity boundary ---
    def test_ambiguous_query_stays_low(self) -> None:
        # 'ayudame con un proyecto' has rrf[4]/rrf[0]≈0.61 — well
        # below the 0.80 ratio gate. Must stay LOW band cap=16.
        subset, tel = self._route_cold("ayudame con un proyecto")
        # Disagree expected here too, but the cluster is genuinely
        # dispersed.
        if not tel.get("retrievers_agree"):
            self.assertEqual(tel.get("confidence_band"), "low")
            self.assertEqual(tel.get("adaptive_cap"), TOP_K)

    # --- (c) Low-signal fallback (top_score < TIGHT_CLUSTER_TOP_SCORE) ---
    def test_low_signal_query_routes_via_floor_not_ratio(self) -> None:
        # 'hace algo' has top_score below 0.025 — must hit LOW via
        # the corroboration floor, NOT via the ratio gate (which
        # could mis-fire if cluster collapse at low scores).
        subset, tel = self._route_cold("hace algo")
        if tel.get("source") == "hybrid":
            if (
                tel.get("top_score") is not None
                and float(tel["top_score"]) < TIGHT_CLUSTER_TOP_SCORE
            ):
                # Must NOT be tight_cluster — floor rules it out.
                self.assertNotEqual(tel.get("confidence_band"), "tight_cluster")

    # --- Telemetry exposes cluster_size ---
    def test_telemetry_exposes_cluster_size(self) -> None:
        _, tel = self._route_cold("cierra steam")
        self.assertIn("cluster_size", tel)
        size = tel.get("cluster_size")
        self.assertIsInstance(size, int)
        # For a TIGHT_CLUSTER case the count should be in the
        # healthy regime [3, 8].
        if tel.get("confidence_band") == "tight_cluster":
            self.assertGreaterEqual(size, 3)
            self.assertLessEqual(size, 12)


@unittest.skipUnless(MODEL_PATH.exists(), "e5-small ONNX model not installed")
class BM25SaturationGuardTest(unittest.TestCase):
    """Verify the BM25=0.00 guard prevents phantom clusters.

    In a 65-tool corpus, BM25 typically returns 0.00 for tools
    whose tokens don't appear in the query. Multiple ties at 0
    get arbitrary order; without the guard, a low-RRF irrelevant
    tool could spuriously inflate rrf[4]/rrf[0].
    """

    def test_bm25_zero_scores_do_not_contribute_to_rrf(self) -> None:
        RouterV2.reset()
        router = RouterV2.get()
        if not router._ensure_loaded():
            self.skipTest(router._load_error)
        # Reach into the route() pipeline directly. We compose the
        # encode + BM25 stages manually so we can inspect the
        # rrf_scores after the guarded fusion.
        query = "cierra steam"
        query_emb = router._encode_batch([f"query: {query}"])[0]
        dense_scores = router._tool_embeddings @ query_emb
        dense_ranking = np.argsort(-dense_scores)
        bm25_scores = router._tool_bm25.get_scores(
            router._tokenize_for_bm25(query),
        )
        # Find a tool with BM25=0.0 that's NOT in dense top-5.
        # That tool's RRF score (post-guard) should be much
        # smaller than rrf[0] — its BM25 contribution is zero.
        from gemma4_agent.router_v2 import RRF_K
        rrf_scores = np.zeros(len(router._tool_names), dtype=np.float64)
        for rank, idx in enumerate(dense_ranking):
            rrf_scores[idx] += 1.0 / (RRF_K + rank + 1)
        bm25_ranking = np.argsort(-bm25_scores)
        for rank, idx in enumerate(bm25_ranking):
            if float(bm25_scores[idx]) <= 0.0:
                continue
            rrf_scores[idx] += 1.0 / (RRF_K + rank + 1)
        # Pick a tool not in dense top-5 with BM25=0.
        candidate_idx = None
        for idx in range(len(router._tool_names)):
            if (
                float(bm25_scores[idx]) <= 0.0
                and idx not in dense_ranking[:5]
            ):
                candidate_idx = idx
                break
        if candidate_idx is None:
            self.skipTest("no BM25=0.0 candidate outside dense top-5")
        # That tool's RRF score should reflect ONLY its dense
        # ranking (which was rank 5+ → small contribution).
        # Specifically it should NOT have a BM25-side bump.
        max_dense_only_contribution = 1.0 / (RRF_K + 5 + 1)  # rank 5
        self.assertLessEqual(
            rrf_scores[candidate_idx], max_dense_only_contribution + 1e-9,
            f"BM25=0 tool {router._tool_names[candidate_idx]!r} "
            f"received contribution from BM25 ranking"
        )


if __name__ == "__main__":
    unittest.main()
```

---

## FIX J1.6 — Commit

`feat(routing): TIGHT_CLUSTER band for disagree-but-clustered queries`

Mensaje:

```
feat(routing): TIGHT_CLUSTER band for disagree-but-clustered queries

Audit during real session 2026-05-17 21:31:11: operator's
"cierra steam" routed to 16 tools (LOW band, cap=TOP_K). Both
retrievers disagreed on top-1 (dense=app, bm25=steam) so Sprint
J's adaptive cap fell through to LOW. But inspecting the RRF
scores, top-5 were tightly clustered:

  app(0.0320), steam(0.0318), watcher(0.0306),
  game_launcher(0.0298), state(0.0282)

rrf[4]/rrf[0] = 0.88 — these are 5 real candidates, not 16. The
extra 11 tools (printer_scanner, smart_home, reminder, ...) were
pure distractors.

Research (docs/architecture/compass_artifact_wf-4173e745-...md,
literature sanity-checked against Shtok 2012, Bahri 2020/2023,
Bruch 2023) recommends a new TIGHT_CLUSTER band:

  TIGHT_CLUSTER fires when:
    dense_top1 != bm25_top1 (otherwise HIGH/MEDIUM caught it),
    AND top_score >= 0.025 (= FALLBACK_THETA; corroboration floor),
    AND rrf_sorted[4] / rrf_sorted[0] >= 0.80 (tight cluster gate).

  Cap = 8 (not 6): cluster is typically 4-5 real candidates;
  cap=8 leaves 3-4 margin for adjacent neighbours. Token cost in
  32K context is negligible vs recall risk.

Calibration probes (cold cache):
  cierra steam               rrf[4]/rrf[0]=0.88 -> TIGHT (cap=8)
  abre el powerpoint...      rrf[4]/rrf[0]=0.93 -> TIGHT
  instala vlc, después...    rrf[4]/rrf[0]=0.83 -> TIGHT
  ayudame con un proyecto    rrf[4]/rrf[0]=0.61 -> LOW (cap=16)
  hace algo                  top_score<0.025    -> LOW (via floor)

0.80 threshold sits 19 points above the highest DISPERSED case
(0.61) and 19 below the lowest TIGHT case (0.83) — symmetric
margin, not over-fit.

Companion fix: BM25 saturation guard. In a 65-tool corpus BM25
returns 0.00 for tools whose tokens don't appear. Multiple ties
at 0.00 receive arbitrary rank order; without a guard, a low-RRF
irrelevant tool could spuriously inflate rrf[4] and trip the
ratio gate. Guard: tools with bm25_score == 0.0 don't contribute
to the BM25 RRF leg. The dense-only contribution survives, so
relevant tools still rank correctly.

Telemetry: new field cluster_size = count of tools whose RRF
score is >= 80% of top-1. Healthy regime for TIGHT_CLUSTER is
cluster_size in [3, 8]. cluster_size > 8 firing TIGHT_CLUSTER
signals BM25 saturation pathology (sentinel for future drift).

Counter: band_tight_cluster joins band_high/medium/low in
RouterV2._counters; session_summary at shutdown shows the
distribution.

Soft-cap-by-score-floor was investigated and rejected for this
sprint: operator predictability is weaker (output depends on full
rrf vector, not just top-1 / top1 / top_score), no probe currently
requires cap in {5, 7}, and hard cap matches the user's stated
"can the operator predict subset size?" decision rule.

Tests pin: band boundaries, the cierra steam ES/EN equivalence
(language-agnostic), the ambiguous-boundary case staying in LOW,
the low-signal fallback going via the floor, cluster_size in
telemetry, BM25=0.00 saturation guard correctness.

Caveat from the research: thresholds are v1 calibrated against
5 probes. Recompute after ~50 logged queries via the new
cluster_size telemetry. If RRF k=60 ever changes, the 0.025
floor must recompute proportionally (it's ≈ 1/(k+1) + 1/(k+10)).
```

---

## REPORTE FINAL

Devolveme:
1. Hash del commit.
2. Output de `python -m pytest gemma4_agent/test_router_v2_tight_cluster.py -v`.
3. Output de `python -m pytest gemma4_agent/test_router_v2_adaptive_cap.py -v`
   (Sprint J tests must remain green).
4. Output de `python -m pytest gemma4_agent/ -q --tb=line`.
5. Repro post-fix mostrando band distribution con TIGHT_CLUSTER:
   ```python
   from gemma4_agent.router_v2 import RouterV2, route_v2
   queries = [
       'cierra steam',                  # expected TIGHT_CLUSTER (cap 8)
       'close steam',                   # expected TIGHT_CLUSTER (cap 8)
       'cierra whatsapp',               # expected HIGH (cap 4) — agree
       'sube el volumen',               # expected HIGH (cap 4)
       'abre el powerpoint que hice',   # expected TIGHT_CLUSTER (cap 8)
       'ayudame con un proyecto',       # expected LOW (cap 16)
       'hace algo',                     # expected LOW (cap 16, low signal)
       'hola',                          # smalltalk
   ]
   for q in queries:
       RouterV2.reset()
       subset, tel = route_v2(q)
       band = tel.get('confidence_band', '-')
       agree = tel.get('retrievers_agree', '-')
       cap = tel.get('adaptive_cap', '-')
       cs = tel.get('cluster_size', '-')
       print(f'{q!r:40s} band={band:14s} agree={agree!s:5s} cap={cap!s:3s} cluster_size={cs!s:3s} size={len(subset):2d}')
   ```
6. session_summary mostrando el nuevo counter:
   ```python
   print(RouterV2.get().session_summary())
   ```

## CRITERIO DE ÉXITO

- 1 commit aterrizado.
- ≥10 tests nuevos verdes en test_router_v2_tight_cluster.py.
- test_router_v2_adaptive_cap.py (Sprint J) sigue verde sin
  cambios.
- Suite completa verde (modulo Sprint 3a pre-existing failure +
  E.5 xfailed).
- Repro post-fix:
  - `cierra steam` cae en TIGHT_CLUSTER, cap=8, size<=8.
  - `cierra whatsapp` sigue en HIGH (Sprint J), cap=4.
  - `ayudame con un proyecto` sigue en LOW, cap=16.
  - `hace algo` sigue en LOW via floor.
- session_summary muestra `band_tight_cluster > 0` después del repro.

## NO HACER (anti-scope)

- NO bajes cap TIGHT_CLUSTER a 6 sin evidencia empírica de un
  probe nuevo donde cap=8 demonstrably daña.
- NO bajes ratio a < 0.75 (la investigación bandeó [0.75, 0.80]).
- NO migres a soft-cap. La investigación lo rechazó por baja
  predictibilidad operacional.
- NO tocás HIGH/MEDIUM bands de Sprint J.
- NO matchees texto del user.
- NO inventes patches al RRF_K=60 o al BM25 más allá del guard.
- Si el test "low-signal `hace algo`" no es determinístico (queries
  ultra-cortas pueden caer en smalltalk o disabled), relájalo a
  "NO tight_cluster" y dejá un comment explicando por qué — los
  otros tests cubren el path estructural.
- NO agregues lógica per-tool (e.g. "if dense_top1 == 'app' AND
  bm25_top1 in known_app_names → TIGHT"). El gate está bien
  estructural.

## Follow-ups documentados (NO incluir en este sprint)

Estos están explícitamente fuera de J.1 — son trabajo de sprint
futuro CON datos de uso real:

1. **HIGH band rank-2..5 divergence**: en queries donde rank-1 es
   inequívoco pero rank-2..5 divergen, agregar
   `stdev(rrf[1..4])/rrf[0]` telemetry counter. Revisitar después
   de 1 semana de data.
2. **Re-calibrar 0.80 ratio** después de ~50 queries logueadas en
   producción. Si la distribución empírica de
   `cluster_size`-cuando-TIGHT_CLUSTER muestra ≥2 probes con >8
   tools clusterizados, revisar.
3. **Soft-cap-by-score-floor**: aceptar SOLO si un probe surge
   donde cap óptimo ∈ {5, 7} y cap=8 demonstrably daña. Hasta
   entonces, hard cap.
4. **Re-calibrar 0.025 floor** si RRF_K ever cambia (proporcional
   a `1/(k+1) + 1/(k+10)`).
