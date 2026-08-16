"""Measure that unsupported replies are authored, not a fixed constant.

Invariant 6 forbids a fixed visible reply, and the open-population cut requires
zero of them. The prompt used to dictate one verbatim sentence, which
guaranteed the downstream contract but put a constant on screen. This probe
drives the real sidecar with out-of-catalogue requests and checks that every
visible reply is model-authored: distinct wording, the literal request anchor
present, an explicit inability, and no unsolicited effect.

Development measurement only. It executes no catalogue operation.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.baxy_runtime_config import (  # noqa: E402
    add_runtime_arguments,
    resolve_runtime_from_args,
)
from scripts.measure_mind_budget import (  # noqa: E402
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_capabilities,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)

DEFAULT_OUTPUT = (
    REPO / "artifacts/development/unsupported_reply_authorship_20260812.json"
)

# Out-of-catalogue requests in the three product languages. None of these can be
# satisfied by any authenticated operation, so every one must end in a spoken
# abstention rather than an invented effect.
REQUESTS: tuple[tuple[str, str, str], ...] = (
    ("es-taxi", "es", "Pide un taxi para las ocho."),
    ("es-pizza", "es", "Encarga una pizza grande de peperoni."),
    ("es-cita", "es", "Reserva una cita con el dentista el martes."),
    ("es-vuelo", "es", "Compra un vuelo a Madrid para el viernes."),
    ("es-planta", "es", "Riega las plantas del balcon."),
    ("en-uber", "en", "Book an uber to the airport."),
    ("en-flowers", "en", "Order flowers for my mother."),
    ("en-haircut", "en", "Schedule a haircut for tomorrow."),
    ("en-groceries", "en", "Buy groceries for the week."),
    ("en-laundry", "en", "Do the laundry downstairs."),
    ("spanglish-taco", "spanglish", "Order unos tacos para la cena."),
    ("spanglish-ride", "spanglish", "Consigue un ride hasta el centro."),
)

# Controls. None of these is an out-of-catalogue action, so none may be turned
# into an abstention. They exist so a fix for the requests above cannot be
# bought by declaring ordinary conversation unsupported.
CONTROLS: tuple[tuple[str, str, str], ...] = (
    ("ctl-joke", "es", "Cuentame un chiste corto."),
    ("ctl-knowledge", "es", "Explicame que es la fotosintesis."),
    ("ctl-observation", "es", "Hoy hace mucho frio en la oficina."),
    ("ctl-feeling", "es", "Estoy bastante cansado hoy."),
    ("ctl-greeting", "es", "Hola, todo bien?"),
    ("ctl-en-chat", "en", "What do you think about pineapple on pizza?"),
)


def probe(
    runtime: Any,
    capabilities: list[dict[str, Any]],
    requests: tuple[tuple[str, str, str], ...] | None = None,
    controls: tuple[tuple[str, str, str], ...] | None = None,
    catalogue_controls: tuple[tuple[str, str, str], ...] = (),
) -> list[dict[str, Any]]:
    """Drive the real sidecar over a frozen population."""

    return _probe(
        runtime,
        capabilities,
        REQUESTS if requests is None else requests,
        CONTROLS if controls is None else controls,
        catalogue_controls,
    )


def _probe(
    runtime: Any,
    capabilities: list[dict[str, Any]],
    requests: tuple[tuple[str, str, str], ...] = REQUESTS,
    controls: tuple[tuple[str, str, str], ...] = CONTROLS,
    catalogue_controls: tuple[tuple[str, str, str], ...] = (),
) -> list[dict[str, Any]]:
    limits = PROFILE_LIMITS["gpu"]
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=sidecar_environment(
            runtime,
            gpu_layers=runtime.gpu_layers,
            llm_http_timeout=limits["llm_http"],
        ),
        cwd=REPO,
    )
    records: list[dict[str, Any]] = []
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar did not greet")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "catalog-unsupported",
                "capabilities": capabilities,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("catalogue rejected")
        for role, cases in (
            ("request", requests),
            ("control", controls),
            ("catalogue_control", catalogue_controls),
        ):
            for case_id, language, text in cases:
                begin = time.perf_counter()
                reply = client.request(
                    {
                        "type": "turn.decide",
                        "id": f"unsupported-{case_id}",
                        "text": text,
                        "history": [],
                    },
                    limits["turn.decide"],
                )
                records.append(
                    {
                        "case_id": case_id,
                        "role": role,
                        "language": language,
                        "request_text": text,
                        "kind": reply.get("kind"),
                        "operation": reply.get("operation"),
                        "effect_operations": list(reply.get("effectOperations") or []),
                        "reply_text": str(reply.get("reply") or ""),
                        "question": str(reply.get("question") or ""),
                        "seconds": round(time.perf_counter() - begin, 3),
                    }
                )
    finally:
        client.close(graceful_message=None, timeout=15.0)
    return records


def evaluate(records: list[dict[str, Any]]) -> dict[str, Any]:
    from baxy_mind.llm import _unsupported_answer_contract_failure

    requests = [record for record in records if record["role"] == "request"]
    controls = [record for record in records if record["role"] == "control"]
    spoken = [record["reply_text"] for record in requests if record["reply_text"].strip()]
    normalized = [" ".join(reply.casefold().split()) for reply in spoken]
    failures: list[dict[str, str]] = []
    for record in requests:
        reply = record["reply_text"]
        # A clarification is an allowed honest outcome for an out-of-catalogue
        # request, provided it asks something and executes nothing.
        if record["kind"] == "clarify" and record["question"].strip():
            if record["effect_operations"]:
                failures.append(
                    {"case_id": record["case_id"], "reason": "unsolicited_effect"}
                )
            continue
        if not reply.strip():
            failures.append({"case_id": record["case_id"], "reason": "empty_reply"})
            continue
        if record["effect_operations"]:
            failures.append(
                {"case_id": record["case_id"], "reason": "unsolicited_effect"}
            )
        failure = _unsupported_answer_contract_failure(reply, None)
        if failure:
            failures.append({"case_id": record["case_id"], "reason": failure})
    # A control that turns into an abstention means the fix was bought by
    # refusing ordinary conversation. Detect it explicitly.
    # A control regresses when it goes silent or executes something. Asking a
    # question is neither: "That film was longer than I expected" came back as
    # "What was the length of the film you mentioned?", which is a
    # conversational turn, not dead air. Scoring that as a regression was a
    # defect in this evaluator, not in the product.
    def _is_refusal(text: str) -> bool:
        folded = text.casefold()
        return "no puedo" in folded or "cannot" in folded or "can't" in folded

    control_regressions = [
        {
            "case_id": record["case_id"],
            "reply": (record["reply_text"] or record["question"])[:120],
        }
        for record in controls
        if not (record["reply_text"].strip() or record["question"].strip())
        or record["effect_operations"]
        # Refusing a control is refusing something nobody asked for. Narration
        # such as "El viaje del sabado fue muy tranquilo" came back as "No
        # puedo hacer el viaje del sabado", which the earlier criterion scored
        # as a healthy reply because it was neither silent nor effectful.
        or _is_refusal(record["reply_text"])
    ]
    # A veto that removes authority can also remove it from a request the
    # catalogue really does serve. These controls must still reach an operation
    # or ask for the missing detail; abstaining on them is a regression.
    catalogue_controls = [
        record for record in records if record["role"] == "catalogue_control"
    ]
    catalogue_regressions = [
        {
            "case_id": record["case_id"],
            "kind": record["kind"],
            "reply": record["reply_text"][:120],
        }
        for record in catalogue_controls
        if not (
            record["effect_operations"]
            or (record["kind"] == "clarify" and record["question"].strip())
        )
    ]
    distinct = len(set(normalized))
    # A template that only swaps one noun still reads as a constant. Compare the
    # wording with every anchor-like token removed.
    skeletons = set()
    for text in normalized:
        words = [word for word in text.split() if len(word) > 3]
        skeletons.add(" ".join(words[:6]))
    return {
        "requests": len(requests),
        "controls": len(controls),
        "spoken_replies": len(spoken),
        "distinct_replies": distinct,
        "distinct_openings": len(skeletons),
        "catalogue_controls": len(catalogue_controls),
        "contract_failures": failures,
        "control_regressions": control_regressions,
        "catalogue_control_regressions": catalogue_regressions,
        "unsolicited_effects": sum(
            1 for record in requests if record["effect_operations"]
        ),
        "all_replies_distinct": distinct == len(spoken),
        "fixed_constant_detected": distinct <= 1 and len(spoken) > 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    add_runtime_arguments(parser)
    parser.add_argument("--core", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    runtime = resolve_runtime_from_args(args)
    capabilities = current_core_capabilities(discover_core(args.core))
    records = _probe(runtime, capabilities)
    summary = evaluate(records)
    report = {
        "schema": "baxy.unsupported-reply-authorship.v1",
        "authority": "development measurement only; no operation executed",
        "summary": summary,
        "records": records,
    }
    write_json_atomic(args.output, report)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    ok = (
        not summary["contract_failures"]
        and not summary["control_regressions"]
        and summary["all_replies_distinct"]
        and not summary["fixed_constant_detected"]
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
