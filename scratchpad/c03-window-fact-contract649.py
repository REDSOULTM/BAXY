"""Probe the current prose contract with consistent and unsupported claims."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'src'))
from baxy_mind.llm import compose_visible_defect

out = root/'artifacts/comprobaciones/C03/astra-window-fact-contract649'
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-window-fact-contract649-private'
out.mkdir(exist_ok=False); private.mkdir(exist_ok=False)
def write(p, v): p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
observed = {'version': 1, 'requestedName': 'Spotify', 'displayName': 'Spotify',
    'installed': True, 'hasVisibleWindow': False, 'visibleWindowCount': 0,
    'authority': 'windows_start_catalog_and_visible_window_snapshot'}
facts = {'situation': json.dumps({'kind': 'operation', 'operation': 'window.application.status',
    'polarity': 'success', 'verified': True, 'succeeded': True, 'observed': observed})}
cases = [
    ('observed647', 'And Spotify?', 'Spotify is installed and running, but no window is currently visible.', False, 'Process liveness not observed.'),
    ('bounded-en', 'And Spotify?', 'Spotify is installed but has no visible window.', True, 'Preserves installation and visibility.'),
    ('count-contradiction-en', 'And Spotify?', 'Spotify has two visible windows.', False, 'Observed zero, not two.'),
    ('installation-contradiction-en', 'And Spotify?', 'Spotify is not installed.', False, 'Observed installed=true.'),
    ('unobserved-negative-en', 'And Spotify?', 'Spotify is not running.', False, 'Absence of a process was not observed either.'),
    ('bounded-unknown-en', 'And Spotify?', 'Spotify is installed with no visible window; background processes were not checked.', True, 'Explicitly preserves the unobserved scope.'),
    ('bounded-es', '¿Y Spotify?', 'Spotify está instalado, pero no tiene ventanas visibles.', True, 'Preserves installation and visibility.'),
    ('count-contradiction-es', '¿Y Spotify?', 'Spotify tiene tres ventanas visibles.', False, 'Observed zero, not three.'),
    ('installation-contradiction-es', '¿Y Spotify?', 'Spotify no está instalado.', False, 'Observed installed=true.'),
    ('unobserved-positive-es', '¿Y Spotify?', 'Spotify está ejecutándose en segundo plano.', False, 'Process liveness not observed.'),
    ('bounded-unknown-es', '¿Y Spotify?', 'Spotify está instalado y no tiene ventanas visibles; no comprobé sus procesos.', True, 'Explicitly preserves the unobserved scope.'),
]
write(out/'PREREG.json', {'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Read-only invocation of the current public prose validator. One observed647 draft and ten declared controls against the same payload. No LLM, dispatch, source changes or product credit.',
    'criteria': 'Reject both fabricated process liveness polarities and contradictions of installed/window count. Accept bounded observations and explicit unknowns. These are contract fixtures, not model-generated results.',
    'source_sha256': sha(root/'src/baxy_mind/llm.py')})
judged = []
for case_id, text, reply, expected_accept, reason in cases:
    defect = compose_visible_defect(reply, 'status', text, facts)
    judged.append({'case_id': case_id, 'text': text, 'reply': reply, 'expected_accept': expected_accept,
        'reason': reason, 'actual_defect': defect, 'correct': bool(defect) != expected_accept})
    print(json.dumps({'case_id': case_id, 'defect': defect, 'correct': bool(defect) != expected_accept}, ensure_ascii=False))
write(private/'adjudication.json', {'facts': facts, 'cases': judged})
write(out/'RESULT.json', {'correct': sum(r['correct'] for r in judged), 'total': len(judged),
    'failed_cases': [r['case_id'] for r in judged if not r['correct']],
    'source_modified': False, 'model_or_product_credit': False,
    'private_sha256': sha(private/'adjudication.json')})
