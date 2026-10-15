"""How a failure is worded: the markers of a told failure, a failed act denied, the person's own failure
words, and a talk reply that tells a failure or a limit.
"""

from __future__ import annotations

import re

from .semantic.normalize import _accent_folded_with_punctuation
from .semantic import claims as semantic_claims
from .semantic.request import fold as _reading_fold
from .semantic.conversation import (
    asks_whether_able, ends_asking_the_person, without_quoted_speech, without_saying_inability,
)
from .compose_situation import _decoded_reason, _FAILED_ATTEMPT


_FAILURE_MARKERS = re.compile(
    # A7 E6 (FINAL t305): «No he podido subir el volumen» is «no pude» in the perfect tense; twin in the App's
    # UserMessagePolicy.LooksLikeFailure.
    r"(?:no pude|no puedo|no (?:he|hemos) podido|(?:haven't|have not) been able|couldn't|could not|can't|cannot|"
    r"eso no lo hago|i don't do that|i do not do that|"
    r"no la encontré|no lo encontré|no pude encontr|"
    r"no responde|se agotó|"
    # H0714/H0401: «Windows no aceptó la solicitud de apagado, por lo que el PC
    # sigue encendido» es un fallo dicho entero y bien, pero ningún marcador lo
    # reconocía y el turno moría en missing_failure tras tres borradores. Que
    # algo no se acepte o se rechace es afirmar que no ocurrió.
    r"no acept[oó]|no fue aceptad[ao]|no la acept[oó]|no lo acept[oó]|"
    r"(?:did\s*n[o']t|does\s*n[o']t|was\s+not)\s+accept(?:ed)?|"
    r"rechaz[oó]|rechazad[ao]|refused|rejected|"
    r"didn't find|did not find|didn't respond|did not respond|"
    r"time ran out|not found|"
    r"irrelevant|irrelevantes?|no useful results|nothing useful|"
    r"sin resultados|no (?:hubo|hay) resultados|no encontr[eé] resultados|no results|"
    # Owner's test 2026-09-21 (turn 205): «ya estaba silenciado, así que no cambió
    # nada» states the failure entire — nothing changed — and died in
    # missing_failure; that nothing changed is affirming it did not happen.
    r"no cambi[oó] nada|no cambi[eé] nada|no se cambi[oó] nada|no hubo cambios?|"
    # M101 (owner script v3z2 t45 «silencia mi microfono», already muted): «…no hubo ningún cambio» as well.
    r"no hubo ning[uú]n cambio|"
    r"nothing (?:was )?changed|no change was made|"
    # ctx-dueno-05 (2026-09-22, «en Steam ve a Crash Bandicoot»): «Intenté hacer
    # clic … pero no hay nada en la pantalla con ese nombre, así que no se
    # realizó la acción» died in missing_failure after the two drafts that named
    # the failure differently died in missing_prior_open and reversed_polarity.
    r"no se realiz[oó]|no se hizo|no se pudo|no se pudieron|no fue posible|no realic[eé]|"
    # M101 (DEV-D v3z D-p31-t2, turn_runtime_failure): «No he procesado tu mensaje porque no logré interpretar…» says
    # the failure entire and died in missing_failure; the App's LooksLikeFailure already reads «no logré» and «no
    # completé» as failures (twin).
    r"no logr[eé]|no complet[eé]|"
    r"was not (?:done|performed|carried out)|could not be (?:done|performed)|"
    # DOWNLOAD2047: «no se guardó nada», «no se bajó la portada» say the failure.
    r"no se (?:guard[oó]|baj[oó]|descarg[oó]) |nada se guard[oó]|nada fue guardad[oa]|no guard[eé] nada|"
    r"nothing was saved|was not saved|"
    # PPTX2051 «make a presentation about dogs with 5 slides» with file.open not
    # verified: «the opening is not confirmed», «cannot be verified» say the
    # failure entire; the Spanish «no pude confirmar» already counted.
    r"(?:is|was|were|could)\s+not\s+(?:be\s+)?(?:confirmed|verified)|cannot\s+be\s+(?:confirmed|verified)|"
    r"not\s+confirmed|unconfirmed|unverified|no\s+(?:est[aá]|qued[oó]|queda)\s+confirmad[oa]|sin\s+confirmar|"
    # WINGET2083 «instala 7-Zip»: «no se puede confirmar que se haya instalado»
    # and «no se confirma la instalación» say the failure as plainly.
    # Tanda 9 «¿me ha llegado algún correo nuevo?» without Outlook: «No se puede verificar si hay correos nuevos
    # porque Outlook no está configurado» says it as plainly, and the turn ended in ⚠ after three drafts.
    r"no\s+(?:se\s+)?(?:puede|pude|puedo|podemos|logro|logr[oó])\s+(?:confirmar|verificar|comprobar)|"
    r"no\s+se\s+(?:confirma|verifica|comprueba)|"
    # Held-out t17 «tengo ganas de escuchar reggaetón», Spotify pressed but not verified playing: «No se ha
    # verificado que esté sonando…», «No estoy seguro de que el reggaetón esté sonando…» said it three times and the
    # turn ended in ⚠.
    r"no\s+se\s+(?:ha\s+|han\s+)?(?:confirm|verific|comprob)(?:[oó]|ado|ada|aron)\b|"
    r"no\s+(?:est[aá]|qued[oó])\s+(?:verificad|comprobad)[oa]|no\s+estoy\s+segur[oa]\s+de\s+que)",
    re.IGNORECASE,
)
_NEGATED_FAILURE = re.compile(
    r"\b(?:(?:sin|ningun[oa]?|no\s+(?:hay|hubo))\s+(?:ningun[oa]?\s+)?fallos?\b"
    r"|no\s+se\s+(?:(?:ha|han)\s+)?(?:detect|registr|report|encontr)(?:ado|o|aron)\s+(?:ningun[oa]?\s+)?fallos?\b"
    r"|(?:not|never)\s+failed\b|(?:no|zero|0)\s+failed\b"
    r"|none\s+of\s+(?:(?!(?:but|and)\b)\w+\s+){1,5}failed\b)"
)


# M93 (held-out v3v t10): the list of open programs and windows, as the inventory_failed cause names it. Folded.
_OPEN_PROGRAMS_LIST = re.compile(
    r"\b(?:programas|ventanas|aplicaciones|apps|procesos)(?:\s*,?\s+(?:y|e|o)\s+(?:las\s+|los\s+)?"
    r"(?:programas|ventanas|aplicaciones|apps|procesos))?\s+abiert[oa]s\b"
)


def _asserts_failure(text: str) -> bool:
    # Same assertion scope as UserMessagePolicy.LooksLikeFailure: negating one
    # failure does not erase an independent failure later in the sentence.
    assertions = _NEGATED_FAILURE.sub("", _accent_folded_with_punctuation(text))
    # M93 (held-out v3v t10 «El Bloc de notas no pudo abrirse porque…», missing_failure): «no pudo abrirse» is «no se
    # pudo abrir» with its pronoun after the verb. Twin: UserMessagePolicy.LooksLikeFailure.
    return _FAILURE_MARKERS.search(text) is not None or re.search(
        r"\b(?:fallos?|failed)\b|\bno\s+(?:encontre|se\s+(?:pudo|pudieron|encontro|encontraron))\b|"
        r"\bno\s+pud(?:o|ieron)\s+[a-z]+(?:arse|erse|irse)\b",
        assertions,
    ) is not None


def _denies_the_failed_act(text: str, situation: dict) -> bool:
    """Uso real t2-r4 c01-1: a failure told as the act not done, in the first person or the reflexive passive, with
    the act's own verb («No puse los bunkers en Spotify porque…», «No se pusieron…» for a media.play.query) is the
    failure told; three such drafts died wanting «no pude» and the final fell to a generic sentence with no cause. Only
    the failed operation's own acts count (semantic.claims.operation_acts): «no lo cerré» over a play stays a defect.
    Ronda 19 (r17 t3-c07 «No envié el mensaje a ron92… porque el cliente no estaba abierto» over a recipient.resolve
    that left message.send undone, twice missing_failure): the acts of the effects the failure left undone
    (``notDone``, on the failed step or on the situation) are the failure told too; an act of neither stays a defect.
    Ronda 19b (r17 t1-c09, the same turn's retry «le envié el mensaje…, pero el mensaje no se envió»): a draft that
    also tells that act as done tells a failure as a success: an operation whose acts the draft both denies and
    claims denies nothing."""

    step = _decoded_reason(situation) or situation
    operations = [str(step.get("operation") or "")]
    for record in (step, situation):
        undone = record.get("notDone") if isinstance(record, dict) else None
        for item in undone if isinstance(undone, list) else ():
            if isinstance(item, dict):
                operations.append(str(item.get("operation") or ""))
    denied = semantic_claims.denied_acts(text)
    claimed = {lemma for _, lemmas in semantic_claims.claimed_acts(text, third_person=False) for lemma in lemmas}
    for operation in dict.fromkeys(operations):
        acts = semantic_claims.operation_acts(operation) or frozenset()
        if denied & acts and not claimed & acts:
            return True
    return False


def _failure_word_is_the_persons(text: str, user_text: str) -> bool:
    """Owner script «Por dios, odio estos fallos» → «Entiendo que la frustración por los fallos es inmensa»: the
    person's «fallos», answered back («los/estos/esos fallos»), claims no failure of BAXY's. «Hubo un fallo», «failed»
    or a failure phrase of its own («no pude…», «no se encontró…») still does."""

    if re.search(r"\bfallos\b", _accent_folded_with_punctuation(user_text or "")) is None:
        return False
    rest = _ECHOED_FAILURES.sub("", str(text))
    # Independent review B3: «Estos fallos se deben a que Spotify no respondió» states a cause of BAXY's.
    if _FAILURE_CAUSE.search(_accent_folded_with_punctuation(rest)) is not None:
        return False
    return rest != str(text) and not _asserts_failure(rest)


def talk_reply_tells_a_failure(reply: object, request: object) -> bool:
    """M101 (DEV-D v3z D-p31-t2 «…estas seguro al 100% que esto es así» → recovered «No tengo certeza absoluta ni
    puedo garantizar resultados…»): a talk reply that tells a failure of BAXY's, which the App's conversation policy
    refuses as looks_like_failure (twin of its exemptions: a question to the person that claims no failed attempt,
    whether BAXY is able, the person's own «fallos»). The App's reading of a knowledge question is narrower than the
    mind's, so that exemption is not assumed: the recovery then asks back instead of handing the App a refusal."""

    text = str(reply or "")
    told = without_quoted_speech(text)
    if not _asserts_failure(told):
        return False
    failed_attempt = _FAILED_ATTEMPT.search(_reading_fold(text)) is not None
    if ends_asking_the_person(text) and not failed_attempt and not _asserts_failure(without_saying_inability(told)):
        return False
    if asks_whether_able(str(request or "")) and not failed_attempt:
        return False
    return not _failure_word_is_the_persons(text, str(request or ""))


# M139 (DEV-G v4n G-s120 «…get a large pepperoni pie delivered from the Domino's on 5th for me», decided social): both
# drafts said the limit — «I can't deliver food or place orders for you.», «…cannot interact with the physical world or
# order food.» — and died as told_failure (the App refuses a failure told in talk); the recovery then wrote the talk
# again with nothing to say and published «I will get a large pepperoni pie delivered…». A told failure that is an
# inability in the present (no attempt failed) and not about knowing or being sure is the limit the model saw: the
# turn's recovery says it as a limit (conversationKind «unsupported»), which the App publishes. Folded.
_PRESENT_INABILITY = re.compile(
    r"\b(?:cannot|can[’']?t|can\s+not|(?:am|i[’']?m)\s+(?:not\s+able|unable)\s+to|no\s+(?:puedo|soy\s+capaz\s+de)|"
    r"no\s+(?:lo\s+|la\s+|los\s+|las\s+|eso\s+)?(?:hago|manejo)|i\s+(?:do\s+not|don[’']?t)\s+(?:do|handle))\b"
)
_KNOWING_INABILITY = re.compile(
    r"\b(?:cannot|can[’']?t|can\s+not|(?:am|i[’']?m)\s+(?:not\s+able|unable)\s+to|no\s+(?:puedo|soy\s+capaz\s+de))\s+"
    r"(?:\w+\s+)?(?:know|tell|say|be\s+(?:sure|certain)|guarantee|confirm|predict|guess|verify|check|"
    r"saber|decir\w*|asegurar\w*|garantizar\w*|confirmar\w*|predecir|adivinar|verificar\w*|comprobar\w*|"
    r"estar\s+segur[oa])\b"
)


def talk_reply_tells_a_limit(reply: object) -> bool:
    """A talk reply's told failure that is a present inability to do something, not a failed attempt nor not knowing
    (see above)."""

    folded = _reading_fold(without_quoted_speech(str(reply or "")))
    return (
        _PRESENT_INABILITY.search(folded) is not None
        and _FAILED_ATTEMPT.search(folded) is None
        and _KNOWING_INABILITY.search(folded) is None
    )


# Twin of UserMessagePolicy.EchoedFailures.
_FAILURE_CAUSE = re.compile(r"\b(?:se\s+deben?|debid[oa]s?|porque|ya\s+que|because|due\s+to|caused)\b")
_ECHOED_FAILURES = re.compile(r"\b(?:los|estos|esos|tantos|tus|sus)\s+fallos\b", re.IGNORECASE)
