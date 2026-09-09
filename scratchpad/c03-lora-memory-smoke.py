"""Three response-only optimizer steps, no acceptance or model promotion."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import os
import sys
import time
import traceback

os.environ['HF_HUB_OFFLINE']='1'
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler

OUT=ROOT/'artifacts/comprobaciones/C03/astra-lora-memory-measured'
assert not OUT.exists()
OUT.mkdir()
base=Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-training-cdbee75f')
assert (base/'VERIFIED.json').is_file(), 'Wait for verified download; never train partial weights'
sample=ROOT/'artifacts/comprobaciones/C03/astra-lora-smoke-input.json'
data=json.loads(sample.read_text(encoding='utf-8'))
prereg={'kind':'training-memory-viability-only','steps':3,'sequenceLength':512,'batchSize':1,
         'quantization':'NF4,double quant,bfloat16 compute','lora':{'rank':8,'alpha':16,'targets':['q_proj','v_proj']},
         'learningRate':0.0002,'seed':13,'gpuLimitMiB':4096,'torchAllocatorFraction':0.55,
         'loss':'Only final assistant response tokens. No loss on request, facts or padding. Native tokenizer template. Select last answer logits instead of allocating vocabulary logits for the whole prompt.',
         'preparation':'Frozen base kept bfloat16 outside NF4 layers; no blanket fp32 cast of large frozen embeddings. Non-reentrant gradient checkpointing. Only LoRA optimized.',
         'inheritance':'Probando Gemma 4/dataset_finetune/scripts/train_ft.py:130-180 response-only loss and exclusion of observed facts, reduced from historical batch4/8.4GB to batch1.',
         'acceptance':'Three finite losses, nonzero trainable gradients, only LoRA trainable, measured GPU peak <=4096 MiB. Not a quality or generalization test.',
         'sampleSha256':hashlib.sha256(sample.read_bytes()).hexdigest(),
         'baseManifestSha256':hashlib.sha256((base/'VERIFIED.json').read_bytes()).hexdigest(),
         'scriptSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         'versions':{name:importlib.metadata.version(name) for name in ['torch','transformers','peft','accelerate','bitsandbytes']}}
(OUT/'PREREG.json').write_text(json.dumps(prereg,indent=2),encoding='utf-8')
gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid())
gpu.start();ram.start();started=time.monotonic();result={'status':'started','steps':[]}
model=None
try:
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer,BitsAndBytesConfig
    from peft import LoraConfig,get_peft_model
    assert torch.cuda.is_available()
    torch.manual_seed(13)
    torch.cuda.set_per_process_memory_fraction(.55)
    tokenizer=AutoTokenizer.from_pretrained(base,local_files_only=True)
    prompt=tokenizer.apply_chat_template(data['messages'],tokenize=False,add_generation_prompt=True,enable_thinking=False)
    complete=tokenizer.apply_chat_template(data['messages']+[{'role':'assistant','content':data['answer']}],tokenize=False,add_generation_prompt=False,enable_thinking=False)
    assert complete.startswith(prompt), 'Response mask must align with native generation prefix'
    prompt_ids=tokenizer(prompt,add_special_tokens=False)['input_ids']
    complete_ids=tokenizer(complete,add_special_tokens=False)['input_ids']
    assert complete_ids[:len(prompt_ids)]==prompt_ids
    answer_ids=complete_ids[len(prompt_ids):]
    assert 0<len(answer_ids)<len(complete_ids)<=512
    padding=512-len(complete_ids)
    ids=torch.tensor([[tokenizer.pad_token_id]*padding+complete_ids],device='cuda')
    attention=torch.tensor([[0]*padding+[1]*len(complete_ids)],device='cuda')
    targets=torch.tensor([answer_ids],device='cuda')
    result['inputTokens']=len(complete_ids);result['answerTokens']=len(answer_ids)
    print(json.dumps({'phase':'load','inputTokens':len(complete_ids),'answerTokens':len(answer_ids)}),flush=True)
    model=AutoModelForCausalLM.from_pretrained(base,local_files_only=True,device_map={'':0},torch_dtype=torch.bfloat16,
        attn_implementation='sdpa',quantization_config=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',
        bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16))
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    model.config.use_cache=False
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
    model=get_peft_model(model,LoraConfig(r=8,lora_alpha=16,lora_dropout=0.0,target_modules=['q_proj','v_proj'],task_type='CAUSAL_LM'))
    trainable=[(name,p) for name,p in model.named_parameters() if p.requires_grad]
    assert trainable and all('lora_' in name for name,_ in trainable)
    result['trainableParameters']=sum(p.numel() for _,p in trainable)
    optimizer=torch.optim.AdamW([p for _,p in trainable],lr=0.0002)
    model.train()
    for step in range(3):
        if gpu.peak_mib is not None and gpu.peak_mib>4096:
            raise RuntimeError('Measured GPU ceiling exceeded')
        tick=time.monotonic();optimizer.zero_grad(set_to_none=True)
        with torch.autocast('cuda',dtype=torch.bfloat16):
            output=model(input_ids=ids[:,:-1],attention_mask=attention[:,:-1],logits_to_keep=len(answer_ids),use_cache=False)
            assert output.logits.shape[1]==len(answer_ids)
            loss=torch.nn.functional.cross_entropy(output.logits.float().reshape(-1,output.logits.shape[-1]),targets.reshape(-1))
        assert torch.isfinite(loss)
        loss.backward()
        grad=torch.nn.utils.clip_grad_norm_([p for _,p in trainable],1.0)
        assert torch.isfinite(grad) and grad>0
        optimizer.step();torch.cuda.synchronize()
        row={'step':step+1,'loss':loss.item(),'gradNorm':grad.item(),'seconds':round(time.monotonic()-tick,3),
             'torchReservedMiB':torch.cuda.memory_reserved()/2**20,'gpuPeakMiB':gpu.peak_mib}
        result['steps'].append(row);print(json.dumps(row),flush=True)
        del output,loss
    result['torchPeakMiB']=torch.cuda.max_memory_reserved()/2**20
    result['status']='steps_completed'
except Exception as exc:
    result['status']='failed';result['error']=f'{type(exc).__name__}: {exc}'
    (OUT/'ERROR.txt').write_text(traceback.format_exc(),encoding='utf-8')
    print(json.dumps({'error':result['error']}),flush=True)
finally:
    gpu.stop();ram.stop()
    result.update(elapsedSeconds=round(time.monotonic()-started,2),gpuPeakMiB=gpu.peak_mib,ramPeakMiB=ram.peak_mib,
                  telemetryAvailable=gpu.telemetry_available)
    result['viable']=result['status']=='steps_completed' and gpu.telemetry_available and gpu.peak_mib is not None and gpu.peak_mib<=4096
    (OUT/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)
