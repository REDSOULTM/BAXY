"""Cola de sugerencias proactivas con cooldowns (anti-"Clippy").

Investigación 5 (Jarvis, 2026-05-23): un patrón detectado por pattern_miner NO se
ofrece de inmediato. Esta cola decide CUÁNDO ofrecer, respetando el balance
proactividad-vs-molestia (Horvitz 1999 act/ask/wait; TaraHome "conservative").

Reglas (del informe):
  - Cooldown GLOBAL: máx 1 sugerencia/hora, 3/día.
  - Cooldown POR PATRÓN: si el usuario lo rechazó, no re-ofrecer por 30 días
    (o hasta que el count del patrón se duplique).
  - Solo ofrecer en un BREAKPOINT (fin de boot, post-chat, silencio del mic) —
    nunca a media tarea.
  - Dedup: no encolar un patrón ya pendiente o ya convertido en rutina.

Estado persistido en ~/.gemma4/behavior/<user>.suggestions.json (local, per-user).
El LLM no participa acá; solo recibe el patrón a conversar cuando esta cola lo
libera. Todo determinista, cabe en vram4.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from .pattern_miner import PatternCandidate

logger = logging.getLogger(__name__)

_DEFAULT_DIR = Path.home() / ".gemma4" / "behavior"
_HOUR = 3600.0
_DAY = 86400.0
_REJECT_COOLDOWN_S = 30 * _DAY


def _pattern_id(p: PatternCandidate) -> str:
    return f"{p.trigger_kind}:{p.trigger_key}->{p.target_kind}:{p.target_key}"


def _user() -> str:
    return (os.environ.get("USERNAME") or os.environ.get("USER")
            or "default").strip() or "default"


@dataclass
class SuggestionQueue:
    """Decide qué patrón ofrecer y cuándo, con cooldowns. Persistente per-user."""

    user: str = field(default_factory=_user)
    dir_path: Path = _DEFAULT_DIR
    max_per_hour: int = 1
    max_per_day: int = 3

    @property
    def _path(self) -> Path:
        safe = "".join(c for c in self.user if c.isalnum() or c in "._-") or "default"
        return self.dir_path / f"{safe}.suggestions.json"

    def _load(self) -> dict:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {"offered": [], "rejected": {}, "accepted": []}

    def _save(self, state: dict) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            logger.debug("suggestion state save failed: %s", exc)

    # ------------------------------------------------------------------ API
    def next_suggestion(
        self, candidates: list[PatternCandidate], *, now: float | None = None,
    ) -> PatternCandidate | None:
        """Devuelve el mejor candidato OFRECIBLE ahora (respetando cooldowns), o
        None si no toca ofrecer. Llamar SOLO en un breakpoint (el caller decide
        que es buen momento). Registra la oferta para el rate-limit."""
        now = time.time() if now is None else now
        state = self._load()
        offered = state.get("offered", [])
        # rate-limit global
        recent_h = [t for t in offered if now - t < _HOUR]
        recent_d = [t for t in offered if now - t < _DAY]
        if len(recent_h) >= self.max_per_hour or len(recent_d) >= self.max_per_day:
            return None

        rejected = state.get("rejected", {})   # pattern_id -> {ts, count_at_reject}
        accepted = set(state.get("accepted", []))

        for cand in candidates:
            pid = _pattern_id(cand)
            if pid in accepted:
                continue  # ya es rutina
            rej = rejected.get(pid)
            if rej:
                # cooldown 30d, salvo que el count se haya DUPLICADO desde el rechazo
                if (now - rej.get("ts", 0)) < _REJECT_COOLDOWN_S and \
                   cand.count < 2 * rej.get("count_at_reject", cand.count):
                    continue
            # OFRECIBLE: registrar la oferta y devolver
            offered.append(now)
            state["offered"] = [t for t in offered if now - t < _DAY]  # podar
            self._save(state)
            return cand
        return None

    def mark_accepted(self, cand: PatternCandidate) -> None:
        state = self._load()
        acc = set(state.get("accepted", []))
        acc.add(_pattern_id(cand))
        state["accepted"] = sorted(acc)
        self._save(state)

    def mark_rejected(self, cand: PatternCandidate, *, now: float | None = None) -> None:
        now = time.time() if now is None else now
        state = self._load()
        state.setdefault("rejected", {})[_pattern_id(cand)] = {
            "ts": now, "count_at_reject": cand.count}
        self._save(state)
