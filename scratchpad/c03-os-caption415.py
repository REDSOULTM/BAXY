"""Measure existing literal-fact transport on private read results, no source edit."""
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / 'src')]
import psutil
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

out = root / 'artifacts/comprobaciones/C03/astra-os-caption415'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-os-caption415-private'
source = private.parent / 'C03-account-product411-private'
audit = [json.loads(line) for line in (source / 'compose-audit.jsonl').open(encoding='utf-8-sig')]
wire = [json.loads(line) for line in (source / 'http-posts.jsonl').open(encoding='utf-8-sig')]
row = next(r for r in audit if r['trace'] == 't5' and r['stage'] == 'first')
payload = next(r['payload'] for r in wire if r.get('stage') == 'request'
               and 'majorVersion' in r['payload']['messages'][-1].get('content', '')
               and r['payload']['messages'][-1]['content'].startswith('Which Windows version am I running?'))
observed = json.loads((root / 'artifacts/comprobaciones/C03/astra-account-product411/OS_OBSERVATION.json').read_text(encoding='utf-8'))
actual = {'id': 'actual411-windows11-en', 'request': payload['messages'][-1]['content'].split('\nsituation:')[0],
          'situation': json.loads(row['situation']), 'reference': payload,
          'origin': 'actual411/t5 and independent local CIM OS_OBSERVATION', 'caption': observed['caption'],
          'expected': 'Report Windows11 Home Single Language, not Windows10 inferred from NTmajor10; keep the observed build if mentioned.'}
cases = [actual]
for identifier, request, caption, build, workstation in [
    ('windows11-es', '¿Qué versión de Windows tengo?', observed['caption'], 26200, True),
    ('windows10-en', 'Which version of Windows is this?', 'Microsoft Windows 10 Enterprise', 19045, True),
    ('server2022-es', '¿Qué Windows tiene este servidor?', 'Microsoft Windows Server 2022 Standard', 20348, False),
]:
    case = copy.deepcopy(actual)
    case.pop('reference')
    case.update(id=identifier, request=request, caption=caption,
                origin='synthetic development OS snapshot/request; not a measurement of this PC',
                expected='Report the supplied OS caption without converting NTmajor10 into a marketing release.')
    case['situation']['observed']['os'].update(buildNumber=build, isWorkstation=workstation)
    cases.append(case)

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def facts(case, variant):
    situation = copy.deepcopy(case['situation'])
    if variant == 'caption':
        situation['observed']['os']['caption'] = case['caption']
    return {'situation': json.dumps(situation, ensure_ascii=False)}


for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):
        os.environ.pop(key)
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(manifest.read_text(encoding='utf-8-sig'))
model = Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'],
                  BAXY_MIND_NGL=str(config['ngl']))

class Captured(Exception):
    pass

class Offline(LlmRuntime):
    def _post(self, payload, *args, **kwargs):
        assert payload == self.reference, 'reconstructed baseline differs from captured411'
        raise Captured()

offline = Offline()
try:
    for case in [c for c in cases if 'reference' in c]:
        offline.reference = case['reference']
        try:
            offline.compose_user_message(case['request'], 'status', facts(case, 'baseline'))
        except Captured:
            pass
        else:
            raise AssertionError('no captured baseline')
finally:
    offline.close()

out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'cases': cases,
    'method': 'Four guarded compose_user_message cases; baseline versus only observed.os.caption. Actual411T5 baseline must equal its captured native payload offline and live. Caption for actual case is independently observed via local CIM; remaining ES/Windows10/Server2022 cases are explicitly synthetic controls. Same prompt/model/sampler/guards, no response injection, source change, extra tool role, product effect or promotion. Measure whether conveying the existing Windows caption prevents marketing-version hallucination before adding a provider read.',
    'inheritance': 'biblioteca/carter/carter_v5/microagents/windows_commands.md:23-32 uses Windows system commands but does not solve OS marketing naming. Current WindowsSystemStatusProbe.ReadOperatingSystem169 uses RtlGetVersion numbers only. Current ExternalProcessRunner and DeviceControlAdapter already bound local PowerShell/CIM; reuse if needed, no new dependency or copied obsolete WMIC. Primary Microsoft OSVERSIONINFOEXW table lists Windows10 and11 both10.0; Win32_OperatingSystem.Caption is the observed OS description.411 CIM independently confirmed Windows11, version10.0.26200.',
    'sources': ['https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/ns-wdm-_osversioninfoexw', 'https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-operatingsystem'],
    'criteria': 'All four outputs identify the supplied actual/synthetic OS release and edition without misreading NTversion as marketingversion. Do not count a literal match alone, a blank reply or a technical payload dump as useful. No provider implementation before this compositional comparison and real CIM mechanism are understood.',
    'limits': {'gpu_stop_mib': 3800, 'minimum_free_ram_mib': 768, 'request_seconds': 40},
    'model': str(model), 'model_sha256': sha(model), 'backend_sha256': sha(config['llama_server']),
    'source_sha256': sha(root / 'src/baxy_mind/llm.py'), 'manifest_sha256': sha(manifest), 'private': str(private)}
assert prereg['model_sha256'] == '00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
os.environ.update(BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private / 'compose-audit.jsonl'), BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1')

class Measured(LlmRuntime):
    case = None
    def _post(self, payload, *args, **kwargs):
        if self.case and self.first:
            self.first = False
            if self.variant == 'baseline' and 'reference' in self.case:
                assert payload == self.case['reference']
        response = super()._post(payload, *args, **kwargs)
        with (private / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'id': self.case['id'] if self.case else None,
                                     'variant': getattr(self, 'variant', None), 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
        return response

client = Measured()
gpu, ram = ProcessTreeGpuSampler(os.getpid()), RamSampler(os.getpid())
stop = threading.Event()
violations = []
complete = False
started = time.monotonic()
def guard():
    while not stop.wait(0.25):
        if gpu.peak_mib is not None and gpu.peak_mib >= 3800:
            violations.append('owned_gpu_conservative_bound')
        if psutil.virtual_memory().available < 768 * 2**20:
            violations.append('system_free_ram_bound')
        if violations:
            client.close()
            return
watch = threading.Thread(target=guard, daemon=True)
try:
    gpu.start()
    ram.start()
    watch.start()
    client.start_warmup()
    assert client.wait_warmup(90)
    assert gpu.telemetry_available and gpu.peak_mib is not None
    (out / 'command.json').write_text(json.dumps(client._server_command(), indent=2) + '\n', encoding='utf-8')
    for case in cases:
        for variant in ['baseline', 'caption']:
            client.case, client.variant, client.first = case, variant, True
            before = time.monotonic()
            client.begin_request(40)
            try:
                answer = client.compose_user_message(case['request'], 'status', facts(case, variant))
                error = None
            except (RuntimeError, TimeoutError) as exc:
                answer, error = None, str(exc)
            finally:
                client.end_request()
            row = {'id': case['id'], 'variant': variant, 'request': case['request'],
                   'answer': answer, 'error': error, 'seconds': round(time.monotonic() - before, 3)}
            with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            print(json.dumps(row, ensure_ascii=True), flush=True)
    complete = True
finally:
    stop.set()
    client.close()
    watch.join(timeout=5)
    gpu.stop()
    ram.stop()
    resources = {'completed': complete, 'violations': violations, 'gpu_peak_mib': gpu.peak_mib,
                 'gpu_telemetry_available': gpu.telemetry_available, 'ram_peak_mib': ram.peak_mib,
                 'seconds': round(time.monotonic() - started, 3), 'manifest_unchanged': sha(manifest) == prereg['manifest_sha256']}
    (out / 'resources.json').write_text(json.dumps(resources, indent=2) + '\n', encoding='utf-8')
assert complete and not violations and resources['manifest_unchanged']
