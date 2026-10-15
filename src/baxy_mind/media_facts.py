"""Media titles as observed: the title of what plays, the local player's session, and whether a reply names
it as read.
"""

from __future__ import annotations

import re
import unicodedata

from .semantic.request import fold as _reading_fold
from .compose_situation import _merged_observed, _situation_from_facts


def _title_fold(value: object) -> str:
    """A played title as words: folded, quotes blind, without emoji or symbols (tanda 5b: a draft may leave the
    title's «😳 👀» out; the words are the name)."""

    return " ".join(
        "".join(ch for ch in _reading_fold(_quote_blind(value)) if unicodedata.category(ch) not in {"So", "Sk", "Cs"})
        .split()
    )


# Operations whose observed title is a played or loaded media title.
_MEDIA_TITLE_OPERATIONS = frozenset({
    "media.status", "media.control", "media.play.youtube", "media.play.query", "media.play.exact",
})
# Those whose title may be named by its names (MUSIC1749, tanda 6b); the local YouTube playback keeps quoting it whole.
_MEDIA_TITLE_BY_PARTS = frozenset({"media.status", "media.play.query", "media.play.exact"})
# M89 (DEV-D v3r D-w05-t3): a reply that says the album of what is playing is not known from here. Folded.
_MEDIA_ALBUM_UNKNOWN = re.compile(
    r"\b(?:no\s+(?:se|lo\s+se|sabria\s+decir|puedo\s+decir|tengo)|desconozco|sin\s+(?:el\s+)?(?:dato|disco)|"
    r"(?:i\s+)?(?:do\s+not|don'?t|cannot|can'?t)\s+(?:know|tell|see)|(?:is|isn'?t)\s+not\s+(?:known|shown)|unknown)\b"
)
_MEDIA_SITE_SUFFIX = re.compile(r"\s+[-—–|]\s+youtube(?:\s+music)?\s*$", re.IGNORECASE)
_MEDIA_TITLE_DECORATION = re.compile(r"\([^()]*\)|\[[^\[\]]*\]")
_MEDIA_TITLE_PART = re.compile(r"\s+[-—–|]\s+")
_MEDIA_TITLE_PERFORMERS = re.compile(r"\s*[&,+/]\s*|\s+(?:feat\.?|ft\.?|featuring|x|y|and|con|with)\s+", re.IGNORECASE)
# M172 (DEV-I v5b I-s047 «ponme algo de Mon Laferte en el spotify» → «Mon Laferte - Mi Buen Amor - Desde El Teatro Fru
# Fru», I-s049 «what's this song called?»): a part after the first that only says which recording it is («En Vivo»,
# «Live at Wembley», «2011 Remaster», «Radio Edit», «Versión Acústica», «Desde El Teatro Fru Fru») is not a name the
# reply owes; «"Mi Buen Amor" de Mon Laferte» names the song. A part that could be a title of its own («Live Forever»,
# «Desde que te fuiste», «Desde el alma», «Stereo») is not a version: «desde»/«from» counts only before a venue. Over
# the folded part, whole.
_MEDIA_TITLE_VERSION = re.compile(
    r"(?:\d{4}\s+)?(?:remaster(?:ed|izad[oa])?|remasterizacion)(?:\s+(?:version|\d{4}))?(?:\s+\d{4})?"
    r"|(?:en\s+vivo|ao\s+vivo|en\s+directo|live|acoustic|acustic[oa]|unplugged|radio\s+edit|single\s+(?:version|edit)|"
    r"bonus\s+track|sped\s+up|slowed(?:\s+(?:and\s+)?reverb)?)(?:\s+(?:version|mix))?"
    r"|versi[oó]n\s+\w+(?:\s+\w+)?"
    r"|(?:\w+\s+){1,2}(?:version|remix|edit)"
    r"|(?:live|en\s+vivo|ao\s+vivo|en\s+directo)\s+(?:at|from|in|en|desde|de)\s+.+"
    r"|(?:desde|from|grabado\s+en|recorded\s+(?:at|in|live\s+at))\s+(?:\w+\s+){0,3}?"
    r"(?:teatro|estadio|auditorio|arena|palacio|festival|sala|club|estudio|studio|hall|theatre|theater|stadium|"
    r"garden|coliseo|foro|concierto|concert|gira|tour)\b.*"
)


def _media_title_names(title: str, *, owed_only: bool = False) -> list[str]:
    """The names in a played title: its parts between « - » without the tab's site or bracketed decoration
    («(Official Video 1987 Remastered)»), each performer apart («Freddie Mercury & Montserrat Caballé»).
    ``owed_only`` leaves out a later part that only names the recording (M172)."""

    video = _MEDIA_SITE_SUFFIX.sub("", title).strip() or title
    return [
        name for index, part in enumerate(_MEDIA_TITLE_PART.split(_MEDIA_TITLE_DECORATION.sub(" ", video)))
        if not (owed_only and index and _MEDIA_TITLE_VERSION.fullmatch(_title_fold(part)))
        for name in _MEDIA_TITLE_PERFORMERS.split(part) if _title_fold(name).split()
    ]


def _title_words_pattern(value: str) -> str | None:
    words = _title_fold(value).split()
    return r"(?<!\w)" + r"\s+".join(re.escape(word) for word in words) + r"(?!\w)" if words else None


def _names_media_title(text: str, title: str, *, by_parts: bool) -> bool:
    """The draft names the observed media title: all its words (MUSIC1555 spacing, MUSIC1773 quotes and tanda 5b
    emoji blind), without the tab's « - YouTube» too; or, ``by_parts``, every name in it (MUSIC1749 «"Bohemian
    Rhapsody" de Queen», tanda 6b «Es Barcelona, de Freddie Mercury y Montserrat Caballé»)."""

    folded = _title_fold(text)
    whole = [_title_words_pattern(title), _title_words_pattern(_MEDIA_SITE_SUFFIX.sub("", title))]
    if any(pattern and re.search(pattern, folded) for pattern in whole):
        return True
    names = [_title_words_pattern(name) for name in _media_title_names(title, owed_only=True)] if by_parts else []
    return bool(names) and all(pattern and re.search(pattern, folded) for pattern in names)


def _without_media_title(text: str, title: str) -> str:
    """``text`` folded, without the observed title's words, whole or by its names."""

    folded = _title_fold(text)
    for value in (title, _MEDIA_SITE_SUFFIX.sub("", title), *_media_title_names(title)):
        pattern = _title_words_pattern(value)
        if pattern:
            folded = re.sub(pattern, " ", folded)
    return folded


def _local_player_session(situation: dict) -> bool:
    """MUSIC1593: a verified media.status/media.control observed on the local YouTube player."""

    observed = _merged_observed(situation) if isinstance(situation, dict) else {}
    return (
        situation.get("operation") in {"media.status", "media.control"}
        and situation.get("verified") is True
        and situation.get("succeeded") is True
        and isinstance(observed, dict)
        and observed.get("authority") == "local_youtube_player"
        and isinstance(observed.get("title"), str)
        and bool(observed["title"].strip())
    )


def _quote_blind(text: str) -> str:
    """MUSIC1773: the text without quotation marks of any typography."""

    return re.sub(r"[\"\u00ab\u00bb\u201c\u201d\u2018\u2019']", "", text or "")


def _verified_media_playing_title(situation: dict) -> bool:
    """MUSIC1773: a verified media.play.query/exact/youtube that is playing with an observed title."""

    observed = _merged_observed(situation) if isinstance(situation, dict) else {}
    return (
        situation.get("operation") in {"media.play.query", "media.play.exact", "media.play.youtube"}
        and situation.get("verified") is True
        and situation.get("succeeded") is True
        and isinstance(observed, dict)
        and observed.get("playbackStatus") == "playing"
        and isinstance(observed.get("title"), str)
        and bool(observed["title"].strip())
    )


def _bracket_is_observed(bracketed: str, facts: dict) -> bool:
    """MUSIC1571: «[11.Larga Vida al Rey]» inside a quoted YouTube title is
    observed text, not a template hole left unfilled."""

    try:
        situation = _situation_from_facts(facts) if isinstance(facts, dict) else {}
    except Exception:  # noqa: BLE001 - a malformed situation is not evidence
        return False
    needle = _reading_fold(bracketed)
    observed = _merged_observed(situation) if isinstance(situation, dict) else {}

    # tanda-02: a search result title «[FREE] …», «… [Live Clock] | …» is
    # observed text one level down (results[].title); the pages report that
    # quoted it died as a template hole.
    def carries(value: object, depth: int = 0) -> bool:
        if isinstance(value, str):
            return bool(needle) and needle in _reading_fold(value)
        if depth >= 3:
            return False
        if isinstance(value, dict):
            return any(carries(child, depth + 1) for child in value.values())
        if isinstance(value, list):
            return any(carries(child, depth + 1) for child in value)
        return False

    return carries(observed)
