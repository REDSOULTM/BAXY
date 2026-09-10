"""Verify observation transparency with stub calls, separate from product data."""
from pathlib import Path
import json
import os
import sys
import tempfile
import types


def verify_hook(path, destination):
    source = path.read_text(encoding='utf-8')
    literal = 'BAXY/C03-compose762-private'
    assert source.count(literal) == 1
    assert destination == Path(os.environ['LOCALAPPDATA']) / literal
    probe = destination / 'observer-write-probe.tmp'
    with probe.open('x', encoding='utf-8') as stream:
        stream.write('observer preflight\n')
    assert probe.read_text(encoding='utf-8') == 'observer preflight\n'
    probe.unlink()
    calls = []
    result = {'sentinel': 'original object'}
    failure = RuntimeError('original exception')

    class Stub:
        fail = False

        def _post(self, payload, *args, **kwargs):
            calls.append(('post', payload, args, kwargs))
            if self.fail:
                raise failure
            return result

        def compose_user_message(self, text, intent, facts, *args, **kwargs):
            calls.append(('compose', text, intent, facts, args, kwargs))
            if self.fail:
                raise failure
            return result

    module_name = 'baxy_mind.llm'
    old_module = sys.modules.get(module_name)
    module = types.ModuleType(module_name)
    module.LlmRuntime = Stub
    previous_local = os.environ['LOCALAPPDATA']
    with tempfile.TemporaryDirectory(prefix='c03-observer762-') as temporary:
        synthetic = Path(temporary) / literal
        synthetic.mkdir(parents=True)
        try:
            os.environ['LOCALAPPDATA'] = temporary
            sys.modules[module_name] = module
            namespace = {'__name__': 'observer_preflight', '__file__': str(path)}
            exec(compile(source, str(path), 'exec'), namespace)
            instance = Stub()
            payload, facts = {'messages': []}, {'observed': {'number': 7}}
            assert instance._post(payload, timeout=3.75, max_attempts=1) is result
            assert instance.compose_user_message('synthetic', 'status', facts, timeout=3.75) is result
            instance.fail = True
            for invoke in (lambda: instance._post(payload, timeout=3.75, max_attempts=1),
                           lambda: instance.compose_user_message('synthetic', 'status', facts, timeout=3.75)):
                try:
                    invoke()
                except RuntimeError as observed:
                    assert observed is failure
                else:
                    raise AssertionError('Observer swallowed exception')
            assert len(calls) == 4
            assert calls[0] == calls[2] and calls[1] == calls[3]
            assert calls[0][1] is payload and calls[1][3] is facts
            assert calls[0][3] == {'timeout': 3.75, 'max_attempts': 1}
            assert calls[1][5] == {'timeout': 3.75}
            for name, stages in [('http-posts.jsonl', ['request', 'response', 'request', 'failure']),
                                 ('compose-boundary.jsonl', ['input', 'output', 'input', 'failure'])]:
                rows = [json.loads(line) for line in (synthetic / name).read_text(encoding='utf-8').splitlines()]
                assert [row['stage'] for row in rows] == stages
                assert rows[-1]['errorType'] == 'RuntimeError' and 'traceback' in rows[-1]
        finally:
            os.environ['LOCALAPPDATA'] = previous_local
            if old_module is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = old_module
    assert not any((destination / name).exists() for name in ['http-posts.jsonl', 'compose-boundary.jsonl'])
    return {'passed': True, 'original_calls': 4, 'arguments_returns_exceptions_preserved': True,
            'synthetic_data_separate': True, 'destination_writable': True}
