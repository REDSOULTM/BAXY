"""Paired native test of typed quantities across the RAM/disk/GPU batch."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix=source[:source.index("history = [{'role'")]
prefix=prefix.replace('astra-native-subject612','astra-native-measurements690').replace('C03-native-subject612-private','C03-native-measurements690-private')
prefix=prefix.replace('out.mkdir(exist_ok=False)','out.mkdir(exist_ok=True)\nassert not (out/"PROCESS.json").exists() and not (out/"PREREG.json").exists()')
prefix=prefix.replace('private.mkdir(exist_ok=False)','private.mkdir(exist_ok=True)\nassert not (private/"responses.jsonl").exists()')
exec(compile(prefix,__file__,'exec'))
import baxy_mind.llm as llm_module
from baxy_mind.request_reading import read_request

def quantity(value, unit='GiB'):
    assert type(value) in {int,float} and value >= 0
    return {'value':round(value/(2**30) if unit=='GiB' else value,4),'unit':unit}

def project_quantities(payload):
    result=copy.deepcopy(payload)
    def visit(node):
        if isinstance(node,list):
            for item in node: visit(item)
        elif isinstance(node,dict):
            for item in list(node.values()): visit(item)
            if node.get('operation')!='system.status' or not isinstance(node.get('seen'),dict): return
            seen=node['seen']
            for name in ['memory','disk']:
                values=seen.get(name)
                if not isinstance(values,dict): continue
                total,available=values.get('totalBytes'),values.get('availableBytes')
                if type(total) is int and type(available) is int and 0<=available<=total:
                    replacement={k:v for k,v in values.items() if k not in {'totalBytes','availableBytes'}}
                    replacement.update(total_usable=quantity(total),available=quantity(available),used=quantity(total-available))
                    seen[name]=replacement
            for adapter in seen.get('adapters',[]):
                if not isinstance(adapter,dict): continue
                total=adapter.get('dedicatedVideoMemoryBytes');used=adapter.get('dedicatedMemoryUsageBytes')
                names={'dedicatedVideoMemoryBytes':'dedicated_vram_capacity','dedicatedMemoryUsageBytes':'dedicated_vram_used',
                    'sharedSystemMemoryLimitBytes':'shared_system_ram_limit','sharedMemoryUsageBytes':'shared_system_ram_used',
                    'dedicatedSystemMemoryBytes':'dedicated_system_ram_capacity'}
                for old,new in names.items():
                    value=adapter.get(old)
                    if type(value) is int and value>=0: adapter[new]=quantity(adapter.pop(old))
                engine=adapter.get('usagePercent')
                if type(engine) in {int,float} and 0<=engine<=100:
                    adapter['gpu_engine_utilization']=quantity(adapter.pop('usagePercent'),'%')
                if type(total) is int and total>0 and type(used) is int and 0<=used<=total:
                    adapter['dedicated_vram_utilization']=quantity(100*used/total,'%')
    visit(result)
    return result

class Captured(Exception): pass
class Builder(LlmRuntime):
    def __init__(self): self._gguf=config['gguf']
    def _post(self,payload,**kwargs):
        self.payload=copy.deepcopy(payload)
        raise Captured()

previous=private.parent/'C03-status-batch689-private'
registry=json.loads((previous/'panel.json').read_text(encoding='utf-8'))
with (previous/'compose-audit.jsonl').open(encoding='utf-8-sig') as stream:
    audit=list(map(json.loads,stream))
cases=[]
for i,row in enumerate(registry,1):
    if row['group'] not in {'memory','disk','gpu'}: continue
    first=next((r for r in audit if r.get('trace')==f't{i}' and r.get('stage')=='first'),None)
    if first is None: continue
    cases.append({'case_id':row['case_id'],'text':row['text'],'group':row['group'],'criterion':row['criterion'],
        'projected':copy.deepcopy(first['payload']),'language':first['language'],
        'original_draft':first['draft'],'origin':'reused measured product689'})
assert len(cases)==24
def synthetic(original,case_id,group,text,scope,measurement):
    case=copy.deepcopy(next(r for r in cases if r['case_id']==original))
    case.update(case_id=case_id,group=group,text=text,original_draft=None,origin='explicit synthetic name/value generalization',
        language=read_request(text).language,
        projected={'operation':'system.status','seen':{'scope':scope,**measurement,'failures':[]}})
    cases.append(case)
synthetic('H0342','memory-used32','memory','How much RAM is in use?','memory',{'memory':{'totalBytes':32*2**30,'availableBytes':24*2**30}})
synthetic('H0342','memory-full16','memory','¿Cuánta RAM libre queda y cuánta está usada?','memory',{'memory':{'totalBytes':16*2**30,'availableBytes':0}})
synthetic('H0384','disk-used1024','disk','How much disk space is used?','disk',{'disk':{'totalBytes':1024*2**30,'availableBytes':int(123.5*2**30)}})
synthetic('gpu-usage-es','gpu-engine92-memory12','gpu','¿Qué porcentaje de VRAM está ocupado?','gpu_usage',{'adapters':[{'name':'Atlas GPU','dedicatedVideoMemoryBytes':8*2**30,'dedicatedMemoryUsageBytes':1*2**30,'usagePercent':92}]})
synthetic('gpu-identity-en','gpu-dedicated4-shared64','gpu','Which GPU is installed and how much dedicated VRAM does it have?','gpu_identity',{'adapters':[{'name':'Órbita GPU','dedicatedVideoMemoryBytes':4*2**30,'sharedSystemMemoryLimitBytes':64*2**30}]})
synthetic('gpu-usage-es','gpu-usage-unmeasured','gpu','¿Cuánta VRAM se está usando?','gpu_usage',{'adapters':[{'name':'Nimbus GPU','dedicatedVideoMemoryBytes':12*2**30}]})
assert len(cases)==30
panel=[]
for row in cases:
    client=Builder()
    # The audit's raw situation string is capped at2048chars; its projected
    # payload remains whole. Inject that recorded projection only in this
    # isolated first-request builder. Never reconstruct missing raw bytes.
    original_projection=llm_module._compose_situation_payload
    llm_module._compose_situation_payload=lambda *args,**kwargs:copy.deepcopy(row['projected'])
    reading=read_request(row['text']).to_payload()
    reading['language']=row['language']
    envelope={'kind':row['projected'].get('kind','operation'),'operation':'system.status','polarity':'success','verified':True,'succeeded':True}
    if 'completedStepsInOrder' in row['projected']: envelope['cause']='mission_completed'
    try:
        try: client.compose_user_message(row['text'],'status',{'situation':envelope,'reading':reading})
        except Captured: control=client.payload
        else: raise AssertionError('No captured first request')
    finally:
        llm_module._compose_situation_payload=original_projection
    projected=copy.deepcopy(control)
    changed=0
    for message in projected['messages']:
        if message['role']!='user' or 'situation: ' not in message['content']: continue
        before,rest=message['content'].split('situation: ',1)
        facts,end=json.JSONDecoder().raw_decode(rest)
        assert facts==row['projected']
        altered=project_quantities(facts)
        assert altered!=facts
        message['content']=before+'situation: '+json.dumps(altered,ensure_ascii=False)+rest[end:]
        changed+=1
    assert changed==1
    for arm,payload in [('current_bytes',control),('typed_quantities',projected)]:
        panel.append({**row,'arm':arm,'payload':payload})
assert len(panel)==60 and psutil.virtual_memory().available>=1800*2**20
write(private/'panel.json',panel)
runner=source[source.index('command = json.loads'):]
start=runner.index("write(out / 'PREREG.json', {");end=runner.index("log = (private / 'launch.log')",start)
runner=runner[:start]+'''write(out/'PREREG.json',{
    'utc':datetime.now(timezone.utc).isoformat(),'cases':30,'arms':2,'calls':60,
    'method':'24 numeric turns from batch689 using complete recorded projected payloads and language, plus six synthetic name/value controls. The raw audit situation string is clipped2048chars; this does not prove clipped model input and is not parsed as full evidence. Pair current byte fields against typed GiB/percent quantities derived only from them. Isolated actual compositor first-request builder temporarily receives the recorded projection; both arms share the same system/user request/language/sampling/max tokens. No product source edit, validator, retry or replacement final. Compare controls to recorded689 drafts before attribution.',
    'criteria':'Correct total/available/used RAM and disk; dedicated VRAM is separate from shared system RAM and engine utilization. Preserve unknown usage as unknown. Values/units must match inputs, all requested quantities answered, no invented device. Judge every draft, not only former failures. No survey coverage from this experiment.',
    'inheritance':'542 fixed video-memory scope but explicitly left wrong8GB prose.689 reproduces dedicated/shared and utilization confusion, arithmetic omission and usable/installed uncertainty across a50-requirement batch. Source686 remains published; this only tests a common measurement projection hypothesis.',
    'profile':'Registered Qwen2507/b9980 first-compositor settings held fixed for causal comparison; no global optimality or model exclusion claim.',
    'command':command,'manifest_sha256':manifest_sha,'model_sha256':sha(config['gguf']),'server_sha256':sha(command[0]),
    'source_sha256':sha(root/'src/baxy_mind/llm.py'),'panel_sha256':sha(private/'panel.json'),
    'source_modified':False,'source_adopted':False,'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240}})
''' + runner[end:]
runner=runner.replace('Collected40 native subject-attribution drafts; adjudication pending.','Collected60 paired numeric drafts; adjudication pending.')
exec(compile(runner,__file__,'exec'))
