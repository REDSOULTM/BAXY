"""M133 (D61.2, 2026-10-02): «abre X» with X not installed → BAXY checks (``app.installed``) and says it is not
installed, like the reviewed literals H0289, H0558, H0249, H0503 and H0691.

The catalog reader ``catalog_unavailable`` closed some named applications as a limit without checking them: reserve
en9233 «open pandora» (a music service BAXY does not play on, but a desktop application), en1994 «can you open my
itunes» (the possessive was no article) and H0406 «Abre una app que no existe llamada AplicacionFantasmaXYZ» (owner
note: «verificar la ausencia antes de afirmar una causa»). They are now read by the presence of the name. What is no
application of this PC — a door, a game the library lacks, a web service — keeps the limit.
"""

from __future__ import annotations

import pytest

from baxy_mind import effect_intent
from baxy_mind import __main__ as mind_main
from baxy_mind.__main__ import _explicit_arguments_from_evidence
from baxy_mind.semantic.conversation import catalog_unavailable

APPLICATIONS = ("Steam", "Spotify", "Google Chrome", "Discord", "Calculadora", "Bloc de notas")
GAMES = effect_intent.build_game_catalog_index([("steam", "2767030", "Marvel Rivals")])
OPERATIONS = ("app.open", "app.installed", "game.launch", "game.entitlement.named", "web.search", "browser.navigate")


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("open pandora", "pandora"),
        ("can you open my itunes", "itunes"),
        ("abre mi itunes porfa", "itunes"),
        ("open the itunes app", "itunes"),
        ("open the deezer app please", "deezer"),
        ("Abre una app que no existe llamada AplicacionFantasmaXYZ", "AplicacionFantasmaXYZ"),
        ("abre la app que se llama Fooblr", "Fooblr"),
        ("open an app called Fooblr", "Fooblr"),
    ],
)
def test_a_named_application_that_is_not_installed_is_checked(text: str, name: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, OPERATIONS, APPLICATIONS, GAMES)
    assert intent is not None and intent.operations == ("app.installed",)
    # The presence read carries the name as written, and the reply step binds the same name (``message.compose``
    # refuses a lookup result that does not bind the request).
    assert _explicit_arguments_from_evidence("app.installed", text, APPLICATIONS, GAMES) == {"name": name}
    assert effect_intent.unresolved_application_open_name(text, APPLICATIONS) == name
    # The catalog reader no longer closes it as a limit: the turn reaches it with that intent.
    assert not catalog_unavailable(text, intent, APPLICATIONS, GAMES)


@pytest.mark.parametrize("text", ["open spotify app", "open the spotify app", "abre mi spotify"])
def test_a_named_application_the_catalog_holds_is_never_read_for_presence(text: str) -> None:
    assert effect_intent.unresolved_application_open_name(text, APPLICATIONS) is None
    intent = effect_intent.resolve_explicit_effects(text, OPERATIONS, APPLICATIONS, GAMES)
    assert intent is None or "app.installed" not in intent.operations


@pytest.mark.parametrize(
    "text",
    [
        "abre la puerta del garaje",
        "open the garage door",
        "Let's play Candy Crush.",
        "open games",
        "Take me to the Instagram app.",
        "open uber",
        "open chess app and begin game",
    ],
)
def test_what_is_no_application_of_this_pc_keeps_the_limit(text: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, OPERATIONS, APPLICATIONS, effect_intent.build_game_catalog_index(()))
    assert intent is None or "app.installed" not in intent.operations
    decision = mind_main._catalog_unavailable_turn_decision(
        text, None, APPLICATIONS, effect_intent.build_game_catalog_index(()),
    )
    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["conversation_kind"] == "unsupported"
    assert decision["effect_operations"] == []
