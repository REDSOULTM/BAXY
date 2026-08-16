from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from experiments.mind_router_spike import (
    analyze_catalog_surface_current_tree_r2 as aggregate,
)
from experiments.mind_router_spike import (
    build_catalog_surface_current_tree_r1 as r1,
)
from experiments.mind_router_spike import (
    build_catalog_surface_current_tree_r2 as campaign,
)
from experiments.mind_router_spike import (
    probe_catalog_surface_current_tree_r2 as probe,
)
from scripts import build_catalog_surface_holdout_r22 as builder
from scripts.build_generalization_product_holdout_r2 import normalize_text


def _capabilities() -> list[dict[str, object]]:
    return [
        {
            "name": name,
            "description": f"Authenticated test surface for {name}",
            "argumentsSchema": {"type": "object", "properties": {}},
            "risk": "test",
        }
        for name in sorted(builder.SEEN_UTTERANCES)
    ]


def test_current_tree_r2_is_unique_and_disjoint_from_r1(
    tmp_path: Path,
    monkeypatch,
) -> None:
    r1_rows = [
        {
            "text": r1._fresh_surface(language, text),
        }
        for language, text in builder.SEEN_UTTERANCES.values()
    ]
    prior = tmp_path / "consumed-r1.jsonl"
    prior.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in r1_rows),
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.setattr(builder, "CAMPAIGN", "current-tree-r2-test")
    monkeypatch.setattr(builder, "ROW_SCHEMA", "baxy.test.current-tree-r2")
    monkeypatch.setattr(
        builder,
        "SURFACE_NAME",
        "cross_language_request_completion_grammar",
    )
    monkeypatch.setattr(builder, "PRIOR_CORPORA", (prior,))
    monkeypatch.setattr(builder, "_fresh_surface", campaign._fresh_surface)

    rows = builder.build_rows(_capabilities())
    normalized = {normalize_text(str(row["text"])) for row in rows}
    normalized_r1 = {normalize_text(str(row["text"])) for row in r1_rows}

    assert len(rows) == 169
    assert len(normalized) == 169
    assert normalized.isdisjoint(normalized_r1)
    assert {str(row["target_operation"]) for row in rows} == set(
        builder.SEEN_UTTERANCES
    )
    assert Counter(row["owner"] for row in rows) == {
        "mind_sidecar": 158,
        "app_private_memory_parser": 11,
    }
    assert all(row["blind_holdout"] is True for row in rows)
    assert all(row["execution_authority"] is False for row in rows)
    assert all(
        any(
            str(row["text"]).endswith(closure)
            for closure in campaign._CLOSURES[str(row["language"])]
        )
        for row in rows
    )


def test_current_tree_r2_configuration_binds_r1_and_measurement_program(
    monkeypatch,
) -> None:
    configured_names = (
        "OUTPUT",
        "PREREGISTRATION",
        "MIND_OUTPUT",
        "MIND_AUDIT",
        "MEMORY_TRX",
        "PRODUCT_OUTPUT",
        "CAMPAIGN",
        "BUILDER_SOURCE",
        "ROW_SCHEMA",
        "PREREGISTRATION_SCHEMA",
        "SURFACE_NAME",
        "METHOD_MATRIX",
        "BUILDER_DEPENDENCIES",
        "MEASUREMENT_SOURCES",
        "POLICY_SOURCES",
        "PRIOR_CORPORA",
        "_fresh_surface",
    )
    for name in configured_names:
        monkeypatch.setattr(builder, name, getattr(builder, name))

    campaign.configure()

    assert builder.CAMPAIGN == "current-tree-r2"
    assert builder.OUTPUT == campaign.OUTPUT
    assert builder.PREREGISTRATION == campaign.PREREGISTRATION
    assert builder._fresh_surface is campaign._fresh_surface
    assert r1.OUTPUT in builder.PRIOR_CORPORA
    assert Path(r1.__file__).resolve() in builder.BUILDER_DEPENDENCIES
    assert all(path.is_file() for path in builder.MEASUREMENT_SOURCES)
    assert all(path.is_file() for path in builder.POLICY_SOURCES)
    assert {
        campaign.OUTPUT,
        campaign.PREREGISTRATION,
        campaign.MIND_OUTPUT,
        campaign.MIND_AUDIT,
        campaign.MEMORY_TRX,
        campaign.PRODUCT_OUTPUT,
    }.isdisjoint(
        {
            r1.OUTPUT,
            r1.PREREGISTRATION,
            r1.MIND_OUTPUT,
            r1.MIND_AUDIT,
            r1.MEMORY_TRX,
            r1.PRODUCT_OUTPUT,
        }
    )


def test_current_tree_r2_probe_and_analyzer_cannot_route_to_r1(monkeypatch) -> None:
    builder_names = (
        "OUTPUT",
        "PREREGISTRATION",
        "MIND_OUTPUT",
        "MIND_AUDIT",
        "MEMORY_TRX",
        "PRODUCT_OUTPUT",
        "CAMPAIGN",
        "BUILDER_SOURCE",
        "ROW_SCHEMA",
        "PREREGISTRATION_SCHEMA",
        "SURFACE_NAME",
        "METHOD_MATRIX",
        "BUILDER_DEPENDENCIES",
        "MEASUREMENT_SOURCES",
        "POLICY_SOURCES",
        "PRIOR_CORPORA",
        "_fresh_surface",
    )
    probe_names = (
        "BUILDER_DEPENDENCIES",
        "MEASUREMENT_SOURCES",
        "AUDIT",
        "OUTPUT",
        "CORPUS",
        "POLICY_SOURCES",
        "PREREGISTRATION",
        "BUILDER",
        "CAMPAIGN",
        "RESULT_SCHEMA",
        "RESULT_SCOPE",
        "TOTAL_CASES",
        "MIND_CASES",
        "MEMORY_CASES",
    )
    analyzer_names = (
        "MEASUREMENT_SOURCES",
        "MEMORY_TRX",
        "MIND_OUTPUT",
        "CORPUS",
        "OUTPUT",
        "POLICY_SOURCES",
        "PREREGISTRATION",
        "CAMPAIGN",
        "RESULT_SCHEMA",
        "RESULT_SCOPE",
        "MEMORY_TEST_PREFIX",
        "TOTAL_CASES",
        "MIND_CASES",
        "MEMORY_CASES",
    )
    for owner, names in (
        (builder, builder_names),
        (probe.runner, probe_names),
        (aggregate.analyzer, analyzer_names),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, getattr(owner, name))

    probe.configure()
    aggregate.configure()

    assert probe.runner.CORPUS == campaign.OUTPUT
    assert probe.runner.PREREGISTRATION == campaign.PREREGISTRATION
    assert probe.runner.OUTPUT == campaign.MIND_OUTPUT
    assert probe.runner.AUDIT == campaign.MIND_AUDIT
    assert probe.runner.BUILDER == Path(campaign.__file__).resolve()
    assert aggregate.analyzer.CORPUS == campaign.OUTPUT
    assert aggregate.analyzer.PREREGISTRATION == campaign.PREREGISTRATION
    assert aggregate.analyzer.MIND_OUTPUT == campaign.MIND_OUTPUT
    assert aggregate.analyzer.MEMORY_TRX == campaign.MEMORY_TRX
    assert aggregate.analyzer.OUTPUT == campaign.PRODUCT_OUTPUT
    assert probe.runner.CORPUS != r1.OUTPUT
    assert aggregate.analyzer.CORPUS != r1.OUTPUT
    assert probe.runner.TOTAL_CASES == aggregate.analyzer.TOTAL_CASES == 169
    assert probe.runner.MIND_CASES == aggregate.analyzer.MIND_CASES == 158
    assert probe.runner.MEMORY_CASES == aggregate.analyzer.MEMORY_CASES == 11
