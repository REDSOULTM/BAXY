"""Orquestador del Jarvis PROACTIVO: pega el observador (disparo en vivo) con el
miner + suggestion_queue + notifier (toast/voz) + creación/rechazo de la rutina.

Flujo (todo en el daemon del observador, NUNCA en el turno de voz):
  observer detecta transición de app
    -> _on_app_transition(app_que_se_abrió)            (este módulo)
       -> ¿ese app completa un patrón trigger->target conocido y sólido?
          -> suggestion_queue.next_suggestion (cooldowns/rechazos)   (REUSA)
             -> notify_suggestion (toast Sí/No + voz opcional)       (notifier)
                -> [Sí] crea la rutina (created_by=jarvis)  / [No] mark_rejected

Gateado OFF (GEMMA4_JARVIS_PROACTIVE). Best-effort: cualquier fallo -> no sugiere
(nunca rompe el observador). Diseño: documentacion/DISENO_jarvis_proactivo_2026-06-07.md.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ventana en la que el target debe seguir al trigger para considerarlo "en vivo".
_LIVE_WINDOW_S = 120


def make_transition_handler(
    behavior_log,
    *,
    create_routine: Callable[[Any], bool],
    lang: str = "es",
    foreground_proc_fn: Optional[Callable[[], Optional[str]]] = None,
    queue: Any = None,
) -> Callable[[str, str, float], None]:
    """Devuelve el callback que el AmbientObserver llama en cada transición de app.

    `create_routine(cand) -> bool`: el runner inyecta la función que crea la rutina
    (reusa la lógica del chat: routine create con created_by=jarvis). Devuelve True
    si la creó. Lo inyectamos para no acoplar este módulo al agente/tools.
    `queue`: SuggestionQueue inyectable (tests pasan una con dir temporal; prod usa
    la default per-user con sus cooldowns persistidos).
    """
    from .pattern_miner import mine_simple_patterns
    from .suggestion_queue import SuggestionQueue
    from . import proactive_notifier as _notifier

    if queue is None:
        queue = SuggestionQueue()

    def _handler(just_opened_app: str, foreground_proc: str, now: float) -> None:
        # gate: solo si el proactivo está ON (notifier ya lo re-chequea, pero
        # salimos barato acá para no minar en vano).
        if not _notifier._proactive_enabled():
            return
        try:
            # ¿qué app/boot ocurrió JUSTO ANTES de este app_open? (el trigger)
            recent = behavior_log.events(since_ms=int((now - _LIVE_WINDOW_S) * 1000))
            prior = [e for e in recent
                     if e.get("kind") in ("app_open", "boot")
                     and e.get("key") and e.get("key") != just_opened_app]
            if not prior:
                return
            trigger_key = prior[-1].get("key")   # el más reciente antes del target

            # minar (ventana 30d) y quedarnos con el patrón que matchea ESTE par.
            cands = mine_simple_patterns(
                behavior_log.events(since_ms=int((now - 30 * 86400) * 1000)))
            match = [c for c in cands
                     if c.trigger_key == trigger_key
                     and c.target_key == just_opened_app
                     and c.to_routine_trigger() is not None]   # solo lo automatizable
            if not match:
                return

            cand = queue.next_suggestion(match, now=now)   # respeta cooldowns/rechazos
            if cand is None:
                return

            def _accept(c):
                try:
                    if create_routine(c):
                        queue.mark_accepted(c)
                        logger.info("jarvis proactivo: rutina creada (%s)", c.describe(lang)[:60])
                except Exception as exc:
                    logger.debug("jarvis proactivo accept failed: %s", exc)

            def _reject(c):
                try:
                    queue.mark_rejected(c, now=time.time())
                except Exception:
                    pass

            _notifier.notify_suggestion(
                cand, lang=lang, foreground_proc=foreground_proc,
                on_accept=_accept, on_reject=_reject)
        except Exception as exc:
            logger.debug("jarvis proactivo handler failed: %s", exc)

    return _handler


def build_routine_from_candidate(tools, cand, *, created_by: str = "jarvis") -> bool:
    """Crea una rutina a partir de un PatternCandidate vía el routine_tool.
    Reusa el MISMO mapeo que el chat (_handle_pending_suggestion). created_by marca
    el origen para la reversibilidad (list/disable/delete filtrado). True si ok."""
    rt = cand.to_routine_trigger()
    if not rt:
        return False
    label = f"jarvis: {cand.describe('es')}"[:60]
    trigger = {"type": rt["trigger_type"]}
    if rt["trigger_type"] in ("on_app_open", "on_app_close") and rt.get("trigger_key"):
        trigger["process"] = rt["trigger_key"]
    args = {"action": "create", "name": label, "created_by": created_by,
            "trigger": trigger, "steps": [rt["action"]]}
    try:
        res = tools.execute("routine", args)
        return bool(isinstance(res, dict) and res.get("ok"))
    except Exception:
        return False
