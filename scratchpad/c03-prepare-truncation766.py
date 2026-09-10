"""Preserve765 diagnosis, pin766 and prepare the next fully sealed category run."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import copy
import hashlib
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
out = base / 'TRUNCATION766'
out.mkdir(exist_ok=False)
now = datetime.now(timezone.utc).isoformat()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
read = lambda path: json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


prior = read(base / 'STATUS_BATCH761/RESULT.json')
exit_record = read(base / 'STATUS_BATCH765/EXIT.json')
assert exit_record['exit_code'] == 0 and exit_record['app_dll_unchanged'] is False
assert all(exit_record[key] for key in ['manifest_unchanged','sources_unchanged','source760_unchanged','source764_unchanged','runner_unchanged'])
rows = read(private / 'C03-status-batch765-private/live-review.json')
assert len(rows) == 73
write(private / 'C03-status-batch765-private/review.json', rows)
result = copy.deepcopy(prior)
result.update(utc=now, status='semantic_diagnosis_only_binary_seal_failed', correct=52,
    not_accredited=21, substantive_failures=21, sealed_acceptance=False,
    method='All73 records reviewed against their own fresh facts, roott1-7 and disputed cases, readonlyt8-40/t41-73. Same frozen panel criteria. All scoring is semantic diagnosis only: launcher rebuilt the DLL after PREREG.',
    interpretation_sensitive=3, resources=read(base / 'STATUS_BATCH765/RESOURCES.json'))
result.pop('evidence_sha256', None)
result.pop('latency_seconds', None)
for verdict in result['verdicts']:
    key = verdict['case_id']
    if key == 'H0650':
        verdict.update(correct=True, category='verified_answer', reason='Fresh memory ranking now places ChatGPT before python; the descending numbered answer matches the values. Different facts from761; not a causal improvement.')
    elif key in {'H0023','H0103'}:
        verdict.update(category='inventory_draft_rejected', reason='Completed drafts are captured, but the five-letter observed title collides with its longer process name in the truncated-word checker. H0023 first draft preserves all20 entries and20/24 scope; H0103 first draft also omits identities/group counts. No final delivered.')
    elif key == 'H0539':
        verdict.update(category='memory_capacity_label_mismatch', reason='Total usable16.54GB is called installed, although measured installed RAM is17.18GB. Distinct from761 available-label error.')
assert sum(v['correct'] for v in result['verdicts']) == 52
result['failure_categories'] = dict(Counter(v['category'] for v in result['verdicts'] if not v['correct']))
result['evidence_sha256'] = {name:sha(private/'C03-status-batch765-private'/name) for name in [
    'review.json','panel.json','launch.log','capture/events.jsonl','compose-audit.jsonl','shell-trace.jsonl','turn-audit.jsonl','raw-replies.jsonl','processes.json','memory-samples.jsonl']}
write(base / 'STATUS_BATCH765/RESULT.json', result)
write(private / 'C03-status-batch765-private/adjudication.json', result)
md = ['# Respuestas765 — diagnóstico, sello de DLL fallido',
      '52respuestas semánticamente acreditables/21fallos. No aceptación de candidato ni crédito automático de encuesta. Payloads completos: review.json.']
for row, verdict in zip(rows, result['verdicts']):
    assert row['case_id'] == verdict['case_id']
    md.extend([f"## {row['turn_id']} · {row['case_id']}", '**Entrada:** '+row['text'],
        '**Respuesta:** '+row['terminal']['final'], '**Criterio:** '+row['criterion'],
        '**Diagnóstico:** '+verdict['reason']])
(private / 'C03-status-batch765-private/ADJUDICACION.md').write_bytes(('\n\n'.join(md)+'\n').encode('utf-8'))
prereg = read(base / 'STATUS_BATCH765/PREREG.json')
app = root / 'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.dll'
write(base / 'STATUS_BATCH765/BINARY_SEAL_FAILURE.json', {
    'utc':now,'before_sha256':prereg['app_dll_sha256'],'after_sha256':sha(app),
    'last_write_utc':datetime.fromtimestamp(app.stat().st_mtime, timezone.utc).isoformat(),
    'observed':'main.py compile_if_needed rebuilt App and published Core before launching the conductor. launch.log records15.43s build. Existing source fingerprint cache did not match; the exact triggering entry and whether differences are only metadata are not proved.',
    'source':'main.py:204-252','decision':'765 retained as diagnosis; no sealed candidate acceptance.',
    'next':'Prepare using the same main.compile_if_needed(force=False) before hashing DLL; then execute actual py main.py --conductor and require unchanged DLL.',
})
(base / 'STATUS_BATCH765/REPORT.md').write_bytes('''# Respuesta producida, rechazo posterior

765 terminó73turnos con52 respuestas semánticamente acreditables y21 fallos. La fuente, el modelo, el manifiesto y el runner permanecieron intactos, pero py main.py recompiló Baxy.dll antes del conductor y después del sello inicial. Por eso se conserva como diagnóstico; no acredita una regresión con binario congelado. BINARY_SEAL_FAILURE.json registra hashes, tiempos y límite de atribución. La siguiente corrida preparará la misma compilación del launcher antes de congelar sus entradas.

El presupuesto denso ya llega a composición. H0023 produce una lista fiel de20entradas y alcance20/24, pero la capa que busca palabras cortadas la rechaza: toma un nombre observado de cinco letras por un recorte del nombre largo de su proceso. H0103 también pasa por ese rechazo, aunque su primera lista tiene omisiones adicionales y no debe aprobarse por retirar ese veto. No se presenta como una reparación terminada: los inventarios aún fallan y los reintentos ahora duran53,52s/37,34s.

La comprobación lexical usa valores de hechos de seis letras o más y compara contra palabras de salida desde cinco. Una palabra completa de cinco queda fuera del conjunto válido. La corrección766 iguala ambos mínimos; no añade una lista de aplicaciones ni cambia el modelo, el prompt o un límite de tiempo. El verificador factual y la adjudicación completa siguen siendo necesarios.

El árbol conducido alcanzó3499,56MiB de VRAM y2386,90MiB de RAM residente sumada, sin guarda activada. Duración382,609s incluyendo preparación; no acredita UI/voz ni consumo conjunto final. H0650 ahora ordena bien valores distintos, por lo que el52frente a51de761 no es una ganancia causal. Datos privados completos en C03-status-batch765-private/ADJUDICACION.md y review.json. Encuesta26/716/0; cero cobertura añadida y C03 activo.
'''.encode('utf-8'))

# Current declarations track the program; historical source and wake seals stay intact.
sys.path.insert(0, str(root))
from scripts.wake_validation_program_tree import fingerprint_program_tree
prior_program = read(base / 'SEMANTIC_INVENTORY760/PROGRAM.json')
program = fingerprint_program_tree(repository_root=root, source_roots=[root/p for p in prior_program['roots']])
assert program['pythonFiles'] == 407
source_paths = ['src/baxy_mind/llm.py','tests/test_compose_contract.py',
    'experiments/stt_quality/evaluate_reserved_stt.py','experiments/stt_quality/audit_fresh_postweight_stt_sources.py',
    'tests/test_price_v8_veto_damage_by_cause.py']
for relative in source_paths[2:4]:
    path = root / relative
    data = path.read_text(encoding='utf-8')
    assert data.count(prior_program['sha256']) == 1
    path.write_bytes(data.replace(prior_program['sha256'],program['sha256']).encode('utf-8'))
old_llm = read(base / 'SEMANTIC_INVENTORY760/SOURCE_PINS.json')['src/baxy_mind/llm.py']
v8 = root / source_paths[4]
data = v8.read_text(encoding='utf-8'); assert data.count(old_llm) == 1
v8.write_bytes(data.replace(old_llm,sha(root/source_paths[0])).encode('utf-8'))
write(out / 'SOURCE_PINS.json', {p:sha(root/p) for p in source_paths})
write(out / 'PROGRAM.json',program)
write(out / 'PLAN.json', {'utc':now,'change':'Five-letter complete source values join the same token range as the checked draft. No model-specific exception, prompt or budget change.',
    'diagnosis':'STATUS_BATCH765/REPORT.md','owners':'457passed/0failed/0skipped,2.99s,30new cases',
    'validation_pending':'Current pin integrity and Fast; then replay captured correct draft and publish before registered73 regression767.',
    'survey_counts':{'covered':26,'open':716,'not_applicable':0},'coverage_added':0})
(out/'owners.log').write_bytes((Path(os.environ['TEMP'])/'c03-truncation766-owners.log').read_bytes().replace(b'\r\n',b'\n'))

runner = (root/'scratchpad/c03-status-batch765.py').read_text(encoding='utf-8')
runner = runner.replace('STATUS_BATCH765','STATUS_BATCH767').replace('batch765','batch767').replace('profile765','profile767')
runner = runner.replace("pins760 = read(ROOT / 'artifacts/comprobaciones/C03/SEMANTIC_INVENTORY760/SOURCE_PINS.json')",
    "pins766 = read(ROOT / 'artifacts/comprobaciones/C03/TRUNCATION766/SOURCE_PINS.json')")
runner = runner.replace('pins760','pins766').replace('source760','source766')
runner = runner.replace('Registered73 product regression after dense inventory764; same panel and criteria as761/752B, no model comparison.',
    'Registered73 product regression after truncation766 with dense764; original panel/criteria. Build prepared before sealing DLL; no model comparison.')
runner = runner.replace('Published764 owners136pass and Fast; Python760 intact. Full7 historical, not new product acceptance.',
    'Published766 owners/current pin integrity and Fast, dense764 owners/Fast retained. Full7 historical, no final acceptance.')
anchor = "paths = subprocess.check_output(\n"
assert runner.count(anchor) == 1
runner = runner.replace(anchor,
    "# Use the launcher build path before sealing. This does not start BAXY.\n"
    "preparation = subprocess.run([sys.executable, '-X', 'utf8', '-c',\n"
    "    'import main; main.compile_if_needed(force=False)'], cwd=ROOT,\n"
    "    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,\n"
    "    creationflags=subprocess.CREATE_NO_WINDOW, check=True)\n"
    "assert all(sha(ROOT / path) == digest for path, digest in {**pins766, **pins764}.items())\n" + anchor)
runner = runner.replace("PRIVATE.mkdir()\n", "PRIVATE.mkdir()\n(PRIVATE / 'build-preparation.log').write_bytes(preparation.stdout)\n")
runner = runner.replace("'app_dll_sha256': app_sha,", "'build_preparation_sha256': sha(PRIVATE / 'build-preparation.log'), 'build_prepared_before_seal': True,\n    'app_dll_sha256': app_sha,")
target = root/'scratchpad/c03-status-batch767.py'; assert not target.exists()
target.write_bytes(runner.encode('utf-8'))
cp=base/'CHECKPOINT.md'; pending=cp.with_suffix('.pending.md')
checkpoint=('765terminado exit0 pero DLL cambió por rebuild del launcher antesdeinferir: diagnóstico52/73,21fallos, no aceptación sellada. '
    'H0023primera lista correcta, veto _truncated_fact_word: nombre completo5letras excluido del vocabulario6+, prefijo de proceso largo. '
    '766candidato iguala mínimos,457owners pass/0skips/30nuevos; faltan integridad/Fast. Preparado767 concompile_if_needed antesdesello. '
    'No inferencia activa; no editar durante siguientesvalidaciones.26/716/0.\n\n')
pending.write_bytes(checkpoint.encode('utf-8')+cp.read_bytes());pending.replace(cp)
rp=base/'RELEVO_ACTIVO.json';r=read(rp)
r.update(checkpoint=checkpoint.strip(),activeValidation=None,workStatus='truncation766_current_integrity_and_fast_pending',
    continuation='Validate766 declarations/Fast, offline captured draft replay, publish and run prepared767 original73 cases with frozen postbuild DLL.',
    latestProductRun={'name':'product765','sessionId':79148,'exitCode':0,'turns':73,'appDllUnchanged':False,
        'status':'semantic_diagnosis_only_binary_seal_failed','adjudication':'52semantically correct/21failures; no acceptance or coverage'})
write(rp,r)
print(json.dumps({'diagnostic765':{'correct':52,'failed':21,'binary_seal':False},'candidate766':program,'runner767_prepared':True}))
