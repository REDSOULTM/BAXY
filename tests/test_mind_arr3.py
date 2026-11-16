"""ARR3 (VIVO23, 15-11-2026): with a card of 4 GB and the Completo profile the person chose, BAXY did not start.

The App now starts in the largest ready-made profile the card holds under the person's, for that start alone, and keeps
their choice (ToolProfile.FitCard, «chosen»). What the model reads of it is that: the person chose the profile that did
not fit, the start runs the one that fits, the choice is kept and asking for it again tries it. Never «BAXY eligió por su
cuenta», which is what a start says of a profile nobody chose (VRAM4B).
"""
import pathlib

from baxy_mind.mind import CARD_PROFILE_FACT
from test_mind_final import _mind
from test_mind_vram4b import OPEN

THEIRS = {"profile": "Esencial", "factory": "Completo", "freeMb": 3400, "needMb": 5200, "chosen": True}


def test_a_start_that_stands_in_for_the_persons_profile_says_theirs_is_kept(tmp_path: pathlib.Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [OPEN], "cardProfile": THEIRS})
    assert "La persona eligió el perfil de herramientas Completo" in mind.system
    assert "3,3 GB de memoria de vídeo libres" in mind.system and "unos 5,1 GB" in mind.system
    assert "arrancó con el perfil Esencial" in mind.system
    assert "sigue guardada" in mind.system and "si la persona lo pide otra vez" in mind.system
    assert "eligió por su cuenta" not in mind.system, "the person chose it: never BAXY's choice"


def test_a_personalizado_is_tried_again_at_the_next_start_only(tmp_path: pathlib.Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [OPEN], "cardProfile": {**THEIRS, "factory": "Personalizado", "again": False}})
    assert "cada arranque vuelve a intentar el perfil Personalizado." in mind.system
    assert "pidiéndotelo" not in mind.system, "a Personalizado is not asked for by voice"


def test_without_chosen_the_fact_is_the_one_of_before(tmp_path: pathlib.Path) -> None:
    for at, chosen in enumerate((None, False, "true", 1)):
        card = {key: value for key, value in THEIRS.items() if key != "chosen"}
        if chosen is not None:
            card["chosen"] = chosen
        mind, _ = _mind(tmp_path / str(at), [])
        mind.configure({"capabilities": [OPEN], "cardProfile": card})
        assert CARD_PROFILE_FACT.format(profile="Esencial", factory="Completo", free="3,3", need="5,1") in mind.system
        assert "La persona eligió" not in mind.system
