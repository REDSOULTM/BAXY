"""ING5 (owner's decision of 2026-11-13): the language of everything the mind writes for the model is a setting of the
person's, Spanish or English, and not something guessed turn by turn. The 4B answers in the language of the last
thing it reads, and all of it was Spanish (the system text, the clock line, every receipt's facts line, the notes):
17 of 120 English requests were answered in English, and a datum of the person's language written into one turn
(ING2, ING3, ING4) moved the decision to call instead. So the whole harness is written in one language at a time.

The texts stay written in Spanish where they always were, and with the language in Spanish every one of them is the
very object it was: what the model reads is byte for byte what it read before this setting existed. Their English is
data (data/harness.en.v1.json: each Spanish text and its English, sentence by sentence, with the constants that
hold them): ``use`` binds every listed constant to its English (or back to its Spanish) in the module that defines it
and in every module that imported it, then lets each module rebuild what it derives from them (``_relanguage``);
``t`` gives the text of one written inside a function. Nothing here reads the person's words or the model's answer:
which language is in use is told by the App (catalog.configure «lang»), never detected.

Sources: Marchisio et al., «Understanding and Mitigating Language Confusion in LLMs», EMNLP 2024
(https://arxiv.org/abs/2406.20052): models answer in the language of their context, and an instruction alone does
little; Qwen-Agent chose its function-calling template by an explicit ``lang`` (zh or en), never by turn
(qwen_agent/llm/fncall_prompts/qwen_fncall_prompt.py); INFORME_ING5.md lists the rest."""
from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SPANISH, ENGLISH = "es", "en"
LANGUAGES = (SPANISH, ENGLISH)
_FILE = Path(__file__).with_name("data") / "harness.en.v1.json"
_PACKAGE = __name__.rpartition(".")[0]

_current = SPANISH
_english: dict[str, str] | None = None  # each Spanish text → its English
_listed: dict[str, list[str]] = {}  # module → the constants that hold those texts
_written: dict[tuple[str, str], Any] = {}  # (module, constant) → its value as written, in Spanish


def current() -> str:
    """The language the harness is written in now: «es» or «en»."""
    return _current


def _load() -> dict[str, str]:
    global _english, _listed
    if _english is None:
        data = json.loads(_FILE.read_text(encoding="utf-8"))
        _english = {str(pair[0]): str(pair[1]) for pair in data["texts"]}
        _listed = {str(module): [str(name) for name in names] for module, names in data["constants"].items()}
    return _english


def t(text: str) -> str:
    """A text written inside a function, in the language in use: as written in Spanish, its English from the data in
    English (one the data lack stays as written, and the test of the data says so)."""
    return text if _current == SPANISH else _load().get(text, text)


def said(value: Any) -> Any:
    """A constant's value in the language in use: every text in it (a text, or the texts of a tuple, list, set or
    dictionary, keys too; a compiled pattern by its text) that the data translate."""
    if _current == SPANISH:
        return value
    english = _load()
    if isinstance(value, str):
        return english.get(value, value)
    if isinstance(value, re.Pattern):
        return re.compile(english[value.pattern], value.flags) if value.pattern in english else value
    if isinstance(value, tuple):
        return tuple(said(item) for item in value)
    if isinstance(value, list):
        return [said(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return type(value)(said(item) for item in value)
    if isinstance(value, dict):
        return {said(key): said(item) for key, item in value.items()}
    return value


def rebind(module: str, name: str, value: Any) -> None:
    """Binds a constant to ``value`` in the module that defines it and wherever the same object was imported by that
    name (``from .mind import SYSTEM``): a module that kept the old one would go on writing the other language."""
    home = sys.modules[f"{_PACKAGE}.{module}"]
    old = getattr(home, name)
    for other in list(sys.modules.values()):
        names = getattr(other, "__dict__", None)
        if isinstance(names, dict) and name in names and names[name] is old:
            names[name] = value


def use(language: str) -> bool:
    """Writes the harness in ``language`` from now on. Whether it changed: False for the language already in use and
    for a word that is neither (nothing changes then)."""
    global _current
    if language not in LANGUAGES or language == _current:
        return False
    _load()
    modules = {module: importlib.import_module(f"{_PACKAGE}.{module}") for module in _listed}
    for module, names in _listed.items():
        for name in names:
            _written.setdefault((module, name), getattr(modules[module], name))
    _current = language
    for module, names in _listed.items():
        for name in names:
            rebind(module, name, said(_written[module, name]))
    for module in modules.values():
        if callable(rebuild := getattr(module, "_relanguage", None)):
            rebuild()
    return True
