"""How good is the model's tool calling on the requests it actually receives?

Every tool-calling measurement so far used the 57 canonical phrasings of
`tests/test_effect_intent.py`. Those are exactly the texts the deterministic
recogniser owns, so in production they never reach the model: measuring them
required suspending the recogniser, and the result is a proxy for a paraphrase,
not a paraphrase.

This probe uses the population that genuinely reaches the model. From the frozen
14836-row historical corpus it takes rows that are a real `user_mission`, name
exactly one operation family, read as an utterance rather than an engineering
note, and -- the point -- are NOT resolved by the deterministic recogniser. 1002
texts qualify; a deterministic stratified sample of them is frozen into the
artifact so a later run compares the same questions.

The corpus labels families (`media.play`, `task.manage`), not leaves, so the
metric is family-level: did the model name an operation of the family the corpus
assigned? That is the granularity the labels support and no more is claimed.
`memory` is excluded because the planner never admits it, so the model could
never name it.

One arm, product code, no recogniser suspension. No effect is executed and
nothing is installed.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
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

OUTPUT = REPO / "artifacts" / "fixes" / "paraphrase_tool_quality_20260731.json"
PER_FAMILY = 6
REPEATS = 2

# Engineering notes wear the same class label as user requests in this corpus.
_TECHNICAL = re.compile(
    r"[\\/_=<>`]|\.(py|json|md|exe|gguf)\b|"
    r"\b(mmproj|KV|VRAM|CPU|flag|parser|ingest|commit|schema)\b",
    re.IGNORECASE,
)


def _oracle(catalog_names: tuple[str, ...]) -> list[dict[str, Any]]:
    """Freeze a deterministic stratified sample of the real long tail."""

    from baxy_mind.effect_intent import (
        resolve_explicit_clarification,
        resolve_explicit_effects,
    )

    families = {name.split(".")[0] for name in catalog_names}
    path = REPO / "tests" / "data" / "historical_messages.jsonl"
    pool: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("class") != "user_mission":
            continue
        if row.get("language") not in ("es", "en"):
            continue
        operations = row.get("operations") or []
        if len(operations) != 1:
            continue
        family = str(operations[0]).split(".")[0]
        # The planner never admits memory.*, so the model could not name it.
        if family not in families or family == "memory":
            continue
        text = (row.get("text_literal") or "").strip().strip("«»\"”“").strip()
        if not text or not 8 <= len(text) <= 70 or text in seen:
            continue
        if _TECHNICAL.search(text):
            continue
        # The population that reaches the model is exactly the one the
        # deterministic recogniser does not own.
        if resolve_explicit_effects(text, catalog_names, ()) is not None:
            continue
        if resolve_explicit_clarification(text, catalog_names) is not None:
            continue
        seen.add(text)
        pool.append({"text": text, "family": family,
                     "label": operations[0], "language": row.get("language")})

    by_family: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for entry in sorted(pool, key=lambda item: item["text"]):
        by_family[entry["family"]].append(entry)
    cases: list[dict[str, Any]] = []
    for family in sorted(by_family):
        for index, entry in enumerate(by_family[family][:PER_FAMILY]):
            cases.append({**entry, "case_id": f"{family}-{index:02d}"})
    return cases


def _sidecar_main(telemetry: str, variant: str = "scheduling_supported") -> int:
    from baxy_mind import effect_intent
    from baxy_mind import llm as llm_module
    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime

    if variant == "baseline":
        # The narrow escape hatch as it stood: only a create-like verb AND
        # one of five nouns, with no verbless nominal opening and no verb
        # that names the act by itself. `[0-9]+` never matches a head,
        # which is how that third branch is switched off.
        effect_intent._SCHEDULING_VERB = (
            rf"(?:{effect_intent._CREATE}|programa|programar|schedule)")
        effect_intent._SCHEDULING_NOUN = (
            r"\b(?:recordatorio|recordatorios|reminder|reminders|"
            r"evento|eventos|event|events|calendario|calendar|"
            r"tarea|tareas|task|tasks|rutina|rutinas|routine|routines)\b")
        effect_intent._SCHEDULING_BY_ITSELF = r"[0-9]+"

    telemetry_path = Path(telemetry)
    current: dict[str, str] = {"id": ""}
    original_prepare = sidecar_module._prepare_turn_result

    def prepare(message, **kwargs):
        current["id"] = str(message.get("id") or "")
        try:
            return original_prepare(message, **kwargs)
        finally:
            # Everything downstream of the policy call runs AFTER it, so this
            # has to be written when the turn closes. Recording it inside the
            # POST hook read an empty list every time.
            with telemetry_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "close_of": current["id"],
                    "veto_fired": fired.get(current["id"], []),
                    "decide_turn_returned": decided.get(current["id"]),
                }) + "\n")

    sidecar_module._prepare_turn_result = prepare

    # Which gate removes the effect? `the vetoes suppress tool calling` is a
    # diagnosis; naming the one that fires is what makes it actionable. Each is
    # wrapped to record only whether IT was the step that dropped the effect.
    fired: dict[str, list[str]] = {}
    decided: dict[str, Any] = {}

    # The effect can also be dropped INSIDE decide_turn, by the semantic guard
    # or the count verifier, before any of the gates below ever sees it.
    # Capturing its return value separates the two layers.
    _original_decide = LlmRuntime.decide_turn

    def decide_turn(self, *args, **kwargs):
        result = _original_decide(self, *args, **kwargs)
        if isinstance(result, dict):
            decided[current["id"]] = {
                "mode": result.get("mode"),
                "effect_operations": result.get("effect_operations"),
            }
        return result

    LlmRuntime.decide_turn = decide_turn

    def _watch(name: str):
        original = getattr(sidecar_module, name)

        def wrapper(decision, *args, **kwargs):
            before = list((decision or {}).get("effect_operations") or [])
            result = original(decision, *args, **kwargs)
            after = list((result or {}).get("effect_operations") or [])
            if before and not after:
                fired.setdefault(current["id"], []).append(name)
            return result

        setattr(sidecar_module, name, wrapper)

    for _gate in (
        "apply_explicit_effect_contract",
        "apply_operation_domain_grounding_veto",
        "apply_compound_effect_conservation_veto",
        "apply_turn_action_relevance_veto",
        "apply_turn_action_grounding_gate",
        "apply_conversation_effect_presentation",
    ):
        _watch(_gate)

    original_build = llm_module._build_turn_policy_payload
    shortlists: dict[str, list[str]] = {}

    def build(text, operation_names, candidate_text, prior_messages):
        shortlists[current["id"]] = list(operation_names or ())
        return original_build(text, operation_names, candidate_text, prior_messages)

    llm_module._build_turn_policy_payload = build
    original_post = LlmRuntime._post

    def post(self, payload, timeout=None, *, max_attempts=2, cancellation=None):
        result = original_post(
            self, payload, timeout, max_attempts=max_attempts,
            cancellation=cancellation)
        envelope = (payload.get("response_format") or {}).get("json_schema") or {}
        if envelope.get("name") != "baxy_turn_decision":
            return result
        timings = result.get("timings") or {}
        raw: dict[str, Any] | None = None
        try:
            parsed = json.loads(result["choices"][0]["message"].get("content") or "")
            if isinstance(parsed, dict):
                raw = {"mode": parsed.get("mode"),
                       "effect_operations": parsed.get("effect_operations")}
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raw = None
        with telemetry_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "turn_id": current["id"],
                "raw_policy": raw,
                "shortlist": shortlists.get(current["id"]),
                "predicted_ms": timings.get("predicted_ms"),
                "prompt_ms": timings.get("prompt_ms"),
            }) + "\n")
        return result

    LlmRuntime._post = post
    try:
        return sidecar_module.main()
    finally:
        sidecar_module._prepare_turn_result = original_prepare
        LlmRuntime._post = original_post


def _run_variant(runtime, capabilities, cases, telemetry, variant):
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
        if client.next_message(limits["handshake"]).get("type") != "hello":
            raise RuntimeError("el sidecar rechazó el saludo")
        if client.request(
            {"type": "catalog.configure", "id": f"cat-{variant}",
             "capabilities": capabilities},
            limits["handshake"],
        ).get("type") != "catalog.ready":
            raise RuntimeError("el catálogo no quedó listo")
        client.request(
            {"type": "turn.decide", "id": "warm", "text": "hola mundo digital",
             "history": []}, limits["turn.decide"])

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
                    rows.append({**case, "variant": variant, "repeat": repeat, "turn_id": turn_id,
                                 "outcome": "transport_error",
                                 "detail": str(error)[:200]})
                    continue
                chosen = list(reply.get("effectOperations") or [])
                chosen_families = {name.split(".")[0] for name in chosen}
                rows.append({
                    **case, "variant": variant, "repeat": repeat, "turn_id": turn_id,
                    "seconds": round(time.perf_counter() - started, 6),
                    "kind": reply.get("kind"),
                    "chosen": chosen,
                    "outcome": (
                        "right_family" if case["family"] in chosen_families
                        else "no_operation" if not chosen
                        else "wrong_family"),
                })
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": f"sd-{variant}"},
            timeout=limits["shutdown"])

    return rows


def run() -> dict[str, Any]:
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES)))
    catalog_names = tuple(str(item.get("name", "")) for item in capabilities)
    cases = _oracle(catalog_names)
    telemetry = OUTPUT.with_name(
        "paraphrase_tool_quality_telemetry_20260731.jsonl")
    if telemetry.exists():
        telemetry.unlink()
    telemetry.touch()
    rows: list[dict[str, Any]] = []
    # ABBA over whole sessions so neither arm owns the warm state.
    for order in (("baseline", "scheduling_supported"),
                  ("scheduling_supported", "baseline")):
        for variant in order:
            rows.extend(_run_variant(
                runtime, capabilities, cases, telemetry, variant))

    calls = [
        json.loads(line)
        for line in telemetry.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    shortlist_by_turn = {
        call["turn_id"]: call["shortlist"]
        for call in calls if call.get("shortlist") and call.get("turn_id")
    }
    for row in rows:
        shortlist = shortlist_by_turn.get(row["turn_id"])
        row["shortlist"] = shortlist
        row["family_was_offered"] = (
            None if shortlist is None
            else any(name.split(".")[0] == row["family"] for name in shortlist)
        )

    outcomes = collections.Counter(row["outcome"] for row in rows)
    offered = [row for row in rows if row.get("family_was_offered")]
    offered_right = sum(1 for row in offered if row["outcome"] == "right_family")
    by_family: dict[str, Any] = {}
    for family in sorted({row["family"] for row in rows}):
        mine = [row for row in rows if row["family"] == family]
        by_family[family] = {
            "turns": len(mine),
            "right_family": sum(1 for row in mine if row["outcome"] == "right_family"),
            "family_offered": sum(1 for row in mine if row.get("family_was_offered")),
            "kinds": dict(collections.Counter(str(row.get("kind")) for row in mine)),
        }

    report = {
        "schema": "baxy.paraphrase-tool-quality.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "effects_executed": 0,
        "question": (
            "on the requests that actually reach the model -- real user "
            "utterances the deterministic recogniser does not own -- does it "
            "name an operation of the right family?"),
        "why_this_corpus": (
            "every earlier tool-calling measurement used the 57 canonical "
            "phrasings the recogniser owns, which required suspending it and "
            "yielded a proxy for a paraphrase rather than a paraphrase. This "
            "corpus is the real population: 1002 qualifying texts, of which a "
            "deterministic stratified sample is frozen here."),
        "granularity": (
            "the corpus labels families, not leaves, so the metric is "
            "family-level and nothing finer is claimed. `memory` is excluded "
            "because the planner never admits it."),
        "runtime": public_runtime_identity(runtime),
        "cases": len(cases),
        "turns": len(rows),
        "right_family_share": round(
            outcomes.get("right_family", 0) / len(rows), 4) if rows else None,
        "family_offered_share": round(
            len(offered) / len(rows), 4) if rows else None,
        "right_family_given_offered": round(
            offered_right / len(offered), 4) if offered else None,
        "outcomes": dict(outcomes.most_common()),
        "by_family": by_family,
        "seconds_p50": round(statistics.median(
            sorted(row["seconds"] for row in rows if "seconds" in row)), 4),
        "frozen_sample": cases,
        "samples": rows,
    }
    write_json_atomic(OUTPUT, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sidecar", action="store_true")
    parser.add_argument("--telemetry", default="")
    parser.add_argument("--variant", default="scheduling_supported")
    args, _ = parser.parse_known_args()
    if args.sidecar:
        return _sidecar_main(args.telemetry, args.variant)
    report = run()
    print(json.dumps({
        "cases": report["cases"],
        "turns": report["turns"],
        "right_family_share": report["right_family_share"],
        "family_offered_share": report["family_offered_share"],
        "right_family_given_offered": report["right_family_given_offered"],
        "outcomes": report["outcomes"],
        "by_family": report["by_family"],
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
