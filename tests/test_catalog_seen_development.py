from __future__ import annotations

import pytest

from scripts.build_catalog_seen_development_r1 import build_rows


def _capability(name: str, *, required: list[str]) -> dict[str, object]:
    return {
        "name": name,
        "description": f"Realiza la operación {name} y verifica el resultado.",
        "argumentsSchema": {
            "type": "object",
            "properties": {key: {"type": "string"} for key in required},
            "required": required,
        },
        "risk": "read_only",
    }


def test_seen_rows_cover_every_catalog_operation_once() -> None:
    rows, catalog_sha256 = build_rows(
        [
            _capability("alpha.read", required=[]),
            _capability("beta.write", required=["value"]),
        ]
    )

    assert len(rows) == 2
    assert {row["compatible_terminal_operation_sets"][0][0] for row in rows} == {
        "alpha.read",
        "beta.write",
    }
    by_operation = {
        row["compatible_terminal_operation_sets"][0][0]: row for row in rows
    }
    assert by_operation["alpha.read"]["outcome"] == "action"
    assert by_operation["alpha.read"]["compatible_effect_operation_sets"] == [
        ["alpha.read"]
    ]
    assert by_operation["beta.write"]["outcome"] == "action"
    assert by_operation["beta.write"]["compatible_effect_operation_sets"] == [
        ["beta.write"]
    ]
    assert by_operation["beta.write"]["required_arguments"] == ["value"]
    assert all(row["catalog_sha256"] == catalog_sha256 for row in rows)
    assert all(row["execution_authority"] is False for row in rows)
    assert all(row["blind_holdout"] is False for row in rows)


def test_seen_rows_reject_duplicate_authenticated_operations() -> None:
    capability = _capability("alpha.read", required=[])
    with pytest.raises(ValueError, match="duplicate operation names"):
        build_rows([capability, capability])
