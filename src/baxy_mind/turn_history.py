"""What the conversation's history says to a turn: the person's earlier messages, BAXY's last reply, and the
language the readers settle for the reply.
"""

from __future__ import annotations

from typing import Any

from .semantic import decider as semantic_decider
from .semantic import dialogue as dialogue_slot
from .argument_payload import _previous_reply_fields
from .semantic.request import read_request, response_language as read_language
from .semantic.dialogue import _previous_user_request


def _explicit_response_language(objective: str) -> str:
    """Idioma de presentación de un efecto explícito. Owner: read_request."""

    return read_language(objective)


def _decisive_request_language(objective: str) -> str | None:
    """Idioma cuando la lectura tiene una selección inequívoca o mezcla explícita.

    El detector del modelo respondía en español a «post a letter to Eris» y a
    «book a shuttle to Callisto». Cuando la lectura del pedido tiene evidencia
    de un solo idioma no hay nada que preguntar: manda ella, que es el mismo
    owner con el que después se redacta y se valida.
    """

    reading = read_request(objective)
    if reading.language == "mixed":
        # Balanced evidence is a positive request for both languages, not an
        # absence of evidence to be replaced by a second monolingual choice.
        return "mixed"
    spanish, english = reading.evidence
    if bool(spanish) == bool(english):
        return None
    return reading.language


def _read_reply_language(objective: str, history: list[Any]) -> str | None:
    """The reply language the readers settle without the model, or None."""

    language = _decisive_request_language(objective)
    if language is None and _answers_the_last_question(history, objective):
        # MUSIC1753 «Play a song on Spotify.» → «Queen»: an answer with
        # no language of its own keeps the language of the request it
        # answers; a proper name is not Spanish evidence. tanda-02: only
        # an answer — a new request with no evidence goes to the detector.
        previous = _previous_user_request(history, objective)
        if isinstance(previous, str) and previous.strip():
            language = _decisive_request_language(previous)
    return language


def _answers_the_last_question(history: object, current_request: str) -> bool:
    """BAXY's last message asked a question, so this one may be its answer."""

    last_reply = dialogue_slot.read_slot({}, history, current_request).last_reply
    return bool(last_reply) and last_reply.rstrip().endswith(("?", "？"))


def _prior_user_texts(history: object, current: str) -> tuple[str, ...]:
    """The person's earlier messages, oldest first, without the current one when the history already ends in it."""

    items = [item for item in history if isinstance(item, dict)] if isinstance(history, list) else []
    if items and items[-1].get("role") == "user" and items[-1].get("content") == current:
        items = items[:-1]
    return tuple(str(item.get("content") or "") for item in items if item.get("role") == "user" and item.get("content"))


def _conversation_grounding_source(objective: str, history: object) -> str:
    """M43: the request, the person's recent turns and BAXY's last reply, the text a decided value may come from.

    Spent FINAL: «Abre el Calendar» restated «Abre el Calendario»; the folder of a PDF said one turn earlier; «save
    that as a note» whose content was BAXY's previous answer. Only what was said in this conversation counts.
    """

    parts = [objective]
    if isinstance(history, list):
        turns = [item for item in history if isinstance(item, dict) and item.get("content")]
        parts.extend(
            str(item["content"])[:1500] for item in turns[-semantic_decider.HISTORY_TURNS:]
            if item.get("role") == "user"
        )
        last_reply = next((item for item in reversed(turns) if item.get("role") == "assistant"), None)
        if last_reply is not None:
            parts.append(str(last_reply["content"])[:1500])
    return "\n".join(parts)


def _previous_reply(history: object) -> str | None:
    """M67 (FINAL F-w14-t3, F-w15-t4): BAXY's reply right before the current message, whole, or None.

    The decider's values are bounded and the grounding source cuts each turn, so a content that is that reply (a SQL
    query, a packing list) travels only through here. Only the history's last assistant turn counts, with at most
    the current message after it.
    """

    if not isinstance(history, list):
        return None
    turns = [item for item in history if isinstance(item, dict) and str(item.get("content") or "").strip()]
    if turns and turns[-1].get("role") == "user":
        turns = turns[:-1]
    if not turns or turns[-1].get("role") != "assistant":
        return None
    return str(turns[-1]["content"]).strip()


def _previous_reply_may_be_content(tool: dict, history: object) -> bool:
    """M67b: BAXY's previous reply fits a long free-text field of the operation, so it may be the content.

    The decider's values are bounded and may restate the content («el query de SQL») instead of carrying it; then
    the extraction, which reads the reply, decides (M67), not the decider's values alone.
    """

    reply = _previous_reply(history)
    if not reply:
        return False
    schema = tool.get("function", {}).get("parameters") if isinstance(tool, dict) else None
    properties = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(properties, dict):
        return False
    strings = tuple(
        name for name, contract in properties.items()
        if isinstance(contract, dict) and contract.get("type") == "string" and "enum" not in contract
    )
    return bool(_previous_reply_fields(schema, strings, reply))


def _conversation_exchanges(history: object) -> list[tuple[str, str]]:
    """M160: each of BAXY's replies with the person's message it answered, oldest first, without the current message."""

    turns = [item for item in history if isinstance(item, dict)] if isinstance(history, list) else []
    if turns and turns[-1].get("role") == "user":
        turns = turns[:-1]
    exchanges: list[tuple[str, str]] = []
    asked = ""
    for item in turns:
        content = str(item.get("content") or "")
        if item.get("role") == "user":
            asked = content
        elif item.get("role") == "assistant" and content.strip():
            exchanges.append((asked, content))
            asked = ""
    return exchanges


def _prior_user_requests(history: object) -> tuple[str, ...]:
    """The person's earlier messages of the conversation, oldest first, without the current one: the history's last
    turn when it is theirs is the message being read (the shell sends it last, as ``_person_message`` reads it), even
    when what is grounded is a plan step's purpose in the model's words and not the message itself."""

    turns = list(history) if isinstance(history, list) else []
    if turns and isinstance(turns[-1], dict) and turns[-1].get("role") == "user":
        turns.pop()
    return tuple(
        str(item.get("content") or "")
        for item in turns
        if isinstance(item, dict) and item.get("role") == "user" and str(item.get("content") or "").strip()
    )


_APP_HISTORY_WINDOW = 12


def _baxy_replied(history: object) -> bool:
    """Whether BAXY said something earlier in the conversation (an assistant turn with content): its last reply is the
    nearest antecedent of «esto» or «lo» (M67 copies it), so a save of «esto» is never read as the window in front
    (review of lectura-ruta, finding 1).

    Only a reply counts, an assistant turn after a turn of the person's: what the shell shows before the person's first
    message (the welcome, a notice) answers nothing and is no antecedent (r15b t-file-1: the welcome as the only
    assistant turn left «guardá esto como N en C» as a new file written with the request as its text)."""

    turns = list(history) if isinstance(history, list) else []
    # A history as long as the App's window (``MainWindowViewModel.BuildMindHistory``: the last twelve messages) may
    # have left out the person's turn a reply at its head answers; that reply is still one (revisión destino del
    # pedido, hallazgo 6). The welcome only heads a conversation shorter than the window.
    person_spoke = len(turns) >= _APP_HISTORY_WINDOW
    for item in turns:
        if not isinstance(item, dict):
            continue
        if item.get("role") == "user":
            person_spoke = True
        elif person_spoke and item.get("role") == "assistant" and str(item.get("content") or "").strip():
            return True
    return False


def _person_message(history: object, objective: str) -> str:
    """The person's own message of this turn: the history's last turn when it is theirs (the shell sends it last),
    otherwise the objective."""

    last = history[-1] if isinstance(history, list) and history else None
    if isinstance(last, dict) and last.get("role") == "user" and str(last.get("content") or "").strip():
        return str(last["content"])
    return objective
