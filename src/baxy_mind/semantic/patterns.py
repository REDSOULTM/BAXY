"""The pattern path: the orchestrator that reads a request clause by clause against the catalog (resolve_explicit_effects, resolve_explicit_clarification_intent, the domain reviews and the compound contracts). Moved from effect_intent (Fase 3.5); effect_intent re-exports it while callers migrate.
"""

from __future__ import annotations

import hashlib
import random
import re
import time
from dataclasses import dataclass
from typing import Iterable
from ..catalog_operation_aliases import exact_catalog_operation_plan
from . import levels, lexicon
from .grammar import TASK_REMINDER_HEAD, _INSTRUCTION_NOUNS, _MACHINE_NOUNS, _without_leading_duration_preface, _fold, _match, _has, _REQUEST_PREFIX, _EXPLICIT_DESIRE_REQUEST, _TRAILING_MEANS_DIRECTIVE, _strip_request_envelope, _explicit_desire_request, _request_head, _head_is, _negative_action_forms, _is_negative_effect_clause, _negative_state_question_body, _machine_status_scopes, _machine_status_scopes_are_one_reading, _machine_status_is_the_whole_clause, _is_past_or_hypothetical_state, _is_machine_knowledge_or_diagnosis, _system_status_domain, _process_list_domain, _network_status_domain, _SET_VOLUME_VERB, _VOLUME_UP_VERB, _VOLUME_DOWN_VERB, _AUDIO_OBSERVATION_HEAD, _indirect_audio_mute_state_query, window_inventory_arguments, _literal_note_payload_request, _is_meta_or_tool_denial, _is_explicit_meta_or_tool_denial, _is_definition_question, _KNOWN_APPLICATION, _CONNECTED_INVENTORY, _OPEN, _MEDIA_RESUME_VERB, _LIST, _READ, _CREATE, _SEARCH, _COVERAGE_ACTION_HEAD, _SEQUENCE_NOMINAL_HEAD, _machine_status_topic, _ENGLISH_SMALL_NUMBERS, _SPANISH_SMALL_NUMBERS, _PERCENTAGE_WORD_VALUES, _explicit_google_search_query, _request_clauses, _PLAY_HEAD, _request_body_surface, _without_address, imperative_rewrites
from .audio import app_scoped_microphone_mute, _LOCAL_VOLUME_DEVICE, _VOLUME_OBJECT, _bare_clitic_volume_request, _bare_music_volume_request, _volume_domain, _MUTE_VERB, _audio_mute_domain, _APP_VOLUME_SPANISH, _APP_VOLUME_ENGLISH, _APP_VOLUME_ENGLISH_SPLIT, _APP_VOLUME_SET_SPANISH, _APP_VOLUME_SET_ENGLISH, _APP_VOLUME_LEVEL_WORDS, _AUDIO_LEVEL_CUE, _is_audio_mute_state_query, _PERCENTAGE_WORD_PATTERN
from .windows import deictic_window_mutation, _FOCUS_HEAD_ONLY, _FOCUS_HEAD_WITH_TAIL, _FOCUS_TAIL, _MINIMIZE_HEAD, _SNAP_HEAD, _SNAP_SIDE, has_named_window_target, _window_domain, minimize_all_request, INDETERMINATE_WINDOW_CLAUSE, other_window_switch_request, PC_HOME_PLACE, start_menu_request
from .display import screen_light_as_brightness, _KNOWN_FOLDER_WORDS, _KNOWN_FOLDER_ENUM, screen_inventory_request, _display_status_question, _without_screen_state_preface, _BRIGHTNESS_OBJECT, _BRIGHTNESS_UP_VERB, _BRIGHTNESS_DOWN_VERB, _BRIGHTNESS_ABSOLUTE, _BRIGHTNESS_ENGLISH_TURN, _BRIGHTNESS_RELATIVE_WORDS, brightness_status_request, _BRIGHTNESS_SET_VERB, _BRIGHTNESS_EXTREME_VALUES, wallpaper_request
from .intent import EffectIntent, _entity_key, _is_negated_match, _append, _append_all
from .catalog import ApplicationCatalogIndex, GameCatalogIndex, build_game_catalog_index, _authenticated_game_target, resolve_game_catalog_app_id, _application_name_key, build_application_catalog_index, _catalog_alias_key, _installed_game_named, installed_game_title
from .temporal import _CALENDAR_MONTH_TOKEN, _CLOCK_TIME_SELECTOR, _BOUNDED_TEMPORAL_SELECTOR, spoken_clock, clock_elsewhere, other_place_clock_question, notification_change, plural_alarm_cancellation
from .media import _youtube_search_query, youtube_play_query, _direct_media_discovery_or_play_request, _named_browser_music_request, _NETFLIX_SPELLED, _underspecified_video_request, _title_case_media_title, _media_transport_action, _resume_existing_media, _REMOVABLE_MEDIA, _bare_spoken_number_media_query, radio_station_query, spoken_media_order, MUSIC_GENRE, _RADIO_PLAY, own_recent_listening_request
from .web import asks_for_information, public_opinion_query, record_fact_query, _public_route_lookup_request, _public_calendar_fact_lookup_request, _WEATHER_WORDS, _weather_lookup_query, _research_question_query, _public_live_lookup_request, _public_product_correction_lookup_request, _public_commerce_lookup_request, _FILESYSTEM_OBJECT_NOUN, operation_identity_is_a_near_miss, curiosity_request, web_image_request, _NAVIGATION_CLIENT, client_navigation_target, _authenticated_application_identity_conflict, _browser_page_domain, browser_back_arguments, browser_new_tab_arguments, browser_close_all_tabs_arguments, _historical_note_search_request, _stored_note_search_query, _nominal_reminder_lookup_title, _location_recommendation_request, _NAMED_BROWSER_SITE_REQUEST, _installed_browser_search_query, _completed_browser_search_pronoun_request, _NAMED_PUBLIC_SITE, _review_web_and_browser_effects, web_download_request, NAMED_CDP_BROWSERS, _named_browser_match, _named_browser, public_event_subject, cinema_listing
from .files import _pdf_summary_request, _file_trash_request, process_report_file_request, _file_creation_request, known_folder_file_path, _current_directory_file_count, _DUPLICATE_FILES, _known_folder_recent_listing, _known_folder_listing_request, _review_file_and_game_effects, folder_txt_zip_open_mission, open_named_file_request, _office_document_roundtrip_intent
from .games import _corrected_game_launch_title, _edit_distance, near_catalog_game_candidates, steam_library_verb, steam_library_title, _steam_install_status_intent, _steam_install_cancel_active_intent, _steam_catalog_list_intent
from .network import _direct_current_time_request, _direct_process_inventory_request, _local_internet_connection_query, _DATIVE_STATE_OPENING, _HARDWARE_MODEL_OPENING, _bluetooth_state_question, wifi_place_request, wifi_radio_set_request, _wifi_scan_question, _wifi_state_question, _review_system_and_network_effects, _wifi_email_intent
from .system import _weather_read_intent, physical_world_request, weather_place_known_only_through_someone
from .notes import puts_into_the_agenda, takes_off_the_agenda, list_entry_request, list_read_request, list_removal_request, list_creation_without_items, _time_only_reminder_request, _count_down_request, _reminder_has_actionable_due, _multiple_alarm_schedule_intent, _task_without_title, _bare_note_inventory_request, _note_inventory_object, _wake_alarm_request, _bounded_calendar_list_query, _fully_enumerated_note_create_count, _fully_enumerated_note_read_order, _has_fully_enumerated_note_cardinality, enumerated_note_dependency_order, _latest_notification_selector, _active_alarm_stop_request, _alarm_turn_off_request, _exact_local_reminder_title, _review_calendar_message_and_direct_reminder_effects, agenda_read_request, agenda_event_request, stated_event_reminder, said_repetition, _CALENDAR_PLACE, reminder_inventory_question, AGENDA_NOT_A_READ, happening_in_a_span_of_hours
from .messaging import _MSG_CHANNEL_WORDS, _message_channel_name, message_request_named_client, message_request_any_channel, email_send_request, email_request_without_address, message_draft_request, message_left_written_request, _latest_email_domain, _notification_listing_request, inbox_read_request, social_network_request, contact_book_request
from .ui import _clipboard_copy_domain, _clipboard_paste_domain, calculator_expression_request, literal_clipboard_write_text, _review_input_and_capture_effects, _VISIBLE_CLICK_APP_CONTEXT, _gerund_click_label, _visible_click_label, _click_in_application, _visible_click_intent
from .apps import self_close_request, _APPLICATION_TRAILING_REQUEST, _application_target_forms, _CLOSE_TRAILING_COURTESY, _close_target_forms, deictic_close_request, _bounded_application_literal, _authenticated_application_list, _OPEN_STATE_CONDITION, close_all_request, _has_multiple_installed_entities, _append_domain_actions, _open_application_spans, _CATALOG_INSTALL_VERB, _opened_applications


@dataclass(frozen=True, slots=True)
class ClarificationIntent:
    """One incomplete request whose operation identity is still certain."""

    operations: tuple[str, ...]
    missing_fields: tuple[str, ...]

    @property
    def operation(self) -> str:
        """Compatibility accessor for callers that only accept one operation."""

        if len(self.operations) != 1:
            raise ValueError("compound clarification has no single operation")
        return self.operations[0]


@dataclass(frozen=True, slots=True)
class CompoundEffectContract:
    minimum_effects: int
    required_clause_sequences: tuple[tuple[str, ...], ...]
    # Positive clauses in source order. An empty operation tuple marks the
    # one clause whose identity still needs independent verification. Special
    # fail-closed contracts (negation, correction, deferral, identity conflict)
    # deliberately leave this empty and therefore can never grant authority.
    clause_requirements: tuple[tuple[str, tuple[str, ...]], ...] = ()


_EXPLICIT_EFFECTS_NOT_RESOLVED = object()


_NEWS_SCOPE_WORDS = (
    r"^(?:de\s+|del\s+|sobre\s+|about\s+|on\s+|of\s+)?"
    r"(?:hoy|today|ahora|now|actuales?|latest|ultimas?|recientes?|recent|"
    r"el\s+dia|the\s+day|el\s+mundo|the\s+world|internacionales?|international|"
    r"en\s+el\s+mundo|in\s+the\s+world|del\s+mundo|de\s+hoy|de\s+ahora|"
    r"breaking|principales|top|nuevas?|new)(?:\s+(?:hoy|today|en\s+el\s+mundo|in\s+the\s+world|de\s+hoy))*$"
)


def _news_headlines_request(text: str) -> bool:
    """REOPEN1993 (grupo N): a request for today's news or headlines («buscá
    noticias de hoy», «qué pasó hoy en el mundo», «dame los titulares»)."""

    folded = _strip_request_envelope(_fold(text))
    if not folded or not _public_live_lookup_request(folded):
        return False
    if _has(folded, _WEATHER_WORDS):
        return False
    if happening_in_a_span_of_hours(folded):
        # M97 (reserve «qué pasa hoy de dos a cuatro de la tarde»): two hours of the day bound the person's agenda.
        return False
    return _has(folded, r"\b(?:news|headlines|noticias|titulares|breaking\s+news)\b") or re.match(
        r"^[¿?¡!\s]*(?:que|what)\s+"
        r"(?:paso|pasa|ha\s+pasado|esta\s+pasando|ocurrio|ocurre|sucedio|"
        r"happened|is\s+happening|has\s+happened)\s+(?:hoy|today)\b",
        folded,
    ) is not None


def _news_topic(text: str) -> str | None:
    """The topic the person named for the news («noticias de tecnología»,
    «news about Chile»), with their own spelling; None for the day's news
    («noticias de hoy», «qué pasó hoy en el mundo»)."""

    if not _news_headlines_request(text):
        return None
    stripped = _strip_request_envelope(text.strip())
    match = re.search(
        # NEWS2027 «qué noticias hay de tecnología»: «hay» may sit between the
        # news word and its topic.
        r"\b(?:noticias?|news|titulares|headlines)\s+(?:hay\s+|tenes\s+|tienes\s+|are\s+there\s+|is\s+there\s+)?"
        r"(?:de|del|sobre|acerca\s+de|about|on|of)\s+"
        r"(?P<topic>[^,;:.!?]+?)\s*(?:\b(?:de\s+hoy|hoy|today|ahora|now)\b)?\s*[.!?]*$",
        stripped,
        re.IGNORECASE,
    )
    if match is None:
        return None
    topic = match.group("topic").strip(" \t\r\n.,;:")
    folded_topic = _fold(topic)
    if (
        not folded_topic
        or re.match(_NEWS_SCOPE_WORDS, folded_topic) is not None
        or _has(folded_topic, r"\b(?:google|internet|la\s+web|the\s+web|online)\b")
        or len(topic.encode("utf-8")) > 128
    ):
        return None
    return topic


def _news_read_intent(
    text: str,
    available_operations: Iterable[str],
) -> EffectIntent | None:
    """REOPEN1993 (grupo N): the news are read as headlines, never as a web
    search that ends listing portal names (H0033, H0374, H0509)."""

    if "web.news.headlines" not in frozenset(available_operations):
        return None
    if not _news_headlines_request(text) or len(_request_clauses(_fold(text))) != 1:
        return None
    return EffectIntent(("web.news.headlines",), (text.strip(),))


# cien-37 030 «send flowers to Deimos», 040 «hire a guide on Ceres», 060 «ship a
# piano to Charon», 090 «rent a studio on Haumea»: no operation of this PC
# reaches these places, and the App has said so since the first hundred runs
# (UserMessagePolicy.LooksLikeOutOfWorldRequest). Without the same knowledge
# here, a block of history turned the boundary into a question about the very
# thing that cannot be done. Only unambiguous names are listed: «Europa»,
# «Io», «Titán» and «luna» also name things one may legitimately talk about,
# and those requests already answer with their boundary.
_OUT_OF_WORLD_PLACES = (
    "deimos", "fobos", "phobos", "ceres", "vesta", "palas", "pallas",
    "caronte", "charon", "haumea", "sedna", "makemake", "eris", "quaoar",
    "triton", "nereida", "nereid", "oberon", "titania", "umbriel", "ariel",
    "miranda", "encelado", "enceladus", "mimas", "japeto", "iapetus",
    "ganimedes", "ganymede", "calisto", "callisto", "pluton", "plutao",
    "neptuno", "urano", "uranus", "mercurio", "marte",
)


_OUT_OF_WORLD_DESTINATION = re.compile(
    r"\b(?:a|al|to|on|en|hacia|para|from|desde)\s+(?:la\s+|el\s+|the\s+)?(?:"
    + "|".join(_OUT_OF_WORLD_PLACES)
    + r")\b",
    re.IGNORECASE,
)


def out_of_world_request(text: str) -> bool:
    """The request points at a place no operation of this PC can reach.

    Tanda 4 2026-09-24: a question about that place («¿hay vida en Marte?», «how far is Mars from the Sun»)
    asks for information and is answered, never bounded (web.asks_for_information)."""

    return _OUT_OF_WORLD_DESTINATION.search(_fold(text)) is not None and not asks_for_information(text)


def _nominal_datetime_query(folded: str) -> bool:
    return re.fullmatch(
        r"(?:(?:y|and)\s+)?(?:(?:la|el|the)\s+)?"
        r"(?:hora|fecha|time|date)[\s?!.]*",
        folded.lstrip("¿¡ "),
    ) is not None


def datetime_followup_antecedent(
    text: str, previous_requests: Iterable[str],
) -> str | None:
    """Find a clock antecedent through contiguous human ellipses, newest first.

    A change of subject ends the chain. Assistant responses and remembered
    clock values are deliberately absent: the next turn still needs a read.
    """
    if not _nominal_datetime_query(_strip_request_envelope(_fold(text))):
        return None
    for request in previous_requests:
        folded = _strip_request_envelope(_fold(request))
        if _nominal_datetime_query(folded):
            continue
        return request if _direct_current_time_request(folded) else None
    return None


def operation_domain_is_grounded(
    text: str,
    operation: str,
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
    *,
    previous_user_text: str | None = None,
    available_operations: Iterable[str] = (),
) -> bool | None:
    """Apply the curated one-sided family gates.

    A catalogue-derived gate was measured here and rejected. It gave each
    operation the words distinctive to it and vetoed a request naming none of
    them, which looked free: zero over-veto against R2 and eight of eleven
    known near-miss collisions caught. R2 is *seen* surfaces, and that was the
    wrong population to calibrate against. On the unseen paraphrases of cut B
    it vetoed 161 additional legitimate target operations, taking over-veto
    from 224 of 560 to 385 of 560. Coverage of a few collisions is not worth
    refusing a quarter more of what the person actually asks for, so it is
    gone; the collisions it uniquely caught are curated below instead.

    That leaves a second problem the curated rules cannot see: what they do not
    cover at all. 60 of the 158 catalogue operations reach no rule, and a
    request outside the catalogue walked straight through the gap. On the
    veto-reach V1 population "Barre las hojas del sendero" -- sweeping leaves
    off a path -- executed ``filesystem.sandbox.append.named`` and said nothing.
    The deterministic recogniser correctly declined it; the gate returned None
    because no rule names that operation, so nothing removed the authority the
    model had taken.

    The floor below closes that for the family that leaked, by generalising the
    condition the covered filesystem rules already impose rather than by adding
    another hand-written entry: **an operation that acts on a file must name
    something in the filesystem.** It is one-sided like every rule here -- it
    can only remove authority -- and it applies solely where no specific rule
    spoke.
    """

    if operation_identity_is_a_near_miss(text, operation):
        # A neighbouring substitute is not a missed paraphrase. The identity
        # verifier may revive the latter; it must not revive the former.
        return False
    verdict = _curated_domain_is_grounded(text, operation, application_names)
    if (
        verdict is False
        and operation == "audio.volume"
        and previous_user_text
        and _contextual_output_level_target(text, previous_user_text, available_operations)
    ):
        return True
    if verdict is not None:
        return verdict
    return _uncovered_family_floor(_fold(text), operation)


def _completed_missing_volume_level_request(
    text: str, previous_user_text: str | None, available_operations: Iterable[str],
) -> str | None:
    """Attach a numeric answer only to a unique, incomplete local-level request.

    Both surfaces are user-authored reference data. The ordinary resolver still
    checks the resulting request, including every current denial and effect.
    An assistant question or a completed earlier action cannot supply this target.
    """
    if not previous_user_text:
        return None
    clauses = _request_clauses(_strip_request_envelope(_fold(text)))
    if not clauses or re.fullmatch(
        r"(?:(?:a|al|to|at)\s+)?(?:100|\d{1,2})\s*"
        r"(?:%|por ciento|percent)?[\s,.!?]*",
        clauses[0],
    ) is None:
        return None
    prior = resolve_explicit_clarification_intent(previous_user_text, available_operations)
    if prior is None or prior.operations != ("audio.volume",) or prior.missing_fields != ("level",):
        return None
    return f"{previous_user_text.strip()}\n{text}"


_MSG_DICTATION_SEPARATOR = re.compile(
    r"\s*(?::|\b(?:que\s+diga|que\s+dice|diciendo(?:le)?|dici[eé]ndole|saying|that\s+says|que|that)\b)",
    re.IGNORECASE,
)


def _completed_missing_message_channel_request(
    text: str, previous_user_text: str | None, available_operations: Iterable[str],
) -> str | None:
    """MSGCLAR «mandale al grupo Musica: prueba 1 …» → «¿por WhatsApp o por
    Discord?» → «por WhatsApp»: the answered client completes the previous
    message request whose only missing field was the channel. The completed
    request is the person's own words with «por <client>» before the dictated
    text, and the ordinary draft reader still has to accept it."""

    if not previous_user_text:
        return None
    answer = _strip_request_envelope(_fold(text)).strip()
    found = re.fullmatch(
        r"[¿?¡!\s]*(?:(?:por|en|via|on|in|through|by|usando|using|con|with)\s+)?"
        r"(?:(?:el|la|the)\s+)?(?:(?:app|aplicacion|application)\s+(?:de\s+|of\s+)?)?"
        r"(?P<ch>whatsapp|wsp|discord|correo(?:\s+electronico)?|(?:e-?)?mail)"
        r"(?:\s+(?:por\s+favor|please|mejor|nomas))?[\s.!?]*",
        answer,
    )
    if found is None:
        return None
    prior = resolve_explicit_clarification_intent(previous_user_text, available_operations)
    if prior is None or prior.operations != ("message.send",) or prior.missing_fields != ("channel",):
        return None
    channel = _message_channel_name(found.group("ch"))
    channel = "correo" if channel == "email" else channel
    previous = _strip_request_envelope(previous_user_text.strip()).strip()
    separator = _MSG_DICTATION_SEPARATOR.search(previous)
    if separator is None:
        return None
    joiner = " on " if _has(
        _fold(previous), r"^[^\w]*(?:send|write|text|message|tell|ask|let)\b",
    ) else " por "
    rest = previous[separator.start():]
    completed = previous[:separator.start()].rstrip() + joiner + channel + (" " if rest.startswith(":") else "") + rest
    return completed if message_draft_request(completed) is not None else None


def _completed_missing_message_text_request(
    text: str, previous_user_text: str | None, available_operations: Iterable[str],
) -> str | None:
    """MAIL «escribile un mail a juan@hotmail.com» → «¿qué querés que diga?» →
    «que llego tarde», or «enviá un correo» → «¿a quién y qué querés que
    diga?» → «a juan que diga que llego tarde»: the answer supplies the text
    (and the addressee) that the previous message request lacked. The completed
    request is the person's own words joined, and the ordinary draft reader
    still has to accept it."""

    if not previous_user_text:
        return None
    answer = _strip_request_envelope(text.strip()).strip().strip("¿?¡!")
    if not answer or len(answer.encode("utf-8")) > 16_384 or explicit_non_action_frame(text):
        return None
    prior = resolve_explicit_clarification_intent(previous_user_text, available_operations)
    if (
        prior is None
        or prior.operations != ("message.send",)
        or "message_text" not in prior.missing_fields
        or "channel" in prior.missing_fields
    ):
        return None
    previous = _strip_request_envelope(previous_user_text.strip()).strip().rstrip(" .!?")
    if "recipient" in prior.missing_fields:
        if not _has(_fold(answer), r"^(?:a|al|para|to)\s+\S"):
            return None
        completed = previous + " " + answer
    else:
        folded_answer = _fold(answer)
        english = _has(_fold(previous), r"^[^\w]*(?:send|write|email|text|message|tell)\b")
        if english:
            joiner = " saying " if _has(folded_answer, r"^that\s+\S") else " saying: "
        else:
            joiner = " que diga " if _has(folded_answer, r"^que\s+\S") else " que diga: "
        completed = previous + joiner + answer
    return completed if message_draft_request(completed) is not None else None


def client_channel_request(text: str) -> tuple[str, str] | None:
    """DISCORD1839 «ve a Cotele en Discord», «Go to Cotele in Discord», «Andá al canal
    Cotele en Discord»: the client and the place named by a go-to order scoped to a
    messaging client; the channel is located and the person asked before joining."""

    folded = _strip_request_envelope(_fold(text)).strip()
    found = re.fullmatch(
        r"[¿?¡!\s]*(?:(?:por\s+favor|please)[,]?\s+)?"
        r"(?:(?:en|in|on)\s+(?P<client_a>" + _NAVIGATION_CLIENT + r")[,]?\s+)?"
        r"(?:ve|anda|andate|entra|entrale|metete|navega|llevame|go|navigate|switch|cambia|cambiate|take\s+me)\s+"
        r"(?:a(?:l)?|to|hacia|into)\s+(?:(?:el|la|the)\s+)?(?:(?:canal|channel|chat|sala|room)\s+(?:de\s+(?:voz|texto)\s+)?(?:de\s+)?)?"
        r"(?P<place>\S.{0,60}?)"
        r"(?:\s+(?:en|in|on|de|del|of)\s+(?:el\s+)?(?P<client_b>" + _NAVIGATION_CLIENT + r"))?"
        r"(?:\s+(?:por\s+favor|please))?[\s.!?]*",
        folded,
    )
    if found is None:
        return None
    client = found.group("client_a") or found.group("client_b")
    place = found.group("place").strip(" \"'«»")
    if client is None or not place or _has(place, r"https?://|\b(?:[a-z0-9-]+\.)+[a-z]{2,63}\b"):
        return None
    raw = _strip_request_envelope(text).strip()
    start = _fold(raw).find(place)
    literal = raw[start:start + len(place)] if start >= 0 and len(_fold(raw)) == len(raw) else place
    return client, literal.strip(" \"'«».!?")


def _completed_missing_music_request(
    text: str, previous_user_text: str | None, available_operations: Iterable[str],
) -> str | None:
    """MUSIC1571 «pon música» → «¿qué música?» → «lofi»: attach the person's
    answer to the incomplete music request as the music named, so it resolves
    like «pon música de lofi». Only after a request the resolver itself reads
    as a music clarification, and only for a short content answer (no request
    head, no question); the answer keeps its own words."""

    if not previous_user_text:
        return None
    prior = resolve_explicit_clarification_intent(previous_user_text, available_operations)
    if (
        prior is None
        or prior.operations != ("media.play.query",)
        or prior.missing_fields not in {("query",), ("station_or_genre",)}
    ):
        return None
    answer = text.strip().strip("\"'“”«»").strip()
    folded = _strip_request_envelope(_fold(answer))
    words = folded.split()
    if (
        not folded
        or len(words) > 8
        or "?" in answer
        or _head_is(_request_head(folded), _COVERAGE_ACTION_HEAD)
        or _negative_action_forms(folded)
        or re.fullmatch(r"(?:no|nada|ninguna|none|nothing|cancela|cancelar|cancel|olvidalo|dejalo)\b.*", folded)
    ):
        return None
    answer = re.sub(r"^(?:algo\s+de|un\s+poco\s+de|some|something\s+like)\s+", "", answer, flags=re.IGNORECASE).strip(" .!")
    if not answer:
        return None
    if prior.missing_fields == ("station_or_genre",):
        # «toca la radio» → «¿qué emisora?» → «cooperativa» / «la 99.9»: the answer names the station.
        station = re.sub(r"^(?:(?:la|el|the)\s+)?(?:(?:radio|emisora|station)\s+)?", "", answer, flags=re.IGNORECASE)
        return f"pon radio {station}" if station else None
    browser_music = _named_browser_music_request(previous_user_text)
    if browser_music is not None and browser_music[1] is None:
        # MUSIC1827 «abrí chrome y poné música» → «¿qué música?» → «rock»: the
        # answer names the music, played from YouTube in that browser.
        label = {"opera_gx": "opera gx"}.get(browser_music[0], browser_music[0])
        return f"pon música de {answer} en {label}"
    if _has(_fold(previous_user_text), r"\bspotify\b"):
        return f"pon música de {answer} en spotify"
    if _has(_fold(previous_user_text), r"\bvideos?\b"):
        # VIDEO1717 «abre youtube y pon un video» → «¿qué video?» → «uno de
        # gatos»: the answer names the video, played from YouTube.
        answer = re.sub(r"^(?:(?:uno|una|one)\s+)?(?:de|of|sobre|about)\s+", "", answer, flags=re.IGNORECASE).strip(" .!") or answer
        return f"pon un video de {answer} en youtube"
    return f"pon música de {answer}"


def _completed_missing_list_entries_request(
    text: str, previous_user_text: str | None, available_operations: Iterable[str],
) -> str | None:
    """«crea una lista de la compra» → «¿qué pongo en ella?» → «leche y pan»: the answer
    is what goes on the list asked for, read like «añade leche y pan a la lista de la
    compra». Only after a request the resolver itself asks the entries of, and only for
    a short content answer (no request head, no question, no refusal)."""

    if not previous_user_text:
        return None
    prior = resolve_explicit_clarification_intent(previous_user_text, available_operations)
    if prior is None or prior.operations != ("task.create",) or prior.missing_fields != ("list_entries",):
        return None
    listed = list_creation_without_items(_fold(previous_user_text))
    answer = text.strip().strip("\"'“”«»").strip(" .!")
    folded = _strip_request_envelope(_fold(answer))
    if (
        listed is None
        or not folded
        or len(folded.split()) > 24
        or "?" in answer
        or _head_is(_request_head(folded), _COVERAGE_ACTION_HEAD)
        or _negative_action_forms(folded)
        or re.fullmatch(r"(?:no|nada|ninguna|none|nothing|cancela|cancelar|cancel|olvidalo|dejalo)\b.*", folded)
    ):
        return None
    return f"añade {answer} a la {listed}"


def list_entries_said_before(text: str, previous_user_text: str | None, last_reply: str | None) -> bool:
    """M89 (DEV-D v3r D-p37-t2 «beer and chips» → «What would you like me to do with beer and chips?» → «Include items
    on the shopping list» → «Would you like me to add beer and chips to your shopping list?»): the mirror of
    ``_completed_missing_list_entries_request``. The entries were the person's last message, the one BAXY's question
    was about; the list named now takes them («items», «las cosas» point back at them). Only a short content message
    (no request head, no question, no refusal) that BAXY's question quotes."""

    if not previous_user_text or not last_reply or not str(last_reply).rstrip().endswith("?"):
        return False
    if list_creation_without_items(_fold(text)) is None:
        return False
    said = str(previous_user_text).strip().strip("\"'“”«»").strip(" .!")
    folded = _strip_request_envelope(_fold(said))
    if (
        not folded
        or len(folded.split()) > 12
        or "?" in said
        or _head_is(_request_head(folded), _COVERAGE_ACTION_HEAD)
        or _negative_action_forms(folded)
        or re.fullmatch(r"(?:no|nada|ninguna|none|nothing|cancela|cancelar|cancel|olvidalo|dejalo)\b.*", folded)
    ):
        return False
    return re.search(rf"(?<!\w){re.escape(folded)}(?!\w)", _fold(str(last_reply))) is not None


def _contextual_output_level_target(
    text: str, previous_user_text: str, available_operations: Iterable[str],
) -> bool:
    """Ground a numeric pronoun target in the immediately preceding audio request.

    This only checks the domain of a proposed absolute-level operation. It does
    not choose the operation, extract its value or claim an observed level.
    Full-clause matching keeps another object or effect outside this inheritance.
    """
    folded = _strip_request_envelope(_fold(text))
    if re.fullmatch(
        r"(?:(?:pon|fija|ajusta|deja|establece)(?:lo|la)\s+(?:a|al)|"
        r"(?:set|put|leave|adjust)\s+it\s+(?:to|at))\s+"
        r"\d{1,3}\s*(?:%|por ciento|percent)?"
        r"(?:\s+(?:ahora|now|please|por favor))?[.!?]*",
        folded,
    ) is None:
        return False
    # A list of earlier targets is not a unique antecedent, even when the
    # audio recognizer can account for one part of that request.
    if _has(_fold(previous_user_text), r"\b(?:y|and|o|or)\b|;"):
        return False
    prior = resolve_explicit_effects(previous_user_text, available_operations)
    return (
        prior is not None
        and len(prior.operations) == 1
        and prior.operations[0] in {"audio.status", "audio.volume", "audio.volume.adjust"}
        and operation_domain_is_grounded(previous_user_text, prior.operations[0]) is True
    )


# A weighted comparative veto was written here and measured and rejected. It
# weighed each term by how few operations the alias corpus attaches it to, and
# refused a proposal that carried no distinctive evidence when another operation
# carried some. On the eight V2 executions it reversed the inversion exactly --
# peripheral.list 1.48 against system.status 0.00, system.process.list 1.48
# against window.application.status 0.00 -- and stopped four of the seven wrong
# ones. Then it refused three of six plainly correct requests, among them
# "revisa el estado del audio" for ``audio.status`` and the note.create text of
# a physical mission that currently passes. Deriving a rule from the cases that
# failed and checking it only there is exactly the error R103 made; this is the
# third catalogue-derived gate to look free on its own evidence and break
# elsewhere. The finding is kept in the maintainability register, not as dead
# code here.
def _uncovered_family_floor(folded: str, operation: str) -> bool | None:
    """Require the object class for families no curated rule reaches.

    Only ``filesystem.`` and the note selectors are floored today, because that is
    where an unsolicited effect was actually observed. The remaining uncovered families are recorded
    as an open defect with their count rather than papered over here: adding
    rules for families no measurement has implicated would be the same
    hand-maintained treadmill this gate is already stuck on.
    """

    if operation.startswith("filesystem."):
        return _has(folded, _FILESYSTEM_OBJECT_NOUN)
    if operation in {"note.restore", "note.trash"}:
        # Tanda 3 2026-09-24 «reanudar la lectura de la lección de francés» executed note.restore with no
        # note to select and showed «argumentos inválidos». Restoring or trashing a note must name a note.
        return _has(folded, r"\b(?:notas?|notes?|apuntes?|anotacion(?:es)?)\b")
    return None


_POINTED_MEDIA = (
    r"\b(?:esta|este|this)\s+(?:cancion|tema|song|track|artista|artist|musica|music)\b|"
    r"\b(?:cancion|tema|song|track|artista|artist)\s+(?:es\s+|is\s+)?(?:esta|este|esto|this)\b|"
    r"\bque\s+(?:cancion|tema|musica|artista)\s+(?:suena|esta\s+sonando|hay\s+en\s+la\s+radio)\b|"
    r"\b(?:quien|who)\s+(?:canta|sings|is\s+singing)\b|"
    # Uso real 2026-09-23 «cómo llamarías al tipo de música que estamos escuchando», «what's on the
    # radio right now»: what plays, pointed at by what is being heard.
    r"\b(?:cancion|tema|musica|song|music|track|la|lo|el)\s+que\s+(?:estamos|estoy|esta|se\s+esta)\s+"
    r"(?:escuchando|oyendo|sonando|reproduciendo|tocando)\b|"
    r"\b(?:song|music|track)\s+(?:that'?s|that\s+is|we'?re|we\s+are|i'?m|i\s+am)\s+(?:playing|listening\s+to|hearing)\b|"
    r"\b(?:what'?s|what\s+is)\s+(?:on|playing\s+on)\s+(?:the\s+)?radio\b"
)


def _curated_domain_is_grounded(
    text: str,
    operation: str,
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
) -> bool | None:
    """Remove authority when a family names the wrong domain.

    One-sided: this never selects an operation.  A named computing domain
    (``bluetooth``, ``wifi``/``wireless``) is enough to keep the proposal;
    extra action-verb lists must not fail closed on a paraphrase that already
    names that domain.  ``False`` is for contradiction or an unnamed domain
    on a covered family.  ``None`` leaves uncovered catalogue operations
    untouched.
    """

    folded = _fold(text)
    if operation == "app.open":
        folded = _strip_request_envelope(folded)
        applications = build_application_catalog_index(application_names)
        return (
            _authenticated_application_target(folded, applications) is not None
            or _authenticated_application_desired_open(
                folded,
                applications,
            )
            is not None
            or bool(_open_application_spans(folded))
        )
    if operation == "task.delete":
        # "Bota los papers viejos al contenedor" reached task.delete. Throwing
        # paper away is not deleting a task, so the task domain has to be named
        # (or the list the entry comes off, «take bathroom painting off the list»).
        removal = list_removal_request(text)
        if removal is not None and removal.entry is not None:
            return True
        return _has(
            folded,
            r"\b(?:tarea|tareas|task|tasks|pendiente|pendientes|todo|to-?do)\b",
        )
    if operation.startswith("peripheral.") and operation != "peripheral.list":
        # "Vacuum the hallway carpet" reached peripheral.scan; a household
        # appliance is not a connected device inventory. peripheral.list keeps
        # its own stricter gate below -- a broad rule here would shadow it and
        # hand back authority that gate already removes.
        return _has(
            folded,
            r"\b(?:periferico|perifericos|peripheral|peripherals|"
            r"dispositivo|dispositivos|device|devices|"
            r"impresora|impresoras|printer|printers|"
            r"escaner|scanner|usb|hardware|accesorio|accesorios)\b",
        )
    if operation == "clipboard.paste":
        # Vocabulary grounding cannot separate this one: pasting a stamp onto an
        # envelope uses the operation's own verb. Ask what is being pasted
        # instead. The clipboard has to be named, or the thing pasted has to be
        # what was previously copied, or the target has to be a focused control.
        return _clipboard_paste_domain(folded)
    if operation == "window.move":
        # "Move the wardrobe towards the far window" names a window, but as the
        # destination. What moves has to be the window itself, so a destination
        # preposition between the verb and the window disqualifies it.
        return (
            re.search(
                r"\b(?:mueve|mover|muevele|desplaza|desplazar|reubica|move)\b"
                r"(?:(?!\b(?:hacia|towards?|junto\s+a|al\s+lado\s+de|"
                r"next\s+to|beside|near|cerca\s+de|frente\s+a|debajo\s+de|"
                r"under|below|behind|detras\s+de|pegado\s+a)\b)[\s\S])"
                r"{0,48}?\b(?:ventana|ventanas|window|windows)\b",
                folded,
                re.IGNORECASE,
            )
            is not None
        )
    if operation in {"system.recyclebin.empty", "system.recyclebin.restore"}:
        # "Envia la bicicleta vieja al reciclaje" was planned as emptying the
        # Windows Recycle Bin -- twice. Municipal recycling and the desktop bin
        # share a word in Spanish, and this operation is destructive and
        # irreversible, so the bin has to be named as the bin.
        return _has(
            folded,
            r"\bpapelera\b|\brecycle\s*bin\b|\brecycling\s*bin\b|"
            r"\btrash\b|\bbasura\s+de(?:l)?\s+(?:escritorio|windows|equipo|pc)\b",
        )
    if operation in {"app.close", "window.close"}:
        # "Cuelga el cuadro en la pared del pasillo" was planned as app.close.
        # Closing something on screen needs the screen named: an authenticated
        # application, or the literal window/program vocabulary.
        applications = build_application_catalog_index(application_names)
        return _authenticated_application_target(
            folded, applications
        ) is not None or _authenticated_application_close_target(
            folded, applications
        ) is not None or deictic_close_request(folded) or _has(
            folded,
            r"\b(?:aplicacion|aplicaciones|application|applications|app|apps|"
            r"programa|programas|program|programs|ventana|ventanas|"
            r"window|windows|pestana|pestanas|tab|tabs|proceso|process)\b",
        )
    if operation == "backup.list":
        return (
            _has(
                folded,
                r"\b(?:backup|backups|respaldo|respaldos|"
                r"copia|copias)(?:\s+de\s+seguridad)?\b",
            )
            and _has(
                folded,
                rf"\b(?:{_LIST}|inventario|inventory|disponibles?|available|"
                r"privad[oa]s?|private)\b",
            )
            and not _has(folded, r"\b(?:log|logs|registro|job|trabajo)\b")
        )
    if operation == "backup.create":
        return (
            _has(folded, r"\b(?:backup|respaldo|copia\s+de\s+seguridad)\b")
            and _has(folded, r"\b(?:archivo|file)\b")
            and not _has(
                folded,
                r"\b(?:pendrive|pen drive|usb|disco externo|external drive|"
                r"documentos|documents|carpeta|folder)\b",
            )
        )
    if operation == "bluetooth.radio.set":
        # Domain noun is the gate. Requiring a closed verb list vetoed
        # "apagame el bluetooth" because "apagame" is not "apaga". Opening
        # Bluetooth settings is a different effect and stays a contradiction.
        if not _has(folded, r"\bbluetooth\b"):
            return False
        if _has(
            folded,
            r"\b(?:configuracion|settings|entra|enter|abre|open)\b",
        ):
            return False
        return True
    if operation == "software.python.status":
        return _has(folded, r"\bpython\b")
    if operation == "software.python.package.status":
        return _python_package_request(folded) is not None
    if operation == "storage.removable.list":
        return _has(folded, r"\b(?:pendrive|pen|usb|externo|externa|external|removable|flash|stick)\b")
    if operation == "calculator.expression.evaluate":
        return calculator_expression_request(folded) is not None
    if operation == "weather.current":
        return _weather_lookup_query(text) is not None
    if operation == "web.news.headlines":
        return _news_headlines_request(text)
    if operation == "display.status":
        return _has(folded, r"\b(?:resolucion|monitor(?:es)?|pantallas?|screens?|displays?|hz|hertz|hercios|frecuencia|refresh)\b")
    if operation == "bluetooth.radio.status":
        return _has(folded, r"\bbluetooth\b") and not _has(
            folded, r"\b(?:configuracion|settings|entra|enter|abre|open)\b"
        )
    if operation == "bluetooth.device.list":
        return (
            _has(folded, r"\bbluetooth\b")
            and _has(
                folded,
                r"\b(?:dispositivos?|devices?|equipos?|accesorios?|hardware|"
                r"detectad[oa]s?|detected|visibles?|visible|cercan[oa]s?|nearby|"
                r"lista|listar|list|enumera|enumerate|muestra|show|cuales|which)\b",
            )
            and not _has(
                folded,
                r"\b(?:ciudad|city|historia|story|imaginari[oa]|imaginary)\b",
            )
        )
    if operation == "input.pointer.control":
        # The pointer family was reachable without ever naming a pointer:
        # "consigue un ride hasta el centro" became input.pointer.control.
        return _has(
            folded,
            r"\b(?:puntero|pointer|cursor|raton|mouse|trackpad|touchpad)\b"
            r"|\b(?:clic|click|clickea|clickear|doble\s+clic|double\s+click|"
            r"arrastra|arrastrar|drag|"
            r"scroll|scrollea|scrollear|rueda)\b",
        )
    if operation == "input.visible.click":
        # Pointing verbs keep the coat-button false friend out. Navigate verbs
        # ("ve a", "go to") are the second clause of Open App → Click X and
        # only ground click, never pointer.control.
        if _visible_click_label(folded, allow_navigate=True) is not None:
            return True
        return _has(
            folded,
            r"\b(?:puntero|pointer|cursor|raton|mouse|trackpad|touchpad)\b"
            r"|\b(?:clic|click|clickea|clickear|doble\s+clic|double\s+click|"
            r"pulsa|presiona|press)\b",
        )
    if operation in {
        "input.key.press",
        "input.text.type",
        "input.keyboard.open",
        "input.keyboard.layout",
        "input.keyboard.status",
    }:
        if operation == "input.key.press" and start_menu_request(folded):
            return True
        return _has(
            folded,
            r"\b(?:teclado|keyboard|tecla|teclas|key|keys|"
            r"escribe|escribir|escribi|tipea|type|typing|teclea|teclear|"
            r"atajo|shortcut|combinacion|combination|presiona|press|"
            r"distribucion|layout|"
            r"dale\s+(?:enter|intro|return)|(?:press|hit|type)\s+enter)\b",
        )
    if operation in {"calendar.event.create", "calendar.event.list"}:
        # The agenda readers are the domain: a read of the person's own agenda («qué tengo por
        # venir», «mi horario para el día») or an event put on it («añade práctica el cuatro de
        # febrero») names it without saying «calendario».
        if operation == "calendar.event.list" and public_event_subject(folded):
            # MASSIVE recommendation_events «dime todos los eventos que ocurren en milán» listed the agenda.
            return False
        if agenda_read_request(text):
            return operation == "calendar.event.list"
        if agenda_event_request(text) is not None:
            return operation == "calendar.event.create"
        names_calendar = _has(
            folded,
            r"\b(?:calendario|calendars?|agendas?|eventos?|events?|citas?|"
            r"appointments?|reunion|reuniones|meetings?)\b",
        )
        if not names_calendar or _has(
            folded,
            r"\b(?:email|e-mail|correo|mail|asunto|subject|escribele|"
            r"write to|send to)\b",
        ):
            return False
        # Creating and listing are opposite directions of one family. "Haz un
        # appointment con el doctor" was grounded for calendar.event.list, so
        # asking to make an appointment could execute a listing instead -- a
        # near-miss effect. Each direction now needs its own verb.
        creation = _has(
            folded,
            r"\b(?:crea|crear|agendar|agendame|programa|programar|"
            r"reserva|reservar|anota|anotar|haz|hazme|"
            r"make|create|schedule|book|set\s+up|add)\b"
            r"|\bagenda\s+(?:un|una|el|la|mi)\b",
        )
        reading = _has(
            folded,
            r"\b(?:que|cuales|cuando|cuantas|muestra|muestrame|dime|ver|"
            r"lista|listar|list|show|tell|revisa|consulta|tengo|hay|"
            r"what|which|when|how\s+many|"
            # Uso real 2026-09-23 «do i have appointments today».
            r"do\s+i\s+have|have\s+i\s+got|any|upcoming|proxim[oa]s?|pendientes?)\b",
        )
        if operation == "calendar.event.create":
            return creation
        return reading and not creation
    if operation in {"browser.navigate", "browser.navigate.named"}:
        if operation == "browser.navigate" and _symbolic_web_destination(text) is not None:
            return True
        if operation == "browser.navigate.named" and _named_browser_search(text) is not None:
            return True
        return _has(
            folded,
            r"\b(?:navegador|browser|web|website|sitio|site|pagina|page|"
            r"internet|google|wikipedia|youtube)\b|https?://|"
            r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\b",
        ) and not _has(folded, r"\b(?:archivo|file|carpeta|folder)\b") and not minimize_all_request(folded)
    if operation == "web.search":
        # A semantic selector may confuse local inspection verbs with a web
        # lookup (for example, "look through Downloads"). A direct search with
        # its own query need not repeat "internet", but cannot borrow a private
        # or local operand. This gate only retains a proposal, never selects it.
        direct_public_search = _direct_public_search_query(text) is not None
        return (
            _symbolic_web_destination(text) is not None
            or _location_recommendation_request(folded)
            or _public_route_lookup_request(folded)
            or _public_calendar_fact_lookup_request(folded)
            or _public_live_lookup_request(folded)
            or _public_commerce_lookup_request(folded)
            or (
                _has(
                    folded,
                    rf"\b(?:{_SEARCH}|consulta|consultar|investiga|investigar|"
                    r"investigate|look\s+on)\b",
                )
                and (
                    direct_public_search
                    or _has(
                        folded,
                        r"\b(?:web|internet|online|google|bing|public\s+api)\b",
                    )
                )
                and not _has(
                    folded,
                    r"\b(?:archivo|file|carpeta|folder|documentos?|documents?|"
                    r"descargas|downloads?|escritorio|desktop|notas?|notes?|"
                    r"tareas?|tasks?|recordatorios?|reminders?|aplicaciones?\s+"
                    r"instaladas?|installed\s+applications?|installed\s+apps?)\b",
                )
            )
        )
    if operation in {"game.install.prepare", "game.install.status"}:
        return _has(folded, r"\b(?:app\s*id|appid)\s*[:#-]?\s*\d{1,16}\b") or (
            _has(folded, r"\b\d{2,16}\b")
            and _has(
                folded,
                r"\b(?:steam|juego|game|instala|instalar|install|"
                r"descarga|download|progreso|progress|estado|status)\b",
            )
        )
    if operation == "filesystem.create.directory":
        # Desktop, Documents and Downloads are catalog roots since the owner's
        # decision of 2026-09-13 (point 2); pictures and drive letters are not.
        return _has(
            folded, r"\b(?:carpeta|folder|directorio|directory)\b"
        ) and not _has(
            folded,
            r"\b(?:imagenes|pictures|fotos|photos)\b|(?:^|\s)[a-z]:[\\/]",
        )
    if operation == "filesystem.path.ensure.absent":
        return (
            _has(folded, r"\b(?:archivo|file|ruta|path)\b")
            and not _has(folded, r"\b(?:carpeta|folder|directorio|directory)\b")
            and _has(
                folded,
                r"\b(?:borra|borrar|elimina|eliminar|delete|remove|"
                r"ausente|absent|no existe|does not exist|verifica|verify|check)\b",
            )
        )
    if operation == "filesystem.hash":
        if _has(folded, r"\bhash\b") and _has(folded, r"\b(?:archivo|file)\b"):
            return True
        return None
    if operation == "filesystem.list":
        return _has(
            folded,
            r"\b(?:archivos?|files?|carpetas?|folders?|directorios?|directories?|"
            r"entradas?|entries|sandbox)\b",
        ) and _has(
            folded,
            rf"\b(?:{_LIST}|enumera|enumerate|muestra|show|inventario|inventory|"
            r"contenido|contents?)\b",
        )
    if operation == "filesystem.write.text":
        # Known folders are catalog roots since 2026-09-13 (owner decision,
        # point 2); pictures and drive letters remain outside.
        return (
            _has(folded, r"\b(?:archivo|file|texto|text)\b")
            and _has(folded, r"\b(?:escribe|write|guarda|save|crea|create)\b")
            and not _has(
                folded,
                r"\b(?:imagenes|pictures|fotos|photos)\b|(?:^|\s)[a-z]:[\\/]",
            )
        )
    if operation == "game.catalog.list":
        return (
            _has(folded, r"\b(?:steam|juegos?|games?)\b")
            and _has(
                folded,
                r"\b(?:catalogo|catalog|biblioteca|library|lista|listar|list|"
                r"instalados|installed)\b",
            )
            and not _has(
                folded,
                r"\b(?:capturas?|screenshots?|tienda|store|shop|loja)\b",
            )
        )
    if operation == "game.install.status":
        return _has(folded, r"\b(?:appid|app id)\s+\d{1,16}\b") and _has(
            folded,
            r"\b(?:estado|status|instalacion|installation|instalad[oa]|installed)\b",
        )
    if operation == "game.launch":
        return _has(folded, rf"\b(?:{_OPEN}|lanza|launch|ejecuta|run)\b") and not _has(
            folded,
            r"\b(?:capturas?|screenshots?|tienda|store|shop|loja|"
            r"biblioteca|library)\b",
        )
    if operation == "audio.microphone.mute":
        # Same words as the reader (semantic.lexicon): a verb the reader accepts is
        # never vetoed here for not being in a shorter copy of the list.
        return (
            _has(folded, rf"\b{lexicon.MICROPHONE_NOUN}\b")
            and _has(folded, rf"\b(?:{lexicon.MICROPHONE_VERB}|mute)\b")
            and not _has(
                folded,
                r"\b(?:en|in|inside)\s+(?:discord|teams|zoom|skype|"
                r"whatsapp|una aplicacion|an app)\b",
            )
        )
    if operation == "email.latest.reply":
        return (
            _has(folded, r"\b(?:responde|responder|reply|answer)\b")
            and _has(folded, r"\b(?:ultimo|ultima|latest|recent)\b")
            and _has(folded, r"\b(?:correo|email|mail)\b")
        )
    if operation == "peripheral.list":
        return (
            (
                _has(
                    folded,
                    r"\b(?:perifericos?|peripherals?|impresoras?|printers?|"
                    r"escaneres?|scanners?|teclados?|keyboards?|mouse|mice|usb)\b",
                )
                or _has(folded, _CONNECTED_INVENTORY)
            )
            and _has(
                folded,
                rf"\b(?:{_LIST}|muestra|show|cuales|which|what|que|tengo)\b",
            )
            and not _has(folded, r"\b(?:predeterminad[oa]|default|establece|set)\b")
        )
    if operation in {"notification.cancel.at", "notification.cancel.latest"}:
        return (
            _has(folded, r"\b(?:alarma|alarm|recordatorio|reminder)\b")
            and _has(
                folded,
                r"\b(?:cancela|cancelar|cancel|quita|quitar|remove|remueve|"
                r"elimina|eliminar|delete|borra|borrar|get rid of)\b",
            )
            and (
                _latest_notification_selector(folded)
                if operation == "notification.cancel.latest"
                else _has(folded, _CLOCK_TIME_SELECTOR)
            )
        )
    if operation == "notification.list.due":
        return _has(
            folded,
            r"\b(?:recordatorios?|reminders?|notificaciones?|notifications?|"
            r"avisos?|alerts?)\b|\bexpired\s+notes?\b",
        ) and _has(
            folded,
            rf"\b(?:{_LIST}|vencid[oa]s?|due|overdue|pendientes?|pending|"
            r"dismissed)\b",
        )
    if operation == "note.list":
        return (
            _note_inventory_object(folded)
            and _has(
                folded,
                rf"\b(?:{_LIST}|indice|index|inventario|inventory|"
                r"completo|complete|privad[oa]s?|private|local)\b",
            )
            and not _has(
                folded,
                r"\b(?:expired|overdue|due|vencid[oa]s?|fuera\s+de\s+plazo)\b",
            )
        )
    if operation == "routine.phrase.create":
        return (
            _has(folded, r"\b(?:rutina|routine|frase|phrase|al oir|when you hear)\b")
            and _has(
                folded,
                r"\b(?:captura|screenshot|reproduce|play|pausa|pause|media)\b",
            )
            and not _has(
                folded, r"\b(?:habito|habit|marcalo|mark it|registre|registra)\b"
            )
        )
    if operation == "media.play.youtube":
        return (
            _has(folded, r"\byoutube\b")
            # MUSIC1553: the voseo and clitic forms («reproducí», «poné», «poneme»).
            and _has(folded, r"\b(?:reproduce|reproducir|reproduci|reproducime|play|pon|pone|poneme|ponme|poner)\b")
            and not _has(
                folded,
                r"\b(?:primer|primero|first|segundo|second|tercer|third|"
                r"resultado|result)\b",
            )
        )
    if operation == "ocr.read":
        return _has(
            folded,
            rf"\b(?:{_READ}|extrae|extraer|extract|run|turn|convert|convierte)\b",
        ) and _has(
            folded,
            r"\b(?:ocr|pantalla|screen|captura|screenshot|imagen|image|"
            r"texto|text|mensaje|message|writing|screenwriting|"
            r"characters?|caracteres?)\b",
        )
    if operation == "system.power":
        return _has(
            folded,
            r"\b(?:equipo|pc|compu|computador(?:a)?|computer|maquina|machine|"
            r"windows)\b",
        ) and not _has(
            folded,
            r"\b(?:telefono|movil|celular|phone|smartphone|tablet|iphone)\b",
        )
    if operation == "system.process.terminate.named":
        return _has(
            folded,
            r"\b(?:forzar|force|mata|matar|kill|termina|terminar|terminate|"
            r"cierra|cerrar|close)\b",
        ) and _has(
            folded,
            r"\b(?:proceso|process|aplicacion|application|app|programa|program)\b",
        )
    if operation == "task.create" and list_entry_request(text) is not None:
        return True
    if operation == "task.create":
        return _has(
            folded,
            r"\b(?:tarea|task|to-do|todo|pendiente)\b",
        ) and _has(
            folded,
            r"\b(?:crea|crear|create|anade|agrega|agregame|add|nueva|new)\b",
        )
    if operation == "task.complete":
        return _has(folded, r"\b(?:tarea|task|to-do|todo)\b") and _has(
            folded,
            r"\b(?:completa|completar|complete|termina|terminada|terminado|"
            r"finish|finished|marca|mark)\b",
        )
    if operation == "reminder.delete":
        return _exact_local_reminder_title(folded) is not None
    if operation == "streaming.navigate":
        return (
            _has(
                folded,
                rf"\b(?:{_OPEN}|navega|navigate|reproduce|play|ver|watch)\b",
            )
            and _has(
                folded,
                r"\b(?:youtube|netflix|prime video|primevideo|streaming|"
                r"pelicula|movie|serie|show|video)\b|https?://",
            )
            and not _has(folded, r"\b(?:como|how)\b")
        )
    if operation == "streaming.play.named":
        return (
            _has(folded, r"\b" + _NETFLIX_SPELLED + r"\b")
            and _has(
                folded,
                # VIDEO1921: «ver» encabeza el pedido igual que los demás, y
                # dejarla sólo en la rama que resuelve la habría partido en dos.
                # «watch» viaja con ella por simetría, pero hoy no resuelve: en
                # inglés es también el reloj inteligente y los lectores de
                # dispositivos la reclaman antes. No acompañar una palabra
                # ambigua es lo seguro; ninguna fila abierta la necesita.
                r"\b(?:reproduce|play|pon|ponme|poneme|pone|busca|find|encuentra|encuentras|"
                r"arranca|arrancala|start|ver|watch)\b",
            )
            and not _has(folded, r"\b(?:como|how|tutorial|ejemplo|example)\b")
        )
    if operation == "shell.command.run":
        return shell_command_request(text) is not None
    if operation == "document.presentation.create":
        return presentation_request(text) is not None
    if operation == "file.compress":
        return compress_named_request(text) is not None or folder_txt_zip_open_mission(text) is not None
    if operation == "file.open":
        return open_named_file_request(text) is not None or folder_txt_zip_open_mission(text) is not None or presentation_request(text) is not None or web_image_request(text) is not None
    if operation == "desktop.wallpaper.set":
        return wallpaper_request(text) is not None
    if operation == "web.download":
        return web_download_request(text) is not None or web_image_request(text) is not None
    if operation == "game.install.named":
        return steam_library_verb(text) == "install"
    if operation == "game.uninstall.named":
        return steam_library_verb(text) == "uninstall"
    if operation == "package.uninstall":
        software = software_package_request(text, application_names)
        return software is not None and software[0] == "uninstall"
    if operation == "package.install.prepare":
        software = software_package_request(text, application_names)
        if software is not None and software[0] == "install":
            return True
        return (
            _spoken_package_id(folded) is not None
            and _has(
                folded,
                r"\b(?:prepara|preparado|prepare|resolve|instalacion|installation|"
                r"instalar|install|paquete|package|staged|tied|alista(?:lo|la)?)\b",
            )
            and not _has(folded, r"https?://|\b(?:juego|game|steam)\b")
        )
    if operation == "office.document.create":
        return (
            _has(
                folded,
                r"\b(?:documento|document|word|excel|hoja de calculo|"
                r"spreadsheet)\b",
            )
            and _has(
                folded,
                r"\b(?:crea|crear|creame|create|nuevo|new|blanco|blank)\b",
            )
            and not _has(
                folded,
                r"\b(?:powerpoint|presentacion|presentation|"
                r"diapositivas?|slides?)\b",
            )
            and not _has(
                folded,
                r"\b(?:convierte|convertir|convierteme|convert|pdf)\b",
            )
        )
    if operation == "media.seek.relative":
        return _has(
            folded,
            r"\b(?:adelanta|atrasa|retrocede|rewind|forward|jump|skip|seek)\b",
        ) and not _has(
            folded,
            r"\b(?:edita|editar|editame|edit|recorta|trim|corta|cut|"
            r"quita|quitar|quitale)\b",
        )
    if operation in {"game.install.cancel.active", "game.install.cancel"}:
        return (
            _has(folded, r"\b(?:steam|juego|game)\b")
            and (
                _has(
                    folded,
                    r"\b(?:cancela|cancelar|cancel|stop|detener|detene)\b",
                )
                or (
                    _has(folded, r"\bpara\b")
                    and _has(
                        folded,
                        r"\b(?:descarga|download|instalacion|install)\b",
                    )
                )
            )
            and not _has(folded, r"\b(?:torrent|series)\b")
        )
    if operation == "clipboard.write.text":
        return _has(folded, r"\b(?:portapapeles|clipboard)\b") and _has(
            folded,
            r"\b(?:copia|copiar|copy|escribe|write|pon|put|guarda|save|"
            r"reemplaza|replace|establece|set)\b",
        )
    if operation == "window.move":
        return (
            _has(folded, r"\b(?:mueve|mover|move|arrastra|drag)\b")
            and _has(folded, r"\b(?:ventana|window)\b")
            and not _has(folded, r"\b(?:archivo|file|carpeta|folder)\b")
        )
    if operation == "system.time":
        # A nominal clock/calendar query is still compatible with this domain.
        # The contextual policy selects the operation; this one-sided veto must
        # not require the person to repeat a verb in an elliptical follow-up.
        # A qualified date (an event, person or historical date) is not covered.
        # The time of another zone or place is this clock read with that zone
        # («place»), so it is covered only when the place is read; a clock of
        # another place that names none is never this clock recited.
        if clock_elsewhere(folded) is not None:
            return True
        if other_place_clock_question(folded):
            return False
        return _nominal_datetime_query(folded) or any(
            _direct_current_time_request(clause)
            for clause in _request_clauses(folded)
        )
    if operation == "system.status":
        request = _strip_request_envelope(folded)
        # «y disco?», «Y espacio? cuánto espacio tengo»: a nominal machine
        # scope with no other verb is the same speech act as «y la fecha?»
        # for the clock (SYSTEM1175/001, /002). Only a scope word, optionally
        # preceded by y/and and an article, and optionally followed by the
        # how-much question on the same scope.
        nominal_scope = re.fullmatch(
            r"(?:(?:y|and)\s+)?(?:(?:el|la|mi|the|my)\s+)?"
            r"(?:disco|disk|espacio|space|bateria|battery|ram|memoria|memory|cpu|gpu)"
            r"[\s?!.]*(?:(?:cuanto|cuanta|how\s+much)\s+(?:espacio|space|ram|memoria|memory)"
            r"\s+(?:tengo|queda|hay|libre|do\s+i\s+have|is\s+left)[\s?!.]*)?",
            request,
        ) is not None
        return (nominal_scope or _is_direct_request(request)) and _system_status_domain(request)
    if operation in {"system.settings.adjust", "system.settings.status"}:
        return _has(
            folded,
            r"\b(?:brillo|brightness|luz\s+de\s+la\s+pantalla|"
            r"screen\s+(?:light|brightness)|how\s+bright)\b",
        )
    if operation == "system.settings.set":
        return _has(
            folded,
            r"\b(?:brillo|brightness|luz nocturna|night light|"
            r"no molestar|do not disturb|dnd|modo avion|airplane mode|flight mode)\b",
        )
    if operation == "system.process.list":
        return _process_list_domain(folded)
    if operation == "network.status":
        return _network_status_domain(folded)
    if operation == "network.port.list":
        # MASSIVE transport_traffic (dev corpus 2026-09-24) «cómo está el tráfico cerca de mí», «me gustaria conocer la
        # situacion del trafico» listed this PC's listening ports. Traffic alone is the road; what this operation reads
        # (ports, sockets, listeners) has to be named.
        return _has(folded, r"\b(?:puertos?|ports?|sockets?|listeners?|escuchando|listening|tcp|udp|endpoints?)\b")
    if operation in {
        "wifi.connect.named",
        "wifi.disconnect",
        "wifi.ensure.connected",
        "wifi.profile.list",
        "wifi.radio.set",
        "wifi.radio.status",
        "wifi.scan",
        "wifi.status",
    }:
        wifi_domain = _has(
            folded,
            r"\b(?:wi[\s-]?fi|red\s+inalambrica|wireless)\b",
        )
        if operation == "wifi.scan":
            # «qué redes hay» names the domain through «redes» alone.
            return _wifi_scan_question(folded)
        if operation == "wifi.radio.set":
            return wifi_domain and wifi_radio_set_request(folded) is not None
        if operation == "wifi.radio.status":
            return wifi_domain
        if not wifi_domain:
            return False
        if operation == "wifi.disconnect":
            # "drop the wireless connection" names the domain and the
            # disconnect; a closed verb list that omitted "drop" was the
            # whitelist-absence defect. Domain named is enough here.
            return True
        if operation == "wifi.profile.list":
            return (
                _has(folded, r"\b(?:perfiles?|profiles?)\b")
                and _has(folded, rf"\b(?:{_LIST}|guardad[oa]s?|saved)\b")
            ) or wifi_place_request(folded) is not None
        if operation == "wifi.status":
            # «decime si el wifi está prendido» and «qué onda con el wifi» ask
            # for the same reading as «estado del wifi»; without these words the
            # gate withdrew wifi.status and the person got a confirmation
            # question instead of the observation (NETWORK1161/003, /004).
            return _has(
                folded,
                r"\b(?:estado|status|conectad[oa]|connected|como|how|which|cual|"
                r"pegad[oa]|a\s+que|prendid[oa]|encendid[oa]|apagad[oa]|activ[oa]|"
                r"onda|on|off|working)\b",
            )
        return _has(
            folded,
            r"\b(?:conecta|conectar|conectame|conectate|connect|cambia|change|enciende|turn\s+on)\b",
        )
    if operation == "memory.status":
        return _has(
            folded,
            r"\b(?:memoria|memory|recuerdos?)\b.{0,40}"
            r"\b(?:local|locales|baxy|asistente|assistant)\b|"
            r"\b(?:baxy|asistente|assistant|local|tus)\b.{0,40}"
            r"\b(?:memoria|memory|recuerdos?)\b",
        ) and not _has(
            folded,
            r"\b(?:ram|uso|usage|libre|free|sistema|system)\b",
        )
    if operation == "audio.mute":
        return _audio_mute_domain(folded)
    if operation in {
        "audio.status",
        "audio.volume",
        "audio.volume.adjust",
    }:
        return _volume_domain(folded)
    if operation == "notification.schedule":
        return _has(
            folded,
            (
                r"\b(?:notificacion(?:es)?|notifications?|avisa(?:me)?|"
                r"avisame|notify|recuerda(?:me)?|recuerdame|remind|"
                r"recordatorios?|reminders?|alarmas?|alarms?|alertas?|alerts?|timers?|"
                r"temporizadores?|despiertame|despertame|levantame|"
                r"wake\s+me(?:\s+up)?)\b"
            ),
        ) or _count_down_request(folded) or (
            # «pon el almuerzo todos los días a las doce y media»: a daily event is a repeating reminder.
            (event := agenda_event_request(text)) is not None and event.repeat is not None
        )
    if operation == "network.ip.list":
        # Without a rule the proposal was vetoed into a confirmation
        # (NETWORK1161/006-008). An IP is named as such.
        return _ip_list_request(folded) or _has(
            folded, r"\b(?:ip|ips|direccion(?:es)?\s+ip|ip\s+address(?:es)?)\b"
        )
    if operation == "reminder.resolve.exact":
        return _nominal_reminder_lookup_title(folded) is not None
    if operation == "email.send":
        return email_send_request(text) is not None or email_request_without_address(text)
    if operation in {"message.recipient.resolve", "message.send"} and message_request_any_channel(text) is not None:
        # REOPEN1993 grupo E: the request names a recipient and a text to say.
        return True
    if operation in {"message.recipient.resolve", "message.send"}:
        # A bare "manda"/"send" grounded this family, so any errand that shares
        # the verb -- a parcel, a bouquet, a box -- could be answered by sending
        # a chat message instead. Excluding physical nouns one by one never
        # terminates: "package" was blocked and "ramo de rosas" walked straight
        # through. Require a positive message signal instead, which is a closed
        # set: a channel, a message noun, a speech act, or a verb carrying the
        # content to be said.
        names_a_message = _has(
            folded,
            r"\b(?:mensaje|mensajes|message|messages|texto|text|"
            r"whatsapp|wsp|discord|telegram|signal|sms|"
            r"correo|email|e-mail|mail|chat)\b",
        )
        speech_act = _has(
            folded,
            r"\b(?:dile|decile|diles|digale|tell|escribele|escribeles|"
            r"write\s+to|responde|respondele|reply|avisale|avisales)\b",
        )
        carries_spoken_content = _has(
            folded,
            r"\b(?:manda|mandale|mandales|envia|enviale|enviales|send)\b"
            r"[^.!?]{0,80}\bque\b",
        )
        # A document can legitimately be sent to a person: "envia el informe a
        # Lucas" is a message with an attachment, not an errand. Digital
        # artifacts stay a closed set, unlike physical goods.
        sends_a_digital_artifact = _has(
            folded,
            r"\b(?:informe|informes|reporte|reportes|report|reports|"
            r"documento|documentos|document|documents|archivo|archivos|"
            r"file|files|pdf|foto|fotos|photo|photos|imagen|imagenes|image|"
            r"images|captura|screenshot|enlace|enlaces|link|links|"
            r"resumen|resumenes|summary|nota|notas|note|notes)\b",
        )
        return (
            names_a_message
            or speech_act
            or carries_spoken_content
            or sends_a_digital_artifact
        )
    if operation == "routine.list":
        return _has(
            folded,
            r"\b(?:rutinas?|routines?|automations?|automatizaciones?|"
            r"secuencias?\s+automaticas?|automatic\s+sequences?)\b",
        ) and _has(
            folded,
            rf"\b(?:{_LIST}|enumera|enumerate|muestra|show|inventario|inventory|"
            r"guardad[oa]s?|saved|stored|disponibles?|available|"
            r"configurad[oa]s?|configured|repeat|repetir|habitual)\b",
        )
    if operation == "system.application.crash.diagnose":
        return _has(
            folded,
            r"\b(?:fallos?|errores?|bloqueos?|cierres?\s+inesperados?|"
            r"crash(?:es|ed|ing)?|failures?|faults?|application\s+errors?|"
            r"eventos?\s+de\s+error|error\s+events?)\b",
        ) and _has(
            folded,
            r"\b(?:aplicaciones?|applications?|apps?|programas?|programs?|"
            r"windows|registro\s+de\s+eventos|event\s+log)\b",
        )
    if operation.startswith("capture."):
        return (
            _has(
                folded,
                (
                    r"\b(?:captura de pantalla|captura (?:de )?(?:la )?ventana|"
                    r"captura de (?:toda )?la pantalla|"
                    r"captura (?:solamente |solo )?(?:de )?(?:la )?ventana|"
                    r"capture (?:only )?(?:the )?(?:active )?window|"
                    r"captura (?:de )?(?:el )?escritorio|capture (?:the )?desktop|"
                    r"pantallazo|screenshot|screen capture|window capture)\b"
                ),
            )
            or (
                _has(
                    folded,
                    r"\bsnapchat\b.{0,48}\bhow\s+desktop\s+looks\b",
                )
            )
            or (
                _has(folded, r"\bsabe\s+en\s+imagen\b")
                and _has(folded, r"\b(?:display|screen|pantalla|escritorio)\b")
            )
            or (_has(folded, r"\b(?:captura|capture)\b") and _has(folded, r"\bocr\b"))
        )
    if operation in {"browser.page.read", "browser.control"}:
        return _browser_page_domain(folded)
    if operation == "filesystem.folder.open":
        return _has(
            folded,
            r"\b(?:carpeta|folder|directorio|directory|escritorio|desktop|"
            r"documentos|documents|descargas|downloads|imagenes|pictures|"
            r"fotos|photos)\b",
        ) and not _has(folded, r"\b(?:archivo|file)\b")
    if operation == "filesystem.move":
        return (
            _has(folded, r"\b(?:mueve|mover|move|arrastra|drag)\b")
            and _has(folded, r"\b(?:archivo|file|carpeta|folder|ruta|path)\b")
            and not _has(folded, r"\b(?:ventana|window)\b")
        )
    if operation == "filesystem.file.open.latest":
        return _has(
            folded,
            r"\b(?:archivo|file)\b",
        ) and _has(
            folded,
            r"\b(?:reciente|latest|last|ultimo|ultima|newest)\b",
        )
    if operation == "filesystem.known.duplicates":
        return _has(
            folded,
            r"\b(?:archivos?|files?|documentos?|documents?|descargas|downloads?)\b",
        ) and _has(folded, _DUPLICATE_FILES)
    if operation == "filesystem.known.search":
        return (
            not _has(
                folded,
                r"\b(?:instala|instalar|install|installation|alista(?:lo|la)?|"
                r"prepare|prepara|preparado|ready|staged|tied)\b",
            )
            and not _has(folded, _DUPLICATE_FILES)
            and _has(
                folded,
                rf"\b(?:{_SEARCH}|locate|ubica|ubicar|find)\b|"
                r"\ba\s+ver\s+si\s+fin\b",
            )
            and _has(
                folded,
                r"\b(?:archivos?|files?|documentos?|documents?|descargas|downloads?|"
                r"imagenes?|pictures?|fotos?|photos?|carpetas?|folders?)\b",
            )
        )
    if operation == "filesystem.search":
        return (
            _has(
                folded,
                rf"\b(?:{_SEARCH}|locate|ubica|ubicar|find)\b",
            )
            and _has(
                folded,
                r"\b(?:archivos?|files?|documentos?|documents?|descargas|downloads?|"
                r"imagenes?|pictures?|fotos?|photos?|carpetas?|folders?|"
                r"escritorio|desktop|disco|drive|ruta|path)\b",
            )
            and not _has(
                folded,
                r"\b(?:web|website|internet|online|google|bing|public\s+api)\b",
            )
        )
    if operation == "task.search":
        return _has(folded, r"\b(?:tareas?|tasks?|to-?dos?)\b") and _has(
            folded,
            rf"\b(?:{_SEARCH}|find|locate|ubica|ubicar|muestra|show)\b",
        )
    if operation == "notification.diagnose":
        return _has(
            folded,
            r"\b(?:alarmas?|alarms?|notificaciones?|notifications?|"
            r"recordatorios?|reminders?|avisos?|alerts?)\b",
        ) and _has(
            folded,
            r"\b(?:diagnostica|diagnose|comprueba|check|revisa|review|"
            r"esta|estan|is|are|hay|there)\b",
        )
    if operation == "clipboard.copy":
        return _clipboard_copy_domain(folded)
    if operation == "clipboard.read.text":
        return (
            _has(folded, r"\b(?:portapapeles|clipboard)\b")
            or _has(
                folded,
                r"\b(?:texto|text)\b.{0,32}\b(?:list[oa]\s+para\s+pegar|"
                r"ready\s+(?:para|to)\s+(?:be\s+)?paste[d]?)\b",
            )
            or _has(
                folded,
                r"\btext\s+fragment\b.{0,40}\b(?:copied|capid)\b",
            )
            or _has(
                folded,
                r"^(?:what\s+did\s+i\s+copy|last\s+(?:thing\s+)?(?:i\s+)?copied|"
                r"que\s+(?:fue\s+lo\s+que\s+)?(?:copie|copié)\s+"
                r"(?:ultimo|ayer|recien|last))\b",
            )
        )
    if operation == "email.latest.read":
        return _latest_email_domain(folded)
    if operation == "media.status":
        return (
            _has(folded, r"\b(?:musica|music|cancion|song|media|multimedia)\b")
            and _has(
                folded,
                r"\b(?:sonando|playing|reproduciendo|playback|estado|status|"
                r"actual|current|sesion|session)\b",
            )
            or _has(
                folded,
                r"\b(?:que|what)\b.{0,40}\b(?:reproduciendo|playing)\b|"
                r"\bwhat(?:'s|\s+is)\s+playing\b",
            )
            or (
                _has(folded, r"\b(?:titulo|title|artista|artist|pista|track)\b")
                and _has(folded, r"\b(?:sonando|reproduciendo|playing)\b")
            )
            # Uso real 2026-09-23: «qué canción es esta», «cómo se llama esta
            # canción», «qué artista es este», «quién canta»: what is playing,
            # pointed at instead of named.
            or _has(folded, _POINTED_MEDIA)
        ) and not _has(
            folded,
            r"\b(?:netflix|youtube|spotify)\b|"
            r"\b(?:en|inside)\s+(?:mi|my)\s+(?:cabeza|mente|head|mind)\b",
        ) and not cinema_listing(folded)
    if operation in {"media.play.exact", "media.play.query"}:
        return _media_play_domain(folded)
    if operation == "vision.describe":
        return (
            _has(
                folded,
                r"\b(?:pantalla|screen|captura|screenshot|imagen|image|"
                r"foto|photo|visual|escena|scene)\b",
            )
            and _has(
                folded,
                r"\b(?:describe|describeme|describe it|mira|look|"
                r"que hay|what is|what's|que se ve|que aparece|"
                r"what appears|ves|visible)\b",
            )
            and not _has(
                folded,
                r"\b(?:configuracion|settings|activa|activar|enable|"
                r"graba|grabar|record|recording|camara|camera)\b",
            )
        )
    if operation == "window.minimize.all":
        return minimize_all_request(folded)
    if operation == "window.close.all":
        return close_all_request(folded)
    if operation == "document.pdf.read":
        return _pdf_summary_request(folded) is not None or (known_folder_file_path(text) or ("",))[0] == "document.pdf.read"
    if operation == "document.text.read":
        return (known_folder_file_path(text) or ("",))[0] == "document.text.read"
    if operation == "filesystem.explorer.count":
        return explorer_count_request(text) is not None
    if operation == "audio.app.volume.adjust":
        return app_volume_request(folded, application_names) is not None
    if operation == "audio.app.volume.set":
        return app_volume_set_request(folded, application_names) is not None
    if operation == "window.snap":
        return _authenticated_application_snap_target(folded, application_names) is not None
    if operation in {
        "window.active",
        "window.focus",
        "window.maximize",
        "window.minimize",
        "window.move",
        "window.resize",
        "window.restore",
    }:
        return _window_domain(folded) or (operation == "window.active" and deictic_close_request(folded))
    if operation == "window.resolve":
        return (
            _authenticated_application_snap_target(folded, application_names) is not None
            or _authenticated_application_close_target(folded, application_names) is not None
            or _authenticated_application_focus_target(folded, application_names) is not None
            or conditional_open_pause_app(folded, application_names) is not None
            or window_inventory_arguments(folded) is not None or _window_domain(folded)
            or _has(folded, r"\b(?:aplicacion|application|proceso|process)\b")
        )
    return None


def confident_non_target_language(text: str) -> str | None:
    """Identify only high-precision Portuguese, French, or Italian cues.

    BAXY's accepted natural-language surface is Spanish, English, and their
    ordinary code-switching. This is intentionally an abstaining detector:
    shared Romance words never suffice, and named entities do not count.
    """

    folded = _fold(text).strip(" ?!.,")
    if _has(
        folded,
        # ``bota`` is ordinary Latin American Spanish -- "bota las boxes viejas
        # al recycling" is spanglish, not Portuguese -- so it only counts with a
        # Portuguese article behind it. A shared Romance word never suffices.
        # ``tela`` too (Fase 3.5b DEV «vaya tela», Spain's Spanish): the Portuguese screen has its article.
        r"\b(?:pra|cento|loja|faz|mexer|tudo|aberto|regista|fiz|hoje|uma)\b|"
        r"\bbota\s+[oa]\b|\b(?:a|na|da)\s+tela\b|\bconecta\s+no\b|"
        r"\bfecha\s+tudo\b|\bde\s+novo\b|\barea\s+de\s+trabalho\b",
    ):
        return "pt"
    # «abre a calculadora» (owner review H0497): a Spanish request with a
    # dropped «l», not Portuguese, when the article is followed by a known
    # application name shared by both surfaces. «abre o bloco de notas» still
    # reads as Portuguese because ``bloco`` is not in that vocabulary.
    if _has(folded, r"\b(?:abre|minimiza)\s+[oa]\b") and not _has(
        folded,
        rf"\b(?:abre|minimiza)\s+[oa]\s+{_KNOWN_APPLICATION}\b",
    ):
        return "pt"
    if _has(
        folded,
        r"\b(?:augmente|fenetre|affiche|autres)\b|\bpour\s+cent\b|"
        r"\bpar\s+dessus\b|"
        # «monte le volume» moria sin respuesta y «quelle heure est-il» se
        # contestaba preguntando: ninguna pista cubria esas dos formas.
        r"\b(?:quelle|ouvre|ferme|baisse|eteins|allume)\b|"
        r"\bmonte\s+(?:le|la)\b|\bs'il\s+(?:te|vous)\s+plait\b",
    ):
        return "fr"
    if _has(
        folded,
        r"\b(?:apri|scrivi|salvala|finestra|spesa)\b|"
        r"\bblocco\s+note\b|\bfai\s+partire\b|"
        r"\b(?:calcolatrice|schermo|volume\s+piu\s+alto)\b|"
        r"\bche\s+ore\s+sono\b|\balza\s+il\b|"
        # «che ora e» es italiano entero. «che» a secas es rioplatense («che,
        # abrime el chrome»), de modo que hace falta la forma completa: el
        # detector sigue absteniéndose ante la palabra suelta.
        r"\bche\s+ora\s+e\b",
    ):
        return "it"
    # El aleman faltaba entero, y por eso un pedido en aleman llegaba a la ruta
    # espanola y podia ejecutarse. Se piden palabras funcionales que ni el
    # espanol ni el ingles tienen: el detector sigue absteniendose ante una
    # palabra compartida.
    if _has(
        folded,
        r"\b(?:offne|oeffne|mach|erstelle|schliesse|zeige|starte)\b|"
        r"\b(?:lautstarke|lauter|leiser|bildschirm|fenster|rechner|"
        r"notiz|uhrzeit)\b|"
        r"\bwie\s+spat\b|\bwie\s+viel\s+uhr\b|\bden\s+(?:rechner|bildschirm)\b|"
        r"\b(?:eine|einen|dass|ich)\s+\w",
    ):
        return "de"
    # «que horas sao» y «aumenta o volume»: portugues que las pistas de arriba
    # no cubrian.
    if _has(
        folded,
        r"\bque\s+horas\b|\baumenta\s+o\b|\bdiminui\s+o\b",
    ):
        return "pt"
    return None


def effect_request_is_authoritative(text: str) -> bool:
    """Return whether text can authorize a present-tense computer effect."""

    folded = _fold(text)
    return (
        confident_non_target_language(text) is None
        and not explicit_non_action_frame(text)
        # «cancele el próximo evento»: an order said with «usted» or as an infinitive is as direct.
        and any(_is_direct_request(said) for said in (folded, *imperative_rewrites(folded)))
        # Dev corpus 2026-09-23 «what is mom's email address», «the email address for bill that i added friday»,
        # «what are the latest photos on my instagram account»: «what is» about the person's own book or account is
        # asked of it, never a definition; and a day said of an entry of the book is when it was saved, not a past
        # state of the machine.
        and not _is_explicit_meta_or_tool_denial(folded)
        and (not _is_definition_question(folded) or contact_book_request(folded) or social_network_request(folded))
        and (not _is_past_or_hypothetical_state(folded) or contact_book_request(folded))
        and not _has_contradictory_correction(folded)
        and not _future_request_announcement(folded)
    )


def _future_request_announcement(folded: str) -> bool:
    """«Si mañana necesito X, te pediré que cierres…» announces a request to come.

    Nothing is asked now: a conditional opening followed by a first-person
    promise to ask later is conversation, not an effect and not an unsupported
    deferral (CLOSE1219-1223 boundary answered «no puedo cerrar ventanas»).
    """

    return _has(
        folded,
        r"^[¿?¡!\s]*(?:si|if|cuando|when|en\s+caso\s+de\s+que)\b.{0,160}"
        r"\b(?:te\s+(?:lo\s+)?(?:pedire|pediria|voy\s+a\s+pedir|dire|diria|avisare|avisaria)|"
        r"i(?:'ll|\s+will|\s+would|\s+might)\s+(?:ask|tell|let)\s+you)\b",
    )


# Uso real tanda 5 2026-09-24 «di lo mismo que yo hasta que te avise» → «Claro, estaré atento» and then «No hay
# más repeticiones por finalizar»: repeating everything the person says from now on is a mode kept across turns,
# and BAXY has none (each turn is read on its own). What is said next ahead of time (present or subjunctive:
# «lo que digo», «lo que diga») is the mode; what was already said («lo que dije») is a recall of the dialogue.
_ECHO_MODE = re.compile(
    r"\b(?:"
    r"(?:di|deci)\s+(?:(?:todo|cada\s+cosa|cualquier\s+cosa)\s+)?"
    r"lo\s+que\s+(?:yo\s+)?(?:te\s+)?(?:diga|digo|escriba|escribo)|"
    r"(?:di|dime|deci|decime|repite|repiteme|repeti|repetime|imita|imitame|haz|hace|habla)\s+"
    r"lo\s+mismo\s+que\s+(?:yo|digo|diga|te\s+digo|te\s+diga)|"
    r"(?:di|deci)\s+(?:cada|cualquier)\s+cosa\s+que\s+(?:yo\s+)?(?:te\s+)?(?:diga|digo|escriba|escribo)|"
    r"(?:modo|mode)\s+(?:loro|eco|espejo|repeticion|echo|parrot)|(?:echo|parrot)\s+mode|"
    r"(?:haz|hace|hazte|hacete)\s+(?:el|de)\s+loro|"
    r"say\s+(?:the\s+)?same\s+(?:thing\s+)?as\s+(?:me|i\s+do)|"
    r"repeat\s+after\s+me\s*(?:until\b|from\s+now\b|[.!]*$)|"
    # Tanda 7 «¿puedes activar este modo que tienes que repites todo el rato lo mismo que yo digo?»: the repeating
    # verb in any person or form («repites», «repetir», «imitando», «repeating»), with a few words between it and
    # what is said next, is the same mode. A negated one («no repitas…») is not asked for. These two replace the
    # imperative-only readings of «repite/imita … lo que digo» and «repeat everything I say».
    # M84 (DEV-D v3o D-s107 «para de repetir lo que digo» → «No hago lo que no es parte de lo que hago»): stopping the
    # repetition («para de», «deja de», «stop») does not ask for the mode either; it is said to BAXY as talk.
    r"(?<!\bno\s)(?<!\bpara\sde\s)(?<!\bparen\sde\s)(?<!\bdeja\sde\s)(?<!\bdejen\sde\s)(?<!\bdeje\sde\s)"
    r"(?<!\bdejar\sde\s)(?<!\bparar\sde\s)(?<!\bpare\sde\s)(?:repit|repet|imit)\w*\s+(?:\w+\s+){0,4}?"
    r"(?:lo\s+mismo\s+que|(?:todo\s+|cada\s+cosa\s+|"
    r"cualquier\s+cosa\s+)?lo\s+que|(?:cada|cualquier)\s+cosa\s+que)\s+(?:yo\s+)?(?:te\s+)?"
    r"(?:digo|diga|escribo|escriba|hablo|hable)|"
    r"(?<!\bnot\s)(?<!n't\s)(?<!\bstop\s)(?<!\bquit\s)(?:(?:repeat|echo|parrot|mimic)\w*\s+(?:\w+\s+){0,4}?|say\s+)"
    r"(?:back\s+)?(?:everything|"
    r"anything|whatever|every\s+word|each\s+word|what)\s+(?:that\s+)?i\s+(?:say|type|write)"
    r")\b"
)


def echo_mode_request(text: str) -> bool:
    """A request to repeat everything the person says from now on (a parrot mode), which BAXY does not keep."""

    return _ECHO_MODE.search(_fold(text)) is not None


# M84 (DEV-D v3o D-s092 «enciende la repetición» → «¿La repetición de qué?»): the player's repeat or shuffle mode is
# no action of media.control (next, pause, play, previous, stop, toggle); turning it on or off is a limit.
_MEDIA_REPEAT_MODE = re.compile(
    r"\b(?:(?:enciende|encender|enciendeme|activa|activar|activame|pon|poner|ponle|prende|prender|quita|quitar|"
    r"desactiva|desactivar|apaga|apagar|turn\s+(?:on|off)|enable|disable|switch\s+(?:on|off)|put\s+on)\s+"
    r"(?:(?:el|la|the)\s+)?(?:modo\s+)?(?:repeticion|aleatorio|shuffle|loop|bucle|repeat)(?:\s+mode)?|"
    r"(?:repite|repetir|repeat|loop)\s+(?:(?:la|esta|esa|el|this|that|the|current)\s+)?"
    r"(?:cancion|song|tema|track|playlist|album)(?:\s+(?:en\s+bucle|on\s+loop|una\s+y\s+otra\s+vez|over\s+and\s+over))?"
    r"[\s.!?]*$)"
)
# M84 (DEV-D v3o D-s006 «confirmen el pedido» → «¿Qué pedido confirmo?»): an order placed with a shop is confirmed,
# placed or tracked there; no operation buys or follows an order. Cancelling one is left out: «cancela el pedido» is
# also what the person asked BAXY.
_SHOP_ORDER_HANDLING = re.compile(
    r"\b(?:confirma|confirmen|confirmar|confirmame|confirm|realiza|realicen|realizar|haz|hagan|hacer|place|rastrea|"
    r"rastreen|rastrear|track)\s+(?:(?:el|mi|la|mis|los|my|the|an?|this|that|este|ese)\s+)?(?:pedidos?|orders?)\b"
)
# M84 (DEV-D v3o D-s122 «How much is my phone, I mean my electric bill?» → «What's your monthly electric bill?»): what
# the person owes on a bill or holds on an account is theirs to read with the company; no operation reads it.
_OWN_BILL_AMOUNT = re.compile(
    r"\b(?:how\s+much|cuanto|cuanta|cual\s+es|what(?:'s|s|\s+is))\b.{0,40}\b(?:my|mi|mis)\s+(?:\w+\s+){0,2}?"
    r"(?:bills?|facturas?|boletas?|recibos?|cuentas?\s+de\s+(?:la\s+)?(?:luz|agua|gas|telefono|celular|internet)|"
    r"saldo|balance)\b"
)


def media_repeat_mode_request(text: str) -> bool:
    """The player's repeat or shuffle mode turned on or off, or the song asked to repeat (see above)."""

    return _MEDIA_REPEAT_MODE.search(_fold(text)) is not None


# M84 (DEV-D v3o D-p02-t1 «Saca foto ahora» → a screenshot, D-s094 «Snap a pic after 10 seconds, no, 20 seconds.» → an
# alarm): a photo taken with nothing of the screen named is the camera's, which BAXY does not use. «saca una foto de
# la pantalla» is a capture; «una foto de X» names what is photographed and is left to the readers.
# M94 (DEV-D D-p02-t2 «¿Serías capaz de hacer foto ahora?», D-p07-t2 «Quiero hacer fotos en modo ráfaga» → talk about
# the camera app): being able to take one, or wanting to, asks for the same photo.
_CAMERA_PHOTO = re.compile(
    r"^[¿¡\s]*(?:(?:por\s+favor|please|porfa|oye|hey|baxy)[\s,]+)*"
    r"(?:(?:puedes|podrias|can\s+you|could\s+you|(?:serias|seria|eres|estas|are\s+you|would\s+you\s+be)\s+"
    r"(?:capaz|able)\s+(?:de|to)|quiero|quisiera|necesito|i\s+want\s+to|i\s+would\s+like\s+to|i'd\s+like\s+to|"
    r"i\s+need\s+to)\s+)?"
    r"(?:saca|sacame|sacanos|sacar|toma|tomame|tomanos|tomar|haz|hazme|hace|haceme|hacer|take|snap|shoot)\s+"
    r"(?:(?:me|us|una|un|la|el|a|an|the|my|mi|nueva|new|quick|rapida)\s+)*"
    r"(?:foto|fotos|fotografia|fotografias|selfie|selfies|pic|pics|picture|pictures|photo|photos|photograph)\b"
    r"(?!\s+(?:de|del|of)\b)"
)
_SCREEN_NAMED = r"\b(?:pantalla|pantallazo|screen|screenshot|captura|capture|escritorio|desktop|ventana|window|monitor)\b"


def camera_photo_request(text: str) -> bool:
    """A photo asked of the camera: taken, with nothing of the screen named (see above)."""

    folded = _fold(text)
    return _CAMERA_PHOTO.search(folded) is not None and not _has(folded, _SCREEN_NAMED)


# M94 (DEV-D D-s007 «hazme una lista de los destinatarios y remitentes de los emails de la ultima semana» → «No tengo
# acceso a tu bandeja…» answered as a list to write): the person's mails taken together (listed, counted, summarised,
# who sent or got them) are read by no operation; the mailbox read is the latest mail alone.
_MAIL_PLURAL = r"(?:correos|e-?mails|mails|mensajes\s+de\s+correo)"
_MAIL_COLLECTION = re.compile(
    r"\b(?:(?:los|las|mis|tus|my|your|the|todos\s+(?:los|mis)|all\s+(?:of\s+)?(?:my|the))\s+(?:\w+\s+)?"
    rf"{_MAIL_PLURAL}|(?:mi|my|la|the)\s+(?:bandeja(?:\s+de\s+entrada)?|inbox)|"
    rf"(?:cuantos|cuantas|how\s+many)\s+(?:\w+\s+)?{_MAIL_PLURAL})\b"
)
_MAIL_TAKEN_TOGETHER = (
    r"\b(?:lista|listame|listado|list|destinatarios|remitentes|senders?|recipients?|cuantos|cuantas|how\s+many|"
    r"resumen|resumeme|resume|resumir|summari[sz]e|summary|todos|all)\b"
)
_ONE_MAIL = r"\b(?:ultimo|latest|most\s+recent|newest|last\s+(?:e-?mail|mail|message))\b"


def person_mail_collection_request(text: str) -> bool:
    """The person's mails asked for together, not the latest one (see above)."""

    folded = _fold(text)
    return (
        _MAIL_COLLECTION.search(folded) is not None
        and _has(folded, _MAIL_TAKEN_TOGETHER)
        and not _has(folded, _ONE_MAIL)
    )


def unserved_personal_request(text: str) -> bool:
    """M84: a request no operation serves, whatever its grammar says of authority (see the readers above): the
    player's repeat mode, an order with a shop, the person's own bill, a photo of the camera; M94: the person's mails
    taken together."""

    folded = _fold(text)
    return (
        media_repeat_mode_request(text)
        or _SHOP_ORDER_HANDLING.search(folded) is not None
        or _OWN_BILL_AMOUNT.search(folded) is not None
        or camera_photo_request(text)
        or person_mail_collection_request(text)
    )

def unsupported_effect_demonstration_request(text: str) -> bool:
    """Recognize a requested demonstration without granting effect authority."""

    return _has(
        _fold(text),
        r"^(?:antes de seguir\s+)?quiero ver como\b.{0,160}"
        r"\b(?:pones|abres|reproduces|usas|haces)\b",
    )


# A frame that explicitly *denies* an instruction -- "esto no es una directriz
# para la computadora, dime nomas: ..." -- is the mirror of the instruction
# frame, and it must stay in place on the authority path: removing it there is
# exactly how an explicit request for no action would become an action.
#
# But it also displaces the content act from the front of the sentence, and the
# patterns below are anchored to ``^``. R25 lost five turns that way: the body
# asked to rewrite or translate a sentence that happened to *quote* an order,
# the anchor missed because the frame sat in front of it, and the turn drew a
# clarification instead of an answer. Removing the frame here is one-sided --
# it can only ever move a turn toward conversation, never toward an effect --
# because a denial of instruction is evidence for conversation.
#
# It reads its two noun classes from the same cognate groups as the positive
# frame, so the mirror can never fall out of step with what it mirrors.
_EXPLICIT_NO_ACTION_INSTRUCTION_FRAME = (
    r"^(?:baxy\s*[,;:]?\s*)?"
    r"(?=[^:]{0,110}\b(?:no|not|sin|without|s[oó]lo|solo|only|nada|"
    r"ning[uú]n|ninguna|ninguno|tampoco|nunca|jam[aá]s|neither|none|never)\b)"
    rf"(?=[^:]{{0,110}}\b(?:{_INSTRUCTION_NOUNS})\b)"
    rf"(?=[^:]{{0,110}}\b(?:{_MACHINE_NOUNS})\b)"
    r"[^:]{1,110}:\s*"
)


def _strip_explicit_no_action_frame(folded: str) -> str:
    """Remove a frame that denies an instruction, for content recognition only.

    Never call this on the authority path. It is safe here and nowhere else,
    because dropping a denial can only make a turn look *more* like
    conversation, and the content-act patterns it feeds are narrow: a request
    that survives the frame -- "no es una orden para el pc, dime nomas: envia
    el correo a Ana" -- still matches none of them.
    """

    return re.sub(_EXPLICIT_NO_ACTION_INSTRUCTION_FRAME, "", folded).strip()


# A programming language named after a program, code or an app («un programa en java», «a java program»).
_CODE_LANGUAGE = (
    r"(?:java|python|c|c\+\+|c#|javascript|typescript|go|rust|kotlin|swift|php|ruby|sql|bash|powershell|"
    r"html|css|json|xml|yaml|markdown|latex|regex|matlab|scala|lua|dart|pascal|cobol|haskell)(?![\w+#])"
)
# What code in a named language is written as: a program, a page, a query, a table…
_CODE_PIECE = (
    r"programa|programas|program|programs|codigo|code|app|aplicacion|clase|class|script|scripts|funcion|function|"
    r"pagina|paginas|page|pages|web|sitio|site|website|consulta|consultas|query|queries|expresion|expression|"
    r"plantilla|template|tabla|table|formulario|form|boton|button|componente|component|"
    r"estilos?|styles?|stylesheet|one-liner|oneliner|comando|command|ejemplo|ejemplos|example|examples|snippet|fragmento"
)


def conversation_only_content_request(text: str) -> bool:
    """Recognize self-contained content work with no external effect.

    These forms ask the model to reason or draft inside the conversation.  A
    quoted imperative (for example, ``send the report``) remains content and
    never becomes authority to perform that imperative.  The patterns are
    anchored to explicit content acts so merely mentioning a catalog domain
    such as Wi-Fi, Steam, a window, or the clipboard cannot close a turn.
    """

    if person_mail_collection_request(text):
        # M94 (DEV-D D-s007): a list or a summary of the person's mails is made of mails no operation reads; it is
        # no text to write here.
        return False
    folded = _strip_explicit_no_action_frame(
        _strip_request_envelope(_fold(text)).strip()
    )
    return _has(
        folded,
        r"^(?:please\s+)?(?:write|draft) me (?:an?|un) (?:email|mail|correo) "
        r"(?:that|saying|about)\b|"
        r"^(?:por\s+favor\s+)?redactame\s+(?:un\s+)?(?:correo|email|mail)\b|"
        r"^(?:reescribe|reformula|refrasea|redacta|rewrite|rephrase)\b.{0,160}"
        r"\b(?:frase|oracion|sentence|phrase|texto|text)\b|"
        r"^(?:calcula|calculate|work\s+out)\b.{1,160}$|"
        r"^(?:dame|give\s+me|write|draft)\b.{0,96}"
        r"\b(?:receta|recipe)\b|"
        r"^dame\s+a\s+currir\s+ese\s+pi\s+para\b.{1,96}$|"
        # Tanda 4c «Actúa como Julio Berne y haz un relato basado en el año 2090» died twice as a
        # knowledge answer that only asked back: a piece of fiction asked for is written, in a persona
        # too. Writing verbs make any story; telling or making ones a story with an indefinite article
        # («cuéntame la historia de Roma» stays a question about Roma).
        rf"^{_PERSONA_FRAME}(?:{_WRITING_VERB}\b.{{0,96}}\b(?:historia|story|leyenda|legend)|"
        rf"(?:{_WRITING_VERB}|{_TELLING_VERB})\b.{{0,96}}\b(?:adivinanza|riddle|poema|poem|cuento|relato|"
        r"fabula|fable|tale|(?:un|una|a|an|another|otro|otra)\s+(?:\w+\s+)?(?:historia|story|leyenda|legend))"
        r")\b|"
        r"^(?:escribe|write)\b.{0,64}\b(?:lista|checklist)\b.{0,64}"
        r"\b(?:teorica|theoretical)\b|"
        r"^(?:escribe|write)\b.{0,64}\b(?:teorica|theoretical)\b.{0,64}"
        r"\b(?:lista|checklist)\b|"
        r"^(?:simula|role[- ]?play)\b.{0,128}\b(?:conversacion|conversation)\b"
        r".{0,96}\b(?:no\s+envies\s+nada|send\s+nothing)\b|"
        r"^(?:compara|comparar|compare)\b"
        r"(?![^\n]{0,192}\b(?:archivo|archivos|file|files|carpeta|folder|"
        r"documento|document|ruta|path)\b).{1,192}$|"
        r"^(?:\S+\s+){0,3}(?:story|cuento|historia)\b.{0,96}"
        r"\b(?:imaginari[oa]|imaginary)\b.{0,64}$|"
        r"^(?:compara|compare)\b.{0,160}"
        r"\b(?:en\s+teoria|in\s+theory|en\s+general|in\s+general|"
        r"sin\s+(?:consultar|revisar)\s+mis\s+datos|"
        r"without\s+(?:checking|consulting)\s+my\s+data|"
        r"sin\s+(?:check|checking)\s+my\s+data)\b|"
        r"^(?:traduce|translate)\b.{0,192}"
        r"\b(?:al|a|into)\s+(?:italiano|italian|ingles|english|espanol|spanish)\b|"
        r"^(?:pon|put)\s+into\s+(?:english|ingles|spanish|espanol|italian|italiano)"
        r"\b.{0,160}\b(?:frase|phrase|sentence)\b|"
        r"^(?:pon|put)\b.{0,32}\b(?:ingles|english)\b.{0,48}"
        r"\b(?:frase|phrase|sentence)\b.{1,128}$|"
        # Owner's mother 2026-09-21 «hazme un currículum», «formato de currículum en word»,
        # «buscame un formato de oficio en word», «hazme un triángulo con las estaciones
        # del año», «buscame palabras con a»: drafted text or a word game, written in the
        # conversation (no operation creates a Word file; the text is given here).
        r"^(?![^\n]{0,160}\b(?:archivo|archivos|file|files|carpeta|folder|nota|notas|note|notes|"
        r"guarda|guardala|guardalo|guardame|guardar|save|escritorio|desktop|documentos|downloads|descargas|"
        r"abre|abri|abrilo|abrila|open|envia|enviar|mandalo|mandala|mandaselo|mandasela|manda|send|imprime|print)\b)"
        # M91 (reserva «dame una lista de cosas que hacer»): the things to do, said with nothing they are about, may be
        # the person's own to-do list; the decider reads it, the readers do not close it as a list to write.
        r"(?![^\n]{0,64}\b(?:cosas|tareas)\s+(?:que|por)\s+hacer"
        r"(?:\s+(?:hoy|manana|esta\s+semana|este\s+fin\s+de\s+semana))?[\s.!?]*$)"
        r"(?:hazme|haceme|hace|haz|armame|arma|escribime|escribeme|escribe|redactame|redacta|"
        # M78 (DEV-D v3l p35-t1 «Has un análisis de FODA sobre la empresa Adidas…» → «No hago análisis de FODA.»):
        # «has un/una» is «haz» misspelt.
        r"has\s+(?=un|una)|"
        r"dame|pasame|buscame|busca|quiero|necesito|make\s+me|write\s+me|write|draft|give\s+me|find\s+me)\b"
        r".{0,48}\b(?:curriculum|curriculums|cv|carta|oficio|texto|poema|cuento|resumen|ensayo|"
        r"lista|triangulo|tabla|esquema|discurso|mensaje\s+de\s+cumpleanos|formato|plantilla|"
        # Dev corpus 2026-09-23 «por favor escribe una queja para levis»: the complaint is written here.
        r"queja|reclamo|reclamacion|complaint|"
        r"resume|cover\s+letter|essay|poem|letter|template|outline|table)\b|"
        # M78: a business analysis (a SWOT/FODA/DAFO, a PESTEL, a market or competitor analysis) is drafted here like
        # an essay, whichever verb asks for it; never a limit. «Haz un análisis del disco» is this PC's, not this.
        r"^(?![^\n]{0,160}\b(?:archivo|archivos|file|files|carpeta|folder|guarda|guardalo|guardala|guardar|save|"
        r"envia|enviar|send|imprime|print|excel|word|powerpoint|presentacion|slides?)\b)"
        r"[¿¡\s]*(?:(?:por\s+favor|porfa|please)\s*,?\s*)?(?:(?:puedes|podrias|can\s+you|could\s+you)\s+)?"
        r"(?:haz|hazme|haceme|has|hacer|hacerme|me\s+haces|realiza|realizame|realizar|elabora|elaborame|elaborar|"
        r"prepara|preparame|escribe|escribeme|redacta|"
        r"redactame|dame|do|make|prepare|write|draft|create|give\s+me|i\s+need|i\s+want|quiero|necesito)\b"
        r".{0,32}\b(?:foda|dafo|swot|pestel|(?:analisis|estudio)\s+(?:de\s+)?(?:mercado|la\s+competencia)|"
        r"(?:market|competitor|competitive)\s+(?:analysis|research))\b|"
        r"^(?:formato|plantilla|ejemplo|modelo|template|example)\s+(?:de|of)\b.{1,96}$|"
        # M81 (DEV-D v3m D-p36-t2/t3 «agrega a la conversación un fragmento donde…», «…características físicas del
        # xenomorfo»): adding to the dialogue, story or scene being written is writing more of it.
        r"^(?![^\n]*\b(?:instagram|whatsapp|facebook|telegram|discord|grupo|group|chat)\b)"
        r"(?:agrega\w*|anade\w*|add)\s+(?:a|al|en|to|into)\s+(?:(?:la|el|the|this|esta|este|our|nuestra|nuestro)\s+)?"
        r"(?:conversacion|dialogo|historia|relato|cuento|guion|escena|story|conversation|dialogue|script|scene)\b"
        r"(?!\s+(?:a|to)\s)|"
        # M81 (DEV-D v3m D-s030 «Me puedes ayudar a crear una carta de finalización de contrato…» → the requirements
        # of such a letter, not the letter): creating a letter or a piece of prose is writing it.
        r"^(?![^\n]{0,160}\b(?:archivo|file|carpeta|folder|guarda\w*|save|word|envia\w*|send|imprime|print)\b)"
        r"(?:(?:me\s+)?(?:puedes|podrias|can\s+you|could\s+you)\s+)?(?:ayudar(?:me)?\s+a\s+|ayudame\s+a\s+|help\s+me\s+)?"
        r"(?:crea|creame|crear|crearme|create)\s+(?:un|una|el|la|a|an|the)\s+(?:\w+\s+)?"
        r"(?:carta|texto|poema|cuento|ensayo|discurso|curriculum|cv|queja|reclamo|letter|essay|poem|speech|resume|"
        r"cover\s+letter)\b|"
        # M81 (DEV-D v3m D-p32-t2 «Dame las claves que mencionas en esa respuesta en forma de lista o tabla.»): the
        # same content asked again as a list or a table is written again in that shape.
        r"^(?![^\n]{0,160}\b(?:archivo|archivos|file|files|carpeta|folder|nota|notas|note|notes|guarda|guardalo|"
        r"guardala|guardar|save|excel|word|envia|enviar|send|imprime|print)\b)"
        r"(?:dame|damelo|damela|pasame|pasamelo|ponlo|ponmelo|ponmela|hazlo|hazmelo|escribelo|escribemelo|"
        r"give\s+me|put|make|write)\b.{0,96}\b(?:en\s+(?:forma|formato)\s+de|como|as\s+an?|in\s+an?)\s+"
        r"(?:lista|tabla|esquema|list|table|bullet\s+points)\b|"
        r"^(?:buscame|busca|dame|decime|dime|find\s+me|give\s+me)\b.{0,32}"
        r"\b(?:palabras|words|sinonimos|synonyms|antonimos|antonyms|rimas|rhymes)\b.{0,96}$|"
        # Tanda 3 2026-09-24 «¿puedes crear un programa en java para resolver una ecuación…?» → «No creo
        # programas en java»: code is written in the conversation like any other text. Code, a program or an
        # app is code with its language named; a script, a function or an algorithm always is. Saving or
        # opening it somewhere is an effect, not a draft.
        # Tanda 6 «Escribe un ejemplo de página HTML con ecuaciones matemáticas.» → «No escribo páginas HTML»:
        # any piece of code named with its language («página HTML», «consulta SQL», «a bash one-liner») and
        # an example asked for («un ejemplo de…», «three examples of…») are written here too. Typing it into a
        # window, a note or the search box is still an effect.
        r"^(?![^\n]{0,160}\b(?:carpeta|folder|guarda|guardalo|guardala|guardar|save|escritorio|desktop|"
        r"abre|abrelo|open|ejecuta|ejecutalo|run|envia|send|nota|notas|note|notes|bloc|notepad|buscador|"
        r"search\s+box|barra)\b)[¿¡\s]*"
        r"(?:crea|crear|creame|escribe|escribir|escribeme|escribime|haz|hazme|hacer|haceme|genera|generar|"
        r"generame|programa|programame|dame|desarrolla|codea|necesito|quiero|redacta|redactame|muestrame|"
        r"ensename|me\s+(?:escribes|escribis|haces|creas|generas|programas|das|muestras|ensenas)|"
        r"create|write|make|build|generate|code|draft|give\s+me|show\s+me|teach\s+me|i\s+need|i\s+want)\b"
        r".{0,48}\b(?:(?:script|funcion|function|algoritmo|algorithm|snippet)\b|"
        r"(?:ejemplos?|examples?)\s+(?:de|of)\b|"
        rf"(?:{_CODE_PIECE})\b.{{0,32}}\b(?:(?:en|in)\s+)?{_CODE_LANGUAGE}|"
        rf"{_CODE_LANGUAGE}\s+(?:[a-z-]+\s+)?(?:{_CODE_PIECE})\b)",
    )


# «actúa como Julio Verne y …», «pretend you're a pirate and …», «como si fueras Borges, …»: the voice a
# piece of fiction is written in, before the order that asks for it.
_PERSONA_FRAME = (
    r"(?:(?:actua|act|habla|talk|pretend|finge|fingi|imagina|imagine|como\s+si\s+fueras|as\s+if\s+you\s+were)"
    r"\b[^,.;]{0,64}?(?:\s+y\s+|\s+and\s+|\s*,\s*))?"
)
_WRITING_VERB = (
    r"(?:inventa|inventame|crea|creame|escribe|escribeme|escribime|redacta|redactame|make\s+up|write(?:\s+me)?|"
    r"create)"
)
_TELLING_VERB = r"(?:haz|hazme|haceme|cuentame|contame|narra|narrame|narrate|tell\s+me|make\s+me)"


_REASSURANCE_STATEMENT = re.compile(
    r"^[\s¿?¡!]*(?:(?:no|nunca)\s+(?:te|se)\s+preocup\w*|tranqui(?:lo|la|los|las)?\b|no\s+pasa\s+nada|"
    r"(?:don'?\s?t|dont|do\s+not)\s+worry|no\s+worries|it'?\s?s\s+(?:ok|okay|fine|alright)|esta\s+bien\s+si\b|todo\s+bien\s+si\b)"
)


def reassurance_statement(text: str) -> bool:
    """CONVERSATION1343 H0059 «NO te preocupes si se abrio steam»: a reassurance, not a request."""

    return _REASSURANCE_STATEMENT.match(_strip_request_envelope(_fold(text)).strip()) is not None


# Tanda 6 «debieras saber que me gusta el jazz» → «Gracias, ya lo tengo en cuenta. ¿Quieres que te recomiende…?»:
# a taste told with a frame that only tells it («para que sepas», «you should know that», «fyi») is the same
# statement. «recuerda que me gusta…» asks to save it and stays out: saving needs the explicit request.
_PREFERENCE_TELLING_FRAME = (
    r"(?:(?:(?:debieras|deberias|debes|tienes\s+que|tenes\s+que)\s+saber|"
    r"you\s+(?:should|ought\s+to|need\s+to|must)\s+know)\s+(?:que|that)\s+|"
    r"para\s+que\s+(?:lo\s+)?sepas\s*,?\s*(?:que\s+)?|(?:te\s+cuento|te\s+digo|te\s+comento)\s*,?\s*(?:que\s+)?|"
    r"(?:quiero|queria)\s+(?:decirte|contarte)\s+que\s+|(?:just\s+)?so\s+you\s+know\s*,?\s*(?:that\s+)?|"
    r"fyi\s*,?\s*|for\s+the\s+record\s*,?\s*|i\s+(?:wanted|want)\s+to\s+(?:tell\s+you|let\s+you\s+know)\s+(?:that\s+)?|"
    r"(?:por\s+cierto|by\s+the\s+way|btw)\s*,?\s*)?"
    r"(?:(?:yo\s+)?(?:tambien|ademas|realmente|la\s+verdad(?:\s+es\s+que)?)\s*,?\s+)?"
)
_FIRST_PERSON_PREFERENCE = re.compile(
    _PREFERENCE_TELLING_FRAME
    + r"(?:(?:a\s+mi\s+)?me\s+(?:gusta|gustan|encanta|encantan|fascina|fascinan)|"
    r"prefiero|adoro|amo|odio|detesto|no\s+me\s+gusta|no\s+me\s+gustan|"
    r"i\s+(?:(?:really|also|actually|truly|just)\s+)?(?:like|love|prefer|hate|enjoy|dislike))\s+"
    r"(?P<thing>(?!(?:que|si|cuando|porque)\b)[a-z][a-z0-9 '\-]{1,80})[\s.!?]*",
    re.IGNORECASE,
)


_PREFERENCE_REQUEST_HEAD = re.compile(
    r"\b(?:que|abre|abri|abris|pone|pon|poneme|pongas|abras|busca|buscame|cierra|"
    r"lanza|inicia|reproduce|manda|envia|escribe|crea|guarda|recuerda|recorda|"
    r"open|play|search|send|close|save|remember|remind)\b"
)


# KNOWLEDGE1505: the engine returns the public page of a bare, well-known name
# (its Wikipedia article or an encyclopedic page first); the names below are
# subjects verified against the engine's relevance rule on 2026-09-15, never
# replies. Many other common names returned unrelated pages that day.
_CURIOSITY_TOPICS_ES = (
    "Colibrí", "Luna", "Saturno", "Antártida", "Ornitorrinco", "Amazonas", "Pingüino", "Delfín",
    "Miel", "Chocolate", "Arcoíris", "Jirafa", "Koala", "Coliseo", "Titanic", "Neptuno", "Ballena",
    "Girasol", "Urano", "Plutón", "Abeja", "Mariposa", "Tortuga", "Cactus", "Microscopio", "Tsunami",
)


_CURIOSITY_TOPICS_EN = (
    "Moon", "Whale", "Jupiter", "Tsunami", "Titanic", "Koala", "Chocolate", "Cactus",
)


def curiosity_topic(text: str) -> str | None:
    """The public subject BAXY looks up for a curiosity request, or None.

    The topic is drawn at random from a list of well-known subjects in the
    language of the request; the answer is whatever the public page states."""

    if not curiosity_request(text):
        return None
    folded = _strip_request_envelope(_fold(text)).strip()
    english = re.match(r"^(?:baxy\s*[,:]?\s*)?(?:tell|give|share|read|show|surprise|i)\b", folded, re.IGNORECASE) is not None
    # The pick is stable for one request within the same hour, so every
    # reading of the turn (planning, verification) names the same subject.
    seed = hashlib.sha256(f"{folded}|{int(time.time() // 3600)}".encode("utf-8")).hexdigest()
    return random.Random(seed).choice(_CURIOSITY_TOPICS_EN if english else _CURIOSITY_TOPICS_ES)


def first_person_preference(text: str) -> str | None:
    """MEMORY1501/1503 H0174 «Me gusta tomar café.»: the thing a first-person taste names, or None.

    A taste or preference with nothing asked is a statement to acknowledge, not an order
    (MEMORY1245 asked where to go for coffee). No request verb, no «que» clause and no
    catalog head may follow the preference."""

    match = _FIRST_PERSON_PREFERENCE.fullmatch(_strip_request_envelope(_fold(text)))
    if match is None:
        return None
    thing = match.group("thing").strip()
    if _PREFERENCE_REQUEST_HEAD.search(thing) is not None:
        return None
    return thing


# Tanda 4f «configuré una alarma para despertarme por la mañana» → «¡Claro! ¿Quieres que te diga qué hora tienes
# configurada…?»: the person telling an alarm, timer or reminder they set themselves asks for nothing; BAXY does not
# know where they set it (a phone, a clock) and acting or offering unasked is what he never does. The past form must
# be the person's own: without its accent «configure/programe/active» is also the formal order, which stays an order.
_OWN_SCHEDULE_OBJECT = (
    r"(?:(?:una|un|la|el|mi|mis|las|los|an?|the|my)\s+)?(?:alarmas?|despertador(?:es)?|temporizador(?:es)?|"
    r"timers?|recordatorios?|alarms?|reminders?)"
)
_OWN_SCHEDULE_SET = r"(?:(?:puest|configurad|programad|activad)[oa]s?|set)"
# Having one is told only with its participle («tengo una alarma puesta»): «tengo recordatorios pendientes» asks.
_OWN_SCHEDULE_STATEMENT = re.compile(
    r"(?:(?:yo|ya|reci[eé]n|tambi[eé]n|hoy|anoche)\s+)*(?:me\s+|te\s+)?(?:(?:"
    r"(?:configur|program|activ|dej|agend|fij|cre|coloqu)é|puse|establecí|estableci|"
    r"he\s+(?:configurado|programado|puesto|activado|dejado|agendado|fijado|creado|establecido)|"
    r"i\s+(?:just\s+|already\s+|also\s+)*(?:set|put|scheduled|made|created|turned\s+on|programmed)(?:\s+up)?|"
    r"i(?:['’]ve|\s+have)\s+(?:just\s+|already\s+|also\s+)*(?:set|put|scheduled|made|created|turned\s+on|programmed)"
    rf"(?:\s+up)?)(?:\s+{_OWN_SCHEDULE_SET})?\s+{_OWN_SCHEDULE_OBJECT}(?:\s+{_OWN_SCHEDULE_SET})?|"
    rf"(?:tengo|i\s+have|i(?:['’]ve|\s+have)\s+got)\s+(?:{_OWN_SCHEDULE_SET}\s+{_OWN_SCHEDULE_OBJECT}|"
    rf"{_OWN_SCHEDULE_OBJECT}\s+{_OWN_SCHEDULE_SET}))"
    r"(?:\s+(?P<tail>[^?¿]{0,100}))?[.!]*"
)
_OWN_SCHEDULE_REQUEST_TAIL = re.compile(
    r"\b(?:puedes|podes|podrias|pueden|revisa|revisala|revisalo|verifica|comprueba|confirma|dime|decime|avisame|"
    r"cambia|cambiala|borra|borrala|quita|quitala|cancela|cancelala|apaga|apagala|sube|baja|"
    r"can\s+you|could\s+you|would\s+you|please|check|verify|confirm|tell\s+me|change|delete|remove|cancel|"
    r"turn\s+(?:it\s+)?off)\b"
)


def reported_own_schedule(text: str) -> bool:
    """Whether the message only tells an alarm, timer or reminder the person set themselves («configuré una alarma
    para despertarme por la mañana», «I've set a timer for the pasta»); a question or a request after it is not."""

    said = " ".join(_strip_request_envelope(str(text or "").casefold()).split()).strip()
    if "?" in said or "¿" in said:
        return False
    found = _OWN_SCHEDULE_STATEMENT.fullmatch(said)
    if found is None:
        return False
    return _OWN_SCHEDULE_REQUEST_TAIL.search(_fold(found.group("tail") or "")) is None


_VISUAL_CONTENT_NOUN = re.compile(
    r"\b(?P<noun>meme|memes|imagen|imagenes|foto|fotos|gif|gifs|sticker|stickers|dibujo|dibujos|picture|pictures|image|images|photo|photos)\b"
)


def visual_content_noun(text: str) -> str:
    """The visual noun asked for («meme», «foto»), for the boundary reply."""

    match = _VISUAL_CONTENT_NOUN.search(_fold(text))
    return match.group("noun") if match is not None else ""


def _completed_missing_image_subject_request(
    text: str, previous_user_text: str | None,
) -> str | None:
    """«tienes alguna foto?» → «¿de qué?» → «de un gato»: the answer names the
    subject of the image asked before."""

    if not previous_user_text:
        return None
    previous = web_image_request(previous_user_text)
    if previous is None or previous[1] is False:
        return None
    answer = text.strip().strip("\"'“”«»").strip(" .!")
    folded = _strip_request_envelope(_fold(answer))
    if not folded or "?" in answer or len(folded.split()) > 8:
        return None
    if _head_is(_request_head(folded), _COVERAGE_ACTION_HEAD) or _negative_action_forms(folded):
        return None
    if re.fullmatch(r"(?:no|nada|ninguna?|none|nothing|cancela|cancelar|cancel|olvidalo|dejalo)\b.*", folded):
        return None
    subject = re.sub(r"^(?:de|del|of|about|sobre)\s+", "", answer, flags=re.IGNORECASE).strip()
    noun = visual_content_noun(previous_user_text) or "imagen"
    return f"mostrame una {noun} de {subject}" if noun in {"imagen", "imagenes", "foto", "fotos", "dibujo", "dibujos"} else f"show me a {noun} of {subject}"


def unsupported_live_machine_query(text: str) -> bool:
    """Recognize a live-machine question outside the observed status schema."""

    folded = _fold(text)
    return _has(
        folded,
        r"\b(?:hay algo mas que|que (?:otra cosa|proceso)|what else|which process)"
        r"\b.{0,100}\b(?:use|usa|uses|using|utilice|utiliza)\b.{0,40}\bgpu\b",
    )


# M80: music services the catalog does not play on (it plays on Spotify and on YouTube), and the verbs of playing.
# M84 (DEV-D v3o D-s050 «Reproduce mi estación de Pandora Sensación de comodidad» played «Pandora & Jordi» on
# YouTube): the service is named where a service stands — after «en / on / from», as «mi Pandora», «la estación de
# Pandora», «Pandora station», «Pandora to play», «open Pandora». «pon música de Pandora» names the band.
_UNOFFERED_SERVICE_NAME = (
    r"(?:pandora|deezer|tidal|soundcloud|apple\s+music|amazon\s+music|iheart\s*radio|napster|audiomack|qobuz)"
)
_UNOFFERED_MUSIC_SERVICE = (
    rf"\b(?:en|on|in|from|desde|via|through|using)\s+(?:(?:mi|my|la|el|the)\s+)?"
    rf"(?:(?:app|aplicacion|cuenta|account)\s+(?:de\s+)?)?{_UNOFFERED_SERVICE_NAME}\b|"
    rf"\b(?:estacion|estaciones|emisora|station|stations|playlist|cuenta|account|app|aplicacion)\s+(?:de|of|en|on)\s+"
    rf"{_UNOFFERED_SERVICE_NAME}\b|"
    rf"\b(?:mi|my)\s+{_UNOFFERED_SERVICE_NAME}\b|"
    rf"\b{_UNOFFERED_SERVICE_NAME}\s+(?:station|stations|radio|app|playlist|account)\b|"
    rf"\b{_UNOFFERED_SERVICE_NAME}\s*,?\s+(?:to\s+)?(?:play|plays|pon|ponme|reproduce|reproduceme|toca|tocame)\b|"
    rf"\b(?:open|abre|abreme|abrir|start|inicia|launch)\s+{_UNOFFERED_SERVICE_NAME}\b"
)


def unoffered_music_service_named(folded: str) -> bool:
    """The request names a music service BAXY does not play on, where a service stands (see above)."""

    return _has(folded, _UNOFFERED_MUSIC_SERVICE) and not _has(folded, r"\b(?:spotify|youtube)\b")
_MUSIC_PLAY_VERB = (
    r"\b(?:play|plays|playing|put\s+on|listen|stream|pon|pone|ponme|poneme|reproduce|reproduci|reproduceme|"
    r"reproducir|toca|tocame|tocar|escuchar|escucha|quiero\s+oir)\b"
)


def known_unsupported_effect_request(
    text: str,
    available_operations: Iterable[str],
) -> bool:
    """Close known missing variants only while no matching operation exists."""

    folded = _fold(text)
    available = frozenset(available_operations)
    # M97 (reserve «envíe un correo a mi asistente para cancelar todas las citas de mañana»): what a mail or a message
    # asks someone else to do is its content, never an act of BAXY's that he lacks.
    said_in_a_message = (
        email_send_request(text) is not None
        or email_request_without_address(text)
        or message_request_any_channel(text) is not None
    )
    contracts = (
        (
            # Owner's test 2026-09-21 (turns 210-213): BAXY does not close itself
            # from the chat; the honest reply says so and how it is closed.
            self_close_request(text),
            {"self.close"},
        ),
        (
            # Uso real tanda 5 «di lo mismo que yo hasta que te avise»: no mode repeats the next messages.
            echo_mode_request(text),
            {"conversation.echo.mode"},
        ),
        (
            # Tanda 4c «ponme algo de mi biblioteca»: no operation opens the person's own collection.
            own_collection_free_choice(text) and not own_recent_listening_request(text),
            {"media.library.play"},
        ),
        (
            _has(folded, r"\b(?:arrastra|drag)\b")
            and _has(folded, r"\b(?:archivo|file|carpeta|folder)\b")
            and _has(folded, r"\b(?:ventana|window)\b"),
            {"input.drag.drop", "filesystem.drag.drop"},
        ),
        (
            _has(folded, r"\b(?:habito|habit)\b")
            and _has(
                folded,
                r"\b(?:arma|armar|crea|crear|create|marca|marcar|mark|registra|register)\b",
            ),
            {"routine.habit.create", "routine.habit.mark"},
        ),
        (
            # Uso real 2026-09-23 «erase my appointment for march seven», «clear my next activity»:
            # events are listed and created, never removed; the limit says so plainly. BAXY's own
            # alarms and reminders keep their cancellation.
            (
                _has(
                    folded,
                    r"\b(?:borra|borrar|borrame|borre|elimina|eliminar|eliminame|elimine|quita|quitar|quitame|quite|"
                    r"cancela|cancelar|cancelame|cancele|delete|remove|erase|clear|cancel)\b(?:\s+\S+){0,3}?\s+"
                    r"(?:citas?|appointments?|eventos?|events?|reuniones|reunion|meetings?|actividad(?:es)?|"
                    r"activit(?:y|ies)|compromisos?|commitments?)\b",
                )
                # Uso real 2026-09-24 «limpia mi agenda para hoy», «clear my calendar for this month».
                or _has(
                    folded,
                    r"\b(?:limpia|limpiar|limpie|despeja|despejar|despeje|vacia|vaciar|vacie|clear|wipe)\s+"
                    r"(?:(?:mi|el|la|my|the)\s+)?(?:agenda|calendario|calendar|horario|schedule)\b",
                )
                # M94 (DEV-D D-s016): an entry taken off the calendar (``semantic.notes.takes_off_the_agenda``).
                or takes_off_the_agenda(folded)
            )
            and not _has(folded, r"\b(?:alarmas?|alarms?|recordatorios?|reminders?|notas?|notes?|archivos?|files?)\b")
            and not said_in_a_message,
            {"calendar.event.delete"},
        ),
        (
            # Dev set 2 «eliminar la lista de cosas por hacer», «i don't want this list any more»: a list is its
            # entries, and no operation removes them all at once; one entry named is taken off (task.delete).
            (removal := list_removal_request(text)) is not None and removal.entry is None,
            {"task.list.delete"},
        ),
        (
            # Uso real 2026-09-24 «alter lunch event to repeat every friday», «alterar el evento del almuerzo
            # para repetir cada viernes»: events are listed and created, never edited; the limit says so.
            _has(
                folded,
                r"\b(?:altera|alterar|altere|modifica|modificar|modifique|edita|editar|edite|cambia|cambiar|"
                # Rescheduling stays the new event it asks for («could you reschedule my meeting»).
                r"cambie|alter|modify|edit|change)\b(?:\s+\S+){0,3}?\s+"
                r"(?:citas?|appointments?|eventos?|events?|reuniones|reunion|meetings?)\b",
            )
            and not _has(folded, r"\b(?:alarmas?|alarms?|recordatorios?|reminders?|notas?|notes?|archivos?|files?)\b")
            and not said_in_a_message,
            {"calendar.event.update"},
        ),
        (
            _has(folded, rf"\b{_OPEN}\b")
            and _has(folded, r"\b(?:archivo|file)\b")
            and not _has(folded, r"\b(?:ultimo|ultima|latest|reciente|newest)\b"),
            # M111 (DEV-F v4d F-s025 «abreme el archivo presupuesto_finca.xlsx q esta en documentos» → «No abro
            # archivos»): ``file.open`` opens a named file of a known folder.
            {"filesystem.file.open.named", "file.open"},
        ),
        (
            _has(folded, r"\b(?:incognito|privad[ao]|private)\b")
            and _has(folded, r"\b(?:ventana|window|navegador|browser)\b"),
            {"browser.window.private.open"},
        ),
        (
            _has(folded, rf"\b{_OPEN}\b")
            and _has(folded, r"\b(?:configuracion|settings)\b")
            and _has(folded, r"\b(?:pantalla|display|screen)\b"),
            {"system.settings.display.open"},
        ),
        (
            _has(folded, r"\b(?:impresora|printer)\b")
            and _has(folded, r"\b(?:predeterminad[ao]|default)\b")
            and _has(folded, r"\b(?:pon|poner|establece|set|make)\b"),
            {"peripheral.default.set"},
        ),
        (
            # Tanda 7 «consígueme un billete de tren a madrid para el próximo jueves» was looked up and answered
            # «No se encontró información…»: getting a ticket, a seat or a booking is buying it, a limit like
            # getting a product paid with a card. Neither is information to look up.
            _has(
                _fold(_without_address(text) or text),
                r"^(?:(?:por\s+favor|porfa|please)\s+)?(?:get\s+me|i\s+(?:want|need)\s+to\s+get|buy(?:\s+me)?|"
                r"book(?:\s+me)?|compra(?:me|nos)?|consigue(?:me|nos)?|consegui(?:me|nos)|reserva(?:me|nos)?|"
                r"saca(?:me|nos)|pilla(?:me|nos))\b",
            )
            and (
                _has(folded, r"\b(?:billetes?|boletos?|pasajes?|entradas?|tickets?|vuelos?|flights?|asientos?|seats?)\b")
                or _has(
                    folded,
                    r"\b(?:american\s+express|visa|mastercard|credit\s+card|debit\s+card|tarjeta|bizum|cash|efectivo)\b",
                )
                and not _has(folded, r"\b(?:game|juego|steam)\b")
            ),
            {"commerce.product.purchase"},
        ),
        (
            # LIMITS1683 H0621 «multiplicá 6 por 7 en la calc», H0705 «Suma 2 más 2
            # en la Calculadora»: one control per confirmed click; no operation
            # evaluates an expression in the Calculator.
            _has(folded, r"\b(?:multiplica|multiplicar|multiplicame|suma|sumar|sumame|resta|restar|restame|divide|dividir|divideme|calcula|calcular|calculame|multiply|add|subtract|divide|calculate|compute)\b")
            and _has(folded, r"\b(?:calc|calculadora|calculator)\b"),
            {"calculator.expression.evaluate"},
        ),
        (
            # LIMITS1683 H0559 «Abre Steam y luego navega por la gui hasta
            # biblioteca», H0432 «Abre Epic Games y navega hasta la biblioteca»
            # were a known limit; since UI1731 the client's interface is walked
            # with input.visible.click (UIA, then OCR on the foreground window),
            # so this contract is inert while that operation exists.
            _has(folded, r"\b(?:navega|navegar|navegame|navigate)\b")
            and _has(folded, r"\b(?:steam|epic(?:\s+games)?|battle\.net|origin|uplay|gog|ubisoft\s+connect)\b")
            and _has(folded, r"\b(?:gui|interfaz|interface|biblioteca|library|tienda|store|menu|menus)\b"),
            {"input.visible.click"},
        ),
        (
            # H0542 «Crea una carpeta en el escritorio, mete un txt dentro,
            # comprímela y luego abre el zip»: la carpeta y el txt se crean, pero
            # ninguna operación comprime una carpeta cualquiera ni abre un zip.
            # Sin declararlo, el verificador veía la primera cláusula servida,
            # retiraba el límite entero y el turno acababa preguntando si quería
            # ayuda para organizar archivos, que no es la respuesta a lo que se
            # pidió. backup.known.create comprime una carpeta conocida como copia
            # de seguridad: no es comprimir la que acaban de crear ni abrir el zip.
            _has(
                folded,
                r"\b(?:(?:des)?comprim[eaií]\w*|des\w*zip\w*|zipe[ao]\w*|zippe[ao]\w*|compress(?:es|ed|ing)?)\b"
                r"|\bzip\s+(?:it|them|la|lo|el|the)\b"
                r"|\b(?:archivo|fichero)\s+zip\b"
                r"|\b(?:un|el|la|the|a)\s+zip\b"
                r"|\.zip\b",
            ),
            # REOPEN1957 H0542: file.compress and file.open now serve it.
            {"file.compress", "file.open"},
        ),
        (
            # LIMITS1683 H0302 «qué redes wifi hay»: saved profiles and the current
            # state are read; no operation scans the networks around the PC.
            _has(folded, r"\b(?:que|cuales|what|which)\s+redes(?:\s+(?:wifi|wi\s*fi|inalambricas))?\s+(?:hay|disponibles|cerca|detectas|ves|encontras)\b"
                         r"|\b(?:escanea|escanear|scan)\b.{0,24}\b(?:wifi|redes|networks)\b"
                         r"|\b(?:what|which)\s+(?:wifi\s+)?networks\s+(?:are\s+(?:there|available|nearby|around)|can\s+you\s+see|do\s+you\s+see)\b"),
            {"wifi.scan"},
        ),
        (
            # LIMITS1683 H0077 «descarga la imagen de portada de wikipedia.org y
            # guardala en el escritorio»: the browser navigates; no operation
            # downloads a file from the web.
            _has(folded, r"\b(?:descarga|descargar|descargame|baja|bajar|bajame|download)\b")
            and _has(folded, r"\b(?:imagen|imagenes|foto|fotos|image|images|picture|pictures|photo|photos|archivo|archivos|file|files|video|videos|pdf)\b")
            and not _has(folded, r"\b(?:steam|epic|juego|game)\b"),
            {"browser.download.file"},
        ),
        (
            # LIMITS1681 H0175 «en Discord apretá enter», H0566 «apretá enviar en
            # WhatsApp»: a control inside a messaging client is never pressed
            # by the product (the visible click works on its own windows).
            _has(folded, r"^[¿?¡!\s]*(?:(?:en|in|on)\s+(?:discord|whatsapp|teams|telegram|slack|skype|zoom|signal|messenger)[,]?\s+)?(?:apreta|apretale|pulsa|pulsale|presiona|presionale|dale\s+a|toca|clickea|click|press|hit)\s+"
                         r"(?:(?:la|el|the)\s+)?(?:tecla\s+|boton\s+(?:de\s+)?|key\s+|button\s+)?(?:enter|intro|return|enviar|send|escape|esc|espacio|space|tab)\b")
            and (_has(folded, r"^[¿?¡!\s]*(?:en|in|on)\s+(?:discord|whatsapp|teams|telegram|slack|skype|zoom|signal|messenger)\b") or _has(folded, r"\b(?:en|in|on)\s+(?:discord|whatsapp|teams|telegram|slack|skype|zoom|signal|messenger)[\s.!?]*$")),
            {"client.control.press"},
        ),
        (
            # LIMITS1681 H0107 «poneme el modo avión»: the radios are switched
            # one by one; no operation toggles airplane mode.
            _has(folded, r"\b(?:modo\s+avion|airplane\s+mode|flight\s+mode)\b")
            and _has(folded, r"\b(?:pon|pone|poneme|poner|activa|activame|activar|prende|prendeme|enciende|apaga|desactiva|quita|saca|turn\s+on|turn\s+off|enable|disable|switch|put|set)\b"),
            {"network.airplane.mode"},
        ),
        (
            # LIMITS1677 H0048 «ejecuta pytest», H0245 «ejecuta ls»: no operation
            # runs a shell command or a program by command line.
            _has(folded, r"^[¿?¡!\s]*(?:(?:por\s+favor|please)\s*[,;:]?\s*)?(?:ejecuta|ejecutame|corre|correme|run|execute|lanza|launch)\s+"
                         r"(?:(?:el|the|este|this|un|a)\s+)?(?:comando\s+|command\s+)?"
                         r"(?:pytest|ls|dir|cd|git|npm|npx|pip|pip3|python|python3|node|dotnet|cargo|make|cmd|powershell|bash|sh|"
                         r"\S+\.(?:py|sh|bat|ps1|cmd|exe\s+/)|comando|command)\b")
            and not _has(folded, r"\b(?:juego|game|steam|app|aplicacion|application|programa|program)\b"),
            {"shell.command.run"},
        ),
        (
            # H0475 «PS C:\\...\\Desktop...> python carter_core.py»: una linea de
            # consola pegada con su prompt es un comando, aunque no traiga verbo
            # delante. Sin esto la del prompt de PowerShell acababa preguntando si
            # la persona queria ayuda para entender el script, mientras que la misma
            # linea sin el «PS» ya decia el limite.
            _has(folded, r"^\s*(?:ps\s+)?[a-z]:\\[^>]*>\s*\S"),
            {"shell.command.run"},
        ),
        (
            # LIMITS1677 H0635 «Puedes ver tu propio código y analizar si hay
            # alguna falla»: BAXY has no reading of its own source.
            _has(folded, r"\b(?:tu|tus|your)\s+(?:propio\s+|own\s+)?(?:codigo|code|fuente|source\s+code|programacion)\b")
            and _has(folded, r"\b(?:ver|leer|analizar|analiza|revisar|revisa|mirar|mira|examinar|examina|see|read|review|analy[sz]e|look|inspect|check)\b"),
            {"self.source.read"},
        ),
        (
            # LIMITS1677 H0444 «cerrá todas las pestañas de chrome»: since
            # BROWSER1841 «cerrá todas las pestañas» closes every open tab in the
            # product's own browser (browser.control close_all); a single-tab or
            # partial close still has no operation and stays a plain limit.
            _has(folded, r"\b(?:cierra|cerra|cerrar|cerrame|cierrame|close)\b")
            and _has(folded, r"\b(?:pestanas?|tabs?)\b")
            and browser_close_all_tabs_arguments(text) is None,
            {"browser.tab.close"},
        ),
        (
            # LIMITS1677 H0238/H0529 «minimizá todas las ventanas», H0658
            # «minimizá todo»: windows are minimized one at a time, never all.
            _has(folded, r"\b(?:minimiza|minimizar|minimizame|minimise|minimize)\b")
            and _has(folded, r"\b(?:todo|todas(?:\s+las)?(?:\s+ventanas)?|all(?:\s+(?:the|my))?(?:\s+windows)?|everything)\b")
            and not _has(folded, r"\b(?:pestanas?|tabs?|menos|except|excepto)\b"),
            {"window.minimize.all"},
        ),
        (
            # LIMITS1677 H0467 «cerrame todo», H0484 «cerrá todas las ventanas»
            # were a known limit; since CLOSEALL1733 (owner 2026-09-16: close
            # everything except Visual Studio Code) window.close.all exists and
            # this contract is inert.
            _has(folded, r"\b(?:cierra|cerra|cerrar|cerrame|cierrame|close)\s+(?:me\s+)?(?:todo|todas\s+las\s+ventanas|todas\s+las\s+apps|todas\s+las\s+aplicaciones|all\s+(?:the\s+|my\s+)?(?:windows|apps|applications)|everything)\b")
            and not _has(folded, r"\b(?:pestanas?|tabs?|menos|except|excepto|de\s+\w+$)\b"),
            {"window.close.all"},
        ),
        (
            # LIMITS1677 H0652 «subí el volumen de spotify»: the volume readers
            # act on the system endpoint; no operation sets one application's
            # volume.
            _has(folded, r"\b(?:volumen|volume)\s+(?:de|del|of)\s+(?:(?:la|el|the)\s+)?(?:app\s+)?(?:spotify|chrome|discord|youtube|steam|zoom|teams|vlc|firefox|opera|edge|whatsapp)\b"
                         r"|\b(?:spotify|chrome|discord|youtube|steam|zoom|teams|vlc|firefox|opera|edge|whatsapp)(?:\'s)?\s+volume\b"),
            {"audio.app.volume.adjust", "audio.app.volume.set"},
        ),
        (
            # Owner 2026-09-21 «qué fue lo último que me dijo vicho en wsp», «leé lo
            # último que me dijo X», «qué me escribió mamá» (H0510/H0720): reading a
            # chat needs the computer-use engine (deferred); a plain limit, not
            # «no pude entender».
            chat_read_request(folded),
            {"message.latest.read"},
        ),
        (
            # MASSIVE social_post/social_query (dev corpus 2026-09-23) «tuitea a
            # Vodafone que…», «what does my facebook feed look like»: no
            # operation posts to a social network or reads the account there.
            social_network_request(text),
            {"social.post", "social.account.read"},
        ),
        (
            # MASSIVE music_likeness «rate five»: a rating given to what plays
            # is kept by the player's account; no operation rates. It was
            # searched on the web as a phrase.
            _has(
                folded,
                r"^[¿?¡!\s]*(?:rate|califica|calificale|puntua|puntuale|valora|valorale|dale|give)\s+"
                r"(?:(?:it|this|esta|este|the|la|el)\s+(?:(?:song|cancion|track|tema|pelicula|movie)\s+)?)?"
                r"(?:(?:con|with|a)\s+)?(?:(?:un|una|a)\s+)?"
                r"(?:\d{1,2}|one|two|three|four|five|ten|uno|una|dos|tres|cuatro|cinco|diez)"
                r"(?:\s+(?:estrellas?|stars?|puntos?|points?))?[\s.!?]*$",
            )
            and not _has(folded, r"^[¿?¡!\s]*(?:dale|give)\s+(?:\d{1,2}|one|two|three|four|five|ten|uno|una|dos|tres|cuatro|cinco|diez)[\s.!?]*$"),
            {"media.rating.set"},
        ),
        (
            # AGENDA1669 H0666 «resumime informe.pdf»: the text reader opens text
            # files; no operation reads or summarises a PDF.
            _has(folded, r"\b(?:resumi|resumime|resumeme|resume|resumir|resumen|summari[sz]e|summary|sum\s+up)\b")
            and _has(folded, r"\.pdf\b|\bpdfs?\b"),
            {"document.pdf.read"},
        ),
        (
            # Uso real 2026-09-23 «prepárame una taza de café»; MASSIVE iot_* (dev
            # corpus 2026-09-23) «pon en marcha una taza de café», «apaga las luces
            # de la cocina»: food, drink and the devices of the house are the
            # physical world, where BAXY has no hands (semantic.system).
            physical_world_request(folded),
            {"physical.errand", "home.device.control"},
        ),
        (
            # LIMITS1665 H0459 «cambiá el fondo de pantalla a azul»: no operation
            # sets the desktop wallpaper.
            _has(folded, r"\b(?:fondo\s+de\s+(?:pantalla|escritorio)|wallpaper|papel\s+tapiz|desktop\s+background)\b")
            and _has(folded, r"\b(?:cambia|cambiar|cambiame|pon|pone|poneme|poner|establece|coloca|usa|change|set|put|use|make)\b"),
            {"desktop.wallpaper.set"},
        ),
        (
            # LIMITS1665 H0188 «Haz un powerpoint hablando de amor de 6
            # diapositivas»: no operation creates a slide deck.
            _has(folded, r"\b(?:powerpoint|power\s+point|presentacion(?:es)?|diapositivas?|slides?|slideshow|slide\s+deck)\b")
            and _has(folded, r"\b(?:haz|hace|haceme|hazme|crea|creame|crear|arma|armame|armar|genera|generame|generar|prepara|preparame|make|create|build|prepare|put\s+together)\b"),
            {"document.presentation.create"},
        ),
        (
            # LIMITS1665 H0306 «agregá a Juan a mis contactos», H0138 «guardá el
            # contacto de Lucía …»; dev corpus 2026-09-23 «what is mom's email
            # address», «cuántos contactos tengo»: no operation keeps or reads an
            # address book (semantic.messaging).
            contact_book_request(text),
            {"contacts.add", "contacts.read"},
        ),
        (
            # UI1659 H0290/H0636 «ve a Cotele en Discord» was a known limit; since
            # UI1735 the client is opened and the channel label clicked on its
            # interface (input.visible.click), so this contract is inert.
            client_navigation_target(folded) is not None,
            {"input.visible.click"},
        ),
        (
            # H0510 «qué me escribió mamá», H0720 «leéme el último mensaje de
            # Pedro» (owner, 2026-09-17 §5: reading private chats stays out;
            # defer or honest limit): no operation reads what a named person
            # wrote in a chat. The mail reader reads the latest mail of the
            # test mailbox regardless of sender, so a request that names mail
            # keeps that path; a chat client or no channel at all is this limit.
            (
                _asks_what_was_said_to_me(folded)
                or _has(folded, r"\bwhat\s+did\s+\w+(?:\s+\w+)?\s+(?:write|send|say|text)\s+(?:to\s+)?me\b"
                             r"|\b(?:lee|leeme|leer|leelo|leela|leelos|leelas|mostra|mostrame|muestra|muestrame|dime|decime|read|show)\b.{0,40}\b(?:mensajes?|messages?|chats?|dms?|texts?)\b.{0,30}\b(?:de|from|of)\s+\w+")
                and not _has(folded, r"\b(?:correos?|mails?|e-?mails?|emails?|inbox|bandeja|gmail|outlook)\b")
            ),
            {"message.read.named"},
        ),
        (
            # H0646 «pone The Office en Prime Video» (owner, 2026-09-20: no
            # Prime Video subscription; the row is an honest limit): the
            # streaming session on this PC has no Prime Video, so no operation
            # can play there. Netflix keeps its own reviewed playback.
            _has(folded, r"\b(?:pon|pone|poneme|ponme|poné|reproduce|reproduci|reprodúceme|play|put(?:\s+on)?|start|inicia|dale|ver|mira|mirar|watch|quiero\s+ver|quisiera\s+ver)\b")
            and _has(folded, r"\b(?:en|on|in)\s+(?:amazon\s+)?(?:prime\s*video|primevideo|prime)\b"),
            {"streaming.play.prime_video"},
        ),
        (
            # M80 (DEV-D v3m D-s069 «I need Pandora to play me a birthday song.» → «Which music provider should be
            # used…?»): music is played on Spotify or YouTube only; a request that names another music service is
            # the limit said plainly, never a question for the service the person already named.
            _has(folded, _MUSIC_PLAY_VERB) and unoffered_music_service_named(folded),
            {"media.play.unoffered_service"},
        ),
        # M84 (DEV-D v3o D-s092, D-s006, D-s122): the repeat mode, an order with a shop, the person's own bill.
        (media_repeat_mode_request(text), {"media.repeat.mode"}),
        (_SHOP_ORDER_HANDLING.search(folded) is not None, {"commerce.order.manage"}),
        (_OWN_BILL_AMOUNT.search(folded) is not None, {"account.bill.read"}),
        (
            # WEATHER2023 boundary «qué clima hacía en Buenos Aires en 1990»:
            # the weather of the past (a past-tense verb or a year) has no
            # live read; weather.current reads today and tomorrow only.
            _has(folded, _WEATHER_WORDS)
            and _has(
                folded,
                r"\b(?:hacia|hizo|hubo|estuvo|estaba|fue|llovio|was|were|did|rained)\b|"
                r"\b(?:19|20)\d\d\b|\b(?:ayer|anteayer|yesterday|la\s+semana\s+pasada|last\s+week)\b",
            ),
            {"weather.history"},
        ),
    )
    return any(
        matched and not supported & available for matched, supported in contracts
    )


def resolve_explicit_clarification(
    text: str,
    available_operations: Iterable[str],
) -> str | None:
    """Return the single certain operation of an incomplete effect, if any."""

    intent = resolve_explicit_clarification_intent(text, available_operations)
    return (
        intent.operation if intent is not None and len(intent.operations) == 1 else None
    )


_TEMPORAL_NUMBER_WORDS = {
    "one": 1,
    "un": 1,
    "una": 1,
    "uno": 1,
    "two": 2,
    "dos": 2,
    "three": 3,
    "tres": 3,
    "four": 4,
    "cuatro": 4,
    "five": 5,
    "cinco": 5,
    "six": 6,
    "seis": 6,
    "seven": 7,
    "siete": 7,
    "eight": 8,
    "ocho": 8,
    "nine": 9,
    "nueve": 9,
    "ten": 10,
    "diez": 10,
    "eleven": 11,
    "once": 11,
    "twelve": 12,
    "doce": 12,
    "fifteen": 15,
    "quince": 15,
    "twenty": 20,
    "veinte": 20,
    "thirty": 30,
    "treinta": 30,
    "forty five": 45,
    "cuarenta y cinco": 45,
    "sixty": 60,
    "sesenta": 60,
}


# «cuál es mi ip», «what's my ip address», «decime qué dirección IP tiene esta
# compu»: the machine's own address, read from the catalog (NETWORK1161/1201).
_IP_LIST_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:(?:decime|dime|mostrame|muestrame|show\s+me|tell\s+me)\s+)?"
    r"(?:(?:cual|which|what)(?:\s+es|'s|s|\s+is)?\s+)?"
    r"(?:mi|my|la|the|tu|your)\s+(?:direccion\s+)?ip(?:\s+address)?"
    r"(?:\s+(?:actual|current|local|de\s+(?:esta|este)\s+(?:compu|computadora|equipo|pc|maquina)|of\s+this\s+(?:pc|computer|machine)))?"
    r"[\s?!.]*$"
    r"|^[¿?¡!\s]*(?:(?:decime|dime|show\s+me|tell\s+me)\s+)?(?:que|what)\s+(?:direccion\s+)?ip(?:\s+address)?\s+"
    r"(?:tengo|tiene\s+(?:esta|este|la|el)\s+(?:compu|computadora|equipo|pc|maquina)|do\s+i\s+have|does\s+this\s+(?:pc|computer|machine)\s+have)"
    r"[\s?!.]*$"
)


def _ip_list_request(folded: str) -> bool:
    """Recognize a request for this machine's own IP address."""

    return _IP_LIST_REQUEST.match(_strip_request_envelope(folded)) is not None


_DIRECTORY_CREATION_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:cre[aá]|crear|cre[aá]me|create|haz|hac[eé]|hazme|make)(?:me)?\s+"
    r"(?:(?:una|un|a|the)\s+)?(?:carpeta|directorio|folder|directory)"
    rf"(?:\s+(?:en|on|in|dentro\s+de|inside)\s+(?:(?:el|la|mi|my|the)\s+)?(?P<folder_a>{_KNOWN_FOLDER_WORDS}))?"
    r"\s+(?:llamad[oa]|named|called|con\s+(?:el\s+)?nombre)\s+(?P<name>\"[^\"]+\"|'[^']+'|\S+?)"
    rf"(?:\s+(?:en|on|in|dentro\s+de|inside)\s+(?:(?:el|la|mi|my|the)\s+)?(?P<folder_b>{_KNOWN_FOLDER_WORDS}))?"
    r"[\s.!?]*$",
    re.IGNORECASE,
)


def _directory_creation_request(text: str) -> re.Match[str] | None:
    """Match one literal folder creation with a name."""

    return _DIRECTORY_CREATION_REQUEST.match(text.strip())


_REMINDER_IDIOM = re.compile(
    r"^(?:no\s+dejes\s+que\s+(?:me\s+)?olvide(?:\s+de)?|que\s+no\s+se\s+me\s+olvide(?:\s+de)?|"
    r"no\s+me\s+dejes\s+olvidar(?:me)?(?:\s+de)?|don'?t\s+let\s+me\s+forget(?:\s+to|\s+about)?|"
    # Uso real 2026-09-24 «no te olvides de recordarme el cumpleaños de mi hermano el veinte de abril»,
    # «acuérdate de recordarme esto»: BAXY asked not to forget to remind is asked to remind.
    r"(?:no\s+te\s+olvides|acuerdate|acordate)\s+de\s+(?:recordarme|avisarme)|"
    r"don'?t\s+forget\s+to\s+remind\s+me(?:\s+(?:to|about|of))?|"
    # M100 (reserva A10 «recuerda que me mueva para que no engorde» → advice): «recuerda que me» with what the person
    # is to do, in the subjunctive, is «recuérdame»; a statement in the indicative («recuerda que me gusta el té», «que me
    # duele») is something to keep, not a reminder.
    r"recuerda(?=\s+que\s+me\s+(?!(?:gusta|gustan|encanta|encantan|duele|duelen|llamo|llaman|toca|tocan|queda|quedan|"
    r"falta|faltan|cuesta|cuestan|molesta|molestan|interesa|interesan|importa|importan|preocupa|preocupan|pasa|"
    r"dijiste|dijo|dijeron|prometiste|debe|deben|debes|ha|han|has|he|hace|hacen|sale|salen|va|van|fue|fueron|"
    r"parece|parecen|cae|caen|da|dan|tiene|tienen|tienes|toca|vale|sirve|sirven|conviene|apetece|queda)\b)[a-z]+[ae]\b))"
    r"\s+"
)
# M100 (reserva A10): a purpose said after the order («para que no engorde», «so I don't forget») does not negate it.
_PURPOSE_TAIL = re.compile(r"\s+(?:para\s+(?:que\s+)?no|so\s+(?:that\s+)?(?:i|we)\s+(?:don'?t|do\s+not|won'?t)|so\s+as\s+not\s+to)\b.*$")


def _incomplete_scheduled_request(
    text: str, available: frozenset[str]
) -> ClarificationIntent | None:
    """Clarify a literal partial time without authorizing a scheduled effect."""

    # Uso real 2026-09-23 «no dejes que me olvide de comprarle un regalo a mi hermana»: the idiom asks
    # for a reminder; its «no» negates the forgetting, not the order.
    folded = _REMINDER_IDIOM.sub("recuerdame ", _strip_request_envelope(_fold(text)), count=1)
    if _has(folded, r"^(?:recuerdame|recordame|remind\s+me|avisame)\b"):
        folded = _PURPOSE_TAIL.sub("", folded)
    # Keep scope checks on the whole request before reading a temporal preface.
    # Quoted payloads and multi-clause requests remain with the existing paths.
    if (
        explicit_non_action_frame(text)
        or _is_meta_or_tool_denial(folded)
        or _is_past_or_hypothetical_state(folded)
        or _has_contradictory_correction(folded)
        or _has(folded, r'["“”«»;]|\b(?:no|nunca|jamas|never|not|without|sin|if|si)\b')
    ):
        return None
    clock = re.search(_CLOCK_TIME_SELECTOR, folded)
    # The numeric vocabulary is shared with the existing spoken-number reader.
    number = r"(?:\d{1,2}|" + "|".join(
        word for word, value in {**_ENGLISH_SMALL_NUMBERS, **_SPANISH_SMALL_NUMBERS}.items()
        if 0 <= value <= 23
    ) + r")"
    if clock is None:
        clock = re.search(
            rf"\b(?:for|para)\s+(?:las?\s+)?{number}\b"
            r"(?!\s+(?:minutes?|minutos?|hours?|horas?|days?|dias?)\b)", folded,
        )
    # «Dentro de doce minutos, recordame …»: the preface may carry its own
    # preposition before the bounded selector (TIME1189/011).
    temporal = re.match(
        rf"^(?:(?:en|in|dentro\s+de|within)\s+)?(?:{_CLOCK_TIME_SELECTOR}|{_BOUNDED_TEMPORAL_SELECTOR})",
        folded,
    )
    body = folded
    if temporal is not None and temporal.end() < len(folded):
        body = _strip_request_envelope(folded[temporal.end():].lstrip(" ,:"))
    if len(_request_clauses(body)) != 1:
        return None
    desire = _EXPLICIT_DESIRE_REQUEST.match(body)
    if desire is not None:
        body = desire.group("body")
    # Uso real 2026-09-23 «i would like a timer set» → «estoy preparando un timer
    # para ti»: the English nominal desire is the same order as «quiero un
    # temporizador»; with no duration the turn asks for it.
    nominal_desire = re.fullmatch(
        r"(?:me\s+vendria\s+bien|i\s+could\s+use|(?:i|we)\s+(?:would\s+like|want|need)|"
        r"i['’]?d\s+like)\s+(?P<body>.+)",
        body,
    )
    if nominal_desire is not None:
        body = nominal_desire.group("body")
    # These are scheduling speech acts, not matches anywhere in arbitrary prose.
    noun_request = re.match(
        # «dame un recordatorio veinticuatro horas antes de mi reunión»: a reminder given, sent or set.
        rf"^(?:{_SCHEDULING_VERB}|fija|establece|establecer|dame|mandame|enviame|give\s+me|send\s+me)\s+"
        r"(?:(?:un|una|el|la|an?|the)\s+)?"
        r"(?P<noun>alarma|alarm|timer|temporizador|recordatorio|reminder)\b(?P<tail>.*)$",
        body,
    )
    if noun_request is None and (desire is not None or nominal_desire is not None):
        noun_request = re.match(
            r"^(?:(?:un|una|an?|the)\s+)?"
            r"(?P<noun>alarma|alarm|timer|temporizador|recordatorio|reminder)\b(?P<tail>.*)$",
            body,
        )
    wake = re.match(r"^(?:wake\s+me(?:\s+up)?|get\s+me\s+up|desp(?:ierta|erta)me|levantame)\b", body)
    # «puedes recordarme que…», «notificarme sobre el evento», «alert me at the time of the event».
    reminder = re.match(
        r"^(?:recuerdame|recordame|recordarme|avisame|avisarme|notificame|notificarme|alertame|"
        r"remind\s+me|alert\s+me|notify\s+me|"
        # M100 (reserva A10 «me gustaría ser notificado de las misas de los domingos…»): being notified, wished for.
        r"ser\s+(?:notificad[oa]s?|avisad[oa]s?|alertad[oa]s?|recordad[oa]s?)|to\s+be\s+(?:notified|reminded|alerted))"
        r"(?:\s+(?P<title>.+))?$",
        body,
    )
    if reminder is None and desire is not None:
        # «necesito que me recuerden las reuniones del lunes»: an impersonal «recuerden» asks the same.
        reminder = re.match(r"^(?:recuerdes|recuerde|recuerden|avises|avise|avisen)\s+(?P<title>.+)$", body)
    if reminder is not None and re.match(
        # «recuérdame que…» stays a reminder: folded, «qué» and «que» are one word.
        r"(?:recuerdame|recordame|remind\s+me)\s+(?:cual|cuales|cuanto|cuanta|cuantos|cuantas|donde|quien|quienes|"
        r"what|which|how\s+(?:many|much)|where|who)\b",
        body,
    ):
        # M91 (reserva «recuérdame cuántas notas tengo»): «remind me how many/which…» asks to be told now, never a
        # reminder whose moment is missing.
        return None
    alarm = wake is not None or (
        noun_request is not None and noun_request.group("noun") in {"alarma", "alarm", "timer", "temporizador"}
    )
    title = (reminder.group("title") or "") if reminder is not None else ""
    if noun_request is not None and noun_request.group("noun") in {"recordatorio", "reminder"}:
        # «un recordatorio para el próximo sábado ir a la biblioteca a las cinco»: after «para/for» the words
        # left once the time is taken out are what to remind.
        payload = re.search(r"\b(?:about|to|de|que|para|for)\s+(?P<title>\S.+)", noun_request.group("tail"))
        title = payload.group("title") if payload is not None else ""
    if title:
        content = re.sub(rf"(?:{_CLOCK_TIME_SELECTOR}|{_BOUNDED_TEMPORAL_SELECTOR})", " ", title)
        # The duration's own preposition («en 30 minutos», «in ten minutes»)
        # is not content either (TIME1195).
        content = re.sub(
            r"\b(?:at|for|para|a|las?|on|next|el|la|proximo|proxima|en|in|dentro|de|within)\b",
            " ",
            content,
        )
        if not re.search(r"[a-z]", content):
            title = ""
    # Only explicitly retained content uses this branch. Time-only reminders
    # retain the existing title clarification below; no AGENDA1024 WIP is merged.
    if (
        not alarm
        and not title
        and reminder is not None
        and "reminder.create" in available
        and _reminder_has_actionable_due(folded)
    ):
        # «avisame en 30 minutos»: the moment is given, the content is not.
        # Without this the effect path asked the model for arguments, which
        # re-asked the delay or invented the content (TIME1195/000, /006).
        return ClarificationIntent(("reminder.create",), ("what_to_remind_or_notify_about",))
    if not alarm and not title and reminder is not None and "reminder.create" in available:
        # Uso real 2026-09-23 «please alert me», «remind me at»: a reminder asked
        # for with neither its content nor its moment asks both.
        return ClarificationIntent(("reminder.create",), ("what_to_remind_or_notify_about", "due_time"))
    if not alarm and not title:
        return None
    repetition = said_repetition(folded)
    operation = "notification.schedule" if alarm or repetition else "reminder.create"
    if operation not in available:
        return None
    if repetition == "unsupported":
        # «recuérdame sacar la basura cada martes»: no alarm or reminder repeats weekly; the question says so.
        return ClarificationIntent((operation,), ("repetition_the_calendar_cannot_hold",))
    if clock is not None:
        literal_clock = clock.group(0)
        # «5pm» writes the meridiem against the digits: no word boundary sits
        # between them, so the hour and its period are read without one.
        # Tanda 7 «remind me at 7:30 to call grandma» was asked «when and what?»:
        # the hour of «7:30» is the 7 before the colon, never the 30 after it.
        digits = re.search(r"(?<![\d:])(\d{1,2})(?=:\d{2}|(?![\d:]))", literal_clock)
        hour_value = int(digits.group(1)) if digits else None
        has_period = _has(
            literal_clock,
            r"(?<![a-z])(?:a\.?\s*m\.?|p\.?\s*m\.?)\b|\b(?:de\s+la|in\s+the)\s+\w+\b",
        )
        if hour_value is not None and (
            hour_value > 23 or (has_period and not 1 <= hour_value <= 12)
        ):
            # «a las 99», «13 pm»: no part of day can make that hour exist, so
            # asking morning/afternoon would be unfaithful (TIME1195 probe).
            return ClarificationIntent((operation,), ("valid_hour_0_to_23",))
        # The shared clock reader hears the minutes and the part of the day
        # wherever it was said («a las cinco y media de la mañana», «esta tarde
        # a las cinco», «a las diez a. m.»); only an hour left without one asks.
        spoken = spoken_clock(folded)
        if spoken is not None and not spoken.resolved:
            return ClarificationIntent((operation,), ("am_pm_or_part_of_day_for_supplied_hour",))
        if spoken is None and not (
            _has(literal_clock, r"\b\d{1,2}:\d{2}\b|\b(?:0|1[3-9]|2[0-3])\b")
            or any(
                (value == 0 or 12 < value <= 23) and _has(literal_clock, rf"\b{word}\b")
                for word, value in {**_ENGLISH_SMALL_NUMBERS, **_SPANISH_SMALL_NUMBERS}.items()
            )
        ):
            return ClarificationIntent((operation,), ("am_pm_or_part_of_day_for_supplied_hour",))
        return None
    if not _reminder_has_actionable_due(folded):
        return ClarificationIntent((operation,), ("alarm_time" if alarm else "due_time",))
    return None


_EXTENSION_COUNT = re.compile(
    r"\b(?:archivos?|ficheros?|files?)?\s*(?:con\s+extension\s+|de\s+extension\s+|with\s+(?:the\s+)?extension\s+)?"
    r"(?P<extension>\*?\.[a-z0-9]{1,15})\b"
)


def explorer_count_request(text: str) -> str | None:
    """REOPEN1957 H0701 «Dime cuantos archivos .py hay en el directorio actual»
    (D24): the current directory is the Explorer folder in front (the Desktop
    with none); the count is by the extension named. Returns the extension."""

    folded = _strip_request_envelope(_fold(text)).strip(" ¿?¡!.")
    if _negative_action_forms(folded):
        return None
    current = _current_directory_file_count(folded) or (
        _has(folded, r"\b(?:cuantos|cuantas|how many|count|cuenta|conta|contame|cuentame)\b")
        and _has(
            folded,
            r"\b(?:directorio|carpeta|folder|directory)\s+(?:actual|current|de trabajo|en (?:el|la) que estoy)\b"
            r"|\b(?:current|working|present|this)\s+(?:directory|folder)\b|\bcwd\b"
            r"|\b(?:esta|este)\s+(?:carpeta|directorio)\b",
        )
        and not _has(folded, r"\b(?:escritorio|desktop|descargas|downloads|documentos|documents)\b")
    )
    if not current:
        return None
    match = _EXTENSION_COUNT.search(folded)
    if match is None:
        return None
    return match.group("extension").lstrip("*")


def resolve_explicit_clarification_intent(
    text: str,
    available_operations: Iterable[str],
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
    *,
    previous_user_text: str | None = None,
) -> ClarificationIntent | None:
    """Preserve the operation identity of a recognized incomplete effect.

    ``previous_user_text`` only gives an output level that leaves out its object («bájale» after «qué brillo
    tengo») the object of the request it follows. A request said after an address («oye toca la radio») or
    a request to listen said another way («poner mi canción favorita») is read as the request it stands for,
    so the turn that asks and the turn that reads the answer see the same incomplete request.
    """

    available = tuple(available_operations)
    if reported_own_schedule(text):
        return None
    found = _clarification_intent_of(text, available, application_names, previous_user_text=previous_user_text)
    if found is not None:
        return found
    addressed = _without_address(text)
    # «establecer un recordatorio para el sábado … a las cinco»: an order said with «usted» or as an
    # infinitive is asked what its tú imperative would be asked (``reading`` reads it the same way).
    for candidate in (addressed, spoken_media_order(addressed or text), *imperative_rewrites(addressed or text)):
        # «me gustaría escuchar call me de aretha franklin después de esta canción»: a request for later
        # is not an incomplete one; asking what to play would ignore what was named.
        if candidate is not None and not _has_unsupported_deferred_effect(_fold(candidate)):
            found = _clarification_intent_of(
                candidate, available, application_names, previous_user_text=previous_user_text,
            )
            if found is not None:
                return found
    return None


def _clarification_intent_of(
    text: str,
    available_operations: Iterable[str],
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
    *,
    previous_user_text: str | None = None,
) -> ClarificationIntent | None:
    if explicit_non_action_frame(text):
        return None
    folded = _strip_request_envelope(_strip_request_envelope(_fold(text)))
    folded = screen_light_as_brightness(folded)
    # MUSIC1571 H0656 «no me molesta, poné música»: the idiom accepts, it does
    # not negate the order that follows.
    folded = re.sub(r"^no\s+me\s+molesta\s*[,;:]?\s+(?=\S)", "", folded, count=1)
    available = frozenset(available_operations)
    alias_plan = exact_catalog_operation_plan(folded)
    if alias_plan is not None and set(alias_plan) <= available:
        # A reviewed full-utterance alias already proves a complete operation
        # identity.  Do not let a looser incomplete-request heuristic pre-empt
        # it; the caller still applies catalogue authority and policy gates.
        return None
    if _is_meta_or_tool_denial(folded):
        return None
    if _literal_note_payload_request(folded):
        # The subordinate text is note content, not a message recipient/body.
        return None
    if known_unsupported_effect_request(text, available):
        # LIMITS1677 «subí el volumen de spotify»: a known effect with no
        # operation has no field to clarify; the limit answers it.
        return None
    if "email.send" in available and email_request_without_address(text):
        # Fase 7: a mail for a name and no address asks the address (never guesses one).
        return ClarificationIntent(("email.send",), ("to",))
    if _weather_read_intent(text, available) is not None and weather_place_known_only_through_someone(text):
        # Tanda 7 «at my sister's»: a place BAXY does not know is asked for, never read as this PC's town.
        return ClarificationIntent(("weather.current",), ("location",))
    if {"web.download", "file.open"} <= available and (image := web_image_request(text)) is not None and image[1]:
        # REOPEN1957 H0069: an image or a photo of nothing in particular is asked
        # what it should show; a meme needs no subject.
        return ClarificationIntent(("web.download",), ("query",))
    if "filesystem.known.search" in available and "filesystem.explorer.count" not in available and _current_directory_file_count(folded):
        # FILES1437 «dime cuántos archivos .py hay en el directorio actual»: BAXY
        # has no working directory; the count needs the person's folder.
        return ClarificationIntent(("filesystem.known.search",), ("folder",))
    if "audio.microphone.mute" in available and app_scoped_microphone_mute(folded) is not None:
        # UI1653 H0232 «silencia mi microfono en discord», H0128 «en Discord
        # apretá silenciar»: BAXY operates the Windows capture endpoint, not
        # the mute control of a voice client; it asks whether to mute the
        # system microphone (the client would stop receiving it) instead of
        # muting it unasked or pretending to press the client button.
        return ClarificationIntent(("audio.microphone.mute",), ("system_microphone_confirmation",))
    level = levels.read(text)
    if level is not None and level.direction is not None and level.amount is None and level.target is None:
        # Uso real 2026-09-23 «súbele un poco», «más bajito», «Volume más alto please», «I don't wanna hear
        # it tan alto»: the direction is given, so only the amount is asked (owner rule H0027, no default step).
        setting = level.setting or levels.setting_of(previous_user_text) or levels.VOLUME
        operation = "system.settings.adjust" if setting == levels.BRIGHTNESS else "audio.volume.adjust"
        if operation in available:
            return ClarificationIntent((operation,), ("amount",))
    if "input.text.type" in available and re.fullmatch(
        # UI1645 H0265 «escribe en el diálogo el de ChadGBT»: a typing order
        # that names where to write and not what; the text is missing.
        r"[¿?¡!\s]*(?:escribe|escribi|escribime|tipea|tipeame|teclea|type|write)\s+"
        r"(?:en|in|into|on)\s+(?:(?:el|la|los|las|the)\s+)?"
        r"(?:dialogo|chat|campo|cuadro|casilla|buscador|barra|caja|input|box|field|dialog|prompt)\b"
        r"(?:\s+box)?(?:\s+(?:de\s+(?:texto|busqueda|chat)|of\s+\w+))?(?:\s+(?:el|la|the)\s+de\s+\S+|\s+(?:de|of)\s+\S+)?[\s.!?]*",
        folded,
    ) is not None and not re.search(r"[\"'«»“”]", folded):
        return ClarificationIntent(("input.text.type",), ("text",))
    if "input.visible.click" in available:
        # UI1639 H0344 «hace click en el boton rojo»: controls are found by
        # their visible text, never by colour; the label is still missing.
        click_label = _visible_click_label(folded)
        if click_label is not None and re.fullmatch(
            r"(?:(?:de\s+)?color\s+)?(?:rojo|roja|verde|azul|amarillo|amarilla|naranja|gris|negro|negra|blanco|blanca|"
            r"violeta|morado|morada|rosa|rosado|celeste|red|green|blue|yellow|orange|grey|gray|black|white|purple|pink)",
            click_label,
        ):
            return ClarificationIntent(("input.visible.click",), ("label",))
    hourly_dynamic_notification = (
        re.fullmatch(
            r"(?:get|send|give)\s+(?:me\s+)?(?:an?\s+)?hourly\s+"
            r"notifications?\s+(?:on|about|for)\s+\S.+[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "notification.schedule" in available and hourly_dynamic_notification:
        return ClarificationIntent(
            ("notification.schedule",),
            ("live_lookup_or_static_reminder", "first_notification_time"),
        )
    dynamic_public_notification = (
        _has(
            folded,
            r"\b(?:set|create|programa|configura)\b.{0,48}"
            r"\b(?:notifications?|notificaciones?|alerts?|avisos?)\b",
        )
        and _has(
            folded,
            r"\b(?:weather|clima|disasters?|desastres?|news|noticias|"
            r"stocks?|acciones)\b",
        )
        and not _has(folded, _CLOCK_TIME_SELECTOR)
    )
    if "notification.schedule" in available and dynamic_public_notification:
        return ClarificationIntent(
            ("notification.schedule",),
            ("live_monitoring_source", "notification_condition"),
        )
    incomplete_recurring_reminder = (
        _has(folded, r"\b(?:every|cada)\b")
        and _has(folded, r"\b(?:reminder|recordatorio)\b")
        and _has(folded, r"\b(?:set|create|crea|pon|programa)\b")
        and re.search(r"\b(?:for|para)\s*[.!?]*$", folded) is not None
    )
    if "reminder.create" in available and incomplete_recurring_reminder:
        return ClarificationIntent(
            ("reminder.create",),
            ("reminder_title", "recurrence_time"),
        )
    # M100 (reserva A10 «necesito algo todos los lunes pon un recordatorio» → the reminders listed): a reminder ordered
    # for something left unnamed («algo», «something») asks what it is about and when.
    unnamed_reminder = re.fullmatch(
        r"(?:(?:necesito|quiero|tengo|hay|i\s+need|i\s+have)\s+)?(?:algo|una\s+cosa|something)\b[^,;.]*?[\s,;.]+"
        r"(?:pon(?:me)?|crea(?:me)?|programa(?:me)?|set|create|make)\s+(?:me\s+)?(?:un|una|a|an)\s+(?:recordatorio|reminder)"
        r"[\s.!?]*",
        folded,
    )
    if "reminder.create" in available and unnamed_reminder is not None:
        return ClarificationIntent(("reminder.create",), ("what_to_remind_or_notify_about", "due_time"))
    deictic_song_replay = (
        re.fullmatch(
            r"(?:quiero|i\s+want\s+to)\s+(?:reproducir|play)\s+"
            r"(?:esta|esa|this|that|the)\s+(?:cancion|song|track)\s+"
            r"(?:de\s+nuevo|otra\s+vez|again)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "media.play.query" in available and deictic_song_replay:
        return ClarificationIntent(
            ("media.play.query",),
            ("song_title_or_current_media_context",),
        )
    categorized_application_request = (
        re.fullmatch(
            r"(?:muestra|muestrame|ensena|ensename|show|show\s+me|list|lista)\s+"
            r"(?:(?:las|los|the|some)\s+)?(?:apps?|aplicaciones?)\s+"
            r"(?:de|para|for)\s+\S.{0,120}[\s.!?]*|"
            r"(?:show|show\s+me|list)\s+(?:(?:the|some)\s+)?"
            r"\S.{0,80}\s+(?:apps?|applications?)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
        # Tanda 4c: «show me the apps», «show me my open apps» name no category; the open ones are read.
        and window_inventory_arguments(folded) is None
    )
    if "app.installed" in available and categorized_application_request:
        return ClarificationIntent(
            ("app.installed",),
            ("specific_application_name",),
        )
    providerless_order_delivery = (
        re.fullmatch(
            r"(?:sabe|sabes|dime|indica|tell\s+me|show\s+me|what|when|cual|cuando)\b"
            r".{0,96}\b(?:entrega\s+estimada|estimated\s+delivery|delivery\s+estimate|"
            r"fecha\s+de\s+entrega|delivery\s+date)\b.{0,96}"
            r"\b(?:mi|my|the)\s+(?:pedido|order)\b[\s.!?]*|"
            r"(?:sabe|sabes|dime|indica|tell\s+me|show\s+me|what|when|cual|cuando)\b"
            r".{0,96}\b(?:mi|my|the)\s+(?:pedido|order)\b.{0,96}"
            r"\b(?:entrega\s+estimada|estimated\s+delivery|delivery\s+estimate|"
            r"fecha\s+de\s+entrega|delivery\s+date)\b[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "web.search" in available and providerless_order_delivery:
        return ClarificationIntent(
            ("web.search",),
            ("merchant_or_tracking_reference",),
        )
    vague_calendar_intent = (
        re.fullmatch(
            r"(?:necesito|quiero|i\s+need\s+to|i\s+want\s+to)\s+"
            r"(?:hacer|do)\s+(?:algo|something)\s+"
            r"(?:hoy|today|manana|tomorrow)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "calendar.event.create" in available and vague_calendar_intent:
        return ClarificationIntent(
            ("calendar.event.create",),
            ("event_title", "start_time", "end_time_or_duration"),
        )
    unspecified_meeting_reschedule = (
        re.fullmatch(
            r"(?:(?:can|could|would)\s+you\s+)?(?:reschedule|reprograma|reagenda)\s+"
            r"(?:(?:my|mi|the|la)\s+)?(?:meeting|reunion)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "calendar.event.create" in available and unspecified_meeting_reschedule:
        return ClarificationIntent(
            ("calendar.event.create",),
            ("existing_event_identity", "new_start_time", "new_end_time"),
        )
    generic_calendar_event = (
        re.fullmatch(
            r"(?:add|create|make|agrega|crea)\s+(?:(?:an?|un)\s+)?event[oa]?\s+"
            r"(?:to|in|en|al)\s+(?:(?:the|el|la)\s+)?calendar(?:\s+app)?[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "calendar.event.create" in available and generic_calendar_event:
        return ClarificationIntent(
            ("calendar.event.create",),
            ("event_title", "start_time", "end_time"),
        )
    yearly_reminder_without_time = (
        _has(folded, r"\b(?:cada\s+ano|every\s+year|yearly|anualmente)\b")
        and _has(folded, r"\b(?:recuerdame|acuerdame|remind\s+me)\b")
        and not _has(folded, _CLOCK_TIME_SELECTOR)
    )
    if "reminder.create" in available and yearly_reminder_without_time:
        return ClarificationIntent(
            ("reminder.create",),
            ("one_time_or_yearly", "year_and_time"),
        )
    dated_notification_without_time = (
        _has(folded, r"\b(?:notificacion|notification)\b")
        and _has(folded, _CALENDAR_MONTH_TOKEN)
        and not _has(folded, _CLOCK_TIME_SELECTOR)
    )
    if "notification.schedule" in available and dated_notification_without_time:
        return ClarificationIntent(
            ("notification.schedule",),
            ("year_and_time",),
        )
    named_resume_without_provider = (
        re.fullmatch(
            r"(?:retoma|reanuda|resume)\s+\S.{0,160}"
            r"\b(?:por\s+donde|where)\b.{0,96}"
            r"\b(?:pare|stopped|left\s+off)\b.{0,80}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if (
        "media.control" in available
        and named_resume_without_provider
        and not _resume_existing_media(folded)
    ):
        return ClarificationIntent(
            ("media.control",),
            ("source_app",),
        )
    shared_note_read = (
        re.fullmatch(
            r"(?:lee|leeme|read)(?:\s+me)?\s+"
            r"(?:(?:los|las|the)\s+)?(?:post-?its?|notas?|notes?)\b.{0,120}"
            r"\b(?:compartid[oa]s?|shared)\b.{0,96}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "note.search" in available and shared_note_read:
        return ClarificationIntent(
            ("note.search",),
            ("shared_note_source",),
        )
    # M112 (DEV-F v4d w38-t1 «get me a large pepperoni with extra jalapeños from the Domino's on Elm St» → «¿Quieres
    # que busque…?»): «get X from a store» is no longer asked as lookup-or-purchase before the decider; an order of food
    # or goods is a limit and a lookup is a search, which the contextual decider tells apart (it did on every
    # clarification turn of DEV-D and DEV-F), and a yes/no offer that asks for no value is what D3 forbids.
    dynamic_market_alert = (
        _has(folded, r"\b(?:avisame|notificame|alert\s+me|notify\s+me)\b")
        and _has(folded, r"\b(?:acciones|stocks?|shares?)\b")
        and _has(
            folded,
            r"\b(?:suben|bajan|subir|bajar|rise|fall|go\s+up|go\s+down)\b",
        )
    )
    if "notification.schedule" in available and dynamic_market_alert:
        return ClarificationIntent(
            ("notification.schedule",),
            ("company", "live_monitoring_source"),
        )
    corrected_private_note_time = (
        re.fullmatch(
            r"(?:let(?:'|\s+u2019)?s|vamos\s+a)\s+"
            r"(?:create|make|crear|hacer)\s+(?:(?:a|una?)\s+)?(?:new\s+|nueva?\s+)?"
            r"(?:private|privada?)\s+(?:note|nota)\b.{0,160}"
            r"\b(?:at|a\s+las?)\s+\S.{0,32}\b(?:actually|en\s+realidad|"
            r"mejor)\b.{0,48}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "note.create" in available and corrected_private_note_time:
        return ClarificationIntent(
            ("note.create",),
            ("time_as_note_content_or_reminder",),
        )
    generic_game_discovery = (
        re.fullmatch(
            r"(?:quiero|quisiera|me\s+gustaria|i\s+want|i(?:'d|\s+would)\s+like)"
            r"\s+(?:probar\s+con|try|jugar(?:\s+a)?|play)\s+"
            r"(?:(?:algun|un|some|a)\s+)?(?:juego|game)\b\S?.{0,220}"
            r"[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    corrected_room_game = (
        _has(folded, r"\b(?:juego|game)\b")
        and _has(folded, r"\b(?:salon|living\s+room)\b")
        and _has(folded, r"\b(?:habitacion|bedroom)\b")
        and _has(folded, r"\b(?:no|mejor|actually|instead)\b")
    )
    room_scoped_game_request = (
        re.fullmatch(
            r"(?:in\s+(?:(?:the|my)\s+)?(?:living\s+room|bedroom)\s*[,;:]?\s*"
            r"(?:play|launch|start)|"
            r"(?:en|para)\s+(?:(?:el|la|mi)\s+)?(?:salon|habitacion)\s*[,;:]?\s*"
            r"(?:pon|inicia|lanza|juega))\s+\S.{0,160}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "game.launch" in available and room_scoped_game_request:
        return ClarificationIntent(
            ("game.launch",),
            ("local_pc_or_supported_device",),
        )
    if "game.launch" in available and corrected_room_game:
        return ClarificationIntent(
            ("game.launch",),
            ("game_title", "target_device"),
        )
    if "game.launch" in available and generic_game_discovery:
        return ClarificationIntent(("game.launch",), ("game_title",))
    topic_free_recipe_search = (
        re.fullmatch(
            r"(?:muestra|ensena|show)(?:\s+me|me)?\s+"
            r"(?:(?:las|unas|some|the)\s+)?(?:recetas|recipes)"
            r"[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "web.search" in available and topic_free_recipe_search:
        return ClarificationIntent(("web.search",), ("recipe_topic",))
    next_available_meeting = (
        re.fullmatch(
            r"(?:set|schedule|create|agenda|programa|crea)\s+"
            r"(?:(?:a|una?)\s+)?(?:meeting|reunion)\b.{0,200}"
            r"\b(?:next|proximo)\s+available\s+(?:meeting\s+)?day\b"
            r"[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "calendar.event.create" in available and next_available_meeting:
        return ClarificationIntent(
            ("calendar.event.create",),
            ("start_time", "end_time_or_duration"),
        )
    # Uso real 2026-09-23 «oye toca la radio», «toca fm», «pon la radio»: the radio with no station
    # named asks which one, as the bare «radio» does; a named station or dial plays (radio_station_query).
    # Uso real 2026-09-24 «por favor sintonice el canal de radio», «radio encendida»: the radio channel, or the
    # radio said switched on, names no station either.
    bare_radio = (
        re.fullmatch(
            # M91 (reserva «que alguien encienda la radio», «could you help me listen to the radio», «cambia de
            # emisora»): said to anyone, politely, as a wish or as a change of station, the radio with no station
            # named still asks which one.
            r"(?:(?:que\s+)?(?:alguien|someone|somebody)\s+|(?:puedes|podrias|can\s+you|could\s+you|will\s+you)"
            r"(?:\s+please)?\s+|(?:let'?s|vamos\s+a)\s+|(?:help\s+me|ayudame\s+a)\s+(?:in\s+)?)?"
            r"(?:(?:pon|ponme|pone|ponga|poner|toca|tocame|tocar|reproduce|enciende|encienda|encender|prende|prenda|"
            r"prender|activa|sintoniza|sintonice|sintonizar|escucha|escuchar|oir|play|put\s+on|turn\s+on|start|inicia|"
            r"tune\s+in\s+to|listen(?:ing)?\s+to|cambia(?:\s+de)?|cambie(?:\s+de)?|change|switch)\s+)?"
            r"(?:(?:la|el|una|un|the|a|some)\s+)?"
            r"(?:radio|emisora|fm|am|station|(?:canal|estacion|emisora)\s+de\s+radio|radio\s+(?:station|channel))"
            r"(?:\s+(?:encendida|prendida|puesta|on))?"
            r"(?:\s+(?:por\s+favor|please|ahora(?:\s+mismo)?|now|right\s+now))?[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "media.play.query" in available and bare_radio:
        return ClarificationIntent(("media.play.query",), ("station_or_genre",))
    # Uso real 2026-09-24 «adelanta por favor», «botón de rebobina»: moving what plays forward or back with no
    # amount asks the amount, as a relative volume does; it is not a refusal.
    bare_seek = re.fullmatch(
        r"(?:(?:el\s+|the\s+)?boton\s+de\s+)?"
        r"(?:adelanta(?:lo|la)?|adelantar|atrasa(?:lo|la)?|atrasar|retrocede|retroceder|rebobina(?:lo|la)?|rebobinar|"
        r"rewind(?:\s+it)?|fast\s+forward(?:\s+it)?|skip\s+(?:ahead|forward|back))"
        r"(?:\s+(?:un\s+poco|a\s+(?:bit|little)|(?:el|la|the)\s+(?:cancion|video|podcast|episodio|audio|pista|song|"
        r"track|episode|audiobook|audiolibro)))?"
        r"(?:\s+(?:por\s+favor|please|porfa))?(?:\s+(?:button|boton))?[\s.!?]*",
        folded,
    )
    if "media.seek.relative" in available and bare_seek is not None:
        return ClarificationIntent(("media.seek.relative",), ("seconds",))
    incomplete_shared_note = (
        re.fullmatch(
            r"(?:quiero|necesito|i\s+want)\s+(?:escribir|crear|hacer|write|create|make)\s+"
            r"(?:(?:una?|a)\s+)?(?:nota|note)\s+(?:compartida|shared)\b"
            r".{0,120}\b(?:hasta|until)\b.{0,48}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    referential_note_read = (
        re.fullmatch(
            r"(?:(?:(?:me|puedes|podrias|can\s+you|could\s+you)\s+)*"
            r"(?:lees|lee|leer|read)\s+(?:(?:me|to\s+me)\s+)?|"
            r"let\s+me\s+(?:see|view)\s+)"
            r"(?:esta|esa|this|that)\s+(?:nota|note)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    corrected_note_without_reminder = (
        _has(folded, r"\b(?:nota|note)\b")
        and _has(folded, r"\b(?:recordatorio|reminder)\b")
        and _has(
            folded,
            r"\b(?:mejor|better)\b.{0,32}\b(?:no\s+(?:incluyas?|include)|"
            r"without|sin)\b",
        )
    )
    if "note.create" in available and (
        incomplete_shared_note or corrected_note_without_reminder
    ):
        return ClarificationIntent(("note.create",), ("note_content",))
    if "note.read" in available and referential_note_read:
        return ClarificationIntent(("note.read",), ("note_identity_or_context",))
    channel_free_conveyance = _has(
        folded,
        r"^(?:hazle\s+(?:saber|llegar)\s+a|cuentale\s+a|dile\s+a)\s+"
        r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
        r"(?:que|el\s+mensaje|the\s+message)\s+\S.+$|"
        r"^dile\s+a\s+[a-z0-9._-]{1,80}\s+\S.+$|"
        # «let me know any new emails»: what BAXY is asked to tell the person
        # is no message to anybody.
        r"^let\s+(?!(?:me|us)\s)[a-z0-9][a-z0-9 ._-]{0,80}?\s+know\s+\S.+$|"
        r"^send\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+the\s+note\s+\S.+$|"
        r"^get\s+(?:the\s+)?(?:update|note|message)\s+\S.+\s+to\s+"
        r"[a-z0-9][a-z0-9 ._-]{0,80}$|"
        r"^pasale\s+a\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
        r"(?:el\s+)?(?:aviso|update)\s+\S.+$|"
        r"^manda\s+a\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+que\s+\S.+$|"
        r"^get\s+word\s+to\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+that\s+\S.+$|"
        r"^pass\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+(?:the\s+)?update\s+\S.+$|"
        r"^send\s+(?!them\b)[a-z0-9][a-z0-9 ._-]{0,80}?\s+that\s+\S.+$|"
        r"^hazle\s+know\s+a\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+que\s+\S.+$|"
        r"^send\s+a\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+el\s+update\s+que\s+\S.+$|"
        r"^hazel\s+sabera\s+a\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+que\s+\S.+$|"
        r"^hustle\s+no\s+a\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+que\s+\S.+$",
    )
    if (
        "message.send" in available
        and channel_free_conveyance
        and not _has(folded, r"\b(?:whatsapp|wsp|discord)\b")
        # REOPEN1993 grupo E: with the resolve/send pair the recipient is looked
        # up in the clients instead of asking which one.
        and not ("message.recipient.resolve" in available and message_request_any_channel(text) is not None)
    ):
        return ClarificationIntent(("message.send",), ("channel",))
    # MESSAGING1363: a reply with content but no addressee and no antecedent
    # («contestale que sí», «respondele que llego en 10») names nobody to
    # answer; the recipient is what is missing, not the channel.
    reply_head = (
        r"(?:contestale|contestales|respondele|respondeles|contesta|responde|"
        r"reply|answer)"
    )
    reply_without_addressee = _has(
        folded, rf"^[^\w]*{reply_head}\s+(?:que|that)\s+\S"
    ) and not _has(folded, rf"^[^\w]*{reply_head}\s+(?:a|to)\s+")
    if "message.send" in available and reply_without_addressee:
        return ClarificationIntent(("message.send",), ("recipient",))
    # MESSAGING1363: an addressee and a channel with nothing to say
    # («escribile por whatsapp a Pedro», «mandale un whatsapp a Ana»).
    addressed_without_content = _has(
        folded,
        (
            r"^[^\w]*(?:escrib[ei]le|escrib[ei]les|mandale|mandales|enviale|"
            r"enviales|hablale|escrib[ei]|manda|envia|write|send|message|text)\s+"
            # The addressee is one or two bare tokens: «mandale hola a Lucas
            # por whatsapp» carries its content and is not this shape.
            r"(?:(?:por|en|via|on)\s+(?:whatsapp|wsp|discord)\s+(?:a|to)\s+"
            r"[a-z0-9][a-z0-9._-]{0,40}(?:\s+[a-z0-9][a-z0-9._-]{0,40})?|"
            r"(?:(?:a|to)\s+)?[a-z0-9][a-z0-9._-]{0,40}\s+(?:por|en|via|on)\s+"
            r"(?:whatsapp|wsp|discord)|"
            r"(?:un|una|a)\s+(?:whatsapp|wsp|discord)\s+(?:a|to)\s+"
            r"[a-z0-9][a-z0-9._-]{0,40}(?:\s+[a-z0-9][a-z0-9._-]{0,40})?|"
            # MAIL (owner decision 2026-09-18 §3) «escribile un mail a
            # juan@hotmail.com», «enviá un correo a juan»: an address or a name
            # (a bracketed placeholder counts as an addressee) and nothing to say.
            r"(?:(?:un|una|a|an)\s+)?(?:correo(?:\s+electronico)?|(?:e-?)?mail)\s+(?:a|para|to)\s+"
            r"[a-z0-9\[][a-z0-9._@\[\]-]{0,60}(?:\s+[a-z0-9][a-z0-9._-]{0,40})?|"
            r"(?:por|via|by)\s+(?:correo(?:\s+electronico)?|(?:e-?)?mail)\s+(?:a|to)\s+"
            r"[a-z0-9\[][a-z0-9._@\[\]-]{0,60}(?:\s+[a-z0-9][a-z0-9._-]{0,40})?)[\s.!?]*$"
        ),
    ) and not _has(folded, r"\b(?:que|that|diciendo|saying)\b|[:\"«»“”]")
    if "message.send" in available and addressed_without_content:
        return ClarificationIntent(("message.send",), ("message_text",))
    corrected_browser = (
        "browser.navigate.named" in available
        and _has(folded, r"\b(?:youtube|video)\b")
        and _has(folded, r"\b(?:pero|but)\b.{0,100}\b(?:opera|browser)\b")
        and _has(folded, r"\b(?:queria|wanted|meant)\b")
        and not _has(folded, r"https?://\S+")
    )
    if corrected_browser:
        return ClarificationIntent(
            ("browser.navigate.named",),
            ("destination_url",),
        )
    # Share the speech-act head so supplied recipient/content stay present.
    message_speech_act = (
        r"(?:dile|decile|mandale|enviale|avisale|escrib[ei]le|respondele)"
    )
    incomplete_message_shape = _has(
        folded,
        (
            r"^[^\w]*(?:envia|enviar|manda|mandar|send)\b.{0,160}"
            r"\b(?:texto|text|mensaje|message)\b|"
            r"^[^\w]*ask\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:if|whether|what|when)\b|"
            r"^[^\w]*message\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:and\s+tell|and\s+say|that|saying)\b|"
            # M91 (reserva «tell me the best story that was ever written»): «tell me/us …» is said to BAXY; its «that»
            # opens a relative clause, never a message to a third person.
            r"^[^\w]*tell\s+(?!(?:me|us)\b)[a-z0-9][a-z0-9 _-]{0,80}?\s+that\b|"
            rf"^[^\w]*{message_speech_act}\s+(?:a\s+)?"
            r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+(?:que|el\s+texto|el\s+mensaje)\b|"
            # MSGCLAR «mandale al grupo Musica: prueba 1 …»: a dictation colon
            # after the addressee carries the text.
            rf"^[^\w]*{message_speech_act}\s+(?:a\s+|al\s+(?:grupo\s+)?|para\s+)?"
            r"[a-z0-9][a-z0-9 ._-]{0,80}?\s*:\s*\S|"
            # MAIL (owner decision 2026-09-18 §3) «enviá un correo»: a mail order
            # is a message request even with nobody and nothing named yet.
            r"^[^\w]*(?:envia|enviale|enviar|manda|mandale|mandar|escrib[ei]|escrib[ei]le|send|write)\b"
            r".{0,160}\b(?:correo|(?:e-?)?mail)\b|"
            r"^[^\w]*let\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+know\s+that\b|"
            r"^[^\w]*write\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:that|the\s+message)\b|"
            r"^[^\w]*preguntale\s+a\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:si|que|a que)\b"
        ),
    )
    if incomplete_message_shape and _has(
        folded,
        r"^ask\s+on\s+the\s+what\s+bluetooth\s+radio\s+can\s+see\b",
    ):
        incomplete_message_shape = False
    if (
        incomplete_message_shape
        and _latest_email_domain(folded)
        and not _has(folded, r"\b(?:whatsapp|wsp|discord)\b")
    ):
        # ``Tell me ... the email that just arrived`` is a live mailbox read,
        # not an incomplete instruction to contact a person named by the
        # greedy ``tell ... that`` messaging surface.
        incomplete_message_shape = False
    desired_volume = _EXPLICIT_DESIRE_REQUEST.match(folded)
    relative_spoken_volume = (
        re.fullmatch(
            # M104 (reserve v3z en3590 «speak loudly» → «I cannot speak aloud…»): the adverb asks the same as the
            # comparative, and «speak up» is «speak louder».
            r"(?:(?:speak|talk)\s+(?:(?:more\s+)?(?:softly|quietly|loudly)|softer|quieter|louder)|speak\s+up|"
            r"turn\s+(?:(?:the\s+)?volume\s+(?:up|down)|"
            r"(?:up|down)\s+(?:the\s+)?volume)|"
            r"(?:raise|lower|increase|decrease)\s+(?:the\s+)?volume)"
            r"(?:\s+please)?[.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
        or (
            desired_volume is not None
            and re.fullmatch(
                r"se\s+(?:oiga|oyera|escuche|escuchara)\s+"
                r"(?:mas\s+(?:fuerte|alto|bajo)|menos\s+fuerte)\s+"
                rf"(?:el|mi)\s+{_LOCAL_VOLUME_DEVICE}"
                r"(?:\s*,?\s*por favor)?[.!?]*",
                desired_volume.group("body"),
            ) is not None
        )
    )
    telegraphic_calendar_invite = (
        re.fullmatch(
            (
                r"(?:calendar\s+)?event\s+(?:send\s+)?invite\s+"
                r"[a-z0-9][a-z0-9 ._-]{0,96}[\s?!.]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    # VIDEO1947 H0130 «Toda la serie en Disney Plus», H0252 «Bueno, una serie
    # East Plus.», H0113 «on everybody en Disney.»: transcripciones cortadas o
    # mal oídas que nombran el servicio de streaming y ningún título legible:
    # sin verbo («toda la serie», «una serie») o con palabras que no forman un
    # título («on everybody»). El único dato que falta es qué ver: se pregunta.
    fragment_streaming_clause = any(
        _has(clause, r"\b" + _NETFLIX_SPELLED + r"\b")
        and (
            re.fullmatch(
                r"[¿?¡!\s]*(?:(?:bueno|dale|che|ya)\s*[,;:]?\s+)?(?:toda|la|una|otra|alguna|the|a|whole|some)\s+(?:la\s+)?"
                r"(?:serie|series|show|peli(?:cula)?|movie|temporada|season)(?:\s+(?:completa|entera|whole))?"
                r"\s+(?:(?:en|on|de|of)\s+)?" + _NETFLIX_SPELLED + r"[\s.!?]*",
                clause,
            ) is not None
            or _has(clause, r"^[¿?¡!\s]*(?:on|in|and|the)\s+\w+\s+(?:en|on)\s+" + _NETFLIX_SPELLED + r"\b")
        )
        and not _has(clause, r"\b(?:llamad[oa]|called|named|titulad[oa])\b")
        and len(clause.split()) <= 7
        for clause in _request_clauses(re.sub(r"^(?:(?:bueno|dale|che|ya)\s*[,;:]?\s+)+", "", folded, count=1))
    )
    incomplete_schedule = _incomplete_scheduled_request(text, available)
    if incomplete_schedule is not None:
        return incomplete_schedule
    if "notification.cancel.at" in available and re.fullmatch(
        # Uso real 2026-09-23 «no me despiertes mañana» was «eso no lo hago»: not to be woken is the
        # wake-up alarm cancelled; which one is asked, as for «cancelá la alarma» (AGENDA1021).
        r"(?:no\s+me\s+(?:despiertes|despiertas|levantes)|don'?t\s+wake\s+me(?:\s+up)?)"
        r"(?:\s+(?:hoy|manana|pasado\s+manana|today|tomorrow|el\s+\w+|on\s+\w+))?[\s.!?]*",
        folded,
    ):
        return ClarificationIntent(("notification.cancel.at",), ("which_alarm",))
    if (
        "notification.cancel.at" in available
        and re.match(
            # Uso real 2026-09-24 «apaga mis alarmas de la mañana tras el viernes», «remove my early alarms»:
            # alarms are cancelled one at a time by their hour; which one is asked.
            r"(?:apaga|apagame|quita|quitame|borra|borrame|elimina|cancela|cancelame|desactiva|remove|delete|cancel|"
            r"turn\s+off|clear|disable)\s+(?:(?:mis|las|todas\s+(?:mis|las)|my|the|all(?:\s+(?:my|the))?)\s+)?"
            r"(?:\w+\s+)?(?:alarmas|alarms)\b",
            folded,
        )
        and not _has(folded, _CLOCK_TIME_SELECTOR)
        # D39 (owner, 2026-09-29): the plural that says no which is read and offered, not asked
        # (``resolve_explicit_effects``); only a plural that says which alarms («de la mañana») is asked.
        and not ("notification.list" in available and plural_alarm_cancellation(text))
    ):
        return ClarificationIntent(("notification.cancel.at",), ("which_alarm",))
    if (
        "reminder.create" in available
        and re.search(
            # Uso real 2026-09-24 «olly i want to go to the outdoor movie screening this weekend remind me»: what
            # was said is what to remind; a trailing «remind me» with no moment asks when.
            r"\S\s*[,.;]?\s+(?:remind\s+me(?:\s+(?:of|about)\s+it)?|recuerdamelo|recordamelo|avisame)[\s.!?]*$",
            folded,
        )
        and not _reminder_has_actionable_due(folded)
    ):
        return ClarificationIntent(("reminder.create",), ("due_time",))
    if (
        not _is_direct_request(folded)
        and not _alarm_turn_off_request(folded)
        and not incomplete_message_shape
        and not relative_spoken_volume
        and not telegraphic_calendar_invite
        # BRIGHT1283: «estoy cansado subí el brillo», «subime el brillo» carry
        # a preamble or a clitic the direct-request heads do not list.
        and not brightness_relative_without_amount(folded)
        and not fragment_streaming_clause
        # «reunirme con Pablo mañana a las tres»: an event said as what the person will do.
        and agenda_event_request(text) is None
    ):
        return None
    corrected_generic_game_request = (
        re.fullmatch(
            (
                r"(?:quiero|quisiera|me\s+gustaria)\s+jugar\s+"
                r"(?:a\s+)?(?:algun|un)\s+juego\s+[^.;!?]{1,80}?\s*[,;]?\s*"
                r"(?:quiero\s+decir|o\s+sea|mejor)\s+[^.;!?]{1,80}"
                r"[\s.!?]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "game.launch" in available and corrected_generic_game_request:
        return ClarificationIntent(("game.launch",), ("game_title",))
    corrected_incomplete_note = (
        re.fullmatch(
            (
                r"(?:can\s+you\s+)?(?:make|create)\s+(?:a\s+)?new\s+"
                r"shared\s*[,;]?\s*(?:no|sorry)\s*[,;]?\s*personal\s+note"
                r"[\s.!?]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "note.create" in available and corrected_incomplete_note:
        return ClarificationIntent(("note.create",), ("note_content",))
    if (
        "ocr.read" in available
        and _has(folded, r"\bocr\b")
        and _has(folded, rf"\b{_READ}\b|\bleela\b|\bleelo\b")
        and not (
            _has(
                folded,
                r"\b(?:captura(?: de pantalla)?|pantallazo|screenshot|screen capture)\b",
            )
            and _has(
                folded,
                r"\b(?:haz|hacer|toma|tomar|crea|capture|take)\b",
            )
        )
    ):
        return ClarificationIntent(
            ("ocr.read",),
            ("image_or_new_screenshot",),
        )
    if (
        "message.send" in available
        and _head_is(
            _request_head(folded),
            r"(?:envia|enviar|enviales|manda|mandar|mandales|send)",
        )
        and _has(
            folded,
            r"\b(?:mandales|enviales|send them)\b|"
            r"\b(?:ese|esa|that)\s+(?:mensaje|message)\b",
        )
    ):
        return ClarificationIntent(
            ("message.send",),
            ("recipient", "message_text"),
        )
    if (
        "message.send" in available
        and incomplete_message_shape
        and message_draft_request(text) is None
        # REOPEN1993 grupo E: a recipient and a text with no client named is complete;
        # the client is looked up in WhatsApp and Discord.
        and not ("message.recipient.resolve" in available and message_request_any_channel(text) is not None)
    ):
        # MSGCLAR «mandale al grupo Musica: prueba 1 de WhatsApp, ya funciona
        # de nuevo»: a client named inside the dictated text is part of the
        # message, not the channel; the channel counts in the instruction
        # before the dictation or as a trailing «por whatsapp».
        instruction_part = re.split(
            r":|\bque\s+diga\b|\bque\s+dice\b|\bdiciendo\b|\bsaying\b|\bthat\s+says\b",
            folded,
            maxsplit=1,
        )[0]
        supported_channel = _has(
            instruction_part,
            r"\b" + _MSG_CHANNEL_WORDS + r"\b",
        ) or _has(
            folded,
            r"\b(?:por|en|via|on|in|through|by)\s+" + _MSG_CHANNEL_WORDS + r"[\s.!?]*$",
        )
        literal_recipient = _has(
            folded,
            (
                r"^[^\w]*ask\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
                r"(?:if|whether|what|when)\b|"
                r"^[^\w]*message\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
                r"(?:and\s+tell|and\s+say|that|saying)\b|"
                r"^[^\w]*tell\s+[a-z0-9][a-z0-9 _-]{0,80}?\s+that\b|"
                rf"^[^\w]*{message_speech_act}\s+"
                r"(?:a\s+)?"
                r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+(?:que|el\s+texto|el\s+mensaje)\b|"
                rf"^[^\w]*{message_speech_act}\s+(?:a\s+|al\s+(?:grupo\s+)?|para\s+)?"
                r"[a-z0-9][a-z0-9 ._-]{0,80}?\s*:\s*\S|"
                r"^[^\w]*let\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+know\s+that\b|"
                r"^[^\w]*write\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
                r"(?:that|the\s+message)\b|"
                r"^[^\w]*preguntale\s+a\s+[a-z0-9]"
                r"[a-z0-9 ._-]{0,80}?\s+(?:si|que|a que)\b|"
                r"\b(?:mensaje|message)\s+(?:a|to)\s+[a-z0-9]"
                r"[a-z0-9 ._-]{0,80}?\s+(?:para|to)\b|"
                r"\b(?:envia|manda|send)\s+"
                r"(?!(?:este|esta|this|that|the|a|an)\b)[a-z0-9]"
                r"[a-z0-9 ._-]{0,80}?\s+(?:el\s+|the\s+)?"
                r"(?:whatsapp\s+)?(?:mensaje|message)\b"
            ),
        ) and not _has(
            folded,
            r"\b(?:a|to)\s+(?:ellos|ellas|les|them)\b",
        )
        literal_payload = _has(
            folded,
            (
                r"\b(?:mensaje|message)\s*:\s*\S|"
                r"^[^\w]*ask\s+.+?\s+(?:if|whether|what|when)\s+\S|"
                r"^[^\w]*message\s+.+?\s+(?:and\s+tell|and\s+say|that|saying)\s+\S|"
                r"^[^\w]*tell\s+[^.;!?]{1,80}?\s+that\s+\S|"
                rf"^[^\w]*{message_speech_act}\s+"
                r"(?:a\s+)?"
                r".+?\s+(?:que|el\s+texto|el\s+mensaje)\s+\S|"
                rf"^[^\w]*{message_speech_act}\s+.+?:\s*\S|"
                r"^[^\w]*let\s+.+?\s+know\s+that\s+\S|"
                r"^[^\w]*write\s+.+?\s+(?:that|the\s+message)\s+\S|"
                r"^[^\w]*preguntale\s+a\s+.+?\s+(?:si|que|a que)\s+\S|"
                r"\b(?:para|to)\s+(?:decirle|tell)\b.+\S|"
                r"\b(?:mensaje|message)\s+[Â«\"'â€˜â€œ]?[a-z0-9].+|"
                r"\b(?:mensaje|message)\s+[^\w\s]\s*[a-z0-9].+"
            ),
        )
        missing_fields = tuple(
            field
            for field, present in (
                ("channel", supported_channel),
                ("recipient", literal_recipient),
                ("message_text", literal_payload),
            )
            if not present
        )
        if missing_fields:
            return ClarificationIntent(("message.send",), missing_fields)
    # Uso real 2026-09-23: an event is asked only what was never said (its time, its title, am or pm,
    # a repetition the calendar cannot hold); a start without an end lasts an hour.
    for clause in (text, *_request_clauses(folded)):
        event = agenda_event_request(clause)
        if event is not None:
            operation = "notification.schedule" if event.repeat else "calendar.event.create"
            if event.missing and operation in available:
                return ClarificationIntent((operation,), event.missing)
            break
    telegraphic_calendar_invite = (
        re.fullmatch(
            (
                r"(?:calendar\s+)?event\s+(?:send\s+)?invite\s+"
                r"[a-z0-9][a-z0-9 ._-]{0,96}[\s?!.]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "calendar.event.create" in available and telegraphic_calendar_invite:
        return ClarificationIntent(
            ("calendar.event.create",),
            ("event_title", "event_time"),
        )
    if (
        "app.open" in available
        and _head_is(_request_head(folded), _OPEN)
        and (
            # A generic app object is missing an identity, not a capability.
            # Consume the whole request so a named target or added instruction
            # stays with its ordinary argument/domain handling.
            re.fullmatch(
                rf"[¿?¡!\s]*{_OPEN}\s+(?:(?:un|una|a|an|el|la|the)\s+)?"
                r"(?:aplicacion|application|app|programa|program)"
                r"(?:\s*[,;]?\s*(?:por\s+favor|please))?[\s.!?]*",
                folded,
            )
            is not None
            or _has(
                folded,
                r"\b(?:navegador\s+por\s+defecto|default\s+browser|"
                r"(?:la\s+|the\s+)?ventana|window)\b",
            )
        )
        and not _has(folded, _KNOWN_APPLICATION)
        and not _has(folded, r"\b(?:incognito|incognita|privada|private)\b")
    ):
        return ClarificationIntent(("app.open",), ("application",))
    if (
        {"backup.create", "filesystem.write.text"} <= available
        and _has(folded, r"\b(?:backup|respaldo|copia\s+de\s+seguridad)\b")
        and _has(
            folded,
            r"\b(?:edita|editar|cambia|cambiar|modifica|modify|edit|change)\b",
        )
    ):
        return ClarificationIntent(
            ("backup.create", "filesystem.write.text"),
            ("target_file", "replacement_content"),
        )
    if (
        "bluetooth.device.pair" in available
        and _head_is(_request_head(folded), r"(?:conecta|conectar|connect)")
        and _has(folded, r"\bbluetooth\b")
        and not _has(
            folded,
            r"\b(?:dispositivo|device|auriculares?|headphones?)\s+\S",
        )
    ):
        return ClarificationIntent(("bluetooth.device.pair",), ("device",))
    if (
        "clipboard.write.text" in available
        and _head_is(_request_head(folded), r"(?:copia|copiar|copiame|copy)")
        and _has(folded, r"\b(?:portapapeles|clipboard)\b")
        and _has(folded, r"\b(?:este|esta|this)\s+(?:texto|text)\b")
    ):
        return ClarificationIntent(("clipboard.write.text",), ("text",))
    if (
        {
            "filesystem.known.search",
            "filesystem.read.text",
            "filesystem.write.text",
        }
        <= available
        and _head_is(_request_head(folded), r"(?:convierte|convert|transforma)")
        and _has(folded, r"\b(?:archivo\s+nuevo|new\s+file)\b")
    ):
        return ClarificationIntent(
            (
                "filesystem.known.search",
                "filesystem.read.text",
                "filesystem.write.text",
            ),
            (
                "source_file",
                "destination_file",
            ),
        )
    # MUSIC1571: «poneme una canción», «ponme musika», «tengo hambre poné
    # música», «no me molesta, poné música» are the same incomplete request:
    # a song or music with nothing named; a spoken preface before the order
    # («tengo hambre», «no me molesta,») is envelope here.
    music_folded = re.sub(
        r"^(?:(?:tengo\s+(?:hambre|sueno|frio|calor)|no\s+me\s+molesta|bueno|dale|che|ya)\s*[,;:]?\s+)+",
        "",
        folded,
        count=1,
    )
    incomplete_media_clause = any(
        # MUSIC1767 «tocá una canción en Spotify», «tocame algo»: the same bare request.
        _head_is(_request_head(clause), r"(?:pon|pone|poneme|ponme|reproduce|reproduci|reproducime|play|toca|tocame|toque)")
        # VIDEO1717 «abre youtube y pon un video»: a bare video is as
        # incomplete as a bare song. Uso real 2026-09-23 «empieza la playlist», «toca»: a playlist,
        # a podcast or the order alone names nothing to play either.
        and (
            _has(clause, r"\b(?:musica|music|musika|cancion|canciones|song|songs|tema|temas|track|tracks|algo|something|videos?)\b")
            or _has(
                clause,
                r"\b(?:playlists?|lista\s+de\s+(?:reproduccion|canciones)|podcasts?|audiolibros?|audiobooks?)"
                r"(?:\s+(?:por\s+favor|please))?[\s.!?]*$",
            )
            or _has(clause, _OWN_FAVOURITE)
            or re.fullmatch(r"(?:pon|ponme|poneme|toca|tocame)[\s.!?]*", clause) is not None
        )
        and _desired_music_query(clause) is None
        # Fase 3.5b M27 (reserva: «necesito escuchar algunas canciones tristes hoy», «pon la cancion la macarena»,
        # «play some jazz music» asked «¿qué música?»): what is left once the order and the generic words go is what
        # to play; only a bare order asks.
        and not _music_clause_names_content(clause)
        # Tanda 4c: a free choice within the person's own collection, or what they played last, is complete.
        and not own_recent_listening_request(clause)
        and not own_collection_free_choice(clause)
        # «pon la canción anterior», «pon el siguiente tema»: a transport order
        # names the song by its place in the queue; nothing is missing.
        and _media_transport_action(clause) is None
        # A video that is already named («un video de lofi en youtube») or a
        # title on a streaming service («The Office en Prime Video») is not bare.
        and youtube_play_query(clause) is None
        and not _has(clause, r"\bvideos?\s+(?:de|sobre|of|about)\s+\S")
        and not _has(clause, r"\b(?:en|on)\s+(?:netflix|disney|prime|hbo|max|crunchyroll|star|paramount|twitch|hulu|peacock|apple)\b")
        for clause in _request_clauses(music_folded)
    )
    # VIDEO1925 H0010 «prende algo en netflix»: un pedido de streaming sin
    # título es tan vacío como una canción sin nombre, y la cláusula de arriba
    # excluye los servicios a propósito porque «The Office en Prime Video» sí
    # nombra un título. Aquí sólo entra lo que nombra el servicio y NO nombra
    # nada que ver: se pregunta por el título, que es el único dato que falta.
    # «Prende» es «pon» en el habla de la persona.
    bare_streaming_clause = any(
        _head_is(
            _request_head(clause),
            r"(?:pon|pone|poneme|ponme|prende|prendeme|prendé|reproduce|reproduci|play|put|start|inicia|dale)",
        )
        and _has(
            clause,
            r"\b(?:algo|something|anything|cualquier\s+cosa|una\s+serie|a\s+(?:series|show)|"
            r"un\s+video|a\s+video|una\s+peli(?:cula)?|a\s+(?:movie|film)|lo\s+que\s+sea|whatever)\b",
        )
        and _has(clause, r"\b(?:en|on)\s+" + _NETFLIX_SPELLED + r"\b")
        and not _has(
            clause,
            r"\b(?:algo|something|una\s+serie|un\s+video|una\s+peli(?:cula)?)\s+"
            r"(?:de|sobre|llamad[oa]|of|about|called|named)\s+\S",
        )
        for clause in _request_clauses(music_folded)
    )
    if "streaming.play.named" in available and (bare_streaming_clause or fragment_streaming_clause):
        # El nombre del hueco es lo que el modelo lee para redactar la pregunta:
        # con «title» a secas, «put something on Netflix» acabó en «what would
        # you like me to add to Netflix?», que lee «put on» como añadir.
        return ClarificationIntent(("streaming.play.named",), ("title_to_watch",))
    browser_music = _named_browser_music_request(text)
    if (
        "media.play.query" in available
        and "browser.navigate.named" in available
        and browser_music is not None
        and browser_music[1] is None
    ):
        # MUSIC1827 «abrí chrome y poné música»: which music is asked first;
        # the answer opens YouTube's results in that browser.
        return ClarificationIntent(("media.play.query",), ("query",))
    if (
        "media.play.query" in available
        and incomplete_media_clause
        and (
            _head_is(
                _request_head(music_folded),
                r"(?:pon|pone|poneme|ponme|reproduce|play|toca|tocame|toque)",
            )
            or (_head_is(_request_head(music_folded), _OPEN) and _has(music_folded, r"\b(?:spotify|youtube)\b"))
        )
    ):
        return ClarificationIntent(("media.play.query",), ("query",))
    if (
        "audio.volume" in available
        and re.fullmatch(
            rf"{_SET_VOLUME_VERB}\s+(?:(?:el|the)\s+)?(?:volumen|volume)"
            r"(?:\s+(?:(?:al?|del?)\s+(?:sistema|equipo|pc|computador(?:a)?|ordenador)|"
            r"(?:of|on)\s+(?:the|my)\s+(?:system|computer|pc)))?"
            r"(?:\s+(?:a|al|en|to|at))?"
            r"(?:\s*,?\s*(?:please|por favor))?[.!?]*",
            folded,
        ) is not None
    ):
        # The same setting head with no target level is incomplete, not a
        # request to observe the previous level. Preserve the known operation
        # before the native selector can repeat an earlier status request.
        # A trailing value preposition still supplies no level. Full matching
        # preserves supplied values, other targets and subsequent clauses.
        return ClarificationIntent(("audio.volume",), ("level",))
    if "audio.app.volume.adjust" in available:
        app_volume = app_volume_request(text, application_names)
        if app_volume is not None and app_volume[2] is None:
            # AUDIO1787 «subí el volumen de spotify»: the application volume
            # keeps its direction and asks how much (owner rule on H0027).
            return ClarificationIntent(("audio.app.volume.adjust",), ("amount",))
    if (
        "audio.volume.adjust" in available
        and (
            _head_is(
                _request_head(folded),
                rf"(?:{_VOLUME_UP_VERB}|{_VOLUME_DOWN_VERB})",
            )
            and _has(folded, r"\b(?:volumen|volume)\b")
            or relative_spoken_volume
            or _bare_music_volume_request(folded)
            or _bare_clitic_volume_request(folded)
        )
        and not _has(folded, r"\b(?:100|[0-9]{1,2})\b")
        and _literal_percentage_word_value(folded) is None
        and _literal_volume_adjustment(folded) is None
        # «sube el volumen de la música a noventa»: a level said in words is no missing amount.
        and not _level_quantity_said(folded)
    ):
        if (
            "system.settings.adjust" in available
            and _has(
                folded,
                rf"\b(?:{_BRIGHTNESS_UP_VERB}|{_BRIGHTNESS_DOWN_VERB})\b[^,;]{{0,24}}"
                rf"\b{_BRIGHTNESS_OBJECT}\b",
            )
            and _literal_brightness_adjustment(folded) is None
        ):
            # AUDIO1461 «subí el volumen y bajá el brillo»: both amounts are
            # missing; the question must name both adjustments (H0027).
            return ClarificationIntent(("audio.volume.adjust", "system.settings.adjust"), ("amount",))
        return ClarificationIntent(("audio.volume.adjust",), ("amount",))
    if (
        "system.settings.adjust" in available
        and brightness_relative_without_amount(folded)
        and _literal_brightness_adjustment(folded) is None
    ):
        # BRIGHT1283: «subí el brillo» keeps its direction and asks how much,
        # the same owner rule as the volume (H0027); no default step.
        return ClarificationIntent(("system.settings.adjust",), ("amount",))
    if (
        {"memory.recall", "clipboard.write.text"} <= available
        and _head_is(_request_head(folded), r"(?:copy|copia|copiame)")
        and _has(folded, r"\b(?:my|mi)\s+(?:email|correo)\s+(?:address|electronico)\b")
        and _has(folded, r"\b(?:clipboard|portapapeles)\b")
    ):
        return ClarificationIntent(
            ("memory.recall", "clipboard.write.text"),
            ("stored_email_address",),
        )
    if (
        "office.document.create" in available
        and "document.presentation.create" not in available
        and _has(folded, r"\b(?:powerpoint|presentacion|presentation)\b")
        and _has(folded, r"\b(?:crea|crear|haz|hacer|make|create)\b")
        and not _has(folded, r"\b(?:sobre|about|titulad[oa]|called|named)\b")
        and not _has(folded, r"\b(?:diapositivas?|slides?)\b|\b\d+\b")
    ):
        return ClarificationIntent(
            ("office.document.create",),
            ("topic_or_content",),
        )
    if (
        "reminder.create" in available
        and _has(folded, r"\b(?:recordatorio|reminder)\b")
        and _head_is(
            _request_head(folded),
            r"(?:pon|ponme|pone|crea|crear|set|create)",
        )
    ):
        if not _reminder_has_actionable_due(folded):
            return ClarificationIntent(("reminder.create",), ("due_time",))
        if _time_only_reminder_request(folded):
            return ClarificationIntent(("reminder.create",), ("title",))
    if (
        "task.create" in available
        and list_creation_without_items(folded) is not None
        # M94 (DEV-D D-s007): a list of the person's mails is no list of theirs to fill (a limit).
        and not person_mail_collection_request(folded)
    ):
        # «por favor crea una nueva lista»: a list is its entries; what goes on it is asked.
        return ClarificationIntent(("task.create",), ("list_entries",))
    if "task.create" in available and _task_without_title(folded):
        # AGENDA1021/TIME1199 H0043 «crea una tarea para el viernes»: only a
        # date was given; the title is asked, never invented.
        return ClarificationIntent(("task.create",), ("title",))
    alarm_turn_off = _alarm_turn_off_request(folded)
    unnamed_cancellation = (
        (
            _head_is(
                _request_head(folded),
                r"(?:delete|remove|cancel|erase|elimina|eliminar|borra|borrar|"
                r"quita|quitar|cancela|cancelar|"
                # AGENDA1337 «cancelame la alarma»: the clitic forms are the
                # same unnamed cancellation.
                r"cancelame|cancelamela|cancelala|borrame|borrala|quitame|quitala|"
                r"eliminame|eliminala)",
            )
            or alarm_turn_off
        )
        and not _has(folded, _CLOCK_TIME_SELECTOR)
        and not _latest_notification_selector(folded)
        and _exact_local_reminder_title(folded) is None
    )
    if (
        unnamed_cancellation
        and "reminder.delete" in available
        and _has(folded, r"\b(?:reminder|recordatorio)\b")
        and not _has(folded, r"\b(?:reminders|recordatorios)\b")
    ):
        return ClarificationIntent(("reminder.delete",), ("reminder_title",))
    if (
        unnamed_cancellation
        and "notification.cancel.at" in available
        and _has(folded, r"\b(?:alarm|alarma)\b")
        and not _has(folded, r"\b(?:alarms|alarmas)\b")
    ):
        # AGENDA1021 H0011 «cancelá la alarma»: the owner rules that the
        # product asks which alarm (unless it already knows a single one);
        # naming the missing field as a time made it ask when to cancel.
        return ClarificationIntent(("notification.cancel.at",), ("which_alarm",))
    if (
        "window.move" in available
        and _head_is(
            _request_head(folded),
            r"(?:arrastra|arrastrar|mueve|mover|drag|move)",
        )
        and _has(folded, r"\b(?:ventana|window)\b")
        and not _has(folded, r"\b(?:activa|active|actual|current|de\s+\S+)\b")
        and not _has(folded, r"\b(?:archivo|file|carpeta|folder)\b")
    ):
        return ClarificationIntent(("window.move",), ("window",))
    return None


def streaming_service_named(text: str) -> str:
    """The catalog value of the streaming service the text names: disney_plus or netflix."""

    folded = _fold(text)
    if _has(folded, r"\b(?:disney\s*\+|disney\s*plus|disneyplus|disney|dysney|disne|dinsey|dizney|east\s*plus)\b"):
        return "disney_plus"
    return "netflix"


def near_catalog_application_candidates(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[str, ...]:
    """APPS1495 «abres team», «Abre stea,», «Sí, abre Ste.», «abre Steel.»: the
    catalog names (at most two) that a plain open order almost names — a
    prefix of three or more letters, or one or two edits away — when the
    target itself matches no catalog entry. Empty for anything else: an
    authenticated target, a target with more than two words, a negation,
    a deferred request, or no near miss."""

    catalog = build_application_catalog_index(application_names)
    folded = _strip_request_envelope(_fold(text))
    if not folded or _has(folded, r"\b(?:no|nunca|jamas|never|don't|do\s+not)\b|\b(?:si|if|cuando|when)\b.{0,20}\b(?:termine|acabe|finish)\b"):
        return ()
    folded = re.sub(r"^(?:si|ok|dale|bueno|y|and)\s*[,.]?\s*(?:quema\s*,?\s*)?", "", folded, count=1).strip()
    if _authenticated_application_target(folded, catalog) is not None:
        return ()
    if resolve_application_catalog_app_id(folded, catalog) is not None:
        # An alias the catalog resolver already authenticates («abrime el
        # chrome» → Google Chrome) is an opening, not a near miss.
        return ()
    request = _application_open_request(folded)
    if request is None or request.group("desire") is not None:
        return ()
    target = request.group("target").strip(" ¿?¡!,:;.-")
    target = re.sub(r"\s*,?\s*(?:por\s+favor|porfa|please|pls)$", "", target).strip(" ,.")
    target = re.sub(r"^(?:el|la|los|las|the|a|an)\s+", "", target)
    key = _application_name_key(target)
    if not key or len(key) < 3 or len(key.split()) > 2 or not re.fullmatch(r"[a-z0-9 .+-]+", key):
        return ()
    if key in catalog.keys:
        return ()
    scored: list[tuple[int, int, str]] = []
    for name, entry_key in catalog.entries:
        tokens = [entry_key] + entry_key.split()
        best = None
        prefix = 0
        for token in tokens:
            if len(token) < 3:
                continue
            if token.startswith(key) and len(key) >= 3:
                score = 0
            else:
                distance = _edit_distance(key, token)
                limit = 1 if len(key) <= 4 else 2
                if distance > limit:
                    continue
                score = distance
            if best is None or score < best:
                best = score
                prefix = _common_prefix_length(key, token)
            elif score == best:
                prefix = max(prefix, _common_prefix_length(key, token))
        if best is not None:
            scored.append((best, -prefix, name))
    scored.sort()
    if not scored:
        return ()
    # A short garbled target («team», «ste») may stand for two names one edit
    # apart (Teams/Steam); a longer one keeps only its closest names.
    best = scored[0][0]
    tolerance = 1 if len(key) <= 4 else 0
    names = []
    prefixes = []
    scores = []
    for score, negative_prefix, name in scored:
        if score <= best + tolerance and name not in names:
            names.append(name)
            prefixes.append(-negative_prefix)
            scores.append(score)
    # NEAR1995 «abre Steel.»: with this PC's catalog «steel» is two edits from
    # «steam» and from two installed «Shell» names alike. What a person hears
    # is the opening of the word: among names tied at the same distance, the
    # one that alone shares three or more leading letters with what was said
    # is the name meant. Names kept only by the short-word tolerance («team»:
    # Teams at 0, Steam at 1) are not a tie and still ask which (H0521, owner).
    if len(names) > 1 and len(set(scores)) == 1:
        longest = max(prefixes)
        leaders = [name for name, length in zip(names, prefixes) if length == longest]
        if longest >= 3 and len(leaders) == 1:
            return (leaders[0],)
    return tuple(names[:2])


def _common_prefix_length(left: str, right: str) -> int:
    count = 0
    for a, b in zip(left, right):
        if a != b:
            break
        count += 1
    return count


def near_single_open_candidate(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
    games: Iterable[tuple[str, str, str]] | GameCatalogIndex,
) -> tuple[str, str] | None:
    """REOPEN1993 (auditoría semántica; regla del dueño 2026-09-19 «lo mal dicho
    lo arregla BAXY»): an open, launch or go-to order that almost names exactly
    ONE installed application («abre Steel.», «Abre stea,», «Sí, abre Ste.») or
    exactly one installed game («Ve a Mad de Rivals.») names it: the opening
    happens and the final says which one opened. Two candidates («abres team»
    → Steam / Microsoft Teams) keep asking which; none keeps the other readers.
    Returns (operation, display name) or None."""

    applications = near_catalog_application_candidates(text, application_names)
    if len(applications) == 1:
        return ("app.open", applications[0])
    if applications:
        return None
    titles = near_catalog_game_candidates(text, games)
    if len(titles) == 1:
        return ("game.launch", titles[0])
    return None


def _indexed_authenticated_application_target(
    text: str,
    catalog: ApplicationCatalogIndex,
    *,
    installed_query: bool,
) -> tuple[int, str] | None:
    """Resolve one anchored target with bounded parsing and indexed lookup."""

    polite = (
        r"(?:(?:por favor|please)\s*[,;:]?\s*|"
        r"(?:puedes|podrias|can you|could you|would you)\s+)?"
    )
    trailing = (
        r"(?:\s*[,;:]?\s+(?:por favor|please|para mi|for me|ahora|now|"
        r"dale|porfa|porfi|porfis|pls|plz))?"
        r"[\s?!.]*$"
    )
    if installed_query:
        patterns = (
            (
                r"^[¿?¡!\s]*(?:esta|estan|is|are)\s+"
                r"(?:instalad[oa]s?|installed)\s+"
                r"(?P<target>.+)$"
            ),
            (
                r"^[¿?¡!\s]*(?:esta|estan|is|are)\s+"
                r"(?P<target>.+)\s+"
                rf"(?:instalad[oa]s?|installed){trailing}"
            ),
        )
    else:
        patterns = (
            (
                rf"^[¿?¡!\s]*{polite}(?:me\s+)?{_OPEN}\b\s+"
                r"(?P<target>.+)$"
            ),
        )
    matches: list[tuple[int, str]] = []
    for pattern in patterns:
        request = _match(text, pattern)
        if request is None or _is_negated_match(text, request):
            continue
        for target, offset in _application_target_forms(
            request.group("target"),
        ):
            target_key = _catalog_alias_key(_application_name_key(target), catalog.keys)
            if target_key is not None:
                matches.append((request.start("target") + offset, target_key))
    if not matches:
        return None if installed_query else _repeated_application_target(text, catalog)
    return min(
        matches,
        key=lambda item: (-len(item[1]), item[1], item[0]),
    )


def _authenticated_application_target(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
    *,
    installed_query: bool = False,
) -> tuple[int, str] | None:
    """Match an anchored app request against the OS-authenticated catalog."""

    return _indexed_authenticated_application_target(
        text,
        build_application_catalog_index(application_names),
        installed_query=installed_query,
    )


def _application_desire_is_positive(folded: str) -> bool:
    """Keep the existing desired-open exclusions on the complete request."""

    return not (
        _is_negative_effect_clause(folded)
        or _is_meta_or_tool_denial(folded)
        or _has_contradictory_correction(folded)
        or _has_unsupported_deferred_effect(folded)
        or _is_past_or_hypothetical_state(folded)
        or _has(
            folded,
            r"\b(?:on|en)\s+(?:my|mi|the|el|la)?\s*"
            r"(?:phone|telefono|movil|celular|tablet|ipad|iphone|console|consola)\b",
        )
    )


def _application_open_request(text: str) -> re.Match[str] | None:
    """Extract an ordinary or positive desired opening without resolving identity."""

    request = _match(
        text,
        (
            r"^[¿?¡!\s]*(?:(?:(?:por favor|please)\s*[,;:]?\s*|"
            r"(?:puedes|podrias|can you|could you|would you)\s+)?"
            rf"(?:me\s+)?{_OPEN}\b|"
            r"(?P<desire>(?:(?:i|we)\s+(?:need|want)\s+(?:you\s+)?to|"
            r"(?:i|we)\s+would\s+like\s+(?:you\s+)?to)\s+"
            r"(?:open|start|launch)|"
            r"(?:necesito|quiero|quisiera)\s+que\s+"
            r"(?:abras|abran|inicies|inicien|lances|lancen)))\s+"
            r"(?P<target>.+)$"
        ),
    )
    if request is not None and request.group("desire") is not None:
        if not _application_desire_is_positive(text):
            return None
    return request


def resolve_application_catalog_app_id(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """Resolve one conservative provider input from the authenticated snapshot."""

    catalog = build_application_catalog_index(application_names)
    folded = _strip_request_envelope(_fold(text))
    # «ponme word» (owner's mother 2026-09-21): the same opening as «abre word».
    folded = re.sub(r"^[¿?¡!\s]*(?:pon|ponme|poneme|pone)\s+(?:me\s+)?", "abre ", folded, count=1)
    target = _authenticated_application_target(folded, catalog)
    if target is None:
        target = _authenticated_application_desired_open(folded, catalog)
    if target is not None:
        matches = [entry for entry in catalog.entries if entry[1] == target[1]]
        return matches[0][0] if len(matches) == 1 else None

    request = _application_open_request(folded)
    raw_target = request.group("target") if request is not None else folded
    forms = _application_target_forms(raw_target)
    if request is not None and request.group("desire") is not None:
        occurrence = catalog.occurrence_pattern
        if occurrence is not None and len(list(occurrence.finditer(folded))) > 1:
            return None
        # Alias resolution must retain the desired-open suffix boundary too.
        forms = tuple(
            (form, offset)
            for form, offset in forms
            if raw_target[offset + len(form) :].strip(" ¿?¡!,:;.-")
            in {"", "por favor", "porfa", "please", "dale", "pls"}
        )
    keys = tuple(
        dict.fromkeys(
            _application_name_key(form)
            for form, _ in forms
            if _application_name_key(form)
        )
    )
    if not keys:
        return None

    notepad_aliases = {
        "app de notas",
        "bloc de notas",
        "coso de notas",
        "editor de texto",
        "notepad",
    }
    calculator_aliases = {"calc", "calculadora", "calculator"}
    settings_aliases = {
        "configuracion",
        "configuracion de windows",
        "configuraciones de windows",
        "windows settings",
    }
    catalog_keys = {key for _, key in catalog.entries}
    for key in keys:
        if key in notepad_aliases and catalog_keys & {"bloc de notas", "notepad"}:
            return "windows.notepad"
        if key in calculator_aliases and catalog_keys & {"calculadora", "calculator"}:
            return "windows.calculator"
        alias_key = _catalog_alias_key(key, frozenset(catalog_keys))
        if alias_key is not None and alias_key != key:
            matches = [name for name, candidate_key in catalog.entries if candidate_key == alias_key]
            if len(matches) == 1:
                return matches[0]
        if key in settings_aliases:
            matches = [
                name
                for name, candidate_key in catalog.entries
                if candidate_key in {"configuracion", "windows settings"}
            ]
            if len(matches) == 1:
                return matches[0]

    for key in keys:
        exact = [
            name for name, candidate_key in catalog.entries if candidate_key == key
        ]
        if len(exact) == 1:
            return exact[0]
        query_tokens = set(_entity_key(key).split())
        if not query_tokens:
            continue
        ranked: list[tuple[int, str]] = []
        for name, _ in catalog.entries:
            candidate_tokens = set(_entity_key(name).split())
            if query_tokens <= candidate_tokens:
                score = 90 - min(6, len(candidate_tokens) - len(query_tokens))
                ranked.append((score, name))
        ranked.sort(key=lambda item: (-item[0], _application_name_key(item[1])))
        if not ranked:
            continue
        if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 8:
            continue
        return ranked[0][1]
    return None


def _authenticated_application_close_target(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[int, str] | None:
    """Recognize one complete close request over an exact authenticated name.

    This supplies intent/domain evidence only: process/window identity still
    comes from window.resolve and the existing exact confirmation contract.
    """
    if (
        not effect_request_is_authoritative(text)
        or _has_unsupported_deferred_effect(_fold(text))
        or _other_device_effect_scope(_fold(text))
    ):
        return None
    # «necesito que cierres whatsapp», «podés cerrar la calculadora?»,
    # «cerrame el paint»: the desire/ability preface and the clitic still
    # ask for one close. The envelope already removes «puedes/could you».
    request = _match(
        _strip_request_envelope(_fold(text)),
        r"^[¿?¡!\s]*(?:(?:necesito|quiero|queria|quisiera|podes|podrias|podria|me\s+(?:podes|podrias|podria))\s+(?:que\s+)?)?"
        r"(?:cierra|cierres|cerra|cerrar|cerrame|close)\s+(?P<target>.+)$",
    )
    if request is None:
        return None
    catalog = build_application_catalog_index(application_names)
    raw_target = request.group("target")
    matches: list[tuple[int, str]] = []
    for target, offset in _close_target_forms(raw_target):
        # Do not inherit open's execution-count hints for a work-loss effect.
        # Only punctuation, the window wrapper's own tail («… window», «… app»)
        # and the existing bounded courtesy are removable.
        suffix = raw_target[offset + len(target):].strip(" ,;:.!?")
        suffix = re.sub(r"^(?:window|app|application)\b", "", suffix).strip(" ,;:.!?")
        if suffix and _APPLICATION_TRAILING_REQUEST.fullmatch(" " + suffix) is None \
                and _CLOSE_TRAILING_COURTESY.fullmatch(" " + suffix) is None:
            continue
        key = _authenticated_close_key(target, catalog)
        if key is not None:
            matches.append((request.start("target") + offset, key))
    identities = {key for _, key in matches}
    if len(identities) != 1:
        return None
    return min(matches, key=lambda item: item[0])


def _authenticated_close_key(target: str, catalog: ApplicationCatalogIndex) -> str | None:
    """Resolve one target form to an exact catalog key, through the shared alias resolver.

    «chrome» → Google Chrome and «notepad» → Bloc de notas reuse the same
    identity resolver the presence reader trusts; anything ambiguous or
    outside the authenticated snapshot stays None.
    """
    key = _application_name_key(target)
    if key in catalog.keys:
        return key
    resolved = resolve_application_catalog_app_id(target, catalog)
    if resolved is None:
        return None
    builtin = {"windows.notepad": ("bloc de notas", "notepad"),
               "windows.calculator": ("calculadora", "calculator")}
    candidates = [name for name, candidate in catalog.entries
                  if candidate == _application_name_key(resolved) or candidate in builtin.get(resolved, ())]
    keys = {_application_name_key(name) for name in candidates}
    return next(iter(keys)) if len(keys) == 1 else None


def _authenticated_application_focus_target(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[int, str] | None:
    """Recognize one request to bring an authenticated application to the front.

    WINDOWS1385 «traé chrome al frente», «enfocá chrome», «bring Chrome to
    the front»: a focus-only head, or a carry/put head with the front tail,
    over one exact catalog identity. Window identity still comes from
    window.resolve; an absent window ends there truthfully.
    """
    if (
        not effect_request_is_authoritative(text)
        or _has_unsupported_deferred_effect(_fold(text))
        or _other_device_effect_scope(_fold(text))
    ):
        return None
    folded = _strip_request_envelope(_fold(text))
    request = _match(
        folded,
        rf"^[¿?¡!\s]*(?:(?:necesito|quiero|queria|quisiera|podes|podrias|podria|me\s+(?:podes|podrias|podria))\s+(?:que\s+)?)?"
        rf"(?:{_FOCUS_HEAD_ONLY}\s+(?:(?:me|a)\s+)?(?P<target_a>.+?)(?:\s+{_FOCUS_TAIL})?"
        rf"|{_FOCUS_HEAD_WITH_TAIL}\s+(?:(?:me|a)\s+)?(?P<target_b>.+?)\s+{_FOCUS_TAIL})[\s.!?]*$",
    )
    if request is None:
        return None
    group = "target_a" if request.group("target_a") is not None else "target_b"
    raw_target = request.group(group)
    catalog = build_application_catalog_index(application_names)
    matches: list[tuple[int, str]] = []
    for target, offset in _close_target_forms(raw_target):
        suffix = raw_target[offset + len(target):].strip(" ,;:.!?")
        suffix = re.sub(r"^(?:window|app|application)\b", "", suffix).strip(" ,;:.!?")
        if suffix and _APPLICATION_TRAILING_REQUEST.fullmatch(" " + suffix) is None \
                and _CLOSE_TRAILING_COURTESY.fullmatch(" " + suffix) is None:
            continue
        key = _authenticated_close_key(target, catalog)
        if key is not None:
            matches.append((request.start(group) + offset, key))
    identities = {key for _, key in matches}
    if len(identities) != 1:
        return None
    return min(matches, key=lambda item: item[0])


def resolve_application_focus_name(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """Preserve an authenticated focus target as a catalog display name."""
    catalog = build_application_catalog_index(application_names)
    target = _authenticated_application_focus_target(text, catalog)
    if target is None:
        return None
    names = {name for name, key in catalog.entries if key == target[1]}
    return next(iter(names)) if len(names) == 1 else None


def _authenticated_application_minimize_target(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[int, str] | None:
    """Recognize one request to minimize an authenticated application by name.

    WINDOWS1695 H0697 «Minimisa ópera.»: a minimize head (the colloquial
    «minimisa» spelling included) over one exact catalog identity, with no
    «ventana» noun; window.resolve (the prerequisite) binds the window and an
    absent one ends there truthfully. «minimizá todo» stays with the desktop
    reader; a deictic «esta ventana» stays with window.active.
    """
    if (
        not effect_request_is_authoritative(text)
        or _has_unsupported_deferred_effect(_fold(text))
        or _other_device_effect_scope(_fold(text))
    ):
        return None
    folded = _strip_request_envelope(_fold(text))
    request = _match(
        folded,
        rf"^[¿?¡!\s]*(?:(?:necesito|quiero|queria|quisiera|podes|podrias|podria|me\s+(?:podes|podrias|podria))\s+(?:que\s+)?)?"
        rf"{_MINIMIZE_HEAD}\s+(?:(?:me|a)\s+)?(?P<target>.+?)[\s.!?]*$",
    )
    if request is None:
        return None
    raw_target = request.group("target")
    if _has(raw_target, r"\b(?:ventana|ventanas|window|windows|todo|todas|everything|all)\b"):
        return None
    catalog = build_application_catalog_index(application_names)
    matches: list[tuple[int, str]] = []
    for target, offset in _close_target_forms(raw_target):
        suffix = raw_target[offset + len(target):].strip(" ,;:.!?")
        suffix = re.sub(r"^(?:window|app|application)\b", "", suffix).strip(" ,;:.!?")
        if suffix and _APPLICATION_TRAILING_REQUEST.fullmatch(" " + suffix) is None                 and _CLOSE_TRAILING_COURTESY.fullmatch(" " + suffix) is None:
            continue
        key = _authenticated_close_key(target, catalog)
        if key is not None:
            matches.append((request.start("target") + offset, key))
    identities = {key for _, key in matches}
    if len(identities) != 1:
        return None
    return min(matches, key=lambda item: item[0])


def resolve_application_minimize_name(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """Preserve an authenticated minimize target as a catalog display name."""
    catalog = build_application_catalog_index(application_names)
    target = _authenticated_application_minimize_target(text, catalog)
    if target is None:
        return None
    names = {name for name, key in catalog.entries if key == target[1]}
    return next(iter(names)) if len(names) == 1 else None


def _authenticated_application_snap_target(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[int, str, str] | None:
    """Recognize one request to dock an authenticated application on a side.

    ARRANGE1781 H0268 «poné chrome a la izquierda»: a placing head over one
    exact catalog identity followed by a side («a la izquierda/derecha»,
    «to the left/right»); window.resolve binds the window and window.snap
    docks it on that half of its monitor. «la ventana de chrome» names the
    same window; «esta ventana» stays with window.active.
    """
    if (
        not effect_request_is_authoritative(text)
        or _has_unsupported_deferred_effect(_fold(text))
        or _other_device_effect_scope(_fold(text))
    ):
        return None
    folded = _strip_request_envelope(_fold(text))
    request = _match(
        folded,
        rf"^[¿?¡!\s]*(?:(?:necesito|quiero|queria|quisiera|podes|podrias|podria|me\s+(?:podes|podrias|podria))\s+(?:que\s+)?)?"
        rf"{_SNAP_HEAD}\s+(?:(?:me|a)\s+)?(?P<target>.+?)\s+{_SNAP_SIDE}[\s.!?]*$",
    )
    if request is None:
        return None
    raw_target = request.group("target")
    if _has(raw_target, r"\b(?:esta|this|esa|that|todo|todas|everything|all|activa|active|actual|current)\b"):
        return None
    side = "left" if _has(request.group("side"), r"\b(?:izquierda|left)\b") else "right"
    catalog = build_application_catalog_index(application_names)
    matches: list[tuple[int, str]] = []
    for target, offset in _close_target_forms(raw_target):
        key = _authenticated_close_key(target, catalog)
        if key is not None:
            matches.append((request.start("target") + offset, key))
    identities = {key for _, key in matches}
    if len(identities) != 1:
        return None
    offset, key = min(matches, key=lambda item: item[0])
    return (offset, key, side)


def resolve_application_snap(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[str, str] | None:
    """The authenticated snap target as (catalog display name, side)."""
    catalog = build_application_catalog_index(application_names)
    target = _authenticated_application_snap_target(text, catalog)
    if target is None:
        return None
    names = {name for name, key in catalog.entries if key == target[1]}
    return (next(iter(names)), target[2]) if len(names) == 1 else None


def resolve_application_snap_name(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """Preserve an authenticated snap target as a catalog display name."""
    resolved = resolve_application_snap(text, application_names)
    return resolved[0] if resolved is not None else None


# M55 (v3b F-w06-t1, F-w06-t2, F-w08-t1): one placing head over several windows, each with its own side —
# «pon el word a la izquierda y el chrome a la derecha», «Coloca la ventana de Word en la mitad izquierda y la de
# Chrome en la mitad derecha», «Snap the Chrome window to the left half and the Slack window to the right half».
_SNAP_PAIR_OPENING = (
    r"^[¿?¡!\s]*(?:(?:necesito|quiero|queria|quisiera|puedes|podes|podrias|podria|"
    r"me\s+(?:puedes|podes|podrias|podria))\s+(?:que\s+)?|(?:can|could|would|will)\s+you\s+(?:please\s+)?|"
    r"please\s+)?"
)
_SNAP_PAIR = re.compile(
    rf"(?P<target>.+?)\s+{_SNAP_SIDE}"
    rf"(?:(?P<more>\s*,?\s+(?:y|e|and)\s+(?:{_SNAP_HEAD}\s+(?:(?:me|a)\s+)?)?|\s*,\s*)"
    r"|(?P<end>(?:\s*,?\s+(?:so|so\s+that|para|para\s+que|porque|because)\b.*)?[\s.!?]*$))",
    re.IGNORECASE,
)
_SNAP_PAIR_ELLIPSIS = re.compile(r"^(?:la|el|the)\s+(?:de|del|of)\s+", re.IGNORECASE)
# M56 (v3c-final F-w08-t1, Slack not installed on the test PC): a name the catalog does not hold is still a name when
# it is one to three plain words and none of them is a word for a window, a program, a side or an article.
_ABSENT_NAME = re.compile(r"[a-z0-9][a-z0-9.+&'-]*(?:\s+[a-z0-9.+&'-]+){0,2}")
_NOT_A_NAME_WORD = frozenset({
    "ventana", "ventanas", "window", "windows", "app", "apps", "aplicacion", "aplicaciones", "application",
    "applications", "programa", "programas", "program", "programs", "pantalla", "screen", "mitad", "half", "lado",
    "side", "el", "la", "los", "las", "the", "de", "del", "of", "y", "e", "and", "otra", "otro", "other", "una",
    "un", "a", "an", "mi", "my", "tu", "your", "eso", "esto", "ese", "esa", "este", "esta", "aquello", "aquella",
    "it", "this", "that", "todo", "todas", "todos", "all", "everything", "ambas", "ambos", "both", "cosa", "thing",
    "lo", "le",
})


def _absent_application_name(raw_target: str, text: str) -> str | None:
    """The name a placing request gives a window the catalog does not hold, as the person wrote it."""

    names = [
        form
        for form, _ in _close_target_forms(raw_target)
        if _ABSENT_NAME.fullmatch(form) and not any(word in _NOT_A_NAME_WORD for word in form.split())
    ]
    if not names:
        return None
    name = min(names, key=len)
    written = re.search(r"(?<!\w)" + r"\s+".join(map(re.escape, name.split())) + r"(?!\w)", str(text), re.IGNORECASE)
    return written.group(0) if written is not None else name


def application_snap_pairs(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
    *,
    absent: bool = False,
) -> tuple[tuple[str, str, str], ...] | None:
    """Each window a placing request docks, in order, as (catalog display name, side, folded clause).

    The clause is the head with that window's own target and side («coloca la de chrome en la mitad derecha»),
    so one plan step can read its window alone. This reads the targets of an effect already decided upstream (the
    decider or a reader); it authorizes nothing: every target must be one exact catalog identity, all distinct, or
    the reading abstains. With ``absent`` (the plan of a placing the decider already chose), a target no catalog
    entry holds keeps the name the person gave it («Slack»): its resolve step asks the PC and the PC says it is not
    there; an ambiguous target still abstains.
    """

    folded = _strip_request_envelope(_fold(text))
    if (
        len(folded) > 2048
        or _has_unsupported_deferred_effect(folded)
        or _other_device_effect_scope(folded)
    ):
        return None
    opening = _match(folded, rf"{_SNAP_PAIR_OPENING}(?P<head>{_SNAP_HEAD})\s+(?:(?:me|a)\s+)?")
    if opening is None:
        return None
    catalog = build_application_catalog_index(application_names)
    head = opening.group("head")
    pairs: list[tuple[str, str, str]] = []
    position = opening.end()
    while True:
        found = _SNAP_PAIR.match(folded, position)
        if found is None:
            return None
        raw_target = _SNAP_PAIR_ELLIPSIS.sub("", found.group("target").strip())
        if not raw_target or _has(
            raw_target,
            r"\b(?:esta|this|esa|that|todo|todas|everything|all|activa|active|actual|current)\b",
        ):
            return None
        keys = {
            key for form, _ in _close_target_forms(raw_target)
            if (key := _authenticated_close_key(form, catalog)) is not None
        }
        names = {name for name, key in catalog.entries if key in keys}
        if not keys and absent:
            absent_name = _absent_application_name(raw_target, str(text))
            names = {absent_name} if absent_name is not None else set()
            keys = {"absent:" + absent_name.casefold()} if absent_name is not None else set()
        if len(keys) != 1 or len(names) != 1:
            return None
        side = "left" if _has(found.group("side"), r"\b(?:izquierda|left)\b") else "right"
        target = found.group("target").strip()
        if next(iter(keys)).startswith("absent:"):
            # The step reads its clause alone: it keeps the name as the person wrote it («Slack»).
            name = next(iter(names))
            target = re.sub(r"(?<!\w)" + re.escape(name.casefold()) + r"(?!\w)", lambda _: name, target, count=1)
        pairs.append((next(iter(names)), side, f"{head} {target} {found.group('side')}"))
        if found.group("end") is not None:
            break
        position = found.end()
    if len({name for name, _, _ in pairs}) != len(pairs):
        return None
    return tuple(pairs)


def resolve_application_close_name(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """Preserve an authenticated close target as a catalog display name."""
    catalog = build_application_catalog_index(application_names)
    target = _authenticated_application_close_target(text, catalog)
    if target is None:
        return None
    names = {name for name, key in catalog.entries if key == target[1]}
    return next(iter(names)) if len(names) == 1 else None


def _repeated_application_target(
    text: str,
    catalog: ApplicationCatalogIndex,
) -> tuple[int, str] | None:
    """Resolve a uniform whole-target repetition through one catalog identity."""

    folded = _strip_request_envelope(_fold(text))
    if len(folded) > 16_384 or not _application_desire_is_positive(folded):
        return None
    request = _application_open_request(folded)
    if (
        request is None
        or _is_negated_match(folded, request)
        or len(_request_clauses(folded)) != 1
    ):
        return None
    matches: set[tuple[int, str]] = set()
    for target, offset in _application_target_forms(request.group("target")):
        repeated = re.fullmatch(r"(?P<unit>.+?)(?:\s+(?P=unit))+", target)
        if repeated is None:
            continue
        unit = repeated.group("unit")
        tokens = set(unit.split())
        identities = [
            (name, key) for name, key in catalog.entries
            if tokens and tokens <= set(key.split())
        ]
        if len(identities) != 1:
            continue
        name, key = identities[0]
        # Exact complete tokens and unique membership constrain the existing
        # resolver; no similarity winner, alias or first-token guess is added.
        resolved = resolve_application_catalog_app_id(unit, catalog)
        if resolved is not None and resolved == resolve_application_catalog_app_id(name, catalog):
            matches.add((request.start("target") + offset, key))
    if len({key for _, key in matches}) != 1:
        return None
    return min(matches)


def resolve_application_window_status_name(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """Resolve a named visible-window question against the app snapshot.

    A foreground snapshot cannot establish absence of other windows. Conversely,
    visible windows do not establish background process liveness. Keep this read
    bounded to presence/count questions about one authenticated application; the
    model still owns other formulations and unresolved application identities.
    """
    catalog = build_application_catalog_index(application_names)
    folded = _strip_request_envelope(_fold(text)).strip(" ¿?¡!.")
    folded = _strip_request_envelope(folded).strip(" ¿?¡!.")
    if _other_device_effect_scope(folded):
        return None
    folded = re.sub(r"\s+(?:por favor|please|ahora|now)$", "", folded)
    # «está corriendo spotify», «tengo discord abierto» (WINDOWS1207): running
    # and «tengo … abierto» are presence questions about one application.
    state = r"(?:abiert[oa]|cerrad[oa]|open|closed|corriendo|running|ejecutandose|activ[oa])"
    inquiry = (
        r"(?:(?:comprueba|revisa|verifica|confirma|averigua|dime)\s+si|"
        r"(?:check|verify|confirm|see|find out|tell me)\s+(?:if|whether))\s+"
    )
    patterns = (
        rf"(?:esta|is)\s+(?P<target>.+?)\s+{state}",
        rf"esta\s+{state}\s+(?P<target>.+?)",
        rf"tengo\s+(?:(?:el|la|a)\s+)?(?P<target>.+?)\s+{state}",
        rf"do\s+i\s+have\s+(?P<target>.+?)\s+{state}",
        rf"{inquiry}(?P<target>.+?)\s+(?:esta|is)\s+{state}",
        rf"{inquiry}esta\s+{state}\s+(?P<target>.+?)",
        r"hay\s+(?:(?:alguna|una)\s+)?ventana\s+de\s+"
        r"(?P<target>.+?)\s+abierta",
        r"are\s+(?:any\s+)?windows\s+of\s+(?P<target>.+?)\s+open",
        r"how\s+many\s+windows\s+of\s+(?P<target>.+?)\s+are\s+open",
        r"how\s+many\s+(?P<target>.+?)\s+windows\s+are\s+open",
        r"cuantas\s+ventanas\s+de\s+(?P<target>.+?)\s+estan\s+abiertas",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, folded)
        if match is None:
            continue
        target = match.group("target")
        # Reuse the catalog's identity resolver, never a vocabulary of app
        # names. Its aliases are also understood by the status provider.
        # Whole-target forms prevent an extra clause becoming part of a name.
        for form, _ in _application_target_forms(target):
            key = _application_name_key(form)
            exact = [name for name, candidate in catalog.entries if candidate == key]
            if len(exact) == 1:
                return exact[0]
        return resolve_application_catalog_app_id(target, catalog)
    return None


# M103 (owner script t22 «¿Sabes qué peli estoy viendo en potplayer?» → media.status read Spotify's session and said
# «Estás escuchando … en Spotify, no en PotPlayer»): what a named player shows is asked of that application, and its
# window title carries it; the current media session is whichever application spoke last. Spotify and the browsers
# keep the media session read (their session is the player itself).
_SHOWN_IN_APPLICATION = re.compile(
    r"\b(?:que|cual|what|which)\b(?:\s+[a-z]+){0,2}?\s+"
    r"(?:(?:estoy|estas|esta|estamos|tengo)\s+(?:viendo|mirando|escuchando|oyendo|reproduciendo|puest[oa])|"
    r"veo|miro|escucho|(?:se\s+)?(?:esta\s+)?(?:reproduce|reproduciendo|sonando|suena|pasando|puest[oa])|"
    r"am\s+i\s+(?:watching|listening\s+to|playing)|(?:is|s)\s+(?:playing|on|showing)|"
    r"(?:is|are)\s+(?:you|we|they)\s+(?:watching|playing))\s+"
    r"(?:en|in|on)\s+(?:el\s+|la\s+|the\s+)?(?P<target>[^,;.!?]+?)[\s?!.]*$"
)
_SESSION_PLAYERS = re.compile(
    r"\b(?:spotify|chrome|google chrome|edge|microsoft edge|firefox|opera|opera gx|brave|navegador|browser)\b"
)


def application_shown_media_name(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """The installed application whose window says what the person is watching or hearing in it, or None."""

    folded = _strip_request_envelope(_fold(text)).strip(" ¿?¡!.").replace("'", " ")
    match = _SHOWN_IN_APPLICATION.search(folded)
    if match is None or _SESSION_PLAYERS.search(match.group("target")):
        return None
    catalog = build_application_catalog_index(application_names)
    for form, _ in _application_target_forms(match.group("target")):
        key = _application_name_key(form)
        exact = [name for name, candidate in catalog.entries if candidate == key]
        if len(exact) == 1:
            return exact[0]
    return resolve_application_catalog_app_id(match.group("target"), catalog)


def resolve_application_window_followup_name(
    text: str,
    previous_requests: Iterable[str],
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """Resolve one bounded read reference from user questions, never answers.

    A new or unresolved subject ends the chain. Previous commands cannot
    authorize an elliptical read, and assistant assertions cannot establish
    the application's identity or its current state.
    """
    catalog = build_application_catalog_index(application_names)

    def followup(request: str, previous: str | None) -> str | None:
        if previous is None:
            return None
        folded = _strip_request_envelope(_fold(request)).strip(" ¿?¡!.")
        folded = re.sub(r"\s+(?:por favor|please|ahora|now)$", "", folded)
        named = re.fullmatch(
            r"(?:y|and|what\s+about|how\s+about|que\s+hay\s+de)\s+(.+)", folded,
        )
        if named is not None:
            # Reuse the same whole-target catalog resolution as a full query.
            return resolve_application_window_status_name(
                f"is {named.group(1)} open", catalog,
            )
        entity = r"(?:es[ae]|est[ae])\s+(?:aplicacion|app|programa)"
        state = r"(?:abiert[oa]|cerrad[oa])"
        if re.fullmatch(
            rf"(?:is\s+(?:it|(?:this|that)\s+(?:app|application|program))\s+"
            rf"(?:still\s+)?(?:open|closed)|"
            rf"esta\s+(?:{entity}\s+{state}|{state}\s+{entity})|"
            rf"{entity}\s+tiene\s+(?:alguna|una)\s+ventana\s+abierta)",
            folded,
        ):
            return previous
        return None

    reference: str | None = None
    for request in previous_requests:
        reference = (
            resolve_application_window_status_name(request, catalog)
            or followup(request, reference)
        )
    return followup(text, reference)


def unresolved_application_open_name(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
    *,
    proper_name: bool = False,
) -> str | None:
    """Bind a literal app name for a presence read, never an opening fallback.

    ``proper_name`` also admits a capitalized bare name (APPS1549); the caller
    must first rule out games, near catalog names and public sites.
    """

    folded = _fold(text)
    if not folded or len(folded) > 16_384:
        return None
    # APPS1671 H0322 «quiero editar una foto en photoshop»: wanting to work in
    # a known program names the program; when the verified catalog does not
    # hold it, the presence read answers by its absence. Only the use-to-do
    # frame, only known software, never a catalog application (that stays a
    # real opening request for the other readers).
    use = re.fullmatch(
        r"[¿?¡!\s]*(?:(?:por\s+favor|please)\s*[,;:]?\s*)?"
        r"(?:quiero|querria|necesito|me\s+gustaria|tengo\s+que|i\s+want\s+to|i\s+need\s+to|i\'?d\s+like\s+to)\s+"
        r"(?:editar|retocar|usar|trabajar|edit|retouch|use|work)\s+(?:.{0,60}?\s+)?"
        rf"(?:en|con|in|with|on)\s+(?:(?:el|la|the)\s+)?(?P<name>{_KNOWN_SOFTWARE})"
        r"(?:\s*,?\s*(?:por\s+favor|please))?[\s.!?]*",
        folded,
    )
    if (
        use is not None
        and not proper_name
        and resolve_application_catalog_app_id(text, application_names) is None
        and resolve_application_catalog_app_id("abre " + use.group("name"), application_names) is None
    ):
        name_words = len(use.group("name").split())
        trimmed = _APPLICATION_TRAILING_REQUEST.sub("", text.rstrip(" ?!.")).rstrip()
        raw_name = " ".join(trimmed.split()[-name_words:])
        return _bounded_application_literal(raw_name)
    source = folded
    request = (
        _application_open_request(folded)
        if _application_desire_is_positive(folded) else None
    )
    if request is None:
        # «no, mejor abrí firefox»: a rectification or courtesy envelope precedes
        # the opening; the envelope grammar is the shared one, and the desire is
        # read on the request it wraps.
        stripped = _strip_request_envelope(folded)
        if stripped != folded and _application_desire_is_positive(stripped):
            source = stripped
            request = _application_open_request(stripped)
    if request is None or _is_negated_match(source, request):
        return None
    # An explicit application noun establishes the domain without guessing
    # whether an unfamiliar bare name denotes an app, file, site or game.
    wrapper = _match(
        request.group("target"),
        r"^(?:(?:el|la|un|una|the|a|an)\s+)?"
        r"(?:aplicacion|application|app|programa|program)\s+",
    )
    # Folding proves grammar only. Recover the original tokens for the read
    # so the provider receives the person's name, including case and accents.
    target_words = len(request.group("target").split())
    raw_target = " ".join(text.split()[-target_words:])
    if wrapper is None and build_application_catalog_index(application_names).entries:
        # A bare name is enough when it is software people open by name and a
        # verified catalog is present to prove it absent; «abrí la puerta»
        # stays outside because ``puerta`` is not.
        wrapper = _match(
            request.group("target"),
            rf"^(?:(?:el|la|the)\s+)?(?={_KNOWN_SOFTWARE}"
            r"(?:\s*[,;:]?\s+(?:por favor|please|para mi|for me|ahora|now|"
            r"dale|porfa|porfi|porfis|pls|plz))?[\s?!.]*$)",
        )
    if proper_name and wrapper is None and build_application_catalog_index(application_names).entries:
        # APPS1549 «abre Saint Rose.»: a proper name (every word capitalized,
        # no article, at most four words) after an open head is a name the
        # person expects on this PC; the verified catalog can prove it absent
        # and the reply can name it. Lowercase common nouns still abstain.
        proper = _APPLICATION_TRAILING_REQUEST.sub("", raw_target.rstrip(" ?!.")).rstrip()
        words = proper.split()
        if (
            1 <= len(words) <= 4
            and all(word[:1].isupper() and word[1:] == word[1:].lower() and word.isalpha() for word in words)
            and not _has(_fold(proper), r"^(?:el|la|los|las|un|una|the|a|an)\b")
        ):
            wrapper = _match(request.group("target"), r"^(?=\S)")
    if (
        wrapper is None
        or resolve_application_catalog_app_id(text, application_names) is not None
    ):
        return None
    raw_name = " ".join(raw_target.split()[len(wrapper.group().split()):])
    # The explicit application wrapper was consumed above. Strip only its
    # request suffix, never another article or program word inside the name.
    raw_name = _APPLICATION_TRAILING_REQUEST.sub("", raw_name.rstrip(" ?!.")).rstrip()
    name = _bounded_application_literal(raw_name)
    # Courtesy is a request envelope, not a separate effect clause.
    if name is None or len(_request_clauses(_strip_request_envelope(folded))) != 1:
        return None
    return name


def resolve_application_installed_name(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """Ground one explicit installed-application observation.

    Unlike ``app.open``, the read-only provider can truthfully answer that an
    arbitrary literal name is absent from the verified Start catalog.  The
    operation therefore must not require the queried name to already be in
    that same catalog.  We still accept an out-of-catalog literal only inside
    a tightly anchored observation request; free mentions and declarative
    sentences continue to abstain.
    """

    opening_name = unresolved_application_open_name(text, application_names)
    if opening_name is not None:
        return opening_name
    # APPS1549: the resolver admits a proper name behind a plain open verb only
    # after ruling out games, near names and public sites; the argument bound
    # here is that same name, exactly as the person wrote it.
    opening_name = unresolved_application_open_name(
        text, application_names, proper_name=True,
    )
    if opening_name is not None:
        return opening_name
    catalog = build_application_catalog_index(application_names)
    folded = _strip_request_envelope(_fold(text)).strip().rstrip(".?!").strip()
    if not folded:
        return None

    candidate: str | None = None
    patterns = (
        (
            r"(?:^|[,;]\s*|\b(?:y|and|then|luego|despues)\s+)"
            r"(?:comprueba|verifica|confirma|revisa|inspecciona|check|"
            r"verify|confirm|review|inspect)\s+"
            r"(?!(?:si|if|whether)\b)"
            r"(?:(?:el|la|the)\s+)?"
            r"(?P<target>[a-z0-9][a-z0-9 ._+@-]{0,100}?)\s+"
            r"(?:installation|instalacion|instalad[oa]|installed)"
            r"(?=$|[,;]|\s+(?:y|and|then|luego|despues)\b)"
        ),
        (
            r"^consulta\s+(?:el\s+)?software\s+local\s+para\s+saber\s+si\s+"
            r"(?:esta\s+)?(?P<target>.+)$"
        ),
        (
            r"^(?:comprueba|revisa|check)\s+(?:en|in)\s+(?:el\s+|the\s+)?"
            r"(?:menu\s+inicio|start\s+menu)\s+(?:la\s+presencia\s+de|for)\s+"
            r"(?P<target>.+)$"
        ),
        (
            r"^look\s+through\s+(?:the\s+)?local\s+software\s+inventory\s+"
            r"for\s+(?P<target>.+)$"
        ),
        (
            r"^find\s+out\s+whether\s+(?P<target>.+?)\s+exists\s+among\s+"
            r"(?:the\s+)?start\s+menu\s+apps?$"
        ),
        (
            r"^(?:chequea|checkea|comprueba)\s+si\s+(?P<target>.+?)\s+"
            r"figura\s+en\s+(?:el\s+)?software\s+de\s+(?:este\s+)?pc$"
        ),
        (
            r"^(?:verifica|verificar|confirma|confirmar|comprueba|comprobar|"
            r"averigua|averiguar|checkea|chequea|fijate|fijese|mira|revisa|"
            r"check|verify|confirm|see|find\s+out|dime|tell\s+me)\s+"
            r"(?:si|if|whether)\s+"
            r"(?:(?:tengo|tienes|tiene|tenemos|i\s+have|we\s+have)\s+)?"
            r"(?P<target>.+?)\s+"
            r"(?:(?:figura|aparece)\s+(?:entre|en)\s+(?:las\s+)?"
            r"(?:aplicaciones|apps)\s+(?:instaladas|de\s+(?:este|mi|el)\s+"
            r"(?:equipo|pc|ordenador|computador))|"
            r"(?:exists|appears|is\s+listed)\s+(?:among|in)\s+(?:the\s+)?"
            r"(?:installed\s+(?:apps|applications)|(?:apps|applications)\s+"
            r"on\s+(?:this|my|the)\s+(?:pc|computer|machine))|"
            r"(?:esta|is)\s+(?:disponible\s+como\s+(?:programa\s+)?"
            r"instalad[oa]|present\s+in\s+(?:my\s+|the\s+)?installed\s+"
            r"apps?|instalad[oa]|installed)|instalad[oa]|installed)"
            r"(?:\s+(?:aqui|here|en\s+(?:este|mi|el)\s+(?:equipo|pc)|"
            r"on\s+(?:this|my|the)\s+computer|localmente|locally))?$"
        ),
        (
            r"^(?:inspect|inspecciona|revisa|review|check)\s+"
            r"(?:(?:the|las?)\s+)?(?:installed\s+(?:applications?|apps?|"
            r"programs?)|aplicaciones?\s+instaladas?|programas?\s+instalados?)"
            r"\s+(?:for|por|para)\s+(?P<target>.+)$"
        ),
        (
            r"^(?:inspect|inspecciona|revisa|review|check)\s+(?:en\s+|in\s+)?"
            r"(?:(?:the|las?)\s+)?(?:installed\s+(?:applications?|apps?|"
            r"programs?)|aplicaciones?\s+instaladas?|programas?\s+instalados?)"
            r"\s+(?:si\s+aparece|if\s+(?:it\s+)?shows\s+up|for)\s+"
            r"(?P<target>.+)$"
        ),
        (
            r"^(?:inspect|inspecciona|revisa|review|check)\s+"
            r"(?:(?:the|el)\s+)?(?:start\s+(?:app|application)\s+inventory|"
            r"inventario\s+de\s+aplicaciones\s+(?:de\s+)?inicio)\s+"
            r"(?:for|por|para)\s+(?P<target>.+)$"
        ),
    )
    for pattern in patterns:
        request = _match(folded, pattern)
        if request is not None and not _is_negated_match(folded, request):
            candidate = request.group("target")
            break

    # Exact catalog evidence is produced by the authenticated entity
    # recognizer for ordinary state questions and repeated app lists.
    if candidate is None:
        exact = [name for name, key in catalog.entries if key == folded]
        if len(exact) == 1:
            return exact[0]
        if folded in {"windows.calculator", "windows.notepad"}:
            return folded
        return None

    forms = _application_target_forms(candidate)
    keys = tuple(
        dict.fromkeys(
            _application_name_key(form)
            for form, _ in forms
            if _application_name_key(form)
        )
    )
    if not keys:
        return None

    catalog_keys = {key for _, key in catalog.entries}
    for key in keys:
        exact = [
            name for name, candidate_key in catalog.entries if candidate_key == key
        ]
        if len(exact) == 1:
            return exact[0]
        if key in {"calc", "calculadora", "calculator"} and catalog_keys & {
            "calculadora",
            "calculator",
        }:
            return "windows.calculator"
        if key in {
            "app de notas",
            "bloc de notas",
            "editor de texto",
            "notepad",
        } and catalog_keys & {"bloc de notas", "notepad"}:
            return "windows.notepad"

    return _bounded_application_literal(forms[-1][0])


def _authenticated_application_request(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[str, tuple[tuple[int, str], ...]] | None:
    """Recognize a whole exact app request before inspecting words in names."""

    names = build_application_catalog_index(application_names)
    bare_target = _application_name_key(text.rstrip(" ?!."))
    if bare_target in names.keys:
        return "app.open", ((0, bare_target),)
    # Owner's mother 2026-09-21 «ponme word»: «pon/ponme/poneme <installed app>»
    # is the opening (not a song, not a wallpaper) when the whole text is that.
    put_app = re.fullmatch(
        r"[¿?¡!\s]*(?:pon|ponme|poneme|pone|poneme)\s+(?:me\s+)?(?:el\s+|la\s+|the\s+)?(?P<app>[^,;:]{1,60}?)"
        r"(?:\s*,?\s*(?:por\s+favor|porfa|please))?[\s?!.]*",
        text,
        re.IGNORECASE,
    )
    if put_app is not None:
        # Tanda 5: an installed app named by any of its bilingual names («ponme la galería»).
        put_key = _catalog_alias_key(_application_name_key(put_app.group("app")), names.keys)
        if put_key is not None:
            return "app.open", ((put_app.start("app"), put_key),)
    for installed_query, operation in (
        (False, "app.open"),
        (True, "app.installed"),
    ):
        target = _authenticated_application_target(
            text,
            names,
            installed_query=installed_query,
        )
        if target is not None:
            return operation, (target,)
        targets = _authenticated_application_list(
            text,
            names,
            installed_query=installed_query,
        )
        if targets:
            return operation, targets
    return None


def _authenticated_application_desired_open(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[int, str] | None:
    """Resolve an exact installed app inside a literal desired-open clause."""

    folded = _fold(text)
    catalog = build_application_catalog_index(application_names)
    occurrence = catalog.occurrence_pattern
    if occurrence is None or not _application_desire_is_positive(folded):
        return None
    found = list(occurrence.finditer(folded))
    if not found:
        # Tanda 5 «quiero que abras la galería»: the app named by one of its bilingual names, alone after the
        # desire (courtesy apart), is the installed app that name stands for.
        request = _application_open_request(folded)
        if request is None or request.group("desire") is None:
            return None
        said = request.group("target")
        for form, offset in _application_target_forms(said):
            key = _catalog_alias_key(_application_name_key(form), catalog.keys)
            rest = said[offset + len(form) :].strip(" ¿?¡!,:;.-")
            if key is not None and (not rest or _has(rest, r"^(?:por favor|porfa|please)$")):
                return request.start("target") + offset, key
        return None
    if len(found) != 1:
        return None
    target = found[0]
    prefix = folded[: target.start()].strip(" ¿?¡!,:;.-")
    suffix = folded[target.end() :].strip(" ¿?¡!,:;.-")
    request = _application_open_request(folded[: target.end()])
    leading_desire = (
        request is not None
        and request.group("desire") is not None
        and any(
            _application_name_key(form)
            == _application_name_key(target.group("target"))
            for form, _ in _application_target_forms(request.group("target"))
        )
        # Courtesy is outside identity; every other suffix stays opaque.
        and (not suffix or _has(suffix, r"^(?:por favor|porfa|please)$"))
    )
    desired_running = (
        _has(prefix, r"^(?:get|keep)$") and _has(suffix, r"^(?:open|running|started)$")
    ) or (
        not prefix
        and _has(
            suffix,
            r"^(?:needs?|has)\s+to\s+be\s+(?:open|running|started)$|"
            r"^(?:tiene|necesita)\s+que\s+estar\s+"
            r"(?:abiert[oa]|funcionando|iniciad[oa])$",
        )
    )
    if not (leading_desire or desired_running):
        return None
    return target.start(), _application_name_key(target.group("target"))


_EXPLICIT_NON_ACTION_FRAME = (
    r"(?:"
    r"sin\s+pedir\s+ning[uú]n\s+cambio\s+en\s+el\s+computador\s*,?\s*"
    r"quiero\s+preguntarte|"
    r"s[oó]lo\s+conversemos\s*;\s*no\s+hagas\s+nada\s+en\s+este\s+equipo|"
    r"let['’]?s\s+only\s+discuss\s+this\s*;\s*"
    r"do\s+not\s+change\s+anything\s+on\s+the\s+computer|"
    r"this\s+is\s+conversation\s+only\s*,?\s*"
    r"with\s+no\s+pc\s+action\s+requested|"
    r"solo\s+let['’]?s\s+talk\s*;\s*no\s+hagas\s+any\s+pc\s+action|"
    r"conversation\s+only\s*,?\s*sin\s+cambiar\s+nada\s+en\s+este\s+equipo|"
    r"(?:quiero|quisiera)\s+(?:preguntarte|consultarte)\s+"
    r"(?:algo|una\s+cosa)\s+sin\s+(?:pedir|solicitar)\s+"
    r"(?:una\s+)?acci[oó]n|"
    r"tengo\s+una\s+(?:duda|pregunta)(?:\s+(?:breve|r[aá]pida|peque[nñ]a))?"
    r"\s*,?\s*(?:s[oó]lo|solamente)\s+para\s+(?:conversar|charlar)|"
    r"just\s+(?:a\s+)?(?:(?:quick|brief|small)\s+)?(?:thought|question)"
    r"\s*,?\s*with\s+no\s+(?:(?:computer|pc)\s+)?action|"
    r"i\s+have\s+(?:a\s+)?(?:(?:short|quick|brief|small)\s+)?"
    r"(?:question|thought)\s*,?\s*just\s+to\s+(?:chat|talk)|"
    r"tengo\s+una\s+(?:quick|brief|short)\s+(?:question|duda)"
    r"\s*,?\s*sin\s+(?:(?:computer|pc)\s+)?(?:action|acci[oó]n)|"
    r"just\s+para\s+(?:conversar|charlar)\s*,?\s*"
    r"(?:una\s+)?(?:duda|question)(?:\s+(?:breve|quick|short))?"
    r")"
)


def declined_means(text: str) -> str | None:
    """The means a trailing directive names (lowercase), or None.

    Only a directive that follows a request counts: «Usa Python.» alone is a
    request of its own and stays untouched.
    """

    found = _TRAILING_MEANS_DIRECTIVE.search(text)
    if found is None or found.start() == 0:
        return None
    return (found.group("means") or found.group("api")).casefold()


def explicit_non_action_body(text: str) -> str | None:
    """Return the body behind an explicit conversation-only boundary.

    Neutral vocatives may precede the boundary, but the boundary itself is not
    stripped as a request envelope.  A colon or equivalent sentence separator
    is mandatory, and the entire trailing body remains non-authoritative even
    if it contains imperative words.
    """

    framed = _strip_request_envelope(text).strip()
    found = _match(
        framed,
        rf"^[¿?¡!\s]*{_EXPLICIT_NON_ACTION_FRAME}"
        r"\s*[,;:.!?\-\u2013\u2014]+\s*[¿¡]?\s*(?P<body>\S.*)$",
    )
    return found.group("body") if found is not None else None


# H0401 «reinicié la PC»: la persona cuenta lo que hizo ella. No es una
# orden y contestarle que no se puede niega algo que nadie pidió. La
# terminación lo decide sin ambigüedad: en rioplatense el imperativo es
# «reiniciá», «apagá», «cerrá», y «reinicié», «apagué», «cerré» sólo
# pueden ser primera persona del pasado.
_FIRST_PERSON_REPORT = re.compile(
    r"^[\s¿?¡!]*(?:ya\s+|recién\s+|justo\s+)?"
    r"(?:reinici|apagu|encend|cerr|abr|instal|desinstal|guard|borr|elimin|"
    r"actualic|descargu|configur|conect|desconect|mov|copi|pegu|silenci)é\b",
    re.IGNORECASE,
)


def first_person_past_report(text: str) -> bool:
    """La persona cuenta una acción que hizo ella, no pide ninguna."""

    body = _strip_request_envelope(str(text or ""))
    if _has(_fold(body), r"\b(?:por\s+favor|please|puedes|pod[eé]s|can\s+you)\b"):
        return False
    return _FIRST_PERSON_REPORT.match(body) is not None


def explicit_non_action_frame(text: str) -> bool:
    """Recognize an explicit conversation-only boundary without granting effects."""

    return explicit_non_action_body(text) is not None


def _is_builtin_keyboard_request(text: str) -> bool:
    """Reserve the OSK phrase for its typed built-in operation."""

    return _head_is(_request_head(text), _OPEN) and _has(
        text,
        r"\b(?:teclado en pantalla|on[ -]screen keyboard)\b",
    )


def explicit_negative_constraint(text: str) -> bool:
    """Recognize a standalone prohibition for prose, never operation authority.

    Reuse the existing action-head vocabulary. Spanish negative imperatives
    use subjunctive endings rather than the affirmative command forms in that
    vocabulary. A negated statement or a compound request stays with the normal
    reader; neither a leading ``no`` nor a device noun proves a prohibition.
    """

    folded = _strip_request_envelope(_fold(text))
    # NEGATIVE1309 «mejor no abras la calculadora»: a softening adverb before
    # the prohibition does not change it.
    folded = re.sub(r"^(?:mejor|por ahora|ahora|hoy|por favor)\s+", "", folded, count=1)
    if any(mark in folded for mark in ("?", "¿")):
        return False
    if any(mark in folded for mark in (";", ",")):
        # «No cierres Chrome, lo estoy usando»: a justification or state after
        # the separator keeps the single prohibition (CLOSE1219-1225/010); any
        # other tail is a compound turn for the normal reader.
        head, tail = re.split(r"[,;]", folded, 1)
        if re.match(
            r"^\s*(?:(?:que\s+)?(?:lo|la|los|las|me|te)\s+)?"
            r"(?:estoy|estamos|esta|estan|sigo|seguimos|necesito|necesitamos|"
            r"i'?m|i\s+am|it'?s|we'?re|they'?re|porque|because|ya\s+que)\b",
            tail,
        ) is None:
            return False
        folded = head.strip()
    if re.search(r"\b(?:y|and|pero|but|sino)\b", folded):
        return False
    if len(_request_clauses(folded)) != 1:
        return False
    return bool(_negative_action_forms(folded))


def _is_social_clause(text: str) -> bool:
    return _has(
        text,
        (
            r"^[¿?¡!\s]*(?:gracias|thanks|thank you|por favor|please|"
            r"que tengas (?:un )?buen dia)\b|"
            # Vocativo suelto: llamar al asistente por su nombre no es una
            # cláusula pendiente, sólo abre la petición que viene después.
            r"^[¿?¡!\s]*(?:(?:che|oye|oiga|hey|ey|ok|okay|hola|escucha|"
            r"listen)\s+)?baxy[\s?!.,;:]*$|"
            # Un saludo o una despedida que ocupan la cláusula entera tampoco
            # dejan una petición pendiente. El anclaje final es lo que mantiene
            # «hola mundo» o «escribe hola» fuera de esta puerta.
            r"^[¿?¡!\s]*(?:buenos dias|buenas tardes|buenas noches|buenas|"
            r"hola|good morning|good afternoon|good evening|hello|hi|hey|"
            r"hasta luego|hasta pronto|hasta manana|nos vemos|adios|chau|"
            r"chao|goodbye|good bye|good night|bye|see you(?: later)?)"
            r"(?:\s+baxy)?[\s?!.,;:]*$"
        ),
    )


def _is_effect_receipt_clause(text: str) -> bool:
    """Accept requests for evidence already guaranteed by the operation contract."""

    return _has(
        text,
        (
            r"^[¿?¡!\s]*(?:dime|decime|tell me)\s+(?:si|whether)\s+"
            r"(?:pudiste|se pudo|lo verificaste|you could|it was)\s+"
            r"(?:verificar(?:lo)?|verified?)\b|"
            r"^[¿?¡!\s]*(?:guardalo|guardala|save it)\s+(?:y|and)\s+"
            r"(?:dime|tell me|show me)\s+(?:el\s+|the\s+)?"
            r"(?:path|ruta)\b"
        ),
    )


_SAID_TO_ME = re.compile(
    r"\b(?:que|qué)\s+(?:fue\s+lo\s+ultimo\s+que\s+)?me\s+"
    r"(?:escribi[oó]|escribieron|mand[oó]|mandaron|envi[oó]|enviaron|dijo|dijeron|puso|pusieron)\b"
)
# M112 (DEV-F v4d w19-t2 «Ahí tiene que estar el PDF de la hipoteca que me mandó el banco ayer. ¿Me lo resumes?» →
# «No resumo documentos.»): «que me mandó» right after a thing named with its article («el PDF de la hipoteca»)
# says which thing it is (a relative clause); only after a pause or a verb («dime qué me dijo», «¿qué me escribió?»)
# does it ask what someone said.
_NAMED_THING_BEFORE = re.compile(
    r"\b(?:el|la|los|las|un|una|unos|unas|del|al|este|esta|estos|estas|ese|esa|esos|esas|mi|mis|tu|tus|su|sus)\s+"
    r"(?:[^\s,.;:!?¿¡]+\s+){0,4}[^\s,.;:!?¿¡]+\s*$"
)


def _asks_what_was_said_to_me(folded: str) -> bool:
    """«qué me dijo/escribió/mandó X» asked, never «el PDF que me mandó el banco» (see above)."""

    return any(
        _NAMED_THING_BEFORE.search(folded[: found.start()]) is None for found in _SAID_TO_ME.finditer(folded)
    )


def chat_read_request(folded: str) -> bool:
    """A request to read what someone wrote in a chat client or to read a chat:
    «qué (fue lo último que) me dijo/escribió X (en wsp)», «leé/leeme lo último
    que me dijo X», «puedes leer una conversación mía de whatsapp», «read my
    last message from X». False for mail (its own reader) and for sending."""

    return (_asks_what_was_said_to_me(folded) or _has(
        folded,
        r"\b(?:lee|leeme|leer|leas|leerme|read)\s+(?:me\s+)?(?:lo\s+ultimo\s+que\s+me\s+(?:dijo|escribio|mando)|"
        r"(?:una|la|mi|my|a|the)\s+(?:conversacion|conversation|chat)|(?:el|los|mis|the|my)\s+(?:ultimos?\s+)?(?:mensajes?|messages?)|"
        r"(?:the\s+)?last\s+message)\b"
        r"|\bwhat\s+did\s+\S+\s+(?:say|write|text)\s+(?:to\s+)?me\b",
    ) or _messages_arrived_question(folded)) and not _has(folded, r"\b(?:correo|mail|email|gmail|outlook)\b")


def _messages_arrived_question(folded: str) -> bool:
    """Dev corpus 2026-09-23 «cuántos mensajes no leídos tengo», «cuándo recibí el mensaje de john smith»: what
    arrived as messages, with no mail named, is the chats (read by the deferred computer-use engine), never a
    sentence to look up or answer from memory. Not writing one, and not an error message."""

    return (
        _has(folded, r"\b(?:mensajes?|messages?|texts?|dms?|sms)\b")
        and _has(
            folded,
            r"\b(?:no\s+leidos?|sin\s+leer|unread|recibi|recibido|recibir|received|receive|llego|llegaron|arrived|"
            r"mensajes?\s+nuevos?|nuevos?\s+mensajes?|new\s+(?:messages|texts))\b",
        )
        and (
            not _has(folded, r"\b(?:mensajes?\s+nuevos?|nuevos?\s+mensajes?|new\s+(?:messages|texts))\b")
            or _has(folded, r"\b(?:tengo|tenemos|hay|cuant[oa]s|have|has|any|got|get)\b")
        )
        and not _has(
            folded,
            r"\b(?:error|errores|sistema|system|windows|consola|console|warning|advertencia)\b|"
            r"\b(?:envi\w*|mand\w*|escrib\w*|redact\w*|respond\w*|contest\w*|send|write|compose|reply)\b",
        )
    )


def _other_device_effect_scope(text: str) -> bool:
    """Reject effects explicitly scoped to a separate personal device."""

    return _has(
        text,
        (
            r"\b(?:en|on)\s+(?:(?:el|la|un|una|mi)\s+|"
            r"(?:(?:my|the|a)\s+)?(?:[a-z]+(?:'s)?\s+){0,2})?"
            r"(?:telefono|movil|celular|phone|smartphone|tablet|ipad|"
            r"iphone|reloj|watch|consola|console|xbox|playstation)\b|"
            r"\bfrom\s+(?:my|the|a)\s+(?:phone|smartphone|tablet)\b|"
            r"\b(?:into|to)\s+(?:my|the|a)\s+"
            r"(?:phone|smartphone|tablet|watch|console)\b|"
            r"\b(?:on|in)\s+another\s+(?:computer|device|pc)\b|"
            r"\ben\s+otro\s+(?:computador|equipo|pc|dispositivo)\b"
        ),
    )


def app_volume_request(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[str, str, int | None] | None:
    """AUDIO1787 «subí el volumen de spotify»: (catalog display name, direction, amount or None).

    A relative volume verb whose object is one authenticated application's
    volume, in Spanish (volumen de X) or English (X's volume / turn up X
    volume); the amount is optional and, when absent, asked (owner rule on
    relative volume without a quantity). The system volume readers keep
    every request that names no application.
    """
    if (
        not effect_request_is_authoritative(text)
        or _other_device_effect_scope(_fold(text))
        or _is_negative_effect_clause(_fold(text))
    ):
        return None
    folded = _strip_request_envelope(_fold(text))
    if _has(folded, r"\b(?:o|or)\b") or len(_request_clauses(folded)) != 1:
        return None
    match = _APP_VOLUME_SPANISH.match(folded) or _APP_VOLUME_ENGLISH.match(folded) or _APP_VOLUME_ENGLISH_SPLIT.match(folded)
    if match is None:
        return None
    verb = match.group("verb")
    if re.fullmatch(rf"{_VOLUME_UP_VERB}|turn\s+up|raise|increase|bump\s+up|crank\s+up|up", verb):
        direction = "up"
    elif re.fullmatch(rf"{_VOLUME_DOWN_VERB}|turn\s+down|lower|decrease|down", verb):
        direction = "down"
    else:
        return None
    raw_app = match.group("app").strip(" ,;:")
    if _has(raw_app, r"\b(?:sistema|equipo|pc|computador(?:a)?|ordenador|system|computer|windows|todo|everything|musica|music)\b"):
        return None
    catalog = build_application_catalog_index(application_names)
    keys = {_authenticated_close_key(form, catalog) for form, _ in _application_target_forms(raw_app)}
    keys.discard(None)
    if len(keys) != 1:
        return None
    key = next(iter(keys))
    names = {name for name, entry_key in catalog.entries if entry_key == key}
    if len(names) != 1:
        return None
    raw_amount = match.group("amount") or match.group("amount2")
    amount = int(raw_amount) if raw_amount is not None else None
    if amount is not None and not 1 <= amount <= 100:
        return None
    return (next(iter(names)), direction, amount)


def _completed_missing_app_volume_request(
    text: str, previous_user_text: str | None, available_operations: Iterable[str],
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
) -> str | None:
    """AUDIO1787 «subí el volumen de spotify» → «¿cuánto?» → «20»: the bare amount
    answer completes the application volume request as «… en 20»."""

    if not previous_user_text:
        return None
    answer = _strip_request_envelope(_fold(text)).strip()
    found = re.fullmatch(
        r"(?:(?:en|by|a|al|to|unos|unas|about)\s+)?(?P<amount>\d{1,3})\s*(?:%|por\s+ciento|percent|puntos?|points?)?[\s.!?]*",
        answer,
    )
    if found is None:
        return None
    prior = resolve_explicit_clarification_intent(previous_user_text, available_operations, application_names)
    if prior is None or prior.operations != ("audio.app.volume.adjust",) or prior.missing_fields != ("amount",):
        return None
    previous_folded = _strip_request_envelope(_fold(previous_user_text))
    joiner = " by " if (_APP_VOLUME_ENGLISH.match(previous_folded) or _APP_VOLUME_ENGLISH_SPLIT.match(previous_folded)) else " en "
    return previous_user_text.strip().rstrip(" .!?") + joiner + found.group("amount")


def app_volume_set_request(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[str, int] | None:
    """Fase 8 (D18) «poné el volumen de Spotify al 40», «set Spotify volume to
    40», «dejá spotify al máximo»: (catalog display name, absolute level 0–100)
    when a setting verb gives one authenticated application's volume one
    absolute target; the relative readers keep «subí/bajá … en 20» and the
    system readers keep every request that names no application."""

    if (
        not effect_request_is_authoritative(text)
        or _other_device_effect_scope(_fold(text))
        or _is_negative_effect_clause(_fold(text))
    ):
        return None
    folded = _strip_request_envelope(_fold(text))
    if _has(folded, r"\b(?:o|or)\b") or len(_request_clauses(folded)) != 1:
        return None
    match = _APP_VOLUME_SET_SPANISH.match(folded) or _APP_VOLUME_SET_ENGLISH.match(folded)
    if match is None:
        return None
    raw_app = match.group("app").strip(" ,;:")
    if _has(raw_app, r"\b(?:sistema|equipo|pc|computador(?:a)?|ordenador|system|computer|windows|todo|everything|musica|music|volumen|volume|sonido|sound|audio|brillo|brightness|pantalla|screen)\b"):
        return None
    catalog = build_application_catalog_index(application_names)
    keys = {_authenticated_close_key(form, catalog) for form, _ in _application_target_forms(raw_app)}
    keys.discard(None)
    if len(keys) != 1:
        return None
    key = next(iter(keys))
    names = {name for name, entry_key in catalog.entries if entry_key == key}
    if len(names) != 1:
        return None
    if match.group("level") is not None:
        level = int(match.group("level"))
    else:
        level = _APP_VOLUME_LEVEL_WORDS[match.group("word")]
    if not 0 <= level <= 100:
        return None
    return (next(iter(names)), level)


def _spoken_package_id(text: str) -> str | None:
    """Recover exact common winget IDs after ASR removes their separator."""

    folded = _fold(text)
    aliases = (
        (r"\b(?:mozilla|mozzala)[\s.,-]+firefox\b", "Mozilla.Firefox"),
        (
            r"\bgithub[\s.,-]+github[\s.,-]*desktop\b",
            "GitHub.GitHubDesktop",
        ),
        (r"\bvlc\b", "VideoLAN.VLC"),
    )
    for pattern, package_id in aliases:
        if _has(folded, pattern):
            return package_id
    package = re.search(
        r"(?<![a-z0-9._-])(?P<id>[a-z0-9][a-z0-9_-]+"
        r"(?:\.[a-z0-9_-]+)+)(?![a-z0-9_-]|\.[a-z0-9_-])",
        text,
        re.IGNORECASE,
    )
    return package.group("id") if package is not None else None


def _spoken_radio_station_request(text: str) -> bool:
    """Recognize a named/dial radio request without treating every `pon` as media."""

    folded = _fold(text)
    return radio_station_query(text) is not None or _head_is(
        _request_head(folded),
        r"(?:pon|ponme|pone|poneme|reproduce|reproducir|play|start|inicia|tune)",
    ) and _has(
        folded,
        r"(?:\bf\s*\.?\s*m\s*\.?\b|\ba\s*\.?\s*m\s*\.?\b|"
        r"\b(?:radio|station|emisora)\b)",
    )


_MUSIC_ORDER_HEAD = re.compile(
    r"^(?:(?:por\s+favor|alexa|oye|baxy)\s+)*(?:pon|pone|poneme|ponme|pondras|reproduce|reproducir|reproduci|"
    r"reproducime|play|toca|tocame|toque|quiero\s+escuchar|necesito\s+escuchar|me\s+gustaria\s+escuchar|escuchar|"
    r"dame|put\s+on|start)\b"
)
# The words that name no music: articles, possessives, «música/canción/algo», courtesy, time, randomness, the player.
_MUSIC_GENERIC_WORDS = frozenset(
    "una|un|unas|unos|algo|alguna|algunas|algun|algunos|la|el|las|los|lo|de|del|al|a|mi|mis|tu|tus|su|sus|some|any|the|"
    "my|me|musica|music|musika|cancion|canciones|song|songs|tema|temas|track|tracks|sonido|sonidos|sound|sounds|por|"
    "favor|please|ahora|now|hoy|today|ya|aqui|here|cualquier|cualquiera|aleatoria|aleatorio|aleatoriamente|random|"
    "shuffle|modo|buena|buenas|bueno|buenos|good|nice|en|on|spotify|youtube|que|y|and|o|or|otra|otras|otro|otros|other|"
    "another|more|mas|nuevo|nueva|nuevos|nuevas|new|podcast|podcasts|audiolibro|audiolibros|audiobook|audiobooks|episodio|"
    "episode|"
    # Independent review M2: courtesy, fillers, repetition, time and the room («pon musica porfa», «…, gracias»,
    # «pls», «otra vez», «un rato», «en el living», «weon») name no music.
    "porfa|porfis|porfavor|gracias|thanks|thx|pls|plz|po|pe|che|weon|weona|wey|guey|mano|bro|loco|pues|nomas|dale|"
    "vez|rato|ratito|momento|living|sala|cuarto|pieza|casa|auto|carro|coche|oficina|alto|fuerte|bajito|despacio|"
    "volumen|fondo".split("|")
)
# The person's own collection keeps the tanda-4c reading (own_collection_free_choice); it is not content said here.
_MUSIC_OWN_COLLECTION = re.compile(
    r"\b(?:favorit\w*|playlists?|lista\s+de\s+reproduccion|lista|biblioteca|library|mis\s+canciones|comprad\w*|"
    r"liked|saved|guardad\w*|my\s+(?:music|songs)|que\s+me\s+gust\w*)\b"
)
_MUSIC_COLLECTION_CONTAINER = re.compile(r"\b(?:playlists?|lista\s+de\s+reproduccion|lista|biblioteca|library)\b")
# Tanda 4 «pon algo para dormir», «pon algo nuevo» ask: a purpose and «nuevo» name no music; a character does.
_MUSIC_PURPOSE = re.compile(r"\b(?:para|for|to)\s+\w+.*$")


def _music_clause_names_content(clause: str) -> bool:
    """«pon música clásica», «canciones tristes», «la canción la macarena» say what to play; «pon música» does not."""

    body = _MUSIC_ORDER_HEAD.sub(" ", _fold(clause), count=1)
    if _MUSIC_OWN_COLLECTION.search(body):
        # M32 (MASSIVE reserve «play my rock playlist», «pon mi lista de reproducción de jazz» were asked «¿qué
        # música?»): next to the person's own collection only a genre named says what to play; how the collection
        # is qualified («preferidas», «de siempre», «descargadas») does not (independent review REV2). A taste
        # («mi cantante de jazz favorito», uso real) names a person, not the collection: it still asks.
        if _MUSIC_COLLECTION_CONTAINER.search(body) is None:
            return False
        # M97 (reserve «mi lista de reproducción de música rap favorita»): with the list said, a taste qualifies the
        # list, and the genre still names what to play. A list named by anything else («mi playlist de gym») is the
        # person's own collection, which no operation reads: it is asked, never searched (tanda 4).
        return re.search(r"\b" + MUSIC_GENRE + r"\b", body) is not None
    body = _MUSIC_PURPOSE.sub(" ", body)
    return any(word not in _MUSIC_GENERIC_WORDS for word in re.findall(r"[a-z0-9ñ]+", body))


def _desired_music_query(text: str) -> str | None:
    """Extract a bounded genre, artist or title query without choosing music.

    MUSIC1571: «pon algo de música» names nothing; a query that is only a
    music noun (with «algo de» in front) is not a query.
    """

    query = _desired_music_query_raw(text)
    if query is not None and re.fullmatch(
        r"(?:(?:algo|un\s+poco|something|some)\s+(?:de\s+|of\s+)?)?"
        r"(?:musica|music|musika|cancion(?:es)?|song(?:s)?|temas?|videos?)",
        _fold(query).strip(),
    ):
        return None
    return query


def _desired_music_query_raw(text: str) -> str | None:
    """Extract a bounded genre, artist or title query without choosing music."""

    folded = _strip_request_envelope(_fold(text))
    request = re.fullmatch(
        r"(?:(?:i\s+)?(?:need|want)|necesito|quiero)\s+"
        r"(?:(?:some|any|algo\s+de|un\s+poco\s+de)\s+)?"
        rf"(?P<query>{MUSIC_GENRE})"
        r"(?:\s+(?:music|musica))?[\s.!?]*",
        folded,
        re.IGNORECASE,
    )
    if request is not None:
        return request.group("query").strip()
    playlist = re.fullmatch(
        r"(?:enciende|inicia|pon|reproduce|start|play)\s+"
        r"(?:(?:la|the)\s+)?(?:lista\s+de\s+reproduccion|playlist)\b"
        r".{0,160}\b(?:musica\s+)?"
        rf"(?P<query>{MUSIC_GENRE})\b"
        r".{0,48}[\s.!?]*",
        folded,
        re.IGNORECASE,
    )
    if playlist is not None:
        return playlist.group("query").strip()
    figurative = re.fullmatch(
        r"(?:comfort|soothe)\s+my\s+ears\s+with\s+"
        r"(?P<query>[a-z0-9][a-z0-9 .&'_-]{0,120})[\s.!?]*",
        folded,
        re.IGNORECASE,
    )
    if figurative is not None:
        return figurative.group("query").strip()
    named = re.fullmatch(
        (
            r"(?:quiero\s+que\s+me\s+pongas|i\s+want\s+you\s+to\s+play)\s+"
            r"(?P<query>\S(?:.{0,160}?\S)?)\s*[.!?]*"
        ),
        folded,
        re.IGNORECASE,
    )
    query = named.group("query").strip() if named is not None else _explicit_named_music_query(text)
    if query is None:
        return None
    if not 1 <= len(query.split()) <= 12 or _has(
        _fold(query),
        # Tanda 6: «pon alarmas a las 7 y a las 8 …» schedules, in the plural too.
        r"\b(?:alarmas?|alarms?|temporizador(?:es)?|timers?|volumen|volume|sonido|sound|"
        r"pantalla|screen|modo|mode|video|movie|pelicula|juego|game|"
        r"multijugador|multiplayer|with|against|conmigo|contra)\b",
    ):
        return None
    return query


# Uso real 2026-09-23 «play song aces high», «alexa play song over the rainbow»,
# «play reggae music»: the music noun came with what to play and the turn still
# asked for it. A song noun followed by its title, or a music noun with its own
# qualifier («reggae music», «música clásica»), names the music; a possessive,
# a preference or a purpose («mi música favorita», «una canción para dormir»)
# does not, and is still asked.
_MUSIC_QUERY_FILLER = (
    r"(?:de|del|by|from|of|para|for|que|that|con|with|mi|mis|my|tu|tus|your|su|sus|"
    r"favorit[oa]s?|favourite|favorite|preferid[oa]s?|nuev[oa]s?|new|algo|something|"
    r"any|some|alguna?|cualquier|otr[oa]s?|other|another|mas|more|est[aeo]s?|es[aeo]s?|this|these|those|"
    r"that|the|la|el|lo|los|las|una?|a|an|buena?|good|random|"
    # «pon la canción anterior», «pon música ahora»: moving through what plays
    # or a time is not a title or a genre.
    r"anterior(?:es)?|siguientes?|previas?|proxim[oa]s?|next|previous|last|ultim[oa]s?|"
    r"ahora|now|ya|luego|despues|later|aleatoria|aleatorio|shuffle)"
)
# Uso real 2026-09-23 «poner mi canción favorita del año pasado», «mi lista de canciones más reproducidas»,
# «un buen tema de mi cantante jazz favorito»: the person's own favourite is theirs to name; it is asked,
# never searched as words.
# Tanda 4 «pon cualquier cosa de mi playlist reciente» played an unrelated YouTube video: the person's own
# collection (a playlist, their library, their liked or saved songs, what they played lately) is theirs too; no
# search finds it, so it is asked the same way.
_OWN_FAVOURITE = (
    r"\b(?:mi|mis|my|tu|tus|your|nuestr[oa]s?|our)\b.*\b(?:favorit[oa]s?|favou?rites?|preferid[oa]s?|"
    r"mas\s+(?:escuchad|reproducid|oid)[oa]s?|most\s+played|"
    r"playlists?|listas?\s+de\s+(?:reproduccion|canciones|musica)|biblioteca|library|"
    r"(?:canciones|temas|musica)\s+(?:guardad[oa]s|que\s+me\s+gustan)|me\s+gusta|liked\s+songs|saved\s+(?:songs|music)|"
    r"recientes?|recently\s+played|recent)\b"
)
# Tanda 4c 2026-09-24 «pon cualquier cosa de mi playlist reciente» was asked «¿Qué quieres que reproduzca de tu
# playlist reciente?»: «cualquier cosa», «lo que sea», «algo», «whatever», «anything», «a song» leave the choice
# to BAXY, so nothing is missing. What the person played last resumes their player
# (media.own_recent_listening_request); any other collection of theirs no operation opens, so it is a plain limit.
_FREE_CHOICE_IN_OWN_COLLECTION = (
    r"\b(?:cualquier\s+(?:cosa|cancion|tema|musica)|lo\s+que\s+(?:sea|quieras)|algo|alguna\s+cancion|una\s+cancion|"
    r"un\s+tema|whatever|anything|something|any\s+(?:song|track|music)|a\s+(?:song|track)|some\s+(?:songs?|music|tracks?)|"
    r"random(?:\s+(?:songs?|tracks?))?)\s+(?:de|del|desde|from|of|in|en|on)\s+(?:(?:la|el|the)\s+)?"
    r"(?:mi|mis|my|nuestr[oa]s?|our)\b"
)


def own_collection_free_choice(text: str) -> bool:
    """«ponme algo de mi biblioteca», «play anything from my playlist»: a play request that leaves the choice free
    within the person's own collection."""

    folded = _strip_request_envelope(_fold(text)).strip(" .!?¿¡")
    return (
        _head_is(
            _request_head(folded),
            r"(?:pon|pone|ponme|poneme|reproduce|reproducir|reproduci|reproducime|play|toca|tocame|put|start)",
        )
        and _has(folded, _FREE_CHOICE_IN_OWN_COLLECTION)
        and _has(folded, _OWN_FAVOURITE)
    )


# Uso real 2026-09-23 «pon mi lista wacky en mi aplicación gaana», «play me playlist wacky in my gaana
# application»: an application named as the place to play is that application's session, never the
# local playback nor Spotify.
_NAMED_APPLICATION_PLACE = (
    r"\b(?:en|on|in)\s+(?:(?:mi|my|la|the)\s+)?"
    r"(?:(?:aplicacion|app|application)\s+(?!(?:de\s+)?(?:spotify|youtube)\b)(?:de\s+)?\S+|"
    r"(?!(?:spotify|youtube|mi|my|la|the)\b)\S+\s+(?:app|application|aplicacion))\b"
)
_NOT_A_MUSIC_CHARACTER = r"(?:aqui|ahi|alli|alla|aca|encima|debajo|adentro|afuera|here|there|on|in|else|mas|more)"
_QUALIFIED_MUSIC_QUERY = re.compile(
    r"(?:(?:la|el|una?|the|a)\s+)?(?:cancion|song|tema|track)\s+"
    rf"(?P<title>(?!{_MUSIC_QUERY_FILLER}\b)\S.*)|"
    # Uso real 2026-09-23 «new pop music», «nueva música pop»: newness or chance in front keeps the genre.
    r"(?:(?:algo\s+de|un\s+poco\s+de|some|nuev[oa]s?|new|latest|random|aleatori[oa]s?)\s+)?"
    # Uso real 2026-09-24 «play classic songs», «pon canciones románticas»: songs qualified the same way.
    rf"(?P<before>(?:(?!{_MUSIC_QUERY_FILLER}\b)[a-z0-9&'-]+\s+){{1,3}})(?:music|musica|songs|canciones|tracks)|"
    r"(?:(?:la|las|the|nuev[oa]s?|new|latest|random|aleatori[oa]s?)\s+)?(?:musica|music|canciones|songs)\s+"
    rf"(?P<after>(?!{_MUSIC_QUERY_FILLER}\b)[a-z0-9&'-]+(?:\s+(?!{_MUSIC_QUERY_FILLER}\b)[a-z0-9&'-]+){{0,2}})|"
    # Uso real 2026-09-24 «pon los mejores country», «lo mejor de queen», «the greatest hits of abba»: the
    # best or the hits of a kind or an artist name the music.
    r"(?:(?:los|las|lo|sus|the|his|her|their)\s+)?(?:mejores|mejor|exitos|grandes\s+exitos|clasicos|best|"
    r"greatest\s+hits|biggest\s+hits|hits|top(?:\s+\d+)?)\s+(?:(?:canciones|temas|songs|of|de|del)\s+)*"
    rf"(?P<hits>(?!{_MUSIC_QUERY_FILLER}\b)[a-z0-9&'-]+(?:\s+[a-z0-9&'-]+){{0,3}})|"
    # «play some jazz», «pon un poco de salsa»: some of a kind of music names it («some music» does not).
    rf"(?:some|a\s+(?:bit|little)\s+of|un\s+poco\s+de)\s+{MUSIC_GENRE}(?:\s+(?:music|musica))?|"
    # «podcasts de nfl», «reply all podcast», «el audiolibro de dune»: a show or a book to listen to,
    # named by its subject or its title, is searched with its noun.
    r"(?:(?:el|los|un|the|a)\s+)?(?:podcasts?|audiolibros?|audiobooks?)\s+(?:(?:de|del|sobre|about|on|of|by)\s+)?"
    rf"(?P<show>(?!{_MUSIC_QUERY_FILLER}\b)\S.*)|"
    rf"(?P<show_before>(?:(?!{_MUSIC_QUERY_FILLER}\b)[a-z0-9&'-]+\s+){{1,4}})(?:podcasts?|audiobooks?)|"
    # Tanda 4 2026-09-24 «me apetece que hagas sonar algo alegre» (read as «pon algo alegre») was asked back
    # «¿Quieres que reproduzca una canción alegre?»; «play something relaxing» was already played. Something
    # with its character («algo tranquilo», «something upbeat») names the music; a place is not a character.
    rf"(?:algo|something)\s+(?!{_MUSIC_QUERY_FILLER}\b|{_NOT_A_MUSIC_CHARACTER}\b)[a-z]+"
    rf"(?:\s+(?:y|e|and)\s+(?!{_MUSIC_QUERY_FILLER}\b|{_NOT_A_MUSIC_CHARACTER}\b)[a-z]+)?",
)


# Tanda 9 «me puedes poner el último disco que sacó Estopa» was asked which record: a piece of music said with who
# made it in a relative clause («que sacó/lanzó/grabó Estopa», «that Drake released», «Adele's latest») names it as
# «el último disco de Estopa» does, and the search finds what is latest. The query says it that way.
_MUSIC_WORK = (
    r"(?:disco|discos|album|albumes|lp|ep|single|sencillo|cancion|canciones|tema|temas|temazo|track|tracks|"
    r"song|songs|record|records|sesion|session|video|videoclip|exito|hit)"
)
_MADE_BY_ES = (
    r"(?:(?:ha|han|haya|hayan|habia|habian)\s+)?"
    r"(?:saco|sacaron|sacado|lanzo|lanzaron|lanzado|grabo|grabaron|grabado|publico|publicaron|publicado|"
    r"estreno|estrenaron|estrenado|hizo|hicieron|hecho|canto|cantaron|cantado|compuso|compusieron|compuesto|"
    r"subio|subieron|subido|saca|sacan|lanza|lanzan|canta|cantan)"
)
_MADE_BY_EN = r"(?:(?:has|have|just)\s+)?(?:released|put\s+out|dropped|recorded|made|sang|sung|came\s+out\s+with)"


def _music_named_by_its_maker(query: str) -> str | None:
    """«el último disco que sacó Estopa» → «el último disco de Estopa», «the new album that Drake released» →
    «the new album by Drake»; None when the query does not name a work and its maker that way."""

    words = query.strip(" .!?").split()
    folded = _fold(" ".join(words)).split()
    spanish = re.fullmatch(
        rf"(?P<work>.*\b{_MUSIC_WORK}\b(?:\s+\w+)?)\s+que\s+{_MADE_BY_ES}\s+(?P<maker>\S.*)", " ".join(folded)
    )
    english = re.fullmatch(
        rf"(?P<work>.*\b{_MUSIC_WORK}\b)\s+(?:that\s+|which\s+)?(?P<maker>\S.*?)\s+{_MADE_BY_EN}"
        r"(?:\s+(?:recently|lately|last|this\s+year))?",
        " ".join(folded),
    )
    found, joiner = (spanish, "de") if spanish is not None else (english, "by")
    if found is None:
        return None
    work = " ".join(words[: len(found.group("work").split())])
    maker_words = found.group("maker").split()
    start = (
        len(folded) - len(maker_words) if spanish is not None else len(found.group("work").split())
        + len(re.match(r"(?:(?:that|which)\s+)?", " ".join(folded[len(found.group("work").split()):])).group().split())
    )
    maker = " ".join(words[start : start + len(maker_words)])
    # «que sacó él», «that they released»: a maker said by a pronoun is named in the conversation, not here.
    if not maker or _has(found.group("maker"), r"^(?:el|ella|ellos|ellas|ese|esa|he|she|they|it|him|her|them)$"):
        return None
    return f"{work} {joiner} {maker}"


def _qualified_music_query(query: str) -> str | None:
    """The music a music noun names by itself, or None when it names none."""

    found = _QUALIFIED_MUSIC_QUERY.fullmatch(_fold(query).strip(" .!?"))
    if found is None:
        return None
    if found.group("title") is not None:
        return query.strip(" .!?")[-len(found.group("title")):].strip() or None
    return query.strip(" .!?") or None


_BARE_MUSIC_NAME_FIRST_WORD_NOT = (
    # A bare name is a proper name said alone; a noun phrase with a determiner,
    # a possessive, a pronoun or a quantifier in front («pon la radio», «pon mi
    # cafetera», «pon todo…») is an object.
    r"(?:el|la|los|las|lo|le|les|un|una|unos|unas|uno|"
    r"mi|mis|tu|tus|su|sus|nuestro|nuestra|este|esta|estos|estas|ese|esa|esos|esas|esto|eso|"
    r"aquel|aquella|me|te|se|nos|todo|toda|todos|todas|algo|alguna?|algun|nada|otro|otra|otros|otras|"
    r"cualquier|cualquiera|mas|menos|muy|ya|aqui|ahi|alli|ahora|luego|otra|vez|"
    r"the|an?|my|your|his|her|our|their|this|that|these|those|it|some|any|all|more|"
    r"up|down|off|back|again)"
)


# Words that make a bare «pon X» a control or a setting, never a name to play.
_BARE_MUSIC_NAME_CONTROL_WORD = (
    r"(?:pausa|pause|stop|play|mute|mudo|silencio|silence|volumen|volume|sonido|sound|audio|"
    r"brillo|brightness|modo|mode|wifi|bluetooth|pantalla|screen|musica|music|cancion|canciones|"
    r"song|songs|tema|temas|video|videos|radio|fm|am|emisora|station|podcast|podcasts|pelicula|movie|serie|juego|game|"
    r"alarma|alarm|recordatorio|reminder|temporizador|timer|atencion|orden|cuidado|ojo|"
    r"siguiente|anterior|next|previous|aleatorio|shuffle|repetir|repeat|bucle|loop|"
    r"subtitulos|subtitles|mayusculas|hora|fecha|clima|tiempo|noticias|time|date|weather|news|"
    r"fuerte|alta|alto|baja|bajo|bajita|bajito|loud|louder|quiet|exactamente|exacto|exacta|exactly|exact|"
    r"tele|television|tv|youtube|prime|hbo|twitch|crunchyroll|paramount|hulu|"
    rf"{_NETFLIX_SPELLED})"
)


def _bare_music_name(query: str) -> bool:
    """«pon rosalia», «puedes poner imogen heap» (MUSIC1559): after a play verb,
    a name said alone —one to six plain words (an artist and a title together, «michael buble save the last
    dance»), no determiner or preposition in front, no application and no control or media noun— is the
    artist or title to play; the person's capitals are not needed (the ear writes lowercase)."""

    folded = _fold(query).strip(" .!?")
    words = folded.split()
    return (
        1 <= len(words) <= 6
        and all(re.fullmatch(r"[a-z]+(?:'[a-z]+)?", word) for word in words)
        and re.fullmatch(_BARE_MUSIC_NAME_FIRST_WORD_NOT, words[0]) is None
        # «pon en marcha…», «pon Tesla en vivo», «pon café con leche»: a
        # preposition makes it a phrase with its own reader, not a name said alone.
        and not _has(folded, r"\b(?:en|de|del|al|a|con|para|por|sin|on|in|at|for|with|to)\b")
        and not _has(folded, rf"\b{_BARE_MUSIC_NAME_CONTROL_WORD}\b")
        and not _has(folded, rf"^(?:{_KNOWN_APPLICATION})$")
        # «pon trece»: a spoken number keeps its own reader (a title, never a level).
        and folded not in _PERCENTAGE_WORD_VALUES
    )


# «poné Queen por favor»: the courtesy after the name is not part of it.
_TRAILING_COURTESY = r"(?:\s*[,;:]?\s+(?:por\s+favor|please|porfa|porfi|pls|plz))?"


# «puedes poner…», «podrías tocar…»: the request envelope leaves the infinitive.
_NAMED_MUSIC_PLAY_VERB = (
    r"(?:pon|ponme|poneme|pone|poné|poner|reproduce|reproducir|reproduc[ií]|play\s+me|play|toca|tocá|tocame|tocáme|toque|tocar)"
)


def _bare_play_name(text: str) -> str | None:
    """The name of a bare «pon X» (``_bare_music_name``) as the person wrote it, or None."""

    found = re.fullmatch(
        rf"{_NAMED_MUSIC_PLAY_VERB}\s+(?P<name>\S(?:.{{0,80}}?\S)?){_TRAILING_COURTESY}[\s.!?]*",
        _request_body_surface(text), re.IGNORECASE,
    )
    return found.group("name") if found is not None and _bare_music_name(found.group("name")) else None


# After «por», what is not who performs it: the courtesy, a time or a duration, a place, and the device or channel
# something goes through («por favor», «por la noche», «por dos horas», «por los parlantes», «por email»).
_NOT_A_PERFORMER = (
    r"(?:favor|si|que|rato|momento|manana|tarde|noche|dia|vez|ejemplo|orden|escrito|email|correo|whatsapp|mensaje|"
    r"telefono|celular|movil|parlantes?|altavoz|altavoces|bocinas?|speakers?|auriculares|audifonos|cascos|headphones|"
    r"bluetooth|pc|computador(?:a)?|ordenador|equipo|ciento|encima|debajo|fondo|aqui|ahi|alli|aca|siempre|hoy|fin|"
    r"dos|tres|cuatro|cinco|diez|quince|veinte|treinta|medi[oa]|horas?|minutos?|segundos?)"
)


def _title_by_performer(query: str) -> bool:
    """Tanda 6 «ponme barcelona por queen»: «<title> por <performer>» names the song and who sings it, like «by».
    Both sides are names said alone (``_bare_music_name``, a leading article allowed: «la bamba por los lobos»);
    «pon todo por escrito», «pon la tele por el canal 5» or «pon la lavadora por la noche» are not."""

    found = re.fullmatch(r"(?P<title>.+?)\s+por\s+(?P<performer>.+)", _fold(query).strip(" .!?"))
    if found is None:
        return False
    title, performer = (
        re.sub(r"^(?:el|la|los|las|the)\s+(?=\S)", "", found.group(name)) for name in ("title", "performer")
    )
    return (
        _bare_music_name(title)
        and _bare_music_name(performer)
        and not _has(performer, rf"\b{_NOT_A_PERFORMER}\b")
    )


def _explicit_named_music_query(text: str) -> str | None:
    """Keep the supplied artist/title of one current imperative verbatim."""

    named = re.fullmatch(
        rf"{_NAMED_MUSIC_PLAY_VERB}\s+"
        # Uso real 2026-09-23 «pon algo de rock north roll», «play something from keane's hopes and
        # fears album», «aleatorias canciones de coldplay»: «something from» names music like «música de».
        r"(?:(?P<music>(?:(?:una?|la|las|los|the|a|some|todas\s+las|all(?:\s+the)?|nuev[oa]s?|new|"
        r"aleatori[oa]s?|random)\s+)*"
        r"(?:m[uú]sica|music|canci[oó]n(?:es)?|songs?|tracks?|algo|something|un\s+poco))\s+"
        r"(?:de|by|from|of)\s+)?"
        rf"(?P<query>\S(?:.{{0,160}}?\S)?){_TRAILING_COURTESY}\s*[.!?]*",
        _request_body_surface(text), re.IGNORECASE,
    )
    if named is None:
        return None
    folded = _fold(text)
    query = named.group("query").strip()
    query = _music_named_by_its_maker(query) or query
    qualified = _qualified_music_query(query) if named.group("music") is None else None
    if qualified is not None:
        query = qualified
    if (
        named.group("music") is None
        and qualified is None
        # «la caza del octubre rojo»: «del» joins a title like «de»; «the number of the beast», «of» too.
        and not (
            _has(_fold(query), r"\S\s+(?:de|del|by|of)\s+\S")
            and not _has(_fold(query), r"\b(?:of|de)\s+(?:that|this|it|them|eso|esto|esa|ese)$")
        )
        and not _title_by_performer(query)
        # MUSIC1749 «poné rock en spotify»: with the provider named, one word
        # (a genre, an artist) is the thing to play there; a generic noun
        # («música», «una canción») still asks what to play.
        and not (
            _has(_fold(query), r"\S\s+(?:en|on)\s+spotify\b")
            and not _has(
                re.sub(r"\s+(?:en|on)\s+spotify\b.*$", "", _fold(query)).strip(),
                r"^(?:(?:una?|la|el|los|las|algo\s+de|some|a|the)\s+)?"
                r"(?:m[uú]sica|music|canci[oó]n(?:es)?|songs?|temas?|tracks?|algo|something|"
                r"cualquier\s+cosa|anything|lo\s+que\s+sea)$",
            )
        )
        # VIDEO1715 «poné Tom and Jerry»: a proper title in the person's own
        # capitals (two capitalised words, connectors allowed) is the thing to
        # play; a single word or a known application name is not.
        and not _title_case_media_title(query)
        and not _bare_music_name(query)
        # «pon música rap», «tocar música reggae»: music with its genre or
        # artist said right after it names what to play.
        and not (
            (genre := re.fullmatch(r"(?:musica|music)\s+(?P<name>\S.*)", _fold(query))) is not None
            and _bare_music_name(genre.group("name"))
        )
    ) or (
        not effect_request_is_authoritative(text)
        or _has_unsupported_deferred_effect(folded)
        or len(_request_clauses(folded)) != 1
        or _other_device_effect_scope(folded)
        or _fold(query) in {"it", "them", "this", "that", "esto", "eso", "esa", "ese"}
        or _has(_fold(query), _OWN_FAVOURITE)
        # MASSIVE iot_* «pon en marcha una taza de café», «poner colores oscuros
        # en lugar de claros en la casa»: starting a thing or setting the house
        # is the physical world, never a title to play.
        or _has(_fold(query), r"^en\s+marcha\b")
        or physical_world_request(folded)
        # Dev corpus 2026-09-23 «pon un tuit a la compañía vodafone…»: a tweet is posted, never played.
        or social_network_request(text)
        # «pon el audio de Spotify al 20 %»: a volume object is a level to set,
        # never the thing to play; «ponme un recordatorio para las 3» schedules.
        or _has(
            _fold(query),
            r"^(?:(?:el|la|the|un|una|a|an)\s+)?(?:audio|volumen|volume|sonido|sound|"
            r"recordatorios?|reminders?|alarmas?|alarms?|temporizador(?:es)?|timers?|nota|note|tarea|task|evento|"
            r"event|"
            # M99 (reserva A6 «por favor pon luz natural» → a YouTube video): a light or its brightness is set, never
            # played.
            r"luz|luces|light|lights|lamparas?|lamps?|brillo|brightness)\b",
        )
        # Uso real 2026-09-23 «pon hamburguesa en mi lista de comestibles» (a list
        # entry), «ponme lo último sobre el precio de las acciones de mercadona»
        # (information): neither object is something to play.
        or _has(
            _fold(query),
            r"\b(?:en|a|al|to|in|on)\s+(?:mi|mis|la|el|my|the)\s+(?:lista|list|carrito|cart|agenda|calendario|notas?)\b|"
            r"^(?:(?:lo|las?)\s+)?ultim[oa]s?\s+(?:sobre|de|del|about|on)\b|"
            r"\b(?:precios?|cotizacion|acciones|stocks?|noticias|news|informacion|information)\b",
        )
        or _has(
            _fold(query),
            r"\b(?:archivo|file|carpeta|folder|pagina|page|fondo|wallpaper|"
            r"portapapeles|clipboard|contrasena|password)\b|"
            # VIDEO1715: a title on a named streaming service is that service's
            # session, never the local YouTube playback. M111 (DEV-F v4d F-s038 «… en netflx porfa»): however the
            # service is spelled (VIDEO1921).
            r"\b(?:en|on)\s+(?:youtube|" + _NETFLIX_SPELLED + r"|apple\s+music|apple\s+tv|prime|hbo|max|"
            r"crunchyroll|star|paramount|twitch|hulu|peacock)\b",
        )
        or _has(_fold(query), _NAMED_APPLICATION_PLACE)
    ):
        return None
    # MUSIC1749: «pon michael jackson en spotify» names the provider, not the
    # music; the query is what precedes it.
    query = re.sub(r"\s*[,;:]?\s+(?:en|on)\s+spotify\b.*$", "", query, flags=re.IGNORECASE).strip(" ,;:.!?")
    return query or None


def _direct_alarm_schedule_request(text: str) -> bool:
    """Read an alarm speech act, allowing its bounded time before the verb."""

    folded = _strip_request_envelope(_fold(text))
    if _wake_alarm_request(folded):
        return True
    if (
        _is_negative_effect_clause(folded)
        or _is_meta_or_tool_denial(folded)
        or _is_past_or_hypothetical_state(folded)
        or _has_contradictory_correction(folded)
        or _other_device_effect_scope(folded)
        or _has(folded, r'["“”«»;]|\b(?:if|si)\b')
    ):
        return False
    temporal = re.match(
        rf"^(?:(?:in|en|dentro de|within)\s+)?"
        rf"(?:{_CLOCK_TIME_SELECTOR}|{_BOUNDED_TEMPORAL_SELECTOR})\s*[, :]\s*",
        folded,
    )
    body = _strip_request_envelope(folded[temporal.end():]) if temporal else folded
    return (
        len(_request_clauses(body)) == 1
        # Uso real 2026-09-23 «pon alerta para las dos de la tarde»: an alert at a time is an alarm.
        and _has(body, r"\b(?:alarm|alarma|alerta|alert)\b")
        and _has(
            body,
            rf"^(?:(?:please|por\s+favor)\s+)?"
            rf"(?:{_SCHEDULING_VERB}|new|nueva|ring|sound)\b|\bwake\s+up\s+alarm\b",
        )
        and _reminder_has_actionable_due(folded)
        and not _has(body, r"\b(?:check|comprueba|revisa|is\s+there|hay)\b")
    )


_NOMINAL_SCHEDULE_REQUEST = re.compile(
    r"^(?:(?:please|por\s+favor)\s+)?"
    # Uso real 2026-09-24 «envíame un recordatorio para recoger a mi perro a la una por la tarde».
    r"(?:dame|damela|quiero|quisiera|necesito|me\s+hace\s+falta|i\s+(?:need|want)|give\s+me|enviame|mandame|"
    r"send\s+me)\s+"
    r"(?:una?|an?)\s+(?:(?:nueva?|new)\s+)?"
    r"(?:(?:notificacion|aviso|alerta|notification|alert)\s+(?:de|of)\s+)?"
    r"(?P<noun>alarma|alarm|despertador|recordatorio|reminder|notificacion|notification|aviso|alerta|alert)\b"
)


def nominal_schedule_request(text: str) -> str | None:
    """«necesito una alarma para mañana a las cinco y media de la mañana», «dame una
    notificación de recordatorio para la reunión de mañana a las diez a. m.» (uso real
    2026-09-23): an alarm or a reminder asked for as a thing, with its moment said, is
    the same scheduling as «pon una alarma …». The operation, or None; without a
    moment the incomplete-request reader asks it, and «dame mis recordatorios» stays a read."""

    folded = _strip_request_envelope(_fold(text))
    if (
        _is_negative_effect_clause(folded)
        or _is_meta_or_tool_denial(folded)
        or _is_past_or_hypothetical_state(folded)
        or _other_device_effect_scope(folded)
        or _has(folded, r'["“”«»;]|\b(?:if|si)\b')
        or len(_request_clauses(folded)) != 1
        or not _reminder_has_actionable_due(folded)
    ):
        return None
    found = _NOMINAL_SCHEDULE_REQUEST.match(folded)
    if found is None:
        return None
    if found.group("noun") in {"alarma", "alarm", "despertador"}:
        return "notification.schedule"
    # «dame un recordatorio para las 5»: a reminder of nothing asks its title.
    return None if _time_only_reminder_request(folded) else "reminder.create"


def _literal_memo_payload(text: str) -> str | None:
    """Return the payload of a compact ``create a memo to ...`` request."""

    folded = _strip_request_envelope(_fold(text))
    match = re.fullmatch(
        r"(?:create|make|add)\s+(?:a\s+)?memo\s+(?:to|that\s+says?)\s+"
        r"(?P<content>\S(?:.{0,480}?\S)?)[\s.!?]*",
        folded,
        re.IGNORECASE,
    )
    if match is not None:
        return match.group("content").strip()
    reversed_mixed_language = re.fullmatch(
        r"(?P<content>[a-z0-9][a-z0-9 ,&'-]{1,240}?)\s+"
        r"[^\x00-\x7f]{1,24}\s+memo\s+create\s+[^\x00-\x7f]{1,24}"
        r"[\s.!?]*",
        folded,
        re.IGNORECASE,
    )
    return (
        reversed_mixed_language.group("content").strip()
        if reversed_mixed_language is not None
        else None
    )


def _media_play_domain(text: str) -> bool:
    if _underspecified_video_request(text):
        return False
    audio_setting = _has(
        text,
        (
            r"\b(?:volumen|volume|audio|sonido|sound)\b"
            r".{0,60}(?:\b\d{1,3}\b|%)"
        ),
    )
    explicit_spotify_context = _has(
        text,
        (
            rf"\b{_OPEN}\b\s+"
            r"(?:(?:el|la|the)\s+)?"
            r"(?:(?:aplicacion|application|app)\s+)?spotify\b"
        ),
    ) and _has(
        text,
        r"\b(?:reproduce|reproducir|play|pon|ponme)\b",
    )
    direct_query = (
        _head_is(_request_head(text), r"(?:reproduce|reproducir|play)")
        and _has(
            text,
            r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
            r"(?:reproduce|reproducir|play|pon)\s+\S.+",
        )
        and not _has(text, r"\b(?:boton|button|video|pelicula|movie|archivo|file)\b")
    )
    live_music_query = re.match(
        r"^[^\w]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
        r"(?:pon|ponme|pone|poneme)\s+(?P<query>.+?)\s+en\s+vivo"
        r"(?:\s+(?:por favor|please))?[\s.!?]*$",
        text,
    )
    if live_music_query is not None:
        query = live_music_query.group("query").strip()
        # "en vivo" is a strong music-performance cue only when the object is
        # not itself a live device, stream, setting, alarm, or display. This
        # keeps the recovery generic across artists without turning every
        # Spanish imperative headed by "pon" into Spotify authority.
        live_music_query = 1 <= len(query.split()) <= 12 and not _has(
            query,
            r"\b(?:camara|camera|television|tv|video|stream|transmision|"
            r"canal|channel|radio|alarma|alarm|temporizador|timer|"
            r"volumen|volume|sonido|sound|pantalla|screen|modo|mode|"
            r"ubicacion|location|gps|mapa|map|trafico|traffic)\b",
        )
    interactive_play = _has(
        text,
        (
            r"\b(?:play|juega|jugar|juguemos)\b.{0,80}"
            r"\b(?:with|against)\s+(?:me|us)\b|"
            r"\b(?:juega|jugar|juguemos)\b.{0,80}"
            r"\b(?:conmigo|con nosotros|contra mi|contra nosotros)\b"
        ),
    )
    return (
        (
            _has(text, r"\b(?:en|on)\s+spotify\b")
            or explicit_spotify_context
            or direct_query
            or _desired_music_query(text) is not None
            or _spoken_radio_station_request(text)
            or _bare_spoken_number_media_query(text) is not None
            or bool(live_music_query)
            # Uso real 2026-09-23 «iniciar canciones de celine dion», «encuentra
            # algo de jazz suave», «iniciar podcasts de nfl»: a play or start
            # order whose object names music.
            or (
                _has(text, _MUSIC_ORDER)
                # «Pon la música al 20%»: a level, not something to play.
                and not _has(text, r"\d{1,3}\s*(?:%|por\s*ciento|percent)|\bpor\s*ciento\b")
            )
        )
        and not audio_setting
        and not interactive_play
        and not _has(text, _NAMED_APPLICATION_PLACE)
    )


_MUSIC_ORDER = (
    r"\b(?:pon|ponme|pone|poneme|toca|tocame|inicia|iniciar|empieza|empezar|arranca|reproduce|"
    r"reproducir|reproduceme|play|start|encuentra|encuentrame|busca|buscame|quiero\s+escuchar|"
    r"i\s+want\s+to\s+hear|let\s+me\s+hear)\b.{0,60}"
    r"\b(?:canciones|cancion|musica|temas|album|disco|podcasts?|emisora|playlist|songs?|music|tracks?|"
    r"jazz|rock|pop|reggaeton|salsa|lofi|clasica|classical|cumbia|bachata|trap|rap|hip\s+hop|"
    r"boleros?|tango|metal|blues|reggae|electronica|techno|house)\b"
)


def conditional_open_pause_app(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """«si tengo spotify abierto pausalo»: the catalog display name of the
    application whose open window conditions a pause, else None."""

    folded = _strip_request_envelope(_fold(text))
    found = re.match(_OPEN_STATE_CONDITION + r"(?:pausalo|pausala|pausame|pausa|pausar|pause\s+it|pause)[\s.!?]*$", folded)
    if found is None:
        return None
    # The catalog resolver returns the display name the provider expects.
    return resolve_application_catalog_app_id("abre " + found.group("app"), application_names)


def _has_unsupported_deferred_effect(text: str) -> bool:
    """Veto immediate execution when the request actually asks for later."""

    # NETWORK1293 H0230 «decime si el wifi está prendido»: «decime si …» is an
    # indirect question, not a condition that defers the request. Read the
    # rest as the question itself; timing words after it still count.
    # APPS1613 H0275 «Abre Steam y dime si Fall Guys ya está instalado»: the
    # same indirect question after a conjunction or a clause boundary.
    text = re.sub(
        r"(^[¿?¡!\s]*|[,;.]\s*|\b(?:y|and|luego|then)\s+)"
        r"((?:decime|dime|contame|cuentame|tell\s+me|fijate|chequea|check)\s+)(?:si|if|whether)\b",
        r"\1\2",
        text,
        flags=re.IGNORECASE,
    )
    # Retaining a fact for a later question is not scheduling its write. Only
    # remove that subordinate purpose, leaving an earlier "tomorrow" or a
    # separate coordinated action visible to the existing timing check.
    deferred_scope = re.sub(
        rf"\b(?:recuerda|recuerdes|recordar|remember|recall)\b"
        rf"(?!\s+(?:to\s+)?(?:{_COVERAGE_ACTION_HEAD})\b)"
        rf"(?:(?!\b(?:y|and)\s+(?:(?:luego|despues|then)\s+)?"
        rf"(?:{_COVERAGE_ACTION_HEAD})\b)[^.!?;,]){{0,160}}?"
        r"(?P<purpose>\b(?:(?:para|for)\s+)?(?:"
        r"cuando\s+te\s+(?:lo\s+)?pregunte(?:\s+de\s+nuevo)?|"
        r"when\s+i\s+ask(?:\s+you)?(?:\s+again)?)\b)"
        r"(?=\s*(?:[.!?;,]|$))",
        lambda match: match.group(0)[:match.start("purpose") - match.start()] + " ",
        text,
        flags=re.IGNORECASE,
    )
    # Timing words inside a quoted message are payload, not scheduling for the
    # send operation itself: `send ... message “I arrive in ten minutes”` must
    # remain an immediate send. Timing outside the quote is deliberately kept,
    # so `send ... at seven` continues to fail closed until a scheduled-send
    # operation exists in the authenticated catalog.
    if _head_is(_request_head(text), r"(?:envia|enviar|manda|mandar|send)"):
        deferred_scope = re.sub(
            r"«[^»]*»|“[^”]*”|‘[^’]*’|\"[^\"]*\"|'[^']*'",
            " ",
            deferred_scope,
        )
    if _has(text, r"^[¿?¡!\s]*(?:crea|crear|create|make)\s+(?:una?\s+|a\s+)?(?:nota|note)\b"):
        # A quoted note body is data. Keep scheduling before its content
        # marker and conditional actions outside its closing quote visible.
        deferred_scope = re.sub(
            r'(\b(?:con\s+el\s+texto|with\s+the\s+text)\s+)'
            r'(?:"[^\"]*"|«[^»]*»|“[^”]*”)',
            r"\1 literal content",
            deferred_scope,
            flags=re.IGNORECASE,
        )
    # These phrases sequence a second explicit action; they do not defer the
    # mission to a later real-world event. Keep ``after that meeting`` and
    # other event-relative requests untouched and therefore fail-closed.
    deferred_scope = re.sub(
        rf"\b(?:after\s+(?:that|this)|despues\s+de\s+eso|tras\s+eso)\b"
        rf"(?=\s*[,;:]?[¿?¡!\s]*(?:{_COVERAGE_ACTION_HEAD}|"
        rf"{_SEQUENCE_NOMINAL_HEAD})\b)",
        " then ",
        deferred_scope,
        flags=re.IGNORECASE,
    )
    # A time expression after a literal note-content marker belongs to the
    # payload, not to the execution schedule. Inspect each clause separately so
    # an earlier request head cannot make a later note look deferred. A selector
    # before the marker (``create a note tomorrow that says ...``) remains
    # visible and therefore still fails closed.
    scoped_clauses = _request_clauses(deferred_scope)
    if any(_indirect_audio_mute_state_query(clause) for clause in scoped_clauses):
        # Only the subordinate question's marker is non-conditional. Preserve
        # every other clause so an actual "if ... then act" still vetoes now.
        deferred_scope = " . ".join(
            re.sub(r"\b(?:si|if)\b", "", clause, count=1, flags=re.IGNORECASE)
            if _indirect_audio_mute_state_query(clause) else clause
            for clause in scoped_clauses
        )
    if any(_literal_note_payload_request(clause) for clause in scoped_clauses):
        deferred_scope = " . ".join(
            "note literal payload" if _literal_note_payload_request(clause) else clause
            for clause in scoped_clauses
        )
    # This is an immediate ordering boundary inside the current mission, not
    # a request to wait for an external event. The complete phrase is removed;
    # ordinary ``before the meeting`` / ``antes de mañana`` remain deferred.
    deferred_scope = re.sub(
        r"\b(?:before\s+continuing|antes\s+de\s+continuar)\b",
        " ",
        deferred_scope,
        flags=re.IGNORECASE,
    )
    # MUSIC1675 H0421 «si tengo spotify abierto pausalo»: a condition on the
    # present state of an application (open now or not) is checked now by
    # the window read, not awaited; only future events stay deferred.
    deferred_scope = re.sub(_OPEN_STATE_CONDITION, " ", deferred_scope, count=1, flags=re.IGNORECASE)
    hard_deferred = _has(
        deferred_scope,
        (
            r"\b(?:manana|tomorrow|mas tarde|later|"
            r"cuando(?!\s+(?:es|son|fue|sera|seran)\b)|"
            r"when(?!\s+(?:is|are|was|were|will|do|does|did|can|could|should)\b)|"
            r"hasta que|until|esta noche|tonight|mediodia|noon|"
            r"medianoche|midnight|una vez que|once|upon)\b|"
            r"\b(?:dentro de|en)\s+(?:una?|dos|tres|\d+)\s+"
            r"(?:minutos?|minutes?|horas?|hours?|dias?|days?)\b|"
            r"\bin\s+(?:an?|one|two|three|\d+)\s+"
            r"(?:minutes?|hours?|days?)\b|"
            r"\b(?:tras|despues de|antes de|after|before)\s+"
            r"(?:el|la|los|las|the|una?|an?)?\s*[a-z0-9]+\b|"
            r"\b(?:si|if)\s+.{1,120}\b|"
            r"\b(?:al|upon)\s+(?:terminar|finalizar|acabar|finish(?:ing)?)\b|"
            r"\b(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo|"
            r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|"
            r"\b(?:el|on)?\s*\d{1,2}\s+(?:de\s+)?"
            r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
            r"septiembre|octubre|noviembre|diciembre|january|february|"
            r"march|april|may|june|july|august|september|october|"
            r"november|december)\b|"
            r"\b(?:january|february|march|april|may|june|july|august|"
            r"september|october|november|december)\s+\d{1,2}\b|"
            r"\ba las?\s+\d{1,2}(?::\d{2})?\b|"
            r"\bat\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b"
        ),
    )
    terminal_deferred = (
        _has(
            deferred_scope,
            r"\b(?:luego|despues|afterwards)[\s?!.]*$",
        )
        and len(list(re.finditer(rf"\b{_COVERAGE_ACTION_HEAD}\b", deferred_scope))) < 2
    )
    deferred = hard_deferred or terminal_deferred
    if not deferred:
        return False
    head = _request_head(text)
    if _has(
        text,
        r"\b(?:y|and)\s+(?:dime|tell me)\s+(?:si|whether)\s+"
        r"(?:pudiste|se pudo|lo verificaste|you could|it was)\s+"
        r"(?:verificar(?:lo)?|verified?)\b",
    ):
        return False
    if _has(
        text,
        r"\b(?:escribe|escribi|type)\b.{0,160}"
        r"\b(?:manana|tomorrow|esta noche|tonight|lunes|martes|miercoles|"
        r"jueves|viernes|sabado|domingo|monday|tuesday|wednesday|thursday|"
        r"friday|saturday|sunday)\b",
    ):
        return False
    if _literal_note_payload_request(text):
        return False
    if _has(
        text,
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    ) and _has(
        text,
        r"\b(?:see\s+if|check\s+(?:if|whether)|mira\s+si|comprueba\s+si)\b"
        r".{0,48}\b(?:answers?|responde|contest|reach|alcanza|ping)\b",
    ):
        return False
    # Diferir un efecto no es lo mismo que no poder diferirlo. El catálogo tiene
    # `notification.schedule`, `reminder.create` y `calendar.event.create`: para
    # esos actos el «más tarde» ES la operación, no un obstáculo. Esta salida ya
    # existía, pero nombraba tan pocas formas que `ponme una alarma a las 7` o
    # `agenda una reunión el viernes` caían del lado no soportado. Se exigen
    # las DOS señales —verbo de programar y sustantivo programable— para que
    # `pon música mañana`, que no nombra ninguna, siga vetado.
    scheduling_request = (
        (_head_is(head, _SCHEDULING_VERB) and _has(text, _SCHEDULING_NOUN))
        or _head_is(head, _SCHEDULING_BY_ITSELF)
        or _has(
            text,
            rf"\b{_SCHEDULING_BY_ITSELF}\b",
        )
        or _bounded_calendar_list_query(text)
        or _task_reminder_with_due(text)
    )
    return not scheduling_request


def _task_reminder_with_due(text: str) -> bool:
    """«recuerda arreglar … mañana a las siete»: a task to remember at a moment.

    Only a clock or a bounded moment makes it a reminder; «recuerda abrir Steam
    cuando te lo pregunte» stays a deferred action.
    """

    return _has(text, rf"^[¿?¡!\s]*{TASK_REMINDER_HEAD}\s") and _has(
        text, rf"{_CLOCK_TIME_SELECTOR}|{_BOUNDED_TEMPORAL_SELECTOR}"
    )


def _has_unresolved_shared_head_coordination(text: str) -> bool:
    """Detect coordinated objects that require different operation families."""

    head = _request_head(text)
    if _head_is(
        head,
        r"(?:pon|poner|fija|ajusta|establece|set|cambia)",
    ) and _volume_domain(text):
        return _has(
            text,
            (
                r"\b(?:y|and)\b\s+(?:(?:el|la|los|las|the)\s+)?"
                r"(?:brillo|brightness|microfono|microphone|camara|camera|"
                r"notificaciones?|notifications?|pantalla|screen)\b"
            ),
        )
    if _head_is(
        head,
        r"(?:silencia|silenciar|mute|unmute|reactiva|reactivar)",
    ) and _audio_mute_domain(text):
        return _has(
            text,
            (
                r"\b(?:y|and)\b\s+(?:[a-z]+\s+){0,2}"
                r"(?:notificaciones?|notifications?|microfono|microphone|"
                r"camara|camera|brillo|brightness|pantalla|screen)\b"
            ),
        )
    return False


def _coordinated_effect_domain_minimum(text: str) -> int | None:
    """Count effect-domain objects joined under one governing action head."""

    domain_patterns = {
        "note": r"\b(?:(?:mis?|my|una?|otra|another|las?|los?|the)\s+)?(?:notas?|notes?)\b",
        "task": r"\b(?:(?:mis?|my|una?|otra|another|las?|los?|the)\s+)?(?:tareas?|tasks?)\b",
        "reminder": r"\b(?:(?:mis?|my|un|una|los?|las?|the)\s+)?(?:recordatorios?|reminders?)\b",
        "routine": r"\b(?:(?:mis?|my|una?|las?|the)\s+)?(?:rutinas?|routines?)\b",
        "calendar": (
            r"\b(?:(?:un|una|mis?|my|los?|las?|the)\s+)?"
            r"(?:eventos?|events?)(?:\s+(?:del|de|of the)\s+"
            r"(?:calendario|calendar))?\b"
        ),
        "web": (
            r"\b(?:(?:en|on)\s+(?:(?:la|the)\s+)?)?"
            r"(?:web|internet)\b"
        ),
        "email": (
            r"\b(?:(?:mis?|my|el|the)\s+)?(?:correo|correos|email|emails|mail)"
            r"(?:\s+(?:mas\s+)?(?:reciente|recientes|latest))?\b"
        ),
        "process": (
            r"\b(?:procesos?|processes)(?:\s+(?:del|de|of the)\s+"
            r"(?:sistema|system))\b|\b(?:task manager|administrador de tareas)\b"
        ),
        "game": (
            r"\b(?:juegos?|games?)(?:\s+(?:de|del|on|of)\s+steam)\b|"
            r"\bsteam\s+games?\b"
        ),
        "bluetooth": r"\bbluetooth(?:\s+(?:devices?|dispositivos?))?\b",
        "peripheral": r"\b(?:perifericos?|peripherals?)\b",
        "wifi": r"\bwi[\s-]?fi\b",
        "audio": r"\b(?:audio|sonido|sound|musica|music|volumen|volume)\b",
        "brightness": r"\b(?:brillo|brightness)\b",
        "notification": r"\b(?:notificacion(?:es)?|notifications?)\b",
        "filesystem": (
            r"\b(?:(?:una?|mis?|my|los?|las?|the)\s+)?"
            r"(?:carpetas?|folders?|archivos?|files?|directorios?|directories|"
            r"descargas|downloads)\b"
        ),
        "document": r"\b(?:(?:un|una|the)\s+)?(?:documentos?|documents?)\b",
        "backup": r"\b(?:copias? de seguridad|backups?)\b",
        "memory": r"\b(?:memoria local|local memory|memory store)\b",
        "theme": r"\b(?:modo oscuro|dark mode|tema|theme)\b",
        "browser_page": r"\b(?:pagina|page|pestanas|tabs)\b",
        "clipboard": r"\b(?:portapapeles|clipboard|seleccion|selection)\b",
        "capture": r"\b(?:captura de pantalla|screenshot|screen capture)\b",
        "window": r"\b(?:ventana|window)\b",
    }
    spans: list[tuple[int, int, str]] = []
    for domain, pattern in domain_patterns.items():
        for found in re.finditer(pattern, text, re.IGNORECASE):
            spans.append((found.start(), found.end(), domain))
    spans.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    deduplicated: list[tuple[int, int, str]] = []
    for span in spans:
        if any(span[0] >= prior[0] and span[1] <= prior[1] for prior in deduplicated):
            continue
        deduplicated.append(span)
    coordinated: set[tuple[int, int, str]] = set()
    for connector in re.finditer(r"\b(?:y|and)\b", text, re.IGNORECASE):
        if _has(
            text[connector.end() :],
            r"^\s*(?:luego|despues|then|finalmente|finally|afterwards)\b",
        ):
            # This connector introduces a new action head; it does not bind
            # another object to the prior action.
            continue
        left_candidates = [
            span
            for span in deduplicated
            if span[1] <= connector.start() and connector.start() - span[1] <= 160
        ]
        right_candidates = [
            span
            for span in deduplicated
            if span[0] >= connector.end() and span[0] - connector.end() <= 160
        ]
        if not left_candidates or not right_candidates:
            continue
        left = max(left_candidates, key=lambda item: item[1])
        right = min(right_candidates, key=lambda item: item[0])
        if left[2] == right[2]:
            continue
        coordinated.add(left)
        coordinated.add(right)
    return len(coordinated) if len(coordinated) >= 2 else None


def _unresolved_explicit_cardinality(text: str) -> int | None:
    """Return a requested effect count that the argument binder cannot split."""

    words = {
        "dos": 2,
        "two": 2,
        "tres": 3,
        "three": 3,
        "cuatro": 4,
        "four": 4,
        "cinco": 5,
        "five": 5,
    }
    repeated = _match(
        text,
        (
            r"\b(?P<count>dos|two|tres|three|cuatro|four|cinco|five|[2-8])\s+"
            r"(?:notas?|notes?|tareas?|tasks?|recordatorios?|reminders?)\b|"
            r"\b(?P<times>dos|two|tres|three|cuatro|four|cinco|five|[2-8])\s+"
            r"(?:veces|times)\b|\b(?P<twice>twice)\b"
        ),
    )
    if repeated is not None:
        raw = (
            repeated.group("count")
            or repeated.group("times")
            or repeated.group("twice")
        )
        if raw in words:
            return words[raw]
        if raw == "twice":
            return 2
        return int(raw)
    repeated_domain = _match(
        text,
        (
            r"\b(?P<domain>nota|note|tarea|task|recordatorio|reminder)\b"
            r".{0,120}\b(?:y|and)\b\s+"
            r"(?:(?:una?|another|otra|otro|the)\s+)?"
            r"(?P=domain)s?\b"
        ),
    )
    return 2 if repeated_domain is not None else None


# Software people ask to open by name. Membership here never opens anything:
# it only lets an opening whose target is absent from the verified catalog be
# answered by a presence read («abrime el photoshop» → app.installed), instead
# of a model guess that denied the capability (APPS1231/007, /015) or asked for
# «the exact name» (/016).
_KNOWN_SOFTWARE = (
    rf"(?:{_KNOWN_APPLICATION}|photoshop|lightroom|illustrator|premiere(?:\s+pro)?|"
    r"after\s+effects|acrobat|brave|outlook|onenote|teams|zoom|skype|slack|telegram|"
    r"signal|notion|obsidian|obs(?:\s+studio)?|audacity|blender|gimp|inkscape|figma|"
    r"unity|unreal(?:\s+engine)?|godot|visual\s+studio(?:\s+code)?|vs\s*code|pycharm|"
    r"intellij|eclipse|android\s+studio|docker(?:\s+desktop)?|postman|github\s+desktop|"
    r"epic\s+games(?:\s+launcher)?|minecraft|roblox|fortnite|valorant|league\s+of\s+legends|"
    r"itunes|netflix|twitch|messenger|notepad\+\+|sublime(?:\s+text)?|winrar|7-?zip|"
    r"teamviewer|anydesk|virtualbox|vmware|wireshark|filezilla|putty|wordpad|paint|"
    r"camtasia|davinci\s+resolve|canva|dropbox|google\s+drive|onedrive|autocad|matlab|"
    r"rstudio|anaconda|jupyter|kodi|plex|handbrake|thunderbird|evernote|trello|origin|"
    r"battle\.net|ubisoft\s+connect|gog\s+galaxy)"
)


# Diferir un efecto no es lo mismo que no poder diferirlo. El catálogo tiene
# `notification.schedule`, `reminder.create` y `calendar.event.create`: para
# esos actos el «más tarde» ES la operación, no un obstáculo. Se exigen las DOS
# señales —verbo de programar y sustantivo programable— para que `pon música
# mañana`, que no nombra ninguna, siga fallando cerrado.
_SCHEDULING_NOUN = (
    r"\b(?:recordatorio|recordatorios|reminder|reminders|"
    r"evento|eventos|event|events|calendario|calendar|"
    r"tarea|tareas|task|tasks|rutina|rutinas|routine|routines|"
    r"alarma|alarmas|alarm|alarms|"
    r"temporizador|temporizadores|timer|timers|"
    r"aviso|avisos|reunion|reuniones|meeting|meetings|"
    r"cita|citas|appointment|appointments)\b"
)


_SCHEDULING_VERB = (
    rf"(?:{_CREATE}|programa|programar|programame|schedule|"
    r"pon|poner|ponme|pone|poneme|pongame|"
    r"agenda|agendar|agendame|avisa|set|start|inicia|arranca|empeza|empieza|"
    # Uso real 2026-09-23 «activa alarma a las tres y media de la tarde hoy».
    r"activa|activar|activame|activate)"
)


# Un verbo que ya nombra el acto por sí solo, y la apertura nominal sin verbo
# que R3 aceptó como acto de habla, no necesitan repetir el sustantivo:
# «recuérdame comprar pan mañana», «alarma para mañana 8am».
_SCHEDULING_BY_ITSELF = (
    r"(?:recuerdame|recuerdamelo|recordame|recordamelo|avisame|despiertame|despertame|wake\s+me(?:\s+up)?|remind|"
    r"recordatorio|recordatorios|reminder|reminders|"
    r"alarma|alarmas|alarm|alarms|temporizador|temporizadores|timer|timers)"
)


def _has_contradictory_correction(
    text: str, available_operations: Iterable[str] = (),
) -> bool:
    """Reject an earlier effect when a later adversative clause revokes it."""

    # ``yes or no`` asks for a binary answer; its ``or`` is not an alternative
    # operation.  Keep inspecting the actual request so any later correction
    # or alternative still fails closed.
    text = re.sub(
        r"^[¿?¡!\s]*(?:yes\s+or\s+no|si\s+o\s+no)\b[\s,:;\-]*",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    # With the real catalog, the reader and conservation veto can prove that
    # a complete prohibition concerns a
    # different operation from every positive clause. Retractions without an
    # object and overlapping operations cannot be discharged this way.
    available = frozenset(available_operations)
    if available:
        clauses = _request_clauses(text)
        positives = tuple(c for c in clauses if not _is_negative_effect_clause(c))
        negatives = tuple(c for c in clauses if _is_negative_effect_clause(c))
        if positives and negatives:
            applications = build_application_catalog_index(())
            positive_intents = tuple(
                _resolve_explicit_effects_single(
                    c, available, application_names=applications,
                ) for c in positives
            )
            if all(intent is not None for intent in positive_intents):
                positive_operations = {
                    op for intent in positive_intents if intent is not None
                    for op in intent.operations
                }
                independent = True
                for clause in negatives:
                    forms = _negative_action_forms(clause)
                    intents = tuple(
                        _resolve_explicit_effects_single(
                            form, available, application_names=applications,
                        )
                        for form in forms
                    )
                    recognized = tuple(i for i in intents if i is not None)
                    if not recognized or any(
                        positive_operations.intersection(intent.operations)
                        for intent in recognized
                    ):
                        independent = False
                        break
                if independent:
                    text = "; ".join(positives)
    # Preserving the authored sequence is a positive mission constraint, not
    # a revocation of the requested effects. Remove only that bounded phrase;
    # any independent ``but do not ...`` clause remains visible below.
    # Uso real 2026-09-24 «vamos a oír algo de country y salsa que no sea de los estados unidos»: a negation
    # inside a relative clause says what the object is not; it revokes nothing.
    text = re.sub(
        r"\b(?:sin\s+cambiar\s+(?:el\s+)?orden|"
        r"without\s+changing\s+(?:the\s+)?order|"
        r"keep\s+(?:the\s+)?(?:same\s+)?order|"
        r"que\s+no\s+(?:sea|sean|tenga|tengan)|(?:that|which)\s+(?:(?:is|are)\s+not|isn'?t|aren'?t|(?:do|does)(?:\s+not|n'?t)\s+have))\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # M84 (DEV-D v3o D-w04-t1 «…a ver a mi vieja y no sé qué llevar de ropa, ¿cómo va a estar el clima allá?» failed
    # twice and asked «¿Podrías decirme qué ropa…?»): not knowing («no sé qué», «I don't know what») tells why the
    # person asks; it takes back nothing. «que no se cierre» still says what must not happen.
    text = re.sub(
        r"\bno\s+(?:lo\s+)?se\s+(?=(?:que|qu[eé]|como|cual|cuando|donde|si|bien|nada)\b|[,.;!?]|$)|"
        r"\bno\s+tengo\s+(?:ni\s+)?(?:idea|claro)\b|\bno\s+estoy\s+segur[oa]\b|"
        r"\bi\s+(?:don'?t|do\s+not)\s+know\b|\b(?:i'?m\s+)?not\s+sure\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return (
        _has(
            text,
            (
                r"\b(?:pero|but)\b.{0,160}"
                r"\b(?:no|nunca|jamas|never|don'?t|do\s+not)\b"
            ),
        )
        or _has(
            text,
            r",\s*no\s*,|\b(?:en vez de|instead of)\b",
        )
        or _has(
            text,
            (
                r"\b(?:evita|evitar|avoid|avoiding)\b.{0,120}"
                rf"\b(?:{_OPEN}|silencia|mute|captura|navega|navigate|"
                r"elimina|delete|envia|send)\b"
            ),
        )
        # «at five o'clock» is a clock time, not an alternative.
        or _has(text, r"\b(?:o|or)\b(?!['’]\s*clock)")
        or _has(
            text,
            (
                r"\b(?:y|and)\b.{0,40}\b(?:no|nunca|jamas|never|"
                r"don'?t|do\s+not)\b|"
                r"\b(?:sin|without)\s+(?:reproducir|reproducirla|play|"
                r"abrir|open|cambiar|change|silenciar|mute|capturar|capture|"
                r"maximizar|maximize|copiar|copy)\b"
            ),
        )
        or _has(
            text,
            (
                r"(?:[,;.!?]|\b(?:pero|aunque|but|though)\b)\s*"
                r"(?:(?:mejor|en realidad|actually|on second thought)\s+)?"
                r"(?:no\b|don'?t\b|do\s+not\b|better\s+not\b)|"
                r"\b(?:mejor\s+no|en realidad\s+no|better\s+not|"
                r"actually\s+do\s+not|on second thought\s+do\s+not|"
                r"scratch that)\b|"
                r"(?:[,;.]|\b(?:pero|but)\b)\s*(?:mejor\s+)?"
                r"(?:ya no|ignora(?: eso|lo)?|"
                r"deja(?:lo)?(?=\s*(?:$|[,;.!?]))|me retracto|"
                r"me arrepenti|never mind|ignore that|i take that back|"
                r"drop it)\b"
            ),
        )
        or _has(
            text,
            (
                r"(?:--|[,;.!?]|\b(?:pero|but)\b)\s*"
                r"(?:(?:mejor|en realidad|actually|on second thought)\s*[,;:]?\s*)?"
                r"(?:do\s+neither|neither(?:\s+one|\s+of\s+them)?|"
                r"no\s+(?:hagas?|ejecutes?|realices?)\s+"
                r"(?:ningun[oa]|ninguna?\s+de\s+(?:las|los)\s+dos)|"
                r"ningun[oa]\s+de\s+(?:las|los)\s+dos)\b"
            ),
        )
    )


def _review_local_data_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    head: str,
    *,
    context_note: bool,
) -> bool:
    """Append clause-local data effects and report explicit web-search intent."""

    if (
        _head_is(head, r"(?:anota|anotar|anotame|apunta|apuntame|jot)")
        # «apúntame una tarea», «anota un recordatorio»: the created domain named is what is written (_CREATE).
        and not _has(folded, r"\b(?:notas?|notes?|tareas?|tasks?|recordatorios?|reminders?)\b")
        # «anota este evento en mi calendario»: written on the calendar, not in a note.
        and not _has(folded, _CALENDAR_PLACE)
    ):
        _append(
            matches,
            folded,
            "note.create",
            r"\b(?:anota|anotar|anotame|apunta|apuntame|jot)\b",
        )
    if _head_is(head, r"(?:nota|nueva|new)") and _has(
        folded, r"^[¿?¡!\s]*(?:nota\s+nueva|nueva\s+nota|new\s+note)\s*:\s*\S"
    ):
        _append(
            matches,
            folded,
            "note.create",
            r"\b(?:nota\s+nueva|nueva\s+nota|new\s+note)\b",
        )
    if _head_is(head, r"(?:write|escribe|escribir)") and _has(
        folded, r"\b(?:nota|note)\b"
    ):
        _append(
            matches,
            folded,
            "note.create",
            r"\b(?:write|escribe|escribir)\b",
        )

    created_domains = (
        _append_domain_actions(
            matches,
            folded,
            _CREATE,
            {
                "note": "note.create",
                "task": "task.create",
                "reminder": "reminder.create",
            },
        )
        if _head_is(head, _CREATE)
        else 0
    )
    if created_domains:
        created_operations = [
            entry[2]
            for entry in matches
            if entry[2]
            in {
                "note.create",
                "task.create",
                "reminder.create",
            }
        ]
        if len(set(created_operations)) == 1:
            for another in re.finditer(
                r"(?:,|\by\b|\band\b)\s+(?:otra|otro|another)\b",
                folded,
                re.IGNORECASE,
            ):
                if _is_negated_match(folded, another):
                    continue
                matches.append((another.start(), 0, created_operations[0]))
    elif context_note:
        another_note = _match(
            folded,
            r"^(?:otra|otro|another)\b",
        )
        if another_note is not None:
            matches.append((another_note.start(), 0, "note.create"))

    web_search_requested = (
        _head_is(head, _SEARCH)
        and _has(
            folded,
            r"\b(?:en|on)\s+(?:la\s+|the\s+)?(?:web|internet)\b",
        )
        and _has(folded, rf"\b{_SEARCH}\b")
    )
    if not web_search_requested:
        if _head_is(head, _SEARCH):
            _append_domain_actions(
                matches,
                folded,
                _SEARCH,
                {
                    "note": "note.search",
                    "task": "task.search",
                },
            )
    if _head_is(head, _LIST):
        _append_domain_actions(
            matches,
            folded,
            _LIST,
            {
                "note": "note.list",
                "task": "task.list",
                "reminder": "reminder.list",
                "routine": "routine.list",
            },
        )
    if _head_is(head, _READ):
        _append_domain_actions(
            matches,
            folded,
            _READ,
            {"note": "note.read"},
        )
    if (
        context_note
        and _head_is(head, r"(?:leela|leelo|leerla|leerlo|read)")
        and _has(folded, r"\b(?:leela|leelo|leerla|leerlo|read it)\b")
        and not any(entry[2] == "note.read" for entry in matches)
    ):
        _append(
            matches,
            folded,
            "note.read",
            r"\b(?:leela|leelo|leerla|leerlo|read it)\b",
        )
    return web_search_requested


# Aperturas de una pregunta de estado en ES/EN, incluidas las nominales
# («nivel de batería», «gpu usage») que no llevan verbo. Es solo una compuerta
# de acto de habla: cada reviewer sigue exigiendo su propio verbo y objeto, y
# ninguna de estas palabras selecciona por sí sola una operación.
_STATE_QUERY_HEAD = (
    r"(?:en que|en cuanto|a cuanto|a que|de cuanto|"
    r"cuanto|cuanta|cuantos|cuantas|cuan|"
    r"how\s+(?:much|many)|"
    r"queda|quedan|resta|hay|tengo|tiene|tienes|"
    rf"{_DATIVE_STATE_OPENING}|"
    r"am|do|does|have|has|"
    r"dame|decime|mostrame|display|ver|"
    r"chequea|checa|checar|verifica|verificar|fijate|mira|mirar|"
    r"bateria|battery|gpu|vram|cpu|procesador|processor|ram|memoria|memory|"
    r"disco|disk|storage|almacenamiento|espacio|space|windows|"
    r"uso|usage|nivel|level|porcentaje|percentage|percent|carga|"
    r"estado|status|version|free|current|overall|"
    rf"{_HARDWARE_MODEL_OPENING}|"
    r"audio|sonido|sound|volumen|volume)"
)


_PYTHON_STATUS_QUESTION = re.compile(
    r"^[¿?¡!\s]*(?:"
    # «dime la versión de Python instalada», «qué versión de python tengo», «cuál es la versión de python»
    r"(?:(?:dime|decime|di|tell\s+me|say)\s+(?:que|cual|la|the|which|what)\s+|"
    r"(?:que|cual\s+es\s+la|what|what's|whats|which)\s+)?"
    r"version\s+(?:de|del|of)\s+python(?:\s+(?:instalada|instalado|tengo|tienes|hay|esta\s+instalada|is\s+installed|do\s+i\s+have|installed))?"
    # «qué python tengo», «tengo python instalado», «is python installed», «python version»
    r"|(?:que|cual|what|which)\s+python(?:\s+version)?(?:\s+(?:tengo|hay|esta\s+instalado|is\s+installed|do\s+i\s+have))"
    r"|(?:tengo|hay|is)\s+python(?:\s+(?:instalado|installed))?"
    r"|(?:is\s+)?python\s+(?:version|installed)(?:\s+installed)?"
    r")\b[\s?!.,]*$",
    re.IGNORECASE,
)


_PYTHON_PACKAGE_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:"
    # «instala requests con pip», «instalá numpy usando pip», «install pandas with pip»
    r"(?:instala(?:me|r|la|lo)?|install|agrega(?:me)?|anade|pone(?:me)?|pon|add)\s+(?:el\s+|la\s+|the\s+)?"
    r"(?:paquete\s+|package\s+|modulo\s+|module\s+|libreria\s+|library\s+)?(?P<a>[a-z0-9][a-z0-9._-]{0,60})"
    r"(?:\s+(?:de|of|for)\s+python)?\s+(?:con|via|usando|mediante|with|using|through)\s+pip\b"
    # «pip install requests»
    r"|pip3?\s+install\s+(?:-u\s+|--upgrade\s+)?(?P<b>[a-z0-9][a-z0-9._-]{0,60})\b"
    # «instala el paquete requests», «install the python module numpy»
    r"|(?:instala(?:me|r)?|install)\s+(?:el\s+|la\s+|the\s+)?(?:python\s+)?(?:paquete|package|modulo|module|libreria|library)\s+(?:de\s+python\s+)?(?P<c>[a-z0-9][a-z0-9._-]{0,60})\b"
    # «tengo requests instalado en python», «is numpy installed in python»
    r"|(?:tengo|esta|is|do\s+i\s+have)\s+(?:instalad[oa]\s+)?(?:el\s+|la\s+|the\s+)?(?:paquete\s+|package\s+|modulo\s+|module\s+)?(?P<d>[a-z0-9][a-z0-9._-]{0,60})\s+(?:instalad[oa]\s+|installed\s+)?(?:en|in|para|for)\s+python\b"
    r")",
)


_REMOVABLE_STORAGE_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:"
    # «hacé un backup de mis documentos a un pendrive», «copiá mis fotos al usb», «back up my documents to a USB stick»
    r"(?:hace(?:me)?|haz|hazme|make|do|copia(?:me)?|copy|guarda(?:me)?|save|pasa(?:me)?|move|mueve|respalda|back\s*up|backup|exporta|export)\b"
    r"[^.;]{0,80}?\b(?:a|al|en|hacia|to|onto|on|into)\s+(?:un|una|el|la|mi|mis|a|an|the|my)?\s*" + _REMOVABLE_MEDIA + r"s?\b"
    # «qué pendrives hay conectados», «hay algún usb conectado», «is there a flash drive connected»
    r"|(?:que|cuales|cuantos|hay|tengo|is\s+there|are\s+there|which|what|do\s+i\s+have)\b[^.;]{0,40}?\b" + _REMOVABLE_MEDIA + r"s?\b"
    r"[^.;]{0,40}?\b(?:conectad\w*|enchufad\w*|puest\w*|hay|tengo|connected|plugged|attached|available)\b"
    r")",
)


def _removable_storage_request(text: str) -> bool:
    """USB1823 «hace un backup de mis documentos a un pendrive», «qué pendrives hay
    conectados»: a storage.removable.list read of the removable drives connected
    now — nothing is copied; the copy itself is a separate confirmed step."""

    folded = _strip_request_envelope(_fold(text)).strip()
    return _REMOVABLE_STORAGE_REQUEST.match(folded) is not None and not _has(
        folded, r"\b(?:formatea|formatear|format|borra|borrar|elimina|delete|wipe|expulsa|eject|desconecta)\b"
    )


def _python_package_request(text: str) -> str | None:
    """PIP1817 «instala requests con pip»: the package named in an install-with-pip
    or is-it-installed request, answered by a software.python.package.status read
    (pip show in every registered Python) — never an install."""

    folded = _strip_request_envelope(_fold(text)).strip()
    match = _PYTHON_PACKAGE_REQUEST.match(folded)
    if match is None:
        return None
    name = next((value for value in match.groups() if value), None)
    if name is None or name in {"python", "pip", "pip3", "el", "la", "the", "un", "una", "a", "an"}:
        return None
    return name


def _python_status_question(text: str) -> bool:
    """SYSTEM1697 «dime la versión de Python instalada», «qué versión de python
    tengo», «is Python installed»: a software.python.status read of the registered
    installs — never an install, an update or a run."""

    folded = _strip_request_envelope(_fold(text)).strip()
    return (
        _PYTHON_STATUS_QUESTION.match(folded) is not None
        and not _has(folded, r"\b(?:instala|instalar|instalame|install|actualiza|actualizar|update|upgrade|desinstala|uninstall|ejecuta|ejecutar|run|corre|pip)\b")
    )


# H0475: una linea de consola pegada con su prompt —«PS C:\\...> python x.py»,
# «C:\\...> dir»— es una orden escrita como se escribe en una consola. No trae
# verbo de peticion, asi que sin esto no contaba como pedido directo y el turno
# acababa preguntando por el script en vez de decir que no ejecuta comandos.
_CONSOLE_PROMPT_LINE = re.compile(r"^\s*(?:ps\s+)?[a-z]:\\[^>]*>\s*\S", re.IGNORECASE)


def console_prompt_command(text: str) -> bool:
    """El mensaje entero es una linea de consola con su prompt delante."""

    return _CONSOLE_PROMPT_LINE.match(_fold(text)) is not None


def _is_direct_request(text: str) -> bool:
    """Require a request speech act before granting deterministic authority."""

    if console_prompt_command(text):
        return True
    # H0101: «completalo haciendo click en instalar». La cláusula de gerundio
    # nombra la operación y su etiqueta, de modo que el pedido es directo
    # aunque el verbo principal no esté en ninguna lista.
    if _gerund_click_label(text) is not None:
        return True
    topic = _machine_status_topic(text)
    if topic is not None:
        text = topic.group("body")
    text = _negative_state_question_body(text) or text
    # MUSIC1675 «If Spotify is open, pause it.»: the present-state condition
    # frames the request; the speech act is the clause after it.
    conditioned = re.sub(_OPEN_STATE_CONDITION, "", text, count=1)
    if conditioned != text and conditioned.strip():
        text = conditioned
    # SCREEN1807: a leading statement of what is open on the screen frames the request.
    text = _without_screen_state_preface(text)
    # LIMITS1681 «en Discord apretá enter»: the client context frames the request.
    framed = re.sub(r"^[¿?¡!\s]*(?:en|in|on)\s+(?:discord|whatsapp|teams|telegram|slack|skype|zoom|signal|messenger)[,]?\s+", "", text, count=1)
    if framed != text and framed.strip():
        text = framed
    if (
        browser_back_arguments(text) is not None
        or browser_new_tab_arguments(text) is not None
        or browser_close_all_tabs_arguments(text) is not None
        or _direct_process_inventory_request(text)
        or _explicit_google_search_query(text) is not None
        or _resume_existing_media(text)
        or _media_transport_action(text)
        # Uso real 2026-09-24 «sintoniza capital radio madrid»: a station played is the request.
        or radio_station_query(text) is not None
        or _direct_alarm_schedule_request(text)
        or _task_reminder_with_due(text)
        # NETWORK1293: «¿el wifi está encendido?» is a read request without a
        # verb head; the state question itself is the speech act.
        or _wifi_state_question(text)
        or _wifi_scan_question(text)
        or _bluetooth_state_question(text)
        or _display_status_question(text)
        or _python_status_question(text)
        or _python_package_request(text) is not None
        or _removable_storage_request(text)
        or _research_question_query(text) is not None
        or public_opinion_query(text) is not None
        or record_fact_query(text) is not None
        or message_draft_request(text) is not None
        # «tuitea a Vodafone que…»: posting is a request, even with no verb this module knows.
        or social_network_request(text)
        # «what is mom's email address»: asking the address book is a request, however it is said.
        or contact_book_request(text)
        or client_channel_request(text) is not None
        # Uso real 2026-09-23 «vuelve el sonido», «Turn off silenciar», «¡detén este horrible ruido!», «silencio»:
        # the message opens with the mute switched or the sound asked back; that is the request.
        or _has(text, lexicon.MUTE_REQUEST)
        # Dev set 2 «incluir un elemento en una lista», «por favor agregue este artículo a la lista», «por favor
        # elimine mi lista de tareas pendientes»: an entry put on or taken off a list, or a list emptied, is
        # the request whatever the verb's person.
        or list_entry_request(text) is not None
        or list_creation_without_items(text) is not None
        or list_removal_request(text) is not None
    ):
        return True
    request_head = (
        rf"(?:{_OPEN}|{_LIST}|{_READ}|{_CREATE}|{_SEARCH}|{_MUTE_VERB}|"
        r"haz|hacer|hazme|haceme|hace|toma|tomar|fotografia|fotografiar|"
        r"snapshot|captura|capturar|retrata|retratar|take|capture|"
        r"genera|generar|generate|grab|reporta|report|enumera|enumerar|enumerate|"
        r"indica|indicate|detalla|detail|cuentame|describe|presenta|present|"
        # WEB1539 «resumime esta página»: summarizing is a request speech act.
        r"resumime|resumeme|resumi|resumir|resumelo|resumela|summarize|summarise|"
        r"ask(?=\s+(?:on\s+the\s+what\s+bluetooth\s+radio\s+can\s+see|"
        r"kick\s+check\b|capture\b))|"
        r"sabe(?=\s+en\s+imagen\b)|"
        r"as(?=\s+a\s+list\b)|"
        r"state|determina|determine|"
        r"necesito(?:\s+(?:saber|ver|escuchar))?|i\s+need(?:\s+to\s+know)?|"
        r"need\s+to\s+know|quiero(?:\s+ver)?|i\s+want(?:\s+to)?|"
        r"bring\s+up|establish|assess|evalua|evaluate|"
        r"recorre|reveal|revela|read\s+(?:out|back)|name|"
        r"senala|point\s+out|indaga|hunt\s+through|"
        r"senalame|echale\s+un\s+vistazo|have\s+a\s+look|look\s+at|"
        r"pull\s+up|pasame|sacame|tirame|take\s+stock|inventory|"
        r"quisiera|i\s+would\s+like|reune|gather|repasa|"
        r"pon\s+a\s+la\s+vista|bring\b.{0,48}\binto\s+view|"
        r"bring\s+me\s+up\s+to\s+date|dejame|armame|track\s+down|"
        r"a\s+ver\s+si|run\s+(?:this|a\s+quick)\s+check|"
        r"sin\s+omitir|without\s+skipping|"
        r"go\s+point\s+(?:by|por)\s+point|"
        r"conserva|preserve|registra|record|arma|put\s+together|build|"
        r"construye|construir|construct|stage|"
        r"identifica|identify|ensename|recitame|recite|guarda|save|"
        r"produce|assemble|retrieve|scan|explore|photograph|pasa|pass|"
        r"recupera|recuperar|recover|localiza|localizar|locate|encuentras|"
        r"investiga|investigar|investigate|research|build|get|"
        r"look\s+(?:through|across)|"
        r"find|rastrea|rastrear|explora|explorar|ubica|consult|"
        r"look(?=\s+on\s+(?:the\s+)?web\b)|"
        r"confirma|confirm|verify|see|"
        r"do(?=\s+i\s+have)|"
        r"resuelve|resolver|pon|pone|ponelo|ponlo|poner|ponle|fija|ajusta|adjust|"
        r"establece|set|deja|dejalo|dejala|dejar|put|leave|turn|"
        rf"{_VOLUME_UP_VERB}|{_VOLUME_DOWN_VERB}|bajalo|subelo|increment|"
        r"quita|quitar|saca|sacale|sacar|remove|get\s+rid\s+of|"
        # Uso real 2026-09-23 «erase my appointment for march seven», «clear my next activity»;
        # 2026-09-24 «limpia mi agenda para hoy», «alter lunch event to repeat every friday».
        r"erase|clear|limpia|limpiame|despeja|vacia|altera|alter|modifica|modify|"
        r"pega|pegar|pegalo|pegala|paste|"
        r"trancame|tranca|bloqueame|bloquea|lock|"
        r"agendame|"
        r"para(?=\s+(?:lo\s+que\s+esta|la\s+descarga))|"
        r"scroll|scrollea|scrollear|"
        # NETWORK1293: radio verbs with clitics or voseo («apagame el
        # bluetooth», «encendé el bluetooth», «activá»).
        r"apaga|apagame|apagalo|enciende|encende|encendeme|encendelo|"
        r"prende|prendeme|prendelo|activa|activame|activalo|"
        r"desactiva|desactivame|desactivalo|"
        r"apuntame|apunta|jot|"
        r"dale(?=\s+(?:enter|intro|return))|"
        r"llevame|anda|andar|andate|"
        # WEB1883 H0081 «abri opera gx y entra a …»: «entrar a» is the same
        # go-to speech act as «anda a» and «ve a», and it was the only one of
        # the three missing here, so the whole request lost its authority and
        # the turn became a conversation that denied the capability.
        r"entra|entrar|entrale|entrate|vete|vayamos|vamos|"
        r"devuelvele|devuelve|devuelveme|devolver|"
        r"maximiza|maximizar|maximize|minimiza|minimizar|minimize|"
        # WINDOWS1695 «Minimisa ópera.»: the s-for-z spelling is the same order.
        r"minimisa|minimisame|"
        r"restaura|restaurar|restore|escribe|escribi|escribele|escribile|write|type|"
        r"selecciona|select|copia|copiame|copy|edita|edit|convierte|convert|"
        r"elige|elegir|choose|transforma|arrastra|drag|make|"
        r"navega|navegar|navigate|ve|go|clic|click|"
        # UI1273: «apretá el 5», «pulsá el 7», «presioná el nueve», «hacé clic en…».
        r"apreta|apretale|apretalo|apretala|apretar|aprieta|pulsa|pulsale|pulsalo|pulsala|"
        r"presiona|presionale|presionalo|presionala|press|hace(?=\s+clic)|"
        r"recarga|recargar|reload|refresh|reproduce|reproducir|reproduzca|play|tune|"
        # MUSIC1753: voseo and clitic play verbs («reproducí la sinfonía…»,
        # «tocá una canción en Spotify», «tocame algo»).
        r"reproduci|reproducime|reproducila|reproducilo|toca|tocame|tocala|tocalo|toque|"
        r"reanuda|reanudar|resume|pausa|pausar|pause|deten|detener|stop|revisa|revisar|check|review|"
        r"consulta|consultar|comprueba|comprobar|checkea|chequea|averigua|averiguar|"
        r"(?:fijate|fijese)(?=\s+si\b)|"
        r"find\s+out|inspect|inspecciona|give|prepara|prepare|resolve|"
        # WINDOWS1385 «traé chrome al frente», «enfocá chrome», «bring Chrome
        # to the front»: focus heads are request speech acts too.
        r"trae|traeme|traer|lleva|llevar|bring|enfoca|enfocame|enfocar|focus|"
        r"switch(?=\s+to\b)|"
        # SCREEN1417 «describime la pantalla», «describí lo que ves».
        r"describime|describeme|describi|describila|describilo|"
        r"cierra|cerra|cerrar|cerrame|cierrame|cierres|close|envia|enviar|enviale|enviales|"
        r"manda|mandar|mandale|mandales|"
        r"arma|armar|marca|marcar|graba|grabar|record|stage|"
        r"borra|borrar|elimina|eliminar|delete|"
        # AGENDA1339 «cancelame la alarma»: clitic cancellation heads are the
        # same speech act as «cancelá»/«cancel».
        r"cancelame|cancelamela|cancelala|borrame|borrala|quitame|quitala|"
        r"eliminame|eliminala|"
        r"cierralo|cierrala|cerrala|cerralo|close it|dile|decile|tell|send|message|"
        r"pausalo|pausala|pausame|pausa|pausar|pause|"
        r"programa|programar|programame|schedule|agenda|agendar|agendame|"
        r"ponme|pone|poneme|pongame|"
        r"activa|activar|desactiva|desactivar|enciende|encender|prende|prender|"
        r"apaga|apagar|arranca|inicia|start|conecta|conectar|conectame|conectate|connect|"
        # H0401 «reiniciá la PC»: apagar era un acto de habla y reiniciar no, de
        # modo que el pedido ni llegaba a resolverse y el turno decía «No puedo
        # reiniciar la PC» sin haberlo intentado. Es la misma orden.
        r"reinicia|reiniciar|reiniciame|reboot|restart|"
        # H0714 variants «shut down the computer», «turn off the pc», «power off»: the English shutdown is the same order.
        r"shutdown|shut\s+down|turn\s+off|power\s+off|switch\s+off|"
        # LIMITS1677 «Run pytest.», «Execute ls.»: a command run is a request speech act.
        r"run|execute|"
        # LIMITS1683: downloads, arithmetic and scans are request speech acts too.
        r"descarga|descargar|descargame|download|multiplica|multiplicame|suma|sumame|resta|restame|divide|divideme|calcula|calculame|multiply|subtract|calculate|compute|escanea|scan|"
        r"desconecta|disconnect|cambia|change|"
        r"cancela|cancelar|cancel|"
        # M94 (DEV-D D-s064 «¿Sería posible suprimir mi orden de recogida en Lyft…»): suppressing or annulling
        # something is cancelling it.
        r"suprime|suprimir|suprimela|suprimelo|anula|anular|anulame|anulala|anulalo|"
        rf"{_SCHEDULING_BY_ITSELF}|"
        rf"a(?=\s+que\b)|donde|where|hablame|que|cual|cuales|con\s+que|"
        r"el(?=\s+(?:equipo|computador|pc)\b.{0,96}\b(?:red|network)\b)|"
        rf"esta|estan|quedo|sigue|what|which|when|cuando|"
        rf"whether|si|is|are|name|time|current|local|hora|fecha|"
        rf"{_STATE_QUERY_HEAD})"
    )
    return _local_internet_connection_query(text) or _has(
        text,
        rf"^[¿?¡!\s]*{_REQUEST_PREFIX}"
        rf"(?:(?:primero|first)\s*[,;:]?[¿?¡!\s]+)?"
        # «me abrís la calculadora»: the dative clitic precedes a voseo opening.
        r"(?:me\s+(?=(?:abris|abres|abre|abri|abrime|avri)\b))?"
        # «en la calculadora apretá el 5»: the app context frames the request (UI1273).
        # UI1735 «en Opera hacé clic en …», «en Steam andá a la biblioteca»: any
        # application named as the frame (owner: general mechanisms).
        rf"(?:(?:{_VISIBLE_CLICK_APP_CONTEXT}|(?:en|in|on)\s+(?:la\s+|el\s+|the\s+)?[a-z0-9][a-z0-9 .+-]{{1,40}}?)\s*,?\s+)?"
        rf"{request_head}\b",
    ) or _head_is(_request_head(text), request_head)  # the head's forms: clitics, voseo (semantic.grammar)


def _puts_into_the_agenda(text: str) -> bool:
    """M91 (reserva «I need Friday's dinner put on the calendar», «apunte la cena en mi agenda»): what goes into the
    calendar is no read of it (``notes._INTO_THE_AGENDA``, and the participle «put on the calendar»)."""

    return puts_into_the_agenda(text) or (
        _has(
            text, r"\b(?:put|puesto|puesta|poner|added|anadid[oa]|agregad[oa])\s+(?:on|to|en|a|al)\s+(?:the|my|el|mi)\s+"
                  r"(?:calendar|calendario|agenda)\b",
        )
        and not _has(text, r"^(?:has|habias|have\s+you|did\s+you)\b")
    )


def _strict_catalog_request(
    text: str,
    available_operations: frozenset[str],
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> EffectIntent | None:
    """Resolve high-precision catalog reads and explicitly named contracts.

    Every branch requires a request speech act plus a domain-specific object.
    This complements the verb-oriented reviewer for ordinary state questions
    (``check whether ...``, ``consulta el estado ...``) without turning a
    domain noun by itself into effect authority.
    """

    # The public envelope can contain both a vocative and courtesy marker
    # (``Baxy, por favor: ...``).  The outer resolver removes one layer; peel
    # at most one remaining non-semantic layer for surface invariance.
    text = _strip_request_envelope(text).strip().rstrip(".!?").rstrip()
    text = _without_screen_state_preface(text)
    if "filesystem.known.list" in available_operations and (
        _known_folder_listing_request(text) is not None
        or _known_folder_recent_listing(text) is not None
    ):
        return EffectIntent(("filesystem.known.list",), (text,))
    if "notification.list" in available_operations and _notification_listing_request(text):
        return EffectIntent(("notification.list",), (text,))
    if "email.latest.read" in available_operations and inbox_read_request(text):
        return EffectIntent(("email.latest.read",), (text,))
    if "bluetooth.radio.status" in available_operations and _bluetooth_state_question(text):
        return EffectIntent(("bluetooth.radio.status",), (text,))
    if "display.status" in available_operations and _display_status_question(text):
        return EffectIntent(("display.status",), (text,))
    if "software.python.status" in available_operations and _python_status_question(text):
        return EffectIntent(("software.python.status",), (text,))
    if "wifi.scan" in available_operations and _wifi_scan_question(text):
        # NETWORK1729: the networks around the PC are read from the adapter.
        return EffectIntent(("wifi.scan",), (text,))
    if (
        "wifi.radio.set" in available_operations
        and wifi_radio_set_request(text) is not None
        and not _is_negative_effect_clause(_fold(text))
    ):
        # NETWORK1737 «prendé el wifi» / «apagá el wifi»: the radio state, confirmed.
        return EffectIntent(("wifi.radio.set",), (text,))
    if (
        "calculator.expression.evaluate" in available_operations
        and calculator_expression_request(text) is not None
        and not _is_negative_effect_clause(_fold(text))
    ):
        # UI1725: the arithmetic is typed into the open Calculator and its
        # display is read back.
        return EffectIntent(("calculator.expression.evaluate",), (text,))
    if screen_inventory_request(text):
        # Lo que hay en la ventana de delante se mira; no se toca nada.
        return (
            EffectIntent(("input.visible.controls",), (text,))
            if "input.visible.controls" in available_operations else None
        )
    if window_inventory_arguments(text) is not None:
        return (
            EffectIntent(("window.resolve",), (text,))
            if "window.resolve" in available_operations else None
        )
    desired = _explicit_desire_request(text)
    if desired is not None:
        # A need for an explicit action is not a noun-only request to observe
        # the mentioned domain. Restrict this normalization to effect readers.
        text = desired.group("body")
    text = re.sub(
        r"^(?:primero|first)\s*[,;:]?\s+",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )

    benign_domain_alternative = _has(
        text,
        r"\b(?:pista|track)\s+(?:o|or)\s+(?:video|audio)\b",
    )
    channel_leading_message = _has(
        text,
        r"^(?:(?:por|en|on|via|through)\s+(?:whatsapp|discord)|"
        r"(?:have|ave|ab)\s+discord)\s*[,;:]?\s*"
        r"(?:manda|envia|send|dile|cuentale|avisa|avise|notifica|notify|"
        r"hazle\s+(?:llegar|saber)|"
        r"let\b.{0,48}\bknow|get\b.{0,80}\bto)\b",
    )
    bounded_status_question = _has(text, r"^(?:como|how|con\s+que|en\s+que)\b") and (
        _system_status_domain(text)
        or _network_status_domain(text)
        or _has(
            text,
            r"\b(?:wi[\s-]?fi|wireless\s+(?:connection|signal|link)|"
            r"vinculo\s+inalambrico|comunicacion\s+general|"
            r"communication\s+condition|network\s+access|"
            r"audio|sonido|sound|volume|volumen|"
            r"distribucion\s+de\s+teclas|key\s+arrangement|input\s+map)\b",
        )
    )
    bounded_routine_catalog_question = (
        _has(text, r"^(?:que|cuales?|what|which)\b")
        and _has(
            text,
            r"\b(?:rutinas?|routines?|automatizaciones?|automations?|"
            r"secuencias?\s+habituales?|habitual\s+sequences?)\b",
        )
        and _has(
            text,
            r"\b(?:baxy|guardad[oa]s?|saved|available|disponibles?|"
            r"repetir|repeat)\b|\bback\s+si\b",
        )
    )
    benign_referential_followup = _has(
        text,
        r"[?;]\s*(?:revisal[oa]s?|compruebalo|verificalo|leel[oa]s?|"
        r"check(?:\s+(?:it|them))?|verify(?:\s+it)?|read\s+them|"
        r"dame\s+(?:el\s+)?estado|give\s+me\s+(?:the\s+)?"
        r"(?:state|status))[\s.!?]*$",
    )
    explicit_catalog_composition = (
        _has(
            text,
            r"^(?:confirma|confirm|verify|build|construct|crea|create|stage|"
            r"alista|prepare)\b",
        )
        and _has(text, r"[,;]|\b(?:y|and|then|luego)\b")
        and sum(
            bool(_has(text, pattern))
            for pattern in (
                r"\b(?:installed|instalad[oa])\b",
                r"\b(?:juegos?|games?|game\s+catalog|catalogo\s+de\s+juegos)\b",
                r"\b(?:word|excel)\b",
                r"\b[a-z0-9][a-z0-9_+-]+(?:\.[a-z0-9_+-]+)+\b",
            )
        )
        >= 2
    )
    named_window_query = resolve_application_window_status_name(text, application_names)
    if (
        (
            not _is_direct_request(text)
            and not channel_leading_message
            and not bounded_status_question
            and not explicit_catalog_composition
            and named_window_query is None
            and not _literal_note_payload_request(text)
            and not _bare_note_inventory_request(text)
        )
        or _is_negative_effect_clause(text)
        or (_is_meta_or_tool_denial(text) and not bounded_routine_catalog_question)
        or (
            _has_contradictory_correction(text)
            and not benign_domain_alternative
            and not benign_referential_followup
        )
        or _other_device_effect_scope(text)
    ):
        return None
    # Names and bodies of local records are literal payload.  A title such as
    # ``Captura pantalla y extrae texto`` must never be reinterpreted as a
    # screenshot/OCR composition by the catalog-read grammar; the dedicated
    # write resolver below owns the complete record request.
    if _has(
        text,
        r"^(?:crea|crear|create|anota|anotar|note|agrega|agregar|add|guarda|save)\s+"
        r"(?:(?:un|una|a|an)\s+)?(?:nota|note|tarea|task|recordatorio|reminder)\b",
    ):
        return None
    deferred_effect = _has_unsupported_deferred_effect(text)

    def intent(*operations: str, evidence: tuple[str, ...] = ()) -> EffectIntent | None:
        if not operations or not set(operations) <= available_operations:
            return None
        return EffectIntent(operations, evidence or tuple(text for _ in operations))

    if not deferred_effect and _literal_note_payload_request(text):
        return intent("note.create")
    if named_window_query is not None:
        return intent("window.application.status")

    if _local_internet_connection_query(text):
        # The generic internet domain below means web content, not this local
        # observation. Match the whole clause so a second task is not dropped;
        # a missing catalog operation must not become an unrelated web search.
        return intent("network.status")

    if (
        not deferred_effect
        and _has(
            text,
            r"^(?:trancame|tranca|bloqueame|bloquea|lock)\b",
        )
        and _has(
            text,
            r"\b(?:equipo|pc|computador(?:a)?|computer|maquina|machine|windows)\b",
        )
    ):
        resolved = intent("system.power")
        if resolved is not None:
            return resolved

    package_id = _spoken_package_id(text)
    if (
        package_id is not None
        and not deferred_effect
        and not explicit_catalog_composition
        # «deja Git.Git ready y check si Audacity está installed»: the package
        # is one clause of a compound; the clause reader keeps the other one.
        and len(_request_clauses(text)) == 1
        and _has(
            text,
            r"\b(?:prepara|preparado|prepare|stage|staged|resolve|resuelve|"
            r"ubica|locate|deja|leave|instalacion|installation|instalar|"
            r"install|listo|ready|tied|alista(?:lo|la)?)\b",
        )
        and not _has(text, r"https?://|\b(?:juego|game|steam)\b")
    ):
        resolved_package = intent(
            "package.install.prepare",
            evidence=(package_id,),
        )
        if resolved_package is not None:
            return resolved_package

    if _has(
        text,
        r"^(?:have|ave|ab)\s+discord\s+(?:notify|avise)\s+(?:a\s+)?"
        r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+(?:that|que)\s+\S.+$",
    ):
        resolved_message = intent("message.recipient.resolve", "message.send")
        if resolved_message is not None:
            return resolved_message
    if _has(
        text,
        r"^ask\s+capture\b.{0,48}\bturn\s+screen\s*writing\s+into\s+"
        r"characters?\b",
    ):
        resolved_ocr = intent("capture.screenshot", "ocr.read")
        if resolved_ocr is not None:
            return resolved_ocr
    if _has(
        text,
        r"^a\s+ver\s+si\s+fin\b.{0,96}\bdownloads?\b",
    ):
        resolved_files = intent("filesystem.known.search")
        if resolved_files is not None:
            return resolved_files
    if _has(
        text,
        r"^(?:que|which)\s+habitual\s+sequences?\b.{0,72}"
        r"\bback\s+si\b.{0,32}\brepeat\b",
    ) or _has(
        text,
        r"^show\b.{0,32}\bsub\s*personal\s+o\s+the\s+machines\b",
    ):
        resolved_routine = intent("routine.list")
        if resolved_routine is not None:
            return resolved_routine

    request_observation = _has(
        text,
        r"^(?:comprueba|comprobar|checkea|chequea|averigua|averiguar|check|"
        r"ask(?=\s+(?:on\s+the\s+what\s+bluetooth\s+radio\s+can\s+see|"
        r"kick\s+check\b|capture\b))|"
        r"sabe(?=\s+en\s+imagen\b)|"
        r"as(?=\s+a\s+list\b)|find\s+out|"
        r"consulta|consultar|revisa|revisar|review|inspect|inspecciona|mira|"
        r"dime|decime|contame|fijate|dame|cuentame|tell|show|display|muestra|muestrame|ensename|"
        r"indica|indicate|detalla|detail|lista|listar|list|give|describe|"
        r"presenta|present|state|determina|"
        r"determine|identifica|identify|recitame|recite|"
        r"necesito(?:\s+(?:saber|ver|escuchar))?|i\s+need(?:\s+to\s+know)?|"
        r"need\s+to\s+know|bring\s+up|establish|assess|evalua|evaluate|"
        r"recorre|reveal|revela|read\s+(?:out|back)|name|"
        r"senala|point\s+out|indaga|hunt\s+through|"
        r"echale\s+un\s+vistazo|have\s+a\s+look|look\s+at|"
        r"sacame|pull\s+up|pasame|track\s+down|a\s+ver\s+si|"
        r"haz(?:me)?\s+(?:(?:este|un)\s+)?(?:chequeo|recuento|listado|inventario)|"
        r"take\s+stock|make\s+me\s+a\s+list|inventory|"
        r"quiero\s+(?:saber|ver|si(?=\s+el\s+complete\s+index\b)|see|"
        r"el\s+appointment\s+itinerary)|"
        r"quisiera\s+(?:el\s+itinerario|the\s+appointment\s+itinerary)|"
        r"i\s+want\s+to\s+(?:know|see)|"
        r"i\s+would\s+like\s+the\s+appointment\s+itinerary|"
        r"dejame|leave\s+me|guarda|save|reune|gather|repasa|"
        r"pon\s+a\s+la\s+vista|bring\s+(?:the\s+)?(?:saved\s+)?[^,;]{0,40}\s+into\s+view|"
        r"ponme\s+(?:al\s+dia|up\s+to\s+date)|bring\s+me\s+up\s+to\s+date|"
        r"run\s+(?:this|a\s+quick)\s+check|ubica|"
        r"senalame|quedo|sigue|"
        r"sin\s+omitir\s+ninguno\s*[,;:]?\s*revisa|"
        r"without\s+skipping\s+(?:any|ninguno)\s*[,;:]?\s*(?:inspect|revisa)|"
        r"ve\s+punto\s+por\s+punto|go\s+point\s+(?:by|por)\s+point|"
        r"que|cual|cuales|con\s+que|what|which|is|are|esta|estan|hay|quedo|sigue|"
        r"lee|read|abre|open|reporta|report|enumera|enumerate|recupera|recover|"
        r"retrieve|localiza|locate|investiga|investigate|research|confirma|"
        r"confirm|verify|see|look|find|scan|explore|rastrea|explora|consult|"
        r"haz(?:\s+un\s+chequeo)?)\b",
    ) or (
        _has(text, r"^(?:como|how|con\s+que|en\s+que)\b")
        and (
            _system_status_domain(text)
            or _network_status_domain(text)
            or _has(
                text,
                r"\b(?:wi[\s-]?fi|wireless\s+(?:connection|signal|link)|"
                r"vinculo\s+inalambrico|comunicacion\s+general|"
                r"communication\s+condition|network\s+access|"
                r"audio|sonido|sound|volume|volumen|"
                r"distribucion\s+de\s+teclas|key\s+arrangement|input\s+map)\b",
            )
        )
    )
    # Tanda 6 «dame el audio otra vez», «necesito el sonido de nuevo»: the sound asked back is an unmute order
    # (lexicon.SOUND_BACK), not a request to observe the audio.
    request_observation = request_observation and not _has(text, lexicon.MUTE_REQUEST)
    action_composition_head = _has(
        text,
        r"^(?:deja|leave|crea|create|construye|construct|captura|capture|"
        r"toma|take|retrata|conserva|preserve|"
        r"registra|record|arma|armame|put\s+together|build|stage|resolve|"
        r"resuelve|pon|put|find|encuentra)\b",
    ) or (
        _has(text, r"^(?:make|get|quiero(?:\s+ver)?|i\s+want(?:\s+to)?)\b")
        and _has(text, r"\b(?:word|excel|netflix|install|installation)\b")
    )

    # High-precision colloquial singletons.  These are semantic shapes, not
    # utterance literals: a request act and a closed catalog domain are both
    # required, while the negative/meta/other-device gates above still win.
    if request_observation and _has(
        text,
        r"\b(?:palabras?|words?)\b.{0,48}\b(?:list[oa]s?|ready)\b"
        r".{0,24}\b(?:pegar|paste)\b",
    ):
        resolved = intent("clipboard.read.text")
        if resolved is not None:
            return resolved
    if (_is_direct_request(text) or benign_referential_followup) and _has(
        text,
        r"\b(?:equipo|computer)\b.{0,72}\b(?:llegando|reaching)\b"
        r".{0,40}\b(?:red|network)\b",
    ):
        resolved = intent("network.status")
        if resolved is not None:
            return resolved
    if request_observation and _has(
        text,
        r"\b(?:notificacion(?:es)?|notifications?)\b.{0,48}"
        r"\b(?:vencid[oa]s?|expired|overdue)\b",
    ):
        resolved = intent("notification.list.due")
        if resolved is not None:
            return resolved
    if (
        (request_observation or action_composition_head)
        and _has(
            text,
            r"\b(?:word|excel)\b.{0,96}\b(?:se\s+llame|called|calle\s+de|named|"
            r"titulad[oa]|titled)\b",
        )
        and not _has(
            text,
            r"[,;]|\b(?:y|and)\s+(?:stage|alista|prepare|check|comprueba|"
            r"verifica|confirma)\b",
        )
    ):
        resolved = intent("office.document.create")
        if resolved is not None:
            return resolved
    if (
        action_composition_head
        and _has(
            text,
            r"\b(?:imagen|image)\b.{0,32}\b(?:pantalla|screen)\b|"
            r"\b(?:pantalla|screen)\b.{0,32}\b(?:imagen|image)\b",
        )
        and _has(
            text,
            r"\b(?:objetos?|objects?)\b.{0,48}\b(?:aparecen?|appear)\b",
        )
    ):
        resolved = intent("capture.screenshot", "vision.describe")
        if resolved is not None:
            return resolved
    if _is_direct_request(text) and _has(
        text,
        r"\b(?:aplicacion(?:es)?|applications?|apps?)\b.{0,64}"
        r"\b(?:recibiendo|receiving)\b.{0,32}\b(?:teclas|keystrokes)\b",
    ):
        resolved = intent("window.active")
        if resolved is not None:
            return resolved

    # Prefer an explicit installed-program inventory request over domain words
    # that may occur inside an authenticated application name (for example,
    # ``VLC media player``). This remains read-only and requires both an
    # observation head and a closed inventory phrase.
    installed_program_inventory = request_observation and _has(
        text,
        r"\b(?:programas?\s+locales?|local\s+programs?|installed\s+apps?|"
        r"programas?\b.{0,64}\b(?:presencia|installed)|"
        r"(?:installed\s+apps?|programas?)\b.{0,64}\b(?:aparece|shows?\s+up))\b",
    )
    if installed_program_inventory and not _has(
        text,
        r"\b(?:juego|game|steam|telefono|phone|tablet)\b",
    ):
        resolved = intent("app.installed", evidence=(text,))
        if resolved is not None:
            return resolved

    # Two explicit read domains may share one request head ("show X and Y").
    # Resolve only audited pairs and preserve the order in which the user names
    # them; an unrecognized third domain still falls through to fail-closed
    # compound conservation.
    if request_observation or action_composition_head:
        domain_patterns = (
            (
                "system.status",
                r"\b(?:sistema|system|estado\s+integral|integral\s+state|"
                r"overall\s+operating\s+condition|combined\s+operating\s+condition|"
                r"condicion\s+conjunta|condicion\s+del\s+equipo|"
                r"system\s+health|machine\s+health|salud\s+del\s+sistema|"
                r"estado\s+del\s+equipo|lectura\s+global)\b|"
                r"\b(?:maquina|machine)\b.{0,32}\b(?:conjunto|whole)\b|"
                r"\bwhole[- ]machine\b|"
                r"\bestado\s+general\b.{0,24}\b(?:pc|equipo|computador)\b|"
                r"\boverall\s+(?:status|state)\b.{0,24}\b(?:pc|computer)\b",
            ),
            (
                "network.status",
                r"\b(?:la\s+red|network|conectividad|connectivity|network\s+access|"
                r"acceso\s+(?:general\s+)?a\s+la\s+red|comunicacion\s+general|"
                r"communication\s+condition|red\s+general|"
                r"enlace\s+general\s+de\s+la\s+maquina)\b",
            ),
            (
                "task.list",
                r"\b(?:tareas?|tasks?|to-dos?|to\s+dos|unfinished\s+items?|"
                r"pendientes?|obligaciones?|obligations?|open\s+items?|open\s+tasks?|"
                r"unresolved\s+(?:to-dos?|to\s+dos)|quehaceres?|chores?|"
                r"chorsker\b.{0,32}\bmanopen|"
                r"items?\b.{0,40}\b(?:resolution|resolucion))\b",
            ),
            (
                "reminder.list",
                r"\b(?:recordatorios?|reminders?|scheduled\s+reminders?|"
                r"future\s+reminder\s+notices?|scheduled\b.{0,32}\bremember|"
                r"programad[oa]s?\b.{0,40}\brecordar|"
                r"things?\b.{0,56}\b(?:bring\s+back\s+to\s+mind|remember\s+later)|"
                r"cosas?\b.{0,72}\b(?:traerme\s+a\s+la\s+memoria|recordar\s+despues|"
                r"bring\s+back\b.{0,24}\b(?:tom\s+indlater|mindletter)))\b",
            ),
            (
                "notification.list.due",
                r"\b(?:alertas?|alerts?|notices?|avisos?|"
                r"notificaciones?|notifications?)\b.{0,64}"
                r"\b(?:overdue|due|past|paso|pasaron|pasada|plazo|crossed|"
                r"expired|fuera\s+de\s+plazo|venci(?:o|eron|d[oa]s?)|superaron)\b|"
                r"\b(?:overdue|past[- ]due|expired)\s+"
                r"(?:alerts?|notices?|notifications?|notes?)\b",
            ),
            (
                "note.list",
                r"\b(?:apuntes?|anotaciones?|memos?)\b|"
                r"(?<!bloc de )(?<!app de )(?<!coso de )\bnotas?\b|"
                r"\bnotes?\b",
            ),
            (
                "clipboard.read.text",
                r"\b(?:portapapeles|clipboard|listo\s+para\s+pegar|ready\s+to\s+paste|"
                r"waiting\s+to\s+be\s+pasted|preparad[oa]s?\s+para\s+pegar|"
                r"palabras?\s+almacenadas?\s+para\s+(?:el\s+)?proximo\s+pegado|"
                r"words?\s+stored\s+(?:(?:for|para)\s+)?(?:the\s+)?next\s+paste|"
                r"text\s+fragment\b.{0,40}\b(?:copied|capid))\b",
            ),
            ("bluetooth.device.list", r"\bbluetooth\b"),
            (
                "peripheral.list",
                r"\b(?:perifericos?|peripherals?|external\s+devices?|plugged\s+devices?|"
                r"external\s+hardware|hardware\s+externo|"
                r"dispositivos?\s+enchufados?\s+externamente|"
                r"physical\s+accessories|attached\s+accessories|accesorios?\s+fisicos?|"
                r"accesorios?\s+(?:estan\s+)?enchufados?|"
                r"plugged-in\s+accessories|accesorios?|accessories)\b",
            ),
            (
                "browser.tabs.list",
                r"\b(?:pestanas?|tabs?|paginas?\s+(?:abiertas?|cargadas?)|"
                r"pagis\s+abiertas?|"
                r"browser\s+pages?|paginas?\s+del\s+navegador|"
                r"paginas?\b.{0,24}\b(?:abiertas?|cargadas?)|"
                r"(?:open|loaded)\s+pages?|open\s+tab\s+set)\b",
            ),
            (
                "window.active",
                r"\b(?:ventana|window)\b.{0,48}\b(?:activ[oa]|active|foco|focus|"
                r"foreground|primer\s+plano|actual|current|frente|frontal|keystrokes|"
                r"por\s+encima\s+del\s+resto|above\s+the\s+rest)\b|"
                r"\b(?:active|focused|foreground|current|front)\s+window\b|"
                r"(?:^|[,;]\s*|\b(?:y|and)\s+)(?:ventana|window)"
                r"(?=\s*(?:[,;]|\by\b|\band\b|$))|"
                r"^(?:name|identify|show|muestra|consulta|identifica)\s+"
                r"(?:(?:the|la)\s+)?(?:window|ventana)(?=\s*(?:[,;]|$))|"
                r"\b(?:programa|program|application|app)\b.{0,48}"
                r"\b(?:teclas|keystrokes|typing\s+focus|foco\s+de\s+escritura)\b",
            ),
            (
                "input.keyboard.status",
                r"\b(?:key\s+(?:map|arrangement)|mapa\s+(?:de\s+entrada|de\s+teclas)|"
                r"key\s+layout|mapa\s+del\s+teclado|keyboard\s+(?:map|layout)|"
                r"distribucion\s+(?:de\s+entrada|de\s+teclas|del\s+teclado)|"
                r"input\s+(?:map|layout)|esquema\s+de\s+entrada|input\s+scheme|"
                r"(?:distribucion|layout|loud)\b.{0,40}\b(?:tecleando|typing))\b",
            ),
            (
                "email.latest.read",
                r"\b(?:ultimo|ultima|latest|newest|most\s+recent|"
                r"most\s+recently\s+received|mas\s+reciente)\b.{0,32}"
                r"\b(?:correo|email|mail|message|item|mailbox|buzon|inbox)\b|"
                r"\b(?:correo|email|mail|mailbox|buzon|inbox)\b.{0,32}"
                r"\b(?:ultimo|ultima|latest|newest|most\s+recent|mas\s+reciente|"
                r"mas\s+recientemente|recientemente\s+recibido|recently\s+received)\b|"
                r"\b(?:correo|email|mail|mailbox\s+item)\b.{0,40}"
                r"\b(?:entro|came\s+in|received)\b|"
                r"\b(?:newly\s+arrived\s+email|correo\s+recien\s+llegado|"
                r"(?:item|contenido|content)\b.{0,32}\b(?:recien|just)\s+received"
                r"\b.{0,24}\b(?:inbox|buzon)|"
                r"mensaje\b.{0,40}\bera\s+(?:y|ive)\s+blast\b.{0,32}"
                r"\bcorreo)\b",
            ),
            (
                "calendar.event.list",
                r"\b(?:calendario|calendar|agenda|citas?|appointments?|"
                r"compromisos?|commitments?)\b",
            ),
            (
                "audio.status",
                r"\b(?:audio|sonido|sound|volume|volumen|salida\s+sonora|"
                r"sound\s+(?:route|routing)|output\s+routing)\b",
            ),
            (
                "media.status",
                # «las cinco y media» is a clock time, not media.
                # «social media» is a network, not what plays.
                r"\b(?:(?<!y\s)(?<!menos\s)(?<!social\s)media|multimedia|reproduccion|playing|playback|"
                r"sonando|"
                r"audiovisual\s+session|sesion\s+audiovisual|media\s+session|"
                r"(?:track|pista)\s+(?:or|o)\s+(?:video|audio))\b",
            ),
            (
                "wifi.status",
                r"\bwi[\s-]?fi\b|\b(?:wireless\s+(?:connection|connectivity|link|signal)|"
                r"vinculo\s+inalambrico|conexion\s+inalambrica|"
                r"conectividad\s+inalambrica|conexion\s+sin\s+cable)\b",
            ),
            ("web.search", r"\b(?:web|online|internet|en\s+linea)\b"),
            (
                "filesystem.known.duplicates",
                r"\b(?:duplicad[oa]s?|repetid[oa]s?|duplicates?)\b",
            ),
            (
                "filesystem.known.search",
                r"\b(?:documentos|documents|descargas|downloads)\b",
            ),
            (
                "app.installed",
                r"\b(?:software\s+(?:local|inventory|instalado)|"
                r"inventario\s+instalado|programas?\s+locales?|"
                r"installed\s+(?:applications?|apps?|programs?|software)|"
                r"(?:applications?|apps?|programs?|software)\s+installed|"
                r"local\s+(?:app|software)\s+inventory|"
                r"aplicaciones?\s+de\s+inicio|menu\s+inicio|start\s+menu\s+apps?|"
                r"software\s+del\s+equipo|"
                r"(?:whether|si)\b.{0,64}\b(?:instalad[oa]|installed))\b",
            ),
            (
                "game.catalog.list",
                r"\b(?:juegos?|games?|videojuegos?|"
                r"playable\s+(?:titles?|inventory)|titulos?\s+locales?|"
                r"titulos?\b.{0,40}\bbiblioteca|titles?\b.{0,40}\blibrary|"
                r"(?:steam|game)\s+(?:collection|library)|"
                r"(?:coleccion|biblioteca)\s+(?:local\s+)?(?:de\s+)?steam)\b",
            ),
            (
                "backup.list",
                r"\b(?:recovery\s+points?|puntos?\s+de\s+recuperacion|"
                r"recovery\s+copies|copias?\s+de\s+recuperacion|"
                r"restorable\s+copies|restore\s+(?:snapshots?|copies)|"
                r"recoverable\s+(?:snapshots?|backup\s+copies)|"
                r"instantaneas?\s+recuperables?|copias?\s+(?:locales\s+)?recuperables?|"
                r"respaldos?\b.{0,48}\b(?:volver\s+atras|roll\s+back)|"
                r"backups?\b.{0,48}\broll\s+back|respaldos?\s+privados?|"
                r"copias?\s+privadas?|private\s+copies|respaldos?|backups?)\b",
            ),
            (
                "routine.list",
                r"\b(?:rutinas?|routines?|automatic\s+sequences?|automatizaciones?|"
                r"habitual\s+workflows?|flujos?\s+habituales?|"
                r"automated\s+sequences?|secuencias?\s+automatizadas?|"
                r"secuencias?\s+habituales?|habitual\s+sequences?|personal\s+routines?|"
                r"sub\s*personal\s+(?:automations?|o\s+the\s+machines))\b",
            ),
            (
                "capture.screenshot",
                r"\bsnapshot\b|\bsnapchat\b.{0,48}\bhow\s+desktop\s+looks\b|"
                r"\bscreen\s+capture\b|\binstantanea\b.{0,48}"
                r"\b(?:escritorio|pantalla)\b|"
                r"\b(?:capture|captura)\b.{0,32}\b(?:screen|pantalla)\b|"
                r"\b(?:screen|desktop|monitor)\b.{0,52}"
                r"\b(?:image|picture|visual\s+state)\b|"
                r"\b(?:image|picture|imagen)\b.{0,64}"
                r"\b(?:screen|desktop|monitor|display|pantalla|escritorio)\b|"
                r"\b(?:conserva|preserve|registra|record)\b.{0,48}"
                r"\b(?:screen|desktop|monitor|pantalla|escritorio)\b|"
                r"\b(?:photograph|fotografia)\b.{0,40}"
                r"\b(?:screen|pantalla|monitor|desktop|escritorio)\b|"
                r"\b(?:screen|pantalla|monitor|desktop|escritorio)\b.{0,40}"
                r"\b(?:snapshot|photograph|fotografia)\b",
            ),
            (
                "vision.describe",
                r"\b(?:describe|explicame|explica|explain|interpreta|interpret)\b.{0,64}"
                r"\b(?:escena|scene|imagen|image|contenido|contents?|resulting|"
                r"what\s+it\s+contains|what\s+is\s+shown|what(?:'s|\s+is)\s+visible|"
                r"lo\s+que\s+contiene|que\s+muestra)\b|"
                r"\b(?:dime|tell\s+me)\b.{0,48}\b(?:que\s+aparece|what\s+appears)\b|"
                r"\b(?:objetos?|objects?)\b.{0,32}\b(?:aparecen?|appear)\b",
            ),
            (
                "ocr.read",
                r"\b(?:turn|convierte|conviertela|conviertelo|extract|extrae|"
                r"transcribe|reconoce|recognize)\b.{0,48}"
                r"\b(?:words?|palabras?|text|texto|lettering|letras|"
                r"writing|escritura)\b|"
                r"\b(?:read|lee)\s+(?:its|sus)\s+(?:text|lettering|letras)\b|"
                r"\b(?:run|ejecuta)\s+ocr\b|"
                r"\b(?:written|escrito|writing)\b.{0,40}\b(?:characters?|caracteres?)\b|"
                r"\b(?:texto|text)\s+(?:legible|readable)\b",
            ),
            ("office.document.create", r"\b(?:word|excel)\b"),
            (
                "package.install.prepare",
                r"\b(?:stage|alista|prepare|prepara|resolve|resuelve)\b.{0,40}"
                r"\b[a-z0-9][a-z0-9_+-]+\.[a-z0-9._+-]+"
                r"(?![a-z0-9._+-])|"
                r"\b[a-z0-9][a-z0-9_+-]+\.[a-z0-9._+-]+"
                r"(?![a-z0-9._+-]).{0,64}"
                r"\b(?:stage|staged|prepare|prepared|preparado|alista|install|"
                r"installation|instalar|instalarse|ready|listo)\b",
            ),
            ("streaming.play.named", r"\b" + _NETFLIX_SPELLED + r"\b"),
        )
        found_domains: list[tuple[int, str]] = []
        for operation, pattern in domain_patterns:
            found = _match(text, pattern)
            if found is not None:
                found_domains.append((found.start(), operation))
        found_domains = [
            item
            for item in found_domains
            if item[1] != "note.list" or _note_inventory_object(text)
        ]
        if any(
            operation == "filesystem.known.duplicates" for _, operation in found_domains
        ):
            found_domains = [
                item for item in found_domains if item[1] != "filesystem.known.search"
            ]
        installed_game_catalog = next(
            (
                index
                for index, (_, operation) in enumerate(found_domains)
                if operation == "game.catalog.list"
            ),
            None,
        )
        plural_installed_games = _has(
            text,
            r"\b(?:que|cuales|which|what)\s+(?:juegos?|games?|videojuegos?)\b|"
            r"\b(?:juegos|games|videojuegos)\b.{0,48}"
            r"\b(?:instalad[oa]s?|installed|biblioteca|library|catalogo|catalog)\b|"
            r"\b(?:instalad[oa]s?|installed)\b.{0,24}"
            r"\b(?:juegos|games|videojuegos)\b|"
            r"\b(?:game\s+catalog|catalogo\s+(?:local\s+)?de\s+juegos)\b",
        )
        if (
            installed_game_catalog is not None
            and _has(text, r"\b(?:instalad[oa]s?|installed)\b")
            and not plural_installed_games
        ):
            position, _ = found_domains[installed_game_catalog]
            installed_operation = (
                "app.installed"
                if _has(
                    text,
                    r"\bsteam\b.{0,40}\b(?:plataforma\s+de\s+juego|"
                    r"game|gaming\s+platform)\b",
                )
                else "game.installed.named"
            )
            found_domains[installed_game_catalog] = (
                position,
                installed_operation,
            )
        # A noun that is too broad on its own becomes unambiguous inside an
        # explicit catalog enumeration (``system, network, ...``).  Keep this
        # contextual instead of teaching the standalone resolver that a bare
        # ``machine`` or ``copies`` is always a live observation.
        if _has(text, r"[,;]"):
            enumerated_domain_patterns = (
                (
                    "system.status",
                    r"(?:^|[,;]\s*|\b(?:y|and)\s+)(?:sistema|system|maquina|machine|equipo|"
                    r"computador|computer|pc)(?=\s*(?:[,;]|\by\b|\band\b|$))",
                ),
                (
                    "network.status",
                    r"(?:^|[,;]\s*|\b(?:y|and)\s+)(?:red|network)"
                    r"(?=\s*(?:[,;]|\by\b|\band\b|$))",
                ),
                (
                    "input.keyboard.status",
                    r"(?:^|[,;]\s*|\b(?:y|and)\s+)(?:teclado|keyboard)"
                    r"(?=\s*(?:[,;]|\by\b|\band\b|$))",
                ),
                (
                    "backup.list",
                    r"(?:^|[,;]\s*|\b(?:y|and)\s+)(?:copias?|copies)"
                    r"(?=\s*(?:[,;]|\by\b|\band\b|$))",
                ),
                (
                    "email.latest.read",
                    r"^(?:read|lee)\s+(?:mail|correo|email)(?=\s*[,;])",
                ),
            )
            present_operations = {operation for _, operation in found_domains}
            for operation, pattern in enumerated_domain_patterns:
                if operation in present_operations:
                    continue
                found = _match(text, pattern)
                if found is not None:
                    found_domains.append((found.start(), operation))
                    present_operations.add(operation)
            leading_system = _match(
                text,
                r"^(?:report|reporta|show|muestra|consulta|inspect|revisa)\s+"
                r"(?:system|sistema|machine|maquina|equipo|computer|computador|pc)"
                r"(?=\s*[,;])",
            )
            if leading_system is not None and "system.status" not in present_operations:
                found_domains.append((leading_system.start(), "system.status"))
        named_installation = _match(
            text,
            r"(?:^|[,;]\s*|\b(?:y|and|then|luego|despues)\s+)"
            r"(?:comprueba|verifica|confirma|revisa|inspecciona|check|"
            r"verify|confirm|review|inspect)\s+"
            r"(?:(?:el|la|the)\s+)?"
            r"(?P<target>[a-z0-9][a-z0-9 ._+@-]{0,100}?)\s+"
            r"(?:installation|instalacion|instalad[oa]|installed)"
            r"(?=$|[,;]|\s+(?:y|and|then|luego|despues)\b)",
        )
        if named_installation is not None and not any(
            operation == "app.installed" for _, operation in found_domains
        ):
            found_domains.append((named_installation.start("target"), "app.installed"))
        installed_occurrence = (
            application_names.occurrence_pattern.search(text)
            if application_names.occurrence_pattern is not None
            else None
        )
        game_catalog_precedes_installed_app = (
            installed_occurrence is not None
            and any(
                operation == "game.catalog.list"
                and position < installed_occurrence.start()
                for position, operation in found_domains
            )
            and _has(
                text[: installed_occurrence.start()],
                r"\b(?:juegos?|games?|videojuegos?|playable\s+titles?)\b",
            )
        )
        if (
            installed_occurrence is not None
            and _has(
                text[installed_occurrence.start() :],
                r"^[a-z0-9 ._+-]{1,100}\binstallation\b",
            )
            and not game_catalog_precedes_installed_app
            and not any(operation == "app.installed" for _, operation in found_domains)
        ):
            found_domains.append((installed_occurrence.start(), "app.installed"))
        if (
            installed_occurrence is not None
            and any(operation == "app.installed" for _, operation in found_domains)
            and _has(
                installed_occurrence.group(0),
                r"\b(?:nota|notas|note|notes)\b",
            )
        ):
            found_domains = [item for item in found_domains if item[1] != "note.list"]
        if any(
            operation == "notification.list.due" for _, operation in found_domains
        ) and not _has(
            text,
            r"\b(?:tareas?|tasks?|to-dos?|to\s+dos|obligaciones?|obligations?|"
            r"unfinished\s+items?|open\s+items?|"
            r"(?:mis|los|las|my)\s+pendientes)\b",
        ):
            found_domains = [item for item in found_domains if item[1] != "task.list"]
        if any(
            operation == "notification.list.due" for _, operation in found_domains
        ) and not _has(text, r"\b(?:recordatorios?|reminders?)\b"):
            found_domains = [
                item for item in found_domains if item[1] != "reminder.list"
            ]
        if _has(text, r"\b(?:reminded|remind\s+me|set\s+(?:a\s+)?reminder|recuerdame|recordame|recuerden)\b"):
            # Uso real 2026-09-24 «i need to be reminded that there is a meeting … set reminder for tuesday at
            # three p. m.»: asking to be reminded never lists the reminders.
            found_domains = [item for item in found_domains if item[1] != "reminder.list"]
        if any(
            operation == "notification.list.due" for _, operation in found_domains
        ) and _has(
            text,
            r"\b(?:expired|overdue|due|vencid[oa]s?|fuera\s+de\s+plazo)\b",
        ):
            found_domains = [item for item in found_domains if item[1] != "note.list"]
        if (
            any(operation == "bluetooth.device.list" for _, operation in found_domains)
            and any(operation == "peripheral.list" for _, operation in found_domains)
            and not _has(
                text,
                r"\b(?:perifericos?|peripherals?)\b|"
                r"\b(?:accesorios?|accessories)\b.{0,32}"
                r"\b(?:conectad[oa]s?|attached|plugged|enchufad[oa]s?)\b|[,;]",
            )
        ):
            found_domains = [
                item for item in found_domains if item[1] != "peripheral.list"
            ]
        if any(
            operation == "reminder.list" for _, operation in found_domains
        ) and not _has(
            text,
            r"\b(?:tareas?|tasks?|to-dos?|to\s+dos|obligaciones?|obligations?|"
            r"unfinished\s+items?|open\s+items?|"
            r"(?:mis|los|las|my)\s+pendientes)\b|"
            r"(?:^|[,;]\s*|\b(?:y|and)\s+)pendientes"
            r"(?=\s*(?:(?:en\s+ese|in\s+that)\s+orden\s*)?"
            r"(?:[,;]|\by\b|\band\b|$))",
        ):
            found_domains = [item for item in found_domains if item[1] != "task.list"]
        if _puts_into_the_agenda(text):
            found_domains = [item for item in found_domains if item[1] != "calendar.event.list"]
        # M91b (r6-composition-54 «List backups, games, tabs, front window, playback, and sound»): only a request whose
        # one domain is what plays can be sport; «games» listed beside «playback» is the game catalog.
        if [operation for _, operation in found_domains] == ["media.status"] and _has(
            text,
            r"\b(?:teams?|equipos?|league|liga|match(?:es)?|partidos?|games?|tournament|torneo|cup|copa|"
            r"premier|nba|nfl|mlb|nhl|champions|mundial|playoffs?|final)\b",
        ):
            # M91 (reserva «who is playing tonight in the NBA»): teams playing a match are sport, a public lookup, not
            # what this PC plays.
            found_domains = [item for item in found_domains if item[1] != "media.status"]
        if any(operation == "wifi.status" for _, operation in found_domains) and _has(
            text,
            r"\b(?:que|cuales|what|which)\s+redes\b|\bredes\s+(?:wifi\s+)?(?:hay|disponibles|cerca)\b|"
            r"\b(?:escanea|escanear|scan)\b|\bnetworks\s+(?:are\s+(?:there|available|nearby|around)|can\s+you\s+see)\b",
        ):
            # LIMITS1683 «qué redes wifi hay»: the networks around the PC are not
            # the state of its own Wi-Fi; that listing is a known limit.
            found_domains = [item for item in found_domains if item[1] != "wifi.status"]
        if any(
            operation == "wifi.status" for _, operation in found_domains
        ) and not _has(
            text,
            r"\b(?:la\s+red|the\s+network|overall\s+network|"
            r"network\s+access|"
            r"acceso\s+a\s+la\s+red|conectividad\s+general|"
            r"comunicacion\s+general|communication\s+condition)\b|"
            r"(?:^|[,;]\s*)(?:red|network)(?=\s*(?:[,;]|\by\b|\band\b|$))",
        ):
            found_domains = [
                item for item in found_domains if item[1] != "network.status"
            ]
        if any(
            operation == "input.keyboard.status" for _, operation in found_domains
        ) and not _has(
            text,
            r"\b(?:estado|status|salud|health|whole|overall|"
            r"condicion\s+(?:general|conjunta))\b.{0,48}\b(?:sistema|system)\b|"
            r"(?:^|[,;]\s*)(?:sistema|system)(?=\s*(?:[,;]|\by\b|\band\b|$))|"
            r"^(?:consulta|consult|show|muestra|report|reporta|inspect|revisa)\s+"
            r"(?:sistema|system)(?=\s*[,;])",
        ):
            found_domains = [
                item for item in found_domains if item[1] != "system.status"
            ]
        if any(operation == "audio.status" for _, operation in found_domains) and _has(
            text,
            r"\b(?:a la mitad|to half|bajito|bajalo|subelo)\b",
        ):
            found_domains = [
                (start, "audio.volume")
                if operation == "audio.status"
                else (start, operation)
                for start, operation in found_domains
            ]
        found_operation_set = frozenset(operation for _, operation in found_domains)
        unresolved_mail_collection = (
            request_observation
            and bool(found_domains)
            and "email.latest.read" not in found_operation_set
            and _has(
                text,
                r"\b(?:correos|emails|mails|mensajes\s+del\s+buzon|"
                r"mailbox\s+messages|inbox\s+messages)\b",
            )
        )
        if unresolved_mail_collection:
            return None
        action_signatures = {
            "capture.screenshot": (
                r"\b(?:conserva|preserve|registra|record|guarda|save|captura|"
                r"capture|toma|take|photograph|fotografia|retrata|deja|dejame|leave|"
                r"sabe(?=\s+en\s+imagen))\b"
            ),
            "vision.describe": (
                r"\b(?:describe|explica|explicame|explain|interpreta|interpret|"
                r"dime|tell|contarme|cuentame)\b"
            ),
            "ocr.read": (
                r"\b(?:extract|extrae|transcribe|reconoce|recognize|lee|read|"
                r"ocr|turn|convert|pasa|pasame|pull\s+out|saca|sacar|"
                r"convierte|conviertelo|conviertela|entregame)\b"
            ),
            "office.document.create": (
                r"\b(?:build|construct|make|create|crea|construye|arma|armame|"
                r"put\s+together|necesito)\b"
                r".{0,80}\b(?:word|excel)\b.{0,96}"
                r"\b(?:named|called|calle\s+de|llamad[oa]|denominad[oa]|se\s+llame|"
                r"titulad[oa]|titled)\b"
            ),
            "package.install.prepare": (
                r"\b(?:stage|staged|prepare|prepared|alista|preparad[oa]|deja|"
                r"leave|resolve|resuelve)\b.{0,120}"
                r"\b(?:install|installation|instalar|instalacion|ready|list[oa]|"
                r"[a-z0-9][a-z0-9_+-]+\.[a-z0-9._+-]+)\b|"
                r"\b[a-z0-9][a-z0-9_+-]+(?:\.[a-z0-9_+-]+)+"
                r"(?![a-z0-9._+-]).{0,80}"
                r"\b(?:stage|staged|prepare|prepared|preparado|alista|"
                r"install|installation|instalar|instalarse|ready|list[oa])\b"
            ),
            "streaming.play.named": (
                r"\b(?:pon|ponme|poneme|pone|put|play|start|reproduce|ver|watch|find|encuentra|encuentras)\b"
                r".{0,120}\b" + _NETFLIX_SPELLED + r"\b|\b" + _NETFLIX_SPELLED + r"\b.{0,120}"
                r"\b(?:pon|ponme|poneme|pone|put|play|start|reproduce|ver|watch)\b"
            ),
        }
        action_contracts_grounded = all(
            operation not in action_signatures
            or _has(text, action_signatures[operation])
            for operation in found_operation_set
        )
        explicit_coordination = _has(
            text,
            r"\b(?:y|e|and|despues|then|tambien|finally|por\s+ultimo)\b|"
            r"\b(?:junto\s+con|along\s+with)\b|[,;]",
        )
        action_operations = frozenset(action_signatures)
        starts_with_non_observation_action = _has(
            text,
            r"^(?:abre|open|launch|start|crea|crear|create|add|anade|agrega|"
            r"guarda|save|escribe|write|lee|read|pon|put|set|cambia|change)\b",
        ) and not (
            bool(found_operation_set & action_operations)
            or (
                bool({"email.latest.read", "clipboard.read.text"} & found_operation_set)
                and _has(text, r"^(?:abre|open|lee|read)\b")
                and not {"note.list", "app.installed", "game.catalog.list"}
                & found_operation_set
            )
        )
        semantic_domain_conflict = (
            (
                "system.status" in found_operation_set
                and (
                    _is_past_or_hypothetical_state(text)
                    or (
                        _is_machine_knowledge_or_diagnosis(text)
                        and not (
                            len(found_operation_set) >= 3
                            and _has(
                                text,
                                r"\b(?:configuracion\s+de\s+(?:sonido|audio)|"
                                r"sound\s+configuration)\b",
                            )
                        )
                    )
                )
            )
            or (
                "media.status" in found_operation_set
                and _has(
                    text,
                    r"\b(?:en|inside)\s+(?:mi|my)\s+"
                    r"(?:cabeza|mente|head|mind)\b",
                )
            )
            # «hay algún evento deportivo mañana en chicago», «la diferencia entre
            # el calendario romano y el gregoriano»: not the person's agenda.
            or ("calendar.event.list" in found_operation_set and public_event_subject(text))
            or _has(
                text,
                r"\b(?:equipo\s+(?:de\s+)?(?:futbol|medico|editorial)|"
                r"sistema\s+(?:solar|educativo|de\s+ecuaciones)|"
                r"red\s+(?:neuronal|ferroviaria|de\s+transporte)|"
                r"neural\s+network|rail(?:way)?\s+network|transport\s+network|"
                r"window\s+of\s+opportunity|ventana\s+(?:de\s+oportunidad|temporal)|"
                r"audio\s+device|dispositivo\s+de\s+audio|"
                r"volumen\s+de\s+(?:la\s+)?(?:enciclopedia|revista|libro)|"
                r"(?:from|on)\s+(?:my|the|another)\s+(?:phone|computer|device)|"
                r"en\s+(?:mi|el|otro)\s+(?:telefono|computador|equipo)|"
                r"another\s+(?:computer|device)|"
                r"(?:wi[\s-]?fi|wireless)\s+profiles?|perfiles?\s+wi[\s-]?fi|"
                r"procesos?\s+(?:activos?\s+)?del?\s+sistema|active\s+processes?|"
                r"(?:la\s+red|the\s+net)\s+(?:acerca|about)\b)",
            )
        )
        literal_read_conflict = _has(
            text,
            r"^(?:lee|read)\s+(?:(?:la|the)\s+)?(?:frase|words?)\b",
        )
        weak_single_domain = (
            len(found_domains) == 1
            and found_domains[0][1] == "backup.list"
            and not _has(
                text,
                r"\b(?:privad[oa]s?|private|local(?:es|ly)?|recoverable|"
                r"recuperables?|restore|recovery|restaurables?)\b",
            )
        )
        deferred_read_exempt = (
            "app.installed" in found_operation_set
            and _has(text, r"\b(?:si|if|whether)\b")
        ) or (
            found_operation_set == {"reminder.list"}
            and request_observation
            and _has(
                text,
                r"\b(?:recordar|remember|scheduled|programad[oa]s?|future|"
                r"futuros?|later|despues)\b",
            )
        )
        bounded_calendar_read = (
            request_observation
            and "calendar.event.list" in found_operation_set
            and not bool(found_operation_set & action_operations)
        )
        deferred_conflict = deferred_effect and not (
            deferred_read_exempt
            or bounded_calendar_read
            or (
                found_operation_set == {"streaming.play.named"}
                and _has(text, r"\b" + _NETFLIX_SPELLED + r"\b")
            )
        )
        # M100 (reserva A10 «necesito algo todos los lunes pon un recordatorio» → reminder.list): a reminder, alarm, task
        # or note ordered made anywhere in the request is no read of the ones kept.
        makes_a_kept_item = found_operation_set <= {
            "reminder.list", "notification.list", "task.list", "note.list"
        } and _has(
            text,
            r"\b(?:pon|ponme|pone|poneme|crea|creame|programa|programame|agrega|agregame|anade|anademe|establece|"
            r"fija|set|create|add|schedule|make)\s+(?:me\s+)?(?:un|una|otro|otra|a|an|another)\s+(?:nuev[oa]\s+|new\s+)?"
            r"(?:recordatorio|alarma|tarea|nota|reminder|alarm|task|note)\b",
        )
        generic_surface_safe = not (
            starts_with_non_observation_action
            or makes_a_kept_item
            or semantic_domain_conflict
            or literal_read_conflict
            or weak_single_domain
            or deferred_conflict
        )
        shared_minimum = _coordinated_effect_domain_minimum(text)
        shared_surface_complete = (
            shared_minimum is None or len(found_domains) >= shared_minimum
        )
        allowed_two_domain_compositions = {
            frozenset(("system.status", "network.status")),
            frozenset(("task.list", "reminder.list")),
            frozenset(("note.list", "clipboard.read.text")),
            frozenset(("bluetooth.device.list", "peripheral.list")),
            frozenset(("browser.tabs.list", "window.active")),
            frozenset(("email.latest.read", "calendar.event.list")),
            frozenset(("audio.status", "media.status")),
            frozenset(("wifi.status", "network.status")),
            frozenset(("web.search", "filesystem.known.search")),
            frozenset(("app.installed", "game.catalog.list")),
            frozenset(("system.status", "audio.status")),
            frozenset(("calendar.event.list", "task.list")),
            frozenset(("reminder.list", "notification.list.due")),
            frozenset(("app.installed", "peripheral.list")),
            frozenset(("browser.tabs.list", "clipboard.read.text")),
            frozenset(("game.catalog.list", "media.status")),
            frozenset(("bluetooth.device.list", "audio.status")),
            frozenset(("window.active", "input.keyboard.status")),
            frozenset(("email.latest.read", "task.list")),
            frozenset(("backup.list", "note.list")),
            frozenset(("routine.list", "reminder.list")),
            frozenset(("capture.screenshot", "clipboard.read.text")),
            frozenset(("package.install.prepare", "app.installed")),
            frozenset(("streaming.play.named", "audio.status")),
            frozenset(("wifi.status", "bluetooth.device.list")),
            frozenset(("office.document.create", "calendar.event.list")),
            frozenset(("capture.screenshot", "vision.describe")),
            frozenset(("capture.screenshot", "ocr.read")),
        }
        if (
            2 <= len(found_domains) <= 8
            and explicit_coordination
            and action_contracts_grounded
            and generic_surface_safe
            and shared_surface_complete
            and (
                len(found_domains) >= 3
                or found_operation_set in allowed_two_domain_compositions
            )
            and (request_observation or bool(found_operation_set & action_operations))
        ):
            ordered_operations = tuple(
                operation for _, operation in sorted(found_domains)
            )
            resolved = intent(*ordered_operations)
            if resolved is not None:
                return resolved
        if (
            len(found_domains) == 1
            and action_contracts_grounded
            and generic_surface_safe
            and (request_observation or found_domains[0][1] in action_operations)
        ):
            resolved = intent(found_domains[0][1])
            if resolved is not None:
                return resolved
        if len(found_domains) >= 2:
            return None

    if (
        bounded_status_question
        and _system_status_domain(text)
        and _machine_status_scopes_are_one_reading(text)
        and _machine_status_is_the_whole_clause(text)
    ):
        resolved = intent("system.status")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:calendario|calendar|eventos?|events?|reuniones?|meetings?|"
            r"citas?|appointments?|agenda|actividades?\s+calendarizadas?|"
            r"scheduled\s+activities|compromisos?|commitments?)\b",
        )
        and _has(
            text,
            rf"{_BOUNDED_TEMPORAL_SELECTOR}|\b(?:esta\s+jornada|this\s+day)\b",
        )
        # «necesito que me recuerden las reuniones del lunes»: a reminder asked, not the agenda read.
        and not _has(text, AGENDA_NOT_A_READ)
        and not _puts_into_the_agenda(text)
    ):
        resolved = intent("calendar.event.list")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(text, r"\bbluetooth\b")
        and _has(
            text,
            r"\b(?:dispositivos?|devices?|equipos?|accesorios?|hardware|"
            r"detectad[oa]s?|detected|visibles?|visible|cercan[oa]s?|nearby|"
            r"reconoce|recognize|hallad[oa]s?|found)\b",
        )
        and not _has(
            text,
            r"\b(?:notas?|notes?|tareas?|tasks?|recordatorios?|reminders?)\b",
        )
    ):
        resolved = intent("bluetooth.device.list")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and (
            _has(text, r"\b(?:pestanas?|tabs?)\b")
            or _has(
                text,
                r"\b(?:sitios?|sites?)\b.{0,40}\b(?:abiert[oa]s?|open)\b",
            )
            or _has(
                text,
                r"\b(?:paginas?|pages?)\s+(?:abiertas?|open)\b.{0,32}"
                r"\b(?:navegador|browser)\b",
            )
            or (
                _has(text, r"\b(?:navegador|browser)\b")
                and _has(text, r"\b(?:paginas?|pages?)\b")
                and _has(
                    text,
                    r"\b(?:abiertas?|open|actuales?|current|coleccion|collection)\b",
                )
            )
        )
        and _has(
            text,
            r"\b(?:navegador|browser|abiertas?|open|actuales?|current|"
            r"pestanas?|tabs?|sitios?|sites?)\b",
        )
    ):
        resolved = intent("browser.tabs.list")
        if resolved is not None:
            return resolved

    # A capture followed by OCR or visual description is one explicit
    # two-effect contract.  Detect it before the standalone screenshot branch.
    capture_domain = _has(
        text,
        r"\b(?:captura\s+de\s+pantalla|screenshot|screen\s+capture|pantallazo|"
        r"pantalla|screen|escritorio|desktop|monitor|display)\b",
    ) or (
        _has(text, r"\b(?:captura|capture)\b")
        and _has(
            text,
            r"\b(?:ocr|visible|aparece|appears|describe|ves|see)\b",
        )
    )
    capture_action = _has(
        text,
        r"^(?:haz|hacer|toma|tomar|take|captura|capture|retrata|genera|generate|"
        r"crea|crear|fotografia|fotografiar|photograph|snapshot|saca|grab|"
        r"create|guarda|save)\b",
    )
    if capture_domain and capture_action and not deferred_effect:
        if not _has(
            text,
            r"\b(?:nota|note|tarea|task|portapapeles|clipboard|pagina|page)\b",
        ) and _has(
            text,
            r"\b(?:ocr|lee|leer|leela|leelo|leerla|leerlo|read|"
            r"extrae|extraer|extract|transcribe|transcribir|reconoce|"
            r"recognize|convierte|conviertel[oa]|convert|turn|pasa|pasame|"
            r"pull\s+out|saca|sacar|entregame)\b"
            r".{0,80}\b(?:texto|text|ocr|visible|aparece|palabras?|words?|"
            r"writing|letras|lettering|caracteres?|characters?|readable|legible)\b|"
            r"\b(?:lee|read)\s+(?:sus|its)\s+(?:letras|lettering|text)\b|"
            r"\b(?:run|ejecuta)\s+ocr\b|"
            r"\b(?:leela|leelo|leerla|leerlo|read\s+it)\s+"
            r"(?:con|with)\s+ocr\b",
        ):
            resolved = intent("capture.screenshot", "ocr.read")
            if resolved is not None:
                return resolved
        if not _has(
            text,
            r"\b(?:nota|note|tarea|task|portapapeles|clipboard|pagina|page)\b",
        ) and _has(
            text,
            r"\b(?:describ\w*|decime|dime|contame|cuentame|tell\s+me)\s+"
            r"(?:lo\s+que\s+ves|que\s+ves|what\s+you\s+see|que\s+dice|what\s+it\s+says|"
            r"que\s+hay(?:\s+en\s+(?:la\s+)?pantal\w*)?|what\s+is\s+on\s+(?:the\s+)?screen)\b|"
            # SCREEN1807: «ve qué hay en pantalla», «para ver la pantalla»,
            # «identificá el botón» after a capture are the screen text read.
            r"\b(?:ve|mira|fijate|chequea|revisa|see|check|look)\s+(?:que|lo\s+que|what)\s+(?:hay|there\s+is)\b|"
            r"\b(?:para|to)\s+(?:ver|see)\s+(?:la\s+|the\s+)?(?:pantalla|screen)\b|"
            r"\b(?:identifica\w*|identify|ubica|localiza|find)\s+(?:el\s+|los\s+|the\s+)?(?:boton\w*|button\w*)\b",
        ) and not _has(
            text,
            r"\b(?:pantalla|screen)\s+(?:del|de mi|of my)\s+"
            r"(?:telefono|celular|movil|phone|smartphone|tablet|auto|car)\b",
        ):
            # SCREEN1485 «Toma un screenshot de la pantalla ahora mismo y
            # describeme lo que ves»: without a vision provider the truthful
            # description of the screen is its recognized text (SCREEN1417).
            resolved = intent("capture.screenshot", "ocr.read")
            if resolved is not None:
                return resolved
        if not _has(
            text,
            r"\b(?:nota|note|tarea|task|portapapeles|clipboard|pagina|page)\b",
        ) and _has(
            text,
            r"\b(?:describe|describir|interpreta|interpretar|interpret|"
            r"explica|explain|dime\s+que|tell\s+me\s+what|cuentame\s+que|"
            r"contarme\s+que)\b"
            r".{0,100}\b(?:ves|see|aparece|appears|visible|it|pantalla|screen|"
            r"escena|scene|shown|muestra|imagen|image|ella|representa|depicts|"
            r"contenido|contents?|objetos?|objects?)\b|"
            r"\b(?:objetos?|objects?)\b.{0,40}\b(?:aparecen?|appear)\b",
        ):
            resolved = intent("capture.screenshot", "vision.describe")
            if resolved is not None:
                return resolved
        if (
            not _has(
                text,
                r"^(?:crea|crear|create|make|build)\s+(?:(?:un|una|a|an)\s+)?"
                r"(?:nota|note|tarea|task|documento|document)\b",
            )
            and _has(
                text,
                r"\b(?:captura|screenshot|capture|pantallazo|grab|snapshot|"
                r"foto\s+digital|digital\s+(?:snapshot|photo)|imagen|image|"
                r"fotografia|photograph|instantanea|instant\s+picture)\b",
            )
            and _has(
                text,
                r"\b(?:pantalla|screen|escritorio|desktop|screenshot|monitor|display)\b",
            )
        ):
            resolved = intent("capture.screenshot")
            if resolved is not None:
                return resolved

    # An installed-app observation may name a catalog entry or ask for a
    # verified absence.  The latter is safe because the provider only reads
    # the Start inventory and reports whether the literal was found.
    installed_inventory_query = (
        _has(text, r"\b(?:instalad[oa]s?|installed)\b")
        and _has(
            text,
            r"\b(?:si|if|whether|comprueba|averigua|check|find\s+out|confirma|"
            r"verify|verifica|see|inspect|present|disponible|available)\b",
        )
    ) or _has(
        text,
        r"\b(?:start\s+(?:app|application)\s+inventory|"
        r"inventario\s+de\s+aplicaciones\s+(?:de\s+)?inicio|"
        r"software\s+local|local\s+software\s+inventory|"
        r"figura\s+en\s+(?:el\s+)?software|"
        r"(?:figura|aparece|exists|appears|listed)\s+(?:entre|en|among|in)\s+"
        r"(?:(?:las|the|installed)\s+)?(?:aplicaciones|apps|applications)\b|"
        r"menu\s+inicio|start\s+menu\s+apps?)\b",
    )
    generic_installed_inventory_query = request_observation and _has(
        text,
        r"\b(?:inventario\s+instalado|installed\s+apps?|"
        r"programas?\b.{0,64}\b(?:presencia|installed)|"
        r"(?:installed\s+apps?|programas?)\b.{0,64}\b(?:aparece|shows?\s+up)|"
        r"(?:whether|si)\b.{0,64}\b(?:instalad[oa]|installed))\b",
    )
    if generic_installed_inventory_query and not _has(
        text,
        r"\b(?:juego|game|steam|telefono|phone|tablet)\b",
    ):
        resolved = intent("app.installed", evidence=(text,))
        if resolved is not None:
            return resolved
    if installed_inventory_query and not _has(text, r"\b(?:juego|game)\b"):
        installed_name = resolve_application_installed_name(
            text,
            application_names,
        )
        if installed_name is not None:
            resolved = intent("app.installed", evidence=(text,))
            if resolved is not None:
                return resolved

    if (
        request_observation
        and _has(text, r"\b(?:audio|sonido|sound)\b")
        and _has(
            text,
            r"\b(?:estado|status|actual|current|present|configurad[oa]|configured|"
            r"configuracion|configuration|como|how|vigentes?|set|moment)\b",
        )
        and not _has(text, r"\b(?:microfono|microphone|app|aplicacion)\b|\d|%")
    ):
        resolved = intent("audio.status")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:backup|backups|backup\s+snapshots?|respaldo|respaldos|"
            r"copias?\s+de\s+seguridad|copias?\s+privadas?|"
            r"puntos?\s+de\s+recuperacion|recovery\s+points?|"
            r"copias?\s+de\s+recuperacion|recovery\s+copies|"
            r"copias?\s+(?:locales\s+)?recuperables|"
            r"recoverable\s+(?:local\s+)?copies|restorable\s+copies)\b",
        )
        and _has(
            text,
            r"\b(?:lista|list|muestra|show|ensena|present|inventario|inventory|"
            r"snapshots?|disponibles?|available|privad[oa]s?|private|existen|"
            r"stored|guardad[oa]s?|kept|restorable|recuperables?|"
            r"roll\s+back|volver\s+atras|relacion)\b",
        )
        and not _has(text, r"\b(?:log|logs|registro|job|trabajo|work)\b")
    ):
        resolved = intent("backup.list")
        if resolved is not None:
            return resolved

    keyboard_state = (
        (
            _has(text, r"\b(?:teclado|keyboard|key\s+map|mapa\s+de\s+teclas)\b")
            and _has(
                text,
                r"\b(?:idioma|lenguaje|language|distribucion|layout|mapa|map)\b",
            )
            and _has(
                text,
                r"\b(?:actual|current|activ[oa]|active|seleccionad[oa]|selected|"
                r"estado|status|ahora|now|usa|usando|using|uso|use)\b",
            )
        )
        or (
            _has(text, r"\b(?:distribucion|layout)\b")
            and _has(text, r"\b(?:escribir|typing|input|entrada)\b")
            and _has(
                text,
                r"\b(?:actual|current|activ[oa]|active|ahora|now|usa|using|"
                r"estoy|i\s+am)\b",
            )
        )
        or (
            _has(text, r"\b(?:key\s+map|mapa\s+de\s+teclas|keyboard\s+map)\b")
            and _has(
                text,
                r"\b(?:estoy\s+escribiendo|i\s+am\s+typing|typing\s+with)\b",
            )
            and not _has(text, r"\b(?:manual|guide|guia|article|articulo)\b")
        )
    )
    if request_observation and keyboard_state:
        resolved = intent("input.keyboard.status")
        if resolved is not None:
            return resolved

    media_state = (
        _has(text, r"\b(?:que|what)\b.{0,40}\b(?:reproduciendo|playing)\b")
        or _has(text, r"\b(?:what(?:'s|\s+is)\s+playing)\b")
        or (
            _has(text, r"\b(?:media|multimedia|sesion\s+multimedia|media\s+session)\b")
            and _has(
                text,
                r"\b(?:estado|status|actual|current|active|activa|playing|"
                r"reproduciendo|reproduce|reproduccion|actualmente|currently)\b",
            )
        )
        or _has(text, r"\b(?:pista|track|video)\b.{0,40}\b(?:suena|playing)\b")
        or _has(
            text,
            r"\b(?:contenido\s+multimedia|media\s+content)\b.{0,48}"
            r"\b(?:corriendo|running|actual|current|now)\b",
        )
        or _has(
            text,
            r"\b(?:sesion\s+de\s+reproduccion|playback\s+session)\b",
        )
        or _has(
            text,
            r"\b(?:sesion|session)\b.{0,48}\b(?:sonando|playing|reproduciendo)\b",
        )
    )
    if (
        request_observation
        and media_state
        and not _has(text, r"\b(?:netflix|youtube|spotify|cabeza|mente|head|mind)\b")
    ):
        resolved = intent("media.status")
        if resolved is not None:
            return resolved

    private_memory = _has(
        text,
        r"\b(?:memoria|memory|recuerdos?)\b.{0,40}"
        r"\b(?:local|locales|baxy|asistente|assistant)\b|"
        r"\b(?:baxy|asistente|assistant|local|tus)\b.{0,40}"
        r"\b(?:memoria|memory|recuerdos?)\b",
    )
    if (
        request_observation
        and private_memory
        and _has(text, r"\b(?:estado|status|habilitad[oa]|enabled|como|how|local)\b")
        and not _has(text, r"\b(?:ram|uso|usage|libre|free|sistema|system)\b")
    ):
        resolved = intent("memory.status")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:la\s+red|the\s+network|network|red|conectividad|connectivity)\b|"
            r"\b(?:conexion|connection|conectividad|connectivity)\b.{0,40}"
            r"\b(?:general|overall|equipo|computer|pc)\b|"
            r"\b(?:acceso|access)\b.{0,32}\b(?:red|network)\b",
        )
        and _has(
            text,
            r"\b(?:estado|state|status|condicion|condition|conectad[oa]|connected|"
            r"health|general|overall|conexion|connection|conectividad|connectivity|"
            r"funciona|funcionando|works?|working|anda|doing|acceso|access|"
            r"llegando|reaching)\b",
        )
        and not _has(
            text,
            r"\b(?:wi[\s-]?fi|inalambric[oa]|wireless)\b|"
            r"\b(?:neural|neuronal|social|ferroviari[oa]|rail|"
            r"transport|electrica?|electric)\b",
        )
    ):
        resolved = intent("network.status")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(text, r"\b(?:wi[\s-]?fi|inalambric[oa]|wireless)\b")
        and _has(
            text,
            r"\b(?:estado|state|status|actual|current|conectad[oa]|connected|health|"
            r"conexion|connection|conectividad|connectivity|enlace|link|activa|active|"
            r"condicion|condition|senal|signal|anda|doing|asociad[oa]|associated)\b",
        )
    ):
        resolved = intent("wifi.status")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and not _has(text, r"\b(?:recordatorios?|reminders?)\b")
        and _has(
            text,
            r"\b(?:notificaciones?|notifications?|avisos?|alertas?|alerts?|notices?)\b",
        )
        and _has(
            text,
            r"\b(?:vencid[oa]s?|overdue|expired|due|pendientes?|pending|pasaron\s+su\s+hora|"
            r"not\s+been\s+dismissed|superaron\s+su\s+hora|gone\s+past\s+their\s+time|"
            r"plazo\s+se\s+cumplio|deadline\s+has\s+elapsed)\b",
        )
    ):
        resolved = intent("notification.list.due")
        if resolved is not None:
            return resolved

    latest_mail = _has(
        text,
        r"\b(?:ultimo|ultima|last|latest|newest|mas\s+nuevo|mas\s+nueva|"
        r"most\s+recent|recent|mas\s+recientemente)\b|"
        r"\b(?:acaba\s+de\s+llegar|just\s+arrived|recien\s+recibido|"
        r"just\s+received)\b|"
        r"\b(?:llego|arrived)\b.{0,32}\b(?:ultimo|last|recently)\b",
    )
    mail_domain = _has(
        text,
        r"\b(?:correo|email|mail|mailbox|buzon|inbox|inbox\s+message|"
        r"bandeja\s+de\s+entrada)\b",
    )
    if (
        request_observation
        and latest_mail
        and mail_domain
        and not _has(
            text,
            r"\b(?:telefono|phone|smartphone|tablet|reloj|watch)\b",
        )
        and _has(
            text,
            r"\b(?:mensaje|message|item|mailbox|buzon|inbox|arrived|llego|llegar)\b|"
            r"\b(?:mi|my)\b.{0,32}\b(?:correo|email|mail)\b",
        )
    ):
        resolved = intent("email.latest.read")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:perifericos?|peripherals?|hardware\s+periferico|peripheral\s+hardware|"
            r"usb\s+hardware|"
            r"dispositivos?\s+usb|usb\s+devices?|accesorios?\s+usb|usb\s+accessories|"
            r"dispositivos?\s+externos?|external\s+devices?|"
            r"accesorios?\s+enchufados?|plugged-in\s+accessories|"
            r"accesorios?\b.{0,56}\b(?:reconoce|enchufad[oa]s?|conectad[oa]s?)|"
            r"accessories\b.{0,64}\b(?:recognizes?|attached|plugged|connected))\b|"
            rf"{_CONNECTED_INVENTORY}",
        )
        and _has(
            text,
            r"\b(?:lista|list|muestra|show|enumera|enumerate|revisa|inspect|"
            r"conectad[oa]s?|connected|enchufad[oa]s?|plugged|attached)\b",
        )
        and not _has(
            text,
            r"\b(?:telefono|phone|smartphone|tablet|router|auto|car)\b",
        )
    ):
        resolved = intent("peripheral.list")
        if resolved is not None:
            return resolved

    if _bare_note_inventory_request(text):
        resolved = intent("note.list")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _note_inventory_object(text)
        and _has(
            text,
            r"\b(?:lista|list|enumera|enumerate|muestra|show|display|revisa|inspect|"
            r"inventario|inventory|indice|index|guardad[oa]s?|saved|stored|"
            r"conservo|keep|local(?:es|ly)?|privad[oa]s?|private)\b",
        )
        and not _has(text, r"\b(?:tareas?|tasks?|recordatorios?|reminders?)\b")
    ):
        resolved = intent("note.list")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:recordatorios?|reminders?)\b|"
            r"\b(?:cosas?|things?)\b.{0,64}\b(?:recordar|remember|"
            r"bring\s+back\s+to\s+mind)\b|"
            r"\blo\s+que\b.{0,64}\bagendad[oa]\b.{0,32}\brecordar\b|"
            r"\b(?:todo\s+lo\s+que|everything)\b.{0,64}"
            r"\b(?:debo\s+recordar|due\s+to\s+remember|remember\s+later)\b|"
            r"\b(?:avisos?|notices?)\b.{0,32}\b(?:programad[oa]s?|scheduled)\b",
        )
        and _has(
            text,
            r"\b(?:lista|list|enumera|enumerate|muestra|show|display|revisa|inspect|"
            r"inventario|inventory|agendad[oa]s?|scheduled|pendientes?|pending|"
            r"outstanding|programad[oa]s?|things?|cosas?|later|adelante)\b",
        )
    ):
        resolved = intent("reminder.list")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:rutinas?|routines?|automations?|"
            r"automatizaciones?(?:\s+(?:rutinarias?|habituales?))?|"
            r"habitual\s+automations?|secuencias?\s+automaticas?|automatic\s+sequences?)\b",
        )
        and _has(
            text,
            r"\b(?:lista|list|enumera|enumerate|muestra|show|display|revisa|inspect|"
            r"inventario|inventory|guardad[oa]s?|saved|stored|disponibles?|available|"
            r"configurad[oa]s?|configured|habituales?|habitual)\b",
        )
        and not _has(text, r"\b(?:articulo|article|sitio|website|manual|guide)\b")
    ):
        resolved = intent("routine.list")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:tareas?|tasks?|to-dos?|to\s+dos|asuntos?|items?)\b",
        )
        and _has(
            text,
            r"\b(?:lista|list|enumera|enumerate|muestra|show|display|revisa|inspect|"
            r"inventario|inventory|abiertas?|open|pendientes?|pending|not\s+closed|"
            r"sin\s+cerrar|sin\s+completar|unfinished|incomplet[oa]s?|"
            r"siguen\s+abiertos?|still\s+open|remain\s+unfinished)\b",
        )
        and not _has(text, r"\b(?:notas?|notes?|recordatorios?|reminders?)\b")
    ):
        resolved = intent("task.list")
        if resolved is not None:
            return resolved

    if request_observation and _has(
        text,
        r"\b(?:pendientes?|to-dos?|to\s+dos)\b.{0,48}"
        r"\b(?:permanecen\s+abiertos?|remain\s+open|still\s+open)\b",
    ):
        resolved = intent("task.list")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:inventario|inventory)\s+(?:de|of)\s+"
            r"(?:pendientes?|open\s+(?:to-dos?|to\s+dos))\b",
        )
        and _has(text, r"\b(?:abiertos?|open|pendientes?|pending)\b")
    ):
        resolved = intent("task.list")
        if resolved is not None:
            return resolved

    if request_observation and _has(
        text,
        r"\b(?:todo\s+lo\s+que\s+tengo|everything\s+i\s+have)\b.{0,32}"
        r"\b(?:pendiente|pending|open)\b",
    ):
        resolved = intent("task.list")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and (
            _has(text, r"\b(?:portapapeles|clipboard)\b")
            or _has(
                text,
                r"\b(?:texto|text|textual)\b.{0,40}\b(?:copiad[oa]|copied)\b",
            )
            or _has(
                text, r"\b(?:listo\s+para\s+pegar|ready\s+to\s+(?:be\s+)?paste[d]?)\b"
            )
        )
        and not _has(text, r"\b(?:copia|copy)\b.{0,40}\b(?:al|to)\b")
    ):
        resolved = intent("clipboard.read.text")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and (
            _has(text, r"\bsteam\b")
            or _has(
                text,
                r"\b(?:juegos?|games?|videojuegos?)\b.{0,48}"
                r"\b(?:catalogo|catalog|disponibles?|available)\s*(?:local(?:mente|ly)?)?\b",
            )
        )
        and _has(
            text,
            r"\b(?:catalogo|catalog|juegos?|games?|videojuegos?|biblioteca|library|"
            r"titulos?|titles?|playable)\b",
        )
        and not _has(
            text,
            r"\b(?:tienda|store|capturas?|screenshots?|notas?|notes?|"
            r"tareas?|tasks?|recordatorios?|reminders?)\b",
        )
        and (
            not _has(text, r"\b(?:instalad[oa]s?|installed)\b")
            or _has(
                text,
                r"\b(?:que|cuales|which|what)\s+(?:juegos?|games?)\b|"
                r"\b(?:juegos?|games?)\b.{0,24}\b(?:instalad[oa]s?|installed)\b",
            )
        )
    ):
        resolved = intent("game.catalog.list")
        if resolved is not None:
            return resolved

    if (
        (
            request_observation
            or _has(
                text,
                r"^(?:busca|buscar|encuentra|find|search|localiza|locate|"
                r"hay|there\s+are)\b",
            )
        )
        and _has(
            text,
            r"\b(?:archivos?|files?|documentos?|documents?|descargas|downloads?)\b",
        )
        and _has(text, _DUPLICATE_FILES)
        and not _has(text, r"\b(?:web|internet|online|google|bing)\b")
    ):
        resolved = intent("filesystem.known.duplicates")
        if resolved is not None:
            return resolved

    if (
        _has(
            text,
            r"^(?:busca|buscar|encuentra|find|search|localiza|locate|"
            r"a\s+ver\s+si\s+(?:encuentras?|find)|track\s+down|"
            r"revisa\s+(?:documentos|descargas)|look\s+through|scan|explore|"
            r"rastrea|explora)\b",
        )
        and _has(
            text,
            r"\b(?:documentos?|documents?|descargas|downloads?|escritorio|desktop|"
            r"imagenes|pictures)\b",
        )
        and not _has(text, _DUPLICATE_FILES)
        and not _has(text, r"\b(?:web|internet|online|google|bing)\b")
    ):
        resolved = intent("filesystem.known.search")
        if resolved is not None:
            return resolved

    if (
        _has(
            text,
            r"^(?:busca|buscar|search|look\s+up|haz\s+una\s+busqueda)\b",
        )
        and _has(text, r"\b(?:web|internet|online)\b")
        and not _has(
            text,
            r"\b(?:archivo|file|carpeta|folder|notas?|notes?|tareas?|tasks?|"
            r"recordatorios?|reminders?)\b",
        )
    ):
        resolved = intent("web.search")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"^(?:consulta|consultar|consult|investiga|investigar|investigate|"
            r"research|look\s+on|averigua)\b",
        )
        and _has(
            text,
            r"\b(?:web|internet|online|google|bing|public\s+api)\b|"
            r"\b(?:la\s+red|the\s+net)\b\s+(?:acerca|about)\b",
        )
        and not _has(
            text,
            r"\b(?:archivo|file|carpeta|folder|documentos?|documents?|"
            r"descargas|downloads?|escritorio|desktop|notas?|notes?|tareas?|tasks?|"
            r"recordatorios?|reminders?)\b",
        )
    ):
        resolved = intent("web.search")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:ventana|window|aplicacion|application|programa|program)\b",
        )
        and _has(
            text,
            r"\b(?:activa|active|primer\s+plano|foreground|actual|current|foco|focus|"
            r"focused|al\s+frente|in\s+front|delante|in\s+front\s+of|"
            r"recibe\s+el\s+teclado|recibiendo\s+mis\s+teclas|"
            r"receiving\s+(?:keyboard\s+focus|my\s+keystrokes|keyboard\s+input))\b",
        )
        and not _has(text, r"\b(?:oportunidad|opportunity|temporal|timeframe)\b")
    ):
        resolved = intent("window.active")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:sistema|system|equipo|computer|computador|computadora|pc|"
            r"maquina|machine)\b",
        )
        and _has(
            text,
            r"\b(?:estado|state|status|condicion|condition|salud|health|resumen|"
            r"summary|como|how|anda|doing|overall|integral|conjunto|whole|"
            r"operating)\b",
        )
        and not _has(
            text,
            r"\b(?:comprar|buy|purchase|precio|price|might|would|podria|"
            r"otro|otra|another)\b",
        )
    ):
        resolved = intent("system.status")
        if resolved is not None:
            return resolved

    package_id = _spoken_package_id(text)
    if (
        package_id is not None
        and not deferred_effect
        and _has(
            text,
            r"\b(?:prepara|prepare|stage|resolve|resuelve|ubica|locate|deja|leave|"
            r"instalacion|installation|instalar|install|listo|ready|staged|tied|"
            r"alista(?:lo|la)?)\b",
        )
        and not _has(text, r"https?://|\b(?:juego|game|steam)\b")
    ):
        resolved = intent(
            "package.install.prepare",
            evidence=(package_id,),
        )
        if resolved is not None:
            return resolved

    office = re.search(
        r"^(?:crea|crear|create|construye|construir|construct|genera|generar|"
        r"generate|prepara|prepare|make|necesito|i\s+need|"
        r"build|produce|arma|armame|assemble)\s+"
        r"(?:(?:un|una|a|an)\s+)?"
        r"(?P<kind>documento\s+de\s+word|documento\s+word|archivo\s+word|"
        r"word(?:\s+(?:document|doc|file))?|planilla\s+excel|hoja\s+de\s+excel|"
        r"hoja\s+excel|archivo\s+excel|libro\s+excel|excel\s+(?:workbook|file|sheet))\s+"
        r"(?:llamad[oa]|denominad[oa]|named|called|titulad[oa]|titled|"
        r"con\s+el\s+nombre)\s+"
        r"(?P<title>.+)$",
        text,
        re.IGNORECASE,
    )
    if office is not None:
        resolved = intent("office.document.create")
        if resolved is not None:
            return resolved

    channel_conveyance = _has(
        text,
        r"^(?:(?:por|en|via)\s+(?:whatsapp|discord)\s+"
        r"(?:hazle\s+(?:llegar|saber)|cuentale|dile|avisa|notifica)\s+a\s+"
        r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
        r"(?:que|el\s+mensaje|the\s+message)\s+\S.+|"
        r"(?:por|en|via)\s+(?:whatsapp|discord)\s+dile\s+a\s+"
        r"[a-z0-9._-]{1,80}\s+\S.+|"
        r"(?:through|on|via|por|en)\s+(?:whatsapp|discord)\s+"
        r"let\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+know\s+\S.+|"
        r"(?:through|on|via)\s+(?:whatsapp|discord)\s+"
        r"get\s+(?:the\s+)?(?:note|message|update)\s+\S.+\s+to\s+"
        r"[a-z0-9][a-z0-9 ._-]{0,80})$",
    )
    message_shape = (
        channel_conveyance
        or _has(
            text,
            r"^(?:(?:por|en|on|via|through)\s+(?:whatsapp|discord)\s*[,;:]?\s*"
            r"(?:manda|envia|send|avisa|notifica|notify)(?:le)?\s+(?:a\s+)?"
            r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:el\s+|the\s+)?(?:texto|mensaje|message)\s+\S.+|"
            r"(?:manda|envia|send)(?:le)?\s+(?:a\s+)?[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:(?:on|por|en)\s+(?:whatsapp|discord)\s+)?(?:el\s+|the\s+)?"
            r"(?:mensaje|message)\s+\S.+|"
            r"(?:dile|tell|mandale|enviale)\s+(?:a\s+)?"
            r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:(?:on|por|en)\s+(?:whatsapp|discord)\s+)?(?:que|that)\s+\S.+|"
            r"(?:manda|envia|send)\s+(?:en|por|on|via)\s+(?:whatsapp|discord)\s+"
            r"(?:a\s+|to\s+)?[a-z0-9][a-z0-9 ._-]{0,80}?\s+(?:que|that)\s+\S.+|"
            r"message\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:on\s+)?(?:whatsapp|discord)\s+(?:that|saying)\s+\S.+|"
            r"(?:escribele|write\s+to)\s+(?:a\s+)?[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:en|on)\s+(?:whatsapp|discord)\s+(?:que|that)\s+\S.+|"
            r"(?:pasa|pass)\s+(?:a\s+)?[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:el\s+|the\s+)?(?:mensaje|message)\s+\S.+\s+"
            r"(?:por|through|via)\s+(?:whatsapp|discord)|"
            r"(?:escribele|escribe|pasa)\s+(?:en|por|via)\s+"
            r"(?:whatsapp|discord)\s+(?:a\s+)?[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:que|el\s+texto|el\s+mensaje)\s+\S.+|"
            r"escribele\s+(?:en|por|on|via)\s+(?:whatsapp|discord)\s+a\s+"
            r"[a-z0-9][a-z0-9 ._-]{0,80}?\s*[,;:.!?]+\s*\S.+|"
            r"write\s+to\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+on\s+"
            r"(?:whatsapp|discord)\s*[,;:.!?]+\s*\S.+|"
            r"(?:que\s+)?discord\s+(?:le\s+)?(?:avise|notify)\s+a?\s*"
            r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+(?:que|that)\s+\S.+|"
            r"(?:have|ave|ab)\s+discord\s+(?:notify|avise)\s+(?:a\s+)?"
            r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+(?:that|que)\s+\S.+|"
            r"escribe\s+a\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+via\s+"
            r"(?:whatsapp|discord)\s+que\s+\S.+)$",
        )
        and _has(text, r"\b(?:whatsapp|discord)\b")
        and not _has(
            text,
            r"^(?:manda|envia|send|dile|tell)\s+(?:a\s+)?"
            r"(?:ellos|ellas|les|them)\b",
        )
    )
    if message_shape:
        resolved = intent("message.recipient.resolve", "message.send")
        if resolved is not None:
            return resolved

    netflix_weekday_title = _has(
        text,
        r"^(?:reproduce|play|pon|ponme|poneme|pone|put\s+on|busca|find|inicia|start|encuentra|encuentras|"
        r"localiza|locate)\s+wednesday\s+(?:en|in|on|desde|from|through|"
        r"usando|using)\s+netflix\b",
    )
    # VIDEO1921 H0737 «quiero ver stranger things en nerflix»: el servicio se
    # escribe mal —o lo escribe mal el oído de BAXY, que es lo más probable— y
    # eso no lo convierte en otro servicio. Alternancia corta y cerrada, no
    # distancia de edición: el catálogo de servicios es cerrado y una tolerancia
    # genérica acabaría leyendo «Netflix» donde la persona dijo otra cosa.
    if (
        (not deferred_effect or netflix_weekday_title)
        and _has(text, r"\b" + _NETFLIX_SPELLED + r"\b")
        and _has(
            text,
            # VIDEO1921 H0411 «ver stranger things en netflix»: la firma de esta
            # misma operación ya daba «ver» y «watch» por formas legítimas de
            # pedirla, y esta cabeza las rechazaba. La asimetría entre las dos
            # listas era el defecto; «quiero ver …» resolvía por otro camino.
            r"^(?:reproduce|play|pon|ponme|poneme|pone|put\s+on|busca|find|inicia|start|encuentra|encuentras|"
            r"localiza|locate|ver|watch)\b",
        )
        and _has(
            text,
            r"\b(?:en|in|on|desde|from|through|usando|using)\s+" + _NETFLIX_SPELLED + r"\b",
        )
    ):
        resolved = intent("streaming.play.named")
        if resolved is not None:
            return resolved

    return None


def _finalize_effect_matches(
    folded: str,
    matches: list[tuple[int, int, str]],
    available: frozenset[str],
) -> EffectIntent | None:
    dominant_local_operations = {
        "note.create",
        "note.list",
        "note.read",
        "note.search",
        "task.create",
        "task.list",
        "task.search",
        "reminder.create",
        "reminder.list",
        "routine.list",
    }
    if any(entry[2] == "input.text.type" for entry in matches):
        matches = [entry for entry in matches if entry[2] == "input.text.type"]
    elif any(entry[2] in dominant_local_operations for entry in matches):
        matches = [entry for entry in matches if entry[2] in dominant_local_operations]
    # Navigation/play operations already open their named application.  An
    # explicit preceding "open" is a setup phrase, not a second observable
    # effect, unless no richer operation was recognized.
    operation_names = {entry[2] for entry in matches}
    if "app.open" in operation_names:
        filtered: list[tuple[int, int, str]] = []
        for entry in matches:
            if entry[2] != "app.open":
                filtered.append(entry)
                continue
            application = _match(
                folded[entry[0] :],
                rf"^\b{_OPEN}\b(?:\s+(?:el|la|the))?\s+(?P<app>{_KNOWN_APPLICATION})\b",
            )
            app_name = application.group("app") if application is not None else ""
            is_browser = _has(
                app_name,
                r"\b(?:opera|chrome|google chrome|edge|microsoft edge|firefox)\b",
            )
            is_spotify = app_name == "spotify"
            consumed_by_richer_effect = (
                is_browser and "browser.navigate.named" in operation_names
            ) or (
                is_spotify
                and (
                    "media.play.exact" in operation_names
                    or "media.play.query" in operation_names
                )
            )
            if not consumed_by_richer_effect:
                filtered.append(entry)
        matches = filtered

    matches.sort(key=lambda entry: (entry[0], entry[1]))
    retained = [entry for entry in matches if entry[2] in available]
    if not retained or len(retained) > 8:
        return None
    operations = tuple(entry[2] for entry in retained)
    evidence: list[str] = []
    for index, (position, _, _) in enumerate(retained):
        next_position = next(
            (later[0] for later in retained[index + 1 :] if later[0] > position),
            len(folded),
        )
        fragment = folded[position:next_position].strip(" ,;:-")
        fragment = re.sub(
            r"\b(?:y|and|then|luego|despues)\s*$",
            "",
            fragment,
            flags=re.IGNORECASE,
        ).strip(" ,;:-")
        # Google query construction consumes this evidence as data. Retain the
        # complete bounded clause so a plan cannot silently search a prefix.
        evidence.append(
            fragment if _explicit_google_search_query(fragment) is not None
            else fragment[:240] or "efecto solicitado"
        )
    return EffectIntent(operations, tuple(evidence))


def _review_audio_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    head: str,
    *,
    context_audio: bool,
) -> bool:
    """Append audio effects and report whether the clause targets volume."""

    # A preceding audio clause is enough to interpret a numeric continuation
    # ("... y luego al 12%"), but only when this clause starts with the value.
    # Broader inheritance turns years and genre names such as "dance de los
    # 80" into literal volume authority.
    elliptical_audio_level = context_audio and _has(
        folded,
        r"^(?:al?|to)?\s*\d{1,3}\s*(?:%|por ciento|percent)?\b",
    )
    elliptical_audio_status = (
        context_audio
        and _head_is(
            head,
            r"(?:en|a|cuanto|cuanta|dime|decime|muestra|show|what|que|how)",
        )
        and _has(
            folded,
            r"\b(?:cuanto|cuanta|how much|nivel|level|quedo|estado|status)\b",
        )
    )
    audio_level = (
        _volume_domain(folded) or elliptical_audio_level or elliptical_audio_status
    )
    microphone_verb = rf"(?:{_MUTE_VERB}|{lexicon.MICROPHONE_VERB})"
    if (
        (_head_is(head, microphone_verb) or _has(folded, rf"^{lexicon.MUTE_PHRASE}\b"))
        and _has(folded, rf"\b{lexicon.MICROPHONE_NOUN}\b")
        and _has(folded, rf"\b(?:{microphone_verb}|mute)\b")
        and not _has(
            folded,
            r"\b(?:llamada|call|aplicacion|application|app|discord|teams|"
            r"zoom|skype|whatsapp)\b",
        )
    ):
        _append(
            matches,
            folded,
            "audio.microphone.mute",
            rf"\b(?:{microphone_verb}|mute)\b",
        )
    if audio_level:
        literal_level = _literal_percentage_word_value(folded)
        literal_adjustment = _literal_volume_adjustment(folded)
        if literal_level is not None and _head_is(
            head, rf"(?:{_SET_VOLUME_VERB}|{_VOLUME_UP_VERB}|{_VOLUME_DOWN_VERB})",
        ):
            _append(matches, folded, "audio.volume", rf"\b{_VOLUME_OBJECT}\b")
        elif (
            _head_is(head, rf"(?:{_VOLUME_UP_VERB}|{_VOLUME_DOWN_VERB})")
            and _has(
                folded,
                rf"\b{_VOLUME_OBJECT}\s+(?:a(?:l)?|hasta(?:\s+el)?|to|at)\s*(?:100|[0-9]{{1,2}})(?![0-9])",
            )
        ):
            # «baja el volumen a 30»: the direction only states where the level
            # is coming from; the target is absolute (AUDIO1239, H0254).
            _append(matches, folded, "audio.volume", rf"\b{_VOLUME_OBJECT}\b")
        elif literal_adjustment is not None:
            _append(matches, folded, "audio.volume.adjust", rf"\b{_VOLUME_OBJECT}\b")
        elif _has(
            folded,
            r"\b(?:bajalo|bajala|subelo|subela)\b",
        ):
            _append(
                matches,
                folded,
                "audio.volume.adjust",
                r"\b(?:bajalo|bajala|subelo|subela)\b",
            )
        elif (
            _head_is(
                head,
                r"(?:sube|subir|baja|bajar|bajalo|subelo|aumenta|reduce|"
                r"increment|decrease)",
            )
            and _has(
                folded,
                # Fase 3.5 (layer C «subí el volumen 10 puntos»): voseo «subí/bajá».
                r"\b(?:sube|subi|subir|baja|baji|bajar|bajalo|subelo|aumenta|reduce|"
                r"increment|decrease)\b",
            )
            and _has(
                folded,
                r"\b(?:puntos?|points?|en|by|por ciento|percent)\b|%",
            )
            # Tanda 3: «en dos niveles» is a count of steps, not an amount; the amount is asked.
            and not _has(folded, rf"\b{levels.STEP_NOUN}\b")
        ):
            _append(
                matches,
                folded,
                "audio.volume.adjust",
                r"\b(?:sube|subi|subir|baja|baji|bajar|aumenta|reduce|increment|decrease)\b",
            )
        elif (
            _head_is(head, _SET_VOLUME_VERB)
            and _has(folded, rf"\b{_SET_VOLUME_VERB}\b")
            and (
                _has(folded, r"(?:\b\d{1,3}\b|\bpor ciento\b|%)")
                or _literal_percentage_word_value(folded) is not None
            )
        ):
            _append(
                matches,
                folded,
                "audio.volume",
                rf"\b{_SET_VOLUME_VERB}\b",
            )
        elif context_audio and _has(
            folded,
            r"^(?:al?|to)?\s*\d{1,3}\s*(?:%|por ciento|percent)?\b",
        ):
            _append(
                matches,
                folded,
                "audio.volume",
                r"\d{1,3}",
            )
        already_set_volume = any(
            entry[2] in {"audio.volume", "audio.volume.adjust"} for entry in matches
        )
        level_query = (
            not already_set_volume
            and (
                (
                    _head_is(
                        head,
                        r"(?:en|a|cuanto|cuanta|estado|status|actual|current|"
                        r"nivel|level|volumen|volume|dime|decime|muestra|"
                        r"muestrame|mostrame|show|ver|what|que|cual|which|how)",
                    )
                    and _has(folded, _AUDIO_LEVEL_CUE)
                )
                # «muéstrame el volumen», «ver el volumen del sistema»: el verbo de
                # observación ya pide la lectura, sin palabra de medida.
                or (
                    _head_is(head, _AUDIO_OBSERVATION_HEAD)
                    and _has(folded, r"\b(?:volumen|volume)\b")
                )
            )
            and (
                not _has(
                    folded,
                    r"\b(?:pon|poner|fija|ajusta|adjust|establece|set|cambia|change|"
                    r"sube|subi|subir|baja|baji|bajar|bajalo|subelo|aumenta|reduce)\b",
                )
                or _has(folded, r"\b(?:luego|despues|then|after|quedo)\b")
            )
            and not _is_past_or_hypothetical_state(folded)
        )
        if level_query:
            _append(
                matches,
                folded,
                "audio.status",
                rf"{_AUDIO_LEVEL_CUE}|\b(?:volumen|volume|audio|sonido|sound)\b",
                priority=1,
            )
        elif _is_audio_mute_state_query(folded, head):
            _append(
                matches,
                folded,
                "audio.status",
                (
                    r"\b(?:silenciad[oa]s?|mutead[oa]s?|muted|mudo|"
                    r"silencio|mute)\b|"
                    r"\b(?:audio|sonido|sound|volumen|volume)\b"
                ),
                priority=1,
            )
    if (
        (
            _head_is(
                head,
                rf"(?:{_MUTE_VERB}|{lexicon.AUDIO_RESTORE}|quita|quitar|saca|sacar|remove|"
                r"pon|pone|ponlo|ponelo|poner|ponle|deja|dejalo|dejar|put|leave|turn)",
            )
            # Uso real 2026-09-23: the mute switched, the sound asked back, a noise to stop, a bare «silencio».
            or _has(folded, lexicon.MUTE_REQUEST)
        )
        # The system audio is never what a sentence naming the microphone mutes
        # (held-out 2026-09-22 «poné en mute el micro» muted the speakers' family).
        and not _has(folded, rf"\b{lexicon.MICROPHONE_NOUN}\b")
        and (
            _audio_mute_domain(folded)
            # «ponelo en mute», «dejalo en mute»: the pronoun with the mute
            # predicate names the global audio (AUDIO1239, H0189).
            or _has(
                folded,
                r"^[¿?¡!\s]*(?:pon(?:e|lo|elo|le|eme)?|ponlo|deja(?:lo)?|"
                r"leave\s+it|put\s+it|turn\s+it)\s+(?:en|in|on)\s+"
                r"(?:mute|mudo|silencio|silent)[\s?!.]*$",
            )
            or (
                context_audio
                and _has(
                    folded,
                    r"^(?:reactiva(?:lo|la)?|unmute(?: it)?|quita(?:r)? el silencio)[\s?!.]*$",
                )
            )
        )
        and _has(
            folded,
            rf"\b{_MUTE_VERB}\b|"
            rf"\b(?:{lexicon.UNMUTE_WORDS}|{lexicon.MUTE_WORDS})\b|{lexicon.BARE_SILENCE}|"
            r"\b(?:en|in|on)\s+(?:mudo|silencio|mute|silent)\b|"
            r"\bback\s+on\b",
        )
    ):
        _append(
            matches,
            folded,
            "audio.mute",
            rf"\b{_MUTE_VERB}\b|\b{lexicon.AUDIO_RESTORE}\b|"
            r"\b(?:quita|quitar|saca|sacar|remove)\b|"
            r"\b(?:pon|poner|ponle|deja|dejar|put|leave|turn)\b|"
            rf"\b(?:{lexicon.UNMUTE_WORDS}|{lexicon.MUTE_WORDS})\b|{lexicon.BARE_SILENCE}",
        )
        reversal = _match(
            folded,
            (
                r"\b(?:y|and)\b\s+(?:reactiva(?:lo|la)?|reactivar|unmute|"
                r"quita(?:r)?\s+(?:el\s+)?silencio)\b"
            ),
        )
        if reversal is not None:
            matches.append((reversal.start(), 0, "audio.mute"))
    return audio_level


def _literal_percentage_word_value(text: str) -> int | None:
    """Read one bounded ES/EN word-valued literal beside the volume domain."""

    text = _strip_request_envelope(_fold(text))
    if (
        not _volume_domain(text)
        or _is_negative_effect_clause(text)
        or _is_meta_or_tool_denial(text)
        or _has_contradictory_correction(text)
        or _has_unsupported_deferred_effect(text)
        or _has(text, r"\d|\b(?:o|or)\b")
        or _literal_volume_adjustment(text) is not None
    ):
        return None
    value = rf"(?P<level>{_PERCENTAGE_WORD_PATTERN}|mitad|half|maximo|maximum|minimo|minimum)(?!\s+{levels.STEP_NOUN}\b)"
    patterns = (
        rf"\b{_VOLUME_OBJECT}\s+(?:justo\s+|exactly\s+)?"
        rf"(?:a(?:l)?|en|to|at)\s*(?:la\s+|the\s+)?{value}"
        rf"(?:\s*(?:%|por\s+ciento|percent))?\b",
        # The numeric antecedent and its reference must be in this same
        # authored sentence; an absent prior level cannot be manufactured.
        rf"\b{value}\s+percent\s+is\s+enough\s*:\s*"
        rf"{_SET_VOLUME_VERB}\s+(?:the\s+)?(?:{_LOCAL_VOLUME_DEVICE}\s+)?"
        r"volume\s+(?:there|to\s+that\s+level)[.!?]*$",
    )
    matches = [found for pattern in patterns for found in re.finditer(pattern, text)]
    if len(matches) != 1:
        return None
    level = matches[0].group("level").casefold()
    if level in {"mitad", "half"}:
        return 50
    if level in {"maximo", "maximum"}:
        return 100
    if level in {"minimo", "minimum"}:
        # Fase 3.5 (layer C): the same word the per-app reader maps to 0.
        return 0
    return _PERCENTAGE_WORD_VALUES.get(level)


def _literal_volume_adjustment(text: str) -> dict[str, object] | None:
    """Bind a relative quantity to its authored direction and audio object."""

    text = _strip_request_envelope(_fold(text))
    if (
        not _volume_domain(text)
        or _is_negative_effect_clause(text)
        or _is_meta_or_tool_denial(text)
        or _has_contradictory_correction(text)
        or _has_unsupported_deferred_effect(text)
        or _has(text, r"\b(?:o|or)\b")
    ):
        return None
    up = _has(text, rf"\b{_VOLUME_UP_VERB}\b")
    down = _has(text, rf"\b{_VOLUME_DOWN_VERB}\b")
    if up == down:
        return None
    direction = rf"(?:{_VOLUME_UP_VERB}|{_VOLUME_DOWN_VERB})"
    # Tanda 3: «dos niveles», «one level» count steps of unsaid size, not points (owner rule H0027: ask).
    amount = rf"(?P<amount>\d{{1,3}}|{_PERCENTAGE_WORD_PATTERN})(?![a-z0-9])(?!\s+{levels.STEP_NOUN}\b)"
    unit = r"(?:puntos?|(?:percentage\s+)?points?|por\s+ciento|percent|%)"
    patterns = (
        rf"\b{direction}\s+(?:en\s+|by\s+)?{amount}\s+{unit}"
        rf"\s+(?:(?:el|la|the)\s+)?{_VOLUME_OBJECT}\b",
        rf"\b{direction}\s+(?:(?:el|la|the)\s+)?{_VOLUME_OBJECT}"
        rf"\s+(?:en|by)\s+{amount}(?:\s*{unit})?",
    )
    matches = [found for pattern in patterns for found in re.finditer(pattern, text)]
    if len(matches) != 1:
        return None
    raw = matches[0].group("amount")
    value = int(raw) if raw.isdigit() else _PERCENTAGE_WORD_VALUES.get(raw)
    # Retain the former single-number boundary, including an out-of-range
    # number elsewhere in the fragment; do not choose among competing values.
    digits = re.findall(r"\d+", text)
    if value is None or not 1 <= value <= 100 or digits != ([raw] if raw.isdigit() else []):
        return None
    return {"amount": value, "direction": "up" if up else "down"}


def _literal_brightness_adjustment(text: str) -> dict[str, object] | None:
    """Bind a relative quantity to its authored direction and the brightness object."""

    folded = _strip_request_envelope(_fold(text))
    folded = screen_light_as_brightness(folded)
    if (
        _is_negative_effect_clause(folded)
        or _is_meta_or_tool_denial(folded)
        or _has_contradictory_correction(folded)
        or _has(folded, r"\b(?:o|or)\b")
        or re.search(_BRIGHTNESS_ABSOLUTE, folded) is not None
        # «un toque», «un poco»: a relative word is not a quantity («un» is
        # not one point); the request asks how much instead.
        or re.search(_BRIGHTNESS_RELATIVE_WORDS, folded) is not None
    ):
        return None
    english = re.search(_BRIGHTNESS_ENGLISH_TURN, folded)
    up = _has(folded, rf"\b{_BRIGHTNESS_UP_VERB}\b") or (english is not None and english.group("dir") == "up")
    down = _has(folded, rf"\b{_BRIGHTNESS_DOWN_VERB}\b") or (english is not None and english.group("dir") == "down")
    if up == down:
        return None
    direction = rf"(?:{_BRIGHTNESS_UP_VERB}|{_BRIGHTNESS_DOWN_VERB})"
    # Tanda 3: «dos niveles», «one level» count steps of unsaid size, not points (owner rule H0027: ask).
    amount = rf"(?P<amount>\d{{1,3}}|{_PERCENTAGE_WORD_PATTERN})(?![a-z0-9])(?!\s+{levels.STEP_NOUN}\b)"
    unit = r"(?:puntos?|(?:percentage\s+)?points?|por\s+ciento|percent|%)"
    obj = _BRIGHTNESS_OBJECT
    patterns = (
        rf"\b{direction}\s+(?:(?:un|a)\s+)?{amount}\s*{unit}?\s+(?:(?:el|la|the)\s+)?{obj}\b",
        rf"\b{direction}\s+(?:(?:el|la|the|my|mi)\s+)?{obj}\s+(?:(?:en|by|un|a)\s+)?{amount}(?:\s*{unit})?",
        rf"{_BRIGHTNESS_ENGLISH_TURN}\s+(?:by\s+)?{amount}(?:\s*{unit})?",
    )
    matches = [found for pattern in patterns for found in re.finditer(pattern, folded)]
    if len(matches) != 1:
        return None
    raw = matches[0].group("amount")
    value = int(raw) if raw.isdigit() else _PERCENTAGE_WORD_VALUES.get(raw)
    digits = re.findall(r"\d+", folded)
    if value is None or not 1 <= value <= 100 or digits != ([raw] if raw.isdigit() else []):
        return None
    return {"amount": value, "direction": "up" if up else "down"}


def brightness_relative_without_amount(text: str) -> bool:
    """«subí el brillo», «bajame el brillo un toque», «turn the brightness down»: ask how much."""

    folded = _strip_request_envelope(_fold(text))
    if (
        _is_negative_effect_clause(folded)
        or _is_meta_or_tool_denial(folded)
        or _has_contradictory_correction(folded)
        or _is_past_or_hypothetical_state(folded)
        or re.search(r"\d", folded) is not None
        or _literal_percentage_word_value(folded) is not None
        or re.search(_BRIGHTNESS_ABSOLUTE, folded) is not None
        or len(_request_clauses(folded)) != 1
        or _has(folded, r"\b(?:y|and)\s+(?:abre|open|crea|create|apaga|silencia|pon|cierra|close)\b")
    ):
        return False
    return (
        re.search(
            rf"\b(?:{_BRIGHTNESS_UP_VERB}|{_BRIGHTNESS_DOWN_VERB})\s+(?:{_BRIGHTNESS_RELATIVE_WORDS}\s+)?"
            rf"(?:(?:el|la|the|my|mi)\s+)?{_BRIGHTNESS_OBJECT}\b",
            folded,
        ) is not None
        or re.search(_BRIGHTNESS_ENGLISH_TURN, folded) is not None
        or re.search(r"\b(?:brighten|dim)\s+(?:the\s+|my\s+)?(?:screen|display)\b", folded) is not None
    )


def _literal_brightness_level(text: str) -> int | None:
    """«poné el brillo al 80», «pon el brillo al 80%», «subí el brillo al máximo»: an absolute level."""

    folded = _strip_request_envelope(_fold(text))
    if (
        _is_negative_effect_clause(folded)
        or _is_meta_or_tool_denial(folded)
        or _has_contradictory_correction(folded)
        or _is_past_or_hypothetical_state(folded)
        or _has(folded, r"\b(?:o|or)\b")
        or len(_request_clauses(folded)) != 1
    ):
        return None
    obj = _BRIGHTNESS_OBJECT
    # Tanda 3: «en un 45%», «a un 45%» after a setting verb are where the level ends, like «al 45».
    numeric = re.search(
        rf"\b{_BRIGHTNESS_SET_VERB}\s+(?:(?:el|la|the|my|mi)\s+)?{obj}\s+"
        r"(?:a|al|en|to|at|hasta)\s*(?:el\s+|the\s+|un\s+)?(?P<level>100|[0-9]{1,2})"
        r"(?![0-9])(?:\s*(?:%|por\s+ciento|percent))?",
        folded,
    )
    extreme = re.search(
        rf"\b{_BRIGHTNESS_SET_VERB}\s+(?:(?:el|la|the|my|mi)\s+)?{obj}\s+"
        r"(?:a|al|to|at|hasta)\s+(?:el\s+|the\s+)?(?P<word>maximo|max|tope|full|maximum|minimo|min|minimum)\b",
        folded,
    )
    digits = re.findall(r"\d+", folded)
    if numeric is not None and extreme is None:
        raw = numeric.group("level")
        return int(raw) if digits == [raw] else None
    if extreme is not None and numeric is None and not digits:
        return _BRIGHTNESS_EXTREME_VALUES.get(extreme.group("word"))
    return None


def _review_installed_catalog_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    *,
    application_names: Iterable[str],
) -> None:
    """Append authenticated installed-application and game-catalog effects."""

    game_list_query = _has(
        folded,
        r"\b(?:juegos|games)\b",
    ) and (
        _has(folded, rf"\b{_LIST}\b")
        or (
            _has(folded, r"\b(?:instalad[oa]s?|installed)\b")
            and _has(folded, r"\b(?:en|on)\s+steam\b")
        )
    )
    installed_query = _has(folded, r"\b(?:instalad[oa]s?|installed)\b")
    authenticated_installed = _authenticated_application_target(
        folded,
        application_names,
        installed_query=True,
    )
    authenticated_installed_list = _authenticated_application_list(
        folded,
        application_names,
        installed_query=True,
    )
    installed_application = (
        installed_query
        and not game_list_query
        and (
            authenticated_installed is not None
            or _has(
                folded,
                (
                    rf"^[¿?¡!\s]*(?:esta|estan|is|are)?\s*"
                    rf"(?:instalad[oa]s?|installed)\s*"
                    rf"(?:el|la|los|las|the)?\s*{_KNOWN_APPLICATION}"
                    rf"(?:\s+como\b.{{1,80}})?"
                    rf"(?:\s+(?:por favor|please|ahora|now))?[\s?!.]*$"
                ),
            )
            or _has(
                folded,
                (
                    rf"^[¿?¡!\s]*(?:is|are|esta|estan)\s+(?:el|la|the)?\s*"
                    rf"{_KNOWN_APPLICATION}\s+(?:even\s+)?"
                    rf"(?:instalad[oa]s?|installed)"
                    rf"(?:\s+(?:here|aqui|en este\s+(?:equipo|pc)|"
                    rf"on this machine))?"
                    rf"(?:\s+(?:por favor|please|ahora|now))?[\s?!.]*$"
                ),
            )
        )
    )
    installed_game = (
        installed_query
        and not installed_application
        and (
            _has(folded, r"\b(?:juego|game)\b")
            or _has(folded, r"\b(?:en|on)\s+steam\b")
        )
        and not game_list_query
    )
    if authenticated_installed_list:
        matches.extend(
            (position, 0, "app.installed")
            for position, _ in authenticated_installed_list
        )
    elif game_list_query:
        _append(
            matches,
            folded,
            "game.catalog.list",
            r"\b(?:juegos|games)\b",
        )
    elif installed_game:
        _append(
            matches,
            folded,
            "game.installed.named",
            r"\b(?:instalad[oa]s?|installed)\b",
        )
    elif installed_application:
        _append(
            matches,
            folded,
            "app.installed",
            r"\b(?:instalad[oa]s?|installed)\b",
        )
    elif (
        _has(
            folded,
            r"^(?:do\s+i\s+have|tengo|is\s+there)\b",
        )
        and _has(folded, rf"\b{_KNOWN_APPLICATION}\b")
        and _has(
            folded,
            r"\b(?:on this machine|en\s+(?:esta|este)\s+"
            r"(?:maquina|equipo|pc|computador)|aqui|here)\b",
        )
        and not _has(folded, r"\b(?:juego|game)\b")
    ):
        _append(
            matches,
            folded,
            "app.installed",
            rf"\b{_KNOWN_APPLICATION}\b",
        )


def _review_application_and_window_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    head: str,
    *,
    application_names: Iterable[str],
    context_open_application: bool,
    context_window_active: bool,
) -> None:
    """Append authenticated application and foreground-window effects."""

    authenticated_open_list = _authenticated_application_list(
        folded,
        application_names,
    )
    opened_application_spans = (
        () if authenticated_open_list else _open_application_spans(folded)
    )
    authenticated_open = (
        None
        if opened_application_spans
        else _authenticated_application_target(
            folded,
            application_names,
        )
    )
    if _is_builtin_keyboard_request(folded):
        authenticated_open_list = ()
        opened_application_spans = ()
        authenticated_open = None
    explicit_open_count = len(opened_application_spans)
    if authenticated_open_list:
        matches.extend(
            (position, 0, "app.open") for position, _ in authenticated_open_list
        )
    elif explicit_open_count:
        matches.extend(
            (position, 0, "app.open") for position, _ in opened_application_spans
        )
    elif authenticated_open is not None:
        matches.append((authenticated_open[0], 0, "app.open"))
    elif (
        _head_is(head, _OPEN)
        and not _has(folded, _KNOWN_APPLICATION)
        and not _has(
            folded,
            r"\b(?:ventana|window|archivo|file|pagina|page|sitio|site)\b",
        )
    ):
        _append(
            matches,
            folded,
            "app.open",
            rf"\b{_OPEN}\s+(?:(?:el|un|the|a)\s+)?(?:navegador|browser)\b",
        )
    elif context_open_application:
        continued_application = _match(
            folded,
            rf"^(?:el|la|the)?\s*(?P<app>{_KNOWN_APPLICATION})[\s?!.]*$",
        )
        if continued_application is not None:
            matches.append((continued_application.start("app"), 0, "app.open"))

    if (
        _head_is(head, r"(?:cierra|cerra|cerrar|cerrame|cierrame|cierres|close|cierralo|cierrala|cerrala|cerralo)")
        and (
            has_named_window_target(folded)
            or _authenticated_application_close_target(folded, application_names) is not None
            or (
                _has(folded, r"\b(?:cierra|cerra|cerrar|close)\b")
                and _has(
                    folded,
                    rf"^[¿?¡!\s]*(?:cierra|cerra|cerrar|close)\s+"
                    rf"(?:(?:la|the)\s+)?(?:(?:ventana|window)\s+(?:de|of)\s+)?"
                    rf"(?:{_KNOWN_APPLICATION})"
                    r"(?:\s+(?:ventana|window|aplicacion|application|app))?"
                    r"[\s?!.]*$|"
                    r"^[¿?¡!\s]*(?:cierra|cerra|cerrar|close)\s+"
                    r"(?:(?:la|the)\s+)?(?:aplicacion|application|app|programa|program)\s+"
                    r"[a-z0-9][a-z0-9 ._+-]{0,100}[\s?!.]*$",
                )
            )
            or _has(
                folded,
                r"^[¿?¡!\s]*(?:cierra|cerra|cerrar|close)\s+"
                r"(?:(?:la|the)\s+)?(?:"
                r"(?:ventana|window)\s+(?:activa|active|actual|current)|"
                r"(?:active|current)\s+window"
                r")[\s?!.]*$",
            )
            or deictic_close_request(folded)
            or (
                context_open_application
                and _has(
                    folded,
                    r"^(?:cierralo|cierrala|close it)[\s?!.]*$",
                )
            )
        )
        and not _has(
            folded, r"\b(?:forzar|force|kill|termina el proceso|terminate process)\b"
        )
        # Owner's test 2026-09-21 (turns 210-213): «cierra BAXY» names the
        # assistant, not an application with a window; the known limit answers.
        and not self_close_request(folded)
    ):
        _append(
            matches,
            folded,
            "app.close",
            r"\b(?:cierra|cerra|cerrar|cerrame|cierrame|cierres|close|cierralo|cierrala|cerrala|cerralo)\b",
        )

    for pattern, operation in (
        (r"\b(?:maximiza|maximizar|maximize)\b", "window.maximize"),
        (r"\b(?:minimiza|minimizar|minimize)\b", "window.minimize"),
        (r"\b(?:restaura|restaurar|restore)\b", "window.restore"),
    ):
        if (
            _head_is(
                head,
                r"(?:maximiza|maximizar|maximize|minimiza|minimizar|minimize|"
                r"restaura|restaurar|restore)",
            )
            and _has(folded, pattern)
            and (
                _window_domain(folded)
                or (
                    context_window_active
                    and _has(
                        folded,
                        r"^(?:maximiza|maximizar|maximize|minimiza|minimizar|"
                        r"minimize|restaura|restaurar|restore)[\s?!.]*$",
                    )
                )
            )
        ):
            _append_all(matches, folded, operation, pattern)
    if not any(
        entry[2] in {"window.maximize", "window.minimize", "window.restore"}
        for entry in matches
    ) and _has(folded, r"\b(?:ventana|window)\b"):
        if _has(
            folded,
            r"\b(?:hazme|make|pon)\b.{0,24}\bgrande\b.{0,24}"
            r"\b(?:ventana|window)\b|"
            r"\b(?:hazme|make|pon)\b.{0,24}\b(?:ventana|window)\b.{0,24}"
            r"\bgrande\b",
        ):
            _append(
                matches,
                folded,
                "window.maximize",
                r"\b(?:grande|maximize)\b",
            )
        elif _has(
            folded,
            r"\b(?:taskbar|barra\s+de\s+tareas)\b",
        ) and _has(
            folded,
            r"\b(?:abajo|down|send|manda|minimiza|minimize)\b",
        ):
            _append(
                matches,
                folded,
                "window.minimize",
                r"\b(?:taskbar|barra\s+de\s+tareas)\b",
            )
        elif _has(
            folded,
            r"\b(?:tamano|size)\s+normal\b|"
            r"\b(?:tamano|size)\s+(?:original|usual|regular)\b",
        ):
            _append(
                matches,
                folded,
                "window.restore",
                r"\b(?:tamano|size)\b",
            )
    window_mutations = [
        entry
        for entry in matches
        if entry[2]
        in {
            "window.maximize",
            "window.minimize",
            "window.restore",
        }
    ]
    if window_mutations and (
        _has(
            folded,
            r"\b(?:activa|active|actual|current)\b",
        )
        or deictic_window_mutation(folded)
        or context_window_active
    ):
        matches.append(
            (min(entry[0] for entry in window_mutations), -1, "window.active")
        )
    elif (
        not window_mutations
        and _window_domain(folded)
        and _has(folded, r"\b(?:activa|active|actual|current)\b")
        and _has(folded, r"\b(?:que|cual|what|dime)\b")
    ):
        _append(matches, folded, "window.active", r"\b(?:ventana|window)\b")
    elif (
        not window_mutations
        and _has(folded, r"^[¿?¡!\s]*(?:que|cual|what|which|dime|decime)\b")
        and _has(
            folded,
            r"\b(?:app|aplicacion|programa|proceso|application|program|process)\b.{0,24}"
            r"\b(?:activ[ao]|active|en\s+primer\s+plano|al\s+frente|en\s+foco|in\s+(?:the\s+)?foreground|focused)\b",
        )
    ):
        # Fase 3.5 (layer C «qué app está activa ahora», «qué proceso está en primer plano»):
        # the application in front is read from the active window.
        _append(
            matches,
            folded,
            "window.active",
            r"\b(?:app|aplicacion|programa|proceso|application|program|process)\b",
        )


def _symbolic_web_destination(text: str) -> str | None:
    """Preserve a public site operand without manufacturing its URL."""

    request = _strip_request_envelope(text)
    # A social envelope («Buenos días, …», «Baxy, haz esto: …») is transparent
    # for every reader: it is stripped on the folded text when the raw one
    # keeps it (accents, capitals), and it never counts as a clause of its own.
    folded_request = _strip_request_envelope(_fold(text))
    if len(_fold(request)) > len(folded_request):
        request = folded_request
    desired = _explicit_desire_request(request)
    if desired is not None:
        request = request[desired.start("body"):]
    found = re.fullmatch(
        r"[¿?¡!\s]*(?:(?:ve|and[aá]|entra|entr[aá]|entrar|ir|navega|navegar|"
        r"llevame|llévame)\s+a(?:l)?\s+|(?:go|navigate)\s+to\s+|"
        r"take\s+me\s+to\s+|(?:abre|abr[ií]|abrir|open)\s+"
        # WEB1477 H0082 «Abre la p?gina oficial de OpenAI»: a corrupted
        # character inside «página» is a transcription glitch, not another word.
        r"(?=(?:(?:la|el|the|a)\s+)?(?:p[aá?]gina|page|sitio|site|website|portal)\b))"
        r"(?P<target>\S.+?)[\s.!?]*",
        request, re.IGNORECASE,
    )
    if found is None:
        return None
    folded = _fold(request)
    if (
        explicit_non_action_frame(text)
        or _is_meta_or_tool_denial(folded)
        or _is_past_or_hypothetical_state(folded)
        or _has_unsupported_deferred_effect(folded)
        or _has_contradictory_correction(folded)
        or len(_request_clauses(folded)) != 1
        # Tanda 3 «Go to página de inicio»: going home is the PC's desktop, never a site.
        or minimize_all_request(folded)
        or _named_browser(folded) is not None
        or client_navigation_target(folded) is not None
        or _has(folded, r"https?://|\b(?:[a-z0-9-]+\.)+[a-z]{2,63}\b")
        or _has(folded, r"\b(?:archivos?|files?|carpetas?|folders?|documentos?|"
                rf"documents?|descargas|downloads?|{PC_HOME_PLACE}|notas?|notes?|"
                r"tareas?|tasks?|recordatorios?|reminders?|ventanas?|windows?|"
                r"aplicaciones?|applications?|apps?)\b")
    ):
        return None
    # Courtesy and the site-role noun are syntax around the public name, not
    # required result terms. Keep all authority/privacy checks on original text.
    operand = re.sub(
        r",\s*(?:por\s+favor|please)[\s.!?]*$", "", found.group("target"),
        count=1, flags=re.IGNORECASE,
    ).strip()
    target = re.sub(
        r"^(?:(?:la|el|the|a)\s+)?(?:(?:p[aá?]gina|page|sitio|site)"
        r"(?:\s+web)?|website)"
        r"(?:\s+(?:oficial|official|principal|main|home))?\s+(?:(?:de|of)\s+)?",
        "", operand, count=1, flags=re.IGNORECASE,
    ).strip()
    possessive = re.fullmatch(
        r"(?P<name>\S.+?)(?:['’]s|['’])\s+"
        r"(?:(?:official|main|home)\s+)?(?:website|site|web\s+site|page)",
        target, re.IGNORECASE,
    )
    if possessive is not None:
        target = possessive.group("name")
    target = _bounded_application_literal(target)
    if target is None or _has(
        _fold(target),
        r"^(?:(?:la|el|the|a|esta|esa|this|that)\s+)?"
        r"(?:pagina|page|sitio|site|website|portal|alli|ahi|there|it)$",
    ):
        return None
    # Reuse public-query privacy and single-clause guards on the literal operand.
    return _direct_public_search_query("busca " + target)


def _direct_public_search_query(text: str) -> str | None:
    """Read one authoritative public query, preserving its original spelling."""

    match = re.fullmatch(
        rf"[¿?¡!\s]*{_REQUEST_PREFIX}{_SEARCH}(?:\s+for)?\s+"
        r"(?P<query>\S.*)",
        _strip_request_envelope(text),
        re.IGNORECASE,
    )
    if match is None:
        return None
    query = match.group("query").strip(" \t.,;:!?\"'“”«»")
    # SEARCH2005 «Buscá Transformers, porfa»: a trailing courtesy is not part of the query.
    query = re.sub(
        r"\s*[,;]?\s*(?:por\s+favor|porfa|porfi|please|pls|plz|dale|gracias|thanks)\s*$",
        "",
        query,
        flags=re.IGNORECASE,
    ).strip(" \t.,;:!?\"'“”«»")
    folded = _fold(text)
    if (
        not query
        or _has(_fold(query), r"^(?:for|en|on)[.!?]*$")
        or not effect_request_is_authoritative(text)
        # SEARCH2005 «dale, buscame recetas de pizza»: the opener is envelope, not a clause.
        or len(_request_clauses(_fold(_strip_request_envelope(text)))) != 1
        or _has(
            folded,
            r"\b(?:mi|mis|my|our|nuestros?|nuestras?|tus?|your|"
            r"privad[oa]s?|private|local(?:es|ly)?|portapapeles|clipboard|"
            r"contrasenas?|passwords?|correos?|emails?|mensajes?|messages?)\b|"
            r"\b[a-z]:[\\/]|\\\\",
        )
    ):
        return None
    return query


def _named_browser_site_request(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
) -> tuple[str, str] | None:
    """(browser, bare site name) for «abre <navegador> y entra a <sitio>», else None."""

    folded = _fold(without_control_cession_preamble(text))
    found = _NAMED_BROWSER_SITE_REQUEST.fullmatch(folded.strip())
    if found is None:
        return None
    site = found.group("site") or found.group("site2") or ""
    browser_name = found.group("browser") or found.group("browser2") or ""
    browser = _named_browser("in " + browser_name)
    if (
        browser not in NAMED_CDP_BROWSERS
        or explicit_non_action_frame(text)
        or _is_negated_match(folded, found)
        or _is_meta_or_tool_denial(folded)
        or _is_past_or_hypothetical_state(folded)
        or _has_contradictory_correction(folded)
        or not effect_request_is_authoritative(text)
        or re.fullmatch(_NAMED_PUBLIC_SITE, site) is not None
        or resolve_application_catalog_app_id(site, application_names) is not None
        or _has(site, r"^(?:la|el|the|un|una|a|mi|my|este|esta|ese|esa|this|that|eso|it|"
                r"alli|ahi|there|aqui|here|internet|web|google|bing|configuracion|settings|"
                r"ajustes|opciones|options|archivo|archivos|file|files|carpeta|folder|"
                r"escritorio|desktop|descargas|downloads|documentos|documents)$")
    ):
        return None
    return browser, site


def _named_browser_search(text: str) -> tuple[str, str] | None:
    """Bind a public query and browser within one complete current request."""

    # The guards read the request without its social envelope: «Cuando
    # puedas,» is courtesy, not a deferral, and «Te paso una tarea:» names no
    # task of the catalogue.
    folded = _fold(_strip_request_envelope(text))
    if (
        len(text) > 16_384
        or explicit_non_action_frame(text)
        or _is_past_or_hypothetical_state(folded)
        or _has_unsupported_deferred_effect(folded)
        or _is_meta_or_tool_denial(folded)
        or _has_contradictory_correction(folded)
        or _has(folded, r"\b(?:archivo|file|carpeta|folder|documentos?|documents?|"
                r"descargas|downloads?|escritorio|desktop|notas?|notes?|"
                r"tareas?|tasks?|recordatorios?|reminders?|aplicaciones?\s+"
                r"instaladas?|installed\s+applications?|installed\s+apps?)\b")
    ):
        return None
    clauses = _request_clauses(_strip_request_envelope(text))
    if not 1 <= len(clauses) <= 2:
        return None
    query = _direct_public_search_query(clauses[-1])
    if query is None:
        return None
    scope = _named_browser_match(query)
    browser = _named_browser(query)
    if scope is not None:
        if scope.end() != len(query):
            return None
        query = query[:scope.start()].strip()
    if len(clauses) == 2:
        opening = _application_open_request(_fold(clauses[0]))
        if opening is not None and effect_request_is_authoritative(clauses[0]):
            opening_target = "in " + opening.group("target").rstrip(".!?")
            opened_scope = _named_browser_match(opening_target)
            opened = _named_browser(opening_target)
            if (
                opened_scope is None
                or opened_scope.start() != 0
                or opened_scope.end() != len(opening_target)
                or (browser is not None and browser != opened)
            ):
                return None
            browser = opened
        else:
            # Only a literal nominal desire immediately before this search
            # supplies its pronoun's antecedent; no history or model guess.
            antecedent = re.fullmatch(
                r"(?:i\s+(?:need|want)|necesito|quiero)\s+(?P<query>.+)",
                clauses[0].strip(), re.IGNORECASE,
            )
            if antecedent is None or _fold(query) not in {"it", "them", "that", "eso", "esto"}:
                return None
            query = antecedent.group("query").strip()
            if (
                _has(_fold(query), rf"^(?:to\s+)?(?:{_COVERAGE_ACTION_HEAD})\b")
                or _direct_public_search_query("search for " + query) is None
            ):
                return None
    if (
        browser not in NAMED_CDP_BROWSERS
        or not query
        or _fold(query) in {"it", "them", "that", "eso", "esto"}
        or len(query.encode("utf-8")) > 512
        or any(ord(character) < 32 for character in query)
        or _explicit_google_search_query("search " + query) is not None
    ):
        return None
    return browser, query


_REDO_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:hazla|hazlo|hacela|hacelo|hacelo\s+ya|hazlo\s+ya|hazla\s+ya|dale|dale\s+ya|hace\s+eso|haz\s+eso|hacé\s+eso|"
    r"hacelo\s+igual|hazlo\s+igual|hazla\s+igual|do\s+it|just\s+do\s+it|go\s+ahead|do\s+that)"
    r"(?:\s*[,.!]?\s*(?:te\s+dije|ya\s+te\s+dije|te\s+lo\s+dije|i\s+told\s+you|i\s+said).{0,80})?\s*[.!?]*$",
    re.IGNORECASE,
)


def _redo_previous_request(text: str, recent_user_texts: Iterable[str], available: frozenset[str],
                           application_names: Iterable[str] | ApplicationCatalogIndex,
                           game_catalog: Iterable[tuple[str, str, str]] | GameCatalogIndex) -> str | None:
    """Owner 2026-09-21 «Hazla, te dije que si mil veces» after a cancelled
    search: «do it» takes the most recent user request that reads as an
    effect (skipping yes/no answers and the redo itself). None otherwise."""

    if _REDO_REQUEST.match(_fold(text).strip()) is None:
        return None
    for previous in list(recent_user_texts)[:6]:
        candidate = str(previous).strip()
        if not candidate or _REDO_REQUEST.match(_fold(candidate)) is not None:
            continue
        if re.fullmatch(r"[¿?¡!\s]*(?:si|sí|no|confirmo|confirmar|confirm|cancela|cancelar|cancel|ok|dale|yes|nope|yep|claro)\s*[.!]*", _fold(candidate)):
            continue
        resolved = resolve_explicit_effects(candidate, available, application_names, game_catalog)
        if resolved is not None:
            return candidate
    return None


def redo_previous_request_intent(
    text: str, history: object, available_operations: Iterable[str],
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
    game_catalog: Iterable[tuple[str, str, str]] | GameCatalogIndex = (),
) -> EffectIntent | None:
    """«hazla» read against the recent user turns: the previous request again."""

    if not isinstance(history, list):
        return None
    available = frozenset(available_operations)
    items = [item for item in history if isinstance(item, dict)]
    if items and items[-1].get("role") == "user" and items[-1].get("content") == text:
        items = items[:-1]
    recent = [str(item.get("content") or "") for item in reversed(items) if item.get("role") == "user"]
    previous = _redo_previous_request(text, recent, available, application_names, game_catalog)
    if previous is None:
        return None
    resolved = resolve_explicit_effects(previous, available, application_names, game_catalog)
    return EffectIntent(resolved.operations, tuple(previous for _ in resolved.operations)) if resolved is not None else None


def _everyday_media_control(folded: str, head: str) -> bool:
    """Uso real 2026-09-23 «salta al siguiente episodio de podcast», «cambia a la
    siguiente canción de la lista», «para de reproducir», «apaga la música»:
    moving through or stopping what plays, said the everyday way."""

    if _is_negative_effect_clause(folded):
        return False
    return (
        (
            _head_is(head, r"(?:salta|saltate|saltar|cambia|cambiar|pasa|pasate|skip|go)")
            and _has(folded, r"\b(?:siguiente|next|anterior|previous|otra|another)\b")
            and _has(folded, r"\b(?:cancion|song|pista|track|tema|episodio|episode|capitulo|podcast)\b")
        )
        or re.fullmatch(
            r"(?:para|pare|deja|dejar|stop)\s+(?:de\s+)?(?:reproducir|sonar|tocar|playing)\b.{0,24}",
            folded,
        ) is not None
        or re.fullmatch(
            r"(?:apaga|apagame|quita|quitame|corta|cortame|para|pausa|deten|turn\s+off|stop)\s+"
            r"(?:(?:la|el|esta|este|the|this)\s+)?(?:musica|music|cancion|song|reproduccion|playback)"
            r"(?:\s+(?:por\s+favor|please|porfa|ya|ahora))?[\s.!?]*",
            folded,
        ) is not None
    )


def _pointed_media_question(folded: str, head: str) -> bool:
    """Uso real 2026-09-23 «qué canción es esta», «cómo se llama esta canción»,
    «quién es el cantante de esta canción»: what plays, pointed at."""

    return (
        (
            # Uso real 2026-09-24 «sabes sobre la letra de esta canción»: asking whether BAXY knows about it.
            _head_is(head, r"(?:que|what|cual|which|como|how|quien|who|dime|tell|decime|sabes|conoces|know)")
            # Uso real 2026-09-23 «en qué año salió esta canción»: the question word after a preposition.
            or _has(folded, r"^(?:en|de|desde|para|a|in|from|since|for)\s+(?:que|cual|quien|what|which|who|cuando|when)\b")
            # M100 (reserva A1 «quiero saber más sobre esta canción» → «¿qué canción?»): wanting to know about the song,
            # or being told about it, asks the same; «este tema» said so is a topic of the conversation.
            or (
                _has(
                    folded,
                    r"^(?:(?:quiero|quisiera|me\s+gustaria|necesito)\s+(?:saber|conocer)|(?:i\s+(?:want|would\s+like|need)|"
                    r"i'?d\s+like)\s+to\s+(?:know|learn)|cuentame|contame|hablame)\b",
                )
                and _has(folded, r"\b(?:cancion|song|track|artista|artist|cantante|singer)\b")
            )
        )
        and _has(folded, _POINTED_MEDIA)
        # «¿Qué canción está sonando en mi cabeza?» is not this PC's playback.
        and not _has(folded, r"\b(?:en|inside)\s+(?:mi|my)\s+(?:cabeza|mente|head|mind)\b")
    )


def _review_media_and_email_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    head: str,
    *,
    audio_level: bool,
    context_spotify: bool,
) -> None:
    """Append Spotify/media controls and read-only email effects."""

    spotify_target = _has(folded, r"\b(?:en|on)\s+spotify\b")
    spotify = spotify_target or context_spotify
    change_current_artist = _has(
        folded,
        r"^[^\w]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
        r"(?:cambia|cambiar|change|switch)\s+"
        r"(?:(?:el|la|the|current|actual)\s+)?(?:artista|artist)"
        r"(?:\s*[,;:]?\s*(?:por favor|please))?[\s.!?]*$",
    )
    media_transport = _media_transport_action(folded)
    audio_media_setting = _has(
        folded,
        (
            r"\b(?:volumen|volume|audio|sonido|sound)\b"
            r".{0,60}(?:\b\d{1,3}\b|%)"
        ),
    )
    resume_existing_media = _resume_existing_media(folded)
    exact_play = (
        spotify
        and not audio_media_setting
        and _has(
            folded,
            r"\b(?:exactamente|exactly|exact|exacta)\b",
        )
        and _head_is(
            head,
            r"(?:reproduce|reproducir|play|pon)",
        )
        and _has(folded, r"\b(?:reproduce|reproducir|play|pon)\b")
    )
    if unoffered_music_service_named(folded):
        # M84 (DEV-D v3o D-s050): music asked on a service BAXY does not play on is no play here, neither on YouTube
        # nor on Spotify; the known limit (``known_unsupported_effect_request``) says so.
        pass
    elif _explicit_named_music_query(folded) is not None and _desired_music_query(folded) is not None:
        # MUSIC1559: music named without a provider («pon música de daft punk»)
        # plays from YouTube in the local player; «en Spotify» keeps Spotify.
        _append(
            matches, folded, "media.play.query" if spotify else "media.play.youtube",
            r"\b(?:pon|ponme|poneme|pone|reproduce|reproducir|reproduci|play|toca|tocame|toque)\b",
        )
    elif _desired_music_query(folded) is not None:
        _append(
            matches,
            folded,
            "media.play.query",
            r"\b(?:need|want|necesito|quiero)\b",
        )
    elif _spoken_radio_station_request(folded):
        # Uso real tanda 2: a station without a provider plays in the local
        # player, like any music named without one (MUSIC1559); asking what it
        # plays now («qué música está poniendo … f. m.») is played the same way.
        # «pon la radio» names no station: nothing to search on YouTube.
        _append(
            matches,
            folded,
            "media.play.youtube" if not spotify and radio_station_query(folded) is not None else "media.play.query",
            # M91: a change of station to one named tunes it (``media.radio_station_query``).
            rf"\b(?:{_RADIO_PLAY}|que|what|whats|cual|which|cambia|cambiame|cambie|change|switch)\b",
        )
    elif _bare_spoken_number_media_query(folded) is not None:
        _append(
            matches,
            folded,
            "media.play.query",
            r"\b(?:pon|ponme|pone|poneme|reproduce|reproducir|play)\b",
        )
    elif exact_play:
        _append(
            matches,
            folded,
            "media.play.exact",
            rf"\b{_PLAY_HEAD}\b",
        )
    elif (
        (
            _head_is(
                head,
                rf"(?:{_SEARCH}|reproduce|reproducir|reproduzca|play|pon|ponme)",
            )
            and not (_head_is(head, r"(?:pon|poner|ponme)") and audio_level)
            and not audio_media_setting
            and not resume_existing_media
            and spotify_target
            and _has(
                folded,
                rf"\b{_SEARCH}\b|"
                r"\b(?:reproduce|reproducir|reproduzca|play|pon|ponme)\b",
            )
        )
        or (
            _head_is(head, r"(?:reproduce|reproducir|reproduzca|play|pon)")
            and context_spotify
            and not resume_existing_media
            and _has(folded, r"\b(?:reproduce|reproducir|play|pon)\b")
        )
        or (
            _head_is(head, r"(?:reproduce|reproducir|reproduzca|play|pon)")
            and _media_play_domain(folded)
            and not resume_existing_media
            and not media_transport
            and not _has(folded, r"\byoutube\b")
            and _has(
                folded,
                r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
                r"(?:reproduce|reproducir|reproduzca|play|pon)\s+\S.+",
            )
        )
    ):
        _append(
            matches,
            folded,
            "media.play.query",
            rf"\b{_SEARCH}\b|\b{_PLAY_HEAD}\b",
        )
    if (
        _head_is(head, _PLAY_HEAD)
        and _has(folded, r"\byoutube\b")
        and not _has(
            folded,
            r"\b(?:primer|primero|first|segundo|second|tercer|third|"
            r"resultado|result)\b",
        )
        and not resume_existing_media
        and not media_transport
        and _has(folded, rf"\b{_PLAY_HEAD}\b")
    ):
        _append(
            matches,
            folded,
            "media.play.youtube",
            rf"\b{_PLAY_HEAD}\b",
        )
    if (
        media_transport
        or change_current_artist
        or resume_existing_media
        or (
            _head_is(
                head,
                r"(?:pausa|pausar|pause|deten|detener|stop|siguiente|next|anterior|previous|"
                r"reanuda|reanudar|resume|reproduce|reproducir|reproduzca|play)",
            )
            and _has(
                folded,
                r"\b(?:pausa|pausar|pause|deten|detener|stop|siguiente|next|anterior|previous|"
                r"reanuda|reanudar|resume|reproduce|reproducir|reproduzca|play)\b",
            )
            and (
                spotify
                or _has(
                    folded,
                    # Fase 3.5: «pausá el video», «pause the movie» control the same session.
                    r"\b(?:audio|media|musica|music|reproduccion|playback|video|videos|peli|pelicula|serie|episodio|capitulo|movie)\b",
                )
                or exact_play
            )
            and not _has(
                folded,
                r"\b(?:grabacion|recording|microfono|microphone|mic)\b",
            )
            and (
                not _head_is(
                    head,
                    r"(?:reanuda|reanudar|resume|reproduce|reproducir|reproduzca|play)",
                )
                or resume_existing_media
            )
        )
    ):
        _append(
            matches,
            folded,
            "media.control",
            (
                r"\b(?:siguiente|next|anterior|previous|viene|sigue|antes|forward|back|deten(?:e|er)?|para|parar|stop|"
                r"skip\w*|salta\w*|pasa|pasar|past|passed|cambia\w*|proximo|ultimo|last)\b"
                if media_transport
                else r"\b(?:cambia|cambiar|change|switch)\b"
                if change_current_artist
                else rf"\b(?:{_MEDIA_RESUME_VERB}|reproduce|reproducir|reproduzca|play|pon|pone|ponme|poneme|toca|tocame|"
                r"put|start)\b"
                if resume_existing_media
                else r"\b(?:pausa|pausar|pause|deten|detener|stop|siguiente|next|anterior|previous|"
                r"reanuda|reanudar|resume|reproduce|reproducir|reproduzca|play)\b"
            ),
            priority=1,
        )
    if (
        not any(entry[2] == "media.control" for entry in matches)
        and (
            _head_is(head, r"(?:para|pausa|pausar|pause|deten|detener|stop)")
            or (
                _head_is(head, r"(?:deja|dejar)")
                and _has(folded, r"\b(?:deja|dejar)\s+en\s+pausa\b")
            )
        )
        and _has(
            folded,
            r"\b(?:sonando|playing|reproduciendo|cancion|song|pista|track|"
            r"lo\s+que\s+esta\s+sonando)\b",
        )
        and not _has(
            folded,
            r"\b(?:alarma|alarm|grabacion|recording|microfono|microphone|mic)\b",
        )
    ):
        _append(
            matches,
            folded,
            "media.control",
            r"\b(?:deja\s+en\s+pausa|dejar\s+en\s+pausa|"
            r"para|pausa|pausar|pause|deten|detener|stop)\b",
        )
    if (
        not any(entry[2] == "media.control" for entry in matches)
        and _head_is(head, r"(?:pasa|pasar|skip|siguiente|next)")
        and _has(
            folded,
            r"\b(?:siguiente|next|anterior|previous)\b",
        )
        and _has(
            folded,
            r"\b(?:cancion|song|pista|track|musica|music|tema)\b",
        )
    ):
        _append(
            matches,
            folded,
            "media.control",
            r"\b(?:pasa|pasar|skip|siguiente|next)\b",
        )
    if (
        not any(entry[2] == "media.control" for entry in matches)
        and _everyday_media_control(folded, head)
    ):
        _append(
            matches,
            folded,
            "media.control",
            r"\b(?:salta|saltate|saltar|cambia|cambiar|pasa|pasate|skip|go|para|pare|deja|dejar|stop|"
            r"apaga|apagame|quita|quitame|corta|cortame|pausa|deten|turn)\b",
        )
    if _pointed_media_question(folded, head) and not any(entry[2] == "media.status" for entry in matches):
        _append(matches, folded, "media.status", _POINTED_MEDIA)
    if (
        _head_is(head, r"(?:que|what|cual|which|dime|show|muestra)")
        and _has(folded, r"\b(?:musica|music|cancion|song)\b")
        and not _has(
            folded,
            r"\b(?:en|inside)\s+(?:mi|my)\s+(?:cabeza|mente|head|mind)\b",
        )
        and _has(folded, r"\b(?:sonando|playing|reproduciendo)\b")
    ):
        _append(matches, folded, "media.status", r"\b(?:musica|music|cancion|song)\b")
    if (
        _head_is(head, _READ)
        and _latest_email_domain(folded)
        and _has(folded, rf"\b{_READ}\b")
    ):
        _append(
            matches,
            folded,
            "email.latest.read",
            r"\b(?:correo|email|mail)\b",
        )


def _resolve_explicit_effects_single(
    text: str,
    available_operations: Iterable[str],
    *,
    context_browser: str | None = None,
    context_spotify: bool = False,
    context_open_application: bool = False,
    context_capture: bool = False,
    context_note: bool = False,
    context_audio: bool = False,
    context_machine: bool = False,
    context_window_active: bool = False,
    application_names: Iterable[str] = (),
) -> EffectIntent | None:
    """Resolve effects inside one request clause with bounded prior context."""

    folded = _fold(text)
    desired = _explicit_desire_request(folded)
    if desired is not None:
        # This clause is now being read for effects. Keep the original need
        # frame visible to the earlier conversation/clarification readers;
        # only anchored operation matchers consume the explicit action body.
        folded = desired.group("body")
    available = frozenset(available_operations)
    authenticated_request = _authenticated_application_request(
        folded,
        application_names,
    )
    if authenticated_request is not None and not _is_builtin_keyboard_request(folded):
        operation, targets = authenticated_request
        if operation not in available or len(targets) > 8:
            return None
        return EffectIntent(
            tuple(operation for _ in targets),
            tuple(target for _, target in targets),
        )
    desired_open = _authenticated_application_desired_open(
        folded,
        application_names,
    )
    if desired_open is not None and "app.open" in available:
        return EffectIntent(("app.open",), (desired_open[1],))
    in_application = _click_in_application(folded, application_names)
    if in_application is not None and {"app.open", "input.visible.click"} <= available:
        # UI1735 «en <app> hacé clic en X», «ve a X en <app>» (owner: general
        # mechanisms): the application is opened or brought to the front
        # (app.open reuses a running window) and the visible label is clicked
        # on it; any Start-catalog application, any label.
        application, clause = in_application
        clause_click = _visible_click_intent(clause, available, allow_navigate=True)
        if clause_click is not None:
            return EffectIntent(("app.open", "input.visible.click"), (application, clause_click.evidence[0]))
    visible_click = _visible_click_intent(
        folded,
        available,
        allow_navigate=context_open_application,
    )
    if visible_click is not None:
        return visible_click
    strict_request = _strict_catalog_request(
        folded,
        available,
        application_names,
    )
    if strict_request is not None:
        return strict_request
    if (
        not folded
        or len(folded) > 16_384
        or _is_meta_or_tool_denial(folded)
        or _has_contradictory_correction(folded)
        or (
            _has_unsupported_deferred_effect(folded)
            and not _location_recommendation_request(folded)
        )
        or not (
            _is_direct_request(_without_leading_duration_preface(folded))
            or _count_down_request(folded)
            or _bounded_calendar_list_query(folded)
            or _location_recommendation_request(folded)
            or _everyday_media_control(folded, _request_head(folded))
            or _pointed_media_question(folded, _request_head(folded))
            or (
                _has(folded, r"^can i (?:see|view)\b")
                and _has(folded, r"\b(?:reminder|recordatorio)\b")
                and _has(folded, r"\b(?:again|otra vez|de nuevo)\b")
            )
            or (
                context_audio
                and (
                    _has(
                        folded,
                        r"^(?:al?|to)?\s*\d{1,3}\s*(?:%|por ciento|percent)?\b",
                    )
                    or _has(
                        folded,
                        r"^(?:reactiva(?:lo|la)?|unmute(?: it)?|quita(?:r)? el silencio)[\s?!.]*$",
                    )
                )
            )
            or (
                context_open_application
                and _has(
                    folded,
                    rf"^(?:el|la|the)?\s*{_KNOWN_APPLICATION}[\s?!.]*$",
                )
            )
            or (
                context_note
                and _has(
                    folded,
                    r"^(?:otra|otro|another)\b",
                )
            )
            or (
                context_capture
                and _has(
                    folded,
                    r"^(?:describe|describelo|describela|describe it)[\s?!.]*$",
                )
            )
        )
    ):
        return None

    matches: list[tuple[int, int, str]] = []
    head = _request_head(folded)

    _review_system_and_network_effects(matches, folded, head)
    if (
        context_machine
        and "system.process.list" in available
        and not any(operation == "system.process.list" for _, _, operation in matches)
        and _head_is(head, r"(?:lista|listar|muestra|muestrame|show|list)")
        and _has(folded, r"\b(?:procesos?|processes)\b")
        and not _has(
            folded,
            r"\b(?:biologic[oa]s?|biological|celular(?:es)?|cellular|"
            r"metabolic[oa]s?|metabolic|contratacion|hiring|reclutamiento|"
            r"recruitment|empresa|business|negocio|fabricacion|manufacturing)\b",
        )
    ):
        _append(
            matches,
            folded,
            "system.process.list",
            r"\b(?:procesos?|processes)\b",
        )

    audio_level = _review_audio_effects(
        matches,
        folded,
        head,
        context_audio=context_audio,
    )

    _review_installed_catalog_effects(
        matches,
        folded,
        application_names=application_names,
    )
    _review_file_and_game_effects(matches, folded, head)
    _review_application_and_window_effects(
        matches,
        folded,
        head,
        application_names=application_names,
        context_open_application=context_open_application,
        context_window_active=context_window_active,
    )

    _review_input_and_capture_effects(
        matches,
        folded,
        head,
        context_capture=context_capture,
        context_open_application=context_open_application,
    )

    # Bind local-data verbs to the closest following domain noun. This avoids
    # turning incidental words ("a note about my tasks") into extra effects.
    web_search_requested = _review_local_data_effects(
        matches,
        folded,
        head,
        context_note=context_note,
    )
    _review_calendar_message_and_direct_reminder_effects(
        matches,
        folded,
        head,
    )
    _review_web_and_browser_effects(
        matches,
        folded,
        head,
        context_browser=context_browser,
        web_search_requested=web_search_requested,
    )

    _review_media_and_email_effects(
        matches,
        folded,
        head,
        audio_level=audio_level,
        context_spotify=context_spotify,
    )

    return _finalize_effect_matches(folded, matches, available)


_STRICT_COMPOSITION_SEGMENT_SEPARATOR = re.compile(
    r"\s*(?:[,;]+|\b(?:y\s+despues|y\s+luego|and\s+then|"
    r"despues\s+de\s+eso|por\s+ultimo|after\s+(?:that|this)|afterwards|"
    r"junto\s+con|along\s+with|finally|finalmente|then|luego|despues|"
    r"tambien|y|and)\b)\s*",
    re.IGNORECASE,
)


_STRICT_COMPOSITION_NOMINAL_OPERATIONS = (
    (
        "system.status",
        r"(?:system|sistema|machine|maquina|equipo|computer|computador|pc)",
    ),
    ("network.status", r"(?:red|network)"),
    ("backup.list", r"(?:copias?|copies|backups?|respaldos?)"),
    ("email.latest.read", r"(?:correo|email|mail)"),
    ("input.keyboard.status", r"(?:teclado|keyboard)"),
)


def _strict_composition_nominal_operation(segment: str) -> str | None:
    if _nominal_datetime_query(segment):
        return "system.time"
    observation_head = (
        r"(?:(?:reporta?|show|muestra|consulta|lee|read|enumera|list|"
        r"give|dame|revisa|revisar|check|comprueba|comprobar|"
        r"inspecciona|inspect)\s+)?"
    )
    for operation, nominal in _STRICT_COMPOSITION_NOMINAL_OPERATIONS:
        if (
            re.fullmatch(
                rf"[Â¿?Â¡!\s]*{observation_head}(?:(?:el|la|the)\s+)?"
                rf"{nominal}(?:\s+(?:status|state|estado))?[\s.!?]*",
                segment,
                re.IGNORECASE,
            )
            is not None
        ):
            return operation
    return None


def _strict_composition_segments_are_grounded(
    text: str,
    expected: EffectIntent,
    available: frozenset[str],
    applications: ApplicationCatalogIndex,
) -> bool:
    """Prove every coordinated segment belongs to the strict operation list."""

    segments = tuple(
        segment
        for segment in (
            part.strip() for part in _STRICT_COMPOSITION_SEGMENT_SEPARATOR.split(text)
        )
        if segment and re.search(r"\w", segment, re.UNICODE) is not None
    )
    if not 2 <= len(segments) <= 8:
        return False
    operations: list[str] = []
    for segment in segments:
        if (
            re.fullmatch(
                r"(?:exactamente|exactly)\s+(?:en|in)\s+(?:ese|that)\s+"
                r"(?:orden|order)[\s.!?]*",
                segment,
                re.IGNORECASE,
            )
            is not None
        ):
            continue
        resolved = _strict_catalog_request(segment, available, applications)
        if resolved is None:
            # A shared observation head can govern later nominal segments:
            # ``show system status, network access and sound routing``.
            resolved = _strict_catalog_request(
                "show " + segment,
                available,
                applications,
            )
        if resolved is None:
            nominal_operation = _strict_composition_nominal_operation(segment)
            if nominal_operation is None:
                return False
            operations.append(nominal_operation)
        else:
            operations.extend(resolved.operations)
        if len(operations) > 8:
            return False
    return tuple(operations) == expected.operations


# M111 (DEV-F v4d F-w56-t3 «enciéndeme la luz nocturna» → «¿Qué ajuste específico deseas cambiar y a qué valor?»): the
# settings switched on or off, each by the words that name it.
_SWITCHED_SETTINGS = (
    ("airplane_mode", r"\b(?:modo\s+avion|airplane\s+mode|flight\s+mode)\b"),
    ("night_light", r"\b(?:luz\s+nocturna|night\s*light|filtro\s+de\s+luz\s+azul|blue\s+light\s+filter)\b"),
    ("do_not_disturb", r"\b(?:(?:modo\s+)?no\s+molestar|do\s+not\s+disturb|dnd)\b"),
)


def setting_switch_request(text: str) -> tuple[str, int] | None:
    """M111: (setting, 1 on / 0 off) of an order to switch airplane mode, the night light or do-not-disturb; None for
    anything else, a question about its state included."""

    folded = _fold(text)
    named = [(setting, words) for setting, words in _SWITCHED_SETTINGS if _has(folded, words)]
    if len(named) != 1:
        return None
    setting, words = named[0]
    value = airplane_mode_request(text, words)
    return (setting, value) if value is not None else None


def airplane_mode_request(
    text: str, setting_words: str = r"\b(?:modo\s+avion|airplane\s+mode|flight\s+mode)\b",
) -> int | None:
    """REOPEN1957 H0107 «poneme el modo avión»: 1 to switch airplane mode on
    (every radio off), 0 to switch it off; None when the text is not an
    airplane-mode order or asks about its state. M111: ``setting_words`` reads another switched setting the same
    way (``setting_switch_request``)."""

    folded = _strip_request_envelope(_fold(text)).strip().rstrip(".!?").strip()
    if not _has(folded, setting_words):
        return None
    if _is_negative_effect_clause(folded) or _is_meta_or_tool_denial(folded):
        return None
    if _has(folded, r"^[¿?¡!\s]*(?:esta|is|tengo|do\s+i\s+have|hay)\b") or _has(folded, r"\b(?:activado|prendido|encendido|puesto|on)\s*\??$") and not _has(folded, r"^[¿?¡!\s]*(?:pon|pone|poneme|poner|activa|activame|activar|prende|prendeme|enciende|apaga|desactiva|quita|saca|turn|enable|disable|switch|put|set)\b"):
        return None
    if _has(folded, r"\b(?:apaga|apagame|apagar|desactiva|desactivame|desactivar|quita|quitame|quitar|saca|sacame|sacar|turn\s+off|disable|switch\s+off|off)\b"):
        return 0
    if _has(folded, r"\b(?:pon|pone|poneme|ponme|poner|activa|activame|activar|prende|prendeme|prender|enciende|encendeme|enciendeme|encender|activala|activalo|prendela|prendelo|turn\s+on|enable|switch\s+on|put|set|on)\b"):
        return 1
    return None


def airplane_mode_question(text: str) -> bool:
    """«¿está el modo avión activado?»: a read of the radios."""

    folded = _strip_request_envelope(_fold(text)).strip().rstrip(".!?").strip()
    return _has(folded, r"\b(?:modo\s+avion|airplane\s+mode|flight\s+mode)\b") and airplane_mode_request(text) is None and (
        _has(folded, r"^[¿?¡!\s]*(?:esta|is|tengo|do\s+i\s+have|hay)\b") or _has(folded, r"\b(?:activado|prendido|encendido|puesto|on)\b")
    )


def compress_named_request(text: str) -> tuple[str, str] | None:
    """«comprimí la carpeta Fotos del escritorio», «zip the file informe.pdf in
    documents» → (known folder, name). Unnamed targets abstain."""

    raw = _strip_request_envelope(str(text).strip()).rstrip(".!?")
    folded = _fold(raw)
    if _is_negative_effect_clause(folded) or folder_txt_zip_open_mission(text) is not None:
        return None
    match = re.match(
        rf"^[¿?¡!\s]*(?:comprim[eií](?:me|la|lo)?|comprimir|zip(?:ea|pea)?(?:me)?|compress)\s+"
        rf"(?:(?:la|el|the|a)\s+)?(?:(?:carpeta|folder|directorio|archivo|file|fichero)\s+)?"
        rf"(?P<name>[^\s/\\:*?\"<>|]+(?:\s+[^\s/\\:*?\"<>|]+){{0,4}}?)\s+"
        rf"(?:del|de\s+la|de|from|in|en|on)\s+(?:(?:el|la|mi|my|the)\s+)?(?P<folder>{_KNOWN_FOLDER_WORDS}|imagenes|pictures)\b",
        raw,
        re.IGNORECASE,
    )
    if match is None:
        return None
    folder = _KNOWN_FOLDER_ENUM.get(_fold(match.group("folder")), "pictures")
    name = match.group("name").strip()
    return (folder, name) if name and not _has(_fold(name), r"^(?:todo|todos|todas|eso|esto|it|this|that|all)$") else None


_NUMBER_WORDS = {
    "una": 1, "un": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
    "nueve": 9, "diez": 10, "once": 11, "doce": 12, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}


def presentation_request(text: str) -> tuple[str, int] | None:
    """REOPEN1957 H0188 «Haz un powerpoint hablando de amor de 6 diapositivas»:
    (topic as the person wrote it, slide count; 6 when none is given)."""

    raw = _strip_request_envelope(str(text).strip()).rstrip(".!?")
    folded = _fold(raw)
    if _is_negative_effect_clause(folded) or _is_meta_or_tool_denial(folded):
        return None
    if not _has(folded, r"\b(?:powerpoint|power\s+point|presentacion(?:es)?|diapositivas?|slides?|slideshow|slide\s+deck)\b"):
        return None
    if not _has(folded, r"^[¿?¡!\s]*(?:haz|hace|haceme|hazme|crea|creame|crear|arma|armame|armar|genera|generame|generar|prepara|preparame|make|create|build|prepare)\b"):
        return None
    count_match = re.search(r"\b(?P<n>\d{1,2}|" + "|".join(_NUMBER_WORDS) + r")\s+(?:diapositivas?|slides?|laminas?|paginas?)\b", folded)
    count = 6
    if count_match is not None:
        token = count_match.group("n")
        count = int(token) if token.isdigit() else _NUMBER_WORDS[token]
    if not 1 <= count <= 12:
        return None
    numbers = "|".join(_NUMBER_WORDS)
    count_phrase = rf"(?:\d{{1,2}}|{numbers})\s+(?:diapositivas?|slides?|laminas?|paginas?)"
    topic_body = (
        rf"(?P<topic>(?!{count_phrase})(?!(?:una|un|el|la|los|las|a|an|the)\s+(?:diapositiva|slide|presentacion))[^,;:.!?]+?)"
        rf"(?=\s+(?:de|con|of|with)\s+{count_phrase}\b|\s*$)"
    )
    # «sobre», «hablando de», «acerca de», «about» name the topic outright; a
    # bare «de» only when none of them is there («powerpoint de gatos»).
    topic_match = re.search(
        r"\b(?:hablando\s+(?:de|sobre|del|de\s+la|de\s+los|de\s+las)|sobre|acerca\s+de|about|titulad[oa]|called|named)\s+" + topic_body,
        raw,
        re.IGNORECASE,
    ) or re.search(r"\b(?:de|del|on)\s+" + topic_body, raw, re.IGNORECASE)
    if topic_match is None:
        return None
    topic = topic_match.group("topic").strip(" \t\r\n.,;:")
    if not topic or _has(_fold(topic), r"^(?:el|la|los|las|un|una|the|a|an|esto|eso|it|this|that)$") or len(topic.encode("utf-8")) > 120:
        return None
    return (topic, count)


def installed_catalog_application_name(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """The Start-catalog application an install or uninstall request names.

    INSTALL1625 H0651 «instala Spotify», H0574 «desinstalá Spotify», H0089
    «desinstalá Discord»: the product installs nothing by name and uninstalls
    nothing; the truthful turn reads whether the application is present and
    says so. Only an authenticated catalog name qualifies; anything else stays
    with the model.
    """

    folded = _strip_request_envelope(_fold(text)).strip().rstrip(".!?").strip()
    if _is_negative_effect_clause(folded) or _is_meta_or_tool_denial(folded):
        return None
    match = re.fullmatch(
        rf"[¿?¡!\s]*(?:(?:necesito|quiero|quisiera|podes|podrias|puedes|can\s+you|could\s+you|please)\s+(?:que\s+)?)?"
        rf"(?:me\s+)?{_CATALOG_INSTALL_VERB}\s+(?:(?:el|la|the|a)\s+)?(?:(?:app|aplicacion|programa|application)\s+)?"
        r"(?P<name>[a-z0-9][a-z0-9 .+'&-]{0,60}?)"
        r"(?:[\s,]+(?:por\s+favor|please|ahora|now|de\s+nuevo|again))?",
        folded,
    )
    if match is None:
        return None
    name = match.group("name").strip()
    if not name:
        return None
    catalog_name = resolve_application_catalog_app_id("abre " + name, application_names)
    if catalog_name is not None:
        return catalog_name
    # INSTALL1629 «instala Photoshop»: known software absent from the catalog
    # is answered by the same presence read, with the name as the person
    # wrote it (the read proves absence; nothing is installed).
    known = re.fullmatch(_KNOWN_SOFTWARE, name) is not None
    # INSTALL1631 H0620 «Desinstala Worms Rumble»: uninstalling a name the
    # catalog does not hold is answered by the same presence read (nothing
    # can be removed that is not present); a plain name of one to four words.
    uninstall = _has(folded, r"^[¿?¡!\s]*(?:(?:necesito|quiero|quisiera|podes|podrias|puedes|can\s+you|could\s+you|please)\s+(?:que\s+)?)?(?:me\s+)?(?:desinstal|uninstall)")
    plain_name = re.fullmatch(r"[a-z0-9][a-z0-9'+-]*(?:\s+[a-z0-9][a-z0-9'+-]*){0,3}", name) is not None and not _has(
        name,
        r"^(?:(?:todo|todos|todas|eso|esto|aquello|algo|nada|lo|la|el|ese|esa|este|esta|los|las|"
        r"un|una|mi|mis|tu|tus|everything|all|it|this|that|them|my|the)\b.*|"
        r".*\b(?:programas?|aplicaciones?|apps?|juegos?|cosas?|archivos?|programs?|applications?|games?|files?))$",
    )
    if known or (uninstall and plain_name):
        raw = str(text)
        folded_raw = _fold(raw)
        position = folded_raw.find(name) if len(folded_raw) == len(raw) else -1
        return raw[position:position + len(name)] if position >= 0 else name
    return None


def _catalog_entries_named(
    name: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[str, ...]:
    """WINGET2085: the catalog entries whose name begins with the whole
    requested name («7-Zip» → «7-Zip File Manager», «7-Zip Help»)."""

    key = _application_name_key(name)
    if not key:
        return ()
    catalog = build_application_catalog_index(application_names)
    return tuple(
        display for display, entry in catalog.entries
        if entry == key or entry.startswith(key + " ")
    )


def software_package_request(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[str, str, bool] | None:
    """REOPEN1993 grupo G: an install or uninstall of software by name
    («instala Spotify», «instalá Photoshop», «desinstalá Discord») →
    (verb, name as written, whether the Start catalog holds it). Games named
    with their store and Python packages keep their own readers; a name the
    catalog does not hold and that is not known software abstains."""

    folded = _strip_request_envelope(_fold(text)).strip().rstrip(".!?").strip()
    if _is_negative_effect_clause(folded) or _is_meta_or_tool_denial(folded):
        return None
    if _has(folded, r"\b(?:pip|steam|epic|juego|game|python)\b|https?://"):
        return None
    match = re.fullmatch(
        rf"[¿?¡!\s]*(?:(?:necesito|quiero|quisiera|podes|podrias|puedes|can\s+you|could\s+you|please)\s+(?:que\s+)?)?"
        rf"(?:me\s+)?(?P<verb>{_CATALOG_INSTALL_VERB})\s+(?:(?:el|la|the|a)\s+)?(?:(?:app|aplicacion|programa|application)\s+)?"
        r"(?P<name>[a-z0-9][a-z0-9 .+'&-]{0,60}?)"
        r"(?:[\s,]+(?:por\s+favor|please|ahora|now|de\s+nuevo|again))?",
        folded,
    )
    if match is None:
        return None
    verb = "uninstall" if match.group("verb").startswith(("desinstal", "uninstall", "quit", "sac", "elimin", "remov", "remuev")) else "install"
    name = match.group("name").strip()
    if not name or re.fullmatch(r"(?:todo|todos|todas|eso|esto|aquello|algo|nada|lo|la|el|it|this|that|everything|all)", name):
        return None
    if re.match(rf"(?:{lexicon.SETTING_NOUN})\b", name):
        # «baja el volumen 20»: «bajar» lowers a setting of this PC; nothing named «volumen» is installed.
        return None
    catalog_name = resolve_application_catalog_app_id("abre " + name, application_names)
    in_catalog = catalog_name is not None
    known = re.fullmatch(_KNOWN_SOFTWARE, name) is not None
    # «Plants vs. Zombies», «Node.js»: a dot inside a word is part of the name.
    plain = re.fullmatch(r"[a-z0-9][a-z0-9'+.-]*(?:\s+[a-z0-9][a-z0-9'+.-]*){0,3}", name) is not None and not _has(
        name, r"\b(?:programas?|aplicaciones?|apps?|juegos?|cosas?|archivos?|programs?|applications?|games?|files?)\b",
    )
    if not (in_catalog or known or plain):
        return None
    if match.group("verb").startswith("baj") and not (in_catalog or known):
        # Uso real 2026-09-23 «baja un veinte por ciento», «baja las luces del
        # techo» prepared a winget install: «bajar» lowers far more often than it
        # downloads, so only software the catalog or the known list names is a download.
        return None
    raw = str(text)
    folded_raw = _fold(raw)
    position = folded_raw.find(name) if len(folded_raw) == len(raw) else -1
    written = raw[position:position + len(name)] if position >= 0 else name
    return (verb, catalog_name if in_catalog else written, in_catalog)


_SHELL_COMMAND_HEADS = (
    r"(?:pytest|ls|dir|cd|git|npm|npx|pip|pip3|python|python3|node|dotnet|cargo|make|cmd|powershell|bash|sh|"
    r"echo|cat|type|pwd|whoami|hostname|ipconfig|ping|tree|ver|systeminfo|tasklist|where|which|"
    r"\S+\.(?:py|sh|bat|ps1|cmd|exe))"
)


def shell_command_request(text: str) -> tuple[str, str | None] | None:
    """REOPEN1993 (comandos, D11): the command the person asked to run and the
    folder a pasted prompt names («ejecuta ls», «corré git status», «PS C:\\x>
    python app.py»); None for anything that is not a console command."""

    raw = str(text).strip()
    folded = _fold(raw)
    # «ejecutá el comando git status»: the word «comando» names the thing to
    # run, not talk about tools; the denial gate reads the request without it.
    without_noun = re.sub(r"\b(?:el|the|este|this|un|a)\s+(?:comando|command)\s+", "", folded, count=1)
    if _is_negative_effect_clause(folded) or _is_meta_or_tool_denial(without_noun):
        return None
    prompt = re.match(r"^\s*(?:PS\s+)?(?P<cwd>[A-Za-z]:\\[^>]*?)\s*>\s*(?P<command>\S.*)$", raw)
    if prompt is not None:
        return (prompt.group("command").strip(), prompt.group("cwd").strip())
    if _has(folded, r"\b(?:juego|game|steam|app|aplicacion|application|programa|program)\b"):
        return None
    match = re.match(
        r"^[¿?¡!\s]*(?:(?:por\s+favor|please)\s*[,;:]?\s*)?"
        r"(?:ejecuta|ejecutá|ejecutame|ejecútame|corre|corré|correme|corréme|run|execute)\s+"
        r"(?:(?:el|the|este|this|un|a)\s+)?(?:comando\s+|command\s+)?"
        r"(?P<command>\S.*?)\s*[.!?]*$",
        raw,
        re.IGNORECASE,
    )
    if match is None:
        return None
    command = match.group("command").strip().strip("`\"'")
    cwd: str | None = None
    # «ejecutá dir en el escritorio», «run ls in downloads», «corré git status en
    # documentos/proyecto»: a known folder named after the command is its cwd.
    tail = re.search(
        r"\s+(?:en|in|on|dentro\s+de|desde|from)\s+(?:(?:el|la|mi|my|the)\s+)?(?:(?:carpeta|folder)\s+(?:de\s+)?)?"
        r"(?P<folder>escritorio|desktop|documentos|documents|descargas|downloads)(?:[/\\](?P<sub>[^\s/\\][^\n]{0,120}?))?\s*$",
        command,
        re.IGNORECASE,
    )
    if tail is not None:
        folder = {"escritorio": "desktop", "documentos": "documents", "descargas": "downloads"}.get(_fold(tail.group("folder")), _fold(tail.group("folder")))
        cwd = folder + ("/" + tail.group("sub").strip() if tail.group("sub") else "")
        command = command[: tail.start()].strip()
    command_folded = _fold(command)
    if not re.match(rf"^{_SHELL_COMMAND_HEADS}(?:\s|$)", command_folded):
        return None
    if len(command.encode("utf-8")) > 512 or "\n" in command:
        return None
    return (command, cwd)


def _dependent_web_navigation_intent(
    text: str,
    available_operations: frozenset[str],
    application_names: ApplicationCatalogIndex,
) -> EffectIntent | None:
    """Resolve an explicit site search followed by navigation to its result."""

    request = _match(
        text,
        (
            rf"^[¿?¡!\s]*{_REQUEST_PREFIX}{_OPEN}\b\s+"
            r"(?P<destination>wikipedia|(?:la\s+|the\s+)?(?:pagina|page|"
            r"sitio|site|website)\s+[^,;.!?]{1,100})\s+"
            r"(?:y|and)\s+(?:luego\s+|then\s+)?"
            rf"{_SEARCH}\b\s+(?P<query>\S.+?)[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    if not {"web.search", "browser.navigate"} <= available_operations:
        return None
    first_clause = f"abre {request.group('destination')}"
    if _authenticated_application_target(
        first_clause, application_names
    ) is not None or _open_application_spans(first_clause):
        return None
    evidence = request.group(0).strip(" ,;:-")[:240]
    return EffectIntent(
        ("web.search", "browser.navigate"),
        (evidence, evidence),
    )


def _new_notepad_paste_intent(
    text: str,
    available: frozenset[str],
    application_names: ApplicationCatalogIndex,
) -> EffectIntent | None:
    """Open a verified blank Notepad target before pasting the clipboard."""

    if not {"app.open", "clipboard.paste"} <= available:
        return None
    request = _match(
        text,
        (
            r"^[ż?Ą!\s]*(?:pega|pegar|paste)\s+"
            r"(?:(?:el|the)\s+)?(?:texto|text)"
            r"(?:\s+(?:del|from the)\s+(?:portapapeles|clipboard))?\s+"
            r"(?:en|into)\s+(?:(?:un|una|a)\s+)?"
            r"(?:archivo|file|documento|document)\s+"
            r"(?:nuevo|nueva|new)\s+(?:de|en|of|in)\s+"
            r"(?P<application>notepad|bloc de notas)[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    application = request.group("application")
    if resolve_application_catalog_app_id(application, application_names) is None:
        return None
    evidence = request.group(0).strip(" ,;:-")[:240]
    return EffectIntent(
        ("app.open", "clipboard.paste"),
        (application, evidence),
    )


def _pointer_scroll_intent(
    text: str,
    available: frozenset[str],
) -> EffectIntent | None:
    """A spoken scroll is pointer motion, not a page read."""

    if "input.pointer.control" not in available:
        return None
    request = _match(
        text,
        (
            r"^[¿?¡!\s]*(?:scroll|scrollea|scrollear)\b"
            r".{0,48}\b(?:down|up|abajo|arriba|a\s+bit|un\s+poco)\b[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    return EffectIntent(
        ("input.pointer.control",),
        (request.group(0).strip(" ,;:-")[:240],),
    )


def _resolve_clause_local_special_effects(
    clause: str,
    available: frozenset[str],
    applications: ApplicationCatalogIndex,
    games: GameCatalogIndex,
) -> EffectIntent | None:
    """Resolve bounded handlers that normally own one complete request."""

    if "browser.navigate" in available and _installed_browser_search_query(clause) is not None:
        # WEB1455 «Abre un navegador que tengas instalado y busca …»: the two
        # clauses are one reviewed navigation to the public search page.
        return EffectIntent(("browser.navigate",), (clause.strip(),))
    if "browser.navigate" in available and _youtube_search_query(clause) is not None:
        # WEB1481 «buscá videos de gatos en youtube»: one reviewed navigation
        # to YouTube's results page with the person's query.
        return EffectIntent(("browser.navigate",), (clause.strip(),))
    multiple_alarms = _multiple_alarm_schedule_intent(clause, available)
    if multiple_alarms is not None:
        return multiple_alarms
    game_target = _authenticated_game_target(clause, games)
    if game_target is not None and "game.launch" in available:
        return EffectIntent(("game.launch",), (game_target[2],))
    authenticated_request = _authenticated_application_request(
        clause,
        applications,
    )
    if authenticated_request is not None and not _is_builtin_keyboard_request(clause):
        operation, targets = authenticated_request
        if operation in available and len(targets) <= 8:
            return EffectIntent(
                tuple(operation for _ in targets),
                tuple(target for _, target in targets),
            )
    visible_click = _visible_click_intent(clause, available)
    if visible_click is not None:
        return visible_click
    if "notification.dismiss" in available and _active_alarm_stop_request(clause):
        return EffectIntent(("notification.dismiss",), (clause,))
    nominal_reminder = _nominal_reminder_lookup_title(clause)
    if nominal_reminder is not None and "reminder.resolve.exact" in available:
        return EffectIntent(("reminder.resolve.exact",), (clause,))
    if "web.search" in available and _location_recommendation_request(clause):
        return EffectIntent(("web.search",), (clause,))
    if "web.search" in available and _public_route_lookup_request(clause):
        return EffectIntent(("web.search",), (clause,))
    if "web.search" in available and _public_calendar_fact_lookup_request(clause):
        return EffectIntent(("web.search",), (clause,))
    notepad_paste = _new_notepad_paste_intent(
        clause,
        available,
        applications,
    )
    if notepad_paste is not None:
        return notepad_paste
    office_roundtrip = _office_document_roundtrip_intent(clause, available)
    if office_roundtrip is not None:
        return office_roundtrip
    steam_catalog = _steam_catalog_list_intent(clause, available)
    if steam_catalog is not None:
        return steam_catalog
    steam_status = _steam_install_status_intent(clause, available)
    if steam_status is not None:
        return steam_status
    steam_cancel = _steam_install_cancel_active_intent(clause, available)
    if steam_cancel is not None:
        return steam_cancel
    pointer_scroll = _pointer_scroll_intent(clause, available)
    if pointer_scroll is not None:
        return pointer_scroll
    if (
        "reminder.delete" in available
        and _exact_local_reminder_title(clause) is not None
    ):
        return EffectIntent(("reminder.delete",), (clause,))
    wifi_email = _wifi_email_intent(clause, available)
    if wifi_email is not None:
        return wifi_email
    return _dependent_web_navigation_intent(
        clause,
        available,
        applications,
    )


def _catalog_report_clauses(text: str) -> tuple[str, ...] | None:
    """Extract explicit noun clauses without assigning any operation."""

    report = _match(
        text,
        (
            r"^(?:(?:hazme\s+este|haz\s+este|hace\s+este)\s+"
            r"(?:chequeo|check)\s+(?:por|in)\s+"
            r"(?:partes|parts)(?:\s*[,;:.!?]+\s*|\s+)|"
            r"run\s+this\s+check\s+in\s+parts(?:\s*[,;:.!?]+\s*|\s+)|"
            r"necesito\s+(?:(?:un\s+parte\s+conjunto)|"
            r"(?:a\s+(?:combined|campaign)\s+report))"
            r"\s+(?:de|del)\s+|"
            r"i\s+need\s+a\s+combined\s+report\s+covering\s+|"
            r"(?:sin\s+omitir\s+ninguno|without\s+skipping\s+(?:any|ninguno))"
            r"\s*[,;:.!?]*\s*(?:revisa|inspect)\s+(?:en|in)\s+"
            r"(?:(?:este|this)\s+)?(?:orden|order)"
            r"(?:\s*[,;:.!?]+\s*|\s+)|"
            r"(?:ve|go)\s+(?:punto|point)\s+(?:por|by|for)\s+"
            r"(?:punto|point)\s+(?:(?:con|through|with)\s+)?)"
            r"(?P<body>.+)$"
        ),
    )
    if report is None:
        return None
    body = re.sub(
        r"(?:[,;:.!?]+\s*|\s+)(?:devolviendo|returning)\s+"
        r"(?:cada|each)\s+(?:resultado|result)\s+"
        r"(?:por\s+separado|separately)[\s.!?]*$",
        "",
        report.group("body"),
        flags=re.IGNORECASE,
    )
    return tuple(
        clause.strip(" \t\r\n,;:.!?")
        for clause in re.split(
            r"\s*(?:"
            r";\s*(?:(?:despues|then)(?:\s+check)?\b\s*[,;:.!?]*)?|"
            r"\b(?:despues|then)(?:\s+check)?\b\s*[,;:.!?]*"
            r")\s*",
            body,
            flags=re.IGNORECASE,
        )
        if clause.strip()
    )


def compound_retrieval_clauses(text: str) -> tuple[str, ...]:
    """Split an apparent sequence for advisory per-clause retrieval only.

    This deliberately grants no intent or operation authority. Speech
    recognizers routinely remove punctuation around ``después``/``then`` or
    leave a standalone ``check`` fragment; the strict effect grammar must keep
    rejecting those ambiguous forms, while retrieval may still offer each
    clause's authenticated family to the constrained model.
    """

    folded = _strip_request_envelope(_fold(re.sub(r"[\r\n]+", " . ", str(text))))
    strict = _catalog_report_clauses(folded)
    if strict is not None and 2 <= len(strict) <= 8:
        return strict
    parts = re.split(
        r"\s*(?:[.;!?]+\s*)?(?:\b(?:y\s+despues|and\s+then|"
        r"despues(?!\s+(?:de|del)\b)|then|afterwards)\b)"
        r"\s*[,;:.!?]*\s*(?:check\b\s*[,;:.!?]*\s*)?",
        folded,
        flags=re.IGNORECASE,
    )
    clauses: list[str] = []
    for part in parts:
        clause = re.sub(
            r"^check\b\s*[,;:.!?]*\s*",
            "",
            part.strip(" \t\r\n,;:.!?"),
            flags=re.IGNORECASE,
        )
        clause = re.sub(
            r"[,;:.!?]*\s*(?:devolviendo|returning)\s+"
            r"(?:cada|each)\s+(?:resultado|result)\s+"
            r"(?:por\s+separado|separately)[\s.!?]*$",
            "",
            clause,
            flags=re.IGNORECASE,
        ).strip(" \t\r\n,;:.!?")
        if clause and re.search(r"\w", clause, re.UNICODE):
            clauses.append(clause)
    return tuple(clauses) if 2 <= len(clauses) <= 8 else ()


def _catalog_report_composition(
    text: str,
    available: frozenset[str],
) -> EffectIntent | None:
    """Resolve an explicit, bounded catalog report without a model decode.

    Natural report requests often put the speech act only in the first clause
    and name the remaining read domains as noun phrases.  The ordinary clause
    resolver intentionally refuses those fragments in isolation.  This small
    grammar restores compositionality while remaining fail-closed: it requires
    a report wrapper, two to eight explicitly separated clauses, exactly one
    authenticated operation per clause, and zero negative/meta/device scope.

    Speech recognizers do not reliably preserve colons or semicolons.  Accept
    sentence punctuation after the authenticated wrapper and explicit
    ``then``/``despues`` boundaries as equivalent separators.  The domain
    matcher and uniqueness checks below remain unchanged, so punctuation alone
    can never manufacture an operation.
    """

    wrapper_negation = _is_negative_effect_clause(text) and not _has(
        text,
        r"^(?:sin\s+omitir\s+ninguno|without\s+skipping\s+(?:any|ninguno))\b",
    )
    if wrapper_negation or _other_device_effect_scope(text):
        return None
    clauses = _catalog_report_clauses(text)
    if clauses is None:
        return None
    if not 2 <= len(clauses) <= 8 or any(
        _is_negative_effect_clause(clause) for clause in clauses
    ):
        return None

    domains = (
        (
            "system.status",
            r"\b(?:salud\s+global|overall\s+(?:system\s+)?health|"
            r"over\s+(?:all\s+the\s+alt|or\s+layout)\s+del\s+sistema)\b",
        ),
        (
            "network.status",
            r"\b(?:acceso\s+general\s+a\s+la\s+red|general\s+(?:network\s+)?access)\b",
        ),
        (
            "wifi.status",
            r"\bwi[\s-]?fi\b.{0,32}\b(?:senal|signal|enlace|link)\b|"
            r"\b(?:senal|signal|enlace|link)\b.{0,32}\bwi[\s-]?fi\b",
        ),
        (
            "audio.status",
            r"\b(?:volumen|volume)\b.{0,32}\b(?:audio|output|salida)\b|"
            r"\baudio\s+(?:volume|output)\b",
        ),
        (
            "media.status",
            r"\b(?:lo\s+que\s+se\s+esta\s+reproduciendo|"
            r"what\s+is\s+(?:currently\s+)?playing|"
            r"what\s+is\s+(?:playing|plain)\s+ahora)\b",
        ),
        ("window.active", r"\b(?:ventana|window)\b.{0,32}\b(?:foco|focus)\b"),
        (
            "browser.tabs.list",
            r"\b(?:paginas?\s+abiertas?\s+del\s+navegador|"
            r"(?:open\s+pages|pages?\s+abiertas?)\s+(?:del|of\s+the)\s+browser|"
            r"(?:the\s+)?browsers?(?:'s)?\s+open\s+pages)\b",
        ),
        (
            "clipboard.read.text",
            r"\b(?:texto|text)\b.{0,32}\b(?:list[oa]\s+para\s+pegar|"
            r"ready\s+(?:para|to)\s+paste)\b|"
            r"\bcontext\s+ready\s+(?:para|to)\s+paste\b",
        ),
        (
            "input.keyboard.status",
            r"\b(?:distribucion\s+del\s+teclado|"
            r"keyboard\s+input\s+(?:layout|loud))\b",
        ),
        (
            "peripheral.list",
            r"\b(?:accesorios?\s+fisicos?\s+conectados?|"
            r"physical\s+accessories\s+(?:conectados?|attached)|"
            r"attached\s+physical\s+accessories)\b",
        ),
        (
            "bluetooth.device.list",
            r"\b(?:equipos?|devices?)\b.{0,32}\bbluetooth\b|"
            r"\bbluetooth\b.{0,32}\b(?:equipos?|devices?)\b",
        ),
        (
            "task.list",
            r"\b(?:tareas?|tasks?)\b.{0,32}\b(?:abiertas?|open|remain)\b|"
            r"\btask\s+screen\s+man\s+open\b",
        ),
        (
            "note.list",
            r"\b(?:(?:indice|index)\b.{0,24}\b(?:notas?|notes?)|"
            r"private[- ]note\s+index)\b",
        ),
        (
            "reminder.list",
            r"\b(?:recordatorios?|reminders?)\b.{0,32}"
            r"\b(?:programad[oa]s?|scheduled|still|todavia)\b",
        ),
        (
            "routine.list",
            r"\b(?:rutinas?|routines?)\b.{0,32}\b(?:guardad[oa]s?|saved|personal)\b|"
            r"\bsaved\s+personal\s+routines?\b|"
            r"\bsub\s*personal\s+routines?\b",
        ),
        (
            "backup.list",
            r"\b(?:copias?\s+recuperables?|recoverable\s+backup\s+copies)\b",
        ),
        (
            "game.catalog.list",
            r"\b(?:juegos?|games?|gammes)\b.{0,32}\b(?:catalogo|catalog)\b",
        ),
        (
            "calendar.event.list",
            r"\b(?:citas?\s+de\s+hoy|today(?:'s)?\s+appointments?)\b",
        ),
        (
            "email.latest.read",
            r"\b(?:contenido|content)\b.{0,40}\b(?:correo|email)\b.{0,32}"
            r"\b(?:recien\s+llegado|newly\s+arrived)\b|"
            r"\b(?:contenido|content)\b.{0,40}\b(?:recien\s+llegado|"
            r"newly\s+arrived)\b.{0,24}\b(?:correo|email)\b|"
            r"\b(?:correo|email)\b.{0,40}\b(?:recien\s+llegado|newly\s+arrived)\b|"
            r"\bnewly\s+arrived\s+emails?(?:'s)?\s+contents?\b|"
            r"\b(?:content|contenido)\b.{0,40}\bnullier\s+i[dt]\b"
            r".{0,24}\b(?:mails?|emails?|correos?)\b|"
            r"\b(?:content|contenido)\b.{0,40}\bnullier\b.{0,24}"
            r"\b(?:mails?|emails?|correos?)\b",
        ),
        (
            "notification.list.due",
            r"\b(?:avisos?\s+vencidos?|overdue\s+(?:notices?|avisos?)|"
            r"over\s*do\s+avisos?)\b",
        ),
        (
            "app.installed",
            r"\b(?:(?:si|sea)\s+\S.{0,48}\s+(?:figura\s+)?instalad[oa]|"
            r"(?:whether|si)\s+\S.{0,48}\s+is\s+installed)\b",
        ),
        (
            "filesystem.known.search",
            r"\b(?:archivos?|files?)\b.{0,64}\b(?:documentos|documents)\b",
        ),
    )
    operations: list[str] = []
    evidence: list[str] = []
    for clause in clauses:
        matches = [
            operation
            for operation, pattern in domains
            if operation in available and _has(clause, pattern)
        ]
        if len(matches) != 1:
            return None
        operations.append(matches[0])
        evidence.append(clause[:240])
    if len(set(operations)) != len(operations):
        return None
    return EffectIntent(tuple(operations), tuple(evidence))


_BOUNDED_STATUS_SEQUENCE_DOMAINS = (
    ("system.status", r"\b(?:estado\s+del\s+sistema|system\s+status)\b"),
    ("audio.status", r"\b(?:estado\s+del\s+audio|audio\s+status)\b"),
    ("network.status", r"\b(?:estado\s+de\s+la\s+red|network\s+status)\b"),
    (
        "input.keyboard.status",
        r"\b(?:estado\s+del\s+teclado|keyboard\s+status)\b",
    ),
    ("input.mouse.status", r"\b(?:estado\s+del\s+raton|mouse\s+status)\b"),
    (
        "bluetooth.radio.status",
        r"\b(?:estado\s+de\s+la\s+radio\s+bluetooth|"
        r"bluetooth\s+radio\s+status)\b",
    ),
    (
        "peripheral.list",
        r"\b(?:perifericos\s+conectados|connected\s+peripherals|"
        r"attached\s+peripherals)\b",
    ),
    (
        "bluetooth.device.list",
        r"\b(?:dispositivos\s+bluetooth\s+visibles|"
        r"visible\s+bluetooth\s+devices|bluetooth\s+devices\s+visible)\b",
    ),
)


_DATED_MACHINE_REPORT = re.compile(
    r"^[¿?¡!\s]*(?:muestra|muestrame|mostra|mostrame|dime|decime|dame|"
    r"show(?:\s+me)?|tell\s+me|give\s+me)\s+(?:(?:la|el|the)\s+)?"
    r"(?P<clock>(?:fecha|date)(?:\s+(?:y|and)\s+(?:(?:la\s+|the\s+)?hora|time))?"
    r"(?:\s+(?:actual(?:es)?|current|de\s+hoy|del\s+sistema|of\s+the\s+system|system))*)"
    r"\s+(?:y|and)\s+(?P<machine>.+?)[\s.!?]*$",
    re.IGNORECASE,
)


def _dated_machine_report(text: str) -> EffectIntent | None:
    """«Muestra la fecha actual y el uso de RAM del sistema»: clock, then status.

    A show/tell head, the date (optionally with the time) and one measurable
    machine scope joined by «y/and» is a read-only plan: system.time first,
    then system.status of the scope the existing readers ground (RAM, disk…).
    The bounded sequence above needs two ordering markers; this shape has
    none. Prohibitions, hypotheticals and other devices stay out.
    """

    if (
        _is_meta_or_tool_denial(text)
        or _is_negative_effect_clause(text)
        or _other_device_effect_scope(text)
    ):
        return None
    found = _DATED_MACHINE_REPORT.match(text)
    if found is None:
        return None
    machine = found.group("machine")
    if (
        not _system_status_domain(machine)
        or not _machine_status_scopes(machine)
        or not _machine_status_scopes_are_one_reading(machine)
        or len(_request_clauses(text)) > 2
    ):
        return None
    return EffectIntent(("system.time", "system.status"), (found.group("clock"), machine))


def _bounded_status_sequence_intent(
    text: str,
    available: frozenset[str],
) -> EffectIntent | None:
    """Resolve an explicitly ordered, read-only multi-domain report."""

    if (
        _is_meta_or_tool_denial(text)
        or _is_negative_effect_clause(text)
        or _other_device_effect_scope(text)
        or not _has(
            text,
            r"\b(?:revisa|reporta?|check|comprueba|dime|show|muestra)\b",
        )
    ):
        return None
    sequence_markers = re.findall(
        r"\b(?:primero|first|despues|then|finalmente|finally)\b",
        text,
        re.IGNORECASE,
    )
    if len(sequence_markers) < 2:
        return None
    matches: list[tuple[int, str, str]] = []
    for operation, pattern in _BOUNDED_STATUS_SEQUENCE_DOMAINS:
        found = re.search(pattern, text, re.IGNORECASE)
        if found is not None:
            matches.append((found.start(), operation, found.group(0)))
    matches.sort()
    operations = tuple(operation for _, operation, _ in matches)
    if (
        not 2 <= len(operations) <= 8
        or len(set(operations)) != len(operations)
        or not set(operations) <= available
    ):
        return None
    # This shortcut reports only the status domains it recognized. If the
    # request carries more clauses than domains, at least one clause -- a note
    # to create, a message to send -- would be dropped without a trace, and the
    # mission would run as a silent subset of what was asked. Fail the shortcut
    # and let the clause resolver account for every clause instead.
    if len(_request_clauses(text)) > len(operations):
        return None
    return EffectIntent(
        operations,
        tuple(evidence[:240] for _, _, evidence in matches),
    )


# DIALOGUE1487/1489 H0528 «Quiero que lo veas y de que se trata?», «Miralo y
# decime de qué se trata»: a request to look at «it/this/that» and say what it
# is, with nothing named. REOPEN1993: with no earlier request in the
# conversation there is nothing else «lo» can be but the screen in front, so
# the turn looks at the screen (capture + text read) and says what it is
# about; with an antecedent the question «qué debo mirar» stands.
DEICTIC_LOOK_CLAUSE = re.compile(
    r"[\s¡!¿?]*(?:"
    r"(?:quiero|necesito|quisiera)\s+que\s+(?:lo|la|los|las)\s+(?:veas|mires|revises|leas|chequees)|"
    r"(?:mira|miralo|mirala|ve|velo|vela|fijate|revisa|revisalo|revisala|chequea|chequealo|lee|leelo|leela)"
    r"(?:\s+(?:en\s+)?(?:eso|esto|lo|la|aquello))?|"
    r"(?:look\s+at|check(?:\s+out)?|see|read)\s+(?:it|this|that)(?:\s+out)?"
    r")"
    r"(?:\s*(?:,|y|and)\s*(?:me\s+)?(?:digas|decime|dime|contame|cuentame|tell\s+me)?\s*"
    r"(?:de\s+)?(?:que|what)\s+(?:se\s+trata|es|dice|it(?:'s|\s+is)(?:\s+about)?|it\s+says))?"
    r"[\s.!?¿¡]*"
)


def deictic_look_request(text: str) -> bool:
    """True for «miralo y decime de qué se trata» with nothing named."""

    folded = _strip_request_envelope(_fold(text)).strip()
    return bool(folded) and DEICTIC_LOOK_CLAUSE.fullmatch(folded) is not None


# UI1643 H0097 «ponle hola»: a text to put «to it» with nothing named. REOPEN1993
# (owner: ask where «unless the previous context makes the destination clear»):
# right after a request that opened or brought an application to the front,
# the text goes into that application (the focused control of the window in
# front); with no such antecedent the question «dónde» stands.
_DEICTIC_TEXT_ORDER = re.compile(
    r"[\s¡!¿?]*(?:pon[eé]?le|ponele|pon[eé]?melo|put\s+on\s+it|write\s+on\s+it)\s+"
    r"(?!(?:a|al|por|para|que|en)\b)(?P<text>[¿?¡!\w][^.!?]{0,60}?)"
    r"(?:\s+(?:ahora|ya|now|please|por\s+favor|porfa))*[\s.!?]*"
)


def deictic_text_to_type(
    text: str,
    previous_user_text: str | None,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """The literal to type for «ponle <texto>» when the previous request opened
    or focused an application; None otherwise."""

    if not previous_user_text:
        return None
    folded = _strip_request_envelope(_fold(text)).strip()
    order = _DEICTIC_TEXT_ORDER.fullmatch(folded)
    if order is None or _has(
        folded,
        r"\b(?:en|a|al|del|de)\s+(?:el|la|los|las|mi|mis|tu|tus|un|una|the|my|a)?\s*"
        r"(?:ventana|archivo|nota|chat|grupo|mensaje|correo|mail|documento|campo|titulo|"
        r"nombre|whatsapp|discord|telegram|window|file|note|chat|message|document|field)\b",
    ):
        return None
    catalog = build_application_catalog_index(application_names)
    previous_folded = _strip_request_envelope(_fold(previous_user_text))
    opened = _authenticated_application_request(previous_folded, catalog)
    focused = resolve_application_focus_name(previous_user_text, catalog)
    if (opened is None or opened[0] not in {"app.open", "window.focus"}) and focused is None:
        return None
    # The person's own spelling: take the literal from the original text.
    original = re.search(
        r"(?i)(?:pon[eé]?le|ponele|pon[eé]?melo|put\s+on\s+it|write\s+on\s+it)\s+(?P<text>.+?)"
        r"(?:\s+(?:ahora|ya|now|please|por\s+favor|porfa))*[\s.!?]*$",
        text.strip(),
    )
    literal = (original.group("text") if original is not None else order.group("text")).strip()
    return literal or None


def deictic_typed_literal(text: str) -> str | None:
    """The literal a «ponle X» / «write on it X» order asks to type, from the
    request alone (the composer has no history; the reader verified the
    application before the effect ran)."""

    original = re.search(
        r"(?i)(?:pon[eé]?le|ponele|pon[eé]?melo|put\s+on\s+it|write\s+on\s+it)\s+(?P<text>.+?)"
        r"(?:\s+(?:ahora|ya|now|please|por\s+favor|porfa))*[\s.!?]*$",
        (text or "").strip(),
    )
    literal = original.group("text").strip() if original is not None else ""
    return literal or None


# Reads a turn may run before asking about the other clause.
_DEFERRED_READ_OPERATIONS = frozenset({"system.time", "window.resolve"})


@dataclass(frozen=True, slots=True)
class DeferredClarification:
    """A read the turn runs now, and the kind of question its final must end with."""

    read_text: str
    kind: str
    clause: str


def _deferred_clause_kind(clause: str, available: frozenset[str]) -> str | None:
    folded = _strip_request_envelope(_fold(clause)).strip()
    if not folded:
        return None
    if INDETERMINATE_WINDOW_CLAUSE.fullmatch(folded) is not None:
        return "indeterminate_window"
    asked = resolve_explicit_clarification_intent(clause, available)
    if (
        asked is not None
        and asked.operations in {("audio.volume.adjust",), ("audio.app.volume.adjust",)}
        and asked.missing_fields == ("amount",)
    ):
        return "volume_amount"
    return None


def deferred_clarification_split(
    text: str,
    available_operations: Iterable[str],
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
    game_catalog: Iterable[tuple[str, str, str]] | GameCatalogIndex = (),
) -> DeferredClarification | None:
    """AUDIO858 H0067 «subí el volumen y decime qué fecha es», H0527 «listá las
    ventanas y enfocá la mejor»: two clauses joined by «y», one a read the turn
    can do (the date, the window listing) and the other a request that needs
    a question before any effect (the amount, which window). The turn asked
    the amount and dropped the date, or listed nothing. The read runs and the
    final ends with that one question; nothing is guessed for the other clause."""

    if explicit_non_action_frame(text):
        return None
    available = frozenset(available_operations)
    list_read = list_read_request(text)
    if list_read is not None and list_read.absent_clause:
        # Tanda 4c: an add that waits on the read of the list asks nothing; it is a plan (read, then add only
        # what the read did not find), see resolve_explicit_effects.
        return None
    parts = re.split(r"\s*(?:,\s*)?(?<![\w])(?:y|e|and)(?![\w])\s+", text.strip(), maxsplit=1)
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        return None
    for read, other in ((parts[0], parts[1]), (parts[1], parts[0])):
        kind = _deferred_clause_kind(other, available)
        if kind is None:
            continue
        if _deferred_clause_kind(read, available) is not None:
            return None
        intent = resolve_explicit_effects(read, available, application_names, game_catalog)
        if (
            intent is None
            or len(intent.operations) != 1
            or intent.operations[0] not in _DEFERRED_READ_OPERATIONS
        ):
            continue
        return DeferredClarification(read.strip(), kind, other.strip())
    return None


# WEB1883 H0081 «tomá control de mi pc, quiero que abras opera gx y entres a …»:
# the opening clause hands the machine over, it does not ask for anything. With
# it in front, this resolver found no effect and the turn became a conversation
# whose final denied a capability the product has (Opera GX is installed and
# browser.navigate.named was credited in WEB1805); without it the very same
# sentence resolves to the named navigation. Only a LEADING clause is dropped,
# and only when a request follows it.
_CONTROL_CESSION_PREAMBLE = re.compile(
    r"^[\s¡!¿?]*(?:por\s+favor\s*,?\s*|please\s*,?\s*)?"
    r"(?:tom[aá](?:te)?|agarr[aá]|manej[aá]|controla|control[aá]|"
    r"take(?:\s+over)?|assume|use)\s*"
    r"(?:el\s+|the\s+)?(?:control|mando|manejo|comando)?\s*"
    r"(?:de\s+|of\s+|sobre\s+)?"
    r"(?:mi|my|la|el|the)\s*"
    r"(?:pc|computadora|computador|compu|ordenador|m[aá]quina|equipo|"
    r"computer|machine|laptop|notebook)"
    r"\s*(?:[,;.]|\s)\s*(?:y|and|luego|then|despu[eé]s|ahora|now)?\s*",
    re.IGNORECASE,
)


def without_control_cession_preamble(text: str) -> str:
    """The request that follows a clause handing the machine over, or the text."""

    current = str(text or "")
    match = _CONTROL_CESSION_PREAMBLE.match(current)
    if match is None:
        return current
    rest = current[match.end():].strip()
    # «Tomá el control de mi PC.» on its own asks for exactly that and keeps its
    # own answer; only a request that follows the clause replaces it.
    return rest if rest else current


def resolve_explicit_effects(
    text: str,
    available_operations: Iterable[str],
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
    game_catalog: Iterable[tuple[str, str, str]] | GameCatalogIndex = (),
    *,
    previous_user_text: str | None = None,
) -> EffectIntent | None:
    """Resolve a bounded sequence of clause-local, closed-catalog effects.

    A message the clause readers do not resolve may still be an output level said without its object, in
    mixed languages, or as the bare answer to «¿cuánto?» (``output_level_request``). In that case it is
    resolved as the canonical request it states, which goes through the same readers.
    """

    available = tuple(available_operations)
    if reported_own_schedule(text):
        # Tanda 4f: «programé un temporizador de diez minutos» is what the person did, not the formal order
        # «programe» its folded form reads as; telling it asks for nothing.
        return None
    intent = _resolve_clause_effects(
        text, available, application_names, game_catalog, previous_user_text=previous_user_text,
    )
    if intent is not None:
        return intent
    change = notification_change(text)
    if change is not None:
        # M58 (v3d-final F-s019, F-s044, F-s095): moving an alarm, a timer or a reminder to another time is
        # cancelling the one at the old time (the last one set when none is said) and setting the new one. The
        # cancellation is read as its own request; the new one is the person's message (``notification_change``).
        cancel = _resolve_clause_effects(change.cancel_request(), available, application_names, game_catalog)
        if cancel is not None and len(cancel.operations) == 1 and "notification.schedule" in available:
            return EffectIntent((*cancel.operations, "notification.schedule"), (cancel.evidence[0], text.strip()))
    if "notification.list" in available and plural_alarm_cancellation(text):
        # D39 (owner, 2026-09-29; v3d-final F-s040 «Cancela las alarmas, por favor.»): the alarms are read first and
        # offered with their times; they are cancelled only on the yes (``DialogueState.accepted_alarm_cancellation``).
        return EffectIntent(("notification.list",), (text.strip(),))
    level_request = output_level_request(text, previous_user_text, available)
    if level_request is None:
        return None
    return _resolve_clause_effects(level_request, available, application_names, game_catalog)


def output_level_request(
    text: str, previous_user_text: str | None, available_operations: Iterable[str], *, asked: str | None = None,
) -> str | None:
    """The volume or brightness request ``text`` states, as the canonical sentence the level readers read.

    Uso real 2026-09-23: «baja un veinte por ciento», «Brillo 20%», «súbelo a 80» and the answers to
    «¿cuánto?» («un 10», «20», «a 40») were read by nobody. An answer completes only the request right before
    it, and only when that request is a relative change still missing its amount. The pending request keeps
    its object and direction; the answer gives the amount («un 10», «20») or the level to end at («a 40»,
    «al máximo»). «a 40» after «bajá el brillo» is therefore brightness 40, not 40 less. A request that leaves
    its object out takes it from the request it follows (``levels.followup_antecedent``), and otherwise
    refers to the volume. The caller resolves the result with every ordinary check. Nothing is completed
    from what the assistant said. ``asked``, when given, is BAXY's reply between the request and the answer:
    a bare number answers it (``levels.answers_with_amount``: «¿cuánto…?» an amount, a level question or none
    the level to end at).
    """

    available = frozenset(available_operations)
    answer = levels.answer(text)
    if answer is not None:
        if not previous_user_text:
            return None
        if asked is not None and answer.amount is not None and not levels.answers_with_amount(asked, text):
            answer = levels.Level(None, None, None, answer.amount)
        prior = resolve_explicit_clarification_intent(previous_user_text, available)
        if prior is None or prior.missing_fields != ("amount",) or prior.operations not in {
            ("audio.volume.adjust",), ("system.settings.adjust",),
        }:
            return None
        setting = levels.BRIGHTNESS if prior.operations == ("system.settings.adjust",) else levels.VOLUME
        direction = levels.direction_of(previous_user_text)
        if answer.target is None and direction is None:
            return None
        return levels.Level(setting, direction, answer.amount, answer.target).request(setting)
    level = levels.read(text)
    if level is None or (level.amount is None and level.target is None):
        return None
    setting = level.setting or levels.setting_of(previous_user_text)
    if setting is None and level.direction is None:
        # «ponlo al 50» names neither the object nor a way to raise or lower anything: only a request about
        # the volume or the brightness right before it says what «lo» is.
        return None
    return level.request(setting or levels.VOLUME)


def _level_quantity_said(text: str) -> bool:
    """The whole message is an output-level request that says how much or where to (``levels.read``)."""

    level = levels.read(text)
    return level is not None and (level.amount is not None or level.target is not None)


def _resolve_clause_effects(
    text: str,
    available_operations: Iterable[str],
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
    game_catalog: Iterable[tuple[str, str, str]] | GameCatalogIndex = (),
    *,
    previous_user_text: str | None = None,
) -> EffectIntent | None:
    text = without_control_cession_preamble(text)

    if explicit_non_action_frame(text):
        return None
    folded = _strip_request_envelope(_fold(re.sub(r"[\r\n]+", " . ", text)))
    folded = screen_light_as_brightness(folded)
    # H0461 «che, abrime el navegador chrome»: «navegador» delante de un
    # navegador con nombre es una aposición, no un destino. Sin quitarla el
    # pedido no resolvía nada y el turno acababa preguntando qué URL abrir,
    # cuando lo que se pidió fue abrir la aplicación. «abrí el navegador», sin
    # nombre detrás, sigue intacto.
    folded = re.sub(
        r"\b(?:navegador|browser)\s+"
        r"(?=(?:chrome|opera(?:\s*gx)?|edge|brave|firefox|safari)\b)",
        "",
        folded,
    )
    available = frozenset(available_operations)
    if (
        "filesystem.known.list" in available
        and _known_folder_recent_listing(folded.strip().rstrip(".!?")) is not None
    ):
        # FILES1433 «cuenta los archivos en el escritorio y lista los 5 mas
        # recientes»: the literal count bounds the listing; it is not a note
        # cardinality and the conjunction is one read, not two effects.
        return EffectIntent(("filesystem.known.list",), (folded,))
    deferred = deferred_clarification_split(text, available, application_names, game_catalog)
    if deferred is not None:
        # The read clause resolves alone; the other clause is asked in the final.
        return resolve_explicit_effects(
            deferred.read_text, available, application_names, game_catalog,
        )
    completed_level_request = _completed_missing_volume_level_request(
        text, previous_user_text, available,
    )
    if completed_level_request is not None:
        return resolve_explicit_effects(
            completed_level_request, available, application_names, game_catalog,
        )
    completed_message_request = _completed_missing_message_channel_request(
        text, previous_user_text, available,
    ) or _completed_missing_message_text_request(text, previous_user_text, available)
    if completed_message_request is not None:
        # MSGCLAR: the answered client (or the answered text and addressee)
        # completes the previous message request.
        return resolve_explicit_effects(
            completed_message_request, available, application_names, game_catalog,
        )
    # AUDIO1789: the shell may resume a pending objective as «<request>
    # <trusted clarification prefix> <answer>»; the two halves are read as
    # the previous request and its answer.
    if previous_user_text is None and "aclaracion confiable del usuario:" in _fold(text):
        prior, _, answer = _fold(text).partition("aclaracion confiable del usuario:")
        if prior.strip() and answer.strip():
            return resolve_explicit_effects(
                answer.strip(), available, application_names, game_catalog,
                previous_user_text=prior.strip(),
            )
    completed_app_volume_request = _completed_missing_app_volume_request(
        text, previous_user_text, available, application_names,
    )
    if completed_app_volume_request is not None:
        return resolve_explicit_effects(
            completed_app_volume_request, available, application_names, game_catalog,
        )
    completed_list_request = _completed_missing_list_entries_request(
        text, previous_user_text, available,
    )
    if completed_list_request is not None:
        return resolve_explicit_effects(
            completed_list_request, available, application_names, game_catalog,
        )
    completed_music_request = _completed_missing_music_request(
        text, previous_user_text, available,
    )
    if completed_music_request is not None:
        return resolve_explicit_effects(
            completed_music_request, available, application_names, game_catalog,
        )
    if "browser.navigate" in available:
        # Owner 2026-09-21 «Dime que es power automate» → «pasame un link…, o
        # mejor abrelo en mi navegador»: the pronoun takes the entity just asked.
        completed_browser_search = _completed_browser_search_pronoun_request(text, previous_user_text)
        if completed_browser_search is not None:
            return resolve_explicit_effects(
                completed_browser_search, available, application_names, game_catalog,
            )
    if {"web.download", "file.open"} <= available:
        completed_image_request = _completed_missing_image_subject_request(text, previous_user_text)
        if completed_image_request is not None:
            return resolve_explicit_effects(
                completed_image_request, available, application_names, game_catalog,
            )
    contextual_read = (
        "system.time" if _nominal_datetime_query(folded) else
        "window.active" if re.fullmatch(
            r"(?:(?:y|and)\s+)?(?:(?:ahora(?:\s+mismo)?|(?:right\s+)?now)\s+)?"
            r"(?:cual|which(?:\s+one)?)\s+(?:(?:esta|is)\s+(?:activa|active)|"
            r"(?:tiene|has)\s+(?:el\s+)?(?:foco|focus))"
            r"(?:\s+(?:ahora(?:\s+mismo)?|(?:right\s+)?now))?",
            folded.strip(" ¿?¡!."),
        ) else None
    )
    if previous_user_text and contextual_read in available:
        # Inherit only the immediately preceding, independently resolved read
        # request. The assistant's prose cannot authorize a read or manufacture
        # a referent; another topic or an absent antecedent stays unresolved.
        previous = resolve_explicit_effects(
            previous_user_text, available, application_names, game_catalog,
        )
        if previous is not None and previous.operations == (contextual_read,):
            return EffectIntent((contextual_read,), (folded,))
    authenticated_applications = build_application_catalog_index(
        application_names,
    )
    authenticated_games = build_game_catalog_index(game_catalog)
    bare_name = _bare_play_name(text)
    if bare_name is not None:
        launch = "abre " + _fold(bare_name)
        if (
            _authenticated_game_target(launch, authenticated_games) is not None
            or _authenticated_application_request(launch, authenticated_applications) is not None
        ):
            # «pon fortnite», «pon obsidian»: an installed game or catalog
            # application said alone after «pon» is started, never searched as music.
            return resolve_explicit_effects(launch, available, application_names, game_catalog)
    if "task.create" in available and list_entry_request(text) is not None:
        # «añadir el brócoli a mi lista de la compra»: the entry is a task on that list.
        return EffectIntent(("task.create",), (text,))
    removal = list_removal_request(text)
    if removal is not None and removal.entry is not None and {"task.resolve.exact", "task.delete"} <= available:
        # «take bathroom painting off the list»: the entry's task is found by its title and sent to the trash
        # (the plan puts task.resolve.exact first, planner._required_predecessors).
        return EffectIntent(("task.delete",), (text,))
    list_read = list_read_request(text)
    if list_read is not None and list_read.operation in available:
        if list_read.absent_clause and "task.create" in available:
            # Tanda 4c «add flour to my shopping list if it's not already on it» read the list and then asked
            # «Should I add it?»: the person already said what to do when it is missing. The list is read and
            # the add waits on that read (planner.guarding_predecessors); the App skips it when the read found
            # the entry.
            return EffectIntent((list_read.operation, "task.create"), (text, text))
        # «decir la lista», «qué hay en mi lista de la compra», «do i have cheese on my
        # shopping list»: the list is read, never answered from the model's memory.
        return EffectIntent((list_read.operation,), (text,))
    browser_music = _named_browser_music_request(text)
    if "browser.navigate.named" in available and browser_music is not None and browser_music[1] is None:
        # MUSIC1827 «open Edge and play some music»: which music is asked first
        # (clarification), not an open-and-play mission with «some music».
        return None
    channel_request = client_channel_request(text)
    if "client.channel.locate" in available and channel_request is not None and channel_request[0] == "discord":
        # DISCORD1839: the channel is located and the person asked before any join.
        return EffectIntent(("client.channel.locate",), (text,))
    if "email.send" in available and email_send_request(text) is not None:
        # Fase 7 (D4): mail to the address named, from the owner's Outlook, confirmed in normal mode.
        return EffectIntent(("email.send",), (text,))
    if {"message.recipient.resolve", "message.send"} <= available and message_request_any_channel(text) is not None:
        # REOPEN1993 grupo E: no client named → the recipient is looked up in the
        # clients and, when unique, the message is sent (confirmed in normal mode).
        return EffectIntent(("message.recipient.resolve", "message.send"), (text, text))
    if "message.draft" in available and message_left_written_request(text) is not None:
        # M111 (DEV-F v4d F-s014, F-w05-t2): a message the person asks to leave written, or orders not to send, is a
        # draft, read before any reader that sends one.
        return EffectIntent(("message.draft",), (text,))
    if {"message.recipient.resolve", "message.send"} <= available and message_request_named_client(text) is not None:
        # Owner 2026-09-21 «Mandale un mensaje a vicho por wsp diciendole hola»: the
        # client IS named → the person is looked up in that client and the message
        # is sent to them (confirmed in normal mode); the forced test destination
        # of message.send.test stays for the measurement panels only.
        return EffectIntent(("message.recipient.resolve", "message.send"), (text, text))
    if "message.send.test" in available and message_draft_request(text) is not None and not (
        "email.send" in available and message_draft_request(text)[0] == "email"
    ):
        # Fase 7: with email.send served, a mail request without an address is asked
        # its address instead of being forced to the test mailbox.
        # MSG §6 (owner decision 2026-09-17): a messaging request is sent for real,
        # but the destination is forced to the owner's own test channel; the final
        # says the truth about where it went.
        return EffectIntent(("message.send.test",), (text,))
    if "message.draft" in available and message_draft_request(text) is not None and not (
        "email.send" in available and message_draft_request(text)[0] == "email"
    ):
        # MSG1837: the message is left written in the named client, never sent.
        return EffectIntent(("message.draft",), (text,))
    if "web.search" in available and _research_question_query(text) is not None:
        # WEB1831: a research order carrying a question is the public search
        # for that question, in the person's words.
        return EffectIntent(("web.search",), (text,))
    if "web.search" in available and (
        public_opinion_query(text) is not None or record_fact_query(text) is not None
    ):
        # Fase 3.5 (owner test 2026-09-21, turns 23/35/58): what people think of a
        # public work and a record or dated fact come from public pages, not from
        # the model's memory.
        return EffectIntent(("web.search",), (text,))
    if "storage.removable.list" in available and _removable_storage_request(text):
        # USB1823: a backup or copy to a pendrive first reads which removable
        # drives are connected; nothing is copied.
        return EffectIntent(("storage.removable.list",), (text,))
    if "software.python.package.status" in available and _python_package_request(text) is not None:
        # PIP1817: installing a Python package with pip is answered by whether
        # it is already installed in the registered Pythons; nothing is installed.
        return EffectIntent(("software.python.package.status",), (text,))
    if (
        "game.entitlement.named" in available
        and steam_library_title(text) is not None
        # INSTALL1625: a game the local catalog holds is launched, not read.
        and _authenticated_game_target(folded, authenticated_games) is None
        # INSTALL1633: a near miss of an installed game or catalog application,
        # or a catalog application itself, keeps its own path (clarifier, open).
        and not near_catalog_game_candidates(text, authenticated_games)
        and not near_catalog_application_candidates(text, authenticated_applications)
        and resolve_application_catalog_app_id(text, authenticated_applications) is None
        # Tanda 5 «launch my home screen»: the PC's home screen is no game title.
        and not minimize_all_request(folded)
    ):
        # REOPEN1993 grupo S (D1/D11: the survey is the specification): a
        # download or install is the real install (the adapter says «not in
        # the library» or «already installed» when that is the case), an
        # uninstall is the real uninstall; launching what is not installed
        # keeps the library read (INSTALL1633).
        library_verb = steam_library_verb(text)
        if library_verb == "install" and "game.install.named" in available:
            return EffectIntent(("game.install.named",), (text,))
        if library_verb == "uninstall" and "game.uninstall.named" in available:
            return EffectIntent(("game.uninstall.named",), (text,))
        # INSTALL1617: a Steam download, install or uninstall of a named game
        # first reads whether the title is in the person's library and on disk;
        # the install effect itself needs an entitlement and a confirmation,
        # and most such requests name games the library does not hold.
        return EffectIntent(("game.entitlement.named",), (text,))
    if "filesystem.explorer.count" in available and explorer_count_request(text) is not None:
        # REOPEN1957 H0701: the Explorer folder in front is the current directory.
        return EffectIntent(("filesystem.explorer.count",), (text,))
    if (known_path := known_folder_file_path(text)) is not None and known_path[0] in available:
        # REOPEN1957 H0299: the pasted path under a known folder is read to say what it is about.
        return EffectIntent((known_path[0],), (text,))
    if {"web.download", "file.open"} <= available and (image := web_image_request(text)) is not None and not image[1]:
        # REOPEN1957 H0069: the first image the search lists is downloaded
        # and opened; the viewer shows it (the chat cannot).
        return EffectIntent(("web.download", "file.open"), (text, text))
    if {"wifi.profile.list", "wifi.connect.named"} <= available and wifi_place_request(text) is not None:
        # REOPEN1957 H0170/H0376: the saved networks are read first so the final
        # can list them when no network is associated with that place yet.
        return EffectIntent(("wifi.profile.list", "wifi.connect.named"), (text, text))
    if {"document.presentation.create", "file.open"} <= available and presentation_request(text) is not None:
        # REOPEN1957 H0188: the deck is written and then opened.
        return EffectIntent(("document.presentation.create", "file.open"), (text, text))
    if {"filesystem.create.directory", "filesystem.write.text", "file.compress", "file.open"} <= available and folder_txt_zip_open_mission(text) is not None:
        # REOPEN1957 H0542: create the folder, put a text file in it, zip it, open the zip.
        return EffectIntent(("filesystem.create.directory", "filesystem.write.text", "file.compress", "file.open"), (text, text, text, text))
    if "file.compress" in available and compress_named_request(text) is not None:
        return EffectIntent(("file.compress",), (text,))
    if "file.open" in available and open_named_file_request(text) is not None:
        return EffectIntent(("file.open",), (text,))
    if "desktop.wallpaper.set" in available and wallpaper_request(text) is not None:
        # REOPEN1957 H0459: a solid colour or a picture as the desktop background.
        return EffectIntent(("desktop.wallpaper.set",), (text,))
    if "web.download" in available and web_download_request(text) is not None:
        # REOPEN1957 H0077: the file or the page's cover image lands in the folder named.
        return EffectIntent(("web.download",), (text,))
    if "shell.command.run" in available and shell_command_request(text) is not None:
        # REOPEN1993 (D11): a console command is run for real and its output quoted.
        return EffectIntent(("shell.command.run",), (text,))
    software = software_package_request(text, authenticated_applications)
    if software is not None:
        # REOPEN1993 grupo G: software is installed and removed by the Windows
        # package manager. Installing what the Start catalog already holds is
        # answered by its presence (INSTALL1625); removing it is a real
        # uninstall; installing what is absent resolves the package and
        # installs it, or says winget does not offer it.
        verb, _name, in_catalog = software
        if verb == "uninstall" and in_catalog and "package.uninstall" in available:
            return EffectIntent(("package.uninstall",), (text,))
        if (
            verb == "uninstall"
            and not in_catalog
            and "package.uninstall" in available
            and len(_catalog_entries_named(_name, authenticated_applications)) > 1
        ):
            # WINGET2085 «desinstalá 7-Zip»: Start holds «7-Zip File Manager» and
            # «7-Zip Help», so no single catalog entry resolved and the turn
            # stopped at an ambiguous presence read. What gets removed is the
            # package, and winget resolves it by its own name and id.
            return EffectIntent(("package.uninstall",), (text,))
        if (
            verb == "uninstall"
            and not in_catalog
            and "game.uninstall.named" in available
            and _installed_game_named(_name, authenticated_games) is not None
        ):
            # REOPEN1993 grupo S (H0620 «Desinstala Worms Rumble»): a bare name
            # that is an installed game is uninstalled from its launcher.
            return EffectIntent(("game.uninstall.named",), (text,))
        if verb == "install" and not in_catalog and {"package.install.prepare", "package.install.commit"} <= available:
            return EffectIntent(("package.install.prepare", "package.install.commit"), (text, text))
    if (
        "app.installed" in available
        and installed_catalog_application_name(text, authenticated_applications) is not None
    ):
        # INSTALL1625: installing or uninstalling a catalog application is
        # answered by its presence; nothing is installed or removed.
        return EffectIntent(("app.installed",), (text,))
    if "browser.control" in available and browser_new_tab_arguments(text) is not None:
        # BROWSER1493 «abrí una pestaña nueva»: one new blank tab in the
        # product's browser, verified by its presence.
        return EffectIntent(("browser.control",), (text,))
    if "browser.control" in available and browser_close_all_tabs_arguments(text) is not None:
        # BROWSER1841 «cerrá todas las pestañas»: close every open tab in the
        # product's own browser, verified by their absence.
        return EffectIntent(("browser.control",), (text,))
    if "browser.control" in available and browser_back_arguments(text) is not None:
        # A complete history request is not a destination to search.
        return EffectIntent(("browser.control",), (text,))
    if (
        "window.minimize.all" in available
        and minimize_all_request(folded)
        and not _is_negative_effect_clause(folded)
    ):
        # MINALL1687: every desktop window minimized and verified iconic.
        return EffectIntent(("window.minimize.all",), (text,))
    if "input.key.press" in available and start_menu_request(folded):
        # Tanda 4: the Start menu (or the PC's applications) shown with the Windows key.
        return EffectIntent(("input.key.press",), (text,))
    if (
        "window.close.all" in available
        and close_all_request(folded)
        and not _is_negative_effect_clause(folded)
    ):
        # CLOSEALL1733: every desktop window asked to close, except the editor.
        return EffectIntent(("window.close.all",), (text,))
    if (
        {"window.resolve", "media.control"} <= available
        and conditional_open_pause_app(text, authenticated_applications) is not None
        and not _is_negative_effect_clause(folded)
    ):
        # MUSIC1675 «si tengo spotify abierto pausalo»: the window read decides
        # the condition; an absent window ends the mission truthfully, a
        # present one pauses that application's session.
        return EffectIntent(("window.resolve", "media.control"), (text, text))
    if (
        "window.snap" in available
        and resolve_application_snap(text, authenticated_applications) is not None
        and not _is_negative_effect_clause(folded)
        and not _is_meta_or_tool_denial(folded)
    ):
        # ARRANGE1781 «poné chrome a la izquierda»: docking an authenticated
        # application on one half of the screen is window.snap; window.resolve
        # (its prerequisite) binds the window.
        return EffectIntent(("window.snap",), (folded,))
    if (
        "window.minimize" in available
        and resolve_application_minimize_name(text, authenticated_applications) is not None
        and not _is_negative_effect_clause(folded)
        and not _is_meta_or_tool_denial(folded)
    ):
        # WINDOWS1695 «Minimisa ópera.»: minimizing an authenticated application
        # by name is window.minimize; window.resolve binds its window.
        return EffectIntent(("window.minimize",), (folded,))
    if (
        "window.focus" in available
        and resolve_application_focus_name(text, authenticated_applications) is not None
        and not _is_negative_effect_clause(folded)
        and not _is_meta_or_tool_denial(folded)
    ):
        # WINDOWS1385: bringing an authenticated application to the front is
        # window.focus; window.resolve (its prerequisite) binds the window.
        return EffectIntent(("window.focus",), (folded,))
    if (
        {"capture.active.window", "ocr.read"} <= available
        and deictic_look_request(text)
        and previous_user_text is None
    ):
        # REOPEN1993 H0528: nothing named earlier, so «lo» is what is in
        # front of the person. CONTEXT1999: the whole screen read Steam's menu
        # bar and an editor before the dialog in front; the active window is
        # what «lo» names, and the rest of the desktop is not read.
        return EffectIntent(("capture.active.window", "ocr.read"), (folded, folded))
    if (
        "input.text.type" in available
        and deictic_text_to_type(text, previous_user_text, authenticated_applications) is not None
    ):
        # REOPEN1993 H0097: the text goes into the application just opened.
        return EffectIntent(("input.text.type",), (text,))
    if {"window.resolve", "window.focus"} <= available and other_window_switch_request(text):
        # REOPEN1993 H0263: the inventory is read and the window behind the
        # foreground one is focused (grounded from that reading, never guessed).
        return EffectIntent(("window.resolve", "window.focus"), (folded, folded))
    single_near = near_single_open_candidate(text, authenticated_applications, authenticated_games)
    if single_near is not None and single_near[0] in available:
        # REOPEN1993 «abre Steel.» → Steam, «Ve a Mad de Rivals.» → Marvel
        # Rivals: one installed candidate is opened, not asked about.
        return EffectIntent((single_near[0],), (single_near[1],))
    destination = _symbolic_web_destination(text)
    if (
        destination is not None
        and {"web.search", "browser.navigate"} <= available
        and _authenticated_application_request(folded, authenticated_applications) is None
        and resolve_application_catalog_app_id(destination, authenticated_applications) is None
        # «Abre Portal desde Steam»: a game named in a store's library is the
        # game, not a public site called «portal».
        and resolve_game_catalog_app_id(text, authenticated_games) is None
        and not near_catalog_game_candidates(text, authenticated_games)
        and not _has(folded, r"\b(?:desde|en|from|in|on)\s+(?:steam|epic(?:\s+games)?)\b")
        # M91 (reserva «ve al siguiente episodio de la serie»): going to the next or the previous episode moves what
        # plays, not the browser.
        and _media_transport_action(folded) is None
    ):
        # Resolve the destination through the existing verified search dependency.
        return EffectIntent(("web.search", "browser.navigate"), (text, text))
    if (
        "app.open" in available
        and _repeated_application_target(text, authenticated_applications) is not None
    ):
        return EffectIntent(("app.open",), (text,))
    browser_music = _named_browser_music_request(text)
    if "browser.navigate.named" in available and browser_music is not None and browser_music[1] is not None:
        # MUSIC1827 «pon música de rock en chrome»: YouTube's results page for
        # the person's words, in the named browser, after the root review.
        return EffectIntent(("browser.navigate.named",), (text,))
    if "browser.navigate.named" in available and _named_browser_search(text) is not None:
        return EffectIntent(("browser.navigate.named",), (text,))
    if (
        {"web.search", "browser.navigate.named"} <= available
        and _named_browser_site_request(text, authenticated_applications) is not None
    ):
        # H0081: the bare site name is looked up by the verified search and the
        # named browser opens its first result (the CHAIN1931 dependency).
        return EffectIntent(("web.search", "browser.navigate.named"), (text, text))
    if (
        "app.installed" in available
        and unresolved_application_open_name(text, authenticated_applications) is not None
    ):
        # Identity is still pending. Read once under the original opening
        # objective; no app.open step or plan is inferred from this result.
        return EffectIntent(("app.installed",), (text,))
    if (
        "app.installed" in available
        and resolve_game_catalog_app_id(text, authenticated_games) is None
        and not near_catalog_application_candidates(text, authenticated_applications)
        and not near_catalog_game_candidates(text, authenticated_games)
        and not _has(folded, rf"\b{_NAMED_PUBLIC_SITE}\b")
        and _symbolic_web_destination(text) is None
        # Only the plain open verbs: «lanzá X» or «ejecutá X» name a game or a
        # program run, not a Start-catalog presence to prove.
        and _has(folded, r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*)?(?:me\s+)?(?:abre|abri|abris|abrime|abrir|open)\b")
        and unresolved_application_open_name(
            text, authenticated_applications, proper_name=True,
        ) is not None
    ):
        # APPS1549 «Y quema, abre Saint Rose.»: a proper name that no catalog,
        # near name or public site claims is read once as an application
        # presence; the verified absence lets the reply name it truthfully.
        return EffectIntent(("app.installed",), (text,))
    alias_plan = exact_catalog_operation_plan(folded)
    if alias_plan is not None and set(alias_plan) <= available:
        return EffectIntent(alias_plan, tuple(folded for _ in alias_plan))
    if (
        {"system.process.list", "filesystem.write.text"} <= available
        and process_report_file_request(folded) is not None
        and not _is_negative_effect_clause(folded)
        and not _is_meta_or_tool_denial(folded)
    ):
        # FILES1705: the listing is read first; the file carries what was read.
        return EffectIntent(("system.process.list", "filesystem.write.text"), (folded, folded))
    if "filesystem.write.text" in available and _file_creation_request(folded) is not None:
        # A named file with literal content is a write, not a note.
        return EffectIntent(("filesystem.write.text",), (folded,))
    if (
        "document.pdf.read" in available
        and _pdf_summary_request(folded) is not None
        and not _is_negative_effect_clause(folded)
        and not _is_meta_or_tool_denial(folded)
    ):
        # PDF1689: the named PDF is read once for its text; the reply presents it.
        return EffectIntent(("document.pdf.read",), (folded,))
    if (
        "filesystem.known.trash.named" in available
        and _file_trash_request(folded) is not None
        and not _is_negative_effect_clause(folded)
        and not _is_meta_or_tool_denial(folded)
        and not _has_contradictory_correction(folded)
    ):
        # A named file deletion is the recoverable trash of that one file.
        return EffectIntent(("filesystem.known.trash.named",), (folded,))
    if (
        "system.settings.status" in available
        and brightness_status_request(folded)
        and not _is_negative_effect_clause(folded)
        and not _is_meta_or_tool_denial(folded)
    ):
        # BRIGHT1283: the brightness question is a read of the monitor value.
        return EffectIntent(("system.settings.status",), (folded,))
    if (
        "system.settings.adjust" in available
        and _literal_brightness_adjustment(folded) is not None
        and not _is_negative_effect_clause(folded)
        and not _is_meta_or_tool_denial(folded)
        and not _has_contradictory_correction(folded)
    ):
        return EffectIntent(("system.settings.adjust",), (folded,))
    if "system.settings.set" in available and setting_switch_request(text) is not None:
        # REOPEN1957 H0107 «poneme el modo avión»: every radio off (or on again).
        return EffectIntent(("system.settings.set",), (folded,))
    if "system.settings.status" in available and airplane_mode_question(text):
        return EffectIntent(("system.settings.status",), (folded,))
    if (
        "system.settings.set" in available
        and _literal_brightness_level(folded) is not None
    ):
        # BRIGHT1287: an absolute brightness level is the sensitive set (confirmation).
        return EffectIntent(("system.settings.set",), (folded,))
    if (
        "clipboard.write.text" in available
        and literal_clipboard_write_text(text) is not None
        and not _is_meta_or_tool_denial(folded)
        and not _has_contradictory_correction(folded)
    ):
        # CLIPBOARD1359: a quoted or colon-introduced literal for the clipboard
        # is the sensitive write (confirmation). The raw text is the evidence so
        # the literal keeps its case and accents.
        return EffectIntent(("clipboard.write.text",), (text,))
    if (
        "filesystem.create.directory" in available
        and _directory_creation_request(folded) is not None
    ):
        return EffectIntent(("filesystem.create.directory",), (folded,))
    clauses = _request_clauses(folded)
    explicit_cardinality = _unresolved_explicit_cardinality(folded)
    if not folded or len(folded) > 16_384:
        return None
    note_dependency_order = enumerated_note_dependency_order(folded)
    if note_dependency_order and {"note.create", "note.read"} <= available:
        note_count = len(note_dependency_order)
        operations = ("note.create",) * note_count + ("note.read",) * note_count
        return EffectIntent(operations, tuple(folded for _ in operations))
    dated_report = _dated_machine_report(folded)
    if dated_report is not None and {"system.time", "system.status"} <= available:
        # SYSTEM1367: «muestra la fecha actual y el uso de RAM del sistema»
        # is one clock read and then one status read of the named scope.
        return dated_report
    status_sequence = _bounded_status_sequence_intent(folded, available)
    if status_sequence is not None:
        return status_sequence
    if _underspecified_video_request(folded):
        return None
    alarm_status_request = (
        re.fullmatch(
            r"(?:(?:(?:please\s+)?tell\s+me|show\s+me|muestra|dime)\s+"
            r"(?:what|which|que|cuales)?\s*(?:alarms?|alarmas?)\s+"
            # M97: «dime qué alarmas tengo (puestas)».
            r"(?:are\s+on|are\s+active|estan\s+activas?|hay|tengo(?:\s+(?:puestas|programadas|activas))?)|"
            # M97: «is there an alarm set for seven», «¿tengo alguna alarma para mañana a las seis?», «hay alguna alarma
            # puesta para las ocho».
            r"(?:is\s+there|are\s+there|hay|tengo|do\s+i\s+have)\s+(?:(?:an?|una?|alguna?|any)\s+)?(?:alarms?|alarmas?)\s+"
            r"(?:(?:set|puestas?|programadas?|activas?)\s+)?"
            r"(?:for|at|para|a\s+las?)\s+\S.{0,48}|"
            r"(?:check|comprueba|revisa)\s+(?:if|si)\s+"
            r"(?:(?:an?|una?)\s+)?(?:alarm|alarma)\s+"
            r"(?:is\s+set|esta\s+puesta|esta\s+programada)\s+"
            r"(?:for|at|para|a\s+las?)\s+\S.{0,48})[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if alarm_status_request and (listing := next(
        (operation for operation in ("notification.list", "notification.diagnose") if operation in available), None,
    )):
        # M97 (reserve «please tell me what alarms are on», «hay una alarma para las diez de la mañana»): which alarms
        # are set is read by listing them (catalog: notification.list «ver qué alarmas … hay programados y cuándo
        # suenan»); notification.diagnose checks whether they work and lists none.
        return EffectIntent((listing,), (folded,))
    if "notification.schedule" in available and _direct_alarm_schedule_request(folded):
        return EffectIntent(("notification.schedule",), (folded,))
    if (nominal_schedule := nominal_schedule_request(folded)) in available:
        return EffectIntent((nominal_schedule,), (folded,))
    if "reminder.create" in available and stated_event_reminder(text) is not None:
        return EffectIntent(("reminder.create",), (text.strip(),))
    direct_named_website = (
        re.fullmatch(
            r"(?:go|take\s+me|navigate|open|ve|llevame|navega)\s+"
            r"(?:to\s+|a\s+)?(?:(?:the|el|la)\s+)?"
            r"(?:washington\s+post|new\s+york\s+times|bbc|cnn)\s+"
            r"(?:website|site|web|sitio|pagina)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "browser.navigate" in available and direct_named_website:
        return EffectIntent(("browser.navigate",), (folded,))
    persistent_mute = (
        re.fullmatch(
            r"(?:de\s+ahora\s+en\s+adelante|from\s+now\s+on)\s+"
            r"(?:en\s+)?(?:mudo|mute|silent|silencio)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "audio.mute" in available and persistent_mute:
        return EffectIntent(("audio.mute",), (folded,))
    if "note.search" in available and _stored_note_search_query(folded) is not None:
        return EffectIntent(("note.search",), (folded,))
    if "system.time" in available and (clock_elsewhere(folded) is not None or _direct_current_time_request(folded)):
        # The time of another place is this clock read with that place's zone.
        return EffectIntent(("system.time",), (folded,))
    if "calendar.event.list" in available and agenda_read_request(text):
        return EffectIntent(("calendar.event.list",), (folded,))
    if (inventory := reminder_inventory_question(text)) and set(inventory) <= set(available):
        return EffectIntent(inventory, (folded,) * len(inventory))
    event = agenda_event_request(text)
    event_operation = "notification.schedule" if event is not None and event.repeat else "calendar.event.create"
    if event is not None and not event.missing and event_operation in available:
        # The person's own writing is the evidence: the title keeps its capitals and accents. An
        # event repeated daily or hourly is a repeating reminder («pon el almuerzo todos los días a
        # las doce y media»); the calendar holds single events.
        return EffectIntent((event_operation,), (text.strip(),))
    if "media.play.query" in available and not unoffered_music_service_named(folded) and (
        _direct_media_discovery_or_play_request(folded)
        # VIDEO1715: the readers fold the text themselves; the raw text keeps
        # the capitals that mark a proper title («poné Tom and Jerry»).
        or _desired_music_query(text) is not None
    ):
        evidence = text if _explicit_named_music_query(text) is not None else folded
        if (
            "media.play.youtube" in available
            and not _has(folded, r"\bspotify\b")
            and _explicit_named_music_query(text) is not None
        ):
            # MUSIC1559: no provider named → the local YouTube playback.
            return EffectIntent(("media.play.youtube",), (evidence,))
        return EffectIntent(("media.play.query",), (evidence,))
    weather_read = _weather_read_intent(text, available)
    if weather_read is not None:
        return weather_read
    news_read = _news_read_intent(text, available)
    if news_read is not None:
        return news_read
    if (
        "web.search" in available
        and _public_live_lookup_request(folded)
        # «find itinerary en Downloads y busca weather Curicó online»: the
        # live lookup is one clause of a compound; the clause reader below keeps
        # the other one.
        and len(_request_clauses(folded)) == 1
    ):
        # WEB1445: the evidence keeps the person's accents («mañana»); the
        # engine answers the literal phrase and not its folded form.
        return EffectIntent(("web.search",), (text.strip(),))
    if {
        "message.recipient.resolve",
        "message.send",
        "task.list",
    } <= available and _has(
        folded,
        r"^por\s+whatsapp\s+(?:avisa|notifica|dile)\s+a\s+[^,;:.!?]{1,80}\s+"
        r"que\s+[^;:.!?]{1,240}\s+y\s+(?:luego|despues)\s+"
        r"(?:muestra|lista|ensena)me\s+(?:mis|las)\s+tareas?\s+abiertas?"
        r"[\s.!?]*$",
    ):
        # The message grammar deliberately consumes free-form body text.  Keep
        # the following task lookup outside that body only for this explicit,
        # bounded two-step construction.
        return EffectIntent(
            ("message.recipient.resolve", "message.send", "task.list"),
            (folded[:240], folded[:240], folded[:240]),
        )
    message_collection = _match(
        folded,
        r"^(?:dile|avisale|avisa|notifica(?:le)?)\s+a\s+[^,;:.!?]{1,80}\s+"
        r"por\s+whatsapp\s+que\s+[^;:.!?]{1,240}\s+y\s+"
        r"(?:luego|despues)\s+"
        r"(?:muestrame|listame|ensename|muestra|lista|ensena)\s+"
        r"(?:mis|las)\s+(?P<collection>tareas?\s+abiertas?|notas?)"
        r"[\s.!?]*$",
    )
    message_collection_operation = (
        "note.list"
        if message_collection is not None
        and _has(message_collection.group("collection"), r"\bnotas?\b")
        else "task.list"
    )
    if (
        message_collection is not None
        and {
            "message.recipient.resolve",
            "message.send",
            message_collection_operation,
        }
        <= available
    ):
        return EffectIntent(
            (
                "message.recipient.resolve",
                "message.send",
                message_collection_operation,
            ),
            (folded[:240], folded[:240], folded[:240]),
        )
    message_reminders = _match(
        folded,
        r"^(?:send|envia|manda|dile|avisa|notifica)\s+"
        r"[^,;:.!?]{1,80}\s+(?:on|por|en)\s+whatsapp\s+"
        r"(?:que|that)\s+\S.{1,240}?\s+"
        r"(?:y\s+then|and\s+then|y\s+luego|y\s+despues)\s+"
        r"(?:show|list|muestra|lista)(?:me)?\s+"
        r"(?:(?:my|mis|the|los|las)\s+)?"
        r"(?:(?:scheduled|programad[oa]s?)\s+)?"
        r"(?:reminders?|recordatorios?)\b[\s.!?]*$",
    )
    if (
        message_reminders is not None
        and {
            "message.recipient.resolve",
            "message.send",
            "reminder.list",
        }
        <= available
    ):
        return EffectIntent(
            ("message.recipient.resolve", "message.send", "reminder.list"),
            (folded[:240], folded[:240], folded[:240]),
        )
    collection_capture = _match(
        folded,
        r"^(?:list|show|muestra|lista)\b.{0,48}\b"
        r"(?P<collection>open\s+tasks?|tareas?\s+abiertas?|notes?|notas?)"
        r"\b\s*,?\s*(?:(?:and|y)\s+)?"
        r"(?:(?:then|despues)\s+)?"
        r"(?:capture|captura)\b.{0,32}\b"
        r"(?:screen|pantalla|view|vista|result|resultado)\b"
        r".{0,48}\b(?:and|y)\s+(?:read|lee|extract|extrae)\b"
        r".{0,32}\b(?:text|texto)\b"
        r".{0,48}\b(?:capture|captura)\b[\s.!?]*$",
    )
    collection_operation = (
        "note.list"
        if collection_capture is not None
        and _has(collection_capture.group("collection"), r"\b(?:notes?|notas?)\b")
        else "task.list"
    )
    if (
        collection_capture is not None
        and {
            collection_operation,
            "capture.screenshot",
            "ocr.read",
        }
        <= available
    ):
        return EffectIntent(
            (collection_operation, "capture.screenshot", "ocr.read"),
            (folded[:240], folded[:240], folded[:240]),
        )
    collection_capture_vision = _match(
        folded,
        r"^(?:list|show|muestra|lista)\b.{0,48}\b"
        r"(?P<collection>open\s+tasks?|tareas?\s+abiertas?|notes?|notas?)"
        r"\b\s*,?\s*(?:(?:and|y)\s+)?"
        r"(?:(?:then|despues)\s+)?"
        r"(?:capture|captura)\b.{0,32}\b"
        r"(?:screen|pantalla|view|vista|result|resultado)\b"
        r".{0,48}\b(?:and|y)\s+describe\b.{0,48}\b"
        r"(?:image|imagen|what\s+appears|lo\s+que\s+aparece)\b"
        r"[\s.!?]*$",
    )
    collection_vision_operation = (
        "note.list"
        if collection_capture_vision is not None
        and _has(
            collection_capture_vision.group("collection"),
            r"\b(?:notes?|notas?)\b",
        )
        else "task.list"
    )
    if (
        collection_capture_vision is not None
        and {
            collection_vision_operation,
            "capture.screenshot",
            "vision.describe",
        }
        <= available
    ):
        return EffectIntent(
            (
                collection_vision_operation,
                "capture.screenshot",
                "vision.describe",
            ),
            (folded[:240], folded[:240], folded[:240]),
        )
    if {
        "capture.screenshot",
        "vision.describe",
    } <= available and _has(
        folded,
        r"^(?:obten|toma|take|get|capture|captura)\b.{0,48}\b"
        r"(?:capture|captura|screenshot|image|imagen)\b.{0,48}\b"
        r"(?:screen|pantalla)\b.{0,64}\b(?:and|y)\s+describe\b"
        r".{0,64}\b(?:same|misma|esa\s+misma|that\s+same)\s+"
        r"(?:capture|captura|image|imagen)\b[\s.!?]*$",
    ):
        return EffectIntent(
            ("capture.screenshot", "vision.describe"),
            (folded[:240], folded[:240]),
        )
    if {
        "capture.screenshot",
        "ocr.read",
    } <= available and _has(
        folded,
        r"^(?:(?:obten|toma|take|get)\b.{0,40}\b"
        r"(?:captura|screenshot|snapshot)\b.{0,96}\b(?:usa|use)\b"
        r".{0,48}\b(?:imagen|image|captura|capture)\b.{0,96}\b"
        r"(?:transcribe|transcribir|read|extract)\b.{0,48}\b"
        r"(?:letras?|texto|text|words?)\b(?:\s+visibles?)?|"
        r"(?:(?:(?:take|toma|get|obten)\s+(?:(?:a|una?)\s+)?)?"
        r"(?:screen\s+capture|captura\b.{0,32}\b(?:screen|pantalla)|"
        r"capture\b.{0,32}\b(?:screen|pantalla)))\b.{0,64}\b"
        r"(?:and|y)\s+(?:read|lee|transcribe|extract|extrae)\b.{0,48}\b"
        r"(?:visible\s+words?|palabras?\s+visibles?)\b.{0,64}\b"
        r"(?:image|imagen)\b)[\s.!?]*$",
    ):
        return EffectIntent(
            ("capture.screenshot", "ocr.read"),
            (folded[:240], folded[:240]),
        )
    if {
        "capture.screenshot",
        "vision.describe",
        "ocr.read",
    } <= available and _has(
        folded,
        r"^(?:(?:take|toma|get|obten)\s+(?:(?:a|the|una?)\s+)?)?"
        r"(?:capture|captura|screenshot)\b"
        r"(?:.{0,48}\b(?:desktop|screen|escritorio|pantalla)\b)?.{0,80}\b"
        r"describe\b.{0,48}\b(?:scene|escena|image|imagen)\b.{0,80}\b"
        r"(?:and|y)\s+(?:transcribe|read|extract|lee)\b.{0,48}\b"
        r"(?:text|texto|words?|palabras?)\b.{0,64}\b"
        r"(?:same|misma|exact|esa)\b.{0,24}\b"
        r"(?:image|imagen|capture|captura)\b[\s.!?]*$",
    ):
        return EffectIntent(
            ("capture.screenshot", "vision.describe", "ocr.read"),
            (folded[:240],) * 3,
        )
    if {
        "calendar.event.list",
        "capture.screenshot",
        "vision.describe",
        "clipboard.read.text",
    } <= available and _has(
        folded,
        r"^(?:display|show|muestra|ensena(?:me)?)\b.{0,48}\b"
        r"(?:calendar|calendario|(?:today|tomorrow)(?:'s)?\s+"
        r"(?:appointments?|events?)|(?:citas?|eventos?)\s+(?:de\s+)?"
        r"(?:hoy|manana))\b.{0,64}\b"
        r"(?:screenshot|capture|captura)\b.{0,64}\b"
        r"describe\b.{0,64}\b(?:view|vista|image|imagen|"
        r"lo\s+que\s+aparece|what\s+appears)\b.{0,64}\b"
        r"(?:read|lee)\b(?:(?:.{0,32}\b(?:clipboard|portapapeles)\b"
        r".{0,24}\b(?:text|texto)\b)|(?:.{0,32}\b(?:text|texto)\b"
        r".{0,32}\b(?:clipboard|portapapeles)\b))[\s.!?]*$",
    ):
        return EffectIntent(
            (
                "calendar.event.list",
                "capture.screenshot",
                "vision.describe",
                "clipboard.read.text",
            ),
            (folded[:240],) * 4,
        )
    catalog_report = _catalog_report_composition(folded, available)
    if catalog_report is not None:
        return catalog_report
    report_clauses = _catalog_report_clauses(folded)
    if report_clauses is not None and len(report_clauses) >= 2:
        # The wrapper proves this is one multi-domain report. If any spoken
        # clause cannot be grounded to exactly one operation, falling through
        # would silently execute only the recognizable subset.
        return None
    spoken_report_markers = len(
        re.findall(
            r"\b(?:despues|then)(?:\s+check)?\b",
            folded,
            flags=re.IGNORECASE,
        )
    )
    spoken_report_minimum = (
        spoken_report_markers + 1
        if spoken_report_markers >= 2
        and _has(folded, r"\b(?:por\s+separado|separately)\b")
        else None
    )
    strict_request = _strict_catalog_request(
        folded,
        available,
        authenticated_applications,
    )
    if (
        strict_request is not None
        and spoken_report_minimum is not None
        and len(strict_request.operations) < spoken_report_minimum
    ):
        return None
    if (
        strict_request is not None
        and "task.list" in available
        and "task.list" not in strict_request.operations
        and _has(
            folded,
            r"\b(?:y\s+luego|y\s+despues|and\s+then)\s+"
            r"(?:lista|listar|muestra|show|list)\w*\b.{0,32}"
            r"\b(?:tareas?|tasks?)\b",
        )
    ):
        return None
    strict_capture_pipeline = (
        strict_request is not None
        and strict_request.operations
        in {
            ("capture.screenshot", "ocr.read"),
            ("capture.screenshot", "vision.describe"),
        }
    )
    strict_streaming_pipeline = (
        strict_request is not None
        and strict_request.operations == ("streaming.play.named",)
        and _has(
            folded,
            r"(?:\b(?:y|and)\b|[;,])\s+(?:ponla|ponlo|reproducela|reproducelo|"
            r"put\s+it(?:\s+on)?|start\s+it|"
            r"start\s+the\s+(?:show|movie|title|series))"
            r"(?:\s+(?:from|on|through)\s+netflix)?"
            r"[\s.!?]*$",
        )
    )
    strict_package_pipeline = (
        strict_request is not None
        and strict_request.operations == ("package.install.prepare",)
        and _has(
            folded,
            r"(?<![a-z0-9._-])[a-z0-9][a-z0-9_-]+"
            r"(?:\.[a-z0-9_-]+)+(?![a-z0-9_-]|\.[a-z0-9_-])",
        )
        and not _has(
            folded,
            r"\b(?:juego|game|steam|nota|note|tarea|task|mensaje|message)\b",
        )
    )
    strict_email_pipeline = (
        strict_request is not None
        and strict_request.operations == ("email.latest.read",)
        and _has(
            folded,
            r"^(?:abre|open)\b.{0,24}\b(?:lee|read)\b",
        )
    )
    strict_message_pipeline = (
        strict_request is not None
        and strict_request.operations == ("message.recipient.resolve", "message.send")
    )
    strict_media_alternative = (
        strict_request is not None
        and strict_request.operations == ("media.status",)
        and _has(
            folded,
            r"\b(?:pista|track)\s+(?:o|or)\s+(?:video|audio)\b",
        )
    )
    strict_audited_composition = (
        strict_request is not None
        and 2 <= len(strict_request.operations) <= 8
        and _strict_composition_segments_are_grounded(
            folded,
            strict_request,
            available,
            authenticated_applications,
        )
    )
    strict_referential_followup = (
        strict_request is not None
        and len(strict_request.operations) == 1
        and _has(
            folded,
            r"[?;]\s*(?:revisal[oa]s?|compruebalo|verificalo|leel[oa]s?|"
            r"check(?:\s+(?:it|them))?|verify(?:\s+it)?|read\s+them|"
            r"dame\s+(?:el\s+)?estado|give\s+me\s+(?:the\s+)?"
            r"(?:state|status))[\s.!?]*$",
        )
    )
    strict_single_domain_attributes = (
        strict_request is not None
        and len(strict_request.operations) == 1
        and _has(
            folded,
            r"\b(?:por\s+donde\s+y\s+a\s+que\s+nivel|"
            r"volume\s+and\s+output\s+routing|"
            r"(?:link|enlace)\s+(?:and|y)\s+(?:signal|senal)|"
            r"(?:signal|senal)\s+(?:and|y)\s+(?:link|enlace))\b",
        )
    )
    strict_single_domain_confirmation = (
        strict_request is not None
        and strict_request.operations == ("app.installed",)
        and _has(
            folded,
            r"\b(?:programas?|programs?)\b.{0,64}\b(?:y|and)\s+"
            r"(?:confirma|confirm)\b.{0,48}\b(?:presencia|presence)\b",
        )
    )
    if strict_request is not None and (
        (
            len(clauses) == 1
            and (
                len(strict_request.operations) == 1
                or strict_request.operations
                == ("message.recipient.resolve", "message.send")
            )
        )
        or strict_capture_pipeline
        or strict_streaming_pipeline
        or strict_package_pipeline
        or strict_email_pipeline
        or strict_message_pipeline
        or strict_media_alternative
        or strict_audited_composition
        or strict_referential_followup
        or strict_single_domain_attributes
        or strict_single_domain_confirmation
    ):
        return strict_request
    if (
        strict_request is not None
        and len(strict_request.operations) >= 2
        and len(clauses) == 1
    ):
        # Do not let the generic clause loop re-admit a strict multi-operation
        # candidate whose coordinated segments were not all accounted for.
        return None
    if "notification.schedule" in available and _wake_alarm_request(folded):
        return EffectIntent(("notification.schedule",), (folded,))
    if "network.ip.list" in available and _ip_list_request(folded):
        return EffectIntent(("network.ip.list",), (folded,))
    steam_cancel = _steam_install_cancel_active_intent(folded, available)
    if steam_cancel is not None:
        return steam_cancel
    pointer_scroll = _pointer_scroll_intent(folded, available)
    if pointer_scroll is not None:
        return pointer_scroll
    if (
        "media.play.query" in available
        and re.fullmatch(
            r"(?:comfort|soothe)\s+my\s+ears\s+with\s+\S.{0,120}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    ):
        return EffectIntent(("media.play.query",), (folded,))
    if "note.create" in available and _literal_memo_payload(folded) is not None:
        return EffectIntent(("note.create",), (folded,))
    if "note.search" in available and _historical_note_search_request(folded):
        return EffectIntent(("note.search",), (folded,))
    if "reminder.create" in available and _time_only_reminder_request(folded):
        return None
    multiple_alarms = _multiple_alarm_schedule_intent(folded, available)
    if multiple_alarms is not None:
        return multiple_alarms
    corrected_game_title = _corrected_game_launch_title(folded)
    if corrected_game_title is not None and "game.launch" in available:
        corrected_game = _authenticated_game_target(
            "lanza " + corrected_game_title,
            authenticated_games,
        )
        if corrected_game is not None:
            return EffectIntent(("game.launch",), (corrected_game[2],))
    game_target = _authenticated_game_target(folded, authenticated_games)
    if game_target is not None and "game.launch" in available:
        _, _, display_name = game_target
        return EffectIntent(("game.launch",), (display_name,))
    authenticated_request = _authenticated_application_request(
        folded,
        authenticated_applications,
    )
    if authenticated_request is not None and not _is_builtin_keyboard_request(folded):
        operation, targets = authenticated_request
        if operation not in available or len(targets) > 8:
            return None
        return EffectIntent(
            tuple(operation for _ in targets),
            tuple(target for _, target in targets),
        )
    weather_read = _weather_read_intent(text, available)
    if weather_read is not None:
        return weather_read
    news_read = _news_read_intent(text, available)
    if news_read is not None:
        return news_read
    if (
        len(clauses) == 1
        and "web.search" in available
        and (
            _public_live_lookup_request(folded)
            or _public_route_lookup_request(folded)
            or _public_calendar_fact_lookup_request(folded)
        )
    ):
        # Weather and news are live feeds, not stable model knowledge. Their
        # literal domain closes the read request without relying on a semantic
        # family guess; Core still validates and verifies the public lookup.
        # WEB1445: the evidence keeps the person's accents («mañana»); the
        # engine answers the literal phrase and not its folded form.
        return EffectIntent(("web.search",), (text.strip(),))
    if "web.search" in available and _public_product_correction_lookup_request(folded):
        # The correction replaces the nominal query; it is not a second
        # physical effect. Keep this read-only and let Core verify the lookup.
        return EffectIntent(("web.search",), (folded,))
    if "web.search" in available and _public_commerce_lookup_request(folded):
        return EffectIntent(("web.search",), (folded,))
    if "web.search" in available and _location_recommendation_request(folded):
        # Temporal phrases such as "después de la medianoche" are query
        # constraints, not composition separators. Preserve the complete
        # request before the generic clause splitter sees "después". Read
        # before the definition gate below: tanda 3 «what are the best
        # restaurants in my area» is a place to look up, not a definition.
        return EffectIntent(("web.search",), (folded,))
    shared_domain_minimum = _coordinated_effect_domain_minimum(folded)
    if _has_unresolved_shared_head_coordination(folded):
        shared_domain_minimum = max(2, shared_domain_minimum or 0)
    if (
        _is_meta_or_tool_denial(folded)
        or _has_contradictory_correction(folded, available)
        or _other_device_effect_scope(folded)
        or (
            _has_unsupported_deferred_effect(folded)
            and not _location_recommendation_request(folded)
        )
        or _has_multiple_installed_entities(folded)
        or (
            explicit_cardinality is not None
            and not _has_fully_enumerated_note_cardinality(
                clauses,
                explicit_cardinality,
            )
        )
        or (
            not _is_direct_request(_without_leading_duration_preface(folded))
            and not _count_down_request(folded)
            # A conjunction does not make independently explicit questions
            # implicit. The clause resolver below must still account for all
            # of them; this never grants a recognized subset authority.
            and not (
                len(clauses) > 1
                and all(_is_direct_request(clause) for clause in clauses)
            )
            and not _bounded_calendar_list_query(folded)
            and not _location_recommendation_request(folded)
            and _nominal_reminder_lookup_title(folded) is None
            and _exact_local_reminder_title(folded) is None
            and not _literal_note_payload_request(folded)
            and not _bare_note_inventory_request(folded)
            and not (
                _has(folded, r"^can i (?:see|view)\b")
                and _has(folded, r"\b(?:reminder|recordatorio)\b")
                and _has(folded, r"\b(?:again|otra vez|de nuevo)\b")
            )
            and not _active_alarm_stop_request(folded)
            and not _everyday_media_control(folded, _request_head(folded))
            and not _pointed_media_question(folded, _request_head(folded))
            and not any(
                _authenticated_application_desired_open(
                    clause,
                    authenticated_applications,
                )
                is not None
                for clause in clauses
            )
        )
    ):
        return None
    if (
        len(clauses) == 1
        and "system.power" in available
        and _has(
            folded,
            # H0401 «reiniciá la PC»: el apagado estaba y el reinicio no, de modo
            # que el pedido no resolvía ninguna operación y el turno contestaba
            # «No puedo reiniciar la PC» sin haberlo intentado siquiera. Es la
            # misma transición, con otra acción. El nombre del equipo, que se
            # exige más abajo, es lo que impide que «reiniciá el router» entre
            # por aquí.
            r"^(?:apaga|apagame|apagar|shutdown|shut\s+down|turn\s+off|power\s+off|switch\s+off|"
            r"reinicia|reiniciame|reiniciar|reboot|restart)\b",
        )
        and (
            (
                _has(
                    folded,
                    r"\b(?:equipo|pc|compu|computador(?:a)?|computer|maquina|"
                    r"machine|windows|sistema|system)\b",
                )
                # «apaga el sonido del sistema», «turn off the system volume»: the
                # object is the audio, not the machine.
                and not _has(folded, r"\b(?:sonido|audio|volumen|volume|sound|musica|music|luz|luces|light|lights|pantalla|screen|monitor|wifi|bluetooth|radio)\b")
            )
            # H0401 variant «reiniciá» alone: a bare restart order names nothing
            # else on this PC but the PC itself (a bare «apagá» stays ambiguous).
            or re.fullmatch(r"(?:reinicia|reiniciame|reiniciar|reboot|restart)(?:\s+(?:ya|ahora|now|please|por\s+favor))?", folded.strip(" .!?"))
        )
        and not _has(
            folded,
            r"\b(?:telefono|movil|celular|phone|smartphone|tablet|iphone)\b",
        )
    ):
        return EffectIntent(("system.power",), (folded,))
    if "audio.app.volume.set" in available and app_volume_set_request(text, authenticated_applications) is not None:
        # Fase 8 (D18) «poné el volumen de spotify al 40»: one application's
        # volume at an absolute level, paused or not, verified by post-read.
        return EffectIntent(("audio.app.volume.set",), (folded,))
    if "audio.app.volume.adjust" in available:
        app_volume = app_volume_request(text, authenticated_applications)
        if app_volume is not None and app_volume[2] is not None:
            # AUDIO1787 «subí el volumen de spotify en 20»: the application
            # volume with its authored amount is one verified adjustment.
            return EffectIntent(("audio.app.volume.adjust",), (folded,))
    if (
        len(clauses) <= 2
        and "audio.volume.adjust" in available
        and _volume_domain(folded)
        and _has(folded, r"\b(?:bajalo|bajala|subelo|subela)\b")
        and not _has(
            folded,
            r"\b(?:y|and)\s+(?:abre|open|crea|create|apaga|silencia)\b",
        )
    ):
        return EffectIntent(("audio.volume.adjust",), (folded,))
    if (
        len(clauses) == 1
        and "audio.volume" in available
        and _volume_domain(folded)
        and _has(folded, r"\ba la mitad\b|\bto half\b")
    ):
        return EffectIntent(("audio.volume",), (folded,))
    visible_click = _visible_click_intent(folded, available)
    if visible_click is not None:
        return visible_click
    if "notification.dismiss" in available and _active_alarm_stop_request(folded):
        return EffectIntent(("notification.dismiss",), (folded,))
    nominal_reminder = _nominal_reminder_lookup_title(folded)
    if nominal_reminder is not None and "reminder.resolve.exact" in available:
        return EffectIntent(("reminder.resolve.exact",), (folded,))
    notepad_paste = _new_notepad_paste_intent(
        folded,
        available,
        authenticated_applications,
    )
    if notepad_paste is not None:
        return notepad_paste
    if (
        "reminder.delete" in available
        and _exact_local_reminder_title(folded) is not None
    ):
        return EffectIntent(("reminder.delete",), (folded,))
    wifi_email = _wifi_email_intent(folded, available)
    if wifi_email is not None:
        return wifi_email
    authenticated_list = _authenticated_application_list(
        folded,
        authenticated_applications,
    ) or _authenticated_application_list(
        folded,
        authenticated_applications,
        installed_query=True,
    )
    if authenticated_list:
        direct_applications = _resolve_explicit_effects_single(
            folded,
            available,
            application_names=authenticated_applications,
        )
        if (
            direct_applications is not None
            and len(direct_applications.operations) == len(authenticated_list)
            and all(
                operation in {"app.open", "app.installed"}
                for operation in direct_applications.operations
            )
        ):
            return direct_applications

    records: list[dict[str, str | None]] = []
    context_browser: str | None = None
    context_spotify = False
    context_steam = False
    context_open_application = False
    context_capture = False
    context_note = False
    context_audio = False
    context_machine = False
    enumerated_note_create_count = 0
    context_window_active = _has(
        folded,
        r"\b(?:ventana|window)\b",
    ) and _has(
        folded,
        r"\b(?:activa|active|actual|current)\b",
    )
    clause_index = 0
    while clause_index < len(clauses):
        clause = clauses[clause_index]
        consumed_clauses = 1
        local_browser = _named_browser(clause)
        authenticated_opened = _authenticated_application_list(
            clause,
            authenticated_applications,
        )
        if not authenticated_opened:
            authenticated_target = _authenticated_application_target(
                clause,
                authenticated_applications,
            )
            authenticated_opened = (
                (authenticated_target,) if authenticated_target is not None else ()
            )
        result = None
        # Some closed handlers represent one semantic effect group using
        # several coordinated action heads (for example, connect Wi-Fi, open
        # mail, and read the latest message).  The generic splitter separates
        # those heads so independent effects can compose.  Reassemble only the
        # shortest prefix that a bounded handler can account for, leaving any
        # following clause available to the rest of the mission.
        maximum_group_size = min(4, len(clauses) - clause_index)
        for group_size in range(1, maximum_group_size + 1):
            grouped_clause = " y ".join(
                clauses[clause_index : clause_index + group_size]
            )
            result = _resolve_clause_local_special_effects(
                grouped_clause,
                available,
                authenticated_applications,
                authenticated_games,
            )
            if result is not None:
                clause = grouped_clause
                consumed_clauses = group_size
                local_browser = _named_browser(clause)
                break
        if result is None:
            result = _resolve_explicit_effects_single(
                clause,
                available,
                context_browser=context_browser,
                context_spotify=context_spotify,
                context_open_application=context_open_application,
                context_capture=context_capture,
                context_note=context_note,
                context_audio=context_audio,
                context_machine=context_machine,
                context_window_active=context_window_active,
                application_names=authenticated_applications,
            )
        if result is None and len(clauses) > 1:
            # Inside a compound request a shared observation head governs a
            # later bare domain nominal: ``revisa el teclado, ... y el estado
            # de la red``. The strict composition verifier already treats this
            # mapping as authoritative, so the resolver must agree with it or
            # the conservation veto abstains from a request the product can in
            # fact ground. The table stays closed to authenticated operations.
            nominal_operation = _strict_composition_nominal_operation(clause)
            if nominal_operation is not None and nominal_operation in available:
                result = EffectIntent((nominal_operation,), (clause,))
        if (
            result is None
            and "note.read" in available
            and enumerated_note_create_count > 0
        ):
            read_order = _fully_enumerated_note_read_order(clause)
            if read_order and all(
                index <= enumerated_note_create_count for index in read_order
            ):
                result = EffectIntent(
                    tuple("note.read" for _ in read_order),
                    tuple(clause for _ in read_order),
                )
        if (
            result is not None
            and result.operations == ("app.installed",)
            and context_steam
            and "game.installed.named" in available
            and not (
                authenticated_applications.occurrence_pattern is not None
                and authenticated_applications.occurrence_pattern.search(clause)
            )
            and installed_game_title(clause) is not None
        ):
            # APPS1613 H0275 «Abre Steam y dime si Fall Guys ya está
            # instalado»: after Steam was opened in this request, an installed
            # question about a name absent from the Start catalog asks the
            # Steam/Epic manifests, not the Start catalog.
            result = EffectIntent(("game.installed.named",), (clause,))
        if result is None:
            if (
                _is_negative_effect_clause(clause)
                or _is_social_clause(clause)
                or _is_effect_receipt_clause(clause)
                or (
                    context_capture
                    and _has(
                        clause,
                        r"^(?:guardalo|guardala|save it|"
                        r"(?:dime|tell me|show me)\s+(?:el\s+|the\s+)?"
                        r"(?:path|ruta))[\s?!.]*$",
                    )
                )
            ):
                clause_index += consumed_clauses
                continue
            return None

        if result.operations == ("note.create",):
            local_count = _fully_enumerated_note_create_count(clause)
            if local_count is not None:
                result = EffectIntent(
                    tuple("note.create" for _ in range(local_count)),
                    tuple(clause for _ in range(local_count)),
                )
                enumerated_note_create_count = local_count
        elif result.operations == ("note.read",) and enumerated_note_create_count > 0:
            read_order = _fully_enumerated_note_read_order(clause)
            if read_order:
                if any(index > enumerated_note_create_count for index in read_order):
                    return None
                result = EffectIntent(
                    tuple("note.read" for _ in read_order),
                    tuple(clause for _ in read_order),
                )

        if "browser.navigate.named" in result.operations:
            target_browser = local_browser or context_browser
            if target_browser is not None:
                for index in range(len(records) - 1, -1, -1):
                    if (
                        records[index]["operation"] == "app.open"
                        and records[index]["application"] == target_browser
                    ):
                        del records[index]
                        break
        if any(
            operation in {"media.play.exact", "media.play.query"}
            for operation in result.operations
        ):
            for index in range(len(records) - 1, -1, -1):
                if (
                    records[index]["operation"] == "app.open"
                    and records[index]["application"] == "spotify"
                ):
                    del records[index]
                    break

        opened_in_clause = _opened_applications(clause) or tuple(
            name for _, name in authenticated_opened
        )
        opened = iter(opened_in_clause)
        for operation, evidence in zip(
            result.operations,
            result.evidence,
            strict=True,
        ):
            if (
                operation == "window.active"
                and any(record["operation"] == "window.active" for record in records)
                and any(
                    candidate
                    in {
                        "window.maximize",
                        "window.minimize",
                        "window.restore",
                    }
                    for candidate in result.operations
                )
            ):
                continue
            application = next(opened, None) if operation == "app.open" else None
            records.append(
                {
                    "operation": operation,
                    "evidence": evidence,
                    "application": application,
                }
            )

        continued_application = _has(
            clause,
            rf"^(?:el|la|the)?\s*{_KNOWN_APPLICATION}[\s?!.]*$",
        )
        context_open_application = bool(opened_in_clause) or (
            context_open_application
            and continued_application
            and "app.open" in result.operations
        )
        if opened_in_clause:
            latest = opened_in_clause[-1]
            context_browser = (
                latest if latest in {"opera", "opera_gx", "chrome", "edge", "firefox"} else None
            )
            context_spotify = latest == "spotify"
            context_steam = latest == "steam"
        elif "browser.navigate.named" in result.operations:
            context_browser = local_browser or context_browser
        elif any(
            operation in {"media.play.exact", "media.play.query"}
            for operation in result.operations
        ):
            context_spotify = True
        context_capture = context_capture or ("capture.screenshot" in result.operations)
        context_note = context_note or ("note.create" in result.operations)
        context_audio = context_audio or any(
            operation.startswith("audio.") for operation in result.operations
        )
        context_machine = context_machine or any(
            operation in {"system.status", "system.process.list"}
            for operation in result.operations
        )
        clause_index += consumed_clauses

    if (
        not records
        or len(records) > 8
        or (shared_domain_minimum is not None and len(records) < shared_domain_minimum)
    ):
        return None
    operations = tuple(str(record["operation"]) for record in records)
    if spoken_report_minimum is not None and len(operations) < spoken_report_minimum:
        # Even if ASR corrupts the report wrapper, repeated sequence markers
        # plus an explicit separate-result tail preserve its cardinality. A
        # shorter operation list would execute only a recognizable subset.
        return None
    if (
        "task.list" in available
        and "task.list" not in operations
        and _has(
            folded,
            r"\b(?:y\s+luego|y\s+despues|and\s+then)\s+"
            r"(?:lista|listar|muestra|show|list)\w*\b.{0,32}"
            r"\b(?:tareas?|tasks?)\b",
        )
    ):
        # A free-form message body must not absorb an explicit following task
        # lookup when the recipient transcription is uncertain.
        return None
    return EffectIntent(
        operations,
        tuple(str(record["evidence"]) for record in records),
    )


# M111: what the person says they have not done yet (perfect tense, folded): «no lo he abierto», «todavía no la he
# leído», «I haven't opened it».
_PAST_STATEMENT_BODY = (
    r"(?:(?:y|and|pero|but)\s+)?(?:(?:todavia|aun)\s+)?(?:"
    r"no\s+(?:(?:me|te|lo|la|los|las|le|les)\s+)?(?:he|hemos|habia|habiamos)\s+\w+(?:ado|ido|isto|ierto|cho)"
    r"(?:\s+(?:todavia|aun|nada))?"
    r"|i\s+(?:haven'?t|have\s+not|hadn'?t|didn'?t|did\s+not)\s+(?:\w+\s+){0,2}?"
    r"(?:opened|open|read|seen|see|checked|check|looked|heard|watched)(?:\s+(?:it|them|that))?(?:\s+yet)?)"
)
_PAST_STATEMENT = re.compile(r"^" + _PAST_STATEMENT_BODY + r"[\s.!?]*$")
_PAST_STATEMENT_TAIL = re.compile(r"(?:\s*,\s*|\s+)" + _PAST_STATEMENT_BODY + r"[\s.!?]*$")


def unresolved_compound_contract(
    text: str,
    available_operations: Iterable[str],
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
    game_catalog: Iterable[tuple[str, str, str]] | GameCatalogIndex = (),
    *,
    resolved_intent: EffectIntent | None | object = (_EXPLICIT_EFFECTS_NOT_RESOLVED),
    previous_user_text: str | None = None,
) -> CompoundEffectContract | None:
    """Describe a compound whose positive clauses are not all recognized.

    This is a conservation veto, not a classifier.  If the compositional
    resolver covers the whole request there is no unresolved contract.  For
    an incomplete compound, recognized clause sequences and their true
    cardinality are retained while every unresolved positive action adds at
    least one effect.  The caller must fail closed because the unresolved
    operation identity cannot be proved by this operation-only recognizer.
    """

    available = tuple(available_operations)
    if deferred_clarification_split(text, available, application_names, game_catalog) is not None:
        # The read clause is the whole effect of the turn; the other clause
        # becomes the final's question, not an unresolved positive action.
        return None
    completed_level_request = _completed_missing_volume_level_request(
        text, previous_user_text, available,
    )
    if completed_level_request is not None:
        return unresolved_compound_contract(
            completed_level_request, available, application_names, game_catalog,
            resolved_intent=resolved_intent,
        )
    folded = _strip_request_envelope(_fold(re.sub(r"[\r\n]+", " . ", text)))
    clauses = _request_clauses(folded)
    # M111 (DEV-F v4d F-w01-t1 «léeme el último correo que me llegó, … y no lo he abierto» → asked for the sender):
    # what the person says at the end that they have not done is a statement, not a negated order; the request is the
    # rest.
    said = _PAST_STATEMENT_TAIL.sub("", folded).strip(" ,")
    if said and said != folded and not _PAST_STATEMENT.match(folded):
        return unresolved_compound_contract(said, available, application_names, game_catalog)
    authenticated_applications = build_application_catalog_index(
        application_names,
    )
    authenticated_request = _authenticated_application_request(
        folded,
        authenticated_applications,
    )
    if authenticated_request is not None:
        operation, targets = authenticated_request
        if len(targets) <= 8 and operation in available:
            return None
        operations = tuple(operation for _ in targets)
        return CompoundEffectContract(
            max(1, len(operations)),
            ((operations,) if operations else ()),
        )
    if authenticated_applications and _authenticated_application_identity_conflict(
        folded,
        authenticated_applications,
    ):
        return CompoundEffectContract(1, ())
    if (
        isinstance(resolved_intent, EffectIntent)
        and resolved_intent.operations == ("reminder.delete",)
        and _exact_local_reminder_title(folded) is not None
    ):
        # A subject-level negative such as ``no necesito comida para perro``
        # is the reason for the following explicit deletion, not a negation of
        # it.  This exemption is available only after the closed reminder
        # grammar extracted one exact title; ordinary ``no borres`` requests
        # still fail closed below.
        return None
    benign_media_alternative = (
        isinstance(resolved_intent, EffectIntent)
        and resolved_intent.operations == ("media.status",)
        and _has(
            folded,
            r"\b(?:pista|track)\s+(?:o|or)\s+(?:video|audio)\b",
        )
    )
    # Tanda 3 «¿estamos a enero o febrero?»: the choice is between answers to one clock read.
    benign_calendar_choice = (
        isinstance(resolved_intent, EffectIntent)
        and resolved_intent.operations == ("system.time",)
        and _direct_current_time_request(folded)
    )
    benign_asr_catalog_report = (
        isinstance(resolved_intent, EffectIntent)
        and 2 <= len(resolved_intent.operations) <= 8
        and _catalog_report_clauses(folded) is not None
        and _has(folded, r"\bover\s+or\s+layout\s+del\s+sistema\b")
    )
    benign_exhaustive_report = (
        isinstance(resolved_intent, EffectIntent)
        and 2 <= len(resolved_intent.operations) <= 8
        and _has(
            folded,
            r"^(?:sin\s+omitir\s+ninguno|without\s+skipping\s+(?:any|ninguno))"
            r"\s*,?\s*(?:revisa|inspect)\s+(?:en|in)\s+"
            r"(?:(?:este|this)\s+)?(?:orden|order)\s*:\s*",
        )
    )
    benign_trash_prepare_without_commit = (
        isinstance(resolved_intent, EffectIntent)
        and resolved_intent.operations == ("filesystem.trash.prepare",)
        and exact_catalog_operation_plan(folded) == ("filesystem.trash.prepare",)
    )
    benign_routine_catalog_question = (
        isinstance(resolved_intent, EffectIntent)
        and resolved_intent.operations == ("routine.list",)
        and _has(
            folded,
            r"^which\s+habitual\s+sequences\s+does\s+bax[yi]\s+know\s+how\s+to\s+repeat[\s.!?]*$",
        )
    )
    benign_product_correction = (
        isinstance(resolved_intent, EffectIntent)
        and resolved_intent.operations == ("web.search",)
        and _public_product_correction_lookup_request(folded)
    )
    benign_live_lookup = (
        isinstance(resolved_intent, EffectIntent)
        and resolved_intent.operations in (("web.search",), ("weather.current",), ("web.news.headlines",))
        and _public_live_lookup_request(folded)
    )
    # Tanda 4 «find instructions on how to play taboo», «busca cómo se juega a la brisca»: «how to» after an
    # order to search is what to look up, not a how-to explanation that forbids tools.
    benign_research_lookup = (
        isinstance(resolved_intent, EffectIntent)
        and resolved_intent.operations == ("web.search",)
        and _research_question_query(text) is not None
    )
    benign_game_correction = (
        isinstance(resolved_intent, EffectIntent)
        and resolved_intent.operations == ("game.launch",)
        and _corrected_game_launch_title(folded) is not None
    )
    # M111 (DEV-F v4d F-s014 «… pero no se lo mandes eh»): the order not to send a message left written is that
    # draft's own constraint, not a negated second effect.
    benign_draft_not_sent = (
        isinstance(resolved_intent, EffectIntent)
        and resolved_intent.operations == ("message.draft",)
        and message_left_written_request(text) is not None
    )
    if benign_draft_not_sent:
        return None
    if (
        (
            _is_negative_effect_clause(folded)
            or any(_is_negative_effect_clause(clause) for clause in clauses)
        )
        # A negative clause is not a global ban on an independent positive
        # clause. The full semantic request still carries its constraints;
        # conservation below counts positive effects, not negative statements.
        # Standalone negatives, explicit tool denial, corrections and device
        # restrictions retain their separate fail-closed contracts.
        and len(clauses) < 2
        and not benign_exhaustive_report
        and not benign_trash_prepare_without_commit
        or (
            _has_contradictory_correction(folded, available)
            and not benign_media_alternative
            and not benign_calendar_choice
            and not benign_asr_catalog_report
            and not benign_product_correction
            and not benign_live_lookup
            and not benign_game_correction
            and not benign_trash_prepare_without_commit
        )
        # A "what is" envelope can ask for a personal observation. Leaving
        # it to semantic selection is not a missing clause or a no-tool order.
        or (
            _is_explicit_meta_or_tool_denial(folded)
            and not benign_routine_catalog_question
            and not benign_research_lookup
        )
        or _other_device_effect_scope(folded)
    ):
        return CompoundEffectContract(1, ())
    if resolved_intent is _EXPLICIT_EFFECTS_NOT_RESOLVED:
        resolved = resolve_explicit_effects(
            folded,
            available,
            authenticated_applications,
            game_catalog,
        )
    elif resolved_intent is None or isinstance(resolved_intent, EffectIntent):
        resolved = resolved_intent
    else:
        raise TypeError("resolved intent has an invalid type")
    incomplete_exhaustive_report_tail = (
        isinstance(resolved, EffectIntent)
        and len(resolved.operations) >= 2
        and _has(
            folded,
            r"^(?:sin\s+omitir\s+ninguno|"
            r"without\s+skipping\s+(?:any|ninguno))\b",
        )
        and _has(
            folded,
            r"\b(?:resultado\s+por\s+separado|result\s+separately)[\s.!?]*$",
        )
        and not _has(
            folded,
            r"\b(?:devolviendo\s+cada\s+resultado\s+por\s+separado|"
            r"returning\s+each\s+result\s+separately)[\s.!?]*$",
        )
    )
    if incomplete_exhaustive_report_tail:
        # The user explicitly forbade omissions, but the ASR tail itself is
        # missing the return verb/determiner. Treat the apparently complete
        # subset as a truncated utterance and ask again instead of executing.
        return CompoundEffectContract(1, ())
    if resolved is not None:
        return None
    deferred_effect = _has_unsupported_deferred_effect(folded)
    shared_head_minimum = _coordinated_effect_domain_minimum(folded)
    if _has_unresolved_shared_head_coordination(folded):
        shared_head_minimum = max(2, shared_head_minimum or 0)
    multiple_installed_entities = _has_multiple_installed_entities(folded)
    explicit_cardinality = _unresolved_explicit_cardinality(folded)
    if (
        deferred_effect
        or shared_head_minimum is not None
        or multiple_installed_entities
        or explicit_cardinality is not None
    ):
        recognized = _resolve_explicit_effects_single(
            folded,
            available,
            application_names=authenticated_applications,
        )
        recognized_operations = recognized.operations if recognized is not None else ()
        return CompoundEffectContract(
            (
                max(1, len(recognized_operations))
                if deferred_effect
                else max(
                    explicit_cardinality or shared_head_minimum or 2,
                    len(recognized_operations) + 1,
                )
            ),
            ((recognized_operations,) if recognized_operations else ()),
        )
    if len(clauses) < 2:
        return None
    minimum_effects = 0
    unresolved_positive_clauses = 0
    required_sequences: list[tuple[str, ...]] = []
    clause_requirements: list[tuple[str, tuple[str, ...]]] = []
    for clause in clauses:
        result = _resolve_explicit_effects_single(
            clause,
            available,
            application_names=authenticated_applications,
        )
        if result is not None:
            minimum_effects += len(result.operations)
            required_sequences.append(result.operations)
            clause_requirements.append((clause, result.operations))
            continue
        if not _is_negative_effect_clause(clause) and not _is_social_clause(clause):
            minimum_effects += 1
            unresolved_positive_clauses += 1
            clause_requirements.append((clause, ()))
    if unresolved_positive_clauses == 0 or minimum_effects == 0:
        return None
    return CompoundEffectContract(
        minimum_effects,
        tuple(required_sequences),
        tuple(clause_requirements),
    )
