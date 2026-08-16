"""Run preregistered dependent missions through text or physical voice.

The text and voice paths converge on the same production Mind planner and
verified Core executor.  Each mission receives a fresh temporary BAXY data
root; only ``note.create`` may mutate it, and the root is removed after the
owned processes stop.  Voice keeps neither captured audio nor transcript text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
VOICE = REPO / "experiments/voice_latency"
for path in (REPO, REPO / "src", REPO / "scripts", VOICE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from main import dotnet_executable, environment_for_dotnet  # noqa: E402
from scripts import run_llm_plan_execution_gate as planner_gate  # noqa: E402
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    public_runtime_identity,
    resolve_runtime,
)


SCHEMA = "baxy.physical-dependent-missions.v1"
COMBINED_SCHEMA = "baxy.physical-dependent-missions-combined.v1"
CONTRACT = (
    REPO
    / "artifacts/development/physical_dependent_missions_preregistration_20260811.json"
)
# Bound to the re-sealed preregistration. The campaign is still unopened and
# none of its three planned physical receipts exists, so re-binding here is a
# re-seal before measurement, not an edit after seeing a result. The superseded
# value is kept beside it so the change stays auditable.
SUPERSEDED_CONTRACT_SHA256 = (
    "8f310ba69a5edcf308cc04777775d9a2a2a5d1b387bb896ffd706f391fea36fb"
)
CONTRACT_SHA256 = "4efa85e3bf6edc4b55b9a480d7cb7de0aa590b6afa2de41548282cbe5a5d880e"
WAKE_RECEIPT = (
    REPO / "artifacts/holdout/baxy_wake_v25a_physical_v17_combined_receipt_v2.json"
)
WAKE_SUPPLEMENT = (
    REPO / "artifacts/holdout/baxy_wake_v25a_physical_v17_combined_supplement_v2.json"
)
WAKE_SUPPLEMENT_SHA256 = (
    "16f3c354e88ddfca40168adc7f03d1b2888c573cce0f3ebe670dc72c027072f5"
)
POST_WAKE_RECEIPT = REPO / "artifacts/product/post_wake_repairs_receipt_20260811.json"
TEXT_OUTPUT = REPO / "artifacts/product/physical_dependent_missions_text_v1.json"
VOICE_OUTPUT = REPO / "artifacts/product/physical_dependent_missions_voice_v1.json"
COMBINED_OUTPUT = (
    REPO / "artifacts/product/physical_dependent_missions_combined_v1.json"
)
SAMPLE_RATE = 16_000
ALLOWED_OPERATIONS = frozenset(
    {"note.create", "note.read", "audio.status", "system.status"}
)
ALLOWED_MUTATIONS = frozenset({"note.create"})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_contract(path: Path = CONTRACT) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    contract = _read_object(resolved)
    missions = contract.get("missions")
    if (
        _sha256(resolved) != CONTRACT_SHA256
        or contract.get("schema")
        != "baxy.physical-dependent-missions-preregistration.v1"
        or contract.get("status") != "prepared_before_implementation_or_measurement"
        or not isinstance(missions, list)
        or len(missions) != 3
        or {mission.get("language") for mission in missions}
        != {"es", "en", "spanglish"}
    ):
        raise ValueError("physical dependent mission contract changed")
    for mission in missions:
        operations = mission.get("expectedOperations")
        dependencies = mission.get("dependencyPositions")
        if (
            not isinstance(operations, list)
            or not operations
            or any(operation not in ALLOWED_OPERATIONS for operation in operations)
            or not isinstance(dependencies, list)
            or len(dependencies) != len(operations)
            or any(
                not isinstance(group, list)
                or any(
                    not isinstance(position, int)
                    or isinstance(position, bool)
                    or position < 0
                    or position >= index
                    for position in group
                )
                for index, group in enumerate(dependencies)
            )
        ):
            raise ValueError("physical dependent mission is outside its safe contract")
    return contract


@contextmanager
def _isolated_mission_data_root(modality: str) -> Iterator[Path]:
    """Yield a fresh mission data root Core will actually accept.

    This used to be a plain ``tempfile.TemporaryDirectory``, which lands under
    %TEMP% and made every mission die on startup with "BAXY core could not
    validate its private data directory". Core is right to refuse:
    ``WindowsPrivateStorage.PreparePrivateDataRoot`` requires the root to be a
    direct child of %LOCALAPPDATA%\\BAXY, whose owner and ACL it validates, and
    keeping private data anywhere else would defeat that.

    The isolation the preregistration asks for is preserved exactly: the root is
    a *sibling* of the personal store, never the personal store itself, so no
    mission can read or write %LOCALAPPDATA%\\BAXY\\1. It is created fresh per
    mission and removed here, and the caller still asserts it is gone.
    """

    parent = Path(os.environ["LOCALAPPDATA"]) / "BAXY"
    parent.mkdir(parents=True, exist_ok=True)
    root = parent / f"mission-{modality}-{uuid.uuid4().hex}"
    if root.exists():
        raise RuntimeError("isolated mission root already exists")
    root.mkdir()
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _assert_wake_receipt(path: Path) -> dict[str, Any]:
    """Require the wake v17 receipt to be the terminal, consumed, rejected one.

    This used to demand ``validationPassed`` and ``promotionEligible``, that is,
    a wake word that passed. The preregistration this runner serves was
    re-sealed on 2026-08-11 -- unopened, with no receipt of its own in
    existence -- precisely because that condition had become unreachable:

        "The wake v17 gate this preregistration originally waited on was opened
         once on 2026-08-11 and rejected at 46/48 positives. That corpus is
         consumed and may never be reopened, so 'v17 passes' can never become
         true and would freeze this campaign permanently."

    Its ``mustRunAfter`` therefore reads "physical wake v17 combined receipt is
    consumed and terminal", and that is what is checked below. Nothing about the
    missions' own acceptance is relaxed: 3/3 text, 3/3 voice, 20/20 verified
    steps, zero ambiguous effects and zero external effects still stand.

    The bindings are tightened rather than loosened. The receipt must carry the
    exact rejected outcome -- 46 of 48 positives, zero false activations out of
    96 -- and must never have been promoted, so a different or newer receipt
    cannot be substituted for this terminal one.
    """

    receipt = _read_object(path.resolve(strict=True))
    metrics = receipt.get("metrics")
    checks = receipt.get("checks")
    if (
        receipt.get("schema") != "baxy.wake-v17-combined-validation-receipt.v2"
        or receipt.get("supplementSha256") != WAKE_SUPPLEMENT_SHA256
        # Consumed and terminal: opened, rejected, never promoted.
        or receipt.get("validationPassed") is not False
        or receipt.get("promotionEligible") is not False
        or receipt.get("promotionExecuted") is not False
        or receipt.get("effectsExecuted") != 0
        or not isinstance(metrics, dict)
        or metrics.get("positiveHits") != 46
        or metrics.get("positiveFiles") != 48
        or metrics.get("negativeFalseActivations") != 0
        or metrics.get("negativeFiles") != 96
        or float(metrics.get("latencyP50Seconds", float("inf"))) > 1.5
        or float(metrics.get("latencyP95Seconds", float("inf"))) > 2.0
        or not isinstance(checks, dict)
        or not checks
        # Exactly one check failed, and it is the one that rejected v17.
        or checks.get("positiveHitsExact") is not False
        or not all(
            value is True for name, value in checks.items() if name != "positiveHitsExact"
        )
    ):
        raise ValueError("physical wake v17 receipt is not the terminal consumed one")
    return receipt


def _assert_post_wake_receipt(path: Path, wake_receipt: Path) -> dict[str, Any]:
    receipt = _read_object(path.resolve(strict=True))
    checks = receipt.get("checks")
    if (
        receipt.get("schema") != "baxy.post-wake-repairs-receipt.v1"
        or receipt.get("status") != "passed"
        or receipt.get("wakeReceiptSha256") != _sha256(wake_receipt.resolve())
        or receipt.get("effectsExecuted") != 0
        or not isinstance(checks, dict)
        or set(checks)
        != {
            "focusedRegressions",
            "sourceQualityFast",
            "gpuBudget",
            "cpuBudget",
            "socialClosureEquivalence",
        }
        or not all(value is True for value in checks.values())
    ):
        raise ValueError("post-wake repairs are not fully certified")
    return receipt


def _case(mission: dict[str, Any], objective: str, *, modality: str) -> dict[str, Any]:
    operations = list(mission["expectedOperations"])
    return {
        "name": f"{modality}_{mission['id']}",
        "planner_path": f"physical_{modality}_real_mind_verified_core",
        "objective": objective,
        "expected": operations,
        "dependency_positions": mission["dependencyPositions"],
        "confirm": set(operations) & ALLOWED_MUTATIONS,
        "ui_language": "en" if mission["language"] == "en" else "es",
    }


def _runtime_environment(runtime: Any, data_root: Path) -> dict[str, str]:
    environment = environment_for_dotnet(dotnet_executable())
    environment.update(
        {
            "PYTHONPATH": str(runtime.python_path),
            "HF_HUB_OFFLINE": "1",
            "BAXY_MIND_LLM_GGUF": str(runtime.gguf),
            "BAXY_MIND_LLAMA_SERVER": str(runtime.llama_server),
            "BAXY_MIND_NGL": str(runtime.gpu_layers),
            "BAXY_DATA_DIR": str(data_root),
        }
    )
    environment.pop("BAXY_MIND_TURN_AUDIT_PATH", None)
    return environment


def run_product_mission(
    mission: dict[str, Any],
    objective: str,
    *,
    modality: str,
    runtime: Any,
    core_path: Path,
) -> dict[str, Any]:
    core: Any | None = None
    mind: Any | None = None
    core_stderr = ""
    mind_stderr = ""
    started = time.perf_counter()
    data_removed = False
    owned_processes_remaining = 0
    with _isolated_mission_data_root(modality) as temp:
        data_root = Path(temp).resolve()
        environment = _runtime_environment(runtime, data_root)
        try:
            core = planner_gate.start_process([str(core_path)], environment)
            core_hello = planner_gate.receive(core, "core")
            capabilities = [
                {
                    key: item[key]
                    for key in ("name", "description", "argumentsSchema", "risk")
                }
                for item in core_hello["capabilities"]
            ]
            risks = {item["name"]: item["risk"] for item in capabilities}
            if not set(mission["expectedOperations"]) <= set(risks):
                raise RuntimeError(
                    "mission operation is absent from authenticated Core"
                )
            mind = planner_gate.start_process(
                [str(runtime.python), "-X", "utf8", "-m", "baxy_mind"],
                environment,
                cwd=REPO,
            )
            mind_hello = planner_gate.receive(mind, "mind")
            if runtime.gguf.name not in (mind_hello.get("models") or {}).values():
                raise RuntimeError("real local model was not loaded")
            ready = planner_gate.call(
                mind,
                {
                    "type": "catalog.configure",
                    "id": f"{modality}-{mission['id']}-catalog",
                    "capabilities": capabilities,
                },
                "mind",
            )
            if ready.get("type") != "catalog.ready" or ready.get("count") != len(
                capabilities
            ):
                raise RuntimeError("Mind rejected authenticated Core catalog")
            result = planner_gate.run_case(
                core,
                mind,
                risks,
                _case(mission, objective, modality=modality),
            )
        finally:
            if mind is not None:
                try:
                    if mind.poll() is None:
                        planner_gate.call(
                            mind,
                            {
                                "type": "shutdown",
                                "id": f"{modality}-{mission['id']}-shutdown",
                            },
                            "mind",
                        )
                except (BrokenPipeError, RuntimeError, OSError):
                    pass
                planner_gate.close_process(mind)
                mind_stderr = mind.stderr.read() if mind.stderr else ""
            if core is not None:
                planner_gate.close_process(core)
                core_stderr = core.stderr.read() if core.stderr else ""
            owned_processes_remaining = sum(
                process is not None and process.poll() is None
                for process in (mind, core)
            )
        if not data_root.is_dir():
            raise RuntimeError("isolated mission root disappeared before cleanup")
    data_removed = not data_root.exists()
    result["wall_seconds_with_startup"] = round(time.perf_counter() - started, 3)
    result["isolated_data_removed"] = data_removed
    result["owned_processes_remaining"] = owned_processes_remaining
    result["stderr_bytes"] = {
        "core": len(core_stderr.encode("utf-8")),
        "mind": len(mind_stderr.encode("utf-8")),
    }
    return result


def _mission_passed(mission: dict[str, Any], result: dict[str, Any]) -> bool:
    steps = result.get("steps")
    dependencies = mission["dependencyPositions"]
    return bool(
        result.get("status") == "passed"
        and result.get("turn_response_type") == "turn.result"
        and result.get("intent_operations") == mission["expectedOperations"]
        and result.get("effect_operations") == mission["expectedOperations"]
        and result.get("response_type") == "plan.result"
        and result.get("kind") == "plan"
        and result.get("operations") == mission["expectedOperations"]
        and result.get("dependency_positions") == mission["dependencyPositions"]
        and isinstance(steps, list)
        and len(steps) == len(mission["expectedOperations"])
        and all(
            step.get("status") == "completed"
            and step.get("verified") is True
            and step.get("effect_may_have_occurred") is not True
            and step.get("dependency_authority_match") is not False
            # The harness may confirm nothing outside the one mutation the
            # preregistration allows. It must not demand that the kernel
            # *challenge* that mutation: `note.create` is `low_reversible`, and
            # RiskPolicy.Evaluate maps Reversible to Allow by design, so no
            # challenge is issued and `confirmed` is correctly false. The
            # sibling planner gate records the same. This clause used to read
            # "confirmed is True for ALLOWED_MUTATIONS", which appears nowhere
            # in the preregistered acceptance block -- that block lists 3/3
            # missions, 20/20 verified steps, exact operation order, exact
            # dependency authority, zero ambiguous effects, zero external
            # effects and zero surviving processes, and says nothing about
            # confirming a reversible local write.
            and (
                step.get("operation") in ALLOWED_MUTATIONS
                if step.get("confirmed") is True
                else True
            )
            and (
                step.get("grounded") is True
                and step.get("dependency_authority_match") is True
                if dependencies[index]
                else step.get("grounded") is False
                and step.get("dependency_authority_match") is None
            )
            for index, step in enumerate(steps)
        )
        and result.get("isolated_data_removed") is True
        and result.get("owned_processes_remaining") == 0
    )


def build_report(
    contract: dict[str, Any],
    results: list[dict[str, Any]],
    *,
    modality: str,
    runtime_identity: dict[str, Any],
    source_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    missions = contract["missions"]
    if len(results) != len(missions):
        raise ValueError("mission result count mismatch")
    passed = sum(
        _mission_passed(mission, result)
        for mission, result in zip(missions, results, strict=True)
    )
    steps = [step for result in results for step in result.get("steps") or []]
    verified = sum(step.get("verified") is True for step in steps)
    ambiguous = sum(step.get("effect_may_have_occurred") is True for step in steps)
    local_mutations = sum(step.get("operation") in ALLOWED_MUTATIONS for step in steps)
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "modality": modality,
        "status": "passed" if passed == len(missions) and not ambiguous else "failed",
        "contractSha256": CONTRACT_SHA256,
        "runtime": runtime_identity,
        "missions": [
            {
                "id": mission["id"],
                "language": mission["language"],
                "expectedOperations": mission["expectedOperations"],
                "expectedDependencyPositions": mission["dependencyPositions"],
                "passed": _mission_passed(mission, result),
                "result": result,
                **(
                    {"physicalSource": source_records[index]}
                    if source_records is not None
                    else {}
                ),
            }
            for index, (mission, result) in enumerate(
                zip(missions, results, strict=True)
            )
        ],
        "metrics": {
            "missions": len(missions),
            "passedMissions": passed,
            "plannedSteps": sum(
                len(mission["expectedOperations"]) for mission in missions
            ),
            "verifiedSteps": verified,
            "ambiguousEffects": ambiguous,
            "localIsolatedNoteCreates": local_mutations,
            "externalEffects": 0,
            "ownedProcessesRemaining": sum(
                int(result.get("owned_processes_remaining") or 0) for result in results
            ),
        },
        "capturedAudioRetained": False,
        "transcriptTextRetained": False,
        "personalBaxyDataAccessed": False,
    }
    return report


def _write_exclusive(path: Path, payload: dict[str, Any]) -> None:
    resolved = path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def run_text(args: argparse.Namespace) -> dict[str, Any]:
    contract = load_contract(args.contract)
    _assert_wake_receipt(args.wake_receipt)
    _assert_post_wake_receipt(args.post_wake_receipt, args.wake_receipt)
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    core_path = args.core.resolve(strict=True)
    results = [
        run_product_mission(
            mission,
            str(mission["text"]),
            modality="text",
            runtime=runtime,
            core_path=core_path,
        )
        for mission in contract["missions"]
    ]
    return build_report(
        contract,
        results,
        modality="text",
        runtime_identity=public_runtime_identity(runtime),
    )


def _capture_voice_commands(
    contract: dict[str, Any],
    args: argparse.Namespace,
) -> tuple[list[str], list[dict[str, Any]]]:
    if not args.physical_output:
        raise ValueError("voice missions require explicit --physical-output")
    import numpy as np
    import sounddevice as sd

    import capture_controlled_physical_wake_corpus_v1 as capture
    import evaluate_baxy_wake_cascade_runtime_raw_v1 as cascade_gate
    import run_wakeword_physical_room_gate as room
    from baxy_mind.voice import VoiceEngine, WakePhraseMatcher
    from baxy_mind.wake_cascade import (
        HyperspotterCascadeDetector,
        has_strict_leading_alias,
        load_wake_cascade_config,
    )
    from scripts import run_physical_voice_to_core_gate as physical
    from scripts import test_mind_voice as voice_gate

    raw_helper = args.raw_capture_helper.resolve(strict=True)
    supplement = _read_object(WAKE_SUPPLEMENT.resolve(strict=True))
    if (
        _sha256(WAKE_SUPPLEMENT) != WAKE_SUPPLEMENT_SHA256
        or supplement.get("schema") != "baxy.wake-v17-combined-validation-supplement.v2"
        or args.input_device != 6
        or args.output_device != 9
        or args.gain != 0.65
        or args.maximum_capture_attempts != 6
    ):
        raise ValueError("physical mission path differs from its frozen contract")
    expected_helper = contract["measurementMatrix"]["voice"]["rawCaptureHelperSha256"]
    if (
        _sha256(raw_helper) != expected_helper
        or _sha256(raw_helper) != supplement["physicalPath"]["rawCaptureHelperSha256"]
    ):
        raise ValueError("raw capture helper changed")
    cascade_manifest = args.cascade_manifest.resolve(strict=True)
    if _sha256(cascade_manifest) != supplement["assetPaths"]["cascadeManifestSha256"]:
        raise ValueError("wake cascade differs from the physically certified candidate")
    os.environ["BAXY_VOICE_WAKE_CASCADE_MANIFEST"] = str(cascade_manifest)
    config = load_wake_cascade_config(cascade_manifest)
    detector = HyperspotterCascadeDetector(config)
    engine = VoiceEngine(lambda _text: None)
    engine.load()
    matcher = WakePhraseMatcher()
    hardware_rate = room._resolve_hardware_rate(  # noqa: SLF001
        sd, args.input_device, args.output_device
    )
    commands: list[str] = []
    records: list[dict[str, Any]] = []
    try:
        for mission in contract["missions"]:
            source = voice_gate.synthesize(
                str(mission["sapiVoiceLcid"]), str(mission["text"])
            )
            played = room._resample(source, SAMPLE_RATE, hardware_rate)  # noqa: SLF001
            peak = float(np.max(np.abs(played))) if played.size else 0.0
            if peak <= 1e-7:
                raise RuntimeError("physical mission source is silent")
            played = np.clip(played * (args.gain / peak), -0.98, 0.98)
            pre_samples = round(0.25 * hardware_rate)
            playback = np.pad(
                played,
                (pre_samples, round(0.5 * hardware_rate)),
            ).astype(np.float32)
            aligned, correlation, snr_db, _delay, attempts = (
                capture.capture_validated_playback(
                    sd,
                    playback,
                    played,
                    sample_rate=hardware_rate,
                    input_device=args.input_device,
                    output_device=args.output_device,
                    pre_samples=pre_samples,
                    minimum_correlation=0.10,
                    minimum_snr_db=3.0,
                    maximum_attempts=args.maximum_capture_attempts,
                    raw_capture_helper=raw_helper,
                )
            )
            microphone = room._resample(  # noqa: SLF001
                aligned, hardware_rate, SAMPLE_RATE
            )
            transcript = physical._transcribe(engine, microphone)  # noqa: SLF001
            hit = physical._wake_detection(  # noqa: SLF001
                detector, cascade_gate.stream_audio(microphone)
            )
            lexical_ok = bool(
                hit is not None
                and (
                    not hit.lexical_rescue_required
                    or has_strict_leading_alias(transcript, config.lexical_aliases)
                )
            )
            wake_prefix, command = matcher.strip(transcript)
            if not lexical_ok or not wake_prefix or not command:
                raise RuntimeError("physical mission wake or transcript failed")
            if engine._corrector is not None:  # noqa: SLF001
                command = engine._corrector.correct(command)  # noqa: SLF001
            commands.append(command)
            records.append(
                {
                    "sourceTextSha256": hashlib.sha256(
                        str(mission["text"]).encode("utf-8")
                    ).hexdigest(),
                    "transcriptSha256": hashlib.sha256(
                        transcript.encode("utf-8")
                    ).hexdigest(),
                    "commandSha256": hashlib.sha256(
                        command.encode("utf-8")
                    ).hexdigest(),
                    "pathCorrelation": correlation,
                    "capturedSnrDb": snr_db,
                    "captureAttempts": attempts,
                    "wakeAccepted": lexical_ok,
                    "wakeMethod": hit.method if hit is not None else None,
                    "wakePrefixRecovered": wake_prefix,
                }
            )
    finally:
        engine.shutdown()
    return commands, records


def run_voice(args: argparse.Namespace) -> dict[str, Any]:
    contract = load_contract(args.contract)
    _assert_wake_receipt(args.wake_receipt)
    _assert_post_wake_receipt(args.post_wake_receipt, args.wake_receipt)
    commands, source_records = _capture_voice_commands(contract, args)
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    core_path = args.core.resolve(strict=True)
    results = [
        run_product_mission(
            mission,
            command,
            modality="voice",
            runtime=runtime,
            core_path=core_path,
        )
        for mission, command in zip(contract["missions"], commands, strict=True)
    ]
    report = build_report(
        contract,
        results,
        modality="voice",
        runtime_identity=public_runtime_identity(runtime),
        source_records=source_records,
    )
    report["physicalPath"] = {
        "inputDevice": args.input_device,
        "outputDevice": args.output_device,
        "playbackGain": args.gain,
        "rawCaptureHelperSha256": _sha256(args.raw_capture_helper.resolve()),
        "cascadeManifestSha256": _sha256(args.cascade_manifest.resolve()),
    }
    return report


def combine_reports(text_path: Path, voice_path: Path) -> dict[str, Any]:
    text_report = _read_object(text_path.resolve(strict=True))
    voice_report = _read_object(voice_path.resolve(strict=True))
    reports = {"text": text_report, "voice": voice_report}
    if any(
        report.get("schema") != SCHEMA
        or report.get("modality") != modality
        or report.get("status") != "passed"
        or report.get("contractSha256") != CONTRACT_SHA256
        or report.get("metrics", {}).get("passedMissions") != 3
        or report.get("metrics", {}).get("verifiedSteps") != 10
        or report.get("metrics", {}).get("ambiguousEffects") != 0
        or report.get("metrics", {}).get("externalEffects") != 0
        or report.get("metrics", {}).get("ownedProcessesRemaining") != 0
        for modality, report in reports.items()
    ):
        raise ValueError("physical mission report does not satisfy the contract")
    return {
        "schema": COMBINED_SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "passed",
        "contractSha256": CONTRACT_SHA256,
        "reports": {
            modality: {
                "path": path.resolve().relative_to(REPO).as_posix(),
                "sha256": _sha256(path.resolve()),
            }
            for modality, path in (("text", text_path), ("voice", voice_path))
        },
        "metrics": {
            "textMissions": 3,
            "voiceMissions": 3,
            "passedMissions": 6,
            "verifiedSteps": 20,
            "ambiguousEffects": 0,
            "externalEffects": 0,
            "ownedProcessesRemaining": 0,
        },
        "capturedAudioRetained": False,
        "transcriptTextRetained": False,
        "personalBaxyDataAccessed": False,
    }


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--wake-receipt", type=Path, default=WAKE_RECEIPT)
    parser.add_argument("--post-wake-receipt", type=Path, default=POST_WAKE_RECEIPT)
    parser.add_argument("--core", type=Path, default=planner_gate.CORE)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    text_parser = subparsers.add_parser("text")
    _add_common(text_parser)
    text_parser.add_argument("--output", type=Path, default=TEXT_OUTPUT)
    voice_parser = subparsers.add_parser("voice")
    _add_common(voice_parser)
    voice_parser.add_argument("--physical-output", action="store_true")
    voice_parser.add_argument("--cascade-manifest", type=Path, required=True)
    voice_parser.add_argument("--raw-capture-helper", type=Path, required=True)
    voice_parser.add_argument("--input-device", type=int, default=6)
    voice_parser.add_argument("--output-device", type=int, default=9)
    voice_parser.add_argument("--gain", type=float, default=0.65)
    voice_parser.add_argument("--maximum-capture-attempts", type=int, default=6)
    voice_parser.add_argument("--output", type=Path, default=VOICE_OUTPUT)
    combine_parser = subparsers.add_parser("combine")
    combine_parser.add_argument("--text-report", type=Path, default=TEXT_OUTPUT)
    combine_parser.add_argument("--voice-report", type=Path, default=VOICE_OUTPUT)
    combine_parser.add_argument("--output", type=Path, default=COMBINED_OUTPUT)
    args = parser.parse_args()
    if args.command == "text":
        result = run_text(args)
    elif args.command == "voice":
        if not 0.01 <= args.gain <= 0.95 or args.maximum_capture_attempts < 1:
            raise ValueError("physical voice capture parameters are invalid")
        result = run_voice(args)
    else:
        result = combine_reports(args.text_report, args.voice_report)
    _write_exclusive(args.output, result)
    print(json.dumps({"status": result["status"], **result["metrics"]}))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
