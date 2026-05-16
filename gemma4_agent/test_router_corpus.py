"""Router corpus from real user utterances captured in traces.

Companion to test_router.py — instead of synthetic phrasings, this file uses
actual user inputs harvested from gemma4_agent/data/traces.jsonl. It measures
hit-rate against the deterministic planner and asserts a minimum global hit
rate, NOT per-case routing. Per-case assertions live in test_router.py.

Why a hit-rate test and not per-case asserts?
  - Real utterances are messy (typos, mixed lang, half-finished). Per-case
    rigidity would over-fit and break on legitimate router improvements.
  - We want a regression alarm if a router change drops the global hit rate
    by ≥5 percentage points.
"""
from __future__ import annotations

import unittest
from dataclasses import dataclass

from .planner import plan_mission, select_tool_names


@dataclass(frozen=True)
class Utterance:
    text: str
    expected_any_of: tuple[str, ...]  # router hit if subset contains at least one


# Utterances harvested from traces (2026-05-12 → 2026-05-15). Selected to cover
# the seven most-active intent buckets: streaming, app open/close, audio,
# whatsapp, browser/web, memory recall, system. Pure chitchat omitted (no
# tool expected, no signal).
CORPUS: list[Utterance] = [
    # ── Streaming / media (the most-touched intent in last 7d traces) ──
    Utterance("pon una canción de Michael Jackson", ("media",)),
    Utterance("pon Daredevil en Disney+, mi perfil es emma", ("media",)),
    Utterance("Pon daredevil born again en disney", ("media",)),
    Utterance("pon musica en Spotify", ("media",)),
    Utterance("Pon bad de michael jackson", ("media",)),
    Utterance("pon un video en youtube de gatos", ("media",)),
    Utterance("para la cancion", ("media", "audio")),
    Utterance("pon en pantalla completa el video", ("media", "gui", "window")),
    Utterance("puedes reanudar el video que estoy viendo?", ("media", "audio")),
    Utterance("en Spotify pon una canción de Benson Boone", ("media",)),

    # ── App open / close (high frequency, simple verbs) ──
    Utterance("abre Spotify", ("app", "media")),
    Utterance("Abre steam", ("steam", "app")),
    Utterance("cierra whatsapp", ("app", "whatsapp")),
    Utterance("cierra logitech g hub", ("app",)),
    Utterance("abre opera gx y luego ve a la pagina de steam",
              ("app", "browser", "steam")),
    Utterance("instala doom eternal en steam", ("steam",)),

    # ── Volume / audio ──
    Utterance("Cambia el volumen a 10", ("audio",)),
    Utterance("baja el volumen", ("audio",)),
    Utterance("pon el volumen del PC a 20", ("audio",)),  # cleaned (trace had typo)
    Utterance("puedes cambiar el dispositivo e audio?",
              ("audio_device", "audio")),

    # ── WhatsApp ──
    Utterance("Dile a mi amiga que la amo mucho.", ("whatsapp", "contacts")),
    Utterance("escribele en wsp a amor", ("whatsapp", "contacts")),
    Utterance("Hey Gemma, mandale 'te amo muchisimo' a Ana en wsp",
              ("whatsapp", "contacts")),

    # ── Filesystem ──
    Utterance("Ves los archivos en C:\\Users\\usuario\\Downloads??",
              ("filesystem",)),
    Utterance("puedes tomar todolos los archivos y organizarlos?",
              ("filesystem",)),

    # ── Browser / web ──
    Utterance("en opera busca gordo", ("browser",)),
    Utterance("ve a steam a la paguna de marvel rivals",
              ("steam", "browser")),
    Utterance("investigame algo sobre Batman vs Superman cuando salió esa película",
              ("web", "browser")),

    # ── System ──
    Utterance("dime la hora", ("system",)),
    Utterance("pantallazo", ("gui", "vision")),

    # ── Memory / state ──
    Utterance("Quiero que me recuerdes como red", ("memory",)),
    Utterance("Como me llamo", ("memory",)),
]


def _subset_for(text: str) -> list[str]:
    plan = plan_mission(text)
    return list(select_tool_names(text, plan))


class TestRouterCorpus(unittest.TestCase):
    """Global hit-rate alarm. Drops > 5pp from current baseline = test fail."""

    # 2026-05-16 measurement: documented in NIGHT_AUDIT — we want at least
    # this much. If your router change drops below, the bar moved on purpose
    # (or it broke); investigate before bumping.
    MIN_HIT_RATE = 0.75

    def test_hit_rate_meets_threshold(self):
        misses: list[Utterance] = []
        hits = 0
        for u in CORPUS:
            subset = _subset_for(u.text)
            if any(t in subset for t in u.expected_any_of):
                hits += 1
            else:
                misses.append(u)
        rate = hits / len(CORPUS)
        msg = (
            f"router hit-rate {rate:.0%} ({hits}/{len(CORPUS)}) below "
            f"threshold {self.MIN_HIT_RATE:.0%}. Misses:\n"
            + "\n".join(
                f"  - {u.text!r} expected any of {u.expected_any_of}, got "
                f"{_subset_for(u.text)[:6]}..."
                for u in misses
            )
        )
        self.assertGreaterEqual(rate, self.MIN_HIT_RATE, msg)


class TestRouterDoesNotMisrouteProfileAnswers(unittest.TestCase):
    """REGRESION: "Mi perfil es X" used to misroute to email (because of
    "es" + name). Pending-action resume now intercepts these before the
    router, but if that bypass ever breaks, the router itself should not
    confidently steer toward unrelated tools."""

    def test_mi_perfil_es_short_phrase_does_not_force_email(self):
        # NOTE: the agent's _try_resume_pending_action runs BEFORE the router
        # in the live flow, so this only matters as a safety net. We assert
        # that "email" is not the dominant routing signal — i.e. it should not
        # be one of the few tools selected for such a short phrase.
        subset = _subset_for("Mi perfil es Ema")
        # If email shows up, it should be incidental, not solo.
        # Strong miss = subset is exactly {"email"} or similar.
        self.assertNotEqual(subset, ["email"])

    def test_bare_name_does_not_lock_to_any_action_tool(self):
        # "Ema" alone is a non-actionable utterance; router can pick anything
        # but should not commit to a destructive action category.
        subset = _subset_for("Ema")
        for forbidden in ("filesystem_delete", "shutdown", "system"):
            # subset items might be compound tool names, so substring match
            # is loose but sufficient for this regression check.
            self.assertNotIn(forbidden, subset)


if __name__ == "__main__":
    unittest.main()
