"""Telemetria local opt-in (Sprint 11 / Item I4 del informe externo).

Almacena metricas anonimas en SQLite local bajo
`<AgentConfig.state_path>.parent / telemetry.sqlite` para que el dev pueda
detectar problemas en hardware target (6 GB VRAM) sin necesitar feedback
explicito del usuario. Principio rector del informe (Bloque I4):

  - Opt-in default OFF (env var GEMMA4_TELEMETRY=true para encender).
  - Todo en disco local; jamas sale del equipo sin export manual.
  - Cero IDs externos. Cero contenido del prompt. Cero tokens.
  - Rotacion automatica a 30 dias.

Diseño:
  - El modulo expone una clase `TelemetryStore` thread-safe.
  - Singleton `TELEMETRY` al final del archivo. Se conecta al BUS via
    `BUS.add_listener` cuando esta enabled.
  - Cada evento de interes se mapea a una fila en una de las tablas:
      turns, sessions, voice, incidents.

Tablas (definicion en init_schema):
  turns       — un row por request al LLM
  sessions    — un row por arranque del server / proceso
  voice       — un row por utterance (STT + TTS)
  incidents   — OOM, parser_recover, vision_threshold, etc.

Acciones que el dev/usuario puede hacer:
  TelemetryStore.export_json(dst_path) — dump completo a JSON
  TelemetryStore.summarize_last_24h() — resumen para troubleshooting
  TelemetryStore.disable() — deshabilita en runtime

Como NO se enciende automaticamente:
  - El env var es el unico switch.
  - Si el usuario lo activa por error: solo se escribe a disco local;
    no hay efecto secundario fuera del equipo.

NOTA: las metricas exactas que se capturan son intencionalmente conservadoras.
Subset del catalogo Bloque I4 del informe; se puede ampliar sin romper el
schema (campos JSON adicionales).
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)


ENV_FLAG = "GEMMA4_TELEMETRY"
ROTATION_DAYS = 30


# Eventos del BUS que la telemetria escucha. Mapping kind -> tabla.
_KIND_TO_TABLE: dict[str, str] = {
    "vision_threshold_reached": "incidents",
    "boot_stage": "sessions",
    # Otros kinds usuales del bus que NO persistimos por privacidad/ruido:
    #   activity, turn, llm_response, voice_*, etc.
}


def is_enabled() -> bool:
    """Lee env var. Default False."""
    raw = (os.environ.get(ENV_FLAG) or "").strip().lower()
    return raw in {"1", "true", "yes", "on", "enabled"}


def _now_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _now_epoch_ms() -> int:
    return int(time.time() * 1000)


class TelemetryStore:
    """SQLite-backed local-only telemetry."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._lock = threading.RLock()
        self._enabled = False
        self._bus_listener_attached = False
        self._init_done = False

    def _ensure_initialized(self) -> bool:
        """Crea archivo + tablas si hace falta. Idempotente.

        Return True si pudo inicializar; False si fallo IO (en cuyo caso
        deshabilitamos y seguimos sin telemetria — nunca rompemos el agent).
        """
        if self._init_done:
            return True
        with self._lock:
            if self._init_done:
                return True
            try:
                self._db_path.parent.mkdir(parents=True, exist_ok=True)
                with self._connect() as conn:
                    self._init_schema(conn)
                self._init_done = True
                return True
            except (OSError, sqlite3.Error) as exc:
                logger.warning("telemetry init failed: %s; disabling", exc)
                self._enabled = False
                return False

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Conexion con timeout y row_factory consistente.

        SQLite con WAL en local es seguro para multi-thread del agente
        sin tocar locking explicito a nivel Python.
        """
        conn = sqlite3.connect(str(self._db_path), timeout=2.0)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            ts_ms INTEGER NOT NULL,
            kind TEXT NOT NULL,
            profile TEXT,
            payload_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_ts ON sessions(ts_ms);

        CREATE TABLE IF NOT EXISTS turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            ts_ms INTEGER NOT NULL,
            ttft_ms INTEGER,
            tokens_completion INTEGER,
            tokens_prompt_total INTEGER,
            tps REAL,
            cache_n_reused INTEGER,
            vram_peak_mb INTEGER,
            tool_call_count INTEGER,
            tool_call_errors INTEGER,
            payload_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_turns_ts ON turns(ts_ms);

        CREATE TABLE IF NOT EXISTS voice (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            ts_ms INTEGER NOT NULL,
            kind TEXT NOT NULL,  -- 'stt' or 'tts'
            duration_ms INTEGER,
            rtf REAL,
            first_phoneme_ms INTEGER,
            payload_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_voice_ts ON voice(ts_ms);

        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            ts_ms INTEGER NOT NULL,
            kind TEXT NOT NULL,  -- 'oom', 'parser_recover', 'vision_threshold', etc.
            severity TEXT,        -- 'info', 'warn', 'error'
            payload_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_incidents_ts ON incidents(ts_ms);
        CREATE INDEX IF NOT EXISTS idx_incidents_kind ON incidents(kind);
        """)

    # ------------------------------------------------------------------
    # Enable / disable / bus listener
    # ------------------------------------------------------------------

    def enable_if_configured(self) -> bool:
        """Lee env var. Si esta activado y no estabamos, inicializa +
        suscribe al BUS. Idempotente. Devuelve estado final."""
        want = is_enabled()
        if not want:
            self._enabled = False
            return False
        if self._enabled:
            return True
        if not self._ensure_initialized():
            return False
        # Subscribirse al bus de manera best-effort.
        try:
            from .events_bus import BUS
            if not self._bus_listener_attached:
                BUS.add_listener(self._on_bus_event)
                self._bus_listener_attached = True
        except Exception as exc:
            logger.debug("telemetry: bus subscribe skipped: %s", exc)
        self._enabled = True
        logger.info("telemetry: ENABLED (local-only, %s)", self._db_path)
        return True

    def disable(self) -> None:
        """Deshabilita en runtime sin borrar datos historicos."""
        if not self._enabled:
            return
        try:
            from .events_bus import BUS
            BUS.remove_listener(self._on_bus_event)
        except Exception:
            pass
        self._bus_listener_attached = False
        self._enabled = False
        logger.info("telemetry: DISABLED (db file kept at %s)", self._db_path)

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ------------------------------------------------------------------
    # Listener
    # ------------------------------------------------------------------

    def _on_bus_event(self, event: dict[str, Any]) -> None:
        """Listener sincronico. Debe ser rapido y a prueba de excepciones."""
        if not self._enabled:
            return
        kind = str(event.get("kind") or "")
        if not kind:
            return
        # Mapping conservador: solo persistimos algunos kinds.
        if kind == "vision_threshold_reached":
            self.record_incident(
                kind="vision_threshold",
                severity="warn",
                payload={
                    "image_count": event.get("image_count"),
                    "threshold": event.get("threshold"),
                    "issue": event.get("issue"),
                },
            )
        elif kind == "boot_stage":
            stage = str(event.get("stage") or "")
            if stage in {"vision_relaunch", "llama_health", "llama_skipped"}:
                self.record_session(
                    kind=stage,
                    profile=event.get("profile"),
                    payload=event,
                )

    # ------------------------------------------------------------------
    # Recording helpers (publicos)
    # ------------------------------------------------------------------

    def record_turn(
        self,
        *,
        ttft_ms: int | None = None,
        tokens_completion: int | None = None,
        tokens_prompt_total: int | None = None,
        tps: float | None = None,
        cache_n_reused: int | None = None,
        vram_peak_mb: int | None = None,
        tool_call_count: int | None = None,
        tool_call_errors: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if not self._enabled or not self._ensure_initialized():
            return
        payload = json.dumps(extra or {}, ensure_ascii=False)
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    """INSERT INTO turns (ts, ts_ms, ttft_ms, tokens_completion,
                                          tokens_prompt_total, tps, cache_n_reused,
                                          vram_peak_mb, tool_call_count, tool_call_errors,
                                          payload_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (_now_ts(), _now_epoch_ms(), ttft_ms, tokens_completion,
                     tokens_prompt_total, tps, cache_n_reused, vram_peak_mb,
                     tool_call_count, tool_call_errors, payload),
                )
        except sqlite3.Error as exc:
            logger.debug("telemetry record_turn failed: %s", exc)

    def record_session(self, *, kind: str, profile: str | None = None, payload: dict[str, Any] | None = None) -> None:
        if not self._enabled or not self._ensure_initialized():
            return
        payload_json = json.dumps(payload or {}, ensure_ascii=False, default=str)
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT INTO sessions (ts, ts_ms, kind, profile, payload_json) VALUES (?, ?, ?, ?, ?)",
                    (_now_ts(), _now_epoch_ms(), kind, profile, payload_json),
                )
        except sqlite3.Error as exc:
            logger.debug("telemetry record_session failed: %s", exc)

    def record_voice(
        self,
        *,
        kind: str,  # 'stt' or 'tts'
        duration_ms: int | None = None,
        rtf: float | None = None,
        first_phoneme_ms: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if not self._enabled or not self._ensure_initialized():
            return
        payload = json.dumps(extra or {}, ensure_ascii=False)
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    """INSERT INTO voice (ts, ts_ms, kind, duration_ms, rtf,
                                          first_phoneme_ms, payload_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (_now_ts(), _now_epoch_ms(), kind, duration_ms, rtf,
                     first_phoneme_ms, payload),
                )
        except sqlite3.Error as exc:
            logger.debug("telemetry record_voice failed: %s", exc)

    def record_incident(
        self,
        *,
        kind: str,
        severity: str = "warn",
        payload: dict[str, Any] | None = None,
    ) -> None:
        if not self._enabled or not self._ensure_initialized():
            return
        payload_json = json.dumps(payload or {}, ensure_ascii=False, default=str)
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT INTO incidents (ts, ts_ms, kind, severity, payload_json) VALUES (?, ?, ?, ?, ?)",
                    (_now_ts(), _now_epoch_ms(), kind, severity, payload_json),
                )
        except sqlite3.Error as exc:
            logger.debug("telemetry record_incident failed: %s", exc)

    # ------------------------------------------------------------------
    # Reading + housekeeping
    # ------------------------------------------------------------------

    def rotate(self, keep_days: int = ROTATION_DAYS) -> int:
        """Borra rows mas viejas que `keep_days` dias. Devuelve total borrado."""
        if not self._ensure_initialized():
            return 0
        cutoff_ms = _now_epoch_ms() - (keep_days * 24 * 3600 * 1000)
        total = 0
        try:
            with self._lock, self._connect() as conn:
                for table in ("turns", "sessions", "voice", "incidents"):
                    cur = conn.execute(f"DELETE FROM {table} WHERE ts_ms < ?", (cutoff_ms,))
                    total += cur.rowcount
        except sqlite3.Error as exc:
            logger.debug("telemetry rotate failed: %s", exc)
        return total

    def summarize_last_24h(self) -> dict[str, Any]:
        """Resumen util para troubleshooting (ver Bloque I4 del informe)."""
        if not self._ensure_initialized():
            return {"enabled": self._enabled, "error": "init_failed"}
        cutoff_ms = _now_epoch_ms() - (24 * 3600 * 1000)
        out: dict[str, Any] = {"enabled": self._enabled, "window_h": 24}
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) c, AVG(ttft_ms) avg_ttft, MAX(ttft_ms) p_max_ttft, "
                    "AVG(tps) avg_tps, MAX(vram_peak_mb) max_vram "
                    "FROM turns WHERE ts_ms >= ?", (cutoff_ms,)
                ).fetchone()
                out["turns"] = {
                    "count": row["c"], "avg_ttft_ms": row["avg_ttft"],
                    "max_ttft_ms": row["p_max_ttft"], "avg_tps": row["avg_tps"],
                    "max_vram_mb": row["max_vram"],
                }
                incidents = conn.execute(
                    "SELECT kind, COUNT(*) c FROM incidents WHERE ts_ms >= ? GROUP BY kind",
                    (cutoff_ms,),
                ).fetchall()
                out["incidents"] = {r["kind"]: r["c"] for r in incidents}
                voice = conn.execute(
                    "SELECT kind, COUNT(*) c, AVG(rtf) avg_rtf, AVG(first_phoneme_ms) avg_fp "
                    "FROM voice WHERE ts_ms >= ? GROUP BY kind",
                    (cutoff_ms,),
                ).fetchall()
                out["voice"] = {
                    r["kind"]: {"count": r["c"], "avg_rtf": r["avg_rtf"],
                                "avg_first_phoneme_ms": r["avg_fp"]}
                    for r in voice
                }
        except sqlite3.Error as exc:
            out["error"] = f"query_failed: {exc}"
        return out

    def export_json(self, dst_path: Path) -> dict[str, Any]:
        """Dump completo de las 4 tablas a JSON. Util para que el usuario
        comparta voluntariamente con el equipo de soporte. Nunca llama por si
        solo a la red.
        """
        if not self._ensure_initialized():
            return {"error": "init_failed"}
        data: dict[str, Any] = {"exported_at": _now_ts(), "db_path": str(self._db_path)}
        try:
            with self._connect() as conn:
                for table in ("turns", "sessions", "voice", "incidents"):
                    rows = conn.execute(f"SELECT * FROM {table} ORDER BY ts_ms").fetchall()
                    data[table] = [dict(r) for r in rows]
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            dst_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"ok": True, "path": str(dst_path), "totals": {k: len(v) for k, v in data.items() if isinstance(v, list)}}
        except (OSError, sqlite3.Error) as exc:
            return {"error": str(exc)}


# ----------------------------------------------------------------------
# Singleton
# ----------------------------------------------------------------------

def _default_db_path() -> Path:
    """Path por default: junto al state.json del agente.

    Si no se puede determinar, %LOCALAPPDATA%/gemma4_agent/telemetry.sqlite.
    """
    try:
        from .config import AgentConfig
        cfg = AgentConfig.from_env()
        return cfg.state_path.parent / "telemetry.sqlite"
    except Exception:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".gemma4")
        return Path(base) / "gemma4_agent" / "telemetry.sqlite"


TELEMETRY = TelemetryStore(_default_db_path())
