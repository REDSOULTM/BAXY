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
