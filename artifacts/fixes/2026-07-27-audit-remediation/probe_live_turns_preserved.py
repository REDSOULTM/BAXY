"""Sonda de remediación que conserva los efectos reconocidos entre turn y plan."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def receive(process: subprocess.Popen[str]) -> dict[str, Any]:
    line = process.stdout.readline()
    if not line:
        raise RuntimeError("process closed: " + process.stderr.read())
    return json.loads(line)


def call(
    process: subprocess.Popen[str], message: dict[str, Any]
) -> dict[str, Any]:
    process.stdin.write(
        json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    process.stdin.flush()
    return receive(process)


def observed_operations(
    turn: dict[str, Any], plan: dict[str, Any] | None
) -> list[str]:
    if turn.get("kind") == "action":
        operation = turn.get("operation")
        return [operation] if isinstance(operation, str) else []
    if turn.get("kind") == "plan" and isinstance(plan, dict):
        steps = plan.get("steps")
        if isinstance(steps, list):
            return [
                step["operation"]
                for step in steps
                if isinstance(step, dict)
                and isinstance(step.get("operation"), str)
            ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases-json", type=Path, required=True)
    parser.add_argument("--history-json", type=Path)
    parser.add_argument("--endpoint")
    args = parser.parse_args()

    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("remediation-turn-probe-" + uuid.uuid4().hex)
    )
    runtime_manifest = json.loads(
        (
            Path(os.environ["LOCALAPPDATA"])
            / "BAXYRuntime"
            / "mind-runtime-v1.json"
        ).read_text(encoding="utf-8")
    )
    environment = {
        **os.environ,
        "PYTHONPATH": str(Path.cwd() / "src"),
        "BAXY_DATA_DIR": str(data_root),
        "BAXY_MIND_LLM_GGUF": str(runtime_manifest["gguf"]),
        "BAXY_MIND_LLAMA_SERVER": str(runtime_manifest["llama_server"]),
        "BAXY_MIND_LLM_REQUEST_TIMEOUT": "6",
        "HF_HUB_OFFLINE": "1",
    }
    if args.endpoint:
        environment["BAXY_MIND_LLM_ENDPOINT"] = args.endpoint
    else:
        environment.pop("BAXY_MIND_LLM_ENDPOINT", None)

    core = subprocess.Popen(
        [str(args.core.resolve(strict=True))],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    mind: subprocess.Popen[str] | None = None
    rows: list[dict[str, Any]] = []
    try:
        hello = receive(core)
        capabilities = [
            {
                key: item[key]
                for key in ("name", "description", "argumentsSchema", "risk")
            }
            for item in hello["capabilities"]
        ]
        mind = subprocess.Popen(
            [sys.executable, "-X", "utf8", "-m", "baxy_mind"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=environment,
            cwd=Path.cwd(),
        )
        mind_hello = receive(mind)
        catalog_request = {
            "type": "catalog.configure",
            "id": "catalog",
            "capabilities": capabilities,
        }
        application_catalog = hello.get("applicationCatalog")
        if isinstance(application_catalog, dict):
            catalog_request["applicationCatalog"] = application_catalog
        catalog_ready = call(mind, catalog_request)
        time.sleep(8)
        history = (
            json.loads(args.history_json.read_text(encoding="utf-8"))
            if args.history_json is not None
            else [
                {
                    "role": "assistant",
                    "content": "Hola. Estoy lista para ayudarte con este equipo.",
                }
            ]
        )
        cases = json.loads(args.cases_json.read_text(encoding="utf-8"))
        for index, raw_case in enumerate(cases, 1):
            case = raw_case if isinstance(raw_case, dict) else {"text": raw_case}
            text = str(case["text"])
            started = time.perf_counter()
            turn = call(
                mind,
                {
                    "type": "turn.decide",
                    "id": f"case-{index}",
                    "text": text,
                    "history": history,
                },
            )
            plan = None
            if turn.get("kind") == "plan":
                plan = call(
                    mind,
                    {
                        "type": "plan",
                        "id": f"plan-{index}",
                        "text": text,
                        "history": history,
                        "expectedOperations": turn.get("effectOperations", []),
                    },
                )

            expected_kind = case.get("expectedKind")
            expected_operation = case.get("expectedOperation")
            expected_plan = case.get("expectedPlanOperations")
            forbidden_kinds = case.get("forbiddenKinds", [])
            forbidden_operations = case.get("forbiddenOperations", [])
            forbidden_sequences = case.get("forbiddenOperationSequences", [])
            operations = observed_operations(turn, plan)
            kind_matches = expected_kind is None or turn.get("kind") == expected_kind
            operation_matches = (
                expected_operation is None
                or operations == [expected_operation]
            )
            plan_matches = expected_plan is None or operations == expected_plan
            forbidden_matches = (
                not isinstance(forbidden_kinds, list)
                or turn.get("kind") not in forbidden_kinds
            )
            forbidden_sequence_matches = (
                not isinstance(forbidden_sequences, list)
                or operations not in forbidden_sequences
            )
            forbidden_operation_matches = (
                not isinstance(forbidden_operations, list)
                or not any(
                    operation in forbidden_operations
                    for operation in operations
                )
            )
            matches = (
                kind_matches
                and operation_matches
                and plan_matches
                and forbidden_matches
                and forbidden_sequence_matches
                and forbidden_operation_matches
            )
            rows.append(
                {
                    "text": text,
                    "expected": {
                        key: case[key]
                        for key in (
                            "expectedKind",
                            "expectedOperation",
                            "expectedPlanOperations",
                            "forbiddenKinds",
                            "forbiddenOperations",
                            "forbiddenOperationSequences",
                        )
                        if key in case
                    },
                    "elapsed_seconds": round(
                        time.perf_counter() - started, 3
                    ),
                    "matches": matches,
                    "observedOperations": operations,
                    "result": turn,
                    "plan": plan,
                }
            )
            print(
                f"{index:02d}/{len(cases)} "
                f"{'PASS' if matches else 'FAIL'} {text!r}: "
                f"{turn.get('kind')} {', '.join(operations)}",
                flush=True,
            )

        report = {
            "schema": "baxy-audit-remediation-live-turn-probe-v1",
            "measured_at": datetime.now(timezone.utc).isoformat(),
            "catalog_count": len(capabilities),
            "mind_hello": mind_hello,
            "catalog_ready": catalog_ready,
            "history": history,
            "passed": sum(1 for row in rows if row["matches"]),
            "failed": sum(1 for row in rows if not row["matches"]),
            "cases": rows,
        }
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    finally:
        if mind is not None:
            try:
                call(mind, {"type": "shutdown", "id": "shutdown"})
            except (BrokenPipeError, OSError, RuntimeError):
                pass
            if mind.poll() is None:
                mind.kill()
            mind.wait(timeout=10)
        if core.stdin:
            core.stdin.close()
        if core.poll() is None:
            core.wait(timeout=10)
        shutil.rmtree(data_root, ignore_errors=True)
    return 1 if any(not row["matches"] for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
