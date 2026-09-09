"""Bounded native experiment: explicit no-effect decision, never executable."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import json
import os
import time
import urllib.request

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-abstain290'
out.mkdir(exist_ok=False)
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui288-private'
import sys
sys.path.insert(0,str(root/'src'))
from baxy_mind.llm import LlmRuntime
hello=json.loads((Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-app-catalog262-private/HELLO_CATALOGS.json').read_text(encoding='utf-8'))
descriptions={row['name']:{'description':row['description']} for row in hello['capabilities']}
prior=[json.loads(line) for line in (root/'artifacts/comprobaciones/C03/astra-native-scope/posts.jsonl').read_text(encoding='utf-8').splitlines()]
class Captured(Exception):
    pass
class Capture(LlmRuntime):
    def __init__(self):
        pass
    def _post(self,payload):
        self.payload=payload
        raise Captured()
cases=[]
for index,row in enumerate(prior):
    names=[tool['function']['name'].removeprefix('baxy_').replace('__','.') for tool in row['payload']['tools']]
    runtime=Capture()
    try:
        runtime._post_native_tool_selection(row['case'],names,descriptions,[])
    except Captured:
        pass
    calls=row['response']['choices'][0]['message'].get('tool_calls') or []
    expected=[call['function']['name'].removeprefix('baxy_').replace('__','.') for call in calls]
    cases.append({'case_id':f'scope-{index+1}','payload':runtime.payload,'expected':expected})
prereg={'utc':datetime.now(timezone.utc).isoformat(),
    'hypothesis':'UI288 selector emits long unneeded prose, truncates at256 then retries until timeout. Give no-effect a finite native decision alongside existing leaf choices, forcing a finished choice without executable authority.',
    'method':'Eleven previously validated native-scope controls (development/synthetic), rebuilt through current native selector with same historical subset and current authenticated Core descriptions; before and after have identical candidates/seed/temp/max_tokens on Qwen3.5. Expected sets preserve previously adjudicated native-scope evidence. Compare original auto with required plus internal no_effect_decision. Replace only contradictory no-function prose instructions with explicit no-effect decision. No production edit, no operations/effects, no truncated decision accepted.',
    'criteria':'No previously correct scope control may regress: genuine prohibition, translation, past event and knowledge remain no-effect; authorized clock and compound remain requested effects. No-effect combined with operations invalid. Original known compound/selection failures remain reported; this does not certify full C03.',
    'inheritance':'1_toolcalling.md:333-335 proposed permanent required + synthetic conversation outcome, distinct from rejected forcing a real effect after auto abstains. New trigger evidence: actual UI288 first native truncation. Native capability described in llama.cppb9980 function-calling documentation; required behavior checked on actual backend.',
    'source':'https://raw.githubusercontent.com/ggml-org/llama.cpp/b9980/docs/function-calling.md',
    'cases':cases}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
none='baxy_no_effect_decision'
descriptor={'type':'function','function':{'name':none,'description':'Internal classification outcome: no requested computer action or external read matches. Select this alone for conversation, stable knowledge, advice, negated requests, hypotheticals, past events or actions aimed at another device. This grants no operation authority and does not answer the person. Never combine it with another function.','parameters':{'type':'object','properties':{},'additionalProperties':False}}}
results=[]
for case in cases:
    for variant in ['before','explicit_no_effect']:
        payload=copy.deepcopy(case['payload'])
        if variant=='explicit_no_effect':
            payload['tool_choice']='required'
            payload['tools'].append(descriptor)
            prompt=payload['messages'][0]['content']
            prompt=prompt.replace('Use no function for conversation, stable knowledge, advice, negated requests, hypotheticals, past events, or actions aimed at another device.',f'Use {none} alone for conversation, stable knowledge, advice, negated requests, hypotheticals, past events, or actions aimed at another device.')
            prompt=prompt.replace('If no function applies, keep any text to one brief sentence; a separate conversational stage answers the person.',f'If no operation applies, select {none} alone; a separate conversational stage answers the person.')
            payload['messages'][0]['content']=prompt
        with urllib.request.urlopen('http://127.0.0.1:58635/slots',timeout=5) as response:
            assert not any(item['is_processing'] for item in json.load(response)), 'Backend busy, do not disturb owner input.'
        start=time.monotonic()
        request=urllib.request.Request('http://127.0.0.1:58635/v1/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
        record={'case_id':case['case_id'],'variant':variant,'expected':case['expected'],'payload':payload}
        try:
            with urllib.request.urlopen(request,timeout=90) as response:
                result=json.load(response)
            record['response']=result
            choice=result['choices'][0]
            calls=choice['message'].get('tool_calls') or []
            names=[call['function']['name'] for call in calls]
            record['names']=names
            record['finish']=choice['finish_reason']
            record['operations']=[name.removeprefix('baxy_').replace('__','.') for name in names if name!=none]
            record['valid']=choice['finish_reason']!='length' and not (none in names and names!=[none]) and (variant=='before' or bool(names))
        except Exception as error:
            record['error']=repr(error)
        record['seconds']=round(time.monotonic()-start,3)
        results.append(record)
        (out/'RESULT.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in record.items() if k not in ('payload','response')},ensure_ascii=True),flush=True)
