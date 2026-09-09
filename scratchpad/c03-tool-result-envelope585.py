"""Separate captured CPU evidence from the user request using native tool roles."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-native-compose-profile523.py').read_text(encoding='utf-8')
source = source.replace('astra-native-compose-profile523', 'astra-tool-result-envelope585').replace('C03-native-compose-profile523-private', 'C03-tool-result-envelope585-private')
start = source.index('ids='); end = source.index('manifest=Path(', start)
source = source[:start] + '''
capture=private.parent/'C03-cpu-actor-product582-private/http-posts.jsonl'
rows=[json.loads(s) for s in capture.read_text(encoding='utf-8-sig').splitlines()]
cases=[{'id':r['id'],'case':'582:'+str(r['id']),'payload':r['payload']} for r in rows if r['stage']=='request' and r['id'] in (4,9,10,12,14,20,21,23)]
assert len(cases)==8
def tool_envelope(payload):
    result=copy.deepcopy(payload)
    messages=result['messages'];assert len(messages)==2
    lines=messages[1]['content'].splitlines()
    fact_lines=[line for line in lines if line.startswith('situation: ')]
    assert len(fact_lines)==1
    fact_line=fact_lines[0];facts=json.loads(fact_line[11:])
    assert facts['operation']=='system.status' and facts['seen']['scope']=='cpu'
    messages[1]['content']='\\n'.join(line for line in lines if line!=fact_line)
    messages += [
        {'role':'assistant','content':'','tool_calls':[{'id':'captured_cpu','type':'function','function':{'name':'system.status','arguments':json.dumps({'scope':'cpu'})}}]},
        {'role':'tool','tool_call_id':'captured_cpu','name':'system.status','content':fact_line},
    ]
    return result
for case in cases:tool_envelope(case['payload'])
''' + source[end:]
start = source.index('profiles='); end = source.index("write(private/'cases.json',cases)", start)
source = source[:start] + '''
profiles=[('registered-user-envelope',{'seed':0}),('native-tool-envelope',{'seed':0})]
write(out/'PREREG.json',{'method':'Eight exact consumed CPU writer captures582. Keep identity, wording, observations, per-turn instructions, model, quantization, backend, sampling and max_tokens. Only move the original situation line into a native tool response preceded by a synthetic structural representation of the already-observed CPU read. That assistant tool call is an experimental envelope, not a claim it was generated in the historical turn. No handwritten assistant prose or execution. Native model comparison, not product or human acceptance.',
 'inheritance':'558/559 stateless instruction/field renaming failed.578–582 draft repair partly fixes ownership but produces bad Spanish.583 evaluates bounded reasoning9B. Current prompts put both personal question and machine evidence inside the same user message. Test role separation before adding another instruction or detector.',
 'sources':['https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/raw/main/tokenizer_config.json','https://github.com/QwenLM/Qwen3/blob/main/docs/source/framework/function_call.md'],
 'research':'Official exact2507 template accepts assistant tool_calls and tool-role results, wrapped as tool_response. No fabricated visible completion and no available-tools list requesting more execution. This probes representation, not a new catalog operation. Verify effective apply-template for both profiles.',
 'profile_rationale':'Registered greedy and seed0 held equal to isolate envelope. Not a model ranking or assumption defaults maximize quality. Any promising representation must next survive documented sampling and counterfactual values, then existing guards and actual product.',
 'criteria':'Same correct observed percentages/counts and language, no attribution to assistant process or ownership, fluent Spanish/English, EOS and nonempty final without tool calls. All failures retained.',
 'server_command':command,'manifest_sha256':manifest_sha,'capture_sha256':sha(capture),'profiles':profiles,'limits':{'gpu_stop_mib':3800,'free_ram_mib':768,'total_seconds':360,'request_seconds':60}})
''' + source[end:]
source = source.replace('case_index%3', 'case_index%2')
source = source.replace('if gpu.peak_mib>3800:', 'if gpu.peak_mib is not None and gpu.peak_mib>3800:')
source = source.replace("payload=copy.deepcopy(case['payload']);payload.update(settings)", """payload=copy.deepcopy(case['payload']);payload.update(settings)
            if profile=='native-tool-envelope':payload=tool_envelope(payload)
            if case_index==0:
                template_request=urllib.request.Request(url+'/apply-template',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(template_request,timeout=10) as response:write(private/('template-'+profile+'.json'),json.load(response))""")
source = source.replace('27 native writer requests collected', '16 tool-envelope writer requests collected')
exec(compile(source, __file__, 'exec'))
