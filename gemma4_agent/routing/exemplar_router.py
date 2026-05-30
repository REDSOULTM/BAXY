"""Semantic exemplar memory for router decisions.

This layer is a data artifact, not a phrase-rule layer: it loads embeddings for
curated historical router examples and uses cosine similarity to recover a
high-confidence label. It is intentionally conservative so novel wording still
falls through to the calibrated heads in ``planner.py``.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PATH = Path(__file__).resolve().parent.parent / "data" / "router_exemplars.npz"  # reorg 2026-05-28
_TOP_K = int(os.environ.get("GEMMA4_EXEMPLAR_TOP_K", "5"))
_MIN_SCORE = float(os.environ.get("GEMMA4_EXEMPLAR_MIN_SCORE", "0.92"))
_CONFLICT_SCORE = float(os.environ.get("GEMMA4_EXEMPLAR_CONFLICT_SCORE", "0.975"))
# Margen relativo que el voto-ABSTENCIÓN debe superar al mejor voto-TOOL para
# que el exemplar abstenga (S3c, 2026-05-30). CAUSA RAÍZ medida: un imperativo
# limpio ("abre el navegador") tiene como vecino-top una PREGUNTA reflexiva
# casi idéntica en el espacio de embeddings ("me abrí el navegador?" label []),
# cuyo voto-abstención (score² ~0.896) vencía por 0.005 a los 4 vecinos-comando
# ("abre el navegador ese" [app,web], ~0.891). El exemplar abstenía y
# cortocircuitaba TODO el resto del planner -> subset vacío en un comando obvio.
# Exigir que la abstención GANE por margen (no por un pelo) evita que un único
# vecino-pregunta envenene 4 vecinos-comando. NO afecta la charla genuina, donde
# la abstención domina por mucho ("gracias", "holas"). Medido global antes de
# fijar el default.
_ABSTAIN_MARGIN = float(os.environ.get("GEMMA4_EXEMPLAR_ABSTAIN_MARGIN", "0.05"))
# Banda bajo el mejor vecino dentro de la cual un vecino-TOOL "casi-cruza" el
# MIN_SCORE (S3c-bis, 2026-05-30). CAUSA RAÍZ medida tras el reentreno FT 3ep:
# cuando el ÚNICO vecino sobre MIN_SCORE es no-tool (una pregunta reflexiva casi
# idéntica, p.ej. "recuerdas todo de mí?" label []) y el vecino-tool correcto
# ("qué cosas recuerdas sobre Carter?"→memory) cae JUSTO debajo del corte (0.79
# vs 0.92), el voto sale vacío y el exemplar abstenía, cortocircuitando el head
# calibrado (que dice should_abstain=False) y el encoder (memory 0.739). El fix
# S3c (margen) sólo protege cuando AMBOS vecinos cruzan el umbral. Acá NO cruzan,
# así que generalizamos: si hay un vecino-tool fuerte dentro de esta banda bajo el
# mejor no-tool, el exemplar DEFIERE (return None) al head en vez de silenciar.
# La charla pura no tiene vecino-tool cercano → sigue abstaniéndose. NO baja el
# MIN_SCORE global (no agrega ruido); sólo evita el cortocircuito ambiguo.
_ABSTAIN_NEAR_BAND = float(os.environ.get("GEMMA4_EXEMPLAR_ABSTAIN_NEAR_BAND", "0.15"))


@dataclass(frozen=True)
class ExemplarMatch:
    tools: tuple[str, ...]
    score: float
    source: str

    @property
    def abstain(self) -> bool:
        return not self.tools


@dataclass
class _Index:
    queries: list[str]
    labels: list[tuple[str, ...]]
    embeddings: Any
    exact: dict[str, tuple[str, ...]]


_INDEX: _Index | None = None
_TRIED = False
_LOCK = threading.Lock()


def is_enabled() -> bool:
    raw = (os.environ.get("GEMMA4_EXEMPLAR_ROUTER") or "").strip().casefold()
    return raw not in {"0", "false", "no", "off"}


def match(text: str) -> ExemplarMatch | None:
    """Return a high-confidence historical semantic match, if any."""
    if not is_enabled() or not text.strip():
        return None
    idx = _load()
    if idx is None:
        return None

    exact = idx.exact.get(text)
    if exact is not None:
        return ExemplarMatch(tools=exact, score=1.0, source="exact")

    try:
        import numpy as np
        from .semantic_router import embed

        qv = embed(text)
        if qv is None:
            return None
        scores = idx.embeddings @ np.asarray(qv, dtype=np.float32)
        if scores.size == 0:
            return None
        top = np.argsort(-scores)[: max(1, _TOP_K)]
        best_i = int(top[0])
        best_score = float(scores[best_i])
        if best_score < _MIN_SCORE:
            return None

        # Weighted vote across near-tied exemplars. This keeps the layer
        # semantic instead of depending on a single neighbor's annotation.
        votes: dict[str, float] = {}
        abstain_vote = 0.0
        for raw_i in top:
            i = int(raw_i)
            score = float(scores[i])
            if score < _MIN_SCORE:
                continue
            weight = score * score
            tools = idx.labels[i]
            if not tools:
                abstain_vote += weight
            else:
                for tool in tools:
                    votes[tool] = votes.get(tool, 0.0) + weight
        if not votes:
            # Sólo vecinos no-tool cruzaron MIN_SCORE. Si un vecino-TOOL fuerte
            # quedó JUSTO debajo del corte (dentro de _ABSTAIN_NEAR_BAND del mejor
            # no-tool), la abstención es AMBIGUA: deferir al abstain head calibrado
            # en vez de cortocircuitar. La charla pura no tiene vecino-tool cercano
            # y sigue abstaniéndose. (S3c-bis: generaliza el margen al caso en que
            # el vecino-tool no llega a votar por caer bajo el umbral.)
            near_tool = any(
                idx.labels[int(i)]
                and float(scores[int(i)]) >= best_score - _ABSTAIN_NEAR_BAND
                for i in top
            )
            if near_tool:
                return None
            return ExemplarMatch(tools=(), score=best_score, source="semantic")
        # Abstener SOLO si el voto-abstención SUPERA al mejor voto-tool por un
        # margen (no por un empate ínfimo): un único vecino-pregunta no debe
        # silenciar un imperativo respaldado por varios vecinos-comando. La
        # charla real abstiene por mucho y cruza el margen sin problema.
        if abstain_vote > max(votes.values(), default=0.0) * (1.0 + _ABSTAIN_MARGIN):
            return ExemplarMatch(tools=(), score=best_score, source="semantic")
        ranked = tuple(t for t, _ in sorted(votes.items(), key=lambda kv: -kv[1])[:4])
        return ExemplarMatch(tools=ranked, score=best_score, source="semantic")
    except Exception:
        return None


def has_tool_conflict(text: str) -> bool:
    """True when a no-tool exact exemplar has a near-identical tool neighbor."""
    if not is_enabled() or not text.strip():
        return False
    idx = _load()
    if idx is None:
        return False
    try:
        import numpy as np
        from .semantic_router import embed

        qv = embed(text)
        if qv is None:
            return False
        scores = idx.embeddings @ np.asarray(qv, dtype=np.float32)
        if scores.size == 0:
            return False
        top = np.argsort(-scores)[: max(8, _TOP_K)]
        for raw_i in top:
            i = int(raw_i)
            if idx.queries[i] == text:
                continue
            if float(scores[i]) < _CONFLICT_SCORE:
                continue
            if idx.labels[i]:
                return True
        return False
    except Exception:
        return False


def _load() -> _Index | None:
    global _INDEX, _TRIED
    if _INDEX is not None:
        return _INDEX
    if _TRIED:
        return None
    with _LOCK:
        if _INDEX is not None:
            return _INDEX
        if _TRIED:
            return None
        _TRIED = True
        if not _PATH.exists():
            return None
        try:
            import numpy as np

            data = np.load(_PATH, allow_pickle=False)
            queries = [str(x) for x in data["queries"].tolist()]
            labels = [tuple(json.loads(str(x))) for x in data["labels"].tolist()]
            embeddings = np.asarray(data["embeddings"], dtype=np.float32)
            exact: dict[str, tuple[str, ...]] = {}
            for q, tools in zip(queries, labels):
                # Exact historical examples are treated as reviewed labels.
                # There are no exact-string conflicts in the curated corpus; if
                # one appears later, unioning preserves recall without code edits.
                if q in exact:
                    exact[q] = tuple(dict.fromkeys([*exact[q], *tools]))
                else:
                    exact[q] = tools
            _INDEX = _Index(
                queries=queries,
                labels=labels,
                embeddings=embeddings,
                exact=exact,
            )
            return _INDEX
        except Exception:
            _INDEX = None
            return None
