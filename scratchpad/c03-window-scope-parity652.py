"""Match integrated first requests to measured650 and conserve other routes."""
from pathlib import Path
import copy
import hashlib
import json
import os
import subprocess
import sys
import types

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'src'))
from baxy_mind.llm import LlmRuntime

base = root/'artifacts/comprobaciones/C03'
home = Path(os.environ['LOCALAPPDATA'])/'BAXY'
config = json.loads((home.parent/'BAXYRuntime/mind-runtime-v1.json').read_text(encoding='utf-8-sig'))
panel = json.loads((home/'C03-native-window-scope650-private/panel.json').read_text(encoding='utf-8'))
module_name = 'baxy_mind._window_scope_baseline652'
baseline = types.ModuleType(module_name)
baseline.__package__ = 'baxy_mind'
baseline.__file__ = str(root/'src/baxy_mind/llm.py')
sys.modules[module_name] = baseline
old_source = subprocess.check_output(['git', 'show', 'e1c6db6b:src/baxy_mind/llm.py'], cwd=root).decode('utf-8')
exec(compile(old_source, module_name, 'exec'), baseline.__dict__)

class Captured(Exception):
    pass

def capture(runtime_type, text, facts, intent='status'):
    class Builder(runtime_type):
        def __init__(self):
            self._gguf = config['gguf']
        def _post(self, payload, **_kwargs):
            self.payload = copy.deepcopy(payload)
            raise Captured()
    client = Builder()
    try:
        client.compose_user_message(text, intent, facts)
    except Captured:
        return client.payload
    raise AssertionError('Expected a first compositor request')

def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

results = []
for row in panel:
    runtime_type = LlmRuntime if row['arm'] == 'observation_scope' else baseline.LlmRuntime
    current = capture(runtime_type, row['text'], row['facts'])
    assert current == row['payload'], (row['case_id'], row['arm'])
    results.append({'case_id': row['case_id'], 'arm': row['arm'], 'payload_equal': True, 'sha256': digest(current)})

original = next(r for r in panel if r['case_id'] == 'observed647')
observed = json.loads(original['facts']['situation'])
controls = []
for label, patch in [
    ('unverified', {'verified': False}), ('unsuccessful', {'succeeded': False}),
    ('acting', {'cause': 'acting'}), ('installation-read', {'operation': 'app.installed'}),
    ('foreground-read', {'operation': 'window.active'}),
    ('conversation', {'kind': 'conversation', 'operation': '', 'verified': False}),
]:
    situation = copy.deepcopy(observed)
    situation.update(patch)
    controls.append((label, {'situation': json.dumps(situation)}))
for label, value in [('missing-count', None), ('boolean-count', True)]:
    situation = copy.deepcopy(observed)
    situation['observed']['visibleWindowCount'] = value
    controls.append((label, {'situation': json.dumps(situation)}))
controls.append(('mission-with-steps', {'situation': json.dumps({
    'kind': 'mission', 'polarity': 'success', 'verified': True, 'succeeded': True,
    'steps': [observed, {'kind': 'operation', 'operation': 'system.time',
        'polarity': 'success', 'observed': {'clock': '14:32'}}],
})}))
for label, facts in controls:
    previous = capture(baseline.LlmRuntime, original['text'], facts)
    current = capture(LlmRuntime, original['text'], facts)
    assert current == previous, label
    results.append({'case_id': label, 'arm': 'unaffected_control', 'payload_equal': True, 'sha256': digest(current)})
(base/'astra-window-scope-source652/PARITY.json').write_text(
    json.dumps({'compared': len(results), 'inference': False, 'results': results}, ensure_ascii=False, indent=2)+'\n',
    encoding='utf-8', newline='\n')
print({'measured_payloads_preserved': 16, 'unaffected_controls': len(controls), 'inference': False})
