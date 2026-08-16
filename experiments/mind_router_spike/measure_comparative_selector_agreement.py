"""Price a comparative selector as the gate the per-operation veto cannot be.

R116 measured that the domain gate is *inverted* on paraphrase, not merely
loose: across V2's eight executions it refused the wanted operation in all seven
that failed and grounded it in the one that succeeded. The stated cause is
structural -- a paraphrase drops the specific term and keeps the generic one, so
a gate that judges each operation on its own always rewards the more generic
candidate. The stated fix is comparative ranking among candidates.

R117 built that ranking out of the alias corpus, weighting terms by how few
operations they attach to. It reversed the inversion on the failing cases and
then refused three of six plainly correct requests, so it was rejected, and the
register concluded the alias corpus does not carry the signal.

This measures the one comparative instrument that does not come from the alias
corpus: ``_select_single_effect_operation``, the closed-catalog selector that
already exists and already recovers actions from zero-tool conversation turns.
It is comparative by construction -- every catalogue operation competes in one
call, and the empty string is a first-class answer -- and it reads the
authenticated descriptions rather than any corpus of surface forms.

The question priced here is narrow and falsifiable: **if an action or plan the
deterministic recogniser did not prove had to agree with an independent
comparative selection, what would it stop and what would it break?**

Development diagnostic over already-consumed populations. It executes no
operation, drives no turn, and promotes nothing: a claim needs a fresh sealed V6.
"""

from __future__ import annotations

import argparse
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
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)

from experiments.mind_router_spike.probe_native_tool_contract_ceiling import (  # noqa: E402
    _start_server,
    _stop_server,
)


DEFAULT_SOURCE = REPO / "artifacts/development/turn_kind_safety_boundary_20260812.json"
DEFAULT_OUTPUT = (
    REPO / "artifacts/development/comparative_selector_agreement_20260812.json"
)


# The selector's JSON-schema enum compiles to GBNF inside llama.cpp, and the
# whole 169-operation catalogue in one enum is rejected with HTTP 400 while 144
# is accepted. Production never meets that wall because it selects over a
# retrieval shortlist. A diagnostic that wants every operation in competition
# therefore runs a deterministic tournament: fixed contiguous chunks in
# catalogue publication order, then one final selection over the chunk winners.
# Chunking is by position, never by relevance, so nothing about the answer is
# decided by how the chunks were drawn.
_SELECTOR_CHUNK = 48


def _tournament_select(
    llm: Any,
    text: str,
    capabilities: list[dict[str, Any]],
) -> tuple[str | None, list[str], int]:
    """Select one operation with the entire catalogue in competition."""

    def _select(subset: list[dict[str, Any]]) -> str | None:
        names = [str(item["name"]) for item in subset]
        lines = "\n".join(
            f"{item['name']} | {str(item['description']).strip()}" for item in subset
        )
        return llm._select_single_effect_operation(text, names, lines)

    calls = 0
    winners: list[str] = []
    for start in range(0, len(capabilities), _SELECTOR_CHUNK):
        chunk = capabilities[start : start + _SELECTOR_CHUNK]
        calls += 1
        pick = _select(chunk)
        if pick:
            winners.append(pick)
    if not winners:
        return None, winners, calls
    if len(winners) == 1:
        return winners[0], winners, calls
    by_name = {str(item["name"]): item for item in capabilities}
    calls += 1
    return _select([by_name[name] for name in winners]), winners, calls


def _effect_rows(source: Path) -> list[dict[str, Any]]:
    report = json.loads(source.read_text(encoding="utf-8"))
    if report.get("schema") != "baxy.turn-kind-safety-boundary.v1":
        raise ValueError("source is not the turn-kind boundary diagnostic")
    rows = []
    for row in report["rows"]:
        if not row["effect_operations"]:
            continue
        row["is_leak"] = row["role"] == "request"
        rows.append(row)
    return rows


def run(source: Path, output: Path) -> dict[str, Any]:
    from baxy_mind.llm import LlmRuntime

    rows = _effect_rows(source)
    capabilities, _, _ = current_core_catalog_snapshot(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    # The whole authenticated catalogue competes, not a retrieval shortlist.
    # That is the adversarial form of the question: if the selector still agrees
    # with every operation present, a shortlist can only make it easier.
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
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
    measured: list[dict[str, Any]] = []
    try:
        for index, row in enumerate(rows, start=1):
            error = ""
            selected: str | None = None
            winners: list[str] = []
            calls = 0
            started = time.perf_counter()
            llm.begin_request(180.0, attempt=1)
            try:
                selected, winners, calls = _tournament_select(
                    llm,
                    row["request_text"],
                    capabilities,
                )
            except Exception as exc:  # noqa: BLE001 - measurement boundary
                error = f"{type(exc).__name__}: {exc}"[:300]
            finally:
                llm.end_request()
            proposed = list(row["effect_operations"])
            measured.append(
                {
                    **{
                        key: row[key]
                        for key in (
                            "population",
                            "case_id",
                            "role",
                            "request_text",
                            "kind",
                            "effect_operations",
                            "resolved",
                            "is_leak",
                        )
                    },
                    "compound": len(proposed) > 1,
                    "selected": selected,
                    "chunk_winners": winners,
                    "selector_calls": calls,
                    "abstained": selected is None or selected == "",
                    "agrees": bool(selected) and selected in proposed,
                    "seconds": round(time.perf_counter() - started, 6),
                    "error": error,
                }
            )
            print(
                f"[{index:02d}/{len(rows):02d}] {row['case_id']} "
                f"leak={row['is_leak']} proposed={proposed} "
                f"selected={selected!r} agrees={measured[-1]['agrees']}",
                flush=True,
            )
    finally:
        llm.close()
        _stop_server(process)

    report = {
        "schema": "baxy.comparative-selector-agreement.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "authority": (
            "development diagnostic over consumed populations; executes nothing "
            "and promotes nothing. A claim requires a fresh sealed V6."
        ),
        "effects_executed": 0,
        "catalogue_operations": len(capabilities),
        "selector_chunk": _SELECTOR_CHUNK,
        "source": str(source.resolve()),
        "summary": _summarise(measured),
        "rows": measured,
    }
    write_json_atomic(output, report)
    return report


def _summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Score only where a single-effect selector is the right instrument.

    A compound mission asks for three or four atomic effects; a selector built
    to name one of them cannot be scored as agreeing or disagreeing with the
    whole list, so those rows are reported separately rather than folded into a
    rate that would flatter or damn the instrument by construction.
    """

    single = [row for row in rows if not row["compound"]]
    compound = [row for row in rows if row["compound"]]
    leaks = [row for row in single if row["is_leak"]]
    legitimate = [row for row in single if not row["is_leak"]]
    latencies = [row["seconds"] for row in rows if not row["error"]]
    return {
        "rows": len(rows),
        "single_effect_rows": len(single),
        "leaks": {
            "total": len(leaks),
            "stopped": sum(1 for row in leaks if not row["agrees"]),
            "detail": [
                {
                    "case_id": row["case_id"],
                    "request_text": row["request_text"],
                    "proposed": row["effect_operations"],
                    "selected": row["selected"],
                    "stopped": not row["agrees"],
                }
                for row in leaks
            ],
        },
        "legitimate_single_effect": {
            "total": len(legitimate),
            "agreed": sum(1 for row in legitimate if row["agrees"]),
            "broken": [
                {
                    "population": row["population"],
                    "case_id": row["case_id"],
                    "request_text": row["request_text"],
                    "proposed": row["effect_operations"],
                    "selected": row["selected"],
                }
                for row in legitimate
                if not row["agrees"]
            ],
        },
        "compound_missions_not_scored": [
            {
                "case_id": row["case_id"],
                "proposed": row["effect_operations"],
                "selected": row["selected"],
            }
            for row in compound
        ],
        "seconds_p50": round(statistics.median(latencies), 6) if latencies else None,
        "errors": sum(1 for row in rows if row["error"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(args.source, args.output)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
