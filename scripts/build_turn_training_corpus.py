"""Exporta evidencia promovida para entrenamiento/evaluación offline.

No genera reglas, no altera el runtime y no entrena pesos. El archivo de salida
es privado aunque mezcle evidencia local y licenciada. Conserva procedencia y
usa un split estable por misión para evitar que paráfrasis de la misma tarea
aparezcan en train y test.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind.turn_evidence import (  # noqa: E402
    TRAINING_SCHEMA_VERSION,
    load_private_corpus,
    training_examples,
)


DEFAULT_CORPUS = (
    ROOT / "tests" / "data" / "turn_evidence_runtime.v1.jsonl"
    if (ROOT / "tests" / "data" / "turn_evidence_runtime.v1.jsonl").is_file()
    else ROOT / "tests" / "data" / "historical_messages.jsonl"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=DEFAULT_CORPUS,
        help="JSONL de evidencia promovido; se puede fijar explícitamente.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="JSONL privado de salida; no debe publicarse.",
    )
    return parser.parse_args()


def write_atomic(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def report_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.name


def main() -> int:
    args = parse_args()
    records, report = load_private_corpus(args.corpus)
    rows = training_examples(records)
    if not rows:
        raise RuntimeError("el corpus no produjo filas de entrenamiento elegibles")
    write_atomic(
        args.output,
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
    )
    split_counts = Counter(str(row["split"]) for row in rows)
    mode_counts = Counter(str(row["target"]["mode"]) for row in rows)
    manifest = {
        "schema": "baxy.turn-training-manifest.v1",
        "training_schema": TRAINING_SCHEMA_VERSION,
        "source": report_path(args.corpus),
        "source_sha256": report.source_sha256,
        "source_rows": report.source_rows,
        "eligible_rows": report.accepted_rows,
        "excluded": {
            "private": report.excluded_private,
            "noncanonical": report.excluded_noncanonical,
            "ambiguous": report.excluded_ambiguous,
            "out_of_scope": report.excluded_out_of_scope,
        },
        "split_counts": dict(sorted(split_counts.items())),
        "mode_counts": dict(sorted(mode_counts.items())),
        "group_count": len({str(row["group"]) for row in rows}),
    }
    manifest_path = args.output.with_suffix(args.output.suffix + ".manifest.json")
    write_atomic(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    print(
        json.dumps(
            {
                "output": report_path(args.output),
                "manifest": report_path(manifest_path),
                **manifest,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
