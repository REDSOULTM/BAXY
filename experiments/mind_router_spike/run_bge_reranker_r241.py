"""Run the sealed R240 GPU cross-encoder abstention development probe once."""

from __future__ import annotations

import gc
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

from experiments.mind_router_spike import preregister_bge_reranker_r240 as r240


RUNTIME = REPO / "tests/data/turn_evidence_runtime.v1.jsonl"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
OUTPUT = REPO / "artifacts/development/bge_reranker_r241_development.json"
INSIDE_COUNT = 256
OUTSIDE_COUNT = 256
BATCH_SIZE = 8
MAX_LENGTH = 256


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
    selected = [sorted(rows, key=lambda row: _key(row["source_id"]))[0] for _, rows in sorted(by_family.items())]
    selected_ids = {row["source_id"] for row in selected}
    remainder = sorted((row for rows in by_family.values() for row in rows if row["source_id"] not in selected_ids), key=lambda row: _key(row["source_id"]))
    selected.extend(remainder[: INSIDE_COUNT - len(selected)])
    selected_outside = sorted(outside, key=lambda row: _key(row["source_id"]))[:OUTSIDE_COUNT]
    if len(selected) != INSIDE_COUNT or len(selected_outside) != OUTSIDE_COUNT:
        raise RuntimeError("R241 requires exact public development sample counts")
    return selected, selected_outside


def family_documents() -> tuple[list[str], list[str]]:
    capabilities = json.loads(CATALOG.read_text(encoding="utf-8"))["catalogue"]["capabilities"]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for capability in capabilities:
        groups[str(capability["name"]).split(".", 1)[0]].append(capability)
    names = sorted(groups)
    documents: list[str] = []
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


def score_pairs(queries: list[str], documents: list[str]) -> np.ndarray:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    root = r240.r238.r237.ROOT
    tokenizer = AutoTokenizer.from_pretrained(str(root), local_files_only=True)
    if not torch.cuda.is_available():
        raise RuntimeError("R241 requires CUDA; do not substitute a CPU probe for the sealed GPU run")
    device = torch.device("cuda")
    model = AutoModelForSequenceClassification.from_pretrained(str(root), local_files_only=True).to(device).eval()
    scores: list[float] = []
    try:
        with torch.inference_mode():
            for query in queries:
                for start in range(0, len(documents), BATCH_SIZE):
                    batch = documents[start : start + BATCH_SIZE]
                    encoded = tokenizer([query] * len(batch), batch, padding=True, truncation=True, max_length=MAX_LENGTH, return_tensors="pt").to(device)
                    scores.extend(torch.sigmoid(model(**encoded).logits.reshape(-1)).cpu().tolist())
    finally:
        del model
        gc.collect()
        torch.cuda.empty_cache()
    return np.asarray(scores, dtype=np.float64).reshape(len(queries), len(documents))


def run() -> dict[str, Any]:
    preregistration = json.loads(r240.OUTPUT.read_text(encoding="utf-8"))
    if preregistration != r240.build():
        raise RuntimeError("R241 preregistration identity changed")
    inside, outside = sample_rows()
    names, documents = family_documents()
    started = time.monotonic()
    scores = score_pairs([row["text"] for row in [*inside, *outside]], documents)
    top_scores = scores.max(axis=1)
    threshold = float(np.nextafter(top_scores[:INSIDE_COUNT].min(), -np.inf))
    accepted = top_scores >= threshold
    inside_lost = int((~accepted[:INSIDE_COUNT]).sum())
    outside_zero = int((~accepted[INSIDE_COUNT:]).sum())
    verdict = "candidate_not_promoted_requires_fresh_oos" if outside_zero == OUTSIDE_COUNT else "rejected_development_oos_separation"
    return {
        "schema": "baxy.bge-reranker.r241-development-result.v1",
        "authority": "gpu_development_probe_not_runtime_or_r228_measurement",
        "verdict": verdict,
        "candidate": {"model": r240.r238.r237.MODEL + "@" + r240.r238.r237.REVISION, "device": "cuda", "family_documents": len(names), "catalog_operations": 174, "pair_count": len(top_scores) * len(names), "threshold": threshold, "threshold_rule": "nextafter_below_minimum_selected_inside_score"},
        "development_population": {"inside_rows": INSIDE_COUNT, "outside_rows": OUTSIDE_COUNT, "sources": ["PRESTO v1", "MASSIVE v1.1"], "texts_retained": False, "source_ids_retained": False},
        "observed": {"inside_rows_lost": inside_lost, "outside_zero_candidates": outside_zero, "outside_zero_candidate_rate": outside_zero / OUTSIDE_COUNT, "inside_score_quantiles": _quantiles(top_scores[:INSIDE_COUNT]), "outside_score_quantiles": _quantiles(top_scores[INSIDE_COUNT:]), "elapsed_seconds": time.monotonic() - started},
        "constraints": {"r228_opened": False, "public_holdout_opened": False, "registered_runtime_modified": False, "providers_enabled": False, "effects_executed": 0, "opened_v9": False, "voice_stt_wake_exercised": False},
        "next_requirement": "Do not tune this threshold or open R228; any candidate needs a separately sealed fresh OOS runner.",
        "identities": {"preregistration_sha256": sha256(r240.OUTPUT), "runtime_corpus_sha256": sha256(RUNTIME), "catalog_sha256": sha256(CATALOG), "program_sha256": sha256(Path(__file__))},
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite development result: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(run(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
