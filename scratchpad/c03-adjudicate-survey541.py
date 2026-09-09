"""Adjudicate completed product evidence; never credit unrun or merely mapped cases."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
import os

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-survey-readonly541'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-survey-readonly541-private'
registry=private.parent/'C03-survey-requirements336-private/requirements.jsonl'
panel=json.loads((private/'panel.json').read_text(encoding='utf-8'))
with (private/'capture/events.jsonl').open(encoding='utf-8-sig') as handle:
    events=list(map(json.loads,handle))
terminals=[r for r in events if r.get('type')=='terminal']
assert len(panel)==44 and len(terminals)==25
notes={
 'H0002':'París/Roma/Lima correctos. Literal histórico y dos países distintos, español e inglés; no confunde el cambio de país con el contexto previo.',
 'H0003':'Abierto. La respuesta libre afirma un ranking mundial de bibliotecas sin respaldo y la variante del Pacífico añade una relación de dimensiones no sustentada. La variante lunar es correcta; no compensa las otras.',
 'H0007':'Abierto. La lectura contiene logicalProcessorCount16; el español dice16 núcleos sin distinguirlos de los físicos. El inglés sí dice logical cores. No se acredita un conteo físico no observado.',
 'H0012':'Abierto para revisión de voz y cambio de referente: ambas respuestas repiten el juego de palabras de chuta y referencias a temas anteriores. Identidad BAXY conservada; no se da crédito automático sólo por el nombre.',
 'H0016':'Einstein, Newton y Marie Curie conservan persona, área y aportes; cambian nombres y español/inglés. No mezclan las biografías del diálogo previo.',
 'H0021':'Identidad propia BAXY en español e inglés, sin adoptar nombres del historial ni afirmar efectos.',
 'H0025':'Abierto. Inglés informa124.58GB conforme a124584828928bytes observados. La variante española plural se niega por fuera de catálogo aunque la familia de lectura existe; no se acredita la lectura de todos los discos.',
 'H0026':'Abierto. Español convierte6287261696bytes dedicados en8GB, confundiendo probablemente el límite compartido8269754368bytes. Inglés recibió summary sin adapters tras perder gpu_identity y afirmó sólo GPU integrada. Primer fallo: prosa; segundo: alcance y prosa. Fuente542 repara el alcance, pendiente producto.',
 'H0037':'Abierto. La observación isChargingfalse/isAcOnlinetrue/chargePercent95 sustenta no estar cargando; el español añade ya está cargada. Inglés correcto; no se equipara95% a carga completa.',
 'H0040':'Lecturas Steam y Spotify publican no abierto. Se conserva como evidencia pendiente de adjudicar sus observaciones por invocación; no se cubre sólo por dos frases plausibles.',
 'H0041':'12 y15 correctos; falta la variante inglesa81 porque la corrida fue cortada antes. No se marca cubierto con un grupo incompleto.',
}
covered={'H0002','H0016','H0021'}
results=[]
for i,case in enumerate(panel):
    terminal=terminals[i] if i<len(terminals) else None
    results.append({**case,'ordinal':i+1,'terminal':terminal,
                    'adjudication':notes.get(case['case_id'],'No ejecutado en541; sin crédito.'),
                    'case_covered':case['case_id'] in covered})
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
write(private/'adjudication.json',results)
md=['# Sesión real541 — encuesta y generalización','',
    '44 turnos previstos;25finales publicados. Corte por RAM libre del sistema bajo768MiB. Las19entradas restantes no tienen resultado. Fuente120713be, runtime registrado, perfil aislado, sin UI/voz.','']
for row in results:
    md.extend([f'## {row["ordinal"]} · {row["case_id"]} · {row["origin"]}','',row['text'],'',
               row['terminal']['final'] if row['terminal'] else '[no ejecutado]','',row['adjudication'],''])
(private/'RESULT.md').write_text('\n'.join(md),encoding='utf-8')
before=registry.read_bytes()
(private/'requirements-before-adjudication.jsonl').write_bytes(before)
requirements=list(map(json.loads,before.decode('utf-8-sig').splitlines()))
now=datetime.now(timezone.utc).isoformat()
for row in requirements:
    if row['case_id'] in notes:
        evidence={'campaign':'astra-survey-readonly541','source_commit':'120713be877aaf426820174ece35a642923f5eda',
                  'private_adjudication':str(private/'adjudication.json'),
                  'ordinals':[r['ordinal'] for r in results if r['case_id']==row['case_id']],
                  'ui_or_voice_credit':False,'partial_campaign':True}
        row['verification_evidence'].append(evidence)
        row['verification_reason']=notes[row['case_id']]
        row['verification_updated_at']=now
    if row['case_id'] in covered:
        assert all(r['terminal'] is not None for r in results if r['case_id']==row['case_id'])
        row['verification_status']='covered'
        row['generalization_status']='verified_product_variants'
registry.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in requirements),encoding='utf-8')
counts=Counter(r['verification_status'] for r in requirements)
assert counts=={'covered':3,'open':739} and len(requirements)==742
summary_path=base/'SURVEY_REQUIREMENTS336.json'
summary=json.loads(summary_path.read_text(encoding='utf-8'))
summary.update(requirements_sha256=sha(registry),validated_current=3,
               verification_counts={'covered':3,'open':739,'not_applicable':0},updated_at=now)
write(summary_path,summary)
resources=json.loads((out/'resources.json').read_text(encoding='utf-8'))
report={'planned':44,'published':25,'unrun':19,'covered_case_ids':sorted(covered),
        'survey_counts':summary['verification_counts'],'resources':resources,
        'private_report':str(private/'RESULT.md'),'private_report_sha256':sha(private/'RESULT.md'),
        'adjudication_sha256':sha(private/'adjudication.json'),
        'known_failures':{k:v for k,v in notes.items() if k not in covered},
        'limitation':'No global acceptance, UI/audio credit or automatic coverage of related messages. Completed evidence retained despite resource-aborted campaign; unrun cases never counted.'}
write(out/'RESULT.json',report)
(out/'RESULT.md').write_text('\n'.join([
 '# Encuesta541 — primera cobertura individual con producto real','',
 '3cubiertos/739abiertos/0no aplicables. Se cubrenH0002(capitales),H0016(biografías) yH0021(identidad BAXY), con el literal revisado y variantes ES/EN que cambian referentes. No se extiende el crédito automáticamente a otros mensajes.','',
 'Se publicaron25finales de44previstos. El guard detuvo sólo el árbol diagnóstico al quedar menos de768MiB libres en el PC.19turnos no ejecutados; exit1 conservado. GPU3499,559MiB/RAM2430,715MiB/96,985s; sin UI/voz, no presupuesto conjunto certificado.','',
 'Bloqueos observados: afirmaciones gratuitas en curiosidades; núcleos lógicos tratados como físicos en español; consulta española de discos rechazada; VRAM dedicada confundida en la prosa; consulta inglesa de GPU degradada a summary sin adaptadores;95% descrito como batería ya cargada.','',
 'El registro privado742 se actualizó porcase_id con motivo, evidencia y variantes. Informe privado completo y hashes enRESULT.json. Fuente542 aborda el alcance GPU/RAM; no da por resuelta la narración de VRAM.','']),encoding='utf-8')
print(json.dumps(summary['verification_counts']))
