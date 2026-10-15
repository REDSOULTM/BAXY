"""The shape of a conversation reply: lists asked by count, the content shape asked, whole sentences, and
the bounded presentation text.
"""

from __future__ import annotations

import json
import re

from .semantic.normalize import _policy_guard_text
from .semantic import listing as semantic_listing
from .semantic.grammar import spoken_number_request
from .semantic.web import news_watch_subject
from .effect_intent import (
    _strip_request_envelope, first_person_preference, visual_content_noun, explicit_non_action_body,
)
from .semantic.request import fold as _reading_fold, read_request
from .semantic.conversation import (
    _conversation_presentation_shape, _roleplay_participant_names, assistant_desire_thing, content_shape_asked,
    sarcasm_question, spelling_word, versus_contenders,
)
from .dialogue_history import _normalized_dialogue_text
from .capability_families import _capability_phrases, CAPABILITY_SAMPLE, served_capability_families
from .reply_budget import _CONTENT_SHAPES


_SPELLED_RUNS = tuple(
    re.compile(rf"(?<![^\W\d_])[^\W\d_](?![^\W\d_])(?:{separator}[^\W\d_](?![^\W\d_]))+")
    for separator in (r"\s*[-–—,·.;:/]\s*", r"\s+")
)


def _spells_the_word(value: object, word: str) -> bool:
    """The reply says the word's letters one by one, in order and nothing more in that run (accents aside)."""

    letters = "".join(character for character in _reading_fold(word) if character.isalpha())
    folded = _reading_fold(str(value or ""))
    return bool(letters) and any(
        "".join(character for character in run if character.isalpha()) == letters
        for pattern in _SPELLED_RUNS
        for run in pattern.findall(folded)
    )


def _figures(number: int | None, language: str) -> str:
    """A whole number in figures, grouped by thousands from five digits on (100.223, 100,223; 2026 stays 2026)."""

    if number is None:
        return ""
    if number < 10_000:
        return str(number)
    grouped = f"{number:,}"
    return grouped if language == "en" else grouped.replace(",", ".")


def _numbers_in_figures(value: object) -> set[int]:
    """Every whole number a reply writes in figures, with or without thousands separators («100.223», «100223»)."""

    grouped = r"(?<![\d.,])\d{1,3}(?:[.,\s]\d{3})+(?!\d)|\d+"
    return {
        int(re.sub(r"\D", "", found))
        for found in re.findall(grouped, str(value or ""))
    }


def _follows_written_content(prior_user_requests: tuple[str, ...], last_assistant: str) -> bool:
    """The last turn wrote content: the person asked a draft (a content or role-play shape) or BAXY's last answer is a
    list of items (semantic.listing.items_listed)."""

    if semantic_listing.items_listed(last_assistant) is not None:
        return True
    if not prior_user_requests:
        return False
    return _conversation_presentation_shape(
        prior_user_requests[-1], conversation_kind="knowledge", has_history=len(prior_user_requests) > 1,
    ) in _CONTENT_SHAPES


def _closed_list_instruction(enumeration: semantic_listing.Enumeration, response_language: str | None) -> str:
    """Uso real v3 tanda 2 «dame 4 paises de sudamerica que no tengan salida al mar» → «Bolivia, Paraguay, Perú y
    Ecuador»: only two exist, and the count asked was filled with two that have a coast. A list of a closed class (not
    an open one such as ideas or recipes, semantic.listing.Enumeration.open) is told with what really meets it."""

    count = enumeration.count
    # Ronda 19 (r17 t3-c03 «dame 5 juegos…» → four; t3-c17 «dame 4 causas…» → «el nacionalismo» and «el nacionalismo
    # eslavo»): every counted list, open or closed, is exactly that many distinct items; the count is a ceiling of what
    # exists, never a goal to fill.
    if enumeration.open:
        if response_language == "en":
            return (
                f"The person asks for {count} items: give exactly {count}, each a different one (none repeated, none "
                "the same as another under a new name), as a numbered list."
            )
        return (
            f"La persona pide {count} elementos: da exactamente {count}, cada uno distinto (ninguno repetido ni que sea "
            "otro con distinto nombre), como lista numerada."
        )
    if response_language == "en":
        return (
            f"The person asks for {count} items: {count} is a ceiling, not a goal. Name only items that really meet "
            f"every condition asked; check each one before naming it. If fewer than {count} exist, say how many there "
            f"really are and name only those: never fill the count with others. If {count} or more exist, give "
            f"exactly {count}, each a different one, as a numbered list."
        )
    return (
        f"La persona pide {count} elementos: {count} es un tope, no una meta. Nombra sólo los que de verdad cumplen "
        f"todas las condiciones pedidas; comprueba cada uno antes de nombrarlo. Si existen menos de {count}, di cuántos "
        f"hay de verdad y nombra sólo esos: nunca completes la cuenta con otros. Si existen {count} o más, da "
        f"exactamente {count}, cada uno distinto, como lista numerada."
    )


def _enumeration_count_defect(reply: str, enumeration: semantic_listing.Enumeration | None) -> bool:
    """Ronda 19: a draft that lists other than the count asked (r17 t3-c03 four games for five), or one item twice. A
    draft that lists fewer and says how many there are («Solo hay dos: Bolivia y Paraguay» for four) is the honest
    answer of a closed class; a draft that lists nothing is not judged here."""

    if enumeration is None:
        return False
    items = semantic_listing.listed_items(reply)
    if len(items) < 2:
        return False
    if semantic_listing.repeated_items(items):
        return True
    # Review 2 r19: a list in sections («Online: 1. 2. 3.», «En la misma PC: 1. 2.») is read whole too; a draft is
    # written again only when no reading of it has the count asked.
    if enumeration.count in semantic_listing.counts_listed(reply):
        return False
    # Review 3 r19 (2026-10-09): «Solo hay 2: Bolivia y Paraguay. Los que tienen mar son Chile, Perú y Ecuador.» for
    # four: a closed class answered with fewer, and how many there are said, is the honest answer whatever else it names.
    return not (
        len(items) < enumeration.count
        and not enumeration.open
        and any(said < enumeration.count for said in semantic_listing.counts_said(reply))
    )


def _figure_cut_left_the_list_short(
    draft: str, kept: str, enumeration: semantic_listing.Enumeration | None,
) -> bool:
    """Ronda 24 (r23 t3-c17 t1 «dame 4 causas de la primera guerra mundial» → three): the draft listed the count asked
    and taking its figures from memory out (``_without_memory_figures``) left fewer; that shorter list is BAXY's cut,
    not the model's honest count, so it is not published. Revisión 1: a draft that already listed fewer («1. Bolivia
2.
    Paraguay» for four landlocked countries) is judged by ``_enumeration_count_defect`` alone, as it always was."""

    if enumeration is None:
        return False
    return len(semantic_listing.listed_items(kept)) < enumeration.count <= len(semantic_listing.listed_items(draft))


def _figure_cut_repeated_items(draft: str, kept: str) -> bool:
    """Revisión 2 de la ronda 24: taking the figures out left an item said twice that the draft said once («El Mundial
    de 1954 … de 1974» → «El Mundial … El Mundial»); such a list is not published (the reply is written again)."""

    return bool(semantic_listing.repeated_items(semantic_listing.listed_items(kept))) and not (
        semantic_listing.repeated_items(semantic_listing.listed_items(draft))
    )


def _enumeration_retry_instruction(
    reply: str, enumeration: semantic_listing.Enumeration, response_language: str | None,
) -> str:
    """What the writer is told when its draft listed other than the count asked (``_enumeration_count_defect``)."""

    items = semantic_listing.listed_items(reply)
    repeated = semantic_listing.repeated_items(items)
    count = enumeration.count
    if response_language == "en":
        said = f"Your draft listed {len(items)} items" + (
            f" and said {', '.join(repeated)} twice" if repeated else ""
        )
        return (
            f"{said}; the person asked for {count}. Write the answer again with exactly {count} different items as a "
            "numbered list" + ("." if enumeration.open else f"; if fewer than {count} exist, say how many and name "
                               "only those.")
        )
    said = f"Tu borrador nombró {len(items)} elementos" + (
        f" y repitió {', '.join(repeated)}" if repeated else ""
    )
    return (
        f"{said}; la persona pidió {count}. Escribe de nuevo la respuesta con exactamente {count} elementos distintos "
        "como lista numerada" + ("." if enumeration.open else f"; si existen menos de {count}, di cuántos hay y "
                                 "nombra sólo esos.")
    )


def _complete_sentences(text: str) -> str:
    """The reply up to its last finished sentence: a decode stopped by its
    budget never publishes half a sentence (the words kept are the model's)."""

    ends = list(re.finditer(r"[.!?…](?:[»\"'”)\]*_]*)(?=\s|$)", text))
    return text[: ends[-1].end()].strip() if ends else ""


def _shaped_presentation_text(
    text: str, shape: str | None, *, response_language: str | None = None,
    served_operations: tuple[str, ...] = (),
) -> str:
    """Give a closed prose formatter only bounded literal anchors, not a task."""

    if shape == "free_content":
        language = response_language or read_request(text).language
        return json.dumps({"response_language": language, "request": text}, ensure_ascii=False)
    if shape == "spelling":
        language = response_language or read_request(text).language
        return json.dumps({"response_language": language, "word": spelling_word(text) or ""}, ensure_ascii=False)
    if shape == "spoken_number":
        language = response_language or read_request(text).language
        return json.dumps(
            {"response_language": language, "said": text.strip(), "number": _figures(spoken_number_request(text), language)},
            ensure_ascii=False,
        )
    if shape == "versus_opinion":
        language = response_language or read_request(text).language
        first, second = versus_contenders(text) or ("", "")
        return json.dumps(
            {"response_language": language, "first": first, "second": second},
            ensure_ascii=False,
        )
    if shape == "sarcastic_answer":
        language = response_language or read_request(text).language
        return json.dumps(
            {"response_language": language, "question": sarcasm_question(text) or text},
            ensure_ascii=False,
        )
    if shape == "assistant_desire":
        language = response_language or read_request(text).language
        return json.dumps(
            {"response_language": language, "thing": assistant_desire_thing(text) or ""},
            ensure_ascii=False,
        )
    if shape == "news_watch_limit":
        language = response_language or read_request(text).language
        return json.dumps(
            {"response_language": language, "subject": news_watch_subject(text)},
            ensure_ascii=False,
        )
    if shape == "misnamed_greeting":
        reading = read_request(text)
        language = response_language or reading.language
        return json.dumps(
            {
                "response_language": language,
                "name_used": (reading.ask or "").strip(" .!"),
                "name": "BAXY",
            },
            ensure_ascii=False,
        )
    if shape == "reassurance_ack":
        language = response_language or read_request(text).language
        return json.dumps(
            {"response_language": language, "user_statement": text},
            ensure_ascii=False,
        )
    if shape == "preference_ack":
        language = response_language or read_request(text).language
        return json.dumps(
            {
                "response_language": language,
                "preference": text.strip(),
                "thing": first_person_preference(text) or "",
            },
            ensure_ascii=False,
        )
    if shape == "visual_content_boundary":
        language = response_language or read_request(text).language
        return json.dumps(
            {"response_language": language, "requested": visual_content_noun(text) or "imagen"},
            ensure_ascii=False,
        )
    if shape == "identity":
        language = response_language or read_request(text).language
        return json.dumps(
            {
                "response_language": language,
                "asked": text.strip(),
                "name": "BAXY",
                "runs_on": "this PC" if language == "en" else "este PC",
            },
            ensure_ascii=False,
        )
    if shape == "how_it_works":
        language = response_language or read_request(text).language
        families = served_capability_families(list(served_operations))
        return json.dumps(
            {
                "response_language": language,
                "runs_on": "this PC" if language == "en" else "este PC",
                "can": _capability_phrases(families, language)[:CAPABILITY_SAMPLE],
            },
            ensure_ascii=False,
        )
    if shape == "constraint_ack":
        return json.dumps(
            {
                "response_language": response_language or read_request(text).language,
                "user_constraint": text,
            },
            ensure_ascii=False,
        )
    if shape == "roleplay_draft":
        return json.dumps(
            {
                "draft_kind": "fictional_dialogue",
                "participant_names": list(_roleplay_participant_names(text)),
                "external_send": False,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    if shape in {"content_draft", "translation"}:
        current = explicit_non_action_body(text) or str(text)
        current = _strip_request_envelope(current.strip()).strip()
        return current or str(text)
    if shape not in {"missing_context", "underspecified_comparison"}:
        return text
    numbered_list = re.search(r"(?m)^\s*\d+[.)]", text) is not None
    anchors = tuple(
        dict.fromkeys(
            token
            for token in _policy_guard_text(text).split()
            if (len(token) >= 3 or token.isdigit())
            and token not in _UNSUPPORTED_ANCHOR_STOPWORDS
            and not (numbered_list and token.isdigit())
        )
    )[:8]
    if shape == "missing_context":
        return json.dumps(
            {
                "reference_present": False,
                "literal_anchors": list(anchors),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    return json.dumps(
        {
            "alternatives_named": False,
            "literal_anchors": list(anchors),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


_PREFERENCE_FUNCTION_WORDS = frozenset({
    "tomar", "comer", "beber", "jugar", "leer", "escuchar", "mirar", "hacer", "para", "como", "cuando",
    "mucho", "mucha", "muchos", "muchas", "bastante", "todo", "toda", "todos", "todas", "siempre",
    "drinking", "eating", "playing", "reading", "watching", "listening", "very", "much", "really", "with",
})


# Content written for the person — a joke, a story, a draft, a translation — is not BAXY's report of
# what happened: «Ayer compré un reloj…» in a joke, «Ya envié el informe» in a draft claim nothing.
_WRITTEN_CONTENT_SHAPES = frozenset({"free_content", "content_draft", "roleplay_draft", "translation", "spelling"})


def _content_shape_instruction(request: object, language: str | None) -> str:
    """M85 (DEV-D v3o D-p32-t2, D-p36-t2): the shape the person asked the content in, said to the writer, or ""."""

    english = language == "en"
    shape = content_shape_asked(str(request or ""))
    if shape == "dialogue":
        return (
            "Write only the new lines of the dialogue before, each one with the name of who speaks followed by a "
            "colon, as in that dialogue; keep what the work is really like."
            if english
            else "Escribe sólo las líneas nuevas del diálogo anterior, cada una con el nombre de quien habla seguido "
            "de dos puntos, como en ese diálogo; respeta cómo es de verdad la obra."
        )
    if shape == "table":
        return (
            "Write it as a table: one row per line, its columns separated by « | »."
            if english
            else "Escríbelo como tabla: una fila por línea, con sus columnas separadas por « | »."
        )
    if shape == "list":
        return (
            "Write it as a list: one item per line, each starting with «- »."
            if english
            else "Escríbelo como lista: un elemento por línea, cada uno empezando por «- »."
        )
    return ""


# The reply's own lines (wording, not the person's): a speaker's label, a list item.
_SPEAKER_LINE = re.compile(r"^\s*[^\W\d_][\w .'’-]{0,40}:\s*\S")
_LIST_LINE = re.compile(r"^\s*(?:[-•*·–]|\d{1,2}[.)])\s*\S")


def _misses_content_shape(value: object, request: object) -> bool:
    """A list asked written as one line, or new dialogue lines asked written with no speaker (M85)."""

    lines = [line for line in str(value or "").splitlines() if line.strip()]
    shape = content_shape_asked(str(request or ""))
    if shape == "dialogue":
        return not any(_SPEAKER_LINE.match(line) for line in lines)
    if shape in {"list", "table"}:
        return sum(1 for line in lines if _LIST_LINE.match(line) or line.count("|") >= 2) < 2
    return False


def _new_dialogue_lines(value: object, last_answer: object) -> str:
    """M99 (DEV-D v3x D-p36-t3): the lines of a dialogue reply that BAXY's last answer does not already hold, in order;
    "" when every line is old (the reply is then not changed here)."""

    said = {_normalized_dialogue_text(line) for line in str(last_answer or "").splitlines() if line.strip()}
    lines = [line for line in str(value or "").splitlines() if line.strip()]
    kept = [line for line in lines if _normalized_dialogue_text(line) not in said]
    return "\n".join(kept) if kept and len(kept) < len(lines) else ""


_UNSUPPORTED_ANCHOR_STOPWORDS = frozenset(
    """
    a al algo an and as be con como completa completar de del do el en esa ese
    eso esta este exacta exacto exactamente for fue had has have i in is it la
    las lo los me mi my no of on or para pedido please por que request requested
    result resultado se sequence secuencia si solicitud solicitado tal that the
    this to tu un una unas unos was were with y ya you your
    arriba bien como cuanto dejaste donde excede gana hasta hay hiciste ido listo
    mal max nueva personally que quien required salio tengas those tiempo todo
    use verifica which
    favor porfa porfis plis pls plz gracias thanks baxy oye hey
    abre abrir open take toma tomar guarda guardala guardar save set haz hacer
    make escribe escribile escribele write diciendo say arrastra drag activa
    activar deja dejar pon poner cambia cambiar cierra cerrar close mutea mutear
    silencia silenciar muestra mostrar show crea crear create
    """.split()
)
