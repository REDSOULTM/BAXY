"""Build and preregister BAXY's execution-inert R18 blind product holdout.

R18 is the fresh certification population after the failed R17 opening and
its development-only repair.  It retains the balanced 700-case distribution
while changing entities, discourse frames, addressed surfaces, and generated
composition orders.  No normalized request may overlap R7-R17.
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
from scripts import build_generalization_product_holdout_r17 as r17  # noqa: E402
from scripts.build_generalization_surface_holdout import (  # noqa: E402
    Scenario,
    Utterance,
)


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v18.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v18.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r18_mind.json"
MIND_AUDIT = (
    REPO / "artifacts/holdout/generalization_product_holdout_r18_mind.raw.jsonl"
)
MEMORY_TRX = REPO / "artifacts/holdout/generalization_product_holdout_r18_memory.trx"
PRODUCT_OUTPUT = (
    REPO / "artifacts/holdout/generalization_product_holdout_r18_product.json"
)
PRIOR_CORPORA = (*r17.PRIOR_CORPORA, r17.OUTPUT)
POLICY_SOURCES = r17.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r18.py",
    REPO
    / "experiments/mind_router_spike/analyze_generalization_product_holdout_r18.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    *r17.BUILDER_DEPENDENCIES,
    REPO / "scripts/build_generalization_product_holdout_r17.py",
)
REFERENCES = r17.REFERENCES


_REPLACEMENTS = (
    ("Carpeta Coral", "Carpeta Ámbar"),
    ("Maple Folder", "Cedar Folder"),
    ("pases del planetario", "entradas del acuario"),
    ("planetarium passes", "aquarium tickets"),
    ("Teresa", "Camila"),
    ("Julián", "Renato"),
    ("Robin", "Jamie"),
    ("Morgan", "Drew"),
    ("Avery", "Riley"),
    ("Taylor", "Skyler"),
    ("Severance", "Foundation"),
    ("Silo", "Dark Matter"),
    ("arrecifes de coral", "islas volcánicas"),
    ("coral reefs", "volcanic islands"),
    ("dispositivos GPS para senderismo", "radios meteorológicas portátiles"),
    ("trail GPS devices", "portable weather radios"),
    (
        "quinientos veintinueve dividido por veintitrés",
        "seiscientos once dividido por veintiséis",
    ),
    (
        "five hundred twenty-nine divided by twenty-three",
        "six hundred eleven divided by twenty-six",
    ),
    (
        "quinientos twenty-nine divided by twenty-three",
        "seiscientos eleven divided by twenty-six",
    ),
    ("gnocchi", "bibimbap"),
    ("puerto tranquilo", "huerto invernal"),
    ("quiet harbor", "winter orchard"),
    ("Lucía", "Paula"),
    ("Tomás", "Andrés"),
    ("Valentina", "Fernanda"),
    ("Gabriel", "Mateo"),
    ("Parker", "Blake"),
    ("Quinn", "Reese"),
    ("Casey", "Devon"),
    ("Jordan", "Cameron"),
    ("Iris", "Noelia"),
    ("Mónica", "Susana"),
)


def _replace_token(text: str, old: str, new: str) -> str:
    return re.sub(
        rf"(?<!\w){re.escape(old)}(?!\w)",
        new,
        text,
        flags=re.IGNORECASE,
    )


def _rewrite(text: str) -> str:
    rewritten = r17._rewrite(text)
    for old, new in _REPLACEMENTS:
        rewritten = _replace_token(rewritten, old, new)
    return rewritten


def _request_utterance(value: Utterance, index: int) -> Utterance:
    prefixes = {
        "es": (
            "Te paso una tarea específica para este equipo: ",
            "Necesito que atiendas esto ahora: ",
        ),
        "en": (
            "Here is a specific request for this PC: ",
            "Please do this on the computer now: ",
        ),
        "spanglish": (
            "Necesito esta exact thing on the computer: ",
            "For this equipo right now, por favor ",
        ),
    }
    body = _rewrite(value.text)
    body = body[:1].lower() + body[1:]
    return Utterance(value.language, prefixes[value.language][index % 2] + body)


def _conversation_utterance(value: Utterance, index: int) -> Utterance:
    markers = {
        "es": (
            "Quisiera consultarte una cosa sin solicitar una acción: ",
            "Tengo una pregunta rápida, solamente para charlar: ",
        ),
        "en": (
            "Just a brief question, with no PC action: ",
            "I have a quick thought, just to talk: ",
        ),
        "spanglish": (
            "Tengo una brief question, sin PC acción: ",
            "Just para charlar, una question quick: ",
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
    for family, scenario in r17.r16.r7.SCENARIOS.items()
}
CLARIFICATIONS = Scenario(
    r17.r16.r7.CLARIFICATIONS.operations,
    tuple(
        _request_utterance(utterance, index)
        for index, utterance in enumerate(r17.r16.r7.CLARIFICATIONS.utterances)
    ),
)
COMPOSITION_PARTS = {
    operation: {language: _rewrite(part) for language, part in language_parts.items()}
    for operation, language_parts in r17.r16.r7.COMPOSITION_PARTS.items()
}


def _generated_compositions() -> tuple[builder.Composition, ...]:
    operations = tuple(COMPOSITION_PARTS)
    steps = tuple(
        step for step in range(2, len(operations)) if gcd(step, len(operations)) == 1
    )
    prior_sequences = {
        tuple(composition.operations)
        for composition in (
            *r17.r16.r7.COMPOSITIONS,
            *r17.r16.r8.COMPOSITIONS,
            *r17.r16.r9.COMPOSITIONS,
            *r17.r16.r10.COMPOSITIONS,
            *r17.r16.r11.COMPOSITIONS,
            *r17.r16.r12.COMPOSITIONS,
            *r17.r16.r13.COMPOSITIONS,
            *r17.r16.r14.COMPOSITIONS,
            *r17.r16.r15.COMPOSITIONS,
            *r17.r16.COMPOSITIONS,
            *r17.COMPOSITIONS,
        )
    }
    current: set[tuple[str, ...]] = set()
    languages = ("es", "en", "spanglish")
    rows: list[builder.Composition] = []
    for index in range(94):
        size = 2 + (index * 3 + 5) % 7
        language = languages[(index + 2) % len(languages)]
        selected: tuple[str, ...] | None = None
        for attempt in range(len(operations) * len(steps)):
            step = steps[(index * 37 + attempt // len(operations) + 29) % len(steps)]
            cursor = (index * 53 + attempt * 41 + 47) % len(operations)
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
            raise RuntimeError(f"R18 could not derive novel composition {index}")
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        base = r17.r16.r7._composition_text(language, parts, index + 613)
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
            Utterance("en", "Capture the screen and read every word from that image"),
            0,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe"),
        _request_utterance(
            Utterance("es", "Captura el escritorio y describe esa misma imagen"),
            1,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe", "ocr.read"),
        _request_utterance(
            Utterance(
                "en",
                "Take a screenshot, describe that scene, and read all text from the same capture",
            ),
            2,
        ),
    ),
    builder.Composition(
        ("message.recipient.resolve", "message.send", "task.list"),
        _request_utterance(
            Utterance(
                "es",
                "Notifícale a Noelia por WhatsApp que llegaré en treinta y cinco minutos y luego muestra mis tareas abiertas",
            ),
            3,
        ),
    ),
    builder.Composition(
        ("task.list", "capture.screenshot", "ocr.read"),
        _request_utterance(
            Utterance(
                "en",
                "List the open tasks, capture the resulting screen, and read the text in that capture",
            ),
            4,
        ),
    ),
    builder.Composition(
        ("system.process.list", "system.time", "task.list", "system.status"),
        _request_utterance(
            Utterance(
                "spanglish",
                "Lista los procesos, tell me the time, show my open tasks y luego check system status",
            ),
            5,
        ),
    ),
)
COMPOSITIONS = _generated_compositions() + SPECIAL_COMPOSITIONS
CONVERSATIONS = tuple(
    _conversation_utterance(utterance, index)
    for index, utterance in enumerate(r17.r16.r7.CONVERSATIONS)
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
    builder.CAMPAIGN = "r18"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-holdout.v18"
    builder.PREREGISTRATION_SCHEMA = "baxy.generalization-product-preregistration.v18"
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "post_r17_repair_fresh_entities_generalized_local_frames_"
        "and_composition_orders_absent_from_r7_r17"
    )
    builder.REFERENCES = REFERENCES
    builder.ADDRESSED_PREFIXES = {
        "es": "Baxy, haz esto: ",
        "en": "Baxy, do this: ",
        "spanglish": "Baxy, handle esto: ",
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
