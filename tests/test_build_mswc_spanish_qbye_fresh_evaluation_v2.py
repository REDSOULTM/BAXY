from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "build_mswc_spanish_qbye_fresh_evaluation_v2.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_mswc_spanish_qbye_fresh_evaluation_v2", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_fresh_selection_excludes_prior_words_and_requires_speakers() -> None:
    development = {
        "prior": [
            {"SPEAKER": f"p{index}", "WORD": "prior", "LINK": f"prior/{index}.opus"}
            for index in range(4)
        ],
        "valid": [
            {"SPEAKER": f"v{index}", "WORD": "valid", "LINK": f"valid/{index}.opus"}
            for index in range(4)
        ],
        "sparse": [
            {"SPEAKER": "one", "WORD": "sparse", "LINK": "sparse/one.opus"}
        ],
    }
    selected = MODULE.select_fresh_words(
        development,
        excluded_words={"prior"},
        count=1,
        examples_per_class=4,
        seed=1,
    )
    assert selected == ["valid"]
