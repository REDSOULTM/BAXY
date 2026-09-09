"""Preserve complete resumed evidence and only adjudicate demonstrated behaviors."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
import os

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-survey-resume543-private'
out=base/'astra-survey-resume543'
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
panel=read(private/'panel.json')
with (private/'capture/events.jsonl').open(encoding='utf-8-sig') as handle:
    events=list(map(json.loads,handle))
terminals=[r for r in events if r.get('type')=='terminal']
assert len(panel)==len(terminals)==22
assert read(out/'EXIT.json')['exitCode']==0
assert read(out/'resources.json')['violations']==[]
gpu_payloads=[]
with (private/'http-posts.jsonl').open(encoding='utf-8-sig') as handle:
    for line in handle:
        row=json.loads(line)
        if row['stage']!='request':continue
        messages=row['payload'].get('messages',[])
        if not messages or not messages[0]['content'].startswith('Eres BAXY, un compañero.'):continue
        content=messages[-1]['content']
        if not any(content.startswith(c['text']+'\n') for c in panel[:3]):continue
        for segment in content.splitlines():
            if segment.startswith('situation: '):
                facts=json.loads(segment[len('situation: '):])
                if facts.get('operation')=='system.status':
                    seen=facts['seen']
                    assert seen['scope']=='gpu_identity' and len(seen['adapters'])>0
                    gpu_payloads.append({'request_id':row['id'],'scope':seen['scope'],
                                         'adapter_count':len(seen['adapters'])})
assert len(gpu_payloads)==3
notes={
 'H0026':'542 confirmado en producto: los tres casos entregan gpu_identity con adaptadores. Las respuestas conservan NVIDIA y AMD; redondean capacidad como6GB/512–519MB. No se acredita la exactitud de unidades ni se borra el fallo español original541. Sigue abierto hasta comprobar el literal original y la conversión explícita.',
 'H0041':'Grupo completo entre541 y543: raíces144→12 y225→15 en español;81→9 en inglés. Valores distintos y cambio de sesión/contexto sin arrastrar el resultado previo.',
 'H0042':'Hello? y Buenos días, BAXY. reciben saludos directos en inglés y español, sin afirmar acciones ni reutilizar el tema de hardware previo.',
 'H0062':'El agradecimiento histórico y su variante inglesa reciben respuestas directas, breves y en su idioma; sin atribuir acciones no verificadas.',
 'H0063':'Lecturas de batería útiles en ambos idiomas. Mantener abierto hasta vincular las observaciones y controles de valores/estados; no cubierto sólo por dos frases con95%.',
 'H0065':'Fallo de sujeto en español: Estoy usando23,75% atribuye a BAXY una medida de CPU total. Inglés conserva la medida de todo el procesador. Abierto.',
 'H0073':'Lecturas de volumen100 y sonido no silenciado. Abierto hasta comprobar postlecturas y variantes numéricas; no confundir lectura con cambio de volumen.',
 'H0078':'Inglés responde Alright; español publica metanarración en tercera persona: El usuario ha indicado... Abierto.',
 'H0079':'Ambas lecturas compuestas fallan: español pregunta si se desea exactamente lo ya pedido; inglés dice que no pudo interpretar. Debe resolver hora y batería sin perder una mitad.',
 'H0080':'Ambos idiomas informan online. Abierto hasta contrastar los hechos de conectividad por invocación y sus límites.',
 'H0087':'Identifica NVIDIA en ambos pedidos. Abierto para vincular las observaciones y generalización; no se extiende automáticamente el crédito de alcance542.',
}
results=[{**c,'ordinal':i+1,'terminal':terminals[i],'adjudication':notes[c['case_id']]} for i,c in enumerate(panel)]
write(private/'adjudication.json',results)
lines=['# Sesión543 — producto con alcance GPU corregido','',
       '22/22 finales publicados; exit0 y sin cortes. Son resultados emitidos, no22 casos aprobados. Sin UI/voz física.','']
for r in results:
    lines.extend([f'## {r["ordinal"]} · {r["case_id"]} · {r["origin"]}','',r['text'],'',r['terminal']['final'],'',r['adjudication'],''])
(private/'RESULT.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
registry=private.parent/'C03-survey-requirements336-private/requirements.jsonl'
before=registry.read_bytes()
(private/'requirements-before-adjudication.jsonl').write_bytes(before)
requirements=list(map(json.loads,before.decode('utf-8-sig').splitlines()))
now=datetime.now(timezone.utc).isoformat()
newly_covered={'H0041','H0042','H0062'}
for r in requirements:
    if r['case_id'] not in notes:continue
    r['verification_reason']=notes[r['case_id']]
    r['verification_updated_at']=now
    r['verification_evidence'].append({'campaign':'astra-survey-resume543',
        'source_commit':'56480246','private_adjudication':str(private/'adjudication.json'),
        'ordinals':[x['ordinal'] for x in results if x['case_id']==r['case_id']],
        'ui_or_voice_credit':False})
    if r['case_id'] in newly_covered:
        r['verification_status']='covered'
        r['generalization_status']='verified_product_variants'
registry.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in requirements),encoding='utf-8',newline='\n')
counts=Counter(r['verification_status'] for r in requirements)
assert counts=={'covered':6,'open':736}
summary_path=base/'SURVEY_REQUIREMENTS336.json'
summary=read(summary_path)
summary.update(requirements_sha256=sha(registry),validated_current=6,updated_at=now,
               verification_counts={'covered':6,'open':736,'not_applicable':0})
write(summary_path,summary)
report={'published':22,'planned':22,'exit_code':0,'gpu_scope_verified':gpu_payloads,
        'resources':read(out/'resources.json'),'newly_covered':sorted(newly_covered),
        'survey_counts':summary['verification_counts'],'notes':notes,
        'private_report':str(private/'RESULT.md'),'private_report_sha256':sha(private/'RESULT.md'),
        'adjudication_sha256':sha(private/'adjudication.json')}
write(out/'RESULT.json',report)
(out/'RESULT.md').write_text('''# Producto543 — alcance corregido y encuesta reanudada

La fuente542 entrega gpu_identity con adaptadores en los tres controles de memoria de video, sin caer al resumen de CPU/RAM. Las respuestas ya identifican la GPU dedicada. La exactitud de las unidades y el literal español que falló541 siguen pendientes; no se da por resuelta toda la presentación de VRAM.

22/22 finales publicados, exit0, sin cortes: GPU3497,559MiB, RAM2424,773MiB,65,344s. Sin UI/voz física; no es el consumo conjunto certificado de BAXY. Se completaron las19 entradas no ejecutadas541, en una nueva sesión explícita.

Encuesta:6 cubiertos/736 abiertos/0 no aplicables. Nuevos: H0041(raíces con tres valores y ES/EN), H0042(saludos ES/EN), H0062(agradecimiento ES/EN). Se conserva la evidencia previa de541; no se cubren grupos sólo por coincidencia de familia.

Nuevos fallos concretos: la medida de CPU total se atribuye a BAXY en español; el cierre de conversación español genera metanarración; pedir hora y batería juntos no resuelve ambas lecturas. Las lecturas de batería, volumen, conectividad y GPU tienen evidencia pendiente de adjudicación por invocación y variantes relevantes, no se marcan automáticamente.
''',encoding='utf-8',newline='\n')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
print(json.dumps({'survey':summary['verification_counts'],'gpu_scope_controls':len(gpu_payloads)}))
