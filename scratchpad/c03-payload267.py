"""Capture the real compose payload before transport; no server or inference."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'src'))
from baxy_mind.llm import LlmRuntime, compose_visible_defect

out = root/'artifacts/comprobaciones/C03/astra-compose-provenance267'
wire = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui263-private/http-posts.jsonl'
rows = [json.loads(line) for line in wire.read_text(encoding='utf-8').splitlines()]
before = next(row['payload'] for row in rows if row['stage']=='request' and row['id']==9)
raw_reply = next(row['response']['choices'][0]['message']['content'] for row in rows
    if row['stage']=='response' and row['id']==9)
old_user = before['messages'][-1]['content']
old_situation = json.loads(next(line.split(': ',1)[1] for line in old_user.splitlines()
    if line.startswith('situation: ')))
prior = old_situation['previousResponse']
user_text = old_user.splitlines()[0].removeprefix('Texto original de la persona: ')
facts = {'situation':{'kind':'conversation','polarity':'success'}, 'context':prior}

class Captured(Exception):
    pass

class CaptureRuntime(LlmRuntime):
    def __init__(self):
        self._gguf = r'D:\BAXYRuntime\experiments\models\qwen35-4b-e87f1764\Qwen3.5-4B-Q4_K_M.gguf'
        self.payload = None

    def _post(self, payload):
        self.payload = copy.deepcopy(payload)
        raise Captured()

runtime = CaptureRuntime()
try:
    runtime.compose_user_message(user_text, 'conversation', facts)
except Captured:
    pass
after = runtime.payload
assert after is not None
assert before['messages'][0] == after['messages'][0]
assert {k:v for k,v in before.items() if k!='messages'} == {k:v for k,v in after.items() if k!='messages'}
assert [message['role'] for message in before['messages']] == [message['role'] for message in after['messages']]
new_lines = after['messages'][-1]['content'].splitlines()
new_situation = json.loads(next(line.split(': ',1)[1] for line in new_lines if line.startswith('situation: ')))
dialogue = json.loads(next(line.split(': ',1)[1] for line in new_lines
    if line.startswith('previous_dialogue_for_references_only: ')))
assert new_situation == {k:v for k,v in old_situation.items() if k!='previousResponse'}
assert dialogue == [{'role':'assistant','content':prior}]
def without_context_lines(content):
    return [line for line in content.splitlines() if not line.startswith(
        ('situation: ', 'previous_dialogue_for_references_only: '))]
assert without_context_lines(old_user) == without_context_lines(after['messages'][-1]['content'])
report = {'method':'Exact UI263 HTTP9 versus current compose assembly intercepted before HTTP; no inference.',
    'sourceSha256':hashlib.sha256((root/'src/baxy_mind/llm.py').read_bytes()).hexdigest(),
    'before':before, 'after':after, 'originalReply':raw_reply,
    'currentValidatorDefectForOriginalReply':compose_visible_defect(raw_reply,'conversation',user_text,facts),
    'newNativeReply':None, 'nativeComparisonPending':True}
target = out/'PAYLOAD_COMPARISON.json'
assert not target.exists()
target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'systemAndSettingsIdentical':True, 'onlyDifference':'prior dialogue moved outside evidence',
    'newSituation':new_situation, 'oldReplyStillAcceptedByPythonValidator':report['currentValidatorDefectForOriginalReply']=='',
    'nativeComparisonPending':True}, ensure_ascii=False))
