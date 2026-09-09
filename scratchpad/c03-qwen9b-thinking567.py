"""Qualify inherited9B in its documented thinking mode on current causal failures."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-native-compose-profile523.py').read_text(encoding='utf-8')
source = source.replace('astra-native-compose-profile523', 'astra-qwen9b-thinking567').replace('C03-native-compose-profile523-private', 'C03-qwen9b-thinking567-private')
start = source.index('ids='); end = source.index('manifest=Path(', start)
source = source[:start] + '''
all_cases=json.loads((private.parent/'C03-scoped-configuration566-private/cases.json').read_text(encoding='utf-8-sig'))
selected={'enable-confirmation','save-result','stored-name-es','clock-result','progress','memory-capability-disabled','C03-survey-readonly541-private:26','C03-survey-readonly541-private:59','C03-survey-resume543-private:17','es-disabled-empty','en-disabled','en-enabled'}
cases=[c for c in all_cases if c['case'] in selected]
assert len(cases)==12
''' + source[end:]
start = source.index('command=json.loads('); end = source.index('with socket.socket()', start)
source = source[:start] + '''
command=json.loads((base/'astra-qwen9b-profile482/command-Qwen3.5-9B.json').read_text(encoding='utf-8-sig'))
assert sha(command[0])=='16eac28198d6218a9892f08dac0f0c81612a72872b4dd9741c4c6c36f88c4fd7'
assert sha(command[command.index('-m')+1])=='03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8'
for flag,value in [('-ngl','19'),('-c','8192'),('-np','1'),('--reasoning','on'),('--reasoning-budget','-1')]:
    command[command.index(flag)+1]=value
free=psutil.virtual_memory().available/2**20
write(out/'PREFLIGHT.json',{'free_ram_mib':free,'required_mib':4000,'estimate':'482 native model buffers CUDA2444/CPU2963MiB at14layers. Five extra layers move roughly600MiB to GPU, one slot lowers recurrent state; estimated own RAM near3100MiB plus768MiB guard. This is an estimate to be measured, not proof.'})
assert free>=4000,'Insufficient RAM for this profile; do not close user programs'
''' + source[end:]
start = source.index('profiles='); end = source.index("write(private/'cases.json',cases)", start)
source = source[:start] + '''
profiles=[('documented-thinking-seed0',{'temperature':1.,'top_p':.95,'top_k':20,'min_p':0.,'presence_penalty':1.5,'repeat_penalty':1.,'seed':0,'max_tokens':6144,'reasoning_budget_tokens':-1})]
write(out/'PREREG.json',{'method':'Twelve unchanged current writer captures557/566 on existing Qwen3.5-9B Q4_K_M with documented general thinking profile. No instructions540/565/566 or modified observations. Prior482 was nonthinking;453 thinking covered4B/Gemma, not9B. Evaluate actual final content, not reasoning. No model promotion from one seed.',
 'sources':['https://huggingface.co/Qwen/Qwen3.5-9B#best-practices','https://github.com/ggml-org/llama.cpp/pull/28068','astra-qwen9b-profile482/PLAN.md'],
 'profile_rationale':'Official general thinking T1,p.95,k20,min0,presence1.5,repeat1. No intermediate cutoff;6144 total output tokens within8192 context for these short prompts. Manufacturer recommends more for complex benchmarks: a length finish here is censored, never scored as semantic inability. Native diagnostic may exceed product latency and is not production-ready by implication.',
 'resources_rationale':'NGL19,one8192slot versus482 NGL14,three4096slots: move weights into available VRAM and reduce recurrent state to fit currently available RAM. Preserve b10865 GDN fix,q8 KV,FA,b2048,ub256,no-mmap/cache0. This is profile qualification, not attribution to one flag.',
 'criteria':'Correct user/assistant subject, CPU logical qualifier and percent owner, bytes/units and no physical GPU count inferred from adapter rows; memory state versus capability, truthful receipts and natural progress. Stop/length/error and per-request timing recorded; no UI/voice/effects/survey credit. No global settings changed.',
 'server_command':command,'manifest_sha256':manifest_sha,'profiles':profiles,'case_count':len(cases),
 'limits':{'gpu_stop_mib':3800,'free_ram_mib':768,'total_seconds':1200,'request_seconds':180}})
''' + source[end:]
source = source.replace("payload=copy.deepcopy(case['payload']);payload.update(settings)", "payload=copy.deepcopy(case['payload']);payload.update(settings)\n            payload['chat_template_kwargs']={**payload.get('chat_template_kwargs',{}),'enable_thinking':True}")
source = source.replace('case_index%3', 'case_index%1')
source = source.replace('if gpu.peak_mib>3800:', 'if gpu.peak_mib is not None and gpu.peak_mib>3800:')
source = source.replace('if time.monotonic()-start>360:', "if gpu.peak_mib is None and time.monotonic()-start>15:violations.append('missing_gpu_telemetry')\n        if time.monotonic()-start>1200:")
source = source.replace('urlopen(request,timeout=60)', 'urlopen(request,timeout=180)')
source = source.replace("write(out/'READY.json',", "with urllib.request.urlopen(url+'/props',timeout=10) as response:write(private/'effective-props.json',json.load(response))\n    request=urllib.request.Request(url+'/apply-template',data=json.dumps({**cases[0]['payload'],'chat_template_kwargs':{'enable_thinking':True}}).encode(),headers={'Content-Type':'application/json'})\n    with urllib.request.urlopen(request,timeout=10) as response:write(private/'effective-template.json',json.load(response))\n    write(out/'READY.json',")
source = source.replace('27 native writer requests collected', '12 reasoning writer requests collected')
exec(compile(source, __file__, 'exec'))
