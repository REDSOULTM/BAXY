"""Record the absent reasoning instead of claiming a valid thinking comparison."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out=base/'astra-social-thinking616'
private=home/'C03-social-thinking616-private'
assert not (out/'RESULT.json').exists()
panel={(r['case_id'],r['arm']):r for r in read(private/'panel.json')}
responses=rows(private/'responses.jsonl')
assert len(panel)==len(responses)==40
adjudication=[]
for r in responses:
    case=panel[r['case_id'],r['arm']]
    choice=r['response']['choices'][0]
    assert choice['finish_reason']=='stop'
    raw=json.loads(choice['message']['content'])
    count='zero' if raw['request_type'] in {'stable_conversation','social_conversation'} else raw['effect_count']
    adjudication.append({**r,'text':case['text'],'expected_type':case['expected_type'],'expected_count':case['expected_count'],
                         'raw':raw,'actual_reasoning':bool(choice['message'].get('reasoning_content')),
                         'normalized_correct':raw['request_type']==case['expected_type'] and count==case['expected_count'],
                         'raw_count_correct':raw['effect_count']==case['expected_count']})
assert not any(r['actual_reasoning'] for r in adjudication)
write(private/'adjudication.json',adjudication)
report=['# 616: opción de pensamiento no equivale a pensamiento efectivo']
for r in adjudication:
    report += ['## '+r['case_id']+' · '+r['arm'],r['text'],json.dumps(r['raw'],ensure_ascii=False),
               'Esperado: '+r['expected_type']+'/'+r['expected_count']+'; correcto normalizado='+str(r['normalized_correct'])]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
scores=Counter(r['arm'] for r in adjudication if r['normalized_correct'])
note='''# Guardia616: no hubo razonamiento efectivo

Mismos20 casos y subtipo615, perfil GoogleT1/p.95/k64/min0,3072tokens en ambos brazos. Todas40 salidas terminan, pero ninguna contiene reasoning_content, incluidas las20 con enable_thinking=true. Correctas normalizadas: directo12/20, opción thinking11/20. Es una comparación de configuración solicitada, no una medida válida de calidad con razonamiento. No se adopta el subtipo ni se sigue variando su instrucción semántica.

El contraste617 cambia de estrategia: salida nativa, sin gramática forzada, con las mismas definiciones y una instrucción de serialización JSON.613 ya demostró razonamiento real en este backend sin gramática. Se separan formato y comprensión antes de concluir incapacidad del modelo; aún no se demuestra causalidad del formato. La documentación upstream distingue gramáticas inmediatas y diferidas: https://github.com/ggml-org/llama.cpp/blob/master/docs/development/parsing.md. Esa documentación general no sustituye la prueba de esta versión/modelo.

Pico1679,988MiB GPU/1034,320MiB RAM,22,016s. Sin fuente ni registro modificados, sin UI/voz ni cobertura adicional:25/717/0. Fuente606 y su Full siguen siendo la versión validada.
'''
seal(out,private,{'utc':datetime.now(timezone.utc).isoformat(),'per_arm':20,'normalized_correct_by_arm':dict(scores),
                 'actual_thinking_responses':0,'thinking_comparison_valid':False,'source_adopted':False,
                 'resources':read(out/'RESOURCES.json')},note,['panel.json','requests.jsonl','responses.jsonl','adjudication.json','RESULT.md'])
with (base/'INVESTIGACION_MODELO_C03.md').open('a',encoding='utf-8',newline='\n') as stream:
    stream.write('\n\n## Cierre612–616 y aislamiento nativo617\n\n613 terminó: history-direct8/8, native-direct7/8, native-thinking8/8, history-thinking6/8. Producto61433/35: identidad/vocativo correctos, estilo H0218 y rechazo de pregunta social H0032 fallan.615 subtipo social baja15/20→12/20 normalizados; rechazado.616 perfil documentado no produce pensamientos reales con gramática, aun solicitándolos;12/20 frente11/20 no permite evaluar razonamiento.617 elimina la restricción de salida para observarlo, sin cambiar definiciones. Ninguna promoción. Full606 ya terminó verde:10218pass+466subtests/3skips Python;4452pass/1skip agregado .NET.\n')
state=read(base/'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='612–616 sellados.616 no produjo razonamiento real: comparación inválida para thinking. Fuente606/registro intactos;25/717/0.',
             continuation='Recoger617 sesión96985 TEMP/c03-native-schema617.log; salida nativa sin gramática, mismos casos/definiciones/perfil. Adjudicar JSON, pensamientos y semántica. No repetir prompts615. Publicar evidencia sellada612–616, sin introducir fuente experimental.')
write(base/'RELEVO_ACTIVO.json',state)
(base/'HANDOFF.md').write_text(note+'\nActivo617 sesión96985, TEMP/c03-native-schema617.log. Fuente606 commitbbb3a951, HEAD publicadoaa42c099. Evidencia612–616 lista para publicar;617 sin adjudicar. Encuesta742/rev1248 intacta,25/717/0. Ninguna decisión pendiente del dueño. C03 continúa con UI, voz, cobertura, regresión operativa y Full final pendientes.\n',encoding='utf-8',newline='\n')
print(dict(scores))
