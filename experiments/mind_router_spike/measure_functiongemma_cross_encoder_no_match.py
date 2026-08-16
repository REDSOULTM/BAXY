"""Measure one local request/operation cross-encoder without product changes.

The threshold is selected only from the frozen, disjoint FunctionGemma
verifier validation receipt.  R2/R28, V1-V7 and the consumed physical text
missions are opened afterwards and used only to diagnose identity recall and
the four named no-match requests.  The scorer executes no operation.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[2]
MODEL = Path(r"D:\BAXYRuntime\assets\models\functiongemma-270m-it-hf")
ADAPTER = Path(r"D:\BAXYRuntime\experiments\functiongemma-verifier-v1")
SCORER = REPO / "experiments/functiongemma_selector/score_verifier.py"
DEVELOPMENT = (
    REPO / "artifacts/research/functiongemma_verifier_scored_validation_r1.json"
)
DEVELOPMENT_CORPUS = (
    REPO / "artifacts/research/functiongemma_verifier_validation.v1.jsonl"
)
PRICING = (
    REPO / "artifacts/development/consumed_retrieval_mechanism_pricing_20260812.json"
)
CATALOG = REPO / "artifacts/development/catalog_vocabulary_snapshot.json"
DEFAULT_CASES = (
    REPO
    / "artifacts/development/"
    "functiongemma_cross_encoder_no_match_cases_20260813.jsonl"
)
DEFAULT_RAW = (
    REPO
    / "artifacts/development/"
    "functiongemma_cross_encoder_no_match_raw_20260813.json"
)
DEFAULT_OUTPUT = (
    REPO
    / "artifacts/development/"
    "functiongemma_cross_encoder_no_match_rejected_20260813.json"
)
NO_ACTION = "__no_action__"
NO_MATCH_REQUESTS = {
    "taxi_es": "Pide un taxi para las ocho.",
    "taxi_en": "Book a taxi for eight o'clock.",
    "known_leak_v1": "Barre las hojas del sendero.",
    "known_leak_v5": "Boil the artichokes for dinner.",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _literal_assignment(path: Path, name: str) -> Any:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            return ast.literal_eval(node.value)
    raise ValueError(f"{path.name} does not define {name}")


def _consumed_texts() -> dict[str, str]:
    texts: set[str] = set()
    holdout = REPO / "artifacts/holdout"
    for name in (
        "catalog_surface_current_tree_r2.jsonl",
        "generalization_product_current_tree_r28.jsonl",
    ):
        texts.update(str(row["text"]) for row in _read_jsonl(holdout / name))
    spike = REPO / "experiments/mind_router_spike"
    for version in range(1, 8):
        builder = spike / f"build_veto_reach_v{version}.py"
        for assignment in ("CATALOGUE_CONTROLS", "REQUESTS", "CONTROLS"):
            texts.update(
                str(text)
                for _case_id, _language, text in _literal_assignment(
                    builder, assignment
                )
            )
    preregistration = json.loads(
        (
            REPO
            / "artifacts/development/"
            "physical_dependent_missions_preregistration_20260811.json"
        ).read_text(encoding="utf-8")
    )
    texts.update(str(mission["text"]) for mission in preregistration["missions"])
    return {_text_sha256(text): text for text in texts}


def _tool(operation: str, description: str) -> dict[str, Any]:
    name = (
        "baxy_no_action"
        if operation == NO_ACTION
        else "baxy_" + operation.replace(".", "__")
    )
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": {}},
        },
    }


def _case(
    pair_id: str,
    text: str,
    operation: str,
    description: str,
) -> dict[str, Any]:
    return {
        "schema": "baxy.functiongemma-verifier-row.v1",
        "case_id": hashlib.sha256(pair_id.encode("utf-8")).hexdigest()[:24],
        "source": "r126-cross-encoder-diagnostic",
        "text": text,
        "candidate_operation": operation,
        "base_operation": operation,
        "operation": operation,
        "verdict": "accept",
        "negative_kind": None,
        "tools": [
            _tool(
                NO_ACTION,
                "Select this only when the message requests no concrete action "
                "or external read covered by the other declared BAXY operations.",
            ),
            _tool(operation, description),
        ],
    }


def build_diagnostic_cases() -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    catalog_payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    descriptions = {
        str(item["name"]): str(item["description"])
        for item in catalog_payload["capabilities"]
    }
    texts = _consumed_texts()
    pricing = json.loads(PRICING.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = []
    metadata: dict[str, dict[str, str]] = {}
    seen: set[str] = set()

    def append_pair(
        *,
        pair_id: str,
        text: str,
        operation: str,
        cause: str,
        population: str,
    ) -> None:
        if pair_id in seen:
            return
        seen.add(pair_id)
        case = _case(pair_id, text, operation, descriptions[operation])
        cases.append(case)
        metadata[case["case_id"]] = {
            "pair_id": pair_id,
            "cause": cause,
            "population": population,
            "operation": operation,
            "text_sha256": _text_sha256(text),
        }

    for row in pricing["row_counterfactuals"]:
        baseline = set(row["candidate_sets"]["baseline"])
        text_hash = str(row["text_sha256"])
        text = texts.get(text_hash)
        if text is None:
            raise ValueError(f"consumed text unavailable for {text_hash}")
        for operation in row["expected_operations"]:
            if operation not in baseline:
                continue
            pair_id = f"{row['population']}:{row['row_id']}:{operation}"
            append_pair(
                pair_id=pair_id,
                text=text,
                operation=operation,
                cause="served_identity",
                population=str(row["population"]),
            )

    for cause, text in NO_MATCH_REQUESTS.items():
        for operation in sorted(descriptions):
            append_pair(
                pair_id=f"{cause}:{operation}",
                text=text,
                operation=operation,
                cause=cause,
                population="consumed_diagnostic",
            )
    return cases, metadata


def select_zero_accept_loss_threshold(
    development_rows: Iterable[dict[str, Any]],
) -> dict[str, int | float]:
    rows = list(development_rows)
    accepts = [
        float(row["accept_margin"]) for row in rows if row["verdict"] == "accept"
    ]
    rejects = [
        float(row["accept_margin"]) for row in rows if row["verdict"] == "reject"
    ]
    if not accepts:
        raise ValueError("development validation has no accept rows")
    threshold = min(accepts)
    return {
        "threshold": threshold,
        "development_accept_rows": len(accepts),
        "development_accept_rows_lost": sum(value < threshold for value in accepts),
        "development_reject_rows": len(rejects),
        "development_reject_rows_separated": sum(
            value < threshold for value in rejects
        ),
    }


def acceptance_summary(
    rows: Iterable[dict[str, Any]],
    threshold: float,
) -> dict[str, Any]:
    values = list(rows)
    served = [row for row in values if row["cause"] == "served_identity"]
    lost = sorted(
        str(row["pair_id"])
        for row in served
        if float(row["accept_margin"]) < threshold
    )
    by_population = {
        population: {
            "total": len(group),
            "lost": sum(
                float(row["accept_margin"]) < threshold for row in group
            ),
        }
        for population, group in (
            (
                value,
                [row for row in served if row["population"] == value],
            )
            for value in sorted({str(row["population"]) for row in served})
        )
    }
    causes = sorted({str(row["cause"]) for row in values} - {"served_identity"})
    no_match = {}
    for cause in causes:
        group = [row for row in values if row["cause"] == cause]
        accepted = sum(float(row["accept_margin"]) >= threshold for row in group)
        no_match[cause] = {
            "pairs": len(group),
            "accepted_pairs": accepted,
            "separated": accepted == 0,
        }
    return {
        "served_identity": {
            "total": len(served),
            "lost": len(lost),
            "lost_pair_ids": lost,
            "by_population": by_population,
        },
        "no_match_by_cause": no_match,
    }


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
        newline="\n",
    )


def _score(
    *,
    python: Path,
    cases: Path,
    raw_output: Path,
    batch_size: int,
) -> None:
    subprocess.run(
        [
            str(python),
            str(SCORER),
            "--model",
            str(MODEL),
            "--adapter",
            str(ADAPTER),
            "--cases",
            str(cases),
            "--output",
            str(raw_output),
            "--batch-size",
            str(batch_size),
        ],
        cwd=REPO,
        check=True,
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    development = json.loads(DEVELOPMENT.read_text(encoding="utf-8"))
    threshold = select_zero_accept_loss_threshold(development["rows"])
    cases, metadata = build_diagnostic_cases()
    _write_jsonl(args.cases, cases)
    _score(
        python=args.python,
        cases=args.cases,
        raw_output=args.raw_output,
        batch_size=args.batch_size,
    )
    raw = json.loads(args.raw_output.read_text(encoding="utf-8"))
    measured = [
        {
            **metadata[str(row["case_id"])],
            "accept_margin": float(row["accept_margin"]),
        }
        for row in raw["rows"]
    ]
    acceptance = acceptance_summary(measured, float(threshold["threshold"]))
    all_no_match = all(
        value["separated"]
        for value in acceptance["no_match_by_cause"].values()
    )
    accepted = acceptance["served_identity"]["lost"] == 0 and all_no_match
    completion_rows = len(cases) * 2
    forward_seconds = completion_rows / float(raw["forward_rows_per_second"])
    report = {
        "schema": "baxy.functiongemma-cross-encoder-no-match.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "authority": "development_diagnostic_not_for_promotion",
        "verdict": "accepted_for_runtime_consideration" if accepted else "rejected",
        "effects_executed": 0,
        "runtime_productive_files_modified": False,
        "opened_v8": False,
        "full_run": False,
        "e2e_run": False,
        "model": {
            "identity": "unsloth/functiongemma-270m-it",
            "revision": (
                MODEL
                / ".cache/huggingface/download/model.safetensors.metadata"
            ).read_text(encoding="utf-8").splitlines()[0],
            "base_weights_sha256": _sha256(MODEL / "model.safetensors"),
            "adapter": str(ADAPTER),
            "adapter_weights_sha256": _sha256(
                ADAPTER / "adapter_model.safetensors"
            ),
            "adapter_config_sha256": _sha256(ADAPTER / "adapter_config.json"),
            "architecture": "causal-LM pair verifier; request and one operation are jointly attended",
            "parameters": 271895168,
            "local_before_probe": True,
            "downloaded": False,
        },
        "development_selection": {
            **threshold,
            "source": str(DEVELOPMENT.relative_to(REPO)).replace("\\", "/"),
            "source_sha256": _sha256(DEVELOPMENT),
            "corpus_sha256": _sha256(DEVELOPMENT_CORPUS),
            "train_validation_normalised_overlap": 0,
            "threshold_used_consumed_rows": False,
            "reject_separation_by_cause": {
                kind: {
                    "total": len(group),
                    "separated": sum(
                        float(row["accept_margin"]) < float(threshold["threshold"])
                        for row in group
                    ),
                }
                for kind, group in (
                    (
                        value,
                        [
                            row
                            for row in development["rows"]
                            if row.get("negative_kind") == value
                        ],
                    )
                    for value in sorted(
                        {
                            str(row["negative_kind"])
                            for row in development["rows"]
                            if row.get("negative_kind") is not None
                        }
                    )
                )
            },
        },
        "consumed_diagnostic": {
            "populations": "R2/R28/V1-V7/consumed physical text missions",
            "selection_authority": False,
            **acceptance,
        },
        "incremental_latency": {
            "diagnostic_pairs": len(cases),
            "forced_completion_rows": completion_rows,
            "batch_size": raw["batch_size"],
            "measured_forward_seconds": round(forward_seconds, 6),
            "measured_milliseconds_per_pair": round(
                forward_seconds * 1000 / len(cases), 6
            ),
            "forward_rows_per_second": raw["forward_rows_per_second"],
            "forward_batch_seconds": raw["forward_batch_seconds"],
            "peak_allocated_mib": raw["peak_allocated_mib"],
            "peak_reserved_mib": raw["peak_reserved_mib"],
        },
        "tdd": {
            "red": "module absent; focused test collection failed as expected",
            "green_expected": "experiments/tests/test_cross_encoder_no_match.py",
        },
        "inputs": {
            "cases": str(args.cases.relative_to(REPO)).replace("\\", "/"),
            "cases_sha256": _sha256(args.cases),
            "raw_scores": str(args.raw_output.relative_to(REPO)).replace("\\", "/"),
            "raw_scores_sha256": _sha256(args.raw_output),
            "pricing_sha256": _sha256(PRICING),
            "catalog_sha256": _sha256(CATALOG),
        },
        "limits": [
            "No runtime promotion was performed.",
            "The consumed populations were diagnostic only.",
            "No V8, Full, E2E, commit, installation, or external effect was run.",
        ],
    }
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python",
        type=Path,
        default=Path(
            r"D:\BAXYRuntime\experiments\functiongemma-train-v1\Scripts\python.exe"
        ),
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--batch-size", type=int, default=4)
    run(parser.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
