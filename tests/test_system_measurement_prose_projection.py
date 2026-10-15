"""Measurement meaning survives the narrator boundary without mutating evidence."""

import copy

import pytest

from baxy_mind.compose_payload import _compose_situation_payload
from baxy_mind.measurement_prose_projection import project_system_measurements


GIB = 2**30


@pytest.mark.parametrize("name", ["memory", "disk"])
@pytest.mark.parametrize("total,available", [(32_000_000_000, 24_000_000_000),
                                             (16_000_000_000, 0), (1000, 1000)])
def test_used_quantity_is_derived_from_the_same_snapshot(name, total, available):
    # v3 r5a M4: RAM and disk sizes in Windows' unit (2**30 bytes labelled «GB»), the figure the person sees.
    seen = {name: {"totalBytes": total, "availableBytes": available}, "failures": []}
    original = copy.deepcopy(seen)
    result = project_system_measurements(seen)[name]
    assert result["used"] == {"value": round((total - available) / GIB, 4), "unit": "GB"}
    assert result["free"] == {"value": round(available / GIB, 4), "unit": "GB"}
    assert result["total"] == {"value": round(total / GIB, 4), "unit": "GB"}
    assert "totalBytes" not in result
    assert seen == original


@pytest.mark.parametrize("installed", [None, 0, 8 * GIB, True, 16 * GIB, 32 * GIB])
def test_installed_ram_is_never_inferred_from_usable_ram(installed):
    result = project_system_measurements({"memory": {
        "totalBytes": 15 * GIB, "availableBytes": 3 * GIB, "installedBytes": installed,
    }})["memory"]
    assert result["used"]["value"] == 12
    assert result["total"]["value"] == 15
    assert result["installed_capacity"] == (
        {"value": installed // GIB, "unit": "GB"} if installed in (16 * GIB, 32 * GIB) else None
    )


def test_v3_45_installed_ram_is_told_as_windows_shows_it():
    # v3 r5a M4 (v3-45): 17179869184 bytes are «16 GB» in Windows' own window, never «17,18 GB».
    result = project_system_measurements({"memory": {
        "totalBytes": 17_101_000_000, "availableBytes": 6_000_000_000, "installedBytes": 17_179_869_184,
    }})["memory"]
    assert result["installed_capacity"] == {"value": 16, "unit": "GB"}
    assert result["total"]["value"] == round(17_101_000_000 / GIB, 4)
    # Counter-case: a size that is no whole number of Windows' GB keeps its decimals.
    assert project_system_measurements({"disk": {"totalBytes": 500_000_000_000, "availableBytes": 0}})[
        "disk"]["total"] == {"value": round(500_000_000_000 / GIB, 4), "unit": "GB"}


@pytest.mark.parametrize("total,available", [(None, 0), (True, 0), (-1, 0), (10, 11),
                                             (10, -1), (10, float("nan")), (2**65, 0)])
def test_invalid_measurements_do_not_create_derived_facts(total, available):
    result = project_system_measurements({"memory": {"totalBytes": total, "availableBytes": available}})
    assert "used" not in result["memory"]


@pytest.mark.parametrize("name", ["Atlas GPU", "Órbita 29", "GPU Is Active"])
def test_engine_and_vram_usage_are_independent_and_names_and_failures_survive(name):
    # v3 r5a M4 review: GPU memory in the same unit as the RAM, the Task Manager's (2**30 bytes labelled «GB»).
    seen = {"adapters": [{"name": name, "dedicatedVideoMemoryBytes": 8 * GIB,
                          "dedicatedMemoryUsageBytes": 1 * GIB, "usagePercent": 92,
                          "sharedSystemMemoryLimitBytes": 64 * GIB,
                          "sharedMemoryUsageBytes": 0, "dedicatedSystemMemoryBytes": 0},
                         {"name": "unmeasured", "dedicatedVideoMemoryBytes": 4 * GIB}],
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


def test_everything_labelled_gb_has_one_unit():
    # v3 r5a M4 review: with 16 GiB of RAM the shared GPU memory (half of it, as Windows sizes it) was told «8,5 GB»
    # beside a RAM of «15,9 GB»; the Task Manager shows «7,9 GB». Every quantity labelled «GB» is 2**30 bytes.
    ram = 16 * GIB - 100 * 2**20
    result = project_system_measurements({
        "memory": {"totalBytes": ram, "availableBytes": 4 * GIB},
        "adapters": [{"sharedSystemMemoryLimitBytes": ram // 2, "dedicatedVideoMemoryBytes": 6 * GIB,
                      "dedicatedSystemMemoryBytes": 0, "sharedMemoryUsageBytes": GIB // 2}],
    })
    gpu = result["adapters"][0]
    assert result["memory"]["total"] == {"value": round(ram / GIB, 4), "unit": "GB"}
    assert gpu["shared_system_ram_limit"] == {"value": round(ram / 2 / GIB, 4), "unit": "GB"}
    assert gpu["dedicated_vram_capacity"] == {"value": 6, "unit": "GB"}
    assert gpu["shared_system_ram_used"] == {"value": 0.5, "unit": "GB"}
    labelled = [result["memory"][key] for key in ("total", "free", "used")] + [
        gpu[key] for key in ("shared_system_ram_limit", "dedicated_vram_capacity", "dedicated_system_ram_capacity",
                             "shared_system_ram_used")]
    assert all(item["unit"] == "GB" for item in labelled)
    # Counter-case: the shares stay percentages, never sizes.
    assert "dedicated_vram_utilization" not in gpu


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
                     "totalBytes": 15 * GIB, "availableBytes": 3 * GIB,
                     "installedBytes": 16 * GIB}}}
    original = copy.deepcopy(situation)
    result = _compose_situation_payload(situation, language, text)
    assert result["seen"]["memory"]["used"] == {"value": 12, "unit": "GB"}
    assert result["seen"]["memory"]["installed_capacity"] == {"value": 16, "unit": "GB"}
    assert situation == original
    situation["operation"] = "file.read"
    result = _compose_situation_payload(situation, language, text)
    assert result["seen"]["memory"] == situation["observed"]["memory"]
