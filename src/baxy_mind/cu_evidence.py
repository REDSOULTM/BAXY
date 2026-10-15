"""Whether the sub-goal is done: the model's «done» evidence judged against the view and the history (a
citation of what the mission did, never of what was there), and the goals reached without the model (an arrival
by a click's effect, an option already held).
"""

from __future__ import annotations

import re

from . import operation_floor
from .semantic.account_acts import account_act
from .semantic.cu_buscar import (
    chooses_an_option, goal_is_only_the_option, parameter_goal, proof_stems, slot_text, text_slot, undoes_a_state,
)
from .semantic.missions import fold, label_alternatives
from .semantic.cu_semejanza import CLICK_MARGIN, CLICK_SIMILARITY, runner_up
from .cu_vocabulary import CONTENT_COPY_KEYS, CONTENT_WRITTEN_EFFECT_KEYS, _UNSEEN_EFFECT_KEYS, _evidence_rules
from .cu_view import (
    _CHOSEN_STATES, _bare, _chosen, _is_switch, _shown_as_words, _view_holds, _view_lines, citation_pieces,
    find_control, view_contains,
)
from .cu_goals import _goal_names_control, _goal_target, _search_goal
from .cu_fields import _search_box
from .cu_history import _acts_on, _clicks_on, _may_have_acted, only_opened
from .cu_unasked import _REMOVAL_NAME
from .cu_meaning import REASON_ARRIVED_BY_EFFECT, SemanticMatcher, _free_goal_label
from .cu_first_look import _CITATION_MARKS, _new_part_by_identity, _seen_at_start, look_parts
from .cu_text_place import _names_slot
from .cu_creation import _brought_this_subgoal
from .cu_menus import _menu_opened_by


def _arrived_by_effect(goal: str, view: dict, history: list[dict], semantic: SemanticMatcher | None) -> dict[str, object] | None:
    """P3: a sub-goal with no check of its own (a free goal, or a tab whose window never marks it selected) is reached
    when its last step was a verified click that changed the window on the control the goal names (by its whole name,
    or by meaning past the click threshold) and the window shows a line that appeared after it: «done» citing that
    line, which the shell checks on screen like any evidence.

    Never when the click opened something instead of arriving (review of P3, measured on Steam: «BIBLIOTECA» only
    opened the menu «Página principal · Colecciones · Descargas»): a menu the click opened (``_menu_opened_by``), the
    clicked control now expanded, or an open menu in the view. Never for a tab when the window does mark a tab
    selected (then the check decides: a sibling selected means the tab was not reached). Never citing a line that
    carries the clicked name (its tooltip «Dibujar (Alt+D)»)."""

    last = history[-1] if history and isinstance(history[-1], dict) else None
    if last is None or last.get("operation") != "input.visible.click" or last.get("ok") is not True:
        return None
    if last.get("changed") is not True and last.get("surfaceChanged") is not True:
        return None
    if last.get("echo") is True:
        return None
    label = str(last.get("label") or "").strip()
    parsed = _goal_target(goal)
    place = parsed[2] if parsed is not None else _free_goal_label(goal)
    if not label or not place:
        return None
    named = fold(label).strip() == fold(place).strip() or fold(label).strip() in {fold(name) for name in label_alternatives(place)}
    if not named and semantic is not None:
        # Whether the click arrived depends on the match alone (review of lat-e5, finding 3: with E5 loading the step
        # went back to the model, which pressed «Biblioteca de videos» a second time): a loading encoder is waited for,
        # within the mind's one cold allowance.
        scored = semantic.scored(place, {"controls": [{"name": label}, *[
            control for control in (view.get("controls") or []) if isinstance(control, dict)
        ]]}, wait=True)
        top = scored[0] if scored else None
        named = (
            top is not None and fold(top[0]) == fold(label) and top[1] >= CLICK_SIMILARITY
            and top[1] - runner_up(scored, top[0]) >= CLICK_MARGIN
        )
    if not named:
        return None
    controls = [control for control in (view.get("controls") or []) if isinstance(control, dict)]
    if (parsed is not None and parsed[3] == "TabItem") or last.get("kind") == "TabItem":
        if any(
            control.get("kind") == "TabItem" and "selected" in str(control.get("state") or "").split()
            for control in controls
        ):
            return None
    clicked = find_control(view, label)
    if (
        any(control.get("kind") == "Menu" for control in controls)
        or (clicked is not None and "expanded" in str(clicked.get("state") or "").split())
        or _menu_opened_by(view, history, place, goal) is not None
    ):
        return None
    appeared = view.get("newTextAfterClick") if isinstance(view.get("newTextAfterClick"), list) else view.get("newText")
    pressed = fold(label).strip()
    lines = [
        str(line).strip() for line in (appeared if isinstance(appeared, list) else [])
        if isinstance(line, str) and len(str(line).strip()) >= 3 and pressed not in fold(line)
        and view_contains(view, str(line).strip())
    ]
    if not lines:
        return None
    return {"operation": "done", "arguments": {"evidence": lines[0][:80]}, "reason": REASON_ARRIVED_BY_EFFECT}


REASON_ALREADY_HELD = "la opción que pide el objetivo ya estaba elegida en la primera vista"


def _already_held(goal: str, view: dict, history: list[dict]) -> dict[str, object] | None:
    """Pasada r15b (A2: v3-31, «cambia el modo a ventana» with «Ventana» selected on the first look after opening): a
    goal that chooses an option (``chooses_an_option``) whose option the view shows selected before any act of the
    sub-goal (opening the application is none) is reached as it already was: «done» with «already», which the shell
    checks (ComputerUseSuccessCheck.AlreadyChosen) and the final tells as «ya estaba». Only a selection, never a switch
    on: a goal that switches something off reads «on» the other way."""

    if not chooses_an_option(goal) or any(_may_have_acted(step) for step in history):
        return None
    proof = _mission_proof(view, history, goal)
    if proof is None or not proof[1]:
        return None
    name = proof[0]
    if parameter_goal(goal) or not goal_is_only_the_option(goal, name):
        # Review of sistema-cumplido, finding 1: «pon la canción despacito» with «Despacito» selected (selected is not
        # playing), «selecciona juan pérez y bórralo»: the goal asks more than the option held; the model judges.
        return None
    if not any(
        isinstance(control, dict) and fold(control.get("name")).strip() == fold(name).strip()
        and "selected" in str(control.get("state") or "").split()
        for control in view.get("controls") or ()
    ):
        return None
    return {"operation": "done", "arguments": {"evidence": name, "already": True}, "reason": REASON_ALREADY_HELD}


# The kinds a press acts on (an item of a gallery or a list opens what it names); a tab or a tree's item is a place
# already shown when selected, and a switch changes a setting.
_PRESS_KINDS = frozenset({"Button", "SplitButton", "MenuItem", "Hyperlink", "ListItem"})


def _cited_control_name(evidence: str, view: dict) -> str:
    """Evidence written the way the step's prompt lists a control («Document «Documento1»», its kind and its name in
    guillemets, or the name alone in guillemets, or its whole line: «TabItem «Transiciones» · selected focused») is
    that control's name when the view holds a control of that name (and kind, when cited) in every state the line
    cites. Live check of r7, t-long-2: the blank document opened and the done citing it either way was refused as «not
    in the view»; pasada v3 r9 (v3-02, v3-13): the tab and the radio button cited by their line. Anything else stays as
    cited."""

    line = _CONTROL_LINE.match(evidence.strip())
    if line is None:
        return evidence
    kind, name, tail = line.group("kind") or "", line.group("name").strip(), line.group("tail") or ""
    cited_states = {word for word in re.findall(r"[a-z]+", tail.casefold()) if word in _STATE_WORDS}
    controls = view.get("controls") if isinstance(view, dict) else None
    if not name or not isinstance(controls, list):
        return evidence
    held = any(
        isinstance(control, dict) and kind in ("", str(control.get("kind") or ""))
        and str(control.get("name") or "").strip() == name
        and cited_states <= set(str(control.get("state") or "").split())
        for control in controls
    )
    return name if held else evidence


# A control as the step's prompt lists it: its index, its kind and its name in guillemets, then its states and the rest
# of its line after «·» (``compact_view_text``); every part but the name may be left out.
_CONTROL_LINE = re.compile(r"^(?:\d+\s*·\s*)?(?P<kind>[A-Za-z]+)?\s*«(?P<name>[^«»]+)»(?P<tail>\s*·.*)?$")
_STATE_WORDS = frozenset({"selected", "on", "off", "focused", "expanded", "collapsed", "disabled"})


def _chosen_before(view: dict, step: dict) -> bool | None:
    """Whether the look right before this click showed its control chosen (the App's «chosenBeforeClick», folded names
    by step); None when the App did not say."""

    before = view.get("chosenBeforeClick") if isinstance(view, dict) else None
    names = before.get(str(step.get("step"))) if isinstance(before, dict) else None
    if not isinstance(names, list):
        return None
    return _bare(step.get("label")) in {_bare(item) for item in names}


def chosen_by_act(citation: str, view: dict, history: list[dict] | None) -> bool:
    """Pasada v3 r9 (v3-02, v3-09): the citation is a control of the view shown chosen that a verified click of this
    sub-goal pressed while it was not chosen yet: the act chose it, so it is new though its name was on the first look.
    Twin of ComputerUseSuccessCheck.ChosenByAct."""

    cited = _bare(citation)
    controls = view.get("controls") if isinstance(view, dict) else None
    if not cited or not any(_chosen(control) and _bare(control.get("name")) == cited for control in controls or ()):
        return False
    return any(_chosen_before(view, step) is not True for step in _clicks_on(history, cited))


def _mission_proof(view: dict, history: list[dict] | None, goal: str | None) -> tuple[str, bool] | None:
    """What the screen proves of the goal when the model's citation does not (pasada v3 r9: v3-02, v3-09, v3-10, v3-13
    said done citing a line the view does not hold): (name, already).

    A control the goal names shown chosen: by the mission when the sub-goal's last verified click pressed it while not
    chosen (``chosen_by_act``); «already» when no act of the sub-goal touched it but clicks that did not choose it (the
    state asked held before acting). In a goal of writing or searching, the field whose value is the text the
    sub-goal typed (BAXY put it, the window shows it), cited by its name; a search also needs something that appeared
    besides the box. None when nothing proves it, or when two controls could (no guess)."""

    controls = [control for control in (view.get("controls") if isinstance(view, dict) else None) or () if isinstance(control, dict)]
    clicks = [
        step for step in history or ()
        if isinstance(step, dict) and step.get("ok") is True and step.get("operation") == "input.visible.click"
        and not only_opened(step)
    ]
    keyed = any(
        isinstance(step, dict) and step.get("ok") is True and step.get("operation") in {"input.key.press", "input.text.type"}
        for step in history or ()
    )
    last = _bare(clicks[-1].get("label")) if clicks else ""
    found: dict[str, bool] = {}
    for control in controls:
        name = str(control.get("name") or "").strip()
        if not name or not _chosen(control) or not _goal_names_control(goal, name):
            continue
        # Review of ronda 20b (finding 1): «already» only when every click that may have acted on it (an uncertain
        # one too: the box changed, the application's mark did not follow) was verified and found it chosen.
        acted = _acts_on(history, name)
        if _bare(name) == last and chosen_by_act(name, view, history):
            found[name] = False
        elif not keyed and all(step.get("ok") is True and _chosen_before(view, step) is True for step in acted):
            found[name] = True
    if len(found) == 1:
        name, already = next(iter(found.items()))
        return name, already
    if found:
        return None
    said = fold(goal or "").strip()
    if not (_search_goal(goal) or said.startswith(("escribir ", "write ", "type "))):
        return None
    typed = [
        fold(step.get("text")).strip() for step in history or ()
        if isinstance(step, dict) and step.get("ok") is True and step.get("operation") == "input.text.type"
    ]
    if not typed or not typed[-1]:
        return None
    fields = [
        control for control in controls
        if str(control.get("kind") or "") in {"Edit", "ComboBox", "Document"} and str(control.get("name") or "").strip()
        and fold(control.get("value")).strip() == typed[-1]
    ]
    if len(fields) != 1:
        return None
    if _search_goal(goal) and not view.get("newText") and not any(
        str(control.get("kind") or "") not in {"Edit", "ComboBox", "Document", "Text"} and typed[-1] in fold(control.get("name"))
        for control in controls
    ):
        return None
    return str(fields[0].get("name")).strip(), False


def _proved_done(view: dict, history: list[dict] | None, goal: str | None, why: str) -> dict[str, object] | None:
    proof = _mission_proof(view, history, goal)
    if proof is None:
        return None
    name, already = proof
    arguments: dict[str, object] = {"evidence": name}
    if already:
        arguments["already"] = True
    return {"operation": "done", "arguments": arguments, "reason": why}


def _evidence_names_a_press(evidence: str, view: dict, goal: str | None) -> str | None:
    """The one control the evidence names by its whole name, when the goal names it too and it is something to press
    (``_PRESS_KINDS``, not a switch nor disabled): the act a done before any step skipped. A control the goal does not
    name is no act of it (v3-17: «recortar la imagen» citing the gallery's «Galería»)."""

    wanted = fold(evidence).strip(" «»\"'")
    controls = view.get("controls") if isinstance(view, dict) else None
    if not wanted or not isinstance(controls, list) or not _shown_as_words(wanted, fold(goal or "")):
        return None
    named = [
        control for control in controls
        if isinstance(control, dict) and fold(control.get("name")).strip() == wanted
    ]
    if len(named) != 1:
        return None
    control = named[0]
    states = str(control.get("state") or "").split()
    if control.get("kind") not in _PRESS_KINDS or _is_switch(control) or "disabled" in states:
        return None
    name = str(control.get("name") or "")
    # A done says the act is already done: a press made of it never removes nor changes the account (an «Eliminar»
    # on whatever is chosen now, a second «Comprar»), the same veto as every press the model did not choose.
    if _REMOVAL_NAME.search(fold(name)) or account_act(name) is not None:
        return None
    return name


def key_left_the_view_as_it_was(step: dict) -> bool:
    """Ronda 24 (pasada r23 t-menu-4): a verified key whose first look found the window's signature unchanged
    (``sameView``) did nothing a look sees, unless its effect lands where the signature does not look (data
    «computerUse.contentKeys.unseenEffect»; review 4 of ronda 24: the Terminal's Enter that ran a command, the arrow
    that brought it back, the Ctrl+V into its console). Of those, a key whose effect lands on the written text
    («writtenEffect») left the view as it was only when the App also read the same written text (``sameText``); a
    caret, selection, clipboard, save or undo key never does. Twin of ComputerUseSuccessCheck.KeyLeftTheViewAsItWas."""

    if step.get("sameView") is not True:
        return False
    key = fold(step.get("key")).strip().replace(" ", "_")
    if key in CONTENT_COPY_KEYS:
        return False
    if key not in _UNSEEN_EFFECT_KEYS:
        return True
    return key in CONTENT_WRITTEN_EFFECT_KEYS and step.get("sameText") is True


def acted_with_effect(history: list[dict], goal: str | None) -> bool:
    """A verified act of the sub-goal with an effect: a key that did not leave the view as it was
    (``key_left_the_view_as_it_was``), a text, a scroll that moved the content, or
    a click that changed something and is no echo of a query typed before it (the App's verdict, «echo»). Opening the
    application counts only for a goal of opening it (data «evidence.openGoal»). Unless the goal is a search, a text
    typed into a box that only searches («query») and the Enter that sends it are no act, nor is Tab. Twin of
    ComputerUseSuccessCheck.ActedWithEffect."""

    opening = re.match(_evidence_rules()["openGoal"], fold(goal or "").strip()) is not None
    searching = _search_goal(goal)
    query_sent = False
    for step in history:
        if not isinstance(step, dict) or step.get("ok") is not True:
            continue
        operation = step.get("operation")
        if operation == "app.open":
            if opening:
                return True
        elif operation == "input.visible.click":
            if only_opened(step):
                continue
            if step.get("changed") is True and step.get("echo") is not True:
                return True
            query_sent = False
        elif operation == "input.text.type":
            if not searching and step.get("query") is True:
                query_sent = True
                continue
            return True
        elif operation == "input.key.press":
            key = fold(step.get("key")).strip()
            if key == "tab" or (key == "enter" and query_sent):
                continue
            if key_left_the_view_as_it_was(step):
                # Ronda 24 (pasada r23 t-menu-4): a key after which the window kept what a look sees did nothing.
                continue
            return True
        elif operation == "input.scroll":
            if step.get("changed") is True:
                return True
    return False


# Ronda 24: the kinds of a control that is an option a press chooses (a list's entry, a radio button, a tab); a combo
# box's value is one too. Twin of ComputerUseSuccessCheck.OptionKinds.
_OPTION_KINDS = frozenset({"ListItem", "RadioButton", "TabItem"})
# The kinds of a control a press makes something with (the product's command). Twin of ProductCommandKinds.
_PRODUCT_COMMAND_KINDS = frozenset({"Button", "SplitButton", "MenuItem", "Hyperlink"})


def product_noun(goal: str | None) -> str | None:
    """The folded noun of the product a goal makes («captura» of «sacá una captura de pantalla completa»: data
    «evidence.productGoal», group 1), or None for a goal that makes no product. Twin of
    ComputerUseSuccessCheck.ProductNoun."""

    found = re.search(_evidence_rules()["productGoal"], fold(goal or "").strip())
    return found.group(1) if found is not None else None


def _option_chosen_by_act(piece: str, view: dict, history: list[dict]) -> bool:
    name = fold(piece).strip(_CITATION_MARKS)
    if not name:
        return False
    option = any(
        isinstance(control, dict) and (
            (control.get("kind") in _OPTION_KINDS and fold(control.get("name")).strip() == name)
            or (control.get("kind") == "ComboBox" and fold(control.get("value")).strip() == name))
        for control in view.get("controls") or ()
    )
    return option and (bool(_acts_on(history, name)) or chosen_by_act(piece, view, history))


def _product_made(history: list[dict], noun: str, goal: str | None) -> bool:
    """Review 1 of ronda 24 (finding 2): a click of the sub-goal on a command (``_PRODUCT_COMMAND_KINDS``) whose name
    carries the product's noun and that acted with an effect (``acted_with_effect``): the product was made. Twin of
    ComputerUseSuccessCheck.ProductMade."""

    word = re.compile(rf"\b{re.escape(noun)}\b")
    return any(
        isinstance(step, dict) and step.get("operation") == "input.visible.click"
        and step.get("kind") in _PRODUCT_COMMAND_KINDS
        and word.search(fold(step.get("label") or step.get("name"))) is not None
        and acted_with_effect([step], goal)
        for step in history or ()
    )


def _option_not_product(evidence: str, view: dict, history: list[dict], goal: str | None) -> str | None:
    """Ronda 24 (pasada r23 v3-33): in a goal of making a product (``product_noun``), a done whose every cited piece is
    an option an act of the sub-goal chose (``_OPTION_KINDS`` or a combo box's value) proves nothing made: the reason
    for the model's retry, naming the view's command that carries the product's noun when there is one. None otherwise.
    Twin of ComputerUseSuccessCheck.OptionNotProduct. Review 1 of ronda 24 (finding 2): the refusal holds only while the
    option is the only news; once a command of the product (``_product_made``) acted with an effect in the sub-goal,
    the product is no longer pending and the done is judged as any other."""

    noun = product_noun(goal)
    if noun is None or _product_made(history, noun, goal):
        return None
    pieces = [evidence] if _view_holds(view, evidence) else citation_pieces(evidence)
    if not pieces or not all(_option_chosen_by_act(piece, view, history) for piece in pieces):
        return None
    word = re.compile(rf"\b{re.escape(noun)}\b")
    command = next((
        str(control.get("name")) for control in view.get("controls") or ()
        if isinstance(control, dict) and control.get("kind") in _PRODUCT_COMMAND_KINDS
        and "disabled" not in str(control.get("state") or "").split() and word.search(fold(control.get("name")))
    ), None)
    chosen = str(evidence)[:40]
    if command is not None:
        return f"«{chosen}» es una opción elegida: no hay {noun} hasta pulsar «{command[:60]}»"
    return f"«{chosen}» es una opción elegida: hacé el paso que produce {noun}"


def _seen_at_start_all(evidence: str, view: dict, history: list[dict] | None, goal: str | None = None) -> bool:
    """The citation showed on the first look and no act chose it (``_seen_at_start``, ``chosen_by_act``). Ronda 20 P6:
    a citation of several lines (« | ») that the view holds only piece by piece is new when at least one piece is.
    Ronda 20 P4: a piece new by identity (``_new_part_by_identity``) is new though its name showed before. Mirror of
    EvidenceRefusal's «seen_at_start»."""

    pieces = [evidence] if _view_holds(view, evidence) else citation_pieces(evidence)
    return all(
        _seen_at_start(piece, view) and not chosen_by_act(piece, view, history)
        and not _changed_by_its_click(piece, view, history, goal)
        and not _new_part_by_identity(piece, view, history or [], goal)
        for piece in pieces
    )


def _changed_by_its_click(citation: str, view: dict, history: list[dict] | None, goal: str | None = None) -> bool:
    """Ronda 24 (pasada r23, v3-53): the citation is a control of the view that a verified click of the sub-goal pressed
    and changed, by its identity (the App's «changedByClick»), and the control now shows the change the goal asks for
    (``_toward_goal``): what the act changed that way is new though its name showed before. A control no click changed
    stays «seen at the start», and so does one changed the other way (revisión 1 de r24, B1: «activá el wifi» and the
    click left «Wi-Fi» off). Twin of ComputerUseSuccessCheck.ChangedByItsClick."""

    changed = view.get("changedByClick") if isinstance(view, dict) else None
    cited = _bare(citation)
    if not cited or not isinstance(changed, list):
        return False
    controls = view.get("controls") if isinstance(view, dict) else None
    named = [control for control in controls or () if isinstance(control, dict) and _bare(control.get("name")) == cited]
    if not any(_toward_goal(control, goal, history) for control in named):
        return False
    return any(step.get("step") in changed for step in _clicks_on(history, cited))


def _toward_goal(control: dict, goal: str | None, history: list[dict] | None = None) -> bool:
    """Revisión 1 de r24 (B1): the state a control shows goes the way the goal asks. A switch off only in a goal that
    takes something off (``semantic.cu_buscar.undoes_a_state``); a switch on or an item selected only in any other
    goal; a control with neither, only when its value is a value the goal names (whole words: «80» of «poné el volumen
    en 80»). No state and no named value tells no direction. Revisión 2 de r24 (B1): a value the typing of the sub-goal
    wrote (``_typed_value``) is no change of the click, and a search never goes by a value (its proof is a result line,
    never the box that repeats the query). Twin of ComputerUseSuccessCheck.TowardGoal."""

    states = set(str(control.get("state") or "").split())
    undoing = undoes_a_state(goal)
    if "off" in states:
        return undoing
    if states & _CHOSEN_STATES:
        return not undoing
    value = _bare(control.get("value"))
    return (
        bool(value) and not _search_goal(goal) and not _typed_value(control, value, history)
        and _shown_as_words(value, fold(goal or ""))
    )


def _typed_value(control: dict, value: str, history: list[dict] | None) -> bool:
    """Revisión 2 de r24 (B1): a verified ``input.text.type`` of the sub-goal wrote the value the control shows: its text
    is that value, or it typed into that control after a click on it. The click before the typing takes no credit for
    what the typing wrote («buscar receta»: a click on the box «Buscar», then «receta» typed into it). Twin of
    ComputerUseSuccessCheck.TypedValue."""

    name = _bare(control.get("name"))
    steps = [step for step in history or () if isinstance(step, dict) and step.get("ok") is True]
    clicked = [step.get("step") for step in _clicks_on(steps, name) if isinstance(step.get("step"), int)]
    return any(
        step.get("operation") == "input.text.type"
        and (_bare(step.get("text")) == value or (
            bool(name) and _bare(step.get("into") or step.get("field")) == name
            and isinstance(step.get("step"), int) and any(step["step"] > at for at in clicked)))
        for step in steps
    )


def _unrelated_evidence(evidence: str, view: dict, history: list[dict] | None, goal: str | None) -> bool:
    """Ronda 22 (pasada r18: t4-c06 cited the gallery «Excel | Inicio | 1 | Nuevo | 2…» for «crea un blank workbook»,
    t4-c13 the notice «DOCUMENTO DE SOLO LECTURA» for the bold): every piece of the citation new on screen (as
    ``_seen_at_start_all`` reads it) is a notice of the window's own state (data «evidence.noticeText») that shares no
    word of the goal (``semantic.cu_buscar.proof_stems``: data «evidence.relevanceFillers» and the window's process name
    aside, the alias groups of «computerUse.evidenceAliases» and «evidence.creatingKin»), and no control a click of the
    sub-goal chose (now chosen) relates. Revisión 3 de r22 (bloqueante B1): any other new text proves by being new after
    the act, whatever its words (a song in another control, the state a key left, the tab a chord chose). A goal with no word of its own is not judged, nor a search
    (its proof is a result line besides the box, ``_holds_typing``), nor a view with no first look (nothing tells which
    piece is new). Mirror of EvidenceRefusal's «unrelated»."""

    rules = _evidence_rules()
    first_look = view.get("firstLook") if isinstance(view, dict) else None
    if not isinstance(first_look, str) or not first_look or re.search(rules["searchGoal"], fold(goal or "").strip()):
        return False
    window = view.get("window") if isinstance(view, dict) else None
    process = fold(window.get("process") if isinstance(window, dict) else "")
    drop = [*rules["relevanceFillers"], *re.findall(r"[a-z0-9]+", process)]
    kin = [
        *operation_floor.floor_data()["computerUse"]["evidenceAliases"]["groups"], *rules["creatingKin"],
        rules["numberKin"],
    ]
    asked = proof_stems(goal, drop, kin)
    if not asked:
        return False
    notice = re.compile(rules["noticeText"])
    measured = re.compile(rules["measuredValue"])

    def related(text: str) -> bool:
        # Revisión 3 de r22 (bloqueante B1): only a notice of the window's own state that shares no word of the goal
        # relates to nothing. Any other new text proves by being new after the act, whatever its words: the song a
        # click on «Siguiente» brought in another control, the «Reproducir (k)» a key left, the tab a chord chose.
        return any(
            notice.search(fold(part)) is None
            or measured.search(fold(part)) is not None or bool(proof_stems(part, drop, kin) & asked)
            for part in citation_pieces(text)
        )

    pieces = [evidence] if _view_holds(view, evidence) else citation_pieces(evidence)
    if any(_new_part_by_identity(piece, view, history or [], goal) for piece in pieces):
        # Revisión 2 de r22: a part new by identity is the new thing a command the goal names brought, related by it.
        return False
    fresh = [piece for piece in pieces if not _seen_at_start(piece, view) or chosen_by_act(piece, view, history)]
    if any(related(piece) for piece in fresh) or _act_changed_its_control(view, history):
        return False
    labels = [
        str(step.get("label") or "") for step in history or ()
        if isinstance(step, dict) and step.get("ok") is True and step.get("operation") == "input.visible.click"
    ]
    return not any(label and related(label) and chosen_by_act(label, view, history) for label in labels)


def _switch_state(control: object) -> str:
    """The switch state a control shows («on», «off»), or empty: selection, focus and an opened list are no switch."""

    states = str(control.get("state") or "").split() if isinstance(control, dict) else []
    return "on" if "on" in states else "off" if "off" in states else ""


def _act_changed_its_control(view: dict, history: list[dict] | None) -> bool:
    """Revisión 2 de r22 (bloqueante 1): a verified click of the sub-goal changed its own control, whatever the words:
    the control it pressed, by its identity (the App's «changedByClick», ComputerUseSuccessCheck.ChangedByClick:
    «Reproducir (k)» now «Pausa (k)», «Silenciar» now «Activar sonido», «Wi-Fi» now on); a switch the click named, now
    on and chosen by the act (``chosen_by_act``), or now off after the look before the click showed it on; or the
    option the click chose, now the whole value of a control the first look showed with another value («Elige tu
    modo»: «Claro» now «Oscuro»). An entry only selected is none of these (ronda 20b: what the act chose in place
    proves no arrival). Twin of ComputerUseSuccessCheck.ActChangedItsControl."""

    clicks = [
        step for step in history or ()
        if isinstance(step, dict) and step.get("ok") is True and step.get("operation") == "input.visible.click"
        and not only_opened(step)
    ]
    if not clicks:
        return False
    changed = view.get("changedByClick") if isinstance(view, dict) else None
    if isinstance(changed, list) and any(step.get("step") in changed for step in clicks):
        return True
    controls = [control for control in (view.get("controls") if isinstance(view, dict) else None) or ()
                if isinstance(control, dict)]
    first_look = view.get("firstLook") if isinstance(view, dict) else None
    before = {part for part in (first_look if isinstance(first_look, str) else "").split("\n") if part}
    for click in clicks:
        label = _bare(click.get("label"))
        if not label:
            continue
        named = [control for control in controls if _bare(control.get("name")) == label]
        if any(_switch_state(control) == "on" for control in named) and chosen_by_act(label, view, history):
            return True
        if any(_switch_state(control) == "off" for control in named) and _chosen_before(view, click) is True:
            return True
        if before and any(
            fold(control.get("value")).strip() == label and fold(control.get("name"))
            and fold(control.get("name")) + "\t" + fold(control.get("value")) not in before
            and any(part == fold(control.get("name")) or part.startswith(fold(control.get("name")) + "\t") for part in before)
            for control in controls
        ):
            return True
    return False


def _holds_typing(evidence: str, history: list[dict], view: dict, goal: str | None) -> bool:
    """The citation is, or holds by plain containment (glued to another word too), a text typed in this sub-goal or in
    an earlier mission of the session (the App's «typedInSession»), and nothing but a field or the written text shows
    it: no item named so, no window title and, in a search, fewer than two result lines that repeat it (a line saying
    nothing was found is none). Mirror of EvidenceRefusal's «typed_by_baxy»."""

    cited = fold(evidence).strip(_CITATION_MARKS)
    if len(cited) < 3:
        return False
    typed = [
        fold(step.get("text")).strip(_CITATION_MARKS) for step in history
        if isinstance(step, dict) and step.get("ok") is True and step.get("operation") == "input.text.type"
    ]
    earlier = view.get("typedInSession") if isinstance(view, dict) else None
    typed += [fold(text).strip(_CITATION_MARKS) for text in earlier or [] if isinstance(text, str)]
    if not any(len(text) >= 3 and (text in cited or cited in text) for text in typed):
        return False
    window = view.get("window") if isinstance(view, dict) else None
    if isinstance(window, dict) and cited in fold(window.get("title")):
        return False
    # Revisión 3 de la ronda 21 (twin of the App's ComparedControls there): a control listed only for the goal's words
    # («reserved») shows nothing of the act; its name carries the goal's words, mostly what BAXY typed.
    if any(
        isinstance(control, dict) and control.get("reserved") is not True
        and str(control.get("kind") or "") not in {"Text", "Edit", "ComboBox", "Document"}
        and cited in fold(control.get("name"))
        for control in (view.get("controls") if isinstance(view, dict) else None) or []
    ):
        return False
    if _search_goal(goal):
        nothing_found = re.compile(_evidence_rules()["noResults"])
        results = [line for line in (fold(line) for line in _view_lines(view)) if cited in line and not nothing_found.search(line)]
        return len(results) < 2
    return True


def _slot_written(evidence: str, view: dict, history: list[dict], goal: str | None) -> bool:
    """Ronda 24 (pasada r23, v3-08): the citation is the literal text the goal puts in a part it names
    (``semantic.cu_buscar.slot_text``, «ponele de título Lista del super» → «Lista del super», part «titulo»), a verified
    step of the sub-goal typed it into a field that names that part (``_names_slot``: «Título de página»), and that
    field of the view, no search box, shows it as its whole value: the act asked, done and seen. A text typed into a
    field that does not name the part (a search box) proves nothing of it. Revisión 3 de r24 (B1: «ponele de nombre
    «Gym» a la playlist» typed «Gym» into «Nombre» of the dialog «Editar detalles» brought, with «Guardar» unpressed):
    a field of a form still to save holds a text, not the act (``_form_left_unsaved``). Revisión 4 de r24 (B1: «ponele
    de título «pruebas» a la pestaña» typed «pruebas» into «Título de la pestaña», the rename box the click on «Cambiar
    nombre de pestaña» brought, with no Enter and the tab still named the old way): a field the sub-goal itself brought
    (``_field_brought``) is a passing box until a verified click on a button that saves or confirms came after the
    typing; until then the proof is what shows the name outside a field (the item named so)."""

    slot = text_slot(goal)
    text = slot_text(goal) if slot is not None else None
    cited = _bare(evidence)
    if not text or not cited or cited != _bare(text):
        return False
    fields = {
        _bare(control.get("name")): control
        for control in (view.get("controls") if isinstance(view, dict) else None) or ()
        if isinstance(control, dict) and control.get("kind") in {"Edit", "Document", "ComboBox"}
        and _names_slot(control.get("name"), slot) and not _search_box(view, control)
        and _bare(control.get("value")) == cited
    }
    typed = [
        position for position, step in enumerate(history)
        if isinstance(step, dict) and step.get("ok") is True and step.get("operation") == "input.text.type"
        and _bare(step.get("text")) == cited and _bare(step.get("field") or step.get("into")) in fields
    ]
    if not typed:
        return False
    after = history[typed[-1] + 1:]
    field = fields[_bare(history[typed[-1]].get("field") or history[typed[-1]].get("into"))]
    if _field_brought(field, view) and not _commit_clicked(after):
        return False
    return not _form_left_unsaved(view, after)


def _field_brought(control: dict, view: dict) -> bool:
    """Revisión 4 de r24 (B1): a field the sub-goal brought, never one already on its first look (v3-08's «Título de
    página»): its name is among the lines the last verified click made appear (the App's «newTextAfterClick»), or parts
    with its name, whatever value they hold (the typing changed it), show more times than on the sub-goal's first look
    (Explorer's rename box «Nombre» beside the column «Nombre»). Without either look, nothing counts as brought. Twin
    of ComputerUseSuccessCheck.FieldBrought."""

    name = fold(control.get("name")).strip()
    if not name or not isinstance(view, dict):
        return False
    appeared = view.get("newTextAfterClick")
    if isinstance(appeared, list) and any(isinstance(line, str) and fold(line).strip() == name for line in appeared):
        return True
    first_look = view.get("firstLook")
    if not isinstance(first_look, str) or not first_look.strip():
        return False
    key = fold(control.get("name")).replace("\n", " ").replace("\r", " ")

    def named(parts: list[str]) -> int:
        return sum(1 for part in parts if part.split("\t", 1)[0] == key)

    return named(look_parts(view)) > named(first_look.split("\n"))


def _commit_clicked(after: list[dict]) -> bool:
    """A verified click that changed something on a button that saves or confirms (data «evidence.commitControl»)
    among ``after``. Twin of ComputerUseSuccessCheck.CommitClicked."""

    commit = _evidence_rules()["commitControl"]
    return any(
        isinstance(step, dict) and step.get("ok") is True and step.get("changed") is not False
        and step.get("operation") == "input.visible.click" and re.search(commit, fold(step.get("label")).strip())
        for step in after
    )


def _form_left_unsaved(view: dict, after: list[dict]) -> bool:
    """Revisión 3 de r24 (B1): a button that saves or confirms (data «evidence.commitControl») that this sub-goal
    brought (``_brought_this_subgoal``: the form the sub-goal opened, never a «Guardar» on screen all along) is on
    offer, and no verified click on such a button came after the typing (``after``): what was typed sits in a form
    still to save, so nothing is set yet. The rule of ``_creation_shown`` and ``_form_button_cited``. Twin of
    ComputerUseSuccessCheck.FormLeftUnsaved."""

    commit = _evidence_rules()["commitControl"]
    if not isinstance(view, dict) or not any(
        isinstance(item, dict) and item.get("kind") in {"Button", "SplitButton"}
        and re.search(commit, fold(item.get("name")).strip()) and _brought_this_subgoal(item, view)
        for item in view.get("controls") or ()
    ):
        return False
    return not _commit_clicked(after)


def _entry_shown(evidence: str, view: dict, history: list[dict]) -> bool:
    """The evidence is the value a list box of the view shows now, and a verified step of this sub-goal chose that
    entry in that box by pattern (``entry``: one of its own entries, never a text written into it)."""

    cited = fold(evidence).strip(" «»\"'")
    if not cited:
        return False
    boxes = [
        control for control in (view.get("controls") or []) if isinstance(control, dict)
        and str(control.get("kind")) == "ComboBox" and fold(control.get("value") or "").strip() == cited
    ] if isinstance(view, dict) else []
    return any(
        isinstance(step, dict) and step.get("operation") == "input.text.type" and step.get("ok") is True
        and step.get("entry") is True and fold(step.get("text")).strip() == cited
        and any(fold(box.get("name")).strip(" :") == fold(step.get("field")).strip(" :") for box in boxes)
        for step in history
    )


def _echoes_typing(evidence: str, history: list[dict], *, contained: bool = True) -> bool:
    """The evidence is a text typed in this sub-goal, or (``contained``) holds one as whole words while no verified
    click after that typing moved the window elsewhere: what is on screen then may be there only because it was
    typed. A goal of writing a text is proved by the text, so it only refuses the bare echo."""

    cited = fold(evidence).strip(" «»\"'")
    for position, step in enumerate(history):
        if not isinstance(step, dict) or step.get("operation") != "input.text.type":
            continue
        typed = fold(step.get("text")).strip()
        if not typed:
            continue
        if cited == typed:
            return True
        moved = any(
            isinstance(later, dict) and later.get("ok") is True and later.get("changed") is not False
            and later.get("operation") in {"input.visible.click", "app.open"}
            for later in history[position + 1:]
        )
        if contained and len(typed) >= 3 and not moved and re.search(rf"(?<!\w){re.escape(typed)}(?!\w)", cited):
            return True
    return False
