"""Smoke seguro de cada operación publicada por el core real de BAXY.

Este arnés pertenece a la evidencia de auditoría, no al producto. Todas las
operaciones reciben una solicitud deliberadamente inválida para comprobar la
frontera de schema sin efectos. Las operaciones declaradas read_only reciben
además una solicitud válida sintetizada para alcanzar el provider; un fallo
seguro por objetivo inexistente sigue contando como provider alcanzable.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def receive(process: subprocess.Popen[str]) -> dict[str, Any]:
    line = process.stdout.readline()
    if not line:
        raise RuntimeError("core_closed: " + process.stderr.read())
    return json.loads(line)


def call(process: subprocess.Popen[str], operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
    request = {
        "type": "operation.request",
        "requestId": str(uuid.uuid4()),
        "missionId": str(uuid.uuid4()),
        "invocationId": str(uuid.uuid4()),
        "operation": operation,
        "arguments": arguments,
    }
    process.stdin.write(json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n")
    process.stdin.flush()
    return receive(process)


def sample(schema: Any, name: str = "") -> Any:
    if not isinstance(schema, dict):
        return None
    for key in ("const", "default"):
        if key in schema:
            return schema[key]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    for key in ("oneOf", "anyOf"):
        variants = schema.get(key)
        if isinstance(variants, list) and variants:
            return sample(variants[0], name)
    value_type = schema.get("type")
    if isinstance(value_type, list):
        value_type = next((item for item in value_type if item != "null"), "null")
    if value_type == "object" or "properties" in schema:
        properties = schema.get("properties")
        required = schema.get("required")
        if not isinstance(properties, dict):
            return {}
        names = required if isinstance(required, list) else []
        return {
            child_name: sample(properties[child_name], child_name)
            for child_name in names
            if child_name in properties
        }
    if value_type == "array":
        minimum = schema.get("minItems", 0)
        return [sample(schema.get("items", {}), name)] if minimum else []
    if value_type == "integer":
        return int(schema.get("minimum", 1))
    if value_type == "number":
        return float(schema.get("minimum", 1))
    if value_type == "boolean":
        return False
    if value_type == "null":
        return None
    lowered = name.casefold()
    if "url" in lowered or "uri" in lowered:
        return "https://example.com/"
    if lowered.endswith("utc"):
        return "2026-07-27T00:00:00Z"
    if lowered in {"limit", "count"}:
        return 1
    if lowered.endswith("id"):
        return "audit-missing-id"
    if "path" in lowered:
        return "audit-missing-path"
    if "query" in lowered:
        return "BAXY audit"
    return "audit"


def safe_terminal(response: dict[str, Any]) -> bool:
    return (
        response.get("type") == "operation.response"
        and response.get("status") in {"completed", "failed"}
        and response.get("effectMayHaveOccurred", False) is not True
    )


def isolated_provider_call(
    core: Path,
    operation: str,
    arguments: dict[str, Any],
) -> tuple[dict[str, Any] | None, int, str, bool]:
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("catalog-provider-" + uuid.uuid4().hex)
    )
    environment = {**os.environ, "BAXY_DATA_DIR": str(data_root)}
    process = subprocess.Popen(
        [str(core)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    request = {
        "type": "operation.request",
        "requestId": str(uuid.uuid4()),
        "missionId": str(uuid.uuid4()),
        "invocationId": str(uuid.uuid4()),
        "operation": operation,
        "arguments": arguments,
    }
    response: dict[str, Any] | None = None
    stderr = ""
    timed_out = False
    try:
        payload = json.dumps(
            request, ensure_ascii=False, separators=(",", ":")
        ) + "\n"
        try:
            stdout, stderr = process.communicate(input=payload, timeout=20)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            stdout, stderr = process.communicate(timeout=10)
        lines = [line for line in stdout.splitlines() if line.strip()]
        if len(lines) >= 2:
            response = json.loads(lines[1])
    finally:
        if process.poll() is None:
            process.kill()
            exit_code = process.wait(timeout=10)
        else:
            exit_code = process.returncode
        shutil.rmtree(data_root, ignore_errors=True)
    return response, exit_code, stderr, timed_out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    core = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    private_root = Path(os.environ["LOCALAPPDATA"]) / "BAXY"
    private_root.mkdir(parents=True, exist_ok=True)
    data_root = private_root / ("catalog-smoke-" + uuid.uuid4().hex)
    environment = {**os.environ, "BAXY_DATA_DIR": str(data_root)}
    process = subprocess.Popen(
        [str(core)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    started = time.perf_counter()
    cases: list[dict[str, Any]] = []
    hello: dict[str, Any] = {}
    stderr = ""
    try:
        hello = receive(process)
        for index, capability in enumerate(hello.get("capabilities") or [], 1):
            name = str(capability.get("name", ""))
            risk = str(capability.get("risk", ""))
            invalid = call(process, name, {"__baxyAuditUnexpected": True})
            contract_ok = (
                invalid.get("status") == "failed"
                and invalid.get("verified") is False
                and invalid.get("effectMayHaveOccurred", False) is not True
                and isinstance(invalid.get("errorCode"), str)
            )
            provider: dict[str, Any] | None = None
            provider_ok: bool | None = None
            synthesized: dict[str, Any] | None = None
            provider_exit_code: int | None = None
            provider_stderr = ""
            provider_timed_out = False
            if risk == "read_only":
                raw = sample(capability.get("argumentsSchema"), name)
                synthesized = raw if isinstance(raw, dict) else {}
                (
                    provider,
                    provider_exit_code,
                    provider_stderr,
                    provider_timed_out,
                ) = isolated_provider_call(core, name, synthesized)
                provider_ok = provider is not None and safe_terminal(provider)
            cases.append(
                {
                    "index": index,
                    "operation": name,
                    "risk": risk,
                    "contract": {
                        "passed": contract_ok,
                        "status": invalid.get("status"),
                        "verified": invalid.get("verified"),
                        "error": invalid.get("errorCode"),
                        "effect_may_have_occurred": invalid.get(
                            "effectMayHaveOccurred", False
                        ),
                    },
                    "provider": None
                    if risk != "read_only"
                    else {
                        "passed": provider_ok,
                        "argument_keys": sorted(synthesized or {}),
                        "status": provider.get("status") if provider else None,
                        "verified": provider.get("verified") if provider else None,
                        "error": provider.get("errorCode") if provider else None,
                        "effect_may_have_occurred": (
                            provider.get("effectMayHaveOccurred", False)
                            if provider
                            else False
                        ),
                        "core_exit_code": provider_exit_code,
                        "core_stderr": provider_stderr.strip(),
                        "timed_out": provider_timed_out,
                    },
                }
            )
            print(
                f"{index:03d}/{len(hello.get('capabilities') or [])} "
                f"{name}: contract={'PASS' if contract_ok else 'FAIL'}"
                + (
                    f" provider={'PASS' if provider_ok else 'FAIL'}"
                    if provider_ok is not None
                    else ""
                ),
                flush=True,
            )
    finally:
        if process.stdin:
            process.stdin.close()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        stderr = process.stderr.read() if process.stderr else ""
        shutil.rmtree(data_root, ignore_errors=True)

    failed = [
        case
        for case in cases
        if not case["contract"]["passed"]
        or case["provider"] is not None
        and not case["provider"]["passed"]
    ]
    report = {
        "schema": "baxy-night-audit-catalog-smoke-v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "core": str(core),
        "core_version": hello.get("coreVersion"),
        "catalog_count": len(hello.get("capabilities") or []),
        "seconds": round(time.perf_counter() - started, 3),
        "summary": {
            "total_operations": len(cases),
            "contract_passed": sum(case["contract"]["passed"] for case in cases),
            "read_only_provider_attempted": sum(
                case["provider"] is not None for case in cases
            ),
            "read_only_provider_passed": sum(
                case["provider"] is not None and case["provider"]["passed"]
                for case in cases
            ),
            "failed": len(failed),
        },
        "cases": cases,
        "stderr": stderr,
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2), flush=True)
    return 1 if failed or len(cases) != 168 else 0


if __name__ == "__main__":
    raise SystemExit(main())
