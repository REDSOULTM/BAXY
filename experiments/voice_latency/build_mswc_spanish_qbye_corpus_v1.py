"""Build a word- and speaker-disjoint Spanish MSWC QbyE pilot corpus.

The official MSWC test split is deliberately outside this development
campaign.  Training words and open-keyword validation words are disjoint;
enrollment and query examples for every validation word are also drawn from
different pseudonymous speaker groups.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile


SAFE_WORD = re.compile(r"[a-z]{3,12}")
TARGET_FORMS = ("baxy", "baxi", "baksi", "faxi", "vaxi", "bakshi")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_digest(seed: int, *values: str) -> str:
    joined = "\x1f".join((str(seed), *values))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def levenshtein(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_value in enumerate(left, 1):
        current = [left_index]
        for right_index, right_value in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_value != right_value),
                )
            )
        previous = current
    return previous[-1]


def target_neighborhood_excluded(word: str) -> bool:
    return any(levenshtein(word, target) <= 2 for target in TARGET_FORMS)


def read_split(path: Path) -> dict[str, list[dict[str, str]]]:
    by_word: dict[str, list[dict[str, str]]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ["LINK", "WORD", "VALID", "SPEAKER", "GENDER"]:
            raise ValueError(f"mswc_qbye_csv_contract_invalid:{path}")
        for row in reader:
            word = row["WORD"]
            link = PurePosixPath(row["LINK"])
            if (
                row["VALID"].casefold() != "true"
                or SAFE_WORD.fullmatch(word) is None
                or target_neighborhood_excluded(word)
                or len(link.parts) != 2
                or link.parts[0] != word
                or link.suffix != ".opus"
                or not row["SPEAKER"]
            ):
                continue
            by_word.setdefault(word, []).append(row)
    return by_word


def rank_words(words: list[str], *, seed: int, role: str) -> list[str]:
    return sorted(words, key=lambda word: (stable_digest(seed, role, word), word))


def select_distinct_speakers(
    rows: list[dict[str, str]], *, count: int, seed: int, role: str
) -> list[dict[str, str]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            stable_digest(seed, role, row["WORD"], row["SPEAKER"], row["LINK"]),
            row["LINK"],
        ),
    )
    selected = []
    speakers = set()
    for row in ordered:
        if row["SPEAKER"] in speakers:
            continue
        selected.append(row)
        speakers.add(row["SPEAKER"])
        if len(selected) == count:
            break
    if len(selected) != count:
        raise ValueError(f"mswc_qbye_distinct_speakers_missing:{role}:{len(selected)}:{count}")
    return selected


def private_speaker_group(raw_speaker: str) -> str:
    return hashlib.sha256(
        ("baxy-mswc-speaker-group-v1\x1f" + raw_speaker).encode("utf-8")
    ).hexdigest()


def build(
    *,
    train_csv_path: Path,
    development_csv_path: Path,
    audio_archive_path: Path,
    output_root: Path,
    seed: int,
    training_classes: int,
    evaluation_classes: int,
    training_examples_per_class: int,
    enrollment_examples_per_class: int,
    query_examples_per_class: int,
) -> dict[str, object]:
    if (
        output_root.exists()
        or training_classes < 2
        or evaluation_classes < 1
        or training_examples_per_class < 2
        or enrollment_examples_per_class < 1
        or query_examples_per_class < 1
    ):
        raise ValueError("mswc_qbye_schedule_invalid")
    train_csv_path = train_csv_path.resolve(strict=True)
    development_csv_path = development_csv_path.resolve(strict=True)
    audio_archive_path = audio_archive_path.resolve(strict=True)
    output_root = output_root.resolve()
    partial_root = output_root.with_name(output_root.name + ".partial")
    if partial_root.exists():
        raise FileExistsError(f"mswc_qbye_partial_output_exists:{partial_root}")

    train = read_split(train_csv_path)
    development = read_split(development_csv_path)
    evaluation_total = enrollment_examples_per_class + query_examples_per_class
    evaluation_candidates = [
        word
        for word, rows in development.items()
        if len({row["SPEAKER"] for row in rows}) >= evaluation_total
    ]
    evaluation_words = rank_words(
        evaluation_candidates, seed=seed, role="open_keyword_evaluation"
    )[:evaluation_classes]
    if len(evaluation_words) != evaluation_classes:
        raise ValueError("mswc_qbye_evaluation_classes_missing")
    evaluation_set = set(evaluation_words)
    training_candidates = [
        word
        for word, rows in train.items()
        if word not in evaluation_set
        and len({row["SPEAKER"] for row in rows}) >= training_examples_per_class
    ]
    training_words = rank_words(
        training_candidates, seed=seed, role="metric_training"
    )[:training_classes]
    if len(training_words) != training_classes:
        raise ValueError("mswc_qbye_training_classes_missing")

    selected: list[dict[str, object]] = []
    for word in training_words:
        rows = select_distinct_speakers(
            train[word],
            count=training_examples_per_class,
            seed=seed,
            role="metric_training",
        )
        for row in rows:
            selected.append(
                {
                    "class_name": word,
                    "partition": "metric_training",
                    "official_split": "train",
                    "source_link": row["LINK"],
                    "speaker_group": private_speaker_group(row["SPEAKER"]),
                    "gender_metadata": row["GENDER"],
                }
            )
    for word in evaluation_words:
        rows = select_distinct_speakers(
            development[word],
            count=evaluation_total,
            seed=seed,
            role="open_keyword_evaluation",
        )
        for index, row in enumerate(rows):
            selected.append(
                {
                    "class_name": word,
                    "partition": (
                        "open_keyword_enrollment"
                        if index < enrollment_examples_per_class
                        else "open_keyword_query"
                    ),
                    "official_split": "development",
                    "source_link": row["LINK"],
                    "speaker_group": private_speaker_group(row["SPEAKER"]),
                    "gender_metadata": row["GENDER"],
                }
            )
    source_links = [str(record["source_link"]) for record in selected]
    if len(source_links) != len(set(source_links)):
        raise ValueError("mswc_qbye_selected_link_overlap")
    selected_by_archive_name = {
        f"es/clips/{link}": record for link, record in zip(source_links, selected, strict=True)
    }

    partial_root.mkdir(parents=True)
    audio_root = partial_root / "audio"
    remaining = set(selected_by_archive_name)
    with tarfile.open(audio_archive_path, mode="r|gz") as archive:
        for member in archive:
            if member.name not in remaining:
                continue
            if not member.isfile():
                raise ValueError(f"mswc_qbye_archive_member_invalid:{member.name}")
            record = selected_by_archive_name[member.name]
            relative_path = PurePosixPath(str(record["source_link"]))
            target = audio_root.joinpath(*relative_path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError(f"mswc_qbye_archive_stream_missing:{member.name}")
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
        example = min(remaining)
        raise ValueError(f"mswc_qbye_archive_members_missing:{len(remaining)}:{example}")

    selected.sort(
        key=lambda record: (
            str(record["partition"]),
            str(record["class_name"]),
            str(record["source_link"]),
        )
    )
    role_counts = {
        role: sum(record["partition"] == role for record in selected)
        for role in (
            "metric_training",
            "open_keyword_enrollment",
            "open_keyword_query",
        )
    }
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-qbye-corpus.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_open_keyword_metric_training",
        "source": {
            "dataset": "MLCommons Multilingual Spoken Words Corpus",
            "language": "es",
            "license": "CC-BY-4.0",
            "audio_url": "https://mswc.mlcommons-storage.org/audio/es.tar.gz",
            "splits_url": "https://mswc.mlcommons-storage.org/splits/es.tar.gz",
            "audio_archive_sha256": sha256(audio_archive_path),
            "train_csv_sha256": sha256(train_csv_path),
            "development_csv_sha256": sha256(development_csv_path),
        },
        "contract": {
            "seed": seed,
            "safe_word_pattern": SAFE_WORD.pattern,
            "target_neighborhood_forms": list(TARGET_FORMS),
            "target_neighborhood_maximum_levenshtein_distance": 2,
            "training_classes": training_classes,
            "evaluation_classes": evaluation_classes,
            "training_examples_per_class": training_examples_per_class,
            "enrollment_examples_per_class": enrollment_examples_per_class,
            "query_examples_per_class": query_examples_per_class,
            "all_selected_examples_use_distinct_speakers_within_each_word": True,
            "training_and_evaluation_word_classes_disjoint": True,
            "evaluation_enrollment_and_query_speakers_disjoint_within_each_word": True,
            "class_selection": "sha256_ranked_after_fixed_eligibility_filter",
            "clip_selection": "sha256_ranked_one_clip_per_pseudonymous_speaker",
        },
        "metrics": {
            "records": len(selected),
            "training_word_classes": len(training_words),
            "evaluation_word_classes": len(evaluation_words),
            **role_counts,
        },
        "training_words": sorted(training_words),
        "evaluation_words": sorted(evaluation_words),
        "records": selected,
        "official_test_metadata_accessed": False,
        "official_test_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "speaker_reidentification_attempted": False,
        "effects_executed": 0,
    }
    manifest_path = partial_root / "corpus.manifest.v1.json"
    manifest_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(partial_root, output_root)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-csv", type=Path, required=True)
    parser.add_argument("--development-csv", type=Path, required=True)
    parser.add_argument("--audio-archive", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=3501)
    parser.add_argument("--training-classes", type=int, default=1000)
    parser.add_argument("--evaluation-classes", type=int, default=200)
    parser.add_argument("--training-examples-per-class", type=int, default=32)
    parser.add_argument("--enrollment-examples-per-class", type=int, default=4)
    parser.add_argument("--query-examples-per-class", type=int, default=12)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build(
        train_csv_path=args.train_csv,
        development_csv_path=args.development_csv,
        audio_archive_path=args.audio_archive,
        output_root=args.output_root,
        seed=args.seed,
        training_classes=args.training_classes,
        evaluation_classes=args.evaluation_classes,
        training_examples_per_class=args.training_examples_per_class,
        enrollment_examples_per_class=args.enrollment_examples_per_class,
        query_examples_per_class=args.query_examples_per_class,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
