"""Contrast native selector reference dependence without executing any tool."""
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

base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-selector-references68'
out.mkdir(exist_ok=False)
wire_path = base / 'astra-files64-wire/wire-29264.jsonl'
packets = [json.loads(line) for line in wire_path.read_text(encoding='utf-8').splitlines()]
template = [row['payload'] for row in packets if row['payload'].get('tool_choice') == 'auto'][1]
cases = [
    ('Sí, hazlo.', '¿Qué podemos hacer con el informe?',
     'Puedo leer el contenido de informe.txt. ¿Quieres que lo lea?', 'filesystem.read.text'),
    ('Yes, do that.', 'Can you help me with my report?',
     'I can search for a file named report.txt. Shall I search for it?', 'filesystem.search'),
    ('Ahora léelo.', 'Busca informe.txt.',
     'Encontré informe.txt.', 'filesystem.read.text'),
    ('Read the second one.', 'Search for the reports.',
     'I found report-a.txt and report-b.txt.', 'filesystem.read.text'),
    ('No, solo búscalo.', 'Lee informe.txt.',
     'Estoy preparando la lectura de informe.txt.', 'filesystem.search'),
    ('¿Por qué no pudiste?', 'Lee informe.txt.',
     'No pude leer el archivo porque la búsqueda no admite rutas absolutas.', None),
]
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'],
                  BAXY_MIND_NGL=str(config['ngl']))
prereg = {'method': 'Six explicitly synthetic reference controls. Reuse the exact declared tool shortlist and '
          'native selector prompt/parameters captured for files64 t2. Change only the technical test dialogue/current '
          'request, then compare full prior dialogue, only previous user text and no prior dialogue. '
          'Expected operations are selection-only; no handler runs, authorization, UI, audio or human reserve claim. '
          'Measure whether removing previous assistant prose loses necessary effect references before any source change.',
          'cases': cases, 'wireSha256': hashlib.sha256(wire_path.read_bytes()).hexdigest(),
          'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest()}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
client = LlmRuntime()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start(); ram.start()
started = time.monotonic()
try:
    client.start_warmup(); assert client.wait_warmup(90)
    for index, (current, user, assistant, expected) in enumerate(cases, 1):
        for variant in ('full', 'user_history_only', 'no_context'):
            payload = copy.deepcopy(template)
            history = [{'role': 'user', 'content': user}, {'role': 'assistant', 'content': assistant}]
            if variant == 'user_history_only':
                history = history[:1]
            elif variant == 'no_context':
                history = []
            payload['messages'][-1]['content'] = json.dumps({
                'previous_dialogue_for_references_only': history,
                'current_request_to_interpret': current}, ensure_ascii=False)
            client.begin_request(40)
            try:
                response = client._post(payload)
            finally:
                client.end_request()
            with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'turn': f't{index}', 'text': current, 'variant': variant,
                    'expected': expected, 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
            message = response['choices'][0]['message']
            print(json.dumps({'turn': index, 'variant': variant,
                'operations': [c['function']['name'] for c in message.get('tool_calls', [])],
                'content': message.get('content')}, ensure_ascii=False), flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib,
        'ramPeakMiB': ram.peak_mib,
        'registrationUnchanged': hashlib.sha256(reg.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
