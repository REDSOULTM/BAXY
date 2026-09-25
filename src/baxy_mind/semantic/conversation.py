"""Messages that ask BAXY to talk, not to act: a social act, a nonunderstanding, a question of knowledge or a
limit BAXY states.

They moved from ``__main__`` with the unification of the reading (owner, 2026-09-24: every reading of the request
lives in ``semantic/``). Each returns what it read — the conversation kind and the language to answer in, or
whether the form is there — and ``__main__`` builds the turn decision from it. None grants an operation.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .. import effect_intent
from .catalog import ApplicationCatalogIndex, GameCatalogIndex, build_application_catalog_index
from .dialogue import _history_has_pending_clarification, _previous_user_request
from .grammar import ARITHMETIC_EXPRESSION, SPOKEN_NUMBER, spoken_number_request
from .intent import EffectIntent
from .patterns import conversation_only_content_request, echo_mode_request
from .request import (
    INTENT_AMBIGUOUS_ACTION,
    INTENT_CAPABILITY,
    INTENT_IDENTITY,
    _INTERROGATIVE,
    fold as _reading_fold,
    read_request,
    response_language as read_language,
    speaking_directive,
)
from .grammar import _strip_request_envelope
from .normalize import _accent_folded_with_punctuation, _policy_guard_text
from .patterns import (
    explicit_negative_constraint,
    explicit_non_action_body,
    first_person_preference,
    reassurance_statement,
    reported_own_schedule,
)
from .web import visual_content_request


# Un acto social completo no pide nada: saludar, despedirse, agradecer o
# preguntar cómo está el asistente no nombra un efecto ni concede autoridad.
# Las alternancias son cerradas y se consumen con `re.fullmatch`, así que
# cualquier cláusula añadida —«hola, pon el volumen al 30»— deja de coincidir y
# vuelve al modelo. Cada rama declara su idioma porque el propio patrón ya lo
# fija; derivarlo de un contador de tokens respondería en español a «hi».
_SOCIAL_SEPARATOR = r"[\s,;:.!¡¿]+"


_SOCIAL_VOCATIVE = r"baxy"


_SOCIAL_ACTS: tuple[tuple[str, dict[str, str]], ...] = (
    (
        "es",
        {
            "acknowledgement": (
                r"(?:muy bien|de una|perfecto|excelente|genial|barbaro|listo)"
            ),
            "greeting": (r"(?:buenos dias|buenas tardes|buenas noches|buenas|hola)"),
            "farewell": (
                r"(?:hasta luego|hasta pronto|hasta manana|nos vemos|"
                r"nos hablamos|adios|chau|chao)"
            ),
            "gratitude": (
                r"(?:muchas gracias|mil gracias|"
                r"gracias(?: por (?:todo|tu ayuda|la ayuda))?|"
                r"te lo agradezco)"
            ),
            "compliment": (r"(?:sos un capo|eres un capo|sos genial|eres genial)"),
            # MASSIVE general_joke «toc toc»: the opening of a knock-knock joke is answered in play.
            "game": r"(?:toc,? toc)",
            # Uso real tanda 5 «¿qué dices de nuevo?» (what's new) was answered with an invented list of
            # what BAXY does, «lanzar dados» included: asking what is new greets like «qué tal».
            "wellbeing": (
                r"(?:como estas|como andas|como va|que tal todo|que tal|"
                r"todo bien|que dices de (?:nuevo|bueno)|que (?:hay|me cuentas|cuentas)(?: de (?:nuevo|bueno))?|"
                r"que onda|que hubo|quiubo|que novedades)"
            ),
        },
    ),
    (
        "en",
        {
            "acknowledgement": (r"(?:very well|perfect|excellent|great|awesome|nice)"),
            "greeting": (
                r"(?:good morning|good afternoon|good evening|"
                r"(?:hello|hey|hi)(?: there)?)"
            ),
            "farewell": (
                r"(?:see you later|see you|good night|goodbye|good bye|"
                r"take care|bye)"
            ),
            "gratitude": (
                r"(?:thanks(?: a lot| so much)?|"
                r"thank you(?: very much| so much)?)"
            ),
            "compliment": (
                r"(?:you are great|you are awesome|you(?:['’]?re) great|"
                r"you(?:['’]?re) awesome)"
            ),
            "game": r"(?:knock,? knock)",
            "wellbeing": (
                r"(?:how are you doing|how are you|how is it going|"
                r"how['’]?s it going|what(?:['’]?s| is) (?:up|new))"
            ),
        },
    ),
)


def _social_turn_pattern(parts: dict[str, str]) -> str:
    """Compose one language's closed social envelope."""

    greeting = parts["greeting"]
    core = (
        rf"(?:{greeting}(?:{_SOCIAL_SEPARATOR}{greeting})?"
        rf"|{parts['farewell']}|{parts['gratitude']}|{parts['game']})"
    )
    wellbeing = parts["wellbeing"]
    return (
        r"[¿?¡!\s]*"
        rf"(?:{parts['acknowledgement']}{_SOCIAL_SEPARATOR})?"
        rf"(?:{core}"
        rf"(?:{_SOCIAL_SEPARATOR}{_SOCIAL_VOCATIVE})?"
        rf"(?:{_SOCIAL_SEPARATOR}{wellbeing})?"
        rf"(?:{_SOCIAL_SEPARATOR}{parts['compliment']})?"
        rf"|{wellbeing})"
        r"[\s?!.]*"
    )


_SOCIAL_TURNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (language, re.compile(_social_turn_pattern(parts), re.IGNORECASE))
    for language, parts in _SOCIAL_ACTS
)


def social_act(
    objective: str,
    history: object = None,
    *,
    pending_clarification: bool | None = None,
) -> tuple[str, str] | None:
    """A standalone social act: its conversation kind («social», or «knowledge» for a question about what BAXY
    wants) and the language it was said in; None when the message is not one."""

    # Una aclaración pendiente convierte cualquier respuesta en parte de ese
    # intercambio. Ante la duda se devuelve el turno al modelo, que es
    # exactamente el comportamiento previo.
    if _history_has_pending_clarification(history, pending_clarification):
        return None
    assistant_preference = False
    folded = unicodedata.normalize("NFKD", objective.casefold())
    folded = "".join(
        character for character in folded if not unicodedata.combining(character)
    )
    folded = " ".join(folded.split())
    language = next(
        (
            candidate
            for candidate, pattern in _SOCIAL_TURNS
            if pattern.fullmatch(folded) is not None
        ),
        None,
    )
    if language is None:
        # The private-memory parser recognizes this declarative form, but it
        # grants no persistence authority. A whole self-introduction belongs
        # to conversation, before PC tools can prime a Windows-account read.
        declaration = re.fullmatch(
            r"(?:(?P<es>(?:yo\s+)?me\s+llamo|mi\s+nombre\s+es)|"
            r"my\s+name\s+is)\s+"
            r"(?P<name>[^\W\d_](?:[^\W\d_]|[ '’\-]){0,79})[.!]*",
            folded,
        )
        if declaration is not None:
            # Do not swallow an unpunctuated question or command after the
            # asserted first name. Reuse the shared vocabulary, not a name list.
            tail = declaration.group("name").strip().partition(" ")[2]
            if (
                _INTERROGATIVE.search(tail) is None
                and re.search(rf"\b{effect_intent._COVERAGE_ACTION_HEAD}\b", tail)
                is None
            ):
                language = "es" if declaration.group("es") is not None else "en"
    if language is None:
        personal_wellbeing_report = (
            (
                "es",
                r"[Â¿?Â¡!\s]*(?:mi\s+)?dia\s+"
                r"(?:fue|ha\s+sido|esta\s+siendo)\s+"
                r"(?:(?:muy|extremadamente|bastante|realmente)\s+)?"
                r"(?:duro|dificil|pesado|terrible|agotador|bueno|genial|"
                r"excelente)[\s?!.]*",
            ),
            (
                "en",
                r"[Â¿?Â¡!\s]*my\s+day\s+"
                r"(?:was|has\s+been|is\s+being)\s+"
                r"(?:(?:very|extremely|quite|really)\s+)?"
                r"(?:hard|difficult|rough|terrible|exhausting|good|great|"
                r"excellent)[\s?!.]*",
            ),
        )
        language = next(
            (
                candidate
                for candidate, pattern in personal_wellbeing_report
                if re.fullmatch(pattern, folded, re.IGNORECASE) is not None
            ),
            None,
        )
    if language is None:
        assistant_preference_question = (
            (
                "es",
                r"[¿?¡!\s]*(?:que|cual)\s+quieres\s+hacer\s+hoy[\s?!.]*",
            ),
            (
                "en",
                r"[¿?¡!\s]*what\s+do\s+you\s+want\s+to\s+do\s+today[\s?!.]*",
            ),
        )
        language = next(
            (
                candidate
                for candidate, pattern in assistant_preference_question
                if re.fullmatch(pattern, folded, re.IGNORECASE) is not None
            ),
            None,
        )
        assistant_preference = language is not None
    if language is None:
        # «Hi again» y «buenas, compa» son saludos completos: la lectura del
        # pedido los reconoce sin ampliar otro patrón por cada variante, y sin
        # tragarse un pedido que venga detrás del saludo.
        greeting = read_request(objective)
        if greeting.greeting_only:
            language = greeting.language
    if language is None:
        return None
    return ("knowledge" if assistant_preference else "social"), language


def nonunderstanding(
    objective: str,
    history: object = None,
    *,
    pending_clarification: bool | None = None,
) -> str | None:
    """A standalone comprehension reaction outside a clarification: the language to answer in, or None."""

    if _history_has_pending_clarification(history, pending_clarification):
        return None
    folded = unicodedata.normalize("NFKD", objective.casefold())
    folded = "".join(
        character for character in folded if not unicodedata.combining(character)
    )
    folded = " ".join(folded.split())
    explicit_nonunderstanding = (
        re.fullmatch(
            (
                r"[¿?¡!\s]*(?:"
                r"no (?:te )?(?:entendi|entiendo|comprendi|comprendo)|"
                r"no me quedo claro|"
                r"i (?:did not|didn't|do not|don't) "
                r"(?:understand|get it|get that)|"
                r"i(?:'m| am) confused"
                r")[\s?!.]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    has_assistant_context = isinstance(history, list) and any(
        isinstance(item, dict)
        and item.get("role") == "assistant"
        and isinstance(item.get("content"), str)
        and bool(str(item["content"]).strip())
        for item in history
    )
    elliptical_reaction = (
        has_assistant_context
        and re.fullmatch(
            (
                r"[¿?¡!\s]*(?:que|como|por\s+que|what|how|why|"
                r"que\s+dijiste|what\s+did\s+you\s+say)[\s?!.]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if not explicit_nonunderstanding and not elliptical_reaction:
        return None
    return read_language(objective)


def _current_public_role_question(objective: str) -> bool:
    """Recognize a time-sensitive office-holder fact that needs verification."""

    folded = effect_intent._strip_request_envelope(effect_intent._fold(objective))
    return (
        re.match(r"^[¿?¡!\s]*(?:quien|who)\b", folded, re.IGNORECASE) is not None
        and names_a_current_public_office(folded)
    )


def _assistant_capability_aspiration(objective: str) -> bool:
    """Recognize third-person product wishes, never direct user commands."""

    folded = effect_intent._strip_request_envelope(effect_intent._fold(objective))
    if not folded:
        return False
    return (
        re.match(
            (
                r"^(?:"
                r"i\s+(?:want|would\s+like)\s+(?:baxy|the\s+assistant|"
                r"my\s+assistant|it)\s+to\s+(?:be\s+able\s+to|have\s+(?:the\s+)?"
                r"ability\s+to)|"
                r"i(?:'d|\s+would)\s+like\s+(?:baxy|the\s+assistant|my\s+assistant|"
                r"it)\s+to\s+(?:be\s+able\s+to|have\s+(?:the\s+)?ability\s+to)|"
                r"i\s+wish\s+(?:baxy|the\s+assistant|my\s+assistant|it)\s+could|"
                r"(?:baxy|the\s+assistant|my\s+assistant|it)\s+should\s+be\s+able\s+to|"
                r"(?:quiero|me\s+gustaria)\s+que\s+(?:baxy|el\s+asistente|"
                r"mi\s+asistente|este\s+asistente)\s+(?:pueda|pudiera|"
                r"sea\s+capaz\s+de)|"
                r"ojala\s+(?:baxy|el\s+asistente|mi\s+asistente|este\s+asistente)\s+"
                r"(?:pudiera|pueda|fuera\s+capaz\s+de)|"
                r"(?:baxy|el\s+asistente|mi\s+asistente|este\s+asistente)\s+"
                r"deberia\s+(?:poder|ser\s+capaz\s+de)"
                r")\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )


def _deictic_open_request(objective: str) -> bool:
    """Recognize an opening whose operand is a reference, not a catalog name."""

    folded = effect_intent._strip_request_envelope(effect_intent._fold(objective))
    if (
        effect_intent.explicit_non_action_frame(objective)
        or not effect_intent._application_desire_is_positive(folded)
        or len(effect_intent._request_clauses(folded)) != 1
    ):
        return False
    opening = effect_intent._application_open_request(folded)
    if opening is None:
        return re.fullmatch(
            r"[¿?¡!\s]*(?:abre|abri)(?:lo|la|los|las)"
            r"(?:\s*,?\s*(?:por favor|please|porfa|porfi|porfis|plis|pls|plz))?[.!?\s]*", folded,
        ) is not None
    target = re.sub(
        # cien-36 096 «ábreme eso porfa»: the colloquial politeness word was not
        # in this list, so the request stopped being a bare deictic and went to
        # the unsupported-effect contract, which answered that it could not
        # understand instead of asking what to open, as «ábreme eso» does.
        r"\s*,?\s*(?:por favor|please|for me|porfa|porfi|porfis|plis|pls|plz)[.!?\s]*$", "",
        opening.group("target"),
    ).strip(" .!?\t\r\n")
    return re.fullmatch(
        r"(?:est[aeo]s?|es[aeo]s?|aquell[ao]s?|it|them|"
        r"(?:this|that|these|those)(?:\s+ones?)?)"
        r"(?:\s*,?\s*(?:el|la|los|las)\s+que\s+"
        r"(?:(?:te|le|les)\s+)?(?:digo|dije|indico|indique|menciono|mencione))?",
        target,
    ) is not None


def _standalone_deictic_request(objective: str, history: object = None) -> bool:
    """Recognize a command whose required referent is entirely absent."""

    if _deictic_open_request(objective):
        return _previous_user_request(
            history if isinstance(history, list) else [], objective,
        ) is None
    if read_request(objective).has(INTENT_AMBIGUOUS_ACTION):
        return True
    folded = effect_intent._fold(objective).strip()
    return (
        re.fullmatch(
            # DIALOGUE1277 H0562 «Si hazlo», «dale, hacelo»: an assent that
            # carries the order itself («hazlo», voseo «hacelo») without any
            # prior request names no action. It went to the model, which said
            # it could not understand instead of asking which action.
            r"(?:(?:si|ok|okay|dale|bueno|vale|ya|yes|yeah|sure)\s*,?\s+)?"
            r"(?:(?:por favor|please)\s*,?\s+)?(?:"
            r"haz(?:lo|\s+(?:eso|esto|aquello))|"
            r"hace(?:lo|\s+(?:eso|esto|aquello))|"
            r"dale(?:\s+con)?\s+(?:eso|esto)|"
            r"do\s+(?:it|that|this)|"
            r"make\s+(?:it|that)\s+happen|"
            r"go\s+ahead(?:\s+with\s+(?:it|that|this))?"
            r")(?:\s*,?\s*(?:por favor|please))?[.!?]*",
            folded,
        )
        is not None
    )


def _general_factoid_prompt(objective: str) -> bool:
    folded = effect_intent._strip_request_envelope(effect_intent._fold(objective))
    # Tanda 4f «cien mil doscientas veintitrés»: a number said in words is written in figures in conversation.
    if _arithmetic_question(folded) or _concept_description(folded) or spoken_number_request(objective) is not None:
        return True
    return (
        re.fullmatch(
            (
                r"[¿?¡!\s]*(?:"
                r"(?:please\s+)?tell\s+me\s+the\s+score\s+of\s+the\s+game|"
                r"what\s+sound\s+does\s+(?:an?\s+|the\s+)?"
                r"[a-z][a-z .'-]{0,48}\s+make|"
                # MASSIVE general_quirky «que sonido hace un perro»: the Spanish mirror.
                r"(?:que|cual\s+es\s+el)\s+(?:sonido|ruido)\s+(?:hace|hacen|emite|emiten|produce|producen)\s+"
                r"(?:un|una|el|la|los|las)\s+[a-z][a-z .'-]{0,48}|"
                r"(?:(?:podrias|puedes|can\s+you|could\s+you)\s+)?"
                r"(?:confirmar|confirm)\s+(?:si|whether)\s+"
                r"[a-z][a-z .'-]{0,64}\s+(?:esta\s+casad[oa]|is\s+married)|"
                # «me puedes dar una receta…»: the envelope strip already took
                # «me puedes», so «dar» may stand alone in front of the recipe.
                r"(?:(?:me\s+)?(?:puedes|podrias)\s+)?(?:dar\s+)?"
                r"(?:una\s+)?receta(?:\s+casera)?\s+(?:de|para)\s+\S.+|"
                r"cual\s+es\s+la\s+receta\s+(?:de|del)\s+\S.+|"
                r"what\s+(?:all\s+)?(?:goes|ingredients?\s+go)\s+into\s+"
                r"(?:(?:a|the)\s+)?\S.{0,96}\b(?:cake|dish|recipe)\b|"
                r"(?:necesito|quiero)\s+(?:una\s+)?receta\s+con\s+"
                r"(?:los\s+)?ingredientes\b.{0,120}|"
                r"i\s+need\s+to\s+know\s+more\s+about\s+(?:the\s+)?"
                r"(?:parade|festival|fair|concert)\s+(?:this|next)\s+weekend|"
                r"(?:give|show)\s+(?:me\s+)?details\s+(?:of|about)\s+"
                r"(?!(?:my|this|the)\s+(?:computer|pc|device|order)\b)"
                r"[a-z][a-z .'-]{1,96}|"
                r"(?:cuentame|contame|tell\s+me)\s+(?:todo|all)\s+"
                r"(?:sobre|about)\s+(?!(?:mi|mis|my|this|este|esta)\b)"
                r"[a-z][a-z .'-]{1,96})[\s?!.]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )


def _arithmetic_question(folded: str) -> bool:
    """MASSIVE qa_maths «what is four plus five», «cuál es la suma de los dos números cuatro y seis»,
    «muéstrame la respuesta a este problema doscientos cuarenta y seis más seiscientos cincuenta y cuatro»:
    arithmetic on the person's own numbers is answered in conversation. The model had sent the first to a web
    search and offered the others back as «¿Quieres que calcule…?». Typing it into the open Calculator names the
    Calculator and keeps its own reader."""

    return (
        re.fullmatch(
            r"[¿?¡!\s]*(?:(?:cuanto|cuanta)\s+(?:es|son|da|dan|seria)|cual\s+es|what(?:'s|\s+is)|how\s+much\s+is|"
            r"calcula|calculame|calculate|compute|resuelve|solve|"
            r"(?:dime|dame|muestrame|mostrame|tell\s+me|give\s+me|show\s+me)\s+(?:(?:la|el|the)\s+)?"
            r"(?:respuesta|resultado|answer|result)(?:\s+(?:a|de|of|to)\s+(?:este|esta|this)\s+"
            r"(?:problema|operacion|cuenta|problem|calculation|sum))?)?\s*"
            rf"(?:{ARITHMETIC_EXPRESSION}|"
            r"(?:(?:la|el|the)\s+)?(?:suma|resta|multiplicacion|division|producto|sum|product)\s+(?:de|of|entre|between)\s+"
            rf"(?:(?:los|las|the)\s+)?(?:(?:dos|two)\s+)?(?:(?:numeros|numbers)\s+)?{SPOKEN_NUMBER}(?:\s+(?:y|and)\s+{SPOKEN_NUMBER})?)"
            r"[\s?!.=]*",
            folded,
        )
        is not None
    )


def _concept_description(folded: str) -> bool:
    """MASSIVE qa_definition «describe infierno», «dime la descripción de teléfono inteligente», «cómo
    describirías una pelota», «describe rock sand»: describing a thing by its name is knowledge. The model
    proposed describing the screen, the domain gate withdrew it and the turn said «Eso no lo hago». What is on
    the screen, an image, a window, a file or something pointed at keeps its own readers."""

    found = re.fullmatch(
        r"[¿?¡!\s]*(?:describe(?:me)?|describa|como\s+describirias|how\s+would\s+you\s+describe|"
        r"(?:dime|dame|decime|give\s+me|tell\s+me)\s+(?:la\s+|una\s+|the\s+|a\s+)?(?:descripcion|description)\s+(?:de|del|of)|"
        r"(?:la\s+|una\s+|the\s+|a\s+)?(?:descripcion|description)\s+(?:de|del|of))\s+"
        r"(?P<thing>[a-z][a-z .'-]{0,60}?)[\s?!.]*",
        folded,
    )
    return found is not None and not re.search(
        r"\b(?:esto|eso|este|esta|ese|esa|aquello|aqui|lo\s+que|this|that|it|what|here|"
        r"mi|mis|tu|tus|my|your|pantalla|screen|imagen|imagenes|image|images|foto|fotos|photo|photos|picture|"
        r"ventana|ventanas|window|windows|video|archivo|archivos|file|files|captura|screenshot|escritorio|desktop|"
        r"camara|camera|pc|computadora|computador|equipo|computer|"
        # «describe el clima de hoy» is a live read, not a definition.
        r"clima|tiempo|weather|pronostico|forecast|noticias|news|hora|fecha|time|date|hoy|today|ahora|now|"
        r"actual|current|estado|status|sistema|system)\b",
        found.group("thing"),
    )


def _personal_checkin_statement(objective: str) -> bool:
    folded = effect_intent._strip_request_envelope(effect_intent._fold(objective))
    if (
        re.fullmatch(
            (
                r"my\s+day\s+is\s+going\s+(?:well|great|fine|okay|ok)"
                r"(?:\s*[,;]?\s*add\s+a\s+memo)?[\s.!?]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    ):
        return True
    # MEMORY1501 H0174 «Me gusta tomar café.»: a first-person taste or
    # preference with nothing asked is a statement to acknowledge, not an
    # order (MEMORY1245 asked where to go for coffee). The reader is shared
    # with the preference_ack presentation shape (MEMORY1503). Tanda 4f: so is an alarm or timer the person set
    # themselves («configuré una alarma para despertarme por la mañana»).
    return (
        effect_intent.first_person_preference(objective) is not None
        or effect_intent.reported_own_schedule(objective)
    )


def _closed_unsupported_request(objective: str) -> bool:
    """Close requests whose missing authority cannot be recovered from a tool."""

    folded = effect_intent._strip_request_envelope(effect_intent._fold(objective))
    standalone_speed = (
        re.fullmatch(
            r"(?:rapido|mas\s+rapido|faster|quicker)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    external_console_correction = (
        re.fullmatch(
            r"i\s+want\s+to\s+play\s+\S.{0,120}\s+on\s+the\s+"
            r"(?:switch|xbox|playstation|wii)\s*[,;]?\s*i\s+mean\s+the\s+"
            r"(?:switch|xbox|playstation|wii)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    external_console_game_request = (
        re.fullmatch(
            r"(?:quiero|quisiera|i\s+want\s+to)\s+(?:jugar|play)\s+"
            r"\S.{0,160}\s+(?:en|on)\s+(?:(?:la|the)\s+)?"
            r"(?:play|playstation|xbox|switch|wii)\b.{0,96}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    referential_answer_review = (
        re.fullmatch(
            r"(?:mira|revisa|comprueba|look\s+at|review|check)\s+"
            r"(?:lo\s+que|what)\s+(?:escribiste|wrote)\s+"
            r"(?:para|for|en|in)\s+(?:esta|this)\s+"
            r"(?:pregunta|question|respuesta|answer)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    nominal_reminder_fragment = re.fullmatch(
        r"(?:recordatorio|reminder)\s+(?:de|for|about)\s+"
        r"\S(?:.{0,80}?\S)?[\s.!?]*",
        folded,
        re.IGNORECASE,
    ) is not None and not effect_intent._reminder_has_actionable_due(folded)
    transactional_purchase_correction = (
        re.fullmatch(
            r"(?:compra|comprar|buy|purchase|order)\b.{0,160}"
            r"\b(?:paga|pagar|pay|paypal|tarjeta|card)\b.{0,120}"
            r"\b(?:no\s+mejor|mejor|i\s+mean|make\s+that)\b.{0,96}"
            r"\b(?:tarjeta|card|paypal|debito|credito|debit|credit)\b"
            r"[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    corrected_payment_purchase = (
        re.fullmatch(
            r"(?:necesito|quiero|i\s+need|i\s+want)\b.{0,160}"
            r"\b(?:conseguir|comprar|buy|get|purchase|pagar|pay)\b.{0,160}"
            r"\b(?:tarjeta|card|visa|mastercard|paypal|bizum)\b.{0,120}"
            r"\b(?:bueno\s+mejor|mejor|actually|i\s+mean|instead)\b.{0,96}"
            r"\b(?:tarjeta|card|visa|mastercard|paypal|bizum)\b"
            r"[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    shopping_list_statement = (
        re.fullmatch(
            r"(?:items?|things?)\s+to\s+get\s+(?:are|include)\s+"
            r"\S.{0,320}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    vague_food_location = (
        re.fullmatch(
            r"(?:(?:alexa|bax[yi])\s+)?(?:donde\s+esta|where\s+is)\s+"
            r"(?:mi|my)\s+(?:comida|food|order|pedido)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    providerless_order_status = (
        re.fullmatch(
            r"(?:how\s+is|what(?:'s|\s+is)\s+the\s+status\s+of|"
            r"como\s+va|cual\s+es\s+el\s+estado\s+de)\s+"
            r"(?:mi|my|the)\s+(?:order|pedido)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    providerless_card_purchase = (
        re.fullmatch(
            r"(?:can|could)\s+i\s+(?:get|buy|order)\s+\S.{0,160}"
            r"\bwith\s+(?:my|a)\s+(?:credit|debit)\s+card\b[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    corrected_unavailable_game = (
        re.fullmatch(
            r"(?:quitar|quita|remove)\b.{0,80}"
            r"\b(?:quiero\s+decir|mejor|i\s+mean|actually)\b.{0,48}"
            r"\b(?:poner|pon|play|launch|open)\b.{0,96}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    first_person_future_game_statement = (
        re.fullmatch(
            r"(?:voy\s+a|i(?:'m|\s+am)\s+going\s+to)\s+"
            r"(?:echar|jugar|play)\b.{0,200}\b(?:partida|game)\b.{0,160}"
            r"[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    application_inventory_list = (
        re.fullmatch(
            r"(?:muestra|mostrar|muestrame|ensena|ensename|ensenarme|lista|"
            r"listame|show|list|ver)\s+"
            r"(?:(?:me|the|las?|todas?|all|ah)\s+)*(?:apps?|aplicaciones?)"
            r"\s+(?:instalad[oa]s?|descargad[oa]s?|installed|downloaded)"
            r"(?:\s+(?:hoy|today))?[\s.!?]*|"
            r"(?:ver|show)\s+(?:(?:las?|the)\s+)?(?:apps?|aplicaciones?)\s+"
            r"(?:instalad[oa]s?|installed)\s*[,;]?\s*"
            r"(?:digo|i\s+mean)\s+(?:descargad[oa]s?|downloaded)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
        # Tanda 4c «show me las aplicaciones»: the applications shown are the open ones (the window inventory);
        # the installed or downloaded ones listed have no operation.
    )
    unsupported_open_game_status = (
        re.fullmatch(
            r"(?:juegos?|games?)\s+(?:abiertos?|open|running|ejecutandose)"
            r"[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    return (
        standalone_speed
        # Uso real tanda 5 «di lo mismo que yo hasta que te avise»: no order verb makes the parrot mode
        # authoritative, and it is still a request with no operation (its known contract keeps it a limit).
        or echo_mode_request(objective)
        or external_console_correction
        or external_console_game_request
        or referential_answer_review
        or nominal_reminder_fragment
        or transactional_purchase_correction
        or corrected_payment_purchase
        or shopping_list_statement
        or vague_food_location
        or providerless_order_status
        or providerless_card_purchase
        or corrected_unavailable_game
        or first_person_future_game_statement
        or application_inventory_list
        or unsupported_open_game_status
    )


def stable_no_effect(
    objective: str,
    history: object = None,
    *,
    pending_clarification: bool | None = None,
) -> tuple[str, str] | None:
    """Close only unambiguous non-effect clauses before tool selection: the conversation kind and the language to
    answer in, or None.

    The model remains responsible for the natural-language reply.  This
    classifier grants no operation authority; it prevents an erroneous leaf
    proposal from turning a clearly conversational turn into a second, slow
    semantic clarification.  The patterns deliberately cover closed syntactic
    envelopes rather than catalog nouns, and pending clarifications always go
    back to the model with their dialogue context.
    """

    explicit_non_action = effect_intent.explicit_non_action_frame(objective)
    if explicit_non_action:
        return "knowledge", read_language(objective)
    marker = "aclaracion confiable del usuario:"
    if marker in effect_intent._fold(objective):
        # Owner's mother 2026-09-21 «buscame un formato de oficio en word» →
        # «¿Quieres que te cree un documento en Word?» → «si» → the same question
        # again. A plain assent to a yes/no clarification re-reads the base
        # request on its own: when it is a stable no-effect turn, that answer
        # closes it here instead of going back to the model for another question.
        base, _, answer = effect_intent._fold(objective).partition(marker)
        if re.fullmatch(r"[\s¿?¡!]*(?:si|sí|dale|ok|okey|claro|obvio|confirmo|yes|yeah|yep|sure|por favor)[\s.!?]*", answer or ""):
            resumed = stable_no_effect(base.strip(), None, pending_clarification=False)
            if resumed is not None:
                return resumed
        return None
    if _history_has_pending_clarification(history, pending_clarification):
        return None
    folded = effect_intent._strip_request_envelope(effect_intent._fold(objective))
    if not folded:
        return None

    assistant_capability_aspiration = _assistant_capability_aspiration(objective)
    standalone_deictic_request = _standalone_deictic_request(objective, history)
    personal_checkin_statement = _personal_checkin_statement(objective)
    closed_unsupported_request = _closed_unsupported_request(objective)

    definition = re.match(
        (
            # Uso real tanda 5 «Me podrias indicar que es el futbol americano y sus reglas para jugar?» (19.3 s,
            # the knowledge reply ran out of the turn after the whole model path): a verb that asks to be told
            # («indicar», «decir», «explicar», «tell me») carries the same definition.
            r"^[¿?¡!\s]*(?:(?:me\s+)?(?:indica|indicame|indicar|indicarme|indicas|dime|decime|decir|decirme|"
            r"dices|explica|explicame|explicar|explicarme|explicas|cuentame|contame|contar|contarme|"
            r"tell\s+me|explain\s+to\s+me)\s+)?"
            r"(?:que\s+es|que\s+son|what\s+(?:is|are|es)|what's|"
            r"para\s+que\s+sirve|explain\s+what)\b"
        ),
        folded,
        re.IGNORECASE,
    ) is not None and not effect_intent._has(
        folded,
        (
            r"\b(?:actual|actualmente|ahora|current|currently|right\s+now|"
            r"volumen|volume|hora|time|fecha|date|estado|status|"
            r"sonando|playing|usando|using)\b"
        ),
    )
    component_description = re.match(
        (
            r"^[¿?¡!\s]*(?:describe(?:\s+about)?|describeme|explain|"
            r"tell\s+me\s+about)\s+"
            r"(?:(?:el|la|un|una|the|a)\s+)?"
            r"(?:(?:computer|pc|ordenador|computador)\s+)?"
            r"(?:disco\s+duro|hard\s+(?:drive|disk)|ssd|hdd|"
            r"procesador|processor|cpu|"
            r"tarjeta\s+grafica|graphics\s+card|gpu|memoria\s+ram|ram)\b"
        ),
        folded,
        re.IGNORECASE,
    ) is not None and not effect_intent._has(
        folded,
        (
            r"\b(?:actual|actualmente|ahora|current|currently|right\s+now|"
            r"estado|status|uso|usage|usando|using|libre|free|capacidad|capacity|"
            r"temperatura|temperature|cuanto|cuanta|how\s+much)\b"
        ),
    )
    geographic_factoid = (
        re.match(
            (
                r"^[Â¿?Â¡!\s]*(?:tell\s+me\s+about|cuentame\s+sobre)\s+"
                r"(?!(?:my|this|the|mi|este|esta)\s+"
                r"(?:computer|pc|device|ordenador|computador|dispositivo)\b)"
                r"[a-z][a-z .'-]{1,80}\s+"
                r"(?:location|geography|ubicacion|geografia)[\s?!.]*$"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    personal_address_request = (
        re.fullmatch(
            (
                r"[¿?¡!\s]*(?:(?:dime|dame)\s+(?:la\s+)?direccion\s+de|"
                r"tell\s+me\s+(?:the\s+)?address\s+of|"
                r"what\s+is\s+(?:the\s+)?address\s+of)\s+"
                r"[a-z][a-z .'-]{1,96}[\s?!.]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    nominal_concept_fragment = (
        re.fullmatch(
            (
                r"[Â¿?Â¡!\s]*(?:encontrar|buscar|find|finding)\s+"
                r"(?:(?:una|a)\s+)?(?:ruta|route)[\s?!.]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    procedure = (
        re.match(
            (
                r"^[¿?¡!\s]*(?:"
                r"como\s+(?:puedo|podria|debo|deberia|hago\s+para|se)\b|"
                r"(?:explica|explicame|explain)\s+(?:como|how)\b|"
                r"how\s+(?:do|can|could|would|should)\s+"
                r"(?:i|we|you)\b|how\s+to\b|explain\s+how\s+to\b"
                r")"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    content_drafting = conversation_only_content_request(objective)
    stable_knowledge_prompt = (
        re.match(
            (
                r"^[¿?¡!\s]*(?:"
                r"(?:define|explica|explicame|explain)\b|"
                r"(?:por\s+que|why)\b|"
                r"(?:(?:que|what)\s+quiere\s+decir)\b|"
                r"what\s+does\b.{0,96}\b(?:mean|significa|decir)\b|"
                # MASSIVE qa_factoid «cuál es la diferencia entre el calendario romano y el gregoriano».
                r"(?:que|cual\s+es\s+la|what(?:\s+is)?(?:\s+the)?|what's(?:\s+the)?)\s+(?:diferencia|difference)\b|"
                r"(?:cuentame|contame|tell\s+me)\b.{0,48}\b(?:historia|history)\b|"
                r"(?:cuentame|contame|tell\s+me)\b.{0,48}\b(?:chiste|joke)\b|"
                r"(?:resume|summarize)\b|"
                r"(?:propon|propone|sugiere|suggest)\b.{0,48}\b(?:nombres?|names?)\b|"
                r"(?:traduce|translate)\b|"
                r"(?:ayudame|help\s+me)\b.{0,64}\b(?:practicar|practice|rehearse)\b"
                r")"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    general_factoid_prompt = _general_factoid_prompt(objective)
    # Uso real 2026-09-23 «who made you», «¿cuál es tu lugar de origen?»: a
    # question about the one answering carries no effect and no public lookup.
    self_question = read_request(objective).has(INTENT_IDENTITY)
    joke_request = (
        re.match(
            (
                r"^[¿?¡!\s]*(?:"
                r"i(?:'d|\s+would)?\s+like\s+to\s+hear|let\s+me\s+hear|"
                r"i\s+(?:want|wanna)\s+(?:to\s+)?hear|(?:quiero|quisiera)\s+(?:oir|escuchar)|"
                r"me\s+gustaria\s+(?:oir|escuchar)|"
                r"(?:find|get|give|tell)\s+me|"
                r"(?:buscame|dame|cuentame|contame))\b.{0,80}"
                r"\b(?:jokes?|chistes?)\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    knowledge_after_negated_effect = (
        re.match(
            (
                r"^(?:no|nunca|jamas|do\s+not|don't|never)\b[^;]{1,160};\s*"
                r"(?:(?:solo|solamente|just|only)\s+)?"
                r"(?:explica|explicame|explain|define|dime\s+que|tell\s+me\s+what|"
                r"what\s+does)\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
        # Explaining after a prohibition cannot cancel a later requested effect.
        # Reuse the clause reader, which splits at independent action heads.
        and len(effect_intent._request_clauses(folded)) == 1
    )
    opinion_prompt = (
        re.match(
            (
                r"^[¿?¡!\s]*(?:what\s+do\s+you\s+think\s+about|"
                r"que\s+opinas\s+de|cual\s+es\s+tu\s+opinion\s+(?:de|sobre))\b"
                r"\s+\S.+$"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    capability_question = (
        re.fullmatch(
            (
                r"[¿?¡!\s]*(?:what\s+(?:can|can\s*t|cannot)\s+you\s+do|"
                r"que\s+(?:puedes|no\s+puedes)\s+hacer|"
                r"cuales\s+son\s+tus\s+capacidades)"
                r"(?:\s+baxy)?[\s?!.]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    # Both detectors below judge a *hypothesis*, and both are anchored to the
    # front of the request. A frame that denies an instruction -- "No assignment
    # for the computer, just answer me: what would happen if ..." -- sits in
    # front of the body and neither `_strip_request_envelope` nor
    # `explicit_non_action_frame` removes it, so the anchor never reaches the
    # hypothesis. Measured on the current tree: 21 of 21 framed surfaces missed
    # across three languages and the seven frames R27 used, against 3 of 3
    # detected bare.
    #
    # The frame also poisons the judgement itself: "This would never be a
    # provision for the PC" contributes its own "would" to the hypothetical
    # test, which is the frame speaking rather than the person.
    #
    # `_strip_explicit_no_action_frame` is the repair R25 already paid for, it
    # is generated from the same cognate groups as the positive instruction
    # frame, and removing a denial can only move a turn toward conversation.
    # It is applied **only here**: the other anchored patterns in this function
    # keep reading the unstripped text on purpose, because `leading_negation`
    # is what closes a denial-framed body that merely quotes an order, and
    # taking that net away would send such a body down to the model.
    hypothesis_folded = effect_intent._strip_explicit_no_action_frame(folded)
    # The strip removing something *is* the recognition: the generated class
    # matched, so the person explicitly denied issuing an instruction. Reading
    # it as its own conversation signal replaces two accidents.
    #
    # `leading_negation` is a short hand-list anchored at the very first token,
    # and it misses a denial that does not open with one of its words: "Ninguna
    # encomienda para el ordenador, contéstame nomás: ..." returned nothing at
    # all before this, and "This would never be a provision for the PC, ..."
    # was held only because the frame's own "would" was being counted as the
    # person's hypothesis -- cover that vanishes the moment that misreading is
    # corrected, as it is two lines below.
    #
    # This is one-sided in the safe direction, unlike stripping the frame for
    # every pattern: it can only close a turn as conversation, never grant an
    # effect. The generated class already requires a negation, an instruction
    # noun and a machine noun before the colon, so an ordinary request cannot
    # trip it.
    explicit_denial_frame = hypothesis_folded != folded
    past_or_hypothetical = effect_intent._is_past_or_hypothetical_state(
        hypothesis_folded
    )
    counterfactual_hypothetical = effect_intent._has(
        hypothesis_folded,
        # Owner's mother 2026-09-21 «Si tuvieras un sueño, cuál te gustaría que
        # fuera», «imagina que tuvieras uno»: the second-person subjunctive is
        # the same counterfactual, a question to answer, not a state to refuse.
        r"^(?:si|if)\b.{0,160}\b(?:tuviera|tuvieras|tuviese|tuvieses|pudiera|pudieras|"
        r"fuera|fueras|quisiera|quisieras|comprara|comprase|compraria|abriria|"
        r"podria|podrias|gustaria|had|bought|would|could|were)\b|"
        r"^(?:que\s+ocurriria\s+si|what\s+(?:would\s+happen|pasaria)\s+"
        r"(?:si|if))\b|"
        r"^(?:pero\s+)?(?:imagina|imaginate|imagine)\b",
    )
    nominal_effect_observation = (
        re.match(
            (
                r"^[Â¿?Â¡!\s]*(?:(?:el\s+)?cierre\s+de\s+.+?\s+"
                r"(?:podia|podria|puede)\s+(?:hacer\s+)?perder\b|"
                r"(?:closing|the\s+closing\s+of)\s+.+?\s+"
                r"(?:could|might|can)\s+(?:cause\s+)?(?:lose|losing)\b)"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    leading_negation = (
        re.match(
            r"^[¿?¡!\s]*(?:no|nunca|jamas|do\s+not|don't|never)\b",
            folded,
            re.IGNORECASE,
        )
        is not None
        # A negative opening cannot cancel a later positive request. Leave
        # compound turns to the normal selector instead of forcing zero effects.
        # A justification after the separator («No cierres Chrome, lo estoy
        # usando», CLOSE1219-1223/010) is still the same prohibition.
        and len(effect_intent._request_clauses(folded)) == 1
        and (
            not any(separator in folded for separator in (",", ";"))
            or re.match(
                # KNOW1835 «No me contestes nada, solo estaba pensando en voz alta.»:
                # a past-tense or «just …» explanation is the same justification.
                r"^\s*(?:(?:solo|just)\s+)?(?:(?:que\s+)?(?:lo|la|los|las|me|te)\s+)?"
                r"(?:estoy|estamos|esta|estan|estaba|estabamos|era|sigo|seguimos|necesito|necesitamos|"
                r"i'?m|i\s+am|i\s+was|we\s+were|it'?s|it\s+was|we'?re|they'?re|porque|because|ya\s+que)\b",
                re.split(r"[,;]", folded, 1)[1],
                re.IGNORECASE,
            )
            is not None
        )
    )
    other_device = effect_intent._has(
        folded,
        (
            r"\b(?:en|on)\s+(?:(?:el|la|un|una|mi)\s+|"
            r"(?:(?:my|the|a)\s+)?(?:[a-z]+(?:'s)?\s+){0,2})?"
            r"(?:telefono|movil|celular|phone|smartphone|tablet|ipad|"
            r"iphone|reloj|watch|consola|console|xbox|playstation)\b"
        ),
    ) and not effect_intent._has(
        folded,
        (
            r"\b(?:bluetooth|conecta|conectar|connect|empareja|"
            r"emparejar|pair|sincroniza|sincronizar|sync)\b"
        ),
    )
    assistant_silence_preference = (
        re.match(
            (
                r"^[¿?¡!\s]*(?:"
                r"no\s+(?:(?:me\s+)?hables|digas\s+nada|respondas)\s+"
                r"(?:hasta\s+que|a\s+menos\s+que)|"
                r"(?:do\s+not|don't)\s+(?:speak|talk|say\s+anything|respond)\s+"
                r"(?:until|unless)"
                r")\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    assistant_command_history_request = (
        re.match(
            (
                r"^[¿?¡!\s]*(?:"
                r"(?:puedes\s+)?(?:mostrarme|muestrame|dime|lista)\b.{0,80}"
                r"\b(?:mis|tus)\s+(?:comandos|ordenes)\s+"
                r"(?:recientes|anteriores|historial)\b|"
                r"(?:can\s+you\s+)?(?:show|tell|list)\b.{0,80}"
                r"\b(?:my|your)\s+(?:recent\s+)?commands?\b"
                r")"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    current_public_role_question = _current_public_role_question(objective)
    underspecified_video_request = effect_intent._underspecified_video_request(folded)
    interactive_play = effect_intent._has(
        folded,
        (
            r"\bplay\b.{0,80}\b(?:with|against)\s+"
            r"(?:me|us|(?!(?:the|a|an|my|computer|cpu|machine|bot)\b)"
            r"[a-z][a-z.'-]{1,40})\b|"
            r"\b(?:juega|jugar|juguemos)\b.{0,80}"
            r"\b(?:conmigo|con nosotros|contra mi|contra nosotros|"
            r"(?:con|contra)\s+(?!(?:el|la|un|una|mi|computador|computadora|"
            r"pc|maquina|bot)\b)[a-z][a-z.'-]{1,40})\b"
        ),
    )
    acknowledged_hearing = (
        re.fullmatch(
            (
                r"[¿?¡!\s]*(?:(?:si\s*[,;:]?\s*){1,2}"
                r"(?:ya\s+)?(?:te\s+)?(?:oigo|escucho)|"
                r"(?:yeah\s*[,;:]?\s*){1,2}i\s+hear\s+you)"
                r"[\s?!.]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if not (
        assistant_capability_aspiration
        or standalone_deictic_request
        or personal_checkin_statement
        or closed_unsupported_request
        or definition
        or component_description
        or geographic_factoid
        or personal_address_request
        or nominal_concept_fragment
        or procedure
        or content_drafting
        or stable_knowledge_prompt
        or general_factoid_prompt
        or self_question
        or joke_request
        or knowledge_after_negated_effect
        or opinion_prompt
        or capability_question
        or past_or_hypothetical
        or counterfactual_hypothetical
        or explicit_denial_frame
        or nominal_effect_observation
        or leading_negation
        or other_device
        or assistant_silence_preference
        or assistant_command_history_request
        or current_public_role_question
        or underspecified_video_request
        or interactive_play
        or acknowledged_hearing
    ):
        return None
    return (
        (
            "social"
            if acknowledged_hearing or personal_checkin_statement
            else "unsupported"
            if personal_address_request or closed_unsupported_request
            else "knowledge"
            if (
                definition
                or component_description
                or geographic_factoid
                or nominal_concept_fragment
                or procedure
                or content_drafting
                or stable_knowledge_prompt
                or general_factoid_prompt
                or self_question
                or joke_request
                or knowledge_after_negated_effect
                or opinion_prompt
                or capability_question
                or counterfactual_hypothetical
                or (leading_negation and not assistant_silence_preference)
                # A denial of instruction asks to be talked to, not refused.
                # "unsupported" would answer an answerable question with an
                # inability, which is the visible defect R125 measured.
                or explicit_denial_frame
            )
            else "followup"
            if (
                nominal_effect_observation
                or assistant_silence_preference
                or underspecified_video_request
                or standalone_deictic_request
            )
            else "unsupported"
        ),
        (
            "en"
            if acknowledged_hearing and re.search(r"\bi\s+hear\s+you\b", folded)
            else read_language(objective)
        ),
    )


_COMMON_BARE_APPLICATION_REQUESTS = frozenset(
    {
        "booking",
        "discord",
        "facebook",
        "instagram",
        "snapchat",
        "telegram",
        "tiktok",
        "whatsapp",
    }
)


def catalog_unavailable(
    objective: str,
    explicit_intent: EffectIntent | None,
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
    game_catalog: GameCatalogIndex,
) -> bool:
    """A literal app/game request that lacks an authenticated identity: BAXY states the limit."""

    if explicit_intent is not None or _deictic_open_request(objective):
        return False
    folded = effect_intent._strip_request_envelope(effect_intent._fold(objective))
    if not folded:
        return False
    bare_application = effect_intent._application_name_key(folded.rstrip(" ?!."))
    application_keys = build_application_catalog_index(application_names).keys
    requested_common_applications = tuple(
        name
        for name in _COMMON_BARE_APPLICATION_REQUESTS
        if re.search(rf"\b{re.escape(name)}\b", folded)
    )
    application_request = (
        re.match(
            r"^(?:take\s+me\s+to|go\s+to|get\s+.+?\s+started|open|abre|abrir|"
            r"inicia|iniciar|lanza|launch|ouverture)\b",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    unavailable_application = (
        bare_application in _COMMON_BARE_APPLICATION_REQUESTS
        and bare_application not in application_keys
    ) or (
        application_request
        and len(requested_common_applications) == 1
        and requested_common_applications[0] not in application_keys
    )
    game_request = (
        re.match(
            (
                r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
                r"(?:(?:(?:vamos\s+a|let(?:'s|\s+us))\s+(?:start\s+)?"
                r"(?:juega|jugar|juguemos|play|playing))|"
                r"(?:juega|jugar|juguemos|play|start\s+up)|"
                r"(?:abre|abrir|open|lanza|launch|ejecuta|run))\b\s+"
                r"(?:(?:al|el|the)\s+)?(?:(?:juego|game)\s+)?\S.+$"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
        or re.fullmatch(
            r"get\s+\S.{0,160}\s+started[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    unavailable_game = (
        game_request
        and effect_intent._authenticated_game_target(folded, game_catalog) is None
    )
    return bool(unavailable_application or unavailable_game)


def first_person_observation(folded: str) -> bool:
    """The person reports what they are, have, see or notice («estoy…», «me aparece…», «i see…»): a statement,
    not a request (the non-effect relabelling of ``__main__``)."""

    return (
        re.search(
            (
                r"\b(?:estoy|estaba|estuve|tengo|tenia|veo|noto|observo|"
                r"me aparece|me salio|dejo de|"
                r"i am|i m|i was|i have|i ve|i did|i see|i notice|"
                r"i observe|stopped)\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )


def names_a_question_word(folded: str) -> bool:
    """A question word or «explain» anywhere in the message: talk about it is knowledge."""

    return (
        re.search(
            r"\b(?:que|cual|cuanto|como|por que|what|which|how|why|explain|explica)\b",
            folded,
        )
        is not None
    )


# Uso real tanda 5 2026-09-24 «¿puedes reproducir mis últimas palabras?» played media and then asked which
# words: saying back the previous message, the person's or BAXY's own, is conversation over the dialogue. The
# whole message is the literal. Only what was already said is recalled («lo que dije», never «lo que diga»,
# which is the echo mode BAXY does not keep) and only as the whole ask, so «qué dije sobre la reunión» or
# «repite la última canción» keep their own readers.
_RECALL_FRAME = (
    r"^(?:(?:oye|hey|baxy|a\s+ver|bueno|ok|okay|por\s+favor|porfa|please)\s+)*"
    r"(?:(?:me\s+)?(?:puedes|podes|podrias|podria|can\s+you|could\s+you|would\s+you)\s+(?:please\s+)?)?"
)


_RECALL_TAIL = r"(?:\s+(?:otra\s+vez|de\s+nuevo|again|back|por\s+favor|porfa|please|baxy))*$"


_RECALL_SAY = (
    r"(?:me\s+)?(?:repite|repiteme|repeti|repetime|repetir|repetirme|repites|reproduce|reproduceme|reproduci|reproducir|di|dime|"
    r"deci|decime|decir|decirme|lee|leeme|leer|leerme|recuerdame|recordame|recordarme|"
    r"repeat|say|tell\s+me|read|read\s+me)\s+(?:(?:back|again|otra\s+vez|de\s+nuevo)\s+)?"
)


_RECALL_WHEN = r"(?:\s+(?:antes|recien|hace\s+un\s+(?:momento|rato|ratito)|just\s+now|before|earlier|a\s+moment\s+ago))?"


_PERSON_RECALL = re.compile(
    _RECALL_FRAME
    + r"(?:"
    + _RECALL_SAY
    # Tanda 7b «por favor, ¿puedes repetir lo mismo que te he dicho?» was answered «¿en qué puedo ayudarte?»:
    # «lo mismo que» and the perfect («te he dicho», «te había dicho») say what was already said too.
    + r"(?:lo\s+(?:ultimo\s+|mismo\s+)?que\s+(?:yo\s+)?(?:te\s+)?(?:acabo\s+de\s+|he\s+|habia\s+)?"
    r"(?:dije|escribi|puse|pregunte|pedi|decir|escribir|preguntar|pedir|dicho|escrito|puesto|preguntado|pedido)"
    + _RECALL_WHEN
    + r"|mis\s+ultimas\s+palabras|mi\s+ultim[oa]\s+(?:mensaje|frase|pregunta|pedido)|"
    r"mi\s+(?:mensaje|frase|pregunta|pedido)\s+anterior|"
    r"(?:what\s+|the\s+same\s+(?:thing\s+)?(?:that\s+|what\s+)?)i\s+(?:just\s+|have\s+|ve\s+)?(?:said|wrote|written|"
    r"typed|asked(?:\s+you)?)"
    + _RECALL_WHEN
    + r"|my\s+(?:last|previous)\s+(?:message|words|sentence|question|request))|"
    r"que\s+(?:fue\s+lo\s+(?:ultimo\s+)?que\s+)?(?:te\s+)?(?:dije|escribi|pregunte|pedi|acabo\s+de\s+"
    r"(?:decir|escribir|preguntar|pedir))"
    + _RECALL_WHEN
    + r"|cual(?:es)?\s+(?:fue|fueron|era|eran)\s+(?:mis\s+ultimas\s+palabras|mi\s+ultim[oa]\s+"
    r"(?:mensaje|frase|pregunta)|lo\s+(?:ultimo\s+)?que\s+(?:te\s+)?dije)|"
    r"what\s+did\s+i\s+(?:just\s+)?(?:say|write|type|ask(?:\s+you)?)"
    + _RECALL_WHEN
    + r"|what\s+(?:was|were)\s+my\s+(?:last|previous)\s+(?:message|words|sentence|question|request)"
    r")"
    + _RECALL_TAIL
)


_ASSISTANT_RECALL = re.compile(
    _RECALL_FRAME
    + r"(?:"
    + _RECALL_SAY
    + r"(?:lo\s+(?:ultimo\s+|mismo\s+)?que\s+(?:me\s+)?(?:dijiste|respondiste|contestaste|escribiste|acabas\s+de\s+"
    r"(?:decir|responder|contestar|escribir)|has\s+(?:dicho|respondido|contestado|escrito))"
    + _RECALL_WHEN
    + r"|tu\s+ultim[oa]\s+(?:respuesta|mensaje|frase)|tu\s+(?:respuesta|mensaje)\s+anterior|tus\s+ultimas\s+palabras|"
    r"what\s+you\s+(?:just\s+)?(?:said|answered|replied|wrote)"
    + _RECALL_WHEN
    + r"|your\s+(?:last|previous)\s+(?:answer|message|reply|words))|"
    r"que\s+(?:fue\s+lo\s+(?:ultimo\s+)?que\s+)?(?:me\s+)?(?:dijiste|respondiste|contestaste|acabas\s+de\s+"
    r"(?:decir|responder|contestar))"
    + _RECALL_WHEN
    + r"|what\s+did\s+you\s+(?:just\s+)?(?:say|answer|reply|write)"
    + _RECALL_WHEN
    + r"|what\s+(?:was|were)\s+your\s+(?:last|previous)\s+(?:answer|message|reply|words)"
    r")"
    + _RECALL_TAIL
)


def _recalled_speaker(current: object) -> str | None:
    """Whose whole previous message the current one asks to be said back: "user", "assistant" or None."""

    folded = _policy_guard_text(current)
    if _PERSON_RECALL.match(folded) is not None:
        return "user"
    if _ASSISTANT_RECALL.match(folded) is not None:
        return "assistant"
    return None


# Uso real tanda 5 2026-09-24 «roll that dice, ai» was searched on the web (a CapCut dice page). A die, a coin
# or a number within a range is drawn here, for real, by the mind; the drawn value reaches the narrator as the
# one literal of its sentence, so the model never picks the number itself.
@dataclass(frozen=True)
class RandomDraw:
    """What was asked to be drawn: dice («die»), a coin («coin») or a number in [low, high] («number»)."""

    kind: str
    count: int = 1
    low: int = 1
    high: int = 6
    faces: tuple[str, ...] = ()


_DRAW_COUNTS = {
    "un": 1, "una": 1, "uno": 1, "a": 1, "an": 1, "one": 1, "dos": 2, "two": 2, "tres": 3, "three": 3,
    "cuatro": 4, "four": 4, "cinco": 5, "five": 5, "seis": 6, "six": 6,
}


_DRAW_FRAME = (
    r"^(?:(?:oye|hey|baxy|ok|okay|bueno|vale|dale|a\s+ver|por\s+favor|porfa|please|pls)\s+)*"
    r"(?:(?:me\s+)?(?:puedes|podes|podrias|can\s+you|could\s+you|would\s+you)\s+(?:please\s+)?|"
    r"(?:quiero\s+que|necesito\s+que|i\s+want\s+you\s+to|i\s+need\s+you\s+to)\s+)?"
)


_DRAW_TAIL = (
    r"(?:\s+(?:por\s+favor|porfa|please|pls|ai|ia|bot|baxy|amigo|bro|para\s+mi|for\s+me|ahora|now|"
    r"otra\s+vez|de\s+nuevo|again|ya))*$"
)


_DRAW_COUNT = r"(?:\d{1,2}|un|una|uno|a|an|one|dos|two|tres|three|cuatro|four|cinco|five|seis|six)"


_DIE_DRAW = re.compile(
    _DRAW_FRAME
    + r"(?:(?:tira|tirame|tiras|tirar|tirarme|tire|lanza|lanzame|lanzas|lanzar|lanzarme|lance|echa|echame|echar|"
    r"arroja|arrojame|arrojar|avienta|aventar|roll|throw|toss)\s+(?:(?P<count>" + _DRAW_COUNT + r")|"
    r"el|los|la|las|the|that|this|those|these|some|unos|unas|my|mi|mis)?\s*"
    r"(?:(?:dados?|dice|die)(?:\s+de\s+(?P<sides>\d{1,3})\s+caras|\s+with\s+(?P<sides_en>\d{1,3})\s+sides)?|"
    r"d(?P<sides_short>\d{1,3}))|"
    r"(?:haz|hace|haceme|hazme|do|make)\s+(?:una|a)\s+(?:tirada|roll)(?:\s+de\s+dados?|\s+of\s+(?:the\s+)?dice)?)"
    + _DRAW_TAIL
)


_COIN_DRAW = re.compile(
    _DRAW_FRAME
    + r"(?:(?:tira|tirame|lanza|lanzame|echa|echame|arroja|flip|toss|throw)\s+(?:una|la|a|the)\s+(?:moneda|coin)"
    r"(?:\s+al\s+aire)?(?:\s+(?P<face_a>cara|heads)\s+o\s+(?P<face_b>cruz|sello|tails))?|"
    r"(?P<pair>cara\s+o\s+(?:cruz|sello)|aguila\s+o\s+sol|heads\s+or\s+tails))"
    + _DRAW_TAIL
)


_NUMBER_DRAW = re.compile(
    _DRAW_FRAME
    + r"(?:dame|dime|decime|elige|elegi|escoge|escogi|saca|genera|piensa\s+en|pick|give\s+me|choose|generate|"
    r"tell\s+me|think\s+of)\s+(?:un|a)\s+(?:random\s+)?(?:numero|number)(?:\s+(?:al\s+azar|aleatorio|cualquiera|"
    r"at\s+random))?\s+(?:del|entre|de|between|from)\s+(?P<low>\d{1,6})\s+(?:al|y|a|hasta|and|to)\s+"
    r"(?P<high>\d{1,6})"
    + _DRAW_TAIL
)


def random_draw_request(text: object) -> RandomDraw | None:
    """The die, coin or number within a range the whole message asks to be drawn, or None."""

    folded = _policy_guard_text(text)
    found = _DIE_DRAW.match(folded)
    if found is not None:
        count_word = found.group("count") or "1"
        count = int(count_word) if count_word.isdigit() else _DRAW_COUNTS[count_word]
        sides = int(found.group("sides") or found.group("sides_en") or found.group("sides_short") or 6)
        if not 1 <= count <= 10 or not 2 <= sides <= 1000:
            return None
        return RandomDraw("die", count=count, high=sides)
    found = _COIN_DRAW.match(folded)
    if found is not None:
        named = found.group("pair") or (
            f"{found.group('face_a')} o {found.group('face_b')}" if found.group("face_a") else ""
        )
        faces = tuple(re.split(r"\s+(?:o|or)\s+", named)) if named else ()
        return RandomDraw("coin", high=2, faces=faces)
    found = _NUMBER_DRAW.match(folded)
    if found is not None:
        low, high = int(found.group("low")), int(found.group("high"))
        return RandomDraw("number", low=low, high=high) if low < high else None
    return None


# Tanda 4c 2026-09-24 «oye compárteme algún chiste para hacerme feliz», «i'd like you to tell me a joke» were
# answered «¿Quieres un chiste de amor, de trabajo o de general?»: a request for a bit of content is complete
# whatever frame carries it. The frame (an address, a courtesy, being able to, wanting it) carries the request;
# the verb gives or tells it; the thing is named with at most a quality, a topic or a purpose after it.
_FREE_CONTENT_FRAME = (
    r"(?:(?:oye|oiga|hey|ey|mira|che|baxy|bueno|ok|okay|vale|dale|please|pls|por\s+favor|porfa)\s+|"
    r"(?:i\s+d|i\s+would|id)\s+(?:like|love)\s+(?:you\s+to\s+|to\s+(?:hear|read)\s+)?|"
    r"i\s+(?:want|need)\s+(?:you\s+to\s+)?|"
    r"(?:can|could|would|will)\s+you\s+(?:please\s+)?|"
    r"(?:me\s+|nos\s+)?(?:puedes|podes|podrias|podria|puede|pueden)\s+|"
    r"(?:quiero|quisiera|necesito|me\s+gustaria|me\s+encantaria|te\s+pido)\s+(?:que\s+)?|"
    # «Actúa como Julio Verne y haz un relato…»: the voice to write it in.
    r"(?:actua|act|habla|talk|speak|finge\s+ser|pretend\s+(?:to\s+be|you\s+are)|como\s+si\s+fueras)\s+"
    r"(?:(?:como|like|as)\s+)?[a-z0-9]+(?:\s+[a-z0-9]+){0,3}\s+(?:y|e|and)\s+)*"
)


_FREE_CONTENT_VERB = (
    r"(?:(?:me|nos|te)\s+)?"
    r"(?:cuentame|contame|cuenta|conta|cuentas|cuentes|cuente|decime|dime|di|dices|digas|diga|"
    r"dame|da|das|des|tirame|tira|tiras|tires|echame|echa|echas|eches|sueltame|suelta|sueltas|sueltes|"
    r"comparteme|compartime|comparte|compartes|compartas|regalame|regala|regalas|hazme|haceme|haz|haces|hagas|"
    r"inventame|inventate|inventa|inventas|inventes|recitame|recita|narrame|narra|explicame|explica|hablame|habla|"
    r"(?:contar|decir|dar|tirar|echar|soltar|compartir|regalar|hacer|inventar|recitar|narrar|explicar|hablar)"
    r"(?:me|nos)?|"
    r"(?:te\s+)?sabes|conoces|tienes|tenes|quiero|quisiera|necesito|oir|escuchar|leer|"
    r"tell|give|say|share|crack|throw|recite|know|have|got|hear|read|do\s+you\s+(?:know|have)|you\s+got|"
    r"i\s+(?:want|need)|(?:i\s+d|i\s+would|id)\s+(?:like|love)|hit\s+(?:me|us)\s+with|make\s+up|come\s+up\s+with)"
    r"(?:\s+(?:me|us|nos|to\s+me|with\s+me))?\s+"
)


_FREE_CONTENT_QUALITY = (
    r"(?:buen|bueno|buena|buenos|buenas|corto|corta|cortos|cortas|pequeno|pequena|breve|nuevo|nueva|gracioso|graciosa|"
    r"divertido|divertida|interesante|curioso|curiosa|malo|mala|original|random|aleatorio|"
    r"short|quick|good|funny|silly|bad|cheesy|dad|clean|new|little|interesting|curious|fun)"
)


_FREE_CONTENT_THING = (
    r"(?:chistes?|bromas?|chascarrillos?|jokes?|puns?|juegos?\s+de\s+palabras|adivinanzas?|acertijos?|riddles?|"
    r"trabalenguas|tongue\s+twisters?|curiosidad(?:es)?|datos?\s+curiosos?|(?:fun|random|interesting|cool)\s+facts?|"
    r"piropos?|pick\s*up\s+lines?|cuentos?|relatos?|historias?|stor(?:y|ies)|poemas?|poems?|poesias?|haikus?)"
)


_FREE_CONTENT_COURTESY = r"(?:\s+(?:please|pls|porfa|por\s+favor|baxy|ahora|now|anda|va|ya))*"


# A quality and nothing else after the thing; a verb in front also allows its topic («de programadores», «about
# cats») or its purpose («para hacerme feliz», «to cheer me up»).
_FREE_CONTENT_SHORT_TAIL = rf"(?:\s+{_FREE_CONTENT_QUALITY})?{_FREE_CONTENT_COURTESY}$"


_FREE_CONTENT_LONG_TAIL = (
    rf"(?:\s+{_FREE_CONTENT_QUALITY})?"
    r"(?:\s+(?:de|del|sobre|acerca\s+de|about|on|of|with|con|para|pa|to|so|que|that|basad[oa]\s+en|based\s+on)"
    r"(?:\s+[a-z0-9]+){1,10})?" + _FREE_CONTENT_COURTESY + r"$"
)


_FREE_CONTENT_AMOUNT = (
    r"(?:(?:un|una|unos|unas|algun|alguna|algunos|algunas|algo\s+de|otro|otra|otros|otras|un\s+par\s+de|dos|tres|"
    r"mas|tu\s+mejor|a|an|one|some|any|another|a\s+couple\s+of|two|three|more|your\s+best)\s+)?"
)


# Tanda 6 «haz una carcajada cuando quieras» → an answer dragging two earlier turns; «ríete diabólicamente» → «te río
# de verdad 😈»: a laugh asked for is a bit of content performed on the spot («¡Muajajaja!»), with its manner or
# its moment after it. The imperative «ríete» asks for it too; «no te rías» or «¿de qué te ríes?» do not start so.
_LAUGHTER_ASK = (
    r"(?:(?:(?:haz|hazme|haceme|hace|suelta|sueltame|echa|echate|echame|dame|tira|tirate|give\s+me|give|do|let\s+out)\s+)"
    r"(?:(?:un|una|otra|otro|tu\s+mejor|a|an|another|your\s+best)\s+)?(?:[a-z]+\s+)?"
    r"(?:carcajadas?|risas?|risotadas?|laughs?|laughters?|cackles?)|"
    r"(?:riete|reite|rie|reirte|reir|laugh|cackle)(?:\s+(?:for|at)\s+me)?)"
    r"(?:\s+[a-z]+){0,4}[\s.!]*$"
)


_LAUGHTER_ASKED = re.compile(r"^" + _FREE_CONTENT_FRAME + _LAUGHTER_ASK)


# tanda-02: a bare plural noun asking for jokes was answered with a question about the topic. The thing named on
# its own —a joke, a curiosity, with or without earlier turns— is asked for, not a question about which one; with a
# verb in front it may bring its topic or its purpose.
_FREE_CONTENT_THING_CUE = re.compile(
    r"^" + _FREE_CONTENT_FRAME + r"(?:"
    + _FREE_CONTENT_VERB + _FREE_CONTENT_AMOUNT + rf"(?:{_FREE_CONTENT_QUALITY}\s+)?" + _FREE_CONTENT_THING
    + _FREE_CONTENT_LONG_TAIL
    + r"|(?:hazme|haceme|make\s+me)\s+(?:reir|sonreir|laugh|smile)" + _FREE_CONTENT_LONG_TAIL
    + r"|" + _FREE_CONTENT_AMOUNT + rf"(?:{_FREE_CONTENT_QUALITY}\s+)?" + _FREE_CONTENT_THING + _FREE_CONTENT_SHORT_TAIL
    + r"|" + _LAUGHTER_ASK
    + r")"
)


# «contame algo», «estoy aburrido»: open content, read so only with no earlier
# turn that «algo» could be about.
_FREE_CONTENT_CUE = re.compile(
    r"^(?:" + _FREE_CONTENT_FRAME
    + r"(?:contame|cuentame|conta|cuenta|decime|dime|tirame|tira|explicame|explica|hablame|habla|comparteme|comparte|"
    r"tell\s+me|give\s+me|say|share)\s+"
    + r"(?:algo|something|anything|cualquier\s+cosa|una\s+cosa)" + _FREE_CONTENT_SHORT_TAIL
    + r"|(?:estoy|ando|me\s+siento)\s+(?:re\s+|muy\s+|super\s+)?aburrid[oa][\s.!?]*$|^i\s?m\s+(?:so\s+)?bored[\s.!?]*$)"
)


_MISNAMED_VOCATIVE = re.compile(r"^[A-ZÁÉÍÓÚÑ][A-Za-zÁ-ÿ'-]{1,24}[.!]?$")


_REASSURANCE_OPENING = re.compile(
    r"^(?:(?:no|nunca)\s+(?:te|se)\s+preocup\w*|tranqui(?:lo|la|los|las)?\b|no\s+pasa\s+nada|"
    r"(?:don'?\s?t|dont|do\s+not)\s+worry|no\s+worries|it'?\s?s\s+(?:ok|okay|fine|alright)|esta\s+bien\s+si\b|todo\s+bien\s+si\b)"
)


# KNOWLEDGE1527 H0030 «¿Quieres el acompañante de Batman?»: an offer to BAXY.
_ASSISTANT_DESIRE_QUESTION = re.compile(
    r"^[\s¿?¡!]*(?:quieres|queres|quiere|te\s+gustaria|le\s+gustaria|do\s+you\s+want|would\s+you\s+like)\s+"
    r"(?!que\b|abrir|poner|buscar|cerrar|to\b)"
    r"(?P<thing>(?:el|la|los|las|un|una|unos|unas|a|an|some|the)\s+[a-z][a-z0-9 .'-]{1,60}?)[\s?!.]*$"
)


def assistant_desire_thing(text: str) -> str | None:
    """The thing a person offered BAXY («¿Quieres el acompañante de Batman?»), or None."""

    found = _ASSISTANT_DESIRE_QUESTION.match(_policy_guard_text(_strip_request_envelope(text)))
    if found is None:
        return None
    thing = found.group("thing").strip()
    if re.search(r"\b(?:que|abra|abras|ponga|pongas|busque|busques|cierre|cierres|haga|hagas|volumen|brillo)\b", thing):
        return None
    return thing


# KNOWLEDGE1525 H0582 «Quien gana en batman vs superman»: two contenders.
_VERSUS_QUESTION = re.compile(
    r"^[\s¿?¡!]*(?:quien|who)\s+(?:gana|ganaria|vence|venceria|would\s+win|wins|win)\s+"
    r"(?:(?:en\s+una\s+pelea|en\s+un\s+combate|in\s+a\s+fight)\s+)?(?:entre|en|between|in)\s+"
    r"(?P<first>[a-z0-9][a-z0-9 .'-]{0,38}?)\s+(?:vs\.?|versus|contra|y|and|o|or)\s+"
    r"(?P<second>[a-z0-9][a-z0-9 .'-]{0,38}?)[\s?!.]*$"
)


# KNOWLEDGE1525 H0596 «El agua moja?, responde con sarcasmo»: a sarcastic tone was asked for.
_SARCASM_REQUEST = re.compile(
    r"^(?P<question>.+?)[\s,;:.!?]*(?:(?:y\s+)?(?:responde|respondeme|respondelo|contesta|contestame|contestalo|answer|reply)"
    r"(?:\s+(?:me|lo|la|it))?\s+(?:con\s+sarcasmo|sarcasticamente|sarcastically|with\s+sarcasm))[\s.!?]*$"
)


def versus_contenders(text: str) -> tuple[str, str] | None:
    """The two contenders of a who-wins question, or None."""

    found = _VERSUS_QUESTION.match(_policy_guard_text(_strip_request_envelope(text)))
    if found is None:
        return None
    return found.group("first").strip(), found.group("second").strip()


def sarcasm_question(text: str) -> str | None:
    """The question a sarcastic answer was asked for, or None."""

    found = _SARCASM_REQUEST.match(_policy_guard_text(_strip_request_envelope(text)))
    if found is None:
        return None
    question = found.group("question").strip(" ,;:.!?¿¡")
    return question or None


# Tanda 4 2026-09-24 «spell potato» → «Potato.»: spelling a word is saying its letters one by one. Read on the
# casefolded words as written, so the word keeps its accents («deletrea camión»).
_SPELLING_REQUEST = re.compile(
    r"^[\s¿?¡!]*(?:(?:hola|oye|hey|baxy|por\s+favor|porfa|please)[\s,:;.!]+)*"
    r"(?:(?:can|could|would)\s+you\s+(?:please\s+)?|(?:me\s+)?(?:puedes|podés|podes|podrías|podrias)\s+)?"
    r"(?:spell(?:\s+out)?|(?:me\s+)?deletr[eé](?:a|á|as|ás|ame|ar(?:me)?)|"
    r"how\s+(?:do\s+you|do\s+i|would\s+you|to|is|are)\s+(?:you\s+)?spell(?:ed)?|"
    r"c[oó]mo\s+se\s+deletrea|c[oó]mo\s+(?:deletreo|deletreas|deletrear)|"
    r"what(?:\s+is|['’]s)\s+the\s+spelling\s+of|"
    r"(?:c[oó]mo\s+se\s+escribe|escr[ií]b(?:e|eme|ime|i)|write)(?=.*\b(?:letra\s+por\s+letra|letter\s+by\s+letter)\b))"
    r"\s+(?:(?:the\s+word|the\s+name|la\s+palabra|el\s+nombre|el\s+apellido)\s+)?[\"'«“‘]?"
    r"(?P<word>[^\W\d_][^\W\d_'’-]{0,39})[\"'»”’]?"
    r"(?:\s+(?:for\s+me|por\s+favor|please|porfa|letra\s+por\s+letra|letter\s+by\s+letter|en\s+ingl[eé]s|"
    r"en\s+espa[nñ]ol|in\s+english|in\s+spanish))*[\s.?!]*$"
)


_SPELLED_QUESTION = re.compile(
    r"^[\s¿?¡!]*how\s+(?:is|are)\s+(?:the\s+word\s+)?[\"'«“‘]?(?P<word>[^\W\d_][^\W\d_'’-]{0,39})[\"'»”’]?"
    r"\s+spelled[\s.?!]*$"
)


_NOT_A_SPELLED_WORD = frozenset(
    "it that this eso esto esa ese aquello me you te lo la something algo anything nada".split()
)


def spelling_word(text: str) -> str | None:
    """The word a person asked to have spelled («spell potato» → «potato»), or None."""

    said = str(text or "").strip().casefold()
    found = _SPELLING_REQUEST.match(said) or _SPELLED_QUESTION.match(said)
    if found is None or found.group("word") in _NOT_A_SPELLED_WORD:
        return None
    return found.group("word")


_HOW_IT_WORKS_CUE = re.compile(
    r"^[\s¿?¡!]*(?:y\s+)?(?:como\s+funciona(?:s|n)?(?:\s+(?:esto|eso|baxy|este\s+asistente|todo\s+esto|el\s+asistente))?|"
    r"how\s+(?:does|do)\s+(?:this|it|you|baxy)\s+work)[\s.?!]*$"
)


# Tanda 4c 2026-09-24 «a partir de ahora imítame» → «Claro, ya estoy en el mismo estilo… ¿Qué necesitas ahora?»:
# how BAXY talks or behaves from now on, imitating the person included, is a directive on his conduct like the
# language he speaks; it is acknowledged, not followed by a question.
_CONDUCT_DIRECTIVE = re.compile(
    r"^(?:(?:por\s+favor|porfa|please|baxy|oye|hey|ok|okay|bueno|vale)\s+)*(?:"
    r"(?:a\s+partir\s+de\s+(?:ahora|hoy|ya)|desde\s+(?:ahora|hoy|ya)(?:\s+en\s+adelante)?|de\s+ahora\s+en\s+adelante|"
    r"en\s+adelante|from\s+now\s+on|starting\s+(?:now|today)|for\s+the\s+rest\s+of\s+(?:the|this|our)\s+"
    r"(?:chat|conversation))\s+(?:(?:quiero\s+que|i\s+want\s+you\s+to|please|por\s+favor)\s+)?"
    r"(?:imita|imitame|imitar|imites|copia|copiame|copies|habla|hablame|hablar|hables|responde|respondeme|respondas|"
    r"contesta|contestame|contestes|tutea|tuteame|trata|tratame|trates|actua|actues|seas|usa|uses|"
    # «sé más breve»: without its accent «se» is also the pronoun («se me olvida»), so a quality follows it.
    r"se\s+(?:mas|menos|muy)?\s*(?:breve|directo|directa|formal|informal|amable|conciso|concisa|claro|clara|"
    r"gracioso|graciosa|serio|seria|sincero|sincera)|"
    r"imitate|copy|mimic|talk|speak|answer|reply|respond|act|be|use)\b.{0,80}"
    r"|(?:imitame|copiame|imitate\s+me|copy\s+me|mimic\s+me)(?:\s+.{0,60})?"
    r")$"
)


# Owner 2026-09-24 («conciso… de una»): a plain answer is one or two sentences,
# so its budget is sized to that; a request that asks for more (detail, steps,
# a list, a story) keeps room for the content it asked for.
_EXTENDED_ANSWER_ASK = re.compile(
    r"\b(?:en\s+detalle|detallad\w*|a\s+fondo|profundi\w*|paso\s+a\s+paso|pasos|reglas|listas?|enumer\w*|"
    r"ejemplos|todo\s+(?:sobre|lo\s+que)|relato|cuento|historia|poema|ensayo|carta|resum\w*|"
    r"in\s+detail|detailed|step\s+by\s+step|steps|rules|lists?|listing|examples|everything\s+about|"
    r"story|poem|essay|letter|summar\w*|elaborat\w*)\b"
)


def _conversation_presentation_shape(
    text: str,
    *,
    conversation_kind: str | None,
    has_history: bool,
) -> str | None:
    """Close a few no-history prose contracts without changing turn authority."""

    semantic_text = explicit_non_action_body(text) or text
    # cien-40 007/028: «traduce 'good evening' al español» recibía la forma de
    # redacción de contenido, no la de traducción, así que el prompt del
    # traductor —devolver la traducción y nada más— no llegaba nunca a los
    # pedidos más corrientes. Un pedido de traducción es una traducción.
    # cien-43 038 «no lances Steam» y luego «if it didn't happen, say so»: la
    # pregunta por si ocurrio o no llegaba sin forma ninguna y el modelo devolvia
    # la condicion como tautologia. Es el mismo reconocimiento de la restriccion,
    # que ya tiene su prompt y su contrato.
    if has_history and _NON_EVENT_CONFIRMATION.search(
        _policy_guard_text(_strip_request_envelope(semantic_text)),
    ):
        return "constraint_ack"
    if re.match(
        r"^[\s¿?¡!]*(?:traduc(?:e|i|ime|eme|ir|elo|ela|ela)|translate)\b",
        _policy_guard_text(_strip_request_envelope(semantic_text)),
    ):
        return "translation"
    if spelling_word(semantic_text) is not None:
        return "spelling"
    if spoken_number_request(semantic_text) is not None:
        return "spoken_number"
    # Uso real 2026-09-23 «vuelve a hablar en español» → «Claro, estoy aquí para
    # ayudarte en español 😎 ¿En qué puedo ayudarte hoy?»: how BAXY should speak
    # is a directive on his conduct, acknowledged in one sentence like any other.
    # Uso real tanda 5: a parrot mode («a partir de ahora imita lo que digo») is a limit, never acknowledged.
    if not echo_mode_request(semantic_text) and (
        speaking_directive(semantic_text)
        or _CONDUCT_DIRECTIVE.match(_policy_guard_text(_strip_request_envelope(semantic_text)))
    ):
        return "constraint_ack"
    if conversation_only_content_request(semantic_text):
        roleplay = _policy_guard_text(_strip_request_envelope(semantic_text))
        return (
            "roleplay_draft"
            if re.search(
                r"\b(?:role\s+play|simula)\b.{0,48}\b"
                r"(?:conversation|conversacion)\b",
                roleplay,
            )
            else "content_draft"
        )
    if _FREE_CONTENT_THING_CUE.match(_policy_guard_text(_strip_request_envelope(semantic_text))) is not None:
        # KNOWLEDGE1144 «contame un chiste»; tanda-02: the bare noun, after other turns.
        return "free_content"
    # Tanda 4f «configuré una alarma para despertarme por la mañana»: an alarm the person set is what they tell,
    # acknowledged without an offer, whatever came before in the conversation.
    if reported_own_schedule(semantic_text):
        return "observation_ack"
    # MEMORY1501/1503 H0174 «Me gusta tomar café.»: the social turn answered with the assistant's own tastes and
    # offers; the shape keeps it to an acknowledgement naming the person's preference. Tanda 6: after earlier
    # turns too («debieras saber que me gusta el jazz» got an offer), unless the taste points back at them («me
    # gusta esa», «I like that one»).
    preference = first_person_preference(semantic_text)
    if preference is not None and not (
        has_history and re.match(r"(?:ese|esa|eso|esos|esas|este|esta|esto|lo|la|it|that|this|those|these)\b", preference)
    ):
        return "preference_ack"
    if not has_history:
        # CONVERSATION1343 H0122 «hola Carter»: a greeting with another name
        # is answered by greeting back and saying the name is BAXY.
        reading = read_request(semantic_text)
        if (
            reading.greets
            and _MISNAMED_VOCATIVE.fullmatch(reading.ask or "") is not None
            and _reading_fold(reading.ask) != "baxy"
        ):
            return "misnamed_greeting"
        # CONVERSATION1343 H0059 «NO te preocupes si se abrio steam»: a
        # reassurance takes a brief acknowledgement, not a question.
        if reassurance_statement(semantic_text):
            return "reassurance_ack"
        # KNOWLEDGE1144/1149/1179 «contame algo», «estoy aburrido»: the
        # content is asked for, not a question about which content.
        if _FREE_CONTENT_CUE.match(_policy_guard_text(_strip_request_envelope(semantic_text))) is not None:
            return "free_content"
        # CONVERSATION1343 H0069 «Tienes algun meme?»: the generic unsupported
        # wording inverted the subject («Pido un meme…»); say the boundary.
        if visual_content_request(semantic_text):
            return "visual_content_boundary"
    # KNOWLEDGE1525 H0582 «Quien gana en batman vs superman»: KNOWLEDGE1473
    # asserted an invented outcome as a fact; the shape keeps it an opinion
    # whatever kind the model chose for the turn.
    if versus_contenders(semantic_text) is not None:
        return "versus_opinion"
    # KNOWLEDGE1525 H0596 «El agua moja?, responde con sarcasmo».
    if sarcasm_question(semantic_text) is not None:
        return "sarcastic_answer"
    # KNOWLEDGE1527 H0030 «¿Quieres el acompañante de Batman?»: BAXY has no
    # wants; it says so naming the thing and offers to act on it if meant.
    if assistant_desire_thing(semantic_text) is not None:
        return "assistant_desire"
    if conversation_kind not in {"knowledge", "followup"}:
        return None
    if explicit_negative_constraint(semantic_text):
        return "constraint_ack"
    if _HOW_IT_WORKS_CUE.search(_policy_guard_text(_strip_request_envelope(semantic_text))):
        # IDENTITY1323 H0373 «cómo funciona esto» answered as a plain chat.
        return "how_it_works"
    identity_reading = read_request(semantic_text)
    if identity_reading.has(INTENT_IDENTITY) and not identity_reading.has(INTENT_CAPABILITY):
        # IDENTITY1325 H0012 «to quien chuta eres.»: the plain knowledge reply
        # asked what «chuta» meant instead of saying who answers. A combined
        # «who are you and what can you do» keeps the catalog answer.
        return "identity"
    # Classify the question inside a language wrapper, while keeping the
    # original request for generation. Otherwise "responde en ...: qué es ..."
    # becomes an observation acknowledgment instead of an explanation.
    folded = _policy_guard_text(_strip_request_envelope(semantic_text))
    for _ in range(4):
        stripped = re.sub(
            r"^(?:(?:a\s+ver\s+baxy|baxy|hola|hello|hi|hey|oye|listen)\s+|"
            r"(?:por\s+curiosidad|una\s+duda|just\s+curious|a\s+question)\s+|"
            r"(?:por\s+favor|porfa|please)\s+|"
            r"(?:puedes|podrias|can\s+you|could\s+you|"
            r"would\s+you(?:\s+please)?)\s+)",
            "",
            folded,
            count=1,
        ).strip()
        if stripped == folded:
            break
        folded = stripped
    if re.search(
        r"^(?:please\s+)?(?:write|draft) me an? (?:email|mail) "
        r"(?:that|saying|about)\b",
        folded,
    ):
        return "content_draft"
    if re.match(r"^(?:traduce|traducir|translate)\b", folded):
        return "translation"
    if re.match(
        r"^(?:find|get|give|tell)\s+me\b",
        folded,
    ) and re.search(r"\b(?:jokes?|chistes?)\b", folded):
        # A joke request asks the model to produce content. It is not a plain
        # observation to acknowledge in one declarative sentence.
        return None
    if (
        re.search(
            r"\b(?:quien gana|which wins|who wins)\b",
            folded,
        )
        and re.search(r"\b(?:vs|versus|entre .+ y |between .+ and )\b", folded) is None
    ):
        return "underspecified_comparison"
    if not has_history and re.search(
        (
            r"\b(?:which of those|required task|todo lo de arriba|esta tarea|"
            r"nueva sesion|todo listo|el progreso|como ha ido|donde dejaste|"
            r"que me hiciste|intentalo|try it)\b"
        ),
        folded,
    ):
        return "missing_context"
    if (
        not has_history
        and not any(marker in text for marker in ("?", "¿", "？"))
        and re.match(
            r"\s*(?:que|what|why|how|which|who|cuando|when|donde|where|"
            r"por\s+que|como|cual|quien)\b",
            folded,
        )
        is None
        and re.match(
            r"\s*(?:explica(?:me)?|explain|describe|dime|tell me|cuentame|contame|"
            r"propon|propone|sugiere|suggest|traduce|translate|resume|"
            r"summarize|ayudame|help me)\b",
            folded,
        )
        is None
        # A knowledge turn must retain its information request. An adverb or
        # noun at the beginning is not evidence that the person asserted a
        # fact: "ahora explicame que es Steam" was forced into observation_ack
        # and answered as if the user had already supplied the explanation.
        # Only the already-classified followup may use this acknowledgment.
        and conversation_kind == "followup"
        and _reads_as_an_observation(folded)
    ):
        return "observation_ack"
    return None


# An acknowledgement restates what the person said. A command is not a
# statement, so acknowledging one invents a fact: "Compra un vuelo a Madrid"
# came back as "Mencionas que compraste un vuelo a Madrid", which is simply
# false. Require a declarative opening instead of accepting anything that is
# not a question. Falling through costs an abstention, which is honest; the
# alternative costs a fabrication, which invariant 2 forbids outright.
_OBSERVATION_OPENING = re.compile(
    r"^(?:"
    r"hoy|ayer|manana|anoche|ahora|siempre|nunca|todavia|ya|aqui|alla|"
    r"estoy|estamos|esta|estan|era|fue|hace|hay|tengo|tenemos|tenia|"
    r"me|mi|mis|nos|nuestro|nuestra|yo|nosotros|"
    r"el|la|los|las|un|una|unos|unas|este|esta|estos|estas|eso|esto|"
    r"parece|creo|pienso|siento|veo|noto|"
    r"today|yesterday|tomorrow|tonight|now|always|never|still|here|there|"
    r"i|im|ive|my|we|our|it|its|this|that|these|those|the|a|an|"
    r"is|are|was|were|feels|seems|looks|sounds"
    r")\b",
    re.IGNORECASE,
)


# A declarative opener is not the only shape an observation takes: "Cierre de
# Word podía perder trabajo" starts with a noun. What those share, and what a
# command lacks, is a finite verb that is not the first word. Accept either
# signal; a command still has its verb in front and nothing behind it.
_OBSERVATION_FINITE_VERB = re.compile(
    r"\b(?:"
    r"es|son|era|eran|fue|fueron|sera|seria|"
    r"esta|estan|estaba|estaban|estuvo|"
    r"hace|hacia|hay|habia|hubo|"
    r"puede|pueden|podia|podian|podria|podrian|pudo|"
    r"tiene|tienen|tenia|tenian|tuvo|"
    r"parece|parecia|suele|solia|va|van|iba|iban|"
    # A gerund or infinitive subject carries its predicate later: "Pintar la
    # reja nos llevo toda la tarde" is narration, not an order to paint.
    r"llevo|llevaron|duro|duraron|costo|costaron|tomo|tomaron|"
    r"resulto|salio|quedo|"
    r"took|lasted|"
    r"is|are|was|were|has|have|had|does|did|"
    r"can|could|will|would|should|might|must|"
    r"seems|seemed|feels|felt|looks|looked|sounds|sounded"
    r")\b",
    re.IGNORECASE,
)


def _reads_as_an_observation(folded: str) -> bool:
    stripped = folded.strip()
    if _OBSERVATION_OPENING.match(stripped) is not None:
        return True
    found = _OBSERVATION_FINITE_VERB.search(stripped)
    return found is not None and found.start() > 0


def _roleplay_participant_names(text: object) -> tuple[str, ...]:
    current = _strip_request_envelope(str(text or "").strip())
    name = r"[^\W\d_][\w'’\-]{0,39}"
    for pattern in (
        rf"\b(?:between|entre)\s+(?P<first>{name})\s+"
        rf"(?:and|y)\s+(?P<second>{name})\b",
        rf"\b(?:send\s+nothing\s+(?:to|a)|no\s+envies\s+nada\s+a)\s+"
        rf"(?P<first>{name})\s+(?:nor|ni|and|y)\s+"
        rf"(?P<second>{name})\b",
    ):
        found = re.search(pattern, current, flags=re.IGNORECASE)
        if found is not None:
            participants = (found.group("first"), found.group("second"))
            if participants[0].casefold() != participants[1].casefold():
                return participants
    return ()


def recall_asked(current: object) -> str | None:
    """What the message asks to be said back: the whole previous message of «user» or «assistant», a literal
    («quoted») the person said before («la palabra que mencioné antes»), or None."""

    speaker = _recalled_speaker(current)
    if speaker is not None:
        return speaker
    folded = _policy_guard_text(current)
    if (
        re.search(
            r"\b(?:palabra|frase|nombre|dato|codigo|word|phrase|name|value|code)\b",
            folded,
        )
        and re.search(
            r"\b(?:mencione|dije|escribi|use|mentioned|said|wrote|used)\b",
            folded,
        )
        and re.search(
            r"\b(?:anterior|previa|previo|antes|previous|prior|last|earlier)\b",
            folded,
        )
    ):
        return "quoted"
    return None


def quoted_literals(said: str) -> list[str]:
    """The literals quoted in a message («…», “…”, "…", `…`), in order."""

    return [
        next(group for group in match.groups() if group is not None).strip()
        for match in re.finditer(
            r"«([^»\r\n]{1,256})»|“([^”\r\n]{1,256})”|"
            r'"([^"\r\n]{1,256})"|`([^`\r\n]{1,256})`',
            said,
        )
    ]


def asks_an_extended_answer(text: str) -> bool:
    """The person asks for more than a plain answer: detail, steps, a list, a story (the reply keeps room)."""

    return _EXTENDED_ANSWER_ASK.search(_reading_fold(text)) is not None


def asks_a_laugh(request: object) -> bool:
    """A laugh asked for, performed on the spot («haz una carcajada», «ríete»)."""

    return _LAUGHTER_ASKED.match(_policy_guard_text(_strip_request_envelope(str(request or "")))) is not None


# Only a question for the name or for who is answering has BAXY's name as its
# answer; «¿cuál es tu lugar de origen?» is answered without it («No tengo un
# lugar de origen; vivo en este PC» was rejected for not saying «BAXY»).
_IDENTITY_ASKS_THE_NAME = (
    r"\b(?:quien\s+(?:\w+\s+){0,2}(?:eres|sos|es\s+usted)|quien\s+(?:habla|esta\s+hablando)|"
    r"who\s+(?:\w+\s+){0,2}are\s+you|who\s+is\s+speaking|(?:tu|your)\s+(?:propio\s+|own\s+)?"
    r"(?:nombre|name)|como\s+te\s+llamas|what\s+(?:should\s+i\s+)?call\s+you|presentate|"
    r"introduce\s+yourself|describete|describe\s+yourself)\b"
)


_DEICTIC_REFERENCE = re.compile(
    r"\b(?:this|that|these|those|este|esta|esto|estos|estas|ese|esa|eso|"
    r"esos|esas)\b",
    re.IGNORECASE,
)


_IDENTITY_QUESTION = re.compile(
    r"\b(?:what|which)\b.{0,48}\b(?:name|called)\b"
    r"|\b(?:como\s+se\s+llama|que\s+nombre)\b",
    re.IGNORECASE,
)


# The person asks whether something of theirs is so («está mi orden lista para recoger ya», «did I leave the
# stove on», «¿tengo reuniones mañana?»). What they may or should do is knowledge («¿mi perro puede comer
# uvas?», «do I need a visa»), and a question about the world or about BAXY is not about theirs.
_ASKED_ABOUT_WRAPPER = re.compile(
    r"^\W*(?:(?:i\s+(?:need|want|would\s+like)\s+to\s+know|i'd\s+like\s+to\s+know|tell\s+me|(?:can|could)\s+you\s+"
    r"(?:tell\s+me|check)|do\s+you\s+know|check|quiero\s+saber|necesito\s+saber|dime|me\s+(?:puedes|podes|podrias)\s+"
    r"decir|sabes|revisa|mira|fijate|comprueba|verifica)\s+(?:if|whether|si)\s+)"
)


_ASKED_WH = re.compile(
    r"^\W*(?:que|cual|cuales|como|donde|cuando|quien|quienes|cuanto|cuanta|cuantos|cuantas|por\s+que|para\s+que|"
    r"what|which|how|where|when|who|whom|whose|why)\b"
)


_ASKED_ABOUT_THE_PERSON = re.compile(
    r"\b(?:mi|mis|my|mine|tengo|tenia|llevo|deje|puse|hice|do\s+i|did\s+i|have\s+i|i\s+have|i've|i\s+had|i\s+left)\b"
)


_ASKED_WHAT_MAY_BE = re.compile(
    r"\b(?:puedo|puede|pueden|podria|podrian|debo|debe|deberia|deberian|necesito|necesita|hace\s+falta|conviene|"
    r"es\s+(?:bueno|malo|normal|seguro|recomendable|posible)|can|could|should|must|may|might|need|needs|ought|"
    r"is\s+it\s+(?:ok|okay|safe|normal|bad|good|possible)|would)\b"
)


_NON_EVENT_CONFIRMATION = re.compile(
    r"(?:si|if)\s+(?:eso|it|that)?\s*(?:no|didn\s?t|did not|nunca)\s+"
    r"(?:pas[oó]|ocurri[oó]|sucedi[oó]|happen(?:ed)?|lo\s+hiciste|hiciste)\b",
)


def _asks_non_event_confirmation(user_text: str) -> bool:
    """The person asks whether what they forbade actually happened."""

    return _NON_EVENT_CONFIRMATION.search(
        _policy_guard_text(_strip_request_envelope(str(user_text or "")))
    ) is not None


# «Si hazlo», «dale, hacelo», «do it»: an assent that names no action. The
# clarification must ask which action, never «¿Qué querés que abra?».
_ASSENT_WITHOUT_ACTION = re.compile(
    r"[\s¡!¿?]*(?:(?:si|ok|okay|dale|bueno|vale|ya|yes|yeah|sure)\s*,?\s+)?"
    r"(?:(?:por favor|please)\s*,?\s+)?"
    r"(?:haz(?:lo|\s+(?:eso|esto|aquello))|hace(?:lo|\s+(?:eso|esto|aquello))|"
    r"dale(?:\s+con)?\s+(?:eso|esto)|do\s+(?:it|that|this)|"
    r"make\s+(?:it|that)\s+happen|go\s+ahead(?:\s+with\s+(?:it|that|this))?)"
    r"(?:\s*,?\s*(?:por favor|please))?[\s.!?]*",
    re.IGNORECASE,
)


# A time-sensitive office holder: who holds it now is looked up, never answered from memory.
_CURRENT_WORD = r"\b(?:current|currently|actual|actualmente|ahora|now)\b"
_PUBLIC_OFFICE = (
    r"\b(?:president|presidente|prime\s+minister|primer\s+ministro|"
    r"chancellor|canciller|governor|gobernador|mayor|alcalde|ceo)\b"
)


def names_a_current_public_office(folded: str) -> bool:
    """«el presidente actual», «the current ceo»: a public office and now (folded, one space between words)."""

    return bool(effect_intent._has(folded, _CURRENT_WORD) and effect_intent._has(folded, _PUBLIC_OFFICE))


def asks_baxys_name(request: object) -> bool:
    """The identity question asks the name («¿cómo te llamas?»): the answer says «BAXY»."""

    return re.search(_IDENTITY_ASKS_THE_NAME, _policy_guard_text(str(request or ""))) is not None


def asks_a_polar_question_about_the_person(request: object) -> bool:
    """A yes/no question about the person's own things («¿tengo correos nuevos?»), not a wh-question nor what may
    be: only what was read of them answers it."""

    asked = _ASKED_ABOUT_WRAPPER.sub("", _accent_folded_with_punctuation(request).casefold())
    return not (
        _ASKED_WH.search(asked) is not None
        or _ASKED_ABOUT_THE_PERSON.search(asked) is None
        or _ASKED_WHAT_MAY_BE.search(asked) is not None
    )


def asks_what_this_is(request: object) -> bool:
    """«¿qué es esto?», «what is that?»: an identity question about something pointed at, not named."""

    request_folded = _policy_guard_text(request)
    return (
        _DEICTIC_REFERENCE.search(request_folded) is not None
        and _IDENTITY_QUESTION.search(request_folded) is not None
    )


def assent_without_action(current: str) -> bool:
    """«sí, hazlo», «dale» with nothing to do named: an assent that names no action."""

    return _ASSENT_WITHOUT_ACTION.fullmatch(_reading_fold(current)) is not None


def coordinates_actions(request: object) -> bool:
    """The request joins two things with «y» / «and»: a denial mirroring both is one limit."""

    return re.search(r"\b(?:y|e|and)\b", _policy_guard_text(str(request or ""))) is not None


# cien-41 y cien-45, turno 027: el pedido ambiguo que sólo trae el verbo; abrir o cerrar sin objeto.
_AMBIGUOUS_ACTION_VERBS = (
    ("open", ("abrir", "abre", "abreme", "open")),
    ("close", ("cerrar", "cierra", "close")),
)


def ambiguous_action_verb(user_text: str) -> str | None:
    """The action an ambiguous request names without its object («abre», «cierra»): «open», «close» or None."""

    folded = _reading_fold(user_text)
    for action, verbs in _AMBIGUOUS_ACTION_VERBS:
        if any(re.search(r"(?<!\w)" + verb, folded) for verb in verbs):
            return action
    return None


def quoted_translation_phrase(user_text: str) -> str | None:
    """The quoted phrase a translation request asks for («traduce 'good evening'»), as written, or None."""

    current = str(user_text or "")
    if re.search(r"traduc|translat", current, re.IGNORECASE) is None:
        return None
    quoted = re.search(r"['‘“\"«]([^'’”\"»]{2,40})['’”\"»]", current)
    return quoted.group(1) if quoted is not None else None
