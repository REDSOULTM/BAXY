"""Verify the precise foreground projection using the actual compositor builder."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix = source[:source.index("history = [{'role'")]
prefix = prefix.replace('astra-native-subject612', 'astra-native-window-projection668').replace('C03-native-subject612-private', 'C03-native-window-projection668-private')
exec(compile(prefix, __file__, 'exec'))

old_private = private.parent / 'C03-native-schema-prose662-private'
previous = json.loads((old_private / 'panel.json').read_text(encoding='utf-8'))
key = 'is_current_window_for_user_interaction'

class Captured(Exception):
    pass

class Builder(LlmRuntime):
    def __init__(self):
        self._gguf = config['gguf']

    def _post(self, payload, **kwargs):
        self.payload = copy.deepcopy(payload)
        raise Captured()

def build(text, facts):
    client = Builder()
    try:
        client.compose_user_message(text, 'status', facts)
    except Captured:
        return client.payload
    raise AssertionError('No first request captured')

def rename(payload, old, new):
    result = copy.deepcopy(payload)
    for message in result['messages']:
        for literal in ('true', 'false'):
            message['content'] = message['content'].replace(f'"{old}": {literal}', f'"{new}": {literal}')
    return result

panel = []
for original in previous:
    if original['arm'] != 'current':
        continue
    candidate = build(original['text'], original['facts'])
    assert candidate == rename(original['payload'], 'foreground', key), original['case_id']
    for arm, payload in [('published660', original['payload']), ('projection667', candidate)]:
        panel.append({**copy.deepcopy(original), 'arm': arm, 'payload': payload})

base_situation = json.loads(panel[0]['facts']['situation'])
for language in ('es', 'en'):
    for active, topmost in ((True, False), (False, True)):
        situation = copy.deepcopy(base_situation)
        situation['operation'] = 'window.resolve'
        window = situation['observed']['windows'][0]
        window.update(title='Atlas', processName='Atlas', state='normal', foreground=active, alwaysOnTop=topmost)
        text = ('¿La ventana Atlas está activa y está configurada para mantenerse siempre encima?' if language == 'es'
                else 'Is the Atlas window active and configured to stay always on top?')
        facts = {'situation': json.dumps(situation, ensure_ascii=False)}
        candidate = build(text, facts)
        for arm, payload in [('published660', rename(candidate, key, 'foreground')), ('projection667', candidate)]:
            panel.append({'case_id': f'topmost-{language}-{str(active).lower()}', 'text': text,
                          'language': language, 'facts': facts, 'arm': arm, 'payload': payload})

assert len(panel) == 28
assert psutil.virtual_memory().available >= 1800 * 2**20, 'Need startup RAM headroom'
write(private / 'panel.json', panel)
runner = source[source.index('command = json.loads'):]
start = runner.index("write(out / 'PREREG.json', {")
end = runner.index("log = (private / 'launch.log')", start)
runner = runner[:start] + '''write(out / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'cases':14, 'arms':2, 'calls':28,
    'method':'Reuse exact ten662 baseline requests and capture candidate667 from the real compositor. Assert all candidate request changes are only Boolean foreground field renaming. Four new declared ES/EN fixtures distinguish current interaction from always-on-top, with true/false controls. Native first drafts only; no retries, kernel or UI.',
    'criteria':'Adjudicate all28 drafts for language, names, state/count, unsupported claims and EOS. The original foreground Spanish leak must disappear without factual or naturalness regression. Topmost is independent of current interaction. No exact-response oracle and no score based only on disappearance of a word.',
    'inheritance':'662 added instruction and official sampling did not fix leak;663 ambiguous projection appeared10/10 but had unsound z-order semantics;664 global policy rejected by665 grammar regression.667 preserves provider GetForegroundWindow meaning and27 focal tests. This campaign tests its new label, not the rejected in_front_of_other_windows label.',
    'research':'Fixed registered Qwen non-thinking backend/profile for causal isolation; no model ranking. Microsoft defines foreground as the window the user currently works with and distinguishes topmost z-order. Yin2025 motivates serialization hypothesis only, not evidence of BAXY prose quality.',
    'sources':['https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getforegroundwindow','https://learn.microsoft.com/en-us/windows/win32/winmsg/window-features#z-order','https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507','https://aclanthology.org/2025.findings-naacl.437/'],
    'command':command,'manifest_sha256':manifest_sha,'model_sha256':sha(config['gguf']),
    'server_sha256':sha(command[0]),'source_sha256':sha(root/'src/baxy_mind/llm.py'),
    'panel_sha256':sha(private/'panel.json'),'baseline_panel_sha256':sha(old_private/'panel.json'),
    'source_modified':True,'source_adopted':False,
    'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240},
})
''' + runner[end:]
runner = runner.replace('Collected40 native subject-attribution drafts; adjudication pending.', 'Collected28 projection drafts; adjudication pending.')
exec(compile(runner, __file__, 'exec'))
