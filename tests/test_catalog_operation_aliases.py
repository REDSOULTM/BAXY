from __future__ import annotations

import json
import re
from pathlib import Path

from baxy_mind.catalog_operation_aliases import (
    catalog_operation_aliases,
    exact_catalog_operation_plan,
)
from baxy_mind.semantic.request import read_request
from baxy_mind.effect_intent import (
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
    unresolved_compound_contract,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src/baxy_mind/data/catalog_operation_aliases.v1.json"
# C03 (plan post-goal 2026-09-20, Fase 1): the v1 asset keeps its R267 identity;
# the aliases of the operations added in C03 (AGENDA1435, NETWORK1457, SYSTEM1459)
# live in a second asset loaded with it and bound to the live catalogue below.
C03_DATA = ROOT / "src/baxy_mind/data/catalog_operation_aliases.c03.v1.json"
CURRENT_CATALOGUE = ROOT / "artifacts/development/current_core_catalog_snapshot_r219.json"
PRODUCT_CATALOGUE = ROOT / "src/Baxy.Kernel/Operations/ProductCatalog.cs"


def _c03_rows() -> list[dict]:
    return json.loads(C03_DATA.read_text(encoding="utf-8"))["aliases"]


def _product_operations() -> set[str]:
    pattern = re.compile(r'Descriptor\(\s*"([a-z0-9_.]+)"')
    return set(pattern.findall(PRODUCT_CATALOGUE.read_text(encoding="utf-8")))


def test_runtime_alias_asset_is_complete_unique_and_proposal_only() -> None:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    catalogue = json.loads(CURRENT_CATALOGUE.read_text(encoding="utf-8"))
    aliases = catalog_operation_aliases()
    current_operations = {
        row["name"] for row in catalogue["catalogue"]["capabilities"]
    }
    alias_operations = {
        operation for row in payload["aliases"] for operation in row["operations"]
    }

    assert payload["authority"] == "proposal_only_authenticated_catalog_intersection"
    assert payload["catalog_operations"] == catalogue["catalogue"]["operations"] == 174
    assert payload["catalog_sha256"] == catalogue["catalogue"]["operation_names_sha256"]
    assert payload["alias_count"] == 157
    c03 = json.loads(C03_DATA.read_text(encoding="utf-8"))
    assert c03["alias_count"] == len(c03["aliases"]) == 3
    assert len(aliases) == 157 + 3
    assert len(set(aliases)) == len(aliases)
    assert alias_operations <= current_operations
    assert "notification.cancel.at" not in alias_operations
    c03_operations = {operation for row in c03["aliases"] for operation in row["operations"]}
    assert c03_operations <= _product_operations()
    assert c03_operations.isdisjoint(alias_operations)


def test_every_exact_alias_resolves_only_through_authenticated_operations() -> None:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    for row in payload["aliases"] + _c03_rows():
        expected = tuple(row["operations"])
        observed = resolve_explicit_effects(row["text"], expected)

        assert observed is not None, row["target_operation"]
        assert observed.operations == expected, row["target_operation"]


def test_alias_matching_is_exact_and_non_action_boundary_still_wins() -> None:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    row = next(
        value
        for value in payload["aliases"]
        if value["target_operation"] == "system.recyclebin.empty"
    )
    normalized = row["normalized_text"]
    available = tuple(row["operations"])

    assert exact_catalog_operation_plan(normalized) == available
    assert exact_catalog_operation_plan(normalized.rstrip(".!?")) == available
    assert exact_catalog_operation_plan(normalized + " extra") is None
    assert (
        resolve_explicit_effects(
            "Just a brief question, with no PC action: " + row["text"],
            available,
        )
        is None
    )


def test_polite_social_closure_is_transparent_for_every_exact_alias() -> None:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    tails = {
        "es": ("; por favor, eso es todo.", "; gracias, eso es todo!"),
        "en": (
            "; please, that's the whole request.",
            "; thank you, nothing else!",
        ),
        "spanglish": ("; please, eso es todo.", "; gracias, that's all!"),
    }
    corpus_rows = {
        row["target_operation"]: row
        for row in (
            json.loads(line)
            for line in (
                ROOT
                / "artifacts/development/catalog_seen_scenarios_r2_dependency_complete.jsonl"
            )
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        )
    }
    for row in payload["aliases"] + _c03_rows():
        source = corpus_rows.get(row["target_operation"])
        # The C03 aliases have no R2 corpus row; their language is the text's.
        language = source["language"] if source is not None else read_request(row["text"]).language
        expected = tuple(row["operations"])
        for tail in tails[language]:
            text = row["text"].rstrip(".!?") + tail
            observed = resolve_explicit_effects(text, expected)
            assert observed is not None, row["target_operation"]
            assert observed.operations == expected, row["target_operation"]


def test_request_completion_closure_is_transparent_for_every_exact_alias() -> None:
    """A tail announcing the request ended must not change the request.

    The R1 oracle failed 88/169 because these completion tails reached
    retrieval and decision as if they were part of the sentence. The private
    memory parser in `Baxy.App` was repaired first; this covers the same
    bounded family on the Mind side so both borders normalize identically.
    """

    payload = json.loads(DATA.read_text(encoding="utf-8"))
    # Deliberately disjoint from the surfaces the sealed R2 constructor emits.
    # These exercise the same bounded grammar branches, so R2 keeps measuring
    # closures this development regression never optimized against.
    tails = {
        "es": (
            "; con eso termina mi solicitud.",
            "; mi pedido concluye por ahora.",
            "; la petición queda completa aquí.",
        ),
        "en": (
            "; that completes my request.",
            "; this finishes the task for now.",
            "; the task has been done.",
        ),
        "spanglish": (
            "; con eso, my request is complete.",
            "; the task is now finished.",
            "; con esto, my task is done for now.",
        ),
    }
    corpus_rows = {
        row["target_operation"]: row
        for row in (
            json.loads(line)
            for line in (
                ROOT
                / "artifacts/development/catalog_seen_scenarios_r2_dependency_complete.jsonl"
            )
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        )
    }
    for row in payload["aliases"] + _c03_rows():
        source = corpus_rows.get(row["target_operation"])
        language = source["language"] if source is not None else read_request(row["text"]).language
        expected = tuple(row["operations"])
        for tail in tails[language]:
            text = row["text"].rstrip(".!?") + tail
            observed = resolve_explicit_effects(text, expected)
            assert observed is not None, f"{row['target_operation']} :: {tail}"
            assert observed.operations == expected, (
                f"{row['target_operation']} :: {tail}"
            )


def test_completion_closure_normalization_is_identical_on_both_borders() -> None:
    """Accented and folded spellings must strip to the same request."""

    from baxy_mind.effect_intent import _fold, _strip_request_envelope

    for accented, folded in (
        ("sube el volumen; la petición queda completa aquí.", "sube el volumen"),
        ("sube el volumen; la peticion queda completa aqui.", "sube el volumen"),
        ("mute the audio; that completes my request.", "mute the audio"),
        ("mute the audio; the task has been done.", "mute the audio"),
    ):
        assert _strip_request_envelope(accented) == folded
        assert _strip_request_envelope(_fold(accented)) == _fold(folded)


def test_social_closure_words_without_a_separator_remain_literal() -> None:
    assert exact_catalog_operation_plan("write nothing else") is None


def test_completion_wording_without_a_separator_stays_part_of_the_request() -> None:
    """Only a punctuated tail is a closure; the same words inline are content."""

    from baxy_mind.effect_intent import _strip_request_envelope

    for literal in (
        "escribe una nota que diga mi tarea termina hoy",
        "recuerdame que la solicitud queda completada el viernes",
        "write a note saying my request is now complete",
    ):
        assert _strip_request_envelope(literal) == literal


def test_a_turn_made_only_of_a_closure_keeps_its_own_text() -> None:
    """Stripping must never empty the body and hand a bare fragment onward."""

    from baxy_mind.effect_intent import _strip_request_envelope

    for closure_only in ("; eso es todo.", "; that completes my request."):
        assert _strip_request_envelope(closure_only).strip() != ""


def test_complete_destructive_aliases_are_not_preempted_as_incomplete() -> None:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    targets = {
        "notification.cancel.at",
        "notification.cancel.latest",
        "reminder.delete",
    }

    for row in payload["aliases"]:
        if row["target_operation"] not in targets:
            continue
        available = tuple(row["operations"])

        assert resolve_explicit_clarification_intent(row["text"], available) is None
        observed = resolve_explicit_effects(row["text"], available)
        assert observed is not None
        assert observed.operations == available


def test_exact_trash_prepare_can_explicitly_defer_the_commit() -> None:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    row = next(
        value
        for value in payload["aliases"]
        if value["target_operation"] == "filesystem.trash.prepare"
    )
    available = tuple(row["operations"])
    observed = resolve_explicit_effects(row["text"], available)

    assert observed is not None
    assert observed.operations == available
    assert (
        unresolved_compound_contract(
            row["text"],
            available,
            resolved_intent=observed,
        )
        is None
    )


def test_trash_prepare_negation_remains_non_actionable() -> None:
    text = "No prepares el archivo seleccionado para enviarlo a la papelera."
    available = ("filesystem.trash.prepare",)

    observed = resolve_explicit_effects(text, available)
    assert observed is None
    assert unresolved_compound_contract(
        text,
        available,
        resolved_intent=observed,
    ) is not None
