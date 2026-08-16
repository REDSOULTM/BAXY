from __future__ import annotations

import dataclasses
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "train_turn_policy_e5_development.py"
FIXTURES = ROOT / "tests" / "fixtures" / "turn_policy_e5_development"
ALLOWED_OPERATIONS = frozenset(
    {
        "app.open",
        "mail.send",
        "notification.schedule",
        "system.time",
    }
)
ALLOWED_FAMILIES = frozenset(
    operation.split(".", 1)[0] for operation in ALLOWED_OPERATIONS
)

SPEC = importlib.util.spec_from_file_location(
    "baxy_turn_policy_e5_development_under_test",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
POLICY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = POLICY
SPEC.loader.exec_module(POLICY)


def _load_fixture_examples():
    intent_policy = POLICY.load_mtop_intent_policy(
        FIXTURES / "mtop_policy_map.json",
        ALLOWED_OPERATIONS,
    )
    runtime_train = POLICY.load_runtime_development(
        FIXTURES / "runtime_train.jsonl",
        "train",
    )
    runtime_validation = POLICY.load_runtime_development(
        FIXTURES / "runtime_validation.jsonl",
        "validation",
    )
    mtop = POLICY.load_mtop_development(
        FIXTURES / "mtop_development.jsonl",
        ALLOWED_OPERATIONS,
        intent_policy,
    )
    examples = (
        runtime_train.examples + runtime_validation.examples + mtop.examples
    )
    return intent_policy, runtime_train, runtime_validation, mtop, examples


def _synthetic_vectors(rows: int, dimensions: int = 5) -> np.ndarray:
    values = np.arange(1, rows * dimensions + 1, dtype=np.float32)
    return values.reshape(rows, dimensions)


def _head(kind: str, classes: tuple[str, ...], dimensions: int = 3):
    coefficients = np.arange(
        1,
        len(classes) * dimensions + 1,
        dtype=np.float64,
    ).reshape(len(classes), dimensions)
    coefficients /= 100.0
    intercepts = np.linspace(-0.05, 0.05, len(classes), dtype=np.float64)
    return POLICY.LinearHead(kind, classes, coefficients, intercepts)


def _constant_binary_head(
    classes: tuple[str, str],
    second_probability: float,
    dimensions: int = 3,
):
    logit = math.log(second_probability / (1.0 - second_probability))
    return POLICY.LinearHead(
        "softmax",
        classes,
        np.zeros((2, dimensions), dtype=np.float64),
        np.asarray((-0.5 * logit, 0.5 * logit), dtype=np.float64),
    )


def _group(
    mission_id: str,
    split: str,
    trigger: str,
    families: tuple[str, ...],
    operations: tuple[str, ...],
    *,
    no_effect_disposition: str | None = None,
    member_vectors: tuple[np.ndarray, ...] | None = None,
    member_locales: tuple[str, ...] | None = None,
):
    vector = np.asarray([0.2, 0.4, 0.8], dtype=np.float64)
    members = member_vectors or (vector / np.linalg.norm(vector),)
    return POLICY.GroupExample(
        mission_id=mission_id,
        split=split,
        trigger=trigger,
        no_effect_disposition=(
            no_effect_disposition
            if trigger == POLICY.TRIGGER_NEGATIVE
            else None
        )
        or (
            POLICY.OUTCOME_CONVERSATION
            if trigger == POLICY.TRIGGER_NEGATIVE
            else None
        ),
        families=families,
        operations=operations,
        datasets=("synthetic",),
        vector=vector / np.linalg.norm(vector),
        member_vectors=members,
        member_locales=member_locales or tuple("en" for _ in members),
    )


def test_loaders_keep_only_reviewed_development_evidence() -> None:
    intent_policy, runtime_train, runtime_validation, mtop, examples = (
        _load_fixture_examples()
    )

    assert intent_policy.dispositions["IN:SET_ALARM"] == "candidate"
    assert intent_policy.ood_intents == frozenset({"IN:PLAY_GAME"})
    assert len(runtime_train.examples) == 4
    assert len(runtime_validation.examples) == 8
    assert runtime_train.exclusions == {
        "runtime_clarify_without_effect_target": 1
    }
    assert len(mtop.examples) == 18
    assert mtop.exclusions == {
        "mtop_contract_structure_mismatch_ambiguous": 2
    }
    assert all(
        example.mission_id != "synthetic-mtop-train-mismatch"
        for example in mtop.examples
    )
    corrected_missing = [
        example
        for example in mtop.examples
        if example.mission_id == "synthetic-mtop-train-missing"
    ]
    assert len(corrected_missing) == 2
    assert all(
        example.trigger == POLICY.TRIGGER_POSITIVE
        and example.operations == ("notification.schedule",)
        for example in corrected_missing
    )
    assert {
        example.no_effect_disposition
        for example in mtop.examples
        if example.trigger == POLICY.TRIGGER_NEGATIVE
    } == {
        POLICY.OUTCOME_CONVERSATION,
        POLICY.OUTCOME_UNSUPPORTED,
    }
    assert all(
        example.no_effect_disposition == POLICY.OUTCOME_CONVERSATION
        for example in runtime_train.examples + runtime_validation.examples
        if example.trigger == POLICY.TRIGGER_NEGATIVE
    )
    POLICY.validate_development_examples(
        examples,
        allowed_families=ALLOWED_FAMILIES,
    )


def test_supported_intent_cannot_be_forged_as_mapped_ood(tmp_path: Path) -> None:
    intent_policy, *_ = _load_fixture_examples()
    row = {
        "schema": POLICY.MTOP_ROW_SCHEMA,
        "text": "A supported intent mislabeled as unsupported",
        "locale": "en",
        "split": "train",
        "mission_id": "forged-supported-ood",
        "source_id": "forged-supported-ood-en",
        "semantic": {"intent": "IN:SEND_MESSAGE"},
        "projection": {
            "disposition": "ood_no_effect",
            "candidate_operations": [],
            "families": [],
            "reason": "mapped_unsupported_intent",
            "execution_authority": False,
        },
    }
    path = tmp_path / "mtop_development.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="explicitly reviewed"):
        POLICY.load_mtop_development(
            path,
            ALLOWED_OPERATIONS,
            intent_policy,
        )


def test_unlisted_intent_cannot_enter_as_ood(tmp_path: Path) -> None:
    intent_policy, *_ = _load_fixture_examples()
    row = {
        "schema": POLICY.MTOP_ROW_SCHEMA,
        "text": "An unreviewed intent",
        "locale": "en",
        "split": "validation",
        "mission_id": "unreviewed-ood",
        "source_id": "unreviewed-ood-en",
        "semantic": {"intent": "IN:UNREVIEWED"},
        "projection": {
            "disposition": "ood_no_effect",
            "candidate_operations": [],
            "families": [],
            "reason": "mapped_unsupported_intent",
            "execution_authority": False,
        },
    }
    path = tmp_path / "mtop_development.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="explicitly reviewed"):
        POLICY.load_mtop_development(
            path,
            ALLOWED_OPERATIONS,
            intent_policy,
        )


def test_mission_and_normalized_text_leakage_are_rejected() -> None:
    *_, examples = _load_fixture_examples()
    train = next(example for example in examples if example.split == "train")
    validation = next(
        example for example in examples if example.split == "validation"
    )

    crossed_mission = dataclasses.replace(
        validation,
        mission_id=train.mission_id,
        source_id="synthetic-crossed-mission",
    )
    with pytest.raises(ValueError, match="mission_id crosses"):
        POLICY.validate_development_examples(
            (*examples, crossed_mission),
            allowed_families=ALLOWED_FAMILIES,
        )

    copied_text = dataclasses.replace(
        validation,
        text=train.text,
        source_id="synthetic-copied-text",
        mission_id="synthetic-distinct-validation-mission",
    )
    with pytest.raises(ValueError, match="normalized text crosses"):
        POLICY.validate_development_examples(
            (*examples, copied_text),
            allowed_families=ALLOWED_FAMILIES,
        )


def test_cross_source_decontamination_protects_validation_by_mission() -> None:
    *_, examples = _load_fixture_examples()
    train_examples = [
        example for example in examples if example.split == "train"
    ]
    validation_examples = [
        example for example in examples if example.split == "validation"
    ]
    train_collision = train_examples[0]
    train_keep = next(
        example
        for example in train_examples
        if example.mission_id != train_collision.mission_id
    )
    validation_collision = dataclasses.replace(
        validation_examples[0],
        text=train_collision.text,
        trigger=train_collision.trigger,
        families=train_collision.families,
        operations=train_collision.operations,
        mission_id="synthetic-validation-collision",
        source_id="synthetic-validation-collision-source",
    )
    validation_keep = next(
        example
        for example in validation_examples
        if example.mission_id != validation_examples[0].mission_id
    )

    filtered = POLICY.decontaminate_cross_source_development(
        {
            "runtime_train": POLICY.LoadResult(
                (train_collision, train_keep),
                {},
            ),
            "runtime_validation": POLICY.LoadResult(
                (validation_collision, validation_keep),
                {},
            ),
        }
    )

    assert filtered["runtime_train"].examples == (train_keep,)
    assert filtered["runtime_validation"].examples == (
        validation_collision,
        validation_keep,
    )
    assert filtered["runtime_train"].exclusions == {
        "cross_split_exact_text_train_missions_removed": 1,
        "cross_split_exact_text_train_rows_removed": 1,
    }
    POLICY.validate_development_examples(
        (
            *filtered["runtime_train"].examples,
            *filtered["runtime_validation"].examples,
        ),
        allowed_families=ALLOWED_FAMILIES,
    )


def test_cross_source_conflicting_exact_text_quarantines_both_missions() -> None:
    *_, examples = _load_fixture_examples()
    train_examples = [
        example for example in examples if example.split == "train"
    ]
    validation_examples = [
        example for example in examples if example.split == "validation"
    ]
    train_collision = train_examples[0]
    train_keep = next(
        example
        for example in train_examples
        if example.mission_id != train_collision.mission_id
    )
    validation_collision = dataclasses.replace(
        validation_examples[0],
        text=train_collision.text,
        trigger=(
            POLICY.TRIGGER_NEGATIVE
            if train_collision.trigger == POLICY.TRIGGER_POSITIVE
            else POLICY.TRIGGER_POSITIVE
        ),
        families=(
            ()
            if train_collision.trigger == POLICY.TRIGGER_POSITIVE
            else ("app",)
        ),
        operations=(),
        mission_id="synthetic-validation-conflict",
        source_id="synthetic-validation-conflict-source",
    )
    validation_keep = next(
        example
        for example in validation_examples
        if example.mission_id != validation_examples[0].mission_id
    )

    filtered = POLICY.decontaminate_cross_source_development(
        {
            "runtime_train": POLICY.LoadResult(
                (train_collision, train_keep),
                {},
            ),
            "runtime_validation": POLICY.LoadResult(
                (validation_collision, validation_keep),
                {},
            ),
        }
    )

    assert filtered["runtime_train"].examples == (train_keep,)
    assert filtered["runtime_validation"].examples == (validation_keep,)
    assert filtered["runtime_train"].exclusions == {
        "cross_split_conflicting_exact_text_missions_removed": 1,
        "cross_split_conflicting_exact_text_rows_removed": 1,
    }
    assert filtered["runtime_validation"].exclusions == {
        "cross_split_conflicting_exact_text_missions_removed": 1,
        "cross_split_conflicting_exact_text_rows_removed": 1,
    }


def test_mission_aggregation_gives_each_parallel_group_one_vote() -> None:
    *_, examples = _load_fixture_examples()
    vectors = _synthetic_vectors(len(examples))

    groups = POLICY.aggregate_mission_vectors(examples, vectors)

    assert len(groups) == len({example.mission_id for example in examples})
    assert all(np.linalg.norm(group.vector) == pytest.approx(1.0) for group in groups)
    assert (
        sum(
            group.mission_id == "synthetic-mtop-train-open"
            for group in groups
        )
        == 1
    )


def test_utterance_training_weights_sum_to_one_vote_per_mission() -> None:
    first = _group(
        "mission-with-two-variants",
        "train",
        POLICY.TRIGGER_POSITIVE,
        ("app",),
        ("app.open",),
        member_vectors=(
            np.asarray([1.0, 0.0, 0.0]),
            np.asarray([0.0, 1.0, 0.0]),
        ),
        member_locales=("en", "es"),
    )
    second = _group(
        "mission-with-one-variant",
        "train",
        POLICY.TRIGGER_POSITIVE,
        ("app",),
        ("app.open",),
        member_vectors=(np.asarray([0.0, 0.0, 1.0]),),
        member_locales=("en",),
    )

    matrix, labels, weights = POLICY.flatten_group_members(
        [first, second],
        [POLICY.TRIGGER_POSITIVE, POLICY.TRIGGER_POSITIVE],
    )

    assert matrix.shape == (3, 3)
    assert labels == [POLICY.TRIGGER_POSITIVE] * 3
    assert weights[:2].sum() == pytest.approx(weights[2])
    assert weights.mean() == pytest.approx(1.0)


def test_validation_partition_is_deterministic_and_group_disjoint() -> None:
    *_, examples = _load_fixture_examples()
    groups = POLICY.aggregate_mission_vectors(
        examples,
        _synthetic_vectors(len(examples)),
    )
    validation = [group for group in groups if group.split == "validation"]
    strata: dict[tuple[str, str, tuple[str, ...]], list] = {}
    for group in validation:
        key = (
            group.outcome,
            "operation" if group.operations else "no_operation",
            group.datasets,
        )
        strata.setdefault(key, []).append(group)
    for index, members in enumerate(strata.values()):
        if len(members) == 1:
            validation.append(
                dataclasses.replace(
                    members[0],
                    mission_id=f"{members[0].mission_id}-replica-{index}",
                )
            )

    first = POLICY.split_validation_groups(validation, "stable-seed")
    second = POLICY.split_validation_groups(validation, "stable-seed")

    first_ids = tuple(
        tuple(group.mission_id for group in partition) for partition in first
    )
    second_ids = tuple(
        tuple(group.mission_id for group in partition) for partition in second
    )
    assert first_ids == second_ids
    calibration, evaluation = first
    assert {group.mission_id for group in calibration}.isdisjoint(
        group.mission_id for group in evaluation
    )
    assert {group.outcome for group in calibration} == set(
        POLICY.OUTCOME_CLASSES
    )
    assert {group.outcome for group in evaluation} == set(
        POLICY.OUTCOME_CLASSES
    )
    assert any(group.operations for group in calibration)


def test_split_conformal_quantiles_and_safe_shortlist_abstention() -> None:
    assert POLICY.conformal_quantile([0.1, 0.2, 0.3, 0.4], 0.25) == 0.4
    assert POLICY.conformal_quantile([0.1, 0.2], 0.05) == 1.0
    assert POLICY.conformal_classification_set(
        [0.95, 0.20],
        ["supported", "other"],
        0.10,
    ) == ("supported",)
    assert POLICY.conformal_label_conditional_set(
        [0.70, 0.30],
        ["negative", "positive"],
        {"negative": 0.20, "positive": 0.80},
    ) == ("positive",)
    assert POLICY.conformal_multilabel_set(
        [0.95, 0.94, 0.93],
        ["one", "two", "three"],
        0.10,
        maximum_size=2,
    ) == ()


def test_strict_guard_is_mission_level_and_fail_closed() -> None:
    guard = POLICY.strict_guard_threshold(
        [0.10, 0.40, 0.25],
        delta=0.05,
    )

    assert guard["threshold"] == 0.40
    assert guard["calibration_missions"] == 3
    assert guard["calibration_false_accepts"] == 0
    assert guard["wilks_upper_rate"] == pytest.approx(
        1.0 - math.pow(0.05, 1.0 / 3.0)
    )
    assert not (0.40 > guard["threshold"])
    assert 0.41 > guard["threshold"]


def test_ood_never_becomes_fast_chat_when_conversation_guard_rejects() -> None:
    effect_head = _constant_binary_head(
        (POLICY.TRIGGER_NEGATIVE, POLICY.TRIGGER_POSITIVE),
        0.01,
    )
    conversation_biased_head = _constant_binary_head(
        POLICY.NO_EFFECT_CLASSES,
        0.01,
    )
    family_head = POLICY.LinearHead(
        "one_vs_rest",
        ("app",),
        np.zeros((1, 3), dtype=np.float64),
        np.asarray([4.0]),
    )
    operation_head = POLICY.LinearHead(
        "one_vs_rest",
        ("app.open",),
        np.zeros((1, 3), dtype=np.float64),
        np.asarray([4.0]),
    )
    ood = _group(
        "ood-mission",
        "validation",
        POLICY.TRIGGER_NEGATIVE,
        (),
        (),
        no_effect_disposition=POLICY.OUTCOME_UNSUPPORTED,
    )
    common = {
        "effect_thresholds": {
            POLICY.TRIGGER_NEGATIVE: 0.05,
            POLICY.TRIGGER_POSITIVE: 0.05,
        },
        "no_effect_thresholds": {
            POLICY.OUTCOME_CONVERSATION: 0.05,
            POLICY.OUTCOME_UNSUPPORTED: 0.05,
        },
        "family_threshold": 0.05,
        "operation_threshold": 0.05,
        "maximum_families": 1,
        "maximum_operations": 1,
    }

    rejected = POLICY._evaluate(
        [ood],
        effect_head,
        conversation_biased_head,
        family_head,
        operation_head,
        selective_guards={
            "supported_effect": {"threshold": 1.0},
            "conversation_fast_path": {"threshold": 0.99},
        },
        **common,
    )
    permissive = POLICY._evaluate(
        [ood],
        effect_head,
        conversation_biased_head,
        family_head,
        operation_head,
        selective_guards={
            "supported_effect": {"threshold": 1.0},
            "conversation_fast_path": {"threshold": 0.0},
        },
        **common,
    )

    rejected_outcome = rejected["selective_outcome"]
    assert rejected_outcome["selection_rate"] == 0.0
    assert rejected_outcome["directional_safety"][
        "unsafe_ood_as_conversation"
    ] == 0
    assert permissive["selective_outcome"]["directional_safety"][
        "unsafe_ood_as_conversation"
    ] == 1


def test_supported_signal_requires_structural_family_agreement() -> None:
    effect_head = _constant_binary_head(
        (POLICY.TRIGGER_NEGATIVE, POLICY.TRIGGER_POSITIVE),
        0.99,
    )
    no_effect_head = _constant_binary_head(POLICY.NO_EFFECT_CLASSES, 0.5)
    low_family_logit = math.log(0.01 / 0.99)
    family_head = POLICY.LinearHead(
        "one_vs_rest",
        ("app",),
        np.zeros((1, 3), dtype=np.float64),
        np.asarray([low_family_logit]),
    )
    operation_head = POLICY.LinearHead(
        "one_vs_rest",
        ("app.open",),
        np.zeros((1, 3), dtype=np.float64),
        np.asarray([0.0]),
    )
    conversation = _group(
        "conversation-mission",
        "validation",
        POLICY.TRIGGER_NEGATIVE,
        (),
        (),
    )

    metrics = POLICY._evaluate(
        [conversation],
        effect_head,
        no_effect_head,
        family_head,
        operation_head,
        effect_thresholds={
            POLICY.TRIGGER_NEGATIVE: 0.05,
            POLICY.TRIGGER_POSITIVE: 0.05,
        },
        no_effect_thresholds={
            POLICY.OUTCOME_CONVERSATION: 1.0,
            POLICY.OUTCOME_UNSUPPORTED: 1.0,
        },
        family_threshold=0.05,
        operation_threshold=0.05,
        selective_guards={
            "supported_effect": {"threshold": 0.0},
            "conversation_fast_path": {"threshold": 1.0},
        },
        maximum_families=1,
        maximum_operations=1,
    )

    outcome = metrics["selective_outcome"]
    assert outcome["selection_rate"] == 0.0
    assert outcome["directional_safety"]["unsafe_false_supported"] == 0


def test_evaluation_reports_utterance_and_directional_safety_metrics() -> None:
    effect_head = _head(
        "softmax",
        (POLICY.TRIGGER_NEGATIVE, POLICY.TRIGGER_POSITIVE),
    )
    no_effect_head = _head("softmax", POLICY.NO_EFFECT_CLASSES)
    family_head = _head("one_vs_rest", ("app", "system"))
    operation_head = _head("one_vs_rest", ("app.open", "system.time"))
    groups = [
        _group(
            "evaluation-negative",
            "validation",
            POLICY.TRIGGER_NEGATIVE,
            (),
            (),
        ),
        _group(
            "evaluation-positive",
            "validation",
            POLICY.TRIGGER_POSITIVE,
            ("app",),
            ("app.open",),
        ),
    ]

    metrics = POLICY._evaluate(
        groups,
        effect_head,
        no_effect_head,
        family_head,
        operation_head,
        effect_thresholds={
            POLICY.TRIGGER_NEGATIVE: 1.0,
            POLICY.TRIGGER_POSITIVE: 1.0,
        },
        no_effect_thresholds={
            POLICY.OUTCOME_CONVERSATION: 1.0,
            POLICY.OUTCOME_UNSUPPORTED: 1.0,
        },
        family_threshold=1.0,
        operation_threshold=1.0,
        selective_guards={
            "supported_effect": {"threshold": 1.0},
            "conversation_fast_path": {"threshold": 1.0},
        },
        maximum_families=2,
        maximum_operations=2,
    )

    assert metrics["utterances"] == 2
    assert metrics["effect_gate"]["utterance_coverage"] == 1.0
    assert metrics["selective_outcome"]["abstention_rate"] == 1.0
    safety = metrics["selective_outcome"]["directional_safety"]
    assert safety["unsafe_false_supported"] == 0
    assert safety["unsafe_conversation_as_supported"] == 0
    assert safety["unsafe_ood_as_supported"] == 0
    assert safety["unsafe_supported_as_conversation"] == 0
    assert safety["unsafe_ood_as_conversation"] == 0


def test_v1_embedding_cache_identity_is_reusable_for_v2_disposition() -> None:
    *_, mtop, _ = _load_fixture_examples()
    original = next(
        example
        for example in mtop.examples
        if example.no_effect_disposition == POLICY.OUTCOME_UNSUPPORTED
    )
    relabeled = dataclasses.replace(
        original,
        no_effect_disposition=POLICY.OUTCOME_CONVERSATION,
    )

    assert original.target_signature != relabeled.target_signature
    assert POLICY.examples_fingerprint([original]) == (
        POLICY.examples_fingerprint([relabeled])
    )


def test_embedding_cache_is_atomic_text_free_and_content_addressed(
    tmp_path: Path,
) -> None:
    *_, examples = _load_fixture_examples()
    selected = examples[:4]
    vectors = _synthetic_vectors(len(selected), dimensions=3)
    encoder = {
        "model": "synthetic/e5",
        "revision": "a" * 40,
        "manifest_sha256": "b" * 64,
        "query_prefix": "query: ",
        "normalize_embeddings": True,
    }

    manifest_path = POLICY.write_embedding_cache_atomic(
        tmp_path,
        dataset_name="runtime_train",
        source_sha256="c" * 64,
        examples=selected,
        encoder_identity=encoder,
        vectors=vectors,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    array_path = manifest_path.parent / manifest["array"]["file_name"]

    assert manifest["contains_text"] is False
    assert manifest["contains_source_ids"] is False
    assert manifest["contains_mission_ids"] is False
    assert manifest["contains_derived_embeddings"] is True
    assert manifest["privacy_class"] == "sensitive_derived_embeddings"
    assert manifest["array"]["file_name"].endswith(".npz")
    for example in selected:
        assert example.text not in manifest_path.read_text(encoding="utf-8")
        assert example.text.encode("utf-8") not in array_path.read_bytes()
    with np.load(array_path, allow_pickle=False) as bundle:
        assert bundle.files == ["vectors"]
    loaded = POLICY.load_embedding_cache(
        manifest_path,
        dataset_name="runtime_train",
        source_sha256="c" * 64,
        examples=selected,
        encoder_identity=encoder,
    )
    np.testing.assert_array_equal(loaded, vectors.astype(np.float32))
    assert not list(tmp_path.glob("*.tmp"))
    assert not list(tmp_path.glob(".*.tmp"))


def test_embedding_cache_rejects_privacy_and_path_tampering(
    tmp_path: Path,
) -> None:
    *_, examples = _load_fixture_examples()
    selected = examples[:2]
    encoder = {"model": "synthetic/e5", "revision": "fixed"}
    manifest_path = POLICY.write_embedding_cache_atomic(
        tmp_path,
        dataset_name="runtime_train",
        source_sha256="d" * 64,
        examples=selected,
        encoder_identity=encoder,
        vectors=_synthetic_vectors(len(selected), dimensions=2),
    )
    original = json.loads(manifest_path.read_text(encoding="utf-8"))

    private = dict(original)
    private["contains_text"] = True
    manifest_path.write_text(json.dumps(private), encoding="utf-8")
    with pytest.raises(ValueError, match="identity"):
        POLICY.load_embedding_cache(
            manifest_path,
            dataset_name="runtime_train",
            source_sha256="d" * 64,
            examples=selected,
            encoder_identity=encoder,
        )

    traversing = dict(original)
    traversing["array"] = dict(original["array"])
    traversing["array"]["file_name"] = "../outside.npz"
    manifest_path.write_text(json.dumps(traversing), encoding="utf-8")
    with pytest.raises(ValueError, match="array reference"):
        POLICY.load_embedding_cache(
            manifest_path,
            dataset_name="runtime_train",
            source_sha256="d" * 64,
            examples=selected,
            encoder_identity=encoder,
        )


def test_verified_cache_hit_does_not_load_the_encoder(
    tmp_path: Path,
) -> None:
    runtime = POLICY.load_runtime_development(
        FIXTURES / "runtime_train.jsonl",
        "train",
    )
    source_path = FIXTURES / "runtime_train.jsonl"
    encoder = {"model": "synthetic/e5", "revision": "fixed"}
    expected = _synthetic_vectors(len(runtime.examples), dimensions=2)
    POLICY.write_embedding_cache_atomic(
        tmp_path,
        dataset_name="runtime_train",
        source_sha256=POLICY._sha256_file(source_path),
        examples=runtime.examples,
        encoder_identity=encoder,
        vectors=expected,
    )
    encoder_holder = []

    vectors, lineage = POLICY._vectors_for_source(
        cache_directory=tmp_path,
        dataset_name="runtime_train",
        source_path=source_path,
        examples=runtime.examples,
        encoder_identity=encoder,
        encoder_holder=encoder_holder,
        device="cpu",
        batch_size=2,
    )

    np.testing.assert_array_equal(vectors, expected.astype(np.float32))
    assert encoder_holder == []
    assert len(lineage["embedding_cache_manifest_sha256"]) == 64
    assert len(lineage["embedding_array_sha256"]) == 64


def test_forbidden_sources_are_rejected_before_open() -> None:
    with pytest.raises(ValueError, match="forbidden"):
        POLICY._assert_development_input_path(
            Path("turn_policy_final_v4_test.jsonl")
        )
    with pytest.raises(ValueError, match="tests/data"):
        POLICY._assert_development_input_path(
            ROOT / "tests" / "data" / "public_train.jsonl"
        )
    POLICY._assert_development_input_path(
        FIXTURES / "runtime_train.jsonl"
    )


def test_cli_requires_explicit_source_pins_and_defaults_to_cpu(
    tmp_path: Path,
) -> None:
    arguments = [
        "--runtime-train",
        str(FIXTURES / "runtime_train.jsonl"),
        "--expected-runtime-train-sha256",
        "1" * 64,
        "--runtime-validation",
        str(FIXTURES / "runtime_validation.jsonl"),
        "--expected-runtime-validation-sha256",
        "2" * 64,
        "--mtop-development",
        str(FIXTURES / "mtop_development.jsonl"),
        "--expected-mtop-development-sha256",
        "3" * 64,
        "--expected-product-catalog-sha256",
        "4" * 64,
        "--expected-mtop-map-sha256",
        "5" * 64,
        "--cache-directory",
        str(tmp_path / "development-cache"),
        "--output",
        str(tmp_path / "development-artifact.json"),
    ]

    args = POLICY.parse_args(arguments)

    assert args.device == "cpu"
    assert args.effect_c == 1.0
    assert args.no_effect_c == 1.0
    assert args.selective_guard_delta == 0.05
    assert args.expected_runtime_train_sha256 == "1" * 64
    assert args.expected_runtime_validation_sha256 == "2" * 64
    assert args.expected_mtop_development_sha256 == "3" * 64


def test_artifact_contains_only_hashes_aggregates_and_safe_weights() -> None:
    effect_head = _head(
        "softmax",
        (POLICY.TRIGGER_NEGATIVE, POLICY.TRIGGER_POSITIVE),
    )
    no_effect_head = _head("softmax", POLICY.NO_EFFECT_CLASSES)
    family_head = _head("one_vs_rest", ("app", "system"))
    operation_head = _head("one_vs_rest", ("app.open", "system.time"))
    train_groups = [
        _group(
            "private-train-mission",
            "train",
            POLICY.TRIGGER_POSITIVE,
            ("app",),
            ("app.open",),
        )
    ]
    calibration_groups = [
        _group(
            "private-calibration-mission",
            "validation",
            POLICY.TRIGGER_NEGATIVE,
            (),
            (),
        )
    ]
    evaluation_groups = [
        _group(
            "private-evaluation-mission",
            "validation",
            POLICY.TRIGGER_POSITIVE,
            ("system",),
            ("system.time",),
        )
    ]
    artifact = POLICY.build_text_free_artifact(
        sources=[
            {
                "name": "runtime_train",
                "sha256": "1" * 64,
                "rows": 4,
                "row_fingerprint_sha256": "2" * 64,
                "contains_test": False,
                "embedding_cache_manifest_sha256": "7" * 64,
                "embedding_array_sha256": "8" * 64,
            }
        ],
        catalog_identity={
            "sha256": "3" * 64,
            "public_operations": 169,
            "families": 24,
        },
        encoder_identity={
            "model": "intfloat/multilingual-e5-small",
            "revision": "4" * 40,
            "manifest_sha256": "5" * 64,
            "query_prefix": "query: ",
            "normalize_embeddings": True,
        },
        training_identity={
            "fit_unit": "utterance_l2_normalized_mission_disjoint",
            "linear_solver": "lbfgs",
            "sample_weight": (
                "equal_head_target_source_mass_then_inverse_mission_variants"
            ),
            "effect_c": 1.0,
            "no_effect_c": 1.0,
            "family_c": 4.0,
            "operation_c": 4.0,
            "maximum_families": 8,
            "maximum_operations": 24,
            "validation_seed_sha256": "6" * 64,
            "selective_guard_delta": 0.05,
        },
        train_groups=train_groups,
        calibration_groups=calibration_groups,
        evaluation_groups=evaluation_groups,
        effect_head=effect_head,
        no_effect_head=no_effect_head,
        family_head=family_head,
        operation_head=operation_head,
        thresholds={
            "effect": {
                POLICY.TRIGGER_NEGATIVE: 0.2,
                POLICY.TRIGGER_POSITIVE: 0.25,
            },
            "no_effect_disposition": {
                POLICY.OUTCOME_CONVERSATION: 0.2,
                POLICY.OUTCOME_UNSUPPORTED: 0.25,
            },
            "family": 0.3,
            "operation": 0.4,
            "selective_guards": {
                "supported_effect": POLICY.strict_guard_threshold(
                    [0.4],
                    delta=0.05,
                ),
                "conversation_fast_path": POLICY.strict_guard_threshold(
                    [0.5],
                    delta=0.05,
                ),
            },
        },
        alpha=0.05,
        exclusions={"mtop_contract_structure_mismatch_ambiguous": 2},
        metrics={"groups": 1, "trigger": {"coverage": 1.0}},
    )
    serialized = POLICY._canonical_json_bytes(artifact).decode("utf-8")

    assert artifact["schema"] == "baxy.turn-policy-e5-development.v2"
    assert artifact["status"] == "development_only_not_runtime_authority"
    assert artifact["privacy"] == {
        "contains_text": False,
        "contains_source_ids": False,
        "contains_mission_ids": False,
        "contains_model_responses": False,
        "contains_derived_model_parameters": True,
    }
    assert artifact["constraints"]["execution_authority"] is False
    assert artifact["constraints"]["mtop_candidate_is_advisory_only"] is True
    assert artifact["constraints"]["ood_can_authorize_fast_chat"] is False
    assert artifact["protocol"]["outcome_classes"] == list(
        POLICY.OUTCOME_CLASSES
    )
    assert set(artifact["heads"]) == {
        "effect_gate",
        "no_effect_disposition",
        "family_shortlist",
        "operation_shortlist",
    }
    assert all(
        guard["calibration_false_accepts"] == 0
        for guard in artifact["selective_guards"].values()
    )
    assert "private-train-mission" not in serialized
    assert "private-calibration-mission" not in serialized
    assert "private-evaluation-mission" not in serialized
    for head in artifact["heads"].values():
        body = {key: value for key, value in head.items() if key != "weights_sha256"}
        assert head["weights_sha256"] == POLICY._sha256_bytes(
            POLICY._canonical_json_bytes(body)
        )
    policy_payload = {
        key: artifact[key]
        for key in (
            "constraints",
            "catalog",
            "encoder",
            "training",
            "protocol",
            "heads",
            "conformal",
            "selective_guards",
        )
    }
    evidence_payload = {
        key: artifact[key]
        for key in ("sources", "groups", "exclusions", "metrics")
    }
    assert artifact["integrity"]["policy_payload_sha256"] == (
        POLICY._sha256_bytes(POLICY._canonical_json_bytes(policy_payload))
    )
    assert artifact["integrity"]["evidence_payload_sha256"] == (
        POLICY._sha256_bytes(POLICY._canonical_json_bytes(evidence_payload))
    )


def test_development_tool_has_no_runner_builder_or_remote_model_dependency() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "import build_mtop_turn_evidence" not in source
    assert "import measure_turn_policy" not in source
    assert "local_files_only=True" in source
    assert "allow_pickle=False" in source
    assert "--runtime-train" in source
    assert "--runtime-validation" in source
    assert "--mtop-development" in source
