"""Compare first drafts with one explicit observation-scope instruction."""
from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
validated = root/'artifacts/comprobaciones/C03/astra-window-regression651/RESULT.json'
assert validated.exists(), 'Finish and seal Full651 before starting inference.'
assert json.loads(validated.read_text(encoding='utf-8'))['full_exit'] == 0
source = (root/'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix = source[:source.index("history = [{'role'")]
prefix = prefix.replace('astra-native-subject612', 'astra-native-window-scope650').replace('C03-native-subject612-private', 'C03-native-window-scope650-private')
exec(compile(prefix, __file__, 'exec'))
from baxy_mind.llm import _compose_situation_payload

observed_audit = private.parent/'C03-context-product647-private/compose-audit.jsonl'
with observed_audit.open(encoding='utf-8') as stream:
    observed_rows = [row for line in stream if (row := json.loads(line))['trace'] == 't15' and row['stage'] == 'first']
assert len(observed_rows) == 1 and observed_rows[0]['published'] is True
observed647 = observed_rows[0]

class Captured(Exception): pass
class Builder(LlmRuntime):
    def __init__(self): self._gguf = config['gguf']
    def _post(self, payload, **_kwargs):
        self.payload = copy.deepcopy(payload)
        raise Captured()

cases = [
    ('observed647', 'And Spotify?', 'Spotify', True, 0),
    ('absence-es', '¿Y Paint?', 'Paint', True, 0),
    ('one-en', 'Is Google Chrome open?', 'Google Chrome', True, 1),
    ('one-es', '¿Está abierta Calculadora?', 'Calculadora', True, 1),
    ('count-en', 'How many windows of Orbit 23 are open?', 'Orbit 23', True, 3),
    ('count-es', '¿Cuántas ventanas de Órbita 23 están abiertas?', 'Órbita 23', True, 3),
    ('not-installed-en', 'Is Sundial open?', 'Sundial', False, 0),
    ('not-installed-es', '¿Está abierta Brújula?', 'Brújula', False, 0),
]
panel = []
for case_id, text, name, installed, count in cases:
    observed = {'version': 1, 'requestedName': name, 'displayName': name if installed else None,
        'installed': installed, 'hasVisibleWindow': count > 0, 'visibleWindowCount': count,
        'authority': 'windows_start_catalog_and_visible_window_snapshot'}
    facts = {'situation': json.dumps({'kind': 'operation', 'operation': 'window.application.status',
        'polarity': 'success', 'verified': True, 'succeeded': True, 'observed': observed})}
    if case_id == 'observed647':
        assert json.loads(facts['situation']) == json.loads(observed647['situation'])
        facts['situation'] = observed647['situation']
        assert _compose_situation_payload(json.loads(facts['situation']), 'en', text) == observed647['payload']
    client = Builder()
    try:
        client.compose_user_message(text, 'status', facts)
    except Captured:
        pass
    else:
        raise AssertionError('Expected the first real compositor request')
    for arm in ['current', 'observation_scope']:
        payload = copy.deepcopy(client.payload)
        if arm == 'observation_scope':
            payload['messages'][0]['content'] += (
                ' This observation reports installation and visible windows only.'
                ' It does not report background processes. Preserve installed,'
                ' hasVisibleWindow and visibleWindowCount; do not infer a process state.'
            )
        panel.append({'case_id': case_id, 'text': text, 'name': name, 'installed': installed,
            'visible_window_count': count, 'facts': facts, 'arm': arm, 'payload': payload})
write(private/'panel.json', panel)
runner = source[source.index('command = json.loads'):]
start = runner.index("write(out / 'PREREG.json', {")
end = runner.index("log = (private / 'launch.log')", start)
runner = runner[:start]+'''write(out/'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'cases':8, 'arms':2, 'calls':16,
    'method': 'Actual current compositor first-request builder; one arm adds only a generic scope instruction. Same model/profile/payload otherwise. Observed647 fields plus seven declared installation/visibility/count fixtures, ES/EN and names varied. No kernel, retries, validators or dispatch; this is first-draft diagnosis, not an exact product replay or real machine state for the synthetic names.',
    'criteria': 'Judge all16 drafts for installation, visibility, requested count, language and unsupported process claims. A negative process claim is unobserved too. Do not score with the deficient validator649 or promote from one lucky answer.',
    'inheritance': '647 first published draft invents running from installedtrue/count0.649 shows current validator accepts both process polarities and installation/count contradictions. Existing shape instructions name verified clock/audio facts; evaluate analogous scope conditioning before source edits.',
    'profile': 'Actual registered Qwen2507 public-composition sampling and first-draft budget, captured without overrides. Server b9980 unchanged.',
    'command':command, 'manifest_sha256':manifest_sha, 'model_sha256':sha(config['gguf']),
    'server_sha256':sha(command[0]), 'source_sha256':sha(root/'src/baxy_mind/llm.py'),
    'panel_sha256':sha(private/'panel.json'), 'source_modified':False,
    'observed647_audit_sha256':sha(observed_audit),
    'observed647_situation_and_visible_payload_equal':True,
    'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240},
})
''' + runner[end:]
runner = runner.replace('Collected40 native subject-attribution drafts; adjudication pending.', 'Collected16 native window-scope drafts; adjudication pending.')
exec(compile(runner, __file__, 'exec'))
