"""The reading gate: one read of a message (Fase 3.5). The utterance forms the pattern alone does not read (an order after talk, a place said first, a desire to listen, the clauses of a compound, talk that asks nothing) and read(), which returns them together as a Reading that the turn consumes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable

from . import dialogue
from .catalog import ApplicationCatalogIndex, GameCatalogIndex
from .grammar import (
    _ASSISTANT_NAME,
    _CLAUSE_EDGE_PUNCTUATION,
    _head_forms,
    _original_clause,
    _without_address,
    imperative_rewrites,
)
from .intent import EffectIntent
from .media import player_opened_to_play, spoken_media_order
from .messaging import after_opening_the_mailbox
from .normalize import fold as _fold
from .patterns import (
    ClarificationIntent,
    CompoundEffectContract,
    resolve_explicit_clarification_intent,
    reported_own_schedule,
    resolve_explicit_effects,
)


# Coordination between clauses: a comma, «y/e», «después/luego», «and/then».
_CLAUSE_COORDINATION = re.compile(
    r"\s*[,;]\s*(?:(?:y|e|and)\s+)?(?:(?:despues|después|luego|then)\s+)?"
    r"|\s+(?:y\s+despues|y\s+después|y\s+luego|and\s+then|y|e|and|then|luego|despues|después)\s+",
    re.IGNORECASE,
)


_LEADING_VOCATIVE = re.compile(
    rf"^[\s¡¿]*(?:(?:hey|oye|oiga|che|hola|ok|okay)[\s,]+)?{_ASSISTANT_NAME}\b[\s,.:;!]*",
    re.IGNORECASE,
)


def _coordinated_clauses(objective: str) -> list[str]:
    """The coordinated clauses of a request, as written; a leading vocative is an address, not a clause."""

    return [
        part.strip(_CLAUSE_EDGE_PUNCTUATION)
        for part in _CLAUSE_COORDINATION.split(_LEADING_VOCATIVE.sub("", objective, count=1))
        if part.strip(_CLAUSE_EDGE_PUNCTUATION)
    ]


def _clause_starts_with_order(clause: str) -> bool:
    """A coordinated clause is an order: an order verb, or an imperative by its form with an object."""

    folded = _LEADING_VOCATIVE.sub("", _fold(clause), count=1)
    if not folded:
        return False
    if _OVERHEARD_ACTION_WORDS.match(folded) is not None:
        return True
    words = folded.split()
    return len(words) >= 2 and any(
        form != words[0] and form.endswith(("ar", "er", "ir")) for form in _head_forms(words[0])
    )


# A lead that makes the order after it not a plain order: a condition («si
# llueve, …»; a bare «sí» folds to «si» and is assent) or reported speech.
_LEAD_NOT_TALK = re.compile(
    r"\b(?:si|cuando|apenas|en\s+cuanto|mientras|if|when|once|while)\s+\w|"
    r"\b(?:dice|dijo|decia|dicen|me\s+dijo|says|said|told)\b"
)


# What follows an order and is not talk about it: a correction, a coordination, or more of the order itself
# (a place, an amount, «algo tranquilo», «al 50»).
_NOT_TALK_AFTER_ORDER = re.compile(
    r"^[¿¡\s]*(?:no\s*[,.;!]|(?:no\s+(?:mejor|espera|perdon|era|es)|mejor|digo|perdon|quiero\s+decir|o\s+sea|"
    r"espera|wait|sorry|i\s+mean|actually|rather|instead|pero|but|y|e|and|o|u|or|luego|despues|then|"
    r"el|la|los|las|lo|un|una|unos|unas|algo|al|a|en|de|del|con|para|por|sin|hasta|desde|hacia|"
    r"the|an|some|to|in|on|at|with|for|from|\d)\b)"
)


def _order_with_talk(
    objective: str,
    resolve: Callable[[str], EffectIntent | None],
) -> EffectIntent | None:
    """The order said with talk around it.

    After talk («Me encanta cómo lo definís, oye, hablando de amor, pon una canción de amor en YouTube», owner
    test 2026-09-21 turn 15): the pattern reads whole requests and talk before the order hid it. The tail from
    the first clause the pattern resolves on its own is the request, when no earlier clause is an order, a
    condition, reported speech or a negation.

    Before talk («para la música, me va a explotar la cabeza», tanda 3 2026-09-24, answered with chat): the
    first clause is an order the pattern resolves on its own and what follows is only said about it — not an
    order, a condition, reported speech, a correction or more of the order.
    """

    parts = re.split(r"(?<=[,.;!?])\s+", objective.strip())
    if len(parts) < 2 or len(parts) > 8:
        return None
    for index in range(1, len(parts)):
        lead = " ".join(parts[:index])
        folded_lead = _fold(lead)
        if _LEAD_NOT_TALK.search(folded_lead) or _OVERHEARD_ACTION_WORDS.search(folded_lead):
            break
        if resolve(parts[index - 1].strip(_CLAUSE_EDGE_PUNCTUATION)) is not None:
            # M143 (DEV-H v4o H-s089 «minimise everything for a second, i need to find a file on the desktop» → a file
            # search, where the isolated decider minimized every window): a clause before that is an order of its own
            # is no talk; what follows it is said about it (here why), never the request in its place.
            break
        tail = " ".join(parts[index:]).strip()
        found = resolve(tail)
        if found is not None:
            return found
    said_after = _fold(" ".join(parts[1:]))
    if (
        not _clause_starts_with_order(parts[0])
        or _NOT_TALK_AFTER_ORDER.match(said_after)
        or _LEAD_NOT_TALK.search(said_after)
        or _OVERHEARD_ACTION_WORDS.search(said_after)
        or _TALK_EXTRA_ORDER.search(said_after)
    ):
        return None
    return resolve(parts[0].strip(_CLAUSE_EDGE_PUNCTUATION))


_FRONTED_PLACE = re.compile(
    r"^[¿¡\s]*(?P<prep>en|on|in|por|desde)\s+(?P<place>[^\s,]+(?:\s+[^\s,]+){0,2}?)\s*,?\s+(?P<order>\S.*)$",
    re.IGNORECASE,
)


def _addressed_request(
    objective: str,
    resolve: Callable[[str], EffectIntent | None],
) -> EffectIntent | None:
    """«oye abre chrome», «olly pon rosalía»: the request after the address, when it resolves on its own."""

    rest = _without_address(objective)
    return resolve(rest) if rest is not None else None


def _mailbox_opened_to_read(
    objective: str,
    resolve: Callable[[str], EffectIntent | None],
) -> EffectIntent | None:
    """«abre mi cuenta de correo y revisa nuevos correos» (dev corpus 2026-09-23): opening the mailbox is the way
    to what arrived, which the mail read answers; any other order after the opening keeps its compound."""

    rest = after_opening_the_mailbox(objective)
    found = resolve(rest) if rest is not None else None
    return found if found is not None and found.operations == ("email.latest.read",) else None


def _desired_media_request(
    objective: str,
    resolve: Callable[[str], EffectIntent | None],
) -> EffectIntent | None:
    """«Quiero una canción de amor», «escuchemos a Soda Stereo», «tocar música reggae», «iniciar
    podcasts de nfl», «nueva música pop» read as «pon …» (owner test turn 16; uso real 2026-09-23).

    A request to listen said another way (``media.spoken_media_order``) is the same request as the
    order to play; the words are the person's and stay the query. Only when the order resolves on its own.
    """

    if re.search(r"\b(?:chistes?|jokes?|bromas?|adivinanzas?|riddles?)\b", _fold(objective)):
        # MASSIVE general_joke «i want to hear a joke», «me gustaría escuchar algunos buenos chistes»:
        # a joke is told by BAXY, not played.
        return None
    if re.search(r"\b(?:informacion|information|info|datos|data|detalles|details)\b", _fold(objective)):
        # M99 (reserva A6 «important house information» → Spotify played «house»): information is read, not played.
        return None
    order = spoken_media_order(_without_address(objective) or objective)
    return resolve(order) if order is not None else None


# M100 (reserva A10 «me gustaría ser notificado de las misas de los domingos a las once de la mañana» → «no encuentro un
# pedido»): being notified or reminded, wished for, is the order «avísame / remind me» with the same words. Folded.
_WISHED_NOTICE = re.compile(
    r"^(?:(?:yo\s+)?(?:me\s+gustaria|me\s+encantaria|quiero|quisiera|necesito|preferiria)\s+"
    r"(?:ser\s+(?:notificad[oa]s?|avisad[oa]s?|alertad[oa]s?|recordad[oa]s?)|"
    r"que\s+me\s+(?:avises|avisaras|avisen|notifiques|notificaras|notifiquen|recuerdes|recordaras|recuerden|alertes))|"
    r"(?:i\s+(?:would\s+like|want|need)|i'?d\s+like)\s+(?:to\s+be\s+(?:notified|reminded|alerted)|"
    r"you\s+to\s+(?:notify|remind|alert)\s+me))\s+(?P<rest>\S.*)$"
)


def _wished_notice_request(
    objective: str,
    resolve: Callable[[str], EffectIntent | None],
) -> EffectIntent | None:
    """«me gustaría ser avisado de la reunión mañana a las diez», «I'd like to be reminded of the rent on Friday at
    nine» read as «avísame de la reunión…», «remind me of the rent…» (see above); only when that order resolves."""

    found = _WISHED_NOTICE.match(_fold(_without_address(objective) or objective).strip(" ¿?¡!.,"))
    if found is None:
        return None
    head = "remind me" if found.group(0).startswith("i") else "avisame"
    return resolve(f"{head} {found.group('rest')}")


def _player_opened_to_play_request(
    objective: str,
    resolve: Callable[[str], EffectIntent | None],
) -> EffectIntent | None:
    """M100 (reserva A14): «abre spotify y pon X», «open the music app and play a song» read as the order to play X
    there (``media.player_opened_to_play``); only when that order resolves to playing."""

    order = player_opened_to_play(_without_address(objective) or objective)
    found = resolve(order) if order is not None else None
    return found if found is not None and all(op.startswith("media.play") for op in found.operations) else None


# The usted and subjunctive forms said alone as interjections (surprise, calling attention, urging): folded.
_LONE_INTERJECTION = re.compile(
    r"(?:vaya|vayan|venga|vengan|oiga|oigan|mire|miren|diga|digame|ande|fijese|figurese|vamos)(?:\s+(?:vaya|pues|ya))?"
)


def _imperative_rewrite_request(
    objective: str,
    resolve: Callable[[str], EffectIntent | None],
) -> EffectIntent | None:
    """«envíeme un recordatorio…», «establecer recordatorio…», «recuérda me la reunión…» read as the tú/voseo
    order they say (``grammar.imperative_rewrites``), after an address; only a rewrite that resolves on its own."""

    said = _without_address(objective) or objective
    if _LONE_INTERJECTION.fullmatch(_fold(said).strip(" ¿?¡!.,;:")) is not None:
        # M91 (reserva «vaya»): an interjection said alone is no order in another person («vaya» → «ve» read the
        # screen); «silencie» alone still is.
        return None
    for rewrite in imperative_rewrites(said):
        effects = resolve(rewrite)
        if effects is not None:
            return effects
    return None


def _fronted_place_request(
    objective: str,
    resolve: Callable[[str], EffectIntent | None],
) -> EffectIntent | None:
    """«en YouTube pon una canción» read as «pon una canción en YouTube» (layer C).

    The pattern reads the place after the order; said first, it hid the order.
    Only when what follows the place is an order and the reordered request
    resolves on its own; the words are the person's.
    """

    match = _FRONTED_PLACE.match(objective.strip())
    if match is None or not _clause_starts_with_order(match.group("order")):
        return None
    order = match.group("order").strip().rstrip(".!?")
    return resolve(f"{order} {match.group('prep')} {match.group('place')}")


# Words that make a statement about the PC a possible indirect request («estoy con el volumen
# muy alto»): such a statement is left to the ordinary reading.
_TALK_PC_DOMAIN = re.compile(
    r"\b(?:volumen|sonido|audio|brillo|pantalla|ventana|archivo|carpeta|microfono|micro|wifi|bluetooth|"
    r"musica|cancion|video|app|aplicacion|programa|juego|steam|spotify|youtube|chrome|edge|navegador|"
    r"volume|sound|brightness|screen|window|file|folder|music|song)\b"
)


_TALK_LOOKUP = re.compile(r"\b(?:investig\w*|busc\w*|averigu\w*|fijate|googlea\w*|search|look\s+up)\b")


# A request said as a desire or as a reproach is still a request: «yo quiero ver Netflix»,
# «te dije que abras Spotify», «me gustaría que pongas algo».
_TALK_DESIRED_REQUEST = re.compile(
    r"(?<!\bno\s)\b(?:quiero|quisiera|queria|necesito|me\s+gustaria|i\s+want|i\s+need|i'?d\s+like)\s+(?:to\s+)?"
    r"(?:\w+(?:ar|er|ir)\b(?!\s+que)|que\s+\w+(?:as|es|ais|eis)\b)|"
    r"\b(?:te\s+(?:dije|pedi|estoy\s+diciendo)|you\s+(?:were\s+)?told)\s+(?:que\s+)?\w+(?:as|es)\b"
)


# Verbs of media and navigation said as an order at a clause start («pasá a la siguiente»).
_TALK_EXTRA_ORDER = re.compile(
    r"(?:^|[,.;:!]\s*|\b(?:y|e|o)\s+)(?:pasa|pasame|salta|saltea|adelanta|atrasa|repeti|repite|vuelve|volve|"
    r"skip|next|mute|mutea|sube|subi|baja|baji)(?:me|te|lo|la|los|las|le|les)?\b"
)


def _leading_proved_clauses(
    objective: str,
    contract: CompoundEffectContract | None,
    resolve: Callable[[str], object | None],
) -> tuple[list[str], list[str]] | None:
    """(proved, pending) clauses of a compound, in the person's words, or None.

    The compound contract's clause reading wins; without one, the coordinated
    clauses are read one by one and the leading ones the pattern resolves on
    their own are the proved part («abre Word» in «abre Word y ayudame a…»).
    """

    if contract is not None and contract.clause_requirements:
        proved = [_original_clause(objective, c) for c, ops in contract.clause_requirements if ops]
        pending = [_original_clause(objective, c) for c, ops in contract.clause_requirements if not ops]
        if not all(_clause_starts_with_order(clause) for clause in (*proved, *pending)):
            # «buenas, phrase_hook_test_… y dime la hora»: a token that is not an
            # order is not a part BAXY declines; it is not offered around.
            return None
    else:
        clauses = _coordinated_clauses(objective)
        if len(clauses) < 2:
            return None
        if not all(_clause_starts_with_order(clause) for clause in clauses):
            # «baxy, cierra baxy» (dueño turn 50): a vocative is not a clause.
            # «abre Ratchet y Clank», «juga Dungeons and Dragons»: a title with a
            # conjunction is one name, not two clauses.
            return None
        count = 0
        for clause in clauses:
            if resolve(clause) is None:
                break
            count += 1
        proved, pending = clauses[:count], clauses[count:]
    return (proved, pending) if proved and pending else None


def _compound_partial_offer(
    objective: str,
    clauses: tuple[list[str], list[str]] | None,
    response_language: str | None,
) -> tuple[str, str] | None:
    """(question, objective) offering the proved clauses of a compound BAXY cannot finish.

    Fase 3.5: «abre Steam, ve a biblioteca y busca Batman» ended as «no puedo
    abrir Steam ni…», denying the clause BAXY can do. When the whole mission
    cannot keep authority but some clauses were proved on their own, the honest
    turn names both parts in the person's own words and asks before doing the
    proved part; the proved part is the objective an assent resumes. It does not
    claim the rest is impossible (it may be a separate request, «cuánto es 25
    por 4»), only that it is not done in this one. Nothing runs in this turn.
    """

    if clauses is None:
        return None
    proved, pending = clauses
    if response_language == "en":
        question = (
            "I can do " + " and ".join(f"“{clause}”" for clause in proved) + " now; "
            + " and ".join(f"“{clause}”" for clause in pending)
            + " I can't do in the same request. Shall I do the first part?"
        )
    else:
        question = (
            "Ahora puedo hacer " + " y ".join(f"«{clause}»" for clause in proved) + ". Lo de "
            + " y ".join(f"«{clause}»" for clause in pending)
            + " no lo hago en el mismo pedido. ¿Hago lo primero?"
        )
    return question, " y ".join(proved)


_OVERHEARD_ACTION_WORDS = re.compile(
    # An order verb counts where a clause starts: after the beginning, a
    # punctuation mark or a connective («…, toma un screenshot», «y ve que
    # hay»); «si hace bien el trabajo» or «la ve y si no» inside a stretch of
    # talk is not an order to BAXY.
    r"(?:^|[,.;:!¡¿]\s*|\b(?:y|o|e|u|baxy|entonces|luego|despues|ahora|primero|tambien)\s+)"
    r"(?:baxy|abre|abri|abris|abrir|abrime|pone|pon|poneme|pongas|poner|busca|buscame|buscar|"
    r"cierra|cerra|cerrar|reproduce|reproduci|manda|mandame|envia|enviame|escribe|escribi|crea|"
    r"guarda|guardame|recuerda|recorda|recordame|sube|subi|subile|baja|baji|bajale|silencia|"
    r"apaga|prende|enciende|lanza|inicia|muestra|mostrame|dime|decime|contame|cuentame|explica|"
    r"explicame|avisame|avisa|llama|llamame|programa|agenda|calcula|traduce|traducime|lee|leeme|"
    r"copia|pega|borra|elimina|instala|desinstala|descarga|configura|conecta|desconecta|"
    r"toma|tomame|saca|sacame|captura|capturame|identifica|mira|mirame|revisa|revisame|haz|hace|haceme|"
    r"dale|clic|click|clickea|presiona|pulsa|selecciona|elige|escoge|ejecuta|corre|ve|anda|entra|"
    r"screenshot|dime|responde|contesta|resume|resumime|completa|completalo|completala|termina|terminalo|"
    r"confirma|confirmalo|acepta|aceptalo|cancela|cancelalo|"
    r"open|play|search|close|send|write|set|turn|remind|show|tell|launch|start|stop|find|take|click|"
    r"puedes|podes|podrias|puede|quiero\s+que|necesito\s+que|me\s+(?:ayudas|ayudarias|dices|decis|cuentas|contas|explicas))\b"
    # «Mira, bueno, la neta…», «Dale, dale.»: a verb followed by a comma or a
    # period is a discourse marker in talk, not an order with an object.
    r"(?!\s*[,.;])"
)


def plain_talk(text: str, *, effects: EffectIntent | None, clarification: object | None) -> str | None:
    """The talk act of a message that asks nothing («statement», «feedback», «reaction»), or None.

    The form is read by ``dialogue.talk_act``; a message with an order, a request the pattern reads,
    a desire or reproach that repeats a request, a lookup verb, or (for a statement) a PC domain
    word is left to the ordinary reading.
    """

    if effects is not None or clarification is not None:
        return None
    act = dialogue.talk_act(text)
    if act is None:
        return None
    folded = _fold(text)
    # «baxy» counts as an address in the overheard-speech list; here it is not an order.
    orders = re.sub(r"\bbaxy\b", "", folded)
    if (
        _OVERHEARD_ACTION_WORDS.search(orders)
        or _TALK_EXTRA_ORDER.search(orders)
        or _TALK_DESIRED_REQUEST.search(folded)
        or _TALK_LOOKUP.search(folded)
        # MASSIVE «i had a problem with my burger can you tweet bk»: a request after the story is a request.
        or re.search(r"\b(?:can|could|would|will)\s+you\s+(?!believe\b|imagine\b)[a-z]+", folded)
    ):
        return None
    if act == "statement" and _TALK_PC_DOMAIN.search(folded):
        return None
    return act


@dataclass(frozen=True)
class Reading:
    """One read of a message, before any model: what the pattern proves and what kind of turn it is.

    ``effects``        the explicit effects the pattern reads, directly or through one of the utterance
                       forms it does not read alone (``source`` says which);
    ``clarification``  a recognized effect that lacks a value («subí el volumen» → how much);
    ``talk``           talk that asks nothing («statement», «feedback», «reaction»).
    """

    effects: EffectIntent | None
    source: str
    clarification: ClarificationIntent | None
    talk: str | None


def utterance_form(
    text: str,
    resolve: Callable[[str], EffectIntent | None],
) -> tuple[str, EffectIntent] | None:
    """The request inside an utterance form the pattern does not read alone (talk around the order, a fronted
    place, an address, a desire to listen, the mailbox opened to read it, an order said with «usted», as an
    infinitive or with a split clitic), with the form's name; None when there is none. The decision and the
    argument binder both read the request through here, so the arguments come from the same clause the decision
    read (tanda 3 «para la música, me va a explotar la cabeza» was read and then asked which action)."""

    if reported_own_schedule(text):
        # Tanda 4f: «programé un temporizador» is what the person did; rewritten as the «usted» order it became one.
        return None
    for name, form in (
        ("order_with_talk", _order_with_talk),
        ("fronted_place", _fronted_place_request),
        ("addressed", _addressed_request),
        ("desired_media", _desired_media_request),
        ("mailbox_opened", _mailbox_opened_to_read),
        ("wished_notice", _wished_notice_request),
        ("player_opened_to_play", _player_opened_to_play_request),
        ("imperative_rewrite", _imperative_rewrite_request),
    ):
        effects = form(text, resolve)
        if effects is not None:
            return name, effects
    return None


def read(
    text: str,
    *,
    available_operations: Iterable[str],
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
    previous_user_text: str | None = None,
) -> Reading:
    """The reading gate (Fase 3.5): the turn consumes this instead of calling the readers one by one."""

    available = tuple(available_operations)

    def resolve(candidate: str) -> EffectIntent | None:
        if resolve_explicit_clarification_intent(candidate, available, application_names) is not None:
            # M143 (DEV-H v4o H-s092 «so like, is it gonna rain where my grandma lives this weekend?» → this PC's town,
            # where the isolated decider asked which city): an order read out of talk is read as it would be alone, and
            # alone it is asked (the clarification goes first); the talk around it leaves it to the decider.
            return None
        return resolve_explicit_effects(candidate, available, application_names, game_catalog)

    effects = resolve_explicit_effects(
        text, available, application_names, game_catalog, previous_user_text=previous_user_text,
    )
    source = "pattern" if effects is not None else ""
    if effects is None:
        uttered = utterance_form(text, resolve)
        if uttered is not None:
            source, effects = uttered
    clarification = resolve_explicit_clarification_intent(
        text, available, application_names, previous_user_text=previous_user_text,
    )
    return Reading(
        effects=effects,
        source=source,
        clarification=clarification,
        talk=plain_talk(text, effects=effects, clarification=clarification),
    )
