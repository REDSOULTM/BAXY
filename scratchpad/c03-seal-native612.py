"""Adjudicate every native612 draft; do not promote its best isolated arm."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-native-subject612'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-native-subject612-private'
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
assert not (out/'RESULT.json').exists()
panel={(r['case_id'],r['arm']):r for r in read(private/'panel.json')}
with (private/'responses.jsonl').open(encoding='utf-8-sig') as stream:
    responses=list(map(json.loads,stream))
assert len(responses)==len(panel)==40
failures={
    ('H0012','native'):'Misreads the colloquial identity question and requests unnecessary clarification.',
    ('H0012','identity'):'Misreads the expletive as kicking a ball and speculates about a game.',
    ('H0012','policy'):'Publishes SIEMPRE, an instruction fragment unrelated to the identity question.',
    ('H0012','history'):'Names BAXY but treats the expletive as the verb kick; irrelevant, unnatural opening retained as a failure.',
    ('H0012','greedy'):'Eres tú assigns the question to the wrong subject, even though a later clause identifies BAXY.',
    ('vocative-es','native'):'Correctly separates assistant from Atlas but adds an unverified, unnecessary attribution about another model. This is not product-quality grounded prose.',
    ('user-name-es','identity'):'Names Vera but offers a physical cafe outing, incompatible with the product role.',
    ('user-name-en','identity'):'Adds Spanish follow-up prose to an English request.',
    ('noisy-en','history'):'Spanish draft for an English request. The existing product language-repair route is absent from this native-only probe.',
    ('noisy-en','greedy'):'Spanish draft for an English request; not a claim that product final language repair fails.',
    ('vocative-en','greedy'):'Addresses the user as Morgan, though the user supplied Morgan as the addressee.',
}
adjudication=[]
report=['# Diagnóstico nativo612: no hay una solución adoptable en estas variantes',
        'Ocho casos por cinco brazos, todos con512tokens, un solo borrador y sin guardas. Cada paso añade un componente; el último sólo cambia el muestreo. Se puntúa el conjunto, no la respuesta más favorable. El brazo nativo puede identificarse como Qwen; a partir de identidad se exige el papel real de BAXY.']
for row in responses:
    key=(row['case_id'],row['arm']); case=panel[key]
    choice=row['response']['choices'][0]
    assert choice['finish_reason']=='stop' and not choice['message'].get('reasoning_content')
    verdict='failed' if key in failures else 'correct'
    adjudication.append({**row,'text':case['text'],'criterion':case['criterion'],'verdict':verdict,
                         'reason':failures.get(key,'Correct subject, meaningful reply and appropriate language under the declared arm.')})
    report += [f"## {row['case_id']} · {row['arm']}",case['text'],choice['message']['content'],
               verdict+': '+adjudication[-1]['reason']]
write(private/'adjudication.json',adjudication)
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
scores=Counter(row['arm'] for row in adjudication if row['verdict']=='correct')
result={'utc':datetime.now(timezone.utc).isoformat(),'per_arm':8,'correct_by_arm':dict(scores),
        'all40_finish_stop':True,'reasoning_content_responses':0,'adopted':False,
        'survey':{'covered':25,'open':717,'not_applicable':0},'resources':read(out/'RESOURCES.json'),
        'interpretation':'H0012 already fails without the BAXY wrapper. Added policies/history introduce separate language/subject effects. Documented sampling improves the Morgan draft but does not solve H0012 or the whole panel. No truncation or reasoning leakage explains these40 outputs. This does not rank the model globally or certify current product finals.',
        'private_hashes':{name:sha(private/name) for name in ['panel.json','requests.jsonl','responses.jsonl','adjudication.json','RESULT.md']}}
write(out/'RESULT.json',result)
note='''# Diagnóstico612: el error coloquial también existe en el modelo nativo

40 borradores completos, sin truncamiento ni reasoning_content. Aciertos por brazo de8casos: nativo6, identidad5, políticas7, historial6, greedy5. Son comparaciones de componentes y muestreo; no cinco candidatos equivalentes ni una aceptación del producto.

H0012 falla ya sin BAXY: el modelo no reconoce bien la pregunta coloquial. Identidad introduce una interpretación de fútbol; políticas llegan a copiar SIEMPRE; con historial identifica a BAXY pero conserva una apertura irrelevante o invierte el sujeto. Cambiar al perfil recomendado no resuelve este caso. No se adopta otro prompt ni un cambio de muestreo.

Las otras variantes muestran causas distintas: historial español desvía un borrador inglés (la reparación final de idioma no forma parte de esta prueba), y greedy llama Morgan al usuario aunque éste se dirigía al asistente. Por tanto la clasificación intermedia no basta para demostrar comprensión. Campo de sujeto, historial e inferencia deben evaluarse juntos antes de otro cambio.

Servidor nativo:3495,559MiB GPU/719,297MiB RAM,16,984s para40peticiones; no son recursos de BAXY completo. Fuente606 y registro intactos. Encuesta25/717/0, cero crédito añadido por612. Todos los borradores y payloads permanecen locales, con huellas públicas; sin UI/voz ni selección de una corrida favorable.
'''
(out/'RESULT.md').write_text(note,encoding='utf-8',newline='\n')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
with (root/'.gitattributes').open('a',encoding='utf-8',newline='\n') as stream:
    stream.write('/artifacts/comprobaciones/C03/astra-native-subject612/** -text\n')
with (base/'CHECKPOINT.md').open('a',encoding='utf-8',newline='\n') as stream: stream.write('\n\n'+note)
(base/'HANDOFF.md').write_text(note+'\nNo hay procesos activos. Siguiente: heredar perfiles/modelos ya contrastados antes de decidir una alternativa para comprensión coloquial y sujeto. No repetir594/595 ni609. La variante de muestreo612 no es una solución. Aclaraciones, gramática, progreso, UI/voz/memoria conjunta y registroCPU pendientes.\n',encoding='utf-8',newline='\n')
state=read(base/'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=result['utc'],checkpoint='612 completado40/40stop, sin reasoning; H0012 falla desde el modelo nativo. Sin adopción ni procesos activos. Fuente606 publicada, Fullverde, encuesta25/717/0.',continuation='Revisar herencia de perfiles/modelos aplicables a comprensión coloquial y sujeto antes de otra comparación acotada.612 no justifica promover prompt/sampler.609 rechazado y restaurado. Mantener fuente606; cerrar aclaraciones, gramática, progreso, UI/voz/recursos y restoC03.')
write(base/'RELEVO_ACTIVO.json',state)
print(json.dumps(result,ensure_ascii=False))
