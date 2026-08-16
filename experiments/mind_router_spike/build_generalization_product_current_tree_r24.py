"""Prepare an unopened current-tree Cut-B population after R23.

R23 scored 599 of 688, and every one of its 89 failures sat in a single cell of
six: Spanish requests carrying the addressed frame. That frame said "atiende
esta *indicación* de la máquina" while the English and spanglish ones said
"machine *instruction*", and `indicacion` was missing from the instruction-noun
lexicon. Where the word was present the grammar scored 573 of 573; where it was
missing it scored 23,5 %.

That is a seal-design defect as much as a grammar defect. R23 used **one**
addressed frame per language, so a single missing word could erase a whole cell
and hide everything else the seal was meant to measure. This population fixes
the instrument: the vocative carries no instruction noun at all, and the request
frames rotate through **four different instruction nouns per language**. A
lexical gap now shows up as a quarter of one cell instead of a cliff, and twelve
frames are exercised where R23 exercised six.

Entities are rewritten on top of R23's own rewrite so no surface repeats, and
composition orders are drawn against every prior corpus including R23.
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
    build_generalization_product_current_tree_r23 as r23,
)
from scripts import build_generalization_product_holdout_r3 as builder  # noqa: E402
from scripts import build_generalization_product_holdout_r21 as r21  # noqa: E402
from scripts.build_generalization_surface_holdout import Scenario, Utterance  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/generalization_product_current_tree_r24.jsonl"
PREREGISTRATION = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r24.preregistration.json"
)
MIND_OUTPUT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r24_mind.json"
)
MIND_AUDIT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r24_mind.raw.jsonl"
)
MEMORY_TRX = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r24_memory.trx"
)
PRODUCT_OUTPUT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r24_product.json"
)
PRIOR_CORPORA = (*r23.PRIOR_CORPORA, r23.OUTPUT)
POLICY_SOURCES = r23.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/"
    "probe_generalization_product_current_tree_r24.py",
    REPO / "experiments/mind_router_spike/"
    "analyze_generalization_product_current_tree_r24.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    *r23.BUILDER_DEPENDENCIES,
    Path(r23.__file__).resolve(),
)
REFERENCES = r23.REFERENCES


# Entities disjoint from R21, R22 and R23.
_REPLACEMENTS = (
    ("Carpeta Turquesa", "Carpeta Granate"),
    ("Willow Folder", "Cedar Folder"),
    ("entradas del jardín botánico", "entradas del planetario"),
    ("botanical garden tickets", "planetarium tickets"),
    ("Ximena", "Consuelo"),
    ("Joaquín", "Bautista"),
    ("Quinn", "Sutton"),
    ("Marlowe", "Halcyon"),
    ("Ellis", "Bristow"),
    ("Rory", "Tamsin"),
    ("Severance", "Fringe"),
    ("Silo", "Counterpart"),
    ("dunas costeras", "salares de altura"),
    ("coastal dunes", "highland salt flats"),
    ("termos de acero aislado", "brújulas de placa base"),
    ("insulated steel flasks", "baseplate compasses"),
    (
        "mil doscientos siete dividido por veintitrés",
        "mil quinientos treinta y uno dividido por treinta y siete",
    ),
    (
        "one thousand two hundred seven divided by twenty-three",
        "one thousand five hundred thirty-one divided by thirty-seven",
    ),
    (
        "mil two hundred seven divided by twenty-three",
        "mil five hundred thirty-one divided by thirty-seven",
    ),
    ("okonomiyaki", "borscht"),
    ("huerto vertical", "estanque de lluvia"),
    ("vertical orchard", "rain pond"),
    ("Amparo", "Rosalinda"),
    ("Rodrigo", "Teodoro"),
    ("Lucía", "Odalys"),
    ("Ignacio", "Wenceslao"),
    ("Sloane", "Peregrine"),
    ("Arden", "Callaway"),
    ("Reagan", "Marisol"),
    ("Juniper", "Thistle"),
    ("Beatriz", "Genoveva"),
    ("Rocío", "Milagros"),
)


def _replace_token(text: str, old: str, new: str) -> str:
    return re.sub(rf"(?<!\w){re.escape(old)}(?!\w)", new, text, flags=re.IGNORECASE)


def _rewrite(text: str) -> str:
    rewritten = r23._rewrite(text)
    for old, new in _REPLACEMENTS:
        rewritten = _replace_token(rewritten, old, new)
    return rewritten


# Four frames per language, each naming a *different* instruction noun, so a
# single missing word costs a quarter of a cell instead of the whole cell.
# None of these wordings appear in R22 or R23.
_REQUEST_PREFIXES = {
    "es": (
        "Esta consigna va para el equipo: ",
        "Recibe esta directriz de la computadora: ",
        "Va un encargo para la máquina: ",
        "Atiende este mandato en el PC: ",
    ),
    "en": (
        "This directive goes to the machine: ",
        "Take this order for the computer: ",
        "Here is an errand for the PC: ",
        "Attend to this command on the machine: ",
    ),
    "spanglish": (
        "Esta directive va para el computer: ",
        "Take esta consigna para la máquina: ",
        "Va un command para el PC: ",
        "Attend este encargo en la computadora: ",
    ),
}
# No-action frames, also four apiece. These name an instruction and a machine
# too, so they remain the case a naive frame rule would turn into an action.
_CONVERSATION_PREFIXES = {
    "es": (
        "Ninguna consigna para el equipo, sólo charlemos: ",
        "Esto no es una directriz para la computadora, dime nomás: ",
        "Sin encargo alguno para la máquina, conversemos: ",
        "No va ningún mandato al PC, respóndeme y ya: ",
    ),
    "en": (
        "No directive for the machine, let us just talk: ",
        "This is not an order for the computer, only tell me: ",
        "No errand for the PC at all, just chat: ",
        "No command goes to the machine, answer me and that is it: ",
    ),
    "spanglish": (
        "Ninguna directive para el computer, sólo charlemos: ",
        "Esto no es una order para la máquina, dime nomás: ",
        "Sin command alguno para el PC, just conversemos: ",
        "No va ningún encargo a la computadora, answer me y ya: ",
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
    languages = ("es", "en", "spanglish")
    random = Random(240024)
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
            raise RuntimeError(f"R24 could not derive novel composition {index}")
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        body = _BASE._composition_text(language, parts, index + 2401)
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
    builder.CAMPAIGN = "current-tree-r24"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-current-tree.r24"
    builder.PREREGISTRATION_SCHEMA = (
        "baxy.generalization-product-current-tree-preregistration.r24"
    )
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "post_r23_current_tree_unseen_paraphrases_with_four_rotating_instruction_"
        "nouns_per_language_and_an_instruction_free_vocative"
    )
    builder.REFERENCES = REFERENCES
    # Deliberately carries no instruction noun: the addressed/plain split must
    # not be confounded with the instruction-noun lexicon again.
    builder.ADDRESSED_PREFIXES = {
        "es": "Baxy, ",
        "en": "Baxy, ",
        "spanglish": "Baxy, ",
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
