"""Semantic-risk revision of the structured ASR fusion result.

Written-form aliases (state name/abbreviation, spacing, acronym segmentation)
preserve evidence but do not require a user clarification.  Only alternatives
that can denote different real entities block an effect.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys
from typing import Sequence


def _load_v3():
    path = Path(__file__).with_name("semantic_stt_fusion_v3.py")
    specification = importlib.util.spec_from_file_location(
        "baxy_semantic_stt_fusion_v3_frozen", path
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("semantic_stt_fusion_v3_import_failed")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


_BASE = _load_v3()
BilingualLexicon = _BASE.BilingualLexicon
EntityAmbiguity = _BASE.EntityAmbiguity
_SEMANTIC_AMBIGUITY_REASONS = frozenset(
    {
        "address_homophone",
        "bilingual_device_brand",
        "multi_asr_proper_name",
    }
)


@dataclass(frozen=True)
class SemanticTranscript:
    text: str
    ambiguities: tuple[EntityAmbiguity, ...]
    transformations: tuple[str, ...]

    @property
    def requires_clarification(self) -> bool:
        return any(
            ambiguity.reason in _SEMANTIC_AMBIGUITY_REASONS
            for ambiguity in self.ambiguities
        )


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
    return SemanticTranscript(
        text=result.text,
        ambiguities=result.ambiguities,
        transformations=result.transformations,
    )


__all__ = [
    "BilingualLexicon",
    "EntityAmbiguity",
    "SemanticTranscript",
    "canonicalize_transcript",
]
