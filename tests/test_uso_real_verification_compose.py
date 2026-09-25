"""Uso real final verification (2026-09-25): composition regressions against the 3.5 close (held-out, cien).

1. «cerralo» after «abrí el bloc de notas»: the model wrote «¿quieres confirmar o cancelar?» three times, each was
   rejected for its lowercase lead and the turn ended in ⚠. A lowercase first letter is form: the compose loop puts
   it in capital and publishes the draft on the first try. Owner: llm.LlmRuntime.compose_user_message (capital_lead).
"""

from __future__ import annotations

import pytest

from baxy_mind.llm import compose_visible_defect
from test_c03_cpu_actor import Recorder


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
