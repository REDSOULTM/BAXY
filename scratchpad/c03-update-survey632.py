"""Link the audited window failure without changing coverage or owner answers."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
p=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-survey-requirements336-private/requirements.jsonl'
before=p.read_bytes();assert hashlib.sha256(before).hexdigest()=='1ee9583ffc2255819fbf90f5faa40227950a04005965bb3fa9862921aff0f0f8'
lines=before.splitlines(keepends=True);changes=0;now=datetime.now(timezone.utc).isoformat()
for i,line in enumerate(lines):
 row=json.loads(line)
 if row['case_id']!='H0040':continue
 assert row['verification_status']=='open' and 'verification_reason_before632' not in row
 row['verification_reason_before632']=row['verification_reason']
 row['verification_reason']='632:541/85 observa sólo window.active y no prueba ausencia de otras ventanas;541/89 responde knowledge sin observación. Ambas negaciones incumplen verificación. El lector actual repite el alcance erróneo en español; el producto inglés actual aún necesita prueba. Abierto, sin crédito por plausibilidad.'
 row['verification_evidence'].append({'campaign':'astra-window-evidence632','method':'read-only adjudication of541 plus current Python scope probe; no current English inference',
  'private_evidence':str(p.parent.parent/'C03-window-evidence632-private/evidence.json'),
  'public_result_sha256':hashlib.sha256((base/'astra-window-evidence632/RESULT.json').read_bytes()).hexdigest(),'ui_or_voice_credit':False})
 row['verification_updated_at']=now
 lines[i]=(json.dumps(row,ensure_ascii=False)+'\n').encode('utf-8');changes+=1
assert changes==1
after=b''.join(lines);p.write_bytes(after)
public=base/'SURVEY_REQUIREMENTS336.json';summary=json.loads(public.read_text(encoding='utf-8'))
summary['requirements_sha256']=hashlib.sha256(after).hexdigest();summary['updated_at']=now
public.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print({'changed_cases':['H0040'],'coverage_unchanged':summary['verification_counts'],'requirements_sha256':summary['requirements_sha256']})
