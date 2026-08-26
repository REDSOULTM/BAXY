from __future__ import annotations

from collections import Counter

from scripts.adjudicate_observed_product_replay import read_jsonl, text_sha256
from scripts.build_observed_current_contracts import (
    DEFAULT_CATALOG,
    DEFAULT_CORPUS,
    DEFAULT_MAPPING,
    load_catalog_names,
    read_mapping,
    unique_variants,
)
from scripts.review_observed_current_contracts import decide, review_rows


def variant(text: str, *operations: str, hash_value: str | None = None) -> dict:
    return {
        "text": text,
        "text_sha256": hash_value or text_sha256(text),
        "historical_contract": {"operations": list(operations)},
    }


def test_independent_semantics_override_stale_historical_labels() -> None:
    message = decide(
        variant(
            "Mandale un mensaje a Música en whatsapp que diga hola",
            "media.play",
        )
    )
    bluetooth = decide(variant("tengo el bluetooth encendido", "bluetooth.manage"))
    screen = decide(variant("leéme lo que dice la pantalla", "vision.describe"))

    assert message.operations == ("message.send",)
    assert message.support == ("message.recipient.resolve",)
    assert bluetooth.kind == "conversation"
    assert bluetooth.operations == ()
    assert screen.operations == ("ocr.read",)
    assert screen.support == ("capture.screenshot",)


def test_implicit_memory_requires_consent_but_explicit_memory_is_actionable() -> None:
    implicit = decide(variant("Mi nombre es Albeda Kegis.", "memory.save"))
    explicit = decide(variant("Recuerda que me llamo Reta.", "memory.save"))

    assert implicit.kind == "clarify"
    assert implicit.operations == ()
    assert explicit.kind == "action"
    assert explicit.operations == ("memory.save",)


def test_session_bound_referent_has_an_exact_reviewed_override() -> None:
    decision = decide(
        variant(
            "Abrelo",
            hash_value="d6c0e4e5" + "0" * 56,
        )
    )

    assert decision.operations == ("app.open",)
    assert decision.rule == "session_referent_application_open"


def test_frozen_inventory_has_exact_binary_coverage_and_only_current_operations() -> None:
    corpus = list(read_jsonl(DEFAULT_CORPUS))
    message_ids = {row["message_id"] for row in corpus}
    variants = unique_variants(corpus, read_mapping(DEFAULT_MAPPING, message_ids))

    reviews = review_rows(variants)

    assert len(reviews) == 626
    assert len({row["text_sha256"] for row in reviews}) == 626
    assert Counter(row["contract"]["kind"] for row in reviews) == {
        "action": 367,
        "clarify": 86,
        "conversation": 173,
    }
    assert all(row["verdict"] == "pass" for row in reviews)
    assert all(row["rule"] != "historical_contract_requires_independent_clarification" for row in reviews)
    catalog = load_catalog_names(DEFAULT_CATALOG)
    granted = {
        operation
        for row in reviews
        for field in ("operations", "allowed_support_operations", "denied_operations")
        for operation in row["contract"][field]
    }
    assert granted <= catalog
