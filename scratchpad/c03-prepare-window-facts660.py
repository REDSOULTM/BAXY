"""Pin the candidate and preserve baseline/intermediate contract evidence."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-window-facts-source660'
out.mkdir(exist_ok=False)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
files = {p.relative_to(root).as_posix():p for folder in ['experiments/voice_latency','scripts','src/baxy_mind']
         for p in (root / folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode()+b'\n'+sha(files[name]).encode()+b'\n')
tree = digest.hexdigest()
for name in ['audit_fresh_postweight_stt_sources.py','evaluate_reserved_stt.py']:
    path = root / 'experiments/stt_quality' / name
    data = path.read_bytes()
    old = b'bdcb3f8cbfcaa4f428cbf2329a3cd250c8c97b62c1018ab3594fe6fa9c10cadf'
    assert data.count(old) == 1
    path.write_bytes(data.replace(old,tree.encode()))
path = root / 'tests/test_price_v8_veto_damage_by_cause.py'
data = path.read_bytes()
old = b'e6993ddb155b9586dd178e5814604eb4ec25f7baf853d68a9c855d3d6e41de45'
assert data.count(old) == 1
path.write_bytes(data.replace(old,sha(root / 'src/baxy_mind/llm.py').encode()))
sources = {name:sha(root / name) for name in ['src/baxy_mind/llm.py','src/baxy_mind/window_prose_facts.py','tests/test_c03_window_facts.py']}
record = {'utc':datetime.now(timezone.utc).isoformat(),'source':660,'adopted':False,
    'sources':sources,'python_tree_sha256':tree,'python_files':len(files),
    'inheritance':'649 checked only compose_visible_defect, not the entire publishability predicate. The production compositor also runs _payload_fact_defect. New Recorder tests confirm four bad drafts pass the full old path. Keep both guards at their actual owners; no second model.',
    'research_reused':['astra-native-fact-judge656','astra-nli-fact-probe658','astra-nli-native-parity659'],
    'design':'Extend the existing fact contract with field-qualified installation/cardinality/process assertions. Reuse ES/EN cardinal vocabulary; preserve ranges, names, uncertainty and other operations. A complete window answer may mention an unknown process state without becoming a failed window read. An unknown process statement alone still cannot answer the window question.',
    'test_refinement':'The initial publication test offered only process uncertainty as a response to Is Orbit23 open. It was refined to include a real window answer, and a separate regression now requires rejecting uncertainty alone. Initial46fail/32pass log is retained, not treated as the baseline for the final104-case cohort. Same final tests run against published654 bytes in an isolated module.',
    'focal_final':{'passed':104,'seconds':.68},
    'next':'Owner suites, current declarations, Fast, exact24-case product655 regression661. Prose foreground defect remains separate; do not award global C03 closure from field tests.'}
(out / 'PREREG.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
temp = Path(os.environ['TEMP'])
logs = {'c03-window-facts660-baseline.log':'INITIAL_BASELINE.log',
        'c03-window-facts660-baseline-unknown.log':'INITIAL_UNKNOWN.log',
        'c03-window-facts660-focal.log':'INITIAL_FOCAL.log',
        'c03-window-facts660-expanded-red.log':'EXPANDED_RED.log',
        'c03-window-facts660-expanded.log':'EXPANDED_INTERMEDIATE.log',
        'c03-window-facts660-final-focal.log':'FOCAL.log',
        'c03-window-facts660-same-cohort-baseline.log':'BASELINE.log'}
for original,dest in logs.items():
    (out / dest).write_bytes((temp / original).read_bytes())
with (root / '.gitattributes').open('a',encoding='utf-8',newline='\n') as f:
    f.write('/artifacts/comprobaciones/C03/astra-window-facts-source660/** -text\n')
note = ('\n\n## Candidata660 — conservación de hechos en el compositor completo\n\n'
        '104 controles finales pasan: cantidades/rangos,nombres,instalación,procesos desconocidos y reintento real del compositor con transporte simulado. La comprobación649 era parcial; esta baseline verifica además la frontera completa de publicación. Se conserva la prueba inicial y su refinamiento explícito sobre respuesta incompleta. No LLM/kernel/UI en tests. '
        'Sin modelo ni llamada adicional. Fuente660 aún NOadoptada; faltan dueñas/declaraciones/Fast y producto661. Contrato delimitado, no prueba universal. Fuente654 publicada; encuesta26/716/0.\n')
with (base / 'CHECKPOINT.md').open('a',encoding='utf-8',newline='\n') as f:
    f.write(note)
print(record)
