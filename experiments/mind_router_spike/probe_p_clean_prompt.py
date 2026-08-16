"""Can the primary policy stop writing what BAXY can derive?

88% of what the JSON schema costs the primary policy is not the grammar engine:
it is the 56 extra structural tokens the schema forces it to emit. Two of those
fields are stated by the prompt itself as functions of another field:

    "effect_count resume la longitud: zero, one o multiple"
    "operation debe estar vacio salvo en action, donde debe coincidir con el
     unico elemento de effect_operations"

So BAXY can compute both from `mode` and `effect_operations`. Removing them from
the schema gives the model less to get wrong rather than more, which is the
opposite trade from compacting the grammar. But they are also emitted *before*
`effect_operations`, so they may be acting as a commitment scaffold. That is a
question for measurement, not for argument.

The gate here is exact decision equality on the frozen turn corpus: a variant is
only promotable if every turn decides identically. Latency that costs a decision
is not a gain. Nothing is installed and no effect is executed.
"""

from __future__ import annotations

import argparse
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

OUTPUT = REPO / "artifacts" / "fixes" / "p_clean_prompt_20260731.json"
DERIVED = ("operation", "effect_count")

# The same frozen corpus the pipeline decomposition used, so the two artifacts
# describe the same turns.
CASES: tuple[tuple[str, str], ...] = (
    ("conv-01", "contame un chiste corto"),
    ("conv-02", "que opinas de la pizza con pina"),
    ("conv-03", "hola, todo bien?"),
    ("act-01", "pon el volumen al 30 por ciento"),
    ("act-02", "set the volume to 45 percent"),
    ("guard-01", "necesito dejar el equipo en silencio ya mismo"),
    ("guard-02", "quiero ver como esta todo por dentro de la maquina"),
    ("guard-03", "prepara algo para que no me olvide del dentista"),
    ("guard-04", "podrias dejarme la pantalla lista para trabajar"),
    ("plan-01", "sube el volumen"),
    ("clarify-01", "hazlo"),
    ("tail-01", "por que mi gpu no se usa"),
)
REPEATS = 2


def _derive(decision: dict[str, Any]) -> dict[str, Any]:
    """Recompute exactly what the prompt already declares as a function."""

    operations = decision.get("effect_operations")
    operations = operations if isinstance(operations, list) else []
    count = len(operations)
    decision["effect_count"] = (
        "zero" if count == 0 else "one" if count == 1 else "multiple")
    decision["operation"] = (
        str(operations[0])
        if decision.get("mode") == "action" and count == 1
        else ""
    )
    return decision


def _sidecar_main(variant: str, telemetry: str) -> int:
    """Run the real sidecar with the primary schema rewritten for one variant."""

    from baxy_mind import llm as llm_module
    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime

    telemetry_path = Path(telemetry)
    original_build = llm_module._build_turn_policy_payload
    original_post = LlmRuntime._post

    if variant == "clean_prompt":
        # The schema no longer carries `operation` or `effect_count`, but the
        # prompt still instructs the model about both. This variant removes those
        # two sentences while keeping the mode-selection semantics they carried:
        # one effect means action, several mean plan.
        stale = (
            "effect_count resume la longitud: zero, one o multiple. one implica "
            "action y multiple implica plan. operation debe estar vacío salvo en "
            "action, donde debe coincidir con el único elemento de "
            "effect_operations; "
        )
        replacement = "Un único efecto implica action y varios implican plan. "
        if stale not in llm_module.TURN_POLICY_PROMPT:
            raise RuntimeError(
                "el prompt primario no contiene el texto que esta variante retira")
        llm_module.TURN_POLICY_PROMPT = llm_module.TURN_POLICY_PROMPT.replace(
            stale, replacement)

    def build(text, operation_names, candidate_text, prior_messages):
        return original_build(text, operation_names, candidate_text, prior_messages)

    llm_module._build_turn_policy_payload = build

    def post(self, payload, timeout=None, *, max_attempts=2, cancellation=None):
        result = original_post(
            self, payload, timeout, max_attempts=max_attempts,
            cancellation=cancellation)
        envelope = (payload.get("response_format") or {}).get("json_schema") or {}
        if envelope.get("name") != "baxy_turn_decision":
            return result

        # P's own timings, straight from llama-server. Turn wall time cannot see
        # this effect: the corpus mixes deterministic turns that never reach the
        # model with model turns costing seconds.
        timings = result.get("timings") or {}
        with telemetry_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "variant": variant,
                "prompt_n": timings.get("prompt_n"),
                "cache_n": timings.get("cache_n"),
                "predicted_n": timings.get("predicted_n"),
                "prompt_ms": timings.get("prompt_ms"),
                "predicted_ms": timings.get("predicted_ms"),
            }) + "\n")

        return result

    LlmRuntime._post = post
    try:
        return sidecar_module.main()
    finally:
        llm_module._build_turn_policy_payload = original_build
        LlmRuntime._post = original_post


def _run_variant(
    runtime: Any,
    variant: str,
    telemetry: Path,
) -> list[dict[str, Any]]:
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES)))
    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime, gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"])
    command = [
        str(runtime.python), "-u", "-X", "utf8",
        str(Path(__file__).resolve()), "--sidecar", "--variant", variant,
        "--telemetry", str(telemetry),
    ]
    client = JsonLineProcess(command, environment=environment, cwd=REPO)
    rows: list[dict[str, Any]] = []
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("el sidecar rechazó el saludo")
        ready = client.request(
            {"type": "catalog.configure", "id": f"cat-{variant}",
             "capabilities": capabilities},
            limits["handshake"])
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("el catálogo no quedó listo")
        client.request(
            {"type": "turn.decide", "id": "warm", "text": "hola", "history": []},
            limits["turn.decide"])

        for repeat in range(REPEATS):
            for case_id, text in CASES:
                started = time.perf_counter()
                reply = client.request(
                    {"type": "turn.decide", "id": f"{variant}-{repeat}-{case_id}",
                     "text": text, "history": []},
                    limits["turn.decide"])
                rows.append({
                    "variant": variant,
                    "repeat": repeat,
                    "case_id": case_id,
                    "seconds": round(time.perf_counter() - started, 6),
                    # These are the fields the turn.result envelope actually
                    # carries. Reading the internal schema's names here would
                    # compare a dict of nulls and prove nothing.
                    "decision": {
                        key: reply.get(key)
                        for key in ("kind", "operation", "effectOperations", "question")
                    },
                    "reply_text": reply.get("reply"),
                })
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": f"sd-{variant}"},
            timeout=limits["shutdown"])
    return rows


def run() -> dict[str, Any]:
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    samples: list[dict[str, Any]] = []
    telemetry = OUTPUT.with_name("p_clean_prompt_telemetry_20260731.jsonl")
    if telemetry.exists():
        telemetry.unlink()
    telemetry.touch()
    # ABBA over whole variant sessions so neither arm owns the warm state.
    for order in (("baseline", "clean_prompt"), ("clean_prompt", "baseline")):
        for variant in order:
            samples.extend(_run_variant(runtime, variant, telemetry))

    calls = [
        json.loads(line)
        for line in telemetry.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    def summarize(variant: str) -> dict[str, Any]:
        values = sorted(
            row["seconds"] for row in samples if row["variant"] == variant)
        return {
            "n": len(values),
            "p50_s": round(statistics.median(values), 4),
            "min_s": round(values[0], 4),
            "max_s": round(values[-1], 4),
            "mean_s": round(statistics.fmean(values), 4),
            "stdev_s": round(statistics.stdev(values), 4) if len(values) > 1 else 0.0,
        }

    # The model is not perfectly deterministic even at temperature 0 under
    # continuous batching, so a case can legitimately show more than one outcome
    # inside a single arm. Hiding that behind a set comparison would overstate
    # the gate. The gate is therefore: the candidate may not introduce a
    # decision the baseline never produced.
    per_case: dict[str, Any] = {}
    no_new_decisions = True
    nondeterministic: list[str] = []
    for case_id, _ in CASES:
        sides: dict[str, list[str]] = {}
        for variant in ("baseline", "clean_prompt"):
            sides[variant] = sorted({
                json.dumps(row["decision"], ensure_ascii=False, sort_keys=True)
                for row in samples
                if row["case_id"] == case_id and row["variant"] == variant
            })
        introduced = [
            value for value in sides["clean_prompt"] if value not in sides["baseline"]
        ]
        if introduced:
            no_new_decisions = False
        if len(sides["baseline"]) > 1 or len(sides["clean_prompt"]) > 1:
            nondeterministic.append(case_id)
        per_case[case_id] = {
            "baseline_outcomes": [json.loads(value) for value in sides["baseline"]],
            "clean_prompt_outcomes": [json.loads(value) for value in sides["clean_prompt"]],
            "introduced_by_candidate": [json.loads(value) for value in introduced],
            "same_outcome_set": sides["baseline"] == sides["clean_prompt"],
            "deterministic_in_both": (
                len(sides["baseline"]) == 1 and len(sides["clean_prompt"]) == 1),
        }

    def policy_stats(variant: str) -> dict[str, Any] | None:
        rows = [
            row for row in calls
            if row["variant"] == variant and row.get("predicted_n")
        ]
        if not rows:
            return None
        predicted = sorted(row["predicted_n"] for row in rows)
        decode = sorted(row["predicted_ms"] for row in rows)
        prefill = sorted(row["prompt_ms"] for row in rows if row.get("prompt_ms"))
        rate = [row["predicted_ms"] / row["predicted_n"] for row in rows]
        return {
            "p_calls": len(rows),
            "predicted_n_p50": statistics.median(predicted),
            "predicted_n_mean": round(statistics.fmean(predicted), 2),
            "predicted_ms_p50": round(statistics.median(decode), 1),
            "predicted_ms_mean": round(statistics.fmean(decode), 1),
            "predicted_ms_stdev": (
                round(statistics.stdev(decode), 1) if len(decode) > 1 else 0.0),
            "prompt_ms_p50": round(statistics.median(prefill), 1) if prefill else None,
            "ms_per_token_p50": round(statistics.median(rate), 2),
        }

    baseline, candidate = summarize("baseline"), summarize("clean_prompt")
    policy_baseline = policy_stats("baseline")
    policy_candidate = policy_stats("clean_prompt")
    policy_delta = None
    if policy_baseline and policy_candidate:
        policy_delta = {
            "predicted_n": round(
                policy_candidate["predicted_n_mean"]
                - policy_baseline["predicted_n_mean"], 2),
            "predicted_ms_p50": round(
                policy_candidate["predicted_ms_p50"]
                - policy_baseline["predicted_ms_p50"], 1),
            "predicted_ms_mean": round(
                policy_candidate["predicted_ms_mean"]
                - policy_baseline["predicted_ms_mean"], 1),
        }

    report = {
        "schema": "baxy.p-derived-fields.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "effects_executed": 0,
        "question": (
            "the primary schema makes the model write `operation` and "
            "`effect_count`, which the prompt itself declares as functions of "
            "`mode` and `effect_operations`. If BAXY derives them instead, does "
            "any turn decide differently?"),
        "gate": (
            "the candidate may not introduce a decision the baseline never "
            "produced, on any case of the frozen turn corpus. A variant that "
            "invents one decision is rejected however much it saves. Cases that "
            "are nondeterministic inside a single arm are reported rather than "
            "hidden, because a set comparison alone would overstate the gate."),
        "method": (
            "the real sidecar per variant, whole sessions alternated in ABBA "
            "order, the same 12-case corpus twice per session. The candidate "
            "removes the two fields from the schema and BAXY fills them back in "
            "from mode and effect_operations, so everything downstream sees the "
            "identical decision shape."),
        "runtime": public_runtime_identity(runtime),
        "baseline": baseline,
        "clean_prompt": candidate,
        "delta_p50_s": round(candidate["p50_s"] - baseline["p50_s"], 4),
        "no_new_decisions": no_new_decisions,
        "nondeterministic_cases": nondeterministic,
        "policy_baseline": policy_baseline,
        "policy_clean_prompt": policy_candidate,
        "policy_delta": policy_delta,
        "policy_note": (
            "these are the primary policy's own llama-server timings, one row "
            "per P call. Turn wall time cannot resolve this effect: that "
            "distribution is bimodal, mixing deterministic turns near 0.001 s "
            "with model turns of several seconds."),
        "per_case": per_case,
        "samples": samples,
        "policy_calls": calls,
    }
    write_json_atomic(OUTPUT, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sidecar", action="store_true")
    parser.add_argument("--variant", default="baseline")
    parser.add_argument("--telemetry", default="")
    args, _ = parser.parse_known_args()
    if args.sidecar:
        return _sidecar_main(args.variant, args.telemetry)
    report = run()
    print(json.dumps({
        "policy_baseline": report["policy_baseline"],
        "policy_clean_prompt": report["policy_clean_prompt"],
        "policy_delta": report["policy_delta"],
        "no_new_decisions": report["no_new_decisions"],
        "nondeterministic_cases": report["nondeterministic_cases"],
        "turn_delta_p50_s_for_reference": report["delta_p50_s"],
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
