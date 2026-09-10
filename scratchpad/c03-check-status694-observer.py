"""Check observational identity and render694 driver without launching BAXY."""
import ast
import builtins
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import types

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-status-batch694.py').read_text(encoding='utf-8')
source = source[source.index("source=(root/'scratchpad/c03-status-batch689.py')"):]
namespace = {'root': root, '__file__': str(root/'scratchpad/c03-status-batch694.py')}
drivers = []


def render(code, *unused):
    if 'ProcessTreeGpuSampler' in code.co_names:
        drivers.append(namespace['source'])
        return
    builtins.exec(code, namespace)


namespace['exec'] = render
builtins.exec(compile(source, '<render694>', 'exec'), namespace)
assert len(drivers) == 1
driver = drivers[0]
ast.parse(driver)
assert "BAXY_MIND_PYTHONPATH=str(root/'scratchpad/c03-status694-hook')+os.pathsep+str(root/'src')" in driver
assert "time.monotonic()-started>900" in driver
assert 'C03-private-product521-private' not in driver
assert 'C03-status-batch694-private' in driver
assert 'transparent local HTTP/decision observation' in driver

calls = []
response = {'choices': [{'text': 'unchanged'}]}
decision = {'mode': 'action'}
error = ValueError('sentinel failure')


class FakeRuntime:
    def _post(self, payload, *args, **kwargs):
        calls.append(('post', payload, args, kwargs))
        if payload.get('fail'):
            raise error
        return response

    def decide_turn(self, text, candidates, *, history=None, evidence=None):
        calls.append(('decide', text, candidates, history, evidence))
        return decision


module = types.ModuleType('baxy_mind.llm')
module.LlmRuntime = FakeRuntime
sys.modules['baxy_mind.llm'] = module
with tempfile.TemporaryDirectory(prefix='c03-observer694-') as directory:
    os.environ['LOCALAPPDATA'] = directory
    private = Path(directory)/'BAXY/C03-status-batch694-private'
    private.mkdir(parents=True)
    runpy.run_path(str(root/'scratchpad/c03-status694-hook/sitecustomize.py'))
    runtime = FakeRuntime()
    payload = {'messages': [{'role': 'user', 'content': 'private fixture'}]}
    assert runtime._post(payload, 7, flag=True) is response
    assert calls[-1][1] is payload and calls[-1][2:] == ((7,), {'flag': True})
    candidates, history, evidence = [], [], []
    assert runtime.decide_turn('query', candidates, history=history, evidence=evidence) is decision
    assert calls[-1][2] is candidates and calls[-1][3] is history and calls[-1][4] is evidence
    try:
        runtime._post({'fail': True})
    except ValueError as caught:
        assert caught is error
    else:
        raise AssertionError('Exception was swallowed')
    assert len(calls) == 3
    http = [json.loads(line) for line in (private/'http-posts.jsonl').read_text(encoding='utf-8').splitlines()]
    assert [row['stage'] for row in http] == ['request', 'response', 'request', 'failure']
    boundary = [json.loads(line) for line in (private/'decision-boundary.jsonl').read_text(encoding='utf-8').splitlines()]
    assert [row['stage'] for row in boundary] == ['input', 'output']

print(json.dumps({'driver_rendered_without_launch': True, 'driver_sha256': hashlib.sha256(driver.encode()).hexdigest(), 'single_call_argument_return_exception_identity': True, 'private_records': len(http)+len(boundary)}))
