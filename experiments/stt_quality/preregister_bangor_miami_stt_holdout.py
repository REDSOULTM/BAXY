"""Freeze Bangor Miami STT partitions without inspecting reference text.

The acquired mirror is incomplete, so this generator never presents it as the
canonical 56-recording corpus.  It validates the three acquired files, reads
only WebVTT NOTE/timestamp lines, excludes materially overlapping cues, and
selects recording-disjoint development and blind partitions.  Cue text and MP3
audio remain unopened by BAXY models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


SCHEMA = "baxy.stt-natural-codeswitch-preregistration.v1"
SOURCE_COMMIT = "2ff0591ffe0fd8eaef40d5f3c681826a144fb5d7"
SEED = 20260811
SEGMENTS_PER_RECORDING = 12
MIN_DURATION_MS = 1500
MAX_DURATION_MS = 12000
MAX_OTHER_SPEECH_OVERLAP_MS = 100
EXPECTED_FILES = {
    "miamiCorpus_merged.mp3": {
        "bytes": 531928129,
        "sha256": "b1fececb6976721a8f9e6cad2eae67161fe7321cf53bd2ed179a9d0f6db2e086",
    },
    "miamiCorpus_merged.vtt": {
        "bytes": 635315,
        "sha256": "0fcfbdef4c6e8155be2a8d49da834558762af0dbfe76bfeabe00f22ee7ef0212",
    },
    "README.md": {
        "bytes": 3689,
        "sha256": "2cfe2b8d3917fc4f9a8d8026ee0914644b55f314289e5cfc87d9042652e1f530",
    },
}
EXPECTED_RECORDINGS = {
    "herring10",
    "herring13",
    "herring3",
    "herring6",
    "herring7",
    "herring8",
    "sastre1",
    "sastre8",
    "sastre9",
    "zeledon14",
    "zeledon5",
    "zeledon9",
}
BLIND_COUNTS_BY_GROUP = {"herring": 4, "sastre": 2, "zeledon": 2}
# Re-sealed against the current tree; this holdout has never been opened.
# See audit_fresh_postweight_stt_sources.py for the full lineage.
EXPECTED_PROGRAM_TREE_SHA256 = (
    "45b27ee3ecf5fbfb91f24e96853c6f6b34fcce1202b63733d6552023f082893e"
)
NOTE_PATTERN = re.compile(
    r"^NOTE\s+(?P<recording>\S+)\s+offset=(?P<offset>\d\d:\d\d:\d\d\.\d{3})"
    r"\s+duration=(?P<duration>\d+(?:\.\d+)?)s$"
)
TIMESTAMP_PATTERN = re.compile(
    r"^(?P<start>\d\d:\d\d:\d\d\.\d{3})\s+-->\s+"
    r"(?P<end>\d\d:\d\d:\d\d\.\d{3})$"
)
GROUP_PATTERN = re.compile(r"^[a-z]+")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_score(label: str) -> str:
    return hashlib.sha256(f"{SEED}:{label}".encode()).hexdigest()


def _timestamp_ms(value: str) -> int:
    hours, minutes, seconds = value.split(":")
    whole_seconds, milliseconds = seconds.split(".")
    return (
        int(hours) * 3_600_000
        + int(minutes) * 60_000
        + int(whole_seconds) * 1000
        + int(milliseconds)
    )


def _manifest_sha256(records: list[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    for record in sorted(
        records,
        key=lambda item: (
            str(item["recordingId"]),
            int(item["cueOrdinal"]),
        ),
    ):
        canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
        digest.update(canonical.encode("utf-8"))
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


def _parse_structure(vtt_path: Path) -> dict[str, dict[str, object]]:
    recordings: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    with vtt_path.open("r", encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.rstrip("\r\n")
            note = NOTE_PATTERN.fullmatch(line)
            if note is not None:
                recording_id = note.group("recording")
                if recording_id in recordings:
                    raise RuntimeError(f"duplicate_recording_note:{recording_id}")
                current = {
                    "recordingId": recording_id,
                    "offsetMs": _timestamp_ms(note.group("offset")),
                    "reportedDurationMs": round(float(note.group("duration")) * 1000),
                    "cues": [],
                }
                recordings[recording_id] = current
                continue
            timestamp = TIMESTAMP_PATTERN.fullmatch(line)
            if timestamp is None:
                continue
            if current is None:
                raise RuntimeError("timestamp_before_recording_note")
            cues = current["cues"]
            if not isinstance(cues, list):
                raise TypeError("invalid_cue_collection")
            cues.append(
                {
                    "cueOrdinal": len(cues),
                    "globalStartMs": _timestamp_ms(timestamp.group("start")),
                    "globalEndMs": _timestamp_ms(timestamp.group("end")),
                }
            )
    if set(recordings) != EXPECTED_RECORDINGS:
        raise RuntimeError("miami_recording_index_changed")
    return recordings


def _isolated_candidates(recording: dict[str, object]) -> list[dict[str, object]]:
    cues = recording["cues"]
    if not isinstance(cues, list):
        raise TypeError("invalid_cue_collection")
    offset_ms = int(recording["offsetMs"])
    candidates: list[dict[str, object]] = []
    for index, cue in enumerate(cues):
        start_ms = int(cue["globalStartMs"])
        end_ms = int(cue["globalEndMs"])
        duration_ms = end_ms - start_ms
        if not MIN_DURATION_MS <= duration_ms <= MAX_DURATION_MS:
            continue
        max_overlap = 0
        for other_index, other in enumerate(cues):
            if index == other_index:
                continue
            overlap = min(end_ms, int(other["globalEndMs"])) - max(
                start_ms, int(other["globalStartMs"])
            )
            max_overlap = max(max_overlap, overlap)
            if max_overlap > MAX_OTHER_SPEECH_OVERLAP_MS:
                break
        if max_overlap > MAX_OTHER_SPEECH_OVERLAP_MS:
            continue
        candidates.append(
            {
                "recordingId": recording["recordingId"],
                "cueOrdinal": cue["cueOrdinal"],
                "globalStartMs": start_ms,
                "globalEndMs": end_ms,
                "relativeStartMs": start_ms - offset_ms,
                "relativeEndMs": end_ms - offset_ms,
                "durationMs": duration_ms,
                "maximumOtherSpeechOverlapMs": max_overlap,
            }
        )
    return candidates


def _recording_partitions(recording_ids: set[str]) -> tuple[list[str], list[str]]:
    blind: list[str] = []
    development: list[str] = []
    for group, blind_count in BLIND_COUNTS_BY_GROUP.items():
        members = sorted(
            (
                recording_id
                for recording_id in recording_ids
                if recording_id.startswith(group)
            ),
            key=lambda recording_id: _stable_score(f"recording:{recording_id}"),
        )
        if len(members) <= blind_count:
            raise RuntimeError(f"insufficient_recordings_for_group:{group}")
        blind.extend(members[:blind_count])
        development.extend(members[blind_count:])
    if set(blind) | set(development) != recording_ids:
        raise RuntimeError("recording_partition_incomplete")
    return sorted(blind), sorted(development)


def _select_segments(
    recordings: dict[str, dict[str, object]], recording_ids: list[str]
) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for recording_id in recording_ids:
        candidates = _isolated_candidates(recordings[recording_id])
        candidates.sort(
            key=lambda cue: _stable_score(
                "cue:"
                f"{cue['recordingId']}:"
                f"{cue['cueOrdinal']}:"
                f"{cue['globalStartMs']}:"
                f"{cue['globalEndMs']}"
            )
        )
        if len(candidates) < SEGMENTS_PER_RECORDING:
            raise RuntimeError(f"insufficient_isolated_cues:{recording_id}")
        selected.extend(candidates[:SEGMENTS_PER_RECORDING])
    return sorted(
        selected,
        key=lambda cue: (str(cue["recordingId"]), int(cue["cueOrdinal"])),
    )


def build_receipt(
    *, repository_root: Path, source_root: Path, preregistered_at_utc: str
) -> dict[str, object]:
    repository_root = repository_root.resolve(strict=True)
    source_root = source_root.resolve(strict=True)
    files: dict[str, object] = {}
    for name, expected in EXPECTED_FILES.items():
        path = source_root / name
        observed = {"bytes": path.stat().st_size, "sha256": _sha256(path)}
        if observed != expected:
            raise RuntimeError(f"miami_source_file_changed:{name}")
        files[name] = observed

    recordings = _parse_structure(source_root / "miamiCorpus_merged.vtt")
    blind_recordings, development_recordings = _recording_partitions(set(recordings))
    blind_segments = _select_segments(recordings, blind_recordings)
    development_segments = _select_segments(recordings, development_recordings)
    if len(blind_segments) != 96 or len(development_segments) != 48:
        raise RuntimeError("miami_segment_partition_count_changed")

    recording_index = []
    for recording_id in sorted(recordings):
        recording = recordings[recording_id]
        recording_index.append(
            {
                "recordingId": recording_id,
                "offsetMs": recording["offsetMs"],
                "reportedDurationMs": recording["reportedDurationMs"],
                "cues": len(recording["cues"]),
                "isolatedCandidates": len(_isolated_candidates(recording)),
            }
        )

    return {
        "schema": SCHEMA,
        "preregisteredAtUtc": preregistered_at_utc,
        "generator": {
            "path": Path(__file__).resolve().relative_to(repository_root).as_posix(),
            "sha256": _sha256(Path(__file__).resolve()),
        },
        "role": "recording_disjoint_unopened_natural_es_en_codeswitch_stt_holdout_component",
        "evaluationStatus": "unopened",
        "modelAudioDecoded": False,
        "referenceTextUsedForSelection": False,
        "corpusSelectionFrozen": True,
        "canonicalSource": {
            "name": "Bangor Miami Spanish-English Corpus",
            "url": "https://talkbank.org/biling/access/Bangor/Miami.html",
            "doi": "10.21415/T5J01D",
            "reportedParticipants": 84,
            "reportedRecordings": 56,
            "reportedHours": 35,
            "license": "GPL-3.0-or-later",
        },
        "retrievalMirror": {
            "repository": "https://huggingface.co/datasets/drewoodward/miami-corpus",
            "commit": SOURCE_COMMIT,
            "canonical": False,
            "complete": False,
            "localRoot": source_root.as_posix(),
            "files": files,
            "observedRecordings": len(recordings),
            "observedCues": sum(
                len(recording["cues"]) for recording in recordings.values()
            ),
            "recordingIndex": recording_index,
        },
        "selection": {
            "seed": SEED,
            "recordingDisjoint": True,
            "blindRecordingCountsByGroup": BLIND_COUNTS_BY_GROUP,
            "blindRecordings": blind_recordings,
            "developmentRecordings": development_recordings,
            "cueFilter": {
                "minimumDurationMs": MIN_DURATION_MS,
                "maximumDurationMs": MAX_DURATION_MS,
                "maximumOtherSpeechOverlapMs": MAX_OTHER_SPEECH_OVERLAP_MS,
                "referenceTextExamined": False,
            },
            "segmentsPerRecording": SEGMENTS_PER_RECORDING,
            "blindSegments": blind_segments,
            "blindSegmentManifestSha256": _manifest_sha256(blind_segments),
            "blindDurationSeconds": round(
                sum(int(segment["durationMs"]) for segment in blind_segments) / 1000,
                3,
            ),
            "developmentSegments": development_segments,
            "developmentSegmentManifestSha256": _manifest_sha256(development_segments),
            "developmentDurationSeconds": round(
                sum(int(segment["durationMs"]) for segment in development_segments)
                / 1000,
                3,
            ),
        },
        "modelContaminationAudit": {
            "runtimeFinalAsr": "nvidia/parakeet-tdt-0.6b-v3-int8 via sherpa-onnx",
            "officialModelCard": "https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3",
            "declaredTrainingSources": [
                "nvidia/Granary: YODAS, YouTube-Commons, VoxPopuli, LibriLight",
                "NeMo ASR Set 3.0: LibriSpeech, Fisher, NSC Part 1, VCTK, Europarl-ASR, MLS, Common Voice 7, AMI",
            ],
            "declaredEvaluationSources": [
                "FLEURS",
                "MLS",
                "CoVoST",
                "Open ASR Leaderboard",
            ],
            "bangorMiamiDeclaredInTrainingOrEvaluationSources": False,
            "eligibleAsBlindSpanishSpanglishCandidate": True,
            "eligibilityRequiresSelectedReferenceCoverageAuditAtEvaluation": True,
            "sufficientAloneForFinalPhysicalSttCertification": False,
        },
        "evaluationContract": {
            "blindAudioMayNotBeUsedForTrainingOrTuning": True,
            "blindReferenceTextMayBeOpenedOnlyByVersionedEvaluator": True,
            "developmentFailuresMayNotTuneOnBlindRecordings": True,
            "wakeValidationPartitionMayNotBeUsed": True,
            "requiredMetrics": [
                "word_error_rate_by_en_es_codeswitch",
                "semantic_operation_preservation",
                "entity_and_number_preservation",
                "stt_latency_p50_p95",
                "recording_group_breakdown",
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
                "blindRecordings": len(receipt["selection"]["blindRecordings"]),
                "blindSegments": len(receipt["selection"]["blindSegments"]),
                "blindSegmentManifestSha256": receipt["selection"][
                    "blindSegmentManifestSha256"
                ],
                "programTreeSha256": receipt["wakeProgramTree"]["sha256"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
