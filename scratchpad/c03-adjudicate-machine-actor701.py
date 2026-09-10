"""Seal all synthetic701 outputs; this population demonstrates no repair gain."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
home=Path(os.environ['LOCALAPPDATA'])/'BAXY'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
rows=lambda p:[json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()]
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
failures={case:'Wi-Fi connectivity is expanded to the whole PC being online/offline; only WLAN was observed.'
          for case in ['wifi.status-0-6','wifi.status-0-8','wifi.status-1-2','wifi.status-1-6','wifi.status-1-8']}
failures['network.status-1-6']='Says no interface is connected despite the observed active interface; contradicts its own online claim.'
loaded={}
for arm in ['baseline','candidate']:
    private=home/f'C03-machine-actor701-{arm}-private'
    loaded[arm]={name:rows(private/name) for name in ['finals.jsonl','requests.jsonl','responses.jsonl']}
assert loaded['baseline']['requests.jsonl']==loaded['candidate']['requests.jsonl']
assert len(loaded['baseline']['requests.jsonl'])==51
for a,b in zip(loaded['baseline']['finals.jsonl'],loaded['candidate']['finals.jsonl'],strict=True):
    assert all(a[k]==b[k] for k in ['case_id','final','calls'])
for arm in ['baseline','candidate']:
    out=base/f'astra-machine-actor701-{arm}'
    assert not (out/'RESULT.json').exists()
    private=home/f'C03-machine-actor701-{arm}-private'
    panel=read(private/'panel.json')
    finals=loaded[arm]['finals.jsonl']
    assert len(panel)==len(finals)==50
    resources=read(out/'RESOURCES.json')
    assert resources['complete'] and resources['manifest_unchanged'] and not resources['violations']
    adjudication=[]
    report=['# 701 — cincuenta controles de red, Wi-Fi y CPU',
            'Todos los primeros borradores y reintentos son generaciones del modelo local. Los dos brazos conservan exactamente51peticiones y50finales.40turnos de red/WLAN no necesitaron reparación: esta población acredita regresión conservada, no mejora del actor. La revisión raíz y la revisión independiente coinciden en44correctos y6fallos de alcance/contradicción. No acredita encuesta, UI ni voz.']
    for case,final in zip(panel,finals,strict=True):
        assert case['case_id']==final['case_id']
        reason=failures.get(case['case_id'], 'Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.')
        verdict='failed' if case['case_id'] in failures else 'correct'
        adjudication.append({**case,**final,'verdict':verdict,'reason':reason})
        report += ['## '+case['case_id'], 'Petición: '+case['text'], 'Respuesta: '+final['final'],
                   verdict+': '+reason, 'Hechos: '+json.dumps(case['expected'],ensure_ascii=False)]
    counts=dict(Counter(r['verdict'] for r in adjudication))
    assert counts=={'correct':44,'failed':6}
    write(private/'adjudication.json',adjudication)
    (out/'RESPUESTAS.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
    write(out/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'arm':arm,'cases':50,
          'counts':counts,'all51_requests_identical':True,'all50_finals_identical':True,
          'wlan_network_repair_calls':0,'source_adopted':False,'survey_coverage_added':0,
          'resources':resources,'failures':failures,
          'private_hashes':{name:sha(private/name) for name in ['panel.json','finals.jsonl','requests.jsonl','responses.jsonl','adjudication.json']}})
    write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
print({'per_arm':{'correct':44,'failed':6},'identical_requests':51,'identical_finals':50,'repair_gain_not_demonstrated':True})
