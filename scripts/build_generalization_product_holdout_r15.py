"""Build and preregister BAXY's execution-inert R15 blind product holdout.

R15 independently confirms the discourse-envelope, installed-inventory, and
dependent-read repairs found after R14. It preserves the 700-case distribution
while changing entities, wrappers, addressed surfaces, and all 94 generic
composition orders. No normalized request may overlap R7-R14.
"""

from __future__ import annotations

import re
import sys
from math import gcd
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts import build_generalization_product_holdout_r3 as builder  # noqa: E402
from scripts import build_generalization_product_holdout_r7 as r7  # noqa: E402
from scripts import build_generalization_product_holdout_r8 as r8  # noqa: E402
from scripts import build_generalization_product_holdout_r9 as r9  # noqa: E402
from scripts import build_generalization_product_holdout_r10 as r10  # noqa: E402
from scripts import build_generalization_product_holdout_r11 as r11  # noqa: E402
from scripts import build_generalization_product_holdout_r12 as r12  # noqa: E402
from scripts import build_generalization_product_holdout_r13 as r13  # noqa: E402
from scripts import build_generalization_product_holdout_r14 as r14  # noqa: E402
from scripts.build_generalization_surface_holdout import (  # noqa: E402
    Scenario,
    Utterance,
)


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v15.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v15.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r15_mind.json"
MIND_AUDIT = REPO / "artifacts/holdout/generalization_product_holdout_r15_mind.raw.jsonl"
MEMORY_TRX = REPO / "artifacts/holdout/generalization_product_holdout_r15_memory.trx"
PRODUCT_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r15_product.json"
PRIOR_CORPORA = (*r14.PRIOR_CORPORA, r14.OUTPUT)
POLICY_SOURCES = r14.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r15.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r15.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    *r14.BUILDER_DEPENDENCIES,
    REPO / "scripts/build_generalization_product_holdout_r14.py",
)
REFERENCES = r14.REFERENCES


_REPLACEMENTS = (
    ("Krita", "Blender"),
    ("VLC media player", "7-Zip"),
    ("Carpeta Horizonte", "Carpeta Aurora"),
    ("Delta Folder", "Cedar Folder"),
    ("entradas del planetario", "pases del acuario"),
    ("planetarium tickets", "aquarium passes"),
    ("Verónica", "Paloma"),
    ("Germán", "Iñaki"),
    ("Morgan", "Dakota"),
    ("Avery", "Hayden"),
    ("Casey", "Finley"),
    ("Taylor", "Cameron"),
    ("Silo", "The Bear"),
    ("Dark", "Shogun"),
    ("vicuñas altiplánicas", "mariposas monarca"),
    ("highland vicuñas", "monarch butterflies"),
    ("radios compactas de manivela", "cafeteras portátiles de viaje"),
    ("compact hand-crank radios", "portable travel espresso makers"),
    (
        "trescientos veintitrés dividido por diecinueve",
        "trescientos noventa y uno dividido por veintitrés",
    ),
    (
        "three hundred twenty-three divided by nineteen",
        "three hundred ninety-one divided by twenty-three",
    ),
    (
        "trescientos twenty-three divided by nineteen",
        "trescientos ninety-one divided by twenty-three",
    ),
    ("paella", "ramen"),
    ("tarde lluviosa", "noche nevada"),
    ("rainy afternoon", "snowy night"),
    ("Lorena", "Clara"),
    ("Esteban", "Mauricio"),
    ("Amalia", "Florencia"),
    ("Benjamín", "Sebastián"),
    ("Jordan", "Reese"),
    ("Parker", "Skyler"),
    ("Rowan", "Devon"),
    ("Emerson", "Marley"),
    ("Vega", "Zoe"),
    ("Antonia", "Rocío"),
)


def _replace_token(text: str, old: str, new: str) -> str:
    return re.sub(
        rf"(?<!\w){re.escape(old)}(?!\w)",
        new,
        text,
        flags=re.IGNORECASE,
    )


def _rewrite(text: str) -> str:
    rewritten = r14._rewrite(text)
    for old, new in _REPLACEMENTS:
        rewritten = _replace_token(rewritten, old, new)
    return rewritten


def _request_utterance(value: Utterance, index: int) -> Utterance:
    prefixes = {
        "es": (
            "Por favor, cuando tengas un minuto, ",
            "A ver, una solicitud rápida: ",
        ),
        "en": (
            "Please, when you have a minute, ",
            "One small request: ",
        ),
        "spanglish": (
            "Porfa, when you have a minute, please ",
            "One small request, porfa: ",
        ),
    }
    body = _rewrite(value.text)
    body = body[:1].lower() + body[1:]
    return Utterance(value.language, prefixes[value.language][index % 2] + body)


def _conversation_utterance(value: Utterance, index: int) -> Utterance:
    markers = {
        "es": ("Una pregunta rápida: ", "Una consulta pequeña: "),
        "en": ("One quick question: ", "A small question: "),
        "spanglish": ("Una pregunta rápida: ", "A small question: "),
    }
    return Utterance(
        value.language,
        markers[value.language][index % 2] + _rewrite(value.text),
    )


SCENARIOS: dict[str, Scenario] = {
    family: Scenario(
        scenario.operations,
        tuple(
            _request_utterance(utterance, index)
            for index, utterance in enumerate(scenario.utterances)
        ),
    )
    for family, scenario in r7.SCENARIOS.items()
}
CLARIFICATIONS = Scenario(
    r7.CLARIFICATIONS.operations,
    tuple(
        _request_utterance(utterance, index)
        for index, utterance in enumerate(r7.CLARIFICATIONS.utterances)
    ),
)
COMPOSITION_PARTS = {
    operation: {
        language: _rewrite(part)
        for language, part in language_parts.items()
    }
    for operation, language_parts in r7.COMPOSITION_PARTS.items()
}


def _generated_compositions() -> tuple[builder.Composition, ...]:
    operations = tuple(COMPOSITION_PARTS)
    steps = tuple(
        step for step in range(2, len(operations)) if gcd(step, len(operations)) == 1
    )
    prior_sequences = {
        tuple(composition.operations)
        for composition in (
            *r7.COMPOSITIONS,
            *r8.COMPOSITIONS,
            *r9.COMPOSITIONS,
            *r10.COMPOSITIONS,
            *r11.COMPOSITIONS,
            *r12.COMPOSITIONS,
            *r13.COMPOSITIONS,
            *r14.COMPOSITIONS,
        )
    }
    current: set[tuple[str, ...]] = set()
    languages = ("es", "en", "spanglish")
    rows: list[builder.Composition] = []
    for index in range(94):
        size = 2 + (index * 2 + 1) % 7
        language = languages[(index + 2) % len(languages)]
        selected: tuple[str, ...] | None = None
        for attempt in range(len(operations) * len(steps)):
            step = steps[(index * 19 + attempt // len(operations) + 13) % len(steps)]
            cursor = (index * 37 + attempt * 23 + 29) % len(operations)
            candidate: list[str] = []
            while len(candidate) < size:
                operation = operations[cursor]
                if operation not in candidate:
                    candidate.append(operation)
                cursor = (cursor + step) % len(operations)
            sequence = tuple(candidate)
            if sequence not in prior_sequences and sequence not in current:
                selected = sequence
                current.add(sequence)
                break
        if selected is None:
            raise RuntimeError(f"R15 could not derive novel composition {index}")
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        base = r7._composition_text(language, parts, index + 331)
        rows.append(
            builder.Composition(
                selected,
                _request_utterance(Utterance(language, base), index),
            )
        )
    return tuple(rows)


SPECIAL_COMPOSITIONS = (
    builder.Composition(
        ("capture.screenshot", "ocr.read"),
        _request_utterance(
            Utterance(
                "spanglish",
                "Capture la pantalla y read every visible word from that exact image",
            ),
            0,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe"),
        _request_utterance(
            Utterance(
                "es",
                "Toma una captura del escritorio y describe lo que aparece en esa imagen",
            ),
            1,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe", "ocr.read"),
        _request_utterance(
            Utterance(
                "spanglish",
                "Capture the desktop, describe esa imagen y read every word visible in the same capture",
            ),
            2,
        ),
    ),
    builder.Composition(
        ("message.recipient.resolve", "message.send", "task.list"),
        _request_utterance(
            Utterance(
                "es",
                "Dile a Zoe por WhatsApp que llego en cuarenta minutos y luego lista mis tareas abiertas",
            ),
            3,
        ),
    ),
    builder.Composition(
        ("task.list", "capture.screenshot", "ocr.read"),
        _request_utterance(
            Utterance(
                "en",
                "Show my open tasks, capture that view, and extract the text from the capture",
            ),
            4,
        ),
    ),
    builder.Composition(
        (
            "calendar.event.list",
            "capture.screenshot",
            "vision.describe",
            "clipboard.read.text",
        ),
        _request_utterance(
            Utterance(
                "es",
                "Enséñame los eventos de mañana, toma una captura de esa vista, describe lo que aparece y después lee el texto del portapapeles",
            ),
            5,
        ),
    ),
)
COMPOSITIONS = _generated_compositions() + SPECIAL_COMPOSITIONS
CONVERSATIONS = tuple(
    _conversation_utterance(utterance, index)
    for index, utterance in enumerate(r7.CONVERSATIONS)
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
    builder.CAMPAIGN = "r15"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-holdout.v15"
    builder.PREREGISTRATION_SCHEMA = "baxy.generalization-product-preregistration.v15"
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "r7_distribution_with_fresh_entities_new_stacked_courtesy_and_small_request_"
        "envelopes_layered_addressing_and_generic_orders_absent_from_r7_r14"
    )
    builder.REFERENCES = REFERENCES
    builder.ADDRESSED_PREFIXES = {
        "es": "Oiga, Baxy: ",
        "en": "Listen, Baxy: ",
        "spanglish": "Che, Baxy: ",
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
