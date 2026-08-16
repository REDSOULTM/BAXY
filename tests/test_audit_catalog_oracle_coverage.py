from __future__ import annotations

import pytest

from scripts.audit_catalog_oracle_coverage import build_audit


def _capability(name: str) -> dict[str, object]:
    return {
        "name": name,
        "description": f"Description for {name}",
        "argumentsSchema": {"type": "object", "properties": {}},
        "risk": "read_only",
    }


def test_audit_separates_current_exact_coverage_from_legacy_labels() -> None:
    capabilities = [
        _capability("alpha.read"),
        _capability("beta.write"),
        _capability("gamma.run"),
    ]
    current_rows = [
        {
            "language": "es",
            "source_declared_language": "pt",
            "compatible_terminal_operation_sets": [["alpha.read"]],
        },
        {
            "language": "es",
            "source_declared_language": "es",
            "compatible_terminal_operation_sets": [
                ["reminder.create"],
                ["notification.schedule"],
            ],
        },
    ]
    holdout_rows = [
        {
            "language": "spanglish",
            "compatible_terminal_operation_sets": [["beta.write"]],
        }
    ]
    historical_rows = [
        {"language": "es", "operations": ["gamma.run"]},
        {"language": "other", "operations": ["gamma.manage"]},
    ]

    audit = build_audit(
        capabilities,
        current_rows,
        holdout_rows,
        historical_rows,
        include_file_hashes=False,
    )

    assert audit["catalog"]["operations"] == 3
    assert audit["coverage"]["evaluation_union_exact_operations"] == [
        "alpha.read",
        "beta.write",
    ]
    assert audit["coverage"]["evaluation_union_missing_operations"] == [
        "gamma.run"
    ]
    assert audit["coverage"]["blind_exact_operations"] == ["beta.write"]
    assert audit["conflicts"]["historical_legacy_abstract_labels"] == [
        "gamma.manage"
    ]
    assert audit["conflicts"]["historical_rows_naming_legacy_labels"] == 1
    assert audit["conflicts"]["current_review_language_metadata_repairs"] == 1
    assert (
        audit["conflicts"][
            "current_review_reminder_notification_alternative_rows"
        ]
        == 1
    )
    assert audit["verdict"]["catalog_exact_operation_coverage_complete"] is False
    assert (
        audit["verdict"]["historical_corpus_is_current_exact_operation_oracle"]
        is False
    )


def test_audit_rejects_duplicate_authenticated_operation_names() -> None:
    with pytest.raises(ValueError, match="duplicate operation names"):
        build_audit(
            [_capability("alpha.read"), _capability("alpha.read")],
            [{"compatible_terminal_operation_sets": [["alpha.read"]]}],
            [{"compatible_terminal_operation_sets": [["alpha.read"]]}],
            [{"operations": ["alpha.read"]}],
            include_file_hashes=False,
        )
