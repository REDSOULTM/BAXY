"""R08 (A/B del banco de uso, 03-11): «para esta canción y pon otra» pasaba a la siguiente con el catálogo de d4bd y
preguntaba «¿qué canción pongo?» con el de HEAD. En el turno aislado con el modelo real (encargo 33) la decisión está al
borde (p del rival 0,35-0,49) y la voltea cualquier herramienta nueva: quitar client.deafen.set la devuelve, quitar
client.channel.open también, quitar deafen y sus menciones no. Un ejemplo en media_control de otra canción sin nombrarla
(next) la devuelve (8 de 8, p de preguntar 0,008) sin bajar G5 ni los vecinos de medios held-out."""
from pathlib import Path

from test_mind_final import _mind

CATALOG = {"capabilities": [{"name": "media.control", "description": "Controla lo que suena.", "risk": "low_reversible",
                             "argumentsSchema": {"type": "object", "properties": {}}}]}


def test_its_examples_put_another_song_with_none_named_as_next(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure(CATALOG)
    description = next(t["function"]["description"] for t in mind.tools if t["function"]["name"] == "media_control")
    examples = description[description.index("Examples:"):]
    assert "«para esta y pon otra» (next)" in examples


def test_it_says_play_or_pause_is_toggle_and_that_its_result_says_which_way(tmp_path: Path) -> None:
    # RUT7/RUT8 (the owner's routine «tiempo», «reproduce o pausa lo que está sonando» = the play/pause key): the 4B went
    # to read what was playing first (off in Esencial) or asked «¿lo pauso o lo sigo?» and never paused (0 of 3). The
    # tool has toggle and its text did not say so; in Completo it read media_status first and then asked. And a toggle's
    # result said only the state after: told backwards 2 of 3 in Completo. The text names toggle, says its result tells
    # what it did, and media_status says a play or a pause needs no reading first (INFORME_RUT8.md).
    mind, _ = _mind(tmp_path, [])
    mind.configure(CATALOG)
    description = next(t["function"]["description"] for t in mind.tools if t["function"]["name"] == "media_control")
    assert "action toggle, in this one call, with nothing to read or ask first" in description
    assert "its result says what it did and what plays now" in description
    assert description.index("action toggle") < description.index("Use when:")
    assert "«reproduce o pausa» (toggle)" in description[description.index("Examples:"):]


def test_reading_what_plays_says_a_play_or_a_pause_needs_no_reading_first(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [*CATALOG["capabilities"], {
        "name": "media.status", "description": "Lee lo que suena.", "risk": "read_only",
        "argumentsSchema": {"type": "object", "properties": {}}}]})
    description = next(t["function"]["description"] for t in mind.tools if t["function"]["name"] == "media_status")
    excluded = description[description.index("Do not use when:"):description.index("Examples:")]
    assert "playing or pausing (media_control acts with nothing read first)" in excluded
