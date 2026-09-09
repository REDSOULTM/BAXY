"""Private local HTTP observation; delegates unchanged to production transport."""
import itertools
import json
import os
from pathlib import Path
import threading
import time
from baxy_mind.llm import LlmRuntime

private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-scoped-lora-product589-private'
private.mkdir(parents=True, exist_ok=True)
lock = threading.Lock()
sequence = itertools.count()
original = LlmRuntime._post

def observe(self, payload, *args, **kwargs):
    number = next(sequence)
    def log(value):
        with lock, (private/'http-posts.jsonl').open('a',encoding='utf-8') as handle:
            handle.write(json.dumps({'time':time.monotonic(),'pid':os.getpid(),'id':number,**value},ensure_ascii=False)+'\n')
    log({'stage':'request','payload':payload})
    try:
        response = original(self,payload,*args,**kwargs)
    except Exception as error:
        log({'stage':'failure','errorType':type(error).__name__,'detail':str(error)})
        raise
    log({'stage':'response','response':response})
    return response

LlmRuntime._post = observe




original_command = LlmRuntime._server_command
def observed_command(self):
    command = [*original_command(self), '--verbosity', '4', '--log-file', str(private/'server.log')]
    (private/'effective-server-command.json').write_text(json.dumps(command, indent=2)+'\n', encoding='utf-8')
    return command
LlmRuntime._server_command = observed_command

"""Experimental CPU-only adapter selection; no response/fact rewriting."""
import hashlib
import urllib.request
from baxy_mind import llm as cpu_llm

_cpu_adapter_path = Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-training-cdbee75f/c03-pilot-lora-v4-f32.gguf')
assert hashlib.sha256(_cpu_adapter_path.read_bytes()).hexdigest() == 'e28d7728c915861a798b005c22e7b9148fdce729e4a402ac5d502abdbeaccce5'
_cpu_role_state = threading.local()
_cpu_original_command = cpu_llm.LlmRuntime._server_command
_cpu_original_ready = cpu_llm.LlmRuntime._wait_ready
_cpu_original_compose = cpu_llm.LlmRuntime.compose_user_message
_cpu_original_post = cpu_llm.LlmRuntime._post


def _cpu_command(self):
    command = _cpu_original_command(self)
    command += ['--lora', str(_cpu_adapter_path), '--lora-init-without-apply']
    (private / 'adapter-effective-server-command.json').write_text(json.dumps(command, indent=2), encoding='utf-8')
    return command


def _cpu_ready(self, timeout=420.0):
    _cpu_original_ready(self, timeout)
    url = self._endpoint + '/lora-adapters'
    with urllib.request.urlopen(url, timeout=5) as response:
        initial = json.load(response)
    assert len(initial) == 1 and initial[0]['id'] == 0
    operation = urllib.request.Request(url, data=json.dumps([{'id': 0, 'scale': 0.0}]).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(operation, timeout=5) as response:
        changed = json.load(response)
    with urllib.request.urlopen(url, timeout=5) as response:
        current = json.load(response)
    assert current[0]['scale'] == 0
    (private / 'adapter-state.json').write_text(json.dumps({'initial': initial, 'set': changed, 'verified': current}, indent=2), encoding='utf-8')


def _cpu_compose(self, user_text, intent, facts, *args, **kwargs):
    situation = cpu_llm._situation_from_facts(facts)
    observed = cpu_llm._merged_observed(situation)
    prior = getattr(_cpu_role_state, 'active', False)
    _cpu_role_state.active = (
        isinstance(observed.get('cpu'), dict) and bool(observed['cpu'])
        and set(observed).issubset({'scope', 'cpu', 'failures'})
        and situation.get('cause') != 'acting'
        and situation.get('kind') != 'confirmation'
    )
    try:
        return _cpu_original_compose(self, user_text, intent, facts, *args, **kwargs)
    finally:
        _cpu_role_state.active = prior


def _cpu_post(self, payload, *args, **kwargs):
    payload = {**payload, 'lora': [{'id': 0, 'scale': 0.0}]}
    if getattr(_cpu_role_state, 'active', False):
        payload.update(temperature=0.7, top_p=0.8, top_k=20, min_p=0.0,
                       presence_penalty=0.0, repeat_penalty=1.0, seed=0,
                       lora=[{'id': 0, 'scale': 1.0}])
    return _cpu_original_post(self, payload, *args, **kwargs)


cpu_llm.LlmRuntime._server_command = _cpu_command
cpu_llm.LlmRuntime._wait_ready = _cpu_ready
cpu_llm.LlmRuntime.compose_user_message = _cpu_compose
cpu_llm.LlmRuntime._post = _cpu_post
