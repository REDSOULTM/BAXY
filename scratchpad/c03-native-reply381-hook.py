"""Diagnostic: forward an actual same-request native abstention into chat guards."""
import copy
from baxy_mind import llm as _llm381

_post381 = LlmRuntime._post
_native381 = LlmRuntime._post_native_tool_selection
_chat381 = LlmRuntime.chat
_local381 = threading.local()


def _post_with_native_candidate381(self, payload, *args, **kwargs):
    candidate = getattr(_local381, 'for_chat', None)
    messages = payload.get('messages') or []
    if (candidate is not None and messages
            and messages[0].get('content') == _llm381.SYSTEM_PROMPT
            and messages[-1].get('content') == candidate[0]):
        _local381.for_chat = None
        with lock, (private / 'forwarded-native.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'request': candidate[0], 'response': candidate[1],
                'replaced_chat_payload': payload}, ensure_ascii=False) + '\n')
        return copy.deepcopy(candidate[1])
    response = _post381(self, payload, *args, **kwargs)
    if getattr(_local381, 'capture_native', False):
        _local381.native_response = copy.deepcopy(response)
    return response


def _native_with_candidate381(self, text, *args, **kwargs):
    self._candidate381 = None
    _local381.capture_native = True
    _local381.native_response = None
    try:
        result = _native381(self, text, *args, **kwargs)
        response = _local381.native_response
    finally:
        _local381.capture_native = False
    if result.get('mode') == 'conversation' and response is not None:
        choice = response['choices'][0]
        message = choice['message']
        if choice.get('finish_reason') == 'stop' and message.get('content') and not message.get('tool_calls'):
            self._candidate381 = (text, response)
    return result


def _chat_with_candidate381(self, text, *args, **kwargs):
    candidate = getattr(self, '_candidate381', None)
    self._candidate381 = None
    _local381.for_chat = (
        candidate if candidate is not None and candidate[0] == text
        and kwargs.get('conversation_kind') == 'knowledge'
        and not kwargs.get('authenticated_operations') else None
    )
    try:
        # All actual chat guards/retries and final turn checks still run.
        return _chat381(self, text, *args, **kwargs)
    finally:
        _local381.for_chat = None


LlmRuntime._post = _post_with_native_candidate381
LlmRuntime._post_native_tool_selection = _native_with_candidate381
LlmRuntime.chat = _chat_with_candidate381
