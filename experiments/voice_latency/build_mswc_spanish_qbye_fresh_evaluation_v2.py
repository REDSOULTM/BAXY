"""Build a fresh Spanish MSWC open-word evaluation disjoint from QbyE v1."""

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
    raise RuntimeError("mswc_qbye_fresh_build_import_invalid")
_BUILD = importlib.util.module_from_spec(_BUILD_SPEC)
_BUILD_SPEC.loader.exec_module(_BUILD)


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"mswc_qbye_fresh_json_invalid:{path}")
    return value


def select_fresh_words(
    development: dict[str, list[dict[str, str]]],
    *,
    excluded_words: set[str],
    count: int,
    examples_per_class: int,
    seed: int,
) -> list[str]:
    candidates = [
        word
        for word, rows in development.items()
        if word not in excluded_words
        and len({row["SPEAKER"] for row in rows}) >= examples_per_class
    ]
    selected = _BUILD.rank_words(
        candidates, seed=seed, role="fresh_open_keyword_evaluation_v2"
    )[:count]
    if len(selected) != count:
        raise ValueError("mswc_qbye_fresh_classes_missing")
    return selected


def build(
    *,
    development_csv_path: Path,
    audio_archive_path: Path,
    exclusion_manifest_path: Path,
    output_root: Path,
    seed: int,
    evaluation_classes: int,
    enrollment_examples_per_class: int,
    query_examples_per_class: int,
) -> dict[str, object]:
    if (
        output_root.exists()
        or evaluation_classes < 2
        or enrollment_examples_per_class < 1
        or query_examples_per_class < 1
    ):
        raise ValueError("mswc_qbye_fresh_schedule_invalid")
    development_csv_path = development_csv_path.resolve(strict=True)
    audio_archive_path = audio_archive_path.resolve(strict=True)
    exclusion_manifest_path = exclusion_manifest_path.resolve(strict=True)
    output_root = output_root.resolve()
    partial_root = output_root.with_name(output_root.name + ".partial")
    if partial_root.exists():
        raise FileExistsError(f"mswc_qbye_fresh_partial_exists:{partial_root}")
    exclusion = read_object(exclusion_manifest_path)
    exclusion_records = exclusion.get("records")
    if (
        exclusion.get("schema") != "baxy.mswc-spanish-qbye-corpus.v1"
        or not isinstance(exclusion_records, list)
    ):
        raise ValueError("mswc_qbye_fresh_exclusion_invalid")
    excluded_words = {
        str(record["class_name"])
        for record in exclusion_records
        if isinstance(record, dict)
    }
    if len(excluded_words) != 1200:
        raise ValueError("mswc_qbye_fresh_exclusion_count_invalid")
    development = _BUILD.read_split(development_csv_path)
    examples_per_class = enrollment_examples_per_class + query_examples_per_class
    evaluation_words = select_fresh_words(
        development,
        excluded_words=excluded_words,
        count=evaluation_classes,
        examples_per_class=examples_per_class,
        seed=seed,
    )
    records: list[dict[str, object]] = []
    for word in evaluation_words:
        rows = _BUILD.select_distinct_speakers(
            development[word],
            count=examples_per_class,
            seed=seed,
            role="fresh_open_keyword_evaluation_v2",
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
                    "official_split": "development",
                    "source_link": row["LINK"],
                    "speaker_group": _BUILD.private_speaker_group(row["SPEAKER"]),
                    "gender_metadata": row["GENDER"],
                }
            )
    source_links = [str(record["source_link"]) for record in records]
    if len(source_links) != len(set(source_links)):
        raise ValueError("mswc_qbye_fresh_link_overlap")
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
                raise ValueError("mswc_qbye_fresh_archive_member_invalid")
            record = selected_by_archive_name[member.name]
            relative = PurePosixPath(str(record["source_link"]))
            target = audio_root.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("mswc_qbye_fresh_archive_stream_missing")
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
        raise ValueError(f"mswc_qbye_fresh_archive_members_missing:{len(remaining)}")
    records.sort(
        key=lambda record: (
            str(record["partition"]),
            str(record["class_name"]),
            str(record["source_link"]),
        )
    )
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-qbye-fresh-evaluation-corpus.v2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "fresh_development_open_word_evaluation_after_v1_selection_close",
        "sources": {
            "dataset": "MLCommons Multilingual Spoken Words Corpus",
            "language": "es",
            "license": "CC-BY-4.0",
            "audio_url": "https://mswc.mlcommons-storage.org/audio/es.tar.gz",
            "audio_archive_sha256": _BUILD.sha256(audio_archive_path),
            "development_csv_sha256": _BUILD.sha256(development_csv_path),
            "exclusion_manifest_sha256": _BUILD.sha256(exclusion_manifest_path),
        },
        "contract": {
            "seed": seed,
            "evaluation_classes": evaluation_classes,
            "enrollment_examples_per_class": enrollment_examples_per_class,
            "query_examples_per_class": query_examples_per_class,
            "all_examples_use_distinct_speakers_within_each_word": True,
            "excluded_prior_training_and_open_word_classes": len(excluded_words),
            "word_selection": "sha256_ranked_after_fixed_eligibility_and_v1_exclusion",
        },
        "metrics": {
            "records": len(records),
            "evaluation_word_classes": len(evaluation_words),
            "open_keyword_enrollment": sum(
                record["partition"] == "open_keyword_enrollment" for record in records
            ),
            "open_keyword_query": sum(
                record["partition"] == "open_keyword_query" for record in records
            ),
        },
        "evaluation_words": sorted(evaluation_words),
        "records": records,
        "official_test_metadata_accessed": False,
        "official_test_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "speaker_reidentification_attempted": False,
        "effects_executed": 0,
    }
    (partial_root / "corpus.manifest.v2.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(partial_root, output_root)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development-csv", type=Path, required=True)
    parser.add_argument("--audio-archive", type=Path, required=True)
    parser.add_argument("--exclusion-manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=4501)
    parser.add_argument("--evaluation-classes", type=int, default=200)
    parser.add_argument("--enrollment-examples-per-class", type=int, default=4)
    parser.add_argument("--query-examples-per-class", type=int, default=12)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build(
        development_csv_path=args.development_csv,
        audio_archive_path=args.audio_archive,
        exclusion_manifest_path=args.exclusion_manifest,
        output_root=args.output_root,
        seed=args.seed,
        evaluation_classes=args.evaluation_classes,
        enrollment_examples_per_class=args.enrollment_examples_per_class,
        query_examples_per_class=args.query_examples_per_class,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
