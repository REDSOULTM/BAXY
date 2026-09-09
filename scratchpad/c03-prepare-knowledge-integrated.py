import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
name = 'astra-knowledge-budget-integrated8'
out = base / name
out.mkdir(exist_ok=False)
known = json.loads((base / 'astra-real-users-contracts22/CASES.json').read_text(encoding='utf-8'))['development']
cases = [known[i] for i in (3, 4, 5)]
cases += [{'text_literal': 'Explica con detalle de qué gases se compone el aire y qué papel tiene la humedad.', 'source_references': [], 'kind': 'synthetic-detail-control'},
          {'text_literal': 'What is an SSID?', 'source_references': [], 'kind': 'synthetic-en-definition'}]
cases += json.loads((base / 'astra-audio-endpoint-name3/CASES.json').read_text(encoding='utf-8'))['development'][:1]
cases += [{'text_literal': 'no me molesta, dime la hora', 'source_references': [], 'kind': 'synthetic-known-negative-social-control'},
          {'text_literal': 'dime la hora', 'source_references': [], 'kind': 'synthetic-recovery-control'}]
assert len(cases) == 8
(out / 'CASES.json').write_text(json.dumps({'development': cases, 'method': 'Consumed historical inputs and explicitly synthetic regression controls; no fresh acceptance.'}, ensure_ascii=False, indent=2), encoding='utf-8')
(base / f'{name}.turns.jsonl').write_text(''.join(json.dumps({'cmd': 'turn', 'text': r['text_literal']}, ensure_ascii=False) + '\n' for r in cases), encoding='utf-8')
script = (root / 'scratchpad/c03-audio-endpoint-name3.py').read_text(encoding='utf-8')
script = script.replace('astra-audio-endpoint-name3', name).replace('c03-audio-endpoint-name3', 'c03-knowledge-budget-integrated8')
script = script.replace('Three previously consumed literal audio requests: identify output, read level, read mute. Current NativeAOT Core published from source with read-only PKEY_Device_FriendlyName and propagated endpointName.', 'Eight development turns, combining consumed literal knowledge/audio inputs and synthetic detail, English-definition, negative-social and recovery controls. Knowledge policy one sentence unless depth/format requested, budget256; no further prompt variants. Current Core includes verified endpointName.')
(root / 'scratchpad/c03-knowledge-budget-integrated8.py').write_text(script, encoding='utf-8')
print('Prepared eight preregistered development turns; no reserved inputs.')
