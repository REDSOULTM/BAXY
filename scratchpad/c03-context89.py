from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / 'src'), str(root)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

sys.stdout.reconfigure(encoding='utf-8')
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-context89'
out.mkdir(exist_ok=False)
source = base / 'astra-files86-negation/wire-19416.jsonl'
wire = [json.loads(s) for s in source.read_text(encoding='utf-8').splitlines()]
template = wire[6]['payload']
assert template['messages'][-1]['content'].startswith("Texto original de la persona: Why couldn't you read that file?")
cases = [
    ('empty_cause', "Why couldn't you read that file?", 'en',
        'Lee el archivo "c03-ausente.txt" del sandbox.',
        'No se encontró el archivo "c03-ausente.txt" en el sandbox.'),
    ('new_arithmetic', 'cuánto es doce por ocho', 'es', 'Pon el volumen.',
        '¿A qué nivel quieres que ponga el volumen?'),
    ('new_limits', 'cuáles son tus límites aquí', 'es', 'Qué es una subnet mask',
        'Una máscara de subred distingue la parte de red de la parte de host de una dirección IP.'),
    ('why_latency', '¿por qué importa?', 'es', 'Qué es la latencia de red',
        'La latencia de red es el tiempo que tarda un dato en llegar.'),
    ('new_checksum', 'Explain what a checksum is in one sentence.', 'en',
        'Lee el archivo "c03-ausente.txt" del sandbox.',
        'No se encontró el archivo "c03-ausente.txt" en el sandbox.'),
]
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
model = 'D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf'
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=model, BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
prereg = {'method': 'Native composer comparison, no functions/source change. First case is exact86 recovery payload '
    'and its actual preceding exchange. Other four are explicit technical controls based on historical no-replay '
    'test and current checksum control; not literal old-run reproductions or human reserve. Compare absent context '
    'with the previous exchange as JSON data inside situation, never an assistant turn or instruction. '
    'Same model/sampler/role prompt. Judge cause, topic isolation and context, not merely publication.',
    'cases': cases, 'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'model': model,
    'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest()}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
client = LlmRuntime(); gpu = ProcessTreeGpuSampler(os.getpid()); ram = RamSampler(os.getpid())
gpu.start(); ram.start(); started = time.monotonic()
try:
    client.start_warmup(); assert client.wait_warmup(90)
    for key, text, language, previous_request, previous_answer in cases:
        for variant in ('without_context', 'previous_exchange_data'):
            payload = copy.deepcopy(template)
            situation = {'kind': 'conversation'}
            if variant == 'previous_exchange_data':
                situation['previousExchange'] = {'request': previous_request, 'response': previous_answer}
            if key == 'empty_cause':
                payload['messages'][-1]['content'] = payload['messages'][-1]['content'].replace(
                    'situation: {"kind": "conversation"}',
                    'situation: ' + json.dumps(situation, ensure_ascii=False))
            else:
                payload['messages'][-1]['content'] = ('Texto original de la persona: ' + text + '\nsituation: '
                    + json.dumps(situation, ensure_ascii=False) + '\nMandatory language: '
                    + ('Spanish.' if language == 'es' else 'English.'))
            client.begin_request(40)
            try:
                response = client._post(payload)
            finally:
                client.end_request()
            row = {'case': key, 'variant': variant, 'payload': payload, 'response': response}
            with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            print(json.dumps({'case': key, 'variant': variant, 'choice': response['choices'][0]}, ensure_ascii=False), flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib,
        'ramPeakMiB': ram.peak_mib, 'registrationUnchanged': hashlib.sha256(reg.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
