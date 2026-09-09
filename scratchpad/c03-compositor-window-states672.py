"""Exercise native generation plus the actual compositor fact/retry boundary."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix = source[:source.index("history = [{'role'")]
prefix = prefix.replace('astra-native-subject612', 'astra-compositor-window-states672').replace('C03-native-subject612-private', 'C03-compositor-window-states672-private')
exec(compile(prefix, __file__, 'exec'))
previous = json.loads((private.parent / 'C03-native-window-projection668-private/panel.json').read_text(encoding='utf-8'))
panel = [{**copy.deepcopy(row), 'arm':'compositor671'} for row in previous if row['arm'] == 'projection667']
assert len(panel) == 14
assert psutil.virtual_memory().available >= 1800*2**20
write(private / 'panel.json', panel)

class NativeCompositor(LlmRuntime):
    def __init__(self, case):
        self._gguf = config['gguf']
        self.case = case
        self.calls = 0

    def _post(self, payload):
        self.calls += 1
        append(private / 'requests.jsonl', {'case_id':self.case['case_id'], 'call':self.calls, 'payload':payload})
        request = urllib.request.Request(url+'/v1/chat/completions', data=json.dumps(payload, ensure_ascii=False).encode(), headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
        append(private / 'responses.jsonl', {'case_id':self.case['case_id'], 'call':self.calls, 'response':result})
        assert not violations
        return result

runner = source[source.index('command = json.loads'):]
start = runner.index("write(out / 'PREREG.json', {")
end = runner.index("log = (private / 'launch.log')", start)
runner = runner[:start] + '''write(out / 'PREREG.json', {
    'utc':datetime.now(timezone.utc).isoformat(),'cases':14,
    'method':'Same14 fixture requests668. Real LlmRuntime.compose_user_message with native local transport, existing fact validators and retry contract. No mocked answer or new reply text. Compare all first drafts and final outputs; no kernel/UI/voice.',
    'criteria':'Judge final truth, completeness and language, preserve ten original controls. Three unambiguous focus contradictions must not be published. Empty output is a failed answer, never acceptance. Ambiguous English conjunction/completeness remains a distinct limit and must be adjudicated.',
    'inheritance':'668 original10/10 but compound0/4;670 confuses visible/normal with focus already in native model.671 bounded focus assertions now checked in existing contract;662 focused tests pass including uncertainty, titles, conditionals and actual compositor with injected drafts.',
    'command':command,'manifest_sha256':manifest_sha,'model_sha256':sha(config['gguf']),
    'server_sha256':sha(command[0]),'source_sha256':sha(root/'src/baxy_mind/llm.py'),
    'window_fact_source_sha256':sha(root/'src/baxy_mind/window_prose_facts.py'),
    'panel_sha256':sha(private/'panel.json'),'source_adopted':False,
    'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240},
})
''' + runner[end:]
start = runner.index('    for row in panel:')
end = runner.index('    complete=True', start)
runner = runner[:start] + '''    for row in panel:
        client = NativeCompositor(row)
        begin = time.monotonic()
        final = client.compose_user_message(row['text'], 'status', row['facts'])
        append(private / 'finals.jsonl', {'case_id':row['case_id'], 'text':row['text'], 'final':final, 'calls':client.calls, 'seconds':time.monotonic()-begin})
        print(row['case_id']+' calls='+str(client.calls)+' nonempty='+str(bool(final)), flush=True)
''' + runner[end:]
runner = runner.replace('Collected40 native subject-attribution drafts; adjudication pending.', 'Collected14 compositor outcomes; adjudication pending.')
exec(compile(runner, __file__, 'exec'))
