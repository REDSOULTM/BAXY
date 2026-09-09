"""Read server/template compatibility before comparing model answers."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,sys,threading,time,urllib.request
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root),str(root/'src')]
import psutil
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-backend-compat449';out.mkdir(exist_ok=False)
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-backend-compat449-private';private.mkdir(exist_ok=False)
with (private.parent/'C03-memory-roles438-private/posts.jsonl').open(encoding='utf-8-sig') as f:
 reference=next(json.loads(line)['payload'] for line in f if '"id": "actual437-t7"' in line and '"variant": "baseline"' in line)
models={
 'qwen35-4b':Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf'),
 'gemma-published':Path('D:/BAXYRuntime/experiments/models/baxy-gemma4-e2b-published-f9b84ecd/gemma-4-E2B-it-Q4_K_M.gguf')}
servers={'b9980':Path('D:/BAXYRuntime/assets/llama-b9980-cuda12.4/llama-server.exe'),
 'b10809':Path('D:/BAXYRuntime/assets/llama-v0.4.0-b10809-cuda12.4/llama-server.exe')}
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
initial=sha(manifest)
prereg={'utc':datetime.now(timezone.utc).isoformat(),'method':'Two existing candidate models, old/new backend sequentially. Read props, slots, and render one unchanged438 payload through apply-template; generate no answers. Capture exact profiles and logs to detect changed context/template/defaults before controlled inference. This is compatibility, not quality or fair model ranking. User20 requires documented model-specific profiles after backend isolation.',
 'models':{k:{'path':str(p),'sha256':sha(p)} for k,p in models.items()},'servers':{k:{'path':str(p),'sha256':sha(p)} for k,p in servers.items()},
 'manifest_sha256':initial,'limits':{'gpu_stop_mib':3800,'minimum_free_ram_mib':768},'private':str(private)}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
results=[]
for model_name,model in models.items():
 for backend,server in servers.items():
  key=model_name+'-'+backend
  for env_key in list(os.environ):
   if env_key.startswith('BAXY_MIND_'):os.environ.pop(env_key)
  os.environ.update(BAXY_MIND_LLM_GGUF=str(model),BAXY_MIND_LLAMA_SERVER=str(server),BAXY_MIND_NGL='99',BAXY_MIND_KV_CACHE_TYPE='q8_0')
  class Logged(LlmRuntime):
   def _server_command(self):return [*super()._server_command(),'--log-file',str(out/(key+'-startup.log'))]
  client=Logged();gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid())
  stop=threading.Event();violations=[];started=time.monotonic()
  def watch():
   while not stop.wait(.25):
    if gpu.peak_mib is not None and gpu.peak_mib>=3800:violations.append('gpu_bound')
    if psutil.virtual_memory().available<768*2**20:violations.append('system_free_ram_bound')
    if violations:client.close();return
  thread=threading.Thread(target=watch,daemon=True);row={'model':model_name,'backend':backend}
  def http(path,data=None):
   body=None if data is None else json.dumps(data,ensure_ascii=False).encode('utf-8')
   request=urllib.request.Request(client._endpoint+path,data=body,headers={'Content-Type':'application/json'})
   with urllib.request.urlopen(request,timeout=20) as f:return json.load(f)
  try:
   gpu.start();ram.start();thread.start();client.start_warmup();assert client.wait_warmup(90)
   assert gpu.telemetry_available and gpu.peak_mib is not None
   props=http('/props');slots=http('/slots')
   rendered=http('/apply-template',reference)
   for suffix,data in [('props',props),('slots',slots),('rendered',rendered),('command',client._server_command())]:
    (private/(key+'-'+suffix+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
   prompt=rendered.get('prompt');assert isinstance(prompt,str)
   row.update(props_context=props.get('default_generation_settings',{}).get('n_ctx'),
      total_slots=props.get('total_slots'),slots=[{k:s.get(k) for k in ['id','n_ctx','is_processing']} for s in slots],
      rendered_sha256=hashlib.sha256(prompt.encode('utf-8')).hexdigest(),rendered_characters=len(prompt),
      generation_settings=props.get('default_generation_settings',{}))
  except Exception as error:row['error']=type(error).__name__+': '+str(error)
  finally:
   stop.set();client.close();thread.join(timeout=5);gpu.stop();ram.stop()
   row.update(violations=violations,gpu_peak_mib=gpu.peak_mib,ram_peak_mib=ram.peak_mib,seconds=round(time.monotonic()-started,3))
   results.append(row)
   (out/'RESULTS.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
   print(json.dumps({k:v for k,v in row.items() if k!='generation_settings'},ensure_ascii=True),flush=True)
assert sha(manifest)==initial
(out/'PINS.json').write_text(json.dumps({p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'},indent=2)+'\n',encoding='utf-8',newline='\n')
assert all(not r.get('error') and not r['violations'] for r in results), 'inspect compatibility failures before inference'
