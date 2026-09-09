from pathlib import Path
import copy, hashlib, json, os, sys, time
root=Path.cwd(); sys.path.insert(0,str(root/'src')); sys.path.insert(0,str(root))
from baxy_mind.llm import LlmRuntime
from baxy_mind.request_reading import read_request
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler
out=root/'artifacts/comprobaciones/C03/astra-history-isolated'
assert not out.exists(); out.mkdir()
source=root/'artifacts/comprobaciones/C03/astra-qwen2507-corpus-warm/paired.json'
rows=json.loads(source.read_text(encoding='utf-8-sig'))
class Recorder(LlmRuntime):
    def __init__(self, reply):
        self._gguf='Qwen3-4B-Instruct-2507-Q4_K_M.gguf'; self.reply=reply; self.payloads=[]
    def _post(self,payload):
        self.payloads.append(copy.deepcopy(payload))
        return {'choices':[{'message':{'content':self.reply},'finish_reason':'stop'}]}
panels=[]
for target in ['t8','t9','t10','t13','t14','t15']:
    history=[]
    for row in rows:
        if row['turnId']==target:
            history.append({'role':'user','content':row['request']})
            history=history[-12:]
            recorder=Recorder(row['final'])
            recorder.chat(row['request'],history=history,conversation_kind='knowledge',response_language=read_request(row['request']).language)
            original=recorder.payloads[0]
            assert len(recorder.payloads)==1
            candidate=copy.deepcopy(original)
            candidate['messages']=[m for m in candidate['messages'] if m['role']=='system']+[candidate['messages'][-1]]
            panels.append({'turnId':target,'request':row['request'],'full':original,'isolated':candidate})
            break
        history.extend([{'role':'user','content':row['request']},{'role':'assistant','content':row['final']}])
model=Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf')
os.environ.update(BAXY_MIND_LLAMA_SERVER='D:/BAXYRuntime/assets/llama-b9980-cuda12.4/llama-server.exe',BAXY_MIND_LLM_GGUF=str(model),BAXY_MIND_NGL='99',BAXY_MIND_KV_CACHE_TYPE='q8_0')
prereg={'kind':'direct-model-context-ablation-not-product-acceptance','source':str(source),'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'history':'Reconstructed from published paired turns using MainWindowViewModel.BuildMindHistory 12-message rule. Not a captured original HTTP prompt. Same reconstructed history on both sides.','hypothesis':'Second diagnostic after removing only assistant history worsened topic and language. Isolate the current user message with the unchanged system instructions to determine whether failures persist without any prior turns. Diagnostic only: not a proposal to drop product memory or context.','cases':panels,'sampling':{'temperature':.7,'top_p':.8,'top_k':20,'min_p':0,'seed':0},'llmSha256':hashlib.sha256((root/'src/baxy_mind/llm.py').read_bytes()).hexdigest()}
prereg['model']={'path':str(model),'sha256':hashlib.sha256(model.read_bytes()).hexdigest()}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2),encoding='utf-8')
client=LlmRuntime(); gpu=ProcessTreeGpuSampler(os.getpid()); ram=RamSampler(os.getpid()); gpu.start();ram.start();started=time.monotonic()
try:
    client.start_warmup(); assert client.wait_warmup(120), 'Model failed warmup'
    with (out/'replies.jsonl').open('w',encoding='utf-8') as stream:
        for i,panel in enumerate(panels):
            for variant in ['isolated']:
                if gpu.peak_mib is not None and gpu.peak_mib>4096:
                    raise RuntimeError('GPU ceiling exceeded')
                payload=dict(panel[variant],temperature=.7,top_p=.8,top_k=20,min_p=0,seed=0)
                tick=time.monotonic();response=client._post(payload)
                result={'turnId':panel['turnId'],'variant':variant,'request':panel['request'],'seconds':round(time.monotonic()-tick,3),'response':response}
                stream.write(json.dumps(result,ensure_ascii=False)+'\n');stream.flush()
                print(json.dumps({'turnId':panel['turnId'],'variant':variant,'seconds':result['seconds']}),flush=True)
finally:
    client.close();gpu.stop();ram.stop()
    result={'elapsedSeconds':round(time.monotonic()-started,2),'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib}
    (out/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
