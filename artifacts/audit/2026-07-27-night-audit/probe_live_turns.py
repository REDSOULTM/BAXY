"""Sonda sin efectos de turn.decide contra el modelo vivo del escritorio."""

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


CASES = [
    "Hola",
    "Abre Opera",
    "Abre el Bloc de notas",
    "abre notepad",
    "Abre la calculadora",
    "Abre Chrome",
    "Abre Spotify",
    "Que hora es?",
    "Abre Opera y navega a https://example.com/",
    "Abre Spotify, reproduce exactamente Beat It y despues pausa",
]


def receive(process: subprocess.Popen[str]) -> dict[str, Any]:
    line = process.stdout.readline()
    if not line:
        raise RuntimeError("process closed: " + process.stderr.read())
    return json.loads(line)


def call(process: subprocess.Popen[str], message: dict[str, Any]) -> dict[str, Any]:
    process.stdin.write(
        json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    process.stdin.flush()
    return receive(process)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint")
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-plans", action="store_true")
    parser.add_argument("--case", action="append", dest="selected_cases")
    parser.add_argument("--cases-json", type=Path)
    parser.add_argument("--history-json", type=Path)
    args = parser.parse_args()
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("live-turn-probe-" + uuid.uuid4().hex)
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
    rows = []
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
        ready = call(
            mind,
            {
                "type": "catalog.configure",
                "id": "catalog",
                "capabilities": capabilities,
            },
        )
        # The desktop initializes its router worker and prewarms the model
        # before enabling input. Mirror that readiness window.
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
        if args.cases_json is not None:
            loaded_cases = json.loads(args.cases_json.read_text(encoding="utf-8"))
            cases = [
                item if isinstance(item, dict) else {"text": str(item)}
                for item in loaded_cases
            ]
        else:
            cases = [
                {"text": text} for text in (args.selected_cases or CASES)
            ]
        for index, case in enumerate(cases, 1):
            text = str(case["text"])
            started = time.perf_counter()
            result = call(
                mind,
                {
                    "type": "turn.decide",
                    "id": f"case-{index}",
                    "text": text,
                    "history": history,
                },
            )
            plan = None
            if args.include_plans and result.get("kind") == "plan":
                plan = call(
                    mind,
                    {
                        "type": "plan",
                        "id": f"plan-{index}",
                        "text": text,
                        "history": history,
                    },
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
                        )
                        if key in case
                    },
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                    "result": result,
                    "plan": plan,
                }
            )
            print(
                f"{index:02d}/{len(cases)} {text!r}: "
                f"{result.get('kind')} {result.get('operation') or ''} "
                f"{result.get('question') or result.get('reply') or ''}",
                flush=True,
            )
        report = {
            "schema": "baxy-night-audit-live-turn-probe-v1",
            "measured_at": datetime.now(timezone.utc).isoformat(),
            "catalog_count": len(capabilities),
            "mind_hello": mind_hello,
            "catalog_ready": ready,
            "history": history,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
