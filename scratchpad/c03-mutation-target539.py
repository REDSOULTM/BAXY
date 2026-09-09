"""Isolate the verified mutation selector discarded by the public projection."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-native-compose-profile523.py').read_text(encoding='utf-8')
source = source.replace('astra-native-compose-profile523','astra-mutation-target539')
source = source.replace('C03-native-compose-profile523-private','C03-mutation-target539-private')
start = source.index('ids=')
end = source.index('manifest=Path',start)
source = source[:start] + '''rows=list(map(json.loads,(previous/'http-posts.jsonl').open(encoding='utf-8-sig')))
original=next(r['payload'] for r in rows if r['stage']=='request' and r['id']==4)
cases=[]
for label in ['name','favorite color','pet name','delivery preference']:
    cases.append({'id':4,'case':label,'payload':original,'selector':label})
''' + source[end:]
start = source.index('profiles=')
end = source.index("write(private/'cases.json',cases)",start)
source = source[:start] + '''profiles=[('baseline',{'seed':0}),('verified-selector',{'seed':0})]
def treatment(payload,selector):
    message=payload['messages'][1]
    lines=message['content'].splitlines()
    for i,line in enumerate(lines):
        if line.startswith('situation: '):
            facts=json.loads(line[len('situation: '):])
            facts['seen']['label']=selector
            lines[i]='situation: '+json.dumps(facts,ensure_ascii=False)
    message['content']='\\n'.join(lines)
write(out/'PREREG.json',{
 'utc':datetime.now(timezone.utc).isoformat(),
 'method':'Native ablation of a concrete projection loss: Core MemoryMutationWireResult contains verified selector; MemoryOperationResponseProjection.TryProjectMutation validates and discards it. Capture521 save result receives only confirm and bookkeeping flags. Add seen.label using that selector, keep every existing flag, original prompt, shape and request. Four labels include actual synthetic name and three counterfactual verified receipts; no claim those counterfactual records were really saved.',
 'criteria':'Describe the actual saved target naturally without claiming its value or subject. Do not recite false corrections/sensitivity or invent effects. If no gain, reject; do not adopt target propagation solely on a plausible causal explanation.',
 'sources':['src/Baxy.Core/Operations/MemoryHandlers.cs:336','src/Baxy.App/MemoryOperationResponseProjection.cs:126'],
 'inheritance':'537 descriptors and538 system-contract changes failed and are not applied. Return to original source520 prompt. 515 removed false flags without target grounding and failed; this keeps those flags and tests only lost target.',
 'authorization':'AUTORIZACION_DUENO_536.md; development, not blind acceptance.',
 'manifest_sha256':manifest_sha,'capture_sha256':sha(previous/'http-posts.jsonl'),
 'server_command':command,'profiles':profiles,'cases':[c['case'] for c in cases],
 'limits':{'gpu_stop_mib':3800,'free_ram_mib':768,'total_seconds':360,'request_seconds':60}})
''' + source[end:]
source = source.replace('case_index%3','case_index%2')
source = source.replace("payload=copy.deepcopy(case['payload']);payload.update(settings)","payload=copy.deepcopy(case['payload']);payload.update(settings)\n            if profile=='verified-selector':treatment(payload,case['selector'])")
source = source.replace('if gpu.peak_mib>3800:','if gpu.peak_mib is not None and gpu.peak_mib>3800:')
source = source.replace('if time.monotonic()-start>360:',"if gpu.peak_mib is None and time.monotonic()-start>10:violations.append('missing_gpu_telemetry')\n        if time.monotonic()-start>360:")
source = source.replace('27 native writer requests collected','8 native writer requests collected')
exec(compile(source,__file__,'exec'))
