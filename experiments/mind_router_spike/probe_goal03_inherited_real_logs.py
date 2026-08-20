"""Inventory inherited real-language selector evidence without exposing texts."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
PROGRAMACION = REPO.parent
REAL_LOGS = (
    PROGRAMACION
    / "Probando Gemma 4"
    / "gemma4_agent"
    / "data"
    / "router_corpus_real_logs.jsonl"
)
FUNCTIONGEMMA_TRAIN = (
    PROGRAMACION
    / "FunctionGemma"
    / "finetune_llm"
    / "curated"
    / "train_v3.jsonl"
)
REDUCED_ACTION_MAP = (
    PROGRAMACION
    / "FunctionGemma"
    / "finetune_llm"
    / "reduced_catalog"
    / "tool_action_map.json"
)
FULL_ACTION_MAP = PROGRAMACION / "FunctionGemma" / "tool_action_map.json"
CURRENT_UNION_TRAIN = Path(
    r"D:\BAXYRuntime\experiments\functiongemma-current-union-v1\train.jsonl"
)
FRESH = REPO / "artifacts" / "development" / "goal03_fresh_paraphrase_corpus.v1.jsonl"
OUTPUT = REPO / "artifacts" / "development" / "goal03_inherited_real_logs_v31.json"


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


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", value))


def _text_set(rows: list[dict[str, Any]], key: str) -> set[str]:
    return {_normalize(str(row.get(key) or "")) for row in rows} - {""}


def run(output: Path) -> dict[str, Any]:
    for path in (
        REAL_LOGS,
        FUNCTIONGEMMA_TRAIN,
        REDUCED_ACTION_MAP,
        FULL_ACTION_MAP,
        CURRENT_UNION_TRAIN,
        FRESH,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    real = _jsonl(REAL_LOGS)
    inherited = _jsonl(FUNCTIONGEMMA_TRAIN)
    current = _jsonl(CURRENT_UNION_TRAIN)
    fresh = _jsonl(FRESH)
    action_map = json.loads(REDUCED_ACTION_MAP.read_text(encoding="utf-8"))
    full_action_map = json.loads(FULL_ACTION_MAP.read_text(encoding="utf-8"))

    real_texts = _text_set(real, "q")
    inherited_texts = _text_set(inherited, "user_text")
    current_texts = _text_set(current, "text")
    fresh_texts = _text_set(fresh, "text")

    mapped_rows = 0
    single_mapped_rows = 0
    mapped_targets: collections.Counter[str] = collections.Counter()
    full_mapped_rows = 0
    full_single_mapped_rows = 0
    full_mapped_targets: collections.Counter[str] = collections.Counter()
    history_rows = [row for row in inherited if row.get("dataset_part") == "history_curated"]
    history_tool_rows = 0
    for row in history_rows:
        if row.get("correct_tools"):
            history_tool_rows += 1
        targets: list[str] = []
        for result in row.get("tool_results") or []:
            tool = result.get("tool")
            action = result.get("action")
            target = action_map.get(f"{tool}::{action}") if tool and action else None
            if target and target not in targets:
                targets.append(target)
        if targets:
            mapped_rows += 1
            mapped_targets.update(targets)
        if len(targets) == 1:
            single_mapped_rows += 1
        full_targets: list[str] = []
        for result in row.get("tool_results") or []:
            tool = result.get("tool")
            action = result.get("action")
            target = (
                full_action_map.get(f"{tool}::{action}") if tool and action else None
            )
            if target and target not in full_targets:
                full_targets.append(target)
        if full_targets:
            full_mapped_rows += 1
            full_mapped_targets.update(full_targets)
        if len(full_targets) == 1:
            full_single_mapped_rows += 1

    report = {
        "schema": "baxy.goal03-inherited-real-logs.v1",
        "sources": {
            "real_logs": {
                "path": str(REAL_LOGS),
                "sha256": _sha256(REAL_LOGS),
                "rows": len(real),
                "unique_normalized_texts": len(real_texts),
            },
            "functiongemma_train_v3": {
                "path": str(FUNCTIONGEMMA_TRAIN),
                "sha256": _sha256(FUNCTIONGEMMA_TRAIN),
                "rows": len(inherited),
                "unique_normalized_texts": len(inherited_texts),
                "dataset_parts": dict(
                    sorted(collections.Counter(row.get("dataset_part") for row in inherited).items())
                ),
                "projects": dict(
                    sorted(collections.Counter(row.get("project") for row in inherited).items())
                ),
            },
            "reduced_action_map": {
                "path": str(REDUCED_ACTION_MAP),
                "sha256": _sha256(REDUCED_ACTION_MAP),
                "family_action_pairs": len(action_map),
                "individual_function_names": len(set(action_map.values())),
            },
            "full_action_map": {
                "path": str(FULL_ACTION_MAP),
                "sha256": _sha256(FULL_ACTION_MAP),
                "family_action_pairs": len(full_action_map),
                "individual_function_names": len(set(full_action_map.values())),
            },
            "current_union_train": {
                "path": str(CURRENT_UNION_TRAIN),
                "sha256": _sha256(CURRENT_UNION_TRAIN),
                "rows": len(current),
                "unique_normalized_texts": len(current_texts),
            },
            "fresh_corpus": {
                "path": str(FRESH.relative_to(REPO)),
                "sha256": _sha256(FRESH),
                "rows": len(fresh),
                "unique_normalized_texts": len(fresh_texts),
            },
        },
        "normalized_text_overlap": {
            "real_logs_with_functiongemma_train_v3": len(real_texts & inherited_texts),
            "real_logs_with_current_union_train": len(real_texts & current_texts),
            "functiongemma_train_v3_with_current_union_train": len(
                inherited_texts & current_texts
            ),
            "real_logs_with_fresh": len(real_texts & fresh_texts),
            "functiongemma_train_v3_with_fresh": len(inherited_texts & fresh_texts),
        },
        "history_curated_mapping": {
            "rows": len(history_rows),
            "rows_with_correct_tools": history_tool_rows,
            "rows_with_at_least_one_reduced_target": mapped_rows,
            "rows_with_exactly_one_reduced_target": single_mapped_rows,
            "unique_reduced_targets": len(mapped_targets),
            "top_reduced_targets": dict(mapped_targets.most_common(30)),
            "rows_with_at_least_one_full_target": full_mapped_rows,
            "rows_with_exactly_one_full_target": full_single_mapped_rows,
            "unique_full_targets": len(full_mapped_targets),
            "top_full_targets": dict(full_mapped_targets.most_common(30)),
        },
        "published_historical_measurement": {
            "curated_holdout_recall": 0.9964,
            "real_log_strict_recall": 0.857,
            "real_log_domain_equivalent_recall": 0.891,
            "source": "biblioteca/gemma4-agent/documentacion/02_router/05_HISTORIAL_SPRINTS.md",
        },
        "privacy": {
            "raw_texts_copied_to_report": 0,
            "effects_executed": 0,
            "source_projects_modified": False,
        },
        "decision": (
            "measure catalogue crosswalk coverage before reusing inherited real-language "
            "rows; do not train or inspect fresh failures"
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = run(args.output.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
