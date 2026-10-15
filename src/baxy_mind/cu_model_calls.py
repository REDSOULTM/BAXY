"""The short calls to the local model besides the step: a label's names in the other language, the clauses of
a long request, and the route hints of a goal changed through menus or dialogs.
"""

from __future__ import annotations

from typing import Any, Iterable

from .semantic.missions import fold, label_translatable, model_clauses_fit, state_change_value
from .cu_view import view_contains


def _gbnf_quoted(value: str) -> str:
    """A GBNF literal that matches the JSON text ``"value"``."""

    return '"\\"' + value + '\\""'


def _gbnf_string(name: str, limit: int) -> str:
    """A JSON string of at most ``limit`` plain characters (no control characters, simple escapes)."""

    return (
        f'{name} ::= "\\"" {name}-char{{0,{limit}}} "\\""\n'
        f'{name}-char ::= [^"\\\\\\x00-\\x1F] | "\\\\" ["\\\\/bfnrt]'
    )


# A place named in one language on a window shown in the other («go to date and time» on a Spanish Settings) whose
# names the table (semantic/missions.py ``label_alternatives``) does not know: the local model gives the names the
# window may show, and a name is used only where the view shows it (``deterministic_step``). The model is sent the
# label alone: never the request, never the screen, and nothing goes to the web.
TRANSLATE_PROMPT = (
    "Traducís el nombre de un lugar o control de una interfaz de Windows o de una aplicación (página de Configuración, "
    "pestaña, menú, botón) entre español e inglés, con las palabras exactas que esa interfaz muestra en cada idioma. "
    'Devolvés JSON compacto {"es":[…],"en":[…]}: hasta dos nombres por idioma, el más probable primero, sin '
    "explicaciones."
)
_TRANSLATED_NAMES = 2
TRANSLATE_GRAMMAR = "\n".join([
    'root ::= "{" ' + _gbnf_quoted("es") + ' ":" names "," ' + _gbnf_quoted("en") + ' ":" names "}"',
    'names ::= "[" (label ("," label){0,' + str(_TRANSLATED_NAMES - 1) + '})? "]"',
    _gbnf_string("label", 40),
])
TRANSLATE_MAX_TOKENS = 48


# ``translate_label``'s source when the model gave the label itself as its name in both languages.
TRANSLATED_AS_SAID = "as_said"


def translate_label(llm: Any, name: str, cached: object = None) -> tuple[tuple[str, ...], str]:
    """The names ``name`` may carry on screen in the other language, and where they came from: the shell's cache entry
    for this label when it has names (no model call), else one short call to the local model at temperature 0 with
    the label alone. Empty when the label is not translatable (``label_translatable``) or the reply cannot be read."""

    if not label_translatable(name):
        return (), ""
    own = fold(name).strip()
    if isinstance(cached, dict) and isinstance(cached.get("names"), list):
        names = _translated_names(cached["names"], own)
        if names:
            return names, "cache"
    if llm is None:
        return (), ""
    payload = {
        "messages": [
            {"role": "system", "content": TRANSLATE_PROMPT},
            {"role": "user", "content": str(name).strip()},
        ],
        "grammar": TRANSLATE_GRAMMAR,
        "temperature": 0.0,
        "max_tokens": TRANSLATE_MAX_TOKENS,
        "cache_prompt": True,
        "seed": 0,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    try:
        reply = llm._post_schema_object(payload, "la traducción de una etiqueta")
    except (ValueError, RuntimeError, KeyError, TypeError, OSError):
        return (), ""
    if not isinstance(reply, dict):
        return (), ""
    said = [item for language in ("es", "en") if isinstance(reply.get(language), list) for item in reply[language]]
    names = _translated_names(said, own)
    if not names and said and all(isinstance(item, str) and fold(item).strip() == own for item in said):
        # The model wrote the label itself in both languages: a name that does not translate («Hollow Knight»), told
        # apart from a reply with no name (review of lat-e5, finding 1: ``_held_for_the_encoder``).
        return (), TRANSLATED_AS_SAID
    return names, "model"


# A long request said without joiners («abrí Paint cambiá el tamaño a 500 por 500 dibujá un rectángulo guardalo como
# x»): the local model splits it into clauses with the person's own words, and each clause is then read by the
# deterministic readers (semantic/missions.py ``mission_from_model_clauses``); a split with any word the person did
# not say is never used (v3 punto 2, A7).
SPLIT_PROMPT = (
    "Partís un pedido para usar la computadora en las órdenes que dice, en orden. Cada orden con las mismas palabras "
    "del pedido, sin agregar, traducir ni cambiar ninguna. Devolvés JSON compacto {\"clauses\":[…]} sin explicaciones."
)
_SPLIT_CLAUSES = 8
SPLIT_GRAMMAR = "\n".join([
    'root ::= "{" ' + _gbnf_quoted("clauses") + ' ":" "[" clause ("," clause){0,' + str(_SPLIT_CLAUSES - 1) + '} "]" "}"',
    _gbnf_string("clause", 160),
])
SPLIT_MAX_TOKENS = 220


def split_request_clauses(llm: Any, text: str) -> tuple[str, ...]:
    """The clauses of a long request as the local model splits them, validated against the request's own words
    (``model_clauses_fit``); empty when there is no model, the reply cannot be read or the split adds a word."""

    if llm is None or not str(text or "").strip():
        return ()
    payload = {
        "messages": [
            {"role": "system", "content": SPLIT_PROMPT},
            {"role": "user", "content": str(text).strip()},
        ],
        "grammar": SPLIT_GRAMMAR,
        "temperature": 0.0,
        "max_tokens": SPLIT_MAX_TOKENS,
        "cache_prompt": True,
        "seed": 0,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    try:
        reply = llm._post_schema_object(payload, "las cláusulas de un pedido")
    except (ValueError, RuntimeError, KeyError, TypeError, OSError):
        return ()
    if not isinstance(reply, dict) or not isinstance(reply.get("clauses"), list):
        return ()
    return model_clauses_fit(text, reply["clauses"]) or ()


# A free goal of one clause that changes a state through menus or dialogs («en 7-zip cambia la vista a detalles»,
# «filtra el registro para que solo salgan los errores»): when the first view does not show where it ends, or four
# steps changed nothing, the local model names the route a person would follow (at most four labels: menus, tabs,
# buttons). They are hints that rank the controls the step model is shown and are told to it as orientation, never
# acts, checks or text to type; one call per (application, goal).
ROUTE_PROMPT = (
    "Nombrás la ruta que una persona sigue en una aplicación de Windows para hacer un objetivo por sus menús o "
    "diálogos: hasta 4 etiquetas en orden (menús, pestañas, botones u opciones), como las muestra la interfaz, en el "
    "idioma del objetivo, sin verbos ni explicaciones. Devolvés JSON compacto {\"route\":[…]}."
)
ROUTE_HINTS = 4
ROUTE_GRAMMAR = "\n".join([
    'root ::= "{" ' + _gbnf_quoted("route") + ' ":" "[" label ("," label){0,' + str(ROUTE_HINTS - 1) + '} "]" "}"',
    _gbnf_string("label", 40),
])
ROUTE_MAX_TOKENS = 80
# Four steps in a row that changed nothing: the route is asked for then, once.
ROUTE_STALL_STEPS = 4
_ROUTE_LABEL_WORDS = 5
_ROUTE_CACHE: dict[tuple[str, str], tuple[str, ...]] = {}


def route_wanted(goal: str, success_check: str | None, view: dict, history: list[dict]) -> bool:
    """A free goal of one clause that changes a state by menus or dialogs (``semantic.missions.state_change_value``),
    whose first view does not show the value it ends in, or whose last four steps changed nothing."""

    if success_check or not isinstance(view, dict):
        return False
    value = state_change_value(goal)
    if not value:
        return False
    if not history:
        return not view_contains(view, value)
    recent = [step for step in history[-ROUTE_STALL_STEPS:] if isinstance(step, dict)]
    return len(recent) == ROUTE_STALL_STEPS and all(
        step.get("ok") is not True or step.get("changed") is False or step.get("surfaceChanged") is False
        for step in recent
    )


def route_hints(llm: Any, application: str | None, goal: str) -> tuple[str, ...]:
    """At most four labels of the route to a goal, as the local model names them, cached by (application, goal) for
    the life of the mind (an empty answer too: it is never asked twice). Only short labels are kept."""

    key = (fold(application or ""), fold(goal))
    if key in _ROUTE_CACHE:
        return _ROUTE_CACHE[key]
    hints: tuple[str, ...] = ()
    if llm is not None and key[1]:
        payload = {
            "messages": [
                {"role": "system", "content": ROUTE_PROMPT},
                {"role": "user", "content": (f"Aplicación: {application}\n" if application else "") + f"Objetivo: {goal}"},
            ],
            "grammar": ROUTE_GRAMMAR,
            "temperature": 0.0,
            "max_tokens": ROUTE_MAX_TOKENS,
            "cache_prompt": True,
            "seed": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        try:
            reply = llm._post_schema_object(payload, "la ruta de un objetivo")
        except (ValueError, RuntimeError, KeyError, TypeError, OSError):
            reply = None
        labels = reply.get("route") if isinstance(reply, dict) else None
        found: dict[str, str] = {}
        for label in labels if isinstance(labels, list) else ():
            text = " ".join(str(label).split()).strip(" >,;.") if isinstance(label, str) else ""
            folded = fold(text)
            if text and len(text) <= 40 and len(text.split()) <= _ROUTE_LABEL_WORDS and folded not in found:
                found[folded] = text
        hints = tuple(found.values())[:ROUTE_HINTS]
    _ROUTE_CACHE[key] = hints
    return hints


def _translated_names(items: Iterable[object], own: str) -> tuple[str, ...]:
    """The distinct names among ``items`` that are not the label itself, in order, at most four."""

    found: dict[str, str] = {}
    for item in items:
        text = str(item).strip() if isinstance(item, str) else ""
        key = fold(text).strip()
        if key and key != own and key not in found and len(found) < 2 * _TRANSLATED_NAMES:
            found[key] = text
    return tuple(found.values())


class LabelTranslator:
    """The translation of one step's labels: at most one lookup per label (cache or model), and what was asked kept
    for the shell (``report``), which keeps the cache and counts the translations seen or not on screen."""

    def __init__(self, llm: Any, cached: object = None, *, enabled: bool = True) -> None:
        self._llm = llm
        self._enabled = enabled
        self._cached = cached if isinstance(cached, dict) else {}
        self._done: dict[str, tuple[str, ...]] = {}
        # The labels the model gave back as they were said (``TRANSLATED_AS_SAID``): names that do not translate.
        self._as_said: set[str] = set()
        self.report: dict[str, object] | None = None

    def __call__(self, name: str) -> tuple[str, ...]:
        key = fold(name).strip()
        if not self._enabled:
            return ()
        if key in self._done:
            return self._done[key]
        names, source = translate_label(self._llm, name, self._cached.get(key))
        self._done[key] = names
        if source == TRANSLATED_AS_SAID:
            self._as_said.add(key)
        if names:
            self.report = {"label": key, "names": list(names), "source": source}
        return names

    def said_as_is(self, name: str) -> bool:
        """The model, asked, gave ``name`` itself back as its name in the other language (a proper name)."""

        return fold(name).strip() in self._as_said
