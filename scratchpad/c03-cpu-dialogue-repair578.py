"""Compare explicit repair of the actual draft with prior stateless instructions."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-native-compose-profile523.py').read_text(encoding='utf-8')
source = source.replace('astra-native-compose-profile523', 'astra-cpu-dialogue-repair578').replace('C03-native-compose-profile523-private', 'C03-cpu-dialogue-repair578-private')
start = source.index('ids='); end = source.index('manifest=Path(', start)
source = source[:start] + '''
specs=[('C03-survey-resume543-private',17),('C03-survey-resume543-private',18),('C03-cpu-product575-private',6),('C03-cpu-product575-private',7)]
cases=[]
for folder,ident in specs:
    captured=[json.loads(line) for line in (private.parent/folder/'http-posts.jsonl').read_text(encoding='utf-8-sig').splitlines()]
    request=next(r for r in captured if r['id']==ident and r['stage']=='request')
    response=next(r for r in captured if r['id']==ident and r['stage']=='response')
    draft=response['response']['choices'][0]['message']['content']
    cases.append({'id':ident,'case':folder+':'+str(ident),'payload':request['payload'],'draft':draft})
''' + source[end:]
start = source.index('profiles='); end = source.index("write(private/'cases.json',cases)", start)
source = source[:start] + '''
profiles=[('baseline',{'seed':0}),('draft-feedback',{'seed':0})]
feedback='Review who the subject of your previous answer is. The observations describe this computer; they do not measure the assistant as a process or hardware owned by the assistant. Correct only the subject if needed, keep all observed values and the original question language. Return only the revised answer.'
write(out/'PREREG.json',{'method':'Four consumed actual writer captures: CPU usage ES failure/EN control, CPU model+core ES ownership failure575 and EN core control. Compare exact initial writer with a second dialogue turn carrying its actual captured draft plus explicit subject feedback. Preserve original facts, request, model and sampling. This tests draft-aware correction, not another stateless naming/instruction sweep.',
 'inheritance':'558/559 stateless field rename/ownership instruction did not fix the failure. Current compose_visible_defect has wrong_actor only for capabilities/connectivity, so CPU first person passes without repair. Existing third generic repair also asks First person; no claim this caused the initial native543/575 failures (their system prompts do not contain it). No guard/source change until native evidence supports repair.',
 'criteria':'ES must stop saying Estoy usando/Tengo for computer observations, with values unchanged. Correct EN controls must preserve language, subject and facts. Native success alone is not adoption; requires fact-scoped guard, bounded existing retry path, owner tests and actual product regression. No global default model ranking, new training or survey credit.',
 'feedback':feedback,'profiles':profiles,'case_count':len(cases),'server_command':command,'manifest_sha256':manifest_sha,
 'limits':{'gpu_stop_mib':3800,'free_ram_mib':768,'total_seconds':360,'request_seconds':60}})
''' + source[end:]
source = source.replace("payload=copy.deepcopy(case['payload']);payload.update(settings)", "payload=copy.deepcopy(case['payload']);payload.update(settings)\n            if profile=='draft-feedback':payload['messages'] += [{'role':'assistant','content':case['draft']},{'role':'user','content':feedback}]")
source = source.replace('case_index%3', 'case_index%2')
source = source.replace('if gpu.peak_mib>3800:', 'if gpu.peak_mib is not None and gpu.peak_mib>3800:')
source = source.replace('if time.monotonic()-start>360:', "if gpu.peak_mib is None and time.monotonic()-start>10:violations.append('missing_gpu_telemetry')\n        if time.monotonic()-start>360:")
source = source.replace('27 native writer requests collected', '8 draft-repair comparisons collected')
exec(compile(source, __file__, 'exec'))
