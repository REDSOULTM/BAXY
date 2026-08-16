"""Build and preregister BAXY's execution-inert R21 blind product holdout.

R21 is a fresh post-R20 population with new entities, already-supported
transparent request boundaries, and composition orders absent from R7-R20.
No product decision is inspected before the corpus and source hashes are
sealed.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from random import Random


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts import build_generalization_product_holdout_r3 as builder  # noqa: E402
from scripts import build_generalization_product_holdout_r20 as r20  # noqa: E402
from scripts.build_generalization_surface_holdout import (  # noqa: E402
    Scenario,
    Utterance,
)


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v21.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v21.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r21_mind.json"
MIND_AUDIT = (
    REPO / "artifacts/holdout/generalization_product_holdout_r21_mind.raw.jsonl"
)
MEMORY_TRX = REPO / "artifacts/holdout/generalization_product_holdout_r21_memory.trx"
PRODUCT_OUTPUT = (
    REPO / "artifacts/holdout/generalization_product_holdout_r21_product.json"
)
PRIOR_CORPORA = (*r20.PRIOR_CORPORA, r20.OUTPUT)
POLICY_SOURCES = r20.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r21.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r21.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    *r20.BUILDER_DEPENDENCIES,
    REPO / "scripts/build_generalization_product_holdout_r20.py",
)
REFERENCES = r20.REFERENCES


_REPLACEMENTS = (
    ("Carpeta Cobalto", "Carpeta Jade"),
    ("Maple Folder", "Cedar Folder"),
    ("entradas del planetario", "entradas del acuario"),
    ("planetarium tickets", "aquarium tickets"),
    ("Valentina", "Camila"),
    ("Tomás", "Mateo"),
    ("Morgan", "Riley"),
    ("Quinn", "Sawyer"),
    ("Avery", "Reese"),
    ("Parker", "Blake"),
    ("Severance", "Foundation"),
    ("Silo", "Dark Matter"),
    ("bosques de niebla", "arrecifes de coral"),
    ("cloud forests", "coral reefs"),
    ("purificadores de agua portátiles", "radios meteorológicas compactas"),
    ("portable water purifiers", "compact weather radios"),
    (
        "ochocientos cuarenta y uno dividido por veintinueve",
        "novecientos cincuenta y tres dividido por treinta y uno",
    ),
    (
        "eight hundred forty-one divided by twenty-nine",
        "nine hundred fifty-three divided by thirty-one",
    ),
    (
        "ochocientos forty-one divided by twenty-nine",
        "novecientos fifty-three divided by thirty-one",
    ),
    ("okonomiyaki", "bibimbap"),
    ("observatorio de primavera", "invernadero de invierno"),
    ("spring observatory", "winter greenhouse"),
    ("Elena", "Sofía"),
    ("Javier", "Andrés"),
    ("Mariana", "Verónica"),
    ("Sebastián", "Gabriel"),
    ("Casey", "Jamie"),
    ("Jordan", "Sydney"),
    ("Taylor", "Cameron"),
    ("Dakota", "Phoenix"),
    ("Lucía", "Paula"),
    ("Teresa", "Mónica"),
)


def _replace_token(text: str, old: str, new: str) -> str:
    return re.sub(
        rf"(?<!\w){re.escape(old)}(?!\w)",
        new,
        text,
        flags=re.IGNORECASE,
    )


def _rewrite(text: str) -> str:
    rewritten = r20._rewrite(text)
    for old, new in _REPLACEMENTS:
        rewritten = _replace_token(rewritten, old, new)
    return rewritten


def _request_utterance(value: Utterance, index: int) -> Utterance:
    prefixes = {
        "es": (
            "Te doy una tarea concreta para el PC: ",
            "Necesito que realices esto ahora: ",
        ),
        "en": (
            "Here is one specific task for this computer: ",
            "Please do the following on the PC now: ",
        ),
        "spanglish": (
            "Necesito this exact thing on the computer: ",
            "For este equipo right now, por favor ",
        ),
    }
    body = _rewrite(value.text)
    body = body[:1].lower() + body[1:]
    return Utterance(value.language, prefixes[value.language][index % 2] + body)


def _conversation_utterance(value: Utterance, index: int) -> Utterance:
    markers = {
        "es": (
            "Quisiera preguntarte algo sin pedir una acción: ",
            "Tengo una pregunta pequeña, solamente para conversar: ",
        ),
        "en": (
            "I have a quick thought, just to chat: ",
            "Just a brief question, with no PC action: ",
        ),
        "spanglish": (
            "Tengo una brief duda, sin computer action: ",
            "Just para conversar, una duda short: ",
        ),
    }
    return Utterance(
        value.language,
        markers[value.language][index % 2] + _rewrite(value.text),
    )


_BASE = r20._BASE
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
    prior_sequences = _prior_composition_sequences()
    current: set[tuple[str, ...]] = set()
    languages = ("en", "spanglish", "es")
    random = Random(210021)
    rows: list[builder.Composition] = []
    for index in range(94):
        size = 2 + (index * 3 + 5) % 7
        language = languages[index % len(languages)]
        selected: tuple[str, ...] | None = None
        for _attempt in range(10_000):
            sequence = tuple(random.sample(operations, size))
            if sequence not in prior_sequences and sequence not in current:
                selected = sequence
                current.add(sequence)
                break
        if selected is None:
            raise RuntimeError(f"R21 could not derive novel composition {index}")
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        base = _BASE._composition_text(language, parts, index + 947)
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
                "en",
                "Take a screen capture and extract every visible word from that same image",
            ),
            0,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe"),
        _request_utterance(
            Utterance(
                "en",
                "Take an image of this screen and describe that same capture",
            ),
            1,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe", "ocr.read"),
        _request_utterance(
            Utterance(
                "es",
                "Toma una captura, describe esa escena y lee todo el texto de la misma imagen",
            ),
            2,
        ),
    ),
    builder.Composition(
        ("message.recipient.resolve", "message.send", "reminder.list"),
        _request_utterance(
            Utterance(
                "en",
                "Send Paula on WhatsApp that I'll arrive soon and then list my scheduled reminders",
            ),
            3,
        ),
    ),
    builder.Composition(
        ("task.list", "capture.screenshot", "vision.describe"),
        _request_utterance(
            Utterance(
                "en",
                "Show my open tasks, capture that result, and describe what appears in the image",
            ),
            4,
        ),
    ),
    builder.Composition(
        ("system.process.list", "system.status", "system.time", "task.list"),
        _request_utterance(
            Utterance(
                "spanglish",
                "List running processes, check system health, tell me the time y show open tasks",
            ),
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
    builder.CAMPAIGN = "r21"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-holdout.v21"
    builder.PREREGISTRATION_SCHEMA = "baxy.generalization-product-preregistration.v21"
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "post_r20_systemic_boundary_and_compound_repair_fresh_entities_"
        "supported_frames_and_composition_orders_absent_from_r7_r20"
    )
    builder.REFERENCES = REFERENCES
    builder.ADDRESSED_PREFIXES = {
        "es": "Baxy, haz this: ",
        "en": "Baxy, do esto: ",
        "spanglish": "Baxy, atiende this: ",
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
