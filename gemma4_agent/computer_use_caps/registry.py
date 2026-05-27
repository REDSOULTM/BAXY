"""Computer-use adapter registry.

This registry describes app families and their supported layers. It is not an
intent router and it does not match user language. Selection comes from the
capability snapshot: process/window class/UIA/CDP availability.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AdapterSpec:
    family: str
    app_kinds: tuple[str, ...]
    primary_layers: tuple[str, ...]
    fallback_layers: tuple[str, ...]
    supported_ops: tuple[str, ...]
    verifier: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("app_kinds", "primary_layers", "fallback_layers", "supported_ops"):
            data[key] = list(data[key])
        return data


ADAPTER_SPECS: dict[str, AdapterSpec] = {
    "browser": AdapterSpec(
        family="browser",
        app_kinds=("browser",),
        primary_layers=("browser_cdp", "browser_accessibility"),
        fallback_layers=("uia", "ocr", "vision"),
        supported_ops=("open_url", "click", "type", "fill_field", "wait_for", "send", "keypress"),
        verifier="title_dom_accessibility_text",
        notes="Use structured browser protocol when available; UIA/OCR/vision are fallbacks.",
    ),
    "native_uia": AdapterSpec(
        family="native_uia",
        app_kinds=("native_or_unknown", "office", "winui_uwp", "explorer_shell"),
        primary_layers=("uia_control_pattern", "uia_probe"),
        fallback_layers=("ocr", "vision"),
        supported_ops=("focus_app", "click", "fill_field", "toggle", "wait_for", "type", "send", "keypress"),
        verifier="uia_patterns_and_window_state",
        notes="Prefer Invoke/Value/Toggle/Selection patterns over coordinates.",
    ),
    "electron_or_webview": AdapterSpec(
        family="electron_or_webview",
        app_kinds=("electron_or_webview",),
        primary_layers=("uia_probe", "ocr"),
        fallback_layers=("vision",),
        supported_ops=("click", "fill_field", "toggle", "wait_for", "type", "send", "keypress"),
        verifier="uia_or_ocr_or_vision_state",
        notes="Chromium shells often expose partial UIA; verify after every action.",
    ),
    "app_specialist": AdapterSpec(
        family="app_specialist",
        app_kinds=("specialist",),
        primary_layers=("app_specialist",),
        fallback_layers=("uia", "ocr", "vision"),
        supported_ops=("focus_app", "open_chat", "open_voice", "discord_control"),
        verifier="domain_specific_state",
        notes="Specialists own app-specific flows; generic UI remains fallback.",
    ),
    "unknown": AdapterSpec(
        family="unknown",
        app_kinds=("unknown",),
        primary_layers=("uia_probe",),
        fallback_layers=("ocr", "vision"),
        supported_ops=("click", "fill_field", "toggle", "wait_for", "type", "send", "keypress"),
        verifier="post_action_state_only",
        notes="Never claim success without a structural or visual verifier.",
    ),
}


def family_for_snapshot(snapshot: dict[str, Any] | None) -> str:
    snap = snapshot or {}
    if bool(snap.get("is_browser")):
        return "browser"
    app_kind = str(snap.get("app_kind") or "unknown")
    if app_kind == "electron_or_webview":
        return "electron_or_webview"
    if app_kind in {"native_or_unknown", "office", "winui_uwp", "explorer_shell"}:
        return "native_uia"
    return "unknown"


def spec_for_snapshot(snapshot: dict[str, Any] | None) -> AdapterSpec:
    return ADAPTER_SPECS.get(family_for_snapshot(snapshot), ADAPTER_SPECS["unknown"])


__all__ = ["ADAPTER_SPECS", "AdapterSpec", "family_for_snapshot", "spec_for_snapshot"]
