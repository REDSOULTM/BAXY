"""Derive narrator quantities from typed system.status measurements.

The canonical byte observations stay unchanged. Decimal GB prevents a binary
quantity from being narrated as gigabytes; engine load and VRAM occupancy have
different names because they measure different things.
"""

from __future__ import annotations

import math
from typing import Any


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
