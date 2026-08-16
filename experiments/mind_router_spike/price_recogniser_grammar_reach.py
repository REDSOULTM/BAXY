"""Why cut B closed 700/700 while V8 served 1 of 21.

Both seals are published, blind, opened once and unreopened. Both claim to
carry unseen formulations of catalogue capabilities. They disagree by a factor
of twenty, so at least one of them is not measuring what its bar names.

This instrument **reads only** published corpora and runs two deterministic
predicates from the frozen runtime over both. It never starts the product,
never invokes the decider, never enables a provider and executes nothing.

It reports, for each population:

* how often ``resolve_explicit_effects`` -- the deterministic recogniser --
  resolves the request to its expected operation without any model call;
* how often ``operation_domain_is_grounded`` would veto that same expected
  operation;
* the overlap, which is the whole finding: when the recogniser resolves,
  ``apply_operation_domain_grounding_veto`` returns early
  (``src/baxy_mind/__main__.py:1621``) and the gate is never consulted.

The available-operation set is the 158 Mind-sidecar operations named by the
versioned alias catalogue, not a set derived from either corpus, so neither
population can inflate its own reach.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import effect_intent  # noqa: E402

SCHEMA = "baxy.recogniser-grammar-reach.v1"
HOLDOUT = ROOT / "artifacts" / "holdout"
ALIASES = ROOT / "src" / "baxy_mind" / "data" / "catalog_operation_aliases.v1.json"
CUT_B = HOLDOUT / "generalization_product_current_tree_r28.jsonl"
VETO_V8 = HOLDOUT / "veto_reach_v8.corpus.jsonl"
OUTPUT = (
    ROOT / "artifacts" / "audit" / "recogniser_grammar_reach_r28_vs_v8_20260813.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def catalogue_operations() -> tuple[str, ...]:
    """The Mind sidecar's share of the authenticated catalogue."""

    with ALIASES.open(encoding="utf-8") as handle:
        catalogue = json.load(handle)
    operations: set[str] = set()
    for alias in catalogue["aliases"]:
        operations.update(alias.get("operations") or [])
        target = alias.get("target_operation")
        if target:
            operations.add(target)
    return tuple(sorted(operations))


def cut_b_rows() -> list[tuple[str, str, str]]:
    """Single-action rows whose oracle names exactly one operation."""

    rows = []
    for row in _read_jsonl(CUT_B):
        if row.get("case_type") != "single_action":
            continue
        sets = row.get("compatible_effect_operation_sets") or []
        if len(sets) != 1 or len(sets[0]) != 1:
            continue
        rows.append((row["case_id"], row["text"], sets[0][0]))
    return rows


def veto_reach_rows() -> list[tuple[str, str, str]]:
    """The V8 rows whose oracle expects an operation at all."""

    return [
        (row["case_id"], row["text"], row["expected_operation"])
        for row in _read_jsonl(VETO_V8)
        if row.get("expected_operation")
    ]


def _alias_terms(catalogue: dict[str, Any], operation: str) -> list[str]:
    terms = []
    for alias in catalogue["aliases"]:
        if alias.get("target_operation") == operation:
            text = alias.get("text")
            if isinstance(text, str):
                terms.append(text)
    return terms


def measure(
    label: str,
    rows: Iterable[tuple[str, str, str]],
    operations: tuple[str, ...],
    catalogue: dict[str, Any],
) -> dict[str, Any]:
    rows = list(rows)
    resolved_correct = 0
    resolved_other = 0
    unresolved: list[dict[str, str]] = []
    gate_would_veto = 0
    veto_rescued_by_recogniser = 0
    veto_reaches_the_turn: list[dict[str, str]] = []
    names_own_alias = 0

    for case_id, text, operation in rows:
        intent = effect_intent.resolve_explicit_effects(text, operations, (), ())
        resolved = intent is not None and operation in tuple(intent.operations)
        if intent is None:
            unresolved.append(
                {"case_id": case_id, "operation": operation, "text": text}
            )
        elif resolved:
            resolved_correct += 1
        else:
            resolved_other += 1

        vetoed = (
            effect_intent.operation_domain_is_grounded(text, operation, ()) is False
        )
        if vetoed:
            gate_would_veto += 1
            if resolved:
                veto_rescued_by_recogniser += 1
            else:
                veto_reaches_the_turn.append(
                    {"case_id": case_id, "operation": operation, "text": text}
                )

        folded = effect_intent._fold(text)
        if any(
            effect_intent._fold(term) in folded
            for term in _alias_terms(catalogue, operation)
            if len(term) > 3
        ):
            names_own_alias += 1

    total = len(rows)

    def share(value: int) -> float:
        return round(value / total, 4) if total else 0.0

    return {
        "population": label,
        "rows": total,
        "deterministic_recogniser": {
            "resolved_the_expected_operation": resolved_correct,
            "resolved_a_different_operation": resolved_other,
            "did_not_resolve": len(unresolved),
            "reach": share(resolved_correct),
        },
        "domain_gate": {
            "would_veto_the_expected_operation": gate_would_veto,
            "veto_rate": share(gate_would_veto),
            "rescued_because_the_recogniser_resolved_first": (
                veto_rescued_by_recogniser
            ),
            "veto_actually_reaches_the_turn": len(veto_reaches_the_turn),
        },
        "rows_literally_containing_an_alias_of_their_own_operation": names_own_alias,
        "unresolved_sample": unresolved[:10],
        "veto_reaches_the_turn_sample": veto_reaches_the_turn[:10],
    }


def build() -> dict[str, Any]:
    operations = catalogue_operations()
    with ALIASES.open(encoding="utf-8") as handle:
        catalogue = json.load(handle)

    cut_b = measure("cut B — R28, sealed 700/700", cut_b_rows(), operations, catalogue)
    veto = measure(
        "veto-reach V8 — sealed, served 1 of 21",
        veto_reach_rows(),
        operations,
        catalogue,
    )

    return {
        "schema": SCHEMA,
        "measured_on": "2026-08-13",
        "reads_only_published_artifacts": True,
        "product_started": False,
        "decider_invoked": False,
        "providers_enabled": False,
        "effects_executed": 0,
        "voice_stt_wake_exercised": False,
        "identities": {
            "catalogue_operations": len(operations),
            "catalogue_aliases_sha256": _sha256(ALIASES),
            "cut_b_corpus_sha256": _sha256(CUT_B),
            "veto_reach_v8_corpus_sha256": _sha256(VETO_V8),
            "effect_intent_sha256": _sha256(ROOT / "src" / "baxy_mind" / "effect_intent.py"),
        },
        "populations": [cut_b, veto],
        "finding": (
            "The two seals do not measure the same path. The deterministic"
            f" recogniser resolves {cut_b['deterministic_recogniser']['reach']:.0%}"
            " of cut B and"
            f" {veto['deterministic_recogniser']['reach']:.0%} of the V8"
            " serviceable rows. Cut B's 700/700 is a measurement of the"
            " recogniser's grammar, not of the model path; V8 is a measurement"
            " of the model path, and there the product serves 1 of 21."
        ),
        "why_the_gate_looks_harmless_on_cut_b": (
            "The gate would veto"
            f" {cut_b['domain_gate']['would_veto_the_expected_operation']} of"
            f" {cut_b['rows']} cut B rows, but"
            f" {cut_b['domain_gate']['rescued_because_the_recogniser_resolved_first']}"
            " of them never reach it: apply_operation_domain_grounding_veto"
            " returns early at src/baxy_mind/__main__.py:1621 when the"
            " recogniser already proved the same operations. A seal whose rows"
            " resolve deterministically cannot price this gate."
        ),
        "consequence": (
            "Cut B cannot demonstrate the generalisation its bar names. Its"
            " generating grammar does not leave the recogniser's grammar, so a"
            " 700/700 over it is not evidence about unseen phrasing in"
            " general. A cut B whose generator is independent of the recogniser"
            " is required before any generalisation claim is credible."
        ),
        "limits": [
            "runs two deterministic predicates, not the product turn",
            "application catalogue and game catalogue are passed empty, which"
            " can only lower the recogniser's measured reach, never raise it",
            "cut B rows with an ambiguous oracle (more than one compatible"
            " operation set) are excluded; only single-operation rows are"
            " counted",
        ],
    }


def main() -> int:
    report = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(
        (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
    )
    for population in report["populations"]:
        recogniser = population["deterministic_recogniser"]
        gate = population["domain_gate"]
        print(f"{population['population']}  (n={population['rows']})")
        print(
            "   recogniser resolves : "
            f"{recogniser['resolved_the_expected_operation']}"
            f" ({recogniser['reach']:.0%})"
        )
        print(
            "   gate would veto     : "
            f"{gate['would_veto_the_expected_operation']}"
            f" ({gate['veto_rate']:.0%}), rescued first by the recogniser:"
            f" {gate['rescued_because_the_recogniser_resolved_first']}"
        )
    print(f"artifact: {OUTPUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
