"""Structural layer policy for computer-use actions.

The policy is intentionally small and deterministic. It does not infer user
intent from language. It only looks at the detected app/window capability and
the closed primitive the planner already selected, then records which layer
should own the action and which fallbacks are acceptable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class LayerPolicy:
    primary: str
    fallbacks: tuple[str, ...] = ()
    reason: str = ""
    risk: str = "normal"
    require_verification: bool = True
    allow_blind_pixel_click: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["fallbacks"] = list(self.fallbacks)
        return data


_BROWSER_OPS = frozenset({
    "open_url", "click", "type", "fill_field", "toggle", "wait_for", "send", "keypress",
})
_UI_STRUCTURAL_OPS = frozenset({
    "click", "fill_field", "toggle", "wait_for", "type", "send", "keypress", "scroll",
})
_APP_SPECIALIST_OPS = frozenset({
    "focus_app", "open_chat", "open_voice", "discord_control",
})


def _available_fallbacks(ocr_available: bool, vision_available: bool) -> tuple[str, ...]:
    layers: list[str] = []
    if ocr_available:
        layers.append("ocr")
    if vision_available:
        layers.append("vision")
    return tuple(layers)


def _visual_primary(ocr_available: bool, vision_available: bool) -> str:
    if ocr_available:
        return "ocr"
    if vision_available:
        return "vision"
    return "honest_fail"


def choose_policy(snapshot: dict[str, Any] | None, op: str) -> LayerPolicy:
    """Choose API/UIA/OCR/vision order from observable capability state.

    This function is safe to call in tests and dry-run evals. It never touches
    the desktop; the snapshot was already collected by ``CapabilityDetector``.
    """
    snap = snapshot or {}
    app_kind = str(snap.get("app_kind") or "unknown")
    is_browser = bool(snap.get("is_browser"))
    cdp_candidate = bool(snap.get("cdp_candidate"))
    uia_available = snap.get("uia_available")
    uia_degraded = bool(snap.get("uia_degraded"))
    ocr_available = snap.get("ocr_available") is not False
    vision_available = snap.get("vision_fallback_available") is not False
    visual_fallbacks = _available_fallbacks(ocr_available, vision_available)

    if op in _APP_SPECIALIST_OPS:
        return LayerPolicy(
            primary="app_specialist",
            fallbacks=("uia", *visual_fallbacks),
            reason="closed primitive has a specialist adapter",
            risk="low",
        )

    if is_browser and op in _BROWSER_OPS:
        if cdp_candidate:
            return LayerPolicy(
                primary="browser_cdp",
                fallbacks=("uia", *visual_fallbacks),
                reason="browser window can use structured browser protocol",
                risk="low",
            )
        return LayerPolicy(
            primary="browser_accessibility",
            fallbacks=("uia", *visual_fallbacks),
            reason="browser window without CDP candidate; use accessibility before pixels",
            risk="medium",
        )

    if op in _UI_STRUCTURAL_OPS:
        if uia_available is True and not uia_degraded:
            return LayerPolicy(
                primary="uia_control_pattern",
                fallbacks=visual_fallbacks,
                reason="UIA exposes a usable control tree",
                risk="low",
            )
        if uia_available is True and uia_degraded:
            return LayerPolicy(
                primary=_visual_primary(ocr_available, vision_available),
                fallbacks=("vision",) if ocr_available and vision_available else (),
                reason="UIA tree is present but degraded for this window",
                risk="medium",
            )
        if app_kind in {"electron_or_webview", "winui_uwp"}:
            return LayerPolicy(
                primary="uia_probe",
                fallbacks=visual_fallbacks,
                reason="webview/native shell may expose partial UIA; probe before pixels",
                risk="medium",
            )
        return LayerPolicy(
            primary="uia_probe",
            fallbacks=visual_fallbacks,
            reason="unknown native UI; inspect UIA before fallback layers",
            risk="medium",
        )

    return LayerPolicy(
        primary="generic_verified",
        fallbacks=("uia", *visual_fallbacks),
        reason="generic primitive still requires post-action verification",
        risk="normal",
    )


__all__ = ["LayerPolicy", "choose_policy"]
