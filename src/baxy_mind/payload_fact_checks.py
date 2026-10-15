"""The checks that a public text keeps the facts its payload gave, per operation family and across them
(``_payload_fact_defect``).
"""

from __future__ import annotations

import re
from typing import Iterable

from .semantic.normalize import _accent_folded_with_punctuation
from .semantic import answer_evidence as semantic_answer_evidence
from .semantic import knowledge as semantic_knowledge
from .semantic import quantities as semantic_quantities
from .semantic import windows as semantic_windows
from .effect_intent import _entity_lookup_query, curiosity_request, declined_means
from .semantic.request import fold as _reading_fold
from .window_prose_facts import window_fact_defect
from .semantic.display import monitor_facts_asked
from .clock_facts import _misses_calendar_facts, _names_clock_place
from .compose_situation import _CAUSE_FACT, _merged_observed, _RADIO_SWITCH_OPERATIONS
from .clock_checks import _clock_fact_defect
from .device_facts import (
    _capture_unmet_untold, _contradicted_brightness_extreme, _invented_windows_version, _mislabelled_installed_memory,
    _observed_levels, _ocr_unsupported_terms, _python_package_state_defect, _recognized_screen_text,
    _screen_count_defect, _snap_beyond_half_untold, _unobserved_direction, _unreceived_untold,
    _wifi_scan_networks_in_situation,
)
from .search_report import (
    _claims_declined_means, _not_found_invents_a_cause, _place_existence_denied, _places_whole_address, _QUOTED_NAME,
    _search_listing_not_from_one_ranking, _SEARCH_NOT_FOUND, _search_report_absence_claim,
    _search_report_answer_unstated, _search_report_defines_the_ask, _search_report_denies_found_places,
    _search_report_echoes_the_ask, _search_report_from_no_pertinent_result, _search_report_leaves_out_subject,
    _search_report_moves_the_subject, _search_report_names_a_page, _search_report_names_nothing,
    _search_report_names_the_person_as_finder, _search_report_off_subject, _search_report_offers_a_finder,
    _search_report_other_year, _search_report_past_as_next, _search_report_proposal_as_fact,
    _search_report_repeats_a_quote, _search_report_shows_the_search, _search_report_speaks_as_a_page,
    _search_report_stale_day, _search_report_undated_relative_day, _search_report_unsourced_claim,
    _search_report_why_title_as_fact, _search_results_of, _search_results_text, _search_unsupported_claim,
    _SEARCH_WEATHER_CLAIM, _SMALL_NUMBER_WORDS,
)
from .listing_facts import (
    _open_search_listing_defect, _page_read_in_payload, _page_read_quote_defect, _pdf_read_in_payload,
    _pdf_read_quote_defect, _tab_listing_fact_defect, _written_file_after_listing, _youtube_playback_defect,
    _youtube_playback_in_payload,
)
from .agenda_facts import (
    _alarm_offer_defect, _known_listing_in_payload, _listing_fact_defect, _record_titles, _task_listing_defect,
    _without_record_titles,
)
from .weather_facts import _weather_fact_defect
from .deterministic_finals import _quotes_what_it_was_not_given
from .consulted_answers import _recipe_has_its_form


# Person and copula shift when a stated fact is confirmed back («mi cumpleaños»
# → «tu cumpleaños»); the content words are what must survive untranslated.
_REMEMBERED_FUNCTION_WORDS = frozenset(
    "mi mis tu tus su sus me te se yo vos usted el la lo los las un una unos unas "
    "es soy eres sos son esta estan estoy de del al en y e o u que como con por "
    "para my your his her their our its i you we they am is are the a an of in on "
    "at to and or it this that".split()
)


def _remembered_content_words(value: str) -> list[str]:
    return [
        word
        for word in re.findall(r"[^\W_]+", value or "")
        if _reading_fold(word) not in _REMEMBERED_FUNCTION_WORDS
    ]


def _missing_remembered_words(text: str, value: str) -> list[str]:
    folded = _reading_fold(text or "")
    return [
        word
        for word in _remembered_content_words(value)
        if re.search(rf"(?<![^\W_]){re.escape(_reading_fold(word))}(?![^\W_])", folded) is None
    ]


def _headline_words(value: str) -> str:
    return " ".join(re.findall(r"\w+", _reading_fold(value)))


def _without_quoted_headlines(text: str, situation: dict) -> str:
    """``text`` folded, without the verified headlines it quotes, their own «¿…?» included.

    M75 (DEV-D v3l D-s032 «Noticias sobre Taylor Swift»): the feed's «La crítica se harta de Taylor Swift, pero… ¿es
    ‘Cleveland’ tan mala?» quoted with plain quotes was read as BAXY asking, and the first draft (three headlines as
    written) and the deterministic final both died on extra_claim. A headline is found by its words in order, as the
    quoting check reads it (M60); the question marks it carries go with it, a question of BAXY's own stays."""

    folded = _accent_folded_with_punctuation(text)
    if situation.get("operation") != "web.news.headlines" or not (
        situation.get("verified") is True and situation.get("succeeded") is True
    ):
        return folded
    headlines = _merged_observed(situation).get("headlines")
    for item in headlines if isinstance(headlines, list) else []:
        title = item.get("title") if isinstance(item, dict) else None
        words = re.findall(r"\w+", _accent_folded_with_punctuation(title)) if isinstance(title, str) else []
        if len(words) < 3:
            continue
        # Only the marks at the headline's own ends; one inside it goes with the words around it.
        opening = r"(?:¿\W{0,3})?" if re.match(r"\W*¿", title) else ""
        closing = r"(?:\W{0,3}\?)?" if re.search(r"\?\W*$", title) else ""
        folded = re.sub(
            opening + r"(?<!\w)" + r"\W+".join(re.escape(word) for word in words) + r"(?!\w)" + closing, " ", folded,
        )
    return folded


def _news_fact_defect(text: str, payload: dict) -> str:
    """REOPEN1993 grupo N: the reply quotes the observed headlines (at least
    three when the feed gave that many) and names no portal listing instead."""

    if payload.get("operation") != "web.news.headlines":
        return ""
    seen = payload.get("seen")
    if not isinstance(seen, dict) or not isinstance(seen.get("headlines"), list):
        return ""
    titles = [
        str(item.get("title")).strip()
        for item in seen["headlines"]
        if isinstance(item, dict) and isinstance(item.get("title"), str) and item.get("title").strip()
    ]
    if not titles:
        return ""
    # M60 (DEV-D s032 q4 «Noticias sobre Taylor Swift»): the feed's «: Taylor Swift abre su intimidad con Travis
    # Kelce» was quoted without its stray colon and did not count, so two drafts with three headlines died. A
    # headline is quoted when its words are, in order; punctuation and quotation marks are typography.
    said_words = f" {_headline_words(text)} "
    quoted = sum(1 for title in titles if (words := _headline_words(title)) and f" {words} " in said_words)
    if quoted < min(3, len(titles)):
        return "missing_state"
    return ""


def _shell_fact_defect(text: str, payload: dict) -> str:
    """REOPEN1993 comandos: a quoted output line must be one the command
    printed; a failed command is not reported as a success; a command with
    output does not get reported as silent."""

    if payload.get("operation") != "shell.command.run":
        return ""
    seen = payload.get("seen")
    if not isinstance(seen, dict) or not isinstance(seen.get("exitCode"), int):
        return ""
    lines = [str(line) for line in seen.get("lines") or [] if isinstance(line, str)]
    stderr = str(seen.get("stderr") or "")
    folded_text = _reading_fold(text)
    printed = _reading_fold("\n".join(lines) + "\n" + stderr)
    for quoted in re.findall(r"[«\"“`]([^»\"”`\n]{4,200})[»\"”`]", text):
        if _reading_fold(quoted) not in printed:
            return "invented_number" if re.search(r"\d", quoted) else "extra_claim"
    failed = seen["exitCode"] != 0
    if failed and re.search(r"\b(?:salio bien|exito|exitosa|exitosamente|correctamente|sin problemas|succeeded|successfully|worked)\b", folded_text) and not re.search(r"\b(?:no|fall|error)\b", folded_text):
        return "extra_claim"
    if not failed and lines and not any(_reading_fold(line) in folded_text for line in lines[:5]):
        return "missing_state"
    if not failed and not lines and not re.search(
        # SHELL2075 H0245 «ejecuta ls» with an empty folder: the instruction says
        # «si no hubo salida, dilo» and «No hubo salida» — the plainest way to say
        # it — was not among the accepted forms, so three faithful drafts died.
        r"\b(?:sin salida|ninguna salida|no hubo salida|no (?:imprimio|produjo|mostro|devolvio|escribio)|"
        r"nada|no output|no lines|nothing|printed nothing|empty|vacia)\b",
        folded_text,
    ):
        return "missing_state"
    return ""


def _package_fact_defect(text: str, payload: dict) -> str:
    """REOPEN1993 grupo G: the reply names the package and does not claim a
    finished install or removal while the process is still running."""

    operation = payload.get("operation")
    seen = payload.get("seen")
    if operation not in {"package.install.commit", "package.uninstall"} or not isinstance(seen, dict):
        return ""
    name = seen.get("name")
    folded_text = _reading_fold(text)
    if isinstance(name, str) and name.strip() and _reading_fold(name) not in folded_text:
        return "missing_state"
    running = seen.get("installing") is True or seen.get("uninstalling") is True
    if running and re.search(
        r"\b(?:instal(?:e|ado|ada)|desinstal(?:e|ado|ada)|quit(?:e|ado|ada)|elimin(?:e|ado|ada)|removed|installed|uninstalled)\b",
        folded_text,
    ) and not re.search(r"\b(?:sigue|todavia|aun|still|empez|comenz|started|running|corriendo|en curso|en marcha)\b", folded_text):
        return "extra_claim"
    return ""


def _wifi_place_fact_defect(text: str, payload: dict) -> str:
    """REOPEN1957 H0170/H0376: when no network is associated with the place
    yet, the reply asks which of the saved networks it is, naming them, and
    never claims a connection. A verified connect by place says so."""

    seen = payload.get("seen")
    reason = payload.get("reason")
    folded_text = _reading_fold(text)
    if isinstance(reason, dict) and reason.get("cause") == _CAUSE_FACT["wifi_place_unknown"]:
        if "?" not in text:
            return "missing_state"
        if re.search(r"(?<!\bno )(?<!\bnot )\b(?:conecte|conectado|conectada|connected|te conecte|listo)\b", folded_text):
            return "reversed_polarity"
        labels = seen.get("savedNetworks") if isinstance(seen, dict) else None
        if isinstance(labels, list) and labels and not any(_reading_fold(str(label)) in folded_text for label in labels):
            return "missing_state"
        return ""
    if payload.get("operation") == "wifi.connect.named" and isinstance(seen, dict) and seen.get("place") and seen.get("connected") is True:
        if not re.search(r"\b(?:conect|connect)", folded_text):
            return "missing_state"
    return ""


# M92 (DEV-D v3u D-w01-t2 «oye y cuánta sal le echo al agua, más o menos» → «Se le pone a gusto.», D-w01-t3 «pa 3
# litros» → three drafts computing 1,5, 30–75 and 150 over «sal por litro … es de 10 gramos»): the amount of an
# ingredient asked is answered with a figure — the one the read gives, or the one BAXY computed from a per-unit rule
# it gives (``semantic.quantities.rated_totals``) — or told not found. Folded.
_SPOKEN_FIGURE = re.compile(
    r"\d|½|¼|¾|\b(?:dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|quince|veinte|treinta|cuarenta|"
    r"cincuenta|cien|ciento|mil|medio|media|two|three|four|five|six|seven|eight|nine|ten|twelve|twenty|hundred|half|"
    r"(?:un|una|a|an|one)\s+(?:taza|tazas|cucharada|cucharadas|cucharadita|cucharaditas|pizca|puñado|punado|gramo|"
    r"kilo|litro|cup|tablespoon|teaspoon|pinch|handful|gram|liter|litre))\b"
)


def _ingredient_amount_asked(payload: dict, user_text: str) -> bool:
    """M92: the request, or the query the search sent for it (which carries the ingredient the conversation named),
    asks how much of an ingredient (``semantic.knowledge.kitchen_quantity``), and the pages read state quantities
    («700 gramos de harina», «10 g por litro»): an answer-shaped figure may be there."""

    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    return any(
        semantic_knowledge.kitchen_quantity(asked) is not None
        for asked in (user_text, str(seen.get("query") or "")) if asked
    ) and bool(semantic_quantities.measures(_search_results_text(payload) or ""))


def _amount_report_defect(text: str, payload: dict, user_text: str, results_text: str) -> str:
    """M92: a report of a search for how much of an ingredient that answers with no figure, or without the figure BAXY
    computed from a per-unit rule the read gives; a not-found is always a report."""

    if not _ingredient_amount_asked(payload, user_text):
        return ""
    answering = [
        part for part in re.split(r"(?<=[.!?;])\s+", str(text or "").strip())
        if part.strip() and _SEARCH_NOT_FOUND.match(_reading_fold(part)) is None
    ]
    if not answering:
        return ""
    rated = semantic_quantities.rated_totals(user_text, results_text)
    if rated and not semantic_quantities.gives_a_total(" ".join(answering), rated):
        return "rule_calculation_not_given"
    if not rated and _SPOKEN_FIGURE.search(_reading_fold(" ".join(answering))) is None:
        return "amount_without_figure"
    return ""


# M93 (DEV-D v3u D-s062 «Go al homescreen» → window.minimize.all failed → «…porque el intento de cerrar todas las
# ventanas falló…»): the act a report names is the operation's own. Minimizing, maximizing, restoring, closing and
# opening are different acts; a report of one that names another, and never its own, tells something that was not
# tried. Folded words.
_OPERATION_ACTS = {
    "minimize": r"\bminimi[zs]\w*|\bminimiz\w*",
    "maximize": r"\bmaximi[zs]\w*|\bmaximiz\w*",
    "restore": r"\brestaur\w*|\brestor\w*",
    "close": r"\bcerr\w*|\bcierr\w*|\bclos(?:e|ed|ing|es)\b",
    "open": r"\babr(?:ir|e|i|o|io|ieron|irla|irlo|irse|iendo)\b|\babiert[oa]s?\b|\bopen(?:ed|ing|s)?\b",
}


# M93 (DEV-D v3u D-w18-t4 «remind me en 45 minutes to take a break» → «Te he recordado para que tomes un descanso a las
# 20:23.»): a notification just scheduled rings later; saying BAXY already reminded, or that it already rang, tells a
# thing that has not happened. Folded.
_SCHEDULED_TOLD_AS_RUNG = re.compile(
    r"\b(?:ya\s+)?te\s+(?:he|habia)\s+(?:recordado|avisado|notificado|despertado)\b|"
    r"\bte\s+(?:recorde|avise|notifique|desperte)\b|\b(?:ya\s+)?(?:sono|ha\s+sonado)\b|"
    r"\bi(?:'ve|\s+have)\s+(?:already\s+)?(?:reminded|notified|alerted)\s+you\b|"
    r"\bi\s+(?:already\s+)?(?:reminded|notified|alerted)\s+you\b|"
    r"\b(?:it|the\s+(?:alarm|reminder|timer))\s+(?:already\s+)?(?:rang|went\s+off)\b"
)


def _schedule_told_as_rung(text: str, payload: dict) -> bool:
    """A verified alarm or reminder still to ring, reported as if it had already rung."""

    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    return (
        payload.get("operation") in {"notification.schedule", "reminder.create"}
        and bool(seen)
        and not payload.get("cause")
        and _SCHEDULED_TOLD_AS_RUNG.search(_reading_fold(text)) is not None
    )


# M99 (DEV-D v3x D-w18-t4 «Recuerda en 45 minutos que te toca tomar un descanso a las 23:56.»): the report of a reminder
# just scheduled opened on an order to the person to remember, where BAXY is the one who reminds. Folded.
_SCHEDULE_TOLD_AS_ORDER = re.compile(
    r"^[¡\s]*(?:recuerda|recorda|acuerdate|no\s+(?:te\s+)?olvides|remember|don'?t\s+forget|do\s+not\s+forget)\b"
)


def _schedule_told_as_order(text: str, payload: dict) -> bool:
    """A verified alarm or reminder still to ring, reported as an order to the person to remember (see above)."""

    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    return (
        payload.get("operation") in {"notification.schedule", "reminder.create"}
        and bool(seen)
        and not payload.get("cause")
        and _SCHEDULE_TOLD_AS_ORDER.search(_reading_fold(text)) is not None
    )


# M135 (DEV-F v4i/v4k/v4m F-w47-t2, the same draft three rounds: a WhatsApp draft left unverified → «Se borró el
# borrador para mi contacto…»): a report that says something was deleted, when the operation deletes nothing, tells a
# thing that did not happen. Affirmative deletions only (a «no se borró nada» is no claim). Folded words.
_CLAIMED_DELETION = re.compile(
    r"(?<!\bno\s)(?<!\bnot\s)\b(?:se\s+(?:ha\s+|han\s+)?(?:borro|borraron|elimino|eliminaron)|"
    r"(?:he|hemos|ha|han)\s+(?:borrado|eliminado)|borre|elimine|"
    r"(?:was|were|been|has|have)\s+(?:deleted|erased)|i\s+(?:deleted|erased))\b"
)
_DELETING_OPERATION = re.compile(r"trash|delete|remove|cancel|clear|uninstall|purge|empty|reset")


def _report_claims_a_deletion(text: str, payload: dict) -> bool:
    """M135: the report of one operation that deletes nothing says that something was deleted (see above)."""

    reason = payload.get("reason") if isinstance(payload.get("reason"), dict) else {}
    operation = str(payload.get("operation") or reason.get("operation") or "")
    if not operation or _DELETING_OPERATION.search(operation) or payload.get("completedStepsInOrder"):
        return False
    return _CLAIMED_DELETION.search(_reading_fold(text)) is not None


def _report_changes_the_act(text: str, payload: dict) -> str:
    """The other act a report of a window or application operation names instead of its own; ""."""

    reason = payload.get("reason") if isinstance(payload.get("reason"), dict) else {}
    operation = str(payload.get("operation") or reason.get("operation") or "")
    if not operation.startswith(("window.", "app.")):
        return ""
    own = [act for act in _OPERATION_ACTS if act in operation.split(".")]
    if len(own) != 1:
        return ""
    folded = _reading_fold(text)
    if re.search(_OPERATION_ACTS[own[0]], folded):
        return ""
    return next((act for act, pattern in _OPERATION_ACTS.items() if act != own[0] and re.search(pattern, folded)), "")


# M95 (DEV-D v3x D-w15-t4 «y guardame eso en una nota que se llame reunion jueves» → «He guardado la nota «reunion
# jueves» con el resumen del informe trimestral de Documentos.»): the note holds the words «resumen del informe
# trimestral de Documentos», no summary. A note whose written text names a kind of text (a summary, a translation, a
# list… of something) rather than being it is reported with that text quoted as written, never as if it held the thing.
_DESCRIBED_CONTENT = re.compile(
    r"^(?:(?:el|la|los|las|un|una|the|a|an)\s+)?(?P<kind>resumen|traduccion|transcripcion|contenido|texto|lista|"
    r"informe|summary|translation|transcript|contents?|text|list|report)\s+(?:de|del|of)\b"
)
_NOTE_WRITE_OPERATIONS = frozenset({"note.create", "note.append", "note.update"})


def _note_content_described(text: str, payload: dict) -> bool:
    """M95: the report of a note written with a description for content tells that description, unquoted, as what the
    note holds (see above). Saying the note was saved, or quoting its text, is right."""

    seen = payload.get("seen") if isinstance(payload, dict) else None
    if payload.get("operation") not in _NOTE_WRITE_OPERATIONS or not isinstance(seen, dict):
        return False
    content = _reading_fold(str(seen.get("content") or "").strip())
    described = _DESCRIBED_CONTENT.search(content)
    if described is None:
        return False
    quotes = r"[«\"“]([^»\"”]{1,400})[»\"”]"
    if any(_reading_fold(item).strip(" .") == content.strip(" .") for item in re.findall(quotes, str(text or ""))):
        return False
    unquoted = _reading_fold(re.sub(quotes, " ", str(text or "")))
    return re.search(rf"\b{described.group('kind')}\b", unquoted) is not None


def _search_report_recipe_not_read(text: str, payload: dict, user_text: str) -> bool:
    """M102 (DEV-D v3z D-s017 «a good southern style mac n cheese recipe» → «Southern-style mac and cheese uses a
    creamy no-cook sauce with cheddar…», D-w10-t1 «¿me regalas una receta sencilla de arepas de queso?» → the
    encyclopedia's sentence about the arepa): a named dish's recipe asked for, and no page read that is one (no recipe
    reference, no page with its ingredients listed and its steps numbered). D52: a recipe is its quantities and steps;
    what was read is not it, so the report says the recipe was not found."""

    if payload.get("operation") != "web.search" or _search_results_text(payload) is None:
        return False
    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    if seen.get("reference") is not None or not semantic_knowledge.asks_one_recipe(user_text or ""):
        return False
    if any(_recipe_has_its_form(str(item.get("snippet") or "")) for item in _search_results_of(payload)
           if isinstance(item, dict)):
        return False
    return any(
        _SEARCH_NOT_FOUND.match(_reading_fold(sentence)) is None
        for sentence in re.split(r"(?<=[.!?])\s+", str(text).strip())
        if sentence.strip()
    )


def _payload_fact_defect(text: str, payload: dict, user_text: str = "", *, said: str | None = None) -> str:
    """El texto público conserva los hechos que el payload le dio.

    Sin esto, «el volumen es el número correspondiente» pasaba con `level` en
    los hechos, y «Tengo lo que necesito para ayudarte» pasaba como respuesta de
    capacidades con `can` delante. Se comprueba contra el payload de este turno,
    no contra una lista de frases esperadas.
    """

    if not isinstance(payload, dict) or not payload:
        return ""
    window_defect = window_fact_defect(text, payload, user_text)
    if window_defect:
        return window_defect
    if _report_changes_the_act(text, payload):
        return "report_changes_the_act"
    if _report_claims_a_deletion(text, payload):
        return "report_claims_a_deletion"
    if _schedule_told_as_rung(text, payload):
        return "schedule_told_as_rung"
    if _schedule_told_as_order(text, payload):
        return "schedule_told_as_order"
    if _search_report_speaks_as_a_page(text, payload, user_text):
        return "search_report_page_voice"
    if payload.get("operation") == "web.search" and _search_report_names_the_person_as_finder(text):
        # Tanda 8 «¿a qué hora se fue el sol ayer?» → «No lo encontraste.»: BAXY searched, not the person.
        return "search_report_wrong_finder"
    if _search_report_shows_the_search(text, payload, user_text):
        # Owner rule 2026-09-24: the lookup is invisible (see _search_report_shows_the_search).
        return "search_report_shows_the_search"
    if _search_report_repeats_a_quote(text, payload):
        return "search_report_repeats_a_quote"
    if _not_found_invents_a_cause(text, payload):
        return "search_not_found_invents_a_cause"
    if _place_existence_denied(text, payload):
        # M77 (DEV-D v3l D-s087): not recognised is not nonexistent.
        return "place_existence_denied"
    results_text = _search_results_text(payload)
    if results_text and semantic_quantities.underived_price(text, user_text or "", results_text):
        # M62 (v3e2-final F-w13-t2): the money a report gives for the asked quantity is the unit price read or the
        # total computed from it (payload «calculation»), never another figure of the page (a full tank's price).
        return "underived_price"
    if results_text:
        amount_defect = _amount_report_defect(text, payload, user_text or "", results_text)
        if amount_defect:
            return amount_defect
    if _search_report_answer_unstated(text, payload, user_text):
        # Estabilización TZ-VETO (z1 t2-c01 t4): judged before the unsourced words. «…al menos un disco de estudio…»
        # died on «menos» alone, the hint asked to drop that word and keep the rest, and the retry published «Un disco
        # de estudio: Vida de perros.»; the answer no result states is named first, and its hint asks for the
        # not-found.
        return "search_report_answer_unstated"
    if _search_report_unsourced_claim(text, payload, user_text):
        # WEB1879 H0060: a sentence of the report summarised causes in its own
        # voice; no result contains them. Reinstated in WEB1889: the turn no
        # longer dies when every candidate falls, so the rule has a way out.
        return "search_report_unsourced_claim"
    if _search_results_text(payload) is not None and semantic_answer_evidence.denied_and_affirmed(
        text, _search_results_text(payload) or "", _SEARCH_NOT_FOUND
    ):
        # Ronda 24 (r23 t4-c02 t3 «No hay película de Bestiario…, pero sí existe una llamada Bestiario de 2002.»);
        # revisión 1 (bloqueante 2): a not-found clause denies nothing.
        return "search_report_denies_and_affirms"
    if _search_listing_not_from_one_ranking(text, payload, user_text):
        return "search_listing_not_one_ranking"
    if _search_report_names_a_page(text, payload, user_text):
        return "search_report_names_a_page"
    if _search_report_offers_a_finder(text, payload, user_text):
        return "search_report_page_voice"
    if (
        _search_results_text(payload) is not None
        and _entity_lookup_query(user_text or "") is None
        and not curiosity_request(user_text or "")
        and re.search(r"https?://", str(text)) is not None
    ):
        # H0463: «DOOM Eternal: idStudio - SteamDB https://steamdb.info/app/…»
        # is a pasted listing, not a report a companion would say; pages are
        # named by title and site. The safety-net report has that shape.
        return "search_report_pasted_urls"
    task_defect = _task_listing_defect(text, payload) or _alarm_offer_defect(text, payload, user_text)
    if task_defect:
        return task_defect
    if _note_content_described(text, payload):
        return "note_content_described"
    if _search_report_recipe_not_read(text, payload, user_text):
        return "search_report_recipe_not_read"
    folded = _reading_fold(text)
    seen = payload.get("seen")
    # A wifi reading observes the WLAN connection, not internet reachability.
    # «The PC is offline» / «no está en línea» were appended to connected=false
    # (NETWORK1161/010-011, 1163/005, 1165/004) while network.status read
    # online=true. Only a reading that carries `online` may speak about it.
    if (
        # The visible payload of a verified success carries only the
        # operation and its observed facts («seen»); failures carry a cause
        # (NETWORK1299: compose-audit payload_keys ['operation', 'seen']).
        isinstance(payload.get("operation"), str)
        and isinstance(seen, dict)
        and seen
        and not payload.get("cause")
        and not payload.get("error")
        and (_ACTION_ATTRIBUTED_TO_USER.search(text) is not None or tells_own_act_as_the_persons(text))
    ):
        # NETWORK1295/1297 «Apagame el bluetooth.» → «Ya apagaste el
        # bluetooth»: the assistant did it, not the person. This is the
        # predicate that gates acceptance (blocked → payload defect), not
        # only the audit label in rejection_reason.
        return "action_attributed_to_user"
    if (
        isinstance(payload.get("operation"), str)
        and not payload.get("cause")
        and not payload.get("error")
        and names_an_unseen_known_folder(text, seen)
    ):
        return "extra_claim"
    if (
        user_text
        and declined_means(user_text) is not None
        and not payload.get("error")
        and _claims_declined_means(text)
    ):
        # SYSTEM1545 H0076: the person named Python; the reading was direct.
        # A report that says it used or ran a language, a script or a terminal
        # claims a capability the assistant does not have.
        return "claimed_means"
    if _snap_beyond_half_untold(text, payload):
        # M159 (DEV-I v4w I-s048): the window is on the asked side but its own minimum is wider than the half.
        return "snap_beyond_half_untold"
    if (
        payload.get("operation") == "system.status"
        and isinstance(seen, dict)
        and isinstance(seen.get("os"), dict)
        and _invented_windows_version(text, seen["os"])
    ):
        # SYSTEM1305 H0508: «Windows 11 versión 22H2» — no feature-update name
        # or version number is observed beyond major/minor/build.
        return "invented_version"
    if (
        payload.get("operation") == "system.status"
        and isinstance(seen, dict)
        and isinstance(seen.get("memory"), dict)
        and _mislabelled_installed_memory(text, seen["memory"])
    ):
        # SYSTEM1183/1303 H0508: «16,54 GB de RAM instalados» labels the observed
        # total (16,54 GB) as installed when installed_capacity is 17,18 GB.
        return "mislabelled_installed"
    if (
        isinstance(payload.get("operation"), str)
        and payload["operation"].startswith("system.settings.")
        and isinstance(seen, dict)
        and _contradicted_brightness_extreme(text, seen)
    ):
        return _contradicted_brightness_extreme(text, seen)
    if _unobserved_direction(text, _observed_levels(payload)):
        return "unobserved_direction"
    prior_steps = payload.get("completedStepsInOrder")
    written = _written_file_after_listing(payload)
    if written is not None and _reading_fold(written).casefold() not in folded:
        # FILES1707 H0334: the listing was read and the file was written, and
        # the final only listed the processes. The file is the request.
        return "missing_written_file"
    if (
        payload.get("outcome") == "failed"
        and isinstance(prior_steps, list)
        and any(
            isinstance(step, dict)
            and step.get("operation") in semantic_windows.WINDOW_PLACEMENT_OPERATIONS
            and isinstance(step.get("resultAtThisStep"), dict)
            and step["resultAtThisStep"].get("readOnly") is False
            for step in prior_steps
        )
        and not semantic_windows.tells_a_window_placement(text)
    ):
        # Tanda t4-r6 c19 «ponme el navegador y el word uno al lado del otro»: Opera was snapped, Word's step failed,
        # and the final said only that it could not place them. What was already done is told before what failed.
        return "missing_prior_placement"
    if (
        payload.get("operation") == "input.visible.click"
        and isinstance(seen, dict)
        and seen.get("ok") is True
        and re.search(
            r"\b(?:apret\w*|puls\w*|presion\w*|toc\w*|clic|click\w*|clique\w*|"
            r"press\w*|tap\w*|hit|"
            # UI1731 «navegá hasta la biblioteca»: a verified click on a section
            # label is faithfully told as going there.
            r"naveg\w*|navigat\w*|fui|entr[eé]|went|entered|abri\s+la\s+seccion)\b",
            folded,
        )
        is None
    ):
        # UI1275 H0555 «en la calculadora apretá el 5» → «Apagué el 5»: the
        # verified click was narrated with a wrong verb. Say the button was
        # pressed; the label stays whatever the person said.
        return "missing_click_verb"
    if (
        payload.get("operation") == "input.visible.click"
        and isinstance(seen, dict)
        and (seen.get("ok") is True or seen.get("clicked") is True)
        and re.search(
            r"\b(?:deshabilitad\w*|desactivad\w*|inhabilitad\w*|disabled|not\s+clickable|no\s+(?:era|estaba|es|esta)\s+(?:clicable|clickeable|pulsable)|"
            r"no\s+se\s+(?:pudo|pudieron)|couldn'?t|could\s+not|no\s+pude|no\s+encontr\w*|ausente|absent|was\s+not\s+(?:found|present))\b",
            folded,
        )
        is not None
    ):
        # UI1635: a verified click narrated as a failure because the control
        # was gone afterwards (its dialog closed).
        return "reversed_result"
    if (
        payload.get("operation") in ("capture.screenshot", "capture.active.window")
        and isinstance(seen, dict)
        and (seen.get("storedPrivately") is True or isinstance(seen.get("savedIn"), str))
        and re.match(
            r"^[¡!¿?\s]*(?:sac[aá]|sacame|tom[aá]|tomame|captur[aá]|hac[eé]|take|capture|grab)\b",
            text.strip().casefold(),
        )
        is not None
    ):
        # SCREEN1399 H0093 «sacá un screenshot» → «Sacá un screenshot del área virtual.»: the verified capture was
        # echoed as an order. Estabilización R5: only the echo; the list of past forms vetoed every «He tomado/He
        # capturado la captura…» (t2-c16, 5 slower, 0 right). Accents kept: «Capturé» is no «capture».
        return "capture_not_reported"
    if (
        payload.get("operation") in ("capture.screenshot", "capture.active.window")
        and isinstance(seen, dict)
        and isinstance(seen.get("fileName"), str)
        and _reading_fold(seen["fileName"]) not in folded
    ):
        # Ronda 22 (uso real r18 t4-c09 «saca una captura de pantalla y guardala» → «…la guardé de forma privada en este
        # dispositivo»): a capture saved where the person asked is told with where it is, or they cannot find it.
        return "capture_place_untold"
    if _unreceived_untold(text, payload):
        # Revisión 2 de r22 (bloqueante 3, «toma una captura y mándala a mi jefe» → «Hice la captura de pantalla.»):
        # a part of the request the operation could not receive is said as not done, never lost in silence.
        return "unreceived_part_untold"
    if _capture_unmet_untold(text, payload):
        # Revisión r22 (bloqueante 1, «toma una captura y guárdala en mi pendrive» → «…la guardé de forma privada»): a
        # place asked that the capture could not take is said as not done, never lost in silence.
        return "capture_unmet_untold"
    recognized = _recognized_screen_text(payload)
    if isinstance(recognized, str) and recognized.strip():
        # SCREEN1409 «leéme lo que dice la pantalla»: the finals summarized a
        # «Fable limit warning», generated scripts and an execution flow that
        # the recognized text never contained. Every content word of the
        # report must come from that text (or the request); framing words
        # about reading a screen are the only allowance.
        if _ocr_unsupported_terms(text, recognized, user_text):
            return "ocr_unsupported_terms"
        count_defect = _screen_count_defect(text, payload, user_text)
        if count_defect:
            return count_defect
    listing = _known_listing_in_payload(payload)
    if listing is not None:
        # FILES1425: the person asked what the folder holds; a name that is not
        # in the listing or a count that is not the observed one is invented.
        listing_defect = _listing_fact_defect(text, listing)
        if listing_defect:
            return listing_defect
    pdf = _pdf_read_in_payload(payload)
    if pdf is not None:
        # PDF1689: a passage the document did not carry, or a number it did
        # not carry, is invented; the report quotes the document as read.
        pdf_defect = _pdf_read_quote_defect(text, pdf)
        if pdf_defect:
            return pdf_defect
    page = _page_read_in_payload(payload)
    if page is not None:
        # WEB1539: a passage the page did not show, or a number it did not
        # carry, is invented; the report quotes the page as read.
        page_defect = _page_read_quote_defect(text, page)
        if not page_defect and isinstance(payload.get("openSearch"), dict):
            # Review r10a finding 3: the search already open, read for a «top N»: every item listed is read.
            page_defect = _open_search_listing_defect(text, page, payload["openSearch"])
        if page_defect:
            return page_defect
    playing = _youtube_playback_in_payload(payload)
    if playing is not None:
        # MUSIC1553: the only title the report may quote is the observed one.
        playback_defect = _youtube_playback_defect(text, playing)
        if playback_defect:
            return playback_defect
        if not re.sub(r'[«"“][^»"”]{1,512}[»"”]', "", text).strip(" .,;:!¡\n\t"):
            # MUSIC1573 «poneme una canción» → «algo de jazz»: the retry wrote
            # the English title alone and the language veto answered, so the
            # next hint dropped the title. The title alone lacks the state.
            return "missing_state"
    results_text = _search_results_text(payload)
    if payload.get("operation") == "web.search" and results_text is None:
        # WEB1445/002 «va a llover mañana» over a search that returned nothing
        # relevant: «Sí, va a llover mañana. Pero no pude confirmarlo…» asserts
        # a forecast no result gave. A failed search supports no weather claim.
        if _SEARCH_WEATHER_CLAIM.search(_reading_fold(text)) is not None:
            return "search_unsupported_claim"
    if results_text is not None:
        # WEB1445 «qué clima hace hoy»: the results were forecast index pages and
        # the finals invented «buen tiempo, temperaturas agradables, poco viento»
        # or denied having any information. A weather claim must be quoted from
        # a result. WEB1447 showed that grounding every content word rejected
        # honest prose («existen», «diferentes», «específica»), so the words are
        # free and only the claims and the denials are checked.
        if _search_unsupported_claim(text, results_text) is not None:
            return "search_unsupported_claim"
        if re.search(
            # Owner rule 2026-09-24: when no page states it, «No lo encontré» / «I couldn't find it» is the answer;
            # what stays denied is having no information at all while the pages were read.
            r"\bno\s+(?:tengo|dispongo\s+de|hay|pude\s+obtener)\b.{0,40}"
            r"\b(?:informacion|datos|resultados|clima|pronostico|tiempo)\b"
            r"|\b(?:i\s+)?(?:don't|do\s+not)\s+have\b|\b(?:i\s+)?(?:couldn't|could\s+not)\s+get\b",
            _reading_fold(text),
        ):
            return "search_result_denied"
        if _search_report_denies_found_places(text, payload, user_text):
            # M54: an OpenStreetMap place list is the answer, so neither «no lo encontré» nor «no hay» fits it.
            return "search_places_denied"
        if _search_report_absence_claim(text, payload, user_text):
            return "search_report_absence_claim"
        if _search_report_off_subject(text, payload, user_text) or _search_report_from_no_pertinent_result(
            text, payload, user_text
        ):
            # Owner method 2026-09-25 (no inventing): a search that did not answer is said as not found.
            return "search_report_off_subject"
        if _search_report_proposal_as_fact(text, payload, user_text):
            return "search_report_proposal_as_fact"
        if _search_report_other_year(text, payload, user_text):
            # M77 (DEV-D v3l D-w14-t1): this year's question is not answered with another year's result.
            return "search_report_other_year"
        if _search_report_past_as_next(text, payload, user_text):
            # M83 (DEV-D v3o D-w08-t2): a day already gone is not the next one.
            return "search_report_past_as_next"
        if _search_report_stale_day(text, payload) is not None:
            # M77 (DEV-D v3l D-p05-t2): a dated headline's «mañana» is its own day's.
            return "search_report_stale_day"
        if _search_report_undated_relative_day(text, payload):
            # M93 (DEV-D v3u D-s027): an undated page's «mañana» is no known day.
            return "search_report_undated_day"
        if _search_report_defines_the_ask(text, payload, user_text):
            # M77 (DEV-D v3l D-p19-t3, D-p23-t2, D-w17-t5): the word asked with is not what was asked.
            return "search_report_defines_the_ask"
    if _search_report_why_title_as_fact(text, payload):
        # M77 (DEV-D v3l D-s021): «Por qué X» does not state X.
        return "search_report_why_title_as_fact"
    if _search_report_moves_the_subject(text, payload):
        # M93 (DEV-D v3u D-s021): «Campeón del mundo con Alemania critica…» is not «Alemania criticó…».
        return "search_report_moves_the_subject"
    if results_text is not None:
        if _places_whole_address(text, payload, user_text):
            return "places_whole_address"
        if _search_report_echoes_the_ask(text, payload, user_text):
            # M93 (DEV-D v3u D-w06-t4): «Las pizzerías abiertas están cerca de Curico.» says only what was asked.
            return "search_report_echoes_the_ask"
        if _search_report_names_nothing(text, payload, user_text):
            # M70 (held-out v3h t14): «Nadie lo dijo.» over five pages about the critics. After the specific defects,
            # whose hints say better what to change.
            return "search_report_names_nothing"
        if _search_report_leaves_out_subject(text, payload, user_text, said):
            # M71 (held-out v3j t14): the subject the conversation carried is named, whatever the report says of it.
            return "search_report_leaves_out_subject"
    written = seen.get("writtenText") if isinstance(seen, dict) else None
    if payload.get("operation") == "clipboard.write.text" and isinstance(written, str) and written:
        # CLIPBOARD1359: «Hola» / «Buen día.» were published after a verified
        # write. The final must carry the written text and say it was copied.
        if _reading_fold(written) not in folded:
            return "missing_written_text"
        if re.search(
            r"\b(?:copi\w*|pegu\w*|portapapeles|clipboard|pasted?|paste)\b",
            folded,
        ) is None:
            return "echo_without_report"
    typed = seen.get("typedText") if isinstance(seen, dict) else None
    if payload.get("operation") == "input.text.type" and isinstance(typed, str) and typed:
        # THEN2003: «Hola mundo» alone was published after a verified typing.
        if _reading_fold(typed) not in folded:
            return "missing_typed_text"
        if re.search(
            r"\b(?:escrib\w*|tecle\w*|tipe\w*|puse|coloqu\w*|typed?|wrote|written|entered|put)\b",
            folded,
        ) is None:
            return "typed_echo_without_report"
    if (
        payload.get("operation") == "window.close.all"
        and isinstance(seen, dict)
        and isinstance(seen.get("closed"), int)
    ):
        # CLOSEALL1733: every number in the reply is an observed count; a
        # remaining window must be told, never hidden; nothing was forced.
        allowed_counts = {str(seen.get(key)) for key in ("closed", "remainingVisible", "keptOpen", "desktopWindows") if isinstance(seen.get(key), int)}
        for number in re.findall(r"(?<![\w.,])\d+(?![\w.,%])", text):
            if number not in allowed_counts:
                return "invented_number"
        remaining = seen.get("remainingVisible")
        if isinstance(remaining, int) and remaining > 0:
            # A window that stayed open must be reported with its count; «cerré
            # todas» over a remaining window hides it.
            number_words = {1: ("una", "uno", "one"), 2: ("dos", "two"), 3: ("tres", "three"), 4: ("cuatro", "four"), 5: ("cinco", "five")}
            spoken = number_words.get(remaining, ())
            if str(remaining) not in text and not any(re.search(rf"\b{word}\b", _reading_fold(text)) for word in spoken):
                return "missing_state"
            if re.search(r"\b(?:todas|todo|all|every|everything)\b", _reading_fold(text)) and not re.search(
                r"\b(?:menos|salvo|except|pero|but|aunque|although)\b", _reading_fold(text)
            ):
                return "extra_claim"
        if seen.get("closed") == 0 and re.search(r"\b(?:cerr[eé]|closed|cerrad[ao]s)\b", _reading_fold(text)) and not re.search(
            r"\b(?:ninguna|ningun|nada|no habia|no hay|no window|nothing|none|no had)\b", _reading_fold(text)
        ):
            # Nothing was closed: a final that reports a closing invents it.
            return "reversed_result"
        if re.search(r"\b(?:forc|mat[eé]|kill|termin[eé])\w*", _reading_fold(text)):
            return "extra_claim"
    scanned = seen if (payload.get("operation") == "wifi.scan" and isinstance(seen, dict) and isinstance(seen.get("networks"), list)) else _wifi_scan_networks_in_situation(payload)
    if isinstance(scanned, dict) and isinstance(scanned.get("networks"), list):
        # NETWORK1729: every quoted network name is an observed SSID and the
        # count is the observed one; nothing was connected. NETWORK1737: the
        # same over the mission «radio on, then scan».
        seen = scanned
        observed_names = {str(entry.get("ssid")).strip().casefold() for entry in seen["networks"] if isinstance(entry, dict) and isinstance(entry.get("ssid"), str)}
        for quoted in re.findall(_QUOTED_NAME, text):
            if quoted.strip().casefold() not in observed_names:
                return "invented"
        count = seen.get("networkCount")
        if isinstance(count, int) and not isinstance(count, bool):
            # Observed names may carry digits («Vecino 24»); only the free
            # numbers of the prose are judged, and signal percentages are
            # observed data.
            prose = text
            for entry in seen["networks"]:
                if isinstance(entry, dict) and isinstance(entry.get("ssid"), str) and entry["ssid"].strip():
                    prose = prose.replace(entry["ssid"].strip(), " ")
            prose = re.sub(r"\d+\s*(?:%|por\s*ciento|percent)", " ", prose)
            for number in re.findall(r"(?<![\w.,])\d+(?![\w.,%])", prose):
                if int(number) != count and int(number) != 0:
                    return "invented_number"
            if count == 0 and not re.search(r"\b(?:ninguna|no \w+ ninguna|none|no networks|no wi-?fi)\b", _reading_fold(text)):
                return "missing_state"
        if re.search(r"\b(?:conect[eé]|me conect[eé]|connected to|joined)\b", _reading_fold(text)):
            return "extra_claim"
    if (
        payload.get("operation") == "calculator.expression.evaluate"
        and isinstance(seen, dict)
        and isinstance(seen.get("value"), str)
    ):
        # UI1725: every number in the reply is an operand of the typed
        # expression or the value the Calculator showed; the value must appear.
        allowed_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", str(seen.get("expression") or "")))
        shown_value = str(seen["value"]).strip()
        allowed_numbers.add(shown_value)
        allowed_numbers.add(shown_value.replace(",", "."))
        allowed_numbers.add(shown_value.replace(".", ","))
        for number in re.findall(r"\d+(?:[.,]\d+)?", text):
            if number not in allowed_numbers:
                return "invented_number"
        if shown_value and shown_value not in text and shown_value.replace(".", ",") not in text and shown_value.replace(",", ".") not in text:
            return "missing_state"
    weather_defect = _weather_fact_defect(text, payload, user_text)
    if weather_defect:
        return weather_defect
    news_defect = _news_fact_defect(text, payload)
    if news_defect:
        return news_defect
    package_defect = _package_fact_defect(text, payload)
    if package_defect:
        return package_defect
    shell_defect = _shell_fact_defect(text, payload)
    if shell_defect:
        return shell_defect
    wifi_place_defect = _wifi_place_fact_defect(text, payload)
    if wifi_place_defect:
        return wifi_place_defect
    tab_defect = _tab_listing_fact_defect(text, payload)
    if tab_defect:
        return tab_defect
    if payload.get("operation") == "filesystem.explorer.count" and isinstance(seen, dict) and type(seen.get("count")) is int:
        # REOPEN1957 H0701: the figure and the folder's name are the facts; any
        # other number is invented.
        folded_count = _reading_fold(text)
        allowed = {str(seen["count"])} | ({str(seen["filesInFolder"])} if type(seen.get("filesInFolder")) is int else set())
        numbers = re.findall(r"(?<![\w.,])\d+(?![\w.,])", text)
        if any(number not in allowed for number in numbers):
            return "invented_number"
        if str(seen["count"]) not in numbers and not (seen["count"] <= 10 and re.search(
            r"\b(?:cero|ning[uú]n[oa]?|zero|none|no hay|uno?|una|one|dos|two|tres|three|cuatro|four|cinco|five|seis|six|siete|seven|ocho|eight|nueve|nine|diez|ten)\b", folded_count,
        )):
            return "missing_state"
        folder_name = seen.get("folderName")
        if isinstance(folder_name, str) and folder_name.strip() and _reading_fold(folder_name) not in folded_count:
            return "missing_state"
    if (
        payload.get("operation") == "document.presentation.create"
        and isinstance(seen, dict)
        and isinstance(seen.get("slideCount"), int)
    ):
        # REOPEN1957 H0188: the file and the slide count are the facts.
        if isinstance(seen.get("name"), str) and _reading_fold(seen["name"]) not in folded and _reading_fold(seen["name"]).removesuffix(".pptx") not in folded:
            return "missing_state"
        for number in re.findall(r"(?<![\w.,])\d+(?![\w.,])", text):
            if number != str(seen["slideCount"]):
                return "invented_number"
        if str(seen["slideCount"]) not in text and not re.search(r"\b(?:seis|six|cinco|five|cuatro|four|tres|three|dos|two|siete|seven|ocho|eight|diez|ten)\b", folded):
            return "missing_state"
    if payload.get("operation") in {"file.compress", "file.open", "desktop.wallpaper.set", "web.download"} and isinstance(seen, dict):
        # REOPEN1957 H0542/H0459/H0077: the reply names what the postread saw.
        named = [str(seen.get(key)) for key in ("zipName", "name", "color") if isinstance(seen.get(key), str) and seen.get(key)]
        if named and not any(_reading_fold(value) in folded for value in named):
            return "missing_state"
        observed_numbers = {str(seen.get(key)) for key in ("entryCount", "bytes") if isinstance(seen.get(key), int)}
        for number in re.findall(r"(?<![\w.,])\d{2,}(?![\w.,])", text):
            if number not in observed_numbers:
                return "invented_number"
    if (
        payload.get("operation") in {"system.settings.set", "system.settings.status"}
        and isinstance(seen, dict)
        and seen.get("setting") == "airplane_mode"
        and isinstance(seen.get("airplaneMode"), bool)
    ):
        # REOPEN1957 H0107: the reply states the observed airplane-mode state.
        on = seen["airplaneMode"]
        says_on = re.search(r"\b(?:activad|encendid|prendid|puest|on\b|activ[eo]\b)", folded) is not None and not re.search(r"\b(?:no|desactiv|apagad|off)\b", folded)
        says_off = re.search(r"\b(?:desactivad|apagad|quitad|off\b|desactiv[eo]\b)", folded) is not None
        if not re.search(r"modo avion|airplane mode|flight mode", folded):
            return "missing_state"
        if (on and says_off and not says_on) or (not on and says_on and not says_off):
            return "extra_claim"
    if (
        payload.get("operation") == "system.power"
        and isinstance(seen, dict)
        and isinstance(seen.get("delaySeconds"), int)
    ):
        # REOPEN1993 grupo P: the announced delay is the fact; a past-tense
        # «se apagó»/«se reinició» claims what has not happened yet.
        if str(seen["delaySeconds"]) not in text:
            return "missing_state"
        if re.search(r"\b(?:se\s+(?:apago|reinicio)|ya\s+(?:esta|se)\s+(?:apagad|reiniciad)|was\s+(?:shut\s+down|restarted)|has\s+(?:shut\s+down|restarted))\b", _reading_fold(text)):
            return "extra_claim"
    if (
        payload.get("operation") == "storage.removable.list"
        and isinstance(seen, dict)
        and isinstance(seen.get("drives"), list)
    ):
        # USB1823: with no removable drive, a drive named or a copy claimed is
        # invented; numbers must be the observed sizes or count.
        folded_text = _reading_fold(text)
        if not seen["drives"]:
            if re.search(r"\b(?:copi[eé]|copiad[oa]s?|respald[eé]|hice (?:el|un|la) (?:backup|respaldo|copia)|backed up|copied|saved)\b", folded_text) and not re.search(r"\bno (?:se )?copi|\bnothing (?:was )?copied|\bnot (?:been )?copied|\bno (?:se )?respald|\bno hice\b", folded_text):
                return "extra_claim"
            if re.search(r"\b(?:unidad|drive|disco|pendrive|usb)\s+[a-z]:", folded_text):
                return "extra_claim"
        observed_numbers = {str(seen.get("driveCount"))}
        for drive in seen["drives"]:
            if isinstance(drive, dict):
                for key in ("freeGiB", "totalGiB"):
                    if isinstance(drive.get(key), (int, float)):
                        value = drive[key]
                        observed_numbers.update({str(value), str(value).replace(".", ","), str(int(value)) if float(value).is_integer() else str(value)})
        prose = re.sub(r"[«\"“][^»\"”]{1,4096}[»\"”]", " ", text)
        for number in re.findall(r"(?<![\w.,:-])\d+(?:[.,]\d+)?(?![\w.,:-])", prose):
            if number not in observed_numbers:
                return "invented_number"
    if (
        payload.get("operation") == "software.python.package.status"
        and isinstance(seen, dict)
        and (isinstance(seen.get("pythons"), list) or isinstance(seen.get("installedIn"), list))
    ):
        # PIP1817: every version-like number must be a registered Python version
        # or the observed package version; PIP1819: the state said is the observed one.
        state_defect = _python_package_state_defect(text, seen)
        if state_defect:
            return state_defect
        observed_versions: set[str] = set()
        for entry in seen.get("pythons") or []:
            if isinstance(entry, dict):
                for key in ("pythonVersion", "packageVersion", "tag"):
                    if isinstance(entry.get(key), str):
                        observed_versions.add(entry[key].strip())
        for key in ("installedIn", "notInstalledIn", "noPipIn"):
            for label in seen.get(key) or []:
                observed_versions.update(re.findall(r"\d+(?:\.\d+)+", str(label)))
        for number in re.findall(r"(?<![\w.])\d+(?:\.\d+)+(?![\w.])", text):
            if not any(version == number or version.startswith(number + ".") for version in observed_versions):
                return "invented_number"
    if (
        payload.get("operation") == "software.python.status"
        and isinstance(seen, dict)
        and isinstance(seen.get("pythons"), list)
    ):
        # SYSTEM1697: every version-like number in the reply must be a
        # registered one; the count of installs must not be invented.
        observed_versions = {
            str(entry.get("pythonVersion")).strip()
            for entry in seen["pythons"]
            if isinstance(entry, dict) and isinstance(entry.get("pythonVersion"), str)
        }
        observed_versions |= {str(entry.get("tag")).strip() for entry in seen["pythons"] if isinstance(entry, dict) and isinstance(entry.get("tag"), str)}
        for number in re.findall(r"(?<![\w.])\d+(?:\.\d+)+(?![\w.])", text):
            if not any(version == number or version.startswith(number + ".") for version in observed_versions):
                return "invented_number"
        count = seen.get("pythonCount")
        if count == 0 and not re.search(r"\b(?:no|ningun|ninguna|none|not|isn't|is not)\b", _reading_fold(text)):
            return "missing_state"
        if isinstance(count, int) and count > 0 and not any(version in text for version in observed_versions):
            return "missing_state"
    if (
        payload.get("operation") == "display.status"
        and isinstance(seen, dict)
        and isinstance(seen.get("monitors"), list)
    ):
        # SYSTEM1459: every number in the reply must be an observed one
        # (width, height, refresh rate, count), and the asked number must appear.
        observed_numbers: set[str] = set()
        for monitor in seen["monitors"]:
            if isinstance(monitor, dict):
                for key in ("width", "height", "refreshHz"):
                    if isinstance(monitor.get(key), int):
                        observed_numbers.add(str(monitor[key]))
        count = seen.get("monitorCount")
        if isinstance(count, int):
            observed_numbers.add(str(count))
        numbers_in_text = re.findall(r"(?<![\d.,])\d{2,}(?![\d.,])", text)
        if any(number not in observed_numbers for number in numbers_in_text):
            return "invented_number"
        asks = monitor_facts_asked(user_text)
        if "resolution" in asks and not all(
            any(str(monitor.get(key)) in text for monitor in seen["monitors"] if isinstance(monitor, dict))
            for key in ("width", "height")
        ):
            return "missing_state"
        if "refresh" in asks and not any(
            str(monitor.get("refreshHz")) in text for monitor in seen["monitors"] if isinstance(monitor, dict)
        ):
            return "missing_state"
        if "count" in asks and isinstance(count, int):
            words = {1: r"\b(?:un|uno|una|one|solo\s+un|1)\b", 2: r"\b(?:dos|two|2)\b", 3: r"\b(?:tres|three|3)\b", 4: r"\b(?:cuatro|four|4)\b"}
            if not re.search(words.get(count, rf"\b{count}\b"), folded):
                return "missing_state"
    if (
        payload.get("operation") in _RADIO_SWITCH_OPERATIONS
        and isinstance(seen, dict)
        and seen.get("alreadyInState") is True
    ):
        # v3 r6 lectores (t2-r4 c15 «turn bluetooth on» with it already on): nothing was switched. «Lo encendí» or
        # «I turned it on» claims a change that did not happen; a reply without «ya»/«already» hides why nothing did.
        # «Bluetooth was already turned on», «is already switched on», «was already active» state what was there;
        # only the act («I turned it on», «lo activé») claims a switch.
        stated = re.sub(
            r"\b(?:already|still|was|is|were|are|been|be|stays?|remains?)\s+(?:already\s+|still\s+)?(?:been\s+)?"
            r"(?:turned|switched|active)\b",
            " ",
            folded,
        )
        if re.search(r"\b(?:encendi|apague|active|desactive|prendi|lo\s+puse|la\s+puse|turned|switched)\b", stated):
            return "extra_claim"
        if not re.search(r"\b(?:ya|already|still|sigue|seguia)\b", folded):
            return "missing_state"
    if (
        payload.get("operation") == "bluetooth.radio.status"
        and isinstance(seen, dict)
        and isinstance(seen.get("radioOn"), bool)
    ):
        # NETWORK1457: the read is one boolean; the reply must carry it and
        # must not claim a change («lo encendí»).
        on_words = r"\b(?:encendid[oa]|prendid[oa]|activad[oa]|activ[oa]|on)\b"
        off_words = r"\b(?:apagad[oa]|desactivad[oa]|inactiv[oa]|off)\b"
        # «no está encendido», «no tienes el bluetooth encendido»: up to three
        # words may separate the negation from the state word.
        negated = r"\bno\s+(?:\w+\s+){0,3}?"
        negated_on = re.search(negated + on_words, folded) is not None
        negated_off = re.search(negated + off_words, folded) is not None
        # «no está encendido» states the off state; «no está apagado» the on state.
        says_on = (re.search(on_words, folded) is not None and not negated_on) or negated_off
        says_off = (re.search(off_words, folded) is not None and not negated_off) or negated_on
        if seen["radioOn"] is True and (says_off and not says_on):
            return "reversed_state"
        if seen["radioOn"] is False and (says_on and not says_off):
            return "reversed_state"
        if not says_on and not says_off:
            return "missing_state"
        if re.search(r"\b(?:encendi|apague|active|desactive|prendi|lo\s+puse|turned|switched)\b", folded):
            return "extra_claim"
    if (
        payload.get("operation") in {"wifi.radio.set", "wifi.radio.status"}
        and isinstance(seen, dict)
        and isinstance(seen.get("wifiRadioOn"), bool)
    ):
        # NETWORK1737 «apagá el wifi»: the post-read state is the fact. The
        # reply must carry it with the right polarity, and «Ya apagó el wifi»
        # (third person) is not the assistant speaking.
        on_words = r"\b(?:encendid[oa]|prendid[oa]|activad[oa]|encendi|prendi|active|encendio|prendio|activo|on|enabled|turned\s+on|switched\s+on)\b"
        off_words = r"\b(?:apagad[oa]|desactivad[oa]|apague|desactive|apago|desactivo|off|disabled|turned\s+off|switched\s+off)\b"
        negated = r"\bno\s+(?:\w+\s+){0,3}?"
        says_on = re.search(on_words, folded) is not None and re.search(negated + on_words, folded) is None
        says_off = re.search(off_words, folded) is not None and re.search(negated + off_words, folded) is None
        if seen["wifiRadioOn"] is True and says_off and not says_on:
            return "reversed_result"
        if seen["wifiRadioOn"] is False and says_on and not says_off:
            return "reversed_result"
        if not says_on and not says_off:
            return "missing_state"
        if re.search(r"\b(?:apago|encendio|prendio|activo|desactivo|ha\s+(?:apagado|encendido)|he\s+has|she\s+has|it\s+turned)\b", folded) and not re.search(
            r"\b(?:quedo|esta|queda|is|is\s+now)\b[^.;]{0,20}\b(?:apagad|encendid|prendid|activad|desactivad|on|off)", folded
        ):
            return "third_person"
    if (
        payload.get("operation") == "wifi.status"
        and isinstance(seen, dict)
        and "connected" in seen
        and "online" not in seen
        and re.search(
            # NETWORK1293 H0302: «el PC no está conectado a ninguna red» claims
            # the whole network from a wifi-only read (Ethernet was online);
            # «ninguna red wifi» keeps the wifi scope and is the read itself.
            r"\b(?:offline|online|en linea|internet|any network|no network|"
            r"(?:ninguna red|sin red|no tiene red|no hay red)"
            r"(?!\s+(?:wifi|wi-fi|wi fi|wlan|inalambrica)\b))\b",
            folded,
        )
        is not None
    ):
        return "invented_connectivity"
    # NETWORK1297: a «missing_scan_limit» defect here («qué redes wifi hay» must
    # say it cannot scan) exhausted every retry into no_response: the other
    # composer vetoes leave no room for that sentence. The scan limit stays a
    # documented condition of wifi.status, not a composer rule.
    # A verified account read must survive composition. UI264 returned the
    # assistant's identity while omitting the actual Windows userName. Match
    # the observed value, including accents, without accepting a longer name.
    account = seen.get("userName") if isinstance(seen, dict) else None
    if isinstance(account, str) and account.strip() and not re.search(
        r"(?<!\w)" + re.escape(account.casefold()) + r"(?!\w)", text.casefold()
    ):
        return "missing_name"
    if isinstance(seen, dict) and "level" in seen:
        level = str(seen["level"]).strip()
        # Tanda 6c «el volumen es cero»: a small level said as its word is the level.
        if level and not re.search(rf"(?<!\d){re.escape(level)}(?!\d)", folded) and not any(
            re.search(rf"\b{word}\b", folded) for word in _SMALL_NUMBER_WORDS.get(level, ())
        ):
            return "missing_name"
    # MEMORY1251: «red» was confirmed as «rojo» and «my favorite drink is tea»
    # as «mi favorito es el té». What the memory keeps is quoted, not translated.
    remembered = seen.get("remembered") if isinstance(seen, dict) else None
    if isinstance(remembered, str) and _missing_remembered_words(text, remembered):
        return "missing_remembered"
    clock = payload.get("clock")
    if isinstance(clock, str) and clock:
        allowed: list[tuple[int, int]] = []
        given = payload.get("given")
        if isinstance(given, str) and re.fullmatch(r"\d\d:\d\d", given):
            # A converted time is said next to the time it converts.
            allowed.append((int(given[:2]), int(given[3:])))
        place = payload.get("place")
        if isinstance(place, str) and place.strip() and not _names_clock_place(text, place):
            return "missing_state"
        countdown = payload.get("countdown")
        if isinstance(countdown, dict):
            try:
                target_hour, target_minute = (int(part) for part in str(countdown.get("target")).split(":", 1))
                allowed.append((target_hour, target_minute))
                allowed.append((int(countdown.get("remaining_hours", 0)), int(countdown.get("remaining_minutes", 0))))
            except (TypeError, ValueError):
                pass
        # CLOCK1329 H0399: «Faltan 14 horas y 7 minutos para las 3 de la tarde»
        # answers the countdown without restating the clock; the observed time
        # is optional there and only a contrary clock claim is a defect.
        clock_defect = _clock_fact_defect(
            text, clock, required=not isinstance(countdown, dict), allowed=tuple(allowed),
        )
        if clock_defect:
            return clock_defect
    if any(isinstance(payload.get(key), (str, list)) and payload[key] for key in ("date", "weekday", "month", "year", "asked_days")) and (
        _misses_calendar_facts(text, payload)
    ):
        return "missing_name"
    seen = payload.get("seen")
    if isinstance(seen, dict) and seen and "effect" not in payload:
        # El turno leyó un estado; no lo cambió. Uso real 2026-09-23: «el cambio
        # del peso chileno», «bajo la lluvia», «el silencio» son sustantivos o
        # preposiciones de lo leído, no «yo cambio»; sólo el verbo en primera
        # persona afirma un efecto (y cayeron todas las búsquedas de divisas).
        # M153: a record's title quoted back («hago la cena», «bajo eléctrico») is the person's words, not BAXY's.
        told = _reading_fold(_without_record_titles(text, _record_titles(payload.get("operation"), seen)))
        if (
            re.search(
                r"(?<!\bel )(?<!\bdel )(?<!\bal )(?<!\bun )(?<!\bsu )(?<!\btu )(?<!\bmi )(?<!\bde )"
                r"(?<!\ben )(?<!\bpor )(?<!\bsin )(?<!\bmas )(?<!\bmuy )(?<!\besta )(?<!\bestan )(?<!\bes )"
                r"\b(?:hago|pongo|ajusto|subo|bajo|silencio|cambio|configuro)\b"
                r"(?!\s+(?:de|del)\b)"
                # M58 (v3d-final F-s066 «¿hará bueno para San Juan?»): «28.5 °C bajo un cielo despejado», «lloverá
                # bajo 29 °C» are «under», not «I lower»; three right drafts died and the reply lost tomorrow's rain.
                r"(?<!\bbajo(?=\s+(?:un|una|el|la|los|las)\s+(?:cielo|sol|lluvia|nubes?|nublado|niebla|viento|"
                r"calor|frio|techo|agua|nieve|temperatura)s?\b))"
                r"(?<!\bbajo(?=\s+(?:cero|\d)))"
                # M153 (DEV-G v4s G-w01-t3 «dejame una alarma mañana a las 7 que tengo turno temprano» → «He programado
                # la alarma para mañana a las 07:00 bajo el título "Turno temprano".», refused): «bajo el título» (or
                # «el nombre», «la etiqueta») is what the record is called, not «I lower».
                r"(?<!\bbajo(?=\s+(?:el|la)\s+(?:titulo|nombre|etiqueta)\b))"
                r"|\bi (?:set|turn|adjust|change|raise|lower|mute)\b",
                told,
            )
            is not None
        ):
            return "reversed_result"
    served = payload.get("can")
    if isinstance(served, list) and served:
        vocabulary = {
            word
            for phrase in served
            for word in re.findall(r"[a-z]{4,}", _reading_fold(str(phrase)))
        }
        if vocabulary and not (vocabulary & set(re.findall(r"[a-z]{4,}", folded))):
            return "missing_name"
    if _quotes_what_it_was_not_given(text, payload, user_text, said):
        return "unsourced_quote"
    return ""


# A completed effect reported as the person's own act («Ya apagaste el
# bluetooth», NETWORK1295): second-person preterites of the effect verbs.
_ACTION_ATTRIBUTED_TO_USER = re.compile(
    r"\b(?:apagaste|encendiste|prendiste|activaste|desactivaste|abriste|cerraste|"
    r"pusiste|subiste|bajaste|mandaste|enviaste|borraste|guardaste|silenciaste|"
    r"you (?:turned|opened|closed|set|sent|saved|muted))\b",
    re.IGNORECASE,
)

# Live 2026-10-07 (cu-universal v2, y5 «… andá a Descargas y después a Imágenes» → «Has abierto correctamente la
# carpeta Imágenes dentro de Descargas.»; x12 «Has iniciado la aplicación de la calculadora…»): the compound perfect
# and any second-person preterite tell BAXY's verified act as the person's. A word in -aste/-iste that is no act of
# doing (a noun, «existe», the person's own asking or saying: «la carpeta que pediste») is no such claim.
_SECOND_PERSON_PERFECT = re.compile(
    r"\b(?:has|habeis)\s+(?:ya\s+)?(?P<verb>[a-z]+(?:ado|ada|ido|ida)|abierto|puesto|hecho|escrito|vuelto|roto|"
    r"cubierto|descubierto|resuelto|devuelto|impreso)\b"
)
_SECOND_PERSON_PRETERITE = re.compile(r"\b(?P<verb>[a-z]{2,}(?:aste|iste))\b")
_ENGLISH_SECOND_PERSON_ACT = re.compile(
    r"\byou(?:'ve|\s+have)?\s+(?:just\s+|already\s+|successfully\s+|now\s+)?(?P<verb>[a-z]+ed|made|set|put|sent|shut|"
    r"ran|began|took|built|did)\b"
)
_NOT_AN_OWN_ACT = frozenset({
    # what the person does by asking or saying
    "pediste", "pedido", "dijiste", "dicho", "mencionaste", "mencionado", "preguntaste", "preguntado", "quisiste",
    "querido", "indicaste", "indicado", "solicitaste", "solicitado", "nombraste", "nombrado", "elegiste", "elegido",
    "especificaste", "especificado", "comentaste", "comentado", "contaste", "contado", "aclaraste", "aclarado",
    "ordenaste", "ordenado", "viste", "visto", "oiste", "escuchaste", "escuchado", "deseaste", "preferiste",
    "llamaste",
    # the person's own progress, which a listing of their tasks tells
    "completaste", "completado", "terminaste", "terminado", "cumpliste", "cumplido", "acabaste", "acabado",
    "completed", "finished",
    "asked", "requested", "wanted", "mentioned", "named", "wished", "needed", "liked", "preferred", "specified",
    "indicated", "said", "ordered", "described", "chose", "picked", "selected", "called", "meant",
    # words that only end like a second-person preterite
    "existe", "consiste", "insiste", "resiste", "asiste", "desiste", "persiste", "subsiste", "coexiste", "triste",
    "chiste", "quiste", "alpiste", "despiste", "contraste", "desgaste", "engaste", "traste", "taste", "waste",
    "paste", "haste", "caste",
})


def tells_own_act_as_the_persons(text: object) -> bool:
    """A sentence of a verified report tells BAXY's act in the second person («Has abierto…», «Ya apagaste…», «You
    opened…»). A question («¿Has abierto…?») asks the person and is no report; see the note above."""

    for part in re.findall(r"[^.!?;:\n]+[.!?;:\n]*", str(text or "").replace("’", "'")):
        sentence = _reading_fold(part).strip()
        if not sentence or "?" in part or "¿" in part:
            continue
        for pattern in (_SECOND_PERSON_PERFECT, _SECOND_PERSON_PRETERITE, _ENGLISH_SECOND_PERSON_ACT):
            for found in pattern.finditer(sentence):
                verb = found.group("verb")
                if verb in _NOT_AN_OWN_ACT or (pattern is _ENGLISH_SECOND_PERSON_ACT and verb.endswith("eed")):
                    continue
                if _NEGATED_BEFORE.search(sentence[: found.start()]) is not None:
                    # «Aún no has completado ninguna»: what the person has not done is no claim of an act.
                    continue
                return True
    return False


_NEGATED_BEFORE = re.compile(r"\b(?:no|nunca|jamas|not|never)\s+(?:(?:lo|la|los|las|le|les|me|te|se)\s+)?$")


# A known folder named in a report that names one (live 2026-10-07, y5: Downloads opened, the final placed the folder
# «Imágenes» inside it because the person had said it). The folder the facts name is the only one the report may say.
_KNOWN_FOLDER_FORMS: dict[str, tuple[str, ...]] = {
    "desktop": ("desktop", "escritorio"),
    "downloads": ("downloads", "descargas"),
    "documents": ("documents", "documentos"),
    "pictures": ("pictures", "imagenes"),
    "music": ("music", "musica"),
    "videos": ("videos",),
}


def _strings_of(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings_of(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings_of(item)


def names_an_unseen_known_folder(text: object, seen: object) -> bool:
    """The report names a known folder (Imágenes, Downloads…) the observed facts do not hold, while those facts name
    another one: the place the operation acted on is the one it observed, whatever the person asked for. Only facts
    with a ``folder`` (a known-folder operation) are weighed."""

    if not isinstance(seen, dict) or not isinstance(seen.get("folder"), str):
        return False
    observed = " ".join(_reading_fold(item) for item in _strings_of(seen))

    def named(forms: tuple[str, ...], where: str) -> bool:
        return any(re.search(rf"\b{form}\b", where) is not None for form in forms)
    if not any(named(forms, observed) for forms in _KNOWN_FOLDER_FORMS.values()):
        return False
    said = _reading_fold(str(text or ""))
    return any(named(forms, said) and not named(forms, observed) for forms in _KNOWN_FOLDER_FORMS.values())
