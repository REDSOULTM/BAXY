from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT / "experiments" / "wake_validation" / "validate_physical_wake_v17_program.py"
)
SPEC = importlib.util.spec_from_file_location("wake_v17_program", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _records(
    count: int, flag: str, *, hit: bool, prefix: str
) -> list[dict[str, object]]:
    return [
        {
            "record": index,
            "audioSha256": f"{prefix}{index:063x}"[-64:],
            flag: hit,
        }
        for index in range(count)
    ]


def _group(count: int, flag: str, *, hit: bool, prefix: str) -> dict[str, object]:
    return {
        "files": count,
        "records": _records(count, flag, hit=hit, prefix=prefix),
    }


def test_validate_group_accepts_an_identity_preserving_or_policy() -> None:
    cascade = _group(3, "accepted", hit=True, prefix="a")
    endpoint = _group(3, "hit", hit=False, prefix="a")
    fusion_records = [
        {
            "record": row["record"],
            "audioSha256": row["audioSha256"],
            "cascade": True,
            "endpoint": False,
            "cascadeOrEndpoint": True,
            "cascadeAndEndpoint": False,
        }
        for row in cascade["records"]
    ]
    fusion = {
        "files": 3,
        "records": fusion_records,
        "policies": {"cascadeOrEndpoint": {"hits": 3, "files": 3, "rate": 1.0}},
    }

    hits, identities = module._validate_group(cascade, endpoint, fusion, expected=3)

    assert hits == 3
    assert len(identities) == 3


def test_validate_group_rejects_cross_report_audio_mismatch() -> None:
    cascade = _group(1, "accepted", hit=True, prefix="a")
    endpoint = _group(1, "hit", hit=False, prefix="b")
    fusion = {
        "files": 1,
        "records": [
            {
                "record": 0,
                "audioSha256": cascade["records"][0]["audioSha256"],
                "cascade": True,
                "endpoint": False,
                "cascadeOrEndpoint": True,
                "cascadeAndEndpoint": False,
            }
        ],
        "policies": {"cascadeOrEndpoint": {"hits": 1, "files": 1, "rate": 1.0}},
    }

    with pytest.raises(ValueError, match="identity-preserving"):
        module._validate_group(cascade, endpoint, fusion, expected=1)


def test_validate_group_rejects_a_false_fusion_summary() -> None:
    cascade = _group(1, "accepted", hit=False, prefix="a")
    endpoint = _group(1, "hit", hit=False, prefix="a")
    fusion = {
        "files": 1,
        "records": [
            {
                "record": 0,
                "audioSha256": cascade["records"][0]["audioSha256"],
                "cascade": False,
                "endpoint": False,
                "cascadeOrEndpoint": False,
                "cascadeAndEndpoint": False,
            }
        ],
        "policies": {"cascadeOrEndpoint": {"hits": 1, "files": 1, "rate": 1.0}},
    }

    with pytest.raises(ValueError, match="summary"):
        module._validate_group(cascade, endpoint, fusion, expected=1)


def test_current_base_preregistration_matches_every_frozen_measurement_source() -> None:
    path = (
        ROOT
        / "artifacts"
        / "development"
        / "baxy_wake_routed_cascade_v25a_reserved_physical_v17_preregistration_v1.json"
    )

    payload = module.validate_base_preregistration(path)

    assert payload["evaluationContract"]["programTree"]["sha256"] == (
        module.EXPECTED_PROGRAM_TREE_SHA256
    )


def test_write_json_exclusive_refuses_to_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "receipt.json"
    module.write_json_exclusive(output, {"first": True})

    with pytest.raises(FileExistsError):
        module.write_json_exclusive(output, {"second": True})

    assert json.loads(output.read_text(encoding="utf-8")) == {"first": True}
