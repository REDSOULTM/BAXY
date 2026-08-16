"""Run the preregistered CPU-only BGE-M3 semantic abstention development probe."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import preregister_bge_m3_semantic_abstention_r235 as r235


RUNTIME = REPO / "tests/data/turn_evidence_runtime.v1.jsonl"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
OUTPUT = REPO / "artifacts/development/bge_m3_semantic_abstention_r236.json"
INSIDE_COUNT = 256
OUTSIDE_COUNT = 256


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def public_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    families = {str(item["name"]).split(".", 1)[0] for item in catalog["catalogue"]["capabilities"]}
    inside: list[dict[str, Any]] = []
    outside: list[dict[str, Any]] = []
    for line in RUNTIME.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        provenance = row.get("provenance")
        source = str(provenance.get("dataset")) if isinstance(provenance, dict) else ""
        if source not in {"PRESTO v1", "MASSIVE v1.1"} or row.get("split") != "train":
            continue
        row_families = [str(value) for value in row.get("families") or []]
        record = {"source_id": str(row["source_id"]), "text": str(row["text"]), "families": row_families}
        if len(row_families) == 1 and row_families[0] in families:
            inside.append(record)
        elif not row_families:
            outside.append(record)
    return inside, outside


def sample_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    inside, outside = public_rows()
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in inside:
        by_family[row["families"][0]].append(row)
    selected: list[dict[str, Any]] = []
    for family in sorted(by_family):
        selected.append(sorted(by_family[family], key=lambda row: _key(row["source_id"]))[0])
    remainder = sorted(
        (row for rows in by_family.values() for row in rows if row not in selected),
        key=lambda row: _key(row["source_id"]),
    )
    selected.extend(remainder[: INSIDE_COUNT - len(selected)])
    selected_outside = sorted(outside, key=lambda row: _key(row["source_id"]))[:OUTSIDE_COUNT]
    if len(selected) != INSIDE_COUNT or len(selected_outside) != OUTSIDE_COUNT:
        raise RuntimeError("R236 requires exact public development sample counts")
    return selected, selected_outside


def family_documents() -> tuple[list[str], list[str]]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["catalogue"]["capabilities"]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for capability in catalog:
        groups[str(capability["name"]).split(".", 1)[0]].append(capability)
    names = sorted(groups)
    documents = []
    for family in names:
        parts = [f"Familia BAXY: {family}."]
        for capability in sorted(groups[family], key=lambda row: str(row["name"])):
            parts.append(
                f"Operación: {capability['name']}. {capability['description']} Riesgo: {capability['risk']}. Schema: {json.dumps(capability['argumentsSchema'], ensure_ascii=False, sort_keys=True)}"
            )
        documents.append("\n".join(parts))
    return names, documents


def _quantiles(values: np.ndarray) -> dict[str, float]:
    return {name: float(np.quantile(values, quantile)) for name, quantile in (("min", 0.0), ("p50", 0.5), ("p95", 0.95), ("max", 1.0))}


def run() -> dict[str, Any]:
    preregistration = json.loads(r235.OUTPUT.read_text(encoding="utf-8"))
    if preregistration != r235.build():
        raise RuntimeError("R235 preregistration identity changed")
    from sentence_transformers import SentenceTransformer

    inside, outside = sample_rows()
    names, documents = family_documents()
    started = time.monotonic()
    model = SentenceTransformer(str(r235.r232.r231.CANDIDATE_ROOT), device="cpu")
    model.max_seq_length = 256
    family_vectors = np.asarray(model.encode(documents, normalize_embeddings=True, batch_size=8, show_progress_bar=False), dtype=np.float32)
    query_vectors = np.asarray(model.encode([row["text"] for row in [*inside, *outside]], normalize_embeddings=True, batch_size=16, show_progress_bar=False), dtype=np.float32)
    scores = query_vectors @ family_vectors.T
    top_scores = scores.max(axis=1)
    threshold = float(np.nextafter(top_scores[:INSIDE_COUNT].min(), -np.inf))
    accepted = top_scores >= threshold
    inside_lost = int((~accepted[:INSIDE_COUNT]).sum())
    outside_zero = int((~accepted[INSIDE_COUNT:]).sum())
    return {
        "schema": "baxy.bge-m3-semantic-abstention.r236-development-result.v1",
        "authority": "development_only_cpu_probe_not_a_runtime_or_r228_measurement",
        "candidate": {
            "model_id": "BAAI/bge-m3",
            "revision": "5617a9f61b028005a4858fdac845db406aefb181",
            "device": "cpu",
            "family_documents": len(names),
            "catalog_operations": 174,
            "threshold": threshold,
            "threshold_rule": "nextafter_below_minimum_selected_inside_score",
        },
        "development_population": {
            "inside_rows": INSIDE_COUNT,
            "outside_rows": OUTSIDE_COUNT,
            "sources": ["PRESTO v1", "MASSIVE v1.1"],
            "texts_retained": False,
            "source_ids_retained": False,
        },
        "observed": {
            "inside_rows_lost": inside_lost,
            "outside_zero_candidates": outside_zero,
            "outside_zero_candidate_rate": outside_zero / OUTSIDE_COUNT,
            "inside_score_quantiles": _quantiles(top_scores[:INSIDE_COUNT]),
            "outside_score_quantiles": _quantiles(top_scores[INSIDE_COUNT:]),
            "elapsed_seconds": time.monotonic() - started,
        },
        "constraints": {
            "r228_opened": False,
            "public_holdout_opened": False,
            "registered_runtime_modified": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "next_requirement": "A fresh OOS population and full runner remain required before any R228 opening or runtime integration.",
        "identities": {
            "preregistration_sha256": sha256(r235.OUTPUT),
            "runtime_corpus_sha256": sha256(RUNTIME),
            "catalog_sha256": sha256(CATALOG),
            "program_sha256": sha256(Path(__file__)),
        },
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite development result: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(run(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
