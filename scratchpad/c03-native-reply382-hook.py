"""Diagnostic: forward an actual same-request native abstention into chat guards."""
import copy
from baxy_mind import llm as _llm382

_post382 = LlmRuntime._post
_native382 = LlmRuntime._post_native_tool_selection
_chat382 = LlmRuntime.chat
_decide382 = LlmRuntime.decide_turn
_local382 = threading.local()


def _post_with_native_candidate382(self, payload, *args, **kwargs):
    candidate = getattr(_local382, 'for_chat', None)
    messages = payload.get('messages') or []
    if (candidate is not None and messages
            and messages[0].get('content') == _llm382.SYSTEM_PROMPT
            and messages[-1].get('content') == candidate[0]):
        _local382.for_chat = None
        with lock, (private / 'forwarded-native.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'request': candidate[0], 'response': candidate[1],
                'replaced_chat_payload': payload}, ensure_ascii=False) + '\n')
        return copy.deepcopy(candidate[1])
    response = _post382(self, payload, *args, **kwargs)
    if getattr(_local382, 'capture_native', False):
        _local382.native_response = copy.deepcopy(response)
    return response


def _native_with_candidate382(self, text, *args, **kwargs):
    if not getattr(_local382, 'inside_decide', False):
        return _native382(self, text, *args, **kwargs)
    self._candidate382 = None
    _local382.capture_native = True
    _local382.native_response = None
    try:
        result = _native382(self, text, *args, **kwargs)
        response = _local382.native_response
    finally:
        _local382.capture_native = False
    if result.get('mode') == 'conversation' and response is not None:
        choice = response['choices'][0]
        message = choice['message']
        if choice.get('finish_reason') == 'stop' and message.get('content') and not message.get('tool_calls'):
            self._candidate382 = (text, response)
    return result


def _chat_with_candidate382(self, text, *args, **kwargs):
    candidate = getattr(self, '_candidate382', None)
    self._candidate382 = None
    _local382.for_chat = (
        candidate if candidate is not None and candidate[0].strip('¿?¡!. ') == text.strip('¿?¡!. ')
        and kwargs.get('conversation_kind') == 'knowledge'
        and not kwargs.get('authenticated_operations') else None
    )
    if _local382.for_chat is not None:
        _local382.for_chat = (text, _local382.for_chat[1])
    try:
        # All actual chat guards/retries and final turn checks still run.
        return _chat382(self, text, *args, **kwargs)
    finally:
        _local382.for_chat = None


def _decide_with_candidate382(self, *args, **kwargs):
    self._candidate382 = None
    _local382.inside_decide = True
    try:
        return _decide382(self, *args, **kwargs)
    finally:
        _local382.inside_decide = False


LlmRuntime.decide_turn = _decide_with_candidate382
LlmRuntime._post = _post_with_native_candidate382
LlmRuntime._post_native_tool_selection = _native_with_candidate382
LlmRuntime.chat = _chat_with_candidate382
