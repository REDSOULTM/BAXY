"""Local document knowledge base using SQLite FTS5.

Optionally reranks retrieval results with a local cross-encoder
(default `cross-encoder/ms-marco-MiniLM-L-6-v2`, ~80MB) when called
with `rerank=True`. The cross-encoder is lazy-loaded with the same
retry-on-transient policy as `semantic_router._STATE`. Disable with
env `GEMMA4_KNOWLEDGE_RERANK=false`.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_RERANK_MODEL_DEFAULT = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_RERANK_STATE: dict[str, Any] = {
    "model": None,
    "permanently_disabled": False,
    "last_attempt_ts": 0.0,
    "last_error": "",
    "attempt_count": 0,
}
_RERANK_RETRY_COOLDOWN_S = 120
_RERANK_RETRY_MAX = 3


def _rerank_enabled() -> bool:
    raw = (os.environ.get("GEMMA4_KNOWLEDGE_RERANK") or "").strip().casefold()
    if raw in {"0", "false", "no", "off"}:
        return False
    return True


def _load_reranker() -> Any | None:
    """Lazy-load the cross-encoder model. None on failure (transient or perma)."""
    if _RERANK_STATE["permanently_disabled"]:
        return None
    if _RERANK_STATE["model"] is not None:
        return _RERANK_STATE["model"]
    import time as _time
    now = _time.time()
    if _RERANK_STATE["attempt_count"] > 0 and (now - _RERANK_STATE["last_attempt_ts"]) < _RERANK_RETRY_COOLDOWN_S:
        return None
    if _RERANK_STATE["attempt_count"] >= _RERANK_RETRY_MAX:
        _RERANK_STATE["permanently_disabled"] = True
        return None
    _RERANK_STATE["attempt_count"] += 1
    _RERANK_STATE["last_attempt_ts"] = now
    try:
        from sentence_transformers import CrossEncoder  # type: ignore[import-not-found]
    except ImportError as exc:
        _RERANK_STATE["permanently_disabled"] = True
        _RERANK_STATE["last_error"] = f"ImportError: {exc}"
        return None
    model_name = os.environ.get("GEMMA4_RERANK_MODEL") or _RERANK_MODEL_DEFAULT
    try:
        model = CrossEncoder(model_name)
    except Exception as exc:
        _RERANK_STATE["last_error"] = f"CrossEncoder init failed: {exc}"
        return None
    _RERANK_STATE["model"] = model
    _RERANK_STATE["last_error"] = ""
    return model


def _rerank_rows(query: str, rows: list[dict[str, Any]], limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Re-rank rows by cross-encoder score against `query`. Returns (rows, info)."""
    info: dict[str, Any] = {"used": False, "model": _RERANK_MODEL_DEFAULT}
    if not rows:
        return rows[:limit], info
    if not _rerank_enabled():
        info["skipped"] = "disabled_by_env"
        return rows[:limit], info
    model = _load_reranker()
    if model is None:
        info["skipped"] = "model_unavailable"
        info["last_error"] = _RERANK_STATE["last_error"]
        return rows[:limit], info
    pairs = [(query, str(row.get("snippet") or row.get("title") or "")) for row in rows]
    try:
        scores = model.predict(pairs, show_progress_bar=False)
    except Exception as exc:
        info["skipped"] = f"predict_failed: {exc}"
        return rows[:limit], info
    indexed = list(enumerate(rows))
    indexed.sort(key=lambda pair: -float(scores[pair[0]]))
    reranked: list[dict[str, Any]] = []
    for original_idx, row in indexed[:limit]:
        out = dict(row)
        out["rerank_score"] = round(float(scores[original_idx]), 4)
        reranked.append(out)
    info["used"] = True
    info["candidate_count"] = len(rows)
    return reranked, info


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


@dataclass
class KnowledgeStore:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    title TEXT,
                    created_at TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}'
                )
                """
            )
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
                    doc_id UNINDEXED,
                    chunk_index UNINDEXED,
                    source UNINDEXED,
                    title UNINDEXED,
                    content
                )
                """
            )

    def ingest_text(self, text: str, *, source: str, title: str | None = None, metadata: str = "{}") -> dict[str, Any]:
        text = text.strip()
        if not text:
            return {"ok": False, "error": "empty document"}
        doc_id = hashlib.sha256(f"{source}\0{text}".encode("utf-8", errors="ignore")).hexdigest()[:24]
        chunks = _chunk_text(text)
        with self._connect() as conn:
            conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
            conn.execute(
                "INSERT OR REPLACE INTO documents(id, source, title, created_at, metadata) VALUES (?, ?, ?, ?, ?)",
                (doc_id, source, title or Path(source).name, _now(), metadata),
            )
            conn.executemany(
                "INSERT INTO chunks(doc_id, chunk_index, source, title, content) VALUES (?, ?, ?, ?, ?)",
                [(doc_id, i, source, title or Path(source).name, chunk) for i, chunk in enumerate(chunks)],
            )
        return {"ok": True, "doc_id": doc_id, "source": source, "title": title or Path(source).name, "chunks": len(chunks)}

    def ingest_file(self, path: Path, *, title: str | None = None) -> dict[str, Any]:
        if not path.is_file():
            return {"ok": False, "error": "file not found", "path": str(path)}
        if path.suffix.casefold() not in {".txt", ".md", ".json", ".csv", ".log", ".py", ".ps1", ".yaml", ".yml"}:
            return {"ok": False, "error": "unsupported file type for local text ingest", "path": str(path), "supported": [".txt", ".md", ".json", ".csv", ".log", ".py", ".ps1", ".yaml", ".yml"]}
        text = path.read_text(encoding="utf-8", errors="replace")
        return self.ingest_text(text, source=str(path.resolve()), title=title or path.name)

    def search(self, query: str, *, limit: int = 5, rerank: bool | None = None) -> dict[str, Any]:
        """BM25 + optional cross-encoder rerank.

        rerank=None: auto (uses env GEMMA4_KNOWLEDGE_RERANK, default on).
        rerank=True: force rerank (errors if model unavailable -> falls back).
        rerank=False: BM25 only, skip rerank cost.

        When rerank is active, we retrieve `limit * 4` BM25 candidates (max 40)
        and then re-rank with the cross-encoder, returning the top `limit`.
        """
        query = query.strip()
        if not query:
            return {"ok": False, "error": "missing query"}
        do_rerank = _rerank_enabled() if rerank is None else bool(rerank)
        # Over-fetch for the reranker to have material to work with.
        bm25_limit = max(1, min(40, limit * 4)) if do_rerank else max(1, min(20, limit))
        fts_query = _fts_query(query)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT doc_id, chunk_index, source, title, snippet(chunks, 4, '[', ']', ' ... ', 24) AS snippet,
                       bm25(chunks) AS rank
                FROM chunks
                WHERE chunks MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, bm25_limit),
            ).fetchall()
        bm25_rows = [dict(row) for row in rows]
        if do_rerank and bm25_rows:
            final_rows, rerank_info = _rerank_rows(query, bm25_rows, limit)
        else:
            final_rows = bm25_rows[:limit]
            rerank_info = {"used": False, "skipped": "off_by_caller_or_env" if not do_rerank else "no_candidates"}
        result: dict[str, Any] = {
            "ok": True,
            "query": query,
            "results": final_rows,
            "count": len(final_rows),
            "bm25_candidates": len(bm25_rows),
            "rerank": rerank_info,
        }
        if final_rows:
            result["content_verified"] = True
        else:
            # Búsqueda EXITOSA sin coincidencias en las notas/documentos PERSONALES del
            # usuario. NO es un fallo de verificación: marcar content_verified=False
            # hacía que el pipeline lo tratara como tool-fallido (status
            # needs_verification) y el 4B respondiera "No pude encontrar la
            # información". Pero "¿cuántos segundos hay en un minuto?" es conocimiento
            # GENERAL -> lo debe responder el LLM. MEDIDO en vivo 2026-05-31. Quitamos
            # la señal de no-verificado (NO seteamos content_verified) y guiamos al LLM
            # con una nota para que responda de su propio conocimiento.
            result["completion_status"] = "search_complete_no_matches"
            result["note"] = (
                "Sin coincidencias en las notas/documentos personales del usuario. "
                "Si es una pregunta de conocimiento general, respondela vos "
                "directamente con tu conocimiento; NO digas que no la encontraste."
            )
        return result

    def list_documents(self, *, limit: int = 100) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id, source, title, created_at, metadata FROM documents ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return {"ok": True, "documents": [dict(row) for row in rows], "count": len(rows)}

    def delete(self, doc_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        return {"ok": True, "doc_id": doc_id, "deleted": cur.rowcount}

    def status(self) -> dict[str, Any]:
        with self._connect() as conn:
            docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        return {"ok": True, "path": str(self.path), "documents": docs, "chunks": chunks, "backend": "sqlite_fts5"}


def _chunk_text(text: str, *, max_chars: int = 2200, overlap: int = 250) -> list[str]:
    paragraphs = [part.strip() for part in text.splitlines() if part.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 1 <= max_chars:
            current = f"{current}\n{para}".strip()
            continue
        if current:
            chunks.append(current)
        current = (current[-overlap:] + "\n" + para).strip() if current and overlap else para
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]


def _fts_query(query: str) -> str:
    terms = [term.replace('"', "") for term in query.split() if term.strip()]
    if not terms:
        return query
    return " OR ".join(f'"{term}"' for term in terms[:12])
