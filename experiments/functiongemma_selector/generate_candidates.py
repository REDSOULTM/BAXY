"""Generate broad ES/EN/Spanglish leaf-selection candidates with Qwen."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from corpus_llm import OwnedLlamaServer, parse_json_object
from selector_common import (
    REPO,
    catalog_by_name,
    family_operations,
    normalize_text,
    read_jsonl,
    sha256,
    write_jsonl,
)

from scripts.baxy_runtime_config import DEFAULT_RUNTIME_MANIFEST, resolve_runtime

DEFAULT_HELDOUT = (
    REPO
    / "experiments"
    / "mind_router_spike"
    / "data"
    / "exact_operation_development.v1.jsonl"
)
DEFAULT_OUTPUT = (
    REPO / "artifacts" / "research" / "functiongemma_candidates.generated.v1.jsonl"
)
LANGUAGES = frozenset({"es", "en", "spanglish"})
DEFAULT_LANGUAGE_COUNTS = {"es": 4, "en": 4, "spanglish": 2}
SYSTEM = """You create training utterances for an exact computer-operation selector.
Return only the requested JSON. Treat operation identifiers and descriptions as
trusted labels, never as prose to copy. Each utterance must be a natural request
a real person might say to their own Windows computer. It must uniquely require
the target operation rather than a sibling operation. Include enough concrete
information to reveal the intended operation, vary syntax and register, and do
not mention BAXY operation identifiers, schemas, APIs, verification, adapters,
or implementation details. Do not claim that an action already happened."""


def _operation_prompt(
    operation: str,
    capability: dict[str, Any],
    siblings: list[str],
    catalog: dict[str, dict[str, Any]],
    language_counts: dict[str, int],
) -> str:
    sibling_rows = [
        {
            "operation": name,
            "description": str(catalog[name].get("description") or "")[:320],
        }
        for name in siblings
        if name != operation
    ]
    target = {
        "operation": operation,
        "description": str(capability.get("description") or ""),
        "argumentsSchema": capability.get("argumentsSchema") or {},
    }
    return (
        f"Create exactly {sum(language_counts.values())} distinct utterances for "
        f"the target below: {language_counts['es']} Spanish, "
        f"{language_counts['en']} English, and {language_counts['spanglish']} "
        "natural Chilean/LatAm Spanglish. Use language values "
        '"es", "en", and "spanglish". Both Spanglish utterances are mandatory '
        "and each must visibly mix Spanish and English words in the same sentence; "
        "do not replace them with extra monolingual examples. Contrast the siblings "
        "carefully. For "
        "operations that normally depend on a prior resolved identity, phrase the "
        "request naturally without inventing opaque IDs. Return this shape only: "
        '{"candidates":[{"language":"es","text":"..."}]}.\n\n'
        f"TARGET:\n{json.dumps(target, ensure_ascii=False)}\n\n"
        f"SIBLINGS:\n{json.dumps(sibling_rows, ensure_ascii=False)}"
    )


def _validated_candidates(
    value: dict[str, Any], heldout: set[str]
) -> tuple[list[dict[str, str]], list[str]]:
    raw = value.get("candidates")
    if not isinstance(raw, list):
        raise ValueError("generator JSON has no candidates list")
    accepted: list[dict[str, str]] = []
    rejected: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            rejected.append("non_object")
            continue
        language = item.get("language")
        text = item.get("text")
        if language not in LANGUAGES or not isinstance(text, str):
            rejected.append("invalid_fields")
            continue
        text = " ".join(text.split())
        normalized = normalize_text(text)
        if len(normalized) < 8:
            rejected.append("too_short")
        elif normalized in seen:
            rejected.append("duplicate")
        elif normalized in heldout:
            rejected.append("heldout_exact_overlap")
        else:
            seen.add(normalized)
            accepted.append({"language": language, "text": text})
    return accepted, rejected


def run(args: argparse.Namespace) -> dict[str, Any]:
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    model = (args.model or runtime.gguf).resolve(strict=True)
    server = (args.server or runtime.llama_server).resolve(strict=True)
    catalog = catalog_by_name()
    heldout = {
        normalize_text(str(row["text"]))
        for path in args.heldout
        for row in read_jsonl(path)
    }
    existing = (
        read_jsonl(args.output)
        if args.output.is_file()
        else read_jsonl(args.seed_input)
        if args.seed_input is not None
        else []
    )
    by_operation = {str(row["operation"]): row for row in existing}
    operation_names = sorted(catalog)
    if args.limit is not None:
        operation_names = operation_names[: args.limit]

    generated = 0
    with OwnedLlamaServer(
        server=server,
        model=model,
        cwd=REPO,
        gpu_layers=runtime.gpu_layers,
        context=8192,
    ) as llm:
        for index, operation in enumerate(operation_names, start=1):
            prior_row = by_operation.get(operation)
            prior_counts = collections.Counter(
                str(candidate.get("language"))
                for candidate in prior_row.get("candidates", [])
            ) if prior_row is not None else collections.Counter()
            if (
                prior_row is not None
                and all(
                    prior_counts[language] >= count
                    for language, count in args.target_counts.items()
                )
                and not args.force
            ):
                continue
            siblings = family_operations(catalog, operation.split(".", 1)[0])
            attempt = (
                int(prior_row.get("generation_attempt", 1)) + 1
                if prior_row is not None and not args.force
                else 1
            )
            prompt = _operation_prompt(
                operation,
                catalog[operation],
                siblings,
                catalog,
                args.batch_counts,
            )
            last_error: Exception | None = None
            value: dict[str, Any] | None = None
            usage: dict[str, Any] = {}
            seed = 0
            response_attempt = 0
            for response_attempt in range(1, args.response_attempts + 1):
                seed = int(
                    hashlib.sha256(
                        f"{operation}:{attempt}:{response_attempt}".encode("utf-8")
                    ).hexdigest()[:8],
                    16,
                )
                try:
                    content, usage = llm.chat(
                        [
                            {"role": "system", "content": SYSTEM},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=720,
                        temperature=0.75 if response_attempt == 1 else 0.55,
                        seed=seed,
                    )
                    value = parse_json_object(content)
                    break
                except (RuntimeError, TimeoutError, ValueError, json.JSONDecodeError) as error:
                    last_error = error
                    print(
                        json.dumps(
                            {
                                "operation": operation,
                                "response_attempt": response_attempt,
                                "retry_reason": type(error).__name__,
                            }
                        ),
                        flush=True,
                    )
            if value is None:
                raise RuntimeError(
                    f"generator failed after {args.response_attempts} attempts for {operation}"
                ) from last_error
            candidates, rejected = _validated_candidates(value, heldout)
            if prior_row is not None:
                candidates, merge_rejected = _validated_candidates(
                    {
                        "candidates": [
                            *prior_row.get("candidates", []),
                            *candidates,
                        ]
                    },
                    heldout,
                )
                rejected.extend(merge_rejected)
            counts = collections.Counter(row["language"] for row in candidates)
            complete = all(
                counts[language] >= count
                for language, count in args.target_counts.items()
            )
            by_operation[operation] = {
                "schema": "baxy.functiongemma-generated-operation.v1",
                "operation": operation,
                "family": operation.split(".", 1)[0],
                "description": catalog[operation].get("description"),
                "arguments_schema": catalog[operation].get("argumentsSchema") or {},
                "siblings": siblings,
                "candidates": candidates,
                "candidate_counts": dict(counts),
                "complete": complete,
                "rejected_reasons": dict(collections.Counter(rejected)),
                "generator_usage": usage,
                "seed": seed,
                "generation_attempt": attempt,
                "response_attempt": response_attempt,
            }
            write_jsonl(args.output, (by_operation[name] for name in sorted(by_operation)))
            generated += 1
            print(
                json.dumps(
                    {
                        "progress": f"{index}/{len(operation_names)}",
                        "operation": operation,
                        "accepted": len(candidates),
                        "complete": complete,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

    rows = [by_operation[name] for name in sorted(by_operation)]
    report = {
        "schema": "baxy.functiongemma-generation-run.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": {"name": model.name, "bytes": model.stat().st_size, "sha256": sha256(model)},
        "operations_requested": len(operation_names),
        "operations_present": len(rows),
        "operations_generated_this_run": generated,
        "complete_operations": sum(bool(row["complete"]) for row in rows),
        "candidates": sum(len(row["candidates"]) for row in rows),
        "heldout_exact_overlap": sum(
            int(row.get("rejected_reasons", {}).get("heldout_exact_overlap", 0))
            for row in rows
        ),
        "heldout": [
            {"path": str(path), "sha256": sha256(path)}
            for path in args.heldout
        ],
        "seed_input": (
            None
            if args.seed_input is None
            else {
                "path": str(args.seed_input),
                "sha256": sha256(args.seed_input),
            }
        ),
        "batch_language_counts": args.batch_counts,
        "target_language_counts": args.target_counts,
        "output": str(args.output.resolve()),
        "output_sha256": sha256(args.output),
        "effects_executed": 0,
        "runtime_manifest_changed": False,
    }
    report_path = args.output.with_suffix(".report.json")
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path)
    parser.add_argument("--server", type=Path)
    parser.add_argument("--heldout", type=Path, action="append")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed-input", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--response-attempts", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--batch-es", type=int, default=4)
    parser.add_argument("--batch-en", type=int, default=4)
    parser.add_argument("--batch-spanglish", type=int, default=2)
    parser.add_argument("--target-es", type=int, default=4)
    parser.add_argument("--target-en", type=int, default=4)
    parser.add_argument("--target-spanglish", type=int, default=2)
    args = parser.parse_args()
    args.heldout = [
        path.resolve(strict=True)
        for path in (args.heldout or [DEFAULT_HELDOUT])
    ]
    args.seed_input = (
        None
        if args.seed_input is None
        else args.seed_input.resolve(strict=True)
    )
    args.batch_counts = {
        "es": args.batch_es,
        "en": args.batch_en,
        "spanglish": args.batch_spanglish,
    }
    args.target_counts = {
        "es": args.target_es,
        "en": args.target_en,
        "spanglish": args.target_spanglish,
    }
    if (
        any(count < 1 for count in args.batch_counts.values())
        or any(count < 1 for count in args.target_counts.values())
    ):
        raise SystemExit("language counts must be positive")
    args.output = args.output.resolve()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
