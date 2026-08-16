"""Summarize a sealed local-model ABBA budget comparison.

The input reports intentionally contain only contract projections and stable
failure codes.  This analyzer preserves that privacy boundary while verifying
the preregistered order, identities, request counts, resource limits and zero
effects before emitting a development verdict.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


PREREGISTRATION_SCHEMA = "baxy.local-model-abba-preregistration.v1"
REPORT_SCHEMA = "baxy-mind-budget-gate-v6"
OUTPUT_SCHEMA = "baxy.local-model-abba-verdict.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path.name}")
    return value


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _profile_projection(profile: dict[str, Any]) -> dict[str, Any]:
    errors = profile.get("errors")
    latency = profile.get("latency_seconds")
    if not isinstance(errors, list) or not isinstance(latency, dict):
        raise ValueError("profile shape is invalid")
    stable_errors: list[str] = []
    for error in errors:
        if not isinstance(error, dict):
            raise ValueError("profile error is not an object")
        case_id = error.get("case_id")
        reason = error.get("reason")
        if not isinstance(case_id, str) or not isinstance(reason, str):
            raise ValueError("profile error is not stable")
        stable_errors.append(f"{case_id}:{reason}")
    projection: dict[str, Any] = {
        "status": profile.get("status"),
        "requests_expected": profile.get("requests_expected"),
        "requests_completed": profile.get("requests_completed"),
        "errors": stable_errors,
        "tree_ram_peak_mib": profile.get("tree_ram_peak_mib"),
        "startup": profile.get("startup"),
        "latency_seconds": latency,
    }
    if "process_tree_vram_peak_mib" in profile:
        projection["process_tree_vram_peak_mib"] = profile.get(
            "process_tree_vram_peak_mib"
        )
    return projection


def _median(values: list[float | int | None]) -> float | None:
    present = [float(value) for value in values if isinstance(value, (int, float))]
    return round(statistics.median(present), 3) if present else None


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    error_counts: Counter[str] = Counter()
    expected = 0
    completed = 0
    statuses: list[str] = []
    for row in rows:
        for profile_name in ("gpu", "cpu_fallback"):
            profile = row["profiles"][profile_name]
            expected += int(profile["requests_expected"])
            completed += int(profile["requests_completed"])
            statuses.append(str(profile["status"]))
            error_counts.update(
                f"{profile_name}:{error}" for error in profile["errors"]
            )
    gpu = [row["profiles"]["gpu"] for row in rows]
    cpu = [row["profiles"]["cpu_fallback"] for row in rows]
    return {
        "reports": len(rows),
        "requests_expected": expected,
        "requests_completed": completed,
        "errors": sum(error_counts.values()),
        "exact_contracts": completed - sum(error_counts.values()),
        "error_multiset": dict(sorted(error_counts.items())),
        "all_profiles_passed": all(status == "passed" for status in statuses),
        "median": {
            "gpu_vram_peak_mib": _median(
                [profile.get("process_tree_vram_peak_mib") for profile in gpu]
            ),
            "gpu_ram_peak_mib": _median(
                [profile.get("tree_ram_peak_mib") for profile in gpu]
            ),
            "cpu_ram_peak_mib": _median(
                [profile.get("tree_ram_peak_mib") for profile in cpu]
            ),
            "gpu_narrate_p50_seconds": _median(
                [profile["latency_seconds"]["narrate"]["p50"] for profile in gpu]
            ),
            "cpu_narrate_p50_seconds": _median(
                [profile["latency_seconds"]["narrate"]["p50"] for profile in cpu]
            ),
            "gpu_catalog_ready_seconds": _median(
                [profile["startup"]["catalog_ready_seconds"] for profile in gpu]
            ),
            "cpu_catalog_ready_seconds": _median(
                [profile["startup"]["catalog_ready_seconds"] for profile in cpu]
            ),
        },
    }


def summarize(
    *,
    repository_root: Path,
    preregistration_path: Path,
    active_model_path: Path,
    candidate_model_path: Path,
) -> dict[str, Any]:
    root = repository_root.resolve(strict=True)
    prereg_path = preregistration_path.resolve(strict=True)
    preregistration = _read_object(prereg_path)
    if preregistration.get("schema") != PREREGISTRATION_SCHEMA:
        raise ValueError("preregistration schema mismatch")
    if preregistration.get("status") != "sealed_before_abba":
        raise ValueError("preregistration was not sealed before ABBA")

    program = preregistration.get("program")
    variants = preregistration.get("variants")
    order = preregistration.get("order")
    if (
        not isinstance(program, dict)
        or not isinstance(variants, dict)
        or set(variants) != {"A", "B"}
        or not isinstance(order, list)
        or [entry.get("variant") for entry in order if isinstance(entry, dict)]
        != ["A", "B", "B", "A"]
    ):
        raise ValueError("ABBA preregistration shape mismatch")

    program_path = (root / str(program.get("path") or "")).resolve(strict=True)
    if _sha256(program_path) != program.get("sha256"):
        raise ValueError("measurement program changed after preregistration")

    model_paths = {
        "A": active_model_path.resolve(strict=True),
        "B": candidate_model_path.resolve(strict=True),
    }
    for variant, path in model_paths.items():
        identity = variants[variant]
        if (
            path.stat().st_size != identity.get("bytes")
            or _sha256(path) != identity.get("sha256")
        ):
            raise ValueError(f"variant {variant} identity mismatch")

    rows: list[dict[str, Any]] = []
    report_paths: set[Path] = set()
    for expected_position, entry in enumerate(order, start=1):
        if not isinstance(entry, dict) or entry.get("position") != expected_position:
            raise ValueError("ABBA position mismatch")
        variant = str(entry["variant"])
        report_path = (root / str(entry.get("output") or "")).resolve(strict=True)
        if report_path in report_paths:
            raise ValueError("ABBA report reused")
        report_paths.add(report_path)
        report = _read_object(report_path)
        if report.get("schema") != REPORT_SCHEMA:
            raise ValueError("measurement report schema mismatch")
        runtime = report.get("runtime")
        method = report.get("method")
        profiles = report.get("profiles")
        if (
            not isinstance(runtime, dict)
            or not isinstance(method, dict)
            or method.get("effects_executed") != 0
            or not isinstance(profiles, dict)
            or set(profiles) != {"gpu", "cpu_fallback"}
        ):
            raise ValueError("measurement report safety shape mismatch")
        gguf = runtime.get("gguf")
        expected_model = model_paths[variant]
        if (
            not isinstance(gguf, dict)
            or gguf.get("name") != expected_model.name
            or gguf.get("bytes") != expected_model.stat().st_size
        ):
            raise ValueError("measurement report model identity mismatch")
        projected_profiles = {
            name: _profile_projection(profiles[name])
            for name in ("gpu", "cpu_fallback")
        }
        for profile in projected_profiles.values():
            if (
                profile["requests_expected"] != 45
                or profile["requests_completed"] != 45
            ):
                raise ValueError("ABBA profile did not complete 45 requests")
        rows.append(
            {
                "position": expected_position,
                "variant": variant,
                "report": report_path.relative_to(root).as_posix(),
                "report_sha256": _sha256(report_path),
                "status": report.get("status"),
                "profiles": projected_profiles,
            }
        )

    aggregated = {
        variant: _aggregate([row for row in rows if row["variant"] == variant])
        for variant in ("A", "B")
    }
    candidate_passed = (
        aggregated["B"]["all_profiles_passed"]
        and aggregated["B"]["errors"] == 0
    )
    active_passed = (
        aggregated["A"]["all_profiles_passed"]
        and aggregated["A"]["errors"] == 0
    )
    return {
        "schema": OUTPUT_SCHEMA,
        "status": (
            "candidate_passed_development_requires_blind"
            if candidate_passed
            else "candidate_rejected"
        ),
        "preregistration": prereg_path.relative_to(root).as_posix(),
        "preregistration_sha256": _sha256(prereg_path),
        "order_verified": "ABBA",
        "program_sha256_verified": True,
        "model_hashes_verified": True,
        "reports": rows,
        "aggregate": aggregated,
        "comparison": {
            "active_passed": active_passed,
            "candidate_passed": candidate_passed,
            "candidate_gpu_narration_faster": (
                aggregated["B"]["median"]["gpu_narrate_p50_seconds"]
                < aggregated["A"]["median"]["gpu_narrate_p50_seconds"]
            ),
            "candidate_cpu_narration_faster": (
                aggregated["B"]["median"]["cpu_narrate_p50_seconds"]
                < aggregated["A"]["median"]["cpu_narrate_p50_seconds"]
            ),
        },
        "verdict": {
            "promotion_eligible": False,
            "active_manifest_changed": False,
            "effects_executed": 0,
            "reason": (
                "Candidate passed development; a distinct blind cut is still required."
                if candidate_passed
                else "Candidate failed the sealed contract workload; latency gains cannot compensate for a reproducible runtime failure."
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--active-model", type=Path, required=True)
    parser.add_argument("--candidate-model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository_root = Path(__file__).resolve().parents[2]
    result = summarize(
        repository_root=repository_root,
        preregistration_path=args.preregistration,
        active_model_path=args.active_model,
        candidate_model_path=args.candidate_model,
    )
    _write_json_atomic(args.output.resolve(), result)
    print(
        json.dumps(
            {
                "schema": result["schema"],
                "status": result["status"],
                "active": result["aggregate"]["A"],
                "candidate": result["aggregate"]["B"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
