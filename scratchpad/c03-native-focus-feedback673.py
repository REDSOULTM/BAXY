"""Compare generic repair with externally verified field-level contradiction data."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix = source[:source.index("history = [{'role'")]
prefix = prefix.replace('astra-native-subject612', 'astra-native-focus-feedback673').replace('C03-native-subject612-private', 'C03-native-focus-feedback673-private')
exec(compile(prefix, __file__, 'exec'))
old = private.parent / 'C03-compositor-window-states672-private'
read_rows = lambda p: [json.loads(line) for line in p.read_text(encoding='utf-8').splitlines()]
old_panel = {row['case_id']:row for row in json.loads((old / 'panel.json').read_text(encoding='utf-8'))}
requests = {(row['case_id'],row['call']):row for row in read_rows(old / 'requests.jsonl')}
responses = {(row['case_id'],row['call']):row for row in read_rows(old / 'responses.jsonl')}
panel = []
for case_id in ['topmost-es-true','topmost-es-false','topmost-en-false']:
    case = old_panel[case_id]
    seen = json.loads(case['facts']['situation'])['observed']['windows'][0]
    assert isinstance(seen['foreground'], bool)
    for variant, name in [('original','Atlas'),('renamed','Brújula 7' if case['language']=='es' else 'Nimbus 41')]:
        payload = copy.deepcopy(requests[case_id,2]['payload'])
        for message in payload['messages']:
            message['content'] = message['content'].replace('Atlas',name)
        draft = responses[case_id,1]['response']['choices'][0]['message']['content'].replace('Atlas',name)
        # The focus assertion was independently adjudicated672 and detected
        # by the current factual owner. No model-generated verdict is used.
        evidence = {'window_title':name, 'contradiction':{'predicate':'is_active_window',
                    'observed_value':seen['foreground'], 'draft_claim':not seen['foreground']},
                    'rejected_draft':draft}
        for arm in ['generic672','verified_field_feedback']:
            request = copy.deepcopy(payload)
            if arm == 'verified_field_feedback':
                request['messages'][-1]['content'] += '\nVerified factual correction: ' + json.dumps(evidence, ensure_ascii=False)
            panel.append({'case_id':case_id+'-'+variant,'origin':case_id,'variant':variant,
                          'text':case['text'].replace('Atlas',name),'language':case['language'],
                          'arm':arm,'payload':request,'evidence':evidence,
                          'facts':case['facts']['situation'].replace('Atlas',name)})
assert len(panel)==12
assert psutil.virtual_memory().available >= 1800*2**20
write(private / 'panel.json', panel)
runner = source[source.index('command = json.loads'):]
start = runner.index("write(out / 'PREREG.json', {")
end = runner.index("log = (private / 'launch.log')",start)
runner = runner[:start]+'''write(out / 'PREREG.json', {
    'utc':datetime.now(timezone.utc).isoformat(),'cases':6,'arms':2,'calls':12,
    'method':'Use exact672 second-request generic repairs for three unambiguous contradictions plus declared subject-name variants. Change only user data by appending independently verified field/value contradiction and rejected draft. No new system instruction, model judge or fixed output. Local native first draft for each repair request.',
    'criteria':'Both observed predicates must be preserved and requested language natural. Removing false focus by omitting it is incomplete, not success. All original generic controls must reproduce672. If useful, feedback must derive from observed typed fields in existing validator before any source adoption.',
    'inheritance':'672 validator rejects wrong focus but generic State only what seen shows repeats wrong claims or omits focus. Test specific external evidence instead of another equivalent generic instruction. No change of model/profile or wider quality ranking.',
    'command':command,'manifest_sha256':manifest_sha,'model_sha256':sha(config['gguf']),
    'server_sha256':sha(command[0]),'source_sha256':sha(root/'src/baxy_mind/llm.py'),
    'window_fact_source_sha256':sha(root/'src/baxy_mind/window_prose_facts.py'),
    'panel_sha256':sha(private/'panel.json'),'source_modified':False,'source_adopted':False,
    'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240},
})
''' + runner[end:]
runner = runner.replace('Collected40 native subject-attribution drafts; adjudication pending.', 'Collected12 field-feedback drafts; adjudication pending.')
exec(compile(runner, __file__, 'exec'))
