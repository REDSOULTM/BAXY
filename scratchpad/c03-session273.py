"""Review authorized owner logs without inventing missing user text or UI outcomes."""
from pathlib import Path
from datetime import datetime, timezone
import collections
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-owner264-snapshot268'
out = base / 'astra-owner-review273'
out.mkdir(exist_ok=False)
def read(name):
    return [dict(row, sourceLine=index) for index, line in enumerate((private / name).read_text(encoding='utf-8-sig').splitlines(), 1) if (row := json.loads(line))]
turns = read('turn-audit.jsonl')
compose = read('compose-audit.jsonl')
raw = read('raw-replies.jsonl')
final = [row for row in turns if row.get('phase') == 'final']
unique_compose = {}
for row in compose:
    if 'trace' not in row:
        continue
    key = (row['trace'], row.get('stage'), row.get('draft_sha256'), row.get('published'), row.get('reason'))
    unique_compose.setdefault(key, row)
published = [row for row in unique_compose.values() if row.get('published')]
reasons = collections.Counter(row.get('reason') for row in unique_compose.values() if row.get('reason'))
review = ['# Sesión manual264 — revisión parcial autorizada', '',
    'Fuente: copia privada268, preservada tras autorización del dueño. Los textos del usuario no aparecen completos en estos logs. No se reconstruyen por conjetura. «published» acredita la decisión del compositor, no una captura final de la pantalla. Los registros duplicados se mantienen en la fuente.', '',
    '## Decisiones finales de la mente', '']
for row in final:
    review.extend([f"### Request {row['request_id']} — línea {row['sourceLine']}", '',
        'Entrada literal: no disponible en este registro.', '',
        '```json', json.dumps({key:row.get(key) for key in ('decision_path', 'raw_decision', 'final', 'honesty', 'recovery') if key in row}, ensure_ascii=False, indent=2), '```', ''])
review.extend(['## Composición: borradores admitidos, deduplicados por trace/etapa/hash', ''])
for row in published:
    review.extend([f"### {row['trace']} — {row['intent']} — línea {row['sourceLine']}", '',
        row.get('draft', ''), '', 'Situación recibida:', '```json', row.get('situation', ''), '```', ''])
review.extend(['## Respuestas brutas del modelo — no equivalen a publicación', ''])
for row in raw:
    review.extend([f"### Línea {row['sourceLine']} — {row.get('stage')} — intento {row.get('attempt')}", '',
        f"Hash del pedido: `{row.get('request_sha256')}`", '', row.get('raw_reply', ''), ''])
review_path = private / 'REVIEW273.md'
assert not review_path.exists()
review_path.write_text('\n'.join(review) + '\n', encoding='utf-8')
summary = {'utc': datetime.now(timezone.utc).isoformat(), 'privateReport': str(review_path),
    'reportSha256': hashlib.sha256(review_path.read_bytes()).hexdigest(),
    'turnAuditRows': len(turns), 'finalDecisions': len(final),
    'finalKinds': dict(collections.Counter(row.get('final', {}).get('kind') for row in final)),
    'attemptFailureTypes': dict(collections.Counter(row.get('error_type') for row in turns if row.get('phase') == 'attempt_failure')),
    'composeAuditRows': len(compose), 'composeDraftRows': sum('trace' in row for row in compose),
    'uniqueComposeDrafts': len(unique_compose), 'uniqueComposerPublishedDrafts': len(published),
    'composeRejectionReasons': dict(reasons), 'rawReplies': len(raw),
    'distinctRawRequestHashes': len({row['request_sha256'] for row in raw}),
    'fullUserTranscriptRecovered': False, 'uiPublicationVerified': False,
    'automaticallyReplayedOwnerEffects': False}
(out / 'RESULT.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False))
