"""Isolate derived binary units in numeric evidence; no source or prompt change."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-native-compose-profile523.py').read_text(encoding='utf-8')
source=source.replace('astra-native-compose-profile523','astra-native-quantities552').replace('C03-native-compose-profile523-private','C03-native-quantities552-private')
start=source.index('ids=')
end=source.index("manifest=Path(",start)
source=source[:start]+'''cases=[]
captures=[]
for campaign in ('C03-survey-readonly541-private','C03-survey-resume543-private','C03-coordinate-product546-private'):
    path=private.parent/campaign/'http-posts.jsonl'
    captures.append({'path':str(path),'sha256':sha(path)})
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        row=json.loads(line)
        messages=row.get('payload',{}).get('messages',[])
        if row['stage']!='request' or not messages or not messages[0]['content'].startswith('Eres BAXY, un compañero.'):
            continue
        content=messages[-1]['content']
        if not any(term in content for term in ('dedicatedVideoMemoryBytes','availableBytes','totalBytes')):continue
        cases.append({'id':row['id'],'case':campaign+':'+str(row['id']),'payload':row['payload']})
assert cases and len(cases)<=16
''' +source[end:]
start=source.index('profiles=')
end=source.index("write(private/'cases.json',cases)",start)
source=source[:start]+'''profiles=[('baseline',{'seed':0}),('derived-GiB',{'seed':0})]
def enrich(value):
    if isinstance(value,list):
        for child in value:enrich(child)
    if not isinstance(value,dict):return
    for key,item in list(value.items()):
        enrich(item)
        if key.endswith('Bytes') and isinstance(item,int) and not isinstance(item,bool) and item>=0:
            value[key[:-5]+'GiB']=round(item/(2**30),2)
def treatment(payload):
    for message in payload['messages']:
        lines=message['content'].splitlines()
        for i,line in enumerate(lines):
            if line.startswith('situation: '):
                facts=json.loads(line[11:]);enrich(facts)
                lines[i]='situation: '+json.dumps(facts,ensure_ascii=False)
        message['content']='\\n'.join(lines)
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),
 'method':'Replay all native numeric writers with byte-capacity fields from541/543/546, baseline versus derived GiB siblings rounded to2decimals. Keep every original raw byte value, observation, prompt, subject, sampler and model. One intervention: compute physical units outside language generation. No fixed visible replies, no removal of shared memory limits or adapter entries. This is a native diagnostic, not current product behavior.',
 'cause':'Observed dedicated GPU bytes misreported as8GB, and RAM/disk conversions inconsistently rounded. Test whether explicit physical quantities resolve numeric claims before changing source. Do not treat a memory limit as currently used RAM; do not combine adapters.',
 'criteria':'Correct dedicated versus shared capacity, faithful units/rounded values, all requested fields, appropriate language and no new claims. Report every output, not only promising pairs. CPU subject and closing metanarration are separate open defects.',
 'authorization':'AUTORIZACION_DUENO_536.md; owner development text stays on loopback.',
 'captures':captures,'manifest_sha256':manifest_sha,'server_command':command,'case_count':len(cases),
 'limits':{'gpu_stop_mib':3800,'free_ram_mib':768,'total_seconds':360,'request_seconds':60}})
''' +source[end:]
source=source.replace('case_index%3','case_index%2')
source=source.replace("payload=copy.deepcopy(case['payload']);payload.update(settings)","payload=copy.deepcopy(case['payload']);payload.update(settings)\n            if profile=='derived-GiB':treatment(payload)")
source=source.replace('if gpu.peak_mib>3800:','if gpu.peak_mib is not None and gpu.peak_mib>3800:')
source=source.replace('if time.monotonic()-start>360:',"if gpu.peak_mib is None and time.monotonic()-start>10:violations.append('missing_gpu_telemetry')\n        if time.monotonic()-start>360:")
source=source.replace('27 native writer requests collected','Numeric native pairs collected')
exec(compile(source,__file__,'exec'))
