"""Registered2507: restore actual parameter contracts on same native controls292."""
from pathlib import Path
from datetime import datetime,timezone
import copy
import json
import os
import time
import urllib.request

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-schemas294'
out.mkdir(exist_ok=False)
prior=json.loads((root/'artifacts/comprobaciones/C03/astra-selector-model292/RESULT.json').read_text(encoding='utf-8'))
hello=json.loads((Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-app-catalog262-private/HELLO_CATALOGS.json').read_text(encoding='utf-8'))
schemas={row['name']:row['argumentsSchema'] for row in hello['capabilities']}
prereg={'utc':datetime.now(timezone.utc).isoformat(),'method':'Same18 native AUTO payloads292, now existing registered2507 in real desktop293 backend. Only restore exact Core parameter schemas and remove contradictory argument-defer sentence. No candidate/order/template/sampling/limit change. No operation execution, no source adoption.',
    'hypothesis':'Empty schemas discard named-application vs empty foreground selector distinction.292 exposed only win07 regression against Qwen3.5;279 tested full schemas on different model and priority-adjusted candidates, not this comparison.',
    'criteria':'window.application.status for win07 and no loss of other17 controls; inspect arguments separately, no model-proposed ID becomes authority. UI293 still asks unnecessary Paris clarification; no claim that native improvement fixes all product layers.',
    'inheritance':'astra-schema279/PREREG.json and RESULTS; INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md. Qwen official function calling documents schemas; exact2507 behavior measured here.',
    'source':'https://qwen.readthedocs.io/en/stable/framework/function_call.html',
    'cases':[row['case_id'] for row in prior]}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
removed='Function arguments are extracted and validated in a later stage, so the declared functions take no arguments here. '
results=[]
for row in prior:
    payload=copy.deepcopy(row['payload'])
    assert removed in payload['messages'][0]['content']
    payload['messages'][0]['content']=payload['messages'][0]['content'].replace(removed,'')
    for tool in payload['tools']:
        operation=tool['function']['name'].removeprefix('baxy_').replace('__','.')
        tool['function']['parameters']=copy.deepcopy(schemas[operation])
    with urllib.request.urlopen('http://127.0.0.1:63490/slots',timeout=5) as response:
        assert not any(item['is_processing'] for item in json.load(response))
    req=urllib.request.Request('http://127.0.0.1:63490/v1/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
    started=time.monotonic()
    with urllib.request.urlopen(req,timeout=90) as response:
        response=json.load(response)
    choice=response['choices'][0]
    calls=choice['message'].get('tool_calls') or []
    result={'case_id':row['case_id'],'expected':row['expected'],'operations':[call['function']['name'].removeprefix('baxy_').replace('__','.') for call in calls],'calls':calls,'finish':choice['finish_reason'],'seconds':round(time.monotonic()-started,3),'payload':payload,'response':response}
    results.append(result)
    (out/'RESULT.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('payload','response')},ensure_ascii=True),flush=True)
