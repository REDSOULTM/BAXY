"""Isolate schema-literal leakage in the existing first-draft writer."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix = source[:source.index("history = [{'role'")]
prefix = prefix.replace('astra-native-subject612','astra-native-schema-prose662').replace('C03-native-subject612-private','C03-native-schema-prose662-private')
exec(compile(prefix,__file__,'exec'))
from baxy_mind.llm import _compose_situation_payload

observed_audit = private.parent / 'C03-window-facts-product661-private/compose-audit.jsonl'
with observed_audit.open(encoding='utf-8-sig') as stream:
    original = [row for line in stream if (row := json.loads(line)).get('trace') == 't24' and row.get('stage') == 'first']
assert len(original) == 1 and original[0]['published']
original = original[0]
base_situation = json.loads(original['situation'])

class Captured(Exception): pass
class Builder(LlmRuntime):
    def __init__(self): self._gguf = config['gguf']
    def _post(self,payload,**kwargs):
        self.payload = copy.deepcopy(payload)
        raise Captured()

cases = [
    ('observed661','Baxy, ¿qué ventana está activa ahora?','ChatGPT','maximized','es'),
    ('focus-short-es','¿Qué ventana está activa?','ChatGPT','maximized','es'),
    ('focus-en','Baxy, which window has focus now?','ChatGPT','maximized','en'),
    ('name-state-es','¿Qué ventana está en primer plano?','Órbita 23','normal','es'),
    ('name-state-en','Which window is in the foreground?','Orbit 23','normal','en'),
    ('state-question-es','¿Está maximizada la ventana activa?','Brújula','normal','es'),
    ('state-question-en','Is the active window maximized?','Sundial','maximized','en'),
    ('literal-name-es','¿Qué ventana está activa?','Foreground','normal','es'),
]
fixtures = []
for case_id,text,name,state,language in cases:
    situation = copy.deepcopy(base_situation)
    window = situation['observed']['windows'][0]
    window.update(processName=name,title=name,state=state)
    fixtures.append((case_id,text,language,situation))
for language,name,text in [('es','Órbita 23','¿Cuántas ventanas de Órbita 23 están abiertas?'),('en','Orbit 23','How many windows of Orbit 23 are open?')]:
    fixtures.append(('app-control-'+language,text,language,{
        'kind':'operation','operation':'window.application.status','polarity':'success','verified':True,'succeeded':True,
        'observed':{'requestedName':name,'displayName':name,'installed':True,'visibleWindowCount':3,'hasVisibleWindow':True}}))
instruction = (' Field names and enum values describe observations; express their meaning in everyday language in the requested language. '
               'They are not literal text to copy. Preserve proper names, titles, paths and measured values exactly; do not translate those names or invent facts.')
panel = []
for case_id,text,language,situation in fixtures:
    facts = {'situation':json.dumps(situation,ensure_ascii=False)}
    if case_id == 'observed661':
        facts['situation'] = original['situation']
        assert situation == base_situation
        assert _compose_situation_payload(situation,language,text) == original['payload']
    client = Builder()
    try:
        client.compose_user_message(text,'status',facts)
    except Captured:
        pass
    else:
        raise AssertionError('Missing first request')
    for arm in ['current','schema_semantics','documented_profile']:
        payload = copy.deepcopy(client.payload)
        if arm == 'schema_semantics':
            payload['messages'][0]['content'] += instruction
        elif arm == 'documented_profile':
            payload.update(temperature=0.7,top_p=0.8,top_k=20,min_p=0.0,seed=0)
        panel.append({'case_id':case_id,'text':text,'language':language,'facts':facts,'arm':arm,'payload':payload})
write(private / 'panel.json',panel)
runner = source[source.index('command = json.loads'):]
start = runner.index("write(out / 'PREREG.json', {")
end = runner.index("log = (private / 'launch.log')",start)
runner = runner[:start]+'''write(out / 'PREREG.json', {
    'utc':datetime.now(timezone.utc).isoformat(),'cases':10,'arms':3,'calls':30,
    'method':'Actual first-request compositor builder, no retries/validators/kernel/UI. Current greedy vs same request with one schema-semantics instruction, and separately current instructions with official Qwen sampling. All observed fields retained. First case equals661 observed situation/payload; nine declared fixtures vary name, state, language, question and operation. No product replay credit.',
    'criteria':'Read all30 complete drafts for correct subject, language, requested state/count, naturalness and unsupported facts. Preserve literal proper name Foreground. Do not ban a word or infer correctness from existing validators. No promotion from a single repaired answer.',
    'inheritance':'661/t24 publishes foreground from its first draft, not a UI mutation. Existing prompt forbids internals but language contract exempts contract literals. Carter11_lecciones_v1_a_v4.md:105-117 warns eight rewrites distorted replies; test existing writer instruction before new layers.',
    'hypothesis':'Differentiate schema labels from literal proper names without deleting observations or adding a narrator. This is a local hypothesis, not a result proved by cited work.',
    'research':'Official Qwen4B2507 card checked2026-09-09: non-thinking and T.7/topP.8/topK20/minP0. Yin2025 studies serialization for entity matching, not BAXY prose: motivates an explicit representation test only; it does not validate this prompt. Prior650 scope conditioning and rejected656/658 judges remain inherited evidence.',
    'sources':['https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507','https://aclanthology.org/2025.findings-naacl.437/'],
    'instruction':instruction,'command':command,'manifest_sha256':manifest_sha,'model_sha256':sha(config['gguf']),
    'server_sha256':sha(command[0]),'source_sha256':sha(root/'src/baxy_mind/llm.py'),
    'panel_sha256':sha(private/'panel.json'),'observed661_sha256':sha(observed_audit),'source_modified':False,
    'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240},
})
''' + runner[end:]
runner = runner.replace('Collected40 native subject-attribution drafts; adjudication pending.','Collected30 native schema-prose drafts; adjudication pending.')
exec(compile(runner,__file__,'exec'))
