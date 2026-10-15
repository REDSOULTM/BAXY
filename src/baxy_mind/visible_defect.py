"""The veto of a composed reply that a person would read as a filled hole or an unbacked statement
(``compose_visible_defect``), and the checks only it uses.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from urllib.parse import urlparse

from .semantic.normalize import _accent_folded_with_punctuation, _policy_guard_text, fold
from .semantic import dialogue as dialogue_slot
from .semantic import listing as semantic_listing
from .semantic import voice_register as semantic_voice_register
from .semantic import claims as semantic_claims
from .semantic import messaging as semantic_messaging
from .semantic.network import asks_calendar_part
from .semantic.temporal import clock_later_asked, plural_alarm_cancellation
from .semantic.games import _edit_distance
from . import effect_intent
from .effect_intent import countdown_target, literal_clipboard_write_text
from .semantic.request import (
    fold as _reading_fold, followup_topic, INTENT_CAPABILITY, INTENT_CONTINUE_CONSTRAINT, INTENT_REFUSE, read_request,
)
from .window_prose_facts import window_status_assertions
from .observed_response_literals import without_observed_names
from .semantic.conversation import (
    _conversation_presentation_shape, asks_for_an_internal_identifier, asks_for_code, asks_whether_able,
    ends_asking_the_person, without_quoted_speech, without_saying_inability,
)
from .semantic.apps import asks_to_close, object_asked_to_close
from .semantic.audio import asks_a_timed_silence
from .semantic.media import asks_the_album, asks_what_is_playing
from .semantic.network import asks_the_clock, names_the_time
from .semantic.notes import names_the_title
from .semantic.request import _conversation_response_language, addressed_language
from .request_intents import (
    _knowledge_to_answer, _looks_like_ambiguous_action, _looks_like_capability_question,
    _looks_like_continue_constraint, _looks_like_greeting_ask, _looks_like_knowledge_question,
    _looks_like_negative_constraint, _looks_like_refuse_question, _message_response_language,
)
from .dialogue_history import _repeats_the_last_answer, _says_the_person_back
from .reply_language_checks import (
    _DOTTED_OP, _IDENTIFIER_TOKEN, _MISMATCHED_ACTION_NOUN, _SNAKE_CODE, _SUCCESS_OPENERS, _WEB_HOST,
    visible_reply_breaks_article_agreement, visible_reply_breaks_estar_participle, visible_reply_breaks_first_person,
    visible_reply_breaks_spanish_plural, visible_reply_breaks_word_case, visible_reply_calls_the_person_baxy,
    visible_reply_cuts_a_word, visible_reply_invents_a_spanish_infinitive, visible_reply_is_a_fixed_stall,
    visible_reply_leaks_a_contract_token, visible_reply_says_a_vulgarity, visible_reply_speaks_of_the_person,
)
from .clock_facts import (
    _calendar_contradiction, _calendar_facts, _countdown_facts, _local_datetime_from_observed, _misses_calendar_facts,
    _names_clock_place, _place_clock_facts,
)
from .compose_situation import (
    _ABSENCE_STATEMENT, _addressed_to_the_person, _ALREADY_STATEMENT, _completed_step_operation, _computer_use_mission,
    _downloaded_and_opened_picture, _FAILED_ATTEMPT, _failure_is_an_absence, _failure_is_an_asked_state_held,
    _failure_is_an_unchanged_state, _failure_opened_the_page, _GENERAL_PLAYBACK_ABSENCE, _local_clock_from_situation,
    _merged_observed, _microphone_muted_fact, _MICROPHONE_SAID_OFF, _MICROPHONE_SAID_ON, _only_the_session_tab_read,
    _recalled_records, _reply_calendar_moment, _situation_error_codes, _situation_from_facts, _situation_steps,
    _verified_empty_known_file_query, _verified_notification_dues, _without_memory_notice,
    _without_observed_search_vocabulary,
)
from .capability_families import CAPABILITY_FAMILIES
from .clock_checks import (
    _clock_fact_defect, _clock_only_from_situation, _failure_invents_a_clock, _scheduled_notification_defect,
)
from .media_facts import (
    _bracket_is_observed, _MEDIA_ALBUM_UNKNOWN, _MEDIA_TITLE_BY_PARTS, _MEDIA_TITLE_OPERATIONS, _names_media_title,
    _title_fold, _without_media_title,
)
from .failure_wording import (
    _asserts_failure, _denies_the_failed_act, _FAILURE_MARKERS, _failure_word_is_the_persons, _OPEN_PROGRAMS_LIST,
)
from .device_facts import _opens_with_observed_identifier, _recognized_screen_text_in_situation
from .search_report import (
    _listing_not_found_report, _search_not_found_report, _search_results_of, _verified_search_results,
)
from .agenda_facts import (
    _guarded_add_not_run, _LIST_ADD_CLAIM, _new_empty_list, _observed_local_clocks, _situation_record_titles,
    _TITLED_ITEM_WRITES, _without_record_titles,
)
from .app_open_facts import (
    _app_open_observed_name, _app_open_was_already_running, _apps_found_running, _claims_a_relaunch,
    _claims_it_performed_the_open, _claims_the_target_was_open_before, _states_it_was_already_running,
)
from .previous_answer import _contradicts_previous_count, _referenced_previous_answer
from .draft_cleanup import _glued_proper_name, _strip_prompt_labels
from .limit_voice import _unsupported_answer_has_inability, limit_voice_defect
from .conversation_checks import visible_reply_is_only_questions
from .reply_claims import (
    _EFFECT_CLAIM_NEGATED, _go_ahead_reply_unmet, _NEGATED_OWN_WRITE, _OBSERVED_INSTRUMENT_READING,
    _PRESENT_STATE_CLAIM, _READING_IS_ABOUT_THIS_MACHINE_NOW, cancelled_clarification_defect, conversation_world_claim,
    visible_reply_promises_the_act,
)
from .conversation_shape import _misses_content_shape, _numbers_in_figures
from .talk_memory_figures import talk_memory_figures
from .compose_payload import (
    _app_is_feminine, _localized_confirmation_words, _required_compose_input, identifier_is_plumbing,
)
from .compose_instructions import _ALREADY_SHOWN_AUTHORITY
from .computer_use_finals import (
    _capture_place_claimed, _capture_saved_place_contradicted, _claims_defect, _computer_use_final_defect,
    _elevated_read_floor, _reached_but_unread_report, _without_quoted_focused_field,
)
from .deterministic_finals import _absent_label_misquoted, _NOT_UNDERSTOOD_CAUSES
from .payload_fact_checks import _headline_words, _without_quoted_headlines, tells_own_act_as_the_persons


def _names_the_boundary(folded_reply: str) -> str | bool:
    """La respuesta dice que el pedido queda fuera de lo que hace este PC."""

    return any(marker in folded_reply for marker in _SCOPE_MARKERS) or _unsupported_answer_has_inability(
        folded_reply
    )


def _verified_effect(situation: object) -> bool:
    """A result the PC verified done: one operation verified and succeeded, or a mission whose every step was."""

    if not isinstance(situation, dict):
        return False
    if str(situation.get("cause") or "").strip().lower() == "mission_completed":
        return True
    return bool(situation.get("operation")) and situation.get("verified") is True and situation.get("succeeded") is True


def _page_prose_of(value: object) -> list[str]:
    """The page prose of the facts: result titles, snippets and urls."""

    if isinstance(value, dict):
        prose = [
            child for key, child in value.items()
            if key in ({"snippet", "url", "title"} if "snippet" in value else {"snippet", "url"})
            and isinstance(child, str)
        ]
        return prose + [text for child in value.values() for text in _page_prose_of(child)]
    if isinstance(value, (list, tuple)):
        return [text for child in value for text in _page_prose_of(child)]
    return []


def _truncated_fact_word(text: str, facts: dict) -> bool:
    """Una palabra de los hechos publicada a medias: «mover y enfoc ventanas».

    Se deriva de lo que se le dio al modelo, no de un diccionario: si un token
    del texto es el principio de una palabra que venía en los hechos y no es esa
    palabra ni una de sus formas más largas, el modelo la cortó.
    """

    def values_only(value: object) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            # Narrator metadata describes observations; it is not literal text
            # whose wording must be preserved like names, titles or capabilities.
            # The operation identifier is metadata too: «I'll remind you» is
            # not a truncated «reminder.create» (TIME1189/012), and «address»
            # is not a cut of the provenance value
            # «windows_active_unicast_addresses_secondread» (NETWORK1201/002).
            # A search result snippet is prose, not a name: «clima actual» is
            # not a cut of the snippet word «actualizada» (WEB1447/001). A
            # result URL glues words together («atlasanimal.com»): «Atlas» is
            # not a cut of it (KNOWLEDGE1509/000). The title of a search
            # result is that page's prose too: «se actualiza durante el día» is
            # not a cut of the title word «Actualizado» (uso real 2026-09-23).
            page_prose = {"snippet", "url", "title"} if "snippet" in value else {"snippet", "url"}
            return [
                text
                for key, child in value.items()
                # A7 E5 (DEV-A3 t388): cause is the English prose of a typed cause for the narrator; the Spanish
                # «ambiguo» of a reply is not a cut of its «ambiguous».
                if key not in {"observationScope", "unit", "operation", "authority", "cause"} | page_prose
                for text in values_only(child)
            ]
        if isinstance(value, (list, tuple)):
            return [text for child in value for text in values_only(child)]
        return []

    # Nested wire keys such as seen.final.volumePercent are not natural words
    # supplied to the narrator: "volume" is not a truncated "volumePercent".
    values = " ".join(values_only(facts or {})).casefold()
    # Compare the same token lengths on both sides. A complete short name
    # may also prefix a longer process name in the very same observation.
    fact_words = set(re.findall(r"[a-záéíóúñ]{5,}", values))
    if not fact_words:
        return False
    # tanda-02 (how to get to a theme park): the page's own word is whole, not a
    # cut of a longer fact word. The label «parque» of a result host such as
    # parquelandia.parque.com was read as a cut of the query's «parquelandia».
    page_words = set(re.findall(r"[a-záéíóúñ]{5,}", " ".join(_page_prose_of(facts or {})).casefold()))
    for token in re.findall(r"[a-záéíóúñ]{5,}", text.casefold()):
        if token in fact_words or token in page_words:
            continue
        if any(
            word.startswith(token)
            and len(word) >= len(token) + 2
            # KNOWLEDGE1507: «curiosidad» is the singular of the result title
            # word «curiosidades», not a cut of it; the same for «-s» plurals.
            and word not in (token + "s", token + "es")
            for word in fact_words
        ):
            return True
    return False


_META_OPENING = re.compile(
    r"^\s*(?:"
    r"en (?:espa[nñ]ol|ingl[eé]s)|in (?:spanish|english)|"
    r"en la situaci[oó]n|in the situation|"
    r"(?:la frase|el texto|el mensaje) (?:es|ser[ií]a)|"
    r"(?:the |la |los |las )?(?:facts?|hechos?|situation|situaci[oó]n) "
    r"(?:are|is|son|es)"
    r")\b",
    re.IGNORECASE,
)

# Vocabulario del encargo, nunca de una respuesta: el modelo describía cómo
# había redactado en vez de contestar («hago una frase en español según los
# detalles del turno», «I am a system that responds in English»).
_TASK_METADISCOURSE = re.compile(
    r"(?:una|la|otra) frase en (?:espa[nñ]ol|ingl[eé]s)|"
    r"a sentence in (?:spanish|english)|"
    r"(?:detalles|datos) del turno|details of (?:this |the )?turn|"
    r"cumple con (?:los|las) (?:requisitos|reglas)|meets the requirements|"
    r"respond[eo]s? en (?:espa[nñ]ol|ingl[eé]s)|"
    r"respond(?:s|ing)? in (?:spanish|english)|"
    # KNOWLEDGE1473 «Que es doom eternal=»: «videojuego de disparos en primera
    # persona» quoted from a Wikipedia snippet is the genre, not the model
    # telling that it wrote in the first person.
    r"(?<!disparos )(?<!disparos en )(?<!juego )(?<!juego en )(?<!vista )(?<!vista en )"
    r"(?<!camara )(?<!camara en )(?<!cámara )(?<!cámara en )(?<!perspectiva )(?<!perspectiva en )"
    r"(?<!shooter )(?<!shooter en )"
    r"(?:en |in )?primera persona(?! shooter)|"
    r"first person(?! shooter| view| perspective| camera| combat)|"
    r"sin (?:c[oó]digo|t[eé]rminos internos)|no internal (?:codes?|terms?)|"
    # M54 (v3b-final F-p08-t3 «What is the venue of the event?» → «The venue is not specified in the provided
    # information»): the facts the writer was given are the prompt, not something the person gave or can see.
    r"\b(?:the|this|la|esta|los|estos|las|estas) (?:provided|given|supplied) (?:information|info|data|facts|context|"
    # M105 (DEV-D v4a D-p23-t2 «…in the provided text»).
    r"texts?|content|passages?|documents?)\b|"
    r"\b(?:el|los|este|estos) textos? (?:proporcionad|suministrad|facilitad|dad)[oa]s?\b|"
    r"\b(?:information|info|data|facts|context) (?:provided|given|supplied)(?! by)\b|"
    r"\b(?:informaci[oó]n|datos|hechos|contexto|situaci[oó]n) (?:proporcionad|suministrad|facilitad)[oa]s?\b|"
    # M89 (DEV-D v3r D-p35-t3 «…solo refleje lo que me diste en la situación…»): «la situación» is the prompt's name
    # for the facts; what was given «in the situation» is the prompt spoken of.
    r"\b(?:me|te|nos) (?:diste|dio|dieron|di|pasaste|pasaron) en la situaci[oó]n\b|"
    r"\b(?:you|i) (?:gave|was given|were given) (?:me |you )?in the situation\b",
    re.IGNORECASE,
)

# H0714 y H0096: una respuesta que empieza explicando «el fallo» habla del
# desperfecto interno, no con la persona. El dueno lo rechazo escrito asi en
# espanol —«El fallo se debe a que el resultado no fue verificado»— y el mismo
# molde salia en ingles —«The failure occurred because no element on the screen
# matches...»— aun con el hecho correcto detras. Se veta solo la apertura, de
# modo que contar lo que paso sigue siendo posible en cualquier otro lugar de
# la frase.
_FAILURE_AS_TOPIC = re.compile(
    r"^\s*(?:el|la)\s+(?:fallo|falla|error)\s+"
    r"(?:se\s+deb[eií]|fue\s+(?:porque|debido)|ocurri[oó]|sucedi[oó]|"
    r"se\s+produjo|consisti[oó])"
    r"|^\s*the\s+(?:failure|error)\s+"
    r"(?:occurred|happened|arose|stems|resulted|is\s+due|was\s+(?:because|due|caused))",
    re.IGNORECASE,
)

_SCOPE_MARKERS = (
    "not listed",
    "outside",
    "beyond",
    "not part of",
    "not in my",
    "nothing else",
    "only do",
    "only what",
    "only the work",
    "fuera de",
    "no esta en",
    "no está en",
    "mas alla",
    "más allá",
    "no figura",
    "nada mas",
    "nada más",
    "solo hago",
    "sólo hago",
    "solo lo que",
    "sólo lo que",
    "unicamente",
    "únicamente",
)


_CONCRETE_ACTS = re.compile(
    r"\b(?:open|close|launch|book|send|install|delete|mute|"
    r"volume|window|app|note|file|browser|print|download|"
    r"abrir|cerrar|lanzar|reservar|enviar|instalar|room)\b"
)


def _names_a_served_act(folded_reply: str, facts: dict) -> bool:
    """La respuesta habla del trabajo de este PC, no de una categoría moral.

    Vale un marcador de alcance («outside», «not listed», «fuera de»), una
    palabra del catálogo activo que el shell manda en `capabilities`, o un acto
    concreto conocido. Antes sólo valía esta última lista cerrada, y por eso
    «I will never install unauthorized software on this PC» —correcta— se
    rechazaba seis veces seguidas hasta agotar la composición.
    """

    if any(marker in folded_reply for marker in _SCOPE_MARKERS):
        return True
    if _CONCRETE_ACTS.search(folded_reply) is not None:
        return True
    families = facts.get("capabilities") if isinstance(facts, dict) else None
    if not isinstance(families, (list, tuple)) or not families:
        families = list(CAPABILITY_FAMILIES)
    vocabulary: set[str] = set()
    for family in families:
        entry = CAPABILITY_FAMILIES.get(str(family or "").casefold())
        if entry is None:
            continue
        for phrase in entry:
            vocabulary.update(re.findall(r"[a-záéíóúñ]{4,}", phrase.casefold()))
    return any(
        word in vocabulary for word in re.findall(r"[a-záéíóúñ]{4,}", folded_reply)
    )


def repeats_a_sent_instruction(
    candidate: str,
    instructions: object,
    request: str = "",
    observed_texts: tuple[str, ...] = (),
) -> bool:
    """El texto visible reproduce el encargo que se envió en este turno.

    Derivado de lo que realmente se envió, no de una lista de frases prohibidas:
    si mañana cambia una instrucción, la garantía sigue en pie. Se compara sin
    acentos porque la instrucción decía «terminos» y el modelo escribía
    «términos», y la copia pasaba.

    Cuenta además el rótulo con el que abre una instrucción —«Internal language
    policy», «Política interna del turno»—: es tan encargo como su cuerpo, y era
    por ahí por donde salía a pantalla, no copiado sino citado: «(Note: I'm
    responding in English as per the internal language policy.)»
    (panel-opus-13/044).

    Sólo el rótulo de apertura, y sólo si no lleva cifras. Cortar por todos los
    dos puntos convertía un hecho de obligada reproducción —«Incluye
    literalmente: Paso 1: La hora local es 14:25.»— en una instrucción copiada,
    y el turno se quedaba sin publicar el dato que debía dar.

    Y lo que dijo la persona no es una instrucción interna aunque la
    instrucción lo repita: contestar «keep talking without launching anything»
    es decir «I will keep talking without launching anything», y vetarlo agotó
    el turno seis veces seguidas (limites-19/009). Es la misma exención que ya
    tienen los términos prohibidos que aparecen en el pedido.
    """

    folded_candidate = _reading_fold(candidate or "")
    if not folded_candidate:
        return False
    if not isinstance(instructions, (list, tuple)):
        return False
    folded_request = _reading_fold(request or "")
    for instruction in instructions:
        text_sent = str(instruction or "")
        fragments = re.split(r"[.\n]", text_sent)
        label, separator, _ = text_sent.partition(":")
        if separator and len(label) <= 48 and not any(c.isdigit() for c in label):
            fragments.append(label)
        for sentence in fragments:
            fragment = _reading_fold(sentence)
            if len(fragment) < 16 or fragment not in folded_candidate:
                continue
            if folded_request and fragment in folded_request:
                continue
            # MUSIC1559: a hint that names an observed value («Daft Punk -
            # Instant Crush (Official Video) ft. Julian Casablancas») is
            # asking for that value; the draft that quotes it is not copying
            # the instruction.
            if any(fragment.strip(" «»\"'") in _reading_fold(value) for value in observed_texts if value):
                continue
            return True
    return False


# Tanda 4c «Incrementa el brightness al level 8» → «El brightness se incrementó al nivel 8.»: the Spanish contract
# («Fuera de los literales del contrato, no introduzcas palabras inglesas») was checked only sentence by sentence,
# so the person's English noun echoed inside Spanish prose passed. These are the PC's own nouns with the Spanish
# word a Spanish reply uses; a quoted literal, an observed name, a host («weather.com») or a capitalised title
# word («Official Music Video») keeps its words.
_ENGLISH_PC_NOUNS = {
    "brightness": "brillo", "level": "nivel", "volume": "volumen", "sound": "sonido", "screen": "pantalla",
    "music": "música", "song": "canción", "folder": "carpeta", "file": "archivo", "files": "archivos",
    "settings": "configuración", "keyboard": "teclado", "battery": "batería", "wallpaper": "fondo de pantalla",
    "desktop": "escritorio", "clipboard": "portapapeles", "alarm": "alarma", "reminder": "recordatorio",
    "weather": "clima", "microphone": "micrófono", "speakers": "parlantes", "window": "ventana",
}
_ENGLISH_PC_NOUN = re.compile(r"(?<![\w-])(?<!\w\.)(?:" + "|".join(_ENGLISH_PC_NOUNS) + r")(?![\w-])(?!\.\w)")


def _english_pc_nouns(text: str) -> list[str]:
    """The PC nouns written in English (lower case) in a reply, outside quoted literals."""

    prose = re.sub(r'"[^"]*"|«[^»]*»|“[^”]*”', "", text)
    return list(dict.fromkeys(_ENGLISH_PC_NOUN.findall(prose)))


# M50: the code of a reply to a code request — a fenced block, an inline span, or bare lines of code (v3a-final
# F-w07-t1 answered «def calcular_media(lista):» with no fence) — is the content asked for. Only the prose around it
# is judged for jargon, internal identifiers and language. Twin of UserMessagePolicy.RequestedCodeProse.
_CODE_FENCE = re.compile(r"```[\s\S]*?(?:```|\Z)|`[^`\n]+`")
_CODE_LINE = re.compile(
    r"^(?:[ \t]{2,}\S.*"
    r"|\s*(?:def|class|function|const|let|var|return|import|elif|except|catch|public|private|static|async|await|"
    r"fn|func|package|using|#include)\b.*"
    r"|\s*from\s+[\w.]+\s+import\b.*"
    r"|\s*(?:for|while|if|switch)\s*\(.*"
    r"|\s*(?:print|console\.\w+|document\.\w+|System\.out\.\w+)\s*\(.*"
    r"|\s*(?:SELECT|FROM|WHERE|ORDER BY|GROUP BY|HAVING|LIMIT|INSERT INTO|UPDATE|DELETE FROM|CREATE TABLE|"
    r"(?:LEFT |RIGHT |INNER |OUTER )?JOIN|VALUES|UNION)\b.*"
    r"|\s*[\w.\[\]]+\s*(?:[-+*/%]|\?\?)?=\s*[^=\s].*"
    r"|.*[{};]\s*|\s*[}\])].*)$"
)


def requested_code_prose(reply: str) -> str:
    """``reply`` without the code it carries: fenced and inline code, and lines that are code."""

    unfenced = _CODE_FENCE.sub(" ", str(reply or ""))
    return "\n".join(line for line in unfenced.splitlines() if not _CODE_LINE.match(line)).strip()


def _reply_uses_opposite_language(text: str, language: str | None) -> bool:
    """Shared direct/compose check; short neutral names are not a language error."""
    if language not in {"es", "en"}:
        return False

    def opposite(fragment: str) -> bool:
        spanish, english = read_request(fragment).evidence
        # An accented name alone is neutral; Spanish wording must support
        # the orthographic bonus, including short answers such as «Sí».
        if spanish and not read_request(_policy_guard_text(fragment)).evidence[0]:
            spanish = 0
        wanted, other = (spanish, english) if language == "es" else (english, spanish)
        return not wanted and other >= 2

    # Ronda 22 (r18 t3-c03 «1. Among Us … 4. It Takes Two 5. Portal 2» for a Spanish request): a line or item that is
    # only a name or a title (semantic.listing.title_only) is in no language of the reply; a list of titles alone is
    # neutral, as a short name is.
    text = "\n".join(line for line in str(text or "").split("\n") if not semantic_listing.title_only(line))
    if not text.strip():
        return False
    if opposite(text):
        return True
    # A correct opening must not hide an unrelated foreign-language sentence.
    # Embedded literal quotations may legitimately retain their source language;
    # the whole-answer check above still rejects an entirely foreign quote.
    prose = re.sub(
        r'```[\s\S]*?```|`[^`]*`|"[^"]*"|«[^»]*»|“[^”]*”'
        r"|(?<!\w)'[\s\S]*?'(?!\w)",
        "", text,
    )
    return any(opposite(sentence) for sentence in re.split(r"(?<=[.!?])\s+|\n+", prose))


def _cpu_only_numbers_contradict(text: str, observed: dict) -> bool:
    """Check CPU quantities where no other observed metric can own them."""
    cpu = observed.get("cpu")
    if not isinstance(cpu, dict) or not cpu or set(observed) - {"scope", "cpu", "failures"}:
        return False
    number_text = text.replace("−", "-")
    for match in re.finditer(
        r"(?<![\w.,+-])([+-]?\d+(?:[.,]\d+)?)\s*(?:%|por\s*ciento\b|per\s*cent\b)",
        number_text,
        re.IGNORECASE,
    ):
        value = cpu.get("usagePercent")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 100:
            return True
        shown = match[1].replace(",", ".")
        precision = len(shown.partition(".")[2])
        if abs(float(shown) - value) > 0.5 * 10 ** -precision + 1e-9:
            return True
    counts = re.finditer(
        r"(?<![\w+-])(?:(?P<number>[+-]?\d+)\s+(?:"
        r"(?P<before>physical|logical)\s+(?:cores?|processors?)|"
        r"(?:n[uú]cleos?|cores?|procesadores?|processors?)(?:\s+(?P<after>f[ií]sicos?|l[oó]gicos?))?)|"
        r"(?P<label>physical|logical)\s+(?:cores?|processors?)(?:\s+count)?\s*:\s*(?P<count>[+-]?\d+))\b",
        number_text,
        re.IGNORECASE,
    )
    for match in counts:
        qualifier = match["before"] or match["after"] or match["label"] or "physical"
        key = "logicalProcessorCount" if qualifier.casefold().startswith(("log", "lóg")) else "physicalCoreCount"
        value = cpu.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value != int(match["number"] or match["count"]):
            return True
    return False


# The reads and the incomplete request a deferred clarification can join;
# the composer re-reads the person's text with this closed set only.
_DEFERRED_COMPOSE_OPERATIONS = (
    "system.time", "window.resolve", "audio.volume.adjust", "audio.volume",
    "audio.app.volume.adjust", "audio.app.volume.set",
)
_DEFERRED_QUESTION_WORDS = {
    "volume_amount": re.compile(
        r"cu[aá]nto|qu[eé]\s+cantidad|a\s+qu[eé]\s+nivel|cu[aá]ntos?\s+(?:puntos|niveles|por\s+ciento)|how\s+much|what\s+level|by\s+how",
        re.IGNORECASE,
    ),
    "indeterminate_window": re.compile(
        r"cu[aá]l|qu[eé]\s+ventana|which(?:\s+window|\s+one)?", re.IGNORECASE,
    ),
}
_DEFERRED_EFFECT_CLAIMS = {
    "volume_amount": re.compile(
        r"(?:sub[ií]|baj[eé]|aument[eé]|reduj[eé]|ajust[eé]|cambi[eé]|pus[eé])\s+(?:el\s+)?volumen|"
        r"volumen\s+(?:subido|bajado|ajustado|cambiado)|(?:raised|lowered|turned\s+(?:up|down)|adjusted|changed)\s+the\s+volume",
        re.IGNORECASE,
    ),
    "indeterminate_window": re.compile(
        # «enfoqué» (done) is a claim; «que enfoque» (the question) is not.
        r"\benfoqué\b|\b(?:ya|la|lo)\s+enfoqu[eé]\b|\b(?:quedó|está)\s+enfocad[ao]\b|"
        r"\bla\s+(?:traje|activé|puse\s+al\s+frente)\b|\b(?:i\s+)?(?:focused|brought)\b",
        re.IGNORECASE,
    ),
}


def _undenied_claim(pattern: re.Pattern[str], text: str) -> bool:
    """A claim of the effect the pattern names that no negation in its clause denies («no lo añadí»)."""

    stripped = text.strip()
    return any(
        _EFFECT_CLAIM_NEGATED.search(re.split(r"[.,;:!?¿¡]", stripped[:claim.start()].casefold())[-1]) is None
        for claim in pattern.finditer(stripped)
    )


def _deferred_clarification_for(user_text: str, situation: dict) -> object | None:
    """AUDIO858 H0067, H0527: the read the turn ran plus the question its final owes."""

    operation = situation.get("operation")
    if not isinstance(operation, str) or operation not in {"system.time", "window.resolve"}:
        return None
    if situation.get("verified") is not True or situation.get("succeeded") is not True:
        return None
    deferred = effect_intent.deferred_clarification_split(user_text or "", _DEFERRED_COMPOSE_OPERATIONS)
    if deferred is None:
        return None
    read = effect_intent.resolve_explicit_effects(deferred.read_text, _DEFERRED_COMPOSE_OPERATIONS)
    if read is None or read.operations != (operation,):
        return None
    return deferred


def _deferred_question_defect(text: str, deferred: object) -> str:
    """The final states the read and ends with the one question the other clause needs;
    the other clause's effect is never claimed."""

    stripped = text.strip()
    if _undenied_claim(_DEFERRED_EFFECT_CLAIMS[deferred.kind], stripped):
        return "extra_claim"
    sentences = [part for part in re.split(r"(?<=[.!?])\s+", stripped) if part.strip()]
    if not sentences or not sentences[-1].rstrip().endswith("?"):
        return "missing_deferred_question"
    if _DEFERRED_QUESTION_WORDS[deferred.kind].search(sentences[-1]) is None:
        return "missing_deferred_question"
    if stripped.count("?") > 1:
        return "too_many_sentences"
    return ""


def _without_deferred_question(text: str) -> str:
    """The trailing question is owed; the rest is judged as an operation final."""

    sentences = [part for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]
    if sentences and sentences[-1].rstrip().endswith("?"):
        sentences = sentences[:-1]
    return " ".join(sentences)


_RECALLED_AS_OWN = re.compile(
    r"^\W*(?:me\s+llamo|mi\s+nombre\s+es|me\s+gusta|me\s+encanta|mi\s+(?:bebida|color|ciudad|comida)\s+favorit[ao]\s+es|"
    r"my\s+name\s+is|i\s+like|i\s+love|i\s+am\s+called|i'm\s+called|my\s+favou?rite)\b",
    re.IGNORECASE,
)


def _denies_the_destination(folded_reply: str, folded_destination: str) -> bool:
    """True when the sentence that names the real destination negates the delivery
    to it. A truthful reply names the destination first and only then says it did
    not reach the person asked for («… a X, no al destinatario pedido»); a denial
    puts the negation before it («pero no llegó a X»). A dot inside the address
    («gmail.com») is not a sentence end."""

    if not folded_destination:
        return False
    for sentence in re.split(r"[;\n]|\.(?=\s|$)", folded_reply):
        position = sentence.find(folded_destination)
        if position < 0:
            continue
        if re.search(r"\b(?:no|not|never|nunca|tampoco|didn't|did\s+not)\b", sentence[:position]) is not None:
            return True
    return False


# The HTML elements (WHATWG) whose names a template hole could be confused with:
# «<iframe>» in a technical answer is markup, «<hora actual>» is a hole.
_HTML_ELEMENT_NAMES = frozenset(
    "abbr address area article aside audio base bdi bdo blockquote body button canvas caption cite "
    "code col colgroup data datalist del details dfn dialog div embed fieldset figcaption figure "
    "footer form head header hgroup html iframe img input ins kbd label legend link main map mark "
    "menu meta meter nav noscript object optgroup option output param picture pre progress ruby "
    "samp script search section select slot small source span strong style sub summary sup svg "
    "table tbody template textarea tfoot thead time title track var video wbr".split()
)


_PRESENT_ANCHOR = re.compile(
    r"\b(?:hoy|ahora|actualmente|today|now|currently|tonight|esta\s+noche|manana|tomorrow|ayer|yesterday|"
    r"dentro\s+de|a\s+partir\s+de\s+hoy|desde\s+hoy|from\s+(?:now|today)|este\s+(?:ano|mes)|esta\s+semana|"
    r"this\s+(?:year|month|week))\b"
)
_CALENDAR_WORDS = (
    r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre|"
    r"january|february|march|april|june|july|august|september|october|november|december|"
    r"lunes|martes|miercoles|jueves|viernes|sabado|domingo|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"
)
_PRESENT_CLAIM = re.compile(
    r"(?<![\w.,])\d+(?:[.,:/-]\d+)*(?!\w)|\b(?:" + _CALENDAR_WORDS + r")\b"
    # M77 (DEV-D v3l D-p27-t1 «Any good movies for me to watch?» → «…try the new space opera or the cozy mystery that's
    # been trending this week.»): with nothing read, what is trending, in fashion or most watched now is not known.
    r"|\b(?:trending|trends?|tendencias?|de\s+moda|viral|most\s+(?:watched|popular|streamed)|mas\s+(?:vist[oa]s?|"
    r"popular(?:es)?|escuchad[oa]s?)|top\s+(?:charts?|lists?)|number\s+one|numero\s+uno)\b"
)


def _unverified_present_fact(text: str, user_text: str, facts: dict) -> str | None:
    """A date, weekday or figure about now that no one said and nothing read.

    A conversation carries no observation: the calendar, the clock and today's
    figures are not known to it. A sentence anchored to the present («hoy»,
    «dentro de», «this week») may only restate what the person said, what the
    referenced previous answer said, or what this turn's situation observed.
    """

    said = _reading_fold(
        " ".join(
            (
                user_text or "",
                _referenced_previous_answer(user_text, facts),
                str(facts.get("situation") or ""),
            )
        )
    )
    for sentence in re.split(r"(?<=[.!?;])\s+|\n", _reading_fold(text)):
        if _PRESENT_ANCHOR.search(sentence) is None:
            continue
        for claim in _PRESENT_CLAIM.finditer(sentence):
            if re.search(r"(?<![\w.,])" + re.escape(claim.group(0)) + r"(?!\w)", said) is None:
                return claim.group(0)
    return None


def _names_forbidden_term(vocabulary: str, term: str) -> bool:
    """A7 E2 (FINAL t241): a jargon term ends where its word ends; «operacion» inside «operaciones básicas»
    (arithmetic) or «tool» inside «toolkit» go on into another word, while a name glued in front («XRouter») still
    says it. Twin of UserMessagePolicy.LeakedInternalTerm."""

    folded = term.casefold()
    if not folded:
        return False
    end = r"(?!\w)" if re.search(r"\w$", folded) else ""
    return re.search(re.escape(folded) + end, vocabulary.casefold()) is not None


def _said_misspelled(user_text: str, name: str) -> bool:
    """A7 E1 (FINAL t299 «ponme algo de luis miguel en spotfy»): the person named it with a typo; by the owner's rule
    (2026-09-19) what was misheard or mistyped BAXY repairs, so a reply that names it spelled right names what was
    said. A small edit distance against a word the person wrote, never a new name."""

    budget = 1 if len(name) <= 5 else 2
    return any(
        abs(len(word) - len(name)) <= budget and _edit_distance(word, name) <= budget
        for word in re.findall(r"[a-z0-9]+", fold(user_text or ""))
        if len(word) >= 4
    )


_ATTEMPTED_KEYS = frozenset({"target", "attempted"})


def _attempted_targets(situation: object, depth: int = 0) -> list[object]:
    """M134: what a result says it tried — the «target» and «attempted» of a failure or of its steps, decoded."""

    found: list[object] = []
    if depth > 8:
        return found
    if isinstance(situation, str) and situation.lstrip().startswith("{"):
        try:
            situation = json.loads(situation)
        except ValueError:
            return found
    if isinstance(situation, dict):
        for key, value in situation.items():
            if key in _ATTEMPTED_KEYS:
                found.append(value)
            else:
                found.extend(_attempted_targets(value, depth + 1))
    elif isinstance(situation, (list, tuple)):
        for value in situation:
            found.extend(_attempted_targets(value, depth + 1))
    return found


def _identifier_key(token: str) -> str:
    """An identifier compared without case or accents («cotización-pisos.pdf» is «cotizacion-pisos.pdf»)."""

    return fold(token)


def _observed_identifier_tokens(situation: dict) -> set[str]:
    """A7 E4 (DEV-A3 t103): a file name inside an observed window title («baxy-guardia.txt: Bloc de notas») is what
    was seen, not an internal code; only the observed values count, never the operation that read them.

    M134 (DEV-F v4i–v4l2 F-w22-t2 «great, can you summarize the lease PDF in there?», F-w24-t4, DEV-D D-w15-t3): the
    file a failed read tried («target»/«attempted»: «lease.pdf», «cotizacion-pisos.pdf», «informe_trimestral.txt») is
    the person's thing named back, not a contract code; every draft that said «no encontré lease.pdf en Descargas»
    died as internal_code and the turn ended in ⚠ in every round. Twin: ObservedResponseLiterals.ObservedIdentifierTokens."""

    tokens: set[str] = set()

    def walk(value: object, key: str = "") -> None:
        if key in {"operation", "operations", "authority", "windowId", "endpointIdHash"}:
            return
        if isinstance(value, str):
            tokens.update(_identifier_key(match) for match in _IDENTIFIER_TOKEN.findall(value))
        elif isinstance(value, dict):
            for child_key, child in value.items():
                walk(child, str(child_key))
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk(child, key)

    walk(_merged_observed(situation))
    walk(_attempted_targets(situation))
    operation = _identifier_key(str(situation.get("operation") or ""))
    tokens.discard(operation)
    return tokens


_REPEATED_WORD = re.compile(r"\b(\w+)(?:\s+\1){1,}\b")


def _observed_repeated_words(situation: dict) -> set[str]:
    """M172 (DEV-I v5b I-s049 «what's this song called?» over «Mi Buen Amor - Desde El Teatro Fru Fru»): the words a
    verified result observed already repeated («fru fru», «bora bora»), casefolded. Saying them is data, not a stutter.
    Twin: UserMessagePolicy.ObservedRepeatedWords."""

    words: set[str] = set()
    if situation.get("verified") is not True:
        return words

    def walk(value: object, depth: int = 0) -> None:
        if depth > 6:
            return
        if isinstance(value, str):
            words.update(found.group(1) for found in _REPEATED_WORD.finditer(value.casefold()))
        elif isinstance(value, dict):
            for child in value.values():
                walk(child, depth + 1)
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk(child, depth + 1)

    walk(_merged_observed(situation))
    return words


# Typed causes whose fact is that a source did not answer: saying so is the cause, not an invented non-answer.
_NON_ANSWER_CAUSES = frozenset({
    "download_source_unavailable", "weather_service_unavailable", "time_place_service_unavailable",
})


def _this_turn_resolved(situation: dict) -> bool:
    """Revisión 2 de la ronda 24 (r23 t2-c03 #3: the real final was a two-step plan told as ``{kind: status, cause:
    mission_completed, steps: [window.resolve, app.close]}``, with no ``verified`` nor ``succeeded`` on top): whether
    this turn's result resolved what was asked — a verified, succeeded operation, a mission that reached its goal, or
    a completed mission whose every step was verified and succeeded. Contracaso: a completed mission with a step that
    failed or was not verified, or with no step at all, resolved nothing that can be told."""

    if not isinstance(situation, dict):
        return False
    if situation.get("verified") is True and (
        situation.get("succeeded") is True
        or (isinstance(situation.get("observed"), dict) and situation["observed"].get("reached") is True)
    ):
        return True
    if str(situation.get("cause") or "").strip().lower() != "mission_completed":
        return False
    steps = _situation_steps(situation)
    return bool(steps) and len(steps) == len(situation.get("steps") or []) and all(
        step.get("verified") is True and step.get("succeeded") is True for step in steps
    )


def _verified_titled_item_write(situation: dict, operation: str, cause: str) -> bool:
    """A verified write of a task or a note, alone or as a step of a completed mission."""

    if (
        operation in _TITLED_ITEM_WRITES
        and situation.get("verified") is True
        and situation.get("succeeded") is True
    ):
        return True
    return cause == "mission_completed" and any(
        step.get("operation") in _TITLED_ITEM_WRITES
        and step.get("verified") is True
        and step.get("succeeded") is True
        for step in _situation_steps(situation)
    )


# M97: a span of time named in a timed mute's reply, and the words that say nothing brings the sound back by itself
# («hasta que me lo pidas», «no lo reactivo solo», «until you ask», «won't turn it back on»). Folded.
_TIMED_SPAN_WORD = re.compile(r"\b(?:horas?|minutos?|rato|ratito|hours?|minutes?|while)\b")
_NO_TIMER_SAID = re.compile(
    r"\b(?:hasta\s+que|until|no\s+(?:lo\s+|la\s+|el\s+sonido\s+)?(?:reactiv|vuelv|devuelv|activ|quit|desactiv|restaur)\w*|"
    r"(?:won'?t|will\s+not|do\s+not|don'?t|can'?t|cannot)\s+(?:\w+\s+){0,3}(?:back|unmute|restore|by\s+itself|on\s+my\s+own)|"
    r"no\s+tengo\s+(?:un\s+)?(?:temporizador|reloj)|no\s+(?:hay|pongo)\s+(?:un\s+)?temporizador|"
    r"(?:no|not)\s+(?:\w+\s+){0,3}(?:solo|sola|por\s+si\s+solo|by\s+itself|automatic\w*|automatica\w*))"
)


def own_voice_defect(text: str, said: str = "", *, act_report: bool = False, preterite_floor: bool = False) -> str:
    """A report of BAXY's own act that is not said in BAXY's voice (voice audit 2026-10-07): a misspelled first person
    preterite («Abrazé», «Andé»), the first person plural for what BAXY alone did («Ya estamos en…») or the
    peninsular perfect for a just-done act («Ya he entrado en…»). ``said`` holds the person's and the screen's words,
    which are theirs. The plural is judged only in the report of a verified act (``act_report``), where nobody but
    BAXY acted; elsewhere «estamos en la misma zona horaria» is the person and BAXY together. The perfect is vetoed
    only where a preterite floor stands behind the retries
    (``preterite_floor``: the computer-use mission); elsewhere «He guardado la nota» is still published. Returns the
    defect, or ""."""

    if semantic_voice_register.misspelled_own_preterite(text, said):
        return "misspelled_act"
    if act_report and semantic_voice_register.tells_own_act_in_plural(text, said):
        return "plural_own_act"
    if preterite_floor and semantic_voice_register.tells_own_act_in_peninsular_perfect(text, said):
        return "peninsular_perfect"
    return ""


def compose_visible_defect(
    text: str,
    intent: str,
    user_text: str,
    facts: dict,
    *,
    said: str | None = None,
) -> str:
    """Reject a composed reply that a person would read as a filled hole.

    ``said`` is the person's own message when it is known (the App judges the reply against it).

    Shipped entry for goal 06: polarity, no internal codes, no copied Spotify,
    no invented infinitives, no canned stall.
    """

    stripped = _strip_prompt_labels((text or "").strip())
    if not stripped:
        return "empty"
    situation_now = _situation_from_facts(facts) if isinstance(facts, dict) else {}
    held = situation_now.get("alreadyHolds") if isinstance(situation_now.get("alreadyHolds"), dict) else {}
    talk = "conversation" in {intent, situation_now.get("kind")}

    def repeats(previous: object) -> bool:
        return _repeats_the_last_answer(stripped, previous, said or user_text)

    # Uso real 2026-10-07 (M99; v3 t2 c03-2, c04-4): after a correction the last final is never told again, a failure's
    # included. A held count (the only held fact the writer words, encargo TZ-HOLD) gives the items in another shape,
    # never the last answer with «Ya» in front.
    if (talk or not held) and any(
        isinstance(again := situation_now.get(key), dict) and repeats(again.get("previousReply"))
        for key in ("sameResultAgain", "correctedFinal", "alreadyHolds")
    ):
        return "repeats_last_answer"
    corrected_final = situation_now.get("correctedFinal")
    if (
        isinstance(corrected_final, dict)
        and corrected_final.get("previousTurnActed") is False
        and _this_turn_resolved(situation_now)
        and dialogue_slot.opens_with_a_denial(stripped)
    ):
        # Ronda 24 (r23 t2-c03 #3 «no bro cerraste el que no era…» after a turn that only asked → «No, cerré la
        # ventana…»): this turn's act resolves what the person asks; a bare denial in front argues with a reproach
        # of a question. Contracaso: a turn whose act failed, or a last final that told an act, is not judged here.
        return "denies_the_correction"
    if semantic_listing.argues_the_count(stripped, said or user_text):
        # Revisión 2 de la ronda 24 (r23 t3-c17 t2: the drafts with the four causes died and the composed fallback
        # «Te di 3 elementos, no 7 ni 4.» was published): a count dispute is answered with the count asked, never
        # argued. Contracaso: «Ya te di 4, los que pediste» (the settled dispute) and a reply that lists the items.
        return "argues_the_count"
    if (
        situation_now.get("verified") is True
        and semantic_claims.unmatched_play(situation_now.get("operation"), _merged_observed(situation_now))
        and not semantic_claims.tells_unmatched_play(stripped)
    ):
        # Revisión 1 r24u (bloqueante 1, t2-c01 «Fother Muckers» told as «los bunkers»): what plays was not shown to
        # be the query (matchesQuery false); a reply that does not say so would read as the request done. The
        # result's own sentence says it (templateSuffices), so no draft is asked again.
        return "unmatched_play"
    prior_asked = facts.get("priorRequests") if isinstance(facts, dict) else None
    if (
        (intent == "conversation" or _situation_from_facts(facts).get("kind") == "conversation")
        and asks_for_code(
            user_text,
            tuple(item for item in prior_asked if isinstance(item, str)) if isinstance(prior_asked, list) else (),
        )
    ):
        # M50 (v3a-final F-w12-t1 «Aquí tienes la función: `def calcular_gastos(montos): …`» died as internal_code):
        # the code asked for is the content; the prose around it is judged as any reply. A reply that is only code
        # has nothing else to judge.
        stripped = requested_code_prose(stripped)
        if not stripped:
            return ""
    if visible_reply_is_a_fixed_stall(stripped):
        return "stall"
    if visible_reply_says_a_vulgarity(stripped, f"{user_text} {said or ''}"):
        # M97 (reserve es315): never a vulgarity the person did not say.
        return "vulgarity"
    if visible_reply_invents_a_spanish_infinitive(stripped) or visible_reply_breaks_word_case(
        # An observed name («watchOS» in a page title) is written as it was seen.
        stripped, f"{user_text} {json.dumps(facts, ensure_ascii=False, default=str)}",
    ) or visible_reply_breaks_spanish_plural(stripped, user_text) or visible_reply_cuts_a_word(stripped):
        return "invented"
    # A literal identifier supplied by the person (for example a filename)
    # is not leaked protocol metadata. Exempt only the same complete token
    # from the code-shape check; other content and all factual checks remain.
    identifier_sources = [user_text]
    prior_requests = facts.get("priorRequests")
    if isinstance(prior_requests, list):
        identifier_sources.extend(item for item in prior_requests if isinstance(item, str))
    user_identifiers = {
        _identifier_key(match)
        for source in identifier_sources
        for match in _IDENTIFIER_TOKEN.findall(source)
    } | _observed_identifier_tokens(_situation_from_facts(facts))
    vocabulary_text = without_observed_names(stripped, _situation_from_facts(facts))
    without_user_identifiers = _IDENTIFIER_TOKEN.sub(
        lambda match: "" if _identifier_key(match[0]) in user_identifiers else match[0],
        vocabulary_text,
    )
    if (
        _SNAKE_CODE.search(without_user_identifiers) is not None
        or _DOTTED_OP.search(_WEB_HOST.sub("", without_user_identifiers)) is not None
    ):
        return "internal_code"
    reported = _situation_from_facts(facts)
    if intent in {"status", "error"} and reported.get("kind") != "conversation":
        # M108: the report of a result names no contract token, and what was verified is never promised.
        if visible_reply_leaks_a_contract_token(stripped, reported, identifier_sources):
            return "internal_code"
        if identifier_is_plumbing(str(reported.get("operation") or "")) and visible_reply_says_an_internal_identifier(
            stripped, f"{user_text} {said or ''}"
        ):
            return "internal_code"
        if intent == "status" and _verified_effect(reported) and visible_reply_promises_the_act(stripped):
            return "promised_effect"
        if intent == "status" and _verified_effect(reported) and tells_own_act_as_the_persons(stripped):
            # Live 2026-10-07 (y5, x12): «Has abierto…», «Has iniciado…» — BAXY's verified act told as the person's.
            return "action_attributed_to_user"
        heard = f"{user_text} {said or ''} {json.dumps(facts, ensure_ascii=False, default=str)}"
        if voice_defect := own_voice_defect(
            stripped,
            heard,
            act_report=intent == "status" and _verified_effect(reported),
            preterite_floor=reported.get("operation") == "mission.computer.use",
        ):
            return voice_defect
    if re.search(r"</?think>", stripped, re.IGNORECASE) is not None:
        return "internal_code"
    if "el mensaje es" in stripped.casefold():
        return "internal_code"
    # Tanda 6b «El título observado es "…". El estado de reproducción es pausado.»: the words the prompt uses for a
    # read are not the person's; the song is named and its state said as a person would.
    if re.search(
        r"\b(?:t[ií]tulo|artista|estado)\s+observad[oa]s?\b|\bobserved\s+(?:title|artist|state|playback)\b|"
        r"\bestado\s+de\s+(?:la\s+)?reproducci[oó]n\b|\bplayback\s*status\b",
        stripped,
        re.IGNORECASE,
    ):
        return "internal_code"
    # Nombrar un campo del contrato es jerga: «la situación.greeting».
    if (
        re.search(
            r"situaci[oó]n\.[a-z]|situation\.[a-z]|\bseen\.[a-z]|\bobserved\.[a-z]",
            stripped,
            re.IGNORECASE,
        )
        is not None
    ):
        return "internal_code"
    # Una apertura que anuncia el idioma o los hechos habla del encargo, no del
    # turno: «En español, la frase es: ...», «The facts are: ...».
    if _META_OPENING.match(stripped) is not None:
        return "copied_instruction"
    if _TASK_METADISCOURSE.search(stripped) is not None:
        return "copied_instruction"
    if _FAILURE_AS_TOPIC.match(stripped) is not None:
        return "failure_as_topic"
    # cien-39 072 «de qué te ocupas en este PC» → «Me ocupó abrir y cerrar
    # programas…»: tercera persona del pretérito donde va la primera del
    # presente. Dice que algo le ocupó a BAXY, no de qué se ocupa.
    if re.search(
        r"(?<![a-záéíóú])me\s+(?:ocup|encarg|dedic|enfoc)[oó]\s+"
        r"(?:a\s+)?[a-záéíóú]+(?:ar|er|ir)\b",
        stripped,
        re.IGNORECASE,
    ) is not None or visible_reply_breaks_first_person(stripped):
        return "broken_person_conjugation"
    if visible_reply_breaks_estar_participle(stripped):
        return "broken_estar_participle"
    # Un hueco por rellenar no es una respuesta: «La hora actual es [hora
    # actual en español].» (conocimiento-3/t3).
    placeholder = re.search(r"\[[^\]]{3,}\]|\{[^}]{3,}\}|<[a-z ]{3,}>", stripped)
    # H0463: un informe de busqueda cita el JSON que trae el fragmento del
    # resultado ({"620": {"success":true, ...}}). Un hueco de plantilla se
    # escribe con palabras; un objeto JSON empieza por comilla o trae «":».
    # Sin esta salvedad los tres candidatos caian en copied_instruction y el
    # turno terminaba sin respuesta.
    if placeholder is not None and re.match(
        r"\{\s*\"|\{[^}]*\"\s*:", placeholder.group(0)
    ) is not None:
        placeholder = None
    # Uso real tanda 2 «¿Cómo incluir un archivo HTML en otro HTML?»: «<iframe>»
    # names a markup element, the answer itself; a template hole is a phrase.
    if placeholder is not None and placeholder.group(0)[1:-1] in _HTML_ELEMENT_NAMES:
        placeholder = None
    if placeholder is not None and not _bracket_is_observed(placeholder.group(0), facts):
        # MAIL1853 «escribile un mail a [EMAIL_REDACTED]»: a bracket the person
        # wrote themselves, in this turn or in an earlier request of the same
        # dialogue, is their own word, not a template hole left unfilled.
        bracket = placeholder.group(0).casefold()
        if not any(
            isinstance(source, str) and bracket in source.casefold()
            for source in identifier_sources
        ):
            return "copied_instruction"
    # `can` es lo que hace BAXY. Atribuírselo a la persona invierte el actor:
    # «Puedes abrir y cerrar programas…» ante «qué puedes hacer en este PC».
    if _looks_like_capability_question(user_text) and re.match(
        r"\s*(?:puedes|tú puedes|tu puedes|usted puede|you can|you are able)\b",
        stripped,
        re.IGNORECASE,
    ):
        return "wrong_actor"
    if (
        "usar esa respuesta" in stripped.casefold()
        or "unusable answer" in stripped.casefold()
    ):
        return "internal_code"
    if "unclear" in stripped.casefold():
        return "internal_code"
    if (
        "entender la solicitud" in stripped.casefold()
        or "borrador anterior" in stripped.casefold()
        or "previous draft" in stripped.casefold()
    ):
        return "internal_code"
    if (
        "borrador del welcome" in stripped.casefold()
        or "welcome con exito" in stripped.casefold()
        or "welcome con éxito" in stripped.casefold()
    ):
        return "internal_code"
    if (
        "error de composicion" in stripped.casefold()
        or "error de composición" in stripped.casefold()
    ):
        return "internal_code"
    if (
        "understand the situation" in stripped.casefold()
        or "understand the task" in stripped.casefold()
        or "respond in english as" in stripped.casefold()
        or "draft was closed" in stripped.casefold()
        or "situacion del turno" in stripped.casefold()
        or "situación del turno" in stripped.casefold()
        or "responder en español" in stripped.casefold()
        or "responder en espanol" in stripped.casefold()
        or "con una frase" in stripped.casefold()
        or "dato adicional" in stripped.casefold()
        or "no tengo acceso" in stripped.casefold()
        or "idioma obligatorio" in stripped.casefold()
        or re.search(r"\bjson\b", stripped.casefold()) is not None
    ):
        return "internal_code"
    if re.search(r"\bsoy by\b", stripped.casefold()) is not None:
        return "invented"
    if re.search(r"\bqwen\b", vocabulary_text.casefold()) is not None:
        return "internal_code"
    if "baxy is at" in stripped.casefold():
        return "extra_claim"
    if (
        _looks_like_capability_question(user_text)
        and re.match(
            r"\s*(?:hola|hello|hi\b|hey\b|buenos|buenas)\b",
            stripped,
            re.IGNORECASE,
        )
        # «Hola, ¿qué puedes hacer?» pide un saludo y una respuesta: el saludo
        # delante no es el defecto, quedarse sólo en el saludo sí lo es.
        and (not read_request(user_text).greets or read_request(stripped).greeting_only)
    ):
        return "knowledge_greeting"
    if "teá" in stripped:
        return "invented"
    if _looks_like_knowledge_question(user_text) and re.search(
        r"\b(?:illegal|unethical|ethical|malicious|ilegal|"
        r"legal requirements?|guidelines|safety polic|harmful)\b",
        stripped.casefold(),
    ):
        return "extra_claim"
    if _looks_like_refuse_question(user_text) and re.search(
        r"cannot refuse|can't refuse|can not refuse|will not refuse|"
        r"won't refuse|refuse nothing|no puedo rechazar|\bno rechazo\b",
        stripped.casefold(),
    ):
        return "reversed_result"
    if _looks_like_refuse_question(user_text) and re.search(
        r"\b(?:\d+\s*gb|\bram\b|memory (?:limit|capacity)|maximum ram)\b",
        stripped.casefold(),
    ):
        return "extra_claim"
    if _looks_like_refuse_question(user_text):
        folded_refuse = stripped.casefold()
        if (
            re.search(
                r"i don't do that|i do not do that|eso no lo hago",
                folded_refuse,
            )
            is None
        ):
            # Un límite se responde negando («I will never …») o restringiéndose
            # («Sólo hago lo de este PC, nada más»). Exigir sólo la negación, y
            # además un verbo de una lista cerrada, agotó cuatro composiciones
            # correctas seguidas en panel-opus-3.
            # cien-36 023/082 «qué no haces» → «Sólo hago lo que este PC me
            # ordena»: the machine orders nothing and BAXY obeys no machine;
            # the person is the one who asks. That sentence reads as obedience
            # to the PC, which is false, so it is not publishable.
            if re.search(
                r"\b(?:este\s+)?(?:pc|computadora|ordenador|equipo|maquina)\b[^.]{0,30}"
                r"\b(?:me\s+)?(?:ordena|ordene|manda|mande)\b|"
                r"\b(?:me\s+)?(?:ordena|ordene|manda|mande)\s+(?:este\s+)?"
                r"(?:pc|computadora|ordenador|equipo|maquina)\b|"
                r"\b(?:this\s+)?(?:pc|computer|machine)\s+(?:orders|tells|commands)\s+me\b|"
                r"\b(?:what|lo\s+que)\s+(?:this\s+|este\s+)?(?:pc|computer|machine)\s+"
                r"(?:orders|tells|commands|ordena|manda)\b",
                folded_refuse,
            ) is not None:
                return "obeys_the_machine"
            restricts = any(marker in folded_refuse for marker in _SCOPE_MARKERS)
            negates = (
                re.search(
                    r"i don't do|i do not do|don't do that|"
                    r"\bi won't\b|\bi will not\b|\bi will never\b|\bi never\b|"
                    r"\bi cannot\b|\bi can't\b|no puedo|\bno hago\b|\bnunca\b",
                    folded_refuse,
                )
                is not None
            )
            if not negates and not restricts:
                return "extra_claim"
            if not restricts and not _names_a_served_act(folded_refuse, facts):
                return "extra_claim"
    if (
        re.search(r"\b(?:ethernet|interfaces conectadas)\b", stripped.casefold())
        is not None
    ):
        return "extra_claim"
    if "de la sala" in stripped.casefold() or "of the room" in stripped.casefold():
        return "extra_claim"
    if "seen you" in stripped.casefold() or "he visto" in stripped.casefold():
        return "extra_claim"
    situation = _situation_from_facts(facts)
    asked = re.sub(r"[¿?¡!.]", "", (user_text or "").casefold()).strip()
    answered = re.sub(r"[¿?¡!.]", "", stripped.casefold()).strip()
    asked_lead = re.sub(
        r"^(?:dime|dame|decime|tell me|give me)\s+",
        "",
        asked,
    )
    if (
        len(asked) >= 12
        and answered
        and (
            answered == asked
            or (
                answered == asked_lead
                and (
                    not _looks_like_greeting_ask(stripped)
                    or _looks_like_knowledge_question(user_text)
                )
            )
        )
        and intent != "welcome"
        and not _looks_like_greeting_ask(user_text)
    ):
        observed_open = situation.get("observed")
        opened_name = (
            observed_open.get("displayName") if isinstance(observed_open, dict) else None
        )
        # An imperative and its completed first-person report can have the same
        # spelling. Exempt only this echo, bound to the verified complete name;
        # any nominal qualifier is already present in the identical request.
        completed_open_echo = (
            answered == asked
            and situation.get("kind") == "operation"
            and situation.get("operation") == "app.open"
            and situation.get("polarity") == "success"
            and situation.get("verified") is True
            and situation.get("succeeded") is True
            and isinstance(opened_name, str)
            and bool(opened_name.strip())
            and "?" not in stripped
            and "¿" not in stripped
            and re.fullmatch(
                r"(?:(?:yo\s+)?abrí|i\s+(?:have\s+)?opened)\s+"
                r"(?:(?:el|la|the)\s+)?"
                + re.escape(opened_name.strip())
                + r"(?:\s+(?:de|of)\s+\w+)?\.?",
                stripped,
                re.IGNORECASE,
            ) is not None
        )
        if not completed_open_echo:
            return "extra_claim"
    if re.search(
        r"i'm baxy|im baxy|i am baxy|soy baxy|living on the pc|vive en el pc",
        stripped.casefold(),
    ) and (
        "system.time" in json.dumps(facts or {}, ensure_ascii=False).casefold()
        or asks_the_clock(user_text)
    ):
        return "extra_claim"
    if "cannot provide" in stripped.casefold():
        return "invented"
    if (
        "i'm happy to help" in stripped.casefold()
        or "im happy to help" in stripped.casefold()
    ):
        return "internal_code"
    if "no está clara" in stripped.casefold() or "no esta clara" in stripped.casefold():
        return "internal_code"
    if "borrador no cumple" in stripped.casefold():
        return "internal_code"
    # M79 (DEV-D v3m w19-t4, w09-t3): the cause code «external_effect_ambiguous» said in words is still the code.
    if re.search(
        r"\b(?:efecto|fallo|error)\s+externo\b|\bexternal\s+(?:effect|failure|error)\b|\befecto\s+(?:es\s+)?ambiguo\b|"
        r"\beffect\s+(?:is\s+|was\s+)?ambiguous\b",
        _reading_fold(stripped),
    ) is not None and "extern" not in _reading_fold(user_text or ""):
        return "internal_code"
    if (
        re.search(
            r"\b(?:tengo internet|i have internet|"
            r"i(?:'m| am|m)(?: not)? connected|"
            r"i(?:'m| am|m)(?: not)? online|"
            r"estoy conectado|no estoy conectado|estoy online)\b",
            stripped.casefold(),
        )
        is not None
    ):
        return "wrong_actor"
    if _looks_like_negative_constraint(user_text) and re.search(
        r"i don't do that|i do not do that|eso no lo hago|"
        r"no puedo ayudarte|no puedo abrir|cannot open|can't open|"
        r"couldn't open|unable to open",
        stripped.casefold(),
    ):
        return "reversed_result"
    if (
        "definido, una frase" in stripped.casefold()
        or "definido una frase" in stripped.casefold()
    ):
        return "internal_code"
    if _looks_like_knowledge_question(user_text) and re.match(
        r"\s*(?:configur[oe]|defino|pongo|ajusto|i (?:set|configure|define|adjust))\b",
        stripped,
        re.IGNORECASE,
    ):
        return "copied_instruction"
    user_folded = (user_text or "").casefold()
    if ("traduce" in user_folded or "translate " in user_folded) and (
        "al español" in user_folded
        or "al espanol" in user_folded
        or "to spanish" in user_folded
    ):
        reply_folded = stripped.casefold().strip(" .!?¡¿")
        if (
            reply_folded in {"hi", "hello", "hey"}
            or reply_folded.startswith(("hi,", "hello,", "hi i"))
            or "i'm baxy" in reply_folded
            or "im baxy" in reply_folded
        ):
            return "wrong_language"
        if "puedo ayudarte" in reply_folded or "en qué puedo" in reply_folded:
            return "extra_claim"
        if "good morning" in user_folded and not any(
            token in reply_folded for token in ("buenos", "días", "dias")
        ):
            return "extra_claim"
        if "good night" in user_folded and "noches" not in reply_folded:
            return "extra_claim"
        if re.search(r"translates to|in spanish is|wait,", reply_folded):
            return "extra_claim"
    if _looks_like_continue_constraint(user_text) and re.search(
        r"eso no lo hago|i don't do that|i do not do that|no puedo ayudar",
        stripped.casefold(),
    ):
        return "asserted_failure"
    if (
        _looks_like_ambiguous_action(user_text)
        and "?" not in stripped
        and "¿" not in stripped
        # M109 (DEV-D v4d D-p24-t4): the act said not done, with why, answers «do it» (twin of the App's check).
        and not dialogue_slot.says_not_done_and_why(stripped)
    ):
        return "clarification_not_a_question"
    if (
        "significa exactamente" in stripped.casefold()
        or "en este contexto" in stripped.casefold()
    ):
        return "internal_code"
    if "hecho ya ocurrido" in stripped.casefold():
        return "copied_instruction"
    # Bind a third-person subject to narration of the request. User/account
    # nouns also occur in direct answers and must not be banned by themselves.
    if re.search(
        r"\b(?:(?:al|del|el|la|este|esta|ese|esa)\s+(?:usuario|usuaria|persona)|"
        r"(?:the|this|that)\s+(?:user|person|requester))\s+"
        r"(?:le gustaria|le interesa|quiere|quisiera|desea|prefiere|pidio|ha pedido|"
        r"pregunto|dijo|saludo|solicito|menciono|se refiere|would like|wants|asked|said|"
        r"greeted|requested|mentioned|prefers|has asked|is referring)\b",
        _policy_guard_text(stripped),
    ) is not None:
        return "internal_code"
    if visible_reply_speaks_of_the_person(stripped, user_text):
        return "third_person_addressee"
    if (
        re.search(r"\b(?:cannot|can't|can not)\s+[a-z]+ing\b", stripped.casefold())
        is not None
    ):
        return "invented"
    if _looks_like_knowledge_question(user_text) and re.search(
        r"\b(?:central european|pacific time|eastern time|\bcet\b|utc\s*[+-]\s*\d+)\b",
        stripped.casefold(),
    ):
        return "invented"
    polarity = str(situation.get("polarity") or "").strip().lower()
    kind = str(situation.get("kind") or intent).strip().lower()
    cause = str(situation.get("cause") or "").strip().lower()
    operation = str(situation.get("operation") or "").strip().lower()
    if cause == "clarification_cancelled" and (cancelled := cancelled_clarification_defect(stripped)):
        return cancelled
    # Uso real 2026-09-25 (tanda 8): the App's conversation fallback composed «Sí, está lista
    # para recoger.» for «está mi orden lista para recoger ya» from the bare situation
    # {"kind":"conversation"}. A message composed where no operation ran carries the same
    # contract as the mind's conversation reply: nothing done, read or observed is said.
    # A failure is one only when it is the limit («out_of_catalog»): a timeout or a failed mission ran something.
    # A welcome keeps its own opener check.
    ran_nothing = not (operation or situation.get("reason") or situation.get("steps")) and (
        kind in {"conversation", "clarification"} or (kind == "failure" and cause == "out_of_catalog")
    )
    if ran_nothing and cause != "acting":
        prior = facts.get("priorRequests")
        if (
            kind == "conversation"
            and dialogue_slot.go_ahead_with_nothing_pending(said or user_text, str(facts.get("context") or ""))
            and _go_ahead_reply_unmet(stripped, said or user_text)
        ):
            # M88 (DEV-D v3r D-p24-t5 «I confirm the action will proceed.»): a go-ahead nothing was waiting for, in a
            # turn that ran nothing, is answered by saying it was not done — whatever words the draft uses otherwise.
            # M105: judged before the world claims, whose generic hint would hide this one.
            return "go_ahead_not_done"
        if kind == "conversation" and _contradicts_previous_count(stripped, facts):
            # Uso real v3 tanda 2 «Solo te proporcioné dos recetas de pollo en lugar de cinco.» after five ideas.
            return "contradicts_previous_answer"
        world_claim = conversation_world_claim(
            stripped, user_text, tuple(str(item) for item in prior if isinstance(item, str))
            if isinstance(prior, list) else (),
        )
        if world_claim == "effect_claim" and intent == "error" and not (
            _asserts_failure(stripped) or _names_the_boundary(stripped.casefold())
        ):
            # M139 × the out-of-catalog contract: an error turn whose draft claims the act and tells no failure nor
            # limit («Claro, ya la reservé.») wants the failure said (its hint), not only the effect forbidden.
            return "missing_failure"
        if world_claim:
            return world_claim
        if kind == "conversation" and _says_the_person_back(stripped, said or user_text):
            # M85 (DEV-D v3o D-p27-t5 «Nope, that's a lot.» → «That is a lot.»).
            return "echo"
        if kind == "conversation" and _misses_content_shape(stripped, said or user_text):
            # M85 (DEV-D v3o D-p32-t2, D-p36-t2): a list, a table or dialogue lines asked and not written so.
            return "content_shape"
        if (
            kind == "conversation"
            and not asks_for_code(said or user_text, ())
            and _conversation_presentation_shape(
                said or user_text, conversation_kind="knowledge", has_history=bool(prior),
            ) is None
        ):
            # M95 (D52; DEV-D D-p28-t3): the conversation message composed where nothing was read is held to the mind's
            # talk rule: no figure from memory that the conversation does not state.
            earlier = [str(item) for item in prior if isinstance(item, str)] if isinstance(prior, list) else []
            # Ronda 24 (r23 t4-c04 «El brillo ya está al 40…» vetoed though the last answer said «al 40»): what the
            # state carries as already said (alreadyHolds, correctedFinal, undoNothing) is stated in the
            # conversation. Contracaso: a year no fact carries is still a figure from memory.
            stated = [
                str(value)
                for key in ("alreadyHolds", "correctedFinal", "undoNothing")
                if isinstance(situation, dict) and isinstance(situation.get(key), dict)
                for value in situation[key].values()
                if isinstance(value, str)
            ]
            if talk_memory_figures(
                stripped, said or user_text, [*earlier, *stated, str(facts.get("context") or ""), user_text], earlier,
            ):
                return "memory_figures"
    blob = f"{user_text} {json.dumps(situation, ensure_ascii=False)}".casefold()
    folded = stripped.casefold()
    if (
        kind == "operation"
        and operation == "audio.mute"
        and polarity == "success"
        and asks_a_timed_silence(said or user_text)
        and _TIMED_SPAN_WORD.search(_reading_fold(stripped)) is not None
        and _NO_TIMER_SAID.search(_reading_fold(stripped)) is None
    ):
        # M97 (reserve, MASSIVE audio_volume_mute «silencia por dos horas»): nothing gives the sound back when the span
        # ends; «Silencié el audio por dos horas» promises a timer nobody set.
        return "timed_mute_promised"
    # Un destino que ya estaba en ejecución no lo abrió este turno (APPS1029 «Abrí Steam.» sobre un proceso que
    # llevaba horas vivo): desde la estabilización F lo dice el suelo antes de cualquier borrador (dato
    # «unchanged» de app.open en operation_floor.v1.json), así que ese veto y su pista se retiraron.
    if (
        kind == "operation"
        and operation == "app.open"
        and polarity == "success"
    ):
        already_running = _app_open_was_already_running(situation)
        # La dirección espejo, que REPAIR1032 destapó en H0575: con el recibo
        # diciendo alreadyRunning=false, «Ya tengo la calculadora abierta.» da por
        # anterior un estado que este turno acaba de crear.
        if not already_running and _claims_the_target_was_open_before(folded):
            return "invented_prior_open_state"
        # M65 (conv-v3g owner script t37 «He abierto Steam y he entrado en la biblioteca.»): app.open opens the
        # application or brings it forward, nothing inside it; a section entered, a click or a page gone to was not
        # this operation's and nothing observed it.
        if re.search(
            r"\b(?:(?:he|hemos)\s+(?:entrado|ido|navegado|hecho\s+clic|pulsado|abierto\s+(?:la|el)\s+(?:secci[oó]n|"
            r"pestaña|biblioteca|men[uú]))|entr[eé]\s+(?:a|al|en)\b|fui\s+a\b|hice\s+clic|puls[eé]\b|"
            r"(?:i\s+)?(?:went|navigated|clicked|entered)\b)",
            folded,
        ):
            return "extra_claim"
    # Review r10a finding 6, review of its fix: the front window already showed the page before the link and no
    # window changed (authority «user_browser_front_already_showed»). «Abrí…» tells an opening nobody saw, and «ya
    # estaba abierta» is the fact, not an invented prior state (the deterministic final says it).
    already_shown = (
        kind == "operation"
        and operation in {"browser.navigate", "browser.navigate.named"}
        and polarity == "success"
        and _merged_observed(situation).get("authority") == _ALREADY_SHOWN_AUTHORITY
    )
    if already_shown and (
        (_claims_it_performed_the_open(folded) and not _states_it_was_already_running(folded))
        or _claims_a_relaunch(folded)
    ):
        return "unstated_already_shown"
    # WEB1261: «Ya fui a YouTube. La página ya estaba abierta.» gave a verified
    # navigation from about:blank a prior state it never had.
    if (
        kind == "operation"
        and not already_shown
        and operation in {"browser.navigate", "browser.navigate.named", "streaming.navigate"}
        and polarity == "success"
        and (
            _claims_the_target_was_open_before(folded)
            or re.search(
                r"\b(?:ya\s+estabas?\s+(?:en|ahi|alli)|ya\s+te\s+encontrabas\s+en|"
                r"you\s+were\s+already\s+(?:on|at|in)|already\s+(?:on|at)\s+the)\b",
                folded,
            ) is not None
        )
    ):
        return "invented_prior_open_state"
    if _clock_only_from_situation(situation) and re.search(
        r"\bbaxy\b|confianza|sigue adelante|t[uú] eres|"
        r"parte de esta|te dice|responsable|cuidar lo que",
        folded,
    ):
        return "extra_claim"
    if "spotify" in folded and "spotify" not in blob and not _said_misspelled(user_text, "spotify"):
        return "unmentioned_name"
    # M146 (DEV-G v4p/v4q G-s087 «resúmeme el pdf del contrato de alquiler que tengo en documentos», file absent):
    # «No pude leer el contrato de alquiler porque el archivo no se encontró en la carpeta documentos.» died three
    # times here and the turn ended in ⚠. «contrato» is the prompt's word for its own contract, but a word of this
    # list the person said is theirs (the same exemption as the prompt echo below); everything else still counts. Their
    # own message when it is known, not the request as the model understood it (H-w37-t1 below).
    said_folded = (said or user_text or "").casefold()
    if any(
        found.group(0) not in said_folded
        for found in re.finditer(
            r"observable state|observed state|observed status|"
            r"\bthe status is\b|"
            r"\bstatus update\b|\bstatus:\s*success\b|\bpolarity\b|"
            r"request analysis|failure in request|"
            # Fase 3.5 (corpus A/C: «Sí, pero el análisis de la solicitud falló»):
            # the cause code request_analysis_failed read aloud in Spanish.
            r"an[aá]lisis de (?:la|tu) (?:solicitud|petici[oó]n)|an[aá]lisis del pedido|"
            r"(?:la|tu) solicitud fall[oó]|el an[aá]lisis fall[oó]|"
            r"one english sentence|^una frase\b|\bcontrato\b|"
            r"responder en espa|con una frase|dato adicional|no tengo acceso|"
            r"idioma obligatorio|mandatory language|situacion del turno|"
            r"situación del turno|segun la situacion|según la situación",
            folded,
        )
    ):
        return "internal_code"
    if "estado observable" in folded or re.search(
        r"\bel estado es\b|\bthe state is\b", folded
    ):
        return "internal_code"
    if cause == "timeout" and "trajo" in folded:
        return "invented"
    # Two observed windows titled «Configuración» on consecutive list lines
    # are data, not a stutter (WINDOWS1209/000). M172: so is a word the verified result observed repeated
    # («"Mi Buen Amor - Desde El Teatro Fru Fru"», quoted in part or reordered, which the whole-name mask misses).
    repeated = {found.group(1) for found in _REPEATED_WORD.finditer(vocabulary_text.casefold())}
    if repeated and not repeated <= _observed_repeated_words(situation):
        return "invented"
    if re.match(r"^\s*(?:say|di|use|usa)\b", folded):
        return "copied_instruction"
    # Vocabulario que sólo aparece en el encargo… salvo cuando la persona lo
    # usa. «keep talking without launching anything» se contesta diciendo «I
    # will keep talking without launching anything», y «keep talking» está en
    # esta lista: el turno se agotaba seis veces seguidas por acertar
    # (limites-21/009). Misma exención que los términos prohibidos.
    prompt_echo = re.search(
        r"observed\.app|name every observed|menciona cada|título o paso|"
        r"nombre la nota|must appear|debe aparecer|the seen app|"
        r"note title must|observed app|progress only|progress continues|"
        r"no listo|^no (?:open|closed)[.!]?$|name the window|state closed|"
        r"one sentence of progress|una frase de que sigues|still in progress|"
        r"without the result|sin el resultado|progress, without|"
        r"in progress, without|no result claimed|without claiming|"
        r"name mute state|name what is in seen|do not invert|"
        r"name the pc network|not yourself|name seen\.online|"
        r"pc network name|specify the pc network|"
        r"in one short sentence|stay in the conversation|"
        r"keep talking|received the instruction|"
        r"required response|one short sentence of the facts|"
        r"understand the facts|name the local clock|^name the |"
        r"do not introduce yourself|do not describe presence|"
        r"observed\.muted|state muted matching|^progreso\.?$|"
        r"^muted\.?$|^unmuted\.?$|wait ended|mission unfinished|"
        # SCREEN1807: the screen-text lens sentence copied as the reply.
        r"cita cada una de esas l[ií]neas|quote each of those lines|"
        r"escribe a continuaci[oó]n las l[ií]neas|write the lines of seen|l[ií]neas de seen\.lines|"
        r"l[ií]neas y escribe:|lines and (?:then )?writes?:|"
        # M78 (DEV-D v3l w20-t4 «…no se puede determinar sin información adicional en los datos de situation»): the
        # facts' own field names are the machinery, not what the person is told.
        r"datos de (?:la )?situation|(?:the )?situation data|datos de seen|(?:the )?seen data",
        folded,
    )
    if (
        prompt_echo is not None
        and prompt_echo.group(0) not in (user_text or "").casefold()
    ):
        return "copied_instruction"
    # An observed window title on its own list line («MainWindowView»,
    # «Configuración») is data, not an invented word (WINDOWS1209/000).
    if re.search(r"(?m)^[a-z]{8,}$", vocabulary_text.casefold()):
        return "invented"
    for word in re.findall(
        r"\b\w*(?:ventana[a-záéíóúñ]{2,}|window[a-z]{2,})\w*\b", folded
    ):
        if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", blob) is None:
            return "invented"
    if (
        re.search(r"\bproviders?\b", folded)
        and "provider" not in (user_text or "").casefold()
    ):
        return "internal_code"
    # SCREEN1421: a screen line quoted verbatim may itself read «"key": false»;
    # observed text is data, so these code shapes are judged on the masked copy.
    if re.search(r":\s*(?:true|false)\b", vocabulary_text.casefold()) is not None:
        return "internal_code"
    if re.search(r"localTime|stepCount", vocabulary_text):
        return "internal_code"
    if _glued_proper_name(stripped, situation, user_text):
        return "invented"
    if re.search(r"\bya terminado\b", folded) and "ha terminado" not in folded:
        return "invented"
    language = _conversation_response_language(user_text, facts)
    if language in {"es", "en"} and _addressed_to_the_person(intent, _situation_from_facts(facts)):
        # M99 (DEV-D v3x D-w15-t3): the question back is judged in the language the person speaks; M134: the failure
        # told too.
        language = addressed_language(said or user_text, language)
    # El idioma de la respuesta se lee con el mismo owner que fija el del turno,
    # y sólo se veta cuando la evidencia del texto es de un solo idioma: «I will
    # not open any programs.» ante un pedido español pasaba los dos literales de
    # abajo (panel-opus-2/027), y «Yes.» no debe vetarse por no traer evidencia.
    # Observed window titles keep their own language: an English list of
    # Spanish-titled windows is not a Spanish reply (WINDOWS1211/007).
    if _reply_uses_opposite_language(vocabulary_text, language):
        return "wrong_language"
    if language == "en" and re.search(
        r"\b(?:listo|no pude|eso no lo hago|hola|encontré|agotó|"
        r"buenos|puedo|días|dias)\b",
        vocabulary_text.casefold(),
    ):
        return "wrong_language"
    if language == "es" and re.search(
        r"\bstill\b|\bworking\b|\bcouldn't\b|\bcould not\b", vocabulary_text.casefold()
    ):
        return "wrong_language"
    if language == "es" and _english_pc_nouns(vocabulary_text):
        return "english_word"
    if visible_reply_breaks_article_agreement(vocabulary_text):
        return "wrong_gender"
    failure_assertions = stripped
    if kind == "conversation":
        # M85 (DEV-D v3o D-p36-t2): what the characters of a written dialogue say, inside quotes, is theirs, not BAXY's
        # («Ash: "No puedo dejarlo ir."»). Twin of UserMessagePolicy.WithoutQuotedSpeech.
        failure_assertions = without_quoted_speech(failure_assertions)
    presence = _merged_observed(situation)
    if (
        str(situation.get("operation") or "").startswith("media.")
        and situation.get("verified") is True
        and situation.get("succeeded") is True
        and isinstance(presence, dict)
    ):
        # MUSIC1749: the observed title is not a statement about the outcome
        # («… Can't Stop …» is the song, not a failure). M140 (DEV-G v4o G-s099 «skip esta cancion» → «Está sonando MC
        # Hammer - U Can't Touch This.» died as asserted_failure three times): the song a control or a status read
        # observed is the song too.
        for key in ("title", "artist"):
            value = presence.get(key)
            if isinstance(value, str) and value.strip():
                failure_assertions = re.sub(
                    r"\s+".join(re.escape(part) for part in value.split()),
                    " ", failure_assertions, flags=re.IGNORECASE,
                )
    if (
        situation.get("operation") in {"web.search", "web.news.headlines"}
        and situation.get("verified") is True
        and situation.get("succeeded") is True
        and isinstance(presence, dict)
        and isinstance(presence.get("results") or presence.get("headlines"), list)
    ):
        # H0060 «me falla mucho whatsapp … porqué suele fallar»: the pages found
        # are about failures, so the words they carry («fallos», «no funciona»,
        # «cortes») are observed data when the reply repeats them, not a
        # statement about the search. Only words the results carry are masked;
        # «no pude» and the other markers of an own failure stay in the lens.
        failure_assertions = _without_observed_search_vocabulary(
            _without_memory_notice(failure_assertions) if situation.get("operation") == "web.search"
            else failure_assertions,
            presence,
        )
    elif (
        situation.get("kind") == "failure"
        and isinstance(situation.get("reason"), dict)
        and situation["reason"].get("operation") == "web.search"
    ):
        # M87 × M88 (DEV-D v3r D-s111): the answer from memory also follows a search whose results did not answer
        # (web_search_results_irrelevant); its D35 notice is the scope of that read there too, not a failure claim.
        failure_assertions = _without_memory_notice(failure_assertions)
    if (
        polarity == "success"
        and _failure_is_an_asked_state_held(situation)
        and _ALREADY_STATEMENT.search(_accent_folded_with_punctuation(stripped)) is not None
    ):
        # M139 (DEV-G v4n G-s021 «bro abre Discord y mutea el micro…», the microphone already muted): in a completed
        # mission, «el micrófono ya estaba silenciado, así que no hubo cambio» tells the state of the step that found
        # it already so (nothing attempted, nothing changed), not a failed mission; three drafts died as
        # asserted_failure or for want of the opening and the turn ended in ⚠. Twin: UserMessagePolicy
        # WithoutHeldStepUnchanged.
        failure_assertions = re.sub(
            r"\b(?:no\s+(?:se\s+)?cambi[oóeé]\s+nada|no\s+hubo\s+(?:ning[uú]n\s+)?cambios?|nada\s+cambi[oó]|"
            r"nothing\s+(?:was\s+)?changed|no\s+change\s+was\s+made|there\s+(?:was|were)\s+no\s+changes?)\b",
            " ",
            failure_assertions,
            flags=re.IGNORECASE,
        )
    empty_file_query = _verified_empty_known_file_query(situation)
    if empty_file_query is not None:
        # A successful empty search proves a negative finding, not a failed
        # execution. Mask only its query-bound predicate in this failure lens.
        # Keep every qualifier and independent assertion for the normal checks;
        # no whole-sentence wording or scope vocabulary grants an exemption.
        name = re.escape(_accent_folded_with_punctuation(empty_file_query))
        target = rf"[\"'«»“”‘’]?(?<!\w){name}(?!\w)[\"'«»“”‘’]?"
        determiner = r"(?:(?:el|un|ningun|ninguno|the|a|any)\s+)?"
        object_name = rf"{determiner}(?:(?:archivo|file)\s+)?(?:(?:llamado|named)\s+)?{target}"
        finding_predicate = (
            rf"\bno\s+(?:encontre|se\s+encontro)\s+{object_name}"
            rf"|\b(?:i\s+)?(?:didn't|did\s+not)\s+find\s+{object_name}"
            rf"|{object_name}\s+(?:no\s+se\s+encontro|was\s+not\s+found)\b"
        )
        failure_assertions = re.sub(
            finding_predicate, "", _accent_folded_with_punctuation(stripped),
        )
    # Pasada r18 (t-menu-2): a mission that failed arrives wrapped ({kind: failure, reason: {operation:
    # mission.computer.use}}); its final is judged by the same vetoes as an operation's, on the mission it tells.
    told_mission = situation if kind == "operation" and situation.get("operation") == "mission.computer.use" else (
        _computer_use_mission(situation) if kind == "failure" else None)
    if told_mission is not None:
        # Computer use (CONTRATO_VISTA_ACCION.md §4.5): a join never observed, a
        # false past time or a failed mission told as a success are invented.
        from . import cu_projection as _cu_projection
        from . import cu_reply_checks as _cu_reply_checks

        mission_defect = _cu_reply_checks.mission_defect(
            _accent_folded_with_punctuation(stripped),
            _cu_projection.project_seen(_merged_observed(told_mission), "es"),
        )
        if mission_defect is not None:
            return mission_defect
    if (
        polarity == "success"
        and situation.get("operation") != "message.send.test"
        and _send_not_stated(stripped, situation, told_mission is not None)
    ):
        # Encargo E (banco i1 c6: «Escribí "prueba BAXY C6" en el chat con Ron92 en Discord.» over a send verified):
        # a final of a verified send that does not say it was sent hides the act of risk; the person may send it again.
        return "send_not_stated"
    if _absent_label_misquoted(stripped, situation):
        # Pasada r18 (v3-64): what a not-found click looked for is quoted only as attempted.label.
        return "absent_label_misquoted"
    if final_defect := _computer_use_final_defect(stripped, situation):
        # cu-r17: an app already running told as opened, a question of the mission left unanswered.
        return final_defect
    if (
        kind == "operation"
        and situation.get("operation") == "client.channel.locate"
        and polarity == "success"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
    ):
        # DISCORD1839: nothing was joined; a final that says it joined invents it.
        folded_reply = _accent_folded_with_punctuation(stripped)
        claims_joined = re.search(r"\b(?:me\s+uni|me\s+he\s+unido|nos\s+unimos|joined|entre\s+(?:a|al)\b|estoy\s+en\s+el\s+canal|ya\s+estoy|te\s+uni)\b", folded_reply)
        negated_join = re.search(r"\b(?:no|not|sin|didn't|did\s+not|without|todavia\s+no|aun\s+no)\s+(?:\w+\s+){0,2}(?:uni\w*|unir\w*|join\w*|entr\w*)\b", folded_reply)
        if claims_joined is not None and negated_join is None:
            return "joined_claimed"
    if (
        kind == "operation"
        and situation.get("operation") == "browser.control"
        and _merged_observed(situation).get("action") == "close_all"
        and situation.get("succeeded") is not True
        and type(_merged_observed(situation).get("closedTabs")) is int
        and _merged_observed(situation)["closedTabs"] > 0
    ):
        # Measured live (Opera GX): three tabs closed, the fourth close not seen, and the final said «No se cerraron
        # las pestañas». The tabs seen closed are said, with their number.
        closed = _merged_observed(situation)["closedTabs"]
        words = ("", "una|uno|one", "dos|two", "tres|three", "cuatro|four", "cinco|five", "seis|six", "siete|seven",
                 "ocho|eight", "nueve|nine", "diez|ten")
        said_word = closed < len(words) and re.search(
            r"\b(?:" + words[closed] + r")\b", _accent_folded_with_punctuation(stripped),
        )
        if closed not in _numbers_in_figures(stripped) and not said_word:
            return "extra_claim"
    if (
        kind == "operation"
        and situation.get("operation") == "browser.control"
        and _merged_observed(situation).get("action") == "close_all"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
    ):
        folded_reply = _accent_folded_with_punctuation(stripped)
        closed_seen = _merged_observed(situation)
        if re.search(
            # BROWSER1841: the tabs were closed just now, in this turn; a final
            # that places the action at a specific past time («yesterday», «ayer»,
            # «last week») invents when it happened.
            r"\b(?:ayer|anoche|antier|anteayer|antes\s+de\s+ayer|la\s+semana\s+pasada|el\s+otro\s+dia|hace\s+(?:un|unos|varios|dos|tres)\s+(?:dia|dias|semana|semanas|hora|horas)|"
            r"yesterday|last\s+night|last\s+week|the\s+other\s+day|days?\s+ago|hours?\s+ago|weeks?\s+ago)\b",
            folded_reply,
        ) or (
            # The browser keeps its last tab: «cerré todas» without the one left says what did not happen.
            re.search(r"\b(?:todas|all|every)\b", folded_reply)
            and not re.search(r"\b(?:queda|quedan|quedo|dej\w*|menos|salvo|excepto|left|remains?|kept|except|but\s+one)\b", folded_reply)
        ):
            return "extra_claim"
        # The counts said are the ones read back: tabs closed and tabs left.
        read_counts = {closed_seen.get(key) for key in ("closedTabs", "tabCount") if type(closed_seen.get(key)) is int}
        if read_counts and not _numbers_in_figures(stripped) <= read_counts:
            return "invented_number"
    if (
        kind == "operation"
        and situation.get("operation") == "message.draft"
        and polarity == "success"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
    ):
        # MSG1837: the draft was never sent; a final that says it was sent or
        # delivered invents the delivery.
        folded_reply = _accent_folded_with_punctuation(stripped)
        claims_sent = re.search(r"\b(?:envie|enviado|enviada|sent|delivered|entregado|entregue)\b", folded_reply)
        negated_send = re.search(
            r"\b(?:no|sin|not|didn't|did\s+not|never|nunca|without)\s+(?:\w+\s+){0,2}(?:envie|enviar\w*|enviad\w*|send\w*|sent|mand\w*|entreg\w*)\b",
            folded_reply,
        )
        if claims_sent is not None and negated_send is None:
            return "draft_claimed_sent"
    if (
        kind == "operation"
        and situation.get("operation") == "message.send.test"
        and polarity == "success"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
    ):
        # MSG §6: the message went to the owner's test channel, not the requested
        # recipient. The reply must name the real destination; if it names only the
        # requested recipient (different from the destination) it hides where it went.
        seen_send = _merged_observed(situation)
        forced_dest = str(seen_send.get("forcedDestination") or "").strip()
        requested = str(seen_send.get("requestedRecipient") or "").strip()
        folded_reply = _accent_folded_with_punctuation(stripped)
        if forced_dest and _accent_folded_with_punctuation(forced_dest) not in folded_reply:
            return "sent_wrong_destination"
        if _send_not_stated(stripped, situation, False):
            # A verified send that the reply does not state (MSGSEND1845: «Hola
            # Música.») hides the delivery the person asked for.
            return "send_not_stated"
        if forced_dest and _denies_the_destination(
            folded_reply, _accent_folded_with_punctuation(forced_dest),
        ):
            # MAIL1863 H0018: the reply denied the delivery to the very
            # destination it reached («pero no llegó a
            # autor@example.com»), which is false whoever the
            # person named.
            return "denied_test_destination"
        if (
            requested
            and _accent_folded_with_punctuation(requested) == _accent_folded_with_punctuation(forced_dest)
            and re.search(
                r"\b(?:no|not|never|nunca|tampoco)\b[^.;]{0,40}\b(?:envi\w*|mand\w*|sent|send|entreg\w*|fue|went|lleg\w*"
                r"|destinatari\w*|persona|recipient|solicitad\w*|pedid\w*|indicad\w*|nombrad\w*|named|requested)\b",
                folded_reply,
            )
        ):
            # The person named the test channel itself: a reply that denies a send
            # to anyone, or that says it did not go to «the requested recipient»,
            # withholds or contradicts a delivery that happened exactly where asked
            # (MSGSEND1847: «no al destinatario solicitado» for «ya voy» to Música).
            return "denied_test_destination"
        if (
            requested
            and _accent_folded_with_punctuation(requested) != _accent_folded_with_punctuation(forced_dest)
            and re.search(
                r"\b(?:a|al|to)\s+" + re.escape(_accent_folded_with_punctuation(requested)),
                folded_reply,
            )
            and re.search(
                r"\b(?:envie|envio|mande|mando|sent|send|entregue|le\s+(?:envie|mande))\b[^.;]{0,40}\b"
                + re.escape(_accent_folded_with_punctuation(requested)),
                folded_reply,
            )
            # DISCORD1869 H0394: «Le envié "hola" a Valeria, no a ShooterCock» names
            # the real destination and denies the requested one, which is the truth;
            # only a reply that does not deny it claims the wrong delivery.
            and not _denies_the_destination(
                folded_reply, _accent_folded_with_punctuation(requested),
            )
        ):
            return "sent_wrong_destination"
    if (
        kind == "operation"
        and situation.get("operation") == "game.entitlement.named"
        and polarity == "success"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
        and presence.get("owned") is False
    ):
        # INSTALL1617 «Descarga Worms Rumble en Steam»: the library read
        # verified the game is not the person's; «no puedo descargarlo /
        # instalarlo / desinstalarlo» states that consequence, not a failed
        # read. Mask only that predicate in the failure lens.
        failure_assertions = re.sub(
            r"\b(?:no\s+(?:puedo|podre|podria|se\s+puede|es\s+posible|voy\s+a\s+poder)|"
            r"(?:i\s+)?(?:can't|cannot|can\s+not|couldn't|could\s+not|am\s+unable\s+to|it\s+is\s+not\s+possible\s+to|won't\s+be\s+able\s+to))"
            r"\s+(?:be\s+)?(?:descargar|descargarlo|descargarla|descargartelo|descargarse|bajar|bajarlo|bajarla|instalar|instalarlo|instalarla|instalartelo|instalarse|"
            r"desinstalar|desinstalarlo|desinstalarla|desinstalarse|download|downloaded|install|installed|uninstall|uninstalled|remove|removed)"
            r"[^.;]{0,80}",
            "",
            _accent_folded_with_punctuation(failure_assertions),
        )
    if (
        kind == "operation"
        and situation.get("operation") == "game.entitlement.named"
        and polarity == "success"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
        and (
            # H0578 «desinstalá Fortnite de Epic Games» → «Fortnite ya está
            # desinstalado… lo eliminé correctamente»: the library read never
            # installs, downloads or removes anything; a draft that says it did
            # (or that an installed game is gone) invents the effect.
            re.search(
                r"\b(?:lo\s+|la\s+|se\s+)?(?:desinstal(?:[eé]|ado|ada|amos|aste)|elimin(?:[eé]|ado|ada|amos|aste)|borr(?:[eé]|ado|ada|amos|aste)|quit(?:[eé]|ado|ada|aste)|"
                r"uninstalled|removed|deleted)\b|"
                r"\b(?:lo\s+|la\s+|se\s+)?(?:instal(?:[eé]|amos|aste)|descargu(?:[eé]|amos)|descargaste|baj(?:[eé]|amos|aste))\b|"
                r"\b(?:i|we)\s+(?:have\s+)?(?:installed|downloaded|uninstalled|removed)\b|"
                r"\b(?:se\s+(?:instal[oó]|descarg[oó]|desinstal[oó])|(?:has|have)\s+been\s+(?:installed|downloaded|uninstalled))\b",
                _accent_folded_with_punctuation(stripped),
            )
            is not None
        )
    ):
        return "extra_claim"
    if (
        kind == "operation"
        and situation.get("operation") == "game.entitlement.named"
        and polarity == "success"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
        and presence.get("owned") is False
        and re.search(
            # INSTALL1621 H0345: «Aunque esté en tu lista de posesiones, para
            # instalarlo necesitas confirmarlo» hints at a licence the read
            # denies and at a confirmation nobody was offered.
            r"\b(?:confirm|posesion|posesiones|lo\s+tienes|lo\s+tenes|ya\s+lo\s+tienes|es\s+tuyo|te\s+pertenece|you\s+own|owned\b|in\s+your\s+library,?\s+but)",
            _accent_folded_with_punctuation(stripped),
        )
    ):
        return "extra_claim"
    if _verified_search_results(situation):
        # WEB1447 «va a llover mañana»: the search verified forecast pages that
        # carry no values, and «No puedo confirmar si va a llover mañana porque
        # los resultados solo proporcionan pronósticos» states that scope
        # truthfully. Mask only that predicate in the failure lens; an invented
        # forecast or a denial of the results is still vetoed on the payload.
        # Owner rule 2026-09-24: when no page answers, the lookup stays invisible
        # and the answer says only that it was not found («No lo encontré», «I
        # couldn't find it»); that is the scope of the read, not a failed mission.
        failure_assertions = re.sub(
            r"\b(?:(?:no\s+(?:puedo|podria|se\s+puede|es\s+posible)|(?:i\s+)?(?:can't|cannot|can\s+not|am\s+unable\s+to|it\s+is\s+not\s+possible\s+to))"
            r"\s+(?:confirmar|confirmarte|asegurar|asegurarte|determinar|precisar|saber|decir|decirte|confirm|determine|tell|say|know)|"
            r"no\s+(?:(?:lo|la|los|las)\s+)?(?:encontre|halle|pude\s+encontrar(?:lo|la|los|las)?)|"
            r"(?:i\s+)?(?:couldn't|could\s+not|didn't|did\s+not|wasn't\s+able\s+to|was\s+not\s+able\s+to)\s+find)"
            r"[^.;]{0,120}",
            "",
            _accent_folded_with_punctuation(failure_assertions),
        )
    if _recognized_screen_text_in_situation(situation) is not None:
        # SCREEN1417 «qué hay en la pantalla»: no vision provider exists, so the
        # reading says it cannot describe images and reads the text. That is
        # the stated scope of a verified reading, not a failed mission; mask
        # only that predicate in the failure lens.
        failure_assertions = re.sub(
            r"\b(?:no\s+(?:puedo|podia|podria)|(?:i\s+)?(?:can't|cannot|can\s+not|couldn't|could\s+not|am\s+unable\s+to|am\s+not\s+able\s+to))"
            # SCREEN1809 «identificá el botón»: the scope said about buttons too.
            r"\s+(?:describir|describirte|ver|identificar|reconocer|describe|see|identify|recognize|recognise)"
            r"\s+(?:las\s+|los\s+|the\s+)?(?:imagenes?|images?|pictures?|graficos?|graphics|visuales?|visuals|botones?|buttons?)"
            r"[^.;]{0,80}",
            "",
            _accent_folded_with_punctuation(failure_assertions),
        )
    if (
        kind == "operation"
        and situation.get("operation") == "app.installed"
        and polarity == "success"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
        and presence.get("installed") is False
        and isinstance(presence.get("requestedName"), str)
        and presence["requestedName"].strip()
        and presence.get("authority") == "windows_start_catalog_snapshot"
    ):
        # A successful catalog read can prove absence, not a launch or failure
        # of the read. Remove only complete, name-bound factual propositions.
        name = re.escape(_accent_folded_with_punctuation(presence["requestedName"].strip()))
        target = rf"(?:(?:la|the)\s+)?(?:(?:aplicacion|application|app)\s+)?{name}"
        catalog = (
            r"(?:el\s+catalogo(?:\s+de\s+(?:la\s+autoridad\s+observada|inicio\s+de\s+windows))?"
            r"|the\s+(?:(?:observed|windows\s+start(?:\s+application)?)\s+)?catalog(?:ue)?"
            r"(?:\s+of\s+the\s+observed\s+authority)?)"
        )
        absent = (
            rf"(?:no\s+se\s+encontro\s+{target}|(?:{target}\s+)?no\s+"
            rf"(?:esta(?:\s+presente)?|figura|aparece))\s+en\s+{catalog}"
            rf"|(?:{target}\s+)?(?:was\s+not\s+found|(?:it\s+is|it's|is)\s+not\s+(?:found|present|listed))"
            rf"\s+in\s+{catalog}"
        )
        unavailable = (
            rf"(?:no\s+(?:se\s+)?(?:pudo|puede|pude|puedo)\s+abrir(?:\s+{target})?"
            rf"|(?:i\s+)?(?:could\s+not|couldn't|cannot|can't)\s+(?:open|launch)"
            rf"(?:\s+{target})?|it\s+(?:cannot|can't|could\s+not)\s+be\s+opened|"
            r"(?:its\s+)?opening\s+could\s+not\s+proceed)"
        )
        supported = (
            rf"(?:{absent})(?:,\s*(?:por\s+lo\s+que|asi\s+que|so)\s+{unavailable})?"
            rf"|{unavailable}\s+(?:porque|because)\s+(?:{absent})"
        )
        failure_assertions = _accent_folded_with_punctuation(stripped)
        for clause in reversed(tuple(re.finditer(r"[^.;\n]+[.;]?", failure_assertions))):
            statement = clause[0].strip().rstrip(".;")
            if (
                re.search(rf"(?<!\w){name}(?!\w)", statement)
                and re.fullmatch(supported, statement, re.IGNORECASE)
            ):
                failure_assertions = (
                    failure_assertions[:clause.start()] + " " + failure_assertions[clause.end():]
                )
        # A separate completed opening or explicit attempt is not catalog evidence.
        if re.search(
            r"(?:^|[.;]|\b(?:pero|but|y|and)\b)\s*"
            r"(?:(?:ya|yo|i|you|we|la|lo)\s+)*"
            r"(?:abri|abriste|abrio|abrieron|opened|launched|"
            r"intente|intentamos|tried|attempted)\b|"
            r"\b(?:is|was|has\s+been)\s+(?:opened|launched)\b",
            failure_assertions,
        ):
            return "extra_claim"
    # cien-45/48 turno 027: un pedido ambiguo que el bloque lleva a la ruta de
    # error se contesta preguntando, y la pregunta caia en la regla que exige
    # decir el fallo. No hay fallo que decir: la persona pidio abrir algo sin
    # decir que. La lista de pedidos ambiguos es cerrada y el texto ha de ser
    # solo pregunta.
    # A7 (FINAL t23/t199/t320): after an action was decided and its arguments came back empty, the App reports
    # ambiguous_request, whose fact asks for one short question; the question is the reply, not a failure to say.
    is_failure = (intent == "error" or polarity == "failure") and not (
        (_looks_like_ambiguous_action(user_text) or cause == "ambiguous_request")
        and visible_reply_is_only_questions(stripped)
    )
    if is_failure:
        if _SUCCESS_OPENERS.match(stripped) is not None:
            return "reversed_polarity"
        # M79 (DEV-D v3m w04-t4 «Mejor a las 6 en punto…» → «…varias alarmas estaban programadas para las 6:15…», ⚠
        # missing_literal_fact): the App judges the clocks against the person's own message, not the request as the
        # mind understood it («…de mañana a las 6:15 a las 6:00»); its twin reads the same words.
        if _failure_invents_a_clock(stripped, said if said else user_text, situation):
            return "extra_claim"
        if re.match(
            # NETWORK1737 «qué redes wifi hay» with the radio off: «La causa del
            # fallo es que la radio…» narrates the composer instruction; the
            # person is told the state, not the anatomy of the failure.
            r"(?:la|el|the)\s+(?:causa|motivo|razon|cause|reason)\s+(?:del?|of|for)\b",
            folded,
        ):
            return "metadiscourse"
        # M93 (held-out v3v t10 «abrí el bloc de notas», inventory_failed): «…no pudo leer la lista de programas y
        # ventanas abiertos» names the list that could not be read, the failure's own cause; it claims nothing open.
        # M101 (DEV-D v3z D-w10-t4 «He abierto YouTube, pero no he podido confirmar si la música tropical está
        # sonando.», refused three times and no final): when the failure is a YouTube page that opened and did not
        # confirm playback, the open page is its cause fact, not a reversed result.
        page_opened = _failure_opened_the_page(situation)
        # Estabilización F (estab2 t2-c18), revisión H3: only the app a step of the same plan found running is told as
        # already open; any other «abierto» is judged as before.
        said_open = _OPEN_PROGRAMS_LIST.sub(" ", folded)
        for name in _apps_found_running(situation):
            said_open = re.sub(
                rf"{re.escape(name.casefold())}»?\s+(?:ya\s+estaba\s+abiert[oa]|was\s+already\s+open)", " ", said_open,
            )
        if not page_opened and re.search(r"abiert|\bis open\b", said_open) and not re.search(
            # CLOSE1371 «cierra steam» with no Steam window: «no tiene ninguna
            # ventana abierta» / «no está abierto» state the absence, they do
            # not claim the application is open.
            r"\b(?:no|ni|ninguna?|nada|not|isn'?t|no\s+hay|sin)\b[^.;,]{0,40}\babiert|"
            r"\b(?:is\s+not|isn'?t|not)\s+open\b",
            folded,
        ):
            return "reversed_polarity"
        # ctx-dueno-05 (2026-09-22, «en Steam ve a Crash Bandicoot»): the open
        # is a completed step of the same mission and may be told;
        # «Abrí Steam … pero no se realizó el clic» reverses
        # nothing. Only a mission whose open did not complete keeps the veto.
        if (
            cause == "mission_failed"
            and re.search(
                # PPTX2051 «no window or process appeared to confirm it opened»:
                # «opened» inside a verification or negation clause claims
                # nothing; only the bare affirmation reverses the polarity.
                r"(?<!\bconfirm )(?<!\bconfirm it )(?<!\bconfirm that it )(?<!\bverify it )(?<!\bverify that it )"
                r"(?<!\bwhether it )(?<!\bif it )(?<!\bnot )(?<!\bnever )(?<!\bhaving )"
                r"\bopened\b|\babrí\b|\babri\b",
                folded,
            )
            and not _completed_step_operation(situation, "app.open")
            and not page_opened
        ):
            return "reversed_polarity"
        if cause == "mission_failed" and re.search(
            # UI1735 «ve a Cotele en Discord» with the click failed: «Ya anduve
            # a Cotele en Discord, pero no pude verificar…» claims the navigation
            # it then denies; a negated «no fui» stays. M74 (DEV-D v3l D-p24-t3): «the web browser could not be
            # reached» is the cause the shell gives, in the passive; «be reached» claims nothing BAXY did.
            r"(?<!\bno )(?<!\bnot )(?<!\bnunca )(?<!\bbe )(?<!\bbeen )(?<!\bbeing )"
            r"(?:\bya\s+)?\b(?:anduve|fui|entr[eé]|navegu[eé]|hice\s+clic|puls[eé]|apret[eé]|"
            r"i\s+went|i\s+navigated|i\s+clicked|i\s+entered|i\s+reached|reached)\b",
            folded,
        ):
            return "reversed_polarity"
        if cause == "mission_failed" and re.search(
            # CLOSE1651 «Cerrá WhatsApp, por favor.» with no window: «Ya cerré
            # WhatsApp, pero como no había ninguna ventana abierta…» claims
            # the close it then denies; a negated «no cerré nada» stays.
            r"(?<!\bno )(?<!\bnot )(?<!\bnunca )(?:\bya\s+)?\b(?:cerr[eé]|lo\s+cerr[eé]|la\s+cerr[eé]|i\s+closed|closed\s+it|"
            r"has\s+been\s+closed|qued[oó]\s+cerrad[oa]|ya\s+est[aá]\s+cerrad[oa])\b",
            folded,
        ):
            return "reversed_polarity"
        if (
            cause in {"mission_failed", "out_of_catalog"}
            and re.search(r"no respond|didn't respond|did not respond|no respondo", folded)
            # DOWNLOAD2047 «descargá https://example.com/index.html»: «la dirección
            # no respondió» is the typed cause (download_source_unavailable), not
            # an invented non-answer. M60 (DEV-D p25-t1 v3c «the weather service did not respond»): so is a
            # service whose cause fact is that it did not answer.
            and not _NON_ANSWER_CAUSES & set(_situation_error_codes(situation))
        ):
            return "extra_claim"
        # Fuera de catálogo no se intentó nada: «No pude reservar la mesa en
        # Titán» afirma un intento que no existió.
        if cause in {"out_of_catalog", "out-of-catalog"} and re.search(
            r"no pude|no logr[eé]|i couldn't|i could not|failed to|no consegu[ií]",
            folded,
        ):
            return "extra_claim"
        if cause in {"out_of_catalog", "out-of-catalog"}:
            # Fuera de catálogo no es un intento fallido, es un límite. Basta
            # con decirlo; exigir además «No pude:» obligaba a afirmar un
            # intento que nunca ocurrió.
            if not _names_the_boundary(folded):
                return "missing_failure"
            return limit_voice_defect(stripped, user_text)
        if _only_the_session_tab_read(situation) and _GENERAL_PLAYBACK_ABSENCE.search(
            _accent_folded_with_punctuation(stripped)
        ):
            # M105 (DEV-D v4a D-s047 «No hay música reproduciéndose porque no se ha abierto ningún video de YouTube»):
            # only the assistant's own YouTube tab was looked for; what the PC plays was not read.
            return "absence_beyond_check"
        if cause in _NOT_UNDERSTOOD_CAUSES and stripped in {
            dialogue_slot.words_floor_question(user_text, "es"), dialogue_slot.words_floor_question(user_text, "en"),
        } - {""}:
            # D59 §7: a turn not understood is asked about with the person's words; no failure is told (none ran).
            return ""
        if not _asserts_failure(stripped) and not _denies_the_failed_act(stripped, situation) and not (
            # Uso real 2026-09-23 «qué música se está reproduciendo» with no player
            # found: «No hay un video de YouTube en ejecución» IS the failure told,
            # when the failure is that absence. Twelve such drafts died wanting «no pude».
            _failure_is_an_absence(situation)
            and _ABSENCE_STATEMENT.search(_accent_folded_with_punctuation(stripped)) is not None
        ) and not (
            # Fase 3.5b owner script «activa mi microfono» (already on): «El micrófono ya estaba activo, por lo que
            # no ha cambiado su estado» IS the failure told; wanting «no pude» made the final claim an attempt failed.
            _failure_is_an_unchanged_state(situation)
            and _ALREADY_STATEMENT.search(_accent_folded_with_punctuation(stripped)) is not None
        ):
            return "missing_failure"
        # M62 (v3e2-final F-s019): the colon of a clock («a las 8:00») is not a label's.
        parts = re.split(r"(?<!\d):(?!\d)", stripped, maxsplit=1)
        if len(parts) == 2:
            tail_tokens = re.findall(r"[a-záéíóúñ]{3,}", parts[1].casefold())
            if not tail_tokens or (
                len(tail_tokens[-1]) <= 3
                and tail_tokens[-1] not in {"the", "app", "not", "out"}
            ):
                return "missing_failure"
    elif (
        cause != "acting"
        # M45: «No cambié nada» is the honest cancellation; vetoing it as a failure made the retry claim the effect.
        and cause != "clarification_cancelled"
        and kind not in {"welcome", "confirmation", "clarification"}
        and _asserts_failure(window_status_assertions(failure_assertions, {
            "operation": situation.get("operation"), "seen": _merged_observed(situation),
        }, require_window_answer=True))
        and not (
            kind == "conversation"
            and _looks_like_knowledge_question(user_text)
            and re.fullmatch(
                r"(?:i\s+)?" + _FAILURE_MARKERS.pattern,
                stripped.strip(" .!?¡¿"),
                re.IGNORECASE,
            ) is None
        )
        and not _looks_like_refuse_question(user_text)
        and not _looks_like_capability_question(user_text)
        # M75 (DEV-D v3l D-p02-t2 «¿Serías capaz de hacer foto ahora?»): «No puedo hacer fotos.» answers whether BAXY
        # is able; three such drafts died here and the turn ended in ⚠. A failed attempt claimed is still a failure
        # (twin: UserMessagePolicy looks_like_failure).
        and not (kind == "conversation" and asks_whether_able(user_text) and _FAILED_ATTEMPT.search(folded) is None)
        # M85 (DEV-D v3o D-p27-t1 «Any good movies for me to watch?» → «I don't know what you like, so I can't recommend
        # anything specific. What kind of movies do you usually enjoy?», refused; the fallback invented a film): what
        # BAXY cannot do yet, said to ask the person for what is missing, is a question, not a failure told
        # (twin: UserMessagePolicy looks_like_failure).
        and not (
            kind == "conversation" and ends_asking_the_person(stripped) and _FAILED_ATTEMPT.search(folded) is None
            and not _asserts_failure(without_saying_inability(without_quoted_speech(stripped)))
        )
        and not (kind == "conversation" and _failure_word_is_the_persons(failure_assertions, user_text))
        and not _search_not_found_report(stripped, situation)
        and not _listing_not_found_report(stripped, situation)
        and not _reached_but_unread_report(stripped, situation)
        # r15b2 v3-22 t3: a look at a window that runs as administrator read nothing; saying so is no failure claimed.
        and not _elevated_read_floor(situation, "es", said or user_text)
    ):
        return "asserted_failure"
    if intent == "welcome" or kind == "welcome":
        if _SUCCESS_OPENERS.match(stripped) is not None:
            return "welcome_opener"
        if _asserts_failure(stripped):
            return "reversed_polarity"
        if re.search(r"bienvenida\b", folded) is not None:
            return "wrong_gender"
        if language != "en" and re.search(r"\b(?:everything|ready)\b", folded):
            return "wrong_language"
        if re.search(r"abiert|\bis open\b|\bdoor\b|\bdevice\b|\bcall\b", folded):
            return "extra_claim"
        reply_reading = read_request(stripped)
        if _looks_like_knowledge_question(user_text) and reply_reading.greets:
            body = reply_reading.ask.lstrip(" .!?¿¡")
            if visible_reply_is_only_questions(body):
                return "answered_with_a_question"
        if _looks_like_knowledge_question(user_text) and (
            not read_request(user_text).greets or read_request(stripped).greeting_only
        ):
            folded_reply = stripped.casefold().strip(" .!?¿¡")
            if folded_reply.startswith(
                ("hola", "hello", "hi ", "hi,", "hey", "hi i'm", "hi, i")
            ) or folded_reply in {"hi", "hey", "hello"}:
                return "knowledge_greeting"
    if intent == "conversation" or kind == "conversation":
        if _unverified_present_fact(stripped, user_text, facts) is not None:
            return "unverified_present_fact"
        if not asks_for_code(said or user_text, ()) and repeats(facts.get("context")):
            # M103 (owner script t41 «Dimelo tu, te mande la mision a tiu» → t40's reply again, word for word): the App's
            # conversation fallback is held to the mind's M99 check; the previous answer travels as the context.
            return "repeats_last_answer"
        followup_subject = followup_topic(user_text, facts.get("priorRequests"))
        # Lo que la persona pidió decide si una pregunta puede ser la respuesta.
        # Por sus capacidades, sus límites o por seguir hablando se contesta con
        # el catálogo; devolver «¿Qué específicamente no puedes hacer en este
        # PC?» deja el turno sin respuesta (limites-14/003..006, /009).
        answerable_from_the_catalog = bool(
            read_request(user_text).intents
            & {INTENT_CAPABILITY, INTENT_REFUSE, INTENT_CONTINUE_CONSTRAINT}
        )
        if (
            _looks_like_knowledge_question(user_text)
            or followup_subject is not None
            or answerable_from_the_catalog
        ):
            # Devolver la pregunta no la contesta. «para qué lo necesita el PC»
            # se publicó como «¿Para qué necesita el PC para ejecutar tareas
            # específicas?» (seguimiento-10/020): el turno acaba sin respuesta.
            if visible_reply_is_only_questions(stripped):
                return "answered_with_a_question"
    if intent == "clarification" or kind == "clarification":
        if _required_compose_input(situation) is None and _knowledge_to_answer(user_text):
            if "?" in stripped or "¿" in stripped:
                return "knowledge_question"
            folded_reply = stripped.casefold().strip(" .!?¿¡")
            if folded_reply in {"hola", "hi", "hey", "hello", "hola baxy"} or (
                folded_reply.startswith("hola") and len(folded_reply) < 28
            ):
                return "knowledge_greeting"
        elif "?" not in stripped and "¿" not in stripped:
            return "clarification_not_a_question"
        if stripped.count("¿") > 1 or stripped.count("?") > 1:
            return "too_many_sentences"
    # Brevity belongs to presentation, not factual validity. A greeting with
    # an introduction or a two-sentence explanation is still one useful reply.
    # Confirmation choices and pending-state truth matter, not punctuation.
    if intent == "confirmation" or kind == "confirmation":
        if _SUCCESS_OPENERS.match(stripped) is not None:
            return "confirmation_asserted"
        required_choices = _localized_confirmation_words(
            [
                str(value).strip()
                for value in (facts.get("requiredResponseWords") or [])
                if str(value).strip()
            ],
            language,
        )
        if required_choices and any(
            not re.search(
                rf"(?<!\w){re.escape(choice.casefold())}(?!\w)",
                folded,
            )
            for choice in required_choices
        ):
            return "missing_confirmation_choice"
        if not required_choices and (
            not re.search(r"confirm", folded) or not re.search(r"cancel", folded)
        ):
            return "missing_confirmation_choice"
        # Prueba del dueño 2026-09-21 (turno 151): «¿confirmar o cancelar la
        # cerrado de Edge?». El participio del paso («cerrado») usado como
        # sustantivo con el artículo del otro género no es castellano; la
        # pregunta se rehace nombrando la acción con el verbo o su sustantivo.
        if _MISMATCHED_ACTION_NOUN.search(folded) is not None:
            return "malformed_action_noun"
    if cause == "acting":
        if (
            _SUCCESS_OPENERS.match(stripped) is not None
            or re.match(r"^\s*(?:hola|hi|hello)\b", folded) is not None
            or re.search(r"abiert|\bis open\b|cerrad|\bis closed\b", folded)
            or _asserts_failure(stripped)
        ):
            return "acting_asserted"
        # A progress word cannot authenticate an instrument reading. Reuse the
        # existing reading/predicate grammar, allowing numeric targets from
        # the request (a reminder time, file size) without asserting them as
        # current measurements. Progress has no observed results to report.
        punctuated = _accent_folded_with_punctuation(stripped)
        readings = tuple(_OBSERVED_INSTRUMENT_READING.finditer(punctuated))
        request_literals = re.sub(r"\s+", "", _accent_folded_with_punctuation(user_text))
        if readings and (
            _READING_IS_ABOUT_THIS_MACHINE_NOW.search(punctuated) is not None
            or _PRESENT_STATE_CLAIM.search(punctuated) is not None
            or any(
                re.sub(r"\s+", "", reading.group()) not in request_literals
                for reading in readings
            )
        ):
            return "acting_asserted"
        # Progressive verb morphology admits the activity in the request;
        # it must not require the model to repeat "sigo" or "still working".
        if not re.search(
            r"\b(?:\w{2,}(?:ing|ando|iendo)|sigo|progress|progreso|curso)\b",
            re.split(r"[.!?]", folded, maxsplit=1)[0],
        ):
            return "acting_asserted"
    observed = situation.get("observed")
    observed_dict = _merged_observed(situation)
    if not observed_dict and isinstance(observed, dict):
        observed_dict = observed
    if _cpu_only_numbers_contradict(stripped, observed_dict):
        return "wrong_machine_value"
    if isinstance(observed_dict.get("cpu"), dict) and observed_dict["cpu"] and re.search(
        r"\b(?:estoy\s+(?:usando|ocupando|consumiendo)|"
        r"tengo\s+(?:(?:un|una|el|la)\s+)?(?:procesador|cpu)|"
        r"tengo\s+(?:(?:un|el)\s+)?(?:uso|consumo)\b[^.!?\n]{0,60}\b(?:cpu|procesador)|"
        r"mi\s+(?:equipo|pc|computador(?:a)?|ordenador|procesador|cpu)|"
        r"i(?:\s+am|'m|’m)\s+(?:using|consuming)|"
        r"i\s+have\s+(?:(?:an?|the|\d+)\s+[^.!?\n]{0,80})?(?:processors?|cpu|cores)|"
        r"my\s+(?:computer|pc|processor|cpu))\b",
        folded,
    ):
        return "wrong_machine_actor"
    if isinstance(observed_dict.get("battery"), dict) and observed_dict["battery"] and re.search(
        r"\b(?:(?:tengo|me\s+queda|estoy\s+(?:a|al))\s+"
        r"(?:(?:un|una|el|la)\s+)?(?:\d+(?:[.,]\d+)?\s*"
        r"(?:%|por\s*ciento|percent|per\s+cent)\s*(?:de\s+)?)?(?:bater[ií]a|carga)|"
        r"mi\s+bater[ií]a|estoy\s+(?:cargando|descargando)|"
        r"i\s+(?:have|(?:do\s+not|don't|don’t)\s+have)\s+"
        r"(?:(?:a|the|no)\s+)?(?:\d+(?:[.,]\d+)?\s*"
        r"(?:%|percent|per\s+cent)\s*(?:of\s+)?)?(?:battery|charge)|"
        r"my\s+battery|i(?:\s+am|'m|’m)\s+(?:not\s+)?(?:charging|discharging))\b",
        folded,
    ):
        return "wrong_machine_actor"
    # M153: a reminder or a task titled «poner el celular en silencio» / «mute the TV» says no mute of BAXY's.
    mentions_mute = re.search(
        r"silenci|\bmuted\b|\bunmuted\b|\bmute\b",
        _without_record_titles(folded, _situation_record_titles(situation)),
    )
    # Owner's test 2026-09-21 (turn 205): «el micrófono ya estaba silenciado» is
    # the typed cause of the failure (microphone_already_muted), not a claim
    # beyond the facts; the mute words of that cause are the fact.
    # M54: «ya está al máximo, pero en silencio» is the typed cause volume_already_at_maximum_muted.
    mute_is_the_cause = any(
        str(code).startswith("microphone_already_") or str(code) == "volume_already_at_maximum_muted"
        for code in _situation_error_codes(situation)
    )
    if mentions_mute and "muted" not in observed_dict and operation != "audio.mute" and not mute_is_the_cause:
        return "extra_claim"
    # M69 (guion v3h t46 «activalo»): «El micrófono está desactivado.» over muted=false. For the microphone, off or
    # disabled is muted and on or active is unmuted, in both languages; the state is the post-read or the one that
    # already held.
    microphone_muted = _microphone_muted_fact(situation)
    microphone_said = folded
    if microphone_muted is not None and "muted" not in observed_dict:
        # The state that already held is still the state: «ya estaba desactivado» says it off now.
        microphone_said = re.sub(r"\bestaba\b", "está", folded)
        microphone_said = re.sub(r"\bwas(?:\s+already)?\b", "is", microphone_said)
    if microphone_muted is False and _MICROPHONE_SAID_OFF.search(microphone_said):
        return "reversed_mute"
    if microphone_muted is True and _MICROPHONE_SAID_ON.search(microphone_said):
        return "reversed_mute"
    if "muted" in observed_dict:
        muted = observed_dict.get("muted") is True
        # MIC1813: «micrófono está silenciado» contains «no esta silenci»; the
        # negation is a word, not the tail of «micrófono».
        # cien-106 t006 «…el audio está activo al 100 %, sin estar silenciado» died three drafts as reversed_mute.
        unmuted_ok = re.search(
            r"reactiv|unmuted|\bya no est[aá] silenci|"
            r"\bno est[aá] silenci|\bsin\s+(?:estar\s+)?silenci|\bfalse\b|not muted|"
            r"isn't muted|is not muted",
            folded,
        )
        if muted and unmuted_ok is not None:
            return "reversed_mute"
        if not muted:
            # Tanda 6 «Reactiva el speaker»: «El speaker estaba silenciado y ahora está activo» tells the observed
            # baseline and was rejected, costing a retry. The past mute is the fact when the baseline was muted.
            baseline = observed_dict.get("baseline")
            was_muted = observed_dict.get("baselineMuted") is True or (
                isinstance(baseline, dict) and baseline.get("muted") is True
            )
            told_now = (
                re.sub(r"\b(?:estaba|estaban|was|were|had\s+been)\s+(?:silenciad[oa]s?|muted)\b", " ", folded)
                if was_muted
                else folded
            )
            if re.search(r"silenci|\bmuted\b", told_now) and unmuted_ok is None:
                return "reversed_mute"
            # Tanda 6b «No, el sonido no está activo…» over muted=false: the sound said off is a mute said otherwise.
            if re.search(
                r"\b(?:sonido|audio|speakers?|altavoz|altavoces|sound)\s+(?:\w+\s+){0,2}?"
                r"(?:no\s+est[aá]\s+activ|is\s+not\s+active|isn'?t\s+active|is\s+off\b|est[aá]\s+apagad|"
                r"est[aá]\s+desactivad|is\s+disabled)",
                told_now,
            ):
                return "reversed_mute"
        # Owner's test 2026-09-21 (turn 205): «Tu micrófono está activo» names
        # the observed unmute by its device; the state word need not be «mute».
        if not re.search(
            r"silenci|\bmuted\b|\bunmuted\b|\bmute\b|audio|speaker|altavoc|"
            r"volumen|volume|micr[oó]fono|microphone|\bmic\b",
            folded,
        ):
            return "missing_name"
        if (
            polarity == "success"
            and re.search(r"\bvolumen\b|\bvolume\b", folded)
            and "level" not in observed_dict
            and "volumen" not in blob
            and "volume" not in blob
        ):
            return "extra_claim"
    if (intent == "welcome" or kind == "welcome") and re.search(
        r"\bhola\b.*\bhola\b", folded
    ):
        return "welcome_repeat"
    lead = vocabulary_text.lstrip("¿¡\"'")
    if lead and lead[0].isalpha() and lead[0].islower() and not _opens_with_observed_identifier(lead, situation):
        return "lowercase"
    # AUDIO1793: the application of a volume adjustment is the audio target,
    # not an opened application whose open/closed state the final must state.
    app_name = None if operation in {"audio.app.volume.adjust", "audio.app.volume.set"} else observed_dict.get("app")
    # NEAR1997 H0227 «abre Steel.»: the app.open receipt names what opened as
    # `appId`; a final that says «La app ya estaba abierta» leaves the person
    # who said «Steel» without knowing what BAXY understood. The observed id is
    # the name the final has to carry.
    if app_name is None and operation == "app.open":
        app_name = _app_open_observed_name(situation)
    if isinstance(app_name, str) and app_name.strip():
        feminine = _app_is_feminine(app_name)
        if (
            feminine
            and re.search(r"está abierto\b", folded)
            and "abierta" not in folded
        ):
            return "wrong_gender"
        if not feminine and re.search(r"está abiertas\b|está cerradas\b", folded):
            return "wrong_gender"
        if (
            feminine
            and re.search(r"está cerrado\b", folded)
            and "cerrada" not in folded
        ):
            return "wrong_gender"
    if polarity == "success" and cause != "acting" and kind in {"operation", "status"}:
        aliases = {
            "calculadora": ("calculator", "calculadora"),
            "calculator": ("calculator", "calculadora"),
            "notepad": ("notepad", "bloc"),
            # THEN2007 «open notepad»: the Store app is «Bloc de notas» in this
            # Windows and «Notepad» in an English reply; both name it.
            "bloc de notas": ("notepad", "bloc"),
            "explorador de archivos": ("explorer", "explorador"),
            "file explorer": ("explorer", "explorador"),
            "terminal": ("terminal",),
        }
        if isinstance(app_name, str) and app_name.strip():
            names = {app_name.casefold(), *aliases.get(app_name.casefold(), ())}
            if operation == "app.open":
                # NEAR1997: «Abrí Chrome» names «Google Chrome»; any word of the
                # catalog name of four letters or more counts as naming it.
                names |= {word for word in app_name.casefold().split() if len(word) >= 4}
            if not any(name in folded for name in names):
                return "missing_name"
            closed_request = asks_to_close(user_text)
            if closed_request and re.search(r"abiert|\bis open\b", folded):
                return "reversed_result"
            if not closed_request and not re.search(
                r"abiert|open|running|cerrad|closed|playing|reproduc|ejecuci",
                folded,
            ) and not (
                # THEN2003 «abrí el bloc de notas»: «Abrí el Bloc de notas.» tells
                # the state of an app that was closed and opened now.
                operation == "app.open" and _claims_it_performed_the_open(folded)
            ):
                return "missing_state"
        def media_transport(operation: str, situation: dict, observed_dict: dict) -> bool:
            return (
                operation == "media.control"
                and situation.get("verified") is True
                and situation.get("succeeded") is True
                # MUSIC1593: the local YouTube player reports and stops its own
                # playback with the same fields as an SMTC session.
                and observed_dict.get("authority") in {"windows_smtc", "local_youtube_player"}
                and isinstance(observed_dict.get("sourceAppUserModelId"), str)
                and bool(observed_dict["sourceAppUserModelId"].strip())
                and observed_dict.get("playbackStatus") in {"playing", "paused", "stopped"}
            ) or (
                # MUSIC1553: the local YouTube playback names what plays by its
                # observed title; «título» need not be said for the quote to count.
                operation == "media.play.youtube"
                and situation.get("verified") is True
                and situation.get("succeeded") is True
                and observed_dict.get("playbackStatus") == "playing"
            ) or (
                # MUSIC1747 «pon michael jackson en spotify»: the Spotify client
                # playback names what plays by its observed title the same way.
                operation in {"media.play.query", "media.play.exact"}
                and situation.get("verified") is True
                and situation.get("succeeded") is True
                and observed_dict.get("playbackStatus") == "playing"
                and isinstance(observed_dict.get("title"), str)
            ) or (
                # Las filas de vídeo «pon Stranger Things en Netflix»: la
                # reproducción en la sesión de streaming nombra lo que se ve por su
                # título observado, igual que Spotify o el reproductor local. Sin
                # estar aquí, el guardián exigía además la palabra «título» en la
                # respuesta, y los tres borradores —«Ya está reproduciendo Stranger
                # Things en Netflix»— morían en missing_name con el vídeo avanzando.
                operation == "streaming.play.named"
                and situation.get("verified") is True
                and situation.get("succeeded") is True
                and observed_dict.get("playbackStatus") == "playing"
                and isinstance(observed_dict.get("title"), str)
            )

        # M146 (DEV-G v4p/v4q G-s116 «abrí spotify y ponime algo de jazz tranqui…», plan app.open + media.play.query
        # verified): «Abrí Spotify y ya está reproduciendo "Vendla - After Winter Comes Spring"…» died three times as
        # missing_name, because the mission has no operation of its own and only a single playback was let name what
        # plays by its title. A step of the mission that verified that playback, with that same title, names it the
        # same way; the title must still be in the reply.
        verified_media_transport = media_transport(operation, situation, observed_dict) or any(
            isinstance(step.get("observed"), dict)
            and step["observed"].get("title") == observed_dict.get("title")
            and media_transport(str(step.get("operation") or ""), step, step["observed"])
            for step in _situation_steps(situation)
        )
        # H0516 «… guarda una captura en el escritorio …»: la captura de pantalla
        # no lleva ruta —queda en la carpeta privada de BAXY— y dos de los tres
        # borradores decían «se guardó en el escritorio». Un lugar que el recibo
        # no da es inventado, en una misión de varios pasos o en una sola.
        _capture_steps = [
            step for step in _situation_steps(situation)
            if step.get("operation") in {"capture.screenshot", "capture.active.window"}
        ] or ([situation] if operation in {"capture.screenshot", "capture.active.window"} else [])
        _capture_given_place = any(
            isinstance((step.get("observed") or {}).get(key), str)
            for step in _capture_steps
            for key in ("path", "savedTo", "filePath", "location")
        )
        # Ronda 22: a copy saved where the person asked (savedFolder) is a place the receipt gives — that place only.
        _capture_saved = {
            folder for step in _capture_steps
            if isinstance(folder := (step.get("observed") or {}).get("savedFolder"), str)
        }
        if _capture_steps and not _capture_given_place and not _capture_saved and _capture_place_claimed(folded):
            return "invented_capture_location"
        if _capture_saved and not _capture_given_place and _capture_saved_place_contradicted(folded, _capture_saved):
            # Revisión 2 de r22 (bloqueante 2, savedFolder=desktop → «…la guardé en Descargas…», «…quedó privada en
            # este PC, no la guardé en ningún lado»): the person looks where the final says and finds nothing.
            return "capture_saved_place_contradicted"
        # H0081 «quiero que abras opera gx y entras a pivigames»: la navegación
        # verificada da el navegador y la dirección final, nada más. El borrador
        # decía «el sitio está disponible y puedo ver las últimas actualizaciones
        # y categorías de juegos… no he podido verificar si es seguro»: contenido
        # que nadie leyó (no hubo lectura de página) y juicios que el recibo no
        # da. Se veta la descripción del contenido, no el nombre del sitio.
        _navigation_steps = [
            step for step in _situation_steps(situation)
            if step.get("operation") in {"browser.navigate", "browser.navigate.named"}
        ] or ([situation] if operation in {"browser.navigate", "browser.navigate.named"} else [])
        _page_read = any(
            step.get("operation") in {"browser.page.read", "ocr.read", "vision.describe"}
            for step in _situation_steps(situation)
        ) or operation in {"browser.page.read", "ocr.read", "vision.describe"}
        if _navigation_steps and not _page_read and re.search(
            r"\b(?:puedo ver|veo|se ven?|muestra|aparecen?|contenido|disponible|actualizaciones|categor[ií]as|seguro|segura|seguridad|confiable|fiable|verificar|virus|i can see|i see|shows|showed|content|available|safe|safety|reliable|trustworthy|verify|verified)\b",
            folded,
        ):
            return "navigation_content_claim"
        if _navigation_steps and not _page_read and semantic_claims.tells_page_content(stripped):
            # Semilla fix2 t2/t3: «No hay películas … disponibles en Google», «el resultado confirma…»: nothing read
            # the page that was opened.
            return "navigation_content_claim"
        if _navigation_steps and not _page_read:
            # La variante inglesa listaba los resultados de la búsqueda («a YouTube
            # channel, a related site (pivigamers.com), a Reddit discussion…»): la
            # búsqueda fue el medio para dar con la dirección, no lo pedido. Salvo
            # que lo navegado sea una página de resultados (WEB1481/1885), ni
            # «resultados» ni ningún otro dominio que el alcanzado.
            _reached_hosts = set()
            for step in _navigation_steps:
                for key in ("finalUrl", "requestedUrl"):
                    value = (step.get("observed") or {}).get(key) if step is not situation else observed_dict.get(key)
                    if isinstance(value, str) and value:
                        host = (urlparse(value).hostname or "").casefold()
                        if host:
                            _reached_hosts.add(host[4:] if host.startswith("www.") else host)
            _results_page = any(
                host.endswith(("bing.com", "youtube.com", "duckduckgo.com", "google.com"))
                for host in _reached_hosts
            )
            if _reached_hosts and not _results_page:
                if re.search(r"\b(?:resultados?|results?)\b", folded):
                    return "navigation_content_claim"
                for host in re.findall(
                    r"(?<![\w@.-])(?:https?://)?(?:www\.)?((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63})(?![\w-])",
                    folded,
                ):
                    if host.casefold() not in _reached_hosts:
                        return "wrong_address"
        if (
            operation == "streaming.play.named"
            and situation.get("verified") is True
            and situation.get("succeeded") is True
            and observed_dict.get("playbackStatus") == "playing"
            and re.search(
                r"\bno\s+(?:se\s+pued[eo]n?|pude|puedo|podemos|es\s+posible|fue\s+posible)\b"
                r"|\bno\s+(?:se\s+)?(?:est[aá]|logr[oó]|consigui[oó])\s+reproduci"
                r"|\b(?:can(?:'|’)?t|cannot|couldn(?:'|’)?t|could\s+not|unable\s+to|wasn(?:'|’)?t\s+able|not\s+possible)\b",
                folded,
            )
        ):
            # VIDEO1953: con «El diablo viste a la moda 2» avanzando, un borrador
            # abrió «No, no se puede reproducir "The Devil" en Disney Plus» antes
            # de nombrar lo que se ve. La búsqueda del servicio corrigió el
            # título; nada falló. Una reproducción verificada no admite ninguna
            # negación de capacidad en su final.
            return "playback_denied"
        if (
            operation == "streaming.play.named"
            and isinstance(observed_dict.get("observedProgressSeconds"), (int, float))
            and re.search(
                r"\d[\d.,]*\s*(?:segundos?|seconds?|secs?\b)"
                # VIDEO1919 H0155: el veto de los dígitos dejaba abierta la puerta
                # de al lado, y por ahí se publicó «se está reproduciendo desde el
                # momento cero». El recibo trae el avance medido ENTRE DOS
                # LECTURAS, no la posición en el vídeo: decir por dónde va es
                # afirmar sin verificar, y aquel acierto fue casualidad.
                r"|\bdesde\s+(?:el\s+)?(?:momento\s+)?(?:cero|principio|comienzo|inicio)\b"
                r"|\bfrom\s+the\s+(?:very\s+)?(?:beginning|start)\b"
                r"|\bdesde\s+el\s+minuto\b",
                folded,
            )
        ):
            # Los segundos observados son la prueba de que el vídeo avanza, no un
            # hecho que contarle a la persona: un borrador los leyó como suyos
            # —«Ya estás viendo Stranger Things en Netflix. Está en reproducción
            # y has pasado 0.63 segundos»— y le atribuyó un tiempo que pasó el
            # vídeo, no ella. Pedir una serie no es preguntar por dónde va.
            return "playback_progress_stated"
        # Tanda 6b «set alarms for 2pm and 3pm»: a mission's alarms are judged like one alarm, each by its time.
        scheduled_dues = _verified_notification_dues(situation)
        if _verified_titled_item_write(situation, operation, cause) and _NEGATED_OWN_WRITE.search(
            _reading_fold(stripped)
        ):
            # M60 (DEV-D p03-t3 v3d «I did not remove the chips from your shopping list because you requested
            # that.» over a verified delete): the write the store verified, told as not done, is the result
            # reversed. The title rule caught it only by accident, for not saying «title».
            return "reversed_result"
        title = observed_dict.get("title")
        if scheduled_dues and not names_the_title(user_text):
            # A generated description («alarm at 3 pm») is not an explicitly chosen identity.
            title = None
        if isinstance(title, str) and title.strip():
            # MUSIC1555: a YouTube title with doubled spaces is still named
            # when the draft writes it with single ones.
            # MUSIC1773: quotation marks inside the title («Op. 125 "Choral"») are
            # typography; the draft may write them straight or curly.
            title_named = title.casefold() in folded or re.search(
                r"\s+".join(re.escape(part) for part in _title_fold(title).split()), _title_fold(stripped)
            ) is not None or (
                # Tanda 5b / 6b: a played title named without the tab's « - YouTube» or by every name in it.
                operation in _MEDIA_TITLE_OPERATIONS
                and _names_media_title(stripped, title, by_parts=operation in _MEDIA_TITLE_BY_PARTS)
            ) or (
                # INSTALL1619: the model wrote «Batman: Arkham Knight» for the
                # library title «batman arkham knight»; punctuation between the
                # words of the game's title still names it.
                operation == "game.entitlement.named"
                and re.search(
                    r"[\s:,\-–—.]+".join(re.escape(part) for part in _reading_fold(title).split()),
                    _reading_fold(stripped),
                ) is not None
            )
            if not title_named or (
                operation != "media.status" and not verified_media_transport
                and not scheduled_dues
                and not (
                    operation in _TITLED_ITEM_WRITES
                    and situation.get("verified") is True
                    and situation.get("succeeded") is True
                )
                # Tanda 4c: the list read and then the add of the entry it did not find («add flour to my
                # shopping list if it's not already on it»); the created title is named like a single add.
                # M60 (DEV-D p03-t3 «Nevermind I do not want chips on there», resolve + delete, all three runs):
                # «I have removed chips from your shopping list.» names the removed item by its title as well; nine
                # drafts died for not saying «note» or «title».
                and not (
                    cause == "mission_completed"
                    and any(
                        step.get("operation") in _TITLED_ITEM_WRITES
                        and step.get("verified") is True
                        and step.get("succeeded") is True
                        for step in _situation_steps(situation)
                    )
                )
                # INSTALL1617: the Steam library read names the game by its
                # title; «Worms Rumble no está en tu biblioteca» names it
                # without the word «título».
                and not (
                    operation == "game.entitlement.named"
                    and situation.get("verified") is True
                    and situation.get("succeeded") is True
                )
                # Owner's live check 2026-10-06 «léeme lo que dice la página» (Opera GX): a page's title is the name
                # of the page, not a record's title; «En GX Corner se informa que…» names it, and three right
                # summaries died here for not saying «título».
                and not (
                    operation == "browser.page.read"
                    and situation.get("verified") is True
                    and situation.get("succeeded") is True
                )
                and not re.search(r"nota|note|t[íi]tulo|title", folded)
            ):
                return "missing_name"
            if not (isinstance(app_name, str) and app_name.strip()) and re.search(
                r"abiert|\bis open\b|cerrad|\bis closed\b", folded
            ) and not (
                # «léeme la página que tengo abierta» → «La página abierta es GX Corner y dice: …» describes the page
                # the person asked about, not an application opened or closed (owner's live check 2026-10-06).
                operation == "browser.page.read"
                and situation.get("verified") is True
                and situation.get("succeeded") is True
            ):
                return "extra_claim"
            if re.match(
                rf"^{re.escape(title.strip())},\s*(?:el |the )?t[íi]tulo es",
                stripped,
                re.IGNORECASE,
            ):
                return "copied_instruction"
        if verified_media_transport and re.match(
            # MUSIC1759 «¡Ah, qué buena canción! Estoy escuchando…»: an opinion is
            # not an observed fact of the playback.
            r"[¡!\s]*(?:ah|oh|uy|uf|wow|genial|excelente|perfecto|great|awesome|nice|"
            r"qu[eé]\s+buen[ao]|what\s+a\s+(?:great|good|nice))\b",
            stripped,
            re.IGNORECASE,
        ):
            return "extra_claim"
        if operation == "media.status" or verified_media_transport:
            # Metadata names are literal facts, not assertions of playback.
            # Verified controls use the same names/state checks; a music title
            # does not require the unrelated document label "title" or "note".
            playback_text = stripped
            for field in ("title", "artist"):
                name = observed_dict.get(field)
                if isinstance(name, str) and name.strip():
                    if not _names_media_title(stripped, name, by_parts=operation in _MEDIA_TITLE_BY_PARTS):
                        return "missing_name"
                    # The title's own words («Playing God», «Stop») are no claim about the playback.
                    playback_text = _without_media_title(playback_text, name)
            album = observed_dict.get("album")
            if operation == "media.status" and asks_the_album(user_text):
                # M89 (DEV-D v3r D-w05-t3 «de qué disco es esta» → «Está sonando Piano Bar de Charly García.»): the
                # album asked is the answer when the session publishes it; without it, the reply says it is not known
                # from here instead of repeating the song as if that answered.
                if isinstance(album, str) and album.strip():
                    if not _names_media_title(stripped, album, by_parts=True):
                        return "missing_name"
                    playback_text = _without_media_title(playback_text, album)
                elif _MEDIA_ALBUM_UNKNOWN.search(_reading_fold(stripped)) is None:
                    return "missing_name"
            playback = observed_dict.get("playbackStatus")
            if playback in {"playing", "paused", "stopped"}:
                assertions = list(re.finditer(
                    r"\b(?:(?P<negative>no|not|nothing|isn't|isn’t|aren't|aren’t)\s+)?"
                    r"(?:(?:se|est[aá]|est[aá]n|is|are|sigue|still|currently|"
                    r"hay|nada|ahora|actualmente)\s+)*"
                    r"(?:(?P<playing>sonando|suena|reproduci[eé]ndo(?:se)?|reproduce|en\s+reproducci[oó]n|escuchando|playing"
                    # MUSIC1573 «poné una canción» → «Bad Bunny»: «Estoy viendo el
                    # video «…» en YouTube» states the playback of the video the
                    # product itself announced; watching is the playing state here.
                    + (r"|viendo|watching" if operation == "media.play.youtube" else "")
                    # M172 (DEV-I v5b I-s047 «He iniciado la reproducción de "Mi Buen Amor" de Mon Laferte en
                    # Spotify.», missing_state): starting the playback the result verified playing says that state;
                    # the auxiliary is part of it so «no he iniciado…» stays a negation.
                    + r"|(?:(?:he|hemos|ha)\s+)?(?:iniciado|inici[eé]|comenzado|comenc[eé]|empezado|empec[eé])\s+"
                    r"(?:la\s+reproducci[oó]n|a\s+(?:reproducir|sonar))" + r")|"
                    # Uso real 2026-09-23 «para de reproducir»: «La reproducción
                    # se detuvo», «Dejé de reproducir» say the verified stop with a
                    # verb, not an adjective, and both drafts died in missing_state.
                    r"(?P<paused>pausad[oa]s?|en\s+pausa|paused|paus[eé]|paus[oó])|"
                    r"(?P<stopped>detenid[oa]s?|parad[oa]s?|stopped|detuv(?:e|o|ieron)|"
                    r"par[eé]|dej[eé]\s+de\s+(?:reproducir|sonar)|dej[oó]\s+de\s+(?:reproducirse|reproducir|sonar)))\b",
                    playback_text,
                    re.IGNORECASE,
                ))
                names_observed_state = False
                for assertion in assertions:
                    state = next(
                        key for key in ("playing", "paused", "stopped")
                        if assertion.group(key)
                    )
                    if (state == playback) == bool(assertion.group("negative")):
                        return "reversed_result"
                    if state == playback or (state == "playing" and assertion.group("negative")):
                        names_observed_state = True
                # Tanda 6b «qué persona hizo esta canción que está sonando en la radio» (paused): who made it or
                # which song it is is answered by the title; the state is then not owed, and a contrary one
                # still is reversed above.
                if not names_observed_state and not (
                    operation == "media.status" and asks_what_is_playing(user_text)
                ):
                    return "missing_state"
        if (
            operation in {"audio.app.volume.adjust", "audio.app.volume.set"}
            and situation.get("verified") is True
            and situation.get("succeeded") is True
        ):
            # AUDIO1793 «bajá el volumen de Spotify» → «Spotify está cerrado. El
            # volumen es de 85. No hay sonido.»: the application volume final
            # names the application and its observed level and claims nothing
            # about the application being closed, open or silent.
            app_label = str(observed_dict.get("app") or "").strip()
            if app_label and _reading_fold(app_label) not in _reading_fold(stripped):
                return "missing_name"
            level_value = observed_dict.get("level")
            if isinstance(level_value, int) and not re.search(
                rf"(?<![\d.,]){level_value}(?!\d|[.,]\d)", stripped
            ):
                return "missing_name"
            # AUDIO1799: «not silenced» / «no está silenciado» reads the unmuted
            # sessions truthfully; only an affirmed silence is invented.
            unnegated = re.sub(
                r"\b(?:not|isn't|is\s+not|no|no\s+est[aá]n?|no\s+quedo|no\s+quedan?|sin(?:\s+estar)?)\s+"
                r"(?:silenciad[oa]s?|silenced|en\s+silencio|mute[d]?|muteado)\b",
                " ",
                folded,
            )
            if re.search(
                r"\b(?:cerrad[oa]s?|closed|abiert[oa]s?|is open|no\s+hay\s+sonido|sin\s+sonido|no\s+sound|"
                r"silenciad[oa]s?|silenced|en\s+silencio|mute[d]?|muteado)\b",
                unnegated,
            ) and observed_dict.get("muted") is not True:
                return "extra_claim"
        # cien-106 t006 «el audio está activo al 100 %»: a percentage is the level said.
        if "level" in observed_dict and not re.search(
            r"volumen|volume|\bnivel\b|\blevel\b|\d\s*%|\bpor\s*ciento\b|\bpercent\b", folded
        ):
            return "missing_name"
        place_clock = _place_clock_facts(
            _merged_observed(situation), user_text, _message_response_language(user_text),
        )
        if place_clock is not None and not _names_clock_place(stripped, str(place_clock["place"])):
            return "missing_state"
        # The time of another place is the clock this reply owes, next to the
        # time it converts; this PC's own clock is not the answer then.
        clock = str(place_clock["clock"]) if place_clock is not None else _local_clock_from_situation(situation)
        date_requested = clock and place_clock is None and asks_calendar_part(user_text)
        hours_left: tuple[tuple[int, int], ...] = ()
        if date_requested:
            local = _local_datetime_from_observed(_merged_observed(situation))
            calendar = _calendar_facts(local, user_text, "es") if local is not None else {}
            if local is None or _misses_calendar_facts(stripped, calendar):
                return "missing_name"
            # M87 (DEV-D v3r D-s001 «¿cuántas horas quedan para el finde?» → «Hoy es miércoles y quedan 54 horas y 46
            # minutos para el fin de semana.», refused as reversed_result): the hours left that M85 counts read like
            # a clock («54 horas y 46») and are the answer, not a contrary clock claim, as a countdown's are.
            counted = re.fullmatch(r"(\d+) h(?: (\d+) min)?", str(calendar.get("hours_until") or ""))
            if counted is not None:
                hours_left = ((int(counted[1]), int(counted[2] or 0)),)
        clock_required = not date_requested or names_the_time(user_text)
        given = place_clock.get("given") if place_clock is not None else None
        allowed_clock_values: tuple[tuple[int, int], ...] = (
            ((int(given[:2]), int(given[3:])),) if isinstance(given, str) else ()
        ) + hours_left
        later = clock_later_asked(user_text) if clock and place_clock is None else None
        later_local = _local_datetime_from_observed(_merged_observed(situation)) if later is not None else None
        if later is not None and later_local is not None:
            # A7 C (DEV-A3 t217 «¿qué hora será de aquí a doce minutos?»): the payload carries the clock later on
            # (M40); the reply owes that time, and naming the current one next to it is no contrary claim.
            then = later_local + timedelta(minutes=later[1])
            allowed_clock_values += ((later_local.hour, later_local.minute),)
            clock = f"{then.hour:02d}:{then.minute:02d}"
        countdown_asked = countdown_target(user_text) if clock else None
        if countdown_asked is not None:
            # CLOCK1331 H0399: «Faltan 13 horas y 48 minutos para las 3 de la
            # tarde» answers the countdown; the observed clock is optional and
            # the target and remaining figures are not contrary clock claims.
            clock_required = False
            local = _local_datetime_from_observed(_merged_observed(situation))
            if local is not None:
                facts = _countdown_facts(local, countdown_asked, "es")
                target_hour, target_minute = (int(part) for part in countdown_asked.split(":", 1))
                allowed_clock_values = (
                    (target_hour, target_minute),
                    (int(facts["remaining_hours"]), int(facts["remaining_minutes"])),
                )
        if clock:
            clock_defect = _clock_fact_defect(
                stripped, clock, required=bool(clock_required), allowed=allowed_clock_values,
            )
            if clock_defect:
                return clock_defect
        if clock and re.search(
            r"\bset (?:the )?clock\b|\bconfigure\b|ponga el reloj",
            folded,
        ):
            return "extra_claim"
        # Libro de cuentas del redactor (extra_claim −27: «He copiado al portapapeles: "reunion jueves 15:00 sala 3".», 24
        # vetoes): the text a verified clipboard write put there (the request's literal, as in the writer's payload) is
        # the person's, like a record's title: its clock and its question are not BAXY's. Never a message's text: a
        # quoted question was what stopped «Ya le llegó a Ron92 el mensaje «…».» over a draft never sent.
        receipt_texts = _situation_record_titles(situation) + [
            copied for copied in [literal_clipboard_write_text(user_text or "")]
            if copied and operation == "clipboard.write.text" and situation.get("verified") is True
        ]
        if scheduled_dues:
            scheduled_defect = _scheduled_notification_defect(stripped, scheduled_dues)
            if scheduled_defect:
                return scheduled_defect
        elif not clock and any(
            # Uso real 2026-09-23 «qué alarmas hay puestas»: the listing gives each
            # alarm's next run in local time and the answer has to say it; only a
            # clock that no listed alarm has is invented. The same holds for the
            # sun times a weather read observed. Libro de cuentas del redactor («He copiado al portapapeles: "reunion
            # jueves 15:00 sala 3".», 24 vetoes): nor is one inside the text the receipt carries (``receipt_texts``).
            f"{int(hour):02d}:{minute}" not in _observed_local_clocks(situation)
            for hour, minute in re.findall(
                r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)", _without_record_titles(stripped, receipt_texts),
            )
        ):
            return "extra_claim"
        question_text = stripped
        if _recalled_records(situation) and _RECALLED_AS_OWN.match(stripped) is not None:
            # MEMORY1599 «Como me llamo» → «Me llamo Valentina.»: the recalled
            # record is the person's; said in the first person it becomes BAXY's.
            return "recalled_as_own"
        deferred_clarification = _deferred_clarification_for(user_text, situation)
        if deferred_clarification is not None:
            # AUDIO858 H0067 «subí el volumen y decime qué fecha es», H0527
            # «listá las ventanas y enfocá la mejor»: the final owes one
            # question for the clause the turn could not complete; judged
            # apart from the read it reports.
            deferred_defect = _deferred_question_defect(stripped, deferred_clarification)
            if deferred_defect:
                return deferred_defect
            question_text = _without_deferred_question(stripped)
        if _guarded_add_not_run(user_text, situation) is not None and _undenied_claim(_LIST_ADD_CLAIM, stripped):
            # Tanda 4c: the read found the entry, so the add that waited on it never ran.
            return "extra_claim"
        if (
            operation in {"browser.navigate", "browser.navigate.named"}
            and situation.get("verified") is True
            and situation.get("succeeded") is True
        ):
            observed_urls = {
                value for key in ("requestedUrl", "finalUrl")
                if isinstance(value := observed_dict.get(key), str) and value
            }
            # WEB1477 «Abre la página oficial de Wikipedia»: the navigation
            # ended at www.wikipedia.org and the final cited another search
            # result as «la URL visitada». Only the navigated address may be
            # reported.
            navigated = {value.rstrip("/").casefold() for value in observed_urls}
            for found in re.finditer(r"""(?<![\w:/])https?://[^\s<>"'“”‘’]+""", stripped, flags=re.IGNORECASE):
                cited = found[0].rstrip(".,;:!)]}»").rstrip("/").casefold()
                if navigated and cited not in navigated:
                    return "wrong_address"
            question_text = re.sub(
                r"""(?<![\w:/])https?://[^\s<>"'“”‘’]+""",
                lambda found: found[0].replace("?", "") if (
                    found[0] in observed_urls
                    or found[0].rstrip(".,;:!)]}»") in observed_urls
                ) else found[0],
                stripped,
                flags=re.IGNORECASE,
            )
        if (
            operation in _MEDIA_TITLE_OPERATIONS
            and situation.get("verified") is True
            and situation.get("succeeded") is True
        ):
            # Tanda 5b «busca podcast y reprodúce lo»: the playing video was «… | Seré Weón? 👀 - YouTube»; its «?»
            # is the title's, not BAXY asking, and all three drafts died on it. Written without the tab's
            # « - YouTube», or by its names, it is the same title (tanda 6b: any observed media title).
            question_text = without_observed_names(question_text, situation)
            played = observed_dict.get("title") if isinstance(observed_dict, dict) else None
            if isinstance(played, str) and played.strip():
                question_text = _without_media_title(question_text, played)
        if _verified_titled_item_write(situation, operation, cause):
            # M146 (DEV-F v4p F-w47-t4 «Apúntamelo en una nota…»): the note was stored with the person's question as its
            # title («…¿cuántos dólares me dan hoy por cada euro»); quoted as observed it is the note's name, not BAXY
            # asking, like a media title above. A question of BAXY's own words is still one.
            for written in [situation, *_situation_steps(situation)]:
                stored = written.get("observed") if isinstance(written.get("observed"), dict) else {}
                title = stored.get("title")
                if isinstance(title, str) and title.strip():
                    question_text = re.sub(re.escape(title.strip()), " ", question_text, flags=re.IGNORECASE)
        # M153: so is a reminder's or an alarm's title («¿Tomaste la pastilla?»), or a task's in a list read.
        question_text = _without_record_titles(question_text, receipt_texts)
        # Revisión 1 de r24b (B3): the field a computer-use mission left the cursor in, quoted as the window names it
        # («¿Qué quieres reproducir?»), is the window's words, not BAXY asking (computerUse.searchOpened). An unquoted
        # question is still BAXY's.
        question_text = _without_quoted_focused_field(question_text, situation)
        if (
            operation == "web.search"
            and situation.get("verified") is True
            and situation.get("succeeded") is True
        ):
            # WEB1447 «va a llover mañana»: a quoted result title such as
            # «Tiempo en Santiago mañana — ¿Va a llover? | tiempo.cl» is an
            # observed name, not a question the assistant asks.
            question_text = without_observed_names(question_text, situation)
            # tanda-02 (the time in another city): «example.net says: "What time
            # is it in that city right now? See the live clock…"» quotes the
            # page, and the page's question inside the quotation is not the
            # assistant asking. Only a quotation the results carry verbatim is
            # the page's; an unquoted question is still BAXY's.
            def words_of(value: str) -> str:
                return " " + " ".join(re.findall(r"\w+", _reading_fold(value))) + " "

            page_words = words_of(" ".join(
                str(item.get(key) or "")
                for item in _search_results_of(situation) if isinstance(item, dict)
                for key in ("title", "snippet")
            ))
            question_text = re.sub(
                r"[«\"“][^»\"”]{1,600}[»\"”]",
                lambda quoted: " " if (
                    len((quoted_words := words_of(quoted.group(0)[1:-1])).split()) >= 3
                    and quoted_words in page_words
                ) else quoted.group(0),
                question_text,
            )
        if (
            operation == "client.channel.locate"
            and situation.get("verified") is True
            and situation.get("succeeded") is True
        ):
            # DISCORD1839: the observed channel name may itself contain «?»/«!»
            # («Cotele!!!??»), and the finding legitimately ends by asking
            # whether to join. Neither is the assistant asking an unsolicited
            # question: remove the observed names and the one trailing question
            # before the check. The joined_claimed veto still guards a false
            # claim of having joined.
            for _key in ("channelName", "server", "query"):
                _value = observed_dict.get(_key) if isinstance(observed_dict, dict) else None
                if isinstance(_value, str) and _value.strip():
                    question_text = question_text.replace(_value, " ")
            question_text = re.sub(r"[¿?][^?¿]*\??\s*$", "", question_text).strip()
        if (
            operation == "notification.list"
            and situation.get("verified") is True
            and situation.get("succeeded") is True
            and plural_alarm_cancellation(user_text or "")
        ):
            # D39 (owner, 2026-09-29): «cancela las alarmas» is answered by the alarms read and the one question
            # whether to cancel them (_alarm_offer_defect demands it); that trailing question is the owner's.
            question_text = re.sub(r"[¿?][^?¿]*\??\s*$", "", question_text).strip()
        if _new_empty_list(user_text, situation) is not None:
            # D59.5 (owner, 2026-10-02): the new list made empty is answered with the one question offering to add
            # things to it; that trailing question is the owner's. Nothing was put on it.
            question_text = re.sub(r"[¿?][^?¿]*\??\s*$", "", question_text).strip()
            if re.search(r"\b(?:añad[ií]|anad[ií]|agregu[eé]|anot[eé]|puse|apunt[eé]|added|put|wrote)\b", question_text,
                         re.IGNORECASE):
                return "extra_claim"
        if operation == "web.news.headlines":
            question_text = _without_quoted_headlines(question_text, situation)
        if (
            operation == "web.news.headlines"
            and situation.get("verified") is True
            and situation.get("succeeded") is True
            and isinstance(observed_dict, dict)
            and isinstance(observed_dict.get("headlines"), list)
        ):
            # M77 (DEV-D v3l D-s032 «Noticias sobre Taylor Swift»): the headline «La crítica se harta de Taylor Swift,
            # pero… ¿es ‘Cleveland’ tan mala?» quoted with its words is the outlet asking, not BAXY, and the draft that
            # quoted three headlines died as extra_claim. A question whose words are an observed headline's is that
            # headline's.
            headline_words = [
                f" {_headline_words(str(item.get('title') or ''))} "
                for item in observed_dict["headlines"] if isinstance(item, dict)
            ]

            def headline_question(found: re.Match[str]) -> str:
                words = _headline_words(found.group(0))
                return " " if words and any(f" {words} " in title for title in headline_words) else found.group(0)

            question_text = re.sub(r"¿?[^¿?.;:!]*\?", headline_question, question_text)
        if "?" in question_text or "¿" in question_text:
            return "extra_claim"
        closed_request = asks_to_close(user_text)
        # H0516 «… y luego cierra Opera»: en una misión de varios pasos el cierre
        # no trae nombre de aplicación en lo observado, y exigir «ventana» a
        # «cerré Opera GX» tumbaba un final fiel. Si la persona nombró lo que
        # había que cerrar y el final repite ese nombre, está nombrado.
        closed_object = object_asked_to_close(user_text)
        closed_named = bool(
            closed_object
            and closed_object not in {"todo", "everything", "all", "eso", "esto", "that", "it", "lo", "la"}
            and closed_object in folded
        )
        if (
            closed_request
            # «¿a qué hora cierra el museo?» asks a page, not to close anything.
            and operation not in {"browser.control", "web.search"}
            and not (isinstance(app_name, str) and app_name.strip())
        ):
            # BROWSER1841 «close all tabs»: closing tabs names «pestañas»/«tabs»,
            # not a window; the close_all narration is guarded by its own lens.
            if not closed_named and "ventana" not in folded and "window" not in folded:
                return "missing_name"
            # Nombrar lo cerrado exime de «ventana», no de decir que se cerró: un
            # final que abre Opera GX y calla el cierre no cuenta la misión.
            if not re.search(r"cerrad|closed|\bcerr[eé]\b|\bcerramos\b", folded):
                return "missing_state"
    if cause == "mission_completed" and (picture := _downloaded_and_opened_picture(situation)) is not None:
        # MEME2055: the picture the viewer shows is named by its file.
        # The stem alone («meme») is the noun asked, not the file: the name
        # with its extension is what the viewer shows.
        if _reading_fold(picture[0]) not in folded:
            return "missing_name"
    if cause == "mission_completed":
        skip = {
            "abri",
            "cree",
            "puse",
            "listo",
            "nota",
            "the",
            "and",
            "volume",
            "volumen",
            "puse",
            "creé",
            "la",
            "el",
            "las",
            "los",
            "una",
            "uno",
            "con",
            "exito",
            "éxito",
            "success",
        }
        for step in situation.get("steps") or []:
            if isinstance(step, str) and step.lstrip().startswith("{"):
                continue
            tokens = [
                token
                for token in re.findall(r"[A-Za-zÁÉÍÓÚÜáéíóúüñÑ]{3,}|\d+", str(step))
                if token.casefold() not in skip
            ]
            if tokens and not any(token.casefold() in folded for token in tokens):
                return "missing_name"
    # Tanda 6 («nunca inventa»): whatever the route, no date about today that this PC's calendar denies.
    calendar = _calendar_contradiction(stripped, user_text, _reply_calendar_moment(_situation_from_facts(facts)))
    if calendar:
        return calendar
    if kind == "operation" and situation.get("operation") == "mission.computer.use":
        # cu-r16: every word of a mission final comes from the facts, the person's words or BAXY's own vocabulary.
        # Judged after the named vetoes, so a draft with one of them is told that one first. Ronda 21: not a failed
        # mission's final, whose cause is told in the writer's own words (r5a M6, g1); the named vetoes judge it.
        from . import cu_projection as _cu_projection
        from . import cu_reply_checks as _cu_reply_checks

        if _cu_reply_checks.ungrounded_word(
            _accent_folded_with_punctuation(stripped),
            _cu_projection.project_seen(_merged_observed(situation), "es"),
            " ".join(part for part in (user_text, said) if part),
        ) is not None:
            return "ungrounded_word"
    if claim := _claims_defect(stripped, intent, reported):
        return claim
    # M62 (v3e2-final F-p07-t4 «Have a great day, BAXY!»): BAXY never calls the person by its own name. Judged last,
    # so a draft with another defect is told that one first.
    return "person_called_baxy" if visible_reply_calls_the_person_baxy(stripped) else ""


_INTERNAL_IDENTIFIER_SAID = re.compile(
    r"\b(?:hwnd|handle|pid|process\s*id|id\s+del?\s+proceso|identificador\s+(?:del?\s+)?(?:proceso|ventana)|"
    r"identificador)\b[^.!?\d]{0,24}\d{3,}"
)


def visible_reply_says_an_internal_identifier(text: object, user_text: str) -> bool:
    """The reply says a handle or process id with its number, and the person did not ask for one (see above)."""

    return not asks_for_an_internal_identifier(user_text) and (
        _INTERNAL_IDENTIFIER_SAID.search(_reading_fold(str(text or ""))) is not None
    )


# A verified send said as such. MAIL1859: «le dije X a Y», «le escribí», «I told them» state the delivery of a send
# operation as plainly as «envié»; in a mission «escribí» is its typing part, never the send (encargo E).
_SENT_SAID = r"envie|envio|enviado|enviada|mande|mando|mandado|sent|delivered|entregue|entregado"
_SEND_STATED = re.compile(rf"\b(?:{_SENT_SAID})\b")
_SEND_TOLD = re.compile(
    rf"\b(?:{_SENT_SAID}|dije|dijo|dicho|escribi|escribio|escrito|avise|aviso|avisado|comunique|comunico|"
    r"told|said|wrote|written|passed\s+along)\b"
)


def _send_not_stated(reply: str, situation: dict, mission: bool) -> bool:
    """Whether a final over a verified send (``semantic.messaging.verified_send``: a send operation, or a mission whose
    part «enviar» held on the text seen sent) says nothing of the send: one veto for every send (MSGSEND1845, encargo
    E). In a mission only a word of sending says it; «escribí» is its typing part."""

    if not semantic_messaging.verified_send(situation):
        return False
    stated = _SEND_STATED if mission else _SEND_TOLD
    return stated.search(_accent_folded_with_punctuation(reply)) is None
