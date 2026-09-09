"""Isolate candidate availability; injected candidate is diagnostic, not a router."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix = source[:source.index("history = [{'role'")]
prefix = prefix.replace('astra-native-subject612', 'astra-native-context644').replace('C03-native-subject612-private', 'C03-native-context644-private')
exec(compile(prefix, __file__, 'exec'))
from baxy_mind.planner import PlannerCatalog

inherited = private.parent/'C03-context-candidates643-private'
tools = json.loads((inherited/'tools.json').read_text(encoding='utf-8'))
catalog = PlannerCatalog(tools)
cases = json.loads((inherited/'retrieval.json').read_text(encoding='utf-8'))[:4]
prior = [{'role': 'user', 'content': 'Is Spotify open?'},
         {'role': 'assistant', 'content': 'Spotify is installed but not currently open.'}]
prior_es = [{'role': 'user', 'content': '¿Está abierta la aplicación Steam?'},
            {'role': 'assistant', 'content': 'Sí, hay dos ventanas de Steam abiertas.'}]
for case_id, text, history, expected in [
    ('coherent-reference-en', 'Is it open now?', prior, ['window.application.status']),
    ('coherent-name-es', '¿Y Paint?', prior_es, ['window.application.status']),
    ('coherent-reference-es', '¿Esa aplicación tiene alguna ventana abierta?', prior_es, ['window.application.status']),
    ('independent-clock', 'What time is it?', prior, ['system.time']),
    ('constraint', 'No abras ninguna ventana.', prior_es, []),
    ('social', 'Thanks for checking.', prior, []),
]:
    cases.append({'case_id': case_id, 'text': text, 'history': history, 'expected': expected})

class Captured(Exception): pass
class Builder(LlmRuntime):
    def __init__(self): self._gguf = config['gguf']
    def _post(self, payload, **_kwargs):
        self.payload = copy.deepcopy(payload)
        raise Captured()

panel = []
for case in cases:
    names = [t.name for t in catalog.shortlist(case['text'])]
    added = names if 'window.application.status' in names else [*names[:-1], 'window.application.status']
    for arm, selected in [('current', names), ('diagnostic_candidate', added)]:
        client = Builder()
        try:
            client._post_native_tool_selection(case['text'], selected,
                {name: {'description': catalog.get(name).description} for name in selected}, case['history'])
        except Captured:
            pass
        else:
            raise AssertionError('Expected first native request capture')
        panel.append({**case, 'arm': arm, 'expected': case.get('expected', ['window.application.status']),
            'candidates': selected, 'payload': client.payload})
write(private/'panel.json', panel)

runner = source[source.index('command = json.loads'):]
start = runner.index("write(out / 'PREREG.json', {")
end = runner.index("log = (private / 'launch.log')", start)
runner = runner[:start]+'''write(out/'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'cases': 10, 'arms': 2, 'calls': 20,
    'method': 'Actual native selection builder. Only append missing window.application.status as last candidate replacing the last of28. Original bounded roles remain identical between arms. Four observed four-message histories from642 plus six coherent/reference/topic-shift/no-effect controls. This is an oracle candidate-availability diagnostic, not an implemented retrieval policy, exact full-history product replay, or coverage.',
    'criteria': 'Score every draft for correct operation set and finish_reason. No kernel or provider dispatch. Any gain establishes only a retrieval prerequisite; remaining selection, grounding, language and prose failures stay open.',
    'profile': 'Product native selection: temperature0, seed0, max256, automatic tools, no thinking; registered Qwen2507 and b9980 unchanged.',
    'inheritance': '643 contextual lexical query helps two followups but loses an independent network candidate; no global history concatenation adopted.',
    'command': command, 'manifest_sha256': manifest_sha, 'model_sha256': sha(config['gguf']),
    'server_sha256': sha(command[0]), 'source_sha256': sha(root/'src/baxy_mind/llm.py'),
    'panel_sha256': sha(private/'panel.json'), 'source_modified': False,
    'limits': {'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240},
})
''' + runner[end:]
runner = runner.replace('Collected40 native subject-attribution drafts; adjudication pending.', 'Collected20 native context-selection drafts; adjudication pending.')
exec(compile(runner, __file__, 'exec'))
