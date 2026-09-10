"""Connectivity recovery keeps observed scope and the latest failed draft."""
import copy
import json

import pytest

from baxy_mind.llm import compose_visible_defect
from test_c03_cpu_actor import Recorder


def facts(operation, connected):
    observed = {'connected': connected} if operation == 'wifi.status' else {'online': connected}
    return {'situation': {'kind': 'operation', 'operation': operation,
                         'polarity': 'success', 'verified': True,
                         'succeeded': True, 'observed': observed}}


@pytest.mark.parametrize('operation', ['wifi.status', 'network.status'])
@pytest.mark.parametrize('connected', [False, True])
@pytest.mark.parametrize('language', ['es', 'en'])
def test_repair_preserves_original_observations_and_actual_rejected_subject(operation, connected, language):
    scope = 'Wi-Fi' if operation == 'wifi.status' else 'network'
    if language == 'es':
        question = f'Comprueba la conexión de este PC a {scope}.'
        bad = f'{"" if connected else "No "}Estoy conectado a {scope}.'
        good = f'El PC {"" if connected else "no "}está conectado a {scope}.'
    else:
        question = f'Am I connected to {scope}?'
        bad = f'I am {"" if connected else "not "}connected to {scope}.'
        good = f'The PC is {"" if connected else "not "}connected to {scope}.'
    source = facts(operation, connected)
    original = copy.deepcopy(source)
    assert compose_visible_defect(bad, 'status', question, source) == 'wrong_actor'
    client = Recorder([bad, good])
    assert client.compose_user_message(question, 'status', source) == good
    assert source == original
    first, retry = client.payloads
    assert retry['messages'][:-2] == first['messages']
    assert retry['messages'][-2] == {'role': 'assistant', 'content': bad}
    assert retry['messages'][-1]['role'] == 'user'
    assert 'observations' in retry['messages'][-1]['content']
    assert 'whether this PC is online' not in retry['messages'][-1]['content']
    assert retry['max_tokens'] == first['max_tokens']


def test_next_repair_uses_latest_wlan_draft_without_demanding_first_person():
    first = 'No estoy conectado a ninguna red wifi.'
    second = 'Estoy conectado a una red wifi.'
    good = 'El PC no está conectado a ninguna red wifi.'
    client = Recorder([first, second, good])
    assert client.compose_user_message('¿A qué wifi estoy conectado?', 'status', facts('wifi.status', False)) == good
    assert len(client.payloads) == 3
    assert client.payloads[2]['messages'][-2]['content'] == second
    assert 'First person' not in json.dumps(client.payloads[2]['messages'])
    assert client.payloads[2]['messages'][:-2] == client.payloads[0]['messages']


def test_unrepaired_actor_still_exhausts_without_publishing_wrong_subject():
    client = Recorder(['No estoy conectado a ninguna red wifi.'] * 3)
    assert client.compose_user_message('¿A qué wifi estoy conectado?', 'status', facts('wifi.status', False)) == ''
    assert len(client.payloads) == 3


def test_correct_wlan_answer_needs_no_repair():
    good = 'El PC no está conectado a ninguna red wifi.'
    client = Recorder([good])
    assert client.compose_user_message('¿A qué wifi estoy conectado?', 'status', facts('wifi.status', False)) == good
    assert len(client.payloads) == 1


def test_other_model_keeps_its_own_sampling_when_repairing_network_subject():
    client = Recorder(['I am not connected to Wi-Fi.', 'The PC is not connected to Wi-Fi.'], model='Other-4B.gguf')
    assert client.compose_user_message('Am I connected to Wi-Fi?', 'status', facts('wifi.status', False))
    assert client.payloads[1]['temperature'] == 0.0
    assert 'top_k' not in client.payloads[1]
