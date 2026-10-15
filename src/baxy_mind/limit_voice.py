"""The voice of a limit: a reply that says, in BAXY's first person, that he does not do what was asked, and
the defects of one that does not.
"""

from __future__ import annotations

import re

from .semantic.normalize import _policy_guard_text
from .semantic import dialogue as dialogue_slot
from . import effect_intent
from .semantic.request import fold as _reading_fold
from .semantic.conversation import asks_to_make, asks_to_order, names_a_request_noun, wants_to_consume
from .reply_language_checks import (
    limit_breaks_the_asked_verb, visible_reply_breaks_first_person, visible_reply_says_a_vulgarity,
)


# tanda-02: limits that did not sound like BAXY saying no. «Pido leer esa
# novela…, pero está fuera de lo que hago» put the person's words in his mouth;
# «activar ese modo no es una acción que realice BAXY» spoke of him in the third
# person; «Abrir la app del tiempo no está en lo que hago» and «Ir al inicio no
# lo hago» made the request, as an infinitive, the subject of the sentence.
# 00_IDENTIDAD: «Eso no lo hago», plain, in the first person.
_LIMIT_OPENING = re.compile(
    r"^\s*(?:(?:eso|esto)\s+no\s+lo\s+hago|i\s+(?:don'?t|do\s+not)\s+do\s+that)\s*[:,;.—-]\s*"
)
_LIMIT_PERSON_VOICE = re.compile(r"^(?:pido|pedi|quiero|necesito|i\s+(?:ask|want|need))\b")
_LIMIT_REQUEST_SUBJECT = re.compile(
    # A clause headed by a Spanish infinitive (with its clitics) negated by
    # «no», or by an English gerund negated by «not», later in the same clause:
    # the request made the subject of the limit.
    r"^(?:(?!(?:mejor|lugar|hogar|ayer|mujer|primer|cualquier|tercer)\b)"
    r"[a-zñ]*(?:ar|er|ir)(?:me|te|se|le|lo|la|nos|les|los|las)?\b[^.;:]*?\bno\b"
    r"|(?!(?:during|\w*thing)\b)[a-z]+ing\b[^.;:]*?\b(?:not|isn'?t|aren'?t|don'?t)\b)"
)


# M89: «no te pido encargar…», «no le digo que compre…», «I don't ask you to order…»: BAXY's own act is denied, never
# asking the person to do the thing. Folded.
_LIMIT_ASKS_THE_PERSON = re.compile(
    r"\bno\s+(?:te|le|les|os)\s+(?:pido|digo|mando|obligo|sugiero|recomiendo)\s+(?:[a-z]+(?:ar|er|ir)|que\s+[a-z]+)\b|"
    r"\bi\s+(?:do\s+not|don'?t)\s+(?:ask|tell|make)\s+you\s+to\s+\w+"
)


_LIMIT_CLITICS = r"(?:me|te|se|le|lo|la|nos|les|los|las)?"
_LIMIT_ACT_IS_NOT_ACT = re.compile(
    rf"^[a-zñ]+(?:ar|er|ir){_LIMIT_CLITICS}\b[^.;:]*?\bno\s+es\s+(?:(?:el|lo)\s+mismo\s+que\s+)?"
    rf"[a-zñ]+(?:ar|er|ir){_LIMIT_CLITICS}\b|"
    r"^[a-z]+ing\b[^.;:]*?\b(?:is\s+not|isn'?t)\s+(?:the\s+same\s+as\s+)?(?!(?:some|no|any|every)thing\b)[a-z]+ing\b"
)


# M97 (DEV-D v3x D-p29-t3 «I would like to watch this movie with English subtitles» → «I do not watch movies with
# English subtitles.»): watching, listening, reading, eating or drinking is what the person said they want to do; the
# limit denies BAXY's own act (putting it on, playing it, ordering it), never the person's (semantic.conversation.
# wants_to_consume reads the request). Folded.
_LIMIT_DENIES_CONSUMING = re.compile(
    r"\bi\s+(?:do\s+not|don'?t)\s+(?:watch|listen|see|hear|eat|drink|read)\b|"
    r"(?:^|[.:;,]\s*|\byo\s+)no\s+(?:(?:la|lo|las|los|le|les)\s+)?(?:veo|miro|escucho|oigo|como|bebo|tomo|leo)\b"
)


def _limit_denies_the_persons_act(folded_limit: str, request: object) -> bool:
    """The limit denies, as BAXY's act, the consuming the person said they want to do (see above)."""

    return wants_to_consume(request) and _LIMIT_DENIES_CONSUMING.search(folded_limit) is not None


def limit_voice_defect(text: object, request: object = "") -> str:
    """Why a limit does not say, in BAXY's own first person, that he does not do it."""

    folded = _reading_fold(str(text or "")).strip(" ¡!¿?\"«»")
    body = _LIMIT_OPENING.sub("", folded, count=1)
    clauses = [" ".join(part.split()) for part in re.split(r"[:;,.]", folded) if part.strip()]
    if len(clauses) != len(set(clauses)):
        # M89 (DEV-D v3r D-s006 «No confirmo el pedido: no confirmo el pedido.»): the limit said twice.
        return "limit_repeats_itself"
    if _LIMIT_ASKS_THE_PERSON.search(folded) is not None:
        # M89 (DEV-D v3r D-s042 «No te pido encargar o comprar un pastel…»): the limit denies asking the person to do
        # it, not doing it.
        return "limit_asks_the_person"
    # M93 (DEV-D v3u D-p02-t1 «No saco fotos: sacar una foto no es tomarla yo.»): the explanation after the colon that
    # says one act is not another act («sacar … no es tomarla», «taking … isn't snapping») explains nothing.
    if any(_LIMIT_ACT_IS_NOT_ACT.match(part.strip()) for part in re.split(r"[:;]", folded)[1:]):
        return "limit_act_is_not_act"
    if _LIMIT_PERSON_VOICE.match(body) or any(
        _LIMIT_REQUEST_SUBJECT.match(clause.strip())
        for clause in {folded, body}
    ):
        return "limit_echoes_request"
    if re.search(r"(?<!\bsoy )(?<!\bi am )(?<!\bi'm )\bbaxy\b", folded) and not (
        effect_intent.self_close_request(str(request or ""))
    ):
        return "limit_third_person"
    # M78 (DEV-D v3l s004 «recomprar el último billete de tren a huesca»): the limit contract refused «No recomprobo…»
    # and the recovered limit, judged here only, published it. A first person that is no form of the verb asked is
    # broken in either path.
    if (
        visible_reply_breaks_first_person(text)
        or limit_breaks_the_asked_verb(text, request)
        or visible_reply_says_a_vulgarity(text, request)
    ):
        return "limit_broken_person"
    if _limit_denies_the_persons_act(folded, request):
        return "limit_persons_act"
    # M62: the act denied is the act asked (checked before the reason, so the retry is told about the act).
    if _limit_changes_the_act(text, request):
        return "limit_changed_act"
    if _limit_names_no_act(text, request):
        return "limit_names_no_act"
    # Independent review B1: «¿por qué no puedes…?» asks for the reason.
    if (
        _LIMIT_REASON.search(folded)
        and not dialogue_slot.asks_for_the_reason(str(request or ""))
        # M103 (owner script t50/t51 «baxy, cierra baxy» → «No cierro BAXY desde el chat, ya que se cierra con la X de
        # su ventana o con Alt+F4.» refused, and «No cierro el pedido.» published): how BAXY is closed is what the
        # self-close limit says (its system line asks for it), however the clause is joined.
        and not (effect_intent.self_close_request(str(request or "")) and _SAYS_HOW_BAXY_CLOSES.search(folded))
    ):
        return "limit_gives_a_reason"
    return ""


# M101 (DEV-D v3z D-s037 «Eso no lo hago: tomar una foto de la playa no es algo que yo realice.», D-s042 «Eso no lo
# hago: comprar un pastel de camote en una panadería local no lo preparo yo.»): the limit named the thing asked and then
# said it again as the subject of a second denial; both drafts died (limit_echoes_request, limit_changed_act) and the
# turns ended with no final. What the opening names is the whole limit; the denial repeated after it is cut.
_LIMIT_ECHOED_DENIAL = re.compile(
    r"^(?P<opening>\s*(?:eso|esto)\s+no\s+lo\s+hago|\s*i\s+(?:don'?t|do\s+not)\s+do\s+that)\s*:\s*(?P<named>[^.;:!?]+?)"
    r"\s+(?:no|est[aá]\s+fuera|queda\s+fuera|(?:is|are)\s+(?:not|outside|beyond|something)|isn'?t|aren'?t)\b",
    re.IGNORECASE,
)
# A clause cut inside itself («tomar una foto que | no salga movida») ends in a word that leads what was cut.
_LIMIT_NAMED_OPEN_END = frozenset(
    "que de del la el los las lo un una a al en con por para y e o u ni sin si cuando donde como "
    "that which who the a an of to in on for with and or if when where".split()
)


def limit_without_its_echo(text: object) -> str:
    """«Eso no lo hago: <lo pedido> no lo preparo yo.» → «Eso no lo hago: <lo pedido>.»; empty when the text is not a
    limit of that shape (see above). The caller judges the result like any other draft."""

    found = _LIMIT_ECHOED_DENIAL.match(str(text or ""))
    if found is None:
        return ""
    named = found.group("named").strip(" ,—–-")
    if len(named.split()) < 2 or _reading_fold(named.split()[-1]) in _LIMIT_NAMED_OPEN_END:
        return ""
    opening = found.group("opening").strip()
    return f"{opening[:1].upper()}{opening[1:]}: {named}."


# M62 (v3e2-final F-w11-t1 «pideme unos tacos al pastor porfa…» → «No hago tacos al pastor.»): the talk reply's
# «no preparo» was refused (M50), and the recovered limit said «no hago» with the dish as its object — making it
# again. «Hago» with a thing as its object is making that thing; «eso no lo hago», «no hago pedidos» are not.
_LIMIT_DOES_A_THING = re.compile(
    r"\bno\s+(?:(?:lo|la|los|las|te|le|les)\s+)?hago\s+(?:(?:un|una|unos|unas|el|la|los|las|tu|tus|esos?|esas?)\s+)?"
    r"(?!(?:eso|esto|nada|yo|por|para|porque|aqui|aca|desde|en|con|ya|pedidos?|compras?|encargos?)\b)[a-z]"
)


def _limit_changes_the_act(text: object, request: object) -> bool:
    """The limit denies making a thing when the person asked to order or buy it, or denies making, cooking or
    preparing it when making was not asked (M50/M54, v3a-final and v3e2-final F-w11-t1)."""

    guarded = _policy_guard_text(text)
    if asks_to_order(request) and (
        _MAKING_ACT.search(guarded) is not None or _LIMIT_DOES_A_THING.search(_reading_fold(str(text or ""))) is not None
    ):
        return True
    return _MAKING_ACT.search(guarded) is not None and not asks_to_make(request)


# M62 (v3e2-final F-s064 «ahora sígueme, repite todo lo que diga» → «No hago el pedido.»; the same run's «No hago el
# pedido de agregar el número de móvil de Pedro»): the limit denied «the request» instead of naming what it does not
# do. «El pedido» is an act only when an order was asked («no hago pedidos de comida»).
_LIMIT_META_OBJECT = re.compile(
    r"\bno\s+(?:(?:lo|la)\s+)?(?:hago|cumplo|atiendo|proceso|realizo|ejecuto|puedo\s+(?:hacer|cumplir|atender))\s+"
    r"(?:el|la|ese|esa|este|esta|tu|su)\s+(?:pedido|solicitud|peticion|encargo)\b|"
    r"\bi\s+(?:do\s+not|don'?t|can'?t|cannot|won'?t)\s+(?:do|fulfil+|process|handle|complete|carry\s+out)\s+"
    r"(?:the|that|this|your)\s+(?:request|order)\b"
)


# M103 (owner script t50/t51 «cierra BAXY» → «No cierro el pedido.»): any act of BAXY's said of «el pedido» denies the
# request, not an act, unless the person's own words were about an order or a request.
_LIMIT_ACT_ON_THE_REQUEST = re.compile(
    r"\bno\s+(?:(?:lo|la|me|te|se)\s+)?[a-zñ]{2,}o\s+(?:el|la|ese|esa|este|esta|tu|su)\s+"
    r"(?:pedido|solicitud|peticion|encargo)\s*(?:[.!,;:]|$)"
)


def _limit_names_no_act(text: object, request: object) -> bool:
    """The limit denies «el pedido» / «the request» itself, and the person did not ask to order anything."""

    folded = _reading_fold(str(text or ""))
    if asks_to_order(request):
        return False
    return _LIMIT_META_OBJECT.search(folded) is not None or (
        _LIMIT_ACT_ON_THE_REQUEST.search(folded) is not None
        and not names_a_request_noun(request)
    )


# cien-106 «post a letter to Eris» → «I cannot post a letter to Eris because I do not have the ability to send
# messages or interact with external entities»: the limit is said plainly (00_IDENTIDAD, owner's concision rule);
# a reason for it is a claim about BAXY nobody checked (he does send messages).
_LIMIT_REASON = re.compile(r"\b(?:porque|ya\s+que|puesto\s+que|dado\s+que|debido\s+a|because|since)\b")
# M103: the way BAXY's own window is closed (its X, Alt+F4), said by the self-close limit.
_SAYS_HOW_BAXY_CLOSES = re.compile(r"\balt\s*\+?\s*f4\b|\b(?:la|the|its|su)\s+x\b")


# Tanda 3 and 4 2026-09-24 «No reanudo la lectura de la lección de francés.», «No leo libros en voz alta»: BAXY
# saying no in his first person with the verb of what he does not do is the plain limit of 00_IDENTIDAD, and both
# the limit contract and the composer's boundary check refused it four times per turn, until the recovery published
# «No pude entender bien la solicitud…». A first-person present denied at the head of a clause («no leo», «yo no
# abro», «I don't read») is the limit; knowing, having, understanding or remembering are not doing.
_FIRST_PERSON_NEGATED_DOING = re.compile(
    r"(?:^|[.:;,!¡]\s*|\byo\s+)no\s+(?:(?:me|te|se|lo|la|los|las|le|les|nos)\s+)?"
    r"(?!(?:se|creo|tengo|entiendo|conozco|recuerdo|estoy|solo|todo|mucho|tanto|como|pero|poco|claro|puedo|"
    # What he perceives is an observation of the machine («no veo ningún dispositivo»), never a limit.
    r"veo|oigo|escucho|noto|encuentro|detecto|observo|percibo|siento)\b)"
    r"(?:[a-zñ]{2,}o|doy|voy)\b|"
    r"\bi\s+(?:do\s+not|don['’]?t|never)\s+"
    r"(?!(?:know|have|understand|think|see|remember|like|want|need|mind|care|believe|recall|feel|hear|notice|"
    r"find|detect|observe|sense)\b)[a-z]{2,}\b"
)


def _unsupported_answer_has_inability(value: object) -> bool:
    """The reply says, in BAXY's first person, that he does not or cannot do it (the one owner of this reading)."""

    normalized = _policy_guard_text(value)
    return _FIRST_PERSON_NEGATED_DOING.search(_reading_fold(str(value or "")).strip()) is not None or (
        re.search(
            (
                r"\b(?:"
                r"no (?:puedo|es posible|esta disponible|se puede)|"
                # 00_IDENTIDAD «Eso no lo hago»: the plain limit is an inability.
                r"no (?:lo |la |los |las |eso )?(?:hago|llevo|manejo|gestiono)|no es algo que|"
                # Tanda 5e «No tengo whisper mode.»: a mode or function he does not have is the limit said.
                r"no tengo (?:(?:un|una|el|la|ese|esa|este|esta|ningun|ninguna)\s)?(?:[a-z]+\s)?"
                r"(?:modos?|mode|modes|funcion|funciones|opcion|opciones|option|options|feature|features)|"
                r"i (?:do not|don t) have (?:(?:a|an|the|that|this|any)\s)?(?:[a-z]+\s)?"
                r"(?:modes?|features?|options?|functions?)|"
                r"i (?:do not|don t) (?:do|handle)|(?:that|this) (?:is not|isn t|s not) something i (?:do|can do)|"
                r"(?:esa|esta|la) (?:variante|combinacion|accion|solicitud) "
                r"no (?:esta disponible|se puede completar)|"
                r"i (?:cannot|can t|am unable)|"
                r"\S.{0,160}\bcannot be\b|"
                r"(?:that|this|the requested) "
                r"(?:variant|combination|action|request) "
                r"(?:is not available|cannot be completed)|"
                r"(?:isn t|is not) (?:available|supported)"
                r")\b"
            ),
            normalized,
            re.IGNORECASE,
        )
        is not None
    )


# v3a-final F-w11-t1 «pideme unos tacos al pastor» → «…los tacos al pastor del partido no los preparo yo»: a limit on
# ordering something that says BAXY does not make it names another act. The verbs of making a thing, in the reply.
_MAKING_ACT = re.compile(
    # M62: «la luz de la cocina» (DEV-D w03-t3) is the kitchen, not cooking: the verb's forms, not the noun.
    r"\b(?:prepar\w*|cocin(?:o|ar\w*|amos|are|aria|ado|ada|ados|adas)|fabric\w*|horne\w*|elabor\w*|cook\w*|"
    r"bak(?:e|es|ing)|brew\w*)\b"
)
