# DIAX18 (CASX1 caso 23, «crea un documento de Word con una historia de 500 palabras»): the decision that writes the
# document's text inside its call reached DECISION_TOKENS (768), its JSON ended mid-sentence, the kernel's receipt said
# «unparsedArguments: not an argument of this tool; format/title: required and missing», and the model wrote the same
# call again, cut again: 139 s and no document.
import json
from pathlib import Path


def _cut(name: str, raw: str, tokens: int) -> dict:
    return {"choices": [{"finish_reason": "length", "message": {"content": "", "tool_calls": [
        {"id": "c1", "function": {"name": name, "arguments": raw}}]}}],
        "usage": {"prompt_tokens": 30000, "completion_tokens": tokens}}


STORY = {"format": "docx", "title": "El faro", "paragraphs": ["Había una vez un faro.", "Y siguió allí."]}
CUT_RAW = '{"format": "docx", "title": "El faro", "paragraphs": ["Había una vez un faro.", "Y siguió'


def test_a_call_cut_at_the_decisions_cap_is_written_again_with_more_room(tmp_path: Path) -> None:
    from baxy_mind.mind import DECISION_TOKENS, LONG_CALL_TOKENS
    from test_mind_final import _call, _mind
    whole = _call("office_document_create", STORY)
    whole["choices"][0]["finish_reason"] = "tool_calls"
    whole["usage"] = {"prompt_tokens": 30000, "completion_tokens": 1500}
    mind, server = _mind(tmp_path, [_cut("office_document_create", CUT_RAW, DECISION_TOKENS), whole])
    decision = mind.decide(1, "crea un documento de Word con una historia de 500 palabras sobre un faro")
    assert decision["kind"] == "action"
    assert decision["arguments"] == STORY
    assert [b["max_tokens"] for b in server.bodies] == [DECISION_TOKENS, LONG_CALL_TOKENS]
    assert server.bodies[1]["messages"] == server.bodies[0]["messages"]


def test_a_call_still_cut_is_not_run_and_the_model_reads_it_was_its_length(tmp_path: Path) -> None:
    from baxy_mind.mind import DECISION_TOKENS, LONG_CALL_TOKENS
    from test_mind_final import _mind, _say
    mind, server = _mind(tmp_path, [_cut("office_document_create", CUT_RAW, DECISION_TOKENS),
                                    _cut("office_document_create", CUT_RAW, LONG_CALL_TOKENS),
                                    _say("Es demasiado largo para una sola vez; lo escribo más corto.")])
    decision = mind.decide(1, "crea un documento de Word con una historia de 2000 palabras")
    assert decision["kind"] != "action"
    results = [m for m in server.bodies[2]["messages"] if m["role"] == "tool"]
    assert len(results) == 1
    said = json.loads(results[0]["content"])
    assert said["status"] == "not_run" and said["error"] == "call_cut_at_length"
    assert str(LONG_CALL_TOKENS) in said["observed"]["next"]
    assert "unparsedArguments" not in results[0]["content"]


def test_a_second_cut_in_the_turn_ends_it_in_words(tmp_path: Path) -> None:
    from baxy_mind.mind import DECISION_TOKENS, LONG_CALL_TOKENS
    from test_mind_final import _mind, _say
    mind, server = _mind(tmp_path, [_cut("office_document_create", CUT_RAW, DECISION_TOKENS),
                                    _cut("office_document_create", CUT_RAW, LONG_CALL_TOKENS),
                                    _cut("office_document_create", CUT_RAW, DECISION_TOKENS),
                                    _cut("office_document_create", CUT_RAW, LONG_CALL_TOKENS),
                                    _say("No cabe en una sola llamada.")])
    decision = mind.decide(1, "crea un documento de Word con una historia de 3000 palabras")
    assert decision["kind"] != "action"
    assert server.bodies[-1].get("tool_choice") == "none"


def test_an_ordinary_decision_is_asked_once_with_the_same_cap(tmp_path: Path) -> None:
    from baxy_mind.mind import DECISION_TOKENS
    from test_mind_final import _call, _mind
    mind, server = _mind(tmp_path, [_call("office_document_create", STORY)])
    assert mind.decide(1, "crea un documento corto")["kind"] == "action"
    assert [b["max_tokens"] for b in server.bodies] == [DECISION_TOKENS]


def test_words_cut_at_the_cap_are_not_asked_again(tmp_path: Path) -> None:
    from baxy_mind.mind import DECISION_TOKENS
    from test_mind_final import _mind
    words = {"choices": [{"finish_reason": "length", "message": {"content": "Había una vez " * 300}}],
             "usage": {"prompt_tokens": 30000, "completion_tokens": DECISION_TOKENS}}
    mind, server = _mind(tmp_path, [words])
    mind.decide(1, "cuéntame una historia larga")
    assert [b["max_tokens"] for b in server.bodies] == [DECISION_TOKENS]


def test_the_larger_room_stays_inside_the_context(tmp_path: Path) -> None:
    from baxy_mind.mind import DECISION_TOKENS
    from test_mind_final import _call, _mind
    cut = _cut("office_document_create", CUT_RAW, DECISION_TOKENS)
    cut["usage"]["prompt_tokens"] = 47652  # FakeServer.context 49,152: 1,499 tokens left
    whole = _call("office_document_create", STORY)
    mind, server = _mind(tmp_path, [cut, whole])
    mind.decide(1, "crea un documento de Word con una historia de 500 palabras")
    assert server.bodies[1]["max_tokens"] == 1499
