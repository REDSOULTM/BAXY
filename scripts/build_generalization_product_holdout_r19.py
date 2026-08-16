"""Build and preregister BAXY's execution-inert R19 blind product holdout.

R19 certifies the post-R18 composition repair on a fresh balanced population.
It changes entities, request frames, addressed surfaces, and generated
composition orders, with zero normalized overlap allowed against R7-R18.
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
from scripts import build_generalization_product_holdout_r18 as r18  # noqa: E402
from scripts.build_generalization_surface_holdout import (  # noqa: E402
    Scenario,
    Utterance,
)


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v19.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v19.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r19_mind.json"
MIND_AUDIT = (
    REPO / "artifacts/holdout/generalization_product_holdout_r19_mind.raw.jsonl"
)
MEMORY_TRX = REPO / "artifacts/holdout/generalization_product_holdout_r19_memory.trx"
PRODUCT_OUTPUT = (
    REPO / "artifacts/holdout/generalization_product_holdout_r19_product.json"
)
PRIOR_CORPORA = (*r18.PRIOR_CORPORA, r18.OUTPUT)
POLICY_SOURCES = r18.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r19.py",
    REPO
    / "experiments/mind_router_spike/analyze_generalization_product_holdout_r19.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    *r18.BUILDER_DEPENDENCIES,
    REPO / "scripts/build_generalization_product_holdout_r18.py",
)
REFERENCES = r18.REFERENCES


_REPLACEMENTS = (
    ("Carpeta Ámbar", "Carpeta Índigo"),
    ("Cedar Folder", "Willow Folder"),
    ("entradas del acuario", "entradas del museo"),
    ("aquarium tickets", "museum tickets"),
    ("Camila", "Adriana"),
    ("Renato", "Sergio"),
    ("Jamie", "Alex"),
    ("Drew", "Hayden"),
    ("Riley", "Finley"),
    ("Skyler", "Rowan"),
    ("Foundation", "The Bear"),
    ("Dark Matter", "Andor"),
    ("islas volcánicas", "oasis del desierto"),
    ("volcanic islands", "desert oases"),
    ("radios meteorológicas portátiles", "cargadores solares portátiles"),
    ("portable weather radios", "portable solar chargers"),
    (
        "seiscientos once dividido por veintiséis",
        "setecientos tres dividido por treinta y siete",
    ),
    (
        "six hundred eleven divided by twenty-six",
        "seven hundred three divided by thirty-seven",
    ),
    (
        "seiscientos eleven divided by twenty-six",
        "setecientos three divided by thirty-seven",
    ),
    ("bibimbap", "shakshuka"),
    ("huerto invernal", "biblioteca otoñal"),
    ("winter orchard", "autumn library"),
    ("Paula", "Rosa"),
    ("Andrés", "Felipe"),
    ("Fernanda", "Carolina"),
    ("Mateo", "Nicolás"),
    ("Blake", "Logan"),
    ("Reese", "Harper"),
    ("Devon", "Kendall"),
    ("Cameron", "Emerson"),
    ("Noelia", "Clara"),
    ("Susana", "Patricia"),
)


def _replace_token(text: str, old: str, new: str) -> str:
    return re.sub(
        rf"(?<!\w){re.escape(old)}(?!\w)",
        new,
        text,
        flags=re.IGNORECASE,
    )


def _rewrite(text: str) -> str:
    rewritten = r18._rewrite(text)
    for old, new in _REPLACEMENTS:
        rewritten = _replace_token(rewritten, old, new)
    return rewritten


def _request_utterance(value: Utterance, index: int) -> Utterance:
    prefixes = {
        "es": (
            "Te doy una petición puntual para el PC: ",
            "Necesito que realices lo siguiente: ",
        ),
        "en": (
            "Here's a concrete task for the computer: ",
            "Please handle this on this computer: ",
        ),
        "spanglish": (
            "Necesito this thing on this PC: ",
            "For este PC, please ",
        ),
    }
    body = _rewrite(value.text)
    body = body[:1].lower() + body[1:]
    return Utterance(value.language, prefixes[value.language][index % 2] + body)


def _conversation_utterance(value: Utterance, index: int) -> Utterance:
    markers = {
        "es": (
            "Quiero consultarte una cosa sin solicitar una acción: ",
            "Tengo una duda pequeña, sólo para charlar: ",
        ),
        "en": (
            "Just a small thought, with no computer action: ",
            "I have a brief question, just to talk: ",
        ),
        "spanglish": (
            "Tengo una short question, sin PC action: ",
            "Just para conversar, una question short: ",
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
    for family, scenario in r18.r17.r16.r7.SCENARIOS.items()
}
CLARIFICATIONS = Scenario(
    r18.r17.r16.r7.CLARIFICATIONS.operations,
    tuple(
        _request_utterance(utterance, index)
        for index, utterance in enumerate(r18.r17.r16.r7.CLARIFICATIONS.utterances)
    ),
)
COMPOSITION_PARTS = {
    operation: {language: _rewrite(part) for language, part in language_parts.items()}
    for operation, language_parts in r18.r17.r16.r7.COMPOSITION_PARTS.items()
}


def _generated_compositions() -> tuple[builder.Composition, ...]:
    operations = tuple(COMPOSITION_PARTS)
    steps = tuple(
        step for step in range(2, len(operations)) if gcd(step, len(operations)) == 1
    )
    prior_sequences = {
        tuple(composition.operations)
        for composition in (
            *r18.r17.r16.r7.COMPOSITIONS,
            *r18.r17.r16.r8.COMPOSITIONS,
            *r18.r17.r16.r9.COMPOSITIONS,
            *r18.r17.r16.r10.COMPOSITIONS,
            *r18.r17.r16.r11.COMPOSITIONS,
            *r18.r17.r16.r12.COMPOSITIONS,
            *r18.r17.r16.r13.COMPOSITIONS,
            *r18.r17.r16.r14.COMPOSITIONS,
            *r18.r17.r16.r15.COMPOSITIONS,
            *r18.r17.r16.COMPOSITIONS,
            *r18.r17.COMPOSITIONS,
            *r18.COMPOSITIONS,
        )
    }
    current: set[tuple[str, ...]] = set()
    languages = ("es", "en", "spanglish")
    rows: list[builder.Composition] = []
    for index in range(94):
        size = 2 + (index * 4 + 3) % 7
        language = languages[index % len(languages)]
        selected: tuple[str, ...] | None = None
        for attempt in range(len(operations) * len(steps)):
            step = steps[(index * 41 + attempt // len(operations) + 31) % len(steps)]
            cursor = (index * 59 + attempt * 43 + 53) % len(operations)
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
            raise RuntimeError(f"R19 could not derive novel composition {index}")
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        base = r18.r17.r16.r7._composition_text(language, parts, index + 719)
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
            Utterance("spanglish", "Toma un screenshot y describe that same image"),
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
        ("message.recipient.resolve", "message.send", "note.list"),
        _request_utterance(
            Utterance(
                "es",
                "Dile a Clara por WhatsApp que llegaré en veinticinco minutos y después lista mis notas",
            ),
            3,
        ),
    ),
    builder.Composition(
        ("note.list", "capture.screenshot", "ocr.read"),
        _request_utterance(
            Utterance(
                "en",
                "Show the saved notes, capture that result, and extract the text from the capture",
            ),
            4,
        ),
    ),
    builder.Composition(
        ("system.status", "task.list", "system.time", "system.process.list"),
        _request_utterance(
            Utterance(
                "spanglish",
                "Check system status, show my open tasks, dime la hora y luego list active processes",
            ),
            5,
        ),
    ),
)
COMPOSITIONS = _generated_compositions() + SPECIAL_COMPOSITIONS
CONVERSATIONS = tuple(
    _conversation_utterance(utterance, index)
    for index, utterance in enumerate(r18.r17.r16.r7.CONVERSATIONS)
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
    builder.CAMPAIGN = "r19"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-holdout.v19"
    builder.PREREGISTRATION_SCHEMA = "baxy.generalization-product-preregistration.v19"
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "post_r18_composition_repair_fresh_entities_frames_"
        "and_composition_orders_absent_from_r7_r18"
    )
    builder.REFERENCES = REFERENCES
    builder.ADDRESSED_PREFIXES = {
        "es": "Baxy, do esto: ",
        "en": "Baxy, atiende this: ",
        "spanglish": "Baxy, por favor: ",
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
