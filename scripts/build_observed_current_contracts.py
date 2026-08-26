#!/usr/bin/env python3
"""Build the independent current-tree contract mapping for Goal 10 replays."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Iterable

if __package__:
    from scripts.adjudicate_observed_product_replay import (
        AdjudicationError,
        file_sha256,
        object_sha256,
        read_jsonl,
        text_sha256,
        write_json,
        write_jsonl_atomic,
    )
else:
    from adjudicate_observed_product_replay import (
        AdjudicationError,
        file_sha256,
        object_sha256,
        read_jsonl,
        text_sha256,
        write_json,
        write_jsonl_atomic,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "tests" / "data" / "historical_observed_product_turns.v1.jsonl"
DEFAULT_MAPPING = ROOT / "tests" / "data" / "historical_message_mapping.jsonl"
DEFAULT_CATALOG = ROOT / "artifacts" / "development" / "current_core_catalog_snapshot_r219.json"
DEFAULT_SUMMARY = ROOT / "artifacts" / "goal10" / "observed-current-contracts-summary.v1.json"
CONTRACT_FIELDS = {
    "kind",
    "operations",
    "allowed_support_operations",
    "denied_operations",
    "success_evidence",
}


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AdjudicationError(f"{label} must be non-empty text")
    return value.strip()


def _strings(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise AdjudicationError(f"{label} must be a string list")
    result = [item.strip() for item in value]
    if any(not item for item in result) or (nonempty and not result):
        raise AdjudicationError(f"{label} contains no usable evidence")
    return result


def read_mapping(path: Path, message_ids: set[str]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(path):
        message_id = row.get("message_id")
        if message_id not in message_ids:
            continue
        if message_id in selected:
            raise AdjudicationError(f"mapping contains duplicate message_id {message_id}")
        selected[message_id] = row
    missing = message_ids - set(selected)
    if missing:
        raise AdjudicationError(f"mapping is missing {len(missing)} observed message IDs")
    return selected


def unique_variants(
    corpus_rows: Iterable[dict[str, Any]],
    mapping: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    variants: dict[str, dict[str, Any]] = {}
    for row in corpus_rows:
        message_id = _text(row.get("message_id"), "corpus.message_id")
        literal = _text(row.get("text_literal"), f"corpus[{message_id}].text_literal")
        source_text_hash = _text(
            row.get("text_sha256"),
            f"corpus[{message_id}].text_sha256",
        )
        replay_text_hash = text_sha256(literal)
        redacted = row.get("redacted") is True
        if not redacted and replay_text_hash != source_text_hash:
            raise AdjudicationError(f"corpus[{message_id}] text SHA-256 mismatch")
        mapped = mapping[message_id]
        acceptance_test_id = _text(
            mapped.get("acceptance_test_id"),
            f"mapping[{message_id}].acceptance_test_id",
        )
        historical = {
            key: deepcopy(mapped.get(key))
            for key in (
                "outcome_type",
                "operations",
                "denied_operations",
                "plan",
                "risk",
                "provider_roles",
                "verification",
                "natural_response",
            )
        }
        existing = variants.get(source_text_hash)
        if existing is None:
            variants[source_text_hash] = {
                "text": literal,
                "text_sha256": source_text_hash,
                "replay_text_sha256": replay_text_hash,
                "redacted": redacted,
                "acceptance_test_id": acceptance_test_id,
                "historical_contract": historical,
                "occurrence_count": 1,
                "classes": [str(row.get("class") or "")],
                "languages": [str(row.get("language") or "")],
            }
            continue
        if (
            existing["text"] != literal
            or existing["replay_text_sha256"] != replay_text_hash
            or existing["redacted"] != redacted
            or existing["acceptance_test_id"] != acceptance_test_id
            or existing["historical_contract"] != historical
        ):
            raise AdjudicationError(
                f"frozen literal {source_text_hash} has conflicting independent contracts"
            )
        existing["occurrence_count"] += 1
        existing["classes"].append(str(row.get("class") or ""))
        existing["languages"].append(str(row.get("language") or ""))
    for variant in variants.values():
        variant["classes"] = sorted(set(variant["classes"]))
        variant["languages"] = sorted(set(variant["languages"]))
    return variants


def load_catalog_names(path: Path) -> set[str]:
    try:
        root = json.loads(path.read_text(encoding="utf-8"))
        capabilities = root["catalogue"]["capabilities"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise AdjudicationError(f"cannot read current catalog snapshot: {path}") from error
    names = {
        item.get("name") for item in capabilities if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    if len(names) != len(capabilities):
        raise AdjudicationError("current catalog snapshot has duplicate or invalid operations")
    return names


def load_contract_reviews(
    paths: Iterable[Path],
    variants: dict[str, dict[str, Any]],
    catalog_names: set[str],
) -> dict[str, dict[str, Any]]:
    reviews: dict[str, dict[str, Any]] = {}
    for path in paths:
        for review in read_jsonl(path):
            if review.get("schema") != "baxy.goal10-observed-contract-review.v1":
                raise AdjudicationError(f"{path}: unsupported contract review schema")
            literal_hash = _text(review.get("text_sha256"), "review.text_sha256")
            if literal_hash in reviews:
                raise AdjudicationError(f"duplicate current-contract review for {literal_hash}")
            variant = variants.get(literal_hash)
            if variant is None:
                raise AdjudicationError(f"review targets an unknown frozen literal {literal_hash}")
            if (
                review.get("text") != variant["text"]
                or review.get("replay_text_sha256") != variant["replay_text_sha256"]
                or text_sha256(review["text"]) != variant["replay_text_sha256"]
            ):
                raise AdjudicationError(f"review[{literal_hash}] does not bind the exact frozen text")
            if review.get("acceptance_test_id") != variant["acceptance_test_id"]:
                raise AdjudicationError(f"review[{literal_hash}] targets another acceptance contract")
            if review.get("historical_contract_sha256") != object_sha256(
                variant["historical_contract"]
            ):
                raise AdjudicationError(f"review[{literal_hash}] is stale for the historical contract")
            if review.get("verdict") != "pass":
                raise AdjudicationError(f"review[{literal_hash}] is not an approved binary contract")
            reason = _text(review.get("reason"), f"review[{literal_hash}].reason")
            bases = _strings(
                review.get("authority_bases"),
                f"review[{literal_hash}].authority_bases",
                nonempty=True,
            )
            contract = review.get("contract")
            if not isinstance(contract, dict) or set(contract) != CONTRACT_FIELDS:
                raise AdjudicationError(
                    f"review[{literal_hash}].contract must contain exactly {sorted(CONTRACT_FIELDS)}"
                )
            kind = contract.get("kind")
            if kind not in {"conversation", "clarify", "action"}:
                raise AdjudicationError(f"review[{literal_hash}] has unknown contract kind")
            operations = _strings(contract.get("operations"), "contract.operations")
            support = _strings(
                contract.get("allowed_support_operations"),
                "contract.allowed_support_operations",
            )
            denied = _strings(contract.get("denied_operations"), "contract.denied_operations")
            evidence = _strings(
                contract.get("success_evidence"),
                "contract.success_evidence",
                nonempty=True,
            )
            if kind == "action" and not operations:
                raise AdjudicationError(f"review[{literal_hash}] action has no requested effects")
            if kind != "action" and (operations or support):
                raise AdjudicationError(f"review[{literal_hash}] non-action grants operation authority")
            if set(operations) & set(support):
                raise AdjudicationError(f"review[{literal_hash}] mixes requested and support roles")
            unknown = (set(operations) | set(support) | set(denied)) - catalog_names
            if unknown:
                raise AdjudicationError(
                    f"review[{literal_hash}] names operations outside the current catalog: {sorted(unknown)}"
                )
            normalized = deepcopy(review)
            normalized["reason"] = reason
            normalized["authority_bases"] = bases
            normalized["contract"] = {
                "kind": kind,
                "operations": operations,
                "allowed_support_operations": support,
                "denied_operations": denied,
                "success_evidence": evidence,
            }
            reviews[literal_hash] = normalized
    missing = set(variants) - set(reviews)
    if missing:
        raise AdjudicationError(f"current-contract review is missing {len(missing)} unique literals")
    return reviews


def contract_mapping_rows(
    corpus_rows: Iterable[dict[str, Any]],
    mapping: dict[str, dict[str, Any]],
    reviews: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in corpus_rows:
        message_id = row["message_id"]
        literal_hash = row["text_sha256"]
        review = reviews[literal_hash]
        contract = review["contract"]
        source = mapping[message_id]
        output.append(
            {
                "schema": "baxy.goal10-observed-current-contract.v1",
                "message_id": message_id,
                "source_text_sha256": literal_hash,
                "text_sha256": review["replay_text_sha256"],
                "acceptance_test_id": source["acceptance_test_id"],
                "acceptance_scope": "product_1_0",
                "outcome_type": contract["kind"],
                "operations": contract["operations"],
                "allowed_support_operations": contract["allowed_support_operations"],
                "denied_operations": contract["denied_operations"],
                "verification": contract["success_evidence"],
                "contract_review": {
                    "reason": review["reason"],
                    "authority_bases": review["authority_bases"],
                    "historical_contract_sha256": review["historical_contract_sha256"],
                },
            }
        )
    return output


def template_rows(variants: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "schema": "baxy.goal10-observed-contract-review-template.v1",
            **deepcopy(variant),
            "historical_contract_sha256": object_sha256(variant["historical_contract"]),
            "verdict": "unreviewed",
            "reason": "",
            "authority_bases": [],
            "contract": {
                "kind": "",
                "operations": [],
                "allowed_support_operations": [],
                "denied_operations": [],
                "success_evidence": [],
            },
        }
        for variant in sorted(variants.values(), key=lambda item: item["text_sha256"])
    ]


def build_summary(
    rows: list[dict[str, Any]],
    variants: dict[str, dict[str, Any]],
    corpus_path: Path,
    mapping_path: Path,
    catalog_path: Path,
    review_paths: list[Path],
    output_path: Path,
) -> dict[str, Any]:
    return {
        "schema": "baxy.goal10-observed-current-contracts-summary.v1",
        "occurrence_count": len(rows),
        "unique_text_count": len(variants),
        "contract_kind_counts": dict(sorted(Counter(row["outcome_type"] for row in rows).items())),
        "operation_counts": dict(
            sorted(Counter(operation for row in rows for operation in row["operations"]).items())
        ),
        "corpus_sha256": file_sha256(corpus_path),
        "mapping_sha256": file_sha256(mapping_path),
        "catalog_sha256": file_sha256(catalog_path),
        "review_inputs": [
            {"file": path.name, "sha256": file_sha256(path)} for path in review_paths
        ],
        "private_output_sha256": file_sha256(output_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--reviews", type=Path, action="append")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--template-output", type=Path)
    parser.add_argument("--expected-occurrences", type=int, default=1947)
    parser.add_argument("--expected-unique", type=int, default=626)
    return parser.parse_args()


def _require_private(path: Path, label: str) -> None:
    if path == ROOT or ROOT in path.parents:
        raise AdjudicationError(f"{label} contains private exact messages and must stay outside the repository")


def main() -> int:
    args = parse_args()
    corpus_path = args.corpus.resolve()
    mapping_path = args.mapping.resolve()
    catalog_path = args.catalog.resolve()
    corpus_rows = list(read_jsonl(corpus_path))
    if len(corpus_rows) != args.expected_occurrences:
        raise AdjudicationError(
            f"expected {args.expected_occurrences} occurrences, found {len(corpus_rows)}"
        )
    message_ids = {row.get("message_id") for row in corpus_rows}
    if len(message_ids) != len(corpus_rows) or not all(isinstance(item, str) for item in message_ids):
        raise AdjudicationError("observed corpus message IDs are missing or duplicated")
    mapping = read_mapping(mapping_path, message_ids)
    variants = unique_variants(corpus_rows, mapping)
    if len(variants) != args.expected_unique:
        raise AdjudicationError(f"expected {args.expected_unique} unique texts, found {len(variants)}")

    if args.template_output is not None:
        template_path = args.template_output.resolve()
        _require_private(template_path, "contract review template")
        write_jsonl_atomic(template_path, template_rows(variants))
        print(
            json.dumps(
                {
                    "schema": "baxy.goal10-observed-contract-review-template-summary.v1",
                    "occurrence_count": len(corpus_rows),
                    "unique_text_count": len(variants),
                    "private_template_sha256": file_sha256(template_path),
                },
                sort_keys=True,
            )
        )
        return 0

    if not args.reviews or args.output is None:
        raise AdjudicationError("--reviews and --output are required outside template mode")
    review_paths = [path.resolve() for path in args.reviews]
    output_path = args.output.resolve()
    _require_private(output_path, "current contract mapping")
    catalog_names = load_catalog_names(catalog_path)
    reviews = load_contract_reviews(review_paths, variants, catalog_names)
    output_rows = contract_mapping_rows(corpus_rows, mapping, reviews)
    write_jsonl_atomic(output_path, output_rows)
    summary = build_summary(
        output_rows,
        variants,
        corpus_path,
        mapping_path,
        catalog_path,
        review_paths,
        output_path,
    )
    write_json(args.summary_output.resolve(), summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
