"""CPU NLI with native premise/hypothesis input and separate thread profiles."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-nli-fact-probe658-private'
out = base / 'astra-nli-fact-probe658'
assets = Path('D:/BAXYRuntime/experiments/models/minilm-nli-0a71e92a')

def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def append(path,value):
    with path.open('a',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,ensure_ascii=False)+'\n')

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

if '--worker' in sys.argv:
    threads = int(sys.argv[-1])
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    before = time.perf_counter()
    session = ort.InferenceSession(str(assets / 'onnx/model.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
    load_seconds = time.perf_counter()-before
    assert session.get_providers() == ['CPUExecutionProvider']
    tokenizer = Tokenizer.from_file(str(assets / 'tokenizer.json'))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    config = json.loads((assets / 'config.json').read_text(encoding='utf-8'))
    labels = [config['id2label'][str(i)].lower() for i in range(3)]
    assert labels == ['entailment','neutral','contradiction'], labels
    label_map = {'entailment':'supported','neutral':'unknown','contradiction':'contradicted'}
    input_names = {r.name for r in session.get_inputs()}
    assert input_names <= {'input_ids','attention_mask','token_type_ids'}
    assert 'input_ids' in input_names and 'attention_mask' in input_names
    panel = json.loads((private / 'panel.json').read_text(encoding='utf-8'))
    def infer(premise,hypothesis):
        encoded = tokenizer.encode(premise,hypothesis,add_special_tokens=True)
        assert len(encoded.ids) <= 512, 'Do not silently truncate a factual premise or claim.'
        feeds = {'input_ids':encoded.ids,'attention_mask':encoded.attention_mask,'token_type_ids':encoded.type_ids}
        actual = {key:np.asarray([value],dtype=np.int64) for key,value in feeds.items() if key in input_names}
        started = time.perf_counter()
        logits = session.run(None,actual)[0][0]
        elapsed = time.perf_counter()-started
        weights = np.exp(logits-np.max(logits))
        probs = weights / weights.sum()
        return {'label':label_map[labels[int(np.argmax(logits))]],
                'probabilities':{label_map[label]:float(prob) for label,prob in zip(labels,probs)},
                'tokens':len(encoded.ids),'inference_seconds':elapsed}
    # Independent warmup; neither its result nor text is an acceptance case.
    infer('The light is on.','The light is on.')
    for row in panel:
        started = time.perf_counter()
        result = infer(row['premise'],row['reply'])
        append(private / f'results-{threads}.jsonl',{'case_id':row['case_id'],**result,'pair_total_seconds':time.perf_counter()-started})
    write(private / f'backend-{threads}.json',{'ort_version':ort.__version__,'providers':session.get_providers(),
          'input_names':sorted(input_names),'labels':labels,'intra_threads':threads,'inter_threads':1,
          'execution':'ORT_SEQUENTIAL','graph_optimization':'ORT_ENABLE_ALL','load_seconds':load_seconds,
          'native_pair_template':True,'truncation':False,'padding':False})
    print(f'Completed31 NLI cases, CPU threads={threads}',flush=True)
    raise SystemExit(0)

assert (base / 'astra-nli-assets657/RESULT.json').exists()
asset_manifest = json.loads((base / 'astra-nli-assets657/RESULT.json').read_text(encoding='utf-8'))
assert all(sha(Path(row['path'])) == row['sha256'] for row in asset_manifest['verified'])
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
original = json.loads((private.parent / 'C03-native-fact-judge656-private/panel.json').read_text(encoding='utf-8'))
cases = [r for r in original if r['arm'] == 'greedy']
assert len(cases) == 31
spanish_ids = {'bounded-es','count-contradiction-es','installation-contradiction-es','unobserved-positive-es',
               'bounded-unknown-es','count-range-true','count-range-false','not-installed-true','not-installed-false',
               'abstention-es','conjunction-bad','windows-present-es','volume-good','volume-bad'}
panel = []
for r in cases:
    seen = r['facts']['observed']
    spanish = r['case_id'] in spanish_ids
    if 'requestedName' in seen:
        name = json.dumps(seen['requestedName'],ensure_ascii=False)
        if spanish:
            premise = (f'La observación corresponde a la aplicación {name}. '
                       f'{name} '+('está instalada. ' if seen['installed'] else 'no está instalada. ')+
                       f'Número de ventanas visibles de {name}: {seen["visibleWindowCount"]}. '
                       'No se comprobó si tiene procesos en ejecución. '
                       'Esta observación no informa sobre acciones realizadas.')
        else:
            premise = (f'This observation is about the application {name}. '
                       f'{name} '+('is installed. ' if seen['installed'] else 'is not installed. ')+
                       f'Number of visible windows of {name}: {seen["visibleWindowCount"]}. '
                       'Whether it has running processes was not checked. '
                       'This observation gives no information about actions performed.')
    elif 'level' in seen:
        premise = (f'El nivel de volumen observado es {seen["level"]}%. No hay información sobre acciones realizadas.'
                   if spanish else f'The observed volume level is {seen["level"]}%. There is no information about actions performed.')
    else:
        assert set(seen) == {'ramUsageMiB'}
        premise = f'The measured RAM usage is {seen["ramUsageMiB"]} MiB.'
    panel.append({'case_id':r['case_id'],'facts':r['facts'],'premise':premise,'reply':r['reply'],
                  'expected_label':r['expected_label'],'language':'es' if spanish else 'en','origin':r['origin']})
write(private / 'panel.json',panel)
write(out / 'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'cases':31,'profiles':[2,4],
    'method':'Official six-layer multilingual NLI ONNX FP32 on CPU, native premise/hypothesis pairs. One independent warmup, no case retries. Same31 hypotheses/expectations656; deterministic natural-language premises preserve field values and explicitly state observation limits. Per-case premise language is declared fixture metadata, not another tested classifier.',
    'criteria':'Exact three-way labels and supported/unsupported decision; false acceptance/rejection separately. Do not relax threshold, change labels, omit abstentions or promote on average score. Record every probability/token count and actual provider/thread configuration. No silent truncation.',
    'comparison_limit':'656 uses Qwen with structured JSON facts;658 uses a trained NLI model and native text premises. Two factors change, so differences cannot be attributed to model alone. This is appropriate-use candidate evaluation, not a single-factor causal ranking.',
    'source':'https://huggingface.co/MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli',
    'revision':'0a71e92a985b6e1ad1828cf67ce9c459639c1dca','model_sha256':sha(assets / 'onnx/model.onnx'),
    'tokenizer_sha256':sha(assets / 'tokenizer.json'),'panel_sha256':sha(private / 'panel.json'),
    'resource_limits':{'seconds_per_profile':180,'minimum_free_ram_mib':768,'device':'CPU only'},
    'runtime_modified':False,'ui_or_voice_or_product_credit':False})
import psutil
results = []
for threads in [2,4]:
    command = [sys.executable,'-X','utf8',__file__,'--worker',str(threads)]
    log_path = private / f'worker-{threads}.log'
    started = time.monotonic()
    peak = 0
    violations = []
    with log_path.open('w',encoding='utf-8') as log:
        child = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        append(out / 'PROCESSES.jsonl',{'threads':threads,'pid':child.pid,'command':command})
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
                    child.terminate()
                    break
                time.sleep(.05)
        finally:
            if child.poll() is None:
                child.terminate()
            code = child.wait(timeout=15)
    results.append({'threads':threads,'exit_code':code,'peak_rss_mib':peak/2**20,'seconds':time.monotonic()-started,'violations':violations})
    write(out / 'RESOURCES.json',results)
    assert code == 0 and not violations, results[-1]
    print(f'Completed CPU profile {threads}',flush=True)
print('Both profiles complete; adjudication required, not promoted.',flush=True)
