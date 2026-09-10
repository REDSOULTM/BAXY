"""Record manual adjudication767; append evidence without changing survey coverage."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import copy
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
OUT = BASE / 'STATUS_BATCH767'
RUN = PRIVATE / 'C03-status-batch767-private'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


now = datetime.now(timezone.utc).isoformat()
source = '21cb408063c65a285ecd605863ef9f68aadb1a95'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == source
assert not (OUT / 'RESULT.json').exists()
exit_result = read(OUT / 'EXIT.json')
assert exit_result['exit_code'] == 0
assert all(exit_result[k] for k in ['manifest_unchanged', 'sources_unchanged',
    'source766_unchanged', 'source764_unchanged', 'runner_unchanged', 'app_dll_unchanged'])
resources = read(OUT / 'RESOURCES.json')
assert not resources['violations']
review = read(RUN / 'review.json')
assert len(review) == 73
failures = {
    'H0023': ('inventory_draft_rejected', 'No final inventory. First draft names all20 returned identities but asserts unobserved recency; later drafts omit or duplicate identities. False short-word rejection repaired766 does not justify accepting chronology.'),
    'H0103': ('inventory_draft_rejected', 'No final inventory. First draft groups20 windows into10 labels without preserving identities/multiplicities and adds unobserved visibility; later text confuses page20 with total25.'),
    **{key: ('global_inventory_interpretation', 'No inventory reaches Core; clarification does not fulfill the supported inventory request. English request also receives Spanish clarification.') for key in ['H0209', 'H0663', 'windows-all-en']},
    'H0532': ('no_fresh_read', 'Memory capacity asserted without a fresh Core read.'),
    'H0539': ('memory_total_labelled_available', '16.5GB usable RAM is labelled available; measured available is1.9235GB, installed17.1799GB, usable16.5395GB.'),
    'H0655': ('memory_total_labelled_available', 'Only16.54GB available is asserted; available is1.9033GB, usable16.5395GB. Unlike765 the complete reply does not distinguish those quantities.'),
    'H0508': ('memory_total_labelled_available', 'OS observation is correct but16.54GB usable RAM is labelled available; measured available1.8964GB.'),
    **{key: ('supported_read_not_selected', 'Supported requested fresh reading not obtained; no accredited answer.') for key in ['H0359', 'H0450', 'H0499', 'H0602', 'clock-date-en', 'audio-order-es']},
    'cpu-usage-en': ('cpu_percent_scaled_twice', 'Measured usagePercent0.6622516556291391 becomes66.2% in repeated drafts. Rejected as wrong_machine_value; no final answer.'),
    'H0732': ('internet_not_observed', 'InterfacesUp alone does not establish Internet connectivity; final asserts PC online.'),
    'network-wifi-en': ('wifi_scope_expanded', 'Observed WLAN disconnected is expanded to disconnected from every network.'),
    'network-internet-es': ('no_fresh_read', 'Internet absence asserted without a fresh Core read.'),
    **{key: ('cpu_process_metric_and_membership', 'Process lifetime TotalProcessorSeconds is presented as current CPU ranking; process instances also do not establish aggregate app ranking.') for key in ['H0364', 'processes-top2-es']},
    'H0675': ('no_fresh_read', 'Python RAM amount asserted without a fresh process reading.'),
}
assert len(failures) == 22
verdicts = []
for row in review:
    key = row['case_id']
    category, reason = failures.get(key, ('verified_answer', 'Complete reply checked against this turn\'s fresh observation and original semantic criterion.'))
    if key in {'H0104', 'windows-focus-mixed', 'windows-focus-reference-es'}:
        reason = 'Fresh foreground observation supports WhatsApp identity. Accepted wording uses ventana, not the older rejected ventanal form; no causal repair credited.'
    if key == 'H0650':
        reason = 'Fresh RAM ranking is correctly descending: python875, ChatGPT838, llama769, msedge519, ChatGPT402MB; distinct observed process instances retained.'
    verdicts.append({k: row[k] for k in ['case_id', 'group', 'turn_id']} | {
        'correct': key not in failures, 'category': category, 'reason': reason})
assert sum(v['correct'] for v in verdicts) == 51
result = {'utc': now, 'source_commit': source, 'status': 'complete_registered_regression_adjudicated',
    'cases': 73, 'correct': 51, 'not_accredited': 22, 'substantive_failures': 22,
    'coverage_added': 0, 'survey': {'covered': 26, 'open': 716, 'not_applicable': 0},
    'method': 'All73 complete records against their own fresh observations and frozen689/729 criteria; root t1-7 plus bounded read-only reviews t8-40 and t41-73. No terminal-status-only scoring.',
    'interpretation_sensitive': 2,
    'interpretation_sensitivity': 'H0383/audio-status-en retain prior acceptance of the measured default endpoint without requiring an unrequested literal endpoint name/percent symbol. H0655 now fails: its complete wording mislabels usable RAM as available.',
    'comparison_limit': 'Different machine observations and prose prevent attributing score changes to766.765 also failed its DLL seal. Native model comparison remains699, paired prompt diagnosis737.',
    'resources': resources, 'panel_sha256': sha(RUN / 'panel.json'),
    'failure_categories': dict(Counter(v['category'] for v in verdicts if not v['correct'])),
    'verdicts': verdicts,
    'evidence_sha256': {name: sha(RUN / name) for name in ['review.json', 'panel.json', 'launch.log',
        'capture/events.jsonl', 'compose-audit.jsonl', 'shell-trace.jsonl', 'turn-audit.jsonl',
        'raw-replies.jsonl', 'processes.json', 'memory-samples.jsonl']}}
write(OUT / 'RESULT.json', result)
write(RUN / 'adjudication.json', result)
md = ['# Adjudicación privada767', '51 respuestas acreditadas y22 fallos; sin cobertura automática. Hechos y borradores completos en review.json.']
for row, verdict in zip(review, verdicts):
    md.extend([f"## {row['turn_id']} · {row['case_id']}", '**Entrada:** ' + row['text'],
        '**Respuesta:** ' + row['terminal']['final'], '**Criterio:** ' + row['criterion'],
        '**Adjudicación:** ' + ('PASS. ' if verdict['correct'] else 'FAIL. ') + verdict['reason']])
(RUN / 'ADJUDICACION.md').write_bytes(('\n\n'.join(md) + '\n').encode('utf-8'))

registry = PRIVATE / 'C03-survey-requirements336-private/requirements.jsonl'
before_sha = sha(registry)
assert before_sha == '680a4e1de73b6ab9d9d0b7122c74084f978ab514b688cb8c45f6621f362d26a0'
backup = RUN / 'requirements-before767.jsonl'
assert not backup.exists()
backup.write_bytes(registry.read_bytes())
before = [json.loads(line) for line in backup.open(encoding='utf-8-sig')]
after = copy.deepcopy(before)
human = {v['case_id']: v for v in verdicts if v['case_id'].startswith('H')}
assert len(human) == 50
for row in after:
    verdict = human.get(row['case_id'])
    if verdict is None:
        continue
    row.setdefault('verification_evidence', []).append({
        'campaign': 'STATUS_BATCH767', 'source_commit': source, 'case_id': row['case_id'],
        'turn_id': verdict['turn_id'], 'literal_diagnostic_correct': verdict['correct'],
        'category': verdict['category'], 'private_adjudication': str(RUN / 'adjudication.json'),
        'development_variants_in_same_family': [v['case_id'] for v in verdicts
            if v['group'] == verdict['group'] and not v['case_id'].startswith('H')],
        'registered_runtime': True, 'no_hooks': True, 'ui_or_voice_credit': False, 'coverage_credit': False})
    row['verification_reason'] = ('767: literal ' + ('acreditado' if verdict['correct'] else 'sin acreditar')
        + '; ' + verdict['category'] + '. Generalización completa pendiente, sin crédito de UI/voz/consumo conjunto.')
    row['verification_updated_at'] = now
allowed = {'verification_evidence', 'verification_reason', 'verification_updated_at'}
assert len(after) == 742 and Counter(r['verification_status'] for r in after) == {'open': 716, 'covered': 26}
assert all({k:v for k,v in a.items() if k not in allowed} == {k:v for k,v in b.items() if k not in allowed}
           for a,b in zip(before, after))
assert sum(a != b for a,b in zip(before, after)) == 50
registry.write_bytes((''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in after)).encode('utf-8'))
write(OUT / 'REGISTRY_UPDATE.json', {'utc': now, 'before_sha256': before_sha,
    'after_sha256': sha(registry), 'snapshot_private': str(backup), 'changed_rows': 50,
    'fields_changed': sorted(allowed), 'coverage_added': 0, 'counts': result['survey'],
    'authorship_expectations_literals_source_references_and_statuses_unchanged': True})
(OUT / 'REPORT.md').write_bytes('''# Tanda767: binario estable, inventario todavía pendiente

Los73 casos completos producen51 respuestas acreditadas y22 fallos. Fuente766, fuente764, manifiesto, runner y DLL permanecen intactos; la preparación de main.py ocurrió antes del sello. EXIT conserva su quality_adjudicated=false original: RESULT registra la revisión posterior. Todas las respuestas se compararon con sus propias observaciones frescas y los criterios originales, sin exigir frases propias de un modelo.

El falso veto lexical de766 desaparece, pero H0023 introduce recencia de apertura no observada en su lista20/25. Rechazar ese dato es correcto. Los reintentos pierden entradas o multiplicidad; H0103 también omite identidades y confunde página con total. El canal de corrección conserva sólo una etiqueta extra_claim y exige una frase, sin comunicar la ausencia de tiempos de apertura. Ésa es la siguiente frontera a reparar; no otro modelo ni una relajación del veto factual.

El foco mixto pasa con una redacción distinta, sin reparar todavía la forma ventanal rechazada antes. H0655 ahora llama disponible a RAM utilizable sin desambiguar; cpu-usage-en convierte0,662% en66,2%. El cambio de puntuación respecto de otras corridas no demuestra causalidad: cambian las observaciones y la prosa;765 además carecía de sello válido de DLL.

Pico del árbol conducido:3499,56MiB VRAM y2489,31MiB RAM residente sumada;218,734s de corrida, preparación aparte, sin guarda de recursos activada. No acredita pantalla, voz ni el consumo conjunto final. Se agregan50 referencias a la encuesta conservando26 cubiertos,716 abiertos y0 no aplicables. Datos literales y payloads permanecen privados en C03-status-batch767-private. C03 sigue activo.
'''.encode('utf-8'))
checkpoint = ('767 terminada/adjudicada:51/73 acreditadas,22 fallos; todos los EXIT guards true, sin violaciones. '
    '3499,56MiB VRAM/2489,31MiB RSS/218,734s, sin UI/voz.50 referencias de encuesta añadidas,26/716/0; SHA=' + sha(registry)
    + '. Fuente766 publicada21cb4080. Sesión79389 terminal0 recogida, no proceso activo. Siguiente: corregir pérdida de causa factual en retry de inventario y exigencia de una frase; no relajar verdad ni cambiar modelo.\n\n')
cp = BASE / 'CHECKPOINT.md'
pending = cp.with_suffix('.pending.md')
pending.write_bytes(checkpoint.encode('utf-8') + cp.read_bytes())
pending.replace(cp)
relevo = read(BASE / 'RELEVO_ACTIVO.json')
relevo.update(confirmedAtUtc=now, checkpoint=checkpoint.strip(), activeValidation=None,
    workStatus='status767_adjudicated_inventory_correction_pending',
    continuation='Repair factual correction in window_prose_facts.py and llm.py; preserve full list without unobserved chronology.',
    latestProductRun={'name': 'product767', 'sessionId': 79389, 'exitCode': 0, 'turns': 73,
        'appDllUnchanged': True, 'adjudication': '51correct/22failures; no coverage or UI/voice credit'})
write(BASE / 'RELEVO_ACTIVO.json', relevo)
(BASE / 'HANDOFF.md').write_bytes(('''# Handoff C03 —767 —2026-09-10

Goal activo en Goal-c03; main intacto5f572ee1. Fuente766 publicada21cb408063c65a285ecd605863ef9f68aadb1a95. Encuesta742/rev1248:26cubiertos/716abiertos/0NA; registroSHA=''' + sha(registry) + '''. Sin pregunta pendiente. BAXY manual cerrado.79389 terminó0/recogido; no inferencia ni gate activo.

767 adjudicada51/73,22fallos; todos los guards true incluido DLL.3499,56MiB GPU/2489,31MiB RSS,218,734s preparación aparte. RESULT/REPORT en STATUS_BATCH767; respuestas y payloads privados C03-status-batch767-private/review.json,ADJUDICACION.md.50 referencias añadidas a encuesta sin cambiar estados. No ganancia causal ni UI/voz/cobertura. H0655 y CPUEN fallan con redacción distinta; foco mixto pasa ahora con ventana, sin reparar ventanal.

Siguiente: reparar la transformación rechazo→corrección de inventario. window_prose_facts.py:405–445 detecta recencia no observada pero devuelve extra_claim; llm.py:10076–10090,10172,10220 exige una frase, aun para20entradas. Reusar canal Verified factual correction actual para causa concreta y permitir toda la lista, sin nombres/modelos excepcionales ni cambiar presupuesto. No edición fuente768 iniciada todavía.

766 igualó mínimos5/5 de palabra observada/salida;30controles,457owners/0skip,343integridad/1skipSTT,Fast0/Release11,04s. TRUNCATION766/VALIDATION y PUBLICATION registran comandos/pins. Programa407=b779c55710ff6efbf1d179d460d7ad6c093bd71e96ad8b290db56d0efa455ad3, raíces experiments/voice_latency+scripts+src/baxy_mind. No tocar sellos históricos751/760 ni wakev17. Replay766 usó sobre reconstruido porque audit.situation se corta2048caracteres; payload idéntico,1stub, no inferencia.

764 aplica presupuesto dense existente al inventario:136dueñas/Fast0.765sólo diagnóstico52/21 porque launcher reconstruyó DLL después del sello;767 prepara con main.compile_if_needed antes de PREREG. Runtime/perfiles no cambiados.699:50tareas completas×6perfiles sinBAXY;737:57pares K2,14sóloBAXY/3sólo directo. No promover un modelo con estos datos.

Otros bloqueos: interpretación de inventario, foco ventanal/relativa, lecturas ausentes, etiquetasRAM, Internet vs interfaz/WLAN, CPU acumulada vs actual. Full7 histórico4574.NETpass/1skip+16omisiones;11399Pythonpass/3skips+466subtests. Falta cobertura742, reserva, UI/loopback/AEC, recursos conjuntos≤4GiB, matriz/continuidad y Full final. Preservar WIP ajeno; C03 no terminado.
''').encode('utf-8'))
print(json.dumps({'correct': 51, 'failures': 22, 'registry_sha256': sha(registry)}))
