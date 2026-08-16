from __future__ import annotations

import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "probe_mvp_core_provider_matrix.py"
SPEC = importlib.util.spec_from_file_location("probe_mvp_core_provider_matrix", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def response(
    *, status: str, verified: bool, error: str | None, possible: bool = False
) -> dict[str, object]:
    return {
        "type": "operation.response",
        "status": status,
        "verified": verified,
        "errorCode": error,
        "effectMayHaveOccurred": possible,
    }


def test_memory_contract_requires_the_private_envelope_rejection() -> None:
    valid = response(
        status="rejected",
        verified=False,
        error=MODULE.PRIVATE_ENVELOPE_ERROR,
    )
    assert MODULE.valid_contract_rejection("memory.list", valid)
    assert not MODULE.valid_contract_rejection(
        "memory.list",
        response(status="failed", verified=False, error="invalid_arguments"),
    )


def test_normal_contract_requires_safe_unverified_failure() -> None:
    valid = response(status="failed", verified=False, error="invalid_arguments")
    assert MODULE.valid_contract_rejection("system.time", valid)
    assert not MODULE.valid_contract_rejection(
        "system.time",
        response(
            status="failed",
            verified=False,
            error="invalid_arguments",
            possible=True,
        ),
    )


def test_read_only_terminal_requires_coherent_verification() -> None:
    assert MODULE.valid_read_only_terminal(
        response(status="completed", verified=True, error=None)
    )
    assert MODULE.valid_read_only_terminal(
        response(status="failed", verified=False, error="target_not_found")
    )
    assert not MODULE.valid_read_only_terminal(
        response(status="completed", verified=False, error=None)
    )
    assert not MODULE.valid_read_only_terminal(
        response(status="failed", verified=True, error="target_not_found")
    )


def test_schema_sampler_is_bounded_and_inert() -> None:
    schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1},
            "enabled": {"type": "boolean"},
        },
        "required": ["url", "limit", "enabled"],
    }
    assert MODULE.sample(schema) == {
        "url": "https://example.com/",
        "limit": 1,
        "enabled": False,
    }
