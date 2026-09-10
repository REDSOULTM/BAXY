"""Keep the current K2 comparison recoverable without altering C03 coverage."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json

p = argparse.ArgumentParser()
p.add_argument('--active-tag', default='')
p.add_argument('--session', type=int, default=0)
p.add_argument('--note', required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
comparison = base / 'K2_HORIZON_COMPARISON696'
tags = ['q8-high-reference1', 'qwen-registered1', '37-q4-high-cpu-kv1', 'qwen-documented1',
        '09-bf16-high-reference1', '37-q4-high-gpu8k1', '37-q4-high-native-selectors1',
        '37-q8-high-native-gpu24-noop1', '09-bf16-high-native-selectors1', '37-q4-low-native-gpu8k1']
completed = {}
for tag in tags:
    folder = comparison / ('run-' + tag)
    if (folder / 'ADJUDICATION.json').exists():
        adj = json.loads((folder / 'ADJUDICATION.json').read_text(encoding='utf-8'))
        m = json.loads((folder / 'MEASUREMENTS.json').read_text(encoding='utf-8'))
        completed[tag] = {k: adj[k] for k in ['pass', 'fail', 'selector_pass', 'prose_and_conversation_pass']}
        completed[tag].update(cases=m['responses'], gpu_mib=m['resources']['gpu_peak_mib'],
                              ram_mib=m['resources']['ram_peak_mib'], median_seconds=m['seconds']['median'],
                              max_seconds=m['seconds']['max'])
path = base / 'RELEVO_ACTIVO.json'
state = json.loads(path.read_text(encoding='utf-8-sig'))
state['confirmedAtUtc'] = datetime.now(timezone.utc).isoformat()
state['checkpoint'] = a.note
state['continuation'] = 'Cerrar controles K2 pendientes, adjudicar, escribir y abrir reporte comparativo antes de reanudar reparaciones Qwen. C03 no terminado; encuesta 26/716/0 intacta.'
state['activeValidation'] = ({'name': a.active_tag, 'sessionId': a.session,
                              'log': 'TEMP/c03-k2-run696-' + a.active_tag + '.log'} if a.active_tag else None)
state['activeReadOnlyAgent'] = None
state['k2Comparison']['weightsVerified'] = 5
state['k2Comparison']['completedNativePanels'] = completed
state['k2Comparison']['panelTag'] = a.active_tag or None
state['k2Comparison']['smokeAttempts'] = ['q8-auto: regex_error before readiness',
    'q8-unicode1: 261/285 token IDs; missing NFC; no generation',
    'q8-nfc1: 285/285 and three smoke cases pass',
    '37-q4-high-cpu-kv1: 285/285 and three smoke cases pass']
state['k2Comparison']['rejectedResourceProfiles'] = [{
    'tag': '37-q8-high-native-gpu28-1', 'gpu_peak_mib': 4154.70703125,
    'reason': 'Exceeded product 4096 MiB ceiling during load, before readiness; zero generations. Sampler guard overshot.'}]
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
status = '# Estado vigente de la comparación K2 696\n\n' + a.note + '\n\n'
status += 'Tandas Qwen pausadas. Runtime productivo intacto. C03 activo: 26 cubiertos / 716 abiertos / 0 NA. Las pruebas nativas no conceden cobertura ni certifican UI/voz.\n\n'
status += 'Detalle recuperable y sesiones: RELEVO_ACTIVO.json; evidencia: K2_HORIZON_COMPARISON696.\n\n'
handoff = base / 'HANDOFF.md'
previous = handoff.read_text(encoding='utf-8-sig')
marker = '\n<!-- END_CURRENT_K2_STATUS -->\n'
if marker in previous:
    previous = previous.split(marker, 1)[1]
handoff.write_text(status + marker + previous, encoding='utf-8')
checkpoint = base / 'CHECKPOINT.md'
with checkpoint.open('a', encoding='utf-8') as f:
    f.write('\n\n## Comparación K2 696 — ' + state['confirmedAtUtc'] + '\n\n' + a.note + '\n')
print(json.dumps({'completed': len(completed), 'active': state['activeValidation']}, ensure_ascii=False))
