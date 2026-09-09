"""Preserve the measurement owner in the numeric field name, not a reply template."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-native-compose-profile523.py').read_text(encoding='utf-8')
source=source.replace('astra-native-compose-profile523','astra-native-cpu-owner558').replace('C03-native-compose-profile523-private','C03-native-cpu-owner558-private')
start=source.index('ids=');end=source.index('manifest=Path(',start)
source=source[:start]+'''cases=[]
for campaign,ids in [('C03-survey-readonly541-private',{26,27}),('C03-survey-resume543-private',{17,18})]:
    for line in (private.parent/campaign/'http-posts.jsonl').read_text(encoding='utf-8-sig').splitlines():
        row=json.loads(line)
        if row['stage']=='request' and row['id'] in ids:
            cases.append({'id':row['id'],'case':campaign+':'+str(row['id']),'payload':row['payload']})
assert len(cases)==4
''' +source[end:]
start=source.index('profiles=');end=source.index("write(private/'cases.json',cases)",start)
source=source[:start]+'''profiles=[('baseline',{'seed':0}),('measurement-owner',{'seed':0})]
def treatment(payload):
    def rename(value):
        if isinstance(value,list):
            for item in value:rename(item)
        if not isinstance(value,dict):return
        cpu=value.get('cpu')
        if isinstance(cpu,dict) and 'usagePercent' in cpu:
            cpu['wholeComputerUsagePercent']=cpu.pop('usagePercent')
        for item in value.values():rename(item)
    for message in payload['messages']:
        lines=message['content'].splitlines()
        for i,line in enumerate(lines):
            if line.startswith('situation: '):
                facts=json.loads(line[11:]);rename(facts)
                lines[i]='situation: '+json.dumps(facts,ensure_ascii=False)
        message['content']='\\n'.join(lines)
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),
 'method':'Four exact native CPU captures541/543, two arms. Only rename the CPU usagePercent evidence field to wholeComputerUsagePercent, keeping its numeric value, logical count, model, failures, request and prompts unchanged. The provider metric is whole-machine processor usage, not BAXY process usage. No post-generation correction, fixed visible phrase or extra metadata layer. Diagnostic, not source adoption.',
 'cause':'Spanish user first person is echoed by the assistant as Estoy usando23.75%. The sparse usagePercent field does not carry measurement ownership explicitly. This tests ownership semantics rather than another global voice/prompt rewrite.556 proves the problem remains after independent contextual-answer repair.',
 'inheritance':'CPU provider ReadCpu derives usage from the whole-system probe; Gemma557 fixes subject but trades other factual failures, not promoted.552/553 numeric unit enrichment rejected for unrelated factual regressions. This changes neither physical units nor model.',
 'criteria':'Spanish and English usage must refer to the computer/person, never BAXY consumption; preserve exact observations and no model/count regression. Processor identity/count requests are negative controls: do not call16logical processors16physical cores. Need product/regression before source adoption.',
 'manifest_sha256':manifest_sha,'server_command':command,'case_count':len(cases),'limits':{'gpu_stop_mib':3800,'free_ram_mib':768,'total_seconds':360,'request_seconds':60}})
''' +source[end:]
source=source.replace('case_index%3','case_index%2')
source=source.replace("payload=copy.deepcopy(case['payload']);payload.update(settings)","payload=copy.deepcopy(case['payload']);payload.update(settings)\n            if profile=='measurement-owner':treatment(payload)")
source=source.replace('if gpu.peak_mib>3800:','if gpu.peak_mib is not None and gpu.peak_mib>3800:')
source=source.replace('if time.monotonic()-start>360:',"if gpu.peak_mib is None and time.monotonic()-start>10:violations.append('missing_gpu_telemetry')\n        if time.monotonic()-start>360:")
source=source.replace('27 native writer requests collected','8 CPU native replies collected')
exec(compile(source,__file__,'exec'))
