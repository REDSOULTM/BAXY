"""Goal 03: is the argument right once the operation is right?

Choosing the operation and filling its arguments are two different requests in
the protocol, and consolidating a catalogue moves work from the first to the
second. A tool hit rate of 100 % with the wrong argument is the same loss in
another place, so this measures the second half on its own.

Only the rows whose arguments the text fixes unambiguously take part, and their
expectations live in their own file so the comprehension corpus stays byte-exact
against the runs that scored it. Each row asks the runtime for the arguments of
its declared operation and compares the fields the expectation names; fields it
does not name are not scored, because the contract may legitimately fill them.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
)
from experiments.mind_router_spike.run_goal03_comprehension import (  # noqa: E402
    CORPUS,
    RESULT_DIR,
    load_corpus,
)

SCHEMA = "baxy.goal03-arguments.v1"
EXPECTATIONS = (
    REPO / "artifacts" / "development" / "goal03_argument_expectations.v1.jsonl"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Goal 03 argument accuracy")
    parser.add_argument("--label", required=True)
    parser.add_argument("--corpus", default=str(CORPUS))
    parser.add_argument("--expectations", default=str(EXPECTATIONS))
    parser.add_argument("--gguf")
    arguments = parser.parse_args()

    corpus = {row["case_id"]: row for row in load_corpus(Path(arguments.corpus))}
    rows = [
        {**corpus[entry["case_id"]], **entry}
        for entry in load_corpus(Path(arguments.expectations))
    ]
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities, applications, games = current_core_catalog_snapshot(
        discover_core(None)
    )
    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    environment["BAXY_VOICE_STREAMING_STT"] = "off"
    if arguments.gguf:
        environment["BAXY_MIND_LLM_GGUF"] = arguments.gguf

    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=environment,
        cwd=REPO,
    )
    records: list[dict[str, Any]] = []
    try:
        if client.next_message(limits["handshake"]).get("type") != "hello":
            raise RuntimeError("el sidecar no saludó")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": f"{arguments.label}-catalog",
                "capabilities": capabilities,
                "applicationCatalog": applications,
                "gameCatalog": games,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("el catálogo fue rechazado")
        for row in rows:
            started = time.perf_counter()
            reply = client.request(
                {
                    "type": "arguments",
                    "id": f"{arguments.label}-{row['case_id']}",
                    "operation": row["operation"],
                    "text": row["text"],
                },
                limits["arguments"],
            )
            produced = reply.get("arguments")
            produced = produced if isinstance(produced, dict) else {}
            expected = row["expected_arguments"]
            wrong = {
                field: {"expected": value, "observed": produced.get(field)}
                for field, value in expected.items()
                if produced.get(field) != value
            }
            records.append(
                {
                    "case_id": row["case_id"],
                    "language": row["language"],
                    "operation": row["operation"],
                    "text": row["text"],
                    "ok": reply.get("ok"),
                    "question": str(reply.get("question") or ""),
                    "expected_arguments": expected,
                    "observed_arguments": produced,
                    "wrong_fields": wrong,
                    "exact": not wrong and reply.get("ok") is True,
                    "seconds": round(time.perf_counter() - started, 3),
                }
            )
    finally:
        client.close(graceful_message=None, timeout=limits["shutdown"])

    exact = sum(1 for record in records if record["exact"])
    asked = sum(1 for record in records if record["ok"] is False)
    fields_total = sum(len(record["expected_arguments"]) for record in records)
    fields_wrong = sum(len(record["wrong_fields"]) for record in records)
    seconds = sorted(record["seconds"] for record in records)
    report = {
        "schema": SCHEMA,
        "decider": Path(arguments.gguf).name if arguments.gguf else "registered",
        "rows": len(records),
        "exact_argument_sets": exact,
        "rate": round(exact / max(len(records), 1), 4),
        "asked_instead_of_filling": asked,
        "fields": {
            "scored": fields_total,
            "wrong": fields_wrong,
            "rate": round((fields_total - fields_wrong) / max(fields_total, 1), 4),
        },
        "latency_seconds": {
            "p50": round(statistics.median(seconds), 3) if seconds else None,
            "max": round(seconds[-1], 3) if seconds else None,
        },
        "records": records,
    }
    destination = RESULT_DIR / f"goal03_arguments_{arguments.label}.json"
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "decider",
                    "rows",
                    "exact_argument_sets",
                    "rate",
                    "asked_instead_of_filling",
                    "fields",
                    "latency_seconds",
                )
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
