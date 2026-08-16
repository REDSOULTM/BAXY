"""Build and preregister BAXY's execution-inert R20 blind product holdout.

R20 certifies the post-R19 reminder repair on a fresh balanced population. It
changes entities, transparent request frames, addressed surfaces, and the
standard composition orders, with zero normalized overlap allowed against
R7-R19.
"""

from __future__ import annotations

import json
import re
import sys
from math import gcd
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts import build_generalization_product_holdout_r3 as builder  # noqa: E402
from scripts import build_generalization_product_holdout_r19 as r19  # noqa: E402
from scripts.build_generalization_surface_holdout import (  # noqa: E402
    Scenario,
    Utterance,
)


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v20.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v20.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r20_mind.json"
MIND_AUDIT = (
    REPO / "artifacts/holdout/generalization_product_holdout_r20_mind.raw.jsonl"
)
MEMORY_TRX = REPO / "artifacts/holdout/generalization_product_holdout_r20_memory.trx"
PRODUCT_OUTPUT = (
    REPO / "artifacts/holdout/generalization_product_holdout_r20_product.json"
)
PRIOR_CORPORA = (*r19.PRIOR_CORPORA, r19.OUTPUT)
POLICY_SOURCES = r19.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r20.py",
    REPO
    / "experiments/mind_router_spike/analyze_generalization_product_holdout_r20.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    *r19.BUILDER_DEPENDENCIES,
    REPO / "scripts/build_generalization_product_holdout_r19.py",
)
REFERENCES = r19.REFERENCES


_REPLACEMENTS = (
    ("Carpeta Índigo", "Carpeta Cobalto"),
    ("Willow Folder", "Maple Folder"),
    ("entradas del museo", "entradas del planetario"),
    ("museum tickets", "planetarium tickets"),
    ("Adriana", "Valentina"),
    ("Sergio", "Tomás"),
    ("Alex", "Morgan"),
    ("Hayden", "Quinn"),
    ("Finley", "Avery"),
    ("Rowan", "Parker"),
    ("The Bear", "Severance"),
    ("Andor", "Silo"),
    ("oasis del desierto", "bosques de niebla"),
    ("desert oases", "cloud forests"),
    ("cargadores solares portátiles", "purificadores de agua portátiles"),
    ("portable solar chargers", "portable water purifiers"),
    (
        "setecientos tres dividido por treinta y siete",
        "ochocientos cuarenta y uno dividido por veintinueve",
    ),
    (
        "seven hundred three divided by thirty-seven",
        "eight hundred forty-one divided by twenty-nine",
    ),
    (
        "setecientos three divided by thirty-seven",
        "ochocientos forty-one divided by twenty-nine",
    ),
    ("shakshuka", "okonomiyaki"),
    ("biblioteca otoñal", "observatorio de primavera"),
    ("autumn library", "spring observatory"),
    ("Rosa", "Elena"),
    ("Felipe", "Javier"),
    ("Carolina", "Mariana"),
    ("Nicolás", "Sebastián"),
    ("Logan", "Casey"),
    ("Harper", "Jordan"),
    ("Kendall", "Taylor"),
    ("Emerson", "Dakota"),
    ("Clara", "Lucía"),
    ("Patricia", "Teresa"),
)


def _replace_token(text: str, old: str, new: str) -> str:
    return re.sub(
        rf"(?<!\w){re.escape(old)}(?!\w)",
        new,
        text,
        flags=re.IGNORECASE,
    )


def _rewrite(text: str) -> str:
    rewritten = r19._rewrite(text)
    for old, new in _REPLACEMENTS:
        rewritten = _replace_token(rewritten, old, new)
    return rewritten


def _request_utterance(value: Utterance, index: int) -> Utterance:
    prefixes = {
        "es": (
            "Esta vez necesito una acción concreta en este equipo: ",
            "Encárgate en el computador de esto: ",
        ),
        "en": (
            "On this computer, carry out this specific request: ",
            "I need this done locally on the PC: ",
        ),
        "spanglish": (
            "Haz this concrete action en este computador: ",
            "On this PC, encárgate de esto: ",
        ),
    }
    body = _rewrite(value.text)
    body = body[:1].lower() + body[1:]
    return Utterance(value.language, prefixes[value.language][index % 2] + body)


def _conversation_utterance(value: Utterance, index: int) -> Utterance:
    markers = {
        "es": (
            "Sin pedir ningún cambio en el computador, quiero preguntarte: ",
            "Sólo conversemos; no hagas nada en este equipo: ",
        ),
        "en": (
            "Let's only discuss this; do not change anything on the computer: ",
            "This is conversation only, with no PC action requested: ",
        ),
        "spanglish": (
            "Solo let's talk; no hagas any PC action: ",
            "Conversation only, sin cambiar nada en este equipo: ",
        ),
    }
    return Utterance(
        value.language,
        markers[value.language][index % 2] + _rewrite(value.text),
    )


_BASE = r19.r18.r17.r16.r7
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
    operation: {language: _rewrite(part) for language, part in language_parts.items()}
    for operation, language_parts in _BASE.COMPOSITION_PARTS.items()
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
    steps = tuple(
        step for step in range(2, len(operations)) if gcd(step, len(operations)) == 1
    )
    prior_sequences = _prior_composition_sequences()
    current: set[tuple[str, ...]] = set()
    languages = ("es", "en", "spanglish")
    rows: list[builder.Composition] = []
    for index in range(94):
        size = 2 + (index * 5 + 4) % 7
        language = languages[index % len(languages)]
        selected: tuple[str, ...] | None = None
        for attempt in range(len(operations) * len(steps)):
            step = steps[(index * 47 + attempt // len(operations) + 37) % len(steps)]
            cursor = (index * 67 + attempt * 29 + 61) % len(operations)
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
            raise RuntimeError(f"R20 could not derive novel composition {index}")
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        base = _BASE._composition_text(language, parts, index + 823)
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
            Utterance("spanglish", "Capture this screen y transcribe all words from that same image"),
            0,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe"),
        _request_utterance(
            Utterance("es", "Obtén una imagen de esta pantalla y describe visualmente esa misma captura"),
            1,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe", "ocr.read"),
        _request_utterance(
            Utterance("en", "Capture this desktop, explain that image, and transcribe the text from it"),
            2,
        ),
    ),
    builder.Composition(
        ("message.recipient.resolve", "message.send", "reminder.list"),
        _request_utterance(
            Utterance("spanglish", "Send Lucía on WhatsApp que llegaré en media hora y then show scheduled reminders"),
            3,
        ),
    ),
    builder.Composition(
        ("note.list", "capture.screenshot", "vision.describe"),
        _request_utterance(
            Utterance("es", "Muestra mis notas, captura ese resultado y describe lo que aparece en la imagen"),
            4,
        ),
    ),
    builder.Composition(
        ("task.list", "system.time", "system.status", "system.process.list"),
        _request_utterance(
            Utterance("en", "List open tasks, tell me the time, check system health, and list running processes"),
            5,
        ),
    ),
)
COMPOSITIONS = _generated_compositions() + SPECIAL_COMPOSITIONS
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
    builder.CAMPAIGN = "r20"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-holdout.v20"
    builder.PREREGISTRATION_SCHEMA = "baxy.generalization-product-preregistration.v20"
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "post_r19_reminder_repair_fresh_entities_frames_"
        "and_composition_orders_absent_from_r7_r19"
    )
    builder.REFERENCES = REFERENCES
    builder.ADDRESSED_PREFIXES = {
        "es": "Baxy, atiende este pedido: ",
        "en": "Baxy, take care of this request: ",
        "spanglish": "Baxy, handle este pedido: ",
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
