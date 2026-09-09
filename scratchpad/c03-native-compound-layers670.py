"""Locate compound-state confusion before changing product logic or instructions."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix = source[:source.index("history = [{'role'")]
prefix = prefix.replace('astra-native-subject612', 'astra-native-compound-layers670').replace('C03-native-subject612-private', 'C03-native-compound-layers670-private')
exec(compile(prefix, __file__, 'exec'))
from baxy_mind.llm import _compose_situation_payload
previous = json.loads((private.parent / 'C03-native-window-projection668-private/panel.json').read_text(encoding='utf-8'))
panel = []
for original in previous:
    if original['arm'] != 'projection667' or not original['case_id'].startswith('topmost-'):
        continue
    projected = _compose_situation_payload(json.loads(original['facts']['situation']), original['language'], original['text'])
    minimal = [{'role':'user', 'content': original['text'] + '\nObserved facts: ' + json.dumps(projected, ensure_ascii=False)}]
    for arm, messages in [('native_facts', minimal), ('identity_facts', [{'role':'system','content':SYSTEM_PROMPT}, *minimal]), ('compositor667', original['payload']['messages'])]:
        payload = copy.deepcopy(original['payload'])
        payload['messages'] = copy.deepcopy(messages)
        panel.append({**copy.deepcopy(original), 'arm':arm, 'payload':payload})
assert len(panel) == 12
assert psutil.virtual_memory().available >= 1800*2**20
write(private / 'panel.json', panel)
runner = source[source.index('command = json.loads'):]
start = runner.index("write(out / 'PREREG.json', {")
end = runner.index("log = (private / 'launch.log')", start)
runner = runner[:start] + '''write(out / 'PREREG.json', {
    'utc':datetime.now(timezone.utc).isoformat(),'cases':4,'arms':3,'calls':12,
    'method':'Same four668 compound-state fixtures and exact projected facts. Native question plus facts, then BAXY identity added, then exact full compositor667 request. Fixed registered greedy parameters. No invented answer, extra guidance, validator, retry, kernel or UI.',
    'criteria':'Both requested predicates must be answered independently with their actual opposite Boolean values. Judge truth, completeness and language. Full compositor control must reproduce668 before causal claims. Native/identity are diagnostic ablations, not alternative product contracts.',
    'inheritance':'668 both field spellings failed all four conjunction controls;667 repaired original leak and669 real-window panel24/24 but not adopted. Locate whether confusion appears before full product instructions instead of adding equivalent rules.',
    'research_reused':'Qwen official non-thinking profile and Microsoft foreground/topmost semantics recorded668. No new model ranking or inference of optimality from defaults.',
    'command':command,'manifest_sha256':manifest_sha,'model_sha256':sha(config['gguf']),
    'server_sha256':sha(command[0]),'source_sha256':sha(root/'src/baxy_mind/llm.py'),
    'panel_sha256':sha(private/'panel.json'),'source_modified':False,'source_adopted':False,
    'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240},
})
''' + runner[end:]
runner = runner.replace('Collected40 native subject-attribution drafts; adjudication pending.', 'Collected12 compound-layer drafts; adjudication pending.')
exec(compile(runner, __file__, 'exec'))
