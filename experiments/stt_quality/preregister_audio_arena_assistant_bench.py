"""Freeze an unread real-audio STT partition from Audio Arena Assistant Bench.

This generator deliberately never opens ``metadata.jsonl`` or the benchmark
turn definitions: those files contain the reference transcripts.  It reads
only paths, WAV headers, hashes, Git provenance, and speaker/environment
metadata.  The selected audio remains unavailable to BAXY models until a
separate versioned evaluator has been preregistered.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import wave
from pathlib import Path


SCHEMA = "baxy.stt-real-audio-preregistration.v1"
SOURCE_COMMIT = "7d8464ca6a73b490f23be0a51feb3cb3656cc107"
SOURCE_COMMIT_AT_UTC = "2026-03-24T05:11:19Z"
PARAKEET_REPOSITORY_CREATED_AT_UTC = "2025-08-04T13:34:09.000Z"
PARAKEET_LOCAL_ASSET_TIMESTAMP_UTC = "2025-08-16T09:28:03Z"
EXCLUDED_TURN_IDS = tuple(range(0, 6))
RESERVED_TURN_IDS = tuple(range(6, 31))
EXPECTED_SPEAKERS = ("person1", "person2")
EXPECTED_FORMAT = {
    "channels": 1,
    "bitsPerSample": 16,
    "sampleRateHz": 24000,
    "compression": "NONE",
}
# Re-sealed against the current tree; this benchmark has never been opened.
# See audit_fresh_postweight_stt_sources.py for the full lineage.
EXPECTED_PROGRAM_TREE_SHA256 = (
    "f83a369c92a4a0af73dffc83b4d3a38f50552bd2c341a44d53ccb813c7929900"
)
TURN_PATTERN = re.compile(r"turn_(\d{3})\.wav\Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(source_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source_root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _manifest_sha256(records: list[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: str(item["path"])):
        digest.update(str(record["path"]).encode("utf-8"))
        digest.update(b"\n")
        digest.update(str(record["sha256"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _program_tree(repository_root: Path) -> dict[str, object]:
    roots = (
        repository_root / "experiments" / "voice_latency",
        repository_root / "scripts",
        repository_root / "src" / "baxy_mind",
    )
    files: dict[str, Path] = {}
    for root in roots:
        for path in root.rglob("*.py"):
            if path.is_file() and not path.is_symlink():
                files[path.relative_to(repository_root).as_posix()] = path
    digest = hashlib.sha256()
    for relative in sorted(files):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\n")
        digest.update(_sha256(files[relative]).encode("ascii"))
        digest.update(b"\n")
    result = {
        "schema": "baxy.wake-validation-program-tree.v1",
        "roots": [
            "experiments/voice_latency",
            "scripts",
            "src/baxy_mind",
        ],
        "pythonFiles": len(files),
        "sha256": digest.hexdigest(),
    }
    if result["sha256"] != EXPECTED_PROGRAM_TREE_SHA256:
        raise RuntimeError("wake_program_tree_changed")
    return result


def _wav_record(source_root: Path, path: Path) -> dict[str, object]:
    match = TURN_PATTERN.fullmatch(path.name)
    if match is None:
        raise RuntimeError(f"unexpected_audio_name:{path.name}")
    with wave.open(str(path), "rb") as audio:
        record = {
            "path": path.relative_to(source_root).as_posix(),
            "speaker": path.parent.name,
            "turnId": int(match.group(1)),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "durationSeconds": round(audio.getnframes() / audio.getframerate(), 6),
            "channels": audio.getnchannels(),
            "bitsPerSample": audio.getsampwidth() * 8,
            "sampleRateHz": audio.getframerate(),
            "compression": audio.getcomptype(),
        }
    for field, expected in EXPECTED_FORMAT.items():
        if record[field] != expected:
            raise RuntimeError(f"unexpected_audio_format:{record['path']}:{field}")
    return record


def build_receipt(
    *, repository_root: Path, source_root: Path, preregistered_at_utc: str
) -> dict[str, object]:
    repository_root = repository_root.resolve(strict=True)
    source_root = source_root.resolve(strict=True)
    if _git(source_root, "rev-parse", "HEAD") != SOURCE_COMMIT:
        raise RuntimeError("assistant_bench_source_commit_changed")
    if _git(source_root, "status", "--porcelain"):
        raise RuntimeError("assistant_bench_source_tree_dirty")

    all_records = [
        _wav_record(source_root, path)
        for speaker in EXPECTED_SPEAKERS
        for path in sorted((source_root / "real_audio" / speaker).glob("*.wav"))
    ]
    if len(all_records) != 62:
        raise RuntimeError("assistant_bench_real_audio_count_changed")
    selected = [
        record for record in all_records if record["turnId"] in RESERVED_TURN_IDS
    ]
    excluded = [
        record for record in all_records if record["turnId"] in EXCLUDED_TURN_IDS
    ]
    if len(selected) != 50 or len(excluded) != 12:
        raise RuntimeError("assistant_bench_partition_count_changed")

    speaker_metadata: dict[str, object] = {}
    for speaker in EXPECTED_SPEAKERS:
        path = source_root / "real_audio" / speaker / "recording_metadata.json"
        speaker_metadata[speaker] = {
            "sha256": _sha256(path),
            "metadata": json.loads(path.read_text(encoding="utf-8")),
        }

    return {
        "schema": SCHEMA,
        "preregisteredAtUtc": preregistered_at_utc,
        "generator": {
            "path": Path(__file__).resolve().relative_to(repository_root).as_posix(),
            "sha256": _sha256(Path(__file__).resolve()),
        },
        "role": "temporally_disjoint_unopened_real_english_stt_holdout_component",
        "evaluationStatus": "unopened",
        "modelAudioDecoded": False,
        "referenceTranscriptsReadForReservedTurns": False,
        "corpusSelectionFrozen": True,
        "source": {
            "name": "Audio Arena Assistant Bench",
            "publisher": "Arcada Labs",
            "repository": "https://huggingface.co/datasets/arcada-labs/assistant-bench",
            "upstream": "https://github.com/Design-Arena/audio-arena-bench",
            "license": "MIT",
            "language": "en",
            "commit": SOURCE_COMMIT,
            "commitAtUtc": SOURCE_COMMIT_AT_UTC,
            "localRoot": source_root.as_posix(),
            "gitTreeClean": True,
        },
        "speakerAndEnvironmentMetadata": speaker_metadata,
        "structuralAudit": {
            "realAudioFiles": len(all_records),
            "bytes": sum(int(record["bytes"]) for record in all_records),
            "durationSeconds": round(
                sum(float(record["durationSeconds"]) for record in all_records), 6
            ),
            "audioManifestSha256": _manifest_sha256(all_records),
            "format": EXPECTED_FORMAT,
            "audioPayloadDecodedByBaxyModel": False,
            "wavHeadersRead": True,
        },
        "selection": {
            "rule": "both human speakers, turn IDs 006 through 030 inclusive",
            "excludedBecauseReferenceTextWasInspectedInThisCampaign": list(
                EXCLUDED_TURN_IDS
            ),
            "reservedTurnIds": list(RESERVED_TURN_IDS),
            "reservedFiles": len(selected),
            "reservedDurationSeconds": round(
                sum(float(record["durationSeconds"]) for record in selected), 6
            ),
            "reservedManifestSha256": _manifest_sha256(selected),
            "records": selected,
        },
        "modelContaminationAudit": {
            "runtimeFinalAsr": "nvidia/parakeet-tdt-0.6b-v3-int8 via sherpa-onnx",
            "officialModelCard": "https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3",
            "modelRepositoryCreatedAtUtc": PARAKEET_REPOSITORY_CREATED_AT_UTC,
            "localConvertedAssetTimestampUtc": PARAKEET_LOCAL_ASSET_TIMESTAMP_UTC,
            "datasetCommitAtUtc": SOURCE_COMMIT_AT_UTC,
            "datasetPostdatesFrozenModelWeights": True,
            "audioArenaListedInOfficialTrainingDatasets": False,
            "audioArenaListedInOfficialEvaluationDatasets": False,
            "priorBaxyRepositoryOrArtifactReferencesFoundBeforePreregistration": False,
            "eligibleAsBlindEnglishSttEvidence": True,
            "sufficientAloneForFinalMultilingualSttCertification": False,
        },
        "evaluationContract": {
            "reservedAudioMayNotBeUsedForTrainingOrTuning": True,
            "reservedReferenceTextMayBeOpenedOnlyByVersionedEvaluator": True,
            "developmentFailuresMayNotTuneOnReservedRows": True,
            "wakeValidationPartitionMayNotBeUsed": True,
            "requiredMetrics": [
                "word_error_rate_by_speaker",
                "semantic_operation_preservation",
                "entity_date_time_number_and_spelling_preservation",
                "stt_latency_p50_p95",
            ],
            "requiredPass": {
                "semanticOperationPreservation": 1.0,
                "criticalEntityPreservation": 1.0,
                "unsafeEffects": 0,
            },
        },
        "wakeProgramTree": _program_tree(repository_root),
        "effectsExecuted": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--preregistered-at-utc", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    receipt = build_receipt(
        repository_root=arguments.repository_root,
        source_root=arguments.source_root,
        preregistered_at_utc=arguments.preregistered_at_utc,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(arguments.output),
                "reservedFiles": receipt["selection"]["reservedFiles"],
                "reservedManifestSha256": receipt["selection"][
                    "reservedManifestSha256"
                ],
                "programTreeSha256": receipt["wakeProgramTree"]["sha256"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
