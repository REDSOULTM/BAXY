"""Prepare an unopened current-tree Cut-B population after R27.

R27 scored 698 of 700 and the physical dependent missions then found two
recognizer defects that no cut-B seal had ever exercised, because no cut-B
corpus enumerates two notes and then reads them back by ordinal:

* a scope modifier hid the governing noun, so "create a **local** note titled A
  and another titled B" rebuilt the elliptical clause with no object at all and
  counted the pair as one note;
* "read the second note and finally the first note" resolved to a single read,
  which is a conservation loss -- four operations asked, three returned.

Both are closed. This population exists to test them blind, so its composition
bodies deliberately include enumerated multi-note authoring with modifiers and
coordinated ordinal read-backs, in all three languages, alongside the ordinary
cut-B distribution. Entities and frames are new again.
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
    build_generalization_product_current_tree_r27 as r27,
)
from scripts import build_generalization_product_holdout_r3 as builder  # noqa: E402
from scripts import build_generalization_product_holdout_r21 as r21  # noqa: E402
from scripts.build_generalization_surface_holdout import Scenario, Utterance  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/generalization_product_current_tree_r28.jsonl"
PREREGISTRATION = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r28.preregistration.json"
)
MIND_OUTPUT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r28_mind.json"
)
MIND_AUDIT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r28_mind.raw.jsonl"
)
MEMORY_TRX = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r28_memory.trx"
)
PRODUCT_OUTPUT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r28_product.json"
)
# R24 is absent on purpose: it was sealed but never opened, so nothing of it has
# been seen. R25 is present, because it was opened and spent.
PRIOR_CORPORA = (*r27.PRIOR_CORPORA, r27.OUTPUT)
POLICY_SOURCES = r27.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/"
    "probe_generalization_product_current_tree_r28.py",
    REPO / "experiments/mind_router_spike/"
    "analyze_generalization_product_current_tree_r28.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    *r27.BUILDER_DEPENDENCIES,
    Path(r27.__file__).resolve(),
)
REFERENCES = r27.REFERENCES


# Entities disjoint from R21 through R25.
_REPLACEMENTS = (
    ("Carpeta Ocre", "Carpeta Cobalto"),
    ("Rowan Grove Folder", "Hazel Ridge Folder"),
    ("entradas del observatorio", "entradas del anfiteatro"),
    ("observatory tickets", "amphitheatre tickets"),
    ("Filomena", "Ludovica"),
    ("Evaristo", "Fulgencio"),
    ("Thorne", "Whitlock"),
    ("Marlow", "Prosper"),
    ("Ashby", "Kingsley"),
    ("Linnea", "Ottilie"),
    ("Dispatches", "Pantheon"),
    ("Tales", "Scavengers"),
    ("turberas del sur", "quebradas del norte"),
    ("southern peatlands", "northern ravines"),
    ("faroles de queroseno", "cantimploras de cobre"),
    ("kerosene lanterns", "copper canteens"),
    (
        "dos mil ciento siete dividido por cincuenta y nueve",
        "dos mil cuatrocientos sesenta y tres dividido por setenta y uno",
    ),
    (
        "two thousand one hundred seven divided by fifty-nine",
        "two thousand four hundred sixty-three divided by seventy-one",
    ),
    (
        "dos mil one hundred seven divided by fifty-nine",
        "dos mil four hundred sixty-three divided by seventy-one",
    ),
    ("pierogi", "moussaka"),
    ("reloj de sol", "vitral del pasillo"),
    ("sundial", "hallway stained glass"),
    ("Candelaria", "Purificacion"),
    ("Eleuterio", "Segismundo"),
    ("Guadalupe", "Remedios"),
    ("Melquiades", "Nicomedes"),
    ("Fairbanks", "Ellsworth"),
    ("Rosalind", "Marigold"),
    ("Jacinta", "Estrella"),
    ("Yarrow", "Sorrel"),
    ("Praxedes", "Nicolasa"),
    ("Amaranta", "Consolacion"),
)


def _replace_token(text: str, old: str, new: str) -> str:
    return re.sub(rf"(?<!\w){re.escape(old)}(?!\w)", new, text, flags=re.IGNORECASE)


def _rewrite(text: str) -> str:
    rewritten = r27._rewrite(text)
    for old, new in _REPLACEMENTS:
        rewritten = _replace_token(rewritten, old, new)
    return rewritten


# Four instruction frames per language again, none of them used by R22-R25.
_REQUEST_PREFIXES = {
    "es": (
        "Despacha esta encomienda en el ordenador: ",
        "Anota este pedido para el equipo: ",
        "Da curso a esta solicitud en la computadora: ",
        "Aplica esta disposicion en el portatil: ",
    ),
    "en": (
        "Dispatch this assignment on the computer: ",
        "Log this order against the machine: ",
        "Give effect to this request on the PC: ",
        "Apply this provision on the laptop: ",
    ),
    "spanglish": (
        "Despacha esta assignment en el computer: ",
        "Anota este order para el equipo: ",
        "Give curso a esta solicitud en la machine: ",
        "Apply esta disposicion en el portatil: ",
    ),
}
# Denial frames, reworded again. These are the shape R25 lost six turns to: the
# body that follows may quote an order, and quoting one is not issuing one.
_CONVERSATION_PREFIXES = {
    "es": (
        "No despaches encomienda alguna en el ordenador, contestame nomas: ",
        "Ningun pedido va al equipo, solo dime: ",
        "Jamas seria una solicitud para la computadora, charlemos: ",
        "Nunca apliques disposicion en el portatil, respondeme y ya: ",
    ),
    "en": (
        "Do not dispatch any assignment on the computer, just answer me: ",
        "No order goes to the machine, only tell me: ",
        "This would never be a request for the PC, let us talk: ",
        "Never apply a provision on the laptop, answer me and that is all: ",
    ),
    "spanglish": (
        "No despaches assignment alguna en el computer, contestame nomas: ",
        "Ningun order va al equipo, solo dime: ",
        "Jamas seria una solicitud para la machine, charlemos: ",
        "Nunca apliques disposicion en el portatil, answer me y ya: ",
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
    random = Random(280028)
    rows: list[builder.Composition] = []
    for index in range(100):
        size = 2 + (index * 3 + 4) % 7
        language = languages[index % len(languages)]
        selected: tuple[str, ...] | None = None
        for _attempt in range(10_000):
            sequence = tuple(random.sample(operations, size))
            if sequence not in prior_sequences and sequence not in current:
                selected = sequence
                current.add(sequence)
                break
        if selected is None:
            raise RuntimeError(f"R28 could not derive novel composition {index}")
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        body = _BASE._composition_text(language, parts, index + 2801)
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
    builder.CAMPAIGN = "current-tree-r28"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-current-tree.r28"
    builder.PREREGISTRATION_SCHEMA = (
        "baxy.generalization-product-current-tree-preregistration.r28"
    )
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "post_r27_current_tree_unseen_paraphrases_with_enumerated_multi_note_"
        "authoring_modifiers_and_coordinated_ordinal_read_backs"
    )
    builder.REFERENCES = REFERENCES
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
