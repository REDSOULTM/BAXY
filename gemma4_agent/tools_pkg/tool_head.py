"""Per-tool logit head — the research's anti-bloat subset selector.

The four research reports' recommended architecture: a multi-label router head
emitting a per-tool logit with a PER-TOOL CALIBRATED THRESHOLD. The subset is
"tools whose logit clears their own bar" — not top-k, not a band. This is what
structurally prevents bloat: a flat-distribution query ("pausa") activates only
the tool(s) that individually clear threshold ({media}), not the whole cluster.

Runtime: one query embedding (already computed by semantic_router) · a 65×384
matmul · per-tool sigmoid · per-tool threshold compare. Sub-millisecond, numpy
only, no sklearn. Weights in versioned JSON (scripts/train_tool_head.py).

Returns the tools that fire, sorted by margin over their threshold (most
confident first), so the caller can keep the strongest and cap if needed.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PATH = Path(__file__).resolve().parent.parent / "data" / "tool_head.json"  # reorg 2026-05-28


@dataclass
class ToolHead:
    tools: list[str]
    weights: Any           # np.ndarray [N, D]
    biases: Any            # np.ndarray [N]
    thresholds: Any        # np.ndarray [N]

    def fire(self, embedding: Any) -> list[tuple[str, float]]:
        """Return (tool, margin) for every tool whose calibrated probability
        clears its threshold, strongest margin first. margin = p - threshold."""
        import numpy as np
        v = np.asarray(embedding, dtype=np.float32)
        z = self.weights @ v + self.biases
        p = 1.0 / (1.0 + np.exp(-z))
        out: list[tuple[str, float]] = []
        for i, tool in enumerate(self.tools):
            thr = float(self.thresholds[i])
            if thr <= 1.0 and p[i] >= thr:
                out.append((tool, float(p[i] - thr)))
        out.sort(key=lambda x: -x[1])
        return out


_HEAD: ToolHead | None = None
_TRIED = False
# Serializes load(): warmup thread + first turn both call it. Double-checked
# locking keeps _HEAD/_TRIED consistent and avoids a double JSON parse.
import threading as _threading
_LOAD_LOCK = _threading.Lock()


def is_enabled() -> bool:
    raw = (os.environ.get("GEMMA4_TOOL_HEAD") or "").strip().casefold()
    return raw not in {"0", "false", "no", "off"}


def load() -> ToolHead | None:
    global _HEAD, _TRIED
    if _HEAD is not None:
        return _HEAD
    if _TRIED:
        return None
    with _LOAD_LOCK:
        if _HEAD is not None:
            return _HEAD
        if _TRIED:
            return None
        return _load_locked()


def _load_locked() -> ToolHead | None:
    global _HEAD, _TRIED
    _TRIED = True
    if not _PATH.exists():
        return None
    try:
        import numpy as np
        d = json.loads(_PATH.read_text(encoding="utf-8"))
        _HEAD = ToolHead(
            tools=list(d["tools"]),
            weights=np.asarray(d["weights"], dtype=np.float32),
            biases=np.asarray(d["biases"], dtype=np.float32),
            thresholds=np.asarray(d["thresholds"], dtype=np.float32),
        )
        return _HEAD
    except Exception:
        return None
