"""Pin the typed-name correction and retain the unsuccessful baseline evidence."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-window-vocabulary-source705'
out.mkdir(exist_ok=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
write = lambda p, value: p.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
files = {p.relative_to(root).as_posix(): p for folder in ['experiments/voice_latency', 'scripts', 'src/baxy_mind']
         for p in (root/folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode()+b'\n'+sha(files[name]).encode()+b'\n')
tree = digest.hexdigest()
old = json.loads((base/'astra-machine-actor-source702/RESULT.json').read_text(encoding='utf-8'))
paths = ['src/Baxy.App/ObservedResponseLiterals.cs', 'src/Baxy.App/UserMessagePolicy.cs',
         'src/baxy_mind/observed_response_literals.py', 'src/baxy_mind/llm.py',
         'tests/Baxy.Integration.Tests/ObservedWindowVocabularyTests.cs',
         'tests/test_c03_observed_window_vocabulary.py']
for name in ['audit_fresh_postweight_stt_sources.py', 'evaluate_reserved_stt.py']:
    path = root/'experiments/stt_quality'/name
    data = path.read_bytes()
    assert data.count(old['python_tree_sha256'].encode()) == 1
    path.write_bytes(data.replace(old['python_tree_sha256'].encode(), tree.encode()))
    paths.append(path.relative_to(root).as_posix())
path = root/'tests/test_price_v8_veto_damage_by_cause.py'
data = path.read_bytes()
assert data.count(old['sources']['src/baxy_mind/llm.py'].encode()) == 1
path.write_bytes(data.replace(old['sources']['src/baxy_mind/llm.py'].encode(), sha(root/'src/baxy_mind/llm.py').encode()))
paths.append(path.relative_to(root).as_posix())
for name in ['python-baseline', 'python-baseline2', 'python-failure', 'negative-baseline',
             'dotnet-baseline', 'python-focal', 'dotnet-focal']:
    (out/(name.upper()+'.log')).write_bytes((Path(os.environ['TEMP'])/('c03-window-vocabulary705-'+name+'.log')).read_bytes())
record = {
    'utc': datetime.now(timezone.utc).isoformat(), 'adopted': False,
    'parent_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'sources': {name: sha(root/name) for name in paths}, 'python_tree_sha256': tree, 'python_files': len(files),
    'design': 'Treat complete names from verified, succeeded window operation observations as opaque only during vocabulary/code-shape checks. Mission steps retain their own envelopes. Do not derive exemptions from requested targets, root title/reason, merged data or dialogue. Original prose remains unchanged for factual checks, recovery and publication. The public length cap applies before masking. No model, prompt, sampler, retry-count, risk or catalog changes.',
    'inheritance': ['OperationVisibleFacts.FromOutcome verified/succeeded envelope and sanitized observed payload',
                    'window_prose_facts quoted/subject identity opacity',
                    'existing user-identifier vocabulary exceptions in C# and Python',
                    'source703 and fully reviewed product704 remain baseline',
                    'product694 H0104 first draft correct but rejected forbidden_term; source705 does not repair the separate postposed ventanal grammar'],
    'baseline': {'python_passed': 6, 'python_failed': 43, 'dotnet_passed': 11, 'dotnet_failed': 7,
                 'fixture_correction': 'Initial Python run49fail: six negative fixtures expected ValueError, while the existing composer returns empty after three rejected drafts. Only that fixture expectation was corrected before the authoritative baseline43fail/6pass; source was unchanged. Original logs retained.'},
    'initial_focal': {'python_passed': 373, 'dotnet_passed': 113, 'skipped': 0,
                      'limit': 'Before adding unquoted names, complete-token boundaries, unrelated self-description and public-length controls.'},
    'validation_next': 'Expanded owners, then Full because adoption touches C# and Python together. Replay actual historical draft privately and run a complete product panel only after code validation. Tests replaying drafts are technical veto controls, not fresh user acceptance or evidence of model generation.',
    'survey_counts': {'covered': 26, 'open': 716, 'not_applicable': 0},
    'goal_complete': False, 'new_coverage': 0,
}
write(out/'PREREG.json', record)
state = json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
state.update(confirmedAtUtc=record['utc'], workStatus='window_vocabulary705_owners_running',
             checkpoint='705 candidato compartido: nombres de ventanas observados exentos sólo dentro del literal para vocabulario; hechos y prosa intactos.373focalesPython/113App verdes; dueñas ampliadas en curso. No adoptado;26/716/0.',
             continuation='Recoger97801 Python y26335.NET; logsTEMP/c03-window-vocabulary705-*-owners.log. EjecutarFull705 tras dueñas verdes por cambio conjunto. Fuente y declaracionesSTT selladas en PREREG. Sin inferencia/producto nuevo aún.',
             previousGoalTurnClassification='no_progress',
             previousGoalTurnClassificationReason='El turno anterior aclaró y auditó metodología ya publicada; no cambió producto ni próxima acción. Ahora705 implementa el bloqueo disponible.',
             activeValidation={'name': 'window_vocabulary705_owners', 'pythonSessionId': 97801, 'dotnetSessionId': 26335})
write(base/'RELEVO_ACTIVO.json', state)
with (base/'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n## Candidato705 — nombres observados frente a vocabulario interno\n\nSe implementa una exención limitada al segmento exacto de títulos/procesos de ventanas con operación, succeeded y verified verdaderos. No altera la respuesta ni las comprobaciones fácticas. Los pasos de misión conservan su propio sobre; títulos de raíz, diálogos y observaciones sin verificar no autorizan vocabulario. Baseline43fallos/6passPython y7fallos/11passApp; focal373Python/113App verdes,0skips. Se corrigió antes del baseline la expectativa de6fixtures negativas: agotamiento devuelve vacío, noValueError; logs originales conservados. Dueñas ampliadas en97801/26335; Full requerido antes de adopción conjunta. Encuesta26/716/0; no nueva cobertura ni inferencia.\n')
print({'candidate705': True, 'python_tree': tree, 'files': len(files), 'adopted': False})
