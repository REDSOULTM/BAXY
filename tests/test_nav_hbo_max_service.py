"""Owner 2026-10-06: «Disney y HBO deberían de funcionar». HBO Max joins streaming.play.named and streaming.navigate:
«en HBO Max», «en HBOMax» and «en HBO» name the service; a bare «Max» does not (it is also «al máximo»)."""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind import effect_intent

STREAM_AVAILABLE = frozenset(
    {"streaming.play.named", "streaming.navigate", "app.open", "web.search", "memory.status", "browser.navigate"}
)


@pytest.mark.parametrize(
    ("text", "title"),
    [
        ("pon The Last of Us en HBO Max", "The Last of Us"),
        ("pon the last of us en hbo", "the last of us"),
        ("quiero ver euphoria en hbomax", "euphoria"),
        ("play the last of us on hbo max", "the last of us"),
        ("pon en hbo max la casa del dragon", "la casa del dragon"),
        ("ponme superman en HBO", "superman"),
    ],
)
def test_a_title_on_hbo_max_plays_it_there(text: str, title: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, STREAM_AVAILABLE, ("Spotify",), ())
    assert intent is not None and intent.operations == ("streaming.play.named",)
    arguments = mind._explicit_arguments_from_evidence(
        "streaming.play.named", text, ("Spotify",), effect_intent.build_game_catalog_index(())
    )
    assert arguments == {"service": "hbo_max", "title": title}


@pytest.mark.parametrize(
    ("text", "service"),
    [("pon bluey en disney plus", "disney_plus"), ("ponme stranger things en netflix", "netflix")],
)
def test_the_other_services_keep_their_value(text: str, service: str) -> None:
    arguments = mind._explicit_arguments_from_evidence(
        "streaming.play.named", text, ("Spotify",), effect_intent.build_game_catalog_index(())
    )
    assert arguments is not None and arguments["service"] == service


@pytest.mark.parametrize("text", ["pon el brillo en max", "ponlo en max"])
def test_a_bare_max_is_a_level_not_the_service(text: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, STREAM_AVAILABLE, ("Spotify",), ())
    assert intent is None or "streaming.play.named" not in intent.operations


def test_an_hbo_max_address_is_its_resource() -> None:
    url = "https://play.hbomax.com/show/93ba22b1-833e-47ba-ae94-8ee7b9eefa9a"
    arguments = mind._explicit_arguments_from_evidence(
        "streaming.navigate", f"abre {url}", ("Spotify",), effect_intent.build_game_catalog_index(())
    )
    assert arguments == {"resourceUri": url, "service": "hbo_max"}
