"""Exercise the real BAXY LLM planner through verified core execution.

This is the missing integration boundary between the planner-only corpus gate
and the direct-adapter physical gates.  Every case is planned by the production
sidecar, grounded from the same bounded observation projection as the app, and
executed through the production JSONL core.  The matrix is intentionally
limited to read-only or reversible effects explicitly named by the test case.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
import winreg
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.baxy_runtime_config import (  # noqa: E402
    add_runtime_arguments,
    public_runtime_identity,
    resolve_runtime_from_args,
)
from scripts.build_layout import load_build_layout  # noqa: E402
from main import (  # noqa: E402
    dotnet_executable,
    environment_for_dotnet,
)

BUILD_LAYOUT = load_build_layout(REPO)
CORE = BUILD_LAYOUT.core_executable(REPO)
OUTPUT = REPO / "artifacts/planner_recovery/llm_plan_execution_gate.json"

SAFE_FIELDS = {
    "available", "backupId", "captureId", "connected", "count", "devices",
    "deviceId", "enabled", "entries", "exists", "fileId", "files", "hash",
    "installed", "items", "isTrashed", "jobId", "noteId", "notes",
    "processId", "recipientId", "reminderId", "reminders", "resourceId", "resourceUri",
    "results", "revision", "routineId", "routines", "sessionId", "sha256",
    "state", "status", "taskId", "tasks", "totalCount", "version",
    "windowId", "windows",
}
OPERATION_SAFE_FIELDS = {
    "bluetooth.device.list": {"canPair", "name", "paired"},
    "browser.page.read": {"truncated", "url"},
    "browser.tabs.list": {"tabs", "targetId", "truncated", "url"},
    "filesystem.list": {"relativePath"},
    "filesystem.search": {"relativePath"},
    "game.catalog.list": {"games", "name"},
    "game.purchase.prepare": {"expectedPriceCents"},
    "peripheral.list": {"kind", "name"},
    "reminder.resolve.exact": {"expectedVersion", "reviewLabel"},
    "web.search": {"url"},
    "wifi.profile.list": {"label", "profiles"},
}
MAX_ARRAY_ITEMS = 32
MAX_STRING_LENGTH = 2_048
PHYSICAL_VOICE_READ_ONLY_OPERATIONS = frozenset(("audio.status", "system.status"))


def resolve_functional_python(runtime: Any) -> tuple[Path, str]:
    """Resolve CPython 3.12 while preserving the registered dependency set."""

    import_paths = [runtime.python_path]
    registered_site_packages = (
        runtime.python.parent.parent / "Lib" / "site-packages"
    )
    if registered_site_packages.is_dir():
        import_paths.append(registered_site_packages)
    python_path = os.pathsep.join(str(path) for path in import_paths)
    candidates = [runtime.python]
    configuration = runtime.python.parent.parent / "pyvenv.cfg"
    if configuration.is_file():
        for line in configuration.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip().casefold() == "home":
                candidates.append(Path(value.strip()) / "python.exe")
                break
    local_data = Path(os.environ.get("LOCALAPPDATA", ""))
    program_files = Path(os.environ.get("ProgramFiles", ""))
    user_profile = Path(os.environ.get("USERPROFILE", ""))
    if str(local_data):
        candidates.append(local_data / "Programs" / "Python" / "Python312" / "python.exe")
    if str(program_files):
        candidates.append(program_files / "Python312" / "python.exe")
    if str(user_profile):
        candidates.append(
            user_profile
            / ".cache"
            / "codex-runtimes"
            / "codex-primary-runtime"
            / "dependencies"
            / "python"
            / "python.exe"
        )

    probe = (
        "import sys,baxy_mind,baxy_mind.voice,numpy,onnxruntime,sherpa_onnx;"
        "raise SystemExit(0 if sys.version_info[:2] == (3,12) else 4)"
    )
    checked: set[Path] = set()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = python_path
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
        except (FileNotFoundError, OSError):
            continue
        if resolved in checked or not resolved.is_file():
            continue
        checked.add(resolved)
        try:
            completed = subprocess.run(
                [str(resolved), "-X", "utf8", "-c", probe],
                cwd=REPO,
                env=environment,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if completed.returncode == 0:
            return resolved, python_path
    raise RuntimeError(
        "no CPython 3.12 candidate can load the registered BAXY dependencies"
    )


def build_physical_voice_case(text: str, expected_operation: str) -> dict[str, Any]:
    """Build the only external case accepted from a physical voice transcript."""

    objective = str(text).strip()
    operation = str(expected_operation).strip()
    if (
        not objective
        or len(objective) > 512
        or "\x00" in objective
        or operation not in PHYSICAL_VOICE_READ_ONLY_OPERATIONS
    ):
        raise ValueError("physical voice gate case is not a bounded read-only request")
    return {
        "name": "physical_voice_transcript_to_core",
        "planner_path": "physical_room_voice_real_sidecar_verified_core",
        "objective": objective,
        "expected": [operation],
        "confirm": set(),
    }


def main() -> None:
    global OUTPUT
    parser = argparse.ArgumentParser(
        description="Gate físico opt-in del planner LLM y core verificado."
    )
    parser.add_argument("--core", type=Path, default=CORE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    add_runtime_arguments(parser)
    args = parser.parse_args()
    runtime = resolve_runtime_from_args(args)
    python, mind_python_path = resolve_functional_python(runtime)
    runtime_identity = public_runtime_identity(runtime)
    runtime_identity["python"] = {
        "name": python.name,
        "bytes": python.stat().st_size,
        "registeredCandidateWasFunctional": python == runtime.python.resolve(),
    }
    core_path = args.core.resolve(strict=True)
    if not core_path.is_file():
        raise FileNotFoundError("baxy-core no es un archivo")
    OUTPUT = args.output.resolve()

    run_id = uuid.uuid4().hex[:10]
    data_root = Path(os.environ["LOCALAPPDATA"]) / "BAXY" / ("llm-e2e-" + run_id)
    documents_root = known_documents_root() / "BAXY"
    document_prefix = f"BAXY LLM E2E {run_id}"
    preexisting_documents = set(documents_root.glob(document_prefix + "-*")) \
        if documents_root.is_dir() else set()
    environment = environment_for_dotnet(dotnet_executable())
    environment.update(
        {
            "PYTHONPATH": mind_python_path,
            "HF_HUB_OFFLINE": "1",
            "BAXY_MIND_LLM_GGUF": str(runtime.gguf),
            "BAXY_MIND_LLAMA_SERVER": str(runtime.llama_server),
            "BAXY_MIND_NGL": str(runtime.gpu_layers),
            "BAXY_DATA_DIR": str(data_root),
        }
    )
    cases = build_cases(run_id, document_prefix)
    physical_voice_text = os.environ.get("BAXY_LLM_GATE_PHYSICAL_VOICE_TEXT", "")
    physical_voice_expected = os.environ.get(
        "BAXY_LLM_GATE_PHYSICAL_VOICE_EXPECTED", ""
    )
    if physical_voice_text or physical_voice_expected:
        cases = [
            build_physical_voice_case(physical_voice_text, physical_voice_expected)
        ]
    requested_cases = {
        name.strip()
        for name in os.environ.get("BAXY_LLM_GATE_CASES", "").split(",")
        if name.strip()
    }
    if requested_cases:
        cases = [case for case in cases if case["name"] in requested_cases]
        missing = requested_cases - {case["name"] for case in cases}
        if missing:
            raise ValueError(f"unknown gate cases: {sorted(missing)}")
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    core: subprocess.Popen[str] | None = None
    mind: subprocess.Popen[str] | None = None
    core_stderr = ""
    mind_stderr = ""
    catalog_count = 0
    try:
        core = start_process([str(core_path)], environment)
        core_hello = receive(core, "core")
        capabilities = [
            {key: item[key] for key in ("name", "description", "argumentsSchema", "risk")}
            for item in core_hello["capabilities"]
        ]
        risks = {item["name"]: item["risk"] for item in capabilities}
        catalog_count = len(capabilities)

        mind = start_process(
            [str(python), "-X", "utf8", "-m", "baxy_mind"],
            environment,
            cwd=REPO,
        )
        mind_hello = receive(mind, "mind")
        if runtime.gguf.name not in (mind_hello.get("models") or {}).values():
            raise RuntimeError(f"real LLM was not loaded: {mind_hello}")
        catalog_configure: dict[str, Any] = {
            "type": "catalog.configure",
            "id": "catalog",
            "capabilities": capabilities,
        }
        application_catalog = core_hello.get("applicationCatalog")
        if isinstance(application_catalog, dict):
            catalog_configure["applicationCatalog"] = application_catalog
        game_catalog = core_hello.get("gameCatalog")
        if isinstance(game_catalog, dict):
            catalog_configure["gameCatalog"] = game_catalog
        ready = call(
            mind,
            catalog_configure,
            "mind",
        )
        if ready.get("type") != "catalog.ready" or ready.get("count") != catalog_count:
            raise RuntimeError(f"planner catalog rejected: {ready}")

        for index, case in enumerate(cases, 1):
            result = run_case(core, mind, risks, case)
            results.append(result)
            write_report(
                results, catalog_count, started, complete=False,
                core_stderr="", mind_stderr="",
                model_name=runtime.gguf.name,
                runtime_identity=runtime_identity,
            )
            print(
                f"llm execution {index}/{len(cases)} {case['name']}: {result['status']}",
                flush=True,
            )
    finally:
        if mind is not None:
            try:
                if mind.poll() is None:
                    call(mind, {"type": "shutdown", "id": "shutdown"}, "mind")
            except (BrokenPipeError, RuntimeError, OSError):
                pass
            close_process(mind)
            mind_stderr = mind.stderr.read() if mind.stderr else ""
        if core is not None:
            close_process(core)
            core_stderr = core.stderr.read() if core.stderr else ""
        shutil.rmtree(data_root, ignore_errors=True)
        cleanup_documents(documents_root, document_prefix, preexisting_documents)

    report = write_report(
        results, catalog_count, started, complete=True,
        core_stderr=core_stderr, mind_stderr=mind_stderr,
        model_name=runtime.gguf.name,
        runtime_identity=runtime_identity,
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"-> {OUTPUT}")
    if report["summary"]["status"] not in {"passed", "passed_with_environment_blocks"}:
        raise SystemExit(1)


def build_cases(run_id: str, document_prefix: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "deterministic_file_write",
            "planner_path": "deterministic_skeleton",
            "objective": f"crea archivo llm-e2e-{run_id}.txt con prueba-verificada-{run_id}",
            "expected": ["filesystem.write.text"],
            "confirm": {"filesystem.write.text"},
        },
        {
            "name": "llm_note_roundtrip",
            "planner_path": "real_llm_skeleton_and_grounding",
            "objective": (
                f"Crea una nota titulada Prueba LLM {run_id} con el contenido "
                f"verificación {run_id} y después lee esa misma nota creada."
            ),
            "expected": ["note.create", "note.read"],
            "dependency_positions": [[], [0]],
            "confirm": {"note.create"},
        },
        {
            "name": "llm_note_ordinal_dependency",
            "planner_path": "real_llm_conserved_turn_exact_dependency_grounding",
            "objective": (
                f"Crea una nota titulada Alfa {run_id} con contenido primero {run_id}, "
                f"después crea una nota titulada Beta {run_id} con contenido segundo "
                f"{run_id}, y finalmente lee la primera nota."
            ),
            "expected": ["note.create", "note.create", "note.read"],
            "dependency_positions": [[], [], [0]],
            "confirm": {"note.create"},
        },
        {
            "name": "llm_note_parallel_pair_dependencies",
            "planner_path": "real_llm_four_step_dependency_dag",
            "objective": (
                f"Crea una nota titulada Alfa paralela {run_id} con contenido "
                f"primero paralelo {run_id}, después crea una nota titulada Beta "
                f"paralela {run_id} con contenido segundo paralelo {run_id}, luego "
                "lee la primera nota creada y finalmente lee la segunda nota creada."
            ),
            "expected": ["note.create", "note.create", "note.read", "note.read"],
            "dependency_positions": [[], [], [0], [1]],
            "confirm": {"note.create"},
        },
        {
            "name": "llm_note_reverse_pair_dependencies",
            "planner_path": "real_llm_four_step_dependency_dag",
            "objective": (
                f"Crea una nota titulada Alfa inversa {run_id} con contenido primero "
                f"inverso {run_id}, después crea una nota titulada Beta inversa "
                f"{run_id} con contenido segundo inverso {run_id}, luego lee la "
                "segunda nota creada y finalmente lee la primera nota creada."
            ),
            "expected": ["note.create", "note.create", "note.read", "note.read"],
            "dependency_positions": [[], [], [1], [0]],
            "confirm": {"note.create"},
        },
        {
            "name": "llm_note_interleaved_pair_dependencies",
            "planner_path": "real_llm_four_step_dependency_dag",
            "objective": (
                f"Crea una nota titulada Alfa intercalada {run_id} con contenido "
                f"primero intercalado {run_id} y lee esa misma nota; después crea "
                f"una nota titulada Beta intercalada {run_id} con contenido segundo "
                f"intercalado {run_id} y lee esa misma segunda nota."
            ),
            "expected": ["note.create", "note.read", "note.create", "note.read"],
            "dependency_positions": [[], [0], [], [2]],
            "confirm": {"note.create"},
        },
        {
            "name": "llm_note_eight_step_interleaved_dependencies",
            "planner_path": "real_llm_eight_step_dependency_dag",
            "objective": (
                f"Crea una nota titulada Uno intercalada {run_id} con contenido uno "
                f"{run_id} y lee esa misma nota; luego crea una nota titulada Dos "
                f"intercalada {run_id} con contenido dos {run_id} y lee esa misma "
                f"nota; después crea una nota titulada Tres intercalada {run_id} con "
                f"contenido tres {run_id} y lee esa misma nota; finalmente crea una "
                f"nota titulada Cuatro intercalada {run_id} con contenido cuatro "
                f"{run_id} y lee esa misma nota."
            ),
            "expected": [
                "note.create", "note.read", "note.create", "note.read",
                "note.create", "note.read", "note.create", "note.read",
            ],
            "dependency_positions": [
                [], [0], [], [2], [], [4], [], [6],
            ],
            "confirm": {"note.create"},
        },
        {
            "name": "llm_note_eight_step_permuted_dependencies",
            "planner_path": "real_llm_eight_step_dependency_dag",
            "objective": (
                f"Crea cuatro notas: la primera titulada Uno permutada {run_id} con "
                f"contenido uno {run_id}, la segunda titulada Dos permutada {run_id} "
                f"con contenido dos {run_id}, la tercera titulada Tres permutada "
                f"{run_id} con contenido tres {run_id} y la cuarta titulada Cuatro "
                f"permutada {run_id} con contenido cuatro {run_id}. Después lee, en "
                "este orden exacto, la tercera nota, la primera nota, la cuarta nota "
                "y la segunda nota."
            ),
            "expected": [
                "note.create", "note.create", "note.create", "note.create",
                "note.read", "note.read", "note.read", "note.read",
            ],
            "dependency_positions": [
                [], [], [], [], [2], [0], [3], [1],
            ],
            "confirm": {"note.create"},
        },
        {
            "name": "llm_note_eight_step_permuted_dependencies_en",
            "planner_path": "real_llm_eight_step_dependency_dag",
            "ui_language": "en",
            "objective": (
                f"Create four notes: the first titled One permuted {run_id} with "
                f"content one {run_id}, the second titled Two permuted {run_id} "
                f"with content two {run_id}, the third titled Three permuted "
                f"{run_id} with content three {run_id}, and the fourth titled Four "
                f"permuted {run_id} with content four {run_id}. After that read, in "
                "this exact order, the fourth note, the second note, the first note, "
                "and the third note."
            ),
            "expected": [
                "note.create", "note.create", "note.create", "note.create",
                "note.read", "note.read", "note.read", "note.read",
            ],
            "dependency_positions": [
                [], [], [], [], [3], [1], [0], [2],
            ],
            "confirm": {"note.create"},
        },
        {
            "name": "office_roundtrip",
            "planner_path": "deterministic_skeleton_real_llm_grounding",
            "objective": (
                f"Crea un documento Word llamado {document_prefix} y después lee "
                "ese mismo documento que acabas de crear."
            ),
            "expected": ["office.document.create", "office.document.read"],
            "confirm": {"office.document.create"},
        },
        {
            "name": "capture_ocr_grounding",
            "planner_path": "deterministic_skeleton_real_llm_grounding",
            "objective": "lee el texto de mi pantalla",
            "expected": ["capture.screenshot", "ocr.read"],
            "confirm": {"capture.screenshot", "ocr.read"},
        },
        {
            "name": "llm_steam_catalog_status",
            "planner_path": "real_llm_skeleton",
            "objective": (
                "Primero enumera mi catálogo local de Steam y después comprueba el "
                "estado de instalación del AppID 945360."
            ),
            "expected": ["game.catalog.list", "game.install.status"],
            "confirm": set(),
        },
        {
            "name": "web_search_and_navigation",
            "planner_path": "deterministic_bounded_skeleton",
            "objective": (
                "Busca exactamente OpenAI Codex en la web y después navega exactamente "
                "a https://example.com/."
            ),
            "expected": ["web.search", "browser.navigate"],
            "confirm": {"browser.navigate"},
        },
        {
            "name": "streaming_and_search",
            "planner_path": "deterministic_bounded_skeleton",
            "objective": (
                "Navega mi sesión de YouTube exactamente a "
                "https://www.youtube.com/results?search_query=BAXY+planner "
                "y después busca exactamente OpenAI Codex en la web."
            ),
            "expected": ["streaming.navigate", "web.search"],
            "confirm": {"streaming.navigate"},
        },
        {
            "name": "llm_calendar_read",
            "planner_path": "real_llm_skeleton",
            "objective": (
                "Lista los eventos de mi calendario entre 2026-07-16T04:00:00Z "
                "y 2026-07-17T04:00:00Z."
            ),
            "expected": ["calendar.event.list"],
            "confirm": set(),
            "environmental_errors": {"outlook_profile_not_configured"},
        },
        {
            "name": "spotify_exact_then_pause",
            "planner_path": "deterministic_bounded_skeleton",
            "objective": (
                "Reproduce en Spotify la canción titulada exactamente Beat It y después "
                "pausa esa reproducción."
            ),
            "expected": ["media.play.exact", "media.control"],
            "confirm": {"media.play.exact", "media.control"},
        },
    ]


def run_case(
    core: subprocess.Popen[str],
    mind: subprocess.Popen[str],
    risks: dict[str, str],
    case: dict[str, Any],
) -> dict[str, Any]:
    before = time.perf_counter()
    decision = call(
        mind,
        {
            "type": "turn.decide",
            "id": f"{case['name']}-turn",
            "text": case["objective"],
            "history": [],
            "uiLanguage": case.get("ui_language", "es"),
        },
        "mind",
    )
    effect_operations = decision.get("effectOperations")
    if not isinstance(effect_operations, list):
        effect_operations = []
    effect_operations = [
        operation for operation in effect_operations if isinstance(operation, str)
    ]
    decision_seconds = round(time.perf_counter() - before, 3)
    result: dict[str, Any] = {
        "case": case["name"],
        "planner_path": case["planner_path"],
        "turn_response_type": decision.get("type"),
        "turn_kind": decision.get("kind"),
        "turn_question": decision.get("question"),
        "turn_reply": decision.get("reply"),
        "intent_operations": decision.get("intentOperations") or [],
        "effect_operations": effect_operations,
        "decision_seconds": decision_seconds,
        "response_type": None,
        "kind": None,
        "operations": [],
        "steps": [],
        "seconds": 0.0,
        "status": "failed",
    }
    if (
        decision.get("type") != "turn.result"
        or decision.get("kind") not in {"action", "plan"}
        or Counter(effect_operations)
        != Counter(case.get("expected_effects", case["expected"]))
    ):
        result["error"] = "turn decision did not exactly cover the bounded objective"
        result["seconds"] = round(time.perf_counter() - before, 3)
        return result

    reply = call(
        mind,
        {
            "type": "plan",
            "id": case["name"],
            "text": case["objective"],
            "history": [],
            "expectedOperations": effect_operations,
        },
        "mind",
    )
    result["response_type"] = reply.get("type")
    result["kind"] = reply.get("kind")
    if reply.get("type") != "plan.result" or reply.get("kind") != "plan":
        result["error"] = reply.get("message") or reply.get("question") or reply.get("code")
        result["seconds"] = round(time.perf_counter() - before, 3)
        return result

    steps = reply.get("steps") or []
    operations = [step.get("operation") for step in steps]
    result["operations"] = operations
    expected = case["expected"]
    if Counter(operations) != Counter(expected):
        result["error"] = "planner operations did not exactly cover the bounded objective"
        result["seconds"] = round(time.perf_counter() - before, 3)
        return result
    id_positions = {
        str(step.get("id", "")): position
        for position, step in enumerate(steps)
    }
    dependency_positions = [
        [id_positions.get(str(dependency), -1) for dependency in step.get("dependsOn") or []]
        for step in steps
    ]
    result["dependency_positions"] = dependency_positions
    if dependency_positions != case.get(
        "dependency_positions",
        dependency_positions,
    ):
        result["error"] = "planner bound a result consumer to the wrong producer"
        result["seconds"] = round(time.perf_counter() - before, 3)
        return result
    if any(operation.startswith("memory.") for operation in operations):
        result["error"] = "private operation crossed the planner boundary"
        result["seconds"] = round(time.perf_counter() - before, 3)
        return result

    mission_id = str(uuid.uuid4())
    observations: list[dict[str, Any]] = []
    completed: set[str] = set()
    pending = list(steps)
    while pending:
        progressed = False
        for step in list(pending):
            step_id = str(step.get("id", ""))
            dependencies = step.get("dependsOn") or []
            if not all(dependency in completed for dependency in dependencies):
                continue
            operation = str(step.get("operation", ""))
            arguments = step.get("arguments")
            grounded = False
            dependency_observations: list[dict[str, Any]] = []
            if step.get("argumentsMode") == "after_dependencies":
                selected = select_verified_dependency_observations(step, observations)
                if selected is None:
                    result["error"] = (
                        f"step {step_id} lacks exact verified dependency observations"
                    )
                    result["seconds"] = round(time.perf_counter() - before, 3)
                    return result
                dependency_observations = selected
                grounding = call(
                    mind,
                    {
                        "type": "plan.ground",
                        "id": f"{case['name']}-{step_id}",
                        "objective": case["objective"],
                        "operation": operation,
                        "purpose": step.get("purpose", ""),
                        "observations": dependency_observations,
                    },
                    "mind",
                )
                if grounding.get("type") != "plan.ground.result":
                    result["error"] = grounding.get("message") or grounding.get("code") \
                        or "grounding failed"
                    result["seconds"] = round(time.perf_counter() - before, 3)
                    return result
                arguments = grounding.get("arguments")
                grounded = True
            if not isinstance(arguments, dict):
                result["error"] = f"step {step_id} did not materialize arguments"
                result["seconds"] = round(time.perf_counter() - before, 3)
                return result

            dependency_authority_match = (
                dependency_authority_matches(arguments, dependency_observations)
                if grounded
                else None
            )
            if dependency_authority_match is False:
                result["error"] = (
                    f"step {step_id} selected authority outside its dependencies"
                )
                result["seconds"] = round(time.perf_counter() - before, 3)
                return result

            invocation_id = str(uuid.uuid4())
            request = {
                "type": "operation.request",
                "requestId": str(uuid.uuid4()),
                "missionId": mission_id,
                "invocationId": invocation_id,
                "operation": operation,
                "arguments": arguments,
            }
            response = call(core, request, "core")
            confirmed = False
            if response.get("errorCode") == "confirmation_required":
                if operation not in case["confirm"]:
                    result["error"] = f"unexpected confirmation request for {operation}"
                    result["seconds"] = round(time.perf_counter() - before, 3)
                    return result
                token = (response.get("result") or {}).get("token")
                if not isinstance(token, str) or not token:
                    result["error"] = f"confirmation challenge for {operation} had no token"
                    result["seconds"] = round(time.perf_counter() - before, 3)
                    return result
                request["requestId"] = str(uuid.uuid4())
                request["confirmationToken"] = token
                response = call(core, request, "core")
                confirmed = True

            step_result = {
                "id": step_id,
                "operation": operation,
                "risk": risks.get(operation),
                "arguments_mode": step.get("argumentsMode"),
                "argument_keys": sorted(arguments),
                "grounded": grounded,
                "dependency_step_ids": [
                    observation["stepId"]
                    for observation in dependency_observations
                ],
                "dependency_authority_match": dependency_authority_match,
                "confirmed": confirmed,
                "status": response.get("status"),
                "verified": response.get("verified"),
                "error": response.get("errorCode"),
                "effect_may_have_occurred": response.get("effectMayHaveOccurred", False),
            }
            if response.get("verified") is True and isinstance(response.get("result"), dict):
                step_result["evidence"] = project(response["result"], operation)
            result["steps"].append(step_result)
            if response.get("status") != "completed" or response.get("verified") is not True:
                error = response.get("errorCode") or f"{operation} was not verified"
                if (
                    error in case.get("environmental_errors", set())
                    and response.get("effectMayHaveOccurred", False) is False
                ):
                    result["status"] = "environment_blocked"
                    result["environmental_precondition"] = error
                    result["seconds"] = round(time.perf_counter() - before, 3)
                    return result
                result["error"] = error
                result["seconds"] = round(time.perf_counter() - before, 3)
                return result
            observations.append(make_observation(step_id, operation, response))
            completed.add(step_id)
            pending.remove(step)
            progressed = True
        if not progressed:
            result["error"] = "planner emitted an unresolved dependency graph"
            result["seconds"] = round(time.perf_counter() - before, 3)
            return result

    result["status"] = "passed"
    result["seconds"] = round(time.perf_counter() - before, 3)
    return result


def select_verified_dependency_observations(
    step: dict[str, Any],
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    dependencies = step.get("dependsOn")
    if (
        step.get("argumentsMode") != "after_dependencies"
        or not isinstance(dependencies, list)
        or not dependencies
        or any(not isinstance(item, str) or not item for item in dependencies)
        or len(set(dependencies)) != len(dependencies)
    ):
        return None

    selected: list[dict[str, Any]] = []
    for dependency in dependencies:
        matches = [
            observation
            for observation in observations
            if observation.get("stepId") == dependency
            and observation.get("verified") is True
            and observation.get("status") == "completed"
        ]
        if len(matches) != 1:
            return None
        selected.append(json.loads(json.dumps(matches[0], ensure_ascii=False)))
    return selected


def dependency_authority_matches(
    arguments: dict[str, Any],
    observations: list[dict[str, Any]],
) -> bool | None:
    argument_authority = collect_authority_values(arguments)
    if not argument_authority:
        return None
    observed_authority = collect_authority_values(observations)
    return all(
        values <= observed_authority.get(field, set())
        for field, values in argument_authority.items()
    )


def collect_authority_values(value: Any) -> dict[str, set[str]]:
    collected: dict[str, set[str]] = {}

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for field, child in node.items():
                if is_authority_field(field):
                    scalars = child if isinstance(child, list) else [child]
                    values = {
                        json.dumps(item, ensure_ascii=False, sort_keys=True)
                        for item in scalars
                        if item is not None and not isinstance(item, (dict, list))
                    }
                    if values:
                        collected.setdefault(field, set()).update(values)
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return collected


def is_authority_field(field: str) -> bool:
    return field in {"resourceUri", "url"} or field.endswith(("Id", "Ids"))


def make_observation(step_id: str, operation: str, response: dict[str, Any]) -> dict[str, Any]:
    observation: dict[str, Any] = {
        "stepId": step_id,
        "operation": operation,
        "verified": response.get("verified") is True,
        "status": response.get("status"),
    }
    if response.get("verified") is True and isinstance(response.get("result"), dict):
        observation["result"] = project(response["result"], operation)
    return observation


def project(value: Any, operation: str, depth: int = 0) -> Any:
    if depth > 5:
        return None
    if isinstance(value, dict):
        return {
            key: projected
            for key, child in value.items()
            if is_safe_field(operation, key)
            and (projected := project(child, operation, depth + 1)) is not None
        }
    if isinstance(value, list):
        return [project(child, operation, depth + 1) for child in value[:MAX_ARRAY_ITEMS]]
    if isinstance(value, str):
        return value[:MAX_STRING_LENGTH]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return None


def is_safe_field(operation: str, name: str) -> bool:
    return (
        name in SAFE_FIELDS
        or name in OPERATION_SAFE_FIELDS.get(operation, set())
        or name.endswith("Id")
        or name.endswith("Ids")
    )


def start_process(
    command: list[str],
    environment: dict[str, str],
    *,
    cwd: Path | None = None,
) -> subprocess.Popen[str]:
    return subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
        env=environment,
        cwd=cwd,
    )


def call(process: subprocess.Popen[str], message: dict[str, Any], label: str) -> dict[str, Any]:
    if process.stdin is None:
        raise RuntimeError(f"{label} stdin is unavailable")
    process.stdin.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
    process.stdin.flush()
    return receive(process, label)


def receive(process: subprocess.Popen[str], label: str) -> dict[str, Any]:
    if process.stdout is None:
        raise RuntimeError(f"{label} stdout is unavailable")
    line = process.stdout.readline()
    if not line:
        stderr = process.stderr.read() if process.stderr else ""
        raise RuntimeError(f"{label} closed its protocol: {stderr[-4_000:]}")
    return json.loads(line)


def close_process(process: subprocess.Popen[str]) -> None:
    if process.stdin is not None and not process.stdin.closed:
        process.stdin.close()
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def cleanup_documents(
    documents_root: Path,
    prefix: str,
    preexisting: set[Path],
) -> None:
    if not documents_root.is_dir():
        return
    root = documents_root.resolve()
    for candidate in documents_root.glob(prefix + "-*"):
        resolved = candidate.resolve()
        if candidate in preexisting or resolved.parent != root or not resolved.is_file():
            continue
        resolved.unlink()


def known_documents_root() -> Path:
    """Resolve Windows' redirected Documents known folder, not a guessed path."""

    registry_path = (
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
    )
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_path) as key:
            raw, _ = winreg.QueryValueEx(key, "Personal")
    except OSError as error:
        raise RuntimeError("windows_documents_known_folder_unavailable") from error
    if not isinstance(raw, str) or not raw.strip():
        raise RuntimeError("windows_documents_known_folder_invalid")
    resolved = Path(os.path.expandvars(raw)).resolve()
    if not resolved.is_absolute():
        raise RuntimeError("windows_documents_known_folder_invalid")
    return resolved


def write_report(
    results: list[dict[str, Any]],
    catalog_count: int,
    started: float,
    *,
    complete: bool,
    core_stderr: str,
    mind_stderr: str,
    model_name: str,
    runtime_identity: dict[str, Any],
) -> dict[str, Any]:
    passed = sum(case.get("status") == "passed" for case in results)
    environment_blocked = sum(
        case.get("status") == "environment_blocked" for case in results
    )
    failed = len(results) - passed - environment_blocked
    ambiguous = sum(
        step.get("effect_may_have_occurred") is True and step.get("verified") is not True
        for case in results for step in case.get("steps", [])
    )
    report = {
        "schema_version": 1,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "complete": complete,
        "scope": "real_llm_plan_ground_core_execute_verified_postread",
        "model": model_name,
        "runtime": runtime_identity,
        "core_catalog_count": catalog_count,
        "total_seconds": round(time.perf_counter() - started, 3),
        "cases": results,
        "summary": {
            "passed": passed,
            "environment_blocked": environment_blocked,
            "failed": failed,
            "total": len(results),
            "verified_steps": sum(
                step.get("verified") is True
                for case in results for step in case.get("steps", [])
            ),
            "real_llm_plan_cases": sum(
                str(case.get("planner_path", "")).startswith("real_llm")
                for case in results
            ),
            "real_llm_plan_cases_passed": sum(
                str(case.get("planner_path", "")).startswith("real_llm")
                and case.get("status") == "passed"
                for case in results
            ),
            "model_grounded_steps": sum(
                step.get("grounded") is True
                for case in results for step in case.get("steps", [])
            ),
            "ambiguous_effects": ambiguous,
            "status": (
                "passed" if complete and passed == len(results) and not ambiguous
                else "passed_with_environment_blocks"
                if complete and not failed and environment_blocked and not ambiguous
                else "failed" if complete else "in_progress"
            ),
        },
        "stderr": {
            "core": core_stderr[-4_000:],
            "mind": mind_stderr[-4_000:],
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    os.replace(temporary, OUTPUT)
    return report


if __name__ == "__main__":
    main()
