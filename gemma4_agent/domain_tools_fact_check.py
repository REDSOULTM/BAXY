"""Fact-Check domain tool — extracted from domain_tools.py (R2 sprint
2026-05-28).

Verificación LÉXICA de claims contra fuentes locales: TF-IDF + cosine
similarity por chunk (pure-Python, sin sklearn). NO llama LLM — devuelve
snippets ranqueados para que el agente escriba el veredicto con evidencia.
Stance heuristic (supports/contradicts/no_evidence) basada en cues de
negación en es/en, no en ML.

Funciones extraídas (3):
  fact_check_tool                (entry: status, check, compare)
  _fact_check_chunks             (sentence-level split + merge)
  _fact_check_rank               (TF-IDF + cosine, detecta negación)

Constants extraídos:
  _NEGATION_CUES_EN / _NEGATION_CUES_ES."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ._shared import _err, _ok
from .tool_result import ToolResult
from .state import AgentState


__all__ = [
    "fact_check_tool",
    "_fact_check_chunks",
    "_fact_check_rank",
    "_NEGATION_CUES_EN",
    "_NEGATION_CUES_ES",
]


# R4 sprint 2026-05-28: handler migrado a ToolResult con .to_dict().
def _ok_tr(**kw):
    return ToolResult.ok_result(**kw).to_dict()


def _err_tr(msg, **kw):
    return ToolResult.err(msg, **kw).to_dict()


def fact_check_tool(args: dict[str, Any], state: AgentState, knowledge_executor=None) -> dict[str, Any]:
    """Compound tool for lexical claim verification against local sources.

    Actions:
      - status
      - check(claim, sources=[paths|ids|texts]?, use_knowledge=true)
      - compare(claim, text)
    Strategy: TF-IDF + cosine similarity per-chunk against the claim. We do
    NOT call an LLM here; we return ranked snippets so Gemma can write the
    final verdict from real evidence. Stance heuristic (supports/contradicts/
    no_evidence) is rule-based on negation cues, not an ML model.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok_tr(
            backend="tfidf_cosine + bm25_fts5",
            note="Lexical only; no LLM call inside the tool. The agent itself writes the verdict from ranked snippets.",
        )
    if action == "compare":
        claim = str(args.get("claim") or "").strip()
        text = str(args.get("text") or "").strip()
        if not claim or not text:
            return _err_tr("compare requires claim and text")
        chunks = _fact_check_chunks(text)
        ranked = _fact_check_rank(claim, [{"source": "<inline>", "title": "inline", "text": ch} for ch in chunks])
        return _ok_tr(claim=claim, matches=ranked[:10], evaluated=len(chunks))
    if action != "check":
        return _err_tr(
            "unknown fact_check action", action=action,
            valid_actions=["status", "check", "compare"],
            status="needs_user",
        )

    claim = str(args.get("claim") or "").strip()
    if not claim:
        return _err_tr("missing claim")
    raw_sources = args.get("sources")
    sources_arg: list[Any] = raw_sources if isinstance(raw_sources, list) else []
    use_knowledge = bool(args.get("use_knowledge", True))
    limit = int(args.get("limit", 10))

    candidates: list[dict[str, Any]] = []

    # 1. Explicit sources: each entry can be a path, a resource id (res_*), or a text body.
    for entry in sources_arg:
        text = ""
        label = "<inline>"
        path = None
        if isinstance(entry, dict):
            text = str(entry.get("text") or "")
            label = str(entry.get("source") or entry.get("title") or "inline")
            path = entry.get("path")
        elif isinstance(entry, str):
            stripped = entry.strip()
            if stripped.startswith("res_"):
                resource = state._load().get("resources", {}).get(stripped)
                if resource:
                    meta = resource.get("metadata") or {}
                    text = str(meta.get("text") or "")
                    label = str(resource.get("label") or stripped)
                    if not text and meta.get("path") and Path(str(meta["path"])).is_file():
                        text = Path(str(meta["path"])).read_text(encoding="utf-8", errors="replace")[:50000]
            elif Path(stripped).exists() and Path(stripped).is_file():
                text = Path(stripped).read_text(encoding="utf-8", errors="replace")[:50000]
                label = Path(stripped).name
                path = stripped
            else:
                text = stripped
                label = "inline"
        if not text:
            continue
        for ch in _fact_check_chunks(text):
            candidates.append({"source": label, "title": label, "text": ch, "path": path})

    # 2. Local RAG: top-k from knowledge if requested.
    if use_knowledge and knowledge_executor:
        kn = knowledge_executor("knowledge", {"action": "search", "query": claim, "limit": limit})
        for row in kn.get("results", []) if isinstance(kn, dict) else []:
            snip = str(row.get("snippet") or "").replace("[", "").replace("]", "")
            if snip:
                candidates.append({"source": row.get("source") or row.get("title") or "knowledge", "title": row.get("title"), "text": snip})

    if not candidates:
        return _ok_tr(
            claim=claim,
            verdict="no_evidence",
            evaluated=0,
            note="No sources provided and knowledge search returned nothing. Pass sources=[...] or ingest documents first via knowledge(ingest) / document(ingest_to_knowledge).",
            matches=[],
        )

    ranked = _fact_check_rank(claim, candidates)
    top = ranked[:limit]
    # Verdict heuristic:
    # - If best score >= 0.35 and no negation context, lean supports.
    # - If best score >= 0.35 and negation/contradiction cue near match, lean contradicts.
    # - Else no_evidence.
    if not top:
        verdict = "no_evidence"
    else:
        best = top[0]
        if best["score"] >= 0.35:
            verdict = "contradicts" if best.get("negation_signal") else "supports"
        elif best["score"] >= 0.18:
            verdict = "weakly_supports"
        else:
            verdict = "no_evidence"
    return _ok_tr(
        claim=claim,
        verdict=verdict,
        evaluated=len(candidates),
        matches=top,
        note="Verdict is a lexical heuristic; treat as one signal, not ground truth. Inspect matches and write a final answer with citations.",
    )


_NEGATION_CUES_EN = {"not", "no", "never", "false", "untrue", "wrong", "incorrect", "deny", "denies", "denied", "refute", "refuted"}
_NEGATION_CUES_ES = {"no", "nunca", "falso", "falsa", "incorrecto", "incorrecta", "niega", "niegan", "negado", "desmentido", "rechaza", "rechazado"}


def _fact_check_chunks(text: str) -> list[str]:
    """Sentence-level chunks (rough split on . ! ? newlines, then merge short)."""
    raw = re.split(r"(?<=[\.!?])\s+|\n{2,}", text)
    chunks: list[str] = []
    buf = ""
    for sent in raw:
        sent = sent.strip()
        if not sent:
            continue
        if len(buf) + len(sent) < 600:
            buf = f"{buf} {sent}".strip()
        else:
            if buf:
                chunks.append(buf)
            buf = sent
    if buf:
        chunks.append(buf)
    return chunks


def _fact_check_rank(claim: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """TF-IDF + cosine similarity. Pure-Python, no sklearn dependency."""
    import math
    from collections import Counter
    def tokenize(text: str) -> list[str]:
        return re.findall(r"[\wÀ-ſ]{2,}", text.casefold())
    claim_tokens = tokenize(claim)
    if not claim_tokens or not candidates:
        return []
    # Build vocabulary and DF over candidates + claim.
    docs = [tokenize(c["text"]) for c in candidates]
    df: Counter[str] = Counter()
    for doc in docs + [claim_tokens]:
        for term in set(doc):
            df[term] += 1
    n_docs = len(docs) + 1

    def tfidf_vector(tokens: list[str]) -> dict[str, float]:
        if not tokens:
            return {}
        tf = Counter(tokens)
        total = len(tokens)
        return {t: (count / total) * math.log((n_docs + 1) / (df.get(t, 1) + 1) + 1.0) for t, count in tf.items()}

    def cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        # Iterate over the smaller dict for the dot product.
        small, large = (a, b) if len(a) <= len(b) else (b, a)
        dot = sum(v * large.get(k, 0.0) for k, v in small.items())
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    claim_vec = tfidf_vector(claim_tokens)
    claim_token_set = set(claim_tokens)
    negation_cues = _NEGATION_CUES_EN | _NEGATION_CUES_ES

    ranked: list[dict[str, Any]] = []
    for cand, tokens in zip(candidates, docs):
        score = cosine(claim_vec, tfidf_vector(tokens))
        # Detect negation cues within a 6-token window of any claim term in the chunk.
        negation_signal = False
        for i, tok in enumerate(tokens):
            if tok not in claim_token_set:
                continue
            window = tokens[max(0, i - 6): i + 7]
            if any(w in negation_cues for w in window):
                negation_signal = True
                break
        ranked.append({
            "source": cand.get("source"),
            "title": cand.get("title"),
            "path": cand.get("path"),
            "score": round(float(score), 4),
            "negation_signal": negation_signal,
            "snippet": cand["text"][:400],
        })
    ranked.sort(key=lambda r: -r["score"])
    return ranked
