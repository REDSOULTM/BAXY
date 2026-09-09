"""Offline trace of the production chat guards on the exact responses296."""
from pathlib import Path
import copy
import json
import sys
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind import llm

out = root / 'artifacts/comprobaciones/C03/astra-guard297'
out.mkdir(exist_ok=False)
(out / 'PREREG.json').write_text(json.dumps({
    'utc': datetime.now(timezone.utc).isoformat(),
    'hypothesis': 'The request restatement guard counts the answered greeting in front of a distinct follow-up question.',
    'method': 'Replay exact responses296 through actual chat with predicate tracing; no new inference, effects, persistence or product mutation.',
    'criteria': 'Identify every true predicate and actual audit_reason before modifying source.'
}, indent=2)+'\n', encoding='utf-8')
names = ['visible_reply_denies_a_served_capability',
         'visible_reply_asserts_an_unread_machine_state',
         'visible_reply_restates_the_request',
         'visible_reply_invents_a_spanish_infinitive',
         'visible_reply_is_a_fixed_stall', '_reply_uses_opposite_language',
         'repeats_a_sent_instruction', '_shaped_conversation_answer_violates_contract']
originals = {name: getattr(llm, name) for name in names}
trace = []
for name, fn in originals.items():
    def traced(*args, _name=name, _fn=fn, **kwargs):
        result = _fn(*args, **kwargs)
        trace.append({'predicate': _name, 'reply': str(args[0]), 'result': result})
        return result
    setattr(llm, name, traced)
rows = json.loads((root/'artifacts/comprobaciones/C03/astra-memory296/RESULT.json').read_text(encoding='utf-8'))
results = []
try:
    for row in rows:
        trace.clear()
        class Runtime(llm.LlmRuntime):
            def __init__(self):
                self._gguf = row['posts'][0]['response']['model']
                self.posts = iter(row['posts'])
            def _post(self, payload):
                return copy.deepcopy(next(self.posts)['response'])
        runtime = Runtime()
        result = {'request': row['request']}
        try:
            result['answer'] = runtime.chat(row['request'], temperature=0.0,
                conversation_kind='knowledge', response_language='en' if row['request'].startswith('my ') else 'es')[0]
        except llm.ConversationReplyContractError as error:
            result['audit_reason'] = error.audit_reason
        result['trace'] = list(trace)
        results.append(result)
        print(json.dumps({**result, 'trace': [item for item in trace if item['result']]}, ensure_ascii=True))
finally:
    for name, fn in originals.items():
        setattr(llm, name, fn)
(out/'RESULT.json').write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
