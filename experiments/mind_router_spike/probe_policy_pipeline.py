"""Per-component trace of the real turn policy pipeline, correlated by identity.

Every POST records the request identity that ``LlmRuntime.begin_request``
published for the turn that originated it, so a call is attributed to a turn
because the runtime says so, not because it happened to land inside a
wall-clock window. That distinction matters: the sidecar overlaps speculative
work, retires cancelled work and warms up in the background, so window overlap
attributes the same seconds to several turns at once and to turns that never
called the model at all.

Calls whose identity does not match any measured turn are reported separately
as background or orphan work instead of being folded into a turn.

No Core operation is dispatched and no registered asset changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_capabilities,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)

DEFAULT_OUTPUT = REPO / "artifacts" / "fixes" / "policy_pipeline_20260731.json"

# Componentes del planificador, por nombre de schema. La gramática de idioma no
# lleva nombre y se identifica por su digest.
COMPONENT_BY_SCHEMA = {
    "baxy_turn_decision": "P primary policy",
    "baxy_semantic_effect_guard": "G semantic guard",
    "baxy_effect_count_verification": "V count verification",
    "baxy_operation_compatibility": "C compatibility",
    "baxy_single_effect_selector": "S single effect selector",
    "baxy_turn_failure_clarification": "clarify generation",
    "baxy_plan_skeleton": "plan skeleton",
    "baxy_refined_plan_skeleton": "plan refinement",
}

# Corpus estable: conversación, acción, plan, clarify, colas conocidas y casos
# construidos para que el guard semántico sí participe.
CASES: tuple[tuple[str, str, str], ...] = (
    ("conv-01", "conversation", "contame un chiste corto"),
    ("conv-02", "conversation", "que opinas de la pizza con pina"),
    ("conv-03", "conversation", "hola, todo bien?"),
    ("act-01", "action", "pon el volumen al 30 por ciento"),
    ("act-02", "action", "set the volume to 45 percent"),
    # G se agenda siempre junto a P, así que basta con que el turno llegue al
    # modelo. Estos textos tienen forma de efecto pero el reconocedor
    # determinista no los resuelve, de modo que el guard participa de verdad.
    ("guard-01", "guard", "necesito dejar el equipo en silencio ya mismo"),
    ("guard-02", "guard", "quiero ver como esta todo por dentro de la maquina"),
    ("guard-03", "guard", "prepara algo para que no me olvide del dentista"),
    ("guard-04", "guard", "podrias dejarme la pantalla lista para trabajar"),
    ("plan-01", "plan", "sube el volumen"),
    ("clarify-01", "clarify", "hazlo"),
    ("tail-01", "tail", "por que mi gpu no se usa"),
)


def _schema_name(payload: dict[str, Any]) -> str | None:
    response_format = payload.get("response_format")
    if isinstance(response_format, dict):
        envelope = response_format.get("json_schema")
        if isinstance(envelope, dict):
            name = envelope.get("name")
            if isinstance(name, str) and name:
                return name
    return None


def _component(payload: dict[str, Any]) -> str:
    name = _schema_name(payload)
    if name is not None:
        return COMPONENT_BY_SCHEMA.get(name, name)
    grammar = payload.get("grammar")
    if isinstance(grammar, str) and grammar:
        # El guard se envía compactado a GBNF: `_compact_structured_grammar`
        # elimina su `response_format` en la copia de wire, así que sobre el
        # cable G y L se parecen. Sólo la gramática de idioma es literalmente
        # `_RESPONSE_LANGUAGE_GRAMMAR`; cualquier otra gramática compactada es
        # el guard. Confundirlos hace desaparecer G de la medición.
        from baxy_mind.llm import _RESPONSE_LANGUAGE_GRAMMAR

        if grammar == _RESPONSE_LANGUAGE_GRAMMAR:
            return "L language grammar"
        return "G semantic guard"
    return "chat / knowledge reply"


def _run_trace_sidecar(trace_path: Path) -> int:
    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime

    original_post = LlmRuntime._post

    def tracing_post(
        self: LlmRuntime,
        payload: dict[str, Any],
        timeout: float | None = None,
        *,
        max_attempts: int = 2,
        cancellation: Any = None,
    ) -> dict[str, Any]:
        identity = getattr(self, "_request_identity", "")
        attempt = int(getattr(self, "_request_attempt", 0))
        component = _component(payload)
        messages = json.dumps(
            payload.get("messages"), ensure_ascii=False, sort_keys=True)
        started = time.perf_counter()
        error = ""
        result: dict[str, Any] = {}
        try:
            result = original_post(
                self,
                payload,
                timeout,
                max_attempts=max_attempts,
                cancellation=cancellation,
            )
            return result
        except BaseException as failure:  # noqa: BLE001 - re-raised below
            error = type(failure).__name__
            raise
        finally:
            elapsed = time.perf_counter() - started
            timings = {}
            choices = result.get("choices") if isinstance(result, dict) else None
            finish_reason = ""
            content_chars = 0
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict):
                    finish_reason = str(first.get("finish_reason") or "")
                    message = first.get("message")
                    if isinstance(message, dict):
                        content = message.get("content")
                        content_chars = len(content) if isinstance(content, str) else 0
            if isinstance(result, dict):
                raw = result.get("timings")
                if isinstance(raw, dict):
                    timings = raw
            record = {
                "request_identity": identity,
                "component": component,
                "logical_attempt": attempt,
                "payload_sha256": hashlib.sha256(
                    messages.encode("utf-8")).hexdigest(),
                "payload_chars": len(messages),
                "prompt_tokens": timings.get("prompt_n"),
                "cached_tokens": timings.get("cache_n"),
                "predicted_tokens": timings.get("predicted_n"),
                "prompt_ms": timings.get("prompt_ms"),
                "predicted_ms": timings.get("predicted_ms"),
                "wall_seconds": round(elapsed, 6),
                "finish_reason": finish_reason,
                "content_chars": content_chars,
                "temperature": payload.get("temperature"),
                "seed": payload.get("seed"),
                "max_tokens": payload.get("max_tokens"),
                "error": error,
                "unix_start": time.time() - elapsed,
            }
            with trace_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    LlmRuntime._post = tracing_post  # type: ignore[method-assign]
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime._post = original_post  # type: ignore[method-assign]


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def stat(key: str) -> dict[str, Any] | None:
        values = [
            row[key] for row in rows
            if isinstance(row.get(key), (int, float))
        ]
        if not values:
            return None
        ordered = sorted(values)
        return {
            "n": len(ordered),
            "min": round(ordered[0], 3),
            "p50": round(statistics.median(ordered), 3),
            "max": round(ordered[-1], 3),
        }

    reasons: dict[str, int] = {}
    for row in rows:
        reasons[row["finish_reason"] or "none"] = (
            reasons.get(row["finish_reason"] or "none", 0) + 1)
    return {
        "calls": len(rows),
        "distinct_payloads": len({row["payload_sha256"] for row in rows}),
        "prompt_tokens": stat("prompt_tokens"),
        "cached_tokens": stat("cached_tokens"),
        "predicted_tokens": stat("predicted_tokens"),
        "prompt_ms": stat("prompt_ms"),
        "predicted_ms": stat("predicted_ms"),
        "wall_seconds": stat("wall_seconds"),
        "finish_reasons": reasons,
        "empty_content": sum(1 for row in rows if row["content_chars"] == 0),
        "retry_calls": sum(1 for row in rows if row["logical_attempt"] > 0),
        "errors": sum(1 for row in rows if row["error"]),
    }


def run(output: Path) -> dict[str, Any]:
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES)))
    limits = PROFILE_LIMITS["gpu"]
    trace_path = output.with_suffix(".trace.jsonl")
    if trace_path.exists():
        trace_path.unlink()
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    environment["BAXY_POLICY_TRACE"] = str(trace_path)
    command = [
        str(runtime.python), "-u", "-X", "utf8",
        str(Path(__file__).resolve()), "--sidecar-trace", str(trace_path),
    ]
    client = JsonLineProcess(command, environment=environment, cwd=REPO)
    turns: list[dict[str, Any]] = []
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar hello rejected")
        catalog = client.request(
            {
                "type": "catalog.configure",
                "id": "catalog-policy-pipeline",
                "capabilities": capabilities,
            },
            limits["handshake"],
        )
        if catalog.get("type") != "catalog.ready":
            raise RuntimeError("catalog handshake rejected")
        for case_id, family, text in CASES:
            started = time.perf_counter()
            reply = client.request(
                {
                    "type": "turn.decide",
                    "id": case_id,
                    "text": text,
                    "history": [],
                },
                limits["turn.decide"],
            )
            turns.append({
                "case_id": case_id,
                "family": family,
                "elapsed_seconds": round(time.perf_counter() - started, 4),
                "kind": reply.get("kind"),
                "operation": reply.get("operation"),
                "effect_operations": reply.get("effectOperations"),
                "turn_attempts": reply.get("turn_attempts"),
            })
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": "shutdown-policy"},
            timeout=limits["shutdown"],
        )

    records: list[dict[str, Any]] = []
    if trace_path.exists():
        with trace_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    records.append(json.loads(line))

    measured = {turn["case_id"] for turn in turns}
    consumed = [row for row in records if row["request_identity"] in measured]
    background = [
        row for row in records
        if row["request_identity"] not in measured
    ]
    by_turn: dict[str, list[dict[str, Any]]] = {name: [] for name in measured}
    for row in consumed:
        by_turn[row["request_identity"]].append(row)
    by_component: dict[str, list[dict[str, Any]]] = {}
    for row in consumed:
        by_component.setdefault(row["component"], []).append(row)

    for turn in turns:
        rows = by_turn.get(turn["case_id"], [])
        turn["wire_calls"] = len(rows)
        turn["sum_inference_seconds"] = round(
            sum(row["wall_seconds"] for row in rows), 4)
        # Con identidad real esta relación ya es interpretable: por encima de 1
        # significa trabajo solapado dentro del propio turno, nunca prestado.
        turn["overlap_ratio"] = (
            round(turn["sum_inference_seconds"] / turn["elapsed_seconds"], 2)
            if turn["elapsed_seconds"] > 0 else None)
        turn["components"] = sorted({row["component"] for row in rows})

    report = {
        "schema": "baxy.policy-pipeline.v2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "effects_executed": 0,
        "correlation": (
            "every POST carries the request identity that "
            "LlmRuntime.begin_request published for its turn. Calls are "
            "attributed by that identity, never by wall-clock proximity."
        ),
        "supersedes": (
            "pglvc_pipeline_20260731.json, whose window-based correlation "
            "attributed the same seconds to several turns and gave deterministic "
            "turns inferences they never made"
        ),
        "runtime": public_runtime_identity(runtime),
        "turns": turns,
        "per_component_consumed": {
            name: _summarize(rows) for name, rows in sorted(by_component.items())
        },
        "background_or_orphan": {
            "calls": len(background),
            "identities": sorted({row["request_identity"] for row in background}),
            "by_component": {
                name: sum(1 for row in background if row["component"] == name)
                for name in sorted({row["component"] for row in background})
            },
            "sum_seconds": round(
                sum(row["wall_seconds"] for row in background), 4),
        },
        "totals": {
            "trace_calls": len(records),
            "attributed_to_measured_turns": len(consumed),
            "background_or_orphan": len(background),
        },
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sidecar-trace", type=Path, default=None)
    args = parser.parse_args()
    if args.sidecar_trace is not None:
        return _run_trace_sidecar(args.sidecar_trace)
    report = run(args.output)
    print(json.dumps(report["totals"], indent=1))
    for name, summary in report["per_component_consumed"].items():
        print(f"{name:28} calls={summary['calls']:3} "
              f"prefill_p50={summary['prompt_ms']['p50'] if summary['prompt_ms'] else None} "
              f"decode_p50={summary['predicted_ms']['p50'] if summary['predicted_ms'] else None}")
    print("background/orphan:", report["background_or_orphan"]["calls"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
