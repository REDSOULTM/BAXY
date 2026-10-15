"""Motor de computer use, lado mente (documentacion/computer-use/CONTRATO_VISTA_ACCION.md): elegir un paso.

``decide_step`` da UN paso para el shell: primero lo que el objetivo dicta sin modelo (``cu_rules.deterministic_step``
y las comprobaciones de lo ya cumplido), y si no queda nada la vista compacta va al modelo, que contesta un acto con
esquema JSON estricto a temperatura 0 (``cu_step_prompt``); unas comprobaciones sin modelo deciden si ese acto es
legítimo (``cu_validate``), con un reintento ante el rechazo y lo que aún está cerrado abierto antes de rendirse
(``cu_unfold``). En una misión encadenada cada paso es del sub-objetivo en curso.

Las demás piezas del motor viven en los módulos hermanos ``cu_*``, cada uno importa sólo de los anteriores en el orden
``cu_vocabulary`` → ``cu_finals``; lo que el compositor puede decir de una misión, en ``cu_projection``,
``cu_reply_checks`` y ``cu_finals``.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Callable, Iterable

from . import effect_intent
from .semantic.answer_evidence import citation_misses_question
from .semantic.cu_buscar import naming_words
from .semantic.missions import (
    QUESTION_MARK, label_alternatives, label_translatable, presupposes_an_open_document, writes_or_sends,
)
from .semantic.cu_tipos import OPEN_FILE_GOAL
from .semantic.arguments import with_new_document
from .semantic.windows import asks_for_the_front
from .semantic.limits import LIMIT_CODE, counted_scroll, limits_data, long_list_reached
from .cu_view import _scroll_part, _viewed_control
from .cu_goals import _goal_target, question_step_goal
from .cu_acts import _REASON_FIND, _none
from .cu_window import application_is_in_front, reopens_unraised
from .cu_history import _SPENT_KEYS, spent_steps
from .cu_unasked import _rule_presses_unasked
from .cu_meaning import (
    ENCODER_COLD, ENCODER_FAILED, SOURCE_MODEL, SOURCE_RULE, SOURCE_SEMANTIC, SemanticMatcher, _SEMANTIC_REASONS,
)
from .cu_creation import _created_by_diff, _created_by_effect, _creation_refusal
from .cu_documents import (
    NO_DOCUMENT_OPEN, REASON_NO_DOCUMENT, _new_document_in_front, _new_document_made, _start_page_offer,
)
from .cu_gates import _gate_step, inherited_dialog
from .cu_options import _numbered_list_step
from .cu_menus import _MENU_BAR_HOLDS, _menus_to_open
from .cu_address import _place_by_address
from .cu_chats import call_not_found, chat_search_step, read_in_place
from .cu_lookup import REASON_BY_NAME, _REASON_BURST, _blind_lookup
from .cu_rules import deterministic_step
from .cu_evidence import _already_held, _arrived_by_effect
from .cu_diagnosis import failed_click_diagnosis, presses_a_spent_key, refused_by_the_guard, repeats_the_failed_step
from .cu_validate import NOT_THE_OWN_BUTTON, _presses_system_menu, validate_decision
from .cu_unfold import _exactly_named_step, _order_lookup, _routine_opens_help, _unfold_before_giving_up
from .cu_open_file import open_file_step
from .cu_model_calls import LabelTranslator, route_hints, route_wanted
from .cu_step_prompt import (
    STEP_GRAMMAR, STEP_PROMPT, _SHOWN_CONTROLS, _history_line, _model_step, _rejected_arrow, _similar_controls,
    as_json, compact_view_text, retry_instruction, similar_line,
)


OPERATION = "mission.computer.use"
STEP_REQUEST = "computer.use.step"
STEP_RESULT = "computer.use.step.result"

# El repertorio cerrado del bucle (contrato §2). Goal v3 punto 2: «reveal» trae a la vista un elemento de una lista
# larga por UI Automation (input.scroll con label) y «type» con «field» pone un campo de formulario en un valor.
# Arrastrar y dibujar son un límite declarado (estabilización L): no hay acto que lo haga. Goal v3 B3 (órdenes en
# menús cerrados): «open» con índice abre sólo la flecha o la lista de un control (nunca su clic), «menu» su menú
# contextual y «double» le da doble clic, los tres por la identidad que dio la vista (``input.visible.click`` con
# ``manner``).
ACTS = ("click", "type", "key", "scroll", "reveal", "open", "menu", "double", "done", "none")


def decide_step(
    llm: Any,
    *,
    objective: str,
    goal: str,
    application: str | None,
    success_check: str | None,
    view: dict,
    history: list[dict],
    budget_left: int,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    subgoal: int = 0,
    subgoal_count: int = 1,
    label_translations: object = None,
    encoder: Callable[..., Any] | None = None,
    form_check: str | None = None,
    game_catalog: Iterable[tuple[str, str, str]] | Any = (),
) -> dict[str, object]:
    """One step for the shell: {operation, arguments, reason}; operation is a
    catalog primitive, «done» or «none». In a chained mission ``goal``,
    ``application`` and ``success_check`` are the current sub-goal's
    (``subgoal`` of ``subgoal_count``, 0-based) and ``history`` its steps.
    ``label_translations`` is the shell's cache entry for the goal's label
    ({label: {names: […]}}); a step that looked a translation up says so in
    ``translation`` {label, names, source} (contract §4.4.1). ``encoder`` is the mind's
    interactive E5 encoder (``encode(texts, prefix=…)``): with it the goal's place is
    matched by meaning (``SemanticMatcher``); without it, or when it fails, the step is
    the literal one."""

    # A request that writes or sends goes to the person's own content (a chat, a contact), named as said: no translation
    # and no match by meaning.
    own_content = writes_or_sends(objective)
    translator = LabelTranslator(llm, label_translations, enabled=not own_content)
    semantic = SemanticMatcher(encoder) if encoder is not None and not own_content else None
    history, spent = spent_steps(history)
    token = _SPENT_KEYS.set(spent)
    wanted_token = _VIEW_NAMES.set(None)
    try:
        decision = _decide_step(
            llm, objective=objective, goal=goal, application=application, success_check=success_check, view=view,
            history=history, budget_left=budget_left, application_names=application_names, subgoal=subgoal,
            subgoal_count=subgoal_count, translator=translator, semantic=semantic, form_check=form_check,
            game_catalog=game_catalog,
        )
        ranked_by = _VIEW_NAMES.get()
    finally:
        _SPENT_KEYS.reset(token)
        _VIEW_NAMES.reset(wanted_token)
    scrolled = decision.get("arguments") if isinstance(decision.get("arguments"), dict) else {}
    if (
        decision.get("operation") == "input.scroll" and not scrolled.get("label")
        and _looks_in_a_list(objective, goal, view, scrolled) and long_list_reached(history)
    ):
        # Estabilización L (límite: scroll largo en listas virtualizadas): the list moved by every wheel scroll the
        # sub-goal may spend and still does not end; another one is no step, the limit is said.
        decision = _none("la lista no acaba", code=LIMIT_CODE + "long_list")
    # Ronda 21: the words the listing was ranked by go back to the shell, so the sub-goal's next look keeps a bounded
    # room for the controls they name before the view is cut (a step the rules decided ranks by the table's names).
    wanted = view_wanted(goal, ranked_by if ranked_by is not None else _table_place_names(goal))
    if wanted:
        decision = {**decision, "wanted": wanted}
    if translator.report is not None:
        decision = {**decision, "translation": translator.report}
    # The shell's trace says where the step came from (a rule, a name matched by meaning or the model) and, when the
    # step asked the encoder, what the encoder was: a literal step of a cold encoder is told from a literal choice.
    if "source" not in decision:
        decision = {
            **decision,
            "source": SOURCE_SEMANTIC if decision.get("reason") in _SEMANTIC_REASONS else SOURCE_RULE,
        }
    if semantic is not None and semantic.state:
        decision = {**decision, "encoder": semantic.state}
    if semantic is not None and semantic.spent_ms >= 1.0:
        # lat-e5: the time the step spent in the encoder (waiting for it and encoding), for the shell's trace apart from
        # the model's (r13a: «model_ms» summed 728 s where the model took 188 s).
        decision = {**decision, "encoderMs": int(semantic.spent_ms)}
    return decision


def _looks_in_a_list(objective: str, goal: str, view: dict, scrolled: dict) -> bool:
    """Review of L2, C1: the wheel turns a list of the view (a List, DataGrid, Table or Tree: data «listKinds»). Never
    a scroll the person counted or bounded by a page («bajá 5 veces», «hasta el final de la página»): a document or a
    page is no list. A «mostrar X» sub-goal says the limit in its own step (cu_navigation._reveal_step)."""

    if counted_scroll(objective) or counted_scroll(goal):
        return False
    turned = _viewed_control(view, scrolled.get("index")) if isinstance(view, dict) else None
    return turned is not None and turned.get("kind") in limits_data()["listKinds"]


def _decide_step(
    llm: Any,
    *,
    objective: str,
    goal: str,
    application: str | None,
    success_check: str | None,
    view: dict,
    history: list[dict],
    budget_left: int,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    subgoal: int,
    subgoal_count: int,
    translator: LabelTranslator,
    semantic: SemanticMatcher | None = None,
    form_check: str | None = None,
    game_catalog: Iterable[tuple[str, str, str]] | Any = (),
) -> dict[str, object]:

    # «… y decime si está activado» rides on a single mission's goal for the final to answer; the steps are the
    # goal's, never the question's («escribir hola; y responder: …» types «hola»).
    asked_head, _, asked = str(goal or "").partition(QUESTION_MARK)
    goal = question_step_goal(goal, application)
    # Contract «Seguridad v2»: a developer's or BAXY's own window the request did not name (the view marks it by its
    # process) is never acted on, also when no application is named and the mission works on the window in front.
    window = view.get("window") if isinstance(view, dict) else None
    if isinstance(window, dict) and window.get("protected") is True:
        return _none("la ventana de delante está protegida y no la nombraste", code="window_protected")
    # Encargo IMP2: a chat's reading where the chat already is, and a call to leave that is not there, need no act.
    chat_step = read_in_place(asked, view, history) or call_not_found(goal, view, history)
    if chat_step is not None:
        return chat_step
    # Encargo EX (tanda n6 t4-c06): a modal dialog of the application the mission did not open is said, never pressed.
    inherited = inherited_dialog(view, history, goal, subgoal)
    if inherited is not None:
        return inherited
    # cu-v3-abrir-archivo: a file named to open is opened with the mission's application by the shell (file.open),
    # never searched for in the window; the window it opens is where the mission goes on.
    if goal.startswith(OPEN_FILE_GOAL):
        return open_file_step(goal[len(OPEN_FILE_GOAL):], application, history, application_names)
    # Deterministic first: the application named by the request is not in
    # front and nothing was done yet → bring it to the front (app.open reuses a
    # running window). No model needed for what the request already says.
    # cu-v3-elevacion (r9 v3-23, v3-65): its window runs as administrator and its program opens again with the person's
    # rights (the view says so: window.reopensUnraised) → opened again that way, a new copy BAXY can read and press.
    if application and not history and application_is_in_front(view, application) and not reopens_unraised(view):
        # Ronda 24b (banco r23 u5, n6): a new document asked for with the application already in front is made there
        # (the opening makes and sees it) or, blank and unnamed already, is the one asked for.
        fresh = _new_document_in_front(objective, goal, view, application, application_names, subgoal=subgoal)
        if fresh is not None:
            return fresh
    made = _new_document_made(goal, view, history)
    if made is not None:
        return made
    placed = _place_by_address(objective, goal, application, view, history, application_names, game_catalog)
    if placed is not None:
        return placed
    if application and not history and (
        not application_is_in_front(view, application) or reopens_unraised(view)
    ):
        app_id = effect_intent.resolve_application_catalog_app_id(f"abre {application}", application_names)
        if app_id is not None:
            # v3 point 0 (arreglo 4): the mission opens it behind the person's window, unless the request asks to see
            # it in front.
            arguments: dict[str, object] = {"appId": app_id}
            if asks_for_the_front(objective):
                arguments["foreground"] = True
            # cu-v3-documento-nuevo (t4-c06 «bro abre excel y crea un blank workbook»): a new document asked for is
            # made by the opening, which sees it made. The request's words only, never the sub-goal the model wrote.
            arguments = with_new_document(arguments, (objective,), application_names)
            return {"operation": "app.open", "arguments": arguments, "reason": "la aplicación pedida no está delante"}
    # v3 limits (M2): the application shows a gate (an account to add, a sign-in, an update, a resource it cannot
    # find) instead of its working window, and the goal names nothing of it: said with its cause, nothing pressed on it.
    gated = _gate_step(view, history, objective, goal)
    if gated is not None:
        return gated
    if _start_page_offer(view) is not None and presupposes_an_open_document(objective):
        # Estabilización G3 (tandas f2nb t2-c10, t3-c02, t4-c13: Word and Excel born on their start page for «poné el
        # título en negrita», «en el excel que tengo abierto seleccioná la fila 1»; the model typed «1» twice into the
        # start page's name box, and a sub-goal closed by its own evidence after a click on «Inicio»): a request about
        # a document already open, on a start page with none, is said as such (the floor's
        # computer_use_no_document_open); nothing is typed, clicked or created there.
        return _none(REASON_NO_DOCUMENT, code=NO_DOCUMENT_OPEN)
    # Ronda 20b (v3-43): the shell's check found the goal's place and its question is still unread there
    # (view.questionPending): no rule hunts the place again (the search box, «Atrás», «Actualizar», the address bar
    # until the repeated step); the model reads the datum (a done citing it) or takes the step to the page showing it.
    pending = question_pending(view, history)
    parsed_goal = _goal_target(goal)
    if not pending and semantic is not None and (
        success_check is None or (parsed_goal is not None and parsed_goal[3] == "TabItem")
    ):
        # P3: a sub-goal with no check of its own, or a tab the window never marks selected, reached by the effect of
        # the click on the control it names.
        arrived = _arrived_by_effect(goal, view, history, semantic)
        if arrived is not None:
            return arrived
    if success_check is None and not pending:
        # Pasada r15b (A2): what is already done closes without the model's «done» (v3-03, v3-04, v3-31).
        created = _created_by_effect(goal, view, history) or _created_by_diff(goal, view, history)
        if created is not None:
            return created
        held = _already_held(goal, view, history)
        if held is not None:
            return held
    # Ronda 21 (pasada r18 v3-36): the App's guard refused the rule's or the learned key on a document the mission may
    # not touch (``refused``): the model takes the next step with that refusal in its history.
    # Ronda 22 (r18 t2-c04): a list the goal sets to a number, open or showing its value, decides by its entries;
    # never while the mission's window holds a question still unread (ronda 20b: no rule acts over it), nor after the
    # guard refused a rule's step (integración ronda 22: the list rule is a rule too, so the model takes that step).
    ruled_out = pending or refused_by_the_guard(history)
    # Encargo TZ-WA2: a chat of an application whose data say how its chat list is searched is gone to by the data,
    # never by the model (it pressed «Nuevo chat») nor by the tab rule (it left the «No leídos» filter on).
    chat = None if ruled_out else chat_search_step(goal, application, view, history)
    if chat is not None:
        return chat
    numbered = None if ruled_out else _numbered_list_step(goal, view, history)
    if numbered is not None:
        return numbered
    dictated = None if ruled_out else deterministic_step(
        goal=goal, view=view, history=history, application=application, objective=objective, translate=translator,
        semantic=semantic, success_check=success_check, form_check=form_check,
    )
    if repeats_the_failed_step(dictated, history) or presses_a_spent_key(dictated, view):
        # Ronda 21 (pasada r18 t-scroll-4): a rule's step that would repeat the one that just failed is the model's to
        # decide with that failure in front of it, never a «repeated_step» stop the model never saw. Nor is a key spent
        # on this application (revisión 1, hallazgo b: one the App's guard refused) pressed again by any rule.
        dictated = None
    # r9 (t-menu-3, v3-62, v3-50: 25 steps «e5_cold», 12 «e5_failed»): an encoder that could not answer cannot say
    # whether the window shows the place with other words («Ver» for «View»), so a blind way of looking it up (a
    # shortcut; the wheel changes nothing) is no step of a rule then: the model decides with the view (ctrl_k in a text editor opened
    # its «Insertar vínculo» dialog).
    # Ronda 20 P1 (v3-03): the click on the window's search is blind too while a control of the view shares a word
    # with the place as said or translated (one lookup per label: the step's own translation is cached).
    # Ronda 21 (v3-25): a click by name off the view («windows logs» on a window in Spanish showing «Registros de
    # Windows») is as blind as the search: a tree of hundreds of nodes took the sub-goal's whole clock.
    searching_click = isinstance(dictated, dict) and dictated.get("operation") == "input.visible.click" and dictated.get(
        "reason") in {_REASON_FIND, _REASON_BURST, REASON_BY_NAME}
    blind = _encoder_down(semantic) and _blind_lookup(
        dictated, history, view, _lookup_names(goal, translator) if searching_click else (), objective,
    )
    # Lote r11 (v3-11): a rule's or a match's press that would create what the goal does not name, or create again, is
    # the model's to decide with the view (the refusal is the validation's).
    # Pasada r15b (A1): nor is the window's system menu pressed by a rule or a match the goal does not ask for.
    if dictated is not None and not blind and _creation_refusal(dictated, view, history, goal) is None and not (
        dictated.get("operation") == "input.visible.click"
        and _presses_system_menu(view, dictated.get("arguments"), goal)
    ) and not _routine_opens_help(dictated, view, goal, objective) and not _rule_presses_unasked(dictated, goal, objective):
        return dictated
    last_failed = history[-1] if history and isinstance(history[-1], dict) and history[-1].get("ok") is False else None
    # v3 ronda 5 (lectura, diseño 6): the route's labels rank the controls shown and orient the model; never an act.
    route = route_hints(llm, application, goal) if route_wanted(goal, success_check, view, history) else ()
    place_names = _place_names(goal, view, translator)
    _VIEW_NAMES.set(tuple(dict.fromkeys((*place_names, *route))))
    similar = _similar_controls(goal, view, place_names, semantic)
    user = (
        f"Pedido: {objective}\n"
        + (f"Sub-objetivo {subgoal + 1} de {subgoal_count}\n" if subgoal_count > 1 else "")
        + f"Objetivo: {goal}"
        + (f"\nAplicación: {application}" if application else "")
        + (f"\nSe cumple cuando: {success_check}" if success_check else "")
        + (f"\nRuta probable (pistas, no actos): {' > '.join(route)}" if route else "")
        + f"\nPasos que quedan: {budget_left}\n"
        + ("Historial:\n" + "\n".join(_history_line(step) for step in history[-6:])
           + (f" — {diagnosis}" if (diagnosis := failed_click_diagnosis(last_failed, view)) else "") + "\n" if history else "")
        + (similar_line(similar) + "\n" if similar else "")
        + "Vista:\n" + compact_view_text(
            view, goal=goal, names=tuple(dict.fromkeys((*place_names, *route))),
            similar=[str(control.get("name") or "") for control in similar],
        )
    )
    payload = {
        "messages": [
            {"role": "system", "content": STEP_PROMPT},
            {"role": "user", "content": user},
        ],
        "grammar": STEP_GRAMMAR,
        "temperature": 0.0,
        "max_tokens": 160,
        "cache_prompt": True,
        "seed": 0,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    raw = _model_step(llm, payload)
    if raw is None:
        return {**_none("el modelo no dio un paso legible", code="decision_unreadable"), "source": SOURCE_MODEL}
    decision = validate_decision(
        raw, view=view, history=history, last_failed=last_failed, application_names=application_names, goal=goal,
        objective=objective, success_check=success_check, application=application, semantic=semantic,
    )
    decision = _cites_the_answer(decision, asked, asked_head, view)
    if decision["operation"] == "none" and decision.get("code") in _RETRIED:
        # One more try with the rejection in front of the model (contract §4.4).
        # With a control similar to the objective on screen, the retry names it and offers no «none» (P2: a rejected
        # act followed by «none» ended eleven missions of the r3 pass with the place on screen).
        payload["messages"].append({"role": "assistant", "content": as_json(raw)})
        payload["messages"].append({"role": "user", "content": retry_instruction(
            str(decision["reason"]), similar, _rejected_arrow(raw, view, last_failed),
            admits_done=decision.get("admits_done") is True,
        )})
        raw = _model_step(llm, payload)
        if raw is None:
            return {**_none("el modelo no dio un paso legible", code="decision_unreadable"), "source": SOURCE_MODEL}
        decision = validate_decision(
            raw, view=view, history=history, last_failed=last_failed, application_names=application_names, goal=goal,
            objective=objective, success_check=success_check, application=application, semantic=semantic,
        )
        decision = _cites_the_answer(decision, asked, asked_head, view)
    if decision["operation"] == "none" and not pending:
        # The step was the model's because a similar name was on screen, or a menu bar held the routine's shortcuts
        # back, and the model took none of it: the literal step (the window's search, its shortcut, the wheel) is the
        # fallback, never lost (review finding 1: with the bar's hold the mission stopped where ctrl_k was tried).
        # Without the encoder only the bar's hold made the step the model's: the literal one is asked only then.
        held = _MENU_BAR_HOLDS.get() and bool(_menus_to_open(view, history))
        # Ronda 21 (revisión 1, hallazgo d): the fallback passes the same two guards as the rule's step: after a key the
        # App's guard refused no rule's step is taken, and none that repeats the step that just failed.
        if (semantic is not None or held) and not refused_by_the_guard(history):
            token = _MENU_BAR_HOLDS.set(False)
            try:
                literal = deterministic_step(
                    goal=goal, view=view, history=history, application=application, objective=objective,
                    translate=translator, success_check=success_check,
                )
            finally:
                _MENU_BAR_HOLDS.reset(token)
            # With the encoder down, a blind lookup of a name already looked up is not retried (e5-etiquetas). The
            # lookup a loading encoder left to the model (lat-e5, ``_held_for_the_encoder``) is its fallback like any
            # other: the hold costs one model call, never the mission (review of lat-e5, finding 1).
            if literal is not None and not repeats_the_failed_step(literal, history) and not presses_a_spent_key(
                literal, view
            ) and not (
                semantic is not None and _encoder_down(semantic) and _blind_lookup(literal, history)
            ) and not (
                literal.get("operation") == "input.visible.click"
                and _presses_system_menu(view, literal.get("arguments"), goal)
            ) and not _routine_opens_help(literal, view, goal, objective) and not _rule_presses_unasked(literal, goal, objective):
                return literal
        if budget_left > 1 and decision.get("code") in _UNFOLD_BEFORE_NONE:
            # Ronda 24 (v3-37): the one control of the view whose whole name is what the check or the goal names is
            # pressed before any search of orders; two controls that carry that name leave it to the model.
            exact = _exactly_named_step(goal, success_check, view, history)
            if exact is not None and not repeats_the_failed_step(exact, history) and _creation_refusal(
                exact, view, history, goal
            ) is None and not _presses_system_menu(view, exact.get("arguments"), goal) and not _rule_presses_unasked(
                exact, goal, objective
            ):
                return {**exact, "source": SOURCE_RULE}
            # Ronda 20b, palanca 6 (v3-40 a: «split the pane» lives only in the window's command palette): an order is
            # looked up in the window's search of orders when one is on screen.
            ordered = _order_lookup(goal, view, history)
            if ordered is not None:
                return {**ordered, "source": SOURCE_RULE}
            # (v3-38, v3-39: the mission stopped with 9 steps left and «Configuración» inside the list of a split
            # button): before giving up, what may lead to the goal and is still closed is opened (ronda 24: only that).
            unfolded = _unfold_before_giving_up(view, history, goal, objective, last_failed, semantic=semantic)
            if unfolded is not None:
                return {**unfolded, "source": SOURCE_RULE}
    return {**decision, "source": SOURCE_MODEL}


def question_pending(view: object, history: list[dict]) -> bool:
    """Ronda 20b (v3-43): the shell's check of the goal held on this window after a verified act of the sub-goal, and
    the question the goal carries is still unread on it (the view's ``questionPending``, QuestionDatumUnread). The place
    is reached: no rule hunts it again; the model reads the datum or takes the step to the page that shows it."""

    return (
        isinstance(view, dict)
        and view.get("questionPending") is True
        and any(isinstance(step, dict) and step.get("ok") is True for step in history)
    )


def ends_mission(decision: dict, subgoal: int, subgoal_count: int) -> bool:
    """The step ends the mission as the mind sees it: a «none», or «done» on the last sub-goal. The sidecar then frees
    the E5 worker to the catalog's promotion (``router.release_background``); a step the shell still asks after it
    holds the worker again."""

    operation = decision.get("operation") if isinstance(decision, dict) else None
    return operation == "none" or (operation == "done" and subgoal + 1 >= max(1, subgoal_count))


def _encoder_down(semantic: SemanticMatcher | None) -> bool:
    """The step asked the encoder and it could not answer: still loading, or failed."""

    return semantic is not None and semantic.state in (ENCODER_COLD, ENCODER_FAILED)


def _place_label(goal: str) -> str:
    """The name of the goal's place: the target a goal that names a control says, else the free goal itself when it
    is short enough to be a control's name («Insert a table», «add a new slide»)."""

    parsed = _goal_target(goal)
    return parsed[2] if parsed is not None else str(goal or "").strip()


def _lookup_names(goal: str, translate: Callable[[str], tuple[str, ...]] | None) -> tuple[str, ...]:
    """The place's names a blind lookup is weighed against (``_blind_lookup``): as said, the table's and the other
    language's."""

    label = _place_label(goal)
    if not label:
        return ()
    names = (label, *label_alternatives(label))
    if translate is not None and label_translatable(label):
        names = (*names, *translate(label))
    return names


def _place_names(goal: str, view: dict, translate: Callable[[str], tuple[str, ...]] | None) -> tuple[str, ...]:
    """The other names of the goal's place for ranking the model's listing (``_ranked_controls``): the table's, and the
    other language's (``translate``, one lookup per label) only when the listing is cut, so a view that shows every
    control costs no lookup."""

    label = _place_label(goal)
    if not label:
        return ()
    names = label_alternatives(label)
    controls = view.get("controls") if isinstance(view, dict) else None
    listed = [control for control in controls if not _scroll_part(control, view)] if isinstance(controls, list) else []
    if translate is not None and len(listed) > _SHOWN_CONTROLS and label_translatable(label):
        names = (*names, *translate(label))
    return tuple(dict.fromkeys((label, *names)))


# Ronda 21 (vista ordenada por objetivo): the names the step's listing was ranked by (``_place_names`` and the route),
# set by ``_decide_step`` when it asks the model; None when the step came from a rule before that.
_VIEW_NAMES: ContextVar[tuple[str, ...] | None] = ContextVar("cu_view_names", default=None)
# At most this many words go with the next look (the catalog's bound for «wanted» of input.visible.controls).
_VIEW_WANTED_MAX = 24


def _table_place_names(goal: str) -> tuple[str, ...]:
    """The goal's place and the table's other names for it, without any lookup (a step the rules decided)."""

    label = _place_label(goal)
    return tuple(dict.fromkeys((label, *label_alternatives(label)))) if label else ()


def view_wanted(goal: str | None, names: Iterable[str] = ()) -> list[str]:
    """The goal's words the shell's next look carries («wanted»): the same ``naming_words`` that ``_ranked_controls``
    raises a control by, the longest first (the most telling ones survive the bound), at most ``_VIEW_WANTED_MAX`` of
    at most 64 bytes each."""

    words = sorted(naming_words(goal or "", *(str(name) for name in names)), key=lambda word: (-len(word), word))
    return [word for word in words if len(word.encode("utf-8")) <= 64][:_VIEW_WANTED_MAX]


_RETRIED = frozenset({
    NOT_THE_OWN_BUTTON,
    "label_not_visible", "evidence_not_visible", "already_open", "application_unknown", "control_covers_window",
    "no_progress", "opens_elsewhere", "changes_a_setting", "changes_the_tool", "scroll_part", "no_text_field",
    "types_the_place", "application_not_requested", "not_a_field", "search_box_not_target", "text_not_arriving",
    "key_without_effect", "repeated_step", "already_in_view", "file_not_written", "key_spent",
    "command_box", "creates_again", "creates_other", "system_menu", "cannot_open", "cannot_double", "runs_when_opened",
    # Ronda 21 (v3-24, v3-26): two controls of that name, and the node the window is already in.
    "label_ambiguous", "already_current",
    # Pasada r15b (v3-17): a press that changes the account and the goal does not ask for is one wrong control, never
    # the end of the mission: the model gets another try with the refusal in front of it.
    "changes_the_account",
    # Ronda 24 (pasada r23 v3-33): an option chosen cited as the product a goal makes; the retry names the control.
    "option_not_product",
    # Estabilización G2 (t2-c03): a text typed that the request did not ask for, while going somewhere.
    "types_unasked_text",
})


def _view_texts(view: dict) -> list[str]:
    """What the window writes: each control's name with its value and the texts that follow it in the tree (a row's
    cells, a switch's «Desactivado», a slider's «75»: revision 1 of ronda 23), and the lines read by zones."""

    texts: list[str] = []
    previous: object = None
    for control in view.get("controls") or () if isinstance(view, dict) else ():
        if not isinstance(control, dict):
            continue
        said = " ".join(str(control.get(key)) for key in ("name", "value") if control.get(key))
        index = control.get("i")
        follows = isinstance(index, int) and isinstance(previous, int) and index == previous + 1
        if texts and follows and control.get("kind") == "Text":
            texts[-1] = f"{texts[-1]} {said}".strip()
        elif said:
            texts.append(said)
        previous = index if said or follows else None
    zones = view.get("text") if isinstance(view, dict) else None
    for lines in zones.values() if isinstance(zones, dict) else ():
        texts += [str(line) for line in lines or () if line] if isinstance(lines, list) else []
    return texts


def _cites_the_answer(decision: dict[str, object], question: str, head: str, view: dict) -> dict[str, object]:
    """Ronda 23 (live r21 v3-62): a done of a goal that carries a question cites the datum that answers it. When the
    window writes something of the question's words («(activa)» for «which network is active») and the citation is none
    of it («El firewall está activado.»), the done is refused and the model retries with the refusal in front of it."""

    if decision.get("operation") != "done" or not question.strip():
        return decision
    arguments = decision.get("arguments") if isinstance(decision.get("arguments"), dict) else {}
    cited = str(arguments.get("evidence") or "")  # type: ignore[union-attr]
    window = view.get("window") if isinstance(view, dict) and isinstance(view.get("window"), dict) else {}
    if not citation_misses_question(cited, question, _view_texts(view), (head, str(window.get("title") or ""))):
        return decision
    return _none(f"«{cited[:60]}» no responde «{question.strip()[:80]}»; citá el dato de la vista que la responde",
                 code="evidence_not_visible")


# Ronda 20b, palanca 6: the refusals after which a collapsed list is opened before the mission gives up
# (``_unfold_before_giving_up``): the model's own «none» and the refusals the model had its retry for.
_UNFOLD_BEFORE_NONE = frozenset({"no_step_visible"}) | _RETRIED
