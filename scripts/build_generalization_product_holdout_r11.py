"""Build and preregister BAXY's execution-inert R11 blind product holdout.

R11 is the fresh confirmation campaign after the Q4 GPU promotion, the CPU
deadline repair, and the memory-parser repair exposed by R10. It preserves the
700-case public distribution while changing request and conversation
envelopes, entities, addressed surfaces, and every generic composition order.
No R11 row may overlap an earlier product holdout after normalization.
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
from scripts.build_generalization_surface_holdout import (  # noqa: E402
    Scenario,
    Utterance,
)


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v11.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v11.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r11_mind.json"
MIND_AUDIT = REPO / "artifacts/holdout/generalization_product_holdout_r11_mind.raw.jsonl"
MEMORY_TRX = REPO / "artifacts/holdout/generalization_product_holdout_r11_memory.trx"
PRODUCT_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r11_product.json"
PRIOR_CORPORA = (*r10.PRIOR_CORPORA, r10.OUTPUT)
POLICY_SOURCES = r10.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r11.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r11.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    REPO / "scripts/build_generalization_product_holdout_r10.py",
    REPO / "scripts/build_generalization_product_holdout_r9.py",
    REPO / "scripts/build_generalization_product_holdout_r8.py",
    REPO / "scripts/build_generalization_product_holdout_r7.py",
    REPO / "scripts/build_generalization_product_holdout_r3.py",
    REPO / "scripts/build_generalization_surface_holdout.py",
)
REFERENCES = r10.REFERENCES


_REPLACEMENTS = (
    ("Krita", "Spotify"),
    ("7-Zip", "VLC"),
    ("Plan Boreal", "Carpeta Horizonte"),
    ("Boreal Plan", "Horizon Folder"),
    ("pases de tren", "recibos del hospedaje"),
    ("train passes", "hotel receipts"),
    ("Paula", "Camila"),
    ("Martín", "Joaquín"),
    ("Quinn", "Morgan"),
    ("Parker", "Reese"),
    ("River", "Taylor"),
    ("Skyler", "Casey"),
    ("Arcane", "Dark"),
    ("The Good Place", "Silo"),
    ("mariposas monarca", "ajolotes mexicanos"),
    ("monarch butterflies", "Mexican axolotls"),
    ("molinos manuales de café", "filtros portátiles de agua"),
    ("manual coffee grinders", "portable water filters"),
    ("ciento veintisiete dividido por siete", "ciento noventa y ocho dividido por dieciocho"),
    ("one hundred twenty-seven divided by seven", "one hundred ninety-eight divided by eighteen"),
    ("ciento twenty-seven divided by seven", "ciento ninety-eight divided by eighteen"),
    ("sopa", "ramen"),
    ("soup", "ramen"),
    ("noche fría", "tarde lluviosa"),
    ("cold evening", "rainy afternoon"),
    ("Rocío", "Maite"),
    ("Luciano", "Benjamín"),
    ("Abril", "Florencia"),
    ("Thiago", "Baltazar"),
    ("Rowan", "Emerson"),
    ("Hayden", "Dakota"),
    ("Finley", "Peyton"),
    ("Blair", "Cameron"),
    ("Alex", "Jordan"),
    ("Julia", "Valentina"),
)


def _replace_token(text: str, old: str, new: str) -> str:
    return re.sub(
        rf"(?<!\w){re.escape(old)}(?!\w)",
        new,
        text,
        flags=re.IGNORECASE,
    )


def _rewrite(text: str) -> str:
    rewritten = text.replace("Pass Lee the update", "Pass Avery the update")
    for old, new in _REPLACEMENTS:
        rewritten = _replace_token(rewritten, old, new)
    if re.search(r"\b(?:avery|jordan|peyton)\s+el\s+message\b", rewritten, re.I):
        raise RuntimeError("R11 entity replacement corrupted an action verb")
    return rewritten


def _request_utterance(value: Utterance, index: int) -> Utterance:
    prefixes = {
        "es": ("Cuando puedas, ", "Una petición rápida: "),
        "en": ("When you have a moment, ", "One quick request: "),
        "spanglish": ("Cuando puedas, please ", "One quick request, porfa: "),
    }
    body = _rewrite(value.text)
    body = body[:1].lower() + body[1:]
    return Utterance(
        value.language,
        prefixes[value.language][index % 2] + body,
    )


def _conversation_utterance(value: Utterance, index: int) -> Utterance:
    markers = {
        "es": ("A propósito: ", "Tengo una pregunta: "),
        "en": ("One thing: ", "I was wondering: "),
        "spanglish": ("A propósito: ", "I was wondering: "),
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
        )
    }
    current: set[tuple[str, ...]] = set()
    languages = ("en", "spanglish", "es")
    rows: list[builder.Composition] = []
    for index in range(94):
        size = 3 + (index * 7 + 5) % 6
        language = languages[index % len(languages)]
        selected: tuple[str, ...] | None = None
        for attempt in range(len(operations) * len(steps)):
            step = steps[(index * 7 + attempt // len(operations) + 3) % len(steps)]
            cursor = (index * 17 + attempt * 11 + 5) % len(operations)
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
            raise RuntimeError(f"R11 could not derive novel composition {index}")
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        base = r7._composition_text(language, parts, index + 83)
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
            Utterance("es", "Guarda una captura y extrae de esa misma imagen las palabras visibles"),
            0,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe"),
        _request_utterance(
            Utterance("en", "Capture the desktop and describe the scene shown in that same image"),
            1,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe", "ocr.read"),
        _request_utterance(
            Utterance("spanglish", "Capture la pantalla, describe that scene y transcribe también its visible text"),
            2,
        ),
    ),
    builder.Composition(
        ("message.recipient.resolve", "message.send", "task.list"),
        _request_utterance(
            Utterance("en", "Tell Jordan on WhatsApp that I will be there in fifteen, then list my open tasks"),
            3,
        ),
    ),
    builder.Composition(
        ("task.list", "capture.screenshot", "ocr.read"),
        _request_utterance(
            Utterance("es", "Muestra las tareas abiertas, captura la pantalla y lee el texto de esa captura"),
            4,
        ),
    ),
    builder.Composition(
        ("calendar.event.list", "capture.screenshot", "vision.describe", "clipboard.read.text"),
        _request_utterance(
            Utterance("spanglish", "Show mañana's calendar, capture that view, describe la imagen y read the clipboard text"),
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
    builder.CAMPAIGN = "r11"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-holdout.v11"
    builder.PREREGISTRATION_SCHEMA = "baxy.generalization-product-preregistration.v11"
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "r7_distribution_with_new_entities_new_request_and_discourse_envelopes_"
        "new_addressed_surfaces_and_generic_orders_absent_from_r7_r10"
    )
    builder.REFERENCES = REFERENCES
    builder.ADDRESSED_PREFIXES = {
        "es": "Baxy, escucha: ",
        "en": "Baxy, listen: ",
        "spanglish": "Baxy, mira: ",
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
