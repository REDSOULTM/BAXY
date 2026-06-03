"""Registro de eventos de comportamiento del usuario para el loop proactivo.

Base del "Jarvis": observar qué hace el usuario (apps que abre/cierra, comandos,
arranques) para que el miner detecte patrones repetidos y el asistente OFREZCA
automatizarlos ("veo que cerrás Discord al prender la PC, ¿te lo automatizo?").

Decisiones de diseño:
  - Tabla SQLite SEPARADA de ExperienceMemory (NO contaminar el log de chat;
    mezclar todo en una sola DB la contamina —se midió hasta 52% de registros
    espurios— y degrada las consultas).
  - WHITELIST estricta de tipos de evento (anti-poison): solo señales estables.
  - Per-usuario (Windows username) → no mezcla perfiles (multi-usuario universal).
  - Append-only, barato (<10 MB, <50 ms); la minería corre APARTE, no acá.
  - Recuperación de corrupción como experience.py (cuarentena + recrear una vez).
  - Todo local en ~/.gemma4/behavior/<user>.db. Sin cloud.

Este módulo SOLO registra y consulta. La detección de patrones vive en
pattern_miner.py; la decisión de ofrecer, en el suggestion queue.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# WHITELIST anti-poison: solo estos tipos de evento se registran. Cualquier otro
# se ignora (evita que basura/tests contaminen el log, como ocurre cuando una DB
# acepta cualquier tipo de evento sin filtrar).
ALLOWED_KINDS = frozenset({
    "boot",         # arranque de la PC / sesión del agente
    "app_open",     # el usuario (o el agente) abrió una app
    "app_close",    # cerró una app
    "cmd",          # comando de voz/texto ejecutado (key = intent/tool)
    "correction",   # el usuario corrigió algo (key = qué)
    # Observador de ambiente: registra METADATA (qué/cuándo), no contenido.
    "media_play",   # algo se reprodujo (key = "artista — título"), via SMTC
    "app_focus",    # app en foco del usuario (key = proc name), via win32 foreground
})

_SCHEMA_VERSION = 1
_DEFAULT_DIR = Path.home() / ".gemma4" / "behavior"


def _current_user() -> str:
    return (os.environ.get("USERNAME") or os.environ.get("USER")
            or "default").strip() or "default"


@dataclass
class BehaviorLog:
    """Log append-only de eventos del usuario. Lazy-loaded, per-usuario."""

    user: str = field(default_factory=_current_user)
    dir_path: Path = _DEFAULT_DIR
    # Conexión SQLite POR THREAD (threading.local). Una conexión sqlite3 sólo puede
    # usarse en el thread que la creó (check_same_thread). El behavior_log lo tocan
    # VARIOS threads —el main (lee el perfil cada turno), el ambient_observer (escribe
    # app_focus/media_play desde su daemon), la reflexión LLM— así que una conexión
    # ÚNICA compartida hacía que las ops del thread "equivocado" fallaran SILENCIOSAS
    # (record→False, events→[]): medido, el observador en daemon perdía registros.
    # WAL (PRAGMA abajo) soporta multi-conexión a la misma DB → una conexión por thread
    # es el patrón correcto. `_disabled` sí es compartido (si la DB está corrupta, lo
    # está para todos).
    _local: "threading.local" = field(default_factory=threading.local, repr=False, compare=False)
    _disabled: bool = False

    @property
    def path(self) -> Path:
        safe = "".join(c for c in self.user if c.isalnum() or c in "._-") or "default"
        return self.dir_path / f"{safe}.db"

    # ------------------------------------------------------------------ wiring
    def _open(self) -> sqlite3.Connection | None:
        if self._disabled:
            return None
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            return conn
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.path), timeout=5.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS behavior_events ("
                " ts INTEGER NOT NULL, user TEXT NOT NULL, kind TEXT NOT NULL,"
                " key TEXT NOT NULL, context TEXT,"
                " PRIMARY KEY (ts, user, kind, key))"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_behavior_kind_key"
                " ON behavior_events(kind, key)")
            conn.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
            conn.execute("INSERT OR IGNORE INTO meta(k,v) VALUES('schema',?)",
                         (str(_SCHEMA_VERSION),))
            conn.commit()
            self._local.conn = conn
            return conn
        except sqlite3.DatabaseError as exc:
            # CORRUPTION RECOVERY (mismo patrón que experience.py): cuarentena +
            # recrear una vez. El log degrada a "empieza de cero", no brickea.
            logger.warning("behavior DB unusable (%s); quarantining %s", exc, self.path)
            try:
                bad = self.path.with_suffix(f".corrupt.{int(time.time())}")
                if self.path.exists():
                    self.path.rename(bad)
            except OSError:
                self._disabled = True
                return None
            try:
                conn = sqlite3.connect(str(self.path), timeout=5.0)
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS behavior_events ("
                    " ts INTEGER NOT NULL, user TEXT NOT NULL, kind TEXT NOT NULL,"
                    " key TEXT NOT NULL, context TEXT,"
                    " PRIMARY KEY (ts, user, kind, key))")
                conn.commit()
                self._local.conn = conn
                return conn
            except sqlite3.DatabaseError:
                self._disabled = True
                return None
        except Exception as exc:
            logger.warning("behavior DB open failed (%s); disabling", exc)
            self._disabled = True
            return None

    # ------------------------------------------------------------------ API
    def record(self, kind: str, key: str, context: dict | None = None) -> bool:
        """Registra un evento. Devuelve True si se guardó. Best-effort: nunca
        lanza (no debe romper el turno). Ignora kinds fuera de la whitelist."""
        if kind not in ALLOWED_KINDS:
            return False
        key = (key or "").strip().lower()
        if not key:
            return False
        conn = self._open()
        if conn is None:
            return False
        try:
            ts = int(time.time() * 1000)
            ctx = json.dumps(context, ensure_ascii=False) if context else None
            conn.execute(
                "INSERT OR IGNORE INTO behavior_events(ts,user,kind,key,context)"
                " VALUES(?,?,?,?,?)", (ts, self.user, kind, key, ctx))
            conn.commit()
            return True
        except sqlite3.Error as exc:
            logger.debug("behavior record failed: %s", exc)
            return False

    def events(self, since_ms: int | None = None, kinds: frozenset | None = None
               ) -> list[dict]:
        """Devuelve eventos (para el miner). since_ms filtra por antigüedad."""
        conn = self._open()
        if conn is None:
            return []
        try:
            q = "SELECT ts,kind,key,context FROM behavior_events WHERE user=?"
            params: list = [self.user]
            if since_ms is not None:
                q += " AND ts>=?"; params.append(int(since_ms))
            q += " ORDER BY ts ASC"
            rows = conn.execute(q, params).fetchall()
        except sqlite3.Error:
            return []
        out = []
        for ts, kind, key, ctx in rows:
            if kinds and kind not in kinds:
                continue
            out.append({"ts": ts, "kind": kind, "key": key,
                        "context": json.loads(ctx) if ctx else {}})
        return out

    def prune(self, older_than_days: int = 60) -> int:
        """Borra eventos viejos (retención). Devuelve filas borradas."""
        conn = self._open()
        if conn is None:
            return 0
        try:
            cutoff = int((time.time() - older_than_days * 86400) * 1000)
            cur = conn.execute("DELETE FROM behavior_events WHERE user=? AND ts<?",
                               (self.user, cutoff))
            conn.commit()
            return cur.rowcount or 0
        except sqlite3.Error:
            return 0

    def close(self) -> None:
        # Cierra la conexión de ESTE thread (cada thread tiene la suya). Best-effort:
        # las conexiones de otros threads se liberan al terminar el proceso/GC.
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
            self._local.conn = None
