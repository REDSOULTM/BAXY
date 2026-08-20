"""Inventory the inherited router/effect gates explicitly named by Goal 03B.

This is a read-only evidence probe.  It distinguishes family-retrieval scores
and post-reply fabrication guards from the current leaf-selection objective.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
BANK = REPO.parent / "Probando Gemma 4/dataset_finetune/out"
CORPUS = REPO / "artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl"
SELECTION = (
    REPO
    / "artifacts/development/goal03_qwen3_8b_iq2_think128_official_sampling_s0_v16.json"
)
OUTPUT = REPO / "artifacts/development/goal03_inherited_eval_banks_v24.json"
EXPECTED_CORPUS_SHA256 = (
    "761c1bc3b3facbf14a3aaafa09f24c0e5e0baaf8cebdd0edc7c2e648cb87413d"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _metric(text: str, pattern: str) -> dict[str, int | float]:
    match = re.search(pattern, text)
    if not match:
        raise RuntimeError(f"metric not found: {pattern}")
    hit, rows, rate = match.groups()
    return {"hit": int(hit), "rows": int(rows), "rate": float(rate)}


def _devfail_prompts(text: str) -> list[str]:
    prompts: list[str] = []
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate or candidate[0] not in {"'", '"'}:
            continue
        try:
            value = ast.literal_eval(candidate)
        except (SyntaxError, ValueError):
            continue
        if isinstance(value, str):
            prompts.append(value)
    return prompts


def main() -> int:
    if _sha256(CORPUS) != EXPECTED_CORPUS_SHA256:
        raise RuntimeError("sealed Goal 03 corpus identity changed")

    router_eval_path = BANK / "_router_eval_NEWBASE_noes.txt"
    devfails_path = BANK / "_router_eval_devfails.txt"
    baseline_path = BANK / "eval/_gates_baseline.json"
    guard5_path = BANK / "eval/_gates_ft_r2_guard5.json"
    deploy_path = BANK / "eval/_gates_deploy_smoke.json"
    paths = [router_eval_path, devfails_path, baseline_path, guard5_path, deploy_path]

    router_eval = router_eval_path.read_text(encoding="utf-8")
    devfails = devfails_path.read_text(encoding="utf-8")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    guard5 = json.loads(guard5_path.read_text(encoding="utf-8"))
    deploy = json.loads(deploy_path.read_text(encoding="utf-8"))
    corpus = _jsonl(CORPUS)
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))

    prompts = _devfail_prompts(devfails)
    normalized_corpus = {
        " ".join(str(row["text"]).casefold().split()): row["case_id"] for row in corpus
    }
    exact_overlap = [
        {"prompt": prompt, "case_id": normalized_corpus[" ".join(prompt.casefold().split())]}
        for prompt in prompts
        if " ".join(prompt.casefold().split()) in normalized_corpus
    ]
    residual = [
        row["case_id"]
        for row in selection["rows"]
        if row["in_catalog"] and not row["selected_expected"]
    ]

    result = {
        "schema": "baxy.goal03-inherited-eval-banks.v1",
        "source": {
            "bank": str(BANK),
            "sha256": {str(path.relative_to(BANK)): _sha256(path) for path in paths},
            "corpus_sha256": _sha256(CORPUS),
            "selection_sha256": _sha256(SELECTION),
        },
        "router_family_eval": {
            "population": {"rows": 2102, "dev": 1676, "holdout": 426},
            "dev_tool_recall": _metric(
                router_eval, r"\[dev\]\s+TOOL RECALL (\d+)/(\d+)=(\d+\.\d+)"
            ),
            "dev_no_tool_keep": _metric(
                router_eval, r"\[dev\].*?NO-TOOL keep (\d+)/(\d+)=(\d+\.\d+)"
            ),
            "holdout_tool_recall": _metric(
                router_eval, r"\[holdout\]\s+TOOL RECALL (\d+)/(\d+)=(\d+\.\d+)"
            ),
            "holdout_no_tool_keep": _metric(
                router_eval, r"\[holdout\].*?NO-TOOL keep (\d+)/(\d+)=(\d+\.\d+)"
            ),
            "unit": "coarse tool family offered in a subset, not current operation leaf selected",
            "dev_recall_miss_prompts": len(prompts),
            "exact_prompt_overlap_with_sealed_goal03": exact_overlap,
        },
        "current_leaf_selector": {
            "retrieved": selection["in_catalog"]["retrieved"],
            "selected_expected": selection["in_catalog"]["selected_expected"],
            "rows": selection["in_catalog"]["rows"],
            "residual_case_ids": residual,
        },
        "post_reply_gate": {
            "unit": "unfounded visible value claims after execution, not operation abstention",
            "baseline": {
                "fabrications": baseline["g2_fabricaciones"],
                "identity_ok": baseline["g4_ok"],
                "live_cases_pass": baseline["g6_pass"],
            },
            "guard5": {
                "fabrications": guard5["g2_fabricaciones"],
                "identity_ok": guard5["g4_ok"],
                "live_cases_pass": guard5["g6_pass"],
            },
            "deploy_smoke": {
                "fabrications": deploy["g2_fabricaciones"],
                "identity_ok": deploy["g4_ok"],
                "live_cases_pass": deploy["g6_pass"],
            },
            "current_equivalent": {
                "conversation_guard": "src/baxy_mind/llm.py::visible_reply_asserts_an_unread_machine_state",
                "kernel_outcome": "src/Baxy.Kernel/Operations/OperationOutcome.cs",
                "verified_narration": "src/Baxy.Kernel/Operations/IOperationResponseNarrator.cs",
            },
        },
        "conclusion": (
            "The bank confirms two already inherited concerns: high family retrieval and "
            "post-reply grounding. It contains no measured leaf selector that can resolve "
            "the current 14 selection errors, and its reply guard already has stricter "
            "owners in the current mind/kernel contract."
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: result[key] for key in (
        "router_family_eval", "current_leaf_selector", "post_reply_gate", "conclusion"
    )}, ensure_ascii=False, indent=2))
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
