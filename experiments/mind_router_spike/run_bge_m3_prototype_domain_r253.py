"""Run the sealed BGE-M3 exemplar-family and separate domain-boundary probe."""

from __future__ import annotations

import hashlib
import json
import sys
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import attest_clinc_oos_development_r251 as r251
from experiments.mind_router_spike import preregister_bge_m3_prototype_domain_r252 as r252
from experiments.mind_router_spike import run_bge_m3_semantic_abstention_r236 as r236
from experiments.mind_router_spike import run_direct_abstain_classifier_r248 as r248
from experiments.mind_router_spike import run_head_only_reranker_domain_r246 as r246
from experiments.mind_router_spike import run_supervised_reranker_domain_r243 as r243


R207 = REPO / "artifacts/development/r207_cross_encoder_pairs.jsonl"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
OUTPUT = REPO / "artifacts/development/bge_m3_prototype_domain_r253.json"
INSIDE_COUNT = 256
BATCH_SIZE = 32
EPOCHS = 20
LEARNING_RATE = 1e-2
SEED = 252253


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normal(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def families() -> list[str]:
    names = sorted({str(row["name"]).split(".", 1)[0] for row in json.loads(CATALOG.read_text(encoding="utf-8"))["catalogue"]["capabilities"]})
    if len(names) != 31:
        raise RuntimeError("R253 requires the 31-family current catalogue")
    return names


def inside_evaluation() -> list[dict[str, Any]]:
    all_inside, _ = r243._rows()
    r236_inside, r236_outside = r236.sample_rows()
    r243_inside, r243_outside, r243_train = r243._sample_development_rows()
    r246_inside, r246_outside, r246_train = r246.development_rows()
    r250_inside, r250_outside, _ = r248.development_rows()
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
            *r250_inside,
            *r250_outside,
        ]
    }
    available = [row for row in all_inside if row["source_id"] not in reserved]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in available:
        groups[row["families"][0]].append(row)
    chosen = [sorted(groups[name], key=lambda row: _key(row["source_id"]))[0] for name in sorted(groups)]
    remainder = sorted((row for rows in groups.values() for row in rows if row not in chosen), key=lambda row: _key(row["source_id"]))
    result = [*chosen, *remainder[: INSIDE_COUNT - len(chosen)]]
    if len(result) != INSIDE_COUNT or len({row["families"][0] for row in result}) != 31:
        raise RuntimeError("R253 requires a fresh balanced 31-family inside evaluation")
    return result


def training_rows(names: list[str], evaluation: list[dict[str, Any]]) -> tuple[list[tuple[str, int]], list[str]]:
    index = {name: number for number, name in enumerate(names)}
    forbidden = {_normal(row["text"]) for row in evaluation}
    known: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for line in R207.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["target"] != 1:
            continue
        query = str(row["query"])
        item = (_normal(query), index.get(str(row["operation"]).split(".", 1)[0], -1))
        if item[1] < 0:
            continue
        if item[0] in forbidden:
            raise RuntimeError("R253 known training overlaps fresh evaluation")
        if item not in seen:
            seen.add(item)
            known.append((query, item[1]))
    clinc = r251.development_rows()
    outside_train = [row[0] for row in clinc["oos_train"]]
    if set(label for _, label in known) != set(range(len(names))) or len(outside_train) != 250:
        raise RuntimeError("R253 requires R207 coverage and intact CLINC train")
    return known, outside_train


def _embed(model: Any, tokenizer: Any, texts: list[str], device: Any) -> np.ndarray:
    import torch

    result: list[np.ndarray] = []
    model.eval()
    with torch.inference_mode():
        for start in range(0, len(texts), BATCH_SIZE):
            encoded = tokenizer(texts[start : start + BATCH_SIZE], padding=True, truncation=True, max_length=128, return_tensors="pt").to(device)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                hidden = model(**encoded).last_hidden_state.float()
            mask = encoded["attention_mask"].unsqueeze(-1)
            vector = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1)
            result.append(torch.nn.functional.normalize(vector, p=2, dim=1).cpu().numpy())
    return np.concatenate(result, axis=0).astype(np.float32, copy=False)


def _quantiles(values: np.ndarray) -> dict[str, float]:
    return {name: float(np.quantile(values, quantile)) for name, quantile in (("min", 0.0), ("p50", 0.5), ("p95", 0.95), ("max", 1.0))}


def run() -> dict[str, Any]:
    preregistration = json.loads(r252.OUTPUT.read_text(encoding="utf-8"))
    if preregistration != r252.build() or OUTPUT.exists():
        raise RuntimeError("R253 preregistration changed or result already exists")
    import torch
    from transformers import AutoModel, AutoTokenizer

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("R253 requires CUDA BF16")
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    device = torch.device("cuda")
    names = families()
    evaluation = inside_evaluation()
    known_train, outside_train = training_rows(names, evaluation)
    clinc = r251.development_rows()
    outside_eval = [row[0] for row in clinc["oos_val"]]
    root = r252.r232.r231.CANDIDATE_ROOT
    tokenizer = AutoTokenizer.from_pretrained(str(root), local_files_only=True)
    model = AutoModel.from_pretrained(str(root), local_files_only=True).to(device)
    started = time.monotonic()
    known_embeddings = _embed(model, tokenizer, [row[0] for row in known_train], device)
    outside_train_embeddings = _embed(model, tokenizer, outside_train, device)
    inside_embeddings = _embed(model, tokenizer, [row["text"] for row in evaluation], device)
    outside_embeddings = _embed(model, tokenizer, outside_eval, device)
    if not all(np.isfinite(value).all() for value in (known_embeddings, outside_train_embeddings, inside_embeddings, outside_embeddings)):
        raise RuntimeError("R253 produced non-finite embeddings")
    features = torch.tensor(np.concatenate((known_embeddings, outside_train_embeddings)), device=device)
    labels = torch.cat((torch.ones(len(known_embeddings), device=device), torch.zeros(len(outside_train_embeddings), device=device)))
    head = torch.nn.Linear(features.shape[1], 1, device=device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=LEARNING_RATE)
    positive_weight = torch.tensor([len(outside_train_embeddings) / len(known_embeddings)], device=device)
    for _ in range(EPOCHS):
        logits = head(features).reshape(-1)
        loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels, pos_weight=positive_weight)
        if not torch.isfinite(loss):
            raise RuntimeError("R253 non-finite domain-boundary loss")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
    with torch.inference_mode():
        probabilities = torch.sigmoid(head(torch.tensor(np.concatenate((inside_embeddings, outside_embeddings)), device=device)).reshape(-1)).cpu().numpy()
    centroids = np.asarray([known_embeddings[[label == number for _, label in known_train]].mean(axis=0) for number in range(len(names))], dtype=np.float32)
    centroids /= np.linalg.norm(centroids, axis=1, keepdims=True)
    family_scores = inside_embeddings @ centroids.T
    predicted = family_scores.argmax(axis=1)
    expected = np.asarray([names.index(row["families"][0]) for row in evaluation])
    threshold = float(np.nextafter(probabilities[:INSIDE_COUNT].min(), -np.inf))
    accepted = probabilities >= threshold
    inside_lost = int((~accepted[:INSIDE_COUNT]).sum())
    inside_mismatches = int((predicted != expected).sum())
    outside_zero = int((~accepted[INSIDE_COUNT:]).sum())
    peak_mib = float(torch.cuda.max_memory_allocated(device) / (1024 * 1024))
    passed = inside_lost == 0 and inside_mismatches == 0 and outside_zero == len(outside_eval)
    return {"schema": "baxy.bge-m3-prototype-domain.r253-result.v1", "authority": "isolated_cuda_development_probe_not_runtime_or_r228_measurement", "verdict": "candidate_not_promoted_requires_fresh_oos" if passed else "rejected_development_family_or_oos_separation", "candidate": {"base": "BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181", "device": "cuda_bf16", "family_centroids": len(names), "domain_boundary": "balanced_logistic_head_over_frozen_BGE-M3_query_embedding", "threshold": threshold}, "training": {"known_rows": len(known_train), "outside_rows": len(outside_train), "epochs": EPOCHS, "peak_allocated_mib": peak_mib}, "development_population": {"inside_rows": INSIDE_COUNT, "outside_rows": len(outside_eval), "texts_retained": False, "source_ids_retained": False}, "observed": {"inside_rows_lost": inside_lost, "inside_family_mismatches": inside_mismatches, "inside_family_exact_rate": (INSIDE_COUNT - inside_mismatches) / INSIDE_COUNT, "outside_zero_candidates": outside_zero, "outside_zero_candidate_rate": outside_zero / len(outside_eval), "inside_domain_probability_quantiles": _quantiles(probabilities[:INSIDE_COUNT]), "outside_domain_probability_quantiles": _quantiles(probabilities[INSIDE_COUNT:]), "elapsed_seconds": time.monotonic() - started}, "constraints": {"r228_opened": False, "public_holdout_opened": False, "registered_runtime_modified": False, "providers_enabled": False, "effects_executed": 0, "opened_v9": False, "voice_stt_wake_exercised": False}, "next_requirement": "Do not tune threshold or rerun. Only a passing candidate may receive separately sealed full-path and visible-text measurement.", "identities": {"preregistration_sha256": sha256(r252.OUTPUT), "r207_sha256": sha256(R207), "catalog_sha256": sha256(CATALOG), "program_sha256": sha256(Path(__file__))}}


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite result: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(run(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
