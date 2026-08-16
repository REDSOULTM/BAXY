"""Build and preregister BAXY's execution-inert R13 blind product holdout.

R13 independently confirms the two-clause report and dependent-read repairs.
It preserves the 700-case product distribution while changing entities,
availability/meta-request envelopes, addressed surfaces, and every one of the
94 generic composition orders. No normalized request may overlap R7-R12.
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
from scripts.build_generalization_surface_holdout import (  # noqa: E402
    Scenario,
    Utterance,
)


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v13.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v13.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r13_mind.json"
MIND_AUDIT = REPO / "artifacts/holdout/generalization_product_holdout_r13_mind.raw.jsonl"
MEMORY_TRX = REPO / "artifacts/holdout/generalization_product_holdout_r13_memory.trx"
PRODUCT_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r13_product.json"
PRIOR_CORPORA = (*r12.PRIOR_CORPORA, r12.OUTPUT)
POLICY_SOURCES = r12.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r13.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r13.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    *r12.BUILDER_DEPENDENCIES,
    REPO / "scripts/build_generalization_product_holdout_r12.py",
)
REFERENCES = r12.REFERENCES


_REPLACEMENTS = (
    ("Audacity", "Inkscape"),
    ("GIMP", "Notepad++"),
    ("Carpeta Mirador", "Carpeta Estuario"),
    ("Harbor Folder", "Lagoon Folder"),
    ("boletos del museo", "pases del festival"),
    ("museum tickets", "festival passes"),
    ("Renata", "Solange"),
    ("Matías", "Tomás"),
    ("Riley", "Bailey"),
    ("Sawyer", "Reagan"),
    ("Jamie", "Robin"),
    ("Drew", "Blake"),
    ("Severance", "Foundation"),
    ("Andor", "Mr Robot"),
    ("flamencos del Atacama", "pingüinos patagónicos"),
    ("Atacama flamingos", "Patagonian penguins"),
    ("cargadores solares compactos", "hervidores de viaje plegables"),
    ("compact solar chargers", "foldable travel kettles"),
    (
        "doscientos veinticinco dividido por quince",
        "doscientos setenta y dos dividido por diecisiete",
    ),
    (
        "two hundred twenty-five divided by fifteen",
        "two hundred seventy-two divided by seventeen",
    ),
    (
        "doscientos twenty-five divided by fifteen",
        "doscientos seventy-two divided by seventeen",
    ),
    ("risotto", "gnocchi"),
    ("mañana ventosa", "tarde soleada"),
    ("windy morning", "sunny evening"),
    ("Elisa", "Mara"),
    ("Facundo", "Ramiro"),
    ("Agustina", "Josefina"),
    ("Nicolás", "Lautaro"),
    ("Kendall", "Quincy"),
    ("Harper", "Shannon"),
    ("Logan", "Carter"),
    ("Sydney", "Leslie"),
    ("Ari", "Noa"),
    ("Catalina", "Magdalena"),
)


def _replace_token(text: str, old: str, new: str) -> str:
    return re.sub(
        rf"(?<!\w){re.escape(old)}(?!\w)",
        new,
        text,
        flags=re.IGNORECASE,
    )


def _rewrite(text: str) -> str:
    rewritten = r12._rewrite(text)
    for old, new in _REPLACEMENTS:
        rewritten = _replace_token(rewritten, old, new)
    return rewritten


def _request_utterance(value: Utterance, index: int) -> Utterance:
    prefixes = {
        "es": ("Cuando te venga bien, ", "Una petición simple: "),
        "en": ("When it is convenient, ", "One brief request: "),
        "spanglish": ("Cuando te venga bien, please ", "One brief request, porfa: "),
    }
    body = _rewrite(value.text)
    body = body[:1].lower() + body[1:]
    return Utterance(value.language, prefixes[value.language][index % 2] + body)


def _conversation_utterance(value: Utterance, index: int) -> Utterance:
    markers = {
        "es": ("Una consulta simple: ", "Una pregunta breve: "),
        "en": ("A simple question: ", "One brief question: "),
        "spanglish": ("Una consulta simple: ", "One brief question: "),
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
        )
    }
    current: set[tuple[str, ...]] = set()
    languages = ("es", "en", "spanglish")
    rows: list[builder.Composition] = []
    for index in range(94):
        size = 2 + (index * 3 + 2) % 7
        language = languages[index % len(languages)]
        selected: tuple[str, ...] | None = None
        for attempt in range(len(operations) * len(steps)):
            step = steps[(index * 13 + attempt // len(operations) + 7) % len(steps)]
            cursor = (index * 29 + attempt * 17 + 11) % len(operations)
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
            raise RuntimeError(f"R13 could not derive novel composition {index}")
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        base = r7._composition_text(language, parts, index + 191)
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
            Utterance("en", "Capture the screen and read all visible words from that same image"),
            0,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe"),
        _request_utterance(
            Utterance("spanglish", "Capture el desktop y describe everything visible in that exact image"),
            1,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe", "ocr.read"),
        _request_utterance(
            Utterance("es", "Captura el escritorio, describe la escena y transcribe el texto de esa misma imagen"),
            2,
        ),
    ),
    builder.Composition(
        ("message.recipient.resolve", "message.send", "task.list"),
        _request_utterance(
            Utterance("en", "Tell Noa on WhatsApp that I arrive in twenty-five minutes, then list my open tasks"),
            3,
        ),
    ),
    builder.Composition(
        ("task.list", "capture.screenshot", "ocr.read"),
        _request_utterance(
            Utterance("spanglish", "Show mis open tasks, capture that screen y read the text from the capture"),
            4,
        ),
    ),
    builder.Composition(
        ("calendar.event.list", "capture.screenshot", "vision.describe", "clipboard.read.text"),
        _request_utterance(
            Utterance("es", "Muestra los eventos de mañana, captura esa vista, describe la imagen y lee el texto del portapapeles"),
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
    builder.CAMPAIGN = "r13"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-holdout.v13"
    builder.PREREGISTRATION_SCHEMA = "baxy.generalization-product-preregistration.v13"
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "r7_distribution_with_fresh_entities_new_convenience_and_meta_request_"
        "envelopes_layered_addressing_and_generic_orders_absent_from_r7_r12"
    )
    builder.REFERENCES = REFERENCES
    builder.ADDRESSED_PREFIXES = {
        "es": "Escucha, Baxy: ",
        "en": "Listen, Baxy: ",
        "spanglish": "Mira, Baxy: ",
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
