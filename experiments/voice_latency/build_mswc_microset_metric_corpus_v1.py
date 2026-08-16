"""Select a deterministic real-speech MSWC metric-learning pilot corpus."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


ARCHIVE_SHA256 = "4b091336f1a22147653c43259ce534ab53c2a21f57a83c9f7a02866e16b40f2e"
ARCHIVE_BYTES = 612_495_518
SOURCE_URL = "https://mswc.mlcommons-storage.org/mswc_microset.tar.gz"
LANGUAGES = ("en", "es")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_link(value: str) -> str:
    normalized = value.replace("\\", "/").strip()
    path = Path(normalized)
    if (
        not normalized
        or path.is_absolute()
        or len(path.parts) != 2
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.suffix.casefold() != ".opus"
    ):
        raise ValueError(f"mswc_metric_link_invalid:{value}")
    return normalized


def deterministic_select(
    values: list[str], *, limit: int, material: str
) -> list[str]:
    if limit < 1 or len(values) != len(set(values)):
        raise ValueError("mswc_metric_selection_invalid")
    return sorted(
        values,
        key=lambda value: hashlib.sha256(
            f"{material}|{value}".encode("utf-8")
        ).digest(),
    )[:limit]


def read_split(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    if not rows or set(rows[0]) != {"LINK", "WORD", "VALID", "SPEAKER", "GENDER"}:
        raise ValueError(f"mswc_metric_split_invalid:{path}")
    output = []
    for row in rows:
        link = safe_link(row["LINK"])
        if row["VALID"] != "True" or Path(link).parts[0] != row["WORD"]:
            continue
        output.append({**row, "LINK": link})
    return output


def build(
    *,
    archive_path: Path,
    extracted_root: Path,
    output_path: Path,
    train_per_class: int,
    development_per_class: int,
    minimum_train_per_class: int,
    minimum_development_per_class: int,
    seed: int,
) -> dict[str, object]:
    if (
        output_path.exists()
        or train_per_class < 1
        or development_per_class < 1
        or minimum_train_per_class < 2
        or minimum_development_per_class < 2
    ):
        raise ValueError("mswc_metric_schedule_invalid")
    archive_path = archive_path.resolve(strict=True)
    extracted_root = extracted_root.resolve(strict=True)
    output_path = output_path.resolve()
    if (
        archive_path.stat().st_size != ARCHIVE_BYTES
        or sha256(archive_path) != ARCHIVE_SHA256
    ):
        raise ValueError("mswc_metric_archive_hash_mismatch")

    records: list[dict[str, object]] = []
    excluded_classes = []
    split_hashes = {}
    inventory_counts = {}
    for language in LANGUAGES:
        language_root = extracted_root / language
        clips_root = language_root / "clips"
        dev_path = language_root / f"{language}_dev.csv"
        test_path = language_root / f"{language}_test.csv"
        dev_rows = read_split(dev_path)
        test_rows = read_split(test_path)
        split_hashes[f"{language}_dev"] = sha256(dev_path)
        split_hashes[f"{language}_test"] = sha256(test_path)
        dev_by_link = {row["LINK"]: row for row in dev_rows}
        test_links = {row["LINK"] for row in test_rows}
        if set(dev_by_link).intersection(test_links):
            raise ValueError("mswc_metric_split_overlap")
        all_links = sorted(
            safe_link(path.relative_to(clips_root).as_posix())
            for path in clips_root.glob("*/*.opus")
        )
        if len(all_links) != len(set(all_links)):
            raise ValueError("mswc_metric_inventory_duplicate")
        inventory_counts[language] = len(all_links)
        training_links = [
            link for link in all_links if link not in dev_by_link and link not in test_links
        ]
        words = sorted({Path(link).parts[0] for link in all_links})
        for word in words:
            class_name = f"{language}:{word}"
            class_train = [
                link for link in training_links if Path(link).parts[0] == word
            ]
            class_dev = [
                link for link in dev_by_link if Path(link).parts[0] == word
            ]
            if (
                len(class_train) < minimum_train_per_class
                or len(class_dev) < minimum_development_per_class
            ):
                excluded_classes.append(
                    {
                        "class_name": class_name,
                        "training_available": len(class_train),
                        "development_available": len(class_dev),
                    }
                )
                continue
            selected_train = deterministic_select(
                class_train,
                limit=min(train_per_class, len(class_train)),
                material=f"{seed}|train|{class_name}",
            )
            selected_dev = deterministic_select(
                class_dev,
                limit=min(development_per_class, len(class_dev)),
                material=f"{seed}|development|{class_name}",
            )
            for split, links in (
                ("train", selected_train),
                ("development", selected_dev),
            ):
                for link in links:
                    path = clips_root / Path(link)
                    resolved = path.resolve(strict=True)
                    resolved.relative_to(clips_root.resolve(strict=True))
                    metadata = dev_by_link.get(link, {})
                    records.append(
                        {
                            "language": language,
                            "word": word,
                            "class_name": class_name,
                            "split": split,
                            "relative_path": f"{language}/clips/{link}",
                            "speaker": metadata.get("SPEAKER"),
                            "gender": metadata.get("GENDER"),
                            "opus_bytes": resolved.stat().st_size,
                            "opus_sha256": sha256(resolved),
                        }
                    )
    classes = sorted({str(record["class_name"]) for record in records})
    if len(classes) < 40:
        raise ValueError(f"mswc_metric_classes_insufficient:{len(classes)}")
    for class_name in classes:
        for split, minimum in (
            ("train", minimum_train_per_class),
            ("development", minimum_development_per_class),
        ):
            count = sum(
                record["class_name"] == class_name and record["split"] == split
                for record in records
            )
            if count < minimum:
                raise ValueError(f"mswc_metric_selected_class_insufficient:{class_name}:{split}")
    report: dict[str, object] = {
        "schema": "baxy.mswc-microset-metric-corpus.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "url": SOURCE_URL,
            "license": "CC-BY-4.0",
            "speaker_reidentification_attempted": False,
            "archive_sha256": ARCHIVE_SHA256,
            "archive_bytes": ARCHIVE_BYTES,
            "split_sha256": split_hashes,
            "inventory_opus_files": inventory_counts,
        },
        "selection": {
            "seed": seed,
            "method": "sha256_rank_within_official_split_and_language_word_class",
            "train_per_class_limit": train_per_class,
            "development_per_class_limit": development_per_class,
            "minimum_train_per_class": minimum_train_per_class,
            "minimum_development_per_class": minimum_development_per_class,
            "test_metadata_used_only_to_exclude_paths": True,
            "test_audio_accessed": False,
        },
        "counts": {
            "classes": len(classes),
            "training_records": sum(record["split"] == "train" for record in records),
            "development_records": sum(
                record["split"] == "development" for record in records
            ),
            "records": len(records),
            "excluded_classes": len(excluded_classes),
        },
        "classes": classes,
        "excluded_classes": excluded_classes,
        "records": records,
        "candidate_training_started": False,
        "test_audio_accessed": False,
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
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--extracted-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--train-per-class", type=int, default=100)
    parser.add_argument("--development-per-class", type=int, default=50)
    parser.add_argument("--minimum-train-per-class", type=int, default=10)
    parser.add_argument("--minimum-development-per-class", type=int, default=5)
    parser.add_argument("--seed", type=int, default=3401)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = build(
        archive_path=arguments.archive,
        extracted_root=arguments.extracted_root,
        output_path=arguments.output,
        train_per_class=arguments.train_per_class,
        development_per_class=arguments.development_per_class,
        minimum_train_per_class=arguments.minimum_train_per_class,
        minimum_development_per_class=arguments.minimum_development_per_class,
        seed=arguments.seed,
    )
    print(json.dumps(report["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
