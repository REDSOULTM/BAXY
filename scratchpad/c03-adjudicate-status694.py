"""Record manual review of all 73 completed694 outputs without new inference."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-status-batch694-private'
rows = json.loads((private / 'review.json').read_text(encoding='utf-8'))
assert len(rows) == 73 and len({r['case_id'] for r in rows}) == 73
assert not (base / 'astra-status-batch694/RESULT.json').exists()

failures = {}

def fail(ids, cause, reason):
    for case_id in ids.split():
        assert case_id not in failures
        failures[case_id] = {'verdict': 'failed', 'cause_group': cause, 'reason': reason}

fail('H0023 H0103 H0209 H0663 windows-all-en', 'unnecessary_clarification',
     'A clear enumeration request becomes a clarification without a fresh window list; English variant also receives Spanish.')
fail('H0104 windows-focus-mixed', 'false_composition_rejection',
     'Fresh foreground identity exists, but the compositor rejects drafts matching that identity and exhausts recovery. No useful final is published.')
fail('disk-used-es H0532 H0675', 'historical_observation_without_fresh_read',
     'Final presents a measurement or ranking from prior conversation without a new Core read. Agreement with a previous value does not satisfy the frozen freshness criterion.')
fail('H0539 H0508', 'measurement_field_meaning',
     'Narrator labels total usable RAM as available RAM; the fresh payload separately measures a much smaller available amount and installed capacity. H0508 also omits the requested installed RAM.')
fail('H0359 cpu-order-es H0450 H0499 H0602 clock-date-en audio-order-es',
     'available_read_not_selected',
     'A supported current read is not executed; output reports interpretation failure or false incapability, or composition subsequently exhausts. This is not successful fulfillment.')
fail('H0127 H0433', 'false_composition_rejection',
     'wifi.status returns a verified disconnected WLAN state, but wrong_actor rejection exhausts composition without a useful final.')
fail('H0732', 'link_state_not_internet_verification',
     'Final says the PC is online in answer to Internet availability, but NetworkInformationStatusProbe only counts interfaces whose OperationalStatus is Up. Neither Internet reachability nor an explicit narrower limitation is supplied.')
fail('network-wifi-en', 'observation_scope_expansion',
     'A disconnected WLAN observation becomes not connected to any network. wifi.status does not establish absence of Ethernet or Internet; the broader statement is unsupported.')
fail('network-internet-es', 'unverified_state_claim',
     'No Core operation occurs; final nevertheless asserts no Internet and a failed connection attempt. The payload says only interpretation failed and operationAttempted=false.')
fail('H0364', 'missing_process_observation',
     'Final names a CPU ranking, but the composition payload contains only a working-step status, not observed process facts. The asserted ranking is not grounded at the narration boundary.')
fail('H0650 processes-top3-en processes-top2-es', 'process_ranking_not_preserved',
     'Published order or membership differs from the fresh requested ranking. Repeated process names must not be silently removed or replaced. CPU payload also measures accumulated processor seconds, not current CPU rate.')

verdicts = {}
for row in rows:
    case_id = row['case_id']
    if case_id in failures:
        verdicts[case_id] = failures[case_id]
        continue
    assert row['terminal']['kind'] == 'published_final' and row['core_calls'] and row['compose'], case_id
    verdicts[case_id] = {
        'verdict': 'correct_observed_run', 'cause_group': '',
        'reason': 'Manual review: requested facts, units and scope agree with the fresh typed observation. This individual run does not demonstrate generalization or close a survey requirement.',
    }
    if case_id == 'H0065':
        verdicts[case_id]['reason'] += ' Minor grammatical mixing is preserved as a quality defect; the measured percentage is exact, intelligible and not an invented fact.'
    if case_id in {'H0026', 'gpu-identity-en'}:
        verdicts[case_id]['reason'] += ' Duplicate or unnecessarily broad read remains an efficiency/scope concern; observed requested GPU identity and capacity are correct.'
    if case_id == 'H0655':
        verdicts[case_id]['reason'] += ' The phrase disponible en total is interpreted with the explicit separate free, used and installed values, not as a second free-memory claim.'
    if case_id == 'windows-focus-reference-es':
        verdicts[case_id]['reason'] += ' Correct final follows two false title-related rejections; final success does not erase this integration defect.'

assert set(failures) <= set(verdicts)
counts = dict(Counter(v['verdict'] for v in verdicts.values()))
(private / 'verdicts.json').write_text(json.dumps(verdicts, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
old = {r['case_id']: r for r in json.loads((private.parent/'C03-status-batch689-private/adjudication.json').read_text(encoding='utf-8'))}
transitions = Counter(old[k]['verdict']+' -> '+v['verdict'] for k,v in verdicts.items())
gains = [k for k,v in verdicts.items() if v['verdict']=='correct_observed_run' and old[k]['verdict']!='correct_observed_run']
losses = [k for k,v in verdicts.items() if v['verdict']!='correct_observed_run' and old[k]['verdict']=='correct_observed_run']
note = f'''# Producto694: revisión completa, {counts.get('correct_observed_run', 0)} de 73 respuestas verificadas

Revisión de los 73 finales completos contra petición, payload tipado y criterio original689. {counts.get('failed', 0)} fallan; no se omiten agotamientos, falsas incapacidades, datos del historial ni afirmaciones no verificadas. Los textos e historias permanecen privados en LOCALAPPDATA; RESULT.json publica categorías, conteos y hashes.

Transiciones respecto de689: {dict(transitions)}. Mejoran a correcto: {', '.join(gains)}. Pasan de correcto a fallo: {', '.join(losses)}. Son dos corridas con estados Windows cambiantes, no una atribución causal automática de cada transición a693.

La proyección compartida conserva unidades y distingue capacidad instalada, utilizable, libre y usada; quedan errores de interpretación del modelo. Los fallos de ventanas, frescura, alcance de red y procesos continúan. H0732 no se acredita como Internet: el provider sólo observa interfaces Up. La segunda revisión inicialmente aceptó H0732 y network-wifi-en; raíz revisó el provider y rechazó ambos por alcance de evidencia. H0065 conserva una incorrección gramatical sin alterar el porcentaje; no demuestra calidad lingüística general.

El conductor terminó exit0 con manifiesto intacto. Pico de la corrida diagnóstica3499,5586MiB GPU y2485,0547MiB RAM; sin infracciones del monitor. No hubo UI/voz simultáneas: no es consumo total certificado de BAXY. Full693 existente:11051 Pythonpass/3 skips ambientales/466 subtests y4480.NETpass/1skip agregado; opt-ins separados. No se ha ejecutado otro Full ni se cuentan skips como pases.

Encuesta742/rev1248:26 cubiertos/716 abiertos/0NA. Esta revisión agrega cero cobertura; C03 continúa EN_CURSO. Comparación de modelos699/700 completada y publicada en a8eaf976; Qwen sigue candidato, no producto aceptado. Siguiente: decidir adopción limitada de693 por sus mediciones propias y reparar primeras transformaciones erróneas, sin aplicar prototype695.
'''
(private/'public-note.md').write_text(note, encoding='utf-8', newline='\n')
receipt = {'utc': datetime.now(timezone.utc).isoformat(), 'reviewed': 73, 'counts': counts,
           'transitions': dict(transitions), 'gains': gains, 'losses': losses,
           'private_review_sha256': hashlib.sha256((private/'review.json').read_bytes()).hexdigest(),
           'root_review': 'All visible finals and typed facts read; partial independent second review38-72. Disagreements and noncausal comparisons disclosed in RESULT.md.',
           'source_adopted': False, 'new_coverage': 0}
(base/'astra-status-batch694/MANUAL_REVIEW.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(receipt, ensure_ascii=False))
