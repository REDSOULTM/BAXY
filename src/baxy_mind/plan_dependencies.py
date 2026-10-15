"""Identities a plan step takes from its verified predecessors (a window, a device, a note, a recipient), never
from the model's extraction.
"""

from __future__ import annotations

import json

from . import effect_intent
from .semantic import dialogue as dialogue_slot
from .semantic.apps import names_the_window_in_front
from .semantic.notes import names_a_note, note_addition
from .semantic.windows import said_snap_side
from .effect_intent import ApplicationCatalogIndex, GameCatalogIndex
from .planner import conditional_predecessors, required_predecessors, validate_json_schema_instance
from .semantic.arguments import _explicit_arguments_from_evidence, window_snap_side_for_step
from .semantic.messaging import message_body


_DETERMINISTIC_DEPENDENCY_FIELDS = {
    "app.close": ("windowId",),
    "window.focus": ("windowId",),
    "window.maximize": ("windowId",),
    "window.minimize": ("windowId",),
    "window.move": ("windowId",),
    "window.resize": ("windowId",),
    "window.restore": ("windowId",),
    "window.snap": ("windowId",),
    "bluetooth.device.pair": ("deviceId",),
    "peripheral.scan": ("deviceId",),
    "filesystem.read.text": ("resourceId",),
    "game.install.commit": ("confirmationId",),
    "package.install.commit": ("confirmationId",),
    "game.purchase.commit": ("confirmationId", "expectedPriceCents"),
    "message.send": ("recipientId",),
    "note.read": ("noteId",),
    # M160: the rest of a note.update (revision, title, what it says) is the read's too (``_note_addition_arguments``).
    "note.update": ("noteId",),
    "notification.dismiss": ("reminderId", "expectedVersion"),
    "ocr.read": ("captureId",),
    "office.document.read": ("documentId",),
    "peripheral.print": ("deviceId",),
    "reminder.delete": ("reminderId", "expectedVersion", "reviewLabel"),
    "task.delete": ("taskId", "expectedVersion", "reviewLabel"),
    # M76 (DEV-D v3l D-w17-t2): identity and version from task.resolve.exact.
    "task.complete": ("taskId", "expectedVersion"),
    "task.reopen": ("taskId", "expectedVersion"),
    "vision.describe": ("captureId",),
    "wifi.connect": ("profileId",),
}


def _collect_dependency_field_values(value: object, field: str) -> list[object]:
    values: list[object] = []
    if isinstance(value, dict):
        for name, child in value.items():
            if (
                name == field
                and child is not None
                and not isinstance(child, (dict, list))
            ):
                values.append(child)
            values.extend(_collect_dependency_field_values(child, field))
    elif isinstance(value, list):
        for child in value:
            values.extend(_collect_dependency_field_values(child, field))
    return values


def _window_is_sizable(window: dict) -> bool:
    """A window a person could see as one: at least 200x100 when sizes are reported."""

    width, height = window.get("width"), window.get("height")
    if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
        return True
    return width >= 200 and height >= 100


def _verified_dependency_identity_arguments(
    operation: str,
    objective: str,
    observations: object,
    tool: dict[str, object],
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
    game_catalog: GameCatalogIndex | None = None,
    *,
    purpose: str = "",
) -> dict[str, object] | None:
    """Copy a complete unique identity from permitted verified producers.

    This is the sidecar equivalent of the App boundary's deterministic
    projector.  It removes stochastic model extraction only when the selected
    dependency already proves every argument required by the exact schema.
    """

    if not isinstance(observations, list):
        return None
    if operation == "note.update":
        return _note_addition_arguments(objective, purpose, observations, tool)
    if operation == "filesystem.write.text":
        report = effect_intent.process_report_file_request(effect_intent._fold(objective))
        if report is not None:
            return _process_report_file_arguments(report, observations, tool)
    if operation == "file.open":
        # REOPEN1957 H0069: the file to open is the one the download just wrote.
        downloads = [
            observation["result"]
            for observation in observations
            if isinstance(observation, dict)
            and observation.get("operation") == "web.download"
            and observation.get("verified") is True
            and observation.get("status") == "completed"
            and isinstance(observation.get("result"), dict)
        ]
        if len(downloads) == 1 and isinstance(downloads[0].get("name"), str) and isinstance(downloads[0].get("folder"), str):
            candidate = {"folder": downloads[0]["folder"], "name": downloads[0]["name"]}
            function = tool.get("function")
            schema = function.get("parameters") if isinstance(function, dict) else None
            if isinstance(schema, dict) and validate_json_schema_instance(candidate, schema):
                return candidate
    if operation == "browser.navigate.named":
        # H0516 «Abre Opera GX, busca una receta de pizza, …»: la navegación
        # que sigue a una búsqueda va al primer resultado verificado, en el
        # navegador que la persona nombró. El modelo, rellenando a ciegas,
        # escribió «opera» donde la persona dijo «Opera GX», y en este PC sólo
        # está Opera GX: el navegador es del pedido y la URL de la búsqueda.
        browser = effect_intent._named_browser(effect_intent._fold(objective))
        named_site = effect_intent._named_browser_site_request(objective, application_names)
        if named_site is not None:
            # H0081 «quiero que abras opera gx y entras a pivigames»: «abras» is
            # not one of the leading verbs the named-browser reader knows, and
            # without the browser from the reader the model wrote «opera» again.
            browser = named_site[0]
        searches = [
            observation["result"]
            for observation in observations
            if isinstance(observation, dict)
            and observation.get("operation") == "web.search"
            and observation.get("verified") is True
            and observation.get("status") == "completed"
            and isinstance(observation.get("result"), dict)
        ]
        if browser is not None and len(searches) == 1:
            first = next(
                (
                    result.get("url")
                    for result in (searches[0].get("results") or [])
                    if isinstance(result, dict) and isinstance(result.get("url"), str)
                ),
                None,
            )
            if first is not None:
                candidate = {"browser": browser, "url": first}
                function = tool.get("function")
                schema = function.get("parameters") if isinstance(function, dict) else None
                if isinstance(schema, dict) and validate_json_schema_instance(candidate, schema):
                    return candidate
    if operation == "window.focus" and effect_intent.other_window_switch_request(objective):
        # REOPEN1993 H0263 «cambiá a la otra ventana»: the first visible,
        # non-minimized window that is not in the foreground, in the order
        # the inventory observed (front to back), is «la otra».
        for observation in observations:
            if not (
                isinstance(observation, dict)
                and observation.get("operation") == "window.resolve"
                and observation.get("verified") is True
                and observation.get("status") == "completed"
                and isinstance(observation.get("result"), dict)
            ):
                continue
            windows = observation["result"].get("windows")
            if not isinstance(windows, list):
                continue
            # CONTEXT1999: the inventory also lists untitled tool windows
            # (DisplayFusion widgets 33x29, an explorer 0x0 shell window,
            # the taskbar) ahead of the real ones; a person sees as «la
            # otra ventana» the first titled, sizable, non-minimized window
            # behind the one in the foreground.
            visible = [
                window for window in windows
                if isinstance(window, dict)
                and isinstance(window.get("windowId"), str)
                and str(window.get("title") or "").strip()
                and window.get("state") != "minimized"
                and _window_is_sizable(window)
            ]
            behind = visible
            for index, window in enumerate(visible):
                if window.get("foreground") is True:
                    behind = visible[index + 1:] + visible[:index]
                    break
            for window in behind:
                if window.get("foreground") is not True:
                    return {"windowId": window["windowId"]}
        return None
    fields = _DETERMINISTIC_DEPENDENCY_FIELDS.get(operation, ())
    producers = set(required_predecessors(operation)) | set(
        conditional_predecessors(operation, objective)
    )
    if not fields or not producers:
        return None
    results = [
        observation["result"]
        for observation in observations
        if isinstance(observation, dict)
        and observation.get("operation") in producers
        and observation.get("verified") is True
        and observation.get("status") == "completed"
        and isinstance(observation.get("result"), dict)
    ]
    if not results:
        return None
    arguments: dict[str, object] = {}
    for field in fields:
        unique = {
            json.dumps(value, ensure_ascii=False, sort_keys=True): value
            for result in results
            for value in _collect_dependency_field_values(result, field)
        }
        if len(unique) == 1:
            arguments[field] = next(iter(unique.values()))
    function = tool.get("function")
    schema = function.get("parameters") if isinstance(function, dict) else None
    if not isinstance(schema, dict):
        return None
    if not validate_json_schema_instance(arguments, schema):
        # ARRANGE1781 «poné chrome a la izquierda»: the identity alone did
        # not satisfy window.snap (side missing) and the model extraction
        # produced nothing in Spanish; the fields the person authored come
        # from the effect reader, never from the model.
        explicit = _explicit_arguments_from_evidence(
            operation,
            objective,
            application_names if isinstance(application_names, tuple) else (),
            game_catalog if game_catalog is not None else GameCatalogIndex(),
        )
        if explicit is None and operation == "window.snap":
            # M55: a request that docks several windows gives each its own side; the step's purpose
            # picks which of the request's pairs this window is, the side stays the person's.
            explicit = window_snap_side_for_step(objective, purpose, application_names)
        if explicit is None and operation == "window.snap" and names_the_window_in_front(objective):
            # M145 (DEV-G v4p G-s041, G-s082, G-s102; DEV-H H-s028): the window in front has no name to read the
            # side beside; the side is the one half the request says.
            side = said_snap_side(objective)
            explicit = {"side": side} if side is not None else None
        if not isinstance(explicit, dict):
            return None
        merged = {**explicit, **arguments}
        if not validate_json_schema_instance(merged, schema):
            return None
        return merged
    return arguments


def _note_addition_arguments(
    objective: str, purpose: str, observations: list[object], tool: dict[str, object],
) -> dict[str, object] | None:
    """M160 (DEV-G v4w G-w12-t2 «agrégale que quiero comprarle un ramo de flores» after the note was made → «¿Cuál es
    el título de la nota que deseas editar?»): note.update replaces a note chosen by its identity and revision with a
    whole title and content; for an addition («Agrega «X» a la nota «Y».») they are the verified read's, and the content
    is what the note says followed by what the request adds (``semantic.notes.note_addition``), never rewritten. None
    when the request adds nothing it can say (a new title, a whole new text): the model grounds those as before."""

    reads = [
        observation["result"]
        for observation in observations
        if isinstance(observation, dict)
        and observation.get("operation") == "note.read"
        and observation.get("verified") is True
        and observation.get("status") == "completed"
        and isinstance(observation.get("result"), dict)
    ]
    added = note_addition(objective) or note_addition(purpose)
    if len(reads) != 1 or added is None:
        return None
    note = reads[0]
    if (
        not isinstance(note.get("noteId"), str)
        or not isinstance(note.get("title"), str)
        or isinstance(note.get("revision"), bool)
        or not isinstance(note.get("revision"), int)
        or note.get("isTrashed")
    ):
        return None
    said = str(note.get("content") or "").rstrip()
    candidate = {
        "noteId": note["noteId"],
        "expectedRevision": note["revision"],
        "expectedTitle": note["title"],
        "title": note["title"],
        "content": f"{said}\n{added}" if said else added,
    }
    function = tool.get("function")
    schema = function.get("parameters") if isinstance(function, dict) else None
    return candidate if isinstance(schema, dict) and validate_json_schema_instance(candidate, schema) else None


def _conversation_note_selector(
    operation: str,
    plan_operations: tuple[str, ...],
    person: str,
    dialogue_state: dialogue_slot.DialogueState,
    schema: dict[str, object],
) -> dict[str, str] | None:
    """M160 (DEV-G v4w G-w12-t2 «agrégale que quiero comprarle un ramo de flores» right after «He guardado la nota con
    el título "ideas para el cumpleaños de juliana".»): the read before a note.update is of the note this conversation
    just made, read or changed (``DialogueState.edited_note_title``), by the title the store verified, when the person
    names no note of their own. None otherwise: with no note in the conversation, the step is read and asked as before."""

    if operation != "note.read" or "note.update" not in plan_operations or names_a_note(person):
        return None
    title = dialogue_state.edited_note_title()
    selector = {"title": title} if title else None
    return selector if selector is not None and validate_json_schema_instance(selector, schema) else None


def _process_report_file_arguments(
    report: dict[str, object],
    observations: list[object],
    tool: dict[str, object],
) -> dict[str, object] | None:
    """FILES1705: project the verified process listing into the file text.

    Every token of the text is evidence: the header repeats the request's
    own words and each line is the observed process name with its observed
    working-set bytes, so the grounding contract holds without a model.
    """

    listings = [
        observation["result"]
        for observation in observations
        if isinstance(observation, dict)
        and observation.get("operation") == "system.process.list"
        and observation.get("verified") is True
        and observation.get("status") == "completed"
        and isinstance(observation.get("result"), dict)
        and isinstance(observation["result"].get("processes"), list)
    ]
    if len(listings) != 1:
        return None
    lines: list[str] = []
    for entry in listings[0]["processes"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            return None
        measure = entry.get("workingSetBytes") if report.get("sort") == "memory" else entry.get("cpuUsagePercent")
        if measure is None:
            measure = entry.get("totalProcessorSeconds")
        if isinstance(measure, bool) or not isinstance(measure, (int, float)):
            return None
        # Rendered exactly as the observation JSON carries it (shortest
        # round-trip for a float, no exponent), so the line stays evidence.
        if isinstance(measure, int):
            rendered = str(measure)
        elif measure.is_integer():
            rendered = str(int(measure))
        else:
            rendered = repr(measure)
            if 'e' in rendered or 'E' in rendered:
                return None
        lines.append(f"{entry['name'].strip()}: {rendered}")
    if not lines:
        return None
    header = str(report.get("description") or "").strip()
    if not header:
        return None
    # The default name is built from the request's own words (its noun and its
    # resource word) so that it grounds in either language.
    noun = "processes" if "processes" in header.split() else "procesos"
    name = str(report.get("name") or f"{noun}-{report.get('resource_word') or 'memoria'}.txt")
    arguments: dict[str, object] = {"relativePath": name, "text": header + "\n" + "\n".join(lines) + "\n"}
    function = tool.get("function")
    schema = function.get("parameters") if isinstance(function, dict) else None
    if not isinstance(schema, dict) or not validate_json_schema_instance(arguments, schema):
        return None
    return arguments


def _verified_message_send_arguments(
    objective: str,
    observations: object,
) -> dict[str, object] | None:
    """Join one verified recipient identity with the user's literal message body."""

    if not isinstance(observations, list):
        return None
    recipient_ids = {
        result["recipientId"]
        for observation in observations
        if isinstance(observation, dict)
        and observation.get("operation") == "message.recipient.resolve"
        and observation.get("verified") is True
        and observation.get("status") == "completed"
        and isinstance((result := observation.get("result")), dict)
        and isinstance(result.get("recipientId"), str)
        and result["recipientId"].strip()
    }
    if len(recipient_ids) != 1:
        return None
    body = message_body(objective)
    if body is None:
        return None
    return {"recipientId": next(iter(recipient_ids)), "text": body}
