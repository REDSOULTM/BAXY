"""Prepare an unopened current-tree Cut-B population after R26.

R26 scored 668 of 688 and 18 of its 20 failures were one English word:
``petition``. Spanish ``peticion`` had been in the instruction-noun class for a
while; its cognate had not. That was the second seal lost to a noun entering on
one side of the language border alone, after R23 lost a whole Spanish cell to
``indicacion``.

Patching a word per seal is a treadmill, so the class stopped being a hand
list. It is now stated as cognate groups in
``effect_intent.INSTRUCTION_NOUN_COGNATES``/``MACHINE_NOUN_COGNATES``, no group
may have an empty side, and a test parses the C# parser and fails if the two
borders drift. This population exists to test that structure against frames it
has never seen -- including nouns the cognate groups admit but no previous
corpus ever used.

R26's use/mention repair is also re-tested here: the denial frames below wrap
bodies that quote orders, which is the shape R25 lost six turns to.
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
    build_generalization_product_current_tree_r26 as r26,
)
from scripts import build_generalization_product_holdout_r3 as builder  # noqa: E402
from scripts import build_generalization_product_holdout_r21 as r21  # noqa: E402
from scripts.build_generalization_surface_holdout import Scenario, Utterance  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/generalization_product_current_tree_r27.jsonl"
PREREGISTRATION = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r27.preregistration.json"
)
MIND_OUTPUT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r27_mind.json"
)
MIND_AUDIT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r27_mind.raw.jsonl"
)
MEMORY_TRX = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r27_memory.trx"
)
PRODUCT_OUTPUT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r27_product.json"
)
# R24 is absent on purpose: it was sealed but never opened, so nothing of it has
# been seen. R25 is present, because it was opened and spent.
PRIOR_CORPORA = (*r26.PRIOR_CORPORA, r26.OUTPUT)
POLICY_SOURCES = r26.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/"
    "probe_generalization_product_current_tree_r27.py",
    REPO / "experiments/mind_router_spike/"
    "analyze_generalization_product_current_tree_r27.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    *r26.BUILDER_DEPENDENCIES,
    Path(r26.__file__).resolve(),
)
REFERENCES = r26.REFERENCES


# Entities disjoint from R21 through R25.
_REPLACEMENTS = (
    ("Carpeta Índigo", "Carpeta Ocre"),
    ("Alder Folder", "Rowan Grove Folder"),
    ("entradas del acuario", "entradas del observatorio"),
    ("aquarium tickets", "observatory tickets"),
    ("Nicanora", "Filomena"),
    ("Anselmo", "Evaristo"),
    ("Blakely", "Thorne"),
    ("Verity", "Marlow"),
    ("Caldwell", "Ashby"),
    ("Isolde", "Linnea"),
    ("Utopia", "Dispatches"),
    ("Devs", "Tales"),
    ("bosques de niebla", "turberas del sur"),
    ("cloud forests", "southern peatlands"),
    ("hamacas de nailon", "faroles de queroseno"),
    ("nylon hammocks", "kerosene lanterns"),
    (
        "mil ochocientos cuarenta y nueve dividido por cuarenta y tres",
        "dos mil ciento siete dividido por cincuenta y nueve",
    ),
    (
        "one thousand eight hundred forty-nine divided by forty-three",
        "two thousand one hundred seven divided by fifty-nine",
    ),
    (
        "mil eight hundred forty-nine divided by forty-three",
        "dos mil one hundred seven divided by fifty-nine",
    ),
    ("ratatouille", "pierogi"),
    ("muro de musgo", "reloj de sol"),
    ("moss wall", "sundial"),
    ("Perpetua", "Candelaria"),
    ("Casimiro", "Eleuterio"),
    ("Maribel", "Guadalupe"),
    ("Baltasar", "Melquiades"),
    ("Winslow", "Fairbanks"),
    ("Emberly", "Rosalind"),
    ("Azucena", "Jacinta"),
    ("Bramble", "Yarrow"),
    ("Herminia", "Práxedes"),
    ("Soledad", "Amaranta"),
)


def _replace_token(text: str, old: str, new: str) -> str:
    return re.sub(rf"(?<!\w){re.escape(old)}(?!\w)", new, text, flags=re.IGNORECASE)


def _rewrite(text: str) -> str:
    rewritten = r26._rewrite(text)
    for old, new in _REPLACEMENTS:
        rewritten = _replace_token(rewritten, old, new)
    return rewritten


# Four instruction frames per language again, none of them used by R22-R25.
_REQUEST_PREFIXES = {
    "es": (
        "Esta encomienda es para el ordenador: ",
        "Tramita este mandato en la máquina: ",
        "Queda esta disposición para el equipo: ",
        "Sigue esta indicación en el portátil: ",
    ),
    "en": (
        "This assignment is for the computer: ",
        "Put this mandate through on the machine: ",
        "This provision stands for the PC: ",
        "Follow this direction on the laptop: ",
    ),
    "spanglish": (
        "Esta assignment es para el ordenador: ",
        "Tramita este mandate en la machine: ",
        "Queda esta provision para el equipo: ",
        "Follow esta indicación en el laptop: ",
    ),
}
# Denial frames, reworded again. These are the shape R25 lost six turns to: the
# body that follows may quote an order, and quoting one is not issuing one.
_CONVERSATION_PREFIXES = {
    "es": (
        "Ninguna encomienda para el ordenador, contéstame nomás: ",
        "No tramites mandato alguno en la máquina, sólo dime: ",
        "Jamás sería una disposición para el equipo, charlemos: ",
        "Nunca va una indicación al portátil, respóndeme y ya: ",
    ),
    "en": (
        "No assignment for the computer, just answer me: ",
        "Do not put any mandate through on the machine, only tell me: ",
        "This would never be a provision for the PC, let us talk: ",
        "No direction ever goes to the laptop, answer me and that is all: ",
    ),
    "spanglish": (
        "Ninguna assignment para el ordenador, contéstame nomás: ",
        "No tramites mandate alguno en la machine, sólo dime: ",
        "Jamás sería una provision para el equipo, charlemos: ",
        "Nunca va una indicación al laptop, answer me y ya: ",
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
    random = Random(270027)
    rows: list[builder.Composition] = []
    for index in range(100):
        size = 2 + (index * 4 + 2) % 7
        language = languages[index % len(languages)]
        selected: tuple[str, ...] | None = None
        for _attempt in range(10_000):
            sequence = tuple(random.sample(operations, size))
            if sequence not in prior_sequences and sequence not in current:
                selected = sequence
                current.add(sequence)
                break
        if selected is None:
            raise RuntimeError(f"R27 could not derive novel composition {index}")
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        body = _BASE._composition_text(language, parts, index + 2701)
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
    builder.CAMPAIGN = "current-tree-r27"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-current-tree.r27"
    builder.PREREGISTRATION_SCHEMA = (
        "baxy.generalization-product-current-tree-preregistration.r27"
    )
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "post_r26_current_tree_unseen_paraphrases_with_cognate_generated_"
        "instruction_and_denial_frames_never_used_by_any_prior_corpus"
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
