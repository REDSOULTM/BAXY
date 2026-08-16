from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from local_evidence import require_runtime_turn_evidence
from baxy_mind.public_turn_corpus import (
    PUBLIC_RECORD_SCHEMA_VERSION,
    SourceMap,
    build_massive_records,
    build_presto_records,
    load_source_map,
)


def test_public_corpus_contract_import_is_runtime_independent() -> None:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    completed = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-c",
            (
                "import sys; "
                "import baxy_mind.public_turn_corpus as corpus; "
                "assert corpus.PUBLIC_RECORD_SCHEMA_VERSION == "
                "'baxy.turn-evidence-record.v1'; "
                "assert 'baxy_mind.turn_evidence' not in sys.modules; "
                "assert 'baxy_mind.turn_probe' not in sys.modules; "
                "assert 'numpy' not in sys.modules"
            ),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr


def _map(*, quality: bool = False) -> SourceMap:
    return SourceMap(
        source={"name": "fixture", "license": "CC-BY-4.0", "download_url": "https://example.test"},
        locales=frozenset({"es-ES", "en-US"}),
        require_empty_previous_turns=True,
        maximum_text_characters=384,
        labels={"Open_app": ("action", ("app",)), "play_music": ("action", ("media",))},
        minimum_localized_judgments=2 if quality else 0,
        minimum_localized_grammar_score=3 if quality else 0,
    )


def test_presto_adapter_keeps_only_mapped_standalone_locales(tmp_path: Path) -> None:
    rows = [
        {
            "inputs": "abre la musica",
            "targets": "Open_app ( app )",
            "metadata": {"locale": "es-ES", "example_id": "safe", "previous_turns": []},
        },
        {
            "inputs": "esa",
            "targets": "Open_app ( app )",
            "metadata": {"locale": "es-ES", "example_id": "context", "previous_turns": [{"user_query": "x"}]},
        },
        {
            "inputs": "open music",
            "targets": "Unknown ( x )",
            "metadata": {"locale": "en-US", "example_id": "unmapped", "previous_turns": []},
        },
        {
            "inputs": "oeffne musik",
            "targets": "Open_app ( app )",
            "metadata": {"locale": "de-DE", "example_id": "locale", "previous_turns": []},
        },
    ]
    archive = tmp_path / "presto.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("presto_train.jsonl", "".join(json.dumps(row) + "\n" for row in rows))

    records, report = build_presto_records(archive, _map(), "train")

    assert len(records) == 1
    assert records[0]["schema"] == PUBLIC_RECORD_SCHEMA_VERSION
    assert records[0]["families"] == ["app"]
    assert records[0]["split"] == "train"
    assert records[0]["provenance"]["license"] == "CC-BY-4.0"
    assert report.excluded_contextual == 1
    assert report.excluded_unmapped == 1
    assert report.excluded_locale == 1


def test_massive_adapter_honors_partition_and_localized_quality(tmp_path: Path) -> None:
    accepted_es = {
        "id": "same",
        "locale": "es-ES",
        "partition": "train",
        "intent": "play_music",
        "utt": "pon musica",
        "judgments": [
            {"intent_score": 1, "grammar_score": 4},
            {"intent_score": 1, "grammar_score": 3},
        ],
    }
    accepted_en = {
        "id": "same",
        "locale": "en-US",
        "partition": "train",
        "intent": "play_music",
        "utt": "play music",
    }
    rejected_quality = {
        "id": "bad",
        "locale": "es-ES",
        "partition": "train",
        "intent": "play_music",
        "utt": "mala",
        "judgments": [{"intent_score": 1, "grammar_score": 1}],
    }
    dev_row = {**accepted_es, "id": "dev", "partition": "dev"}
    archive = tmp_path / "massive.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for locale, rows in {
            "es-ES": [accepted_es, rejected_quality, dev_row],
            "en-US": [accepted_en],
        }.items():
            payload = "".join(json.dumps(row) + "\n" for row in rows).encode("utf-8")
            info = tarfile.TarInfo(f"1.1/data/{locale}.jsonl")
            info.size = len(payload)
            bundle.addfile(info, io.BytesIO(payload))

    records, report = build_massive_records(archive, _map(quality=True), "train")

    assert len(records) == 2
    assert {record["source_id"] for record in records} == {
        "massive-v1.1:es-ES:same",
        "massive-v1.1:en-US:same",
    }
    assert {record["mission_id"] for record in records} == {"massive-v1.1:same"}
    assert report.excluded_quality == 1
    assert report.excluded_partition == 1


def test_reviewed_source_maps_cannot_introduce_a_baxy_family() -> None:
    root = Path(__file__).resolve().parents[1]
    catalog = (root / "src" / "Baxy.Kernel" / "Operations" / "ProductCatalog.cs").read_text(encoding="utf-8")
    product_families = {
        operation.split(".", 1)[0]
        for operation in re.findall(r'Descriptor\(\s*"([a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+)"', catalog)
    }
    assert product_families
    for source_map_path in (
        root / "src" / "baxy_mind" / "data" / "presto_turn_evidence_map.v1.json",
        root / "src" / "baxy_mind" / "data" / "massive_turn_evidence_map.v1.json",
    ):
        source_map = load_source_map(source_map_path)
        mapped_families = {
            family
            for _mode, families in source_map.labels.values()
            for family in families
        }
        assert mapped_families <= product_families


def test_promoted_runtime_corpus_is_large_but_contains_only_evidence_fields() -> None:
    root = Path(__file__).resolve().parents[1]
    corpus = require_runtime_turn_evidence(root)
    rows = [json.loads(line) for line in corpus.read_text(encoding="utf-8").splitlines()]

    assert len(rows) >= 20_000
    assert all(set(row) == {"schema", "text", "mode", "families", "mission_id", "source_id", "split", "provenance"} for row in rows)
    assert all(row["schema"] == PUBLIC_RECORD_SCHEMA_VERSION for row in rows)
    assert all(row["mode"] in {"conversation", "clarify", "action", "plan"} for row in rows)
    assert all("memory" not in row["families"] for row in rows)
    assert all(row["split"] in {None, "train"} for row in rows)
    assert {row["provenance"]["license"] for row in rows} >= {"private-local", "CC-BY-4.0"}


def test_promoted_holdout_has_no_exact_text_seen_by_runtime() -> None:
    root = Path(__file__).resolve().parents[1]
    runtime = [
        json.loads(line)
        for line in require_runtime_turn_evidence(root)
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    holdout = [
        json.loads(line)
        for line in (root / "tests" / "data" / "turn_evidence_public_holdout.v1.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    normalized_runtime = {
        " ".join(str(row["text"]).casefold().split())
        for row in runtime
    }
    normalized_holdout = {
        " ".join(str(row["text"]).casefold().split())
        for row in holdout
    }

    assert normalized_runtime.isdisjoint(normalized_holdout)


def test_promotion_manifest_is_portable_and_does_not_leak_local_paths() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (root / "tests" / "data" / "turn_evidence_public_manifest.v1.json")
        .read_text(encoding="utf-8")
    )

    serialized = json.dumps(manifest, ensure_ascii=False)
    assert "C:\\" not in serialized
    assert "D:\\" not in serialized
    assert manifest["outputs"]["runtime"]["repo_path"] == (
        "tests/data/turn_evidence_runtime.v1.jsonl"
    )
    assert manifest["outputs"]["heldout"]["repo_path"] == (
        "tests/data/turn_evidence_public_holdout.v1.jsonl"
    )
