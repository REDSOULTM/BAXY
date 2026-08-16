from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "build_mswc_spanish_qbye_sequence_research_v3.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_mswc_spanish_qbye_sequence_research_v3", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_sequence_research_selection_excludes_and_requires_speakers() -> None:
    training = {
        "prior": [
            {"SPEAKER": f"p{i}", "WORD": "prior", "LINK": f"prior/{i}.opus"}
            for i in range(4)
        ],
        "valid": [
            {"SPEAKER": f"v{i}", "WORD": "valid", "LINK": f"valid/{i}.opus"}
            for i in range(4)
        ],
        "sparse": [
            {"SPEAKER": "one", "WORD": "sparse", "LINK": "sparse/one.opus"}
        ],
    }
    selected = MODULE.select_research_words(
        training,
        excluded={"prior"},
        count=1,
        examples_per_class=4,
        seed=1,
    )
    assert selected == ["valid"]
