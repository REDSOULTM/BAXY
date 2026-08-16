"""Build a train-split MSWC corpus for phonetic QbyE sequence research."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import tarfile


_BUILD_PATH = Path(__file__).with_name("build_mswc_spanish_qbye_corpus_v1.py")
_BUILD_SPEC = importlib.util.spec_from_file_location("_baxy_qbye_corpus_v1", _BUILD_PATH)
if _BUILD_SPEC is None or _BUILD_SPEC.loader is None:
    raise RuntimeError("mswc_qbye_sequence_research_import_invalid")
_BUILD = importlib.util.module_from_spec(_BUILD_SPEC)
_BUILD_SPEC.loader.exec_module(_BUILD)


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"mswc_qbye_sequence_research_json_invalid:{path}")
    return value


def excluded_words(manifest_paths: list[Path]) -> set[str]:
    excluded: set[str] = set()
    for raw_path in manifest_paths:
        path = raw_path.resolve(strict=True)
        manifest = read_object(path)
        schema = manifest.get("schema")
        if schema == "baxy.mswc-spanish-qbye-corpus.v1":
            records = manifest.get("records")
            if not isinstance(records, list):
                raise ValueError("mswc_qbye_sequence_research_v1_records_invalid")
            excluded.update(
                str(record["class_name"])
                for record in records
                if isinstance(record, dict)
            )
        elif schema == "baxy.mswc-spanish-qbye-fresh-evaluation-corpus.v2":
            words = manifest.get("evaluation_words")
            if not isinstance(words, list):
                raise ValueError("mswc_qbye_sequence_research_v2_words_invalid")
            excluded.update(str(word) for word in words)
        else:
            raise ValueError(f"mswc_qbye_sequence_research_exclusion_invalid:{path}")
    return excluded


def select_research_words(
    training: dict[str, list[dict[str, str]]],
    *,
    excluded: set[str],
    count: int,
    examples_per_class: int,
    seed: int,
) -> list[str]:
    candidates = [
        word
        for word, rows in training.items()
        if word not in excluded
        and len({row["SPEAKER"] for row in rows}) >= examples_per_class
    ]
    selected = _BUILD.rank_words(
        candidates, seed=seed, role="phonetic_sequence_research_v3"
    )[:count]
    if len(selected) != count:
        raise ValueError("mswc_qbye_sequence_research_classes_missing")
    return selected


def build(
    *,
    train_csv_path: Path,
    audio_archive_path: Path,
    exclusion_manifest_paths: list[Path],
    output_root: Path,
    seed: int,
    research_classes: int,
    enrollment_examples_per_class: int,
    query_examples_per_class: int,
) -> dict[str, object]:
    if (
        output_root.exists()
        or len(exclusion_manifest_paths) < 1
        or research_classes < 2
        or enrollment_examples_per_class < 1
        or query_examples_per_class < 1
    ):
        raise ValueError("mswc_qbye_sequence_research_schedule_invalid")
    train_csv_path = train_csv_path.resolve(strict=True)
    audio_archive_path = audio_archive_path.resolve(strict=True)
    resolved_exclusions = [path.resolve(strict=True) for path in exclusion_manifest_paths]
    output_root = output_root.resolve()
    partial_root = output_root.with_name(output_root.name + ".partial")
    if partial_root.exists():
        raise FileExistsError(f"mswc_qbye_sequence_research_partial_exists:{partial_root}")
    excluded = excluded_words(resolved_exclusions)
    training = _BUILD.read_split(train_csv_path)
    examples_per_class = enrollment_examples_per_class + query_examples_per_class
    words = select_research_words(
        training,
        excluded=excluded,
        count=research_classes,
        examples_per_class=examples_per_class,
        seed=seed,
    )
    records: list[dict[str, object]] = []
    for word in words:
        rows = _BUILD.select_distinct_speakers(
            training[word],
            count=examples_per_class,
            seed=seed,
            role="phonetic_sequence_research_v3",
        )
        for index, row in enumerate(rows):
            records.append(
                {
                    "class_name": word,
                    "partition": (
                        "open_keyword_enrollment"
                        if index < enrollment_examples_per_class
                        else "open_keyword_query"
                    ),
                    "official_split": "train",
                    "source_link": row["LINK"],
                    "speaker_group": _BUILD.private_speaker_group(row["SPEAKER"]),
                    "gender_metadata": row["GENDER"],
                }
            )
    source_links = [str(record["source_link"]) for record in records]
    if len(source_links) != len(set(source_links)):
        raise ValueError("mswc_qbye_sequence_research_link_overlap")
    selected_by_archive_name = {
        f"es/clips/{link}": record
        for link, record in zip(source_links, records, strict=True)
    }
    partial_root.mkdir(parents=True)
    audio_root = partial_root / "audio"
    remaining = set(selected_by_archive_name)
    with tarfile.open(audio_archive_path, mode="r|gz") as archive:
        for member in archive:
            if member.name not in remaining:
                continue
            if not member.isfile():
                raise ValueError("mswc_qbye_sequence_research_archive_member_invalid")
            record = selected_by_archive_name[member.name]
            relative = PurePosixPath(str(record["source_link"]))
            target = audio_root.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("mswc_qbye_sequence_research_archive_stream_missing")
            digest = hashlib.sha256()
            byte_count = 0
            with source, target.open("xb") as destination:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    destination.write(chunk)
                    digest.update(chunk)
                    byte_count += len(chunk)
            record["relative_path"] = target.relative_to(partial_root).as_posix()
            record["audio_bytes"] = byte_count
            record["audio_sha256"] = digest.hexdigest()
            remaining.remove(member.name)
            if not remaining:
                break
    if remaining:
        raise ValueError(f"mswc_qbye_sequence_research_archive_members_missing:{len(remaining)}")
    records.sort(
        key=lambda record: (
            str(record["partition"]),
            str(record["class_name"]),
            str(record["source_link"]),
        )
    )
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-qbye-sequence-research-corpus.v3",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "train_split_only_phonetic_sequence_query_by_example_research",
        "sources": {
            "dataset": "MLCommons Multilingual Spoken Words Corpus",
            "language": "es",
            "license": "CC-BY-4.0",
            "audio_url": "https://mswc.mlcommons-storage.org/audio/es.tar.gz",
            "audio_archive_sha256": _BUILD.sha256(audio_archive_path),
            "train_csv_sha256": _BUILD.sha256(train_csv_path),
            "exclusion_manifests": [
                {"path": path.as_posix(), "sha256": _BUILD.sha256(path)}
                for path in resolved_exclusions
            ],
        },
        "contract": {
            "seed": seed,
            "research_classes": research_classes,
            "enrollment_examples_per_class": enrollment_examples_per_class,
            "query_examples_per_class": query_examples_per_class,
            "all_examples_use_distinct_speakers_within_each_word": True,
            "excluded_prior_word_classes": len(excluded),
            "word_selection": "sha256_ranked_after_fixed_eligibility_and_prior_exclusion",
        },
        "metrics": {
            "records": len(records),
            "research_word_classes": len(words),
            "open_keyword_enrollment": sum(
                record["partition"] == "open_keyword_enrollment" for record in records
            ),
            "open_keyword_query": sum(
                record["partition"] == "open_keyword_query" for record in records
            ),
        },
        "research_words": sorted(words),
        "records": records,
        "official_test_metadata_accessed": False,
        "official_test_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "speaker_reidentification_attempted": False,
        "effects_executed": 0,
    }
    (partial_root / "corpus.manifest.v3.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(partial_root, output_root)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-csv", type=Path, required=True)
    parser.add_argument("--audio-archive", type=Path, required=True)
    parser.add_argument("--exclusion-manifest", type=Path, nargs="+", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=5501)
    parser.add_argument("--research-classes", type=int, default=600)
    parser.add_argument("--enrollment-examples-per-class", type=int, default=2)
    parser.add_argument("--query-examples-per-class", type=int, default=6)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build(
        train_csv_path=args.train_csv,
        audio_archive_path=args.audio_archive,
        exclusion_manifest_paths=args.exclusion_manifest,
        output_root=args.output_root,
        seed=args.seed,
        research_classes=args.research_classes,
        enrollment_examples_per_class=args.enrollment_examples_per_class,
        query_examples_per_class=args.query_examples_per_class,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
