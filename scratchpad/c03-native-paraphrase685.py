"""Test whether the compositor's explicit paraphrase instruction causes lexical drift."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix = source[:source.index("history = [{'role'")]
prefix = prefix.replace('astra-native-subject612', 'astra-native-paraphrase685').replace('C03-native-subject612-private', 'C03-native-paraphrase685-private')
exec(compile(prefix, __file__, 'exec'))
previous = json.loads((private.parent / 'C03-native-mixed-focus682-private/panel.json').read_text(encoding='utf-8'))
panel = []
for original in previous:
    if original['arm'] != 'compositor':
        continue
    for arm in ['compositor_control', 'without_paraphrase']:
        row = copy.deepcopy(original)
        row['arm'] = arm
        if arm == 'without_paraphrase':
            system = row['payload']['messages'][0]
            phrase = ' Expresa el mensaje con tus propias palabras.'
            assert system['role'] == 'system' and system['content'].count(phrase) == 1
            system['content'] = system['content'].replace(phrase, '')
        panel.append(row)
assert len(panel) == 10
assert psutil.virtual_memory().available >= 1800 * 2**20
write(private / 'panel.json', panel)
runner = source[source.index('command = json.loads'):]
start = runner.index("write(out / 'PREREG.json', {")
end = runner.index("log = (private / 'launch.log')", start)
runner = runner[:start] + '''write(out / 'PREREG.json', {
    'utc':datetime.now(timezone.utc).isoformat(),'cases':5,'arms':2,'calls':10,
    'method':'Paired exact five682 compositor requests. Remove only the instruction Expresa el mensaje con tus propias palabras. All user inputs, observed payloads, language contract, identity/factual constraints and effective sampling remain identical. Native first drafts, no validator or retry and no product source change.',
    'hypothesis':'The unnecessary requirement to paraphrase may replace the software-window noun with ventanal.682 already localizes the lexical error to full compositor requests and reproduces it with two names. This test isolates that specific clause rather than removing all product constraints.',
    'criteria':'All five controls must reproduce682 before causal interpretation. Judge natural software-window terminology, correct title and language, no new facts or regressions. Improvement here would justify broader regression, never immediate promotion.',
    'inheritance':'682 original and Atlas fail lexical choice; renamed Orbit and two language controls pass.664 language-policy removal was rejected by665 grammar regression and is not repeated.670/682 wholesale prompt ablations remain diagnostics only.',
    'research_reused':'Official Qwen2507 non-thinking profile and effective b9980 parameters inherited682; fixed settings isolate a prompt clause, not an optimality comparison or model exclusion.',
    'command':command,'manifest_sha256':manifest_sha,'model_sha256':sha(config['gguf']),
    'server_sha256':sha(command[0]),'source_sha256':sha(root/'src/baxy_mind/llm.py'),
    'panel_sha256':sha(private/'panel.json'),'source_modified':False,'source_adopted':False,
    'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240},
})
''' + runner[end:]
runner = runner.replace('Collected40 native subject-attribution drafts; adjudication pending.', 'Collected10 paired paraphrase drafts; adjudication pending.')
exec(compile(runner, __file__, 'exec'))
