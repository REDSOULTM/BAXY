"""Which language an answer is in (src/baxy_mind/language_id.py: langid.py's model, restricted to Spanish and
English), measured on replies written with it and on replies held out from it, and the App's tag kept where the text
does not settle it."""
import json
import lzma
import pickle
from pathlib import Path

import pytest

from baxy_mind import language_id

DATA = Path(__file__).with_name("data")


def _replies(name: str) -> list[dict]:
    return json.loads((DATA / name).read_text(encoding="utf-8"))["replies"]


# The figures measured when SURE was set (2026-11-04): a change to the model or the threshold that loses one shows here.
@pytest.mark.parametrize(("name", "tag", "right"), [
    ("language_id_replies.v1.json", "es", 80), ("language_id_replies.v1.json", "en", 81),
    ("language_id_heldout.v1.json", "es", 108), ("language_id_heldout.v1.json", "en", 115),
])
def test_answers_are_said_in_their_own_language_as_measured(name: str, tag: str, right: int) -> None:
    replies = _replies(name)
    assert sum(language_id.said_in(reply["text"], tag) == reply["lang"] for reply in replies) >= right
    # the App's tag alone, as before: half of them in the wrong language
    assert sum(reply["lang"] == tag for reply in replies) == len(replies) // 2


@pytest.mark.parametrize("text", ["Listo.", "OK.", "Done.", "Got it.", "Hecho."])
def test_a_reply_too_short_to_settle_its_language_keeps_the_app_s(text: str) -> None:
    assert language_id.identify(text)[1] < language_id.SURE
    assert language_id.said_in(text, "es") == "es" and language_id.said_in(text, "en") == "en"


@pytest.mark.parametrize(("text", "lang"), [
    ("Son 1.500 pesos chilenos.", "es"), ("Abrí Spotify.", "es"), ("Instalé el juego en tu Xbox One.", "es"),
    ("I opened Spotify.", "en"), ("Your C drive has 120 GB free out of 512 GB.", "en"),
])
def test_a_reply_that_settles_its_language_is_said_in_it_whatever_the_tag(text: str, lang: str) -> None:
    assert language_id.said_in(text, "es") == lang == language_id.said_in(text, "en")


def test_the_model_is_read_with_nothing_but_data_and_arrays(tmp_path: Path) -> None:
    with lzma.open(language_id.MODEL) as handle:
        assert len(language_id._Arrays(handle).load()) == 5
    hostile = tmp_path / "model.plzma"
    with lzma.open(hostile, "wb") as handle:
        pickle.dump(Path("x"), handle)  # any class other than the standard library's arrays
    with lzma.open(hostile) as handle, pytest.raises(pickle.UnpicklingError):
        language_id._Arrays(handle).load()
