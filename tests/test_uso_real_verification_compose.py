"""Uso real final verification (2026-09-25): composition regressions against the 3.5 close (held-out, cien).

1. «cerralo» after «abrí el bloc de notas»: the model wrote «¿quieres confirmar o cancelar?» three times, each was
   rejected for its lowercase lead and the turn ended in ⚠. A lowercase first letter is form: the compose loop puts
   it in capital and publishes the draft on the first try. Owner: llm.LlmRuntime.compose_user_message (capital_lead).
2. «averiguá qué dijo la crítica»: three drafts spoke as the page and the turn ended in ⚠ (the list of pages that
   used to close such a turn is gone by the owner's rule that the search is not seen). What no draft can say from the
   pages in BAXY's own voice was not found: «No lo encontré.» Owner: compose_user_message (last_resort).
"""

from __future__ import annotations

import pytest

from baxy_mind.llm import compose_visible_defect
from test_c03_cpu_actor import Recorder
from test_c03_uso_real_compose import _RATE_ASK, _RATE_RESULTS, _search_situation


def _wifi(connected: bool) -> dict:
    return {"situation": {"kind": "operation", "operation": "wifi.status", "polarity": "success", "verified": True,
                          "succeeded": True, "observed": {"connected": connected}}}


@pytest.mark.parametrize(
    ("question", "draft", "published"),
    [
        ("¿Estoy conectado al wifi?", "el PC está conectado a Wi-Fi.", "El PC está conectado a Wi-Fi."),
        ("Am I on Wi-Fi?", "the PC is connected to Wi-Fi.", "The PC is connected to Wi-Fi."),
    ],
)
def test_a_lowercase_lead_is_capitalised_without_a_retry(question: str, draft: str, published: str) -> None:
    facts = _wifi(True)
    assert compose_visible_defect(draft, "status", question, facts) == "lowercase"
    client = Recorder([draft])
    assert client.compose_user_message(question, "status", facts) == published
    assert len(client.payloads) == 1


@pytest.mark.parametrize(
    ("question", "pasted", "not_found"),
    [
        (_RATE_ASK, "Nuestro conversor de moneda le permite conocer el cambio del peso chileno en relación con el yen.",
         "No lo encontré."),
        ("yen to chilean peso today", "Our converter on diariodivisas.com gives the rate in real time.",
         "I couldn't find it."),
    ],
)
def test_a_search_report_no_draft_can_say_ends_as_not_found(question: str, pasted: str, not_found: str) -> None:
    client = Recorder([pasted, pasted, pasted])
    assert client.compose_user_message(question, "status", {"situation": _search_situation(_RATE_RESULTS)}) == not_found
    assert len(client.payloads) == 3
