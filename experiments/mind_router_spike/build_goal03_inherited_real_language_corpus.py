"""Extract high-confidence current-operation rows from inherited real logs."""

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
SEALED = REPO / "artifacts" / "development" / "goal03_fresh_paraphrase_corpus.v1.jsonl"
DEFAULT_OUTPUT = Path(r"D:\BAXYRuntime\experiments\functiongemma-real-language-v1")
DEFAULT_REPORT = (
    REPO / "artifacts" / "development" / "goal03_inherited_real_language_corpus_v33.json"
)
EXPECTED_SEALED_SHA256 = (
    "761c1bc3b3facbf14a3aaafa09f24c0e5e0baaf8cebdd0edc7c2e648cb87413d"
)

# Only one-to-one relations whose old action contract and current operation
# description agree. Ambiguous/destructive legacy actions are deliberately absent.
PAIR_TO_CURRENT = {
    "app::close": "app.close",
    "app::open": "app.open",
    "app::search": "app.installed",
    "audio::mute": "audio.mute",
    "audio::set_volume": "audio.volume",
    "browser::open": "browser.navigate",
    "browser::search": "web.search",
    "filesystem::list": "filesystem.list",
    "filesystem::mkdir": "filesystem.create.directory",
    "filesystem::read": "filesystem.read.text",
    "filesystem::search": "filesystem.known.search",
    "gui::screenshot": "capture.screenshot",
    "media::next": "media.control",
    "media::pause": "media.control",
    "media::play": "media.play.query",
    "media::previous": "media.control",
    "media::resume": "media.control",
    "media::stop": "media.control",
    "memory::recall": "memory.recall",
    "memory::save": "memory.save",
    "steam::library": "game.catalog.list",
    "steam::open": "app.open",
    "system::battery": "system.status",
    "system::cpu_ram_gpu": "system.status",
    "system::processes": "system.process.list",
    "system::time": "system.time",
    "vision::describe_screen": "vision.describe",
    "web::search": "web.search",
    "whatsapp::send_message": "message.send",
    "window::active": "window.active",
    "window::close": "app.close",
    "window::focus": "window.focus",
    "window::list": "window.resolve",
    "window::maximize": "window.maximize",
    "window::minimize": "window.minimize",
}


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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", value))


def _split(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row["operation"])].append(row)
    train: list[dict[str, Any]] = []
    validation: list[dict[str, Any]] = []
    for operation, group in sorted(grouped.items()):
        ordered = sorted(
            group,
            key=lambda row: hashlib.sha256(
                _normalize(str(row["text"])).encode("utf-8")
            ).hexdigest(),
        )
        held = max(1, min(len(ordered) - 1, round(len(ordered) * 0.2)))
        validation.extend(ordered[:held])
        train.extend(ordered[held:])
    return train, validation


def _counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = collections.Counter(str(row["operation"]) for row in rows)
    return {
        "rows": len(rows),
        "operations": len(values),
        "by_operation": dict(sorted(values.items())),
    }


def build(output_dir: Path, report_path: Path) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty {output_dir}")
    if _sha256(SEALED) != EXPECTED_SEALED_SHA256:
        raise RuntimeError("sealed Goal 03 corpus identity changed")

    real_norm = {_normalize(str(row["q"])) for row in _jsonl(REAL_LOGS)}
    sealed_norm = {_normalize(str(row["text"])) for row in _jsonl(SEALED)}
    candidates: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    rejected = collections.Counter()
    for line_number, row in enumerate(_jsonl(FUNCTIONGEMMA_TRAIN), start=1):
        text = str(row.get("user_text") or "").strip()
        normalized = _normalize(text)
        if row.get("dataset_part") != "history_curated" or normalized not in real_norm:
            rejected["not_in_real_history_intersection"] += 1
            continue
        if normalized in sealed_norm:
            rejected["sealed_exact_overlap"] += 1
            continue
        if (
            row.get("n_steps") != 1
            or not row.get("original_was_correct")
            or float(row.get("confidence") or 0.0) < 0.8
        ):
            rejected["quality_gate"] += 1
            continue
        results = row.get("tool_results") or []
        if len(results) != 1:
            rejected["not_single_tool_result"] += 1
            continue
        result = results[0]
        pair = f"{result.get('tool')}::{result.get('action')}"
        operation = PAIR_TO_CURRENT.get(pair)
        if operation is None:
            rejected["ambiguous_or_unmapped_pair"] += 1
            continue
        candidates[normalized].append(
            {
                "schema": "baxy.functiongemma-inherited-real-row.v1",
                "case_id": f"inherited-real:{line_number}",
                "text": text,
                "operation": operation,
                "language": row.get("lang") or "es",
                "source": "inherited-real-language-high-confidence-v1",
                "legacy_pair": pair,
            }
        )

    rows: list[dict[str, Any]] = []
    conflicting = 0
    for group in candidates.values():
        operations = {str(row["operation"]) for row in group}
        if len(operations) != 1:
            conflicting += 1
            continue
        rows.append(sorted(group, key=lambda row: str(row["case_id"]))[0])
    train, validation = _split(rows)
    output_dir.mkdir(parents=True, exist_ok=False)
    train_path = output_dir / "mapped_train.jsonl"
    validation_path = output_dir / "mapped_validation.jsonl"
    _write_jsonl(train_path, train)
    _write_jsonl(validation_path, validation)

    report = {
        "schema": "baxy.goal03-inherited-real-language-corpus.v1",
        "sources": {
            "real_logs": {"path": str(REAL_LOGS), "sha256": _sha256(REAL_LOGS)},
            "functiongemma_train_v3": {
                "path": str(FUNCTIONGEMMA_TRAIN),
                "sha256": _sha256(FUNCTIONGEMMA_TRAIN),
            },
            "sealed_exclusion_only": {
                "path": str(SEALED.relative_to(REPO)),
                "sha256": _sha256(SEALED),
            },
        },
        "mapping": {
            "accepted_legacy_pairs": len(PAIR_TO_CURRENT),
            "current_operations": len(set(PAIR_TO_CURRENT.values())),
            "policy": "one-to-one contract match only; ambiguous and destructive pairs absent",
        },
        "deduplicated_rows": len(rows),
        "conflicting_normalized_texts_removed": conflicting,
        "rejected": dict(sorted(rejected.items())),
        "outputs": {
            "train": {"path": str(train_path), "sha256": _sha256(train_path), **_counts(train)},
            "validation": {
                "path": str(validation_path),
                "sha256": _sha256(validation_path),
                **_counts(validation),
            },
        },
        "split_policy": "per-operation deterministic normalized-SHA 80/20",
        "exact_normalized_overlap_with_sealed": sum(
            _normalize(str(row["text"])) in sealed_norm for row in rows
        ),
        "privacy": {
            "raw_texts_copied_to_versioned_report": 0,
            "source_projects_modified": False,
            "effects_executed": 0,
        },
        "decision": "build production-like candidates only if row and operation coverage justify it",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    report = build(args.output_dir.resolve(), args.report.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
