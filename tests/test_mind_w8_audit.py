"""Audit of the mind (w8-mente, 2026-10-23): each test holds one finding fixed in src/baxy_mind."""
import json

import pytest

from test_mind_doubt_policy import _call as _sure_call
from test_mind_doubt_policy import _mind as _doubt_mind
from test_mind_doubt_policy import _say as _doubt_say
from test_mind_doubt_policy import _token


def _unsure_yes() -> dict:
    reply = _sure_call("confirm_pending", {"approve": True}, 0.78)
    reply["choices"][0]["logprobs"]["content"][0] = _token("<tool_call>", 1.0)
    return reply


@pytest.mark.parametrize("pending, error", [
    (None, "nothing_pending"),
    ({"operation": "filesystem.known.trash.named", "ended": "dropped"}, "confirmation_dropped")])
def test_an_unsure_yes_with_nothing_waiting_reads_why_instead_of_a_doubt_question(tmp_path, monkeypatch, pending,
                                                                                 error) -> None:
    # The confirm floor held an unsure «sí» even when nothing waited for one: the result that says so (nothing_pending,
    # or the question that ended and the call to make again) never reached the model, which asked a question instead.
    monkeypatch.delenv("BAXY_S1_DOUBT", raising=False)
    monkeypatch.delenv("BAXY_CONFIRM_FLOOR", raising=False)
    mind, server = _doubt_mind(tmp_path, [_unsure_yes(), _doubt_say("No había nada esperando tu sí.")])
    result = mind.decide(1, "sí pero el otro", pending)
    assert result["kind"] == "conversation" and result["operation"] is None
    told = [m["content"] for m in server.bodies[1]["messages"] if m["role"] == "tool"]
    assert json.loads(told[-1])["error"] == error
    assert not any("Nota interna" in str(m["content"]) for m in server.bodies[1]["messages"])
