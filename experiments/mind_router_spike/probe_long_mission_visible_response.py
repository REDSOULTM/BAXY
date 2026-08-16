"""Measure model-authored visible responses for long and partial missions.

The probe starts the registered local mind runtime and sends only
``message.compose`` requests containing synthetic, already-verified facts. It
never configures a plan, calls Core, dispatches a provider, or performs an
effect. Acceptance requires every literal fact and action to survive while
internal vocabulary, opaque identities, false success, and generic follow-up
questions stay out of the person-facing text.
"""

from __future__ import annotations

import argparse
import hashlib
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
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    file_sha256,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    JsonLineProcess,
    PROFILE_LIMITS,
    sidecar_environment,
    write_json_atomic,
)


OUTPUT = REPO / "artifacts/fixes/long_mission_visible_response_r1.json"
FORBIDDEN_GLOBAL = (
    "planner",
    "router",
    "schema",
    "tool",
    "json",
    "catálogo",
    "catalogo",
    "grounding",
    "checkpoint",
    "reconciliación",
    "reconciliacion",
    "core",
    "identificador interno",
    "internal identifier",
    "qué quieres hacer ahora",
    "que quieres hacer ahora",
    "necesitas algo más",
    "necesitas algo mas",
    "what would you like to do next",
    "do you need anything else",
)


def fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value).casefold()
    return "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    )


def _mission_situation(intro: str, facts: list[str], reason: str = "") -> str:
    lines = [intro, *(f"• {fact}" for fact in facts)]
    if reason:
        lines.append(f"Motivo: {reason}")
    return "\n".join(lines)


def build_cases() -> list[dict[str, Any]]:
    success_es = [
        "Paso 1: La hora local es 14:25.",
        "Paso 2: Encontré la tarea «Revisar presupuesto».",
        "Paso 3: Encontré la nota «Clave Alfa».",
        "Paso 4: Hay 17 procesos activos.",
        "Paso 5: Silencié el audio.",
        "Paso 6: Puse el volumen en 35 %.",
        "Paso 7: Creé la tarea «Informe Q3».",
        "Paso 8: Creé la nota «Resumen final».",
    ]
    success_en = [
        "Step 1: The local time is 14:25.",
        "Step 2: I found the task «Review budget».",
        "Step 3: I found the note «Alpha Key».",
        "Step 4: There are 17 active processes.",
        "Step 5: I muted the audio.",
        "Step 6: I set the volume to 35%.",
        "Step 7: I created the task «Q3 Report».",
        "Step 8: I created the note «Final summary».",
    ]
    partial_es = [
        "Paso 1: Abrí Bloc de notas.",
        "Paso 2: Creé la nota «Clave Alfa».",
        "Paso 3: Puse el volumen en 35 %.",
    ]
    partial_en = [
        "Step 1: I opened Notepad.",
        "Step 2: I created the note «Alpha Key».",
        "Step 3: I set the volume to 35%.",
    ]
    dense_es = [f"Proceso {index}: PID {4100 + index}." for index in range(1, 13)]
    dense_en = [f"Process {index}: PID {5100 + index}." for index in range(1, 13)]
    return [
        {
            "case_id": "octet-success-es",
            "user_text": (
                "Dime la hora, lista tareas, notas y procesos; silencia el audio, "
                "ponlo al 35 %, crea la tarea Informe Q3 y la nota Resumen final."
            ),
            "intent": "status",
            "facts": {
                "situation": _mission_situation(
                    "Completé y verifiqué los 8 pasos de la misión.", success_es
                ),
                "mustNotAskFollowUp": True,
                "actor": "BAXY (yo, primera persona)",
                "mustPreserveFirstPerson": True,
                "requiredActions": ["silencié", "puse", "creé"],
                "requiredFacts": success_es,
            },
            "forbids": ["I completed", "I found"],
        },
        {
            "case_id": "octet-success-en",
            "user_text": (
                "Tell me the time, list tasks, notes and processes; mute audio, "
                "set it to 35%, create the Q3 Report task and Final summary note."
            ),
            "intent": "status",
            "facts": {
                "situation": _mission_situation(
                    "I completed and verified all 8 mission steps.", success_en
                ),
                "mustNotAskFollowUp": True,
                "actor": "BAXY (I, first person)",
                "mustPreserveFirstPerson": True,
                "requiredActions": ["muted", "set", "created"],
                "requiredFacts": success_en,
            },
            "forbids": ["Listo", "encontré", "misión"],
        },
        {
            "case_id": "partial-failure-es",
            "user_text": (
                "Abre Bloc de notas, crea la nota Clave Alfa, pon el volumen al "
                "35 % y después imprime el informe."
            ),
            "intent": "error",
            "facts": {
                "situation": _mission_situation(
                    "No pude completar toda la misión. Antes de detenerla, "
                    "completé y verifiqué 3 pasos:",
                    partial_es,
                    "No pude completar el paso 4; detuve los restantes.",
                ),
                "mustNotAskFollowUp": True,
                "actor": "BAXY (yo, primera persona)",
                "mustPreserveFirstPerson": True,
                "requiredActions": ["abrí", "creé", "puse"],
                "requiredFacts": partial_es,
                "partialMission": True,
            },
            "contains_any": ["no pude", "falló", "fallo"],
            "forbids": ["could not", "failed"],
        },
        {
            "case_id": "partial-failure-en",
            "user_text": (
                "Open Notepad, create the Alpha Key note, set volume to 35%, "
                "and then print the report."
            ),
            "intent": "error",
            "facts": {
                "situation": _mission_situation(
                    "I could not complete the whole mission. I completed and "
                    "verified 3 steps before stopping:",
                    partial_en,
                    "I could not complete step 4, so I stopped the rest.",
                ),
                "mustNotAskFollowUp": True,
                "actor": "BAXY (I, first person)",
                "mustPreserveFirstPerson": True,
                "requiredActions": ["opened", "created", "set"],
                "requiredFacts": partial_en,
                "partialMission": True,
            },
            "contains_any": ["could not", "couldn't", "failed"],
            "forbids": ["Listo", "encontré", "no pude"],
        },
        {
            "case_id": "dense-processes-es",
            "user_text": "Lista los doce procesos activos que encontraste.",
            "intent": "status",
            "facts": {
                "situation": _mission_situation(
                    "Encontré estos procesos activos:", dense_es
                ),
                "mustNotAskFollowUp": True,
                "requiredFacts": dense_es,
            },
            "forbids": ["I found", "processes active", "Lista los"],
        },
        {
            "case_id": "dense-processes-en",
            "user_text": "List the twelve active processes you found.",
            "intent": "status",
            "facts": {
                "situation": _mission_situation(
                    "I found these active processes:", dense_en
                ),
                "mustNotAskFollowUp": True,
                "requiredFacts": dense_en,
            },
            "forbids": ["Listo", "encontré", "List the", "Show the"],
        },
        {
            "case_id": "confirmation-complete-options",
            "user_text": "Borra el archivo temporal y sigue con la misión.",
            "intent": "confirmation",
            "facts": {
                "situation": (
                    "El siguiente paso requiere una decisión. Responde «confirmar "
                    "/ confirm» o «cancelar / cancel»."
                ),
                "requiredResponseWords": [
                    "confirmar", "confirm", "cancelar", "cancel"
                ],
            },
        },
        {
            "case_id": "opaque-identities-hidden",
            "user_text": "Abre la nota que elegí.",
            "intent": "error",
            "facts": {
                "situation": (
                    "No pude abrir la nota elegida porque ya no está disponible."
                ),
                "internalIdentity": "note_opaque_0123456789abcdef",
                "correlationIdentity": "trace_opaque_0123456789abcdef",
            },
            "contains_any": ["no pude", "no está disponible", "no esta disponible"],
            "forbids": [
                "note_opaque_0123456789abcdef",
                "trace_opaque_0123456789abcdef",
            ],
        },
    ]


def _word_present(text: str, value: str) -> bool:
    return re.search(
        rf"(?<!\w){re.escape(value.casefold())}(?!\w)",
        text.casefold(),
    ) is not None


def _starts_with_request_imperative(text: str) -> bool:
    folded = fold(text)
    return re.search(
        r"^\s*(?:(?:list|show|tell|open|create|set|mute|close|delete|send)\b|"
        r"(?:lista|muestra)\s+(?:el|la|los|las|un|una)\b|"
        r"(?:dime|abre|crea|pon|silencia|cierra|elimina|envia)\b)",
        folded,
    ) is not None


def validate(case: dict[str, Any], reply: dict[str, Any], seconds: float) -> list[str]:
    errors: list[str] = []
    text = str(reply.get("text") or "").strip()
    facts = case["facts"]
    folded = fold(text)
    if reply.get("type") != "message.compose.result":
        errors.append("unexpected_response_type")
    if not text:
        errors.append("empty_response")
    if len(text) > 4096:
        errors.append("response_too_long")
    if seconds >= 10.25:
        errors.append("composition_budget_exceeded")
    if case["intent"] == "status" and _starts_with_request_imperative(text):
        errors.append("imperative_result")
    for fact in facts.get("requiredFacts", []):
        if str(fact).casefold() not in text.casefold():
            errors.append(f"missing_fact:{fact}")
    for action in facts.get("requiredActions", []):
        if not _word_present(text, str(action)):
            errors.append(f"missing_action:{action}")
    for word in facts.get("requiredResponseWords", []):
        if not _word_present(text, str(word)):
            errors.append(f"missing_choice:{word}")
    contains_any = [fold(str(value)) for value in case.get("contains_any", [])]
    if contains_any and not any(value in folded for value in contains_any):
        errors.append("missing_required_polarity")
    for value in (*FORBIDDEN_GLOBAL, *case.get("forbids", [])):
        if fold(str(value)) in folded:
            errors.append(f"forbidden:{value}")
    return errors


def composition_budget_seconds(facts: dict[str, Any]) -> float:
    required_facts = [str(value) for value in facts.get("requiredFacts", [])]
    return 10.0 if (
        facts.get("partialMission") is True
        or len(required_facts) >= 8
        or sum(len(value) for value in required_facts) >= 512
    ) else 5.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(0.95 * len(ordered) + 0.999) - 1))
    return ordered[rank]


def run(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError("refusing to overwrite an existing visible-response artifact")
    output.parent.mkdir(parents=True, exist_ok=True)
    runtime = resolve_runtime(manifest_path=args.runtime_manifest)
    manifest_before = file_sha256(args.runtime_manifest)
    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=environment,
        cwd=REPO,
    )
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar rejected its handshake")
        for case in build_cases():
            before = time.perf_counter()
            reply = client.request(
                {
                    "type": "message.compose",
                    "id": f"visible-{case['case_id']}",
                    "userText": case["user_text"],
                    "intent": case["intent"],
                    "facts": case["facts"],
                    "budgetSeconds": composition_budget_seconds(case["facts"]),
                },
                12.0,
            )
            seconds = time.perf_counter() - before
            errors = validate(case, reply, seconds)
            rows.append(
                {
                    "case_id": case["case_id"],
                    "intent": case["intent"],
                    "seconds": round(seconds, 6),
                    "response_type": reply.get("type"),
                    "text": reply.get("text"),
                    "passed": not errors,
                    "errors": errors,
                }
            )
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": "visible-shutdown"},
            timeout=limits["shutdown"],
        )

    latencies = [float(row["seconds"]) for row in rows]
    report = {
        "schema": "baxy.long-mission-visible-response.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "real_llm_message_compose_only_synthetic_verified_facts",
        "authority": "no_catalog_no_plan_no_core_request_no_provider_no_effect",
        "runtime": public_runtime_identity(runtime),
        "effects_executed": 0,
        "total_seconds": round(time.perf_counter() - started, 3),
        "metrics": {
            "passed": sum(bool(row["passed"]) for row in rows),
            "total": len(rows),
            "pass_rate": sum(bool(row["passed"]) for row in rows) / len(rows),
            "seconds_p50": statistics.median(latencies),
            "seconds_p95": _p95(latencies),
            "seconds_max": max(latencies),
        },
        "acceptance": {
            "all_cases_passed": all(bool(row["passed"]) for row in rows),
            "runtime_manifest_unchanged": (
                manifest_before == file_sha256(args.runtime_manifest)
            ),
            "zero_effects": True,
        },
        "source": {"probe_sha256": _sha256(Path(__file__).resolve())},
        "rows": rows,
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-manifest",
        type=Path,
        default=DEFAULT_RUNTIME_MANIFEST,
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = run(args)
    print(json.dumps({
        "metrics": report["metrics"],
        "acceptance": report["acceptance"],
        "failures": [
            {
                "case_id": row["case_id"],
                "text": row["text"],
                "errors": row["errors"],
            }
            for row in report["rows"]
            if not row["passed"]
        ],
        "effects_executed": report["effects_executed"],
    }, ensure_ascii=False, indent=2))
    return 0 if all(report["acceptance"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
