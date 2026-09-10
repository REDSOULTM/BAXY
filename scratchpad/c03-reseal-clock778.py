"""Retain candidate1 evidence and seal modal/infinitive coverage before rerun."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'CLOCK_SCOPE778'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not (OUT / 'CANDIDATE2.json').exists()
sys.path.insert(0, str(ROOT))
from scripts.wake_validation_program_tree import fingerprint_program_tree
prior = read(OUT / 'PROGRAM.json')
program = fingerprint_program_tree(repository_root=ROOT, source_roots=[ROOT / p for p in prior['roots']])
assert program['pythonFiles'] == 407
for name in ['experiments/stt_quality/evaluate_reserved_stt.py',
             'experiments/stt_quality/audit_fresh_postweight_stt_sources.py']:
    path = ROOT / name
    source = path.read_text(encoding='utf-8')
    assert source.count(prior['sha256']) == 1
    path.write_bytes(source.replace(prior['sha256'], program['sha256']).encode('utf-8'))
pins = read(OUT / 'SOURCE_PINS.json')
write(OUT / 'SOURCE_PINS.json', {p: sha(ROOT / p) for p in pins})
write(OUT / 'PROGRAM.json', program)
logs = {}
for name in ['candidate1-final', 'candidate1-fast', 'modal-baseline', 'modal-fixed']:
    raw = (Path(os.environ['TEMP']) / f'c03-clock778-{name}.log').read_bytes()
    normalized = '\n'.join(line.rstrip() for line in raw.decode('utf-8-sig').splitlines()) + '\n'
    target = OUT / (name + '.log')
    target.write_bytes(normalized.encode('utf-8'))
    logs[name] = {'original_sha256': hashlib.sha256(raw).hexdigest(), 'public_sha256': sha(target)}
write(OUT / 'CANDIDATE2.json', {'utc': datetime.now(timezone.utc).isoformat(),
    'cause': 'Preflight779 found only variant08 unresolved. Wrapper correctly returns pasarme la hora; imperative-only head lacked the infinitive plus clitic.',
    'change': 'Spanish observation heads share imperative/infinitive forms including attached me; same whole-request reader and clause-boundary head.',
    'candidate1_validation': '2274pass/1environmental STT skip,63.15s; Fast0/Release21.48s,session75716 collected.',
    'candidate1_sources_private': str(Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-clock-scope778-private'),
    'modal_baseline': '24fail/80pass,0.94s', 'modal_repaired': '24pass/80deselected,0.63s',
    'new_total_controls': 104, 'logs': logs, 'pending': 'Repeat owners/current integrity/Fast on final pins, then same50 product779; no trial started or panel changed.'})
note = ('778 candidato2: preflight77949/50 reconocidos detectó pasarme; envoltorio correcto, infinitivo con clítico ausente. '
        'Familia morfológica compartida corregida24pass;104controles totales. Candidato1 conservado2274pass/1skipSTT/Fast0. '
        'Pendientes finales/integridad/Fast y mismo panel779sin modificar.26/716/0.\n\n')
cp = BASE / 'CHECKPOINT.md'
pending = cp.with_suffix('.pending.md')
pending.write_bytes(note.encode('utf-8') + cp.read_bytes())
pending.replace(cp)
state = read(BASE / 'RELEVO_ACTIVO.json')
state.update(checkpoint=note.strip(), workStatus='clock_scope778_candidate2_validation_pending')
write(BASE / 'RELEVO_ACTIVO.json', state)
print(json.dumps({'program': program['sha256'], 'pins': len(pins)}))
