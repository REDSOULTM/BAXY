"""Internal capabilities for the public ``computer_use`` compound tool.

These are not top-level tools exposed to the LLM. They keep the public contract
as ``computer_use(goal=...)`` while separating domain execution inside the plan
executor.
"""
from __future__ import annotations

from .apps import AppCapability
from .browser import BrowserCapability
from .detector import CapabilityDetector, CapabilitySnapshot
from .discord import DiscordCapability
from .generic_ui import GenericUICapability
from .policy import LayerPolicy, choose_policy
from .registry import ADAPTER_SPECS, AdapterSpec, family_for_snapshot, spec_for_snapshot
from .router import CapabilityRouter

__all__ = [
    "AppCapability",
    "BrowserCapability",
    "CapabilityDetector",
    "CapabilitySnapshot",
    "CapabilityRouter",
    "DiscordCapability",
    "GenericUICapability",
    "LayerPolicy",
    "ADAPTER_SPECS",
    "AdapterSpec",
    "choose_policy",
    "family_for_snapshot",
    "spec_for_snapshot",
]
