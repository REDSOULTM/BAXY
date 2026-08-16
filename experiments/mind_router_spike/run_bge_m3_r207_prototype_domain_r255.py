"""Run the sealed query-disjoint BGE-M3 prototype/domain CUDA probe once."""

from __future__ import annotations

import gc
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
from experiments.mind_router_spike import preregister_bge_m3_r207_prototype_domain_r254 as r254


R207 = REPO / "artifacts/development/r207_cross_encoder_pairs.jsonl"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
OUTPUT = REPO / "artifacts/development/bge_m3_r207_prototype_domain_r255.json"
BATCH_SIZE = 16
EPOCHS = 20
LEARNING_RATE = 1e-2
SEED = 254255
INSIDE_COUNT = 256


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normal(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def family_names() -> list[str]:
    catalogue = json.loads(CATALOG.read_text(encoding="utf-8"))["catalogue"]["capabilities"]
    names = sorted({str(row["name"]).split(".", 1)[0] for row in catalogue})
    if len(names) != 31:
        raise RuntimeError("R255 requires the 31-family typed catalogue")
    return names


def split_rows(names: list[str]) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    indices = {name: index for index, name in enumerate(names)}
    by_pair: dict[tuple[str, int], str] = {}
    for line in R207.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["target"] != 1:
            continue
        family = str(row["operation"]).split(".", 1)[0]
        label = indices.get(family)
        query = str(row["query"])
        if label is not None:
            by_pair.setdefault((normal(query), label), query)
    groups: dict[int, list[tuple[tuple[str, int], str]]] = defaultdict(list)
    for pair, query in by_pair.items():
        groups[pair[1]].append((pair, query))
    if set(groups) != set(range(len(names))):
        raise RuntimeError("R255 needs at least one R207 positive per typed family")
    selected = [sorted(groups[label], key=lambda item: key(item[0][0] + "\0" + str(label)))[0] for label in range(len(names))]
    selected_pairs = {pair for pair, _ in selected}
    remainder = sorted(
        ((pair, query) for pair, query in by_pair.items() if pair not in selected_pairs),
        key=lambda item: key(item[0][0] + "\0" + str(item[0][1])),
    )
    evaluation = [*selected, *remainder[: INSIDE_COUNT - len(selected)]]
    if len(evaluation) != INSIDE_COUNT or len({pair[1] for pair, _ in evaluation}) != len(names):
        raise RuntimeError("R255 needs exactly 256 R207 evaluation pairs over 31 families")
    evaluation_normalized = {pair[0] for pair, _ in evaluation}
    training = [(query, pair[1]) for pair, query in by_pair.items() if pair[0] not in evaluation_normalized]
    if not training or set(label for _, label in training) != set(range(len(names))):
        raise RuntimeError("R255 training lacks a typed family after the strict query split")
    if evaluation_normalized & {normal(query) for query, _ in training}:
        raise RuntimeError("R255 query-disjoint split was violated")
    return sorted(training, key=lambda item: key(normal(item[0]) + "\0" + str(item[1]))), [(query, pair[1]) for pair, query in evaluation]


def embed(model: Any, tokenizer: Any, texts: list[str], device: Any) -> np.ndarray:
    import torch

    chunks: list[np.ndarray] = []
    model.eval()
    with torch.inference_mode():
        for start in range(0, len(texts), BATCH_SIZE):
            encoded = tokenizer(texts[start : start + BATCH_SIZE], padding=True, truncation=True, max_length=128, return_tensors="pt").to(device)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                hidden = model(**encoded).last_hidden_state.float()
            mask = encoded["attention_mask"].unsqueeze(-1)
            vectors = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1)
            chunks.append(torch.nn.functional.normalize(vectors, p=2, dim=1).cpu().numpy())
    return np.concatenate(chunks, axis=0).astype(np.float32, copy=False)


def quantiles(values: np.ndarray) -> dict[str, float]:
    return {name: float(np.quantile(values, point)) for name, point in (("min", 0.0), ("p50", 0.5), ("p95", 0.95), ("max", 1.0))}


def run() -> dict[str, Any]:
    preregistration = json.loads(r254.OUTPUT.read_text(encoding="utf-8"))
    if preregistration != r254.build() or OUTPUT.exists():
        raise RuntimeError("R255 preregistration identity changed or result already exists")
    import torch
    from transformers import AutoModel, AutoTokenizer

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("R255 requires CUDA BF16")
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.cuda.reset_peak_memory_stats()
    device = torch.device("cuda")
    names = family_names()
    known_train, inside = split_rows(names)
    clinc = r251.development_rows()
    outside_train = [row[0] for row in clinc["oos_train"]]
    outside = [row[0] for row in clinc["oos_val"]]
    if len(outside_train) != 250 or len(outside) != 100:
        raise RuntimeError("R255 requires intact CLINC development counts")
    tokenizer = AutoTokenizer.from_pretrained(str(r254.r232.r231.CANDIDATE_ROOT), local_files_only=True)
    model = AutoModel.from_pretrained(str(r254.r232.r231.CANDIDATE_ROOT), local_files_only=True).to(device)
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    started = time.monotonic()
    known_vectors = embed(model, tokenizer, [query for query, _ in known_train], device)
    train_oos_vectors = embed(model, tokenizer, outside_train, device)
    inside_vectors = embed(model, tokenizer, [query for query, _ in inside], device)
    outside_vectors = embed(model, tokenizer, outside, device)
    if not all(np.isfinite(values).all() for values in (known_vectors, train_oos_vectors, inside_vectors, outside_vectors)):
        raise RuntimeError("R255 produced non-finite frozen embeddings")
    features = torch.tensor(np.concatenate((known_vectors, train_oos_vectors)), device=device)
    labels = torch.cat((torch.ones(len(known_vectors), device=device), torch.zeros(len(train_oos_vectors), device=device)))
    head = torch.nn.Linear(features.shape[1], 1, device=device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=LEARNING_RATE)
    positive_weight = torch.tensor([len(train_oos_vectors) / len(known_vectors)], device=device)
    loss_value = 0.0
    for _ in range(EPOCHS):
        logits = head(features).reshape(-1)
        loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels, pos_weight=positive_weight)
        if not torch.isfinite(loss):
            raise RuntimeError("R255 non-finite domain-boundary loss")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        loss_value = float(loss.item())
    all_vectors = np.concatenate((inside_vectors, outside_vectors))
    with torch.inference_mode():
        probabilities = torch.sigmoid(head(torch.tensor(all_vectors, device=device)).reshape(-1)).cpu().numpy()
    centroids = np.asarray([known_vectors[[label == index for _, label in known_train]].mean(axis=0) for index in range(len(names))], dtype=np.float32)
    centroids /= np.linalg.norm(centroids, axis=1, keepdims=True)
    predicted = (inside_vectors @ centroids.T).argmax(axis=1)
    expected = np.asarray([label for _, label in inside])
    threshold = float(np.nextafter(probabilities[:INSIDE_COUNT].min(), -np.inf))
    accepted = probabilities >= threshold
    inside_lost = int((~accepted[:INSIDE_COUNT]).sum())
    inside_mismatches = int((predicted != expected).sum())
    outside_zero = int((~accepted[INSIDE_COUNT:]).sum())
    peak_mib = float(torch.cuda.max_memory_allocated(device) / (1024 * 1024))
    elapsed = time.monotonic() - started
    del head, model
    gc.collect()
    torch.cuda.empty_cache()
    passed = inside_lost == 0 and inside_mismatches == 0 and outside_zero == len(outside)
    return {
        "schema": "baxy.bge-m3-r207-prototype-domain.r255-result.v1",
        "authority": "isolated_cuda_development_probe_not_runtime_or_blind_holdout_measurement",
        "verdict": "candidate_not_promoted_requires_blind_path_measurement" if passed else "rejected_development_family_or_oos_separation",
        "candidate": {"base": "BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181", "device": "cuda_bf16", "family_centroids": len(names), "domain_boundary": "class-balanced_logistic_head_over_frozen_BGE-M3_query_embeddings", "threshold": threshold, "threshold_rule": "nextafter_below_minimum_inside_domain_probability"},
        "training": {"known_rows": len(known_train), "outside_rows": len(outside_train), "epochs": EPOCHS, "learning_rate": LEARNING_RATE, "final_domain_loss": loss_value, "peak_allocated_mib": peak_mib},
        "development_population": {"inside_rows": len(inside), "outside_rows": len(outside), "texts_retained": False, "source_ids_retained": False, "inside_partition": "R207 query-disjoint SHA-256 split", "outside_partition": "CLINC oos_val"},
        "observed": {"inside_rows_lost": inside_lost, "inside_family_mismatches": inside_mismatches, "inside_family_exact_rate": (len(inside) - inside_mismatches) / len(inside), "outside_zero_candidates": outside_zero, "outside_zero_candidate_rate": outside_zero / len(outside), "inside_domain_probability_quantiles": quantiles(probabilities[:INSIDE_COUNT]), "outside_domain_probability_quantiles": quantiles(probabilities[INSIDE_COUNT:]), "elapsed_seconds": elapsed},
        "constraints": {"r228_opened": False, "public_holdout_opened": False, "registered_runtime_modified": False, "providers_enabled": False, "effects_executed": 0, "opened_v9": False, "voice_stt_wake_exercised": False},
        "next_requirement": "Do not tune or rerun R255. A passing result remains development-only and needs a separately sealed blind full-path and visible-text measurement; a failure rejects this architecture.",
        "identities": {"preregistration_sha256": sha256(r254.OUTPUT), "r207_sha256": sha256(R207), "catalog_sha256": sha256(CATALOG), "clinc_source_sha256": r251.SOURCE_SHA256, "program_sha256": sha256(Path(__file__))},
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite result: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(run(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
