"""Run the sealed R247 direct typed-family plus abstain classifier once on CUDA."""

from __future__ import annotations

import gc
import hashlib
import json
import math
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import preregister_direct_abstain_classifier_r247 as r247
from experiments.mind_router_spike import run_bge_m3_semantic_abstention_r236 as r236
from experiments.mind_router_spike import run_head_only_reranker_domain_r246 as r246
from experiments.mind_router_spike import run_supervised_reranker_domain_r243 as r243


RUNTIME = REPO / "tests/data/turn_evidence_runtime.v1.jsonl"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
R207 = REPO / "artifacts/development/r207_cross_encoder_pairs.jsonl"
OUTPUT = REPO / "artifacts/development/direct_abstain_classifier_r248.json"
MODEL_OUTPUT = Path(r"D:\BAXYRuntime\candidates\bge-reranker-r248-direct-abstain")
INSIDE_COUNT = 256
OUTSIDE_COUNT = 256
BATCH_SIZE = 32
MAX_LENGTH = 128
LEARNING_RATE = 2e-4
SEED = 247248
ABSTAIN = "__abstain__"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def family_names() -> list[str]:
    capabilities = json.loads(CATALOG.read_text(encoding="utf-8"))["catalogue"]["capabilities"]
    names = sorted({str(capability["name"]).split(".", 1)[0] for capability in capabilities})
    if len(names) != 31:
        raise RuntimeError("R248 requires exactly 31 current typed families")
    return names


def development_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    inside, outside = r243._rows()
    r236_inside, r236_outside = r236.sample_rows()
    r243_inside, r243_outside, r243_train = r243._sample_development_rows()
    r246_inside, r246_outside, r246_train = r246.development_rows()
    reserved = {
        row["source_id"]
        for row in [
            *r236_inside,
            *r236_outside,
            *r243_inside,
            *r243_outside,
            *r243_train,
            *r246_inside,
            *r246_outside,
            *r246_train,
        ]
    }
    fresh_inside = sorted((row for row in inside if row["source_id"] not in reserved), key=lambda row: _key(row["source_id"]))
    fresh_outside = sorted((row for row in outside if row["source_id"] not in reserved), key=lambda row: _key(row["source_id"]))
    evaluation_inside = fresh_inside[:INSIDE_COUNT]
    evaluation_outside = fresh_outside[:OUTSIDE_COUNT]
    if len(evaluation_inside) != INSIDE_COUNT or len(evaluation_outside) != OUTSIDE_COUNT:
        raise RuntimeError("R248 requires fresh disjoint development evaluation rows")
    return evaluation_inside, evaluation_outside, fresh_outside[OUTSIDE_COUNT:]


def training_rows(
    names: list[str], evaluation_inside: list[dict[str, Any]], evaluation_outside: list[dict[str, Any]], fresh_outside: list[dict[str, Any]]
) -> list[tuple[str, int]]:
    index = {name: number for number, name in enumerate(names)}
    evaluated = {_normalize(row["text"]) for row in [*evaluation_inside, *evaluation_outside]}
    positives: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for line in R207.read_text(encoding="utf-8").splitlines():
        pair = json.loads(line)
        if pair["target"] != 1:
            continue
        family = str(pair["operation"]).split(".", 1)[0]
        query = str(pair["query"])
        row = (_normalize(query), index.get(family, -1))
        if row[1] < 0:
            continue
        if row[0] in evaluated:
            raise RuntimeError("R248 training text overlaps its fresh evaluation population")
        if row not in seen:
            seen.add(row)
            positives.append((query, row[1]))
    if not positives or set(label for _, label in positives) != set(range(len(names))):
        raise RuntimeError("R248 requires R207 positives for every current typed family")
    abstain_count = len(positives)
    if len(fresh_outside) < abstain_count:
        raise RuntimeError("R248 requires enough fresh OOS rows to balance all in-catalog positives")
    abstain_rows = [(row["text"], len(names)) for row in fresh_outside[:abstain_count]]
    return sorted([*positives, *abstain_rows], key=lambda row: _key(row[0] + "\0" + str(row[1])))


def _quantiles(values: np.ndarray) -> dict[str, float]:
    return {name: float(np.quantile(values, quantile)) for name, quantile in (("min", 0.0), ("p50", 0.5), ("p95", 0.95), ("max", 1.0))}


def _merkle(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update((path.relative_to(root).as_posix() + "\0" + sha256(path) + "\n").encode("utf-8"))
    return digest.hexdigest()


def _batches(rows: list[tuple[str, int]]) -> list[list[tuple[str, int]]]:
    return [rows[start : start + BATCH_SIZE] for start in range(0, len(rows), BATCH_SIZE)]


def run() -> dict[str, Any]:
    preregistration = json.loads(r247.OUTPUT.read_text(encoding="utf-8"))
    if preregistration != r247.build():
        raise RuntimeError("R248 preregistration identity changed")
    if OUTPUT.exists() or MODEL_OUTPUT.exists():
        raise RuntimeError("R248 refuses to overwrite a result or trained candidate")
    import torch
    from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("R248 requires CUDA BF16 support")
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    device = torch.device("cuda")
    names = family_names()
    labels = [*names, ABSTAIN]
    evaluation_inside, evaluation_outside, fresh_outside = development_rows()
    training = training_rows(names, evaluation_inside, evaluation_outside, fresh_outside)
    counts = Counter(label for _, label in training)
    if set(counts) != set(range(len(labels))):
        raise RuntimeError("R248 training classes are incomplete")
    class_weights = torch.tensor([len(training) / (len(labels) * counts[label]) for label in range(len(labels))], dtype=torch.float32, device=device)
    root = r247.r245.r238.r237.ROOT
    tokenizer = AutoTokenizer.from_pretrained(str(root), local_files_only=True)
    config = AutoConfig.from_pretrained(str(root), local_files_only=True, num_labels=len(labels), id2label={number: label for number, label in enumerate(labels)}, label2id={label: number for number, label in enumerate(labels)})
    model = AutoModelForSequenceClassification.from_pretrained(str(root), config=config, ignore_mismatched_sizes=True, local_files_only=True).to(device)
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    classifier = getattr(model, "classifier", None)
    if classifier is None:
        raise RuntimeError("R248 model lacks sequence classification head")
    classifier.float()
    for parameter in classifier.parameters():
        parameter.requires_grad_(True)
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=LEARNING_RATE)
    loss_sum = 0.0
    started = time.monotonic()
    model.train()
    for batch in _batches(training):
        encoded = tokenizer([query for query, _ in batch], padding=True, truncation=True, max_length=MAX_LENGTH, return_tensors="pt").to(device)
        targets = torch.tensor([label for _, label in batch], dtype=torch.long, device=device)
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            logits = model(**encoded).logits.float()
            loss = torch.nn.functional.cross_entropy(logits, targets, weight=class_weights)
        if not torch.isfinite(loss):
            raise RuntimeError("R248 non-finite training loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(trainable, 1.0)
        optimizer.step()
        loss_sum += float(loss.item())
    model.eval()
    probabilities: list[np.ndarray] = []
    queries = [row["text"] for row in [*evaluation_inside, *evaluation_outside]]
    with torch.inference_mode():
        for start in range(0, len(queries), BATCH_SIZE):
            encoded = tokenizer(queries[start : start + BATCH_SIZE], padding=True, truncation=True, max_length=MAX_LENGTH, return_tensors="pt").to(device)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                probabilities.append(torch.softmax(model(**encoded).logits.float(), dim=1).cpu().numpy())
    matrix = np.concatenate(probabilities, axis=0).astype(np.float64, copy=False)
    if matrix.shape != (len(queries), len(labels)) or not np.isfinite(matrix).all() or not math.isfinite(loss_sum):
        raise RuntimeError("R248 non-finite or malformed evaluation scores")
    known_maximums = matrix[:, : len(names)].max(axis=1)
    abstain_probabilities = matrix[:, len(names)]
    margins = known_maximums - abstain_probabilities
    threshold = float(np.nextafter(margins[:INSIDE_COUNT].min(), -np.inf))
    accepted = margins >= threshold
    predicted = matrix[:, : len(names)].argmax(axis=1)
    expected = np.asarray([names.index(row["families"][0]) for row in evaluation_inside], dtype=np.int64)
    inside_lost = int((~accepted[:INSIDE_COUNT]).sum())
    inside_mismatches = int((predicted[:INSIDE_COUNT] != expected).sum())
    outside_zero = int((~accepted[INSIDE_COUNT:]).sum())
    MODEL_OUTPUT.mkdir(parents=True)
    model.save_pretrained(str(MODEL_OUTPUT), safe_serialization=True)
    tokenizer.save_pretrained(str(MODEL_OUTPUT))
    candidate_merkle = _merkle(MODEL_OUTPUT)
    peak_mib = float(torch.cuda.max_memory_allocated(device) / (1024 * 1024))
    del model
    gc.collect()
    torch.cuda.empty_cache()
    passed = inside_lost == 0 and inside_mismatches == 0 and outside_zero == OUTSIDE_COUNT
    return {
        "schema": "baxy.direct-abstain-classifier.r248-result.v1",
        "authority": "isolated_cuda_development_probe_not_runtime_or_r228_measurement",
        "verdict": "candidate_not_promoted_requires_fresh_oos" if passed else "rejected_development_family_or_oos_separation",
        "candidate": {"base": r247.r245.r238.r237.MODEL + "@" + r247.r245.r238.r237.REVISION, "trained_candidate": str(MODEL_OUTPUT), "trained_candidate_merkle_sha256": candidate_merkle, "device": "cuda_bf16", "classifier_labels": labels, "trainable_parameters": sum(parameter.numel() for parameter in trainable), "threshold": threshold, "threshold_rule": "nextafter_below_minimum_inside_known_probability_minus_explicit_abstain_probability"},
        "training": {"rows": len(training), "class_counts": {labels[number]: counts[number] for number in range(len(labels))}, "epochs": 1, "batch_size": BATCH_SIZE, "max_length": MAX_LENGTH, "learning_rate": LEARNING_RATE, "class_balanced_loss": True, "mean_loss": loss_sum / len(_batches(training)), "peak_allocated_mib": peak_mib},
        "development_population": {"inside_rows": INSIDE_COUNT, "outside_rows": OUTSIDE_COUNT, "fresh_training_oos_rows": counts[len(names)], "texts_retained": False, "source_ids_retained": False},
        "observed": {"inside_rows_lost": inside_lost, "inside_family_mismatches": inside_mismatches, "inside_family_exact_rate": (INSIDE_COUNT - inside_mismatches) / INSIDE_COUNT, "outside_zero_candidates": outside_zero, "outside_zero_candidate_rate": outside_zero / OUTSIDE_COUNT, "inside_margin_quantiles": _quantiles(margins[:INSIDE_COUNT]), "outside_margin_quantiles": _quantiles(margins[INSIDE_COUNT:]), "inside_abstain_probability_quantiles": _quantiles(abstain_probabilities[:INSIDE_COUNT]), "outside_abstain_probability_quantiles": _quantiles(abstain_probabilities[INSIDE_COUNT:]), "elapsed_seconds": time.monotonic() - started},
        "constraints": {"r228_opened": False, "public_holdout_opened": False, "registered_runtime_modified": False, "providers_enabled": False, "effects_executed": 0, "opened_v9": False, "voice_stt_wake_exercised": False},
        "next_requirement": "Do not tune this threshold or open R228. Only a passing candidate may receive a separately sealed fresh OOS runner and visible-text audit.",
        "identities": {"preregistration_sha256": sha256(r247.OUTPUT), "runtime_corpus_sha256": sha256(RUNTIME), "catalog_sha256": sha256(CATALOG), "r207_sha256": sha256(R207), "program_sha256": sha256(Path(__file__))},
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite result: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(run(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
