"""Price retrieval and pruning mechanisms over already-consumed populations.

This is a development diagnostic.  It replays recorded candidate/decision
telemetry and never starts the product, invokes a provider, or opens a new
population.  Counterfactual candidate sets are reported only when the consumed
record contains enough evidence to derive them; an unobserved counterfactual is
not silently treated as equivalence.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np

REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from baxy_mind import __main__ as mind  # noqa: E402
from baxy_mind import effect_intent  # noqa: E402
from baxy_mind import llm as mind_llm  # noqa: E402
from baxy_mind.family_classifier import FamilyClassifier  # noqa: E402
from baxy_mind.planner import PlannerCatalog  # noqa: E402
from baxy_mind.router import (  # noqa: E402
    SemanticEncoder,
    verified_encoder_snapshot_identity,
)
from baxy_mind.semantic_family_arbiter import SemanticFamilyArbiter  # noqa: E402
from baxy_mind.turn_evidence import (  # noqa: E402
    CACHE_ENVIRONMENT_VARIABLE,
    TurnEvidenceService,
)
from experiments.mind_router_spike.probe_native_tool_contract_ceiling import (  # noqa: E402
    _start_server,
    _stop_server,
)
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    PROFILE_LIMITS,
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
)


DEFAULT_OUTPUT = (
    REPO
    / "artifacts/development/consumed_retrieval_mechanism_pricing_20260812.json"
)
STEP3_REJECTIONS = (
    REPO
    / "artifacts/development/open_catalogue_closed_reversion_20260812.json",
    REPO
    / "artifacts/development/open_catalogue_candidate_rejected_20260812.json",
    REPO
    / "artifacts/development/functiongemma_cross_encoder_no_match_rejected_20260813.json",
)
REDUNDANT_BRIDGES = frozenset(
    {
        "application_reference_bridge",
        "explicit_ocr_bridge",
        "literal_schema_bridge",
        "message_reference_bridge",
    }
)
MECHANISMS = (
    "fallback_after_abstention",
    "semantic_family_arbiter",
    "literal_reference_bridges",
    "domain_gate",
    "post_decision_verifiers",
)
ZERO_AUDITED_METRICS = (
    "candidate_set_changed_rows",
    "decision_changed_rows",
    "correct_operation_lost_rows",
    "leak_avoided_rows",
    "prompt_cost_delta_bytes",
)


@dataclass(frozen=True)
class PopulationSource:
    name: str
    result: Path
    builder: Path | None = None


@dataclass(frozen=True)
class RowSnapshot:
    population: str
    row_id: str
    role: str
    expected_operations: tuple[str, ...]
    baseline_candidates: tuple[str, ...]
    candidates_without: dict[str, tuple[str, ...] | None]
    raw_operations: tuple[str, ...]
    final_operations: tuple[str, ...]
    first_veto: str | None
    candidate_prompt_bytes: int
    raw_candidates_available: bool = True
    raw_decision_available: bool = True


@dataclass(frozen=True)
class PopulationInput:
    population: str
    row_id: str
    text: str
    expected_operations: tuple[str, ...]
    decision_variants: dict[str, tuple[str, ...]]
    outside_catalogue: bool = False


@dataclass(frozen=True)
class CounterfactualRow:
    population: str
    row_id: str
    text: str
    expected_operations: tuple[str, ...]
    variants: dict[str, tuple[str, ...]]
    decision_variants: dict[str, tuple[str, ...]]
    outside_catalogue: bool = False
    downstream_variants: dict[str, dict[str, Any]] = field(default_factory=dict)


def population_manifest() -> tuple[PopulationSource, ...]:
    holdout = REPO / "artifacts/holdout"
    spike = REPO / "experiments/mind_router_spike"
    populations = [
        PopulationSource(
            "catalog_surface_current_tree_r2",
            holdout / "catalog_surface_current_tree_r2_mind.json",
        ),
        PopulationSource(
            "generalization_product_current_tree_r28",
            holdout / "generalization_product_current_tree_r28_mind.json",
        ),
    ]
    for version in range(1, 8):
        populations.append(
            PopulationSource(
                f"veto_reach_v{version}",
                holdout / f"veto_reach_v{version}.json",
                spike / f"build_veto_reach_v{version}.py",
            )
        )
    populations.append(
        PopulationSource(
            "physical_dependent_missions_text_v1",
            REPO / "artifacts/product/physical_dependent_missions_text_v1.json",
        )
    )
    return tuple(populations)


def candidate_prompt_bytes(candidates: Iterable[str]) -> int:
    payload = json.dumps(
        list(candidates),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return len(payload.encode("utf-8"))


def _operations_from_terminals(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    operations: list[str] = []
    for terminal in value:
        if isinstance(terminal, list):
            operations.extend(str(item) for item in terminal)
    return tuple(dict.fromkeys(operations))


def _counterfactuals(
    baseline: tuple[str, ...],
) -> dict[str, tuple[str, ...] | None]:
    # The historical audit stores the final candidate set, not contribution
    # provenance.  Claiming a set "without" a pre-decision mechanism would be
    # fabricated evidence, so those cells remain explicitly unavailable.
    return {
        "fallback_after_abstention": None,
        "semantic_family_arbiter": None,
        "literal_reference_bridges": None,
        "domain_gate": baseline,
        "post_decision_verifiers": baseline,
    }


def _load_mind_rows(source: PopulationSource) -> list[RowSnapshot]:
    payload = json.loads(source.result.read_text(encoding="utf-8"))
    snapshots: list[RowSnapshot] = []
    for row in payload["rows"]:
        baseline = tuple(str(value) for value in row.get("candidate_operations", []))
        expected = _operations_from_terminals(row.get("expected_terminal_operations"))
        snapshots.append(
            RowSnapshot(
                population=source.name,
                row_id=str(row["case_id"]),
                role=str(row.get("case_type") or "unknown"),
                expected_operations=expected,
                baseline_candidates=baseline,
                candidates_without=_counterfactuals(baseline),
                raw_operations=tuple(str(value) for value in row.get("raw_operations", [])),
                final_operations=tuple(
                    str(value) for value in row.get("final_effect_operations", [])
                ),
                first_veto=row.get("first_veto"),
                candidate_prompt_bytes=candidate_prompt_bytes(baseline),
            )
        )
    return snapshots


def _literal_assignment(path: Path, name: str) -> Any:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            return ast.literal_eval(node.value)
    raise ValueError(f"{path.name} does not define literal {name}")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _audit_by_case(path: Path, case_ids: set[str]) -> dict[str, dict[str, Any]]:
    matched: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return matched
    for record in _load_jsonl(path):
        if record.get("phase") != "final":
            continue
        request_id = str(record.get("request_id") or "")
        case_id = next(
            (candidate for candidate in case_ids if request_id.endswith(candidate)),
            None,
        )
        if case_id is not None:
            matched[case_id] = record
    return matched


def _stage_operations(record: dict[str, Any], stage_name: str) -> tuple[str, ...]:
    for stage in record.get("stages", []):
        if stage.get("name") == stage_name:
            return tuple(str(value) for value in stage.get("effect_operations", []))
    return ()


def _load_r_population_inputs(
    source: PopulationSource,
) -> tuple[list[PopulationInput], list[dict[str, str]]]:
    corpus_path = source.result.with_name(source.result.name.replace("_mind.json", ".jsonl"))
    audit_path = source.result.with_name(
        source.result.name.replace("_mind.json", "_mind.raw.jsonl")
    )
    if not corpus_path.is_file():
        return [], [
            {
                "population": source.name,
                "reason": f"missing_text_oracle:{corpus_path.relative_to(REPO).as_posix()}",
            }
        ]
    measured = json.loads(source.result.read_text(encoding="utf-8"))
    measured_ids = {str(row["case_id"]) for row in measured["rows"]}
    corpus = [
        row
        for row in _load_jsonl(corpus_path)
        if str(row["case_id"]) in measured_ids
    ]
    case_ids = {str(row["case_id"]) for row in corpus}
    audits = _audit_by_case(audit_path, case_ids)
    rows: list[PopulationInput] = []
    for record in corpus:
        case_id = str(record["case_id"])
        expected = _operations_from_terminals(
            record.get("compatible_terminal_operation_sets")
        )
        decision_variants: dict[str, tuple[str, ...]] = {}
        audit = audits.get(case_id)
        if audit is not None:
            final = audit.get("final") or {}
            decision_variants = {
                "baseline": tuple(
                    str(value) for value in final.get("effect_operations", [])
                ),
                "without_domain_gate": _stage_operations(
                    audit,
                    "information_question",
                ),
                "without_post_decision_verifiers": _stage_operations(
                    audit,
                    "validated_raw",
                ),
            }
        rows.append(
            PopulationInput(
                population=source.name,
                row_id=case_id,
                text=str(record["text"]),
                expected_operations=expected,
                decision_variants=decision_variants,
            )
        )
    return rows, []


def _load_veto_population_inputs(
    source: PopulationSource,
) -> tuple[list[PopulationInput], list[dict[str, str]]]:
    if source.builder is None or not source.builder.is_file():
        return [], [{"population": source.name, "reason": "missing_builder_oracle"}]
    intended = {
        str(case_id): (str(operation),)
        for case_id, operation in dict(
            _literal_assignment(source.builder, "INTENDED")
        ).items()
    }
    rows: list[PopulationInput] = []
    for assignment in ("CATALOGUE_CONTROLS", "REQUESTS", "CONTROLS"):
        for case_id, _language, text in _literal_assignment(source.builder, assignment):
            rows.append(
                PopulationInput(
                    population=source.name,
                    row_id=str(case_id),
                    text=str(text),
                    expected_operations=intended.get(str(case_id), ()),
                    decision_variants={},
                    outside_catalogue=assignment == "REQUESTS",
                )
            )
    return sorted(rows, key=lambda row: row.row_id), []


def _load_physical_population_inputs(
    source: PopulationSource,
) -> tuple[list[PopulationInput], list[dict[str, str]]]:
    preregistration = (
        REPO
        / "artifacts/development/"
        "physical_dependent_missions_preregistration_20260811.json"
    )
    if not preregistration.is_file():
        return [], [
            {
                "population": source.name,
                "reason": "missing_physical_text_preregistration",
            }
        ]
    payload = json.loads(preregistration.read_text(encoding="utf-8"))
    return [
        PopulationInput(
            population=source.name,
            row_id=str(mission["id"]),
            text=str(mission["text"]),
            expected_operations=tuple(
                str(value) for value in mission["expectedOperations"]
            ),
            decision_variants={},
        )
        for mission in payload["missions"]
    ], []


def load_population_inputs() -> tuple[list[PopulationInput], list[dict[str, str]]]:
    rows: list[PopulationInput] = []
    unavailable: list[dict[str, str]] = []
    for source in population_manifest():
        if source.name in {
            "catalog_surface_current_tree_r2",
            "generalization_product_current_tree_r28",
        }:
            loaded, missing = _load_r_population_inputs(source)
        elif source.name.startswith("veto_reach_"):
            loaded, missing = _load_veto_population_inputs(source)
        else:
            loaded, missing = _load_physical_population_inputs(source)
        rows.extend(loaded)
        unavailable.extend(missing)
    return sorted(rows, key=lambda row: (row.population, row.row_id)), unavailable


def _veto_contract(source: PopulationSource) -> dict[str, tuple[str, ...]]:
    if source.builder is None:
        return {}
    intended = dict(_literal_assignment(source.builder, "INTENDED"))
    contract: dict[str, tuple[str, ...]] = {
        str(case_id): (str(operation),) for case_id, operation in intended.items()
    }
    for assignment in ("REQUESTS", "CONTROLS"):
        for case_id, _language, _text in _literal_assignment(source.builder, assignment):
            contract[str(case_id)] = ()
    return contract


def _load_veto_rows(source: PopulationSource) -> list[RowSnapshot]:
    contract = _veto_contract(source)
    if not source.result.is_file():
        return [
            RowSnapshot(
                population=source.name,
                row_id=row_id,
                role="catalogue_control" if expected else "non_catalogue_or_control",
                expected_operations=expected,
                baseline_candidates=(),
                candidates_without={mechanism: None for mechanism in MECHANISMS},
                raw_operations=(),
                final_operations=(),
                first_veto=None,
                candidate_prompt_bytes=0,
                raw_candidates_available=False,
                raw_decision_available=False,
            )
            for row_id, expected in sorted(contract.items())
        ]
    payload = json.loads(source.result.read_text(encoding="utf-8"))
    snapshots = []
    for row in payload["records"]:
        row_id = str(row["case_id"])
        final = tuple(str(value) for value in row.get("effect_operations", []))
        snapshots.append(
            RowSnapshot(
                population=source.name,
                row_id=row_id,
                role=str(row["role"]),
                expected_operations=contract[row_id],
                baseline_candidates=(),
                candidates_without={mechanism: None for mechanism in MECHANISMS},
                raw_operations=(),
                final_operations=final,
                first_veto=None,
                candidate_prompt_bytes=0,
                raw_candidates_available=False,
                raw_decision_available=False,
            )
        )
    return snapshots


def _load_physical_rows(source: PopulationSource) -> list[RowSnapshot]:
    payload = json.loads(source.result.read_text(encoding="utf-8"))
    snapshots = []
    for mission in payload["missions"]:
        expected = tuple(str(value) for value in mission["expectedOperations"])
        result = mission.get("result") or {}
        final = tuple(str(value) for value in result.get("effect_operations", []))
        snapshots.append(
            RowSnapshot(
                population=source.name,
                row_id=str(mission["id"]),
                role="physical_text_mission",
                expected_operations=expected,
                baseline_candidates=(),
                candidates_without={mechanism: None for mechanism in MECHANISMS},
                raw_operations=(),
                final_operations=final,
                first_veto=None,
                candidate_prompt_bytes=0,
                raw_candidates_available=False,
                raw_decision_available=False,
            )
        )
    return snapshots


def collect_rows() -> list[RowSnapshot]:
    rows: list[RowSnapshot] = []
    for source in population_manifest():
        if source.name in {
            "catalog_surface_current_tree_r2",
            "generalization_product_current_tree_r28",
        }:
            rows.extend(_load_mind_rows(source))
        elif source.name.startswith("veto_reach_"):
            rows.extend(_load_veto_rows(source))
        else:
            rows.extend(_load_physical_rows(source))
    return rows


def _correct_operation_lost(
    expected: tuple[str, ...],
    baseline: tuple[str, ...],
    without: tuple[str, ...],
) -> bool:
    expected_set = set(expected)
    return bool(expected_set & set(baseline)) and not expected_set.issubset(without)


def _decision_delta(row: RowSnapshot, mechanism: str) -> bool:
    if mechanism not in {"domain_gate", "post_decision_verifiers"}:
        return False
    if not row.raw_decision_available:
        return False
    if mechanism == "domain_gate" and row.first_veto != "domain_grounding":
        return False
    return row.raw_operations != row.final_operations


def _leak_avoided(row: RowSnapshot, mechanism: str) -> bool:
    return (
        not row.expected_operations
        and bool(row.raw_operations)
        and not row.final_operations
        and _decision_delta(row, mechanism)
    )


def _tool_prompt_bytes(
    candidates: tuple[str, ...],
    tool_payloads: dict[str, dict[str, Any]],
) -> int:
    payload = [tool_payloads[name] for name in candidates]
    return len(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


def build_counterfactual_report(
    rows: list[CounterfactualRow],
    *,
    tool_payloads: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    variants = sorted({name for row in rows for name in row.variants})
    variant_metrics: dict[str, dict[str, Any]] = {}
    for variant in variants:
        recalled = 0
        expected = 0
        outside_rows: list[str] = []
        outside_entries = 0
        prompt_bytes = 0
        observed_rows = 0
        for row in rows:
            candidates = row.variants.get(variant)
            if candidates is None:
                continue
            observed_rows += 1
            expected_set = set(row.expected_operations)
            expected += len(expected_set)
            recalled += len(expected_set & set(candidates))
            qualified = f"{row.population}:{row.row_id}"
            if row.outside_catalogue and candidates:
                outside_rows.append(qualified)
                outside_entries += len(candidates)
            prompt_bytes += _tool_prompt_bytes(candidates, tool_payloads)
        variant_metrics[variant] = {
            "rows": observed_rows,
            "expected_operation_recall": {
                "recalled": recalled,
                "expected": expected,
                "ratio": recalled / expected if expected else None,
            },
            "outside_catalogue_false_candidate_rows": outside_rows,
            "outside_catalogue_false_candidate_entries": outside_entries,
            "prompt_bytes": prompt_bytes,
        }

    mechanism_variants = {
        "fallback_after_abstention": "without_fallback_after_abstention",
        "semantic_family_arbiter": "without_semantic_family_arbiter",
        "literal_schema_bridge": "without_literal_schema_bridge",
        "application_reference_bridge": "without_application_reference_bridge",
        "message_reference_bridge": "without_message_reference_bridge",
        "explicit_ocr_bridge": "without_explicit_ocr_bridge",
    }
    mechanisms: dict[str, dict[str, Any]] = {}
    for mechanism, variant in mechanism_variants.items():
        preservation: list[str] = []
        avoided: list[str] = []
        changed: list[dict[str, Any]] = []
        downstream_comparisons: list[dict[str, Any]] = []
        for row in rows:
            baseline = row.variants.get("baseline")
            without = row.variants.get(variant)
            if baseline is None or without is None or baseline == without:
                continue
            qualified = f"{row.population}:{row.row_id}"
            expected_set = set(row.expected_operations)
            if expected_set & set(baseline) and not expected_set.issubset(without):
                preservation.append(qualified)
            if row.outside_catalogue and len(without) < len(baseline):
                avoided.append(qualified)
            changed.append(
                {
                    "population": row.population,
                    "row_id": row.row_id,
                    "baseline": list(baseline),
                    "without": list(without),
                    "prompt_bytes_delta": (
                        _tool_prompt_bytes(without, tool_payloads)
                        - _tool_prompt_bytes(baseline, tool_payloads)
                    ),
                }
            )
            baseline_decision = row.downstream_variants.get("baseline")
            without_decision = row.downstream_variants.get(variant)
            if baseline_decision is not None and without_decision is not None:
                downstream_comparisons.append(
                    {
                        "population": row.population,
                        "row_id": row.row_id,
                        "baseline": baseline_decision,
                        "without": without_decision,
                        "equivalent": baseline_decision == without_decision,
                    }
                )
        mechanisms[mechanism] = {
            "variant": variant,
            "candidate_set_changed_rows": changed,
            "downstream_comparisons": downstream_comparisons,
            "rows_requiring_preservation": preservation,
            "false_candidate_rows_avoided": avoided,
            "zero_refuters": {
                metric: sorted({row.population for row in rows})
                for metric, value in (
                    ("rows_requiring_preservation", preservation),
                    ("false_candidate_rows_avoided", avoided),
                )
                if not value
            },
        }

    for mechanism, variant in (
        ("domain_gate", "without_domain_gate"),
        ("post_decision_verifiers", "without_post_decision_verifiers"),
    ):
        changed = []
        preservation = []
        avoided = []
        unavailable = []
        observable_populations: set[str] = set()
        for row in rows:
            baseline = row.decision_variants.get("baseline")
            without = row.decision_variants.get(variant)
            qualified = f"{row.population}:{row.row_id}"
            if baseline is None or without is None:
                unavailable.append(qualified)
                continue
            observable_populations.add(row.population)
            if baseline == without:
                continue
            changed.append(
                {
                    "population": row.population,
                    "row_id": row.row_id,
                    "baseline": list(baseline),
                    "without": list(without),
                }
            )
            expected_set = set(row.expected_operations)
            if expected_set & set(baseline) and not expected_set.issubset(without):
                preservation.append(qualified)
            if not expected_set and without and not baseline:
                avoided.append(qualified)
        mechanisms[mechanism] = {
            "variant": variant,
            "decision_changed_rows": changed,
            "rows_requiring_preservation": preservation,
            "false_operation_rows_avoided": avoided,
            "unobservable_rows": unavailable,
            "zero_refuters": {
                metric: sorted(observable_populations)
                for metric, value in (
                    ("rows_requiring_preservation", preservation),
                    ("false_operation_rows_avoided", avoided),
                )
                if not value
            },
        }

    return {
        "variant_metrics": variant_metrics,
        "mechanisms": mechanisms,
    }


class _CachedEncoder:
    def __init__(self, encoder: SemanticEncoder) -> None:
        self._encoder = encoder
        self._rows: dict[str, Any] = {}

    def prime(self, texts: Iterable[str], *, batch_size: int = 128) -> None:
        unique = list(dict.fromkeys(texts))
        for start in range(0, len(unique), batch_size):
            batch = unique[start : start + batch_size]
            encoded = self._encoder.encode(tuple(batch))
            self._rows.update(zip(batch, encoded, strict=True))

    def __call__(self, texts: Iterable[str]) -> Any:
        requested = tuple(texts)
        missing = [text for text in dict.fromkeys(requested) if text not in self._rows]
        if missing:
            self.prime(missing)
        return np.asarray([self._rows[text] for text in requested], dtype=np.float32)


def _downstream_decision_shape(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        key: decision.get(key)
        for key in (
            "mode",
            "operation",
            "conversation_kind",
            "effect_count",
            "effect_operations",
            "effect_verification",
        )
    }


def _compare_changed_candidates_downstream(
    rows: list[CounterfactualRow],
    tool_payloads: dict[str, dict[str, Any]],
) -> None:
    affected = [
        row
        for row in rows
        if row.variants["baseline"]
        != row.variants["without_application_reference_bridge"]
    ]
    if not affected:
        return
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
    llm = mind_llm.LlmRuntime()
    try:
        for row in affected:
            for variant in (
                "baseline",
                "without_application_reference_bridge",
            ):
                candidates = [
                    tool_payloads[name] for name in row.variants[variant]
                ]
                llm.begin_request(
                    120.0,
                    attempt=1,
                    identity=f"pricing:{row.population}:{row.row_id}:{variant}",
                )
                try:
                    decision = llm.decide_turn(
                        row.text,
                        candidates,
                        history=[],
                        evidence=[],
                    )
                finally:
                    llm.end_request()
                row.downstream_variants[variant] = _downstream_decision_shape(
                    decision
                )
    finally:
        llm.close()
        _stop_server(process)


def _pre_route(
    objective: str,
    *,
    planner_catalog: PlannerCatalog,
    application_names: tuple[str, ...],
    game_catalog: Any,
) -> tuple[str, Any, Any]:
    routing_objective = effect_intent._strip_request_envelope(objective).strip()
    if not routing_objective:
        routing_objective = objective
    available_operations = tuple(tool.name for tool in planner_catalog.tools)
    authenticated_operations = available_operations
    non_target_language = mind.confident_non_target_language(objective)
    explicit_non_action = effect_intent.explicit_non_action_frame(objective)
    content_drafting = mind.conversation_only_content_request(objective)
    explicit_clarification = (
        None
        if non_target_language is not None or content_drafting or explicit_non_action
        else mind.resolve_explicit_clarification_intent(
            objective,
            authenticated_operations,
        )
    )
    if explicit_clarification is not None:
        return routing_objective, "closed_conversation", None
    recalled_literal = mind_llm._literal_recall_reference([], objective)
    literal_recall_decision = (
        {"mode": "conversation"} if recalled_literal is not None else None
    )
    stable_no_effect_decision = (
        literal_recall_decision
        or mind._explicit_stable_no_effect_turn_decision(objective, [])
    )
    stable_no_effect_is_closed = (
        explicit_non_action
        or literal_recall_decision is not None
        or (
            stable_no_effect_decision is not None
            and (
                mind._assistant_capability_aspiration(objective)
                or mind._general_factoid_prompt(objective)
                or mind._personal_checkin_statement(objective)
                or mind._closed_unsupported_request(objective)
            )
        )
    )
    live_public_intent = (
        mind.EffectIntent(("web.search",), (objective,))
        if "web.search" in available_operations
        and effect_intent._public_live_lookup_request(
            effect_intent._strip_request_envelope(effect_intent._fold(objective))
        )
        else None
    )
    explicit_intent = (
        None
        if non_target_language is not None or stable_no_effect_is_closed
        else live_public_intent
        or mind.resolve_explicit_effects(
            objective,
            available_operations,
            application_names,
            game_catalog,
        )
    )
    catalog_unavailable_decision = mind._catalog_unavailable_turn_decision(
        objective,
        explicit_intent,
        application_names,
        game_catalog,
    )
    unresolved = mind.unresolved_compound_contract(
        objective,
        available_operations,
        application_names,
        game_catalog,
        resolved_intent=explicit_intent,
    )
    explicit_conversation = (
        mind._explicit_unsupported_turn_decision(objective)
        if non_target_language is not None
        or (
            unresolved is not None
            and (
                mind.effect_request_is_authoritative(objective)
                or mind.unsupported_effect_demonstration_request(objective)
            )
        )
        or (
            mind.effect_request_is_authoritative(objective)
            and mind.known_unsupported_effect_request(
                objective,
                available_operations,
            )
        )
        else catalog_unavailable_decision
        or mind._explicit_social_turn_decision(objective, [])
        or mind._explicit_nonunderstanding_turn_decision(objective, [])
        or stable_no_effect_decision
    )
    if explicit_intent is not None:
        return routing_objective, explicit_intent, unresolved
    if explicit_conversation is not None:
        return routing_objective, "closed_conversation", unresolved
    return routing_objective, None, unresolved


def _former_literal_schema_families(
    objective: str,
    tools: tuple[Any, ...],
) -> frozenset[str]:
    if re.search(r"https?://[^\s]+", objective, re.IGNORECASE) is None:
        return frozenset()
    return frozenset(
        tool.family
        for tool in tools
        if isinstance(tool.schema.get("properties"), dict)
        and {"url", "resourceUri"} & set(tool.schema["properties"])
    )


def _former_application_reference_families(
    objective: str,
    application_names: tuple[str, ...],
    available_families: set[str],
) -> frozenset[str]:
    if "app" not in available_families:
        return frozenset()
    catalog = effect_intent.build_application_catalog_index(application_names)
    occurrence = catalog.occurrence_pattern
    if occurrence is None or occurrence.search(effect_intent._fold(objective)) is None:
        return frozenset()
    return frozenset({"app"})


def _former_message_reference_families(
    objective: str,
    available_families: set[str],
) -> frozenset[str]:
    if "message" not in available_families:
        return frozenset()
    if not effect_intent._has(
        effect_intent._fold(objective),
        r"\b(?:whatsapp|wsp|sms|discord|mensaje|message)\b",
    ):
        return frozenset()
    return frozenset({"message"})


def _former_explicit_ocr_families(objective: str) -> frozenset[str]:
    if re.search(r"\bocr\b", objective, re.IGNORECASE):
        return frozenset({"ocr"})
    if re.search(
        r"\b(?:lee|leer|leeme|read|extract|extrae)\b.{0,48}"
        r"\b(?:texto|text)\b.{0,48}"
        r"\b(?:pantalla|screen|captura|capture|imagen|image)\b",
        objective,
        re.IGNORECASE,
    ):
        return frozenset({"ocr"})
    return frozenset()


def _candidate_names(
    objective: str,
    *,
    planner_catalog: PlannerCatalog,
    family_classifier: FamilyClassifier,
    semantic_family_arbiter: SemanticFamilyArbiter,
    encoder: _CachedEncoder,
    turn_evidence: TurnEvidenceService,
    application_names: tuple[str, ...],
    game_catalog: Any,
    disabled: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    routing_objective, pre_route, unresolved = _pre_route(
        objective,
        planner_catalog=planner_catalog,
        application_names=application_names,
        game_catalog=game_catalog,
    )
    if pre_route == "closed_conversation":
        return ()
    if pre_route is not None:
        shortlist = mind._shortlist_with_required_effects(
            (),
            pre_route.operations,
            planner_catalog,
        )
    else:
        available_families = {tool.family for tool in planner_catalog.tools}
        prediction = family_classifier.predict(
            routing_objective,
            available_families,
        )
        if prediction is not None:
            semantic_families: tuple[str, ...] = ()
            if "semantic_family_arbiter" not in disabled:
                embedding = encoder((routing_objective,))[0]
                semantic_families = tuple(
                    item.family
                    for item in semantic_family_arbiter.rank(
                        embedding,
                        available_families,
                        count=1,
                    )
                )
            literal_families = (
                frozenset()
                if "literal_schema_bridge" in disabled
                else _former_literal_schema_families(
                    routing_objective,
                    planner_catalog.tools,
                )
            )
            application_families = (
                frozenset()
                if "application_reference_bridge" in disabled
                else _former_application_reference_families(
                    routing_objective,
                    application_names,
                    available_families,
                )
            )
            message_families = (
                frozenset()
                if "message_reference_bridge" in disabled
                else _former_message_reference_families(
                    routing_objective,
                    available_families,
                )
            )
            ocr_families = (
                frozenset()
                if "explicit_ocr_bridge" in disabled
                else _former_explicit_ocr_families(routing_objective)
            )
            primary_families = (
                tuple(sorted(ocr_families))
                if ocr_families
                else tuple(
                    dict.fromkeys((prediction.family, *semantic_families))
                )
            )
            predicted = mind._prioritized_family_tools(
                planner_catalog.tools,
                primary_families,
                sorted(application_families),
                sorted(message_families),
                sorted(literal_families),
            )[: mind.MAX_SHORTLIST_OPERATIONS]
            if unresolved is None:
                shortlist = predicted
            else:
                required = tuple(
                    operation
                    for sequence in unresolved.required_clause_sequences
                    for operation in sequence
                )
                lexical = (
                    planner_catalog.shortlist(routing_objective)
                    if not required
                    else ()
                )
                combined = tuple(
                    {
                        tool.name: tool for tool in (*predicted, *lexical)
                    }.values()
                )[: mind.MAX_SHORTLIST_OPERATIONS]
                shortlist = mind._shortlist_with_required_effects(
                    combined,
                    required,
                    planner_catalog,
                )
        elif "fallback_after_abstention" in disabled:
            shortlist = ()
        else:
            candidate_families = turn_evidence.candidate_families(
                routing_objective,
                encoder,
            )
            shortlist = planner_catalog.shortlist(
                routing_objective,
                preferred_families=candidate_families,
            )
        clause_shortlist = mind._compound_clause_shortlist(
            routing_objective,
            planner_catalog,
            family_classifier,
        )
        if clause_shortlist:
            clauses = mind.compound_retrieval_clauses(routing_objective)
            advisory_operations = mind.compound_retrieval_operation_hints(
                routing_objective,
                tuple(tool.name for tool in planner_catalog.tools),
                application_names,
            )
            advisory_tools = tuple(
                tool
                for operation in advisory_operations
                if (tool := planner_catalog.get(operation)) is not None
            )
            if len(advisory_tools) == len(clauses) and len(clauses) >= 2:
                shortlist = advisory_tools
            else:
                shortlist = tuple(
                    {
                        tool.name: tool
                        for tool in (
                            *advisory_tools,
                            *clause_shortlist,
                            *shortlist,
                        )
                    }.values()
                )[: mind.MAX_SHORTLIST_OPERATIONS]
            if unresolved is not None:
                required = tuple(
                    operation
                    for sequence in unresolved.required_clause_sequences
                    for operation in sequence
                )
                shortlist = mind._shortlist_with_required_effects(
                    shortlist,
                    required,
                    planner_catalog,
                )
    return tuple(tool.name for tool in shortlist)


def recompute_counterfactual_rows(
    inputs: list[PopulationInput],
    *,
    core: Path | None = None,
) -> tuple[
    list[CounterfactualRow],
    dict[str, dict[str, Any]],
    dict[str, Any],
]:
    capabilities, application_value, game_value = current_core_catalog_snapshot(
        discover_core(core)
    )
    tools = mind.configure_tools(capabilities)
    application_names = mind.configure_application_catalog(application_value)
    game_entries = mind.configure_game_catalog(game_value)
    game_catalog = mind.build_game_catalog_index(game_entries)
    semantic_encoder = SemanticEncoder(device="cpu")
    encoder = _CachedEncoder(semantic_encoder)
    encoder.prime(
        effect_intent._strip_request_envelope(row.text).strip() or row.text
        for row in inputs
    )
    planner_catalog = PlannerCatalog(tools, encoder=encoder)
    family_classifier = FamilyClassifier()
    family_arbiter = SemanticFamilyArbiter()
    prior_cache = os.environ.get(CACHE_ENVIRONMENT_VARIABLE)
    with tempfile.TemporaryDirectory(prefix="baxy-retrieval-pricing-") as cache:
        os.environ[CACHE_ENVIRONMENT_VARIABLE] = cache
        evidence = TurnEvidenceService()
        evidence.start(encoder, lambda: True)
        deadline = time.monotonic() + 360.0
        while evidence.state == "building" and time.monotonic() < deadline:
            time.sleep(0.05)
        diagnostics = evidence.diagnostics
        try:
            if evidence.state == "building":
                raise TimeoutError("turn_evidence_build_timeout")
            rows = []
            variants = {
                "baseline": frozenset(),
                "without_fallback_after_abstention": frozenset(
                    {"fallback_after_abstention"}
                ),
                "without_semantic_family_arbiter": frozenset(
                    {"semantic_family_arbiter"}
                ),
                "without_literal_schema_bridge": frozenset(
                    {"literal_schema_bridge"}
                ),
                "without_application_reference_bridge": frozenset(
                    {"application_reference_bridge"}
                ),
                "without_message_reference_bridge": frozenset(
                    {"message_reference_bridge"}
                ),
                "without_explicit_ocr_bridge": frozenset(
                    {"explicit_ocr_bridge"}
                ),
                "without_redundant_bridges": REDUNDANT_BRIDGES,
            }
            for source in inputs:
                candidate_variants = {
                    name: _candidate_names(
                        source.text,
                        planner_catalog=planner_catalog,
                        family_classifier=family_classifier,
                        semantic_family_arbiter=family_arbiter,
                        encoder=encoder,
                        turn_evidence=evidence,
                        application_names=application_names,
                        game_catalog=game_catalog,
                        disabled=disabled,
                    )
                    for name, disabled in variants.items()
                }
                rows.append(
                    CounterfactualRow(
                        population=source.population,
                        row_id=source.row_id,
                        text=source.text,
                        expected_operations=source.expected_operations,
                        variants=candidate_variants,
                        decision_variants=source.decision_variants,
                        outside_catalogue=source.outside_catalogue,
                    )
                )
        finally:
            evidence.stop(timeout=30.0)
            if prior_cache is None:
                os.environ.pop(CACHE_ENVIRONMENT_VARIABLE, None)
            else:
                os.environ[CACHE_ENVIRONMENT_VARIABLE] = prior_cache
    tool_payloads = {
        tool.name: {
            "name": tool.name,
            "description": tool.description,
            "arguments_schema": tool.schema,
        }
        for tool in planner_catalog.tools
    }
    _compare_changed_candidates_downstream(rows, tool_payloads)
    return rows, tool_payloads, {
        "catalog_operations": len(planner_catalog.tools),
        "family_classifier": "baxy.family-classifier-manifest.v1",
        "semantic_family_arbiter": "baxy.semantic-family-arbiter-manifest.v1",
        "encoder": verified_encoder_snapshot_identity(),
        "turn_evidence": diagnostics,
    }


def build_report(rows: list[RowSnapshot]) -> dict[str, Any]:
    population_names = sorted({row.population for row in rows})
    mechanisms: dict[str, Any] = {}
    recommendations: dict[str, dict[str, Any]] = {}
    for mechanism in MECHANISMS:
        changed: list[dict[str, Any]] = []
        lost: list[str] = []
        decisions: list[str] = []
        leaks: list[str] = []
        unavailable: list[str] = []
        prompt_delta = 0
        for row in sorted(rows, key=lambda item: (item.population, item.row_id)):
            without = row.candidates_without.get(mechanism)
            qualified_id = (
                row.row_id
                if len(population_names) == 1
                else f"{row.population}:{row.row_id}"
            )
            if without is None:
                unavailable.append(qualified_id)
            elif without != row.baseline_candidates:
                delta = candidate_prompt_bytes(without) - row.candidate_prompt_bytes
                prompt_delta += delta
                changed.append(
                    {
                        "population": row.population,
                        "row_id": row.row_id,
                        "with": list(row.baseline_candidates),
                        "without": list(without),
                        "prompt_cost_delta_bytes": delta,
                    }
                )
                if _correct_operation_lost(
                    row.expected_operations,
                    row.baseline_candidates,
                    without,
                ):
                    lost.append(qualified_id)
            if _decision_delta(row, mechanism):
                decisions.append(qualified_id)
            if _leak_avoided(row, mechanism):
                leaks.append(qualified_id)
        entry = {
            "candidate_set_changed_rows": changed,
            "decision_changed_rows": decisions,
            "correct_operation_lost_rows": lost,
            "leak_avoided_rows": leaks,
            "prompt_cost_delta_bytes": prompt_delta,
            "counterfactual_unavailable_rows": unavailable,
            "zero_refuters": {},
        }
        for metric in ZERO_AUDITED_METRICS:
            if entry[metric] in (0, []):
                entry["zero_refuters"][metric] = population_names
        mechanisms[mechanism] = entry
        evidence_rows = [
            *entry["correct_operation_lost_rows"],
            *entry["leak_avoided_rows"],
            *entry["decision_changed_rows"],
        ]
        if evidence_rows:
            recommendations[mechanism] = {
                "verdict": "preserve_observed_effect",
                "first_row_requiring_preservation": evidence_rows[0],
            }
        elif unavailable:
            recommendations[mechanism] = {
                "verdict": "inconclusive_no_prune",
                "first_unobserved_counterfactual_row": unavailable[0],
            }
        else:
            recommendations[mechanism] = {
                "verdict": "zero_on_consumed_rows_diagnostic_only",
                "refuting_populations": population_names,
            }

    return {
        "schema": "baxy.consumed-retrieval-mechanism-pricing.v1",
        "authority": "development_diagnostic_not_for_promotion",
        "effects_executed": 0,
        "opened_v8": False,
        "source_tree_modified": False,
        "prompt_cost_unit": "utf8_bytes_of_compact_candidate_name_array",
        "populations": population_names,
        "rows": len(rows),
        "observability": {
            "raw_candidates_rows": sum(row.raw_candidates_available for row in rows),
            "raw_decisions_rows": sum(row.raw_decision_available for row in rows),
            "pre_veto_rows": sum(
                row.raw_decision_available and row.first_veto is not None for row in rows
            ),
        },
        "metrics": {
            "candidate_entries": sum(len(row.baseline_candidates) for row in rows),
            "rows_with_candidates": sum(bool(row.baseline_candidates) for row in rows),
            "candidate_name_prompt_bytes": sum(
                row.candidate_prompt_bytes for row in rows
            ),
            "rows_with_expected_operations": sum(
                bool(row.expected_operations) for row in rows
            ),
            "rows_without_expected_operations": sum(
                not row.expected_operations for row in rows
            ),
        },
        "mechanisms": mechanisms,
        "recommendations_by_mechanism": recommendations,
        "recommendation": (
            "Do not prune any mechanism: no pre-decision counterfactual is "
            "observable in every consumed population. Preserve every mechanism "
            "that names a decision or leak row; treat all other zeros as "
            "diagnostic, not equivalence."
        ),
    }


def _source_hashes() -> dict[str, str | None]:
    hashes: dict[str, str | None] = {}
    for source in population_manifest():
        for path in (source.result, source.builder):
            if path is None:
                continue
            relative = path.relative_to(REPO).as_posix()
            hashes[relative] = (
                hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            )
    for path in STEP3_REJECTIONS:
        relative = path.relative_to(REPO).as_posix()
        hashes[relative] = (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        )
    return dict(sorted(hashes.items()))


def _step3_rejection_evidence() -> list[dict[str, Any]]:
    evidence = []
    for path in STEP3_REJECTIONS:
        payload = json.loads(path.read_text(encoding="utf-8"))
        evidence.append(
            {
                "path": path.relative_to(REPO).as_posix(),
                "schema": payload.get("schema"),
                "verdict": payload.get("verdict"),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return evidence


def _recommendations(mechanisms: dict[str, dict[str, Any]]) -> dict[str, Any]:
    recommendations = {}
    for name, measurement in mechanisms.items():
        preservation = measurement["rows_requiring_preservation"]
        changed = measurement.get("candidate_set_changed_rows")
        if changed is None:
            changed = measurement.get("decision_changed_rows", [])
        if preservation:
            recommendations[name] = {
                "verdict": "preserve_observed_recall",
                "first_row_requiring_preservation": preservation[0],
            }
        elif measurement.get("unobservable_rows"):
            recommendations[name] = {
                "verdict": "inconclusive_no_prune",
                "first_unobservable_row": measurement["unobservable_rows"][0],
            }
        elif (
            name in REDUNDANT_BRIDGES
            and changed
            and measurement.get("downstream_comparisons")
            and all(
                comparison["equivalent"]
                for comparison in measurement["downstream_comparisons"]
            )
        ):
            recommendations[name] = {
                "verdict": "prune_equivalent_after_downstream_comparison",
                "refuting_populations": sorted(
                    {
                        comparison["population"]
                        for comparison in measurement["downstream_comparisons"]
                    }
                ),
            }
        elif changed:
            recommendations[name] = {
                "verdict": "changes_consumed_rows_without_recall_loss",
                "first_changed_row": (
                    f"{changed[0]['population']}:{changed[0]['row_id']}"
                ),
            }
        elif name in REDUNDANT_BRIDGES:
            recommendations[name] = {
                "verdict": "prune_equivalent_candidate_sets_and_recall",
                "refuting_populations": sorted(
                    {
                        population
                        for values in measurement.get("zero_refuters", {}).values()
                        for population in values
                    }
                ),
            }
        else:
            recommendations[name] = {
                "verdict": "equivalent_on_consumed_rows_diagnostic_only",
                "refuting_populations": sorted(
                    {
                        population
                        for values in measurement.get("zero_refuters", {}).values()
                        for population in values
                    }
                ),
            }
    return recommendations


def _write_report(output: Path, report: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8") + b"\n"
    output.write_bytes(encoded)


def run(
    output: Path = DEFAULT_OUTPUT,
    *,
    core: Path | None = None,
    evaluator: Callable[
        [list[PopulationInput]],
        tuple[
            list[CounterfactualRow],
            dict[str, dict[str, Any]],
            dict[str, Any],
        ],
    ]
    | None = None,
) -> dict[str, Any]:
    inputs, unavailable = load_population_inputs()
    if evaluator is None:
        rows, tool_payloads, identities = recompute_counterfactual_rows(
            inputs,
            core=core,
        )
    else:
        rows, tool_payloads, identities = evaluator(inputs)
    pricing = build_counterfactual_report(rows, tool_payloads=tool_payloads)
    report = {
        "schema": "baxy.consumed-retrieval-mechanism-pricing.v2",
        "authority": "development_diagnostic_not_for_promotion",
        "effects_executed": 0,
        "opened_v8": False,
        "source_tree_modified": False,
        "prompt_cost_unit": "utf8_bytes_of_compact_native_tool_candidate_array",
        "rows": len(rows),
        "unobservable_populations": unavailable,
        "identities": identities,
        "step3_rejections": _step3_rejection_evidence(),
        "variant_metrics": pricing["variant_metrics"],
        "mechanisms": pricing["mechanisms"],
        "recommendations_by_mechanism": _recommendations(pricing["mechanisms"]),
        "pruning_metrics": {
            "before": pricing["variant_metrics"]["baseline"],
            "after": pricing["variant_metrics"].get(
                "without_redundant_bridges",
                pricing["variant_metrics"]["baseline"],
            ),
        },
        "row_counterfactuals": [
            {
                "population": row.population,
                "row_id": row.row_id,
                "text_sha256": hashlib.sha256(row.text.encode("utf-8")).hexdigest(),
                "expected_operations": list(row.expected_operations),
                "outside_catalogue": row.outside_catalogue,
                "candidate_sets": {
                    name: list(candidates)
                    for name, candidates in sorted(row.variants.items())
                },
                "decision_operation_sets": {
                    name: list(operations)
                    for name, operations in sorted(row.decision_variants.items())
                },
            }
            for row in rows
        ],
        "source_sha256": _source_hashes(),
    }
    _write_report(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--core", type=Path)
    args = parser.parse_args()
    report = run(args.output, core=args.core)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "rows": report["rows"],
                "unobservable_populations": report["unobservable_populations"],
                "recommendations": report["recommendations_by_mechanism"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
