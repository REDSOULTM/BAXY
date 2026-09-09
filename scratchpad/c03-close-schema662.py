"""Seal the failed added-instruction and sampling hypotheses."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out = base/'astra-native-schema-prose662'
private = home/'C03-native-schema-prose662-private'
assert not (out/'RESULT.json').exists()
prereg = read(out/'PREREG.json')
assert sha(root/'src/baxy_mind/llm.py') == prereg['source_sha256']
panel = {(r['case_id'],r['arm']):r for r in read(private/'panel.json')}
responses = rows(private/'responses.jsonl')
assert len(panel) == len(responses) == 30
adjudication = []
for response in responses:
    case = panel[response['case_id'],response['arm']]
    choice = response['response']['choices'][0]
    assert choice['finish_reason'] == 'stop' and not choice['message'].get('reasoning_content')
    failed = case['case_id'] == 'observed661'
    adjudication.append({**case,'response':response,'verdict':'failed' if failed else 'correct',
        'reason':'Preserves observed state but copies foreground into Spanish prose; same failure as661.' if failed else 'Individually reviewed subject, state/count, language and naturalness; literal title Foreground is a proper name, not a state-label leak.'})
scores = Counter(r['arm'] for r in adjudication if r['verdict']=='correct')
assert dict(scores) == {'current':9,'schema_semantics':9,'documented_profile':9}
write(private/'adjudication.json',adjudication)
report = ['# 662 — tres brazos9/10; sin mejora']
for r in adjudication:
    report += ['## '+r['case_id']+' / '+r['arm'],r['text'],r['response']['response']['choices'][0]['message']['content'],r['verdict']+': '+r['reason'],r['facts']['situation']]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note = '''# 662 — instrucción adicional y muestreo no corrigen la fuga

Diez primeros borradores por brazo, todos EOS. Actual9/10, instrucción adicional de semántica9/10 y perfilQwen documentado9/10. El actual reproduce literalmente661/t24; los dos cambios conservan foreground como estado en la respuesta española. Nombres, estados normal/maximizado, cantidades y controles ingleses se conservan, incluido Foreground como nombre propio. No se adopta ninguno de los cambios ni se añade una llamada.

Servidor nativo con primeras peticiones del compositor, sin kernel/reintentos/validación/UI. Un caso usa situación y payload reales; nueve fixtures son desarrollo declarado. GPU3497,559MiB,RAM720,199MiB,14,797s,sin infracciones y registro intacto; no recursos conjuntos ni ahorro de producto. Carter11:105–117 y las fuentes enlazadas en PREREG fundamentan el contraste, no prueban el resultado de BAXY. Sigue663: reemplazar la excepción ambigua en su ubicación final frente a cambiar sólo la etiqueta del campo, manteniendo todos los hechos. Encuesta26/716/0,fuente660 intacta.
'''
seal(out,private,{'scores':dict(scores),'total_per_arm':10,'all_eos':True,'adopted':False,
    'observed661_reproduced':True,'resources':read(out/'RESOURCES.json'),'ui_or_voice_credit':False},note,
    ['panel.json','requests.jsonl','responses.jsonl','adjudication.json','RESULT.md'])
print({'scores':dict(scores),'adopted':False})
