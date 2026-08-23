"""Goal 07: compound missions keep every clause, ground later steps, and halt."""

from __future__ import annotations

from pathlib import Path

from baxy_mind.__main__ import (
    _explicit_arguments_from_evidence,
    _explicit_plan_skeleton,
    apply_compound_effect_conservation_veto,
)
from baxy_mind.effect_intent import (
    operation_domain_is_grounded,
    resolve_explicit_effects,
    unresolved_compound_contract,
)

REPO = Path(__file__).resolve().parents[1]
AVAILABLE = frozenset(
    {
        "app.open",
        "audio.status",
        "input.visible.click",
        "network.status",
        "note.create",
        "note.read",
        "system.status",
    }
)
APPS = ("Steam", "Notepad", "Spotify")


def test_open_then_go_to_keeps_both_steps_and_grounds_the_click_label() -> None:
    text = "Abre Steam y ve a la biblioteca"
    intent = resolve_explicit_effects(text, AVAILABLE, application_names=APPS)
    assert intent is not None
    assert intent.operations == ("app.open", "input.visible.click")
    assert unresolved_compound_contract(
        text, AVAILABLE, application_names=APPS, resolved_intent=intent
    ) is None
    skeleton = _explicit_plan_skeleton(intent.operations, intent.evidence)
    assert [step["operation"] for step in skeleton["steps"]] == [
        "app.open",
        "input.visible.click",
    ]
    click_args = _explicit_arguments_from_evidence(
        "input.visible.click",
        intent.evidence[1],
        APPS,
    )
    assert click_args == {"label": "biblioteca"}
    open_args = _explicit_arguments_from_evidence("app.open", intent.evidence[0], APPS)
    assert open_args == {"appId": "Steam"}


def test_open_then_go_to_english_and_spanglish() -> None:
    english = resolve_explicit_effects(
        "Open Steam and go to Library",
        AVAILABLE,
        application_names=APPS,
    )
    spanglish = resolve_explicit_effects(
        "Abre Steam and click Library",
        AVAILABLE,
        application_names=APPS,
    )
    assert english is not None
    assert english.operations == ("app.open", "input.visible.click")
    assert spanglish is not None
    assert spanglish.operations == ("app.open", "input.visible.click")
    assert _explicit_arguments_from_evidence(
        "input.visible.click", english.evidence[1], APPS
    ) == {"label": "library"}


def test_dependent_clause_keeps_the_governing_head() -> None:
    text = (
        "Reporta el estado del audio, el estado del sistema y termina "
        "con el estado de la red."
    )
    intent = resolve_explicit_effects(text, AVAILABLE)
    assert intent is not None
    assert intent.operations == (
        "audio.status",
        "system.status",
        "network.status",
    )
    assert unresolved_compound_contract(text, AVAILABLE, resolved_intent=intent) is None


def test_unrecognized_second_clause_does_not_run_as_silent_subset() -> None:
    text = "Abre Steam y envía un mensaje a Ana"
    assert resolve_explicit_effects(text, AVAILABLE, application_names=APPS) is None
    contract = unresolved_compound_contract(text, AVAILABLE, application_names=APPS)
    assert contract is not None
    assert contract.minimum_effects >= 2
    vetoed = apply_compound_effect_conservation_veto(
        {
            "mode": "plan",
            "operation": "app.open",
            "effect_operations": ["app.open"],
            "effect_count": "one",
            "effect_verification": "pending",
        },
        contract,
    )
    assert vetoed["mode"] == "conversation"
    assert vetoed["effect_operations"] == []


def test_click_domain_accepts_go_to_after_an_open_and_rejects_a_coat_button() -> None:
    assert operation_domain_is_grounded(
        "ve a la biblioteca",
        "input.visible.click",
    ) is True
    assert operation_domain_is_grounded(
        "Sew the button on my coat.",
        "input.visible.click",
    ) is False


def test_web_destination_is_not_a_visible_click() -> None:
    intent = resolve_explicit_effects(
        "Abre Chrome y ve a wikipedia",
        AVAILABLE,
        application_names=("Chrome", "Steam"),
    )
    if intent is not None:
        assert "input.visible.click" not in intent.operations


def test_visible_click_cascade_source_has_no_app_names() -> None:
    files = (
        REPO / "src/Baxy.Providers.Windows/External/DesktopClickVisible.ps1",
        REPO / "src/Baxy.Providers.Windows/External/WindowsVisibleControlAdapter.cs",
        REPO / "src/Baxy.Providers.Windows/External/WindowsVisibleOcrLocator.cs",
        REPO / "src/Baxy.Providers.Windows/External/WindowsVisibleVisionLocator.cs",
        REPO / "src/Baxy.Providers.Windows/External/VisibleControlSurface.cs",
    )
    banned = ("steam", "spotify", "discord", "chrome")
    for path in files:
        text = path.read_text(encoding="utf-8").casefold()
        for name in banned:
            assert name not in text, f"{path.name} hardcodes {name}"
    script = files[0].read_text(encoding="utf-8")
    assert "Start-Sleep -Milliseconds 400" in script
    assert "SelectionItemPattern" in script
    adapter = files[1].read_text(encoding="utf-8")
    ocr_index = adapter.index("_ocr")
    vision_index = adapter.index("_vision")
    assert ocr_index < vision_index
