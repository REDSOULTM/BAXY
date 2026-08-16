"""Does the LLM get to answer a farewell, or does a constant answer for it?

BAXY told a person who said `nos vemos` that it could not produce a reliable
answer, four times out of four, in both arms of the social-envelope A/B. The
model was not failing: `chat` rejects a reply whose normalised text equals the
person's own, and for a farewell the mirror *is* the answer. `¡Nos vemos!`,
`¡Chau!`, `Bye!` and `Good night!` were all discarded and replaced by a fixed
string. `¡Adiós!` survived only by the accident of its accent.

The candidate lets a social turn mirror. The gate is not latency: it is that
every visible word comes from the model and no turn is answered by a constant.
Nothing is installed and no effect is executed.
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

OUTPUT = REPO / "artifacts" / "fixes" / "farewell_reply_20260731.json"
VARIANTS = ("baseline", "model_answers")

# The fixed string the guard substituted. Its presence in a visible reply is
# the failure this probe measures.
CONSTANT = "No pude generar una respuesta fiable"

CASES: tuple[tuple[str, str, str], ...] = (
    ("bye-es-01", "nos vemos", "farewell"),
    ("bye-es-02", "chau", "farewell"),
    ("bye-es-03", "hasta luego", "farewell"),
    ("bye-es-04", "adios", "farewell"),
    ("bye-en-01", "bye", "farewell"),
    ("bye-en-02", "good night", "farewell"),
    ("bye-en-03", "see you later", "farewell"),
    # Greeting and gratitude never mirrored, so they must stay exactly as they
    # were: this is the control that the change is scoped to what it claims.
    ("hi-01", "hola", "greeting"),
    ("hi-02", "hi", "greeting"),
    ("ty-01", "gracias", "gratitude"),
    ("ty-02", "thank you", "gratitude"),
    # A knowledge turn keeps the anti-echo guard, which is the behaviour the
    # change deliberately does not touch.
    ("know-01", "por que el cielo es azul", "knowledge"),
)
REPEATS = 2


def _sidecar_main(variant: str) -> int:
    """Run the real sidecar, restoring the unconditional guard for baseline."""

    from baxy_mind import llm as llm_module
    from baxy_mind import __main__ as sidecar_module

    if variant == "baseline":
        original_chat = llm_module.LlmRuntime.chat

        def chat(self, text, history=None, tools=None, temperature=0.7, *,
                 conversation_kind=None, response_language=None,
                 cancellation=None):
            # The previous behaviour: a mirror is always treated as a failure,
            # whatever the speech act.
            reply, calls = original_chat(
                self, text, history=history, tools=tools,
                temperature=temperature, conversation_kind=conversation_kind,
                response_language=response_language, cancellation=cancellation)
            if llm_module._normalized_dialogue_text(reply) == (
                    llm_module._normalized_dialogue_text(text)):
                return (
                    "No pude generar una respuesta fiable esta vez. "
                    "¿Puedes reformular la pregunta?"), calls
            return reply, calls

        llm_module.LlmRuntime.chat = chat
    return sidecar_module.main()


def _run_variant(runtime: Any, variant: str) -> list[dict[str, Any]]:
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES)))
    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime, gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"])
    command = [
        str(runtime.python), "-u", "-X", "utf8",
        str(Path(__file__).resolve()), "--sidecar", "--variant", variant,
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
                started = time.perf_counter()
                reply = client.request(
                    {"type": "turn.decide", "id": f"{variant}-{repeat}-{case_id}",
                     "text": text, "history": []},
                    limits["turn.decide"])
                visible = str(reply.get("reply") or "")
                rows.append({
                    "variant": variant,
                    "repeat": repeat,
                    "case_id": case_id,
                    "family": family,
                    "text": text,
                    "seconds": round(time.perf_counter() - started, 6),
                    "kind": reply.get("kind"),
                    "reply_text": visible,
                    "answered_by_a_constant": CONSTANT in visible,
                })
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": f"sd-{variant}"},
            timeout=limits["shutdown"])
    return rows


def run() -> dict[str, Any]:
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    samples: list[dict[str, Any]] = []
    for order in (VARIANTS, tuple(reversed(VARIANTS))):
        for variant in order:
            samples.extend(_run_variant(runtime, variant))

    per_case: dict[str, Any] = {}
    for case_id, text, family in CASES:
        entry: dict[str, Any] = {"text": text, "family": family}
        for variant in VARIANTS:
            rows = [
                row for row in samples
                if row["case_id"] == case_id and row["variant"] == variant
            ]
            entry[variant] = {
                "answered_by_a_constant": sum(
                    1 for row in rows if row["answered_by_a_constant"]),
                "turns": len(rows),
                "replies": sorted({row["reply_text"] for row in rows}),
                "p50_s": round(statistics.median(
                    sorted(row["seconds"] for row in rows)), 4) if rows else None,
                "kinds": sorted({str(row["kind"]) for row in rows}),
            }
        per_case[case_id] = entry

    def constants(variant: str) -> int:
        return sum(
            1 for row in samples
            if row["variant"] == variant and row["answered_by_a_constant"])

    def p50(variant: str, family: str) -> float | None:
        values = sorted(
            row["seconds"] for row in samples
            if row["variant"] == variant and row["family"] == family)
        return round(statistics.median(values), 4) if values else None

    families = sorted({family for _, _, family in CASES})
    report = {
        "schema": "baxy.farewell-reply.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "effects_executed": 0,
        "question": (
            "does the model get to answer a farewell, or does a constant answer "
            "for it?"),
        "mechanism": (
            "chat() replaced any reply whose normalised text equalled the "
            "person's own with a fixed string. That guard exists to catch a "
            "model parroting the question, but for a farewell the mirror IS the "
            "answer, so it discarded `¡Nos vemos!`, `¡Chau!`, `Bye!` and `Good "
            "night!`. `¡Adiós!` survived only by the accident of its accent. The "
            "candidate lets a turn classified as a social act mirror; every "
            "other conversation kind keeps the guard unchanged."),
        "gate": (
            "no visible reply may be produced by a constant, and the greeting, "
            "gratitude and knowledge controls must keep answering exactly as "
            "they did. Latency is reported but is not the gate."),
        "method": (
            "the real sidecar per variant, whole sessions alternated in ABBA "
            "order, the same corpus twice per session. The baseline arm "
            "restores the unconditional guard inside the same product code."),
        "runtime": public_runtime_identity(runtime),
        "answered_by_a_constant": {
            variant: constants(variant) for variant in VARIANTS
        },
        "turns_per_arm": len(samples) // 2,
        "by_family_p50_s": {
            family: {variant: p50(variant, family) for variant in VARIANTS}
            for family in families
        },
        "passed": constants("model_answers") == 0,
        "per_case": per_case,
        "samples": samples,
    }
    write_json_atomic(OUTPUT, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sidecar", action="store_true")
    parser.add_argument("--variant", default="baseline")
    args, _ = parser.parse_known_args()
    if args.sidecar:
        return _sidecar_main(args.variant)
    report = run()
    print(json.dumps({
        "answered_by_a_constant": report["answered_by_a_constant"],
        "turns_per_arm": report["turns_per_arm"],
        "by_family_p50_s": report["by_family_p50_s"],
        "passed": report["passed"],
        "farewell_replies": {
            case: report["per_case"][case]["model_answers"]["replies"]
            for case in report["per_case"]
            if report["per_case"][case]["family"] == "farewell"
        },
    }, ensure_ascii=False, indent=1))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
