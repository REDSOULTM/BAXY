"""When a turn does reach the model, how good is its tool calling?

Deterministic recognisers cannot cover every phrasing a person will use, so the
model has to carry the long tail. That makes one number worth having and
currently missing: given a request whose correct operation is known, how often
does the primary policy name it, and when it fails, HOW does it fail?

The oracle is free and already frozen. `tests/test_effect_intent.py` CASES pairs
each text with the operation the recogniser grants it, and those pairings are
regression-tested. In production those texts never reach the model, precisely
because the recogniser owns them. This probe suspends the recogniser for the
measurement only, so each text is decided by P exactly as an unrecognised
paraphrase of it would be.

This is a MEASUREMENT, not an A/B and not a change: one arm, product code, the
recogniser suspended only inside the probe's own sidecar. It reports accuracy,
the failure taxonomy and the retry cost per case, so the next change to the
policy can be aimed instead of guessed. No effect is executed and nothing is
installed.
"""

from __future__ import annotations

import argparse
import collections
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
TESTS = REPO / "tests"
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)

OUTPUT = REPO / "artifacts" / "fixes" / "policy_tool_quality_20260731.json"
REPEATS = 2


def _oracle() -> list[dict[str, Any]]:
    """The frozen text -> operations pairing, straight from the test corpus."""

    import test_effect_intent as frozen

    cases: list[dict[str, Any]] = []
    for index, (text, operations) in enumerate(frozen.CASES):
        if not operations:
            # An abstention has no single right answer for P; excluded so the
            # accuracy number means one thing only.
            continue
        cases.append({
            "case_id": f"tool-{index:02d}",
            "text": text,
            "expected_operations": list(operations),
            "expected_kind": "action" if len(operations) == 1 else "plan",
        })
    return cases


def _sidecar_main(telemetry: str, variant: str = "leading_band") -> int:
    """Suspend the deterministic recogniser so every text is decided by P."""

    from baxy_mind import effect_intent
    from baxy_mind import llm as llm_module
    from baxy_mind import planner as planner_module
    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime

    telemetry_path = Path(telemetry)

    if variant == "baseline":
        # The baseline is the state promoted earlier today: the catalog floor
        # is in place and the leading-family band is not, so this A/B isolates
        # the widened band alone rather than re-measuring the floor.
        planner_module.LEADING_FAMILIES = 0
    elif variant == "sibling_baseline":
        sidecar_module._application_reference_retrieval_families = (
            lambda *_args, **_kwargs: frozenset()
        )
        for operation in (
            "app.open",
            "audio.volume",
            "audio.volume.adjust",
            "media.play.exact",
            "media.play.query",
        ):
            llm_module._NATIVE_SELECTION_DESCRIPTION_SUFFIXES.pop(
                operation,
                None,
            )

    # The measurement's whole point: force the turn onto the model path.
    effect_intent.resolve_explicit_effects = lambda *a, **k: None
    effect_intent.resolve_explicit_clarification = lambda *a, **k: None
    sidecar_module.resolve_explicit_effects = lambda *a, **k: None
    sidecar_module.resolve_explicit_clarification = lambda *a, **k: None
    sidecar_module._explicit_social_turn_decision = lambda *a, **k: None

    current: dict[str, str] = {"id": ""}
    original_prepare = sidecar_module._prepare_turn_result

    def prepare(message, **kwargs):
        current["id"] = str(message.get("id") or "")
        return original_prepare(message, **kwargs)

    sidecar_module._prepare_turn_result = prepare

    # The schema's enum only admits shortlisted operations, so an operation E5
    # never retrieved is one P physically cannot name. Without this, a
    # retrieval failure is indistinguishable from a model failure.
    original_build = llm_module._build_turn_policy_payload
    shortlists: dict[str, list[str]] = {}

    def build(text, operation_names, candidate_text, prior_messages):
        shortlists[current["id"]] = list(operation_names or ())
        return original_build(text, operation_names, candidate_text, prior_messages)

    llm_module._build_turn_policy_payload = build
    original_post = LlmRuntime._post
    original_native_selection = LlmRuntime._post_native_tool_selection

    def native_selection(
        self, text, operation_names, contracts_by_operation, prior_messages,
    ):
        result = original_native_selection(
            self,
            text,
            operation_names,
            contracts_by_operation,
            prior_messages,
        )
        with telemetry_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "turn_id": current["id"],
                "raw_policy": {
                    "mode": result.get("mode"),
                    "effect_operations": result.get("effect_operations"),
                },
                "shortlist": list(operation_names or ()),
                "contract": "native_tools",
            }) + "\n")
        return result

    def post(self, payload, timeout=None, *, max_attempts=2, cancellation=None):
        result = original_post(
            self, payload, timeout, max_attempts=max_attempts,
            cancellation=cancellation)
        envelope = (payload.get("response_format") or {}).get("json_schema") or {}
        if envelope.get("name") != "baxy_turn_decision":
            return result
        timings = result.get("timings") or {}
        # P's RAW proposal, before every veto BAXY applies afterwards. Without
        # this the measurement cannot tell `the model proposed the wrong thing`
        # from `the model proposed the right thing and a veto rejected it`,
        # which are opposite defects with opposite fixes.
        raw: dict[str, Any] | None = None
        try:
            content = result["choices"][0]["message"].get("content") or ""
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                raw = {
                    "mode": parsed.get("mode"),
                    "effect_operations": parsed.get("effect_operations"),
                }
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raw = None
        with telemetry_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "turn_id": current["id"],
                "raw_policy": raw,
                "shortlist": shortlists.get(current["id"]),
                "predicted_n": timings.get("predicted_n"),
                "predicted_ms": timings.get("predicted_ms"),
                "prompt_ms": timings.get("prompt_ms"),
                "cache_n": timings.get("cache_n"),
            }) + "\n")
        return result

    LlmRuntime._post = post
    LlmRuntime._post_native_tool_selection = native_selection
    try:
        return sidecar_module.main()
    finally:
        sidecar_module._prepare_turn_result = original_prepare
        LlmRuntime._post = original_post
        LlmRuntime._post_native_tool_selection = original_native_selection


def _classify(expected: dict[str, Any], observed: dict[str, Any]) -> str:
    """Name HOW the policy failed, not merely that it did."""

    kind = observed.get("kind")
    got = list(observed.get("effectOperations") or [])
    want = expected["expected_operations"]
    if not want and expected.get("expected_kind") == "conversation":
        return "exact" if kind == "conversation" and not got else "unsafe_action"
    if got == want:
        return "exact"
    if kind == "clarify":
        return "asked_to_clarify_a_clear_request"
    if kind == "conversation":
        return "answered_instead_of_acting"
    if not got:
        return "acted_without_naming_an_operation"
    if set(got) == set(want):
        return "right_operations_wrong_order"
    same_family = {o.split(".")[0] for o in got} == {o.split(".")[0] for o in want}
    if same_family:
        return "right_family_wrong_operation"
    return "wrong_family"


def _run(runtime: Any, cases: list[dict[str, Any]], telemetry: Path,
         variant: str = "leading_band") -> list[dict[str, Any]]:
    capabilities, application_catalog, game_catalog = current_core_catalog_snapshot(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES)))
    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime, gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"])
    command = [
        str(runtime.python), "-u", "-X", "utf8",
        str(Path(__file__).resolve()), "--sidecar", "--telemetry", str(telemetry),
        "--variant", variant,
    ]
    client = JsonLineProcess(command, environment=environment, cwd=REPO)
    rows: list[dict[str, Any]] = []
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("el sidecar rechazó el saludo")
        ready = client.request(
            {"type": "catalog.configure", "id": f"cat-{variant}",
             "capabilities": capabilities,
             "applicationCatalog": application_catalog,
             "gameCatalog": game_catalog},
            limits["handshake"])
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("el catálogo no quedó listo")
        client.request(
            {"type": "turn.decide", "id": "warm", "text": "hola mundo digital",
             "history": []},
            limits["turn.decide"])

        for repeat in range(REPEATS):
            for case in cases:
                turn_id = f"{variant}-{repeat}-{case['case_id']}"
                started = time.perf_counter()
                try:
                    reply = client.request(
                        {"type": "turn.decide", "id": turn_id,
                         "text": case["text"], "history": []},
                        limits["turn.decide"])
                except Exception as error:  # noqa: BLE001 - measurement only
                    rows.append({
                        "variant": variant,
                        "case_id": case["case_id"], "repeat": repeat,
                        "text": case["text"], "turn_id": turn_id,
                        "seconds": round(time.perf_counter() - started, 6),
                        "outcome": "transport_error", "detail": str(error)[:200],
                    })
                    continue
                observed = {
                    "kind": reply.get("kind"),
                    "operation": reply.get("operation"),
                    "effectOperations": reply.get("effectOperations"),
                }
                rows.append({
                    "variant": variant,
                    "case_id": case["case_id"], "repeat": repeat,
                    "text": case["text"], "turn_id": turn_id,
                    "seconds": round(time.perf_counter() - started, 6),
                    "expected_operations": case["expected_operations"],
                    "observed": observed,
                    "outcome": _classify(case, observed),
                })
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": f"sd-{variant}"},
            timeout=limits["shutdown"])
    return rows


def run() -> dict[str, Any]:
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    cases = _oracle()
    telemetry = OUTPUT.with_name("policy_tool_quality_telemetry_20260731.jsonl")
    if telemetry.exists():
        telemetry.unlink()
    telemetry.touch()
    rows = []
    # ABBA over whole sessions so neither arm owns the warm state.
    for order in (("baseline", "leading_band"),
                  ("leading_band", "baseline")):
        for variant in order:
            rows.extend(_run(runtime, cases, telemetry, variant))

    calls = [
        json.loads(line)
        for line in telemetry.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    per_turn_calls = collections.Counter(row.get("turn_id", "") for row in calls)

    # Attribute each turn to the model or to the machinery that runs after it.
    raw_by_turn: dict[str, dict[str, Any]] = {}
    shortlist_by_turn: dict[str, list[str]] = {}
    for call in calls:
        raw = call.get("raw_policy")
        if raw and call.get("turn_id"):
            raw_by_turn.setdefault(call["turn_id"], raw)
        if call.get("shortlist") and call.get("turn_id"):
            shortlist_by_turn.setdefault(call["turn_id"], call["shortlist"])
    attribution: collections.Counter[str] = collections.Counter()
    retrievable: collections.Counter[str] = collections.Counter()
    for row in rows:
        if "expected_operations" not in row:
            continue
        raw = raw_by_turn.get(row["turn_id"])
        want = row["expected_operations"]
        proposed = list((raw or {}).get("effect_operations") or [])
        model_right = proposed == want
        final_right = row["outcome"] == "exact"
        # Could P have named the right thing at all?
        shortlist = shortlist_by_turn.get(row["turn_id"])
        row["shortlist"] = shortlist
        if shortlist is None:
            retrievable["no_shortlist_captured"] += 1
        elif all(operation in shortlist for operation in want):
            retrievable["expected_was_offered"] += 1
        elif any(operation in shortlist for operation in want):
            retrievable["expected_partly_offered"] += 1
        else:
            retrievable["expected_never_offered_to_the_model"] += 1
        if raw is None:
            attribution["no_raw_policy_captured"] += 1
        elif model_right and final_right:
            attribution["model_right_kept"] += 1
        elif model_right and not final_right:
            attribution["model_right_but_overridden_after_P"] += 1
        elif not model_right and final_right:
            attribution["model_wrong_but_repaired_after_P"] += 1
        else:
            attribution["model_wrong"] += 1
        row["raw_policy"] = raw

    outcomes = collections.Counter(row["outcome"] for row in rows)
    exact = outcomes.get("exact", 0)
    by_case: dict[str, Any] = {}
    for case in cases:
        mine = [row for row in rows if row["case_id"] == case["case_id"]]
        by_case[case["case_id"]] = {
            "text": case["text"],
            "expected_operations": case["expected_operations"],
            "outcomes": sorted({row["outcome"] for row in mine}),
            "observed": [row.get("observed") for row in mine],
            "policy_calls": sum(
                per_turn_calls.get(row["turn_id"], 0) for row in mine),
            "turns": len(mine),
            "p50_s": round(statistics.median(
                sorted(row["seconds"] for row in mine)), 4) if mine else None,
        }

    # A case that is exact in every repeat is stable; one that flips is the
    # model being nondeterministic on a request whose answer is known.
    stable = [c for c, i in by_case.items() if i["outcomes"] == ["exact"]]
    unstable = [
        c for c, i in by_case.items()
        if len(i["outcomes"]) > 1 and "exact" in i["outcomes"]
    ]
    never = [c for c, i in by_case.items() if "exact" not in i["outcomes"]]

    total_calls = sum(per_turn_calls.get(row["turn_id"], 0) for row in rows)
    report = {
        "schema": "baxy.policy-tool-quality.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "effects_executed": 0,
        "question": (
            "given a request whose correct operation is known, how often does "
            "the primary policy name it, and how does it fail when it does not?"),
        "method": (
            "one arm, product code, the deterministic recogniser suspended "
            "inside the probe's own sidecar so each text is decided by P exactly "
            "as an unrecognised paraphrase of it would be. The oracle is the "
            "frozen text -> operations pairing of tests/test_effect_intent.py "
            "CASES; abstentions are excluded because they have no single right "
            "answer. This is a measurement, not an A/B and not a change."),
        "runtime": public_runtime_identity(runtime),
        "cases": len(cases),
        "turns": len(rows),
        "accuracy_exact": round(exact / len(rows), 4) if rows else None,
        "by_variant": {
            variant: {
                "turns": sum(1 for r in rows if r.get("variant") == variant),
                "exact": sum(
                    1 for r in rows
                    if r.get("variant") == variant and r["outcome"] == "exact"),
                "expected_was_offered": sum(
                    1 for r in rows
                    if r.get("variant") == variant and r.get("shortlist")
                    and all(o in r["shortlist"]
                            for o in r.get("expected_operations", []))),
            }
            for variant in ("baseline", "leading_band")
        },
        "outcomes": dict(outcomes.most_common()),
        "attribution": dict(attribution.most_common()),
        "retrievability": dict(retrievable.most_common()),
        "retrievability_note": (
            "the schema enum only admits shortlisted operations, so an "
            "operation E5 never retrieved is one the model physically could "
            "not name. Those turns are a retrieval failure, not a model "
            "failure, and no prompt or schema change would fix them."),
        "attribution_note": (
            "the headline accuracy is the FINAL envelope, which is what the "
            "person experiences. It is not the model's accuracy on its own: "
            "`model_right_but_overridden_after_P` counts turns where P proposed "
            "exactly the expected operations and BAXY's post-policy vetoes "
            "changed the answer. Those two failures have opposite fixes, so "
            "they are never reported as one number."),
        "stable_exact_cases": len(stable),
        "unstable_cases": sorted(unstable),
        "never_exact_cases": sorted(never),
        "retry_cost": {
            "policy_calls": total_calls,
            "turns": len(rows),
            "calls_per_turn": round(total_calls / len(rows), 3) if rows else None,
            "note": (
                "a retry is a whole extra decode, so a policy that hesitates is "
                "not only less accurate, it is also slower. This is the link "
                "between tool-calling quality and latency."),
        },
        "by_case": by_case,
        "samples": rows,
        "policy_calls": calls,
    }
    write_json_atomic(OUTPUT, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sidecar", action="store_true")
    parser.add_argument("--telemetry", default="")
    parser.add_argument("--variant", default="leading_band")
    args, _ = parser.parse_known_args()
    if args.sidecar:
        return _sidecar_main(args.telemetry, args.variant)
    report = run()
    print(json.dumps({
        "cases": report["cases"],
        "turns": report["turns"],
        "accuracy_exact": report["accuracy_exact"],
        "outcomes": report["outcomes"],
        "by_variant": report["by_variant"],
        "attribution": report["attribution"],
        "retrievability": report["retrievability"],
        "stable_exact_cases": report["stable_exact_cases"],
        "unstable_cases": report["unstable_cases"],
        "never_exact_cases": report["never_exact_cases"],
        "retry_cost": report["retry_cost"],
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
