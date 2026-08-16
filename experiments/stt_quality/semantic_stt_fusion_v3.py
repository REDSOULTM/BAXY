"""Precision revision of semantic STT fusion.

V2 surfaced three unnecessary ambiguities from ordinary lower-case morphology
(``como dos/comodos``, ``cambiar los/cambiarlos`` and ``time zone/timezone``).
This revision keeps lexicon compounds only when the acoustic transcript itself
marks both words as a named entity with capitalization.  It deliberately gives
up one lower-case ``work day`` rescue; the measured anchor gate still remains
above 99%, while false clarification pressure is removed.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Sequence


def _load_frozen_base():
    path = Path(__file__).with_name("semantic_stt_fusion.py")
    specification = importlib.util.spec_from_file_location(
        "baxy_semantic_stt_fusion_v2_frozen", path
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("semantic_stt_fusion_v2_import_failed")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


_BASE = _load_frozen_base()
BilingualLexicon = _BASE.BilingualLexicon
EntityAmbiguity = _BASE.EntityAmbiguity
SemanticTranscript = _BASE.SemanticTranscript


def _named_compound_surface(surface: str) -> bool:
    words = surface.split()
    return len(words) == 2 and all(word and word[0].isupper() for word in words)


def canonicalize_transcript(
    primary: str,
    *,
    alternatives: Sequence[str] = (),
    lexicon: BilingualLexicon | None = None,
) -> SemanticTranscript:
    result = _BASE.canonicalize_transcript(
        primary,
        alternatives=alternatives,
        lexicon=lexicon,
    )
    kept: list[EntityAmbiguity] = []
    text = result.text
    removed = False
    for ambiguity in result.ambiguities:
        if ambiguity.reason != "lexical_compound" or _named_compound_surface(
            ambiguity.surface
        ):
            kept.append(ambiguity)
            continue
        suffix = "/" + "/".join(ambiguity.alternatives)
        text = text.replace(ambiguity.surface + suffix, ambiguity.surface, 1)
        removed = True
    transformations = list(result.transformations)
    if removed and not kept and "explicit_entity_ambiguity" in transformations:
        transformations.remove("explicit_entity_ambiguity")
    return SemanticTranscript(
        text=text,
        ambiguities=tuple(kept),
        transformations=tuple(transformations),
    )


__all__ = [
    "BilingualLexicon",
    "EntityAmbiguity",
    "SemanticTranscript",
    "canonicalize_transcript",
]
