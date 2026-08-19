"""Goal 03B: pick the second opinion by measurement, not by taste.

The curated domain gate is one-sided and cannot tell "this request does not name
my domain" from "BAXY cannot do this". Goal 03B replaces its deletion branch
with a confirmation, and that needs a second opinion to decide *which* refusals
still deserve to be offered. This prices the candidates side by side on the raw
proposals a goal 03 run already recorded, so no product code moves first.

Every candidate is a one-sided read of the authenticated contract -- description
plus argument schema -- never of the shape of the text, which is the class goal
03 refuted five times.

The two ground truths come from the corpus itself: an in-catalog row whose
expected operation is among the refused ones *should* be offered; an
out-of-catalog row should never be.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    PROFILE_LIMITS,
    current_core_capabilities,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)
from experiments.mind_router_spike.probe_native_tool_contract_ceiling import (  # noqa: E402
    _start_server,
    _stop_server,
)

SCHEMA = "baxy.goal03b-second-opinion-variants.v1"
RESULT_DIR = REPO / "artifacts" / "development"

# The contrapositive of the identity question. A small local decider answers
# "is this the requested effect?" with a yes far too easily; asking it to name
# the mismatch instead makes the same weight state the opposite claim, and only
# a proposal that survives both readings is offered for confirmation.

OPERATION_MISMATCH_PROMPT = (
    "Se te da un pedido de una persona y una sola operacion del catalogo de "
    "BAXY. Responde compatible=true UNICAMENTE si la operacion produciria un "
    "resultado distinto del que la persona pidio: otro verbo, otro objeto, otro "
    "dispositivo, otro destino, otro momento, o un sustituto aproximado en vez "
    "de lo pedido. compatible=false si la operacion es exactamente el efecto "
    "pedido. Que falten argumentos, identificadores, confirmacion o un paso "
    "previo del catalogo no es una diferencia de resultado. Ejemplos de "
    "true: llamar por telefono contra enviar un mensaje; formatear un disco "
    "contra escribir un archivo; mandar flores contra crear un documento; "
    "arrancar una maquina virtual contra lanzar un juego. Ejemplo de false: "
    "apagar el bluetooth contra encender o apagar la radio bluetooth. No "
    "propongas otra operacion."
)


def _bounded_identity_prompt(llm_module: Any) -> str:
    return (
        llm_module.OPERATION_IDENTITY_PROMPT
        + " The person may also be asking for something this machine simply "
        "cannot do -- a physical errand, a purchase, a phone call, a household "
        "appliance, another device, an administrative task, or a program that "
        "is not installed. In that case there is no requested atomic effect for "
        "this operation to be, so compatible=false, however plausible the "
        "operation looks as a substitute. Never answer true for an operation "
        "that is merely the closest thing available."
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Goal 03B second-opinion variants")
    parser.add_argument("--source", required=True)
    parser.add_argument("--label", required=True)
    arguments = parser.parse_args()

    from baxy_mind import effect_intent
    from baxy_mind import llm as llm_module
    from baxy_mind.llm import LlmRuntime

    source = RESULT_DIR / f"goal03_{arguments.source}.telemetry.jsonl"
    rows = [
        json.loads(line)
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    contracts = {
        str(item["name"]): {
            "description": str(item["description"]),
            "arguments_schema": item["argumentsSchema"],
        }
        for item in capabilities
    }
    os.environ.update(
        sidecar_environment(
            runtime,
            gpu_layers=runtime.gpu_layers,
            llm_http_timeout=PROFILE_LIMITS["gpu"]["llm_http"],
        )
    )
    process, port = _start_server(runtime, runtime.gguf)
    os.environ["BAXY_MIND_LLM_ENDPOINT"] = f"http://127.0.0.1:{port}"
    llm = LlmRuntime()
    globals()["OPERATION_IDENTITY_PROMPT_BASE"] = llm_module.OPERATION_IDENTITY_PROMPT
    prompts = {
        "identity": llm_module.OPERATION_IDENTITY_PROMPT,
        "identity_bounded": _bounded_identity_prompt(llm_module),
        "strict": llm_module.OPERATION_COMPATIBILITY_PROMPT,
        "mismatch": OPERATION_MISMATCH_PROMPT,
    }
    seconds: collections.defaultdict[str, list[float]] = collections.defaultdict(list)
    report_rows: list[dict[str, Any]] = []
    try:
        for row in rows:
            text = str(row["text"])
            refused = [
                operation
                for operation in dict.fromkeys(row.get("raw_operations") or [])
                if operation in contracts
                and effect_intent.operation_domain_is_grounded(text, operation) is False
            ][:8]
            verdicts: dict[str, dict[str, bool]] = {name: {} for name in prompts}
            llm.begin_request(60.0, attempt=1)
            for operation in refused:
                for name, prompt in prompts.items():
                    started = time.perf_counter()
                    verdicts[name][operation] = llm._operation_is_fully_compatible(
                        text,
                        operation,
                        contracts[operation],
                        _system_prompt=prompt,
                    )
                    seconds[name].append(time.perf_counter() - started)
            report_rows.append(
                {
                    "case_id": row["case_id"],
                    "in_catalog": bool(row["in_catalog"]),
                    "expected_operations": list(row.get("expected_operations") or []),
                    "refused_operations": refused,
                    "verdicts": verdicts,
                    "text": text,
                }
            )
    finally:
        _stop_server(process)

    def offers(row: dict[str, Any], candidate: str) -> bool:
        refused = row["refused_operations"]
        if not refused:
            return False
        identity = row["verdicts"]["identity"]
        strict = row["verdicts"]["strict"]
        mismatch = row["verdicts"]["mismatch"]
        bounded = row["verdicts"]["identity_bounded"]
        if candidate == "identity":
            return all(identity[operation] for operation in refused)
        if candidate == "identity_bounded":
            return all(bounded[operation] for operation in refused)
        if candidate == "strict":
            return all(strict[operation] for operation in refused)
        if candidate == "identity_and_strict":
            return all(identity[operation] and strict[operation] for operation in refused)
        if candidate == "identity_and_not_mismatch":
            return all(
                identity[operation] and not mismatch[operation] for operation in refused
            )
        if candidate == "not_mismatch":
            return all(not mismatch[operation] for operation in refused)
        raise ValueError(candidate)

    candidates = (
        "identity",
        "identity_bounded",
        "strict",
        "identity_and_strict",
        "identity_and_not_mismatch",
        "not_mismatch",
    )
    summary: dict[str, dict[str, int]] = {}
    for candidate in candidates:
        offered_expected = 0
        offered_other = 0
        offered_out = 0
        refused_in = 0
        for row in report_rows:
            if not row["refused_operations"]:
                continue
            offered = offers(row, candidate)
            if row["in_catalog"]:
                if not offered:
                    refused_in += 1
                elif set(row["expected_operations"]) & set(row["refused_operations"]):
                    offered_expected += 1
                else:
                    offered_other += 1
            elif offered:
                offered_out += 1
        summary[candidate] = {
            "in_catalog_offered_the_expected_operation": offered_expected,
            "in_catalog_offered_another_operation": offered_other,
            "in_catalog_still_unsupported": refused_in,
            "out_of_catalog_offered": offered_out,
        }

    report = {
        "schema": SCHEMA,
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {
            "telemetry": str(source.relative_to(REPO)),
            "sha256": _sha256(source),
            "rows": len(rows),
        },
        "population": {
            "rows_the_gate_refuses": sum(
                1 for row in report_rows if row["refused_operations"]
            ),
            "in_catalog": sum(
                1
                for row in report_rows
                if row["refused_operations"] and row["in_catalog"]
            ),
            "out_of_catalog": sum(
                1
                for row in report_rows
                if row["refused_operations"] and not row["in_catalog"]
            ),
        },
        "seconds": {
            name: {
                "calls": len(values),
                "p50": round(statistics.median(values), 4) if values else None,
            }
            for name, values in sorted(seconds.items())
        },
        "candidates": summary,
        "rows": report_rows,
    }
    destination = RESULT_DIR / f"goal03b_second_opinion_variants_{arguments.label}.json"
    write_json_atomic(destination, report)
    print(
        json.dumps(
            {key: report[key] for key in ("population", "candidates", "seconds")},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
