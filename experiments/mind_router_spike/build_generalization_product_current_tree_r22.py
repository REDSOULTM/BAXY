"""Prepare an unopened current-tree Cut-B population after R21.

The builder deliberately derives new entities, request surfaces, and
composition orders without invoking BAXY.  Importing this module never writes
the holdout; ``main`` is the only operation that seals the official files.
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

from scripts import build_generalization_product_holdout_r3 as builder  # noqa: E402
from scripts import build_generalization_product_holdout_r21 as r21  # noqa: E402
from scripts.build_generalization_surface_holdout import (  # noqa: E402
    Scenario,
    Utterance,
)


OUTPUT = REPO / "artifacts/holdout/generalization_product_current_tree_r22.jsonl"
PREREGISTRATION = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r22.preregistration.json"
)
MIND_OUTPUT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r22_mind.json"
)
MIND_AUDIT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r22_mind.raw.jsonl"
)
MEMORY_TRX = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r22_memory.trx"
)
PRODUCT_OUTPUT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r22_product.json"
)
PRIOR_CORPORA = (*r21.PRIOR_CORPORA, r21.OUTPUT)
POLICY_SOURCES = r21.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/"
    "probe_generalization_product_current_tree_r22.py",
    REPO / "experiments/mind_router_spike/"
    "analyze_generalization_product_current_tree_r22.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    *r21.BUILDER_DEPENDENCIES,
    REPO / "scripts/build_generalization_product_holdout_r21.py",
)
REFERENCES = r21.REFERENCES


_REPLACEMENTS = (
    ("Carpeta Jade", "Carpeta Ámbar"),
    ("Cedar Folder", "Birch Folder"),
    ("entradas del acuario", "entradas del museo marítimo"),
    ("aquarium tickets", "maritime museum tickets"),
    ("Camila", "Renata"),
    ("Mateo", "Nicolás"),
    ("Riley", "Rowan"),
    ("Sawyer", "Emerson"),
    ("Reese", "Finley"),
    ("Blake", "Hayden"),
    ("Foundation", "Andor"),
    ("Dark Matter", "Constellation"),
    ("arrecifes de coral", "lagunas glaciales"),
    ("coral reefs", "glacial lagoons"),
    ("radios meteorológicas compactas", "linternas solares plegables"),
    ("compact weather radios", "foldable solar lanterns"),
    (
        "novecientos cincuenta y tres dividido por treinta y uno",
        "mil setenta y uno dividido por cincuenta y uno",
    ),
    (
        "nine hundred fifty-three divided by thirty-one",
        "one thousand seventy-one divided by fifty-one",
    ),
    (
        "novecientos fifty-three divided by thirty-one",
        "mil seventy-one divided by fifty-one",
    ),
    ("bibimbap", "shakshuka"),
    ("invernadero de invierno", "jardín lunar"),
    ("winter greenhouse", "moon garden"),
    ("Sofía", "Isidora"),
    ("Andrés", "Felipe"),
    ("Verónica", "Daniela"),
    ("Gabriel", "Cristóbal"),
    ("Jamie", "Harper"),
    ("Sydney", "Payton"),
    ("Cameron", "Kendall"),
    ("Phoenix", "Sage"),
    ("Paula", "Natalia"),
    ("Mónica", "Claudia"),
)


def _replace_token(text: str, old: str, new: str) -> str:
    return re.sub(
        rf"(?<!\w){re.escape(old)}(?!\w)",
        new,
        text,
        flags=re.IGNORECASE,
    )


def _rewrite(text: str) -> str:
    rewritten = r21._rewrite(text)
    for old, new in _REPLACEMENTS:
        rewritten = _replace_token(rewritten, old, new)
    return rewritten


_REQUEST_PREFIXES = {
    "es": (
        "Esto sí es una orden para el equipo: ",
        "Actúa en el PC con esta instrucción: ",
    ),
    "en": (
        "Treat this as an instruction for the computer: ",
        "Carry out this PC request: ",
    ),
    "spanglish": (
        "Esto is a real PC instruction: ",
        "Haz this on the computer: ",
    ),
}
_CONVERSATION_PREFIXES = {
    "es": (
        "Esto es sólo una conversación y no una orden para el PC: ",
        "Respóndeme sin realizar ningún cambio en el equipo: ",
    ),
    "en": (
        "This is only a conversation, not a computer instruction: ",
        "Answer without making any change on the PC: ",
    ),
    "spanglish": (
        "This es sólo conversación, not a PC instruction: ",
        "Respóndeme only, sin hacer cambios on the computer: ",
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
        for line in path.read_text(encoding="utf-8").splitlines():
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
    languages = ("spanglish", "es", "en")
    random = Random(220022)
    rows: list[builder.Composition] = []
    for index in range(100):
        size = 2 + (index * 5 + 3) % 7
        language = languages[index % len(languages)]
        selected: tuple[str, ...] | None = None
        for _attempt in range(10_000):
            sequence = tuple(random.sample(operations, size))
            if sequence not in prior_sequences and sequence not in current:
                selected = sequence
                current.add(sequence)
                break
        if selected is None:
            raise RuntimeError(f"R22 could not derive novel composition {index}")
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        body = _BASE._composition_text(language, parts, index + 2201)
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
    builder.CAMPAIGN = "current-tree-r22"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-current-tree.r22"
    builder.PREREGISTRATION_SCHEMA = (
        "baxy.generalization-product-current-tree-preregistration.r22"
    )
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "post_r21_current_tree_unseen_paraphrases_disjoint_entities_"
        "and_composition_orders"
    )
    builder.REFERENCES = REFERENCES
    builder.ADDRESSED_PREFIXES = {
        "es": "Baxy, ejecuta esta instrucción del equipo: ",
        "en": "Baxy, execute this computer instruction: ",
        "spanglish": "Baxy, ejecuta this PC instruction: ",
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
