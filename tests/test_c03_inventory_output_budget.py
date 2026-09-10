"""Real786 completions and resource boundaries for the existing dense budget."""
import copy
import json
from pathlib import Path

import pytest

from baxy_mind.llm import LlmRuntime


MODELS = ['Qwen3-4B-Instruct-2507-Q4_K_M.gguf', 'K2-Horizon-3.7B-Q4_K_M.gguf']
RECORDED = json.loads((Path(__file__).parent / 'data/c03_inventory_completion786.json').read_text(encoding='utf-8'))


def observation(count):
    return {
        'kind': 'operation', 'operation': 'window.resolve',
        'verified': True, 'succeeded': True, 'polarity': 'success',
        'observed': {
            'windows': [{'title': f'Orbita {i}', 'processName': 'Viewer'} for i in range(count)],
            'count': count, 'observedCount': count, 'offset': 0, 'complete': True,
            'totalCount': count, 'hasMore': False, 'nextOffset': None,
        },
    }


class FirstRequest(BaseException):
    pass


class Capture(LlmRuntime):
    def __init__(self, model):
        self._gguf = model
        self.requests = []

    def _post(self, payload):
        self.requests.append(copy.deepcopy(payload))
        raise FirstRequest()


def first_request(model, situation, request='List the windows.'):
    original = copy.deepcopy(situation)
    client = Capture(model)
    with pytest.raises(FirstRequest):
        client.compose_user_message(request, 'status', {'situation': situation})
    assert situation == original
    return client.requests[0]


@pytest.mark.parametrize('model', MODELS)
@pytest.mark.parametrize('user_text', ['Lista las ventanas.', 'List the windows.'])
@pytest.mark.parametrize('count,expected', [(0, 256), (1, 256), (7, 256), (8, 512), (20, 512), (50, 512)])
def test_only_dense_inventories_use_the_existing_larger_budget(model, user_text, count, expected):
    payload = first_request(model, observation(count), user_text)
    assert payload['max_tokens'] == expected
    assert payload['cache_prompt'] is False
    assert 'Este resultado contiene muchos hechos obligatorios' not in payload['messages'][1]['content']


@pytest.mark.parametrize('model', MODELS)
@pytest.mark.parametrize('size,expected', [(511, 256), (512, 512), (800, 512)])
def test_long_identity_uses_projected_character_boundary_without_ascii_inflation(model, size, expected):
    situation = observation(1)
    window = situation['observed']['windows'][0]
    window['title'] = ''
    base = len(json.dumps([window], ensure_ascii=False, separators=(',', ':')))
    window['title'] = 'á' * (size - base)
    assert first_request(model, situation)['max_tokens'] == expected


@pytest.mark.parametrize('model', MODELS)
@pytest.mark.parametrize('mutation', [
    {'verified': False}, {'verified': 'true'}, {'succeeded': False},
    {'succeeded': 'true'}, {'operation': 'window.application.status'},
    {'operation': 'system.status'},
])
def test_unsupported_or_unverified_inventory_does_not_gain_a_larger_budget(model, mutation):
    situation = observation(20)
    situation.update(mutation)
    assert first_request(model, situation)['max_tokens'] == 256


@pytest.mark.parametrize('model', MODELS)
def test_unrequested_window_details_do_not_inflate_the_output_budget(model):
    situation = observation(1)
    situation['observed']['windows'][0]['unusedDetails'] = 'x' * 5000
    assert first_request(model, situation)['max_tokens'] == 256


@pytest.mark.parametrize('case', RECORDED, ids=lambda c: c['case_id'])
def test_recorded_complete_inventory_is_delivered_without_retry_or_prompt_change(case):
    client = Capture(MODELS[0])

    def replay(payload):
        client.requests.append(copy.deepcopy(payload))
        arm = 'B_output_512' if payload['max_tokens'] >= 512 else 'A_original_256'
        return {'choices': [copy.deepcopy(case['replies'][arm])]}

    client._post = replay
    result = client.compose_user_message(case['request'], 'status', {'situation': case['situation']})
    assert result == case['replies']['B_output_512']['message']['content']
    assert len(client.requests) == 1
    assert client.requests[0]['messages'] == case['messages']
    assert client.requests[0]['max_tokens'] == 512
