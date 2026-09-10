"""Keep the active native investigation recoverable without accepting C03."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
p=argparse.ArgumentParser()
p.add_argument('--tag',required=True)
p.add_argument('--session',type=int)
p.add_argument('--status',choices=['running','completed','failed'],required=True)
a=p.parse_args()
path=base/'RELEVO_ACTIVO.json'
state=json.loads(path.read_text(encoding='utf-8-sig'))
entry=dict(tag=a.tag,sessionId=a.session,status=a.status,
    panel_sha256='a29167820a7a40ca2c43571276d98596ab0e146eb6b82ac699f768b85a035443',
    directory='artifacts/comprobaciones/C03/K2_HORIZON_NATIVE699/run-'+a.tag)
folder=root/entry['directory']
if a.status=='completed':
    for filename,key in [('MEASUREMENTS.json','measurements'),('ADJUDICATION.json','adjudication')]:
        if (folder/filename).exists():
            data=json.loads((folder/filename).read_text(encoding='utf-8'))
            entry[key]={k:v for k,v in data.items() if k in ['passed','failed','cases','responses','seconds','resources','raw_results_sha256']}
state.setdefault('independentNative699',{})[a.tag]=entry
if a.status=='running':
    state['activeValidation']=entry
elif (state.get('activeValidation') or {}).get('tag')==a.tag:
    state['activeValidation']=None
state['confirmedAtUtc']=datetime.now(timezone.utc).isoformat()
state['checkpoint']=f'Referencia independiente699 {a.tag}: {a.status}. Decisión provisional;693/694 pausados;C03 activo;encuesta26/716/0.'
path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with (base/'CHECKPOINT.md').open('a',encoding='utf-8') as f:
    f.write('\n\n## Referencia independiente699 — '+state['confirmedAtUtc']+'\n\n'+state['checkpoint']+'\n')
print(json.dumps(entry))
