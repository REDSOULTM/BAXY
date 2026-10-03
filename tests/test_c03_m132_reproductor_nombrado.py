"""M132 — owner script t22 (rounds v4j, v4k, v4l): «Sabes que peli estoy viendo en potplayer?».

M103 sends a question about what a named player shows to that player's window (window.resolve), but on the owner's
PC the Start menu lists «Uninstall PotPlayer-64 bit» beside «PotPlayer 64 bit»: the bare name «potplayer» tied
between the two, named neither, and the turn fell back to the media session (media.status → «no se pudo acceder a
la información de PotPlayer»). An uninstaller entry is never the application a person names; it is the one only
when they say uninstall. The click half of M132 (t36/t38/t42) is pinned in the provider tests
(``ExternalAdaptersTests.VisibleClick*``).
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.arguments import _explicit_arguments_from_evidence
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.patterns import application_shown_media_name, resolve_application_catalog_app_id

# The owner's Start menu, as listed on this PC (uninstallers included).
APPS = (
    "PotPlayer 64 bit",
    "Uninstall PotPlayer-64 bit",
    "Steam",
    "Steam Support Center",
    "Spotify",
    "Node.js",
    "Uninstall Node.js",
    "VLC media player",
)
READS = frozenset({"app.open", "media.status", "window.resolve", "window.application.status"})


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("Sabes que peli estoy viendo en potplayer?", "PotPlayer 64 bit"),  # the guion's words
        ("¿qué serie tengo puesta en el potplayer?", "PotPlayer 64 bit"),
        ("what am I watching on potplayer", "PotPlayer 64 bit"),
        ("qué canción suena en spotify", None),  # Spotify keeps its media session
    ],
)
def test_a_player_with_an_uninstaller_beside_it_is_still_named(text: str, name: str | None) -> None:
    assert application_shown_media_name(text, APPS) == name


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("abre potplayer", "PotPlayer 64 bit"),
        ("abre el potplayer", "PotPlayer 64 bit"),
        ("abre node.js", "Node.js"),
        # Saying uninstall names the uninstaller.
        ("abre uninstall potplayer", "Uninstall PotPlayer-64 bit"),
    ],
)
def test_the_uninstaller_is_named_only_by_saying_uninstall(text: str, name: str) -> None:
    assert resolve_application_catalog_app_id(text, APPS) == name


def test_the_window_read_names_the_player_not_its_uninstaller() -> None:
    assert _explicit_arguments_from_evidence(
        "window.resolve", "Sabes que peli estoy viendo en potplayer?", APPS,
    ) == {"applicationName": "PotPlayer 64 bit"}


class _Decider:
    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision

    def decide_in_context(self, *_args: object, **_kwargs: object) -> ContextDecision:
        return self.decision


def _tool(operation: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "read_only",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }


def test_the_media_session_choice_becomes_the_player_window_read() -> None:
    text = "Sabes que peli estoy viendo en potplayer?"
    # What the decider chose in v4j, v4k and v4l.
    decision = ContextDecision("¿Qué película estoy viendo en PotPlayer?", "action", ("media.status",), "")

    result = sidecar._context_decided_result(
        {"id": "m132", "text": text, "history": [{"role": "user", "content": text}]},
        llm=_Decider(decision),
        planner_catalog=PlannerCatalog([_tool(name) for name in sorted(READS)]),
        application_names=APPS,
    )

    assert result["kind"] == "action"
    assert result["operation"] == "window.resolve"
