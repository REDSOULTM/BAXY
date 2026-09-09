"""Contrast the ambiguous literal exemption with field-name representation."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix = source[:source.index("history = [{'role'")]
prefix = prefix.replace('astra-native-subject612','astra-native-literal-contract663').replace('C03-native-subject612-private','C03-native-literal-contract663-private')
exec(compile(prefix,__file__,'exec'))
old_private = private.parent / 'C03-native-schema-prose662-private'
previous = json.loads((old_private/'panel.json').read_text(encoding='utf-8'))
old_es = 'Idioma obligatorio: español. Fuera de los literales del contrato, no introduzcas palabras inglesas.'
new_es = 'Idioma obligatorio: español. Conserva sin traducir los nombres propios, títulos y rutas. Describe los estados observados con palabras españolas.'
panel = []
for original in previous:
    if original['arm'] != 'current':
        continue
    for arm in ['current','literal_contract','descriptive_field']:
        row = copy.deepcopy(original)
        row['arm'] = arm
        if arm == 'literal_contract' and row['language'] == 'es':
            assert sum(m['content'].count(old_es) for m in row['payload']['messages']) == 1
            for message in row['payload']['messages']:
                message['content'] = message['content'].replace(old_es,new_es)
        if arm == 'descriptive_field':
            for message in row['payload']['messages']:
                message['content'] = message['content'].replace('"foreground": true','"in_front_of_other_windows": true')
        panel.append(row)
write(private/'panel.json',panel)
runner = source[source.index('command = json.loads'):]
start = runner.index("write(out / 'PREREG.json', {")
end = runner.index("log = (private / 'launch.log')",start)
runner = runner[:start]+'''write(out/'PREREG.json',{
    'utc':datetime.now(timezone.utc).isoformat(),'cases':10,'arms':3,'calls':30,
    'method':'Exact662 current requests reused. Arm1 current control; arm2 replaces only Spanish literal-exemption policy at its actual user-message location; English untouched controls. Arm3 changes only the foreground Boolean key into a semantically descriptive English key, retaining true and all other fields. No combination, omitted fact, validator or retry. Diagnostic counterfactuals, not product sources.',
    'criteria':'Adjudicate every draft against662 facts, requested state/count, names and language. Proper name Foreground must remain. Current control should reproduce662 before causal claims. Do not accept schema spelling as Spanish prose. If policy revision does not improve after662, stop adding equivalent instructions and change representation strategy.',
    'inheritance':'662 original9/10, added system instruction9/10, official sampling9/10; all reproduce661 foreground leakage. Tests discriminate the later ambiguous literal exception from the field spelling instead of adding another system rule. No change to runtime.',
    'research_reused':'662 references and actual registered Qwen non-thinking template/profile; this is cause isolation at fixed greedy, not a global quality ranking.',
    'sources':['https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507','https://aclanthology.org/2025.findings-naacl.437/'],
    'old_es':old_es,'new_es':new_es,'command':command,'manifest_sha256':manifest_sha,
    'model_sha256':sha(config['gguf']),'server_sha256':sha(command[0]),'source_sha256':sha(root/'src/baxy_mind/llm.py'),
    'panel_sha256':sha(private/'panel.json'),'baseline_panel_sha256':sha(old_private/'panel.json'),
    'source_modified':False,'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240},
})
''' + runner[end:]
runner = runner.replace('Collected40 native subject-attribution drafts; adjudication pending.','Collected30 literal-contract drafts; adjudication pending.')
exec(compile(runner,__file__,'exec'))
