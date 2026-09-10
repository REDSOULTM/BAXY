"""Seal the completed model investigation without closing or adopting C03 source."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import py_compile
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'K2_HORIZON_SELECTOR700'
def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
assert subprocess.check_output(['git','branch','--show-current'],cwd=root,text=True).strip() == 'Goal-c03'
native = read(base / 'K2_HORIZON_NATIVE699/SUMMARY699.json')
paired = read(out / 'SUMMARY700.json')
assert native['outputs'] == 300 and len(native['effort_only_payload_parity']) == 50
assert [r['adjudication']['passed'] for r in native['profiles']] == [33,40,39,40,28,38]
assert [(r['grade']['before_passed'],r['grade']['passed']) for r in paired['records']] == [(7,5),(10,8)]
for r in native['profiles']:
    folder = base / 'K2_HORIZON_NATIVE699' / ('run-' + r['tag'])
    assert read(folder / 'ADJUDICATION.json') == r['adjudication']
    assert read(folder / 'MEASUREMENTS.json') == r['measurements']
    assert read(folder / 'RESPONSE_TIMING.json') == r['timing']
for r in paired['records']:
    folder = out / ('run-' + r['grade']['tag'])
    assert read(folder / 'ADJUDICATION.json') == r['grade']
    assert read(folder / 'MEASUREMENTS.json') == r['measurements']
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
assert sha(manifest) == '13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'

script_names = subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','--','scratchpad'],cwd=root,text=True).splitlines()
scripts = sorted(set(n for n in script_names if n.endswith('.py') and ('k2' in n.lower() or '699' in n or '700' in n)))
for name in scripts:
    py_compile.compile(str(root/name),doraise=True)
method = read(base / 'K2_HORIZON_NATIVE699/METHOD_VALIDATION.json')
assert method['public_pins_verified'] == 211 and method['old_measurements_unchanged']
validation = dict(utc=datetime.now(timezone.utc).isoformat(), independent_outputs=300,
    paired_new_outputs=40, manually_reviewed_new_outputs=340,
    effort_only_payload_pairs=50, removed_system_payload_pairs=40,
    diagnostic_python_scripts_compiled=len(scripts), powershell_syntax_errors=0,
    historical_public_pins_verified=211, manifest_unchanged=True,
    source_full='No new product source adopted. Prior source693 Full is separate:11051 Python pass/3 environmental skips/466 subtests;4480.NET pass/1 aggregate skip. Not a C03 closing Full.',
    backend_tests='Previously sealed698:121 auto-parser tests/4539 assertions,39 PEG tests/210 assertions;0 failures/exceptions/skips.',
    scope='Evidence validation; not all model answers pass, no survey credit, no product acceptance.')
assert read(base / 'K2_HORIZON_NATIVE699/POWERSHELL_VALIDATION.json')['errors'] == 0
(out/'EVIDENCE_VALIDATION700.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
closure = dict(utc=validation['utc'], investigation_status='completed', goal_status='EN_CURSO',
    goal_completed=False, decision='retain_registered_qwen_as_working_candidate', model_promoted=False,
    original_outputs=300, paired_new_outputs=40, previous_conditioned_outputs=860,
    rationale='K2 has gains and regressions, but no joint advantage in Spanish quality, latency and memory. Removing the selected BAXY policy has mixed effects and reduces both totals. Native/local profile results are not universal original-weight judgments.',
    report='artifacts/comprobaciones/C03/K2_HORIZON_SELECTOR700/INFORME_PARA_DUENO.md',
    next_action='Resume full payload adjudication of product694, then adopt or repair source693 only if evidence supports it; continue C03 blockers.',
    survey={'covered':26,'open':716,'not_applicable':0},
    runtime_manifest_sha256=sha(manifest))
(out/'CLOSURE700.json').write_text(json.dumps(closure,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
state_path=base/'RELEVO_ACTIVO.json'
state=read(state_path)
assert state['surveyVerificationCounts']==closure['survey']
state['activeValidation']=None
state['k2Comparison'].update(investigationCompleted=True,decision=closure['decision'],promotion=False,
    ownerDecisionPending=False,closure='artifacts/comprobaciones/C03/K2_HORIZON_SELECTOR700/CLOSURE700.json',
    independentOutputs=300,pairedNewOutputs=40,
    evidenceValidation='artifacts/comprobaciones/C03/K2_HORIZON_SELECTOR700/EVIDENCE_VALIDATION700.json')
state['k2Report']=closure['report']
state['ownerPriority']='Comparison complete; resume C03 product blockers with registered Qwen candidate, preserving independent model versus BAXY-layer methodology.'
state['checkpoint']='Comparison699/700 complete:300 original outputs+40 paired; retain Qwen working candidate, no model promotion or C03 acceptance. Resume694/693. Survey26/716/0.'
state['confirmedAtUtc']=validation['utc']
state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with (base/'CHECKPOINT.md').open('a',encoding='utf-8') as f:
    f.write('\n\n## Comparación independiente y política cerradas — '+validation['utc']+'\n\n'+state['checkpoint']+'\n\n')
    f.write('Referencias: BF16 pequeño33/50, Qwen40/50, K2grande39/50. Prácticos: Qwen40/50 (1.352s,3165.55MiB GPU/715.38MiB RAM); K2low28/50; K2high38/50 (8.8285s,3444.23MiB GPU/787.56MiB RAM). Son picos del servidor, no del producto.\n\n')
    f.write('Quitar sólo el system: Qwen7→5/20, K2high10→8/20; K2recupera hora y abstención pero pierde4casos. Un caso sin herramienta deInternet no concede capacidad. Todas340salidas nuevas revisadas; paridad50effort+40system. EVIDENCE_VALIDATION700 verifica coherencia/hashes/compilación; no nuevo Full deproducto ni cobertura. Informes viejos698 son históricos rectificados; CLOSURE700 es la decisión más reciente.\n')

# Inventory only the five exact, newly produced research directories and their diagnostics.
folders=[str((base/n).relative_to(root)).replace('\\','/') for n in [
    'K2_HORIZON_COMPARISON696','K2_HORIZON_LATENCY697','K2_HORIZON_REVIEW_2026-09-09',
    'K2_HORIZON_NATIVE699','K2_HORIZON_SELECTOR700']]
names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','--',*folders],cwd=root,text=True).splitlines()
names=sorted(set(names+scripts)-{'artifacts/comprobaciones/C03/K2_HORIZON_SELECTOR700/PINS700.json'})
pins={n:dict(bytes=(root/n).stat().st_size,sha256=sha(root/n)) for n in names}
(out/'PINS700.json').write_text(json.dumps(dict(utc=validation['utc'],files=pins,scope='Exact public research files and Python diagnostics; excludes this receipt, mutable C03 checkpoint and private raw history.'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(validation=validation,pinned_files=len(pins),decision=closure['decision'])))
