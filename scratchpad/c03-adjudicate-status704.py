"""Explicit review of all73 status finals after confirmation continuity703."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-status-batch704-private'
rows = json.loads((private / 'review.json').read_text(encoding='utf-8'))
assert len(rows) == 73 and not (base / 'astra-status-batch704/RESULT.json').exists()
passed = set('''H0104 windows-focus-reference-es H0025 H0207 H0384 H0442 H0644 disk-free-en
H0026 H0087 H0114 H0194 H0370 H0625 gpu-identity-en gpu-usage-es
H0111 H0156 H0162 H0342 H0655 memory-total-en memory-free-mixed memory-used-es
H0037 H0144 H0379 H0665 battery-charge-en battery-level-es H0065 H0350 cpu-usage-en
H0126 H0180 H0223 H0449 H0498 H0586 H0600 H0700 H0727 clock-time-mixed clock-date-reference-es
H0127 H0433 H0650 processes-top3-en H0383 audio-status-en'''.split())
assert len(passed) == 50
verdicts = {}

def fail(ids, cause, reason):
    for case_id in ids.split():
        assert case_id not in passed and case_id not in verdicts
        verdicts[case_id] = {'verdict': 'failed', 'cause_group': cause, 'reason': reason}

fail('H0023 H0103 H0209 H0663', 'unnecessary_clarification',
     'A clear window enumeration request becomes a clarification without a fresh window list.')
fail('windows-all-en', 'wrong_operation_and_unnecessary_confirmation',
     'The window enumeration is routed to browser.tabs.list, requiring confirmation instead of providing the requested window list. The wrong initial operation remains a failure even though later requests now escape.')
fail('windows-focus-mixed', 'false_composition_rejection',
     'The fresh foreground identity is ChatGPT and the draft correctly names its focused window, but the validator rejects the ventanal wording as missing_fact through18drafts and publishes no useful final.')
fail('disk-used-es H0532 H0675', 'historical_observation_without_fresh_read',
     'The final repeats a measurement or process ranking from conversation without a new requested Core read. Prior agreement does not establish current usage or satisfy the frozen freshness criterion.')
fail('H0539 H0508', 'measurement_field_meaning',
     'H0539 labels16.54GB usable memory as installed despite17.18GB separately observed installed capacity. H0508 labels usable memory as available and omits requested installed capacity. Correct digits do not repair a wrong field meaning.')
fail('H0359 cpu-order-es H0450 H0499 H0602 clock-date-en audio-order-es', 'available_read_not_selected',
     'A supported fresh status read is not executed. The final reports interpretation failure, false incapability, or composition exhaustion instead of fulfilling the request.')
fail('H0732', 'link_state_not_internet_verification',
     'The answer claims online for an Internet question, but network.status only counts interfaces whose OperationalStatus is Up. Internet reachability is not verified and the limitation is not stated.')
fail('network-wifi-en', 'observation_scope_expansion',
     'The disconnected Wi-Fi observation is expanded to absence of any network connection. It does not establish absence of Ethernet or Internet.')
fail('network-internet-es', 'unverified_state_claim',
     'No Core operation occurs, but the final claims no Internet and a failed connection attempt. The payload establishes only interpretation failure.')
fail('H0364 processes-top2-es', 'cpu_ranking_metric_and_membership',
     'The final claims a current CPU ranking while the observed metric is accumulated totalProcessorSeconds. It also collapses repeated process names or substitutes members. Process facts are present after the progress compose; they were not omitted from review.')

for row in rows:
    case_id = row['case_id']
    if case_id not in passed:
        assert case_id in verdicts, case_id
        continue
    assert row['terminal']['kind'] == 'published_final' and row['core_calls'] and row['compose'], case_id
    reason = 'Manual review of the complete final and all distinct compose stages: requested facts, labels, scope and language agree with fresh typed observations. This observed run alone does not certify generalization or grant survey coverage.'
    if case_id == 'H0655':
        reason += ' As in694, disponible en total is interpreted with the separate explicit free/used/installed quantities; the wording remains a quality concern, not a second free-memory measurement.'
    if case_id in {'H0026', 'gpu-identity-en'}:
        reason += ' Duplicate or overly broad status reads remain an efficiency/scope concern; the requested GPU identity and dedicated capacity are correctly observed and reported.'
    verdicts[case_id] = {'verdict': 'correct_observed_run', 'cause_group': '', 'reason': reason}

assert set(verdicts) == {row['case_id'] for row in rows}
counts = dict(Counter(v['verdict'] for v in verdicts.values()))
assert counts == {'failed': 23, 'correct_observed_run': 50}
old = {row['case_id']: row for row in json.loads((private.parent / 'C03-status-batch702-private/adjudication.json').read_text(encoding='utf-8'))}
transitions = dict(Counter(old[k]['verdict']+' -> '+v['verdict'] for k, v in verdicts.items()))
gains = [k for k, v in verdicts.items() if v['verdict'] == 'correct_observed_run' and old[k]['verdict'] != 'correct_observed_run']
losses = [k for k, v in verdicts.items() if v['verdict'] != 'correct_observed_run' and old[k]['verdict'] == 'correct_observed_run']
assert len(gains) == 32 and not losses
prior_captured = rows[6:45]
fresh = sum(bool(row['core_calls']) for row in prior_captured)
assert fresh == 35
assert all('confirmar o cancelar' not in row['terminal']['final'].lower() and 'confirm or cancel' not in row['terminal']['final'].lower() for row in prior_captured)
(private / 'verdicts.json').write_text(json.dumps(verdicts, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
resources = json.loads((base / 'astra-status-batch704/resources.json').read_text(encoding='utf-8'))
note = f'''# Producto704:50respuestas correctas y23fallos de73

Se revisaron todos los finales y todas las etapas de composición contra los mismos criterios, entradas y orden689/694/702. Respecto702 hay32ganancias y0pérdidas:{transitions}. Los18aciertos previos se conservan. La tanda completa aún falla y no se acredita cobertura automáticamente.

La misma selección equivocada de browser.tabs.list vuelve a generar confirmación en el sexto turno. Esta vez los39pedidos siguientes dejan de responder a esa confirmación:35hacen una lectura nueva y32terminan correctamente. Tres lecturas todavía se redactan/rechazan mal; cuatro pedidos siguen sin elegir su lectura. La mejora de continuidad se respalda también con pruebas de invocación exacta, outbox, persistencia y retención de efectos inciertos. No se modifica catálogo, riesgo, modelo, muestreo ni fuentePython.

Fallos restantes:4aclaraciones innecesarias de ventanas,1selección de pestañas con confirmación,1rechazo falso del foco,3datos históricos sin lectura,2camposRAM mal interpretados,7lecturas soportadas no seleccionadas,3afirmaciones de red fuera de su evidencia y2rankingsCPU basados en segundos acumulados con miembros alterados. Los hechos de procesos se leen después del progreso; no se diagnostica ausencia por mirar sólo compose[0]. H0655 conserva el criterio contextual694 y su deuda de redacción. Los dos casos GPU compuestos mantienen lecturas redundantes o más amplias de lo necesario.

Validación703:18focales iniciales; dueñas ampliadas188pass/4fallosdefixture/0skip. Los4casos usaban token no canónico y fecha sin formatoO exacto; sólo se corrigió esa construcción. La ejecución enfocada final pasa11controles, incluidos esos4 y sus controles de identidad/reemplazo,0skips. No son199tests únicos: los4fallos de los192seleccionados quedan resueltos y hay7controles repetidos. Fast exit0,0warnings/errors,Release25,21s. Fuente productiva idéntica entre ambas ejecuciones; parser de confirmación intacto. Full693 es línea base, no Full703.

Conductor exit0/manifiesto intacto. GPU{resources['gpu_peak_mib']}MiB,RAM{resources['ram_peak_mib']}MiB,{resources['seconds']}s, sin infracciones. Esto mide procesos del diagnóstico sin UI/voz simultáneas, no el consumo total certificado de BAXY. Las cifras de memoria global que BAXY lee del PC incluyen otros programas y no son su propio consumo. El tiempo total no se presenta como mejora de latencia: ahora se ejecutan lecturas que antes eran bloqueadas.

Encuesta742/rev1248:26cubiertos/716abiertos/0NA. C03EN_CURSO. Se puede adoptar de forma delimitada la continuidad corregida con sus pruebas y esta comparación; persisten bloqueos de selección, hechos frescos y validador de identidades. No repetir el panel sin una nueva corrección o pregunta causal.
'''
(private / 'public-note.md').write_text(note, encoding='utf-8', newline='\n')
receipt = {'utc': datetime.now(timezone.utc).isoformat(), 'reviewed': 73, 'counts': counts,
           'transitions702': transitions, 'gains': gains, 'losses': losses,
           'prior_confirmation_captured': 39, 'now_fresh_reads': fresh, 'now_correct': 32,
           'private_review_sha256': hashlib.sha256((private / 'review.json').read_bytes()).hexdigest(),
           'review_scope': 'Root read all finals and facts; second readonly review of zero-based45–72 agrees. Initial ordinal-only selector comparison was rejected: HTTPid, request_id and turn id are different counters.',
           'new_coverage': 0, 'source_adopted': False, 'goal_complete': False}
(base / 'astra-status-batch704/MANUAL_REVIEW.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps({'counts': counts, 'transitions': transitions, 'gains': len(gains), 'losses': losses}))
