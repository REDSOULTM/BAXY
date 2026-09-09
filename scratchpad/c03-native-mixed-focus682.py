"""Locate the mixed-window wording defect in native drafts, before validation."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix = source[:source.index("history = [{'role'")]
prefix = prefix.replace('astra-native-subject612', 'astra-native-mixed-focus682').replace('C03-native-subject612-private', 'C03-native-mixed-focus682-private')
exec(compile(prefix, __file__, 'exec'))
from baxy_mind.llm import _compose_situation_payload

class Captured(Exception):
    pass

class Builder(LlmRuntime):
    def __init__(self):
        self._gguf = config['gguf']

    def _post(self, payload, **kwargs):
        self.payload = copy.deepcopy(payload)
        raise Captured()

previous = private.parent / 'C03-survey-focus679-private'
with (previous / 'compose-audit.jsonl').open(encoding='utf-8-sig') as stream:
    original = next(r for line in stream if (r := json.loads(line)).get('trace') == 't4')
observed = json.loads(original['situation'])
cases = [
    ('mixed-original', 'Baxy, ¿qué window tiene focus ahora?', 'ChatGPT'),
    ('mixed-renamed', 'Baxy, ¿qué window tiene focus ahora?', 'Órbita 29'),
    ('mixed-other-name', 'Baxy, ¿qué window tiene focus ahora?', 'Atlas'),
    ('spanish-control', 'Ahora mismo, ¿qué ventana tiene el foco?', 'ChatGPT'),
    ('english-control', 'Which window is active right now?', 'ChatGPT'),
]
panel = []
for case_id, text, name in cases:
    facts = copy.deepcopy(observed)
    facts['observed']['windows'][0].update(title=name, processName=name)
    client = Builder()
    try:
        client.compose_user_message(text, 'status', {'situation': facts})
    except Captured:
        full = client.payload
    else:
        raise AssertionError('First compositor request was not captured')
    language = 'en' if case_id == 'english-control' else 'es'
    projected = _compose_situation_payload(facts, language, text)
    minimal = [{'role': 'user', 'content': text + '\nObserved facts: ' + json.dumps(projected, ensure_ascii=False)}]
    for arm, messages in [
        ('native_facts', minimal),
        ('identity_facts', [{'role': 'system', 'content': SYSTEM_PROMPT}, *minimal]),
        ('compositor', full['messages']),
    ]:
        payload = {**copy.deepcopy(full), 'messages': copy.deepcopy(messages)}
        panel.append({'case_id': case_id, 'text': text, 'name': name, 'language': language,
            'arm': arm, 'facts': facts, 'payload': payload,
            'criterion': 'Identify the observed active software window with natural ES/EN wording; no architectural-window nouns, metadata, invented states or wrong names.'})
assert len(panel) == 15
assert psutil.virtual_memory().available >= 1800 * 2**20
write(private / 'panel.json', panel)
runner = source[source.index('command = json.loads'):]
start = runner.index("write(out / 'PREREG.json', {")
end = runner.index("log = (private / 'launch.log')", start)
runner = runner[:start] + '''write(out / 'PREREG.json', {
    'utc':datetime.now(timezone.utc).isoformat(),'cases':5,'arms':3,'calls':15,
    'method':'Exact mixed679 input/observation, two explicitly synthetic name substitutions, and two prior language controls. Native facts, identity plus facts, and first request built by actual compositor. Registered greedy sampling held fixed. No validator/retry, answer replacement, backend override, kernel/UI or survey credit.',
    'criteria':'Individually assess active software-window identity, natural wording and requested language. The original compositor arm must reproduce679 before attributing its lexical defect. Ablations diagnose prompt roles; they are not product alternatives.',
    'inheritance':'679 mixed draft uses ventanal; coverage validator separately misses inverted subject.680 only fixes title-relative scope.670 previously showed native Boolean confusion; this is a distinct observed software-window lexical defect, not another Boolean prompt sweep.',
    'research_reused':'Official Qwen2507 non-thinking profile and Microsoft foreground semantics inherited670. Keep effective registered settings for causal isolation; no claim of optimality or model exclusion from defaults.',
    'command':command,'manifest_sha256':manifest_sha,'model_sha256':sha(config['gguf']),
    'server_sha256':sha(command[0]),'source_sha256':sha(root/'src/baxy_mind/llm.py'),
    'window_fact_source_sha256':sha(root/'src/baxy_mind/window_prose_facts.py'),
    'panel_sha256':sha(private/'panel.json'),'source_modified':False,'source_adopted':False,
    'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240},
})
''' + runner[end:]
runner = runner.replace('Collected40 native subject-attribution drafts; adjudication pending.', 'Collected15 mixed-focus native drafts; adjudication pending.')
exec(compile(runner, __file__, 'exec'))
