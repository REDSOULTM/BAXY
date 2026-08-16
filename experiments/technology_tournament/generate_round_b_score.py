#!/usr/bin/env python3
"""Validate and score the final Round-B evidence deterministically.

Only the three explicitly numbered functional repetitions are eligible for the
two finalists.  Older unsuffixed WPF captures are deliberately never opened.
The two rejected WebView captures are retained as disqualification evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
import tempfile
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "technology_tournament"
RAW = ARTIFACTS / "raw"
PROTOCOL_PATH = ARTIFACTS / "protocol.json"
CASES_PATH = ROOT / "experiments" / "technology_tournament" / "cases.json"
SUPPLY_PATH = RAW / "round_b_supply_chain.json"
REPRODUCIBILITY_PATH = RAW / "round_b_reproducibility.json"
REPRODUCIBILITY_HARNESS_PATH = ROOT / "experiments" / "technology_tournament" / "round_b" / "reproducibility_harness.ps1"
OUTPUT = ARTIFACTS / "round_b_scorecard.json"
ROUND_A_SCORECARD_PATH = ARTIFACTS / "round_a_scorecard.json"
ROUND_A_PACKAGING_PATH = RAW / "packaging_results.json"
FUNCTIONAL_HARNESS_PATH = ROOT / "experiments" / "technology_tournament" / "round_b" / "harness.ps1"
LIFECYCLE_HARNESS_PATH = ROOT / "experiments" / "technology_tournament" / "round_b" / "lifecycle_harness.ps1"
PACKAGE_HARNESS_PATH = ROOT / "experiments" / "technology_tournament" / "round_b" / "package_lifecycle.ps1"
BUILD_RECIPE_PATH = ROOT / "experiments" / "technology_tournament" / "round_b" / "build_round_b.ps1"
OFFICIAL_WPF_SC_PATH = ARTIFACTS / "build" / "round_b" / "wpf_sc_shell"
SBOM_GENERATOR_PATH = ROOT / "experiments" / "technology_tournament" / "generate_round_b_sbom.py"
DOTNET_PIN_PATH = ROOT / "global.json"
DOTNET_PROJECT_PATH = ROOT / "experiments" / "technology_tournament" / "dotnet_windows_core" / "BaxySlice.csproj"
RUST_TOOLCHAIN_PATH = ROOT / "experiments" / "technology_tournament" / "rust_core" / "rust-toolchain.toml"
RUST_MANIFEST_PATH = ROOT / "experiments" / "technology_tournament" / "rust_core" / "Cargo.toml"
RUST_LOCK_PATH = ROOT / "experiments" / "technology_tournament" / "rust_core" / "Cargo.lock"
RUST_CONFIG_PATH = ROOT / "experiments" / "technology_tournament" / "rust_core" / ".cargo" / "config.toml"

SYSTEMS: dict[str, dict[str, Any]] = {
    "dotnet-wpf": {
        "slug": "dotnet_wpf",
        "family": ".NET/Windows",
        "architecture": ".NET 10 WPF native shell + .NET NativeAOT core",
        "core": ".NET NativeAOT",
        "toolchain_count": 1,
        "round_a_core_id": "dotnet_native_aot",
    },
    "dotnet-wpf-rust": {
        "slug": "dotnet_wpf_rust",
        "family": "coherent hybrid",
        "architecture": ".NET 10 WPF native shell + statically linked Rust core",
        "core": "Rust static MSVC",
        "toolchain_count": 2,
        "round_a_core_id": "rust_native",
    },
}

REJECTED_INPUTS = {
    "dotnet-webview": RAW / "round_b_dotnet_webview_rejected_network.json",
    "tauri-rust": RAW / "round_b_tauri_rust_rejected_network.json",
}

EXPECTED_WEIGHTS = {
    "verified_missions": 25,
    "resources": 15,
    "latency": 10,
    "ux_accessibility": 10,
    "privacy_security": 10,
    "installation_lifecycle": 10,
    "maintainability_testability": 10,
    "license_maturity": 5,
    "migration_reuse": 5,
}

EFFECT_CASES = {
    "T02_CREATE_NOTE",
    "T03_READ_NOTE",
    "T04_COMPOUND_CREATE_READ",
    "T05_TRASH_NOTE",
    "T06_RESTORE_NOTE",
    "T14_UNICODE_FILENAME",
}
HOSTILE_CASES = {
    "T09_BLOCK_TRAVERSAL",
    "T10_BLOCK_ABSOLUTE_PATH",
    "T11_BLOCK_NUL",
    "T12_REFUSE_PROTECTED_DELETE",
}


class EvidenceError(RuntimeError):
    """Raised when final evidence is missing, contradictory, or gate-failing."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"Missing required evidence: {relative(path)}")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"Invalid JSON evidence {relative(path)}: {exc}") from exc
    require(isinstance(value, dict), f"Evidence root must be an object: {relative(path)}")
    return value


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def source_record(path: Path) -> dict[str, str]:
    return {"path": relative(path), "sha256": sha256_file(path)}


def validate_current_file_record(record: dict[str, Any], label: str) -> Path:
    path_value = record.get("path") or record.get("pin_file")
    expected_hash = record.get("sha256") or record.get("pin_sha256")
    require(isinstance(path_value, str) and path_value, f"{label}: missing path")
    require(isinstance(expected_hash, str) and len(expected_hash) == 64, f"{label}: missing SHA-256")
    path = (ROOT / path_value).resolve()
    require(path.is_relative_to(ROOT.resolve()), f"{label}: path escaped the repository")
    require(path.is_file(), f"{label}: current file is missing")
    require(sha256_file(path) == expected_hash, f"{label}: current file drifted after reproducibility evidence")
    if "bytes" in record:
        require(record.get("bytes") == path.stat().st_size, f"{label}: current file byte count drifted")
    return path


def validate_provenance(
    data: dict[str, Any],
    expected: dict[str, Path],
    label: str,
) -> None:
    provenance = data.get("provenance")
    require(isinstance(provenance, dict), f"{label}: missing provenance")
    require(set(provenance) == set(expected), f"{label}: provenance input set drift")
    for name, expected_path in expected.items():
        record = provenance.get(name, {})
        path = validate_current_file_record(record, f"{label} {name}")
        require(path == expected_path.resolve(), f"{label}: {name} points at the wrong file")
        if "bytes" in record:
            require(record.get("bytes") == path.stat().st_size, f"{label}: {name} byte count drift")


def tree_inventory(path: Path) -> dict[str, Any]:
    require(path.is_dir(), f"Missing official artifact tree: {relative(path)}")
    files: list[dict[str, Any]] = []
    for item in sorted(
        (candidate for candidate in path.rglob("*") if candidate.is_file()),
        key=lambda candidate: (candidate.relative_to(path).as_posix().casefold(), candidate.relative_to(path).as_posix()),
    ):
        files.append(
            {
                "relative_path": item.relative_to(path).as_posix(),
                "bytes": item.stat().st_size,
                "sha256": sha256_file(item),
            }
        )
    rows = "".join(f"{item['relative_path']}\0{item['bytes']}\0{item['sha256']}\n" for item in files)
    return {
        "tree_sha256": hashlib.sha256(rows.encode("utf-8")).hexdigest(),
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "files": files,
    }


def tree_content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(
        (candidate for candidate in path.rglob("*") if candidate.is_file()),
        key=lambda candidate: (candidate.relative_to(path).as_posix().casefold(), candidate.relative_to(path).as_posix()),
    ):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(item.read_bytes())
    return digest.hexdigest()


def close(left: float, right: float, tolerance: float = 1e-6) -> bool:
    return math.isclose(float(left), float(right), rel_tol=tolerance, abs_tol=tolerance)


def percentile_linear(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(float(value) for value in values)
    require(bool(ordered), "Cannot derive a percentile from an empty sample")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def lower_is_better(value: float, full_at: float, zero_at: float, points: float) -> float:
    if value <= full_at:
        return points
    if value >= zero_at:
        return 0.0
    return points * (zero_at - value) / (zero_at - full_at)


def higher_is_better(value: float, zero_at: float, full_at: float, points: float) -> float:
    if value >= full_at:
        return points
    if value <= zero_at:
        return 0.0
    return points * (value - zero_at) / (full_at - zero_at)


def artifact_points(mib: float) -> float:
    if mib <= 100:
        return 4.0
    if mib >= 1000:
        return 0.0
    return 4.0 * (math.log(1000) - math.log(mib)) / (math.log(1000) - math.log(100))


def round_b_vram_points(mib: float) -> float:
    """Frozen Round-B curve: 4 at <=3 GiB, 2 at 4 GiB, 0 above 4 GiB."""
    if mib <= 3072:
        return 4.0
    if mib <= 4096:
        return 4.0 - 2.0 * (mib - 3072.0) / 1024.0
    return 0.0


def network_snapshot_empty(snapshot: dict[str, Any], *, require_samples: int | None = None) -> bool:
    if snapshot.get("observer_ok") is not True:
        return False
    if snapshot.get("observer") != "Get-NetTCPConnection+Get-NetUDPEndpoint":
        return False
    if snapshot.get("tcp") != [] or snapshot.get("udp") != []:
        return False
    samples = snapshot.get("samples")
    if require_samples is not None:
        if not isinstance(samples, list) or len(samples) != require_samples:
            return False
    if isinstance(samples, list):
        return all(
            isinstance(item, dict)
            and item.get("observer_ok") is True
            and item.get("observer") == "Get-NetTCPConnection+Get-NetUDPEndpoint"
            and item.get("tcp") == []
            and item.get("udp") == []
            for item in samples
        )
    return True


def package_launch_passed(launch: dict[str, Any]) -> bool:
    return all(
        (
            launch.get("passed") is True,
            launch.get("core_attested") is True,
            launch.get("mission_verified") is True,
            launch.get("effect_verified") is True,
            launch.get("journal_completed_records") == 1,
            launch.get("replay_visible") is True,
            launch.get("replay_single_effect") is True,
            launch.get("graceful_shutdown") is True,
            launch.get("orphan_process_ids") == [],
            launch.get("bundle_cache_bytes") == 0,
            launch.get("errors") == [],
            launch.get("network_observer_ok") is True,
            all(
                isinstance(snapshot, dict)
                and snapshot.get("observer_ok") is True
                and snapshot.get("observer") == "Get-NetTCPConnection+Get-NetUDPEndpoint"
                and snapshot.get("tcp") == []
                and snapshot.get("udp") == []
                for snapshot in launch.get("network_snapshots", [])
            ),
            len(launch.get("network_snapshots", [])) == 2,
        )
    )


def validate_protocol() -> tuple[dict[str, Any], dict[str, Any], list[str], dict[str, int]]:
    protocol = load_json(PROTOCOL_PATH)
    cases = load_json(CASES_PATH)
    require(protocol.get("protocol_id") == "baxy-technology-tournament-v1", "Unexpected protocol id")
    require(protocol.get("status") == "frozen-before-measurement", "Protocol was not frozen before measurement")
    require(protocol.get("weights") == EXPECTED_WEIGHTS, "Frozen score weights changed")
    require(sum(protocol["weights"].values()) == 100, "Frozen weights do not total 100")
    require(cases.get("protocol_id") == protocol["protocol_id"], "Cases do not bind the frozen protocol")
    case_list = cases.get("cases")
    require(isinstance(case_list, list) and len(case_list) == 16, "Round B requires the exact 16-case suite")
    case_ids = [case.get("id") for case in case_list]
    require(len(case_ids) == len(set(case_ids)), "Case ids are not unique")
    case_weights = {case["id"]: int(case["weight"]) for case in case_list}
    require(sum(case_weights.values()) == 34, "Unexpected functional case weight total")
    return protocol, cases, case_ids, case_weights


def validate_round_a_pareto_evidence(protocol: dict[str, Any]) -> dict[str, dict[str, Any]]:
    round_a = load_json(ROUND_A_SCORECARD_PATH)
    require(round_a.get("schema_version") == 1 and round_a.get("protocol_id") == protocol.get("protocol_id"), "Round-A Pareto evidence identity drift")
    require(round_a.get("source_results_sha256") == sha256_file(ROUND_A_PACKAGING_PATH), "Round-A Pareto scorecard is not bound to current packaging results")
    require(round_a.get("weights_unchanged") is True, "Round-A scorecard changed the frozen weights")
    require(round_a.get("round_a_promotion", {}).get("integrated_finalists") == ["dotnet_windows_core", "rust_core"], "Round-A promoted finalist set drift")
    frozen_dimensions = protocol.get("pareto_dimensions", [])
    require("build_seconds" in frozen_dimensions and "implementation_source_lines" in frozen_dimensions and len(frozen_dimensions) == 9, "Frozen Pareto dimension set drift")
    scores = round_a.get("scores", {})
    inherited: dict[str, dict[str, Any]] = {}
    for system_id, config in SYSTEMS.items():
        core_id = config["round_a_core_id"]
        score = scores.get(core_id, {})
        raw = score.get("raw", {})
        require(score.get("disqualified") is False and score.get("gate_failures") == [], f"Round-A promoted core is not eligible: {core_id}")
        require(raw.get("functional_weight_passed") == raw.get("functional_weight_total") == 34, f"Round-A promoted core contract drift: {core_id}")
        require(isinstance(raw.get("build_seconds"), (int, float)) and raw["build_seconds"] > 0, f"Round-A build time is invalid: {core_id}")
        require(isinstance(raw.get("implementation_source_lines"), int) and raw["implementation_source_lines"] > 0, f"Round-A source-line evidence is invalid: {core_id}")
        inherited[system_id] = {
            "core_id": core_id,
            "build_seconds": float(raw["build_seconds"]),
            "implementation_source_lines": int(raw["implementation_source_lines"]),
        }
    return inherited


def validate_functional_run(
    path: Path,
    data: dict[str, Any],
    system_id: str,
    case_ids: list[str],
    case_weights: dict[str, int],
) -> None:
    label = relative(path)
    require(data.get("schema_version") == 1, f"{label}: unsupported schema")
    require(data.get("protocol_id") == "baxy-technology-tournament-v1", f"{label}: protocol drift")
    require(data.get("round") == "b_integrated_system", f"{label}: wrong round")
    require(data.get("shell_id") == system_id, f"{label}: wrong system id")
    validate_provenance(
        data,
        {"harness": FUNCTIONAL_HARNESS_PATH, "protocol": PROTOCOL_PATH, "cases": CASES_PATH},
        label,
    )
    functional = data.get("functional", {})
    samples = functional.get("cases")
    require(isinstance(samples, list), f"{label}: missing functional cases")
    observed_ids = [sample.get("case_id") for sample in samples]
    require(observed_ids == case_ids, f"{label}: case order/set differs from the frozen suite")
    require(
        all(sample.get("weight") == case_weights[sample["case_id"]] for sample in samples),
        f"{label}: case weight drift",
    )
    passed_weight = sum(sample["weight"] for sample in samples if sample.get("passed") is True)
    require(functional.get("passed_weight") == passed_weight, f"{label}: passed-weight total is inconsistent")
    require(functional.get("total_weight") == sum(case_weights.values()), f"{label}: total weight is inconsistent")
    require(close(functional.get("pass_ratio", -1), passed_weight / sum(case_weights.values())), f"{label}: pass ratio is inconsistent")
    require(all(sample.get("passed") is True and sample.get("failures") == [] for sample in samples), f"{label}: a final functional case failed")
    require(all(sample.get("route") == "visible_composer" for sample in samples[:-1]), f"{label}: a natural-language case bypassed the visible composer")
    malformed = samples[-1]
    require(malformed.get("case_id") == "T16_MALFORMED_REQUEST" and malformed.get("route") == "raw_core_transport_probe", f"{label}: malformed transport was not probed against the integrated core")
    transport = malformed.get("transport_evidence", {})
    require(
        transport.get("passed") is True
        and transport.get("failures") == []
        and transport.get("process_survived") is True
        and transport.get("recovery_response_valid") is True
        and transport.get("recovery_response_state") == "done"
        and transport.get("stderr_redacted") is True
        and transport.get("stderr_record") == "BAXY_PROTOCOL_ERROR malformed_json"
        and transport.get("malformed_stdout_protocol_records") == 0
        and transport.get("filesystem_unchanged") is True
        and transport.get("filesystem_snapshot_scope") == "complete_workspace_before_recovery"
        and transport.get("workspace_before_malformed") == transport.get("workspace_after_malformed_before_recovery")
        and transport.get("exit_code") == 0
        and transport.get("timed_out") is False
        and network_snapshot_empty(transport.get("network_snapshot", {})),
        f"{label}: malformed-input recovery/redaction/network evidence failed",
    )
    hashes = data.get("hashes", {})
    require(
        set(hashes) == {"shell_bundle_sha256", "shell_entrypoint_sha256", "core_sha256", "source_tree_sha256"},
        f"{label}: incomplete hash binding",
    )
    require(all(isinstance(value, str) and len(value) == 64 for value in hashes.values()), f"{label}: invalid SHA-256")
    bundle_scope = data.get("shell_bundle_scope", {})
    bundle_files = bundle_scope.get("files", [])
    require(bundle_scope.get("kind") == "explicit_fdd_runtime_files_loaded_by_the_measured_shell", f"{label}: functional shell bundle scope is ambiguous")
    require(isinstance(bundle_files, list) and len(bundle_files) == 4, f"{label}: expected the four effective FDD shell files")
    require(len({record.get("path") for record in bundle_files}) == 4, f"{label}: duplicate effective shell file")
    effective_paths = [validate_current_file_record(record, f"{label}: effective FDD shell file") for record in bundle_files]
    effective_digest = hashlib.sha256()
    for effective_path in sorted(set(effective_paths)):
        effective_digest.update(relative(effective_path).encode("utf-8"))
        effective_digest.update(effective_path.read_bytes())
    require(effective_digest.hexdigest() == hashes["shell_bundle_sha256"], f"{label}: effective FDD shell hash is inconsistent")
    require(sum(path.stat().st_size for path in effective_paths) == data.get("shell_bundle_bytes"), f"{label}: effective FDD shell byte count is inconsistent")
    accessibility = data.get("accessibility", {})
    require(accessibility.get("live_region_events") == 32, f"{label}: expected exactly 32 live-region events")
    require(accessibility.get("core_ready_visible") is True, f"{label}: core readiness was not visible")
    require(accessibility.get("technical_runtime_hidden") is True, f"{label}: technical runtime leaked into UI")
    require(accessibility.get("raw_protocol_hidden") is True, f"{label}: raw protocol leaked into UI")
    require(accessibility.get("composer_named") is True and accessibility.get("send_named") is True, f"{label}: unnamed primary control")
    controls = accessibility.get("focusable_controls", [])
    require(isinstance(controls, list) and len(controls) == 7, f"{label}: incomplete focusable-control catalog")
    expected_focus_controls = {
        ("InvocationInput", "ID de invocación de prueba"),
        ("MessageInput", "Mensaje para BAXY"),
        ("SendButton", "Enviar mensaje"),
        ("ContrastButton", "Alternar contraste alto"),
        ("", "Crear una nota"),
        ("", "Leer una nota"),
        ("", "Mover a papelera"),
    }
    require({(control.get("automation_id"), control.get("name")) for control in controls} == expected_focus_controls, f"{label}: expected tab-stop control set drift")
    control_keys = [control.get("key") for control in controls]
    require(all(isinstance(key, str) and key for key in control_keys) and len(control_keys) == len(set(control_keys)), f"{label}: invalid focusable-control identities")
    start_key = accessibility.get("focus_start_key")
    forward = accessibility.get("forward_focus_order", [])
    reverse = accessibility.get("reverse_focus_order", [])
    expected_reverse = [start_key, *reversed(forward[1:-1]), start_key]
    require(
        accessibility.get("forward_focus_cycle_complete") is True
        and accessibility.get("reverse_focus_cycle_complete") is True
        and start_key in control_keys
        and len(forward) == len(controls) + 1
        and len(reverse) == len(controls) + 1
        and forward[0] == forward[-1] == start_key
        and reverse[0] == reverse[-1] == start_key
        and len(set(forward[:-1])) == len(controls)
        and set(forward[:-1]) == set(control_keys)
        and reverse == expected_reverse,
        f"{label}: complete forward/reverse focus cycle failed",
    )
    require(accessibility.get("keyboard_submit_case") == "T01_CONVERSATION", f"{label}: keyboard submit was not exercised")
    resources = data.get("resources", {})
    require(network_snapshot_empty(resources.get("network_snapshot", {}), require_samples=18), f"{label}: sampled network gate failed")
    gpu = resources.get("gpu", {})
    require(
        gpu.get("idle", {}).get("source") == "Win32_PerfFormattedData_GPUPerformanceCounters_GPUProcessMemory",
        f"{label}: GPU source is not the declared process counter",
    )
    require(data.get("cleanup", {}).get("passed") is True, f"{label}: cleanup failed")
    require(data.get("cleanup", {}).get("orphan_process_ids") == [], f"{label}: orphan processes remain")


def validate_lifecycle(
    path: Path,
    data: dict[str, Any],
    system_id: str,
    functional_hashes: dict[str, str],
) -> dict[str, bool]:
    label = relative(path)
    require(data.get("schema_version") == 1, f"{label}: unsupported schema")
    require(data.get("protocol_id") == "baxy-technology-tournament-v1", f"{label}: protocol drift")
    require(data.get("round") == "b_lifecycle" and data.get("system_id") == system_id, f"{label}: identity drift")
    validate_provenance(
        data,
        {"harness": LIFECYCLE_HARNESS_PATH, "protocol": PROTOCOL_PATH, "cases": CASES_PATH},
        label,
    )
    require(data.get("hashes") == {key: functional_hashes[key] for key in ("shell_bundle_sha256", "shell_entrypoint_sha256", "core_sha256")}, f"{label}: lifecycle hashes do not match functional evidence")

    cold = data.get("cold_start", {})
    cold_samples = cold.get("samples", [])
    cold_values = [sample.get("ready_ms") for sample in cold_samples if sample.get("valid") is True]
    require(cold.get("repetitions") == 7 and cold.get("valid") == 7 and len(cold_values) == 7, f"{label}: cold-start sample count drift")
    require(all(sample.get("root_exited_prematurely") is False and sample.get("orphan_process_ids") == [] for sample in cold_samples), f"{label}: a cold-start root exited prematurely or left orphan processes")
    require(close(cold.get("p50_ms", -1), percentile_linear(cold_values, 0.50)), f"{label}: cold p50 is inconsistent")
    require(close(cold.get("p95_ms", -1), percentile_linear(cold_values, 0.95)), f"{label}: cold p95 is inconsistent")

    warm = data.get("warm_ui", {})
    warm_samples = warm.get("samples", [])
    warm_values = [sample.get("elapsed_ms") for sample in warm_samples if sample.get("valid") is True]
    require(warm.get("valid") == 30 and len(warm_values) == 30, f"{label}: warm sample count drift")
    require(warm.get("warmup_discarded", {}).get("index") == 0, f"{label}: warm-up was not explicitly discarded")
    require(close(warm.get("p50_ms", -1), percentile_linear(warm_values, 0.50)), f"{label}: warm p50 is inconsistent")
    require(close(warm.get("p95_ms", -1), percentile_linear(warm_values, 0.95)), f"{label}: warm p95 is inconsistent")
    require(close(warm.get("throughput_per_second", -1), 1000.0 / statistics.mean(warm_values)), f"{label}: throughput is inconsistent")
    require(warm.get("orphan_process_ids") == [], f"{label}: warm run left orphan processes")

    single = data.get("single_instance", {})
    crash = data.get("crash_and_restart", {})
    scale = data.get("scale_and_contrast", {})
    gates = {
        "cold_and_warm_samples": all(sample.get("root_exited_prematurely") is False and sample.get("orphan_process_ids") == [] for sample in cold_samples),
        "single_instance": single.get("passed") is True
        and single.get("second_exited_within_ms") == 3000
        and single.get("second_exit_code") == 0
        and isinstance(single.get("primary_core_pid"), int)
        and single.get("primary_core_pid") > 0,
        "process_ownership_and_cleanup": warm.get("orphan_process_ids") == []
        and crash.get("crash_orphan_process_ids") == []
        and crash.get("graceful_restart_orphan_process_ids") == []
        and scale.get("orphan_process_ids") == [],
        "crash_restart_and_data": crash.get("create_verified") is True
        and crash.get("job_cleanup_passed") is True
        and crash.get("restart_read_verified") is True,
        "scale_equivalent_and_contrast": scale.get("controls_contained") is True
        and scale.get("responsive_activity_hidden") is True
        and scale.get("editor_offscreen") is False
        and scale.get("send_offscreen") is False
        and scale.get("contrast_toggled") is True
        and float(scale.get("sampled_pixel_change_ratio", 0)) >= 0.05,
    }
    require(all(gates.values()), f"{label}: lifecycle gate failed: {[key for key, value in gates.items() if not value]}")
    return gates


def validate_package(path: Path, data: dict[str, Any], system_id: str, core_sha256: str) -> dict[str, bool]:
    label = relative(path)
    require(data.get("schema_version") == 2, f"{label}: unsupported package schema")
    require(data.get("protocol_id") == "baxy-technology-tournament-v1", f"{label}: protocol drift")
    require(data.get("round") == "b_package_lifecycle" and data.get("system_id") == system_id, f"{label}: identity drift")
    validate_provenance(
        data,
        {
            "harness": PACKAGE_HARNESS_PATH,
            "cases": CASES_PATH,
            "protocol": PROTOCOL_PATH,
            "build_recipe": BUILD_RECIPE_PATH,
        },
        label,
    )
    require(data.get("hashes", {}).get("core_sha256") == core_sha256, f"{label}: packaged core differs from functional core")
    expected_package_gates = {
        "reparse_defense",
        "install",
        "update",
        "tampered_payload_rejected",
        "rollback",
        "uninstall_keep_data",
        "reinstall",
        "uninstall_purge_data",
    }
    gates = data.get("gates", {})
    require(set(gates) == expected_package_gates, f"{label}: package gate set drift")
    require(all(value is True for value in gates.values()), f"{label}: package lifecycle gate failed")
    require(data.get("failed_gates") == [] and data.get("overall_passed") is True, f"{label}: contradictory package verdict")
    require(data.get("package_integrity", {}).get("authenticity") == "not_provided", f"{label}: authenticity claim changed without scorer review")
    require(data.get("package_integrity", {}).get("tampered_payload_rejected") is True, f"{label}: tampered payload was accepted")
    require(data.get("package_integrity", {}).get("content_tampered_payload_rejected") is True, f"{label}: default-stream tamper was accepted")
    require(data.get("package_integrity", {}).get("alternate_data_stream_observed") is True, f"{label}: hostile ADS fixture was not observed")
    require(data.get("package_integrity", {}).get("alternate_data_stream_payload_rejected") is True, f"{label}: alternate data stream was accepted")
    require(data.get("reparse_defense") == {"rejected": True, "external_sentinel_preserved": True}, f"{label}: reparse defense failed")
    runtime = data.get("runtime_resolution_probe", {})
    require(runtime.get("clean_machine_claimed") is False, f"{label}: an unexecuted clean-machine claim was introduced")
    require(runtime.get("shared_with_install_launch") is True, f"{label}: first/install launch alias is not declared")
    require(runtime.get("first_launch") == data.get("install", {}).get("launch"), f"{label}: declared shared first launch differs from install launch")
    launches = [
        data.get("install", {}).get("launch", {}),
        data.get("update", {}).get("launch", {}),
        data.get("rollback", {}).get("launch", {}),
        data.get("reinstall", {}).get("launch", {}),
    ]
    require(all(package_launch_passed(launch) for launch in launches), f"{label}: an installed launch/effect/replay check failed")
    require(data.get("update", {}).get("payload_changed") is True, f"{label}: update payload did not change")
    tampered_update = data.get("tampered_update", {})
    require(
        tampered_update.get("rejected") is True
        and tampered_update.get("content_tamper_rejected") is True
        and tampered_update.get("alternate_data_stream_rejected") is True
        and tampered_update.get("current_after_content_tamper") == "1.0.1"
        and tampered_update.get("current_after_alternate_data_stream_tamper") == "1.0.1"
        and tampered_update.get("current_unchanged") is True,
        f"{label}: tampered update gate failed",
    )
    require(isinstance(data.get("package_bytes"), int) and data["package_bytes"] > 0, f"{label}: invalid package size")
    return {key: bool(value) for key, value in gates.items()}


def validate_supply_chain(
    supply: dict[str, Any],
    packages: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]]]:
    require(supply.get("schema_version") == 1, "Unsupported supply-chain schema")
    require(supply.get("protocol_id") == "baxy-technology-tournament-v1", "Supply-chain protocol drift")
    require(supply.get("round") == "b_supply_chain", "Wrong supply-chain round")
    provenance = supply.get("provenance", {})
    require(isinstance(provenance, dict) and set(provenance) == {"generator", "protocol", "package_evidence", "build_inputs"}, "Supply-chain provenance set drift")
    generator_path = validate_current_file_record(provenance.get("generator", {}), "Supply-chain generator")
    protocol_path = validate_current_file_record(provenance.get("protocol", {}), "Supply-chain protocol")
    require(generator_path == SBOM_GENERATOR_PATH.resolve() and protocol_path == PROTOCOL_PATH.resolve(), "Supply-chain generator/protocol provenance points at the wrong file")
    build_inputs = provenance.get("build_inputs", {})
    expected_build_inputs = {
        "dotnet_pin": DOTNET_PIN_PATH,
        "dotnet_project": DOTNET_PROJECT_PATH,
        "rust_toolchain": RUST_TOOLCHAIN_PATH,
        "rust_manifest": RUST_MANIFEST_PATH,
        "rust_lock": RUST_LOCK_PATH,
    }
    require(set(build_inputs) == set(expected_build_inputs), "Supply-chain build-input provenance set drift")
    for name, expected_path in expected_build_inputs.items():
        observed = validate_current_file_record(build_inputs.get(name, {}), f"Supply-chain {name}")
        require(observed == expected_path.resolve(), f"Supply-chain {name} points at the wrong file")
    package_sources = provenance.get("package_evidence", {})
    require(set(package_sources) == set(SYSTEMS), "Supply-chain package provenance finalist set drift")
    for system_id, config in SYSTEMS.items():
        expected_path = RAW / f"round_b_package_{config['slug']}.json"
        observed = validate_current_file_record(package_sources.get(system_id, {}), f"Supply-chain package evidence {system_id}")
        require(observed == expected_path.resolve(), f"Supply-chain package provenance path drift for {system_id}")
    reports = supply.get("systems")
    require(isinstance(reports, list), "Supply-chain system reports are missing")
    by_id = {report.get("system_id"): report for report in reports}
    require(set(by_id) == set(SYSTEMS), "Supply-chain finalist set drift")
    sbom_sources: dict[str, dict[str, str]] = {}
    for system_id, report in by_id.items():
        package = packages[system_id]
        require(report.get("package_bytes") == package.get("package_bytes"), f"Supply chain/package byte mismatch for {system_id}")
        require(report.get("core_sha256") == package.get("hashes", {}).get("core_sha256"), f"Supply chain/core mismatch for {system_id}")
        require(report.get("shell_sha256") == package.get("hashes", {}).get("shell_entrypoint_sha256"), f"Supply chain/shell mismatch for {system_id}")
        require(report.get("manifest_all_files_verified") is True, f"Package file hashes were not all verified for {system_id}")
        require(report.get("package_gates_passed") == 8, f"Supply-chain package gate count drift for {system_id}")
        require(report.get("manifest_authenticity") == "not_provided", f"Manifest authenticity claim drift for {system_id}")
        require(report.get("authenticode_source") == "round_b_package_lifecycle.signatures", f"Authenticode source drift for {system_id}")
        require(report.get("authenticode") == package.get("signatures") == {"shell": "NotSigned", "core": "NotSigned"}, f"Authenticode evidence drift for {system_id}")
        sbom_path = (ROOT / report.get("sbom_path", "")).resolve()
        require(sbom_path.is_relative_to(ARTIFACTS.resolve()), f"SBOM escaped artifact root for {system_id}")
        require(sbom_path.is_file(), f"SBOM is missing for {system_id}")
        require(sha256_file(sbom_path) == report.get("sbom_sha256"), f"SBOM hash mismatch for {system_id}")
        sbom = load_json(sbom_path)
        require(sbom.get("bomFormat") == "CycloneDX" and sbom.get("specVersion") == "1.6", f"Invalid CycloneDX identity for {system_id}")
        require(sbom.get("metadata", {}).get("component", {}).get("hashes") == [{"alg": "SHA-256", "content": report.get("package_manifest_sha256")}], f"SBOM root is not bound to package manifest for {system_id}")
        require(report.get("sbom_component_count") == len(sbom.get("components", [])) + 1, f"SBOM component count mismatch for {system_id}")
        if system_id == "dotnet-wpf-rust":
            forbidden = {"vcruntime140.dll", "ucrtbase.dll", "msvcp140.dll"}
            require(not forbidden.intersection(report.get("core_imports", [])), "Rust core is not statically CRT-linked")
            require(report.get("external_application_packages") == 5, "Active Rust crate inventory drift")
            rust_core = next((component for component in sbom.get("components", []) if component.get("bom-ref") == "baxy:rust-core"), None)
            require(isinstance(rust_core, dict) and rust_core.get("licenses") == [{"license": {"id": "MIT"}}], "Rust first-party crate license was not carried from Cargo.toml")
        else:
            require(report.get("external_application_packages") == 0, "Unexpected external app package in pure .NET finalist")
        sbom_sources[system_id] = source_record(sbom_path)
    known_gaps = supply.get("known_gaps", [])
    require(any("license" in gap.lower() for gap in known_gaps), "Missing first-party license gap")
    require(any("authenticode" in gap.lower() for gap in known_gaps), "Missing executable-signing gap")
    require(any("authentic" in gap.lower() for gap in known_gaps), "Missing manifest-authenticity gap")
    return by_id, sbom_sources


def validate_reproducibility() -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if not REPRODUCIBILITY_PATH.is_file():
        return None, {
            "status": "not_present",
            "points_effect": "installation.reproducible_clean_build receives 0/2; no NE is used in the final round",
        }
    data = load_json(REPRODUCIBILITY_PATH)
    require(data.get("schema_version") == 1, "Unsupported reproducibility schema")
    require(data.get("evidence_id") == "round_b_reproducibility", "Wrong reproducibility evidence id")
    if "protocol_id" in data:
        require(data.get("protocol_id") == "baxy-technology-tournament-v1", "Reproducibility protocol drift")
    validate_provenance(data, {"harness": REPRODUCIBILITY_HARNESS_PATH}, "Reproducibility")
    gates = data.get("gates", {})
    required_gates = {
        "toolchains_pinned",
        "repository_sdk_toolchains_pinned",
        "host_native_toolchain_observed",
        "build_directories_ignored",
        "inputs_unchanged",
        "input_replicas_exact",
        "independent_builds_succeeded",
        "wpf_self_contained_reproducible",
        "dotnet_native_aot_reproducible",
        "rust_static_reproducible",
        "rust_static_crt",
        "all_passed",
    }
    require(required_gates.issubset(gates), "Reproducibility gate set is incomplete")
    require(data.get("passed") is True and all(gates[name] is True for name in required_gates), "Reproducibility gate failed")

    scope = data.get("scope", {})
    require(
        scope.get("classification") == "same_host_isolated_source_replicas_shared_caches"
        and scope.get("source_replicas_isolated") is True
        and scope.get("output_roots_isolated") is True
        and scope.get("process_runs_separate") is True
        and scope.get("host_shared") is True
        and scope.get("global_caches_shared") is True
        and scope.get("clean_environment") is False
        and scope.get("cross_host") is False
        and scope.get("cache_state_reset_between_runs") is False
        and scope.get("official_packaging_artifacts_modified") is False,
        "Reproducibility environment scope is overstated or incomplete",
    )

    recipe_path = validate_current_file_record(data.get("recipe", {}), "Reproducibility recipe")
    require(recipe_path == BUILD_RECIPE_PATH.resolve(), "Reproducibility recipe points at the wrong file")
    toolchains = data.get("toolchains", {})
    dotnet_pin_path = validate_current_file_record(toolchains.get("dotnet", {}), ".NET toolchain pin")
    rust_pin_path = validate_current_file_record(toolchains.get("rust", {}), "Rust toolchain pin")
    require(dotnet_pin_path == DOTNET_PIN_PATH.resolve(), ".NET reproducibility pin points at the wrong file")
    require(rust_pin_path == RUST_TOOLCHAIN_PATH.resolve(), "Rust reproducibility pin points at the wrong file")
    rust_config = toolchains.get("rust_static_crt_configuration", {})
    rust_config_path = validate_current_file_record(rust_config, "Rust static-link configuration")
    require(rust_config_path == RUST_CONFIG_PATH.resolve(), "Rust static-link configuration points at the wrong file")
    require(rust_config.get("configured") is True, "Rust static CRT was not configured")
    require(rust_config.get("deterministic_link_configured") is True, "Rust deterministic linker mode was not configured")

    host_native = toolchains.get("host_native", {})
    linker = host_native.get("linker", {})
    windows_sdk = host_native.get("windows_sdk", {})
    require(
        host_native.get("classification") == "observed_same_host_native_toolchain"
        and host_native.get("repository_pinned") is False
        and host_native.get("passed") is True
        and isinstance(host_native.get("msvc_tools_version"), str)
        and bool(host_native.get("msvc_tools_version")),
        "Host native toolchain identity is missing or falsely described as pinned",
    )
    linker_path_value = linker.get("path")
    require(isinstance(linker_path_value, str) and linker_path_value, "Observed linker path is missing")
    linker_path = Path(linker_path_value)
    require(linker_path.is_file(), "Observed link.exe is no longer present")
    require(sha256_file(linker_path) == linker.get("file_sha256"), "Observed link.exe binary hash drift")
    require(sha256_text(linker_path_value.lower()) == linker.get("path_sha256"), "Observed link.exe path hash drift")
    require(all(isinstance(linker.get(name), str) and linker.get(name) for name in ("file_version", "product_version")), "Observed link.exe version is incomplete")
    sdk_directory_value = windows_sdk.get("directory")
    require(windows_sdk.get("discovered") is True and isinstance(windows_sdk.get("version"), str) and windows_sdk.get("version"), "Observed Windows SDK identity is incomplete")
    require(isinstance(sdk_directory_value, str) and Path(sdk_directory_value).is_dir(), "Observed Windows SDK directory is missing")
    require(sha256_text(sdk_directory_value.lower()) == windows_sdk.get("directory_path_sha256"), "Observed Windows SDK directory path hash drift")
    library_paths = windows_sdk.get("native_library_paths", [])
    require(isinstance(library_paths, list) and library_paths and all(record.get("exists") is True and isinstance(record.get("path"), str) and Path(record["path"]).is_dir() and sha256_text(record["path"].lower()) == record.get("path_sha256") for record in library_paths), "Observed native library path identity is incomplete")
    binding = toolchains.get("host_native_build_binding", {})
    identity_hash = binding.get("identity_sha256")
    require(
        binding.get("both_builds_captured_identity") is True
        and binding.get("both_runs_match_observed_identity") is True
        and binding.get("passed") is True
        and isinstance(identity_hash, str)
        and len(identity_hash) == 64
        and binding.get("run_01_identity_sha256") == identity_hash
        and binding.get("run_02_identity_sha256") == identity_hash,
        "Build logs were not bound to the observed host-native toolchain",
    )

    snapshots = data.get("input_snapshots", {})
    snapshot_names = (
        "before_run_01",
        "between_runs",
        "after_run_02",
        "run_01_replica",
        "run_02_replica",
    )
    require(snapshots.get("unchanged") is True, "Build inputs changed between reproducibility runs")
    require(snapshots.get("replicas_exact") is True, "Isolated build replicas differed from source inputs")
    recorded_snapshots = [snapshots.get(name) for name in snapshot_names]
    require(all(isinstance(snapshot, dict) for snapshot in recorded_snapshots), "Reproducibility input snapshots are incomplete")
    tree_hashes = {snapshot.get("tree_sha256") for snapshot in recorded_snapshots}
    require(len(tree_hashes) == 1, "Reproducibility input snapshot hashes differ")
    current_snapshot = snapshots["after_run_02"]
    records = current_snapshot.get("files")
    require(isinstance(records, list) and records, "Reproducibility source file inventory is empty")
    relative_paths = [record.get("relative_path") for record in records if isinstance(record, dict)]
    require(len(relative_paths) == len(records) == len(set(relative_paths)), "Reproducibility source paths are invalid or duplicated")
    total_bytes = 0
    tree_rows: list[str] = []
    for record in records:
        path_value = record.get("relative_path")
        require(isinstance(path_value, str) and path_value and ".." not in Path(path_value).parts, "Unsafe reproducibility source path")
        path = (ROOT / path_value).resolve()
        require(path.is_relative_to(ROOT.resolve()) and path.is_file(), f"Current reproducibility input is missing: {path_value}")
        size = path.stat().st_size
        digest = sha256_file(path)
        require(size == record.get("bytes") and digest == record.get("sha256"), f"Current reproducibility input drifted: {path_value}")
        total_bytes += size
        tree_rows.append(f"{path_value}\0{size}\0{digest}\n")
    require(current_snapshot.get("file_count") == len(records), "Reproducibility source file count drift")
    require(current_snapshot.get("total_bytes") == total_bytes, "Reproducibility source byte count drift")
    require(
        hashlib.sha256("".join(tree_rows).encode("utf-8")).hexdigest() == current_snapshot.get("tree_sha256"),
        "Reproducibility source tree digest is inconsistent",
    )
    builds = data.get("builds", [])
    require(len(builds) == 2, "Reproducibility requires two independent builds")
    require(all(build.get("exit_code") == 0 and build.get("passed") is True for build in builds), "An independent build failed")
    for index, build in enumerate(builds, start=1):
        require(
            build.get("source_isolation") == "separate_exact_source_replica"
            and build.get("host_scope") == "same_host_as_other_run"
            and build.get("global_package_caches") == "shared_between_runs"
            and build.get("clean_environment") is False
            and build.get("cross_host") is False
            and build.get("build_metadata_captured") is True
            and build.get("build_metadata_error") is None
            and build.get("build_reported_dotnet_sdk") == "10.0.100"
            and str(build.get("build_reported_rustc", "")).startswith("rustc 1.97.0 (")
            and build.get("build_reported_reproduction_classification") == {
                "host_scope": "single_host",
                "output_root_isolated": True,
                "source_replica_isolation": "provided_by_reproducibility_harness",
                "global_package_caches": "shared_host_caches",
                "clean_environment": False,
                "cross_host": False,
            }
            and build.get("native_link_toolchain") == host_native
            and build.get("native_link_toolchain_sha256") == identity_hash,
            f"Reproducibility run {index} metadata classification/binding drift",
        )
        for log_key, hash_key in (("stdout_log", "stdout_sha256"), ("stderr_log", "stderr_sha256")):
            log_value = build.get(log_key)
            require(isinstance(log_value, str), f"Reproducibility run {index} missing {log_key}")
            log_path = (ROOT / log_value).resolve()
            require(log_path.is_relative_to(ARTIFACTS.resolve()) and log_path.is_file(), f"Reproducibility run {index} log escaped or is missing")
            require(sha256_file(log_path) == build.get(hash_key), f"Reproducibility run {index} log hash drift")
    comparisons = data.get("comparisons", {})
    for name in ("wpf_self_contained", "dotnet_native_aot", "rust_static"):
        comparison = comparisons.get(name, {})
        require(comparison.get("same_file_set") is True, f"{name}: reproduced file set differs")
        require(comparison.get("artifact_hashes_equal") is True, f"{name}: reproduced artifact hashes differ")
        require(comparison.get("tree_hash_equal") is True, f"{name}: reproduced tree hashes differ")
        require(comparison.get("passed") is True, f"{name}: reproducibility comparison failed")
    runtime = data.get("rust_static_runtime", {})
    runtime_runs = runtime.get("runs", [])
    require(
        runtime.get("imports_equal") is True
        and runtime.get("passed") is True
        and len(runtime_runs) == 2
        and all(
            run.get("forbidden_imports") == []
            and run.get("dumpbin_exit_code") == 0
            and run.get("passed") is True
            for run in runtime_runs
        ),
        "Rust CRT runtime audit failed",
    )
    return data, {"status": "passed", **source_record(REPRODUCIBILITY_PATH)}


def validate_reproducibility_bindings(
    reproducibility: dict[str, Any] | None,
    packages: dict[str, dict[str, Any]],
) -> None:
    if reproducibility is None:
        return
    comparisons = reproducibility["comparisons"]
    expected = {
        "wpf_self_contained": packages["dotnet-wpf"]["hashes"]["shell_entrypoint_sha256"],
        "dotnet_native_aot": packages["dotnet-wpf"]["hashes"]["core_sha256"],
        "rust_static": packages["dotnet-wpf-rust"]["hashes"]["core_sha256"],
    }
    for name, expected_hash in expected.items():
        primary = comparisons[name].get("primary_artifact", {})
        require(primary.get("equal") is True, f"{name}: reproduced primary artifacts differ")
        require(
            primary.get("run_01_sha256") == expected_hash
            and primary.get("run_02_sha256") == expected_hash,
            f"{name}: reproducible artifact hash is not the officially packaged hash",
        )
    official_wpf = tree_inventory(OFFICIAL_WPF_SC_PATH)
    reproduced_wpf = comparisons["wpf_self_contained"]
    require(official_wpf == reproduced_wpf.get("run_01") == reproduced_wpf.get("run_02"), "The complete official self-contained WPF tree differs from both reproducible builds")
    official_content_hash = tree_content_hash(OFFICIAL_WPF_SC_PATH)
    require(
        all(package.get("hashes", {}).get("shell_bundle_sha256") == official_content_hash for package in packages.values()),
        "The package shell-bundle hash is not the complete official self-contained WPF tree",
    )


def make_cell(
    points: float,
    maximum: float,
    *,
    method: str,
    criterion: str,
    evidence: Any,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    require(0 <= points <= maximum, f"Invalid cell score {points}/{maximum}")
    return {
        "status": method,
        "points": round(float(points), 6),
        "maximum": maximum,
        "criterion": criterion,
        "evidence": evidence,
        "limitations": limitations or [],
    }


def score_system(
    system_id: str,
    runs: list[dict[str, Any]],
    lifecycle: dict[str, Any],
    package: dict[str, Any],
    supply: dict[str, Any],
    lifecycle_gates: dict[str, bool],
    package_gates: dict[str, bool],
    reproducibility: dict[str, Any] | None,
    round_a_pareto: dict[str, Any],
) -> dict[str, Any]:
    config = SYSTEMS[system_id]
    cases = [case for run in runs for case in run["functional"]["cases"]]
    passed_weight = sum(case["weight"] for case in cases if case["passed"])
    total_weight = sum(case["weight"] for case in cases)
    functional_ratio = passed_weight / total_weight
    idle_mib = statistics.median(run["resources"]["idle"]["private_bytes"] for run in runs) / 1_048_576
    peak_mib = statistics.median(run["resources"]["max_sampled_private_bytes"] for run in runs) / 1_048_576
    gpu_peak_mib = statistics.median(run["resources"]["gpu"]["max_sampled_dedicated_bytes"] for run in runs) / 1_048_576
    gpu_shared_peak_mib = statistics.median(run["resources"]["gpu"]["max_sampled_shared_bytes"] for run in runs) / 1_048_576
    package_mib = package["package_bytes"] / 1_048_576
    cold_p95 = float(lifecycle["cold_start"]["p95_ms"])
    warm_p95 = float(lifecycle["warm_ui"]["p95_ms"])
    throughput = float(lifecycle["warm_ui"]["throughput_per_second"])
    by_case = {
        case_id: [
            next(case for case in run["functional"]["cases"] if case["case_id"] == case_id)
            for run in runs
        ]
        for case_id in (case["case_id"] for case in runs[0]["functional"]["cases"])
    }
    all_network_empty = all(network_snapshot_empty(run["resources"]["network_snapshot"], require_samples=18) for run in runs)
    hard_gates = {
        "functional_90_percent": functional_ratio >= 0.90,
        "hostile_inputs_and_protected_target": all(all(sample["passed"] for sample in by_case[case_id]) for case_id in HOSTILE_CASES),
        "no_sampled_network_or_listeners": all_network_empty,
        "verified_effects": all(all(sample["passed"] for sample in by_case[case_id]) for case_id in EFFECT_CASES),
        "idempotent_replay": all(sample["passed"] for sample in by_case["T07_IDEMPOTENT_REPLAY"]),
        "journal_tail_recovery": all(sample["passed"] for sample in by_case["T15_TRUNCATED_JOURNAL_RECOVERY"]),
        "malformed_input_redacted_and_process_survives": all(sample["passed"] for sample in by_case["T16_MALFORMED_REQUEST"]),
        "functional_cleanup": all(run["cleanup"]["passed"] and run["cleanup"]["orphan_process_ids"] == [] for run in runs),
        "lifecycle": all(lifecycle_gates.values()),
        "package_lifecycle": all(package_gates.values()),
        "supply_chain_bound": supply["core_sha256"] == package["hashes"]["core_sha256"],
    }
    require(all(hard_gates.values()), f"{system_id}: finalist hard gate failed: {[key for key, value in hard_gates.items() if not value]}")

    cells: dict[str, dict[str, Any]] = {}
    cells["verified_missions"] = make_cell(
        25.0 * functional_ratio,
        25,
        method="measured",
        criterion="Frozen formula: 25 × passed case-weight / total case-weight across the three numbered final repetitions.",
        evidence={"passed_weight": passed_weight, "total_weight": total_weight, "repetitions": 3},
    )
    cells["resources.idle_private_working_set"] = make_cell(
        lower_is_better(idle_mib, 100, 500, 3),
        3,
        method="measured",
        criterion="3 points at <=100 MiB; linear to 0 at 500 MiB. Input is the median of three final-run tree-private-byte samples.",
        evidence={"median_mib": round(idle_mib, 6), "run_mib": [round(run["resources"]["idle"]["private_bytes"] / 1_048_576, 6) for run in runs]},
    )
    cells["resources.peak_private_working_set"] = make_cell(
        lower_is_better(peak_mib, 200, 1000, 4),
        4,
        method="measured",
        criterion="4 points at <=200 MiB; linear to 0 at 1000 MiB. Input is the median of three final-run sampled peaks.",
        evidence={"median_mib": round(peak_mib, 6), "run_mib": [round(run["resources"]["max_sampled_private_bytes"] / 1_048_576, 6) for run in runs]},
    )
    cells["resources.installed_or_self_contained_bytes"] = make_cell(
        artifact_points(package_mib),
        4,
        method="measured",
        criterion="4 points at <=100 MiB; log-linear to 0 at 1000 MiB. Uses the validated offline package, not the FDD test shell.",
        evidence={"package_bytes": package["package_bytes"], "package_mib": round(package_mib, 6)},
    )
    cells["resources.base_and_peak_vram"] = make_cell(
        round_b_vram_points(gpu_peak_mib),
        4,
        method="measured",
        criterion="Round-B frozen curve: 4 points at <=3072 MiB, 2 at 4096 MiB, 0 above 4096 MiB.",
        evidence={"median_peak_dedicated_mib": round(gpu_peak_mib, 6), "median_peak_shared_mib": round(gpu_shared_peak_mib, 6), "source": "Win32_PerfFormattedData_GPUPerformanceCounters_GPUProcessMemory"},
        limitations=["This slice does not load an inference model; its GPU figure measures only the integrated shell/core cut."],
    )
    cells["latency.cold_start_p95"] = make_cell(
        lower_is_better(cold_p95, 250, 2000, 4),
        4,
        method="measured",
        criterion="4 points at <=250 ms; linear to 0 at 2000 ms.",
        evidence={"p95_ms": round(cold_p95, 6), "valid_samples": lifecycle["cold_start"]["valid"]},
    )
    cells["latency.warm_mission_p95"] = make_cell(
        lower_is_better(warm_p95, 50, 500, 4),
        4,
        method="measured",
        criterion="4 points at <=50 ms; linear to 0 at 500 ms.",
        evidence={"p95_ms": round(warm_p95, 6), "valid_samples": lifecycle["warm_ui"]["valid"]},
    )
    cells["latency.warm_throughput"] = make_cell(
        higher_is_better(throughput, 10, 100, 2),
        2,
        method="measured",
        criterion="2 points at >=100 missions/s; linear from 0 at 10 missions/s.",
        evidence={"missions_per_second": round(throughput, 6)},
    )

    cells["ux.natural_spanish_and_honest_states"] = make_cell(
        2, 2, method="reviewed",
        criterion="Full credit requires all natural-language cases to pass through the visible composer and honest blocked/verified states to remain visible.",
        evidence={"final_runs": 3, "all_cases_passed": True, "visible_composer_cases_per_run": 15},
    )
    cells["ux.progress_without_raw_protocol"] = make_cell(
        2, 2, method="reviewed",
        criterion="Full credit requires progress announcements while raw protocol and runtime implementation names remain hidden.",
        evidence={"live_region_events_per_run": [run["accessibility"]["live_region_events"] for run in runs], "raw_protocol_hidden": True, "technical_runtime_hidden": True},
    )
    cells["ux.keyboard_and_focus"] = make_cell(
        2, 2, method="reviewed",
        criterion="Full credit requires named controls, a complete deterministic forward/reverse focus cycle, and keyboard submission.",
        evidence={
            "focusable_control_counts": [len(run["accessibility"]["focusable_controls"]) for run in runs],
            "forward_cycles_complete": [run["accessibility"]["forward_focus_cycle_complete"] for run in runs],
            "reverse_cycles_complete": [run["accessibility"]["reverse_focus_cycle_complete"] for run in runs],
            "keyboard_submit_case": "T01_CONVERSATION",
        },
    )
    cells["ux.accessible_names_live_regions_and_screen_reader"] = make_cell(
        1, 2, method="reviewed",
        criterion="One point for inspected UIA names and live-region events; the second requires a physical Narrator/NVDA run.",
        evidence={"minimum_named_nodes": min(run["accessibility"]["named_nodes"] for run in runs), "live_region_events_per_run": [run["accessibility"]["live_region_events"] for run in runs]},
        limitations=["No physical Narrator or NVDA session was executed."],
    )
    cells["ux.contrast_scaling_reduced_motion"] = make_cell(
        1, 2, method="reviewed",
        criterion="One point for measured high-contrast change and containment in an equivalent 900×520 DIP work area; the second requires physical 200% DPI and reduced-motion coverage.",
        evidence={"contrast_change_ratio": round(lifecycle["scale_and_contrast"]["sampled_pixel_change_ratio"], 6), "equivalent_work_area": lifecycle["scale_and_contrast"]["equivalent_work_area"], "controls_contained": True},
        limitations=["Physical 200% DPI hardware was unavailable.", "Reduced-motion behavior was not exercised."],
    )

    cells["security.offline_and_no_listeners"] = make_cell(
        2, 2, method="measured",
        criterion="Full credit requires a healthy fail-closed observer and empty TCP/UDP snapshots in all 18 UI samples, raw malformed-core recovery, and four unique installed launches.",
        evidence={"functional_network_samples": 54, "malformed_core_network_samples": 3, "package_unique_launches_checked": 4, "observer_fail_closed": True, "empty": all_network_empty},
        limitations=["Functional network evidence is discrete sampling, not continuous ETW tracing."],
    )
    cells["security.root_containment_and_input_sanitization"] = make_cell(
        2, 2, method="measured",
        criterion="Full credit requires traversal, absolute-path and NUL rejection in every run plus hostile junction/reparse refusal with sentinel preservation.",
        evidence={"cases": sorted(HOSTILE_CASES - {"T12_REFUSE_PROTECTED_DELETE"}), "reparse_defense": package["reparse_defense"]},
    )
    cells["security.risk_authorization_and_protected_targets"] = make_cell(
        2, 2, method="measured",
        criterion="Full credit requires protected destructive targets to remain blocked in every repetition.",
        evidence={"case": "T12_REFUSE_PROTECTED_DELETE", "passed_repetitions": 3},
    )
    cells["security.redaction_secret_storage_and_least_privilege"] = make_cell(
        1, 2, method="reviewed",
        criterion="One point for exact malformed-input redaction plus same-process recovery; the second requires exercised secret storage and least-privilege installation.",
        evidence={"malformed_case": "T16_MALFORMED_REQUEST", "route": "raw_core_transport_probe", "passed_repetitions": 3},
        limitations=["This cut has no secret-storage flow.", "The internal package mechanism is not a least-privilege Windows installer certification."],
    )
    cells["security.verified_effect_idempotency_and_tamper_evidence"] = make_cell(
        0, 2, method="reviewed",
        criterion="This combined cell receives full credit only when effects and replay are verified and the durable journal has cryptographic tamper evidence.",
        evidence={"effects_verified": True, "replay_idempotent": True, "package_payload_tamper_detected": True, "journal_mac_or_signature": False},
        limitations=["The durable JSONL journal has no MAC or signature.", "The package manifest detects change only while its colocated unsigned manifest remains trusted."],
    )

    cells["installation.reproducible_clean_build"] = make_cell(
        1 if reproducibility is not None else 0,
        2,
        method="measured" if reproducibility is not None else "not_demonstrated",
        criterion="One point requires two isolated same-host builds with identical complete trees and unchanged inputs; the second requires a fixed native linker/Windows SDK and cross-host or clean-VM reproduction.",
        evidence={"reproducibility_report_present": reproducibility is not None, "same_host_all_passed": reproducibility.get("passed") if reproducibility else False, "complete_official_wpf_tree_bound": reproducibility is not None},
        limitations=["MSVC link.exe and the Windows SDK were host-provided rather than pinned; no cross-host or clean-VM reproduction was executed."] if reproducibility is not None else ["No reproducibility report was present when the scorecard was generated."],
    )
    cells["installation.offline_install_and_first_launch"] = make_cell(
        1, 2, method="reviewed",
        criterion="One point for self-contained offline first launch with runtime lookup disabled; the second requires a genuinely clean Windows machine/VM installer run.",
        evidence={"runtime_lookup_disabled": True, "first_launch_passed": True, "bundle_cache_bytes": 0, "clean_machine_claimed": False},
        limitations=[package["scope"]],
    )
    cells["installation.single_instance_process_ownership_and_cleanup"] = make_cell(
        2, 2, method="measured",
        criterion="Full credit requires enforced single-instance behavior and zero warm/crash/graceful orphan processes.",
        evidence={"single_instance": lifecycle["single_instance"]["passed"], "job_cleanup": lifecycle["crash_and_restart"]["job_cleanup_passed"], "orphans": []},
    )
    cells["installation.crash_recovery_and_data_preservation"] = make_cell(
        2, 2, method="measured",
        criterion="Full credit requires a verified effect before crash, owned-process cleanup and verified data read after restart.",
        evidence=lifecycle["crash_and_restart"],
    )
    cells["installation.upgrade_rollback_and_uninstall"] = make_cell(
        2, 2, method="measured",
        criterion="Full credit requires changed update payload, tamper refusal, rollback, keep-data uninstall, reinstall and purge-data uninstall.",
        evidence={"package_gates": package_gates, "failed_gates": package["failed_gates"], "default_stream_tamper_rejected": True, "alternate_data_stream_rejected": True},
        limitations=["Evidence covers the internal offline package mechanism, not MSI/MSIX certification."],
    )

    cells["maintainability.automated_contract_and_regression_tests"] = make_cell(
        2, 2, method="reviewed",
        criterion="Full credit requires all 15 natural-language cases through the visible UI plus the raw malformed-transport case in three integrated repetitions and lifecycle/package gates.",
        evidence={"visible_ui_cases": 15 * len(runs), "raw_transport_probes": len(runs), "functional_passed": len(cases), "lifecycle_gates": lifecycle_gates, "package_gates": package_gates},
    )
    cells["maintainability.typed_versioned_boundaries"] = make_cell(
        1, 2, method="reviewed",
        criterion="One point for schema-versioned JSON and a typed UI bridge; the second requires a generated/centrally enforced cross-process contract.",
        evidence={"schema_versioned": True, "typed_ui_bridge": True, "malformed_transport_probe": "raw_core_transport_probe"},
        limitations=["The process boundary is hand-maintained JSON rather than a generated IDL contract."],
    )
    cells["maintainability.fault_injection_and_deterministic_replay"] = make_cell(
        2, 2, method="measured",
        criterion="Full credit requires idempotent invocation replay, truncated-journal recovery and crash/restart verification.",
        evidence={"T07": True, "T15": True, "crash_restart": lifecycle_gates["crash_restart_and_data"]},
    )
    cells["maintainability.diagnostics_and_observability"] = make_cell(
        0, 2, method="reviewed",
        criterion="Points require a product diagnostics/observability surface, not only tournament harness telemetry.",
        evidence={"harness_telemetry": True, "product_diagnostics_surface": False},
        limitations=["No user-facing diagnostic export or production event pipeline was demonstrated."],
    )
    complexity_points = 2 if config["toolchain_count"] == 1 else 1
    cells["maintainability.complexity_and_change_isolation_review"] = make_cell(
        complexity_points, 2, method="reviewed",
        criterion="Two points for one pinned language/toolchain across shell and core; one when a second pinned toolchain and FFI/runtime supply chain remain.",
        evidence={"toolchain_count": config["toolchain_count"], "shell": ".NET WPF", "core": config["core"]},
        limitations=[] if complexity_points == 2 else ["The hybrid adds Rust, Cargo crates and static CRT inventory to the same process boundary."],
    )

    license_points = 2 if supply.get("first_party_license_declared") is True else 1
    cells["license.compatible_and_recorded"] = make_cell(
        license_points, 2, method="reviewed",
        criterion="One point for third-party licenses recorded in CycloneDX; the second requires a declared first-party license and complete provenance.",
        evidence={"first_party_license_declared": supply["first_party_license_declared"], "sbom_components": supply["sbom_component_count"]},
        limitations=["First-party license is not declared.", "Embedded icon provenance is not recorded."],
    )
    cells["license.maintained_supported_components"] = make_cell(
        2, 2, method="reviewed",
        criterion="Full credit requires pinned, current toolchains and inventory of the runtime/framework components actually shipped.",
        evidence={"dotnet": "10.0.100", "rust": "1.97.0" if system_id.endswith("rust") else None, "runtime_framework_packs": supply["runtime_framework_packs"]},
    )
    cells["license.sbom_hashes_and_supply_chain"] = make_cell(
        1, 1, method="measured",
        criterion="Full credit requires a hash-bound CycloneDX SBOM, verified package file manifest and core import audit.",
        evidence={"sbom_sha256": supply["sbom_sha256"], "manifest_all_files_verified": supply["manifest_all_files_verified"], "core_imports": supply["core_imports"]},
        limitations=["Executables and package manifests are unsigned."],
    )

    cells["migration.historical_corpus_and_regression_reuse"] = make_cell(
        2, 2, method="reviewed",
        criterion="Full credit requires the same frozen corpus-derived 16-case protocol through the integrated GUI.",
        evidence={"protocol_id": "baxy-technology-tournament-v1", "cases": 16, "repetitions": 3},
    )
    cells["migration.proven_useful_component_reuse_without_legacy_inheritance"] = make_cell(
        2, 2, method="reviewed",
        criterion="Full credit requires reuse of promoted, executable Round-A behavior without importing the legacy application architecture.",
        evidence={"promoted_core": config["core"], "shared_native_shell": True, "legacy_runtime_inherited": False},
    )
    migration_effort_points = 1 if config["toolchain_count"] == 1 else 0
    cells["migration.estimated_migration_effort_reproduced_by_change"] = make_cell(
        migration_effort_points, 1, method="reviewed",
        criterion="The point requires the integrated change to stay within the native .NET toolchain; a second language/toolchain scores zero conservatively.",
        evidence={"toolchain_count": config["toolchain_count"], "integrated_cut_executed": True},
        limitations=[] if migration_effort_points else ["No quantified evidence showed that the second Rust toolchain reduces total migration effort."],
    )

    maximum = sum(cell["maximum"] for cell in cells.values())
    earned = sum(cell["points"] for cell in cells.values())
    require(maximum == 100, f"{system_id}: final cells do not total 100")
    require(all(cell["status"] != "NE" for cell in cells.values()), f"{system_id}: final score contains NE")
    categories = {
        "verified_missions": cells["verified_missions"]["points"],
        "resources": sum(cell["points"] for name, cell in cells.items() if name.startswith("resources.")),
        "latency": sum(cell["points"] for name, cell in cells.items() if name.startswith("latency.")),
        "ux_accessibility": sum(cell["points"] for name, cell in cells.items() if name.startswith("ux.")),
        "privacy_security": sum(cell["points"] for name, cell in cells.items() if name.startswith("security.")),
        "installation_lifecycle": sum(cell["points"] for name, cell in cells.items() if name.startswith("installation.")),
        "maintainability_testability": sum(cell["points"] for name, cell in cells.items() if name.startswith("maintainability.")),
        "license_maturity": sum(cell["points"] for name, cell in cells.items() if name.startswith("license.")),
        "migration_reuse": sum(cell["points"] for name, cell in cells.items() if name.startswith("migration.")),
    }
    categories = {name: round(value, 6) for name, value in categories.items()}
    return {
        "family": config["family"],
        "architecture": config["architecture"],
        "disqualified": False,
        "hard_gates": hard_gates,
        "raw": {
            "functional_weight_passed": passed_weight,
            "functional_weight_total": total_weight,
            "functional_pass_ratio": round(functional_ratio, 6),
            "cold_start_p95_ms": round(cold_p95, 6),
            "warm_p95_ms": round(warm_p95, 6),
            "throughput_per_second": round(throughput, 6),
            "idle_private_mib_median": round(idle_mib, 6),
            "peak_private_mib_median": round(peak_mib, 6),
            "peak_private_working_set_mib": round(peak_mib, 6),
            "gpu_peak_dedicated_mib_median": round(gpu_peak_mib, 6),
            "package_mib": round(package_mib, 6),
            "artifact_mib": round(package_mib, 6),
            "security_gate_failures": 0,
            "lifecycle_gate_failures": 0,
            "toolchain_count": config["toolchain_count"],
            "build_seconds": round_a_pareto["build_seconds"],
            "implementation_source_lines": round_a_pareto["implementation_source_lines"],
            "pareto_inherited_core_id": round_a_pareto["core_id"],
        },
        "cells": cells,
        "category_points": categories,
        "final_points": round(earned, 6),
        "maximum_points": 100,
        "final_normalized_100": round(earned, 6),
    }


def dominates(left: dict[str, Any], right: dict[str, Any], orientations: dict[str, str]) -> bool:
    comparisons: list[bool] = []
    strict: list[bool] = []
    for dimension, orientation in orientations.items():
        left_value = left[dimension]
        right_value = right[dimension]
        if orientation == "min":
            comparisons.append(left_value <= right_value)
            strict.append(left_value < right_value)
        else:
            comparisons.append(left_value >= right_value)
            strict.append(left_value > right_value)
    return all(comparisons) and any(strict)


def pareto(scores: dict[str, dict[str, Any]], orientations: dict[str, str]) -> list[str]:
    eligible = {system_id: score["raw"] for system_id, score in scores.items() if not score["disqualified"]}
    return sorted(
        system_id
        for system_id, raw in eligible.items()
        if not any(
            other_id != system_id and dominates(other_raw, raw, orientations)
            for other_id, other_raw in eligible.items()
        )
    )


def validate_rejected(path: Path, expected_id: str) -> dict[str, Any]:
    data = load_json(path)
    require(data.get("protocol_id") == "baxy-technology-tournament-v1", f"Rejected evidence protocol drift: {expected_id}")
    require(data.get("round") == "b_integrated_system" and data.get("shell_id") == expected_id, f"Rejected evidence identity drift: {expected_id}")
    snapshot = data.get("resources", {}).get("network_snapshot", {})
    tcp = snapshot.get("tcp", [])
    udp = snapshot.get("udp", [])
    require(len(tcp) + len(udp) > 0, f"Rejected WebView candidate lacks its network gate failure: {expected_id}")
    return {
        "system_id": expected_id,
        "disqualified": True,
        "gate_failures": ["no_network"],
        "reason": "The measured WebView process tree exposed TCP/UDP activity; its hash cannot win without a new full-protocol repetition.",
        "network": {"tcp_records": len(tcp), "udp_records": len(udp)},
        "idle_private_mib": round(data["resources"]["idle"]["private_bytes"] / 1_048_576, 6),
        "peak_private_mib": round(data["resources"]["max_sampled_private_bytes"] / 1_048_576, 6),
        "hashes": data["hashes"],
        "evidence": source_record(path),
    }


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
            temporary = Path(stream.name)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def build_scorecard() -> dict[str, Any]:
    protocol, _cases, case_ids, case_weights = validate_protocol()
    round_a_pareto = validate_round_a_pareto_evidence(protocol)
    reproducibility, reproducibility_source = validate_reproducibility()
    supply_document = load_json(SUPPLY_PATH)

    runs_by_system: dict[str, list[dict[str, Any]]] = {}
    lifecycle_by_system: dict[str, dict[str, Any]] = {}
    package_by_system: dict[str, dict[str, Any]] = {}
    lifecycle_gates_by_system: dict[str, dict[str, bool]] = {}
    package_gates_by_system: dict[str, dict[str, bool]] = {}
    source_finalists: dict[str, Any] = {}

    for system_id, config in SYSTEMS.items():
        slug = config["slug"]
        run_paths = [RAW / f"round_b_{slug}_run{index:02d}.json" for index in range(1, 4)]
        runs = [load_json(path) for path in run_paths]
        for path, run in zip(run_paths, runs):
            validate_functional_run(path, run, system_id, case_ids, case_weights)
        first_hashes = runs[0]["hashes"]
        require(all(run["hashes"] == first_hashes for run in runs), f"{system_id}: final repetitions used different hashes")
        size_keys = ("shell_bundle_bytes", "core_bytes", "bundle_bytes")
        require(all(tuple(run[key] for key in size_keys) == tuple(runs[0][key] for key in size_keys) for run in runs), f"{system_id}: final repetition bundle sizes differ")

        lifecycle_path = RAW / f"round_b_lifecycle_{slug}.json"
        lifecycle = load_json(lifecycle_path)
        lifecycle_gates = validate_lifecycle(lifecycle_path, lifecycle, system_id, first_hashes)
        package_path = RAW / f"round_b_package_{slug}.json"
        package = load_json(package_path)
        package_gates = validate_package(package_path, package, system_id, first_hashes["core_sha256"])

        runs_by_system[system_id] = runs
        lifecycle_by_system[system_id] = lifecycle
        package_by_system[system_id] = package
        lifecycle_gates_by_system[system_id] = lifecycle_gates
        package_gates_by_system[system_id] = package_gates
        source_finalists[system_id] = {
            "functional_runs": [source_record(path) for path in run_paths],
            "lifecycle": source_record(lifecycle_path),
            "package_lifecycle": source_record(package_path),
        }

    require(
        runs_by_system["dotnet-wpf"][0]["hashes"]["shell_bundle_sha256"]
        == runs_by_system["dotnet-wpf-rust"][0]["hashes"]["shell_bundle_sha256"]
        and runs_by_system["dotnet-wpf"][0]["hashes"]["shell_entrypoint_sha256"]
        == runs_by_system["dotnet-wpf-rust"][0]["hashes"]["shell_entrypoint_sha256"],
        "The two functional finalists did not use the same native WPF shell",
    )
    require(
        package_by_system["dotnet-wpf"]["hashes"]["shell_bundle_sha256"]
        == package_by_system["dotnet-wpf-rust"]["hashes"]["shell_bundle_sha256"]
        and package_by_system["dotnet-wpf"]["hashes"]["shell_entrypoint_sha256"]
        == package_by_system["dotnet-wpf-rust"]["hashes"]["shell_entrypoint_sha256"],
        "The two packages did not use the same self-contained WPF shell",
    )
    validate_reproducibility_bindings(reproducibility, package_by_system)
    supply_by_system, sbom_sources = validate_supply_chain(supply_document, package_by_system)
    scores = {
        system_id: score_system(
            system_id,
            runs_by_system[system_id],
            lifecycle_by_system[system_id],
            package_by_system[system_id],
            supply_by_system[system_id],
            lifecycle_gates_by_system[system_id],
            package_gates_by_system[system_id],
            reproducibility,
            round_a_pareto[system_id],
        )
        for system_id in SYSTEMS
    }

    orientations = {
        "functional_weight_passed": "max",
        "cold_start_p95_ms": "min",
        "warm_p95_ms": "min",
        "peak_private_working_set_mib": "min",
        "artifact_mib": "min",
        "build_seconds": "min",
        "security_gate_failures": "min",
        "lifecycle_gate_failures": "min",
        "implementation_source_lines": "min",
    }
    require(list(orientations) == protocol.get("pareto_dimensions"), "Final Pareto orientation set/order differs from the nine frozen dimensions")
    frontier = pareto(scores, orientations)
    eligible_frontier = [system_id for system_id in frontier if not scores[system_id]["disqualified"]]
    require(bool(eligible_frontier), "No eligible Round-B Pareto finalist remains")
    winner_id = max(eligible_frontier, key=lambda system_id: (scores[system_id]["final_points"], -SYSTEMS[system_id]["toolchain_count"], system_id))
    fallback_ids = sorted((system_id for system_id in eligible_frontier if system_id != winner_id), key=lambda system_id: scores[system_id]["final_points"], reverse=True)
    if winner_id == "dotnet-wpf":
        decision_reason = "The pure .NET system preserves the same verified behavior and native WPF product evidence while avoiding the hybrid's second language, crate and static-CRT supply chain; its small resource differences do not compensate for that measured complexity and migration cost."
    else:
        decision_reason = "The selected Pareto finalist has the highest complete frozen-protocol score; its measured system advantage exceeds the reviewed toolchain and migration cost recorded in the qualitative cells."

    rejected = [validate_rejected(path, system_id) for system_id, path in REJECTED_INPUTS.items()]
    result = {
        "schema_version": 1,
        "protocol_id": protocol["protocol_id"],
        "round": "b_integrated_system_final",
        "weights_unchanged": True,
        "weights": EXPECTED_WEIGHTS,
        "rounding": "Scores and derived metrics are retained to six decimal places.",
        "source_evidence": {
            "generator": source_record(Path(__file__)),
            "protocol": source_record(PROTOCOL_PATH),
            "cases": source_record(CASES_PATH),
            "finalists": source_finalists,
            "supply_chain": source_record(SUPPLY_PATH),
            "sboms": sbom_sources,
            "reproducibility": reproducibility_source,
            "round_a_pareto_inherited_core_metrics": {
                "scorecard": source_record(ROUND_A_SCORECARD_PATH),
                "source_results": source_record(ROUND_A_PACKAGING_PATH),
            },
            "excluded_stale_inputs": [
                "artifacts/technology_tournament/raw/round_b_dotnet_wpf.json",
                "artifacts/technology_tournament/raw/round_b_dotnet_wpf_rust.json",
            ],
        },
        "scores": scores,
        "pareto": {
            "frontier": frontier,
            "orientations": orientations,
            "note": "Both native-shell finalists remain when neither is no-worse in every measured frozen dimension and strictly better in at least one.",
            "inherited_core_dimensions": {
                "source": relative(ROUND_A_SCORECARD_PATH),
                "dimensions": ["build_seconds", "implementation_source_lines"],
                "mapping": round_a_pareto,
                "note": "These two frozen dimensions retain the hash-bound Round-A measurements of the exact promoted core implementations; the other seven dimensions use integrated Round-B evidence.",
            },
        },
        "rejected_candidates": rejected,
        "decision": {
            "winner_declared": True,
            "winner_id": winner_id,
            "winner_architecture": SYSTEMS[winner_id]["architecture"],
            "fallback_ids": fallback_ids,
            "selection_rule": "Highest final 100-point score among non-disqualified Pareto finalists; ties prefer fewer pinned implementation toolchains.",
            "reason": decision_reason,
        },
        "limitations": [
            "Network proof uses a fail-closed observer but remains discrete: 18 UI-run samples, one malformed-core sample per run and package launch snapshots, not continuous ETW.",
            "Accessibility lacks a physical Narrator/NVDA session and physical 200% DPI run.",
            "Package evidence is an internal offline lifecycle mechanism, not clean-VM MSI/MSIX certification.",
            "Build identity is deterministic across two isolated source replicas on this host; MSVC/link.exe and the Windows SDK were not pinned and no cross-host reproduction was run.",
            "The journal, package manifest and first-party executables are unsigned; journal records have no MAC.",
        ],
    }
    return result


def main() -> int:
    try:
        result = build_scorecard()
        atomic_write_json(OUTPUT, result)
    except EvidenceError as exc:
        print(f"Round-B scorecard evidence error: {exc}")
        return 2
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
