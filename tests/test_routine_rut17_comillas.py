"""RUT17 (VIVO22, 14-11: «Todos los sábados a las 8 de la tarde dime «hora de regar las plantas».» was kept with the text
«hora de regar las plantas»», and BAXY said it back so): the words dictated between a pair of quotes are kept without them,
whatever sign ends the sentence after the closing one. Only the form: a pair of quotes around the whole text."""
from __future__ import annotations

import pytest

from baxy_mind import routine_fill
from baxy_mind import routine_guide as forms

SAID = "Todos los sábados a las 8 de la tarde dime {open}hora de regar las plantas{close}{end}"
PAIRS = [("«", "»"), ('"', '"'), ("'", "'"), ("“", "”")]


@pytest.mark.parametrize(("open_", "close"), PAIRS)
@pytest.mark.parametrize("end", [".", "", "!", " ."])
def test_the_text_said_in_one_breath_is_kept_without_its_quotes(open_: str, close: str, end: str) -> None:
    ordered = forms.heard(SAID.format(open=open_, close=close, end=end), "es")
    assert ordered is not None and ordered.guide is not None
    assert ordered.guide.say == "hora de regar las plantas"
    assert "plantas»»" not in ordered.guide.question() and "«hora de regar las plantas»" in ordered.guide.question()


@pytest.mark.parametrize(("open_", "close"), PAIRS)
def test_the_answer_to_what_to_say_is_kept_without_its_quotes(open_: str, close: str) -> None:
    assert forms._kept(f"{open_}hora de regar las plantas{close}.") == "hora de regar las plantas"


def test_the_text_the_model_read_is_kept_without_its_quotes() -> None:
    said = {*"todos los sabados a las 8 de la tarde dime hora de regar las plantas".split()}
    assert routine_fill._theirs("«hora de regar las plantas».", said) == "hora de regar las plantas"


@pytest.mark.parametrize(("text", "kept"), [
    ("«¿ya regaste?».", "¿ya regaste?"),                      # the signs inside the quotes are the text's own
    ("«riega» y «abona».", "riega» y «abona»."),               # two quoted pieces: no pair around the whole, as before
    ("hora de regar.", "hora de regar."),                      # no quotes: as before
    ("«hora de regar", "hora de regar"),                       # an opening quote alone: as before
    ("'", "'"),                                         # one quote alone: as before
])
def test_only_a_pair_around_the_whole_text_is_taken_off(text: str, kept: str) -> None:
    assert forms._kept(text) == kept
