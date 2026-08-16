"""Extract labeled three-second runtime views from a controlled RAW corpus."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"controlled_raw_runtime_logmel_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_RUNTIME = load_component(
    "extract_baxy_hyperspotter_physical_runtime_logmel_v2.py",
    "_controlled_raw_runtime_logmel_windows_v1",
)
_BASE = _RUNTIME._BASE


def human_positive_provenance(
    source_manifest: dict[str, object],
    augmented_files: list[tuple[str, str]],
) -> dict[str, dict[str, object]]:
    """Bind each augmented clip to its real source speaker.

    The augmentation campaign emits exactly three deterministic variants for
    every source recording, in source-manifest order.  Keeping the original
    speaker group here is essential: treating each variant as a new persona
    would leak the same voice across training and validation.
    """

    source_records = source_manifest.get("records")
    if (
        source_manifest.get("schema") != "baxy.ccby-wake-holdout-corpus.v1"
        or not isinstance(source_records, list)
    ):
        raise ValueError("controlled_raw_runtime_logmel_human_source_invalid")
    positive_records = [
        record
        for record in source_records
        if isinstance(record, dict) and record.get("label") == "positive"
    ]
    if not positive_records or len(augmented_files) != len(positive_records) * 3:
        raise ValueError("controlled_raw_runtime_logmel_human_count_invalid")

    result: dict[str, dict[str, object]] = {}
    for index, (filename, audio_sha256) in enumerate(augmented_files):
        if filename != f"clip_{index:06d}.wav":
            raise ValueError("controlled_raw_runtime_logmel_human_order_invalid")
        source = positive_records[index // 3]
        wav = source.get("wav")
        speaker_group = source.get("speaker_group")
        if (
            not isinstance(wav, dict)
            or not isinstance(wav.get("sha256"), str)
            or not isinstance(speaker_group, str)
            or not speaker_group
            or not isinstance(source.get("source_id"), str)
            or source.get("partition") not in {"development", "blind"}
            or not isinstance(source.get("language"), str)
            or len(audio_sha256) != 64
        ):
            raise ValueError("controlled_raw_runtime_logmel_human_record_invalid")
        key = audio_sha256.lower()
        if key in result:
            raise ValueError("controlled_raw_runtime_logmel_human_hash_duplicate")
        result[key] = {
            "persona_id": f"real_human_{speaker_group}",
            "human_speaker_group": speaker_group,
            "human_source_id": source["source_id"],
            "human_language": source["language"],
            "human_original_partition": source["partition"],
            "human_base_audio_sha256": str(wav["sha256"]).lower(),
            "human_augmentation_variant": index % 3,
        }
    return result


def load_human_positive_provenance(
    source_manifest_path: Path, augmented_positive_directory: Path
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    source_manifest_path = source_manifest_path.resolve(strict=True)
    augmented_positive_directory = augmented_positive_directory.resolve(strict=True)
    files = sorted(augmented_positive_directory.glob("*.wav"))
    file_hashes = [(path.name, _BASE.sha256(path)) for path in files]
    provenance = human_positive_provenance(
        _BASE.read_object(source_manifest_path), file_hashes
    )
    digest = hashlib.sha256()
    for filename, audio_sha256 in file_hashes:
        digest.update(filename.encode("utf-8"))
        digest.update(b"\0")
        digest.update(audio_sha256.encode("ascii"))
        digest.update(b"\n")
    return provenance, {
        "human_source_manifest_sha256": _BASE.sha256(source_manifest_path),
        "human_augmented_positive_index_sha256": digest.hexdigest(),
        "human_augmented_positive_files": len(file_hashes),
        "human_source_speakers": len(
            {str(value["human_speaker_group"]) for value in provenance.values()}
        ),
    }


def controlled_records(
    manifest: dict[str, object],
    *,
    positive_provenance: dict[str, dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    records = manifest.get("records")
    counts = manifest.get("counts")
    physical_path = manifest.get("physicalPath")
    if (
        manifest.get("schema") != "baxy.controlled-physical-wake-corpus.v1"
        or manifest.get("blindHumanPartitionAccessed") is not False
        or manifest.get("developmentOnly") is not True
        or not isinstance(records, list)
        or not isinstance(counts, dict)
        or not isinstance(physical_path, dict)
        or physical_path.get("captureTransport") != "wasapi_raw_iaudioclient2"
    ):
        raise ValueError("controlled_raw_runtime_logmel_boundary_invalid")
    result: list[dict[str, object]] = []
    observed = {"positive": 0, "negative": 0}
    for record in records:
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("recordId"), str)
            or not isinstance(record.get("sourceSha256"), str)
            or not isinstance(record.get("output"), str)
            or not isinstance(record.get("outputSha256"), str)
        ):
            raise ValueError("controlled_raw_runtime_logmel_record_invalid")
        record_id = str(record["recordId"])
        source_label = record_id.split("/", 1)[0]
        if source_label not in observed:
            raise ValueError("controlled_raw_runtime_logmel_label_invalid")
        observed[source_label] += 1
        source_sha256 = str(record["sourceSha256"]).lower()
        human = None
        if source_label == "positive" and positive_provenance is not None:
            human = positive_provenance.get(source_sha256)
            if human is None:
                raise ValueError(
                    "controlled_raw_runtime_logmel_human_provenance_missing"
                )
        result.append(
            {
                "label": (
                    "positive"
                    if source_label == "positive"
                    else "adversarial_negative"
                ),
                "persona_id": (
                    f"controlled_source_{source_sha256[:16]}"
                    if human is None
                    else human["persona_id"]
                ),
                "record_id": record_id,
                "source_audio_sha256": source_sha256,
                "relative_path": record["output"],
                "audio_sha256": str(record["outputSha256"]).lower(),
                "captured_snr_db": record.get("capturedSnrDb"),
                "path_correlation": record.get("pathCorrelation"),
                **({} if human is None else human),
            }
        )
    expected = {
        label: int(counts.get(label, -1)) for label in ("positive", "negative")
    }
    if observed != expected:
        raise ValueError("controlled_raw_runtime_logmel_counts_invalid")
    return result


def positive_window_evidence(
    report: dict[str, object], *, corpus_manifest_sha256: str
) -> dict[str, int]:
    positive = report.get("positive")
    schema = report.get("schema")
    if (
        schema
        not in {
            "baxy.raw-rolling-multialias-wake-corpus-development.v2",
            "baxy.wake-cascade-runtime-raw-development.v1",
        }
        or report.get("corpusManifestSha256") != corpus_manifest_sha256
        or report.get("blindHumanPartitionAccessed") is not False
        or not isinstance(positive, dict)
        or not isinstance(positive.get("records"), list)
    ):
        raise ValueError("controlled_raw_runtime_logmel_evidence_boundary_invalid")
    result: dict[str, int] = {}
    for record in positive["records"]:
        if not isinstance(record, dict) or not isinstance(
            record.get("audioSha256"), str
        ):
            raise ValueError("controlled_raw_runtime_logmel_evidence_record_invalid")
        if schema == "baxy.raw-rolling-multialias-wake-corpus-development.v2":
            if record.get("accepted") is not True or not isinstance(
                record.get("firstAcceptedWindowIndex"), int
            ):
                raise ValueError(
                    "controlled_raw_runtime_logmel_evidence_record_invalid"
                )
            window_index = int(record["firstAcceptedWindowIndex"])
        else:
            available = record.get("candidateAvailableAtStreamSeconds")
            if record.get("upstreamCandidate") is not True or not isinstance(
                available, (int, float)
            ):
                raise ValueError(
                    "controlled_raw_runtime_logmel_evidence_record_invalid"
                )
            start_samples = max(
                0, round(float(available) * _RUNTIME.SAMPLE_RATE) - _RUNTIME.WINDOW_SAMPLES
            )
            window_index = round(start_samples / _RUNTIME.HOP_SAMPLES)
        result[str(record["audioSha256"]).lower()] = window_index
    return result


def extract(
    *,
    physical_manifest_path: Path,
    positive_window_report_path: Path | None,
    human_source_manifest_path: Path | None,
    human_augmented_positive_directory: Path | None,
    hyperspotter_site_packages: Path,
    output_directory: Path,
) -> dict[str, object]:
    physical_manifest_path = physical_manifest_path.resolve(strict=True)
    hyperspotter_site_packages = hyperspotter_site_packages.resolve(strict=True)
    output_directory = output_directory.resolve()
    partial = output_directory.with_name(output_directory.name + ".partial")
    if output_directory.exists() or partial.exists():
        raise FileExistsError("controlled_raw_runtime_logmel_output_exists")
    manifest = _BASE.read_object(physical_manifest_path)
    if (human_source_manifest_path is None) != (
        human_augmented_positive_directory is None
    ):
        raise ValueError("controlled_raw_runtime_logmel_human_arguments_invalid")
    human_sources: dict[str, object] = {}
    positive_provenance = None
    if human_source_manifest_path is not None:
        positive_provenance, human_sources = load_human_positive_provenance(
            human_source_manifest_path,
            human_augmented_positive_directory,
        )
    source_records = controlled_records(
        manifest, positive_provenance=positive_provenance
    )
    selected_positive_windows: dict[str, int] | None = None
    if positive_window_report_path is not None:
        positive_window_report_path = positive_window_report_path.resolve(strict=True)
        selected_positive_windows = positive_window_evidence(
            _BASE.read_object(positive_window_report_path),
            corpus_manifest_sha256=_BASE.sha256(physical_manifest_path),
        )

    import torch
    import soundfile as sf

    while str(hyperspotter_site_packages) in sys.path:
        sys.path.remove(str(hyperspotter_site_packages))
    sys.path.insert(0, str(hyperspotter_site_packages))
    importlib.invalidate_caches()
    import whisper

    started = time.perf_counter()
    arrays: list[np.ndarray] = []
    records: list[dict[str, object]] = []
    for source_record in source_records:
        path = (
            physical_manifest_path.parent / str(source_record["relative_path"])
        ).resolve(strict=True)
        if _BASE.sha256(path) != source_record["audio_sha256"]:
            raise ValueError("controlled_raw_runtime_logmel_audio_hash_mismatch")
        waveform, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
        if sample_rate != _RUNTIME.SAMPLE_RATE or waveform.shape[1] != 1:
            raise ValueError("controlled_raw_runtime_logmel_wave_invalid")
        windows = _RUNTIME.continuous_runtime_windows(waveform[:, 0])
        for window_index, (window_start, window) in enumerate(windows):
            if source_record["label"] == "positive" and selected_positive_windows is not None:
                selected = selected_positive_windows.get(str(source_record["audio_sha256"]))
                if selected is None:
                    raise ValueError("controlled_raw_runtime_logmel_positive_evidence_missing")
                if window_index != selected:
                    continue
            feature = (
                whisper.log_mel_spectrogram(
                    torch.from_numpy(window), n_mels=_RUNTIME.MEL_BINS
                )
                .transpose(0, 1)
                .contiguous()
                .cpu()
                .numpy()
                .astype(np.float32)
            )
            if feature.shape != (300, _RUNTIME.MEL_BINS):
                raise ValueError("controlled_raw_runtime_logmel_feature_invalid")
            arrays.append(feature)
            records.append(
                {
                    **source_record,
                    "runtime_window_index": window_index,
                    "runtime_window_start_samples": window_start,
                }
            )

    offsets = np.arange(len(records) + 1, dtype=np.int64) * 300
    partial.mkdir(parents=True)
    feature_path = partial / "logmel.f16.npy"
    offset_path = partial / "offsets.i64.npy"
    features = np.lib.format.open_memmap(
        feature_path,
        mode="w+",
        dtype=np.float16,
        shape=(int(offsets[-1]), _RUNTIME.MEL_BINS),
    )
    for index, value in enumerate(arrays):
        features[offsets[index] : offsets[index + 1]] = value.astype(np.float16)
    features.flush()
    del features, arrays
    np.save(offset_path, offsets)
    output_records = [
        {
            **record,
            "feature_start": int(offsets[index]),
            "feature_end": int(offsets[index + 1]),
            "feature_frames": 300,
        }
        for index, record in enumerate(records)
    ]
    report: dict[str, object] = {
        "schema": "baxy.controlled-raw-runtime-logmel.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "physical_manifest_sha256": _BASE.sha256(physical_manifest_path),
            "positive_window_report_sha256": (
                None
                if positive_window_report_path is None
                else _BASE.sha256(positive_window_report_path)
            ),
            **human_sources,
        },
        "contract": {
            "role": "opened_development_training_only",
            "sample_rate": _RUNTIME.SAMPLE_RATE,
            "mel_bins": _RUNTIME.MEL_BINS,
            "runtime_window_samples": _RUNTIME.WINDOW_SAMPLES,
            "side_padding_samples": _RUNTIME.SIDE_PADDING_SAMPLES,
            "hop_samples": _RUNTIME.HOP_SAMPLES,
            "filenames_or_transcripts_retained": False,
            "positive_window_selection": (
                "all_runtime_windows"
                if selected_positive_windows is None
                else "first_consensus_window_from_frozen_development_gate"
            ),
        },
        "counts": {
            "positive": sum(record["label"] == "positive" for record in records),
            "adversarial_negative": sum(
                record["label"] == "adversarial_negative" for record in records
            ),
            "source_records": len(source_records),
            "records": len(records),
            "frames": int(offsets[-1]),
        },
        "files": {
            "logmel": feature_path.name,
            "logmel_sha256": _BASE.sha256(feature_path),
            "offsets": offset_path.name,
            "offsets_sha256": _BASE.sha256(offset_path),
        },
        "records": output_records,
        "runtime_seconds": time.perf_counter() - started,
        "human_development_audio_accessed": positive_provenance is not None,
        "blind_human_audio_accessed": False,
        "development_only": True,
        "effects_executed": 0,
    }
    (partial / "features.manifest.v1.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    partial.rename(output_directory)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-manifest", type=Path, required=True)
    parser.add_argument("--positive-window-report", type=Path)
    parser.add_argument("--human-source-manifest", type=Path)
    parser.add_argument("--human-augmented-positive-directory", type=Path)
    parser.add_argument("--hyperspotter-site-packages", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = extract(
        physical_manifest_path=arguments.physical_manifest,
        positive_window_report_path=arguments.positive_window_report,
        human_source_manifest_path=arguments.human_source_manifest,
        human_augmented_positive_directory=(
            arguments.human_augmented_positive_directory
        ),
        hyperspotter_site_packages=arguments.hyperspotter_site_packages,
        output_directory=arguments.output_directory,
    )
    print(json.dumps(report["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
