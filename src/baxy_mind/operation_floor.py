"""The floor of an action: the final said from the turn's facts alone when no draft could be published.

M107 (DEV-D unseen run, 2026-10-01): twelve actions ended with no visible final («composition_failed:
no_response;retry_exhausted») — every draft was refused and the last resort had nothing for their operation — and two
more on the M102 path that moves a notification (notification.cancel.latest then notification.schedule). An action's
result can always be said: the operation, whether it was verified, failed or left uncertain, and what was observed
(the name of what was acted on, a list read, a state read after). Every word comes from data/operation_floor.v1.json —
one plain clause per catalog operation — and from the observation; nothing the result did not hold is stated. The App
reads the same data (Baxy.App.OperationFloor) and builds the same sentence when the mind returned none.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).resolve().parent / "data" / "operation_floor.v1.json"
# Estabilización F: a plan's step left unconfirmed (result_unverified) goes, like a failed one, with its own facts.
_MISSION_CAUSES = frozenset({"mission_completed", "mission_failed", "result_unverified"})
# An act left undone because the person cancelled it at its confirmation (a plan's, a private memory operation's).
_CANCELLED_CAUSES = frozenset({"remaining_steps_cancelled", "memory_cancelled"})
_LONGEST_NAME = 120
_LONGEST_CONTENT = 200
_LISTED_NAMES = 3


@lru_cache(maxsize=1)
def floor_data() -> dict:
    return json.loads(_DATA.read_text(encoding="utf-8"))


_CLITICS = ("nos", "les", "los", "las", "me", "te", "se", "lo", "la", "le")


@lru_cache(maxsize=1)
def spanish_infinitives() -> frozenset[str]:
    """M108: the verb of every operation's plain clause («apagar», «abrir», «buscarlo» → «buscar»). The final gate
    reads a first-person future of any of them as an act promised (reply_claims.visible_reply_promises_the_act)."""

    verbs: set[str] = set()
    for entry in floor_data()["operations"].values():
        variants = (entry.get("variants") or {}).get("values") or {}
        for clause in (entry["es"][0], *(variant["es"][0] for variant in variants.values())):
            verb = clause.split()[0]
            clitic = next((c for c in _CLITICS if verb.endswith(c) and verb[: -len(c)].endswith(("ar", "er", "ir"))), "")
            verbs.add(verb[: len(verb) - len(clitic)])
    return frozenset(verbs)


def failure_sentences() -> dict[str, tuple[str, str]]:
    """The typed failures whose cause is said whole: code -> (Spanish, English). Encargo H2: a device the computer
    lacks (each «absent» code of «computerUse.limits.devices») is said with its cause, as a mission says it."""

    limits = floor_data()["computerUse"]["limits"]
    absent = {
        code: tuple(_sentence(limits[lang]["absent"].format(cause=device[lang])) for lang in ("es", "en"))
        for device in limits["devices"].values() for code in device["absent"]
    }
    return {**absent, **{code: (texts["es"], texts["en"]) for code, texts in floor_data()["failures"].items()}}


def cause_clause(code: object, english: bool) -> str:
    """The person's words for a stop cause a direct act shares with computer use («computerUse.causes»: the person
    was busy or acted during it, the window changed), or ""."""

    said = floor_data()["computerUse"]["causes"].get(str(code or "").strip().lower())
    return said["en" if english else "es"] if isinstance(said, dict) else ""


def failure_family_cause(code: object, english: bool) -> str:
    """Ronda 19 (uso real r17 t3-c07): the cause a failure code says by its family (data ``failureFamilies``), or "" for
    a code of no family. Revisión r19 (bloqueante 4): a family names what failed as well as how («…_client_not_running»,
    «app_not_found»), the whole last words of the code, so the cause speaks of the thing that failed: a bare
    «…_not_found» («spotify_exact_play_control_not_found», «shell_command_directory_not_found») names a control or a
    folder, not the act's object, and says no cause."""

    key = str(code or "").strip().lower()
    for family in floor_data()["failureFamilies"]["families"]:
        if key == family["code"] or key.endswith("_" + family["code"]):
            return family["en" if english else "es"]
    return ""


def with_family_cause(sentence: str, situation: dict, english: bool) -> str:
    """Ronda 19 (r17 t3-c07 «No pude enviar el mensaje a «ron92».», no cause): the mind's last sentence for a step that
    failed while others waited on it (a mission's failed reason, or a read that left effects undone) says the cause of
    its code's family before the full stop. The App's twin floor (OperationFloor) keeps its plain clause; an uncertain
    step keeps its own «pero no pude confirmar»."""

    if not sentence or not isinstance(situation, dict):
        return sentence
    reason = _decoded(situation.get("reason")) if situation.get("cause") == "mission_failed" else None
    step = reason if isinstance(reason, dict) and reason.get("operation") else situation
    if step is situation and not step.get("notDone"):
        return sentence
    if (_uncertain(step) and not _told_by_undone(step)) or step.get("polarity") != "failure" or situation.get("steps"):
        return sentence
    cause = failure_family_cause(step.get("error"), english)
    if not cause or not sentence.endswith("."):
        return sentence
    join = floor_data()["failureFamilies"]["join"]["en" if english else "es"]
    return sentence[:-1] + join.format(cause=cause) + "."


def _told_by_undone(step: dict) -> bool:
    """A quiet read told by the effects it left undone (``_step``): those were not done, whatever the read left."""

    return bool(_entry(step).get("quiet")) and any(isinstance(item, dict) for item in step.get("notDone") or ())


def stopped_final(step: dict, code: object, english: bool) -> str:
    """Uso real t2-r4 c01-1: a direct act stopped with a cause of «computerUse.causes» (input_user_interrupted on a
    Spotify play) is said as not done with that cause — «No pude poner la música «los bunkers»: empezaste a usar el PC
    mientras lo hacía…» —, never as a result left unconfirmed. "" when the operation has no plain clause or the code
    no cause. A step whose effect may have happened (effectUncertain) keeps the floor's own «intenté…, pero no pude
    confirmar si se hizo» before the cause: the stop is a fact, the act not done is not."""

    cause = cause_clause(code, english)
    entry = _entry(step)
    if not cause or not entry:
        return ""
    language = "en" if english else "es"
    templates = floor_data()["templates"][language]
    clause = _attempted_clause(entry, step, {}, language, templates)
    told = templates["uncertain" if _uncertain(step) else "failed"].format(clause=clause)
    return _sentence(told + templates["detail"] + cause)


def cancelled_final(situation: object, english: bool, now: datetime | None = None) -> str:
    """Ronda 28 (banco c7 t2, «no» → «no_response;retry_exhausted»): the last resort of a plan cancelled at the act
    that waited for its confirmation (data ``cancelledFloor``): every effect made before it, each with its own clause
    and receipt, and the act not made, named by its arguments or by what the step that resolved its identifier
    observed. "" for any other turn, for an act of no operation of this data, or when a step made cannot be told."""

    if not isinstance(situation, dict) or str(situation.get("cause") or "").strip().lower() != "remaining_steps_cancelled":
        return ""
    action = situation.get("cancelledAction")
    entry = _entry(action) if isinstance(action, dict) else {}
    raw = situation.get("steps") if isinstance(situation.get("steps"), list) else []
    steps = _decoded_steps(raw)
    if not entry or len(steps) != len(raw):
        return ""
    language = "en" if english else "es"
    templates = floor_data()["templates"][language]
    told = [
        _step(step, english, templates, now) for step in steps
        if step.get("readOnly") is not True and not _entry(step).get("quiet")
    ]
    if not all(told):
        return ""
    arguments = action.get("arguments") if isinstance(action.get("arguments"), dict) else {}
    arguments = {
        key: value.split(", ")[0] if key in floor_data()["cancelledFloor"]["firstPartOf"] and isinstance(value, str)
        else value for key, value in arguments.items()
    }
    identifiers = [(key, value) for key, value in arguments.items() if key.endswith("Id") and isinstance(value, str) and value]
    resolved = next(
        (seen for step in steps if any((seen := _observed(step)).get(key) == value for key, value in identifiers)), {},
    )
    left = floor_data()["cancelledFloor"][language].format(
        act=_attempted_clause(entry, {}, {**resolved, **arguments}, language, templates),
    )
    left += "".join(templates["and"] + goal for goal in _goals_left(situation.get("cancelledGoals"), language, templates))
    return _sentence(_joined(told, templates) + templates["but"] + left if told else left)


def _goals_left(goals: object, language: str, templates: dict) -> list[str]:
    """C7Y5 (banco fp c7, «no» to the voice channel of a chain «Discord → Steam»): the sub-goals of the mission the
    cancellation left undone, after the act not made (data ``cancelledFloor.rest``): a place by its name, any other goal
    quoted, each in the application it was for unless its name already says it."""

    from .cu_goals import _place_of  # cu_goals reads this module's data on import

    rest = floor_data()["cancelledFloor"]["rest"][language]
    said = []
    for item in goals if isinstance(goals, list) else []:
        goal = " ".join(str(item.get("goal") or "").split()) if isinstance(item, dict) else ""
        if not goal:
            continue
        place = _place_of(goal, [])
        clause = rest["place" if place else "goal"].format(
            place=templates["quote"].format(value=place), goal=templates["quote"].format(value=goal),
        )
        app = " ".join(str(item.get("application") or "").split())
        said.append(rest["in"].format(clause=clause, app=app) if app and app.casefold() not in goal.casefold() else clause)
    return said


def again(sentence: str, english: bool) -> str:
    """Revisión F (H2): the floor's sentence said once more, when it would repeat the last answer (data ``again``)."""

    return floor_data()["templates"]["en" if english else "es"]["again"].format(sentence=sentence)


def clarification_floor(english: bool) -> str:
    """The floor's question for a missing value no question can name in the person's words (data
    ``compositionFailures.clarification``, the App's same line)."""

    return floor_data()["compositionFailures"]["clarification"]["en" if english else "es"]


def pending_final(situation: object, english: bool) -> str:
    """Estabilización M2 (live recheck 2026-10-12: «nah» to «¿…que borro de mi memoria tu bebida favorita…?» was
    drafted «He borrado de tu memoria tu bebida favorita.» with nothing erased): the question that confirms a pending
    act (data ``asked``) or the sentence of that act cancelled (data ``cancelled``), said whole from what the act names;
    "" when its operation has no such wording."""

    if not isinstance(situation, dict):
        return ""
    if str(situation.get("cause") or "").strip().lower() == "clarification_cancelled":
        # Estabilización M3 (live 2026-10-12: «No, cancelá» to a pending question → «No pude contarte cómo salió lo que
        # pediste.»): the question the person cancelled is said dropped, with nothing done (data clarificationCancelled).
        return floor_data()["clarificationCancelled"]["en" if english else "es"]
    cancelled = str(situation.get("cause") or "").strip().lower() in _CANCELLED_CAUSES
    act = _decoded(situation.get("cancelledAction" if cancelled else "pendingAction"))
    if not isinstance(act, dict) or (not cancelled and situation.get("kind") != "confirmation"):
        return ""
    language = "en" if english else "es"
    # Encargo VZ (imp3d imp-dc-voz: «¿Quieres confirmar que entres al canal Cotele…?»): an act that goes out to the world
    # is asked in BAXY's first person from its family and the name it acts on (data «worldActAsked»).
    world = floor_data()["worldActAsked"].get(str(act.get("worldAct") or ""))
    if not cancelled and isinstance(world, dict) and (name := str(act.get("actName") or "").strip()):
        return _sentence(world[language].replace("{name}", name))
    wording = _entry({"operation": act.get("operation")}).get("cancelled" if cancelled else "asked")
    if not isinstance(wording, dict):
        return ""
    # Encargo E (imp3 imp-wa-enviar-normal: «¿Quieres confirmar que envíes el mensaje…?»): an act names what it acts on
    # by its own fields or its arguments (the Enter towards a message box: «target»). An operation whose wording has no
    # default («""») is said only for the values it names.
    arguments = act.get("arguments") if isinstance(act.get("arguments"), dict) else {}
    said = next(
        (found for field in wording["by"]
         if (found := wording["values"].get(str(act.get(field) or arguments.get(field) or "")))),
        wording["values"].get(""),
    )
    return _sentence(said[language]) if said else ""


def floor_final(situation: dict, english: bool, now: datetime | None = None) -> str:
    """The sentence for one operation result or one mission, or "" when the facts carry no action to tell."""

    if not isinstance(situation, dict):
        return ""
    if pending := pending_final(situation, english):
        return pending
    templates = floor_data()["templates"]["en" if english else "es"]
    cause = str(situation.get("cause") or "").strip().lower()
    if cause in _MISSION_CAUSES:
        return _sentence(_mission(situation, cause, english, templates, now))
    if situation.get("kind") != "operation" and not _verified_status_of_an_operation(situation):
        # Progress, questions, conversation, a turn not understood: no action named to tell. A sentence with no
        # operation in it would be a fixed reply (owner's review of M75: the ⚠ stays there).
        return ""
    return _sentence(_step(situation, english, templates, now))


def tells_first(situation: object) -> bool:
    """Estabilización F (owner, 2026-10-11: «Lo que el suelo determinista de frases sabe decir no lo redacta el modelo.
    Ningún final afirma algo no verificado»): whether a turn's result is one the mind says from this floor before any
    draft. An operation, or a plan's step, that failed, was left uncertain or was cancelled; a verified one that found
    its state already there or that is always said whole (``told``: a memory result), or whose receipt carries the
    content it acted on (``content``), when every step it tells has its clause. A confirmation still owed, a turn that names no operation and any other verified
    result stay the writer's."""

    if not isinstance(situation, dict):
        return False
    cause = str(situation.get("cause") or "").strip().lower()
    if cause == "remaining_steps_cancelled" or pending_final(situation, False):
        return True
    reason = _decoded(situation.get("reason")) if cause in _MISSION_CAUSES else None
    if isinstance(reason, dict) and _entry({**reason, "kind": "operation"}):
        # A lookup whose answer only its own final says (noSuccessFloor: a web search, the clock) may still be
        # answered otherwise when it fails (M53: a recipe from memory, said as such): the writer keeps it.
        return not _entry({**reason, "kind": "operation"}).get("noSuccessFloor")
    steps = _decoded_steps(situation.get("steps")) if cause == "mission_completed" else (
        [situation] if situation.get("kind") == "operation" or _verified_status_of_an_operation(situation) else []
    )
    if not steps or not all(_entry(step) for step in steps):
        return False
    if len(steps) == 1 and not _verified(steps[0]):
        # A read or an act whose effect may have happened is the floor's; a result only left unverified (no
        # effectUncertain, polarity success) keeps the writer and its own checks.
        return not _entry(steps[0]).get("noSuccessFloor") and (
            steps[0].get("polarity") == "failure" or steps[0].get("effectUncertain") is True
        )
    told = [step for step in steps if len(steps) == 1 or not _entry(step).get("quiet")]
    return all(_verified(step) and not _entry(step).get("noSuccessFloor") for step in told) and any(
        _told(_entry(step), _observed(step)) or _proven_content(_entry(step), _observed(step))
        # Encargo I2 (identidad redpc: «Activá el modo accesible» switched from normal was drafted «El modo accesible
        # ya está activado.»): a switch whose variant says it whole (data «whole»: the on/off settings) is the floor's
        # either way, switched now or found already there (``told``).
        or (_variant(_entry(step), _observed(step)) or {}).get("whole") is True
        for step in told
    )


def _verified(step: dict) -> bool:
    return step.get("verified") is True and step.get("succeeded") is True


def _told(entry: dict, observed: dict) -> dict | None:
    """The wording a verified receipt is said with whole (data ``told``): one that found the state already there (its
    ``key`` flag is ``is``), or one always said so (no ``key``: a memory result, Estabilización M2); else None."""

    told = entry.get("told")
    if isinstance(told, dict) and ("key" not in told or observed.get(told["key"]) is told.get("is", False)):
        return told
    return None


def _proven_content(entry: dict, observed: dict) -> bool:
    """Revisión F (H4): a receipt that carries its content, or proves one the floor cannot quote (``contentProof``:
    a hash that did not match the text asked, a text too long): either way the floor says it, quoting only the first,
    so no draft retells a text."""

    return bool(_carried_content(entry, observed)) or bool(
        entry.get("content") and any(observed.get(key) for key in floor_data()["contentProof"])
    )


def _filled(text: str, observed: dict) -> str:
    """``text`` with its observed fields ({value}) filled, «{object}» kept; "" when one is not observed."""

    for name in {name for name in re.findall(r"\{(\w+)\}", text) if name != "object"}:
        value = observed.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float, str)) or value == "":
            return ""
        text = text.replace("{" + name + "}", f"{value:g}" if isinstance(value, float) else str(value))
    return text


def _carried_content(entry: dict, observed: dict) -> str:
    if not entry.get("content"):
        return ""
    return next((text for key in floor_data()["content"] if (text := _usable(observed.get(key), _LONGEST_CONTENT))), "")


def _mission(situation: dict, cause: str, english: bool, templates: dict, now: datetime | None) -> str:
    steps = _decoded_steps(situation.get("steps"))
    # Ronda 22 (r18 t4-c19 «ponme el navegador y el word uno al lado del otro»): a quiet read (window.resolve) is only
    # what an effect needed. In a mission that failed it is never told as done, even when it is the only step: its
    # list («hay 3: <títulos>») named windows the request never named. The effect left undone, or the cause, is said.
    quiet_out = len(steps) > 1 or cause != "mission_completed"
    told = [
        clause for step in steps
        if not (quiet_out and _entry(step).get("quiet"))
        and (clause := _step(step, english, templates, now))
    ]
    if cause == "mission_completed":
        return _joined(told, templates)
    reason = _decoded(situation.get("reason"))
    if isinstance(reason, dict) and reason.get("operation") and reason.get("kind") == "failure":
        # Ronda 22 (r18 t4-c19): the plan's own failure (a detail missing) names the step it stopped at; that
        # step is the effect not done («no pude colocar la ventana»).
        reason = {**reason, "kind": "operation"}
    failed = _step(reason, english, templates, now) if isinstance(reason, dict) and reason.get("operation") else ""
    if not told:
        # Nothing done before: the failed step is the whole report, or there is no action to name.
        return failed
    failed = failed or templates["rest"]
    # An uncertain step already carries its own «but» («intenté…, pero no pude confirmar…»).
    uncertain = isinstance(reason, dict) and _uncertain(reason)
    return _joined(told, templates) + templates["and" if uncertain else "but"] + failed


def _step(step: dict, english: bool, templates: dict, now: datetime | None) -> str:
    entry = _entry(step)
    if not entry:
        return ""
    language = "en" if english else "es"
    observed = _observed(step)
    if _verified(step):
        if entry.get("noSuccessFloor"):
            return ""
        told = _told(entry, observed)
        if told:
            # v3 r6 lectores: the wording picks by the observed field the data names («state» of a radio already
            # on or off), or by «kind». Ronda 22 (r18 t4-c07, t1-c13 «Creé la carpeta» over a folder that existed):
            # a receipt whose «reachedState» is true found the state already there («is»: true), and its wording
            # names the object with {object}.
            by = observed.get(told.get("by", "kind"))
            key = ("true" if by else "false") if isinstance(by, bool) else str(by or "")
            said = told["values"].get(key) or told["values"][""]
            wording = _filled(said[language], observed) or told["values"][""][language]
            return wording.replace("{object}", _object(entry, observed, language, templates))
        variant = _variant(entry, observed)
        clause = (variant or entry)[language][1] + _object(entry, observed, language, templates)
        if entry.get("when"):
            clause += _when(step, observed, templates, now)
        return templates["done"].format(clause=clause + _detail(entry, variant, observed, language, templates))
    if str(step.get("polarity") or "") == "pending":
        # A confirmation still owed is asked, not told.
        return ""
    # Only a verified result picks its variant by what it observed (muted, on, the kind set): a state read beside a
    # failure is the one that held, not the one asked.
    clause = _attempted_clause(entry, step, observed, language, templates)
    # M116: a read that only looked for what an effect needed (the window to place) is told by the effect it left
    # undone — «no pude colocar la ventana «Obsidian» a la izquierda» — when the facts carry it.
    if entry.get("quiet"):
        undone = [
            said for item in (step.get("notDone") if isinstance(step.get("notDone"), list) else [])
            if (said := _attempted_clause(_entry({"operation": (item or {}).get("operation")}), item, {}, language,
                                          templates) if isinstance(item, dict) else "")
        ]
        clause = _joined(undone, templates) if undone else clause
        if undone:
            # Encargo IMP2 (imp1 imp-wa-enviar: «Intenté enviar el mensaje a «Música», pero no pude confirmar si se hizo.»
            # over a contact search that failed before any send): the effects left undone were not done; only the read
            # that stopped them may have touched something.
            return templates["failed"].format(clause=clause)
    return templates["uncertain" if _uncertain(step) else "failed"].format(clause=clause)


def _attempted_clause(entry: dict, step: dict, observed: dict, language: str, templates: dict) -> str:
    """The plain clause of a step not done, with what it was about and, since M116, what it attempted: the client
    and the side said in words, the message's text quoted (data ``attempted`` and ``content``)."""

    if not entry:
        return ""
    attempted = step.get("attempted")
    # Revisión F (H5, r31 B2; estab t2-c03 t4 «Intenté cambiar el ajuste…» over {setting: brightness, value: 30}): the
    # variant the step asked for words it, with that variant's facts (the level asked).
    variant = _variant(entry, attempted) if isinstance(attempted, dict) else None
    clause = (variant or entry)[language][0] + _object(entry, observed, language, templates, step.get("target"))
    if not isinstance(attempted, dict):
        return clause
    data = floor_data()
    for spec in data["attempted"]:
        value = attempted.get(spec["key"])
        said = spec["values"].get(value) if isinstance(value, str) else None
        if said:
            clause += " " + said[language]
    asked = [said for fact in (variant or {}).get("facts") or [] if (said := _fact(fact, attempted, language))]
    if asked:
        return clause + templates["detail"] + templates["list"].join(asked)
    for key in data["content"]:
        text = _usable(attempted.get(key), _LONGEST_CONTENT)
        if text:
            return clause + templates["detail"] + templates["quote"].format(value=text)
    return clause


def _uncertain(step: dict) -> bool:
    """The effect may have happened and was not confirmed: neither done nor failed."""

    return step.get("effectUncertain") is True or (step.get("succeeded") is True and step.get("verified") is not True)


def _verified_status_of_an_operation(step: dict) -> bool:
    """Estabilización M (live identity check §3e): the private memory says its verified results as status facts that
    name their operation (the App's MemoryOperationResponseProjection); they are an operation's result all the same.
    Twin: OperationFloor.VerifiedStatusOfAnOperation."""

    return (
        step.get("kind") == "status" and bool(step.get("operation"))
        and step.get("verified") is True and step.get("succeeded") is True
    )


def _entry(step: object) -> dict:
    if not isinstance(step, dict) or (
        step.get("kind", "operation") != "operation" and not _verified_status_of_an_operation(step)
    ):
        return {}
    return floor_data()["operations"].get(str(step.get("operation") or ""), {})


def _variant(entry: dict, observed: dict) -> dict | None:
    """The variant of the operation the observation names (muted or not, on or off, the kind set), if any."""

    variants = entry.get("variants")
    if not isinstance(variants, dict):
        return None
    value = observed.get(variants["key"])
    key = ("true" if value else "false") if isinstance(value, bool) else str(value if value is not None else "")
    chosen = variants["values"].get(key)
    # Encargo I2: a variant may pick again by another field (a switch of a setting by the value set: «activé», never
    # «cambié»), keeping what it says itself (its facts, «whole») under the inner one.
    inner = _variant(chosen, observed) if isinstance(chosen, dict) else None
    return {**chosen, **inner} if chosen and inner else chosen


def _usable(value: object, longest: int = _LONGEST_NAME) -> str:
    text = " ".join(value.split()) if isinstance(value, str) else ""
    if not text or len(text) > longest or "«" in text or "»" in text:
        return ""
    return text


def _named(value: object, templates: dict) -> str:
    text = _usable(value)
    return " " + templates["quote"].format(value=text) if text else ""


def _object(entry: dict, observed: dict, language: str, templates: dict, target: object = None) -> str:
    """What was acted on: the step's target when it names one, else the first identifying field observed, and who
    made it when the read names them. Nothing for an operation whose target is no name to say (a search query, a
    folder key)."""

    if entry.get("anonymous"):
        return ""
    data = floor_data()
    keys = [None] if isinstance(target, str) else data["identity"]
    # Ronda 22 revisión 2 (r18 t2-c18, t3-c15 «Coloqué la ventana: a la izquierda»): a receipt that reports the
    # object acted on as a record of its own (data «objectIn»: the snapped «window») is named from that record.
    nested = observed.get(entry["objectIn"]) if entry.get("objectIn") else None
    sources = [observed, nested] if isinstance(nested, dict) else [observed]
    for key, source in ((key, source) for source in sources for key in keys):
        named = _named(target if key is None else source.get(key), templates)
        if named:
            word = (entry.get("objectWord") or {}).get(language)
            byline = _usable(observed.get(data["byline"]["key"]))
            by = data["byline"][language].format(value=byline) if byline else ""
            return (f" {word}{named}" if word else named) + by
    return ""


def _when(step: dict, observed: dict, templates: dict, now: datetime | None) -> str:
    """The verified time of a scheduled notification, at this PC's clock: the next run Windows read back for an alarm
    (both the due and the next run observed), the stored due of a reminder record."""

    due = _utc(observed.get("dueUtc"))
    if step.get("operation") == "notification.schedule":
        due = _utc(observed.get("nextRunUtc")) if due is not None else None
    if due is None:
        return ""
    local = due.astimezone()
    today = (now or datetime.now().astimezone()).astimezone().date()
    article = templates["articleOne" if local.hour == 1 else "article"]
    clock = f"{local:%H:%M}"
    if local.date() == today:
        said = templates["whenToday"]
    elif local.date() == today + timedelta(days=1):
        said = templates["whenTomorrow"]
    else:
        said = templates["whenDate"]
    said = said.format(article=article, clock=clock, day=local.day, month=templates["months"][local.month - 1])
    return " " + " ".join(said.split())


def _utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    stamp = value.strip().replace("Z", "+00:00")
    head, dot, rest = stamp.partition(".")
    if dot:
        digits = len(rest) - len(rest.lstrip("0123456789"))
        stamp = f"{head}.{rest[:min(digits, 6)]}{rest[digits:]}"
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _detail(entry: dict, variant: dict | None, observed: dict, language: str, templates: dict) -> str:
    specs = [*(entry.get("facts") or []), *((variant or {}).get("facts") or []), *floor_data()["facts"]]
    # Ronda 22 revisión 2 (r18 t3-c15): a fact that completes the clause («a la izquierda», data «attached») follows
    # it with a space, never after the detail separator («Coloqué la ventana: a la izquierda»).
    attached = "".join(" " + said for fact in specs if fact.get("attached") and (said := _fact(fact, observed, language)))
    facts = [said for fact in specs if not fact.get("attached") and (said := _fact(fact, observed, language))]
    content = _content(entry, observed, templates)
    if content:
        facts.append(content)
    if facts:
        return attached + templates["detail"] + templates["list"].join(facts)
    if attached:
        return attached
    # v3 r5a M3 (v3-43, v3-44): a mission's steps are no list it read («hay 3: «Opciones de energía»»).
    listed = "" if entry.get("noListing") else _listing(observed, templates)
    return templates["listDetail"] + listed if listed else ""


def _fact(fact: dict, observed: dict, language: str) -> str:
    value = observed.get(fact["key"])
    if "values" in fact:
        said = fact["values"].get(value) if isinstance(value, str) else None
        return said[language] if said else ""
    texts = fact[language]
    if isinstance(value, bool):
        return texts[0 if value else 1] if len(texts) == 2 else ""
    if isinstance(value, (int, float)):
        return texts[0].format(value=f"{value:g}" if isinstance(value, float) else value)
    text = _usable(value)
    return texts[0].format(value=text) if text and len(texts) == 1 else ""


def _content(entry: dict, observed: dict, templates: dict) -> str:
    text = _carried_content(entry, observed)
    return templates["content"].format(value=templates["quote"].format(value=text)) if text else ""


def _listing(observed: dict, templates: dict) -> str:
    """How many items a read listed and the first names, as the read wrote them; nothing when no list was read."""

    data = floor_data()
    count = next((observed[key] for key in data["listCounts"] if type(observed.get(key)) is int), None)
    for key, value in observed.items():
        if not isinstance(value, list):
            continue
        names: list[str] = []
        for item in value:
            name = _usable(item) if isinstance(item, str) else next(
                (said for field in data["listNames"] if isinstance(item, dict) and (said := _usable(item.get(field)))),
                "",
            )
            if name and name not in names:
                names.append(name)
        if not names:
            # An empty list beside others («failures»: []) is not the read's answer; only its count says nothing.
            continue
        total = count if count is not None else observed.get(f"{key}Count")
        total = total if type(total) is int else len(value)
        quoted = [templates["quote"].format(value=name) for name in names[:_LISTED_NAMES]]
        listed = _joined(quoted, templates)
        return templates["countOne" if total == 1 else "countNamed"].format(count=total, names=listed)
    if count == 0:
        return templates["none"]
    return templates["count"].format(count=count) if count is not None else ""


def _joined(parts: list[str], templates: dict) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return templates["list"].join(parts[:-1]) + templates["and"] + parts[-1]


def _sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    lead = len(text) - len(text.lstrip("«¿¡\"'"))
    text = text[:lead] + text[lead].upper() + text[lead + 1:]
    return text if text.endswith((".", "!", "?")) else text + "."


def _decoded(value: object) -> object:
    if isinstance(value, str) and value.lstrip().startswith("{"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def _decoded_steps(steps: object) -> list[dict]:
    return [step for raw in (steps if isinstance(steps, list) else []) if isinstance(step := _decoded(raw), dict)]


def _observed(step: dict) -> dict:
    """The observation of a result with its read-back state lifted (``state``/``final``: muted, level), as
    compose_situation._lift_observed_blob reads it."""

    observed = step.get("observed")
    if not isinstance(observed, dict):
        return {}
    lifted = dict(observed)
    state = observed.get("state") if isinstance(observed.get("state"), dict) else observed.get("final")
    if isinstance(state, dict):
        if "muted" in state:
            lifted["muted"] = state["muted"]
        level = state.get("volumePercent", state.get("level"))
        if level is not None and "level" not in observed:
            lifted["level"] = level
    return lifted
