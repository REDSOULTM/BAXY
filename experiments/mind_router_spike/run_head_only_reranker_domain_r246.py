"""Run the R245 frozen-base, finite-gated domain probe once on CUDA."""

from __future__ import annotations

import gc
import hashlib
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import preregister_head_only_reranker_domain_r245 as r245
from experiments.mind_router_spike import run_supervised_reranker_domain_r243 as r243


RUNTIME = REPO / "tests/data/turn_evidence_runtime.v1.jsonl"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
OUTPUT = REPO / "artifacts/development/head_only_reranker_domain_r246.json"
MODEL_OUTPUT = Path(r"D:\BAXYRuntime\candidates\bge-reranker-r246-head-only")
INSIDE_COUNT = 256
OUTSIDE_COUNT = 256
TRAIN_OOS_QUERIES = 256
BATCH_SIZE = 8
MAX_LENGTH = 256
LEARNING_RATE = 2e-4
SEED = 245246


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def development_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    inside, outside = r243._rows()
    r236_inside, r236_outside = r243.r236.sample_rows()
    r243_inside, r243_outside, r243_train = r243._sample_development_rows()
    reserved = {row["source_id"] for row in [*r236_inside, *r236_outside, *r243_inside, *r243_outside, *r243_train]}
    fresh_inside = sorted((row for row in inside if row["source_id"] not in reserved), key=lambda row: _key(row["source_id"]))
    fresh_outside = sorted((row for row in outside if row["source_id"] not in reserved), key=lambda row: _key(row["source_id"]))
    evaluation_inside = fresh_inside[:INSIDE_COUNT]
    evaluation_outside = fresh_outside[:OUTSIDE_COUNT]
    training_outside = fresh_outside[OUTSIDE_COUNT : OUTSIDE_COUNT + TRAIN_OOS_QUERIES]
    if len(evaluation_inside) != INSIDE_COUNT or len(evaluation_outside) != OUTSIDE_COUNT or len(training_outside) != TRAIN_OOS_QUERIES:
        raise RuntimeError("R246 requires fresh disjoint development partitions")
    return evaluation_inside, evaluation_outside, training_outside


def _quantiles(values: np.ndarray) -> dict[str, float]:
    return {name: float(np.quantile(values, quantile)) for name, quantile in (("min", 0.0), ("p50", 0.5), ("p95", 0.95), ("max", 1.0))}


def _merkle(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update((path.relative_to(root).as_posix() + "\0" + sha256(path) + "\n").encode("utf-8"))
    return digest.hexdigest()


def run() -> dict[str, Any]:
    preregistration = json.loads(r245.OUTPUT.read_text(encoding="utf-8"))
    if preregistration != r245.build():
        raise RuntimeError("R246 preregistration identity changed")
    if OUTPUT.exists() or MODEL_OUTPUT.exists():
        raise RuntimeError("R246 refuses to overwrite a result or trained candidate")
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("R246 requires CUDA BF16 support")
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    device = torch.device("cuda")
    names, documents = r243.family_documents()
    evaluation_inside, evaluation_outside, training_outside = development_rows()
    train_pairs = r243.training_pairs(documents, training_outside)
    root = r245.r238.r237.ROOT
    tokenizer = AutoTokenizer.from_pretrained(str(root), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(str(root), local_files_only=True).to(device)
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    classifier = getattr(model, "classifier", None)
    if classifier is None:
        raise RuntimeError("R246 model lacks sequence classification head")
    classifier.float()
    for parameter in classifier.parameters():
        parameter.requires_grad_(True)
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=LEARNING_RATE)
    loss_sum = 0.0
    started = time.monotonic()
    model.train()
    for start in range(0, len(train_pairs), BATCH_SIZE):
        batch = train_pairs[start : start + BATCH_SIZE]
        encoded = tokenizer([item[0] for item in batch], [item[1] for item in batch], padding=True, truncation=True, max_length=MAX_LENGTH, return_tensors="pt").to(device)
        labels = torch.tensor([item[2] for item in batch], device=device)
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            logits = model(**encoded).logits.reshape(-1).float()
            loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels)
        if not torch.isfinite(loss):
            raise RuntimeError("R246 non-finite training loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(trainable, 1.0)
        optimizer.step()
        loss_sum += float(loss.item())
    model.eval()
    queries = [row["text"] for row in [*evaluation_inside, *evaluation_outside]]
    scores: list[float] = []
    with torch.inference_mode():
        for query in queries:
            for start in range(0, len(names), BATCH_SIZE):
                batch_names = names[start : start + BATCH_SIZE]
                encoded = tokenizer([query] * len(batch_names), [documents[name] for name in batch_names], padding=True, truncation=True, max_length=MAX_LENGTH, return_tensors="pt").to(device)
                with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                    scores.extend(torch.sigmoid(model(**encoded).logits.reshape(-1)).float().cpu().tolist())
    matrix = np.asarray(scores, dtype=np.float64).reshape(len(queries), len(names))
    maximums = matrix.max(axis=1)
    if not np.isfinite(maximums).all() or not math.isfinite(loss_sum):
        raise RuntimeError("R246 non-finite evaluation scores")
    threshold = float(np.nextafter(maximums[:INSIDE_COUNT].min(), -np.inf))
    accepted = maximums >= threshold
    inside_lost = int((~accepted[:INSIDE_COUNT]).sum())
    outside_zero = int((~accepted[INSIDE_COUNT:]).sum())
    MODEL_OUTPUT.mkdir(parents=True)
    model.save_pretrained(str(MODEL_OUTPUT), safe_serialization=True)
    tokenizer.save_pretrained(str(MODEL_OUTPUT))
    candidate_merkle = _merkle(MODEL_OUTPUT)
    peak_mib = float(torch.cuda.max_memory_allocated(device) / (1024 * 1024))
    del model
    gc.collect()
    torch.cuda.empty_cache()
    verdict = "candidate_not_promoted_requires_fresh_oos" if outside_zero == OUTSIDE_COUNT else "rejected_development_oos_separation"
    return {
        "schema": "baxy.head-only-reranker-domain.r246-result.v1",
        "authority": "isolated_cuda_development_probe_not_runtime_or_r228_measurement",
        "verdict": verdict,
        "candidate": {"base": r245.r238.r237.MODEL + "@" + r245.r238.r237.REVISION, "trained_candidate": str(MODEL_OUTPUT), "trained_candidate_merkle_sha256": candidate_merkle, "device": "cuda_bf16", "trainable_parameters": sum(parameter.numel() for parameter in trainable), "family_documents": len(names), "pair_count_evaluated": len(queries) * len(names), "threshold": threshold},
        "training": {"pairs": len(train_pairs), "epochs": 1, "batch_size": BATCH_SIZE, "learning_rate": LEARNING_RATE, "mean_loss": loss_sum / ((len(train_pairs) + BATCH_SIZE - 1) // BATCH_SIZE), "peak_allocated_mib": peak_mib},
        "development_population": {"inside_rows": INSIDE_COUNT, "outside_rows": OUTSIDE_COUNT, "training_oos_rows": TRAIN_OOS_QUERIES, "texts_retained": False, "source_ids_retained": False},
        "observed": {"inside_rows_lost": inside_lost, "outside_zero_candidates": outside_zero, "outside_zero_candidate_rate": outside_zero / OUTSIDE_COUNT, "inside_score_quantiles": _quantiles(maximums[:INSIDE_COUNT]), "outside_score_quantiles": _quantiles(maximums[INSIDE_COUNT:]), "elapsed_seconds": time.monotonic() - started},
        "constraints": {"r228_opened": False, "public_holdout_opened": False, "registered_runtime_modified": False, "providers_enabled": False, "effects_executed": 0, "opened_v9": False, "voice_stt_wake_exercised": False},
        "next_requirement": "Do not tune this threshold or open R228; any candidate needs a separately sealed fresh OOS runner and visible-text audit.",
        "identities": {"preregistration_sha256": sha256(r245.OUTPUT), "runtime_corpus_sha256": sha256(RUNTIME), "catalog_sha256": sha256(CATALOG), "program_sha256": sha256(Path(__file__))},
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite result: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(run(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
