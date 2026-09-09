"""Reject native JSON classification without disguising serialization failures."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out=base/'astra-native-schema617'
private=home/'C03-native-schema617-private'
assert not (out/'RESULT.json').exists()
panel={(r['case_id'],r['arm']):r for r in read(private/'panel.json')}
responses=rows(private/'responses.jsonl')
assert len(panel)==len(responses)==40
adjudication=[]
for r in responses:
    case=panel[r['case_id'],r['arm']];choice=r['response']['choices'][0]
    assert choice['finish_reason']=='stop'
    thought=bool(choice['message'].get('reasoning_content'))
    assert thought==(r['arm']=='thinking')
    try: raw=json.loads(choice['message']['content'])
    except json.JSONDecodeError: raw=None
    valid=(isinstance(raw,dict) and set(raw)=={'request_type','effect_count'}
           and raw['request_type'] in {'social_conversation','stable_conversation','external_read','environment_change','incomplete_effect'}
           and raw['effect_count'] in {'zero','one','multiple'})
    count=('zero' if valid and raw['request_type'] in {'social_conversation','stable_conversation'} else raw.get('effect_count') if valid else None)
    adjudication.append({**r,'text':case['text'],'expected_type':case['expected_type'],'expected_count':case['expected_count'],
                         'strict_schema_valid':valid,'actual_reasoning':thought,
                         'correct':bool(valid and raw['request_type']==case['expected_type'] and count==case['expected_count'])})
write(private/'adjudication.json',adjudication)
report=['# Nativo617: razonamiento efectivo, sin clasificador utilizable']
for r in adjudication:
    report += ['## '+r['case_id']+' · '+r['arm'],r['text'],r['response']['choices'][0]['message']['content'],
               'Esperado: '+r['expected_type']+'/'+r['expected_count']+'; esquema válido='+str(r['strict_schema_valid'])+'; correcto='+str(r['correct'])]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
scores={arm:sum(r['correct'] for r in adjudication if r['arm']==arm) for arm in ['direct','thinking']}
note='''# Nativo617: descartar la vía del subtipo para este candidato

Sin gramática forzada,20/20 peticiones thinking sí producen reasoning_content; las20 directas no. Todas terminan, pero aparecen conteos numéricos fuera del enum, JSON sin comillas y bloques Markdown. No se corrigen para dar puntos. Continúan las confusiones de identidad/redacción como social, negación como efecto y argumentos incompletos como completos. El pensamiento puede reconocer la lectura nombrada y la cuenta compuesta, pero no ofrece una clasificación general utilizable.

Esto distingue la ausencia de razonamiento de616 de un límite semántico persistente. No se adopta salida libre, nueva gramática, subtipo, sampler ni modelo. Se abandona esta vía; no se siguen barriendo prompts de clasificación. Resultado íntegro privado, conteo estricto en RESULT.json. Recursos:1679,988MiB GPU/969,430MiB RAM,98,359s; no UI/voz.

618 aborda por separado el fallo de estilo de614: expresar trato y género como instrucciones gramaticales claras, conservando identidad. Panel de12 casos con controles de sujeto e idiomas; sólo se considerará con prueba de producto. Fuente606 y registro intactos. Encuesta25/717/0, ninguna decisión pendiente del dueño.
'''
seal(out,private,{'utc':datetime.now(timezone.utc).isoformat(),'per_arm':20,'strict_correct_by_arm':scores,
                 'actual_thinking_responses':20,'all40_finish_stop':True,'source_adopted':False,
                 'resources':read(out/'RESOURCES.json')},note,['panel.json','requests.jsonl','responses.jsonl','adjudication.json','RESULT.md'])
state=read(base/'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='612–617 sellados. Nativo617 sí piensa pero no clasifica con fiabilidad; subtipo descartado. Fuente606/Full606 intactos;25/717/0.',
             continuation='Recoger618 sesión16282 TEMP/c03-style618.log:12pares de instrucciones de estilo, diagnóstico independiente. No reabrir barrido de prompts del guard. Publicar612–617 y mantener fuente606 hasta validación de producto.')
write(base/'RELEVO_ACTIVO.json',state)
(base/'HANDOFF.md').write_text(note+'\nActivo618 sesión16282, TEMP/c03-style618.log. Evidencia612–617 sellada pendiente de publicación. No fuente adoptada desde606. UI/voz/cobertura/operaciones y Full final siguen pendientes.\n',encoding='utf-8',newline='\n')
print(scores)
