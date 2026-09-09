"""Read-only adjudication of two previously unverified window answers."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import sys
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'src'))
from baxy_mind.effect_intent import resolve_explicit_effects
base=root/'artifacts/comprobaciones/C03';home=Path(os.environ['LOCALAPPDATA'])/'BAXY'
prior=home/'C03-survey-readonly541-private';private=home/'C03-window-evidence632-private';out=base/'astra-window-evidence632'
private.mkdir(exist_ok=False);out.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def rows(p):return [json.loads(l) for l in p.open(encoding='utf-8-sig')]
adjudication=json.loads((prior/'adjudication.json').read_text(encoding='utf-8'))
cases=[r for r in adjudication if r['case_id']=='H0040'];assert len(cases)==2
turns=[r for r in rows(prior/'turn-audit.jsonl') if r.get('request_id') in {'85','89'}]
compose=[r for r in rows(prior/'compose-audit.jsonl') if r.get('trace') in {'t22','t23'}]
raw=[r for r in rows(prior/'raw-replies.jsonl') if r.get('request_sha256')=='1656dea419905ec8e949e1baace7bab996054dd5e9c3881ffea8897b73bda93f']
assert len(compose)==1 and compose[0]['payload']['operation']=='window.active'
assert compose[0]['payload']['seen']['count']==1
english=next(r for r in turns if r.get('request_id')=='89' and r.get('phase')=='final')
assert english['final']['kind']=='conversation' and english['final']['effect_operations']==[]
ops=('window.active','window.list','window.application.status','app.installed','app.open')
probes=[]
for text in [cases[0]['text'],cases[1]['text'],'hay alguna ventana de Notepad abierta','Is Paint open?']:
 intent=resolve_explicit_effects(text,ops)
 probes.append({'text':text,'operations':list(intent.operations) if intent else None})
write(private/'evidence.json',{'cases':cases,'turns':turns,'compose':compose,'raw_replies':raw,'current_parser_probes':probes})
report=['# Ventanas632 — negaciones no acreditadas por las observaciones',
 'La respuesta española541 afirma que no existe ninguna ventana de la aplicación solicitada. El único hecho recibido es window.active: una ventana ChatGPT enfocada. Esa observación no enumera las demás ventanas y no acredita ausencia.',
 'La respuesta inglesa541 afirma que Spotify no está abierto. Auditoría89 devuelve conversation/knowledge sin operaciones; raw-replies muestra la misma negación sin observación. Es invención de estado, no éxito verificado.',
 'El reconocedor actual sigue asignando window.active al literal español y a la variante con Notepad. El inglés no tiene efecto explícito; no se ejecutó el decisor nativo actual y no se presume su resultado.',
 '## Literales y respuestas']
for r in cases:report.extend([r['text'],r['terminal']['final']])
(private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note='''# Auditoría632 — ausencia de ventanas no demostrada

H0040 permanece abierto. Las dos frases de541 que parecían correctas no lo están: el español deduce ausencia global de una lectura de la única ventana enfocada; el inglés responde desde conocimiento sin ejecutar ninguna observación. Las trazas85/89 y la composición t22 demuestran la diferencia. No basta comprobar que el texto «suena posible».

El reconocedor actual repite el alcance incorrecto window.active para el literal español y otra aplicación. La rama inglesa no se ejecutó con el modelo actual: su fallo histórico queda separado de la reproducción actual de Python. Esta auditoría no usa inferencia, no cambia fuente ni modifica el registro de encuesta mientras Full630 está en marcha.

Siguiente reparación, después de resolver y publicar630: localizar la regla explícita que reduce cualquier ventana nombrada a window.active, conservar el alcance por aplicación del catálogo y comprobar el resultado con aplicaciones abiertas/cerradas y español/inglés. No relajar el compositor para aceptar una ausencia sin enumeración o lectura específica. No hay cobertura nueva,25/717/0, ni crédito UI/voz.
'''
(out/'RESULT.md').write_text(note,encoding='utf-8',newline='\n')
write(out/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'case_id':'H0040','historical_replies':2,'historical_correct':0,'current_spanish_parser_wrong_scope':True,'current_english_product_run':False,'source_modified':False,'survey_modified':False,
 'current_sources':{p:sha(root/p) for p in ['src/baxy_mind/effect_intent.py','src/baxy_mind/__main__.py']},
 'historical_sources':{s:sha(prior/s) for s in ['adjudication.json','turn-audit.jsonl','compose-audit.jsonl','raw-replies.jsonl','shell-trace.jsonl']},
 'private_hashes':{s:sha(private/s) for s in ['evidence.json','RESULT.md']}})
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
with (root/'.gitattributes').open('a',encoding='utf-8',newline='\n') as stream:stream.write('/artifacts/comprobaciones/C03/astra-window-evidence632/** -text\n')
print({'H0040_historical_correct':0,'current_spanish_scope_wrong':True,'survey_unchanged':True})
