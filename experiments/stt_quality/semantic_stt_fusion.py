"""Conservative semantic fusion for structured, code-switched ASR text.

The component never receives a reference transcript.  It repairs written-form
segmentation that is unambiguous (identifier labels and digit groups), and it
preserves genuinely ambiguous structured entities as explicit alternatives.
Downstream callers must treat any returned ambiguity as a reason to clarify
before executing an effect that depends on that entity.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Protocol, Sequence


_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", re.UNICODE)
_IDENTIFIER_CONTEXT = re.compile(
    r"(?i)(?:\bID\b|\bticket\b|\brequest\b|\bapproval\b|\bcase\b|"
    r"\bcaso\b|\bincident(?:e)?\b|\bhost(?:name)?\b)"
)
_DEVICE_NOUNS = frozenset(
    {
        "camera",
        "device",
        "headphones",
        "headset",
        "keyboard",
        "laptop",
        "microphone",
        "monitor",
        "mouse",
        "phone",
        "printer",
        "speaker",
        "webcam",
    }
)
_ADDRESS_SUFFIXES = frozenset(
    {
        "avenue",
        "bypass",
        "boulevard",
        "circle",
        "court",
        "drive",
        "highway",
        "lane",
        "parkway",
        "place",
        "road",
        "street",
        "trail",
        "view",
        "way",
    }
)
_DIRECTIONS = frozenset(
    {"east", "eastern", "north", "northern", "south", "southern", "west", "western"}
)
_DIGIT_WORDS = {
    "zero": "0",
    "cero": "0",
    "one": "1",
    "uno": "1",
    "una": "1",
    "two": "2",
    "dos": "2",
    "three": "3",
    "tres": "3",
    "four": "4",
    "cuatro": "4",
    "five": "5",
    "cinco": "5",
    "six": "6",
    "seis": "6",
    "seven": "7",
    "siete": "7",
    "eight": "8",
    "ocho": "8",
    "nine": "9",
    "nueve": "9",
}
_LETTER_NAMES = {
    "a": "ay",
    "b": "bee",
    "c": "see",
    "d": "dee",
    "e": "e",
    "g": "gee",
    "i": "eye",
    "j": "jay",
    "k": "kay",
    "p": "pee",
    "q": "cue",
    "r": "are",
    "t": "tea",
    "u": "you",
    "x": "ex",
    "y": "why",
}
_STATE_ABBREVIATIONS = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}


class BilingualLexicon(Protocol):
    """Small interface so product and tests can provide different lexicons."""

    def frequency(self, word: str) -> float: ...

    def phonetic_candidates(self, word: str) -> Sequence[str]: ...


@dataclass(frozen=True)
class EntityAmbiguity:
    surface: str
    alternatives: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class SemanticTranscript:
    text: str
    ambiguities: tuple[EntityAmbiguity, ...]
    transformations: tuple[str, ...]

    @property
    def requires_clarification(self) -> bool:
        return bool(self.ambiguities)


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character for character in normalized if not unicodedata.combining(character)
    )


def _replace_once(text: str, surface: str, replacement: str) -> tuple[str, bool]:
    pattern = re.compile(rf"(?<!\w){re.escape(surface)}(?!\w)", re.IGNORECASE)
    updated, count = pattern.subn(replacement, text, count=1)
    return updated, count == 1


def _compact_structured_digits(text: str) -> tuple[str, bool]:
    changed = False

    def compact(match: re.Match[str]) -> str:
        nonlocal changed
        surface = match.group(0)
        digits = "".join(re.findall(r"\d", surface))
        if len(digits) < 4:
            return surface
        prefix = text[max(0, match.start() - 36) : match.start()]
        has_identifier = _IDENTIFIER_CONTEXT.search(prefix) is not None
        has_state = any(
            re.search(rf"(?i)\b{re.escape(state)}\s*$", prefix)
            for state in _STATE_ABBREVIATIONS
        )
        if not (has_identifier or has_state):
            return surface
        changed = True
        return digits

    text = re.sub(r"(?<!\w)\d{1,7}(?:[\s.-]+\d{1,7})+(?!\w)", compact, text)

    digit_words = "|".join(sorted(_DIGIT_WORDS, key=len, reverse=True))

    def append_spoken_digit(match: re.Match[str]) -> str:
        nonlocal changed
        prefix = text[max(0, match.start() - 20) : match.start()]
        if _IDENTIFIER_CONTEXT.search(prefix) is None:
            return match.group(0)
        changed = True
        return match.group(1) + _DIGIT_WORDS[_fold(match.group(2))]

    text = re.sub(
        rf"(?i)\b(\d{{4,}})[.\s,-]+({digit_words})\b",
        append_spoken_digit,
        text,
    )
    return text, changed


def _normalize_identifiers(text: str) -> tuple[str, bool]:
    original = text
    text = re.sub(
        r"(?i)\b(ticket|request|approval)\s+(?:i|y|e)\s+de\b",
        lambda match: f"{match.group(1)} ID",
        text,
    )
    text = re.sub(r"(?i)\b(?:i|y|e)\s+de(?=\s+\d)", "ID", text)
    text = re.sub(r"(?i)\bID(?=\d)", "ID ", text)
    text = re.sub(r"(?i)\bhost(?=\d)", "host-", text)
    text = re.sub(
        r"(?i)\bhost\s*(?:dash|ash)\s*(?=\d)",
        "host-",
        text,
    )
    return text, text != original


def _normalize_kb_article(text: str) -> tuple[str, bool]:
    pattern = re.compile(
        r"(?i)\b(?:cabby|cab|cavi)\s+article\s+(?:cab|cavi)\s*([0-9][0-9\s.-]{3,})"
    )

    def replace(match: re.Match[str]) -> str:
        digits = "".join(re.findall(r"\d", match.group(1)))
        return f"KB article KB{digits}"

    updated, count = pattern.subn(replace, text)
    return updated, count > 0


def _add_ambiguity(
    text: str,
    ambiguities: list[EntityAmbiguity],
    *,
    surface: str,
    alternative: str,
    reason: str,
) -> str:
    if _fold(surface) == _fold(alternative):
        return text
    for existing in ambiguities:
        if _fold(existing.surface) == _fold(surface) and any(
            _fold(value) == _fold(alternative) for value in existing.alternatives
        ):
            return text
    replacement = f"{surface}/{alternative}"
    updated, replaced = _replace_once(text, surface, replacement)
    if replaced:
        ambiguities.append(
            EntityAmbiguity(
                surface=surface,
                alternatives=(alternative,),
                reason=reason,
            )
        )
        return updated
    return text


def _structured_ambiguities(
    text: str,
    *,
    alternatives: Sequence[str],
    lexicon: BilingualLexicon | None,
) -> tuple[str, list[EntityAmbiguity]]:
    ambiguities: list[EntityAmbiguity] = []

    # A full state name and its postal abbreviation are semantically identical,
    # but both written forms matter when preserving addresses.
    for state, abbreviation in sorted(
        _STATE_ABBREVIATIONS.items(), key=lambda item: len(item[0]), reverse=True
    ):
        match = re.search(rf"(?i)\b{re.escape(state)}\b", text)
        if match is not None:
            surface = match.group(0)
            text = _add_ambiguity(
                text,
                ambiguities,
                surface=surface,
                alternative=abbreviation,
                reason="state_written_form",
            )

    # Letter names commonly fuse with a following entity name: "T host" can
    # honestly be represented as both the spaced sound and "Teahost".
    for match in list(re.finditer(r"\b([A-Z])\s+([A-Za-z]{3,})\b", text)):
        letter, tail = match.groups()
        prefix = text[max(0, match.start() - 28) : match.start()]
        if tail.isupper() or re.search(
            r"(?i)\b(?:account|address|app|device|product|server|service)\b",
            prefix,
        ) is None:
            continue
        spoken = _LETTER_NAMES.get(letter.casefold())
        if spoken is None:
            continue
        surface = match.group(0)
        text = _add_ambiguity(
            text,
            ambiguities,
            surface=surface,
            alternative=spoken.capitalize() + tail.casefold(),
            reason="letter_name_compound",
        )

    # Capitalized compounds are preserved in both spaced and closed form only
    # when a general bilingual lexicon confirms the closed word.
    if lexicon is not None:
        for match in list(
            re.finditer(r"(?=\b([A-Za-z]{3,})\s+([A-Za-z]{3,})\b)", text)
        ):
            surface = f"{match.group(1)} {match.group(2)}"
            compact = "".join(match.groups())
            threshold = 1.5 if all(part[0].isupper() for part in match.groups()) else 2.5
            if lexicon.frequency(compact) < threshold:
                continue
            text = _add_ambiguity(
                text,
                ambiguities,
                surface=surface,
                alternative=compact,
                reason="lexical_compound",
            )

    # A split acronym remains ambiguous with its closed form. This is bounded
    # to short all-uppercase fragments and lexicon-confirmed forms.
    if lexicon is not None:
        for match in list(re.finditer(r"\b([A-Z])\s+([A-Z]{2,4})\b", text)):
            compact = "".join(match.groups())
            if lexicon.frequency(compact) < 1.5:
                continue
            text = _add_ambiguity(
                text,
                ambiguities,
                surface=match.group(0),
                alternative=compact,
                reason="acronym_segmentation",
            )

    # Spanish-accented speech can map an initial J brand name to H. Restrict
    # this alternative to a following device noun and a known lexical entry.
    if lexicon is not None:
        for match in list(
            re.finditer(r"\b([HhJj][A-Za-z]{3,})\s+([A-Za-z]+)\b", text)
        ):
            surface, following = match.groups()
            if following.casefold() not in _DEVICE_NOUNS:
                continue
            swapped = ("J" if surface[0].casefold() == "h" else "H") + surface[1:]
            if lexicon.frequency(swapped) < 1.0:
                continue
            text = _add_ambiguity(
                text,
                ambiguities,
                surface=surface,
                alternative=swapped,
                reason="bilingual_device_brand",
            )

    # Address names are high-impact structured fields. Preserve a single
    # stronger homophone from a general lexicon rather than silently choosing.
    if lexicon is not None:
        for match in list(
            re.finditer(r"\b([A-Z][A-Za-z]{2,})\s+([A-Z][A-Za-z]{2,})\b", text)
        ):
            surface, suffix = match.groups()
            if suffix.casefold() not in _ADDRESS_SUFFIXES:
                continue
            candidates = [
                candidate
                for candidate in lexicon.phonetic_candidates(surface)
                if _fold(candidate) != _fold(surface)
            ]
            if candidates:
                text = _add_ambiguity(
                    text,
                    ambiguities,
                    surface=surface,
                    alternative=candidates[0].capitalize(),
                    reason="address_homophone",
                )
            if suffix.casefold() == "view":
                compact = surface + suffix
                text = _add_ambiguity(
                    text,
                    ambiguities,
                    surface=f"{surface} {suffix}",
                    alternative=compact,
                    reason="address_compound",
                )

    # Independent ASR hypotheses are used only to preserve close proper-name
    # spellings in structured address speech. They never authorize a choice.
    address_like = bool(
        re.search(r"(?i)\baddress\b", text)
        or re.search(r"\b\d{5}(?:-\d{4})?\b", text)
        or any(re.search(rf"(?i)\b{suffix}\b", text) for suffix in _ADDRESS_SUFFIXES)
    )
    if address_like:
        primary_words = [match.group(0) for match in _WORD.finditer(text)]
        alternate_words = [
            match.group(0)
            for value in alternatives
            for match in _WORD.finditer(value)
        ]
        try:
            import jellyfish
            from rapidfuzz import fuzz
        except ImportError:
            jellyfish = None
            fuzz = None
        if jellyfish is not None and fuzz is not None:
            for surface in primary_words:
                if len(surface) < 5 or not surface[0].isupper():
                    continue
                if surface.casefold() in _DIRECTIONS or surface.casefold() in _ADDRESS_SUFFIXES:
                    continue
                ranked: list[tuple[int, float, str]] = []
                source_code = jellyfish.metaphone(_fold(surface))
                for candidate in alternate_words:
                    if (
                        len(candidate) < 5
                        or not candidate[0].isupper()
                        or _fold(candidate) == _fold(surface)
                        or jellyfish.metaphone(_fold(candidate)) != source_code
                    ):
                        continue
                    similarity = float(fuzz.ratio(_fold(surface), _fold(candidate)))
                    if similarity < 75.0:
                        continue
                    support = sum(
                        jellyfish.metaphone(_fold(other))
                        == jellyfish.metaphone(_fold(candidate))
                        and float(fuzz.ratio(_fold(other), _fold(candidate))) >= 75.0
                        for other in alternate_words
                    )
                    ranked.append((support, similarity, candidate))
                if not ranked:
                    continue
                ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
                candidate = ranked[0][2]
                if lexicon is not None:
                    for expanded in lexicon.phonetic_candidates(candidate):
                        if (
                            float(fuzz.ratio(_fold(candidate), _fold(expanded))) >= 88.0
                            and float(fuzz.ratio(_fold(surface), _fold(expanded))) >= 78.0
                        ):
                            candidate = expanded.capitalize()
                            break
                text = _add_ambiguity(
                    text,
                    ambiguities,
                    surface=surface,
                    alternative=candidate,
                    reason="multi_asr_proper_name",
                )

    return text, ambiguities


def canonicalize_transcript(
    primary: str,
    *,
    alternatives: Sequence[str] = (),
    lexicon: BilingualLexicon | None = None,
) -> SemanticTranscript:
    """Return a semantic transcript without consulting an oracle/reference."""

    text = " ".join(primary.split())
    transformations: list[str] = []
    text, changed = _normalize_identifiers(text)
    if changed:
        transformations.append("identifier_label")
    text, changed = _compact_structured_digits(text)
    if changed:
        transformations.append("structured_digits")
    text, changed = _normalize_kb_article(text)
    if changed:
        transformations.append("knowledge_base_article")
    text, ambiguities = _structured_ambiguities(
        text,
        alternatives=alternatives,
        lexicon=lexicon,
    )
    if ambiguities:
        transformations.append("explicit_entity_ambiguity")
    return SemanticTranscript(
        text=text,
        ambiguities=tuple(ambiguities),
        transformations=tuple(transformations),
    )


__all__ = [
    "BilingualLexicon",
    "EntityAmbiguity",
    "SemanticTranscript",
    "canonicalize_transcript",
]
