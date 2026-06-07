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
            # CRÍTICO (auditoría 2026-06-07): en Windows hay que CERRAR el handle
            # SQLite fallido ANTES de renombrar — si no, el archivo queda bloqueado
            # (WinError 32), el rename falla, y _disabled=True deja la DB BRICKEADA
            # (Jarvis muerto sin recuperarse). El conn de la línea 88 sigue vivo.
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass
            try:
                bad = self.path.with_suffix(f".corrupt.{int(time.time())}")
                if self.path.exists():
                    self.path.rename(bad)
                # mover también los sidecars WAL/SHM: una recreación con -wal viejo
                # de una DB corrupta puede re-corromper la nueva (auditoría, LOW).
                for _sfx in ("-wal", "-shm"):
                    _side = self.path.with_name(self.path.name + _sfx)
                    if _side.exists():
                        try:
                            _side.rename(bad.with_name(bad.name + _sfx))
                        except OSError:
                            try:
                                _side.unlink()
                            except OSError:
                                pass
            except OSError:
                self._disabled = True
                return None
            try:
                conn = sqlite3.connect(str(self.path), timeout=5.0)
                # MISMO setup que la ruta normal: sin WAL la DB recuperada perdía la
                # garantía multi-conexión (riesgo cross-thread tras corrupción), y sin
                # el índice last_event_ts/miner quedaban lentos. (Caveat del diagnóstico.)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS behavior_events ("
                    " ts INTEGER NOT NULL, user TEXT NOT NULL, kind TEXT NOT NULL,"
                    " key TEXT NOT NULL, context TEXT,"
                    " PRIMARY KEY (ts, user, kind, key))")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_behavior_kind_key"
                    " ON behavior_events(kind, key)")
                conn.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
                conn.execute("INSERT OR IGNORE INTO meta(k,v) VALUES('schema',?)",
                             (str(_SCHEMA_VERSION),))
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

    def last_event_ts(self, kind: str, key: str | None = None) -> int | None:
        """ts (ms) del evento MÁS RECIENTE de este kind (y key opcional), o None.
        Barato (índice idx_behavior_kind_key). Lo usa el throttle de `boot` para no
        floodear la DB cuando el proceso del agente se re-instancia en bucle."""
        conn = self._open()
        if conn is None:
            return None
        try:
            q = ("SELECT MAX(ts) FROM behavior_events"
                 " WHERE user=? AND kind=?")
            params: list = [self.user, kind]
            if key is not None:
                q += " AND key=?"; params.append((key or "").strip().lower())
            row = conn.execute(q, params).fetchone()
        except sqlite3.Error:
            return None
        return int(row[0]) if row and row[0] is not None else None

    def record_throttled(self, kind: str, key: str, min_gap_s: float,
                         context: dict | None = None) -> bool:
        """Como record() pero SOLO si pasó >= min_gap_s desde el último evento
        (mismo kind+key). Causa-raíz del flood de `boot` (F2): cada construcción de
        Gemma4Agent grababa un boot; con restart-loops/server-zombie eso producía
        decenas de miles de filas (medido: 21.442 boots = 77% de la DB, gaps de
        ~180ms) que envenenan al pattern_miner. El throttle vive ACÁ (no en el
        caller) para que cualquier señal de alta frecuencia lo reuse."""
        try:
            last = self.last_event_ts(kind, (key or "").strip().lower())
            if last is not None and (time.time() * 1000 - last) < min_gap_s * 1000:
                return False
        except Exception:
            pass  # ante cualquier duda, grabamos (best-effort, no perder señal)
        return self.record(kind, key, context)

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

    def record_boot(self) -> bool:
        """Registra el arranque de sesión, THROTTLEADO, y aplica retención.

        Encapsula la política de boot para que el caller (Gemma4Agent.__init__)
        sea una sola línea. Dos arreglos viven acá, no en el agente:
        - F2 (flood): cada construcción de Gemma4Agent grababa un boot; con
          restart-loops/server-zombie eso infló la DB a ~21.4k boots (77% de la
          tabla, gaps de ~180ms) y envenenaba las reglas del pattern_miner. Solo
          registramos si pasó >= el gap (un boot REAL son minutos/horas; un
          relanzamiento en bucle son ms). Gap por estado del SO (último ts en la
          DB), configurable por env, NO lista hardcoded.
        - F3 (retención): nadie corría prune() -> la DB crecía sin techo. El
          docstring de prune promete 60 días; ahora SÍ se aplica, best-effort.
        """
        try:
            gap_s = float(os.environ.get("GEMMA4_BOOT_THROTTLE_S", "300"))  # 5 min
        except (TypeError, ValueError):
            gap_s = 300.0
        ok = self.record_throttled("boot", "agent", gap_s)
        try:
            self.prune(older_than_days=60)
        except Exception:
            pass
        return ok

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
