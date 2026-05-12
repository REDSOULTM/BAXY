"""Local document knowledge base using SQLite FTS5."""

from __future__ import annotations

import hashlib
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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

    def search(self, query: str, *, limit: int = 5) -> dict[str, Any]:
        query = query.strip()
        if not query:
            return {"ok": False, "error": "missing query"}
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
                (fts_query, max(1, min(20, limit))),
            ).fetchall()
        return {
            "ok": True,
            "query": query,
            "results": [dict(row) for row in rows],
            "count": len(rows),
            "content_verified": bool(rows),
        }

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
