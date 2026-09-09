"""Record the missing-level repair before integrated product verification."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-clarification-source628'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, v): p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
assert not (out/'PREREG.json').exists()
files = {p.relative_to(root).as_posix():p for folder in ['experiments/voice_latency','scripts','src/baxy_mind'] for p in (root/folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for relative in sorted(files): digest.update(relative.encode()+b'\n'+sha(files[relative]).encode()+b'\n')
tree_sha = digest.hexdigest()
for name in ['audit_fresh_postweight_stt_sources.py','evaluate_reserved_stt.py']:
    p = root/'experiments/stt_quality'/name
    data = p.read_bytes(); old = b'47de59d8e395e11d7ada744fb459bb10a12f9458173db971236009f9abfd1d0a'
    assert data.count(old)==1
    p.write_bytes(data.replace(old,tree_sha.encode()))
for src, dest in [('c03-clarification628-red.log','RED.log'),('c03-clarification628-targeted.log','TARGETED.log')]:
    (out/dest).write_bytes((Path(os.environ['TEMP'])/src).read_bytes())
write(out/'PREREG.json', {'utc':datetime.now(timezone.utc).isoformat(), 'source':628,
    'effect_intent_sha256':sha(root/'src/baxy_mind/effect_intent.py'),
    'python_tree_sha256':tree_sha,'python_files':len(files),
    'test_first':{'failed':14,'passed':41},'targeted':{'passed':55},
    'method':'Existing full-clause missing-level recognizer accepts an unfilled value preposition. No fixed prosa, inferred level, operation promotion, semantic-guard change or model/profile change.',
    'criteria':'Owner suites and Fast green, same12 product608 controls plus8 incomplete-value variants in product629. No new failures or effects; retain all old defects, no UI/voice claim.'})
state=json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='628 candidato: lector de volumen conserva nivel ausente tras a/al/en/to/at.14rojos previos→55pass focales. Dueñas/Fast/producto629 pendientes;25/717/0.',
    continuation='Completar dueñas628 y Fast antes de lanzar629. Adjudicar20finales y ausencia de efectos. No adopción ni cierre hasta evidencia; fuente publicada626 sigue vigente.')
write(base/'RELEVO_ACTIVO.json',state)
with (base/'CHECKPOINT.md').open('a',encoding='utf-8',newline='\n') as stream:
    stream.write('\n\n## Candidato628 — aclaración de nivel ausente\n\n608 pierde la orden de volumen al terminar en una preposición sin valor. Se extiende el reconocedor completo existente;14fallos nuevos antes,55pass después. Mantiene valor presente, catálogo, negación, dispositivo y compuestos. Sólo Python; no cambio de prosa/modelo. Dueñas/Fast/producto629 pendientes. Encuesta25/717/0. No decisión pendiente del dueño.\n')
print({'source':628,'tree_sha256':tree_sha,'files':len(files)})
