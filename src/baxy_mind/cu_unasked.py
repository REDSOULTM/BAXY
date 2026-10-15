"""What nobody asked for: an act in the person's name, a text the request did not say, a press that opens the
help or another tab, removes or discards, and the safety filters of a list opened without the model.
"""

from __future__ import annotations

import re

from .semantic.account_acts import account_act, goal_asks_for, request_carries, world_act
from .semantic.cu_buscar import OPENS_ELSEWHERE, asks_a_new_tab, frame_button
from .semantic.missions import fold, label_alternatives, writes_or_sends
from .semantic.request import evident_language, name_language
from .semantic.cu_semejanza import acts_on_the_window
from .cu_vocabulary import _WORD, _function_words, _own_words
from .cu_goals import _PLACE_NAMED, _POSSESSIVE, _goal_target, _placing_goal, _search_goal
from .cu_window import _web_browser


# A press that throws away what is being made («Descartar», «Discard»): never made of a text aimed at it.
_DISCARD_NAME = re.compile(r"(?<!\w)(?:descart\w*|discard\w*|desechar)(?!\w)")


def unasked_text(text: str, goal: str | None, objective: str | None) -> str | None:
    """The refusal's code when the model types a text the request did not ask for, else None. One rule, two reaches:

    - any goal: a lone letter the request never says as a word (live v3-11: «n» typed as a section's name);
    - a goal that goes somewhere, presses or looks (``_placing_goal``), never a search's nor one that writes or sends:
      a text that does not come from the request (estabilización G2, tandas f2 del notebook t2-c03: going to
      «pantalla», the model typed in Settings' search «d ingo, II de octubre», the lock screen's date read by OCR).

    A text comes from the request when one of its words (three letters or more, no function word) is a word of the
    request, of the goal or of the other names of the goal's place (``label_alternatives``), or shares its first
    letters with one (``stemLength``): the place's name or a search for it, «youtube.com» for «andá a youtube». Numbers
    and signs are never judged («2^10» for «2 elevado a 10», «2» for «dos»): they stay the model's, as an abbreviation
    or a code does; nor is a text in the other language than the place's (a translation of its name)."""

    if not objective:
        return None
    typed = fold(text).strip()
    said = fold(f"{objective} {goal or ''}")
    if len(typed) == 1 and typed.isalpha():
        return None if re.search(rf"(?<!\w){re.escape(typed)}(?!\w)", said) else "text_not_requested"
    if not _placing_goal(goal) or _search_goal(goal) or fold(goal).startswith("buscar ") or writes_or_sends(goal):
        return None
    common = _function_words()
    words = [word for word in re.findall(r"[a-z]+", typed) if len(word) > 2 and word not in common]
    if not words:
        return None
    parsed = _goal_target(goal or "")
    place = parsed[2] if parsed is not None else ""
    language = name_language(place) or evident_language(objective)
    if language is not None and name_language(text) not in (None, language):
        # The place said in the window's other language (pasada r30 v3-03: «slide sorter» looked up as «Organizador de
        # diapositivas»): a translation the model makes, as ``translate_label`` does, never judged word by word.
        return None
    sources = set(_WORD.findall(f"{said} {fold(' '.join(label_alternatives(place)))}"))
    stem = _own_words()[1]
    if any(word in sources or any(len(source) >= stem and word[:stem] == source[:stem] for source in sources)
           for word in words):
        return None
    return "types_unasked_text"


# A control that removes what is chosen (a list of programs, a file manager's delete): with it on offer, Enter on the
# chosen item is no safe default. Whole words, so «Borradores» or «Quitarse» names nothing here.
_REMOVAL_NAME = re.compile(
    r"(?<!\w)(?:desinstal\w*|uninstall\w*|elimin(?:ar|a)|delete|borr(?:ar|a)|quit(?:ar|a)|remove)(?!\w)"
)


# Help and the web (r9, v3-41 and v3-44: Control Panel's search offered «Buscar "…" en Ayuda y soporte técnico de
# Windows», the routine pressed it as the result naming the place and the mission went on in a browser's help page;
# v3-04: «Obtener ayuda sobre …»). Words of the offer, never an application's name. Only the offer to look something
# up there: a bare «Ayuda»/«Help» menu only opens a menu (whose «Acerca de» or «Buscar actualizaciones» a request may
# want), and an entry that names the help without offering a search is no lookup of the person's words.
_OPENS_HELP = re.compile(
    r"\b(?:buscar|busca|search|searches|look up)\b.*"
    r"\b(?:(?:en|in|on)\s+(?:la\s+|the\s+)?(?:ayuda|help|soporte|support|web|internet|linea)|online)\b"
    r"|\b(?:buscar|busca|search)\s+(?:en\s+)?(?:la\s+|the\s+)?(?:web|internet)\b"
    r"|\b(?:obtener|obtene|get)\s+(?:ayuda|help)\s+(?:sobre|con|para|acerca de|with|on|about|for)\b"
    r"|\b(?:ayuda|help)\s+(?:y|and)\s+(?:soporte|support)\b"
)
# The person asks for help or for the web: help words, or a search or a place «en la web / en internet / en el
# navegador». A name that merely holds «web» or «internet» («cámara web», «Opciones de Internet») asks for neither.
_ASKS_HELP = re.compile(
    r"\b(?:ayuda|help|soporte|support|asistencia)\b"
    r"|\b(?:busca\w*|search\w*|googlea\w*|look\w* up)\b.*\b(?:web|internet|linea|online|navegador|browser)\b"
    r"|\b(?:en|in|on)\s+(?:la\s+|el\s+|the\s+)?(?:web|internet|navegador|browser)\b"
)


def opens_help(name: object, view: dict | None, *said: object) -> bool:
    """The control or line ``name`` offers the help or a web search, and nothing the person said (``said``: the goal,
    the request, the target) asks for help or the web, in a window that is no web browser: never pressed (rule 4 of
    the r9 task «teclas sin efecto»: a desktop application's mission never ends in a browser's help)."""

    if not _OPENS_HELP.search(fold(name)):
        return False
    if any(_ASKS_HELP.search(fold(text)) for text in said if text):
        return False
    return not (isinstance(view, dict) and _web_browser(view))


def _safe_to_unfold(control: dict, goal: str | None = None) -> bool:
    """The safety filters of a list opened without the model: never one named for an account act, an act that goes out
    to the world (ronda 29, v3-08 and v3-09: the list of «Compartir» opened blind asked the person to confirm what
    nobody had asked), a removal, a discard, the window's frame or an act on the window. A name that opens another tab
    is fine: only its list opens. With the ``goal`` that names the control, an act in the person's name it asks for
    («hacer clic en reproducir») is no reason to refuse it (``unasked_act``)."""

    name = str(control.get("name") or "")
    folded = fold(name)
    acted = account_act(name) if goal is None else unasked_act(name, goal)
    return not (
        acted is not None or world_act(name) is not None
        or _REMOVAL_NAME.search(folded) or _DISCARD_NAME.search(folded)
        or frame_button(folded) or acts_on_the_window(name) or "disabled" in str(control.get("state") or "").split()
    )


# A control that opens another tab or window (``OPENS_ELSEWHERE``, from ``semantic.cu_buscar``): the mission's window
# would stop being the one in front.
_ELSEWHERE_WORDS = re.compile(r"\b(?:pestana|ventana|tab|window)s?\b")


def _request_opens_one(objective: str | None, history: list[dict], goal: str | None = None) -> bool:
    """The person's request asks to open a new tab or window for this sub-goal (``semantic.cu_buscar.asks_a_new_tab``,
    r9 v3-37: the model's click on «Nueva pestaña» was refused) and it has not opened one yet: one opened by a click or
    by Ctrl+T that changed the window ends it."""

    return asks_a_new_tab(objective, goal) and not any(
        isinstance(step, dict) and step.get("ok") is True and (
            (step.get("operation") == "input.visible.click" and OPENS_ELSEWHERE.search(fold(step.get("label"))) is not None)
            or (step.get("operation") == "input.key.press" and step.get("key") == "ctrl_t" and step.get("sameView") is not True)
        )
        for step in history
    )


def unasked_act(clicked: object, goal: str | None, objective: str | None = None) -> str | None:
    """The act in the person's name (``account_act``: following, saving, liking, installing, the session, playing or
    pausing) that pressing ``clicked`` would do and the goal does not ask for; None when it does none or the goal asks
    for it. The control that IS the place a goal «ir a X» names (its whole name: «Tus me gusta») only goes there; one
    that merely mentions it («Seguir a Tu biblioteca», «Reproducir Tu biblioteca») does the act. An act the request
    carries (``request_carries``: «en Spotify poné Los Bunkers» reaches here as «activar bunkers») is asked by the
    request for any sub-goal that is not going to a place or a search («ir a tu biblioteca y poné Rock» plays in its
    second sub-goal, never on the way to the library)."""

    act = account_act(clicked)
    if act is None or goal_asks_for(goal or "", act):
        return None
    folded_goal = fold(goal or "")
    if request_carries(act) and goal_asks_for(objective or "", act) and not folded_goal.startswith(("ir a ", "buscar ")):
        return None
    place = _PLACE_NAMED.match(folded_goal)
    goes_there = place is not None and _POSSESSIVE.sub("", fold(clicked)).strip() == place.group("place").strip()
    return None if goes_there else act


def _rule_presses_unasked(step: object, goal: str | None, objective: str | None = None) -> bool:
    """Encargo S (banco e2 u1: going to «Tu biblioteca» a rule pressed «Pausar Tu biblioteca» on a list nobody asked to
    play): a rule's or a match's click never does an act in the person's name the goal does not ask for
    (``unasked_act``); the step is the model's, and its click passes the same guard."""

    if not isinstance(step, dict) or step.get("operation") != "input.visible.click":
        return False
    arguments = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
    return unasked_act(arguments.get("label"), goal, objective) is not None
