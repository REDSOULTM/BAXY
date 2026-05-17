# PROMPT — Sprint 8a (infra del nuevo routing, sin regex)

> Continúa el mismo chat de Claude Code (Sprints 0-7 + post-audit fix).
> **Sprint 8a:** infra del nuevo router. NO toca descriptions ni hace
> blind test todavía (eso es 8b y 8c).
>
> Plan completo:
> - **8a:** infra (e5-small ONNX + bm25s + RRF + smalltalk gate + cache). ~1 noche.
> - **8b:** enriquecer las 65 tool descriptions con example_queries ES+EN. ~1 noche híbrida.
> - **8c:** blind test + tuning + self-improving loop. ~1 noche.

---

## Origen del diseño

Investigación de Claude Research (mayo 2026) sobre tool-routing
para agents locales con 65 tools y multi-idioma. Guardada en:
`docs/architecture/compass_artifact_wf-d0912118-4331-40c8-9029-0e66be0fb5b7_text_markdown.md`.

Resumen de la recomendación principal (cita §5):
- Modelo: `intfloat/multilingual-e5-small` int8 ONNX (~113 MB, 384 dim, 100 idiomas).
- Backbone: hybrid BM25 + dense con Reciprocal Rank Fusion (k=60).
- Pre-gate: smalltalk centroide vs tools centroide (sin regex).
- Cache: LRU semantic similarity con θ=0.88.
- NO cross-encoder rerank en hot path (probado 350ms CPU, fuera de budget).

Papers que fundamentan:
- RAG-MCP (arXiv:2505.03275)
- Toolshed (ICAART 2025)
- Tool2Vec (arXiv:2409.02141)
- Re-Invoke (Google Research 2024)

## Estado del repo al arrancar

- HEAD: `99abf5a` (fix de "power point" del Sprint 7 follow-up).
- Working tree limpio.
- 65 compound tools intactas.
- `onnxruntime==1.23.2` y `rank-bm25==0.2.2` ya instalados.
- `sentence-transformers==5.3.0` instalado (lo seguimos usando como
  fallback durante migración).
- `semantic_router.py` actual: usa MiniLM-L12-v2, solo path de fallback
  cuando regex devuelve `[]`.
- `planner.py` actual: regex-first, semantic-fallback. **Sprint 8a
  cambia esto a semantic-first.**

---

## Prompt completo (copy/paste al chat existente)

```
Continuamos. Estado: rama PortandoLoMejor, HEAD 99abf5a, working
tree limpio, 65 compound tools, 743 tests verde.

# OBJETIVO DE SPRINT 8a

Crear la INFRA del nuevo router universal sin regex, basada en la
investigación de Claude Research (mayo 2026). NO tocar las
descriptions de tools (Sprint 8b) ni hacer blind test (Sprint 8c).

Resultado al cierre: un módulo nuevo `gemma4_agent/router_v2.py`
con la pipeline de 4 layers (smalltalk gate, cache, hybrid retrieval,
fallback), corriendo en paralelo al router viejo PERO desactivado
por default (env var `GEMMA4_ROUTER_V2=1` para activarlo).

# REGLAS GENERALES

1. Trabajás en PortandoLoMejor. Commits chicos, prefijo "sprint8a.X:".
2. NO toques planner.py ni semantic_router.py. Router viejo sigue
   activo por default. Router nuevo coexiste detrás de feature flag.
3. NO toques las tool descriptions actuales (Sprint 8b las
   reescribirá).
4. NO modifiques las 65 compound tools.
5. NO instales `bm25s` todavía (ver pre-flight 8a.1 — decidimos si
   bm25s vs rank-bm25 existente).
6. Verificación post-commit:
   - `python -c "import gemma4_agent"` OK
   - `python -c "from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"` == 65
   - `python -m gemma4_agent.launcher status` OK
7. NUNCA git add -A. Archivos específicos.
8. Si dudás entre implementar o esperar: dejá lo dudoso para 8b/8c.

# CONTEXTO TÉCNICO

- El router v2 lee de `TOOL_DESCRIPTIONS` actual (62 entries en
  `semantic_router.py`). En Sprint 8b se reemplazan por el nuevo
  formato YAML con `purpose + example_queries`. Hoy en 8a usamos
  las viejas — el bm25 va a tener menos material pero el código
  funciona.
- El embedding model nuevo es ONNX, NO sentence-transformers Python.
  Hay que descargarlo de huggingface (`Xenova/multilingual-e5-small`)
  o vendoreaarlo. El modelo ONNX vive en `~/.gemma4/models/e5-small/`.

# WORKFLOW

## 8a.1 — Pre-flight: ONNX e5-small + bm25 library

**Decisión 1: bm25s vs rank-bm25**

`rank-bm25==0.2.2` ya está instalado. `bm25s` (Lù 2024) es 500x más
rápido pero no está instalado.

Para 65 documents la diferencia es trivial — ambos sub-ms. Usá el
que ya está: `rank-bm25`. Si más tarde el catálogo crece, migrás.

**Decisión 2: descargar e5-small ONNX**

Verificá si `~/.gemma4/models/e5-small/` ya existe. Si no:
- El usuario tiene autorización blanket para instalar deps faltantes
  (ver memory feedback_install_authorization).
- Descargar `Xenova/multilingual-e5-small` desde huggingface:
  ```python
  from huggingface_hub import snapshot_download
  snapshot_download(
      repo_id="Xenova/multilingual-e5-small",
      local_dir="<HOME>/.gemma4/models/e5-small",
      allow_patterns=["onnx/model_quantized.onnx", "tokenizer*", "*.json"],
  )
  ```
- Tamaño esperado: ~113 MB (model_quantized.onnx) + tokenizer ~5 MB.

Si la descarga falla por red, **NO abortés el sprint** — anotalo
en log y seguís con el módulo `router_v2.py`. El usuario lo bajará
cuando esté online. El módulo debe degradar a "router_v2 disabled,
model not available".

Commit: "sprint8a.1: bootstrap e5-small ONNX download (idempotent)"

## 8a.2 — Crear `gemma4_agent/router_v2.py`

Esqueleto del módulo:

```python
"""Tool-routing v2 — semantic-first, sin regex.

Architecture (per Claude Research May 2026):
- Layer 0: cache LRU semantic
- Layer 1: smalltalk gate via centroid
- Layer 2: hybrid retrieval (BM25 + dense + RRF k=60)
- Layer 3: confidence-gated fallback

Default OFF. Enable with env GEMMA4_ROUTER_V2=1.

Model: intfloat/multilingual-e5-small int8 ONNX, 100 langs, 384 dim.
BM25: rank-bm25 (existing dep). RRF: Cormack & Clarke 2009 k=60.
"""
from __future__ import annotations

import hashlib
import os
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

MODEL_DIR = Path.home() / ".gemma4" / "models" / "e5-small"
MODEL_PATH = MODEL_DIR / "onnx" / "model_quantized.onnx"
CACHE_MAX = 1000
CACHE_THETA = 0.88
SMALLTALK_THETA = 0.55
TOOLS_THETA = 0.35
FALLBACK_THETA = 0.30
TOP_K = 16
RRF_K = 60


class RouterV2:
    """Singleton router. Lazy-loaded on first call."""

    _instance: "RouterV2 | None" = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> "RouterV2":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._tool_names: list[str] = []
        self._tool_embeddings = None  # np.ndarray [n_tools, 384]
        self._tool_bm25 = None
        self._smalltalk_centroid = None
        self._tools_centroid = None
        self._cache: OrderedDict[str, tuple[Any, list[str]]] = OrderedDict()
        # cache: key = sha256(normalized text), value = (query_emb, subset)
        self._loaded = False
        self._load_failed = False
        self._load_error = ""

    def is_available(self) -> bool:
        return MODEL_PATH.exists() and not self._load_failed

    def _ensure_loaded(self) -> bool:
        """Lazy-init. Returns True if ready."""
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
            tokenizer_path = MODEL_DIR / "tokenizer.json"
            self._tokenizer = Tokenizer.from_file(str(tokenizer_path))
            self._build_index()
            self._loaded = True
            return True
        except Exception as exc:
            self._load_failed = True
            self._load_error = f"{type(exc).__name__}: {exc}"
            return False

    def _build_index(self):
        """Compute embeddings for all 65 tool descriptions + centroids."""
        # Leer descriptions del lugar correcto.
        # Sprint 8a: usar TOOL_DESCRIPTIONS de semantic_router.
        # Sprint 8b: switch a `prompts/tool_descriptions/*.yaml`.
        from .semantic_router import TOOL_DESCRIPTIONS
        from .tools import COMPOUND_TOOL_SCHEMAS
        # Tools del LLM (65)
        compound_names = sorted({
            s.get("function", {}).get("name", "")
            for s in COMPOUND_TOOL_SCHEMAS
            if s.get("function", {}).get("name")
        })
        # Descriptions disponibles
        self._tool_names = compound_names
        docs = []
        for name in compound_names:
            desc = TOOL_DESCRIPTIONS.get(name, name)
            docs.append(f"passage: {desc}")  # E5 convention
        # Dense embeddings
        self._tool_embeddings = self._encode_batch(docs)
        # BM25 index
        from rank_bm25 import BM25Okapi
        tokenized = [self._tokenize_for_bm25(d) for d in docs]
        self._tool_bm25 = BM25Okapi(tokenized)
        # Centroids
        import numpy as np
        self._tools_centroid = np.mean(self._tool_embeddings, axis=0)
        # Smalltalk centroid: precomputado offline (ver 8a.3)
        # Por ahora, embed de frases default si no hay archivo.
        smalltalk_path = MODEL_DIR / "smalltalk_centroid.npy"
        if smalltalk_path.exists():
            self._smalltalk_centroid = np.load(smalltalk_path)
        else:
            # Compute from defaults (Sprint 8a inline). 8b puede mover
            # estas frases a un archivo yaml.
            smalltalk_phrases = [
                "hola", "hello", "buenos dias", "buenas tardes",
                "gracias", "thank you", "como estas", "que tal",
                "ok", "perfecto", "listo", "claro",
                "si", "no", "no se", "tal vez",
                "chau", "bye", "hasta luego", "nos vemos",
            ]
            smalltalk_embs = self._encode_batch(
                [f"query: {p}" for p in smalltalk_phrases]
            )
            self._smalltalk_centroid = np.mean(smalltalk_embs, axis=0)

    def _tokenize_for_bm25(self, text: str) -> list[str]:
        """Unicode-aware tokenization for BM25, no per-language stopwords."""
        import re
        # Split on whitespace + punctuation, keep accents
        tokens = re.findall(r"\w+", text.lower(), re.UNICODE)
        return tokens

    def _encode_batch(self, texts: list[str]):
        """Run ONNX inference, return [n, 384] np.ndarray L2-normalized."""
        import numpy as np
        # Tokenize
        encs = [self._tokenizer.encode(t) for t in texts]
        max_len = max(len(e.ids) for e in encs)
        input_ids = np.zeros((len(encs), max_len), dtype=np.int64)
        attention_mask = np.zeros((len(encs), max_len), dtype=np.int64)
        for i, e in enumerate(encs):
            input_ids[i, :len(e.ids)] = e.ids
            attention_mask[i, :len(e.ids)] = 1
        # Run
        outputs = self._model.run(
            None,
            {"input_ids": input_ids, "attention_mask": attention_mask},
        )
        # Mean pooling + L2 normalize
        token_embeddings = outputs[0]
        mask_expanded = attention_mask[..., None].astype(np.float32)
        summed = (token_embeddings * mask_expanded).sum(axis=1)
        counts = mask_expanded.sum(axis=1).clip(min=1e-9)
        embeddings = summed / counts
        # L2 normalize
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True).clip(min=1e-9)
        return embeddings / norms

    def _cache_get(self, query_emb) -> list[str] | None:
        """Check semantic cache. Returns subset if hit, None otherwise."""
        import numpy as np
        if not self._cache:
            return None
        # Linear scan (cache is small ~1000)
        for key, (cached_emb, subset) in self._cache.items():
            sim = float(np.dot(query_emb, cached_emb))
            if sim > CACHE_THETA:
                # LRU touch
                self._cache.move_to_end(key)
                return subset
        return None

    def _cache_put(self, query: str, query_emb, subset: list[str]):
        key = hashlib.sha256(query.lower().strip().encode("utf-8")).hexdigest()
        self._cache[key] = (query_emb, subset)
        self._cache.move_to_end(key)
        while len(self._cache) > CACHE_MAX:
            self._cache.popitem(last=False)

    def route(self, query: str) -> tuple[list[str], dict]:
        """Main entry. Returns (subset, telemetry_dict).

        telemetry_dict keys:
          - source: "cache" | "smalltalk" | "hybrid" | "fallback" | "disabled"
          - elapsed_ms: float
          - top_score: float | None (only for hybrid)
        """
        import time
        import numpy as np
        t0 = time.monotonic()
        telemetry: dict[str, Any] = {"source": "disabled", "elapsed_ms": 0.0}
        if not self._ensure_loaded():
            telemetry["source"] = "disabled"
            telemetry["error"] = self._load_error
            telemetry["elapsed_ms"] = (time.monotonic() - t0) * 1000
            return [], telemetry
        if not query or not query.strip():
            telemetry["source"] = "empty_query"
            telemetry["elapsed_ms"] = (time.monotonic() - t0) * 1000
            return [], telemetry
        # Encode query
        query_emb = self._encode_batch([f"query: {query}"])[0]
        # Layer 0: cache
        cached = self._cache_get(query_emb)
        if cached is not None:
            telemetry["source"] = "cache"
            telemetry["elapsed_ms"] = (time.monotonic() - t0) * 1000
            return cached, telemetry
        # Layer 1: smalltalk gate
        smalltalk_sim = float(np.dot(query_emb, self._smalltalk_centroid))
        tools_sim = float(np.dot(query_emb, self._tools_centroid))
        if smalltalk_sim > SMALLTALK_THETA and tools_sim < TOOLS_THETA:
            telemetry["source"] = "smalltalk"
            telemetry["smalltalk_sim"] = smalltalk_sim
            telemetry["tools_sim"] = tools_sim
            telemetry["elapsed_ms"] = (time.monotonic() - t0) * 1000
            self._cache_put(query, query_emb, [])
            return [], telemetry
        # Layer 2: hybrid retrieval
        # Dense: cosine over normalized embeddings (already normalized)
        dense_scores = self._tool_embeddings @ query_emb
        dense_ranking = np.argsort(-dense_scores)  # descending
        # BM25
        bm25_scores = self._tool_bm25.get_scores(self._tokenize_for_bm25(query))
        bm25_ranking = np.argsort(-bm25_scores)
        # RRF
        rrf_scores = np.zeros(len(self._tool_names))
        for rank, idx in enumerate(dense_ranking):
            rrf_scores[idx] += 1.0 / (RRF_K + rank + 1)
        for rank, idx in enumerate(bm25_ranking):
            rrf_scores[idx] += 1.0 / (RRF_K + rank + 1)
        # Top-K
        top_indices = np.argsort(-rrf_scores)[:TOP_K]
        subset = [self._tool_names[i] for i in top_indices]
        top_score = float(rrf_scores[top_indices[0]])
        telemetry["source"] = "hybrid"
        telemetry["top_score"] = top_score
        telemetry["dense_top1"] = self._tool_names[dense_ranking[0]]
        telemetry["bm25_top1"] = self._tool_names[bm25_ranking[0]]
        # Layer 3: confidence gate
        if top_score < FALLBACK_THETA:
            # Fallback: tools populares + top-1
            popular = ["filesystem", "media", "system", "web", "office",
                       "app", "browser", "audio", "steam"]
            popular = [t for t in popular if t in self._tool_names]
            fallback = popular[:8] + [subset[0]]
            subset = list(dict.fromkeys(fallback))  # dedupe preserving order
            telemetry["fallback_applied"] = True
        telemetry["elapsed_ms"] = (time.monotonic() - t0) * 1000
        self._cache_put(query, query_emb, subset)
        return subset, telemetry


def route_v2(query: str) -> tuple[list[str], dict]:
    """Public entry. Returns ([], {"source": "disabled"}) if model not ready."""
    return RouterV2.get().route(query)


def is_enabled() -> bool:
    """True only if env GEMMA4_ROUTER_V2 is on AND model is loadable."""
    raw = (os.environ.get("GEMMA4_ROUTER_V2") or "").strip().lower()
    if raw not in {"1", "true", "yes", "on"}:
        return False
    return RouterV2.get().is_available()
```

Commit: "sprint8a.2: add router_v2.py with hybrid retrieval pipeline (default OFF)"

## 8a.3 — Tests del router_v2

Crear `gemma4_agent/test_router_v2.py`:

```python
"""Tests for router_v2 — semantic-first tool routing.

Skips all tests if the e5-small ONNX model is not present (cold install).
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path

from gemma4_agent.router_v2 import RouterV2, MODEL_PATH


@unittest.skipUnless(MODEL_PATH.exists(), "e5-small ONNX model not installed")
class RouterV2BasicTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.router = RouterV2.get()
        assert cls.router._ensure_loaded(), f"Load failed: {cls.router._load_error}"

    def test_is_available(self):
        self.assertTrue(self.router.is_available())

    def test_smalltalk_gate_es(self):
        subset, telemetry = self.router.route("hola, como estas?")
        self.assertEqual(subset, [])
        self.assertEqual(telemetry["source"], "smalltalk")

    def test_smalltalk_gate_en(self):
        subset, telemetry = self.router.route("thanks")
        self.assertEqual(subset, [])
        self.assertEqual(telemetry["source"], "smalltalk")

    def test_power_point_routes_to_office(self):
        """The bug that motivated Sprint 8: 'power point' must reach office."""
        subset, telemetry = self.router.route("Puedes hacerme un power point?")
        self.assertIn("office", subset, f"got: {subset}")
        self.assertEqual(telemetry["source"], "hybrid")

    def test_steam_routes_to_steam(self):
        subset, _ = self.router.route("abrime el Steam")
        self.assertIn("steam", subset)

    def test_filesystem_routes_to_filesystem(self):
        subset, _ = self.router.route("borrá el archivo X de mi escritorio")
        self.assertIn("filesystem", subset)

    def test_multilang_french(self):
        """Multi-language without explicit FR queries."""
        subset, _ = self.router.route("ouvre Chrome")
        # Should route to browser/app — exact match not guaranteed, but
        # at least one of these.
        self.assertTrue(
            any(t in subset for t in ["browser", "app", "browser_real"]),
            f"got: {subset}",
        )

    def test_cache_hit_on_repeat(self):
        # First call
        s1, t1 = self.router.route("hola")
        # Second call (same text → cache hit)
        s2, t2 = self.router.route("hola")
        self.assertEqual(s1, s2)
        # Second call should be cache or smalltalk; both are valid

    def test_latency_under_budget(self):
        # Cold + warm. We test warm (cache loaded).
        self.router.route("warmup")
        subset, telemetry = self.router.route("abrime el navegador")
        self.assertLess(telemetry["elapsed_ms"], 300.0,
                        f"latency budget exceeded: {telemetry['elapsed_ms']:.1f}ms")

    def test_top_k_capped(self):
        subset, _ = self.router.route("hacer cualquier cosa")
        self.assertLessEqual(len(subset), 16 + 5)  # 16 + popular fallback


@unittest.skipUnless(MODEL_PATH.exists(), "e5-small ONNX model not installed")
class RouterV2EnvDisabledTest(unittest.TestCase):
    def test_is_enabled_false_by_default(self):
        from gemma4_agent.router_v2 import is_enabled
        # No env var set → False
        old = os.environ.pop("GEMMA4_ROUTER_V2", None)
        try:
            self.assertFalse(is_enabled())
        finally:
            if old is not None:
                os.environ["GEMMA4_ROUTER_V2"] = old


if __name__ == "__main__":
    unittest.main()
```

Commit: "sprint8a.3: tests for router_v2 (skip if model not installed)"

## 8a.4 — Cableado opt-in en agent.py

NO reemplazar el router viejo. Agregar un BLOQUE PARALELO controlado
por env var:

En `agent.py:run_content`, después de calcular `selected_tool_names`
con el router viejo (línea ~559 aprox), agregar:

```python
# Sprint 8a: router_v2 shadow run (default OFF).
# When GEMMA4_ROUTER_V2=1, replaces selected_tool_names.
# When GEMMA4_ROUTER_V2_SHADOW=1, only logs what v2 would have picked,
# without changing the actual subset (for blind comparison).
try:
    from .router_v2 import is_enabled as _v2_enabled, route_v2
    v2_enabled = _v2_enabled()
    v2_shadow = (os.environ.get("GEMMA4_ROUTER_V2_SHADOW") or "").strip().lower() in {"1","true","yes","on"}
    if v2_enabled or v2_shadow:
        v2_subset, v2_telemetry = route_v2(raw_text_early or "")
        self.trace.event(
            turn_id, "router_v2",
            shadow=v2_shadow,
            v2_subset=v2_subset,
            v1_subset=list(selected_tool_names),
            agreement=sorted(set(v2_subset) & set(selected_tool_names)),
            disagreement_v2_only=sorted(set(v2_subset) - set(selected_tool_names)),
            disagreement_v1_only=sorted(set(selected_tool_names) - set(v2_subset)),
            **v2_telemetry,
        )
        if v2_enabled and not v2_shadow:
            selected_tool_names = v2_subset
except Exception as exc:
    self.trace.event(turn_id, "router_v2_error", error=str(exc))
```

Verificación: con `GEMMA4_ROUTER_V2_SHADOW=1` el agente sigue usando
el router viejo PERO logea qué hubiera hecho v2. Esto permite blind
test en producción durante Sprint 8c sin riesgo.

Commit: "sprint8a.4: opt-in v2 routing via GEMMA4_ROUTER_V2 + shadow mode"

## 8a.5 — Reporting

Escribí `docs/architecture/sprint_prompts/_sprint8a_log.md`:

- Timestamp.
- ¿Se descargó el modelo OK?
- LOC delta: `git diff --shortstat 99abf5a..HEAD`.
- Tests nuevos pasaron (o skipped por model not installed).
- Path para activar v2 en producción cuando 8c termine.

Adicionalmente actualizar `docs/architecture/08_findings_post_plan.md`
con sección §0.2 mencionando Sprint 8a.

Commit: "sprint8a: write log"

# VERIFICACIONES AL CIERRE

```bash
# 1. Import (NO debe romper aunque el modelo no esté)
python -c "import gemma4_agent; from gemma4_agent.router_v2 import route_v2; print('OK')"

# 2. Tools intactas
python -c "from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"

# 3. Launcher status sigue OK
python -m gemma4_agent.launcher status 2>&1 | head -5

# 4. Tests del router_v2
python -m pytest gemma4_agent/test_router_v2.py -v 2>&1 | tail -20

# 5. Suite completa (no regresiones)
python -m pytest gemma4_agent/ -q --tb=no 2>&1 | tail -3
```

# QUÉ NO HAGAS

- NO reemplaces el router viejo en producción. Es opt-in.
- NO toques planner.py, semantic_router.py.
- NO reescribas las descriptions (Sprint 8b).
- NO hagas blind test todavía (Sprint 8c).
- NO instales bm25s (rank-bm25 ya está).
- NO uses git add -A.

Arrancá.
```

---

## Notas para vos al despertar

1. **El modelo se descarga 1 sola vez** (~113 MB). El agente registra
   en log si falló y degrada con `is_enabled() → False`.
2. **El router viejo sigue siendo el activo.** Para activar v2,
   necesitarías `set GEMMA4_ROUTER_V2=1` en tu shell.
3. **Shadow mode (`GEMMA4_ROUTER_V2_SHADOW=1`)** es lo más útil
   antes de Sprint 8c: el agente sigue funcionando con el router
   viejo pero loguea qué hubiera hecho v2. Te permite comparar
   ambos sin riesgo.
4. **Sprint 8b** sigue después: el router v2 funcionará pero con
   las descriptions cortas actuales. Sprint 8b las enriquece.
5. **Sprint 8c** valida con blind test + decide activar v2 como
   default.

Si el agente no puede descargar el modelo por red, el sprint sigue
siendo válido — el módulo está creado, los tests están escritos
(skipped), y vos lo bajás manual cuando puedas.
