"""The computer-use engine's own words and data rules: its vocabulary (data/computer_use_words.v1.json), the
evidence rules, the content keys and the floor's place and part data (operation_floor.v1.json «computerUse»), read
once and shared by the steps and the finals.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from . import operation_floor
from .semantic.missions import fold


def _commit_on_offer(controls: list[dict]) -> bool:
    """A button that saves or confirms a form («Guardar», «Save & close», «Crear», «OK»; data
    «evidence.commitControl») is on offer: what the form makes does not exist yet. Twin of
    ComputerUseSuccessCheck.CommitOnOffer."""

    commit = _evidence_rules()["commitControl"]
    return any(
        item.get("kind") in {"Button", "SplitButton"} and re.search(commit, fold(item.get("name")).strip())
        for item in controls if isinstance(item, dict)
    )


# Ronda 21: the keys as the act alters a document's content or not (operation_floor.v1.json
# «computerUse.contentKeys»), shared with the App's ComputerUseMissionWindow.
_CONTENT_KEYS: dict = operation_floor.floor_data()["computerUse"]["contentKeys"]
CONTENT_KEEPING_KEYS = frozenset(_CONTENT_KEYS["keeping"])
# Ronda 24: the keys whose effect is the clipboard, which no look shows (data «computerUse.contentKeys.copy»).
CONTENT_COPY_KEYS = frozenset(_CONTENT_KEYS["copy"])
# Review 4 of ronda 24: of the keys whose effect the view's signature does not see (data
# «computerUse.contentKeys.unseenEffect»), those whose effect lands on the written text («writtenEffect»).
CONTENT_WRITTEN_EFFECT_KEYS = frozenset(_CONTENT_KEYS["writtenEffect"])


# The words of a created thing that never tell one thing from another.
_CREATED_FILLERS = frozenset({"un", "una", "el", "la", "los", "las", "nuevo", "nueva", "nuevos", "nuevas", "new", "a",
                              "an", "the", "de", "del", "en", "of", "in", "mi", "my"})


def _created_words(text: str) -> set[str]:
    """The words that tell what is created, cut to five letters; a word of a kin group (data «creatingKin»: the same
    thing in Spanish and English, «página»/«page», «correo»/«mensaje»/«email») stands for its whole group, so the goal
    said in one language reads the command shown in the other."""

    kin: dict[str, str] = {}
    for group in _evidence_rules().get("creatingKin") or ():
        stems = [fold(str(word))[:5] for word in group]
        for stem in stems:
            kin.setdefault(stem, stems[0])
    return {
        kin.get(word[:5], word[:5]) for word in re.findall(r"[a-z0-9]+", fold(text)) if word not in _CREATED_FILLERS
    }


# Encargo S: the verbs before a place's name on the button that opens it or closes it (data «computerUse.placeToggle»,
# read by the App's ComputerUseSuccessCheck too).
_PLACE_TOGGLE = operation_floor.floor_data()["computerUse"]["placeToggle"]


# Keys whose effect lands where the view's signature does not look (written text, the caret, the selection, the
# clipboard, a saved file, a submitted line): a look that kept the signature says nothing about them. Measured on the
# Terminal's frozen view (14 controls, the console text no control's value): a typed command and its Enter keep the
# signature although the command ran.
# Data «computerUse.contentKeys.unseenEffect» (review 4 of ronda 24), shared with the App.
_UNSEEN_EFFECT_KEYS = frozenset(_CONTENT_KEYS["unseenEffect"])


def _evidence_rules() -> dict:
    return operation_floor.floor_data()["computerUse"]["evidence"]


# cu-r16 (voice audit 2026-10-07: «Abrazé a la sección de Bluetooth», «donde busco la opción de Wi-Fi», «Ya estamos
# en…», «mis playlists»): every word of a mission final comes from the turn's facts or from BAXY's own small vocabulary
# of arrival, act and function words (data/computer_use_words.v1.json). A word from neither was never observed.
_WORDS_DATA = Path(__file__).resolve().parent / "data" / "computer_use_words.v1.json"
_WORD = re.compile(r"[a-z0-9]+")


@lru_cache(maxsize=1)
def _own_words() -> tuple[frozenset[str], int]:
    data = json.loads(_WORDS_DATA.read_text(encoding="utf-8"))
    words: set[str] = set()
    for family in ("function", "own"):
        for listed in data[family].values():
            words.update(fold(word) for word in listed)
    return frozenset(words), int(data["stemLength"])


@lru_cache(maxsize=1)
def _function_words() -> frozenset[str]:
    """The Spanish and English function words of the vocabulary («de», «tu», «the»…): no word of them names a place."""

    data = json.loads(_WORDS_DATA.read_text(encoding="utf-8"))
    return frozenset(fold(word) for listed in data["function"].values() for word in listed)


@lru_cache(maxsize=1)
def _language_words() -> tuple[frozenset[str], frozenset[str], dict[str, tuple[str, ...]]]:
    """The Spanish and English function words (to tell an English reply) and the es→en screen-state map."""

    data = json.loads(_WORDS_DATA.read_text(encoding="utf-8"))
    spanish = frozenset(fold(word) for word in data["function"]["es"])
    english = frozenset(fold(word) for word in data["function"]["en"])
    listed = data.get("screenStates") or {}
    states = {fold(word): tuple(fold(item) for item in said) for word, said in listed.items()}
    return spanish - english, english - spanish, states


@lru_cache(maxsize=1)
def _application_kinds() -> dict[str, frozenset[str]]:
    data = json.loads(_WORDS_DATA.read_text(encoding="utf-8"))
    listed = data.get("applicationKinds") or {}
    return {fold(name): frozenset(fold(word) for word in words) for name, words in listed.items()}


@lru_cache(maxsize=1)
def _screen_lists() -> dict[str, tuple[str, ...]]:
    """Ronda 20b, palanca 6: the names of the window's parts the steps read by data («screenLists»): the search of
    orders, the labels beside a view's option, the frame's navigation."""

    data = json.loads(_WORDS_DATA.read_text(encoding="utf-8"))
    listed = data.get("screenLists") or {}
    return {
        key: tuple(fold(name).strip() for name in names if str(name).strip())
        for key, names in listed.items() if isinstance(names, list)
    }


def _named_by_list(name: object, key: str) -> bool:
    """The name is one of the list's entries, or starts with one as a whole word («Atrás a Panel de control»,
    «Dirección: Panel de control», «Ver por: Categoría»)."""

    folded = re.sub(r"\s+", " ", fold(name)).strip(" ¿?¡!.")
    return bool(folded) and any(
        folded == entry or folded.startswith(entry + " ") or folded.startswith(entry + ":")
        for entry in _screen_lists().get(key, ())
    )


# Live 2026-10-07 (v2-v9 «en el Reloj andá a Reloj mundial», v2-u7/v2-w1 «… andá a Alarma»): a clock the window shows is
# what was observed, but Windows writes it with bidi marks inside («7‎:‎58»), and the part of the day is not written.
_BIDI_MARKS = re.compile("[‎‏‪-‮⁦-⁩]")


# The floor of a mission (live 2026-10-07): when every draft was refused, «Lo hice en la aplicación «Reloj»; hay 2:
# «Reloj mundial».» counted the steps as a list read. The floor says what the person asked about, from the facts only:
# the place reached, or what could not be done and its cause.
_PLACE_GOAL = re.compile(operation_floor.floor_data()["computerUse"]["placeGoal"], re.IGNORECASE)
_LONGEST_FLOOR_NAME: int = operation_floor.floor_data()["computerUse"]["longestName"]


def _floor_name(value: object) -> str:
    text = " ".join(_BIDI_MARKS.sub("", value).split()).strip(" .;:") if isinstance(value, str) else ""
    return text if text and len(text) <= _LONGEST_FLOOR_NAME and "«" not in text and "»" not in text else ""


# Voice audit 2026-10-07 (cu-r16): a third of the published mission finals the model wrote had a defect («Ya te llevé a
# la sección de sonido», «Abrazé a la sección de Bluetooth», «ahora selecciono Títulos», «mis playlists»), and the
# simple missions are most of them. A mission without a question is told part by part from its facts (data
# «computerUse.parts»): the places reached, the controls picked, the text typed or searched, a calculation whose value
# the window shows. Its twin is the App's OperationFloor.Parts.
_PARTS: dict = operation_floor.floor_data()["computerUse"]["parts"]
