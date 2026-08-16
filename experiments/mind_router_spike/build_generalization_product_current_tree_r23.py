"""Prepare an unopened current-tree Cut-B population after R22.

R22 closed at 149 of 688, and the number said something other than what it
looked like. 560 of its rows carried an instruction frame; with the frame the
deterministic recogniser resolved 29, without it 444. The envelope grammar now
covers that shape.

So this seal has one job the previous one could not do: prove the repair was a
repair and not a memorisation. Every instruction frame here is **different from
the nine R22 used**, while keeping the same shape, because a rule written by
shape must survive wordings it never saw. Entities are rewritten again on top
of R22's own rewrite so no surface repeats, and composition orders are drawn
against every prior corpus including R22.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from random import Random


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import (  # noqa: E402
    build_generalization_product_current_tree_r22 as r22,
)
from scripts import build_generalization_product_holdout_r3 as builder  # noqa: E402
from scripts import build_generalization_product_holdout_r21 as r21  # noqa: E402
from scripts.build_generalization_surface_holdout import Scenario, Utterance  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/generalization_product_current_tree_r23.jsonl"
PREREGISTRATION = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r23.preregistration.json"
)
MIND_OUTPUT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r23_mind.json"
)
MIND_AUDIT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r23_mind.raw.jsonl"
)
MEMORY_TRX = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r23_memory.trx"
)
PRODUCT_OUTPUT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r23_product.json"
)
PRIOR_CORPORA = (*r22.PRIOR_CORPORA, r22.OUTPUT)
POLICY_SOURCES = r22.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/"
    "probe_generalization_product_current_tree_r23.py",
    REPO / "experiments/mind_router_spike/"
    "analyze_generalization_product_current_tree_r23.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    *r22.BUILDER_DEPENDENCIES,
    Path(r22.__file__).resolve(),
)
REFERENCES = r22.REFERENCES


# Entities disjoint from both R21 and R22.
_REPLACEMENTS = (
    ("Carpeta Ámbar", "Carpeta Turquesa"),
    ("Birch Folder", "Willow Folder"),
    ("entradas del museo marítimo", "entradas del jardín botánico"),
    ("maritime museum tickets", "botanical garden tickets"),
    ("Renata", "Ximena"),
    ("Nicolás", "Joaquín"),
    ("Rowan", "Quinn"),
    ("Emerson", "Marlowe"),
    ("Finley", "Ellis"),
    ("Hayden", "Rory"),
    ("Andor", "Severance"),
    ("Constellation", "Silo"),
    ("lagunas glaciales", "dunas costeras"),
    ("glacial lagoons", "coastal dunes"),
    ("linternas solares plegables", "termos de acero aislado"),
    ("foldable solar lanterns", "insulated steel flasks"),
    (
        "mil setenta y uno dividido por cincuenta y uno",
        "mil doscientos siete dividido por veintitrés",
    ),
    (
        "one thousand seventy-one divided by fifty-one",
        "one thousand two hundred seven divided by twenty-three",
    ),
    (
        "mil seventy-one divided by fifty-one",
        "mil two hundred seven divided by twenty-three",
    ),
    ("shakshuka", "okonomiyaki"),
    ("jardín lunar", "huerto vertical"),
    ("moon garden", "vertical orchard"),
    ("Isidora", "Amparo"),
    ("Felipe", "Rodrigo"),
    ("Daniela", "Lucía"),
    ("Cristóbal", "Ignacio"),
    ("Harper", "Sloane"),
    ("Payton", "Arden"),
    ("Kendall", "Reagan"),
    ("Sage", "Juniper"),
    ("Natalia", "Beatriz"),
    ("Claudia", "Rocío"),
)


def _replace_token(text: str, old: str, new: str) -> str:
    return re.sub(rf"(?<!\w){re.escape(old)}(?!\w)", new, text, flags=re.IGNORECASE)


def _rewrite(text: str) -> str:
    rewritten = r22._rewrite(text)
    for old, new in _REPLACEMENTS:
        rewritten = _replace_token(rewritten, old, new)
    return rewritten


# Instruction frames of the same shape as R22's, worded differently on purpose.
# If the envelope grammar only learned R22's nine literals, these fail.
_REQUEST_PREFIXES = {
    "es": (
        "Tómalo como una instrucción para este computador: ",
        "Te paso una orden concreta para la máquina: ",
    ),
    "en": (
        "Handle the following as a request for the machine: ",
        "Consider this an instruction meant for the PC: ",
    ),
    "spanglish": (
        "Toma this como una instrucción para el computer: ",
        "Handle esto as a machine request: ",
    ),
}
# No-action frames, also reworded. These name an instruction and a machine too,
# so they are the case a naive frame rule turns into an action.
_CONVERSATION_PREFIXES = {
    "es": (
        "Sin ninguna orden para el computador, sólo dime: ",
        "No pido ninguna instrucción en la máquina, conversemos: ",
    ),
    "en": (
        "With no instruction for the machine, only tell me: ",
        "Not a request for the PC, just a conversation: ",
    ),
    "spanglish": (
        "Sin ninguna instruction para el computer, sólo dime: ",
        "Not an orden para la máquina, just conversemos: ",
    ),
}


def _request_utterance(value: Utterance, index: int) -> Utterance:
    body = _rewrite(value.text)
    body = body[:1].lower() + body[1:]
    prefixes = _REQUEST_PREFIXES[value.language]
    return Utterance(value.language, prefixes[index % len(prefixes)] + body)


def _conversation_utterance(value: Utterance, index: int) -> Utterance:
    prefixes = _CONVERSATION_PREFIXES[value.language]
    return Utterance(
        value.language,
        prefixes[index % len(prefixes)] + _rewrite(value.text),
    )


_BASE = r21._BASE
SCENARIOS: dict[str, Scenario] = {
    family: Scenario(
        scenario.operations,
        tuple(
            _request_utterance(utterance, index)
            for index, utterance in enumerate(scenario.utterances)
        ),
    )
    for family, scenario in _BASE.SCENARIOS.items()
}
CLARIFICATIONS = Scenario(
    _BASE.CLARIFICATIONS.operations,
    tuple(
        _request_utterance(utterance, index)
        for index, utterance in enumerate(_BASE.CLARIFICATIONS.utterances)
    ),
)
COMPOSITION_PARTS = {
    operation: {language: _rewrite(part) for language, part in parts.items()}
    for operation, parts in _BASE.COMPOSITION_PARTS.items()
}


def _prior_composition_sequences() -> set[tuple[str, ...]]:
    sequences: set[tuple[str, ...]] = set()
    for path in PRIOR_CORPORA:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("case_type") != "composition":
                continue
            accepted = row.get("compatible_terminal_operation_sets", [])
            if accepted:
                sequences.add(tuple(str(value) for value in accepted[0]))
    return sequences


def _generated_compositions() -> tuple[builder.Composition, ...]:
    operations = tuple(COMPOSITION_PARTS)
    prior_sequences = _prior_composition_sequences()
    current: set[tuple[str, ...]] = set()
    languages = ("en", "spanglish", "es")
    random = Random(230023)
    rows: list[builder.Composition] = []
    for index in range(100):
        size = 2 + (index * 3 + 5) % 7
        language = languages[index % len(languages)]
        selected: tuple[str, ...] | None = None
        for _attempt in range(10_000):
            sequence = tuple(random.sample(operations, size))
            if sequence not in prior_sequences and sequence not in current:
                selected = sequence
                current.add(sequence)
                break
        if selected is None:
            raise RuntimeError(f"R23 could not derive novel composition {index}")
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        body = _BASE._composition_text(language, parts, index + 2301)
        rows.append(
            builder.Composition(
                selected,
                _request_utterance(Utterance(language, body), index),
            )
        )
    return tuple(rows)


COMPOSITIONS = _generated_compositions()
CONVERSATIONS = tuple(
    _conversation_utterance(utterance, index)
    for index, utterance in enumerate(_BASE.CONVERSATIONS)
)


def configure() -> None:
    builder.OUTPUT = OUTPUT
    builder.PREREGISTRATION = PREREGISTRATION
    builder.MIND_OUTPUT = MIND_OUTPUT
    builder.MIND_AUDIT = MIND_AUDIT
    builder.MEMORY_TRX = MEMORY_TRX
    builder.PRODUCT_OUTPUT = PRODUCT_OUTPUT
    builder.PRIOR_CORPORA = PRIOR_CORPORA
    builder.POLICY_SOURCES = POLICY_SOURCES
    builder.MEASUREMENT_SOURCES = MEASUREMENT_SOURCES
    builder.BUILDER_DEPENDENCIES = BUILDER_DEPENDENCIES
    builder.CAMPAIGN = "current-tree-r23"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-current-tree.r23"
    builder.PREREGISTRATION_SCHEMA = (
        "baxy.generalization-product-current-tree-preregistration.r23"
    )
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "post_r22_current_tree_unseen_paraphrases_with_instruction_frames_"
        "the_envelope_grammar_never_saw"
    )
    builder.REFERENCES = REFERENCES
    builder.ADDRESSED_PREFIXES = {
        "es": "Baxy, atiende esta indicación de la máquina: ",
        "en": "Baxy, perform this machine instruction: ",
        "spanglish": "Baxy, atiende this machine instruction: ",
    }
    builder.SCENARIOS = SCENARIOS
    builder.CLARIFICATIONS = CLARIFICATIONS
    builder.COMPOSITIONS = COMPOSITIONS
    builder.CONVERSATIONS = CONVERSATIONS


def main() -> int:
    configure()
    return builder.main()


if __name__ == "__main__":
    raise SystemExit(main())
