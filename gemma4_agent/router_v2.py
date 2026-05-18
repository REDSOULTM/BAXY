"""Tool-routing v2 — semantic-first, sin regex.

Architecture (per Claude Research May 2026):

- **Layer 0** — semantic cache (LRU + cosine threshold).
- **Layer 1** — smalltalk gate (cheap centroid vs centroid check).
- **Layer 2** — hybrid retrieval (BM25 + dense embeddings + RRF k=60).
- **Layer 3** — confidence-gated fallback to popular tools.

Default OFF. Enable with env ``GEMMA4_ROUTER_V2=1``. A separate flag
``GEMMA4_ROUTER_V2_SHADOW=1`` runs v2 in parallel with v1 and only
logs the comparison (no behavioural change), enabling blind tests
in production.

- Model: ``intfloat/multilingual-e5-small`` int8 ONNX (100 langs, 384
  dim). Downloaded by ``scripts/bootstrap_e5_small.py``.
- BM25: ``rank-bm25`` (already a dep).
- RRF: Cormack & Clarke (2009), constant k=60.

If the ONNX model is not present on disk, ``is_enabled()`` returns
False and ``route_v2()`` returns ``([], {"source": "disabled"})``;
callers must treat that as "router v2 silently unavailable, fall back
to v1".
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_DIR = Path.home() / ".gemma4" / "models" / "e5-small"
MODEL_PATH = MODEL_DIR / "onnx" / "model_quantized.onnx"
TOKENIZER_PATH = MODEL_DIR / "tokenizer.json"
SMALLTALK_CENTROID_PATH = MODEL_DIR / "smalltalk_centroid.npy"

# Tool2Vec-style enriched descriptions (Sprint 8b). Loaded once at
# index-build time. The YAML lives next to this module so it ships
# with the package.
TOOL_DESCRIPTIONS_YAML = Path(__file__).parent / "tool_descriptions.yaml"

CACHE_MAX = 1000
CACHE_THETA = 0.88        # cosine similarity threshold for cache hit

# Smalltalk gate uses the DELTA between similarity-to-smalltalk-centroid
# and similarity-to-tools-centroid, not absolute values. e5-small
# embeddings are dense enough that absolute cosine for any query
# against either centroid lands in the 0.85-0.95 band; only the
# *difference* discriminates.
#
# Recalibrated 2026-05-17 (hotfix E.5) after the audit detected
# that 'pone benson boone' had delta=0.028 — just above the old
# 0.025 threshold — firing the gate on a clear music request.
# Raising to 0.030 means the gate only fires when the smalltalk
# signal is more clearly dominant. The probe set that anchors
# the new value:
#   "hola, como estas?"     → delta +0.033 (still fires ✓)
#   "thanks"                → delta +0.060 (still fires ✓)
#   "gracias"               → delta +0.080 (still fires ✓)
#   "pone benson boone"     → delta +0.028 (no longer fires ✓)
#   "abrime el Steam"       → delta +0.014 (never fired ✓)
#   "power point"           → delta +0.012 (never fired ✓)
SMALLTALK_DELTA_THETA = 0.030  # smalltalk - tools >= this → gate fires
# RRF top-1 floor. With 65 docs and RRF k=60 the theoretical max for a
# document that's #1 in BOTH dense and BM25 rankings is 2 * 1/61 ≈ 0.0328.
# Below this floor the top result is unrelated; pop in the popular set.
FALLBACK_THETA = 0.025
TOP_K = 16                # subset size cap
RRF_K = 60                # RRF constant per Cormack & Clarke 2009

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
# confidence and fallback paths never overlap. 4 is the minimum
# safe HIGH cap — gives the LLM 3 neighbours so it can recover
# when top-1 is marginally wrong (e.g. audio top-1 when intent was
# really audio_device).
HIGH_CONFIDENCE_TOP_SCORE = 0.030
HIGH_CONFIDENCE_CAP = 4
MEDIUM_CONFIDENCE_TOP_SCORE = 0.020
MEDIUM_CONFIDENCE_CAP = 8

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
# tools; cap=8 leaves a 3-4 tool margin for adjacent neighbours.
# Token cost of 2 extra schemas in 32K context is negligible vs.
# recall risk.
#
# Research: docs/architecture/compass_artifact_wf-4173e745-...md
# (literature sanity-checked: Shtok 2012, Bahri 2020/2023,
# Bruch 2023).
TIGHT_CLUSTER_TOP_SCORE = 0.025   # = FALLBACK_THETA; corroboration floor
TIGHT_CLUSTER_RATIO = 0.80        # rrf[4] / rrf[0] cutoff
TIGHT_CLUSTER_CAP = 8
TIGHT_CLUSTER_RANK_AT = 4         # which RRF rank to compare against rank-0

# Tools chosen for the low-confidence fallback. Order roughly matches
# the most-used tools observed in Sprint 2's usage report. Kept short
# so even on a worst-case query the LLM still has a viable subset.
_POPULAR_FALLBACK_TOOLS = (
    "filesystem", "media", "system", "web", "office",
    "app", "browser", "audio", "steam",
)

# Default smalltalk seed phrases. Used to bootstrap the smalltalk
# centroid the first time the router runs. A future sprint can move
# these to a YAML file and persist the precomputed centroid.
_SMALLTALK_SEED_PHRASES = (
    "hola", "hello", "hi", "hey",
    "buenos dias", "buenas tardes", "buenas noches",
    "good morning", "good afternoon", "good evening",
    "gracias", "thank you", "thanks",
    "como estas", "que tal", "how are you",
    "ok", "perfecto", "listo", "claro", "vale",
    "si", "no", "no se", "tal vez", "quizas",
    "chau", "adios", "bye", "hasta luego", "nos vemos",
    "que bueno", "genial", "excelente",
)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class RouterV2:
    """Process-singleton hybrid router. Lazy-loaded on first call.

    Singleton because the ONNX session + tool index together cost ~5s
    to build cold and ~120 MB of RSS; we want one instance shared
    across the agent worker, the FastAPI server, etc.
    """

    _instance: "RouterV2 | None" = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> "RouterV2":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Drop the singleton — exposed for tests that monkey-patch state."""
        with cls._lock:
            cls._instance = None

    def __init__(self) -> None:
        self._model: Any = None
        self._tokenizer: Any = None
        self._tool_names: list[str] = []
        self._tool_embeddings: Any = None        # np.ndarray [n_tools, 384]
        self._tool_bm25: Any = None
        self._smalltalk_centroid: Any = None     # np.ndarray [384]
        self._tools_centroid: Any = None         # np.ndarray [384]
        self._cache: "OrderedDict[str, tuple[Any, list[str]]]" = OrderedDict()
        self._loaded = False
        self._load_failed = False
        self._load_error = ""
        # Hotfix H 2026-05-17: per-process counters for rolling
        # calibration telemetry. The launcher emits a summary at
        # atexit so we can track v2 health over real sessions
        # without instrumenting every turn. load_failed is bumped
        # at most once per process (sticky).
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
            # Hotfix J 2026-05-17: track how often each confidence
            # band fires so the session_summary shows whether the
            # bands need re-calibration after real usage.
            "band_high": 0,
            "band_medium": 0,
            "band_low": 0,
            # Hotfix J.1 2026-05-17: TIGHT_CLUSTER band counter
            # joins the existing trio. The _record_call bump
            # (`f"band_{band}"`) picks it up automatically because
            # the band name is now "tight_cluster".
            "band_tight_cluster": 0,
        }
        self._load_failed_counted = False
        self._latency_ms_sum: float = 0.0
        self._latency_ms_max: float = 0.0

    def session_summary(self) -> dict[str, Any]:
        """Return aggregated stats since process start.

        Hotfix H 2026-05-17. Emitted from launcher's atexit hook
        so operators get a single 'router_v2_session_summary' log
        line at the end of each session. latency_ms_avg is over
        all calls; latency_ms_max is the worst single call seen.
        """
        calls = max(1, self._counters["calls_total"])
        return {
            **self._counters,
            "latency_ms_avg": round(self._latency_ms_sum / calls, 2),
            "latency_ms_max": round(self._latency_ms_max, 2),
        }

    def _record_call(self, telemetry: dict[str, Any]) -> None:
        """Update session counters from a route() telemetry dict.

        Called once per route() exit, regardless of which pipeline
        path produced the result.
        """
        self._counters["calls_total"] += 1
        src = str(telemetry.get("source") or "unknown")
        key = f"source_{src}"
        if key in self._counters:
            self._counters[key] += 1
        if telemetry.get("fallback_applied"):
            self._counters["fallback_applied"] += 1
        if telemetry.get("pending_tool_injected"):
            self._counters["pending_tool_injected"] += 1
        # Hotfix J 2026-05-17: bucket the call by adaptive-cap
        # confidence band. Only set on hybrid-path turns; cache /
        # smalltalk / empty_query / disabled leave it unset.
        band = telemetry.get("confidence_band")
        if band:
            key = f"band_{band}"
            if key in self._counters:
                self._counters[key] += 1
        if src == "disabled" and not self._load_failed_counted:
            self._counters["load_failed"] += 1
            self._load_failed_counted = True
        elapsed = float(telemetry.get("elapsed_ms") or 0.0)
        self._latency_ms_sum += elapsed
        if elapsed > self._latency_ms_max:
            self._latency_ms_max = elapsed

    def is_available(self) -> bool:
        """True only after a successful _ensure_loaded()."""
        return MODEL_PATH.exists() and not self._load_failed

    def _ensure_loaded(self) -> bool:
        """Lazy-init. Returns True if ready, False otherwise (sticky)."""
        if self._loaded:
            return True
        if self._load_failed:
            return False
        if not MODEL_PATH.exists():
            self._load_failed = True
            self._load_error = f"model not found at {MODEL_PATH}"
            return False
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer
            self._model = ort.InferenceSession(
                str(MODEL_PATH),
                providers=["CPUExecutionProvider"],
            )
            self._tokenizer = Tokenizer.from_file(str(TOKENIZER_PATH))
            self._build_index()
            self._loaded = True
            return True
        except Exception as exc:  # noqa: BLE001 — load must never crash callers
            self._load_failed = True
            self._load_error = f"{type(exc).__name__}: {exc}"
            return False

    # ------------------------------------------------------------------
    # Index construction
    # ------------------------------------------------------------------

    @staticmethod
    def _load_tool_descriptions() -> dict[str, dict[str, Any]]:
        """Load enriched descriptions from tool_descriptions.yaml.

        Returns a dict keyed by tool name. Each value is the parsed
        YAML entry (purpose, domain, example_queries.es/en). Falls
        back to {} if the YAML can't be parsed — callers must cope.
        """
        try:
            import yaml
            with open(TOOL_DESCRIPTIONS_YAML, encoding="utf-8") as fh:
                entries = yaml.safe_load(fh) or []
        except Exception:  # noqa: BLE001 — never crash the router on a bad YAML
            return {}
        return {e["name"]: e for e in entries if isinstance(e, dict) and "name" in e}

    @staticmethod
    def _doc_for_dense(entry: dict[str, Any], name: str) -> str:
        """Compose the dense-embedding document for a tool.

        Purpose (English technical summary) + ES + EN example queries
        joined into a single passage. The encoder ingests this once
        per tool at index-build time, so it can be richer than what
        BM25 receives.
        """
        purpose = (entry.get("purpose") or "").strip()
        eq = entry.get("example_queries") or {}
        es = " ".join(eq.get("es") or [])
        en = " ".join(eq.get("en") or [])
        body = " ".join(filter(None, [purpose, es, en])) or name
        return body

    @staticmethod
    def _doc_for_bm25(entry: dict[str, Any], name: str) -> str:
        """Compose the BM25 document for a tool.

        We include the tool name (so "steam"/"netflix" hit even from
        the name alone), the purpose, and the example_queries in both
        anchor languages — BM25 thrives on lexical diversity.
        """
        purpose = (entry.get("purpose") or "").strip()
        eq = entry.get("example_queries") or {}
        es = " ".join(eq.get("es") or [])
        en = " ".join(eq.get("en") or [])
        body = " ".join(filter(None, [name, purpose, es, en])) or name
        return body

    def _build_index(self) -> None:
        """Compute embeddings + BM25 + centroids for the 65 compound tools."""
        import numpy as np
        from rank_bm25 import BM25Okapi

        from .tools import COMPOUND_TOOL_SCHEMAS

        # 65 tool names, sorted for determinism.
        compound_names = sorted({
            s.get("function", {}).get("name", "")
            for s in COMPOUND_TOOL_SCHEMAS
            if s.get("function", {}).get("name")
        })
        self._tool_names = compound_names

        # Sprint 8b enriched descriptions. If the YAML doesn't load
        # (corrupt, missing), entries() returns {} and the dense/BM25
        # docs collapse to bare tool names — degraded but not broken.
        entries = self._load_tool_descriptions()

        # E5 convention: documents are prefixed with "passage: ",
        # queries with "query: ". Skipping this asymmetric prefix
        # measurably hurts recall on the same model.
        docs = [
            f"passage: {self._doc_for_dense(entries.get(name, {}), name)}"
            for name in compound_names
        ]

        # Dense embeddings (already L2-normalized by _encode_batch).
        self._tool_embeddings = self._encode_batch(docs)

        # BM25 index over the bare (prefix-free) docs.
        bare_docs = [
            self._doc_for_bm25(entries.get(name, {}), name)
            for name in compound_names
        ]
        tokenized = [self._tokenize_for_bm25(d) for d in bare_docs]
        self._tool_bm25 = BM25Okapi(tokenized)

        # Tools centroid: average of all 65 tool embeddings.
        self._tools_centroid = np.mean(self._tool_embeddings, axis=0)
        norm = np.linalg.norm(self._tools_centroid)
        if norm > 1e-9:
            self._tools_centroid = self._tools_centroid / norm

        # Smalltalk centroid: load precomputed if available, else
        # compute from seed phrases.
        if SMALLTALK_CENTROID_PATH.exists():
            try:
                self._smalltalk_centroid = np.load(SMALLTALK_CENTROID_PATH)
            except Exception:  # noqa: BLE001
                self._smalltalk_centroid = None
        if self._smalltalk_centroid is None:
            seeds = [f"query: {p}" for p in _SMALLTALK_SEED_PHRASES]
            smalltalk_embs = self._encode_batch(seeds)
            self._smalltalk_centroid = np.mean(smalltalk_embs, axis=0)
            sm_norm = np.linalg.norm(self._smalltalk_centroid)
            if sm_norm > 1e-9:
                self._smalltalk_centroid = self._smalltalk_centroid / sm_norm

    @staticmethod
    def _tokenize_for_bm25(text: str) -> list[str]:
        """Unicode-aware tokenization for BM25, language-agnostic.

        No per-language stopwords — we keep all words because for a
        65-doc index the IDF term in BM25 already handles common-word
        suppression, and stopword lists would discriminate against
        non-English queries.
        """
        import re
        return re.findall(r"\w+", text.lower(), re.UNICODE)

    def _encode_batch(self, texts: list[str]) -> Any:
        """Run ONNX inference; return [n, 384] L2-normalized embeddings.

        E5-style mean pooling: average token embeddings over the
        attention mask, then L2-normalize. ``token_type_ids`` is
        required by this particular ONNX export (BERT-style); we
        always pass zeros.
        """
        import numpy as np

        encs = [self._tokenizer.encode(t) for t in texts]
        max_len = max(len(e.ids) for e in encs)
        input_ids = np.zeros((len(encs), max_len), dtype=np.int64)
        attention_mask = np.zeros((len(encs), max_len), dtype=np.int64)
        for i, e in enumerate(encs):
            input_ids[i, : len(e.ids)] = e.ids
            attention_mask[i, : len(e.ids)] = 1
        token_type_ids = np.zeros_like(input_ids)

        outputs = self._model.run(
            None,
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids,
            },
        )
        token_embeddings = outputs[0]  # [n, seq, 384]
        mask_expanded = attention_mask[..., None].astype(np.float32)
        summed = (token_embeddings * mask_expanded).sum(axis=1)
        counts = mask_expanded.sum(axis=1).clip(min=1e-9)
        embeddings = summed / counts
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True).clip(min=1e-9)
        return embeddings / norms

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _cache_get(self, query_emb: Any) -> list[str] | None:
        """Linear-scan semantic cache lookup. Hit iff cosine > CACHE_THETA."""
        import numpy as np

        if not self._cache:
            return None
        for key, (cached_emb, subset) in self._cache.items():
            sim = float(np.dot(query_emb, cached_emb))
            if sim > CACHE_THETA:
                self._cache.move_to_end(key)
                return list(subset)
        return None

    def _cache_put(self, query: str, query_emb: Any, subset: list[str]) -> None:
        key = hashlib.sha256(query.lower().strip().encode("utf-8")).hexdigest()
        self._cache[key] = (query_emb, list(subset))
        self._cache.move_to_end(key)
        while len(self._cache) > CACHE_MAX:
            self._cache.popitem(last=False)

    # ------------------------------------------------------------------
    # Public entry
    # ------------------------------------------------------------------

    def route(
        self,
        query: str,
        *,
        pending_tool_hint: str | None = None,
    ) -> tuple[list[str], dict[str, Any]]:
        """Resolve a query to a tool subset.

        Returns ``(subset, telemetry)``. ``telemetry["source"]`` is one
        of: ``cache``, ``smalltalk``, ``hybrid``, ``disabled``,
        ``empty_query``. ``elapsed_ms`` is always present.

        pending_tool_hint (hotfix F 2026-05-17): tool name from a
        pending intent (set when a previous tool result returned
        status='needs_user'). When present, that tool is injected
        into the returned subset regardless of pipeline path —
        cache, smalltalk, or hybrid. The LLM still decides whether
        to call it; the hint only widens reachability.
        """
        import numpy as np

        def _apply_hint(subset: list[str]) -> list[str]:
            """Hotfix F 2026-05-17. Inject pending_tool_hint at the
            head if missing. Pure helper so every return path applies
            the same logic. No-op when hint is None or already present.

            Hotfix H 2026-05-17: also records the call in the
            session counters so every return path bumps the right
            tally (calls_total, source_*, fallback_applied,
            pending_tool_injected, latency_ms_*).
            """
            if pending_tool_hint and pending_tool_hint not in subset:
                subset = [pending_tool_hint, *subset]
                telemetry["pending_tool_injected"] = pending_tool_hint
            self._record_call(telemetry)
            return subset

        t0 = time.monotonic()
        telemetry: dict[str, Any] = {"source": "disabled", "elapsed_ms": 0.0}

        if not self._ensure_loaded():
            telemetry["error"] = self._load_error
            telemetry["elapsed_ms"] = (time.monotonic() - t0) * 1000
            return _apply_hint([]), telemetry

        if not query or not query.strip():
            telemetry["source"] = "empty_query"
            telemetry["elapsed_ms"] = (time.monotonic() - t0) * 1000
            return _apply_hint([]), telemetry

        # Encode once and reuse for cache + gate + dense retrieval.
        query_emb = self._encode_batch([f"query: {query}"])[0]

        # Layer 0 — semantic cache.
        cached = self._cache_get(query_emb)
        if cached is not None:
            telemetry["source"] = "cache"
            telemetry["elapsed_ms"] = (time.monotonic() - t0) * 1000
            return _apply_hint(cached), telemetry

        # Layer 1 — smalltalk gate (delta between centroids).
        # See SMALLTALK_DELTA_THETA docstring for the calibration story.
        smalltalk_sim = float(np.dot(query_emb, self._smalltalk_centroid))
        tools_sim = float(np.dot(query_emb, self._tools_centroid))
        smalltalk_delta = smalltalk_sim - tools_sim
        if smalltalk_delta >= SMALLTALK_DELTA_THETA:
            telemetry["source"] = "smalltalk"
            telemetry["smalltalk_sim"] = smalltalk_sim
            telemetry["tools_sim"] = tools_sim
            telemetry["smalltalk_delta"] = smalltalk_delta
            telemetry["elapsed_ms"] = (time.monotonic() - t0) * 1000
            self._cache_put(query, query_emb, [])
            return _apply_hint([]), telemetry

        # Layer 2 — hybrid retrieval (BM25 + dense, fused via RRF).
        dense_scores = self._tool_embeddings @ query_emb        # cosine on L2-norm embs
        dense_ranking = np.argsort(-dense_scores)               # descending

        bm25_scores = self._tool_bm25.get_scores(
            self._tokenize_for_bm25(query),
        )
        bm25_ranking = np.argsort(-bm25_scores)

        rrf_scores = np.zeros(len(self._tool_names), dtype=np.float64)
        for rank, idx in enumerate(dense_ranking):
            rrf_scores[idx] += 1.0 / (RRF_K + rank + 1)
        # Hotfix J.1 2026-05-17: BM25 saturation guard. Tools with
        # raw BM25=0 are NOT genuinely ranked — they appear in the
        # ranking in arbitrary order due to ties at zero. Treating
        # them as "not in BM25 list" prevents spurious cluster
        # inflation in the TIGHT_CLUSTER detector below. The dense-
        # only contribution survives, so relevant tools still rank
        # correctly; only the rank-tail scores change.
        for rank, idx in enumerate(bm25_ranking):
            if float(bm25_scores[idx]) <= 0.0:
                continue
            rrf_scores[idx] += 1.0 / (RRF_K + rank + 1)

        # Always compute the full ranking first — we cap after we
        # know which confidence band we're in (hotfix J 2026-05-17).
        top_indices = np.argsort(-rrf_scores)[:TOP_K]
        subset_full = [self._tool_names[int(i)] for i in top_indices]
        top_score = float(rrf_scores[top_indices[0]])

        # Adaptive cap by retriever agreement + RRF score.
        # Detection is 100% structural — reads top1 names from the
        # rankings route() already computed for telemetry.
        dense_top1_name = self._tool_names[int(dense_ranking[0])]
        bm25_top1_name = self._tool_names[int(bm25_ranking[0])]
        retrievers_agree = dense_top1_name == bm25_top1_name
        # rrf_sorted is reused below for both the TIGHT_CLUSTER
        # gate and the cluster_size telemetry — compute once.
        rrf_sorted = np.sort(rrf_scores)[::-1]  # descending
        if retrievers_agree and top_score >= HIGH_CONFIDENCE_TOP_SCORE:
            adaptive_cap = HIGH_CONFIDENCE_CAP
            confidence_band = "high"
        elif retrievers_agree and top_score >= MEDIUM_CONFIDENCE_TOP_SCORE:
            adaptive_cap = MEDIUM_CONFIDENCE_CAP
            confidence_band = "medium"
        else:
            # Hotfix J.1 2026-05-17: distinguish "tight cluster of
            # real candidates" from "genuinely ambiguous → TOP_K
            # fallback". Both retrievers disagree on top-1 but if
            # their rankings overlap enough that the top-5 RRF
            # scores stay close to top-1, there are 4-5 real
            # candidates, not 16.
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

        # Hotfix J.1 2026-05-17: cluster_size telemetry — count of
        # top-TOP_K candidates whose RRF score is within 80% of
        # top-1. Healthy regime for TIGHT_CLUSTER is [3, 8];
        # cluster_size > 8 while firing TIGHT_CLUSTER signals
        # BM25-saturation pathology (sentinel for future drift).
        top_k_scores = rrf_sorted[:TOP_K] if len(rrf_sorted) >= TOP_K else rrf_sorted
        if len(top_k_scores) > 0 and float(top_k_scores[0]) > 0.0:
            cluster_size = int(np.sum(
                top_k_scores / float(top_k_scores[0]) >= TIGHT_CLUSTER_RATIO
            ))
        else:
            cluster_size = 0

        telemetry["source"] = "hybrid"
        telemetry["top_score"] = top_score
        telemetry["dense_top1"] = dense_top1_name
        telemetry["bm25_top1"] = bm25_top1_name
        telemetry["smalltalk_sim"] = smalltalk_sim
        telemetry["tools_sim"] = tools_sim
        telemetry["smalltalk_delta"] = smalltalk_delta
        # Hotfix J: expose the adaptive cap decision so we can
        # audit whether the bands are well-calibrated in production.
        telemetry["confidence_band"] = confidence_band
        telemetry["adaptive_cap"] = adaptive_cap
        telemetry["retrievers_agree"] = retrievers_agree
        # Hotfix J.1 2026-05-17: cluster_size is the count of
        # candidates within 80% of top-1; used to audit the
        # TIGHT_CLUSTER calibration in production.
        telemetry["cluster_size"] = cluster_size

        # Layer 3 — confidence fallback. RRF top-1 below FALLBACK_THETA
        # means even the best document is unrelated to the query;
        # surface the popular tools so the LLM has something to pick.
        if top_score < FALLBACK_THETA:
            popular = [t for t in _POPULAR_FALLBACK_TOOLS if t in self._tool_names]
            fallback = popular[:8] + [subset[0]] if subset else popular[:8]
            subset = list(dict.fromkeys(fallback))
            telemetry["fallback_applied"] = True

        telemetry["elapsed_ms"] = (time.monotonic() - t0) * 1000
        self._cache_put(query, query_emb, subset)
        return _apply_hint(subset), telemetry


# ---------------------------------------------------------------------------
# Module-level entry points
# ---------------------------------------------------------------------------

def route_v2(
    query: str,
    *,
    pending_tool_hint: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Module entry. Returns ``([], {"source": "disabled"})`` if model absent.

    pending_tool_hint (hotfix F 2026-05-17): forwarded to
    RouterV2.route() — when set, that tool is forced into the
    returned subset regardless of which pipeline path served the
    query (cache, smalltalk, hybrid, disabled).
    """
    return RouterV2.get().route(query, pending_tool_hint=pending_tool_hint)


def is_enabled() -> bool:
    """v2 is the authoritative router by default when the model is
    available (hotfix E 2026-05-17, Sprint 8c activation).

    Operator controls:
      GEMMA4_ROUTER_V1_ONLY=1   -> force v1 (regex planner) only.
      GEMMA4_ROUTER_V2=0/false  -> same effect; explicit.
      <unset> + model present   -> v2 is authoritative.
      <unset> + model absent    -> v1 fallback automatically.

    If router_v2 fails to load (sticky _load_failed), v1 is the
    automatic fallback — no env var needed.
    """
    v1_only = (os.environ.get("GEMMA4_ROUTER_V1_ONLY") or "").strip().lower()
    if v1_only in {"1", "true", "yes", "on"}:
        return False
    explicit = (os.environ.get("GEMMA4_ROUTER_V2") or "").strip().lower()
    if explicit in {"0", "false", "no", "off"}:
        return False
    if explicit in {"1", "true", "yes", "on"}:
        return RouterV2.get().is_available()
    return RouterV2.get().is_available()


def is_shadow() -> bool:
    """Shadow mode logs how v2 would route without changing v1's pick.

    Default behavior (hotfix E 2026-05-17): shadow is ON whenever
    the e5-small model is on disk AND GEMMA4_ROUTER_V2_SHADOW is
    not explicitly '0' / 'false' / 'off'. Operator can disable
    with GEMMA4_ROUTER_V2_SHADOW=0 if shadow logging itself causes
    problems.
    """
    raw = (os.environ.get("GEMMA4_ROUTER_V2_SHADOW") or "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    return MODEL_PATH.exists()


__all__ = [
    "MODEL_DIR",
    "MODEL_PATH",
    "TOOL_DESCRIPTIONS_YAML",
    "RouterV2",
    "route_v2",
    "is_enabled",
    "is_shadow",
    # Hotfix J 2026-05-17: adaptive cap constants exported so
    # tests can pin the band boundaries.
    "HIGH_CONFIDENCE_TOP_SCORE",
    "HIGH_CONFIDENCE_CAP",
    "MEDIUM_CONFIDENCE_TOP_SCORE",
    "MEDIUM_CONFIDENCE_CAP",
    "TOP_K",
    # Hotfix J.1 2026-05-17: TIGHT_CLUSTER band constants.
    "TIGHT_CLUSTER_TOP_SCORE",
    "TIGHT_CLUSTER_RATIO",
    "TIGHT_CLUSTER_CAP",
    "TIGHT_CLUSTER_RANK_AT",
    "FALLBACK_THETA",
    "RRF_K",
]
