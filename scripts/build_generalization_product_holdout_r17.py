"""Build and preregister BAXY's execution-inert R17 blind product holdout.

R17 certifies the current post-R50 policy with fresh entities, discourse
wrappers, and composition orders. It preserves R16's balanced 700-case product
distribution, and no normalized request may overlap any prior product holdout.
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
from scripts import build_generalization_product_holdout_r16 as r16  # noqa: E402
from scripts.build_generalization_surface_holdout import (  # noqa: E402
    Scenario,
    Utterance,
)


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v17.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v17.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r17_mind.json"
MIND_AUDIT = REPO / "artifacts/holdout/generalization_product_holdout_r17_mind.raw.jsonl"
MEMORY_TRX = REPO / "artifacts/holdout/generalization_product_holdout_r17_memory.trx"
PRODUCT_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r17_product.json"
PRIOR_CORPORA = (*r16.PRIOR_CORPORA, r16.OUTPUT)
POLICY_SOURCES = r16.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r17.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r17.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    *r16.BUILDER_DEPENDENCIES,
    REPO / "scripts/build_generalization_product_holdout_r16.py",
)
REFERENCES = r16.REFERENCES


_REPLACEMENTS = (
    ("Carpeta Bruma", "Carpeta Coral"),
    ("Birch Folder", "Maple Folder"),
    ("pases del observatorio", "pases del planetario"),
    ("observatory passes", "planetarium passes"),
    ("Nadia", "Teresa"),
    ("Óscar", "Julián"),
    ("Sage", "Robin"),
    ("Ellis", "Morgan"),
    ("Remy", "Avery"),
    ("Kerry", "Taylor"),
    ("Slow Horses", "Severance"),
    ("Ripley", "Silo"),
    ("ballenas azules", "arrecifes de coral"),
    ("blue whales", "coral reefs"),
    ("linternas compactas de campamento", "dispositivos GPS para senderismo"),
    ("compact camping lanterns", "trail GPS devices"),
    (
        "cuatrocientos treinta y siete dividido por veintitrés",
        "quinientos veintinueve dividido por veintitrés",
    ),
    (
        "four hundred thirty-seven divided by twenty-three",
        "five hundred twenty-nine divided by twenty-three",
    ),
    (
        "cuatrocientos thirty-seven divided by twenty-three",
        "quinientos twenty-nine divided by twenty-three",
    ),
    ("curry", "gnocchi"),
    ("amanecer con niebla", "puerto tranquilo"),
    ("foggy dawn", "quiet harbor"),
    ("Elena", "Lucía"),
    ("Rodrigo", "Tomás"),
    ("Daniela", "Valentina"),
    ("Martín", "Gabriel"),
    ("Lane", "Parker"),
    ("Wren", "Quinn"),
    ("Arden", "Casey"),
    ("Sidney", "Jordan"),
    ("Uma", "Iris"),
    ("Beatriz", "Mónica"),
)


def _replace_token(text: str, old: str, new: str) -> str:
    return re.sub(
        rf"(?<!\w){re.escape(old)}(?!\w)",
        new,
        text,
        flags=re.IGNORECASE,
    )


def _rewrite(text: str) -> str:
    rewritten = r16._rewrite(text)
    for old, new in _REPLACEMENTS:
        rewritten = _replace_token(rewritten, old, new)
    return rewritten


def _request_utterance(value: Utterance, index: int) -> Utterance:
    prefixes = {
        "es": (
            "Te dejo una instrucción concreta para este computador: ",
            "Necesito que hagas lo siguiente ahora: ",
        ),
        "en": (
            "Here's one concrete instruction for this computer: ",
            "Please handle the following on this PC now: ",
        ),
        "spanglish": (
            "Necesito this exact thing on this PC: ",
            "For este computador ahora, please ",
        ),
    }
    body = _rewrite(value.text)
    body = body[:1].lower() + body[1:]
    return Utterance(value.language, prefixes[value.language][index % 2] + body)


def _conversation_utterance(value: Utterance, index: int) -> Utterance:
    markers = {
        "es": (
            "Quiero preguntarte algo sin pedir una acción: ",
            "Tengo una duda breve, sólo para conversar: ",
        ),
        "en": (
            "Just a quick thought, with no computer action: ",
            "I have a short question, just to chat: ",
        ),
        "spanglish": (
            "Tengo una quick question, sin computer action: ",
            "Just para conversar, una duda breve: ",
        ),
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
    for family, scenario in r16.r7.SCENARIOS.items()
}
CLARIFICATIONS = Scenario(
    r16.r7.CLARIFICATIONS.operations,
    tuple(
        _request_utterance(utterance, index)
        for index, utterance in enumerate(r16.r7.CLARIFICATIONS.utterances)
    ),
)
COMPOSITION_PARTS = {
    operation: {
        language: _rewrite(part)
        for language, part in language_parts.items()
    }
    for operation, language_parts in r16.r7.COMPOSITION_PARTS.items()
}


def _generated_compositions() -> tuple[builder.Composition, ...]:
    operations = tuple(COMPOSITION_PARTS)
    steps = tuple(
        step for step in range(2, len(operations)) if gcd(step, len(operations)) == 1
    )
    prior_sequences = {
        tuple(composition.operations)
        for composition in (
            *r16.r7.COMPOSITIONS,
            *r16.r8.COMPOSITIONS,
            *r16.r9.COMPOSITIONS,
            *r16.r10.COMPOSITIONS,
            *r16.r11.COMPOSITIONS,
            *r16.r12.COMPOSITIONS,
            *r16.r13.COMPOSITIONS,
            *r16.r14.COMPOSITIONS,
            *r16.r15.COMPOSITIONS,
            *r16.COMPOSITIONS,
        )
    }
    current: set[tuple[str, ...]] = set()
    languages = ("es", "en", "spanglish")
    rows: list[builder.Composition] = []
    for index in range(94):
        size = 2 + (index * 5 + 4) % 7
        language = languages[(index + 1) % len(languages)]
        selected: tuple[str, ...] | None = None
        for attempt in range(len(operations) * len(steps)):
            step = steps[(index * 31 + attempt // len(operations) + 23) % len(steps)]
            cursor = (index * 47 + attempt * 37 + 43) % len(operations)
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
            raise RuntimeError(f"R17 could not derive novel composition {index}")
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        base = r16.r7._composition_text(language, parts, index + 521)
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
            Utterance("es", "Toma una captura y extrae todo el texto de esa misma imagen"),
            0,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe"),
        _request_utterance(
            Utterance("en", "Take a screenshot and describe that exact image"),
            1,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe", "ocr.read"),
        _request_utterance(
            Utterance(
                "spanglish",
                "Captura la pantalla, describe that image y read every word from the same capture",
            ),
            2,
        ),
    ),
    builder.Composition(
        ("message.recipient.resolve", "message.send", "note.list"),
        _request_utterance(
            Utterance(
                "es",
                "Avísale a Iris por WhatsApp que llegaré en cuarenta minutos y después lista mis notas",
            ),
            3,
        ),
    ),
    builder.Composition(
        ("note.list", "capture.screenshot", "ocr.read"),
        _request_utterance(
            Utterance(
                "en",
                "Show my notes, capture that view, and read the text from the capture",
            ),
            4,
        ),
    ),
    builder.Composition(
        (
            "system.time",
            "system.status",
            "system.process.list",
            "task.list",
        ),
        _request_utterance(
            Utterance(
                "spanglish",
                "Dime la hora, check system status, lista los procesos y luego show my open tasks",
            ),
            5,
        ),
    ),
)
COMPOSITIONS = _generated_compositions() + SPECIAL_COMPOSITIONS
CONVERSATIONS = tuple(
    _conversation_utterance(utterance, index)
    for index, utterance in enumerate(r16.r7.CONVERSATIONS)
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
    builder.CAMPAIGN = "r17"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-holdout.v17"
    builder.PREREGISTRATION_SCHEMA = "baxy.generalization-product-preregistration.v17"
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "r16_distribution_with_fresh_entities_explicit_local_wrappers_"
        "and_generic_orders_absent_from_r7_r16"
    )
    builder.REFERENCES = REFERENCES
    builder.ADDRESSED_PREFIXES = {
        "es": "Baxy, atiende esto: ",
        "en": "Baxy, handle this: ",
        "spanglish": "Baxy, haz this: ",
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
