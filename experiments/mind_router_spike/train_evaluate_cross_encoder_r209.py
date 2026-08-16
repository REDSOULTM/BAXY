"""Train R208's compatibility cross-encoder and score the frozen R186 rows."""
from __future__ import annotations

import hashlib
import json
import random
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PRE = REPO / "artifacts/development/cross_encoder_r208_preregistration.json"
PAIRS = REPO / "artifacts/development/r207_cross_encoder_pairs.jsonl"
CATALOG = REPO / "artifacts/development/catalog_vocabulary_snapshot.json"
OUT = REPO / "artifacts/development/cross_encoder_r209_attested.json"
NO_ACTION = "__no_action__"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines() if line]


def percentile95(values: list[float]) -> float:
    ordered = sorted(values)
    position = 0.95 * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def run() -> dict[str, object]:
    import numpy as np
    import torch
    from torch.utils.data import DataLoader, Dataset
    from transformers import Adafactor, AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding

    preregistration = json.loads(PRE.read_text(encoding="utf8"))
    contract = preregistration["candidate"]
    training = contract["training"]
    if sha(PAIRS) != preregistration["identities"]["pairs_sha256"] or sha(CATALOG) != preregistration["identities"]["catalog_sha256"]:
        raise RuntimeError("r209_frozen_input_contract_failed")
    if not torch.cuda.is_available():
        raise RuntimeError("r209_requires_cuda")
    pair_rows = rows(PAIRS)
    catalog = {row["name"]: row["description"] for row in json.loads(CATALOG.read_text(encoding="utf8"))["capabilities"]}
    documents = catalog | {NO_ACTION: "No BAXY catalog operation applies; abstain without proposing an operation."}
    operations = sorted(documents)
    source = Path(contract["source_checkpoint"])
    random.seed(training["seed"])
    np.random.seed(training["seed"])
    torch.manual_seed(training["seed"])
    torch.cuda.manual_seed_all(training["seed"])
    tokenizer = AutoTokenizer.from_pretrained(source, local_files_only=True)
    encoded = tokenizer([row["query"] for row in pair_rows], [row["operation_document"] for row in pair_rows], truncation=True, max_length=training["max_length"], padding=False)

    class PairDataset(Dataset):
        def __len__(self) -> int:
            return len(pair_rows)

        def __getitem__(self, index: int) -> dict[str, object]:
            target = int(pair_rows[index]["target"])
            label = compatible if target else incompatible
            return {key: value[index] for key, value in encoded.items()} | {"labels": label}

    model = AutoModelForSequenceClassification.from_pretrained(source, local_files_only=True).cuda()
    compatible = model.config.label2id[contract["decision"]["compatible_label"]]
    incompatible = 1 - compatible
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    loader = DataLoader(PairDataset(), batch_size=training["batch_size"], shuffle=True, generator=torch.Generator().manual_seed(training["seed"]), collate_fn=DataCollatorWithPadding(tokenizer=tokenizer, pad_to_multiple_of=8, return_tensors="pt"), pin_memory=True)
    weights = torch.ones(2, device="cuda")
    weights[compatible] = training["positive_class_weight"]
    optimizer = Adafactor(model.parameters(), lr=training["learning_rate"], scale_parameter=False, relative_step=False, warmup_init=False)
    scaler = torch.amp.GradScaler("cuda")
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    losses: list[float] = []
    for epoch in range(training["epochs"]):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        epoch_losses: list[float] = []
        for step, batch in enumerate(loader, 1):
            labels = batch.pop("labels").cuda()
            inputs = {key: value.cuda() for key, value in batch.items()}
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                loss = torch.nn.functional.cross_entropy(model(**inputs).logits, labels, weight=weights, label_smoothing=0.02) / training["gradient_accumulation"]
            scaler.scale(loss).backward()
            epoch_losses.append(float(loss.detach()) * training["gradient_accumulation"])
            if step % training["gradient_accumulation"] == 0 or step == len(loader):
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
        losses.append(float(np.mean(epoch_losses)))
        print(json.dumps({"epoch": epoch + 1, "loss": losses[-1]}), flush=True)
    model.eval()
    measurements: list[dict[str, object]] = []
    threshold = contract["decision"]["candidate_probability_threshold"]
    with torch.inference_mode():
        for evaluation in preregistration["evaluation"]["rows"]:
            queries = [evaluation["text"]] * len(operations)
            docs = [f"Operation {operation}: {documents[operation]}" for operation in operations]
            started_row = time.perf_counter()
            probabilities: list[float] = []
            for offset in range(0, len(operations), 32):
                inputs = {key: value.cuda() for key, value in tokenizer(queries[offset:offset + 32], docs[offset:offset + 32], truncation=True, max_length=training["max_length"], padding=True, return_tensors="pt").items()}
                with torch.autocast(device_type="cuda", dtype=torch.float16):
                    logits = model(**inputs).logits.float().cpu()
                probabilities.extend(torch.softmax(logits, dim=1)[:, compatible].tolist())
            scores = dict(zip(operations, probabilities, strict=True))
            candidates = [operation for operation in operations if operation != NO_ACTION and scores[operation] >= threshold]
            measurements.append({**evaluation, "candidate_operations": candidates, "exact": candidates == evaluation["expected_operations"], "seconds": round(time.perf_counter() - started_row, 6), "raw_compatibility_scores": {operation: round(score, 6) for operation, score in scores.items()}})
    known = [row for row in measurements if row["population"] == "r146_model_owned"]
    oos = [row for row in measurements if row["population"] == "oos_control"]
    return {"schema": "baxy.cross-encoder-r209-attested.v1", "identities": {"program_sha256": sha(Path(__file__)), "preregistration_sha256": sha(PRE), "pairs_sha256": sha(PAIRS), "catalog_sha256": sha(CATALOG)}, "training": {"pairs": len(pair_rows), "epoch_mean_losses": losses, "seconds": round(time.perf_counter() - started, 3), "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 1), "peak_reserved_mib": round(torch.cuda.max_memory_reserved() / 2**20, 1), "checkpoint_saved": False}, "rows": measurements, "result": {"raw_exact": sum(row["exact"] for row in known), "model_owned_rows": len(known), "oos_zero_candidates": sum(not row["candidate_operations"] for row in oos), "p95_seconds": round(percentile95([row["seconds"] for row in measurements]), 6)}, "execution": {"runtime_modified": False, "providers_enabled": False, "external_effects_executed": 0, "opened_v9": False, "voice_stt_wake_exercised": False}}


def main() -> None:
    result = run()
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())
    print(json.dumps(result["result"], sort_keys=True))


if __name__ == "__main__":
    main()
