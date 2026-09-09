"""Pin the contextual-read candidate before integrated measurement."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'; out = base/'astra-context-source646'
out.mkdir(exist_ok=False)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, v): p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
files = {p.relative_to(root).as_posix(): p for folder in ['experiments/voice_latency', 'scripts', 'src/baxy_mind'] for p in (root/folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for relative in sorted(files): digest.update(relative.encode()+b'\n'+sha(files[relative]).encode()+b'\n')
tree = digest.hexdigest()
for name in ['audit_fresh_postweight_stt_sources.py', 'evaluate_reserved_stt.py']:
    p = root/'experiments/stt_quality'/name; data = p.read_bytes()
    old = b'6e00cb73fdc65e3bbf9b02d2e77f8db8f4e21702d01590edd4359f28e9418394'
    assert data.count(old) == 1
    p.write_bytes(data.replace(old, tree.encode()))
p = root/'tests/test_price_v8_veto_damage_by_cause.py'; data = p.read_bytes()
old = b'3c66e6cbe15ae091590393946e1c5f1ad056c89869a2c6bb345de616f760b9c6'
assert data.count(old) == 1
p.write_bytes(data.replace(old, sha(root/'src/baxy_mind/__main__.py').encode()))
paths = ['src/baxy_mind/effect_intent.py', 'src/baxy_mind/__main__.py',
    'src/Baxy.App/MainWindowViewModel.cs', 'src/Baxy.App/MindSidecarClient.cs',
    'tests/test_window_query_context.py']
write(out/'PREREG.json', {'utc': datetime.now(timezone.utc).isoformat(), 'source': 646,
    'sources': {p: sha(root/p) for p in paths}, 'python_tree_sha256': tree,
    'method': 'Resolve bounded named/pronominal read follow-ups from user questions only; retain original request. A changed, ambiguous or unresolved subject ends the chain. Same function owns selection and exact-schema grounding. Pass the existing shell history to argument extraction, without a second state store or new model.',
    'inheritance': '643 rejected global history concatenation;644/645 isolated missing candidate and stale-state recital. arguments messages omitted history despite contextual selection; bounded parser replaces that missing interpretation for explicit window-read references.',
    'criteria': 'Exact20panel642 again; all contextual reads must execute window.application.status with correct name and fresh state. No writes. Preserve negative/missing-value and explicit reads. Owners, Fast and Full required before combined Python/C# adoption. Broader names/topic shifts and voice/UI remain separate evidence.',
    'test_first': {'failed': 46}, 'targeted_passed': 50, 'model_and_profile_unchanged': True})
for suffix, target in [('red', 'RED.log'), ('targeted', 'TARGETED.log'), ('owners', 'OWNERS.log')]:
    (out/target).write_bytes((Path(os.environ['TEMP'])/f'c03-context646-{suffix}.log').read_bytes())
state = json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='646 candidato de lectura contextual y transporte de historial a argumentos;50 focales verdes. Falta Fast/producto647/Full antes de adopción conjunta.25/717/0.',
    continuation='Recoger validaciones646 y repetir20panel642 mediante647. Verificar referencias con nombre exacto y observación nueva. Full obligatorio para adoptar C#+Python. Sin nuevo modelo, prosa fija o estado paralelo.',
    previousGoalTurnClassification='progress', pendingOwnerClarification=None)
write(base/'RELEVO_ACTIVO.json', state)
with (base/'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as f:
    f.write('\n\n## Candidato 646 — continuidad de consulta y argumentos\n\n46 rojos iniciales; 50 focales verdes tras resolver referencias de preguntas del usuario. Se pasa el historial existente a argumentos; identidad y esquema se verifican otra vez. No se transforma el texto original ni se revive una orden previa. Falta producto647 y Full para adoptar Python+C#. Encuesta25/717/0.\n')
print({'source': 646, 'tree': tree, 'main_sha256': sha(root/'src/baxy_mind/__main__.py')})
