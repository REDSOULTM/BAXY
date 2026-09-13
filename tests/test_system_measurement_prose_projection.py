"""Measurement meaning survives the narrator boundary without mutating evidence."""

import copy

import pytest

from baxy_mind.llm import _compose_situation_payload
from baxy_mind.measurement_prose_projection import project_system_measurements


@pytest.mark.parametrize("name", ["memory", "disk"])
@pytest.mark.parametrize("total,available", [(32_000_000_000, 24_000_000_000),
                                             (16_000_000_000, 0), (1000, 1000)])
def test_used_quantity_is_derived_from_the_same_snapshot(name, total, available):
    seen = {name: {"totalBytes": total, "availableBytes": available}, "failures": []}
    original = copy.deepcopy(seen)
    result = project_system_measurements(seen)[name]
    assert result["used"] == {"value": round((total - available) / 10**9, 4), "unit": "GB"}
    assert result["free"] == {"value": round(available / 10**9, 4), "unit": "GB"}
    assert result["total"] == {"value": round(total / 10**9, 4), "unit": "GB"}
    assert "totalBytes" not in result
    assert seen == original


@pytest.mark.parametrize("installed", [None, 0, 8_000_000_000, True, 16_000_000_000, 32_000_000_000])
def test_installed_ram_is_never_inferred_from_usable_ram(installed):
    result = project_system_measurements({"memory": {
        "totalBytes": 15_000_000_000, "availableBytes": 3_000_000_000, "installedBytes": installed,
    }})["memory"]
    assert result["used"]["value"] == 12
    assert result["total"]["value"] == 15
    assert result["installed_capacity"] == (
        {"value": installed / 10**9, "unit": "GB"} if installed in (16_000_000_000, 32_000_000_000) else None
    )


@pytest.mark.parametrize("total,available", [(None, 0), (True, 0), (-1, 0), (10, 11),
                                             (10, -1), (10, float("nan")), (2**65, 0)])
def test_invalid_measurements_do_not_create_derived_facts(total, available):
    result = project_system_measurements({"memory": {"totalBytes": total, "availableBytes": available}})
    assert "used" not in result["memory"]


@pytest.mark.parametrize("name", ["Atlas GPU", "Órbita 29", "GPU Is Active"])
def test_engine_and_vram_usage_are_independent_and_names_and_failures_survive(name):
    seen = {"adapters": [{"name": name, "dedicatedVideoMemoryBytes": 8_000_000_000,
                          "dedicatedMemoryUsageBytes": 1_000_000_000, "usagePercent": 92,
                          "sharedSystemMemoryLimitBytes": 64_000_000_000,
                          "sharedMemoryUsageBytes": 0, "dedicatedSystemMemoryBytes": 0},
                         {"name": "unmeasured", "dedicatedVideoMemoryBytes": 4_000_000_000}],
            "failures": [{"adapter": "unmeasured", "error": "measurement_failed"}]}
    original = copy.deepcopy(seen)
    result = project_system_measurements(seen)
    gpu, unknown = result["adapters"]
    assert gpu["name"] == name
    assert gpu["gpu_engine_utilization"] == {"value": 92, "unit": "%"}
    assert gpu["dedicated_vram_utilization"] == {"value": 12.5, "unit": "%"}
    assert gpu["dedicated_vram_capacity"] == {"value": 8, "unit": "GB"}
    assert gpu["shared_system_ram_limit"] == {"value": 64, "unit": "GB"}
    assert "dedicated_vram_used" not in unknown
    assert "gpu_engine_utilization" not in unknown
    assert result["failures"] == seen["failures"]
    assert seen == original


@pytest.mark.parametrize("total,used,engine", [(0, 0, None), (10, 11, float("inf")),
                                              (10, -1, float("nan")), (10, True, True)])
def test_zero_missing_or_invalid_capacity_does_not_produce_utilization(total, used, engine):
    gpu = project_system_measurements({"adapters": [{"dedicatedVideoMemoryBytes": total,
        "dedicatedMemoryUsageBytes": used, "usagePercent": engine}]})["adapters"][0]
    assert "dedicated_vram_utilization" not in gpu
    assert "gpu_engine_utilization" not in gpu


@pytest.mark.parametrize("language,text", [("es", "¿Cuánta RAM está en uso?"),
                                         ("en", "How much RAM is used?"),
                                         ("mixed", "RAM usada ahora please")])
def test_real_compositor_boundary_projects_measurements_in_every_language(language, text):
    situation = {"kind": "operation", "operation": "system.status", "succeeded": True,
                 "verified": True, "observed": {"memory": {
                     "totalBytes": 15_000_000_000, "availableBytes": 3_000_000_000,
                     "installedBytes": 16_000_000_000}}}
    original = copy.deepcopy(situation)
    result = _compose_situation_payload(situation, language, text)
    assert result["seen"]["memory"]["used"] == {"value": 12, "unit": "GB"}
    assert result["seen"]["memory"]["installed_capacity"] == {"value": 16, "unit": "GB"}
    assert situation == original
    situation["operation"] = "file.read"
    result = _compose_situation_payload(situation, language, text)
    assert result["seen"]["memory"] == situation["observed"]["memory"]
