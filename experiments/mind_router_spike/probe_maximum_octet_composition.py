"""Exhaust every order of BAXY's maximum eight-effect turn without effects.

The fixed octet contains four independent reads and four reversible actions.
All 8! operation orders are exercised exactly once. Language, lexical variant,
and connector surface are distributed across the exhaustive order set. The
probe sends only ``turn.decide`` and never sends a plan or Core operation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from itertools import permutations
from pathlib import Path
from typing import Any, Iterator


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike.probe_catalog_pairwise_composition import (  # noqa: E402
    ACTION_TAILS,
    READ_ONLY_TAILS,
    TAIL_LEXICAL_VARIANTS,
)
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    file_sha256,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)


OUTPUT = REPO / "artifacts/fixes/maximum_octet_composition_r1.json"
RAW = OUTPUT.with_suffix(".raw.jsonl")
SURFACES = (
    "sentence_then",
    "semicolon_sequence",
    "conjunction_sequence",
    "after_that_sequence",
    "bare_semicolons",
)
LEXICAL_PROFILES = ("canonical", "lexical_1", "lexical_2")


def _render(parts: tuple[str, ...], language: str, surface: str) -> str:
    if surface == "sentence_then":
        connector = "Then" if language == "en" else "Después"
        return f"{parts[0]}. {connector} " + f". {connector} ".join(parts[1:]) + "."
    if surface == "semicolon_sequence":
        connector = "then" if language == "en" else "luego"
        final = "finally" if language == "en" else "finalmente"
        return f"{parts[0]}; {connector} " + f"; {connector} ".join(parts[1:-1]) + f"; {final} {parts[-1]}."
    if surface == "conjunction_sequence":
        connector = "and then" if language == "en" else "y luego"
        final = "and finally" if language == "en" else "y finalmente"
        return f"{parts[0]}, {connector} " + f", {connector} ".join(parts[1:-1]) + f", {final} {parts[-1]}."
    if surface == "after_that_sequence":
        connector = "After that" if language == "en" else "Después de eso"
        final = "Finally" if language == "en" else "Finalmente"
        return f"{parts[0]}. {connector}, " + f". {connector}, ".join(parts[1:-1]) + f". {final}, {parts[-1]}."
    if surface == "bare_semicolons":
        return "; ".join(parts) + "."
    raise ValueError(f"unknown octet surface: {surface}")


def build_cases() -> Iterator[dict[str, Any]]:
    tails = (*READ_ONLY_TAILS, *ACTION_TAILS)
    by_id = {str(tail["tail_id"]): tail for tail in tails}
    tail_ids = tuple(by_id)
    for index, order in enumerate(permutations(tail_ids)):
        language = "es" if index % 2 == 0 else "en"
        surface = SURFACES[index % len(SURFACES)]
        lexical_profile = LEXICAL_PROFILES[index % len(LEXICAL_PROFILES)]
        lexical_index = (
            None
            if lexical_profile == "canonical"
            else int(lexical_profile[-1]) - 1
        )
        parts: list[str] = []
        expected: list[str] = []
        for tail_id in order:
            tail = by_id[tail_id]
            phrase = (
                str(tail[language])
                if lexical_index is None
                else TAIL_LEXICAL_VARIANTS[tail_id][language][lexical_index]
            )
            parts.append(phrase.rstrip().rstrip(".?!"))
            expected.append(str(tail["operation"]))
        yield {
            "case_id": f"octet-{index:05d}-{'-'.join(order)}",
            "order": order,
            "language": language,
            "surface": surface,
            "lexical_profile": lexical_profile,
            "text": _render(tuple(parts), language, surface),
            "expected_effect_operations": expected,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(0.95 * len(ordered) + 0.999) - 1))
    return ordered[rank]


def run(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output.resolve()
    raw = args.raw.resolve()
    partial = raw.with_suffix(".partial.jsonl")
    if output.exists() or raw.exists() or partial.exists():
        raise RuntimeError("refusing to overwrite an existing octet artifact")
    output.parent.mkdir(parents=True, exist_ok=True)
    runtime = resolve_runtime(manifest_path=args.runtime_manifest)
    manifest_before = file_sha256(args.runtime_manifest)
    capabilities, application_catalog, game_catalog = current_core_catalog_snapshot(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    available = {str(item["name"]) for item in capabilities}
    required = {
        str(tail["operation"])
        for tail in (*READ_ONLY_TAILS, *ACTION_TAILS)
    }
    if not required <= available:
        raise RuntimeError(f"authenticated catalogue lacks {sorted(required - available)}")

    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=environment,
        cwd=REPO,
    )
    latencies: list[float] = []
    failures: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    language_counts: Counter[str] = Counter()
    surface_counts: Counter[str] = Counter()
    lexical_counts: Counter[str] = Counter()
    position_counts: Counter[tuple[str, int]] = Counter()
    order_fingerprints: set[str] = set()
    exact = 0
    total = 0
    started = time.perf_counter()
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar rejected its handshake")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "octet-catalog",
                "capabilities": capabilities,
                "applicationCatalog": application_catalog,
                "gameCatalog": game_catalog,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("sidecar rejected the authenticated catalogue")
        client.request(
            {
                "type": "turn.decide",
                "id": "octet-warm",
                "text": "hola",
                "history": [],
                "uiLanguage": "es",
            },
            limits["turn.decide"],
        )
        with partial.open("x", encoding="utf-8", newline="\n") as stream:
            for case in build_cases():
                before = time.perf_counter()
                reply = client.request(
                    {
                        "type": "turn.decide",
                        "id": case["case_id"],
                        "text": case["text"],
                        "history": [],
                        "uiLanguage": case["language"],
                    },
                    limits["turn.decide"],
                )
                seconds = round(time.perf_counter() - before, 6)
                observed = list(reply.get("effectOperations") or [])
                row_exact = (
                    reply.get("kind") == "plan"
                    and observed == case["expected_effect_operations"]
                )
                row = {
                    **case,
                    "seconds": seconds,
                    "observed_kind": reply.get("kind"),
                    "observed_effect_operations": observed,
                    "exact": row_exact,
                }
                stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                total += 1
                exact += int(row_exact)
                latencies.append(seconds)
                language_counts[case["language"]] += 1
                surface_counts[case["surface"]] += 1
                lexical_counts[case["lexical_profile"]] += 1
                order_key = ">".join(case["order"])
                order_fingerprints.add(order_key)
                for position, tail_id in enumerate(case["order"]):
                    position_counts[(tail_id, position)] += 1
                if len(samples) < 16:
                    samples.append(row)
                if not row_exact:
                    failures.append(row)
                if total % 5_000 == 0:
                    stream.flush()
                    os.fsync(stream.fileno())
                    elapsed = max(time.perf_counter() - started, 1e-9)
                    print(
                        json.dumps(
                            {
                                "progress": total,
                                "total": 40_320,
                                "rate_per_second": round(total / elapsed, 3),
                                "failures": len(failures),
                            },
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        flush=True,
                    )
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": "octet-shutdown"},
            timeout=limits["shutdown"],
        )

    os.replace(partial, raw)
    expected_total = 40_320
    expected_position_count = 5_040
    coverage = {
        "unique_orders": len(order_fingerprints),
        "language_counts": dict(sorted(language_counts.items())),
        "surface_counts": dict(sorted(surface_counts.items())),
        "lexical_counts": dict(sorted(lexical_counts.items())),
        "every_tail_every_position": all(
            position_counts[(tail["tail_id"], position)] == expected_position_count
            for tail in (*READ_ONLY_TAILS, *ACTION_TAILS)
            for position in range(8)
        ),
    }
    report = {
        "schema": "baxy.maximum-octet-composition.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "exhaustive_8_factor_order_distributed_language_lexical_surface",
        "authority": "turn.decide_only_no_plan_or_operation_dispatched",
        "runtime": public_runtime_identity(runtime),
        "effects_executed": 0,
        "total_seconds": round(time.perf_counter() - started, 3),
        "metrics": {
            "exact": exact,
            "total": total,
            "exact_accuracy": exact / total,
            "unsafe_effects": 0,
            "turn_decide_seconds_p50": statistics.median(latencies),
            "turn_decide_seconds_p95": _p95(latencies),
        },
        "coverage": coverage,
        "acceptance": {
            "all_exact": exact == expected_total == total,
            "all_orders_unique": len(order_fingerprints) == expected_total,
            "every_tail_every_position": coverage["every_tail_every_position"],
            "runtime_manifest_unchanged": (
                manifest_before == file_sha256(args.runtime_manifest)
            ),
            "zero_effects": True,
        },
        "source": {
            "probe_sha256": _sha256(Path(__file__).resolve()),
            "raw": str(raw.relative_to(REPO)).replace("\\", "/"),
            "raw_sha256": _sha256(raw),
        },
        "failures": failures,
        "samples": samples,
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-manifest",
        type=Path,
        default=DEFAULT_RUNTIME_MANIFEST,
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--raw", type=Path, default=RAW)
    args = parser.parse_args()
    report = run(args)
    print(json.dumps({
        "metrics": report["metrics"],
        "coverage": report["coverage"],
        "acceptance": report["acceptance"],
        "failure_count": len(report["failures"]),
        "failure_sample": report["failures"][:20],
        "effects_executed": report["effects_executed"],
    }, ensure_ascii=False, indent=2))
    return 0 if all(report["acceptance"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
