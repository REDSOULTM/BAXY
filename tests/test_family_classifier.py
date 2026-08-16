from __future__ import annotations

from baxy_mind.family_classifier import (
    EXPECTED_MANIFEST_SHA256,
    MANIFEST,
    MIN_PREDICTION_MARGIN,
    FamilyClassifier,
    _sha256,
)
from experiments.mind_router_spike.probe_presentable_product_oracle import (
    AUDITED_OUT_OF_SCOPE,
    FROZEN_SAMPLE_SHA256,
    _load_frozen_oracle,
)
FAMILIES = {
    "app",
    "audio",
    "backup",
    "bluetooth",
    "browser",
    "calendar",
    "capture",
    "clipboard",
    "email",
    "filesystem",
    "game",
    "input",
    "media",
    "memory",
    "message",
    "network",
    "note",
    "notification",
    "ocr",
    "office",
    "package",
    "peripheral",
    "reminder",
    "routine",
    "streaming",
    "system",
    "task",
    "vision",
    "web",
    "wifi",
    "window",
}


def test_family_classifier_manifest_is_attested() -> None:
    assert _sha256(MANIFEST) == EXPECTED_MANIFEST_SHA256


def test_family_classifier_routes_unseen_multilingual_requests() -> None:
    classifier = FamilyClassifier()
    cases = {
        "open Notepad and Calculator side by side": "app",
        "sube el volumen del compu a 10.": "audio",
        "qué hay en el portapapeles": "clipboard",
        "elimina solo archivo temporal tmp.txt": "filesystem",
        "tomá nota de que compre pan": "note",
        "timer de 10 minutos": "notification",
        "remind me to take out the trash tomorrow": "reminder",
        "tengo el brillo al máximo": "system",
    }

    assert {
        text: classifier.predict(text, FAMILIES).family
        for text in cases
    } == cases


def test_family_classifier_abstains_without_catalog_families() -> None:
    assert FamilyClassifier().predict("abre algo", ()) is None


def test_family_classifier_keeps_the_existing_low_margin_abstention() -> None:
    assert MIN_PREDICTION_MARGIN == 0.05
    assert (
        FamilyClassifier().predict(
            "what words am i holding ready to drop",
            FAMILIES,
        )
        is None
    )


def test_presentable_product_oracle_population_is_hash_bound_and_stable() -> None:
    sample = _load_frozen_oracle(
        tuple(f"{family}.test" for family in FAMILIES if family != "memory")
    )

    assert FROZEN_SAMPLE_SHA256 == (
        "c8db6a7b32f2ec607edfefd731a59ffb38dc918be3705f2e2fcaeaca0bce3feb"
    )
    assert len(sample) == 147
    assert len(
        [row for row in sample if row["case_id"] not in AUDITED_OUT_OF_SCOPE]
    ) == 140
