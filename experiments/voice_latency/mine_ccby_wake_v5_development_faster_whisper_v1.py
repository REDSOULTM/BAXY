"""Mine lexical wake candidates from preregistered CC-BY development audio."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))
from audit_ccby_wake_development_faster_whisper_v1 import (  # noqa: E402
    sha256,
    sha256_tree,
)
from baxy_mind.wake_verifier import (  # noqa: E402
    has_exact_lexical_target,
    has_liberal_lexical_proposal,
)


ALLOWED_LICENSE = "Creative Commons Attribution license (reuse allowed)"
CONSUMED_BLIND_SOURCE_IDS = frozenset(
    {"ix-oaNUxFSA", "mwSFvsMnBRE", "gcSAZ2eLlZ4", "LaTRmCVcsDY"}
)


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"wake_v5_mining_json_invalid:{path}")
    return value


def select_sources(
    spec: dict[str, object], inventories: dict[str, dict[str, object]]
) -> list[tuple[str, dict[str, object]]]:
    if (
        spec.get("schema") != "baxy.ccby-wake-v5-development-sources.v1"
        or spec.get("scope") != "development_only"
    ):
        raise ValueError("wake_v5_mining_spec_invalid")
    excluded = set(spec.get("excluded_consumed_blind_source_ids", []))
    if excluded != CONSUMED_BLIND_SOURCE_IDS:
        raise ValueError("wake_v5_mining_blind_exclusion_invalid")
    source_entries = spec.get("sources")
    if not isinstance(source_entries, list) or not source_entries:
        raise ValueError("wake_v5_mining_sources_missing")
    selected: list[tuple[str, dict[str, object]]] = []
    seen: set[str] = set()
    for entry in source_entries:
        if not isinstance(entry, dict):
            raise ValueError("wake_v5_mining_source_entry_invalid")
        inventory_name = str(entry.get("inventory", ""))
        source_id = str(entry.get("id", ""))
        if source_id in CONSUMED_BLIND_SOURCE_IDS or source_id in seen:
            raise ValueError(f"wake_v5_mining_source_boundary_invalid:{source_id}")
        inventory = inventories.get(inventory_name)
        if inventory is None:
            raise ValueError(f"wake_v5_mining_inventory_missing:{inventory_name}")
        matches = [
            source
            for source in inventory.get("sources", [])
            if isinstance(source, dict) and source.get("id") == source_id
        ]
        if len(matches) != 1:
            raise ValueError(f"wake_v5_mining_source_missing:{source_id}")
        source = matches[0]
        if source.get("license") != ALLOWED_LICENSE:
            raise ValueError(f"wake_v5_mining_license_invalid:{source_id}")
        selected.append((inventory_name, source))
        seen.add(source_id)
    return selected


def is_lexical_candidate(text: str) -> bool:
    return has_exact_lexical_target(text) or has_liberal_lexical_proposal(text)


def mine(
    *,
    spec_path: Path,
    inventory_paths: dict[str, Path],
    model_path: Path,
    runtime_dll_directory: Path,
    output_path: Path,
    cpu_threads: int,
) -> dict[str, object]:
    if output_path.exists() or cpu_threads < 1:
        raise ValueError("wake_v5_mining_schedule_invalid")
    spec_path = spec_path.resolve(strict=True)
    model_path = model_path.resolve(strict=True)
    runtime_dll_directory = runtime_dll_directory.resolve(strict=True)
    output_path = output_path.resolve()
    inventory_paths = {
        name: path.resolve(strict=True) for name, path in inventory_paths.items()
    }
    spec = read_object(spec_path)
    expected_hashes = spec.get("inventory_sha256")
    if not isinstance(expected_hashes, dict):
        raise ValueError("wake_v5_mining_inventory_hashes_missing")
    for name, path in inventory_paths.items():
        if sha256(path) != expected_hashes.get(name):
            raise ValueError(f"wake_v5_mining_inventory_hash_mismatch:{name}")
    inventories = {name: read_object(path) for name, path in inventory_paths.items()}
    selected = select_sources(spec, inventories)

    dll_handle = os.add_dll_directory(str(runtime_dll_directory))
    os.environ["PATH"] = str(runtime_dll_directory) + os.pathsep + os.environ.get(
        "PATH", ""
    )
    os.environ["OMP_NUM_THREADS"] = str(cpu_threads)
    import ctranslate2
    from faster_whisper import WhisperModel
    from importlib.metadata import version

    model = WhisperModel(
        str(model_path),
        device="cuda",
        compute_type="float16",
        cpu_threads=cpu_threads,
        local_files_only=True,
    )
    records: list[dict[str, object]] = []
    started = time.perf_counter()
    total_audio_seconds = 0.0
    candidate_count = 0
    for inventory_name, source in selected:
        inventory_root = inventory_paths[inventory_name].parent
        audio_path = inventory_root / str(source["audio_file"])
        if sha256(audio_path) != source.get("audio_sha256"):
            raise ValueError(f"wake_v5_mining_audio_hash_mismatch:{source['id']}")
        segments_generator, info = model.transcribe(
            str(audio_path),
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=True,
            word_timestamps=True,
            without_timestamps=False,
            initial_prompt=None,
            hotwords=None,
        )
        segments = []
        candidates = []
        for index, segment in enumerate(segments_generator):
            text = segment.text.strip()
            item = {
                "index": index,
                "start_seconds": float(segment.start),
                "end_seconds": float(segment.end),
                "text": text,
                "words": [
                    {
                        "start_seconds": float(word.start),
                        "end_seconds": float(word.end),
                        "word": word.word,
                        "probability": float(word.probability),
                    }
                    for word in (segment.words or [])
                ],
            }
            segments.append(item)
            if is_lexical_candidate(text):
                candidates.append(item)
        candidate_count += len(candidates)
        total_audio_seconds += float(source["audio_seconds"])
        records.append(
            {
                "source_id": source["id"],
                "title": source["title"],
                "uploader": source["uploader"],
                "license": source["license"],
                "webpage_url": source["webpage_url"],
                "audio_file": source["audio_file"],
                "audio_sha256": source["audio_sha256"],
                "audio_seconds": source["audio_seconds"],
                "language": info.language,
                "language_probability": float(info.language_probability),
                "segments": segments,
                "lexical_candidates": candidates,
            }
        )
    report: dict[str, object] = {
        "schema": "baxy.ccby-wake-v5-development-faster-whisper-mining.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_data_mining",
        "sources": {
            "spec_sha256": sha256(spec_path),
            "inventory_sha256": {
                name: sha256(path) for name, path in inventory_paths.items()
            },
            "model_tree_sha256": sha256_tree(model_path),
            "model_bin_sha256": sha256(model_path / "model.bin"),
        },
        "dependencies": {
            "faster_whisper": version("faster-whisper"),
            "ctranslate2": version("ctranslate2"),
            "av": version("av"),
            "cuda_device_count": ctranslate2.get_cuda_device_count(),
        },
        "inference": {
            "device": "cuda",
            "compute_type": "float16",
            "beam_size": 1,
            "best_of": 1,
            "temperature": 0.0,
            "condition_on_previous_text": False,
            "vad_filter": True,
            "word_timestamps": True,
            "initial_prompt": None,
            "hotwords": None,
        },
        "metrics": {
            "source_count": len(records),
            "audio_seconds": total_audio_seconds,
            "lexical_candidate_segments": candidate_count,
            "sources_with_lexical_candidates": sum(
                bool(record["lexical_candidates"]) for record in records
            ),
        },
        "records": records,
        "runtime_seconds": time.perf_counter() - started,
        "candidate_model_scores_accessed": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    dll_handle.close()
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--round1-inventory", type=Path, required=True)
    parser.add_argument("--round2-inventory", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--runtime-dll-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu-threads", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = mine(
        spec_path=arguments.spec,
        inventory_paths={
            "round1": arguments.round1_inventory,
            "round2": arguments.round2_inventory,
        },
        model_path=arguments.model,
        runtime_dll_directory=arguments.runtime_dll_directory,
        output_path=arguments.output,
        cpu_threads=arguments.cpu_threads,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
