"""BAXY's previous answer as context of the next turn: when a message refers to it, and the item counts a
reply says of it.
"""

from __future__ import annotations

from .semantic import dialogue as dialogue_slot
from .semantic import listing as semantic_listing
from .semantic.request import is_elliptical_followup


def _referenced_previous_answer(user_text: str, facts: dict) -> str:
    """BAXY's previous answer, when this message cannot be understood without it.

    tanda-02b t28 «¡ave, cesar!» after a search about «the date in 64 days»: the
    recomposed conversation got the previous answer as its only fact and
    answered the previous topic with an invented date. The previous answer is
    reference data for an elliptical follow-up («¿y eso qué significa?») or a
    message that points back («explícamelo mejor»); a message that stands on
    its own is answered on its own.
    """

    whole = str(facts.get("context") or "").strip()
    # Uso real v3 tanda 2 («dame 5 ideas…», five given; «no, te pedí 5 che, me tiraste menos»): cut at 320 characters
    # the five ideas were two, and the recovery said «Solo te proporcioné dos recetas». A list is referenced whole.
    listed = semantic_listing.items_listed(whole)
    previous = whole[:_LISTED_ANSWER_REFERENCE_CHARS] if listed is not None else whole[:320]
    if not previous:
        return ""
    prior = facts.get("priorRequests")
    antecedents = tuple(
        str(item) for item in reversed(prior if isinstance(prior, list) else []) if str(item or "").strip()
    )[:2]
    slot = dialogue_slot.DialogueSlot(None, None, antecedents or (previous,), previous)
    if is_elliptical_followup(user_text) or dialogue_slot.dependency(user_text, slot) is not None:
        return previous
    if listed is not None and _says_the_list_count(user_text, listed, prior):
        # «no te pedí 4, me tiraste como 7»: a count said right after a list is about that list.
        return previous
    return ""


# The bound of BAXY's previous answer as reference data when it is a list: five items with a line each.
_LISTED_ANSWER_REFERENCE_CHARS = 1_600


def _says_the_list_count(user_text: str, listed: int, prior: object) -> bool:
    """The message says the count of the list just given or the count its request asked («te pedí 5», «me tiraste
    como 7» after seven). Any number is not that: «¿cuánto es 3 por 4?» or «dame 3 ideas de postre» after five dinner
    ideas stand on their own, and the list with «si pidió menos, deja sólo esos» would turn them into a cut list."""

    said = set(semantic_listing.counts_said(user_text))
    if not said or semantic_listing.enumeration_asked(user_text) is not None:
        # A message that asks a counted list of its own («dame 5 ideas de postre») is a new request.
        return False
    counts = {listed}
    last_request = next((str(item) for item in reversed(prior) if isinstance(item, str)), "") if isinstance(
        prior, (list, tuple)
    ) else ""
    asked = semantic_listing.enumeration_asked(last_request) if last_request else None
    if asked is not None:
        counts.add(asked.count)
    return bool(said & counts)


def _settled_count_dispute(text: str, prior_requests: tuple[str, ...], last_assistant: str) -> int | None:
    """Ronda 19 (r17 t2-c02 T2 «no, te pedí 5 che, me tiraste menos» after five ideas): the count of BAXY's last list
    when the message disputes it (semantic.listing.count_disputed) and the list already had the count asked, counted
    from the list itself; None when the message disputes nothing («dame otras 5», «explícame la 5», «son 5 o 4?»),
    asks a list of its own, says only other counts, or the list did not have what was asked."""

    if not prior_requests or semantic_listing.enumeration_asked(text) is not None:
        return None
    asked = semantic_listing.enumeration_asked(prior_requests[-1])
    # Review 2 r19: «te pedí 5 vegetarianas», «me diste 5 con pollo y yo quería con carne» correct what the list was,
    # not its count (semantic.listing.count_disputed reads the class asked, «te pedí 5 ideas», as part of the count).
    if asked is None or not semantic_listing.count_disputed(text, asked.kind):
        return None
    # Review 3 r19 (2026-10-09): «me diste 5 y quería 10», «I wanted 10, you gave me 5», «no son 5, son 6» ask another
    # count. Besides what the person says BAXY gave («me tiraste como 7»), every number said is the count asked.
    said = set(semantic_listing.counts_said(text)) - set(semantic_listing.given_counts(text))
    if said - {asked.count}:
        return None
    listed = semantic_listing.items_listed(last_assistant, counted=True)
    return listed if listed == asked.count else None


def _settled_count_instruction(listed: int, response_language: str | None) -> str:
    """What the writer is told when the person disputes a count its last list already met (``_settled_count_dispute``)."""

    if response_language == "en":
        return (
            f"Your previous answer already listed {listed} items, the {listed} asked (counted by BAXY). Say so in one "
            "short sentence; do not write the list again."
        )
    return (
        f"Tu respuesta anterior ya tenía {listed} elementos, los {listed} que pidió (BAXY los contó). Dilo en una frase "
        "corta; no vuelvas a escribir la lista."
    )


def _previous_answer_items(facts: dict) -> int | None:
    """How many items BAXY's previous answer listed: the recovery's ``previousAnswerItems``, else read from ``context``
    (semantic.listing.items_listed); None when it listed none."""

    given = facts.get("previousAnswerItems") if isinstance(facts, dict) else None
    if type(given) is int and given >= 2:
        return given
    if not isinstance(facts, dict):
        return None
    # Ronda 19 (r17 t3-c17 «…el nacionalismo, las alianzas europeas, el nacionalismo eslavo y el imperialismo»): an
    # inline list is counted when the request before asked a number.
    prior = facts.get("priorRequests")
    request = next((str(item) for item in reversed(prior) if isinstance(item, str)), "") if isinstance(
        prior, list
    ) else ""
    counted = bool(request) and semantic_listing.enumeration_asked(request) is not None
    return semantic_listing.items_listed(str(facts.get("context") or ""), counted=counted)


def _previous_items_instruction(listed: int, response_language: str | None) -> str:
    """What the writer is told of the count of its previous answer (``_previous_answer_items``)."""

    if response_language == "en":
        return (
            f"Your previous answer listed {listed} items (previousAnswerItems). If the person says you gave another "
            f"number, do not agree: say you gave {listed}. If they asked for more than {listed}, add the missing ones; "
            f"if they asked for fewer, keep only that many."
        )
    return (
        f"Tu respuesta anterior tenía {listed} elementos (previousAnswerItems). Si la persona dice que diste otra "
        f"cantidad, no le des la razón: di que le diste {listed}. Si pidió más de {listed}, agrega los que faltan; si "
        "pidió menos, deja sólo esos."
    )


def _contradicts_previous_count(reply: str, facts: dict) -> bool:
    """The reply says BAXY gave a number of items its previous answer did not list («Solo te proporcioné dos recetas»
    after five), or more or fewer than asked when it gave the count asked. A reply that says no count, or the true
    one, is not judged."""

    listed = _previous_answer_items(facts)
    if listed is None:
        return False
    stated = semantic_listing.stated_given_count(reply)
    if stated is not None:
        return stated != listed
    # Audit 2026-10-08 t4-c02-2 «Lo siento, te di más de lo que pediste» after the three titles asked: «more» or
    # «fewer» than the count the request before asked is judged against what was listed.
    relation = semantic_listing.stated_given_relation(reply)
    prior = facts.get("priorRequests") if isinstance(facts, dict) else None
    request = next((str(item) for item in reversed(prior) if isinstance(item, str)), "") if isinstance(prior, list) else ""
    asked = semantic_listing.enumeration_asked(request) if relation and request else None
    if asked is None:
        return False
    return (relation == "more" and listed <= asked.count) or (relation == "fewer" and listed >= asked.count)
