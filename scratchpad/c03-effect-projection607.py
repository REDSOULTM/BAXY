"""Replay original594 native classifications through one changed presentation rule."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json
import os
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind.__main__ import apply_conversation_effect_presentation
from baxy_mind.llm import derive_semantic_effect_state

out = root / 'artifacts/comprobaciones/C03/astra-effect-projection607'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-effect-projection607-private'
prior = private.parent / 'C03-guard-boundary594-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

source = (root / 'src/baxy_mind/__main__.py').read_text(encoding='utf-8')
node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
            and n.name == 'apply_conversation_effect_presentation')
original = ast.get_source_segment(source, node)
old = 'if state not in {"complete", "not_complete"}:'
assert original.count(old) == 1
changed = original.replace(old, 'if state != "complete":')
namespace = dict(apply_conversation_effect_presentation.__globals__)
exec(compile(changed, '<607-presentation-only-candidate>', 'exec'), namespace)
candidate = namespace['apply_conversation_effect_presentation']
write(out / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Offline replay of unchanged native original594 guard outputs. Compare actual presentation function with one candidate condition: only a complete effect can relabel primary knowledge as unsupported. All inputs, model outputs, classifiers, operation authority and full-source files unchanged.',
    'hypothesis': 'Missing arguments do not establish that a capability is unsupported. A one-sided incomplete guard must not convert primary knowledge into an unsupported capability.',
    'criteria': 'H0012 keeps primary knowledge. Other native594 cases keep exactly the existing presentation. No conversation becomes an action. This comparison does not validate primary classification, missing-argument clarification, action execution, UI or final prose; integrated regression is required before adoption.',
    'source_sha256': sha(root / 'src/baxy_mind/__main__.py'),
    'capture_sha256': sha(prior / 'responses.jsonl'),
    'inheritance': '593 first incorrect boundary;594/595 prompt variants rejected. Existing one-sided guard contract and historical minimum-live-safe audit retained. Current grammar/model research594 reused: syntax constraints do not establish semantics.',
})
panel = {row[0]: row for row in json.loads((prior / 'panel.json').read_text(encoding='utf-8'))}
rows = []
with (prior / 'responses.jsonl').open(encoding='utf-8') as stream:
    for line in stream:
        record = json.loads(line)
        if record['arm'] != 'original':
            continue
        choice = record['response']['choices'][0]
        assert choice['finish_reason'] == 'stop'
        raw = json.loads(choice['message']['content'])
        state = derive_semantic_effect_state(raw)
        class Guard:
            def _verify_semantic_effect_shape(self, _text):
                return state, raw['effect_count']
        decision = {'mode': 'conversation', 'conversation_kind': 'knowledge',
                    'operation': None, 'effect_operations': [], 'effect_count': 'zero'}
        case_id, text, expected = panel[record['case_id']]
        before = apply_conversation_effect_presentation(decision, text, Guard())
        after = candidate(decision, text, Guard())
        assert before['mode'] == after['mode'] == 'conversation'
        assert before['operation'] is None and after['operation'] is None
        assert before['effect_operations'] == after['effect_operations'] == []
        rows.append({'case_id': case_id, 'text': text, 'expected_request_type': expected,
                     'native': raw, 'state': state, 'before': before, 'after': after})
assert len(rows) == 16
changed_rows = [row for row in rows if row['before'] != row['after']]
write(private / 'replay.json', rows)
report = '\n\n'.join(
    f"## {row['case_id']}\n\nEntrada: {row['text']}\n\nNativo: {json.dumps(row['native'],ensure_ascii=False)}\n\nPresentación: {row['before']['conversation_kind']} → {row['after']['conversation_kind']}."
    for row in rows
)
(private / 'RESULT.md').write_text('# Reproducción de la proyección607\n\n' + report + '\n', encoding='utf-8')
result = {'utc': datetime.now(timezone.utc).isoformat(), 'cases': len(rows),
          'changed_cases': [row['case_id'] for row in changed_rows],
          'no_action_authority_changed': True, 'source_adopted': False,
          'final_prose_or_ui_credit': False,
          'private_hashes': {name: sha(private / name) for name in ['replay.json', 'RESULT.md']}}
write(out / 'RESULT.json', result)
write(out / 'PINS.json', {name: sha(out / name) for name in ['PREREG.json', 'RESULT.json']})
print(json.dumps(result, ensure_ascii=False))
