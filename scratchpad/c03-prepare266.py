"""Freeze the diagnosed boundary and preserve ownership of the manual UI."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-acknowledgement266'
out.mkdir(exist_ok=False)
before = out / 'before'
before.mkdir()
sources = ['src/baxy_mind/effect_intent.py', 'tests/test_effect_intent.py']
hashes = {}
for name in sources:
    path = root / name
    shutil.copy2(path, before/path.name)
    hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
now = datetime.now(timezone.utc).isoformat()
(out/'PREREG.json').write_text(json.dumps({
    'utc': now, 'hypothesis': 'A separated affirmative discourse marker is not a second requested effect. Existing shared request-envelope normalization must preserve the following speech act and be used by authenticated app argument resolution too.',
    'evidence': 'astra-boundaries265/RESULT.json: Si, abre steam has minimum_effects=2 because si is counted as unresolved positive clause; catalogUnavailable is null. No LLM fault at this first transformation.',
    'method': 'Before/after owner boundary tests using literal UI263 regression plus constructed grammatical controls clearly marked synthetic. No inference or actions in the owner264 window. No new prompt, operation, or success prose. Same frozen Core262 three-case replay after source change.',
    'criteria': 'Affirmative marker leaves independently authorized operation and authenticated target intact; bare affirmation, conditions, quoted data, prohibitions, unknown apps, and actual compound constraints retain their boundaries. Existing effect, compound and turn policy suites pass.',
    'sourceBefore': hashes,
    'limitations': 'This repairs the deterministic boundary, not the missing long-phrase retrieval or compositor proof. Actual UI and model regression still required before acceptance.',
    'priorResearch': ['INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md', 'SEGUIMIENTOS.md'],
    'primarySource': 'https://www.rae.es/dpd/s%C3%AD',
}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
checkpoint = base/'CHECKPOINT.md'
shutil.copyfile(checkpoint, base/'HANDOFF.md')
relevo = base/'RELEVO_ACTIVO.json'
data = json.loads(relevo.read_text(encoding='utf-8'))
data.update(confirmedAtUtc=now,
    checkpoint='265: first failure for Si, abre steam is a false compound cardinality (2); catalog-unavailable is null. Owner264 remains open.',
    continuation='266 shared speech-act normalization and bounded owner tests; keep UI264 untouched, defer its new messages per owner. Full acceptance scope remains pending.',
    userOwnedInstance={'pid':84328, 'createTime':1788820609.3516054, 'automaticClose':False,
        'launcher':100540, 'privateLogs':'%LOCALAPPDATA%/BAXY/C03-owner264-private/',
        'instruction':'Keep open. Do not restart, close, or inject agent inputs. New owner messages are for later correction.'})
relevo.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(out)
