"""Rule ``unmatched`` of the answer check (encargo A5): the answer attributes to a video words that its result says
(``titleMatchesQuery: false``) the title did not match. Only form is compared; the model writes its answer again with
the fact."""
import pytest

from baxy_mind.answer_check import check
from test_answer_check import _r

YOUTUBE = {"status": "completed", "verification": "readback", "observed": {
    "version": 1, "provider": "youtube", "query": "Marta Vega Sorry Baby", "titleMatchesQuery": False,
    "title": "Sorry Baby", "browser": "Google Chrome", "playbackStatus": "playing"}}
YOUTUBE_OK = {**YOUTUBE, "observed": {k: v for k, v in YOUTUBE["observed"].items() if k != "titleMatchesQuery"}
              | {"title": "Marta Vega - Sorry Baby (Official Video)"}}


def _rules(answer: str, receipts: list[dict], request: str = "") -> list[dict]:
    return [f for f in check(answer, request, receipts, [(r["op"], r["completed"], r["read"]) for r in receipts])
            if f["rule"] == "unmatched"]


@pytest.mark.parametrize("answer", [
    "Puse Sorry Baby de Marta Vega.",  # caso real 1
    "Está sonando «Sorry Baby», la canción de Vega.",
])
def test_the_artist_of_a_title_that_did_not_match_is_flagged(answer: str) -> None:
    findings = _rules(answer, [_r("media.play.youtube", YOUTUBE)], "ponme Sorry Baby de Marta Vega")
    assert [f["rule"] for f in findings] == ["unmatched"]
    assert "Sorry Baby" in findings[0]["fact"]


@pytest.mark.parametrize("answer,receipt", [
    ("Puse «Sorry Baby», pero el título no trae a Marta Vega: no sé si es suya.", YOUTUBE),
    ("Está sonando «Sorry Baby», no puedo confirmar que sea de Marta Vega.", YOUTUBE),
    ("Puse Sorry Baby.", YOUTUBE),
    ("Puse Sorry Baby de Marta Vega.", YOUTUBE_OK),  # the title does carry the words
])
def test_a_title_told_as_it_is_is_not_flagged(answer: str, receipt: dict) -> None:
    assert not _rules(answer, [_r("media.play.youtube", receipt)], "ponme Sorry Baby de Marta Vega")
