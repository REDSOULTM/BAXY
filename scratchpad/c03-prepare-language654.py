"""Pin language-reader candidate after baseline, before integrated validation."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-language-source654'
out.mkdir(exist_ok=False)
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
files = {p.relative_to(root).as_posix(): p for folder in ['experiments/voice_latency', 'scripts', 'src/baxy_mind']
         for p in (root / folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode()+b'\n'+sha(files[name]).encode()+b'\n')
tree = digest.hexdigest()
for name in ['audit_fresh_postweight_stt_sources.py', 'evaluate_reserved_stt.py']:
    path = root / 'experiments/stt_quality' / name
    data = path.read_bytes()
    old = b'd6516137ea188c291331c12e7a52a2d23fbbd5835770efedb56342ef34b8d7ea'
    assert data.count(old) == 1
    path.write_bytes(data.replace(old, tree.encode()))
record = {'utc': datetime.now(timezone.utc).isoformat(), 'source': 654,
          'reader_sha256': sha(root / 'src/baxy_mind/request_reading.py'),
          'python_tree_sha256': tree, 'llm_unchanged_sha256': sha(root / 'src/baxy_mind/llm.py'),
          'baseline': {'failed': 13, 'passed': 27, 'deselected': 260, 'seconds': .76},
          'focal': {'passed': 300, 'seconds': .82}, 'adopted': False,
          'plan': 'Owner suites, current-source declaration checks and Fast; exact20 product regression plus4 foreground language variants. Adjudicate every output before adoption; do not modify source during run.',
          'inheritance': ['astra-window-scope-product653', 'astra-language397', 'astra-decision-language377',
             'biblioteca/gemma4-agent/dataset-finetune/out/_commit_msg2.txt'],
          'research': [
             {'url': 'https://www.rae.es/buen-uso-espa%C3%B1ol/conjugaci%C3%B3n-espa%C3%B1ola',
              'finding': 'has is a Spanish auxiliary as well as an English form; surrounding lexical evidence is necessary.'},
             {'url': 'https://github.com/pemistahl/lingua-py',
              'finding': 'Statistical local alternative for short/mixed text. No new inference benchmark or quality ranking claimed here. Existing reader already carries one language decision; first test correcting its ambiguous word and missing common participles without an additional detector.'}],
          'research_date': '2026-09-09', 'scope': 'Neutral has; existing word tables gain common Spanish open/closed/saved/written/finished forms. No morphological suffix guesses that would count the name Colorado; no app names, new model or fixed prose. Finite word coverage is not universal language identification.'}
(out / 'PREREG.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
import os
for original, dest in [('c03-language654-baseline.log', 'BASELINE.log'), ('c03-language654-focal.log', 'FOCAL.log')]:
    (out / dest).write_bytes((Path(os.environ['TEMP']) / original).read_bytes())
with (root / '.gitattributes').open('a', encoding='utf-8', newline='\n') as f:
    f.write('/artifacts/comprobaciones/C03/astra-language-source654/** -text\n')
with (root / 'artifacts/comprobaciones/C03/CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as f:
    f.write('\n\n## Candidata654 — idioma del auxiliar compartido\n\nBaseline13 fallos/27 pases en40 controles ES/EN/mezcla con historia previa cruzada. Se neutraliza has y se completan participios frecuentes en la tabla existente; ningún nombre de aplicación ni regla por sufijo. Dueña300 pases. Pendientes dueñas integradas, declaraciones, Fast y producto655 de24casos. No adoptada aún. Modelo intacto; encuesta26/716/0.\n')
print(record)
