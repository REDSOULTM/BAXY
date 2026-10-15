"""Facts ``message.compose`` adds beside a verified result: a listing asked for, a page on show, a thing made in
BAXY's store, and the parts of the message the operation could not receive.
"""

from __future__ import annotations

import json
from typing import Any

from . import turn_audit as turn_audit_module
from . import operation_floor
from .semantic import decider as semantic_decider
from .semantic import dialogue as dialogue_slot
from .semantic import answer_evidence as semantic_answer_evidence
from .semantic import listing as semantic_listing
from .semantic import arguments as semantic_arguments
from .semantic import acts_on_result as semantic_acts_on_result
from .semantic import missions as semantic_missions
from .semantic import files as semantic_files
from .compose_situation import _merged_observed, _situation_from_facts
from .compose_instructions import _search_of_address
from .planner import validate_json_schema_instance


def _with_unreceived_parts(facts: dict, said: str, tool_by_name: dict[str, dict]) -> dict:
    """Revisión 2 de r22 (bloqueante 3): the parts of the person's own message that act on what the operation made and
    that its argument schema cannot receive («toma una captura y mándala a mi jefe»: the capture has no recipient)
    ride on the situation as ``unreceived``, so the final tells them as not done. Only a single operation: a mission's
    plan gives each part its own step. Revisión 3: only an operation the data declares as never doing the act itself
    (acts_on_result ``readFor``); a reply that sends, a print, a volume raised by «súbelo» or computer use, whose goal
    carries the whole request, are never told an act they did as not done."""

    situation = _situation_from_facts(facts)
    operation = situation.get("operation")
    tool = tool_by_name.get(operation) if isinstance(operation, str) else None
    if (
        tool is None
        or not semantic_acts_on_result.read_for(operation)
        or situation.get("steps")
        or str(situation.get("kind") or "") != "operation"
    ):
        return facts
    schema = tool["function"].get("parameters")
    properties = schema.get("properties") if isinstance(schema, dict) else None
    parts = semantic_acts_on_result.unreceived_parts(said, properties if isinstance(properties, dict) else {})
    if not parts:
        return facts
    return {**facts, "situation": {**situation, "unreceived": [{"act": part.act, "said": part.said} for part in parts]}}


def _count_read_beside_the_named_place(situation: dict, *requests: str) -> bool:
    """Ronda 20b-3 (revisión 1 de v3-50: «cero archivos zip en la carpeta Escritorio» published for «¿cuántos zip hay en
    baxy-prueba-v3?» and for «decime cuántos archivos tiene adentro» after the 7-Zip mission): a count the adapter read
    from the Desktop (``source: desktop``, no Explorer in front) is not the answer when the request named another place
    (``semantic.files.count_names_a_place_beyond_the_desktop``) or pointed at what a mission showed
    (``semantic.missions.anaphoric_question``). It is not published as a success."""

    if situation.get("operation") != "filesystem.explorer.count" or situation.get("succeeded") is not True:
        return False
    seen = situation.get("seen") if isinstance(situation.get("seen"), dict) else {}
    if "desktop" not in (_merged_observed(situation).get("source"), seen.get("source")):
        return False
    return any(
        semantic_files.count_names_a_place_beyond_the_desktop(said) or semantic_missions.anaphoric_question(said)
        for said in requests if said
    )


def _with_asked_listing(
    operation: str, arguments: dict[str, Any] | None, request: str, schema: dict,
) -> dict[str, Any] | None:
    """Uso real 2026-10-07 «un top 3 peliculas de suspenso del 2026» → one film: a search for a ranked listing asks the
    provider for that many results and says it is a listing (``listing``), so an article about one work is not taken
    as the answer. Only when the catalog's search takes ``listing``; the person's own count is kept within ``limit``."""

    if operation != "web.search" or not isinstance(arguments, dict):
        return arguments
    arguments = _with_answerWords(arguments, request, schema)
    properties = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(properties, dict) or "listing" not in properties:
        return arguments
    asked = semantic_listing.listing_asked(request)
    if asked is None:
        return arguments
    listed = {**arguments, "listing": True}
    if asked.count is not None:
        listed["limit"] = asked.count
    return listed if validate_json_schema_instance(listed, schema) else arguments


def _with_answerWords(arguments: dict[str, Any], request: str, schema: dict) -> dict[str, Any]:
    """Uso real v3 tanda 1 «quien gano el mundial del 2014» → «Brasil ganó…»: the encyclopedia's first sentences named
    Brasil as the host and none said who won. A question that asks a relation («quién ganó», «who directed») tells the
    provider the word beginnings with which a page states it (``answerWords``, semantic.answer_evidence); when no
    fragment carries them, the provider reads the first pertinent source for the sentence that does. Only when the
    catalog's search takes ``answerWords``."""

    properties = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(properties, dict) or "answerWords" not in properties:
        return arguments
    words = semantic_answer_evidence.answerWords(request)
    if not words:
        return arguments
    stated = {**arguments, "answerWords": " ".join(words)}
    # Revisión adversarial: «tras el campeonato de 1950», «the quadrennial world championship» begin as «who won» is
    # stated and say nothing of it; the provider is told so, as the mind's own reading is.
    other = semantic_answer_evidence.answer_words_not(request)
    if other and "answerWordsNot" in properties:
        stated["answerWordsNot"] = " ".join(other)
    return stated if validate_json_schema_instance(stated, schema) else arguments


def _with_listing_and_repetition_facts(
    facts: dict[str, Any],
    situation: dict[str, Any],
    dialogue_state: dialogue_slot.DialogueState,
    understood: str,
    said: str,
) -> dict[str, Any]:
    """Uso real 2026-10-07 (the «top 3» seed): what the writer must know beside the result. ``askedCount``: how many
    the person asked to be listed, so fewer found is said as fewer. ``sameResultAgain``: the person corrected or
    insisted and the same operation observed the same thing again; the words told last time travel so they are not
    told again. A progress notice of the turn still running reports no result: it carries none of them."""

    if dialogue_slot.in_progress(situation):
        return facts
    extra: dict[str, Any] = {}
    if situation.get("operation") == "web.search":
        asked = semantic_listing.listing_asked(said) or semantic_listing.listing_asked(understood)
        if asked is not None and asked.count is not None:
            extra["askedCount"] = asked.count
    shown = dialogue_state.reading_on_show
    reason = situation.get("reason") if isinstance(situation.get("reason"), dict) else {}
    told = situation
    if shown and "browser.page.read" in {situation.get("operation"), reason.get("operation")}:
        # Semilla fix2: the page read is the search already open (``_read_the_page_on_show``); the writer tells what
        # was asked of it, or, when the read failed, that it is open in the person's browser.
        site_query = _search_on_show(shown)
        read = situation if situation.get("operation") == "browser.page.read" else reason
        read_url = _read_page_url(read)
        if site_query is not None and _read_something(read) and not _shows_the_search(
            read_url, shown, site_query, _read_page_observed(read).get("title")
        ):
            # Review r10a finding 2: the read takes whatever page is in front of the person's browser; another page
            # (they moved to their inbox) is not the search. Nothing of it is told: the search is said out of view.
            # Review of the fix: a read whose address could not be read (the receipt's «url» empty) is the search
            # only when its title carries the words searched, as every engine titles its results page.
            told = _search_out_of_view(situation, site_query)
            site_query = None
        if site_query is not None:
            extra["openSearch"] = {"site": site_query[0], "query": site_query[1]}
            asked = (
                semantic_listing.listing_asked(said)
                or semantic_listing.listing_asked(site_query[1])
                or semantic_listing.listing_asked(understood)
            )
            if asked is not None and asked.count is not None:
                extra["askedCount"] = asked.count
    previous = dialogue_state.same_result_again(situation, said)
    if previous is not None:
        extra["sameResultAgain"] = {"previousReply": previous[:400]}
    corrected = dialogue_state.final_before_correction(situation, said)
    if corrected is not None:
        # Uso real v3 t2 (c03-2, c04-4): after a correction, the last final's words are never told again.
        # Ronda 24 (r23 t2-c03 #3): a final that only asked or talked ran nothing (``previousTurnActed`` false).
        extra["correctedFinal"] = {
            "previousReply": corrected[:400],
            **({} if dialogue_state.last_final_acted() else {"previousTurnActed": False}),
        }
    if not extra and told is situation:
        return facts
    return {**facts, "situation": {**told, **extra}}


def _with_made_in_store(
    facts: dict[str, Any], situation: dict[str, Any], said: str, application_names: Any,
) -> dict[str, Any]:
    """Ronda 21, revisión 2 (g; pasada r18 v3-35 «abre notas rapidas» → «ponle: pagar la luz» → «He creado la nota»,
    a false success for the person looking at the application they opened): a verified thing made in BAXY's own store
    beside an application the request or the conversation is in (``semantic.missions.made_beside_an_application``)
    carries where it is (``madeIn``: the store and the application it is not in, operation_floor.v1.json
    «madeInStore»). Contracaso: no application said nor in the conversation, the store itself said, or an operation
    that makes nothing applications make, carry nothing. Revisión 3 (falso éxito): an operation whose result is a file
    on the person's disk (filesystem.write.text, document.presentation.create, office.document.create) is no thing kept
    in the store; only those the data lists («madeInStore» «operations», surface own_store) carry it."""

    made_in_store = operation_floor.floor_data()["madeInStore"]
    operation = str(situation.get("operation") or "")
    if (
        situation.get("kind") != "operation"
        or situation.get("verified") is not True
        or situation.get("succeeded") is not True
        or operation not in made_in_store.get("operations", ())
        or semantic_decider.operation_surface(operation) != "own_store"
    ):
        return facts
    store = str(made_in_store["store"])
    prior = [str(item) for item in (facts.get("priorRequests") or []) if isinstance(item, str) and item.strip()]
    application = semantic_missions.made_beside_an_application(said, prior, operation, application_names, store)
    if application is None:
        return facts
    return {**facts, "situation": {**situation, "madeIn": {"store": store, "notIn": application}}}


def _told_where_it_was_made(text: str, situation: dict[str, Any], english: bool) -> str:
    """The final of a thing made in BAXY's store beside an application (``_with_made_in_store``) says the store: the
    data's sentence closes it when the writer's words never named the store. An empty final stays empty (the App's
    floor tells it)."""

    made = situation.get("madeIn") if isinstance(situation, dict) else None
    if not text.strip() or not isinstance(made, dict) or not made.get("notIn"):
        return text
    if semantic_missions.fold(str(made.get("store") or "")) in semantic_missions.fold(text):
        return text
    sentence = operation_floor.floor_data()["madeInStore"]["en" if english else "es"].format(
        application=made["notIn"],
    )
    return f"{text.rstrip()} {sentence}"


def _read_page_observed(read: object) -> dict:
    """What a page read observed (its «observed», parsed when the App sent it as text), or {}."""

    observed = read.get("observed") if isinstance(read, dict) else None
    if isinstance(observed, str) and observed.lstrip().startswith("{"):
        try:
            observed = json.loads(observed)
        except json.JSONDecodeError:
            observed = None
    return observed if isinstance(observed, dict) else {}


def _read_page_url(read: object) -> str:
    """The address a page read observed («observed.url»), or ""."""

    url = _read_page_observed(read).get("url")
    return url.strip() if isinstance(url, str) else ""


def _read_something(read: object) -> bool:
    """The page read returned a page: verified, with an address, a title or a text of it."""

    observed = _read_page_observed(read)
    return isinstance(read, dict) and read.get("verified") is True and read.get("succeeded") is True and any(
        isinstance(observed.get(key), str) and observed[key].strip() for key in ("url", "title", "text")
    )


def _shows_the_search(read_url: str, shown: str, site_query: tuple[str, str], title: object = None) -> bool:
    """The page read is the search on show: the same address, or the same engine's results for the same words (the
    parameters a results page adds, «&sca_esv=…», are not compared). Without an address read, its title carries the
    words searched."""

    if not read_url:
        words = " ".join(site_query[1].casefold().split())
        return bool(words) and isinstance(title, str) and words in " ".join(title.casefold().split())
    if dialogue_slot.same_page(read_url, shown):
        return True
    read = _search_on_show(read_url)
    return read is not None and read[0] == site_query[0] and (
        " ".join(read[1].casefold().split()) == " ".join(site_query[1].casefold().split())
    )


def _search_out_of_view(situation: dict[str, Any], site_query: tuple[str, str]) -> dict[str, Any]:
    """Review r10a finding 2: the read found another page in front, not the search it was meant to read again. The
    situation keeps no word of that page (its address, title or text are the person's own); the search is said out
    of view (``searchOutOfView``, the floor's «webSearch.outOfView»), never read."""

    kept = {"kind", "operation", "polarity", "verified", "succeeded", "cause", "error", "id", "invocationId", "missionId"}
    told = {key: value for key, value in situation.items() if key in kept}
    return {**told, "observed": {}, "searchOutOfView": {"site": site_query[0], "query": site_query[1]}}


def _search_on_show(address: str) -> tuple[str, str] | None:
    """The site and words of a search-results address («Google», «un top 3 …»); None for any other page."""

    return _search_of_address(address)


def _read_the_page_on_show(
    result: dict[str, Any],
    message: dict[str, Any],
    dialogue_state: dialogue_slot.DialogueState | None,
    tool_by_name: dict[str, Any],
) -> dict[str, Any]:
    """Semilla fix2 («si pero quiero buscar un top 3», «ok pero lo puedes buscar en google…» right after that Google
    search was opened and verified): a correction, an insistence or a listing asked, decided as the navigation to the
    page already verified on show, does not open it again. The page the person sees is read instead
    (``browser.page.read``): what was asked is told from it, and a read that fails still says the search is open in
    their browser (``openSearch`` beside the result, ``_with_listing_and_repetition_facts``). «otra vez» asks to open
    it again and is no correction."""

    if dialogue_state is not None:
        dialogue_state.reading_on_show = None
    if (
        dialogue_state is None
        or result.get("kind") != "action"
        or result.get("operation") not in {"browser.navigate", "browser.navigate.named"}
        or "browser.page.read" not in tool_by_name
    ):
        return result
    text = str(message.get("text", ""))
    if not (dialogue_slot.corrects_or_insists(text) or semantic_listing.listing_asked(text) is not None):
        return result
    request = str(result.get("objective") or text)
    arguments = semantic_arguments._explicit_browser_navigation_arguments(str(result["operation"]), request)
    shown = dialogue_state.on_show((arguments or {}).get("url"))
    if shown is None:
        return result
    dialogue_state.reading_on_show = shown
    objective = (
        f"lee la página que está abierta en mi navegador ({shown})"
        if dialogue_slot.spanish(text) or dialogue_slot.spanish(request)
        else f"read the page open in my browser ({shown})"
    )
    turn_audit_module._append_turn_audit(
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": message.get("id"),
            "phase": "final",
            "decision_path": "page_on_show_read",
            "raw_decision": {"operations": [result["operation"]], "request": request},
            "final": {"kind": "action", "effect_operations": ["browser.page.read"]},
        }
    )
    return {
        **result,
        "operation": "browser.page.read",
        "intentOperations": ["browser.page.read"],
        "effectOperations": ["browser.page.read"],
        "objective": objective,
    }
