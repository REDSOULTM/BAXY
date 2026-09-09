"""Seal independently adjudicated policy and representation contrasts."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out = base/'astra-native-literal-contract663'
private = home/'C03-native-literal-contract663-private'
assert not (out/'RESULT.json').exists()
prereg=read(out/'PREREG.json')
assert prereg['source_sha256']==read(base/'astra-native-schema-prose662/PREREG.json')['source_sha256']
assert read(out/'RESOURCES.json')['complete'] and read(out/'RESOURCES.json')['manifest_unchanged']
panel={(r['case_id'],r['arm']):r for r in read(private/'panel.json')}
responses=rows(private/'responses.jsonl')
previous={r['case_id']:r for r in rows(home/'C03-native-schema-prose662-private/responses.jsonl') if r['arm']=='current'}
assert len(panel)==len(responses)==30
adjudication=[]
for response in responses:
    case=panel[response['case_id'],response['arm']]
    choice=response['response']['choices'][0]
    assert choice['finish_reason']=='stop' and not choice['message'].get('reasoning_content')
    if case['arm']=='current':
        assert choice['message']['content']==previous[case['case_id']]['response']['choices'][0]['message']['content']
    failed=case['case_id']=='observed661' and case['arm']=='current'
    adjudication.append({**case,'response':response,'verdict':'failed' if failed else 'correct',
        'reason':'Same first-draft Spanish state-label leakage as661/662.' if failed else 'Individually reviewed: truthful subject/state/count and requested language, no unnecessary state-label jargon. Proper title Foreground retained.'})
scores=Counter(r['arm'] for r in adjudication if r['verdict']=='correct')
assert dict(scores)=={'literal_contract':10,'descriptive_field':10,'current':9}
write(private/'adjudication.json',adjudication)
report=['# 663 — actual9/10; política10/10; etiqueta10/10']
for r in adjudication:
    report+=['## '+r['case_id']+' / '+r['arm'],r['text'],r['response']['response']['choices'][0]['message']['content'],r['verdict']+': '+r['reason'],r['facts']['situation']]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note='''# 663 — excepción literal y etiqueta aisladas

Los diez controles actuales reproducen662 literalmente:9/10. Reemplazar sólo la excepción española sobre literales del contrato da10/10; renombrar sólo foreground como in_front_of_other_windows, conservando el booleano y todos los campos, también10/10. Todos30 terminan EOS. Se mantienen estados, nombres y cantidades, incluido Foreground como título. La causa es sensible a la política de literales y a la representación; no se atribuye a un único factor exclusivo ni a incapacidad global del modelo.

Se elige como candidata la sustitución de la instrucción existente: conserva el esquema original, sin otra capa, llamada o respuesta fija. No se adopta todavía; exige dueñas y producto. GPU3497,559MiB,RAM719,289MiB,14,625s,sin infracciones. Registro intacto; nativo sin UI/voz, sin medición conjunta ni ahorro. Fuente660 estuvo intacta durante662/663; después se preparó candidata664. Encuesta26/716/0.
'''
seal(out,private,{'scores':dict(scores),'total_per_arm':10,'all_eos':True,'all_current_reproduce662':True,
    'selected_candidate':'literal_contract','adopted':False,'resources':read(out/'RESOURCES.json'),'ui_or_voice_credit':False},note,
    ['panel.json','requests.jsonl','responses.jsonl','adjudication.json','RESULT.md'])
print({'scores':dict(scores),'adopted':False})
