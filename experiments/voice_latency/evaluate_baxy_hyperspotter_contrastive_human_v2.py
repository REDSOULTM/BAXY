"""Evaluate domain-normalized HyperSpotter target-vs-confusable margins.

Confusable text controls are selected only from the fixed synthetic
adversarial manifest.  The operating margin is fixed on speaker-disjoint
synthetic validation before human development is scored.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import unicodedata

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_contrastive_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BASE = load_component(
    "train_baxy_hyperspotter_binary_v1.py", "_baxy_contrastive_base_v2"
)
_EVALUATOR = load_component(
    "evaluate_baxy_hyperspotter_human_development_v1.py",
    "_baxy_contrastive_evaluator_v2",
)


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character) and character.isalnum()
    )


def edit_distance(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_character in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1]
                    + (left_character != right_character),
                )
            )
        previous = current
    return previous[-1]


def select_confusable_controls(
    manifest: dict[str, object], *, count: int, aliases: tuple[str, ...]
) -> list[str]:
    if (
        manifest.get("schema") != "baxy.voxcpm2-ipa-filtered-wake-corpus.v1"
        or manifest.get("class_label") != "adversarial_negative"
        or not isinstance(manifest.get("records"), list)
        or count < 1
    ):
        raise ValueError("baxy_contrastive_control_manifest_invalid")
    alias_values = {normalize_text(alias) for alias in aliases}
    candidates: dict[str, str] = {}
    for record in manifest["records"]:
        if not isinstance(record, dict) or not isinstance(record.get("phrase_text"), str):
            raise ValueError("baxy_contrastive_control_record_invalid")
        text = str(record["phrase_text"])
        normalized = normalize_text(text)
        if normalized and normalized not in alias_values:
            candidates.setdefault(normalized, text)
    ranked = sorted(
        candidates.items(),
        key=lambda pair: (
            min(edit_distance(pair[0], alias) for alias in alias_values),
            abs(len(pair[0]) - min(len(alias) for alias in alias_values)),
            pair[0],
        ),
    )
    if len(ranked) < count:
        raise ValueError("baxy_contrastive_controls_missing")
    # HyperSpotter's character vocabulary intentionally excludes punctuation;
    # use the same accent-free alphanumeric form that determined the ranking.
    return [normalized for normalized, _ in ranked[:count]]


def fixed_metrics(
    labels: np.ndarray, margins: np.ndarray, threshold: float
) -> dict[str, object]:
    labels = np.asarray(labels, dtype=np.int64)
    margins = np.asarray(margins, dtype=np.float64)
    metrics = _BASE.binary_metrics(labels, margins)
    decisions = margins >= threshold
    positive = labels == 1
    negative = ~positive
    return {
        **metrics,
        "fixed_threshold": threshold,
        "fixed_positive_hits": int(np.count_nonzero(decisions & positive)),
        "fixed_false_hits": int(np.count_nonzero(decisions & negative)),
    }


def evaluate(
    *,
    synthetic_feature_manifest_path: Path,
    human_feature_manifest_path: Path,
    adversarial_manifest_path: Path,
    ctc_development_report_path: Path,
    hyperspotter_root: Path,
    hyperspotter_site_packages: Path,
    official_checkpoint_path: Path,
    candidate_checkpoint_path: Path,
    output_path: Path,
    validation_personas: int,
    control_count: int,
    batch_size: int,
    device: str,
) -> dict[str, object]:
    if (
        output_path.exists()
        or validation_personas < 1
        or control_count < 1
        or batch_size < 1
        or device not in {"cpu", "cuda"}
    ):
        raise ValueError("baxy_contrastive_schedule_invalid")
    input_paths = [
        synthetic_feature_manifest_path,
        human_feature_manifest_path,
        adversarial_manifest_path,
        ctc_development_report_path,
        hyperspotter_root,
        hyperspotter_site_packages,
        official_checkpoint_path,
        candidate_checkpoint_path,
    ]
    (
        synthetic_feature_manifest_path,
        human_feature_manifest_path,
        adversarial_manifest_path,
        ctc_development_report_path,
        hyperspotter_root,
        hyperspotter_site_packages,
        official_checkpoint_path,
        candidate_checkpoint_path,
    ) = [path.resolve(strict=True) for path in input_paths]
    output_path = output_path.resolve()
    synthetic_manifest = _BASE._LOGMEL.read_object(
        synthetic_feature_manifest_path
    )
    human_manifest = _BASE._LOGMEL.read_object(human_feature_manifest_path)
    adversarial_manifest = _BASE._LOGMEL.read_object(adversarial_manifest_path)
    ctc_report = _BASE._LOGMEL.read_object(ctc_development_report_path)
    if (
        synthetic_manifest.get("schema") != "baxy.baxy-hyperspotter-logmel.v1"
        or synthetic_manifest.get("human_development_audio_accessed") is not False
        or synthetic_manifest.get("blind_human_audio_accessed") is not False
        or human_manifest.get("schema")
        != "baxy.baxy-hyperspotter-human-logmel.v1"
        or human_manifest.get("blind_human_audio_accessed") is not False
        or ctc_report.get("schema") != "baxy.wake-ssl-ctc-ensemble-development.v1"
        or ctc_report.get("blind_human_audio_accessed") is not False
    ):
        raise ValueError("baxy_contrastive_boundary_invalid")
    synthetic_records = synthetic_manifest.get("records")
    human_records = human_manifest.get("records")
    if not isinstance(synthetic_records, list) or not isinstance(human_records, list):
        raise ValueError("baxy_contrastive_records_invalid")

    def load_arrays(
        path: Path, manifest: dict[str, object], count: int
    ) -> tuple[np.ndarray, np.ndarray]:
        files = manifest.get("files")
        if not isinstance(files, dict):
            raise ValueError("baxy_contrastive_files_invalid")
        feature_path = path.parent / str(files["logmel"])
        offset_path = path.parent / str(files["offsets"])
        if (
            _BASE._LOGMEL.sha256(feature_path) != files.get("logmel_sha256")
            or _BASE._LOGMEL.sha256(offset_path) != files.get("offsets_sha256")
        ):
            raise ValueError("baxy_contrastive_feature_hash_invalid")
        features = np.load(feature_path, mmap_mode="r")
        offsets = np.load(offset_path)
        if len(offsets) != count + 1 or int(offsets[-1]) != len(features):
            raise ValueError("baxy_contrastive_feature_shape_invalid")
        return features, offsets

    synthetic_features, synthetic_offsets = load_arrays(
        synthetic_feature_manifest_path,
        synthetic_manifest,
        len(synthetic_records),
    )
    human_features, human_offsets = load_arrays(
        human_feature_manifest_path, human_manifest, len(human_records)
    )
    model, tokenizer, torch, torch_device, checkpoint = _EVALUATOR.load_candidate(
        hyperspotter_root=hyperspotter_root,
        hyperspotter_site_packages=hyperspotter_site_packages,
        official_checkpoint_path=official_checkpoint_path,
        candidate_checkpoint_path=candidate_checkpoint_path,
        device=device,
    )
    aliases = tuple(str(value) for value in checkpoint["aliases"])
    controls = select_confusable_controls(
        adversarial_manifest, count=control_count, aliases=aliases
    )
    text_candidates = [*aliases, *controls]

    import torch.nn as nn

    keyword_ids = tokenizer(text_candidates)["input_ids"]
    keyword_lengths = torch.tensor([len(value) for value in keyword_ids], dtype=torch.long)
    keyword_values = nn.utils.rnn.pad_sequence(
        [torch.tensor(value, dtype=torch.long, device=torch_device) for value in keyword_ids],
        padding_value=tokenizer.pad_token_id,
        batch_first=True,
    )
    with torch.inference_mode():
        text_weights = model.get_text_weights(keyword_values, keyword_lengths)

    personas = {str(record["persona_id"]) for record in synthetic_records}
    _, validation_persona_set = _BASE.split_personas(
        personas,
        seed=int(checkpoint["seed"]),
        validation_personas=validation_personas,
    )
    synthetic_indexes = [
        index
        for index, record in enumerate(synthetic_records)
        if record["persona_id"] in validation_persona_set
    ]

    def margins_for(
        features: np.ndarray, offsets: np.ndarray, indexes: list[int]
    ) -> np.ndarray:
        batches = []
        with torch.inference_mode():
            for start in range(0, len(indexes), batch_size):
                current = indexes[start : start + batch_size]
                lengths = [
                    int(offsets[index + 1] - offsets[index]) for index in current
                ]
                values = np.zeros((len(current), max(lengths), 80), dtype=np.float32)
                for row, index in enumerate(current):
                    values[row, : lengths[row]] = features[
                        int(offsets[index]) : int(offsets[index + 1])
                    ]
                with torch.autocast(
                    device_type=device, dtype=torch.float16, enabled=device == "cuda"
                ):
                    logits = model.run_classifier(
                        torch.from_numpy(values).to(torch_device),
                        text_weights,
                        torch.tensor(lengths, dtype=torch.long, device=torch_device),
                    )
                target = logits[:, : len(aliases)].max(dim=1).values
                control = logits[:, len(aliases) :].max(dim=1).values
                batches.append((target - control).float().cpu().numpy())
                print(
                    f"BAXY_CONTRASTIVE|{min(start + batch_size, len(indexes))}/{len(indexes)}",
                    flush=True,
                )
        return np.concatenate(batches)

    synthetic_margins = margins_for(
        synthetic_features, synthetic_offsets, synthetic_indexes
    )
    synthetic_labels = np.asarray(
        [synthetic_records[index]["label"] == "positive" for index in synthetic_indexes],
        dtype=np.int64,
    )
    fixed_threshold = float(
        np.nextafter(
            np.max(synthetic_margins[synthetic_labels == 0].astype(np.float64)),
            np.inf,
        )
    )
    human_indexes = list(range(len(human_records)))
    human_margins = margins_for(human_features, human_offsets, human_indexes)
    human_labels = np.asarray(
        [record["label"] == "positive" for record in human_records], dtype=np.int64
    )
    human_decisions = human_margins.astype(np.float64) >= fixed_threshold
    synthetic_metrics = fixed_metrics(
        synthetic_labels, synthetic_margins, fixed_threshold
    )
    human_metrics = fixed_metrics(human_labels, human_margins, fixed_threshold)
    per_corpus = {}
    for corpus in ("human_legacy", "human_expanded"):
        mask = np.asarray([record["corpus"] == corpus for record in human_records])
        per_corpus[corpus] = fixed_metrics(
            human_labels[mask], human_margins[mask], fixed_threshold
        )

    ctc_lookup = {
        (str(record["corpus"]), str(record["relative_path"])): record
        for record in ctc_report.get("records", [])
        if isinstance(record, dict)
    }
    ctc_decisions = []
    for record in human_records:
        corpus = "legacy" if record["corpus"] == "human_legacy" else "expanded"
        matched = ctc_lookup.get((corpus, str(record["relative_path"])))
        if matched is None:
            raise ValueError("baxy_contrastive_ctc_mapping_invalid")
        ctc_decisions.append(bool(matched["ctc_product_detected"]))
    fusion = _EVALUATOR.fusion_metrics(
        labels=human_labels,
        ctc_decisions=np.asarray(ctc_decisions),
        hyper_decisions=human_decisions,
    )
    control_digest = hashlib.sha256(
        json.dumps(controls, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    report: dict[str, object] = {
        "schema": "baxy.baxy-hyperspotter-contrastive-human-development.v2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "synthetic_calibrated_target_minus_confusable_human_development",
        "sources": {
            "synthetic_feature_manifest_sha256": _BASE._LOGMEL.sha256(
                synthetic_feature_manifest_path
            ),
            "human_feature_manifest_sha256": _BASE._LOGMEL.sha256(
                human_feature_manifest_path
            ),
            "adversarial_manifest_sha256": _BASE._LOGMEL.sha256(
                adversarial_manifest_path
            ),
            "ctc_development_report_sha256": _BASE._LOGMEL.sha256(
                ctc_development_report_path
            ),
            "candidate_checkpoint_sha256": _BASE._LOGMEL.sha256(
                candidate_checkpoint_path
            ),
        },
        "contract": {
            "aliases": list(aliases),
            "control_count": len(controls),
            "control_selection": "minimum_normalized_edit_distance_from_fixed_adversarial_phrase_texts",
            "controls_sha256": control_digest,
            "score": "maximum_target_alias_logit_minus_maximum_confusable_control_logit",
            "fixed_threshold_source": "speaker_disjoint_synthetic_validation_negative_maximum",
            "fixed_threshold": fixed_threshold,
            "human_or_blind_data_used_for_control_or_threshold_selection": False,
            "audio_or_filenames_retained": False,
        },
        "synthetic_validation": synthetic_metrics,
        "human_development": human_metrics,
        "human_per_corpus": per_corpus,
        "fixed_threshold_ctc_fusion": fusion,
        "human_development_audio_accessed": True,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-feature-manifest", type=Path, required=True)
    parser.add_argument("--human-feature-manifest", type=Path, required=True)
    parser.add_argument("--adversarial-manifest", type=Path, required=True)
    parser.add_argument("--ctc-development-report", type=Path, required=True)
    parser.add_argument("--hyperspotter-root", type=Path, required=True)
    parser.add_argument("--hyperspotter-site-packages", type=Path, required=True)
    parser.add_argument("--official-checkpoint", type=Path, required=True)
    parser.add_argument("--candidate-checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validation-personas", type=int, default=8)
    parser.add_argument("--control-count", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        synthetic_feature_manifest_path=arguments.synthetic_feature_manifest,
        human_feature_manifest_path=arguments.human_feature_manifest,
        adversarial_manifest_path=arguments.adversarial_manifest,
        ctc_development_report_path=arguments.ctc_development_report,
        hyperspotter_root=arguments.hyperspotter_root,
        hyperspotter_site_packages=arguments.hyperspotter_site_packages,
        official_checkpoint_path=arguments.official_checkpoint,
        candidate_checkpoint_path=arguments.candidate_checkpoint,
        output_path=arguments.output,
        validation_personas=arguments.validation_personas,
        control_count=arguments.control_count,
        batch_size=arguments.batch_size,
        device=arguments.device,
    )
    print(
        json.dumps(
            {
                "synthetic_validation": report["synthetic_validation"],
                "human_development": report["human_development"],
                "human_per_corpus": report["human_per_corpus"],
                "fixed_threshold_ctc_fusion": report[
                    "fixed_threshold_ctc_fusion"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
