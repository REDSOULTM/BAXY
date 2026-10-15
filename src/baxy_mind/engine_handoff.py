"""Orders handed to the computer-use engine: a direct order the turn closed as a limit, a follow-up inside the
conversation's application, and when to ask which window first.
"""

from __future__ import annotations

from typing import Any, Callable

from . import turn_audit as turn_audit_module
from . import effect_intent, operation_floor
from .semantic import decider as semantic_decider
from .semantic import dialogue as dialogue_slot
from .semantic.apps import bare_close_pronoun, deictic_close_request
from .semantic import missions as semantic_missions
from .semantic import limits as semantic_limits
from .semantic.memory import explicit_memory_request
from .semantic.patterns import MISSION_SUBSUMES
from .effect_intent import (
    ApplicationCatalogIndex,
    EffectIntent,
    build_application_catalog_index,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)
from .planner import PlannerCatalog, conditional_predecessors, guarding_predecessors, required_predecessors
from .semantic.conversation import _deictic_open_request
from .turn_history import _baxy_replied, _prior_user_requests, _prior_user_texts, _read_reply_language
from .decided_arguments import _decided_arguments_of
from .operation_contract import _ACTS_WITHOUT_ASKING_RISKS


def _order_served_elsewhere(
    text: str,
    decided: semantic_decider.ContextDecision,
    available_operations: tuple[str, ...],
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
    risk_of: Callable[[str], str | None] | None = None,
    *,
    follow_up: Callable[[], str | None] | None = None,
    unfaithful: bool = False,
    made_there_before: Callable[[], bool] | None = None,
) -> tuple[str, str] | None:
    """v3 ronda 3 (lectura L1): the coverage check of an action the decider chose for an order said inside an installed
    application (``semantic.missions.place_application``). It returns why the typed operations do not serve that order
    (``semantic.decider.order_served_elsewhere``) and the person's words the engine takes as its goal, or None. A
    place the person said and misspelled (v3-04 «abre powerpint, …») is written as the application the decider's
    restatement names, only when the word said is within a typing slip of it (``semantic.missions.place_misspelled``);
    the restatement itself is never the goal (it paraphrases, and sometimes translates).

    Only an action the engine may try alone (``engine_can_try``: no question, no prohibition, nothing undone or paid)
    and never a search whose engine is the place named («buscá en google…»: the search is the request). An operation
    that only finds what another chosen one needs (web.search before browser.navigate.named, H0081; the capture a
    description reads) is no act of its own; one the typed readers read apart in the order («abre Discord y recordame
    …» → app.open + reminder.create) serves a request of its own.

    Corrección ronda 5 (seguridad): an operation that keeps its own route (``_keeps_its_route``: its catalog risk is
    confirmed, ``risk_of``, or the data lists it) is never taken from it.

    Ronda 21 (pasada r18, t-drag-1 «arrastrá lista.txt adentro de la carpeta archivo, en baxy-prueba-v3» kept the
    sandbox's filesystem.move and asked which file; v3-68 «en el programador de tareas esconde el panel…» kept a click
    on «Ocultar panel de acciones» in another application): ``unfaithful`` says the decider's restatement was replaced
    by the person's words (``semantic.decider.faithful_request``, kind «person»). The operations it chose on that
    restatement are checked again, never kept: an order the mission reader reads inside an application or a folder of
    the person's is that place said, and screen primitives whose verbs the person never said
    (``semantic.decider.primitives_unsaid``) are the unfaithful paraphrase, not the order."""

    if (
        decided.decision != "action"
        or not decided.operations
        or "mission.computer.use" in decided.operations
        or "mission.computer.use" not in available_operations
        or any(_keeps_its_route(operation, risk_of) for operation in decided.operations)
        or not semantic_missions.engine_can_try(text, application_names)
    ):
        return None
    said: str | None = text
    place = semantic_missions.place_application(text, application_names)
    corrected = semantic_missions.place_misspelled(text, decided.request or "", application_names)
    if place is None:
        # A follow-up that names no place keeps the decider's typed choice (D21: the conversation's application is the
        # restatement's, not the person's)...
        framed = follow_up() if corrected is None and follow_up is not None else None
        if framed is not None and not semantic_missions.engine_can_try(framed, application_names):
            framed = None
        if framed is not None and semantic_decider.leaves_the_said_value(decided.operations, text, decided.arguments):
            # ...unless (uso real v3 ronda 19, c04 T2 «ahi ponle la escala en 125» → one click on «pantalla») the
            # follow-up said in the conversation's application (``follow_up``) says a value no chosen piece carries.
            return "value_unserved", framed
        # Ronda 21 (pasada r18, v3-35 t2 «ponle: pagar la luz» after «crea una nota rapida nueva» → note.create in
        # BAXY's own store, told «He creado la nota» with nothing done in the application): a follow-up the
        # conversation's application frames, whose chosen operation makes in BAXY's store what applications make
        # (``semantic.decider.made_in_an_application``), is the order said there, and the same coverage check as a
        # place said decides it. Contracasos: «recordame mañana pagar la luz» keeps reminder.create; a key, a click or
        # a value read keep the rule above; an order that mentions another application («cerrá la pestaña de edge»)
        # is never framed in the conversation's. Revisión 1 (hallazgo 1: «abre discord» → «anotá: llamar a mamá»
        # framed the note in Discord, the engine would type it in the person's chat): only when the person's own
        # request in that application made the same thing there (``made_there_before``,
        # ``semantic.missions.made_there_before``: «crea una nota rapida nueva»); after one that only opened it or did
        # anything else, the note stays BAXY's.
        if framed is not None and not (
            semantic_decider.made_in_an_application(decided.operations)
            and not semantic_missions.mentions_an_application(text, application_names)
            and made_there_before is not None and made_there_before()
        ):
            framed = None
        said = framed if framed is not None else corrected
        if said is None and unfaithful and getattr(
            semantic_missions.mission_request(text, application_names), "application", None,
        ) is not None:
            said = text
        if said is None or not semantic_missions.engine_can_try(said, application_names):
            return None
    elif corrected is not None and semantic_missions.place_application(corrected, application_names) == place:
        # Integración ronda 3: the mission reader now takes a near spelling of the place itself («abre powerpint, …»,
        # lectura L2); the engine's goal still says the place as the application it is, the same as when only the
        # restatement named it.
        said = corrected
    if effect_intent._explicit_google_search_query(said):
        return None
    chosen = decided.operations
    feeders = {
        feeder
        for operation in chosen
        for feeder in (
            *required_predecessors(operation),
            *conditional_predecessors(operation, said),
            *guarding_predecessors(operation, said),
        )
        if feeder != operation
    }
    acting = tuple(operation for operation in chosen if operation not in feeders) or chosen
    if unfaithful and (
        semantic_decider.primitives_unsaid(acting, said) or semantic_decider.primitives_said_unchosen(acting, said)
    ):
        return "unfaithful_restatement", said
    read = resolve_explicit_effects(said, available_operations, application_names)
    # Ruta tipada en app (auditoría 2026-10-08): the clause said in place, without its place, as the typed readers read
    # it; what the application is only the place of keeps its route («en Configuración bajá el brillo al 30»). One pass
    # reads the place and the clause, and the clause is read only when an operation needs it (revisión 6: latency).
    in_place = semantic_missions.said_in_place(said, application_names)
    kept_in_place: frozenset[str] = frozenset()
    if in_place is not None:
        clause = in_place[1]

        def read_clause() -> tuple[str, ...]:
            clause_read = resolve_explicit_effects(clause, available_operations, application_names) if clause else None
            return clause_read.operations if clause_read is not None else ()

        kept_in_place = semantic_decider.kept_where_said(acting, in_place[0], read_clause, clause)
    reason = semantic_decider.order_served_elsewhere(
        acting,
        semantic_missions.doing_clauses(said, application_names),
        doing_in_place=in_place is not None,
        kept_in_place=kept_in_place,
        read_apart=read.operations if read is not None else (),
        # v3-27 r9: an operation whose object the order never names is no request of its own beside the application.
        unasked=semantic_decider.unasked_operations(acting, said),
        # Erratas r9 (revisión 3): what only a clause headed by a place inside the application reads.
        read_in_place=(
            semantic_missions.read_only_in_a_place(said, application_names, available_operations)
            if read is not None and set(read.operations) == {"mission.computer.use"} else ()
        ),
    )
    return (reason, said) if reason is not None else None


# The decider's restatement of a request it closed as a limit, carried to the coverage gate inside the turn result
# and taken off it there (the shell's turn.result never carries it).
_DECIDER_RESTATEMENT = "_deciderRestatement"


def _engine_for_an_unserved_order(
    turn_result: dict[str, Any],
    message: dict[str, Any],
    tool_by_name: dict[str, dict],
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
) -> dict[str, Any]:
    """Owner 2026-10-07: a direct order about the PC that the turn closed as a limit is handed to the computer-use
    engine (the person's words are its goal; semantic.missions.engine_can_try), the way a person would try it on
    the screen. Every step it takes is still policed: what reaches a person or destroys is confirmed.

    v3 ronda 5 (lectura M1–M3, diseño 3–4; falsos éxitos M1): the one coverage gate every route's decision passes
    (the typed readers', the decider's, a question for a missing value, the recovery's), with the person's words:
    - a question about an application, the one framing it or the one the conversation is in, that the turn could only
      ask about or close as a limit is a look at it («en <app>, decime <pregunta>»: v3-61, v3-22 t3);
    - typed operations chosen for an order said inside an installed application that act elsewhere or do only a piece
      of it (``_order_served_elsewhere``: v3-24 «en el visor de eventos filtra…» → web.search, v3-53 «en obs silencia
      el audio del escritorio» → audio.mute) are not the order;
    - a question for a value the order did not say, or the recovery's question, about an order said inside an
      installed application is no question the engine needs (t-drag-4, v3-35), unless the application's own service
      asks its own value (``semantic.decider.asks_for_the_application_itself``: «en Spotify subí el volumen» →
      ¿cuánto?)."""

    restated = turn_result.pop(_DECIDER_RESTATEMENT, None)
    if "mission.computer.use" not in tool_by_name:
        return turn_result
    effects = tuple(turn_result.get("effectOperations") or ())
    intents = tuple(turn_result.get("intentOperations") or ())
    if "mission.computer.use" in effects or "mission.computer.use" in intents:
        return turn_result

    def risk_of(operation: str) -> str | None:
        return ((tool_by_name.get(operation) or {}).get("function") or {}).get("risk")

    if any(_keeps_its_route(operation, risk_of) for operation in (*effects, *intents)):
        # Corrección ronda 5 (seguridad): what confirms or refuses on its own route (the PC's power, a command run,
        # an uninstall) is never handed to the engine, whatever route chose it.
        return turn_result
    said = str(message.get("text") or "")
    history = message.get("history") or []
    kind = turn_result.get("kind")
    limited = kind == "conversation" and turn_result.get("conversationKind") == "unsupported" and not effects
    if (kind == "clarify" or limited) and semantic_missions.level_amount_unsaid(said, application_names):
        # Corrección ronda 5 (owner rule: a relative volume or brightness change without a quantity asks how much,
        # never a default step): whatever operation the turn chose, or none, and in an order of several clauses.
        return turn_result
    typed = tuple(operation for operation in intents if operation not in MISSION_SUBSUMES)
    if (kind == "clarify" and not typed) or limited:
        conversation = None
        if semantic_missions.place_application(said, application_names) is None:
            # The one reader of the conversation's application (v3 destino), shared with the mission's destination.
            found = semantic_missions.conversation_application(
                _prior_user_texts(history, said), application_names, tuple(tool_by_name),
            )
            conversation = found[0] if found is not None else None
        asked = semantic_missions.application_question(
            said, application_names, conversation, english=_read_reply_language(said, history) == "en",
        )
        if asked is not None and not _question_read_by_a_typed_operation(asked, tool_by_name, application_names):
            # Corrección ronda 5: a question the turn asked about a typed operation for («¿de qué ciudad?» for the
            # weather) stays its question; one a typed reader reads alone («¿qué hora es?», «en Chrome decime el clima
            # de mañana») is no look at the application: its answer is not on that screen, and the typed one is
            # verified.
            return _handed_to_the_engine(turn_result, message, asked, "application_question")
    if limited:
        text = str(turn_result.get("objective") or said)
        if restated:
            # Uso real v3 t2 (c04 «ahi ponle la escala en 125»): the decider's restatement that frames the
            # conversation's application is the engine's goal; the bare words left the engine on the person's window.
            text = semantic_missions.restatement_for_the_engine(
                str(restated), said, _prior_user_texts(history, said), application_names,
            ) or text
        elif " ".join(text.split()) == " ".join(said.split()):
            # Uso real v3 ronda 19 (c04 T4 «te dije la escala no el brillo, regresa la escala a 100», a limit with no
            # restatement or the recovery's): the follow-up framed in the conversation's application, without what
            # only corrects the last turn.
            text = _follow_up_for_the_engine(said, history, application_names) or text
        if semantic_missions.engine_can_try(text, application_names) and not _question_read_by_a_typed_operation(
            text, tool_by_name, application_names,
        ):
            return _handed_to_the_engine(turn_result, message, text, "engine_for_unserved_order")
        return turn_result
    if (
        kind in {"action", "plan"} and "filesystem.write.text" in effects
        and not _baxy_replied(history) and semantic_missions.saves_what_is_shown(said)
    ):
        # Lectura-ruta (r9 t-file-1): saving what the window shows («guardá esto como N en C») is the window's own Save
        # As, never a new file written with the request as its text. After a reply of BAXY's, «esto» is that reply
        # (M67's typed write keeps it; review of the branch, finding 1).
        return _handed_to_the_engine(turn_result, message, said, "saves_what_is_shown")
    if (
        kind in {"action", "plan"}
        and set(effects) <= MISSION_SUBSUMES
        and semantic_decider.primitives_unsaid(effects, said)
        and dialogue_slot.dependency(said, dialogue_slot.read_slot(message, history, said)) is None
        and semantic_missions.engine_can_try(said, application_names)
        # Revisión 1 (hallazgo 1): the engine acts only where it has a place (an application, or the window in front
        # the person names); «guardalo», «pon hola», «aceptá» alone keep their typed route on the focused control.
        # Revisión 3 (hallazgo 2): and only a place the message itself gives, never the conversation's application
        # («recargá la página de chrome», «cerrá esta pestaña» after a turn in the Bloc de notas keep their route).
        and semantic_missions.engine_destination_said(
            said, application_names, _prior_user_requests(history),
        )
    ):
        # Ronda 20 P3 (pasada r18, v3-11 t1 «en onenote crea una pagina nueva» → one click on «Página» that nothing on
        # the screen was called): primitives of the screen whose verbs the person never said («clic», «escribí»,
        # ``semantic.decider.primitives_unsaid``) are the decider's paraphrase of the order; the engine takes the
        # person's words and reads the screen. A message that leans on the turn before keeps its route (its words
        # alone are no goal), as does an order that says the click or the typing itself.
        return _handed_to_the_engine(turn_result, message, said, "subsumed_by_mission")
    if kind in {"action", "plan"} and effects:
        objective = str(turn_result.get("objective") or said)
        served = _order_served_elsewhere(
            said,
            # Revisión adversarial 3 r19: with the values the decider gave the turn's pieces (a click on «125 %»
            # carries the scale said), never a bare decision that reads every piece as leaving the value.
            semantic_decider.ContextDecision(objective, "action", effects, "", _decided_arguments_of(objective, effects)),
            tuple(tool_by_name),
            application_names,
            risk_of,
            follow_up=lambda: _follow_up_for_the_engine(said, history, application_names),
        )
        if served is not None:
            return _handed_to_the_engine(turn_result, message, served[1], f"served_elsewhere:{served[0]}")
        return turn_result
    if kind != "clarify" or semantic_decider.asks_for_the_application_itself(
        intents, semantic_missions.doing_clauses(said, application_names),
    ):
        return turn_result
    if semantic_missions.ordered_in_application(said, application_names) is not None:
        return _handed_to_the_engine(turn_result, message, said, "clarify_in_application")
    if (
        not typed
        and semantic_missions.place_application(said, application_names) is None
        # Revisión 2 (hallazgo 1): an application the person names without the «en <app>» frame («subí el zoom del
        # bloc de notas a 150») is the order's, never the conversation's: framing it in another one would act in an
        # application the request does not name (``application_question``'s convention). The question stands.
        # Revisión 3 (hallazgo 1): any application it mentions — a short name («de chrome»), a kind («del
        # navegador»), one not installed («del word») — not only one ``said_application`` reads.
        and not semantic_missions.mentions_an_application(said, application_names)
        and not semantic_missions.change_amount_unsaid(said)
        and semantic_missions.engine_can_try(said, application_names)
        # Revisión 1 (hallazgo 2): a message that leans on the turn before («hacelo de nuevo», «y lo otro», an answer
        # still asked about) is no order of its own, and only an order that says the value it sets overrides the
        # question («ok», «asdf qwer» are no order; «cambiale el nombre» → «¿Qué nombre le pongo?» keeps asking).
        and dialogue_slot.dependency(said, dialogue_slot.read_slot(message, history, said)) is None
        and semantic_missions.order_saying_its_value(said)
    ):
        # Ronda 20 P3 (pasada r18, v3-11 t3 «ahora subele el zoom a 150» → «¿Cuánto le subo al zoom?»): an order the
        # turn could only ask about, said without its application inside a conversation that is in one
        # (``conversation_application``, the limited branch's reader), is that application's order. A level without
        # its amount was already asked above (owner rule); a conversation another message left keeps the question.
        found = semantic_missions.conversation_application(
            _prior_user_texts(history, said), application_names, tuple(tool_by_name),
        )
        if found is not None:
            text = semantic_missions.framed_in_application(found[0], said)
            if restated:
                text = semantic_missions.restatement_for_the_engine(
                    str(restated), said, _prior_user_texts(history, said), application_names,
                ) or text
            if not _question_read_by_a_typed_operation(text, tool_by_name, application_names):
                return _handed_to_the_engine(turn_result, message, text, "clarify_in_conversation_application")
    return turn_result


def _mission_goal_of_the_restatement(
    text: str,
    decided: semantic_decider.ContextDecision,
    history: list[dict[str, Any]],
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
) -> str:
    """The goal of a mission the decider restated as screen primitives (the Live v2-s13 and v3-43 branches).

    An order that says its own place is the person's words (integración ronda 3, v3-38). Ronda 21 «palabras de la
    persona con su conversación» (pasada r18, v3-23 «ahora anda a registros de windows, sistema» → «haz clic en
    «Registros de Windows» y luego en «Sistema»» closed by a click's receipt; v3-65 «cambiala a la vista estandar» →
    a click on «Vista estándar», a control the window does not have): when the primitives chosen are verbs the person
    never said (``semantic.decider.primitives_unsaid``), the goal is the person's words framed in the conversation's
    application (``_follow_up_for_the_engine``), with the checks their own words read. Only when no application frames
    them is the restatement the goal, and then a quotation of its own the person never said is no literal label
    (``semantic.decider.without_unsaid_quotes``). Contracaso: «ahora hacé clic en Sistema» says the click, and the
    restatement stays with its receipt check."""

    if semantic_missions.place_application(text, application_names) is not None:
        return text
    if not semantic_decider.primitives_unsaid(decided.operations, text):
        return decided.request
    framed = _follow_up_for_the_engine(text, history, application_names)
    if framed is None:
        # v2-s13 «y ahora andá a configuración» after a mission in Discord: a name only mentioned is a place inside
        # the application the decider itself kept from the conversation.
        framed = semantic_missions.follow_up_for_the_engine(
            text, _prior_user_texts(history, text), application_names,
            english=_read_reply_language(text, history) == "en", mention_is_a_place=True,
        )
        kept = getattr(semantic_missions.mission_request(decided.request, application_names), "application", None)
        if framed is not None and getattr(
            semantic_missions.mission_request(framed, application_names), "application", None,
        ) != kept:
            framed = None
    if framed is not None:
        return framed
    return semantic_decider.without_unsaid_quotes(decided.request, text)


def _names_an_application(
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
) -> Callable[[str], bool]:
    """Ronda 23: whether a name a request said is an installed application (``semantic.missions.said_application``):
    a restatement frames the application itself, so only the other objects of a turn before must be kept."""

    catalog = (
        application_names if isinstance(application_names, ApplicationCatalogIndex)
        else build_application_catalog_index(application_names)
    )
    return lambda name: semantic_missions.said_application(name, catalog) is not None


def _follow_up_for_the_engine(
    said: str, history: list[dict[str, Any]], application_names: tuple[str, ...] | ApplicationCatalogIndex,
) -> str | None:
    """A follow-up said without its application as the engine's goal in the conversation's application
    (``semantic.missions.follow_up_for_the_engine``), in the person's language."""

    return semantic_missions.follow_up_for_the_engine(
        said, _prior_user_texts(history, said), application_names,
        english=_read_reply_language(said, history) == "en",
    )


# Ronda 20 P3, revisión 2 (hallazgo 2): the operations that act in the place a person points to on the screen — the
# screen's own primitives the mission subsumes (a click, typing, a key) and the mission itself. Opening, closing,
# focusing, a level, a search or a read act on no place an «ahí» could point to.
_ACTS_IN_THE_PLACE_POINTED_TO = frozenset(
    {"input.key.press", "input.text.type", "input.visible.click", "mission.computer.use"}
) & (MISSION_SUBSUMES | {"mission.computer.use"})


# Estabilización L (review of L, H1): the operations a «guarda esto» may have been sent to when no typed route serves
# it: the engine, the screen's primitives, and the typed write the decider takes for a save of what is shown.
_WINDOW_SAVE_ROUTES = MISSION_SUBSUMES | {"mission.computer.use", "filesystem.write.text"}


def _asks_which_window(
    turn_result: dict[str, Any],
    message: dict[str, Any],
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
) -> dict[str, Any]:
    """Estabilización L (límite de partida): «guarda esto» with no application said nor in the conversation and no
    window pointed at is asked about (data «computerUse.limits.whichWindow»): BAXY never acts on the person's window
    nor guesses another one. Review of L, H1: only when no typed route serves it — the turn chose the engine, the
    screen's primitives or the write of what is shown, never a memory, the clipboard, the contacts or a note — and never
    after a reply of BAXY's («esto» is that reply, M67). H8d: the answer to that question that names the window
    («en el Bloc de notas», «en esta ventana») is the request asked about, framed there."""

    said = str(message.get("text") or "")
    history = message.get("history") or []
    turns = [item for item in history if isinstance(item, dict)]
    if turns and turns[-1].get("role") == "user":
        turns = turns[:-1]
    if (
        len(turns) >= 2 and turns[-1].get("role") == "assistant"
        and semantic_limits.asked_which_window(turns[-1].get("content"))
        and turns[-2].get("role") == "user"
    ):
        asked = str(turns[-2].get("content") or "")
        framed = semantic_limits.which_window_answer(
            said, asked, application_names,
            english=semantic_limits.asked_which_window_in_english(turns[-1].get("content")),
        )
        return turn_result if framed is None else _handed_to_the_engine(turn_result, message, framed, "which_window_answer")
    effects = set(str(op) for op in turn_result.get("effectOperations") or ())
    if (
        _baxy_replied(history)
        or not effects <= _WINDOW_SAVE_ROUTES
        or ("filesystem.write.text" in effects and not semantic_missions.saves_what_is_shown(said))
        or explicit_memory_request(said)
        or not semantic_limits.asks_which_window(said, application_names, _prior_user_requests(history))
    ):
        return turn_result
    operations = list(dict.fromkeys(str(op) for op in turn_result.get("effectOperations") or ()))
    turn_audit_module._append_turn_audit(
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": message.get("id"),
            "phase": "final",
            "decision_path": "which_window",
            "raw_decision": {"mode": "clarify", "request": said, "effect_operations": []},
            "stages": [{"name": "which_window", "kind": turn_result.get("kind"), "operations": operations}],
            "final": {"kind": "clarify", "intent_operations": operations, "effect_operations": []},
        }
    )
    return {
        "type": "turn.result",
        "id": message.get("id"),
        "kind": "clarify",
        "operation": None,
        "intentOperations": operations,
        "effectOperations": [],
        "question": semantic_limits.which_window_question(_read_reply_language(said, history) == "en"),
        "reply": "",
        "turn_recovery": "which_window",
    }


def _asks_when_the_antecedent_failed(
    turn_result: dict[str, Any],
    message: dict[str, Any],
    dialogue_state: Any,
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
) -> dict[str, Any]:
    """Ronda 20 P3 (pasada r18, v3-11 t2 «escribe ahí: comprar pan, leche y huevos» after «en onenote crea una pagina
    nueva» was told as failed: the text went into the title of a page that already existed). An act whose place the
    person only points back to («ahí», «en ella») and whose request before was told as failed
    (``semantic.dialogue.DialogueState.antecedent_failed``) asks, never acts: the place it points to was never made.
    The question is the floor's data (``computerUse.antecedentFailed``), with both requests quoted and the window the
    failed result itself observed, when it did. An «ahí» whose place the same message says («abrí el bloc de notas y
    escribí ahí hola»: ``semantic.missions.place_said_for_its_pointer``) points to no turn before and acts (revisión
    1, hallazgo 3). Only an act done in the place pointed to asks (revisión 2, hallazgo 2:
    ``_ACTS_IN_THE_PLACE_POINTED_TO``): «pon el volumen ahí al 30», «bueno, ahí probá abrir chrome» act nowhere on the
    screen and keep their route. Any other turn passes unchanged."""

    if turn_result.get("kind") not in {"action", "plan"} or not (
        set(str(op) for op in turn_result.get("effectOperations") or ()) & _ACTS_IN_THE_PLACE_POINTED_TO
    ):
        return turn_result
    said = str(message.get("text") or "")
    history = message.get("history") or []
    if semantic_missions.place_said_for_its_pointer(said, application_names):
        return turn_result
    before = dialogue_state.antecedent_failed(said, dialogue_slot.read_slot(message, history, said))
    if before is None:
        return turn_result
    floor = operation_floor.floor_data()
    english = _read_reply_language(said, history) == "en"
    quote = floor["templates"]["en" if english else "es"]["quote"]
    asked = floor["computerUse"]["antecedentFailed"]
    window = dialogue_state.last_window()
    template = asked[("en" if english else "es") + ("" if window else "Bare")]

    def _in_quotes(value: str) -> str:
        # The shell takes one question: one line, one question mark, at most 512 characters.
        words = " ".join(value.replace("?", " ").replace("¿", " ").split()).strip(" .!")
        return quote.format(value=words[:150])

    question = template.format(
        before=_in_quotes(before), said=_in_quotes(said), window=_in_quotes(window) if window else "",
    )
    operations = list(dict.fromkeys(str(op) for op in turn_result.get("effectOperations") or ()))
    turn_audit_module._append_turn_audit(
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": message.get("id"),
            "phase": "final",
            "decision_path": "antecedent_failed",
            "raw_decision": {"mode": "clarify", "request": said, "effect_operations": []},
            "stages": [{"name": "antecedent_failed", "kind": turn_result.get("kind"), "operations": operations}],
            "final": {"kind": "clarify", "intent_operations": operations, "effect_operations": []},
        }
    )
    return {
        "type": "turn.result",
        "id": message.get("id"),
        "kind": "clarify",
        "operation": None,
        "intentOperations": operations,
        "effectOperations": [],
        "question": question,
        "reply": "",
        "turn_recovery": "antecedent_failed",
    }


# Corrección ronda 5 (seguridad): the catalog risks whose operations confirm before they act (or never act); an
# operation with one keeps its own route and is never handed to the engine by the coverage gate. A click's
# «external_communication» is not one: the engine itself confirms what reaches a person (RiskPolicy).
_KEEPS_ITS_ROUTE_RISKS = frozenset(
    {"forbidden_destructive", "installation", "monetary", "recoverable_delete", "session_disruption", "work_loss"}
)


def _keeps_its_route(operation: str, risk_of: Callable[[str], str | None] | None) -> bool:
    if semantic_decider.keeps_its_route(operation):
        return True
    return risk_of is not None and risk_of(operation) in _KEEPS_ITS_ROUTE_RISKS


# Ronda 24: the catalog risks of an order done instead of said back as a yes/no question. Reading, reversible acts and
# a close (work_loss: the kernel lowers a window that holds no document of the person and otherwise asks, bound to the
# invocation, ``AppCloseHandler``). What reaches a person, deletes, installs or pays keeps its question.
_SAID_BACK_ORDER_RISKS = _ACTS_WITHOUT_ASKING_RISKS | {"work_loss"}


def _operations_the_question_only_says_back(
    question: str,
    text: str,
    planner_catalog: PlannerCatalog,
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
    *,
    decided: tuple[str, ...] = (),
) -> tuple[str, ...] | None:
    """Ronda 24 (r23 t2-c03#2, t4-c03 t4): the operations of a complete order the decider's question only says back
    (``semantic.dialogue.order_said_back``), or None.

    The words said back must read, alone, as an order the explicit readers prove in the person's words: the decider
    asks precisely when it doubts, so its operations never turn its own doubt into an act (revisión 1: «should I close
    discord?», «¿y si cierro discord?», «ya cierra discord, bueno no, mejor no» are no order and keep the question).
    Revisión 2: the decider's operations are the ones done when it brings them, only when they are the ones those
    words read (from the readers otherwise); every operation the readers read in the whole request must be one the
    question says back («cierra discord y spotify» → «¿Quieres que cierre Discord?» keeps its question); when the
    readers cannot read the whole request, what follows the words said back must only tell why
    (``semantic.dialogue.only_gives_a_reason``: «… que me está laggeando el valorant»), and nothing that follows them
    may take the order back (revisión 3, ``semantic.dialogue.takes_the_order_back``). The readers must also see the
    order whole: a request they read as missing a value the catalog's schema requires («aumenta el volumen»: the
    amount, owner rule H0027) keeps its question. Each operation is in the catalog, is not kept on its own route
    (``semantic.decider.keeps_its_route``: system.power, shell commands…) and has a risk the kernel acts on or confirms
    per invocation (``_SAID_BACK_ORDER_RISKS``). «mándale a Ron92 que…» and «borra la carpeta X» keep their question.

    Estabilización T: a decider that asks nothing (``question`` empty: it gave no valid question of its own) says
    nothing back but doubts nothing either; the order is then the person's own words up to the clause that only tells
    why (``semantic.dialogue.order_before_its_reason``), one order and never a pointer (M19/M118: «ciérralo», «cierra
    eso» are asked), under every check above."""

    if question:
        said_back = dialogue_slot.order_said_back(question, text)
    else:
        folded = effect_intent._fold(text)
        if bare_close_pronoun(folded)[0] or deictic_close_request(folded) or _deictic_open_request(text):
            return None
        order = dialogue_slot.order_before_its_reason(text) or text
        if dialogue_slot.takes_the_order_back(order):
            return None
        said_back = dialogue_slot.OrderSaidBack(order, text[len(order):])
    if said_back is None:
        return None
    risks = {tool.name: tool.risk for tool in planner_catalog.tools}
    # The person's words read alone (r23 t4-c03 t4: the decider still weighed a send confirmation pending from the turn
    # before).
    said = resolve_explicit_effects(said_back.said, tuple(risks), application_names)
    said_operations = tuple(said.operations) if said is not None and said.operations else ()
    if not said_operations or "mission.computer.use" in said_operations or (not question and len(said_operations) > 1):
        return None
    # Revisión 3: whatever the readers read, an order taken back after the words said back is no order («cierra
    # discord que me lo pidió mi mamá pero no lo cierres todavía», «close discord because it lags but not yet»).
    if dialogue_slot.takes_the_order_back(said_back.rest):
        return None
    whole = resolve_explicit_effects(text, tuple(risks), application_names)
    if whole is not None and whole.operations:
        if tuple(whole.operations) != said_operations or len(whole.evidence) != len(said.evidence):
            return None
    elif not dialogue_slot.only_gives_a_reason(said_back.rest):
        return None
    if decided and tuple(decided) != said_operations:
        return None
    operations = tuple(decided) or said_operations
    if any(
        resolve_explicit_clarification_intent(words, tuple(risks), application_names) is not None
        for words in (text, said_back.said)
    ):
        return None
    if any(
        risks.get(operation) not in _SAID_BACK_ORDER_RISKS or semantic_decider.keeps_its_route(operation)
        for operation in operations
    ):
        return None
    return operations


def _question_read_by_a_typed_operation(
    asked: str,
    tool_by_name: dict[str, dict],
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
) -> bool:
    """The question of a look at an application (``semantic.missions.application_question``) as a typed reader reads
    it alone, without the mission («decime qué hora es» → system.time)."""

    mission = semantic_missions.mission_request(asked, application_names)
    question = str(getattr(mission, "goal", "")).partition(semantic_missions.QUESTION_MARK)[2]
    if not question:
        return False
    operations = tuple(operation for operation in tool_by_name if operation != "mission.computer.use")
    read = resolve_explicit_effects(question, operations, application_names)
    return read is not None and bool(set(read.operations) - MISSION_SUBSUMES)


def _handed_to_the_engine(
    turn_result: dict[str, Any], message: dict[str, Any], text: str, path: str,
) -> dict[str, Any]:
    """The turn as the computer-use engine's, with ``text`` (the person's words) as its goal (``_engine_for_an_unserved_order``)."""

    tried = {
        "type": "turn.result",
        "id": message.get("id"),
        "kind": "plan",
        "operation": None,
        "intentOperations": ["mission.computer.use"],
        "effectOperations": ["mission.computer.use"],
        "question": "",
        "reply": "",
        "objective": text,
    }
    if turn_result.get("responseLanguage"):
        tried["responseLanguage"] = turn_result["responseLanguage"]
    turn_audit_module._append_turn_audit(
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": message.get("id"),
            "phase": "final",
            "decision_path": "engine_for_unserved_order",
            "raw_decision": {"mode": "action", "request": text, "effect_operations": ["mission.computer.use"]},
            "stages": [{
                "name": path,
                "kind": turn_result.get("kind"),
                "operations": list(turn_result.get("effectOperations") or turn_result.get("intentOperations") or ()),
            }],
            "final": {"kind": "plan", "intent_operations": ["mission.computer.use"],
                      "effect_operations": ["mission.computer.use"]},
        }
    )
    return tried


def _self_contained_mission(
    objective: str,
    explicit_intent: EffectIntent | None,
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
) -> bool:
    """The message names an installed application and reads alone as a step inside it: in a conversation its own
    reading is the turn, not the contextual decider's (a follow-up without the application still goes to the decider,
    Fase 3.5b F4)."""

    if explicit_intent is None:
        return False
    google_query = (
        effect_intent._explicit_google_search_query(objective)
        if explicit_intent.operations == ("browser.navigate",)
        else None
    )
    if google_query and not dialogue_slot.query_points_back(google_query):
        # Uso real 2026-10-07 «Podrias buscarme en google un top 3…» after earlier turns: a search with its own words
        # and the engine named as the place stands alone; the decider sent it to web.search and lost the place.
        # «busca en google eso», «lo que te dije» point back: the decider reads them with the conversation.
        return True
    return (
        explicit_intent.operations == ("mission.computer.use",)
        and getattr(semantic_missions.mission_request(objective, application_names), "application", None) is not None
    )


def _the_place_gone_to_again(
    objective: str,
    history: list[Any],
    available_operations: tuple[str, ...],
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
) -> str | None:
    """Ronda 21 (v3-58): a message that names an application which is the place the request before went to inside
    the conversation's application, read again as the one-turn order there
    (``semantic.missions.follow_up_in_application`` → ``_in_the_place_gone_to``); None for any other message."""

    return semantic_missions.follow_up_in_application(
        objective, _prior_user_texts(history, objective), available_operations, application_names,
        english=_read_reply_language(objective, history) == "en",
    )
