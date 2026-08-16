"""Measure compositional generalization without executing effects.

Each source action must already pass the reviewed current-catalogue probe. The
historical transform appends one independent local-time request. The extended
matrices compose independent read and action tails in both orders, in triads,
and through multiple natural connector/punctuation surfaces. Only
``turn.decide`` is sent; no plan, Core operation, or provider is invoked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from itertools import permutations
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike.probe_current_catalog_review import (  # noqa: E402
    CORPUS,
    _load_inputs,
    _read_audit,
)
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    file_sha256,
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

DEFAULT_BASE_REPORT = (
    REPO / "artifacts/fixes/current_catalog_review_product_probe_r28_extended_final.json"
)
DEFAULT_OUTPUT = REPO / "artifacts/fixes/catalog_pairwise_composition_r1.json"
DEFAULT_AUDIT = DEFAULT_OUTPUT.with_suffix(".raw.jsonl")

READ_ONLY_TAILS: tuple[dict[str, str], ...] = (
    {
        "tail_id": "time",
        "operation": "system.time",
        "en": "Tell me the local time.",
        "es": "Dime la hora local.",
    },
    {
        "tail_id": "tasks",
        "operation": "task.list",
        "en": "List my pending tasks.",
        "es": "Lista mis tareas pendientes.",
    },
    {
        "tail_id": "notes",
        "operation": "note.list",
        "en": "List my notes.",
        "es": "Lista mis notas.",
    },
    {
        "tail_id": "processes",
        "operation": "system.process.list",
        "en": "List the active processes.",
        "es": "Lista los procesos activos.",
    },
)

ACTION_TAILS: tuple[dict[str, str], ...] = (
    {
        "tail_id": "mute",
        "operation": "audio.mute",
        "en": "Mute the audio.",
        "es": "Silencia el audio.",
    },
    {
        "tail_id": "volume",
        "operation": "audio.volume",
        "en": "Set the volume to 17 percent.",
        "es": "Pon el volumen al 17 por ciento.",
    },
    {
        "tail_id": "task-create",
        "operation": "task.create",
        "en": "Create a task called Matrix Tail.",
        "es": "Crea una tarea llamada Cola Matriz.",
    },
    {
        "tail_id": "note-create",
        "operation": "note.create",
        "en": "Create a note titled Matrix Tail with content verified.",
        "es": "Crea una nota titulada Cola Matriz con contenido verificado.",
    },
)

TRIAD_SURFACE_PROFILES: tuple[str, ...] = (
    "semicolon_sequence",
    "conjunction_sequence",
    "after_that_sequence",
    "ordinal_sequence",
    "bare_semicolons",
)

TAIL_LEXICAL_VARIANTS: dict[str, dict[str, tuple[str, str]]] = {
    "time": {
        "en": (
            "What time is it now?",
            "What time does this computer show?",
        ),
        "es": (
            "¿Qué hora es ahora?",
            "¿Qué hora marca este equipo?",
        ),
    },
    "tasks": {
        "en": (
            "Show my tasks.",
            "Enumerate the pending tasks.",
        ),
        "es": (
            "Muéstrame mis tareas.",
            "Enumera las tareas pendientes.",
        ),
    },
    "notes": {
        "en": (
            "Show my saved notes.",
            "Enumerate my notes.",
        ),
        "es": (
            "Muéstrame mis notas guardadas.",
            "Enumera mis notas.",
        ),
    },
    "processes": {
        "en": (
            "Show the running processes.",
            "Enumerate active processes.",
        ),
        "es": (
            "Muéstrame los procesos en ejecución.",
            "Enumera los procesos activos.",
        ),
    },
    "mute": {
        "en": (
            "Put the audio on mute.",
            "Leave the sound on mute.",
        ),
        "es": (
            "Pon el audio en silencio.",
            "Deja el sonido en mudo.",
        ),
    },
    "volume": {
        "en": (
            "Adjust the volume to 17 percent.",
            "Change the sound to 17 percent.",
        ),
        "es": (
            "Ajusta el volumen al 17 por ciento.",
            "Cambia el sonido al 17 por ciento.",
        ),
    },
    "task-create": {
        "en": (
            "Add a task called Matrix Tail.",
            "Create Matrix Tail as a task.",
        ),
        "es": (
            "Añade una tarea llamada Cola Matriz.",
            "Agrega Cola Matriz como tarea.",
        ),
    },
    "note-create": {
        "en": (
            "Add a note called Matrix Tail saying verified.",
            "Create a note named Matrix Tail containing verified.",
        ),
        "es": (
            "Añade una nota llamada Cola Matriz que diga verificado.",
            "Guarda una nota Cola Matriz con el texto verificado.",
        ),
    },
}

QUAD_TAIL_GROUPS: tuple[tuple[str, str, str], ...] = (
    ("time", "tasks", "mute"),
    ("notes", "processes", "volume"),
    ("time", "notes", "task-create"),
    ("tasks", "processes", "note-create"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(0.95 * len(ordered) + 0.999) - 1))
    return ordered[rank]


def _render_triad_surface(
    parts: tuple[str, str, str],
    language: str,
    profile: str,
) -> str:
    first, second, third = parts
    if profile == "semicolon_sequence":
        if language == "en":
            return f"{first}; then {second}; finally {third}."
        return f"{first}; después {second}; finalmente {third}."
    if profile == "conjunction_sequence":
        if language == "en":
            return f"{first}, and then {second}, and finally {third}."
        return f"{first}, y luego {second}, y finalmente {third}."
    if profile == "after_that_sequence":
        if language == "en":
            return f"{first}. After that, {second}. Finally, {third}."
        return f"{first}. Después de eso, {second}. Finalmente, {third}."
    if profile == "ordinal_sequence":
        if language == "en":
            return f"First, {first}. Then {second}. Finally {third}."
        return f"Primero, {first}. Luego {second}. Finalmente {third}."
    if profile == "bare_semicolons":
        return f"{first}; {second}; {third}."
    raise ValueError(f"unsupported triad surface profile: {profile}")


def build_cases(
    base_report: Path,
    matrix: str = "time_suffix",
) -> list[dict[str, Any]]:
    source_rows, _ = _load_inputs()
    source_by_id = {str(row["case_id"]): row for row in source_rows}
    baseline = json.loads(base_report.read_text(encoding="utf-8"))
    passing_ids = {
        str(row["case_id"])
        for row in baseline.get("rows") or []
        if row.get("exact_turn_correct") is True
    }
    cases: list[dict[str, Any]] = []
    for case_id in sorted(passing_ids):
        row = source_by_id.get(case_id)
        if row is None or row.get("outcome") != "action":
            continue
        accepted = [
            list(dict.fromkeys(str(operation) for operation in operations))
            for operations in row.get("compatible_terminal_operation_sets") or []
        ]
        accepted = [operations for operations in accepted if operations]
        if not accepted:
            continue
        language = str(row.get("language") or "es")
        source_text = str(row["text"]).rstrip().rstrip(".?!")
        if matrix == "cross_quad":
            connector = "Then" if language == "en" else "Después"
            language_key = "en" if language == "en" else "es"
            tail_by_id = {
                tail["tail_id"]: tail
                for tail in (*READ_ONLY_TAILS, *ACTION_TAILS)
            }
            for group in QUAD_TAIL_GROUPS:
                group_tails = tuple(tail_by_id[tail_id] for tail_id in group)
                group_operations = {tail["operation"] for tail in group_tails}
                if any(
                    group_operations.intersection(operations)
                    for operations in accepted
                ):
                    continue
                block_names = ("base", *group)
                segments = {
                    "base": source_text,
                    **{
                        tail["tail_id"]: tail[language_key].rstrip(".?!")
                        for tail in group_tails
                    },
                }
                operation_by_block = {
                    tail["tail_id"]: tail["operation"]
                    for tail in group_tails
                }
                for order in permutations(block_names):
                    ordered_segments = tuple(segments[part] for part in order)
                    transformed = (
                        f"{ordered_segments[0]}. {connector} "
                        f"{ordered_segments[1]}. {connector} "
                        f"{ordered_segments[2]}. {connector} "
                        f"{ordered_segments[3]}."
                    )
                    expected_sets: list[list[str]] = []
                    for operations in accepted:
                        expected: list[str] = []
                        for part in order:
                            if part == "base":
                                expected.extend(operations)
                            else:
                                expected.append(operation_by_block[part])
                        expected_sets.append(expected)
                    order_id = ">".join(order)
                    cases.append(
                        {
                            "case_id": (
                                f"quad-{'+'.join(group)}-"
                                f"{'-'.join(order)}-{case_id}"
                            ),
                            "source_case_id": case_id,
                            "tail_id": "+".join(group),
                            "order": order_id,
                            "language": language,
                            "text": transformed,
                            "accepted_effect_operations": expected_sets,
                        }
                    )
            continue
        if matrix in {
            "cross_triad",
            "cross_triad_surface",
            "cross_triad_lexical",
            "cross_triad_surface_lexical",
        }:
            connector = "Then" if language == "en" else "Después"
            for read_tail, action_tail in zip(
                READ_ONLY_TAILS,
                ACTION_TAILS,
                strict=True,
            ):
                tail_operations = {
                    read_tail["operation"],
                    action_tail["operation"],
                }
                if any(
                    tail_operations.intersection(operations)
                    for operations in accepted
                ):
                    continue
                lexical_indexes: tuple[int | None, ...] = (
                    (0, 1)
                    if matrix
                    in {"cross_triad_lexical", "cross_triad_surface_lexical"}
                    else (None,)
                )
                for lexical_index in lexical_indexes:
                    language_key = "en" if language == "en" else "es"
                    read_text = (
                        TAIL_LEXICAL_VARIANTS[read_tail["tail_id"]][language_key][
                            lexical_index
                        ]
                        if lexical_index is not None
                        else read_tail[language_key]
                    )
                    action_text = (
                        TAIL_LEXICAL_VARIANTS[action_tail["tail_id"]][language_key][
                            lexical_index
                        ]
                        if lexical_index is not None
                        else action_tail[language_key]
                    )
                    segments = {
                        "base": source_text,
                        "read": read_text.rstrip(".?!"),
                        "action": action_text.rstrip(".?!"),
                    }
                    lexical_id = (
                        f"lexical_{lexical_index + 1}"
                        if lexical_index is not None
                        else "canonical"
                    )
                    for order in permutations(("base", "read", "action")):
                        ordered_segments = tuple(segments[part] for part in order)
                        surface_profiles: tuple[str | None, ...] = (
                            TRIAD_SURFACE_PROFILES
                            if matrix
                            in {"cross_triad_surface", "cross_triad_surface_lexical"}
                            else (None,)
                        )
                        expected_sets: list[list[str]] = []
                        for operations in accepted:
                            expected: list[str] = []
                            for part in order:
                                if part == "base":
                                    expected.extend(operations)
                                elif part == "read":
                                    expected.append(read_tail["operation"])
                                else:
                                    expected.append(action_tail["operation"])
                            expected_sets.append(expected)
                        for surface_profile in surface_profiles:
                            transformed = (
                                _render_triad_surface(
                                    ordered_segments,
                                    language,
                                    surface_profile,
                                )
                                if surface_profile is not None
                                else (
                                    f"{ordered_segments[0]}. {connector} "
                                    f"{ordered_segments[1]}. {connector} "
                                    f"{ordered_segments[2]}."
                                )
                            )
                            surface_id = surface_profile or "sentence_then"
                            variant_id = (
                                f"{surface_id}-{lexical_id}"
                                if lexical_index is not None
                                else surface_id
                            )
                            cases.append(
                                {
                                    "case_id": (
                                        f"triad-{variant_id}-"
                                        f"{read_tail['tail_id']}-"
                                        f"{action_tail['tail_id']}-"
                                        f"{'-'.join(order)}-{case_id}"
                                    ),
                                    "source_case_id": case_id,
                                    "tail_id": (
                                        f"{read_tail['tail_id']}+"
                                        f"{action_tail['tail_id']}"
                                    ),
                                    "order": "-".join(order),
                                    "surface_profile": surface_id,
                                    "lexical_profile": lexical_id,
                                    "language": language,
                                    "text": transformed,
                                    "accepted_effect_operations": expected_sets,
                                }
                            )
            continue
        tails = (
            READ_ONLY_TAILS[:1]
            if matrix == "time_suffix"
            else ACTION_TAILS
            if matrix == "cross_action_tail"
            else READ_ONLY_TAILS
        )
        orders = ("suffix",) if matrix == "time_suffix" else ("suffix", "prefix")
        for tail in tails:
            tail_operation = tail["operation"]
            if any(tail_operation in operations for operations in accepted):
                continue
            tail_text = tail["en" if language == "en" else "es"]
            connector = "Then" if language == "en" else "Después"
            for order in orders:
                if order == "suffix":
                    transformed = f"{source_text}. {connector} {tail_text}"
                    expected = [
                        [*operations, tail_operation]
                        for operations in accepted
                    ]
                else:
                    transformed = f"{tail_text} {connector} {source_text}."
                    expected = [
                        [tail_operation, *operations]
                        for operations in accepted
                    ]
                cases.append(
                    {
                        "case_id": (
                            f"pair-{tail['tail_id']}-{order}-{case_id}"
                        ),
                        "source_case_id": case_id,
                        "tail_id": tail["tail_id"],
                        "order": order,
                        "language": language,
                        "text": transformed,
                        "accepted_effect_operations": expected,
                    }
                )
    if not cases:
        raise RuntimeError("no passing catalogue actions were eligible for composition")
    return cases


def run(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output.resolve()
    audit = args.audit.resolve()
    base_report = args.base_report.resolve(strict=True)
    if output.exists() or audit.exists():
        raise RuntimeError("refusing to overwrite an existing pairwise artifact")
    output.parent.mkdir(parents=True, exist_ok=True)
    cases = build_cases(base_report, args.matrix)
    runtime = resolve_runtime(manifest_path=args.runtime_manifest)
    manifest_before = file_sha256(args.runtime_manifest)
    capabilities, application_catalog, game_catalog = current_core_catalog_snapshot(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    environment["BAXY_MIND_TURN_AUDIT_PATH"] = str(audit)
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=environment,
        cwd=REPO,
    )
    rows: list[dict[str, Any]] = []
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar rejected its handshake")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "catalog-pairwise",
                "capabilities": capabilities,
                "applicationCatalog": application_catalog,
                "gameCatalog": game_catalog,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("sidecar rejected the authenticated catalogue")
        client.request(
            {
                "type": "turn.decide",
                "id": "warm-pairwise",
                "text": "hola",
                "history": [],
                "uiLanguage": "es",
            },
            limits["turn.decide"],
        )
        for case in cases:
            request_id = str(case["case_id"])
            started = time.perf_counter()
            reply = client.request(
                {
                    "type": "turn.decide",
                    "id": request_id,
                    "text": case["text"],
                    "history": [],
                    "uiLanguage": case["language"],
                },
                limits["turn.decide"],
            )
            observed = list(reply.get("effectOperations") or [])
            exact = (
                reply.get("kind") == "plan"
                and observed in case["accepted_effect_operations"]
            )
            rows.append(
                {
                    **case,
                    "request_id": request_id,
                    "seconds": round(time.perf_counter() - started, 6),
                    "observed_kind": reply.get("kind"),
                    "observed_intent_operations": list(
                        reply.get("intentOperations") or []
                    ),
                    "observed_effect_operations": observed,
                    "exact": exact,
                }
            )
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": "shutdown-pairwise"},
            timeout=limits["shutdown"],
        )

    audits = _read_audit(audit, {str(row["request_id"]) for row in rows})
    for row in rows:
        turn_audit = audits[str(row["request_id"])]
        row["candidate_operations"] = turn_audit.get("candidate_operations") or []
        row["raw_decision"] = turn_audit.get("raw_decision")
        row["policy_stages"] = turn_audit.get("stages") or []
    latencies = [float(row["seconds"]) for row in rows]
    exact_count = sum(bool(row["exact"]) for row in rows)
    report = {
        "schema": "baxy.catalog-pairwise-composition-development.v2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "reviewed_leaf_to_independent_time_pair_not_blind"
            if args.matrix == "time_suffix"
            else "reviewed_leaf_cross_action_tail_bidirectional_pairs_not_blind"
            if args.matrix == "cross_action_tail"
            else "reviewed_leaf_read_action_triad_all_positions_not_blind"
            if args.matrix == "cross_triad"
            else "reviewed_leaf_read_action_triad_surface_invariance_not_blind"
            if args.matrix == "cross_triad_surface"
            else "reviewed_leaf_read_action_triad_lexical_invariance_not_blind"
            if args.matrix == "cross_triad_lexical"
            else "reviewed_leaf_read_action_triad_surface_lexical_cross_not_blind"
            if args.matrix == "cross_triad_surface_lexical"
            else "reviewed_leaf_three_independent_tails_quad_all_positions_not_blind"
            if args.matrix == "cross_quad"
            else "reviewed_leaf_cross_tail_bidirectional_pairs_not_blind"
        ),
        "authority": "turn.decide_only_no_plan_or_operation_dispatched",
        "effects_executed": 0,
        "runtime": public_runtime_identity(runtime),
        "metrics": {
            "exact": exact_count,
            "total": len(rows),
            "exact_accuracy": exact_count / len(rows),
            "unsafe_effects": 0,
            "turn_decide_seconds_p50": statistics.median(latencies),
            "turn_decide_seconds_p95": _p95(latencies),
        },
        "acceptance": {
            "all_pairs_exact": exact_count == len(rows),
            "zero_effects_executed": True,
            "runtime_manifest_unchanged": (
                manifest_before == file_sha256(args.runtime_manifest)
            ),
        },
        "source": {
            "probe_sha256": _sha256(Path(__file__).resolve()),
            "corpus": str(CORPUS.relative_to(REPO)).replace("\\", "/"),
            "corpus_sha256": _sha256(CORPUS),
            "base_report": str(base_report.relative_to(REPO)).replace("\\", "/"),
            "base_report_sha256": _sha256(base_report),
            "audit": str(audit.relative_to(REPO)).replace("\\", "/"),
            "audit_sha256": _sha256(audit),
        },
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
    parser.add_argument("--base-report", type=Path, default=DEFAULT_BASE_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument(
        "--matrix",
        choices=(
            "time_suffix",
            "cross_tail",
            "cross_action_tail",
            "cross_triad",
            "cross_triad_surface",
            "cross_triad_lexical",
            "cross_triad_surface_lexical",
            "cross_quad",
        ),
        default="time_suffix",
    )
    args = parser.parse_args()
    report = run(args)
    print(
        json.dumps(
            {
                "metrics": report["metrics"],
                "acceptance": report["acceptance"],
                "failures": [
                    {
                        "case_id": row["case_id"],
                        "expected": row["accepted_effect_operations"],
                        "kind": row["observed_kind"],
                        "effects": row["observed_effect_operations"],
                    }
                    for row in report["rows"]
                    if not row["exact"]
                ],
                "effects_executed": report["effects_executed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if all(report["acceptance"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
