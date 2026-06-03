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
import logging
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_EMBED_DIM = 384

# Automated-test / smoke inputs that must NOT be stored as real experiences
# (they polluted 52% of the DB and degraded recall over long sessions).
_TEST_JUNK_RE = re.compile(
    r"phrase_hook_test|hook_test|__stop__|test_\d{3,}|\becho prueba\b|^echo\b|^\s*prueba\s*$",
    re.IGNORECASE,
)


def _is_test_junk(text: str) -> bool:
    return bool(_TEST_JUNK_RE.search(text or ""))
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
    # Conexión SQLite POR THREAD (threading.local). Una conexión sqlite3 sólo sirve
    # en el thread que la creó (check_same_thread). Hoy ExperienceMemory se accede
    # sólo desde el main thread, pero el patrón de conexión-única-compartida es el
    # MISMO landmine que rompe cuando un 2º thread toca la conexión: registros
    # perdidos silenciosos. Per-thread future-proofs esto sin cambiar el
    # comportamiento single-thread actual. `_disabled` es compartido.
    _local: "threading.local" = field(default_factory=threading.local, repr=False, compare=False)
    _disabled: bool = False

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ wiring

    def _open(self) -> sqlite3.Connection | None:
        if self._disabled:
            return None
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            return conn
        try:
            return self._connect_and_setup()
        except sqlite3.DatabaseError as exc:
            # CORRUPTION RECOVERY. A malformed DB ("database disk image is
            # malformed", "file is not a database") would otherwise crash every
            # record()/recall() — memory "works for a while then breaks forever"
            # after a power loss / sync conflict mid-write. Quarantine the bad
            # file and recreate from scratch ONCE. Memory degrades to "starts
            # fresh" instead of bricking the agent. The quarantined copy is left
            # for forensics; it is never auto-deleted.
            #
            # NOTE: this catches ONLY sqlite3.DatabaseError (corruption). The
            # deliberate fail-loud schema-drift guard (RuntimeError, raised when
            # the ALTERs were swallowed by a lock) is NOT caught here — it must
            # propagate so the user sees the clear remediation message. That is
            # a config/environment problem (antivirus/sync lock), not corruption
            # we can self-heal by recreating.
            logger.warning("experience DB unusable (%s); quarantining %s", exc, self.path)
            if not self._quarantine_corrupt_db():
                self._disabled = True
                return None
            try:
                return self._connect_and_setup()
            except sqlite3.DatabaseError as exc2:
                logger.error("experience DB still unusable after recreate: %s", exc2)
                self._disabled = True
                return None

    def _quarantine_corrupt_db(self) -> bool:
        """Rename the corrupt DB (and its -wal/-shm sidecars) out of the way so
        a fresh one can be created. Returns True on success."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None
        import time as _t
        stamp = _t.strftime("%Y%m%d-%H%M%S")
        ok = False
        for suffix in ("", "-wal", "-shm"):
            src = Path(str(self.path) + suffix)
            if not src.exists():
                continue
            try:
                src.rename(Path(str(self.path) + suffix + f".corrupt-{stamp}"))
                ok = True
            except OSError as exc:
                logger.error("could not quarantine %s: %s", src, exc)
        return ok

    def _connect_and_setup(self) -> sqlite3.Connection | None:
        try:
            import sqlite_vec  # type: ignore[import-not-found]
        except ImportError:
            self._disabled = True
            return None
        # connect + extension load: a non-corruption failure here disables
        # gracefully; a DatabaseError propagates to _open's recovery path.
        try:
            conn = sqlite3.connect(str(self.path))
            conn.row_factory = sqlite3.Row
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
        except sqlite3.DatabaseError:
            raise  # let _open quarantine + recreate
        except Exception:
            self._disabled = True
            return None
        # Stash the handle NOW (before the CREATE/ALTER statements that actually
        # touch the file pages). On a corrupt file those raise DatabaseError, and
        # the recovery path must be able to close THIS connection before renaming
        # the file — otherwise Windows blocks the rename (WinError 32, file in
        # use). _quarantine_corrupt_db cierra la conexión de ESTE thread.
        self._local.conn = conn
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
        # Provenance fields. Existing rows have NULL for these columns;
        # format_recall_for_prompt handles NULL gracefully. Adding columns is
        # idempotent: each ALTER is wrapped in try/except so re-running on a
        # migrated DB is a no-op.
        for col_def in (
            "ALTER TABLE experiences ADD COLUMN outcome_code TEXT",
            "ALTER TABLE experiences ADD COLUMN failure_reason_code TEXT",
            "ALTER TABLE experiences ADD COLUMN args_signature TEXT",
            "ALTER TABLE experiences ADD COLUMN capability_label TEXT",
            "ALTER TABLE experiences ADD COLUMN grounding_flagged INTEGER DEFAULT 0",
        ):
            try:
                conn.execute(col_def)
            except sqlite3.OperationalError:
                pass  # column already exists
        # Fail-loud after the ALTER block. If the
        # `except sqlite3.OperationalError: pass` above ever swallows a
        # *real* failure (e.g. the DB was locked by antivirus / OneDrive
        # sync during cold-start so the ALTER couldn't run AND the
        # column doesn't already exist), subsequent reads will fail
        # silently. Detect that here and raise with a clear remediation
        # message so the user sees the problem immediately instead of
        # a silently-degraded memory.
        cur = conn.execute("PRAGMA table_info(experiences)")
        existing_cols = {row[1] for row in cur.fetchall()}
        expected_cols = {
            "outcome_code",
            "failure_reason_code",
            "args_signature",
            "capability_label",
            "grounding_flagged",
        }
        missing_cols = expected_cols - existing_cols
        if missing_cols:
            raise RuntimeError(
                f"experience.sqlite schema migration failed: missing columns "
                f"{sorted(missing_cols)}. The ALTER TABLE statements were "
                "swallowed by an `except sqlite3.OperationalError`. Common "
                "cause: the SQLite file is locked by another process "
                "(antivirus realtime scan, backup tool, OneDrive / Dropbox / "
                "Google Drive sync). Workaround: move the agent directory "
                "outside synced/scanned paths, or whitelist it in the "
                f"scanner. Path: {self.path}"
            )
        # vec0 virtual table; embedding bound to experiences.rowid (we keep
        # parity via the AUTOINCREMENT id and pass rowid=id when inserting).
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS experience_vec USING vec0("
            f"embedding float[{_EMBED_DIM}])"
        )
        conn.commit()
        self._local.conn = conn
        return conn

    def close(self) -> None:
        # Cierra la conexión de ESTE thread (cada thread tiene la suya).
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

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
        outcome_code: str | None = None,
        failure_reason_code: str | None = None,
        args_signature: dict[str, Any] | None = None,
        capability_label: str | None = None,
    ) -> dict[str, Any]:
        """Append one turn to the store. embed_fn(text) must return a 384-dim list/np.

        Provenance fields (all optional, written when caller knows them):
          - outcome_code: enum-like short tag (PASS_VERIFIED / PASS_UNVERIFIED /
            PARTIAL / FAILED / NEEDS_USER). Distinct from `outcome` prose.
          - failure_reason_code: enum (search_page_only, no_evidence, timeout, ...).
          - args_signature: dict of normalized tool args (e.g. {"provider":"disney_plus"}).
          - capability_label: from the CAPABILITY_LABELS taxonomy.
        """
        if not is_enabled():
            return {"ok": False, "skipped": "memory_disabled"}
        if not user_input.strip():
            return {"ok": False, "skipped": "empty_input"}
        # Anti-degradation: never store automated-test / smoke inputs as real
        # experiences. Without this guard, 52% of the DB was `echo prueba` /
        # `phrase_hook_test_*` junk that crowded out genuine recalls and
        # dragged the model toward noise over a long session.
        if _is_test_junk(user_input):
            return {"ok": False, "skipped": "test_junk"}
        conn = self._open()
        if conn is None:
            return {"ok": False, "skipped": "sqlite_vec_unavailable"}
        try:
            vec = embed_fn(user_input)
            if vec is None:
                return {"ok": False, "skipped": "embed_failed"}
            ts = time.strftime("%Y-%m-%dT%H:%M:%S%z") or time.strftime("%Y-%m-%dT%H:%M:%S")
            args_sig_json = json.dumps(args_signature, ensure_ascii=False)[:2000] \
                if args_signature else None
            cur = conn.execute(
                "INSERT INTO experiences(turn_id, ts, user_input, tools_used, "
                "outcome, mission_status, summary, outcome_code, "
                "failure_reason_code, args_signature, capability_label) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    turn_id, ts, user_input[:8000],
                    json.dumps(tools_used)[:4000],
                    (outcome or "")[:8000], mission_status,
                    (summary or "")[:2000],
                    outcome_code, failure_reason_code,
                    args_sig_json, capability_label,
                ),
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

    def flag_grounding(self, experience_id: int, *, reason: str | None = None) -> dict[str, Any]:
        """Mark an experience row as having a hallucinated reply.

        Called from the async NLI callback. Future RAG hits on this row will
        include `WARNING_past_reply_was_hallucinated` in their hint so the
        LLM is dissuaded from mimicking the (already-stored) prose. Idempotent.
        """
        if not is_enabled():
            return {"ok": False, "skipped": "memory_disabled"}
        conn = self._open()
        if conn is None:
            return {"ok": False, "skipped": "sqlite_vec_unavailable"}
        try:
            conn.execute(
                "UPDATE experiences SET grounding_flagged = 1, "
                "failure_reason_code = COALESCE(failure_reason_code, ?) "
                "WHERE id = ?",
                (reason or "hallucinated_action", int(experience_id)),
            )
            conn.commit()
            return {"ok": True, "id": int(experience_id)}
        except Exception as exc:
            return {"ok": False, "error": f"flag_grounding_failed: {exc}"}

    def flag_grounding_by_turn(self, turn_id: str, *, reason: str | None = None) -> dict[str, Any]:
        """Same as flag_grounding but identifies the row by turn_id.

        Used by the async NLI callback when only the turn_id is in scope
        (the experience row is persisted with a small delay after the turn
        ends; by the time NLI returns ~1200ms later, the row exists).
        """
        if not is_enabled() or not turn_id:
            return {"ok": False, "skipped": "no_op"}
        conn = self._open()
        if conn is None:
            return {"ok": False, "skipped": "sqlite_vec_unavailable"}
        try:
            cur = conn.execute(
                "UPDATE experiences SET grounding_flagged = 1, "
                "failure_reason_code = COALESCE(failure_reason_code, ?) "
                "WHERE turn_id = ?",
                (reason or "hallucinated_action", str(turn_id)),
            )
            conn.commit()
            return {"ok": True, "turn_id": turn_id, "rows_updated": cur.rowcount}
        except Exception as exc:
            return {"ok": False, "error": f"flag_grounding_by_turn_failed: {exc}"}

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
        """Return top-k USEFUL past experiences most similar to `query`.

        `max_distance` is sqlite-vec's L2 distance threshold. With L2-normalized
        embeddings, distance ~= 2*(1-cos). 1.2 corresponds to cos >= 0.4 which
        is a permissive 'kind of similar' bar.

        Anti-degradation: a recalled turn that FAILED while using NO tool
        teaches nothing — it only feeds the model its own past non-action
        ("cierra steam"→FAILED tools=[]). Worse, the experience DB is 34%
        failures, so unfiltered recall steadily injects bad precedent as the
        DB grows — the "it starts failing after a while" symptom. We over-fetch
        and drop those empty failures so the k slots go to experiences that
        actually carry a lesson (a tool that worked, or a tool to AVOID).
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
            # Over-fetch so the post-filter still has k useful rows to return.
            fetch_k = max(1, k) * 5
            cur = conn.execute(
                """SELECT e.id, e.turn_id, e.ts, e.user_input, e.tools_used,
                          e.mission_status, e.summary, e.outcome_code,
                          e.failure_reason_code, e.args_signature,
                          e.capability_label, e.grounding_flagged,
                          v.distance
                   FROM experience_vec v
                   JOIN experiences e ON e.id = v.rowid
                   WHERE v.embedding MATCH ? AND v.k = ?
                   ORDER BY v.distance ASC""",
                (payload, fetch_k),
            )
            results: list[dict[str, Any]] = []
            for row in cur.fetchall():
                if len(results) >= max(1, k):
                    break
                distance = float(row["distance"])
                if distance > max_distance:
                    continue
                tools_used: list[str] = []
                try:
                    tools_used = json.loads(row["tools_used"] or "[]")
                except json.JSONDecodeError:
                    pass
                status = (row["outcome_code"] or row["mission_status"] or "").upper()
                is_failure = "FAIL" in status
                # Drop a failed turn that used no tool: it's pure noise (often
                # ASR junk or a turn the LLM never acted on) and only anchors
                # the model toward inaction. A failed turn WITH a tool is kept
                # — it becomes a "do NOT use this tool here" lesson downstream.
                if is_failure and not tools_used:
                    continue
                args_sig: dict[str, Any] = {}
                if row["args_signature"]:
                    try:
                        args_sig = json.loads(row["args_signature"]) or {}
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
                    # Provenance fields (may be NULL for legacy rows).
                    "outcome_code": row["outcome_code"],
                    "failure_reason_code": row["failure_reason_code"],
                    "args_signature": args_sig,
                    "capability_label": row["capability_label"],
                    "grounding_flagged": bool(row["grounding_flagged"]),
                    "distance": round(distance, 4),
                })
            return results
        except Exception:
            return []

    def recent(self, *, limit: int = 20) -> list[dict[str, Any]]:
        """Return the N most recent experiences ordered by id desc.

        Unlike `recall`, this does NOT require an embedding — it's a plain
        chronological list for the UI/inspection. Returns [] if disabled or
        sqlite-vec is unavailable.
        """
        if not is_enabled():
            return []
        conn = self._open()
        if conn is None:
            return []
        try:
            cur = conn.execute(
                "SELECT id, turn_id, ts, user_input, tools_used, mission_status, summary "
                "FROM experiences ORDER BY id DESC LIMIT ?",
                (max(1, int(limit)),),
            )
            results: list[dict[str, Any]] = []
            for row in cur.fetchall():
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
                    "distance": None,
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
    """Provenance-tagged RAG.

    Render recalled past turns as POLICY HINTS (what worked / what failed),
    NEVER as reply text the LLM could copy. Critical: the past `summary` /
    `outcome` prose is INTENTIONALLY EXCLUDED from the prompt because the
    LLM (especially smaller local models) mimics it as a template when the
    current turn lacks tools.

    Each line tells the LLM "for this kind of input, last time the system
    used these tools with these args, with this outcome code". No verbal
    cue to copy.
    """
    if not recalls:
        return ""
    lines = [
        "# Lecciones de turnos pasados (USAR para decidir tools/args; NO copiar texto)",
        "# Estos NO son ejemplos de cómo responder — son política de tool selection.",
    ]
    for r in recalls:
        tools = ", ".join(r.get("tools_used") or []) or "ninguna"
        # Prefer outcome_code (new) over mission_status (legacy).
        status = r.get("outcome_code") or r.get("mission_status") or "unknown"
        is_failure = "FAIL" in str(status).upper()
        text = (r.get("user_input") or "").replace("\n", " ")[:120]
        args_sig = r.get("args_signature") or {}
        sig_str = ""
        if isinstance(args_sig, dict) and args_sig:
            sig_str = " ".join(f"{k}={v}" for k, v in args_sig.items())
        reason = r.get("failure_reason_code")
        cap = r.get("capability_label")

        if is_failure:
            # Anti-degradation: a past FAILURE must be an AVOID lesson, never
            # a neutral precedent the model might copy. Otherwise recall feeds
            # the model its own past mistakes (e.g. "baja volumen"→audio_device
            # FAILED) and it repeats them — the "starts failing after a while"
            # symptom. Phrase it as a warning.
            parts = [
                f"input similar=\"{text}\"",
                f"EVITAR: el intento pasado con tools=[{tools}] FALLÓ",
                "elige OTRA tool/args para este tipo de pedido",
            ]
            if sig_str:
                parts.append(f"(args que fallaron: {sig_str})")
            if reason:
                parts.append(f"motivo={reason}")
            lines.append(f"- past[d={r['distance']}] ⚠ NEGATIVA: " + " ".join(parts))
        else:
            parts = [
                f"input similar=\"{text}\"",
                f"tools=[{tools}]",
                f"outcome={status}",
            ]
            if cap:
                parts.append(f"capability=\"{cap}\"")
            if sig_str:
                parts.append(f"args[{sig_str}]")
            # A non-FAILED turn can still have been hallucinated (grounding
            # flag): surface both the warning and the reason so the model
            # treats it as a soft-negative, not clean precedent.
            if reason:
                parts.append(f"failure_reason={reason}")
            if r.get("grounding_flagged"):
                parts.append("WARNING_past_reply_was_hallucinated")
            lines.append(f"- past[d={r['distance']}]: " + " ".join(parts))
    return "\n".join(lines)
