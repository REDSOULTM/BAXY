"""Two-epoch, 132-example development pilot using the measured QLoRA profile."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import os
import random
import sys
import time
import traceback

os.environ.update(HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler
OUT=ROOT/'artifacts/comprobaciones/C03/astra-lora-pilot3-training'
SAVE=Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-training-cdbee75f/c03-pilot-lora-v3')
BASE=SAVE.parent
DATA=ROOT/'artifacts/comprobaciones/C03/astra-lora-pilot3-data'
assert not OUT.exists() and not SAVE.exists()
assert json.loads((ROOT/'artifacts/comprobaciones/C03/astra-lora-memory-measured/RESULT.json').read_text())['viable']
OUT.mkdir()
prereg={'kind':'development-QLoRA-pilot-not-product-acceptance','epochs':2,'microBatch':1,'accumulation':4,
         'sequenceMaximum':512,'rank':8,'alpha':16,'targets':['q_proj','v_proj'],'learningRate':.0002,'seed':13,
         'memoryLimitMiB':4096,'allocatorFraction':.55,'quantization':'NF4 double,bfloat16 compute',
         'loss':'Native final assistant answer only; request/facts/padding have no target loss. No truncation.',
         'evaluation':'After training, compare base and adapter on frozen HOLDOUT plus existing nine-case development probe. No promotion unless materially improves useful faithful language and preserves pure ES/EN. All product routes remain unproven.',
         'hashes':{name:hashlib.sha256((DATA/name).read_bytes()).hexdigest() for name in ['TRAIN.jsonl','HOLDOUT.jsonl','MANIFEST.json']},
         'scriptSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         'versions':{name:importlib.metadata.version(name) for name in ['torch','transformers','peft','bitsandbytes','accelerate','pywin32']}}
(OUT/'PREREG.json').write_text(json.dumps(prereg,indent=2),encoding='utf-8')
gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid());gpu.start();ram.start()
started=time.monotonic();result={'status':'started','updates':[]}
try:
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer,BitsAndBytesConfig
    from peft import LoraConfig,get_peft_model
    torch.manual_seed(13);random.seed(13);torch.cuda.set_per_process_memory_fraction(.55)
    tokenizer=AutoTokenizer.from_pretrained(BASE,local_files_only=True)
    rows=[json.loads(line) for line in (DATA/'TRAIN.jsonl').read_text(encoding='utf-8').splitlines()]
    samples=[]
    for row in rows:
        messages=row['payload']['messages']
        prompt=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
        complete=tokenizer.apply_chat_template(messages+[{'role':'assistant','content':row['answer']}],tokenize=False,add_generation_prompt=False,enable_thinking=False)
        assert complete.startswith(prompt)
        prefix=tokenizer(prompt,add_special_tokens=False)['input_ids']
        ids=tokenizer(complete,add_special_tokens=False)['input_ids']
        assert ids[:len(prefix)]==prefix and len(prefix)<len(ids)<=512,(row['id'],len(ids))
        samples.append((row['id'],ids,ids[len(prefix):]))
    result['trainExamples']=len(samples);result['maxTokens']=max(len(ids) for _,ids,_ in samples)
    print(json.dumps({'phase':'load','examples':len(samples),'maxTokens':result['maxTokens']}),flush=True)
    model=AutoModelForCausalLM.from_pretrained(BASE,local_files_only=True,device_map={'':0},torch_dtype=torch.bfloat16,
        attn_implementation='sdpa',quantization_config=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',
        bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16))
    for p in model.parameters():p.requires_grad_(False)
    model.config.use_cache=False
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
    model=get_peft_model(model,LoraConfig(r=8,lora_alpha=16,lora_dropout=0.0,target_modules=['q_proj','v_proj'],task_type='CAUSAL_LM'))
    pairs=[(n,p) for n,p in model.named_parameters() if p.requires_grad]
    assert pairs and all('lora_' in n for n,_ in pairs)
    parameters=[p for _,p in pairs];result['trainableParameters']=sum(p.numel() for p in parameters)
    optimizer=torch.optim.AdamW(parameters,lr=.0002)
    model.train();optimizer.zero_grad(set_to_none=True)
    batch_losses=[];updates=0
    for epoch in range(2):
        order=list(range(len(samples)));random.shuffle(order)
        for position,index in enumerate(order):
            if not gpu.telemetry_available or gpu.peak_mib is None or gpu.peak_mib>4096:
                raise RuntimeError('GPU telemetry unavailable or ceiling exceeded')
            sample_id,all_ids,answer=samples[index]
            ids=torch.tensor([all_ids[:-1]],device='cuda');targets=torch.tensor([answer],device='cuda')
            with torch.autocast('cuda',dtype=torch.bfloat16):
                output=model(input_ids=ids,logits_to_keep=len(answer),use_cache=False)
                loss=torch.nn.functional.cross_entropy(output.logits.float().reshape(-1,output.logits.shape[-1]),targets.reshape(-1))
            assert torch.isfinite(loss)
            batch_losses.append(loss.item());(loss/4).backward()
            del output,loss,ids,targets
            if (position+1)%4==0:
                grad=torch.nn.utils.clip_grad_norm_(parameters,1.0)
                assert torch.isfinite(grad) and grad>0
                optimizer.step();optimizer.zero_grad(set_to_none=True);torch.cuda.synchronize();updates+=1
                row={'update':updates,'epoch':epoch+1,'loss':sum(batch_losses)/len(batch_losses),'gradNorm':grad.item(),
                     'gpuPeakMiB':gpu.peak_mib,'elapsedSeconds':round(time.monotonic()-started,2)}
                result['updates'].append(row);print(json.dumps(row),flush=True);batch_losses=[]
    assert gpu.peak_mib<=4096
    model.save_pretrained(SAVE,safe_serialization=True)
    tokenizer.save_pretrained(SAVE)
    result.update(status='trained-not-promoted',adapter=str(SAVE),torchPeakMiB=torch.cuda.max_memory_reserved()/2**20,
                  adapterSha256=hashlib.sha256((SAVE/'adapter_model.safetensors').read_bytes()).hexdigest())
except Exception as exc:
    result.update(status='failed',error=f'{type(exc).__name__}: {exc}')
    (OUT/'ERROR.txt').write_text(traceback.format_exc(),encoding='utf-8')
finally:
    gpu.stop();ram.stop()
    result.update(elapsedSeconds=round(time.monotonic()-started,2),gpuPeakMiB=gpu.peak_mib,ramPeakMiB=ram.peak_mib)
    (OUT/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='updates'}),flush=True)
