from __future__ import annotations

import pytest

from scripts import build_catalog_seen_scenarios_r1 as builder


def _capability(name: str) -> dict[str, object]:
    return {
        "name": name,
        "description": f"Description for {name}",
        "argumentsSchema": {"type": "object", "properties": {}},
        "risk": "read_only",
    }


def test_seen_scenarios_cover_the_explicit_catalog_and_split_owners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenarios = {
        "memory.save": ("es", "Recuerda que prefiero té."),
        "system.time": ("en", "Tell me the current time."),
    }
    monkeypatch.setattr(builder, "SEEN_UTTERANCES", scenarios)

    rows, catalog_sha256 = builder.build_rows(
        [_capability("system.time"), _capability("memory.save")]
    )

    assert len(rows) == 2
    by_operation = {
        row["target_operation"]: row for row in rows
    }
    assert by_operation["memory.save"]["owner"] == "app_memory_parser"
    assert by_operation["system.time"]["owner"] == "mind_sidecar"
    assert all(row["catalog_sha256"] == catalog_sha256 for row in rows)
    assert all(row["execution_authority"] is False for row in rows)


def test_seen_scenarios_include_required_predecessors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        builder,
        "SEEN_UTTERANCES",
        {
            "capture.screenshot": ("es", "Toma una captura."),
            "ocr.read": ("es", "Toma una captura y ejecuta OCR."),
        },
    )

    rows, _catalog_sha256 = builder.build_rows(
        [_capability("capture.screenshot"), _capability("ocr.read")]
    )
    row = next(value for value in rows if value["target_operation"] == "ocr.read")

    assert row["compatible_terminal_operation_sets"] == [
        ["capture.screenshot", "ocr.read"]
    ]


def test_seen_scenarios_reject_catalogue_gaps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        builder,
        "SEEN_UTTERANCES",
        {"system.time": ("es", "Dime la hora.")},
    )
    with pytest.raises(ValueError, match="coverage mismatch"):
        builder.build_rows(
            [_capability("system.time"), _capability("network.status")]
        )
