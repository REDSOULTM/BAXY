"""Detección de patrones de comportamiento (Capa A: conteo contextual).

Código DETERMINISTA que mina el behavior_log y detecta rutinas repetidas del
usuario para OFRECER automatizarlas. El LLM NO mina (sería lento/alucinógeno en
4B); solo conversa la sugerencia.

Capa A — conteo contextual: para cada par (trigger, target) dentro de una ventana
temporal, contar cuántas veces el target sigue al trigger. Si supera umbrales
CONSERVADORES, es candidato. Cubre el caso de RED ("cierro Discord al arrancar").

Umbrales conservadores para no molestar sin evidencia (Horvitz 1999, TaraHome):
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

    # Plantillas del patrón por idioma (multilingüe). Solo conectivos/verbos
    # genéricos; los nombres de app (target_key) son neutrales. {trig}/{act} se
    # rellenan con las sub-plantillas. Cubre es/en/pt/fr/de/it; fallback es.
    _DESC = {
        "es": ("arrancás la PC", "abrís {k}", {"app_close": "cerrás {k}", "app_open": "abrís {k}", "cmd": "usás «{k}»"}, "cuando {trig}, {act}"),
        "en": ("you start the PC", "you open {k}", {"app_close": "you close {k}", "app_open": "you open {k}", "cmd": "you use «{k}»"}, "when {trig}, {act}"),
        "pt": ("você liga o PC", "você abre {k}", {"app_close": "você fecha {k}", "app_open": "você abre {k}", "cmd": "você usa «{k}»"}, "quando {trig}, {act}"),
        "fr": ("tu démarres le PC", "tu ouvres {k}", {"app_close": "tu fermes {k}", "app_open": "tu ouvres {k}", "cmd": "tu utilises «{k}»"}, "quand {trig}, {act}"),
        "de": ("du den PC startest", "du {k} öffnest", {"app_close": "du {k} schließt", "app_open": "du {k} öffnest", "cmd": "du «{k}» benutzt"}, "wenn {trig}, {act}"),
        "it": ("avvii il PC", "apri {k}", {"app_close": "chiudi {k}", "app_open": "apri {k}", "cmd": "usi «{k}»"}, "quando {trig}, {act}"),
    }

    def describe(self, lang: str = "es") -> str:
        """Texto natural del patrón en el idioma del usuario (multilingüe)."""
        boot_t, open_t, act_map, frame = self._DESC.get(lang, self._DESC["es"])
        trig = boot_t if self.trigger_kind == "boot" else open_t.format(k=self.trigger_key)
        act = act_map.get(self.target_kind, f"{self.target_kind} {self.target_key}").format(k=self.target_key)
        return frame.format(trig=trig, act=act)


    def to_routine_trigger(self) -> dict[str, Any] | None:
        """Mapea el patrón a un trigger del routine_tool existente (traducción
        1-a-1). None si no hay mapping FIEL."""
        if self.trigger_kind == "boot":
            # HONESTIDAD (auditoría 2026-06-07): NO existe trigger de logon/startup
            # real en routine.py (solo manual/cron/once/on_app_*). Mapear boot->cron
            # caía a daily@09:00 -> "cuando arrancás la PC, abro X" se programaba para
            # las 9 AM, NO al arranque. Mentira funcional. Hasta que exista un trigger
            # AtLogOn, NO ofrecemos automatizar patrones de boot (no prometer lo que no
            # se cumple). El miner los puede detectar, pero no se ofrecen.
            return None
        if self.trigger_kind == "app_open":
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


# Frases del handshake de sugerencia proactiva por idioma (multilingüe). {desc}
# = la descripción del patrón ya en el idioma del usuario. No es una respuesta
# enlatada a una pregunta del usuario: es el handshake sí/no que inicia el propio
# agente, por eso es texto fijo y no pasa por el LLM. Cubre es/en/pt/fr/de/it;
# fallback es.
JARVIS_PHRASES = {
    "es": {"offer": "\n\nPor cierto: noté que {desc}. ¿Querés que lo automatice? (decí sí o no)",
           "rejected": "Listo, no lo automatizo. Avisame si cambiás de idea.",
           "accepted": "Hecho. Automaticé: {desc}.",
           "build_fail": "Quise automatizarlo pero no pude armar la rutina; lo dejo para más adelante.",
           "create_fail": "Intenté automatizarlo pero la creación de la rutina falló. Lo dejamos manual por ahora."},
    "en": {"offer": "\n\nBy the way: I noticed that {desc}. Want me to automate it? (say yes or no)",
           "rejected": "OK, I won't automate it. Let me know if you change your mind.",
           "accepted": "Done. I automated: {desc}.",
           "build_fail": "I wanted to automate it but couldn't build the routine; leaving it for later.",
           "create_fail": "I tried to automate it but creating the routine failed. Keeping it manual for now."},
    "pt": {"offer": "\n\nA propósito: notei que {desc}. Quer que eu automatize? (diga sim ou não)",
           "rejected": "Pronto, não vou automatizar. Avise se mudar de ideia.",
           "accepted": "Feito. Automatizei: {desc}.",
           "build_fail": "Quis automatizar mas não consegui montar a rotina; deixo para depois.",
           "create_fail": "Tentei automatizar mas a criação da rotina falhou. Fica manual por ora."},
    "fr": {"offer": "\n\nAu fait : j'ai remarqué que {desc}. Tu veux que je l'automatise ? (dis oui ou non)",
           "rejected": "D'accord, je ne l'automatise pas. Dis-moi si tu changes d'avis.",
           "accepted": "Fait. J'ai automatisé : {desc}.",
           "build_fail": "Je voulais l'automatiser mais je n'ai pas pu créer la routine ; je laisse pour plus tard.",
           "create_fail": "J'ai essayé d'automatiser mais la création de la routine a échoué. On le garde manuel pour l'instant."},
    "de": {"offer": "\n\nÜbrigens: Mir ist aufgefallen, dass {desc}. Soll ich das automatisieren? (sag ja oder nein)",
           "rejected": "OK, ich automatisiere es nicht. Sag Bescheid, wenn du es dir anders überlegst.",
           "accepted": "Erledigt. Automatisiert: {desc}.",
           "build_fail": "Ich wollte es automatisieren, konnte die Routine aber nicht erstellen; lasse es für später.",
           "create_fail": "Ich habe es versucht, aber die Routine-Erstellung schlug fehl. Bleibt vorerst manuell."},
    "it": {"offer": "\n\nA proposito: ho notato che {desc}. Vuoi che lo automatizzi? (dì sì o no)",
           "rejected": "Ok, non lo automatizzo. Fammi sapere se cambi idea.",
           "accepted": "Fatto. Ho automatizzato: {desc}.",
           "build_fail": "Volevo automatizzarlo ma non sono riuscito a creare la routine; lo lascio per dopo.",
           "create_fail": "Ho provato ad automatizzarlo ma la creazione della routine è fallita. Resta manuale per ora."},
}


def jarvis_phrase(lang: str, key: str) -> str:
    """Frase del handshake en el idioma del usuario (fallback es)."""
    return JARVIS_PHRASES.get(lang, JARVIS_PHRASES["es"]).get(key, JARVIS_PHRASES["es"][key])


def mine_simple_patterns(
    events: list[dict],
    *,
    min_count: int = 8,
    min_consistency: float = 0.75,
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
    # BUG FIX (2026-06-07): contar cada par (trigger->target) UNA SOLA VEZ por
    # ocurrencia del trigger. Antes el loop interno sumaba +1 por CADA aparición
    # del target en la ventana de 2 min -> si tras abrir X el usuario abría Y dos
    # veces (o Y figuraba 2x), pair_count[X->Y] crecía más que trigger_total[X] y
    # la consistencia daba >100% (medido: 1100%). Eso hacía que correlaciones
    # ESPURIAS ("abrís Spotify -> abrís Disney") superaran el umbral 60% y Baxy
    # ofreciera automatizarlas. Con dedup por-trigger, consistency ∈ [0,1] real.
    for i, ev in enumerate(events):
        if ev["kind"] not in ("boot", "app_open"):
            continue
        trig = (ev["kind"], ev["key"])
        trigger_total[trig] += 1
        # targets ÚNICOS vistos en ESTA ventana (dedup: 1 voto por trigger).
        seen_targets: dict[tuple, float] = {}
        for j in range(i + 1, len(events)):
            nxt = events[j]
            dt = nxt["ts"] - ev["ts"]
            if dt > delta_max_ms:
                break
            if nxt["kind"] in ("app_close", "app_open", "cmd") and nxt["key"] != ev["key"]:
                tgt = (nxt["kind"], nxt["key"])
                if tgt not in seen_targets:           # primer (= más cercano) delta
                    seen_targets[tgt] = dt / 1000.0
        for tgt, dt_s in seen_targets.items():
            pair = (trig, tgt)
            pair_count[pair] += 1                     # +1 por trigger, no por aparición
            pair_deltas[pair].append(dt_s)

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
