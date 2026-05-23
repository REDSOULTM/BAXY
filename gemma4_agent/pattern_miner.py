"""Detección de patrones de comportamiento (Capa A: conteo contextual).

Investigación 5 (Jarvis, 2026-05-23): código DETERMINISTA que mina el
behavior_log y detecta rutinas repetidas del usuario para OFRECER automatizarlas.
El LLM NO mina (sería lento/alucinógeno en 4B); solo conversa la sugerencia.

Capa A — conteo contextual: para cada par (trigger, target) dentro de una ventana
temporal, contar cuántas veces el target sigue al trigger. Si supera umbrales
CONSERVADORES, es candidato. Cubre el caso de RED ("cierro Discord al arrancar").

Umbrales (del informe, conservadores para no molestar — Horvitz 1999, TaraHome):
  - min_count: 5 ocurrencias del patrón.
  - min_consistency: 0.6 (el target sigue al trigger ≥60% de las veces).
  - window_days: 7 mínimo (filtra experimentos de un día).
  - delta_max_s: 120 (el target debe ocurrir dentro de 2 min del trigger).

Capa B (PrefixSpan para secuencias compuestas) queda para después; el caso de
RED es Capa A. Todo Python puro, sin GPU, cabe en vram4.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PatternCandidate:
    """Un patrón detectado: 'tras TRIGGER, el usuario hace TARGET'."""
    trigger_kind: str   # 'boot' | 'app_open' | ...
    trigger_key: str    # '' para boot; 'steam.exe' para app_open
    target_kind: str    # 'app_close' | 'app_open' | 'cmd'
    target_key: str     # 'discord.exe', etc.
    count: int          # cuántas veces se observó el patrón
    consistency: float  # count / veces que ocurrió el trigger
    delta_median_s: float  # mediana del delay trigger→target

    def describe_es(self) -> str:
        """Texto natural del patrón para la propuesta (lo que el LLM conversa)."""
        trig = "arrancás la PC" if self.trigger_kind == "boot" else \
               f"abrís {self.trigger_key}"
        act = {"app_close": f"cerrás {self.target_key}",
               "app_open": f"abrís {self.target_key}",
               "cmd": f"usás «{self.target_key}»"}.get(
                   self.target_kind, f"{self.target_kind} {self.target_key}")
        return f"cuando {trig}, {act}"

    def to_routine_trigger(self) -> dict[str, Any] | None:
        """Mapea el patrón a un trigger del routine_tool existente (traducción
        1-a-1 del informe). None si no hay mapping claro."""
        if self.trigger_kind == "boot":
            tt = "cron"  # boot ≈ tarea al inicio de sesión
        elif self.trigger_kind == "app_open":
            tt = "on_app_open"
        elif self.trigger_kind == "app_close":
            tt = "on_app_close"
        else:
            return None
        action = None
        if self.target_kind == "app_close":
            action = {"tool": "app", "args": {"action": "close", "name": self.target_key}}
        elif self.target_kind == "app_open":
            action = {"tool": "app", "args": {"action": "open", "name": self.target_key}}
        if action is None:
            return None
        return {"trigger_type": tt, "trigger_key": self.trigger_key or None,
                "action": action}


def mine_simple_patterns(
    events: list[dict],
    *,
    min_count: int = 5,
    min_consistency: float = 0.6,
    window_days: int = 7,
    delta_max_s: int = 120,
) -> list[PatternCandidate]:
    """Mina patrones (trigger→target) por conteo contextual sobre `events`
    (orden cronológico, como los devuelve BehaviorLog.events()).

    Devuelve candidatos que superan los umbrales conservadores. Vacío si no hay
    suficiente señal (no molesta sin evidencia)."""
    if not events:
        return []
    # ventana temporal: necesitamos ≥window_days de datos para confiar
    span_ms = events[-1]["ts"] - events[0]["ts"]
    if span_ms < window_days * 86400 * 1000:
        return []  # datos insuficientes -> no sugerir aún

    delta_max_ms = delta_max_s * 1000
    # contar: por cada trigger, qué target lo sigue dentro de delta_max
    trigger_total: dict[tuple, int] = defaultdict(int)       # veces que ocurre el trigger
    pair_count: dict[tuple, int] = defaultdict(int)          # (trigger, target) → count
    pair_deltas: dict[tuple, list] = defaultdict(list)

    # un evento es "trigger" si es boot o app_open; el "target" es el siguiente
    # evento accionable dentro de la ventana.
    for i, ev in enumerate(events):
        if ev["kind"] not in ("boot", "app_open"):
            continue
        trig = (ev["kind"], ev["key"])
        trigger_total[trig] += 1
        # buscar targets dentro de delta_max
        for j in range(i + 1, len(events)):
            nxt = events[j]
            dt = nxt["ts"] - ev["ts"]
            if dt > delta_max_ms:
                break
            if nxt["kind"] in ("app_close", "app_open", "cmd") and nxt["key"] != ev["key"]:
                pair = (trig, (nxt["kind"], nxt["key"]))
                pair_count[pair] += 1
                pair_deltas[pair].append(dt / 1000.0)

    out: list[PatternCandidate] = []
    for (trig, target), cnt in pair_count.items():
        if cnt < min_count:
            continue
        total = trigger_total[trig] or 1
        consistency = cnt / total
        if consistency < min_consistency:
            continue
        deltas = sorted(pair_deltas[(trig, target)])
        med = deltas[len(deltas) // 2] if deltas else 0.0
        out.append(PatternCandidate(
            trigger_kind=trig[0], trigger_key=trig[1],
            target_kind=target[0], target_key=target[1],
            count=cnt, consistency=round(consistency, 2), delta_median_s=round(med, 1)))
    # ordenar por (consistencia, count) desc — los más sólidos primero
    out.sort(key=lambda p: (p.consistency, p.count), reverse=True)
    return out
