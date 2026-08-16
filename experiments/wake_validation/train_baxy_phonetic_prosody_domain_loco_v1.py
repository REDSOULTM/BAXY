"""Train a BAXY-specific phonetic/prosodic discriminator on opened data.

Every outer fold leaves one complete physical corpus untouched.  Fit and
calibration records are disjoint inside the other two corpora, and the score
threshold is selected only from calibration negatives.  This is an opened
development architecture screen, never a product or holdout claim.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import random
import time
from typing import Any

import numpy as np


SCHEMA = "baxy.phonetic-prosody-domain-loco-training.v1"
BINDING_SCHEMA = "baxy.phonetic-prosody-domain-loco-binding.v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("phonetic_prosody_json_object_required")
    return value


def forbid_v17(paths: list[Path]) -> None:
    if any("v17" in str(path).lower() for path in paths):
        raise ValueError("phonetic_prosody_physical_v17_forbidden")


def deterministic_split(
    records: list[dict[str, Any]], held_corpus: str, modulus: int = 5
) -> tuple[list[int], list[int], list[int]]:
    if modulus < 3 or held_corpus not in {str(record["corpus"]) for record in records}:
        raise ValueError("phonetic_prosody_split_contract_invalid")
    held = [
        index for index, record in enumerate(records) if record["corpus"] == held_corpus
    ]
    fit: list[int] = []
    calibration: list[int] = []
    training_corpora = sorted(
        {str(record["corpus"]) for record in records if record["corpus"] != held_corpus}
    )
    for corpus in training_corpora:
        for label in ("positive", "negative"):
            indexes = sorted(
                (
                    index
                    for index, record in enumerate(records)
                    if record["corpus"] == corpus and record["label"] == label
                ),
                key=lambda index: str(records[index]["audioSha256"]),
            )
            if len(indexes) < modulus:
                raise ValueError("phonetic_prosody_split_population_too_small")
            for position, index in enumerate(indexes):
                (calibration if position % modulus == 0 else fit).append(index)
    if set(fit) & set(calibration) or (set(fit) | set(calibration)) & set(held):
        raise ValueError("phonetic_prosody_split_overlap")
    if len(set(fit) | set(calibration) | set(held)) != len(records):
        raise ValueError("phonetic_prosody_split_coverage_invalid")
    return sorted(fit), sorted(calibration), sorted(held)


def threshold_above_negative_scores(scores: np.ndarray, labels: np.ndarray) -> float:
    negatives = np.asarray(scores, dtype=np.float64)[np.asarray(labels) == 0]
    if not len(negatives) or not np.isfinite(negatives).all():
        raise ValueError("phonetic_prosody_calibration_negatives_invalid")
    return float(np.nextafter(float(np.max(negatives)), math.inf))


def load_baseline_decisions(binding: dict[str, Any]) -> dict[str, bool]:
    reports = binding.get("baselineReports")
    if not isinstance(reports, list) or len(reports) != 3:
        raise ValueError("phonetic_prosody_baseline_reports_invalid")
    decisions: dict[str, bool] = {}
    for item in reports:
        if not isinstance(item, dict):
            raise ValueError("phonetic_prosody_baseline_report_invalid")
        path = Path(str(item.get("path"))).resolve(strict=True)
        forbid_v17([path])
        if item.get("sha256") != sha256(path):
            raise ValueError("phonetic_prosody_baseline_hash_mismatch")
        report = read_object(path)
        decision_key = item.get("decisionKey")
        if not isinstance(decision_key, str):
            raise ValueError("phonetic_prosody_baseline_key_invalid")
        for partition in ("positive", "negative"):
            section = report.get(partition)
            records = section.get("records") if isinstance(section, dict) else None
            if not isinstance(records, list):
                raise ValueError("phonetic_prosody_baseline_records_invalid")
            for record in records:
                audio_hash = (
                    record.get("audioSha256") if isinstance(record, dict) else None
                )
                decision = (
                    record.get(decision_key) if isinstance(record, dict) else None
                )
                if (
                    not isinstance(audio_hash, str)
                    or not isinstance(decision, bool)
                    or audio_hash in decisions
                ):
                    raise ValueError("phonetic_prosody_baseline_record_invalid")
                decisions[audio_hash] = decision
    return decisions


def summarize(
    records: list[dict[str, Any]],
    indexes: list[int],
    scores: np.ndarray,
    threshold: float,
    baseline: dict[str, bool],
) -> dict[str, Any]:
    selected_scores = np.asarray(scores, dtype=np.float64)
    if len(selected_scores) != len(indexes):
        raise ValueError("phonetic_prosody_summary_shape_invalid")
    labels = np.asarray(
        [1 if records[index]["label"] == "positive" else 0 for index in indexes]
    )
    accepted = selected_scores >= threshold
    baseline_values = np.asarray(
        [baseline[str(records[index]["audioSha256"])] for index in indexes], dtype=bool
    )
    combined = accepted & baseline_values
    return {
        "files": len(indexes),
        "positiveFiles": int(np.sum(labels == 1)),
        "negativeFiles": int(np.sum(labels == 0)),
        "modelPositiveAccepted": int(np.sum(accepted & (labels == 1))),
        "modelNegativeFalseActivations": int(np.sum(accepted & (labels == 0))),
        "baselinePositiveAccepted": int(np.sum(baseline_values & (labels == 1))),
        "baselineNegativeFalseActivations": int(
            np.sum(baseline_values & (labels == 0))
        ),
        "combinedPositiveAccepted": int(np.sum(combined & (labels == 1))),
        "combinedNegativeFalseActivations": int(np.sum(combined & (labels == 0))),
        "records": [
            {
                "audioSha256": records[index]["audioSha256"],
                "label": records[index]["label"],
                "score": float(score),
                "modelAccepted": bool(model_decision),
                "baselineAccepted": bool(baseline_decision),
                "combinedAccepted": bool(model_decision and baseline_decision),
            }
            for index, score, model_decision, baseline_decision in zip(
                indexes, selected_scores, accepted, baseline_values, strict=True
            )
        ],
    }


def make_model(
    torch: Any,
    *,
    hidden_size: int,
    prosody_size: int,
    use_prosody: bool,
    domain_classes: int,
) -> Any:
    nn = torch.nn

    class GradientReverse(torch.autograd.Function):
        @staticmethod
        def forward(ctx: Any, values: Any, strength: float) -> Any:
            ctx.strength = strength
            return values.view_as(values)

        @staticmethod
        def backward(ctx: Any, gradient: Any) -> tuple[Any, None]:
            return -ctx.strength * gradient, None

    class Discriminator(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.use_prosody = use_prosody
            self.input_norm = nn.LayerNorm(hidden_size)
            self.projection = nn.Linear(hidden_size, 128)
            self.temporal = nn.Sequential(
                nn.Conv1d(128, 128, 5, padding=2, groups=128),
                nn.Conv1d(128, 128, 1),
                nn.GELU(),
                nn.Conv1d(128, 128, 5, padding=2, groups=128),
                nn.Conv1d(128, 128, 1),
                nn.GELU(),
            )
            self.attention = nn.Linear(128, 1)
            self.acoustic_head = nn.Sequential(
                nn.Linear(384, 96), nn.GELU(), nn.LayerNorm(96)
            )
            if use_prosody:
                self.prosody_head = nn.Sequential(
                    nn.Linear(prosody_size, 32), nn.GELU(), nn.LayerNorm(32)
                )
                fusion_size = 128
            else:
                self.prosody_head = None
                fusion_size = 96
            self.embedding = nn.Linear(fusion_size, 64)
            self.centers = nn.Parameter(torch.empty(2, 3, 64))
            nn.init.xavier_uniform_(self.centers)
            self.domain_head = nn.Sequential(
                nn.Linear(64, 32), nn.GELU(), nn.Linear(32, domain_classes)
            )

        def forward(
            self,
            values: Any,
            mask: Any,
            prosody_values: Any,
            domain_strength: float,
        ) -> tuple[Any, Any, Any]:
            hidden = self.projection(self.input_norm(values))
            hidden = hidden + self.temporal(hidden.transpose(1, 2)).transpose(1, 2)
            float_mask = mask.unsqueeze(-1).to(hidden.dtype)
            count = float_mask.sum(dim=1).clamp_min(1.0)
            mean = (hidden * float_mask).sum(dim=1) / count
            variance = ((hidden - mean.unsqueeze(1)) ** 2 * float_mask).sum(
                dim=1
            ) / count
            attention_logits = self.attention(hidden).squeeze(-1)
            attention_logits = attention_logits.masked_fill(~mask, -1e4)
            weights = torch.softmax(attention_logits, dim=1).unsqueeze(-1)
            attended = (hidden * weights).sum(dim=1)
            acoustic = self.acoustic_head(
                torch.cat((mean, torch.sqrt(variance + 1e-6), attended), dim=1)
            )
            if self.use_prosody:
                fused = torch.cat((acoustic, self.prosody_head(prosody_values)), dim=1)
            else:
                fused = acoustic
            embedding = torch.nn.functional.normalize(self.embedding(fused), dim=1)
            centers = torch.nn.functional.normalize(self.centers, dim=2)
            cosine = torch.einsum("bd,ckd->bck", embedding, centers).max(dim=2).values
            reversed_embedding = GradientReverse.apply(embedding, domain_strength)
            return cosine, self.domain_head(reversed_embedding), embedding

    return Discriminator()


def make_batch(
    torch: Any,
    features: np.ndarray,
    offsets: np.ndarray,
    prosody: np.ndarray,
    indexes: list[int],
    prosody_center: np.ndarray,
    prosody_scale: np.ndarray,
) -> tuple[Any, Any, Any]:
    lengths = [int(offsets[index + 1] - offsets[index]) for index in indexes]
    maximum = max(lengths)
    hidden_size = int(features.shape[1])
    values = np.zeros((len(indexes), maximum, hidden_size), dtype=np.float32)
    mask = np.zeros((len(indexes), maximum), dtype=np.bool_)
    for local, (index, length) in enumerate(zip(indexes, lengths, strict=True)):
        values[local, :length] = features[offsets[index] : offsets[index + 1]]
        mask[local, :length] = True
    normalized_prosody = (prosody[indexes] - prosody_center) / prosody_scale
    return (
        torch.from_numpy(values).cuda(),
        torch.from_numpy(mask).cuda(),
        torch.from_numpy(normalized_prosody.astype(np.float32)).cuda(),
    )


def balanced_epoch_indexes(
    records: list[dict[str, Any]], indexes: list[int], rng: np.random.Generator
) -> list[int]:
    positives = np.asarray(
        [index for index in indexes if records[index]["label"] == "positive"]
    )
    negatives = np.asarray(
        [index for index in indexes if records[index]["label"] == "negative"]
    )
    target = max(len(positives), len(negatives))
    selected = np.concatenate(
        (
            rng.choice(positives, size=target, replace=len(positives) < target),
            rng.choice(negatives, size=target, replace=len(negatives) < target),
        )
    )
    rng.shuffle(selected)
    return [int(index) for index in selected]


def train_run(
    *,
    torch: Any,
    features: np.ndarray,
    offsets: np.ndarray,
    prosody: np.ndarray,
    records: list[dict[str, Any]],
    fit_indexes: list[int],
    calibration_indexes: list[int],
    held_indexes: list[int],
    baseline: dict[str, bool],
    use_prosody: bool,
    seed: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    output_path: Path,
) -> dict[str, Any]:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    training_corpora = sorted({str(records[index]["corpus"]) for index in fit_indexes})
    domain_ids = {corpus: index for index, corpus in enumerate(training_corpora)}
    prosody_center = np.mean(prosody[fit_indexes], axis=0)
    prosody_scale = np.std(prosody[fit_indexes], axis=0)
    prosody_scale = np.maximum(prosody_scale, 1e-5)
    model = make_model(
        torch,
        hidden_size=int(features.shape[1]),
        prosody_size=int(prosody.shape[1]),
        use_prosody=use_prosody,
        domain_classes=len(training_corpora),
    ).cuda()
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=1e-4
    )
    rng = np.random.default_rng(seed)
    history = []
    started = time.perf_counter()
    for epoch in range(epochs):
        model.train()
        epoch_indexes = balanced_epoch_indexes(records, fit_indexes, rng)
        losses = []
        for start in range(0, len(epoch_indexes), batch_size):
            indexes = epoch_indexes[start : start + batch_size]
            values, mask, prosody_values = make_batch(
                torch,
                features,
                offsets,
                prosody,
                indexes,
                prosody_center,
                prosody_scale,
            )
            labels = torch.tensor(
                [
                    1 if records[index]["label"] == "positive" else 0
                    for index in indexes
                ],
                dtype=torch.long,
                device="cuda",
            )
            domains = torch.tensor(
                [domain_ids[str(records[index]["corpus"])] for index in indexes],
                dtype=torch.long,
                device="cuda",
            )
            optimizer.zero_grad(set_to_none=True)
            cosine, domain_logits, _ = model(values, mask, prosody_values, 0.2)
            arc_logits = cosine.clone()
            arc_logits[torch.arange(len(labels), device="cuda"), labels] -= 0.2
            classification_loss = torch.nn.functional.cross_entropy(
                arc_logits * 20.0, labels
            )
            domain_loss = torch.nn.functional.cross_entropy(domain_logits, domains)
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
                values, mask, prosody_values = make_batch(
                    torch,
                    features,
                    offsets,
                    prosody,
                    batch,
                    prosody_center,
                    prosody_scale,
                )
                cosine, _, _ = model(values, mask, prosody_values, 0.0)
                output.extend((cosine[:, 1] - cosine[:, 0]).cpu().tolist())
        return np.asarray(output, dtype=np.float64)

    calibration_scores = scores(calibration_indexes)
    calibration_labels = np.asarray(
        [
            1 if records[index]["label"] == "positive" else 0
            for index in calibration_indexes
        ]
    )
    threshold = threshold_above_negative_scores(calibration_scores, calibration_labels)
    held_scores = scores(held_indexes)
    state = {
        "state_dict": model.state_dict(),
        "prosody_center": torch.from_numpy(prosody_center.astype(np.float32)),
        "prosody_scale": torch.from_numpy(prosody_scale.astype(np.float32)),
    }
    torch.save(state, output_path)
    return {
        "seed": seed,
        "useProsody": use_prosody,
        "fitFiles": len(fit_indexes),
        "calibrationFiles": len(calibration_indexes),
        "heldFiles": len(held_indexes),
        "threshold": threshold,
        "history": history,
        "calibration": summarize(
            records,
            calibration_indexes,
            calibration_scores,
            threshold,
            baseline,
        ),
        "held": summarize(records, held_indexes, held_scores, threshold, baseline),
        "checkpoint": {
            "filename": output_path.name,
            "sha256": sha256(output_path),
        },
        "runtimeSeconds": time.perf_counter() - started,
    }


def train(binding_path: Path, output_root: Path) -> dict[str, Any]:
    binding_path = binding_path.resolve(strict=True)
    output_root = output_root.resolve()
    partial_root = output_root.with_name(output_root.name + ".partial")
    forbid_v17([binding_path, output_root, partial_root])
    if output_root.exists() or partial_root.exists():
        raise ValueError("phonetic_prosody_output_exists")
    binding = read_object(binding_path)
    if binding.get("schema") != BINDING_SCHEMA:
        raise ValueError("phonetic_prosody_binding_schema_invalid")
    program_path = Path(__file__).resolve()
    if binding.get("programSha256") != sha256(program_path):
        raise ValueError("phonetic_prosody_program_hash_mismatch")
    if Path(str(binding.get("plannedOutputRoot"))).resolve() != output_root:
        raise ValueError("phonetic_prosody_output_binding_mismatch")

    feature_root = Path(str(binding.get("featureRoot"))).resolve(strict=True)
    feature_manifest_path = feature_root / "features.manifest.v1.json"
    if binding.get("featureManifestSha256") != sha256(feature_manifest_path):
        raise ValueError("phonetic_prosody_feature_manifest_hash_mismatch")
    feature_manifest = read_object(feature_manifest_path)
    if feature_manifest.get("schema") != "baxy.opened-physical-wav2vec2-features.v1":
        raise ValueError("phonetic_prosody_feature_manifest_schema_invalid")
    arrays = feature_manifest.get("arrays")
    if not isinstance(arrays, dict):
        raise ValueError("phonetic_prosody_feature_arrays_invalid")

    def load_array(name: str, mmap_mode: str | None) -> np.ndarray:
        descriptor = arrays.get(name)
        if not isinstance(descriptor, dict):
            raise ValueError("phonetic_prosody_feature_array_invalid")
        path = feature_root / str(descriptor.get("filename"))
        if descriptor.get("sha256") != sha256(path):
            raise ValueError("phonetic_prosody_feature_array_hash_mismatch")
        return np.load(path, mmap_mode=mmap_mode)

    features = load_array("features", "r")
    offsets = load_array("offsets", None)
    prosody = load_array("prosody", None).astype(np.float32)
    records = feature_manifest.get("records")
    if not isinstance(records, list) or len(offsets) != len(records) + 1:
        raise ValueError("phonetic_prosody_feature_records_invalid")
    baseline = load_baseline_decisions(binding)
    audio_hashes = {str(record.get("audioSha256")) for record in records}
    if set(baseline) != audio_hashes:
        raise ValueError("phonetic_prosody_baseline_coverage_invalid")

    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("phonetic_prosody_cuda_unavailable")
    seeds = binding.get("seeds")
    variants = binding.get("variants")
    if (
        not isinstance(seeds, list)
        or not seeds
        or not isinstance(variants, list)
        or variants != ["phonetic_only", "dual_stream"]
    ):
        raise ValueError("phonetic_prosody_schedule_invalid")
    epochs = int(binding.get("epochs"))
    batch_size = int(binding.get("batchSize"))
    learning_rate = float(binding.get("learningRate"))
    if epochs < 1 or batch_size < 2 or learning_rate <= 0.0:
        raise ValueError("phonetic_prosody_schedule_invalid")

    partial_root.mkdir(parents=True)
    runs = []
    corpora = sorted({str(record["corpus"]) for record in records})
    for variant in variants:
        for held_corpus in corpora:
            fit_indexes, calibration_indexes, held_indexes = deterministic_split(
                records, held_corpus
            )
            for raw_seed in seeds:
                seed = int(raw_seed)
                checkpoint_path = (
                    partial_root / f"{variant}_{held_corpus}_seed{seed}.pt"
                )
                run = train_run(
                    torch=torch,
                    features=features,
                    offsets=offsets,
                    prosody=prosody,
                    records=records,
                    fit_indexes=fit_indexes,
                    calibration_indexes=calibration_indexes,
                    held_indexes=held_indexes,
                    baseline=baseline,
                    use_prosody=variant == "dual_stream",
                    seed=seed,
                    epochs=epochs,
                    batch_size=batch_size,
                    learning_rate=learning_rate,
                    output_path=checkpoint_path,
                )
                run["variant"] = variant
                run["heldCorpus"] = held_corpus
                runs.append(run)
                held = run["held"]
                print(
                    f"BAXY_PHONETIC_PROSODY|{variant}|{held_corpus}|seed={seed}|"
                    f"model={held['modelPositiveAccepted']}/{held['positiveFiles']}|"
                    f"false={held['modelNegativeFalseActivations']}/"
                    f"{held['negativeFiles']}|combined="
                    f"{held['combinedPositiveAccepted']}/"
                    f"{held['baselinePositiveAccepted']}|combined_false="
                    f"{held['combinedNegativeFalseActivations']}",
                    flush=True,
                )

    variant_summaries = {}
    for variant in variants:
        variant_runs = [run for run in runs if run["variant"] == variant]
        all_preserve = all(
            run["held"]["combinedPositiveAccepted"]
            == run["held"]["baselinePositiveAccepted"]
            for run in variant_runs
        )
        all_zero_false = all(
            run["held"]["combinedNegativeFalseActivations"] == 0 for run in variant_runs
        )
        variant_summaries[variant] = {
            "runs": len(variant_runs),
            "allSeedsAndFoldsPreserveBaselinePositiveCoverage": all_preserve,
            "allSeedsAndFoldsHaveZeroCombinedFalseActivations": all_zero_false,
            "developmentGatePassed": bool(all_preserve and all_zero_false),
        }
    dual_passed = bool(variant_summaries["dual_stream"]["developmentGatePassed"])
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_development_leave_one_complete_physical_corpus_out",
        "bindingSha256": sha256(binding_path),
        "programSha256": sha256(program_path),
        "featureManifestSha256": sha256(feature_manifest_path),
        "contract": {
            "fitCalibrationHeldDisjoint": True,
            "thresholdSelection": "nextafter_maximum_calibration_negative_score",
            "outerHeldCorpusUsedForTraining": False,
            "outerHeldCorpusUsedForThreshold": False,
            "architectureSelectionOnOpenedDevelopment": True,
            "freshPhysicalHoldoutRequiredAfterPass": True,
            "physicalV17Read": False,
            "runtimeModificationAllowed": False,
        },
        "architecture": {
            "teacherLayer": 2,
            "temporal": "two_depthwise_separable_5_frame_blocks",
            "pooling": "masked_mean_std_and_learned_attention",
            "embeddingSize": 64,
            "objective": "three_subcenter_arcface_plus_domain_adversarial",
            "arcfaceMargin": 0.2,
            "arcfaceScale": 20.0,
            "domainAdversarialStrength": 0.2,
            "domainLossWeight": 0.1,
        },
        "schedule": {
            "seeds": [int(seed) for seed in seeds],
            "epochs": epochs,
            "batchSize": batch_size,
            "learningRate": learning_rate,
        },
        "variantSummaries": variant_summaries,
        "runs": runs,
        "developmentGatePassed": dual_passed,
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
    report_path = partial_root / "training.report.v1.json"
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
        f"BAXY_PHONETIC_PROSODY|complete|passed="
        f"{str(result['developmentGatePassed']).lower()}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
