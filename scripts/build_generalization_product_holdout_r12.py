"""Build and preregister BAXY's execution-inert R12 blind product holdout.

R12 is the clean confirmation campaign after the discourse-envelope and
destructive-memory ambiguity repairs. It keeps the 700-case R7 distribution,
but uses fresh entities, request and question envelopes, addressed surfaces,
and 94 generic composition orders absent from R7-R11. No normalized request
may overlap an earlier product holdout.
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
from scripts.build_generalization_surface_holdout import (  # noqa: E402
    Scenario,
    Utterance,
)


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v12.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v12.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r12_mind.json"
MIND_AUDIT = REPO / "artifacts/holdout/generalization_product_holdout_r12_mind.raw.jsonl"
MEMORY_TRX = REPO / "artifacts/holdout/generalization_product_holdout_r12_memory.trx"
PRODUCT_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r12_product.json"
PRIOR_CORPORA = (*r11.PRIOR_CORPORA, r11.OUTPUT)
POLICY_SOURCES = r11.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r12.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r12.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    *r11.BUILDER_DEPENDENCIES,
    REPO / "scripts/build_generalization_product_holdout_r11.py",
)
REFERENCES = r11.REFERENCES


_REPLACEMENTS = (
    ("Spotify", "Audacity"),
    ("VLC", "GIMP"),
    ("Carpeta Horizonte", "Carpeta Mirador"),
    ("Horizon Folder", "Harbor Folder"),
    ("recibos del hospedaje", "boletos del museo"),
    ("hotel receipts", "museum tickets"),
    ("Camila", "Renata"),
    ("Joaquín", "Matías"),
    ("Morgan", "Riley"),
    ("Reese", "Sawyer"),
    ("Taylor", "Jamie"),
    ("Casey", "Drew"),
    ("Dark", "Severance"),
    ("Silo", "Andor"),
    ("ajolotes mexicanos", "flamencos del Atacama"),
    ("Mexican axolotls", "Atacama flamingos"),
    ("filtros portátiles de agua", "cargadores solares compactos"),
    ("portable water filters", "compact solar chargers"),
    (
        "ciento noventa y ocho dividido por dieciocho",
        "doscientos veinticinco dividido por quince",
    ),
    (
        "one hundred ninety-eight divided by eighteen",
        "two hundred twenty-five divided by fifteen",
    ),
    (
        "ciento ninety-eight divided by eighteen",
        "doscientos twenty-five divided by fifteen",
    ),
    ("ramen", "risotto"),
    ("tarde lluviosa", "mañana ventosa"),
    ("rainy afternoon", "windy morning"),
    ("Maite", "Elisa"),
    ("Benjamín", "Facundo"),
    ("Florencia", "Agustina"),
    ("Baltazar", "Nicolás"),
    ("Emerson", "Kendall"),
    ("Dakota", "Harper"),
    ("Peyton", "Logan"),
    ("Cameron", "Sydney"),
    ("Jordan", "Ari"),
    ("Valentina", "Catalina"),
)


def _replace_token(text: str, old: str, new: str) -> str:
    return re.sub(
        rf"(?<!\w){re.escape(old)}(?!\w)",
        new,
        text,
        flags=re.IGNORECASE,
    )


def _rewrite(text: str) -> str:
    rewritten = r11._rewrite(text)
    for old, new in _REPLACEMENTS:
        rewritten = _replace_token(rewritten, old, new)
    return rewritten


def _request_utterance(value: Utterance, index: int) -> Utterance:
    prefixes = {
        "es": ("Cuando tengas un rato, ", "Una solicitud breve: "),
        "en": ("When you get a chance, ", "A small request: "),
        "spanglish": ("Cuando tengas un rato, please ", "A small request, porfa: "),
    }
    body = _rewrite(value.text)
    body = body[:1].lower() + body[1:]
    return Utterance(value.language, prefixes[value.language][index % 2] + body)


def _conversation_utterance(value: Utterance, index: int) -> Utterance:
    markers = {
        "es": ("Una consulta breve: ", "Una pregunta simple: "),
        "en": ("A brief question: ", "One small question: "),
        "spanglish": ("Una consulta breve: ", "One small question: "),
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
        )
    }
    current: set[tuple[str, ...]] = set()
    languages = ("spanglish", "es", "en")
    rows: list[builder.Composition] = []
    for index in range(94):
        size = 2 + (index * 5 + 4) % 7
        language = languages[index % len(languages)]
        selected: tuple[str, ...] | None = None
        for attempt in range(len(operations) * len(steps)):
            step = steps[(index * 11 + attempt // len(operations) + 5) % len(steps)]
            cursor = (index * 23 + attempt * 13 + 7) % len(operations)
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
            raise RuntimeError(f"R12 could not derive novel composition {index}")
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        base = r7._composition_text(language, parts, index + 137)
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
            Utterance("spanglish", "Capture la pantalla y read every visible word from that exact image"),
            0,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe"),
        _request_utterance(
            Utterance("es", "Toma una captura del escritorio y describe lo que aparece en esa misma imagen"),
            1,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe", "ocr.read"),
        _request_utterance(
            Utterance("en", "Capture the screen, describe that scene, and transcribe the words in the same image"),
            2,
        ),
    ),
    builder.Composition(
        ("message.recipient.resolve", "message.send", "task.list"),
        _request_utterance(
            Utterance("spanglish", "Tell Ari por WhatsApp que llego en twenty minutes, then show mis tareas abiertas"),
            3,
        ),
    ),
    builder.Composition(
        ("task.list", "capture.screenshot", "ocr.read"),
        _request_utterance(
            Utterance("es", "Enumera mis tareas abiertas, captura el resultado y transcribe el texto de esa captura"),
            4,
        ),
    ),
    builder.Composition(
        ("calendar.event.list", "capture.screenshot", "vision.describe", "clipboard.read.text"),
        _request_utterance(
            Utterance("en", "Show tomorrow's events, capture that view, describe the image, then read the clipboard text"),
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
    builder.CAMPAIGN = "r12"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-holdout.v12"
    builder.PREREGISTRATION_SCHEMA = "baxy.generalization-product-preregistration.v12"
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "r7_distribution_with_fresh_entities_new_availability_and_meta_request_"
        "envelopes_layered_addressing_and_generic_orders_absent_from_r7_r11"
    )
    builder.REFERENCES = REFERENCES
    builder.ADDRESSED_PREFIXES = {
        "es": "Mira, Baxy: ",
        "en": "Look, Baxy: ",
        "spanglish": "Escucha, Baxy: ",
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
