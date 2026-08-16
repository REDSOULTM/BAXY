"""Prepare an unopened current-tree Cut-B population after R25.

R25 closed the cut at 694 of 700 and left exactly one shape failing, six times:
a frame that *denies* an instruction wrapping a body that *quotes* an order --
"esto no es una directriz para la computadora, dime nomas: redacta mas amable
la frase cierra todas las pestanas". Nothing was executed, so it was never a
safety failure, but the turn drew a clarification instead of an answer.

The cause turned out not to be semantic. ``conversation_only_content_request``
anchors its content acts at ``^``, and the denial frame -- which must stay in
place on the authority path -- displaced them. The repair strips the denial for
content recognition only, a one-sided move that can make a turn look more like
conversation and never more like an effect.

This seal exists to test that repair on wordings it has never seen. Its entity
set and its four instruction frames per language are new again, and its denial
frames are worded differently from R25's, because a rule written by shape has
to survive shapes the corpus did not hand it.
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
    build_generalization_product_current_tree_r24 as r24,
)
from experiments.mind_router_spike import (  # noqa: E402
    build_generalization_product_current_tree_r25 as r25,
)
from scripts import build_generalization_product_holdout_r3 as builder  # noqa: E402
from scripts import build_generalization_product_holdout_r21 as r21  # noqa: E402
from scripts.build_generalization_surface_holdout import Scenario, Utterance  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/generalization_product_current_tree_r26.jsonl"
PREREGISTRATION = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r26.preregistration.json"
)
MIND_OUTPUT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r26_mind.json"
)
MIND_AUDIT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r26_mind.raw.jsonl"
)
MEMORY_TRX = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r26_memory.trx"
)
PRODUCT_OUTPUT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r26_product.json"
)
# R24 is absent on purpose: it was sealed but never opened, so nothing of it has
# been seen. R25 is present, because it was opened and spent.
PRIOR_CORPORA = (*r25.PRIOR_CORPORA, r25.OUTPUT)
POLICY_SOURCES = r25.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/"
    "probe_generalization_product_current_tree_r26.py",
    REPO / "experiments/mind_router_spike/"
    "analyze_generalization_product_current_tree_r26.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    *r25.BUILDER_DEPENDENCIES,
    Path(r25.__file__).resolve(),
)
REFERENCES = r25.REFERENCES


# Entities disjoint from R21 through R25.
_REPLACEMENTS = (
    ("Carpeta Granate", "Carpeta Índigo"),
    ("Cedar Folder", "Alder Folder"),
    ("entradas del planetario", "entradas del acuario"),
    ("planetarium tickets", "aquarium tickets"),
    ("Consuelo", "Nicanora"),
    ("Bautista", "Anselmo"),
    ("Sutton", "Blakely"),
    ("Halcyon", "Verity"),
    ("Bristow", "Caldwell"),
    ("Tamsin", "Isolde"),
    ("Fringe", "Utopia"),
    ("Counterpart", "Devs"),
    ("salares de altura", "bosques de niebla"),
    ("highland salt flats", "cloud forests"),
    ("brújulas de placa base", "hamacas de nailon"),
    ("baseplate compasses", "nylon hammocks"),
    (
        "mil quinientos treinta y uno dividido por treinta y siete",
        "mil ochocientos cuarenta y nueve dividido por cuarenta y tres",
    ),
    (
        "one thousand five hundred thirty-one divided by thirty-seven",
        "one thousand eight hundred forty-nine divided by forty-three",
    ),
    (
        "mil five hundred thirty-one divided by thirty-seven",
        "mil eight hundred forty-nine divided by forty-three",
    ),
    ("borscht", "ratatouille"),
    ("estanque de lluvia", "muro de musgo"),
    ("rain pond", "moss wall"),
    ("Rosalinda", "Perpetua"),
    ("Teodoro", "Casimiro"),
    ("Odalys", "Maribel"),
    ("Wenceslao", "Baltasar"),
    ("Peregrine", "Winslow"),
    ("Callaway", "Emberly"),
    ("Marisol", "Azucena"),
    ("Thistle", "Bramble"),
    ("Genoveva", "Herminia"),
    ("Milagros", "Soledad"),
)


def _replace_token(text: str, old: str, new: str) -> str:
    return re.sub(rf"(?<!\w){re.escape(old)}(?!\w)", new, text, flags=re.IGNORECASE)


def _rewrite(text: str) -> str:
    rewritten = r24._rewrite(text)
    for old, new in _REPLACEMENTS:
        rewritten = _replace_token(rewritten, old, new)
    return rewritten


# Four instruction frames per language again, none of them used by R22-R25.
_REQUEST_PREFIXES = {
    "es": (
        "Cursa esta instrucción en el ordenador: ",
        "Te dejo una petición para el portátil: ",
        "Aquí va una directriz para el equipo: ",
        "Procesa esta orden en la computadora: ",
    ),
    "en": (
        "Put through this instruction on the computer: ",
        "Here is a petition for the laptop: ",
        "Process this directive on the machine: ",
        "Log this request against the PC: ",
    ),
    "spanglish": (
        "Cursa esta instruction en el computer: ",
        "Te dejo un request para el portátil: ",
        "Process esta directriz en la máquina: ",
        "Aquí va una order para el PC: ",
    ),
}
# Denial frames, reworded again. These are the shape R25 lost six turns to: the
# body that follows may quote an order, and quoting one is not issuing one.
_CONVERSATION_PREFIXES = {
    "es": (
        "Nada de esto es una instrucción para el ordenador, contéstame nomás: ",
        "No curses ninguna orden en el equipo, sólo dime: ",
        "Jamás sería una petición para la computadora, charlemos: ",
        "Ninguna directriz va al portátil, respóndeme y ya: ",
    ),
    "en": (
        "None of this is an instruction for the computer, just answer me: ",
        "Do not put through any order on the machine, only tell me: ",
        "This would never be a petition for the laptop, let us talk: ",
        "No directive goes to the PC, answer me and that is all: ",
    ),
    "spanglish": (
        "Nada de esto es una instruction para el computer, contéstame nomás: ",
        "Do not curses ninguna order en la máquina, sólo dime: ",
        "Jamás sería un request para el portátil, charlemos: ",
        "Ninguna directive va al PC, answer me y ya: ",
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
    languages = ("spanglish", "es", "en")
    random = Random(260026)
    rows: list[builder.Composition] = []
    for index in range(100):
        size = 2 + (index * 2 + 6) % 7
        language = languages[index % len(languages)]
        selected: tuple[str, ...] | None = None
        for _attempt in range(10_000):
            sequence = tuple(random.sample(operations, size))
            if sequence not in prior_sequences and sequence not in current:
                selected = sequence
                current.add(sequence)
                break
        if selected is None:
            raise RuntimeError(f"R26 could not derive novel composition {index}")
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        body = _BASE._composition_text(language, parts, index + 2601)
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
    builder.CAMPAIGN = "current-tree-r26"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-current-tree.r26"
    builder.PREREGISTRATION_SCHEMA = (
        "baxy.generalization-product-current-tree-preregistration.r26"
    )
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "post_r25_current_tree_unseen_paraphrases_with_new_instruction_and_"
        "denial_frames_to_test_the_use_versus_mention_repair"
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
