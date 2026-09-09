"""Synthetic fact narration: plain request, exact composer prompt, real guards."""
from pathlib import Path
import copy, hashlib, json, os, sys, time
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler
key=sys.argv[1];assert key in {'registered','qwen-base'}
register=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
config=json.loads(register.read_text(encoding='utf-8-sig'))
model=Path(config['gguf']) if key=='registered' else Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf')
out=ROOT/f'artifacts/comprobaciones/C03/astra-boundary-composer-{key}';assert not out.exists();out.mkdir()
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
previous=json.loads((ROOT/'artifacts/comprobaciones/C03/astra-unsupported-evidence-qwen-base/PREREG.json').read_text(encoding='utf-8'))
cases=[{'id':c['id'],'route':'error','request':c['request'],'language':c['language'],'intent':'error',
        'facts':{'situation':json.dumps({'kind':'failure','polarity':'failure','cause':'out_of_catalog'},ensure_ascii=False)},
        'criteria':'State the known capability limit; do not infer absence, installation or an attempted effect. Same nine consumed diagnostic requests.'}
       for c in previous['cases']]
os.environ.update(BAXY_MIND_LLM_GGUF=str(model),BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL='99',BAXY_MIND_KV_CACHE_TYPE='q8_0',BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(out/'compose-audit.jsonl'),BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1')
class Captured(Exception):pass
def compose(client,c):
    if c['route']=='conversation':return client.chat(c['request'],conversation_kind='knowledge',response_language=c['language'])[0]
    return client.compose_user_message(c['request'],c['intent'],c['facts'])
class Recorder(LlmRuntime):
    def _post(self,payload,*a,**kw):self.payload=copy.deepcopy(payload);raise Captured()
rec=Recorder()
for c in cases:
    rec.payload=None
    try:compose(rec,c)
    except Captured:pass
    assert rec.payload
    c['payload']=rec.payload
common={'temperature':.7,'top_p':.95,'top_k':40,'min_p':.05,'cache_prompt':False,'chat_template_kwargs':{'enable_thinking':False}}
prereg={'kind':'reuse-existing-error-composer-for-known-boundary-not-acceptance','cases':cases,'stages':['guarded'],
 'sampling':common,'method':'Same nine consumed unsupported diagnostic requests. Replace the separate unsupported conversation redactor with the EXISTING error composer and its existing out_of_catalog situation. No product edit yet; current composer guarded only, first prompt asserted, product seeds and budgets preserved. This does not establish whether the requests ought to be routed unsupported; no PC effects. Full app remains required.',
 'hashes':{str(p):sha(p) for p in [model,register,ROOT/'src/baxy_mind/llm.py',Path(__file__)]}}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2),encoding='utf-8')
class Client(LlmRuntime):
    stage=None;case=None;first=False
    def _post(self,payload,*args,**kwargs):
        payload=copy.deepcopy(payload);payload.update(common)
        if self.stage=='guarded' and self.first:
            assert payload['messages']==self.case['payload']['messages'],'First guarded prompt differs'
            self.first=False
        response=super()._post(payload,*args,**kwargs)
        if self.stage:
            with (out/'posts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'stage':self.stage,'id':self.case['id'],'payload':payload,'response':response},ensure_ascii=False)+'\n')
        return response
client=Client();gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid());gpu.start();ram.start();start=time.monotonic();fatal=None
try:
    client.start_warmup();assert client.wait_warmup(90)
    (out/'SERVER_COMMAND.json').write_text(json.dumps(client._server_command(),indent=2),encoding='utf-8')
    for stage in ['guarded']:
        client.stage=stage
        for c in cases:
            assert gpu.peak_mib is not None and gpu.peak_mib<=4096
            client.case=c;client.first=True;client.begin_request(40);tick=time.monotonic();answer=None;error=None;finish=None
            try:
                if stage=='guarded':answer=compose(client,c)
                else:
                    payload=copy.deepcopy(c['payload'])
                    if stage=='plain':
                        instruction='Responde de forma natural a la petición. Los hechos adjuntos son una simulación: describe solamente el estado indicado; no ejecutes acciones ni inventes resultados. Usa español para una petición mixta, inglés si la petición está en inglés.'
                        payload['messages']=[{'role':'system','content':instruction},{'role':'user','content':c['request']+'\nHechos de la simulación: '+c['facts']['situation']}]
                    response=client._post(payload);choice=response['choices'][0];answer=choice['message'].get('content');finish=choice.get('finish_reason')
            except Exception as exc:error=f'{type(exc).__name__}: {exc}'
            finally:client.end_request()
            row={'stage':stage,'id':c['id'],'request':c['request'],'response':answer,'error':error,'finishReason':finish,'seconds':round(time.monotonic()-tick,3)}
            with (out/'replies.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
            print(json.dumps({'stage':stage,'id':c['id'],'error':error}),flush=True)
except Exception as exc:fatal=f'{type(exc).__name__}: {exc}'
finally:
    client.close();gpu.stop();ram.stop()
    result={'seconds':round(time.monotonic()-start,2),'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib,'error':fatal,'registrationUnchanged':sha(register)==prereg['hashes'][str(register)]}
    (out/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
