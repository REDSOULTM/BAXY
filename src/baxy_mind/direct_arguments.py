"""The ``arguments`` request: one operation's grounded arguments, or the question for what is still missing.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from . import effect_intent
from .semantic import dialogue as dialogue_slot
from .semantic.notes import conversation_note_title, note_content_unsaid, task_change
from .semantic import arguments as semantic_arguments
from .semantic import temporal as semantic_temporal
from .semantic.patterns import said_music_query
from .semantic.web import place_fixed_by_conversation, place_query_in_conversation
from .effect_intent import ApplicationCatalogIndex, GameCatalogIndex, conversation_only_content_request
from .planner import validate_json_schema_instance
from .semantic.request import fold as read_fold
from .semantic.arguments import (
    _canonical_due_utc,
    conversation_pdf,
    conversation_text_file,
    corrected_song_title,
    partial_explicit_arguments,
)
from .turn_history import (
    _conversation_grounding_source,
    _person_message,
    _previous_reply,
    _previous_reply_may_be_content,
    _prior_user_texts,
)
from .argument_grounding import (
    _ground_explicit_arguments,
    _said_optional_arguments,
    _stated_argument_fields,
    prepare_direct_argument_result,
)
from .decided_arguments import (
    _as_the_person_spelled,
    _decided_arguments_alone,
    _decided_reply_field,
    _pointed_note_content,
    _REMINDER_OPERATIONS,
    _with_decided_arguments,
    _with_decided_part_of_day,
    _with_decided_restatements,
    _with_decider_values_kept,
    _with_every_known_folder_unsaid,
    _with_pointed_reminder_title,
)


def _with_session_alarm_selector(objective: str, history: object) -> str:
    """REOPEN1993 H0011: «cancelá la alarma» after this conversation set exactly
    one alarm reads as the latest-alarm cancellation; otherwise the text stays
    and the readers ask which alarm."""

    if not isinstance(history, list):
        return objective
    previous = history
    if previous and isinstance(previous[-1], dict) and previous[-1].get("role") == "user" and previous[-1].get("content") == objective:
        previous = previous[:-1]
    requests = [
        str(item.get("content") or "")
        for item in reversed(previous)
        if isinstance(item, dict) and item.get("role") == "user"
    ]
    rewritten = effect_intent.session_single_alarm_rewrite(objective, requests)
    return rewritten if rewritten is not None else objective


def _unschedulable_time_question(
    llm: object,
    operation: str,
    objective: str,
    person: str,
    tool: dict,
    response_language: str | None,
    *,
    now: datetime | None = None,
) -> str:
    """M80 (DEV-D v3m D-s104 «Programa una alarma nueva para la cena a las 18:00 hoy.» at 19:35 → «¿Cuál es la hora
    exacta, qué tipo de recordatorio y qué título…?»; D-s108 «Set a 'wake-up' alarm for Monday, Tuesday and Wednesday of
    this week for 7am» on a Tuesday → «What time… and what should the title be?»): the time, the kind and what it is for
    were said; one notification cannot ring at that moment (today's clock already past, several days). Only when it
    rings is asked, saying why. Empty when the moment said is one a notification holds."""

    if operation not in {"notification.schedule", "reminder.create"}:
        return ""
    now = now or datetime.now().astimezone()
    unschedulable = next(
        (found for text in dict.fromkeys((objective, person))
         if (found := semantic_temporal.unschedulable_time(text, now)) is not None),
        None,
    )
    if unschedulable is None:
        return ""
    clock = unschedulable.clock
    if not unschedulable.ahead and len(unschedulable.passed) == 1:
        ask = (
            f"only when it should ring instead: the {clock} of {unschedulable.passed[0]} the person asked for already "
            f"passed (it is {now:%H:%M} now); say that first, then ask for another day or another time; "
            "the time, the kind and what it is for were already said, never ask them"
        )
    else:
        days = ", ".join((*unschedulable.passed, *unschedulable.ahead))
        passed = (
            f"; {', '.join(unschedulable.passed)} of this week already passed (it is {now:%A %H:%M} now)"
            if unschedulable.passed else ""
        )
        ask = (
            f"only which one day it should ring: one alarm or reminder rings at a single moment and the person named "
            f"several days ({days}) at {clock}{passed}; say that first; the time, the kind and what it is for were "
            "already said, never ask them"
        )
    language = {"response_language": response_language} if response_language else {}
    question = llm.formulate_missing_argument_question(objective, "", tool, ("dueUtc",), **language, ask_as={"dueUtc": ask})
    several = bool(unschedulable.ahead) or len(unschedulable.passed) != 1
    if question and not _says_why_unschedulable(question, several=several):
        # M93 (DEV-D v3u D-s104 at 19:23 → «¿A qué día o hora diferente te gustaría que suene la alarma?»): the question
        # did not say that 18:00 had passed, and «diferente» of what was never said. Asked again once, told so.
        retried = llm.formulate_missing_argument_question(
            objective, "", tool, ("dueUtc",), **language,
            ask_as={"dueUtc": f"{ask}. Your question «{question}» did not say why: open with that short reason, "
                              "then ask"},
        )
        if retried:
            question = retried
    return question


# M93: a question about when that says why the moment said cannot hold (folded).
_UNSCHEDULABLE_PASSED = (
    r"\bya\s+pas\w*|\bpas(?:o|aron|ado|ada|ados|adas)\b|\balready\b|\bpassed\b|\bis\s+(?:past|over|gone)\b|"
    r"\bhas\s+gone\b|\bearlier\s+than\s+now\b"
)
_UNSCHEDULABLE_SEVERAL = (
    r"\bvari[oa]s\s+dias\b|\bmas\s+de\s+un\s+dia\b|\bun\s+solo\b|\bsolo\s+(?:un|una|puede)\b|\bsolo\s+suena\b|"
    r"\bseveral\s+days\b|\bmore\s+than\s+one\s+day\b|\bsingle\b|\bonly\s+(?:one|once|rings)\b|\bone\s+(?:day|time|moment)\b"
)


def _says_why_unschedulable(question: str, *, several: bool) -> bool:
    folded = read_fold(question)
    pattern = _UNSCHEDULABLE_PASSED + ("|" + _UNSCHEDULABLE_SEVERAL if several else "")
    return re.search(pattern, folded) is not None


_TASK_CHANGE_FIELDS = ("title", "details", "due")


def _edited_task_arguments(
    llm: object,
    objective: str,
    person: str,
    tool: dict,
    edited: dict[str, object],
    said: str,
    response_language: str | None,
) -> tuple[dict | None, str]:
    """M80 (DEV-D v3m D-p06-t2, D-p06-t3 «Change that from bacon to eggs.» → «Which task…?», D-p08-t3 «No, cámbialo
    a la lista Comida» → «¿Cuál es el título de la tarea y cuál es la fecha límite?»): task.update replaces every
    editable field, so a change of the task this conversation just made or changed takes its identity, its version
    and every field the person did not change from what the store verified (``DialogueState.edited_task``); only what
    changes is read from what was said (the readers first, else the model, each value grounded in what was said).
    (None, "") when nothing here decides it; (None, question) asks what to change."""

    schema = tool["function"]["parameters"]
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    changes: dict[str, object] = {}
    for text in dict.fromkeys((person, objective)):
        changes = dict(task_change(text, str(edited["title"])))
        if changes:
            break
    if not changes:
        changes_schema = {
            "type": "object",
            "properties": {name: properties[name] for name in _TASK_CHANGE_FIELDS if name in properties},
            "required": [],
            "additionalProperties": False,
        }
        changes_tool = {"type": "function", "function": {**tool["function"], "parameters": changes_schema}}
        extraction = llm.extract_direct_arguments(
            objective, changes_tool, **({"response_language": response_language} if response_language else {}),
        )
        changes = _said_optional_arguments(extraction.arguments, changes_schema, said)
    if isinstance(changes.get("due"), str):
        # M115: a day said with no clock is the task's day, as the store reads it.
        due = _canonical_due_utc(str(changes["due"]), objective) or semantic_temporal.task_due_date(str(changes["due"]))
        if due is None:
            changes.pop("due")
        else:
            changes["due"] = due
    changes = {name: value for name, value in changes.items() if value != edited.get(name)}
    if not changes:
        return None, llm.formulate_missing_argument_question(
            objective, "", tool, ("title",),
            **({"response_language": response_language} if response_language else {}),
            ask_as={"title": (
                f"only what to change in «{edited['title']}» (its name or the list it is on); the task is the one "
                "just made, never ask which one"
            )},
        )
    arguments = {name: edited[name] for name in ("taskId", "expectedVersion", *_TASK_CHANGE_FIELDS)} | changes
    return (arguments, "") if validate_json_schema_instance(arguments, schema) else (None, "")


def _with_conversation_place(
    operation: str, arguments: object, history: object, schema: dict[str, object],
) -> object:
    """M58 (v3d-final F-p05-t3, F-p06-t3): a place named alone in a place search or a weather read carries the town
    the conversation already fixed for it (``semantic.web.place_fixed_by_conversation``); what the message names with
    its own town, or anything else, is left as it came."""

    if not isinstance(arguments, dict) or not isinstance(history, list):
        return arguments
    # The last message of the person is this turn's own; the town comes from the ones before it.
    said_before = [
        str(item.get("content") or "") for item in reversed(history)
        if isinstance(item, dict) and item.get("role") == "user"
    ][1:]
    placed = dict(arguments)
    if operation == "web.search" and isinstance(arguments.get("query"), str) and not arguments.get("nearby"):
        query = place_query_in_conversation(arguments["query"], said_before)
        if query is None:
            return arguments
        placed["query"] = query
    elif operation == "weather.current" and isinstance(arguments.get("location"), str):
        town = place_fixed_by_conversation(arguments["location"], said_before)
        if town is None:
            return arguments
        placed["location"] = f"{arguments['location']}, {town}"
    else:
        return arguments
    return placed if validate_json_schema_instance(placed, schema) else arguments


def _direct_arguments_result(
    message: dict[str, Any],
    *,
    llm: Any,
    tool: dict,
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
    dialogue_state: dialogue_slot.DialogueState,
) -> tuple[dict[str, Any] | None, str]:
    """The «arguments» request: the operation's grounded arguments, or None with the question for what is missing."""

    operation = str(message.get("operation", ""))
    objective = _with_session_alarm_selector(
        str(message.get("text", "")), message.get("history"),
    )
    arguments = _ground_explicit_arguments(
        operation,
        objective,
        tool["function"]["parameters"],
        application_names,
        game_catalog,
        history=message.get("history"),
    )
    question = ""
    said = _conversation_grounding_source(objective, message.get("history"))
    # M118 (D58): what the decider wrote in other words of what was said is said, and what it gave is never replaced by
    # the readers' reading of the same field.
    said = _with_decided_restatements(
        operation, str(message.get("text", "")), tool["function"]["parameters"], said,
    )
    said = _with_every_known_folder_unsaid(operation, tool["function"]["parameters"], said)
    if arguments is not None:
        arguments = _with_decider_values_kept(
            operation, str(message.get("text", "")), arguments, tool["function"]["parameters"], said,
        )
    turn_language = (
        message.get("responseLanguage") if message.get("responseLanguage") in {"es", "en", "mixed"} else None
    )
    person = _person_message(message.get("history"), objective)
    headline = dialogue_state.pointed_headline(person) if operation == "web.search" else None
    if headline is not None and validate_json_schema_instance(
        {"query": headline}, tool["function"]["parameters"],
    ):
        # M83 (DEV-D v3o D-w17-t5 «tell me more about the second one»): the headline pointed at by its
        # place in the news just read is looked up as it was written, never as the decider retold it.
        arguments = {"query": headline}
    if arguments is None:
        # M80 (DEV-D v3m D-s104, D-s108): a moment no notification holds asks only when, saying why.
        question = _unschedulable_time_question(
            llm, operation, objective, person, tool, turn_language,
        )
    if arguments is None and not question and operation == "message.draft":
        # M111 («mándaselo a Ana», «déjaselo escrito a Álvaro por WhatsApp»): the words are those of the message
        # written before in this conversation (the person's last draft, or BAXY's reply the person asked to write);
        # who it goes to is this message's.
        earlier = list(_prior_user_texts(message.get("history"), person))
        forwarded = effect_intent.forwarded_draft(
            person,
            earlier,
            _previous_reply(message.get("history")),
            bool(earlier) and (
                conversation_only_content_request(earlier[-1]) or effect_intent.asks_to_write_a_message(earlier[-1])
            ),
        )
        if forwarded is not None:
            candidate = {"channel": forwarded[0], "recipient": forwarded[1], "text": forwarded[2]}
            if validate_json_schema_instance(candidate, tool["function"]["parameters"]):
                arguments = candidate
    edited = (
        # M174 (DEV-H v5c H-w04-t3 «espera, el jamón no, mejor queso» after «apunta ahí pan, leche y jamón» → the list's
        # own task «Lista para la compra del finde» changed): the entry the change names by its old name is the task
        # changed; else the one this conversation last made or changed (M80).
        dialogue_state.changed_entry(person, objective) or dialogue_state.edited_task()
        if operation == "task.update"
        else None
    )
    if arguments is None and not question and edited is not None:
        # M80 (DEV-D v3m D-p06-t2, D-p06-t3, D-p08-t3): what was not changed is kept from the verified task.
        arguments, question = _edited_task_arguments(
            llm, objective, person, tool, edited, said, turn_language,
        )
    # M141 (DEV-G v4o G-w06-t3 «guárdalo en un archivo que se llame suma.py» → «¿Cuál es el código…?»): when the
    # decider wrote BAXY's last reply (its code) as the content, that reply is the content verbatim and is said.
    last_reply = _previous_reply(message.get("history"))
    reply_written = (
        last_reply
        if _decided_reply_field(operation, str(message.get("text", "")), tool["function"]["parameters"], last_reply)
        else None
    )
    if reply_written is not None:
        said = f"{said}\n{reply_written}"
    # M160 (DEV-H v4w H-w11-t3 «save that whole thing as a note called banana bread» after the recipe and a temperature
    # → «What content should be saved…?»; DEV-F v4w F-w34-t3 «Guárdamela en una nota que se llame tortilla» → the
    # decider's «receta … para cuatro personas»): the note keeps BAXY's words the person points at, verbatim, when
    # they are not its last reply alone; with no title known, the extraction reads them in the last reply's place.
    pointed = None
    if not question:
        pointed = _pointed_note_content(
            operation, str(message.get("text", "")), person, message.get("history"), tool["function"]["parameters"],
            said, arguments,
        )
    if pointed is not None:
        said = f"{said}\n{pointed[0]}"
        candidate = {"title": pointed[1], "content": pointed[0]}
        if pointed[1] is not None and validate_json_schema_instance(candidate, tool["function"]["parameters"]):
            arguments = candidate
        else:
            arguments = None
    if arguments is None and not question and pointed is None and (
        reply_written is not None or not _previous_reply_may_be_content(tool, message.get("history"))
    ):
        # M42b: what the decider read, grounded in what was said, is enough on its own; the separate
        # extraction call runs only when a required value is still missing.
        arguments = _decided_arguments_alone(
            operation, str(message.get("text", "")), tool, said, previous_reply=reply_written,
        )
    if arguments is None and not question and operation in {"document.pdf.read", "document.text.read"}:
        # M127 (DEV-C v4i C-w10-t4): the PDF named by its file name earlier in the conversation is read where that
        # conversation said it is, never asked again. M151: a text file too.
        named = (conversation_pdf if operation == "document.pdf.read" else conversation_text_file)(
            objective,
            [str(item.get("content") or "") for item in message.get("history") or [] if isinstance(item, dict)],
        )
        if named is not None and validate_json_schema_instance(named, tool["function"]["parameters"]):
            arguments = named
    if arguments is None and not question:
        # M47 (FINAL F-w09-t5, F-p02-t3): the shell sends the language the turn decision chose; the
        # objective may be the decider's restatement in the other language, so it cannot decide it.
        response_language = message.get("responseLanguage")
        language_argument = (
            {"response_language": response_language}
            if response_language in {"es", "en", "mixed"}
            else {}
        )
        # M67 (FINAL F-w14-t3 «perfect, copialo al clipboard» after a ```sql answer, F-w15-t4 «save that
        # as a note porfa» after a packing list): the model reads BAXY's last reply beside the objective
        # and says whether it is the content; code copies it verbatim into that field.
        previous_reply = pointed[0] if pointed is not None else _previous_reply(message.get("history"))
        extraction = llm.extract_direct_arguments(
            objective,
            tool,
            stated_fields=_stated_argument_fields(
                operation, objective, tool["function"]["parameters"],
            ),
            **language_argument,
            **({"previous_reply": previous_reply} if previous_reply else {}),
        )
        if extraction.previous_reply_field and previous_reply:
            # The reply is literally what BAXY said (M43's trusted source), whole and not cut.
            objective_source = f"{objective}\n{previous_reply}"
            said = f"{said}\n{previous_reply}"
        else:
            objective_source = objective
        extracted = extraction.arguments
        if extracted is None:
            # M76 (DEV-D v3l D-p19-t1): an abstention keeps what the readers know, so what is asked is
            # only what is still missing (the service of a film named by its title).
            extracted = partial_explicit_arguments(
                operation, objective, tool["function"]["parameters"],
            ) or None
        if extracted is None and operation == "media.play.query" and said_music_query(objective) is not None:
            # M176: an abstention on music named in words no reader grounds keeps the words it was named with (below).
            extracted = {"provider": "spotify", "query": said_music_query(objective)}
        decided_arguments = _with_decided_arguments(
            operation,
            str(message.get("text", "")),
            extracted,
            tool["function"]["parameters"],
            said,
            previous_reply=reply_written,
        )
        arguments, question = prepare_direct_argument_result(
            llm,
            objective,
            tool,
            extracted if decided_arguments is None else decided_arguments,
            # A question written before the decider's values were added may ask for one of them.
            extraction.fallback_question if decided_arguments is None else "",
            trusted_source=objective_source if decided_arguments is None else said,
            **language_argument,
        )
    if arguments is None and operation == "media.play.query":
        # M176 (probe «pon música clásica para concentrarme», «play jazz for dinner», «play the beatles» → «¿Qué quieres
        # escuchar?»): the readers chose the search for music named in words no reader grounds, and the extraction gave
        # nothing that grounds either (an abstention takes them above, before any question is written); the words the
        # person named it with are the query. A value the extraction grounded stays (D58).
        named = said_music_query(person) or said_music_query(objective)
        candidate = {"provider": "spotify", "query": named}
        if named is not None and validate_json_schema_instance(candidate, tool["function"]["parameters"]):
            arguments, question = candidate, ""
    arguments = _with_conversation_place(
        operation, arguments, message.get("history"), tool["function"]["parameters"],
    )
    arguments = _with_decided_part_of_day(operation, str(message.get("text", "")), arguments)
    arguments = _with_pointed_reminder_title(operation, person, message.get("history"), arguments)
    if (
        operation in _REMINDER_OPERATIONS
        and isinstance(arguments, dict)
        and isinstance(arguments.get("title"), str)
        and dialogue_slot.pointed_reminder_unsaid(person, _previous_reply(message.get("history")), arguments["title"])
    ):
        # M165 (DEV-F v4y F-w48-t4 «órale, pues recuérdame eso el domingo a las 3 de la tarde» after a forecast that
        # failed, so it advised nothing → titled «Recuérdame el domingo a las 3 de la tarde.»): what «eso» points at is
        # not in the conversation, and the order repeated is no title; what to remind is asked.
        arguments = None
        question = llm.formulate_missing_argument_question(
            objective, "", tool, ("title",), **({"response_language": turn_language} if turn_language else {}),
        )
    if operation in {"note.read", "note.trash"} and not (isinstance(arguments, dict) and arguments.get("noteId")):
        # M111 (DEV-F v4d F-w03-t6 «la nota del snippet, léemela» → note «Snippet» not found): a note named by a word
        # of the title it was given earlier in the conversation is that note.
        conversation = [
            str(item.get("content") or "") for item in message.get("history") or [] if isinstance(item, dict)
        ]
        titled = conversation_note_title(objective, conversation) or conversation_note_title(
            person, conversation,
        )
        candidate = {**(arguments if isinstance(arguments, dict) else {}), "title": titled}
        if titled is not None and validate_json_schema_instance(candidate, tool["function"]["parameters"]):
            arguments, question = candidate, ""
    if operation == "media.play.exact":
        arguments, question = _corrected_song_arguments(person, message.get("history"), arguments, question, tool)
    arguments = _as_the_person_spelled(operation, arguments, person, message.get("history"))
    if (
        operation == "note.create"
        and isinstance(arguments, dict)
        and note_content_unsaid(person, str(arguments.get("content") or ""))
    ):
        # M157 (M81; DEV-I v4v I-w37-t3 «oye, de paso, crea una nota de la junta de hoy» → content «Junta de hoy.», the
        # title again): a note the person named only by what it is about gets that as its title, and what it says is
        # asked, whoever wrote the title into the content (the decider, the extraction).
        arguments, question = None, llm.formulate_missing_argument_question(
            objective, "", tool, ("content",), **({"response_language": turn_language} if turn_language else {}),
        )
    if operation == "browser.navigate" and arguments is None and dialogue_slot.asks_to_search(person):
        # Ronda 24, revisión 2 (r23 t3-c17 t4 «buscalo en google pa poder citarlo» → «¿Cuál es la URL exacta que deseas
        # visitar?»): a search verb never asks for an address; what is missing is what to look up (the address is the
        # search's).
        question = llm.formulate_missing_argument_question(
            objective, "", tool, ("url",), **({"response_language": turn_language} if turn_language else {}),
            ask_as={"url": "only what to look up: the person asked for a search, whose address is built from it; never "
                           "ask for a web address, a URL, a link or a site"},
        )
    if operation == "app.open" and isinstance(arguments, dict):
        # Review of cu-v3-documento-nuevo (finding 8): a lone opening («abre un excel en blanco») carries the new
        # document the person asked for as the plan's openings do.
        arguments = semantic_arguments.with_new_document(arguments, (person,), application_names)
    return arguments, question


def _corrected_song_arguments(
    person: str, history: object, arguments: dict[str, Any] | None, question: str, tool: dict,
) -> tuple[dict[str, Any] | None, str]:
    """M127 (D58; DEV-F v4i F-w36-t2, F-w60-t2): «la otra, la de estudio / la del disco» plays the song the person asked
    for just before (``semantic.arguments.corrected_song_title``); a title that is part of that song, or holds it, is
    the model's and stays."""

    earlier = _prior_user_texts(history, person)
    song = corrected_song_title(person, earlier[-1], _previous_reply(history) or "") if earlier else None
    if song is None:
        return arguments, question
    title = arguments.get("title") if isinstance(arguments, dict) else None
    if isinstance(title, str) and title.strip():
        said, kept = effect_intent._fold(song), effect_intent._fold(title)
        if kept in said or said in kept:
            return arguments, question
    candidate = {**(arguments if isinstance(arguments, dict) else {}), "provider": "spotify", "title": song}
    if not validate_json_schema_instance(candidate, tool["function"]["parameters"]):
        return arguments, question
    return candidate, ""
