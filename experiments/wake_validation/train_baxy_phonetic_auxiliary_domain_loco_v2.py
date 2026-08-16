"""Train BAXY phonetic verifier with balanced synthetic hard negatives.

The opened physical outer fold remains untouched.  Synthetic positives and
confusables are auxiliary fit data only; threshold calibration uses disjoint
physical negatives from the two non-held corpora.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import random
import time
from typing import Any

import numpy as np


SCHEMA = "baxy.phonetic-auxiliary-domain-loco-training.v2"
BINDING_SCHEMA = "baxy.phonetic-auxiliary-domain-loco-binding.v2"


def load_component(path: Path, name: str) -> Any:
    if not path.is_file():
        raise RuntimeError("phonetic_auxiliary_component_invalid")
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError("phonetic_auxiliary_component_invalid")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def balanced_domain_epoch_indexes(
    records: list[dict[str, Any]],
    indexes: list[int],
    rng: np.random.Generator,
    target_per_cell: int,
) -> list[int]:
    if target_per_cell < 1:
        raise ValueError("phonetic_auxiliary_target_per_cell_invalid")
    selected = []
    domains = sorted({str(records[index]["trainingDomain"]) for index in indexes})
    for domain in domains:
        for label in ("positive", "negative"):
            cell = np.asarray(
                [
                    index
                    for index in indexes
                    if records[index]["trainingDomain"] == domain
                    and records[index]["label"] == label
                ]
            )
            if not len(cell):
                raise ValueError("phonetic_auxiliary_domain_label_cell_empty")
            selected.extend(
                rng.choice(
                    cell,
                    size=target_per_cell,
                    replace=len(cell) < target_per_cell,
                ).tolist()
            )
    rng.shuffle(selected)
    return [int(index) for index in selected]


def make_multi_store_batch(
    torch: Any,
    stores: dict[str, np.ndarray],
    records: list[dict[str, Any]],
    indexes: list[int],
) -> tuple[Any, Any, Any]:
    lengths = [
        int(records[index]["featureEnd"] - records[index]["featureStart"])
        for index in indexes
    ]
    if not lengths or min(lengths) < 1:
        raise ValueError("phonetic_auxiliary_batch_lengths_invalid")
    maximum = max(lengths)
    hidden_sizes = {int(store.shape[1]) for store in stores.values()}
    if len(hidden_sizes) != 1:
        raise ValueError("phonetic_auxiliary_hidden_size_mismatch")
    hidden_size = next(iter(hidden_sizes))
    values = np.zeros((len(indexes), maximum, hidden_size), dtype=np.float32)
    mask = np.zeros((len(indexes), maximum), dtype=np.bool_)
    for local, (index, length) in enumerate(zip(indexes, lengths, strict=True)):
        record = records[index]
        start = int(record["featureStart"])
        end = int(record["featureEnd"])
        values[local, :length] = stores[str(record["store"])][start:end]
        mask[local, :length] = True
    return (
        torch.from_numpy(values).cuda(),
        torch.from_numpy(mask).cuda(),
        torch.zeros((len(indexes), 1), dtype=torch.float32, device="cuda"),
    )


def load_physical_bundle(binding: dict[str, Any], base: Any) -> tuple[Any, ...]:
    root = Path(str(binding.get("physicalFeatureRoot"))).resolve(strict=True)
    manifest_path = root / "features.manifest.v1.json"
    if binding.get("physicalFeatureManifestSha256") != base.sha256(manifest_path):
        raise ValueError("phonetic_auxiliary_physical_manifest_hash_mismatch")
    manifest = base.read_object(manifest_path)
    if manifest.get("schema") != "baxy.opened-physical-wav2vec2-features.v1":
        raise ValueError("phonetic_auxiliary_physical_manifest_schema_invalid")
    arrays = manifest.get("arrays")
    if not isinstance(arrays, dict):
        raise ValueError("phonetic_auxiliary_physical_arrays_invalid")

    def load_array(name: str, mmap_mode: str | None) -> np.ndarray:
        descriptor = arrays.get(name)
        if not isinstance(descriptor, dict):
            raise ValueError("phonetic_auxiliary_physical_array_invalid")
        path = root / str(descriptor.get("filename"))
        if descriptor.get("sha256") != base.sha256(path):
            raise ValueError("phonetic_auxiliary_physical_array_hash_mismatch")
        return np.load(path, mmap_mode=mmap_mode)

    features = load_array("features", "r")
    offsets = load_array("offsets", None)
    source_records = manifest.get("records")
    if not isinstance(source_records, list) or len(offsets) != len(source_records) + 1:
        raise ValueError("phonetic_auxiliary_physical_records_invalid")
    records = [
        {
            "corpus": str(record["corpus"]),
            "trainingDomain": str(record["corpus"]),
            "label": str(record["label"]),
            "audioSha256": str(record["audioSha256"]),
            "store": "physical",
            "featureStart": int(record["featureStart"]),
            "featureEnd": int(record["featureEnd"]),
        }
        for record in source_records
    ]
    return root, manifest_path, manifest, features, records


def load_auxiliary_bundle(binding: dict[str, Any], base: Any) -> tuple[Any, ...]:
    root = Path(str(binding.get("auxiliaryFeatureRoot"))).resolve(strict=True)
    manifest_path = root / "features.manifest.v1.json"
    if binding.get("auxiliaryFeatureManifestSha256") != base.sha256(manifest_path):
        raise ValueError("phonetic_auxiliary_manifest_hash_mismatch")
    manifest = base.read_object(manifest_path)
    if manifest.get("schema") != "baxy.wav2vec2-hidden-wake-training-features.v1":
        raise ValueError("phonetic_auxiliary_manifest_schema_invalid")
    files = manifest.get("files")
    source_records = manifest.get("records")
    if not isinstance(files, dict) or not isinstance(source_records, list):
        raise ValueError("phonetic_auxiliary_files_invalid")
    feature_path = root / str(files.get("features"))
    offset_path = root / str(files.get("offsets"))
    if files.get("features_sha256") != base.sha256(feature_path) or files.get(
        "offsets_sha256"
    ) != base.sha256(offset_path):
        raise ValueError("phonetic_auxiliary_array_hash_mismatch")
    features = np.load(feature_path, mmap_mode="r")
    offsets = np.load(offset_path)
    if len(offsets) != len(source_records) + 1:
        raise ValueError("phonetic_auxiliary_offsets_invalid")
    records = []
    for index, record in enumerate(source_records):
        corpus = str(record.get("corpus"))
        if corpus not in {"synthetic_positive", "synthetic_negative"}:
            continue
        label = str(record.get("label"))
        audio_hash = str(record.get("audio_sha256"))
        if label not in {"positive", "negative"} or len(audio_hash) != 64:
            raise ValueError("phonetic_auxiliary_record_invalid")
        records.append(
            {
                "corpus": "synthetic",
                "trainingDomain": "synthetic",
                "label": label,
                "audioSha256": audio_hash,
                "store": "auxiliary",
                "featureStart": int(offsets[index]),
                "featureEnd": int(offsets[index + 1]),
            }
        )
    counts = {
        "positive": sum(record["label"] == "positive" for record in records),
        "negative": sum(record["label"] == "negative" for record in records),
    }
    if counts != {"positive": 2695, "negative": 1975}:
        raise ValueError("phonetic_auxiliary_counts_invalid")
    return root, manifest_path, manifest, features, records


def train_run(
    *,
    torch: Any,
    base: Any,
    stores: dict[str, np.ndarray],
    records: list[dict[str, Any]],
    fit_indexes: list[int],
    calibration_indexes: list[int],
    held_indexes: list[int],
    baseline: dict[str, bool],
    seed: int,
    epochs: int,
    batch_size: int,
    target_per_cell: int,
    learning_rate: float,
    checkpoint_path: Path,
) -> dict[str, Any]:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    domains = sorted({str(records[index]["trainingDomain"]) for index in fit_indexes})
    domain_ids = {domain: index for index, domain in enumerate(domains)}
    model = base.make_model(
        torch,
        hidden_size=int(stores["physical"].shape[1]),
        prosody_size=1,
        use_prosody=False,
        domain_classes=len(domains),
    ).cuda()
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=1e-4
    )
    rng = np.random.default_rng(seed)
    history = []
    started = time.perf_counter()
    for epoch in range(epochs):
        model.train()
        epoch_indexes = balanced_domain_epoch_indexes(
            records, fit_indexes, rng, target_per_cell
        )
        losses = []
        for start in range(0, len(epoch_indexes), batch_size):
            indexes = epoch_indexes[start : start + batch_size]
            values, mask, dummy_prosody = make_multi_store_batch(
                torch, stores, records, indexes
            )
            labels = torch.tensor(
                [
                    1 if records[index]["label"] == "positive" else 0
                    for index in indexes
                ],
                dtype=torch.long,
                device="cuda",
            )
            domain_labels = torch.tensor(
                [
                    domain_ids[str(records[index]["trainingDomain"])]
                    for index in indexes
                ],
                dtype=torch.long,
                device="cuda",
            )
            optimizer.zero_grad(set_to_none=True)
            cosine, domain_logits, _ = model(values, mask, dummy_prosody, 0.2)
            arc_logits = cosine.clone()
            arc_logits[torch.arange(len(labels), device="cuda"), labels] -= 0.2
            classification_loss = torch.nn.functional.cross_entropy(
                arc_logits * 20.0, labels
            )
            domain_loss = torch.nn.functional.cross_entropy(
                domain_logits, domain_labels
            )
            loss = classification_loss + 0.1 * domain_loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        history.append({"epoch": epoch + 1, "meanLoss": float(np.mean(losses))})

    def scores(indexes: list[int]) -> np.ndarray:
        model.eval()
        output = []
        with torch.inference_mode():
            for start in range(0, len(indexes), batch_size):
                batch = indexes[start : start + batch_size]
                values, mask, dummy_prosody = make_multi_store_batch(
                    torch, stores, records, batch
                )
                cosine, _, _ = model(values, mask, dummy_prosody, 0.0)
                output.extend((cosine[:, 1] - cosine[:, 0]).cpu().tolist())
        return np.asarray(output, dtype=np.float64)

    calibration_scores = scores(calibration_indexes)
    calibration_labels = np.asarray(
        [
            1 if records[index]["label"] == "positive" else 0
            for index in calibration_indexes
        ]
    )
    threshold = base.threshold_above_negative_scores(
        calibration_scores, calibration_labels
    )
    held_scores = scores(held_indexes)
    torch.save({"state_dict": model.state_dict()}, checkpoint_path)
    return {
        "seed": seed,
        "fitFiles": len(fit_indexes),
        "calibrationFiles": len(calibration_indexes),
        "heldFiles": len(held_indexes),
        "threshold": threshold,
        "history": history,
        "calibration": base.summarize(
            records,
            calibration_indexes,
            calibration_scores,
            threshold,
            baseline,
        ),
        "held": base.summarize(records, held_indexes, held_scores, threshold, baseline),
        "checkpoint": {
            "filename": checkpoint_path.name,
            "sha256": base.sha256(checkpoint_path),
        },
        "runtimeSeconds": time.perf_counter() - started,
    }


def train(binding_path: Path, output_root: Path) -> dict[str, Any]:
    binding_path = binding_path.resolve(strict=True)
    output_root = output_root.resolve()
    partial_root = output_root.with_name(output_root.name + ".partial")
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    if not isinstance(binding, dict) or binding.get("schema") != BINDING_SCHEMA:
        raise ValueError("phonetic_auxiliary_binding_invalid")
    base_path = Path(str(binding.get("baseProgram"))).resolve(strict=True)
    base = load_component(base_path, "_baxy_phonetic_prosody_base_v1")
    base.forbid_v17([binding_path, output_root, partial_root, base_path])
    if output_root.exists() or partial_root.exists():
        raise ValueError("phonetic_auxiliary_output_exists")
    program_path = Path(__file__).resolve()
    if (
        binding.get("programSha256") != base.sha256(program_path)
        or binding.get("baseProgramSha256") != base.sha256(base_path)
        or Path(str(binding.get("plannedOutputRoot"))).resolve() != output_root
    ):
        raise ValueError("phonetic_auxiliary_binding_hash_mismatch")

    (
        _,
        physical_manifest_path,
        _,
        physical_features,
        physical_records,
    ) = load_physical_bundle(binding, base)
    (
        _,
        auxiliary_manifest_path,
        _,
        auxiliary_features,
        auxiliary_records,
    ) = load_auxiliary_bundle(binding, base)
    records = physical_records + auxiliary_records
    stores = {"physical": physical_features, "auxiliary": auxiliary_features}
    baseline = base.load_baseline_decisions(binding)
    physical_hashes = {record["audioSha256"] for record in physical_records}
    if set(baseline) != physical_hashes:
        raise ValueError("phonetic_auxiliary_baseline_coverage_invalid")

    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("phonetic_auxiliary_cuda_unavailable")
    seeds = binding.get("seeds")
    if not isinstance(seeds, list) or not seeds:
        raise ValueError("phonetic_auxiliary_schedule_invalid")
    epochs = int(binding.get("epochs"))
    batch_size = int(binding.get("batchSize"))
    target_per_cell = int(binding.get("targetPerDomainLabelCell"))
    learning_rate = float(binding.get("learningRate"))
    if epochs < 1 or batch_size < 2 or target_per_cell < 1 or learning_rate <= 0:
        raise ValueError("phonetic_auxiliary_schedule_invalid")

    partial_root.mkdir(parents=True)
    auxiliary_indexes = list(range(len(physical_records), len(records)))
    runs = []
    for held_corpus in sorted({record["corpus"] for record in physical_records}):
        fit_physical, calibration, held = base.deterministic_split(
            physical_records, held_corpus
        )
        fit = fit_physical + auxiliary_indexes
        for raw_seed in seeds:
            seed = int(raw_seed)
            checkpoint_path = partial_root / f"{held_corpus}_seed{seed}.pt"
            run = train_run(
                torch=torch,
                base=base,
                stores=stores,
                records=records,
                fit_indexes=fit,
                calibration_indexes=calibration,
                held_indexes=held,
                baseline=baseline,
                seed=seed,
                epochs=epochs,
                batch_size=batch_size,
                target_per_cell=target_per_cell,
                learning_rate=learning_rate,
                checkpoint_path=checkpoint_path,
            )
            run["heldCorpus"] = held_corpus
            runs.append(run)
            metrics = run["held"]
            print(
                f"BAXY_PHONETIC_AUX|{held_corpus}|seed={seed}|"
                f"model={metrics['modelPositiveAccepted']}/"
                f"{metrics['positiveFiles']}|false="
                f"{metrics['modelNegativeFalseActivations']}/"
                f"{metrics['negativeFiles']}|combined="
                f"{metrics['combinedPositiveAccepted']}/"
                f"{metrics['baselinePositiveAccepted']}|combined_false="
                f"{metrics['combinedNegativeFalseActivations']}",
                flush=True,
            )

    preserves = all(
        run["held"]["combinedPositiveAccepted"]
        == run["held"]["baselinePositiveAccepted"]
        for run in runs
    )
    zero_false = all(
        run["held"]["combinedNegativeFalseActivations"] == 0 for run in runs
    )
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_development_physical_loco_with_synthetic_auxiliary_fit",
        "bindingSha256": base.sha256(binding_path),
        "programSha256": base.sha256(program_path),
        "baseProgramSha256": base.sha256(base_path),
        "physicalFeatureManifestSha256": base.sha256(physical_manifest_path),
        "auxiliaryFeatureManifestSha256": base.sha256(auxiliary_manifest_path),
        "counts": {
            "physical": len(physical_records),
            "auxiliarySynthetic": len(auxiliary_records),
            "auxiliaryPositive": sum(
                record["label"] == "positive" for record in auxiliary_records
            ),
            "auxiliaryNegative": sum(
                record["label"] == "negative" for record in auxiliary_records
            ),
        },
        "contract": {
            "syntheticUsedForFitOnly": True,
            "physicalFitCalibrationHeldDisjoint": True,
            "thresholdSelection": "nextafter_maximum_physical_calibration_negative_score",
            "outerHeldCorpusUsedForTraining": False,
            "outerHeldCorpusUsedForThreshold": False,
            "physicalV17Read": False,
            "freshPhysicalHoldoutRequiredAfterPass": True,
            "runtimeModificationAllowed": False,
        },
        "architecture": {
            "teacherLayer": 2,
            "temporal": "two_depthwise_separable_5_frame_blocks",
            "pooling": "masked_mean_std_and_learned_attention",
            "embeddingSize": 64,
            "objective": "three_subcenter_arcface_plus_domain_adversarial",
            "trainingDomains": ["synthetic", "two_nonheld_physical_corpora"],
        },
        "schedule": {
            "seeds": [int(seed) for seed in seeds],
            "epochs": epochs,
            "batchSize": batch_size,
            "targetPerDomainLabelCell": target_per_cell,
            "learningRate": learning_rate,
        },
        "runs": runs,
        "allSeedsAndFoldsPreserveBaselinePositiveCoverage": preserves,
        "allSeedsAndFoldsHaveZeroCombinedFalseActivations": zero_false,
        "developmentGatePassed": bool(preserves and zero_false),
        "candidateFrozen": False,
        "productOperatingPoint": False,
        "freshHoldoutClaimSupported": False,
        "promotionEligible": False,
        "runtime": {
            "device": "cuda",
            "torch": importlib.metadata.version("torch"),
            "numpy": importlib.metadata.version("numpy"),
        },
        "filenamesRetained": False,
        "transcriptTextRetained": False,
        "effectsExecuted": 0,
    }
    report_path = partial_root / "training.report.v2.json"
    report_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    partial_root.replace(output_root)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    arguments = parser.parse_args()
    result = train(arguments.binding, arguments.output_root)
    print(
        f"BAXY_PHONETIC_AUX|complete|passed="
        f"{str(result['developmentGatePassed']).lower()}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
