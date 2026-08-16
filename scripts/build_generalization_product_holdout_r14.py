"""Build and preregister BAXY's execution-inert R14 blind product holdout.

R14 confirms the post-R13 presentation fixes on a fresh population. It keeps
the 700-case product distribution and primitive family coverage while changing
entities, discourse envelopes, addressed surfaces, and all 94 generic
composition orders. No normalized request may overlap R7-R13.
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
from scripts.build_generalization_surface_holdout import (  # noqa: E402
    Scenario,
    Utterance,
)


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v14.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v14.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r14_mind.json"
MIND_AUDIT = REPO / "artifacts/holdout/generalization_product_holdout_r14_mind.raw.jsonl"
MEMORY_TRX = REPO / "artifacts/holdout/generalization_product_holdout_r14_memory.trx"
PRODUCT_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r14_product.json"
PRIOR_CORPORA = (*r13.PRIOR_CORPORA, r13.OUTPUT)
POLICY_SOURCES = r13.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r14.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r14.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    *r13.BUILDER_DEPENDENCIES,
    REPO / "scripts/build_generalization_product_holdout_r13.py",
)
REFERENCES = (
    *r13.REFERENCES,
    "https://arxiv.org/abs/1912.09713",
    "https://aclanthology.org/2020.emnlp-main.731/",
    "https://aclanthology.org/2023.emnlp-main.194/",
)


_REPLACEMENTS = (
    ("Inkscape", "Krita"),
    ("Notepad++", "VLC media player"),
    ("Carpeta Estuario", "Carpeta Horizonte"),
    ("Lagoon Folder", "Delta Folder"),
    ("pases del festival", "entradas del planetario"),
    ("festival passes", "planetarium tickets"),
    ("Solange", "Verónica"),
    ("Tomás", "Germán"),
    ("Bailey", "Morgan"),
    ("Reagan", "Avery"),
    ("Robin", "Casey"),
    ("Blake", "Taylor"),
    ("Foundation", "Silo"),
    ("Mr Robot", "Dark"),
    ("pingüinos patagónicos", "vicuñas altiplánicas"),
    ("Patagonian penguins", "highland vicuñas"),
    ("hervidores de viaje plegables", "radios compactas de manivela"),
    ("foldable travel kettles", "compact hand-crank radios"),
    (
        "doscientos setenta y dos dividido por diecisiete",
        "trescientos veintitrés dividido por diecinueve",
    ),
    (
        "two hundred seventy-two divided by seventeen",
        "three hundred twenty-three divided by nineteen",
    ),
    (
        "doscientos seventy-two divided by seventeen",
        "trescientos twenty-three divided by nineteen",
    ),
    ("gnocchi", "paella"),
    ("tarde soleada", "tarde lluviosa"),
    ("sunny evening", "rainy afternoon"),
    ("Mara", "Lorena"),
    ("Ramiro", "Esteban"),
    ("Josefina", "Amalia"),
    ("Lautaro", "Benjamín"),
    ("Quincy", "Jordan"),
    ("Shannon", "Parker"),
    ("Carter", "Rowan"),
    ("Leslie", "Emerson"),
    ("Noa", "Vega"),
    ("Magdalena", "Antonia"),
)


def _replace_token(text: str, old: str, new: str) -> str:
    return re.sub(
        rf"(?<!\w){re.escape(old)}(?!\w)",
        new,
        text,
        flags=re.IGNORECASE,
    )


def _rewrite(text: str) -> str:
    rewritten = r13._rewrite(text)
    for old, new in _REPLACEMENTS:
        rewritten = _replace_token(rewritten, old, new)
    return rewritten


def _request_utterance(value: Utterance, index: int) -> Utterance:
    prefixes = {
        "es": ("Cuando te quede bien, ", "Una solicitud rápida: "),
        "en": ("When you have a minute, ", "A quick request: "),
        "spanglish": (
            "Cuando tengas un minuto, please ",
            "A quick request, por favor: ",
        ),
    }
    body = _rewrite(value.text)
    body = body[:1].lower() + body[1:]
    return Utterance(value.language, prefixes[value.language][index % 2] + body)


def _conversation_utterance(value: Utterance, index: int) -> Utterance:
    markers = {
        "es": ("Una consulta rápida: ", "Una pregunta pequeña: "),
        "en": ("A quick question: ", "One simple question: "),
        "spanglish": ("Una consulta rápida: ", "One simple question: "),
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
            step = steps[(index * 17 + attempt // len(operations) + 11) % len(steps)]
            cursor = (index * 31 + attempt * 19 + 23) % len(operations)
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
            raise RuntimeError(f"R14 could not derive novel composition {index}")
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        base = r7._composition_text(language, parts, index + 257)
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
                "es",
                "Toma una captura de la pantalla y extrae las palabras visibles de esa imagen",
            ),
            0,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe"),
        _request_utterance(
            Utterance(
                "en",
                "Take a screenshot of the desktop and describe what appears in that captured image",
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
                "en",
                "Tell Vega on WhatsApp that I arrive in thirty-five minutes, then list my open tasks",
            ),
            3,
        ),
    ),
    builder.Composition(
        ("task.list", "capture.screenshot", "ocr.read"),
        _request_utterance(
            Utterance(
                "es",
                "Muestra mis tareas abiertas, captura esa vista y extrae el texto de la captura",
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
    builder.CAMPAIGN = "r14"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-holdout.v14"
    builder.PREREGISTRATION_SCHEMA = "baxy.generalization-product-preregistration.v14"
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "r7_distribution_with_fresh_entities_new_quick_request_envelopes_"
        "layered_addressing_and_generic_orders_absent_from_r7_r13"
    )
    builder.REFERENCES = REFERENCES
    builder.ADDRESSED_PREFIXES = {
        "es": "A ver, Baxy: ",
        "en": "Hey, Baxy: ",
        "spanglish": "Oye, Baxy: ",
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
