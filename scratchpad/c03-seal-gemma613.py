"""Seal Gemma613 and qualify only its direct prose profile for integration."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import os

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-gemma-subject613'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-gemma-subject613-private'
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
assert not (out/'RESULT.json').exists()
panel={(r['case_id'],r['arm']):r for r in read(private/'panel.json')}
with (private/'responses.jsonl').open(encoding='utf-8-sig') as stream: responses=list(map(json.loads,stream))
assert len(responses)==len(panel)==32
failures={
    ('H0012','native-direct'):'Interprets the colloquial expletive as kicking somebody; incorrect extra interpretation.',
    ('H0012','history-thinking'):'Misreads the expletive as kicking and fails to identify BAXY.',
    ('noisy-es','history-thinking'):'Identifies BAXY but appends Soy él, an unnatural projection of internal identity/gender instructions.',
}
adjudication=[]
report=['# Gemma613: prosa directa con contexto 8/8; integración pendiente',
        'Mismos ocho casos612, perfil Google, versión original497 y template nativo. No se eligió una respuesta por caso: se compara cada brazo completo. Las respuestas aisladas no invalidan los fallos de herramientas497.']
for row in responses:
    key=row['case_id'],row['arm']; case=panel[key]; choice=row['response']['choices'][0]
    assert choice['finish_reason']=='stop'
    thought=bool(choice['message'].get('reasoning_content'))
    assert thought==row['arm'].endswith('-thinking')
    verdict='failed' if key in failures else 'correct'
    adjudication.append({**row,'text':case['text'],'criterion':case['criterion'],'verdict':verdict,
                         'reason':failures.get(key,'Meets the declared subject, language, truthfulness and naturalness criterion.')})
    report += [f"## {row['case_id']} · {row['arm']}",case['text'],choice['message']['content'],
               verdict+': '+adjudication[-1]['reason'],f"finish_reason=stop; {row['seconds']:.3f}s; reasoning_content present={thought}"]
write(private/'adjudication.json',adjudication)
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
scores=Counter(row['arm'] for row in adjudication if row['verdict']=='correct')
metrics={}
for arm in scores:
    selected=[row for row in responses if row['arm']==arm]
    metrics[arm]={'requests':len(selected),'mean_seconds':sum(row['seconds'] for row in selected)/len(selected),
                  'mean_completion_tokens':sum(row['response']['usage']['completion_tokens'] for row in selected)/len(selected)}
result={'utc':datetime.now(timezone.utc).isoformat(),'correct_by_arm':dict(scores),'per_arm':8,
        'all32_finish_stop':True,'actual_thinking_on_responses':16,'actual_thinking_off_responses':16,
        'metrics':metrics,'resources':read(out/'RESOURCES.json'),
        'qualified_for_next_probe':'history-direct profile only; eight correct first drafts without thoughts',
        'product_promoted':False,'source_changed':False,'operational_failures497_retained':True,
        'survey':{'covered':25,'open':717,'not_applicable':0},
        'private_hashes':{name:sha(private/name) for name in ['panel.json','requests.jsonl','responses.jsonl','adjudication.json','RESULT.md']}}
write(out/'RESULT.json',result)
note='''# Gemma613: ocho respuestas directas correctas con contexto

Gemma4-E2B-it original497 Q4_K_M, perfil GoogleT1/p.95/k64/min0 y template/lazy-on medidos. Con identidad, políticas e historial, el modo directo resuelve8/8: H0012, variedades ES/EN, vocativos y nombres propios con sujeto correcto. Native-direct7/8; native-thinking8/8; history-thinking6/8. Thinking añade coste y vuelve a interpretar mal H0012; además copia una indicación interna de género. Se conservan todos los resultados, no sólo el brazo favorable.

Las32 respuestas terminan normalmente. Se verificó reasoning_content en las16 peticiones con thinking y su ausencia en las16 directas. Servidor nativo:1681,988MiB GPU/987,563MiB RAM,60,234s; los tiempos por brazo están en RESULT.json. No son recursos de BAXY completo ni prueba de que todo el producto quepa en1,64GiB.

Se califica únicamente el perfil directo para un contraste de integración614. Los errores de interfaz/polaridad de497 siguen abiertos y bloquearían una promoción global.614 repite los35 casos605 con el producto606, override aislado de modelo/backend y un hook de parámetros de chat/lazy-on; el resto de roles se conserva para localizar transformaciones. No se cambia registro, fuente, prompts, historial, guardas ni respuestas. Las métricas nativas no acreditan UI, voz, aceptación ni cobertura de encuesta:25/717/0.
'''
(out/'RESULT.md').write_text(note,encoding='utf-8',newline='\n')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
with (root/'.gitattributes').open('a',encoding='utf-8',newline='\n') as stream:stream.write('/artifacts/comprobaciones/C03/astra-gemma-subject613/** -text\n')
with (base/'CHECKPOINT.md').open('a',encoding='utf-8',newline='\n') as stream:stream.write('\n\n'+note)
(base/'HANDOFF.md').write_text(note+'\nActivo614 sesión16366, TEMP/c03-gemma-product614.log. Recoger, leer todos los finales y los wire logs privados; no adelantar promoción. Fuente606 y Full606 intactos. H0012/Atlas y todos los demás criterios siguen abiertos hasta evidencia de producto.\n',encoding='utf-8',newline='\n')
state=read(base/'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=result['utc'],checkpoint='613 terminado:history-direct8/8,native-direct7/8,native-thinking8/8,history-thinking6/8. Perfil directo pasa a producto614, sesión16366. Fuente606/registro intactos; encuesta25/717/0.',continuation='Recoger614 TEMP/c03-gemma-product614.log, adjudicar35finales/audits y parámetros efectivos. No promoción global por613:497 conserva errores de herramientas; otros roles614 congelados, no declaración de óptimo. UI/voz/recursos y restoC03 pendientes.')
write(base/'RELEVO_ACTIVO.json',state)
print(json.dumps(result,ensure_ascii=False))
