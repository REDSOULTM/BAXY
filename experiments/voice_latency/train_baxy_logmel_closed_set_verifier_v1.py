"""Train a compact closed-set BAXY verifier directly on Whisper log-Mel."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import random
import time

import numpy as np


FRAMES = 300
MEL_BINS = 80
PAD_VALUE = -1.5
CANDIDATE_REPORT_SCHEMA = "baxy.raw-rolling-multialias-wake-corpus-development.v2"
CASCADE_REPORT_SCHEMA = "baxy.wake-cascade-runtime-raw-development.v1"
HARD_NEGATIVE_SCHEMA = "baxy.openslr-wake-hard-negative-logmel.v1"
CONTROLLED_HARD_NEGATIVE_SCHEMA = "baxy.controlled-hard-negative-logmel.v1"
SAFETY_SCORE_MARGIN = 0.05


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_logmel_verifier_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ADAPT = load_component(
    "train_baxy_hyperspotter_physical_adaptation_v3.py",
    "_baxy_logmel_verifier_stores_v1",
)
_BASE = _ADAPT._BASE


def source_key(domain: str, record: dict[str, object]) -> str:
    if domain == "synthetic":
        value = f"{record.get('label')}:{record.get('source_index')}"
    elif domain in {
        "physical",
        "human",
        "auxiliary",
        "hard_negative",
        "hard_negative_focus",
    }:
        value = record.get("record_id")
    else:
        raise ValueError("baxy_logmel_verifier_domain_invalid")
    if not isinstance(value, str):
        raise ValueError("baxy_logmel_verifier_source_invalid")
    return f"{domain}:{value}"


def group_indexes(
    domain: str, records: list[dict[str, object]], indexes: list[int]
) -> list[list[int]]:
    groups: dict[str, list[int]] = {}
    contracts: dict[str, tuple[object, object]] = {}
    for index in indexes:
        record = records[index]
        key = source_key(domain, record)
        contract = (record.get("label"), record.get("persona_id"))
        if key in contracts and contracts[key] != contract:
            raise ValueError("baxy_logmel_verifier_source_drift")
        contracts[key] = contract
        groups.setdefault(key, []).append(index)
    return [groups[key] for key in sorted(groups)]


def balanced_batch(
    pools: dict[str, list[list[int]]],
    *,
    batch_size: int,
    auxiliary_probability: float,
    rng: random.Random,
    hard_negative_probability: float = 0.0,
    hard_negative_focus_probability: float = 0.0,
    human_probability: float = 0.0,
) -> tuple[list[tuple[str, int]], list[float], list[str]]:
    required = (
        "synthetic_positive",
        "synthetic_negative",
        "physical_positive",
        "physical_negative",
    )
    if (
        batch_size < 4
        or batch_size % 4
        or not 0.0 <= auxiliary_probability <= 1.0
        or not 0.0 <= hard_negative_probability <= 1.0
        or not 0.0 <= hard_negative_focus_probability <= 1.0
        or not 0.0 <= human_probability <= 1.0
        or auxiliary_probability + human_probability > 1.0
        or any(not pools.get(key) for key in required)
        or (
            auxiliary_probability
            and (
                not pools.get("auxiliary_positive")
                or not pools.get("auxiliary_negative")
            )
        )
        or (hard_negative_probability and not pools.get("hard_negative"))
        or (
            hard_negative_focus_probability
            and not pools.get("hard_negative_focus")
        )
        or (
            human_probability
            and (
                not pools.get("human_positive")
                or not pools.get("human_negative")
            )
        )
    ):
        raise ValueError("baxy_logmel_verifier_batch_invalid")
    pairs: list[tuple[tuple[str, int], float, str]] = []
    quarter = batch_size // 4
    for pool_name in required:
        domain = pool_name.split("_", 1)[0]
        label = 1.0 if pool_name.endswith("positive") else 0.0
        for _ in range(quarter):
            selected_domain = domain
            selected_pool = pools[pool_name]
            if (
                label == 0.0
                and hard_negative_probability
                and rng.random() < hard_negative_probability
            ):
                selected_domain = "hard_negative"
                selected_pool = pools["hard_negative"]
                if (
                    hard_negative_focus_probability
                    and rng.random() < hard_negative_focus_probability
                ):
                    selected_domain = "hard_negative_focus"
                    selected_pool = pools["hard_negative_focus"]
            elif domain == "physical":
                domain_draw = rng.random()
                if domain_draw < human_probability:
                    selected_domain = "human"
                    selected_pool = pools[
                        "human_positive" if label else "human_negative"
                    ]
                elif domain_draw < human_probability + auxiliary_probability:
                    selected_domain = "auxiliary"
                    selected_pool = pools[
                        "auxiliary_positive" if label else "auxiliary_negative"
                    ]
            group = rng.choice(selected_pool)
            pairs.append(
                ((selected_domain, rng.choice(group)), label, selected_domain)
            )
    rng.shuffle(pairs)
    return (
        [selection for selection, _, _ in pairs],
        [label for _, label, _ in pairs],
        [domain for _, _, domain in pairs],
    )


def reduce_source_scores(
    domain: str,
    records: list[dict[str, object]],
    indexes: list[int],
    scores: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    if len(indexes) != len(scores):
        raise ValueError("baxy_logmel_verifier_score_count_invalid")
    groups: dict[str, tuple[int, list[float]]] = {}
    for index, score in zip(indexes, scores):
        record = records[index]
        key = source_key(domain, record)
        label = int(record.get("label") == "positive")
        if key in groups and groups[key][0] != label:
            raise ValueError("baxy_logmel_verifier_score_label_drift")
        groups.setdefault(key, (label, []))[1].append(float(score))
    ordered = sorted(groups)
    return (
        np.asarray([groups[key][0] for key in ordered], dtype=np.int64),
        np.asarray([max(groups[key][1]) for key in ordered], dtype=np.float64),
    )


def candidate_rank(
    physical: dict[str, object],
    human: dict[str, object],
    synthetic: dict[str, object],
    calibration: dict[str, object],
    hard_negative: dict[str, object] | None = None,
) -> tuple[float, ...]:
    physical_recall = float(calibration["physical_recall"])
    human_recall = float(calibration["human_recall"])
    base = (
        min(physical_recall, human_recall),
        physical_recall + human_recall,
        -float(calibration["score_threshold"]),
        float(physical["zero_false_positive_recall"]),
        float(human["zero_false_positive_recall"]),
        float(physical["auc"]),
        float(human["auc"]),
        -float(physical["equal_error_rate"]),
        float(synthetic["auc"]),
    )
    if hard_negative is None:
        return base
    return base


def candidate_audio_hashes(
    report: dict[str, object], *, physical_manifest_sha256: str
) -> set[str]:
    if (
        report.get("schema")
        not in {CANDIDATE_REPORT_SCHEMA, CASCADE_REPORT_SCHEMA}
        or report.get("corpusManifestSha256") != physical_manifest_sha256
        or report.get("blindHumanPartitionAccessed") is not False
    ):
        raise ValueError("baxy_logmel_verifier_candidate_boundary_invalid")
    result: set[str] = set()
    for section_name in ("positive", "negative"):
        section = report.get(section_name)
        records = section.get("records") if isinstance(section, dict) else None
        if not isinstance(records, list):
            raise ValueError("baxy_logmel_verifier_candidate_records_invalid")
        for record in records:
            if not isinstance(record, dict) or not isinstance(
                record.get("audioSha256"), str
            ):
                raise ValueError("baxy_logmel_verifier_candidate_record_invalid")
            selected = (
                record.get("accepted")
                if report.get("schema") == CANDIDATE_REPORT_SCHEMA
                else record.get("upstreamCandidate")
            )
            if not isinstance(selected, bool):
                raise ValueError("baxy_logmel_verifier_candidate_record_invalid")
            if selected:
                result.add(str(record["audioSha256"]).lower())
    if not result:
        raise ValueError("baxy_logmel_verifier_candidate_empty")
    return result


def hard_negative_manifest_schema(path: Path) -> str:
    manifest = _BASE._LOGMEL.read_object(path.resolve(strict=True))
    schema = manifest.get("schema")
    if schema not in {HARD_NEGATIVE_SCHEMA, CONTROLLED_HARD_NEGATIVE_SCHEMA}:
        raise ValueError("baxy_logmel_verifier_hard_negative_schema_invalid")
    return str(schema)


def stratified_persona_split(
    records: list[dict[str, object]],
    *,
    seed: int,
    validation_personas_per_label: int,
) -> tuple[set[str], set[str]]:
    """Split a physical corpus without leaking one speaker across sides."""

    if validation_personas_per_label < 1:
        raise ValueError("baxy_logmel_verifier_physical_split_invalid")
    labels_by_persona: dict[str, str] = {}
    personas_by_label: dict[str, set[str]] = {
        "positive": set(),
        "adversarial_negative": set(),
    }
    for record in records:
        persona = record.get("persona_id")
        label = record.get("label")
        if not isinstance(persona, str) or label not in personas_by_label:
            raise ValueError("baxy_logmel_verifier_physical_split_record_invalid")
        if persona in labels_by_persona and labels_by_persona[persona] != label:
            raise ValueError("baxy_logmel_verifier_physical_persona_label_drift")
        labels_by_persona[persona] = str(label)
        personas_by_label[str(label)].add(persona)

    validation: set[str] = set()
    for offset, label in enumerate(("positive", "adversarial_negative")):
        personas = sorted(personas_by_label[label])
        if len(personas) <= validation_personas_per_label:
            raise ValueError("baxy_logmel_verifier_physical_split_too_small")
        rng = random.Random(seed + 1009 * (offset + 1))
        rng.shuffle(personas)
        validation.update(personas[:validation_personas_per_label])
    return set(labels_by_persona) - validation, validation


def build_model(*, channels: int, blocks: int, dropout: float) -> object:
    import torch
    import torch.nn as nn

    class ResidualBlock(nn.Module):
        def __init__(self, dilation: int) -> None:
            super().__init__()
            self.layers = nn.Sequential(
                nn.Conv1d(
                    channels,
                    channels,
                    kernel_size=5,
                    padding=2 * dilation,
                    dilation=dilation,
                    groups=channels,
                ),
                nn.Conv1d(channels, channels, kernel_size=1),
                nn.GroupNorm(8, channels),
                nn.GELU(),
                nn.Dropout(dropout),
            )

        def forward(self, values: object) -> object:
            return values + self.layers(values)

    class Verifier(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.stem = nn.Sequential(
                nn.Conv1d(MEL_BINS, channels, kernel_size=5, stride=2, padding=2),
                nn.GroupNorm(8, channels),
                nn.GELU(),
            )
            self.blocks = nn.Sequential(
                *[ResidualBlock(2 ** (index % 4)) for index in range(blocks)]
            )
            self.output = nn.Sequential(
                nn.Linear(channels * 2, channels),
                nn.LayerNorm(channels),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(channels, 1),
            )

        def forward(self, values: object) -> object:
            values = self.blocks(self.stem(values.transpose(1, 2)))
            summary = torch.cat((values.amax(dim=2), values.mean(dim=2)), dim=1)
            return self.output(summary)

    if channels < 16 or channels % 8 or blocks < 1:
        raise ValueError("baxy_logmel_verifier_architecture_invalid")
    return Verifier()


def select_trainable_parameters(model: object, scope: str) -> list[object]:
    """Freeze an initialized verifier except for the requested adaptation head."""

    if scope not in {"all", "head", "final"}:
        raise ValueError("baxy_logmel_verifier_trainable_scope_invalid")
    parameters = list(model.parameters())
    for parameter in parameters:
        parameter.requires_grad = scope == "all"
    if scope == "head":
        selected = list(model.output.parameters())
    elif scope == "final":
        selected = list(model.output[-1].parameters())
    else:
        selected = parameters
    for parameter in selected:
        parameter.requires_grad = True
    if not selected or not all(parameter.requires_grad for parameter in selected):
        raise ValueError("baxy_logmel_verifier_trainable_scope_invalid")
    return selected


def train(
    *,
    synthetic_feature_manifest_path: Path,
    physical_feature_manifest_path: Path,
    human_feature_manifest_path: Path,
    auxiliary_feature_manifest_path: Path | None,
    hard_negative_feature_manifest_path: Path | None,
    hard_negative_focus_feature_manifest_path: Path | None,
    candidate_report_paths: list[Path],
    human_candidate_report_paths: list[Path],
    initializer_checkpoint_path: Path | None,
    output_directory: Path,
    seed: int,
    validation_personas: int,
    physical_validation_personas_per_label: int,
    channels: int,
    blocks: int,
    epochs: int,
    batches_per_epoch: int,
    batch_size: int,
    validation_batch_size: int,
    learning_rate: float,
    weight_decay: float,
    dropout: float,
    feature_noise_std: float,
    time_mask_frames: int,
    ranking_weight: float,
    ranking_margin: float,
    auxiliary_probability: float,
    human_probability: float,
    hard_negative_probability: float,
    hard_negative_focus_probability: float,
    hard_negative_validation_personas: int,
    deployment_threshold: float,
    trainable_scope: str,
    device: str,
) -> dict[str, object]:
    if (
        output_directory.exists()
        or epochs < 1
        or batches_per_epoch < 1
        or batch_size < 4
        or batch_size % 4
        or validation_batch_size < 1
        or learning_rate <= 0.0
        or weight_decay < 0.0
        or not 0.0 <= dropout < 1.0
        or feature_noise_std < 0.0
        or time_mask_frames < 0
        or ranking_weight < 0.0
        or ranking_margin < 0.0
        or not 0.0 <= auxiliary_probability <= 1.0
        or not 0.0 <= human_probability <= 1.0
        or auxiliary_probability + human_probability > 1.0
        or not 0.0 <= hard_negative_probability <= 1.0
        or not 0.0 <= hard_negative_focus_probability <= 1.0
        or hard_negative_validation_personas < 1
        or physical_validation_personas_per_label < 1
        or not np.isfinite(deployment_threshold)
        or trainable_scope not in {"all", "head", "final"}
        or (auxiliary_probability and auxiliary_feature_manifest_path is None)
        or (
            hard_negative_probability
            and hard_negative_feature_manifest_path is None
        )
        or (
            hard_negative_focus_probability
            and hard_negative_focus_feature_manifest_path is None
        )
        or device not in {"cpu", "cuda"}
    ):
        raise ValueError("baxy_logmel_verifier_schedule_invalid")
    output_directory = output_directory.resolve()
    physical_manifest_path = physical_feature_manifest_path.resolve(strict=True)
    physical_preview = _BASE._LOGMEL.read_object(physical_manifest_path)
    physical_schema = physical_preview.get("schema")
    if physical_schema not in {
        _ADAPT.PHYSICAL_SCHEMA,
        _ADAPT.AUXILIARY_SCHEMA,
    }:
        raise ValueError("baxy_logmel_verifier_physical_schema_invalid")
    stores = {
        "synthetic": _ADAPT._load_store(
            synthetic_feature_manifest_path,
            expected_schema=_ADAPT.SYNTHETIC_SCHEMA,
        ),
        "physical": _ADAPT._load_store(
            physical_manifest_path,
            expected_schema=str(physical_schema),
            allow_human_development=True,
        ),
    }
    stores["human"] = _ADAPT._load_store(
        human_feature_manifest_path,
        expected_schema=_ADAPT.AUXILIARY_SCHEMA,
        allow_human_development=True,
    )
    if stores["human"]["manifest"].get("human_development_audio_accessed") is not True:
        raise ValueError("baxy_logmel_verifier_human_manifest_invalid")
    if auxiliary_feature_manifest_path is not None:
        stores["auxiliary"] = _ADAPT._load_store(
            auxiliary_feature_manifest_path,
            expected_schema=_ADAPT.AUXILIARY_SCHEMA,
        )
    if hard_negative_feature_manifest_path is not None:
        hard_negative_schema = hard_negative_manifest_schema(
            hard_negative_feature_manifest_path
        )
        stores["hard_negative"] = _ADAPT._load_store(
            hard_negative_feature_manifest_path,
            expected_schema=hard_negative_schema,
            allow_human_development=(
                hard_negative_schema == CONTROLLED_HARD_NEGATIVE_SCHEMA
            ),
        )
    if hard_negative_focus_feature_manifest_path is not None:
        hard_negative_focus_schema = hard_negative_manifest_schema(
            hard_negative_focus_feature_manifest_path
        )
        stores["hard_negative_focus"] = _ADAPT._load_store(
            hard_negative_focus_feature_manifest_path,
            expected_schema=hard_negative_focus_schema,
            allow_human_development=(
                hard_negative_focus_schema == CONTROLLED_HARD_NEGATIVE_SCHEMA
            ),
        )
    physical_manifest_sha256 = str(
        stores["physical"]["manifest"]["sources"]["physical_manifest_sha256"]
    )
    candidate_hashes: set[str] | None = None
    resolved_candidate_reports: list[Path] = []
    if candidate_report_paths:
        candidate_hashes = set()
        for raw_path in candidate_report_paths:
            path = raw_path.resolve(strict=True)
            resolved_candidate_reports.append(path)
            candidate_hashes.update(
                candidate_audio_hashes(
                    _BASE._LOGMEL.read_object(path),
                    physical_manifest_sha256=physical_manifest_sha256,
                )
            )
    human_manifest_sha256 = str(
        stores["human"]["manifest"]["sources"]["physical_manifest_sha256"]
    )
    human_candidate_hashes: set[str] | None = None
    resolved_human_candidate_reports: list[Path] = []
    if human_candidate_report_paths:
        human_candidate_hashes = set()
        for raw_path in human_candidate_report_paths:
            path = raw_path.resolve(strict=True)
            resolved_human_candidate_reports.append(path)
            human_candidate_hashes.update(
                candidate_audio_hashes(
                    _BASE._LOGMEL.read_object(path),
                    physical_manifest_sha256=human_manifest_sha256,
                )
            )
    personas = {
        str(record["persona_id"]) for record in stores["synthetic"]["records"]
    }
    training_personas, validation_persona_set = _BASE.split_personas(
        personas, seed=seed, validation_personas=validation_personas
    )

    physical_personas = {
        str(record["persona_id"]) for record in stores["physical"]["records"]
    }
    if physical_personas.issubset(personas):
        physical_training_personas = physical_personas & training_personas
        physical_validation_persona_set = (
            physical_personas & validation_persona_set
        )
        physical_split_mode = "aligned_to_synthetic_persona_split"
    else:
        (
            physical_training_personas,
            physical_validation_persona_set,
        ) = stratified_persona_split(
            stores["physical"]["records"],
            seed=seed,
            validation_personas_per_label=(
                physical_validation_personas_per_label
            ),
        )
        physical_split_mode = "independent_label_stratified_speaker_split"

    def indexes(domain: str, allowed_personas: set[str]) -> list[int]:
        return [
            index
            for index, record in enumerate(stores[domain]["records"])
            if record["persona_id"] in allowed_personas
        ]

    synthetic_training = indexes("synthetic", training_personas)
    synthetic_validation = indexes("synthetic", validation_persona_set)
    physical_training = indexes("physical", physical_training_personas)
    physical_validation = indexes(
        "physical", physical_validation_persona_set
    )
    human_split_records = stores["human"]["records"]
    if human_candidate_hashes is not None:
        human_split_records = [
            record
            for record in human_split_records
            if record["label"] == "positive"
            or str(record.get("audio_sha256", "")).lower()
            in human_candidate_hashes
        ]
    human_training_personas, human_validation_persona_set = (
        stratified_persona_split(
            human_split_records,
            seed=seed + 31,
            validation_personas_per_label=(
                physical_validation_personas_per_label
            ),
        )
    )
    human_training = indexes("human", human_training_personas)
    human_validation = indexes("human", human_validation_persona_set)
    hard_negative_training: list[int] = []
    hard_negative_validation: list[int] = []
    hard_negative_training_personas: set[str] = set()
    hard_negative_validation_persona_set: set[str] = set()
    if "hard_negative" in stores:
        hard_personas = sorted(
            {
                str(record["persona_id"])
                for record in stores["hard_negative"]["records"]
            }
        )
        if len(hard_personas) <= hard_negative_validation_personas:
            raise ValueError("baxy_logmel_verifier_hard_negative_split_invalid")
        hard_rng = random.Random(seed + 17)
        hard_rng.shuffle(hard_personas)
        hard_negative_validation_persona_set = set(
            hard_personas[:hard_negative_validation_personas]
        )
        hard_negative_training_personas = (
            set(hard_personas) - hard_negative_validation_persona_set
        )
        for index, record in enumerate(stores["hard_negative"]["records"]):
            target = (
                hard_negative_validation
                if record["persona_id"] in hard_negative_validation_persona_set
                else hard_negative_training
            )
            target.append(index)
    if candidate_hashes is not None:
        def is_verifier_candidate(index: int) -> bool:
            record = stores["physical"]["records"][index]
            return (
                record["label"] == "positive"
                or str(record.get("audio_sha256", "")).lower() in candidate_hashes
            )

        physical_training = [
            index for index in physical_training if is_verifier_candidate(index)
        ]
        physical_validation = [
            index for index in physical_validation if is_verifier_candidate(index)
        ]
    if human_candidate_hashes is not None:
        def is_human_verifier_candidate(index: int) -> bool:
            record = stores["human"]["records"][index]
            return (
                record["label"] == "positive"
                or str(record.get("audio_sha256", "")).lower()
                in human_candidate_hashes
            )

        human_training = [
            index for index in human_training if is_human_verifier_candidate(index)
        ]
        human_validation = [
            index for index in human_validation if is_human_verifier_candidate(index)
        ]

    def pool(domain: str, selected: list[int], label: str) -> list[list[int]]:
        records = stores[domain]["records"]
        return group_indexes(
            domain,
            records,
            [index for index in selected if records[index]["label"] == label],
        )

    pools = {
        "synthetic_positive": pool(
            "synthetic", synthetic_training, "positive"
        ),
        "synthetic_negative": pool(
            "synthetic", synthetic_training, "adversarial_negative"
        ),
        "physical_positive": pool("physical", physical_training, "positive"),
        "physical_negative": pool(
            "physical", physical_training, "adversarial_negative"
        ),
        "human_positive": pool("human", human_training, "positive"),
        "human_negative": pool(
            "human", human_training, "adversarial_negative"
        ),
    }
    if "auxiliary" in stores:
        auxiliary_indexes = list(range(len(stores["auxiliary"]["records"])))
        pools.update(
            {
                "auxiliary_positive": pool(
                    "auxiliary", auxiliary_indexes, "positive"
                ),
                "auxiliary_negative": pool(
                    "auxiliary", auxiliary_indexes, "adversarial_negative"
                ),
            }
        )
    if "hard_negative" in stores:
        pools["hard_negative"] = group_indexes(
            "hard_negative",
            stores["hard_negative"]["records"],
            hard_negative_training,
        )
    if "hard_negative_focus" in stores:
        pools["hard_negative_focus"] = group_indexes(
            "hard_negative_focus",
            stores["hard_negative_focus"]["records"],
            list(range(len(stores["hard_negative_focus"]["records"]))),
        )
    if any(not value for value in pools.values()):
        raise ValueError("baxy_logmel_verifier_split_invalid")

    import torch
    import torch.nn.functional as functional

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("baxy_logmel_verifier_cuda_unavailable")
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    if device == "cuda":
        torch.cuda.manual_seed_all(seed)
        torch.set_float32_matmul_precision("high")
    torch_device = torch.device(device)
    model = build_model(channels=channels, blocks=blocks, dropout=dropout).to(
        torch_device
    )
    resolved_initializer_checkpoint = None
    if initializer_checkpoint_path is not None:
        resolved_initializer_checkpoint = initializer_checkpoint_path.resolve(
            strict=True
        )
        initializer = torch.load(
            resolved_initializer_checkpoint,
            map_location="cpu",
            weights_only=False,
        )
        if (
            not isinstance(initializer, dict)
            or initializer.get("schema")
            != "baxy.logmel-closed-set-verifier-checkpoint.v1"
            or initializer.get("channels") != channels
            or initializer.get("blocks") != blocks
            or not isinstance(initializer.get("model_state_dict"), dict)
        ):
            raise ValueError("baxy_logmel_verifier_initializer_invalid")
        model.load_state_dict(initializer["model_state_dict"], strict=True)
    trainable_parameters = select_trainable_parameters(model, trainable_scope)
    optimizer = torch.optim.AdamW(
        trainable_parameters, lr=learning_rate, weight_decay=weight_decay
    )
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")
    rng = random.Random(seed + 1)
    augmentation_rng = np.random.default_rng(seed + 2)
    validation_scores: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    def feature_batch(
        selections: list[tuple[str, int]], *, augment: bool
    ) -> object:
        values = np.full(
            (len(selections), FRAMES, MEL_BINS), PAD_VALUE, dtype=np.float32
        )
        for row, (domain, index) in enumerate(selections):
            store = stores[domain]
            offsets = store["offsets"]
            source = np.asarray(
                store["features"][
                    int(offsets[index]) : int(offsets[index + 1])
                ],
                dtype=np.float32,
            )
            if len(source) > FRAMES:
                start = (
                    int(augmentation_rng.integers(0, len(source) - FRAMES + 1))
                    if augment
                    else (len(source) - FRAMES) // 2
                )
                source = source[start : start + FRAMES]
            if domain == "synthetic":
                maximum_start = FRAMES - len(source)
                start = (
                    int(augmentation_rng.integers(0, maximum_start + 1))
                    if augment
                    else min(100, maximum_start)
                )
            else:
                start = 0
            values[row, start : start + len(source)] = source
            if augment:
                if feature_noise_std:
                    values[row] += augmentation_rng.normal(
                        0.0, feature_noise_std, values[row].shape
                    ).astype(np.float32)
                if time_mask_frames:
                    width = int(
                        augmentation_rng.integers(0, time_mask_frames + 1)
                    )
                    if width:
                        mask_start = int(
                            augmentation_rng.integers(0, FRAMES - width + 1)
                        )
                        values[row, mask_start : mask_start + width] = PAD_VALUE
        return torch.from_numpy(values).to(torch_device)

    def evaluate(domain: str, selected: list[int]) -> dict[str, object]:
        scores: list[np.ndarray] = []
        model.eval()
        with torch.inference_mode():
            for start in range(0, len(selected), validation_batch_size):
                batch_indexes = selected[start : start + validation_batch_size]
                with torch.autocast(
                    device_type=device,
                    dtype=torch.float16,
                    enabled=device == "cuda",
                ):
                    logits = model(
                        feature_batch(
                            [(domain, index) for index in batch_indexes],
                            augment=False,
                        )
                    )
                scores.append(logits[:, 0].float().cpu().numpy())
        labels, reduced = reduce_source_scores(
            domain,
            stores[domain]["records"],
            selected,
            np.concatenate(scores),
        )
        if set(labels.tolist()) != {0, 1}:
            raise ValueError("baxy_logmel_verifier_validation_labels_invalid")
        validation_scores[domain] = (labels, reduced)
        result = _BASE.binary_metrics(labels, reduced)
        positive = labels == 1
        negative = labels == 0
        result["deployment_threshold"] = deployment_threshold
        result["positive_accepted_at_deployment_threshold"] = int(
            np.sum(reduced[positive] >= deployment_threshold)
        )
        result["true_positive_recall_at_deployment_threshold"] = float(
            np.mean(reduced[positive] >= deployment_threshold)
        )
        result["false_acceptances_at_deployment_threshold"] = int(
            np.sum(reduced[negative] >= deployment_threshold)
        )
        result["window_examples"] = len(selected)
        result["source_examples"] = len(labels)
        return result

    def evaluate_negative_domain(
        domain: str, selected: list[int]
    ) -> dict[str, object]:
        scores: list[np.ndarray] = []
        model.eval()
        with torch.inference_mode():
            for start in range(0, len(selected), validation_batch_size):
                batch_indexes = selected[start : start + validation_batch_size]
                with torch.autocast(
                    device_type=device,
                    dtype=torch.float16,
                    enabled=device == "cuda",
                ):
                    logits = model(
                        feature_batch(
                            [
                                (domain, index)
                                for index in batch_indexes
                            ],
                            augment=False,
                        )
                    )
                scores.append(logits[:, 0].float().cpu().numpy())
        labels, reduced = reduce_source_scores(
            domain,
            stores[domain]["records"],
            selected,
            np.concatenate(scores),
        )
        if set(labels.tolist()) != {0}:
            raise ValueError("baxy_logmel_verifier_hard_negative_labels_invalid")
        validation_scores[domain] = (labels, reduced)
        return {
            "threshold": deployment_threshold,
            "false_acceptances_at_threshold": int(
                np.sum(reduced >= deployment_threshold)
            ),
            "maximum_score": float(np.max(reduced)),
            "p99_score": float(np.percentile(reduced, 99)),
            "window_examples": len(selected),
            "source_examples": len(reduced),
        }

    def evaluate_all() -> dict[str, dict[str, object]]:
        result = {
            "physical": evaluate("physical", physical_validation),
            "human": evaluate("human", human_validation),
            "synthetic": evaluate("synthetic", synthetic_validation),
        }
        if "hard_negative" in stores:
            result["hard_negative"] = evaluate_negative_domain(
                "hard_negative", hard_negative_validation
            )
        if "hard_negative_focus" in stores:
            result["hard_negative_focus"] = evaluate_negative_domain(
                "hard_negative_focus",
                list(range(len(stores["hard_negative_focus"]["records"]))),
            )
        negative_scores = [
            scores[labels == 0]
            for domain in (
                "physical",
                "human",
                "hard_negative",
                "hard_negative_focus",
            )
            if domain in validation_scores
            for labels, scores in (validation_scores[domain],)
        ]
        maximum_negative = float(
            max(float(np.max(scores)) for scores in negative_scores)
        )
        calibrated_threshold = max(
            deployment_threshold, maximum_negative + SAFETY_SCORE_MARGIN
        )
        physical_labels, physical_scores = validation_scores["physical"]
        human_labels, human_scores = validation_scores["human"]
        result["calibration"] = {
            "lower_bound": deployment_threshold,
            "safety_margin": SAFETY_SCORE_MARGIN,
            "maximum_gated_or_hard_negative_score": maximum_negative,
            "score_threshold": calibrated_threshold,
            "physical_recall": float(
                np.mean(
                    physical_scores[physical_labels == 1]
                    >= calibrated_threshold
                )
            ),
            "human_recall": float(
                np.mean(
                    human_scores[human_labels == 1] >= calibrated_threshold
                )
            ),
            "physical_false_acceptances": int(
                np.sum(
                    physical_scores[physical_labels == 0]
                    >= calibrated_threshold
                )
            ),
            "human_false_acceptances": int(
                np.sum(
                    human_scores[human_labels == 0] >= calibrated_threshold
                )
            ),
            "hard_negative_false_acceptances": int(
                np.sum(
                    validation_scores["hard_negative"][1]
                    >= calibrated_threshold
                )
            ) if "hard_negative" in validation_scores else 0,
            "hard_negative_focus_false_acceptances": int(
                np.sum(
                    validation_scores["hard_negative_focus"][1]
                    >= calibrated_threshold
                )
            ) if "hard_negative_focus" in validation_scores else 0,
        }
        return result

    output_directory.mkdir(parents=True)
    checkpoint_path = output_directory / "baxy-logmel-closed-set-verifier-v1.pt"
    started = time.perf_counter()
    history: list[dict[str, object]] = []
    best_rank: tuple[float, ...] | None = None
    for epoch in range(1, epochs + 1):
        model.train()
        losses: list[float] = []
        for _ in range(batches_per_epoch):
            selections, labels, domains = balanced_batch(
                pools,
                batch_size=batch_size,
                auxiliary_probability=auxiliary_probability,
                human_probability=human_probability,
                rng=rng,
                hard_negative_probability=hard_negative_probability,
                hard_negative_focus_probability=(
                    hard_negative_focus_probability
                ),
            )
            targets = torch.tensor(labels, dtype=torch.float32, device=torch_device)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(
                device_type=device,
                dtype=torch.float16,
                enabled=device == "cuda",
            ):
                logits = model(feature_batch(selections, augment=True))[:, 0]
                loss = functional.binary_cross_entropy_with_logits(logits, targets)
                if ranking_weight:
                    rank_losses = []
                    for domain in (
                        "synthetic",
                        "physical",
                        "auxiliary",
                        "hard_negative",
                    ):
                        mask = torch.tensor(
                            [value == domain for value in domains],
                            dtype=torch.bool,
                            device=torch_device,
                        )
                        positive = logits[mask & (targets == 1.0)]
                        negative = logits[mask & (targets == 0.0)]
                        if len(positive) and len(negative):
                            rank_losses.append(
                                functional.softplus(
                                    negative[:, None]
                                    - positive[None, :]
                                    + ranking_margin
                                ).mean()
                            )
                    if rank_losses:
                        loss = loss + ranking_weight * torch.stack(rank_losses).mean()
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(trainable_parameters, 5.0)
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.detach().cpu()))
        validation = evaluate_all()
        rank = candidate_rank(
            validation["physical"],
            validation["human"],
            validation["synthetic"],
            validation["calibration"],
            validation.get("hard_negative"),
        )
        selected = best_rank is None or rank > best_rank
        if selected:
            best_rank = rank
            torch.save(
                {
                    "schema": "baxy.logmel-closed-set-verifier-checkpoint.v1",
                    "seed": seed,
                    "channels": channels,
                    "blocks": blocks,
                    "dropout": dropout,
                    "best_epoch": epoch,
                    "model_state_dict": {
                        key: value.detach().cpu()
                        for key, value in model.state_dict().items()
                    },
                },
                checkpoint_path,
            )
        entry = {
            "epoch": epoch,
            "mean_training_loss": float(np.mean(losses)),
            "validation": validation,
            "checkpoint_selected": selected,
        }
        history.append(entry)
        print(json.dumps(entry, sort_keys=True), flush=True)

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval().cpu()
    onnx_path = output_directory / "baxy-logmel-closed-set-verifier-v1.onnx"
    example = torch.full((1, FRAMES, MEL_BINS), PAD_VALUE)
    with torch.inference_mode():
        reference = model(example).numpy()
    torch.onnx.export(
        model,
        example,
        str(onnx_path),
        input_names=["logmel"],
        output_names=["wake_logit"],
        dynamic_axes={"logmel": {0: "batch"}, "wake_logit": {0: "batch"}},
        opset_version=17,
        dynamo=False,
    )
    import onnxruntime as ort

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    actual = session.run(None, {"logmel": example.numpy()})[0]
    parity_error = float(np.max(np.abs(reference - actual)))
    if parity_error > 1e-4:
        raise ValueError("baxy_logmel_verifier_onnx_parity_invalid")
    selected_entry = next(
        entry
        for entry in history
        if entry["epoch"] == checkpoint["best_epoch"]
    )
    report: dict[str, object] = {
        "schema": "baxy.logmel-closed-set-verifier-training.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "speaker_disjoint_direct_logmel_wake_verifier_development",
        "sources": {
            "synthetic_feature_manifest_sha256": _BASE._LOGMEL.sha256(
                stores["synthetic"]["manifest_path"]
            ),
            "physical_feature_manifest_sha256": _BASE._LOGMEL.sha256(
                stores["physical"]["manifest_path"]
            ),
            "human_feature_manifest_sha256": _BASE._LOGMEL.sha256(
                stores["human"]["manifest_path"]
            ),
            "auxiliary_feature_manifest_sha256": (
                None
                if "auxiliary" not in stores
                else _BASE._LOGMEL.sha256(stores["auxiliary"]["manifest_path"])
            ),
            "hard_negative_feature_manifest_sha256": (
                None
                if "hard_negative" not in stores
                else _BASE._LOGMEL.sha256(
                    stores["hard_negative"]["manifest_path"]
                )
            ),
            "hard_negative_focus_feature_manifest_sha256": (
                None
                if "hard_negative_focus" not in stores
                else _BASE._LOGMEL.sha256(
                    stores["hard_negative_focus"]["manifest_path"]
                )
            ),
            "candidate_report_sha256": [
                _BASE._LOGMEL.sha256(path) for path in resolved_candidate_reports
            ],
            "human_candidate_report_sha256": [
                _BASE._LOGMEL.sha256(path)
                for path in resolved_human_candidate_reports
            ],
            "initializer_checkpoint_sha256": (
                None
                if resolved_initializer_checkpoint is None
                else _BASE._LOGMEL.sha256(resolved_initializer_checkpoint)
            ),
        },
        "contract": {
            "seed": seed,
            "initialization": (
                "random"
                if resolved_initializer_checkpoint is None
                else "attested_logmel_checkpoint"
            ),
            "training_personas": sorted(training_personas),
            "validation_personas": sorted(validation_persona_set),
            "physical_split_mode": physical_split_mode,
            "physical_training_personas": sorted(physical_training_personas),
            "physical_validation_personas": sorted(
                physical_validation_persona_set
            ),
            "physical_validation_personas_per_label": (
                physical_validation_personas_per_label
            ),
            "human_training_personas": sorted(human_training_personas),
            "human_validation_personas": sorted(
                human_validation_persona_set
            ),
            "frames": FRAMES,
            "mel_bins": MEL_BINS,
            "channels": channels,
            "blocks": blocks,
            "epochs": epochs,
            "batches_per_epoch": batches_per_epoch,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "weight_decay": weight_decay,
            "dropout": dropout,
            "feature_noise_std": feature_noise_std,
            "time_mask_frames": time_mask_frames,
            "ranking_weight": ranking_weight,
            "ranking_margin": ranking_margin,
            "auxiliary_probability": auxiliary_probability,
            "human_probability": human_probability,
            "hard_negative_probability": hard_negative_probability,
            "hard_negative_focus_probability": (
                hard_negative_focus_probability
            ),
            "hard_negative_validation_personas": sorted(
                hard_negative_validation_persona_set
            ),
            "hard_negative_training_personas": sorted(
                hard_negative_training_personas
            ),
            "deployment_threshold": deployment_threshold,
            "trainable_scope": trainable_scope,
            "trainable_parameter_count": int(
                sum(parameter.numel() for parameter in trainable_parameters)
            ),
            "physical_negative_scope": (
                "all_physical_negatives"
                if candidate_hashes is None
                else "union_of_frozen_upstream_candidate_reports"
            ),
            "upstream_candidate_audio_hashes": (
                0 if candidate_hashes is None else len(candidate_hashes)
            ),
            "human_negative_scope": (
                "all_human_physical_negatives"
                if human_candidate_hashes is None
                else "union_of_frozen_upstream_candidate_reports"
            ),
            "human_upstream_candidate_audio_hashes": (
                0
                if human_candidate_hashes is None
                else len(human_candidate_hashes)
            ),
            "source_uniform_window_sampling": True,
            "source_score_reduction": "maximum_runtime_window_logit",
        },
        "pool_source_counts": {key: len(value) for key, value in pools.items()},
        "history": history,
        "selected": {
            "best_epoch": checkpoint["best_epoch"],
            "validation": selected_entry["validation"],
            "checkpoint": checkpoint_path.name,
            "checkpoint_sha256": _BASE._LOGMEL.sha256(checkpoint_path),
            "onnx": onnx_path.name,
            "onnx_sha256": _BASE._LOGMEL.sha256(onnx_path),
            "onnx_parity_max_abs_error": parity_error,
        },
        "runtime_seconds": time.perf_counter() - started,
        "human_development_audio_accessed": any(
            store["manifest"].get("human_development_audio_accessed") is True
            for store in stores.values()
        ),
        "blind_human_audio_accessed": False,
        "development_only": True,
        "effects_executed": 0,
    }
    (output_directory / "training.report.v1.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-feature-manifest", type=Path, required=True)
    parser.add_argument("--physical-feature-manifest", type=Path, required=True)
    parser.add_argument("--human-feature-manifest", type=Path, required=True)
    parser.add_argument("--auxiliary-feature-manifest", type=Path)
    parser.add_argument("--hard-negative-feature-manifest", type=Path)
    parser.add_argument("--hard-negative-focus-feature-manifest", type=Path)
    parser.add_argument("--candidate-report", type=Path, action="append", default=[])
    parser.add_argument(
        "--human-candidate-report", type=Path, action="append", default=[]
    )
    parser.add_argument("--initializer-checkpoint", type=Path)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=9701)
    parser.add_argument("--validation-personas", type=int, default=8)
    parser.add_argument(
        "--physical-validation-personas-per-label", type=int, default=2
    )
    parser.add_argument("--channels", type=int, default=128)
    parser.add_argument("--blocks", type=int, default=6)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batches-per-epoch", type=int, default=120)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--validation-batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--dropout", type=float, default=0.15)
    parser.add_argument("--feature-noise-std", type=float, default=0.01)
    parser.add_argument("--time-mask-frames", type=int, default=8)
    parser.add_argument("--ranking-weight", type=float, default=0.25)
    parser.add_argument("--ranking-margin", type=float, default=1.0)
    parser.add_argument("--auxiliary-probability", type=float, default=0.25)
    parser.add_argument("--human-probability", type=float, default=0.35)
    parser.add_argument("--hard-negative-probability", type=float, default=0.75)
    parser.add_argument(
        "--hard-negative-focus-probability", type=float, default=0.0
    )
    parser.add_argument("--hard-negative-validation-personas", type=int, default=20)
    parser.add_argument("--deployment-threshold", type=float, default=3.0)
    parser.add_argument(
        "--trainable-scope", choices=("all", "head", "final"), default="all"
    )
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = train(
        synthetic_feature_manifest_path=arguments.synthetic_feature_manifest,
        physical_feature_manifest_path=arguments.physical_feature_manifest,
        human_feature_manifest_path=arguments.human_feature_manifest,
        auxiliary_feature_manifest_path=arguments.auxiliary_feature_manifest,
        hard_negative_feature_manifest_path=(
            arguments.hard_negative_feature_manifest
        ),
        hard_negative_focus_feature_manifest_path=(
            arguments.hard_negative_focus_feature_manifest
        ),
        candidate_report_paths=arguments.candidate_report,
        human_candidate_report_paths=arguments.human_candidate_report,
        initializer_checkpoint_path=arguments.initializer_checkpoint,
        output_directory=arguments.output_directory,
        seed=arguments.seed,
        validation_personas=arguments.validation_personas,
        physical_validation_personas_per_label=(
            arguments.physical_validation_personas_per_label
        ),
        channels=arguments.channels,
        blocks=arguments.blocks,
        epochs=arguments.epochs,
        batches_per_epoch=arguments.batches_per_epoch,
        batch_size=arguments.batch_size,
        validation_batch_size=arguments.validation_batch_size,
        learning_rate=arguments.learning_rate,
        weight_decay=arguments.weight_decay,
        dropout=arguments.dropout,
        feature_noise_std=arguments.feature_noise_std,
        time_mask_frames=arguments.time_mask_frames,
        ranking_weight=arguments.ranking_weight,
        ranking_margin=arguments.ranking_margin,
        auxiliary_probability=arguments.auxiliary_probability,
        human_probability=arguments.human_probability,
        hard_negative_probability=arguments.hard_negative_probability,
        hard_negative_focus_probability=(
            arguments.hard_negative_focus_probability
        ),
        hard_negative_validation_personas=(
            arguments.hard_negative_validation_personas
        ),
        deployment_threshold=arguments.deployment_threshold,
        trainable_scope=arguments.trainable_scope,
        device=arguments.device,
    )
    print(json.dumps(report["selected"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
