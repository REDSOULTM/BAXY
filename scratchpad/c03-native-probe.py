"""Development-only paired prompt diagnostic; never product acceptance."""
import copy
import hashlib
import json
import os
import sys
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json').read_text())
model_option = next((name for name in ('qwen8','ministral','qwen35','qwen','gemma') if '--' + name in sys.argv), None)
if model_option:
    manifest['gguf'] = ({'qwen8':'D:/BAXY/experimental_assets_20260801/Qwen3-8B-Q4_K_M.gguf','ministral':'D:/BAXY/experimental_assets_20260730/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf','qwen35':'D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf'}.get(model_option) or str(Path(manifest['gguf']).parent / {'qwen':'Qwen3-4B-Q4_K_M.gguf','gemma':'gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf'}[model_option]))
    with open(manifest['gguf'], 'rb') as model_file:
        manifest['gguf_sha256'] = hashlib.file_digest(model_file, 'sha256').hexdigest()
if model_option == 'qwen8':
    manifest['ngl'] = 20
for key, env in [('gguf','BAXY_MIND_LLM_GGUF'), ('llama_server','BAXY_MIND_LLAMA_SERVER'), ('ngl','BAXY_MIND_NGL')]:
    os.environ[env] = str(manifest[key])
if '--q8' in sys.argv:
    os.environ['BAXY_MIND_KV_CACHE_TYPE'] = 'q8_0'
from baxy_mind.llm import LlmRuntime
from baxy_mind.request_reading import read_request
from scripts.measure_mind_budget import ProcessTreeGpuSampler

CASES = [
    ('cuánto es doce por ocho', None),
    ('cuánto es diecisiete más veintiséis', None),
    ('What is fourteen times six?', None),
    ('explain what DNS caching is in one sentence', None),
    ('why does it matter?', 'DNS caching'),
    ('explícame qué es un router en una frase', None),
    ('¿y para qué sirve?', 'router'),
    ('¿por qué importa?', 'latencia de red'),
    ('¿y por qué se usa?', 'proxy'),
    ('Explica qué es un checksum en una frase', None),
    ('Explain encryption, pero en simple', None),
    ('Qué es una backup copy, en simple', None),
]

class Probe(LlmRuntime):
    seed = 1
    captures = None
    def _server_command(self):
        command = super()._server_command()
        if '--thinking' in sys.argv:
            command[command.index('--reasoning') + 1] = 'auto'
            command[command.index('--reasoning-budget') + 1] = '-1' if '--natural-stop' in sys.argv else '512'
            command.extend(['--reasoning-format', 'deepseek'])
        return command
    def _post(self, payload, **kwargs):
        payload = copy.deepcopy(payload)
        if '--answer-question' in sys.argv:
            for message in payload.get('messages', []):
                message['content'] = message['content'].replace(
                    'Explain the concept in one short sentence.',
                    "Answer the person's actual question directly.",
                )
        payload['seed'] = self.seed
        if model_option == 'ministral':
            payload.update(temperature=0.05, top_p=0.95)
        if model_option == 'qwen8':
            payload.update(temperature=0.7, top_p=0.8, top_k=20, min_p=0.0)
        if model_option == 'qwen35':
            payload.update(temperature=1.0 if '--thinking' in sys.argv else 0.7,
                top_p=0.95 if '--thinking' in sys.argv else 0.8, top_k=20, min_p=0.0, presence_penalty=1.5)
        if '--thinking' in sys.argv:
            payload['chat_template_kwargs'] = {'enable_thinking':True}
            if '--natural-stop' in sys.argv:
                payload['max_tokens'] = 2048
            else:
                payload['chat_template_kwargs']['low_effort'] = True
                payload['max_tokens'] += 768
        self.captures.append(payload)
        return super()._post(payload, **kwargs)

suffix = model_option or ('thinking' if '--thinking' in sys.argv else 'probe')
if model_option and '--thinking' in sys.argv:
    suffix += '-thinking'
if '--q8' in sys.argv:
    suffix += '-q8'
if '--bare' in sys.argv:
    suffix += '-bare'
tag = next((value.removeprefix('--tag=') for value in sys.argv if value.startswith('--tag=')), '')
if tag:
    assert tag.replace('-', '').isalnum()
    suffix += '-' + tag
out = ROOT / ('artifacts/comprobaciones/C03/astra-native-' + suffix)
out.mkdir(exist_ok='--resume' in sys.argv)
prereg = {'cases':CASES,'purpose':'Separate composition scaffolding from local model capability; all cases development forever','manifest':manifest,'argv':sys.argv[1:],'sourceHashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['src/baxy_mind/llm.py','src/baxy_mind/request_reading.py']},'ministralProfile':{'temperature':0.05,'top_p':0.95,'source':'https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512-GGUF#recommended-settings'} if model_option == 'ministral' else None,'qwen8Profile':{'temperature':0.7,'top_p':0.8,'top_k':20,'min_p':0,'source':'https://huggingface.co/Qwen/Qwen3-8B#best-practices','hypothesis':'A larger inherited model with partial GPU offload may improve semantics while fitting the 4 GB ceiling; previous rejection measured tool selection, not this content task.'} if model_option == 'qwen8' else None}
prereg['probeSha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
prereg['diagnosticOverride'] = 'Replace concept explanation instruction with answering actual question in captured payload only' if '--answer-question' in sys.argv else None
prereg['concurrentWork'] = 'Full Python suite; timing is observational and not comparable to isolated measurements' if '--concurrent-full' in sys.argv else None
prereg['reasoningHypothesis'] = 'Previous forced 512-token stop leaked unfinished reasoning into content. Preserve natural end of thinking, bounded by 2048 output tokens and 60-second request, q8 cache. No model promotion.' if '--natural-stop' in sys.argv else None
completed = set()
if '--resume' in sys.argv:
    original = json.loads((out/'PREREGISTRO.json').read_text(encoding='utf-8'))
    assert original['sourceHashes'] == prereg['sourceHashes'] and original['manifest'] == manifest
    completed = {(row['id'], row['arm']) for row in map(json.loads, (out/'results.jsonl').read_text(encoding='utf-8').splitlines())}
    (out/'RESUMPTION.json').write_text(json.dumps({'reason':'stdout encoding failure after results were persisted; fresh process resumes only missing independent diagnostic calls','completedPairs':sorted(completed),'previousGpu':json.loads((out/'gpu.json').read_text())}),encoding='utf-8')
else:
    (out/'PREREGISTRO.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
client = Probe()
gpu = ProcessTreeGpuSampler(os.getpid())
gpu.start()
try:
    client._ensure_started()
    (out/'llama-command.json').write_text(json.dumps(client._server_command()), encoding='utf-8')
    for index, (question, subject) in enumerate(CASES):
        if gpu.peak_mib and gpu.peak_mib > 4096:
            raise RuntimeError('Native runtime exceeds BAXY 4 GB ceiling')
        for arm in (['current'] if '--current-only' in sys.argv else ['direct'] if '--bare' in sys.argv else ['current', 'direct']):
            if (index + 1, arm) in completed:
                continue
            client.seed = index + 1
            client.captures = []
            client.begin_request(60 if '--natural-stop' in sys.argv else 35, identity=f'probe-{index}-{arm}')
            started = time.monotonic()
            response = None
            error = None
            language = read_request(question).language
            try:
                if arm == 'current':
                    facts = {'situation':'{"kind":"conversation","polarity":"success"}'}
                    if subject:
                        facts['priorRequests'] = [f'explain what {subject} is in one sentence']
                    response = client.compose_user_message(question, 'conversation', facts)
                else:
                    instruction = ('Eres BAXY, un compañero local. Responde directamente y con brevedad a lo que pregunta la persona. '
                        'No afirmes haber ejecutado acciones ni observado este PC. ' +
                        {'es':'Responde en español.', 'en':'Answer in English.', 'mixed':'Conserva el spanglish de la persona.'}[language])
                    if subject:
                        instruction += '\nTema de la pregunta, tomado del pedido anterior: ' + json.dumps(subject, ensure_ascii=False)
                    messages = ([{'role':'user','content':((f'Context: {subject}. ' if subject else '') + question)}] if '--bare' in sys.argv else [{'role':'system','content':instruction},{'role':'user','content':question}])
                    response = client._post({'messages':messages,
                        'temperature':1.0,'top_p':0.95,'max_tokens':256,'cache_prompt':False,
                        'chat_template_kwargs':{'enable_thinking':False}})
            except Exception as exc:
                error = type(exc).__name__ + ': ' + str(exc)
            finally:
                client.end_request()
            row = {'id':index+1,'arm':arm,'question':question,'subject':subject,'response':response,'error':error,
                'seconds':round(time.monotonic()-started,3),'payloads':client.captures}
            with (out/'results.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(row,ensure_ascii=False)+'\n')
            public = response['choices'][0]['message'].get('content') if isinstance(response, dict) else response
            print(json.dumps({'id':index+1,'arm':arm,'response':public,'error':error,'seconds':row['seconds']},ensure_ascii=True),flush=True)
finally:
    gpu.stop()
    (out/'gpu.json').write_text(json.dumps({'peakMiB':gpu.peak_mib,'telemetryAvailable':gpu.telemetry_available,'scope':'diagnostic Python and children, not full installed BAXY'}), encoding='utf-8')
    client.close()
