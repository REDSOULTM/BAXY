"""Native selection isolation; proposals only, no audio effects."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / 'src'), str(root)]
from baxy_mind.llm import LlmRuntime, _prepare_turn_candidates
from baxy_mind.effect_intent import resolve_explicit_effects, resolve_explicit_clarification_intent
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler, current_core_catalog_snapshot

base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-incomplete-volume46'
out.mkdir(exist_ok=True)
assert not (out / 'PREREG.json').exists()
source = base / 'astra-routes-regression46'
paired = json.loads((source / 'paired.json').read_text(encoding='utf-8'))
audit = [json.loads(line) for line in (source / 'turn-audit.jsonl').open(encoding='utf-8')]
observed = next(r for r in audit if r.get('request_id') == '79' and r.get('phase') == 'raw_attempt')
catalog, _, _ = current_core_catalog_snapshot(root / 'src/Baxy.Core/bin/Release/net10.0-windows10.0.19041.0/win-x64/publish/baxy-core.exe')
by_name = {row['name']: row for row in catalog}
candidates = [{'name': name, 'description': by_name[name]['description'], 'arguments_schema': by_name[name]['argumentsSchema']} for name in observed['candidate_operations']]
names, _, contracts = _prepare_turn_candidates(candidates)
history = [message for row in paired[19:22] for message in (
    {'role': 'user', 'content': row['request']}, {'role': 'assistant', 'content': row['final']})]
cases = [
    ('Ajusta el volumen.', 'clarify'),
    ('Set the volume.', 'clarify'),
    ('Set the volume, por favor.', 'clarify'),
    ('Pon el volumen.', 'clarify'),
    ('Sube el volumen.', 'clarify'),
    ('¿A qué volumen está?', 'audio.status'),
    ('Ajusta el volumen al 80%.', 'audio.volume'),
    ('Ajusta el volumen de ventas.', 'not_audio'),
]
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
prereg = {'cases': cases, 'history': history, 'candidates': candidates,
    'method': 'Consumed and synthetic diagnostic controls; not reserve. Exact t23 candidate identities and current catalog contracts. Native selector with reconstructed last three public pairs, then same selector without history: one difference, no prompt or source edit. Captures actual HTTP payloads and responses. No functions execute. Literal reader inspected alongside native result; removing history is diagnostic, not a proposal to discard references.',
    'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest(),
    'sourceHashes': {str(p): hashlib.sha256((root / p).read_bytes()).hexdigest() for p in ['src/baxy_mind/llm.py', 'src/baxy_mind/effect_intent.py', 'scratchpad/c03-incomplete-volume46.py']}}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')

class Client(LlmRuntime):
    stage = ''
    case = ''
    def _post(self, payload, *args, **kwargs):
        response = super()._post(payload, *args, **kwargs)
        with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'stage': self.stage, 'case': self.case, 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
        return response

client = Client()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start(); ram.start()
started = time.monotonic()
try:
    client.start_warmup()
    assert client.wait_warmup(90)
    for stage in ('reconstructed_history', 'without_history'):
        client.stage = stage
        for text, expected in cases:
            client.case = text
            client.begin_request(60)
            try:
                result = client._post_native_tool_selection(text, names, contracts, history if stage == 'reconstructed_history' else [])
            finally:
                client.end_request()
            row = {'stage': stage, 'text': text, 'expected': expected, 'answer': result,
                'literalEffect': repr(resolve_explicit_effects(text, by_name)),
                'literalClarification': repr(resolve_explicit_clarification_intent(text, by_name))}
            with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            print(json.dumps(row, ensure_ascii=False), flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib,
        'ramPeakMiB': ram.peak_mib, 'registrationUnchanged': hashlib.sha256(reg.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
