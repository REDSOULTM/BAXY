"""Preserve product failures and reject the unqualified guard subtype."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
home = Path(os.environ['LOCALAPPDATA']) / 'BAXY'

def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):
    with p.open(encoding='utf-8-sig') as stream: return list(map(json.loads, stream))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, v): p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
def seal(out, private, result, note, names):
    result['private_hashes'] = {name:sha(private/name) for name in names}
    write(out/'RESULT.json', result)
    (out/'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
    write(out/'PINS.json', {p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
    with (root/'.gitattributes').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write('/artifacts/comprobaciones/C03/'+out.name+'/** -text\n')
    with (base/'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write('\n\n'+note)

out = base/'astra-gemma-product614'
private = home/'C03-gemma-product614-private'
assert not (out/'RESULT.json').exists()
assert read(out/'EXIT.json') == {'exitCode':0,'manifest_unchanged':True}
panel = read(private/'panel.json')
finals = [r for r in rows(private/'capture/events.jsonl') if r.get('type')=='terminal']
assert len(panel)==len(finals)==35
failures = {
    'H0218':'Uses internal style word tuteo as the user addressee; unnatural response.',
    'H0032':'Valid social acknowledgement becomes a false interpretation failure. Native chat returns a reasonable conversational question; the later knowledge-question-only guard rejects it because social subtype was erased.',
}
adjudication = [{**case,'terminal':final,'verdict':'failed' if case['case_id'] in failures else 'correct',
                 'reason':failures.get(case['case_id'],'Meets declared subject, language, truthfulness and naturalness criterion.')}
                for case,final in zip(panel,finals)]
assert sum(r['verdict']=='correct' for r in adjudication)==33
write(private/'adjudication.json',adjudication)
report = ['# Producto614: 33/35; candidato sin promoción']
for r in adjudication:
    report += ['## '+r['case_id'],r['text'],r['terminal']['final'],r['verdict']+': '+r['reason']]
report += ['## Primera transformación incorrecta H0032',
           'HTTP95: stable_conversation/zero. HTTP98 y102: ¿En qué te puedo ayudar ahora? Native no-tool conserva knowledge y main rechaza la pregunta social como explicación sin respuesta. El error posterior no demuestra que el texto del usuario fuera inválido.',
           '## H0218','HTTP76: De nada, tuteo. ¿En qué te puedo ayudar? SYSTEM incluye Eres un él. Tuteas. El borrador ya usa una palabra de estilo como apelativo; ninguna corrección literal adoptada.']
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note614 = '''# Producto614: Gemma directo 33 de 35

Fuente606 y registro Qwen intactos. Gemma original497 con perfil directo613 resuelve H0012 y el vocativo Atlas, pero falla H0218 (apelativo «tuteo») y H0032 (una pregunta social válida rechazada por presentarse como conocimiento). No se promueve: el resultado no mejora el total33/35 de605 y las herramientas497 siguen pendientes. No se acredita encuesta con este override ni se reabren casos cubiertos por la fuente registrada.

Pico1681,988MiB GPU y2827,551MiB RAM en74,906s, sin infracciones. Es un conductor de producto sin UI/voz simultáneas, no el mínimo de BAXY completo. Encuesta25 cubiertos/717 abiertos/0 no aplicables. Fuente606 conserva Full606 verde.
'''
seal(out,private,{'utc':datetime.now(timezone.utc).isoformat(),'source':606,'finals':35,'correct_finals':33,
                 'failed_cases':failures,'resources':read(out/'resources.json'),'product_promoted':False,
                 'ui_or_voice_credit':False,'survey':{'covered':25,'open':717,'not_applicable':0}},
     note614,['panel.json','capture/events.jsonl','http-posts.jsonl','adjudication.json','RESULT.md','turn-audit.jsonl'])

out = base/'astra-social-kind615'
private = home/'C03-social-kind615-private'
assert not (out/'RESULT.json').exists()
panel = {(r['case_id'],r['arm']):r for r in read(private/'panel.json')}
responses = rows(private/'responses.jsonl')
assert len(panel)==len(responses)==40
adjudication=[]
for r in responses:
    case=panel[r['case_id'],r['arm']]
    choice=r['response']['choices'][0]
    assert choice['finish_reason']=='stop' and not choice['message'].get('reasoning_content')
    raw=json.loads(choice['message']['content'])
    normalized_count='zero' if raw['request_type'] in {'stable_conversation','social_conversation'} else raw['effect_count']
    adjudication.append({**r,'text':case['text'],'expected_type':case['expected_type'],'expected_count':case['expected_count'],
                         'raw':raw,'type_correct':raw['request_type']==case['expected_type'],
                         'raw_count_correct':raw['effect_count']==case['expected_count'],
                         'normalized_correct':raw['request_type']==case['expected_type'] and normalized_count==case['expected_count']})
write(private/'adjudication.json',adjudication)
report=['# Guardia615: subtipo rechazado para adopción']
for r in adjudication:
    report += ['## '+r['case_id']+' · '+r['arm'],r['text'],json.dumps(r['raw'],ensure_ascii=False),
               'Esperado: '+r['expected_type']+'/'+r['expected_count']+'; correcto normalizado='+str(r['normalized_correct'])]
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
scores=Counter(r['arm'] for r in adjudication if r['normalized_correct'])
note615 = '''# Guardia615: clasificación social insuficiente

40 llamadas nativas,20 casos por brazo. El subtipo reconoce cinco reacciones sociales, pero también etiqueta como social una pregunta de identidad y una petición de redactar un saludo. Una lectura de archivo pasa de external_read a environment_change. Ambos brazos conservan errores de negación, argumentos ausentes y cardinalidad compuesta. Los conteos crudos erróneos de conversación se distinguen de la normalización a cero que ya hace el runtime.

No se adopta la nueva representación. Se conserva el resultado completo y se prueba616 con perfil Google y pensamiento directo/activado, manteniendo ambos brazos a3072tokens para verificar coste y cortes. Si no aparece una distinción general viable, se abandona esta vía; no se añaden alias ni excepciones de literal. Sin cambios de fuente, registro ni cobertura25/717/0.
'''
seal(out,private,{'utc':datetime.now(timezone.utc).isoformat(),'per_arm':20,'normalized_correct_by_arm':dict(scores),
                 'source_adopted':False,'all40_finish_stop':True,'resources':read(out/'RESOURCES.json')},
     note615,['panel.json','requests.jsonl','responses.jsonl','adjudication.json','RESULT.md'])
state=read(base/'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
             checkpoint='614 producto33/35;615 subtipo rechazado. Fuente606/Full606/registro intactos. Encuesta25/717/0.',
             continuation='Recoger616 sesión81745 TEMP/c03-social-thinking616.log, adjudicar40 respuestas y razonamientos. Segundo intento de esta vía; si insuficiente cambiar estrategia. Sellar/publicar612–616. C03/UI/voz/cobertura pendientes.',
             pendingOwnerClarification=None)
write(base/'RELEVO_ACTIVO.json',state)
(base/'HANDOFF.md').write_text(note614+'\n'+note615+'\nActivo616 sesión81745, TEMP/c03-social-thinking616.log. No fuente adoptada desde606. Publicación pendiente de evidencia612–616; rama Goal-c03, main intacto.\n',encoding='utf-8',newline='\n')
print(json.dumps({'614_correct':33,'615_normalized_scores':dict(scores),'source_changed':False}))
