"""Arguments of an operation grounded in what the person said: the literal reading of the request, the closed
constraints the catalog's JSON Schema cannot express, and the question for a required field that is missing.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from typing import Any

from . import effect_intent
from .semantic import knowledge as semantic_knowledge
from .semantic import levels as semantic_levels
from .semantic import captures as semantic_captures
from .semantic import missions as semantic_missions
from .semantic import memory as semantic_memory
from .semantic import reading as semantic_reading
from .semantic import temporal as semantic_temporal
from .semantic.system import names_this_place, weather_destination_there
from .semantic.patterns import output_level_request
from .semantic.web import near_the_person, news_lookup_query
from .semantic.windows import start_menu_request
from .effect_intent import ApplicationCatalogIndex, GameCatalogIndex
from .planner import (
    PlannerContractError,
    fixed_arguments,
    normalize_grounded_arguments,
    validate_argument_grounding,
    validate_json_schema_instance,
)
from .semantic.dialogue import _previous_user_request
from .semantic.arguments import (
    _canonical_due_utc,
    _explicit_arguments_from_evidence,
    due_before_said_moment,
    literal_ocr_language,
    literal_vision_prompt,
    partial_explicit_arguments,
    reminder_title_without_que,
)
from .turn_history import _person_message, _prior_user_requests, _prior_user_texts


_ARGUMENT_FIELD_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")


def unresolved_argument_fields(
    arguments: object,
    schema: object,
    trusted_source: str,
) -> tuple[str, ...]:
    """Locate unresolved required fields from the authenticated JSON Schema.

    This is called only after whole-object grounding failed. Each required
    field is rechecked independently against the same schema and trusted user
    text, so the clarification layer never guesses from an operation name.
    """

    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise PlannerContractError("schema de argumentos no canónico")
    properties = schema.get("properties")
    required = schema.get("required")
    if (
        not isinstance(properties, dict)
        or not isinstance(required, list)
        or not 1 <= len(required) <= 64
        or len(set(required)) != len(required)
        or any(
            not isinstance(name, str)
            or _ARGUMENT_FIELD_NAME.fullmatch(name) is None
            or name not in properties
            for name in required
        )
    ):
        raise PlannerContractError(
            "el schema no identifica argumentos requeridos aclarables"
        )

    unresolved: list[str] = []
    for name in required:
        if not isinstance(arguments, dict) or name not in arguments:
            unresolved.append(name)
            continue
        field_schema = {
            "type": "object",
            "properties": {name: properties[name]},
            "required": [name],
            "additionalProperties": False,
        }
        if not validate_argument_grounding(
            {name: arguments[name]},
            field_schema,
            trusted_source,
        ):
            unresolved.append(name)
    if not unresolved:
        raise PlannerContractError(
            "el fallo de argumentos no corresponde a un dato requerido"
        )
    return tuple(unresolved)


def normalize_objective_arguments(
    arguments: object,
    schema: object,
    objective: str,
) -> tuple[dict | None, tuple[str, ...]]:
    """Ground extracted literals only against the authenticated user objective."""

    grounded = normalize_grounded_arguments(arguments, schema, objective)
    if grounded is not None:
        return grounded, ()
    return None, unresolved_argument_fields(arguments, schema, objective)


def _said_optional_arguments(arguments: object, schema: dict, trusted_source: str) -> dict:
    """The optional fields of ``arguments`` each grounded in what was said, alone (M76); none when there are none."""

    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    kept: dict = {}
    for name, value in (arguments.items() if isinstance(arguments, dict) else ()):
        contract = properties.get(name)
        if not isinstance(contract, dict):
            continue
        field_schema = {"type": "object", "properties": {name: contract}, "required": [name], "additionalProperties": False}
        if validate_argument_grounding({name: value}, field_schema, trusted_source):
            kept[name] = value
    return kept


def prepare_direct_argument_result(
    llm: object,
    objective: str,
    tool: dict,
    arguments: object,
    fallback_question: str = "",
    response_language: str | None = None,
    *,
    trusted_source: str | None = None,
) -> tuple[dict | None, str]:
    """Return only grounded arguments or one schema-grounded clarification.

    ``response_language`` is the turn's language decided upstream (M47); the question is formulated in it rather
    than in the objective's. ``trusted_source`` widens the evidence to what the person and BAXY said in the
    conversation (M43) when the values came from the decider, which read it; the question still asks from the
    objective.
    """

    schema = tool["function"]["parameters"]
    if isinstance(arguments, dict) or arguments is None:
        # Estabilización M2: what the contract fixes is filled, never asked (``fixed_arguments``).
        arguments = {**fixed_arguments(schema), **(arguments or {})}
    if not schema.get("required"):
        # M76 (DEV-D v3l D-s014, D-s054, D-s080: the weather asked «¿En qué ciudad…?»): with every field optional
        # there is nothing to ask. A value the person did not say (a town the model brought, this PC's own) is left
        # out and the operation's default applies; what was said is kept.
        arguments = _said_optional_arguments(
            arguments, schema, objective if trusted_source is None else trusted_source,
        )
    grounded, fields = normalize_objective_arguments(
        arguments,
        schema,
        objective if trusted_source is None else trusted_source,
    )
    if grounded is not None:
        operation = str(tool["function"].get("canonical_name") or "")
        normalized = _normalize_grounded_operation_arguments(
            operation,
            grounded,
            objective,
        )
        if normalized is not None:
            return normalized, ""
        fields = ("dueUtc",) if "dueUtc" in schema.get("required", []) else fields
    if fallback_question:
        return None, fallback_question
    question = llm.formulate_missing_argument_question(
        objective,
        "",
        tool,
        fields,
        **({"response_language": response_language} if response_language else {}),
    )
    return None, question


def trusted_plan_grounding_source(
    objective: str,
    observations: object,
) -> str:
    """Build provenance from user text and verified dependency observations.

    A plan step's ``purpose`` is model-authored guidance. It is deliberately
    absent from this interface so it can never launder an invented argument
    into trusted textual evidence.
    """

    return (
        objective
        + "\n"
        + json.dumps(
            observations,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


def _window_query_reference_name(
    objective: str,
    history: object,
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
) -> str | None:
    """Read the same bounded user reference during selection and grounding."""
    if not isinstance(history, list):
        return None
    previous = history[-12:]
    if (
        previous
        and isinstance(previous[-1], dict)
        and previous[-1].get("role") == "user"
        and previous[-1].get("content") == objective
    ):
        previous = previous[:-1]
    requests = [
        str(item.get("content") or "")
        for item in previous
        if isinstance(item, dict) and item.get("role") == "user"
    ]
    return effect_intent.resolve_application_window_followup_name(
        objective, requests, application_names,
    )


_OUTPUT_LEVEL_OPERATIONS = ("audio.volume", "audio.volume.adjust", "system.settings.adjust", "system.settings.set")


def _stated_argument_fields(operation: str, objective: str, schema: dict[str, object]) -> tuple[str, ...]:
    """Required fields the request already settles, so the question for the rest never asks them again.

    Tanda 3: a brightness lowered «un nivel» was asked «¿Cuánto y en qué dirección…?»:
    the direction was said. A field with one allowed value is settled by the operation itself, and the
    direction of a level change by the words that raise or lower it.
    """

    properties = schema.get("properties")
    required = schema.get("required")
    if not isinstance(properties, dict) or not isinstance(required, list):
        return ()
    stated: list[str] = []
    for field in required:
        contract = properties.get(field)
        enum = contract.get("enum") if isinstance(contract, dict) else None
        if isinstance(enum, list) and len(enum) == 1:
            stated.append(field)
        elif (
            field == "direction"
            and operation in _OUTPUT_LEVEL_OPERATIONS
            and semantic_levels.direction_of(objective) is not None
        ):
            stated.append(field)
        elif field in partial_explicit_arguments(operation, objective, schema):
            # M76 (DEV-D v3l D-p19-t1): a title the readers know is not asked with the service that is missing.
            stated.append(field)
    return tuple(stated)


def _reference_lookup(objective: str, history: object) -> "semantic_knowledge.ReferenceLookup | None":
    """M53 (step 6 of goal v3, D35): a named dish's recipe or a named work's plot is looked up, never recited.

    ``semantic.knowledge`` reads the kind of fact from the person's words; the decider (its LoRA) is unchanged: its
    «talk» for these kinds becomes ``web.search`` with the query the reader writes, the same one the arguments step
    reads back from the same request.
    """

    # M88: BAXY's last answer is the referent of «¿cuánto sería eso de harina en gramos?».
    last_reply = next(
        (
            str(item.get("content") or "")
            for item in reversed(history if isinstance(history, list) else [])
            if isinstance(item, dict) and item.get("role") == "assistant"
        ),
        "",
    )
    # Ronda 19: BAXY's earlier answers carry the titles it showed («Está sonando «Soda Stereo - De Musica Ligera…»»).
    seen = tuple(
        str(item.get("content") or "")
        for item in (history if isinstance(history, list) else [])
        if isinstance(item, dict) and item.get("role") == "assistant"
    )
    return semantic_knowledge.reference_lookup(objective, _prior_user_texts(history, objective), last_reply, seen)


def _ground_explicit_arguments(
    operation: str,
    evidence: str,
    schema: dict[str, object],
    application_names: tuple[str, ...] = (),
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
    *,
    history: object = None,
) -> dict[str, object] | None:
    """Return a complete schema-grounded literal or abstain without inference."""

    if operation in {"memory.save", "memory.correct", "memory.forget"}:
        # Estabilización M: the datum the person said, read whole (``semantic.memory.memory_request``); never the
        # model's, so «cambiá mi color favorito a verde» corrects the selector the save wrote.
        asked = semantic_memory.memory_request(evidence)
        if asked is not None and asked[0] == operation and validate_json_schema_instance(asked[1], schema):
            return dict(asked[1])
    if operation == "notification.schedule" and (change := semantic_temporal.notification_change(evidence)) is not None:
        # M58 (v3d-final F-s019, F-s044, F-s095): the new time of a moved alarm, timer or reminder, its kind and what
        # it is for, read from the change the person asked for; the cancellation is its own step. M62 (v3e2-final
        # F-s044 «…from 3 to 4»): with neither clock saying its part of the day, the new one takes the part of the day
        # the old one was said with earlier in this conversation; with none said, it is asked.
        said_before = [
            str(item.get("content") or "")
            for item in reversed(history if isinstance(history, list) else [])
            if isinstance(item, dict) and item.get("content") != evidence
        ]
        part_of_day = semantic_temporal.change_part_of_day(change, said_before)
        if part_of_day is None and change.clocks_lack_the_part_of_day():
            # D61 sets a new hour without its part of the day at the next time it comes; a moved one is read against
            # the old one, so with neither said it is still asked (M62), never moved by the clock.
            return None
        moved = change.schedule_arguments(part_of_day)
        moved = _normalize_grounded_operation_arguments(operation, moved, moved["dueUtc"])
        return moved if moved is not None and validate_json_schema_instance(moved, schema) else None
    if operation == "web.search":
        reference = _reference_lookup(evidence, history)
        if reference is not None:
            # M53: the reader supplies the class word the provider reads («receta», «resumen»), as the news reader
            # supplies «noticias» below; the referent is the person's own words.
            looked_up = {"query": reference.query}
            if validate_json_schema_instance(looked_up, schema):
                return looked_up
    explicit = _explicit_arguments_from_evidence(
        operation,
        evidence,
        application_names,
        game_catalog,
    )
    if explicit is None and operation == "window.application.status":
        name = _window_query_reference_name(evidence, history, application_names)
        if name is not None:
            explicit = {"name": name}
    if explicit is None:
        deferred = effect_intent.deferred_clarification_split(
            evidence, (operation, "audio.volume.adjust", "audio.volume"), application_names, game_catalog,
        )
        if deferred is not None:
            # AUDIO858 H0067, H0527: the App sends the whole compound; the
            # read clause alone carries the arguments (window.resolve's
            # listing selector), the other clause is asked in the final.
            explicit = _explicit_arguments_from_evidence(
                operation, deferred.read_text, application_names, game_catalog,
            )
    if explicit is None:
        # Tanda 3 «para la música, me va a explotar la cabeza»: the decision read the order inside talk,
        # an address or a fronted place; the arguments read that same clause.
        uttered = semantic_reading.utterance_form(
            evidence,
            lambda clause: effect_intent.resolve_explicit_effects(
                clause, (operation,), application_names, game_catalog,
            ),
        )
        if uttered is not None and uttered[1].operations == (operation,):
            explicit = _explicit_arguments_from_evidence(
                operation, uttered[1].evidence[0], application_names, game_catalog,
            )
    if explicit is None and operation == "browser.navigate.named":
        # MUSIC1827 «abrí chrome y poné música» → «¿qué música?» → «rock»: the
        # decision read the answer as the completed browser music request;
        # the arguments read that same surface (history or resumed objective).
        previous = _previous_user_request(history, evidence) if isinstance(history, list) else None
        answer = evidence
        folded_evidence = effect_intent._fold(evidence)
        if previous is None and "aclaracion confiable del usuario:" in folded_evidence:
            previous, _, answer = folded_evidence.partition("aclaracion confiable del usuario:")
        completed = effect_intent._completed_missing_music_request(
            answer.strip(), (previous or "").strip() or None, (operation, "media.play.query"),
        )
        if completed is not None and effect_intent._named_browser_music_request(completed) is not None:
            explicit = _explicit_arguments_from_evidence(
                operation, completed, application_names, game_catalog,
            )
    if (
        explicit is None
        and operation in ("media.play.youtube", "media.play.query")
        and isinstance(history, list)
    ):
        # MUSIC1571 «poné una canción» → «¿qué música?» → «Bad Bunny»: the
        # answer alone names no request, so the literal reader abstained and
        # the model's extraction decided the turn (H0405 asked «¿qué buscas
        # en YouTube sobre Bad Bunny?»; H0066 «lofi» happened to ground).
        # The decision already read the answer as the completed music
        # request; the arguments read that same surface.
        completed = effect_intent._completed_missing_music_request(
            evidence,
            _previous_user_request(history, evidence),
            ("media.play.query", "media.play.youtube"),
        )
        if completed is not None:
            explicit = _explicit_arguments_from_evidence(
                operation,
                completed,
                application_names,
                game_catalog,
            )
    if explicit is None and operation in ("message.send.test", "message.draft"):
        # MSGCLAR1851 «mandale al grupo Musica: prueba 1 …» → «¿en qué canal?»
        # → «por WhatsApp»: the decision read the answer as the completed
        # message request; the arguments read that same surface (from the
        # history, or from the resumed objective with the trusted prefix).
        previous = _previous_user_request(history, evidence) if isinstance(history, list) else None
        answer = evidence
        folded_evidence = effect_intent._fold(evidence)
        if previous is None and "aclaracion confiable del usuario:" in folded_evidence:
            previous, _, answer = folded_evidence.partition("aclaracion confiable del usuario:")
        completed = effect_intent._completed_missing_message_channel_request(
            answer.strip(), (previous or "").strip() or None, ("message.send", operation),
        ) or effect_intent._completed_missing_message_text_request(
            answer.strip(), (previous or "").strip() or None, ("message.send", operation),
        )
        if completed is not None:
            explicit = _explicit_arguments_from_evidence(
                operation, completed, application_names, game_catalog,
            )
    if explicit is None and operation in _OUTPUT_LEVEL_OPERATIONS:
        # Uso real 2026-09-23 «Brillo 20%», «baja un veinte por ciento», «a 40» after «bajá el brillo»: the
        # decision read the canonical level request (``output_level_request``). The arguments are read from
        # that same request, never from the model's reading of a bare number: brightness 100 became 60
        # because «a 40» was taken as «40 less».
        previous = _previous_user_request(history, evidence) if isinstance(history, list) else None
        answer = evidence
        folded_evidence = effect_intent._fold(evidence)
        if previous is None and "aclaracion confiable del usuario:" in folded_evidence:
            previous, _, answer = folded_evidence.partition("aclaracion confiable del usuario:")
        completed = output_level_request(
            answer.strip(), (previous or "").strip() or None, _OUTPUT_LEVEL_OPERATIONS,
        )
        if completed is not None:
            explicit = _explicit_arguments_from_evidence(
                operation, completed, application_names, game_catalog,
            )
    if explicit is None and operation == "wifi.connect.named":
        # REOPEN1957 H0170/H0376 «conectate al wifi de casa» → «¿cuál de las
        # guardadas es la de casa?» → «Fibertel-2G»: the answer names the
        # profile; the place comes from the previous request in the history.
        answer = effect_intent.wifi_place_answer(evidence, history)
        if answer is not None:
            explicit = {"profileName": answer[0], "place": answer[1]}
    if explicit is None and operation in {"audio.app.volume.adjust", "audio.app.volume.set"}:
        # AUDIO1791 «subí el volumen de spotify» → «¿cuánto?» → «20»: the
        # decision read the answer as the completed request; the arguments
        # read that same surface (from the history, or from the resumed
        # objective that carries the trusted clarification prefix). «al 20»
        # completes it as the level (revisión ruta-tipada 4).
        previous = _previous_user_request(history, evidence) if isinstance(history, list) else None
        answer = evidence
        folded_evidence = effect_intent._fold(evidence)
        if previous is None and "aclaracion confiable del usuario:" in folded_evidence:
            previous, _, answer = folded_evidence.partition("aclaracion confiable del usuario:")
        completed = effect_intent._completed_missing_app_volume_request(
            answer.strip(), (previous or "").strip() or None, ("audio.app.volume.adjust", operation), application_names,
        )
        if completed is not None:
            explicit = _explicit_arguments_from_evidence(
                operation, completed, application_names, game_catalog,
            )
    if explicit is None and isinstance(history, list):
        items = [item for item in history if isinstance(item, dict)]
        recent = [str(item.get("content") or "") for item in reversed(items) if item.get("role") == "user" and item.get("content") != evidence]
        completed = None
        if operation == "browser.navigate":
            # «abrelo en mi navegador» after «qué es X»: the arguments read the completed request.
            completed = effect_intent._completed_browser_search_pronoun_request(evidence, recent)
        if completed is None:
            # «hazla» after a cancelled request: the previous request's own arguments.
            completed = effect_intent._redo_previous_request(
                evidence, recent, frozenset({operation}), application_names, game_catalog,
            )
        if completed is not None:
            explicit = _explicit_arguments_from_evidence(
                operation, completed, application_names, game_catalog,
            )
    if explicit is None and operation in {"notification.schedule", "reminder.create"}:
        return _timed_task_arguments(operation, evidence, history, schema)
    if operation == "weather.current" and explicit is not None and explicit.get("location") is None:
        # M58 (v3d-final F-w15-t1): the weather clause says «allá»; the place is the one the whole message says the
        # person is going to («me voy a San Antonio»). Never this PC's town in its place.
        there = weather_destination_there(evidence)
        if there is not None:
            explicit = {**explicit, "location": there}
    if explicit is None and operation == "mission.computer.use":
        # The decider chose the engine for a request the mission reader does not read («en Paint dibujá un
        # círculo»): the goal is the person's clause as said and the application the installed one it names.
        # v3 destino: with no application said, the one the conversation is in (the person's earlier requests).
        explicit = semantic_missions.free_form_arguments(
            evidence, application_names, _prior_user_requests(history),
        )
    if explicit is None:
        return None
    if operation in semantic_captures.CAPTURE_OPERATIONS:
        # Ronda 22: the folder is the capture reader's own enum value (Pictures when only «guárdala» was said), never
        # a literal the person must have spelled. A restatement that dropped the keeping falls back to the person's
        # own message of this turn.
        if not explicit and isinstance(history, list):
            explicit = semantic_captures.capture_save_arguments(_person_message(history, evidence))
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if operation == "mission.computer.use":
        # Computer use: the application is the catalog's display name, the goal
        # is normalized («calculá» → «calcular») and the success check is a
        # grammar of the reader's own; none of them is a literal the person
        # must have spelled; a chained request carries its sub-goals in steps.
        # The reader is deterministic, never the model.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if operation == "notification.schedule" and "recurrence" in explicit:
        # The repeating-event reader owns kind and recurrence (enum values the person need not
        # spell); the title is the person's words and the moment is read back by the clock reader.
        normalized = _normalize_grounded_operation_arguments(operation, explicit, evidence)
        return normalized if normalized is not None and validate_json_schema_instance(normalized, schema) else None
    if operation == "notification.schedule" and explicit.get("dueUtc") == semantic_temporal.alarm_for_hour(
        effect_intent._fold(evidence)
    ):
        # M165 (DEV-I v4y I-s008 «set an alarm for 6 to get up for my run, cheers» → «When would you like the alarm to
        # go off…?»): the hour after «for/para» on an alarm is the hour reader's clock (D61, «at 6»), a word the person
        # need not spell; the literal check dropped it and the extraction asked. The title is the person's words.
        normalized = _normalize_grounded_operation_arguments(operation, explicit, evidence)
        return normalized if normalized is not None and validate_json_schema_instance(normalized, schema) else None
    if (
        operation in {"filesystem.create.directory", "filesystem.write.text", "file.compress", "file.open"}
        and effect_intent.folder_txt_zip_open_mission(evidence) is not None
    ):
        # REOPEN1957 H0542: the unnamed folder and file take Windows' default
        # names, which the person never spelled.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if operation == "input.key.press" and start_menu_request(effect_intent._fold(evidence)):
        # Tanda 4: the Start menu reader owns the key; the person says the menu, not «win».
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if operation == "web.search" and near_the_person(evidence):
        # Uso real tanda 4c «comida para llevar cerca», «qué pasa en mi ciudad»: near
        # the person is near this PC's city, which the provider adds (``nearby``;
        # the person never spells a flag). The query crosses its usual grounding.
        query_only: dict | None = explicit
        if explicit.get("query") != news_lookup_query(evidence):
            query_only, _ = normalize_objective_arguments(explicit, schema, evidence)
        near = {**query_only, "nearby": True} if query_only is not None else None
        return near if near is not None and validate_json_schema_instance(near, schema) else None
    if operation == "web.search" and explicit.get("query") == news_lookup_query(evidence):
        # WEB1451 «qué pasó hoy en el mundo»: the news reader supplies the
        # word «noticias»; the scope words are the person's own.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if operation == "web.search" and explicit.get("query") == effect_intent.public_opinion_query(evidence):
        # M96 (held-out conv-v3v t14 «averiguá qué dijo la crítica» after «anoche vi Oppenheimer…», restated «¿Qué
        # dijo la crítica de Oppenheimer?»): the opinion reader supplies «opiniones»/«reviews» like the news reader
        # supplies «noticias», and the work is the person's words; the literal check dropped the query and the turn
        # asked the restatement back («¿Qué crítica específica…?»).
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if (
        operation == "web.search"
        and effect_intent.curiosity_request(evidence)
        and explicit.get("query") in effect_intent._CURIOSITY_TOPICS_ES + effect_intent._CURIOSITY_TOPICS_EN
    ):
        # KNOWLEDGE1505/1507 «decime una curiosidad»: the curiosity reader
        # supplies the subject from its own list; the person named none, so
        # the literal check would discard every pick and the turn asked back.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if operation == "notification.list" and explicit == {"limit": 50} and semantic_temporal.plural_alarm_cancellation(
        evidence
    ):
        # M62 (v3e2-final F-s040): the offer of every alarm reads as many as the catalog lets it; the bound is the
        # reader's, not a number the person says.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if operation == "filesystem.known.list" and explicit.get("folder") in (
        effect_intent._known_folder_listing_request(evidence),
        (effect_intent._known_folder_recent_listing(evidence) or (None, None))[0],
    ):
        # The listing reader owns the known-folder enum and the bounded limit;
        # neither is a word the person must spell literally.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if (
        operation == "filesystem.known.search"
        and effect_intent._literal_known_file_search(evidence) == explicit
    ):
        # The shared positive request grammar owns the known-folder enum;
        # the filename remains literal. Keep the authenticated schema boundary.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if (
        operation == "calculator.expression.evaluate"
        and effect_intent.calculator_expression_request(evidence) == explicit.get("expression")
    ):
        # UI1725: the expression is composed from the person's own numbers and
        # operator word («6 por 7» -> 6*7); the symbol is not a literal token.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if (
        operation in {"document.text.read", "document.pdf.read", "filesystem.explorer.count"}
        and (
            effect_intent.known_folder_file_path(evidence) is not None
            or effect_intent.explorer_count_request(evidence) is not None
        )
    ):
        # REOPEN1957 H0299/H0701: the folder enum, the subfolder and the
        # extension come from the path or the count request as read.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if (
        operation == "document.pdf.read"
        and effect_intent._pdf_summary_request(evidence) is not None
    ):
        # PDF1689: the reader owns the known-folder enum (all_known when no
        # folder is named); the file name remains the person's literal.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if (
        operation == "filesystem.known.trash.named"
        and effect_intent._file_trash_request(evidence) is not None
    ):
        # The deletion reader owns the known-folder enum, including all_known
        # when no folder is named («borrá el archivo viejo.txt»: FILES1241/002
        # failed as ambiguous because «all_known» has no literal in the text);
        # the file name remains the person's literal.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if operation == "window.resolve" and not validate_json_schema_instance(
        explicit, schema
    ):
        # A legacy process-only schema cannot represent title identity. Never
        # discard the selector to make this literal fit a different contract.
        return None
    if operation == "window.resolve" and "applicationName" in explicit:
        # The authenticated catalog owns this display name; the provider alone
        # binds it to a live OS application identity and issues a window token.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if operation == "window.resolve" and explicit.get("process") == "*" and explicit.get("byTitle") is False:
        # The closed inventory request supplies this catalog selector. The
        # person need not spell the provider's wildcard in natural language.
        return explicit
    if operation in {
        "app.installed",
        "app.open",
        "audio.app.volume.adjust",
        "audio.app.volume.set",
        "audio.mute",
        "audio.volume",
        "audio.volume.adjust",
        "browser.control",
        "browser.navigate",
        "browser.navigate.named",
        # Uso real 2026-09-23: the agenda readers own the UTC instants of a
        # window or an event (semantic.temporal); the title is the person's.
        "calendar.event.create",
        "calendar.event.list",
        "client.channel.locate",
        "message.draft",
        "message.send.test",
        "game.launch",
        # REOPEN1993 grupo G/N/W: the readers own the package name (catalog
        # name or the person's), the news topic and the weather place.
        "desktop.wallpaper.set",
        "file.compress",
        "file.open",
        "game.install.named",
        "game.uninstall.named",
        "package.install.prepare",
        "package.uninstall",
        "shell.command.run",
        "web.download",
        "web.news.headlines",
        "weather.current",
        "wifi.connect.named",
        "message.recipient.resolve",
        "email.send",
        "media.control",
        "media.play.exact",
        "media.play.query",
        "media.play.youtube",
        # D39 (M58): the clock reader of a cancellation owns hour, minute and period; «las 7:05» grounded
        # its minute as the literal «5», which «05» never is, and the minute was dropped (7:00 cancelled).
        "notification.cancel.at",
        # VIDEO1929 H0737 «quiero ver stranger things en nerflix»: el extractor
        # conserva el título literal y aporta el único servicio del catálogo;
        # exigir que «netflix» apareciera escrito tal cual tiraba esa lectura y
        # el turno preguntaba en qué servicio, con el servicio delante.
        "streaming.play.named",
        "system.process.list",
        "system.settings.adjust",
        "system.settings.set",
        "system.settings.status",
        "system.status",
        "system.time",
        "window.application.status",
    }:
        # Core's verified installed application/game snapshots own identity
        # canonicalization. Requiring a canonical display name or opaque AppID
        # to also appear literally in user text would discard that authority.
        # Browser history directions cross a complete-request grammar.
        # Browser destinations cross an equally closed parser: only a literal
        # URL, bare host, named service, or explicitly requested Google query
        # encoded by that parser is canonical. The media
        # query parser preserves the literal query and supplies the catalog's
        # sole provider value. System scopes are enum identities selected by
        # the existing domain parser, not words the user must spell literally.
        # Process ranks use that same closed metric/cardinal parser.
        # Audio's closed quantity parser grounds word-valued levels and
        # relative directions before canonicalizing them to catalog values.
        # Rechecking those values as generic literals would lose that evidence.
        # Every path still crosses the exact catalog JSON
        # Schema here.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    grounded, _ = normalize_objective_arguments(
        explicit,
        schema,
        evidence,
    )
    if grounded is None:
        return None
    normalized = _normalize_grounded_operation_arguments(
        operation,
        grounded,
        evidence,
    )
    return (
        normalized
        if normalized is not None and validate_json_schema_instance(normalized, schema)
        else None
    )


def _timed_task_arguments(
    operation: str, evidence: str, history: object, schema: dict[str, object],
) -> dict[str, object] | None:
    """M58 (v3d-final F-s011 «Reanudar el ejercicio en 5 minutos, mejor en 10 minutos» → «¿cuándo y en qué
    formato?»): a thing to do at a time, said with no alarm or reminder noun, for an operation already decided to be a
    notification. It is a reminder of that thing at the one time kept (the last of a corrected pair), read from the
    request or, when the restatement lost it, from the person's own message."""

    said = [evidence]
    if isinstance(history, list):
        said += [
            str(item.get("content") or "") for item in reversed(history)
            if isinstance(item, dict) and item.get("role") == "user"
        ][:1]
    found_in, task = next(
        (
            (text, found) for text in said
            # M76 (DEV-D v3l D-s120): a rest of a stated length is timed too («un descanso de 14 minutos»).
            if (found := semantic_temporal.timed_task(text) or semantic_temporal.timed_break(text)) is not None
        ),
        ("", None),
    )
    if task is None:
        return None
    arguments: dict[str, object] = {"dueUtc": task.due, "title": task.title}
    if operation == "notification.schedule":
        arguments["kind"] = task.kind
    # M170 (DEV-I v4y I-w20-t3, decided «Recuérdame mañana a las 8:45 que tengo una reunión a las 9.»): the request's two
    # clocks send the reading to the person's message, which names no day («…una reunion a las 9, recuerdamelo 15
    # minutos antes de eso»); the day the request places beside that moment or the clock that rings («mañana a las
    # 8:45») rides with it, so D61b reads tomorrow's 9 and not the next 9 (by day, tonight's 21:00, rung at 20:45).
    placed_day = semantic_temporal.placed_day_of_moment(evidence, found_in, task.due)
    moment = task.due if placed_day is None else f"{placed_day} {task.due}"
    # M137 (DEV-G v4n G-s016, DEV-F v4m F-w55-t1): the advance «recordámelo una hora antes» is read from the message.
    arguments = _normalize_grounded_operation_arguments(operation, arguments, moment, said=found_in)
    return arguments if arguments is not None and validate_json_schema_instance(arguments, schema) else None


def _fold_with_source_offsets(value: str) -> tuple[str, tuple[int, ...]]:
    """Fold text exactly like the effect resolver while retaining source offsets."""

    expanded: list[tuple[str, int]] = []
    for source_index, source_character in enumerate(value):
        decomposed = unicodedata.normalize("NFKD", source_character.casefold())
        expanded.extend(
            (character, source_index)
            for character in decomposed
            if not unicodedata.combining(character)
        )

    folded: list[str] = []
    offsets: list[int] = []
    pending_space: int | None = None
    for character, source_index in expanded:
        if character.isspace():
            if folded and pending_space is None:
                pending_space = source_index
            continue
        if pending_space is not None:
            folded.append(" ")
            offsets.append(pending_space)
            pending_space = None
        folded.append(character)
        offsets.append(source_index)
    return "".join(folded), tuple(offsets)


def _restore_evidence_surfaces(
    objective: str,
    evidence: tuple[str, ...],
) -> tuple[str, ...]:
    """Map normalized clause evidence back to the user's original literals."""

    folded_objective, offsets = _fold_with_source_offsets(objective)
    if not offsets:
        return evidence
    restored: list[str] = []
    cursor = 0
    for fragment in evidence:
        folded_fragment = effect_intent._fold(fragment)
        position = folded_objective.find(folded_fragment, cursor)
        if position < 0:
            position = folded_objective.find(folded_fragment)
        if position < 0 or not folded_fragment:
            restored.append(fragment)
            continue
        source_start = offsets[position]
        source_end = offsets[position + len(folded_fragment) - 1] + 1
        surface = objective[source_start:source_end].strip(" \t\r\n,;:-")
        restored.append(surface or fragment)
        cursor = position + len(folded_fragment)
    return tuple(restored)


def _normalize_grounded_operation_arguments(
    operation: str,
    arguments: dict[str, Any],
    context: str = "",
    *,
    now_utc: datetime | None = None,
    said: str | None = None,
) -> dict[str, Any] | None:
    """Apply closed semantic constraints not expressible by catalog JSON Schema. ``said``: the person's message the
    moment was read from, when ``context`` is only that moment (M137)."""

    normalized = dict(arguments)
    if operation == "weather.current" and isinstance(normalized.get("location"), str) and names_this_place(
        normalized["location"]
    ):
        # M76 (DEV-D v3l D-s054): «aquí» is this PC's place, read by the weather with no place named.
        del normalized["location"]
    if operation == "window.resolve":
        # M55 (v3b F-w06-t1, F-w08-t1 «invalid selector»): Core's selector contract is exactly one of
        # applicationName or process, and an application name takes neither byTitle nor offset. A neutral
        # byTitle=false or offset=0 beside a name is dropped; two selectors (two windows read into one
        # step) or none is never sent to fail in the Core.
        if "applicationName" in normalized:
            if normalized.get("byTitle") is False:
                normalized.pop("byTitle")
            if normalized.get("offset") == 0:
                normalized.pop("offset")
        if ("applicationName" in normalized) == ("process" in normalized) or (
            "applicationName" in normalized and ("byTitle" in normalized or "offset" in normalized)
        ):
            return None
    if (
        operation == "note.read"
        and isinstance(normalized.get("noteId"), str)
        and normalized.get("noteId")
    ):
        # Core's selector contract is exactly one of noteId or title. A
        # dependency-produced opaque ID is stronger than the repeated title.
        normalized.pop("title", None)
    objective = context
    if operation == "ocr.read" and "language" not in normalized:
        language = literal_ocr_language(objective)
        if language is not None:
            normalized["language"] = language
    if operation == "vision.describe" and "prompt" not in normalized:
        prompt = literal_vision_prompt(objective)
        if prompt is not None:
            normalized["prompt"] = prompt
    if operation == "task.create" and isinstance(normalized.get("due"), str):
        # M115 (DEV-F v4e2 F-s022, v4d F-w39-t3 «…para el jueves» → «el sistema la considera inválida»): the store reads
        # a day or a moment; what was said of it is written so, and a day nobody can tell is left out.
        due = _canonical_due_utc(normalized["due"], context, now_utc=now_utc) or semantic_temporal.task_due_date(
            normalized["due"], today=now_utc.astimezone().date() if now_utc is not None else None,
        )
        if due is None:
            normalized.pop("due")
        else:
            normalized["due"] = due
    if operation in {"notification.schedule", "reminder.create"}:
        raw_due = normalized.get("dueUtc")
        if not isinstance(raw_due, str):
            return None
        # M137 (DEV-G v4n G-s016, G-s019; DEV-F v4m F-w55-t1): «remind me an hour before» of the moment said in the
        # same message rings that long before it, titled with what happens then; the readers read the event's moment.
        advanced = due_before_said_moment(
            raw_due, normalized.get("title"), context, context if said is None else said, now_utc=now_utc,
        )
        if advanced is not None and advanced[0] is None:
            return None
        if advanced is not None:
            due_utc = advanced[0]
            if isinstance(advanced[1], str) and advanced[1]:
                normalized["title"] = advanced[1]
        else:
            due_utc = _canonical_due_utc(
                raw_due,
                context,
                now_utc=now_utc,
            )
        if due_utc is None:
            return None
        normalized["dueUtc"] = due_utc
        if operation == "reminder.create" and isinstance(
            normalized.get("title"),
            str,
        ):
            title = reminder_title_without_que(str(normalized["title"]))
            if not title:
                return None
            normalized["title"] = title
    return normalized
