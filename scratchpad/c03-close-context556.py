from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,json,os,subprocess
root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-context-product556-private'
out=base/'astra-context-product556'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
panel=read(private/'panel.json')
events=[json.loads(s) for s in (private/'capture/events.jsonl').read_text(encoding='utf-8-sig').splitlines()]
terminals=[r for r in events if r.get('type')=='terminal']
assert len(panel)==len(terminals)==10 and read(out/'EXIT.json')['exitCode']==0
assert not read(out/'resources.json')['violations']
posts=[json.loads(s) for s in (private/'http-posts.jsonl').read_text(encoding='utf-8-sig').splitlines()]
first=next(r for r in posts if r['id']==11 and r['stage']=='response')
retry=next(r for r in posts if r['id']==12 and r['stage']=='response')
parsed=json.loads(first['response']['choices'][0]['message']['content'])
answer=json.loads(retry['response']['choices'][0]['message']['content'])['answer']
assert parsed['direct_answer']=='Eso era todo, gracias.'
assert parsed['resolved_meaning']!=terminals[5]['final']==answer
assert 'Solmira729' in terminals[9]['final']
notes={'H0065':'Español sigue atribuyendo CPU total aBAXY: Estoy usando13,75%. Inglés comunica16.9% del procesador. Abierto, sin crédito por emisión.',
       'H0073':'Lectura de volumen100/no silenciado repetida como contexto; sin nueva adjudicación de requisito.',
       'H0078':'Cuatro despedidas/agradecimientos ES/EN reciben acuse dirigido a la persona, sin publicar análisis de usuario ni eco. El literal español activa realmente el reintento de555: native11 produce eco y análisis, native12 genera la respuesta final. Generaliza a cierre corto, cierre explícito, gratitud y cambio deidioma/contexto.',
       'continuity-control':'Declaración temporal y recuerdo deSolmira729; final conserva el literal exacto, sin afirmar guardado privado. Control de regresión, no requisito nuevo automáticamente cubierto.'}
adjudication=[{**c,'ordinal':i+1,'terminal':terminals[i],'adjudication':notes[c['case_id']]} for i,c in enumerate(panel)]
write(private/'adjudication.json',adjudication)
lines=['# Producto556 — cierre contextual','',*['\n'.join([f"## {r['ordinal']} · {r['case_id']}",'',r['text'],'',r['terminal']['final'],'',r['adjudication'],'']) for r in adjudication], '\n## Evidencia nativa del reintento\n',json.dumps({'first_resolution':parsed,'retry_answer':answer},ensure_ascii=False,indent=2)]
(private/'RESULT.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
registry=private.parent/'C03-survey-requirements336-private/requirements.jsonl'
assert not (private/'requirements-before-adjudication.jsonl').exists()
before=registry.read_bytes();(private/'requirements-before-adjudication.jsonl').write_bytes(before)
rows=[json.loads(s) for s in before.decode('utf-8-sig').splitlines()]
row=next(r for r in rows if r['case_id']=='H0078')
assert row['verification_status']=='open'
row.update(verification_status='covered',generalization_status='verified_product_variants',verification_reason=notes['H0078'],verification_updated_at=datetime.now(timezone.utc).isoformat())
source_commit=subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,text=True,check=True).stdout.strip()
assert source_commit.startswith('8027c222')
row['verification_evidence'].append({'campaign':'astra-context-product556','source_commit':source_commit,'private_adjudication':str(private/'adjudication.json'),'ordinals':[5,6,7,8],'native_retry_ids':[11,12],'ui_or_voice_credit':False})
registry.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8',newline='\n')
assert Counter(r['verification_status'] for r in rows)=={'covered':8,'open':734}
counts={'covered':8,'open':734,'not_applicable':0}
summary=read(base/'SURVEY_REQUIREMENTS336.json');summary.update(requirements_sha256=sha(registry),validated_current=8,verification_counts=counts,updated_at=datetime.now(timezone.utc).isoformat());write(base/'SURVEY_REQUIREMENTS336.json',summary)
write(out/'RESULT.json',{'published':10,'newly_covered':['H0078'],'survey_counts':counts,'resources':read(out/'resources.json'),'native_retry_verified':[11,12],'private_report':str(private/'RESULT.md'),'private_report_sha256':sha(private/'RESULT.md'),'adjudication_sha256':sha(private/'adjudication.json'),'limitations':'CPU subject remains wrong inSpanish. Headless conductor, no UI/audio credit.'})
note='''# Producto556 — reintento contextual verificado

10 finales, exit0/sin cortes. La despedida española genera un eco en direct_answer y análisis en resolved_meaning(native11); la fuente555 ejecuta el reintento directo(native12) y publica su respuesta, sin el análisis interno. Cuatro variantes de cierre ES/EN y control de recuerdo literalSolmira729 completados. CPU española sigue con sujeto equivocado y permanece abierta.

Encuesta8 cubiertos/734 abiertos/0NA; nuevoH0078. GPU3497,559MiB/RAM2444,422MiB,39,469s, sinUI/voz. Fuente555 publicada8027c222. No equivale a cierre deC03 ni a cobertura automática de casos similares.
'''
(out/'RESULT.md').write_text(note,encoding='utf-8',newline='\n')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
with (root/'.gitattributes').open('a',encoding='utf-8',newline='\n') as stream:stream.write('/artifacts/comprobaciones/C03/astra-context-product556/** -text\n')
with (base/'CHECKPOINT.md').open('a',encoding='utf-8',newline='\n') as stream:stream.write('\n\n'+note)
state=read(base/'RELEVO_ACTIVO.json');state.update(checkpoint='556: closing retry verified in real product; survey8/734/0. Native Gemma557 screen running on18 actual writer captures.',surveyVerificationCounts=counts,publishedSourceCommit=source_commit);write(base/'RELEVO_ACTIVO.json',state)
handoff=base/'HANDOFF.md';handoff.write_text('# Handoff C03 — 556\n\n'+note.split('\n\n',1)[1]+'\nGemma557: selección de18 escritores reales, excluye cierre ya reparado. Perfil462 thinking/lazy, sin nuevas instrucciones ni unidades553. Sesión98930 en curso; recoger y adjudicar, sin promoción implícita.\n\n'+handoff.read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
print(json.dumps(counts))
