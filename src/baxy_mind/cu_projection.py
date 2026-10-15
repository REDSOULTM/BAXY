"""What the composer may say about a mission (contract §4.5): the observed facts projected for it, a step
described, a vague stop refined by what its steps observed, and the instruction the composer is given.
"""

from __future__ import annotations

import re
from pathlib import PureWindowsPath
from typing import Any

from . import operation_floor
from .semantic.colours import shade_of
from .semantic.chats import last_written
from .semantic.missions import QUESTION_MARK, fold
from .semantic.cu_tipos import OPEN_FILE_GOAL
from .cu_vocabulary import _evidence_rules, _floor_name
from .cu_goals import colour_goal
from .cu_history import _may_have_acted
from .cu_open_file import file_not_opened_cause


# The words a click step is told with, done and tried (operation_floor.v1.json «computerUse.stepWords»).
_STEP_WORDS: dict[str, dict[str, str]] = operation_floor.floor_data()["computerUse"]["stepWords"]


def describe_step(step: dict, language: str) -> str:
    operation = str(step.get("operation") or "")
    if operation == "input.visible.click":
        # Pasada r18 (t-menu-2): a step whose receipt does not hold is told with the verb of trying, never of doing.
        tried = "ok" in step and step.get("ok") is not True
        words = _STEP_WORDS[("en" if language == "en" else "es") + ("Tried" if tried else "")]
        manner = step.get("manner")
        return words[manner if manner in ("open", "menu", "double") else "click"].replace(
            "{label}", str(step.get("label")))
    if operation == "input.key.press":
        return (f"pressed {step.get('key')}" if language == "en" else f"tecla {step.get('key')}")
    if operation == "input.text.type":
        # Falsos éxitos v3 M4 (t-form-2): the text is the effect a failed mission left; the final names it. Encargo H1
        # (tanda fin1 t2-c04 t4: «escribió «100»» among the failed steps of a field never found): a text no key
        # reached (refused, its effect not uncertain) is told with the verb of trying, as a click is.
        typed = _floor_name(step.get("text"))
        tried = "ok" in step and step.get("ok") is not True and step.get("effectUncertain") is not True
        # Encargo K (banco def1 x8: «escribí «125+75»» while the Calculator got «25+75»): a text the App's look after it
        # read cut («arrived» false, ComputerUseMission.ArrivedCut) is told with the verb of trying; the screen says the rest.
        tried = tried or step.get("arrived") is False
        if typed:
            if tried:
                return f"tried to type «{typed}»" if language == "en" else f"intentó escribir «{typed}»"
            return f"typed «{typed}»" if language == "en" else f"escribió «{typed}»"
        if tried:
            return "tried to type the text" if language == "en" else "intentó escribir el texto"
        return "typed the text" if language == "en" else "escribió el texto"
    if operation == "input.scroll":
        return "scrolled" if language == "en" else "desplazó la vista"
    if operation == "app.open":
        if step.get("placeOpened") is True:
            # Estabilización, encargo C (banco f2c lug-2: «trajo la aplicación al frente» became «Lo hice en «Steam»»):
            # an opening that opened a place by its address says so, with what it searched (a game's number is no word).
            value = _floor_name(step.get("placeValue"))
            if value and not value.isdigit():
                return f"searched «{value}» by its address" if language == "en" else f"buscó «{value}» por su dirección"
            return "opened the place by its address" if language == "en" else "abrió el lugar por su dirección"
        # Encargo H1 (tandas fin1/fin2 t3-c02 t1: Excel was not open, the mission started it and its final only said
        # «Llegué a Excel»): an opening that started the application (receipt «alreadyRunning» false) is told as such.
        named = _floor_name(step.get("appId") or step.get("name"))
        if step.get("ok") is True and step.get("alreadyRunning") is False and named:
            return f"opened «{named}»" if language == "en" else f"abrió «{named}»"
        return "brought the application to the front" if language == "en" else "trajo la aplicación al frente"
    if operation == "file.open":
        # Review of cu-v3-abrir-archivo (finding 4): never the operation's own name in a final.
        named = _floor_name(step.get("name"))
        if step.get("ok") is True:
            return (f"opened «{named}»" if language == "en" else f"abrió «{named}»") if named else (
                "opened the file" if language == "en" else "abrió el archivo")
        return (f"tried to open «{named}»" if language == "en" else f"intentó abrir «{named}»") if named else (
            "tried to open the file" if language == "en" else "intentó abrir el archivo")
    return operation


# The typed stop reasons as facts the final can state (the model words them; «operación» is a forbidden term in finals,
# so no cause says it). Data shared with the App's floor (operation_floor.v1.json «computerUse.causes»).
_STOP_CAUSES: dict[str, dict[str, str]] = operation_floor.floor_data()["computerUse"]["causes"]


def project_seen(observed: dict, language: str) -> dict[str, object]:
    """What the composer may say about a mission: only what the loop observed."""

    raw_steps = observed.get("steps")
    steps: list[Any] = raw_steps if isinstance(raw_steps, list) else []
    done = [step for step in steps if isinstance(step, dict) and step.get("ok") is True]
    failed = [step for step in steps if isinstance(step, dict) and step.get("ok") is not True]
    raw_window = observed.get("window")
    window: dict[str, Any] = raw_window if isinstance(raw_window, dict) else {}
    goal = observed.get("goal")
    question = None
    if isinstance(goal, str) and QUESTION_MARK in goal:
        # «… y decime si el modo es claro u oscuro»: the person's question about the window at the end.
        goal, question = goal.split(QUESTION_MARK, 1)
    seen: dict[str, object] = {
        "goal": goal,
        "reached": observed.get("reached") is True,
        "stepsDone": [describe_step(step, language) for step in done][:8],
        # Revisión U, H3: a protected window's title (an editor's file, a console's command) never reaches the
        # writer nor names the place; it is said by its application (protectedWindow below).
        "windowTitle": None if window.get("protected") is True else window.get("title"),
        "joined": observed.get("joined") is True,
    }
    if question:
        seen["question"] = question
    if observed.get("application"):
        seen["application"] = observed.get("application")
    if failed:
        seen["stepsFailed"] = [describe_step(step, language) for step in failed][:4]
    if observed.get("evidence"):
        seen["evidence"] = observed.get("evidence")
    if observed.get("satisfiedBy"):
        seen["satisfiedBy"] = observed.get("satisfiedBy")
    if _floor_name(observed.get("focusedField")):
        # Revisión 1 de r24b (B3): the field the window had the keyboard in is a fact of the window; the final of a
        # search opened names it (computerUse.searchOpened), so its words are grounded (ungrounded_word).
        seen["focusedField"] = _floor_name(observed.get("focusedField"))
    shade =_chosen_shade(goal, done) if seen["reached"] else None
    if shade is not None:
        seen["chosenShade"] = shade
    if isinstance(observed.get("screen"), dict):
        screen = dict(observed["screen"])
        # Revisión 2 de la ronda 22: which lines are a control's label is for the mind's own readers
        # (``semantic.dialogue._screen_parts``), never a fact the writer words.
        screen.pop("controlLines", None)
        if isinstance(screen.get("values"), list):
            # Pasada v3 r9 (v3-43): a page still loading showed only its «Cargando» bar, and the plan asked was
            # answered «Cargando». A loading indicator is no fact of the window (data «computerUse.loading»).
            loading = re.compile(operation_floor.floor_data()["computerUse"]["loading"])
            screen["values"] = [
                item for item in screen["values"]
                if not (isinstance(item, dict) and loading.search(fold(item.get("name"))))
            ]
        groups = screen.pop("groups", None)
        chat_lines = screen.pop("chatLines", None)
        if isinstance(chat_lines, list) and question and last_written(question) is not None:
            # Encargo IMP4: the lines of a chat drawn without an accessible tree, with their places, for the same question.
            seen["chatLines"] = [line for line in chat_lines if isinstance(line, dict)]
        if isinstance(groups, list) and question and last_written(question) is not None:
            # Imprescindibles de mensajería: the entries of a conversation the window names (the App's «groups») are a
            # fact only for a question about what was last written there; every other mission's facts stay as they were.
            seen["messages"] = [entry for entry in groups if isinstance(entry, str)][-8:]
        seen["screen"] = screen
    cover = window.get("coveredBy")
    if (
        observed.get("stoppedBy") == "computer_use_window_covered"
        and isinstance(cover, dict) and (cover.get("title") or cover.get("process"))
    ):
        # Ronda 20 P5 (pasada r18 v3-16: «…porque la pantalla se quedó bloqueada» over a stop on no visible step, with
        # the covering window among the facts): the window that covers the application is a fact of the window, given
        # to the writer only when it is the cause the mission stopped on.
        seen["coveredBy"] = str(cover.get("title") or cover.get("process"))
    if observed.get("stoppedBy"):
        seen["stoppedBy"] = observed.get("stoppedBy")
        seen["stoppedBecause"] = _STOP_CAUSES.get(str(observed.get("stoppedBy")), {}).get(
            "en" if language == "en" else "es", str(observed.get("stoppedBy")).replace("_", " ")
        )
        if observed.get("stoppedBy") == "computer_use_window_covered" and seen.get("coveredBy"):
            seen["stoppedBecause"] = operation_floor.floor_data()["computerUse"]["coveredBy"][
                "en" if language == "en" else "es"
            ].format(window=seen["coveredBy"])
        protected_app = _floor_name(re.sub(r"(?i)\.exe$", "", str(window.get("process") or "")))
        if observed.get("stoppedBy") == "computer_use_window_protected" and protected_app:
            # Estabilización U (identity live check: «Activa el modo accesible…» stopped on BAXY's own window
            # and the final said «la ventana protegida era un editor de código»): the cause named a list of
            # kinds and the writer picked one. The protected window is said by its application (its process,
            # as «Seguridad v2» identifies it), never by its title: an editor's or a console's title carries
            # the person's paths, hosts and commands (revisión U, H3).
            seen["stoppedBecause"] = operation_floor.floor_data()["computerUse"]["protectedWindow"][
                "en" if language == "en" else "es"
            ].replace("{app}", protected_app)
        if observed.get("stoppedBy") == "computer_use_seen_not_done" and observed.get("seenNotDone"):
            # Seen, not done (falsos éxitos v3 M1): what the model cited already showed or was typed by BAXY.
            seen["seenNotDone"] = observed.get("seenNotDone")
        gate = observed.get("gate") if isinstance(observed.get("gate"), dict) else {}
        gate_text = _floor_name(gate.get("text"))
        gates = operation_floor.floor_data()["computerUse"]["appGate"]
        if (observed.get("stoppedBy") == "computer_use_app_gate" and gate_text
                and isinstance(gates.get(str(gate.get("kind"))), dict)):
            # v3 limits (M2): the gate said with what the screen writes (live v3-05: Outlook's account wizard), and
            # what was pressed on it: nothing, or its «Ahora no» after which it stayed.
            lang = "en" if language == "en" else "es"
            floor = operation_floor.floor_data()
            quote = floor["templates"][lang]["quote"]
            tails = floor["computerUse"]["appGateTail"]
            pressed = _floor_name(gate.get("pressed"))
            seen["gate"] = gate_text
            if pressed:
                seen["gatePressed"] = pressed
            tail = (tails["pressed"][lang].replace("{pressed}", quote.format(value=pressed)) if pressed
                    else tails["untouched"][lang])
            seen["stoppedBecause"] = (
                gates[str(gate.get("kind"))][lang].replace("{text}", quote.format(value=gate_text)).replace("{tail}", tail)
            )
        refined = refined_stop(observed)
        if refined:
            # Ronda 20 P5 (pasada r18 v3-29): «no vi un control» when the search found nothing; the cause is what the
            # steps observed (data «computerUse.refinedStops»).
            seen["stoppedBecause"] = operation_floor.floor_data()["computerUse"]["refinedStops"][refined][
                "en" if language == "en" else "es"
            ]
        missing = _floor_name(observed.get("missingPlace"))
        if observed.get("stoppedBy") == "computer_use_place_not_found" and missing:
            # Searched by name in the window and not found (live n5: «Wi-Fi» on a PC without Wi-Fi).
            floor = operation_floor.floor_data()
            lang = "en" if language == "en" else "es"
            seen["stoppedBecause"] = floor["computerUse"]["placeNotFound"][lang].format(
                place=floor["templates"][lang]["quote"].format(value=missing)
            )
        candidates = [
            name for name in (_floor_name(item) for item in observed.get("destinationCandidates") or () if isinstance(item, str))
            if name
        ] if isinstance(observed.get("destinationCandidates"), list) else []
        if observed.get("stoppedBy") == "computer_use_destination_ambiguous" and len(candidates) > 1:
            # Ronda 21, destino por contenido: the windows the request fits, by their titles, so the person says which.
            # Twin of the App's OperationFloor.
            floor = operation_floor.floor_data()
            lang = "en" if language == "en" else "es"
            quote = floor["templates"][lang]["quote"]
            seen["destinationCandidates"] = candidates
            seen["stoppedBecause"] = floor["computerUse"]["destinationCandidates"][lang].replace(
                "{windows}", ", ".join(quote.format(value=name) for name in candidates)
            )
        if observed.get("stoppedBy") == "computer_use_file_not_opened":
            # Review of cu-v3-abrir-archivo (finding 4): the file not opened is said with its cause.
            named = _file_not_opened(observed)
            if named is not None:
                seen["stoppedBecause"] = file_not_opened_cause(
                    str(observed.get("fileNotOpened") or "other"), named[0], named[1], language)
    raw_subgoals = observed.get("subgoals")
    if isinstance(raw_subgoals, list) and raw_subgoals:
        subgoals = [
            {"goal": item.get("goal"), "application": item.get("application"), "reached": item.get("reached") is True}
            for item in raw_subgoals[:8] if isinstance(item, dict)
        ]
        raw_items = [item for item in raw_subgoals[:8] if isinstance(item, dict)]
        for position, (said, item) in enumerate(zip(subgoals, raw_items)):
            # Regresiones r4 (v2-c2): what carried a number in a part's window when it was reached (a calculator's
            # display) is that part's fact; the chain's last window never shows it.
            numbers = [value for value in item.get("numbers") or () if isinstance(value, str)]
            if numbers:
                said["numbers"] = numbers
            # Ronda 24b (x10): the place as the window wrote it when the part was reached, and whether an act got it
            # there; reached with no act on a strong term (``_strong_arrival``), it was already there. Revisión 1 (B4):
            # no act of the mission up to that part's close (``_mission_acted_until``: an earlier part's click may have
            # put the window there) and no opening that launched the application (``_mission_launched``).
            if isinstance(item.get("arrivedAs"), str) and item["arrivedAs"].strip():
                said["arrivedAs"] = item["arrivedAs"].strip()
            if isinstance(item.get("acted"), bool):
                said["acted"] = item["acted"]
                if said["reached"] and item["acted"] is False and _strong_arrival(item.get("satisfiedBy")) and not (
                    _mission_launched(observed) or _mission_acted_until(observed, raw_items, position)
                ):
                    said["alreadyThere"] = True
        seen["subgoals"] = subgoals
        unreached = next((item for item in subgoals if not item["reached"]), None)
        if unreached is not None:
            seen["firstUnreached"] = unreached["goal"]
    return seen


def refined_stop(observed: dict) -> str:
    """Ronda 20 P5: the cause a vague stop («computerUse.refinedStops.stops») had by what its steps observed, as a key
    of that data: «emptySearch» when a search was made and found nothing — text typed and, on it or on the key pressed
    right after it, a line saying nothing was found among what appeared (data «evidence.noResults» or
    «emptySearch.afterSearch») — and no step after it but one of «emptySearch.passes»; "" otherwise. A click after the
    search left it, and a line with no search before it is a state of the window (revisión 1 de r20 P5, hallazgo 4).
    Twin of OperationFloor.RefinedStop."""

    rule = operation_floor.floor_data()["computerUse"]["refinedStops"]
    if str(observed.get("stoppedBy") or "") not in rule["stops"]:
        return ""
    raw = observed.get("steps")
    done = [step for step in raw if isinstance(step, dict) and step.get("ok") is True] if isinstance(raw, list) else []
    empty = rule["emptySearch"]
    nothing_found = [re.compile(_evidence_rules()["noResults"]), re.compile(empty["afterSearch"])]
    for index in range(len(done) - 1, -1, -1):
        step = done[index]
        operation = step.get("operation")
        appeared = step.get("appeared") if isinstance(step.get("appeared"), list) else []
        if any(isinstance(line, str) and any(rx.search(fold(line)) for rx in nothing_found) for line in appeared):
            searched = operation == "input.text.type" or (
                operation == "input.key.press" and index > 0 and done[index - 1].get("operation") == "input.text.type"
            )
            return "emptySearch" if searched else ""
        if operation not in empty["passes"]:
            return ""
    return ""


def _file_not_opened(observed: dict) -> tuple[str, str | None] | None:
    """(the file's name, the application asked) of the sub-goal «abrir el archivo …» a mission stopped on: the first
    one not reached of a chain, or the mission's own goal."""

    raw = observed.get("subgoals")
    parts = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    candidates = [item for item in parts if item.get("reached") is not True] or [observed]
    for item in candidates:
        goal = str(item.get("goal") or "").split(QUESTION_MARK)[0]
        if goal.startswith(OPEN_FILE_GOAL):
            target = goal[len(OPEN_FILE_GOAL):].strip()
            name = PureWindowsPath(target).name or target
            application = item.get("application") or observed.get("application")
            return name, str(application) if application else None
    return None


def _chosen_shade(goal: object, done: list[dict]) -> dict[str, str] | None:
    """{asked, chosen}: the colour the goal chose and the swatch clicked for it when that swatch is one of its shades
    («Añil» for «azul»), from the last verified click; None otherwise."""

    asked = colour_goal(goal) if isinstance(goal, str) else None
    if asked is None:
        return None
    for step in reversed(done):
        if step.get("operation") != "input.visible.click":
            continue
        for value in (step.get("name"), step.get("label")):
            if isinstance(value, str) and shade_of(asked, value):
                return {"asked": asked, "chosen": " ".join(value.split())}
        return None
    return None


def compose_instruction(seen: dict, language: str) -> str:
    del language
    return _question_instruction(seen) + _result_instruction(seen)


def _question_instruction(seen: dict) -> str:
    if not seen.get("question"):
        return ""
    return (
        "seen.question is what the person asked about the window once the mission was done: answer it FIRST, "
        "only from seen.screen and seen.evidence, saying the value written there; when they do not show the answer, "
        "or the mission did not reach its goal, say you could not see it, never guess. Then: "
    )


# The voice of a mission final is BAXY's own (documentacion/00_IDENTIDAD.md): a companion who confirms the observable
# state, warm and brief, speaking informally to the person; a failure is said plainly with its cause, without apology.
_SPEAKER = (
    "Speak as the one who acted, in the FIRST PERSON (never the third person, never your own name, never «you» for "
    "your own acts), informally and warmly, in the person's language, in {length}. "
)
# What the final confirms depends on what the goal's check read: a place reached or a value read is confirmed as the
# window shows it; a key pressed or a text typed is only said done (its effect was never read).
_CONFIRM_STATE = (
    "Confirm the state the window shows now (where it is, the value asked), not the clicks, keys or steps you took; "
)
_DONE_ONLY = "Say only that it is done in that app, never what it caused, nor the keys or steps you took; "
_MIXED = (
    "For a part that went somewhere or read a value, confirm the state the window shows now; for a part that pressed "
    "a key or typed, say only that it is done in that app, never what it caused; never the clicks, keys or steps; "
)
_NO_META = (
    "never mention the mission, the evidence, the check, the screen or the view as such. A goal «ir a X» only went to "
    "X: never say you set, created, started, turned on or changed anything there. "
)
_ACT_ONLY_GOAL = re.compile(r"^(?:apretar|escribir|enviar)\b")


def _acts_only(goal: object) -> bool:
    """A goal whose check reads nothing of the window: a key to press, a text to type, what was written to send."""

    return isinstance(goal, str) and QUESTION_MARK not in goal and _ACT_ONLY_GOAL.match(fold(goal).strip()) is not None


def _voice(goals: list[object], question: bool, length: str = "ONE short sentence") -> str:
    acting = [_acts_only(goal) for goal in goals] or [False]
    if question or not any(acting):
        body = _CONFIRM_STATE
    elif all(acting):
        body = _DONE_ONLY
    else:
        body = _MIXED
    return _SPEAKER.format(length=length) + body + _NO_META


def _result_instruction(seen: dict) -> str:
    if seen.get("subgoals"):
        goals = [item.get("goal") for item in seen["subgoals"] if isinstance(item, dict)]
        length = "ONE short sentence" if seen.get("reached") else "at most TWO short sentences"
        chained = (
            "This result is a computer-use mission of several parts done in order: seen.subgoals lists each part "
            "(goal, application, reached true or false). " + _voice(goals, bool(seen.get("question")), length)
            + "Name the parts briefly in their order only when there are several applications or places. "
        )
        if seen.get("reached"):
            return chained + (
                "Every part was reached. When seen.evidence names the result, say its text as it is written. "
                "seen.joined says whether a voice channel or call was joined: say you joined only if it is true. "
                "Never add parts, steps, times or results that are not in seen."
            )
        return chained + (
            "Not every part was reached: lead with what you could not do (seen.firstUnreached), said in the first "
            "person singular (Spanish «pude», never «pudiste»: you acted, not the person), and its cause "
            "(seen.stoppedBecause, reworded lightly, never «operación» or «operation»), plainly and without apology; "
            "then, briefly, the parts that were done. Never say that a part with reached false was done, never say "
            "the whole request succeeded, and never invent a cause that is not in seen."
        )
    if seen.get("reached"):
        return (
            "This result is a computer-use mission that REACHED its goal: seen.goal is what was asked, "
            "seen.stepsDone the acts done in order on the window seen.windowTitle, seen.evidence the text on screen "
            "that proves it when present, seen.screen what the window showed at the end (seen.screen.numbers: the "
            "controls and lines carrying a number, such as a display or a counter; seen.screen.values: its fields "
            "and chosen items; seen.screen.lines: a few lines). " + _voice([seen.get("goal")], bool(seen.get("question")))
            + (
                "" if _acts_only(seen.get("goal")) and not seen.get("question") else
                "When the goal asked for a calculation, a number or a value, lead with it, said exactly as the matching "
                "entry of seen.screen.numbers or seen.screen.values writes it; do not list the other lines of the window. "
            )
            + (
                "The window had no colour named seen.chosenShade.asked: you chose its closest shade, the swatch "
                "seen.chosenShade.chosen. Say that swatch's name exactly as written and that it is the asked colour of "
                "the palette (as in «Elegí Añil, el azul de la paleta»); never say you chose a swatch named "
                "seen.chosenShade.asked. " if seen.get("chosenShade") else ""
            )
            + "seen.joined says whether a voice channel or call was joined: say you joined only if it is true. Never "
            "add steps, times or results that are not in seen: a time or a date only as seen.screen writes it, never "
            "the part of the day (morning, afternoon, a.m., p.m.) unless it is written there."
        )
    return (
        "This result is a computer-use mission that did NOT reach its goal: seen.goal is what was asked, "
        "seen.stepsDone what was done before stopping, seen.stepsFailed what could not be done, "
        "seen.stoppedBecause the cause in the person's words. In ONE short sentence, in the person's language and "
        "in the FIRST PERSON, say plainly that you could not do it and why (seen.stoppedBecause, reworded lightly, "
        "never «operación» or «operation»), without apology and without listing steps: say first, in the first "
        "person singular, that you could not (Spanish «pude», never «pudiste»: you acted, not the person). Never say "
        "it succeeded and never invent a cause that is not in seen."
    )


def _mission_launched(observed: dict) -> bool:
    """Revisión 1 de la ronda 24b (B3): an opening of the mission started the application (``alreadyRunning`` not
    true): the place it shows on its first look is where BAXY's launch left it, never where the person already was
    (the rule of ``_place_said``, review r10a finding 1). Twin of the App's OperationFloor.MissionLaunched."""

    steps = observed.get("steps") if isinstance(observed.get("steps"), list) else []
    return any(
        isinstance(step, dict) and step.get("operation") == "app.open" and step.get("alreadyRunning") is not True
        for step in steps
    )


def _mission_acted_until(observed: dict, items: list[dict], position: int) -> bool:
    """Revisión 1 de la ronda 24b (B4: «ir a opciones; luego ir a general; luego ir a privacidad», «General» selected
    when the click on «Opciones» opened the dialog): whether any act of the mission came before the close of the part
    at ``position``: an earlier part that acted, or a step of the mission (``_may_have_acted``) of that part or an
    earlier one (its ``subgoal``, which a chained mission writes on every step, its opening's too). A place an act of
    the mission put on screen was never «already» there (the rule of ``_place_said``). Twin of the App's
    OperationFloor.MissionActedUntil."""

    if any(item.get("acted") is True for item in items[:position]):
        return True
    steps = observed.get("steps") if isinstance(observed.get("steps"), list) else []
    for step in steps:
        part = step.get("subgoal") if isinstance(step, dict) else None
        if _may_have_acted(step) and isinstance(part, int) and not isinstance(part, bool) and part <= position:
            return True
    return False


def _strong_arrival(satisfied_by: object) -> bool:
    """Ronda 24b (x10): a term that proves by itself where the window is: a mark of the navigation row, the window's or
    the page's title, a control shown selected or current. A page read by its header or a resemblance (``page:``,
    ``similar:``) is weak, and a part reached on it with no act is never told as «ya estaba»."""

    if not isinstance(satisfied_by, str) or not satisfied_by.strip() or satisfied_by == "model_evidence":
        return False
    for atom in (part.strip() for part in satisfied_by.split("&") if part.strip()):
        kind, _, rest = atom.partition(":")
        kind = kind.strip().lower()
        if kind in {"mark", "title"} or (kind == "control" and rest.rsplit(":", 1)[-1] in {"selected", "current"}):
            return True
    return False
