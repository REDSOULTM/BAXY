from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,json,os,subprocess
root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-coordinate-product546-private'
out=base/'astra-coordinate-product546'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert read(out/'EXIT.json')['exitCode']==0 and not read(out/'resources.json')['violations']
panel=read(private/'panel.json')
events=[json.loads(s) for s in (private/'capture/events.jsonl').read_text(encoding='utf-8-sig').splitlines()]
terminals=[e for e in events if e.get('type')=='terminal']
assert len(terminals)==len(panel)==6
posts=[json.loads(s) for s in (private/'http-posts.jsonl').read_text(encoding='utf-8-sig').splitlines()]
results=[]
for i,(case,terminal) in enumerate(zip(panel,terminals)):
    writers=[r for r in posts if r['stage']=='request' and r['payload'].get('messages') and r['payload']['messages'][0]['content'].startswith('Eres BAXY, un compañero.') and r['payload']['messages'][-1]['content'].startswith(case['text']+'\n')]
    assert len(writers)==1
    content=writers[0]['payload']['messages'][-1]['content']
    facts=json.loads(next(s[11:] for s in content.splitlines() if s.startswith('situation: ')))
    if i<3:
        steps=facts['completedStepsInOrder']
        assert len(steps)==2
        clock=next(s['resultAtThisStep']['clock'] for s in steps if s['operation']=='system.time')
        battery=next(s['resultAtThisStep']['seen']['battery']['chargePercent'] for s in steps if s['operation']=='system.status')
        assert clock in terminal['final'] and str(battery)+'%' in terminal['final']
        note='Hora y batería completas, coinciden con las observaciones de ambas operaciones. Idioma y orden del pedido conservados; sin confirmación redundante.'
    elif i==3:
        note='Fecha y RAM disponibles conservadas:2026-09-09 y2745311232bytes. La primera persona Tengo puede confundir RAM del sistema con BAXY; queda abierta la presentación general de recursos.'
    elif i==4:
        note='Disco y batería presentes;127255064576bytes narrados127.2GB. Se conserva evidencia completa, pero no se certifica redondeo matemático de esta presentación.'
    else:
        assert facts['seen']['scope']=='os_memory'
        note='Regresión de scope combinado: una sola lectura os_memory conserva Windows11 y RAM, sin descomposición adicional. No se acredita exactitud de unidades sólo por decir16GB.'
    results.append({**case,'ordinal':i+1,'terminal':terminal,'native_request_id':writers[0]['id'],'facts':facts,'adjudication':note})
write(private/'adjudication.json',results)
lines=['# Producto546 — preguntas coordinadas','']
for r in results:
    lines += [f"## {r['ordinal']} · {r['origin']}",'',r['text'],'',r['terminal']['final'],'',r['adjudication'],'','```json',json.dumps(r['facts'],ensure_ascii=False,indent=2),'```','']
(private/'RESULT.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
registry=private.parent/'C03-survey-requirements336-private/requirements.jsonl'
before=registry.read_bytes()
assert not (private/'requirements-before-adjudication.jsonl').exists()
(private/'requirements-before-adjudication.jsonl').write_bytes(before)
rows=[json.loads(s) for s in before.decode('utf-8-sig').splitlines()]
row=next(r for r in rows if r['case_id']=='H0079')
assert row['verification_status']=='open'
row.update(verification_status='covered',generalization_status='verified_product_variants',verification_updated_at=datetime.now(timezone.utc).isoformat(),verification_reason='Producto546 resuelve hora+batería con el literal humano, variante inglesa y orden inverso español; ambos hechos contrastados por invocación. Lecturas y objetos distintos en los controles de composición, más catálogo incompleto/negación/otro dispositivo/texto citado verificados por dueñas545. No extiende cobertura a la presentación general de RAM/disco ni a casos similares.')
row['verification_evidence'].append({'campaign':'astra-coordinate-product546','source_commit':'1d08cc297547ebc1d38d98492a41973816423416','private_adjudication':str(private/'adjudication.json'),'ordinals':[1,2,3],'composition_controls':[4,5,6],'ui_or_voice_credit':False})
registry.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8',newline='\n')
counts=Counter(r['verification_status'] for r in rows)
assert counts=={'covered':7,'open':735}
counts={'covered':7,'open':735,'not_applicable':0}
summary=read(base/'SURVEY_REQUIREMENTS336.json')
summary.update(requirements_sha256=sha(registry),validated_current=7,verification_counts=counts,updated_at=datetime.now(timezone.utc).isoformat())
write(base/'SURVEY_REQUIREMENTS336.json',summary)
write(out/'RESULT.json',{'published':6,'newly_covered':['H0079'],'survey_counts':counts,'resources':read(out/'resources.json'),'private_report':str(private/'RESULT.md'),'private_report_sha256':sha(private/'RESULT.md'),'adjudication_sha256':sha(private/'adjudication.json'),'limitations':'No UI/audio; resource presentation ambiguities remain explicitly open. No automatic coverage of similar survey cases.'})
(out/'RESULT.md').write_text('''# Producto546 — hora y batería verificadas

Fuente545 publicada en1d08cc297547ebc1d38d98492a41973816423416. Seis finales, exit0 y sin cortes. Los tres pedidos de hora+batería, en español, inglés y orden inverso, conservan ambos datos verificados. El scope combinado de sistema/RAM sigue siendo una sola lectura. RAM/disco tienen presentación de sujeto y unidades pendiente; no se declara resuelta.

Encuesta7 cubiertos/735 abiertos/0 no aplicables; nuevoH0079. GPU3497,559MiB y RAM1893,363MiB,28,296s. Conductor compartido sin UI/voz: no representa el presupuesto conjunto final. Informe literal y payloads en la ruta privada deRESULT.json.
''',encoding='utf-8',newline='\n')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
state=read(base/'RELEVO_ACTIVO.json')
state.update(surveyVerificationCounts=counts,publishedSourceCommit='1d08cc297547ebc1d38d98492a41973816423416',checkpoint='546: actual compound reads verified; survey7covered/735open/0NA. E5 fidelity549 running.')
write(base/'RELEVO_ACTIVO.json',state)
with (base/'CHECKPOINT.md').open('a',encoding='utf-8',newline='\n') as stream:
    stream.write('\n\n## Tramo546 — composición confirmada en producto\n\nFuente545 publicada en1d08cc29. Producto546 completó6 finales sin cortes; hora+batería verificadas enES/EN/orden inverso. Encuesta7 cubiertos/735 abiertos/0NA, nuevoH0079; presentación general de recursos abierta. GPU3497,559MiB/RAM1893,363MiB,28,296s, sinUI/voz. E5 comparación547 completada; tokenizer548 identifica divergencia por normalización, no defecto de FP32.549 contrasta tokenizador efectivo y shortlist real; sin adopción.\n')
with (root/'.gitattributes').open('a',encoding='utf-8',newline='\n') as stream:stream.write('/artifacts/comprobaciones/C03/astra-coordinate-product546/** -text\n')
print(json.dumps(counts))
