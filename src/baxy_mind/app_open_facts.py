"""What an app.open receipt says (already running, the observed name) and the checks of a reply that tells the
opening.
"""

from __future__ import annotations

import re

from .compose_situation import _merged_observed, _situation_steps


def _app_open_was_already_running(situation: dict) -> bool:
    """True when the app.open receipt says the target was running before this turn.

    The receipt field is `alreadyRunning`; the visible payload renames it to
    `was_running_before_open` so a False value cannot be read as «still closed».
    Both spellings are accepted here because the validator sees either shape
    depending on whether the situation was already projected for the narrator.
    """

    for source in (situation.get("observed"), situation.get("seen"),
                   _merged_observed(situation)):
        if not isinstance(source, dict):
            continue
        for key in ("alreadyRunning", "was_running_before_open"):
            value = source.get(key)
            if isinstance(value, bool):
                return value
    return False


def _apps_found_running(situation: dict) -> list[str]:
    """Revisión F (H3): the names of the apps a verified app.open step of the plan found already running."""

    return [
        name for step in _situation_steps(situation)
        if step.get("operation") == "app.open" and step.get("verified") is True and step.get("succeeded") is True
        and _app_open_was_already_running(step) and (name := _app_open_observed_name(step))
    ]


def _app_open_observed_name(situation: dict) -> str | None:
    """The name an app.open receipt reports for what opened, or None.

    THEN2001 H0097 «abrí el bloc de notas»: a Store application opens under a
    catalog id («windows.notepad») with the person's name in `displayName`
    («Bloc de notas»); the id is a name only when it is a plain one (Steam).
    """

    for source in (situation.get("observed"), situation.get("seen"),
                   _merged_observed(situation)):
        if not isinstance(source, dict):
            continue
        for key in ("displayName", "app", "appId"):
            value = source.get(key)
            if not (isinstance(value, str) and value.strip()):
                continue
            if key == "appId" and "." in value:
                continue
            return value.strip()
    return None


def _claims_it_performed_the_open(folded: str) -> bool:
    """True when the reply attributes the opening to BAXY in this turn."""

    return re.search(
        r"(?:^|[.;:,]\s*|\b(?:y|and|so|pero|but)\s+)(?:ya\s+|yo\s+|i\s+|i've\s+|i\s+have\s+)*"
        # M65 (conv-v3g owner script t37 «He abierto Steam…» over alreadyRunning=true): the perfect tense too.
        r"(?:abrí|abri|abro|(?:(?:lo|la)\s+)?he\s+abierto|opened|launched|started)\b",
        folded,
    ) is not None


def _states_it_was_already_running(folded: str) -> bool:
    """True when the reply says the target was already open or running."""

    return re.search(
        r"ya\s+(?:estaba|está|esta)\b|ya\s+se\s+encontraba\b|"
        r"already\s+(?:running|open|opened|started|launched)\b|"
        r"was\s+already\b|no\s+new\s+instance\b|"
        r"(?:estaba|está|esta)\s+(?:ya\s+)?(?:en\s+ejecución|en\s+ejecucion|abiert[oa]|corriendo)\b",
        folded,
    ) is not None


def _claims_a_relaunch(folded: str) -> bool:
    """True when the reply says it opened the target again over a reused process."""

    # As with opening claims and failure assertions, keep polarity scoped to
    # each clause. An affirmative subject/verb head cannot skip over a denial;
    # a later independent affirmative clause must still be checked.
    # H0461 «che, abrime el chrome» con Chrome ya corriendo: «Ya estaba
    # corriendo, así que solo lo abrí de nuevo» decía justo lo que el recibo
    # niega, y pasaba porque el ancla sólo miraba el punto, el «pero» y la «y».
    # Una consecutiva —«así que», «entonces»— y una coma encabezan cláusula
    # igual; «sólo» y «just» delante no cambian lo que se afirma. Una cláusula
    # que empieza negando sigue fuera.
    return re.search(
        r"(?:^|[.;,]\s*|\b(?:pero|but)\s+|\b(?:as[ií]\s+que|entonces|so|then)\s+"
        r"|\b(?:y|and)\s+(?=(?:yo|i)\b))"
        r"(?!no\b|not\b|nunca\b|never\b)"
        r"(?:s[oó]lo\s+|solamente\s+|just\s+|only\s+)*"
        r"(?:ya\s+|yo\s+|i\s+|i've\s+|i\s+have\s+)*(?:(?:lo|la)\s+)?"
        r"(?:volv[ií]\s+a\s+(?:abrir|lanzar)|"
        r"(?:abrí|abri|abro|lancé|lance)\s+(?:de\s+nuevo|otra\s+vez|igual)|"
        r"(?:opened|launched|started|reopened|relaunched)\s+(?:it\s+|the\s+app\s+)?(?:again|anyway))\b",
        folded,
    ) is not None


def _claims_the_target_was_open_before(folded: str) -> bool:
    """True when the reply asserts the target was ALREADY open before this request.

    Only unambiguous prior-state claims count. «ya está abierta» right after opening
    it is a true statement about the present, so it stays out; «ya estaba», «ya la
    tenía» and «was already running» assert a state the receipt may deny.
    """

    return re.search(
        r"ya\s+estaba\b|ya\s+se\s+encontraba\b|ya\s+ten[íi]a\b|"
        r"ya\s+(?:la|lo)\s+ten[íi]a\b|"
        r"was\s+already\b|were\s+already\b|"
        r"already\s+(?:running|open|opened|started|launched)\s+(?:before|previously)\b|"
        r"(?:estaba|estuvo)\s+(?:ya\s+)?(?:en\s+ejecución|en\s+ejecucion|abiert[oa]|corriendo)\b",
        folded,
    ) is not None
