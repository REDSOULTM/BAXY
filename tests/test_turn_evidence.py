from __future__ import annotations

import hashlib
import json
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import baxy_mind.turn_evidence as evidence_module
from baxy_mind.turn_evidence import (
    CACHE_ENVIRONMENT_VARIABLE,
    CorpusEvidenceReport,
    EVIDENCE_RECORD_SCHEMA_VERSION,
    TurnEvidenceAbstentionPolicy,
    TurnEvidenceIndex,
    TurnEvidenceMatch,
    TurnEvidenceRecord,
    TurnEvidenceService,
    TurnEvidenceThresholds,
    load_abstention_policy,
    load_private_corpus,
    split_for_mission,
    summarize_match_confidence,
    training_examples,
)


def _row(
    source_id: str,
    text: str,
    *,
    mission: str,
    row_class: str = "conversation_question",
    operations: list[str] | None = None,
    possible_chain: bool = False,
    **overrides: object,
) -> dict[str, object]:
    row: dict[str, object] = {
        "message_id": source_id,
        "text_literal": text,
        "canonical_mission_id": mission,
        "class": row_class,
        "operations": operations or [],
        "possible_chain": possible_chain,
        "dedup_status": "canonical_source",
        "redacted": False,
        "data_or_preferences": [],
    }
    row.update(overrides)
    return row


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_corpus_loader_filters_private_noncanonical_and_ambiguous_rows(tmp_path: Path) -> None:
    rows = [
        _row("safe", "abre la calculadora", mission="app-open", row_class="user_mission", operations=["app.open"]),
        _row("private", "recuerda mi secreto", mission="memory", row_class="user_mission", operations=["memory.save"]),
        _row("preference", "mi nombre es Ana", mission="name", data_or_preferences=["person_name"]),
        _row("redacted", "dato oculto", mission="redacted", redacted=True),
        _row("duplicate", "otra frase", mission="dup", dedup_status="duplicate"),
        _row("wrong-a", "abre algo", mission="amb-a"),
        _row("wrong-b", "abre algo", mission="amb-b", row_class="user_mission", operations=["app.open"]),
        _row("requirement", "debe haber una acción", mission="req", row_class="product_requirement"),
    ]
    corpus = tmp_path / "corpus.jsonl"
    _write_rows(corpus, rows)

    records, report = load_private_corpus(corpus)

    assert [(record.source_id, record.mode, record.families) for record in records] == [
        ("safe", "action", ("app",)),
    ]
    assert report.source_rows == len(rows)
    assert report.excluded_private == 3
    assert report.excluded_noncanonical == 1
    assert report.excluded_ambiguous == 2
    assert report.excluded_out_of_scope == 1
    assert report.source_sha256 == hashlib.sha256(corpus.read_bytes()).hexdigest()


def test_training_split_is_stable_and_never_leaks_a_mission() -> None:
    records = [
        TurnEvidenceRecord("abre calculadora", "action", ("app",), "same-mission", "one"),
        TurnEvidenceRecord("inicia calculadora", "action", ("app",), "same-mission", "two"),
        TurnEvidenceRecord("explica este concepto", "conversation", (), "other-mission", "three"),
    ]

    rows = training_examples(records)

    by_group: dict[str, set[str]] = {}
    for row in rows:
        by_group.setdefault(str(row["group"]), set()).add(str(row["split"]))
        assert row["provenance"]["license"] == "private-local"
    assert all(len(splits) == 1 for splits in by_group.values())
    assert by_group["same-mission"] == {split_for_mission("same-mission")}


def test_promoted_record_requires_provenance_and_preserves_upstream_holdout(tmp_path: Path) -> None:
    rows = [
        {
            "schema": EVIDENCE_RECORD_SCHEMA_VERSION,
            "text": "abre la aplicacion de musica",
            "mode": "action",
            "families": ["app"],
            "mission_id": "public-group",
            "source_id": "public-one",
            "split": "test",
            "provenance": {"dataset": "licensed", "license": "CC-BY-4.0"},
        },
        {
            "schema": EVIDENCE_RECORD_SCHEMA_VERSION,
            "text": "sin procedencia no entra",
            "mode": "conversation",
            "families": [],
            "mission_id": "bad",
            "source_id": "bad",
            "split": "train",
        },
    ]
    corpus = tmp_path / "promoted.jsonl"
    _write_rows(corpus, rows)

    records, report = load_private_corpus(corpus)

    assert [(record.source_id, record.split) for record in records] == [("public-one", "test")]
    assert report.excluded_out_of_scope == 1
    assert training_examples(records)[0]["split"] == "test"
    assert training_examples(records)[0]["provenance"] == {
        "dataset": "licensed",
        "license": "CC-BY-4.0",
    }


def test_retrieval_prefers_candidate_family_and_diversifies_missions() -> None:
    records = [
        TurnEvidenceRecord("abre una aplicación", "action", ("app",), "m1", "one"),
        TurnEvidenceRecord("inicia un programa", "action", ("app",), "m1", "two"),
        TurnEvidenceRecord("sube el volumen", "action", ("audio",), "m2", "three"),
        TurnEvidenceRecord("explica el resultado", "conversation", (), "m3", "four"),
    ]
    vectors = np.asarray(
        [[1.0, 0.0], [0.99, 0.01], [0.95, 0.05], [0.8, 0.2]],
        dtype=np.float32,
    )
    report = CorpusEvidenceReport("a" * 64, 4, 4, 0, 0, 0, 0)
    index = TurnEvidenceIndex(records, vectors, report)
    policy = TurnEvidenceAbstentionPolicy.permissive(
        runtime_source_sha256=report.source_sha256,
        encoder_identity=index.encoder_identity,
        neighbors=3,
        calibration_fingerprint="fixture",
        calibration_rows=1,
    )

    result = index.retrieve(
        "abre el bloc de notas",
        lambda _texts: np.asarray([[1.0, 0.0]], dtype=np.float32),
        ["app.open"],
        policy=policy,
        limit=3,
    )

    assert result[0]["families"] == ["app"]
    assert len(result) == 3
    assert all("example" not in card for card in result)
    assert sum(card["families"] == ["app"] for card in result) == 1
    assert result[0] == {
        "mode": "action",
        "families": ["app"],
        "score": 1.0,
        "candidate_family_match": True,
    }


def test_semantic_score_outranks_candidate_family_hint() -> None:
    records = [
        TurnEvidenceRecord("abre una aplicación", "action", ("app",), "m1", "one"),
        TurnEvidenceRecord("te explico la causa", "conversation", (), "m2", "two"),
    ]
    vectors = np.asarray([[0.1, 0.995], [1.0, 0.0]], dtype=np.float32)
    report = CorpusEvidenceReport("a" * 64, 2, 2, 0, 0, 0, 0)
    index = TurnEvidenceIndex(records, vectors, report)

    matches = index.search(
        "por qué pasó",
        lambda _texts: np.asarray([[1.0, 0.0]], dtype=np.float32),
        ["app.open"],
        limit=2,
    )

    assert matches[0].record.mode == "conversation"
    assert not matches[0].candidate_family_match
    assert matches[1].candidate_family_match


def test_exact_top_k_matches_stable_sorted_golden_at_score_boundary() -> None:
    scores = np.asarray(
        [1.0, 1.0, 1.0, 0.0, -0.0, 0.5, 0.5, -1.0],
        dtype=np.float32,
    )
    indices = np.asarray([1, 0, 2, 6, 5, 4, 3, 7], dtype=np.intp)
    source_ids = ("dup", "dup", "z", "b", "a", "same", "same", "x")
    family_matches = (False, False, False, True, False, True, False, True)

    by_source = evidence_module._exact_top_k_indices(
        scores,
        indices,
        limit=4,
        suffix_key=lambda index: (source_ids[index],),
    )
    by_family_then_source = evidence_module._exact_top_k_indices(
        scores,
        indices,
        limit=4,
        suffix_key=lambda index: (
            family_matches[index],
            source_ids[index],
        ),
    )

    assert by_source == [2, 1, 0, 6]
    assert by_family_then_source == [2, 1, 0, 5]
    for limit in range(1, len(indices) + 2):
        assert evidence_module._exact_top_k_indices(
            scores,
            indices,
            limit=limit,
            suffix_key=lambda index: (source_ids[index],),
        ) == sorted(
            (int(index) for index in indices),
            key=lambda index: (float(scores[index]), source_ids[index]),
            reverse=True,
        )[:limit]


@pytest.mark.parametrize("non_finite", [float("nan"), float("inf"), float("-inf")])
def test_exact_top_k_uses_historical_sort_for_non_finite_scores(
    non_finite: float,
) -> None:
    scores = np.asarray(
        [1.0, 1.0, 0.0, -0.0, 0.5, 0.5, -1.0],
        dtype=np.float32,
    )
    scores[3] = non_finite
    indices = np.asarray([5, 0, 3, 1, 6, 2, 4], dtype=np.intp)
    source_ids = ("dup", "dup", "z", "b", "a", "same", "same")
    family_matches = (False, True, False, True, False, True, False)
    suffixes = (
        lambda index: (source_ids[index],),
        lambda index: (family_matches[index], source_ids[index]),
    )

    for suffix_key in suffixes:
        expected = sorted(
            (int(index) for index in indices),
            key=lambda index: (float(scores[index]), *suffix_key(index)),
            reverse=True,
        )[:4]
        assert evidence_module._exact_top_k_indices(
            scores,
            indices,
            limit=4,
            suffix_key=suffix_key,
        ) == expected


def test_exact_top_k_matches_sorted_across_deterministic_adversarial_cases() -> None:
    random = np.random.default_rng(84_621)
    score_pool = np.asarray(
        [-3.0, -1.0, -0.0, 0.0, 0.25, 0.25, 1.0, 1.0, 3.0],
        dtype=np.float32,
    )
    source_pool = np.asarray(["a", "a", "b", "c", "z"], dtype=object)

    for _ in range(256):
        count = int(random.integers(2, 80))
        scores = random.choice(score_pool, size=count)
        source_ids = random.choice(source_pool, size=count)
        family_matches = random.integers(0, 2, size=count, dtype=np.int8)
        indices = random.permutation(count).astype(np.intp)
        limit = int(random.integers(1, count))

        def suffix_key(index: int) -> tuple[bool, str]:
            return bool(family_matches[index]), str(source_ids[index])

        expected = sorted(
            (int(index) for index in indices),
            key=lambda index: (float(scores[index]), *suffix_key(index)),
            reverse=True,
        )[:limit]

        assert evidence_module._exact_top_k_indices(
            scores,
            indices,
            limit=limit,
            suffix_key=suffix_key,
        ) == expected


def test_candidate_training_index_array_is_frozen_native_index_storage() -> None:
    records = [
        TurnEvidenceRecord("", "action", ("app",), "m1", "one", "train"),
        TurnEvidenceRecord("", "plan", ("web",), "m2", "two", "train"),
        TurnEvidenceRecord("", "conversation", (), "m3", "three", "train"),
    ]
    report = CorpusEvidenceReport("a" * 64, 3, 3, 0, 0, 0, 0)
    index = TurnEvidenceIndex(
        records,
        np.eye(3, dtype=np.float32),
        report,
    )

    assert index._candidate_training_index_array.dtype == np.intp
    assert index._candidate_training_index_array.tolist() == [0, 1]
    assert not index._candidate_training_index_array.flags.writeable
    with pytest.raises(ValueError):
        index._candidate_training_index_array[0] = 2


def test_candidate_families_are_a_diverse_broad_union_without_mode_authority() -> None:
    records = [
        TurnEvidenceRecord("", "action", ("app",), "m1", "one", "train"),
        TurnEvidenceRecord("", "action", ("app",), "m1", "two", "train"),
        TurnEvidenceRecord("", "action", ("audio",), "m2", "three", "train"),
        TurnEvidenceRecord("", "conversation", (), "m3", "four", "train"),
        TurnEvidenceRecord(
            "",
            "plan",
            ("browser", "web"),
            "m4",
            "five",
            "train",
        ),
    ]
    vectors = np.asarray(
        [
            [1.0, 0.0],
            [0.99, 0.01],
            [0.95, 0.05],
            [0.90, 0.10],
            [0.85, 0.15],
        ],
        dtype=np.float32,
    )
    report = CorpusEvidenceReport("a" * 64, 5, 5, 0, 0, 0, 0)
    index = TurnEvidenceIndex(records, vectors, report)

    families = index.candidate_families(
        "pedido",
        lambda _texts: np.asarray([[1.0, 0.0]], dtype=np.float32),
        neighbors=4,
    )

    assert families == ("app", "audio", "web", "browser")
    assert "conversation" not in families
    assert "action" not in families


def test_candidate_families_use_only_canonical_public_train_records() -> None:
    records = [
        TurnEvidenceRecord("", "action", ("app",), "historical", "one"),
        TurnEvidenceRecord(
            "",
            "action",
            ("audio",),
            "validation",
            "two",
            "validation",
        ),
        TurnEvidenceRecord(
            "",
            "action",
            ("browser",),
            "test",
            "three",
            "test",
        ),
        TurnEvidenceRecord(
            "",
            "conversation",
            ("notification",),
            "wrong-mode",
            "four",
            "train",
        ),
        TurnEvidenceRecord(
            "",
            "action",
            ("not-valid",),
            "bad-family",
            "five",
            "train",
        ),
        TurnEvidenceRecord(
            "",
            "action",
            ("calendar", "calendar"),
            "duplicate-family",
            "six",
            "train",
        ),
        TurnEvidenceRecord(
            "",
            "action",
            ("calendar",),
            "train-action",
            "seven",
            "train",
        ),
        TurnEvidenceRecord(
            "",
            "plan",
            ("web",),
            "train-plan",
            "eight",
            "train",
        ),
    ]
    vectors = np.asarray(
        [
            [1.0, 0.0],
            [0.99, 0.01],
            [0.98, 0.02],
            [0.97, 0.03],
            [0.96, 0.04],
            [0.95, 0.05],
            [0.90, 0.10],
            [0.80, 0.20],
        ],
        dtype=np.float32,
    )
    report = CorpusEvidenceReport("a" * 64, 8, 8, 0, 0, 0, 0)
    index = TurnEvidenceIndex(records, vectors, report)

    families = index.candidate_families(
        "pedido",
        lambda _texts: np.asarray([[1.0, 0.0]], dtype=np.float32),
        neighbors=8,
    )

    assert families == ("calendar", "web")


def test_candidate_expansion_is_identical_when_evidence_retrieval_is_disabled() -> None:
    records = [
        TurnEvidenceRecord("", "action", ("app",), "m1", "one", "train"),
    ]
    vectors = np.asarray([[1.0, 0.0]], dtype=np.float32)
    report = CorpusEvidenceReport("a" * 64, 1, 1, 0, 0, 0, 0)
    index = TurnEvidenceIndex(records, vectors, report)
    encoder = lambda _texts: np.asarray([[1.0, 0.0]], dtype=np.float32)
    enabled = TurnEvidenceService(evidence_enabled=True)
    disabled = TurnEvidenceService(evidence_enabled=False)
    enabled._index = index
    disabled._index = index

    assert enabled.candidate_families("abre", encoder) == ("app",)
    assert disabled.candidate_families("abre", encoder) == ("app",)
    assert disabled.retrieve("abre", encoder, ["app.open"]) == []


def test_service_stop_interrupts_readiness_wait_and_joins_idempotently(
    tmp_path: Path,
) -> None:
    corpus = tmp_path / "turn-evidence.jsonl"
    corpus.write_text("", encoding="utf-8")
    service = TurnEvidenceService(corpus)
    readiness_checked = threading.Event()
    encoder_calls: list[tuple[str, ...]] = []

    def is_encoder_ready() -> bool:
        readiness_checked.set()
        return False

    def encoder(texts):
        encoder_calls.append(tuple(texts))
        raise AssertionError("encoder must not run after cancellation")

    service.start(encoder, is_encoder_ready)
    assert readiness_checked.wait(timeout=1.0)

    started_at = time.monotonic()
    assert service.stop(timeout=0.25)
    elapsed = time.monotonic() - started_at

    assert elapsed < 0.5
    assert service.state == "stopped"
    assert encoder_calls == []
    assert service.stop(timeout=0.0)


def test_service_cancelled_during_corpus_load_never_calls_encoder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    corpus = tmp_path / "turn-evidence.jsonl"
    corpus.write_text("", encoding="utf-8")
    source_sha256 = hashlib.sha256(b"").hexdigest()
    load_started = threading.Event()
    release_load = threading.Event()
    encoder_calls: list[tuple[str, ...]] = []

    def blocked_load(_path: Path):
        load_started.set()
        release_load.wait(timeout=2.0)
        return (
            [TurnEvidenceRecord("fixture", "action", ("app",), "m1", "s1")],
            CorpusEvidenceReport(source_sha256, 1, 1, 0, 0, 0, 0),
        )

    def encoder(texts):
        encoder_calls.append(tuple(texts))
        return np.ones((len(texts), 1), dtype=np.float32)

    monkeypatch.setattr(evidence_module, "load_private_corpus", blocked_load)
    service = TurnEvidenceService(corpus)
    service.start(encoder, lambda: True)
    assert load_started.wait(timeout=1.0)
    assert not service.stop(timeout=0.0)

    release_load.set()
    assert service.stop(timeout=0.5)

    assert service.state == "stopped"
    assert encoder_calls == []


def test_confidence_summarizes_score_margin_agreement_and_entropy() -> None:
    matches = [
        TurnEvidenceMatch(
            TurnEvidenceRecord("", "action", ("app",), "m1", "one"),
            0.90,
            False,
        ),
        TurnEvidenceMatch(
            TurnEvidenceRecord("", "action", ("app",), "m2", "two"),
            0.80,
            False,
        ),
        TurnEvidenceMatch(
            TurnEvidenceRecord("", "conversation", (), "m3", "three"),
            0.70,
            False,
        ),
    ]

    confidence = summarize_match_confidence(matches)

    assert confidence.neighbor_count == 3
    assert confidence.top1_score == 0.9
    assert np.isclose(confidence.score_margin, 0.1)
    assert confidence.predicted_mode == "action"
    assert 0.0 < confidence.mode_entropy < 1.0
    assert confidence.mode_agreement > 0.5
    assert confidence.predicted_family == "app"
    assert 0.0 < confidence.family_entropy < 1.0


def test_retrieval_abstains_without_policy_or_when_confidence_is_low() -> None:
    records = [
        TurnEvidenceRecord("", "action", ("app",), "m1", "one"),
        TurnEvidenceRecord("", "conversation", (), "m2", "two"),
    ]
    report = CorpusEvidenceReport("b" * 64, 2, 2, 0, 0, 0, 0)
    index = TurnEvidenceIndex(
        records,
        np.asarray([[1.0, 0.0], [0.99, 0.01]], dtype=np.float32),
        report,
    )
    encoder = lambda _texts: np.asarray([[1.0, 0.0]], dtype=np.float32)
    strict = TurnEvidenceAbstentionPolicy(
        runtime_source_sha256=report.source_sha256,
        encoder_identity=index.encoder_identity,
        neighbors=2,
        actionable=TurnEvidenceThresholds(
            minimum_top1_score=0.0,
            minimum_score_margin=0.5,
            minimum_mode_agreement=0.0,
            maximum_mode_entropy=1.0,
            minimum_family_agreement=0.0,
            maximum_family_entropy=1.0,
        ),
        conversational=TurnEvidenceThresholds.permissive(),
        calibration_fingerprint="fixture",
        calibration_rows=1,
    )

    assert index.retrieve("abre algo", encoder, ["app.open"]) == []
    assert (
        index.retrieve(
            "abre algo",
            encoder,
            ["app.open"],
            policy=strict,
        )
        == []
    )


def test_loader_rejects_legacy_policy_that_could_promote_action(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("BAXY_MIND_TURN_EVIDENCE_POLICY", raising=False)
    policy = TurnEvidenceAbstentionPolicy.permissive(
        runtime_source_sha256="c" * 64,
        encoder_identity="fixture",
        neighbors=5,
        calibration_fingerprint="d" * 64,
        calibration_rows=123,
    )
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy.to_dict()), encoding="utf-8")

    with pytest.raises(ValueError, match="one-sided"):
        load_abstention_policy(path)


def test_cache_is_bound_to_encoder_identity_and_detects_corruption(
    tmp_path: Path,
    monkeypatch,
) -> None:
    corpus = tmp_path / "promoted.jsonl"
    _write_rows(
        corpus,
        [
            {
                "schema": EVIDENCE_RECORD_SCHEMA_VERSION,
                "text": "frase sensible que no debe quedar en cache",
                "mode": "action",
                "families": ["app"],
                "mission_id": "one",
                "source_id": "one",
                "split": "train",
                "provenance": {"dataset": "fixture", "license": "CC-BY-4.0"},
            }
        ],
    )
    cache = tmp_path / "cache"
    cache.mkdir()
    stale_metadata = cache / "stale-v3.json"
    stale_vectors = stale_metadata.with_suffix(".npy")
    with stale_vectors.open("wb") as handle:
        np.save(handle, np.asarray([[1.0, 0.0]], dtype=np.float32))
    stale_metadata.write_text(
        json.dumps(
            {
                "schema": "baxy.turn-evidence.v3",
                "source_sha256": hashlib.sha256(corpus.read_bytes()).hexdigest(),
                "encoder_identity": "fixture-a",
                "records": [
                    {
                        "text": "frase sensible que no debe quedar en cache",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(CACHE_ENVIRONMENT_VARIABLE, str(cache))
    calls = 0

    def encoder(texts):
        nonlocal calls
        calls += 1
        return np.asarray([[1.0, 0.0] for _ in texts], dtype=np.float32)

    first = TurnEvidenceIndex.from_corpus(
        corpus,
        encoder,
        encoder_identity="fixture-a",
    )
    assert first.count == 1
    assert calls == 1
    assert not stale_metadata.exists()
    assert not stale_vectors.exists()
    metadata_text = next(cache.glob("*.json")).read_text(encoding="utf-8")
    assert "frase sensible que no debe quedar en cache" not in metadata_text
    assert '"text"' not in metadata_text
    assert '"contains_text":false' in metadata_text

    warm = TurnEvidenceIndex.from_corpus(
        corpus,
        lambda _texts: (_ for _ in ()).throw(AssertionError("cache miss")),
        encoder_identity="fixture-a",
    )
    assert warm.count == 1
    assert warm._records[0].text == ""
    assert calls == 1

    other = TurnEvidenceIndex.from_corpus(
        corpus,
        encoder,
        encoder_identity="fixture-b",
    )
    assert other.encoder_identity == "fixture-b"
    assert calls == 2
    assert len(list(cache.glob("*.json"))) == 2

    fixture_a_metadata = next(
        path
        for path in cache.glob("*.json")
        if json.loads(path.read_text(encoding="utf-8"))["encoder_identity"]
        == "fixture-a"
    )
    vectors_path = fixture_a_metadata.with_suffix(".npy")
    vectors_path.write_bytes(vectors_path.read_bytes()[:-1] + b"x")
    rebuilt = TurnEvidenceIndex.from_corpus(
        corpus,
        encoder,
        encoder_identity="fixture-a",
    )
    assert rebuilt.count == 1
    assert calls == 3
