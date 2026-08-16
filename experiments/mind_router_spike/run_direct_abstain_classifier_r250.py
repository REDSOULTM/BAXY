"""Run the feasible sealed R249 direct abstain classifier once on CUDA."""

from __future__ import annotations

import gc
import hashlib
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import preregister_direct_abstain_classifier_r249 as r249
from experiments.mind_router_spike import run_direct_abstain_classifier_r248 as r248


OUTPUT = REPO / "artifacts/development/direct_abstain_classifier_r250.json"
MODEL_OUTPUT = Path(r"D:\BAXYRuntime\candidates\bge-reranker-r250-direct-abstain")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def training_rows(
    names: list[str], evaluation_inside: list[dict[str, Any]], evaluation_outside: list[dict[str, Any]], fresh_outside: list[dict[str, Any]]
) -> list[tuple[str, int]]:
    index = {name: number for number, name in enumerate(names)}
    evaluated = {r248._normalize(row["text"]) for row in [*evaluation_inside, *evaluation_outside]}
    positives: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for line in r248.R207.read_text(encoding="utf-8").splitlines():
        pair = json.loads(line)
        if pair["target"] != 1:
            continue
        query = str(pair["query"])
        row = (r248._normalize(query), index.get(str(pair["operation"]).split(".", 1)[0], -1))
        if row[1] < 0:
            continue
        if row[0] in evaluated:
            raise RuntimeError("R250 training text overlaps its fresh evaluation population")
        if row not in seen:
            seen.add(row)
            positives.append((query, row[1]))
    if not positives or set(label for _, label in positives) != set(range(len(names))):
        raise RuntimeError("R250 requires R207 positives for every current typed family")
    abstain_rows = [(row["text"], len(names)) for row in fresh_outside]
    if not abstain_rows:
        raise RuntimeError("R250 requires every fresh OOS row available after evaluation")
    return sorted([*positives, *abstain_rows], key=lambda row: r248._key(row[0] + "\0" + str(row[1])))


def run() -> dict[str, Any]:
    preregistration = json.loads(r249.OUTPUT.read_text(encoding="utf-8"))
    if preregistration != r249.build():
        raise RuntimeError("R250 preregistration identity changed")
    if OUTPUT.exists() or MODEL_OUTPUT.exists():
        raise RuntimeError("R250 refuses to overwrite a result or trained candidate")
    import torch
    from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("R250 requires CUDA BF16 support")
    torch.manual_seed(r248.SEED)
    torch.cuda.manual_seed_all(r248.SEED)
    device = torch.device("cuda")
    names = r248.family_names()
    labels = [*names, r248.ABSTAIN]
    evaluation_inside, evaluation_outside, fresh_outside = r248.development_rows()
    training = training_rows(names, evaluation_inside, evaluation_outside, fresh_outside)
    counts = Counter(label for _, label in training)
    if set(counts) != set(range(len(labels))):
        raise RuntimeError("R250 training classes are incomplete")
    class_weights = torch.tensor([len(training) / (len(labels) * counts[label]) for label in range(len(labels))], dtype=torch.float32, device=device)
    root = r249.r247.r245.r238.r237.ROOT
    tokenizer = AutoTokenizer.from_pretrained(str(root), local_files_only=True)
    config = AutoConfig.from_pretrained(str(root), local_files_only=True, num_labels=len(labels), id2label={number: label for number, label in enumerate(labels)}, label2id={label: number for number, label in enumerate(labels)})
    model = AutoModelForSequenceClassification.from_pretrained(str(root), config=config, ignore_mismatched_sizes=True, local_files_only=True).to(device)
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    classifier = getattr(model, "classifier", None)
    if classifier is None:
        raise RuntimeError("R250 model lacks sequence classification head")
    classifier.float()
    for parameter in classifier.parameters():
        parameter.requires_grad_(True)
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=r248.LEARNING_RATE)
    loss_sum = 0.0
    started = time.monotonic()
    model.train()
    for batch in r248._batches(training):
        encoded = tokenizer([query for query, _ in batch], padding=True, truncation=True, max_length=r248.MAX_LENGTH, return_tensors="pt").to(device)
        targets = torch.tensor([label for _, label in batch], dtype=torch.long, device=device)
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            logits = model(**encoded).logits.float()
            loss = torch.nn.functional.cross_entropy(logits, targets, weight=class_weights)
        if not torch.isfinite(loss):
            raise RuntimeError("R250 non-finite training loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(trainable, 1.0)
        optimizer.step()
        loss_sum += float(loss.item())
    model.eval()
    probabilities: list[np.ndarray] = []
    queries = [row["text"] for row in [*evaluation_inside, *evaluation_outside]]
    with torch.inference_mode():
        for start in range(0, len(queries), r248.BATCH_SIZE):
            encoded = tokenizer(queries[start : start + r248.BATCH_SIZE], padding=True, truncation=True, max_length=r248.MAX_LENGTH, return_tensors="pt").to(device)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                probabilities.append(torch.softmax(model(**encoded).logits.float(), dim=1).cpu().numpy())
    matrix = np.concatenate(probabilities, axis=0).astype(np.float64, copy=False)
    if matrix.shape != (len(queries), len(labels)) or not np.isfinite(matrix).all() or not math.isfinite(loss_sum):
        raise RuntimeError("R250 non-finite or malformed evaluation scores")
    known_maximums = matrix[:, : len(names)].max(axis=1)
    abstain_probabilities = matrix[:, len(names)]
    margins = known_maximums - abstain_probabilities
    threshold = float(np.nextafter(margins[: r248.INSIDE_COUNT].min(), -np.inf))
    accepted = margins >= threshold
    predicted = matrix[:, : len(names)].argmax(axis=1)
    expected = np.asarray([names.index(row["families"][0]) for row in evaluation_inside], dtype=np.int64)
    inside_lost = int((~accepted[: r248.INSIDE_COUNT]).sum())
    inside_mismatches = int((predicted[: r248.INSIDE_COUNT] != expected).sum())
    outside_zero = int((~accepted[r248.INSIDE_COUNT :]).sum())
    MODEL_OUTPUT.mkdir(parents=True)
    model.save_pretrained(str(MODEL_OUTPUT), safe_serialization=True)
    tokenizer.save_pretrained(str(MODEL_OUTPUT))
    candidate_merkle = r248._merkle(MODEL_OUTPUT)
    peak_mib = float(torch.cuda.max_memory_allocated(device) / (1024 * 1024))
    del model
    gc.collect()
    torch.cuda.empty_cache()
    passed = inside_lost == 0 and inside_mismatches == 0 and outside_zero == r248.OUTSIDE_COUNT
    return {
        "schema": "baxy.direct-abstain-classifier.r250-result.v1",
        "authority": "isolated_cuda_development_probe_not_runtime_or_r228_measurement",
        "verdict": "candidate_not_promoted_requires_fresh_oos" if passed else "rejected_development_family_or_oos_separation",
        "candidate": {"base": r249.r247.r245.r238.r237.MODEL + "@" + r249.r247.r245.r238.r237.REVISION, "trained_candidate": str(MODEL_OUTPUT), "trained_candidate_merkle_sha256": candidate_merkle, "device": "cuda_bf16", "classifier_labels": labels, "trainable_parameters": sum(parameter.numel() for parameter in trainable), "threshold": threshold, "threshold_rule": "nextafter_below_minimum_inside_known_probability_minus_explicit_abstain_probability"},
        "training": {"rows": len(training), "class_counts": {labels[number]: counts[number] for number in range(len(labels))}, "epochs": 1, "batch_size": r248.BATCH_SIZE, "max_length": r248.MAX_LENGTH, "learning_rate": r248.LEARNING_RATE, "inverse_frequency_class_weighted_loss": True, "mean_loss": loss_sum / len(r248._batches(training)), "peak_allocated_mib": peak_mib},
        "development_population": {"inside_rows": r248.INSIDE_COUNT, "outside_rows": r248.OUTSIDE_COUNT, "fresh_training_oos_rows": counts[len(names)], "texts_retained": False, "source_ids_retained": False},
        "observed": {"inside_rows_lost": inside_lost, "inside_family_mismatches": inside_mismatches, "inside_family_exact_rate": (r248.INSIDE_COUNT - inside_mismatches) / r248.INSIDE_COUNT, "outside_zero_candidates": outside_zero, "outside_zero_candidate_rate": outside_zero / r248.OUTSIDE_COUNT, "inside_margin_quantiles": r248._quantiles(margins[: r248.INSIDE_COUNT]), "outside_margin_quantiles": r248._quantiles(margins[r248.INSIDE_COUNT :]), "inside_abstain_probability_quantiles": r248._quantiles(abstain_probabilities[: r248.INSIDE_COUNT]), "outside_abstain_probability_quantiles": r248._quantiles(abstain_probabilities[r248.INSIDE_COUNT :]), "elapsed_seconds": time.monotonic() - started},
        "constraints": {"r228_opened": False, "public_holdout_opened": False, "registered_runtime_modified": False, "providers_enabled": False, "effects_executed": 0, "opened_v9": False, "voice_stt_wake_exercised": False},
        "next_requirement": "Do not tune this threshold or open R228. Only a passing candidate may receive a separately sealed fresh OOS runner and visible-text audit.",
        "identities": {"preregistration_sha256": sha256(r249.OUTPUT), "runtime_corpus_sha256": sha256(r248.RUNTIME), "catalog_sha256": sha256(r248.CATALOG), "r207_sha256": sha256(r248.R207), "program_sha256": sha256(Path(__file__))},
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite result: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(run(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
