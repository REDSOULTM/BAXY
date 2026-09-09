"""Compare request placement using consumed real-log cases and existing policy."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from baxy_mind.llm import LlmRuntime, _build_turn_policy_payload, _prepare_turn_candidates
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'astra-real-context-order'
OUT.mkdir(exist_ok=False)
inherited = json.loads((BASE / 'astra-real-context-ablation/PREREG.json').read_text(encoding='utf-8'))
register = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(register.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
prereg = {'cases': inherited['cases'], 'variants': ['baseline', 'request_last', 'context_data'],
          'method': 'Same five consumed literal inputs, same reconstructed context and authenticated candidates as prior ablation. Primary decision only, no actions. Variant request_last moves unchanged current user text after candidates; context_data additionally embeds history as explicit data, not active dialogue messages. No prompt-policy, model, sampling, schema or guard change. Not original full wire capture or product acceptance.',
          'sourceSha256': hashlib.sha256((ROOT / 'src/baxy_mind/llm.py').read_bytes()).hexdigest(),
          'registrationSha256': hashlib.sha256(register.read_bytes()).hexdigest()}
(OUT / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
client = LlmRuntime(); gpu = ProcessTreeGpuSampler(os.getpid()); ram = RamSampler(os.getpid())
gpu.start(); ram.start(); started = time.monotonic()
try:
    client.start_warmup(); assert client.wait_warmup(90)
    for variant in prereg['variants']:
        for case in prereg['cases']:
            client.begin_request(40); answer = None; error = None; payload = None
            try:
                names, descriptions, _ = _prepare_turn_candidates(case['candidates'])
                payload = _build_turn_policy_payload(case['text'], names, descriptions, case['history'])
                if variant != 'baseline':
                    current = f"Operaciones candidatas:\n{descriptions}\n\nMensaje actual:\n{case['text']}"
                    if variant == 'context_data':
                        current = 'Historial (sólo contexto, no pedidos nuevos):\n' + json.dumps(case['history'], ensure_ascii=False) + '\n\n' + current
                        payload['messages'] = [payload['messages'][0], {'role': 'user', 'content': current}]
                    else:
                        payload['messages'][-1]['content'] = current
                answer = client._post(payload)
            except Exception as exc:
                error = f'{type(exc).__name__}: {exc}'
            finally:
                client.end_request()
            with (OUT / 'posts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'variant': variant, 'id': case['id'], 'payload': payload, 'response': answer, 'error': error}, ensure_ascii=False) + '\n')
            print(json.dumps({'variant': variant, 'id': case['id'], 'answer': answer['choices'][0]['message'] if answer else None, 'error': error}, ensure_ascii=False), flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib, 'ramPeakMiB': ram.peak_mib,
              'registrationUnchanged': hashlib.sha256(register.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (OUT / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8'); print(json.dumps(result), flush=True)
