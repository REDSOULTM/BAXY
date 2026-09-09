"""Link each evaluated survey literal, including open groups, to its actual verdict."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-conversation-regression592-private'
registry = private.parent / 'C03-survey-requirements336-private/requirements.jsonl'
backup = private / 'requirements-before-linking-open-groups.jsonl'
assert not backup.exists()
backup.write_bytes(registry.read_bytes())
requirements = [json.loads(line) for line in registry.read_text(encoding='utf-8').splitlines()]
adjudication = json.loads((private / 'adjudication.json').read_text(encoding='utf-8'))
by_id = {row['case_id']: row for row in adjudication if row['case_id'].startswith('H')}
group_failures = {
    'identity': 'fallan H0012 y dos variantes inglesas de identidad',
    'greeting': 'la variante con Atlas atribuye el nombre al usuario sin fundamento',
    'small-talk': 'H0241 y la variante española conservan un fallo gramatical',
}
for row in requirements:
    measured = by_id.get(row['case_id'])
    if measured is None:
        continue
    evidence = next((item for item in row['verification_evidence'] if item.get('campaign') == 'astra-conversation-regression592'), None)
    if evidence is None:
        evidence = {'campaign': 'astra-conversation-regression592',
                    'source': '590 WIP; hashes in PREREG',
                    'private_adjudication': str(private / 'adjudication.json'),
                    'ui_or_voice_credit': False}
        row['verification_evidence'].append(evidence)
    evidence.update(ordinal=measured['ordinal'], literal_verdict=measured['verdict'],
                    group=measured['group'], group_passed=measured['group'] == 'thanks')
    if measured['group'] != 'thanks':
        assert row['verification_status'] == 'open'
        row.update(generalization_status='failed_variants_in_preregistered_group',
                   verification_updated_at=datetime.now(timezone.utc).isoformat(),
                   verification_reason=f"592: literal {measured['verdict']}; grupo abierto porque {group_failures[measured['group']]}. No acreditar el requisito sólo por parentesco ni por publicación de una respuesta.")
assert Counter(row['verification_status'] for row in requirements) == {'covered': 16, 'open': 726}
registry.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in requirements), encoding='utf-8', newline='\n')
path = root / 'artifacts/comprobaciones/C03/SURVEY_REQUIREMENTS336.json'
summary = json.loads(path.read_text(encoding='utf-8'))
summary.update(requirements_sha256=hashlib.sha256(registry.read_bytes()).hexdigest(),
               updated_at=datetime.now(timezone.utc).isoformat())
path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print('All21 measured survey literals linked;16covered/726open/0NA unchanged.')
