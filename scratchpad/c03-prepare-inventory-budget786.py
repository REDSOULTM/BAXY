"""Inherit785 transport/guards; change only first-draft output cap in paired786."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'scratchpad/c03-prose-sampling785.py').read_text(encoding='utf-8')
source = source.replace('Paired50-case first-draft sampler diagnostic; immutable product,150calls.',
                        'Paired50-case output-budget diagnostic; immutable product,100calls.')
source = source.replace("PRIVATE = SOURCE.parent / 'C03-prose-sampling785-private'",
                        "PRIVATE = SOURCE.parent / 'C03-inventory-budget786-private'")
source = source.replace("OUT = BASE / 'PROSE_SAMPLING785'", "OUT = BASE / 'INVENTORY_BUDGET786'")
source = source.replace('from baxy_mind.llm import LlmRuntime, _compose_situation_payload\n', '')
start = source.index('panel = []\n')
end = source.index('command=next(', start)
source = source[:start] + '''reference_private = SOURCE.parent / 'C03-prose-sampling785-private'
reference = read(BASE / 'PROSE_SAMPLING785/PREREG.json')
assert sha(reference_private / 'cases.json') == reference['cases_sha256']
assert sha(reference_private / 'planned.json') == reference['planned_sha256']
reference_pins = read(BASE / 'PROSE_SAMPLING785/PINS.json')
assert sha(BASE / 'PROSE_SAMPLING785/ADJUDICATION.json') == reference_pins['files']['ADJUDICATION.json']
panel = read(reference_private / 'cases.json')
reference_payloads = {p['case_id']:p['payload'] for p in read(reference_private / 'planned.json')
                      if p['arm'] == 'A_registered_greedy'}
assert len(panel) == len(reference_payloads) == 50
planned=[]
for index,case in enumerate(panel):
    baseline = reference_payloads[case['id']]
    assert baseline['temperature'] == 0 and baseline['max_tokens'] == 256
    assert baseline.get('cache_prompt') is False
    variants=[]
    for arm,cap in [('A_original_256',256),('B_output_512',512)]:
        payload=copy.deepcopy(baseline)
        payload['max_tokens']=cap
        assert {k:v for k,v in payload.items() if k != 'max_tokens'} == {k:v for k,v in baseline.items() if k != 'max_tokens'}
        variants.append({'arm':arm,'case_id':case['id'],'payload':payload})
    if index % 2:
        variants.reverse()
    planned.extend(variants)
''' + source[end:]
start = source.index("plan={'utc':")
end = source.index('stop = threading.Event()', start)
source = source[:start] + '''plan={'utc':datetime.now(timezone.utc).isoformat(),'calls':len(planned),'cases':len(panel),'command':command,
    'model':prior['model'],'backend':prior['backend'],'source_pins':source_pins,'driver_sha256':sha(__file__),
    'planned_sha256':sha(PRIVATE/'planned.json'),'cases_sha256':sha(PRIVATE/'cases.json'),
    'reference_cases_sha256':reference['cases_sha256'],
    'reference_adjudication_sha256':reference_pins['files']['ADJUDICATION.json'],
    'intervention':'Same50 frozen785 cases and exact A_registered_greedy HTTP bodies. A max_tokens256 versus B max_tokens512; only output cap differs. Alternating arm order. Product source/prompt/sampler unchanged.',
    'inheritance':'785 found17 length cuts across3arms and sampler alone did not resolve the category.754-759/768/771 showed limits of additional prompt wording.764 supplies dense-inventory9s model/10s app time, distinct from Python output cap256.',
    'limits':{'observe_seconds_per_call':15,'output_caps':[256,512],'gpu_stop_mib':3800,'free_ram_min_mib':768,'wall_seconds':900},
    'criterion':'Same frozen785 criteria and whole-answer adjudication policy: requested facts, title/process identities and exact multiplicity, scope, quantities, subject, language and no unsupported chronology. Keep truncation, omissions, subject and value errors separate. No relaxation for a longer response.',
    'scope':'First-draft BAXY-context output-budget diagnostic; not native-model ranking, recommended-recipe reference, complete product/UI/voice/reserve acceptance or automatic survey credit. No product adoption. All user data stays local.',
    'environment_defaults':{'OMP_NUM_THREADS':'4','MKL_NUM_THREADS':'4','TOKENIZERS_PARALLELISM':'false'}}
write(OUT / 'PREREG.json', plan)
''' + source[end:]
target = ROOT / 'scratchpad/c03-inventory-budget786.py'
assert not target.exists()
compile(source, str(target), 'exec')
target.write_bytes(source.encode('utf-8'))
print(target)
