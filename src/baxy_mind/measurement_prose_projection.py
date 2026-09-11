"""Derive narrator quantities from typed system.status measurements.

The canonical byte observations stay unchanged. Decimal GB prevents a binary
quantity from being narrated as gigabytes; engine load and VRAM occupancy have
different names because they measure different things.
"""

from __future__ import annotations

import math
import re
from typing import Any

from .request_reading import fold


def _byte_count(value: object) -> bool:
    return type(value) is int and 0 <= value <= 2**64 - 1


def _quantity(value: int | float, unit: str = "GB") -> dict[str, Any]:
    return {"value": round(value / 10**9 if unit == "GB" else value, 4), "unit": unit}


def project_system_measurements(seen: dict[str, Any]) -> dict[str, Any]:
    """Project only known measurement fields, preserving partial observations."""
    result = dict(seen)
    for name in ("memory", "disk"):
        values = seen.get(name)
        if not isinstance(values, dict):
            continue
        total, available = values.get("totalBytes"), values.get("availableBytes")
        if _byte_count(total) and _byte_count(available) and available <= total:
            projected = {k: v for k, v in values.items() if k not in {
                "totalBytes", "availableBytes", "installedBytes",
            }}
            projected.update(total_usable=_quantity(total), available=_quantity(available),
                             used=_quantity(total - available))
            if name == "memory":
                installed = values.get("installedBytes")
                projected["installed_capacity"] = (
                    _quantity(installed) if _byte_count(installed) and installed >= total else None
                )
            result[name] = projected
    adapters = seen.get("adapters")
    if not isinstance(adapters, list):
        return result
    names = {
        "dedicatedVideoMemoryBytes": "dedicated_vram_capacity",
        "dedicatedMemoryUsageBytes": "dedicated_vram_used",
        "sharedSystemMemoryLimitBytes": "shared_system_ram_limit",
        "sharedMemoryUsageBytes": "shared_system_ram_used",
        "dedicatedSystemMemoryBytes": "dedicated_system_ram_capacity",
    }
    projected_adapters = []
    for adapter in adapters:
        if not isinstance(adapter, dict):
            projected_adapters.append(adapter)
            continue
        projected = dict(adapter)
        for old, new in names.items():
            value = adapter.get(old)
            if _byte_count(value):
                projected[new] = _quantity(value)
                projected.pop(old)
        engine = adapter.get("usagePercent")
        if type(engine) in (int, float) and math.isfinite(engine) and 0 <= engine <= 100:
            projected["gpu_engine_utilization"] = _quantity(engine, "%")
            projected.pop("usagePercent")
        total = adapter.get("dedicatedVideoMemoryBytes")
        used = adapter.get("dedicatedMemoryUsageBytes")
        if _byte_count(total) and total > 0 and _byte_count(used) and used <= total:
            projected["dedicated_vram_utilization"] = _quantity(100 * used / total, "%")
        projected_adapters.append(projected)
    result["adapters"] = projected_adapters
    return result


def project_process_measurements(seen: dict[str, Any], user_text: str) -> dict[str, Any]:
    """Separate observed count, returned instances and the requested resource."""
    result = dict(seen)
    if seen.get("observationScope") == "accessible_processes":
        # Describe the provider's boundary without exposing its enum to narration.
        result["observationScope"] = (
            "processes accessible during this observation; "
            "completeness for the whole PC is not established"
        )
    request = fold(user_text)
    count_request = re.search(
        r"\b(?:cuantos|cuenta|cantidad|numero|how many|count)\b", request,
    ) is not None
    also_list = re.search(r"\b(?:lista(?:los)?|list|show|muestra(?:los|me)?)\b", request)
    count_only = count_request and (not also_list or re.search(
        r"\b(?:sin listarlos|without listing|do not list)\b", request,
    ))
    if count_only:
        # Ten returned rows say nothing about a count of two hundred observed.
        # Keep the authoritative count and its scope without an irrelevant list.
        return {key: value for key, value in result.items() if key in {
            "observedProcessCount", "observationScope",
        }}
    rows = seen.get("processes")
    if not isinstance(rows, list):
        return result
    projected_rows = []
    for row in rows:
        if not isinstance(row, dict):
            projected_rows.append(row)
            continue
        projected = {key: value for key, value in row.items() if key not in {
            "totalProcessorSeconds", "workingSetBytes", "cpuUsagePercent", "sampleDurationSeconds",
        }}
        memory = row.get("workingSetBytes")
        if seen.get("sort") != "cpu" and _byte_count(memory):
            projected["resident_memory"] = _quantity(memory / 10**6, "MB")
        cpu = row.get("cpuUsagePercent")
        if seen.get("sort") == "cpu" and type(cpu) in (int, float) and math.isfinite(cpu):
            projected["current_cpu_usage"] = _quantity(cpu, "%")
            projected["sampleDurationSeconds"] = row.get("sampleDurationSeconds")
        if re.search(r"\b(?:acumulad[oa]|cumulative|lifetime|total processor seconds)\b", request):
            projected["lifetime_cpu_time_seconds"] = row.get("totalProcessorSeconds")
        projected_rows.append(projected)
    result["processes"] = projected_rows
    return result
