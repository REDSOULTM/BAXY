"""Checkpoint mínimo de misión multi-paso (Fase 7 computer-use).

PROBLEMA: una misión GUI de varios pasos ("abrí Notepad y escribí X y guardá")
que se interrumpe a la mitad (crash, reinicio del proceso, el usuario cancela)
se pierde — el agente no sabe qué hizo ni qué falta. Para misiones de varios
pasos eso es frustrante (rehacer todo) o peligroso (repetir un paso no
idempotente).

SOLUCIÓN (mínima, SOLO modo misión): persistir el progreso clause-by-clause en
un JSON atómico. Antes de cada paso guardamos {clauses, done_index}; al terminar
borramos. Al arrancar, si quedó un checkpoint, el agente puede ofrecer reanudar
los pasos PENDIENTES.

Es "modo misión" a propósito: NO se activa para turnos atómicos (1 cláusula) ni
charla — solo para comandos compuestos GUI (≥2 cláusulas), donde reanudar tiene
sentido. Reusa atomic_write_json (no truncado en crash).

Gate: GEMMA4_MISSION_CHECKPOINT=0 lo desactiva. Best-effort: cualquier fallo de
I/O NO rompe la misión (el checkpoint es una red, no un bloqueante).
"""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Any

from ..memory_pkg.state import atomic_write_json

# Edad máxima de un checkpoint para considerarlo reanudable. Un checkpoint viejo
# (de hace horas) probablemente ya no aplica al estado actual del SO -> lo
# ignoramos al reanudar (pero no rompe nada).
_MAX_RESUMABLE_AGE_S = 1800  # 30 min


def _enabled() -> bool:
    return os.environ.get("GEMMA4_MISSION_CHECKPOINT", "1").strip().lower() \
        not in {"0", "false", "no", "off"}


def _path(state_path: Path) -> Path:
    # Sibling del state.json del agente: mission_checkpoint.json
    return state_path.parent / "mission_checkpoint.json"


def begin(state_path: Path, clauses: list[str], *, kind: str = "multi_intent") -> str | None:
    """Inicia un checkpoint de misión. Devuelve el mission_id o None (off/fallo).
    Solo para misiones de varios pasos (≥2 cláusulas)."""
    if not _enabled() or not clauses or len(clauses) < 2:
        return None
    mid = f"mis_{uuid.uuid4().hex[:10]}"
    try:
        atomic_write_json(_path(state_path), {
            "mission_id": mid,
            "kind": kind,
            "clauses": list(clauses),
            "done_index": 0,
            "results": [],
            "created_at": time.time(),
            "updated_at": time.time(),
            "status": "in_progress",
        })
    except Exception:
        return None
    return mid


def mark_done(state_path: Path, mission_id: str | None, clause_index: int,
              reply: str = "") -> None:
    """Marca la cláusula `clause_index` como completada. Best-effort."""
    if not mission_id or not _enabled():
        return
    p = _path(state_path)
    try:
        import json
        if not p.exists():
            return
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("mission_id") != mission_id:
            return  # otra misión escribió el archivo; no pisar
        data["done_index"] = max(int(data.get("done_index", 0)), clause_index + 1)
        results = data.setdefault("results", [])
        results.append({"clause_index": clause_index, "reply": (reply or "")[:200]})
        data["updated_at"] = time.time()
        atomic_write_json(p, data)
    except Exception:
        pass


def finish(state_path: Path, mission_id: str | None) -> None:
    """Cierra la misión: borra el checkpoint (completada normalmente)."""
    if not mission_id or not _enabled():
        return
    p = _path(state_path)
    try:
        import json
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            # solo borrar si es NUESTRA misión (no pisar otra en curso)
            if data.get("mission_id") in (mission_id, None):
                p.unlink()
    except Exception:
        pass


def pending(state_path: Path) -> dict[str, Any] | None:
    """Devuelve el checkpoint pendiente reanudable (in_progress, no vencido, con
    cláusulas sin hacer) o None. Para que el agente ofrezca reanudar al arrancar."""
    if not _enabled():
        return None
    p = _path(state_path)
    try:
        import json
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("status") != "in_progress":
        return None
    age = time.time() - float(data.get("created_at", 0) or 0)
    if age > _MAX_RESUMABLE_AGE_S:
        return None
    clauses = data.get("clauses") or []
    done = int(data.get("done_index", 0))
    if done >= len(clauses):
        return None  # nada pendiente
    data["remaining"] = clauses[done:]
    return data
