"""Reuse the existing trained adapter before considering new training."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-native-compose-profile523.py').read_text(encoding='utf-8')
source=source.replace('astra-native-compose-profile523','astra-inherited-lora560').replace('C03-native-compose-profile523-private','C03-inherited-lora560-private')
start=source.index('ids=');end=source.index('manifest=Path(',start)
source=source[:start]+'''cases=json.loads((private.parent/'C03-gemma-current-writer557-private/cases.json').read_text(encoding='utf-8-sig'))
assert len(cases)==18
''' +source[end:]
start=source.index('profiles=');end=source.index("write(private/'cases.json',cases)",start)
source=source[:start]+'''adapter=Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-training-cdbee75f/c03-pilot-lora-v4-f32.gguf')
assert sha(adapter)=='e28d7728c915861a798b005c22e7b9148fdce729e4a402ac5d502abdbeaccce5'
command += ['--lora',str(adapter),'--lora-init-without-apply']
documented={'temperature':.7,'top_p':.8,'top_k':20,'min_p':0.,'presence_penalty':0.,'repeat_penalty':1.,'seed':0,'cache_prompt':False}
profiles=[('registered-base',{'seed':0,'lora':[{'id':0,'scale':0.}]}),
          ('documented-base',{**documented,'lora':[{'id':0,'scale':0.}]}),
          ('documented-pilot4',{**documented,'lora':[{'id':0,'scale':1.}]})]
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),
 'method':'Eighteen current native writer captures already frozen557, three profiles: registered base, documented Qwen sampling base, identical documented sampling with existing LoRA pilot4. Same model, raw facts, instructions and token limit. Adapter loaded once with zero default; explicit per-request scale, no global runtime or product changes. No new training and no source adoption.',
 'inheritance':'Existing192-example QLoRA pilot4 trained2epochs, rank8 q/v, saved e28d7728 GGUF. Previous51-case evaluation and route diagnostic used older inputs and language criteria; pilot2 integrated17/21 after owner clarification, not falsely independent new success. Current facts/schema and557 hard failures differ; test the actual inherited artifact before retraining.',
 'sources':['artifacts/comprobaciones/C03/astra-lora-pilot4-training/RESULT.json','artifacts/comprobaciones/C03/astra-lora-pilot4-evaluation/PREREG.json','https://raw.githubusercontent.com/ggml-org/llama.cpp/b9980/tools/server/README.md','https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507#best-practices'],
 'criteria':'Separate sampler improvement from adapter effect. All public content adjudicated for correct subject, capability/state, private confirmation, raw metrics and GPU units; no credit for reasoning or EOF truncation. Existing failures remain failures. Promising results still require varied controls and actual full product; single seed is development only.',
 'profiles':profiles,'adapter_sha256':sha(adapter),'manifest_sha256':manifest_sha,'server_command':command,'case_count':18,
 'limits':{'gpu_stop_mib':3800,'free_ram_mib':768,'total_seconds':360,'request_seconds':60},
 'privacy':'All owner content stays on loopback; no external training or messages. Kernel effects not executed.'})
''' +source[end:]
source=source.replace("write(out/'READY.json',", "with urllib.request.urlopen(url+'/lora-adapters',timeout=5) as response:adapters=json.load(response)\n    assert len(adapters)==1 and adapters[0]['id']==0 and adapters[0]['scale']==0\n    write(out/'ADAPTERS.json',adapters)\n    write(out/'READY.json',")
source=source.replace('if gpu.peak_mib>3800:','if gpu.peak_mib is not None and gpu.peak_mib>3800:')
source=source.replace('if time.monotonic()-start>360:',"if gpu.peak_mib is None and time.monotonic()-start>10:violations.append('missing_gpu_telemetry')\n        if time.monotonic()-start>360:")
source=source.replace('27 native writer requests collected','54 inherited-adapter writer requests collected')
exec(compile(source,__file__,'exec'))
