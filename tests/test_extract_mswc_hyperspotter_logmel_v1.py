from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "extract_mswc_hyperspotter_logmel_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "extract_mswc_hyperspotter_logmel_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_logmel_selection_is_bounded_per_class_and_partition() -> None:
    records = [
        {
            "class_name": class_name,
            "partition": partition,
            "source_link": f"{class_name}/{index}.opus",
        }
        for class_name in ("casa", "mundo")
        for partition in ("metric_training", "open_keyword_query")
        for index in range(4)
    ]
    selected = MODULE.select_records(
        records,
        partitions={"metric_training"},
        examples_per_class=2,
        seed=1,
    )
    assert len(selected) == 4
    assert {record["partition"] for record in selected} == {"metric_training"}
    assert all(
        sum(item["class_name"] == class_name for item in selected) == 2
        for class_name in ("casa", "mundo")
    )
