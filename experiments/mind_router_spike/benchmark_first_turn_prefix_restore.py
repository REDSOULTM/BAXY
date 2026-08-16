"""Physical A/B for restoring prebuilt P/G/L slot caches on first turn.

The seed server is a one-time, separately reported preparation step.  It
primes the same safe synthetic P/G/L token prefixes used by
``benchmark_first_turn_prefix_priming.py`` and saves each pinned slot through
llama.cpp b9980's documented ``/slots/{id}?action=save`` endpoint.

Every measured arm then starts a fresh server with the same
``--slot-save-path``.  The baseline sends one real turn without loading any
file.  The candidate verifies the cache-file hashes, restores all three slots
concurrently, and sends the exact same real turn using automatic slot
selection.  Startup, integrity checking, restore calls and real-turn latency
are reported separately and as one startup-to-response total.

The experiment never starts Core or executes an external operation.  Cache
files live in a benchmark-owned temporary directory and are deleted after the
report is written.  No runtime manifest or installed asset is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from benchmark_first_turn_prefix_priming import (  # type: ignore[import-not-found]
    _actual_request_projection,
    _http_json,
    _prime_prefixes,
)
from benchmark_llama_slot_pinning import (  # type: ignore[import-not-found]
    CASES,
    InstrumentedRuntime,
    _case_projection,
    _run_case,
    _stage,
    _stage_summary,
)


_SLOT_BY_STAGE = {"P": 0, "G": 1, "L": 2}
_FILENAME_BY_STAGE = {
    "P": "baxy-prefix-p.slot",
    "G": "baxy-prefix-g.slot",
    "L": "baxy-prefix-l.slot",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class SlotPathRuntime(InstrumentedRuntime):
    def __init__(self, arm: str, slot_save_path: Path) -> None:
        self._benchmark_slot_save_path = slot_save_path.resolve()
        super().__init__(arm)

    def _server_command(self) -> list[str]:
        command = super()._server_command()
        command.extend(
            [
                "--slot-save-path",
                str(self._benchmark_slot_save_path),
            ]
        )
        return command

    def _post(
        self,
        payload: dict[str, Any],
        timeout: float | None = None,
        *,
        max_attempts: int = 2,
        cancellation: Any = None,
    ) -> dict[str, Any]:
        wire = dict(payload)
        stage = _stage(wire)
        if (
            self._benchmark_arm == "restored_pinned"
            and stage in _SLOT_BY_STAGE
        ):
            wire["id_slot"] = _SLOT_BY_STAGE[stage]
        response = super()._post(
            wire,
            timeout,
            max_attempts=max_attempts,
            cancellation=cancellation,
        )
        selected_slot = response.get("id_slot")
        with self._benchmark_lock:
            for record in reversed(self._benchmark_records):
                if (
                    record["case"] == self._benchmark_case
                    and record["stage"] == stage
                    and "server_selected_slot" not in record
                ):
                    record["server_selected_slot"] = selected_slot
                    break
        return response


def _slot_action(
    endpoint: str,
    *,
    action: str,
    stage: str,
) -> dict[str, Any]:
    slot = _SLOT_BY_STAGE[stage]
    filename = _FILENAME_BY_STAGE[stage]
    started = time.perf_counter()
    response = _http_json(
        endpoint,
        f"/slots/{slot}?action={action}",
        {"filename": filename},
    )
    elapsed = time.perf_counter() - started
    timings = response.get("timings")
    if not isinstance(timings, dict):
        timings = {}
    return {
        "stage": stage,
        "id_slot": slot,
        "filename": filename,
        "elapsed_seconds": elapsed,
        "n_saved": response.get("n_saved"),
        "n_written": response.get("n_written"),
        "n_restored": response.get("n_restored"),
        "n_read": response.get("n_read"),
        "save_ms": timings.get("save_ms"),
        "restore_ms": timings.get("restore_ms"),
    }


def _parallel_slot_actions(
    endpoint: str,
    action: str,
) -> tuple[float, list[dict[str, Any]]]:
    started = time.perf_counter()
    with ThreadPoolExecutor(
        max_workers=3,
        thread_name_prefix=f"baxy-slot-{action}",
    ) as executor:
        futures = [
            executor.submit(
                _slot_action,
                endpoint,
                action=action,
                stage=stage,
            )
            for stage in ("P", "G", "L")
        ]
        records = [future.result() for future in futures]
    elapsed = time.perf_counter() - started
    records.sort(key=lambda item: str(item["stage"]))
    return elapsed, records


def _build_seed(
    slot_path: Path,
) -> dict[str, Any]:
    runtime = SlotPathRuntime("seed", slot_path)
    started = time.perf_counter()
    priming: dict[str, Any] | None = None
    save_seconds = 0.0
    save_records: list[dict[str, Any]] = []
    try:
        runtime.start_warmup()
        if not runtime.wait_warmup(420.0):
            raise TimeoutError("seed llama-server did not become ready")
        ready_at = time.perf_counter()
        endpoint = runtime._endpoint
        if not isinstance(endpoint, str) or not endpoint:
            raise RuntimeError("seed endpoint is missing")
        priming = _prime_prefixes(endpoint)
        save_seconds, save_records = _parallel_slot_actions(
            endpoint,
            "save",
        )
        finished_at = time.perf_counter()
    finally:
        runtime.close()
    assert priming is not None
    files: dict[str, Any] = {}
    for stage, filename in _FILENAME_BY_STAGE.items():
        path = slot_path / filename
        if not path.is_file():
            raise FileNotFoundError(f"slot cache was not saved: {path}")
        files[stage] = {
            "filename": filename,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
            "safe_prefix_sha256": priming["prefixes"][stage][
                "safe_prefix_sha256"
            ],
            "safe_prefix_tokens": priming["prefixes"][stage][
                "safe_prefix_tokens"
            ],
        }
    return {
        "startup_to_ready_seconds": ready_at - started,
        "priming": priming,
        "save_seconds": save_seconds,
        "save_requests": save_records,
        "one_time_seed_total_seconds": finished_at - started,
        "files": files,
    }


def _verify_cache_files(
    slot_path: Path,
    seed_files: dict[str, Any],
) -> tuple[float, list[dict[str, Any]]]:
    started = time.perf_counter()
    records: list[dict[str, Any]] = []
    for stage in ("P", "G", "L"):
        expected = seed_files[stage]
        path = slot_path / str(expected["filename"])
        actual_size = path.stat().st_size
        actual_sha256 = _sha256_file(path)
        if (
            actual_size != expected["size_bytes"]
            or actual_sha256 != expected["sha256"]
        ):
            raise ValueError(f"{stage} slot cache integrity mismatch")
        records.append(
            {
                "stage": stage,
                "filename": expected["filename"],
                "size_bytes": actual_size,
                "sha256": actual_sha256,
                "matches_seed": True,
            }
        )
    return time.perf_counter() - started, records


def _run_fresh_arm(
    arm: str,
    case: Any,
    slot_path: Path,
    seed_files: dict[str, Any],
) -> dict[str, Any]:
    runtime = SlotPathRuntime(arm, slot_path)
    startup_started = time.perf_counter()
    integrity_seconds = 0.0
    integrity_records: list[dict[str, Any]] = []
    restore_seconds = 0.0
    restore_records: list[dict[str, Any]] = []
    turn: dict[str, Any] | None = None
    try:
        runtime.start_warmup()
        if not runtime.wait_warmup(420.0):
            raise TimeoutError("llama-server did not become ready")
        ready_at = time.perf_counter()
        if arm in {"restored", "restored_pinned"}:
            integrity_seconds, integrity_records = _verify_cache_files(
                slot_path,
                seed_files,
            )
            endpoint = runtime._endpoint
            if not isinstance(endpoint, str) or not endpoint:
                raise RuntimeError("owned llama-server endpoint is missing")
            restore_seconds, restore_records = _parallel_slot_actions(
                endpoint,
                "restore",
            )
        turn_started = time.perf_counter()
        turn = _run_case(runtime, case)
        completed_at = time.perf_counter()
    finally:
        runtime.close()
    assert turn is not None
    return {
        "arm": arm,
        "case": case.name,
        "startup_to_ready_seconds": ready_at - startup_started,
        "integrity_verification_seconds": integrity_seconds,
        "integrity_verification": integrity_records,
        "restore_api_seconds": restore_seconds,
        "restore_requests": restore_records,
        "restore_total_seconds": integrity_seconds + restore_seconds,
        "first_turn_e2e_seconds": completed_at - turn_started,
        "ready_to_first_turn_complete_seconds": completed_at - ready_at,
        "startup_to_first_turn_complete_seconds": completed_at - startup_started,
        "turn": turn,
        "posts": runtime._benchmark_records,
        "actual_request_projection": _actual_request_projection(
            runtime._benchmark_records
        ),
        "stage_summary": _stage_summary(runtime._benchmark_records),
    }


def _pair_result(
    case: Any,
    arm_order: list[str],
    slot_path: Path,
    seed_files: dict[str, Any],
) -> dict[str, Any]:
    arms = [
        _run_fresh_arm(arm, case, slot_path, seed_files)
        for arm in arm_order
    ]
    by_arm = {arm["arm"]: arm for arm in arms}
    baseline = by_arm["baseline"]
    candidate_name = next(
        name for name in by_arm if name != "baseline"
    )
    restored = by_arm[candidate_name]
    baseline_requests = baseline["actual_request_projection"]
    restored_requests = restored["actual_request_projection"]
    request_identity = [
        (item["stage"], item["payload_sha256"])
        for item in baseline_requests
    ] == [
        (item["stage"], item["payload_sha256"])
        for item in restored_requests
    ]
    prompt_token_identity = [
        (item["stage"], item["prompt_tokens_total"])
        for item in baseline_requests
    ] == [
        (item["stage"], item["prompt_tokens_total"])
        for item in restored_requests
    ]
    cache_match_by_stage: dict[str, Any] = {}
    for stage in ("P", "G", "L"):
        baseline_post = next(
            (
                post
                for post in baseline["posts"]
                if post["stage"] == stage
            ),
            None,
        )
        restored_post = next(
            (
                post
                for post in restored["posts"]
                if post["stage"] == stage
            ),
            None,
        )
        baseline_cache = (
            int(baseline_post["cache_n"])
            if baseline_post is not None
            and isinstance(baseline_post.get("cache_n"), (int, float))
            else None
        )
        restored_cache = (
            int(restored_post["cache_n"])
            if restored_post is not None
            and isinstance(restored_post.get("cache_n"), (int, float))
            else None
        )
        cache_match_by_stage[stage] = {
            "restored_id_slot": _SLOT_BY_STAGE[stage],
            "server_selected_slot": (
                restored_post.get("server_selected_slot")
                if restored_post is not None
                else None
            ),
            "baseline_cache_n": baseline_cache,
            "restored_cache_n": restored_cache,
            "cache_n_increased": (
                baseline_cache is not None
                and restored_cache is not None
                and restored_cache > baseline_cache
            ),
        }
    cache_reappeared = all(
        evidence["cache_n_increased"]
        for evidence in cache_match_by_stage.values()
    )
    return {
        "case": case.name,
        "expected_mode": case.expected_mode,
        "arm_order": arm_order,
        "candidate_arm": candidate_name,
        "real_slot_selection": (
            "explicit_pgl"
            if candidate_name == "restored_pinned"
            else "automatic"
        ),
        "exact_turn_output": (
            _case_projection(baseline["turn"])
            == _case_projection(restored["turn"])
        ),
        "actual_request_identity": request_identity,
        "actual_prompt_token_identity": prompt_token_identity,
        "automatic_slot_cache_match_by_stage": cache_match_by_stage,
        "automatic_slot_selection_preserved_restored_prefixes": (
            cache_reappeared
            if candidate_name == "restored"
            else None
        ),
        "restored_prefixes_reappeared": cache_reappeared,
        "delta_restored_minus_baseline_seconds": {
            "first_turn_e2e": (
                float(restored["first_turn_e2e_seconds"])
                - float(baseline["first_turn_e2e_seconds"])
            ),
            "ready_to_first_turn_complete_including_restore": (
                float(restored["ready_to_first_turn_complete_seconds"])
                - float(baseline["ready_to_first_turn_complete_seconds"])
            ),
            "startup_to_first_turn_complete": (
                float(restored["startup_to_first_turn_complete_seconds"])
                - float(baseline["startup_to_first_turn_complete_seconds"])
            ),
        },
        "arms": arms,
    }


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--arm-order",
        choices=(
            "baseline-restored",
            "restored-baseline",
            "baseline-restored_pinned",
            "restored_pinned-baseline",
        ),
        default="baseline-restored",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="cases",
        help="case name; repeat to select several (default: all)",
    )
    parser.add_argument(
        "--server",
        type=Path,
        default=Path(
            r"D:\BAXYRuntime\assets\llama-b9980-cuda12.4\llama-server.exe"
        ),
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(
            r"D:\BAXYRuntime\assets\models"
            r"\gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf"
        ),
    )
    args = parser.parse_args()
    if not args.server.is_file() or not args.model.is_file():
        raise FileNotFoundError("official runtime assets are missing")

    selected = list(CASES)
    if args.cases:
        requested = set(args.cases)
        selected = [case for case in CASES if case.name in requested]
        missing = requested - {case.name for case in selected}
        if missing:
            raise ValueError(f"unknown cases: {sorted(missing)}")
    if not selected:
        raise ValueError("at least one case is required")

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(args.server)
    os.environ["BAXY_MIND_LLM_GGUF"] = str(args.model)
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"

    arm_order = args.arm_order.split("-")
    with tempfile.TemporaryDirectory(
        prefix="baxy-prefix-restore-",
    ) as temporary:
        slot_path = Path(temporary).resolve()
        seed = _build_seed(slot_path)
        pairs = [
            _pair_result(case, arm_order, slot_path, seed["files"])
            for case in selected
        ]

    delta_keys = (
        "first_turn_e2e",
        "ready_to_first_turn_complete_including_restore",
        "startup_to_first_turn_complete",
    )
    deltas = {
        key: [
            float(pair["delta_restored_minus_baseline_seconds"][key])
            for pair in pairs
        ]
        for key in delta_keys
    }
    exact_outputs = all(pair["exact_turn_output"] for pair in pairs)
    request_identity = all(pair["actual_request_identity"] for pair in pairs)
    prompt_token_identity = all(
        pair["actual_prompt_token_identity"] for pair in pairs
    )
    restored_prefixes_reappeared = all(
        pair["restored_prefixes_reappeared"]
        for pair in pairs
    )
    automatic_real_slots = "restored" in arm_order
    result = {
        "schema": "baxy.first-turn-prefix-restore-ab.v1",
        "arm_order": arm_order,
        "server": str(args.server.resolve()),
        "server_sha256": _sha256_file(args.server),
        "model": str(args.model.resolve()),
        "model_sha256": _sha256_file(args.model),
        "profile": {
            "parallel": 3,
            "context_per_slot": 4_096,
            "cache_prompt": "llama.cpp b9980 default true",
            "fresh_server_per_case_and_arm": True,
            "one_real_turn_per_server": True,
            "restore_slots": dict(_SLOT_BY_STAGE),
            "real_requests_use_automatic_slot_selection": automatic_real_slots,
            "real_requests_pin_only_initial_pgl": not automatic_real_slots,
            "slot_save_path": "benchmark-owned temporary directory",
        },
        "safety": {
            "production_code_changed": False,
            "runtime_manifest_changed": False,
            "installed_assets_changed": False,
            "core_started": False,
            "external_effects_executed": False,
            "real_case_text_in_cache_files": False,
            "temporary_cache_files_deleted_after_report": True,
        },
        "binding": {
            "required_before_restore": [
                "server_sha256",
                "model_sha256",
                "parallel",
                "context_per_slot",
                "cache_type_k=q8_0",
                "cache_type_v=q8_0",
                "chat template and P/G/L safe-prefix SHA-256",
                "each slot-cache file SHA-256 and byte length",
            ],
            "seed_files": seed["files"],
        },
        "one_time_seed": seed,
        "exact_turn_outputs": exact_outputs,
        "actual_request_identity": request_identity,
        "actual_prompt_token_identity": prompt_token_identity,
        "automatic_slot_selection_preserved_restored_prefixes": (
            restored_prefixes_reappeared if automatic_real_slots else None
        ),
        "restored_prefixes_reappeared": restored_prefixes_reappeared,
        "aggregate_delta_restored_minus_baseline_seconds": {
            key: {
                "median": _median(values),
                "total": sum(values),
                "wins": sum(value < 0.0 for value in values),
                "pairs": len(values),
                "minimum": min(values),
                "maximum": max(values),
            }
            for key, values in deltas.items()
        },
        "pairs": pairs,
        "candidate_status": (
            "research_only"
            if restored_prefixes_reappeared
            else "mechanism_failed"
        ),
        "promotion_rule": (
            "Require exact projected outputs, identical real payloads and "
            "prompt-token totals, verified model/server/profile/prefix/file "
            "bindings, increased P/G/L cache_n under automatic real-slot "
            "selection, and repeatable opposite-order gains after integrity "
            "checking plus restore are included. Seed cost remains explicit "
            "and must be amortized; no cache can enter installed assets without "
            "an attested Setup lifecycle and explicit authorization."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "schema",
                    "arm_order",
                    "exact_turn_outputs",
                    "actual_request_identity",
                    "actual_prompt_token_identity",
                    "automatic_slot_selection_preserved_restored_prefixes",
                    "restored_prefixes_reappeared",
                    "aggregate_delta_restored_minus_baseline_seconds",
                    "candidate_status",
                )
            },
            ensure_ascii=False,
        )
    )
    return (
        0
        if (
            exact_outputs
            and request_identity
            and prompt_token_identity
            and restored_prefixes_reappeared
        )
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
