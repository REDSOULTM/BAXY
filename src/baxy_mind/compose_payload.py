"""The payload of a composition: the observed facts and derived quantities the writer receives, and the user
content of the composer.
"""

from __future__ import annotations

import copy
import json
from datetime import timedelta

from .semantic import quantities as semantic_quantities
from .semantic.windows import asks_to_name_windows
from .semantic.network import asks_calendar_part
from .semantic.temporal import clock_later_asked, plural_alarm_cancellation
from . import effect_intent
from .effect_intent import countdown_target, literal_clipboard_write_text
from .measurement_prose_projection import project_process_measurements, project_system_measurements
from .semantic.request import (
    INTENT_CAPABILITY, INTENT_CONTINUE_CONSTRAINT, INTENT_NEGATIVE_CONSTRAINT, INTENT_REFUSE, RequestReading,
    read_request,
)
from .window_prose_facts import project_window_inventory
from .semantic.conversation import asks_for_an_internal_identifier
from .semantic.network import names_the_time
from .clock_facts import (
    _calendar_facts, _countdown_facts, _local_clock_from_observed, _local_datetime_from_observed, _place_clock_facts,
    _window_title_as_shown,
)
from .compose_situation import (
    _ALREADY_IN_STATE_OPERATIONS, _ASKED_STATE_ALREADY_HELD, _attempted_facts, _CAUSE_FACT, _cause_in_prose,
    _has_cause_fact, _merged_observed, _not_done_facts, _TYPED_TRANSITION_OPERATIONS,
)
from .capability_families import _capability_phrases, CAPABILITY_SAMPLE
from .device_facts import (
    _capture_saved_folder_name, _capture_unmet_facts, _project_python_package_status, _screen_text_excerpt,
    _unreceived_facts,
)
from .search_report import _search_results_text
from .listing_facts import (
    _PAGE_LISTING_CHARACTERS, _project_game_listing, _project_known_listing, _project_page_read, _project_pdf_read,
    _project_tab_listing,
)
from .agenda_facts import (
    _alarm_offer_seen, _project_cancelled_notification, _project_notification_listing, _project_scheduled_notification,
)
from .weather_facts import _project_weather_read
from .argument_payload import person_askable_fields


def _localized_confirmation_words(words: list[str], language: str) -> list[str]:
    """Collapse bilingual aliases without dropping a confirmation decision."""

    aliases = {
        "confirmar": ("confirmar", "confirm"),
        "confirm": ("confirmar", "confirm"),
        "cancelar": ("cancelar", "cancel"),
        "cancel": ("cancelar", "cancel"),
        "continuar": ("continuar", "continue"),
        "continue": ("continuar", "continue"),
    }
    localized: list[str] = []
    seen_aliases: set[tuple[str, str]] = set()
    for word in words:
        pair = aliases.get(word.casefold())
        if pair is None:
            localized.append(word)
            continue
        if pair in seen_aliases:
            continue
        seen_aliases.add(pair)
        localized.append(pair[1] if language == "en" else pair[0])
    return localized


def _compose_action_facts(action: object) -> object:
    facts = copy.deepcopy(action)
    if isinstance(facts, dict) and isinstance(facts.get("arguments"), dict):
        # Window capabilities authorize execution; they are not a name a person
        # can use to distinguish targets. Keep the prepared action elsewhere.
        facts["arguments"].pop("windowId", None)
    return facts


def _required_compose_input(situation: dict) -> str | None:
    if (
        str(situation.get("kind") or "").strip().lower() != "clarification"
        or str(situation.get("polarity") or "").strip().lower() != "pending"
    ):
        return None
    value = situation.get("missingValue")
    if not isinstance(value, str) or not value.strip():
        return None
    # M76 (DEV-D v3l): the shell names the operation's missing fields when the arguments step gave no question; a
    # write guard among them (expectedVersion) is not something to ask the person. Estabilización M3: nor a field
    # internal to the operation the shell names (the scope of a forget); with none left, nothing is named.
    fields = tuple(part.strip() for part in value.split(",") if part.strip())
    if not fields:
        return value.strip()
    return ", ".join(person_askable_fields(fields, operation=situation.get("operation"))) or None


def _compose_situation_payload(
    situation: dict,
    language: str,
    user_text: str = "",
    reading: RequestReading | None = None,
    capabilities: list[str] | None = None,
    *,
    _reason_depth: int = 0,
    _window_titles_quiet: bool = False,
) -> dict:
    """Hechos observados y cantidades derivadas de esas mismas mediciones.

    Esta función presentaba el pedido como si fuera un efecto medido: del verbo
    «close» sacaba `effect=closed` y `seen.window=true` sin ninguna observación,
    y una lectura de red sin `online` ni `connected` salía como `online=false`.
    Aquí ya no se infiere nada del texto del pedido: lo desconocido se calla y
    la polaridad negativa viaja en `outcome` para que un reintento no la pierda.
    """

    reading = reading or read_request(user_text)
    payload: dict[str, object] = {}
    kind = str(situation.get("kind") or "").strip().lower()
    if kind in {
        "welcome",
        "conversation",
        "clarification",
        "confirmation",
        "status",
        "error",
    }:
        # Message purpose is not a PC observation. Preserve it even when there
        # are no facts: otherwise welcome and progress collapse to the same
        # empty payload and the model can only answer the language instruction.
        payload["kind"] = kind
    required_input = _required_compose_input(situation)
    if required_input is not None:
        payload["missingValue"] = required_input
    # Uso real 2026-10-07 (the «top 3» seed): how many the person asked to be listed, and the words told of the same
    # result before, when they corrected or insisted and the same thing was found again (__main__ adds both).
    if type(situation.get("askedCount")) is int and situation["askedCount"] > 0:
        payload["askedCount"] = situation["askedCount"]
    if isinstance(situation.get("openSearch"), dict):
        # Semilla fix2: the search already open in the person's browser that this turn read instead of opening again.
        payload["openSearch"] = {
            key: value for key, value in situation["openSearch"].items() if isinstance(value, str) and value.strip()
        }
    for repeated in ("sameResultAgain", "correctedFinal", "alreadyHolds", "undoNothing"):
        # Ronda 24: «previousTurnActed» (correctedFinal) is a flag, kept as it is.
        if isinstance(situation.get(repeated), dict):
            payload[repeated] = {
                key: value for key, value in situation[repeated].items()
                if (isinstance(value, str) and value.strip()) or type(value) is bool
            }
    polarity = str(situation.get("polarity") or "").strip().lower()
    cause_value = situation.get("cause") or ""
    # Typed operation results carry their cause in error; mission events use
    # cause. Preserve both representations through the same prose projection.
    if (
        not cause_value
        and kind == "operation"
        and polarity == "failure"
        and isinstance(situation.get("error"), str)
    ):
        cause_value = situation["error"]
    if (
        kind == "operation"
        and polarity == "failure"
        and isinstance(situation.get("error"), str)
        and _has_cause_fact(situation["error"])
    ):
        # MUSIC1755: a typed client error («spotify_exact_result_not_found»)
        # says what happened; the generic mission cause
        # («external_effect_ambiguous») only says it was not verified.
        cause_value = situation["error"]
    cause_key = str(cause_value).strip().lower()
    if cause_key == "mission_completed" and "completedRequest" in situation:
        # "confirmar" carries no objective. Retain what the completed mission
        # was for, just as cancellation retains the request that was stopped.
        # Falsos éxitos v3 M4 (v3-51 «…y creé una nueva escena llamada Pruebas» after a single app.open; t-file-1 the
        # folder said from the request): it travels as what was asked («requested»), never as a fact; what was done
        # is in the steps, and the final gate backs only their acts (_act_ledger).
        payload["requested"] = _compose_action_facts(
            situation["completedRequest"]
        )
    if cause_key == "acting":
        phase = str(situation.get("phase") or "")
        payload["state"] = {
            "understanding": "reviewing the person's request",
            "preparing_steps": "preparing the steps for the request",
            "acting": "working on the current step",
            "working": "working on the request",
        }.get(phase, "in progress")
        step = situation.get("step")
        total = situation.get("totalSteps")
        if phase == "acting" and type(step) is int and type(total) is int and 0 < step <= total and total > 1:
            payload.update(step=step, totalSteps=total)
    if isinstance(situation.get("readOnly"), bool):
        payload["readOnly"] = situation["readOnly"]
    for key in ("operationAttempted", "retryable"):
        if isinstance(situation.get(key), bool):
            payload[key] = situation[key]
    target = situation.get("target")
    if target not in (None, "", []):
        payload["target"] = target
    # M116 (DEV-F v4e2 F-s014 «déjale escrito a la Lupita en WhatsApp…» → «No pude dejar escrito el mensaje
    # «Lupita».»): a step that failed or was left unverified carries what it attempted (the App's
    # Baxy.App.AttemptedArguments: to whom, which words, where) and the effects it left undone, so the final says
    # them beside the cause.
    attempted = _attempted_facts(situation.get("attempted"))
    if attempted:
        payload["attempted"] = attempted
    not_done = _not_done_facts(situation.get("notDone"), language)
    if _reason_depth == 0:
        # Revisión r22 (bloqueante 1): a place asked for the capture that it could not take is told as not done.
        not_done += _capture_unmet_facts(situation, user_text, language)
        # Revisión 2 de r22 (bloqueante 3): every part of the request the operation's schema could not receive.
        not_done += _unreceived_facts(situation, language)
    if not_done:
        payload["notDone"] = not_done
    if kind == "confirmation":
        # The current user text can be an invalid reply or a recovery request.
        # Describe the pending invocation, not an action inferred from that reply.
        for key in ("pendingRequest", "pendingAction"):
            if key in situation:
                payload[key] = _compose_action_facts(situation[key])
        # Export confirmation already carries the destination and possible
        # redirection/sync from the shell. Dropping them prevents the narrator
        # from explaining what the person is about to authorize.
        destination = situation.get("destination")
        if isinstance(destination, str) and destination.strip():
            payload["destination"] = destination
        if isinstance(situation.get("mayRedirectOrSync"), bool):
            payload["mayRedirectOrSync"] = situation["mayRedirectOrSync"]
    if cause_key in {"remaining_steps_cancelled", "memory_cancelled"}:
        # "cancelar" names no target. Keep the exact stopped action rather than
        # asking the narrator to infer it from old window observations or history.
        for key in ("cancelledRequest", "cancelledAction"):
            if key in situation:
                payload[key] = _compose_action_facts(situation[key])
    if polarity == "failure" and kind == "operation" and cause_key in _ASKED_STATE_ALREADY_HELD:
        # M69 (guion v3h t47): the asked state already held; nothing failed and nothing was attempted.
        payload["outcome"] = "already_as_asked"
    elif polarity == "failure":
        payload["outcome"] = "failed"
    elif cause_key in {"remaining_steps_cancelled", "memory_cancelled", "clarification_cancelled"}:
        # Successful cancellation does not complete the requested action.
        # Earlier verified effects stay in completedStepsInOrder below.
        # M45 (FINAL t22): a cancelled clarification sent as «completed» was
        # composed «Reanudaré el ejercicio en 10 minutos.»; nothing ran.
        payload["outcome"] = "cancelled"
    elif (
        polarity == "success"
        and situation.get("kind") == "status"
        and cause_key != "acting"
    ):
        # A status reports a transition that already happened, not an action
        # the model should request or repeat.
        payload["outcome"] = "completed"
    if situation.get("effectUncertain") is True:
        # A failed verification does not prove either success or absence of an
        # effect. Keep that distinction, including during a later request.
        payload["outcome"] = "unverified"
        payload["effect"] = "unknown"
        for key in ("pendingRequest", "pending", "canRepeat", "evidenceRetained"):
            if key in situation:
                payload[key] = situation[key]
    seen = situation.get("observed")
    operation = str(situation.get("operation") or "").strip()
    if (
        operation in {"app.open", "browser.navigate", "browser.navigate.named", "streaming.navigate"}
        and kind == "operation"
        and polarity == "success"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
        and situation.get("effectUncertain") is not True
    ):
        # Opening was verified already; this is not a promise to launch later.
        # WEB1259: a verified navigation composed as «Voy a youtube.» without it.
        payload["outcome"] = "completed"
    completed_steps: list[dict] = []
    if _reason_depth < 8:
        step_results: list[dict] = []
        for step_result in situation.get("steps") or []:
            if isinstance(step_result, str):
                try:
                    step_result = json.loads(step_result)
                except json.JSONDecodeError:
                    continue
            if isinstance(step_result, dict):
                step_results.append(step_result)
        # Ronda 22 revisión 2: a window read's titles stay out only where they are no answer, in a mission that did
        # not complete or in a read that an effect after it needed (its window was the effect's target). The last
        # reads of a completed mission are what the person asked («¿qué documento tengo abierto en Word?»).
        mission_unfinished = str(situation.get("cause") or "").strip().lower() != "mission_completed"
        for index, step_result in enumerate(step_results):
            feeds_effect = any(later.get("readOnly") is False for later in step_results[index + 1:])
            facts = _compose_situation_payload(
                step_result, language, user_text, reading, capabilities,
                _reason_depth=_reason_depth + 1,
                _window_titles_quiet=mission_unfinished or feeds_effect,
            )
            if facts:
                completed_steps.append(
                    {
                        "operation": step_result.get("operation"),
                        "resultAtThisStep": facts,
                    }
                )
    if completed_steps:
        # A resolver snapshot precedes the effect it enables. Flattening both
        # made a closed window appear currently maximized and visible. Keep
        # every result in execution order, including independently requested reads.
        payload["completedStepsInOrder"] = completed_steps
    merged_seen = {} if completed_steps else _merged_observed(situation)
    if operation == "network.status" and merged_seen:
        online = merged_seen.get("online")
        if online is None:
            online = merged_seen.get("connected")
        # Sin lectura de conectividad no se afirma que no la haya: se calla.
        if online is not None:
            payload["seen"] = {"online": bool(online)}
    elif merged_seen:
        visible_seen = dict(merged_seen)
        if operation == "system.status":
            visible_seen = project_system_measurements(visible_seen)
        elif operation == "system.process.list":
            visible_seen = project_process_measurements(visible_seen, user_text)
        elif operation == "weather.current":
            visible_seen = _project_weather_read(visible_seen, user_text)
        elif (
            operation == "app.installed"
            and visible_seen.get("authority") == "windows_start_catalog_snapshot"
        ):
            # Presentation only: keep the authenticated snapshot and checks intact.
            visible_seen["authority"] = (
                "Windows Start application catalog" if language == "en"
                else "catálogo de inicio de Windows"
            )
        elif operation == "app.open" and isinstance(visible_seen.get("alreadyRunning"), bool):
            # The receipt records whether it was running BEFORE this invocation.
            # False must not tell the narrator that the app is still closed.
            visible_seen["was_running_before_open"] = visible_seen.pop("alreadyRunning")
        elif operation == "desktop.wallpaper.set":
            # WALLPAPER2037 (notebook, 2026-09-22): the receipt's RGB triple
            # («170 20 20») and the previous wallpaper's path reached the
            # narrator, which wrote the code into the final and died in
            # invented_number three times for two of four cases; the colour name
            # is the fact the person asked for, the code and the path are the
            # adapter's. The checks keep the whole receipt.
            visible_seen.pop("rgb", None)
            visible_seen.pop("previousWallpaper", None)
        elif operation == "clipboard.write.text":
            # CLIPBOARD1359 H0199/H0356: the receipt carries only the sequence
            # number and the character count, so the narrator echoed the text
            # («Hola») instead of reporting the copy. The written literal is
            # the one the reader grounded from this same request; the receipt
            # verified it by post-read.
            written = literal_clipboard_write_text(user_text) if user_text else None
            if (
                isinstance(written, str)
                and situation.get("verified") is True
                and situation.get("succeeded") is True
            ):
                visible_seen["writtenText"] = written
        elif operation == "input.text.type" and visible_seen.get("ok") is True:
            # THEN2003 «ponle hola mundo»: the receipt carries counts and the
            # window it typed into, not the text, so the narrator echoed «Hola
            # mundo». The typed literal comes from the request; the window from
            # the receipt.
            typed = effect_intent.deictic_typed_literal(user_text) if user_text else None
            projected = {}
            if isinstance(typed, str) and situation.get("verified") is True and situation.get("succeeded") is True:
                projected["typedText"] = typed
            title = visible_seen.get("foregroundTitleBefore")
            if isinstance(title, str) and title.strip():
                projected["typedInto"] = title.strip()
            visible_seen = projected
        elif operation == "input.key.press" and visible_seen.get("ok") is True:
            # Tanda 4c «show me las aplicaciones»: the receipt's title of the window that had the focus before the
            # press (an update dialog) reached the narrator, which told it as an error the system had shown. The
            # key pressed is the fact; focus bookkeeping and event counts are the adapter's verification.
            visible_seen = {"keyPressed": visible_seen.get("key")}
        elif operation == "input.visible.click" and visible_seen.get("ok") is True:
            # UI1635 «clic en el botón Aceptar»: the receipt's absentOrDisabled
            # is a post-read — the control was gone after the click because
            # its dialog closed — but the narrator read it as «disabled» and
            # published a failure over a verified click. Say what it means.
            projected = {"name": visible_seen.get("name"), "clicked": True}
            if visible_seen.get("absentOrDisabled") is True:
                projected["controlGoneAfterClick"] = True
                projected["note"] = (
                    "the control disappeared after the click (its dialog or view closed); the click succeeded"
                    if language == "en"
                    else "el control desapareció tras el clic (su diálogo o vista se cerró); el clic se hizo"
                )
            if visible_seen.get("selected") is True:
                projected["selected"] = True
            if visible_seen.get("surfaceChanged") is True:
                projected["surfaceChanged"] = True
            visible_seen = projected
        elif operation == "mission.computer.use":
            # Computer use (CONTRATO_VISTA_ACCION.md §4.5): the composer sees
            # what the loop did and saw, never the raw steps or hashes.
            from . import cu_projection as _cu_projection

            visible_seen = _cu_projection.project_seen(visible_seen, language)
        elif operation == "window.close.all" and isinstance(visible_seen.get("closed"), int):
            # CLOSEALL1733 «cerrame todo»: the counts are the facts; process names
            # («Code», «Notepad») are not words for the person — the kept editor
            # is named as the product it is.
            remaining_count = visible_seen.get("remainingVisible")
            projected = {
                "closedWindows": visible_seen.get("closed"),
                "windowsStillOpenAfterAsking": remaining_count,
            }
            if visible_seen.get("editorKeptOpen") is True:
                projected["keptOpenOnPurpose"] = "Visual Studio Code"
            if isinstance(remaining_count, int) and remaining_count > 0:
                projected["note"] = (
                    f"{remaining_count} window(s) were asked to close and stayed open (an application may be asking whether to save); this does not count Visual Studio Code, which was kept on purpose"
                    if language == "en"
                    else f"{remaining_count} ventana(s) recibieron el pedido de cierre y siguen abiertas (alguna aplicación puede estar preguntando si guardar); no cuenta Visual Studio Code, que se dejó abierto a propósito"
                )
            if visible_seen.get("closed") == 0 and remaining_count == 0:
                projected["note"] = (
                    "there was no window to close" if language == "en" else "no había ninguna ventana que cerrar"
                )
            visible_seen = projected
        elif operation == "filesystem.known.list":
            visible_seen = _project_known_listing(visible_seen, language)
        elif operation == "game.catalog.list":
            visible_seen = _project_game_listing(visible_seen, language)
        elif operation == "browser.page.read":
            visible_seen = _project_page_read(
                visible_seen, language, _PAGE_LISTING_CHARACTERS if isinstance(situation.get("openSearch"), dict) else None,
            )
        elif operation in {"document.pdf.read", "document.text.read"}:
            visible_seen = _project_pdf_read(visible_seen, language)
        elif operation == "filesystem.explorer.count":
            # REOPEN1957 H0701: the folder's own name, where it was taken from and the figures.
            visible_seen = {
                key: visible_seen[key]
                for key in ("folderName", "source", "extension", "count", "filesInFolder")
                if key in visible_seen
            }
        elif operation == "audio.microphone.mute" and isinstance(visible_seen.get("muted"), bool):
            # M69 (guion v3h t46 «activalo» after muting): «muted: false» was composed «El micrófono está
            # desactivado.», the opposite of the truth. The narrator gets the microphone's state in words.
            projected = {"microphone": _microphone_state_words(visible_seen["muted"], language)}
            if isinstance(visible_seen.get("baselineMuted"), bool):
                projected["microphoneBefore"] = _microphone_state_words(visible_seen["baselineMuted"], language)
            visible_seen = projected
        elif operation == "media.play.youtube":
            # MUSIC1553: the process id and the IPC authority are not for the
            # person; the query, the observed title and the state are.
            visible_seen = {
                key: visible_seen[key]
                for key in ("provider", "query", "title", "playbackStatus", "titleObserved")
                if key in visible_seen
            }
        elif operation == "notification.list":
            listing = _project_notification_listing(visible_seen, language)
            # D39/M62: «cancela las alarmas» is answered with the alarms alone and whether the yes cancels them all.
            visible_seen = (
                _alarm_offer_seen(visible_seen, listing) if plural_alarm_cancellation(user_text or "") else listing
            )
        elif operation in {"notification.schedule", "reminder.create"}:
            visible_seen = _project_scheduled_notification(visible_seen, situation, language, user_text or "")
        elif operation == "notification.cancel.at" and situation.get("verified") is True:
            visible_seen = _project_cancelled_notification(visible_seen, situation, language)
        elif operation == "ocr.read":
            # SCREEN1407 «leéme lo que dice la pantalla»: the receipt carries the
            # layout boxes, hashes and timestamps (about 30 KB) and the composer
            # prompt overflowed the context before the model ran. The person
            # asked for the text: keep it (bounded), the line count and language.
            # SCREEN1413: given the whole text the model transcribed it and ran
            # out of budget; given an excerpt it can only quote the excerpt.
            projected: dict = {}
            recognized = visible_seen.get("text")
            layout = visible_seen.get("layout")
            layout_lines = layout.get("lines") if isinstance(layout, dict) else None
            if isinstance(layout_lines, list) and layout_lines:
                # The provider joins the text with spaces; the layout keeps lines.
                recognized = "\n".join(
                    str(line.get("text") or "") for line in layout_lines if isinstance(line, dict)
                )
            if isinstance(recognized, str):
                excerpt = _screen_text_excerpt(recognized)
                # SCREEN1419: quoted as a joined string, the model copied the
                # JSON newline escapes into the quotation; a list quotes cleanly.
                projected["lines"] = excerpt
                projected["text"] = "\n".join(excerpt)
            for key in ("lineCount", "language"):
                if visible_seen.get(key) is not None:
                    projected[key] = visible_seen[key]
            visible_seen = projected
        elif operation == "software.python.package.status":
            # PIP1817: the per-Python list (installed true/false per entry) was
            # generalized from its first entry; the model gets the split lists.
            visible_seen = _project_python_package_status(visible_seen)
        elif operation == "browser.control":
            # BROWSER1493 «abrí una pestaña nueva»: the target id is an
            # internal identifier; the person needs the action and its state.
            # In the person's own browser (owner 2026-10-06) the tab that closed and the tab now in front are what
            # the person sees change; closing every tab also says how many closed and how many are left.
            counts = ("closedTabs", "tabCount") if visible_seen.get("action") == "close_all" else ()
            visible_seen = {
                **{
                    key: visible_seen[key]
                    for key in ("action", "observedState", "closedTab", "activeTab")
                    if isinstance(visible_seen.get(key), str)
                },
                **{key: visible_seen[key] for key in counts if type(visible_seen.get(key)) is int},
            }
        elif operation == "browser.tabs.list":
            visible_seen = _project_tab_listing(visible_seen)
        elif operation in ("capture.screenshot", "capture.active.window"):
            # SCREEN1399 H0093 «sacá un screenshot»: the receipt's captureId,
            # sha256 and timestamp were narrated («con el ID capture_…») and the
            # internal-code veto blocked every draft. The person needs to know
            # that the capture was taken, of what, and that it stayed private.
            scope = visible_seen.get("scope")
            saved_in = _capture_saved_folder_name(visible_seen.get("savedFolder"), language)
            file_name = visible_seen.get("fileName")
            visible_seen = {
                key: visible_seen[key]
                for key in ("width", "height")
                if isinstance(visible_seen.get(key), int)
            }
            visible_seen["captured"] = (
                ("the active window" if scope == "active_window" else "the whole screen")
                if language == "en"
                else ("la ventana activa" if scope == "active_window" else "toda la pantalla")
            )
            if saved_in is not None and isinstance(file_name, str) and file_name.strip():
                # Ronda 22 (uso real r18 t2-c16, t3-c11, t4-c09): the copy the person asked to keep was saved and read
                # back; where it is (the folder's visible name, from data) and its file name are what they need.
                visible_seen["savedIn"] = saved_in
                visible_seen["fileName"] = file_name.strip()
            else:
                visible_seen["storedPrivately"] = True
        elif isinstance(operation, str) and operation.startswith("system.settings."):
            # BRIGHT1319 H0430: «según la lectura de WMI» was copied from the
            # provenance token; the monitor instance path is internal too. The
            # canonical observation and the factual checks keep both.
            visible_seen.pop("authority", None)
            if isinstance(visible_seen.get("monitors"), list):
                visible_seen["monitors"] = [
                    {key: value for key, value in monitor.items() if key != "instanceName"}
                    if isinstance(monitor, dict) else monitor
                    for monitor in visible_seen["monitors"]
                ]
        if operation in {"audio.app.volume.adjust", "audio.app.volume.set"}:
            # AUDIO1795: the application's volume fact is the app, the direction,
            # the amount and the levels; the sessions' mute flag, process name and
            # session count invited claims about silence and open/closed state.
            for key in ("muted", "processName", "sessionCount", "authority", "endpointIdHash"):
                visible_seen.pop(key, None)
        if identifier_is_plumbing(operation) and not asks_for_an_internal_identifier(user_text or ""):
            # Live 2026-10-07 (x12 «abrí la calculadora» → «Abrí la calculadora y ahora está ejecutándose en la ventana
            # con el handle 4722336.»): a window handle or process id is the adapter's, never what the person sees.
            # A window or process inventory keeps them: there they are what was listed.
            for key in _INTERNAL_IDENTIFIER_KEYS:
                visible_seen.pop(key, None)
        if operation in {"wifi.radio.set", "wifi.radio.status"} and isinstance(visible_seen.get("state"), bool):
            # NETWORK1737: «state» is removed below as an internal status field,
            # but the radio's read-back state is the fact of these operations.
            visible_seen["wifiRadioOn"] = visible_seen["state"]
        if operation == "bluetooth.radio.set" and isinstance(visible_seen.get("state"), bool):
            # v3 r6 lectores (t2-r4 c15): the Bluetooth radio's read-back state is the fact of the switch too.
            visible_seen["radioOn"] = visible_seen["state"]
        if operation in _ALREADY_IN_STATE_OPERATIONS and visible_seen.get("changed") is False:
            # v3 r6 lectores (t2-r4 c15 «turn bluetooth on» with it already on): the radio was already in the state
            # asked for and nothing was switched; the reply says so («ya estaba encendido»), never «lo encendí».
            visible_seen["alreadyInState"] = True
        held_state = (
            situation.get("verified") is True
            and situation.get("succeeded") is True
            and visible_seen.get("reachedState") is True
        )
        if held_state:
            # Ronda 22 (r18 t4-c07, t1-c13 «Creé la carpeta» over a folder that existed): a verified mutation whose
            # receipt found the state already there (reachedState) changed nothing; the reply says it was so.
            visible_seen["alreadyInState"] = True
        if (
            situation.get("verified") is True
            and situation.get("succeeded") is True
            and not held_state
            and (
                merged_seen.get("applied") is True
                # WALLPAPER2039 (notebook, 2026-09-22): the typed tools' receipts
                # are the postread of the change (colour, zip, file, radio…) and
                # carry no «applied» flag, so «I set the wallpaper to solid red»
                # died as reversed_result under the read-only heuristic.
                or operation in _TYPED_TRANSITION_OPERATIONS
            )
        ):
            # An observed, verified transition is not a read-only snapshot.
            # Preserve its authority before internal status fields are removed.
            payload["effect"] = "applied"
        clock = _local_clock_from_observed(visible_seen)
        place_clock = _place_clock_facts(merged_seen, user_text, language)
        if place_clock is not None:
            # The time of another place is its own fact set; this PC's clock is
            # not the answer and the zone identifiers are not words to say.
            payload.update(place_clock)
            visible_seen.pop("place", None)
            clock = None
        for key in (
            "localTime",
            "utc",
            "localUtcOffsetMinutes",
            "version",
            "operation",
            "targetId",
            "windowId",
            "endpointIdHash",
            "state",
            "verified",
            "succeeded",
            "kind",
            "polarity",
        ):
            visible_seen.pop(key, None)
        if visible_seen.get("clientOpened") is False:
            # D59 §1: a messaging client that was already open is no news to the person.
            visible_seen.pop("clientOpened")
        if (
            _window_titles_quiet
            and isinstance(visible_seen.get("windows"), list)
            and not asks_to_name_windows(user_text)
        ):
            # Ronda 22 (r18 t4-c19 «ponme el navegador y el word uno al lado del otro»: every draft of the failed
            # mission carried «Verification page | Example Platform» and the other titles). A window read of a
            # mission that did not complete, or one an effect after it needed, travels without titles (its count,
            # state and place stay); its titles still when the request asks what the windows are or show.
            visible_seen["windows"] = [
                {key: value for key, value in window.items() if key != "title"} if isinstance(window, dict)
                else window
                for window in visible_seen["windows"]
            ]
        if isinstance(visible_seen.get("windows"), list):
            # The canonical snapshot stays unchanged. Describe its Boolean
            # meaning to the narrator: the short API label leaked into Spanish
            # prose. Activation does not establish z-order above topmost windows.
            visible_seen["windows"] = [
                {
                    ("is_current_window_for_user_interaction" if key == "foreground"
                     and isinstance(value, bool) and "is_current_window_for_user_interaction" not in window
                     else key): _window_title_as_shown(value) if key == "title" else value
                    for key, value in window.items() if key != "windowId"
                }
                if isinstance(window, dict)
                else window
                for window in visible_seen["windows"]
            ]
        if clock:
            if not asks_calendar_part(user_text) or names_the_time(user_text):
                payload["clock"] = clock
            target = countdown_target(user_text)
            local = _local_datetime_from_observed(merged_seen)
            later = clock_later_asked(user_text)
            if later is not None and local is not None:
                # M40: the clock later on is arithmetic on the observed clock, done here; the narrator copies it.
                then = local + timedelta(minutes=later[1])
                payload["clock"] = f"{then.hour:02d}:{then.minute:02d}"
            if target is not None and local is not None:
                # CLOCK1327 H0399: the remaining time is arithmetic on the
                # observed clock, done here; the narrator copies the figures.
                payload["countdown"] = _countdown_facts(local, target, language)
            if asks_calendar_part(user_text):
                local = _local_datetime_from_observed(merged_seen)
                if local is not None:
                    payload.update(_calendar_facts(local, user_text, language))
        if visible_seen:
            payload["seen"] = visible_seen
    _ = seen
    if cause_key != "acting":
        cause = _cause_in_prose(str(cause_value), language)
        if cause and cause_key not in {"mission_failed", "mission_completed"}:
            # Status codes name the resulting state, not the reason it happened.
            # Labelling cancellation as a cause made the model invent why it stopped.
            key = "state" if situation.get("kind") == "status" else "cause"
            payload[key] = cause
    reason = situation.get("reason")
    if isinstance(reason, str) and reason.lstrip().startswith(("{", "[")):
        try:
            reason = json.loads(reason)
        except json.JSONDecodeError:
            reason = None
    # MissionNarration serializa el fallo del paso dentro de reason. Conserva
    # esos hechos con la misma proyección; nunca envíes el JSON crudo como prosa.
    if isinstance(reason, dict) and _reason_depth < 8:
        reason_facts = _compose_situation_payload(
            reason, language, _reason_depth=_reason_depth + 1, _window_titles_quiet=True
        )
        if reason_facts:
            payload["reason"] = reason_facts
        if reason_facts.get("cause") == _CAUSE_FACT["wifi_place_unknown"]:
            # REOPEN1957 H0170/H0376: the labels of the saved networks are the
            # facts the question needs; the opaque ids are not words.
            profiles = _merged_observed(situation).get("profiles")
            payload.pop("completedStepsInOrder", None)
            labels = [
                str(item.get("label")).strip()
                for item in (profiles if isinstance(profiles, list) else [])
                if isinstance(item, dict) and str(item.get("label") or "").strip()
            ]
            place = effect_intent.wifi_place_request(user_text or "")
            payload["seen"] = {"savedNetworks": labels[:20], "place": place or "casa"}
    elif isinstance(reason, str) and reason.strip():
        payload["reason"] = _cause_in_prose(reason, language)
    step = situation.get("step")
    if cause_key != "acting" and isinstance(step, int) and not isinstance(step, bool) and step > 0:
        payload["step"] = step
    if reading.has(INTENT_CONTINUE_CONSTRAINT):
        payload["opening"] = "none"
    if reading.has(INTENT_NEGATIVE_CONSTRAINT):
        # «No abras la Calculadora ahora» pide lo mismo que «no abras
        # nada»: la apertura queda fijada aunque nombre la aplicación.
        payload["opening"] = "none"
    if kind == "conversation" and reading.has(INTENT_REFUSE):
        # Una pregunta por los límites no recibe la lista de capacidades: con
        # ella delante, el modelo la negaba entera («I will never open or close
        # apps…»), que es exactamente lo contrario de la verdad.
        payload["beyond"] = "none"
    elif kind == "conversation" and reading.has(INTENT_CAPABILITY):
        served = _capability_phrases(capabilities, language)
        if served:
            # Una frase no enumera treinta familias. Se nombran las primeras
            # del catálogo servido; que hay más lo dice la instrucción, no un
            # campo del payload que el modelo copiaba tal cual.
            payload["can"] = served[:CAPABILITY_SAMPLE]
    choices = situation.get("choices")
    if isinstance(choices, list) and choices:
        # Recovery can offer continue/retry rather than confirm/cancel. Keep
        # every supplied decision, using the same localization as validation.
        payload["choices"] = _localized_confirmation_words(choices, language)
    # The typed operation scopes its result or failure. Without it, a failed
    # memory save was attributed to the greeting in the same user request.
    # Preserve supplied identity; never infer an operation from the request.
    if operation and isinstance(situation.get("operation"), str):
        payload["operation"] = operation
    if situation.get("verified") is True and situation.get("succeeded") is True:
        payload = project_window_inventory(payload, user_text)
    results_text = _search_results_text(payload)
    if results_text and user_text:
        # M62 (v3e2-final F-w13-t2 «y si cargo 40 litros cuanto me sale» → «…$73.000 por 40 litros», a full tank's
        # price): what the asked quantity costs at the unit price read is computed here; the narrator copies it.
        totals = semantic_quantities.priced_totals(user_text, results_text, language)
        if totals:
            payload["calculation"] = [item.sentence for item in totals[:3]]
        # M92 (DEV-D v3u D-w01-t3 «pa 3 litros» over «sal por litro … es de 10 gramos»): a per-unit rule read, applied
        # to the quantity asked, is computed here too.
        rated = semantic_quantities.rated_totals(user_text, results_text, language)
        if rated:
            payload["rule_calculation"] = [item.sentence for item in rated[:3]]
    return payload


def _microphone_state_words(muted: bool, language: str) -> str:
    """M69: the microphone's mute flag said as its state, never as a bare boolean."""

    if language == "en":
        return "muted: silenced, not picking up sound" if muted else "active: on, not muted, picking up sound"
    return "silenciado: no capta sonido" if muted else "activo: encendido, sin silenciar, capta sonido"


def _visible_compose_facts(prompt_facts: dict) -> dict | None:
    if not isinstance(prompt_facts, dict):
        return None
    inner = prompt_facts.get("situation")
    if isinstance(inner, dict):
        return inner
    visible = {
        key: value
        for key, value in prompt_facts.items()
        if key not in {"situation", "previous_dialogue_for_references_only"}
        and value not in (None, "", [], {})
    }
    return visible or None


def _compose_user_content(
    user_text: str,
    prompt_facts: dict,
    language_contract: str,
    *,
    include_request: bool = True,
) -> str:
    """Contenido de usuario del compositor. Un saludo con petición la conserva.

    La heurística anterior aceptaba cualquier inicio hey/hi/hello de menos de
    28 caracteres y devolvía sólo los hechos: «hey, close Paint» y «hey, what
    can you do» perdían el pedido antes de llegar al modelo.
    """

    # Progress narrates current activity, not an unexecuted requested goal.
    # The original request still determines language and all policy checks.
    # Preserve the speaker of the actual user message. Quoting the request
    # under an internal narrator label made an account read answer "quien soy"
    # as the assistant ("Soy..."). The same literal request binds correctly
    # without changing the facts, the language contract or the retry path.
    parts = [user_text] if include_request else []
    visible = _visible_compose_facts(prompt_facts)
    if visible:
        parts.append("situation: " + json.dumps(visible, ensure_ascii=False))
    dialogue = prompt_facts.get("previous_dialogue_for_references_only")
    if dialogue:
        # Published prose supplies conversational references, not observations.
        # Keep it outside situation, which the composer treats as evidence.
        parts.append(
            "previous_dialogue_for_references_only: "
            + json.dumps(dialogue, ensure_ascii=False)
        )
    if language_contract:
        parts.append(language_contract)
    return "\n".join(parts)


_FEMININE_APP_NAMES = frozenset({"calculadora", "terminal"})


def _app_is_feminine(name: str) -> bool:
    return name.casefold() in _FEMININE_APP_NAMES


# Live 2026-10-07 (x12 «abrí la calculadora» → «Abrí la calculadora y ahora está ejecutándose en la ventana con el
# handle 4722336.»): a window handle or a process id is the adapter's, never what the person sees, unless asked for.
_INTERNAL_IDENTIFIER_KEYS = ("windowHandle", "hwnd", "handle", "processId", "pid", "threadId")


def identifier_is_plumbing(operation: str) -> bool:
    """An operation whose window handle or process id only says which window it acted on (opening an application, the
    computer-use engine, opening a file or a folder); a window or process inventory lists them as its content."""

    return operation in {"app.open", "app.close", "mission.computer.use", "file.open"} or operation.startswith(
        "filesystem."
    )
