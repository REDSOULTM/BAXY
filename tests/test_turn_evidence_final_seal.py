from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "seal_turn_evidence_final_subset.py"
SPEC = importlib.util.spec_from_file_location("seal_turn_evidence_final_subset", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
seal = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = seal
SPEC.loader.exec_module(seal)


def test_seal_uses_only_ids_and_is_reproducible(tmp_path: Path) -> None:
    holdout = tmp_path / "holdout.jsonl"
    rows = [
        {
            "split": "validation",
            "source_id": "validation",
            "text": "must not enter seal",
            "mode": "action",
        },
        *[
            {
                "split": "test",
                "source_id": f"test-{index}",
                "text": f"private literal {index}",
                "mode": "conversation",
                "families": [],
            }
            for index in range(20)
        ],
    ]
    holdout.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    first = seal.build_seal(holdout)
    second = seal.build_seal(holdout)
    encoded = json.dumps(first)

    assert first == second
    assert first["contains_text_or_labels"] is False
    assert first["final"]["source_ids"] == sorted(
        first["final"]["source_ids"]
    )
    assert first["final"]["rows"] + first["exploratory_complement"]["rows"] == 20
    assert "private literal" not in encoded
    assert '"mode"' not in encoded
