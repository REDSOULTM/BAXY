"""The turn as the contextual decider reads it, with the whole conversation, and the checks on what it decided.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Callable

from . import turn_audit as turn_audit_module
from . import effect_intent
from .semantic import decider as semantic_decider
from .semantic import dialogue as dialogue_slot
from .semantic import knowledge as semantic_knowledge
from .semantic.apps import bare_close_pronoun, close_request_for_opened, deictic_close_request, names_the_active_window
from .semantic.notes import (
    asks_overdue_notifications,
    entries_on_a_list,
    list_creation_said,
    names_own_event,
    question_with_context,
    question_with_its_reason,
)
from .semantic import levels as semantic_levels
from .semantic import missions as semantic_missions
from .semantic import messaging as semantic_messaging
from .semantic import memory as semantic_memory
from .semantic.memory import explicit_memory_request
from .semantic import temporal as semantic_temporal
from .semantic import ui as semantic_ui
from .semantic.patterns import MISSION_SUBSUMES, application_shown_media_name, list_entries_said_before, mission_reads
from .semantic.web import (
    asks_latest_release,
    asks_to_watch_the_news,
    asks_what_a_cinema_shows,
    currency_conversion_request,
    names_own_data,
    searches_places_somewhere,
)
from .semantic.media import asks_what_sounds
from .semantic.files import NamedFileMeant, named_file_meant, named_file_operation, named_file_request, only_file_named
from .effect_intent import (
    ApplicationCatalogIndex,
    EffectIntent,
    conversation_only_content_request,
    operation_domain_is_grounded,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)
from .planner import PlannerCatalog, PlannerContractError, required_predecessors
from .semantic.dialogue import _history_has_pending_clarification, _previous_user_request
from .semantic.conversation import _deictic_open_request, asks_for_code
from .semantic.arguments import conversation_file_folder, watch_named_title
from .semantic.messaging import latest_mail_reply_without_words
from .sidecar_budgets import DEICTIC_CLARIFICATION_CPU_BUDGET_SECONDS, TURN_DECIDE_RECOVERY_BUDGET_SECONDS
from .turn_history import _decisive_request_language, _previous_reply, _prior_user_texts, _read_reply_language
from .argument_grounding import _OUTPUT_LEVEL_OPERATIONS, _reference_lookup
from .decided_arguments import _remember_decided_arguments, _REMINDER_OPERATIONS, _schema_field_of
from .turn_recovery import _recovery_question_is_valid
from .turn_decisions import _conversation_reply_arguments
from .engine_handoff import (
    _DECIDER_RESTATEMENT,
    _follow_up_for_the_engine,
    _mission_goal_of_the_restatement,
    _names_an_application,
    _operations_the_question_only_says_back,
    _order_served_elsewhere,
)


def _asks_application_volume(
    text: str,
    available_operations: tuple[str, ...],
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
) -> bool:
    """M167: the request raises or lowers one application's own volume («súbele a spotify»), read or asked."""

    try:
        found = (
            resolve_explicit_clarification_intent(text, available_operations, application_names),
            resolve_explicit_effects(text, available_operations, application_names),
        )
    except (ValueError, TypeError):
        return False
    return any(read is not None and "audio.app.volume.adjust" in read.operations for read in found)


# M84: the operations a moment counted from BAXY's last answer is set with (``semantic.temporal.anchored_offset_request``).
_ANCHORED_SCHEDULE_OPERATIONS = frozenset({"notification.schedule", "reminder.create", "calendar.event.create"})
# M89: the reads of what is installed on this PC (never the newest published release).
_INSTALLED_SOFTWARE_READS = frozenset({"software.python.status", "software.python.package.status", "app.installed"})
# M103: the reads a decider chooses for «¿qué estoy viendo en <reproductor>?» (the media session, a window state).
_SHOWN_MEDIA_READS = frozenset({"media.status", "window.application.status", "window.active", "window.resolve"})


def _clock_read_request(text: str, history: object) -> str | None:
    """The request as a read of this PC's clock, when the readers prove one (M85): the time of another place (with
    «allá» said as the place of the person's last clock question) or this clock some minutes or hours later."""

    folded = effect_intent._fold(text)
    if semantic_temporal.clock_elsewhere(folded) is not None or semantic_temporal.clock_later_asked(text) is not None:
        return text
    prior = [
        str(turn.get("content") or "")
        for turn in (history if isinstance(history, list) else [])
        if isinstance(turn, dict) and turn.get("role") == "user" and str(turn.get("content") or "").strip() != text.strip()
    ]
    return semantic_temporal.clock_there_request(text, prior)


# Ronda 22: the key a turn's message carries, inside the mind only, for what the failed last request tried when the
# correction names the provider it already tried (``DialogueState.attempted_again``).
_ATTEMPTED_AGAIN = "_attemptedAgain"


def _contrastive_redecision(
    text: str,
    history: object,
    decided: semantic_decider.ContextDecision,
    available_operations: tuple[str, ...],
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
    attempted: object = None,
) -> semantic_decider.ContextDecision | None:
    """Uso real v3 tanda 4 c01-4 «no po, en spotify te dije, no en youtube» → restated «Pon una cumbia en YouTube.» and
    played there; c04-2 «joder que te he dicho brillo no volumen» right after the brightness was set → talk about the
    sound output. A contrastive correction (``semantic.dialogue.contrastive_correction``) is about the last request: Y
    in it becomes X, and a request that already named X is done again as it was (the readers' final then says the state
    it found, «ya estaba al 40»). It replaces the decider's choice when that choice names what the person refused, or
    when it is no action; the corrected request must read an effect by itself and must not name the refused thing.

    Ronda 22 (pasada r18 t4-c01: the try in Spotify had failed and the correction rebuilt «y ponme cumbia mientras»
    into the query «cumbia mientras»): ``attempted`` is what the last request tried when the correction names the
    provider it already tried (``DialogueState.attempted_again``: request, operation, arguments); that request and
    those arguments are tried again, whatever the decider chose."""

    contrast = dialogue_slot.contrastive_correction(text)
    if contrast is None:
        return None
    if isinstance(attempted, tuple) and len(attempted) == 3 and attempted[1] in available_operations:
        tried_request, tried_operation, tried_arguments = attempted
        corrected = dialogue_slot.corrected_request(str(tried_request), text)
        try:
            read = resolve_explicit_effects(corrected, available_operations, application_names) if corrected else None
        except (TypeError, ValueError):
            read = None
        if read is not None and tuple(read.operations) == (tried_operation,):
            return semantic_decider.ContextDecision(
                corrected, "action", (tried_operation,), "", tuple(tried_arguments),
            )
    last = _previous_user_request(history if isinstance(history, list) else [], text)
    corrected = dialogue_slot.corrected_request(last, text) if last else None

    def names_refused(*said: str) -> bool:
        words = effect_intent._fold(" ".join(said)).replace(".", " ")
        # Review 2026-10-08 r2: «Abre Chrome, no Firefox.» repeats the refusal; only a mention not denied names it.
        words = re.sub(rf"\b(?:no|not)\s+(?:\w+\s+){{0,2}}?{re.escape(contrast.refused)}\b", " ", words)
        return re.search(rf"\b{re.escape(contrast.refused)}\b", words) is not None

    chose_refused = decided.decision == "action" and names_refused(
        decided.request or "", *decided.operations,
        *(value for _, value in decided.arguments if isinstance(value, str)),
    )
    if corrected is None:
        # Review 2026-10-08 r2: the order after the contrast that no reader can join to it («… y sube el volumen» with
        # no last request to correct, «subelo» after a place) is the decider's, but the refused thing is never done.
        return semantic_decider.ContextDecision(text, "clarify", (), "") if chose_refused else None
    try:
        read = resolve_explicit_effects(corrected, available_operations, application_names)
    except (TypeError, ValueError):
        read = None
    if read is None or not read.operations:
        # Audit 2026-10-08 t1-c02-2 «no, el brillo te dije, no el volumen. bajalo mas»: the corrected request still
        # misses its amount («baja el brillo mas»). The refused thing is never done; what is missing is asked.
        if chose_refused and not names_refused(corrected):
            return semantic_decider.ContextDecision(corrected, "clarify", (), "")
        return None
    if names_refused(corrected, *read.operations):
        return None
    if decided.decision == "action" and not chose_refused:
        return None
    return semantic_decider.ContextDecision(corrected, "action", tuple(read.operations), "")


def _decider_left_the_step(
    decided: semantic_decider.ContextDecision,
    in_application: str,
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
    text: str = "",
) -> bool:
    """Live v2-x12: the decider closed «ahora ponela en modo científica» (after «abrí la calculadora») as a limit, and
    the engine ran the bare words in no window. A step inside the conversation's application
    (``semantic.missions.follow_up_in_application``) is that mission unless the decider chose a typed operation (D21)
    or already restated it as a mission in that same application (its words stand, v2-s13). A question, a talk answer
    or a limit that asks something is the decider's to give (review r10): only an action or a bare limit is replaced."""

    if decided.decision == "limit":
        return not decided.question.strip()
    if decided.decision != "action":
        return False
    if not decided.operations:
        return True
    chosen = set(decided.operations)
    # v3-43 r11: a read of the screen beside a step of the mission is the mission's own post-read (``MISSION_READS``),
    # never a capture the person's words ask for (``mission_reads``).
    reads = mission_reads(text)
    if not chosen - reads or not chosen <= MISSION_SUBSUMES | reads | {"mission.computer.use"}:
        return False
    application = getattr(semantic_missions.mission_request(in_application, application_names), "application", None)
    restated = semantic_missions.mission_request(decided.request, application_names)
    return restated is None or restated.application != application


def _fills_an_undeclared_argument(
    decided: semantic_decider.ContextDecision, planner_catalog: PlannerCatalog,
) -> bool:
    """Ronda 20b (v3-50 t2: «decime cuántos archivos tiene adentro» → filesystem.explorer.count with ``extension`` and
    ``folder``, whose schema declares only ``extension``; the folder was dropped and the Desktop counted): a field the
    decider filled that no operation it chose declares is part of the request the operation cannot honour. The turn is
    then not that operation's (the caller routes it to the conversation's application when there is one).

    Revisión 2 (G-s040 {"app": "Notepad", "side": "left"} for app.open + window.snap; G-s116 {"app.open": "Spotify",
    "media.play.query": "jazz tranquilo"}): a field is declared when ``_schema_field_of`` places it in a chosen
    operation's schema — the field itself, the value keyed by the operation, the prefix «app» of «appId» — as the
    decider's values are read everywhere else (M136/M141). A chosen operation whose schema the catalog does not hold
    leaves the fields unjudged.

    Estabilización X5 (tandas n5, n6 and their offline replay with the real decider: «ya cierra discord» → app.close
    with {"appId": "discord"}, «ya cierra configuracion…» → app.close with {"app": "Configuración"}; both asked): an
    operation whose target is an identifier names it through its catalog prerequisite (``window.resolve`` before
    ``app.close``), which takes the decider's values in the plan (M141); its fields are declared too."""

    if decided.decision != "action" or not decided.operations or not decided.arguments:
        return False
    prerequisites = {before for operation in decided.operations for before in required_predecessors(operation)}
    schemas: dict[str, tuple[dict[str, Any], list[Any]]] = {}
    for tool in planner_catalog.tools:
        if (tool.name in decided.operations or tool.name in prerequisites) and isinstance(tool.schema, dict):
            properties = tool.schema.get("properties")
            required = tool.schema.get("required")
            schemas[tool.name] = (
                properties if isinstance(properties, dict) else {}, required if isinstance(required, list) else [],
            )
    if set(decided.operations) - set(schemas) or not any(properties for properties, _ in schemas.values()):
        return False

    def declared(name: str) -> bool:
        return name in schemas or any(
            _schema_field_of(name, operation, properties, required) is not None
            for operation, (properties, required) in schemas.items()
        )

    return any(not declared(name) and value not in (None, "") for name, value in decided.arguments)


def _typed_read_beside_the_view(
    decided: semantic_decider.ContextDecision, text: str,
) -> bool:
    """Ronda 20b-3 (revisión 1 de v3-50 t2: with only ``extension`` filled, filesystem.explorer.count ran on the Desktop
    for «decime cuántos archivos tiene adentro» after the 7-Zip mission): a question that points back at what the
    mission showed (``semantic.missions.anaphoric_question``) asks about that application's view. A typed operation
    reads its own place (a folder, the web, a setting), never that view, so it is not the answer; a read of the screen
    beside the mission (``mission_reads``) or the mission itself is (D21 keeps a typed step that is the request)."""

    if decided.decision != "action" or not decided.operations or not semantic_missions.anaphoric_question(text):
        return False
    return not set(decided.operations) <= MISSION_SUBSUMES | mission_reads(text) | {"mission.computer.use"}


def _close_of_the_just_opened(
    text: str,
    history: object,
    available_operations: tuple[str, ...],
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
) -> semantic_decider.ContextDecision | None:
    """M96 (held-out t11 «cerralo» after «abrí el bloc de notas», 28/30 oscillating: the decider asked «¿Quieres que
    cierre el Bloc de notas?» in five of seven runs). A bare close pronoun right after the person asked to open one
    application closes that application, by its name; with two or more opened it asks which. Never the window in
    front (2026-09-22: «cerralo» read as the active window closed VS Code). Estabilización X2 (t3-c18 «ya ciérrala»
    after «abre la calculadora» and two steps in it: asked in n1, closed in n2, by the decider's luck): when the request
    before it opened nothing, the application the conversation is in (``semantic.missions.conversation_application``)
    is closed, by its name. None when there is none: the decider reads the turn as before."""

    pronoun, english = bare_close_pronoun(effect_intent._fold(text))
    if not pronoun or "app.close" not in available_operations:
        return None
    slot = dialogue_slot.read_slot({}, history, text)
    antecedent = next((said for said in slot.antecedents if not dialogue_slot.is_social(said)), None)
    read = resolve_explicit_effects(antecedent, available_operations, application_names) if antecedent else None
    opened = [said for operation, said in zip(read.operations, read.evidence) if operation == "app.open"] if read else []
    # With one opened: the person's own words for it («el bloc de notas») first, then the name the open reader kept.
    named_forms = (dialogue_slot.antecedent_object(antecedent), opened[0]) if len(opened) == 1 else ()
    if not opened:
        conversation = semantic_missions.conversation_application(
            [said for said in _prior_user_texts(history, text) if not dialogue_slot.is_social(said)],
            application_names, available_operations,
        )
        if conversation is None:
            return None
        named_forms = (conversation[0],)
    for named in dict.fromkeys(filter(None, named_forms)):
        request = close_request_for_opened(named, english)
        closing = resolve_explicit_effects(request, available_operations, application_names)
        if closing is not None and closing.operations == ("app.close",):
            return semantic_decider.ContextDecision(request=request, decision="action", operations=("app.close",),
                                                    question="")
    return semantic_decider.ContextDecision(request=text, decision="clarify", operations=(), question="")


# M99: the operations whose object is a part of this PC that a request has to name (the keyboard's language, the
# desktop's background, a routine that fires on a phrase): the decider bringing it is not the person asking for it
# («hazme saber cuando escuches sobre España» restated as a routine that takes screenshots). Measured on the reserve
# replay; a wider set (the family gates of every operation) refused hundreds of reads the decider got right.
_OBJECT_NAMED_OPERATIONS = frozenset({"input.keyboard.layout", "desktop.wallpaper.set", "routine.phrase.create"})
_CLOCK_SET_OPERATIONS = frozenset({"notification.schedule", "reminder.create", "calendar.event.create", "timer.start"})
# M174: the writes the decider gives to things put on a list that are not the list's entries: a change of the list's
# own task, or a note nobody asked for.
_NOT_LIST_ENTRY_WRITES = frozenset({"task.update", "note.create", "note.update"})


def _decider_says_the_anchored_moment(decided: semantic_decider.ContextDecision, anchored: str) -> bool:
    """M144 (DEV-H v4p H-w44-t2 «remind me twenty minutes before that» after «Kick-off is at 8pm.»: the decider's «Remind
    me at 7:40pm tonight about the Arsenal match.» was replaced by «remind me at 19:40», titled «remind me»): when the
    decider's action says the same one clock and the same day the count from the conversation gives, its request stands
    (D58) and keeps what the reminder is for; the count only overrules a moment it does not confirm."""

    if decided.decision != "action" or not decided.operations or not set(decided.operations) <= _ANCHORED_SCHEDULE_OPERATIONS:
        return False
    if dialogue_slot.says_no_reminder_title(decided.request):
        # M165 (DEV-G v4y G-w19-t4 «pues salgo sobre las 6 de la tarde, así que calcula desde ahí» restated «Recuérdame
        # en 5:40 de la tarde.» → set at 18:00, titled with the answer): a request that says only the order and its
        # moment keeps nothing the reminder is for; the count, at that same moment, says what it is for and is read.
        return False

    def moment(request: str) -> tuple[list[tuple[int, int]], str | None]:
        clocks = semantic_temporal.spoken_clocks(effect_intent._fold(request))
        return [(clock.hour, clock.minute) for clock in clocks if clock.resolved], semantic_temporal.task_due_date(request)

    said, counted = moment(decided.request), moment(anchored)
    # «tonight» and no day said are the same day.
    today = {None, datetime.now().astimezone().date().isoformat()}
    return len(said[0]) == 1 and said[0] == counted[0] and (said[1] == counted[1] or {said[1], counted[1]} <= today)


def _clock_completes_the_last_request(text: str, history: object, available_operations: tuple[str, ...]) -> bool:
    """M144 (DEV-H v4p H-w06-t4 «a las 3» after «recuérdame comprar tinto para la oficina», which BAXY answered by
    noting a task, → «¿Qué quieres que haga exactamente a las 3?»): the person's last message asked for a reminder or an
    alarm without its hour (what the readers would ask of it, ``due_time``/``alarm_time``); a clock said alone next is
    that hour, whether or not BAXY asked for it."""

    earlier = _prior_user_texts(history, text)
    if not earlier:
        return False
    asked = resolve_explicit_clarification_intent(earlier[-1], available_operations)
    return (
        asked is not None
        and bool({"due_time", "alarm_time"} & set(asked.missing_fields))
        and set(asked.operations) <= _CLOCK_SET_OPERATIONS
    )


def _reminder_day_without_clock(
    decided: semantic_decider.ContextDecision, text: str, available_operations: tuple[str, ...],
) -> effect_intent.ClarificationIntent | None:
    """M144: the hour a reminder the decider set lacks, when its restatement says the day and what it is for and neither
    it, the message nor the decider's values say a clock or a delay: what the readers ask of the same request said
    first (``due_time``). None otherwise."""

    if not decided.operations or not set(decided.operations) <= _REMINDER_OPERATIONS:
        return None
    folded = effect_intent._fold(text)
    if (
        semantic_temporal.spoken_clocks(folded)
        or semantic_temporal.said_only_a_clock(text)
        or semantic_temporal.said_durations(text)
        or semantic_temporal.alarm_for_hour(folded) is not None
    ):
        return None
    if any(
        # A moment the decider gave at an hour other than midnight was read from somewhere («a la misma hora»).
        isinstance(value, str) and re.search(r"T(?!00:00)\d{2}:\d{2}", value)
        for _, value in decided.arguments
    ):
        return None
    asked = resolve_explicit_clarification_intent(decided.request, available_operations)
    if asked is None or asked.missing_fields != ("due_time",) or not set(asked.operations) <= _REMINDER_OPERATIONS:
        return None
    return asked


def _decided_domain_unnamed(
    operations: tuple[str, ...],
    text: str,
    history: object,
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
    available_operations: tuple[str, ...],
) -> bool:
    """M99 (reserva A6 «empezar ted en español» → «Cambia el idioma del teclado a español.», «enséñame un color suave» →
    «Cambia el fondo de escritorio…»): the decider's restatement named the thing its operation acts on, and neither the
    message nor anything the person said before names it. The curated family gates (``operation_domain_is_grounded``,
    one-sided) are the readers' measure of that; False on every message of the person is an act nobody asked for."""

    said = [text, *(
        str(turn.get("content") or "")
        for turn in (history if isinstance(history, list) else [])
        if isinstance(turn, dict) and turn.get("role") == "user"
    )]
    previous = next((item for item in reversed(said[1:]) if item.strip() and item.strip() != text.strip()), None)
    return bool(operations) and any(
        operation in _OBJECT_NAMED_OPERATIONS
        and all(
            operation_domain_is_grounded(
                item, operation, application_names,
                previous_user_text=previous, available_operations=available_operations,
            ) is False
            for item in dict.fromkeys(said)
        )
        for operation in operations
    )


def _decider_catalog(
    planner_catalog: PlannerCatalog,
) -> tuple[tuple[tuple[str, str], ...], dict[str, tuple[str, ...]]]:
    """The operations the contextual decider reads, and the argument fields of each."""

    tools = planner_catalog.decider_tools
    return (
        tuple((tool.name, tool.description) for tool in tools),
        {tool.name: semantic_decider.argument_signature(tool.schema) for tool in tools},
    )


def _warm_context_decider(llm: Any, planner_catalog: PlannerCatalog) -> None:
    """M117: the decider's catalog prompt is read into its slot when the catalog is configured (``warm_decider``)."""

    warm = getattr(llm, "warm_decider", None)
    if warm is None:
        return
    decider_tools, signatures = _decider_catalog(planner_catalog)
    warm(decider_tools, signatures=signatures)


def _prepare_context_decision(llm: Any, message: dict[str, Any], planner_catalog: PlannerCatalog) -> None:
    """M117: ask the contextual decider for this message now, beside the readers (``LlmRuntime.prepare_decision``).

    ``_context_decided_result`` sends the same message with the same catalog, so the prepared reply is the one it
    would have waited for; a turn a conversation reader keeps never reads it.
    """

    prepare = getattr(llm, "prepare_decision", None)
    if prepare is None:
        return
    decider_tools, signatures = _decider_catalog(planner_catalog)
    prepare(str(message.get("text", "")), message.get("history") or [], decider_tools, signatures=signatures)


# M151 (DEV-F/G/H v4s F-w18-t2, F-w22-t3, F-w24-t3, G-w40-t2, G-w40-t3, G-w44-t5, H-w23-t3, H-w32-t2): what the decider
# chose to open, find or read a file with when the file is the one BAXY's last reply named.
_NAMED_FILE_OPERATIONS = frozenset({
    "file.open", "filesystem.file.open.latest", "filesystem.known.search", "document.pdf.read", "document.text.read",
})


def _conversation_named_file(
    decided: semantic_decider.ContextDecision,
    text: str,
    history: list[Any],
    available_operations: tuple[str, ...],
) -> semantic_decider.ContextDecision | None:
    """M151 (D58): the file BAXY's last reply named by its file name, when the person asks what it says or picks it
    from the ones it listed (``semantic.files.named_file_meant``), is read with the reader its extension takes, or
    opened, where the conversation said it is — not opened when what it says was asked, nor the newest file, nor a
    search, nor another file of a similar name. Only a decision that opens, finds or reads a file changes, and only to
    that one file; a decision of that operation on that same file stays the decider's. None when nothing changes."""

    if decided.decision != "action" or not decided.operations or not set(decided.operations) <= _NAMED_FILE_OPERATIONS:
        return None
    earlier = _prior_user_texts(history, text)
    meant = named_file_meant(text, _previous_reply(history) or "", earlier[-1] if earlier else "")
    operation = named_file_operation(meant) if meant is not None else None
    if meant is None or operation is None or operation not in available_operations:
        return None
    conversation = [str(item.get("content") or "") for item in history if isinstance(item, dict)]
    folder = conversation_file_folder(meant.name, conversation)
    if folder is None or (operation == "file.open" and folder == "all_known"):
        return None
    stem = effect_intent._fold(meant.name.rsplit(".", 1)[0])
    if decided.operations == (operation,) and any(
        isinstance(value, str) and effect_intent._fold(value).strip() in {stem, effect_intent._fold(meant.name)}
        for _, value in decided.arguments
    ):
        return None
    language = _read_reply_language(text, history) or _decisive_request_language(_previous_reply(history) or "")
    return semantic_decider.ContextDecision(
        named_file_request(meant, folder, language or "es"), "action", (operation,), "",
    )


def _picks_a_named_file(objective: str, history: object) -> bool:
    """M164: the message picks one of the files BAXY's last reply named, or asks what it says
    (``named_file_meant``)."""

    earlier = _prior_user_texts(history, objective)
    return named_file_meant(objective, _previous_reply(history) or "", earlier[-1] if earlier else "") is not None


def _pointed_file_opened(
    decided: semantic_decider.ContextDecision,
    text: str,
    history: list[Any],
    available_operations: tuple[str, ...],
) -> semantic_decider.ContextDecision | None:
    """M164 (D58; DEV-I v4y I-w27-t3 «could you open it for me?» after «Found it — budget.xlsx is in your Downloads
    folder.» → asked what to open, where the isolated decider opened budget.xlsx): an opening of a pointer («ábrelo»,
    «open it») right after BAXY named one file, and nothing else, opens that file where the conversation said it is.
    Only when the decider asked: a pointer with nothing named before stays asked (M19), and any other decision stays
    the decider's (M151 reads the file decisions). None when nothing changes."""

    if decided.decision != "clarify" or "file.open" not in available_operations or not _deictic_open_request(text):
        return None
    name = only_file_named(text, _previous_reply(history) or "")
    if name is None:
        return None
    conversation = [str(item.get("content") or "") for item in history if isinstance(item, dict)]
    folder = conversation_file_folder(name, conversation)
    if folder is None or folder == "all_known":
        return None
    language = _read_reply_language(text, history) or _decisive_request_language(_previous_reply(history) or "")
    request = named_file_request(NamedFileMeant("open", name, text), folder, language or "es")
    return semantic_decider.ContextDecision(request, "action", ("file.open",), "")


def _asked_in_another_language(question: str, text: str, history: object) -> bool:
    """The decider's question is in Spanish and the person spoke English, or the other way round: it is never shown."""

    person_language = _read_reply_language(text, history)
    question_language = _decisive_request_language(question) if question else None
    return person_language in {"es", "en"} and question_language in {"es", "en"} and person_language != question_language


def _context_decided_result(
    message: dict[str, Any],
    *,
    llm: Any,
    planner_catalog: PlannerCatalog,
    on_limit: Callable[[str], dict[str, Any] | None] | None = None,
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
    overheard: bool = False,
    decided_beforehand: semantic_decider.ContextDecision | None = None,
) -> dict[str, Any]:
    """The turn as the contextual decider reads it (``semantic.decider``), with the whole conversation.

    Fase 3.5b F2–F4: with the conversation in front of it, the model decides a turn better than the readers,
    the shortlist, the native selector and the gates together; the readers keep only the first message of a
    conversation they prove. The restated request travels as ``objective``: the arguments step reads it.
    ``overheard``: the first message reads as talk the microphone caught (``semantic.guards._overheard_speech``);
    only when the decider asks is the question the overheard one (M118). ``decided_beforehand``: the decider was
    already asked about this message (M123: after a reader whose reading it did not confirm); it is not asked twice.
    """

    text = str(message.get("text", ""))
    history = message.get("history") or []
    available_operations = tuple(tool.name for tool in planner_catalog.tools)
    context = dialogue_slot.read_slot({}, history, text)
    antecedent = context.antecedents[0] if context.antecedents else None
    # M162 (DEV-H v4w H-w08-t3 «cuánta diferencia hay con aquí» after «En Lima son las 12:10.» → searched): the hours
    # apart from here, right after BAXY told one place's clock, are that place's clock read, as «allá» is (M84).
    placed = dialogue_slot.place_substituted(text, antecedent) or semantic_temporal.hours_apart_from_the_clock_told(
        text, context.last_reply,
    )
    placed_read = resolve_explicit_effects(placed, available_operations) if placed is not None else None
    closing = _close_of_the_just_opened(text, history, available_operations, application_names)
    # Live v2-x12 «ahora ponela en modo científica» after «abrí la calculadora»: a step that names no application
    # happens in the one the conversation is in, as the one-turn order (``semantic.missions.follow_up_in_application``).
    in_application = (
        semantic_missions.follow_up_in_application(
            text, _prior_user_texts(history, text), available_operations, application_names,
            english=_read_reply_language(text, history) == "en",
        )
        if closing is None
        else None
    )
    said_before = [
        str(turn.get("content") or "") for turn in reversed(history)
        if isinstance(turn, dict) and str(turn.get("content") or "") != text
    ]
    offered = semantic_temporal.accepted_notification_offer(
        text, context.last_reply,
    ) or semantic_temporal.answered_timer_length(text, context.last_reply, said_before)
    offered_read = resolve_explicit_effects(offered, available_operations) if offered is not None else None
    if offered_read is not None and not set(offered_read.operations) <= _ANCHORED_SCHEDULE_OPERATIONS:
        offered_read = None
    taken_back = (
        semantic_temporal.cancelled_notification_just_set(text, context.last_reply) if offered_read is None else None
    )
    taken_back_read = resolve_explicit_effects(taken_back, available_operations) if taken_back is not None else None
    if taken_back_read is not None and taken_back_read.operations == ("notification.cancel.latest",):
        # M113 (DEV-F v4d F-w45-t4 «scratch the garlic knots one» after «Done, 12-minute timer for the garlic knots.» →
        # task.delete): the notification BAXY just reported setting, taken back by what it is for, is the latest one.
        offered, offered_read = taken_back, taken_back_read
    said_before_by_person = _prior_user_texts(history, text)
    # M177 (DEV-I v5b–v5d I-w34-t2 «25» after «How much should I lower it?» → «El volumen se ha ajustado a 25…»): a level
    # request read here is said in the person's language (an answer with none of its own keeps the conversation's), since
    # the result is worded against it.
    level_in_english = (
        _read_reply_language(text, history) or _decisive_request_language(context.last_reply or "")
    ) == "en"
    level_answered = (
        semantic_levels.answered_level_request(
            text, context.last_reply, said_before_by_person[-1], said_before_by_person[-2::-1],
            english=level_in_english,
        )
        if said_before_by_person and offered_read is None
        else None
    )
    level_answered_read = (
        resolve_explicit_effects(level_answered, available_operations) if level_answered is not None else None
    )
    if level_answered_read is not None and (
        not set(level_answered_read.operations) <= set(_OUTPUT_LEVEL_OPERATIONS)
        or _asks_application_volume(said_before_by_person[-1], available_operations, application_names)
    ):
        # The volume of one application keeps its own completion (AUDIO1787) and the decider.
        level_answered_read = None
    level_offer = (
        semantic_levels.accepted_level_offer(text, context.last_reply)
        if closing is None and offered_read is None and level_answered_read is None
        else None
    )
    if level_offer is not None and _asks_application_volume(
        context.last_reply or "", available_operations, application_names,
    ):
        # BAXY offered one application's volume: its own completion and the decider (AUDIO1787).
        level_offer = None
    level_offer_request = (
        level_offer.request(str(level_offer.setting), level_in_english) if level_offer is not None else None
    )
    level_offer_read = (
        resolve_explicit_effects(level_offer_request, available_operations)
        if level_offer is not None and (level_offer.amount is not None or level_offer.target is not None)
        else None
    )
    if level_offer_read is not None and not set(level_offer_read.operations) <= set(_OUTPUT_LEVEL_OPERATIONS):
        level_offer_read = None
    level_offer_asked: tuple[str, ...] | None = None
    if (
        level_offer is not None
        and level_offer.amount is None
        and level_offer.target is None
        and level_offer.direction is not None
    ):
        level_offer_asked = (
            ("system.settings.adjust",) if level_offer.setting == semantic_levels.BRIGHTNESS
            else ("audio.volume.adjust",)
        )
        if not set(level_offer_asked) <= set(available_operations):
            level_offer_asked = None
    # Estabilización M (live identity check §3c-§3d): a save or a correction of the person's datum said whole is the
    # memory operation with its datum (``semantic.memory.memory_request``); the App runs it on its private route.
    memory_asked = semantic_memory.memory_request(text) if closing is None and offered_read is None else None
    if memory_asked is not None and memory_asked[0] not in {tool.name for tool in planner_catalog.decider_tools}:
        memory_asked = None
    read_before_decider = (
        closing is not None
        or memory_asked is not None
        or offered_read is not None
        or level_answered_read is not None
        or level_offer_read is not None
        or level_offer_asked is not None
        or (placed_read is not None and placed_read.operations == ("system.time",))
    )
    said_back_operations: tuple[str, ...] | None = None
    if closing is not None:
        decided = closing
    elif memory_asked is not None:
        decided = semantic_decider.ContextDecision(request=text, decision="action", operations=(memory_asked[0],),
                                                   question="")
    elif offered_read is not None:
        # M110 (DEV-F v4d F-w33-t4 «Yeah, go on» after «Shall I move the alarm to 17:00?» → «What time is the Spurs
        # game?»; F-w45-t3 «go with 12…» after «How long for the garlic knots?»): the yes to BAXY's offer of a
        # notification at one time, or the length that answers its «how long?», is that notification, read as one
        # request.
        decided = semantic_decider.ContextDecision(
            request=str(offered), decision="action", operations=tuple(offered_read.operations), question="",
        )
    elif level_answered_read is not None:
        # M167 (exception to D58, the question was BAXY's; DEV-I v4y I-w15-t3 «unos 15 nomás» right after «¿Cuánto le
        # subo?» → the decider moved the song 15 seconds on): the amount (or the level) that answers BAXY's own «how
        # much do I raise or lower it?» is that change, of the level the person asked about, read as one request
        # (``semantic.levels.answered_level_request``). A question about seconds or moving forward is not this one.
        decided = semantic_decider.ContextDecision(
            request=str(level_answered), decision="action", operations=tuple(level_answered_read.operations),
            question="",
        )
    elif level_offer_read is not None:
        # M177 (exception to D58, the offer was BAXY's; DEV-F F-w32-t2 «ya po, dale» after «¿Bajo el brillo al 40 para
        # que dure más?», F-w04-t2 «yeah drop it to 40» after «Want me to dim the screen to save battery?», F-w52-t2 «sí,
        # dale, bájalo a 30» after «¿Te bajo el brillo para que aguante más?»; the App's decider read a battery drained
        # to 40, files downloaded or nothing): the yes, or the level said, to BAXY's own offer to raise, lower or set the
        # volume or the brightness is that change of that setting, with the level the person said, else the offer's
        # (``semantic.levels.accepted_level_offer``). Nothing nobody named (the battery, a download) is its object.
        decided = semantic_decider.ContextDecision(
            request=str(level_offer_request), decision="action", operations=tuple(level_offer_read.operations),
            question="",
        )
    elif level_offer_asked is not None:
        # M177: a yes to BAXY's offer that says no amount, to an offer that said none («¿Te bajo el brillo?» → «dale»),
        # asks only the amount, of that setting (owner rule H0027: no default step).
        try:
            question = llm.formulate_explicit_clarification_question(
                str(level_offer_request), level_offer_asked, ("amount",),
            )
        except (ValueError, RuntimeError):
            question = ""
        decided = semantic_decider.ContextDecision(
            request=str(level_offer_request), decision="clarify", operations=level_offer_asked, question=question,
        )
    elif read_before_decider:
        # M84 (DEV-D v3o D-w02-t2 «y si allá son las 10 de la mañana acá qué hora es» after «qué hora es en madrid» →
        # restated «¿Qué hora es en Madrid si allá son las 10…?» and talked): «allá» is the place just asked, and the
        # time said there is converted on the clock read (``_place_clock_facts``), never by the decider.
        decided = semantic_decider.ContextDecision(request=placed, decision="action", operations=("system.time",),
                                                   question="")
    else:
        if decided_beforehand is not None:
            decided = decided_beforehand
        else:
            decider_tools, signatures = _decider_catalog(planner_catalog)
            decided = llm.decide_in_context(text, history, decider_tools, signatures=signatures)
        # Estabilización T (tandas estab 1 y 2, t4-c03 t4 «ya cierra discord», t2-c03 t2 «ya cierra configuracion que me
        # esta laggeando el valorant»: the decider asked with no valid question in all four runs; the recovery wrote
        # «¿Quieres que te avise cuando Discord se cierre?», «¿Quieres que te ayude a cerrar Discord ahora mismo?»): only
        # the decider's own question says what it doubts. A recovered question (the last barrier, which by its prompt
        # supposes no action) is no reading of the order; the clarify branch below still writes it when one is asked.
        asked = (
            decided.question
            if _recovery_question_is_valid(decided.question, decided.request or text, history)
            and _recovery_question_is_valid(decided.question, text)
            else ""
        )
        said_back = (
            _operations_the_question_only_says_back(
                asked, text, planner_catalog, application_names, decided=decided.operations,
            )
            if decided.decision == "clarify" and not overheard
            else None
        )
        if said_back is not None:
            # Ronda 24 (r23 t2-c03#2, t4-c03 t4 «ya cierra discord» → «¿Quieres que cierre Discord ahora mismo?»): a
            # yes/no question that only says a complete order back asks for nothing; the order is done, and the kernel
            # still asks, bound to the invocation, what its policy confirms. Revisión 1: it becomes the decider's action
            # here, before every guard that judges an action (a pointer is never the window in front, M19/M118; what
            # only the person knows, M81; an argument no operation declares; an order served elsewhere).
            said_back_operations = said_back
            decided = semantic_decider.ContextDecision(decided.request, "action", said_back, "", decided.arguments)
        memory = next((op for op in decided.operations if op.startswith("memory.")), None)
        if memory is not None and not any(
            explicit_memory_request(said) for said in (text, _previous_user_request(history, text) or "")
        ):
            # M118 (reserve v4g after M114 put memory back in the decider's catalog: «mis contactos son mayormente
            # masculinos o femeninos», «lugares de vacaciones», «cuando se acerca el cumpleaños de mi amigo», «give me
            # petey's telephone number» → memory.recall, 9 of 25 breaks): BAXY's memory is the person's explicit request
            # only (memory instrument). A memory choice nobody asked for is not the request: what else the decider chose,
            # else what the readers prove in the message, else it is asked — what only the person knows is asked (M81),
            # and a personal fact said without asking to keep it is asked about before it is kept (the App's AskToSave).
            others = tuple(op for op in decided.operations if not op.startswith("memory."))
            read = resolve_explicit_effects(text, available_operations, application_names) if not others else None
            if others:
                decided = semantic_decider.ContextDecision(
                    decided.request, "action", others, decided.question, decided.arguments,
                )
            elif read is not None and not any(op.startswith("memory.") for op in read.operations):
                decided = semantic_decider.ContextDecision(text, "action", tuple(read.operations), "")
            else:
                decided = semantic_decider.ContextDecision(text, "clarify", (), "")
        elif memory is not None:
            # M114: memory is the App's own path (an explicit request, its confirmation); the mind never plans it with
            # other steps, so the decider's memory choice travels alone and the App answers it.
            decided = semantic_decider.ContextDecision(
                decided.request, "action", (memory,), decided.question, decided.arguments,
            )
        if in_application is not None and (
            _decider_left_the_step(decided, in_application, application_names, text)
            or _fills_an_undeclared_argument(decided, planner_catalog)
            or _typed_read_beside_the_view(decided, text)
        ):
            decided = semantic_decider.ContextDecision(in_application, "action", ("mission.computer.use",), "")
        elif _fills_an_undeclared_argument(decided, planner_catalog):
            # Ronda 20b-3 (revisión 1 de v3-50: «¿cuántos zip hay en baxy-prueba-v3?» with no conversation before →
            # filesystem.explorer.count with ``folder``, which the count does not declare; the Desktop was counted and
            # published): with no application to send it to, a part of the request the chosen operation cannot honour
            # is asked, never dropped (M19/M81: what the operation cannot hold is not filled in by guessing).
            decided = semantic_decider.ContextDecision(request=text, decision="clarify", operations=(), question="")
        contrasted = _contrastive_redecision(
            text, history, decided, available_operations, application_names,
            attempted=message.get(_ATTEMPTED_AGAIN),
        )
        if contrasted is not None:
            decided = contrasted
    # M64 (v3f-final F-w14-t3): which fields the decider filled, never their values, so a turn whose arguments went
    # wrong can be told apart from one whose decider gave none.
    argument_fields = [name for name, _ in decided.arguments]
    closes_a_pronoun = bare_close_pronoun(effect_intent._fold(text))[0]
    if (
        decided.decision == "action"
        and (_deictic_open_request(text) or deictic_close_request(effect_intent._fold(text)) or closes_a_pronoun)
        and (
            not dialogue_slot.restatement_was_said(
                decided.request,
                [text, *(str(turn.get("content") or "") for turn in history if isinstance(turn, dict))],
            )
            # M118 (safety; cien-113 008 «cierra aquello» with nothing before it → «Cierra la ventana activa.» →
            # window.active and app.close of the Notepad in front, stopped only by the App's confirmation; 2026-09-22
            # «cerralo» closed VS Code): a pronoun is never the window in front. Estabilización X2: nor is the pointer
            # kept as said («ya ciérrala» → «ya ciérrala»), which the plan reads as the window in front.
            or (closes_a_pronoun and (
                names_the_active_window(decided.request) or bare_close_pronoun(effect_intent._fold(decided.request))[0]
            ))
        )
    ):
        # Fase 3.5b M19 (cien-104 «ábreme eso porfa» after the time → «Abre el navegador» → a browser opened): a
        # pointer with no antecedent in what was said is asked, never filled with an object the model brought.
        decided = semantic_decider.ContextDecision(request=text, decision="clarify", operations=(), question="")
    # M154 (DEV-I v4u I-s053 «…a cuánto cerró el blue hoy que tengo que cambiar unos dólares…», H-s093 «…rate todya,
    # im wiring money to my cousin…», I-s078 «mi viejo me preguntó cuántos habitantes tiene Mar del Plata…»): the need
    # that makes the person ask, said after the question, and who asked or claims it, said before, are its context too.
    question_asked = question_with_context(text) or question_with_its_reason(text)
    if decided.decision == "action" and decided.operations == ("web.search",) and (
        names_own_data(text)
        if question_asked is None
        # M138 (DEV-G v4n G-w42-t1 «when do the Lakers play next? my buddy wants to come over and watch it» → asked
        # what only the person knows, where the isolated decider looked the game up): what is said after the question
        # is its context. Only the question, and what the decider would look up, are read for the person's own data.
        else names_own_data(question_asked)
        or names_own_data(decided.request)
        or any(isinstance(value, str) and names_own_data(value) for _, value in decided.arguments)
    ):
        # M81 (DEV-D v3m D-s020 «It's going to rain en la casa de mamá?», D-s053 «¿Miguel sigue viviendo en
        # Arkansas?»): the person's own data never goes to the web (00_IDENTIDAD, invariant 6). What only the person
        # knows (where mom lives, who Miguel is) is asked, never looked up.
        decided = semantic_decider.ContextDecision(request=text, decision="clarify", operations=(), question="")
    if (
        decided.decision == "action"
        and decided.operations
        and set(decided.operations) <= _INSTALLED_SOFTWARE_READS
        and "web.search" in available_operations
        and asks_latest_release(text)
    ):
        # M89 (DEV-D v3r D-w20-t3 «btw what's the latest version of Python right now?» → «Están instaladas las versiones
        # 3.13.3, 3.12.10 y 3.10.0»): the newest release is public and looked up; the copy on this PC is not it.
        decided = semantic_decider.ContextDecision(request=text, decision="action", operations=("web.search",), question="")
    if (
        decided.decision == "action"
        and decided.operations
        and set(decided.operations) <= {"task.search", "notification.list.due"}
        and "calendar.event.list" in available_operations
        and names_own_event(text)
    ):
        # M100 (reserva A1 «what time is the black tie gala dinner supposed to begin», «con quién me encuentro yo hoy»
        # → task.search; «meeting reminders from three to five» → the internal due step): an event of the person's, or
        # who they meet, is read from their calendar.
        decided = semantic_decider.ContextDecision(
            request=decided.request, decision="action", operations=("calendar.event.list",), question="",
        )
    if (
        decided.decision == "action"
        and decided.operations == ("notification.list.due",)
        and "notification.list" in available_operations
        and not asks_overdue_notifications(text)
    ):
        # M110 (DEV-F v4d F-w45-t5 «and the pizza, how many minutes till I pull it out?» → the reminders already due,
        # «The pizza reminder is not set yet.»): what is still to ring is in the list of what is scheduled; the due
        # read is for the ones that already rang.
        decided = semantic_decider.ContextDecision(
            request=decided.request, decision="action", operations=("notification.list",), question="",
        )
    if (
        decided.decision == "action"
        and decided.operations == ("audio.status",)
        and "media.status" in available_operations
        and asks_what_sounds(text)
    ):
        # M164 (DEV-G v4y G-s110 «oye, dime qué es esto que está sonando, que me ha encantado y no la reconozco» →
        # «El volumen está en 60…», where the isolated decider read the media session): what is sounding is the song
        # that plays, never the output's level; a question about the level, the mute or the device keeps audio.status.
        decided = semantic_decider.ContextDecision(
            request=text, decision="action", operations=("media.status",), question="",
        )
    said_level = semantic_levels.read(text) if decided.decision in {"action", "clarify"} else None
    if (
        said_level is not None
        and (said_level.direction is not None or said_level.target is not None)
        and (
            "media.seek.relative" in decided.operations
            # M180 (DEV-G v5b/v5c/v5f G-w21-t2 «súbele un poco a esa» and DEV-H v5f H-w21-t3 «subile un toque», music
            # playing → restated «Pasa a la siguiente canción.» and the song changed): the transport (play, pause, next,
            # previous) never raises or lowers anything. A message the level reader reads whole names no song to skip
            # to; skipping is «pasa a la siguiente», «ponle otra», «skip this one», which it never reads.
            or decided.operations == ("media.control",)
            or (
                decided.decision == "clarify"
                and not decided.operations
                and semantic_levels.names_position(decided.request)
            )
        )
        and not semantic_levels.names_position(text)
    ):
        # M167 (owner rule H0027 and the level readers; DEV-G v4y G-w21-t2 «súbele un poco a esa» with the salsa playlist
        # playing → restated «Adelanta un poco la canción.» and asked «¿Cuántos segundos la adelanto?»; D-w18-t2 «can
        # you bajarle un poco» → «¿Cuántos segundos retrocedo?»; G-w21-t3 «subile 10, con eso ya me sirve» → the song
        # moved 10 seconds on): raising or lowering («súbele», «bájale», «turn it up») is the level, never the position
        # of what plays; moving it is «adelántala», «retrocede», «skip ahead». With the amount said it is that change;
        # without it, only the amount is asked (no default step).
        setting = (
            said_level.setting
            or semantic_levels.setting_of(said_before_by_person[-1] if said_before_by_person else None)
            or semantic_levels.VOLUME
        )
        if said_level.amount is None and said_level.target is None:
            asked_level = (
                ("system.settings.adjust",) if setting == semantic_levels.BRIGHTNESS else ("audio.volume.adjust",)
            )
            if set(asked_level) <= set(available_operations):
                try:
                    question = llm.formulate_explicit_clarification_question(text, asked_level, ("amount",))
                except (ValueError, RuntimeError):
                    question = ""
                decided = semantic_decider.ContextDecision(
                    request=text, decision="clarify", operations=asked_level, question=question,
                )
        else:
            level_request = said_level.request(setting, level_in_english)
            level_read = resolve_explicit_effects(level_request, available_operations)
            if level_read is not None and set(level_read.operations) <= set(_OUTPUT_LEVEL_OPERATIONS):
                decided = semantic_decider.ContextDecision(
                    request=level_request, decision="action", operations=tuple(level_read.operations), question="",
                )
    if (
        "window.resolve" in available_operations
        and (decided.decision in {"talk", "clarify"} or set(decided.operations) <= _SHOWN_MEDIA_READS)
        and application_shown_media_name(text, application_names) is not None
    ):
        # M103 (owner script t22 «¿Sabes qué peli estoy viendo en potplayer?» → media.status read Spotify): what a named
        # player shows is its window's title; with no window of it open, the read says so.
        decided = semantic_decider.ContextDecision(request=text, decision="action", operations=("window.resolve",), question="")
    clock_request = (
        _clock_read_request(text, history)
        if decided.decision in {"talk", "clarify"} and "system.time" in available_operations
        else None
    )
    if clock_request is not None:
        # M85 (DEV-D v3o D-w02-t2 «y si allá son las 10 de la mañana acá qué hora es» after «qué hora es en madrid»,
        # D-s025 «si pasan cuarenta minutos, ¿qué hora será?»): a clock the readers prove — another place's, «allá»
        # being the place of the clock question before, or this clock later on — is this PC's clock read (system.time
        # converts and adds), never an hour the writer says from memory.
        decided = semantic_decider.ContextDecision(
            request=clock_request, decision="action", operations=("system.time",), question="",
        )
    unasked_action: dict[str, Any] | None = None
    if decided.decision == "action":
        slot = dialogue_slot.read_slot({}, history, text)
        unasked = None
        if dialogue_slot.is_social(text):
            # M65 (conv-v3g owner script t37 «Perfecto muy bien» after a question BAXY composed → «Abre Steam y entra
            # a la biblioteca.» and Steam opened): thanks, praise or a closing asks for nothing and answers no
            # question, whatever is pending. An offer BAXY holds is confirmed by the shell, never through here.
            unasked = "social"
        elif "input.text.type" in decided.operations and not semantic_ui.asks_to_type(
            text, slot.last_reply, slot.antecedents[0] if slot.antecedents else None,
        ):
            # M65 (conv-v3g owner script t30 «Di la palabra"algo"» → «Escribe la palabra «algo».»): saying is not
            # typing into the window in front; nothing in the message or the question it answers asks to write.
            unasked = "untyped"
        elif _decided_domain_unnamed(decided.operations, text, history, application_names, available_operations):
            unasked = "unnamed_domain"
        elif dialogue_slot.offers_to_baxy(text):
            # M99 (reserva A6 «quieres netflix and chill» → Netflix opened): something offered to BAXY orders nothing.
            unasked = "offer"
        elif (
            set(decided.operations) & _CLOCK_SET_OPERATIONS
            and semantic_temporal.said_only_a_clock(text)
            and not str(slot.last_reply or "").rstrip().endswith("?")
            and not _history_has_pending_clarification(history, message.get("pendingClarification"))
            and not _clock_completes_the_last_request(text, history, available_operations)
        ):
            # M99 (reserva A6 «las dos menos cuarto» → an alarm at 10:15): a clock said alone, answering no question of
            # BAXY's, sets nothing; what it is for is asked.
            unasked = "bare_clock"
        if unasked is not None:
            unasked_action = {"kind": unasked, "request": decided.request, "operations": list(decided.operations)}
            decided = semantic_decider.ContextDecision(
                # M99 (reserva A6): an act on a thing nobody named, or a clock said alone, is asked about.
                request=text, decision="clarify" if unasked in {"unnamed_domain", "bare_clock"} else "talk",
                operations=(), question="",
            )
            if (
                unasked == "untyped"
                and "mission.computer.use" in available_operations
                and semantic_missions.ordered_in_application(text, application_names) is not None
            ):
                # v3 ronda 5 (lectura M3, v3-27 «abre el mapa de caracteres y copia el símbolo del euro» → typing
                # chosen, then talk): typing nobody asked for is no act, but the order said inside an installed
                # application still is one; the engine does it there with the person's words.
                decided = semantic_decider.ContextDecision(text, "action", ("mission.computer.use",), "")
    # M64 (v3f-final F-w01-t4 «…el mistral de 35» restated «…Mistral de 350 ml…», F-s054 «…mañana en Santiago?»): a
    # number, unit, date, clock time or name of the restatement nobody said never travels as the objective.
    descriptions = {tool.name: tool.description for tool in planner_catalog.tools}
    fidelity = semantic_decider.faithful_request(
        decided.request,
        text,
        [str(turn.get("content") or "") for turn in history if isinstance(turn, dict)],
        world=[semantic_decider.catalog_line(op, descriptions.get(op, "")) for op in decided.operations],
    )
    decider_request = decided.request
    if fidelity.kind != "kept":
        decided = semantic_decider.ContextDecision(
            fidelity.request, decided.decision, decided.operations, decided.question, decided.arguments,
        )
    new_thing = (
        semantic_decider.followup_thing_kept(decided.request, text, antecedent or "")
        if decided.decision == "action" and decided.operations == ("web.search",)
        else None
    )
    if new_thing is not None:
        # M179 (DEV-I v5a–v5d I-w17-t2 «¿y la libra, cómo anda?» after the dollar → restated «¿Cómo está el dólar hoy,
        # por favor?» and the dollar searched again): what a follow-up names new takes the place of what the request
        # before asked about; the rest of that request (today, the country, the team) stays. The decider's own values
        # were about the old thing and are not kept: the query is read from this request.
        decided = semantic_decider.ContextDecision(new_thing, "action", ("web.search",), decided.question)
    edited_draft = (
        effect_intent.edited_draft_request(text, list(_prior_user_texts(history, text)))
        if decided.decision != "action" and "message.draft" in available_operations
        else None
    )
    if edited_draft is not None:
        # M111 (DEV-F v4d F-w01-t4 «mejor cámbialo, ponle que llego como 10 minutos tarde…» → «No puedo cambiar el
        # mensaje…»): new words for the message just left written are that draft again, to the same person in the same
        # client; leaving a message written is never a limit.
        decided = semantic_decider.ContextDecision(
            request=edited_draft, decision="action", operations=("message.draft",), question="",
        )
    if (
        decided.decision == "action"
        and "message.send" in decided.operations
        and "message.draft" in available_operations
        and semantic_messaging.asks_not_to_send(text)
    ):
        # M155 (safety exception to D58; DEV-I v4u I-s061 «… but leave it for me to send»): a message the person orders
        # not to send is left written, never sent, whoever read it — the readers no longer prove a send for it
        # (``resolve_explicit_effects``), and the decider's send is held the same way. Its words are read again from
        # the message (``message.draft`` arguments).
        decided = semantic_decider.ContextDecision(decided.request, "action", ("message.draft",), decided.question)
    clock_cancelled = (
        semantic_temporal.clock_named_cancellation(text, decided.request)
        if decided.decision == "action"
        and decided.operations == ("notification.cancel.latest",)
        and "notification.cancel.at" in available_operations
        else None
    )
    if clock_cancelled is not None:
        # M158 (safety exception to D58; DEV-I v4u/v4v I-w26-t4 «cancela la de las 7 que mañana no trabajo» after a list
        # of eleven alarms and reminders → «cancela la última alarma», and the last one set, not the one at 7, was
        # cancelled): the alarm or reminder the person names by its clock is the one at that clock
        # (``notification.cancel.at``), never the last one set whatever it is. When the last one this conversation set
        # is the one at that clock, M145 (``_own_notification_cancellation``) makes it the latest again. A move
        # (cancel.latest with schedule) and a cancellation that names no clock stay as decided.
        decided = semantic_decider.ContextDecision(clock_cancelled, "action", ("notification.cancel.at",), "")
    if (
        decided.decision == "action"
        and len(decided.operations) == 1
        # The moments of alarms and reminders keep their own readers (``semantic.temporal``).
        and not set(decided.operations) & (_CLOCK_SET_OPERATIONS | {"notification.cancel.at"})
    ):
        restated = resolve_explicit_effects(decided.request, available_operations, application_names)
        if (
            restated is not None
            and 1 < len(restated.operations) <= 8
            and set(restated.operations) == set(decided.operations)
        ):
            # M111 (DEV-F v4d F-s015 «¿Me abres la calculadora y el Bloc de notas?» → «Abre la Calculadora y el Bloc
            # de notas.» with one app.open, and only the Calculator opened): the restatement names the operation as
            # many times as the readers read it; each one is a step.
            decided = semantic_decider.ContextDecision(
                decided.request, "action", tuple(restated.operations), decided.question, decided.arguments,
            )
        elif (
            restated is not None
            and restated.operations == ("mission.computer.use",)
            and set(decided.operations) <= MISSION_SUBSUMES
        ):
            # Live v2-s13 «y ahora andá a configuración» after a mission in Discord: the decider took the application
            # from the conversation («En Discord, haz clic en Configuración.») but chose a lone click, which went to
            # whatever window was in front and ended «No se confirmó si… funcionó». A restatement the mission reader
            # reads as a step inside an application is that mission, decided by the screen like any other; one of its
            # own primitives alone is a piece of it. Its arguments are read from the restatement, not the click's.
            # Integración ronda 3: an order that says its own place («en la terminal andá a configuración y …», v3-38)
            # is the person's words, never the restatement (it paraphrases: «haz clic en Configuración»), as the
            # coverage gate keeps them (``_order_served_elsewhere``).
            decided = semantic_decider.ContextDecision(
                _mission_goal_of_the_restatement(text, decided, history, application_names),
                "action", ("mission.computer.use",), decided.question,
            )
        elif (
            decided.operations == ("input.visible.click",)
            and "mission.computer.use" in available_operations
            and semantic_missions.clicks_a_route(text)
        ):
            # r15b t-menu-4 «Gira la imagen 90 grados a la derecha desde el menú Imagen > Girar»: one click on «Imagen»
            # for a route of two pieces landed on whatever window was in front. A route the person says is the
            # engine's order, in their words, never one click of it.
            decided = semantic_decider.ContextDecision(text, "action", ("mission.computer.use",), decided.question)
    elif (
        decided.decision == "action"
        and set(decided.operations) & MISSION_SUBSUMES
        and set(decided.operations) & mission_reads(text)
        and set(decided.operations) <= MISSION_SUBSUMES | mission_reads(text)
    ):
        restated = resolve_explicit_effects(decided.request, available_operations, application_names)
        if restated is not None and restated.operations == ("mission.computer.use",):
            # v3-43 r11 «luego a opciones de energía y dime qué plan está activo» → «En el Panel de control, haz clic
            # en «Opciones de energía» y dime qué plan…» with a click plus vision.describe: the plan clicked and then
            # alleged «la visión no está configurada» while the window's controls held the answer. A step of the
            # mission with a read of the screen it reaches is the mission (its post-read answers the question).
            decided = semantic_decider.ContextDecision(
                _mission_goal_of_the_restatement(text, decided, history, application_names),
                "action", ("mission.computer.use",), decided.question,
            )
    listed_entries = (
        entries_on_a_list(text, said_before_by_person[::-1])
        if decided.decision == "action"
        and decided.operations
        and set(decided.operations) <= _NOT_LIST_ENTRY_WRITES
        and "task.create" in available_operations
        else None
    )
    if listed_entries is not None:
        # M174 (owner D59 and the decider's catalog «anotar algo en una lista (la del súper…)»; DEV-H v5c H-w10-t2
        # «Agrégale bloqueador, gafas y el cargador del parlante» right after «Crea una lista para el paseo a Santa
        # Marta» → task.update asking which title to change; DEV-D v5c D-w03-t2 «agrega tomates tmb» after «lista del
        # super: …» → note.update): things put on a list of the person's, named in the message or made just before it,
        # are tasks on that list, one per thing; never a change of the list's own task nor a note nobody asked for.
        # The request is the one the readers read as those entries (the plan grounds each one from it).
        listed_request, listed_count = listed_entries
        decided = semantic_decider.ContextDecision(listed_request, "action", ("task.create",) * listed_count, "")
    named_file = _conversation_named_file(decided, text, history, available_operations)
    if named_file is not None:
        # M151 (DEV-F v4s F-w18-t2 «Yeah, that's the one, give us the gist of it» after «Downloads is open; I can see
        # «council_tax_2026-27.pdf»…» → file.open; DEV-G v4s G-w40-t2 «abre el segundo» after «Encontré dos: …» → the
        # newest file): the file BAXY just named, or the one of those it listed that the person picked, is the one read
        # or opened.
        decided = named_file
    pointed_file = _pointed_file_opened(decided, text, history, available_operations)
    if pointed_file is not None:
        # M164 (DEV-I v4y I-w27-t3 «could you open it for me?» after «Found it — budget.xlsx is in your Downloads
        # folder.» → asked): «it» is the one file BAXY just named; it is opened, not asked about.
        decided = pointed_file
    # M110: the thing named («la junta», «kick-off») may have its moment further back in the conversation.
    counted = semantic_temporal.anchored_offset_request(text, context.last_reply, said_before)
    # M113 (DEV-F v4d F-w18-t3 «Remind me the day before the first one's due, nine in the morning»): days counted from a
    # date said earlier in the conversation.
    anchored = counted or semantic_temporal.anchored_day_request(text, context.last_reply, said_before) or (
        # M148 (DEV-G v4r G-w19-t4 «pues salgo sobre las 6 de la tarde…» after «recuérdamelo veinte minutos antes de
        # salir» → «¿A qué hora tienes pensado salir?» → set at 18:00): the moment the answer gives, less the advance the
        # request asked, is when it rings.
        semantic_temporal.answered_advance_request(text, context.pending_request, context.last_reply)
    )
    anchored_read =resolve_explicit_effects(anchored, available_operations) if anchored is not None else None
    if (
        anchored_read is None
        and counted is not None
        and anchored == counted
        and decided.decision == "action"
        and decided.operations
        and set(decided.operations) <= {"notification.schedule", "reminder.create"}
    ):
        # M168 (D77; DEV-I v4y I-w12-t4 «ponem una alarma una hora antes», I-w29-t3 «put a reminder on an hour ahead of
        # tip-off…» after the kick-off BAXY read from ESPN): the readers do not read the order as written («ponem», «put
        # a reminder»), and the decider chose the notice; the moment is still the count from the moment BAXY gave, never
        # the model's own sum.
        anchored_read = EffectIntent(tuple(decided.operations))
    if (
        anchored_read is not None
        and set(anchored_read.operations) <= _ANCHORED_SCHEDULE_OPERATIONS
        and not _decider_says_the_anchored_moment(decided, str(anchored))
    ):
        # M84 (DEV-D v3o D-w08-t3 «ponme recordatorio una ora antes d ese partido» → «¿Cuándo es ese partido?», D-w02-t3
        # «ponme una alarma media hora antes de eso» → «Pon una alarma a las 10:30.»): the moment BAXY just gave, less
        # or plus the duration, is the time; the readers read the request that says it, the decider's is not used.
        decided = semantic_decider.ContextDecision(anchored, "action", tuple(anchored_read.operations), "")
    if (
        decided.decision == "action"
        and anchored_read is None
        and set(decided.operations) <= {"notification.schedule", "reminder.create"}
        and (
            (
                fidelity.kind == "person"
                and any(semantic_temporal.spoken_clocks(effect_intent._fold(what)) for what in fidelity.introduced)
                and not semantic_temporal.spoken_clocks(effect_intent._fold(text))
                and not semantic_temporal.said_only_a_clock(text)
                and not semantic_temporal.said_durations(text)
            )
            # M152 (DEV-G v4s G-w19-t3 «vale, pues recuérdamelo veinte minutos antes de salir» restated «Recuérdame en
            # 20 minutos que tengo que ir al aeropuerto.» → set at 21:20, so G-w19-t4 «pues salgo sobre las 6 de la
            # tarde…» answered no question and was set at 21:20 again): the message says a length, but counted from a
            # moment nobody placed; the restatement that made it a delay from now is a time nobody said either.
            or semantic_temporal.advance_restated_as_delay(text, decider_request)
            # M175 (DEV-F v5c F-w45-t2 «and one for the garlic knots» after «pizza just went in, gimme a 25 minute
            # countdown» restated «Set a 25-minute countdown for the garlic knots.»): a length said for another thing is
            # never borrowed; how long this one runs is asked (unless BAXY's answer gave it, below).
            or semantic_temporal.length_borrowed_for_another(text, decider_request, said_before)
        )
    ):
        # M110 (DEV-F v4d F-w46-t3 «poneme una alarma para ese día bien temprano» restated «…el sábado 2 de octubre a
        # las 5:00» → «¿Cuándo y con qué título…?» as an action): the time was the decider's, not the person's, and the
        # message says none; when it rings is asked.
        decided = semantic_decider.ContextDecision(request=text, decision="clarify", operations=(), question="")
    stepped = (
        semantic_temporal.step_timer_request(text, [
            str(item.get("content") or "") for item in reversed(history)
            if isinstance(item, dict) and item.get("role") == "assistant"
        ])
        if anchored_read is None
        and (
            decided.decision == "clarify"
            or (decided.decision == "action" and set(decided.operations) <= {"notification.schedule", "reminder.create"})
        )
        else None
    )
    stepped_read = resolve_explicit_effects(stepped, available_operations) if stepped is not None else None
    if (
        stepped_read is not None
        and set(stepped_read.operations) <= {"notification.schedule", "reminder.create"}
        and not (
            decided.decision == "action"
            and {minutes for _, minutes in semantic_temporal.said_durations(decided.request)}
            == {minutes for _, minutes in semantic_temporal.said_durations(stepped)}
        )
    ):
        # M175 (DEV-F v5c F-w34-t4 «Venga, ponme el temporizador para lo de pochar» after «…Pocha patata y cebolla a
        # fuego lento unos 20 minutos…», DEV-D v5c D-w10-t3 «¿Me pones un temporizador para voltearlas?» after «…Las
        # cocinamos 5 minutos por cada lado.» → «¿Cuántos minutos le pongo al temporizador?»): a timer asked for a step
        # BAXY's recent answer gave one length is that length, titled by the step; a decider that already set that
        # length keeps its own decision.
        decided = semantic_decider.ContextDecision(stepped, "action", tuple(stepped_read.operations), "")
    day_only = (
        _reminder_day_without_clock(decided, text, available_operations)
        if decided.decision == "action" and anchored_read is None
        else None
    )
    if day_only is not None:
        # M144 (DEV-H v4p H-w32-t4 «no era eso, quería que me lo pongas de recordatorio el jueves» restated «Ponme un
        # recordatorio el jueves para inscribirme a las Jornadas…» → «¿Cuándo, día y hora, quieres que te lo
        # recuerde?»): a reminder with its day and what it is for but no hour asks only the hour, as the same request
        # said first asks it (``resolve_explicit_clarification_intent``); the restatement stays the objective, so the
        # answer completes it. Nothing rings at a midnight nobody said.
        decided = semantic_decider.ContextDecision(
            request=decided.request,
            decision="clarify",
            operations=decided.operations,
            question=llm.formulate_explicit_clarification_question(
                decided.request, decided.operations, day_only.missing_fields,
            ),
        )
    if decided.decision == "action" and anchored_read is None:
        asked = resolve_explicit_clarification_intent(text, available_operations)
        if (
            asked is not None
            and "list_entries" in asked.missing_fields
            and set(asked.operations) & set(decided.operations)
            # M89 (DEV-D v3r D-p37-t2): entries the person said just before, which BAXY's question was about, were said.
            and not list_entries_said_before(text, antecedent, context.last_reply)
            # M91 (reserva «haz una nueva lista de la compra»): a list asked for new is complete when it is made; only
            # an entry that names nothing is missing a value.
            and not list_creation_said(effect_intent._fold(text))
        ):
            # M84 (DEV-D v3o D-p17-t3 «nevermind add an item to my swimming list» → «Add swimming to my list.», and
            # «swimming» was added): the readers prove the entry was not said (M80); the list's name is never its
            # entry, and the decider's restatement does not fill it.
            decided = semantic_decider.ContextDecision(request=text, decision="clarify", operations=(), question="")
    if (
        decided.decision == "action"
        and "email.latest.reply" in decided.operations
        and latest_mail_reply_without_words(text)
    ):
        # M100 (reserva A13 «that last email needs to be answer a. s. a. p.» → answered «a. s. a. p.»): a reply goes
        # with the words the person said, never with how soon or with the restatement's; with none, what to answer is
        # asked.
        decided = semantic_decider.ContextDecision(
            request=text, decision="clarify", operations=("email.latest.reply",), question="",
        )
    if decided.decision != "limit" and asks_to_watch_the_news(text):
        # M104 (reserve v3z es631 «establecer notificaciones para las noticias sobre el gasoducto sur peruano» → a
        # notification scheduled for nothing): watching the news to tell when there is some is no operation; the
        # limit says so, never a notice nobody can fill. D59 §6 (owner, 2026-10-02): whatever was decided (today's
        # headlines read, a talk, a question about the time), and the limit offers to search the news now (the
        # «news_watch_limit» shape).
        decided = semantic_decider.ContextDecision(request=text, decision="limit", operations=(), question="")
    if decided.decision == "limit" and dialogue_slot.takes_back(text, antecedent):
        # M84 (DEV-D v3o D-p01-t3 «no, cancel», D-p14-t3 «Cancelar foto» → «No cancelo la foto.»): taking back what was
        # just asked is said to BAXY, never a limit of cancelling.
        decided = semantic_decider.ContextDecision(request=text, decision="talk", operations=(), question="")
    if decided.decision in {"limit", "talk"} and dialogue_slot.asks_to_undo(text):
        # Uso real v3 t2 (c04-3 «no espera se ve muy grande, regresala como estaba» after a failed change → «No hago
        # ajustes de tamaño de ventana.»): an undo is about the conversation's last change, never a limit. With none
        # asked before, what to undo is asked; when BAXY's last reply told that change did not happen, BAXY has no
        # change to put back and says so in talk (llm_chat: data «heldFact.undoUnapplied»), never how the screen is now.
        if not antecedent:
            decided = semantic_decider.ContextDecision(request=text, decision="clarify", operations=(), question="")
        elif dialogue_slot.undo_with_nothing_changed(text, context.last_reply):
            decided = semantic_decider.ContextDecision(request=text, decision="talk", operations=(), question="")
    if decided.decision == "limit" and (dialogue_slot.is_assent(text) or dialogue_slot.gives_go_ahead(text)):
        # M102 (DEV-D v3z D-p24-t4 «Yes, do it for me.» after «The streaming of Hustlers failed because Netflix requires a
        # sign-in on this PC…» → «I do not handle tasks outside my scope.»): a yes or a go-ahead asks for nothing new, so
        # it is never a limit; what stands in the way (the failure just told, or nothing waiting for the yes) is said in
        # talk, with the conversation in front of the writer (M88 holds it to saying nothing was done).
        decided = semantic_decider.ContextDecision(request=text, decision="talk", operations=(), question="")
    if decided.decision in {"talk", "limit"} and dialogue_slot.do_that_with_nothing_named(text, context.last_reply):
        # M118 (cien-113 048 «haz eso» after «keep chatting without opening apps»: the decider talked and the writer
        # invented «no tengo la capacidad de mantener conversaciones…»): «do that» with nothing to do named before it
        # is asked («¿Qué es eso?»), never answered or refused.
        decided = semantic_decider.ContextDecision(request=text, decision="clarify", operations=(), question="")
    if decided.decision == "clarify" and dialogue_slot.remate_of_what_was_done(text, context.last_reply):
        # M118 (owner script t57 «al volumen» after «He puesto el volumen en 100…» → «¿Cuánto le subo?»; conv-v3z2
        # talked): naming only what was just done asks nothing again; it is answered as the remate it is.
        decided = semantic_decider.ContextDecision(request=text, decision="talk", operations=(), question="")
    # cien-107 100: with a block of history the decider answered «talk» («Write a letter to Eris.»), the knowledge
    # contract let «…because I do not have access to external communication channels…» through; talk is bounded too.
    if decided.decision in {"clarify", "talk"} and effect_intent.out_of_world_request(text):
        # cien-105/106 «post a letter to Eris» → «What should the letter say?», vetoed by the App as a question about
        # what cannot be done: the boundary of an unreachable place holds here too (apply_out_of_world_boundary).
        decided = semantic_decider.ContextDecision(request=text, decision="limit", operations=(), question="")
    if decided.decision == "limit" and conversation_only_content_request(text):
        # M78 (DEV-D v3l p35-t1 «…análisis de FODA…» refused): content written in the conversation (an analysis, a
        # letter, code) is what BAXY does; a limit on it is false.
        decided = semantic_decider.ContextDecision(request=decided.request, decision="talk", operations=(), question="")
    if (
        decided.decision in {"limit", "talk"}
        and "web.search" in available_operations
        and asks_what_a_cinema_shows(text)
    ):
        # M99 (DEV-D v3x D-p28-t1 «I want to watch a movie at Century 25 Union Landing…» → «I cannot order or buy
        # movies…»): what a cinema shows is looked up; the limit was about buying, which nobody asked.
        decided = semantic_decider.ContextDecision(request=text, decision="action", operations=("web.search",), question="")
    if decided.decision == "limit" and "web.search" in available_operations and searches_places_somewhere(
        text, decided.request,
    ):
        # M179 (DEV-F v5b–v5d F-w16-t2 «sí, órale, búscame unas por la Roma Norte» after «¿me puedes pedir unos tacos al
        # pastor por Rappi?» → restated «Busca unos tacos al pastor por Rappi en Roma Norte.» → «Eso no lo hago: buscar
        # tacos al pastor en Roma Norte.»): an order to search for a kind of place in a place said is looked up; the
        # service the conversation named before is a detail of it, never a limit of the search.
        decided = semantic_decider.ContextDecision(
            request=decided.request or text, decision="action", operations=("web.search",), question="",
        )
    if (
        decided.decision == "limit"
        and "streaming.play.named" in available_operations
        and watch_named_title(text) is not None
    ):
        # M179 (DEV-D v5a–v5d D-p19-t1 «I'd like to watch a movie called After the Wedding with Spanish subtitles on.» →
        # «I do not provide movies with subtitles.»): a film or a series the person names to watch is played; how it
        # is watched (subtitles, dubbing) is a detail, never the reason to refuse it. Its title is read from the
        # restatement (``semantic.arguments.partial_explicit_arguments``) and a service not said is asked.
        decided = semantic_decider.ContextDecision(
            request=decided.request or text, decision="action", operations=("streaming.play.named",), question="",
        )
    converted = (
        currency_conversion_request(text, decided.request, context.last_reply or "", antecedent or "")
        if decided.decision == "talk" and "web.search" in available_operations and not asks_for_code(text)
        else None
    )
    if converted is not None:
        # M154 (D35, D52; DEV-H v4u H-w05-t4 «and in pesos chilenos?» after «Hoy el Bitcoin está en 85.000 dólares.» →
        # talked «Today Bitcoin is at 1,850,000 Chilean pesos.»; H-s087 «¿cuánto son 350 dólares en euros, más o
        # menos?» → «Son aproximadamente 320 euros.»): an amount in another currency, or an exchange rate, moves every
        # day; it is looked up (the reference rate, ``FrankfurterRateSource``), with the amount and the currencies said
        # in the conversation (``semantic.web.currency_conversion_request``). A rate of what BAXY said in one currency
        # (M118: «¿y eso cuánto es al mes?») names no second currency and stays the decider's.
        decided = semantic_decider.ContextDecision(
            request=converted, decision="action", operations=("web.search",), question="",
        )
    reference = None
    recommended = False
    # M56 (v3c-final F-w14-t1): code the person asks for is written, whatever the decider's rewrite of it says.
    if (
        decided.decision == "talk"
        and "web.search" in available_operations
        and not asks_for_code(text)
        # M118 (D58): a rate of what BAXY just said is worked out from its numbers, whatever the restatement names.
        # M162 (DEV-I v4w I-w08-t2 «y para la mitad de gente?», DEV-H H-w24-t3 «pasame la brecha en porcentaje»): so
        # is a recipe scaled, a difference, a gap or a percentage of the numbers it said, all of them said.
        # M163 (DEV-G v4y G-w16-t3 «uy y eso cuánto sería en fahrenheit…», G-w08-t3 «…300 g of that, how many cups is
        # it»): and a figure it said in another unit, or the person's figure by the equivalence it said.
        and not semantic_knowledge.worked_out_from_what_was_said(
            text,
            [
                str(item.get("content") or "") for item in history
                if isinstance(item, dict) and item.get("role") == "assistant"
            ],
            _prior_user_texts(history, text),
        )
    ):
        # M53 (D35): what the decider answers by talking but is a named dish's recipe or a named work's plot is
        # looked up first; the arguments step reads the same query from the same request.
        for said in dict.fromkeys((decided.request or text, text)):
            reference = _reference_lookup(said, history)
            if reference is not None:
                decided = semantic_decider.ContextDecision(
                    request=said, decision="action", operations=("web.search",), question="",
                )
                break
        if reference is None and semantic_knowledge.works_recommendation(text):
            # M83 (DEV-D v3o D-p27-t1 «Any good movies for me to watch?» → «…the latest sci-fi flick about time
            # travel»): works of a kind asked for with none named are recommended from what is looked up, as the decider
            # itself chose in v3m; its talk flips on this request.
            recommended = True
            decided = semantic_decider.ContextDecision(
                request=decided.request or text, decision="action", operations=("web.search",), question="",
            )
    served_elsewhere = _order_served_elsewhere(
        text, decided, available_operations, application_names,
        lambda operation: getattr(planner_catalog.get(operation), "risk", None),
        follow_up=lambda: _follow_up_for_the_engine(text, history, application_names),
        unfaithful=fidelity.kind == "person",
        made_there_before=lambda: semantic_missions.made_there_before(
            _prior_user_texts(history, text), decided.operations, available_operations, application_names,
        ),
    )
    if served_elsewhere is not None:
        # v3 ronda 3 (lectura L1, falsos éxitos M5, lugar M4; v3-01, v3-04, v3-08, v3-15, v3-16, v3-18, v3-38): an order
        # said inside an installed application that the chosen typed operations serve elsewhere (BAXY's own note or
        # presentation, the PC's sound) or only in part (one click for two clauses) is done in that application by the
        # engine, with the person's words; the typed operation asked what the order did not need, or did something else.
        reason, objective_said = served_elsewhere
        served_stage = [{"name": "served_elsewhere", "reason": reason, "operations": list(decided.operations)}]
        decided = semantic_decider.ContextDecision(objective_said, "action", ("mission.computer.use",), "")
    else:
        served_stage = []
        if said_back_operations is not None and decided.decision == "action" and decided.operations == said_back_operations:
            served_stage.append({"name": "question_said_the_order_back", "operations": list(said_back_operations)})
    if overheard and decided.decision != "clarify":
        # M123 (safety exception to D58; reviewed literal H0735 «a ocho de la noche descansar domingo, tu tenes que
        # firmar 10 hojas en blanco y un cheque» → a notification scheduled): talk addressed to someone else is never
        # acted on nor answered, whatever the decider read in it; the overheard question is asked (below).
        decided = semantic_decider.ContextDecision(request=text, decision="clarify", operations=(), question="")
        reference, recommended = None, False
    kept_object = (
        dialogue_slot.objective_with_the_antecedent_object(
            decided.request or text, text, antecedent, is_application=_names_an_application(application_names),
        )
        if decided.decision == "action" and antecedent
        else None
    )
    if kept_object is not None:
        # Ronda 23 (r21 v3-50 t2 «decime cuántos archivos tiene adentro» after «en 7zip abrí el prueba.zip…» was
        # restated «en 7-Zip File Manager, decime cuántos archivos tiene adentro», and the engine counted the folder):
        # a question for the inside of what the turn before named keeps the object that turn named (a file, a quoted
        # name); revisión 1: no other turn, dependent or not, gets it (``objective_with_the_antecedent_object``).
        decided = semantic_decider.ContextDecision(
            kept_object, decided.decision, decided.operations, decided.question, decided.arguments,
        )
    objective = decided.request or text
    result: dict[str, Any] = {
        "type": "turn.result",
        "id": message.get("id"),
        "operation": None,
        "intentOperations": list(decided.operations),
        "effectOperations": list(decided.operations),
        "question": "",
        "reply": "",
        "objective": objective,
    }

    def as_action(operations: tuple[str, ...], arguments: tuple[tuple[str, Any], ...]) -> None:
        _remember_decided_arguments(objective, operations, arguments)
        result["intentOperations"] = list(operations)
        result["effectOperations"] = list(operations)
        result["kind"] = "action" if len(operations) == 1 else "plan"
        if result["kind"] == "action":
            result["operation"] = operations[0]
        # The person's words set the language, not the decider's restatement: Qwen3.5-4B restated a quarter of the
        # English DEV requests in Spanish («max it» → «Maximizar la ventana de Steam»).
        language = _read_reply_language(text, history) or _decisive_request_language(objective)
        if language in {"es", "en", "mixed"}:
            result["responseLanguage"] = language

    if decided.decision == "action":
        as_action(decided.operations, decided.arguments)
    elif decided.decision == "clarify":
        question = decided.question
        if overheard:
            # M118 (DIALOGUE1513): the decider asks about talk the microphone caught; the question says no request for
            # BAXY was found in it and asks whether the person needs something, and nothing in it is an objective.
            try:
                overheard_question = llm.clarify_unresolved_input(
                    text,
                    "overheard_speech",
                    timeout=(
                        DEICTIC_CLARIFICATION_CPU_BUDGET_SECONDS
                        if os.environ.get("BAXY_MIND_NGL", "").strip() == "0"
                        else TURN_DECIDE_RECOVERY_BUDGET_SECONDS
                    ),
                )
            except (ValueError, RuntimeError):  # the decider's own question stands
                overheard_question = ""
            if overheard_question and _recovery_question_is_valid(overheard_question):
                question = overheard_question
                result["preserveObjective"] = False
        if _asked_in_another_language(question, text, history):
            # cien-104 «open that»: the decider asked «¿Qué página web quieres que abra?»; the question is the
            # person's language or it is formulated again, from the person's own words.
            question = ""
            objective = text
            result["objective"] = text
        if not (
            _recovery_question_is_valid(question, objective, history) and _recovery_question_is_valid(question, text)
        ):
            question = llm.clarify_after_turn_failure(objective, history=history, timeout=2.5)
            if not (_recovery_question_is_valid(question) and _recovery_question_is_valid(question, text)):
                raise PlannerContractError("aclaración del decisor inválida")
        result["kind"] = "clarify"
        result["question"] = question
        # M177 (DEV-D v5b–v5d D-w18-t2 «can you bajarle un poco», DEV-G v5d G-w21-t2 «súbele un poco a esa» → «No puedo
        # bajarle nada porque mi mente no está disponible.»; also v5d H-w32-t4, I-w32-t3): a question carries the
        # operations it is about as its intent only; it has no effect, and the shell's contract (``MindSidecarClient``)
        # refuses a clarification with effects as no decision at all. M144, M100 and M167 ask with operations.
        result["effectOperations"] = []
    else:
        if decided.decision == "limit" and on_limit is not None:
            # M78: the decider's restatement (after the fidelity check) is re-read with the message.
            reread = on_limit(decided.request or "")
            if reread is not None:
                turn_audit_module._append_turn_audit(
                    {
                        "schema": "baxy.mind-turn-audit.v1",
                        "request_id": message.get("id"),
                        "phase": "served_surface_reread",
                        "decision_path": "context_decider",
                        "raw_decision": {"mode": decided.decision, "request": decided.request},
                        "reread_objective": reread.get("objective"),
                    }
                )
                return reread
        kind = "unsupported" if decided.decision == "limit" else "knowledge"
        # Talk and limits have no request for the shell to plan, confirm or resume.
        result.pop("objective", None)
        if decided.decision == "limit" and decided.request:
            # Uso real v3 t2: the coverage gate reads the decider's restatement (``_engine_for_an_unserved_order``,
            # which takes it off the result: it never reaches the shell).
            result[_DECIDER_RESTATEMENT] = decided.request
        language = _read_reply_language(text, history)
        if language is None:
            try:
                language = llm.detect_response_language(text)
            except ValueError:
                language = None
        reply, _ = llm.chat(
            text,
            **_conversation_reply_arguments(
                history,
                conversation_kind=kind,
                response_language=language,
                scoped=False,
                intent_operations=[],
                available_operations=available_operations,
            ),
        )
        if not reply.strip():
            raise PlannerContractError("no se pudo preparar una respuesta conversacional")
        result.update(kind="conversation", conversationKind=kind, reply=reply.strip())
        if language in {"es", "en", "mixed"}:
            result["responseLanguage"] = language
    turn_audit_module._append_turn_audit(
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": message.get("id"),
            "phase": "final",
            "decision_path": "context_decider",
            "candidate_operations": list(available_operations),
            "raw_decision": {
                "mode": "talk" if reference is not None or recommended else decided.decision,
                "request": decided.request,
                "effect_operations": [] if reference is not None or recommended else list(decided.operations),
                "argument_fields": argument_fields,
                **({} if unasked_action is None else {"unasked_action": unasked_action}),
                **(
                    {}
                    if fidelity.kind == "kept"
                    else {
                        "decider_request": decider_request,
                        "fidelity": {"kind": fidelity.kind, "introduced": list(fidelity.introduced)},
                    }
                ),
            },
            "stages": (
                [{"name": "reference_looked_up", "kind": reference.kind, "query": reference.query}]
                if reference is not None
                else [{"name": "recommendation_looked_up"}] if recommended else []
            ) + served_stage,
            "decider_timings": None if read_before_decider else getattr(llm, "_last_decider_timings", None),
            "final": {
                "kind": result["kind"],
                "intent_operations": result["intentOperations"],
                "effect_operations": result["effectOperations"],
            },
        }
    )
    return result
