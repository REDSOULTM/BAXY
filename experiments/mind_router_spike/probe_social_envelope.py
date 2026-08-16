"""Can BAXY stop sending a pure social act to the primary policy?

Fifteen of the thirty frozen workload turns already avoid the model, and that is
why `decision_ms` has a 21.9 ms median. Every turn removed from P is worth more
than any micro-optimisation of its schema, so the question is which families are
still crossing it for nothing.

Two mechanically linked gaps were measured in the deterministic recogniser:

  A. A whole utterance that is nothing but a social act -- `hola`, `buenas
     tardes`, `nos vemos`, `perfecto gracias`, `hi, how are you?` -- costs a full
     P decode. Only bare gratitude was recognised.

  B. A leading social act blocked an otherwise recognisable request, unless the
     greeting happened to be exactly `hola baxy`. `hola baxy, cuanta bateria
     queda` resolved; `hola, cuanta bateria queda` did not.

Both are the same claim: the social envelope is not part of the request. The
candidate makes that claim uniform through three closed vocabularies consumed
with `re.fullmatch` (or anchored at both ends, for a clause), so any added clause
stops matching and returns the turn to the model.

The gate is exact decision equality on the frozen corpus: a variant is only
promotable if it introduces no decision the baseline never produced. Latency that
costs a decision is not a gain. The variant is verified to have taken effect by
counting P calls per case, not by observing that it ran. Nothing is installed and
no effect is executed.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
import unicodedata
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

OUTPUT = REPO / "artifacts" / "fixes" / "social_envelope_20260731.json"
VARIANTS = ("baseline", "social_envelope")

# Every text below is drawn from the frozen historical corpus or from the frozen
# 30-turn budget workload. `family` records what the case is here to prove.
CASES: tuple[tuple[str, str, str], ...] = (
    # A: the whole utterance is a social act. The candidate answers these
    # without P; the baseline pays a full decode for each one.
    ("social-01", "hola", "whole-social"),
    ("social-02", "buenas tardes", "whole-social"),
    ("social-03", "hola, todo bien?", "whole-social"),
    ("social-04", "hi, how are you?", "whole-social"),
    ("social-05", "perfecto gracias", "whole-social"),
    ("social-06", "nos vemos", "whole-social"),
    ("social-07", "hello there", "whole-social"),
    # B: a leading social act in front of a request the recogniser already owns.
    ("prefix-01", "hola, dime que hora es", "social-prefix"),
    ("prefix-02", "hello, what time is it?", "social-prefix"),
    ("prefix-03", "buenos dias, cuanta bateria queda", "social-prefix"),
    ("prefix-04", "hola, pon el volumen al 30 por ciento", "social-prefix"),
    # Adversarial: social-shaped but carrying something else. These must reach
    # the model in BOTH arms, and the candidate must not swallow them.
    ("adv-01", "escribe hola", "adversarial"),
    ("adv-02", "hola, quien sos?", "adversarial"),
    ("adv-03", "gracias capo", "adversarial"),
    ("adv-04", "mandale hola a lucas por whatsapp", "adversarial"),
    # Continuity with the frozen turn corpus of the previous probes, so the two
    # artifacts describe overlapping turns.
    ("conv-01", "contame un chiste corto", "frozen"),
    ("guard-01", "necesito dejar el equipo en silencio ya mismo", "frozen"),
    ("guard-04", "podrias dejarme la pantalla lista para trabajar", "frozen"),
    ("plan-01", "sube el volumen", "frozen"),
    ("tail-01", "por que mi gpu no se usa", "frozen"),
)
REPEATS = 2

# The exact gratitude-only pattern the candidate replaces. The baseline arm
# restores it so both arms run the same product code with one behaviour swapped.
_BASELINE_GRATITUDE = (
    r"[¿?¡!\s]*(?:muchas gracias|mil gracias|"
    r"gracias(?: por (?:todo|tu ayuda|la ayuda))?|"
    r"thanks(?: a lot| so much)?|"
    r"thank you(?: very much| so much)?|"
    r"te lo agradezco)[\s?!.]*"
)
_BASELINE_REQUEST_PREFIX = (
    r"(?:(?:por favor|please)\s*[,;:]?\s*|"
    r"(?:puedes|podrias|can you|could you|would you)\s+|"
    r"(?:(?:che|oye|oiga|hey|ey|ok|okay|hola|escucha|listen)\s+)?"
    r"baxy\s*[,;:]?\s*)?"
)
_BASELINE_SOCIAL_CLAUSE = (
    r"^[¿?¡!\s]*(?:gracias|thanks|thank you|por favor|please|"
    r"que tengas (?:un )?buen dia)\b|"
    r"^[¿?¡!\s]*(?:(?:che|oye|oiga|hey|ey|ok|okay|hola|escucha|"
    r"listen)\s+)?baxy[\s?!.,;:]*$"
)


def _install_baseline(sidecar_module: Any, effect_intent: Any) -> None:
    """Restore exactly the three behaviours the candidate widens."""

    def baseline_social(objective: str, history: object = None):
        folded = unicodedata.normalize("NFKD", objective.casefold())
        folded = "".join(
            character
            for character in folded
            if not unicodedata.combining(character)
        )
        folded = " ".join(folded.split())
        if re.fullmatch(_BASELINE_GRATITUDE, folded, re.IGNORECASE) is None:
            return None
        return {
            "mode": "conversation",
            "operation": None,
            "question": "",
            "conversation_kind": "social",
            "effect_count": "zero",
            "effect_operations": [],
            "effect_verification": "not_applicable",
            "response_language": sidecar_module._explicit_response_language(
                objective),
        }

    def baseline_social_clause(text: str) -> bool:
        return effect_intent._has(text, _BASELINE_SOCIAL_CLAUSE)

    sidecar_module._explicit_social_turn_decision = baseline_social
    effect_intent._is_social_clause = baseline_social_clause
    # `_request_head` and `_is_direct_request` interpolate this global at call
    # time, so rebinding it is enough to restore the narrower speech-act gate.
    effect_intent._REQUEST_PREFIX = _BASELINE_REQUEST_PREFIX


def _sidecar_main(variant: str, telemetry: str) -> int:
    """Run the real sidecar with one behaviour swapped, and trace P per case."""

    from baxy_mind import effect_intent
    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime

    telemetry_path = Path(telemetry)
    if variant == "baseline":
        _install_baseline(sidecar_module, effect_intent)

    # Attribution by request identity, never by temporal proximity: the turn id
    # is stamped before the decision and read by the POST hook.
    current: dict[str, str] = {"id": ""}
    original_prepare = sidecar_module._prepare_turn_result

    def prepare(message, **kwargs):
        current["id"] = str(message.get("id") or "")
        return original_prepare(message, **kwargs)

    sidecar_module._prepare_turn_result = prepare

    original_post = LlmRuntime._post

    def post(self, payload, timeout=None, *, max_attempts=2, cancellation=None):
        result = original_post(
            self, payload, timeout, max_attempts=max_attempts,
            cancellation=cancellation)
        envelope = (payload.get("response_format") or {}).get("json_schema") or {}
        if envelope.get("name") != "baxy_turn_decision":
            return result

        # P's own timings, straight from llama-server. Turn wall time cannot see
        # this effect: the corpus mixes deterministic turns near 0.001 s with
        # model turns costing seconds.
        timings = result.get("timings") or {}
        with telemetry_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "variant": variant,
                "turn_id": current["id"],
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
        sidecar_module._prepare_turn_result = original_prepare
        LlmRuntime._post = original_post


def _run_variant(runtime: Any, variant: str, telemetry: Path) -> list[dict[str, Any]]:
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
            {"type": "turn.decide", "id": "warm", "text": "hola mundo digital",
             "history": []},
            limits["turn.decide"])

        for repeat in range(REPEATS):
            for case_id, text, family in CASES:
                turn_id = f"{variant}-{repeat}-{case_id}"
                started = time.perf_counter()
                reply = client.request(
                    {"type": "turn.decide", "id": turn_id,
                     "text": text, "history": []},
                    limits["turn.decide"])
                rows.append({
                    "variant": variant,
                    "repeat": repeat,
                    "case_id": case_id,
                    "family": family,
                    "turn_id": turn_id,
                    "seconds": round(time.perf_counter() - started, 6),
                    # These are the fields the turn.result envelope carries.
                    "decision": {
                        key: reply.get(key)
                        for key in ("kind", "operation", "effectOperations",
                                    "question")
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
    telemetry = OUTPUT.with_name("social_envelope_telemetry_20260731.jsonl")
    if telemetry.exists():
        telemetry.unlink()
    telemetry.touch()
    # ABBA over whole variant sessions so neither arm owns the warm state.
    for order in (VARIANTS, tuple(reversed(VARIANTS))):
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
    for case_id, text, family in CASES:
        sides: dict[str, list[str]] = {}
        for variant in VARIANTS:
            sides[variant] = sorted({
                json.dumps(row["decision"], ensure_ascii=False, sort_keys=True)
                for row in samples
                if row["case_id"] == case_id and row["variant"] == variant
            })
        introduced = [
            value for value in sides["social_envelope"]
            if value not in sides["baseline"]
        ]
        if introduced:
            no_new_decisions = False
        if len(sides["baseline"]) > 1 or len(sides["social_envelope"]) > 1:
            nondeterministic.append(case_id)
        # Direct proof the variant took effect: P calls attributed to this case
        # by request identity.
        policy_calls = {
            variant: sum(
                1 for row in calls
                if row.get("turn_id", "").startswith(f"{variant}-")
                and row.get("turn_id", "").endswith(f"-{case_id}")
            )
            for variant in VARIANTS
        }
        per_case[case_id] = {
            "text": text,
            "family": family,
            "baseline_outcomes": [json.loads(value) for value in sides["baseline"]],
            "social_envelope_outcomes": [
                json.loads(value) for value in sides["social_envelope"]],
            "introduced_by_candidate": [json.loads(value) for value in introduced],
            "same_outcome_set": sides["baseline"] == sides["social_envelope"],
            "deterministic_in_both": (
                len(sides["baseline"]) == 1
                and len(sides["social_envelope"]) == 1),
            "policy_calls": policy_calls,
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
            "predicted_ms_total": round(sum(decode), 1),
            "prompt_ms_p50": round(statistics.median(prefill), 1) if prefill else None,
            "prompt_ms_total": round(sum(prefill), 1) if prefill else None,
            "ms_per_token_p50": round(statistics.median(rate), 2),
        }

    baseline, candidate = summarize("baseline"), summarize("social_envelope")
    policy_baseline = policy_stats("baseline")
    policy_candidate = policy_stats("social_envelope")
    policy_delta = None
    if policy_baseline and policy_candidate:
        policy_delta = {
            "p_calls": policy_candidate["p_calls"] - policy_baseline["p_calls"],
            "predicted_ms_total": round(
                policy_candidate["predicted_ms_total"]
                - policy_baseline["predicted_ms_total"], 1),
            "prompt_ms_total": round(
                (policy_candidate["prompt_ms_total"] or 0.0)
                - (policy_baseline["prompt_ms_total"] or 0.0), 1),
            "ms_per_token_p50": round(
                policy_candidate["ms_per_token_p50"]
                - policy_baseline["ms_per_token_p50"], 2),
        }

    families: dict[str, Any] = {}
    for _, _, family in CASES:
        if family in families:
            continue
        members = [case for case, _, member in CASES if member == family]
        families[family] = {
            "cases": members,
            "policy_calls": {
                variant: sum(
                    per_case[case]["policy_calls"][variant] for case in members)
                for variant in VARIANTS
            },
            "p50_s": {
                variant: round(statistics.median(sorted(
                    row["seconds"] for row in samples
                    if row["variant"] == variant and row["case_id"] in members
                )), 4)
                for variant in VARIANTS
            },
        }

    report = {
        "schema": "baxy.social-envelope.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "effects_executed": 0,
        "question": (
            "a turn whose whole text is a social act, and a turn whose request "
            "is merely preceded by one, both cross the primary policy today. If "
            "the deterministic recogniser owns the social envelope instead, does "
            "any turn decide differently?"),
        "gate": (
            "the candidate may not introduce a decision the baseline never "
            "produced, on any case of the frozen corpus. A variant that invents "
            "one decision is rejected however much it saves. Cases that are "
            "nondeterministic inside a single arm are reported rather than "
            "hidden, because a set comparison alone would overstate the gate."),
        "method": (
            "the real sidecar per variant, whole sessions alternated in ABBA "
            "order, the same corpus twice per session. The baseline arm restores "
            "the gratitude-only social pattern, the narrower request prefix and "
            "the narrower social-clause gate inside the same product code, so "
            "the two arms differ only in that one behaviour. P calls are "
            "attributed to a case by request identity, never by proximity."),
        "runtime": public_runtime_identity(runtime),
        "baseline": baseline,
        "social_envelope": candidate,
        "delta_p50_s": round(candidate["p50_s"] - baseline["p50_s"], 4),
        "no_new_decisions": no_new_decisions,
        "nondeterministic_cases": nondeterministic,
        "policy_baseline": policy_baseline,
        "policy_social_envelope": policy_candidate,
        "policy_delta": policy_delta,
        "by_family": families,
        "policy_note": (
            "these are the primary policy's own llama-server timings, one row "
            "per P call, attributed to a turn by its request id. The headline "
            "here is p_calls: a turn the candidate never sends to P has no row "
            "at all, which is the direct proof the variant took effect."),
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
        "policy_social_envelope": report["policy_social_envelope"],
        "policy_delta": report["policy_delta"],
        "by_family": report["by_family"],
        "no_new_decisions": report["no_new_decisions"],
        "nondeterministic_cases": report["nondeterministic_cases"],
        "turn_delta_p50_s_for_reference": report["delta_p50_s"],
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
