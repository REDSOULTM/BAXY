from __future__ import annotations

import importlib.util
import json
import sys
from argparse import Namespace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_turn_policy_runtime_development.py"
SPEC = importlib.util.spec_from_file_location("baxy_prepare_runtime_dev", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
prepare = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = prepare
SPEC.loader.exec_module(prepare)


def row(
    source_id: str,
    mission_id: str,
    text: str,
    *,
    mode: str,
    families: tuple[str, ...],
    split: str | None = "train",
    license_name: str = "CC-BY-4.0",
) -> dict[str, object]:
    return {
        "schema": prepare.ROW_SCHEMA,
        "text": text,
        "mode": mode,
        "families": list(families),
        "mission_id": mission_id,
        "source_id": source_id,
        "split": split,
        "provenance": {
            "dataset": "synthetic public fixture",
            "license": license_name,
        },
    }


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"
            for item in rows
        ),
        encoding="utf-8",
    )


def test_group_split_keeps_translations_and_exact_text_components_together() -> None:
    records = [
        row("a-es", "mission-a", "abre la app", mode="action", families=("app",)),
        row("a-en", "mission-a", "open the app", mode="action", families=("app",)),
        row("b-es", "mission-b", "abre la app", mode="action", families=("app",)),
        row(
            "c-es",
            "mission-c",
            "hola",
            mode="conversation",
            families=(),
        ),
        row(
            "d-es",
            "mission-d",
            "cuéntame algo",
            mode="conversation",
            families=(),
        ),
        row("e-es", "mission-e", "abre notas", mode="action", families=("app",)),
    ]

    train, validation, diagnostics = prepare.partition_rows(
        records,
        seed="stable-fixture-seed",
        validation_fraction=0.4,
    )
    split_by_source = {
        str(item["source_id"]): str(item["split"])
        for item in [*train, *validation]
    }

    assert split_by_source["a-es"] == split_by_source["a-en"]
    assert split_by_source["a-es"] == split_by_source["b-es"]
    assert diagnostics["mission_split_overlap"] == 0
    assert diagnostics["normalized_text_split_overlap"] == 0
    assert len(train) + len(validation) == len(records)


def test_conflicting_exact_text_is_rejected() -> None:
    records = [
        row("a", "mission-a", "igual", mode="action", families=("app",)),
        row("b", "mission-b", "igual", mode="conversation", families=()),
    ]

    with pytest.raises(ValueError, match="conflicting"):
        prepare.partition_rows(
            records,
            seed="stable-fixture-seed",
            validation_fraction=0.2,
        )


@pytest.mark.parametrize("split", ["validation", "test"])
def test_loader_rejects_any_heldout_row(tmp_path: Path, split: str) -> None:
    source = tmp_path / "runtime.jsonl"
    write_jsonl(
        source,
        [
            row(
                "heldout",
                "mission-heldout",
                "never open this as development",
                mode="conversation",
                families=(),
                split=split,
            )
        ],
    )

    with pytest.raises(ValueError, match="non-train held-out"):
        prepare._load_public_train(source)


def test_build_is_deterministic_and_excludes_historical_rows(
    tmp_path: Path,
) -> None:
    source = tmp_path / "runtime.jsonl"
    public_rows: list[dict[str, object]] = []
    for index in range(40):
        public_rows.append(
            row(
                f"source-{index}",
                f"mission-{index}",
                f"public phrase {index}",
                mode=("action" if index % 2 else "conversation"),
                families=(("app",) if index % 2 else ()),
            )
        )
    public_rows.append(
        row(
            "historical",
            "mission-historical",
            "local historical row",
            mode="action",
            families=("app",),
            split=None,
            license_name="private-local",
        )
    )
    write_jsonl(source, public_rows)
    train = tmp_path / "runtime_train.jsonl"
    validation = tmp_path / "runtime_validation.jsonl"
    manifest = tmp_path / "manifest.json"
    args = Namespace(
        source=source,
        expected_source_sha256=prepare._sha256(source),
        train_output=train,
        validation_output=validation,
        manifest=manifest,
        seed="stable-fixture-seed",
        validation_fraction=0.2,
    )

    first = prepare.build(args)
    first_bytes = (train.read_bytes(), validation.read_bytes(), manifest.read_bytes())
    second = prepare.build(args)

    assert first == second
    assert first_bytes == (
        train.read_bytes(),
        validation.read_bytes(),
        manifest.read_bytes(),
    )
    assert first["selection"]["heldout_rows_opened"] is False
    assert first["selection"]["historical_rows_used"] is False
    assert first["excluded"] == {"historical_without_public_split": 1}
    assert first["diagnostics"]["mission_split_overlap"] == 0
    assert first["diagnostics"]["normalized_text_split_overlap"] == 0
    assert b"local historical row" not in train.read_bytes()
    assert b"local historical row" not in validation.read_bytes()
