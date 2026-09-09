"""Credit H0040 only from its completed product variants; keep other cases intact."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
from collections import Counter

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
path = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-survey-requirements336-private/requirements.jsonl'
before = path.read_bytes()
assert hashlib.sha256(before).hexdigest() == '841e78b31ff2cb6d2f97f78b12692588ffae3a85d35f378cd31f0ce4691a8f0b'
result = json.loads((base/'astra-window-scope-product653/RESULT.json').read_text(encoding='utf-8'))
assert result['correct'] == 19 and result['named_application_reads_correct'] == 16
assert result['failed_cases'] == ['focus-en']
assert json.loads((base/'astra-window-scope-source652/RESULT.json').read_text(encoding='utf-8'))['adopted']
lines = before.splitlines(keepends=True)
now = datetime.now(timezone.utc).isoformat()
changed = 0
for index, line in enumerate(lines):
    row = json.loads(line)
    if row['case_id'] != 'H0040':
        continue
    assert row['verification_status'] == 'open' and row['expected_capability'] is True
    assert 'verification_reason_before653' not in row
    row['verification_reason_before653'] = row['verification_reason']
    row['verification_status'] = 'covered'
    row['generalization_status'] = 'verified_product_variants'
    row['verification_reason'] = (
        'Fuente652/producto653: literal H0040 y16 consultas por aplicación correctas. '
        'Variantes ES/EN, seis nombres, orden/cortesía, abierto/cerrado, cantidades0/1/2 '
        'y cuatro referencias con lectura nueva. Prosa de Spotify ya no afirma procesos sin observar. '
        'Conteos coinciden con ambas capturas independientes; AUMID registrado por fila. '
        'No se acredita el foco inglés (otra operación, sigue fallando), el validador factual649 '
        'ni UI/voz conjunta. Esta cobertura es de la conducta demostrada, no garantía universal del compositor.'
    )
    row['verification_evidence'].append({
        'campaign': 'astra-window-scope-product653',
        'method': 'Registered shared product; exact20panel647. All16 application-window queries correct; all four contextual references execute fresh reads. Every final manually adjudicated with current observed state and independent snapshots.',
        'private_evidence': str(path.parent.parent/'C03-window-scope-product653-private/adjudication.json'),
        'public_result_sha256': hashlib.sha256((base/'astra-window-scope-product653/RESULT.json').read_bytes()).hexdigest(),
        'source': 652, 'ui_or_voice_credit': False,
    })
    row['verification_updated_at'] = now
    lines[index] = (json.dumps(row, ensure_ascii=False)+'\n').encode('utf-8')
    changed += 1
assert changed == 1 and len(lines) == 742
after = b''.join(lines)
counts = Counter(json.loads(line)['verification_status'] for line in lines)
assert counts == {'covered': 26, 'open': 716}
path.write_bytes(after)
summary_path = base/'SURVEY_REQUIREMENTS336.json'
summary = json.loads(summary_path.read_text(encoding='utf-8'))
summary.update(requirements_sha256=hashlib.sha256(after).hexdigest(), updated_at=now,
               validated_current=26, verification_counts={'covered': 26, 'open': 716, 'not_applicable': 0})
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
state_path = base/'RELEVO_ACTIVO.json'
state = json.loads(state_path.read_text(encoding='utf-8'))
state['surveyVerificationCounts'] = summary['verification_counts']
state['checkpoint'] = '652 adoptada,653 producto19/20. H0040 cubierto por16 variantes reales; encuesta26/716/0. Contrato649 e idioma siguen pendientes.'
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print({'case_covered': 'H0040', 'counts': summary['verification_counts'], 'requirements_sha256': summary['requirements_sha256']})
