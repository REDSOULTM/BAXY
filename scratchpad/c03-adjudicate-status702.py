"""Preserve all 73 product outcomes, including the pending-confirmation cascade."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
home = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
private = home / 'C03-status-batch702-private'
out = base / 'astra-status-batch702'

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')

assert not (out / 'RESULT.json').exists()
assert read(out / 'EXIT.json') == {'exitCode': 0, 'manifest_unchanged': True}
rows = read(private / 'review.json')
assert len(rows) == 73 and len({row['case_id'] for row in rows}) == 73
assert (private / 'panel.json').read_bytes() == (home / 'C03-status-batch694-private/panel.json').read_bytes()
prereg = read(out / 'PREREG.json')
assert all(sha(root / name) == expected for name, expected in prereg['sources'].items())
plan = read(base / 'STATUS_BATCH702_PLAN.json')
assert sha(root / 'scratchpad/c03-status702-hook/sitecustomize.py') == plan['instrumentation_sha256']
assert sha(home / 'C03-survey-requirements336-private/requirements.jsonl') == plan['requirements_sha256']

passed = set('H0104 H0126 H0180 H0223 H0449 H0498 H0586 H0600 H0700 H0727 clock-time-mixed clock-date-reference-es H0127 H0433 H0650 processes-top3-en H0383 audio-status-en'.split())
verdicts = {}

def fail(ids, cause, reason):
    for case_id in ids.split():
        assert case_id not in verdicts and case_id not in passed
        verdicts[case_id] = {'verdict': 'failed', 'cause_group': cause, 'reason': reason}

fail('H0023 H0103 H0209 H0663', 'unnecessary_clarification',
     'A clear enumeration request becomes a clarification without a fresh list of windows.')
fail('windows-all-en', 'wrong_operation_and_unnecessary_confirmation',
     'The request enumerates windows, but the selector proposes browser.tabs.list. PrivacySensitive becomes a confirmation before the read and starts the subsequent pending-state cascade.')
assert rows[5]['case_id'] == 'windows-all-en' and rows[44]['case_id'] == 'cpu-order-es'
fail(' '.join(row['case_id'] for row in rows[6:45]), 'pending_confirmation_blocks_new_request',
     'A pending browser-tabs confirmation captures this new independent status request. No requested fresh Core read occurs; the visible answer asks to confirm or cancel the previous request. This is a product failure, not evidence that the status provider or model cannot answer in isolation.')
assert all(not row['core_calls'] for row in rows[6:45])
fail('H0450 H0499 H0602 clock-date-en audio-order-es', 'available_read_not_selected',
     'No supported fresh read is executed. The output reports interpretation failure or false incapability, or exhausts composition. That does not fulfill the status request.')
fail('H0732', 'link_state_not_internet_verification',
     'The answer claims that the PC is online for an Internet question. The provider only counts OperationalStatus.Up interfaces; it neither verifies Internet reachability nor states that narrower limitation.')
fail('network-wifi-en', 'observation_scope_expansion',
     'Disconnected WLAN is expanded to not connected to any network. The observed Wi-Fi state does not establish absence of Ethernet or Internet.')
fail('network-internet-es', 'unverified_state_claim',
     'Without a Core operation, the answer claims no Internet and a failed connection attempt. The payload only establishes an interpretation failure, not a measured connection state or attempted connection.')
fail('H0364 processes-top2-es', 'cpu_ranking_metric_and_membership',
     'The final claims a current CPU-consumption ranking, but the actual process payload measures accumulated totalProcessorSeconds. Repeated process names are also collapsed, changing the requested ranking. All compose stages, including facts after progress, were inspected.')
fail('H0675', 'historical_observation_without_fresh_read',
     'The answer repeats a process memory value from the preceding conversation without a fresh requested Core read. Agreement with the previous value does not establish current usage.')

for row in rows:
    case_id = row['case_id']
    if case_id not in passed:
        assert case_id in verdicts, case_id
        continue
    assert row['terminal']['kind'] == 'published_final' and row['core_calls'] and row['compose'], case_id
    reason = 'Manual review of the full final and all compose stages: requested facts, units and scope agree with fresh typed observations. This observed run alone does not establish generalization or grant survey coverage.'
    if case_id in {'H0127', 'H0433'}:
        reason += ' The first draft has the wrong actor; the existing retry with the actual draft now names this PC and preserves disconnected Wi-Fi scope. This is evidence for the limited actor-recovery change.'
    if case_id == 'H0104':
        reason += ' The observed foreground title is ChatGPT, different from694. This success does not demonstrate repair of the title/jargon validator.'
    verdicts[case_id] = {'verdict': 'correct_observed_run', 'cause_group': '', 'reason': reason}

assert set(verdicts) == {row['case_id'] for row in rows}
assert len(passed) == 18
before = {row['case_id']: row for row in read(home / 'C03-status-batch694-private/adjudication.json')}
adjudication = [{**row, **verdicts[row['case_id']], 'before694': before[row['case_id']]['verdict']} for row in rows]
counts = dict(Counter(row['verdict'] for row in adjudication))
assert counts == {'failed': 55, 'correct_observed_run': 18}
transitions = dict(Counter(row['before694']+' -> '+row['verdict'] for row in adjudication))
gains = [row['case_id'] for row in adjudication if row['verdict'] == 'correct_observed_run' and row['before694'] != 'correct_observed_run']
losses = [row['case_id'] for row in adjudication if row['verdict'] != 'correct_observed_run' and row['before694'] == 'correct_observed_run']
write(private / 'verdicts.json', verdicts)
write(private / 'adjudication.json', adjudication)
report = ['# Producto702 — revisión íntegra de los73turnos', json.dumps(counts)]
for row in adjudication:
    report += ['## '+row['case_id'], row['text'], row['terminal']['final'], row['verdict']+': '+row['reason'],
               'Criterio: '+row['criterion'], json.dumps({'core_calls': row['core_calls'], 'decisions': row['decisions'], 'compose': row['compose']}, ensure_ascii=False)]
(private / 'RESULT.md').write_text('\n\n'.join(report)+'\n', encoding='utf-8', newline='\n')
resources = read(out / 'resources.json')
assert not resources['violations']
note = f'''# Producto702:18respuestas correctas y55fallos de73

Se conservan todos los resultados, con el mismo panel, orden y criterios694. La tanda completa falla: no se sustituye su resultado por los dos casos que mejoran. El sexto turno eligió browser.tabs.list al pedir ventanas y solicitó una confirmación innecesaria. Los39pedidos independientes siguientes quedaron atrapados en esa confirmación; ninguno hizo la lectura solicitada. La hora escapó de ese estado por una excepción preexistente. La causa común está en selección, política y continuidad de BAXY.

Transiciones desde694:{transitions}. Mejoran:{', '.join(gains)}. Pasan de correcto a fallo:{', '.join(losses)}. Cambian estado Windows e historial entre corridas; estas transiciones no son una atribución causal automática a la recuperación de actor702. El error de selección aparece antes de usar esa recuperación. H0104 recibe otro título observado, por lo que no acredita corregir el veto de jerga.

H0127/H0433 sí publican el estado Wi-Fi verificado tras un único reintento que conserva el borrador real y los hechos. La comprobación emparejada se documenta aparte al decidir adopción. Los50controles701 por brazo conservaron las51peticiones y50finales idénticos:44correctos/6fallos por brazo, sin activar recuperación WLAN. Son control de regresión, no evidencia de mejora.

Correcciones de diagnóstico: en694 la categoría false_composition_rejection para WLAN era demasiado amplia; el primer borrador tenía un actor incorrecto y lo defectuoso era la recuperación. Para procesos deben leerse todos los compose, no sólo el progreso inicial. H0364 falla aquí por métrica CPU acumulada y miembros del ranking, con hechos presentes en una etapa posterior. No se reescribe el sello694. H0732 sigue fallando: interfaces Up no demuestran Internet. Tampoco se acepta la ampliación Wi-Fi→toda red ni valores históricos sin lectura nueva.

Conductor exit0, manifiesto intacto, GPU{resources['gpu_peak_mib']}MiB/RAM{resources['ram_peak_mib']}MiB y{resources['seconds']}s; sin infracciones. No hubo UI/voz simultáneas ni aceptación del consumo total. Fuente702 tiene79pruebas focales,392dueñas yFast exit0. Full693 es línea base anterior, no un Full702.

Encuesta742/rev1248:26cubiertos/716abiertos/0NA, cero cobertura nueva. C03 EN_CURSO. Siguiente: corregir la causa compartida de confirmación/continuidad conservando autorización del kernel, privacidad y binding exacto, y luego verificar la tanda completa.
'''
(out / 'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
names = ['panel.json', 'turns.jsonl', 'capture/events.jsonl', 'compose-audit.jsonl', 'turn-audit.jsonl', 'shell-trace.jsonl', 'raw-replies.jsonl', 'http-posts.jsonl', 'decision-boundary.jsonl', 'review.json', 'verdicts.json', 'adjudication.json', 'RESULT.md']
result = {'utc': datetime.now(timezone.utc).isoformat(), 'total': 73, 'requirements': 50, 'variants': 23,
          'counts': counts, 'transitions694': transitions, 'gains': gains, 'losses': losses,
          'cause_groups': dict(Counter(row['cause_group'] for row in adjudication if row['cause_group'])),
          'resources': resources, 'plan_sha256': sha(base / 'STATUS_BATCH702_PLAN.json'),
          'private_hashes': {name: sha(private / name) for name in names},
          'survey': {'covered': 26, 'open': 716, 'not_applicable': 0}, 'new_coverage': 0,
          'ui_or_voice_credit': False, 'whole_batch_accepted': False, 'goal_complete': False}
write(out / 'RESULT.json', result)
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
print(json.dumps({'counts': counts, 'transitions': transitions, 'gains': gains, 'losses': losses}))
