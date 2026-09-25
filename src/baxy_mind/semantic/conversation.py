"""Messages that ask BAXY to talk, not to act: a social act, a nonunderstanding, a question of knowledge or a
limit BAXY states.

They moved from ``__main__`` with the unification of the reading (owner, 2026-09-24: every reading of the request
lives in ``semantic/``). Each returns what it read — the conversation kind and the language to answer in, or
whether the form is there — and ``__main__`` builds the turn decision from it. None grants an operation.
"""

from __future__ import annotations

import re
import unicodedata

from .. import effect_intent
from .catalog import ApplicationCatalogIndex, GameCatalogIndex, build_application_catalog_index
from .dialogue import _history_has_pending_clarification, _previous_user_request
from .grammar import ARITHMETIC_EXPRESSION, SPOKEN_NUMBER, spoken_number_request
from .intent import EffectIntent
from .patterns import conversation_only_content_request, echo_mode_request
from .request import (
    INTENT_AMBIGUOUS_ACTION,
    INTENT_IDENTITY,
    _INTERROGATIVE,
    read_request,
    response_language as read_language,
)


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
        and effect_intent._has(
            folded,
            r"\b(?:current|currently|actual|actualmente|ahora|now)\b",
        )
        and effect_intent._has(
            folded,
            r"\b(?:president|presidente|prime\s+minister|primer\s+ministro|"
            r"chancellor|canciller|governor|gobernador|mayor|alcalde|ceo)\b",
        )
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
