"""Locate false conversational refusal using frozen owner dialogue and first payload."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import copy
import json
import os
import sys
import urllib.request

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'src'))
from baxy_mind import llm
out = root/'artifacts/comprobaciones/C03/astra-chat286'
out.mkdir(exist_ok=False)
transcript = json.loads((Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-owner264-heap280/TRANSCRIPT282.json').read_text(encoding='utf-8'))
rows = transcript['messages'] if isinstance(transcript, dict) else transcript
row = next(item for item in rows if item['index'] == 5)
history = [{'role':'user' if item['isUser'] else 'assistant','content':item['body']} for item in rows if item['index'] < 5]
class Captured(Exception):
    pass
class Capture(llm.LlmRuntime):
    def __init__(self):
        self._gguf = r'D:\BAXYRuntime\experiments\models\qwen35-4b-e87f1764\Qwen3.5-4B-Q4_K_M.gguf'
    def _post(self,payload):
        self.payload = copy.deepcopy(payload)
        raise Captured()
runtime=Capture()
try:
    runtime.chat(row['body'],history,temperature=0.0,conversation_kind='knowledge',response_language='es')
except Captured:
    pass
base=runtime.payload
prefix=[]
for item in base['messages']:
    if item['role']!='system':
        break
    prefix.append(item['content'])
base['messages']=[{'role':'system','content':'\n\n'.join(prefix)},*base['messages'][len(prefix):]]
clause='Solo existen las herramientas del catálogo activo. Las acciones se deciden en otra etapa: en este turno conversacional no llames herramientas ni simules haberlas ejecutado. '
assert clause in base['messages'][0]['content']
prereg={'utc':datetime.now(timezone.utc).isoformat(),'request':row['body'],
    'method':'Corrected native payload: production caller __main__.py:6432 fixes temperature=0.0;285 incorrectly used chat default0.7. Other settings match285. First payload of chat API, owner collection index5 and preceding visible history. 2x2: retain/remove only stage-tool instruction; retain/remove prior dialogue. Fifth identity-only baseline, same sampler/limits. No source changes, no tool execution. Captures first raw reply before publication guards.',
    'hypothesis':'Unsupported refusals may be caused by stage implementation instructions or earlier false assistant refusals. Locate contribution before adopting any prompt/history change.',
    'criteria':'Answer request with actual stable places to visit; no invented current hours, no request for unnecessary details, no false inability or denial based on PC scope.',
    'inheritance':'Carter_v3 CODEX_REVIEW_minimum_live_safe_tool_policy_round documents action/chat boundary errors; INVESTIGACION_MODELO_C03 documents exactQwen3.5 template and prior layer studies. This is a new owner failure, not a generic prompt sweep.'}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
variants=[]
for keep_stage,keep_history in [(True,True),(False,True),(True,False),(False,False)]:
    payload=copy.deepcopy(base)
    if not keep_stage:
        payload['messages'][0]['content']=payload['messages'][0]['content'].replace(clause,'')
    if not keep_history:
        payload['messages']=[payload['messages'][0],payload['messages'][-1]]
    variants.append((f'stage{int(keep_stage)}_history{int(keep_history)}',payload))
bare=copy.deepcopy(base)
bare['messages']=[{'role':'system','content':'Eres BAXY, un compañero que vive en el PC. Eres un él. Tuteas.'},base['messages'][-1]]
variants.append(('identity_only',bare))
results=[]
for name,payload in variants:
    with urllib.request.urlopen('http://127.0.0.1:57485/slots',timeout=5) as response:
        assert not any(item['is_processing'] for item in json.load(response))
    req=urllib.request.Request('http://127.0.0.1:57485/v1/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=90) as response:
            result=json.load(response)
        record={'variant':name,'payload':payload,'response':result}
        print(json.dumps({'variant':name,'answer':result['choices'][0]['message'],'finish':result['choices'][0]['finish_reason']},ensure_ascii=True),flush=True)
    except Exception as error:
        record={'variant':name,'payload':payload,'error':repr(error)}
        print(json.dumps({'variant':name,'error':repr(error)}),flush=True)
    results.append(record)
    (out/'RESULT.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

