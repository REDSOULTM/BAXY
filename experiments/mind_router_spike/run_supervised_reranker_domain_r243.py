"""Run the sealed supervised reranker domain-abstention probe once on CUDA."""

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

from experiments.mind_router_spike import preregister_supervised_reranker_domain_r242 as r242
from experiments.mind_router_spike import run_bge_m3_semantic_abstention_r236 as r236


RUNTIME = REPO / "tests/data/turn_evidence_runtime.v1.jsonl"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
R207 = REPO / "artifacts/development/r207_cross_encoder_pairs.jsonl"
OUTPUT = REPO / "artifacts/development/supervised_reranker_domain_r243.json"
MODEL_OUTPUT = Path(r"D:\BAXYRuntime\candidates\bge-reranker-r243-supervised")
INSIDE_COUNT = 256
OUTSIDE_COUNT = 256
TRAIN_OOS_QUERIES = 256
BATCH_SIZE = 4
ACCUMULATION_STEPS = 4
MAX_LENGTH = 256
LEARNING_RATE = 1e-5
SEED = 242243


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return r236.public_rows()


def _sample_development_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    inside, outside = _rows()
    prior_inside, prior_outside = r236.sample_rows()
    reserved = {row["source_id"] for row in [*prior_inside, *prior_outside]}
    available_inside = sorted((row for row in inside if row["source_id"] not in reserved), key=lambda row: _key(row["source_id"]))
    available_outside = sorted((row for row in outside if row["source_id"] not in reserved), key=lambda row: _key(row["source_id"]))
    evaluation_inside = available_inside[:INSIDE_COUNT]
    evaluation_outside = available_outside[:OUTSIDE_COUNT]
    training_outside = available_outside[OUTSIDE_COUNT : OUTSIDE_COUNT + TRAIN_OOS_QUERIES]
    if len(evaluation_inside) != INSIDE_COUNT or len(evaluation_outside) != OUTSIDE_COUNT or len(training_outside) != TRAIN_OOS_QUERIES:
        raise RuntimeError("R243 requires all fresh development partitions")
    return evaluation_inside, evaluation_outside, training_outside


def family_documents() -> tuple[list[str], dict[str, str]]:
    capabilities = json.loads(CATALOG.read_text(encoding="utf-8"))["catalogue"]["capabilities"]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for capability in capabilities:
        groups[str(capability["name"]).split(".", 1)[0]].append(capability)
    documents: dict[str, str] = {}
    for family in sorted(groups):
        parts = [f"Familia BAXY: {family}."]
        for capability in sorted(groups[family], key=lambda row: str(row["name"])):
            parts.append(f"Operación: {capability['name']}. {capability['description']} Riesgo: {capability['risk']}. Schema: {json.dumps(capability['argumentsSchema'], ensure_ascii=False, sort_keys=True)}")
        documents[family] = "\n".join(parts)
    return sorted(documents), documents


def training_pairs(documents: dict[str, str], training_outside: list[dict[str, Any]]) -> list[tuple[str, str, float]]:
    pairs = [json.loads(line) for line in R207.read_text(encoding="utf-8").splitlines() if line]
    positive: list[tuple[str, str, float]] = []
    negative: list[tuple[str, str, float]] = []
    for pair in pairs:
        family = str(pair["operation"]).split(".", 1)[0]
        if family not in documents:
            continue
        row = (str(pair["query"]), documents[family], float(pair["target"]))
        (positive if pair["target"] == 1 else negative).append(row)
    negative = sorted(negative, key=lambda row: _key(row[0] + "\0" + row[1]))[: len(positive)]
    out_of_scope = [(row["text"], document, 0.0) for row in training_outside for document in documents.values()]
    result = [*positive, *negative, *out_of_scope]
    if not positive or len(negative) != len(positive) or not out_of_scope:
        raise RuntimeError("R243 training pair construction failed")
    return sorted(result, key=lambda row: _key(row[0] + "\0" + row[1] + "\0" + str(row[2])))


def _quantiles(values: np.ndarray) -> dict[str, float]:
    return {name: float(np.quantile(values, quantile)) for name, quantile in (("min", 0.0), ("p50", 0.5), ("p95", 0.95), ("max", 1.0))}


def _merkle(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update((path.relative_to(root).as_posix() + "\0" + sha256(path) + "\n").encode("utf-8"))
    return digest.hexdigest()


def run() -> dict[str, Any]:
    preregistration = json.loads(r242.OUTPUT.read_text(encoding="utf-8"))
    if preregistration != r242.build():
        raise RuntimeError("R243 preregistration identity changed")
    if OUTPUT.exists() or MODEL_OUTPUT.exists():
        raise RuntimeError("R243 refuses to overwrite a result or trained candidate")
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("R243 requires the sealed CUDA environment")
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    device = torch.device("cuda")
    names, documents = family_documents()
    evaluation_inside, evaluation_outside, training_outside = _sample_development_rows()
    train_pairs = training_pairs(documents, training_outside)
    root = r242.r238.r237.ROOT
    tokenizer = AutoTokenizer.from_pretrained(str(root), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(str(root), local_files_only=True, torch_dtype=torch.float16).to(device)
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    loss_sum = 0.0
    started = time.monotonic()
    model.train()
    optimizer.zero_grad(set_to_none=True)
    for batch_number, start in enumerate(range(0, len(train_pairs), BATCH_SIZE), start=1):
        batch = train_pairs[start : start + BATCH_SIZE]
        encoded = tokenizer([item[0] for item in batch], [item[1] for item in batch], padding=True, truncation=True, max_length=MAX_LENGTH, return_tensors="pt").to(device)
        labels = torch.tensor([item[2] for item in batch], device=device)
        with torch.autocast(device_type="cuda", dtype=torch.float16):
            logits = model(**encoded).logits.reshape(-1).float()
            loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels) / ACCUMULATION_STEPS
        loss.backward()
        loss_sum += float(loss.item()) * ACCUMULATION_STEPS
        if batch_number % ACCUMULATION_STEPS == 0 or start + BATCH_SIZE >= len(train_pairs):
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            optimizer.zero_grad(set_to_none=True)
    model.eval()
    queries = [row["text"] for row in [*evaluation_inside, *evaluation_outside]]
    scores: list[float] = []
    with torch.inference_mode():
        for query in queries:
            for start in range(0, len(names), BATCH_SIZE):
                batch_names = names[start : start + BATCH_SIZE]
                encoded = tokenizer([query] * len(batch_names), [documents[name] for name in batch_names], padding=True, truncation=True, max_length=MAX_LENGTH, return_tensors="pt").to(device)
                with torch.autocast(device_type="cuda", dtype=torch.float16):
                    scores.extend(torch.sigmoid(model(**encoded).logits.reshape(-1)).float().cpu().tolist())
    matrix = np.asarray(scores, dtype=np.float64).reshape(len(queries), len(names))
    maximums = matrix.max(axis=1)
    threshold = float(np.nextafter(maximums[:INSIDE_COUNT].min(), -np.inf))
    accepted = maximums >= threshold
    inside_lost = int((~accepted[:INSIDE_COUNT]).sum())
    outside_zero = int((~accepted[INSIDE_COUNT:]).sum())
    MODEL_OUTPUT.mkdir(parents=True)
    model.save_pretrained(str(MODEL_OUTPUT), safe_serialization=True)
    tokenizer.save_pretrained(str(MODEL_OUTPUT))
    trained_merkle = _merkle(MODEL_OUTPUT)
    peak_mib = float(torch.cuda.max_memory_allocated(device) / (1024 * 1024))
    del model
    gc.collect()
    torch.cuda.empty_cache()
    verdict = "candidate_not_promoted_requires_fresh_oos" if outside_zero == OUTSIDE_COUNT else "rejected_development_oos_separation"
    return {
        "schema": "baxy.supervised-reranker-domain.r243-result.v1",
        "authority": "isolated_cuda_development_probe_not_runtime_or_r228_measurement",
        "verdict": verdict,
        "candidate": {"base": r242.r238.r237.MODEL + "@" + r242.r238.r237.REVISION, "trained_candidate": str(MODEL_OUTPUT), "trained_candidate_merkle_sha256": trained_merkle, "device": "cuda", "family_documents": len(names), "pair_count_evaluated": len(queries) * len(names), "threshold": threshold},
        "training": {"pairs": len(train_pairs), "epochs": 1, "batch_size": BATCH_SIZE, "gradient_accumulation_steps": ACCUMULATION_STEPS, "learning_rate": LEARNING_RATE, "mean_loss": loss_sum / ((len(train_pairs) + BATCH_SIZE - 1) // BATCH_SIZE), "peak_allocated_mib": peak_mib},
        "development_population": {"inside_rows": INSIDE_COUNT, "outside_rows": OUTSIDE_COUNT, "training_oos_rows": TRAIN_OOS_QUERIES, "texts_retained": False, "source_ids_retained": False},
        "observed": {"inside_rows_lost": inside_lost, "outside_zero_candidates": outside_zero, "outside_zero_candidate_rate": outside_zero / OUTSIDE_COUNT, "inside_score_quantiles": _quantiles(maximums[:INSIDE_COUNT]), "outside_score_quantiles": _quantiles(maximums[INSIDE_COUNT:]), "elapsed_seconds": time.monotonic() - started},
        "constraints": {"r228_opened": False, "public_holdout_opened": False, "registered_runtime_modified": False, "providers_enabled": False, "effects_executed": 0, "opened_v9": False, "voice_stt_wake_exercised": False},
        "next_requirement": "Do not tune this threshold or open R228. Any candidate needs a separately sealed fresh OOS runner and visible-text audit.",
        "identities": {"preregistration_sha256": sha256(r242.OUTPUT), "runtime_corpus_sha256": sha256(RUNTIME), "catalog_sha256": sha256(CATALOG), "r207_sha256": sha256(R207), "program_sha256": sha256(Path(__file__))},
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite result: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(run(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
