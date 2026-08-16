"""Audit a possible one-sided turn-evidence latency fast path.

This experiment never dispatches a Core operation and never changes runtime
assets.  Its default ``overlap`` scope reuses only the promoted turn-evidence
vectors already present in the verified local v4 cache.  ``--scope full``
explicitly encodes the remaining canonical oracle texts on CPU and is kept
opt-in because it is materially heavier.

The audit deliberately does not implement the fast path.  It first proves
whether a valid conversation signal plus ``G=no_effect`` could bypass the
large primary policy decode without changing clarification, effect or visible
reply semantics.  A later physical A/B is allowed only if every blocker
reported here reaches zero on the full scope.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import unicodedata
from typing import Any, Iterable, Sequence

import numpy as np


REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from baxy_mind import __main__ as sidecar_module  # noqa: E402
from baxy_mind.effect_intent import (  # noqa: E402
    resolve_explicit_clarification,
    resolve_explicit_effects,
)
from baxy_mind.llm import derive_semantic_effect_state  # noqa: E402
from baxy_mind.turn_evidence import (  # noqa: E402
    DEFAULT_ENCODER_IDENTITY,
    TurnEvidenceIndex,
    _cache_key,
    load_abstention_policy,
    load_private_corpus,
)
from baxy_mind.turn_probe import (  # noqa: E402
    OneSidedTurnEvidencePolicy,
    summarize_conversation_neighbors,
)
from scripts.measure_mind_budget import (  # noqa: E402
    build_workload,
    write_json_atomic,
)


DEFAULT_RUNTIME = REPO / "tests" / "data" / "turn_evidence_runtime.v1.jsonl"
DEFAULT_ORACLE = (
    REPO / "artifacts" / "historical_exhaustive" / "runtime_oracle.jsonl"
)
DEFAULT_LANGUAGE_SCOPE = (
    REPO
    / "artifacts"
    / "historical_exhaustive"
    / "runtime_language_scope.jsonl"
)
DEFAULT_HISTORICAL_MESSAGES = (
    REPO / "tests" / "data" / "historical_messages.jsonl"
)
DEFAULT_BASELINE = (
    REPO
    / "artifacts"
    / "historical_exhaustive"
    / "runtime_model_gate.final24.merged.jsonl"
)
DEFAULT_STAGE_ARTIFACT = (
    REPO
    / "artifacts"
    / "fixes"
    / "invalid_empty_length_retry_temperature_ab_20260729.json"
)
DEFAULT_CATALOG = (
    REPO / "src" / "Baxy.Kernel" / "Operations" / "ProductCatalog.cs"
)
DEFAULT_OUTPUT = (
    REPO
    / "artifacts"
    / "fixes"
    / "turn_evidence_fastpath_overlap_audit_20260730.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"{path} contiene una fila que no es objeto")
                rows.append(value)
    return rows


def _normalized_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def _catalog_operations(path: Path) -> tuple[str, ...]:
    operations = tuple(
        sorted(
            set(
                re.findall(
                    r'Descriptor\(\s*"([a-z0-9.]+)"',
                    path.read_text(encoding="utf-8"),
                )
            )
        )
    )
    if len(operations) < 100:
        raise ValueError("no se pudo leer el catálogo canónico")
    return operations


def _counter(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _cross_counter(
    values: Iterable[tuple[str, str]],
) -> dict[str, int]:
    counts = Counter(values)
    return {
        f"{left}|{right}": count
        for (left, right), count in sorted(counts.items())
    }


def _policy_signal(
    index: TurnEvidenceIndex,
    policy: OneSidedTurnEvidencePolicy,
    vector: np.ndarray,
    candidate_operations: Sequence[str] = (),
) -> tuple[bool, float, tuple[str, ...]]:
    probe_emits, distribution = policy.probe.emits_conversation(vector)
    if not probe_emits:
        return False, float(distribution["conversation"]), ()
    ranking = index._rank_query(  # noqa: SLF001 - experiment audits exact runtime
        vector,
        candidate_operations,
        limit=max(128, policy.neighbors * 16),
    )
    diverse = []
    missions: set[str] = set()
    for match in ranking:
        if match.record.mission_id in missions:
            continue
        diverse.append(match)
        missions.add(match.record.mission_id)
        if len(diverse) >= policy.neighbors:
            break
    signals = summarize_conversation_neighbors(
        [(match.score, match.record.mode) for match in diverse]
    )
    accepted = (
        signals.neighbor_count >= policy.neighbors
        and policy.conversation_knn.accepts(signals)
    )
    return (
        accepted,
        float(distribution["conversation"]),
        tuple(match.record.mode for match in diverse),
    )


def _load_vectors(
    *,
    runtime: Path,
    oracle_rows: Sequence[dict[str, Any]],
    scope: str,
    device: str,
    batch_size: int,
) -> tuple[
    TurnEvidenceIndex,
    dict[str, np.ndarray],
    dict[str, Any],
]:
    records, report = load_private_corpus(runtime)
    cache_key, source_sha256 = _cache_key(
        runtime.resolve(),
        DEFAULT_ENCODER_IDENTITY,
    )
    cache_root = Path(
        os.environ.get(
            "BAXY_MIND_TURN_EVIDENCE_CACHE",
            str(Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime" / "turn-evidence"),
        )
    )
    vectors_path = cache_root / f"{cache_key}.npy"
    metadata_path = cache_root / f"{cache_key}.json"
    if not vectors_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError("falta el par promovido de caché turn-evidence v4")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if (
        metadata.get("source_sha256") != source_sha256
        or metadata.get("encoder_identity") != DEFAULT_ENCODER_IDENTITY
        or metadata.get("contains_text") is not False
        or metadata.get("vectors_sha256") != _sha256(vectors_path)
    ):
        raise ValueError("el caché turn-evidence no coincide con runtime/encoder")
    vectors = np.load(vectors_path, allow_pickle=False)
    index = TurnEvidenceIndex(records, vectors, report)
    by_text = {
        _normalized_text(record.text): np.asarray(vectors[position])
        for position, record in enumerate(records)
    }
    missing = [
        row
        for row in oracle_rows
        if _normalized_text(str(row["text_literal"])) not in by_text
    ]
    encoded_rows = 0
    if scope == "full" and missing:
        # Import and construct the real encoder only in explicitly requested
        # full mode.  The default audit remains cache-only and thermally quiet.
        from baxy_mind.router import SemanticEncoder

        encoder = SemanticEncoder(device=device)
        for offset in range(0, len(missing), batch_size):
            batch = missing[offset : offset + batch_size]
            texts = [str(row["text_literal"]) for row in batch]
            matrix = np.asarray(encoder.encode(texts), dtype=np.float32)
            if matrix.shape != (len(batch), index.dimensions):
                raise ValueError("el encoder devolvió una matriz incompatible")
            for row, vector in zip(batch, matrix, strict=True):
                by_text[_normalized_text(str(row["text_literal"]))] = vector
            encoded_rows += len(batch)
    return (
        index,
        by_text,
        {
            "cache_key": cache_key,
            "cache_metadata_sha256": _sha256(metadata_path),
            "cache_vectors_sha256": _sha256(vectors_path),
            "cache_rows": index.count,
            "oracle_overlap_rows": len(oracle_rows) - len(missing),
            "oracle_missing_rows": len(missing),
            "newly_encoded_rows": encoded_rows,
        },
    )


def _routing_disposition(
    text: str,
    operations: Sequence[str],
) -> str:
    if resolve_explicit_clarification(text, operations) is not None:
        return "explicit_clarification"
    if resolve_explicit_effects(text, operations, ()) is not None:
        return "explicit_effect"
    if sidecar_module._explicit_social_turn_decision(text) is not None:
        return "explicit_social"
    if (
        sidecar_module._explicit_nonunderstanding_turn_decision(text, [])
        is not None
    ):
        return "explicit_nonunderstanding"
    return "evidence_queried"


def _language_evidence(
    historical_messages: Path,
    target_oracle: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    labels_by_hash: dict[str, set[str]] = {}
    for row in _read_jsonl(historical_messages):
        labels_by_hash.setdefault(str(row["text_sha256"]), set()).add(
            str(row.get("language") or "")
        )
    joined: list[str] = []
    ambiguous = 0
    for row in target_oracle:
        labels = labels_by_hash.get(str(row["text_sha256"]))
        if not labels:
            continue
        if len(labels) != 1:
            ambiguous += 1
            continue
        joined.append(next(iter(labels)))
    directly_mappable = sum(
        label in {"es", "en", "spanglish"}
        for label in joined
    )
    return {
        "historical_hash_overlap": len(joined) + ambiguous,
        "unambiguous_labels": len(joined),
        "ambiguous_labels": ambiguous,
        "label_counts": _counter(joined),
        "direct_es_en_mixed_labels": directly_mappable,
        "direct_rate_on_target_oracle": round(
            directly_mappable / len(target_oracle) if target_oracle else 0.0,
            9,
        ),
        "runtime_authority": "none",
        "gate_status": "not_certified_against_L_output",
        "reason": (
            "source language metadata is not an installed runtime asset and "
            "ADR-0009 forbids compiling corpus texts into phrase rules"
        ),
    }


def _stage_projection(
    path: Path,
    signal_effect_by_normalized_text: dict[str, str],
) -> dict[str, Any]:
    artifact = json.loads(path.read_text(encoding="utf-8"))
    workload = {
        item.case_id: item
        for item in build_workload()
        if (
            item.request_type == "turn.decide"
            and _normalized_text(str(item.message.get("text") or ""))
            in signal_effect_by_normalized_text
        )
    }
    rows: list[dict[str, Any]] = []
    for arm in artifact.get("arms", []):
        if not isinstance(arm, dict) or arm.get("profile") != "baseline":
            continue
        posts_by_case: dict[str, list[dict[str, Any]]] = {}
        for post in arm.get("posts", []):
            if not isinstance(post, dict):
                continue
            case_id = str(post.get("case_id") or "")
            if case_id in workload:
                posts_by_case.setdefault(case_id, []).append(post)
        for case_id, posts in sorted(posts_by_case.items()):
            policy_posts = [post for post in posts if post.get("stage") == "P"]
            guard_posts = [post for post in posts if post.get("stage") == "G"]
            chat_posts = [post for post in posts if post.get("stage") == "chat"]
            if not policy_posts or not guard_posts:
                continue
            try:
                policy_raw = json.loads(str(policy_posts[-1].get("content") or ""))
                guard_raw = json.loads(str(guard_posts[-1].get("content") or ""))
            except json.JSONDecodeError:
                continue
            work = workload.get(case_id)
            history = work.message.get("history", []) if work is not None else None
            normalized_work_text = _normalized_text(
                str(work.message.get("text") or "") if work is not None else ""
            )
            first_chat = str(chat_posts[0].get("content_sha256") or "") if chat_posts else ""
            last_chat = str(chat_posts[-1].get("content_sha256") or "") if chat_posts else ""
            rows.append(
                {
                    "run_id": str(arm.get("run_id") or ""),
                    "case_id": case_id,
                    "oracle_expected_effect": (
                        signal_effect_by_normalized_text.get(
                            normalized_work_text,
                            "",
                        )
                    ),
                    "history_empty": history == [],
                    "p_mode": str(policy_raw.get("mode") or ""),
                    "p_conversation_kind": str(
                        policy_raw.get("conversation_kind") or ""
                    ),
                    "g_state": derive_semantic_effect_state(guard_raw),
                    "g_reported_effect_count": str(
                        guard_raw.get("effect_count") or ""
                    ),
                    "chat_posts": len(chat_posts),
                    "first_last_chat_equal": bool(first_chat)
                    and first_chat == last_chat,
                }
            )
    unique_cases = sorted({row["case_id"] for row in rows})
    forced_knowledge_changes = sorted(
        {
            row["case_id"]
            for row in rows
            if (
                row["history_empty"]
                and row["g_state"] == "no_effect"
                and row["p_mode"] == "conversation"
                and row["p_conversation_kind"] != "knowledge"
                and not row["first_last_chat_equal"]
            )
        }
    )
    g_false_no_effect_cases = sorted(
        {
            row["case_id"]
            for row in rows
            if (
                row["oracle_expected_effect"] != "none"
                and row["g_state"] == "no_effect"
            )
        }
    )
    p_clarify_under_condition_cases = sorted(
        {
            row["case_id"]
            for row in rows
            if (
                row["history_empty"]
                and row["g_state"] == "no_effect"
                and row["p_mode"] == "clarify"
            )
        }
    )
    return {
        "source_rows": len(rows),
        "unique_cases": len(unique_cases),
        "case_ids": unique_cases,
        "p_mode": _counter(str(row["p_mode"]) for row in rows),
        "p_conversation_kind": _counter(
            str(row["p_conversation_kind"]) for row in rows
        ),
        "g_state": _counter(str(row["g_state"]) for row in rows),
        "g_not_no_effect_rows": sum(
            row["g_state"] != "no_effect" for row in rows
        ),
        "p_clarify_rows": sum(row["p_mode"] == "clarify" for row in rows),
        "g_false_no_effect_case_ids": g_false_no_effect_cases,
        "g_false_no_effect_cases": len(g_false_no_effect_cases),
        "p_clarify_under_condition_case_ids": (
            p_clarify_under_condition_cases
        ),
        "p_clarify_under_condition_cases": len(
            p_clarify_under_condition_cases
        ),
        "forced_knowledge_changed_case_ids": forced_knowledge_changes,
        "forced_knowledge_changed_cases": len(forced_knowledge_changes),
        "rows": rows,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    runtime = args.runtime.resolve(strict=True)
    oracle = args.oracle.resolve(strict=True)
    language_scope = args.language_scope.resolve(strict=True)
    historical_messages = args.historical_messages.resolve(strict=True)
    baseline = args.baseline.resolve(strict=True)
    stage_artifact = args.stage_artifact.resolve(strict=True)
    catalog = args.catalog.resolve(strict=True)
    policy_path = args.policy.resolve(strict=True) if args.policy else None
    policy = load_abstention_policy(policy_path)
    if not isinstance(policy, OneSidedTurnEvidencePolicy):
        raise ValueError("no se cargó la política one-sided promovida")

    scope_by_case = {
        str(row["case_id"]): str(row["scope"])
        for row in _read_jsonl(language_scope)
    }
    all_oracle = _read_jsonl(oracle)
    target_oracle = [
        row
        for row in all_oracle
        if scope_by_case.get(str(row["case_id"])) == "target"
    ]
    language_evidence = _language_evidence(
        historical_messages,
        target_oracle,
    )
    index, vectors_by_text, vector_report = _load_vectors(
        runtime=runtime,
        oracle_rows=target_oracle,
        scope=args.scope,
        device=args.device,
        batch_size=args.batch_size,
    )
    if not policy.is_compatible(
        source_sha256=index.report.source_sha256,
        encoder_identity=index.encoder_identity,
        dimensions=index.dimensions,
    ):
        raise ValueError("la política no coincide con el índice promovido")

    operations = _catalog_operations(catalog)
    signal_rows: list[dict[str, Any]] = []
    candidate_tie_sensitive_ids: list[str] = []
    evaluated_rows = 0
    for row in target_oracle:
        vector = vectors_by_text.get(
            _normalized_text(str(row["text_literal"]))
        )
        if vector is None:
            continue
        evaluated_rows += 1
        accepted_without_candidates, probability, neighbor_modes = _policy_signal(
            index,
            policy,
            vector,
        )
        accepted_with_all_candidates, _, _ = _policy_signal(
            index,
            policy,
            vector,
            operations,
        )
        if accepted_without_candidates != accepted_with_all_candidates:
            candidate_tie_sensitive_ids.append(str(row["case_id"]))
        # A real shortlist lies between both tie-break extremes. Only rows
        # accepted under both are safe to count without starting Core merely
        # to reconstruct candidate descriptions for this read-only audit.
        if not (
            accepted_without_candidates
            and accepted_with_all_candidates
        ):
            continue
        signal_rows.append(
            {
                "case_id": str(row["case_id"]),
                "text_sha256": str(row["text_sha256"]),
                "expected_effect": str(row["expected_effect"]),
                "conversation_probability": round(probability, 9),
                "neighbor_modes": list(neighbor_modes),
            }
        )

    oracle_by_case = {
        str(row["case_id"]): row
        for row in target_oracle
    }
    for signal in signal_rows:
        oracle_row = oracle_by_case[signal["case_id"]]
        signal["routing_disposition"] = _routing_disposition(
            str(oracle_row["text_literal"]),
            operations,
        )
    queried_signals = [
        row
        for row in signal_rows
        if row["routing_disposition"] == "evidence_queried"
    ]
    queried_ids = {str(row["case_id"]) for row in queried_signals}

    baseline_by_case = {
        str(row["case_id"]): row
        for row in _read_jsonl(baseline)
    }
    joined_baseline = [
        (
            signal,
            baseline_by_case[str(signal["case_id"])],
        )
        for signal in queried_signals
        if str(signal["case_id"]) in baseline_by_case
    ]
    stage = _stage_projection(
        stage_artifact,
        {
            _normalized_text(
                str(oracle_by_case[str(row["case_id"])]["text_literal"])
            ): str(row["expected_effect"])
            for row in queried_signals
        },
    )

    oracle_collision_ids = sorted(
        str(row["case_id"])
        for row in queried_signals
        if row["expected_effect"] != "none"
    )
    baseline_nonconversation_ids = sorted(
        str(signal["case_id"])
        for signal, result in joined_baseline
        if result.get("decision_kind") != "conversation"
    )
    full_scope = evaluated_rows == len(target_oracle)
    stage_complete = stage["unique_cases"] == len(queried_signals)
    blockers = {
        "canonical_target_rows_not_evaluated": len(target_oracle) - evaluated_rows,
        "signals_without_raw_p_g_stage_evidence": (
            len(queried_signals) - int(stage["unique_cases"])
        ),
        "observed_g_false_no_effect_cases": int(
            stage["g_false_no_effect_cases"]
        ),
        "observed_p_clarify_under_condition_cases": int(
            stage["p_clarify_under_condition_cases"]
        ),
        "changed_replies_without_semantic_quality_gate": int(
            stage["forced_knowledge_changed_cases"]
        ),
    }
    promotion_ready = (
        full_scope
        and stage_complete
        and all(value == 0 for value in blockers.values())
    )
    runtime_occurrences = sum(
        int(row.get("runtime_occurrence_count") or 0)
        for row in all_oracle
    )
    theoretical_repeat_hits = max(0, runtime_occurrences - len(all_oracle))
    return {
        "schema": "baxy.turn-evidence-fastpath-audit.v1",
        "scope": args.scope,
        "effect_free": True,
        "inputs": {
            "runtime": {"path": str(runtime), "sha256": _sha256(runtime)},
            "oracle": {"path": str(oracle), "sha256": _sha256(oracle)},
            "language_scope": {
                "path": str(language_scope),
                "sha256": _sha256(language_scope),
            },
            "historical_messages": {
                "path": str(historical_messages),
                "sha256": _sha256(historical_messages),
            },
            "historical_baseline": {
                "path": str(baseline),
                "sha256": _sha256(baseline),
                "meaning": "final historical outcome, not raw P",
            },
            "stage_artifact": {
                "path": str(stage_artifact),
                "sha256": _sha256(stage_artifact),
            },
            "catalog": {"path": str(catalog), "sha256": _sha256(catalog)},
            "policy": {
                "path": str(
                    policy_path
                    or (
                        REPO
                        / "src"
                        / "baxy_mind"
                        / "data"
                        / "turn_evidence_abstention_policy.v1.json"
                    )
                ),
                "runtime_source_sha256": policy.runtime_source_sha256,
                "encoder_identity": policy.encoder_identity,
            },
        },
        "corpus": {
            "oracle_rows": len(all_oracle),
            "target_rows": len(target_oracle),
            "evaluated_target_rows": evaluated_rows,
            **vector_report,
        },
        "signals": {
            "raw_valid": len(signal_rows),
            "raw_rate_on_evaluated": round(
                len(signal_rows) / evaluated_rows if evaluated_rows else 0.0,
                9,
            ),
            "routing_disposition": _counter(
                str(row["routing_disposition"]) for row in signal_rows
            ),
            "candidate_tie_sensitive_case_ids": sorted(
                candidate_tie_sensitive_ids
            ),
            "candidate_tie_sensitive_rows": len(
                candidate_tie_sensitive_ids
            ),
            "evidence_queried": len(queried_signals),
            "queried_expected_effect": _counter(
                str(row["expected_effect"]) for row in queried_signals
            ),
            "queried_case_ids": sorted(queried_ids),
            "oracle_collision_case_ids": oracle_collision_ids,
        },
        "historical_baseline_final": {
            "joined_rows": len(joined_baseline),
            "decision_kind": _counter(
                str(result.get("decision_kind") or "")
                for _, result in joined_baseline
            ),
            "status": _counter(
                str(result.get("status") or "")
                for _, result in joined_baseline
            ),
            "oracle_effect_by_decision_kind": _cross_counter(
                (
                    str(signal["expected_effect"]),
                    str(result.get("decision_kind") or ""),
                )
                for signal, result in joined_baseline
            ),
            "nonconversation_case_ids": baseline_nonconversation_ids,
        },
        "language_evidence": language_evidence,
        "exact_online_reuse": {
            "canonical_unique_texts": len(all_oracle),
            "provenance_occurrences": runtime_occurrences,
            "theoretical_unbounded_repeat_hits": theoretical_repeat_hits,
            "theoretical_unbounded_repeat_rate": round(
                (
                    theoretical_repeat_hits / runtime_occurrences
                    if runtime_occurrences
                    else 0.0
                ),
                9,
            ),
            "interpretation": (
                "upper bound only; occurrence provenance is not a temporal "
                "request trace and does not prove LRU hit rate"
            ),
            "safe_candidate": (
                "bounded in-memory memoization of validated deterministic G/L "
                "keyed by exact text and runtime fingerprint"
            ),
        },
        "raw_stage_evidence": stage,
        "candidate_gate": {
            "condition_under_audit": (
                "valid one-sided evidence + evidence queried + empty history "
                "+ G=no_effect => cancel P and consume knowledge chat"
            ),
            "full_scope": full_scope,
            "raw_stage_complete": stage_complete,
            "blockers": blockers,
            "promotion_ready": promotion_ready,
            "next_action": (
                "run isolated physical A/B"
                if promotion_ready
                else "do not implement or promote; close every blocker first"
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--oracle", type=Path, default=DEFAULT_ORACLE)
    parser.add_argument(
        "--language-scope",
        type=Path,
        default=DEFAULT_LANGUAGE_SCOPE,
    )
    parser.add_argument(
        "--historical-messages",
        type=Path,
        default=DEFAULT_HISTORICAL_MESSAGES,
    )
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument(
        "--stage-artifact",
        type=Path,
        default=DEFAULT_STAGE_ARTIFACT,
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--policy", type=Path)
    parser.add_argument(
        "--scope",
        choices=("overlap", "full"),
        default="overlap",
    )
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size < 1 or args.batch_size > 512:
        raise SystemExit("--batch-size debe estar entre 1 y 512")
    result = run(args)
    write_json_atomic(args.output, result)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "scope": result["scope"],
                "evaluated": result["corpus"]["evaluated_target_rows"],
                "signals": result["signals"]["evidence_queried"],
                "promotion_ready": result["candidate_gate"]["promotion_ready"],
                "blockers": result["candidate_gate"]["blockers"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
