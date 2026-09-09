"""Adjudicate real connection observations after the published569 repair."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
import os
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
private = local / 'C03-network-product570-private'
out = base / 'astra-network-product570'

def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

panel = read(private / 'panel.json')
events = [json.loads(s) for s in (private / 'capture/events.jsonl').read_text(encoding='utf-8-sig').splitlines()]
finals = [r for r in events if r.get('type') == 'terminal']
assert len(finals) == len(panel) == 8 and read(out / 'EXIT.json')['exitCode'] == 0
assert not read(out / 'resources.json')['violations']
posts = [json.loads(s) for s in (private / 'http-posts.jsonl').read_text(encoding='utf-8-sig').splitlines()]
assert not any('"operation": "web.search"' in str(r.get('payload', {})) for r in posts)
note = 'Literal y seis variantes cambian idioma, sujeto, nombre del equipo, forma interrogativa/imperativa y coordinación con la hora. Nativos3–8 conservan network.status y online:true; native10 contiene pasos ordenados network.status y system.time con02:37. Todos los finales coinciden. Sin búsqueda web ni lectura Wi-Fi sustitutiva. Son observaciones actuales, no un ensayo de desconexión física.'
adjudication = [{**case, 'ordinal': i + 1, 'terminal': finals[i], 'adjudication': note if case['case_id'] == 'H0080' else 'Control previo de volumen100/no silenciado correcto; mantiene instrucción contradictoria sobre muted ya localizada. No nuevo crédito.'} for i, case in enumerate(panel)]
write(private / 'adjudication.json', adjudication)
lines = ['# Producto570 — conectividad', '']
for row in adjudication:
    lines += [f'## {row["ordinal"]} · {row["case_id"]}', '', row['text'], '', row['terminal']['final'], '', row['adjudication'], '']
(private / 'RESULT.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
registry = local / 'C03-survey-requirements336-private/requirements.jsonl'
backup = private / 'requirements-before-adjudication.jsonl'
assert not backup.exists()
backup.write_bytes(registry.read_bytes())
rows = [json.loads(s) for s in backup.read_text(encoding='utf-8-sig').splitlines()]
row = next(r for r in rows if r['case_id'] == 'H0080')
assert row['verification_status'] == 'open'
commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
assert commit.startswith('a9f053b7')
row.update(verification_status='covered', generalization_status='verified_product_variants', verification_reason=note, verification_updated_at=datetime.now(timezone.utc).isoformat())
row['verification_evidence'].append({'campaign': 'astra-network-product570', 'source_commit': commit, 'private_adjudication': str(private / 'adjudication.json'), 'ordinals': list(range(1, 8)), 'ui_or_voice_credit': False})
assert Counter(r['verification_status'] for r in rows) == {'covered': 12, 'open': 730}
registry.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8', newline='\n')
counts = {'covered': 12, 'open': 730, 'not_applicable': 0}
summary = read(base / 'SURVEY_REQUIREMENTS336.json')
summary.update(requirements_sha256=sha(registry), validated_current=12, verification_counts=counts, updated_at=datetime.now(timezone.utc).isoformat())
write(base / 'SURVEY_REQUIREMENTS336.json', summary)
write(out / 'RESULT.json', {'published': 8, 'newly_covered': ['H0080'], 'survey_counts': counts, 'resources': read(out / 'resources.json'), 'private_report_sha256': sha(private / 'RESULT.md'), 'adjudication_sha256': sha(private / 'adjudication.json'), 'source_commit': commit, 'limits': 'Sin UI/voz ni prueba de red física desconectada.'})
public = '# Producto570 — red local verificada\n\n' + note + '\n\n8 finales, exit0, sin cortes. GPU3497,559MiB/RAM1840,793MiB,24,188s. Fuente569 publicada' + commit + '. Encuesta12 cubiertos/730 abiertos/0 no aplicables; nuevoH0080. SinUI/voz.\n'
(out / 'RESULT.md').write_text(public, encoding='utf-8', newline='\n')
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
with (root / '.gitattributes').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('/artifacts/comprobaciones/C03/astra-network-product570/** -text\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n' + public)
state = read(base / 'RELEVO_ACTIVO.json')
state.update(checkpoint='570: network repair verified; survey12/730/0. Audio observation fix571 in validation.', surveyVerificationCounts=counts, publishedSourceCommit=commit, continuation='Finish source571 owners/Fast, verify nested audio composition in product572, publish. Final C03 obligations remain open.')
write(base / 'RELEVO_ACTIVO.json', state)
print(json.dumps(counts))
