"""Replay captured writer requests with registered versus documented Qwen sampling."""
from pathlib import Path
from datetime import datetime,timezone
import copy,hashlib,json,os,socket,subprocess,sys,threading,time,urllib.request,urllib.error
import psutil

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler

base=root/'artifacts/comprobaciones/C03'
out=base/'astra-native-compose-profile523';out.mkdir(exist_ok=False)
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-native-compose-profile523-private';private.mkdir(exist_ok=False)
previous=private.parent/'C03-private-product521-private'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def append(p,v):
    with p.open('a',encoding='utf-8') as f:f.write(json.dumps(v,ensure_ascii=False)+'\n')

ids={1:'disabled-save-error',2:'enable-confirmation',3:'enable-result',4:'save-result',6:'app-clarification',12:'progress',17:'disable-result',18:'clock-result',19:'memory-capability-disabled'}
rows=list(map(json.loads,(previous/'http-posts.jsonl').open(encoding='utf-8-sig')))
cases=[{'id':r['id'],'case':ids[r['id']],'payload':r['payload']} for r in rows if r['stage']=='request' and r['id'] in ids]
assert len(cases)==9 and all(c['payload']['messages'][0]['content'].startswith('Eres BAXY, un compañero. Eres un él.') for c in cases)
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
manifest_sha=sha(manifest);assert manifest_sha=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
command=json.loads((previous/'effective-server-command.json').read_text(encoding='utf-8-sig'))
assert sha(command[0])=='38a9d28ea414442590486459a7d1f5e32655db83148b7a114b79cd1ad242946e'
assert sha(command[command.index('-m')+1])=='3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
command[command.index('--port')+1]=str(port)
command[command.index('--log-file')+1]=str(private/'server.log')
profiles=[('registered-seed0',{'seed':0}),('documented-seed0',{'temperature':0.7,'top_p':0.8,'top_k':20,'min_p':0.0,'presence_penalty':0.0,'repeat_penalty':1.0,'seed':0}),('documented-seed17',{'temperature':0.7,'top_p':0.8,'top_k':20,'min_p':0.0,'presence_penalty':0.0,'repeat_penalty':1.0,'seed':17})]
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'method':'Nine exact captured writer inputs from product521: error, confirmation, enabled/save/disable receipts, clarification, progress, clock, and disabled-memory capability. Native HTTP only, no Core effects or full product. Compare registered greedy payload plus explicit seed0 with official Qwen2507 sampling at seeds0/17. Do not change data, prompt, max_tokens, templates, backend, quantization, hardware configuration or output after generation. Native baseline versus documented profile first; no wording sweep.','source':'https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507#best-practices','profile_rationale':'Qwen model card recommends temperature0.7,top_p0.8,top_k20,min_p0; optional presence0–2 can affect language/performance, so use0, with neutral repetition1. Registered greedy already validated for knowledge512/513; this tests the distinct public writer task rather than assuming that result transfers. Max256 is unchanged for brief writer outputs; any length finish is a failure, not silent truncation.','profiles':profiles,'cases':[{'id':c['id'],'case':c['case'],'payload_sha256':hashlib.sha256(json.dumps(c['payload'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()} for c in cases],'criteria':'Review every native output for facts/cause, decision scope, language, natural BAXY voice and no invented observations/effects. Critical existing faults are internal save narration and denial of memory capability when disabled. Preserve correct disable without PC-change invention and factual clock. No success solely fromHTTP200 or one fluent sample. A promising profile still needs the actual whole writer/guard/product path and regression before adoption.','server_command':command,'manifest_sha256':manifest_sha,'capture_sha256':sha(previous/'http-posts.jsonl'),'limits':{'gpu_stop_mib':3800,'free_ram_mib':768,'total_seconds':360,'request_seconds':60},'exclusions':'Synthetic consumed development captures; no fresh acceptance, real user data, UI/audio or global model ranking. Same product server geometry intentionally held fixed to isolate sampling, not claimed to minimize native-only memory.'})
write(private/'cases.json',cases)
with (private/'launch.log').open('w',encoding='utf-8') as launch:
    process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=launch,stderr=subprocess.STDOUT,cwd=root,creationflags=subprocess.CREATE_NO_WINDOW)
write(out/'PROCESS.json',{'pid':process.pid,'command':command})
gpu=ProcessTreeGpuSampler(process.pid);ram=RamSampler(process.pid)
gpu.start();ram.start();start=time.monotonic();stop=threading.Event();violations=[];complete=False
def terminate_owned():
    try:
        parent=psutil.Process(process.pid)
        for child in parent.children(recursive=True):
            try:child.kill()
            except psutil.Error:pass
        parent.kill()
    except psutil.Error:pass
def guard():
    while not stop.wait(.25):
        if gpu.peak_mib>3800:violations.append('gpu_stop')
        if psutil.virtual_memory().available/(1024**2)<768:violations.append('low_free_ram')
        if time.monotonic()-start>360:violations.append('wall_time')
        if violations:terminate_owned();return
thread=threading.Thread(target=guard,daemon=True);thread.start()
url=f'http://127.0.0.1:{port}'
try:
    while time.monotonic()-start<90:
        assert process.poll() is None and not violations,'server stopped before readiness'
        try:
            with urllib.request.urlopen(url+'/health',timeout=2) as response:health=json.load(response)
            if health.get('status')=='ok':break
        except (urllib.error.URLError,TimeoutError):pass
        time.sleep(.25)
    else:raise TimeoutError('server readiness')
    write(out/'READY.json',{'seconds':time.monotonic()-start,'health':health})
    for case_index,case in enumerate(cases):
        # Rotate order to avoid assigning every cold request to the same profile.
        order=profiles[case_index%3:]+profiles[:case_index%3]
        for profile,settings in order:
            payload=copy.deepcopy(case['payload']);payload.update(settings)
            append(private/'requests.jsonl',{'case':case['case'],'source_id':case['id'],'profile':profile,'payload':payload})
            before=time.monotonic()
            request=urllib.request.Request(url+'/v1/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
            try:
                with urllib.request.urlopen(request,timeout=60) as response:result=json.load(response)
                record={'case':case['case'],'source_id':case['id'],'profile':profile,'seconds':time.monotonic()-before,'response':result}
            except Exception as error:
                record={'case':case['case'],'source_id':case['id'],'profile':profile,'seconds':time.monotonic()-before,'error':type(error).__name__+': '+str(error)}
            append(private/'responses.jsonl',record)
            assert not violations
        print('completed '+case['case'],flush=True)
    complete=True
finally:
    stop.set();terminate_owned();process.wait(timeout=20);thread.join(timeout=5);gpu.stop();ram.stop()
    write(out/'RESOURCES.json',{'completed':complete,'violations':violations,'gpu_peak_mib':gpu.peak_mib,'ram_peak_mib':ram.peak_mib,'seconds':round(time.monotonic()-start,3),'manifest_unchanged':sha(manifest)==manifest_sha,'server_exit_after_intentional_cleanup':process.returncode})
assert complete and not violations
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
print('27 native writer requests collected; adjudication pending.',flush=True)
