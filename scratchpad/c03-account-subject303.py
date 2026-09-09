"""Compare preservation of the semantic subject of a verified account read."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import json
import os
import sys
import urllib.request

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from baxy_mind import llm

out=root/'artifacts/comprobaciones/C03/astra-account-subject303'
out.mkdir(exist_ok=False)
audit=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui293-private/compose-audit.jsonl'
row=next(json.loads(line) for line in audit.read_text(encoding='utf-8').splitlines() if json.loads(line).get('trace')=='t2')
observed=json.loads(row['situation'])
cases=[]
for request,name,domain in [('quien soy','usuario','REDNOTE'),('who am I','usuario','REDNOTE'),
    ('cuál es mi usuario','ana.pérez','WORKGROUP'),('what is my Windows account','dev-user2','LAB')]:
    situation=copy.deepcopy(observed)
    situation['observed'].update(userName=name,domain=domain,qualifiedName=domain+'\\'+name)
    cases.append({'request':request,'facts':{'situation':situation}})
prereg={'utc':datetime.now(timezone.utc).isoformat(),
    'previous_goal_turn':'progress: adopted298/299, verified greeting through product301, Fast299green and UI302reopened. Entire C03 still active.',
    'hypothesis':'Projection drops the operation identity and leaves only seen.userName. A subject read from the typed system.identity result can distinguish the Windows account from the speaking assistant without a forbidden-phrase guard.',
    'method':'Same actual293 verified situation, one literal owner request plus three technical ES/EN/name controls. Native registered2507, unchanged source299 compose API/prompt/sampling/guards. Compare existing projection and addition of semantic subject only. No operations, persistence or promotion. Minimal facts replay, not exact UI293 HTTP payload (not captured).',
    'criteria':'Attribute observed username to Windows account/person, never speaking assistant or saved personal-name memory; retain exact distinct names and accents. Require a reproduced baseline defect plus corrected meaning across controls before adoption.',
    'inheritance':'Carter_v2 LLM_CONTEXT_MEMORY_REPORT.md user-reference provenance; current account284 preserves the name but UI293 demonstrates role failure. Existing model/template research remains applicable.',
    'cases':cases,'subject':"the person's Windows account"}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
class Runtime(llm.LlmRuntime):
    def __init__(self):
        self._gguf=r'D:\BAXYRuntime\experiments\models\qwen3-4b-instruct-2507-a06e946b\Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
        self.posts=[]
    def _post(self,payload):
        payload=copy.deepcopy(payload)
        prefix=[]
        for message in payload['messages']:
            if message['role']!='system':
                break
            prefix.append(message['content'])
        if len(prefix)>1:
            payload['messages']=[{'role':'system','content':'\n\n'.join(prefix)},*payload['messages'][len(prefix):]]
        with urllib.request.urlopen('http://127.0.0.1:58916/slots',timeout=5) as response:
            assert not any(item['is_processing'] for item in json.load(response)), 'Owner/backend busy'
        request=urllib.request.Request('http://127.0.0.1:58916/v1/chat/completions',
            data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=90) as response:
            response=json.load(response)
        self.posts.append({'payload':payload,'response':response})
        return response
original=llm._compose_situation_payload
def with_subject(situation,*args,**kwargs):
    payload=original(situation,*args,**kwargs)
    if situation.get('operation')=='system.identity' and 'seen' in payload:
        payload['subject']=prereg['subject']
    return payload
results=[]
try:
    for case in cases:
        for variant,projection in [('before',original),('subject',with_subject)]:
            llm._compose_situation_payload=projection
            runtime=Runtime()
            result={'request':case['request'],'variant':variant}
            try:
                result['answer']=runtime.compose_user_message(case['request'],'status',case['facts'])
            except Exception as error:
                result['error']=repr(error)
            result['posts']=runtime.posts
            results.append(result)
            (out/'RESULT.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({k:v for k,v in result.items() if k!='posts'},ensure_ascii=True),flush=True)
finally:
    llm._compose_situation_payload=original
