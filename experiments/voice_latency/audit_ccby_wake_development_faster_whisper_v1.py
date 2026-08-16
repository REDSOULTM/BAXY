"""Audit Faster-Whisper lexical evidence on the human development partition."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from baxy_mind.wake_verifier import has_exact_lexical_target  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(root: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        raise ValueError("faster_whisper_model_tree_empty")
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256(path)))
    return digest.hexdigest()


def select_development_records(corpus: dict[str, object]) -> list[dict[str, object]]:
    if (
        corpus.get("schema") != "baxy.ccby-wake-holdout-corpus.v1"
        or corpus.get("blind_partition_was_not_scored") is not True
    ):
        raise ValueError("faster_whisper_wake_development_boundary_invalid")
    records = [
        record
        for record in corpus.get("records", [])
        if isinstance(record, dict) and record.get("partition") == "development"
    ]
    if len(records) != 18:
        raise ValueError("faster_whisper_wake_development_records_invalid")
    return records


def summarize(records: list[dict[str, object]]) -> dict[str, object]:
    positives = [record for record in records if record["label"] == "positive"]
    negatives = [
        record for record in records if record["label"] == "hard_negative"
    ]
    accepted = sum(bool(record["exact_lexical_target"]) for record in positives)
    false = sum(bool(record["exact_lexical_target"]) for record in negatives)
    return {
        "positive_exact_lexical": accepted,
        "positive_total": len(positives),
        "positive_exact_lexical_rate": accepted / len(positives),
        "hard_negative_exact_lexical_false": false,
        "hard_negative_total": len(negatives),
        "diagnostic_zero_false": false == 0,
    }


def audit(
    *,
    corpus_manifest_path: Path,
    model_path: Path,
    output_path: Path,
    cpu_threads: int,
    device: str,
    compute_type: str,
    runtime_dll_directory: Path | None,
) -> dict[str, object]:
    if output_path.exists():
        raise ValueError("faster_whisper_wake_output_exists")
    if cpu_threads < 1:
        raise ValueError("faster_whisper_cpu_threads_invalid")
    if device not in {"cpu", "cuda"}:
        raise ValueError("faster_whisper_device_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    model_path = model_path.resolve(strict=True)
    output_path = output_path.resolve()
    for name in ("config.json", "model.bin", "tokenizer.json"):
        if not (model_path / name).is_file():
            raise ValueError(f"faster_whisper_model_file_missing:{name}")
    corpus = json.loads(corpus_manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(corpus, dict):
        raise ValueError("faster_whisper_wake_corpus_invalid")
    source_records = select_development_records(corpus)

    dll_hashes: dict[str, str] = {}
    dll_handle = None
    if runtime_dll_directory is not None:
        runtime_dll_directory = runtime_dll_directory.resolve(strict=True)
        if not runtime_dll_directory.is_dir():
            raise ValueError("faster_whisper_runtime_dll_directory_invalid")
        dll_handle = os.add_dll_directory(str(runtime_dll_directory))
        os.environ["PATH"] = str(runtime_dll_directory) + os.pathsep + os.environ.get(
            "PATH", ""
        )
        for pattern in ("cublas*.dll", "cudnn*.dll", "cudart*.dll"):
            for path in sorted(runtime_dll_directory.glob(pattern)):
                dll_hashes[path.name] = sha256(path)
        if device == "cuda" and not dll_hashes:
            raise ValueError("faster_whisper_cuda_runtime_dlls_missing")
    os.environ["OMP_NUM_THREADS"] = str(cpu_threads)
    from faster_whisper import WhisperModel
    import ctranslate2

    model = WhisperModel(
        str(model_path),
        device=device,
        compute_type=compute_type,
        cpu_threads=cpu_threads,
        local_files_only=True,
    )
    corpus_root = corpus_manifest_path.parent
    records: list[dict[str, object]] = []
    started = time.perf_counter()
    for source in source_records:
        path = corpus_root / str(source["output_relative_path"])
        wav = source.get("wav")
        if not isinstance(wav, dict) or sha256(path) != wav.get("sha256"):
            raise ValueError(f"faster_whisper_wake_audio_hash_mismatch:{path}")
        segments, info = model.transcribe(
            str(path),
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=False,
            without_timestamps=True,
        )
        transcript = " ".join(segment.text.strip() for segment in segments).strip()
        records.append(
            {
                "relative_path": source["output_relative_path"],
                "speaker_group": source["speaker_group"],
                "label": source["label"],
                "language": info.language,
                "language_probability": info.language_probability,
                "transcript": transcript,
                "exact_lexical_target": has_exact_lexical_target(transcript),
            }
        )
    report: dict[str, object] = {
        "schema": "baxy.ccby-wake-development-faster-whisper-audit.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_diagnostic",
        "sources": {
            "corpus_manifest_sha256": sha256(corpus_manifest_path),
            "model_tree_sha256": sha256_tree(model_path),
            "model_bin_sha256": sha256(model_path / "model.bin"),
        },
        "dependencies": {
            "faster_whisper": version("faster-whisper"),
            "ctranslate2": version("ctranslate2"),
            "av": version("av"),
            "cuda_device_count": ctranslate2.get_cuda_device_count(),
            "runtime_dll_sha256": dll_hashes,
        },
        "inference": {
            "device": device,
            "compute_type": compute_type,
            "cpu_threads": cpu_threads,
            "beam_size": 1,
            "best_of": 1,
            "temperature": 0.0,
            "condition_on_previous_text": False,
            "vad_filter": False,
            "without_timestamps": True,
            "initial_prompt": None,
            "hotwords": None,
        },
        "metrics": summarize(records),
        "records": records,
        "runtime_seconds": time.perf_counter() - started,
        "candidate_frozen": False,
        "product_operating_point": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if dll_handle is not None:
        dll_handle.close()
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu-threads", type=int, default=8)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--runtime-dll-directory", type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = audit(
        corpus_manifest_path=arguments.corpus_manifest,
        model_path=arguments.model,
        output_path=arguments.output,
        cpu_threads=arguments.cpu_threads,
        device=arguments.device,
        compute_type=arguments.compute_type,
        runtime_dll_directory=arguments.runtime_dll_directory,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
