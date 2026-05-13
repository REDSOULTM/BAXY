"""Semantic memory of past agent turns.

Inspired by OS-Copilot's experience replay and Agent-S's procedural memory:
every completed turn gets embedded and stored in a local SQLite database with
sqlite-vec. On a new user request, the agent looks up the top-K most similar
past turns and injects a short hint into the system prompt so it can reuse
working tool sequences from history.

Storage: <state_dir>/experience.sqlite
- experiences: id, turn_id, ts, user_input, tools_used (JSON), outcome,
  mission_status, summary
- experience_vec: virtual table USING vec0(embedding float[384])

Embeddings come from the same multilingual-MiniLM model already loaded for
semantic_router. The dimension is fixed at 384 (the model's output dim).

Disable via env GEMMA4_EXPERIENCE_MEMORY=false.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_EMBED_DIM = 384
# Defaults for housekeeping. Override via env GEMMA4_EXPERIENCE_MAX_RECORDS /
# GEMMA4_EXPERIENCE_MAX_AGE_DAYS. Auto-prune fires every N inserts (cheap).
_DEFAULT_MAX_RECORDS = 5000
_DEFAULT_MAX_AGE_DAYS = 180
_AUTO_PRUNE_EVERY = 50


def is_enabled() -> bool:
    raw = (os.environ.get("GEMMA4_EXPERIENCE_MEMORY") or "").strip().casefold()
    if raw in {"0", "false", "no", "off"}:
        return False
    return True


def _max_records() -> int:
    raw = (os.environ.get("GEMMA4_EXPERIENCE_MAX_RECORDS") or "").strip()
    try:
        n = int(raw)
        return n if n > 0 else _DEFAULT_MAX_RECORDS
    except ValueError:
        return _DEFAULT_MAX_RECORDS


def _max_age_days() -> int:
    raw = (os.environ.get("GEMMA4_EXPERIENCE_MAX_AGE_DAYS") or "").strip()
    try:
        n = int(raw)
        return n if n > 0 else _DEFAULT_MAX_AGE_DAYS
    except ValueError:
        return _DEFAULT_MAX_AGE_DAYS


@dataclass
class ExperienceMemory:
    """Append-only semantic log of past turns. Lazy-loads sqlite-vec."""

    path: Path
    _conn: sqlite3.Connection | None = None
    _disabled: bool = False

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ wiring

    def _open(self) -> sqlite3.Connection | None:
        if self._disabled:
            return None
        if self._conn is not None:
            return self._conn
        try:
            import sqlite_vec  # type: ignore[import-not-found]
        except ImportError:
            self._disabled = True
            return None
        try:
            conn = sqlite3.connect(str(self.path))
            conn.row_factory = sqlite3.Row
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
        except Exception:
            self._disabled = True
            return None
        conn.execute(
            """CREATE TABLE IF NOT EXISTS experiences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turn_id TEXT NOT NULL,
                ts TEXT NOT NULL,
                user_input TEXT NOT NULL,
                tools_used TEXT NOT NULL DEFAULT '[]',
                outcome TEXT,
                mission_status TEXT,
                summary TEXT
            )"""
        )
        # vec0 virtual table; embedding bound to experiences.rowid (we keep
        # parity via the AUTOINCREMENT id and pass rowid=id when inserting).
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS experience_vec USING vec0("
            f"embedding float[{_EMBED_DIM}])"
        )
        conn.commit()
        self._conn = conn
        return conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ----------------------------------------------------------- public writes

    def record(
        self,
        *,
        turn_id: str,
        user_input: str,
        tools_used: list[str],
        outcome: str,
        mission_status: str | None,
        summary: str | None,
        embed_fn: Any,
    ) -> dict[str, Any]:
        """Append one turn to the store. embed_fn(text) must return a 384-dim list/np."""
        if not is_enabled():
            return {"ok": False, "skipped": "memory_disabled"}
        if not user_input.strip():
            return {"ok": False, "skipped": "empty_input"}
        conn = self._open()
        if conn is None:
            return {"ok": False, "skipped": "sqlite_vec_unavailable"}
        try:
            vec = embed_fn(user_input)
            if vec is None:
                return {"ok": False, "skipped": "embed_failed"}
            ts = time.strftime("%Y-%m-%dT%H:%M:%S%z") or time.strftime("%Y-%m-%dT%H:%M:%S")
            cur = conn.execute(
                "INSERT INTO experiences(turn_id, ts, user_input, tools_used, outcome, mission_status, summary) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (turn_id, ts, user_input[:8000], json.dumps(tools_used)[:4000], (outcome or "")[:8000], mission_status, (summary or "")[:2000]),
            )
            rowid = cur.lastrowid
            payload = _vec_blob(vec)
            conn.execute("INSERT INTO experience_vec(rowid, embedding) VALUES (?, ?)", (rowid, payload))
            conn.commit()
            pruned = None
            # Cheap auto-prune: every N inserts check if we're over budget.
            if rowid and rowid % _AUTO_PRUNE_EVERY == 0:
                pruned = self.prune()
            return {"ok": True, "id": rowid, "turn_id": turn_id, "pruned": pruned}
        except Exception as exc:
            return {"ok": False, "error": f"record_failed: {exc}"}

    def prune(self, *, max_records: int | None = None, max_age_days: int | None = None) -> dict[str, Any]:
        """Drop experiences over budget. Returns counts. Safe to call any time.

        - max_records: keeps the N most recent rows. Defaults from env.
        - max_age_days: drops rows older than this. Defaults from env.
        Both are applied; whichever drops more wins.
        """
        conn = self._open()
        if conn is None:
            return {"ok": False, "skipped": "sqlite_vec_unavailable"}
        keep_n = int(max_records if max_records is not None else _max_records())
        keep_days = int(max_age_days if max_age_days is not None else _max_age_days())
        try:
            total = conn.execute("SELECT COUNT(*) FROM experiences").fetchone()[0]
            cutoff_ts = None
            age_dropped = 0
            if keep_days > 0:
                cutoff_struct = time.gmtime(time.time() - keep_days * 86400)
                cutoff_ts = time.strftime("%Y-%m-%dT%H:%M:%S", cutoff_struct)
                # Find ids to drop (sqlite-vec virtual tables can't DELETE via
                # subqueries on a different table, so do it in two passes).
                ids_age = [row[0] for row in conn.execute(
                    "SELECT id FROM experiences WHERE ts < ?", (cutoff_ts,)
                ).fetchall()]
                if ids_age:
                    placeholders = ",".join("?" * len(ids_age))
                    conn.execute(f"DELETE FROM experiences WHERE id IN ({placeholders})", ids_age)
                    conn.execute(f"DELETE FROM experience_vec WHERE rowid IN ({placeholders})", ids_age)
                    age_dropped = len(ids_age)
            size_dropped = 0
            if keep_n > 0:
                # Drop oldest beyond the budget.
                remaining = conn.execute("SELECT COUNT(*) FROM experiences").fetchone()[0]
                if remaining > keep_n:
                    excess = remaining - keep_n
                    ids_excess = [row[0] for row in conn.execute(
                        "SELECT id FROM experiences ORDER BY id ASC LIMIT ?", (excess,)
                    ).fetchall()]
                    if ids_excess:
                        placeholders = ",".join("?" * len(ids_excess))
                        conn.execute(f"DELETE FROM experiences WHERE id IN ({placeholders})", ids_excess)
                        conn.execute(f"DELETE FROM experience_vec WHERE rowid IN ({placeholders})", ids_excess)
                        size_dropped = len(ids_excess)
            conn.commit()
            final = conn.execute("SELECT COUNT(*) FROM experiences").fetchone()[0]
            return {
                "ok": True,
                "before": int(total),
                "after": int(final),
                "age_dropped": int(age_dropped),
                "size_dropped": int(size_dropped),
                "max_records": keep_n,
                "max_age_days": keep_days,
                "cutoff_ts": cutoff_ts,
            }
        except Exception as exc:
            return {"ok": False, "error": f"prune_failed: {exc}"}

    # ------------------------------------------------------------ public reads

    def recall(self, query: str, *, embed_fn: Any, k: int = 3, max_distance: float = 1.2) -> list[dict[str, Any]]:
        """Return top-k past experiences most similar to `query`.

        `max_distance` is sqlite-vec's L2 distance threshold. With L2-normalized
        embeddings, distance ~= 2*(1-cos). 1.2 corresponds to cos >= 0.4 which
        is a permissive 'kind of similar' bar.
        """
        if not is_enabled():
            return []
        if not query.strip():
            return []
        conn = self._open()
        if conn is None:
            return []
        try:
            vec = embed_fn(query)
            if vec is None:
                return []
            payload = _vec_blob(vec)
            cur = conn.execute(
                """SELECT e.id, e.turn_id, e.ts, e.user_input, e.tools_used, e.mission_status, e.summary,
                          v.distance
                   FROM experience_vec v
                   JOIN experiences e ON e.id = v.rowid
                   WHERE v.embedding MATCH ? AND v.k = ?
                   ORDER BY v.distance ASC""",
                (payload, max(1, k)),
            )
            results: list[dict[str, Any]] = []
            for row in cur.fetchall():
                distance = float(row["distance"])
                if distance > max_distance:
                    continue
                tools_used: list[str] = []
                try:
                    tools_used = json.loads(row["tools_used"] or "[]")
                except json.JSONDecodeError:
                    pass
                results.append({
                    "id": row["id"],
                    "turn_id": row["turn_id"],
                    "ts": row["ts"],
                    "user_input": row["user_input"],
                    "tools_used": tools_used,
                    "mission_status": row["mission_status"],
                    "summary": row["summary"],
                    "distance": round(distance, 4),
                })
            return results
        except Exception:
            return []

    def stats(self) -> dict[str, Any]:
        conn = self._open()
        if conn is None:
            return {"available": False, "disabled": self._disabled}
        try:
            count = conn.execute("SELECT COUNT(*) FROM experiences").fetchone()[0]
            last = conn.execute("SELECT ts FROM experiences ORDER BY id DESC LIMIT 1").fetchone()
            return {
                "available": True,
                "path": str(self.path),
                "experience_count": int(count),
                "last_recorded": last["ts"] if last else None,
                "dim": _EMBED_DIM,
                "max_records": _max_records(),
                "max_age_days": _max_age_days(),
                "auto_prune_every": _AUTO_PRUNE_EVERY,
            }
        except Exception as exc:
            return {"available": False, "error": str(exc)}


def _vec_blob(vec: Any) -> Any:
    """Convert an embedding (list or np.ndarray) into the bytes layout sqlite-vec expects."""
    import struct
    if hasattr(vec, "tolist"):
        vec = vec.tolist()
    if len(vec) != _EMBED_DIM:
        raise ValueError(f"embedding dim {len(vec)} != expected {_EMBED_DIM}")
    return struct.pack(f"{_EMBED_DIM}f", *(float(x) for x in vec))


def format_recall_for_prompt(recalls: list[dict[str, Any]]) -> str:
    """Render recalls into a compact bullet list for the system prompt."""
    if not recalls:
        return ""
    lines = ["# Similar past turns (use as hints; not authoritative)"]
    for r in recalls:
        tools = ", ".join(r.get("tools_used") or []) or "no tools"
        status = r.get("mission_status") or "unknown"
        text = (r.get("user_input") or "").replace("\n", " ")[:160]
        summary = (r.get("summary") or "").replace("\n", " ")[:160]
        lines.append(f"- past[{r['distance']}]: \"{text}\" -> tools=[{tools}] status={status}")
        if summary:
            lines.append(f"   summary: {summary}")
    return "\n".join(lines)
