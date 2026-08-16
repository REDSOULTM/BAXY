"""Safely exercise every compiled Core operation contract.

Every catalogue operation first receives deliberately invalid arguments.  That
proves that the public Core boundary rejects malformed calls without dispatching
an effect.  Read-only operations then receive a schema-derived request against
an isolated data root so their real handler/provider path is reached safely.

``memory.*`` is intentionally different: the desktop App owns the private
envelope boundary.  A raw Core request must be rejected with
``invalid_private_envelope`` and is covered end-to-end by the separate App
memory gate.  Treating that rejection as a generic Core failure was the defect
in the historical July audit harness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "baxy.mvp-core-provider-matrix.v1"
PRIVATE_ENVELOPE_ERROR = "invalid_private_envelope"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def receive(process: subprocess.Popen[str]) -> dict[str, Any]:
    assert process.stdout is not None
    line = process.stdout.readline()
    if not line:
        stderr = process.stderr.read() if process.stderr is not None else ""
        raise RuntimeError(f"core_closed: {stderr.strip()}")
    payload = json.loads(line)
    if not isinstance(payload, dict):
        raise RuntimeError("Core emitted a non-object protocol frame")
    return payload


def call(
    process: subprocess.Popen[str],
    operation: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    assert process.stdin is not None
    request = {
        "type": "operation.request",
        "requestId": str(uuid.uuid4()),
        "missionId": str(uuid.uuid4()),
        "invocationId": str(uuid.uuid4()),
        "operation": operation,
        "arguments": arguments,
    }
    process.stdin.write(
        json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    process.stdin.flush()
    return receive(process)


def sample(schema: Any, name: str = "") -> Any:
    """Create a bounded, inert value satisfying the common catalogue schemas."""
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
        minimum = int(schema.get("minItems", 0))
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
        return "2026-08-11T12:00:00Z"
    if lowered in {"limit", "count"}:
        return 1
    if lowered.endswith("id"):
        return "mvp-missing-id"
    if "path" in lowered:
        return "mvp-missing-path"
    if "query" in lowered:
        return "BAXY MVP verification"
    return "mvp-verification"


def no_possible_effect(response: dict[str, Any]) -> bool:
    return response.get("effectMayHaveOccurred", False) is not True


def valid_contract_rejection(
    operation: str,
    response: dict[str, Any],
) -> bool:
    if response.get("type") != "operation.response":
        return False
    if response.get("verified") is not False or not no_possible_effect(response):
        return False
    if operation.startswith("memory."):
        return (
            response.get("status") == "rejected"
            and response.get("errorCode") == PRIVATE_ENVELOPE_ERROR
        )
    return response.get("status") == "failed" and isinstance(
        response.get("errorCode"), str
    )


def valid_read_only_terminal(response: dict[str, Any]) -> bool:
    if response.get("type") != "operation.response" or not no_possible_effect(response):
        return False
    status = response.get("status")
    if status == "completed":
        return response.get("verified") is True and response.get("errorCode") is None
    if status == "failed":
        return response.get("verified") is False and isinstance(
            response.get("errorCode"), str
        )
    return False


def isolated_provider_call(
    core: Path,
    operation: str,
    arguments: dict[str, Any],
    timeout_seconds: int,
) -> tuple[dict[str, Any] | None, int, str, bool]:
    data_root = Path(os.environ["LOCALAPPDATA"]) / "BAXY" / (
        "mvp-provider-" + uuid.uuid4().hex
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
    timed_out = False
    stderr = ""
    try:
        payload = json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n"
        try:
            stdout, stderr = process.communicate(input=payload, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            stdout, stderr = process.communicate(timeout=10)
        frames = [line for line in stdout.splitlines() if line.strip()]
        if len(frames) >= 2:
            parsed = json.loads(frames[1])
            response = parsed if isinstance(parsed, dict) else None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        exit_code = int(process.returncode)
        shutil.rmtree(data_root, ignore_errors=True)
    return response, exit_code, stderr, timed_out


def run(core: Path, output: Path, timeout_seconds: int) -> dict[str, Any]:
    core = core.resolve(strict=True)
    output = output.resolve()
    if output.exists():
        raise RuntimeError(f"refusing to overwrite existing evidence: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    private_root = Path(os.environ["LOCALAPPDATA"]) / "BAXY"
    private_root.mkdir(parents=True, exist_ok=True)
    data_root = private_root / ("mvp-core-contract-" + uuid.uuid4().hex)
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
    rows: list[dict[str, Any]] = []
    hello: dict[str, Any] = {}
    stderr = ""
    try:
        hello = receive(process)
        capabilities = hello.get("capabilities") or []
        for index, capability in enumerate(capabilities, 1):
            operation = str(capability.get("name", ""))
            risk = str(capability.get("risk", ""))
            invalid = call(process, operation, {"__baxyMvpUnexpected": True})
            contract_passed = valid_contract_rejection(operation, invalid)
            provider: dict[str, Any] | None = None
            if risk == "read_only" and not operation.startswith("memory."):
                synthesized = sample(capability.get("argumentsSchema"), operation)
                arguments = synthesized if isinstance(synthesized, dict) else {}
                response, exit_code, provider_stderr, timed_out = isolated_provider_call(
                    core, operation, arguments, timeout_seconds
                )
                provider = {
                    "passed": response is not None
                    and valid_read_only_terminal(response)
                    and not timed_out,
                    "argumentKeys": sorted(arguments),
                    "status": response.get("status") if response else None,
                    "verified": response.get("verified") if response else None,
                    "errorCode": response.get("errorCode") if response else None,
                    "effectMayHaveOccurred": (
                        response.get("effectMayHaveOccurred", False)
                        if response
                        else False
                    ),
                    "coreExitCode": exit_code,
                    "stderr": provider_stderr.strip(),
                    "timedOut": timed_out,
                }
            row = {
                "index": index,
                "operation": operation,
                "risk": risk,
                "contract": {
                    "passed": contract_passed,
                    "status": invalid.get("status"),
                    "verified": invalid.get("verified"),
                    "errorCode": invalid.get("errorCode"),
                    "effectMayHaveOccurred": invalid.get(
                        "effectMayHaveOccurred", False
                    ),
                },
                "readOnlyProvider": provider,
                "separateAppMemoryGateRequired": operation.startswith("memory."),
            }
            rows.append(row)
            provider_label = ""
            if provider is not None:
                provider_label = f" provider={'PASS' if provider['passed'] else 'FAIL'}"
            print(
                f"{index:03d}/{len(capabilities)} {operation}: "
                f"contract={'PASS' if contract_passed else 'FAIL'}{provider_label}",
                flush=True,
            )
    finally:
        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        stderr = process.stderr.read() if process.stderr is not None else ""
        shutil.rmtree(data_root, ignore_errors=True)

    contract_passed = sum(bool(row["contract"]["passed"]) for row in rows)
    providers = [row["readOnlyProvider"] for row in rows if row["readOnlyProvider"]]
    provider_passed = sum(bool(provider["passed"]) for provider in providers)
    memory_rows = sum(bool(row["separateAppMemoryGateRequired"]) for row in rows)
    gate_passed = (
        len(rows) == 169
        and contract_passed == len(rows)
        and provider_passed == len(providers)
        and memory_rows == 11
    )
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "all_contracts_and_non_memory_read_only_real_providers_no_effects",
        "programSha256": sha256(Path(__file__).resolve()),
        "core": str(core),
        "coreSha256": sha256(core),
        "coreVersion": hello.get("coreVersion"),
        "effectsExecuted": 0,
        "seconds": round(time.perf_counter() - started, 3),
        "summary": {
            "catalogOperations": len(rows),
            "contractsPassed": contract_passed,
            "readOnlyProvidersAttempted": len(providers),
            "readOnlyProvidersPassed": provider_passed,
            "appMemoryBoundaryRows": memory_rows,
            "failed": (len(rows) - contract_passed)
            + (len(providers) - provider_passed),
        },
        "separateRequiredEvidence": {
            "appMemoryGate": "RoutesEveryReviewedCatalogMemoryOperation",
            "effectfulProviderSimulations": "pending",
        },
        "rows": rows,
        "coreStderr": stderr.strip(),
        "gatePassed": gate_passed,
    }
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, output)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run(args.core, args.output, args.timeout_seconds)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2), flush=True)
    return 0 if report["gatePassed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
