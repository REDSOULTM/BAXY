"""Tanda 7 (2026-09-25, official window): the latency regression against tanda 6c on the same build.

- Deterministic decisions (a volume, a mute, a timer, a paused track) took 1.3–1.9 s in ``turn.decide`` with no
  model call at all. One decision reads ~770 distinct patterns and the ``re`` module keeps 512 compiled, so every
  turn compiled ~600 of them again: 95 % of a deterministic decision was compiling regular expressions, and the
  same cost sat under every model-path turn's own readers and vetoes. The readers' shared primitives
  (``grammar._match``/``_has``/``_head_is``) now compile each pattern once for the life of the mind.

The phrasings below are not the tanda's: they are paraphrases (es/en/spanglish).
"""

from __future__ import annotations

import re

import pytest

from baxy_mind.semantic import grammar
from baxy_mind.semantic.reading import read

_OPERATIONS = (
    "audio.mute", "audio.volume", "audio.volume.adjust", "notification.schedule",
    "media.control", "weather.current", "system.settings.set", "window.minimize.all", "web.search",
)
_REQUESTS = (
    "vuelve a activar el parlante",
    "turn the speakers back on please",
    "ponle el volumen en 20",
    "súbele unos 10 al sonido",
    "pon una alarma en 7 minutos",
    "set me a timer for 12 minutes for the rice",
    "sigue con la canción que estaba en pausa",
    "is it going to rain later today",
    "baja el brightness a 40 por ciento",
    "llévame al escritorio",
)


# ------------------------------------------------------------------ the readers compile each pattern once


@pytest.mark.parametrize(
    ("text", "pattern"),
    [
        ("Pon el VOLUMEN a 20", r"\bvolumen\b"),
        ("turn the Speakers on", r"\bspeakers?\b"),
        ("nada que ver", r"\bvolumen\b"),
        ("ALARMA en 7", r"(?P<n>\d+)"),
    ],
)
def test_a_reader_match_is_the_case_insensitive_search_it_always_was(text: str, pattern: str) -> None:
    expected = re.search(pattern, text, re.IGNORECASE)
    found = grammar._match(text, pattern)

    assert (found is None) == (expected is None)
    if expected is not None:
        assert found is not None
        assert found.span() == expected.span()
        assert found.groupdict() == expected.groupdict()
    assert grammar._has(text, pattern) is (expected is not None)


@pytest.mark.parametrize(
    ("head", "pattern"),
    [("subele", r"sube"), ("SUBELE", r"sube"), ("ponme", r"pon(?:me)?"), ("ponme", r"baja"), ("apagala", r"apaga")],
)
def test_a_head_is_read_in_all_its_forms_without_case(head: str, pattern: str) -> None:
    expected = any(re.fullmatch(pattern, form, re.IGNORECASE) for form in grammar._head_forms(head))

    assert grammar._head_is(head, pattern) is expected


def test_reading_a_request_again_compiles_nothing() -> None:
    for text in _REQUESTS:
        read(text, available_operations=_OPERATIONS)
    compiled = grammar._compiled.cache_info().misses

    for text in _REQUESTS:
        read(text, available_operations=_OPERATIONS)

    assert grammar._compiled.cache_info().misses == compiled


def test_the_readers_whole_working_set_stays_compiled() -> None:
    for text in _REQUESTS:
        read(text, available_operations=_OPERATIONS)
    info = grammar._compiled.cache_info()

    # Every pattern ever compiled is still held: evicting one would bring the per-turn compilation back.
    assert info.misses == info.currsize < info.maxsize

