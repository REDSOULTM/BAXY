"""The contract of a bounded conversation reply: identity, origin and tastes, and the checks every such
reply passes.
"""

from __future__ import annotations

import re

from .semantic.normalize import _policy_guard_text
from .semantic import quantities as semantic_quantities
from .semantic.grammar import spoken_number_request
from .effect_intent import first_person_preference, visual_content_noun
from .semantic.request import fold as _reading_fold, read_request
from .semantic.conversation import (
    _roleplay_participant_names, asks_a_laugh, asks_baxys_name, assistant_desire_thing, sarcasm_question,
    spelling_word, versus_contenders,
)
from .semantic.system import reports_the_gpu_stopped
from .dialogue_history import _normalized_dialogue_text
from .reply_language_checks import (
    visible_reply_breaks_estar_participle, visible_reply_breaks_spanish_plural, visible_reply_breaks_word_case,
    visible_reply_calls_the_person_baxy, visible_reply_cuts_a_word, visible_reply_invents_a_spanish_infinitive,
    visible_reply_is_a_fixed_stall,
)
from .clock_facts import _calendar_contradiction, _local_now
from .conversation_checks import (
    visible_reply_denies_a_served_capability, visible_reply_offers_more, visible_reply_restates_the_request,
)
from .reply_claims import conversation_world_claim, visible_reply_asserts_an_unread_machine_state
from .conversation_shape import (
    _misses_content_shape, _numbers_in_figures, _PREFERENCE_FUNCTION_WORDS, _spells_the_word, _WRITTEN_CONTENT_SHAPES,
)
from .visible_defect import compose_visible_defect
from .unsupported_answers import _unsupported_answer_mentions_request


# Makers and model families a small local model attributes to itself when asked
# who made it; none of them is a fact BAXY holds about itself.
_INVENTED_ORIGIN = (
    r"\b(?:openai|chatgpt|gpt|alibaba|qwen|google|gemini|gemma|deepmind|meta|llama|"
    r"anthropic|claude|microsoft|copilot|mistral|ibm|granite|deepseek|nvidia)\b"
)

# tanda-02 «what keeps you busy in your free time» → «coding and fixing bugs»:
# BAXY has no tastes, hobbies or free time, so a first-person taste or pastime
# stated as his is invented. Negated forms («no me gusta nada», «I don't have
# hobbies») are not matched.
_INVENTED_TASTE = (
    r"(?<!\bno\s)\bme\s+(?:gusta|gustan|encanta|encantan)\b|(?<!\bno\s)\bdisfruto\b|"
    r"\ben\s+mi\s+tiempo\s+libre\b|\bmis?\s+(?:pasatiempos?|hobbies|hobby|aficion(?:es)?)\s+"
    r"(?:favorit[oa]s?\s+)?(?:es|son)\b|"
    r"\bi\s+(?:really\s+)?(?:like|love|enjoy)\b|\bin\s+my\s+(?:free|spare)\s+time\b|"
    r"\bmy\s+(?:favorite\s+)?(?:hobby|hobbies|pastimes?)\s+(?:is|are)\b|\bkeeps\s+me\s+busy\b"
)

# What BAXY holds about himself, one of which every identity answer says: his name, the PC he lives on as a
# program.
_IDENTITY_ORIGIN_SIGNAL = (
    r"\b(?:cre\w*|naci\w*|desarroll\w*|lanz\w*|edad|anos?|version|entren\w*|created|born|made|built|trained|"
    r"released|launched|developed|age|years?|version|since|desde|en\s+el\s+ano)\b"
)
_IDENTITY_OWN_FACT = (
    r"\b(?:baxy|pc|computadora?|ordenador|equipo|computer|machine|programa|program)\b"
)
# M90 (cien-110 079 «quién eres» → «Soy BAXY, un programa que vive y corre en este PC. No tengo nombre propio ni
# edad, …»; the same in cien-108 and 109): his name is one of his facts, BAXY; saying he has none contradicts it.
_IDENTITY_NAME_DENIED = (
    r"\b(?:no\s+tengo|ni|sin|carezco\s+de)\s+(?:un\s+)?nombre\b|"
    r"\b(?:don\s+t|do\s+not)\s+have\s+(?:a\s+)?(?:real\s+|proper\s+|own\s+)?name\b|"
    r"\bi\s+have\s+no\s+(?:real\s+|proper\s+|own\s+)?name\b|\bnor\s+a\s+name\b|\bnameless\b"
)


def _identity_answer_head(content: str, request: object) -> str:
    """M90 (cien-110 079): an identity answer whose sentences after the first deny his name keeps its first sentence
    when that sentence alone meets the identity contract («Soy BAXY, un programa que vive y corre en este PC.»);
    otherwise the answer stays as it is and the contract judges it."""

    folded = _policy_guard_text(content)
    head = re.split(r"(?<=[.!…])\s+", content.strip(), maxsplit=1)[0].strip()
    if (
        head == content.strip()
        or re.search(_IDENTITY_NAME_DENIED, folded) is None
        or re.search(_IDENTITY_NAME_DENIED, _policy_guard_text(head)) is not None
        or _shaped_conversation_answer_violates_contract(head, request, "identity")
    ):
        return content
    return head


def conversation_reply_speaks_of_the_system(
    value: object, request: object, prior_requests: tuple[str, ...] = (),
) -> bool:
    """M93 (DEV-D v3u D-p31-t2 «…estas seguro al 100% que esto es así», D-p35-t3 «¿Qué tan confiable puedes ser?»): the
    mind published «No, no estoy seguro al 100% porque no tengo acceso a datos históricos ni a mis propias
    herramientas…» and «Soy BAXY, vivo en el PC y no tengo acceso a datos en tiempo real…»; the App refused both as
    internal_code (its UserMessagePolicy twin of the composer's check) and composed again from a bare conversation
    payload: «No tengo certeza absoluta de que no lo encontré…» and three drafts that copied the instructions
    (composition_failed). The conversation reply is judged here by the same rule, so its own retry repairs it."""

    return compose_visible_defect(
        str(value or ""), "conversation", str(request or ""), {"priorRequests": list(prior_requests)},
    ) == "internal_code"


def _shaped_conversation_answer_violates_contract(
    value: object,
    request: object,
    shape: str | None,
    *,
    authenticated_operations: tuple[str, ...] = (),
    prior_requests: tuple[str, ...] = (),
) -> bool:
    """Validate bounded no-history prose without supplying visible wording."""

    # Checked before the shape gate, because a conversation turn that denies a
    # capability the catalog serves is wrong in every shape -- including the
    # unshaped one, which is where all five V1 occurrences landed.
    if visible_reply_denies_a_served_capability(
        value,
        authenticated_operations=authenticated_operations,
    ):
        return True
    if visible_reply_asserts_an_unread_machine_state(value, request=request):
        return True
    if visible_reply_calls_the_person_baxy(value):
        # M62 (v3e2-final F-p07-t4 «Have a great day, BAXY!»): BAXY is the one speaking.
        return True
    if shape not in _WRITTEN_CONTENT_SHAPES and conversation_reply_speaks_of_the_system(value, request, prior_requests):
        return True
    # No operation ran in a conversation turn: a claimed effect or the person's
    # records stated unread are invented (owner's test 2026-09-21, turn 189 «Claro,
    # ya le hice click.»; uso real 2026-09-23 «No hay queso en la lista. Se añadirá.»).
    if (
        shape not in _WRITTEN_CONTENT_SHAPES and conversation_world_claim(value, request, prior_requests)
    ) or _calendar_contradiction(str(value or ""), str(request or ""), _local_now()):
        return True
    # D59 §6: the offer to search the news names the subject the person named; that is the offer, not an echo.
    if shape != "news_watch_limit" and visible_reply_restates_the_request(value, request):
        return True
    if (
        visible_reply_invents_a_spanish_infinitive(value)
        or visible_reply_breaks_word_case(value, request)
        or visible_reply_breaks_spanish_plural(value, request)
        # M105 (DEV-D v4a D-s076 «sentadillas búlgar»).
        or visible_reply_cuts_a_word(value)
    ):
        return True
    if visible_reply_breaks_estar_participle(value):
        return True
    if visible_reply_is_a_fixed_stall(value):
        return True
    # M53 design B (F-s097 «4,54 km/h» for 5 km in 1 h 10 min, F-w12-t3 «el promedio … es 3,14» with no data): a
    # figure derived from the person's quantities is the one BAXY computed, and an average needs numbers to average.
    if shape not in _WRITTEN_CONTENT_SHAPES and semantic_quantities.underived_figure(
        str(value or ""), str(request or ""), prior_requests,
    ):
        return True
    if shape is None:
        # Shaped replies carry their own question rules; the unshaped one is held to the prompt's «sin ofertas».
        return visible_reply_offers_more(value) or _misses_content_shape(value, request)
    content = str(value or "").strip()
    if shape == "roleplay_draft":
        participants = _roleplay_participant_names(request)
        folded_content = _policy_guard_text(content)
        return (
            not content
            or _normalized_dialogue_text(content) == _normalized_dialogue_text(request)
            or ":" not in content
            or bool(
                re.search(
                    r"\b(?:cannot|can't|can\s+t|can\s+not|no\s+puedo|no\s+puede)\b",
                    folded_content,
                )
            )
            or bool(participants)
            and not all(
                participant.casefold() in content.casefold()
                for participant in participants
            )
        )
    if shape == "spelling":
        return (
            "\n" in content
            or any(marker in content for marker in ("?", "¿", "？"))
            or not _spells_the_word(content, spelling_word(str(request or "")) or "")
        )
    if shape == "spoken_number":
        return (
            "\n" in content
            or any(marker in content for marker in ("?", "¿", "？"))
            or _numbers_in_figures(content) != {spoken_number_request(str(request or ""))}
        )
    if shape in {"content_draft", "translation"}:
        return not content or _normalized_dialogue_text(content) == (
            _normalized_dialogue_text(request)
        ) or (shape == "content_draft" and _misses_content_shape(content, request))
    if shape == "how_it_works":
        # Several sentences are expected; a question back, a chat-only
        # self-description (no PC) or a universal behaviour claim («siempre
        # preguntando», «always watching and listening») misses the contract.
        folded_content = _policy_guard_text(content)
        return (
            not content
            or _normalized_dialogue_text(content) == _normalized_dialogue_text(request)
            or any(marker in content for marker in ("?", "¿", "？"))
            or re.search(r"\b(?:pc|computador|computadora|ordenador|equipo|computer|machine)\b", folded_content) is None
            or re.search(r"\b(?:siempre|always|constantemente|constantly|en\s+todo\s+momento|"
                         r"vigil\w*|watching|escuch\w*|listening|monitor\w*)\b", folded_content) is not None
        )
    if shape == "identity":
        folded_content = _policy_guard_text(content)
        return (
            not content
            or any(marker in content for marker in ("?", "¿", "？"))
            or (
                "baxy" not in folded_content
                and asks_baxys_name(request)
            )
            # Uso real 2026-09-23 «who made you»: a maker, lab, model family or a
            # date/age is not among BAXY's facts; naming one is an invented fact. M35 (real log 66 «quién eres,
            # cuánto suma 2 más 2»): the numbers a request brings are its own, and so is their answer.
            or (
                re.search(r"\d", folded_content) is not None
                and (
                    re.search(r"\d", _policy_guard_text(str(request or ""))) is None
                    # REV2: a date, an age or a version of BAXY is invented whatever numbers the request brought.
                    or any(
                        re.search(r"\d", sentence) and re.search(_IDENTITY_ORIGIN_SIGNAL, sentence)
                        for sentence in re.split(r"[.;!]\s*", folded_content)
                    )
                )
            )
            # Tanda 7 «¿quién te desarrolló?» → «No tengo información sobre quién me desarrolló.»: a bare
            # «no information» answers nothing about him; the answer carries one of his facts, his name or
            # the PC he lives on.
            or re.search(_IDENTITY_OWN_FACT, folded_content) is None
            # Tanda 4 2026-09-24 «¿en qué dirección de Google Maps te han creado?»: a maker the person named
            # is their word, answered («no tengo una dirección en Google Maps»), not a maker invented.
            or bool(
                set(re.findall(_INVENTED_ORIGIN, folded_content))
                - set(re.findall(_INVENTED_ORIGIN, _policy_guard_text(str(request or ""))))
            )
            or re.search(_INVENTED_TASTE, folded_content) is not None
            # M90 (cien-110 079): his name is BAXY; denying he has one contradicts it.
            or re.search(_IDENTITY_NAME_DENIED, folded_content) is not None
        )
    if shape == "versus_opinion":
        folded_content = _policy_guard_text(content)
        first, second = versus_contenders(request) or ("", "")
        names = [w for w in re.findall(r"[a-z0-9]{3,}", first + " " + second)]
        return (
            not content
            or "\n" in content
            or any(marker in content for marker in ("?", "¿", "？"))
            or len(re.findall(r"[.!…]\s+\S", content)) > 1
            or re.search(
                r"\b(?:en\s+mi\s+opinion|creo\s+que|diria\s+que|me\s+parece|depende|para\s+mi|yo\s+diria|"
                r"probablemente|posiblemente|seguramente|apostaria|i\s+think|i'?d\s+say|in\s+my\s+opinion|"
                r"it\s+depends|probably|i'?d\s+bet)\b",
                folded_content,
            ) is None
            or (bool(names) and not any(re.search(r"\b" + re.escape(name), folded_content) for name in names))
            or re.search(r"\d", folded_content) is not None
            or re.search(
                r"\b(?:pelicula|film|movie|comic|serie|series|episodio|episode|edicion|issue|creador|creator|"
                r"gano|derroto|vencio|termino\s+ganando|won|defeated|beat)\b",
                folded_content,
            ) is not None
        )
    if shape == "news_watch_limit":
        # D59 §6: the limit said, then the offer to search now asked; nothing promised for later.
        folded_content = _policy_guard_text(content)
        return (
            not content
            or "\n" in content
            or not any(marker in content for marker in ("?", "？"))
            or len(re.findall(r"[.!?…]\s+\S", content)) > 1
            or re.search(r"\b(?:no|not|don\W?t|do\s+not|can\W?t|cannot|can\s+not|unable)\b", folded_content) is None
            or re.search(r"\b(?:busqu\w*|busc\w*|search\w*|look\s+(?:up|for)|check)\b", folded_content) is None
            or re.search(
                r"\b(?:te\s+avisare|te\s+aviso\s+cuando|te\s+notificare|te\s+lo\s+notifico|estare\s+atent[oa]|"
                r"i\W?ll\s+(?:let\s+you\s+know|notify|alert|keep\s+(?:you|an\s+eye))|i\s+will\s+(?:let\s+you\s+know|notify|"
                r"alert|keep\s+(?:you|an\s+eye)))\b",
                folded_content,
            ) is not None
        )
    if shape == "assistant_desire":
        folded_content = _policy_guard_text(content)
        thing_words = [
            w for w in re.findall(r"[a-z0-9]{4,}", _policy_guard_text(assistant_desire_thing(request) or ""))
            if w not in _PREFERENCE_FUNCTION_WORDS
        ]
        return (
            not content
            or "\n" in content
            or any(marker in content for marker in ("?", "¿", "？"))
            # KNOWLEDGE1527: the model adds a third short sentence («Gracias por pensar
            # en mí»); three are accepted, «por favor dime» is not an acceptance.
            or len(re.findall(r"[.!…]\s+\S", content)) > 2
            or re.search(
                r"\b(?:no\s+(?:necesito|quiero|tengo|puedo\s+(?:querer|tener|tomar|comer|usar))|no\s+me\s+hace\s+falta|"
                r"i\s+(?:don't|do\s+not)\s+(?:need|want)|no\s+need)\b",
                folded_content,
            ) is None
            or (bool(thing_words) and not any(re.search(r"\b" + re.escape(w[:-1] if len(w) > 5 else w), folded_content) for w in thing_words))
            or re.search(
                r"\b(?:si,?\s+quiero|me\s+encantaria|me\s+gustaria|claro\s+que\s+si|"
                r"yes,?\s+please|i'?d\s+love|i\s+would\s+like|me\s+encanta|me\s+gusta)\b",
                folded_content,
            ) is not None
        )
    if shape == "sarcastic_answer":
        folded_content = _policy_guard_text(content)
        question_words = re.findall(r"[a-z]{4,}", _policy_guard_text(sarcasm_question(request) or ""))
        return (
            not content
            or "\n" in content
            or any(marker in content for marker in ("?", "¿", "？"))
            or len(re.findall(r"[.!…]\s+\S", content)) > 1
            or re.search(
                r"\b(?:si|claro|obvio|obviamente|por\s+supuesto|evidentemente|desde\s+luego|yes|of\s+course|obviously|sure)\b",
                folded_content,
            ) is None
            or (bool(question_words) and not any(re.search(r"\b" + re.escape(w[:-1] if len(w) > 5 else w), folded_content) for w in question_words))
            or re.search(r"\d", folded_content) is not None
            or re.search(r"\b(?:idiota|estupid|tont[oa]|imbecil|stupid|idiot|dumb)\w*", folded_content) is not None
        )
    if shape == "free_content":
        folded_content = _policy_guard_text(content)
        # A joke is often a question with its answer («¿Por qué…? Porque…»);
        # only a reply that ends by asking the person misses the contract. A
        # poem asked for keeps its four lines (tanda 4c). A laugh is short (tanda 6).
        laugh = asks_a_laugh(request)
        return (
            not content
            or len(content) < (4 if laugh else 20)
            or content.count("\n") > 4
            or content.rstrip().rstrip("😄😎🙂😂🤣!. ").endswith(("?", "？"))
            or re.search(
                r"\b(?:que\s+tipo|what\s+kind|which\s+kind|prefieres|preferis|te\s+gustaria|would\s+you\s+like|"
                r"idioma|language|en\s+espanol\s+o|in\s+spanish\s+or|elige|elegi|choose|"
                # tanda-02: «¿Quieres un chiste de algún tema? Por ejemplo, …»
                # offers a menu of topics instead of the joke.
                r"algun\s+tema|que\s+tema|tema\s+especifico|quieres\s+(?:un|una|que)|"
                r"which\s+topic|what\s+topic|specific\s+topic|do\s+you\s+want|want\s+(?:a|one|me))\b",
                folded_content,
            ) is not None
        )
    if shape == "misnamed_greeting":
        folded_content = _policy_guard_text(content)
        name_used = _reading_fold((read_request(str(request or "")).ask or "").strip(" .!"))
        return (
            not content
            or "\n" in content
            or "baxy" not in folded_content
            or bool(name_used) and re.search(
                r"\b(?:soy|i am|i'm|im|me llamo|my name is)\s+" + re.escape(name_used) + r"\b", folded_content,
            ) is not None
        )
    if shape == "visual_content_boundary":
        folded_content = _policy_guard_text(content)
        noun = visual_content_noun(str(request or ""))
        return (
            not content
            or "\n" in content
            or any(marker in content for marker in ("?", "¿", "？"))
            or re.search(r"\b(?:no\s+puedo|no\s+tengo|no\s+te\s+puedo|no\s+es\s+algo|can'?\s?t|cannot|can\s+not|unable|no\s+muestro|no\s+envio|no\s+mando)\b", folded_content) is None
            or re.search(r"\b(?:pido|te\s+pido|i\s+ask|aqui\s+tienes|aqui\s+va|here\s+is|here'?s)\b", folded_content) is not None
            or (bool(noun) and re.search(r"\b(?:meme|memes|imagen|imagenes|foto|fotos|gif|gifs|sticker|stickers|dibujo|dibujos|picture|pictures|image|images|photo|photos)\b", folded_content) is None)
        )
    if shape == "preference_ack":
        folded_content = _policy_guard_text(content)
        # MEMORY1503: the acknowledgement names the person's preference and
        # never the assistant's own tastes, offers or questions (MEMORY1501
        # finals «Me encanta el café…», «¡A mí también! ¿Te gusta…?»,
        # «¡Claro! ¿Quieres un té…?»).
        taste = _policy_guard_text(first_person_preference(request) or "")
        # Verification 2026-09-25 (owner script «Me gusta como se desenvuelven» → «…el modo en que se desarrollan…»
        # rejected twice, then a recovery question): a taste said as a manner («cómo se desenvuelven», «how they
        # talk») names no thing; it is acknowledged in other words. A thing («el café») is still named.
        manner = re.match(r"(?:como|cuando|lo\s+que|la\s+forma|el\s+modo|how|when|what|the\s+way)\b", taste) is not None
        thing_words = [] if manner else [
            word
            for word in re.findall(r"[a-z0-9]+", taste)
            if len(word) >= 4 and word not in _PREFERENCE_FUNCTION_WORDS
        ]
        return (
            not content
            or "\n" in content
            or any(marker in content for marker in ("?", "¿", "？"))
            or len(re.findall(r"[.!…]\s+\S", content)) > 1
            or (bool(thing_words) and not any(re.search(r"\b" + re.escape(word[:-1] if len(word) > 5 else word), folded_content) for word in thing_words))
            or re.search(
                r"\b(?:me\s+(?:gusta|gustan|encanta|encantan|fascina|fascinan)|a\s+mi\s+tambien|yo\s+tambien|"
                r"prefiero|adoro|amo|odio|detesto|mi\s+favorit[oa]|mis\s+favorit[oa]s|i\s+(?:like|love|prefer|hate|enjoy)|me\s+too|my\s+favou?rite)\b",
                folded_content,
            ) is not None
            or re.search(
                r"\b(?:quieres|queres|quiere|te\s+preparo|te\s+sirvo|te\s+traigo|te\s+hago|te\s+compro|te\s+pido|"
                r"te\s+recomiendo|te\s+sugiero|would\s+you\s+like|do\s+you\s+want|shall\s+i|i\s+can\s+(?:make|bring|get|prepare)|"
                # The folded draft writes «I'll» as «i ll».
                r"guarde|guardado|lo\s+recordare|i\s+saved|i\s?'?ll\s+remember|"
                # Tanda 6 «Gracias, ya lo tengo en cuenta»: keeping it in mind is a claim of memory no one asked
                # to save (D3); the acknowledgement stays a listener's.
                r"(?:lo|la|los|las)\s+(?:tengo|tendre|tomo|tomare)\s+en\s+cuenta|tom[oe]\s+nota|anotad[oa]|lo\s+anoto|"
                r"lo\s+recuerdo|me\s+lo\s+guardo|me\s+acordare|(?:i\s?'?ll|i\s+will)\s+(?:keep|bear)\s+(?:that|it|this)\s+in\s+mind|"
                r"noted|i\s?'?ll\s+note|(?:i\s+)?(?:have|made|make)\s+a\s+note)\b",
                folded_content,
            ) is not None
        )
    if shape == "reassurance_ack":
        folded_content = _policy_guard_text(content)
        # CONVERSATION1347: «Gracias, entiendo. No hay problema.» is a fine
        # acknowledgement; up to two short sentences are accepted.
        return (
            not content
            or "\n" in content
            or any(marker in content for marker in ("?", "¿", "？"))
            or len(re.findall(r"[.!…]\s+\S", content)) > 1
            or re.search(
                r"\b(?:abri|abrio|cerre|cerro|esta\s+abiert[oa]|esta\s+cerrad[oa]|is\s+open|is\s+closed|"
                r"i\s+opened|i\s+closed|opened\s+it|closed\s+it|lo\s+abri|lo\s+cerre|la\s+abri|la\s+cerre)\b",
                folded_content,
            ) is not None
        )
    if shape == "constraint_ack":
        # UI1647 «No escribas nada en ningún lado.»: «Entendido. No escribiré
        # nada en ningún lado.» is the one-sentence acknowledgement behind a
        # bare interjection; the contract reads the sentence that follows it.
        content = re.sub(
            r"^(?:entendido|entendida|de acuerdo|ok|okay|vale|perfecto|claro|listo|bien|"
            r"est[aá] bien|got it|understood|sure|alright|all right|okay then|fine)[.!…]\s+",
            "",
            content,
            count=1,
            flags=re.IGNORECASE,
        )
    if (
        not content
        or "\n" in content
        or "\r" in content
        or (
            shape != "observation_ack"
            and any(marker in content for marker in ("?", "¿", "？"))
        )
        # A trailing decorative symbol is not another sentence. Still reject
        # lexical content after the boundary, including after decorations.
        or re.search(r"[.!…]\s+\W*\w", content) is not None
    ):
        return True
    folded = _policy_guard_text(content)
    if re.search(
        r"\b(?:puedo ayudarte|en que puedo ayudarte|let me know|i can help|"
        r"feel free|quieres que|would you like|intentalo de nuevo|try again)\b",
        folded,
    ):
        return True
    if re.search(
        r"\b(?:literal anchors?|literal_anchors?|aviso de contexto|"
        r"terminos literales|se menciono que se debe|google drive|"
        r"documentos de trabajo|task \d+)\b",
        folded,
    ):
        return True
    if "baxy" in folded and "baxy" not in _policy_guard_text(request):
        return True
    if shape != "observation_ack" and not _unsupported_answer_mentions_request(
        content, request
    ):
        return True
    if shape == "missing_context":
        missing = re.search(
            r"\b(?:falta|faltan|no tengo|no aparece|no esta|sin|ausente|"
            r"missing|not present|not available|do not have|don t have)\b",
            folded,
        )
        reference = re.search(
            r"\b(?:contexto|referencia|tarea|alternativas|resultados|acciones|"
            r"progreso|sesion|dialogo|context|reference|task|alternatives|"
            r"results|actions|progress|session|dialogue)\b",
            folded,
        )
        return missing is None or reference is None
    if shape == "underspecified_comparison":
        return not (
            re.search(r"\bcompar\w*", folded)
            and re.search(r"\b(?:alternativas|opciones|alternatives|options)\b", folded)
            and re.search(
                r"\b(?:falta|faltan|no nombras|no estan|missing|not named|"
                r"not specified)\b",
                folded,
            )
        )
    if shape == "observation_ack":
        request_folded = _policy_guard_text(request)
        if (
            not reports_the_gpu_stopped(request_folded)
        ):
            return False
        return (
            re.search(
                r"\b(?:entiendo|mencionas|observas|indicas|segun tu|"
                r"i understand|you mention|you observe|you indicate|"
                r"your observation)\b",
                folded,
            )
            is None
        )
    return False
