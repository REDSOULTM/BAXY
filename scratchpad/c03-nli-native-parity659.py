"""Verify official ONNX against native FP32 weights on the same premise pairs."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-nli-native-parity659'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-nli-native-parity659-private'
assets = Path('D:/BAXYRuntime/experiments/models/minilm-nli-0a71e92a')
digest = '91b323ccf247ec1e3b5925d566230bae7c52de8147e6062b42e250089a3fc80b'
size = 427997022

def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

if '--worker' in sys.argv:
    import numpy as np
    import torch
    import transformers
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    from tokenizers import Tokenizer
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    tokenizer = AutoTokenizer.from_pretrained(assets,local_files_only=True,use_fast=True,trust_remote_code=False)
    direct = Tokenizer.from_file(str(assets / 'tokenizer.json'))
    direct.no_truncation(); direct.no_padding()
    started = time.perf_counter()
    model = AutoModelForSequenceClassification.from_pretrained(assets,local_files_only=True,trust_remote_code=False,attn_implementation='eager').cpu().eval()
    assert next(model.parameters()).dtype == torch.float32
    load_seconds = time.perf_counter()-started
    panel = json.loads((private.parent / 'C03-nli-fact-probe658-private/panel.json').read_text(encoding='utf-8'))
    old = [json.loads(line) for line in (private.parent / 'C03-nli-fact-probe658-private/results-2.jsonl').read_text(encoding='utf-8').splitlines()]
    labels = [model.config.id2label[i].lower() for i in range(3)]
    assert labels == ['entailment','neutral','contradiction']
    output_labels = ['supported','unknown','contradicted']
    results = []
    with torch.inference_mode():
        for r, reference in zip(panel,old):
            assert r['case_id'] == reference['case_id']
            encoded = tokenizer(r['premise'],r['reply'],truncation=False,return_tensors='pt')
            raw = direct.encode(r['premise'],r['reply'],add_special_tokens=True)
            assert encoded['input_ids'][0].tolist() == raw.ids
            assert encoded['attention_mask'][0].tolist() == raw.attention_mask
            assert len(raw.ids) <= 512
            begin = time.perf_counter()
            probabilities = torch.softmax(model(**encoded).logits[0],-1).tolist()
            elapsed = time.perf_counter()-begin
            predicted = output_labels[int(np.argmax(probabilities))]
            differences = [abs(probability-reference['probabilities'][label]) for label,probability in zip(output_labels,probabilities)]
            results.append({'case_id':r['case_id'],'expected_label':r['expected_label'],'native_label':predicted,
                'onnx_label':reference['label'],'label_parity':predicted == reference['label'],
                'probabilities':dict(zip(output_labels,probabilities)), 'max_probability_abs_difference':max(differences),
                'tokens_equal':True,'seconds':elapsed})
    write(private / 'results.json',results)
    write(private / 'backend.json',{'torch':torch.__version__,'transformers':transformers.__version__,
        'attention_implementation':model.config._attn_implementation,'dtype':'float32','device':'cpu',
        'intra_threads':torch.get_num_threads(),'inter_threads':torch.get_num_interop_threads(),
        'eval':not model.training,'native_fast_tokenizer_parity':True,'load_seconds':load_seconds})
    print(json.dumps({'rows':len(results),'label_parity':sum(r['label_parity'] for r in results),'max_probability_abs_difference':max(r['max_probability_abs_difference'] for r in results)}),flush=True)
    raise SystemExit(0)

out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
write(out / 'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'cases':31,
    'purpose':'658 rejects true scoped claims. Before attributing failure to the NLI model, compare official ONNX FP32 with original PyTorch FP32 and native pair tokenizer. Preserve all658 failures and hypotheses unchanged.',
    'revision':'0a71e92a985b6e1ad1828cf67ce9c459639c1dca','weights_sha256':digest,'weights_bytes':size,
    'source':'https://huggingface.co/MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli',
    'profile':'CPU, FP32, eval/inference_mode, eager attention, 2 intra/1 inter threads, native AutoTokenizer exact token equality with658, no padding/truncation, no fine tuning.',
    'criteria':'Report all predicted labels and probabilities; backend equivalence requires31/31 labels equal and maximum absolute probability difference <=0.001. A mismatch blocks attribution to model quality and requires backend diagnosis. No model or validator promotion.',
    'limits':{'worker_seconds':180,'minimum_free_ram_mib':768},'runtime_modified':False})
path = assets / 'model.safetensors'
if not path.exists():
    partial = assets / 'model.safetensors.partial659'
    assert not partial.exists()
    url = 'https://huggingface.co/MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli/resolve/0a71e92a985b6e1ad1828cf67ce9c459639c1dca/model.safetensors?download=true'
    with urllib.request.urlopen(url,timeout=60) as response,partial.open('xb') as stream:
        while chunk := response.read(4*1024*1024):
            stream.write(chunk)
    assert partial.stat().st_size == size and sha(partial) == digest
    os.replace(partial,path)
assert path.stat().st_size == size and sha(path) == digest
write(out / 'ASSET.json',{'path':str(path),'bytes':size,'sha256':digest})
import psutil
command = [sys.executable,'-X','utf8',__file__,'--worker']
started = time.monotonic()
peak = 0
violations = []
with (private / 'worker.log').open('w',encoding='utf-8') as log:
    child = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    write(out / 'PROCESS.json',{'pid':child.pid,'command':command})
    try:
        while child.poll() is None:
            try:
                proc = psutil.Process(child.pid)
                peak = max(peak,sum(p.memory_info().rss for p in [proc,*proc.children(recursive=True)]))
            except psutil.NoSuchProcess:
                pass
            if time.monotonic()-started > 180:
                violations.append('time_bound')
            if psutil.virtual_memory().available < 768*2**20:
                violations.append('free_ram_bound')
            if violations:
                child.terminate(); break
            time.sleep(.05)
    finally:
        if child.poll() is None:
            child.terminate()
        code = child.wait(timeout=15)
write(out / 'RESOURCES.json',{'exit_code':code,'peak_rss_mib':peak/2**20,'seconds':time.monotonic()-started,'violations':violations})
assert code == 0 and not violations
print('Native parity completed; inspect labels/probabilities before verdict.',flush=True)
